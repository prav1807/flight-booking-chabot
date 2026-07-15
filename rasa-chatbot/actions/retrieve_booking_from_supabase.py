from typing import Any, Dict, List, Text

from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.events import SlotSet

from .middleware import IdentityService, PIIGuard, AuditLogger, RateLimiter

_audit_logger = AuditLogger()
_rate_limiter = RateLimiter()


class RetrieveBookingFromSupabase(Action):
    def name(self) -> Text:
        return "retrieve_booking_from_supabase"

    def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict[Text, Any]]:

        booking_reference = tracker.get_slot("booking_reference_lookup")
        surname = tracker.get_slot("booking_lookup_surname")

        if not booking_reference:
            dispatcher.utter_message(text="Please enter a valid booking reference.")
            return []

        booking_reference = str(booking_reference).strip()

        # ── Rate limiting: protect against repeated brute-force lookup attempts ──
        limit_result = _rate_limiter.check_auth_attempt(tracker.sender_id)
        if not limit_result.get("allowed"):
            _audit_logger.log(
                agent="Identity Service",
                action="retrieve_booking",
                sender_id=tracker.sender_id,
                input_data={"booking_reference": booking_reference},
                output_data=limit_result,
                status="rate_limited",
            )
            dispatcher.utter_message(
                text=(
                    "You've made too many lookup attempts recently. "
                    f"Please try again in about {int(limit_result.get('retry_after_seconds', 60))} seconds."
                )
            )
            return [
                SlotSet("booking_reference_lookup", None),
                SlotSet("booking_lookup_surname", None),
            ]

        # ── Identity verification: never let the LLM decide authentication ──
        identity_result = IdentityService().verify(booking_reference, surname)

        _audit_logger.log(
            agent="Identity Service",
            action="verify_booking_access",
            sender_id=tracker.sender_id,
            input_data={"booking_reference": booking_reference},
            output_data={"status": identity_result.get("status", "OK")},
            status="authenticated" if identity_result.get("authenticated") else "rejected",
        )

        if not identity_result.get("authenticated"):
            status = identity_result.get("status")
            if status == "BOOKING_NOT_FOUND":
                dispatcher.utter_message(
                    text="Sorry, I could not find a booking with that reference."
                )
            elif status == "SURNAME_MISMATCH":
                dispatcher.utter_message(
                    text="The surname doesn't match our records for this booking reference. Please try again."
                )
            else:
                dispatcher.utter_message(
                    text="I couldn't verify this booking right now. Please double-check your details."
                )
            return [
                SlotSet("booking_reference_lookup", None),
                SlotSet("booking_lookup_surname", None),
            ]

        booking = identity_result["booking"]

        # ── PII Guard: mask sensitive fields before they are ever displayed ──
        masked_booking = PIIGuard().mask(booking)

        dispatcher.utter_message(
            text=(
                "Here are your booking details:\n\n"
                f"Booking Reference: {masked_booking.get('id')}\n"
                f"Route: {masked_booking.get('origin')} → {masked_booking.get('destination')}\n"
                f"Trip Type: {masked_booking.get('trip_type')}\n"
                f"Departure Date: {masked_booking.get('departure_date')}\n"
                f"Return Date: {masked_booking.get('return_date')}\n"
                f"Passengers: {masked_booking.get('passengers')}\n"
                f"Travel Class: {masked_booking.get('travel_class')}\n"
                f"Airline: {masked_booking.get('airline')}\n"
                f"Price: {masked_booking.get('price')} {masked_booking.get('currency')}\n"
                f"Passenger: {masked_booking.get('passenger_full_name')}\n"
                f"Email: {masked_booking.get('passenger_email')}\n"
                f"Phone: {masked_booking.get('passenger_phone')}\n"
                f"Status: {masked_booking.get('booking_status')}"
            )
        )

        _rate_limiter.reset(tracker.sender_id, "auth_attempt")

        return [
            SlotSet("booking_reference_lookup", None),
            SlotSet("booking_lookup_surname", None),
        ]
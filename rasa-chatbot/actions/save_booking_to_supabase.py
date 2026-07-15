from typing import Any, Dict, List, Text

from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.events import SlotSet, FollowupAction

from .supabase_client import SupabaseClient
from .middleware import PolicyGuard, AuditLogger, PIIGuard

_audit_logger = AuditLogger()

# Columns that may not exist yet in older `bookings` tables. If Supabase
# rejects the insert because one of these is missing (PGRST204), we retry
# without them rather than losing the entire booking. Run the migration in
# docs/AVIATION_CHATBOT_ARCHITECTURE.md / README to persist these permanently.
_OPTIONAL_COLUMNS = ("ticket_number", "payment_status", "payment_session_id")


class SaveBookingToSupabase(Action):
    def name(self) -> Text:
        return "save_booking_to_supabase"

    def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict[Text, Any]]:

        offer_map = tracker.get_slot("duffel_offer_map") or {}
        selected_flight = tracker.get_slot("selected_flight")
        selected_offer = offer_map.get(str(selected_flight), {})

        ticket_number = tracker.get_slot("ticket_number")
        booking_status = "ticketed" if ticket_number else "confirmed_draft"

        booking_data = {
            "origin": tracker.get_slot("origin"),
            "destination": tracker.get_slot("destination"),
            "trip_type": tracker.get_slot("trip_type"),
            "departure_date": tracker.get_slot("departure_date"),
            "return_date": tracker.get_slot("return_date"),
            "passengers": tracker.get_slot("passengers"),
            "travel_class": tracker.get_slot("travel_class"),
            "selected_duffel_offer_id": tracker.get_slot("selected_duffel_offer_id"),
            "airline": selected_offer.get("airline"),
            "price": selected_offer.get("amount"),
            "currency": selected_offer.get("currency"),
            "passenger_full_name": tracker.get_slot("passenger_full_name"),
            "passenger_email": tracker.get_slot("passenger_email"),
            "passenger_phone": tracker.get_slot("passenger_phone"),
            "booking_status": booking_status,
            "ticket_number": ticket_number,
            "payment_status": tracker.get_slot("payment_status"),
            "payment_session_id": tracker.get_slot("payment_session_id"),
        }

        # ── Policy Guard: final deterministic check before writing to storage ──
        policy_result = PolicyGuard().check("create_booking", booking_data)
        _audit_logger.log(
            agent="Policy Guard",
            action="create_booking",
            sender_id=tracker.sender_id,
            input_data=PIIGuard().mask(booking_data),
            output_data=policy_result,
            status="approved" if policy_result.get("approved") else "rejected",
        )

        if not policy_result.get("approved"):
            dispatcher.utter_message(
                text=(
                    f"I couldn't finalise this booking: {policy_result.get('reason')} "
                    "Please review the details and try again."
                )
            )
            return [
                SlotSet("booking_confirmed", False),
                SlotSet("booking_confirmation", None),
                FollowupAction("utter_anything_else"),
            ]

        try:
            booking_id, dropped_columns = self._insert_with_fallback(booking_data)

            _audit_logger.log(
                agent="Booking Agent",
                action="save_booking",
                sender_id=tracker.sender_id,
                input_data={"booking_reference": booking_id},
                output_data={"booking_status": booking_status, "dropped_columns": dropped_columns},
                status="success",
            )

            confirmation_text = f"Your booking has been saved successfully. Booking reference: {booking_id}"
            if ticket_number:
                confirmation_text = (
                    f"Your booking has been saved and ticketed. Booking reference: {booking_id}"
                )
            if dropped_columns:
                confirmation_text += (
                    f"\n\n(Note: {', '.join(dropped_columns)} could not be stored — "
                    "run the bookings table migration to persist these fields.)"
                )

            dispatcher.utter_message(text=confirmation_text)

            return [
                SlotSet("booking_confirmed", True),
                SlotSet("booking_reference", booking_id),
                FollowupAction("utter_anything_else"),
            ]

        except Exception as e:
            _audit_logger.log(
                agent="Booking Agent",
                action="save_booking",
                sender_id=tracker.sender_id,
                input_data={},
                output_data={"error": str(e)},
                status="error",
            )
            dispatcher.utter_message(
                text=f"The booking was confirmed, but I could not save it to Supabase. Error: {str(e)}"
            )
            return [
                FollowupAction("utter_anything_else"),
            ]

    def _insert_with_fallback(self, booking_data: Dict[str, Any]):
        """
        Inserts the booking row, retrying without any column Supabase
        reports as missing (PGRST204 — "Could not find the 'X' column").
        This keeps the core booking from being lost on an un-migrated
        `bookings` table while still saving payment/ticketing data once
        the schema has been extended. Returns (booking_id, dropped_columns).
        """
        data = dict(booking_data)
        dropped_columns = []
        client = SupabaseClient().client

        for _ in range(len(_OPTIONAL_COLUMNS) + 1):
            try:
                response = client.table("bookings").insert(data).execute()
                return response.data[0]["id"], dropped_columns
            except Exception as e:
                message = str(e)
                missing_column = None
                for column in _OPTIONAL_COLUMNS:
                    if f"'{column}'" in message and "column" in message.lower():
                        missing_column = column
                        break
                if missing_column and missing_column in data:
                    data.pop(missing_column)
                    dropped_columns.append(missing_column)
                    continue
                raise

        raise RuntimeError("Could not save booking after removing optional columns.")
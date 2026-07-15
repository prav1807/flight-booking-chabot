from typing import Any, Dict, List, Text
import json

from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.events import SlotSet

from .duffel_client import DuffelClient
from .normalisation_service import NormalizationService
from .middleware import IdentityService, PolicyGuard, PIIGuard, AuditLogger, RateLimiter
from .crewai_agents.tools.change_fee_calculator import ChangeFeeCalculatorTool
from .crewai_agents.crews import run_change_booking_crew

_audit_logger = AuditLogger()
_rate_limiter = RateLimiter()


class CrewaiChangeBooking(Action):
    """
    Verifies identity, checks policy, calculates the deterministic change
    fee, then uses the Change Booking Agent (CrewAI) to explain the result
    in natural language. Never lets the LLM decide the fee or the approval —
    those come from PolicyGuard and ChangeFeeCalculatorTool only.
    """

    def name(self) -> Text:
        return "crewai_change_booking"

    def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict[Text, Any]]:

        booking_reference = tracker.get_slot("booking_reference_lookup")
        surname = tracker.get_slot("booking_lookup_surname")
        new_departure_date_raw = tracker.get_slot("new_departure_date")

        if not booking_reference or not new_departure_date_raw:
            dispatcher.utter_message(
                text="I need your booking reference and the new departure date to proceed."
            )
            return []

        booking_reference = str(booking_reference).strip()

        # ── Rate limiting: protect against repeated brute-force lookup attempts ──
        limit_result = _rate_limiter.check_auth_attempt(tracker.sender_id)
        if not limit_result.get("allowed"):
            _audit_logger.log(
                agent="Rate Limiter",
                action="change_booking",
                sender_id=tracker.sender_id,
                input_data={"booking_reference": booking_reference},
                output_data=limit_result,
                status="rate_limited",
            )
            dispatcher.utter_message(
                text=(
                    "You've made too many attempts recently. "
                    f"Please try again in about {int(limit_result.get('retry_after_seconds', 60))} seconds."
                )
            )
            return self._reset_slots()

        # ── Identity verification: never let the LLM decide authentication ──
        identity_result = IdentityService().verify(booking_reference, surname)

        _audit_logger.log(
            agent="Identity Service",
            action="verify_change_booking_access",
            sender_id=tracker.sender_id,
            input_data={"booking_reference": booking_reference},
            output_data={"status": identity_result.get("status", "OK")},
            status="authenticated" if identity_result.get("authenticated") else "rejected",
        )

        if not identity_result.get("authenticated"):
            status = identity_result.get("status")
            if status == "BOOKING_NOT_FOUND":
                dispatcher.utter_message(text="Sorry, I could not find a booking with that reference.")
            elif status == "SURNAME_MISMATCH":
                dispatcher.utter_message(
                    text="The surname doesn't match our records for this booking reference. Please try again."
                )
            else:
                dispatcher.utter_message(
                    text="I couldn't verify this booking right now. Please double-check your details."
                )
            return self._reset_slots()

        booking = identity_result["booking"]
        new_departure_date = NormalizationService.normalize_date(new_departure_date_raw)

        # ── Policy Guard: deterministic approval, never overridden by the LLM ──
        policy_context = {
            "booking_reference": booking_reference,
            "fare_is_non_changeable": booking.get("booking_status") == "ticketed"
            and str(booking.get("travel_class", "")).lower() == "economy",
            "old_departure_date": booking.get("departure_date"),
            "new_departure_date": new_departure_date,
        }
        policy_result = PolicyGuard().check("change_booking", policy_context)

        _audit_logger.log(
            agent="Policy Guard",
            action="change_booking",
            sender_id=tracker.sender_id,
            input_data=PIIGuard().mask({**policy_context, "booking_id": booking.get("id")}),
            output_data=policy_result,
            status="approved" if policy_result.get("approved") else "rejected",
        )

        if not policy_result.get("approved"):
            dispatcher.utter_message(
                text=f"I can't process this change: {policy_result.get('reason')}"
            )
            return self._reset_slots()

        # ── Deterministic fee calculation (never LLM-decided) ──
        new_offer_price = self._lookup_new_price(booking, new_departure_date)

        fee_result_json = ChangeFeeCalculatorTool()._run(
            json.dumps({
                "travel_class": booking.get("travel_class"),
                "original_price": booking.get("price"),
                "currency": booking.get("currency"),
                "new_offer_price": new_offer_price,
            })
        )
        fee_result = json.loads(fee_result_json)

        change_context = {
            "booking_reference": booking_reference,
            "old_departure_date": booking.get("departure_date"),
            "new_departure_date": new_departure_date,
            "origin": booking.get("origin"),
            "destination": booking.get("destination"),
        }

        # ── CrewAI agent: natural-language framing only, numbers are fixed ──
        crew_result = run_change_booking_crew(change_context, fee_result)

        _audit_logger.log(
            agent="Change Booking Agent",
            action="explain_change_fee",
            sender_id=tracker.sender_id,
            input_data={"change_context": change_context, "fee_result": fee_result},
            output_data={"message_generated": bool(crew_result.get("message"))},
            status="success",
        )

        dispatcher.utter_message(text=crew_result.get("message"))

        _rate_limiter.reset(tracker.sender_id, "auth_attempt")

        return [
            SlotSet("change_fee_amount", f"{fee_result.get('total_change_cost')} {fee_result.get('currency')}"),
        ]

    def _lookup_new_price(self, booking: Dict[str, Any], new_departure_date: str):
        """
        Best-effort lookup of the new date's cheapest fare via Duffel, so the
        fee calculator can account for a fare difference. Any failure here
        degrades gracefully — the change fee still applies, just without a
        fare-difference component.
        """
        try:
            client = DuffelClient()
            origin_code = NormalizationService.normalize_airport(booking.get("origin"))
            destination_code = NormalizationService.normalize_airport(booking.get("destination"))

            offers = client.create_offer_request(
                origin=origin_code,
                destination=destination_code,
                departure_date=new_departure_date,
                return_date=None,
                passengers_count=int(booking.get("passengers") or 1),
                cabin_class=booking.get("travel_class"),
            )
            if not offers:
                return None
            cheapest = min(offers, key=lambda o: float(o.get("total_amount") or float("inf")))
            return cheapest.get("total_amount")
        except Exception:
            return None

    @staticmethod
    def _reset_slots() -> List[Dict[Text, Any]]:
        return [
            SlotSet("booking_reference_lookup", None),
            SlotSet("booking_lookup_surname", None),
            SlotSet("new_departure_date", None),
        ]

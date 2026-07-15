from typing import Any, Dict, List, Text

from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.events import SlotSet, FollowupAction

from .supabase_client import SupabaseClient
from .normalisation_service import NormalizationService
from .middleware import IdentityService, AuditLogger, PIIGuard

_audit_logger = AuditLogger()

_POSITIVE_RESPONSES = {"yes", "yes proceed", "proceed", "confirm", "y", "ok", "okay", "sure"}
_NEGATIVE_RESPONSES = {"no", "no cancel", "cancel", "n", "stop"}


class ApplyBookingChange(Action):
    """
    Applies (or cancels) a previously priced, previously approved date
    change. The fee/approval were already computed deterministically by
    CrewaiChangeBooking — this action only persists the outcome once the
    customer confirms.
    """

    def name(self) -> Text:
        return "apply_booking_change"

    def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict[Text, Any]]:

        confirmation_raw = str(tracker.get_slot("change_confirmation") or "").lower().strip()
        booking_reference = tracker.get_slot("booking_reference_lookup")
        surname = tracker.get_slot("booking_lookup_surname")
        new_departure_date = NormalizationService.normalize_date(
            tracker.get_slot("new_departure_date")
        )
        change_fee_amount = tracker.get_slot("change_fee_amount")

        if confirmation_raw in _NEGATIVE_RESPONSES or "no" in confirmation_raw.split():
            _audit_logger.log(
                agent="Change Booking Agent",
                action="apply_booking_change",
                sender_id=tracker.sender_id,
                input_data={"booking_reference": booking_reference},
                output_data={"decision": "cancelled_by_user"},
                status="cancelled",
            )
            dispatcher.utter_message(text="No problem, I've cancelled the date change request.")
            return self._reset_slots()

        if confirmation_raw not in _POSITIVE_RESPONSES and "yes" not in confirmation_raw.split():
            dispatcher.utter_message(
                text="Please confirm whether you'd like to proceed with the change (yes/no)."
            )
            return []

        if not booking_reference or not new_departure_date:
            dispatcher.utter_message(
                text="Something went wrong — I've lost track of the booking details. Please start the change request again."
            )
            return self._reset_slots()

        # ── Re-verify identity: never trust that a stale session is still authorised ──
        identity_result = IdentityService().verify(booking_reference, surname)
        if not identity_result.get("authenticated"):
            _audit_logger.log(
                agent="Identity Service",
                action="apply_booking_change",
                sender_id=tracker.sender_id,
                input_data={"booking_reference": booking_reference},
                output_data={"status": identity_result.get("status")},
                status="rejected",
            )
            dispatcher.utter_message(
                text="I couldn't re-verify this booking, so I can't apply the change. Please start again."
            )
            return self._reset_slots()

        try:
            client = SupabaseClient().client
            update_data = {"departure_date": new_departure_date}

            try:
                update_data["change_fee_paid"] = change_fee_amount
                client.table("bookings").update(update_data).eq(
                    "id", str(booking_reference).strip()
                ).execute()
            except Exception as inner_e:
                if "change_fee_paid" in str(inner_e) or "column" in str(inner_e).lower():
                    update_data.pop("change_fee_paid", None)
                    client.table("bookings").update(update_data).eq(
                        "id", str(booking_reference).strip()
                    ).execute()
                else:
                    raise

            _audit_logger.log(
                agent="Change Booking Agent",
                action="apply_booking_change",
                sender_id=tracker.sender_id,
                input_data=PIIGuard().mask(
                    {"booking_reference": booking_reference, "new_departure_date": new_departure_date}
                ),
                output_data={"change_fee_amount": change_fee_amount},
                status="success",
            )

            dispatcher.utter_message(
                text=(
                    f"Your booking {booking_reference} has been updated. "
                    f"New departure date: {new_departure_date}. "
                    f"Change fee charged: {change_fee_amount}."
                )
            )

        except Exception as e:
            _audit_logger.log(
                agent="Change Booking Agent",
                action="apply_booking_change",
                sender_id=tracker.sender_id,
                input_data={"booking_reference": booking_reference},
                output_data={"error": str(e)},
                status="error",
            )
            dispatcher.utter_message(
                text=f"Sorry, I couldn't apply this change right now. Error: {str(e)}"
            )

        return self._reset_slots() + [FollowupAction("utter_anything_else")]

    @staticmethod
    def _reset_slots() -> List[Dict[Text, Any]]:
        return [
            SlotSet("booking_reference_lookup", None),
            SlotSet("booking_lookup_surname", None),
            SlotSet("new_departure_date", None),
            SlotSet("change_fee_amount", None),
            SlotSet("change_confirmation", None),
        ]

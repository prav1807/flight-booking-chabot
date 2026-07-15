from typing import Any, Dict, List, Text

from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.events import SlotSet, FollowupAction

from .payment_client import PaymentClient
from .middleware import PolicyGuard, AuditLogger, PIIGuard

_audit_logger = AuditLogger()


class CreatePaymentSession(Action):
    """
    Payment Agent (deterministic) — creates a checkout session for the
    selected flight offer. The LLM never sees or handles card data; it only
    shows the checkout link and waits for a payment-success signal.
    """

    def name(self) -> Text:
        return "create_payment_session"

    def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict[Text, Any]]:

        offer_map = tracker.get_slot("duffel_offer_map") or {}
        selected_flight = tracker.get_slot("selected_flight")
        selected_offer = offer_map.get(str(selected_flight), {})

        amount = selected_offer.get("amount")
        currency = selected_offer.get("currency")

        booking_context = {
            "origin": tracker.get_slot("origin"),
            "destination": tracker.get_slot("destination"),
            "departure_date": tracker.get_slot("departure_date"),
            "return_date": tracker.get_slot("return_date"),
            "trip_type": tracker.get_slot("trip_type"),
            "passengers": tracker.get_slot("passengers"),
            "travel_class": tracker.get_slot("travel_class"),
            "passenger_full_name": tracker.get_slot("passenger_full_name"),
            "passenger_email": tracker.get_slot("passenger_email"),
            "selected_duffel_offer_id": tracker.get_slot("selected_duffel_offer_id"),
        }

        # ── Policy Guard: re-verify the booking is still valid before payment ──
        policy_result = PolicyGuard().check("create_booking", booking_context)
        _audit_logger.log(
            agent="Policy Guard",
            action="create_payment_session",
            sender_id=tracker.sender_id,
            input_data=PIIGuard().mask(booking_context),
            output_data=policy_result,
            status="approved" if policy_result.get("approved") else "rejected",
        )

        if not policy_result.get("approved"):
            dispatcher.utter_message(
                text=f"I can't proceed to payment: {policy_result.get('reason')}"
            )
            return [
                SlotSet("booking_confirmed", False),
                SlotSet("booking_confirmation", None),
                FollowupAction("utter_anything_else"),
            ]

        if amount is None or currency is None:
            dispatcher.utter_message(
                text="I couldn't determine the price for this booking. Please restart your search."
            )
            return [FollowupAction("utter_anything_else")]

        session = PaymentClient().create_checkout_session(
            amount=amount,
            currency=currency,
            booking_reference=str(selected_flight),
        )

        _audit_logger.log(
            agent="Payment Agent",
            action="create_checkout_session",
            sender_id=tracker.sender_id,
            input_data={"amount": amount, "currency": currency},
            output_data={"session_id": session["session_id"], "status": session["status"]},
            status="pending",
        )

        dispatcher.utter_message(
            text=(
                f"Please complete your payment of {amount} {currency} using the secure checkout link below:\n\n"
                f"{session['checkout_url']}\n\n"
                "Once you've completed payment, let me know (e.g. \"I've paid\")."
            )
        )

        return [
            SlotSet("payment_session_id", session["session_id"]),
            SlotSet("payment_checkout_url", session["checkout_url"]),
            SlotSet("payment_status", "pending"),
        ]

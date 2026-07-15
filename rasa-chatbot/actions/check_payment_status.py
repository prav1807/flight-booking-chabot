from typing import Any, Dict, List, Text

from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.events import SlotSet, FollowupAction

from .payment_client import PaymentClient
from .middleware import AuditLogger

_audit_logger = AuditLogger()


class CheckPaymentStatus(Action):
    """
    Payment Agent (deterministic) — checks whether the checkout session has
    been paid. The AI only waits for a payment-success event; it never
    decides success/failure itself.

    In simulated mode, the user's "I've paid" message is treated as the
    stand-in for Stripe's webhook call (`confirm_payment`), and the status
    is then re-read via `get_session_status` exactly as a real webhook flow
    would be verified — swapping in a real gateway later only changes what
    happens inside PaymentClient.
    """

    def name(self) -> Text:
        return "check_payment_status"

    def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict[Text, Any]]:

        session_id = tracker.get_slot("payment_session_id")

        if not session_id:
            dispatcher.utter_message(
                text="I don't have an active payment session. Let's restart the booking."
            )
            return [FollowupAction("utter_anything_else")]

        client = PaymentClient()

        if client.simulated:
            # Stand-in for the payment provider's webhook confirming success.
            client.confirm_payment(session_id)

        result = client.get_session_status(session_id)
        status = result.get("status")

        _audit_logger.log(
            agent="Payment Agent",
            action="check_payment_status",
            sender_id=tracker.sender_id,
            input_data={"session_id": session_id},
            output_data={"status": status},
            status=status or "unknown",
        )

        if status == "paid":
            dispatcher.utter_message(text="Payment confirmed. Issuing your ticket now...")
            return [
                SlotSet("payment_status", "paid"),
                SlotSet("payment_confirmation_message", None),
                FollowupAction("issue_ticket"),
            ]

        if status == "not_found":
            dispatcher.utter_message(
                text="I couldn't find that payment session. Please restart your booking."
            )
            return [FollowupAction("utter_anything_else")]

        dispatcher.utter_message(
            text=(
                "I haven't received confirmation of your payment yet. "
                "Please complete checkout and let me know once you've paid."
            )
        )
        return [
            SlotSet("payment_status", "pending"),
            SlotSet("payment_confirmation_message", None),
        ]

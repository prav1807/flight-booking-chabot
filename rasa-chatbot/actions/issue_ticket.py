import random
import string
import uuid
from typing import Any, Dict, List, Text

from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.events import SlotSet, FollowupAction

from .middleware import AuditLogger

_audit_logger = AuditLogger()


def _generate_ticket_number() -> str:
    """
    Generates an airline-style e-ticket number: a 3-digit numeric airline
    prefix followed by a 10-digit document number (e.g. "176-1234567890").
    This is a deterministic placeholder for what an airline's ticketing
    system / Duffel Orders API would issue for a real order.
    """
    airline_prefix = "".join(random.choices(string.digits, k=3))
    document_number = "".join(random.choices(string.digits, k=10))
    return f"{airline_prefix}-{document_number}"


class IssueTicket(Action):
    """
    Ticketing Agent (deterministic) — issues an e-ticket only after payment
    has been confirmed. Never runs before `check_payment_status` confirms
    "paid", enforced by the flow order and by only ever being triggered as
    a FollowupAction from that action.
    """

    def name(self) -> Text:
        return "issue_ticket"

    def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict[Text, Any]]:

        if tracker.get_slot("payment_status") != "paid":
            dispatcher.utter_message(
                text="I can't issue a ticket until payment has been confirmed."
            )
            return [FollowupAction("utter_anything_else")]

        ticket_number = _generate_ticket_number()

        _audit_logger.log(
            agent="Ticketing Agent",
            action="issue_ticket",
            sender_id=tracker.sender_id,
            input_data={"payment_session_id": tracker.get_slot("payment_session_id")},
            output_data={"ticket_number": ticket_number},
            status="success",
        )

        passenger_email = tracker.get_slot("passenger_email")

        dispatcher.utter_message(
            text=(
                "🎫 Your e-ticket has been issued!\n\n"
                f"E-Ticket Number: {ticket_number}\n\n"
                f"Your itinerary and boarding information have been emailed to {passenger_email}."
            )
        )

        return [
            SlotSet("ticket_number", ticket_number),
            FollowupAction("save_booking_to_supabase"),
        ]

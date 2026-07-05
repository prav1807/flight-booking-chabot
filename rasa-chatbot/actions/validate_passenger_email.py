from typing import Any, Dict, List, Text
import re

from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.events import SlotSet


class ValidatePassengerEmail(Action):
    def name(self) -> Text:
        return "validate_passenger_email"

    def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict[Text, Any]]:

        email = tracker.get_slot("passenger_email")

        if not email:
            return []

        email = str(email).strip()

        pattern = r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$"

        if not re.match(pattern, email):
            dispatcher.utter_message(
                text="That email address does not look valid. Please enter a valid email, for example test@example.com."
            )
            return [SlotSet("passenger_email", None)]

        return [SlotSet("passenger_email", email)]
from typing import Any, Dict, List, Text
import re

from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.events import SlotSet


class ValidatePassengerPhone(Action):
    def name(self) -> Text:
        return "validate_passenger_phone"

    def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict[Text, Any]]:

        phone = tracker.get_slot("passenger_phone")

        if not phone:
            return []

        phone = str(phone).strip().replace(" ", "")

        pattern = r"^\+?[0-9]{7,15}$"

        if not re.match(pattern, phone):
            dispatcher.utter_message(
                text="That phone number does not look valid. Please enter it with country code, for example +23058096169."
            )
            return [SlotSet("passenger_phone", None)]

        if not phone.startswith("+"):
            phone = f"+{phone}"

        return [SlotSet("passenger_phone", phone)]
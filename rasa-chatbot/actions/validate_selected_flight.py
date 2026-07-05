from typing import Any, Dict, List, Text

from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.events import SlotSet


class ValidateSelectedFlight(Action):
    def name(self) -> Text:
        return "validate_selected_flight"

    def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict[Text, Any]]:

        selected_flight = tracker.get_slot("selected_flight")
        offer_map = tracker.get_slot("duffel_offer_map") or {}

        if selected_flight is None:
            return []
        if tracker.get_slot("selected_flight_confirmed") is True:
            return []

        selected_key = str(selected_flight).strip().lower()

        aliases = {
            "option 1": "1", "first": "1", "the first one": "1",
            "option 2": "2", "second": "2", "the second one": "2",
            "option 3": "3", "third": "3", "the third one": "3",
        }

        selected_key = aliases.get(selected_key, selected_key)
        selected_offer = offer_map.get(selected_key)

        if not selected_offer:
            dispatcher.utter_message(
                text="Sorry, I could not find that option. Please choose 1, 2, or 3."
            )
            return [SlotSet("selected_flight", None)]

        airline = selected_offer.get("airline")
        amount = selected_offer.get("amount")
        currency = selected_offer.get("currency")
        offer_id = selected_offer.get("offer_id")

        dispatcher.utter_message(
            text=f"Great choice. You selected {airline} for {amount} {currency}."
        )

        return [
            SlotSet("selected_flight", selected_key),
            SlotSet("selected_duffel_offer_id", offer_id),
            SlotSet("selected_flight_confirmed", True),
        ]
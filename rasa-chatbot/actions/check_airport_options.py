from typing import Any, Dict, List, Text

from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.events import SlotSet

from .airport_service import AirportService


class CheckAirportOptions(Action):
    def name(self) -> Text:
        return "check_airport_options"

    def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict[Text, Any]]:

        origin = tracker.get_slot("origin")
        destination = tracker.get_slot("destination")

        events = []

        origin_airports = AirportService.get_airports_for_city(origin)
        destination_airports = AirportService.get_airports_for_city(destination)

        if len(origin_airports) == 1:
            events.append(SlotSet("origin_airport", origin_airports[0]["code"]))
        elif len(origin_airports) > 1:
            dispatcher.utter_message(text=AirportService.format_airport_options(origin))
            events.append(SlotSet("origin_airport_options", origin_airports))

        if len(destination_airports) == 1:
            events.append(SlotSet("destination_airport", destination_airports[0]["code"]))
        elif len(destination_airports) > 1:
            dispatcher.utter_message(text=AirportService.format_airport_options(destination))
            events.append(SlotSet("destination_airport_options", destination_airports))

        return events
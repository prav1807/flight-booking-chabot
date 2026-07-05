from typing import Any, Dict, List, Text

from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.events import SlotSet

from .normalisation_service import NormalizationService


class NormalizeTripDetails(Action):
    def name(self) -> Text:
        return "normalize_trip_details"

    def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict[Text, Any]]:

        return [
            SlotSet("trip_type", NormalizationService.normalize_trip_type(tracker.get_slot("trip_type"))),
            SlotSet("departure_date", NormalizationService.normalize_date(tracker.get_slot("departure_date"))),
            SlotSet("return_date", NormalizationService.normalize_date(tracker.get_slot("return_date"))),
            SlotSet("passengers", NormalizationService.normalize_passengers(tracker.get_slot("passengers"))),
            SlotSet("travel_class", NormalizationService.normalize_cabin_class(tracker.get_slot("travel_class"))),
            SlotSet("origin", NormalizationService.normalize_airport(tracker.get_slot("origin"))),
            SlotSet("destination", NormalizationService.normalize_airport(tracker.get_slot("destination"))),
        ]
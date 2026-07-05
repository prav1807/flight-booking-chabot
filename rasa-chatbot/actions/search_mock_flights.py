from typing import Any, Dict, List, Text

from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher


class SearchMockFlights(Action):
    def name(self) -> Text:
        return "search_mock_flights"

    def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict[Text, Any]]:

        origin = tracker.get_slot("origin")
        destination = tracker.get_slot("destination")
        departure_date = tracker.get_slot("departure_date")
        travel_class = tracker.get_slot("travel_class")
        passengers = tracker.get_slot("passengers")

        message = (
            f"I found these available flights from {origin} to {destination}:\n\n"
            f"1. Emirates EK001\n"
            f"   Date: {departure_date}\n"
            f"   Time: 08:30 - 12:45\n"
            f"   Class: {travel_class}\n"
            f"   Passengers: {passengers}\n"
            f"   Price: AED 2,500\n\n"
            f"2. British Airways BA108\n"
            f"   Date: {departure_date}\n"
            f"   Time: 14:20 - 18:40\n"
            f"   Class: {travel_class}\n"
            f"   Passengers: {passengers}\n"
            f"   Price: AED 2,850\n\n"
            f"3. Qatar Airways QR102\n"
            f"   Date: {departure_date}\n"
            f"   Time: 22:00 - 06:10\n"
            f"   Class: {travel_class}\n"
            f"   Passengers: {passengers}\n"
            f"   Price: AED 3,100\n\n"
            "Please choose option 1, 2, or 3."
        )

        dispatcher.utter_message(text=message)

        return []
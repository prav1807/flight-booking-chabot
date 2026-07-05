from typing import Any, Dict, List, Text

from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher


class ShowTripSummary(Action):
    def name(self) -> Text:
        return "show_trip_summary"

    def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict[Text, Any]]:

        origin = tracker.get_slot("origin")
        destination = tracker.get_slot("destination")
        trip_type = tracker.get_slot("trip_type")
        departure_date = tracker.get_slot("departure_date")
        return_date = tracker.get_slot("return_date")
        passengers = tracker.get_slot("passengers")
        travel_class = tracker.get_slot("travel_class")

        message = (
            "Great, I have your flight search details:\n\n"
            f"From: {origin}\n"
            f"To: {destination}\n"
            f"Trip type: {trip_type}\n"
            f"Departure date: {departure_date}\n"
        )

        if trip_type and "return" in str(trip_type).lower():
            message += f"Return date: {return_date}\n"

        message += (
            f"Passengers: {passengers}\n"
            f"Travel class: {travel_class}\n\n"
            "Next, I’ll search available flights."
        )

        dispatcher.utter_message(text=message)

        return []
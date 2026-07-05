from typing import Any, Dict, List, Text

from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher


class ShowFinalBookingSummary(Action):
    def name(self) -> Text:
        return "show_final_booking_summary"

    def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict[Text, Any]]:

        selected_flight = tracker.get_slot("selected_flight")
        offer_map = tracker.get_slot("duffel_offer_map") or {}
        selected_offer = offer_map.get(str(selected_flight))

        passenger_name = tracker.get_slot("passenger_full_name")
        passenger_email = tracker.get_slot("passenger_email")
        passenger_phone = tracker.get_slot("passenger_phone")

        if not selected_offer:
            dispatcher.utter_message(
                text="I could not find the selected flight offer. Please search again."
            )
            return []

        message = (
            "Here is your booking summary:\n\n"
            f"Route: {tracker.get_slot('origin')} → {tracker.get_slot('destination')}\n"
            f"Trip type: {tracker.get_slot('trip_type')}\n"
            f"Departure date: {tracker.get_slot('departure_date')}\n\n"
            f"Flight: {selected_offer.get('airline')}\n"
            f"Departure: {selected_offer.get('departing_at')}\n"
            f"Arrival: {selected_offer.get('arriving_at')}\n"
            f"Price: {selected_offer.get('amount')} {selected_offer.get('currency')}\n\n"
            "Passenger details:\n"
            f"Name: {passenger_name}\n"
            f"Email: {passenger_email}\n"
            f"Phone: {passenger_phone}\n\n"
            "This booking is not confirmed yet."
        )

        dispatcher.utter_message(text=message)
        return []
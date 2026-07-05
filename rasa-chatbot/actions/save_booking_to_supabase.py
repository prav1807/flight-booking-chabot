from typing import Any, Dict, List, Text

from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.events import SlotSet, FollowupAction

from .supabase_client import SupabaseClient


class SaveBookingToSupabase(Action):
    def name(self) -> Text:
        return "save_booking_to_supabase"

    def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict[Text, Any]]:

        offer_map = tracker.get_slot("duffel_offer_map") or {}
        selected_flight = tracker.get_slot("selected_flight")
        selected_offer = offer_map.get(str(selected_flight), {})

        booking_data = {
            "origin": tracker.get_slot("origin"),
            "destination": tracker.get_slot("destination"),
            "trip_type": tracker.get_slot("trip_type"),
            "departure_date": tracker.get_slot("departure_date"),
            "return_date": tracker.get_slot("return_date"),
            "passengers": tracker.get_slot("passengers"),
            "travel_class": tracker.get_slot("travel_class"),
            "selected_duffel_offer_id": tracker.get_slot("selected_duffel_offer_id"),
            "airline": selected_offer.get("airline"),
            "price": selected_offer.get("amount"),
            "currency": selected_offer.get("currency"),
            "passenger_full_name": tracker.get_slot("passenger_full_name"),
            "passenger_email": tracker.get_slot("passenger_email"),
            "passenger_phone": tracker.get_slot("passenger_phone"),
            "booking_status": "confirmed_draft",
        }

        try:
            response = (
                SupabaseClient()
                .client
                .table("bookings")
                .insert(booking_data)
                .execute()
            )

            booking_id = response.data[0]["id"]

            dispatcher.utter_message(
                text=f"Your draft booking has been saved successfully. Booking reference: {booking_id}"
            )

            return [
                SlotSet("booking_confirmed", True),
                SlotSet("booking_reference", booking_id),
                FollowupAction("utter_anything_else"),
            ]

        except Exception as e:
            dispatcher.utter_message(
                text=f"The booking was confirmed, but I could not save it to Supabase. Error: {str(e)}"
            )
            return [
                FollowupAction("utter_anything_else"),
            ]
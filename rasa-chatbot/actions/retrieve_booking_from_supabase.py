from typing import Any, Dict, List, Text

from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.events import SlotSet

from .supabase_client import SupabaseClient


class RetrieveBookingFromSupabase(Action):
    def name(self) -> Text:
        return "retrieve_booking_from_supabase"

    def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict[Text, Any]]:

        booking_reference = tracker.get_slot("booking_reference_lookup")

        if not booking_reference:
            dispatcher.utter_message(text="Please enter a valid booking reference.")
            return []

        booking_reference = str(booking_reference).strip()

        try:
            response = (
                SupabaseClient()
                .client
                .table("bookings")
                .select("*")
                .eq("id", booking_reference)
                .execute()
            )

            if not response.data:
                dispatcher.utter_message(
                    text="Sorry, I could not find a booking with that reference."
                )
                return [SlotSet("booking_reference_lookup", None)]

            booking = response.data[0]

            dispatcher.utter_message(
                text=(
                    "Here are your booking details:\n\n"
                    f"Booking Reference: {booking.get('id')}\n"
                    f"Route: {booking.get('origin')} → {booking.get('destination')}\n"
                    f"Trip Type: {booking.get('trip_type')}\n"
                    f"Departure Date: {booking.get('departure_date')}\n"
                    f"Return Date: {booking.get('return_date')}\n"
                    f"Passengers: {booking.get('passengers')}\n"
                    f"Travel Class: {booking.get('travel_class')}\n"
                    f"Airline: {booking.get('airline')}\n"
                    f"Price: {booking.get('price')} {booking.get('currency')}\n"
                    f"Passenger: {booking.get('passenger_full_name')}\n"
                    f"Email: {booking.get('passenger_email')}\n"
                    f"Phone: {booking.get('passenger_phone')}\n"
                    f"Status: {booking.get('booking_status')}"
                )
            )

            return [SlotSet("booking_reference_lookup", None)]

        except Exception as e:
            dispatcher.utter_message(
                text=f"Sorry, I could not retrieve the booking right now. Error: {str(e)}"
            )
            return []
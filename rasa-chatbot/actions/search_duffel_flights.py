from typing import Any, Dict, List, Text

from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.events import SlotSet

from .duffel_client import DuffelClient
from .normalisation_service import NormalizationService


class SearchDuffelFlights(Action):
    def name(self) -> Text:
        return "search_duffel_flights"

    def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict[Text, Any]]:

        try:
            client = DuffelClient()

            trip_type = tracker.get_slot("trip_type")

            origin_value = tracker.get_slot("origin_airport") or tracker.get_slot("origin")
            destination_value = tracker.get_slot("destination_airport") or tracker.get_slot("destination")

            origin_code = NormalizationService.normalize_airport(origin_value)
            destination_code = NormalizationService.normalize_airport(destination_value)

            departure_date = NormalizationService.normalize_date(
                tracker.get_slot("departure_date")
            )

            return_date_value = NormalizationService.normalize_date(
                tracker.get_slot("return_date")
            )

            print("DEBUG ORIGIN:", origin_code)
            print("DEBUG DESTINATION:", destination_code)
            print("DEBUG DEPARTURE:", departure_date)
            print("DEBUG RETURN:", return_date_value)
            print("DEBUG PASSENGERS:", tracker.get_slot("passengers"))
            print("DEBUG CLASS:", tracker.get_slot("travel_class"))

            offers = client.create_offer_request(
                origin=origin_code,
                destination=destination_code,
                departure_date=departure_date,
                return_date=return_date_value
                if trip_type and "return" in str(trip_type).lower()
                else None,
                passengers_count=int(tracker.get_slot("passengers")),
                cabin_class=tracker.get_slot("travel_class"),
            )

            if not offers:
                dispatcher.utter_message(
                    text="I could not find available flights for this route and date."
                )
                return []

            offer_map = {}
            message = "I found these flight offers:\n\n"

            for index, offer in enumerate(offers[:3], start=1):
                offer_id = offer.get("id")
                airline = offer.get("owner", {}).get("name", "Unknown airline")
                total_amount = offer.get("total_amount")
                total_currency = offer.get("total_currency")

                slice_data = offer.get("slices", [{}])[0]
                segment = slice_data.get("segments", [{}])[0]

                departing_at = segment.get("departing_at", "Unknown departure time")
                arriving_at = segment.get("arriving_at", "Unknown arrival time")

                offer_map[str(index)] = {
                    "offer_id": offer_id,
                    "airline": airline,
                    "amount": total_amount,
                    "currency": total_currency,
                    "departing_at": departing_at,
                    "arriving_at": arriving_at,
                }

                message += (
                    f"{index}. {airline}\n"
                    f"   Departure: {departing_at}\n"
                    f"   Arrival: {arriving_at}\n"
                    f"   Price: {total_amount} {total_currency}\n\n"
                )

            message += "Please choose option 1, 2, or 3."

            dispatcher.utter_message(text=message)

            return [SlotSet("duffel_offer_map", offer_map)]

        except Exception as e:
            print("DUFFEL ERROR:", str(e))

            dispatcher.utter_message(
                text=(
                    "Sorry, I could not retrieve flight availability at the moment.\n\n"
                    "You can try again with different travel details, or complete your booking manually on the Emirates website:\n"
                    "https://www.emirates.com\n\n"
                    "If the issue continues, please contact an Emirates representative for assistance on the following number: +971000000000."
                )
            )

            return []
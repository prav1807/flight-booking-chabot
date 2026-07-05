from difflib import get_close_matches
from typing import Any, Dict, List, Text, Tuple

from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.events import SlotSet

from .airport_service import AirportService

try:
    from .crewai_agents.tools.airport_lookup import AIRPORT_DB, IATA_MAP
except ImportError:
    AIRPORT_DB = {}
    IATA_MAP = {}


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

        # Resolve origin
        origin_airports, origin_city = self._resolve(origin, dispatcher)
        if origin_airports is None:
            # Completely unresolvable — reset so the flow re-asks
            dispatcher.utter_message(
                text=(
                    f"❌ I couldn't find an airport for '{origin}'. "
                    "Please enter a city name like London, Dubai, or Mauritius."
                )
            )
            events.append(SlotSet("origin", None))
            events.append(SlotSet("origin_airport", None))
        elif len(origin_airports) == 1:
            events.append(SlotSet("origin_airport", origin_airports[0]["code"]))
        else:
            dispatcher.utter_message(text=AirportService.format_airport_options(origin_city))
            events.append(SlotSet("origin_airport_options", origin_airports))

        # Resolve destination
        destination_airports, destination_city = self._resolve(destination, dispatcher)
        if destination_airports is None:
            dispatcher.utter_message(
                text=(
                    f"❌ I couldn't find an airport for '{destination}'. "
                    "Please enter a city name like London, Dubai, or Mauritius."
                )
            )
            events.append(SlotSet("destination", None))
            events.append(SlotSet("destination_airport", None))
        elif len(destination_airports) == 1:
            events.append(SlotSet("destination_airport", destination_airports[0]["code"]))
        else:
            dispatcher.utter_message(text=AirportService.format_airport_options(destination_city))
            events.append(SlotSet("destination_airport_options", destination_airports))

        return events

    def _resolve(
        self, value: str, dispatcher: CollectingDispatcher
    ) -> Tuple[List[Dict] | None, str | None]:
        """
        Tries to resolve a city name or airport code to a list of airport dicts.

        Resolution order:
          1. Exact city name match in AirportService (e.g. "london")
          2. IATA code reverse-lookup (e.g. "LHR" → London Heathrow)
          3. Fuzzy city match across full AIRPORT_DB (handles typos like "mauritiuss")

        Returns:
          (airports, city_key) — airports is None if unresolvable.
        """
        if not value:
            return None, None

        key = str(value).lower().strip()

        # 1. Exact city name in AirportService
        airports = AirportService.get_airports_for_city(key)
        if airports:
            return airports, key

        # 2. IATA code reverse-lookup (normalise_trip_details may have converted already)
        iata = key.upper()
        if len(iata) == 3 and iata in IATA_MAP:
            entry = IATA_MAP[iata]
            # Try to find back in AirportService for multi-airport awareness
            city_airports = AirportService.get_airports_for_city(entry.get("city", ""))
            if city_airports:
                return city_airports, entry.get("city", iata)
            return [{"code": iata, "name": entry["name"]}], iata

        # 3. Fuzzy match across full AIRPORT_DB (catches typos)
        if AIRPORT_DB:
            matches = get_close_matches(key, AIRPORT_DB.keys(), n=1, cutoff=0.62)
            if matches:
                best = matches[0]
                entry = AIRPORT_DB[best]
                dispatcher.utter_message(
                    text=f"✅ I matched '{value}' to {best.title()} ({entry['code']})."
                )
                # Use AirportService for multi-airport cities if possible
                service_airports = AirportService.get_airports_for_city(best)
                if service_airports:
                    return service_airports, best
                return [{"code": entry["code"], "name": entry["name"]}], best

        return None, None

from datetime import datetime, timedelta
from dateutil import parser
import re
from difflib import get_close_matches

try:
    from .crewai_agents.tools.airport_lookup import AIRPORT_DB
except ImportError:
    AIRPORT_DB = {}


class NormalizationService:

    @staticmethod
    def normalize_trip_type(value):
        text = str(value or "").lower().strip()

        if any(word in text for word in ["return", "round", "round-trip"]):
            return "return"

        if any(word in text for word in ["one", "one-way", "single"]):
            return "one-way"

        return text

    @staticmethod
    def normalize_cabin_class(value):
        text = str(value or "").lower().strip()

        if "business" in text:
            return "business"
        if "premium" in text:
            return "premium_economy"
        if "first" in text:
            return "first"
        return "economy"

    @staticmethod
    def normalize_passengers(value):
        text = str(value or "").lower().strip()

        if text.isdigit():
            return text

        relationship_words = [
            "wife",
            "husband",
            "partner",
            "couple",
            "girlfriend",
            "boyfriend",
            "fiance",
            "fiancée",
            "spouse"
        ]

        if any(word in text for word in relationship_words):
            return "2"

        number_match = re.search(r"\d+", text)
        if number_match:
            return number_match.group()

        words = {
            "one": "1",
            "two": "2",
            "three": "3",
            "four": "4",
            "five": "5",
            "six": "6",
            "seven": "7",
            "eight": "8",
            "nine": "9",
        }

        for word, number in words.items():
            if word in text:
                return number

        return "1"

    @staticmethod
    def normalize_airport(value):
        mapping = {
            "dubai": "DXB",
            "london": "LHR",
            "heathrow": "LHR",
            "gatwick": "LGW",
            "mauritius": "MRU",
            "paris": "CDG",
            "new york": "JFK",
            "lhr": "LHR",
            "london heathrow": "LHR",
            "dubai airport": "DXB",
            "heathrow airport": "LHR",
            "dubai international airport": "DXB",
            "dubai international": "DXB",
            "dxb": "DXB",
            "london heathrow airport": "LHR",
        }

        text = str(value or "").lower().strip()

        # Exact match in legacy mapping
        if text in mapping:
            return mapping[text]

        # If it already looks like an IATA code, return it as-is
        if len(text) == 3 and text.isalpha():
            return text.upper()

        # Fuzzy match against the full airport DB (handles typos like "mauritiuss")
        if AIRPORT_DB:
            matches = get_close_matches(text, AIRPORT_DB.keys(), n=1, cutoff=0.75)
            if matches:
                return AIRPORT_DB[matches[0]]["code"]

        return str(value).upper()

    @staticmethod
    def normalize_date(value):
        text = str(value or "").lower().strip()

        if not text:
            return None

        today = datetime.today()

        if text == "tomorrow":
            return (today + timedelta(days=1)).strftime("%Y-%m-%d")

        if text.startswith("next "):
            weekdays = {
                "monday": 0,
                "tuesday": 1,
                "wednesday": 2,
                "thursday": 3,
                "friday": 4,
                "saturday": 5,
                "sunday": 6,
            }

            day_name = text.replace("next ", "").strip()
            if day_name in weekdays:
                days_ahead = weekdays[day_name] - today.weekday()
                if days_ahead <= 0:
                    days_ahead += 7
                return (today + timedelta(days=days_ahead)).strftime("%Y-%m-%d")

        try:
            cleaned = re.sub(r"(\d+)(st|nd|rd|th)", r"\1", text)
            parsed = parser.parse(cleaned, dayfirst=True)
            return parsed.strftime("%Y-%m-%d")
        except Exception:
            return value
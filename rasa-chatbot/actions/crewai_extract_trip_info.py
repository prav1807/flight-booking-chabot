import json
import re
from datetime import date
from typing import Any, Dict, List, Optional, Text

from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.events import SlotSet

from .normalisation_service import NormalizationService
from .crewai_agents.tools.date_interpreter import DateInterpreterTool
from .crewai_agents.tools.airport_lookup import AirportLookupTool

_date_tool = DateInterpreterTool()
_airport_tool = AirportLookupTool()

# Word → number mappings for passenger detection
_NUM_WORDS = {
    "one": "1", "two": "2", "three": "3", "four": "4", "five": "5",
    "six": "6", "seven": "7", "eight": "8", "nine": "9",
    "a": "1", "solo": "1", "couple": "2", "pair": "2",
}

# Patterns that indicate a date expression in text
_DATE_PATTERNS = re.compile(
    r"\b("
    r"tomorrow|today"
    r"|next\s+\w+"
    r"|in\s+\d+\s+(?:day|days|week|weeks|month|months)"
    r"|end\s+of\s+(?:next\s+)?\w+"
    r"|(?:start|beginning)\s+of\s+\w+"
    r"|christmas|chrismas|xmas|new\s+year\w*|halloween|valentines?"
    r"|(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may"
    r"|jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:t(?:ember)?)?|oct(?:ober)?"
    r"|nov(?:ember)?|dec(?:ember)?)\w*\s+\d{1,2}(?:st|nd|rd|th)?"
    r"|\d{1,2}(?:st|nd|rd|th)?\s+(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may"
    r"|jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:t(?:ember)?)?|oct(?:ober)?"
    r"|nov(?:ember)?|dec(?:ember)?)\w*"
    r"|\d{4}-\d{2}-\d{2}"
    r"|\d{1,2}[/-]\d{1,2}[/-]\d{2,4}"
    r")\b",
    re.IGNORECASE,
)

# City / country words that should NOT be treated as destinations
_NON_CITY_WORDS = {
    "somewhere", "anywhere", "abroad", "holiday", "vacation", "trip",
    "flight", "book", "travel", "one", "way", "return",
}


def _rule_extract(text: str) -> Dict[str, Optional[str]]:
    """
    Fast, pure-Python extraction — no LLM / Ollama needed.
    Handles the most common natural language booking patterns.
    """
    t = text.lower().strip()
    today = date.today().isoformat()
    result: Dict[str, Optional[str]] = {}

    # ── Origin / Destination from "from X to Y" patterns ─────────────────────────
    # "from Dubai to London", "flying from Paris to New York"
    route_match = re.search(
        r"\bfrom\s+([\w\s]+?)\s+to\s+([\w\s]+?)(?=\s+(?:on|for|in|next|this|tomorrow|one|return|round|\d)|$)",
        t
    )
    if route_match:
        origin_text = route_match.group(1).strip()
        dest_text = route_match.group(2).strip()
        # Only accept if they look like real place names (not generic words)
        if origin_text and origin_text not in _NON_CITY_WORDS and len(origin_text) > 1:
            try:
                r = json.loads(_airport_tool._run(json.dumps({"query": origin_text})))
                if r.get("found"):
                    result["origin"] = r["code"]
            except Exception:
                pass
        if dest_text and dest_text not in _NON_CITY_WORDS and len(dest_text) > 1:
            try:
                r = json.loads(_airport_tool._run(json.dumps({"query": dest_text})))
                if r.get("found"):
                    result["destination"] = r["code"]
            except Exception:
                pass

    # "fly to London" / "going to Paris" / "fly me to New York" (without explicit origin)
    if not result.get("destination"):
        to_match = re.search(
            r"\b(?:fly(?:ing)?|travel(?:ling)?|going|head(?:ing)?|book)\s+(?:me|us|there|back\s+)?\s*to\s+([\w\s]+?)(?=\s+(?:on|for|in|next|this|from)|\s*$)",
            t
        )
        if to_match:
            dest_text = to_match.group(1).strip()
            if dest_text and dest_text not in _NON_CITY_WORDS:
                try:
                    r = json.loads(_airport_tool._run(json.dumps({"query": dest_text})))
                    if r.get("found"):
                        result["destination"] = r["code"]
                except Exception:
                    pass

    # "2 people", "for 3 passengers", "three travellers"
    m = re.search(
        r"\b(\d+|one|two|three|four|five|six|seven|eight|nine)\s*"
        r"(?:people|persons?|passengers?|adults?|tickets?|seats?|travell?ers?)\b", t
    )
    if m:
        v = m.group(1)
        result["passengers"] = _NUM_WORDS.get(v, NormalizationService.normalize_passengers(v))

    if not result.get("passengers"):
        # "for 2", "for 3 people"
        m = re.search(r"\bfor\s+(\d+)\b", t)
        if m:
            result["passengers"] = m.group(1)

    if not result.get("passengers"):
        if re.search(
            r"\b(?:wife|husband|partner|girlfriend|boyfriend|friend|colleague|spouse)"
            r"\s+and\s+(?:me|i|myself)\b", t
        ) or re.search(r"\bme\s+and\s+my\b", t) or re.search(r"\bmyself\s+and\s+my\b", t):
            result["passengers"] = "2"
        elif re.search(r"\bjust\s+(?:me|myself|one)\b", t) or re.search(r"\balone\b", t):
            result["passengers"] = "1"
        elif re.search(r"\bfor\s+myself\b|\bmyself\b|\bsolo\b", t):
            result["passengers"] = "1"

    # ── Travel class ─────────────────────────────────────────────────────────────
    if re.search(r"\bfirst[\s-]?class\b", t):
        result["travel_class"] = "first"
    elif re.search(r"\bbusiness[\s-]?class\b|\bbusiness\b", t):
        result["travel_class"] = "business"
    elif re.search(r"\bpremium[\s-]?economy\b|\bpremium\b", t):
        result["travel_class"] = "premium_economy"
    elif re.search(r"\beconomy\b|\bcoach\b|\bstandard\b", t):
        result["travel_class"] = "economy"

    # ── Trip type ────────────────────────────────────────────────────────────────
    if re.search(r"\bone[\s-]?way\b|\bsingle\b(?!\s+passenger)", t):
        result["trip_type"] = "one-way"
    elif re.search(r"\breturn\b|\bround[\s-]?trip\b|\bboth\s+ways\b", t):
        result["trip_type"] = "return"

    # ── Departure date ───────────────────────────────────────────────────────────
    # Find "on [date]" pattern first, then fall back to any date expression
    on_match = re.search(r"\bon\s+([\w\s]+?)(?=\s+for|\s+in\s+(?:economy|business|first|premium)|\s*$)", t)
    candidates = []
    if on_match:
        candidates.append(on_match.group(1).strip())

    # Add all regex-detected date expressions
    for m in _DATE_PATTERNS.finditer(t):
        c = m.group(1).strip()
        if c not in candidates:
            candidates.append(c)

    for candidate in candidates:
        try:
            r = json.loads(_date_tool._run(json.dumps({"date_text": candidate, "today": today})))
            if r.get("resolved") and r.get("iso_date"):
                result["departure_date"] = r["iso_date"]
                break
        except Exception:
            pass

    return result


def _llm_extract(message: str) -> Dict[str, Optional[str]]:
    """
    Uses the CrewAI Booking Extractor agent to extract info from natural language.
    Requires Ollama. Exceptions bubble up to be caught by the caller.
    """
    from .crewai_agents.crews import run_extraction_crew
    return run_extraction_crew(message)


class CrewAIExtractTripInfo(Action):
    """
    Runs at the START of the booking flow.

    Reads the user's initial message and extracts ALL available booking
    information at once — no need to ask for things already mentioned.

    Example:
      "Book a one-way flight from Mauritius to London on Christmas for 2 in business"
      → Sets 6 slots immediately; flow only asks for what's still missing.

    Uses rule-based extraction first (always works, no Ollama).
    Enhances with CrewAI LLM agent when Ollama is available.
    """

    def name(self) -> Text:
        return "crewai_extract_trip_info"

    def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict[Text, Any]]:

        # Gather last few user messages for context
        user_messages = [
            e["text"] for e in tracker.events
            if e.get("event") == "user" and e.get("text", "").strip()
        ][-3:]
        full_context = " ".join(user_messages).strip()

        if not full_context:
            return []

        # Step 1: Rule-based extraction (always works)
        extracted = _rule_extract(full_context)

        # Step 2: CrewAI LLM fills gaps (optional, requires Ollama)
        try:
            llm_result = _llm_extract(full_context)
            for k, v in llm_result.items():
                if v and not extracted.get(k):
                    extracted[k] = v
        except Exception:
            pass  # Rule-based is sufficient for most common requests

        if not any(extracted.values()):
            return []

        events: List[Dict[Text, Any]] = []
        found: List[str] = []
        missing: List[str] = []

        field_labels = {
            "origin": "From",
            "destination": "To",
            "trip_type": "Trip type",
            "departure_date": "Departure",
            "return_date": "Return",
            "passengers": "Passengers",
            "travel_class": "Class",
        }
        ask_labels = {
            "origin": "origin city",
            "destination": "destination city",
            "trip_type": "trip type (one-way or return)",
            "departure_date": "departure date",
            "return_date": "return date",
            "passengers": "number of passengers",
            "travel_class": "travel class (economy / business / first)",
        }

        for field in ["origin", "destination", "trip_type", "departure_date",
                      "return_date", "passengers", "travel_class"]:
            value = extracted.get(field)
            if value:
                # Normalise before setting
                if field in ("origin", "destination"):
                    value = NormalizationService.normalize_airport(value)
                elif field == "travel_class":
                    value = NormalizationService.normalize_cabin_class(value)
                elif field == "trip_type":
                    value = NormalizationService.normalize_trip_type(value)
                elif field == "passengers":
                    value = NormalizationService.normalize_passengers(value)

                events.append(SlotSet(field, value))
                found.append(f"• {field_labels[field]}: {value}")
            else:
                # Only report as missing if it's a required field
                # (return_date is only required for return trips)
                if field == "return_date":
                    trip_type = extracted.get("trip_type") or tracker.get_slot("trip_type") or ""
                    if "return" not in str(trip_type).lower():
                        continue
                missing.append(ask_labels[field])

        if found:
            msg = "✅ Got it! Here's what I picked up:\n" + "\n".join(found)
            if missing:
                msg += f"\n\nI still need: **{', '.join(missing)}**."
            else:
                msg += "\n\nI have everything — let me run the search!"
            dispatcher.utter_message(text=msg)

        return events

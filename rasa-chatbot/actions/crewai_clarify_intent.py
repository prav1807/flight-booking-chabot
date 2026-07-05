import json
import re
from datetime import date
from typing import Any, Dict, List, Optional, Text

from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.events import SlotSet

from .crewai_agents.tools.date_interpreter import DateInterpreterTool
from .crewai_agents.tools.destination_suggestion import DestinationSuggestionTool
from .crewai_agents.ollama_health import is_ollama_running

# Singletons — instantiate once at import time
_date_tool = DateInterpreterTool()
_dest_tool = DestinationSuggestionTool()

_ISO_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

_VAGUE_DESTINATION_KEYWORDS = [
    "warm", "hot", "sunny", "cold", "cheap", "budget", "luxury", "beach",
    "city", "somewhere", "anywhere", "abroad", "holiday", "vacation",
    "romantic", "adventure", "family", "europe", "asia", "africa",
    "caribbean", "island", "mountain", "ski", "resort",
]


def _is_unresolved_date(value) -> bool:
    """Returns True if the value is not already an ISO-formatted date."""
    if not value:
        return False
    return not _ISO_DATE_RE.match(str(value).strip())


def _is_vague_destination(value) -> bool:
    """Returns True if the value looks like travel criteria rather than a real place."""
    if not value:
        return False
    v = str(value).lower().strip()
    if re.match(r"^[a-z]{3}$", v):  # already an IATA code
        return False
    return any(kw in v for kw in _VAGUE_DESTINATION_KEYWORDS)


class CrewAIClarifyIntent(Action):
    """
    Phase 2 — Intent Clarifier.

    Calls DateInterpreterTool and DestinationSuggestionTool DIRECTLY — no LLM needed.
    Works even when Ollama is offline. Fast and reliable for common cases.

    Handles:
      - Natural language dates: "Christmas", "chrismas" (typo), "end of July",
        "in 3 weeks", "next Friday" → ISO date
      - Vague destinations: "somewhere warm", "cheap city break" → concrete suggestions
    """

    def name(self) -> Text:
        return "crewai_clarify_intent"

    def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict[Text, Any]]:

        today = date.today().isoformat()
        events: List[Dict[Text, Any]] = []

        departure_date = tracker.get_slot("departure_date")
        return_date = tracker.get_slot("return_date")
        destination = tracker.get_slot("destination")

        # ── Resolve departure date ───────────────────────────────────────────────
        if _is_unresolved_date(departure_date):
            resolved = self._resolve_date(departure_date, today)
            if resolved:
                dispatcher.utter_message(
                    text=f"📅 I understood '{departure_date}' as {resolved['explanation']} ({resolved['iso_date']})."
                )
                events.append(SlotSet("departure_date", resolved["iso_date"]))
            else:
                dispatcher.utter_message(
                    text=(
                        f"🗓️ I couldn't interpret '{departure_date}' as a date. "
                        "Please enter a specific date — for example: 25 December 2026 or 2026-12-25."
                    )
                )
                events.append(SlotSet("departure_date", None))

        # ── Resolve return date ──────────────────────────────────────────────────
        if return_date and _is_unresolved_date(return_date):
            resolved = self._resolve_date(return_date, today)
            if resolved:
                dispatcher.utter_message(
                    text=f"📅 I understood '{return_date}' as {resolved['explanation']} ({resolved['iso_date']})."
                )
                events.append(SlotSet("return_date", resolved["iso_date"]))
            else:
                dispatcher.utter_message(
                    text=(
                        f"🗓️ I couldn't interpret '{return_date}' as a return date. "
                        "Please enter a specific date."
                    )
                )
                events.append(SlotSet("return_date", None))

        # ── Resolve vague destination ────────────────────────────────────────────
        if _is_vague_destination(destination):
            try:
                result = json.loads(_dest_tool._run(json.dumps({"criteria": str(destination)})))
                if result.get("found"):
                    dispatcher.utter_message(text=f"🌍 {result['message']}")
                else:
                    dispatcher.utter_message(
                        text=f"I'm not sure where '{destination}' is. Please name a specific city or country."
                    )
            except Exception:
                dispatcher.utter_message(
                    text=f"I'm not sure where '{destination}' is. Please name a specific city or country."
                )
            events.append(SlotSet("destination", None))
            events.append(SlotSet("destination_airport", None))

        return events

    def _resolve_date(self, text: str, today: str) -> Optional[Dict[str, str]]:
        """
        1. Tries rule-based DateInterpreterTool (no Ollama needed).
        2. If that fails AND Ollama is running, asks the LLM crew to interpret the date.
        Returns {"iso_date": "YYYY-MM-DD", "explanation": "..."} or None.
        """
        # Step 1: Rule-based (fast, no network)
        try:
            raw = _date_tool._run(json.dumps({"date_text": str(text), "today": today}))
            result = json.loads(raw)
            if result.get("resolved") and result.get("iso_date"):
                return result
        except Exception:
            pass

        # Step 2: LLM fallback via Ollama (smarter, handles complex expressions)
        if is_ollama_running():
            try:
                from .crewai_agents.crews import run_clarification_crew
                llm_result = run_clarification_crew({
                    "departure_date": text,
                    "return_date": None,
                    "destination": None,
                }, today)
                iso = (llm_result.get("resolved") or {}).get("departure_date")
                if iso and re.match(r"^\d{4}-\d{2}-\d{2}$", str(iso)):
                    return {"iso_date": iso, "explanation": f"interpreted by AI as {iso}"}
            except Exception:
                pass

        return None


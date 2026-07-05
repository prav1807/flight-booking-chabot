"""
Phase 3 — Booking Reviewer Rasa Action

Reviews the complete booking details before the user confirms payment.
Calls BookingReviewTool DIRECTLY — no Ollama/LLM required.
Optionally calls LLM crew for richer commentary if Ollama is running.

Shows:
  - A natural language booking summary
  - Any flags / warnings about the booking
  - Confidence level
"""
import json
from typing import Any, Dict, List, Text

from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.events import SlotSet

from .crewai_agents.tools.booking_review import BookingReviewTool

_review_tool = BookingReviewTool()


class CrewAIReviewBooking(Action):
    """
    Phase 3 — Booking Reviewer.

    Called just before show_final_booking_summary to cross-validate all fields
    and present the user with a friendly plain-language booking overview.
    """

    def name(self) -> Text:
        return "crewai_review_booking"

    def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict[Text, Any]]:

        booking = {
            "origin": tracker.get_slot("origin_airport") or tracker.get_slot("origin"),
            "destination": tracker.get_slot("destination_airport") or tracker.get_slot("destination"),
            "trip_type": tracker.get_slot("trip_type"),
            "departure_date": tracker.get_slot("departure_date"),
            "return_date": tracker.get_slot("return_date"),
            "passengers": tracker.get_slot("passengers"),
            "travel_class": tracker.get_slot("travel_class"),
        }

        try:
            result = json.loads(_review_tool._run(json.dumps(booking)))
        except Exception:
            return []

        confidence = result.get("confidence", "high")
        flags = result.get("flags") or []
        summary = result.get("summary", "")

        # ── Confidence icon ───────────────────────────────────────────────────────
        icon = {"high": "✅", "medium": "⚠️", "low": "❌"}.get(confidence, "✅")

        # ── Booking summary ───────────────────────────────────────────────────────
        msg = f"📋 **Booking Review** {icon}\n\n"
        if summary:
            msg += f"**{summary}**\n\n"

        # ── Flags ─────────────────────────────────────────────────────────────────
        if flags:
            msg += "**Notes:**\n"
            for flag in flags:
                msg += f"{flag}\n"
            msg += "\n"

        if confidence == "high":
            msg += "Everything looks good! Here is your final booking summary:"
        elif confidence == "medium":
            msg += "Please review the notes above before confirming."
        else:
            msg += "There may be issues with your booking. Please review carefully before confirming."

        dispatcher.utter_message(text=msg)

        return []

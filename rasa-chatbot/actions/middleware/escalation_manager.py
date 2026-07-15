"""
Escalation Manager — decides when a conversation should be handed off to
a human agent instead of continuing with automation.

Rasa's tracker already gives us signals for free (slot reset counts,
repeated same-intent messages), but the clearest, most reliable signal
for this project is a per-session failure counter maintained in a slot
(`validation_failure_count`), incremented by `crewai_validate_inputs`
each time a validation attempt fails and reset to 0 on success.
"""

from typing import Any, Dict

DEFAULT_MAX_FAILURES = 3


class EscalationManager:
    """Stateless decision helper — the actual counter lives in a Rasa slot."""

    def __init__(self, max_failures: int = DEFAULT_MAX_FAILURES) -> None:
        self.max_failures = max_failures

    def should_escalate(self, failure_count: int) -> bool:
        try:
            return int(failure_count or 0) >= self.max_failures
        except (TypeError, ValueError):
            return False

    def escalation_message(self, reason: str = "repeated_validation_failures") -> str:
        messages = {
            "repeated_validation_failures": (
                "It looks like we're having trouble getting these details right. "
                "Let me connect you with a travel specialist who can help you complete this booking."
            ),
            "unsupported_request": (
                "This request needs a bit more attention than I can give it. "
                "I'm connecting you with a human travel specialist now."
            ),
            "low_confidence": (
                "I want to make sure this is handled correctly, so I'm bringing in "
                "a travel specialist to assist you further."
            ),
        }
        return messages.get(reason, messages["repeated_validation_failures"])

    def build_escalation_payload(self, tracker, reason: str = "repeated_validation_failures") -> Dict[str, Any]:
        """Bundles context a human agent would need to pick up the conversation."""
        return {
            "sender_id": tracker.sender_id,
            "reason": reason,
            "slots": {
                key: tracker.get_slot(key)
                for key in (
                    "origin",
                    "destination",
                    "trip_type",
                    "departure_date",
                    "return_date",
                    "passengers",
                    "travel_class",
                )
            },
            "latest_message": tracker.latest_message.get("text"),
        }

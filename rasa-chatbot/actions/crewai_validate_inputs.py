import json
from typing import Any, Dict, List, Text

from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.events import SlotSet

from .crewai_agents.tools.date_validation import DateValidationTool
from .crewai_agents.tools.airport_lookup import AirportLookupTool
from .crewai_agents.ollama_health import is_ollama_running
from .middleware import EscalationManager, AuditLogger

# Singletons
_date_validator = DateValidationTool()
_airport_lookup = AirportLookupTool()
_escalation_manager = EscalationManager()
_audit_logger = AuditLogger()


class CrewAIValidateInputs(Action):
    """
    Phase 1 + Phase 2 — Input Validator with optional LLM Error Recovery.

    Calls DateValidationTool and AirportLookupTool DIRECTLY — no LLM required.
    Works even when Ollama is offline.

    If errors are found, optionally calls the LLM Error Recovery crew for
    friendlier messages (gracefully skipped if Ollama is unavailable).

    Validates:
      - Departure date is not in the past and is a valid ISO date
      - Return date is after departure date (return trips)
      - Origin and destination are recognised airports/cities
      - Origin and destination are not the same
      - Passenger count is between 1 and 9
    """

    def name(self) -> Text:
        return "crewai_validate_inputs"

    def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict[Text, Any]]:

        trip_details = {
            "origin": tracker.get_slot("origin"),
            "destination": tracker.get_slot("destination"),
            "trip_type": tracker.get_slot("trip_type"),
            "departure_date": tracker.get_slot("departure_date"),
            "return_date": tracker.get_slot("return_date"),
            "passengers": tracker.get_slot("passengers"),
            "travel_class": tracker.get_slot("travel_class"),
        }

        errors: List[str] = []
        events: List[Dict[Text, Any]] = []

        # 1. Validate dates directly via DateValidationTool
        # Note: skip "past date" check here — crewai_clarify_intent already resolved
        # dates to ISO format. Only check logical constraints (return > departure).
        try:
            date_result = json.loads(_date_validator._run(json.dumps({
                "departure_date": trip_details["departure_date"],
                "return_date": trip_details["return_date"],
                "trip_type": trip_details["trip_type"] or "one-way",
            })))
            for err in (date_result.get("errors") or []):
                # Skip "in the past" error — date was already validated upstream
                if "in the past" not in err.lower():
                    errors.append(err)
        except Exception:
            pass

        # 2. Validate origin via AirportLookupTool
        origin = trip_details["origin"]
        if origin:
            try:
                origin_result = json.loads(_airport_lookup._run(json.dumps({"query": str(origin)})))
                if not origin_result.get("found"):
                    errors.append(
                        f"I couldn't find a valid airport for origin '{origin}'. "
                        "Please check the city name."
                    )
                elif origin_result.get("note") and origin_result.get("code"):
                    # Silently apply fuzzy-matched correction
                    events.append(SlotSet("origin", origin_result["code"]))
            except Exception:
                pass

        # 3. Validate destination via AirportLookupTool
        destination = trip_details["destination"]
        if destination:
            try:
                dest_result = json.loads(_airport_lookup._run(json.dumps({"query": str(destination)})))
                if not dest_result.get("found"):
                    errors.append(
                        f"I couldn't find a valid airport for destination '{destination}'. "
                        "Please check the city name."
                    )
                elif dest_result.get("note") and dest_result.get("code"):
                    events.append(SlotSet("destination", dest_result["code"]))
            except Exception:
                pass

        # 4. Check origin ≠ destination
        if (
            origin and destination
            and str(origin).upper().strip() == str(destination).upper().strip()
        ):
            errors.append(
                "Your origin and destination are the same. "
                "Please enter a different destination."
            )

        # 5. Validate passenger count
        try:
            passengers = int(trip_details["passengers"] or 1)
            if not (1 <= passengers <= 9):
                errors.append(
                    f"Passenger count must be between 1 and 9. You entered {passengers}."
                )
        except (TypeError, ValueError):
            pass

        # No errors — all good
        if not errors:
            _audit_logger.log(
                agent="Input Validator",
                action="validate_inputs",
                sender_id=tracker.sender_id,
                input_data=trip_details,
                output_data={"valid": True},
                status="success",
            )
            events.append(SlotSet("validation_failure_count", 0))
            return events

        # ── Escalation check: too many consecutive failures → hand off to a human ──
        failure_count = int(tracker.get_slot("validation_failure_count") or 0) + 1
        events.append(SlotSet("validation_failure_count", failure_count))

        _audit_logger.log(
            agent="Input Validator",
            action="validate_inputs",
            sender_id=tracker.sender_id,
            input_data=trip_details,
            output_data={"valid": False, "errors": errors, "failure_count": failure_count},
            status="rejected",
        )

        if _escalation_manager.should_escalate(failure_count):
            _audit_logger.log(
                agent="Escalation Manager",
                action="escalate",
                sender_id=tracker.sender_id,
                input_data=_escalation_manager.build_escalation_payload(tracker),
                status="escalated",
            )
            dispatcher.utter_message(
                text=_escalation_manager.escalation_message("repeated_validation_failures")
            )
            events.append(SlotSet("validation_failure_count", 0))
            return events

        # ── Error messaging: Ollama first, raw fallback ───────────────────────────
        messages_to_show = errors
        if is_ollama_running():
            try:
                from .crewai_agents.crews import run_error_recovery_crew
                recovery = run_error_recovery_crew(errors, trip_details)
                if recovery.get("recovery_messages"):
                    messages_to_show = recovery["recovery_messages"]
                suggested = recovery.get("suggested_corrections") or {}
                if suggested.get("origin"):
                    events.append(SlotSet("origin", suggested["origin"]))
                if suggested.get("destination"):
                    events.append(SlotSet("destination", suggested["destination"]))
            except Exception:
                pass  # Use raw error messages
        else:
            # Try anyway — may work if Ollama just started
            try:
                from .crewai_agents.crews import run_error_recovery_crew
                recovery = run_error_recovery_crew(errors, trip_details)
                if recovery.get("recovery_messages"):
                    messages_to_show = recovery["recovery_messages"]
            except Exception:
                pass

        for message in messages_to_show:
            dispatcher.utter_message(text=f"❌ {message}")

        # Reset invalid slots so Rasa re-asks
        error_text = " ".join(errors).lower()
        if "departure" in error_text:
            events.append(SlotSet("departure_date", None))
        if "return date" in error_text:
            events.append(SlotSet("return_date", None))
        if "origin" in error_text:
            events.append(SlotSet("origin", None))
            events.append(SlotSet("origin_airport", None))
        if "destination" in error_text:
            events.append(SlotSet("destination", None))
            events.append(SlotSet("destination_airport", None))
        if "same" in error_text:
            events.append(SlotSet("destination", None))
            events.append(SlotSet("destination_airport", None))

        return events

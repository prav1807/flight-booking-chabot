import json
import re

from crewai import Crew, Process

from .agents import create_input_validator_agent, create_intent_clarifier_agent, create_error_recovery_agent, create_booking_extractor_agent, create_booking_reviewer_agent, create_change_booking_agent
from .tasks import create_validation_task, create_clarification_task, create_error_recovery_task, create_extraction_task, create_booking_review_task, create_change_booking_task


def run_input_validation_crew(trip_details: dict) -> dict:
    """
    Runs the Input Validation Crew on the provided trip details.

    Returns a dict with:
      - valid (bool): whether all inputs passed validation
      - errors (list[str]): blocking error messages to show the user
      - corrections (dict): suggested slot corrections (e.g. fuzzy-matched IATA codes)
      - warnings (list[str]): non-blocking notices
    """
    agent = create_input_validator_agent()
    task = create_validation_task(agent, trip_details)

    crew = Crew(
        agents=[agent],
        tasks=[task],
        process=Process.sequential,
        verbose=False,
    )

    try:
        result = crew.kickoff()
        raw = str(result)
    except Exception:
        raw = ""

    # Extract the JSON block from the agent's response
    json_match = re.search(r'\{.*\}', raw, re.DOTALL)
    if json_match:
        try:
            return json.loads(json_match.group())
        except json.JSONDecodeError:
            pass

    # Fallback: return safe default so booking is not blocked on parse failure
    return {
        "valid": True,
        "errors": [],
        "corrections": {},
        "warnings": [f"Validation response could not be parsed. Proceeding with standard checks."],
    }


def run_clarification_crew(trip_details: dict) -> dict:
    """
    Phase 2 — Runs the Intent Clarification Crew.

    Resolves ambiguous slot values (natural language dates, vague destinations, typos).

    Returns a dict with:
      - clarifications_needed (bool)
      - resolved (dict): field → corrected value (or None if unchanged)
      - unresolvable (list[str]): field names that couldn't be resolved
      - messages (list[str]): user-facing messages for unresolvable fields
    """
    agent = create_intent_clarifier_agent()
    task = create_clarification_task(agent, trip_details)

    crew = Crew(
        agents=[agent],
        tasks=[task],
        process=Process.sequential,
        verbose=False,
    )

    try:
        result = crew.kickoff()
        raw = str(result)
    except Exception:
        raw = ""

    json_match = re.search(r'\{.*\}', raw, re.DOTALL)
    if json_match:
        try:
            return json.loads(json_match.group())
        except json.JSONDecodeError:
            pass

    return {
        "clarifications_needed": False,
        "resolved": {},
        "unresolvable": [],
        "messages": [],
    }


def run_error_recovery_crew(errors: list, trip_details: dict) -> dict:
    """
    Phase 2 — Runs the Error Recovery Crew when the Input Validator finds errors.

    Converts raw validation error strings into friendly, actionable correction messages.

    Returns a dict with:
      - recovery_messages (list[str]): friendly messages to show the user
      - suggested_corrections (dict): field → suggested corrected value
    """
    agent = create_error_recovery_agent()
    task = create_error_recovery_task(agent, errors, trip_details)

    crew = Crew(
        agents=[agent],
        tasks=[task],
        process=Process.sequential,
        verbose=False,
    )

    try:
        result = crew.kickoff()
        raw = str(result)
    except Exception:
        raw = ""

    json_match = re.search(r'\{.*\}', raw, re.DOTALL)
    if json_match:
        try:
            return json.loads(json_match.group())
        except json.JSONDecodeError:
            pass

    # Fallback: return original error messages unchanged
    return {
        "recovery_messages": errors,
        "suggested_corrections": {},
    }


def run_extraction_crew(message: str) -> dict:
    """
    Phase 3 — Runs the Booking Info Extractor Crew on a free-form user message.

    Extracts all available booking fields at once from natural language.
    Returns a dict with the same 7 keys as booking slots (all may be None).
    Requires Ollama to be running.
    """
    agent = create_booking_extractor_agent()
    task = create_extraction_task(agent, message)

    crew = Crew(
        agents=[agent],
        tasks=[task],
        process=Process.sequential,
        verbose=False,
    )

    try:
        result = crew.kickoff()
        raw = str(result)
    except Exception:
        raw = ""

    json_match = re.search(r'\{.*\}', raw, re.DOTALL)
    if json_match:
        try:
            return json.loads(json_match.group())
        except json.JSONDecodeError:
            pass

    return {}


def run_booking_review_crew(booking: dict) -> dict:
    """
    Phase 3 — Runs the Booking Reviewer Crew on a complete booking dict.

    Performs cross-field review: date sanity, unusual class/pax combos,
    same-region routes, and generates a natural language summary.

    Returns a dict with: confidence, flags, summary, message.
    Requires Ollama to be running (LLM crew). Falls back gracefully.
    """
    agent = create_booking_reviewer_agent()
    task = create_booking_review_task(agent, booking)

    crew = Crew(
        agents=[agent],
        tasks=[task],
        process=Process.sequential,
        verbose=False,
    )

    try:
        result = crew.kickoff()
        raw = str(result)
    except Exception:
        raw = ""

    json_match = re.search(r'\{.*\}', raw, re.DOTALL)
    if json_match:
        try:
            return json.loads(json_match.group())
        except json.JSONDecodeError:
            pass

    return {}


def run_change_booking_crew(change_context: dict, fee_result: dict) -> dict:
    """
    Phase 4 — Runs the Change Booking Crew to explain an already-priced,
    already-approved date change in natural language.

    Returns a dict with: message (str).
    Falls back to a plain, deterministic message if the LLM is unavailable
    or its response can't be parsed — the customer must never be blocked
    from seeing the fee just because the LLM explanation failed.
    """
    agent = create_change_booking_agent()
    task = create_change_booking_task(agent, change_context, fee_result)

    crew = Crew(
        agents=[agent],
        tasks=[task],
        process=Process.sequential,
        verbose=False,
    )

    try:
        result = crew.kickoff()
        raw = str(result)
    except Exception:
        raw = ""

    json_match = re.search(r'\{.*\}', raw, re.DOTALL)
    if json_match:
        try:
            parsed = json.loads(json_match.group())
            if parsed.get("message"):
                return parsed
        except json.JSONDecodeError:
            pass

    # Deterministic fallback message — never blocks the flow.
    fare_diff = fee_result.get("fare_difference", 0)
    fare_diff_line = (
        f" plus a {fare_diff} {fee_result.get('currency', '')} fare difference" if fare_diff else ""
    )
    return {
        "message": (
            f"Changing your departure date from {change_context.get('old_departure_date')} to "
            f"{change_context.get('new_departure_date')} costs a {fee_result.get('flat_fee')} "
            f"{fee_result.get('currency', '')} change fee{fare_diff_line}, "
            f"for a total of {fee_result.get('total_change_cost')} {fee_result.get('currency', '')}. "
            "Would you like to proceed? (yes proceed / no cancel)"
        )
    }

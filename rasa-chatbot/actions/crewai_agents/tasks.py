import json
from datetime import date

from crewai import Task

from .agents import create_input_validator_agent


def create_validation_task(agent, trip_details: dict) -> Task:
    """Creates the validation task for the Input Validator Agent."""
    return Task(
        description=(
            f"Validate the following flight booking details and return a structured JSON report.\n\n"
            f"Trip details to validate:\n{json.dumps(trip_details, indent=2)}\n\n"
            "Perform ALL of the following checks:\n\n"
            "1. Use the Date Validation Tool with the departure_date, return_date, and trip_type.\n"
            "2. Use the Airport Lookup Tool to validate the origin city/airport.\n"
            "3. Use the Airport Lookup Tool to validate the destination city/airport.\n"
            "4. Check that origin and destination are not the same city or airport.\n"
            "5. Check that the passenger count is a number between 1 and 9.\n\n"
            "After running all tools, return ONLY a valid JSON object with NO extra text, "
            "markdown, or explanation. The response must be parseable JSON:\n"
            "{\n"
            '  "valid": true or false,\n'
            '  "errors": ["error message 1", "error message 2"],\n'
            '  "corrections": {\n'
            '    "origin": "corrected IATA code if fuzzy-matched, else null",\n'
            '    "destination": "corrected IATA code if fuzzy-matched, else null"\n'
            "  },\n"
            '  "warnings": ["optional warning if something looks unusual but is not invalid"]\n'
            "}"
        ),
        expected_output=(
            "A JSON object with 'valid' (bool), 'errors' (list of strings), "
            "'corrections' (dict with origin and destination keys), "
            "and 'warnings' (list of strings)."
        ),
        agent=agent,
    )


def create_clarification_task(agent, trip_details: dict) -> Task:
    """
    Phase 2 — Task for the Intent Clarifier Agent.
    Looks for unresolved natural-language values in slot data and resolves them.
    """
    today = date.today().isoformat()
    return Task(
        description=(
            f"Review the collected flight booking details below and resolve any ambiguous values.\n\n"
            f"Today's date: {today}\n"
            f"Current slot values:\n{json.dumps(trip_details, indent=2)}\n\n"
            "Work through each field systematically:\n\n"
            "1. 'departure_date': If it is NOT already in YYYY-MM-DD format (e.g. it looks like "
            "'Christmas', 'end of July', 'in 3 weeks'), use the Date Interpreter Tool to convert it. "
            "Pass JSON: {{\"date_text\": \"<value>\", \"today\": \"{today}\"}}\n\n"
            "2. 'return_date': Same as departure_date.\n\n"
            "3. 'destination': If it looks like vague travel criteria (e.g. 'somewhere warm', "
            "'beach holiday', 'cheap city break') rather than a real city or airport code, "
            "use the Destination Suggestion Tool to get specific options. "
            "Pass JSON: {{\"criteria\": \"<value>\"}}\n\n"
            "4. 'origin': If it looks like a city name with a possible typo (e.g. 'Londn', 'Dubaii'), "
            "use the Airport Lookup Tool to find the correct airport.\n\n"
            "If a field is already well-formed (valid IATA code, ISO date, integer), do NOT modify it.\n\n"
            "Return ONLY a valid JSON object with NO extra text or markdown:\n"
            "{{\n"
            '  "clarifications_needed": true or false,\n'
            '  "resolved": {{\n'
            '    "departure_date": "YYYY-MM-DD if resolved from ambiguous text, else null",\n'
            '    "return_date": "YYYY-MM-DD if resolved from ambiguous text, else null",\n'
            '    "origin": "resolved IATA code or city if typo-corrected, else null",\n'
            '    "destination": "resolved IATA code or city if resolved, else null"\n'
            "  }},\n"
            '  "unresolvable": ["list of field names that could not be resolved"],\n'
            '  "messages": ["one user-facing message per unresolvable field, e.g. destination suggestions"]\n'
            "}}"
        ).format(today=today),
        expected_output=(
            "JSON with 'clarifications_needed' (bool), 'resolved' (dict of corrected values), "
            "'unresolvable' (list of field names), and 'messages' (list of user-facing strings)."
        ),
        agent=agent,
    )


def create_error_recovery_task(agent, errors: list, trip_details: dict) -> Task:
    """
    Phase 2 — Task for the Error Recovery Agent.
    Converts raw validation errors into helpful, specific correction messages.
    """
    today = date.today().isoformat()
    return Task(
        description=(
            f"The validation agent found errors in a flight booking. Your job is to generate "
            f"specific, helpful correction messages for the user.\n\n"
            f"Today's date: {today}\n"
            f"Current trip details:\n{json.dumps(trip_details, indent=2)}\n\n"
            f"Validation errors found:\n{json.dumps(errors, indent=2)}\n\n"
            "For EACH error, generate one friendly and specific correction message:\n\n"
            "- Date in the past: Use the Date Interpreter Tool to suggest the same date next year "
            "or the next logical date. Tell the user specifically what to type.\n"
            "- Return before departure: Explain the issue and suggest a valid return date.\n"
            "- Airport/city not found: Use the Airport Lookup Tool with the user's input. "
            "If found via fuzzy match, tell the user 'Did you mean X (CODE)?'. "
            "If not found, suggest they try a nearby major city.\n"
            "- Same origin and destination: Point out the issue and ask for the correct destination.\n"
            "- Invalid passenger count: Give the valid range (1-9) and ask again.\n\n"
            "Messages must be friendly ('you', not 'the user'), specific, and include the correct "
            "value to type wherever possible.\n\n"
            "Return ONLY a valid JSON object with NO extra text or markdown:\n"
            "{{\n"
            '  "recovery_messages": ["friendly message for error 1", "friendly message for error 2"],\n'
            '  "suggested_corrections": {{\n'
            '    "departure_date": "suggested ISO date or null",\n'
            '    "return_date": "suggested ISO date or null",\n'
            '    "origin": "suggested value or null",\n'
            '    "destination": "suggested value or null"\n'
            "  }}\n"
            "}}"
        ),
        expected_output=(
            "JSON with 'recovery_messages' (list of friendly correction strings) "
            "and 'suggested_corrections' (dict of field→suggested value)."
        ),
        agent=agent,
    )


def create_extraction_task(agent, message: str) -> Task:
    """
    Phase 3 — Task for the Booking Info Extractor Agent.
    Extracts all available booking fields from a free-form natural language message.
    """
    today = date.today().isoformat()
    return Task(
        description=(
            f"Extract all available flight booking information from this message:\n"
            f"\"{message}\"\n\n"
            f"Today's date: {today}\n\n"
            "For each field, extract what is explicitly mentioned. Do NOT guess or assume.\n\n"
            "1. If a city or airport is mentioned: use the Airport Lookup Tool to get the IATA code.\n"
            "   Input: {{\"query\": \"<city name>\"}}\n"
            "2. If a date is mentioned: use the Date Interpreter Tool to convert to YYYY-MM-DD.\n"
            "   Input: {{\"date_text\": \"<date expression>\", \"today\": \"{today}\"}}\n"
            "3. For passengers: extract any number or phrase like 'wife and me' (=2), 'just me' (=1).\n"
            "4. For travel class: look for economy, business, first class, premium economy.\n"
            "5. For trip type: look for one-way, return, round trip.\n\n"
            "Return ONLY a valid JSON object with NO extra text:\n"
            "{{\n"
            '  "origin": "IATA code or city name, or null if not mentioned",\n'
            '  "destination": "IATA code or city name, or null if not mentioned",\n'
            '  "trip_type": "one-way or return, or null if not mentioned",\n'
            '  "departure_date": "YYYY-MM-DD, or null if not mentioned",\n'
            '  "return_date": "YYYY-MM-DD, or null if not mentioned",\n'
            '  "passengers": "number as string, or null if not mentioned",\n'
            '  "travel_class": "economy/business/premium_economy/first, or null if not mentioned"\n'
            "}}"
        ).format(today=today),
        expected_output=(
            "JSON object with 7 keys: origin, destination, trip_type, departure_date, "
            "return_date, passengers, travel_class. Null for fields not mentioned."
        ),
        agent=agent,
    )


def create_booking_review_task(agent, booking: dict) -> Task:
    """
    Phase 3 — Task for the Booking Reviewer Agent.
    Reviews a complete booking for cross-field issues and generates a summary.
    """
    return Task(
        description=(
            f"Review this complete flight booking and provide a quality assessment:\n\n"
            f"{json.dumps(booking, indent=2)}\n\n"
            "Use the Booking Review Tool to perform the full review.\n"
            "Input to the tool: the booking JSON above as a string.\n\n"
            "Then interpret the result and return a JSON object:\n"
            "{{\n"
            '  "confidence": "high/medium/low",\n'
            '  "flags": ["list of warnings or notes"],\n'
            '  "summary": "natural language one-line booking summary",\n'
            '  "message": "friendly message to show the user before they confirm"\n'
            "}}"
        ),
        expected_output=(
            "JSON with confidence, flags, summary, and a friendly user-facing message."
        ),
        agent=agent,
    )

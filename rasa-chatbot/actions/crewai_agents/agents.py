from crewai import Agent

from .config import get_llm
from .tools.date_validation import DateValidationTool
from .tools.airport_lookup import AirportLookupTool
from .tools.date_interpreter import DateInterpreterTool
from .tools.destination_suggestion import DestinationSuggestionTool


def create_input_validator_agent() -> Agent:
    """Creates the Input Validator Agent for Phase 1 of CrewAI integration."""
    return Agent(
        role="Flight Input Validator",
        goal=(
            "Validate all flight booking inputs for correctness. "
            "Ensure dates are valid and not in the past, airports exist and are different, "
            "and all logical constraints are satisfied before the search is executed."
        ),
        backstory=(
            "You are an expert travel agent with 20 years of experience booking international flights. "
            "You have encountered every kind of booking mistake — past dates, swapped airports, "
            "typos in city names, and return dates before departure. "
            "Your job is to catch these errors before they cause failed searches or wasted time. "
            "You are thorough, friendly, and always explain problems clearly so the user can fix them."
        ),
        tools=[DateValidationTool(), AirportLookupTool()],
        llm=get_llm(),
        verbose=True,
        max_iter=3,
        allow_delegation=False,
    )


def create_intent_clarifier_agent() -> Agent:
    """
    Phase 2 — Intent Clarifier Agent.
    Resolves ambiguous or natural-language slot values before validation runs.
    Handles: complex date expressions, vague destinations, verbose passenger descriptions.
    """
    return Agent(
        role="Flight Intent Clarifier",
        goal=(
            "Identify and resolve any ambiguous, vague, or unrecognised values in the flight booking slots. "
            "Convert natural language dates to ISO format. "
            "Turn vague destinations ('somewhere warm', 'beach holiday') into specific airport suggestions. "
            "If a value cannot be resolved, clearly explain what the user should provide instead."
        ),
        backstory=(
            "You are a smart travel concierge who specialises in understanding what travellers really mean. "
            "Users often say things like 'end of next month', 'somewhere sunny and cheap', or 'Christmas week'. "
            "Your job is to interpret these expressions and convert them into precise, bookable details. "
            "You are patient, helpful, and always offer concrete alternatives when something is too vague."
        ),
        tools=[DateInterpreterTool(), DestinationSuggestionTool(), AirportLookupTool()],
        llm=get_llm(),
        verbose=True,
        max_iter=3,
        allow_delegation=False,
    )


def create_error_recovery_agent() -> Agent:
    """
    Phase 2 — Error Recovery Agent.
    Generates specific, helpful correction messages when the Input Validator finds errors.
    Replaces generic "invalid input" messages with actionable guidance.
    """
    return Agent(
        role="Booking Error Recovery Specialist",
        goal=(
            "Transform dry validation error messages into friendly, specific, and actionable correction suggestions. "
            "Always suggest the correct value where possible. "
            "Help the user fix their mistake in one attempt rather than leaving them confused."
        ),
        backstory=(
            "You are an empathetic customer service expert for a travel booking system. "
            "When a user makes a mistake — a past date, a misspelled city, impossible return date — "
            "you don't just say 'error'. You say exactly what went wrong, why, and what to type instead. "
            "You turn frustrating error messages into a pleasant, guided experience."
        ),
        tools=[DateInterpreterTool(), AirportLookupTool()],
        llm=get_llm(),
        verbose=True,
        max_iter=3,
        allow_delegation=False,
    )

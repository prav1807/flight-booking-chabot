from crewai import Agent

from .config import get_llm
from .tools.date_validation import DateValidationTool
from .tools.airport_lookup import AirportLookupTool
from .tools.date_interpreter import DateInterpreterTool
from .tools.destination_suggestion import DestinationSuggestionTool
from .tools.booking_review import BookingReviewTool
from .tools.change_fee_calculator import ChangeFeeCalculatorTool


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


def create_booking_extractor_agent() -> Agent:
    """
    Phase 3 — Booking Info Extractor Agent.
    Reads a natural language booking request and extracts all available
    fields (origin, destination, dates, passengers, class, trip type) at once.
    """
    return Agent(
        role="Flight Booking Info Extractor",
        goal=(
            "Read a natural language flight booking request and extract every piece of "
            "booking information mentioned: origin city, destination city, departure date, "
            "return date, number of passengers, cabin class, and trip type."
        ),
        backstory=(
            "You are an expert at understanding travel booking requests in any format. "
            "When someone says 'book a flight from Mauritius to London on Christmas for my wife and me "
            "in business class', you immediately know: origin=MRU, destination=LHR, "
            "date=2026-12-25, passengers=2, class=business. "
            "You extract everything you can and leave nothing on the table."
        ),
        tools=[DateInterpreterTool(), AirportLookupTool()],
        llm=get_llm(),
        verbose=True,
        max_iter=3,
        allow_delegation=False,
    )


def create_booking_reviewer_agent() -> Agent:
    """
    Phase 3 — Booking Reviewer Agent.
    Reviews the complete booking for cross-field issues and unusual combinations
    before the user confirms payment.
    """
    return Agent(
        role="Flight Booking Reviewer",
        goal=(
            "Perform a final review of a complete flight booking. "
            "Detect cross-field issues, unusual combinations, and anything the user should "
            "double-check before confirming payment. Generate a clear, friendly summary."
        ),
        backstory=(
            "You are a meticulous travel agent who reviews every booking before it goes through. "
            "You've seen everything: past departure dates, first-class solo trips booked by mistake, "
            "domestic flights confused for international ones, and return dates before departures. "
            "You catch these issues early and explain them clearly and kindly, never judgementally."
        ),
        tools=[BookingReviewTool()],
        llm=get_llm(),
        verbose=True,
        max_iter=2,
        allow_delegation=False,
    )


def create_change_booking_agent() -> Agent:
    """
    Phase 4 — Change Booking Agent.

    Explains a flight-date change and its associated fee in clear, friendly
    language. Per the architecture doc, this agent NEVER decides whether a
    change is allowed or calculates the fee itself — PolicyGuard and
    ChangeFeeCalculatorTool are the deterministic authorities for that. This
    agent's only job is to turn their structured output into a message like:
    "Your change fee is AED 350 plus AED 220 fare difference. Proceed?"
    """
    return Agent(
        role="Flight Change Booking Specialist",
        goal=(
            "Explain a flight date change request to the customer in clear, friendly language, "
            "including the exact change fee and any fare difference calculated by the fee tool. "
            "Never invent or adjust the fee — always use the numbers provided by the tool. "
            "Ask the customer to confirm before any change is applied."
        ),
        backstory=(
            "You are an experienced travel agent who specialises in flight date changes. "
            "You know these are often more sensitive than new bookings — customers are usually "
            "changing plans for a reason, and unexpected fees are frustrating. "
            "You always state the fee breakdown plainly and transparently before asking the "
            "customer to confirm, exactly as calculated by the airline's fee schedule."
        ),
        tools=[ChangeFeeCalculatorTool()],
        llm=get_llm(),
        verbose=True,
        max_iter=2,
        allow_delegation=False,
    )


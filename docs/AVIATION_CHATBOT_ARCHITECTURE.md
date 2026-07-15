# ✈️ Aviation Chatbot — Industry Challenges & Multi-Agent Architecture

> **Project Stack:** Rasa Pro · CrewAI · Ollama (qwen3:8b) · Duffel API · Supabase · Python 3.11

---

## Table of Contents

1. [Why Aviation Has No Full Booking Chatbot](#1-why-aviation-has-no-full-booking-chatbot)
2. [Multi-Agent Architecture with CrewAI](#2-multi-agent-architecture-with-crewai)
3. [Agent Definitions](#3-agent-definitions)
4. [Guardrail & Safeguard Middleware](#4-guardrail--safeguard-middleware)
5. [End-to-End Conversation Flow](#5-end-to-end-conversation-flow)
6. [Tool-to-Agent Mapping](#6-tool-to-agent-mapping)
7. [Adaptation to This Project's Stack](#7-adaptation-to-this-projects-stack)
8. [Production Readiness Checklist](#8-production-readiness-checklist)

---

## 1. Why Aviation Has No Full Booking Chatbot

### 1.1 Complex Booking Systems

Airlines rely on decades-old Global Distribution Systems (Amadeus, Sabre, Travelport) designed for human travel agents, not conversational AI. Integrating deep enough to search, price, book, modify, and ticket reservations is technically challenging.

**How this project solves it:** The [Duffel API](https://duffel.com/docs) provides a modern REST interface to airline inventory, abstracting GDS complexity. CrewAI agents call Duffel through deterministic Python tools — never directly via LLM.

### 1.2 Flight Pricing Changes Constantly

Fares change based on:

- Seat availability and demand
- Booking class
- Taxes and promotions
- Baggage choices
- Payment method
- Loyalty status

A chatbot must ensure the price shown is valid at the exact moment of purchase.

**How this project solves it:** The `search_duffel_flights` action fetches live pricing. The `crewai_validate_inputs` agent validates inputs *before* calling Duffel, reducing wasted API calls on invalid searches.

### 1.3 Many Exceptions & Special Cases

A booking may involve: multiple airlines, codeshare flights, visa requirements, infants, pets, wheelchair assistance, unaccompanied minors, loyalty upgrades, travel credits, and vouchers.

**How this project solves it:** CrewAI's multi-agent approach isolates concerns — each agent handles one domain. The `Error Recovery Agent` handles edge cases gracefully instead of returning generic errors.

### 1.4 Security Requirements

Retrieving a booking requires verifying identity. Airlines must protect passengers from unauthorized access to passport information, payment details, travel itineraries, and frequent flyer accounts.

**How this project solves it:** Booking retrieval uses `booking_reference_lookup` slot validated against Supabase records. Future enhancement: add Identity Service middleware (see [Section 4.2](#42-identity-service)).

### 1.5 High Cost of Mistakes

If a chatbot books the wrong date, misunderstands a city, applies the wrong fare, forgets baggage, or changes the wrong ticket — the airline absorbs significant costs.

**How this project solves it:** Three-layer validation:

1. `crewai_validate_inputs` — catches logical errors before search
2. `crewai_review_booking` — cross-field review before confirmation
3. `confirm_booking` — explicit user confirmation before persistence

### 1.6 Regulatory & Legal Considerations

Booking flows must disclose fare rules, cancellation policies, refund eligibility, baggage fees, taxes, and passenger rights accurately and at the right time.

**How this project solves it:** `show_final_booking_summary` presents all details from Duffel API data (not LLM-generated). The Booking Reviewer Agent flags unusual combinations for the user to double-check.

### 1.7 Business Considerations

Airlines prefer graphical booking flows for upselling (extra baggage, seat selection, lounge access, insurance). A conversational interface is slower for displaying many options.

**How this project solves it:** The chatbot focuses on the *search and book* flow where conversation excels ("cheapest flight to London next Friday"). Complex visual selections (seat maps) can link out to a UI.

---

## 2. Multi-Agent Architecture with CrewAI

### Core Principle

> **The AI decides *what* to do. The booking engine decides *how* to do it.**

The LLM orchestrates; deterministic APIs execute. No LLM-generated pricing, no LLM-created bookings.

### Architecture Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                       Rasa Pro                               │
│  (Flow orchestration · NLU via Ollama qwen3:8b)             │
│  ┌─────────────────────────────────────────────────────┐    │
│  │  Flows: collect_trip_information, retrieve_booking   │    │
│  └──────────┬──────────────────────────────────────────┘    │
└─────────────┼───────────────────────────────────────────────┘
              │ Custom Action calls (HTTP → localhost:5055)
              ▼
┌─────────────────────────────────────────────────────────────┐
│                  Rasa Action Server                          │
│  ┌─────────────────────────────────────────────────────┐    │
│  │              CrewAI Agent Layer                      │    │
│  │                                                     │    │
│  │  ┌───────────────┐  ┌────────────────────────────┐  │    │
│  │  │ Input         │  │ Booking                    │  │    │
│  │  │ Validator     │  │ Reviewer                   │  │    │
│  │  │ Agent         │  │ Agent                      │  │    │
│  │  └───────────────┘  └────────────────────────────┘  │    │
│  │  ┌───────────────┐  ┌────────────────────────────┐  │    │
│  │  │ Intent        │  │ Error Recovery             │  │    │
│  │  │ Clarifier     │  │ Agent                      │  │    │
│  │  │ Agent         │  │                            │  │    │
│  │  └───────────────┘  └────────────────────────────┘  │    │
│  │  ┌───────────────┐                                  │    │
│  │  │ Booking Info  │                                  │    │
│  │  │ Extractor     │                                  │    │
│  │  └───────────────┘                                  │    │
│  └─────────────────────────────────────────────────────┘    │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐    │
│  │           Guardrail Middleware (Future)              │    │
│  │  ┌────────┐ ┌────────┐ ┌────────┐ ┌─────────────┐  │    │
│  │  │Policy  │ │Identity│ │PII     │ │Audit        │  │    │
│  │  │Guard   │ │Service │ │Guard   │ │Logger       │  │    │
│  │  └────────┘ └────────┘ └────────┘ └─────────────┘  │    │
│  └─────────────────────────────────────────────────────┘    │
│                                                             │
│  Deterministic Actions: normalize, search, validate, save   │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│           External APIs                                      │
│  ┌──────────────────┐     ┌──────────────────────────────┐  │
│  │  Duffel API      │     │  Supabase                    │  │
│  │  (Flight search, │     │  (Booking storage,           │  │
│  │   pricing,       │     │   retrieval)                 │  │
│  │   booking)       │     │                              │  │
│  └──────────────────┘     └──────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

---

## 3. Agent Definitions

### 3.1 Input Validator Agent

| Property | Value |
|----------|-------|
| **Role** | Flight Input Validator |
| **Trigger** | `crewai_validate_inputs` action |
| **Tools** | `DateValidationTool`, `AirportLookupTool` |
| **Responsibility** | Validate dates (not past, return > departure), airports exist and differ, logical constraints |
| **Max Iterations** | 3 |

### 3.2 Intent Clarifier Agent

| Property | Value |
|----------|-------|
| **Role** | Flight Intent Clarifier |
| **Trigger** | `crewai_clarify_intent` action |
| **Tools** | `DateInterpreterTool`, `DestinationSuggestionTool`, `AirportLookupTool` |
| **Responsibility** | Resolve "end of next month", "Christmas week", "somewhere warm" into concrete values |
| **Max Iterations** | 3 |

### 3.3 Error Recovery Agent

| Property | Value |
|----------|-------|
| **Role** | Booking Error Recovery Specialist |
| **Trigger** | Called by Input Validator when errors found |
| **Tools** | `DateInterpreterTool`, `AirportLookupTool` |
| **Responsibility** | Transform "invalid input" into "Did you mean London Heathrow (LHR)?" |
| **Max Iterations** | 3 |

### 3.4 Booking Info Extractor Agent

| Property | Value |
|----------|-------|
| **Role** | Flight Booking Info Extractor |
| **Trigger** | `crewai_extract_trip_info` action |
| **Tools** | `DateInterpreterTool`, `AirportLookupTool` |
| **Responsibility** | Extract all slot values from a single natural language request |
| **Max Iterations** | 3 |

### 3.5 Booking Reviewer Agent

| Property | Value |
|----------|-------|
| **Role** | Flight Booking Reviewer |
| **Trigger** | `crewai_review_booking` action |
| **Tools** | `BookingReviewTool` |
| **Responsibility** | Cross-field validation, unusual combination detection, confidence summary |
| **Max Iterations** | 2 |

---

## 4. Guardrail & Safeguard Middleware

These are **infrastructure components** — not CrewAI agents. Every agent request flows through them before reaching external APIs.

```
Agent Request → Policy Guard → Identity Service → PII Guard → API Call
                                                                  │
                              Audit Logger ← ← ← ← ← ← ← ← Result
```

### 4.1 Policy Guard

**Purpose:** Prevent actions that violate airline rules or regulations.

**Implementation for this project:**

```python
# rasa-chatbot/actions/middleware/policy_guard.py
class PolicyGuard:
    """Validates requests against business rules before API execution."""

    def check(self, action: str, context: dict) -> dict:
        """
        Example checks:
        - Departure date not in the past
        - Return date after departure
        - Passenger count 1-9
        - Origin != Destination
        - Booking is modifiable before change
        """
        # Returns {"approved": True} or {"approved": False, "reason": "..."}
```

**Current status:** Partially covered by `crewai_validate_inputs` (dates, airports). Extend to cover booking modification rules.

### 4.2 Identity Service

**Purpose:** Never let an LLM decide whether someone is authenticated.

**Implementation for this project:**

```python
# rasa-chatbot/actions/middleware/identity_service.py
class IdentityService:
    """Deterministic identity verification — not LLM-controlled."""

    def verify(self, booking_reference: str, surname: str) -> dict:
        """
        Verify against Supabase booking records.
        Returns: {"authenticated": True} or {"status": "VERIFICATION_FAILED"}
        """
        # Query Supabase for booking_reference + surname match
```

**Current status:** `retrieve_booking_from_supabase` queries by reference only. Enhance with surname/email verification.

### 4.3 PII Guard

**Purpose:** Mask sensitive data before passing to the LLM.

**Implementation for this project:**

```python
# rasa-chatbot/actions/middleware/pii_guard.py
class PIIGuard:
    """Sanitizes sensitive fields before they reach CrewAI agents."""

    def mask(self, data: dict) -> dict:
        """
        Transforms:
          {"email": "john@example.com", "phone": "+23057001234"}
        To:
          {"email": "j***@example.com", "phone": "+2305*****34"}
        """
```

**Current status:** Not yet implemented. The LLM currently sees passenger email/phone in slots. Add masking before CrewAI agent context.

### 4.4 Audit Logger

**Purpose:** Record every decision, tool call, and customer confirmation for traceability.

**Implementation for this project:**

```python
# rasa-chatbot/actions/middleware/audit_logger.py
import logging
from datetime import datetime

class AuditLogger:
    """Structured logging for every significant action."""

    def log(self, agent: str, action: str, input_data: dict, output_data: dict):
        """
        Example log entry:
        {
            "timestamp": "2026-07-15T20:10:00Z",
            "agent": "Input Validator",
            "action": "validate_dates",
            "input": {"departure": "2026-07-20", "return": "2026-07-18"},
            "output": {"valid": false, "reason": "Return before departure"}
        }
        """
```

**Current status:** CrewAI runs with `verbose=True` for development. For production, add structured JSON logging to Supabase or a log table.

### 4.5 Confirmation Guard

**Purpose:** Require explicit user confirmation before irreversible actions.

**Current status:** ✅ Already implemented via `booking_confirmation` slot + `confirm_booking` action. User must type "confirm" or "yes" before `save_booking_to_supabase` executes. The `crewai_review_booking` agent shows a summary first.

### 4.6 Human Escalation

**Purpose:** Transfer to live agent when automation cannot handle the case.

**Triggers:**

- Repeated validation failures (>3 retries)
- Low LLM confidence scores
- Customer frustration signals
- Unsupported requests (group bookings, medical travel, complaints)

**Implementation for this project:**

```python
# rasa-chatbot/actions/middleware/escalation_manager.py
class EscalationManager:
    """Monitors conversation signals and triggers handoff."""

    def should_escalate(self, tracker) -> bool:
        # Count slot resets, failed validations, negative sentiment
        pass

    def escalate(self, dispatcher, tracker):
        dispatcher.utter_message(
            text="Let me connect you with a travel specialist who can help further."
        )
        # Trigger Rasa handoff channel or store conversation for agent pickup
```

### 4.7 Session Manager

**Purpose:** Maintain structured booking context across multiple turns.

**Current status:** ✅ Already handled by Rasa Pro's slot system:

```
Slots maintained across turns:
  - origin, destination, departure_date, return_date
  - passengers, travel_class, trip_type
  - selected_flight, passenger_full_name, passenger_email, passenger_phone

CrewAI agents read from tracker.get_slot() and write via SlotSet events.
```

### 4.8 Rate Limiter & Abuse Detection

**Purpose:** Protect Duffel API and system from excessive or malicious use.

**Implementation for this project:**

```python
# rasa-chatbot/actions/middleware/rate_limiter.py
class RateLimiter:
    """Limits API calls per session to prevent abuse."""

    MAX_SEARCHES_PER_SESSION = 10
    MAX_FAILED_AUTH_ATTEMPTS = 3

    def check(self, sender_id: str, action: str) -> bool:
        # Track call counts in memory or Supabase
        # Block if threshold exceeded
        pass
```

---

## 5. End-to-End Conversation Flow

### 5.1 Booking Flow (Current Implementation)

```
User: "Book me a flight from Mauritius to London next Friday, business class for 2"
  │
  ▼
Rasa NLU (qwen3:8b via Ollama)
  → Triggers: collect_trip_information flow
  │
  ▼
crewai_extract_trip_info
  → Extracts: origin=MRU, dest=LHR, date=2026-07-18, class=business, pax=2
  │
  ▼
normalize_trip_details + check_airport_options
  → Resolves IATA codes, presents options if ambiguous
  │
  ▼
crewai_clarify_intent
  → Converts "next Friday" → 2026-07-18 (ISO)
  → Validates date is logical
  │
  ▼
crewai_validate_inputs
  → Cross-checks: origin ≠ destination ✓, date not past ✓, return > departure ✓
  → If errors found → Error Recovery Agent suggests corrections
  │
  ▼
search_duffel_flights
  → Calls Duffel API with validated parameters
  → Returns live pricing and availability
  │
  ▼
User selects flight → validate_selected_flight
  │
  ▼
Collect passenger details → validate_passenger_email → validate_passenger_phone
  │
  ▼
crewai_review_booking
  → Final cross-field review
  → Generates confidence summary
  → Flags unusual combinations
  │
  ▼
show_final_booking_summary
  → All details from API data (not LLM-generated)
  │
  ▼
confirm_booking (explicit "yes" or "confirm" required)
  │
  ▼
save_booking_to_supabase
  → Persists booking record
```

### 5.2 Retrieval Flow (Current Implementation)

```
User: "Show my booking ABC123"
  │
  ▼
Rasa NLU → Triggers: retrieve_booking flow
  │
  ▼
collect: booking_reference_lookup
  │
  ▼
retrieve_booking_from_supabase
  → Queries Supabase by reference
  → Returns booking summary
```

### 5.3 Retrieval Flow (With Safeguards — Future)

```
User: "Show my booking ABC123"
  │
  ▼
collect: booking_reference_lookup + surname
  │
  ▼
Identity Service: verify(reference="ABC123", surname="Smith")
  → If OTP required → send OTP → collect and verify
  │
  ▼
PII Guard: mask sensitive fields before display
  │
  ▼
Audit Logger: log retrieval event
  │
  ▼
Display masked booking summary to user
```

### 5.4 Example Multi-Turn Conversation

```
User:     "Book me a flight to Tokyo."
Bot:      "Where will you be departing from?"

User:     "Dubai."
Bot:      "Got it — Dubai to Tokyo. One-way or return?"

User:     "Return."
Bot:      "When would you like to depart?"

User:     "End of next month."
            │
            ▼  [crewai_clarify_intent]
            │   DateInterpreterTool → 2026-08-31
            │
Bot:      "I've set your departure to 31 August 2026. When would you like to return?"

User:     "A week later."
            │
            ▼  [crewai_clarify_intent]
            │   DateInterpreterTool → 2026-09-07
            │
Bot:      "Return on 7 September 2026. How many passengers?"

User:     "2, economy."
            │
            ▼  [crewai_validate_inputs]
            │   All checks pass ✓
            │
            ▼  [search_duffel_flights]
            │   Returns 12 offers from Duffel API
            │
Bot:      "Here are your top options:
           1. Emirates EK318 — AED 3,240 pp
           2. Qatar Airways QR806 — AED 2,980 pp
           3. Etihad EY878 — AED 3,100 pp"

User:     "Option 2."
            │
            ▼  [crewai_review_booking]
            │   ✓ Route valid, dates logical, class matches price range
            │   Confidence: HIGH
            │
Bot:      "Here's your booking summary:
           Dubai (DXB) → Tokyo (NRT)
           Depart: 31 Aug 2026 | Return: 7 Sep 2026
           2 passengers, Economy
           Qatar Airways QR806 — AED 5,960 total
           
           Shall I confirm this booking?"

User:     "Yes, confirm."
            │
            ▼  [save_booking_to_supabase]
            │
Bot:      "Your booking has been confirmed. Reference: QR-7X2K9M"
```

---

## 6. Tool-to-Agent Mapping

| Agent | Tool | File | Action Performed |
|-------|------|------|-----------------|
| Input Validator | `DateValidationTool` | `tools/date_validation.py` | Checks date logic (not past, return > departure) |
| Input Validator | `AirportLookupTool` | `tools/airport_lookup.py` | Fuzzy-matches city names to IATA codes |
| Intent Clarifier | `DateInterpreterTool` | `tools/date_interpreter.py` | Converts "Christmas" → 2026-12-25 |
| Intent Clarifier | `DestinationSuggestionTool` | `tools/destination_suggestion.py` | "warm and cheap" → airport suggestions |
| Intent Clarifier | `AirportLookupTool` | `tools/airport_lookup.py` | Resolves ambiguous cities |
| Booking Extractor | `DateInterpreterTool` | (shared) | Parse dates from natural language |
| Booking Extractor | `AirportLookupTool` | (shared) | Resolve city names in bulk extraction |
| Booking Reviewer | `BookingReviewTool` | `tools/booking_review.py` | Cross-field analysis and confidence scoring |
| Error Recovery | `DateInterpreterTool` | (shared) | Suggest correct date formats |
| Error Recovery | `AirportLookupTool` | (shared) | "Did you mean London Heathrow (LHR)?" |

### Deterministic Actions (Non-Agent)

| Action | File | Responsibility |
|--------|------|---------------|
| `normalize_trip_details` | `normalise_trip_details.py` | Rule-based IATA code resolution |
| `check_airport_options` | `check_airport_options.py` | Present multiple airport options for a city |
| `search_duffel_flights` | `search_duffel_flights.py` | Call Duffel API for live offers |
| `validate_selected_flight` | `validate_selected_flight.py` | Verify user's flight choice is valid |
| `validate_passenger_email` | `validate_passenger_email.py` | Regex email validation |
| `validate_passenger_phone` | `validate_passenger_phone.py` | Phone number format check |
| `show_final_booking_summary` | `show_final_booking_summary.py` | Display all booking details |
| `confirm_booking` | `confirm_booking.py` | Explicit yes/no gate before save |
| `save_booking_to_supabase` | `save_booking_to_supabase.py` | Persist booking to database |
| `retrieve_booking_from_supabase` | `retrieve_booking_from_supabase.py` | Fetch booking by reference |

---

## 7. Adaptation to This Project's Stack

### 7.1 LLM — Local Ollama (No API Costs)

```python
# crewai_agents/config.py
from crewai import LLM

def get_llm() -> LLM:
    return LLM(
        model="ollama/qwen3:8b",
        base_url="http://localhost:11434",
        temperature=0.1,  # Low for validation accuracy
    )
```

Key points:

- **No API keys** needed for LLM inference
- `think: false` in Rasa `endpoints.yml` disables qwen3 reasoning mode for faster responses
- CrewAI uses the same Ollama instance as Rasa Pro
- `nomic-embed-text` provides embeddings for flow retrieval

### 7.2 Flight Search — Duffel API (Not Amadeus/Sabre Directly)

```python
# actions/duffel_client.py handles all flight search and booking
# CrewAI agents NEVER call Duffel directly
# They validate inputs → Rasa action calls Duffel → returns structured results
```

Duffel provides:

- `POST /air/offer_requests` — search flights
- `POST /air/orders` — create bookings
- Modern REST API (NDC-ready)
- No GDS terminal access required

### 7.3 Booking Storage — Supabase

```python
# actions/supabase_client.py
# Bookings saved to Supabase after confirmation
# Retrieval queries Supabase by booking_reference
```

This is a **prototype/research implementation** — in production, Duffel's order management handles actual PNR lifecycle while Supabase stores supplementary metadata and user preferences.

### 7.4 Dialog Management — Rasa Pro Flows

```yaml
# Rasa Pro handles:
#   - NLU (intent detection via qwen3:8b through CompactLLMCommandGenerator)
#   - Flow orchestration (YAML-defined conversation flows)
#   - Slot collection and validation
#   - Response generation

# CrewAI handles:
#   - Intelligent input validation (beyond regex)
#   - Ambiguity resolution (natural language → ISO dates, vague → specific)
#   - Cross-field review (booking consistency checks)
#   - Error recovery with contextual suggestions
```

### 7.5 Two Virtual Environments (Dependency Isolation)

| venv | Contents | Why Separate |
|------|----------|--------------|
| `.venv` | Rasa Pro | Requires `websockets<11` |
| `.venv-actions` | rasa-sdk, CrewAI, duffel-api, supabase, python-dotenv | Requires `websockets>=11` |

---

## 8. Production Readiness Checklist

### Currently Implemented ✅

- [x] Multi-agent validation (Input Validator, Intent Clarifier, Error Recovery)
- [x] Booking review before confirmation (Booking Reviewer Agent)
- [x] Natural language extraction (Booking Info Extractor Agent)
- [x] Explicit confirmation guard (`confirm_booking` action)
- [x] Session management (Rasa Pro slot system + tracker store)
- [x] Local LLM — no API costs, no data leaving machine (Ollama qwen3:8b)
- [x] Deterministic API calls (Duffel for flights, Supabase for persistence)
- [x] Agent iteration limits (`max_iter=3`) to prevent infinite loops
- [x] Booking retrieval by reference

### Needed for Production 🔲

- [ ] **Policy Guard** — Business rule enforcement middleware
- [ ] **Identity Service** — Surname/OTP verification for booking retrieval
- [ ] **PII Guard** — Mask email/phone/passport before LLM context
- [ ] **Audit Logger** — Structured JSON logs for every agent action
- [ ] **Human Escalation** — Handoff when confidence < threshold or repeated failures
- [ ] **Rate Limiter** — Protect Duffel API from abuse (max searches per session)
- [ ] **Payment Integration** — Stripe/payment gateway (LLM never sees card data)
- [ ] **Ticketing** — E-ticket issuance after payment confirmation
- [ ] **Change Booking Agent** — Modify existing reservations (penalties, fare differences)
- [ ] **Cancellation Agent** — Handle refunds per fare rules

### Proposed File Structure for Safeguards

```
rasa-chatbot/actions/
├── middleware/
│   ├── __init__.py
│   ├── policy_guard.py          # Business rule validation
│   ├── identity_service.py      # Authentication verification
│   ├── pii_guard.py             # Sensitive data masking
│   ├── audit_logger.py          # Structured event logging
│   ├── escalation_manager.py    # Human handoff triggers
│   └── rate_limiter.py          # API abuse prevention
├── crewai_agents/               # (existing — implemented)
│   ├── __init__.py
│   ├── config.py                # Ollama LLM configuration
│   ├── agents.py                # All agent definitions
│   ├── crews.py                 # Crew assembly
│   ├── tasks.py                 # Task definitions
│   ├── ollama_health.py         # Ollama connectivity check
│   └── tools/
│       ├── __init__.py
│       ├── date_validation.py   # Date logic checks
│       ├── date_interpreter.py  # NL date → ISO conversion
│       ├── airport_lookup.py    # Fuzzy city → IATA matching
│       ├── destination_suggestion.py  # Vague → specific suggestions
│       ├── booking_review.py    # Cross-field analysis
│       └── travel_requirements.py     # Visa/document checks
├── crewai_validate_inputs.py    # Rasa action → Input Crew
├── crewai_clarify_intent.py     # Rasa action → Clarifier
├── crewai_extract_trip_info.py  # Rasa action → Extractor
├── crewai_review_booking.py     # Rasa action → Reviewer
└── ... (existing deterministic actions)
```

---

## References

- [CrewAI Documentation](https://docs.crewai.com/)
- [Rasa Pro Documentation](https://rasa.com/docs/rasa-pro/)
- [Duffel API Reference](https://duffel.com/docs/api)
- [Ollama](https://ollama.com/)
- [IATA NDC Standard](https://www.iata.org/en/programs/airline-retailing/ndc/)
- [Supabase Documentation](https://supabase.com/docs)

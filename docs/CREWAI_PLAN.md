# CrewAI Integration Plan — Flight Booking Chatbot

## 1. Problem Statement

The current Rasa-based flight booking chatbot relies on **rule-based normalisation and regex validation** (e.g., `normalisation_service.py`, `validate_passenger_email.py`). While functional, it has limitations:

- Hard-coded airport mappings — fails on unknown cities/airports
- Date normalisation doesn't catch logical errors (e.g., return date before departure)
- No semantic understanding of ambiguous inputs ("somewhere warm", "cheapest option")
- No intelligent error recovery — just "invalid input, try again"
- No cross-field validation (e.g., same origin and destination)

**Research Question:**  
> *"Can a multi-agent system (CrewAI) reduce user input errors and improve booking completion rates in a conversational flight booking chatbot?"*

---

## 2. Proposed Architecture

```
┌─────────────────────────────────────────────────────┐
│                    Rasa Pro                          │
│  (Flow orchestration + NLU via Ollama qwen3:8b)     │
└──────────┬──────────────────────────────────────────┘
           │ Custom Action calls
           ▼
┌─────────────────────────────────────────────────────┐
│              Rasa Action Server                      │
│  ┌───────────────────────────────────────────────┐  │
│  │            CrewAI Agent Layer                  │  │
│  │                                               │  │
│  │  ┌─────────────┐  ┌──────────────────────┐   │  │
│  │  │  Input      │  │  Booking              │   │  │
│  │  │  Validator  │  │  Reviewer             │   │  │
│  │  │  Agent      │  │  Agent                │   │  │
│  │  └─────────────┘  └──────────────────────┘   │  │
│  │  ┌─────────────┐  ┌──────────────────────┐   │  │
│  │  │  Intent     │  │  Error Recovery       │   │  │
│  │  │  Clarifier  │  │  Agent                │   │  │
│  │  │  Agent      │  │                       │   │  │
│  │  └─────────────┘  └──────────────────────┘   │  │
│  └───────────────────────────────────────────────┘  │
│                                                     │
│  Existing actions: normalize, validate, search...   │
└─────────────────────────────────────────────────────┘
           │
           ▼
┌─────────────────────────────────────────────────────┐
│        External APIs (Duffel, Supabase)             │
└─────────────────────────────────────────────────────┘
```

---

## 3. CrewAI Agents Design

### Agent 1: Input Validator Agent

**Role:** Validates and enriches user inputs using LLM reasoning  
**Goal:** Catch errors that regex/rules miss  
**Backstory:** "You are an expert travel agent who validates flight booking details."

**Tasks:**
- Validate dates are logical (not in the past, return > departure)
- Detect impossible routes (same city origin/destination)
- Validate airport codes/city names against knowledge
- Check passenger count is reasonable (1–9)
- Flag suspicious inputs (e.g., typos in city names like "Londn")

**Tools:**
- `DateValidationTool` — checks date logic
- `AirportLookupTool` — fuzzy matches city names to IATA codes (replaces hard-coded mapping)

**Integration point:** Replace/augment `normalize_trip_details` action

---

### Agent 2: Intent Clarifier Agent

**Role:** Disambiguates vague or incomplete user inputs  
**Goal:** Convert ambiguous user messages into structured slot values  
**Backstory:** "You are a helpful travel assistant who asks smart follow-up questions."

**Tasks:**
- Interpret natural language dates ("end of next month", "Christmas week")
- Resolve ambiguous destinations ("I want to go somewhere warm and cheap")
- Infer trip type from context ("me and my wife for a weekend" → 2 passengers, return)
- Handle multi-intent messages ("fly London to Paris next Friday, business class for 2")

**Tools:**
- `DateInterpreterTool` — converts complex date expressions to ISO format
- `DestinationSuggestionTool` — suggests airports based on criteria

**Integration point:** New action `crewai_clarify_intent` called before `normalize_trip_details`

---

### Agent 3: Booking Reviewer Agent

**Role:** Final review of complete booking before submission  
**Goal:** Catch last-minute errors and present a human-readable summary  
**Backstory:** "You are a meticulous travel agent reviewing bookings before payment."

**Tasks:**
- Cross-validate all fields together (dates + route + class make sense)
- Check for common mistakes (wrong year, swapped origin/destination)
- Generate a natural language summary with confidence score
- Flag anything unusual ("Are you sure you want a first-class one-way flight for 1 person?")

**Tools:**
- `BookingSummaryTool` — formats booking into review format
- `PriceReasonabilityTool` — flags unusually priced flights

**Integration point:** Replace/augment `show_final_booking_summary` action

---

### Agent 4: Error Recovery Agent

**Role:** Provides intelligent suggestions when validation fails  
**Goal:** Guide users to correct input rather than just rejecting it  
**Backstory:** "You are a patient assistant who helps users fix mistakes."

**Tasks:**
- Suggest corrections for typos ("Did you mean London Heathrow (LHR)?")
- Offer alternatives when exact match fails
- Explain why input was rejected in plain language
- Provide examples of valid input formats

**Tools:**
- `FuzzyMatchTool` — finds closest valid options
- `ExampleGeneratorTool` — creates contextual input examples

**Integration point:** Called by other agents when validation fails, replaces generic error messages

---

## 4. CrewAI Crew Configuration

```python
# Two crews for different stages of the booking flow

# Crew 1: Input Processing Crew (sequential)
# Triggered after user provides trip details
input_crew = Crew(
    agents=[input_validator, intent_clarifier],
    tasks=[validate_inputs_task, clarify_ambiguity_task],
    process=Process.sequential,  # validator first, then clarifier
    verbose=True
)

# Crew 2: Booking Review Crew (sequential)
# Triggered before final booking confirmation
review_crew = Crew(
    agents=[booking_reviewer, error_recovery],
    tasks=[review_booking_task, suggest_corrections_task],
    process=Process.sequential,
    verbose=True
)
```

---

## 5. LLM Configuration (Ollama + qwen3:8b)

```python
from crewai import LLM

llm = LLM(
    model="ollama/qwen3:8b",
    base_url="http://localhost:11434",
    temperature=0.2,  # Low temperature for validation accuracy
)
```

> **Note:** CrewAI supports Ollama natively via the `ollama/` prefix. No API key needed.

---

## 6. File Structure (New Files)

```
rasa-chatbot/actions/
├── crewai_agents/
│   ├── __init__.py
│   ├── config.py              # LLM and shared configuration
│   ├── agents.py              # Agent definitions
│   ├── tasks.py               # Task definitions
│   ├── crews.py               # Crew assembly
│   └── tools/
│       ├── __init__.py
│       ├── date_validation.py
│       ├── airport_lookup.py
│       ├── fuzzy_match.py
│       └── booking_summary.py
├── crewai_validate_inputs.py   # New Rasa action using Input Crew
├── crewai_review_booking.py    # New Rasa action using Review Crew
└── ... (existing files unchanged)
```

---

## 7. Modified Flow (flight_search_flow.yml)

```yaml
# Key changes marked with ← NEW
steps:
  - action: utter_start_flight_search
  - collect: origin
  - collect: destination
  - action: crewai_validate_inputs      # ← NEW (replaces normalize_trip_details)
  - action: check_airport_options
  - collect: origin_airport
  - collect: destination_airport
  - collect: trip_type
  - collect: departure_date
  - collect: return_date               # (if return trip)
  - collect: passengers
  - collect: travel_class
  - action: show_trip_summary
  - action: search_duffel_flights
  - collect: selected_flight
  - action: validate_selected_flight
  - collect: passenger_full_name
  - collect: passenger_email
  - action: validate_passenger_email
  - collect: passenger_phone
  - action: validate_passenger_phone
  - action: crewai_review_booking       # ← NEW (before final summary)
  - action: show_final_booking_summary
  - collect: booking_confirmation
  - action: confirm_booking
```

---

## 8. Dependencies

Add to `.venv-actions`:
```
crewai[tools]>=0.80.0
```

> CrewAI goes in the **actions venv** (not the Rasa venv) since it runs in the action server. This avoids the websockets conflict.

---

## 9. Implementation Phases

### Phase 1: Foundation ✅ Complete
- [x] Install CrewAI in `.venv-actions`
- [x] Create `crewai_agents/` folder structure
- [x] Configure LLM connection to Ollama
- [x] Build `Input Validator Agent` with `DateValidationTool` and `AirportLookupTool`
- [x] Create `crewai_validate_inputs` Rasa action
- [x] Test with basic inputs (valid dates, known airports)

### Phase 2: Intelligence ✅ Complete
- [x] Build `Intent Clarifier Agent` with `DateInterpreterTool` and `DestinationSuggestionTool`
- [x] Build `Error Recovery Agent` with `DateInterpreterTool` + `AirportLookupTool`
- [x] Create `crewai_clarify_intent` Rasa action
- [x] Update `crewai_validate_inputs` to call Error Recovery crew when errors found
- [x] Handle edge cases: typos, ambiguous cities, complex dates ("Christmas", "end of next month")

### Phase 3: Review & Polish (Week 3)
- [ ] Build `Booking Reviewer Agent`
- [ ] Create `crewai_review_booking` Rasa action
- [ ] Cross-field validation logic
- [ ] Natural language confidence summaries

### Phase 4: Evaluation (Week 4)
- [ ] Design test scenarios (20+ cases: valid, invalid, ambiguous)
- [ ] Measure: error catch rate, booking completion rate, response time
- [ ] Compare: with CrewAI vs without CrewAI (A/B metrics)
- [ ] Document results for dissertation/thesis

---

## 10. Evaluation Metrics (for Postgraduate Research)

| Metric | Without CrewAI | With CrewAI | How to Measure |
|--------|---------------|-------------|----------------|
| Input error catch rate | Baseline | Target: +40% | Count errors caught before API call |
| Booking completion rate | Baseline | Target: +25% | Successful bookings / attempts |
| Avg. corrections per booking | Baseline | Target: -50% | Slot resets counted |
| User satisfaction | Survey | Survey | Likert scale post-task |
| Response latency | ~1s | ~3-5s (LLM) | Time per action |

---

## 11. Academic Contribution

This work contributes:
1. **Novel architecture** — Multi-agent validation layer (CrewAI) integrated inside a dialogue system (Rasa Pro)
2. **Practical evaluation** — Quantitative comparison of rule-based vs LLM-agent-based input validation
3. **Reproducible** — Uses open-source tools (CrewAI, Ollama, Rasa) with local LLM (no API costs)
4. **Problem solved** — Reduces user friction and error rates in task-oriented dialogue systems

---

## 12. Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Ollama/qwen3 too slow for agents | High latency | Use `think: false`, smaller model for simple tasks, cache results |
| CrewAI hallucinations | Wrong corrections | Add rule-based fallback, confidence thresholds |
| Dependency conflicts | Install fails | Isolated in `.venv-actions`, pin versions |
| Agent loops | Infinite retries | Set `max_iter=3` on agents, timeout on crew |

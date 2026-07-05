"""
Phase 3 — Booking Review Tool + Travel Requirements (combined)

Rule-based checks:
  - Cross-field booking validation (dates, class/pax combos, same-region routes)
  - Travel entry requirements (visa, ESTA, address, onward travel)

Works without Ollama — pure Python.
"""
import json
from datetime import date, datetime

from crewai.tools import BaseTool
from .travel_requirements import TravelRequirementsTool


# Countries / regions used to flag same-country routes
_SAME_REGION_PAIRS = {
    frozenset({"LHR", "LGW", "STN", "LTN", "LCY", "MAN", "EDI", "GLA", "BHX", "BRS"}): "UK",
    frozenset({"CDG", "ORY", "NCE", "LYS", "MRS", "TLS", "BOD"}): "France",
    frozenset({"JFK", "LGA", "EWR", "BOS", "LAX", "SFO", "ORD", "MIA", "ATL", "DFW", "SEA", "DEN"}): "USA",
    frozenset({"DXB", "AUH", "SHJ"}): "UAE",
    frozenset({"SIN", "KUL", "BKK", "HKG", "CGK"}): "SE Asia",
}

_EXPENSIVE_COMBOS = [
    ("first", 1, "solo first-class"),
    ("business", 1, "solo business-class"),
]


class BookingReviewTool(BaseTool):
    name: str = "Booking Review Tool"
    description: str = (
        "Performs a final cross-field review of a complete flight booking. "
        "Checks for unusual combinations, flags anything worth confirming with the user, "
        "and returns a structured confidence summary. "
        "Input: JSON string with keys: origin, destination, trip_type, departure_date, "
        "return_date, passengers, travel_class. "
        "Returns JSON with: confidence (high/medium/low), flags (list of warnings), "
        "summary (natural language booking description)."
    )

    def _run(self, input_json: str) -> str:
        try:
            data = json.loads(input_json)
        except Exception:
            return json.dumps({"confidence": "low", "flags": ["Invalid input."], "summary": ""})

        origin = str(data.get("origin") or "").upper()
        destination = str(data.get("destination") or "").upper()
        trip_type = str(data.get("trip_type") or "one-way").lower()
        departure_date_str = str(data.get("departure_date") or "")
        return_date_str = str(data.get("return_date") or "")
        passengers = data.get("passengers")
        travel_class = str(data.get("travel_class") or "economy").lower()

        flags = []
        today = date.today()

        # ── Date sanity checks ────────────────────────────────────────────────────
        departure_date = None
        if departure_date_str:
            try:
                departure_date = datetime.strptime(departure_date_str, "%Y-%m-%d").date()
                days_until = (departure_date - today).days
                if days_until < 0:
                    flags.append(f"⚠️ Departure date ({departure_date_str}) is in the past.")
                elif days_until < 3:
                    flags.append(f"⚠️ Departure is very soon ({days_until} day(s) away). Make sure you have enough time to complete your booking.")
                elif days_until > 365:
                    flags.append(f"ℹ️ Departure is over a year away ({days_until} days). Prices may not be final yet.")
            except ValueError:
                flags.append(f"⚠️ Departure date '{departure_date_str}' doesn't look like a valid date.")

        if return_date_str and "return" in trip_type:
            try:
                return_date = datetime.strptime(return_date_str, "%Y-%m-%d").date()
                if departure_date and return_date <= departure_date:
                    flags.append("⚠️ Return date must be after the departure date.")
                else:
                    trip_length = (return_date - departure_date).days if departure_date else None
                    if trip_length and trip_length > 90:
                        flags.append(f"ℹ️ Long trip detected: {trip_length} days. Is that intentional?")
            except ValueError:
                pass

        # ── Same-region route ─────────────────────────────────────────────────────
        for region_airports, region_name in _SAME_REGION_PAIRS.items():
            if origin in region_airports and destination in region_airports:
                flags.append(f"ℹ️ Both {origin} and {destination} are in {region_name}. This is a domestic/regional flight.")
                break

        # ── Unusual class/passenger combos ────────────────────────────────────────
        try:
            pax = int(passengers or 1)
        except (TypeError, ValueError):
            pax = 1

        if travel_class == "first" and pax == 1:
            flags.append("ℹ️ Solo first-class ticket — one of our premium options! Just confirming this is intentional.")
        elif travel_class == "business" and pax >= 5:
            flags.append(f"ℹ️ Business class for {pax} passengers — this will be a significant expense.")

        if pax > 6:
            flags.append(f"ℹ️ Large group booking ({pax} passengers). You may want to contact us directly for group rates.")

        # ── One-way long haul ─────────────────────────────────────────────────────
        _LONG_HAUL = {"LHR", "CDG", "AMS", "FRA", "JFK", "LAX", "SFO", "SYD", "MEL", "SIN", "HKG", "NRT", "ICN"}
        if "one" in trip_type and origin in _LONG_HAUL and destination in _LONG_HAUL:
            flags.append("ℹ️ One-way long-haul flight. If you plan to return, a round-trip ticket might save money.")

        # ── Travel entry requirements ─────────────────────────────────────────────
        travel_reqs = []
        try:
            req_tool = TravelRequirementsTool()
            req_result = json.loads(req_tool._run(json.dumps({
                "origin": origin,
                "destination": destination,
                "trip_type": trip_type,
            })))
            travel_reqs = req_result.get("requirements") or []
        except Exception:
            pass

        # Separate critical requirements from info/warnings
        critical_reqs = [r for r in travel_reqs if r.get("severity") == "critical"]
        other_reqs = [r for r in travel_reqs if r.get("severity") != "critical"]

        # ── Build natural language summary ────────────────────────────────────────
        class_label = {
            "economy": "Economy", "business": "Business", "first": "First Class",
            "premium_economy": "Premium Economy",
        }.get(travel_class, travel_class.title())

        pax_label = f"{pax} passenger{'s' if pax > 1 else ''}"
        trip_label = "Round Trip" if "return" in trip_type else "One-Way"

        if departure_date_str:
            try:
                d = datetime.strptime(departure_date_str, "%Y-%m-%d")
                dep_label = d.strftime("%A, %d %B %Y")
            except Exception:
                dep_label = departure_date_str
        else:
            dep_label = "date TBC"

        summary = (
            f"{trip_label} | {origin} -> {destination} | {dep_label} | "
            f"{pax_label} | {class_label}"
        )
        if return_date_str and "return" in trip_type:
            try:
                rd = datetime.strptime(return_date_str, "%Y-%m-%d")
                summary += f" | Return: {rd.strftime('%d %B %Y')}"
            except Exception:
                pass

        # ── Confidence score ──────────────────────────────────────────────────────
        critical_flags = [f for f in flags if f.startswith("⚠️")]
        # Critical travel requirements (visa etc.) also lower confidence
        if critical_reqs:
            critical_flags.append("travel_req")
        confidence = "high" if not critical_flags else ("medium" if len(critical_flags) == 1 else "low")

        return json.dumps({
            "confidence": confidence,
            "flags": flags,
            "summary": summary,
            "travel_requirements": travel_reqs,
            "critical_requirements": critical_reqs,
        })

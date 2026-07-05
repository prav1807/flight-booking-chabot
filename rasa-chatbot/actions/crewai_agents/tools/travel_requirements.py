"""
Phase 3 — Travel Requirements Tool

Checks travel entry requirements based on origin country + destination.
Uses a curated knowledge base — no external API needed.

Flags things like:
- US visa / ESTA requirement
- Schengen short-stay limit (90/180 days)
- UK visa requirements
- Proof of onward travel (one-way to strict countries)
- Accommodation address required at border (USA, Australia)
"""
import json
from crewai.tools import BaseTool

# ── IATA code → country mapping ───────────────────────────────────────────────
_IATA_TO_COUNTRY = {
    # Mauritius
    "MRU": "MU",
    # UK
    "LHR": "GB", "LGW": "GB", "LCY": "GB", "STN": "GB", "LTN": "GB",
    "MAN": "GB", "EDI": "GB", "GLA": "GB", "BHX": "GB", "BRS": "GB",
    # USA
    "JFK": "US", "EWR": "US", "LGA": "US", "LAX": "US", "SFO": "US",
    "ORD": "US", "MIA": "US", "ATL": "US", "DFW": "US", "SEA": "US",
    "DEN": "US", "BOS": "US", "IAD": "US", "SAN": "US", "PHX": "US",
    # Canada
    "YYZ": "CA", "YVR": "CA", "YUL": "CA", "YYC": "CA",
    # Australia
    "SYD": "AU", "MEL": "AU", "BNE": "AU", "PER": "AU",
    # New Zealand
    "AKL": "NZ", "CHC": "NZ",
    # Schengen (Germany, France, Netherlands, etc.)
    "FRA": "DE", "MUC": "DE", "BER": "DE", "DUS": "DE", "HAM": "DE",
    "CDG": "FR", "ORY": "FR", "NCE": "FR", "LYS": "FR",
    "AMS": "NL", "RTM": "NL",
    "MAD": "ES", "BCN": "ES",
    "FCO": "IT", "MXP": "IT", "NAP": "IT",
    "ZRH": "CH", "GVA": "CH",
    "VIE": "AT", "BRU": "BE", "LIS": "PT", "CPH": "DK",
    "ARN": "SE", "OSL": "NO", "HEL": "FI", "WAW": "PL",
    "PRG": "CZ", "BUD": "HU",
    # UAE
    "DXB": "AE", "AUH": "AE", "SHJ": "AE",
    # Asia
    "SIN": "SG", "KUL": "MY", "BKK": "TH", "HKG": "HK",
    "NRT": "JP", "HND": "JP", "ICN": "KR",
    "PEK": "CN", "PVG": "CN", "CAN": "CN",
    "DEL": "IN", "BOM": "IN", "BLR": "IN", "MAA": "IN",
    # Africa
    "JNB": "ZA", "CPT": "ZA", "DUR": "ZA",
    "NBO": "KE", "ADD": "ET", "ACC": "GH", "LOS": "NG",
    # Middle East
    "DOH": "QA", "KWI": "KW", "BAH": "BH", "AMM": "JO",
}

_SCHENGEN_COUNTRIES = {
    "DE", "FR", "NL", "ES", "IT", "PT", "BE", "AT", "CH", "DK",
    "SE", "NO", "FI", "PL", "CZ", "HU", "SK", "SI", "GR", "LU",
    "EE", "LV", "LT", "MT", "IS", "LI",
}

# ── Passport requirements: origin_country → destination → requirements ────────
# Format: list of dicts with: type, message, severity (info/warning/critical)
_REQUIREMENTS: dict = {
    # Mauritius passport holders
    "MU": {
        "US": [
            {"type": "visa", "severity": "critical",
             "message": "Mauritius passport holders need a valid US visa or ESTA to enter the USA. Have you obtained this?"},
            {"type": "address", "severity": "warning",
             "message": "US customs will ask for your address in the USA. Please have your hotel or host address ready."},
            {"type": "onward_travel", "severity": "info",
             "message": "For a one-way ticket, US immigration may ask about your onward travel plans."},
        ],
        "GB": [
            {"type": "visa", "severity": "critical",
             "message": "Mauritius passport holders need a valid UK visa to enter the UK since Brexit."},
        ],
        "CA": [
            {"type": "eta", "severity": "critical",
             "message": "Mauritius passport holders need a Canadian eTA (Electronic Travel Authorization) before boarding."},
        ],
        "AU": [
            {"type": "visa", "severity": "critical",
             "message": "Mauritius passport holders need an Australian tourist visa (subclass 600) or ETA before travelling."},
            {"type": "address", "severity": "warning",
             "message": "Australian border force will ask for your accommodation address in Australia."},
        ],
        "NZ": [
            {"type": "nzeta", "severity": "critical",
             "message": "Mauritius passport holders need a New Zealand NZeTA before boarding."},
        ],
        "SCHENGEN": [
            {"type": "visa_free", "severity": "info",
             "message": "Mauritius passport holders can enter the Schengen Area visa-free for up to 90 days in any 180-day period."},
            {"type": "etias", "severity": "warning",
             "message": "Note: The EU ETIAS (travel authorisation) system is expected to launch soon. Check the latest requirements before travel."},
        ],
    },
    # Default / generic checks applied to all trips
    "_default": {
        "US": [
            {"type": "address", "severity": "warning",
             "message": "US Customs will ask for a specific address in the USA. Please have your hotel or host address ready."},
        ],
        "AU": [
            {"type": "address", "severity": "warning",
             "message": "Australian border force will ask for your accommodation details."},
        ],
    },
}

# ── One-way trip warnings by destination ─────────────────────────────────────
_ONEWAY_WARNINGS = {
    "US": "One-way tickets to the USA can raise questions at immigration. Having proof of onward travel or return plans is strongly advised.",
    "GB": "UK immigration may ask about your return plans for a one-way ticket.",
    "AU": "Australian immigration officers often ask about return plans for one-way travellers.",
    "CA": "Canadian border services may ask for proof of onward travel for one-way tickets.",
}


class TravelRequirementsTool(BaseTool):
    name: str = "Travel Requirements Tool"
    description: str = (
        "Checks travel entry requirements (visa, ESTA, address, onward travel) "
        "based on the origin airport and destination airport. "
        "Input: JSON string with 'origin' (IATA code) and 'destination' (IATA code) "
        "and optionally 'trip_type' (one-way or return). "
        "Returns JSON with 'requirements' (list of requirement objects with type, severity, message)."
    )

    def _run(self, input_json: str) -> str:
        try:
            data = json.loads(input_json)
        except Exception:
            return json.dumps({"requirements": []})

        origin_iata = str(data.get("origin") or "").upper().strip()
        dest_iata = str(data.get("destination") or "").upper().strip()
        trip_type = str(data.get("trip_type") or "").lower()

        origin_country = _IATA_TO_COUNTRY.get(origin_iata)
        dest_country = _IATA_TO_COUNTRY.get(dest_iata)

        requirements = []

        # ── Passport-specific requirements ────────────────────────────────────
        if origin_country:
            passport_rules = _REQUIREMENTS.get(origin_country, {})

            # Check for Schengen destination
            if dest_country in _SCHENGEN_COUNTRIES:
                for req in passport_rules.get("SCHENGEN", []):
                    requirements.append(req)
            elif dest_country:
                for req in passport_rules.get(dest_country, []):
                    # Skip one-way warning if this is a return trip
                    if req["type"] == "onward_travel" and "return" in trip_type:
                        continue
                    requirements.append(req)

        # ── Default requirements — skip if already covered by passport rules ─────
        if dest_country:
            for req in _REQUIREMENTS.get("_default", {}).get(dest_country, []):
                # Avoid duplicates based on type
                if not any(r.get("type") == req["type"] for r in requirements):
                    requirements.append(req)

        # ── One-way specific warnings ─────────────────────────────────────────
        if "one" in trip_type and dest_country in _ONEWAY_WARNINGS:
            warn = _ONEWAY_WARNINGS[dest_country]
            if not any(r["message"] == warn for r in requirements):
                requirements.append({"type": "onward_travel", "severity": "warning", "message": warn})

        return json.dumps({
            "requirements": requirements,
            "origin_country": origin_country,
            "destination_country": dest_country,
        })

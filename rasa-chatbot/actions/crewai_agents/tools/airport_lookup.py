import json
from difflib import get_close_matches

from crewai.tools import BaseTool


# Comprehensive airport database — city/common name → IATA info
AIRPORT_DB: dict = {
    # UAE
    "dubai": {"code": "DXB", "name": "Dubai International Airport", "country": "UAE"},
    "abu dhabi": {"code": "AUH", "name": "Abu Dhabi International Airport", "country": "UAE"},
    "sharjah": {"code": "SHJ", "name": "Sharjah International Airport", "country": "UAE"},
    # UK
    "london": {"code": "LHR", "name": "London Heathrow Airport", "country": "UK"},
    "heathrow": {"code": "LHR", "name": "London Heathrow Airport", "country": "UK"},
    "gatwick": {"code": "LGW", "name": "London Gatwick Airport", "country": "UK"},
    "stansted": {"code": "STN", "name": "London Stansted Airport", "country": "UK"},
    "luton": {"code": "LTN", "name": "London Luton Airport", "country": "UK"},
    "manchester": {"code": "MAN", "name": "Manchester Airport", "country": "UK"},
    "birmingham": {"code": "BHX", "name": "Birmingham Airport", "country": "UK"},
    "edinburgh": {"code": "EDI", "name": "Edinburgh Airport", "country": "UK"},
    "glasgow": {"code": "GLA", "name": "Glasgow Airport", "country": "UK"},
    # France
    "paris": {"code": "CDG", "name": "Charles de Gaulle Airport", "country": "France"},
    "nice": {"code": "NCE", "name": "Nice Côte d'Azur Airport", "country": "France"},
    "lyon": {"code": "LYS", "name": "Lyon-Saint Exupéry Airport", "country": "France"},
    # USA
    "new york": {"code": "JFK", "name": "John F. Kennedy International Airport", "country": "USA"},
    "los angeles": {"code": "LAX", "name": "Los Angeles International Airport", "country": "USA"},
    "chicago": {"code": "ORD", "name": "O'Hare International Airport", "country": "USA"},
    "miami": {"code": "MIA", "name": "Miami International Airport", "country": "USA"},
    "san francisco": {"code": "SFO", "name": "San Francisco International Airport", "country": "USA"},
    "boston": {"code": "BOS", "name": "Logan International Airport", "country": "USA"},
    "dallas": {"code": "DFW", "name": "Dallas/Fort Worth International Airport", "country": "USA"},
    "atlanta": {"code": "ATL", "name": "Hartsfield-Jackson Atlanta International Airport", "country": "USA"},
    "seattle": {"code": "SEA", "name": "Seattle-Tacoma International Airport", "country": "USA"},
    "washington": {"code": "IAD", "name": "Dulles International Airport", "country": "USA"},
    # India
    "mumbai": {"code": "BOM", "name": "Chhatrapati Shivaji Maharaj International Airport", "country": "India"},
    "delhi": {"code": "DEL", "name": "Indira Gandhi International Airport", "country": "India"},
    "new delhi": {"code": "DEL", "name": "Indira Gandhi International Airport", "country": "India"},
    "bangalore": {"code": "BLR", "name": "Kempegowda International Airport", "country": "India"},
    "bengaluru": {"code": "BLR", "name": "Kempegowda International Airport", "country": "India"},
    "chennai": {"code": "MAA", "name": "Chennai International Airport", "country": "India"},
    "hyderabad": {"code": "HYD", "name": "Rajiv Gandhi International Airport", "country": "India"},
    "kolkata": {"code": "CCU", "name": "Netaji Subhas Chandra Bose International Airport", "country": "India"},
    # Middle East
    "doha": {"code": "DOH", "name": "Hamad International Airport", "country": "Qatar"},
    "riyadh": {"code": "RUH", "name": "King Khalid International Airport", "country": "Saudi Arabia"},
    "jeddah": {"code": "JED", "name": "King Abdulaziz International Airport", "country": "Saudi Arabia"},
    "kuwait": {"code": "KWI", "name": "Kuwait International Airport", "country": "Kuwait"},
    "muscat": {"code": "MCT", "name": "Muscat International Airport", "country": "Oman"},
    "bahrain": {"code": "BAH", "name": "Bahrain International Airport", "country": "Bahrain"},
    "amman": {"code": "AMM", "name": "Queen Alia International Airport", "country": "Jordan"},
    "beirut": {"code": "BEY", "name": "Rafic Hariri International Airport", "country": "Lebanon"},
    # Africa
    "cairo": {"code": "CAI", "name": "Cairo International Airport", "country": "Egypt"},
    "nairobi": {"code": "NBO", "name": "Jomo Kenyatta International Airport", "country": "Kenya"},
    "johannesburg": {"code": "JNB", "name": "OR Tambo International Airport", "country": "South Africa"},
    "cape town": {"code": "CPT", "name": "Cape Town International Airport", "country": "South Africa"},
    "lagos": {"code": "LOS", "name": "Murtala Muhammed International Airport", "country": "Nigeria"},
    "accra": {"code": "ACC", "name": "Kotoka International Airport", "country": "Ghana"},
    # Asia-Pacific
    "singapore": {"code": "SIN", "name": "Changi Airport", "country": "Singapore"},
    "tokyo": {"code": "NRT", "name": "Narita International Airport", "country": "Japan"},
    "osaka": {"code": "KIX", "name": "Kansai International Airport", "country": "Japan"},
    "sydney": {"code": "SYD", "name": "Sydney Kingsford Smith Airport", "country": "Australia"},
    "melbourne": {"code": "MEL", "name": "Melbourne Airport", "country": "Australia"},
    "auckland": {"code": "AKL", "name": "Auckland Airport", "country": "New Zealand"},
    "toronto": {"code": "YYZ", "name": "Toronto Pearson International Airport", "country": "Canada"},
    "vancouver": {"code": "YVR", "name": "Vancouver International Airport", "country": "Canada"},
    "montreal": {"code": "YUL", "name": "Montréal-Trudeau International Airport", "country": "Canada"},
    "amsterdam": {"code": "AMS", "name": "Amsterdam Airport Schiphol", "country": "Netherlands"},
    "frankfurt": {"code": "FRA", "name": "Frankfurt Airport", "country": "Germany"},
    "berlin": {"code": "BER", "name": "Berlin Brandenburg Airport", "country": "Germany"},
    "munich": {"code": "MUC", "name": "Munich Airport", "country": "Germany"},
    "zurich": {"code": "ZRH", "name": "Zurich Airport", "country": "Switzerland"},
    "istanbul": {"code": "IST", "name": "Istanbul Airport", "country": "Turkey"},
    "rome": {"code": "FCO", "name": "Leonardo da Vinci International Airport", "country": "Italy"},
    "milan": {"code": "MXP", "name": "Milan Malpensa Airport", "country": "Italy"},
    "madrid": {"code": "MAD", "name": "Adolfo Suárez Madrid-Barajas Airport", "country": "Spain"},
    "barcelona": {"code": "BCN", "name": "Barcelona El Prat Airport", "country": "Spain"},
    "lisbon": {"code": "LIS", "name": "Humberto Delgado Airport", "country": "Portugal"},
    "brussels": {"code": "BRU", "name": "Brussels Airport", "country": "Belgium"},
    "vienna": {"code": "VIE", "name": "Vienna International Airport", "country": "Austria"},
    "warsaw": {"code": "WAW", "name": "Warsaw Chopin Airport", "country": "Poland"},
    "bangkok": {"code": "BKK", "name": "Suvarnabhumi Airport", "country": "Thailand"},
    "kuala lumpur": {"code": "KUL", "name": "Kuala Lumpur International Airport", "country": "Malaysia"},
    "hong kong": {"code": "HKG", "name": "Hong Kong International Airport", "country": "Hong Kong"},
    "beijing": {"code": "PEK", "name": "Beijing Capital International Airport", "country": "China"},
    "shanghai": {"code": "PVG", "name": "Shanghai Pudong International Airport", "country": "China"},
    "guangzhou": {"code": "CAN", "name": "Guangzhou Baiyun International Airport", "country": "China"},
    "seoul": {"code": "ICN", "name": "Incheon International Airport", "country": "South Korea"},
    "jakarta": {"code": "CGK", "name": "Soekarno-Hatta International Airport", "country": "Indonesia"},
    "manila": {"code": "MNL", "name": "Ninoy Aquino International Airport", "country": "Philippines"},
    "colombo": {"code": "CMB", "name": "Bandaranaike International Airport", "country": "Sri Lanka"},
    "dhaka": {"code": "DAC", "name": "Hazrat Shahjalal International Airport", "country": "Bangladesh"},
    "kathmandu": {"code": "KTM", "name": "Tribhuvan International Airport", "country": "Nepal"},
    "karachi": {"code": "KHI", "name": "Jinnah International Airport", "country": "Pakistan"},
    "lahore": {"code": "LHE", "name": "Allama Iqbal International Airport", "country": "Pakistan"},
    "islamabad": {"code": "ISB", "name": "Islamabad International Airport", "country": "Pakistan"},
    # Island / leisure destinations
    "mauritius": {"code": "MRU", "name": "Sir Seewoosagur Ramgoolam International Airport", "country": "Mauritius"},
    "maldives": {"code": "MLE", "name": "Velana International Airport", "country": "Maldives"},
    "bali": {"code": "DPS", "name": "Ngurah Rai International Airport", "country": "Indonesia"},
    "phuket": {"code": "HKT", "name": "Phuket International Airport", "country": "Thailand"},
    "tenerife": {"code": "TFS", "name": "Tenerife South Airport", "country": "Spain"},
    "ibiza": {"code": "IBZ", "name": "Ibiza Airport", "country": "Spain"},
}

# Reverse lookup: IATA code → entry
IATA_MAP: dict = {v["code"]: {**v, "city": k} for k, v in AIRPORT_DB.items()}


class AirportLookupTool(BaseTool):
    name: str = "Airport Lookup Tool"
    description: str = (
        "Looks up IATA airport codes from city names or airport names. "
        "Input must be a JSON string with key 'query' containing the city or airport name. "
        "Returns a JSON object with 'found' (bool), 'code' (IATA code), 'name', 'country', "
        "and 'suggestions' (list of close matches when not an exact match)."
    )

    def _run(self, input_json: str) -> str:
        try:
            data = json.loads(input_json)
            query = str(data.get("query", "")).lower().strip()
        except (json.JSONDecodeError, AttributeError):
            query = str(input_json).lower().strip()

        if not query:
            return json.dumps({"found": False, "code": None, "name": None, "country": None, "suggestions": []})

        # Already a valid IATA code
        if len(query) == 3 and query.upper() in IATA_MAP:
            entry = IATA_MAP[query.upper()]
            return json.dumps({
                "found": True,
                "code": query.upper(),
                "name": entry["name"],
                "country": entry["country"],
                "suggestions": [],
            })

        # Exact city match
        if query in AIRPORT_DB:
            entry = AIRPORT_DB[query]
            return json.dumps({
                "found": True,
                "code": entry["code"],
                "name": entry["name"],
                "country": entry["country"],
                "suggestions": [],
            })

        # Fuzzy match against city names
        matches = get_close_matches(query, AIRPORT_DB.keys(), n=3, cutoff=0.6)
        if matches:
            best = matches[0]
            entry = AIRPORT_DB[best]
            suggestions = [
                {"city": m, "code": AIRPORT_DB[m]["code"], "name": AIRPORT_DB[m]["name"]}
                for m in matches
            ]
            return json.dumps({
                "found": True,
                "code": entry["code"],
                "name": entry["name"],
                "country": entry["country"],
                "suggestions": suggestions,
                "note": f"Matched '{query}' to '{best}' via fuzzy search.",
            })

        return json.dumps({
            "found": False,
            "code": None,
            "name": None,
            "country": None,
            "suggestions": [],
            "note": f"No airport found for '{query}'. Please verify the city or airport name.",
        })

import json

from crewai.tools import BaseTool


# Destination knowledge base organised by traveller intent/criteria
DESTINATIONS_BY_THEME: dict = {
    "warm": [
        {"city": "Dubai", "code": "DXB", "reason": "Year-round sunshine, 30°C+"},
        {"city": "Bangkok", "code": "BKK", "reason": "Tropical heat, vibrant culture"},
        {"city": "Bali", "code": "DPS", "reason": "Warm tropical island, stunning temples"},
        {"city": "Tenerife", "code": "TFS", "reason": "Warm year-round, popular sun destination"},
        {"city": "Phuket", "code": "HKT", "reason": "Warm beaches, turquoise water"},
        {"city": "Maldives", "code": "MLE", "reason": "Tropical paradise, always warm"},
    ],
    "beach": [
        {"city": "Maldives", "code": "MLE", "reason": "World-class overwater bungalows"},
        {"city": "Mauritius", "code": "MRU", "reason": "Stunning lagoons and white-sand beaches"},
        {"city": "Phuket", "code": "HKT", "reason": "Famous beaches and clear water"},
        {"city": "Bali", "code": "DPS", "reason": "Beautiful beaches and surf"},
        {"city": "Tenerife", "code": "TFS", "reason": "Black and golden sandy beaches"},
        {"city": "Miami", "code": "MIA", "reason": "South Beach, Art Deco, warm ocean"},
    ],
    "city": [
        {"city": "Paris", "code": "CDG", "reason": "Fashion, art, culture, and cuisine"},
        {"city": "Rome", "code": "FCO", "reason": "History, architecture, great food"},
        {"city": "Amsterdam", "code": "AMS", "reason": "Canals, museums, vibrant nightlife"},
        {"city": "Barcelona", "code": "BCN", "reason": "Gaudi, beaches, and tapas"},
        {"city": "Tokyo", "code": "NRT", "reason": "Unique blend of tradition and modernity"},
        {"city": "New York", "code": "JFK", "reason": "The city that never sleeps"},
    ],
    "city break": [
        {"city": "Paris", "code": "CDG", "reason": "Perfect 2-3 day romantic break"},
        {"city": "Amsterdam", "code": "AMS", "reason": "Compact, walkable, great for a weekend"},
        {"city": "Barcelona", "code": "BCN", "reason": "Sun, architecture, and great food"},
        {"city": "Lisbon", "code": "LIS", "reason": "Affordable European city with great food"},
        {"city": "Vienna", "code": "VIE", "reason": "Culture, music, and coffee houses"},
        {"city": "Istanbul", "code": "IST", "reason": "East-meets-West, unique and vibrant"},
    ],
    "cheap": [
        {"city": "Lisbon", "code": "LIS", "reason": "Affordable European destination"},
        {"city": "Warsaw", "code": "WAW", "reason": "Very budget-friendly European city"},
        {"city": "Istanbul", "code": "IST", "reason": "Affordable with a lot to see"},
        {"city": "Bangkok", "code": "BKK", "reason": "Very budget-friendly Southeast Asia hub"},
        {"city": "Riga", "code": "RIX", "reason": "One of Europe's most affordable capitals"},
        {"city": "Kuala Lumpur", "code": "KUL", "reason": "Great value Southeast Asian city"},
    ],
    "budget": [
        {"city": "Lisbon", "code": "LIS", "reason": "Low cost of living"},
        {"city": "Bangkok", "code": "BKK", "reason": "Extremely affordable"},
        {"city": "Warsaw", "code": "WAW", "reason": "Budget European capital"},
        {"city": "Istanbul", "code": "IST", "reason": "Great value for a major city"},
    ],
    "romantic": [
        {"city": "Paris", "code": "CDG", "reason": "The classic romantic city"},
        {"city": "Rome", "code": "FCO", "reason": "Candlelit dinners and ancient beauty"},
        {"city": "Maldives", "code": "MLE", "reason": "Private overwater villas"},
        {"city": "Venice", "code": "VCE", "reason": "Canals, gondolas, timeless romance"},
        {"city": "Santorini (Athens)", "code": "ATH", "reason": "Iconic sunsets and caldera views"},
        {"city": "Vienna", "code": "VIE", "reason": "Elegant, cultural, and intimate"},
    ],
    "adventure": [
        {"city": "Bali", "code": "DPS", "reason": "Surfing, hiking, volcanic landscapes"},
        {"city": "Kathmandu", "code": "KTM", "reason": "Gateway to Everest trekking"},
        {"city": "Cape Town", "code": "CPT", "reason": "Safaris, shark diving, mountains"},
        {"city": "Nairobi", "code": "NBO", "reason": "Safari hub, Masai Mara gateway"},
        {"city": "Sydney", "code": "SYD", "reason": "Outdoor activities, diving, hiking"},
        {"city": "Queenstown (Christchurch)", "code": "CHC", "reason": "Adventure sports capital"},
    ],
    "family": [
        {"city": "Dubai", "code": "DXB", "reason": "Theme parks, safe, great for kids"},
        {"city": "Singapore", "code": "SIN", "reason": "Universal Studios, clean and safe"},
        {"city": "Bangkok", "code": "BKK", "reason": "Exciting, affordable, kid-friendly"},
        {"city": "Tenerife", "code": "TFS", "reason": "Beaches, water parks, warm weather"},
        {"city": "Lisbon", "code": "LIS", "reason": "Safe, friendly, easy to navigate"},
    ],
    "luxury": [
        {"city": "Maldives", "code": "MLE", "reason": "Ultra-luxury overwater resorts"},
        {"city": "Dubai", "code": "DXB", "reason": "World-class hotels and experiences"},
        {"city": "Mauritius", "code": "MRU", "reason": "Exclusive beach resorts"},
        {"city": "Monaco (Nice)", "code": "NCE", "reason": "Grand Prix, casinos, superyachts"},
        {"city": "Tokyo", "code": "NRT", "reason": "Michelin-starred dining, luxury shopping"},
    ],
    "shopping": [
        {"city": "Dubai", "code": "DXB", "reason": "Massive malls, gold souk, tax-free"},
        {"city": "New York", "code": "JFK", "reason": "5th Avenue, SoHo, designer boutiques"},
        {"city": "London", "code": "LHR", "reason": "Oxford Street, Harrods, Carnaby Street"},
        {"city": "Hong Kong", "code": "HKG", "reason": "Electronics and fashion hub"},
        {"city": "Milan", "code": "MXP", "reason": "Fashion capital, Via Montenapoleone"},
        {"city": "Singapore", "code": "SIN", "reason": "Orchard Road, duty-free"},
    ],
    "culture": [
        {"city": "Rome", "code": "FCO", "reason": "Ancient history at every corner"},
        {"city": "Tokyo", "code": "NRT", "reason": "Unique Japanese culture and traditions"},
        {"city": "Cairo", "code": "CAI", "reason": "Pyramids, ancient Egyptian history"},
        {"city": "Istanbul", "code": "IST", "reason": "Roman, Byzantine, and Ottoman history"},
        {"city": "Kyoto (Osaka)", "code": "KIX", "reason": "Traditional Japan, temples, geishas"},
        {"city": "Beijing", "code": "PEK", "reason": "Great Wall, Forbidden City"},
    ],
    "europe": [
        {"city": "Paris", "code": "CDG", "reason": "Classic European destination"},
        {"city": "Rome", "code": "FCO", "reason": "History and cuisine"},
        {"city": "Amsterdam", "code": "AMS", "reason": "Canals and culture"},
        {"city": "Barcelona", "code": "BCN", "reason": "Sun and Gaudi"},
        {"city": "Vienna", "code": "VIE", "reason": "Music and imperial history"},
        {"city": "Lisbon", "code": "LIS", "reason": "Affordable and charming"},
    ],
    "asia": [
        {"city": "Singapore", "code": "SIN", "reason": "Modern, clean, multicultural"},
        {"city": "Tokyo", "code": "NRT", "reason": "Unique culture and cuisine"},
        {"city": "Bangkok", "code": "BKK", "reason": "Temples, food, nightlife"},
        {"city": "Bali", "code": "DPS", "reason": "Spiritual and beautiful"},
        {"city": "Hong Kong", "code": "HKG", "reason": "Skyline, food, and shopping"},
    ],
    "africa": [
        {"city": "Cape Town", "code": "CPT", "reason": "Stunning landscapes, wine, safaris"},
        {"city": "Nairobi", "code": "NBO", "reason": "Wildlife and safari hub"},
        {"city": "Marrakech (Casablanca)", "code": "CMN", "reason": "Exotic, colourful, ancient medina"},
        {"city": "Cairo", "code": "CAI", "reason": "Pyramids and ancient history"},
    ],
    "middle east": [
        {"city": "Dubai", "code": "DXB", "reason": "Ultra-modern, luxury, and desert experiences"},
        {"city": "Doha", "code": "DOH", "reason": "Modern skyline, cultural gems"},
        {"city": "Abu Dhabi", "code": "AUH", "reason": "Sheikh Zayed mosque, F1, heritage"},
        {"city": "Muscat", "code": "MCT", "reason": "Hidden gem, peaceful and beautiful"},
    ],
}


class DestinationSuggestionTool(BaseTool):
    name: str = "Destination Suggestion Tool"
    description: str = (
        "Suggests specific travel destinations based on vague criteria like 'warm', 'beach', "
        "'cheap', 'city break', 'romantic', 'adventure', or region names like 'Europe' or 'Asia'. "
        "Input must be a JSON string with 'criteria' (the vague destination description). "
        "Returns JSON with 'found' (bool), 'suggestions' (list of destinations with IATA codes), "
        "and 'message' (a human-readable suggestion string)."
    )

    def _run(self, input_json: str) -> str:
        try:
            data = json.loads(input_json)
            criteria = str(data.get("criteria", "")).lower().strip()
        except (json.JSONDecodeError, AttributeError):
            criteria = str(input_json).lower().strip()

        if not criteria:
            return json.dumps({"found": False, "suggestions": [], "message": "No criteria provided."})

        matched_destinations = []

        # Check each theme for keyword overlap
        for theme, destinations in DESTINATIONS_BY_THEME.items():
            if theme in criteria or any(word in criteria for word in theme.split()):
                for dest in destinations:
                    if dest not in matched_destinations:
                        matched_destinations.append(dest)

        # Deduplicate by code
        seen_codes = set()
        unique = []
        for d in matched_destinations:
            if d["code"] not in seen_codes:
                seen_codes.add(d["code"])
                unique.append(d)
        unique = unique[:6]  # cap at 6 suggestions

        if not unique:
            return json.dumps({
                "found": False,
                "suggestions": [],
                "message": (
                    f"I couldn't match '{criteria}' to a specific destination category. "
                    "Please ask the user to name a specific city or country."
                ),
            })

        lines = [f"- {d['city']} ({d['code']}): {d['reason']}" for d in unique]
        message = (
            f"Based on '{criteria}', here are some great options:\n" + "\n".join(lines) +
            "\n\nWhich destination would you like to fly to?"
        )

        return json.dumps({"found": True, "suggestions": unique, "message": message})

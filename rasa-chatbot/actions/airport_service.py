class AirportService:

    AIRPORTS = {
        "dubai": [
            {"code": "DXB", "name": "Dubai International Airport"},
            {"code": "DWC", "name": "Al Maktoum International Airport"},
        ],
        "london": [
            {"code": "LHR", "name": "London Heathrow Airport"},
            {"code": "LGW", "name": "London Gatwick Airport"},
            {"code": "STN", "name": "London Stansted Airport"},
            {"code": "LTN", "name": "London Luton Airport"},
        ],
        "mauritius": [
            {"code": "MRU", "name": "Sir Seewoosagur Ramgoolam International Airport"},
        ],
        "paris": [
            {"code": "CDG", "name": "Charles de Gaulle Airport"},
            {"code": "ORY", "name": "Paris Orly Airport"},
        ],
        "new york": [
            {"code": "JFK", "name": "John F. Kennedy International Airport"},
            {"code": "EWR", "name": "Newark Liberty International Airport"},
            {"code": "LGA", "name": "LaGuardia Airport"},
        ],
    }

    @classmethod
    def get_airports_for_city(cls, city):
        city_key = str(city or "").lower().strip()
        return cls.AIRPORTS.get(city_key, [])

    @classmethod
    def has_multiple_airports(cls, city):
        return len(cls.get_airports_for_city(city)) > 1

    @classmethod
    def get_default_airport_code(cls, city):
        airports = cls.get_airports_for_city(city)

        if not airports:
            return str(city or "").upper()

        return airports[0]["code"]

    @classmethod
    def format_airport_options(cls, city):
        airports = cls.get_airports_for_city(city)

        if not airports:
            return None

        message = f"{city} has multiple airport options:\n\n"

        for index, airport in enumerate(airports, start=1):
            message += f"{index}. {airport['name']} ({airport['code']})\n"

        message += "\nPlease choose the airport code you prefer."

        return message
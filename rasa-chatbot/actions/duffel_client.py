import os
from datetime import datetime, timedelta
from typing import Any, Dict, List

import httpx
from dotenv import load_dotenv

from .normalisation_service import NormalizationService

load_dotenv(dotenv_path="../.env")


class DuffelClient:
    def __init__(self) -> None:
        self.base_url = os.getenv("DUFFEL_BASE_URL", "https://api.duffel.com")
        self.token = os.getenv("DUFFEL_ACCESS_TOKEN")

        if not self.token:
            raise ValueError("DUFFEL_ACCESS_TOKEN is missing from .env")

        self.headers = {
            "Authorization": f"Bearer {self.token}",
            "Duffel-Version": "v2",
            "Content-Type": "application/json",
        }

    def create_offer_request(
        self,
        origin: str,
        destination: str,
        departure_date: str,
        passengers_count: int,
        cabin_class: str,
        return_date: str = None,
    ) -> List[Dict[str, Any]]:

        origin_code = NormalizationService.normalize_airport(origin)
        destination_code = NormalizationService.normalize_airport(destination)

        slices = [
            {
                "origin": origin_code,
                "destination": destination_code,
                "departure_date": NormalizationService.normalize_date(departure_date),
            }
        ]

        if return_date:
            slices.append(
                {
                    "origin": destination_code,
                    "destination": origin_code,
                    "departure_date": NormalizationService.normalize_date(return_date),
                }
            )

        payload = {
            "data": {
                "slices": slices,
                "passengers": [{"type": "adult"} for _ in range(passengers_count)],
                "cabin_class": NormalizationService.normalize_cabin_class(cabin_class),
            }
        }

        response = httpx.post(
            f"{self.base_url}/air/offer_requests",
            headers=self.headers,
            json=payload,
            timeout=60,
        )

        response.raise_for_status()
        data = response.json()["data"]

        return data.get("offers", [])

    def map_city_to_airport(self, value: str) -> str:
        mapping = {
            "dubai": "DXB",
            "london": "LHR",
            "mauritius": "MRU",
            "paris": "CDG",
            "new york": "JFK",
        }

        value_clean = str(value).lower().strip()
        return mapping.get(value_clean, value.upper())

    def normalize_cabin_class(self, value: str) -> str:
        text = str(value).lower().strip()

        if "business" in text:
            return "business"
        if "premium" in text:
            return "premium_economy"
        if "first" in text:
            return "first"
        return "economy"

    def normalize_date(self, value: str) -> str:
        text = str(value).lower().strip()

        if text == "next friday":
            today = datetime.today()
            days_ahead = 4 - today.weekday()
            if days_ahead <= 0:
                days_ahead += 7
            return (today + timedelta(days=days_ahead)).strftime("%Y-%m-%d")

        # Temporary fallback. Later we’ll improve date parsing.
        return text
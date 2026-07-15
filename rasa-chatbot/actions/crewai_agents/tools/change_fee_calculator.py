"""
Change Fee Calculator Tool — deterministic fare/fee calculation for the
"Change Booking" flow (see docs/AVIATION_CHATBOT_ARCHITECTURE.md and the
"Change Booking Agent" section of Aviation-Bot.txt).

This is intentionally rule-based, not LLM-based: the airline's change fee
schedule is business policy, and the fare difference is a hard number, not
something an LLM should approximate or negotiate. The CrewAI "Change
Booking Agent" only explains this result in natural language — it never
computes or overrides it.
"""

import json
from datetime import datetime, date

from crewai.tools import BaseTool

# Flat change fee per cabin class (business rule placeholder — replace with
# the airline's real fare-rule engine / Duffel order-change pricing).
_FLAT_CHANGE_FEE = {
    "economy": 75.0,
    "premium_economy": 125.0,
    "premium economy": 125.0,
    "business": 250.0,
    "first": 400.0,
}

_CURRENCY_DEFAULT = "GBP"


class ChangeFeeCalculatorTool(BaseTool):
    name: str = "Change Fee Calculator Tool"
    description: str = (
        "Calculates the total cost of changing a flight's departure date. "
        "Input: JSON string with keys: travel_class, original_price, currency, "
        "new_offer_price (optional — the price of the new date's cheapest "
        "equivalent fare, if already looked up). "
        "Returns JSON with: flat_fee, fare_difference, total_change_cost, currency."
    )

    def _run(self, input_json: str) -> str:
        try:
            data = json.loads(input_json)
        except (json.JSONDecodeError, TypeError):
            return json.dumps({"error": "Invalid input. Provide a JSON string."})

        travel_class = str(data.get("travel_class") or "economy").lower().strip()
        currency = data.get("currency") or _CURRENCY_DEFAULT

        flat_fee = _FLAT_CHANGE_FEE.get(travel_class, _FLAT_CHANGE_FEE["economy"])

        fare_difference = 0.0
        try:
            original_price = float(data.get("original_price") or 0)
            new_offer_price = data.get("new_offer_price")
            if new_offer_price is not None:
                fare_difference = round(float(new_offer_price) - original_price, 2)
        except (TypeError, ValueError):
            fare_difference = 0.0

        # Never let a "cheaper new date" result in a negative charge here —
        # refunding fare differences is a separate, policy-gated process.
        fare_difference = max(fare_difference, 0.0)

        total_change_cost = round(flat_fee + fare_difference, 2)

        return json.dumps({
            "flat_fee": flat_fee,
            "fare_difference": fare_difference,
            "total_change_cost": total_change_cost,
            "currency": currency,
        })

    @staticmethod
    def days_until(target_date_str: str) -> int:
        """Utility for policy checks: days between today and a YYYY-MM-DD date."""
        try:
            target = datetime.strptime(target_date_str, "%Y-%m-%d").date()
            return (target - date.today()).days
        except (TypeError, ValueError):
            return -1

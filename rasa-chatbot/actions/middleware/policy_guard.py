"""
Policy Guard — validates that a requested action complies with business
rules and regulations BEFORE it is allowed to reach an external API
(Duffel, Supabase) or be executed.

This is intentionally rule-based (no LLM) so that its decisions are
deterministic, auditable, and cannot be talked out of by a crafted user
message. CrewAI agents may still add richer natural-language explanations
around a rejection, but they can never override an "approved: False".
"""

from datetime import datetime, date
from typing import Any, Dict, Optional

MIN_PASSENGERS = 1
MAX_PASSENGERS = 9

VALID_TRAVEL_CLASSES = {"economy", "premium economy", "premium_economy", "business", "first"}
VALID_TRIP_TYPES = {"one-way", "one_way", "oneway", "return", "round-trip", "round_trip"}


class PolicyGuard:
    """Rule-based approval engine for booking-related actions."""

    def check(self, action: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Dispatches to the relevant rule-set for the given action.

        Returns: {"approved": True} or {"approved": False, "reason": "..."}
        """
        handler = getattr(self, f"_check_{action}", None)
        if handler is None:
            # Unknown action names are neither approved nor rejected blindly —
            # fail closed so nothing slips through unreviewed.
            return {"approved": False, "reason": f"Unknown policy action '{action}'."}
        return handler(context)

    # ------------------------------------------------------------------ #
    # Rule sets
    # ------------------------------------------------------------------ #

    def _check_search_flight(self, context: Dict[str, Any]) -> Dict[str, Any]:
        return self._check_common_trip_fields(context)

    def _check_create_booking(self, context: Dict[str, Any]) -> Dict[str, Any]:
        common = self._check_common_trip_fields(context)
        if not common["approved"]:
            return common

        if not context.get("passenger_full_name"):
            return {"approved": False, "reason": "Passenger full name is required."}
        if not context.get("passenger_email"):
            return {"approved": False, "reason": "Passenger email is required."}
        if not context.get("selected_duffel_offer_id") and not context.get("offer_id"):
            return {"approved": False, "reason": "No flight offer selected."}

        return {"approved": True}

    def _check_change_booking(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Rule-set for the 'Change Booking' flow
        (see docs/AVIATION_CHATBOT_ARCHITECTURE.md section 8).
        """
        if not context.get("booking_reference"):
            return {"approved": False, "reason": "A booking reference is required to change a booking."}
        if context.get("fare_is_non_changeable"):
            return {"approved": False, "reason": "This ticket's fare rules do not allow changes."}

        new_departure_date = context.get("new_departure_date")
        new_dep_parsed = self._parse_date(new_departure_date)
        if new_departure_date and new_dep_parsed is None:
            return {
                "approved": False,
                "reason": f"'{new_departure_date}' is not a valid date.",
            }
        if new_dep_parsed and new_dep_parsed < date.today():
            return {"approved": False, "reason": "The new departure date cannot be in the past."}

        old_departure_date = context.get("old_departure_date")
        old_dep_parsed = self._parse_date(old_departure_date)
        if new_dep_parsed and old_dep_parsed and new_dep_parsed == old_dep_parsed:
            return {
                "approved": False,
                "reason": "The new departure date is the same as the current one.",
            }

        return {"approved": True}

    # ------------------------------------------------------------------ #
    # Shared field-level rules
    # ------------------------------------------------------------------ #

    def _check_common_trip_fields(self, context: Dict[str, Any]) -> Dict[str, Any]:
        origin = context.get("origin")
        destination = context.get("destination")
        departure_date = context.get("departure_date")
        return_date = context.get("return_date")
        trip_type = str(context.get("trip_type") or "one-way").lower().strip()
        passengers = context.get("passengers")
        travel_class = context.get("travel_class")

        if origin and destination and str(origin).upper().strip() == str(destination).upper().strip():
            return {"approved": False, "reason": "Origin and destination cannot be the same."}

        dep_parsed = self._parse_date(departure_date)
        if departure_date and dep_parsed is None:
            return {"approved": False, "reason": f"Departure date '{departure_date}' is not a valid date."}
        if dep_parsed and dep_parsed < date.today():
            return {"approved": False, "reason": "Departure date cannot be in the past."}

        if trip_type in {"return", "round-trip", "round_trip"}:
            ret_parsed = self._parse_date(return_date)
            if return_date and ret_parsed is None:
                return {"approved": False, "reason": f"Return date '{return_date}' is not a valid date."}
            if dep_parsed and ret_parsed and ret_parsed <= dep_parsed:
                return {"approved": False, "reason": "Return date must be after the departure date."}

        if passengers is not None:
            try:
                passengers_int = int(passengers)
            except (TypeError, ValueError):
                return {"approved": False, "reason": f"Passenger count '{passengers}' is not a number."}
            if not (MIN_PASSENGERS <= passengers_int <= MAX_PASSENGERS):
                return {
                    "approved": False,
                    "reason": f"Passenger count must be between {MIN_PASSENGERS} and {MAX_PASSENGERS}.",
                }

        if travel_class and str(travel_class).lower().strip() not in VALID_TRAVEL_CLASSES:
            return {"approved": False, "reason": f"'{travel_class}' is not a recognised travel class."}

        return {"approved": True}

    @staticmethod
    def _parse_date(value: Optional[str]):
        if not value:
            return None
        value = str(value).strip()
        for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%d/%m/%Y", "%m/%d/%Y"):
            try:
                return datetime.strptime(value[:19], fmt).date()
            except ValueError:
                continue
        return None

"""
Identity Service — deterministic authentication for booking retrieval.

Never let an LLM decide whether a user is who they claim to be. This
service performs a straightforward, auditable check against the
booking record stored in Supabase: the booking reference must exist,
AND the supplied surname must match (case-insensitively) a name on the
booking's passenger_full_name field.

This is a lightweight verification suitable for a prototype. In
production this would be extended with OTP/email verification for
higher-value actions (e.g. before showing payment details).
"""

from typing import Any, Dict, Optional


class IdentityService:
    """Verifies a customer's right to access a specific booking record."""

    def __init__(self, supabase_client=None) -> None:
        self._supabase_client = supabase_client

    def _get_client(self):
        if self._supabase_client is not None:
            return self._supabase_client
        # Imported lazily so this module can be unit-tested without a
        # live Supabase connection / .env file present.
        from ..supabase_client import SupabaseClient

        return SupabaseClient().client

    def verify(self, booking_reference: str, surname: str) -> Dict[str, Any]:
        """
        Returns one of:
          {"authenticated": True, "booking": {...}}
          {"authenticated": False, "status": "BOOKING_NOT_FOUND"}
          {"authenticated": False, "status": "SURNAME_MISMATCH"}
          {"authenticated": False, "status": "ERROR", "reason": "..."}
        """
        if not booking_reference or not surname:
            return {
                "authenticated": False,
                "status": "MISSING_FIELDS",
                "reason": "Both booking reference and surname are required.",
            }

        try:
            response = (
                self._get_client()
                .table("bookings")
                .select("*")
                .eq("id", str(booking_reference).strip())
                .execute()
            )
        except Exception as e:
            return {"authenticated": False, "status": "ERROR", "reason": str(e)}

        if not response.data:
            return {"authenticated": False, "status": "BOOKING_NOT_FOUND"}

        booking = response.data[0]
        full_name = str(booking.get("passenger_full_name") or "").lower().strip()
        surname_normalised = str(surname).lower().strip()

        if not full_name or surname_normalised not in full_name.split():
            return {"authenticated": False, "status": "SURNAME_MISMATCH"}

        return {"authenticated": True, "booking": booking}

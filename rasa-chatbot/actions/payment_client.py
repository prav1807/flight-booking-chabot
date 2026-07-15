"""
Payment Client — deterministic wrapper around a payment gateway.

Per the architecture doc (docs/AVIATION_CHATBOT_ARCHITECTURE.md, section 4.5 /
"Payment Agent" in Aviation-Bot.txt): the LLM must NEVER see or handle card
data, and must never decide whether a payment succeeded. It only waits for a
payment-success event and reacts to it.

This class exposes a Stripe-Checkout-shaped interface:
  - create_checkout_session(amount, currency, reference) -> session dict
  - confirm_payment(session_id)                          -> marks paid (webhook stand-in)
  - get_session_status(session_id)                       -> current status

Today it runs in SIMULATED mode (in-memory session store, no external call),
which lets the full booking → payment → ticketing flow be exercised without
a live payment account. Swapping to real Stripe later means replacing the
three method bodies with `stripe.checkout.Session.create(...)` /
`stripe.checkout.Session.retrieve(...)` calls — no action/flow code changes
required, since callers only depend on this interface.
"""

import os
import threading
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

_LOCK = threading.Lock()


class PaymentClient:
    """Stripe-Checkout-shaped payment client. Simulated unless STRIPE_SECRET_KEY is set."""

    # Process-local session store, shared across instances (mirrors how a
    # real gateway would persist sessions server-side).
    _sessions: Dict[str, Dict[str, Any]] = {}

    def __init__(self) -> None:
        self.stripe_secret_key = os.getenv("STRIPE_SECRET_KEY")
        self.simulated = not bool(self.stripe_secret_key)

    def create_checkout_session(
        self, amount: Any, currency: str, booking_reference: str
    ) -> Dict[str, Any]:
        """
        Creates a checkout session for the given amount/currency.
        Returns: {"session_id": ..., "checkout_url": ..., "status": "pending"}
        """
        if not self.simulated:
            # Placeholder for a real integration:
            # import stripe
            # stripe.api_key = self.stripe_secret_key
            # session = stripe.checkout.Session.create(...)
            # return {"session_id": session.id, "checkout_url": session.url, "status": session.payment_status}
            raise NotImplementedError(
                "STRIPE_SECRET_KEY is set but real Stripe integration is not implemented yet."
            )

        session_id = f"sim_cs_{uuid.uuid4().hex[:20]}"
        session = {
            "session_id": session_id,
            "booking_reference": booking_reference,
            "amount": amount,
            "currency": currency,
            "status": "pending",
            "checkout_url": f"https://payments.simulated.local/checkout/{session_id}",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

        with _LOCK:
            self._sessions[session_id] = session

        return {
            "session_id": session_id,
            "checkout_url": session["checkout_url"],
            "status": session["status"],
        }

    def confirm_payment(self, session_id: str) -> Dict[str, Any]:
        """
        Simulates the payment-success webhook: marks a session as paid.
        In production this method would not exist — Stripe calls YOUR
        webhook endpoint instead. It's provided here purely so the
        conversational flow has something deterministic to trigger on
        when the (simulated) user says "I've paid".
        """
        with _LOCK:
            session = self._sessions.get(session_id)
            if not session:
                return {"status": "not_found"}
            session["status"] = "paid"
            session["paid_at"] = datetime.now(timezone.utc).isoformat()
            return {"status": "paid"}

    def get_session_status(self, session_id: str) -> Dict[str, Any]:
        """Returns the current status of a checkout session."""
        if not self.simulated:
            raise NotImplementedError(
                "STRIPE_SECRET_KEY is set but real Stripe integration is not implemented yet."
            )

        with _LOCK:
            session = self._sessions.get(session_id)

        if not session:
            return {"status": "not_found"}

        return {"status": session["status"], "session": session}

"""
PII Guard — masks personally identifiable information before it is shown
to the LLM (CrewAI agents) or displayed back to a user who has not been
fully re-verified for that specific field.

The guard is intentionally conservative: it masks the middle of a value
while keeping enough context (first/last characters) for a human to
recognise "yes, that's my email" without exposing the full value.
"""

import re
from typing import Any, Dict

EMAIL_RE = re.compile(r"^(.)(.*)(@.*)$")

# Fields that should always be masked when passed through the guard.
DEFAULT_SENSITIVE_FIELDS = {
    "passenger_email",
    "email",
    "passenger_phone",
    "phone",
    "passport",
    "passport_number",
    "credit_card",
    "card_number",
    "cvv",
}


class PIIGuard:
    """Masks sensitive fields in dicts before they leave a trusted boundary."""

    def mask(self, data: Dict[str, Any], fields: set = None) -> Dict[str, Any]:
        """
        Returns a shallow copy of `data` with sensitive fields masked.
        `fields` overrides the default sensitive-field set if provided.
        """
        sensitive_fields = fields if fields is not None else DEFAULT_SENSITIVE_FIELDS
        masked = dict(data)

        for key, value in data.items():
            if value is None:
                continue
            if key.lower() in sensitive_fields:
                masked[key] = self._mask_value(key.lower(), str(value))

        return masked

    def _mask_value(self, field_name: str, value: str) -> str:
        if "email" in field_name:
            return self.mask_email(value)
        if "phone" in field_name:
            return self.mask_phone(value)
        if "passport" in field_name:
            return self.mask_generic(value, keep_start=0, keep_end=4)
        if "card" in field_name or "cvv" in field_name:
            return self.mask_generic(value, keep_start=0, keep_end=4)
        return self.mask_generic(value, keep_start=1, keep_end=1)

    @staticmethod
    def mask_email(email: str) -> str:
        match = EMAIL_RE.match(email)
        if not match:
            return "***"
        first, _rest, domain = match.groups()
        return f"{first}***{domain}"

    @staticmethod
    def mask_phone(phone: str) -> str:
        digits_only = re.sub(r"\D", "", phone)
        if len(digits_only) <= 4:
            return "*" * len(phone)
        prefix = phone[: max(len(phone) - len(digits_only[-2:]) - 3, 0)]
        # Keep leading "+countrycode" (first 4-5 chars) and last 2 digits visible.
        visible_prefix = phone[:5] if phone.startswith("+") else phone[:2]
        return f"{visible_prefix}{'*' * max(len(phone) - len(visible_prefix) - 2, 3)}{phone[-2:]}"

    @staticmethod
    def mask_generic(value: str, keep_start: int = 1, keep_end: int = 1) -> str:
        if len(value) <= keep_start + keep_end:
            return "*" * len(value)
        start = value[:keep_start] if keep_start else ""
        end = value[-keep_end:] if keep_end else ""
        middle = "*" * (len(value) - keep_start - keep_end)
        return f"{start}{middle}{end}"

"""
Rate Limiter — protects the Duffel API (and our own action server) from
excessive or abusive use, e.g. a script hammering flight search or
repeatedly retrying failed identity verification.

Implemented as a simple in-memory sliding-window counter keyed by
sender_id + bucket name. This is process-local, which is sufficient for
a single action-server instance; for multi-instance deployments this
would be backed by Redis instead (same public interface).
"""

import threading
import time
from typing import Dict, Tuple

_LOCK = threading.Lock()


class RateLimiter:
    """In-memory sliding-window rate limiter."""

    # Shared across instances within the same process so limits persist
    # across separate Rasa action invocations for the same sender.
    _buckets: Dict[Tuple[str, str], list] = {}

    def __init__(
        self,
        max_searches_per_window: int = 10,
        max_failed_auth_per_window: int = 3,
        window_seconds: int = 60,
    ) -> None:
        self.max_searches_per_window = max_searches_per_window
        self.max_failed_auth_per_window = max_failed_auth_per_window
        self.window_seconds = window_seconds

    def _check(self, sender_id: str, bucket: str, limit: int) -> Dict[str, object]:
        key = (sender_id, bucket)
        now = time.time()

        with _LOCK:
            timestamps = self._buckets.get(key, [])
            # Drop timestamps outside the sliding window.
            timestamps = [t for t in timestamps if now - t < self.window_seconds]

            if len(timestamps) >= limit:
                self._buckets[key] = timestamps
                return {
                    "allowed": False,
                    "reason": f"Rate limit exceeded for '{bucket}' ({limit} per {self.window_seconds}s).",
                    "retry_after_seconds": round(self.window_seconds - (now - timestamps[0]), 1),
                }

            timestamps.append(now)
            self._buckets[key] = timestamps
            return {"allowed": True, "remaining": limit - len(timestamps)}

    def check_search(self, sender_id: str) -> Dict[str, object]:
        return self._check(sender_id, "flight_search", self.max_searches_per_window)

    def check_auth_attempt(self, sender_id: str) -> Dict[str, object]:
        return self._check(sender_id, "auth_attempt", self.max_failed_auth_per_window)

    def reset(self, sender_id: str, bucket: str = None) -> None:
        """Clears rate-limit history for a sender (e.g. after successful auth)."""
        with _LOCK:
            if bucket:
                self._buckets.pop((sender_id, bucket), None)
            else:
                for key in list(self._buckets.keys()):
                    if key[0] == sender_id:
                        self._buckets.pop(key, None)

"""
Ollama health check with short-lived cache.

Checks whether Ollama is reachable before attempting LLM calls.
Caches the result for 30 seconds to avoid pinging on every action.
"""
import time
from typing import Optional

try:
    import urllib.request
    import urllib.error
except ImportError:
    pass

_OLLAMA_BASE_URL = "http://localhost:11434"
_TIMEOUT_SECONDS = 2.0
_CACHE_TTL = 30  # seconds

_cache_result: Optional[bool] = None
_cache_time: float = 0.0


def is_ollama_running() -> bool:
    """
    Returns True if Ollama is reachable at localhost:11434.
    Result is cached for 30 seconds to avoid repeated network calls.
    """
    global _cache_result, _cache_time

    now = time.monotonic()
    if _cache_result is not None and (now - _cache_time) < _CACHE_TTL:
        return _cache_result

    try:
        req = urllib.request.urlopen(
            f"{_OLLAMA_BASE_URL}/api/tags",
            timeout=_TIMEOUT_SECONDS,
        )
        _cache_result = req.status == 200
    except Exception:
        _cache_result = False

    _cache_time = now
    return _cache_result


def invalidate_cache() -> None:
    """Force re-check on next call (use after startup or connection change)."""
    global _cache_result, _cache_time
    _cache_result = None
    _cache_time = 0.0

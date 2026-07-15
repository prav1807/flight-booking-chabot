"""
Audit Logger — records every significant decision, tool call, and customer
confirmation for traceability, compliance, and dispute resolution.

Writes structured JSON Lines (one JSON object per line) to a local log file.
This keeps the implementation dependency-free and works even when Supabase
or Ollama are unavailable. In production this could be swapped for a
Supabase table, an event broker, or a centralized logging service without
changing any call sites (they all go through `AuditLogger.log(...)`).
"""

import json
import os
import threading
from datetime import datetime, timezone
from typing import Any, Dict, Optional

_LOCK = threading.Lock()

# rasa-chatbot/actions/middleware/audit_logger.py -> rasa-chatbot/logs/audit.jsonl
_DEFAULT_LOG_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "logs",
)
_DEFAULT_LOG_FILE = os.path.join(_DEFAULT_LOG_DIR, "audit.jsonl")


class AuditLogger:
    """Structured, append-only logger for agent and action activity."""

    def __init__(self, log_file: Optional[str] = None) -> None:
        self.log_file = log_file or _DEFAULT_LOG_FILE
        os.makedirs(os.path.dirname(self.log_file), exist_ok=True)

    def log(
        self,
        agent: str,
        action: str,
        sender_id: Optional[str] = None,
        input_data: Optional[Dict[str, Any]] = None,
        output_data: Optional[Dict[str, Any]] = None,
        status: str = "success",
    ) -> Dict[str, Any]:
        """
        Record one audit event.

        Example:
            AuditLogger().log(
                agent="Input Validator",
                action="validate_dates",
                sender_id=tracker.sender_id,
                input_data={"departure_date": "2026-07-20"},
                output_data={"valid": False, "reason": "Return before departure"},
                status="rejected",
            )
        """
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "agent": agent,
            "action": action,
            "sender_id": sender_id,
            "status": status,
            "input": input_data or {},
            "output": output_data or {},
        }

        try:
            with _LOCK:
                with open(self.log_file, "a", encoding="utf-8") as f:
                    f.write(json.dumps(entry, default=str) + "\n")
        except OSError:
            # Never let logging failures break the conversation flow.
            pass

        return entry

    def read_recent(self, limit: int = 50) -> list:
        """Returns the most recent `limit` audit entries (best-effort, for debugging)."""
        if not os.path.exists(self.log_file):
            return []
        try:
            with open(self.log_file, "r", encoding="utf-8") as f:
                lines = f.readlines()[-limit:]
            return [json.loads(line) for line in lines if line.strip()]
        except OSError:
            return []

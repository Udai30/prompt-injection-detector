"""Per-UTC-day cap on live LLM-judge checks for the public demo (TRD §S7, DEMO_MODE)."""

from __future__ import annotations

import json
import threading
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path


def _today() -> str:
    return datetime.now(UTC).date().isoformat()


class DailyBudget:
    """Counts live checks per UTC day in a JSON file; thread-safe, fails closed on bad data."""

    def __init__(self, path: Path, limit: int, today: Callable[[], str] = _today) -> None:
        self._path = path
        self._limit = limit
        self._today = today
        self._lock = threading.Lock()

    def _used(self) -> int:
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
            return int(data["count"]) if data["day"] == self._today() else 0
        except FileNotFoundError:
            return 0
        except (OSError, ValueError, KeyError, TypeError):
            return self._limit  # unreadable state: refuse rather than overspend

    def try_acquire(self) -> bool:
        """Reserve one live check; False when today's budget is spent."""
        with self._lock:
            used = self._used()
            if used >= self._limit:
                return False
            self._path.parent.mkdir(parents=True, exist_ok=True)
            self._path.write_text(
                json.dumps({"day": self._today(), "count": used + 1}), encoding="utf-8"
            )
            return True

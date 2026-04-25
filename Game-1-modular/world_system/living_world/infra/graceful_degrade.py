"""Graceful-degrade logger (v4 P0 — CC3).

Structured logging contract for every graceful-degrade event across Living
World subsystems. Replaces ad-hoc ``print()`` fallbacks with typed entries
persisted to ``llm_debug_logs/graceful_degrade/``.

Every degrade event logs:

- ``subsystem``      — who degraded (e.g. "npc_agent", "backend_manager")
- ``operation``      — what was attempted (e.g. "generate_dialogue")
- ``failure_reason`` — why it failed (exception class + message)
- ``fallback_taken`` — what was done instead (e.g. "hardcoded dialogue")
- ``severity``       — ``info`` | ``warning`` | ``error``
- ``context``        — arbitrary JSON-serializable extras (npc_id, task, etc.)
- ``timestamp``      — wall-clock ISO
- ``game_time``      — optional game-time tick

Design rules (CC3):
- Silent ``try/except`` is not acceptable. Use :func:`log_degrade` on every
  fallback path.
- Logger never raises. If disk writes fail, it falls back to stderr.
- WES failures additionally call :func:`surface_visible_wes_failure` so
  the UI layer can render a persistent on-screen indicator.

This module has zero dependencies on WNS/WES runtime so it can be used
during boot before those systems exist.
"""

from __future__ import annotations

import json
import os
import sys
import threading
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


SEVERITY_INFO = "info"
SEVERITY_WARNING = "warning"
SEVERITY_ERROR = "error"
SEVERITY_CRITICAL = "critical"  # PLACEHOLDER §3 v1.0: distinct from error —
# critical means the subsystem CANNOT continue to function (DB corruption,
# missing required config, etc.). Surface sinks treat critical as a hard
# fail; error stays a soft fall-through.

_VALID_SEVERITIES = {
    SEVERITY_INFO,
    SEVERITY_WARNING,
    SEVERITY_ERROR,
    SEVERITY_CRITICAL,
}


@dataclass
class DegradeEntry:
    """One structured graceful-degrade event."""

    subsystem: str
    operation: str
    failure_reason: str
    fallback_taken: str
    severity: str = SEVERITY_WARNING
    context: Dict[str, Any] = field(default_factory=dict)
    timestamp_iso: str = ""             # populated at emit if empty
    game_time: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        # asdict handles dataclass; we want pure JSON-safe
        d["context"] = dict(self.context)
        return d


class GracefulDegradeLogger:
    """Singleton logger for graceful-degrade events.

    Writes each entry as JSON to
    ``<log_dir>/YYYY-MM-DDTHH-MM-SS_<subsystem>.json``.
    Also keeps an in-memory ring buffer (bounded) for test/dev inspection.
    """

    _instance: Optional["GracefulDegradeLogger"] = None
    _lock = threading.Lock()

    # Default log directory — relative to repo root. Consumers can override.
    DEFAULT_LOG_DIR = os.path.join("llm_debug_logs", "graceful_degrade")

    # In-memory buffer size for test inspection + quick dev console.
    # Override via env var WES_GRACEFUL_DEGRADE_MAX_BUFFER for prod tuning.
    # 256 is a dev-friendly default — recent enough to inspect after a
    # session, small enough not to swallow memory.
    MAX_BUFFER = int(os.environ.get("WES_GRACEFUL_DEGRADE_MAX_BUFFER", "256"))

    def __init__(self, log_dir: Optional[str] = None) -> None:
        self._log_dir = log_dir or self.DEFAULT_LOG_DIR
        self._buffer: List[DegradeEntry] = []
        self._surface_sinks: List = []   # callables receiving DegradeEntry
        self._write_lock = threading.Lock()

    @classmethod
    def get_instance(cls) -> "GracefulDegradeLogger":
        with cls._lock:
            if cls._instance is None:
                cls._instance = cls()
            return cls._instance

    @classmethod
    def reset(cls, log_dir: Optional[str] = None) -> "GracefulDegradeLogger":
        """Reset the singleton. Test helper."""
        with cls._lock:
            cls._instance = cls(log_dir=log_dir)
            return cls._instance

    # ── configuration ────────────────────────────────────────────────

    def set_log_dir(self, log_dir: str) -> None:
        """Change the output directory. Call once during boot."""
        with self._write_lock:
            self._log_dir = log_dir

    def register_surface_sink(self, sink) -> None:
        """Register a callable ``sink(entry: DegradeEntry) -> None`` that is
        invoked for every WES-severity-error entry. Used by the UI layer
        (see :func:`surface_visible_wes_failure` / CC3 on-screen indicator).

        Sinks should not raise. Failures in a sink are swallowed and reported
        via stderr (logger never raises back into the caller)."""
        self._surface_sinks.append(sink)

    # ── emission ─────────────────────────────────────────────────────

    def log(self, entry: DegradeEntry) -> None:
        """Record a degrade event. Never raises."""
        if entry.severity not in _VALID_SEVERITIES:
            entry.severity = SEVERITY_WARNING
        if not entry.timestamp_iso:
            entry.timestamp_iso = datetime.now(timezone.utc).isoformat()

        # Append to in-memory buffer
        with self._write_lock:
            self._buffer.append(entry)
            if len(self._buffer) > self.MAX_BUFFER:
                self._buffer = self._buffer[-self.MAX_BUFFER:]

        # Persist to disk
        try:
            self._persist(entry)
        except Exception as e:
            # Never raise — fall back to stderr
            sys.stderr.write(
                f"[graceful_degrade] disk write failed: {e}; "
                f"entry={entry.to_dict()}\n"
            )

        # Fan out to surface sinks for error-severity events
        if entry.severity == SEVERITY_ERROR:
            for sink in list(self._surface_sinks):
                try:
                    sink(entry)
                except Exception as e:
                    sys.stderr.write(
                        f"[graceful_degrade] surface sink error: {e}\n"
                    )

    def _persist(self, entry: DegradeEntry) -> None:
        os.makedirs(self._log_dir, exist_ok=True)
        # Filename = timestamp (safe) + subsystem
        safe_ts = entry.timestamp_iso.replace(":", "-").replace(".", "-")
        safe_subsystem = "".join(
            c if c.isalnum() or c in ("_", "-") else "_" for c in entry.subsystem
        )
        filename = f"{safe_ts}_{safe_subsystem}.json"
        path = os.path.join(self._log_dir, filename)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(entry.to_dict(), f, indent=2, sort_keys=True)

    # ── inspection ───────────────────────────────────────────────────

    def recent(self, n: int = 50) -> List[DegradeEntry]:
        """Return the most recent ``n`` entries from the in-memory buffer."""
        with self._write_lock:
            return list(self._buffer[-n:])

    def clear_buffer(self) -> None:
        """Test helper — clear the in-memory buffer."""
        with self._write_lock:
            self._buffer.clear()

    @property
    def log_dir(self) -> str:
        return self._log_dir


# ── Module-level convenience API ─────────────────────────────────────

def log_degrade(
    subsystem: str,
    operation: str,
    failure_reason: str,
    fallback_taken: str,
    severity: str = SEVERITY_WARNING,
    context: Optional[Dict[str, Any]] = None,
    game_time: Optional[float] = None,
) -> DegradeEntry:
    """Record a graceful-degrade event via the singleton logger.

    Returns the recorded entry so callers can chain additional metadata.

    Example::

        try:
            result = risky_call()
        except Exception as e:
            log_degrade(
                subsystem="npc_agent",
                operation="generate_dialogue",
                failure_reason=f"{type(e).__name__}: {e}",
                fallback_taken="hardcoded dialogue",
                severity="warning",
                context={"npc_id": npc_id, "task": "dialogue"},
            )
            return fallback_dialogue()
    """
    entry = DegradeEntry(
        subsystem=subsystem,
        operation=operation,
        failure_reason=failure_reason,
        fallback_taken=fallback_taken,
        severity=severity if severity in _VALID_SEVERITIES else SEVERITY_WARNING,
        context=dict(context or {}),
        game_time=game_time,
    )
    GracefulDegradeLogger.get_instance().log(entry)
    return entry


def surface_visible_wes_failure(
    operation: str,
    failure_reason: str,
    fallback_taken: str,
    context: Optional[Dict[str, Any]] = None,
    game_time: Optional[float] = None,
) -> DegradeEntry:
    """Record a WES failure at ``error`` severity.

    This always triggers registered surface sinks — the UI layer subscribes
    so a visible HUD indicator can appear (CC3). If no UI sink is
    registered, the entry still logs normally.
    """
    return log_degrade(
        subsystem="wes",
        operation=operation,
        failure_reason=failure_reason,
        fallback_taken=fallback_taken,
        severity=SEVERITY_ERROR,
        context=context,
        game_time=game_time,
    )


def get_graceful_degrade_logger() -> GracefulDegradeLogger:
    """Module-level accessor following project singleton pattern."""
    return GracefulDegradeLogger.get_instance()

"""Live runtime observability for the WMS→WNS→WES pipeline.

This is the *live* counterpart to :mod:`world_system.wes.observability`,
which writes per-plan JSON files to disk. The runtime module owns:

- An in-memory ring buffer of the last ~256 pipeline events. Useful for
  the game-engine debug overlay, the prompt studio's live tab, and
  post-mortem diagnosis when something goes wrong without a save file.
- A verbose stdout stream gated on the ``WES_VERBOSE`` environment
  variable. Truthy values (``1``, ``true``, ``yes``, ``on``) enable
  one-line tagged prints at every pipeline stage.
- Tier counters for at-a-glance stats (e.g., "WNS_FIRED: 12,
  WES_DISPATCHED: 4, RELOAD_OK: 4 / RELOAD_FAIL: 0").

Design rules:

- Never raises. Recording is best-effort — a failure to format an event
  must not break the pipeline. All exceptions inside ``record`` are
  swallowed with a single stderr line.
- Singleton pattern so call sites in WMS bridge / WNS weaver / WES
  orchestrator / ContentRegistry / database_reloader can share one ring
  buffer without passing it around as a parameter.
- Keys are short canonical event_type strings (``WMS_EVENT_RECEIVED``,
  ``WNS_FIRED``, ``WES_DISPATCHED``, ``REGISTRY_COMMITTED``,
  ``DB_RELOADED``, ...). The set is open — call sites can introduce new
  types and the buffer just stores them.
"""

from __future__ import annotations

import os
import sys
import threading
import time
from collections import Counter, deque
from dataclasses import dataclass, field
from typing import Any, ClassVar, Dict, List, Optional


# ── Canonical event types ─────────────────────────────────────────────────
# Shared vocabulary for the most common pipeline stages. Call sites are
# free to introduce new strings; these constants exist so consumers
# (overlay, prompt studio, tests) can refer to them by name.

EVT_WMS_EVENT_RECEIVED   = "WMS_EVENT_RECEIVED"      # noqa: E221
EVT_WMS_INTERPRETATION   = "WMS_INTERPRETATION_CREATED"  # noqa: E221
EVT_CASCADE_FIRED        = "CASCADE_FIRED"           # noqa: E221
EVT_WNS_FIRED            = "WNS_FIRED"               # noqa: E221
EVT_WNS_CALL_WES         = "WNS_CALL_WES_REQUESTED"  # noqa: E221
EVT_WES_DISPATCHED       = "WES_DISPATCHED"          # noqa: E221
EVT_WES_PLAN_STARTED     = "WES_PLAN_STARTED"        # noqa: E221
EVT_WES_PLAN_COMPLETED   = "WES_PLAN_COMPLETED"      # noqa: E221
EVT_WES_TOOL_RAN         = "WES_TOOL_RAN"            # noqa: E221
EVT_REGISTRY_STAGED      = "REGISTRY_STAGED"         # noqa: E221
EVT_REGISTRY_COMMITTED   = "REGISTRY_COMMITTED"      # noqa: E221
EVT_REGISTRY_ROLLED_BACK = "REGISTRY_ROLLED_BACK"    # noqa: E221
EVT_DB_RELOADED          = "DB_RELOADED"             # noqa: E221
EVT_DB_RELOAD_FAILED     = "DB_RELOAD_FAILED"        # noqa: E221


# ── Ring buffer entry ─────────────────────────────────────────────────────

@dataclass(frozen=True)
class PipelineEvent:
    """One observed pipeline stage."""
    timestamp: float                        # time.time() at record
    event_type: str                         # canonical EVT_* string
    message: str                            # human-readable summary
    fields: Dict[str, Any] = field(default_factory=dict)

    def format_oneline(self) -> str:
        """Render the event as one tagged line for stdout / overlay."""
        ts = time.strftime("%H:%M:%S", time.localtime(self.timestamp))
        ms = int((self.timestamp - int(self.timestamp)) * 1000)
        bits = [f"[{ts}.{ms:03d}]", f"[{self.event_type}]"]
        if self.message:
            bits.append(self.message)
        if self.fields:
            tail = " ".join(f"{k}={v}" for k, v in self.fields.items())
            bits.append(f"({tail})")
        return " ".join(bits)


# ── Env helpers ───────────────────────────────────────────────────────────

_TRUTHY = {"1", "true", "yes", "on"}


def _verbose_enabled() -> bool:
    """Read ``WES_VERBOSE`` env at call time so toggles work mid-session."""
    return os.environ.get("WES_VERBOSE", "").strip().lower() in _TRUTHY


# ── Singleton ─────────────────────────────────────────────────────────────

class RuntimeObservability:
    """Singleton in-memory ring buffer + counter store for pipeline events.

    Usage::

        obs = RuntimeObservability.get_instance()
        obs.record(EVT_WNS_FIRED, "NL2 weaver fired", layer=2, address="locality:hill")
        for evt in obs.recent(20):
            print(evt.format_oneline())
        snapshot = obs.stats()
    """

    _instance: ClassVar[Optional["RuntimeObservability"]] = None
    _instance_lock: ClassVar[threading.Lock] = threading.Lock()

    DEFAULT_BUFFER_SIZE: ClassVar[int] = 256

    def __init__(self, buffer_size: int = DEFAULT_BUFFER_SIZE) -> None:
        self._buffer: deque[PipelineEvent] = deque(maxlen=buffer_size)
        self._counters: Counter[str] = Counter()
        self._lock = threading.Lock()

    @classmethod
    def get_instance(cls) -> "RuntimeObservability":
        with cls._instance_lock:
            if cls._instance is None:
                cls._instance = RuntimeObservability()
            return cls._instance

    @classmethod
    def reset(cls) -> None:
        """Test helper — drop the singleton + buffer + counters."""
        with cls._instance_lock:
            cls._instance = None

    # ── Public API ──────────────────────────────────────────────────────

    def record(
        self,
        event_type: str,
        message: str = "",
        **fields: Any,
    ) -> None:
        """Record one pipeline event. Never raises.

        If ``WES_VERBOSE`` is set in the environment, also writes a tagged
        one-liner to stdout (so a game session captures the stream even
        without the in-game overlay open).
        """
        try:
            evt = PipelineEvent(
                timestamp=time.time(),
                event_type=event_type,
                message=message,
                fields=dict(fields),
            )
            with self._lock:
                self._buffer.append(evt)
                self._counters[event_type] += 1
            if _verbose_enabled():
                # Print to stdout. We deliberately don't use logging here
                # — the print contract is much simpler for terminal tail.
                print(evt.format_oneline())
        except Exception as e:  # pragma: no cover — defensive
            sys.stderr.write(
                f"[observability_runtime] record failed: {type(e).__name__}: {e}\n"
            )

    def recent(self, n: Optional[int] = None) -> List[PipelineEvent]:
        """Return the most-recent ``n`` events (oldest-first within slice).

        ``n=None`` returns the full buffer. The returned list is a snapshot;
        further records do not mutate it.
        """
        with self._lock:
            if n is None or n >= len(self._buffer):
                return list(self._buffer)
            return list(self._buffer)[-n:]

    def stats(self) -> Dict[str, Any]:
        """Return ``{event_type → count, _total: int, _buffer_size: int}``.

        Useful for the debug overlay's "at-a-glance" header.
        """
        with self._lock:
            counts = dict(self._counters)
            counts["_total"] = sum(self._counters.values())
            counts["_buffer_size"] = len(self._buffer)
            return counts

    def clear(self) -> None:
        """Drop the buffer + counters (keeps the singleton instance)."""
        with self._lock:
            self._buffer.clear()
            self._counters.clear()


# ── Convenience helpers (bind to the singleton) ──────────────────────────

def obs_record(event_type: str, message: str = "", **fields: Any) -> None:
    """Module-level convenience wrapper for the most common usage pattern.

    Equivalent to ``RuntimeObservability.get_instance().record(...)`` but
    one line shorter at every call site.
    """
    RuntimeObservability.get_instance().record(event_type, message, **fields)


def obs_recent(n: Optional[int] = None) -> List[PipelineEvent]:
    return RuntimeObservability.get_instance().recent(n)


def obs_stats() -> Dict[str, Any]:
    return RuntimeObservability.get_instance().stats()


def obs_clear() -> None:
    RuntimeObservability.get_instance().clear()


def obs_verbose_enabled() -> bool:
    """Public wrapper around the env-toggle check (game-engine UI uses it)."""
    return _verbose_enabled()


__all__ = [
    "EVT_WMS_EVENT_RECEIVED",
    "EVT_WMS_INTERPRETATION",
    "EVT_CASCADE_FIRED",
    "EVT_WNS_FIRED",
    "EVT_WNS_CALL_WES",
    "EVT_WES_DISPATCHED",
    "EVT_WES_PLAN_STARTED",
    "EVT_WES_PLAN_COMPLETED",
    "EVT_WES_TOOL_RAN",
    "EVT_REGISTRY_STAGED",
    "EVT_REGISTRY_COMMITTED",
    "EVT_REGISTRY_ROLLED_BACK",
    "EVT_DB_RELOADED",
    "EVT_DB_RELOAD_FAILED",
    "PipelineEvent",
    "RuntimeObservability",
    "obs_record",
    "obs_recent",
    "obs_stats",
    "obs_clear",
    "obs_verbose_enabled",
]

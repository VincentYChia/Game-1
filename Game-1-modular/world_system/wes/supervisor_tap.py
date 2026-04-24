"""Supervisor log-tap (v4 §5.6, CC1).

The supervisor is a cross-tier common-sense checker. Its input is the
full log trail from one plan pass; its output is a verdict + (optional)
rerun decision.

This module provides:

- :class:`SupervisorTap` — collects :class:`TierRunResult` as the
  dispatcher runs, so the supervisor can review the full pass without
  re-reading files from disk. The orchestrator registers one tap per
  plan pass and passes the tap's ``results`` into ``Supervisor.review``.
- :class:`StubSupervisor` — P5 stub that returns an always-pass verdict.
  Agent D will replace this with a real LLM-backed supervisor in P6.5.

Keeping the stub in the same module as the tap makes the fixture-driven
P5 end-to-end test trivial and keeps the supervisor contract visible
as one unit.
"""

from __future__ import annotations

import threading
import time
from typing import TYPE_CHECKING, Any, Dict, List

from world_system.wes.dataclasses import TierRunResult

if TYPE_CHECKING:  # pragma: no cover - typing only
    from world_system.living_world.infra.context_bundle import (
        WESContextBundle,
    )
    from world_system.wes.dataclasses import WESPlan


class SupervisorTap:
    """Collects tier results for supervisor review.

    Thread-safe by design — the dispatcher fans out executor_tool calls
    in parallel, and each parallel worker may append its result
    concurrently.
    """

    def __init__(self) -> None:
        self._results: List[TierRunResult] = []
        self._lock = threading.Lock()

    def record(self, result: TierRunResult) -> None:
        """Append a tier result. Thread-safe."""
        with self._lock:
            self._results.append(result)

    @property
    def results(self) -> List[TierRunResult]:
        """Return a snapshot of all recorded results.

        The caller gets a list copy — appending to it doesn't affect
        the tap's internal storage. The TierRunResult objects
        themselves are still shared references; treat them as read-only.
        """
        with self._lock:
            return list(self._results)

    def clear(self) -> None:
        """Reset the tap. Useful when the orchestrator reruns a plan."""
        with self._lock:
            self._results.clear()


class StubSupervisor:
    """P5 stub supervisor (CC1, §9.Q12).

    Always returns a pass verdict. Sets ``backend_used="stub"`` in the
    outgoing :class:`TierRunResult` the orchestrator wraps around this
    output — see :mod:`wes_orchestrator` for where that happens.

    This stub is intentionally minimal. Agent D's real supervisor will:
    - Read the bundle directive + tier logs.
    - Produce a common-sense check (frost directive, volcanic content?
      flag for rerun).
    - Author adjusted_instructions for the rerun.

    Until then, the stub is the default wiring so P5's end-to-end test
    runs cleanly.
    """

    name: str = "stub_supervisor"

    def review(
        self,
        plan: "WESPlan",
        tier_results: List[TierRunResult],
        bundle: "WESContextBundle",
    ) -> Dict[str, Any]:
        """Always-pass review. Returns the canonical verdict dict.

        The returned dict matches the :class:`Supervisor` protocol shape::

            {
                "verdict": "pass" | "fail",
                "rerun": bool,
                "notes": str,
                "adjusted_instructions": Optional[str],
            }
        """
        return {
            "verdict": "pass",
            "rerun": False,
            "notes": "stub P5",
            "adjusted_instructions": None,
        }


def supervisor_result_to_tier_record(
    verdict: Dict[str, Any],
    latency_ms: float = 0.0,
    backend_used: str = "stub",
) -> TierRunResult:
    """Wrap a supervisor's verdict dict in a :class:`TierRunResult`.

    The orchestrator uses this to persist the supervisor's verdict in
    the same tier-log format as every other tier. Backend_used
    defaults to ``"stub"`` so the P5 log is honest about where the
    verdict came from.
    """
    import json as _json

    return TierRunResult(
        tier="supervisor",
        prompt="",
        raw_response=_json.dumps(verdict, sort_keys=True),
        parsed=dict(verdict),
        latency_ms=float(latency_ms),
        backend_used=backend_used,
        errors=[],
    )


# Convenience — tests import this.
def now_ms() -> float:
    """Monotonic ms clock — shared by tiers that need latency measurement."""
    return time.monotonic() * 1000.0


__all__ = [
    "SupervisorTap",
    "StubSupervisor",
    "supervisor_result_to_tier_record",
    "now_ms",
]

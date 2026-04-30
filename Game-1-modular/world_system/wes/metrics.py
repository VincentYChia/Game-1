"""WES metrics (v4 P9).

Singleton counters covering the WES pipeline. Exposed as a snapshot dict
for the dev dashboard (§10.P9.5). **Placeholders per PLACEHOLDER_LEDGER
§16** — counter list is extensible; designer may add or rename.

Thread-safe. Zero cost when nothing is being recorded.
"""

from __future__ import annotations

import threading
import time
from collections import defaultdict, deque
from typing import Any, ClassVar, Deque, Dict, List, Optional


# One-hour sliding window for plans/hour.
_PLANS_WINDOW_SECONDS = 3600


class WESMetrics:
    """WES observability counters.

    Recorded by the orchestrator (v4 §5) and by the graceful-degrade
    logger via a periodic pull. The dashboard snapshot returns a pure
    dict suitable for JSON serialization.
    """

    _instance: ClassVar[Optional["WESMetrics"]] = None

    def __init__(self) -> None:
        # RLock so snapshot() can reenter via plans_per_hour() /
        # supervisor_rerun_rate() without deadlocking.
        self._lock = threading.RLock()

        # Plans
        self.plans_run_total: int = 0
        self.plans_committed: int = 0
        self.plans_abandoned: int = 0
        self._plan_timestamps: Deque[float] = deque()

        # Per-tool outcomes
        self.tool_successes_by_type: Dict[str, int] = defaultdict(int)
        self.tool_failures_by_type: Dict[str, int] = defaultdict(int)

        # Orphans + supervisor
        self.orphan_blocks_total: int = 0
        self.supervisor_reruns_total: int = 0
        self._supervisor_reviews_total: int = 0   # denominator for rate

        # Graceful degrade
        self.graceful_degrade_events_by_subsystem: Dict[str, int] = defaultdict(int)

        # Backend usage: "<tier>:<backend>" -> count
        self.tier_usage_by_backend: Dict[str, int] = defaultdict(int)

        # WNS-side counters (PLACEHOLDER §16 v1.0 additions).
        # WNS is observed alongside WES so the dashboard can surface
        # both arms of the v4 architecture.
        self.wns_weavings_total: int = 0
        self.wns_weavings_with_wes_calls: int = 0
        self.wns_weavings_with_affinity_shifts: int = 0
        self.wns_threads_minted_total: int = 0       # NEW thread (no match)
        self.wns_threads_continued_total: int = 0    # JOINED existing thread

        # Plan-resolution counters (PLACEHOLDER §16 v1.0 additions).
        self.plan_bounces_total: int = 0             # planner replanned after warning
        self.runtime_cascade_passes_total: int = 0   # extension plans dispatched
        self.runtime_cascade_steps_total: int = 0    # synthetic steps generated

        # WMS→WNS bridge counters (cascade_trigger feeds WNS from WMS
        # interpretations). These mirror WMSToWNSBridge.stats so the
        # dashboard can surface them alongside the rest of the pipeline.
        self.bridge_events_received: int = 0
        self.bridge_events_processed: int = 0
        self.bridge_events_skipped_duplicate: int = 0
        self.bridge_events_skipped_no_locality: int = 0
        self.bridge_weaver_run_failures: int = 0
        self.bridge_address_resolution_failures: int = 0
        # Cascade fires per layer (NL2..NL7). Sum is total cascade
        # firings since session start.
        self.cascade_fires_by_layer: Dict[int, int] = defaultdict(int)
        self.cascade_terminations_total: int = 0
        self.cascade_overruns_total: int = 0

    # ── singleton ────────────────────────────────────────────────────

    @classmethod
    def get_instance(cls) -> "WESMetrics":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        cls._instance = None

    # ── record helpers (call from orchestrator / tier code) ──────────

    def record_plan_started(self) -> None:
        with self._lock:
            self.plans_run_total += 1
            self._plan_timestamps.append(time.time())
            self._prune_old_plan_timestamps_locked()

    def record_plan_committed(self) -> None:
        with self._lock:
            self.plans_committed += 1

    def record_plan_abandoned(self, reason: str = "") -> None:  # noqa: ARG002
        with self._lock:
            self.plans_abandoned += 1

    def record_tool_success(self, tool_name: str) -> None:
        with self._lock:
            self.tool_successes_by_type[tool_name] += 1

    def record_tool_failure(self, tool_name: str) -> None:
        with self._lock:
            self.tool_failures_by_type[tool_name] += 1

    def record_orphan_block(self) -> None:
        with self._lock:
            self.orphan_blocks_total += 1

    def record_supervisor_review(self, rerun_triggered: bool) -> None:
        with self._lock:
            self._supervisor_reviews_total += 1
            if rerun_triggered:
                self.supervisor_reruns_total += 1

    def record_graceful_degrade(self, subsystem: str) -> None:
        with self._lock:
            self.graceful_degrade_events_by_subsystem[subsystem] += 1

    def record_tier_backend_usage(self, tier: str, backend: str) -> None:
        with self._lock:
            self.tier_usage_by_backend[f"{tier}:{backend}"] += 1

    # ── WNS-side recorders ───────────────────────────────────────────

    def record_wns_weaving(
        self,
        *,
        wes_call_count: int = 0,
        affinity_shift_count: int = 0,
        threads_minted: int = 0,
        threads_continued: int = 0,
    ) -> None:
        """Record one NL_N weaving cycle's outcome.

        Counts of zero are valid (most weavings emit nothing).
        ``threads_continued`` = fragments that joined an existing
        thread_id; ``threads_minted`` = fragments that opened a new one.
        """
        with self._lock:
            self.wns_weavings_total += 1
            if wes_call_count > 0:
                self.wns_weavings_with_wes_calls += 1
            if affinity_shift_count > 0:
                self.wns_weavings_with_affinity_shifts += 1
            self.wns_threads_minted_total += int(threads_minted)
            self.wns_threads_continued_total += int(threads_continued)

    def record_plan_bounce(self) -> None:
        """One bounce-back to the planner with an unresolved-refs warning."""
        with self._lock:
            self.plan_bounces_total += 1

    def record_runtime_cascade(self, step_count: int) -> None:
        """One cascade pass dispatched ``step_count`` synthetic steps."""
        with self._lock:
            self.runtime_cascade_passes_total += 1
            self.runtime_cascade_steps_total += int(step_count)

    def sync_from_wms_bridge(self, bridge: Any) -> None:  # noqa: ANN401
        """Pull counters from a :class:`WMSToWNSBridge` snapshot.

        Idempotent — assigns the latest bridge stats to the metrics
        attributes (rather than incrementing). Safe to call on a timer
        from the dashboard. Best-effort: swallows exceptions if the
        bridge interface drifts.
        """
        if bridge is None:
            return
        try:
            stats = bridge.stats
        except Exception:
            return
        with self._lock:
            self.bridge_events_received = int(stats.get("events_received", 0))
            self.bridge_events_processed = int(stats.get("events_processed", 0))
            self.bridge_events_skipped_duplicate = int(
                stats.get("events_skipped_duplicate", 0)
            )
            self.bridge_events_skipped_no_locality = int(
                stats.get("events_skipped_no_locality", 0)
            )
            self.bridge_weaver_run_failures = int(
                stats.get("weaver_run_failures", 0)
            )
            self.bridge_address_resolution_failures = int(
                stats.get("address_resolution_failures", 0)
            )
            cascade = stats.get("cascade") or {}
            fires = cascade.get("fires_total_by_layer") or {}
            self.cascade_fires_by_layer = defaultdict(int)
            for layer, n in fires.items():
                try:
                    self.cascade_fires_by_layer[int(layer)] = int(n)
                except (TypeError, ValueError):
                    continue
            self.cascade_terminations_total = int(
                cascade.get("cascade_terminations", 0)
            )
            self.cascade_overruns_total = int(
                cascade.get("cascade_overruns", 0)
            )

    # ── derived ──────────────────────────────────────────────────────

    def plans_per_hour(self) -> float:
        with self._lock:
            self._prune_old_plan_timestamps_locked()
            return float(len(self._plan_timestamps))

    def supervisor_rerun_rate(self) -> float:
        with self._lock:
            denom = self._supervisor_reviews_total
            if denom == 0:
                return 0.0
            return self.supervisor_reruns_total / float(denom)

    def _prune_old_plan_timestamps_locked(self) -> None:
        cutoff = time.time() - _PLANS_WINDOW_SECONDS
        while self._plan_timestamps and self._plan_timestamps[0] < cutoff:
            self._plan_timestamps.popleft()

    # ── snapshot ─────────────────────────────────────────────────────

    def snapshot(self) -> Dict[str, object]:
        """Pure dict snapshot for dashboards / JSON export."""
        with self._lock:
            return {
                "plans_run_total": self.plans_run_total,
                "plans_committed": self.plans_committed,
                "plans_abandoned": self.plans_abandoned,
                "plans_per_hour": self.plans_per_hour(),
                "tool_successes_by_type": dict(self.tool_successes_by_type),
                "tool_failures_by_type": dict(self.tool_failures_by_type),
                "orphan_blocks_total": self.orphan_blocks_total,
                "supervisor_reruns_total": self.supervisor_reruns_total,
                "supervisor_rerun_rate": self.supervisor_rerun_rate(),
                "graceful_degrade_events_by_subsystem": dict(
                    self.graceful_degrade_events_by_subsystem
                ),
                "tier_usage_by_backend": dict(self.tier_usage_by_backend),
                "wns_weavings_total": self.wns_weavings_total,
                "wns_weavings_with_wes_calls": self.wns_weavings_with_wes_calls,
                "wns_weavings_with_affinity_shifts": self.wns_weavings_with_affinity_shifts,
                "wns_threads_minted_total": self.wns_threads_minted_total,
                "wns_threads_continued_total": self.wns_threads_continued_total,
                "plan_bounces_total": self.plan_bounces_total,
                "runtime_cascade_passes_total": self.runtime_cascade_passes_total,
                "runtime_cascade_steps_total": self.runtime_cascade_steps_total,
                "bridge_events_received": self.bridge_events_received,
                "bridge_events_processed": self.bridge_events_processed,
                "bridge_events_skipped_duplicate": self.bridge_events_skipped_duplicate,
                "bridge_events_skipped_no_locality": self.bridge_events_skipped_no_locality,
                "bridge_weaver_run_failures": self.bridge_weaver_run_failures,
                "bridge_address_resolution_failures": self.bridge_address_resolution_failures,
                "cascade_fires_by_layer": dict(self.cascade_fires_by_layer),
                "cascade_terminations_total": self.cascade_terminations_total,
                "cascade_overruns_total": self.cascade_overruns_total,
            }

    # ── graceful-degrade pull ────────────────────────────────────────

    def sync_from_graceful_degrade_logger(self) -> int:
        """Pull recent graceful-degrade counts from the in-memory buffer.

        Returns the number of events pulled. Idempotent within the
        logger's buffer window; safe to call on a timer."""
        try:
            from world_system.living_world.infra.graceful_degrade import (
                get_graceful_degrade_logger,
            )
        except Exception:
            return 0
        logger = get_graceful_degrade_logger()
        entries = logger.recent(n=256)
        # Reset and rebuild — buffer is bounded, so this is O(buffer_size).
        with self._lock:
            self.graceful_degrade_events_by_subsystem = defaultdict(int)
            for e in entries:
                self.graceful_degrade_events_by_subsystem[e.subsystem] += 1
            return len(entries)


def get_wes_metrics() -> WESMetrics:
    """Module-level accessor."""
    return WESMetrics.get_instance()

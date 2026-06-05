"""PlayerPresenceDriftDetector — negative-pattern behavior trigger.

Phase 7 (2026-06-03). Per consolidation Wave 4 §9.4: the player's
ABSENCE from a locality is itself a behavior signal worth narrating.
"Tarmouth has not seen the wanderer in two seasons. The harbor master
no longer asks where they went." This is the unification thesis at its
most subtle — the world's recognition includes when the player ISN'T
there.

The detector runs on a periodic tick (e.g. every game-day boundary).
It scans StatStore counters for localities that show:

    - non-zero historical activity (the player WAS there)
    - no recent activity (the player hasn't been there in N days)

When the absence window exceeds the dispatch threshold, the detector
fires a behavior-causal directive at the absent locality. The
BehaviorInterpreter routes the directive to the WES pipeline like any
other behavior firing — the only difference is the inferred_intent
mentions absence.

Stringency: this uses ONLY existing WMS surface (StatStore counters,
TriggerManager history). No new WMS structural changes. The 9-rung
discipline holds (rung 3: negative patterns).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional


@dataclass
class DriftCandidate:
    """A locality the player has drifted away from."""

    locality_id: str
    last_activity_game_day: int
    current_game_day: int
    days_since: int
    historical_count: int


class PlayerPresenceDriftDetector:
    """Periodic scanner for absent localities.

    Usage:
        detector = PlayerPresenceDriftDetector(
            stat_store=stat_store,
            absence_threshold_days=30,
        )
        candidates = detector.scan(current_game_day=120)
        for cand in candidates:
            # Fire a behavior-causal directive at cand.locality_id
            ...

    Stateless across calls — the StatStore is the source of truth for
    "when did the player last act at this locality".
    """

    def __init__(
        self,
        stat_store=None,
        *,
        absence_threshold_days: int = 30,
        min_historical_activity: int = 10,
    ):
        self._stat_store = stat_store
        self._threshold = int(absence_threshold_days)
        self._min_history = int(min_historical_activity)

    def scan(
        self,
        *,
        current_game_day: int,
        known_localities: Optional[List[str]] = None,
    ) -> List[DriftCandidate]:
        """Return localities whose absence-since-last-activity exceeds
        the threshold.

        When ``known_localities`` is None, the detector tries to
        enumerate localities from the StatStore tag index (any locality
        tag that appears in ``stat_tags``). When provided, only those
        are scanned (preferred for testability + performance).

        The detector returns up to ``len(known_localities)`` candidates,
        sorted by days_since descending (most drifted-away first).
        """
        if self._stat_store is None:
            return []

        localities = (
            list(known_localities) if known_localities is not None
            else self._discover_localities()
        )
        out: List[DriftCandidate] = []
        for loc_id in localities:
            cand = self._inspect_locality(loc_id, current_game_day)
            if cand is not None:
                out.append(cand)
        out.sort(key=lambda c: c.days_since, reverse=True)
        return out

    def _inspect_locality(
        self, locality_id: str, current_game_day: int,
    ) -> Optional[DriftCandidate]:
        """Return a DriftCandidate if the player has drifted from this
        locality past the threshold, else None.

        Uses StatStore's activity_profile (Phase 0 G14) to detect
        whether the player HAS been here historically, and a recent
        sliding-window query to detect whether they've been here lately.

        For Phase 7's first version we use the per-locality activity
        sum (raw counts via ``activity_profile(loc_id, normalize=False)``)
        as the historical signal. A "last activity" timestamp lookup
        would be ideal but requires StatStore schema extension; for v4
        we approximate using the convention that the detector is called
        periodically and the caller persists last-seen days externally.

        Returns None when:
            - no historical activity at this locality
            - historical activity below ``min_historical_activity``
            - locality has been hit recently (counter has fresh updates)
        """
        try:
            profile = self._stat_store.activity_profile(
                locality_id, normalize=False,
            )
        except Exception:
            return None
        if not profile:
            return None
        total = sum(profile.values())
        if total < self._min_history:
            return None

        last_day = self._lookup_last_activity_day(locality_id)
        if last_day is None:
            return None
        days_since = current_game_day - last_day
        if days_since < self._threshold:
            return None

        return DriftCandidate(
            locality_id=locality_id,
            last_activity_game_day=last_day,
            current_game_day=current_game_day,
            days_since=days_since,
            historical_count=int(total),
        )

    def _lookup_last_activity_day(
        self, locality_id: str,
    ) -> Optional[int]:
        """Best-effort lookup of the most recent game-day the player
        was active at this locality.

        For v4 this reads a synthetic stat the runtime writes when
        events happen (``meta.last_activity_day.locality.<id>``). If
        the synthetic stat isn't populated, return None — the caller
        skips the locality.

        Future: extend StatStore with a per-stat-name updated_at column
        cleanly exposing this; for v4 we use the convention above.
        """
        try:
            v = self._stat_store.get(
                f"meta.last_activity_day.locality.{locality_id}",
            )
        except Exception:
            return None
        if not v:
            return None
        try:
            return int(v)
        except Exception:
            return None

    def _discover_localities(self) -> List[str]:
        """Enumerate localities from the StatStore tag junction table
        (any ``tag_category='locality'`` row's distinct tag_value).
        """
        try:
            conn = getattr(self._stat_store, "_conn", None)
            if conn is None:
                return []
            rows = conn.execute(
                "SELECT DISTINCT tag_value FROM stat_tags "
                "WHERE tag_category = 'locality'"
            ).fetchall()
            return [r[0] for r in rows]
        except Exception:
            return []


__all__ = ["PlayerPresenceDriftDetector", "DriftCandidate"]

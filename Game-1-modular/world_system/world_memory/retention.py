"""Event Retention Manager — prunes old events while preserving milestones.

Keeps: first occurrences, threshold-indexed events, power-of-10 milestones,
interpretation triggers, Layer 2 referenced events, and one event per
time window (timeline markers).

Design authority: WORLD_MEMORY_SYSTEM.md §5.4 (Retention Policy)
"""

from __future__ import annotations

from typing import Dict, List, Set

from world_system.world_memory.config_loader import get_section
from world_system.world_memory.trigger_manager import THRESHOLD_SET
from world_system.world_memory.event_store import EventStore


# Power-of-10 milestones (subset of thresholds, but kept explicit for clarity)
_POWER_OF_10 = frozenset({10, 100, 1000, 10000, 100000})


class EventRetentionManager:
    """Runs periodically to prune old events from the database.

    Preservation rules (Design Doc §5.4):
      1. First occurrence (interpretation_count == 1)
      2. Threshold-indexed events (count in THRESHOLD_SET)
      3. Power-of-10 milestones (count in {10, 100, 1000, 10000, 100000})
      4. Events that triggered interpretations (triggered_interpretation)
      5. Events referenced by Layer 2 cause chains
      6. One event per game-day per (actor, type, subtype) group
    """

    def __init__(self):
        cfg = get_section("retention")
        self.prune_age_threshold = cfg.get("prune_age_threshold", 50.0)
        self.timeline_window = cfg.get("timeline_window", 1.0)
        self.prune_interval = cfg.get("prune_interval", 10.0)
        self._last_prune_time: float = 0.0

    def should_prune(self, current_game_time: float) -> bool:
        return current_game_time - self._last_prune_time >= self.prune_interval

    def prune(self, event_store: EventStore, current_game_time: float) -> int:
        """Remove old events that don't meet retention criteria.

        Returns the number of events deleted.
        """
        self._last_prune_time = current_game_time
        cutoff_time = current_game_time - self.prune_age_threshold

        # Get old events
        old_events = event_store.query(
            before_game_time=cutoff_time,
            limit=5000,
            order_desc=False,
        )

        if not old_events:
            return 0

        # Group by (actor_id, event_type, event_subtype)
        groups: Dict[tuple, list] = {}
        for event in old_events:
            key = (event.actor_id, event.event_type, event.event_subtype)
            groups.setdefault(key, []).append(event)

        events_to_delete: List[str] = []

        for key, events in groups.items():
            events.sort(key=lambda e: e.game_time)
            kept_time_buckets: Set[int] = set()

            for event in events:
                keep = False
                count = event.interpretation_count

                # Rule 1: First occurrence
                if count == 1:
                    keep = True
                # Rule 2: Threshold-indexed (1, 3, 5, 10, 25, 50, 100, ...)
                elif count in THRESHOLD_SET:
                    keep = True
                # Rule 3: Power-of-10 milestones (subset of Rule 2, explicit)
                elif count in _POWER_OF_10:
                    keep = True
                # Rule 4: Triggered interpretation
                elif event.triggered_interpretation:
                    keep = True
                # Rule 5: Referenced by Layer 2 cause chains
                elif event_store.is_referenced_by_interpretation(event.event_id):
                    keep = True
                else:
                    # Rule 6: Timeline marker (one per window per group)
                    time_bucket = int(event.game_time / self.timeline_window)
                    if time_bucket not in kept_time_buckets:
                        keep = True

                if keep:
                    time_bucket = int(event.game_time / self.timeline_window)
                    kept_time_buckets.add(time_bucket)
                else:
                    events_to_delete.append(event.event_id)

        deleted = event_store.delete_events(events_to_delete)
        if deleted > 0:
            print(f"[Retention] Pruned {deleted} old events")
        return deleted

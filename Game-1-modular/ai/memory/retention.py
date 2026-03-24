"""Event Retention Manager — prunes old events while preserving milestones.

Keeps: first occurrences, prime-indexed events, power-of-10 milestones,
interpretation triggers, and one event per time window (longitude data).
"""

from __future__ import annotations

from typing import Dict, List, Set

from ai.memory.config_loader import get_section
from ai.memory.event_recorder import is_prime_trigger
from ai.memory.event_store import EventStore


class EventRetentionManager:
    """Runs periodically to prune old events from the database."""

    def __init__(self):
        cfg = get_section("retention")
        self.prune_age_threshold = cfg.get("prune_age_threshold", 50.0)
        self.timeline_window = cfg.get("timeline_window", 1.0)
        self.prune_interval = cfg.get("prune_interval", 10.0)
        self.power_of_10 = set(cfg.get("power_of_10_milestones", [100, 1000, 10000, 100000]))
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
                # Rule 2: Prime-indexed
                elif is_prime_trigger(count):
                    keep = True
                # Rule 3: Power-of-10 milestones
                elif count in self.power_of_10:
                    keep = True
                # Rule 4: Triggered interpretation
                elif event.triggered_interpretation:
                    keep = True
                # Rule 5: Referenced by Layer 3
                elif event_store.is_referenced_by_interpretation(event.event_id):
                    keep = True
                else:
                    # Rule 6: Timeline marker (one per window)
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

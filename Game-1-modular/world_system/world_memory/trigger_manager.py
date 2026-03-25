"""Dual-track threshold trigger system for the World Memory System.

Track 1 — Individual event streams: count per (actor, type, subtype, locality).
Track 2 — Regional accumulators: count per (locality_id, event_category).

Both use the same threshold sequence.  A trigger is an OPPORTUNITY to evaluate,
not a mandate to produce output.  Evaluators may return None ("not interesting").

Design authority: WORLD_MEMORY_SYSTEM.md §2 (Trigger & Escalation System)
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, ClassVar, Dict, List, Optional, Set, Tuple

from world_system.world_memory.event_schema import WorldMemoryEvent


# ── Constants ───────────────────────────────────────────────────────

THRESHOLDS: List[int] = [
    1, 3, 5, 10, 25, 50, 100, 250, 500, 1000,
    2500, 5000, 10000, 25000, 100000,
]
THRESHOLD_SET: frozenset = frozenset(THRESHOLDS)

# Maps event_type values → broad categories for Track 2 regional counting.
EVENT_CATEGORY_MAP: Dict[str, str] = {
    # Combat
    "attack_performed": "combat",
    "damage_taken": "combat",
    "enemy_killed": "combat",
    "player_death": "combat",
    "dodge_performed": "combat",
    "status_applied": "combat",
    # Gathering
    "resource_gathered": "gathering",
    "node_depleted": "gathering",
    # Crafting
    "craft_attempted": "crafting",
    "item_invented": "crafting",
    "recipe_discovered": "crafting",
    # Economy
    "item_acquired": "economy",
    "item_consumed": "economy",
    "item_equipped": "economy",
    "repair_performed": "economy",
    "trade_completed": "economy",
    # Progression
    "level_up": "progression",
    "skill_learned": "progression",
    "skill_used": "progression",
    "title_earned": "progression",
    "class_changed": "progression",
    # Exploration
    "chunk_entered": "exploration",
    "area_discovered": "exploration",
    # Social
    "npc_interaction": "social",
    "quest_accepted": "social",
    "quest_completed": "social",
    "quest_failed": "social",
    # System — excluded from regional accumulation
    "world_event": "other",
    "position_sample": "other",
}

# Categories that are excluded from regional Track 2 accumulation
_EXCLUDED_CATEGORIES: frozenset = frozenset({"other"})


# ── Data structures ─────────────────────────────────────────────────

@dataclass
class TriggerAction:
    """An opportunity for the interpreter to evaluate a pattern."""
    action_type: str          # "interpret_stream" or "interpret_region"
    key: Tuple                # The counting key that hit a threshold
    count: int                # The threshold count that was reached
    event: WorldMemoryEvent   # The event that caused the trigger


# ── TriggerManager ──────────────────────────────────────────────────

class TriggerManager:
    """Manages dual-track threshold counting.  Singleton.

    Track 1 (stream): per (actor_id, event_type, event_subtype, locality_id).
    Track 2 (regional): per (locality_id, event_category).

    Both tracks fire when their count reaches a value in THRESHOLD_SET.
    """

    _instance: ClassVar[Optional[TriggerManager]] = None

    def __init__(self) -> None:
        self._stream_counts: Dict[Tuple[str, str, str, str], int] = {}
        self._regional_counts: Dict[Tuple[str, str], int] = {}

    @classmethod
    def get_instance(cls) -> TriggerManager:
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        cls._instance = None

    # ── Core API ────────────────────────────────────────────────────

    def on_event(self, event: WorldMemoryEvent) -> List[TriggerAction]:
        """Process an event through both tracks.  Returns trigger actions."""
        actions: List[TriggerAction] = []
        locality = event.locality_id or "unknown"

        # Track 1: individual stream
        stream_key = (event.actor_id, event.event_type,
                      event.event_subtype, locality)
        self._stream_counts[stream_key] = (
            self._stream_counts.get(stream_key, 0) + 1
        )
        stream_count = self._stream_counts[stream_key]
        if stream_count in THRESHOLD_SET:
            actions.append(TriggerAction(
                "interpret_stream", stream_key, stream_count, event,
            ))

        # Track 2: regional accumulator
        category = EVENT_CATEGORY_MAP.get(event.event_type, "other")
        if locality != "unknown" and category not in _EXCLUDED_CATEGORIES:
            region_key = (locality, category)
            self._regional_counts[region_key] = (
                self._regional_counts.get(region_key, 0) + 1
            )
            region_count = self._regional_counts[region_key]
            if region_count in THRESHOLD_SET:
                actions.append(TriggerAction(
                    "interpret_region", region_key, region_count, event,
                ))

        return actions

    def get_stream_count(self, actor_id: str, event_type: str,
                         event_subtype: str, locality: str) -> int:
        """Look up current count for an individual stream."""
        return self._stream_counts.get(
            (actor_id, event_type, event_subtype, locality), 0
        )

    def get_regional_count(self, locality: str, category: str) -> int:
        """Look up current count for a regional accumulator."""
        return self._regional_counts.get((locality, category), 0)

    # ── Persistence ─────────────────────────────────────────────────

    def get_state(self) -> Dict[str, Any]:
        """Serialize both tracks for save-game persistence."""
        return {
            "stream_counts": {
                "|".join(k): v for k, v in self._stream_counts.items()
            },
            "regional_counts": {
                "|".join(k): v for k, v in self._regional_counts.items()
            },
        }

    def load_state(self, state: Dict[str, Any]) -> None:
        """Restore both tracks from saved state."""
        self._stream_counts.clear()
        self._regional_counts.clear()

        for key_str, count in state.get("stream_counts", {}).items():
            parts = key_str.split("|", 3)
            if len(parts) == 4:
                self._stream_counts[tuple(parts)] = count

        for key_str, count in state.get("regional_counts", {}).items():
            parts = key_str.split("|", 1)
            if len(parts) == 2:
                self._regional_counts[tuple(parts)] = count

    # ── Debug ───────────────────────────────────────────────────────

    @property
    def stats(self) -> Dict[str, int]:
        return {
            "stream_keys": len(self._stream_counts),
            "regional_keys": len(self._regional_counts),
            "total_stream_events": sum(self._stream_counts.values()),
            "total_regional_events": sum(self._regional_counts.values()),
        }

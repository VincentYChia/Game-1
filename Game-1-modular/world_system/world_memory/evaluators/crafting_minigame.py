"""Crafting Minigame Evaluator — narrates notable quality achievements across all disciplines."""

from __future__ import annotations

from typing import Optional

from world_system.world_memory.config_loader import get_evaluator_config
from world_system.world_memory.event_schema import InterpretedEvent, WorldMemoryEvent
from world_system.world_memory.event_store import EventStore
from world_system.world_memory.geographic_registry import GeographicRegistry
from world_system.world_memory.entity_registry import EntityRegistry
from world_system.world_memory.interpreter import PatternEvaluator


class CraftingMinigameEvaluator(PatternEvaluator):

    RELEVANT_TYPES = {"craft_attempted"}
    NOTABLE_QUALITIES = {"masterwork", "legendary", "superior"}

    def __init__(self):
        cfg = get_evaluator_config("crafting_minigame")
        self.lookback_time = cfg.get("lookback_time", 100.0)

    def is_relevant(self, event: WorldMemoryEvent) -> bool:
        return event.event_type in self.RELEVANT_TYPES

    def evaluate(self, trigger_event: WorldMemoryEvent,
                 event_store: EventStore,
                 geo_registry: GeographicRegistry,
                 entity_registry: EntityRegistry,
                 interpretation_store: EventStore) -> Optional[InterpretedEvent]:
        recent = event_store.query(
            event_type="craft_attempted",
            actor_id="player",
            since_game_time=trigger_event.game_time - self.lookback_time,
            limit=200,
        )

        total = len(recent)
        if total < 1:
            return None

        # Count quality types
        qualities = {}
        for e in recent:
            qual = e.quality or "normal"
            qualities[qual] = qualities.get(qual, 0) + 1

        # Only narrate notable qualities
        notable_found = {q: c for q, c in qualities.items() if q in self.NOTABLE_QUALITIES}
        if not notable_found:
            return None

        # Pick the most frequent notable quality for the narrative
        best_quality = max(notable_found, key=notable_found.get)
        quality_count = notable_found[best_quality]

        narrative = (
            f"Player has achieved {best_quality} quality "
            f"{quality_count} times out of {total} crafts."
        )

        if quality_count >= 30:
            severity = "major"
        elif quality_count >= 15:
            severity = "significant"
        elif quality_count >= 5:
            severity = "moderate"
        else:
            severity = "minor"

        return InterpretedEvent.create(
            narrative=narrative,
            category="crafting_minigame",
            severity=severity,
            trigger_event_id=trigger_event.event_id,
            trigger_count=trigger_event.interpretation_count,
            game_time=trigger_event.game_time,
            affects_tags=[f"quality:{best_quality}", "event:crafting", "type:player"],
        )

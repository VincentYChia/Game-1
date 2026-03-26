"""Crafting Inventions Evaluator — narrates item invention and recipe discovery counts."""

from __future__ import annotations

from typing import Optional

from world_system.world_memory.config_loader import get_evaluator_config
from world_system.world_memory.event_schema import InterpretedEvent, WorldMemoryEvent
from world_system.world_memory.event_store import EventStore
from world_system.world_memory.geographic_registry import GeographicRegistry
from world_system.world_memory.entity_registry import EntityRegistry
from world_system.world_memory.interpreter import PatternEvaluator


class CraftingInventionsEvaluator(PatternEvaluator):

    RELEVANT_TYPES = {"item_invented", "recipe_discovered"}

    def __init__(self):
        cfg = get_evaluator_config("crafting_inventions")
        self.lookback_time = cfg.get("lookback_time", 100.0)

    def is_relevant(self, event: WorldMemoryEvent) -> bool:
        return event.event_type in self.RELEVANT_TYPES

    def evaluate(self, trigger_event: WorldMemoryEvent,
                 event_store: EventStore,
                 geo_registry: GeographicRegistry,
                 entity_registry: EntityRegistry,
                 interpretation_store: EventStore) -> Optional[InterpretedEvent]:
        event_type = trigger_event.event_type

        count = event_store.count_filtered(
            event_type=event_type,
            since_game_time=trigger_event.game_time - self.lookback_time,
        )

        if count < 1:
            return None

        if event_type == "item_invented":
            narrative = f"Player has invented {count} items total."
        else:
            narrative = f"Player has discovered {count} recipes total."

        # Inventions and discoveries are always at least moderate
        if count >= 30:
            severity = "major"
        elif count >= 15:
            severity = "significant"
        else:
            severity = "moderate"

        return InterpretedEvent.create(
            narrative=narrative,
            category="crafting_inventions",
            severity=severity,
            trigger_event_id=trigger_event.event_id,
            trigger_count=trigger_event.interpretation_count,
            game_time=trigger_event.game_time,
            affects_tags=[f"event:{event_type}", "event:crafting", "type:player"],
        )

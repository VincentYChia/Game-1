"""Crafting Alchemy Evaluator — narrates alchemy craft counts."""

from __future__ import annotations

from typing import Optional

from world_system.world_memory.config_loader import get_evaluator_config
from world_system.world_memory.event_schema import InterpretedEvent, WorldMemoryEvent
from world_system.world_memory.event_store import EventStore
from world_system.world_memory.geographic_registry import GeographicRegistry
from world_system.world_memory.entity_registry import EntityRegistry
from world_system.world_memory.interpreter import PatternEvaluator


class CraftingAlchemyEvaluator(PatternEvaluator):

    RELEVANT_TYPES = {"craft_attempted"}

    def __init__(self):
        cfg = get_evaluator_config("crafting_alchemy")
        self.lookback_time = cfg.get("lookback_time", 100.0)

    def is_relevant(self, event: WorldMemoryEvent) -> bool:
        if event.event_type not in self.RELEVANT_TYPES:
            return False
        return event.context.get("discipline") == "alchemy"

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

        alchemy_events = [e for e in recent if e.context.get("discipline") == "alchemy"]
        count = len(alchemy_events)

        if count < 1:
            return None

        # Count quality occurrences
        qualities = {}
        for e in alchemy_events:
            qual = e.quality
            if qual:
                qualities[qual] = qualities.get(qual, 0) + 1

        if qualities:
            best_quality = max(qualities, key=qualities.get)
            quality_count = qualities[best_quality]
            narrative = (
                f"Player has crafted {count} items in alchemy, "
                f"{quality_count} at {best_quality} quality."
            )
        else:
            narrative = f"Player has crafted {count} items in alchemy."

        if count >= 30:
            severity = "major"
        elif count >= 15:
            severity = "significant"
        elif count >= 5:
            severity = "moderate"
        else:
            severity = "minor"

        return InterpretedEvent.create(
            narrative=narrative,
            category="crafting_discipline",
            severity=severity,
            trigger_event_id=trigger_event.event_id,
            trigger_count=trigger_event.interpretation_count,
            game_time=trigger_event.game_time,
            affects_tags=["domain:alchemy", "event:crafting", "type:player"],
        )

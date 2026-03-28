"""Gathering Tools Evaluator — narrates the total number of gathering
actions the player has performed (global scope)."""

from __future__ import annotations

from typing import Optional

from world_system.world_memory.config_loader import get_evaluator_config
from world_system.world_memory.event_schema import InterpretedEvent, WorldMemoryEvent
from world_system.world_memory.event_store import EventStore
from world_system.world_memory.geographic_registry import GeographicRegistry
from world_system.world_memory.entity_registry import EntityRegistry
from world_system.world_memory.interpreter import PatternEvaluator


class GatheringToolsEvaluator(PatternEvaluator):
    """Reports total gathering actions performed across the entire world
    (all resource types combined)."""

    RELEVANT_TYPES = {"resource_gathered"}

    def __init__(self):
        cfg = get_evaluator_config("gathering_tools")
        self.expiration_offset = cfg.get("expiration_offset", 300.0)
        t = cfg.get("thresholds", {})
        self.minor_max = t.get("minor_max", 50)
        self.moderate_max = t.get("moderate_max", 200)
        self.significant_max = t.get("significant_max", 1000)
        templates = cfg.get("narrative_templates", {})
        self.tpl = templates.get(
            "default",
            "Player has performed {count} gathering actions total.",
        )

    def is_relevant(self, event: WorldMemoryEvent) -> bool:
        return event.event_type in self.RELEVANT_TYPES

    def evaluate(
        self,
        trigger_event: WorldMemoryEvent,
        event_store: EventStore,
        geo_registry: GeographicRegistry,
        entity_registry: EntityRegistry,
        interpretation_store: EventStore,
    ) -> Optional[InterpretedEvent]:
        count = event_store.count_filtered(
            event_type="resource_gathered",
        )

        if count < 1:
            return None

        if count < self.minor_max:
            severity = "minor"
        elif count < self.moderate_max:
            severity = "moderate"
        elif count < self.significant_max:
            severity = "significant"
        else:
            severity = "major"

        narrative = self.tpl.format(count=count)

        return InterpretedEvent.create(
            narrative=narrative,
            category="gathering_tools",
            severity=severity,
            trigger_event_id=trigger_event.event_id,
            trigger_count=trigger_event.interpretation_count,
            game_time=trigger_event.game_time,
            affected_locality_ids=[],
            affected_district_ids=[],
            epicenter_x=trigger_event.position_x,
            epicenter_y=trigger_event.position_y,
            affects_tags=[],
            is_ongoing=True,
            expires_at=trigger_event.game_time + self.expiration_offset,
        )

"""Gathering Global Evaluator — narrates total lifetime gathering of a
specific resource across the entire world."""

from __future__ import annotations

from typing import Optional

from world_system.world_memory.config_loader import get_evaluator_config
from world_system.world_memory.event_schema import InterpretedEvent, WorldMemoryEvent
from world_system.world_memory.event_store import EventStore
from world_system.world_memory.geographic_registry import GeographicRegistry
from world_system.world_memory.entity_registry import EntityRegistry
from world_system.world_memory.interpreter import PatternEvaluator


class GatheringGlobalEvaluator(PatternEvaluator):
    """Reports the total amount of a specific resource gathered across all
    localities (global scope, no locality filter)."""

    RELEVANT_TYPES = {"resource_gathered"}

    def __init__(self):
        cfg = get_evaluator_config("gathering_global")
        self.expiration_offset = cfg.get("expiration_offset", 200.0)
        t = cfg.get("thresholds", {})
        self.minor_max = t.get("minor_max", 20)
        self.moderate_max = t.get("moderate_max", 100)
        self.significant_max = t.get("significant_max", 500)
        templates = cfg.get("narrative_templates", {})
        self.tpl = templates.get(
            "default",
            "Player has gathered {count} {resource} total.",
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
        subtype = trigger_event.event_subtype
        resource_name = subtype.replace("gathered_", "").replace("_", " ")

        count = event_store.count_filtered(
            event_type="resource_gathered",
            event_subtype=subtype,
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

        narrative = self.tpl.format(
            count=count,
            resource=resource_name,
        )

        return InterpretedEvent.create(
            narrative=narrative,
            category="gathering_global",
            severity=severity,
            trigger_event_id=trigger_event.event_id,
            trigger_count=trigger_event.interpretation_count,
            game_time=trigger_event.game_time,
            affected_locality_ids=[],
            affected_district_ids=[],
            epicenter_x=trigger_event.position_x,
            epicenter_y=trigger_event.position_y,
            affects_tags=[
                f"resource:{resource_name.replace(' ', '_')}",
            ],
            is_ongoing=True,
            expires_at=trigger_event.game_time + self.expiration_offset,
        )

"""Progression Levels Evaluator — narrates player level-up events."""

from __future__ import annotations

from typing import Optional

from world_system.world_memory.config_loader import get_evaluator_config
from world_system.world_memory.event_schema import InterpretedEvent, WorldMemoryEvent
from world_system.world_memory.event_store import EventStore
from world_system.world_memory.geographic_registry import GeographicRegistry
from world_system.world_memory.entity_registry import EntityRegistry
from world_system.world_memory.interpreter import PatternEvaluator


class ProgressionLevelsEvaluator(PatternEvaluator):

    RELEVANT_TYPES = {"level_up"}

    def __init__(self):
        cfg = get_evaluator_config("progression_levels")
        self.expiration_offset = cfg.get("expiration_offset", 300.0)
        t = cfg.get("thresholds", {})
        self.moderate_min = t.get("moderate_min", 10)
        self.significant_min = t.get("significant_min", 20)
        self.major_min = t.get("major_min", 25)
        templates = cfg.get("narrative_templates", {})
        self.tpl = templates.get("default",
            "Player has reached level {level}.")

    def is_relevant(self, event: WorldMemoryEvent) -> bool:
        return event.event_type in self.RELEVANT_TYPES

    def evaluate(self, trigger_event: WorldMemoryEvent,
                 event_store: EventStore,
                 geo_registry: GeographicRegistry,
                 entity_registry: EntityRegistry,
                 interpretation_store: EventStore) -> Optional[InterpretedEvent]:
        level = trigger_event.context.get("new_level", trigger_event.magnitude)
        if level is None:
            return None

        level = int(level)

        if level >= self.major_min:
            severity = "major"
        elif level >= self.significant_min:
            severity = "significant"
        elif level >= self.moderate_min:
            severity = "moderate"
        else:
            severity = "minor"

        narrative = self.tpl.format(level=level)

        return InterpretedEvent.create(
            narrative=narrative,
            category="progression_levels",
            severity=severity,
            trigger_event_id=trigger_event.event_id,
            trigger_count=trigger_event.interpretation_count,
            game_time=trigger_event.game_time,
            cause_event_ids=[trigger_event.event_id],
            affected_locality_ids=[trigger_event.locality_id] if trigger_event.locality_id else [],
            affected_district_ids=[trigger_event.district_id] if trigger_event.district_id else [],
            affected_province_ids=[trigger_event.province_id] if trigger_event.province_id else [],
            epicenter_x=trigger_event.position_x,
            epicenter_y=trigger_event.position_y,
            affects_tags=["type:player", "event:level_up"],
            is_ongoing=False,
            expires_at=trigger_event.game_time + self.expiration_offset,
        )

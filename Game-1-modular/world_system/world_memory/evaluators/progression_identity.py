"""Progression Identity Evaluator — narrates title and class change events."""

from __future__ import annotations

from typing import Optional

from world_system.world_memory.config_loader import get_evaluator_config
from world_system.world_memory.event_schema import InterpretedEvent, WorldMemoryEvent
from world_system.world_memory.event_store import EventStore
from world_system.world_memory.geographic_registry import GeographicRegistry
from world_system.world_memory.entity_registry import EntityRegistry
from world_system.world_memory.interpreter import PatternEvaluator


class ProgressionIdentityEvaluator(PatternEvaluator):

    RELEVANT_TYPES = {"title_earned", "class_changed"}

    def __init__(self):
        cfg = get_evaluator_config("progression_identity")
        self.expiration_offset = cfg.get("expiration_offset", 300.0)
        templates = cfg.get("narrative_templates", {})
        self.tpl_title = templates.get("title_earned",
            "Player has earned the title {title}.")
        self.tpl_class = templates.get("class_changed",
            "Player has changed class to {class_name}.")

    def is_relevant(self, event: WorldMemoryEvent) -> bool:
        return event.event_type in self.RELEVANT_TYPES

    def evaluate(self, trigger_event: WorldMemoryEvent,
                 event_store: EventStore,
                 geo_registry: GeographicRegistry,
                 entity_registry: EntityRegistry,
                 interpretation_store: EventStore) -> Optional[InterpretedEvent]:
        et = trigger_event.event_type

        if et == "title_earned":
            return self._eval_title(trigger_event)
        if et == "class_changed":
            return self._eval_class(trigger_event)
        return None

    def _eval_title(self, event: WorldMemoryEvent) -> Optional[InterpretedEvent]:
        title = event.context.get("title", event.event_subtype) or "unknown"
        narrative = self.tpl_title.format(title=title)

        return InterpretedEvent.create(
            narrative=narrative,
            category="progression_identity",
            severity="moderate",
            trigger_event_id=event.event_id,
            trigger_count=event.interpretation_count,
            game_time=event.game_time,
            cause_event_ids=[event.event_id],
            affected_locality_ids=[event.locality_id] if event.locality_id else [],
            affected_district_ids=[event.district_id] if event.district_id else [],
            affected_province_ids=[event.province_id] if event.province_id else [],
            epicenter_x=event.position_x,
            epicenter_y=event.position_y,
            affects_tags=["type:player", "event:title_earned", f"title:{title}"],
            is_ongoing=False,
            expires_at=event.game_time + self.expiration_offset,
        )

    def _eval_class(self, event: WorldMemoryEvent) -> Optional[InterpretedEvent]:
        class_name = event.context.get("class", event.event_subtype) or "unknown"
        narrative = self.tpl_class.format(class_name=class_name)

        return InterpretedEvent.create(
            narrative=narrative,
            category="progression_identity",
            severity="moderate",
            trigger_event_id=event.event_id,
            trigger_count=event.interpretation_count,
            game_time=event.game_time,
            cause_event_ids=[event.event_id],
            affected_locality_ids=[event.locality_id] if event.locality_id else [],
            affected_district_ids=[event.district_id] if event.district_id else [],
            affected_province_ids=[event.province_id] if event.province_id else [],
            epicenter_x=event.position_x,
            epicenter_y=event.position_y,
            affects_tags=["type:player", "event:class_changed", f"class:{class_name}"],
            is_ongoing=False,
            expires_at=event.game_time + self.expiration_offset,
        )

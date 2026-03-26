"""Progression Skills Evaluator — narrates skill learning and usage events."""

from __future__ import annotations

from typing import Optional

from world_system.world_memory.config_loader import get_evaluator_config
from world_system.world_memory.event_schema import InterpretedEvent, WorldMemoryEvent
from world_system.world_memory.event_store import EventStore
from world_system.world_memory.geographic_registry import GeographicRegistry
from world_system.world_memory.entity_registry import EntityRegistry
from world_system.world_memory.interpreter import PatternEvaluator


class ProgressionSkillsEvaluator(PatternEvaluator):

    RELEVANT_TYPES = {"skill_learned", "skill_used"}

    def __init__(self):
        cfg = get_evaluator_config("progression_skills")
        self.expiration_offset = cfg.get("expiration_offset", 300.0)
        self.lookback_time = cfg.get("lookback_time", 50.0)
        t = cfg.get("thresholds", {})
        self.min_trigger = t.get("minimum_trigger", 1)
        self.moderate_min = t.get("moderate_min", 20)
        self.significant_min = t.get("significant_min", 50)
        self.major_min = t.get("major_min", 100)
        templates = cfg.get("narrative_templates", {})
        self.tpl_learned = templates.get("skill_learned",
            "Player has learned the skill {skill_name}.")
        self.tpl_used = templates.get("skill_used",
            "Player has used skills {count} times.")

    def is_relevant(self, event: WorldMemoryEvent) -> bool:
        return event.event_type in self.RELEVANT_TYPES

    def evaluate(self, trigger_event: WorldMemoryEvent,
                 event_store: EventStore,
                 geo_registry: GeographicRegistry,
                 entity_registry: EntityRegistry,
                 interpretation_store: EventStore) -> Optional[InterpretedEvent]:
        et = trigger_event.event_type

        if et == "skill_learned":
            return self._eval_skill_learned(trigger_event)
        if et == "skill_used":
            return self._eval_skill_used(trigger_event, event_store)
        return None

    def _eval_skill_learned(self, event: WorldMemoryEvent) -> Optional[InterpretedEvent]:
        skill_name = event.context.get("skill_name", event.event_subtype) or "unknown"
        narrative = self.tpl_learned.format(skill_name=skill_name)

        return InterpretedEvent.create(
            narrative=narrative,
            category="progression_skills",
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
            affects_tags=["type:player", "event:skill_learned", f"skill:{skill_name}"],
            is_ongoing=False,
            expires_at=event.game_time + self.expiration_offset,
        )

    def _eval_skill_used(self, event: WorldMemoryEvent,
                         event_store: EventStore) -> Optional[InterpretedEvent]:
        count = event_store.count_filtered(event_type="skill_used")

        if count < self.min_trigger:
            return None

        if count >= self.major_min:
            severity = "major"
        elif count >= self.significant_min:
            severity = "significant"
        elif count >= self.moderate_min:
            severity = "moderate"
        else:
            severity = "minor"

        narrative = self.tpl_used.format(count=count)

        cause_events = event_store.query(
            event_type="skill_used",
            limit=10,
        )

        return InterpretedEvent.create(
            narrative=narrative,
            category="progression_skills",
            severity=severity,
            trigger_event_id=event.event_id,
            trigger_count=event.interpretation_count,
            game_time=event.game_time,
            cause_event_ids=[e.event_id for e in cause_events],
            affected_locality_ids=[event.locality_id] if event.locality_id else [],
            affected_district_ids=[event.district_id] if event.district_id else [],
            affected_province_ids=[event.province_id] if event.province_id else [],
            epicenter_x=event.position_x,
            epicenter_y=event.position_y,
            affects_tags=["type:player", "event:skill_used"],
            is_ongoing=True,
            expires_at=event.game_time + self.expiration_offset,
        )

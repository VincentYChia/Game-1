"""Progression Equipment Evaluator — narrates equipment and repair events."""

from __future__ import annotations

from typing import Optional

from world_system.world_memory.config_loader import get_evaluator_config
from world_system.world_memory.event_schema import InterpretedEvent, WorldMemoryEvent
from world_system.world_memory.event_store import EventStore
from world_system.world_memory.geographic_registry import GeographicRegistry
from world_system.world_memory.entity_registry import EntityRegistry
from world_system.world_memory.interpreter import PatternEvaluator


class ProgressionEquipmentEvaluator(PatternEvaluator):

    RELEVANT_TYPES = {"item_equipped", "repair_performed"}

    def __init__(self):
        cfg = get_evaluator_config("progression_equipment")
        self.expiration_offset = cfg.get("expiration_offset", 300.0)
        self.lookback_time = cfg.get("lookback_time", 50.0)
        t = cfg.get("thresholds", {})
        self.min_trigger = t.get("minimum_trigger", 1)
        self.moderate_min = t.get("moderate_min", 10)
        self.significant_min = t.get("significant_min", 25)
        self.major_min = t.get("major_min", 50)
        templates = cfg.get("narrative_templates", {})
        self.tpl_equipped = templates.get("item_equipped",
            "Player has equipped {item}.")
        self.tpl_repair = templates.get("repair_performed",
            "Player has repaired items {count} times.")

    def is_relevant(self, event: WorldMemoryEvent) -> bool:
        return event.event_type in self.RELEVANT_TYPES

    def evaluate(self, trigger_event: WorldMemoryEvent,
                 event_store: EventStore,
                 geo_registry: GeographicRegistry,
                 entity_registry: EntityRegistry,
                 interpretation_store: EventStore) -> Optional[InterpretedEvent]:
        et = trigger_event.event_type

        if et == "item_equipped":
            return self._eval_equipped(trigger_event)
        if et == "repair_performed":
            return self._eval_repair(trigger_event, event_store)
        return None

    def _eval_equipped(self, event: WorldMemoryEvent) -> Optional[InterpretedEvent]:
        item = event.context.get("item_name", event.event_subtype) or "unknown item"
        narrative = self.tpl_equipped.format(item=item)

        return InterpretedEvent.create(
            narrative=narrative,
            category="progression_equipment",
            severity="minor",
            trigger_event_id=event.event_id,
            trigger_count=event.interpretation_count,
            game_time=event.game_time,
            cause_event_ids=[event.event_id],
            affected_locality_ids=[event.locality_id] if event.locality_id else [],
            affected_district_ids=[event.district_id] if event.district_id else [],
            affected_province_ids=[event.province_id] if event.province_id else [],
            epicenter_x=event.position_x,
            epicenter_y=event.position_y,
            affects_tags=["type:player", "event:item_equipped", f"item:{item}"],
            is_ongoing=False,
            expires_at=event.game_time + self.expiration_offset,
        )

    def _eval_repair(self, event: WorldMemoryEvent,
                     event_store: EventStore) -> Optional[InterpretedEvent]:
        count = event_store.count_filtered(event_type="repair_performed")

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

        narrative = self.tpl_repair.format(count=count)

        cause_events = event_store.query(
            event_type="repair_performed",
            limit=10,
        )

        return InterpretedEvent.create(
            narrative=narrative,
            category="progression_equipment",
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
            affects_tags=["type:player", "event:repair_performed"],
            is_ongoing=True,
            expires_at=event.game_time + self.expiration_offset,
        )

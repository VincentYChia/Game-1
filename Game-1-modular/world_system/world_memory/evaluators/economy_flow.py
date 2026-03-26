"""Economy Flow Evaluator — narrates item acquisition and consumption totals."""

from __future__ import annotations

from typing import Optional

from world_system.world_memory.config_loader import get_evaluator_config
from world_system.world_memory.event_schema import InterpretedEvent, WorldMemoryEvent
from world_system.world_memory.event_store import EventStore
from world_system.world_memory.geographic_registry import GeographicRegistry
from world_system.world_memory.entity_registry import EntityRegistry
from world_system.world_memory.interpreter import PatternEvaluator


class EconomyFlowEvaluator(PatternEvaluator):

    RELEVANT_TYPES = {"item_acquired", "item_consumed"}

    def __init__(self):
        cfg = get_evaluator_config("economy_flow")
        self.expiration_offset = cfg.get("expiration_offset", 300.0)
        self.lookback_time = cfg.get("lookback_time", 50.0)
        t = cfg.get("thresholds", {})
        self.min_trigger = t.get("minimum_trigger", 1)
        self.moderate_min = t.get("moderate_min", 10)
        self.significant_min = t.get("significant_min", 50)
        self.major_min = t.get("major_min", 200)
        templates = cfg.get("narrative_templates", {})
        self.tpl_acquired = templates.get("item_acquired",
            "Player has acquired {count} items total.")
        self.tpl_consumed = templates.get("item_consumed",
            "Player has consumed {count} items total.")

    def is_relevant(self, event: WorldMemoryEvent) -> bool:
        return event.event_type in self.RELEVANT_TYPES

    def evaluate(self, trigger_event: WorldMemoryEvent,
                 event_store: EventStore,
                 geo_registry: GeographicRegistry,
                 entity_registry: EntityRegistry,
                 interpretation_store: EventStore) -> Optional[InterpretedEvent]:
        et = trigger_event.event_type

        count = event_store.count_filtered(event_type=et)

        if count < self.min_trigger:
            return None

        if et == "item_acquired":
            narrative = self.tpl_acquired.format(count=count)
        else:
            narrative = self.tpl_consumed.format(count=count)

        if count >= self.major_min:
            severity = "major"
        elif count >= self.significant_min:
            severity = "significant"
        elif count >= self.moderate_min:
            severity = "moderate"
        else:
            severity = "minor"

        cause_events = event_store.query(
            event_type=et,
            limit=10,
        )

        return InterpretedEvent.create(
            narrative=narrative,
            category="economy_flow",
            severity=severity,
            trigger_event_id=trigger_event.event_id,
            trigger_count=trigger_event.interpretation_count,
            game_time=trigger_event.game_time,
            cause_event_ids=[e.event_id for e in cause_events],
            affected_locality_ids=[trigger_event.locality_id] if trigger_event.locality_id else [],
            affected_district_ids=[trigger_event.district_id] if trigger_event.district_id else [],
            affected_province_ids=[trigger_event.province_id] if trigger_event.province_id else [],
            epicenter_x=trigger_event.position_x,
            epicenter_y=trigger_event.position_y,
            affects_tags=["type:player", f"event:{et}"],
            is_ongoing=True,
            expires_at=trigger_event.game_time + self.expiration_offset,
        )

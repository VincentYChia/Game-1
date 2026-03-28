"""Social NPC Evaluator — narrates NPC interaction events."""

from __future__ import annotations

from typing import Optional

from world_system.world_memory.config_loader import get_evaluator_config
from world_system.world_memory.event_schema import InterpretedEvent, WorldMemoryEvent
from world_system.world_memory.event_store import EventStore
from world_system.world_memory.geographic_registry import GeographicRegistry
from world_system.world_memory.entity_registry import EntityRegistry
from world_system.world_memory.interpreter import PatternEvaluator


class SocialNpcEvaluator(PatternEvaluator):

    RELEVANT_TYPES = {"npc_interaction"}

    def __init__(self):
        cfg = get_evaluator_config("social_npc")
        self.expiration_offset = cfg.get("expiration_offset", 300.0)
        self.lookback_time = cfg.get("lookback_time", 50.0)
        t = cfg.get("thresholds", {})
        self.min_trigger = t.get("minimum_trigger", 1)
        self.moderate_min = t.get("moderate_min", 10)
        self.significant_min = t.get("significant_min", 30)
        self.major_min = t.get("major_min", 75)
        templates = cfg.get("narrative_templates", {})
        self.tpl_global = templates.get("global",
            "Player has interacted with NPCs {count} times.")
        self.tpl_specific = templates.get("specific",
            "Player has talked to {npc_name} {count} times.")

    def is_relevant(self, event: WorldMemoryEvent) -> bool:
        return event.event_type in self.RELEVANT_TYPES

    def evaluate(self, trigger_event: WorldMemoryEvent,
                 event_store: EventStore,
                 geo_registry: GeographicRegistry,
                 entity_registry: EntityRegistry,
                 interpretation_store: EventStore) -> Optional[InterpretedEvent]:
        npc_name = trigger_event.context.get("npc_name") or trigger_event.event_subtype

        if npc_name:
            count = event_store.count_filtered(
                event_type="npc_interaction",
                event_subtype=npc_name,
            )
            if count < self.min_trigger:
                return None
            narrative = self.tpl_specific.format(npc_name=npc_name, count=count)
            extra_tags = [f"npc:{npc_name}"]
        else:
            count = event_store.count_filtered(event_type="npc_interaction")
            if count < self.min_trigger:
                return None
            narrative = self.tpl_global.format(count=count)
            extra_tags = []

        if count >= self.major_min:
            severity = "major"
        elif count >= self.significant_min:
            severity = "significant"
        elif count >= self.moderate_min:
            severity = "moderate"
        else:
            severity = "minor"

        cause_events = event_store.query(
            event_type="npc_interaction",
            event_subtype=npc_name if npc_name else None,
            limit=10,
        )

        return InterpretedEvent.create(
            narrative=narrative,
            category="social_npc",
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
            affects_tags=["type:player", "event:npc_interaction"] + extra_tags,
            is_ongoing=True,
            expires_at=trigger_event.game_time + self.expiration_offset,
        )

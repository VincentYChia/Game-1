"""Combat Kills Global Evaluator — narrates total enemy kill counts across all
regions."""

from __future__ import annotations

from typing import Optional

from world_system.world_memory.config_loader import get_evaluator_config
from world_system.world_memory.event_schema import InterpretedEvent, WorldMemoryEvent
from world_system.world_memory.event_store import EventStore
from world_system.world_memory.geographic_registry import GeographicRegistry
from world_system.world_memory.entity_registry import EntityRegistry
from world_system.world_memory.interpreter import PatternEvaluator


class CombatKillsGlobalEvaluator(PatternEvaluator):

    RELEVANT_TYPES = {"enemy_killed"}

    def __init__(self):
        cfg = get_evaluator_config("combat_kills_global")
        self.expiration_offset = cfg.get("expiration_offset", 300.0)
        t = cfg.get("thresholds", {})
        self.min_trigger = t.get("minimum_trigger", 10)
        self.moderate_min = t.get("moderate_min", 50)
        self.significant_min = t.get("significant_min", 100)
        self.major_min = t.get("major_min", 500)
        templates = cfg.get("narrative_templates", {})
        self.tpl = templates.get("default",
            "Player has killed {count} {enemy} total.")

    def is_relevant(self, event: WorldMemoryEvent) -> bool:
        return event.event_type in self.RELEVANT_TYPES

    def evaluate(self, trigger_event: WorldMemoryEvent,
                 event_store: EventStore,
                 geo_registry: GeographicRegistry,
                 entity_registry: EntityRegistry,
                 interpretation_store: EventStore) -> Optional[InterpretedEvent]:
        enemy_subtype = trigger_event.event_subtype
        count = event_store.count_filtered(
            event_type="enemy_killed",
            event_subtype=enemy_subtype,
        )

        if count < self.min_trigger:
            return None

        enemy_name = enemy_subtype.replace("killed_", "").replace("_", " ")

        if count >= self.major_min:
            severity = "major"
        elif count >= self.significant_min:
            severity = "significant"
        elif count >= self.moderate_min:
            severity = "moderate"
        else:
            severity = "minor"

        narrative = self.tpl.format(count=count, enemy=enemy_name)

        cause_events = event_store.query(
            event_type="enemy_killed",
            event_subtype=enemy_subtype,
            limit=10,
        )

        return InterpretedEvent.create(
            narrative=narrative,
            category="combat_kills_global",
            severity=severity,
            trigger_event_id=trigger_event.event_id,
            trigger_count=trigger_event.interpretation_count,
            game_time=trigger_event.game_time,
            cause_event_ids=[e.event_id for e in cause_events],
            affected_locality_ids=[],
            affected_district_ids=[],
            epicenter_x=trigger_event.position_x,
            epicenter_y=trigger_event.position_y,
            affects_tags=[
                f"species:{enemy_name.replace(' ', '_')}",
                "event:combat",
            ],
            is_ongoing=True,
            expires_at=trigger_event.game_time + self.expiration_offset,
        )

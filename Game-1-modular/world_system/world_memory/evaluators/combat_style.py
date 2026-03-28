"""Combat Style Evaluator — narrates global counts of combat action types
(dodges, status applications, attacks)."""

from __future__ import annotations

from typing import Optional

from world_system.world_memory.config_loader import get_evaluator_config
from world_system.world_memory.event_schema import InterpretedEvent, WorldMemoryEvent
from world_system.world_memory.event_store import EventStore
from world_system.world_memory.geographic_registry import GeographicRegistry
from world_system.world_memory.entity_registry import EntityRegistry
from world_system.world_memory.interpreter import PatternEvaluator


class CombatStyleEvaluator(PatternEvaluator):

    RELEVANT_TYPES = {"dodge_performed", "status_applied", "attack_performed"}

    def __init__(self):
        cfg = get_evaluator_config("combat_style")
        self.expiration_offset = cfg.get("expiration_offset", 200.0)
        t = cfg.get("thresholds", {})
        self.min_trigger = t.get("minimum_trigger", 5)
        self.moderate_min = t.get("moderate_min", 20)
        self.significant_min = t.get("significant_min", 50)
        self.major_min = t.get("major_min", 100)
        templates = cfg.get("narrative_templates", {})
        self.tpl_dodge = templates.get("dodge",
            "Player has dodged {count} times.")
        self.tpl_status = templates.get("status",
            "Player has applied status effects {count} times.")
        self.tpl_attack = templates.get("attack",
            "Player has attacked {count} times.")

    def is_relevant(self, event: WorldMemoryEvent) -> bool:
        return event.event_type in self.RELEVANT_TYPES

    def evaluate(self, trigger_event: WorldMemoryEvent,
                 event_store: EventStore,
                 geo_registry: GeographicRegistry,
                 entity_registry: EntityRegistry,
                 interpretation_store: EventStore) -> Optional[InterpretedEvent]:
        event_type = trigger_event.event_type
        count = event_store.count_filtered(
            event_type=event_type,
        )

        if count < self.min_trigger:
            return None

        if event_type == "dodge_performed":
            narrative = self.tpl_dodge.format(count=count)
        elif event_type == "status_applied":
            narrative = self.tpl_status.format(count=count)
        elif event_type == "attack_performed":
            narrative = self.tpl_attack.format(count=count)
        else:
            return None

        if count >= self.major_min:
            severity = "major"
        elif count >= self.significant_min:
            severity = "significant"
        elif count >= self.moderate_min:
            severity = "moderate"
        else:
            severity = "minor"

        return InterpretedEvent.create(
            narrative=narrative,
            category="combat_style",
            severity=severity,
            trigger_event_id=trigger_event.event_id,
            trigger_count=trigger_event.interpretation_count,
            game_time=trigger_event.game_time,
            cause_event_ids=[],
            affected_locality_ids=[],
            affected_district_ids=[],
            epicenter_x=trigger_event.position_x,
            epicenter_y=trigger_event.position_y,
            affects_tags=[
                "event:combat",
                f"action:{event_type}",
            ],
            is_ongoing=True,
            expires_at=trigger_event.game_time + self.expiration_offset,
        )

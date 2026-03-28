"""Combat Boss Kills Evaluator — narrates individual boss kill events."""

from __future__ import annotations

from typing import Optional

from world_system.world_memory.config_loader import get_evaluator_config
from world_system.world_memory.event_schema import InterpretedEvent, WorldMemoryEvent
from world_system.world_memory.event_store import EventStore
from world_system.world_memory.geographic_registry import GeographicRegistry
from world_system.world_memory.entity_registry import EntityRegistry
from world_system.world_memory.interpreter import PatternEvaluator


class CombatBossKillsEvaluator(PatternEvaluator):

    RELEVANT_TYPES = {"enemy_killed"}

    def __init__(self):
        cfg = get_evaluator_config("combat_boss_kills")
        self.expiration_offset = cfg.get("expiration_offset", 500.0)
        self.major_tier_threshold = cfg.get("major_tier_threshold", 4)
        templates = cfg.get("narrative_templates", {})
        self.tpl_with_region = templates.get("with_region",
            "Player has defeated {enemy} in {region}.")
        self.tpl_no_region = templates.get("no_region",
            "Player has defeated {enemy} in the wilds.")

    def is_relevant(self, event: WorldMemoryEvent) -> bool:
        if event.event_type not in self.RELEVANT_TYPES:
            return False
        if "combat:boss" in event.tags:
            return True
        if event.context.get("is_boss"):
            return True
        return False

    def evaluate(self, trigger_event: WorldMemoryEvent,
                 event_store: EventStore,
                 geo_registry: GeographicRegistry,
                 entity_registry: EntityRegistry,
                 interpretation_store: EventStore) -> Optional[InterpretedEvent]:
        enemy_subtype = trigger_event.event_subtype
        enemy_name = enemy_subtype.replace("killed_", "").replace("_", " ")

        locality_id = trigger_event.locality_id
        if locality_id:
            region = geo_registry.regions.get(locality_id)
            region_name = region.name if region else locality_id
            narrative = self.tpl_with_region.format(
                enemy=enemy_name, region=region_name)
        else:
            narrative = self.tpl_no_region.format(enemy=enemy_name)

        tier = trigger_event.tier or 0
        if tier >= self.major_tier_threshold:
            severity = "major"
        else:
            severity = "significant"

        affected_locality_ids = [locality_id] if locality_id else []
        parent_id = None
        if locality_id:
            region = geo_registry.regions.get(locality_id)
            parent_id = region.parent_id if region else None

        return InterpretedEvent.create(
            narrative=narrative,
            category="combat_boss_kill",
            severity=severity,
            trigger_event_id=trigger_event.event_id,
            trigger_count=trigger_event.interpretation_count,
            game_time=trigger_event.game_time,
            cause_event_ids=[trigger_event.event_id],
            affected_locality_ids=affected_locality_ids,
            affected_district_ids=[parent_id] if parent_id else [],
            epicenter_x=trigger_event.position_x,
            epicenter_y=trigger_event.position_y,
            affects_tags=[
                f"species:{enemy_name.replace(' ', '_')}",
                "event:combat",
                "event:boss_kill",
            ],
            is_ongoing=False,
            expires_at=trigger_event.game_time + self.expiration_offset,
        )

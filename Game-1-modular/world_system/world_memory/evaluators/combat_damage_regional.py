"""Combat Damage Regional Evaluator — narrates damage taken and player death
counts within a specific region."""

from __future__ import annotations

from typing import Optional

from world_system.world_memory.config_loader import get_evaluator_config
from world_system.world_memory.event_schema import InterpretedEvent, WorldMemoryEvent
from world_system.world_memory.event_store import EventStore
from world_system.world_memory.geographic_registry import GeographicRegistry
from world_system.world_memory.entity_registry import EntityRegistry
from world_system.world_memory.interpreter import PatternEvaluator


class CombatDamageRegionalEvaluator(PatternEvaluator):

    RELEVANT_TYPES = {"damage_taken", "player_death"}

    def __init__(self):
        cfg = get_evaluator_config("combat_damage_regional")
        self.lookback_time = cfg.get("lookback_time", 60.0)
        self.expiration_offset = cfg.get("expiration_offset", 80.0)
        t = cfg.get("thresholds", {})
        self.min_damage_count = t.get("minimum_damage_count", 3)
        self.moderate_damage = t.get("moderate_damage_count", 8)
        self.significant_damage = t.get("significant_damage_count", 15)
        self.major_damage = t.get("major_damage_count", 30)
        self.min_death_count = t.get("minimum_death_count", 1)
        templates = cfg.get("narrative_templates", {})
        self.tpl_deaths = templates.get("deaths",
            "Player has nearly died in {region} {death_count} times.")
        self.tpl_damage = templates.get("damage",
            "Player has taken damage {damage_count} times in {region}.")

    def is_relevant(self, event: WorldMemoryEvent) -> bool:
        return event.event_type in self.RELEVANT_TYPES

    def evaluate(self, trigger_event: WorldMemoryEvent,
                 event_store: EventStore,
                 geo_registry: GeographicRegistry,
                 entity_registry: EntityRegistry,
                 interpretation_store: EventStore) -> Optional[InterpretedEvent]:
        locality_id = trigger_event.locality_id
        if not locality_id:
            return None

        damage_count = event_store.count_filtered(
            event_type="damage_taken",
            locality_id=locality_id,
            since_game_time=trigger_event.game_time - self.lookback_time,
        )
        death_count = event_store.count_filtered(
            event_type="player_death",
            locality_id=locality_id,
            since_game_time=trigger_event.game_time - self.lookback_time,
        )

        region = geo_registry.regions.get(locality_id)
        region_name = region.name if region else locality_id

        # Prefer death narration if deaths occurred
        if death_count >= self.min_death_count:
            narrative = self.tpl_deaths.format(
                region=region_name, death_count=death_count)
            if death_count >= 3:
                severity = "major"
            elif death_count >= 2:
                severity = "significant"
            else:
                severity = "moderate"
        elif damage_count >= self.min_damage_count:
            narrative = self.tpl_damage.format(
                region=region_name, damage_count=damage_count)
            if damage_count >= self.major_damage:
                severity = "major"
            elif damage_count >= self.significant_damage:
                severity = "significant"
            elif damage_count >= self.moderate_damage:
                severity = "moderate"
            else:
                severity = "minor"
        else:
            return None

        parent_id = region.parent_id if region else None
        return InterpretedEvent.create(
            narrative=narrative,
            category="combat_damage_regional",
            severity=severity,
            trigger_event_id=trigger_event.event_id,
            trigger_count=trigger_event.interpretation_count,
            game_time=trigger_event.game_time,
            cause_event_ids=[],
            affected_locality_ids=[locality_id],
            affected_district_ids=[parent_id] if parent_id else [],
            epicenter_x=trigger_event.position_x,
            epicenter_y=trigger_event.position_y,
            affects_tags=[
                f"biome:{trigger_event.biome}",
                "event:combat",
                "concern:safety",
            ],
            is_ongoing=True,
            expires_at=trigger_event.game_time + self.expiration_offset,
        )

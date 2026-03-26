"""Combat Kills Regional High Tier Evaluator — narrates high-tier enemy kill
counts within a specific region."""

from __future__ import annotations

from typing import Optional

from world_system.world_memory.config_loader import get_evaluator_config
from world_system.world_memory.event_schema import InterpretedEvent, WorldMemoryEvent
from world_system.world_memory.event_store import EventStore
from world_system.world_memory.geographic_registry import GeographicRegistry
from world_system.world_memory.entity_registry import EntityRegistry
from world_system.world_memory.interpreter import PatternEvaluator


class CombatKillsRegionalHighTierEvaluator(PatternEvaluator):

    RELEVANT_TYPES = {"enemy_killed"}

    def __init__(self):
        cfg = get_evaluator_config("combat_kills_regional_high_tier")
        self.lookback_time = cfg.get("lookback_time", 150.0)
        self.expiration_offset = cfg.get("expiration_offset", 150.0)
        t = cfg.get("thresholds", {})
        self.min_trigger = t.get("minimum_trigger", 1)
        self.moderate_min = t.get("moderate_min", 3)
        self.significant_min = t.get("significant_min", 5)
        self.major_min = t.get("major_min", 10)
        templates = cfg.get("narrative_templates", {})
        self.tpl = templates.get("default",
            "Player has killed {count} {enemy} (tier {tier}) in {region}.")

    def is_relevant(self, event: WorldMemoryEvent) -> bool:
        if event.event_type not in self.RELEVANT_TYPES:
            return False
        return event.tier is not None and event.tier >= 3

    def evaluate(self, trigger_event: WorldMemoryEvent,
                 event_store: EventStore,
                 geo_registry: GeographicRegistry,
                 entity_registry: EntityRegistry,
                 interpretation_store: EventStore) -> Optional[InterpretedEvent]:
        locality_id = trigger_event.locality_id
        if not locality_id:
            return None

        enemy_subtype = trigger_event.event_subtype
        count = event_store.count_filtered(
            event_type="enemy_killed",
            event_subtype=enemy_subtype,
            locality_id=locality_id,
            since_game_time=trigger_event.game_time - self.lookback_time,
        )

        if count < self.min_trigger:
            return None

        region = geo_registry.regions.get(locality_id)
        region_name = region.name if region else locality_id
        enemy_name = enemy_subtype.replace("killed_", "").replace("_", " ")
        tier = trigger_event.tier or 3

        if count >= self.major_min:
            severity = "major"
        elif count >= self.significant_min:
            severity = "significant"
        elif count >= self.moderate_min:
            severity = "moderate"
        else:
            severity = "minor"

        narrative = self.tpl.format(
            count=count, enemy=enemy_name, tier=tier, region=region_name)

        cause_events = event_store.query(
            event_type="enemy_killed",
            event_subtype=enemy_subtype,
            locality_id=locality_id,
            since_game_time=trigger_event.game_time - self.lookback_time,
            limit=10,
        )

        parent_id = region.parent_id if region else None
        return InterpretedEvent.create(
            narrative=narrative,
            category="combat_kills_regional",
            severity=severity,
            trigger_event_id=trigger_event.event_id,
            trigger_count=trigger_event.interpretation_count,
            game_time=trigger_event.game_time,
            cause_event_ids=[e.event_id for e in cause_events],
            affected_locality_ids=[locality_id],
            affected_district_ids=[parent_id] if parent_id else [],
            epicenter_x=trigger_event.position_x,
            epicenter_y=trigger_event.position_y,
            affects_tags=[
                f"species:{enemy_name.replace(' ', '_')}",
                f"tier:{tier}",
                f"biome:{trigger_event.biome}",
                "event:combat",
            ],
            is_ongoing=True,
            expires_at=trigger_event.game_time + self.expiration_offset,
        )

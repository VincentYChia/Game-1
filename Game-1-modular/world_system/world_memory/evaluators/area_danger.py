"""Area Danger Evaluator — detects when an area becomes more or less dangerous."""

from __future__ import annotations

from typing import Optional

from world_system.world_memory.config_loader import get_evaluator_config
from world_system.world_memory.event_schema import InterpretedEvent, WorldMemoryEvent
from world_system.world_memory.event_store import EventStore
from world_system.world_memory.geographic_registry import GeographicRegistry
from world_system.world_memory.entity_registry import EntityRegistry
from world_system.world_memory.interpreter import PatternEvaluator


class AreaDangerEvaluator(PatternEvaluator):

    RELEVANT_TYPES = {"damage_taken", "player_death"}

    def __init__(self):
        cfg = get_evaluator_config("area_danger")
        self.lookback_time = cfg.get("lookback_time", 30.0)
        self.expiration_offset = cfg.get("expiration_offset", 50.0)
        self.death_weight = cfg.get("death_weight_multiplier", 10)
        t = cfg.get("thresholds", {})
        self.min_threat = t.get("minimum_threat_score", 5)
        self.moderate_threat = t.get("moderate_threat_score", 10)
        self.significant_threat = t.get("significant_threat_score", 20)
        self.significant_deaths = t.get("significant_death_count", 1)
        self.major_deaths = t.get("major_death_count", 3)
        templates = cfg.get("narrative_templates", {})
        self.tpl_major = templates.get("major",
            "{region} is extremely dangerous. The adventurer has died "
            "{deaths} times here recently. This area poses a serious threat.")
        self.tpl_significant_death = templates.get("significant_death",
            "{region} has proven hazardous. Frequent combat injuries and "
            "a death mark this area as dangerous.")
        self.tpl_significant_deaths = templates.get("significant_deaths",
            "{region} has proven hazardous. Frequent combat injuries and "
            "deaths mark this area as dangerous.")
        self.tpl_moderate = templates.get("moderate",
            "Combat activity is elevated in {region}. "
            "The adventurer has taken repeated damage here.")
        self.tpl_minor = templates.get("minor",
            "Some combat encounters in {region}.")

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

        damage_events = event_store.count_filtered(
            event_type="damage_taken",
            locality_id=locality_id,
            since_game_time=trigger_event.game_time - self.lookback_time,
        )
        death_events = event_store.count_filtered(
            event_type="player_death",
            locality_id=locality_id,
            since_game_time=trigger_event.game_time - self.lookback_time,
        )

        threat_score = damage_events + death_events * self.death_weight

        if threat_score < self.min_threat:
            return None

        region = geo_registry.regions.get(locality_id)
        region_name = region.name if region else locality_id

        if death_events >= self.major_deaths:
            severity = "major"
            narrative = self.tpl_major.format(
                region=region_name, deaths=death_events)
        elif death_events >= self.significant_deaths or threat_score >= self.significant_threat:
            severity = "significant"
            if death_events == 1:
                narrative = self.tpl_significant_death.format(region=region_name)
            else:
                narrative = self.tpl_significant_deaths.format(region=region_name)
        elif threat_score >= self.moderate_threat:
            severity = "moderate"
            narrative = self.tpl_moderate.format(region=region_name)
        else:
            severity = "minor"
            narrative = self.tpl_minor.format(region=region_name)

        parent_id = region.parent_id if region else None
        return InterpretedEvent.create(
            narrative=narrative,
            category="area_danger",
            severity=severity,
            trigger_event_id=trigger_event.event_id,
            trigger_count=trigger_event.interpretation_count,
            game_time=trigger_event.game_time,
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

"""Population Change Evaluator — detects when enemy kills in a region
exceed natural recovery thresholds."""

from __future__ import annotations

from typing import Optional

from world_memory.memory.config_loader import get_evaluator_config
from world_memory.memory.event_schema import InterpretedEvent, WorldMemoryEvent
from world_memory.memory.event_store import EventStore
from world_memory.memory.geographic_registry import GeographicRegistry
from world_memory.memory.entity_registry import EntityRegistry
from world_memory.memory.interpreter import PatternEvaluator


class PopulationChangeEvaluator(PatternEvaluator):

    RELEVANT_TYPES = {"enemy_killed"}

    def __init__(self):
        cfg = get_evaluator_config("population_change")
        self.lookback_time = cfg.get("lookback_time", 50.0)
        self.expiration_offset = cfg.get("expiration_offset", 100.0)
        t = cfg.get("thresholds", {})
        self.min_trigger = t.get("minimum_trigger", 5)
        self.moderate_min = t.get("moderate_min", 10)
        self.significant_min = t.get("significant_min", 20)
        self.major_min = t.get("major_min", 50)
        templates = cfg.get("narrative_templates", {})
        self.tpl_major = templates.get("major",
            "The {enemy} population has been devastated in {region}. "
            "{count} have been killed in a short period. "
            "The species may take significant time to recover in this area.")
        self.tpl_significant = templates.get("significant",
            "{enemy} numbers are noticeably declining in {region}. "
            "{count} have been killed recently.")
        self.tpl_moderate = templates.get("moderate",
            "Increased hunting activity has thinned the {enemy} population "
            "in {region}.")
        self.tpl_minor = templates.get("minor",
            "Several {enemy}s have been killed in {region}.")

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

        enemy_subtype = trigger_event.event_subtype
        recent_kills = event_store.count_filtered(
            event_type="enemy_killed",
            event_subtype=enemy_subtype,
            locality_id=locality_id,
            since_game_time=trigger_event.game_time - self.lookback_time,
        )

        if recent_kills < self.min_trigger:
            return None

        region = geo_registry.regions.get(locality_id)
        region_name = region.name if region else locality_id
        enemy_name = enemy_subtype.replace("killed_", "").replace("_", " ")

        if recent_kills >= self.major_min:
            severity = "major"
            narrative = self.tpl_major.format(
                enemy=enemy_name, region=region_name, count=recent_kills)
        elif recent_kills >= self.significant_min:
            severity = "significant"
            narrative = self.tpl_significant.format(
                enemy=enemy_name, region=region_name, count=recent_kills)
        elif recent_kills >= self.moderate_min:
            severity = "moderate"
            narrative = self.tpl_moderate.format(
                enemy=enemy_name, region=region_name, count=recent_kills)
        else:
            severity = "minor"
            narrative = self.tpl_minor.format(
                enemy=enemy_name, region=region_name, count=recent_kills)

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
            category="population_change",
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
                f"biome:{trigger_event.biome}",
            ],
            is_ongoing=True,
            expires_at=trigger_event.game_time + self.expiration_offset,
        )

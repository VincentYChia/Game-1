"""Resource Pressure Evaluator — detects when gathering outpaces
regeneration in an area."""

from __future__ import annotations

from typing import Optional

from world_system.world_memory.config_loader import get_evaluator_config
from world_system.world_memory.event_schema import InterpretedEvent, WorldMemoryEvent
from world_system.world_memory.event_store import EventStore
from world_system.world_memory.geographic_registry import GeographicRegistry
from world_system.world_memory.entity_registry import EntityRegistry
from world_system.world_memory.interpreter import PatternEvaluator


class ResourcePressureEvaluator(PatternEvaluator):

    RELEVANT_TYPES = {"resource_gathered", "node_depleted"}

    def __init__(self):
        cfg = get_evaluator_config("resource_pressure")
        self.lookback_time = cfg.get("lookback_time", 50.0)
        self.expiration_offset = cfg.get("expiration_offset", 75.0)
        t = cfg.get("thresholds", {})
        self.min_trigger = t.get("minimum_trigger", 10)
        self.moderate_min = t.get("moderate_min", 25)
        self.significant_min = t.get("significant_min", 50)
        self.major_min = t.get("major_min", 100)
        templates = cfg.get("narrative_templates", {})
        self.tpl_major = templates.get("major",
            "{resource} deposits are critically strained in {region}. "
            "Over {count} units have been harvested recently, far outpacing "
            "natural regeneration.")
        self.tpl_significant = templates.get("significant",
            "{resource} is becoming scarce in {region}. "
            "Heavy harvesting ({count} units) is depleting available nodes.")
        self.tpl_moderate = templates.get("moderate",
            "Notable {resource} harvesting activity in {region}. "
            "Resource availability may be declining.")
        self.tpl_minor = templates.get("minor",
            "Steady {resource} gathering is underway in {region}.")

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

        subtype = trigger_event.event_subtype
        resource_name = subtype.replace("gathered_", "").replace("_", " ")

        recent_gathers = event_store.count_filtered(
            event_type="resource_gathered",
            event_subtype=subtype,
            locality_id=locality_id,
            since_game_time=trigger_event.game_time - self.lookback_time,
        )

        if recent_gathers < self.min_trigger:
            return None

        region = geo_registry.regions.get(locality_id)
        region_name = region.name if region else locality_id

        if recent_gathers >= self.major_min:
            severity = "major"
            narrative = self.tpl_major.format(
                resource=resource_name.title(), region=region_name, count=recent_gathers)
        elif recent_gathers >= self.significant_min:
            severity = "significant"
            narrative = self.tpl_significant.format(
                resource=resource_name.title(), region=region_name, count=recent_gathers)
        elif recent_gathers >= self.moderate_min:
            severity = "moderate"
            narrative = self.tpl_moderate.format(
                resource=resource_name, region=region_name, count=recent_gathers)
        else:
            severity = "minor"
            narrative = self.tpl_minor.format(
                resource=resource_name, region=region_name, count=recent_gathers)

        parent_id = region.parent_id if region else None
        return InterpretedEvent.create(
            narrative=narrative,
            category="resource_pressure",
            severity=severity,
            trigger_event_id=trigger_event.event_id,
            trigger_count=trigger_event.interpretation_count,
            game_time=trigger_event.game_time,
            affected_locality_ids=[locality_id],
            affected_district_ids=[parent_id] if parent_id else [],
            epicenter_x=trigger_event.position_x,
            epicenter_y=trigger_event.position_y,
            affects_tags=[
                f"resource:{resource_name.replace(' ', '_')}",
                f"biome:{trigger_event.biome}",
            ],
            is_ongoing=True,
            expires_at=trigger_event.game_time + self.expiration_offset,
        )

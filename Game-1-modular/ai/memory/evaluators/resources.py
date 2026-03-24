"""Resource Pressure Evaluator — detects when gathering outpaces
regeneration in an area."""

from __future__ import annotations

from typing import Optional

from ai.memory.event_schema import InterpretedEvent, WorldMemoryEvent
from ai.memory.event_store import EventStore
from ai.memory.geographic_registry import GeographicRegistry
from ai.memory.entity_registry import EntityRegistry
from ai.memory.interpreter import PatternEvaluator


class ResourcePressureEvaluator(PatternEvaluator):

    RELEVANT_TYPES = {"resource_gathered", "node_depleted"}
    LOOKBACK_TIME = 50.0

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
            since_game_time=trigger_event.game_time - self.LOOKBACK_TIME,
        )

        if recent_gathers < 10:
            return None

        region = geo_registry.regions.get(locality_id)
        region_name = region.name if region else locality_id

        if recent_gathers >= 100:
            severity = "major"
            narrative = (
                f"{resource_name.title()} deposits are critically strained in {region_name}. "
                f"Over {recent_gathers} units have been harvested recently, far outpacing "
                f"natural regeneration."
            )
        elif recent_gathers >= 50:
            severity = "significant"
            narrative = (
                f"{resource_name.title()} is becoming scarce in {region_name}. "
                f"Heavy harvesting ({recent_gathers} units) is depleting available nodes."
            )
        elif recent_gathers >= 25:
            severity = "moderate"
            narrative = (
                f"Notable {resource_name} harvesting activity in {region_name}. "
                f"Resource availability may be declining."
            )
        else:
            severity = "minor"
            narrative = (
                f"Steady {resource_name} gathering is underway in {region_name}."
            )

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
            expires_at=trigger_event.game_time + 75.0,
        )

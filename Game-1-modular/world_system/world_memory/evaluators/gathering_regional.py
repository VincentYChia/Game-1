"""Gathering Regional Evaluator — narrates per-resource gathering totals
within a locality."""

from __future__ import annotations

from typing import Optional

from world_system.world_memory.config_loader import get_evaluator_config
from world_system.world_memory.event_schema import InterpretedEvent, WorldMemoryEvent
from world_system.world_memory.event_store import EventStore
from world_system.world_memory.geographic_registry import GeographicRegistry
from world_system.world_memory.entity_registry import EntityRegistry
from world_system.world_memory.interpreter import PatternEvaluator


class GatheringRegionalEvaluator(PatternEvaluator):
    """Reports how much of a specific resource the player has gathered
    in a particular locality within the lookback window."""

    RELEVANT_TYPES = {"resource_gathered"}

    def __init__(self):
        cfg = get_evaluator_config("gathering_regional")
        self.lookback_time = cfg.get("lookback_time", 100.0)
        self.expiration_offset = cfg.get("expiration_offset", 150.0)
        t = cfg.get("thresholds", {})
        self.minor_max = t.get("minor_max", 10)
        self.moderate_max = t.get("moderate_max", 30)
        self.significant_max = t.get("significant_max", 60)
        templates = cfg.get("narrative_templates", {})
        self.tpl = templates.get(
            "default",
            "Player has gathered {count} {resource} in {region}.",
        )

    def is_relevant(self, event: WorldMemoryEvent) -> bool:
        return event.event_type in self.RELEVANT_TYPES

    def evaluate(
        self,
        trigger_event: WorldMemoryEvent,
        event_store: EventStore,
        geo_registry: GeographicRegistry,
        entity_registry: EntityRegistry,
        interpretation_store: EventStore,
    ) -> Optional[InterpretedEvent]:
        locality_id = trigger_event.locality_id
        if not locality_id:
            return None

        subtype = trigger_event.event_subtype
        resource_name = subtype.replace("gathered_", "").replace("_", " ")

        count = event_store.count_filtered(
            event_type="resource_gathered",
            event_subtype=subtype,
            locality_id=locality_id,
            since_game_time=trigger_event.game_time - self.lookback_time,
        )

        if count < 1:
            return None

        region = geo_registry.regions.get(locality_id)
        region_name = region.name if region else locality_id

        if count < self.minor_max:
            severity = "minor"
        elif count < self.moderate_max:
            severity = "moderate"
        elif count < self.significant_max:
            severity = "significant"
        else:
            severity = "major"

        narrative = self.tpl.format(
            count=count,
            resource=resource_name,
            region=region_name,
        )

        parent_id = region.parent_id if region else None
        return InterpretedEvent.create(
            narrative=narrative,
            category="gathering_regional",
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

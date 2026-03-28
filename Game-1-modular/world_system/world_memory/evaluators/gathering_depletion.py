"""Gathering Depletion Evaluator — narrates how many resource nodes the
player has depleted in a locality.

LAYER 1 DEPENDENCY: Currently narrates raw depletion count. To narrate
percentages (e.g., "45% of oak trees harvested in region"), needs total
node count per chunk from Layer 1. Layer 1 tracks nodes_depleted counts
but not total available nodes per chunk/region. This requires either:
  1. WorldSystem to publish total node count per chunk on generation, or
  2. A new stat_tracker method to record initial node counts per region.
"""

from __future__ import annotations

from typing import Optional

from world_system.world_memory.config_loader import get_evaluator_config
from world_system.world_memory.event_schema import InterpretedEvent, WorldMemoryEvent
from world_system.world_memory.event_store import EventStore
from world_system.world_memory.geographic_registry import GeographicRegistry
from world_system.world_memory.entity_registry import EntityRegistry
from world_system.world_memory.interpreter import PatternEvaluator


class GatheringDepletionEvaluator(PatternEvaluator):
    """Reports how many resource nodes have been depleted in a locality
    within the lookback window."""

    RELEVANT_TYPES = {"node_depleted"}

    def __init__(self):
        cfg = get_evaluator_config("gathering_depletion")
        self.lookback_time = cfg.get("lookback_time", 100.0)
        self.expiration_offset = cfg.get("expiration_offset", 150.0)
        t = cfg.get("thresholds", {})
        self.min_trigger = t.get("minimum_trigger", 1)
        self.minor_max = t.get("minor_max", 3)
        self.moderate_max = t.get("moderate_max", 8)
        self.significant_max = t.get("significant_max", 15)
        templates = cfg.get("narrative_templates", {})
        self.tpl = templates.get(
            "default",
            "Player has depleted {count} resource nodes in {region}.",
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

        count = event_store.count_filtered(
            event_type="node_depleted",
            locality_id=locality_id,
            since_game_time=trigger_event.game_time - self.lookback_time,
        )

        if count < self.min_trigger:
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
            region=region_name,
        )

        parent_id = region.parent_id if region else None
        return InterpretedEvent.create(
            narrative=narrative,
            category="gathering_depletion",
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
            ],
            is_ongoing=True,
            expires_at=trigger_event.game_time + self.expiration_offset,
        )

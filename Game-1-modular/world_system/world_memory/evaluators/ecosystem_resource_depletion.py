"""Ecosystem Resource Depletion Evaluator — tracks resource node
depletion at the ecosystem level (3x3 chunks).

LAYER 2 evaluator that produces resource_harvesting tags.
These are FACTUAL observations ("50% of nodes are depleted")
that Layer 3 inherits and interprets as resource_status
("scarce", "critical", "depleted").

Gate: only tracks ecosystems with >= 5 resource nodes.
Lock: after any threshold fires, locks until 90% replenished.
"""

from __future__ import annotations

from typing import Dict, Optional, Tuple

from world_system.world_memory.event_schema import InterpretedEvent, WorldMemoryEvent
from world_system.world_memory.event_store import EventStore
from world_system.world_memory.geographic_registry import GeographicRegistry
from world_system.world_memory.entity_registry import EntityRegistry
from world_system.world_memory.interpreter import PatternEvaluator


# Minimum resource nodes in an ecosystem to be worth tracking
MIN_NODES_TO_TRACK = 5

# Ecosystem = 3x3 chunks
ECO_SIZE = 3


class EcosystemResourceDepletionEvaluator(PatternEvaluator):
    """Reports resource depletion at ecosystem scale (3x3 chunks).

    Fires at 50%, 75%, 90%, and 100% depletion thresholds.
    Locks after firing until resources recover to 90%+ (depletion < 10%).
    """

    RELEVANT_TYPES = {"resource_gathered", "node_depleted"}

    def __init__(self):
        # State per ecosystem: {eco_key: {initial, depleted, locked, last_threshold}}
        self._eco_state: Dict[Tuple[int, int], Dict] = {}

    def _get_eco_key(self, x: float, y: float) -> Tuple[int, int]:
        """Convert world position to ecosystem grid key."""
        chunk_x = int(x) // 16
        chunk_y = int(y) // 16
        eco_x = chunk_x // ECO_SIZE
        eco_y = chunk_y // ECO_SIZE
        return (eco_x, eco_y)

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
        if not trigger_event.position_x or not trigger_event.position_y:
            return None

        eco_key = self._get_eco_key(trigger_event.position_x, trigger_event.position_y)

        # Initialize ecosystem state if needed
        if eco_key not in self._eco_state:
            self._eco_state[eco_key] = {
                "initial": 0,
                "depleted": 0,
                "locked": False,
                "last_threshold": 0.0,
            }

        state = self._eco_state[eco_key]

        # Count resource events in this ecosystem area
        # Use event_store to count depletions in the area
        eco_chunk_x = eco_key[0] * ECO_SIZE
        eco_chunk_y = eco_key[1] * ECO_SIZE

        # Count total nodes and depleted nodes from event history
        total_gathers = event_store.count_filtered(
            event_type="resource_gathered",
            chunk_x_min=eco_chunk_x * 16,
            chunk_x_max=(eco_chunk_x + ECO_SIZE) * 16,
        ) if hasattr(event_store, 'count_filtered') else 0

        total_depletions = event_store.count_filtered(
            event_type="node_depleted",
            chunk_x_min=eco_chunk_x * 16,
            chunk_x_max=(eco_chunk_x + ECO_SIZE) * 16,
        ) if hasattr(event_store, 'count_filtered') else 0

        # Estimate initial nodes from total activity
        # Each node produces ~5-10 gather events before depletion
        estimated_initial = max(MIN_NODES_TO_TRACK, total_depletions + max(1, total_gathers // 8))
        state["initial"] = max(state["initial"], estimated_initial)
        state["depleted"] = total_depletions

        # Gate: not enough nodes to be meaningful
        if state["initial"] < MIN_NODES_TO_TRACK:
            return None

        depletion_ratio = state["depleted"] / max(1, state["initial"])

        # Check for recovery (unlock)
        if state["locked"] and depletion_ratio < 0.10:
            state["locked"] = False
            state["last_threshold"] = 0.0

            locality_id = trigger_event.locality_id
            region = geo_registry.regions.get(locality_id) if locality_id else None
            region_name = region.name if region else "the area"

            # Get resource category from event tags
            resource_cat = self._get_resource_category(trigger_event)

            return InterpretedEvent.create(
                narrative=f"{resource_cat.title()} around {region_name} has largely recovered. Fresh sources have returned.",
                category="ecosystem_resource_depletion",
                severity="minor",
                trigger_event_id=trigger_event.event_id,
                trigger_count=trigger_event.interpretation_count,
                game_time=trigger_event.game_time,
                affected_locality_ids=[locality_id] if locality_id else [],
                epicenter_x=trigger_event.position_x,
                epicenter_y=trigger_event.position_y,
                affects_tags=[
                    "resource_harvesting:recovering",
                    "domain:gathering",
                    "scope:local",
                    "metric:percentage",
                    "target:node",
                ],
                is_ongoing=False,
                expires_at=trigger_event.game_time + 200.0,
            )

        # If locked, don't fire any thresholds
        if state["locked"]:
            return None

        # Determine which threshold to fire
        threshold = None
        harvesting_tag = None
        severity = None
        narrative_template = None

        if depletion_ratio >= 1.0 and state["last_threshold"] < 1.0:
            threshold = 1.0
            harvesting_tag = "resource_harvesting:exhausted"
            severity = "major"
            narrative_template = "Every {resource} source around {region} has been exhausted."
        elif depletion_ratio >= 0.90 and state["last_threshold"] < 0.90:
            threshold = 0.90
            harvesting_tag = "resource_harvesting:depleted_90"
            severity = "major"
            narrative_template = "{region} has been stripped nearly bare of {resource}. Recovery will take time."
        elif depletion_ratio >= 0.75 and state["last_threshold"] < 0.75:
            threshold = 0.75
            harvesting_tag = "resource_harvesting:depleted_75"
            severity = "significant"
            narrative_template = "Only scattered {resource} remains near {region}. Gatherers will need to range further."
        elif depletion_ratio >= 0.50 and state["last_threshold"] < 0.50:
            threshold = 0.50
            harvesting_tag = "resource_harvesting:depleted_50"
            severity = "moderate"
            narrative_template = "About half the {resource} around {region} has been harvested. The land still provides, but noticeably less."

        if threshold is None:
            return None

        # Fire threshold
        state["last_threshold"] = threshold
        state["locked"] = True

        locality_id = trigger_event.locality_id
        region = geo_registry.regions.get(locality_id) if locality_id else None
        region_name = region.name if region else "the area"
        resource_cat = self._get_resource_category(trigger_event)

        narrative = narrative_template.format(
            resource=resource_cat,
            region=region_name,
        )

        parent_id = region.parent_id if region else None
        return InterpretedEvent.create(
            narrative=narrative,
            category="ecosystem_resource_depletion",
            severity=severity,
            trigger_event_id=trigger_event.event_id,
            trigger_count=trigger_event.interpretation_count,
            game_time=trigger_event.game_time,
            affected_locality_ids=[locality_id] if locality_id else [],
            affected_district_ids=[parent_id] if parent_id else [],
            epicenter_x=trigger_event.position_x,
            epicenter_y=trigger_event.position_y,
            affects_tags=[
                harvesting_tag,
                "domain:gathering",
                "action:deplete",
                "scope:local",
                "metric:percentage",
                "target:node",
                f"biome:{trigger_event.biome}" if trigger_event.biome else "",
            ],
            is_ongoing=True,
            expires_at=trigger_event.game_time + 300.0,
        )

    def _get_resource_category(self, event: WorldMemoryEvent) -> str:
        """Extract resource category from event tags."""
        for tag in (event.tags or []):
            if tag.startswith("material_category:"):
                return tag.split(":", 1)[1]
            if tag.startswith("resource:"):
                val = tag.split(":", 1)[1]
                if "tree" in val or "sapling" in val:
                    return "timber"
                if "ore" in val or "vein" in val or "deposit" in val or "cache" in val:
                    return "ore"
                if "stone" in val or "quarry" in val or "formation" in val:
                    return "stone"
        return "resources"

"""Ecosystem Resource Depletion Evaluator — produces resource_harvesting
events at ecosystem-level depletion milestones.

LAYER 2 evaluator. Produces standalone InterpretedEvents (its own events,
not tags on other events) when resource depletion crosses thresholds
at the ecosystem level (3x3 chunks).

Thresholds (can only progress downward):
  50% depleted → resource_harvesting:depleted_50
  75% depleted → resource_harvesting:scarce
  90% depleted → resource_harvesting:exhausted
  100% depleted → resource_harvesting:completely_harvested

Resets when ecosystem reaches 90% replenishment (depletion < 10%).
Only tracks ecosystems with >= 5 resource nodes.
"""

from __future__ import annotations

from typing import Dict, Optional, Tuple

from world_system.world_memory.config_loader import get_evaluator_config
from world_system.world_memory.event_schema import InterpretedEvent, WorldMemoryEvent
from world_system.world_memory.event_store import EventStore
from world_system.world_memory.geographic_registry import GeographicRegistry
from world_system.world_memory.entity_registry import EntityRegistry
from world_system.world_memory.interpreter import PatternEvaluator


# §15 trap 9: module-level constants kept for backwards compatibility,
# but the canonical values now come from
# ``memory-config.json > evaluators.ecosystem_resource_depletion``.
MIN_NODES_TO_TRACK = 5
ECO_CHUNK_SIZE = 3  # 3x3 chunks per ecosystem

_DEFAULT_THRESHOLDS = [
    (0.50, "depleted_50", "moderate",
     "About half the {resource} around {region} has been harvested."),
    (0.75, "scarce", "significant",
     "Only scattered {resource} remains near {region}. Sources are becoming scarce."),
    (0.90, "exhausted", "major",
     "{region} has been nearly stripped of {resource}. Very little remains."),
    (1.00, "completely_harvested", "major",
     "Every {resource} source around {region} has been exhausted."),
]

THRESHOLDS = list(_DEFAULT_THRESHOLDS)  # public alias kept for tests/imports


def _load_config_thresholds():
    """Build the threshold list from
    ``memory-config.json > ecosystem_resource_depletion``. Falls back
    to the module-level defaults if the JSON is incomplete."""
    cfg = get_evaluator_config("ecosystem_resource_depletion", default={})
    t = cfg.get("thresholds", {}) or {}
    nt = cfg.get("narrative_templates", {}) or {}

    def build(name: str, ratio_key: str, default_ratio: float,
              severity: str, default_text: str):
        return (
            float(t.get(ratio_key, default_ratio)),
            name,
            severity,
            nt.get(name, default_text),
        )

    return [
        build("depleted_50", "depleted_50_pct", 0.50, "moderate",
              "About half the {resource} around {region} has been harvested."),
        build("scarce", "scarce_pct", 0.75, "significant",
              "Only scattered {resource} remains near {region}. Sources are becoming scarce."),
        build("exhausted", "exhausted_pct", 0.90, "major",
              "{region} has been nearly stripped of {resource}. Very little remains."),
        build("completely_harvested", "completely_harvested_pct", 1.00, "major",
              "Every {resource} source around {region} has been exhausted."),
    ]


class EcosystemResourceDepletionEvaluator(PatternEvaluator):
    """Produces resource_harvesting events at ecosystem depletion milestones."""

    RELEVANT_TYPES = {"resource_gathered", "node_depleted"}

    def __init__(self):
        cfg = get_evaluator_config("ecosystem_resource_depletion", default={})
        self.min_nodes_to_track = int(cfg.get("min_nodes_to_track", MIN_NODES_TO_TRACK))
        self.eco_chunk_size = int(cfg.get("ecosystem_chunk_size", ECO_CHUNK_SIZE))
        self._thresholds = _load_config_thresholds()
        self._reset_below = float(
            cfg.get("thresholds", {}).get("reset_when_replenished_below_pct", 0.10)
        )
        # Per-ecosystem state: {eco_key: {"initial": int, "depleted": int, "threshold_idx": int}}
        # threshold_idx tracks how far down the threshold list we've fired
        # -1 = no thresholds fired yet
        self._state: Dict[Tuple[int, int], Dict] = {}

    def _eco_key(self, x: float, y: float) -> Tuple[int, int]:
        chunk_x = int(x) // 16
        chunk_y = int(y) // 16
        return (chunk_x // self.eco_chunk_size, chunk_y // self.eco_chunk_size)

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

        key = self._eco_key(trigger_event.position_x, trigger_event.position_y)

        # Initialize state
        if key not in self._state:
            self._state[key] = {"initial": 0, "depleted": 0, "threshold_idx": -1}
        state = self._state[key]

        # Update counts from event
        if trigger_event.event_type == "node_depleted":
            state["depleted"] += 1
            # Estimate initial from depletions seen (conservative)
            state["initial"] = max(state["initial"], state["depleted"])
        elif trigger_event.event_type == "resource_gathered":
            # Each gather contributes to our estimate of total nodes
            state["initial"] = max(state["initial"], state["depleted"] + 1)

        # Gate: not enough nodes
        if state["initial"] < self.min_nodes_to_track:
            return None

        ratio = state["depleted"] / state["initial"]

        # Check for replenishment reset (configurable)
        if state["threshold_idx"] >= 0 and ratio < self._reset_below:
            state["threshold_idx"] = -1
            # No event produced on reset — just silently unlocks
            return None

        # Find the next threshold to fire (can only go DOWN the list)
        next_idx = state["threshold_idx"] + 1
        if next_idx >= len(self._thresholds):
            return None  # All thresholds already fired

        threshold_ratio, tag_value, severity, template = self._thresholds[next_idx]

        if ratio < threshold_ratio:
            return None  # Haven't reached next threshold yet

        # Fire this threshold
        state["threshold_idx"] = next_idx

        # Build event
        locality_id = trigger_event.locality_id
        region = geo_registry.regions.get(locality_id) if locality_id else None
        region_name = region.name if region else "the area"

        resource_cat = "resources"
        for tag in (trigger_event.tags or []):
            if tag.startswith("material_category:"):
                resource_cat = tag.split(":", 1)[1]
                break

        narrative = template.format(resource=resource_cat, region=region_name)

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
                f"resource_harvesting:{tag_value}",
                "domain:gathering",
                "action:deplete",
                "scope:local",
                "metric:percentage",
                "target:node",
            ],
            is_ongoing=True,
            expires_at=trigger_event.game_time + 300.0,
        )

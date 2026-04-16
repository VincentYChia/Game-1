"""Fishing Activity Evaluator — narrates fish catches within a locality.

Listens to FISH_CAUGHT events (published by game_engine._complete_fishing_minigame)
and reports regional fishing activity. Fires on every catch, escalating severity
based on count within the lookback window.

Fishing is a gathering sub-discipline: events carry `domain:fishing` and are
routed through the same geographic pipeline as other gathering evaluators.
"""

from __future__ import annotations

from typing import Optional

from world_system.world_memory.config_loader import get_evaluator_config
from world_system.world_memory.event_schema import InterpretedEvent, WorldMemoryEvent
from world_system.world_memory.event_store import EventStore
from world_system.world_memory.geographic_registry import GeographicRegistry
from world_system.world_memory.entity_registry import EntityRegistry
from world_system.world_memory.interpreter import PatternEvaluator


class FishingActivityEvaluator(PatternEvaluator):
    """Reports regional fish-catch totals within a configurable lookback window.

    Fires on every FISH_CAUGHT event. Severity escalates as the player
    catches more fish in one location (minor → major). Rare/legendary
    catches always fire at least moderate severity regardless of count.
    """

    RELEVANT_TYPES = {"fish_caught"}

    # Rarities that boost severity by one tier (cap at major)
    _RARE_RARITIES = {"rare", "legendary", "epic"}

    def __init__(self):
        cfg = get_evaluator_config("fishing_activity")
        self.lookback_time = cfg.get("lookback_time", 80.0)
        self.expiration_offset = cfg.get("expiration_offset", 120.0)
        t = cfg.get("thresholds", {})
        self.minor_max = t.get("minor_max", 3)
        self.moderate_max = t.get("moderate_max", 10)
        self.significant_max = t.get("significant_max", 25)
        templates = cfg.get("narrative_templates", {})
        self.tpl_region = templates.get(
            "with_region",
            "Player has caught {count} fish in {region}.",
        )
        self.tpl_global = templates.get(
            "no_region",
            "Player has caught {count} fish.",
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

        # Count all fish caught in this locality within the lookback window
        count = event_store.count_filtered(
            event_type="fish_caught",
            locality_id=locality_id or "",
            since_game_time=trigger_event.game_time - self.lookback_time,
        )

        if count < 1:
            return None

        # Determine base severity from count
        if count < self.minor_max:
            severity = "minor"
        elif count < self.moderate_max:
            severity = "moderate"
        elif count < self.significant_max:
            severity = "significant"
        else:
            severity = "major"

        # Rare/legendary catches boost severity by one tier
        rarity = trigger_event.quality or ""
        if rarity in self._RARE_RARITIES:
            _order = ["minor", "moderate", "significant", "major", "critical"]
            idx = _order.index(severity)
            severity = _order[min(idx + 1, len(_order) - 1)]

        # Build narrative
        if locality_id:
            region = geo_registry.regions.get(locality_id)
            region_name = region.name if region else locality_id
            narrative = self.tpl_region.format(count=count, region=region_name)
        else:
            narrative = self.tpl_global.format(count=count)

        # Extract fish species from subtype (caught_salmon → salmon)
        fish_species = trigger_event.event_subtype or "fish"
        if fish_species.startswith("caught_"):
            fish_species = fish_species[len("caught_"):].replace("_", " ")

        affected_locality_ids = [locality_id] if locality_id else []
        parent_id = None
        if locality_id:
            region = geo_registry.regions.get(locality_id)
            parent_id = region.parent_id if region else None

        affects_tags = [
            "domain:fishing",
            f"resource:{fish_species.replace(' ', '_')}",
        ]
        if rarity:
            affects_tags.append(f"rarity:{rarity}")

        return InterpretedEvent.create(
            narrative=narrative,
            category="fishing_activity",
            severity=severity,
            trigger_event_id=trigger_event.event_id,
            trigger_count=trigger_event.interpretation_count,
            game_time=trigger_event.game_time,
            affected_locality_ids=affected_locality_ids,
            affected_district_ids=[parent_id] if parent_id else [],
            epicenter_x=trigger_event.position_x,
            epicenter_y=trigger_event.position_y,
            affects_tags=affects_tags,
            is_ongoing=True,
            expires_at=trigger_event.game_time + self.expiration_offset,
        )

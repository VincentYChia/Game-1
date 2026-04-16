"""Turret / Barrier Activity Evaluator — narrates player defense deployments.

Listens to TURRET_PLACED and BARRIER_PLACED events (published by
game_engine on placement) and reports regional deployment activity.
Fires on every placement, escalating severity based on how many
defensive structures have been placed in the locality.

Turret *kills* are intentionally NOT counted here — they flow through
the existing ENEMY_KILLED pipeline (with source:turret) so that all
combat evaluators (regional, global, boss) already handle them without
duplication. This evaluator focuses purely on the *placement / fortification*
behaviour: how aggressively is the player building defenses in an area.

Both TURRET_PLACED and BARRIER_PLACED carry `domain:engineering` tags,
so they contribute to the same engineering narrative layer.
"""

from __future__ import annotations

from typing import Optional

from world_system.world_memory.config_loader import get_evaluator_config
from world_system.world_memory.event_schema import InterpretedEvent, WorldMemoryEvent
from world_system.world_memory.event_store import EventStore
from world_system.world_memory.geographic_registry import GeographicRegistry
from world_system.world_memory.entity_registry import EntityRegistry
from world_system.world_memory.interpreter import PatternEvaluator


class TurretActivityEvaluator(PatternEvaluator):
    """Reports regional turret and barrier deployment counts.

    Fires on every TURRET_PLACED or BARRIER_PLACED event.
    Severity escalates as more defensive structures are deployed in
    one location (minor → major). High-tier deployments boost severity
    by one step, reflecting the significance of investing expensive
    materials in fortifications.

    Produces separate narratives for turrets vs barriers, but uses a
    combined locality count for severity so that mixed deployments
    (some turrets, some barriers) still escalate correctly.
    """

    RELEVANT_TYPES = {"turret_placed", "barrier_placed"}

    # Tiers considered "high value" for severity boost (T3+)
    _HIGH_TIERS = {3, 4}

    def __init__(self):
        cfg = get_evaluator_config("turret_activity")
        self.lookback_time = cfg.get("lookback_time", 80.0)
        self.expiration_offset = cfg.get("expiration_offset", 120.0)
        t = cfg.get("thresholds", {})
        self.minor_max = t.get("minor_max", 3)
        self.moderate_max = t.get("moderate_max", 8)
        self.significant_max = t.get("significant_max", 20)
        templates = cfg.get("narrative_templates", {})
        self.tpl_turret_region = templates.get(
            "turret_with_region",
            "Player has placed {count} turrets in {region}.",
        )
        self.tpl_turret_global = templates.get(
            "turret_no_region",
            "Player has placed {count} turrets.",
        )
        self.tpl_barrier_region = templates.get(
            "barrier_with_region",
            "Player has placed {count} barriers in {region}.",
        )
        self.tpl_barrier_global = templates.get(
            "barrier_no_region",
            "Player has placed {count} barriers.",
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
        is_turret = trigger_event.event_type == "turret_placed"

        event_type_str = "turret_placed" if is_turret else "barrier_placed"

        # Count all deployments of this type in this locality within lookback
        count = event_store.count_filtered(
            event_type=event_type_str,
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

        # High-tier deployments boost severity by one step
        tier = trigger_event.tier or 1
        if tier in self._HIGH_TIERS:
            _order = ["minor", "moderate", "significant", "major", "critical"]
            idx = _order.index(severity)
            severity = _order[min(idx + 1, len(_order) - 1)]

        # Build narrative — turrets and barriers have distinct templates
        if locality_id:
            region = geo_registry.regions.get(locality_id)
            region_name = region.name if region else locality_id
            if is_turret:
                narrative = self.tpl_turret_region.format(count=count, region=region_name)
            else:
                narrative = self.tpl_barrier_region.format(count=count, region=region_name)
        else:
            if is_turret:
                narrative = self.tpl_turret_global.format(count=count)
            else:
                narrative = self.tpl_barrier_global.format(count=count)

        # Extract item/material name from subtype
        # subtypes: placed_net_launcher → net launcher, placed_stone_barrier → stone barrier
        raw_subtype = trigger_event.event_subtype or ""
        if raw_subtype.startswith("placed_"):
            item_name = raw_subtype[len("placed_"):].replace("_", " ")
        else:
            item_name = "turret" if is_turret else "barrier"

        affected_locality_ids = [locality_id] if locality_id else []
        parent_id = None
        if locality_id:
            region = geo_registry.regions.get(locality_id)
            parent_id = region.parent_id if region else None

        action_tag = "action:turret_placed" if is_turret else "action:barrier_placed"
        affects_tags = [
            "domain:engineering",
            action_tag,
            f"resource:{item_name.replace(' ', '_')}",
        ]
        if tier and tier >= 3:
            affects_tags.append(f"tier:{tier}")

        return InterpretedEvent.create(
            narrative=narrative,
            category="turret_activity",
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

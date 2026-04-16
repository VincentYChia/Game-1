"""Chest Loot Evaluator — narrates chest-opening activity within a locality.

Listens to CHEST_OPENED events (published by game_engine when the player
takes the first item from a chest) and reports regional looting activity.
Fires on every chest opened, escalating severity based on how many chests
have been opened in the locality within the lookback window.

Chest openings belong to the exploration domain — finding and looting
chests is a measure of how thoroughly the player is clearing an area.
Dungeon chests in particular indicate deep, deliberate exploration rather
than passing through.
"""

from __future__ import annotations

from typing import Optional

from world_system.world_memory.config_loader import get_evaluator_config
from world_system.world_memory.event_schema import InterpretedEvent, WorldMemoryEvent
from world_system.world_memory.event_store import EventStore
from world_system.world_memory.geographic_registry import GeographicRegistry
from world_system.world_memory.entity_registry import EntityRegistry
from world_system.world_memory.interpreter import PatternEvaluator


class ChestLootEvaluator(PatternEvaluator):
    """Reports regional chest-opening counts within a configurable lookback window.

    Fires on every CHEST_OPENED event. Severity escalates as the player
    opens more chests in one location (minor → major). Opening chests in
    a dungeon (`chest_type == "dungeon"`) always fires at least moderate
    severity, reflecting the structured nature of dungeon exploration.
    """

    RELEVANT_TYPES = {"chest_opened"}

    # Chest types that get a baseline severity boost
    _DUNGEON_TYPES = {"dungeon", "boss", "rare"}

    def __init__(self):
        cfg = get_evaluator_config("chest_loot")
        self.lookback_time = cfg.get("lookback_time", 100.0)
        self.expiration_offset = cfg.get("expiration_offset", 150.0)
        t = cfg.get("thresholds", {})
        self.minor_max = t.get("minor_max", 3)
        self.moderate_max = t.get("moderate_max", 8)
        self.significant_max = t.get("significant_max", 15)
        templates = cfg.get("narrative_templates", {})
        self.tpl_region = templates.get(
            "with_region",
            "Player has opened {count} chests in {region}.",
        )
        self.tpl_global = templates.get(
            "no_region",
            "Player has opened {count} chests.",
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

        # Count all chests opened in this locality within lookback window
        count = event_store.count_filtered(
            event_type="chest_opened",
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

        # Dungeon/boss chests guarantee at least moderate severity
        chest_type = ""
        subtype = trigger_event.event_subtype or ""
        if subtype.startswith("opened_"):
            chest_type = subtype[len("opened_"):]
        if chest_type in self._DUNGEON_TYPES:
            _order = ["minor", "moderate", "significant", "major", "critical"]
            if _order.index(severity) < _order.index("moderate"):
                severity = "moderate"

        # Build narrative
        if locality_id:
            region = geo_registry.regions.get(locality_id)
            region_name = region.name if region else locality_id
            narrative = self.tpl_region.format(count=count, region=region_name)
        else:
            narrative = self.tpl_global.format(count=count)

        affected_locality_ids = [locality_id] if locality_id else []
        parent_id = None
        if locality_id:
            region = geo_registry.regions.get(locality_id)
            parent_id = region.parent_id if region else None

        affects_tags = [
            "domain:exploration",
            "action:chest_opened",
        ]
        if chest_type:
            affects_tags.append(f"resource:{chest_type}_chest")

        return InterpretedEvent.create(
            narrative=narrative,
            category="chest_loot",
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

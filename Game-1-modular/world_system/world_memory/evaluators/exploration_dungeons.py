"""Exploration Dungeons Evaluator — narrates dungeon entry events."""

from __future__ import annotations

from typing import Optional

from world_system.world_memory.config_loader import get_evaluator_config
from world_system.world_memory.event_schema import InterpretedEvent, WorldMemoryEvent
from world_system.world_memory.event_store import EventStore
from world_system.world_memory.geographic_registry import GeographicRegistry
from world_system.world_memory.entity_registry import EntityRegistry
from world_system.world_memory.interpreter import PatternEvaluator


class ExplorationDungeonsEvaluator(PatternEvaluator):

    RELEVANT_TYPES = {"chunk_entered"}

    def __init__(self):
        cfg = get_evaluator_config("exploration_dungeons")
        self.expiration_offset = cfg.get("expiration_offset", 300.0)
        self.lookback_time = cfg.get("lookback_time", 50.0)
        t = cfg.get("thresholds", {})
        self.min_trigger = t.get("minimum_trigger", 1)
        self.moderate_min = t.get("moderate_min", 5)
        self.significant_min = t.get("significant_min", 15)
        self.major_min = t.get("major_min", 30)
        templates = cfg.get("narrative_templates", {})
        self.tpl_count = templates.get("dungeon_count",
            "Player has entered {count} dungeons.")
        self.tpl_specific = templates.get("dungeon_specific",
            "Player has entered a {rarity} dungeon.")

    def is_relevant(self, event: WorldMemoryEvent) -> bool:
        if event.event_type not in self.RELEVANT_TYPES:
            return False
        # Only relevant if event has dungeon-related data
        if event.context.get("is_dungeon"):
            return True
        if event.tags and "dungeon" in event.tags:
            return True
        return False

    def evaluate(self, trigger_event: WorldMemoryEvent,
                 event_store: EventStore,
                 geo_registry: GeographicRegistry,
                 entity_registry: EntityRegistry,
                 interpretation_store: EventStore) -> Optional[InterpretedEvent]:
        is_dungeon = trigger_event.context.get("is_dungeon", False)
        has_dungeon_tag = trigger_event.tags and "dungeon" in trigger_event.tags

        if not is_dungeon and not has_dungeon_tag:
            return None

        rarity = trigger_event.context.get("rarity") or trigger_event.quality

        # Count dungeon entries by querying chunk_entered events
        # and filtering for dungeon context (approximate via tags)
        all_chunk_events = event_store.query(
            event_type="chunk_entered",
            limit=500,
        )
        dungeon_count = sum(
            1 for e in all_chunk_events
            if e.context.get("is_dungeon") or (e.tags and "dungeon" in e.tags)
        )

        if dungeon_count < self.min_trigger:
            return None

        if rarity:
            narrative = self.tpl_specific.format(rarity=rarity)
        else:
            narrative = self.tpl_count.format(count=dungeon_count)

        if dungeon_count >= self.major_min:
            severity = "major"
        elif dungeon_count >= self.significant_min:
            severity = "significant"
        elif dungeon_count >= self.moderate_min:
            severity = "moderate"
        else:
            severity = "minor"

        return InterpretedEvent.create(
            narrative=narrative,
            category="exploration_dungeons",
            severity=severity,
            trigger_event_id=trigger_event.event_id,
            trigger_count=trigger_event.interpretation_count,
            game_time=trigger_event.game_time,
            cause_event_ids=[trigger_event.event_id],
            affected_locality_ids=[trigger_event.locality_id] if trigger_event.locality_id else [],
            affected_district_ids=[trigger_event.district_id] if trigger_event.district_id else [],
            affected_province_ids=[trigger_event.province_id] if trigger_event.province_id else [],
            epicenter_x=trigger_event.position_x,
            epicenter_y=trigger_event.position_y,
            affects_tags=["type:player", "event:dungeon_entered"],
            is_ongoing=False,
            expires_at=trigger_event.game_time + self.expiration_offset,
        )

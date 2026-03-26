"""Crafting Trend Evaluator — narrates crafting activity counts and quality breakdown."""

from __future__ import annotations

from typing import Optional

from world_system.world_memory.config_loader import get_evaluator_config
from world_system.world_memory.event_schema import InterpretedEvent, WorldMemoryEvent
from world_system.world_memory.event_store import EventStore
from world_system.world_memory.geographic_registry import GeographicRegistry
from world_system.world_memory.entity_registry import EntityRegistry
from world_system.world_memory.interpreter import PatternEvaluator


class CraftingTrendEvaluator(PatternEvaluator):

    RELEVANT_TYPES = {"craft_attempted", "item_invented"}

    def __init__(self):
        cfg = get_evaluator_config("crafting_trends")
        self.lookback_time = cfg.get("lookback_time", 100.0)
        self.min_event_count = cfg.get("minimum_event_count", 5)
        self.specialization_ratio = cfg.get("specialization_ratio", 0.6)
        self.quality_ratio_threshold = cfg.get("quality_ratio_threshold", 0.3)
        self.high_quality_types = set(cfg.get("high_quality_types",
            ["superior", "masterwork", "legendary"]))
        self.moderate_craft_count = cfg.get("moderate_craft_count", 20)

    def is_relevant(self, event: WorldMemoryEvent) -> bool:
        return event.event_type in self.RELEVANT_TYPES

    def evaluate(self, trigger_event: WorldMemoryEvent,
                 event_store: EventStore,
                 geo_registry: GeographicRegistry,
                 entity_registry: EntityRegistry,
                 interpretation_store: EventStore) -> Optional[InterpretedEvent]:
        count = trigger_event.interpretation_count
        if count < self.min_event_count:
            return None

        recent_crafts = event_store.query(
            event_type="craft_attempted",
            actor_id="player",
            since_game_time=trigger_event.game_time - self.lookback_time,
            limit=100,
        )

        if len(recent_crafts) < self.min_event_count:
            return None

        disciplines = {}
        qualities = {}
        for craft in recent_crafts:
            disc = craft.context.get("discipline", "unknown")
            disciplines[disc] = disciplines.get(disc, 0) + 1
            qual = craft.quality or "normal"
            qualities[qual] = qualities.get(qual, 0) + 1

        if not disciplines:
            return None
        dominant = max(disciplines, key=disciplines.get)
        dominant_count = disciplines[dominant]
        total = len(recent_crafts)

        if dominant_count / total < self.specialization_ratio:
            return None

        high_quality = sum(qualities.get(qt, 0) for qt in self.high_quality_types)
        quality_ratio = high_quality / total if total > 0 else 0

        if quality_ratio > self.quality_ratio_threshold:
            severity = "significant"
            narrative = (
                f"Player has crafted {total} items, {dominant_count} in {dominant}. "
                f"{high_quality} achieved high quality."
            )
        elif dominant_count >= self.moderate_craft_count:
            severity = "moderate"
            narrative = (
                f"Player has crafted {total} items, {dominant_count} in {dominant}."
            )
        else:
            severity = "minor"
            narrative = (
                f"Player has crafted {total} items, {dominant_count} in {dominant}."
            )

        return InterpretedEvent.create(
            narrative=narrative,
            category="crafting_trend",
            severity=severity,
            trigger_event_id=trigger_event.event_id,
            trigger_count=count,
            game_time=trigger_event.game_time,
            affects_tags=[f"domain:{dominant}", "event:crafting", "type:player"],
        )

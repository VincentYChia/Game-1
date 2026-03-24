"""Crafting Trend Evaluator — detects crafting specialization and quality trends."""

from __future__ import annotations

from typing import Optional

from ai.memory.event_schema import InterpretedEvent, WorldMemoryEvent
from ai.memory.event_store import EventStore
from ai.memory.geographic_registry import GeographicRegistry
from ai.memory.entity_registry import EntityRegistry
from ai.memory.interpreter import PatternEvaluator


class CraftingTrendEvaluator(PatternEvaluator):

    RELEVANT_TYPES = {"craft_attempted", "item_invented"}
    LOOKBACK_TIME = 100.0

    def is_relevant(self, event: WorldMemoryEvent) -> bool:
        return event.event_type in self.RELEVANT_TYPES

    def evaluate(self, trigger_event: WorldMemoryEvent,
                 event_store: EventStore,
                 geo_registry: GeographicRegistry,
                 entity_registry: EntityRegistry,
                 interpretation_store: EventStore) -> Optional[InterpretedEvent]:
        # Only trigger at meaningful counts
        count = trigger_event.interpretation_count
        if count < 5:
            return None

        # Get all recent crafting events
        recent_crafts = event_store.query(
            event_type="craft_attempted",
            actor_id="player",
            since_game_time=trigger_event.game_time - self.LOOKBACK_TIME,
            limit=100,
        )

        if len(recent_crafts) < 5:
            return None

        # Count by discipline
        disciplines = {}
        qualities = {}
        for craft in recent_crafts:
            disc = craft.context.get("discipline", "unknown")
            disciplines[disc] = disciplines.get(disc, 0) + 1
            qual = craft.quality or "normal"
            qualities[qual] = qualities.get(qual, 0) + 1

        # Find dominant discipline
        if not disciplines:
            return None
        dominant = max(disciplines, key=disciplines.get)
        dominant_count = disciplines[dominant]
        total = len(recent_crafts)

        # Check for specialization (>60% in one discipline)
        if dominant_count / total < 0.6:
            return None

        # Check quality trend
        high_quality = qualities.get("superior", 0) + qualities.get("masterwork", 0) + qualities.get("legendary", 0)
        quality_ratio = high_quality / total if total > 0 else 0

        if quality_ratio > 0.3:
            severity = "significant"
            narrative = (
                f"The adventurer is becoming a master {dominant} crafter. "
                f"{dominant_count} of their last {total} crafts were {dominant}, "
                f"and {high_quality} achieved exceptional quality."
            )
        elif dominant_count >= 20:
            severity = "moderate"
            narrative = (
                f"The adventurer specializes in {dominant}. "
                f"{dominant_count} of their last {total} crafts focused on this discipline."
            )
        else:
            severity = "minor"
            narrative = (
                f"The adventurer shows a preference for {dominant} crafting."
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

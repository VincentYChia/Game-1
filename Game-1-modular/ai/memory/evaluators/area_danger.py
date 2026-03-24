"""Area Danger Evaluator — detects when an area becomes more or less dangerous."""

from __future__ import annotations

from typing import Optional

from ai.memory.event_schema import InterpretedEvent, WorldMemoryEvent
from ai.memory.event_store import EventStore
from ai.memory.geographic_registry import GeographicRegistry
from ai.memory.entity_registry import EntityRegistry
from ai.memory.interpreter import PatternEvaluator


class AreaDangerEvaluator(PatternEvaluator):

    RELEVANT_TYPES = {"damage_taken", "player_death"}
    LOOKBACK_TIME = 30.0

    def is_relevant(self, event: WorldMemoryEvent) -> bool:
        return event.event_type in self.RELEVANT_TYPES

    def evaluate(self, trigger_event: WorldMemoryEvent,
                 event_store: EventStore,
                 geo_registry: GeographicRegistry,
                 entity_registry: EntityRegistry,
                 interpretation_store: EventStore) -> Optional[InterpretedEvent]:
        locality_id = trigger_event.locality_id
        if not locality_id:
            return None

        # Count damage events in this area recently
        damage_events = event_store.count_filtered(
            event_type="damage_taken",
            locality_id=locality_id,
            since_game_time=trigger_event.game_time - self.LOOKBACK_TIME,
        )
        death_events = event_store.count_filtered(
            event_type="player_death",
            locality_id=locality_id,
            since_game_time=trigger_event.game_time - self.LOOKBACK_TIME,
        )

        # Combined threat score
        threat_score = damage_events + death_events * 10

        if threat_score < 5:
            return None

        region = geo_registry.regions.get(locality_id)
        region_name = region.name if region else locality_id

        if death_events >= 3:
            severity = "major"
            narrative = (
                f"{region_name} is extremely dangerous. The adventurer has died "
                f"{death_events} times here recently. This area poses a serious threat."
            )
        elif death_events >= 1 or threat_score >= 20:
            severity = "significant"
            narrative = (
                f"{region_name} has proven hazardous. Frequent combat injuries and "
                f"{'a death' if death_events == 1 else 'deaths'} mark this area as dangerous."
            )
        elif threat_score >= 10:
            severity = "moderate"
            narrative = (
                f"Combat activity is elevated in {region_name}. "
                f"The adventurer has taken repeated damage here."
            )
        else:
            severity = "minor"
            narrative = f"Some combat encounters in {region_name}."

        parent_id = region.parent_id if region else None
        return InterpretedEvent.create(
            narrative=narrative,
            category="area_danger",
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
                "event:combat",
                "concern:safety",
            ],
            is_ongoing=True,
            expires_at=trigger_event.game_time + 50.0,
        )

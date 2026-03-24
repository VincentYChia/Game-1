"""Population Change Evaluator — detects when enemy kills in a region
exceed natural recovery thresholds."""

from __future__ import annotations

from typing import Optional

from ai.memory.event_schema import InterpretedEvent, WorldMemoryEvent
from ai.memory.event_store import EventStore
from ai.memory.geographic_registry import GeographicRegistry
from ai.memory.entity_registry import EntityRegistry
from ai.memory.interpreter import PatternEvaluator


class PopulationChangeEvaluator(PatternEvaluator):

    RELEVANT_TYPES = {"enemy_killed"}
    LOOKBACK_TIME = 50.0  # Game-time units to look back

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

        enemy_subtype = trigger_event.event_subtype
        recent_kills = event_store.count_filtered(
            event_type="enemy_killed",
            event_subtype=enemy_subtype,
            locality_id=locality_id,
            since_game_time=trigger_event.game_time - self.LOOKBACK_TIME,
        )

        if recent_kills < 5:
            return None

        region = geo_registry.regions.get(locality_id)
        region_name = region.name if region else locality_id
        enemy_name = enemy_subtype.replace("killed_", "").replace("_", " ")

        if recent_kills >= 50:
            severity = "major"
            narrative = (
                f"The {enemy_name} population has been devastated in {region_name}. "
                f"{recent_kills} have been killed in a short period. "
                f"The species may take significant time to recover in this area."
            )
        elif recent_kills >= 20:
            severity = "significant"
            narrative = (
                f"{enemy_name.title()} numbers are noticeably declining in {region_name}. "
                f"{recent_kills} have been killed recently."
            )
        elif recent_kills >= 10:
            severity = "moderate"
            narrative = (
                f"Increased hunting activity has thinned the {enemy_name} population "
                f"in {region_name}."
            )
        else:
            severity = "minor"
            narrative = (
                f"Several {enemy_name}s have been killed in {region_name}."
            )

        cause_events = event_store.query(
            event_type="enemy_killed",
            event_subtype=enemy_subtype,
            locality_id=locality_id,
            since_game_time=trigger_event.game_time - self.LOOKBACK_TIME,
            limit=10,
        )

        parent_id = region.parent_id if region else None
        return InterpretedEvent.create(
            narrative=narrative,
            category="population_change",
            severity=severity,
            trigger_event_id=trigger_event.event_id,
            trigger_count=trigger_event.interpretation_count,
            game_time=trigger_event.game_time,
            cause_event_ids=[e.event_id for e in cause_events],
            affected_locality_ids=[locality_id],
            affected_district_ids=[parent_id] if parent_id else [],
            epicenter_x=trigger_event.position_x,
            epicenter_y=trigger_event.position_y,
            affects_tags=[
                f"species:{enemy_name.replace(' ', '_')}",
                f"biome:{trigger_event.biome}",
            ],
            is_ongoing=True,
            expires_at=trigger_event.game_time + 100.0,
        )

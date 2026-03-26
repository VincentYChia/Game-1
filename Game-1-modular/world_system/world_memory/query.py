"""World Query — entity-first query interface for the World Memory System.

Downstream systems (NPC agents, quest generators) use this to ask questions.
You never search events directly. You find the entity first, then radiate
outward through its location, interests, and awareness radius.

Implements the dual-window system: static (minimum count) + recency (time-based).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, ClassVar, Dict, List, Optional

from world_system.world_memory.config_loader import get_section, get_query_window_config
from world_system.world_memory.event_schema import InterpretedEvent, WorldMemoryEvent
from world_system.world_memory.event_store import EventStore
from world_system.world_memory.geographic_registry import GeographicRegistry
from world_system.world_memory.entity_registry import EntityRegistry, WorldEntity
from world_system.world_memory.tag_relevance import calculate_relevance


@dataclass
class EventWindow:
    """Configurable dual-window for event retrieval."""
    static_size: int = 10
    recency_period: float = 5.0


def _load_window(name: str, default_size: int, default_period: float) -> EventWindow:
    cfg = get_query_window_config(name)
    return EventWindow(
        static_size=cfg.get("static_size", default_size),
        recency_period=cfg.get("recency_period", default_period),
    )


# Preset windows — loaded from config with hardcoded fallbacks
WINDOW_NPC_LOCAL = _load_window("npc_local", 10, 5.0)
WINDOW_REGION_SUMMARY = _load_window("region_summary", 15, 10.0)
WINDOW_PLAYER_ACTIVITY = _load_window("player_activity", 8, 3.0)
WINDOW_FULL_HISTORY = _load_window("full_history", 20, 20.0)
WINDOW_QUICK_CHECK = _load_window("quick_check", 5, 2.0)


@dataclass
class EntityQueryResult:
    """Result of an entity-first query."""
    entity_id: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    direct_events: List[Dict] = field(default_factory=list)
    nearby_relevant_events: List[Dict] = field(default_factory=list)
    local_context: Optional[Dict] = None
    regional_context: Optional[Dict] = None
    ongoing_conditions: List[str] = field(default_factory=list)

    @staticmethod
    def empty(entity_id: str) -> EntityQueryResult:
        return EntityQueryResult(entity_id=entity_id)


class WorldQuery:
    """Entity-first query interface for the World Memory System. Singleton."""

    _instance: ClassVar[Optional[WorldQuery]] = None

    def __init__(self):
        self.entity_registry: Optional[EntityRegistry] = None
        self.geo_registry: Optional[GeographicRegistry] = None
        self.event_store: Optional[EventStore] = None
        qt = get_section("query_thresholds")
        self._nearby_relevance_min = qt.get("nearby_relevance_minimum", 0.2)
        self._ongoing_relevance_min = qt.get("ongoing_condition_relevance_minimum", 0.3)
        self._local_recent_limit = qt.get("local_context_recent_limit", 5)
        self._regional_notable_limit = qt.get("regional_context_notable_limit", 3)

    @classmethod
    def get_instance(cls) -> WorldQuery:
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        cls._instance = None

    def initialize(self, entity_registry: EntityRegistry,
                   geo_registry: GeographicRegistry,
                   event_store: EventStore) -> None:
        self.entity_registry = entity_registry
        self.geo_registry = geo_registry
        self.event_store = event_store

    # ── Primary query method ─────────────────────────────────────────

    def query_entity(self, entity_id: str,
                     window: Optional[EventWindow] = None,
                     current_game_time: float = 0.0) -> EntityQueryResult:
        """THE PRIMARY QUERY METHOD.

        Start from an entity, radiate outward through location and interests.
        Returns everything a system needs to know about this entity's context.
        """
        if not self.entity_registry or not self.event_store:
            return EntityQueryResult.empty(entity_id)

        if window is None:
            window = WINDOW_NPC_LOCAL

        entity = self.entity_registry.get(entity_id)
        if not entity:
            return EntityQueryResult.empty(entity_id)

        metadata = {
            "name": entity.name,
            "type": entity.entity_type.value,
            "tags": entity.tags,
            "position": (entity.position_x, entity.position_y),
            "home_region": entity.home_region_id,
            "metadata": entity.metadata,
        }

        direct_events = self._get_entity_activity(entity, window, current_game_time)
        nearby_events = self._get_nearby_relevant_events(entity, window, current_game_time)
        local_context = self._get_local_context(entity)
        regional_context = self._get_regional_context(entity)
        ongoing = self._get_ongoing_conditions(entity)

        return EntityQueryResult(
            entity_id=entity_id,
            metadata=metadata,
            direct_events=direct_events,
            nearby_relevant_events=nearby_events,
            local_context=local_context,
            regional_context=regional_context,
            ongoing_conditions=ongoing,
        )

    # ── Internal query methods ───────────────────────────────────────

    def _get_entity_activity(self, entity: WorldEntity,
                             window: EventWindow,
                             current_game_time: float) -> List[Dict]:
        """Get events from entity's activity log using dual window."""
        if not entity.activity_log:
            return []

        events = self.event_store.get_by_ids(entity.activity_log[-window.static_size * 2:])
        recency_cutoff = current_game_time - window.recency_period
        recent = [e for e in events if e.game_time >= recency_cutoff]
        recent.sort(key=lambda e: e.game_time, reverse=True)

        if len(recent) >= window.static_size:
            return [self._event_to_summary(e) for e in recent]

        older = [e for e in events if e.game_time < recency_cutoff]
        older.sort(key=lambda e: e.game_time, reverse=True)
        need = window.static_size - len(recent)
        return [self._event_to_summary(e) for e in (recent + older[:need])]

    def _get_nearby_relevant_events(self, entity: WorldEntity,
                                     window: EventWindow,
                                     current_game_time: float) -> List[Dict]:
        """Get events near entity, filtered by interest tags."""
        if entity.position_x is None or not self.event_store:
            return []

        # Query events in entity's locality/district
        filters = {}
        if entity.home_region_id:
            filters["locality_id"] = entity.home_region_id
        elif entity.home_district_id:
            filters["district_id"] = entity.home_district_id

        if not filters:
            return []

        recency_cutoff = current_game_time - window.recency_period
        events = self.event_store.query(
            since_game_time=recency_cutoff,
            limit=window.static_size * 3,
            **filters,
        )

        # Backfill if needed
        if len(events) < window.static_size:
            need = window.static_size - len(events)
            older = self.event_store.query(
                before_game_time=recency_cutoff,
                limit=need,
                **filters,
            )
            events.extend(older)

        # Filter by interest relevance
        scored = []
        for event in events:
            relevance = calculate_relevance(entity.tags, event.tags)
            if relevance > self._nearby_relevance_min:
                scored.append((relevance, event))

        # Sort by relevance * recency
        scored.sort(
            key=lambda pair: pair[0] * (
                1.0 / max(1.0, current_game_time - pair[1].game_time)
            ),
            reverse=True,
        )

        return [self._event_to_summary(e, relevance=r)
                for r, e in scored[:window.static_size]]

    def _get_local_context(self, entity: WorldEntity) -> Optional[Dict]:
        """Get Layer 3 local knowledge for entity's home region."""
        if not entity.home_region_id or not self.geo_registry:
            return None

        region = self.geo_registry.regions.get(entity.home_region_id)
        if not region:
            return None

        # Resolve recent interpretation narratives
        recent_narratives = []
        for interp_id in region.state.recent_events[-self._local_recent_limit:]:
            interp = self.event_store.get_interpretation(interp_id)
            if interp:
                recent_narratives.append(interp.narrative)

        ongoing_narratives = []
        for interp_id in region.state.active_conditions:
            interp = self.event_store.get_interpretation(interp_id)
            if interp and not interp.archived:
                ongoing_narratives.append(interp.narrative)

        return {
            "region_name": region.name,
            "summary": region.state.summary_text or "Nothing notable.",
            "ongoing_conditions": ongoing_narratives,
            "recent_events": recent_narratives,
        }

    def _get_regional_context(self, entity: WorldEntity) -> Optional[Dict]:
        """Get Layer 4 regional knowledge for entity's province."""
        province_id = entity.home_province_id
        if not province_id or not self.geo_registry:
            return None

        region = self.geo_registry.regions.get(province_id)
        if not region:
            return None

        notable_narratives = []
        for interp_id in region.state.recent_events[-self._regional_notable_limit:]:
            interp = self.event_store.get_interpretation(interp_id)
            if interp:
                notable_narratives.append(interp.narrative)

        return {
            "region_name": region.name,
            "summary": region.state.summary_text or "Nothing notable.",
            "notable_events": notable_narratives,
        }

    def _get_ongoing_conditions(self, entity: WorldEntity) -> List[str]:
        """Get ongoing interpretations affecting this entity via tag matching."""
        if not entity.home_region_id or not self.event_store:
            return []

        ongoing = self.event_store.get_ongoing_interpretations(
            locality_id=entity.home_region_id
        )
        relevant = []
        for interp in ongoing:
            relevance = calculate_relevance(entity.tags, interp.affects_tags)
            if relevance > self._ongoing_relevance_min:
                relevant.append(interp.narrative)
        return relevant

    # ── Convenience methods ──────────────────────────────────────────

    def query_location(self, region_id: str,
                       window: Optional[EventWindow] = None,
                       current_game_time: float = 0.0) -> EntityQueryResult:
        """Query a geographic region as an entity."""
        return self.query_entity(f"region_{region_id}", window, current_game_time)

    def query_events_in_area(self, x: float, y: float, radius: float,
                              window: Optional[EventWindow] = None,
                              current_game_time: float = 0.0,
                              tag_filter: Optional[List[str]] = None) -> List[Dict]:
        """Raw event pipeline query — events in a circular area."""
        if not self.event_store or not self.geo_registry:
            return []

        if window is None:
            window = WINDOW_NPC_LOCAL

        # Find locality at center point
        locality = self.geo_registry.get_region_at(x, y)
        filters = {}
        if locality:
            filters["locality_id"] = locality.region_id

        recency_cutoff = current_game_time - window.recency_period
        events = self.event_store.query(
            since_game_time=recency_cutoff,
            tags=tag_filter,
            limit=window.static_size * 2,
            **filters,
        )

        if len(events) < window.static_size:
            need = window.static_size - len(events)
            older = self.event_store.query(
                before_game_time=recency_cutoff,
                tags=tag_filter,
                limit=need,
                **filters,
            )
            events.extend(older)

        return [self._event_to_summary(e) for e in events[:window.static_size * 2]]

    def query_interpretations(self, **kwargs) -> List[InterpretedEvent]:
        """Direct Layer 2 query."""
        if not self.event_store:
            return []
        return self.event_store.query_interpretations(**kwargs)

    def get_world_summary(self, current_game_time: float = 0.0) -> Dict[str, Any]:
        """Get a high-level summary of the world's current state."""
        if not self.event_store or not self.geo_registry:
            return {"status": "not initialized"}

        total_events = self.event_store.get_event_count()
        ongoing = self.event_store.query_interpretations(ongoing_only=True)

        return {
            "total_events_recorded": total_events,
            "ongoing_conditions": [
                {"narrative": i.narrative, "category": i.category, "severity": i.severity}
                for i in ongoing
            ],
            "regions_with_activity": sum(
                1 for r in self.geo_registry.regions.values()
                if r.state.recent_events
            ),
        }

    # ── Helpers ──────────────────────────────────────────────────────

    def _event_to_summary(self, event: WorldMemoryEvent,
                          relevance: float = 1.0) -> Dict:
        return {
            "event_id": event.event_id,
            "type": event.event_type,
            "subtype": event.event_subtype,
            "narrative_hint": f"{event.actor_id} {event.event_subtype}",
            "game_time": event.game_time,
            "position": (event.position_x, event.position_y),
            "magnitude": event.magnitude,
            "result": event.result,
            "tags": event.tags,
            "relevance": relevance,
        }

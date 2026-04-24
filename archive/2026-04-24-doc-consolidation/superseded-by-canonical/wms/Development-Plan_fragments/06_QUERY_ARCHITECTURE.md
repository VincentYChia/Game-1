# Part 6: Query Architecture, Aggregation (Layers 4-5), Window System

## The Static + Recency Window System

### The Problem

When querying "what's happening near the blacksmith?", we need to return enough context — but not too much. Sometimes recent events are abundant (during active combat). Sometimes they're sparse (quiet area). A fixed window of "last 10 events" either over-represents a 5-second combat burst or under-represents a week of quiet activity.

### The Solution: Dual Window

Two windows that work together:

**Static Window**: A fixed number of event slots (e.g., 10). This guarantees a minimum amount of context in every query response.

**Recency Window**: A time-based window (e.g., last 5 game-time units). Everything within this time period is included, regardless of count.

**The Rule**:
- If the recency window has **fewer** events than the static window → backfill from history until the static window is full
- If the recency window has **more** events than the static window → include ALL recent events (don't truncate)

```python
@dataclass
class EventWindow:
    """Configurable dual-window for event retrieval"""
    static_size: int = 10             # Minimum number of events to return
    recency_period: float = 5.0       # Game-time units for "recent"

def get_windowed_events(event_store: EventStore,
                        window: EventWindow,
                        current_game_time: float,
                        **query_filters) -> List[WorldMemoryEvent]:
    """
    Retrieve events using the static + recency dual window.

    1. Get all events in the recency window
    2. If fewer than static_size, backfill from older events
    3. If more than static_size, return all recent events
    """
    recency_cutoff = current_game_time - window.recency_period

    # Step 1: Get recent events
    recent = event_store.query(
        since_game_time=recency_cutoff,
        order_by="game_time DESC",
        **query_filters
    )

    if len(recent) >= window.static_size:
        # Plenty of recent events — return all of them
        return recent

    # Step 2: Not enough recent — backfill from history
    need = window.static_size - len(recent)
    older = event_store.query(
        before_game_time=recency_cutoff,
        order_by="game_time DESC",
        limit=need,
        **query_filters
    )

    # Return: all recent + enough older to fill the static window
    return recent + older
```

### Window Configuration by Context

Different query contexts use different window sizes:

| Context | Static Size | Recency Period | Rationale |
|---------|-------------|---------------|-----------|
| NPC local awareness | 10 | 5.0 game-time | An NPC knows recent local events + some history |
| Region summary | 15 | 10.0 game-time | Region summaries need more breadth |
| Player activity query | 8 | 3.0 game-time | Focused on what just happened |
| Full entity history | 20 | 20.0 game-time | Deep query for detailed context |
| Quick relevance check | 5 | 2.0 game-time | Fast check — is anything relevant happening? |

## Layers 4 and 5: Aggregation

### Layer 4: Local Event Aggregation

Each locality and district maintains a **local knowledge state** — a pre-compiled summary of Layer 3 interpreted events that affect it. This is what an NPC standing in that area "knows."

```python
@dataclass
class LocalKnowledge:
    """Layer 4: What's known in a specific locality or district"""

    region_id: str                    # Which region this belongs to
    region_level: str                 # "locality" or "district"

    # Active conditions (ongoing Layer 3 events affecting this area)
    ongoing_conditions: List[str]     # Interpretation IDs still active
    ongoing_narratives: List[str]     # The narrative text of each (cached for fast access)

    # Recent events (using static + recency window)
    recent_interpretations: List[str]  # Interpretation IDs, most recent first
    recent_narratives: List[str]       # Cached narrative texts

    # Summary (regenerated when conditions change)
    summary: str                      # "The Iron Hills are quiet. Recent mining activity
                                      #  has strained iron deposits. No notable threats."

    last_updated: float               # Game time of last change

    def compile_summary(self, interpretation_store: 'InterpretationStore'):
        """Regenerate the summary from current conditions and recent events"""
        parts = []

        if self.ongoing_conditions:
            parts.append("Ongoing: " + "; ".join(self.ongoing_narratives))

        if self.recent_narratives:
            parts.append("Recent: " + "; ".join(self.recent_narratives[:5]))

        if not parts:
            parts.append("Nothing notable.")

        self.summary = " ".join(parts)
        self.last_updated = time.time()
```

### Layer 5: Regional Event Aggregation

Provinces and the realm maintain broader summaries, filtered by significance:

```python
@dataclass
class RegionalKnowledge:
    """Layer 5: What's known at province or realm level"""

    region_id: str
    region_level: str                 # "province" or "realm"

    # Only significant events propagate up to this level
    notable_interpretations: List[str]  # Interpretation IDs (severity >= "significant")
    notable_narratives: List[str]

    # Cross-locality trends (detected from child summaries)
    trends: List[str]                 # "Iron scarce across all eastern districts"
                                      # "Wolf population recovering in southern forests"

    summary: str
    last_updated: float

    def update_from_children(self, child_knowledge: List[LocalKnowledge],
                            interpretation_store: 'InterpretationStore'):
        """Aggregate child region summaries into regional knowledge"""
        # Collect all notable interpretations from children
        all_notable = []
        for child in child_knowledge:
            for interp_id in child.recent_interpretations:
                interp = interpretation_store.get(interp_id)
                if interp and interp.severity in ("significant", "major", "critical"):
                    all_notable.append(interp)

        # Deduplicate (same interpretation can affect multiple localities)
        seen_ids = set()
        unique_notable = []
        for interp in all_notable:
            if interp.interpretation_id not in seen_ids:
                seen_ids.add(interp.interpretation_id)
                unique_notable.append(interp)

        # Sort by severity then recency
        severity_order = {"critical": 0, "major": 1, "significant": 2}
        unique_notable.sort(key=lambda i: (severity_order.get(i.severity, 3), -i.created_at))

        self.notable_interpretations = [i.interpretation_id for i in unique_notable[:15]]
        self.notable_narratives = [i.narrative for i in unique_notable[:15]]

        # Detect cross-locality trends
        self.trends = self._detect_trends(child_knowledge, interpretation_store)
        self.last_updated = time.time()
```

### Aggregation Manager

```python
class AggregationManager:
    """Maintains Layers 4 and 5. Updated when Layer 3 events change."""
    _instance = None

    def __init__(self):
        self.local_knowledge: Dict[str, LocalKnowledge] = {}    # region_id → Layer 4
        self.regional_knowledge: Dict[str, RegionalKnowledge] = {}  # region_id → Layer 5

    def on_interpretation_created(self, interpretation: InterpretedEvent):
        """Called by WorldInterpreter when a new Layer 3 event is created"""
        # Update Layer 4 for affected localities
        for locality_id in interpretation.affected_locality_ids:
            knowledge = self._get_or_create_local(locality_id, "locality")
            knowledge.recent_interpretations.insert(0, interpretation.interpretation_id)
            knowledge.recent_narratives.insert(0, interpretation.narrative)
            if interpretation.is_ongoing:
                knowledge.ongoing_conditions.append(interpretation.interpretation_id)
                knowledge.ongoing_narratives.append(interpretation.narrative)
            # Trim
            max_size = 20
            knowledge.recent_interpretations = knowledge.recent_interpretations[:max_size]
            knowledge.recent_narratives = knowledge.recent_narratives[:max_size]
            knowledge.compile_summary(self.interpretation_store)

        # Update Layer 4 for affected districts
        for district_id in interpretation.affected_district_ids:
            knowledge = self._get_or_create_local(district_id, "district")
            knowledge.recent_interpretations.insert(0, interpretation.interpretation_id)
            knowledge.recent_narratives.insert(0, interpretation.narrative)
            if interpretation.is_ongoing:
                knowledge.ongoing_conditions.append(interpretation.interpretation_id)
                knowledge.ongoing_narratives.append(interpretation.narrative)
            knowledge.compile_summary(self.interpretation_store)

        # Update Layer 5 for affected provinces (only if significant)
        if interpretation.severity in ("significant", "major", "critical"):
            for province_id in interpretation.affected_province_ids:
                regional = self._get_or_create_regional(province_id, "province")
                child_ids = self.geo_registry.regions[province_id].child_ids
                children = [self.local_knowledge.get(cid) for cid in child_ids
                           if cid in self.local_knowledge]
                regional.update_from_children(
                    [c for c in children if c],
                    self.interpretation_store
                )
```

## The Query Interface — Entity-First

### WorldQuery: The Main Query API

```python
class WorldQuery:
    """
    Entity-first query interface for the World Memory System.
    Downstream systems (NPC agents, quest generators) use this to ask questions.
    Singleton.
    """
    _instance = None

    def __init__(self):
        self.entity_registry: Optional[EntityRegistry] = None
        self.geo_registry: Optional[GeographicRegistry] = None
        self.event_store: Optional[EventStore] = None
        self.interpretation_store: Optional[InterpretationStore] = None
        self.aggregation_manager: Optional[AggregationManager] = None

    def query_entity(self, entity_id: str,
                     window: EventWindow = None,
                     current_game_time: float = 0.0) -> EntityQueryResult:
        """
        THE PRIMARY QUERY METHOD.
        Start from an entity, radiate outward through location and interests.

        Returns everything a system needs to know about this entity's context.
        """
        if window is None:
            window = EventWindow(static_size=10, recency_period=5.0)

        entity = self.entity_registry.get(entity_id)
        if not entity:
            return EntityQueryResult.empty(entity_id)

        # Step 1: Entity metadata
        metadata = {
            "name": entity.name,
            "type": entity.entity_type.value,
            "tags": entity.tags,
            "position": (entity.position_x, entity.position_y),
            "home_region": entity.home_region_id,
            "metadata": entity.metadata
        }

        # Step 2: Direct activity (events involving this entity)
        direct_events = self._get_entity_activity(entity, window, current_game_time)

        # Step 3: Nearby events filtered by interest
        nearby_events = self._get_nearby_relevant_events(entity, window, current_game_time)

        # Step 4: Local knowledge (Layer 4) for entity's home region
        local_context = self._get_local_context(entity)

        # Step 5: Regional knowledge (Layer 5) for broader context
        regional_context = self._get_regional_context(entity)

        # Step 6: Ongoing conditions affecting this entity
        ongoing = self._get_ongoing_conditions(entity)

        return EntityQueryResult(
            entity_id=entity_id,
            metadata=metadata,
            direct_events=direct_events,
            nearby_relevant_events=nearby_events,
            local_context=local_context,
            regional_context=regional_context,
            ongoing_conditions=ongoing
        )

    def _get_entity_activity(self, entity: WorldEntity,
                             window: EventWindow,
                             current_game_time: float) -> List[Dict]:
        """Get events from the entity's activity log using the dual window"""
        if not entity.activity_log:
            return []

        # Get events by ID from the activity log
        events = self.event_store.get_by_ids(entity.activity_log)

        # Apply dual window
        recency_cutoff = current_game_time - window.recency_period
        recent = [e for e in events if e.game_time >= recency_cutoff]
        recent.sort(key=lambda e: e.game_time, reverse=True)

        if len(recent) >= window.static_size:
            return [self._event_to_summary(e) for e in recent]

        # Backfill
        older = [e for e in events if e.game_time < recency_cutoff]
        older.sort(key=lambda e: e.game_time, reverse=True)
        need = window.static_size - len(recent)
        return [self._event_to_summary(e) for e in (recent + older[:need])]

    def _get_nearby_relevant_events(self, entity: WorldEntity,
                                     window: EventWindow,
                                     current_game_time: float) -> List[Dict]:
        """Get events near entity's position, filtered by entity's interests"""
        if entity.position_x is None:
            return []

        # Get events within awareness radius
        nearby_events = get_windowed_events(
            self.event_store,
            window,
            current_game_time,
            near_position=(entity.position_x, entity.position_y),
            radius=entity.awareness_radius
        )

        # Filter by interest relevance
        scored = []
        for event in nearby_events:
            relevance = calculate_relevance(entity.tags, event.tags)
            if relevance > 0.2:  # Minimum relevance threshold
                scored.append((relevance, event))

        # Sort by relevance × recency
        scored.sort(key=lambda pair: pair[0] * (1.0 / max(1.0,
            current_game_time - pair[1].game_time)), reverse=True)

        return [self._event_to_summary(e, relevance=r) for r, e in scored[:window.static_size]]

    def _get_local_context(self, entity: WorldEntity) -> Optional[Dict]:
        """Get Layer 4 local knowledge for entity's home region"""
        if not entity.home_region_id:
            return None

        local = self.aggregation_manager.local_knowledge.get(entity.home_region_id)
        if not local:
            return None

        return {
            "region_name": self.geo_registry.regions[entity.home_region_id].name,
            "summary": local.summary,
            "ongoing_conditions": local.ongoing_narratives,
            "recent_events": local.recent_narratives[:5]
        }

    def _get_regional_context(self, entity: WorldEntity) -> Optional[Dict]:
        """Get Layer 5 regional knowledge for entity's province"""
        province_id = entity.home_province_id
        if not province_id:
            return None

        regional = self.aggregation_manager.regional_knowledge.get(province_id)
        if not regional:
            return None

        return {
            "region_name": self.geo_registry.regions[province_id].name,
            "summary": regional.summary,
            "notable_events": regional.notable_narratives[:3],
            "trends": regional.trends
        }

    def _get_ongoing_conditions(self, entity: WorldEntity) -> List[str]:
        """Get ongoing interpreted events that affect this entity (via tag matching)"""
        ongoing = self.interpretation_store.get_ongoing(entity.home_region_id)
        relevant = []
        for interp in ongoing:
            relevance = calculate_relevance(entity.tags, interp.affects_tags)
            if relevance > 0.3:
                relevant.append(interp.narrative)
        return relevant

    def _event_to_summary(self, event: WorldMemoryEvent,
                          relevance: float = 1.0) -> Dict:
        """Convert a raw event to a query-friendly summary dict"""
        return {
            "event_id": event.event_id,
            "type": event.event_type,
            "subtype": event.event_subtype,
            "narrative_hint": f"{event.actor_id} {event.event_subtype} at {event.locality_id}",
            "game_time": event.game_time,
            "position": (event.position_x, event.position_y),
            "magnitude": event.magnitude,
            "result": event.result,
            "tags": event.tags,
            "relevance": relevance
        }


@dataclass
class EntityQueryResult:
    """Result of an entity-first query"""
    entity_id: str
    metadata: Dict[str, Any]
    direct_events: List[Dict]         # Events directly involving this entity
    nearby_relevant_events: List[Dict] # Events near entity, filtered by interests
    local_context: Optional[Dict]      # Layer 4 summary for home locality
    regional_context: Optional[Dict]   # Layer 5 summary for home province
    ongoing_conditions: List[str]      # Active narratives affecting this entity

    @staticmethod
    def empty(entity_id: str) -> 'EntityQueryResult':
        return EntityQueryResult(
            entity_id=entity_id,
            metadata={},
            direct_events=[],
            nearby_relevant_events=[],
            local_context=None,
            regional_context=None,
            ongoing_conditions=[]
        )
```

### Convenience Query Methods

```python
class WorldQuery:
    # ... (continued from above)

    def query_location(self, region_id: str,
                       window: EventWindow = None,
                       current_game_time: float = 0.0) -> EntityQueryResult:
        """Query a geographic region as an entity"""
        return self.query_entity(f"region_{region_id}", window, current_game_time)

    def query_player_stat(self, stat_key: str) -> Any:
        """Quick Layer 1 lookup — delegates to stat_tracker"""
        # Fast path for aggregate player stats
        # e.g., query_player_stat("combat_stats.total_wolves_killed")
        ...

    def query_events_in_area(self, x: float, y: float, radius: float,
                              window: EventWindow = None,
                              current_game_time: float = 0.0,
                              tag_filter: List[str] = None) -> List[Dict]:
        """Raw Layer 2 query — events in a circular area"""
        events = get_windowed_events(
            self.event_store,
            window or EventWindow(),
            current_game_time,
            near_position=(x, y),
            radius=radius
        )
        if tag_filter:
            events = [e for e in events
                      if any(t in e.tags for t in tag_filter)]
        return [self._event_to_summary(e) for e in events]

    def query_interpretations(self, region_id: Optional[str] = None,
                               category: Optional[str] = None,
                               severity_min: Optional[str] = None,
                               ongoing_only: bool = False) -> List[InterpretedEvent]:
        """Direct Layer 3 query — for systems that need interpreted events"""
        return self.interpretation_store.query(
            region_id=region_id,
            category=category,
            severity_min=severity_min,
            ongoing_only=ongoing_only
        )
```

## Query Examples (User-Specified) — Walkthrough

### "What happened near the blacksmith in the last game-day?"

```python
result = world_query.query_entity(
    "npc_blacksmith_gareth",
    window=EventWindow(static_size=10, recency_period=24.0),  # 1 game-day
    current_game_time=current_time
)

# Returns:
# metadata: Gareth's name, position, tags (job:blacksmith, domain:smithing, resource:iron, ...)
# direct_events: trades, conversations with player, any events Gareth was part of
# nearby_relevant_events: smithing/iron/trade events near Gareth's position,
#   filtered by his interest tags (he notices iron mining nearby, not wolf hunting)
# local_context: Layer 4 summary for Blacksmith's Crossing locality
# regional_context: Layer 5 summary for Iron Hills district
# ongoing_conditions: any active interpretations matching Gareth's interests
```

### "Has the player been killing a lot of wolves?"

```python
# Fast path: Layer 1 aggregate
wolf_kills_total = world_query.query_player_stat("combat_stats.wolf_kills")

# Detail path: Layer 2 recent events
wolf_events = world_query.query_events_in_area(
    x=player.position.x, y=player.position.y,
    radius=9999,  # Global
    window=EventWindow(static_size=20, recency_period=50.0),
    current_game_time=current_time,
    tag_filter=["species:wolf"]
)

# Interpreted path: Layer 3
wolf_interpretations = world_query.query_interpretations(
    category="population_change",
    severity_min="moderate"
)
# Returns: "Wolf population declining in Whispering Woods" if it exists
```

### "Is iron scarce in the eastern forest?"

```python
result = world_query.query_entity(
    "region_eastern_forest",
    window=EventWindow(static_size=15, recency_period=20.0),
    current_game_time=current_time
)

# metadata: region description, tags (resource:iron, biome:forest, ...)
# direct_events: all events in this region (mining, gathering, combat)
# nearby_relevant_events: iron-related events filtered by region tags
# local_context: Layer 4 summary including resource pressure
# ongoing_conditions: any "iron shortage" or "resource pressure" interpretations
```

### "What does this NPC know about?"

```python
result = world_query.query_entity(
    "npc_elara_herbalist",
    window=EventWindow(static_size=10, recency_period=10.0),
    current_game_time=current_time
)

# metadata: Elara's tags tell you her interests (herbs, alchemy, wildlife, forest)
# direct_events: player interactions with her, trades
# nearby_relevant_events: herb gathering, alchemy, wildlife events near her position,
#   filtered by her interest tags (she doesn't notice combat unless wildlife is involved)
# local_context: what's happening in Whispering Woods
# ongoing_conditions: "wildlife declining" or "herb shortage" if applicable
```

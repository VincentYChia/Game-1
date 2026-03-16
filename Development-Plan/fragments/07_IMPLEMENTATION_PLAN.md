# Part 7: SQLite Schema, Integration Points, File Structure, Build Order

## SQLite Schema

All Layer 2 and Layer 3 data lives in a single SQLite database per save file.

```sql
-- ============================================
-- LAYER 2: Raw Event Records
-- ============================================
CREATE TABLE IF NOT EXISTS events (
    event_id TEXT PRIMARY KEY,
    event_type TEXT NOT NULL,
    event_subtype TEXT NOT NULL,

    -- WHO
    actor_id TEXT NOT NULL,
    actor_type TEXT NOT NULL,
    target_id TEXT,
    target_type TEXT,

    -- WHERE
    position_x REAL NOT NULL,
    position_y REAL NOT NULL,
    chunk_x INTEGER NOT NULL,
    chunk_y INTEGER NOT NULL,
    locality_id TEXT,
    district_id TEXT,
    province_id TEXT,
    biome TEXT,

    -- WHEN
    game_time REAL NOT NULL,
    real_time REAL NOT NULL,
    session_id TEXT,

    -- WHAT
    magnitude REAL DEFAULT 0.0,
    result TEXT DEFAULT 'success',
    quality TEXT,
    tier INTEGER,

    -- CONTEXT (JSON blob for event-specific data)
    context_json TEXT DEFAULT '{}',

    -- INTERPRETATION TRACKING
    interpretation_count INTEGER DEFAULT 0,
    triggered_interpretation INTEGER DEFAULT 0  -- SQLite boolean (0/1)
);

-- Indexes for common query patterns
CREATE INDEX IF NOT EXISTS idx_events_type ON events(event_type);
CREATE INDEX IF NOT EXISTS idx_events_subtype ON events(event_type, event_subtype);
CREATE INDEX IF NOT EXISTS idx_events_actor ON events(actor_id);
CREATE INDEX IF NOT EXISTS idx_events_target ON events(target_id);
CREATE INDEX IF NOT EXISTS idx_events_time ON events(game_time);
CREATE INDEX IF NOT EXISTS idx_events_locality ON events(locality_id);
CREATE INDEX IF NOT EXISTS idx_events_district ON events(district_id);
CREATE INDEX IF NOT EXISTS idx_events_chunk ON events(chunk_x, chunk_y);
CREATE INDEX IF NOT EXISTS idx_events_triggered ON events(triggered_interpretation)
    WHERE triggered_interpretation = 1;

-- Tags stored in a separate table for efficient tag-based queries
CREATE TABLE IF NOT EXISTS event_tags (
    event_id TEXT NOT NULL,
    tag TEXT NOT NULL,
    FOREIGN KEY (event_id) REFERENCES events(event_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_event_tags_tag ON event_tags(tag);
CREATE INDEX IF NOT EXISTS idx_event_tags_event ON event_tags(event_id);


-- ============================================
-- LAYER 3: Interpreted Events
-- ============================================
CREATE TABLE IF NOT EXISTS interpretations (
    interpretation_id TEXT PRIMARY KEY,
    created_at REAL NOT NULL,           -- Game time

    -- The narrative
    narrative TEXT NOT NULL,
    category TEXT NOT NULL,
    severity TEXT NOT NULL,

    -- Trigger info
    trigger_event_id TEXT,
    trigger_count INTEGER,
    cause_event_ids_json TEXT DEFAULT '[]',  -- JSON array of event_ids

    -- Spatial scope (JSON arrays of region IDs)
    affected_locality_ids_json TEXT DEFAULT '[]',
    affected_district_ids_json TEXT DEFAULT '[]',
    affected_province_ids_json TEXT DEFAULT '[]',
    epicenter_x REAL,
    epicenter_y REAL,

    -- Routing tags (JSON array)
    affects_tags_json TEXT DEFAULT '[]',

    -- Duration
    is_ongoing INTEGER DEFAULT 0,       -- SQLite boolean
    expires_at REAL,                    -- NULL = no expiry

    -- History
    supersedes_id TEXT,
    update_count INTEGER DEFAULT 1,

    -- Status
    archived INTEGER DEFAULT 0          -- Soft delete when superseded
);

CREATE INDEX IF NOT EXISTS idx_interp_category ON interpretations(category);
CREATE INDEX IF NOT EXISTS idx_interp_severity ON interpretations(severity);
CREATE INDEX IF NOT EXISTS idx_interp_created ON interpretations(created_at);
CREATE INDEX IF NOT EXISTS idx_interp_ongoing ON interpretations(is_ongoing)
    WHERE is_ongoing = 1 AND archived = 0;

-- Tags for interpretations (for matching against entity interests)
CREATE TABLE IF NOT EXISTS interpretation_tags (
    interpretation_id TEXT NOT NULL,
    tag TEXT NOT NULL,
    FOREIGN KEY (interpretation_id) REFERENCES interpretations(interpretation_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_interp_tags_tag ON interpretation_tags(tag);


-- ============================================
-- OCCURRENCE COUNTERS (for prime trigger tracking)
-- ============================================
CREATE TABLE IF NOT EXISTS occurrence_counts (
    actor_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    event_subtype TEXT NOT NULL,
    count INTEGER DEFAULT 0,
    PRIMARY KEY (actor_id, event_type, event_subtype)
);


-- ============================================
-- ENTITY STATE (activity logs, dynamic tags)
-- ============================================
CREATE TABLE IF NOT EXISTS entity_state (
    entity_id TEXT PRIMARY KEY,
    tags_json TEXT DEFAULT '[]',         -- Dynamic tag overrides
    activity_log_json TEXT DEFAULT '[]', -- Circular buffer of recent event_ids
    state_json TEXT DEFAULT '{}'         -- Entity-specific mutable state
);


-- ============================================
-- REGION STATE (Layer 4/5 aggregation data)
-- ============================================
CREATE TABLE IF NOT EXISTS region_state (
    region_id TEXT PRIMARY KEY,
    active_conditions_json TEXT DEFAULT '[]',
    recent_events_json TEXT DEFAULT '[]',
    summary_text TEXT DEFAULT '',
    last_updated REAL DEFAULT 0.0
);
```

## Integration Points with Existing Code

### Minimal Hooks into Existing Systems

The World Memory System integrates via **subscription to the GameEventBus** (already exists). The only code changes to existing files are publishing events that aren't currently published:

| File | Change | Events to Add |
|------|--------|--------------|
| `systems/quest_system.py` | Add 3 publish calls | `QUEST_ACCEPTED`, `QUEST_COMPLETED`, `QUEST_FAILED` |
| `core/game_engine.py` | Add publish in NPC interaction handler | `NPC_INTERACTION` |
| `systems/world_system.py` | Add publish on chunk load | `CHUNK_ENTERED` |
| `core/game_engine.py` | Add PositionSampler.update() to game loop | `POSITION_SAMPLE` |

**All other events** (`DAMAGE_DEALT`, `ENEMY_KILLED`, `RESOURCE_GATHERED`, `ITEM_CRAFTED`, `LEVEL_UP`, `EQUIPMENT_CHANGED`, `SKILL_ACTIVATED`, etc.) are **already published** by the GameEventBus.

### Initialization Sequence

Added to `GameEngine.__init__()` or a startup manager:

```python
# After existing database loading...

# 1. Geographic Registry
from ai.memory.geographic_registry import GeographicRegistry
geo_registry = GeographicRegistry.get_instance()
geo_registry.load_base_map("AI-Config.JSON/geographic-map.json")

# 2. Entity Registry
from ai.memory.entity_registry import EntityRegistry
entity_registry = EntityRegistry.get_instance()
entity_registry.load_from_npcs(npc_db)
entity_registry.load_from_regions(geo_registry)
entity_registry.register_player(character)

# 3. Event Store (SQLite)
from ai.memory.event_store import EventStore
event_store = EventStore(save_dir=get_save_path())

# 4. Interpretation Store
from ai.memory.interpretation_store import InterpretationStore
interpretation_store = InterpretationStore(event_store.db_connection)

# 5. Event Recorder (subscribes to bus)
from ai.memory.event_recorder import EventRecorder
event_recorder = EventRecorder.get_instance()
event_recorder.initialize(event_store, geo_registry, entity_registry, session_id)

# 6. Interpreter
from ai.memory.interpreter import WorldInterpreter
interpreter = WorldInterpreter.get_instance()
interpreter.initialize(event_store, geo_registry, entity_registry, interpretation_store)

# 7. Aggregation Manager
from ai.memory.aggregation import AggregationManager
aggregation = AggregationManager.get_instance()
aggregation.initialize(geo_registry, interpretation_store)

# 8. Query Interface
from ai.memory.query import WorldQuery
world_query = WorldQuery.get_instance()
world_query.initialize(entity_registry, geo_registry, event_store,
                       interpretation_store, aggregation)

# 9. Position Sampler (added to game loop)
from ai.memory.position_sampler import PositionSampler
position_sampler = PositionSampler()

# 10. Retention Manager (runs periodically)
from ai.memory.retention import EventRetentionManager
retention_manager = EventRetentionManager()
```

### Save/Load Integration

```python
# In save_manager.py — add to create_save_data():
save_data["memory_db_path"] = event_store.db_path  # Just record the path
# SQLite auto-persists, but we flush to ensure consistency:
event_store.flush()
entity_registry.save_state(event_store.db_connection)  # Save activity logs + dynamic tags
aggregation.save_state(event_store.db_connection)  # Save Layer 4/5 state

# In save_manager.py — add to load_game():
memory_db_path = save_data.get("memory_db_path")
if memory_db_path and os.path.exists(memory_db_path):
    event_store = EventStore(db_path=memory_db_path)
    entity_registry.load_state(event_store.db_connection)
    aggregation.load_state(event_store.db_connection)
else:
    # New game or legacy save — start fresh
    event_store = EventStore(save_dir=get_save_path())
```

## File Structure

```
Game-1-modular/
├── ai/                               # AI systems root (existing directory from plan)
│   └── memory/                       # World Memory System (ALL NEW)
│       ├── __init__.py
│       │
│       │── # Core Data Layer
│       ├── event_schema.py           # WorldMemoryEvent, EventType, InterpretedEvent dataclasses
│       ├── event_store.py            # SQLite EventStore (Layer 2 read/write)
│       ├── interpretation_store.py   # SQLite InterpretationStore (Layer 3 read/write)
│       │
│       │── # Geographic System
│       ├── geographic_registry.py    # GeographicRegistry, Region, RegionState
│       ├── procedural_geographer.py  # Optional: generate map from biome data
│       │
│       │── # Entity System
│       ├── entity_registry.py        # EntityRegistry, WorldEntity, EntityType
│       ├── tag_relevance.py          # calculate_relevance() and tag matching utilities
│       │
│       │── # Pipeline Components
│       ├── event_recorder.py         # EventRecorder (bus subscriber → SQLite writer)
│       ├── interpreter.py            # WorldInterpreter + PatternEvaluator base class
│       ├── evaluators/               # Pattern evaluator implementations
│       │   ├── __init__.py
│       │   ├── population.py         # PopulationChangeEvaluator
│       │   ├── resources.py          # ResourcePressureEvaluator
│       │   ├── player_milestones.py  # PlayerMilestoneEvaluator
│       │   ├── area_danger.py        # AreaDangerEvaluator
│       │   ├── crafting.py           # CraftingTrendEvaluator
│       │   ├── exploration.py        # ExplorationPatternEvaluator
│       │   └── social.py             # SocialPatternEvaluator
│       ├── aggregation.py            # AggregationManager, LocalKnowledge, RegionalKnowledge
│       │
│       │── # Query Interface
│       ├── query.py                  # WorldQuery, EntityQueryResult, EventWindow
│       │
│       │── # Maintenance
│       ├── retention.py              # EventRetentionManager (pruning)
│       ├── position_sampler.py       # PositionSampler (periodic breadcrumbs)
│       │
│       │── # Testing
│       └── test_memory_system.py     # Unit tests for all components
│
├── AI-Config.JSON/                   # AI configuration (existing directory from plan)
│   ├── geographic-map.json           # NEW: Region definitions for the world
│   ├── region-name-pools.json        # NEW: Name pools for procedural region naming
│   └── interpreter-thresholds.json   # NEW: Configurable thresholds for pattern evaluators
```

## Build Order — Implementation Phases

### Phase A: Foundation (No Game Integration)

Build and test the core data layer independently. No changes to existing game code.

**A1: SQLite Event Store**
- `event_schema.py` — dataclasses for WorldMemoryEvent, InterpretedEvent
- `event_store.py` — SQLite create/read/query for Layer 2
- `interpretation_store.py` — SQLite create/read/query for Layer 3
- **Test**: Create events programmatically, query them, verify indexes work

**A2: Geographic Registry**
- `geographic_registry.py` — Region, RegionState, position-to-region lookup
- `AI-Config.JSON/geographic-map.json` — hand-author a basic map for the existing world
- **Test**: Load map, verify position lookups, verify hierarchy traversal

**A3: Entity Registry**
- `entity_registry.py` — WorldEntity, EntityRegistry, tag index
- `tag_relevance.py` — calculate_relevance()
- **Test**: Register entities with tags, verify tag search, verify relevance scoring

### Phase B: Pipeline (Requires Bus Subscription)

Wire up the recording and interpretation pipeline.

**B1: Event Recorder**
- `event_recorder.py` — subscribe to bus, convert events, write to SQLite
- `position_sampler.py` — periodic position recording
- **Integration**: Add bus.subscribe("*") call in initialization
- **Test**: Play the game briefly, verify events appear in SQLite

**B2: Interpreter**
- `interpreter.py` — WorldInterpreter base, prime number checking
- `evaluators/population.py` — first evaluator (wolf kills → population change)
- `evaluators/resources.py` — second evaluator (mining → resource pressure)
- `AI-Config.JSON/interpreter-thresholds.json` — configurable thresholds
- **Test**: Generate enough events to trigger primes, verify interpretations created

**B3: Aggregation**
- `aggregation.py` — AggregationManager, Layer 4/5 compilation
- **Test**: Verify interpretations flow to region states, summaries generated

### Phase C: Query Interface

**C1: WorldQuery**
- `query.py` — WorldQuery, dual window system, entity-first queries
- **Test**: Query NPCs, regions, player — verify correct data assembly

**C2: Retention**
- `retention.py` — EventRetentionManager, pruning logic
- **Test**: Generate 10K+ events, run pruning, verify milestones kept

### Phase D: Integration

**D1: Minimal Existing Code Changes**
- Add missing event publishes (quest, NPC interaction, chunk enter)
- Add PositionSampler to game loop
- Add initialization sequence to GameEngine
- Add save/load hooks

**D2: End-to-End Test**
- Play the game for 30+ minutes
- Verify: events recorded, interpretations generated, regions have state
- Query the system as an NPC would — verify useful results

### Phase E: Polish & Evaluator Expansion

**E1: Additional Evaluators**
- `evaluators/player_milestones.py`
- `evaluators/area_danger.py`
- `evaluators/crafting.py`
- `evaluators/exploration.py`
- `evaluators/social.py`

**E2: Procedural Geography (Optional)**
- `procedural_geographer.py` — generate map from biome data
- Test with different world seeds

**E3: Performance Testing**
- Benchmark with 100K+ events
- Verify query response times < 10ms
- Verify pruning keeps database manageable

## Estimated File Sizes

| File | Est. Lines | Complexity |
|------|-----------|------------|
| `event_schema.py` | 150-200 | Dataclasses, enums |
| `event_store.py` | 250-350 | SQLite CRUD, indexes |
| `interpretation_store.py` | 150-200 | SQLite CRUD for Layer 3 |
| `geographic_registry.py` | 200-300 | Region loading, spatial lookup, cache |
| `entity_registry.py` | 250-350 | Entity CRUD, tag index, loading from NPCs |
| `tag_relevance.py` | 60-100 | Tag matching utility |
| `event_recorder.py` | 300-400 | Bus subscriber, event conversion, enrichment |
| `interpreter.py` | 200-300 | Base interpreter, prime checking, dispatch |
| `evaluators/*.py` | 100-200 each | 7 evaluators × ~150 = ~1,050 |
| `aggregation.py` | 200-300 | Layer 4/5 maintenance |
| `query.py` | 300-400 | WorldQuery, dual window, result assembly |
| `retention.py` | 150-200 | Pruning logic |
| `position_sampler.py` | 50-80 | Simple timer + publish |
| **Total** | **~2,500-3,500** | |

Plus JSON configs (~200-400 lines) and tests (~500-800 lines).

## Dependencies

**Python standard library only** (no new pip packages):
- `sqlite3` — database
- `uuid` — event IDs
- `json` — serialization
- `math` — distance calculations
- `time` — timestamps
- `dataclasses` — data structures
- `enum` — type enums
- `typing` — type hints

**Existing codebase dependencies**:
- `events/event_bus.py` — GameEventBus subscription
- `data/models/world.py` — Position dataclass
- `data/databases/npc_db.py` — NPC loading
- `systems/biome_generator.py` — chunk biome data (for procedural geography)
- `core/config.py` — Config constants (CHUNK_SIZE, etc.)

## Connection to Downstream Systems

This memory system is **Phase 2.1** of the Living World plan. It provides the data layer that all subsequent phases consume:

- **Phase 2.3 (NPC Agents)**: Call `world_query.query_entity("npc_X")` to get context for NPC dialogue generation
- **Phase 2.4 (Factions)**: Read interpreted events with faction-related tags to track faction state
- **Phase 2.5 (Ecosystem)**: Read resource pressure interpretations to adjust spawn rates
- **Phase 2.6 (World Events)**: Read Layer 5 regional patterns to trigger world events
- **Phase 2.7 (Quest Generation)**: Call `world_query.query_entity()` for quest context
- **Phase 3 (Player Intelligence)**: Query Layer 2 events to build player behavior profile
- **Narrative Threads** (from scratchpad): Layer 3 interpretations become the input for narrative thread creation/management

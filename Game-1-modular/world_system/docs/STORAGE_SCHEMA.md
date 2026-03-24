# Storage Schema — All 7 Layers

**Created**: 2026-03-24
**Scope**: Every SQL table, what layer it belongs to, and how data flows between them

---

## Existing Tables (Layers 1-3)

These are implemented in `world_memory/event_store.py`.

### Layer 2 — Structured Events

```sql
-- Every game action as a structured fact
CREATE TABLE events (
    event_id TEXT PRIMARY KEY,
    event_type TEXT NOT NULL,          -- "enemy_killed", "resource_gathered", etc.
    event_subtype TEXT NOT NULL,        -- "killed_wolf", "gathered_iron_ore", etc.
    actor_id TEXT NOT NULL,            -- "player", npc_id, etc.
    actor_type TEXT NOT NULL,          -- "player", "npc", "world"
    target_id TEXT,
    target_type TEXT,
    position_x REAL NOT NULL,
    position_y REAL NOT NULL,
    chunk_x INTEGER NOT NULL,
    chunk_y INTEGER NOT NULL,
    locality_id TEXT,
    district_id TEXT,
    province_id TEXT,
    biome TEXT,
    game_time REAL NOT NULL,
    real_time REAL NOT NULL,
    session_id TEXT,
    magnitude REAL DEFAULT 0.0,        -- damage amount, gather quantity, etc.
    result TEXT DEFAULT 'success',
    quality TEXT,                       -- "normal", "fine", "superior", "masterwork", "legendary"
    tier INTEGER,
    context_json TEXT DEFAULT '{}',     -- Flexible key-value for event-specific data
    interpretation_count INTEGER DEFAULT 0,
    triggered_interpretation INTEGER DEFAULT 0
);
-- 9 indexes on type, subtype, actor, target, time, locality, district, chunk, triggered

-- Interest-matching tags per event
CREATE TABLE event_tags (
    event_id TEXT NOT NULL REFERENCES events(event_id) ON DELETE CASCADE,
    tag TEXT NOT NULL
);
-- Indexes on tag and event_id

-- Milestone trigger tracking: (actor, type, subtype) → cumulative count
CREATE TABLE occurrence_counts (
    actor_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    event_subtype TEXT NOT NULL,
    count INTEGER DEFAULT 0,
    PRIMARY KEY (actor_id, event_type, event_subtype)
);
```

### Layer 3 — Simple Interpretations

```sql
-- Narrative descriptions produced by Layer 3 evaluators
CREATE TABLE interpretations (
    interpretation_id TEXT PRIMARY KEY,
    created_at REAL NOT NULL,          -- Game time
    narrative TEXT NOT NULL,            -- The one-sentence description
    category TEXT NOT NULL,            -- "population_change", "combat_proficiency", etc.
    severity TEXT NOT NULL,            -- "minor", "moderate", "significant", "major", "critical"
    trigger_event_id TEXT,             -- Which event triggered this evaluation
    trigger_count INTEGER,             -- The milestone count that fired
    cause_event_ids_json TEXT DEFAULT '[]',
    affected_locality_ids_json TEXT DEFAULT '[]',
    affected_district_ids_json TEXT DEFAULT '[]',
    affected_province_ids_json TEXT DEFAULT '[]',
    epicenter_x REAL,
    epicenter_y REAL,
    affects_tags_json TEXT DEFAULT '[]',
    is_ongoing INTEGER DEFAULT 0,
    expires_at REAL,
    supersedes_id TEXT,                -- Previous interpretation this replaces
    update_count INTEGER DEFAULT 1,
    archived INTEGER DEFAULT 0
);
-- Indexes on category, severity, created_at, ongoing

CREATE TABLE interpretation_tags (
    interpretation_id TEXT NOT NULL REFERENCES interpretations(interpretation_id) ON DELETE CASCADE,
    tag TEXT NOT NULL
);
```

### Supporting Tables (Existing)

```sql
-- Per-entity persistent state (activity logs, tags)
CREATE TABLE entity_state (
    entity_id TEXT PRIMARY KEY,
    tags_json TEXT DEFAULT '[]',
    activity_log_json TEXT DEFAULT '[]',
    state_json TEXT DEFAULT '{}'
);

-- Per-region aggregated state (active conditions, recent events)
CREATE TABLE region_state (
    region_id TEXT PRIMARY KEY,
    active_conditions_json TEXT DEFAULT '[]',
    recent_events_json TEXT DEFAULT '[]',
    summary_text TEXT DEFAULT '',
    last_updated REAL DEFAULT 0.0
);

-- Per-NPC memory
CREATE TABLE npc_memory (
    npc_id TEXT PRIMARY KEY,
    relationship_score REAL DEFAULT 0.0,
    interaction_count INTEGER DEFAULT 0,
    last_interaction_time REAL DEFAULT 0.0,
    emotional_state TEXT DEFAULT 'neutral',
    knowledge_json TEXT DEFAULT '[]',
    conversation_summary TEXT DEFAULT '',
    reputation_tags_json TEXT DEFAULT '[]',
    quest_state_json TEXT DEFAULT '{}'
);

-- Faction reputation
CREATE TABLE faction_state (
    faction_id TEXT PRIMARY KEY,
    player_reputation REAL DEFAULT 0.0,
    crossed_milestones_json TEXT DEFAULT '[]',
    last_change_reason TEXT DEFAULT '',
    last_change_time REAL DEFAULT 0.0
);

CREATE TABLE faction_reputation_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    faction_id TEXT NOT NULL,
    delta REAL NOT NULL,
    new_score REAL NOT NULL,
    reason TEXT DEFAULT '',
    game_time REAL DEFAULT 0.0,
    is_ripple INTEGER DEFAULT 0
);

-- Biome resource pools
CREATE TABLE biome_resource_state (
    biome_type TEXT NOT NULL,
    resource_id TEXT NOT NULL,
    initial_total INTEGER DEFAULT 100,
    current_total REAL DEFAULT 100.0,
    total_gathered INTEGER DEFAULT 0,
    regeneration_rate REAL DEFAULT 300.0,
    is_scarce INTEGER DEFAULT 0,
    is_critical INTEGER DEFAULT 0,
    PRIMARY KEY (biome_type, resource_id)
);
```

---

## New Tables (Layers 4-7)

### Layer 4 — Connected Interpretations

```sql
CREATE TABLE connected_interpretations (
    connection_id TEXT PRIMARY KEY,
    created_at REAL NOT NULL,
    narrative TEXT NOT NULL,            -- "The player is plundering Iron Hills..."
    category TEXT NOT NULL,            -- "regional_activity", "cross_domain", "player_identity", "faction_narrative"
    severity TEXT NOT NULL,

    -- What Layer 3 interpretations fed into this
    source_interpretation_ids_json TEXT DEFAULT '[]',

    -- Geographic scope (district to province)
    affected_district_ids_json TEXT DEFAULT '[]',
    affected_province_ids_json TEXT DEFAULT '[]',

    -- Tags for interest matching
    affects_tags_json TEXT DEFAULT '[]',

    -- Lifecycle
    is_ongoing INTEGER DEFAULT 0,
    expires_at REAL,
    supersedes_id TEXT,
    update_count INTEGER DEFAULT 1,
    archived INTEGER DEFAULT 0
);

CREATE TABLE connected_interpretation_tags (
    connection_id TEXT NOT NULL REFERENCES connected_interpretations(connection_id) ON DELETE CASCADE,
    tag TEXT NOT NULL
);
```

### Layer 5 — Province Summaries

```sql
CREATE TABLE province_summaries (
    summary_id TEXT PRIMARY KEY,
    province_id TEXT NOT NULL,
    created_at REAL NOT NULL,
    narrative TEXT NOT NULL,            -- "The northern province has been largely cleared..."

    -- What Layer 4 connections fed this
    source_connection_ids_json TEXT DEFAULT '[]',

    -- Key metrics snapshot at time of summary
    dominant_activity TEXT,             -- "combat", "crafting", "gathering", "exploration"
    threat_level TEXT,                  -- "safe", "moderate", "dangerous", "deadly"
    resource_pressure TEXT,            -- "healthy", "strained", "critical"
    population_trend TEXT,             -- "growing", "stable", "declining", "devastated"

    affects_tags_json TEXT DEFAULT '[]',
    supersedes_id TEXT,
    archived INTEGER DEFAULT 0
);
```

### Layer 6 — Realm State

```sql
CREATE TABLE realm_state (
    realm_id TEXT PRIMARY KEY DEFAULT 'main',
    last_updated REAL NOT NULL,

    -- Economic snapshot
    global_resource_pressure_json TEXT DEFAULT '{}',  -- resource_id → pressure_level
    trade_state_json TEXT DEFAULT '{}',

    -- Political snapshot
    faction_power_json TEXT DEFAULT '{}',             -- faction_id → influence score
    territorial_control_json TEXT DEFAULT '{}',       -- province_id → dominant faction

    -- Player standing at national scale
    player_reputation_summary TEXT DEFAULT '',        -- "Known warrior, respected by Guard"
    player_achievement_summary TEXT DEFAULT '',       -- "Level 20, Master Smith, Wolf Hunter"

    -- Active conflicts / alliances
    active_conflicts_json TEXT DEFAULT '[]',

    narrative TEXT DEFAULT ''                          -- Overall realm description
);
```

### Layer 7 — World Narrative

```sql
-- The world's identity and active story threads
CREATE TABLE world_narrative (
    world_id TEXT PRIMARY KEY DEFAULT 'main',
    last_updated REAL NOT NULL,

    -- World identity
    world_themes_json TEXT DEFAULT '[]',              -- ["frontier", "magical_resurgence"]
    world_epoch TEXT DEFAULT 'The First Age',
    world_tone TEXT DEFAULT 'hopeful',                -- "hopeful", "dark", "tense", "mysterious"

    -- History
    creation_myths_json TEXT DEFAULT '[]',            -- Immutable lore
    historical_events_json TEXT DEFAULT '[]',         -- Resolved threads become history

    -- Generation counters
    content_generated_json TEXT DEFAULT '{}',
    last_major_event_time REAL DEFAULT 0.0
);

-- Active and resolved narrative threads
CREATE TABLE narrative_threads (
    thread_id TEXT PRIMARY KEY,
    created_at REAL NOT NULL,
    source TEXT NOT NULL,               -- "player_action", "npc_rumor", "world_event", "developer"

    -- The narrative element
    theme TEXT NOT NULL,                -- "war", "plague", "discovery", "migration"
    summary TEXT NOT NULL,              -- "A war is brewing in the western territories"
    canonical_facts_json TEXT DEFAULT '[]',
    unresolved_questions_json TEXT DEFAULT '[]',

    -- Spatial anchoring
    origin_province_id TEXT,
    spread_radius REAL DEFAULT 0.0,
    relevance_by_region_json TEXT DEFAULT '{}',  -- region_id → relevance (0.0-1.0)

    -- State
    status TEXT DEFAULT 'rumor',        -- "rumor", "developing", "active", "resolved", "forgotten"
    significance REAL DEFAULT 0.5,
    last_referenced REAL DEFAULT 0.0,

    -- Generation hints for content tools
    generation_hints_json TEXT DEFAULT '{}',

    -- Lifecycle
    resolved_at REAL,
    decay_rate REAL DEFAULT 0.01        -- Significance loss per game-time unit when unreferenced
);
```

---

## Data Flow Summary

```
Player Action
    │
    ▼
Layer 1: stat_tracker++              (in-memory, always)
Layer 2: INSERT INTO events          (SQLite, always)
    │
    ├── occurrence_counts++
    ├── if milestone threshold hit:
    │       ▼
    │   Layer 3: evaluators examine → INSERT INTO interpretations (if notable)
    │       │
    │       ├── region_state updated
    │       ├── npc knowledge updated (via gossip)
    │       ├── if accumulation threshold hit:
    │       │       ▼
    │       │   Layer 4: connected evaluators → INSERT INTO connected_interpretations
    │       │       │
    │       │       ├── if province-level pattern:
    │       │       │       ▼
    │       │       │   Layer 5: INSERT INTO province_summaries
    │       │       │       │
    │       │       │       ├── if multi-province pattern:
    │       │       │       │       ▼
    │       │       │       │   Layer 6: UPDATE realm_state
    │       │       │       │       │
    │       │       │       │       ├── if world-shaping:
    │       │       │       │       │       ▼
    │       │       │       │       │   Layer 7: UPDATE world_narrative / INSERT narrative_threads
```

Most events stop at Layer 2. A significant minority reach Layer 3. Few reach Layer 4. Layer 5+ is rare and impactful.

# World Memory System — Layer 1-2 Redesign Decisions

**Date**: 2026-04-09  
**Status**: Design finalized, implementation pending  
**Scope**: Layer 1 schema (DONE), prompt system (designed), temporal store (designing)

---

## 1A. Fact Recording Criteria (RESOLVED)

### What Gets Recorded in the Fact Store

The system uses a **two-tier filter** on GameEventBus events:

**Tier 1 — Skip visual-only events** (5 events dropped):
`SCREEN_SHAKE`, `PARTICLE_BURST`, `FLASH_ENTITY`, `ATTACK_PHASE`, `ATTACK_STARTED`

**Tier 2 — Only mapped events recorded** (28 bus events → 16 memory types):

| Bus Event | Memory Type | Frequency |
|-----------|------------|-----------|
| DAMAGE_DEALT | attack_performed | High (combat) |
| PLAYER_HIT | damage_taken | High (combat) |
| ENEMY_KILLED | enemy_killed | Medium |
| PLAYER_DIED | player_death | Rare |
| DODGE_PERFORMED | dodge_performed | Medium (combat) |
| STATUS_APPLIED | status_applied | Medium (combat) |
| RESOURCE_GATHERED | resource_gathered | Medium |
| NODE_DEPLETED | node_depleted | Low |
| ITEM_CRAFTED | craft_attempted | Low |
| ITEM_INVENTED | item_invented | Rare |
| RECIPE_DISCOVERED | recipe_discovered | Rare |
| ITEM_ACQUIRED | item_acquired | Medium |
| EQUIPMENT_CHANGED / ITEM_EQUIPPED | item_equipped | Low |
| REPAIR_PERFORMED | repair_performed | Low |
| LEVEL_UP | level_up | Rare |
| SKILL_LEARNED | skill_learned | Rare |
| SKILL_ACTIVATED | skill_used | High (combat) |
| TITLE_EARNED | title_earned | Rare |
| CLASS_CHANGED | class_changed | Rare |
| CHUNK_ENTERED | chunk_entered | Medium (exploration) |
| AREA_DISCOVERED | area_discovered | Rare |
| NPC_INTERACTION | npc_interaction | Low |
| QUEST_ACCEPTED | quest_accepted | Low |
| QUEST_COMPLETED | quest_completed | Low |
| QUEST_FAILED | quest_failed | Rare |
| WORLD_EVENT | world_event | Rare |
| POSITION_SAMPLE | position_sample | Every ~10 real seconds |

### What is NOT Recorded

- **Individual player steps/tile movement**: No `PLAYER_MOVED` event exists. Movement is tracked as:
  - `CHUNK_ENTERED` — fires at 16×16 chunk boundaries (~every 2-3 seconds while exploring)
  - `POSITION_SAMPLE` — periodic breadcrumb every ~10 real seconds
  - `StatTracker.record_movement()` — accumulates `exploration.distance` in StatStore (aggregate only)
- **Menu clicks, camera, UI interactions**: No bus events exist for these
- **Individual attack frames/animations**: Filtered by SKIP_BUS_EVENTS
- **Any event not in BUS_TO_MEMORY_TYPE mapping**: Silently dropped

### Performance Impact

At peak gameplay (active combat): ~10 events/minute  
At exploration: ~2-3 events/minute  
At idle/menu: ~0.1 events/minute (position samples only)  
Average mixed play: ~5 events/minute  

Each event = ~18 SQL operations across StatStore + Fact Store.  
SQLite WAL mode capacity: 10,000+ ops/sec.  
**Actual usage: <2% of SQLite capacity. Not a bottleneck.**

### Source of Truth References

- Filter logic: `world_system/world_memory/event_schema.py` (BUS_TO_MEMORY_TYPE, SKIP_BUS_EVENTS)
- Recording pipeline: `world_system/world_memory/event_recorder.py` (_on_bus_event method)
- Bus subscription: Priority -10 (runs before all other handlers)

---

## 1B. Tag-Based Prompt Fragment System

### Purpose

Layer 2 evaluators will call an LLM (Claude as stopgap, local model as target) to produce
one-sentence factual narrations. The LLM needs enough context to narrate accurately without
misinterpreting the data. The prompt system provides this context via **modular fragments
selected by tags**.

### Architecture

```
ASSEMBLED PROMPT = core_context          (always included)
                 + domain_fragment       (one per trigger, selected by domain: tag)
                 + entity_fragments      (0-3, selected by species:/resource:/discipline: etc.)
                 + data_block            (dynamic, assembled from StatStore + temporal data)
                 + output_instruction    (always included)
```

### Fragment Categories and Counts

| Category | Tag Pattern | Count | Purpose |
|----------|-----------|-------|---------|
| Core | `_core` | 1 | Game description, tier system, world basics |
| Output | `_output` | 1 | Format instructions for the LLM |
| Domain | `domain:*` | 10 | Evaluator lens (combat, gathering, crafting, etc.) |
| Species | `species:*` | 13 | Enemy descriptions (tier, biome, behavior) |
| Material Category | `material_category:*` | 5 | Resource type context (ore, tree, stone, plant, fish) |
| Discipline | `discipline:*` | 6 | Craft discipline mechanics |
| Tier | `tier:*` | 4 | Significance scaling context |
| Element | `element:*` | 8 | Damage type implications |
| Rank | `rank:*` | 3 | Enemy rank significance (normal, boss, unique) |
| Status Effect | `status_effect:*` | 13 | Effect type context (DoT, CC, buff) |
| **Total** | | **64** | |

Each fragment is 1-3 sentences (~10-40 tokens). A typical assembled prompt uses 4-5 fragments
totaling ~180-250 system tokens + ~100-150 data block tokens = **~300-400 tokens input**.

### Fragment Selection Logic

```python
FRAGMENT_CATEGORIES = {"species", "material_category", "discipline", 
                       "tier", "element", "rank", "status_effect"}

def select_fragments(trigger_tags, fragment_library):
    selected = [fragment_library["_core"]]
    
    # Domain (required — exactly one)
    for tag in trigger_tags:
        if tag.startswith("domain:") and tag in fragment_library:
            selected.append(fragment_library[tag])
            break
    
    # Entity/context (optional — add all matching)
    for tag in trigger_tags:
        cat = tag.split(":")[0]
        if cat in FRAGMENT_CATEGORIES and tag in fragment_library:
            selected.append(fragment_library[tag])
    
    selected.append(fragment_library["_output"])
    return [f for f in selected if f]
```

### Fallback Chain

When a tag has no matching fragment:
1. `species:new_enemy` → not found → fall back to `tier:N` (from enemy data)
2. `resource:new_material` → not found → fall back to `material_category:X`
3. `discipline:new_craft` → not found → fall back to `domain:crafting`
4. If all fail → domain fragment alone provides sufficient context

### Auto-Expansion (Future Feature)

When the game encounters an entity with no matching fragment:

1. System detects missing fragment for tag `species:void_horror`
2. Reads the entity's game data from JSON definitions (tier, biome, attack types, description)
3. Calls BackendManager with a meta-prompt containing:
   - Full game context (the `_core` fragment)
   - The entity's game data
   - Examples of existing fragments for similar entities
   - Instruction: "Write a 1-2 sentence fragment describing this entity for narration context"
4. Stores the generated fragment in `prompt_fragments.json` indexed by `species:void_horror`
5. All future evaluator triggers for this entity use the generated fragment

**Key requirement**: The meta-prompt must include comprehensive game context so the generated
fragment is accurate. The `_core` fragment + relevant domain fragment + entity game data
provides this. The LLM generating the fragment should be the most capable available model
(Claude), not the fast local model, since fragment generation is rare (once per new entity)
and accuracy matters more than speed.

**Indexing**: Fragments are always indexed by a single tag string (`species:X`, `tier:N`, etc.).
This means any game system that produces tagged data automatically integrates with the prompt
system. No manual wiring needed — the tag IS the index.

### Storage

File: `world_system/config/prompt_fragments.json`

Structure:
```json
{
  "_meta": {
    "version": "1.0",
    "total_fragments": 64,
    "auto_generation": {
      "enabled": false,
      "meta_prompt_includes": ["_core", "relevant domain fragment", "entity game data"],
      "preferred_model": "claude (high accuracy, infrequent calls)",
      "index_by": "tag string"
    }
  },
  "_core": "...",
  "_output": "...",
  "domain:combat": "...",
  "species:wolf_grey": "...",
  "tier:1": "..."
}
```

### Integration Points

- **StatStore** provides the data block (tag-based queries for relevant stats)
- **Temporal store** provides trend/recency data (today, week average, trend)
- **BackendManager** routes LLM calls (Claude → Ollama → Mock fallback)
- **Evaluator infrastructure** decides WHEN to call (threshold triggers)
- **Fragment library** decides WHAT context to include (tag matching)

---

## Section 3 Decisions (Resolved)

### Counters — REMOVED

The following tables are confirmed redundant and will be removed:

| Table | Why Redundant |
|-------|--------------|
| `occurrence_counts` | StatStore has same data (e.g., `combat.kills.species.wolf = 47`). TriggerManager does its own in-memory counting. This table is written to but read by nobody. |
| `regional_counters` | Never written to by any code. Dead table. |
| `interpretation_counters` | Never written to by any code. Dead table. |

### Consumer/State Tables — MOVED TO CONSUMERS

| Table | New Home |
|-------|---------|
| `npc_memory` | NPCMemoryManager (already manages this data in-memory) |
| `faction_state`, `faction_reputation_history` | FactionSystem (already manages this) |
| `biome_resource_state` | EcosystemAgent (already manages this) |
| `entity_state` | EntityRegistry (in-memory) |
| `region_state` | GeographicRegistry (in-memory) |

### Trigger Tables — REMOVED

| Table | Why |
|-------|-----|
| `event_triggers` | Never written to. Dead code. |
| `pacing_state` | Never written to. Dead code. |

### Layer 2+ Tables — MOVED TO LAYERSTORE

| Table | Already Exists In LayerStore |
|-------|-----|
| `interpretations`, `interpretation_tags` | `layer2_events`, `layer2_tags` |
| `connected_interpretations`, `connected_interpretation_tags` | `layer3_events`, `layer3_tags` |
| `province_summaries` | `layer4_events` |
| `region_state` (previously `realm_state`, renamed in the 2026-04-16 hierarchy alignment; dormant table retained for schema compat) | `layer5_events` |
| `world_narrative`, `narrative_threads` | `layer7_events` |

### What Remains — Temporal Fact Store (FINALIZED)

---

## Temporal Storage System

### Overview

Three SQL tiers capture the time dimension that StatStore (all-time aggregates) cannot:

```
Tier 1: CURRENT DAY EVENTS — individual events as they happen (cleared at day end)
Tier 2: DAILY SUMMARIES    — one detailed row per completed game-day (kept forever)
Tier 3: MONTHLY SUMMARIES  — one row per 30-day period (kept forever, computed from Tier 2)
```

All tiers are proper SQL tables. No JSON blobs for primary data. No row limits.

**Game time reference** (single source of truth):
- `game_engine.py:443` — `CYCLE_LENGTH = 1440.0` seconds (24 real minutes = 1 game day/night cycle)
- `game_engine.py:7635` — `self.game_time += dt` (continuous clock)
- `game_day = int(game_time / CYCLE_LENGTH)`
- Day boundary detected by `DailyLedgerManager.check_day_boundary(game_time)`
- A "month" = every 30 game-days (no in-game month concept; we define this boundary)

### Tier 1: Current Day Events

Individual events recorded as they happen during the current game-day.
Cleared at each day boundary after being summarized into a Tier 2 row.

```sql
CREATE TABLE current_day_events (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    event_type  TEXT NOT NULL,       -- "enemy_killed", "resource_gathered", etc.
    event_subtype TEXT NOT NULL,     -- "killed_wolf", "gathered_iron_ore", etc.
    game_time   REAL NOT NULL,       -- exact game_time of the event
    locality_id TEXT,                -- where it happened
    actor_id    TEXT NOT NULL DEFAULT 'player',
    target_id   TEXT,                -- what was acted on
    magnitude   REAL DEFAULT 0.0,    -- damage, quantity, etc.
    tier        INTEGER,
    tags        TEXT DEFAULT '[]'    -- JSON array of tags from event
);
CREATE INDEX idx_cde_type ON current_day_events(event_type);
CREATE INDEX idx_cde_time ON current_day_events(game_time);
```

This is the "running journal" for today. Max ~50-150 rows per day during heavy play.
It is the ONLY place with individual event detail for the current day.
At day boundary: summarized → Tier 2 row, then `DELETE FROM current_day_events`.

### Tier 2: Daily Summaries

One row per completed game-day. Complete aggregate picture of what happened.
Reading one row tells you everything the player did that day.

Two tables: `daily_summary` for fixed domain totals, `daily_detail` for per-entity breakdowns.

```sql
CREATE TABLE daily_summary (
    game_day                INTEGER PRIMARY KEY,
    game_month              INTEGER NOT NULL,       -- int(game_day / 30)
    game_time_start         REAL NOT NULL,
    game_time_end           REAL NOT NULL,

    -- Combat
    combat_kills            INTEGER DEFAULT 0,
    combat_kills_t1         INTEGER DEFAULT 0,
    combat_kills_t2         INTEGER DEFAULT 0,
    combat_kills_t3         INTEGER DEFAULT 0,
    combat_kills_t4         INTEGER DEFAULT 0,
    combat_damage_dealt     REAL DEFAULT 0.0,
    combat_damage_taken     REAL DEFAULT 0.0,
    combat_highest_hit      REAL DEFAULT 0.0,
    combat_deaths           INTEGER DEFAULT 0,
    combat_dodges           INTEGER DEFAULT 0,
    combat_blocks           INTEGER DEFAULT 0,
    combat_healing          REAL DEFAULT 0.0,
    combat_crits            INTEGER DEFAULT 0,
    combat_status_applied   INTEGER DEFAULT 0,

    -- Gathering
    gathering_collected     INTEGER DEFAULT 0,
    gathering_actions       INTEGER DEFAULT 0,
    gathering_nodes_depleted INTEGER DEFAULT 0,
    gathering_unique_resources INTEGER DEFAULT 0,

    -- Crafting
    crafting_attempts       INTEGER DEFAULT 0,
    crafting_successes      INTEGER DEFAULT 0,
    crafting_unique_disciplines INTEGER DEFAULT 0,
    crafting_materials_used INTEGER DEFAULT 0,

    -- Exploration
    exploration_chunks      INTEGER DEFAULT 0,
    exploration_distance    REAL DEFAULT 0.0,
    exploration_discoveries INTEGER DEFAULT 0,

    -- Social
    social_npc_interactions INTEGER DEFAULT 0,
    social_quests_accepted  INTEGER DEFAULT 0,
    social_quests_completed INTEGER DEFAULT 0,
    social_quests_failed    INTEGER DEFAULT 0,

    -- Economy
    economy_gold_earned     REAL DEFAULT 0.0,
    economy_gold_spent      REAL DEFAULT 0.0,
    economy_items_acquired  INTEGER DEFAULT 0,

    -- Progression
    progression_levels      INTEGER DEFAULT 0,
    progression_exp         REAL DEFAULT 0.0,
    progression_skills_used INTEGER DEFAULT 0,
    progression_mana_spent  REAL DEFAULT 0.0,

    -- Computed
    primary_activity        TEXT DEFAULT 'idle',    -- domain with most events
    top_species             TEXT DEFAULT '',         -- most-killed enemy type
    top_resource            TEXT DEFAULT '',         -- most-gathered resource
    top_discipline          TEXT DEFAULT ''          -- most-used craft discipline
);
CREATE INDEX idx_ds_month ON daily_summary(game_month);
```

Per-entity breakdowns:
```sql
CREATE TABLE daily_detail (
    game_day    INTEGER NOT NULL,
    domain      TEXT NOT NULL,       -- "combat", "gathering", "crafting"
    entity      TEXT NOT NULL,       -- "wolf_grey", "iron_ore", "smithing"
    count       INTEGER DEFAULT 0,
    total       REAL DEFAULT 0.0,    -- magnitude sum (damage, quantity)
    PRIMARY KEY (game_day, domain, entity),
    FOREIGN KEY (game_day) REFERENCES daily_summary(game_day)
);
CREATE INDEX idx_dd_domain ON daily_detail(domain);
```

Example daily_detail rows for Day 14:
```
(14, "combat",    "wolf_grey",    8,  120.0)
(14, "combat",    "spider_acid",  3,   45.0)
(14, "combat",    "golem_stone",  2,  250.0)
(14, "gathering", "iron_ore",    12,   12.0)
(14, "gathering", "oak_log",      8,    8.0)
(14, "crafting",  "smithing",     2,    2.0)
```

### Tier 3: Monthly Summaries

Same structure as Tier 2 but summed over 30-day periods. Provides artificial data breaks
for long playthroughs. Updated incrementally at each day boundary (running accumulator for
current month). Old daily rows are NOT deleted — they stay for queryability.

```sql
CREATE TABLE monthly_summary (
    game_month              INTEGER PRIMARY KEY,
    day_start               INTEGER NOT NULL,
    day_end                 INTEGER NOT NULL,
    days_elapsed            INTEGER DEFAULT 0,

    -- Same domain columns as daily_summary (summed)
    combat_kills            INTEGER DEFAULT 0,
    combat_kills_t1         INTEGER DEFAULT 0,
    combat_kills_t2         INTEGER DEFAULT 0,
    combat_kills_t3         INTEGER DEFAULT 0,
    combat_kills_t4         INTEGER DEFAULT 0,
    combat_damage_dealt     REAL DEFAULT 0.0,
    combat_damage_taken     REAL DEFAULT 0.0,
    combat_highest_hit      REAL DEFAULT 0.0,    -- max across all days in month
    combat_deaths           INTEGER DEFAULT 0,
    combat_dodges           INTEGER DEFAULT 0,
    combat_blocks           INTEGER DEFAULT 0,
    combat_healing          REAL DEFAULT 0.0,
    combat_crits            INTEGER DEFAULT 0,
    combat_status_applied   INTEGER DEFAULT 0,

    gathering_collected     INTEGER DEFAULT 0,
    gathering_actions       INTEGER DEFAULT 0,
    gathering_nodes_depleted INTEGER DEFAULT 0,

    crafting_attempts       INTEGER DEFAULT 0,
    crafting_successes      INTEGER DEFAULT 0,

    exploration_chunks      INTEGER DEFAULT 0,
    exploration_distance    REAL DEFAULT 0.0,
    exploration_discoveries INTEGER DEFAULT 0,

    social_npc_interactions INTEGER DEFAULT 0,
    social_quests_completed INTEGER DEFAULT 0,

    economy_gold_earned     REAL DEFAULT 0.0,
    economy_gold_spent      REAL DEFAULT 0.0,

    progression_levels      INTEGER DEFAULT 0,
    progression_exp         REAL DEFAULT 0.0,

    -- Pre-computed monthly aggregates
    primary_activity        TEXT DEFAULT 'idle',
    peak_combat_day         INTEGER DEFAULT 0,   -- game_day with most kills
    peak_gathering_day      INTEGER DEFAULT 0,   -- game_day with most gathered
    combat_active_days      INTEGER DEFAULT 0,   -- days where combat_kills > 0
    gathering_active_days   INTEGER DEFAULT 0,
    crafting_active_days    INTEGER DEFAULT 0
);
```

Monthly detail (per-entity totals across the month):
```sql
CREATE TABLE monthly_detail (
    game_month  INTEGER NOT NULL,
    domain      TEXT NOT NULL,
    entity      TEXT NOT NULL,
    count       INTEGER DEFAULT 0,
    total       REAL DEFAULT 0.0,
    PRIMARY KEY (game_month, domain, entity),
    FOREIGN KEY (game_month) REFERENCES monthly_summary(game_month)
);
```

### Day Boundary Processing (pseudocode)

```python
def on_day_boundary(ended_day, game_time):
    # 1. Summarize Tier 1 → Tier 2
    events = query_all(current_day_events)
    summary = compute_daily_summary(events, ended_day)
    insert(daily_summary, summary)
    insert_many(daily_detail, compute_detail_breakdown(events, ended_day))
    delete_all(current_day_events)

    # 2. Update Tier 3 running accumulator for current month
    current_month = ended_day // 30
    update_monthly_accumulator(current_month, summary)

    # 3. At month boundary (ended_day % 30 == 29):
    if ended_day % 30 == 29:
        finalize_monthly_summary(current_month)
```

### Temporal Calculations (derived, never stored)

All calculations read from the three tiers + StatStore. None are pre-stored.

| Calculation | Formula | Source |
|------------|---------|--------|
| `today_count(type)` | COUNT from current_day_events WHERE event_type=X | Tier 1 |
| `all_time(stat)` | stat_store.get(name) | StatStore |
| `month_daily_avg(metric)` | monthly_summary.metric / days_elapsed | Tier 3 |
| `recency_ratio` | today_count / all_time | Tier 1 + StatStore |
| `vs_average` | today_count / month_daily_avg | Tier 1 + Tier 3 |
| `day_streak(domain)` | Count consecutive daily_summary rows where domain > 0 | Tier 2 |
| `primary_activity` | max(today domain counts) | Tier 1 |

### What Layer 2 Receives (data block for LLM)

For a wolf kill trigger on Day 14:
```
Stats (all-time, from StatStore):
  combat.kills.species.wolf = 47
  combat.kills = 150
  combat.kills.location.whispering_woods = 23

Today (from Tier 1):
  wolves_killed_today = 8
  total_combat_today = 12
  primary_activity = combat

This month (from Tier 3):
  avg_kills_per_day = 4.2  (58 kills / 14 days)
  combat_active_days = 12 of 14

Derived:
  today vs average = 1.9x
  recency = 17% of all-time wolf kills happened today
```

Pure numbers. No interpretation. The LLM interprets them via prompt fragments.

---

## Document History

- **2026-04-16**: Hierarchy-alignment migration. Notes that the
  dormant `realm_state` table was renamed to `region_state` when WMS
  `RegionLevel` was expanded from 5 shifted labels to 6 game-aligned
  values. Layer 5 events (now `RegionSummaryEvent`) target game
  Region rather than world-scope "realm". See
  `ARCHITECTURAL_DECISIONS.md` §6.
- **2026-04-09**: Initial creation.

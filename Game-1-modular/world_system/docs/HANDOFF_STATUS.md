# World Memory System — Handoff Status

**Date**: 2026-03-26
**Branch**: `claude/living-world-combat-phase-2-XBxdJ`
**Phase**: 2.1 (Memory Layer) — Layer 1 complete, Raw Event Pipeline infrastructure complete
**Tests**: 56 passing (0 failures)

---

## What Was Built

### Layer 1: SQL-Backed Stat Tracking (COMPLETE)

The entire stat tracking system has been migrated from Python dicts to a single flat SQL table with automatic dimensional breakdowns.

**Core files:**
- `world_system/world_memory/stat_store.py` (258 lines) — SQL engine
- `entities/components/stat_tracker.py` (1,100+ lines) — 65 `record_*` methods

**SQL Schema:**
```sql
CREATE TABLE stats (
    key TEXT PRIMARY KEY,    -- "combat.kills.species.wolf"
    count INTEGER DEFAULT 0, -- occurrences
    total REAL DEFAULT 0.0,  -- sum of values
    max_value REAL DEFAULT 0.0, -- best single instance
    updated_at REAL DEFAULT 0.0
);
```

**How it works:** Each game action writes multiple hierarchical keys via `build_dimensional_keys()`. One wolf kill creates: `combat.kills`, `combat.kills.species.wolf`, `combat.kills.tier.1`, `combat.kills.location.whispering_woods` — all automatically. New enemies, regions, weapons get stat rows without code changes.

**What's tracked (65 methods, ~400+ key patterns):**

| Category | Methods | What's Covered |
|----------|---------|----------------|
| Combat | 18 | Damage dealt/taken by type/element/target/location, kills by species/tier/rank, healing, blocking, reflecting, weapon attacks, death by source, status effects, dodges, combos, projectiles, killstreaks |
| Gathering | 8 | Resources by id/tier/category/element/location, tool swings, durability, node depletion, fishing |
| Crafting | 5 | Attempts/success by discipline/tier/recipe/rarity, quality, time, materials, inventions, enchantments |
| Items | 5 | Collected/used/dropped/equipped/repaired by item/category/rarity/slot |
| Skills | 1 | By skill_id/category, mana spent, targets |
| Exploration | 3 | Distance, chunk tracking, landmarks |
| Economy | 3 | Gold earned/spent by source, trades |
| Progression | 5 | Level, exp by source, titles, class changes, skills learned |
| Social | 4 | NPC interactions, quests accepted/completed/failed |
| Dungeons | 7 | Entry/completion by rarity, kills, deaths, waves, chests |
| Time | 4 | Activity time, menu time, idle time, sessions |
| Records | 4 | Personal bests, combat duration, fastest gather, rates |
| Encyclopedia | 2 | First discoveries, completion % |
| Misc | 4 | Menu opens, saves, loads, debug actions |
| Barriers | 2 | Placed/picked up by material |

**Save system:** Stats live in `world_memory.db` (SQLite). `to_dict()` still works for backward compat with old JSON saves. `from_dict()` imports v1.0 legacy saves into SQL automatically.

### Raw Event Pipeline: Event Recording Infrastructure (COMPLETE)

**Core files:**
- `world_system/world_memory/event_store.py` (~1,100 lines) — 20 SQL tables, full CRUD
- `world_system/world_memory/event_recorder.py` (~470 lines) — Bus→SQLite bridge
- `world_system/world_memory/event_schema.py` (240 lines) — WorldMemoryEvent, InterpretedEvent
- `world_system/world_memory/trigger_manager.py` (194 lines) — Threshold-based dual-track triggers

**What's working:**
- EventRecorder subscribes to GameEventBus, converts events, enriches with geographic context, writes to SQLite
- Auto-tagging: location, species, intensity, element, tier, discipline, quality
- Threshold triggers: fires at `1, 3, 5, 10, 25, 50, 100, 250, 500, 1000...` (NOT primes)
- Dual-track counting: individual streams + regional accumulators
- 20 SQL tables covering Raw Event Pipeline through Layer 7 (higher layers are empty schemas, ready for data)

**Bus events published (13 types):**
`DAMAGE_DEALT`, `ENEMY_KILLED`, `PLAYER_HIT`, `DODGE_PERFORMED`, `RESOURCE_GATHERED`, `ITEM_CRAFTED`, `LEVEL_UP`, `SKILL_ACTIVATED`, `EQUIPMENT_CHANGED`, `PLAYER_DIED`, `STATUS_APPLIED`, `NPC_INTERACTION`, `QUEST_ACCEPTED`, `QUEST_COMPLETED`

### Supporting Infrastructure (COMPLETE)

| Component | File | Status |
|-----------|------|--------|
| Geographic Registry | `geographic_registry.py` (344 lines) | Working — region hierarchy, position lookup, chunk cache |
| Entity Registry | `entity_registry.py` (340 lines) | Working — entities, tag index, tag matching |
| World Query | `query.py` (365 lines) | Working — entity-first queries, dual-window system |
| Time Envelope | `time_envelope.py` (120 lines) | Working — trend detection (5 types), severity modifiers |
| Daily Ledger | `daily_ledger.py` (277 lines) | Working — daily aggregation, meta-stats, wired into game loop |
| Retention | `retention.py` (100 lines) | Working — 6 preservation rules, threshold-based |
| Position Sampler | `position_sampler.py` (49 lines) | Working — periodic breadcrumbs |
| Facade | `world_memory_system.py` (~400 lines) | Working — coordinates all subsystems |
| Tag Relevance | `tag_relevance.py` (69 lines) | Working — entity-event relevance scoring |
| Config Loader | `config_loader.py` (80 lines) | Working — JSON config loading |

### Consumer Systems (PRE-EXISTING, EXTERNAL TO WMS)

> These are **consumer systems** that live in `living_world/` for organizational convenience.
> They are NOT part of the World Memory System — they READ WMS data to make outgoing decisions.
> NPC dialogue generation, faction reputation decisions, and ecosystem lifecycle management
> are consumer-side concerns, not WMS concerns.

| Consumer | File | Relationship to WMS |
|----------|------|---------------------|
| Backend Manager | `living_world/backends/backend_manager.py` (553 lines) | LLM infrastructure — no WMS dependency |
| NPC Agent | `living_world/npc/npc_agent.py` (481 lines) | Dialogue generation READS NPCMemory and WorldQuery |
| NPC Memory | `living_world/npc/npc_memory.py` (184 lines) | WMS-owned data — gossip propagation writes here |
| Faction System | `living_world/factions/faction_system.py` (463 lines) | READS events, WRITES reputation state |
| Ecosystem Agent | `living_world/ecosystem/ecosystem_agent.py` (398 lines) | READS gathering events, WRITES resource state |

### Tests

| Test File | Tests | Status |
|-----------|-------|--------|
| `test_stat_store.py` | 19 | All pass — StatStore core + StatTracker dimensional breakdowns |
| `test_foundation_pipeline.py` | 27 | All pass — SQL schema, triggers, time envelopes, daily ledgers, full pipeline |
| `test_memory_system.py` | 10 | All pass — Event store, geographic registry, entity registry, interpreter, full pipeline |

**Run:** `cd Game-1-modular && python world_system/world_memory/test_stat_store.py && python world_system/world_memory/test_foundation_pipeline.py && python world_system/world_memory/test_memory_system.py`

---

## What's NOT Built Yet

### Layer 2 Evaluators: IMPLEMENTED (33 evaluators, all passing)

28 new granular evaluators + 5 legacy evaluators. Each evaluator has a specific
**input frame of reference** — defined by what data it queries and how it processes it.
Same event can trigger multiple evaluators through different frames (e.g., a wolf kill
triggers both `combat_kills_regional_low_tier` and `combat_kills_global`).

Output is **minimal narration** — data to text, not editorializing:
- GOOD: "Player has killed 10 wolves in Whispering Woods."
- BAD: "The wolf population is declining in Whispering Woods."

Scope comes from the DATA, not from the evaluator. If the event has locality_id,
the narration is regional. If not, it's global.

| Category | Count | Evaluators |
|----------|-------|------------|
| Combat | 6 | kills_regional_low_tier, kills_regional_high_tier, kills_global, boss_kills, damage_regional, combat_style |
| Gathering | 4 | regional, depletion, global, tools |
| Crafting | 7 | smithing, alchemy, refining, engineering, enchanting, minigame, inventions |
| Progression | 4 | levels, skills, identity, equipment |
| Exploration | 2 | territory, dungeons |
| Social | 2 | npc, quests |
| Economy/Items | 3 | economy_flow, items_equipment, items_inventory |
| Legacy | 5 | population, resources, area_danger, crafting_trends, player_milestones |

### Next Priority: Retrieval System

The retrieval system needs to:
1. Catalog what evaluators exist and what they produce
2. Auto-match stats/events to the right evaluator
3. Work across layers (Raw Event Pipeline → Layer 2 → Layer 3+)
4. Let consumers find relevant interpretations by querying the catalog

**Retrieval pathways** (Design doc §10):
- **Fast Path**: Layer 1 stat lookups (microsecond) — `stat_store.get()` — DONE
- **Narrative Path**: Layer 2 interpretations (millisecond) — evaluators now producing data
- **Detail Path**: Raw Event Pipeline raw events (millisecond) — `event_store.query()` — DONE

> **NOTE**: Wiring WorldQuery into NPC dialogue is a **consumer integration task**, not a WMS task.

### Known Issues / Touch-ups Needed

- `gathering_depletion`: Needs total node count per chunk from Layer 1 to calculate percentages (currently just counts depletion events)
- Legacy evaluators (population, area_danger, etc.) still use editorializing narration — should be updated to minimal data-to-text style
- Config for new evaluators uses hardcoded defaults — should be added to memory-config.json

### Layers 3-7: Higher Aggregation (SCHEMA ONLY, NOT IMPLEMENTED)

SQL tables exist for municipality consolidation, province summaries, realm state, intercountry state, world narrative, and narrative threads. No code writes to them yet.

### Known Coverage Gaps in Layer 1 (~15%)

These stats exist in design but can't be tracked yet because the game systems don't expose the data:

- Distance by biome (forest/mountain) — biome info not available at `record_movement` call site
- Furthest from spawn — needs spawn position reference
- Items bought vs sold separately — economy system needs instrumentation
- Current gold balance — needs inventory gold integration
- Mana regenerated — no mana regen hook
- Skills on cooldown missed — no hook
- Crafting sub-types (traps_created, alloys_created) — need discipline-specific hooks
- Some dungeon stats (fastest clear by ID, specific dungeon tracking)

---

## Documentation Map

| Document | Location | Purpose |
|----------|----------|---------|
| **WORLD_MEMORY_SYSTEM.md** | `world_system/docs/` | **Single source of truth** — 1,821 lines covering all 16 design sections |
| **FOUNDATION_IMPLEMENTATION_PLAN.md** | `world_system/docs/` | Implementation plan for Layer 1-2 (1,263 lines) — mostly executed |
| **HANDOFF_STATUS.md** | `world_system/docs/` | This file — current state for handoff |
| **README.md** | `world_system/docs/` | Points to WORLD_MEMORY_SYSTEM.md |
| **Archive** | `world_system/docs/archive/` | 7 superseded design docs (historical reference) |
| **Development-Plan pointer** | `Development-Plan/WORLD_MEMORY_POINTER.md` | Redirects to canonical location |

---

## Architecture Quick Reference

```
GameEngine.__init__()
└── WorldMemorySystem.initialize()
    ├── EventStore (SQLite — 20 tables)
    ├── StatStore (shares SQLite connection — 1 table, hierarchical keys)
    ├── GeographicRegistry (region hierarchy from JSON/procedural)
    ├── EntityRegistry (NPCs, regions, player)
    ├── TriggerManager (threshold sequence, dual-track counting)
    ├── EventRecorder (bus subscriber → SQLite + triggers)
    ├── WorldInterpreter (5 evaluators, receives TriggerActions)
    ├── WorldQuery (entity-first queries, dual-window)
    ├── EventRetentionManager (6 preservation rules)
    ├── PositionSampler (periodic breadcrumbs)
    └── DailyLedgerManager (game-day boundary computation)

Character.stat_tracker
└── StatTracker (65 record_* methods)
    └── StatStore (SQL UPSERT with dimensional breakdowns)

Game Loop:
├── bus.publish("EVENT_TYPE", data)
│   ├── EventRecorder → SQLite events + trigger check
│   └── StatTracker.record_*() → SQLite stats
└── WorldMemorySystem.update(dt, game_time)
    ├── Daily ledger computation at day boundaries
    ├── Retention pruning
    └── StatStore flush
```

---

## Key Design Decisions Made

1. **Threshold sequence replaces primes** — Triggers at `1, 3, 5, 10, 25, 50, 100...` instead of prime numbers. More meaningful spacing, sparser at high counts.

2. **Single flat stats table** — One `stats` table with hierarchical text keys instead of 14 separate dict structures. Scales automatically — new enemies/regions/weapons create rows without code changes.

3. **Burst before accelerating** — In trend detection, burst (>30% of all-time in one day) is checked before accelerating (>2x daily average) because any burst is also accelerating.

4. **StatStore shares EventStore's connection** — One SQLite database per save, stats table sits alongside event tables. No separate database to manage.

5. **Legacy properties preserved** — `stat_tracker.combat_damage`, `.gathering_totals`, etc. are computed properties that read from SQL. Old rendering code and save system work without changes.

---

## How to Continue

1. **Read** `world_system/docs/WORLD_MEMORY_SYSTEM.md` — the single source of truth
2. **Run tests** to verify everything works: `python world_system/world_memory/test_stat_store.py && python world_system/world_memory/test_foundation_pipeline.py && python world_system/world_memory/test_memory_system.py`
3. **Next task**: Build retrieval system (catalog evaluators, auto-match stats, serve consumers)
4. **After that**: Layer 3 cross-domain patterns, Layers 4-7 summaries
5. **Polish**: Update legacy evaluator narration to minimal data-to-text style
6. **Separately (consumer work, not WMS)**: Wire WorldQuery into NPC dialogue

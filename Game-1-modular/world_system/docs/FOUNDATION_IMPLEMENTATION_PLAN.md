# World Memory System — Foundation Implementation Plan

**Target**: Layer 2 infrastructure + plumbing for Layers 3-7. No interpreters/evaluators yet.
**Approach**: Fix what's misaligned, add what's missing, test with mocks.
**Design Authority**: `world_system/docs/WORLD_MEMORY_SYSTEM.md` (1,821 lines)
**Date**: 2026-03-25

---

## 1. Current State Assessment

### What Exists and Is Correct

| File | Lines | Status | Notes |
|------|-------|--------|-------|
| `event_schema.py` | 240 | ✅ Good | EventType (28 values), WorldMemoryEvent, InterpretedEvent, BUS_TO_MEMORY_TYPE, SKIP_BUS_EVENTS, SEVERITY_ORDER — all match design doc |
| `event_store.py` | 917 | ⚠️ Partial | Has 7 SQL tables + good CRUD. Missing ~10 tables. See §2 |
| `geographic_registry.py` | 344 | ✅ Good | Region, RegionLevel, GeographicRegistry singleton, chunk cache |
| `entity_registry.py` | 340 | ✅ Good | WorldEntity, EntityType, EntityRegistry singleton, tag index |
| `query.py` | 365 | ✅ Good | WorldQuery, EventWindow, EntityQueryResult, dual-window system |
| `tag_relevance.py` | 69 | ✅ Good | calculate_relevance() — basic but functional |
| `world_memory_system.py` | 384 | ✅ Good | Facade coordinating all subsystems |
| `config_loader.py` | 80 | ✅ Good | JSON config loading |
| `test_memory_system.py` | 648 | ✅ Good | Existing tests — will extend |
| `retention.py` | 94 | ⚠️ Thin | Only 94 lines, needs alignment with design doc's 6 retention rules |
| `position_sampler.py` | 49 | ⚠️ Thin | Minimal — verify matches design |

### What Exists but Is WRONG

| File | Issue | Design Doc Says |
|------|-------|----------------|
| `event_recorder.py` (447 lines) | Uses **prime-number triggers** (lines 22-55). `_generate_primes()`, `is_prime_trigger()`. Fires at 2, 3, 5, 7, 11, 13... | Use **threshold sequence**: `1, 3, 5, 10, 25, 50, 100, 250, 500, 1000, 2500, 5000, 10000`. **Dual-track counting** (stream + regional). Separate `TriggerManager` class. |
| `event_recorder.py` | No regional accumulator counting | Design doc §2.2: Track 2 counts per `(locality_id, event_category)` using same thresholds |
| `event_recorder.py` | No `EVENT_CATEGORY_MAP` | Design doc §2.2: 8 categories (combat, gathering, crafting, exploration, social, progression, economy, other) |
| `event_store.py` schema | Comment says "prime trigger tracking" on `occurrence_counts` | Should be threshold-based. Table structure is fine — just the comment and usage pattern need changing |
| `event_recorder.py` auto-tagging | Missing location tags from geographic enrichment, missing intensity tags, missing `species:` tags from enemy_type | Design doc §9.2: Location tags, intensity derived from tier baselines, species from enemy data |

### What Is MISSING

| Component | Design Doc Section | Priority |
|-----------|-------------------|----------|
| `trigger_manager.py` | §2 (Trigger & Escalation) | **P0** — blocks everything |
| `time_envelope.py` | §8.4 (Time Envelopes) | **P1** — needed by evaluators |
| `daily_ledger.py` | §8.1-8.2 (Daily Ledger, MetaDailyStats) | **P1** — needed by evaluators |
| SQL: `regional_counters` | §11 (Storage Schema) | **P0** — dual-track trigger counting |
| SQL: `interpretation_counters` | §11 | P2 — Layer 3→4 escalation |
| SQL: `daily_ledgers` | §11 | P1 — daily aggregation |
| SQL: `meta_daily_stats` | §11 | P2 — streak tracking |
| SQL: `connected_interpretations` + tags | §11.3 (Layer 4) | P2 — schema only for now |
| SQL: `province_summaries` | §11.4 (Layer 5) | P2 — schema only |
| SQL: `realm_state` | §11.5 (Layer 6) | P3 — schema only |
| SQL: `world_narrative` + `narrative_threads` | §11.6 (Layer 7) | P3 — schema only |
| `EVENT_CATEGORY_MAP` constant | §2.2 | P0 — needed by TriggerManager |
| `TriggerAction` dataclass | §2.6 | P0 — trigger output type |
| Intensity auto-tags | §9.2 | P1 — tag enrichment |
| Location auto-tags | §9.2 | P1 — tag enrichment |

---

## 2. SQL Schema Gap Analysis

### Current Tables (7 — in `event_store.py` `_SCHEMA_SQL`)

```
✅ events                    — Layer 2 raw events (correct, 9 indexes)
✅ event_tags                — Layer 2 tag N:M (correct)
✅ occurrence_counts         — Per-(actor, type, subtype) counters (correct structure, wrong usage)
✅ entity_state              — Entity activity logs (correct)
✅ region_state              — Region aggregation (correct)
✅ npc_memory                — NPC persistent state (correct, slightly different columns than design doc)
✅ faction_state             — Faction reputation (correct)
✅ faction_reputation_history — Rep change log (BONUS — not in design doc, keep it)
✅ biome_resource_state      — Ecosystem tracking (correct)
✅ event_triggers            — Pacing state (BONUS — placeholder, keep it)
✅ pacing_state              — Pacing state (BONUS — placeholder, keep it)
```

### Tables to ADD (10 new tables)

**P0 — Needed for dual-track triggers:**
```sql
-- Regional accumulator for Track 2 counting
CREATE TABLE IF NOT EXISTS regional_counters (
    region_id TEXT NOT NULL,
    event_category TEXT NOT NULL,
    count INTEGER DEFAULT 0,
    PRIMARY KEY (region_id, event_category)
);
```

**P1 — Needed for time tracking:**
```sql
-- Daily aggregation (one row per game-day, never pruned)
CREATE TABLE IF NOT EXISTS daily_ledgers (
    game_day INTEGER PRIMARY KEY,
    game_time_start REAL,
    game_time_end REAL,
    data_json TEXT NOT NULL DEFAULT '{}'
);
```

**P2 — Layer 3→4 escalation counting:**
```sql
-- Interpretation similarity counting for Layer 3→4 triggers
CREATE TABLE IF NOT EXISTS interpretation_counters (
    category TEXT NOT NULL,
    primary_tag TEXT NOT NULL,
    region_id TEXT NOT NULL,
    count INTEGER DEFAULT 0,
    PRIMARY KEY (category, primary_tag, region_id)
);

-- Meta-daily stats (streaks, records, rolling averages)
CREATE TABLE IF NOT EXISTS meta_daily_stats (
    stat_key TEXT PRIMARY KEY,
    data_json TEXT NOT NULL DEFAULT '{}'
);
```

**P2 — Layer 4 schema (empty, ready for evaluators):**
```sql
CREATE TABLE IF NOT EXISTS connected_interpretations (
    id TEXT PRIMARY KEY,
    created_at REAL NOT NULL,
    narrative TEXT NOT NULL,
    category TEXT NOT NULL,
    severity TEXT NOT NULL,
    source_interpretation_ids_json TEXT DEFAULT '[]',
    affected_district_ids_json TEXT DEFAULT '[]',
    affects_tags_json TEXT DEFAULT '[]',
    is_ongoing INTEGER DEFAULT 0,
    expires_at REAL,
    archived INTEGER DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_connected_interp_category ON connected_interpretations(category);
CREATE INDEX IF NOT EXISTS idx_connected_interp_created ON connected_interpretations(created_at);

CREATE TABLE IF NOT EXISTS connected_interpretation_tags (
    id TEXT NOT NULL,
    tag TEXT NOT NULL,
    FOREIGN KEY (id) REFERENCES connected_interpretations(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_connected_interp_tags_tag ON connected_interpretation_tags(tag);
```

**P2 — Layer 5 schema (empty, ready):**
```sql
CREATE TABLE IF NOT EXISTS province_summaries (
    province_id TEXT PRIMARY KEY,
    summary_text TEXT DEFAULT '',
    dominant_activities_json TEXT DEFAULT '[]',
    notable_event_ids_json TEXT DEFAULT '[]',
    resource_state_json TEXT DEFAULT '{}',
    threat_level TEXT DEFAULT 'low',
    last_updated REAL DEFAULT 0.0
);
```

**P3 — Layers 6-7 schema (empty, ready):**
```sql
CREATE TABLE IF NOT EXISTS realm_state (
    realm_id TEXT PRIMARY KEY,
    faction_standings_json TEXT DEFAULT '{}',
    economic_summary TEXT DEFAULT '',
    player_reputation TEXT DEFAULT '',
    major_events_json TEXT DEFAULT '[]',
    last_updated REAL DEFAULT 0.0
);

CREATE TABLE IF NOT EXISTS world_narrative (
    id TEXT PRIMARY KEY DEFAULT 'singleton',
    world_themes_json TEXT DEFAULT '[]',
    world_epoch TEXT DEFAULT 'unknown',
    active_thread_ids_json TEXT DEFAULT '[]',
    resolved_thread_ids_json TEXT DEFAULT '[]',
    world_history_json TEXT DEFAULT '[]',
    last_updated REAL DEFAULT 0.0
);

CREATE TABLE IF NOT EXISTS narrative_threads (
    thread_id TEXT PRIMARY KEY,
    source TEXT NOT NULL,
    theme TEXT NOT NULL,
    summary TEXT NOT NULL,
    canonical_facts_json TEXT DEFAULT '[]',
    unresolved_questions_json TEXT DEFAULT '[]',
    status TEXT DEFAULT 'rumor',
    significance REAL DEFAULT 0.0,
    origin_region TEXT,
    spread_radius REAL DEFAULT 0.0,
    created_at REAL NOT NULL,
    last_referenced REAL,
    generation_hints_json TEXT DEFAULT '{}'
);
CREATE INDEX IF NOT EXISTS idx_narrative_threads_status ON narrative_threads(status);
CREATE INDEX IF NOT EXISTS idx_narrative_threads_significance ON narrative_threads(significance);
```

### Implementation Strategy for SQL Changes

**Do NOT create a migration system.** The database is per-save-file and uses `CREATE TABLE IF NOT EXISTS`. Simply append the new DDL to the existing `_SCHEMA_SQL` string in `event_store.py`. Existing databases get the new tables on next open. Existing tables are untouched (IF NOT EXISTS).

### SQL Integrity Concerns

1. **WAL mode** — already enabled (`PRAGMA journal_mode=WAL`). Good.
2. **Foreign keys** — already enabled (`PRAGMA foreign_keys=ON`). Good.
3. **Auto-commit** — each `record()` call commits. For high-frequency events (position samples every 10s), this is fine. If we ever batch, we'd wrap in a transaction.
4. **Index coverage** — verify all query patterns have supporting indexes:
   - `regional_counters` lookups by `(region_id, event_category)` → PK covers this
   - `interpretation_counters` by `(category, primary_tag, region_id)` → PK covers this
   - `daily_ledgers` by `game_day` → PK covers this
   - Connected interpretations need category + created_at indexes → added above

---

## 3. Trigger System Redesign

### The Problem

`event_recorder.py` lines 22-55 implement a prime-number trigger system:
```python
_PRIMES = _generate_primes(10000)
def is_prime_trigger(count): ...  # Fires at 2, 3, 5, 7, 11, 13, 17, 19, 23...
```

Design doc §2 specifies a fundamentally different system:
- **Threshold sequence**: `1, 3, 5, 10, 25, 50, 100, 250, 500, 1000, 2500, 5000, 10000`
- **Dual-track counting**: individual streams AND regional accumulators
- **Separate TriggerManager class**

Primes fire **too frequently** at low counts (every number 2-23 is either prime or adjacent to one) and **too rarely** at high counts (gaps grow to hundreds). Thresholds are designed for "heavy early coverage, natural thinning" with explicit control.

### The Solution

#### Step 1: Create `trigger_manager.py` (NEW file, ~180 lines)

```python
"""Dual-track threshold trigger system.

Track 1: Individual event streams — (actor, type, subtype, locality) → count
Track 2: Regional accumulators — (locality_id, event_category) → count

Both use the same threshold sequence. A trigger is an OPPORTUNITY to evaluate,
not a mandate to produce output.
"""

THRESHOLDS = [1, 3, 5, 10, 25, 50, 100, 250, 500, 1000, 2500, 5000, 10000, 25000, 100000]
THRESHOLD_SET = frozenset(THRESHOLDS)

EVENT_CATEGORY_MAP = {
    # Combat
    "attack_performed": "combat",
    "damage_taken": "combat",
    "enemy_killed": "combat",
    "player_death": "combat",
    "dodge_performed": "combat",
    "status_applied": "combat",
    # Gathering
    "resource_gathered": "gathering",
    "node_depleted": "gathering",
    # Crafting
    "craft_attempted": "crafting",
    "item_invented": "crafting",
    "recipe_discovered": "crafting",
    # Economy
    "item_acquired": "economy",
    "item_consumed": "economy",
    "item_equipped": "economy",
    "repair_performed": "economy",
    "trade_completed": "economy",
    # Progression
    "level_up": "progression",
    "skill_learned": "progression",
    "skill_used": "progression",
    "title_earned": "progression",
    "class_changed": "progression",
    # Exploration
    "chunk_entered": "exploration",
    "area_discovered": "exploration",
    # Social
    "npc_interaction": "social",
    "quest_accepted": "social",
    "quest_completed": "social",
    "quest_failed": "social",
    # System
    "world_event": "other",
    "position_sample": "other",
}

@dataclass
class TriggerAction:
    action_type: str        # "interpret_stream" or "interpret_region"
    key: Tuple              # The counting key that triggered
    count: int              # The threshold count that was hit
    event: WorldMemoryEvent # The event that caused the trigger

class TriggerManager:
    """Dual-track threshold counting. Singleton."""
    _instance = None

    def __init__(self):
        self._stream_counts: Dict[Tuple, int] = {}     # (actor, type, subtype, locality)
        self._regional_counts: Dict[Tuple, int] = {}    # (locality_id, category)

    def on_event(self, event: WorldMemoryEvent) -> List[TriggerAction]:
        actions = []

        # Track 1: Individual stream
        stream_key = (event.actor_id, event.event_type, event.event_subtype,
                      event.locality_id or "unknown")
        self._stream_counts[stream_key] = self._stream_counts.get(stream_key, 0) + 1
        count = self._stream_counts[stream_key]
        if count in THRESHOLD_SET:
            actions.append(TriggerAction("interpret_stream", stream_key, count, event))

        # Track 2: Regional accumulator
        category = EVENT_CATEGORY_MAP.get(event.event_type, "other")
        if event.locality_id and category != "other":
            region_key = (event.locality_id, category)
            self._regional_counts[region_key] = self._regional_counts.get(region_key, 0) + 1
            rcount = self._regional_counts[region_key]
            if rcount in THRESHOLD_SET:
                actions.append(TriggerAction("interpret_region", region_key, rcount, event))

        return actions

    # Save/load for persistence across sessions
    def get_state(self) -> Dict: ...
    def load_state(self, state: Dict): ...
```

#### Step 2: Update `event_recorder.py`

**Remove**: `_generate_primes()`, `_PRIMES`, `is_prime_trigger()` (lines 22-55)
**Add**: `from world_system.world_memory.trigger_manager import TriggerManager`
**Change**: `initialize()` accepts `trigger_manager` parameter
**Change**: `_on_bus_event()` and `record_direct()` call `trigger_manager.on_event()` instead of `is_prime_trigger()`

Specifically in `_on_bus_event()` (line 162-183), replace:
```python
# OLD
count = self.event_store.increment_occurrence(...)
memory_event.interpretation_count = count
memory_event.triggered_interpretation = is_prime_trigger(count)
...
if memory_event.triggered_interpretation and self._interpreter_callback:
    self._interpreter_callback(memory_event)
```

With:
```python
# NEW
count = self.event_store.increment_occurrence(...)
memory_event.interpretation_count = count
# Check threshold triggers (dual-track)
actions = self.trigger_manager.on_event(memory_event)
memory_event.triggered_interpretation = len(actions) > 0
...
for action in actions:
    if self._interpreter_callback:
        self._interpreter_callback(action)
```

#### Step 3: Persist trigger counts

TriggerManager's in-memory dicts need persistence across save/load. Two options:

**Option A**: Use the `regional_counters` SQL table for Track 2. Reconstruct Track 1 from `occurrence_counts` table on load.
**Option B**: Serialize both dicts to JSON in `pacing_state` table (already exists, currently empty).

**Recommendation**: Option A. `occurrence_counts` already has per-(actor, type, subtype) counts — that's Track 1 minus locality. We can either:
- Add a `locality_id` column to `occurrence_counts` (breaking change) — **NO, avoid this**
- Keep TriggerManager's `_stream_counts` as the authoritative in-memory source, rebuilt from `occurrence_counts` + locality on load — **YES, this works**
- For Track 2, use `regional_counters` table directly

Actually, simplest: TriggerManager keeps both tracks in-memory and serializes to `pacing_state` on save. On load, deserialize. No schema changes to `occurrence_counts` needed.

#### Step 4: Update `world_memory_system.py` facade

Add TriggerManager to initialization sequence. Pass it to EventRecorder.

### Behavioral Difference: Primes vs Thresholds

| Count | Prime fires? | Threshold fires? | Note |
|-------|:-----------:|:----------------:|------|
| 1 | ✅ | ✅ | Both fire on first occurrence |
| 2 | ✅ | ❌ | Prime fires, threshold waits |
| 3 | ✅ | ✅ | Both fire |
| 4 | ❌ | ❌ | Neither |
| 5 | ✅ | ✅ | Both fire |
| 7 | ✅ | ❌ | Prime fires, threshold waits until 10 |
| 10 | ❌ | ✅ | Threshold fires, not prime |
| 11 | ✅ | ❌ | Prime fires, threshold waits until 25 |
| 25 | ❌ | ✅ | Threshold fires, not prime |
| 50 | ❌ | ✅ | Threshold fires |
| 97 | ✅ | ❌ | Prime fires, threshold fires at 100 |
| 100 | ❌ | ✅ | Threshold fires |

At count=100: Primes have fired ~25 times. Thresholds have fired 7 times. Thresholds are deliberately sparser — each trigger is more meaningful.

---

## 4. Auto-Tagging Alignment

### Current State (`event_recorder.py` lines 281-325)

The existing `_build_event_tags()` method handles:
- ✅ `event:{type}` — always added
- ✅ `resource:{id}` — from resource_type, material_id, resource_id
- ✅ `element:{type}` — from damage_type
- ✅ `combat:{weapon}` — from weapon_type
- ✅ `combat:critical` — from is_crit
- ✅ `combat:boss` — from is_boss
- ✅ `tier:{n}` — from tier
- ✅ `biome:{type}` — from biome
- ✅ `domain:{discipline}` — from discipline
- ✅ `quality:{level}` — from quality
- ✅ `game:{tag}` — passthrough from game tag system

### Missing (Design Doc §9.2)

| Tag | Source | Design Doc Reference |
|-----|--------|---------------------|
| `species:{enemy}` | `enemy_type` or `enemy_id` (strip instance suffix) | §9.2 FIELD_TAG_MAP: `"enemy_type": "species:"` |
| `npc:{id}` | `npc_id` field in event data | §9.2 FIELD_TAG_MAP: `"npc_id": "npc:"` |
| `quest:{id}` | `quest_id` field in event data | §9.2 FIELD_TAG_MAP: `"quest_id": "quest:"` |
| `location:{locality}` | From geographic enrichment (post-enrich) | §9.2: "if event.locality_id: tags.append(f'location:{event.locality_id}')" |
| `location:{district}` | From geographic enrichment (post-enrich) | §9.2: "if event.district_id: tags.append(f'location:{event.district_id}')" |
| `intensity:{level}` | Derived from magnitude vs tier baseline | §9.2: tier_baseline = {1: 10, 2: 25, 3: 60, 4: 150} |

### Implementation

The current `_build_event_tags()` runs BEFORE `_enrich_geographic()` — it's called during `_convert_event()` (line 205). Location tags can't be added there because locality_id isn't stamped yet.

**Fix**: Split tagging into two phases:
1. **Phase 1** (in `_convert_event`): Data-driven tags from bus event data (keep existing)
2. **Phase 2** (after `_enrich_geographic`): Location tags + intensity tags

```python
def _on_bus_event(self, event):
    ...
    memory_event = self._convert_event(event, mem_type)  # Phase 1 tags built here
    self._enrich_geographic(memory_event)                 # Stamps locality/district
    self._add_derived_tags(memory_event)                  # NEW: Phase 2 tags
    ...

def _add_derived_tags(self, event: WorldMemoryEvent) -> None:
    """Add tags that depend on geographic enrichment and computed values."""
    # Location tags
    if event.locality_id:
        event.tags.append(f"location:{event.locality_id}")
    if event.district_id:
        event.tags.append(f"location:{event.district_id}")

    # Species tags (extract from enemy-related context)
    enemy_type = event.context.get("enemy_type") or event.context.get("enemy_id")
    if enemy_type:
        base = str(enemy_type).rstrip("0123456789").rstrip("_")
        if base:
            event.tags.append(f"species:{base}")

    # NPC tags
    npc_id = event.context.get("npc_id")
    if npc_id:
        event.tags.append(f"npc:{npc_id}")

    # Quest tags
    quest_id = event.context.get("quest_id")
    if quest_id:
        event.tags.append(f"quest:{quest_id}")

    # Intensity tags (magnitude relative to tier baseline)
    if event.magnitude > 0:
        tier_baseline = {1: 10, 2: 25, 3: 60, 4: 150}
        baseline = tier_baseline.get(event.tier or 1, 10)
        ratio = event.magnitude / baseline
        if ratio > 3.0:
            event.tags.append("intensity:extreme")
        elif ratio > 1.5:
            event.tags.append("intensity:heavy")
        elif ratio > 0.5:
            event.tags.append("intensity:moderate")
        else:
            event.tags.append("intensity:light")
```

### Verification

Test that a wolf kill event produces:
```python
["event:enemy_killed", "species:wolf", "combat:melee", "element:physical",
 "biome:forest", "tier:1", "location:whispering_woods", "location:eastern_highlands",
 "intensity:moderate"]
```

---

## 5. Time Tracking (NEW modules)

### 5.1 `time_envelope.py` (~120 lines)

**Purpose**: Compact temporal descriptor for evaluators. Answers "is this accelerating or dormant?" without scanning all timestamps.

```python
@dataclass
class TimeEnvelope:
    first_at: float          # Game-time of first event
    last_at: float           # Game-time of last event
    total_count: int
    total_span: float        # last_at - first_at
    last_1_day: int          # Events in last 1 game-day
    last_3_days: int         # Events in last 3 game-days
    last_7_days: int         # Events in last 7 game-days
    recent_rate: float       # Events per game-time-unit (last 7 days)
    overall_rate: float      # Events per game-time-unit (all time)
    trend: str               # "accelerating", "steady", "decelerating", "burst", "dormant"

TREND_SEVERITY_MODIFIER = {
    "burst": 2.0,
    "accelerating": 1.5,
    "steady": 1.0,
    "decelerating": 0.8,
    "dormant": 0.5,
}

def compute_envelope(events: List[WorldMemoryEvent],
                     current_game_time: float,
                     game_day_length: float = 1.0) -> TimeEnvelope:
    """Compute a TimeEnvelope from a list of events.

    Args:
        events: Events sorted by game_time (oldest first).
        current_game_time: Current game time for recency calculations.
        game_day_length: How many game-time units = 1 game-day.
    """
    if not events:
        return TimeEnvelope(0, 0, 0, 0, 0, 0, 0, 0.0, 0.0, "dormant")

    times = [e.game_time for e in events]
    first, last = times[0], times[-1]
    total_span = last - first
    total_count = len(events)

    # Bucketed counts
    cutoff_1 = current_game_time - game_day_length
    cutoff_3 = current_game_time - 3 * game_day_length
    cutoff_7 = current_game_time - 7 * game_day_length
    last_1 = sum(1 for t in times if t >= cutoff_1)
    last_3 = sum(1 for t in times if t >= cutoff_3)
    last_7 = sum(1 for t in times if t >= cutoff_7)

    # Rates
    recent_span = min(7 * game_day_length, current_game_time - first) or 1.0
    recent_rate = last_7 / recent_span
    overall_rate = total_count / max(total_span, 1.0)

    # Trend detection (Design doc §8.4)
    trend = _detect_trend(last_1, last_7, total_count, game_day_length)

    return TimeEnvelope(first, last, total_count, total_span,
                       last_1, last_3, last_7, recent_rate, overall_rate, trend)

def _detect_trend(last_1_day, last_7_days, total_count, day_len) -> str:
    if last_7_days == 0:
        return "dormant"
    daily_avg_7d = last_7_days / 7.0
    if last_1_day > daily_avg_7d * 2:
        return "accelerating"
    if last_1_day < daily_avg_7d * 0.3:
        return "decelerating"
    if total_count > 0 and last_1_day > total_count * 0.3:
        return "burst"
    return "steady"
```

**Key design decision**: `game_day_length` is configurable. The game tracks time as a float — we need to know how many time units = 1 "day" for bucketing. Default to 1.0, configurable in `memory-config.json`.

### 5.2 `daily_ledger.py` (~200 lines)

**Purpose**: End-of-day aggregation. One row per game-day summarizing all activity.

```python
@dataclass
class DailyLedger:
    game_day: int
    game_time_start: float
    game_time_end: float
    # Combat
    damage_dealt: float = 0.0
    damage_taken: float = 0.0
    enemies_killed: int = 0
    deaths: int = 0
    highest_single_hit: float = 0.0
    unique_enemy_types_fought: int = 0
    # Gathering
    resources_gathered: int = 0
    unique_resources_gathered: int = 0
    nodes_depleted: int = 0
    # Crafting
    items_crafted: int = 0
    craft_quality_avg: float = 0.0
    unique_disciplines_used: int = 0
    # Exploration
    chunks_visited: int = 0
    new_chunks_discovered: int = 0
    distance_traveled: float = 0.0
    # Social
    npc_interactions: int = 0
    quests_completed: int = 0
    trades_completed: int = 0
    # Meta
    primary_activity: str = "idle"

    def to_json(self) -> str: ...
    @classmethod
    def from_json(cls, game_day: int, json_str: str) -> DailyLedger: ...

@dataclass
class MetaDailyStats:
    consecutive_combat_days: int = 0
    consecutive_peaceful_days: int = 0
    consecutive_crafting_days: int = 0
    consecutive_gathering_days: int = 0
    longest_combat_streak: int = 0
    longest_peaceful_streak: int = 0
    days_with_heavy_combat: int = 0
    days_with_no_combat: int = 0
    most_kills_in_a_day: int = 0
    most_damage_in_a_day: float = 0.0
    most_resources_in_a_day: int = 0
    avg_kills_per_day_7d: float = 0.0
    avg_damage_per_day_7d: float = 0.0

    def to_json(self) -> str: ...
    @classmethod
    def from_json(cls, json_str: str) -> MetaDailyStats: ...

class DailyLedgerManager:
    """Computes and stores daily ledgers. Called at game-day boundaries."""

    def compute_ledger(self, game_day: int, events: List[WorldMemoryEvent]) -> DailyLedger:
        """Aggregate a day's events into a ledger."""
        ...

    def update_meta_stats(self, ledgers: List[DailyLedger]) -> MetaDailyStats:
        """Compute streaks and records from ledger history."""
        ...

    def save_ledger(self, ledger: DailyLedger, event_store: EventStore) -> None:
        """Write ledger to daily_ledgers table."""
        ...

    def load_ledgers(self, event_store: EventStore) -> List[DailyLedger]:
        """Load all ledgers from SQLite."""
        ...
```

**Integration**: The facade's `update()` method checks if the game-day changed. If so, compute ledger for previous day, store it, update meta stats.

**EventStore additions needed**: Two new methods:
- `store_daily_ledger(game_day, data_json)` — INSERT into `daily_ledgers`
- `load_daily_ledgers()` → List of (game_day, data_json) tuples
- `store_meta_daily_stats(data_json)` — UPSERT into `meta_daily_stats`
- `load_meta_daily_stats()` → data_json string

---

## 6. Retention Policy Alignment

### Current State (`retention.py` — 94 lines)

The existing retention manager is thin. Need to verify it implements the 6 preservation rules from Design Doc §5.4.

### Design Doc Requirements (§5.4)

For each `(actor_id, event_type, event_subtype)` group, **always keep**:

1. **First occurrence** — `interpretation_count = 1`
2. **Threshold-indexed events** — `interpretation_count` in `THRESHOLD_SET`
3. **Power-of-10 milestones** — `interpretation_count` in `{10, 100, 1000, 10000}`
4. **Events that triggered interpretations** — `triggered_interpretation = 1`
5. **Events referenced by Layer 3 cause chains** — appear in `interpretations.cause_event_ids_json`
6. **One event per game-day** — timeline markers (keep the first event of each game-day)

**Prune everything else** after configurable age (default ~50 game-time units).

### Implementation Plan

```python
class EventRetentionManager:
    def __init__(self, max_age: float = 50.0):
        self.max_age = max_age

    def run_retention(self, event_store: EventStore, current_game_time: float,
                      game_day_length: float = 1.0) -> int:
        """Delete prunable events older than max_age. Returns count deleted."""
        cutoff = current_game_time - self.max_age

        # Get all events older than cutoff
        # For each (actor, type, subtype) group:
        #   - Keep event where interpretation_count = 1 (first occurrence)
        #   - Keep events where interpretation_count in THRESHOLD_SET
        #   - Keep events where triggered_interpretation = 1
        #   - Keep events referenced in cause chains (join with interpretations)
        #   - Keep one event per game-day bucket
        #   - Delete the rest

        # SQL approach: DELETE with NOT IN subquery
        # This is a single SQL statement — efficient and atomic
        ...
```

**SQL for identifying protected events** (the NOT IN subquery):

```sql
-- Events to KEEP (do not delete)
SELECT event_id FROM events WHERE game_time < :cutoff AND (
    -- Rule 1: First occurrence
    interpretation_count = 1
    -- Rule 2: Threshold milestones
    OR interpretation_count IN (1,3,5,10,25,50,100,250,500,1000,2500,5000,10000)
    -- Rule 3: Power-of-10 (subset of Rule 2, but explicit for clarity)
    -- Rule 4: Triggered interpretations
    OR triggered_interpretation = 1
)
UNION
-- Rule 5: Events in cause chains
SELECT DISTINCT value AS event_id
FROM interpretations, json_each(interpretations.cause_event_ids_json)
WHERE interpretations.archived = 0
UNION
-- Rule 6: First event per game-day (one per day per actor/type/subtype group)
SELECT event_id FROM (
    SELECT event_id, ROW_NUMBER() OVER (
        PARTITION BY actor_id, event_type, event_subtype,
                     CAST(game_time / :day_length AS INTEGER)
        ORDER BY game_time ASC
    ) AS rn FROM events WHERE game_time < :cutoff
) WHERE rn = 1
```

**Key concern**: The `json_each()` function for Rule 5 requires SQLite 3.38+. Python 3.9+ ships with SQLite 3.35+, so we need to verify. Fallback: parse cause chains in Python.

**Frequency**: Run retention every ~100 events recorded (configurable). The facade's `update()` already calls retention periodically.

### Estimated Impact

10,000 oak gathers → keep ~200 events (~2%):
- 1 first occurrence
- 15 threshold events
- ~50 game-day markers (at 1 event/day over 50 days)
- ~10 triggered interpretation events
- ~5 cause-chain references
- ~120 events within max_age (not yet prunable)

---

## 7. Test Strategy — Mock-Based Pipeline Tests

### Philosophy

All tests run **without the game engine**. Mock events are created programmatically via `WorldMemoryEvent.create()` or `EventRecorder.record_direct()`. Tests verify the full pipeline: event → store → tags → triggers → (interpreter hook called).

### Test File: `test_foundation_pipeline.py` (~400-500 lines)

Located at `world_system/world_memory/test_foundation_pipeline.py`.

### Test Categories

#### 7.1 SQL Schema Integrity Tests

```python
class TestSQLSchema:
    """Verify all tables and indexes exist."""

    def test_all_tables_created(self, tmp_store):
        """Every table in design doc §11 exists."""
        tables = tmp_store.get_table_names()
        expected = [
            "events", "event_tags", "occurrence_counts",
            "interpretations", "interpretation_tags",
            "entity_state", "region_state",
            "npc_memory", "faction_state", "faction_reputation_history",
            "biome_resource_state",
            # NEW tables
            "regional_counters", "interpretation_counters",
            "daily_ledgers", "meta_daily_stats",
            "connected_interpretations", "connected_interpretation_tags",
            "province_summaries", "realm_state",
            "world_narrative", "narrative_threads",
        ]
        for table in expected:
            assert table in tables, f"Missing table: {table}"

    def test_indexes_exist(self, tmp_store):
        """Key indexes exist for query performance."""
        indexes = tmp_store.get_index_names()
        must_have = [
            "idx_events_type", "idx_events_actor", "idx_events_time",
            "idx_events_locality", "idx_events_chunk",
            "idx_event_tags_tag", "idx_interp_category",
        ]
        for idx in must_have:
            assert idx in indexes, f"Missing index: {idx}"

    def test_foreign_keys_enabled(self, tmp_store):
        """PRAGMA foreign_keys = ON."""
        result = tmp_store.connection.execute("PRAGMA foreign_keys").fetchone()
        assert result[0] == 1

    def test_wal_mode(self, tmp_store):
        """PRAGMA journal_mode = WAL."""
        result = tmp_store.connection.execute("PRAGMA journal_mode").fetchone()
        assert result[0].lower() == "wal"
```

#### 7.2 Event Recording + Tag Tests

```python
class TestEventRecording:
    """Verify events are stored correctly with proper tags."""

    def test_record_and_retrieve(self, tmp_store):
        """Record an event, read it back, verify all fields."""
        event = WorldMemoryEvent.create(
            event_type="enemy_killed", event_subtype="killed_wolf",
            actor_id="player", position_x=50.0, position_y=75.0,
            magnitude=35.0, tags=["event:enemy_killed", "species:wolf"],
        )
        tmp_store.record(event)
        got = tmp_store.get_event(event.event_id)
        assert got is not None
        assert got.event_type == "enemy_killed"
        assert got.magnitude == 35.0

    def test_tags_stored_and_queryable(self, tmp_store):
        """Tags written to event_tags table, retrievable by tag."""
        event = WorldMemoryEvent.create(
            event_type="resource_gathered", event_subtype="gathered_iron",
            actor_id="player", tags=["resource:iron", "biome:quarry", "tier:2"],
        )
        tmp_store.record(event)
        results = tmp_store.query_events_by_tags(["resource:iron"])
        assert len(results) == 1

    def test_geographic_enrichment_adds_location_tags(self):
        """After _enrich_geographic + _add_derived_tags, location tags present."""
        # Setup geographic registry with test regions
        # Record event at known position
        # Verify location:{locality} and location:{district} in tags

    def test_intensity_tags(self):
        """Magnitude-based intensity tags calculated correctly."""
        # T1 baseline = 10. Magnitude 35 → ratio 3.5 → "intensity:extreme"
        # T2 baseline = 25. Magnitude 10 → ratio 0.4 → "intensity:light"

    def test_species_tags_from_enemy_kills(self):
        """enemy_type → species:{type} tag."""
        # Bus event with enemy_type="wolf" → species:wolf tag

    def test_complete_wolf_kill_tag_set(self):
        """Full integration: wolf kill produces exact tag set from design doc §9.2."""
        expected = [
            "event:enemy_killed", "species:wolf", "combat:melee",
            "element:physical", "biome:forest", "tier:1",
            "location:whispering_woods", "location:eastern_highlands",
            "intensity:moderate",
        ]
```

#### 7.3 Trigger System Tests

```python
class TestTriggerManager:
    """Verify threshold-based dual-track triggering."""

    def test_threshold_sequence_fires(self):
        """Events fire at exactly 1, 3, 5, 10, 25, 50, 100..."""
        tm = TriggerManager()
        fired_at = []
        for i in range(1, 110):
            event = make_wolf_kill(locality="woods")
            actions = tm.on_event(event)
            if any(a.action_type == "interpret_stream" for a in actions):
                fired_at.append(i)
        assert fired_at == [1, 3, 5, 10, 25, 50, 100]

    def test_no_fire_between_thresholds(self):
        """No trigger at 2, 4, 6, 7, 8, 9, 11-24, 26-49..."""
        tm = TriggerManager()
        for i in range(1, 110):
            event = make_wolf_kill(locality="woods")
            actions = tm.on_event(event)
            stream_actions = [a for a in actions if a.action_type == "interpret_stream"]
            count = tm._stream_counts[list(tm._stream_counts.keys())[0]]
            if count not in THRESHOLD_SET:
                assert len(stream_actions) == 0

    def test_primes_do_NOT_fire(self):
        """Verify primes like 2, 7, 11, 13, 17, 19, 23 do NOT trigger."""
        tm = TriggerManager()
        primes_that_should_not_fire = [2, 7, 11, 13, 17, 19, 23, 29, 31, 37, 41, 43, 47]
        fired_at = set()
        for i in range(1, 50):
            event = make_wolf_kill(locality="woods")
            actions = tm.on_event(event)
            if any(a.action_type == "interpret_stream" for a in actions):
                fired_at.add(i)
        for p in primes_that_should_not_fire:
            assert p not in fired_at, f"Prime {p} should NOT fire"

    def test_dual_track_regional(self):
        """Different event types in same locality accumulate for Track 2."""
        tm = TriggerManager()
        # 3 wolf kills + 2 bear kills = 5 combat events in same locality
        for _ in range(3):
            tm.on_event(make_event("enemy_killed", "killed_wolf", locality="woods"))
        for _ in range(2):
            tm.on_event(make_event("enemy_killed", "killed_bear", locality="woods"))
        # Regional combat count = 5 → threshold hit
        regional_key = ("woods", "combat")
        assert tm._regional_counts[regional_key] == 5
        # The 5th event should have produced a regional trigger
        actions = tm.on_event(make_event("enemy_killed", "killed_bear", locality="woods"))
        # ... verify interpret_region action exists

    def test_different_localities_dont_cross(self):
        """Events in different localities tracked independently."""
        tm = TriggerManager()
        for _ in range(5):
            tm.on_event(make_wolf_kill(locality="woods"))
        for _ in range(5):
            tm.on_event(make_wolf_kill(locality="hills"))
        # Each stream has count 5. No cross-contamination.

    def test_position_samples_dont_trigger_regional(self):
        """position_sample category is 'other' — excluded from regional."""
        tm = TriggerManager()
        for _ in range(100):
            tm.on_event(make_event("position_sample", "position_sample", locality="woods"))
        # No regional triggers (category="other" is excluded)
```

#### 7.4 Time Envelope Tests

```python
class TestTimeEnvelope:
    """Verify temporal analysis computations."""

    def test_empty_events(self):
        env = compute_envelope([], current_game_time=100.0)
        assert env.trend == "dormant"
        assert env.total_count == 0

    def test_single_event(self):
        events = [make_event_at_time(50.0)]
        env = compute_envelope(events, current_game_time=100.0)
        assert env.total_count == 1
        assert env.first_at == 50.0

    def test_trend_accelerating(self):
        """Most recent day has >> average → accelerating."""
        # 7 events spread over 7 days, then 5 events in the last day
        events = [make_event_at_time(t) for t in [1,2,3,4,5,6,7, 7.1,7.2,7.3,7.4,7.5]]
        env = compute_envelope(events, current_game_time=8.0)
        assert env.trend == "accelerating"

    def test_trend_dormant(self):
        """No events in last 7 days → dormant."""
        events = [make_event_at_time(1.0)]
        env = compute_envelope(events, current_game_time=100.0)
        assert env.trend == "dormant"

    def test_trend_burst(self):
        """Single day has > 30% of all-time events → burst."""
        # 10 events total, 4 in last day
        events = [make_event_at_time(t) for t in [1,2,3,4,5,6, 9.1,9.2,9.3,9.4]]
        env = compute_envelope(events, current_game_time=10.0)
        assert env.trend == "burst"

    def test_severity_modifier(self):
        assert TREND_SEVERITY_MODIFIER["burst"] == 2.0
        assert TREND_SEVERITY_MODIFIER["dormant"] == 0.5
```

#### 7.5 Daily Ledger Tests

```python
class TestDailyLedger:
    """Verify daily aggregation."""

    def test_compute_combat_day(self):
        """Day with combat events → correct damage/kill counts."""
        events = [
            make_event("attack_performed", "dealt_physical", magnitude=50),
            make_event("attack_performed", "dealt_physical", magnitude=30),
            make_event("enemy_killed", "killed_wolf", magnitude=1),
            make_event("enemy_killed", "killed_bear", magnitude=1),
        ]
        ledger = DailyLedgerManager().compute_ledger(1, events)
        assert ledger.damage_dealt == 80.0
        assert ledger.enemies_killed == 2
        assert ledger.unique_enemy_types_fought == 2
        assert ledger.primary_activity == "combat"

    def test_compute_gathering_day(self):
        events = [make_event("resource_gathered", "gathered_iron")] * 50
        ledger = DailyLedgerManager().compute_ledger(1, events)
        assert ledger.resources_gathered == 50
        assert ledger.primary_activity == "gathering"

    def test_ledger_serialization(self):
        """Round-trip: DailyLedger → JSON → DailyLedger."""
        ledger = DailyLedger(game_day=1, game_time_start=0.0, game_time_end=1.0,
                            enemies_killed=5, damage_dealt=200.0)
        json_str = ledger.to_json()
        restored = DailyLedger.from_json(1, json_str)
        assert restored.enemies_killed == 5

    def test_store_and_load_ledger(self, tmp_store):
        """Ledger persists to SQLite and loads back."""
```

#### 7.6 Full Pipeline Integration Test

```python
class TestFullPipeline:
    """End-to-end: create events → verify storage → verify triggers → verify tags."""

    def test_100_wolf_kills_pipeline(self, tmp_dir):
        """Simulate 100 wolf kills, verify entire pipeline."""
        # Setup
        store = EventStore(save_dir=tmp_dir)
        geo = GeographicRegistry.get_instance()
        # Load test geographic map (small: 1 realm, 1 province, 2 districts, 4 localities)
        geo.load_base_map(TEST_GEO_MAP)
        entity_reg = EntityRegistry.get_instance()
        trigger_mgr = TriggerManager()
        recorder = EventRecorder.get_instance()
        recorder.initialize(store, geo, entity_reg, trigger_mgr, "test_session")

        # Track interpreter callbacks
        triggered_events = []
        recorder.set_interpreter_callback(lambda action: triggered_events.append(action))

        # Simulate 100 wolf kills at position (50, 75) → locality "whispering_woods"
        for i in range(100):
            recorder.record_direct(
                event_type="enemy_killed",
                event_subtype="killed_wolf",
                actor_id="player",
                position_x=50.0, position_y=75.0,
                magnitude=35.0,
                tags=["event:enemy_killed", "species:wolf"],
                context={"enemy_type": "wolf", "tier": 1},
            )

        # Verify storage
        assert store.get_event_count() == 100

        # Verify trigger callbacks
        trigger_counts = [t.count for t in triggered_events if t.action_type == "interpret_stream"]
        assert trigger_counts == [1, 3, 5, 10, 25, 50, 100]

        # Verify NO prime-based triggers
        assert 2 not in trigger_counts
        assert 7 not in trigger_counts
        assert 11 not in trigger_counts

        # Verify regional triggers also fired
        regional_counts = [t.count for t in triggered_events if t.action_type == "interpret_region"]
        assert 1 in regional_counts
        assert 100 in regional_counts

        # Verify tags on a stored event
        events = store.query_events_by_type("enemy_killed", limit=1)
        assert "species:wolf" in events[0].tags

    def test_mixed_event_types_pipeline(self, tmp_dir):
        """Different event types in same locality trigger regional accumulators."""
        # 3 wolf kills + 3 resource gathers + 3 crafts
        # Regional: combat=3 (threshold), gathering=3 (threshold), crafting=3 (threshold)
        # Each hits threshold at 3

    def test_retention_preserves_milestones(self, tmp_dir):
        """After retention, threshold milestones still exist."""
        # Record 200 events, run retention, verify ~15 remain
```

### Test Infrastructure

```python
# Fixtures
@pytest.fixture
def tmp_store(tmp_path):
    store = EventStore(save_dir=str(tmp_path))
    yield store
    store.close()

@pytest.fixture(autouse=True)
def reset_singletons():
    """Reset all singletons between tests."""
    EventRecorder.reset()
    TriggerManager.reset()
    GeographicRegistry.reset()
    EntityRegistry.reset()
    WorldQuery.reset()
    yield

# Test geographic map (minimal)
TEST_GEO_MAP = {
    "realm": {"id": "test_realm", "name": "Test Realm"},
    "provinces": [{"id": "test_province", "bounds": [0,0,99,99]}],
    "districts": [
        {"id": "eastern_highlands", "bounds": [0,0,49,99], "parent": "test_province"},
        {"id": "western_lowlands", "bounds": [50,0,99,99], "parent": "test_province"},
    ],
    "localities": [
        {"id": "whispering_woods", "bounds": [0,0,24,49], "parent": "eastern_highlands",
         "biome": "forest", "tags": ["terrain:forest", "species:wolf"]},
        {"id": "iron_hills", "bounds": [25,0,49,49], "parent": "eastern_highlands",
         "biome": "quarry", "tags": ["terrain:hills", "resource:iron"]},
    ]
}

# Helper functions
def make_wolf_kill(locality="unknown", game_time=0.0):
    return WorldMemoryEvent.create(
        event_type="enemy_killed", event_subtype="killed_wolf",
        actor_id="player", position_x=10.0, position_y=20.0,
        magnitude=35.0, locality_id=locality,
        tags=["event:enemy_killed", "species:wolf"],
    )

def make_event(event_type, subtype, locality="unknown", magnitude=1.0, **kwargs):
    return WorldMemoryEvent.create(
        event_type=event_type, event_subtype=subtype,
        actor_id="player", locality_id=locality,
        magnitude=magnitude, **kwargs,
    )

def make_event_at_time(game_time, event_type="enemy_killed"):
    return WorldMemoryEvent.create(
        event_type=event_type, event_subtype="test",
        actor_id="player", game_time=game_time,
    )
```

---

## 8. Implementation Order (Step-by-Step)

### Phase 1: SQL Schema + TriggerManager (P0 — blocks everything)

**Step 1.1**: Add new table DDL to `event_store.py`
- Append 10 new `CREATE TABLE IF NOT EXISTS` blocks to `_SCHEMA_SQL`
- Update comment from "prime trigger" to "threshold trigger" on `occurrence_counts`
- Add helper methods: `increment_regional_counter()`, `get_regional_count()`, `store_daily_ledger()`, `load_daily_ledgers()`, `store_meta_stats()`, `load_meta_stats()`, `get_table_names()`, `get_index_names()`
- **Test**: `test_all_tables_created`, `test_indexes_exist`, `test_foreign_keys_enabled`, `test_wal_mode`

**Step 1.2**: Create `trigger_manager.py`
- `THRESHOLDS`, `THRESHOLD_SET`, `EVENT_CATEGORY_MAP` constants
- `TriggerAction` dataclass
- `TriggerManager` class with `on_event()`, `get_state()`, `load_state()`
- **Test**: `test_threshold_sequence_fires`, `test_no_fire_between_thresholds`, `test_primes_do_NOT_fire`, `test_dual_track_regional`, `test_different_localities_dont_cross`, `test_position_samples_dont_trigger_regional`

**Step 1.3**: Update `event_recorder.py`
- Remove `_generate_primes()`, `_PRIMES`, `is_prime_trigger()` (lines 22-55)
- Add `trigger_manager` parameter to `initialize()`
- Update `_on_bus_event()` to use `TriggerManager.on_event()`
- Update `record_direct()` similarly
- Add `_add_derived_tags()` method (Phase 2 tags: location, species, npc, quest, intensity)
- Restructure `_on_bus_event()` to call `_add_derived_tags()` after `_enrich_geographic()`
- **Test**: `test_geographic_enrichment_adds_location_tags`, `test_intensity_tags`, `test_species_tags_from_enemy_kills`, `test_complete_wolf_kill_tag_set`

**Step 1.4**: Update `world_memory_system.py` facade
- Create TriggerManager in `initialize()`
- Pass it to EventRecorder
- Add trigger state to save/load

### Phase 2: Time Tracking (P1)

**Step 2.1**: Create `time_envelope.py`
- `TimeEnvelope` dataclass
- `TREND_SEVERITY_MODIFIER` constant
- `compute_envelope()` function
- `_detect_trend()` helper
- **Test**: All `TestTimeEnvelope` tests

**Step 2.2**: Create `daily_ledger.py`
- `DailyLedger` dataclass with serialization
- `MetaDailyStats` dataclass with serialization
- `DailyLedgerManager` class
- **Test**: All `TestDailyLedger` tests

**Step 2.3**: Wire into facade
- Track current game-day in `update()`
- On day change: compute ledger, store, update meta stats
- Add `game_day_length` to config

### Phase 3: Retention Alignment (P1)

**Step 3.1**: Rewrite `retention.py`
- Implement 6 preservation rules from design doc
- Use SQL with THRESHOLD_SET for Rule 2
- Handle `json_each()` for Rule 5 (with Python fallback)
- **Test**: `test_retention_preserves_milestones`

### Phase 4: Full Pipeline Integration (P1)

**Step 4.1**: Create `test_foundation_pipeline.py`
- Full pipeline test with 100 wolf kills
- Mixed event type test
- Retention + milestone test
- **Test**: All `TestFullPipeline` tests

**Step 4.2**: Verify against existing tests
- Run `test_memory_system.py` — must still pass
- Run `tests/test_phase2_systems.py` — must still pass

---

## 9. Files Changed Summary

| File | Action | Est. Lines Changed |
|------|--------|-------------------|
| `event_store.py` | ADD SQL DDL + helper methods | +150 |
| `trigger_manager.py` | **NEW** | ~180 |
| `event_recorder.py` | MODIFY (remove primes, add TriggerManager, add derived tags) | ~80 changed |
| `time_envelope.py` | **NEW** | ~120 |
| `daily_ledger.py` | **NEW** | ~200 |
| `retention.py` | REWRITE | ~150 (was 94) |
| `world_memory_system.py` | MODIFY (add TriggerManager, daily ledger hooks) | ~30 changed |
| `event_schema.py` | MINOR (add TriggerAction if not in trigger_manager) | ~10 |
| `test_foundation_pipeline.py` | **NEW** | ~450 |
| **Total** | | ~1,370 new/changed |

---

## 10. Risk Analysis

| Risk | Mitigation |
|------|-----------|
| Existing tests break when primes removed | Run existing tests first. The test assertions check for `triggered_interpretation=True` — update those to match new threshold behavior. |
| SQLite `json_each()` not available in older Python | Add version check. Python 3.9 → SQLite 3.35+. `json_each()` was added in 3.38.0. If unavailable, parse cause chains in Python. |
| TriggerManager memory grows unbounded | Stream counts grow with `O(unique_streams)`. With ~30 event types × 60 localities × 1 actor = ~1,800 entries max. Negligible. |
| Game-day boundary detection in facade | Need to compare `current_game_time / game_day_length` on each update tick. Off-by-one if day length is fractional — use `int(time / length)`. |
| Existing `occurrence_counts` table has no locality_id | TriggerManager keeps its own in-memory counts. The SQL table is still used for total counts (useful for other queries). No schema change needed. |

---

## 11. Definition of Done

- [ ] All new SQL tables exist and are verified by `test_all_tables_created`
- [ ] `TriggerManager` fires at threshold sequence, NOT primes
- [ ] Dual-track counting works (stream + regional, verified by test)
- [ ] Auto-tagging produces location, species, intensity tags
- [ ] `TimeEnvelope` correctly detects all 5 trends
- [ ] `DailyLedger` computes from events and persists to SQLite
- [ ] Retention preserves the 6 milestone categories
- [ ] Full pipeline test: 100 wolf kills → 7 stream triggers + regional triggers + correct tags
- [ ] ALL existing tests still pass
- [ ] No references to prime-number triggers remain in codebase

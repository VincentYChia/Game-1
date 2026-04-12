# World Memory System — Unified Design Document

**Canonical Location**: `Game-1-modular/world_system/docs/WORLD_MEMORY_SYSTEM.md`
**Created**: 2026-03-16 | **Last Updated**: 2026-03-25
**Status**: Design Complete — Ready for Implementation
**Phase**: 2.1 of Living World Development Plan

> This is the **single source of truth** for the World Memory System design. It consolidates all prior design documents (Development-Plan/ fragments, world_system/docs/ specs, companion docs) into one comprehensive reference. If anything contradicts this document, this document wins.

---

## Table of Contents

1. [Architecture Overview — The 7-Layer Model](#1-architecture-overview)
2. [Trigger & Escalation System](#2-trigger--escalation-system)
3. [Geographic System](#3-geographic-system)
4. [Entity Registry & Interest Tags](#4-entity-registry--interest-tags)
5. [Event Schema & Recording Pipeline](#5-event-schema--recording-pipeline)
6. [Interpreter & Evaluators (Layers 2-3)](#6-interpreter--evaluators-layers-2-3)
7. [Aggregation & World State (Layers 3-7)](#7-aggregation--world-state-layers-3-7)
8. [Time-Based Tracking & Recency](#8-time-based-tracking--recency)
9. [Tagging Strategy](#9-tagging-strategy)
10. [Retrieval Design](#10-retrieval-design)
11. [Storage Schema](#11-storage-schema)
12. [Living World Agents](#12-living-world-agents)
13. [AI Touchpoint Map](#13-ai-touchpoint-map)
14. [Integration Points, File Structure, Build Order](#14-integration--build-order)
15. [Future Design: Narrative Threads & Player Profile](#15-future-design)
16. [Worked Example: Over-Harvesting Iron](#16-worked-example)

---

## Design Principles

1. **Information state only** — Records and interprets. Does NOT apply mechanical game effects, generate dialogue, or make gameplay decisions. Narrative text summaries, not JSON effects. Consumer systems (NPC dialogue, quest generation, faction decisions) are architecturally separate — they READ from WMS but are not part of it.
2. **Entity-first queries** — Never search events directly. Find the entity, radiate outward through location, interests, awareness.
3. **Interest tags are identity** — Overapplied by design. Tags ARE the entity's fingerprint in the information system.
4. **Write-time processing** — Events enriched, propagated, aggregated at write time. Queries are fast reads.
5. **Compression upward** — Each layer condenses the one below. Layer 3 consumers never need the Raw Event Pipeline.
6. **Threshold triggers** — Sequence `1, 3, 5, 10, 25, 50, 100, 250, 500, 1000, 2500, 5000, 10000`. Triggers evaluate; ignoring is valid.
7. **Bounded context** — Every LLM call gets a fixed token budget. No unbounded accumulation.
8. **The world has state beyond the player** — Resources deplete, populations shift, factions maneuver whether the player is present or not.

---

# 1. Architecture Overview

## 1.1 The 7-Layer Model

Data compresses upward. Each layer condenses the one below into better information transfer.

| Layer | Name | Scale | What It Stores | Trigger Cadence |
|:---:|-------|-------|---------------|-----------------|
| 1 | Numerical Stats | Global | 850+ cumulative counters (stat_tracker.py) | Every event |
| — | Raw Event Pipeline | Chunk/Locality | Timestamped facts in SQLite — WHO/WHAT/WHERE/WHEN | Every event |
| 2 | Simple Text Events | Locality/District | One-sentence narratives from evaluators (evaluator output) | Milestone series |
| 3 | Municipality/Local Consolidation | District/Province | Cross-domain and cross-region pattern detection | Accumulation-based |
| 4 | Smaller Region Events | Province | Gross summaries of provincial state | Provincial triggers |
| 5 | Larger Region/Country Events | Realm | Faction landscapes, economic state, player reputation | Multi-province |
| 6 | Intercountry Events | Multi-Realm | Cross-realm patterns, trade routes, diplomatic state | Multi-realm |
| 7 | World Events | World | Narrative threads, world identity, themes, history | World-shaping only |

### The Compression Principle

**"Two layers down" visibility rule**: Layer N can see Layer N-1 (full access) and Layer N-2 (limited/summary access). It never reads lower than that. This forces each layer to do its compression job — you can't skip layers.

### The Fact/Interpretation Boundary

The critical line sits between the Raw Event Pipeline and Layer 2:
- **Below** (Layer 1 + Raw Event Pipeline): **Facts** — immutable records of what happened
- **Above** (Layers 2-7): **Interpretations** — derived meaning, narratives, summaries

### Data Flow Pipeline

```
GAME ACTION (player mines iron)
       │
       ▼
  Layer 0: GameEventBus.publish("RESOURCE_GATHERED", {...})  [ephemeral]
       │
       ├──→ Layer 1: stat_tracker.record(...)                 [existing, unchanged]
       │
       └──→ Raw Event Pipeline: EventRecorder.record(...)     [NEW — SQLite]
                │     Structured event with geographic context + auto-tags
                │
                ▼
            TriggerManager                                     [NEW]
                │     Checks: individual stream + regional accumulator thresholds
                │
                ▼
            Layer 2 Evaluators (if threshold hit)               [NEW]
                │     Evaluators check patterns
                │     Generate one-sentence narrative (or ignore)
                │
                ▼
            Layer 3 Aggregator (if accumulation threshold)     [NEW]
                │     Cross-domain + cross-region patterns
                │
                ▼
            Layers 4-7 (if significance warrants)              [NEW]
                │     Smaller Region → Larger Region → Intercountry → World summaries
                │
                ▼
            [Ready for downstream queries by NPC agents, quest gen, etc.]
```

**Critical**: This pipeline runs at **write time**, not query time. Queries are fast reads.

### Strict Layer Boundaries

Writes flow downward through the pipeline. Reads flow upward. The cycle goes through the **decision layer** (NPC AI, game systems) which is external to the data layers — no circular dependencies within data.

## 1.2 Layer Definitions

### Layer 1: Numerical Stats (Existing, Unchanged)
- **File**: `entities/components/stat_tracker.py` (~1,756 lines, 850+ stats)
- **Role**: Fast-path for aggregate queries. "How many wolves killed total?" answered instantly.
- **No changes needed.**

### Raw Event Pipeline: Structured Events (NEW — SQLite)
- Every meaningful action recorded with full spatial, temporal, contextual data
- One row per event, indexed for spatial/temporal queries
- **Retention**: Pruned over time but first occurrences, threshold milestones, and timeline markers always kept

### Layer 2: Simple Text Events (NEW — SQLite)
- Pattern-detected one-sentence narratives from evaluators
- Each has cause chain, affected tags, severity, duration
- **Narrative text only** — no JSON effects

### Layer 3: Municipality/Local Consolidation (NEW — SQLite)
- Cross-domain patterns: "heavy combat AND resource depletion in same region"
- Cross-region patterns: "iron scarce across multiple districts"
- 4 evaluators synthesize Layer 2 interpretations

### Layer 4: Smaller Region Events (NEW — SQLite)
- Per-province gross summaries: dominant activities, notable events, resource state
- Updated when Layer 3 changes significantly in child regions

### Layer 5: Larger Region/Country Events (NEW — SQLite)
- Faction power balances, economic state, player reputation realm-wide
- Single row per realm, updated on multi-province events

### Layer 6: Intercountry Events (NEW — SQLite)
- Cross-realm patterns, trade routes, diplomatic state
- Updated on multi-realm events

### Layer 7: World Events (NEW — SQLite)
- Narrative threads (persistent story elements with canonical facts)
- World identity, themes, historical events
- Updated only by world-shaping events

---

# 2. Trigger & Escalation System

## 2.1 The Threshold Sequence

```
1, 3, 5, 10, 25, 50, 100, 250, 500, 1000, 2500, 5000, 10000, 25000, 100000
```

The biggest behavioral leaps happen at **1, 10, 100, 1000**. Intermediate points (3, 5, 25, 50, 250, 500) give the system chances to detect patterns without requiring change. **Triggers are opportunities to evaluate, not mandates to produce output.**

## 2.2 Dual-Track Counting

**Track 1 — Individual event streams**: Count per `(actor_id, event_type, event_subtype, locality_id)`.
- Player kills 1st wolf in Whispering Woods → count=1 → TRIGGER
- 3rd wolf → count=3 → TRIGGER
- 4th wolf → NO trigger
- 5th wolf → count=5 → TRIGGER

**Track 2 — Regional accumulators**: Count per `(locality_id, event_category)`.
- 3 wolf kills + 2 bear kills + 4 bandit kills = regional combat count=9
- 1 more = count=10 → TRIGGER (catches aggregate patterns individual streams miss)

Event categories for Track 2: `combat`, `gathering`, `crafting`, `exploration`, `social`, `progression`, `economy`, `other`.

## 2.3 Layer-by-Layer Trigger Logic

**Raw Event Pipeline→Layer 2**: Individual stream OR regional accumulator hits threshold → run relevant Layer 2 evaluators.

**Layer 2→3**: When a locality accumulates 3+ Layer 2 interpretations (or 2+ from different categories) → trigger Layer 3 consolidation evaluators.

**Layer 3→4**: When a province's child districts accumulate 3+ Layer 3 interpretations → trigger Layer 4 summary regeneration.

**Layer 4→5, 5→6, and 6→7**: Multi-province patterns or world-shaping events (faction wars, resource crises, player legendary achievements).

## 2.4 Pass-Through Cascade

Each layer acts as a filter:

```
Raw Event Pipeline event hits threshold
    │
    ▼
Layer 2 Evaluator (tiny LLM / template)
    ├── IGNORE — "5 wolf kills isn't notable" → stop
    ├── GENERATE — create interpretation → pass to Layer 3 check
    └── ABSORB — update existing interpretation → pass to Layer 3 check
                    │
                    ▼
              Layer 3 Consolidator (tiny LLM)
                  ├── ACCEPT — incorporate → stop
                  ├── IGNORE → stop
                  └── ESCALATE → pass to Layer 4
                                    │
                                    ▼
                              Layer 4+ (medium LLM)
```

### LLM Sizing by Layer

| Layer | LLM Size | Rationale |
|-------|----------|-----------|
| 2 | Template or Tiny (Haiku-class) | High volume, simple pattern recognition |
| 3 | Tiny (Haiku-class) | Summarize a few interpretations |
| 4 | Small-Medium (Sonnet-class) | Cross-locality trends, richer narrative |
| 5-7 | Medium (Sonnet-class) | Rare, complex, world-scale |

No parallelism needed — events don't arrive faster than a small LLM can process.

## 2.5 Early Game Templates

At game start, everything is count=1 simultaneously. Use pre-written templates instead of LLM:

```python
FIRST_EVENT_TEMPLATES = {
    ("enemy_killed", "*"): "A newcomer has begun their first hunt.",
    ("resource_gathered", "*"): "Someone has started harvesting the land.",
    ("craft_attempted", "*"): "A crafter has begun their work.",
    ("chunk_entered", "*"): None,  # Suppress — exploring is expected
    ("npc_interaction", "*"): None,  # Suppress — talking is expected
}
```

- Count=1: Templates (no LLM)
- Count=3: Templates with locale context (string formatting)
- Count=5+: Real LLM evaluator

## 2.6 Trigger Implementation

```python
THRESHOLDS = [1, 3, 5, 10, 25, 50, 100, 250, 500, 1000, 2500, 5000, 10000, 25000, 100000]
THRESHOLD_SET = set(THRESHOLDS)

class TriggerManager:
    """Manages individual + regional trigger counting. Singleton."""
    def __init__(self):
        self.stream_counts: Dict[Tuple, int] = {}       # (actor, type, subtype, locality) → count
        self.regional_counts: Dict[Tuple, int] = {}      # (region_id, category) → count
        self.interpretation_counts: Dict[Tuple, int] = {} # (category, tag, region) → count

    def on_event(self, event: WorldMemoryEvent) -> List[TriggerAction]:
        actions = []
        # Individual stream
        stream_key = (event.actor_id, event.event_type, event.event_subtype, event.locality_id)
        self.stream_counts[stream_key] = self.stream_counts.get(stream_key, 0) + 1
        if self.stream_counts[stream_key] in THRESHOLD_SET:
            actions.append(TriggerAction("interpret_stream", stream_key, self.stream_counts[stream_key]))
        # Regional accumulator
        category = EVENT_CATEGORY_MAP.get(event.event_type, "other")
        region_key = (event.locality_id, category)
        self.regional_counts[region_key] = self.regional_counts.get(region_key, 0) + 1
        if self.regional_counts[region_key] in THRESHOLD_SET:
            actions.append(TriggerAction("interpret_region", region_key, self.regional_counts[region_key]))
        return actions
```

---

# 3. Geographic System

## 3.1 Hierarchy

The game's 100x100 tile world (16x16 chunks) gets a **named address hierarchy** superimposed on the existing biome grid:

```
Realm (entire world, 1)
  └── Province (~25x50 tiles, ~4 per realm)
        └── District (~12x25 tiles, ~12-20 total, "Iron Hills", "Whispering Woods")
              └── Locality (~8x16 tiles, ~40-80 total, "Old Mine Shaft", "Blacksmith's Crossing")
```

## 3.2 Region Definition

```python
class RegionLevel(Enum):
    LOCALITY = "locality"
    DISTRICT = "district"
    PROVINCE = "province"
    REALM = "realm"

@dataclass
class Region:
    region_id: str                    # "iron_hills", "eastern_highlands"
    name: str                         # "Iron Hills"
    level: RegionLevel
    bounds_x1: int; bounds_y1: int    # Top-left (inclusive)
    bounds_x2: int; bounds_y2: int    # Bottom-right (inclusive)
    parent_id: Optional[str]          # None for realm
    child_ids: List[str]
    biome_primary: str
    description: str                  # Narrative description for LLM context
    tags: List[str]                   # Geographic identity tags
    state: RegionState                # Mutable conditions (updated by propagation)
```

### Region Tags

Regions carry `category:value` tags for event routing:
```python
"iron_hills" → ["terrain:hills", "terrain:rocky", "resource:iron", "resource:stone",
                 "resource:copper", "biome:quarry", "biome:cave", "danger:moderate",
                 "feature:mines", "feature:ore_veins", "climate:temperate"]
```

When a "resource_pressure" interpretation is created with `affects_tags: ["resource:iron"]`, the propagator finds all regions whose tags include `resource:iron` and updates their state.

## 3.3 Position-to-Region Lookup

```python
class GeographicRegistry:
    """Maps positions to named regions. Singleton. Cached per chunk."""

    def get_region_at(self, x: float, y: float) -> Optional[Region]:
        """Get locality-level region. Cached by chunk center."""
        chunk_key = (int(x) // 16, int(y) // 16)
        if chunk_key in self._chunk_to_locality:
            return self.regions[self._chunk_to_locality[chunk_key]]
        # Scan localities (once per chunk, then cached)
        for region in self.regions.values():
            if region.level == RegionLevel.LOCALITY:
                if region.bounds_x1 <= x <= region.bounds_x2 and region.bounds_y1 <= y <= region.bounds_y2:
                    self._chunk_to_locality[chunk_key] = region.region_id
                    return region
        return None

    def get_full_address(self, x: float, y: float) -> Dict[str, str]:
        """Returns {"locality": "...", "district": "...", "province": "..."}"""
        ...

    def get_regions_by_tag(self, tag: str) -> List[Region]: ...
    def get_nearby_regions(self, x, y, radius, level) -> List[Region]: ...
```

Every Raw Event Pipeline event gets region IDs stamped from the chunk cache — zero per-event lookup cost.

## 3.4 Map Definition

**Recommended: Hybrid** — Procedural generation from biome data for basic structure, then hand-authored overrides via `AI-Config.JSON/geographic-map.json`. New regions addable at runtime (narrative discoveries, world expansion).

---

# 4. Entity Registry & Interest Tags

## 4.1 Entity Definition

Every queryable thing in the world gets a registry entry — the **starting point** for all queries.

```python
class EntityType(Enum):
    PLAYER = "player"
    NPC = "npc"
    ENEMY_TYPE = "enemy_type"      # Species, not individuals
    RESOURCE_TYPE = "resource_type" # Kind, not individual nodes
    LOCATION = "location"           # Named regions
    STATION = "station"
    FACTION = "faction"

@dataclass
class WorldEntity:
    entity_id: str                    # "npc_blacksmith_gareth", "enemy_type_wolf"
    entity_type: EntityType
    name: str
    position_x: Optional[float]      # None for abstract entities (factions, resource types)
    position_y: Optional[float]
    home_region_id: Optional[str]     # Primary locality
    home_district_id: Optional[str]   # Cached parent
    home_province_id: Optional[str]   # Cached parent
    awareness_radius: float           # NPC: ~32-48 tiles, Player: global
    tags: List[str]                   # THE IDENTITY — interest tags
    activity_log: List[str]           # Circular buffer of recent event_ids (max ~100)
    metadata: Dict[str, Any]          # Entity-specific static properties
```

## 4.2 The Interest Tag System

Tags follow `category:value` format. They are **overapplied by design** — they define what the entity notices, cares about, and knows about.

### Tag Categories

```
SPECIES/TYPE:     species:human, species:wolf, type:npc, type:hostile
LOCATION:         location:iron_hills, origin:northern_reaches
AFFILIATION:      faction:miners_guild, allegiance:crown, guild:smithing
JOB/ROLE:         job:blacksmith, job:merchant, role:quest_giver
DOMAIN:           domain:smithing, domain:metalwork, domain:herbs, domain:combat
RESOURCE:         resource:iron, resource:steel, resource:herbs
TENDENCY:         tendency:cautious, tendency:gossip, tendency:honest
PREFERENCE:       preference:quality_over_quantity, preference:rare_materials
CONCERN:          concern:safety, concern:scarcity, concern:wildlife
BIOME:            biome:forest, biome:cave, biome:quarry
COMBAT:           combat:melee, tier:1, element:fire
EVENT INTEREST:   event:trade, event:combat, event:crafting
```

### Example: Gareth the Blacksmith

```python
tags = [
    "species:human", "type:npc",
    "location:blacksmiths_crossing", "location:iron_hills",
    "job:blacksmith", "role:shopkeeper", "guild:smithing",
    "domain:smithing", "domain:metalwork", "domain:weapons", "domain:armor",
    "resource:iron", "resource:steel", "resource:mithril", "resource:coal",
    "tendency:honest", "tendency:perfectionist",
    "preference:quality_over_quantity", "preference:rare_materials",
    "concern:scarcity", "concern:reputation",
    "event:trade", "event:crafting",
    "biome:quarry", "biome:cave"
]
```

## 4.3 Tag Matching

```python
def calculate_relevance(entity_tags: List[str], event_tags: List[str]) -> float:
    """Score 0.0 (irrelevant) to 1.0 (directly relevant) based on tag overlap."""
    entity_categories = {}
    for tag in entity_tags:
        cat, val = tag.split(":", 1)
        entity_categories.setdefault(cat, set()).add(val)

    event_categories = {}
    for tag in event_tags:
        cat, val = tag.split(":", 1)
        event_categories.setdefault(cat, set()).add(val)

    matches = 0
    for cat, vals in event_categories.items():
        if cat in entity_categories:
            matches += 1.0 if entity_categories[cat] & vals else 0.3
    return min(1.0, matches / max(len(event_categories), 1))
```

**Scoring matrix**: Exact value match = 1.0, same category different value = 0.3, concern match = 0.5, distance factor = 0.2-0.8.

## 4.4 Entity Registration

Registry loads from multiple sources at startup:
- `load_from_npcs(npc_db)` — registers all NPCs with auto-generated tags
- `load_from_regions(geo_registry)` — registers regions as queryable entities
- `register_player(character)` — player entity with dynamic tags from behavior

Tags update dynamically via `update_entity_tags(entity_id, add_tags, remove_tags)`.

---

# 5. Event Schema & Recording Pipeline

## 5.1 Raw Event Pipeline Event Schema

```python
@dataclass
class WorldMemoryEvent:
    """Atomic unit of world memory — one thing that happened."""
    # Identity
    event_id: str                     # UUID
    event_type: str                   # EventType enum value
    event_subtype: str                # "mined_iron", "killed_wolf", "crafted_sword"

    # WHO
    actor_id: str                     # "player", "npc_gareth"
    actor_type: str                   # "player", "npc", "enemy", "system"
    target_id: Optional[str]
    target_type: Optional[str]

    # WHERE
    position_x: float; position_y: float
    chunk_x: int; chunk_y: int        # Derived: int(pos) // 16
    locality_id: Optional[str]        # From geographic registry (cached per chunk)
    district_id: Optional[str]
    province_id: Optional[str]
    biome: str

    # WHEN
    game_time: float                  # In-game timestamp
    real_time: float                  # Wall clock (debugging)
    session_id: str

    # WHAT
    magnitude: float                  # Primary numeric value (damage, quantity, gold)
    result: str                       # "success", "failure", "critical", "dodge"
    quality: Optional[str]            # "normal"..."legendary"
    tier: Optional[int]               # T1-T4

    # TAGS — for matching against entity interests (see §9 Tagging)
    tags: List[str]                   # Auto-generated at recording time

    # CONTEXT (event-type-specific data)
    context: Dict[str, Any]           # combat: {weapon, enemy_tier, health_pct}
                                      # gathering: {tool, node_remaining_pct, rare_drop}
                                      # crafting: {recipe_id, discipline, minigame_score}

    # TRIGGER TRACKING
    interpretation_count: int = 0     # Occurrence count for this (actor, type, subtype)
    triggered_interpretation: bool = False
```

## 5.2 Event Types

```python
class EventType(Enum):
    # Combat
    ATTACK_PERFORMED = "attack_performed"
    DAMAGE_TAKEN = "damage_taken"
    ENEMY_KILLED = "enemy_killed"
    PLAYER_DEATH = "player_death"
    DODGE_PERFORMED = "dodge_performed"
    STATUS_APPLIED = "status_applied"
    # Gathering
    RESOURCE_GATHERED = "resource_gathered"
    NODE_DEPLETED = "node_depleted"
    # Crafting
    CRAFT_ATTEMPTED = "craft_attempted"
    ITEM_INVENTED = "item_invented"
    RECIPE_DISCOVERED = "recipe_discovered"
    # Economy
    ITEM_ACQUIRED = "item_acquired"
    ITEM_CONSUMED = "item_consumed"
    ITEM_EQUIPPED = "item_equipped"
    TRADE_COMPLETED = "trade_completed"
    # Progression
    LEVEL_UP = "level_up"
    SKILL_LEARNED = "skill_learned"
    SKILL_USED = "skill_used"
    TITLE_EARNED = "title_earned"
    CLASS_CHANGED = "class_changed"
    # Exploration
    CHUNK_ENTERED = "chunk_entered"
    LANDMARK_DISCOVERED = "landmark_discovered"
    # Social
    NPC_INTERACTION = "npc_interaction"
    QUEST_ACCEPTED = "quest_accepted"
    QUEST_COMPLETED = "quest_completed"
    QUEST_FAILED = "quest_failed"
    # System
    WORLD_EVENT = "world_event"
    POSITION_SAMPLE = "position_sample"  # Periodic breadcrumb (~10s)
```

## 5.3 The EventRecorder

Subscribes to GameEventBus, converts events, enriches with geographic context, writes to Raw Event Pipeline SQLite:

```python
class EventRecorder:
    """Bus subscriber → SQLite writer. Singleton."""
    def __init__(self):
        self.event_store: EventStore = None
        self.geo_registry: GeographicRegistry = None
        self.entity_registry: EntityRegistry = None
        self.trigger_manager: TriggerManager = None
        self._threshold_set = {1, 3, 5, 10, 25, 50, 100, 250, 500, 1000, 2500, 5000, 10000}

    def _on_bus_event(self, event):
        if not self._should_record(event): return
        memory_event = self._convert_event(event)
        self._enrich_geographic(memory_event)   # Stamp locality/district/province
        self._build_event_tags(memory_event)    # Auto-tag (see §9)
        self._update_occurrence_count(memory_event)
        self.event_store.record(memory_event)
        self._update_activity_logs(memory_event)
        # Check triggers (dual-track)
        actions = self.trigger_manager.on_event(memory_event)
        for action in actions:
            self._notify_interpreter(action)
```

### Bus-to-Memory Event Mapping

| Bus Event | Memory Type | Key Data |
|-----------|-----------|----------|
| `DAMAGE_DEALT` | `attack_performed` | amount, damage_type, target, is_crit, weapon |
| `ENEMY_KILLED` | `enemy_killed` | enemy_id, tier, position, loot |
| `RESOURCE_GATHERED` | `resource_gathered` | resource_id, quantity, tool, position |
| `ITEM_CRAFTED` | `craft_attempted` | recipe_id, quality, discipline, success |
| `SKILL_ACTIVATED` | `skill_used` | skill_id, tags, mana_cost |
| `LEVEL_UP` | `level_up` | new_level, stat_points |

Events not yet published (need minimal hooks): `QUEST_ACCEPTED/COMPLETED`, `NPC_INTERACTION`, `CHUNK_ENTERED`, `TRADE_COMPLETED`.

## 5.4 Retention Policy — Milestone Preservation

For each `(actor_id, event_type, event_subtype)`:

**Always keep**:
1. First occurrence (historical baseline)
2. Threshold-indexed events (1st, 3rd, 5th, 10th, 25th, 50th, 100th...)
3. Power-of-10 milestones (100th, 1000th, 10000th)
4. Events that triggered interpretations
5. Events referenced by Layer 2 cause chains
6. One event per game-day (timeline markers)

**Prune everything else** after configurable age threshold (~50 game-time units).

Example: 10,000 oak logs → keep ~200 events (first, thresholds, milestones, timeline markers) = ~2% retention with full temporal coverage.

## 5.5 Position Sampling

Player position sampled every ~10 real seconds as `POSITION_SAMPLE` events. Includes health_pct, velocity, is_sprinting. Creates a breadcrumb trail for exploration analysis.

---

# 6. Interpreter & Evaluators (Layers 2-3)

## 6.1 Design Philosophy

1. **More evaluators is better** — Each covers a narrow domain. Overlap is expected.
2. **Dual coverage is expected** — Killing 50 wolves fires both PopulationDynamics AND CombatProficiency. Different angles, different narratives.
3. **Context prevents misclassification** — Each evaluator sees the trigger event AND surrounding context.
4. **Templates first, LLM when needed** — Layer 2-3 evaluators use templates or tiny LLMs. Only higher layers justify larger models.
5. **Every evaluator can return None** — "Not interesting enough" is a valid result.

## 6.2 Layer 2 Evaluators (9 Designed → 33 Implemented)

> **Implementation status (2026-04-10):** The 9 conceptual evaluators expanded into 33 concrete evaluators covering finer-grained domains. See `world_system/world_memory/evaluators/` for all files. LLM narration via WmsAI is operational — the LLM assigns `significance` tags via structured JSON output. Debug warnings log when the LLM returns no tags.

### 1. Population Dynamics
- **Question**: Are creature populations changing?
- **Triggers on**: `enemy_killed` thresholds per species per locality
- **Examples**: "Wolf population declining in Whispering Woods (23 killed, 5 game-days)" / "Spider infestation growing in Old Mine (spawn rate exceeds kills)"
- **Nuance**: Weighs tier (T3 kill counts less but matters more), compares kill rate to estimated respawn

### 2. Ecosystem Pressure
- **Question**: Are resources being consumed faster than they regenerate?
- **Triggers on**: `resource_gathered`, `node_depleted` thresholds
- **Examples**: "Iron deposits strained in Iron Hills (gathering rate 2x respawn)" / "Herb meadow nearly depleted at Riverside"
- **Nuance**: Tracks sustainability, correlates depletion across resource types

### 3. Combat Proficiency
- **Question**: How is combat activity evolving?
- **Triggers on**: `attack_performed`, `enemy_killed`, `damage_taken`, `player_death`
- **Examples**: "Prolific hunter active in Eastern Highlands" / "Dangerous area: 3 deaths near Dark Cave in 2 days"
- **Nuance**: Full combat picture (kills, near-deaths, flawless victories, weapon variety)

### 4. Crafting Mastery
- **Question**: What crafting patterns are emerging?
- **Triggers on**: `craft_attempted`, `item_invented`, `recipe_discovered`
- **Examples**: "Emerging smithing specialization (80% of crafts)" / "Quality improving: 3 masterwork items this week"
- **Nuance**: Tracks quality distribution over time, discipline focus, invention patterns

### 5. Player Milestones
- **Question**: Has the player achieved something worth narrating?
- **Triggers on**: `level_up`, `title_earned`, `class_changed`, first occurrences
- **Examples**: "Reached Level 10" / "Earned title: Journeyman Smith"
- **Narrow scope**: Only progression events. Combat/crafting milestones belong to their own evaluators.

### 6. Exploration & Discovery
- **Question**: How is the player engaging with geography?
- **Triggers on**: `chunk_entered`, `landmark_discovered`
- **Examples**: "Discovered the Northern Pines" / "Eastern forest abandoned (no visits in 14 days)"

### 7. Social & Reputation
- **Question**: How is the player interacting with NPCs and factions?
- **Triggers on**: `npc_interaction`, `quest_completed`, `quest_failed`
- **Examples**: "Frequent visitor to Gareth's forge" / "3 quests completed for Miners Guild this week"

### 8. Economy & Items
- **Question**: How are goods flowing?
- **Triggers on**: `trade_completed`, `item_equipped`, `item_consumed`
- **Examples**: "Actively trading iron goods at market" / "Hoarding rare materials (5 T3 items unsold)"

### 9. Dungeon Progress
- **Question**: How is the player performing in dungeon content?
- **Triggers on**: `dungeon_entered`, `dungeon_completed`, enemy kills in dungeon localities
- **Examples**: "Cleared Iron Mine dungeon (no deaths)" / "Struggling with cave encounters (2 deaths)"

## 6.3 Layer 3 Consolidators (4 Total) — IMPLEMENTED

> **Implementation status (2026-04-10):** All 4 consolidators built and operational. Layer 3 uses a new `ConsolidatorBase` ABC (not `PatternEvaluator`) because consolidators take multiple L2 events as input rather than a single trigger event. Orchestrated by `Layer3Manager` singleton which triggers every 15 L2 events (configurable in `memory-config.json`). Prompt fragments stored separately in `prompt_fragments_l3.json`.

Layer 3 reads Layer 2 interpretations (full) and Raw Event Pipeline events (limited/summary). Triggers when a district accumulates 3+ Layer 2 interpretations or 2+ from different categories.

**Key files:**
- `world_system/world_memory/consolidator_base.py` (166 lines) — ConsolidatorBase ABC, XML data block builder
- `world_system/world_memory/layer3_manager.py` (422 lines) — Layer3Manager singleton, trigger/orchestration
- `world_system/world_memory/consolidators/` — 4 consolidator implementations
- `world_system/config/prompt_fragments_l3.json` — Layer 3 prompt fragments (separate from L2)
- `world_system/world_memory/game_date.py` (106 lines) — game_time → game_day conversion, relative date formatting

**ConsolidatorBase interface** (differs from PatternEvaluator):
```python
class ConsolidatorBase(ABC):
    def is_applicable(self, l2_events, district_id) -> bool: ...
    def consolidate(self, l2_events, district_id, geo_context, game_time) -> Optional[ConsolidatedEvent]: ...
```

**Trigger mechanism:** Layer3Manager counts L2 events via a callback from `interpreter.on_trigger()`. Every 15 L2 events, `WorldMemorySystem.update()` calls `run_consolidation()` which queries LayerStore for each district with new L2 data and runs all applicable consolidators.

**LLM tag assignment:** The LLM assigns Layer 3 interpretive tags (sentiment, trend, intensity, population_status, resource_status, setting, terrain) via structured JSON output. Consolidators provide template tags as fallback when no LLM is available. Geographic/structural tags (district, consolidator, scope) remain procedural. Debug warnings log when the LLM returns no tags.

**Tag enrichment:** Uses existing `HigherLayerTagAssigner` from `tag_assignment.py` — inherits L2 tags, removes old significance, merges LLM/consolidator tags.

**Date stamps:** All LayerStore events (L2-L7) carry a `game_day` column computed from `game_time / 1440.0`. Relative dates formatted as "X months and Y days ago" for higher-layer LLM consumption. Replaces the designed-but-unbuilt 3-tier temporal storage system.

### 1. Regional Activity Synthesizer (`regional_synthesis`)
- **Scope**: Per WMS district (= game region)
- **Reads**: All Layer 2 interpretations for the district, grouped by locality
- **Produces**: "The Western Frontier shows heavy resource extraction in Iron Hills and moderate combat in Whispering Woods."
- **Applicability**: District has 3+ L2 events OR 2+ from different categories

### 2. Cross-Domain Pattern Detector (`cross_domain`)
- **Scope**: Per WMS district
- **Reads**: Layer 2 interpretations from different domains in the same district
- **Produces**: "Deep Mine shows combat and resource extraction in tandem, suggesting intensive exploitation."
- **Applicability**: District has 2+ domains represented. Detects co-location across domains.

### 3. Player Identity Consolidator (`player_identity`)
- **Scope**: Global (all L2 events regardless of location)
- **Reads**: All recent Layer 2 interpretations about the player
- **Produces**: "The player is primarily a melee combatant with growing smithing expertise, focused on western regions."
- **Applicability**: 5+ total L2 events exist. Skips district-scoped calls.

### 4. Faction Narrative Synthesizer (`faction_narrative`)
- **Scope**: Global (per-faction across all districts)
- **Reads**: Social, economy, and combat L2 events with faction-relevant tags
- **Produces**: "The player has positive engagement with the Warriors Guild through quest completion."
- **Applicability**: 3+ faction-relevant L2 events. Detects faction affiliation from NPC tags and narrative keywords.

## 6.4 Evaluator Visibility Rules

| Evaluator Layer | Can See (Full) | Can See (Limited) | Cannot See |
|:-:|:-:|:-:|:-:|
| Layer 2 | Raw Event Pipeline events | Layer 1 stats | Layers 3-7 |
| Layer 3 | Layer 2 interpretations | Raw Event Pipeline events | Layers 4-7 |
| Layer 4 | Layer 3 consolidated | Layer 2 interpretations | Layers 5-7 |

## 6.5 Dual Coverage Map

The same event type can trigger multiple evaluators:

| Event | PopDyn | EcoPres | Combat | Craft | Mile | Explor | Social | Econ | Dungeon |
|-------|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| enemy_killed | X | | X | | | | | | X |
| resource_gathered | | X | | | | | | X | |
| craft_attempted | | | | X | | | | X | |
| level_up | | | | | X | | | | |
| quest_completed | | | | | X | | X | | |
| trade_completed | | | | | | | X | X | |
| chunk_entered | | | | | | X | | | |

---

# 7. Aggregation & World State (Layers 3-7)

## 7.1 Layer 3: Municipality/Local Consolidation — IMPLEMENTED

Each district maintains consolidated interpretations — cross-domain patterns detected by Layer 3 consolidators. Stored in LayerStore `layer3_events` + `layer3_tags`.

```python
@dataclass
class ConsolidatedEvent:
    """Implemented in event_schema.py. Maps to layer3_events table."""
    consolidation_id: str
    created_at: float                 # game_time
    narrative: str                    # "Heavy combat AND resource depletion suggest..."
    category: str                     # "regional_synthesis", "cross_domain", "player_identity", "faction_narrative"
    severity: str                     # "minor"..."critical"
    source_interpretation_ids: List[str]  # Layer 2 event IDs that fed this
    affected_district_ids: List[str]
    affected_province_ids: List[str]
    affects_tags: List[str]           # Inherited from L2 + LLM-assigned L3 tags
    supersedes_id: Optional[str]      # Previous consolidation for same district+category
    update_count: int
```

**Data flow:**
```
Layer 2 event stored → interpreter notifies Layer3Manager
    → counter increments (every 15 L2 events triggers run)
    → WorldMemorySystem.update() calls run_consolidation()
        → query LayerStore for L2 events per district
        → run all 4 consolidators (is_applicable → consolidate)
        → LLM upgrade (narrative + tag assignment via JSON)
        → tag enrichment (HigherLayerTagAssigner)
        → store in layer3_events + layer3_tags
```

## 7.2 Layer 4: Smaller Region Events (IMPLEMENTED)

Per-province gross summaries. WMS PROVINCE = game Region (`region_X`). Each province has its own `WeightedTriggerBucket` (`layer4_province_{province_id}`), created lazily. Tags accumulate independently per province — no cross-province contamination.

```python
@dataclass
class ProvinceSummaryEvent:
    summary_id: str
    province_id: str                  # e.g. "region_1" (WMS PROVINCE = game Region)
    created_at: float
    narrative: str                    # "Iron Reaches: heavy mining, moderate combat, iron scarcity spreading"
    severity: str                     # minor...critical
    dominant_activities: List[str]    # ["mining", "combat"]
    threat_level: str                 # "low"..."critical"
    source_consolidation_ids: List[str]  # L3 event IDs that fed this
    relevant_l2_ids: List[str]       # High-relevance L2 event IDs
    tags: List[str]                  # Full tag list (LLM-rewritten at this layer)
    supersedes_id: Optional[str]     # Previous summary for same province
```

**Trigger mechanism**: Per-province tag-weighted via `WeightedTriggerBucket`. Geographic tags (`province:`, `district:`, `locality:`, `nation:`) are stripped before scoring so content tags get full positional weight (e.g. `domain:combat` at position 0 = 10 pts). Scoring: 1st=10, 2nd=8, 3rd=6, 4th=5, 5th=4, 6th=3, 7-12th=2, 13th+=1. When any content tag crosses 50 points within a province, the contributing L3 events are used as context. After firing, all scores/contributors for that tag reset to 0 (recurring trigger, no carryover).

**LLM tag rewrite**: At Layer 4+, the LLM receives all inherited tags as input context and outputs a complete reordered tag list (keeping 66-80% of aggregate tags, reordered by relevance). This enables tag position to carry semantic weight in downstream triggers.

**L2 visibility**: Layer 4 sees L3 (full) and L2 (top-5 tag matching). The top 5 content tags from L3 events (by frequency, geo/structural stripped) form a matching set. L2 events must share at least 3 of the 5. Ranked by: match count (desc) → best matched tag rank (asc, winner-take-all) → recency (desc). At most 5 L2 events returned.

**L3 tag ordering**: Frequency-based (most common across origin L2 events first). Documented in `tag_assignment.py:_merge_origin_tags()` with LLM prompting noted as an alternative.

**Prompt fragments**: `prompt_fragments_l4.json` — aggregates ALL lower-layer fragments (L2+L3+L4) for maximum entity context.

**Storage**: `layer4_events` + `layer4_tags` in LayerStore (append-only, same pattern as L2-L3). The `province_summaries` table in EventStore is dormant.

## 7.3 Layer 5: Larger Region/Country Events

Single row per realm capturing faction power, economic state, player reputation.

```python
@dataclass
class RealmState:
    realm_id: str
    faction_standings: Dict[str, float]   # faction_id → reputation (-1.0 to 1.0)
    economic_summary: str                  # "Trade is active, iron scarce, herbs abundant"
    player_reputation: str                 # "Known as a skilled hunter and capable smith"
    major_events: List[str]               # Recent world-significant narratives
    last_updated: float
```

## 7.4 Layer 6: Intercountry Events

Cross-realm patterns, trade routes, and diplomatic state. Updated on multi-realm events.

```python
@dataclass
class IntercountryState:
    id: str
    narrative: str                       # "Trade tensions between eastern and western realms"
    cross_realm_patterns: List[str]      # Detected patterns spanning realms
    trade_route_state: Dict[str, str]    # route_id → "active"/"disrupted"/"closed"
    diplomatic_state: Dict[str, str]     # realm_pair → "allied"/"neutral"/"hostile"
    last_updated: float
```

## 7.5 Layer 7: World Events & Narrative Threads

The "Heart of Memory" — persistent story elements and world identity.

```python
@dataclass
class WorldNarrative:
    world_themes: List[str]          # ["frontier", "magical_resurgence", "ancient_ruins"]
    world_epoch: str                 # Current era/age
    active_threads: List[str]        # IDs of active NarrativeThreads
    resolved_threads: List[str]      # Historical threads
    world_history: List[str]         # Major events in chronological order

@dataclass
class NarrativeThread:
    thread_id: str
    source: str                      # "npc_rumor", "world_event", "player_action", "developer"
    theme: str                       # "war", "plague", "migration", "discovery"
    summary: str                     # "A war is brewing in the western territories"
    canonical_facts: List[str]       # Facts that ARE true (for NPC consistency)
    unresolved_questions: List[str]  # Things not yet decided
    status: str                      # "rumor", "developing", "active", "resolved", "forgotten"
    significance: float              # 0.0-1.0
    origin_region: str
    spread_radius: float             # How far it has spread (grows over time)
```

### NarrativeThread Lifecycle

1. **Introduction**: NPC mentions "rumors of war to the west" → thread created, status="rumor"
2. **Development**: Player travels west, NPCs provide more detail, questions get resolved
3. **Propagation with Distortion**: Distance from epicenter compresses information quality
4. **Escalation or Decay**: Engaged → significance rises, new content generated. Ignored → decays → "forgotten"

## 7.6 Aggregation Manager

```python
class AggregationManager:
    """Maintains Layers 3-4. Updated when Layer 2 events change. Singleton."""
    def on_interpretation_created(self, interp: InterpretedEvent):
        # Update Layer 3 for affected localities/districts
        for locality_id in interp.affected_locality_ids:
            knowledge = self._get_or_create_local(locality_id)
            knowledge.recent_interpretations.insert(0, interp.interpretation_id)
            if interp.is_ongoing:
                knowledge.ongoing_conditions.append(interp.interpretation_id)
            knowledge.compile_summary()
        # Propagate to Layer 4 if significant
        if interp.severity in ("significant", "major", "critical"):
            for province_id in interp.affected_province_ids:
                self._refresh_province_summary(province_id)
```

---

# 8. Time-Based Tracking & Recency

## 8.1 Daily Ledger

At the end of each game-day, compute a `DailyLedger` — one row summarizing all activity:

```python
@dataclass
class DailyLedger:
    game_day: int
    game_time_start: float; game_time_end: float

    # Combat
    damage_dealt: float; damage_taken: float; enemies_killed: int
    deaths: int; highest_single_hit: float; unique_enemy_types_fought: int
    # Gathering
    resources_gathered: int; unique_resources_gathered: int; nodes_depleted: int
    # Crafting
    items_crafted: int; craft_quality_avg: float; unique_disciplines_used: int
    # Exploration
    chunks_visited: int; new_chunks_discovered: int; distance_traveled: float
    # Social
    npc_interactions: int; quests_completed: int; trades_completed: int
    # Health
    total_healing: float; mana_spent: float; skills_activated: int
    # Meta
    active_playtime: float; primary_activity: str  # "combat"/"gathering"/"crafting"/etc.
```

Computed by querying Raw Event Pipeline events for that day's time range. Stored in `daily_ledgers` SQLite table. **Never pruned** — one row per day is trivial.

## 8.2 Meta-Daily Stats (Streaks & Patterns)

```python
@dataclass
class MetaDailyStats:
    # Current streaks (consecutive days)
    consecutive_combat_days: int; consecutive_peaceful_days: int
    consecutive_crafting_days: int; consecutive_gathering_days: int
    # Records (longest ever)
    longest_combat_streak: int; longest_peaceful_streak: int
    # Day counts
    days_with_heavy_combat: int; days_with_no_combat: int
    days_with_deaths: int; deathless_days: int
    # Single-day records
    most_kills_in_a_day: int; most_damage_in_a_day: float
    most_resources_in_a_day: int; most_crafts_in_a_day: int
    # Rolling averages (last 7 days)
    avg_kills_per_day_7d: float; avg_damage_per_day_7d: float
```

Updated once per game-day from DailyLedger history.

## 8.3 Thresholds for Daily Stats

**Recommended: Hybrid approach**

- **Days 1-6**: Static thresholds (hardcoded reasonable tiers)
  - Combat: quiet(<100 dmg), active(100-500), intense(500-2000), extreme(>2000)
  - Gathering: quiet(<20), active(20-100), intense(100-500), extreme(>500)
- **Days 7-29**: Blend 70% static + 30% dynamic (player percentiles)
- **Days 30+**: Blend 30% static + 70% dynamic

Dynamic thresholds = percentile-based from player's own history (P25/P50/P75/P90). Static floors always enforced.

## 8.4 Time Envelopes

**Problem**: To interpret "100 wolf kills," we need temporal context. But not 100 individual timestamps, and not the average (meaningless).

**Solution**: A compact temporal descriptor:

```python
@dataclass
class TimeEnvelope:
    first_at: float; last_at: float   # Game-time of first/last event
    total_count: int; total_span: float
    last_1_day: int; last_3_days: int; last_7_days: int  # Bucketed counts
    recent_rate: float                 # Events per game-time-unit (last 7 days)
    overall_rate: float                # All time
    trend: str                         # "accelerating", "steady", "decelerating", "burst", "dormant"
```

**Trend detection**:
- `last_7_days == 0` → "dormant"
- `last_1_day > last_7_days/7 * 2` → "accelerating"
- `last_1_day < last_7_days/7 * 0.3` → "decelerating"
- `last_1_day > total_count * 0.3` → "burst"
- else → "steady"

**Recency severity modifier**: Interpreters weight severity by trend:
- burst → 2.0x, accelerating → 1.5x, steady → 1.0x, decelerating → 0.8x, dormant → 0.5x

**Interpreter receives**: Trigger event + TimeEnvelope → enables temporal awareness in narrative:
- "Wolf hunting has been **steady** in the Whispering Woods, with 100 killed over 44 days."
- vs. "A **sudden spike** in wolf kills — nearly all 100 occurred in the past few days."

---

# 9. Tagging Strategy

## 9.1 Layer 1 Tagging (Stat Tracker — Implicit)

stat_tracker.py uses nested dict keys as implicit categories. A static lookup bridges to tag format:

```python
STAT_KEY_TO_TAGS = {
    "combat_stats.wolf_kills": ["event:combat", "species:wolf"],
    "gathering_stats.iron_ore": ["event:gathering", "resource:iron"],
    "crafting_stats.smithing_attempts": ["event:crafting", "domain:smithing"],
}
```

**No changes to stat_tracker.py.** This mapping lives in the query layer.

## 9.2 Raw Event Pipeline Tagging (Auto-Generated from Event Data)

Every Raw Event Pipeline event gets tags auto-generated at recording time via a **field-to-tag derivation map**:

```python
# Always: event type tag
tags = [f"event:{event.event_type}"]

# Data-driven field-to-tag mapping
FIELD_TAG_MAP = {
    "resource_type": "resource:",   # → "resource:iron"
    "material_id":   "resource:",   # → "resource:oak_log"
    "enemy_type":    "species:",    # → "species:wolf"
    "weapon_type":   "combat:",     # → "combat:melee"
    "damage_type":   "element:",    # → "element:fire"
    "discipline":    "domain:",     # → "domain:smithing"
    "biome":         "biome:",      # → "biome:forest"
    "tier":          "tier:",       # → "tier:2"
    "npc_id":        "npc:",        # → "npc:gareth"
    "quest_id":      "quest:",      # → "quest:wolf_bounty"
}
```

### Derived Tags (Computed)

```python
# Location tags (from geographic enrichment)
if event.locality_id: tags.append(f"location:{event.locality_id}")
if event.district_id: tags.append(f"location:{event.district_id}")

# Intensity (magnitude relative to tier baseline)
tier_baseline = {1: 10, 2: 25, 3: 60, 4: 150}
ratio = event.magnitude / tier_baseline.get(event.tier or 1, 10)
if ratio > 3.0:   tags.append("intensity:extreme")
elif ratio > 1.5: tags.append("intensity:heavy")
elif ratio > 0.5: tags.append("intensity:moderate")
else:              tags.append("intensity:light")

# Result tags
if event.result == "critical": tags.append("combat:critical")
if event.quality: tags.append(f"quality:{event.quality}")
```

### Complete Example: Wolf Kill Event

```python
# Bus: ENEMY_KILLED, data={enemy_type: "wolf", tier: 1, weapon_type: "melee", biome: "forest"}
tags = [
    "event:enemy_killed", "species:wolf", "combat:melee", "element:physical",
    "biome:forest", "tier:1", "location:whispering_woods", "location:eastern_province",
    "intensity:moderate"
]
```

## 9.3 Layer 2 Tagging (Inherited + Derived)

**Inherited** from cause events (Raw Event Pipeline):
```python
KEEP_CATEGORIES = {"species", "resource", "biome", "location", "domain", "element", "tier", "combat"}
inherited = [t for t in all_cause_tags if t.split(":")[0] in KEEP_CATEGORIES]
```

**Derived** from interpretation properties:
```python
tags.append(f"interpretation:{interp.category}")   # "interpretation:population_change"
tags.append(f"severity:{interp.severity}")          # "severity:major"
if envelope: tags.append(f"trend:{envelope.trend}") # "trend:accelerating"
# Timeframe
if envelope.total_span < 3.0:  tags.append("timeframe:recent")
elif envelope.total_span < 14: tags.append("timeframe:ongoing")
else:                          tags.append("timeframe:historical")
# Scope
if region_count <= 1:  tags.append("scope:local")
elif region_count <= 5: tags.append("scope:district")
else:                   tags.append("scope:regional")
```

## 9.4 Similarity Grouping for Threshold Counting

The trigger system (§2) needs to count "similar" interpretations for Layer 2→3 escalation:

```python
def get_similarity_key(interp) -> Tuple[str, str, str]:
    primary_tag = next((t for t in interp.affects_tags
                        if t.split(":")[0] in ("species", "resource", "domain")), "general")
    primary_region = interp.affected_locality_ids[0] if interp.affected_locality_ids else "global"
    return (interp.category, primary_tag, primary_region)
```

Example: Three wolf-related interpretations in Whispering Woods → key `(population_change, species:wolf, whispering_woods)` → count=3 → threshold hit → Layer 3 triggered.

## 9.5 Tag Lifecycle

```
GameEventBus      → No tags
Layer 1 (Stats)   → Implicit (stat key structure)
Raw Event Pipeline → AUTO-TAGGED from fields + derived (location, intensity, quality)
Layer 2 (Interp)  → INHERITED from Raw Event Pipeline + DERIVED (category, severity, trend, scope)
Layer 3 (Consol)  → Tags from constituent Layer 2 interpretations
Layers 4-7        → Tags from notable lower-layer events
```

---

# 10. Retrieval Design

## 10.1 Three Retrieval Pathways

| Pathway | Source | Speed | Use Case |
|---------|--------|-------|----------|
| **Fast Path** | Layer 1 (stat_tracker) | Microseconds | "How many wolves killed total?" |
| **Narrative Path** | Layers 2-4 (interpretations) | Milliseconds | "What's happening near the blacksmith?" |
| **Detail Path** | Raw Event Pipeline (raw events) | Milliseconds | Evaluators needing evidence |

## 10.2 Entity-First Query Architecture

**The primary query method**: Start from the entity, radiate outward.

```python
class WorldQuery:
    """Entity-first query interface. Singleton."""

    def query_entity(self, entity_id: str, window: EventWindow = None,
                     current_game_time: float = 0.0) -> EntityQueryResult:
        entity = self.entity_registry.get(entity_id)

        # 1. Entity metadata (name, tags, position, home_region)
        metadata = {...}

        # 2. Direct activity (events involving this entity, dual-windowed)
        direct_events = self._get_entity_activity(entity, window, current_game_time)

        # 3. Nearby events filtered by interest tags (relevance > 0.2)
        nearby_events = self._get_nearby_relevant_events(entity, window, current_game_time)

        # 4. Local knowledge (Layer 3 summary for home locality)
        local_context = self._get_local_context(entity)

        # 5. Regional knowledge (Layer 4 summary for province)
        regional_context = self._get_regional_context(entity)

        # 6. Ongoing conditions matching entity's tags (relevance > 0.3)
        ongoing = self._get_ongoing_conditions(entity)

        return EntityQueryResult(metadata, direct_events, nearby_events,
                                 local_context, regional_context, ongoing)
```

### The Dual Window System

Two windows that work together:
- **Static Window**: Fixed event count (e.g., 10). Guarantees minimum context.
- **Recency Window**: Time-based (e.g., last 5 game-time units). Captures all recent activity.
- If recency < static → backfill from history. If recency > static → include ALL recent.

| Context | Static | Recency | Rationale |
|---------|--------|---------|-----------|
| NPC awareness | 10 | 5.0 | Recent events + some history |
| Region summary | 15 | 10.0 | Broader context |
| Player activity | 8 | 3.0 | What just happened |
| Full history | 20 | 20.0 | Deep query |
| Quick check | 5 | 2.0 | Fast relevance scan |

## 10.3 What Each Consumer Gets

### Context Budget: NPC Dialogue Consumer (~500 tokens)
What the WMS provides when a consumer calls `query_entity(npc_id)`:
1. NPC personality + role (from entity tags) — ~50 tokens
2. Recent interactions with player (from activity log) — ~100 tokens
3. Local knowledge summary (Layer 3) — ~100 tokens
4. Relevant ongoing conditions (tag-filtered) — ~100 tokens
5. Regional context (Layer 4, if notable) — ~50 tokens
6. Gossip (distance-filtered interpretations) — ~100 tokens

### Context Budget: Quest Generation Consumer (~1000 tokens)
All of the above plus: player profile, resource state, active narrative threads, faction standings.

### Context Budget: Content Generation Consumer (~500 tokens)
Regional themes, active threads, player level/needs, scarcity data.

## 10.4 Distance-Based Information Quality

NPCs closer to events know more detail:

| Distance | Detail Level | Example |
|----------|-------------|---------|
| <16 tiles (same locality) | Full detail | "The Ironhold dwarves attacked Millhaven. They want the iron mines." |
| <48 tiles (same district) | Summary (first sentence) | "I heard dwarves are fighting humans over mining rights." |
| <100 tiles (same province) | Vague rumor | "Something about trouble with dwarves?" |
| >100 tiles | Nothing (or bare mention if significance > 0.8) | — |

This is NOT lying — it's **information compression and uncertainty**. An NPC 50 chunks away doesn't know details.

## 10.5 Gossip Propagation (Write-Time)

When a Layer 2+ interpretation is created, it's pushed to nearby NPC memory with distance-based delays:

| Distance | Delay | Detail Level |
|----------|-------|-------------|
| Same locality | 60s | Full narrative |
| Adjacent district | 180s | Condensed |
| Same province | 420s | Rumor |
| Cross-province | 24h+ | Only if severity ≥ "major" |

Stored in `npc_memory.knowledge_json` for retrieval by consumer systems (e.g., dialogue generation).

## 10.6 Convenience Query Methods

```python
# Query a region as an entity
world_query.query_location("whispering_woods", window, time)

# Fast Layer 1 lookup
world_query.query_player_stat("combat_stats.wolf_kills")

# Raw Event Pipeline spatial query
world_query.query_events_in_area(x, y, radius, window, tag_filter=["species:wolf"])

# Direct Layer 2 query
world_query.query_interpretations(category="population_change", severity_min="moderate")
```

---

# 11. Storage Schema

All Raw Event Pipeline through Layer 7 data lives in a single SQLite database per save file.

## 11.1 Raw Event Pipeline: Raw Events

```sql
CREATE TABLE events (
    event_id TEXT PRIMARY KEY,
    event_type TEXT NOT NULL, event_subtype TEXT NOT NULL,
    actor_id TEXT NOT NULL, actor_type TEXT NOT NULL,
    target_id TEXT, target_type TEXT,
    position_x REAL NOT NULL, position_y REAL NOT NULL,
    chunk_x INTEGER NOT NULL, chunk_y INTEGER NOT NULL,
    locality_id TEXT, district_id TEXT, province_id TEXT, biome TEXT,
    game_time REAL NOT NULL, real_time REAL NOT NULL, session_id TEXT,
    magnitude REAL DEFAULT 0.0, result TEXT DEFAULT 'success',
    quality TEXT, tier INTEGER,
    context_json TEXT DEFAULT '{}',
    interpretation_count INTEGER DEFAULT 0,
    triggered_interpretation INTEGER DEFAULT 0
);
-- Indexes: event_type, (event_type,event_subtype), actor_id, target_id, game_time,
--          locality_id, district_id, (chunk_x,chunk_y), triggered_interpretation

CREATE TABLE event_tags (
    event_id TEXT NOT NULL, tag TEXT NOT NULL,
    FOREIGN KEY (event_id) REFERENCES events(event_id) ON DELETE CASCADE
);
CREATE INDEX idx_event_tags_tag ON event_tags(tag);

CREATE TABLE occurrence_counts (
    actor_id TEXT NOT NULL, event_type TEXT NOT NULL, event_subtype TEXT NOT NULL,
    count INTEGER DEFAULT 0,
    PRIMARY KEY (actor_id, event_type, event_subtype)
);
```

## 11.2 Layer 2: Interpretations

```sql
CREATE TABLE interpretations (
    interpretation_id TEXT PRIMARY KEY,
    created_at REAL NOT NULL,
    narrative TEXT NOT NULL, category TEXT NOT NULL, severity TEXT NOT NULL,
    trigger_event_id TEXT, trigger_count INTEGER,
    cause_event_ids_json TEXT DEFAULT '[]',
    affected_locality_ids_json TEXT DEFAULT '[]',
    affected_district_ids_json TEXT DEFAULT '[]',
    affected_province_ids_json TEXT DEFAULT '[]',
    epicenter_x REAL, epicenter_y REAL,
    affects_tags_json TEXT DEFAULT '[]',
    is_ongoing INTEGER DEFAULT 0, expires_at REAL,
    supersedes_id TEXT, update_count INTEGER DEFAULT 1,
    archived INTEGER DEFAULT 0
);
CREATE TABLE interpretation_tags (
    interpretation_id TEXT NOT NULL, tag TEXT NOT NULL,
    FOREIGN KEY (interpretation_id) REFERENCES interpretations(interpretation_id) ON DELETE CASCADE
);
```

## 11.3 Layer 3: Municipality/Local Consolidation

```sql
CREATE TABLE connected_interpretations (
    id TEXT PRIMARY KEY, created_at REAL NOT NULL,
    narrative TEXT NOT NULL, category TEXT NOT NULL, severity TEXT NOT NULL,
    source_interpretation_ids_json TEXT DEFAULT '[]',
    affected_district_ids_json TEXT DEFAULT '[]',
    affects_tags_json TEXT DEFAULT '[]',
    is_ongoing INTEGER DEFAULT 0, expires_at REAL, archived INTEGER DEFAULT 0
);
CREATE TABLE connected_interpretation_tags (
    id TEXT NOT NULL, tag TEXT NOT NULL,
    FOREIGN KEY (id) REFERENCES connected_interpretations(id) ON DELETE CASCADE
);
```

## 11.4 Layer 4: Smaller Region Events

```sql
CREATE TABLE province_summaries (
    province_id TEXT PRIMARY KEY,
    summary_text TEXT DEFAULT '',
    dominant_activities_json TEXT DEFAULT '[]',
    notable_event_ids_json TEXT DEFAULT '[]',
    resource_state_json TEXT DEFAULT '{}',
    threat_level TEXT DEFAULT 'low',
    last_updated REAL DEFAULT 0.0
);
```

## 11.5 Layer 5: Larger Region/Country Events

```sql
CREATE TABLE realm_state (
    realm_id TEXT PRIMARY KEY,
    faction_standings_json TEXT DEFAULT '{}',
    economic_summary TEXT DEFAULT '',
    player_reputation TEXT DEFAULT '',
    major_events_json TEXT DEFAULT '[]',
    last_updated REAL DEFAULT 0.0
);
```

## 11.6 Layer 6: Intercountry Events

```sql
CREATE TABLE intercountry_state (
    id TEXT PRIMARY KEY,
    narrative TEXT DEFAULT '',
    cross_realm_patterns_json TEXT DEFAULT '[]',
    trade_route_state_json TEXT DEFAULT '{}',
    diplomatic_state_json TEXT DEFAULT '{}',
    last_updated REAL DEFAULT 0.0
);
```

## 11.7 Layer 7: World Events

```sql
CREATE TABLE world_narrative (
    id TEXT PRIMARY KEY DEFAULT 'singleton',
    world_themes_json TEXT DEFAULT '[]',
    world_epoch TEXT DEFAULT 'unknown',
    active_thread_ids_json TEXT DEFAULT '[]',
    resolved_thread_ids_json TEXT DEFAULT '[]',
    world_history_json TEXT DEFAULT '[]',
    last_updated REAL DEFAULT 0.0
);

CREATE TABLE narrative_threads (
    thread_id TEXT PRIMARY KEY, source TEXT NOT NULL,
    theme TEXT NOT NULL, summary TEXT NOT NULL,
    canonical_facts_json TEXT DEFAULT '[]',
    unresolved_questions_json TEXT DEFAULT '[]',
    status TEXT DEFAULT 'rumor', significance REAL DEFAULT 0.0,
    origin_region TEXT, spread_radius REAL DEFAULT 0.0,
    created_at REAL NOT NULL, last_referenced REAL,
    generation_hints_json TEXT DEFAULT '{}'
);
```

## 11.8 Supporting Tables

```sql
CREATE TABLE entity_state (
    entity_id TEXT PRIMARY KEY,
    tags_json TEXT DEFAULT '[]', activity_log_json TEXT DEFAULT '[]',
    state_json TEXT DEFAULT '{}'
);

CREATE TABLE region_state (
    region_id TEXT PRIMARY KEY,
    active_conditions_json TEXT DEFAULT '[]', recent_events_json TEXT DEFAULT '[]',
    summary_text TEXT DEFAULT '', last_updated REAL DEFAULT 0.0
);

CREATE TABLE daily_ledgers (
    game_day INTEGER PRIMARY KEY,
    game_time_start REAL, game_time_end REAL,
    data_json TEXT NOT NULL
);

CREATE TABLE meta_daily_stats (
    stat_key TEXT PRIMARY KEY, data_json TEXT NOT NULL
);

CREATE TABLE regional_counters (
    region_id TEXT NOT NULL, event_category TEXT NOT NULL, count INTEGER DEFAULT 0,
    PRIMARY KEY (region_id, event_category)
);

CREATE TABLE interpretation_counters (
    category TEXT NOT NULL, primary_tag TEXT NOT NULL, region_id TEXT NOT NULL,
    count INTEGER DEFAULT 0,
    PRIMARY KEY (category, primary_tag, region_id)
);

-- NPC memory (from Living World AI)
CREATE TABLE npc_memory (
    npc_id TEXT PRIMARY KEY,
    interactions_json TEXT DEFAULT '[]', knowledge_json TEXT DEFAULT '[]',
    relationship_score REAL DEFAULT 0.0, last_interaction REAL
);

-- Faction state
CREATE TABLE faction_state (
    faction_id TEXT PRIMARY KEY,
    reputation REAL DEFAULT 0.0, tier TEXT DEFAULT 'neutral',
    milestone_log_json TEXT DEFAULT '[]', last_updated REAL DEFAULT 0.0
);

-- Biome resources
CREATE TABLE biome_resources (
    biome TEXT NOT NULL, resource_type TEXT NOT NULL,
    current_level REAL DEFAULT 1.0, regen_rate REAL DEFAULT 0.01,
    last_updated REAL DEFAULT 0.0,
    PRIMARY KEY (biome, resource_type)
);
```

## 11.9 Data Flow Summary

```
Player Action → EventBus
    ├→ stat_tracker (Layer 1) — cumulative counters
    └→ EventRecorder (Raw Event Pipeline) — SQLite: events + event_tags + occurrence_counts
        └→ TriggerManager checks thresholds
            └→ Layer 2 evaluators → interpretations + interpretation_tags
                └→ Layer 3 consolidators → connected_interpretations
                    └→ Layer 4 → province_summaries
                        └→ Layer 5 → realm_state
                            └→ Layer 6 → intercountry_state
                                └→ Layer 7 → world_narrative + narrative_threads
```

---

# 12. Consumer Systems (External to World Memory)

> **IMPORTANT**: The systems below are **consumers** of the World Memory System, NOT part of it.
> They live in `world_system/living_world/` for organizational convenience, but they are architecturally
> separate. The World Memory System (Layer 1, Raw Event Pipeline, and Layers 2-7) collects, interprets, and serves data.
> Consumer systems READ that data and take outgoing actions (dialogue, reputation changes, etc.).
> The boundary: **World Memory writes information state. Consumers write game state.**

## 12.1 Architecture

```
                     ┌─────────────────────────────────────────┐
                     │         WORLD MEMORY SYSTEM             │
                     │     (Data Collection & Interpretation)   │
GameEventBus ──→     │  EventRecorder → SQLite (Raw Event Pipeline) │
                     │  Evaluators → Interpretations (Layer 2+)    │
                     │  WorldQuery → EntityQueryResult (reads)  │
                     └──────────────┬──────────────────────────┘
                                    │ READS
                     ┌──────────────▼──────────────────────────┐
                     │         CONSUMER SYSTEMS                 │
                     │     (Outgoing Actions & Decisions)       │
                     │  BackendManager (LLM routing)            │
                     │  NPC Dialogue (uses memory as context)   │
                     │  Faction System (reputation decisions)   │
                     │  Ecosystem Agent (resource lifecycle)    │
                     └──────────────────────────────────────────┘
```

## 12.2 What World Memory Provides to Consumers

The World Memory System provides **context and state** that consumer systems use:

| Consumer | What WMS Provides | What the Consumer Does (NOT WMS) |
|----------|-------------------|----------------------------------|
| NPC Dialogue | NPCMemory (knowledge, relationship, emotion), EntityQueryResult, gossip | Generates dialogue text via LLM |
| Faction System | Event history (kills, quests, crafting) | Decides reputation changes, applies ripple |
| Ecosystem Agent | Resource gathering counts per biome | Manages regeneration, scarcity thresholds |
| Quest Generator | Player profile, regional state, scarcity | Creates quest objectives and rewards |

## 12.3 NPC Memory (WMS-Owned Data)

The World Memory System owns and manages NPC memory state:

```python
@dataclass
class NPCMemory:
    npc_id: str
    interactions: List[Dict]          # Recent player interactions
    knowledge: List[Dict]             # Gossip + local awareness (from propagation)
    relationship_score: float         # -1.0 to 1.0 with player
    last_interaction: float
```

**Gossip propagation** is a write-time WMS operation: when Layer 2+ interpretations are created, they're pushed to nearby NPC memory with distance-based delays (60s local, 180s district, 420s province). NPCs only receive gossip matching their interest tags (relevance > 0.2). This data is stored — how it's used for dialogue is a consumer concern.

### 6 Personality Archetypes (Reference for Consumers)

| Archetype | Style | Focus |
|-----------|-------|-------|
| Mentor | Wise, measured | Progression, skills |
| Merchant | Transactional, practical | Economy, trade |
| Guardian | Protective, alert | Safety, threats |
| Gossip | Social, exaggerating | Rumors, social events |
| Scholar | Analytical, precise | Knowledge, discovery |
| Recluse | Brief, wary | Minimal interaction |

## 12.4 Faction State (WMS-Owned Data)

The World Memory System tracks faction reputation as information state:

- 4 factions with reputation scale: Hostile → Unfriendly → Neutral → Friendly → Allied → Exalted
- Reputation history with reasons and timestamps
- Milestone thresholds (0.25, 0.5, 0.75) tracked for consumer use

### Ripple Mechanics (Faction System Consumer Logic)

When reputation changes with one faction, allied/hostile factions feel it:
```
Player gains +10 rep with Miners Guild
  → Merchants Alliance (allied) gains +10 × 0.5 = +5
  → Forest Wardens (hostile) gains +10 × -0.3 = -3
```

### Event→Reputation Mapping (Consumer Logic)

| Event | Affected Faction | Rep Change |
|-------|-----------------|-----------|
| Quest completed | Quest-giving faction | +5 to +20 |
| Enemy killed (faction territory) | Controlling faction | +1 to +5 |
| Resource gathered (faction claim) | Claiming faction | -1 to -3 |
| Trade with faction NPC | That faction | +1 to +3 |

## 12.5 Ecosystem State (WMS-Owned Data)

The World Memory System tracks biome resource levels as information state:

```
Max Level (1.0) ──→ Player gathers ──→ Level decreases
                                           │
                ←── Regeneration ←──────────┘
                    (regen_rate per game-time-unit)
```

Threshold tracking (data only, not outgoing actions):
- Below 0.3 → flags "resource_pressure" for evaluators
- Below 0.1 → flags "critical_scarcity" for evaluators

Each biome has base resource levels and regeneration rates tracked in `biome_resource_state` table.

---

# 13. AI Touchpoint Map

Every place where AI inference or interpretation fires.

## 13.1 All Touchpoints

| # | Touchpoint | Layer | Type | Status |
|---|-----------|-------|------|--------|
| 1-9 | Layer 2 Evaluators (Population, Ecosystem, Combat, Crafting, Milestones, Exploration, Social, Economy, Dungeon) | 2 | Template/Tiny LLM | Designed |
| 10-13 | Layer 3 Evaluators (Regional Activity, Cross-Domain, Player Identity, Faction Narrative) | 3 | Tiny LLM | Designed |
| 14 | NPC Dialogue Generation | Consumer | Medium LLM | Partially working |
| 15 | Faction Milestone Narratives | Consumer | Template/Tiny LLM | Events fire, no narrative |
| 16 | Ecosystem Scarcity → Gossip | Consumer | Template | Data exists, no bridge |
| 17 | LLM Item Generator | External | Claude API | Working (separate system) |

## 13.2 Layer 2 Evaluator Flow

```
Event hits threshold → Evaluator selected → Context assembled (Raw Event Pipeline events + TimeEnvelope)
→ Template or LLM generates one-sentence narrative → InterpretedEvent created → Propagated to regions
```

**Templates vs LLM**: Layers 2-3 use templates by default (fast, deterministic). LLM only when template cannot capture the pattern complexity. Higher layers (4+) always use LLM.

## 13.3 Consumer Integration Gaps (NOT WMS Scope)

The following are gaps in **consumer systems** that need WMS data but haven't integrated yet. These are listed for reference — fixing them is NOT part of World Memory System development:

1. **NPC Dialogue** — `query_entity()` works but NPC dialogue system doesn't call it yet
2. **Faction Milestones** — Events fire and log exists, but no consumer generates narrative feedback
3. **Ecosystem Scarcity → NPC awareness** — `biome_resources` tracked, but gossip propagation bridge not wired

## 13.4 WMS Data Readiness

| Data | WMS Layer | Available | Consumer Ready |
|------|-----------|-----------|---------------|
| NPC memory + gossip | Raw Event Pipeline + Layer 2 | Yes | No (dialogue system not integrated) |
| Faction reputation state | Raw Event Pipeline | Yes | No (milestone narratives not generated) |
| Ecosystem scarcity flags | Raw Event Pipeline | Yes | No (gossip bridge not wired) |
| Player profile/archetype | Layer 1 | Partial | No consumer exists yet |

## 13.5 Implementation Priority

```
1. Storage and retrieval layers (complete the pipeline)
2. Triggers and evaluators (Layer 2 producing interpretations)
3. Layer 3 consolidators (cross-domain patterns)
4. Retrieval integration into NPC prompts
5. Gossip propagation plumbing
6. Layer 4+ summaries
```

---

# 14. Integration Points, File Structure, Build Order

## 14.1 Minimal Hooks into Existing Code

The system integrates via GameEventBus subscription. Only 4 files need changes:

| File | Change | Events to Add |
|------|--------|--------------|
| `systems/quest_system.py` | 3 publish calls | `QUEST_ACCEPTED`, `QUEST_COMPLETED`, `QUEST_FAILED` |
| `core/game_engine.py` | NPC interaction publish + PositionSampler | `NPC_INTERACTION`, `POSITION_SAMPLE` |
| `systems/world_system.py` | Chunk load publish | `CHUNK_ENTERED` |
| `save_system/save_manager.py` | Memory DB path + flush | Save/load hooks |

All other events (`DAMAGE_DEALT`, `ENEMY_KILLED`, `RESOURCE_GATHERED`, `ITEM_CRAFTED`, `LEVEL_UP`, `EQUIPMENT_CHANGED`, `SKILL_ACTIVATED`) are **already published**.

## 14.2 Initialization Sequence

```python
# After existing database loading...
geo_registry = GeographicRegistry.get_instance()
geo_registry.load_base_map("world_system/config/geographic-map.json")

entity_registry = EntityRegistry.get_instance()
entity_registry.load_from_npcs(npc_db)
entity_registry.load_from_regions(geo_registry)
entity_registry.register_player(character)

event_store = EventStore(save_dir=get_save_path())
trigger_manager = TriggerManager.get_instance()
event_recorder = EventRecorder.get_instance()
event_recorder.initialize(event_store, geo_registry, entity_registry, trigger_manager, session_id)

interpreter = WorldInterpreter.get_instance()
interpreter.initialize(event_store, geo_registry, entity_registry)

aggregation = AggregationManager.get_instance()
world_query = WorldQuery.get_instance()
world_query.initialize(entity_registry, geo_registry, event_store, aggregation)

position_sampler = PositionSampler()
retention_manager = EventRetentionManager()
```

## 14.3 File Structure

```
Game-1-modular/world_system/
├── __init__.py
├── config/                           # Configuration JSON
│   ├── geographic-map.json           # Region definitions
│   ├── memory-config.json            # Thresholds, windows, retention
│   ├── backend-config.json           # LLM backend settings
│   ├── ecosystem-config.json         # Resource regeneration rates
│   ├── faction-definitions.json      # Faction relationships
│   └── npc-personalities.json        # Personality archetypes
│
├── docs/                             # Documentation
│   └── WORLD_MEMORY_SYSTEM.md        # THIS FILE — single source of truth
│
├── world_memory/                     # Memory system (Phase 2.1)
│   ├── event_schema.py               # WorldMemoryEvent, EventType, InterpretedEvent
│   ├── event_store.py                # SQLite Raw Event Pipeline CRUD
│   ├── event_recorder.py             # Bus subscriber → SQLite writer
│   ├── geographic_registry.py        # Region hierarchy, position lookup
│   ├── entity_registry.py            # WorldEntity, EntityRegistry, tag index
│   ├── tag_relevance.py              # calculate_relevance()
│   ├── trigger_manager.py            # Dual-track threshold counting
│   ├── interpreter.py                # WorldInterpreter + evaluator dispatch
│   ├── evaluators/                   # 33 pattern evaluators (Layer 2)
│   │   ├── # Combat (6): kills regional low/high tier, global, boss, damage, style
│   │   ├── # Gathering (4): regional, depletion, global, tools
│   │   ├── # Crafting (7): 5 disciplines + minigame + inventions
│   │   ├── # Progression (4): levels, skills, identity, equipment
│   │   ├── # Exploration (2): territory, dungeons
│   │   ├── # Social (2): NPC, quests
│   │   ├── # Economy/Items (3): flow, equipment, inventory
│   │   └── # Legacy (5): population, resources, area_danger, crafting, milestones
│   ├── aggregation.py                # Layers 3-4 maintenance
│   ├── query.py                      # WorldQuery, EntityQueryResult, EventWindow
│   ├── daily_ledger.py               # DailyLedger, MetaDailyStats
│   ├── time_envelope.py              # TimeEnvelope computation
│   ├── retention.py                  # EventRetentionManager
│   ├── position_sampler.py           # Periodic breadcrumbs
│   ├── config_loader.py              # Load config JSONs
│   └── test_memory_system.py         # Tests
│
├── living_world/                     # Living World AI (Phases 2.2-2.5)
│   ├── backends/backend_manager.py   # LLM routing
│   ├── npc/npc_agent.py, npc_memory.py
│   ├── factions/faction_system.py
│   └── ecosystem/ecosystem_agent.py
```

## 14.4 Build Order

### Phase A: Foundation (No Game Integration)
- `event_schema.py`, `event_store.py` — dataclasses + SQLite CRUD
- `geographic_registry.py` + `geographic-map.json` — region hierarchy
- `entity_registry.py`, `tag_relevance.py` — entity + tag system
- **Test**: Programmatic event creation, queries, tag matching

### Phase B: Pipeline (Bus Subscription)
- `event_recorder.py` — bus subscriber → SQLite writer
- `trigger_manager.py` — dual-track threshold counting
- `position_sampler.py` — periodic breadcrumbs
- **Test**: Play briefly, verify events in SQLite

### Phase C: Evaluators (Layer 2)
- `interpreter.py` + `evaluators/*.py` — 9 evaluators
- `time_envelope.py` — temporal context
- `daily_ledger.py` — daily aggregation
- **Test**: Generate enough events to trigger thresholds, verify interpretations

### Phase D: Aggregation & Query
- `aggregation.py` — Layer 3-4 maintenance
- `query.py` — WorldQuery with dual window
- **Test**: Query NPCs, regions — verify useful results

### Phase E: Integration & Polish
- Add missing bus publishes (quest, NPC, chunk enter)
- Add initialization sequence to GameEngine
- Add save/load hooks
- End-to-end test: play 30+ minutes, verify full pipeline

### Phase F: Layer 3 Consolidators & Higher Layers
- Layer 3 consolidators (cross-domain, regional, player identity, faction)
- Layer 4 smaller region summaries
- Layers 5-7 realm/intercountry/world state (may be deferred)

## 14.5 Estimated Sizes

| Component | Est. Lines |
|-----------|-----------|
| event_schema.py + event_store.py | 400-500 |
| geographic_registry.py | 200-300 |
| entity_registry.py + tag_relevance.py | 300-400 |
| event_recorder.py + trigger_manager.py | 400-500 |
| interpreter.py + 9 evaluators | 1,200-1,500 |
| aggregation.py + query.py | 500-700 |
| daily_ledger.py + time_envelope.py | 200-300 |
| retention.py + position_sampler.py | 200-250 |
| **Total** | **~3,500-4,500** |

Plus ~400 lines JSON configs and ~800 lines tests.

## 14.6 Dependencies

**Python standard library only** (no new packages): `sqlite3`, `uuid`, `json`, `math`, `time`, `dataclasses`, `enum`, `typing`.

**Existing codebase**: `events/event_bus.py`, `data/models/world.py`, `data/databases/npc_db.py`, `systems/biome_generator.py`, `core/config.py`.

---

# 15. Future Design: Narrative Threads & Player Profile

> These concepts are **designed but not yet in the implementation plan**. They depend on Layers 2-4 being stable first. Included here for completeness.

## 15.1 Narrative Threads (Layer 7)

Persistent story elements with canonical facts and distance-based distortion. See NarrativeThread dataclass in §7.4.

**Key concepts**:
- **Canonical facts**: What IS true. All NPC versions derive from these.
- **Distance-based distortion**: Information compresses with distance from epicenter. Not lying — uncertainty.
- **Thread lifecycle**: rumor → developing → active → resolved/forgotten
- **Developer injection**: `source="developer"` threads never decay — seed the world with pre-authored stories.

## 15.2 Player Profile (Computed from Actions)

Player interaction is through actions, not conversation. Sentiment extracted from observable behavior:

```python
@dataclass
class PlayerProfile:
    # Playstyle weights (0.0-1.0)
    combat_focus: float; crafting_focus: float
    exploration_focus: float; social_focus: float
    # Behavioral traits
    risk_tolerance: float     # 0=cautious, 1=reckless
    thoroughness: float       # 0=rushes, 1=completionist
    persistence: float        # 0=gives up, 1=never quits
    # Preferences
    preferred_disciplines: List[str]
    preferred_combat_style: str  # "melee", "ranged", "magic"
    # Computed from DailyLedger + MetaDailyStats history
```

Observable signals: quest completion speed, kill:death ratio, combat vs. crafting time ratio, resource hoarding vs. spending, NPC visit patterns, combat tier preferences.

**Not stored directly** — computed periodically from Raw Event Pipeline events and DailyLedger history.

## 15.3 Generation Context (Future)

When narrative threads are active, all content generation systems receive context:
```python
@dataclass
class GenerationContext:
    target_region: str; target_biome: str; target_tier: int
    active_threads: List[NarrativeThread]
    regional_themes: List[str]  # ["war", "scarcity"]
    player_profile: PlayerProfile
    player_level: int
    scarcity_data: Dict[str, float]
    faction_standings: Dict[str, float]
```

This drives thematic content: war threads → war-themed enemies, materials, NPC dialogue.

---

# 16. Worked Example: Over-Harvesting Iron

A complete trace through the system showing how a player action ripples through all layers.

**Setup**: Player has been mining iron in the Iron Hills for several game-days.

### Step 1: Player Mines Iron (Bus→Raw Event Pipeline)
```
GameEventBus.publish("RESOURCE_GATHERED", {resource_type: "iron_ore", quantity: 3, ...})
→ stat_tracker: iron_ore_gathered += 3 (Layer 1)
→ EventRecorder: writes WorldMemoryEvent to SQLite (Raw Event Pipeline)
   Tags: [event:resource_gathered, resource:iron, biome:quarry, location:iron_hills, tier:2]
```

### Step 2: Threshold Hit (Raw Event Pipeline→Layer 2)
```
TriggerManager: iron gathering in iron_hills count = 100 → THRESHOLD HIT
→ Interpreter dispatches to EcosystemPressureEvaluator
→ TimeEnvelope: first_at=day_3, last_at=day_47, trend="accelerating", recent_rate=5/day
→ Evaluator output: "Iron deposits are becoming strained in the Iron Hills.
   Gathering rate significantly exceeds natural regeneration."
→ InterpretedEvent created: category=resource_pressure, severity=significant
→ Propagated to Iron Hills locality + Eastern Highlands district
```

### Step 3: Ecosystem Agent Reacts
```
EcosystemAgent reads biome_resources for quarry biome
→ iron current_level = 0.25 (was 1.0 at start)
→ Adjusts: regen_rate stays the same, but notes critical threshold approaching
```

### Step 4: Faction System Notes
```
FactionSystem: mining in Miners Guild territory
→ Player reputation +2 (for resource extraction)
→ Log: "Player contributing to guild mining output"
```

### Step 5: NPC Gets Gossip (Layer 2→NPC)
```
Gareth the Blacksmith (same locality, 60s delay):
→ Receives full interpretation: "Iron deposits becoming strained in Iron Hills"
→ Stored in npc_memory.knowledge_json
→ Next dialogue: "Iron's getting harder to find around here. I'm worried
   about my supply. You've been mining a lot — maybe ease up?"
```

### Step 6: Layer 3 Pattern Detection
```
Iron Hills now has 3+ Layer 2 interpretations:
  - "Resource pressure on iron" (ecosystem)
  - "Heavy gathering activity" (economy)
  - "Mining specialization detected" (crafting)
→ Layer 3 Cross-Domain consolidator fires:
  "The Iron Hills are experiencing intensive resource extraction. Multiple
   systems show correlated pressure on iron supply."
```

### Step 7: Player Queries NPC
```
Player talks to Gareth → world_query.query_entity("npc_gareth")
→ metadata: blacksmith, iron_hills, tags=[resource:iron, domain:smithing, ...]
→ direct_events: recent trades with player
→ nearby_relevant: iron mining events (tag match), NOT wolf kills (no match)
→ local_context: "Iron Hills under resource pressure, mining activity high"
→ ongoing: "Iron deposits strained" (matches Gareth's resource:iron tag)
→ LLM generates dialogue using all context
```

---

# Appendix: Document History

This unified document consolidates the following prior documents:
- `Development-Plan/WORLD_MEMORY_SYSTEM.md` (2920 lines, 2026-03-16) — 6-layer design
- `Development-Plan/TRIGGER_SYSTEM.md` (227 lines) — trigger & cascade design
- `Development-Plan/TIME_AND_RECENCY.md` (396 lines) — daily ledger, time envelopes
- `Development-Plan/RETRIEVAL_AND_TAGGING.md` (538 lines) — tagging pipeline
- `Development-Plan/WORLD_SYSTEM_SCRATCHPAD.md` (665 lines) — research & narrative threads
- `Development-Plan/fragments/00-07` (2920 lines) — section fragments
- `world_system/docs/README.md` (371 lines, 2026-03-24) — 7-layer overview
- `world_system/docs/LAYER_ARCHITECTURE.md` (205 lines) — layer model
- `world_system/docs/EVALUATOR_DESIGN.md` (263 lines) — evaluator specs
- `world_system/docs/STORAGE_SCHEMA.md` (338 lines) — SQL schema
- `world_system/docs/RETRIEVAL_DESIGN.md` (263 lines) — query design
- `world_system/docs/LIVING_WORLD_AI.md` (421 lines) — agent implementations
- `world_system/docs/AI_TOUCHPOINT_MAP.md` (356 lines) — inference map

The 7-layer architecture (from world_system/docs/, 2026-03-24) supersedes the 6-layer architecture (from Development-Plan/, 2026-03-16). All other content merged by taking the more recent/complete version of each topic.

# World Memory System — Implementation Plan

**Created**: 2026-03-16
**Status**: Ready for Implementation
**Phase**: 2.1 of Living World Development Plan
**Estimated Size**: ~2,500-3,500 lines of Python + ~400 lines JSON configs

---

## Table of Contents

1. [Architecture Overview & Layer Definitions](#1-architecture-overview--layer-definitions)
2. [Geographic System](#2-geographic-system)
3. [Entity Registry & Interest Tags](#3-entity-registry--interest-tags)
4. [Event Schema, Recording Pipeline, Retention Policy](#4-event-schema-recording-pipeline-retention-policy)
5. [Interpreter System (Layer 3)](#5-interpreter-system-layer-3)
6. [Query Architecture, Aggregation, Window System](#6-query-architecture-aggregation-layers-4-5-window-system)
7. [SQLite Schema, Integration Points, File Structure, Build Order](#7-sqlite-schema-integration-points-file-structure-build-order)
8. [Relationship to Existing Documents](#8-relationship-to-existing-documents)

### Companion Documents (Expanded Designs)
- **`TRIGGER_SYSTEM.md`** — Trigger thresholds, cascade model, LLM sizing, early-game templates
- **`TIME_AND_RECENCY.md`** — Daily ledgers, meta-daily stats, time envelopes, recency weighting
- **`RETRIEVAL_AND_TAGGING.md`** — Auto-tagging pipeline, layer-by-layer tagging, retrieval flows, similarity counting

---

## Design Principles

1. **Information state only** — This system records and interprets. It does NOT apply mechanical game effects. Event propagation produces narrative text, not JSON effects. A separate downstream system reads interpretations and decides what game mechanics change.
2. **Entity-first queries** — You never search events directly. You find the entity first (NPC, region, player), then radiate outward through its location, interests, and awareness radius.
3. **Interest tags are identity** — Tags are overapplied by design (species, location, affiliation, job, tendency, hobby, preference, etc.). They ARE the entity's fingerprint in the information system.
4. **Write-time processing** — Events are enriched, propagated, and aggregated at write time, not query time. Queries are fast reads.
5. **Dual-track trigger system** — Individual event streams trigger at the threshold sequence (1, 3, 5, 10, 25, 50, 100, 250, 500, 1000). Regional accumulators trigger at the same thresholds for aggregate patterns. Each trigger can generate, ignore, or absorb. See `TRIGGER_SYSTEM.md` for full design.
6. **Milestone preservation** — Old events are pruned, but first occurrences, threshold-indexed events, power-of-10 milestones, and timeline markers are always kept.
7. **Time-based tracking** — Daily ledgers aggregate per-day stats. Meta-daily stats track streaks, records, and patterns across days. Time envelopes provide compact temporal context for interpretations. See `TIME_AND_RECENCY.md`.
8. **Layered tagging** — Layer 2 events are auto-tagged from data fields. Layer 3 inherits + derives tags. Tags enable similarity counting for trigger thresholds. See `RETRIEVAL_AND_TAGGING.md`.
7. **Strict layer boundaries** — Writes flow downward (Layer 0→2→3→4→5). Reads flow upward. No circular dependencies within the data layers.

---

# 1. Architecture Overview & Layer Definitions

## 1.1 Purpose

The World Memory System is the **information state layer** for the Living World. It records what happens, detects patterns, and organizes knowledge geographically — so that downstream systems (NPC agents, quest generators, ecosystem managers) can ask entity-first questions and get contextual answers.

This system is **narrative only**. It stores and interprets information. It does NOT apply mechanical game effects (damage numbers, stat changes, spawn rates). A separate system reads this information state and decides what game mechanics change.

## 1.2 The Six Layers

```
Layer 5: Regional Events        ← Province/realm-level summaries
Layer 4: Local Events           ← Locality/district-level summaries
Layer 3: Interpreted Events     ← Pattern detection, narrative descriptions
─────────────────────────────────────────────────────────────
Layer 2: Raw Event Records      ← Structured facts in SQLite (NEW — this doc)
Layer 1: Raw Stat Tracking      ← Cumulative counters (EXISTING — stat_tracker.py)
Layer 0: Raw Actions            ← Ephemeral bus messages (EXISTING — event_bus.py)
```

The line between Layers 2 and 3 is the critical boundary. Below it: **facts** (immutable records of what happened). Above it: **interpretations** (derived meaning, narrative descriptions, aggregated knowledge).

### Layer 0: Raw Actions (Ephemeral)

**What**: The `GameEventBus` as it exists today. Every game action fires a pub/sub event. Visual systems, sound, UI subscribe for immediate reactions.

**Storage**: None. Events exist for one processing cycle then are gone.

**Role in this system**: Layer 0 is the **input stream**. The World Memory System subscribes to Layer 0 via `bus.subscribe("*", ...)` and selectively records meaningful events into Layer 2.

**No changes needed**. The bus works. We just add a new subscriber.

### Layer 1: Raw Stat Tracking (Existing, Unchanged)

**What**: The existing `stat_tracker.py` — 1,755 lines, ~1,000 cumulative counters organized into 14 categories (gathering, crafting, combat, exploration, time, records, etc.).

**Storage**: Serialized to JSON via the save system.

**Role in this system**: Layer 1 is a **fast-path for aggregate player queries**. "How many wolves has the player killed total?" is answered instantly from Layer 1 without scanning Layer 2. The World Memory System reads Layer 1 for quick checks but never writes to it.

**No changes needed**. stat_tracker.py stays exactly as-is.

### Layer 2: Raw Event Records (NEW — SQLite)

**What**: Every meaningful game action recorded as a structured fact with full spatial, temporal, and contextual data. Not every frame — only actions that change world state or are relevant to world knowledge.

**Storage**: SQLite database, one row per event. Indexed for fast spatial and temporal queries.

**Role in this system**: Layer 2 is the **world's factual memory**. It answers "what happened, where, when, involving whom?" These are immutable atomic facts — once written, they never change.

**Key distinction from Layer 1**: Layer 1 says "47 wolves killed." Layer 2 has 47 individual records, each with position, time, weapon used, wolf tier, nearby NPCs, player health at the time, etc.

**Retention**: Events are pruned over time using the milestone preservation policy (see Section 4). Old events are condensed but never fully lost — first occurrence, threshold milestones, and timeline markers are always kept.

### Layer 3: Interpreted Events (NEW — SQLite)

**What**: Pattern-detected, threshold-triggered narrative descriptions derived from Layer 2 data. These are the "news stories" of the world.

**Storage**: SQLite, same database as Layer 2 but separate table.

**Examples**:
- "Wolf population declining in Whispering Woods" (wolf kills exceed spawn rate)
- "Iron deposits strained in Iron Hills" (gathering rate exceeds node respawn)
- "A prolific hunter roams the Eastern Highlands" (player combat events concentrated in region)
- "Forest fire has swept through the Northern Pines" (world event propagation)

**Key properties**:
- Each interpreted event has a **cause chain** (which Layer 2 events triggered it)
- Each has **affected tags** (what categories of entities/regions this concerns)
- Each is a **narrative text description**, NOT a JSON effect
- Each has a duration (ongoing vs. one-time) and severity
- Each is spatially anchored to one or more geographic regions

**Trigger mechanism**: The Interpreter checks Layer 2 at **threshold occurrence counts** (1, 3, 5, 10, 25, 50, 100, 250, 500, 1000 — see `TRIGGER_SYSTEM.md`). Both individual event streams and regional accumulators use these thresholds. Each trigger evaluates but can also ignore — not every threshold crossing produces an interpretation.

### Layer 4: Local Events (NEW — In-Memory with SQLite Backup)

**What**: Per-locality and per-district aggregation of Layer 3 interpreted events. This is "what's happening in this immediate area" — what an NPC standing here would know from their surroundings.

**Storage**: Maintained in-memory as part of the geographic region state, backed to SQLite periodically.

**Contents per locality/district**:
- Recent interpreted events (static window + recency window — see Section 6)
- Ongoing conditions (active Layer 3 events with duration)
- Summary narrative: a compressed text description of current local conditions

**Updated when**: A new Layer 3 event is created or expires within this geographic area.

### Layer 5: Regional Events (NEW — In-Memory with SQLite Backup)

**What**: Per-province and per-realm aggregation. Broader patterns visible at a larger geographic scale. What a traveling merchant or regional authority would know.

**Storage**: Same as Layer 4 — in-memory with SQLite backup.

**Contents per province/realm**:
- Notable interpreted events from child localities (filtered by severity)
- Cross-locality trends ("iron scarce across all eastern districts")
- Regional summary narrative

**Updated when**: Layer 4 summaries change significantly in any child region.

## 1.3 Data Flow — The Pipeline

```
GAME ACTION (player mines iron)
       │
       ▼
  Layer 0: GameEventBus.publish("RESOURCE_GATHERED", {...})
       │
       ├──→ [Existing systems: VFX, sound, UI]
       │
       ├──→ Layer 1: stat_tracker.record_resource_gathered(...)  [existing, unchanged]
       │
       └──→ Layer 2: EventRecorder.record(...)                   [NEW]
                │     Writes structured event to SQLite with
                │     geographic context (locality, district, province)
                │
                ▼
            Propagator                                            [NEW]
                │     Routes event to affected entities/regions
                │     Updates entity activity logs
                │     Checks: does this event's count hit a threshold?
                │
                ▼
            Interpreter (if threshold trigger hit)                 [NEW]
                │     Evaluates patterns in Layer 2 data
                │     Generates narrative description if threshold met
                │     Creates Layer 3 interpreted event
                │
                ▼
            Aggregator                                            [NEW]
                │     Updates Layer 4 (local) for affected localities
                │     Updates Layer 5 (regional) if significant
                │
                ▼
            [Ready for downstream queries]
```

**Critical**: This pipeline runs at **write time**, not query time. By the time anything queries the system, data is already organized, propagated, and aggregated. Queries are fast reads, not expensive scans.

## 1.4 Strict Layer Boundaries — No Circular Logic

```
WRITES FLOW DOWNWARD (through the pipeline):
  Layer 0 → Layer 2 → Layer 3 → Layer 4 → Layer 5

READS FLOW UPWARD (queries can read any layer):
  Downstream systems (NPC agents, quest gen) read Layers 1-5

THE GAME LOOP (not circular — this is normal gameplay):
  NPC agent reads Layers 2-5 → decides to act → action becomes Layer 0 event
  → flows through pipeline → becomes new Layer 2/3/4/5 data
```

Layer 3 NEVER directly triggers Layer 3. Layer 4 NEVER writes to Layer 2. The cycle goes through the **decision layer** (NPC AI, game systems), which is external to the data layers.


---

# 2. Geographic System

## 2.1 Purpose

The game world is a grid of 16x16 tile chunks with biome assignments. The Geographic System superimposes a **named address hierarchy** onto this grid — giving every position a human-readable location identity that the memory system and NPC agents can reference.

This is like overlaying a political/cultural map onto a topographic one. The chunks and biomes are the terrain. The geographic regions are the "countries, states, counties, cities" that give places names, narrative identity, and administrative grouping.

## 2.2 Hierarchy

```
Realm (entire world)
  └── Province (~25x50 or ~50x25 tiles, 2-4 per realm)
        └── District (~12x12 to ~25x25 tiles, 2-6 per province)
              └── Locality (~8x8 to ~16x16 tiles, roughly chunk-sized, 2-4 per district)
```

**Tile count for a 100x100 world:**
- 1 Realm
- ~4 Provinces (each covering roughly a quadrant, irregularly shaped)
- ~12-20 Districts (named areas like "Iron Hills", "Whispering Woods")
- ~40-80 Localities (named spots like "Blacksmith's Crossing", "Old Mine")

These numbers are approximate. The system supports any number at any level.

## 2.3 Region Definition

```python
class RegionLevel(Enum):
    LOCALITY = "locality"
    DISTRICT = "district"
    PROVINCE = "province"
    REALM = "realm"

@dataclass
class Region:
    region_id: str                    # Unique identifier: "iron_hills", "eastern_highlands"
    name: str                         # Display name: "Iron Hills", "Eastern Highlands"
    level: RegionLevel                # Which tier in the hierarchy

    # Spatial bounds (tile coordinates, axis-aligned rectangle)
    bounds_x1: int                    # Left edge (inclusive)
    bounds_y1: int                    # Top edge (inclusive)
    bounds_x2: int                    # Right edge (inclusive)
    bounds_y2: int                    # Bottom edge (inclusive)

    # Hierarchy
    parent_id: Optional[str]          # Parent region (None for realm)
    child_ids: List[str]              # Direct children

    # Identity (static, defined at creation)
    biome_primary: str                # Dominant biome type
    description: str                  # Narrative description for LLM context
    tags: List[str]                   # Geographic identity tags (see below)

    # Mutable state (updated by event propagation)
    state: RegionState                # Current conditions (see below)
```

### Region State

```python
@dataclass
class RegionState:
    """Mutable state of a region — updated by event propagation pipeline"""

    # Layer 3 interpreted events affecting this region
    active_conditions: List[str]      # IDs of ongoing Layer 3 events
    recent_events: List[str]          # IDs of recent Layer 3 events (bounded)

    # Narrative summary (regenerated when conditions change)
    summary_text: str                 # "The Iron Hills are under resource pressure..."
    last_updated: float               # Game time of last state change

    def to_dict(self) -> Dict[str, Any]:
        return {
            "active_conditions": self.active_conditions,
            "recent_events": self.recent_events,
            "summary_text": self.summary_text,
            "last_updated": self.last_updated
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'RegionState':
        return cls(
            active_conditions=data.get("active_conditions", []),
            recent_events=data.get("recent_events", []),
            summary_text=data.get("summary_text", ""),
            last_updated=data.get("last_updated", 0.0)
        )
```

## 2.4 Geographic Tags on Regions

Regions carry tags that describe their identity — same tag system used for entities. These tags enable the Propagator to route events to affected regions by tag matching.

```python
# Example region tags:
"iron_hills" → [
    "terrain:hills", "terrain:rocky",
    "resource:iron", "resource:stone", "resource:copper",
    "biome:quarry", "biome:cave",
    "danger:moderate",
    "feature:mines", "feature:ore_veins",
    "climate:temperate"
]

"whispering_woods" → [
    "terrain:forest", "terrain:dense",
    "resource:wood", "resource:herbs", "resource:wildlife",
    "biome:forest",
    "danger:low",
    "feature:ancient_trees", "feature:clearings",
    "climate:temperate", "atmosphere:mysterious"
]

"northern_pines" → [
    "terrain:forest", "terrain:mountainous",
    "resource:wood", "resource:wildlife",
    "biome:forest",
    "danger:moderate",
    "feature:pine_forest", "feature:mountain_pass",
    "climate:cold"
]
```

When a "forest fire" interpreted event is created with `affects_tags: ["terrain:forest", "resource:wood"]`, the Propagator finds all regions whose tags overlap and updates their state.

## 2.5 Position-to-Region Lookup

### At Runtime

Given a position `(x, y)`, determine which locality → district → province → realm it belongs to:

```python
class GeographicRegistry:
    """Maps positions to named regions. Singleton."""
    _instance = None

    def __init__(self):
        self.regions: Dict[str, Region] = {}       # region_id → Region
        self.realm: Optional[Region] = None         # The top-level realm

        # Spatial index: chunk → locality mapping (cached)
        self._chunk_to_locality: Dict[Tuple[int, int], str] = {}
        # Locality → district → province chain (cached)
        self._locality_chain: Dict[str, List[str]] = {}

    def get_region_at(self, x: float, y: float) -> Optional[Region]:
        """Get the most specific (locality-level) region for a position"""
        # First check chunk cache
        chunk_x = int(x) // 16
        chunk_y = int(y) // 16
        cache_key = (chunk_x, chunk_y)

        if cache_key in self._chunk_to_locality:
            return self.regions[self._chunk_to_locality[cache_key]]

        # Scan localities for containment (only needed once per chunk)
        for region in self.regions.values():
            if region.level == RegionLevel.LOCALITY:
                if (region.bounds_x1 <= x <= region.bounds_x2 and
                    region.bounds_y1 <= y <= region.bounds_y2):
                    self._chunk_to_locality[cache_key] = region.region_id
                    return region

        return None  # Position outside all defined localities

    def get_full_address(self, x: float, y: float) -> Dict[str, str]:
        """Get full address hierarchy for a position"""
        locality = self.get_region_at(x, y)
        if not locality:
            return {}

        result = {"locality": locality.region_id}
        current = locality
        while current.parent_id:
            parent = self.regions[current.parent_id]
            result[parent.level.value] = parent.region_id
            current = parent
        return result

    def get_regions_by_tag(self, tag: str) -> List[Region]:
        """Find all regions with a specific tag"""
        return [r for r in self.regions.values() if tag in r.tags]

    def get_nearby_regions(self, x: float, y: float, radius: float,
                           level: RegionLevel = RegionLevel.LOCALITY) -> List[Region]:
        """Find all regions of a given level within radius of a point"""
        results = []
        for region in self.regions.values():
            if region.level != level:
                continue
            # Check center-to-point distance
            cx = (region.bounds_x1 + region.bounds_x2) / 2
            cy = (region.bounds_y1 + region.bounds_y2) / 2
            dist = math.sqrt((x - cx) ** 2 + (y - cy) ** 2)
            if dist <= radius:
                results.append(region)
        return results
```

### Chunk-to-Region Mapping

Computed once per chunk load, cached. Since chunks are 16x16 and localities are roughly chunk-sized, most chunks map to exactly one locality. If a chunk straddles a boundary, the center tile's locality wins.

```python
# On chunk load (in WorldSystem):
address = geographic_registry.get_full_address(chunk_center_x, chunk_center_y)
chunk.locality_id = address.get("locality")
chunk.district_id = address.get("district")
chunk.province_id = address.get("province")
```

Every Layer 2 event recorded in this chunk automatically gets these region IDs stamped — zero per-event lookup cost.

## 2.6 Map Definition — Static or Procedural

### Option A: Static Map (Configuration JSON)

A hand-authored JSON file defining all regions. Best for curated world design.

```json
{
  "realm": {
    "region_id": "known_lands",
    "name": "The Known Lands",
    "level": "realm",
    "bounds": [0, 0, 99, 99],
    "description": "A frontier land of forests, hills, and ancient ruins."
  },
  "provinces": [
    {
      "region_id": "eastern_highlands",
      "name": "Eastern Highlands",
      "level": "province",
      "bounds": [50, 0, 99, 49],
      "parent_id": "known_lands",
      "biome_primary": "quarry",
      "description": "Rocky highlands rich with mineral deposits.",
      "tags": ["terrain:hills", "terrain:rocky", "resource:iron", "resource:stone", "climate:temperate"]
    }
  ],
  "districts": [
    {
      "region_id": "iron_hills",
      "name": "Iron Hills",
      "level": "district",
      "bounds": [60, 10, 80, 30],
      "parent_id": "eastern_highlands",
      "biome_primary": "quarry",
      "description": "The heart of the highlands mining region.",
      "tags": ["terrain:hills", "resource:iron", "resource:copper", "feature:mines", "danger:moderate"]
    }
  ],
  "localities": [
    {
      "region_id": "old_mine_shaft",
      "name": "Old Mine Shaft",
      "level": "locality",
      "bounds": [65, 15, 75, 25],
      "parent_id": "iron_hills",
      "biome_primary": "cave",
      "description": "An abandoned mine with deep iron veins. Dangerous creatures lurk below.",
      "tags": ["terrain:cave", "resource:iron", "feature:abandoned_mine", "danger:high", "atmosphere:dark"]
    }
  ]
}
```

### Option B: Procedural Generation at World Creation

Generate region names and boundaries from the existing biome generator output. Uses the chunk biome assignments to cluster chunks into named regions.

```python
class ProceduralGeographer:
    """Generates named regions from biome data at world creation"""

    def generate_map(self, biome_generator: BiomeGenerator,
                     world_seed: int) -> Dict[str, Region]:
        """
        1. Get biome type for all chunks in the play area
        2. Cluster adjacent chunks of similar biome into localities
        3. Group localities into districts based on biome category
        4. Group districts into provinces based on quadrant
        5. Assign names from a name pool seeded by world_seed
        6. Generate tags from biome data
        """
        ...
```

### Option C: Hybrid (Recommended)

Start with procedural generation for the basic structure, then allow hand-authored overrides and additions. New regions can be added via:
- Developer injection (new JSON entries)
- Narrative threads (a "discovered" region gets named and registered)
- World expansion (new areas beyond current bounds)

```python
class GeographicRegistry:
    def load_base_map(self, filepath: str):
        """Load static map definition"""
        ...

    def generate_unnamed_regions(self, biome_generator: BiomeGenerator):
        """Fill gaps with procedurally named regions"""
        ...

    def register_region(self, region: Region):
        """Add a new region at runtime (expansion, discovery)"""
        self.regions[region.region_id] = region
        self._invalidate_cache()
```

## 2.7 Scalability Considerations

**World expansion**: Adding new territory means defining new regions with new bounds. Existing regions don't change. The realm boundary is conceptual — there's no array indexed 0-100 to resize.

**Region overlap**: Regions at the same level should NOT overlap. The hierarchy enforces containment: every locality is inside exactly one district, etc. If needed, a "border zone" locality can be created.

**Performance**: With ~80 localities, the scan in `get_region_at()` is trivial. For larger worlds (1000+ localities), switch to an R-tree spatial index or a grid-based lookup table.

**Chunk alignment**: Localities don't need to align exactly to chunk boundaries. The chunk-center mapping handles edge cases. But aligning roughly to chunk boundaries simplifies everything.


---

# 3. Entity Registry & Interest Tags

## 3.1 Purpose

Every queryable thing in the world gets an entry in the Entity Registry. This is the **starting point** for all queries — you never search events directly. You find the entity first, then radiate outward through its location, interests, and awareness.

The interest tag system is the **crux** of this architecture. Tags are not a filter — they ARE the entity's identity to the information system. They define what events are relevant, what an NPC would notice, what a region is known for.

## 3.2 Entity Definition

```python
class EntityType(Enum):
    PLAYER = "player"
    NPC = "npc"
    ENEMY_TYPE = "enemy_type"         # Not individual enemies — enemy *species*
    RESOURCE_TYPE = "resource_type"    # Not individual nodes — resource *kind*
    LOCATION = "location"             # Named regions from the geographic system
    STATION = "station"               # Crafting stations
    FACTION = "faction"               # Groups of NPCs/entities

@dataclass
class WorldEntity:
    entity_id: str                    # Unique: "npc_blacksmith_gareth", "enemy_type_wolf"
    entity_type: EntityType
    name: str                         # Display: "Gareth the Blacksmith", "Gray Wolf"

    # Position (None for abstract entities like resource types or factions)
    position_x: Optional[float]
    position_y: Optional[float]

    # Geographic anchoring
    home_region_id: Optional[str]     # Primary region this entity belongs to
    home_district_id: Optional[str]   # Cached parent for faster queries
    home_province_id: Optional[str]   # Cached parent for faster queries

    # HOW FAR THIS ENTITY'S AWARENESS EXTENDS (in tiles)
    awareness_radius: float           # NPC: ~32-48, Region: its own bounds, Player: global

    # THE IDENTITY — Interest Tags
    tags: List[str]                   # See comprehensive tag system below

    # Activity log — bounded circular buffer of Layer 2 event IDs
    activity_log: List[str]           # Most recent N event_ids directly involving this entity
    activity_log_max: int = 100       # How many to keep in the buffer

    # Entity-specific metadata (varies by type)
    metadata: Dict[str, Any]          # Static properties specific to entity type
```

## 3.3 The Interest Tag System — Entity Identity

### Philosophy

Tags are **overapplied by design**. An NPC blacksmith isn't just tagged `["job:blacksmith"]`. They're tagged with everything that defines what they'd notice, care about, or know about. This is their fingerprint in the information system.

### Tag Categories

Every tag follows the format `category:value`. Categories are:

```
SPECIES/TYPE
  species:human, species:dwarf, species:elf
  type:npc, type:hostile, type:passive, type:resource

LOCATION (where they live/belong)
  location:iron_hills, location:eastern_highlands
  origin:northern_reaches
  territory:whispering_woods

AFFILIATION (groups, factions, allegiances)
  faction:miners_guild, faction:forest_wardens
  allegiance:crown, allegiance:independent
  guild:smithing, guild:alchemy

JOB/ROLE (what they do)
  job:blacksmith, job:merchant, job:guard, job:hunter
  role:quest_giver, role:trainer, role:shopkeeper

DOMAIN (knowledge/expertise areas)
  domain:smithing, domain:metalwork, domain:weapons, domain:armor
  domain:alchemy, domain:herbs, domain:potions
  domain:combat, domain:hunting, domain:tracking
  domain:mining, domain:forestry, domain:fishing

RESOURCE INTEREST (what materials matter to them)
  resource:iron, resource:steel, resource:mithril
  resource:wood, resource:herbs, resource:leather
  resource:stone, resource:gems

TENDENCY (behavioral patterns)
  tendency:cautious, tendency:aggressive, tendency:curious
  tendency:generous, tendency:greedy, tendency:honest
  tendency:gossip, tendency:secretive

HOBBY/PREFERENCE (what they enjoy/value)
  preference:quality_over_quantity
  preference:rare_materials, preference:common_goods
  hobby:storytelling, hobby:collecting, hobby:exploring

CONCERN (what worries/motivates them)
  concern:safety, concern:profit, concern:reputation
  concern:scarcity, concern:wildlife, concern:weather

BIOME (what environments they relate to)
  biome:forest, biome:cave, biome:quarry, biome:water

COMBAT (for enemy types and combat-aware NPCs)
  combat:melee, combat:ranged, combat:magic
  tier:1, tier:2, tier:3, tier:4
  element:fire, element:ice, element:lightning

EVENT INTEREST (what kinds of events catch their attention)
  event:trade, event:combat, event:crafting, event:gathering
  event:death, event:discovery, event:quest
```

### Example Entity Tag Sets

**NPC: Gareth the Blacksmith**
```python
tags = [
    # What he is
    "species:human", "type:npc",
    # Where he is
    "location:blacksmiths_crossing", "location:iron_hills",
    # What he does
    "job:blacksmith", "role:shopkeeper", "role:quest_giver",
    "guild:smithing",
    # What he knows about
    "domain:smithing", "domain:metalwork", "domain:weapons",
    "domain:armor", "domain:repair",
    # What resources matter to him
    "resource:iron", "resource:steel", "resource:mithril",
    "resource:coal", "resource:leather",
    # His personality
    "tendency:honest", "tendency:perfectionist",
    "preference:quality_over_quantity",
    "preference:rare_materials",
    # What concerns him
    "concern:scarcity", "concern:reputation",
    # What events he notices
    "event:trade", "event:crafting",
    # Biome awareness
    "biome:quarry", "biome:cave"
]
```

**NPC: Elara the Herbalist**
```python
tags = [
    "species:elf", "type:npc",
    "location:whispering_woods", "location:riverside_camp",
    "job:herbalist", "role:shopkeeper", "role:quest_giver",
    "guild:alchemy",
    "domain:alchemy", "domain:herbs", "domain:potions",
    "domain:nature", "domain:healing",
    "resource:herbs", "resource:mushrooms", "resource:flowers",
    "resource:water",
    "tendency:cautious", "tendency:curious",
    "preference:natural_remedies", "preference:rare_herbs",
    "concern:wildlife", "concern:deforestation",
    "concern:pollution",
    "event:gathering", "event:discovery",
    "biome:forest", "biome:water",
    "hobby:exploring", "hobby:collecting"
]
```

**Enemy Type: Gray Wolf**
```python
tags = [
    "species:wolf", "type:hostile",
    "tier:1",
    "biome:forest", "biome:plains",
    "combat:melee",
    "resource:wolf_pelt", "resource:wolf_fang",
    "behavior:pack", "behavior:territorial",
    "concern:territory", "concern:prey"
]
```

**Region: Iron Hills (as an entity)**
```python
tags = [
    "type:location", "level:district",
    "terrain:hills", "terrain:rocky",
    "biome:quarry", "biome:cave",
    "resource:iron", "resource:copper", "resource:stone",
    "resource:coal", "resource:gems",
    "feature:mines", "feature:ore_veins",
    "danger:moderate",
    "climate:temperate",
    "industry:mining", "industry:smithing"
]
```

**Player (singleton)**
```python
tags = [
    "type:player",
    # Dynamic tags added/updated based on behavior (from PlayerProfile):
    "playstyle:combat_focused",  # or crafting_focused, explorer, etc.
    "preference:melee",          # or ranged, magic
    "level:tier_2",              # derived from current level
    # Dynamic tags from achievements:
    "title:journeyman_smith",
    "class:warrior",
    # Dynamic tags from recent activity:
    "active_in:iron_hills",
    "hunting:wolves"
]
```

### Tag Matching — How Interest Filtering Works

When assembling "what does this entity know about?", the system matches event tags against entity interest tags:

```python
def calculate_relevance(entity_tags: List[str], event_tags: List[str]) -> float:
    """
    Score how relevant an event is to an entity based on tag overlap.
    Returns 0.0 (irrelevant) to 1.0 (directly relevant).
    """
    if not entity_tags or not event_tags:
        return 0.0

    # Extract categories from tags
    entity_categories = {}
    for tag in entity_tags:
        cat, val = tag.split(":", 1) if ":" in tag else (tag, tag)
        entity_categories.setdefault(cat, set()).add(val)

    event_categories = {}
    for tag in event_tags:
        cat, val = tag.split(":", 1) if ":" in tag else (tag, tag)
        event_categories.setdefault(cat, set()).add(val)

    # Score: what fraction of the event's tag categories does the entity care about?
    matches = 0
    total = len(event_categories)
    for cat, vals in event_categories.items():
        if cat in entity_categories:
            # Category match — check value overlap
            if entity_categories[cat] & vals:
                matches += 1
            else:
                matches += 0.3  # Same category, different value = partial match

    return min(1.0, matches / max(total, 1))
```

### Entity Registration

The registry loads entities from multiple sources at startup:

```python
class EntityRegistry:
    """Central registry of all queryable entities. Singleton."""
    _instance = None

    def __init__(self):
        self.entities: Dict[str, WorldEntity] = {}
        self._tag_index: Dict[str, List[str]] = {}  # tag → [entity_ids]

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def register(self, entity: WorldEntity):
        """Add or update an entity"""
        self.entities[entity.entity_id] = entity
        # Update tag index
        for tag in entity.tags:
            self._tag_index.setdefault(tag, []).append(entity.entity_id)

    def get(self, entity_id: str) -> Optional[WorldEntity]:
        return self.entities.get(entity_id)

    def find_by_tag(self, tag: str) -> List[WorldEntity]:
        """Find all entities with a specific tag"""
        ids = self._tag_index.get(tag, [])
        return [self.entities[eid] for eid in ids if eid in self.entities]

    def find_by_tags(self, tags: List[str], match_mode: str = "any") -> List[WorldEntity]:
        """
        Find entities matching tags.
        match_mode: "any" (at least one tag matches) or "all" (every tag matches)
        """
        if match_mode == "any":
            result_ids = set()
            for tag in tags:
                result_ids.update(self._tag_index.get(tag, []))
            return [self.entities[eid] for eid in result_ids if eid in self.entities]
        else:  # "all"
            if not tags:
                return []
            result_ids = set(self._tag_index.get(tags[0], []))
            for tag in tags[1:]:
                result_ids &= set(self._tag_index.get(tag, []))
            return [self.entities[eid] for eid in result_ids if eid in self.entities]

    def find_near(self, x: float, y: float, radius: float,
                  entity_type: Optional[EntityType] = None) -> List[WorldEntity]:
        """Find entities within radius of a position"""
        results = []
        for entity in self.entities.values():
            if entity.position_x is None:
                continue
            if entity_type and entity.entity_type != entity_type:
                continue
            dist = math.sqrt((x - entity.position_x) ** 2 + (y - entity.position_y) ** 2)
            if dist <= radius:
                results.append(entity)
        return results

    def load_from_npcs(self, npc_db: 'NPCDatabase'):
        """Register all NPCs from the existing NPC database"""
        for npc_id, npc_def in npc_db.npcs.items():
            entity = WorldEntity(
                entity_id=f"npc_{npc_id}",
                entity_type=EntityType.NPC,
                name=npc_def.name,
                position_x=npc_def.position.x,
                position_y=npc_def.position.y,
                home_region_id=None,  # Filled by geographic lookup
                tags=self._generate_npc_tags(npc_def),
                awareness_radius=max(npc_def.interaction_radius * 8, 32.0),
                activity_log=[],
                metadata={"dialogue_lines": npc_def.dialogue_lines,
                           "quests": npc_def.quests}
            )
            # Auto-fill geographic data
            geo = GeographicRegistry.get_instance()
            address = geo.get_full_address(npc_def.position.x, npc_def.position.y)
            entity.home_region_id = address.get("locality")
            entity.home_district_id = address.get("district")
            entity.home_province_id = address.get("province")
            # Add location tags
            for level, region_id in address.items():
                entity.tags.append(f"location:{region_id}")

            self.register(entity)

    def load_from_regions(self, geo_registry: 'GeographicRegistry'):
        """Register all regions as entities (so they can be queried too)"""
        for region_id, region in geo_registry.regions.items():
            cx = (region.bounds_x1 + region.bounds_x2) / 2
            cy = (region.bounds_y1 + region.bounds_y2) / 2
            entity = WorldEntity(
                entity_id=f"region_{region_id}",
                entity_type=EntityType.LOCATION,
                name=region.name,
                position_x=cx,
                position_y=cy,
                home_region_id=region_id,
                tags=region.tags + [f"level:{region.level.value}"],
                awareness_radius=max(
                    region.bounds_x2 - region.bounds_x1,
                    region.bounds_y2 - region.bounds_y1
                ) / 2,
                activity_log=[],
                metadata={"description": region.description,
                           "biome_primary": region.biome_primary}
            )
            self.register(entity)
```

### Dynamic Tag Updates

Player tags change over time as behavior changes. NPC tags can change if their role/faction changes:

```python
def update_entity_tags(self, entity_id: str, add_tags: List[str] = None,
                       remove_tags: List[str] = None):
    """Update tags for an entity (e.g., player playstyle changes)"""
    entity = self.entities.get(entity_id)
    if not entity:
        return

    if remove_tags:
        for tag in remove_tags:
            if tag in entity.tags:
                entity.tags.remove(tag)
                if tag in self._tag_index:
                    self._tag_index[tag] = [
                        eid for eid in self._tag_index[tag] if eid != entity_id
                    ]

    if add_tags:
        for tag in add_tags:
            if tag not in entity.tags:
                entity.tags.append(tag)
                self._tag_index.setdefault(tag, []).append(entity_id)
```

### Serialization

```python
def to_dict(self) -> Dict[str, Any]:
    """Serialize for save system"""
    return {
        "entities": {
            eid: {
                "entity_id": e.entity_id,
                "entity_type": e.entity_type.value,
                "name": e.name,
                "position_x": e.position_x,
                "position_y": e.position_y,
                "home_region_id": e.home_region_id,
                "awareness_radius": e.awareness_radius,
                "tags": e.tags,
                "activity_log": e.activity_log,
                "metadata": e.metadata
            }
            for eid, e in self.entities.items()
        }
    }
```


---

# 4. Event Schema, Recording Pipeline, Retention Policy

## 4.1 Layer 2 Event Schema

Every meaningful game action becomes a structured record. This is the world's factual memory.

```python
@dataclass
class WorldMemoryEvent:
    """Atomic unit of world memory — one thing that happened."""

    # Identity
    event_id: str                     # UUID (generated at creation)
    event_type: str                   # EventType enum value
    event_subtype: str                # Specific action: "mined_iron", "killed_wolf", "crafted_sword"

    # WHO
    actor_id: str                     # Entity ID: "player", "npc_gareth", "enemy_wolf_pack_3"
    actor_type: str                   # "player", "npc", "enemy", "system"
    target_id: Optional[str]          # What was acted upon (entity ID, resource ID, recipe ID)
    target_type: Optional[str]        # "enemy", "resource", "item", "npc", "station"

    # WHERE (position + geographic context)
    position_x: float
    position_y: float
    chunk_x: int                      # Derived: int(position_x) // 16
    chunk_y: int                      # Derived: int(position_y) // 16
    locality_id: Optional[str]        # From geographic registry (cached per chunk)
    district_id: Optional[str]        # Parent of locality
    province_id: Optional[str]        # Parent of district
    biome: str                        # ChunkType value at this position

    # WHEN
    game_time: float                  # In-game timestamp
    real_time: float                  # Wall clock (time.time()) for debugging
    session_id: str                   # Which play session

    # WHAT HAPPENED
    magnitude: float                  # Primary numeric value (damage, quantity, gold, etc.)
    result: str                       # "success", "failure", "critical", "dodge", "blocked"
    quality: Optional[str]            # "normal", "fine", "superior", "masterwork", "legendary"
    tier: Optional[int]               # T1-T4 of involved item/resource/enemy

    # TAGS — for matching against entity interests
    tags: List[str]                   # Same tag format as entity tags
                                      # e.g., ["event:gathering", "resource:iron", "biome:quarry",
                                      #         "tool:pickaxe", "tier:2"]

    # CONTEXT SNAPSHOT (what was true at this moment)
    context: Dict[str, Any]           # Flexible dict for event-type-specific data
                                      # Examples:
                                      #   combat: {"weapon": "iron_sword", "enemy_tier": 2,
                                      #            "player_health_pct": 0.7, "combo_count": 3}
                                      #   gathering: {"tool": "steel_pickaxe", "node_remaining_pct": 0.4,
                                      #               "rare_drop": false}
                                      #   crafting: {"recipe_id": "iron_sword_001", "discipline": "smithing",
                                      #              "minigame_score": 0.85, "materials_consumed": {...}}

    # INTERPRETATION TRACKING
    interpretation_count: int = 0     # How many times this event TYPE+subtype has occurred for this actor
                                      # Used for threshold trigger checking
    triggered_interpretation: bool = False  # Did this event trigger a Layer 3 interpretation?
```

## 4.2 Event Types

```python
class EventType(Enum):
    """All trackable event types. Maps to GameEventBus event names."""

    # Combat
    ATTACK_PERFORMED = "attack_performed"
    DAMAGE_TAKEN = "damage_taken"
    ENEMY_KILLED = "enemy_killed"
    PLAYER_DEATH = "player_death"
    DODGE_PERFORMED = "dodge_performed"
    STATUS_APPLIED = "status_applied"
    COMBO_PERFORMED = "combo_performed"

    # Gathering
    RESOURCE_GATHERED = "resource_gathered"
    NODE_DEPLETED = "node_depleted"

    # Crafting
    CRAFT_ATTEMPTED = "craft_attempted"
    ITEM_INVENTED = "item_invented"
    RECIPE_DISCOVERED = "recipe_discovered"

    # Economy/Inventory
    ITEM_ACQUIRED = "item_acquired"
    ITEM_CONSUMED = "item_consumed"
    ITEM_EQUIPPED = "item_equipped"
    TRADE_COMPLETED = "trade_completed"
    REPAIR_PERFORMED = "repair_performed"

    # Progression
    LEVEL_UP = "level_up"
    SKILL_LEARNED = "skill_learned"
    SKILL_USED = "skill_used"
    TITLE_EARNED = "title_earned"
    CLASS_CHANGED = "class_changed"

    # Exploration
    CHUNK_ENTERED = "chunk_entered"
    LANDMARK_DISCOVERED = "landmark_discovered"
    DUNGEON_ENTERED = "dungeon_entered"
    DUNGEON_COMPLETED = "dungeon_completed"

    # Social
    NPC_INTERACTION = "npc_interaction"
    QUEST_ACCEPTED = "quest_accepted"
    QUEST_COMPLETED = "quest_completed"
    QUEST_FAILED = "quest_failed"

    # World/System
    WORLD_EVENT = "world_event"       # Forest fire, invasion, etc.
    POSITION_SAMPLE = "position_sample"  # Periodic breadcrumb (every ~10s)
```

## 4.3 Event Recording Pipeline

### The EventRecorder

Subscribes to Layer 0 (GameEventBus) and writes to Layer 2 (SQLite):

```python
class EventRecorder:
    """
    Subscribes to GameEventBus, converts bus events to WorldMemoryEvents,
    enriches with geographic context, writes to SQLite.
    Singleton.
    """
    _instance = None

    def __init__(self):
        self.event_store: Optional[EventStore] = None  # SQLite backend
        self.geo_registry: Optional[GeographicRegistry] = None
        self.entity_registry: Optional[EntityRegistry] = None
        self.session_id: str = ""

        # Occurrence counters: (actor_id, event_type, event_subtype) → count
        self._occurrence_counts: Dict[Tuple[str, str, str], int] = {}

        # Threshold set for trigger checking
        self._threshold_set: Set[int] = {1, 3, 5, 10, 25, 50, 100, 250, 500,
                                          1000, 2500, 5000, 10000}

    def initialize(self, event_store: 'EventStore',
                   geo_registry: 'GeographicRegistry',
                   entity_registry: 'EntityRegistry',
                   session_id: str):
        """Wire up dependencies and subscribe to bus"""
        self.event_store = event_store
        self.geo_registry = geo_registry
        self.entity_registry = entity_registry
        self.session_id = session_id

        # Subscribe to all bus events
        bus = GameEventBus.get_instance()
        bus.subscribe("*", self._on_bus_event, priority=-10)  # Low priority = runs after game logic

        # Load occurrence counts from database
        self._load_occurrence_counts()

    def _on_bus_event(self, event: 'GameEvent'):
        """Convert a GameEventBus event to a WorldMemoryEvent and record it"""
        # Filter: not all bus events are worth recording
        if not self._should_record(event):
            return

        memory_event = self._convert_event(event)
        if memory_event is None:
            return

        # Enrich with geographic context
        self._enrich_geographic(memory_event)

        # Update occurrence count
        count_key = (memory_event.actor_id, memory_event.event_type, memory_event.event_subtype)
        self._occurrence_counts[count_key] = self._occurrence_counts.get(count_key, 0) + 1
        memory_event.interpretation_count = self._occurrence_counts[count_key]

        # Check if this count hits a threshold (trigger interpretation)
        count = memory_event.interpretation_count
        if count in self._threshold_set:
            memory_event.triggered_interpretation = True

        # Write to SQLite
        self.event_store.record(memory_event)

        # Update entity activity logs
        self._update_activity_logs(memory_event)

        # If interpretation triggered, notify the Interpreter
        if memory_event.triggered_interpretation:
            self._notify_interpreter(memory_event)

    def _should_record(self, event: 'GameEvent') -> bool:
        """Filter bus events — skip visual-only events, high-frequency noise"""
        # Always skip
        skip_types = {"SCREEN_SHAKE", "PARTICLE_BURST", "FLASH_ENTITY",
                      "ATTACK_PHASE"}  # Per-frame visual updates
        if event.event_type in skip_types:
            return False

        # Position samples: only record periodically (handled by separate timer)
        if event.event_type == "POSITION_SAMPLE":
            return True  # These are already rate-limited by the caller

        return True

    def _convert_event(self, event: 'GameEvent') -> Optional[WorldMemoryEvent]:
        """Convert GameEvent to WorldMemoryEvent with proper field mapping"""
        data = event.data

        # Build tags from event data
        tags = self._build_event_tags(event)

        return WorldMemoryEvent(
            event_id=str(uuid.uuid4()),
            event_type=event.event_type.lower(),
            event_subtype=self._derive_subtype(event),
            actor_id=data.get("actor_id", data.get("attacker_id", "player")),
            actor_type=data.get("actor_type", "player"),
            target_id=data.get("target_id", data.get("enemy_id", None)),
            target_type=data.get("target_type", None),
            position_x=data.get("position_x", data.get("position", {}).get("x", 0)),
            position_y=data.get("position_y", data.get("position", {}).get("y", 0)),
            chunk_x=0, chunk_y=0,  # Filled by _enrich_geographic
            locality_id=None, district_id=None, province_id=None,
            biome=data.get("biome", "unknown"),
            game_time=data.get("game_time", 0.0),
            real_time=event.timestamp,
            session_id=self.session_id,
            magnitude=data.get("amount", data.get("quantity", data.get("value", 0.0))),
            result=data.get("result", data.get("outcome", "success")),
            quality=data.get("quality", None),
            tier=data.get("tier", None),
            tags=tags,
            context=self._extract_context(event)
        )

    def _enrich_geographic(self, event: WorldMemoryEvent):
        """Stamp geographic IDs from position"""
        event.chunk_x = int(event.position_x) // 16
        event.chunk_y = int(event.position_y) // 16
        address = self.geo_registry.get_full_address(event.position_x, event.position_y)
        event.locality_id = address.get("locality")
        event.district_id = address.get("district")
        event.province_id = address.get("province")

    def _build_event_tags(self, event: 'GameEvent') -> List[str]:
        """Generate interest-matching tags from event data"""
        tags = [f"event:{event.event_type.lower()}"]
        data = event.data

        # Resource tags
        if "resource_type" in data:
            tags.append(f"resource:{data['resource_type']}")
        if "material_id" in data:
            tags.append(f"resource:{data['material_id']}")

        # Combat tags
        if "damage_type" in data:
            tags.append(f"element:{data['damage_type']}")
        if "weapon_type" in data:
            tags.append(f"combat:{data['weapon_type']}")
        if data.get("is_crit"):
            tags.append("combat:critical")

        # Tier tags
        if "tier" in data:
            tags.append(f"tier:{data['tier']}")

        # Biome tags
        if "biome" in data:
            tags.append(f"biome:{data['biome']}")

        # Discipline tags
        if "discipline" in data:
            tags.append(f"domain:{data['discipline']}")

        # Existing game tags (from the tag system)
        if "tags" in data and isinstance(data["tags"], list):
            for tag in data["tags"]:
                if ":" not in tag:
                    tags.append(f"game:{tag}")
                else:
                    tags.append(tag)

        return tags

    def _update_activity_logs(self, event: WorldMemoryEvent):
        """Append event to relevant entity activity logs"""
        registry = self.entity_registry

        # Actor's log
        actor_entity = registry.get(event.actor_id)
        if actor_entity:
            actor_entity.activity_log.append(event.event_id)
            if len(actor_entity.activity_log) > actor_entity.activity_log_max:
                actor_entity.activity_log.pop(0)

        # Target's log
        if event.target_id:
            target_entity = registry.get(event.target_id)
            if target_entity:
                target_entity.activity_log.append(event.event_id)
                if len(target_entity.activity_log) > target_entity.activity_log_max:
                    target_entity.activity_log.pop(0)

        # Region's log (the locality where this happened)
        if event.locality_id:
            region_entity = registry.get(f"region_{event.locality_id}")
            if region_entity:
                region_entity.activity_log.append(event.event_id)
                if len(region_entity.activity_log) > region_entity.activity_log_max:
                    region_entity.activity_log.pop(0)

    # Note: _generate_primes removed — replaced by static threshold set
    # See TRIGGER_SYSTEM.md for the dual-track trigger architecture
```

### Bus-to-Memory Event Mapping

How existing GameEventBus events map to WorldMemoryEvents:

| Bus Event | Memory Event Type | Key Data Extracted |
|-----------|------------------|-------------------|
| `DAMAGE_DEALT` | `attack_performed` | amount, damage_type, target_id, is_crit, weapon |
| `PLAYER_HIT` | `damage_taken` | amount, damage_type, attacker_id |
| `ENEMY_KILLED` | `enemy_killed` | enemy_id, tier, position, loot |
| `PLAYER_DIED` | `player_death` | killer_id, position |
| `DODGE_PERFORMED` | `dodge_performed` | success (was i-frame hit?) |
| `RESOURCE_GATHERED` | `resource_gathered` | resource_id, quantity, tool, position |
| `ITEM_CRAFTED` | `craft_attempted` | recipe_id, quality, discipline, success |
| `SKILL_ACTIVATED` | `skill_used` | skill_id, tags, mana_cost, targets |
| `LEVEL_UP` | `level_up` | new_level, stat_points |
| `EQUIPMENT_CHANGED` | `item_equipped` | slot, item_id, old_item_id |

Events not currently published by the bus but needed:
- `QUEST_ACCEPTED`, `QUEST_COMPLETED` — add publishing to quest_system.py
- `NPC_INTERACTION` — add publishing to NPC dialogue handling
- `TRADE_COMPLETED` — add publishing to trade system
- `CHUNK_ENTERED` — add publishing to world_system.py chunk loading

## 4.4 Retention Policy — Milestone Preservation

### The Problem

At 2,000-5,000 events per hour of play, a 100-hour save would have 200K-500K events. Most are routine (mined ore, killed wolf, walked to chunk). Keeping everything forever wastes space and slows queries.

### The Solution: Keep Milestones, Prune Routine

For each unique combination of `(actor_id, event_type, event_subtype)`:

**Always Keep:**
1. **First occurrence** — the very first event of this type (historical baseline)
2. **Threshold-indexed events** — every event whose occurrence count matches a trigger threshold (1, 3, 5, 10, 25, 50, 100, 250, 500, 1000, 2500, 5000, 10000)
3. **Power-of-10 milestones** — 100th, 1000th, 10000th occurrence
4. **Events that triggered interpretations** — any event where `triggered_interpretation = True`
5. **Events referenced by Layer 3** — any event_id in an interpreted event's cause chain

**Timeline Markers (Longitude Data):**
6. **One event per time window** — keep at least one event per configurable time interval (e.g., per game-day or per real-hour) to preserve the temporal shape. If the player mined 200 iron in one game-day, we keep one representative from that day even if its index number isn't prime.

**Prune:**
Everything else, after a configurable age threshold (e.g., events older than 50 game-days that don't meet any keep criteria).

### Retention Example

Player has mined 10,000 oak logs over 200 hours of play:

| Kept | Why | Count |
|------|-----|-------|
| 1st oak log | First occurrence | 1 |
| 3rd, 5th, 10th, 25th, 50th, 100th... | Threshold triggers | ~12 |
| 100th, 1000th, 10000th | Power-of-10 milestones | 3 |
| Any that triggered interpretations | Interpretation anchors | varies |
| One per game-day | Timeline longitude | ~200 |
| **Total kept** | | **~1,400-1,500 out of 10,000** |

That's ~15% retention with full temporal coverage and heavy detail at the start.

### Pruning Implementation

```python
class EventRetentionManager:
    """Runs periodically to prune old events"""

    # Configurable thresholds
    PRUNE_AGE_THRESHOLD = 50.0        # Game-time units before events become pruneable
    TIMELINE_WINDOW = 1.0             # Game-time units per mandatory timeline marker
    PRUNE_INTERVAL = 10.0             # How often to run pruning (game-time units)

    def prune(self, event_store: 'EventStore', current_game_time: float):
        """Remove old events that don't meet retention criteria"""
        cutoff_time = current_game_time - self.PRUNE_AGE_THRESHOLD

        # Get all events older than cutoff
        old_events = event_store.query(before_time=cutoff_time)

        # Group by (actor_id, event_type, event_subtype)
        groups = {}
        for event in old_events:
            key = (event.actor_id, event.event_type, event.event_subtype)
            groups.setdefault(key, []).append(event)

        events_to_delete = []
        for key, events in groups.items():
            # Sort by game_time
            events.sort(key=lambda e: e.game_time)

            # Identify which to keep
            kept_times = set()  # For timeline marker dedup
            for event in events:
                keep = False

                # Rule 1: First occurrence (interpretation_count == 1)
                if event.interpretation_count == 1:
                    keep = True

                # Rule 2: Prime-indexed
                elif event.interpretation_count in THRESHOLD_SET:
                    keep = True

                # Rule 3: Power-of-10
                elif event.interpretation_count in {100, 1000, 10000, 100000}:
                    keep = True

                # Rule 4: Triggered interpretation
                elif event.triggered_interpretation:
                    keep = True

                # Rule 5: Referenced by Layer 3 (check via event_store)
                elif event_store.is_referenced_by_interpretation(event.event_id):
                    keep = True

                # Rule 6: Timeline marker (one per window)
                else:
                    time_bucket = int(event.game_time / self.TIMELINE_WINDOW)
                    if time_bucket not in kept_times:
                        keep = True

                if keep:
                    time_bucket = int(event.game_time / self.TIMELINE_WINDOW)
                    kept_times.add(time_bucket)
                else:
                    events_to_delete.append(event.event_id)

        # Batch delete
        if events_to_delete:
            event_store.delete_events(events_to_delete)
            print(f"✓ Pruned {len(events_to_delete)} old events")
```

## 4.5 Position Sampling

The player's position is sampled periodically to create a breadcrumb trail:

```python
class PositionSampler:
    """Records player position every N seconds as a POSITION_SAMPLE event"""

    SAMPLE_INTERVAL = 10.0  # Real seconds between samples

    def __init__(self):
        self._last_sample_time = 0.0
        self._last_position = None

    def update(self, current_time: float, player_position: 'Position',
               player_health_pct: float, is_sprinting: bool,
               is_encumbered: bool):
        """Called each frame — records sample if interval elapsed"""
        if current_time - self._last_sample_time < self.SAMPLE_INTERVAL:
            return

        self._last_sample_time = current_time

        bus = GameEventBus.get_instance()
        bus.publish("POSITION_SAMPLE", {
            "position_x": player_position.x,
            "position_y": player_position.y,
            "health_pct": player_health_pct,
            "is_sprinting": is_sprinting,
            "is_encumbered": is_encumbered,
            "velocity": self._calc_velocity(player_position, current_time),
        }, source="position_sampler")

        self._last_position = player_position.copy()
```


---

# 5. Interpreter System (Layer 3)

## 5.1 Purpose

The Interpreter transforms raw facts (Layer 2) into narrative meaning (Layer 3). It detects patterns, crosses thresholds, and generates **text descriptions** — not JSON effects. This is the "journalist" of the world: it reads the ledger and writes the news.

## 5.2 Trigger Mechanism: Threshold Sequence

> **Full design**: See `TRIGGER_SYSTEM.md` for the complete trigger, cascade, and escalation system.

### The Threshold Sequence

```
1, 3, 5, 10, 25, 50, 100, 250, 500, 1000, 2500, 5000, 10000
```

The Interpreter fires when the occurrence count of an event stream crosses one of these thresholds. This sequence provides:
- **Heavy coverage at the start**: 1st, 3rd, 5th events all trigger
- **Less aggressive growth than exponential**: good for filtered/cataloged counts
- **Natural breakpoints**: 10, 100, 1000 feel meaningful

### Dual-Track Counting

**Track 1 — Individual streams**: Count per `(actor_id, event_type, event_subtype, locality_id)`.
- Player kills 1st wolf in Whispering Woods → count=1 → TRIGGER
- Player kills 3rd wolf → count=3 → TRIGGER
- Player kills 4th wolf → NO trigger
- Player kills 5th wolf → count=5 → TRIGGER

**Track 2 — Regional accumulators**: Count per `(locality_id, event_category)`.
- 3 wolf kills + 2 bear kills + 4 bandit kills in Whispering Woods → regional combat count=9 → NO trigger
- 1 more kill → count=10 → TRIGGER (catches aggregate patterns individual streams miss)

### A Trigger Does NOT Mean Change

Hitting a threshold triggers **evaluation**, not automatic output. The interpreter can:
- **Generate** — create/update an interpretation
- **Ignore** — "not significant enough yet"
- **Absorb** — merge into existing interpretation

### Coverage Analysis

| Occurrences | Thresholds hit | Coverage |
|-------------|---------------|----------|
| 1-10 | 1,3,5,10 = **4** | 40% |
| 1-100 | **8** | 8% |
| 1-1,000 | **10** | 1% |
| 1-10,000 | **13** | 0.13% |

Much sparser than primes — but each trigger is backed by substantial evidence. The regional accumulator provides additional coverage for aggregate patterns.

## 5.3 Interpreted Event Schema

```python
@dataclass
class InterpretedEvent:
    """A narrative description derived from Layer 2 patterns. Layer 3."""

    # Identity
    interpretation_id: str            # UUID
    created_at: float                 # Game time when this interpretation was generated

    # The narrative description — THIS IS THE CORE OUTPUT
    narrative: str                    # Human-readable text description
                                      # "Wolf population is declining in the Whispering Woods.
                                      #  The player has killed 23 wolves in this area over the
                                      #  past 5 game-days, well above the natural recovery rate."

    # Classification
    category: str                     # "population_change", "resource_pressure", "player_milestone",
                                      # "area_danger_shift", "world_event", "economic_shift"
    severity: str                     # "minor", "moderate", "significant", "major", "critical"

    # What triggered this
    trigger_event_id: str             # The Layer 2 event that triggered interpretation
    trigger_count: int                # The threshold count that triggered it
    cause_event_ids: List[str]        # Layer 2 events that form the evidence base

    # Spatial scope
    affected_locality_ids: List[str]  # Which localities this concerns
    affected_district_ids: List[str]  # Which districts
    affected_province_ids: List[str]  # Which provinces (for significant events)
    epicenter_x: float                # Geographic center of the pattern
    epicenter_y: float

    # What this concerns (for routing to affected entities/regions)
    affects_tags: List[str]           # Tags of what's affected
                                      # ["species:wolf", "biome:forest", "resource:wolf_pelt"]
                                      # These are matched against entity/region tags

    # Duration
    is_ongoing: bool                  # Is this still happening or a one-time observation?
    expires_at: Optional[float]       # Game time when this interpretation expires (if ongoing)

    # History tracking
    supersedes_id: Optional[str]      # If this updates a previous interpretation (same pattern,
                                      # higher count), reference the old one
    update_count: int = 1             # How many times this pattern has been re-interpreted
```

## 5.4 The Interpreter

```python
class WorldInterpreter:
    """
    Reads Layer 2 patterns, generates Layer 3 narrative interpretations.
    Called when EventRecorder detects a threshold trigger.
    Singleton.
    """
    _instance = None

    def __init__(self):
        self.event_store: Optional[EventStore] = None
        self.geo_registry: Optional[GeographicRegistry] = None
        self.entity_registry: Optional[EntityRegistry] = None
        self.interpretation_store: Optional[InterpretationStore] = None

        # Pattern evaluators — pluggable rules
        self._evaluators: List[PatternEvaluator] = []

    def initialize(self, event_store, geo_registry, entity_registry, interpretation_store):
        self.event_store = event_store
        self.geo_registry = geo_registry
        self.entity_registry = entity_registry
        self.interpretation_store = interpretation_store

        # Register pattern evaluators
        self._evaluators = [
            PopulationChangeEvaluator(),
            ResourcePressureEvaluator(),
            PlayerMilestoneEvaluator(),
            AreaDangerEvaluator(),
            CraftingTrendEvaluator(),
            ExplorationPatternEvaluator(),
            SocialPatternEvaluator(),
        ]

    def on_trigger(self, trigger_event: WorldMemoryEvent):
        """
        Called when a threshold trigger fires.
        Evaluates all relevant pattern evaluators and generates interpretations.
        """
        for evaluator in self._evaluators:
            if evaluator.is_relevant(trigger_event):
                interpretation = evaluator.evaluate(
                    trigger_event=trigger_event,
                    event_store=self.event_store,
                    geo_registry=self.geo_registry,
                    entity_registry=self.entity_registry,
                    existing_interpretations=self.interpretation_store
                )
                if interpretation is not None:
                    # Check if this supersedes an existing interpretation
                    existing = self.interpretation_store.find_supersedable(
                        category=interpretation.category,
                        affects_tags=interpretation.affects_tags,
                        locality_ids=interpretation.affected_locality_ids
                    )
                    if existing:
                        interpretation.supersedes_id = existing.interpretation_id
                        interpretation.update_count = existing.update_count + 1
                        self.interpretation_store.archive(existing.interpretation_id)

                    self.interpretation_store.record(interpretation)

                    # Propagate to Layers 4/5 (see Section 6)
                    self._propagate(interpretation)

    def _propagate(self, interpretation: InterpretedEvent):
        """Route interpretation to affected regions (narrative propagation)"""
        geo = self.geo_registry

        # Update affected localities
        for locality_id in interpretation.affected_locality_ids:
            region = geo.regions.get(locality_id)
            if region:
                region.state.recent_events.append(interpretation.interpretation_id)
                if interpretation.is_ongoing:
                    region.state.active_conditions.append(interpretation.interpretation_id)
                # Trim to window size
                max_recent = 20
                if len(region.state.recent_events) > max_recent:
                    region.state.recent_events = region.state.recent_events[-max_recent:]

        # Propagate to districts and provinces based on severity
        if interpretation.severity in ("significant", "major", "critical"):
            for district_id in interpretation.affected_district_ids:
                region = geo.regions.get(district_id)
                if region:
                    region.state.recent_events.append(interpretation.interpretation_id)
                    if interpretation.is_ongoing:
                        region.state.active_conditions.append(interpretation.interpretation_id)

        if interpretation.severity in ("major", "critical"):
            for province_id in interpretation.affected_province_ids:
                region = geo.regions.get(province_id)
                if region:
                    region.state.recent_events.append(interpretation.interpretation_id)
                    if interpretation.is_ongoing:
                        region.state.active_conditions.append(interpretation.interpretation_id)
```

## 5.5 Pattern Evaluators

Each evaluator looks for a specific kind of pattern. They're the "reporters" — each covers a different beat.

### Example: Population Change Evaluator

```python
class PopulationChangeEvaluator(PatternEvaluator):
    """Detects when enemy kills in a region exceed natural recovery."""

    RELEVANT_TYPES = {"enemy_killed"}

    def is_relevant(self, event: WorldMemoryEvent) -> bool:
        return event.event_type in self.RELEVANT_TYPES

    def evaluate(self, trigger_event, event_store, geo_registry,
                 entity_registry, existing_interpretations) -> Optional[InterpretedEvent]:
        """
        Check: has the kill rate for this enemy type in this locality
        exceeded a threshold that suggests population impact?
        """
        locality_id = trigger_event.locality_id
        if not locality_id:
            return None

        # Get enemy subtype from the event
        enemy_subtype = trigger_event.event_subtype  # e.g., "killed_wolf"

        # Count kills of this type in this locality over recent time window
        recent_kills = event_store.count_filtered(
            event_type="enemy_killed",
            event_subtype=enemy_subtype,
            locality_id=locality_id,
            since_game_time=trigger_event.game_time - 50.0  # Last 50 game-time units
        )

        # Thresholds (could be configurable per enemy type)
        if recent_kills < 5:
            return None  # Too few to matter

        # Determine severity based on count
        if recent_kills >= 50:
            severity = "major"
            narrative = (f"The {enemy_subtype.replace('killed_', '')} population has been "
                        f"devastated in {geo_registry.regions[locality_id].name}. "
                        f"{recent_kills} have been killed in a short period. "
                        f"The species may take significant time to recover in this area.")
        elif recent_kills >= 20:
            severity = "significant"
            narrative = (f"{enemy_subtype.replace('killed_', '').title()} numbers are noticeably "
                        f"declining in {geo_registry.regions[locality_id].name}. "
                        f"{recent_kills} have been killed recently.")
        elif recent_kills >= 10:
            severity = "moderate"
            narrative = (f"Increased hunting activity has thinned the "
                        f"{enemy_subtype.replace('killed_', '')} population in "
                        f"{geo_registry.regions[locality_id].name}.")
        else:
            severity = "minor"
            narrative = (f"Several {enemy_subtype.replace('killed_', '')}s have been killed "
                        f"in {geo_registry.regions[locality_id].name}.")

        # Get cause events (the actual kill records)
        cause_events = event_store.query(
            event_type="enemy_killed",
            event_subtype=enemy_subtype,
            locality_id=locality_id,
            since_game_time=trigger_event.game_time - 50.0,
            limit=10  # Just the most recent as evidence
        )

        region = geo_registry.regions[locality_id]
        return InterpretedEvent(
            interpretation_id=str(uuid.uuid4()),
            created_at=trigger_event.game_time,
            narrative=narrative,
            category="population_change",
            severity=severity,
            trigger_event_id=trigger_event.event_id,
            trigger_count=trigger_event.interpretation_count,
            cause_event_ids=[e.event_id for e in cause_events],
            affected_locality_ids=[locality_id],
            affected_district_ids=[region.parent_id] if region.parent_id else [],
            affected_province_ids=[],  # Only if severity warrants
            epicenter_x=trigger_event.position_x,
            epicenter_y=trigger_event.position_y,
            affects_tags=[f"species:{enemy_subtype.replace('killed_', '')}",
                         f"biome:{trigger_event.biome}",
                         f"resource:{enemy_subtype.replace('killed_', '')}_pelt"],
            is_ongoing=True,
            expires_at=trigger_event.game_time + 100.0  # Ongoing for 100 game-time units
        )
```

### Other Evaluators (Signature Only)

```python
class ResourcePressureEvaluator(PatternEvaluator):
    """Detects when gathering outpaces node respawn in an area."""
    # Tracks: resource_gathered events per resource type per locality
    # Threshold: gathering rate > estimated respawn rate × 1.5

class PlayerMilestoneEvaluator(PatternEvaluator):
    """Detects notable player achievements worth narrating."""
    # Tracks: first kills, level ups, title earns, craft milestones
    # Fires on first occurrence and at significant counts

class AreaDangerEvaluator(PatternEvaluator):
    """Detects when an area becomes more or less dangerous."""
    # Tracks: player_death + damage_taken frequency per locality
    # Compares to historical baseline

class CraftingTrendEvaluator(PatternEvaluator):
    """Detects crafting specialization and quality trends."""
    # Tracks: craft_attempted per discipline per quality level
    # Detects improving quality over time or discipline focus

class ExplorationPatternEvaluator(PatternEvaluator):
    """Detects exploration milestones and area abandonment."""
    # Tracks: chunk_entered events, time since last visit per area
    # Detects new area discovery or area abandonment

class SocialPatternEvaluator(PatternEvaluator):
    """Detects NPC interaction patterns."""
    # Tracks: npc_interaction frequency per NPC
    # Detects favorite NPCs, avoided NPCs, quest streaks
```

## 5.6 Narrative Propagation — Information State Only

**Critical design decision**: Event propagation produces **narrative text**, not mechanical effects.

When a "forest fire" interpreted event is created:

```python
# WHAT HAPPENS (narrative propagation):
InterpretedEvent(
    narrative="A forest fire has swept through the Northern Pines, consuming "
              "much of the woodland. The fire appears to have started near the "
              "old logging camp and spread quickly through the dry underbrush. "
              "Wildlife has fled the area and timber resources are severely impacted.",
    category="world_event",
    severity="major",
    affects_tags=["terrain:forest", "resource:wood", "species:wildlife",
                  "biome:forest", "feature:pine_forest"],
    is_ongoing=True,
    expires_at=current_game_time + 200.0
)

# WHAT DOES NOT HAPPEN:
# ❌ No {"wood_availability": -0.8, "wildlife_spawn_rate": 0.3}
# ❌ No direct modification of resource node spawn rates
# ❌ No direct modification of enemy spawn tables
# ❌ No JSON effect payloads
```

The narrative text IS the information. A separate downstream system (the gameplay effects system, not part of this design) reads these interpretations and decides what mechanical changes to make. This keeps the memory system pure — it records and interprets, nothing more.

### Why Narrative-Only

1. **Decoupling**: The memory system doesn't need to know about game mechanics. It just knows what happened and what it means in words.
2. **LLM-friendly**: Downstream NPC agents and quest generators consume text, not JSON. Narrative descriptions go directly into LLM prompts as context.
3. **Flexibility**: A human-readable description can mean different things to different consumers. The quest generator reads "forest fire" and creates fire-related quests. The NPC agent reads it and generates worried dialogue. The ecosystem system reads it and adjusts spawn rates. Each consumer interprets the narrative for their own domain.
4. **Debuggability**: You can read the interpretations and immediately understand the world state. No need to decode JSON effect payloads.

### Expiration and Cleanup

Ongoing interpreted events expire:
```python
def cleanup_expired(self, current_game_time: float):
    """Remove expired ongoing conditions from region states"""
    for region in self.geo_registry.regions.values():
        active = []
        for interp_id in region.state.active_conditions:
            interp = self.interpretation_store.get(interp_id)
            if interp and (not interp.expires_at or interp.expires_at > current_game_time):
                active.append(interp_id)
        region.state.active_conditions = active
```


---

# 6. Query Architecture, Aggregation (Layers 4-5), Window System

## 6.1 The Static + Recency Window System

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

## 6.2 Layers 4 and 5: Aggregation

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

## 6.3 The Query Interface — Entity-First

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

## 6.4 Query Examples (User-Specified) — Walkthrough

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


---

# 7. SQLite Schema, Integration Points, File Structure, Build Order

## 7.1 SQLite Schema

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
-- OCCURRENCE COUNTERS (for threshold trigger tracking)
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


-- ============================================
-- DAILY LEDGERS (time-based tracking)
-- See TIME_AND_RECENCY.md for full design
-- ============================================
CREATE TABLE IF NOT EXISTS daily_ledgers (
    game_day INTEGER PRIMARY KEY,
    game_time_start REAL,
    game_time_end REAL,
    data_json TEXT NOT NULL           -- Full DailyLedger serialized
);

CREATE TABLE IF NOT EXISTS meta_daily_stats (
    stat_key TEXT PRIMARY KEY,        -- Single row: "player_meta_stats"
    data_json TEXT NOT NULL           -- Full MetaDailyStats serialized
);


-- ============================================
-- REGIONAL ACCUMULATION COUNTERS
-- See TRIGGER_SYSTEM.md for dual-track triggers
-- ============================================
CREATE TABLE IF NOT EXISTS regional_counters (
    region_id TEXT NOT NULL,
    event_category TEXT NOT NULL,     -- "combat", "gathering", "crafting", etc.
    count INTEGER DEFAULT 0,
    PRIMARY KEY (region_id, event_category)
);

CREATE TABLE IF NOT EXISTS interpretation_counters (
    category TEXT NOT NULL,
    primary_tag TEXT NOT NULL,
    region_id TEXT NOT NULL,
    count INTEGER DEFAULT 0,
    PRIMARY KEY (category, primary_tag, region_id)
);
```

## 7.2 Integration Points with Existing Code

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

## 7.3 File Structure

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
│       │── # Trigger & Time Systems (see TRIGGER_SYSTEM.md, TIME_AND_RECENCY.md)
│       ├── trigger_manager.py        # TriggerManager (dual-track threshold counting)
│       ├── daily_ledger.py           # DailyLedger computation and MetaDailyStats
│       ├── time_envelope.py          # TimeEnvelope computation for interpreter context
│       │
│       │── # Testing
│       └── test_memory_system.py     # Unit tests for all components
│
├── AI-Config.JSON/                   # AI configuration (existing directory from plan)
│   ├── geographic-map.json           # NEW: Region definitions for the world
│   ├── region-name-pools.json        # NEW: Name pools for procedural region naming
│   └── interpreter-thresholds.json   # NEW: Configurable thresholds for pattern evaluators
```

## 7.4 Build Order — Implementation Phases

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
- `interpreter.py` — WorldInterpreter base, threshold checking
- `evaluators/population.py` — first evaluator (wolf kills → population change)
- `evaluators/resources.py` — second evaluator (mining → resource pressure)
- `AI-Config.JSON/interpreter-thresholds.json` — configurable thresholds
- **Test**: Generate enough events to trigger thresholds, verify interpretations created

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

## 7.5 Estimated File Sizes

| File | Est. Lines | Complexity |
|------|-----------|------------|
| `event_schema.py` | 150-200 | Dataclasses, enums |
| `event_store.py` | 250-350 | SQLite CRUD, indexes |
| `interpretation_store.py` | 150-200 | SQLite CRUD for Layer 3 |
| `geographic_registry.py` | 200-300 | Region loading, spatial lookup, cache |
| `entity_registry.py` | 250-350 | Entity CRUD, tag index, loading from NPCs |
| `tag_relevance.py` | 60-100 | Tag matching utility |
| `event_recorder.py` | 300-400 | Bus subscriber, event conversion, enrichment |
| `interpreter.py` | 200-300 | Base interpreter, threshold checking, dispatch |
| `evaluators/*.py` | 100-200 each | 7 evaluators × ~150 = ~1,050 |
| `aggregation.py` | 200-300 | Layer 4/5 maintenance |
| `query.py` | 300-400 | WorldQuery, dual window, result assembly |
| `retention.py` | 150-200 | Pruning logic |
| `position_sampler.py` | 50-80 | Simple timer + publish |
| **Total** | **~2,500-3,500** | |

Plus JSON configs (~200-400 lines) and tests (~500-800 lines).

## 7.6 Dependencies

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

## 7.7 Connection to Downstream Systems

This memory system is **Phase 2.1** of the Living World plan. It provides the data layer that all subsequent phases consume:

- **Phase 2.3 (NPC Agents)**: Call `world_query.query_entity("npc_X")` to get context for NPC dialogue generation
- **Phase 2.4 (Factions)**: Read interpreted events with faction-related tags to track faction state
- **Phase 2.5 (Ecosystem)**: Read resource pressure interpretations to adjust spawn rates
- **Phase 2.6 (World Events)**: Read Layer 5 regional patterns to trigger world events
- **Phase 2.7 (Quest Generation)**: Call `world_query.query_entity()` for quest context
- **Phase 3 (Player Intelligence)**: Query Layer 2 events to build player behavior profile
- **Narrative Threads** (from scratchpad): Layer 3 interpretations become the input for narrative thread creation/management


---

# 8. Relationship to Existing Documents

## 8.1 WORLD_SYSTEM_SCRATCHPAD.md

The scratchpad (Development-Plan/WORLD_SYSTEM_SCRATCHPAD.md) contains the research synthesis and conceptual reasoning that led to this design. Key ideas carried forward:

- **Narrative threads** with canonical facts and distance-based distortion (Sections 152-228 of scratchpad). Layer 3 interpretations become the input for narrative thread creation in future work.
- **Two usage modes** — Reactive (bottom-up from events) and Thematic (top-down developer injection). This system handles the reactive mode. Thematic injection is a future extension.
- **NPCs have beliefs, not facts** — The query system returns context filtered by proximity and interests. NPCs far from an event get less detail. This is the foundation for the Gossamer-style propagation described in the scratchpad.
- **Research sources** — All academic and industry references from the scratchpad remain relevant. See scratchpad Sections 640-665 for the full bibliography.

## 8.2 PART_2_LIVING_WORLD.md

This document implements **Phase 2.1: Memory Layer** from Part 2. The event schema and EventStore design from Part 2 are expanded here into the full 6-layer architecture with geographic context, entity-first queries, interpretation pipeline, and retention policy.

Key differences from the original Part 2 spec:
- **6 layers instead of single EventStore** — Layer 0 (bus), Layer 1 (stat tracker), Layer 2 (events), Layer 3 (interpretations), Layer 4 (local), Layer 5 (regional)
- **Entity-first queries** — Part 2 had a generic query interface. This design starts from entities and radiates outward.
- **Geographic registry** — Not in Part 2. Added to support named regions and spatial context.
- **Interest tag system** — Not in Part 2. Added as the core identity/filtering mechanism.
- **Threshold triggers** — Part 2 used significance scoring. This design uses the threshold sequence (1, 3, 5, 10, 25, 50, 100...) with dual-track counting. See `TRIGGER_SYSTEM.md`.
- **Narrative-only propagation** — Part 2 implied structured effects. This design is purely informational text.
- **Retention policy** — Not in Part 2. Added to manage long-term database size.

## 8.3 OVERVIEW.md (Development Plan)

This system is Phase 2.1 in the dependency graph. It must be complete before:
- Phase 2.3 (NPC Agents) — needs query interface for dialogue context
- Phase 2.4 (Factions) — needs interpreted events for faction state tracking
- Phase 2.5 (Ecosystem) — needs resource pressure data
- Phase 2.6 (World Events) — needs regional pattern detection
- Phase 2.7 (Quest Generation) — needs world context for quest parameters
- Phase 3.1 (Behavior Classifier) — needs Layer 2 event data for player profiling

---

**Document Version**: 1.0
**Last Updated**: 2026-03-16
**Author**: AI Assistant + Project Owner collaboration

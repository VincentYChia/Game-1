# Geographic System Design Document

**Created**: 2026-04-04
**Last Updated**: 2026-04-04
**Status**: Approved for implementation
**Source**: Full design conversation with project owner

---

## 1. Overview

The game world is being restructured from an infinite procedural world to a **finite, layered geographic system** that recreates a believable world. The system has two parallel hierarchies (political and geographic) plus sparse points of interest.

### Generation Pipeline

```
SEED
 │
 ├─ 1. Nation boundaries (template + deformation)
 │
 ├─ 2. Region subdivision (within nations)
 │     │
 │     ├─── POLITICAL BRANCH           GEOGRAPHIC BRANCH
 │     │    3. Provinces                 3. Biomes (derived from
 │     │    4. Districts                    region identity, crosses
 │     │                                    political lines)
 │     │
 │     ├─── DANGER LAYER
 │     │    Ecosystems (3×3 chunk groups)
 │     │    Danger gradient ±2 between neighbors
 │     │
 │     └─── POINTS OF INTEREST
 │          5. Localities (sparse, notable places only)
 │
 └─ 6. Chunk content generation (tiles, resources, enemies)
        Driven by chunk type + danger level
```

### Layer Relationships

- **Political hierarchy** (every chunk belongs to exactly one): Nation → Region → Province → District
- **Geographic layer** (parallel, crosses political lines): Biomes → Chunk Types
- **Danger layer**: Ecosystems (3×3 chunk groups, discrete danger levels)
- **Points of interest** (sparse, don't fill all space): Localities

---

## 2. World Level

| Property | Value | Notes |
|----------|-------|-------|
| Size | 512×512 chunks (8,192×8,192 tiles) | **Code for expansion** — no hardcoded 512 |
| Chunk size | 16×16 tiles | Existing, unchanged |
| Total chunks | 262,144 | |
| Loading | Chunked, not all at once | Existing system, unchanged |
| Player spawn | (0,0) | Wherever that falls on the map; automatically safe |
| Visibility | Player can see full map | No fog of war for now |
| Finite | Yes | Replacing infinite generation |

---

## 3. Nations (STATIC — The Only Static Tier)

| Property | Value |
|----------|-------|
| Count | 5 (support range 3-12, configurable) |
| Minimum area | 30,000 chunks per nation |
| Coverage | Every chunk claimed — no unclaimed wilderness |
| Template maps | 1-3 hand-crafted 512×512 pixel grids with boundary lines |
| Template style | Simple/blocky — deformation does the heavy lifting |
| Contiguity | Required — no nation can be split into islands |
| Minimum corridor | 12 chunks wide — no ultra-thin passages |

### Nation Border Generation

1. **Select template** from 1-3 base maps (seed-based selection)
2. **Deform severely** — think rectangles transformed into articulate detailed country borders
3. **Assign nation IDs** randomly per seed (which nation gets which territory is shuffled)

### Deformation System

| Type | Description |
|------|-------------|
| Border displacement | Noise-based (Perlin/simplex) displacing border chunks. Controls: amplitude, frequency |
| Region scaling | Nations grow/shrink slightly, shifting boundaries |
| **NOT used** | Rotation, mirroring |

### Deformation Constraints

- Nations must remain contiguous after deformation
- No nation smaller than 30,000 chunks after deformation
- No corridor thinner than 12 chunks after deformation
- Deformation is deterministic from seed

---

## 4. Regions (PROCEDURAL)

| Property | Value |
|----------|-------|
| Count per nation | 3-8 (typically 4-6) |
| Size constraint | 10-45% of parent nation's area |
| Subdivision method | Seed-based procedural subdivision of nation territory |
| Boundaries | Deformed (noise-based, like nation borders) |
| Nature | **Geographic** — regions ARE the large-scale geographic identity |
| Naming | Procedural: `[Adjective] [Identity]` (e.g., "Ashen Steppe", "Verdant Lowlands") |
| Contiguity | Required |

### Key Design Rule

**Biomes derive FROM regions, not regions from biomes.** A region IS the large-scale geographic identity (a great forest, a mountain range). Biomes are small-scale texture/variation within that identity.

### Region Identity Types (10 Types)

Each region is assigned one identity that determines what chunk types predominantly generate within it.

| Identity | Real-World Analog | Primary Chunk Types | Secondary Chunk Types |
|----------|------------------|--------------------|-----------------------|
| **Forest** | Temperate woodland | Forest, Dense Thicket | Rocky Forest, Wetland |
| **Mountains** | Mountain range | Rocky Highlands, Quarry, Cave | Deep Cave, Barren Waste |
| **Plains** | Grassland/prairie | Forest (sparse), Quarry | Rocky Highlands, Wetland |
| **Steppe** | Arid grassland | Barren Waste, Quarry | Rocky Highlands, Overgrown Ruins |
| **Lowlands** | River valleys/basins | Wetland, Forest | Lake, River, Rocky Forest |
| **Marshlands** | Swamp/bog | Wetland, Cursed Marsh | Flooded Cave, Lake |
| **Caverns** | Underground networks | Cave, Deep Cave, Crystal Cavern | Flooded Cave |
| **Highlands** | Elevated plateau | Rocky Highlands, Rocky Forest | Quarry, Forest |
| **Lakeland** | Lake district | Lake, River, Wetland | Forest, Flooded Cave |
| **Ruins** | Ancient civilization | Overgrown Ruins, Crystal Cavern | Deep Cave, Dense Thicket |

Generation: ~70% primary chunk types, ~30% secondary, with seed-based variance.

### Region Naming Format

`[Adjective] [Identity]` — e.g., "Whispering Forest", "Iron Mountains", "Bleached Steppe", "Sunken Lowlands"

- Adjective comes from per-nation naming banks (distinct cultural flavor per nation)
- Identity is the geographic type name

---

## 5. Provinces (PROCEDURAL)

| Property | Value |
|----------|-------|
| Area range | 600-2,400 chunks (configurable) |
| Subdivision method | Seed-based procedural subdivision within regions |
| Boundaries | Deformed |
| Nature | **Administrative/named** — named territories within geographic regions |
| Naming | Procedural from seed, per-nation banks |
| Contiguity | Required |

### Province vs Region

- **Region** = geographic identity ("the Iron Mountains")
- **Province** = named place within that geography ("Stormcrest", "Ironwatch")

---

## 6. Districts (PROCEDURAL)

| Property | Value |
|----------|-------|
| Area range | 200-800 chunks (configurable) |
| Subdivision method | Seed-based procedural within provinces |
| Boundaries | Deformed |
| Naming | Procedural from seed |

---

## 7. Biomes (SEPARATE GEOGRAPHIC LAYER)

| Property | Value |
|----------|-------|
| Area range | 400-800 chunks |
| Derived from | Region geographic identity |
| Political boundaries | **Crosses them** — biomes are NOT constrained by province/district lines |
| Nature | Small-scale geographic variation within a region's identity |
| Analogy | A region is "the great forest"; a biome is "the dense thicket" within that forest |

Biome types are essentially the chunk type families — a biome IS the area where a particular chunk type dominates. The region identity drives which biome types can appear.

---

## 8. Localities (SPARSE POINTS OF INTEREST)

| Property | Value |
|----------|-------|
| Coverage | Sparse — only where notable features exist |
| Size | Notable place + adjacent chunks (not a fixed area) |
| Triggers | Dungeons, NPCs, crafting stations, rare resources, etc. |
| Nature | Named points of interest, not administrative divisions |
| Naming | Procedural from seed + feature type |

---

## 9. Chunk Types (15 Types)

Chunk types are **recipes** of existing resources and enemies. No new drops or monsters required — just different permutations and concentrations of existing content.

| Chunk Type | Resources | Enemy Families | Tiles | Narrative |
|---|---|---|---|---|
| **Forest** | Trees (heavy) | Beasts, Oozes | Grass, Dirt | Classic woodland |
| **Dense Thicket** | Trees (very heavy, higher tier bias) | Beasts, Oozes | Grass, Dirt | Overgrown, high density |
| **Cave** | Ores (heavy) | Insects, Constructs | Stone, Dirt | Underground mining |
| **Deep Cave** | Ores (heavy, higher tier bias) | Insects, Constructs, Undead | Stone | Deeper, darker, ancient |
| **Quarry** | Stones (heavy) | Insects, Oozes | Stone, Dirt | Open-pit mining |
| **Rocky Highlands** | Stones, sparse Trees | Beasts, Insects | Stone, Grass | Elevated rocky terrain |
| **Wetland** | Fish, sparse Trees | Oozes, Undead | Water, Mud, Grass | Marshy, shallow water patches |
| **Lake** | Fish (heavy) | — | Water, Grass | Open water, fishing |
| **River** | Fish | — | Water, Grass | Flowing water |
| **Flooded Cave** | Ores, Fish | Insects, Oozes | Stone, Water | Submerged tunnels |
| **Rocky Forest** | Trees, Stones | Beasts, Insects | Grass, Stone | Forest meets rock transition |
| **Crystal Cavern** | Ores, Stones | Oozes (crystal), Constructs | Stone | Gem-rich, shimmering |
| **Overgrown Ruins** | Stones, sparse Trees | Constructs, Oozes | Stone, Grass, Dirt | Ancient structures reclaimed |
| **Barren Waste** | Stones (sparse) | Insects, Undead | Stone, Sand | Desolate, low resources |
| **Cursed Marsh** | Fish (tier bias high), sparse Stones | Oozes, Undead | Water, Mud, Dirt | Dark water, dangerous |

### Enemy Families Reference

All 16 enemies are production ready (including previously testing-only units).

| Family | Enemies | Tier Range | Environment Affinity |
|--------|---------|-----------|---------------------|
| **Beasts** | wolf_grey (T1), wolf_dire (T2), wolf_elder (T3), inferno_drake (T3) | T1-T3 | Open/forest terrain |
| **Oozes** | slime_green (T1), slime_acid (T2), slime_crystal (T3) | T1-T3 | Wet/underground/quarry |
| **Insects** | beetle_brown (T1), beetle_armored (T2), beetle_titan (T4) | T1-T4 | Rock/cave/quarry |
| **Constructs** | golem_stone (T3), golem_crystal (T4) | T3-T4 | Deep cave/ancient |
| **Undead** | void_wraith (T4), void_archon (T4) | T4 | Dark/cursed |
| **Elemental** | storm_titan (T4) | T4 | Open/exposed |
| **Aberration** | entity_primordial (T4) | T4 | Deep/ancient/end-game |

### Spawn System

Chunk types use **weighted odds**, not hard locks. Players won't get resource-locked. Chunk templates heavily bias probabilities but all tier-appropriate enemies can technically appear anywhere.

---

## 10. Danger System

### Ecosystem Sublayer

Danger is organized into **ecosystems** — groups of 3×3 chunks that share the same danger level.

| Property | Value |
|----------|-------|
| Ecosystem size | 3×3 chunks (configurable) |
| Danger assignment | Same level across all 9 chunks in an ecosystem |
| Gradient rule | Neighboring ecosystems can differ by **±2 danger levels** max |
| Biome influence | Biome type modifies danger generation odds (peaceful biome = mostly low, but not barred from high; vice versa) |
| Region influence | Region identity modifies biome generation tendencies |
| Spawn (0,0) | Automatically safe |

**Future consideration**: Ecosystems might also enforce same chunk types within the 3×3 group.

### Danger Levels (6 Discrete)

| Level | Name | T1% | T2% | T3% | T4% | Spawn Density |
|---|---|---|---|---|---|---|
| 1 | Tranquil | 100 | 0 | 0 | 0 | Very sparse |
| 2 | Peaceful | 80 | 15 | 5 | 0 | Sparse |
| 3 | Moderate | 60 | 30 | 10 | 0 | Normal |
| 4 | Dangerous | 25 | 35 | 30 | 10 | Dense |
| 5 | Perilous | 15 | 20 | 45 | 20 | Dense |
| 6 | Lethal | 0 | 15 | 45 | 40 | Very dense |

### Tags for Danger

`population_status` and `resource_status` tags should poll from ecosystems, not individual chunks.

---

## 11. Naming System

**Procedural naming** at all tiers using name banks.

| Tier | Format | Example |
|------|--------|---------|
| Nation | Unique name from bank | "Valdriath", "Korsheim" |
| Region | `[Adjective] [Identity]` | "Ashen Steppe", "Verdant Lowlands" |
| Province | Named place | "Stormcrest", "Ironwatch" |
| District | Named area | "The Hollows", "Greystone Quarter" |
| Locality | Feature-based | "Dragon's Maw", "Elder's Grove" |

### Naming Flavors (5 — Pure Fantasy, No Real Culture Stereotypes)

| Flavor | Style | Adjective Examples | Province Examples |
|--------|-------|-------------------|-------------------|
| **Stoic** | Heavy, northern, grim | Ashen, Iron, Storm, Grim, Frost | Stormcrest, Ironhold, Greywatch |
| **Flowing** | Soft, musical, nature-touched | Verdant, Silver, Misty, Wild | Silvervale, Moonhaven, Dewbrook |
| **Imperial** | Formal, grand, structured | Grand, Golden, Crimson, Noble | Aurelium, Valdris, Corvanta |
| **Stoneworn** | Weathered, ancient, deep | Bitter, Deep, Hollow, Ember | Duskmere, Cindervault, Bleakhaven |
| **Ethereal** | Mystical, luminous, otherworldly | Luminous, Twilight, Opal, Veiled | Aelindra, Lumareth, Orivane |

- Names generated deterministically from world seed
- Name banks are configurable data, not hardcoded
- Each nation gets one flavor assigned randomly per seed

---

## 12. Map Rendering

| Feature | Behavior |
|---------|----------|
| Visibility | Everything drawn — full world visible |
| Zoom behavior | Zoomed out = nation/region borders and labels. Zoom in for province, district, locality detail |
| Borders | Drawn at every tier |
| Labels | Shown per zoom level (like maps in other games) |
| Player can see | Full map from the start (no fog of war for now) |

### Visual Improvements Required

- Chunk tile rendering needs upgrade — less square, more beautiful
- **Blending at chunk boundaries** — no abrupt color changes between adjacent chunks
- New tile types for visual variety (Sand, Mud, Snow, etc.) — visual only, no gameplay changes
- General reweighting of resource/enemy spawns (integrated with biome system)

---

## 13. Tag Library Updates Required

### New address tags needed (not yet in tag_library.py)

| Tag | Layer | Type |
|-----|-------|------|
| `nation` | Layer 2 (or new) | Dynamic, key_tag |
| `region` | Layer 2 (or new) | Dynamic, key_tag |

### Existing tags that align

| Tag | Layer | Status |
|-----|-------|--------|
| `province` | Layer 2 | Exists, keep |
| `district` | Layer 2 | Exists, keep |
| `locality` | Layer 2 | Exists, keep |
| `biome` | Layer 2 | Exists, values TBD (current 12 are placeholders) |
| `scope` | Layer 2 | Exists, values may need update |

### Tags confirmed correct (already committed)

| Tag | Fix Applied |
|-----|-------------|
| `class` | warrior/ranger/scholar/artisan/scavenger/adventurer |
| `title_tier` | novice/apprentice/journeyman/expert/master/special |

### Tags deferred (for NPC/World System development later)

faction, political, military, migration, diplomacy, relation_effect, narrative_role, era_effect, world_theme

---

## 14. Open Items

| Item | Status | Notes |
|------|--------|-------|
| Deformation parameters | TBD | Amplitude, frequency, scaling ranges for noise |
| Template maps | TBD | 1-3 hand-drawn 512×512 grids for nation boundaries |
| Name banks per nation | TBD | Distinct cultural flavors per nation |
| Dungeon spawn rate | Needs adjustment | Current 8% per chunk likely too high for 262K chunks |
| Biome tag values | TBD | Update after chunk type system is implemented |
| Ecosystem same-chunk-type | Future | Consider enforcing same chunk types within 3×3 ecosystem |
| Chunk visual upgrades | TBD | Blending, new tiles, beautiful rendering |
| Spawn density tuning | TBD | Per-danger-level enemy counts and intervals |

---

## 15. Implementation Constraints

- **All size limits configurable** — no hardcoded area values
- **Code for expansion** — world size, nation count, tier counts all configurable
- **Existing chunk loading stays** — not everything in memory at once
- **Sacred boundaries preserved** — no content JSON modifications, no formula changes (per CLAUDE.md)
- **Deterministic from seed** — same seed = same world, always
- **No new enemy drops** — chunk types remix existing resources and enemies only

---

## 16. Existing Systems Affected

| System | Change Needed |
|--------|---------------|
| `systems/biome_generator.py` | Major rework — biomes derive from regions, danger from ecosystems |
| `systems/world_system.py` | Add finite boundary, integrate geographic hierarchy |
| `systems/chunk.py` | Chunks gain nation/region/province/district/biome/ecosystem fields |
| `Combat/combat_manager.py` | Spawn system uses new danger levels + ecosystem grouping |
| `world_system/world_memory/geographic_registry.py` | Rewrite — generated from world, not static JSON |
| `world_system/config/geographic-map.json` | Becomes nation templates + naming config |
| `world_system/world_memory/tag_library.py` | Add nation, region tags; update biome values later |
| `rendering/renderer.py` (render_map_ui) | Add borders/labels at all tiers with zoom levels + visual blending |
| `data/models/world.py` | Add new ChunkTypes, geographic fields, danger levels |
| `core/config.py` | Add world size, geographic config constants |
| `Definitions.JSON/Chunk-templates-2.JSON` | Expand for 15 chunk types + 6 danger levels |
| `Definitions.JSON/hostiles-testing-integration.JSON` | Promote to production (inferno_drake, void_archon, storm_titan) |

---

## 17. Summary Diagram

```
512×512 World (finite, coded for expansion)
 │
 ├── 5 Nations (STATIC templates + severe deformation)
 │    min 30K chunks, 12-chunk corridor, contiguous
 │    Nation ID randomly assigned per seed
 │
 │    └── 3-8 Regions each (PROCEDURAL, deformed)
 │         10-45% of nation area
 │         10 identity types: Forest, Mountains, Plains, Steppe,
 │         Lowlands, Marshlands, Caverns, Highlands, Lakeland, Ruins
 │         Named: "[Adjective] [Identity]"
 │         │
 │         ├── POLITICAL: Provinces (600-2400 chunks)
 │         │    └── Districts (200-800 chunks)
 │         │
 │         ├── GEOGRAPHIC: Biomes (400-800 chunks)
 │         │    Crosses political boundaries
 │         │    Derived from region identity
 │         │    15 chunk types (resource/enemy remixes)
 │         │
 │         ├── DANGER: Ecosystems (3×3 chunk groups)
 │         │    6 discrete levels (Tranquil → Lethal)
 │         │    ±2 gradient between neighbors
 │         │    Biome influences odds, regions influence biomes
 │         │
 │         └── POI: Localities (sparse, notable + adjacent)
 │
 └── 16 Production Enemies across 7 families
      Spawns driven by chunk type + ecosystem danger level
      Weighted odds, not hard locks

Naming: Procedural, per-nation cultural banks, all tiers
Map: Everything visible, zoom for detail, blended chunk visuals
```

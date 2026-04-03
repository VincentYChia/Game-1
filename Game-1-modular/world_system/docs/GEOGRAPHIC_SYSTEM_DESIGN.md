# Geographic System Design Document

**Created**: 2026-04-03
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
 │     │    3. Provinces                 3. Biomes
 │     │    4. Districts                    (derived from region identity,
 │     │                                     crosses political lines)
 │     │
 │     └─── POINTS OF INTEREST
 │          5. Localities (sparse, notable places only)
 │
 └─ 6. Chunk content generation (tiles, resources, enemies)
        Driven by biome type + danger level
```

### Layer Relationships

- **Political hierarchy** (every chunk belongs to exactly one): Nation → Region → Province → District
- **Geographic layer** (parallel, crosses political lines): Biomes
- **Points of interest** (sparse, don't fill all space): Localities

---

## 2. World Level

| Property | Value | Notes |
|----------|-------|-------|
| Size | 512×512 chunks (8,192×8,192 tiles) | **Code for expansion** — no hardcoded 512 |
| Chunk size | 16×16 tiles | Existing, unchanged |
| Total chunks | 262,144 | |
| Loading | Chunked, not all at once | Existing system, unchanged |
| Player spawn | (0,0) | Wherever that falls on the map |
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
| Nature | **Geographic** — regions represent large-scale geographic identity |
| Naming | Procedural from seed, with per-nation naming banks |
| Contiguity | Required |

### Key Design Rule

**Biomes derive FROM regions, not regions from biomes.** A region IS the large-scale geographic identity (a great forest, a mountain range, coastal wetlands). Biomes are small-scale texture/variation within that identity.

### Region Identity Types

**TBD** — To be defined in parallel with chunk type brainstorming. Examples might include: forested highlands, arid plains, coastal wetlands, volcanic mountains, frozen tundra, dense jungle, etc. The specific list will be determined during implementation.

---

## 5. Provinces (PROCEDURAL)

| Property | Value |
|----------|-------|
| Area range | 600-2,400 chunks (configurable) |
| Subdivision method | Seed-based procedural subdivision within regions |
| Boundaries | Deformed |
| Nature | **Administrative/named** — named territories within geographic regions |
| Naming | Procedural from seed |
| Contiguity | Required |

### Province vs Region

- **Region** = geographic identity ("the northern highlands")
- **Province** = named place within that geography ("Ironwatch", "Stormcrest")

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

### Biome Types

**TBD** — Current 12 chunk types are insufficient. New biome types to be brainstormed in parallel with region identity types. The current BiomeGenerator approach (biomes driving everything) is inverted and needs rework.

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

## 9. Danger System

**Changed from distance-based to geography-based.**

Current system: Danger radiates from spawn (safe zone ±8 chunks). This is being replaced.

New system: Danger is tied to **geography, chunks, and biomes**. Certain regions/biomes are inherently dangerous. Spawn area (0,0) is automatically safe (existing behavior preserved).

Specific danger rules TBD during biome/chunk type design.

---

## 10. Naming System

**Procedural naming** at all tiers using name banks.

- Each nation should have a distinct naming flavor/bank (one sounds Norse, another Latin, etc.)
- Names generated deterministically from world seed
- Name banks are configurable data (JSON), not hardcoded
- Applied to: nations, regions, provinces, districts, localities

---

## 11. Map Rendering

| Feature | Behavior |
|---------|----------|
| Visibility | Everything drawn — full world visible |
| Zoom behavior | Zoomed out = nation/region borders and labels. Zoom in for province, district, locality detail |
| Borders | Drawn at every tier |
| Labels | Shown per zoom level (like maps in other games) |
| Player can see | Full map from the start (no fog of war for now) |

---

## 12. Tag Library Updates Required

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
| `biome` | Layer 2 | Exists, values TBD |
| `scope` | Layer 2 | Exists, values may need update |

### Tags confirmed correct (already fixed)

| Tag | Fix Applied |
|-----|-------------|
| `class` | warrior/ranger/scholar/artisan/scavenger/adventurer |
| `title_tier` | novice/apprentice/journeyman/expert/master/special |

### Tags deferred (for NPC/World System development later)

faction, political, military, migration, diplomacy, relation_effect, narrative_role, era_effect, world_theme

### Tags deferred (values TBD after geographic system built)

biome (current 12 values are placeholders)

---

## 13. Open Items

| Item | Status | Notes |
|------|--------|-------|
| Region identity types | TBD | Define in parallel with chunk type brainstorming |
| Chunk types (beyond current 12) | TBD | Next design task after this doc |
| Biome types/values | TBD | Depends on region identities and chunk types |
| Dungeon spawn rate | Needs adjustment | Current 8% per chunk may be too high for 262K chunks |
| Danger progression rules | TBD | Geography-based, not distance-based |
| Specific deformation parameters | TBD | Amplitude, frequency, scaling ranges |
| Template maps | TBD | 1-3 hand-drawn 512×512 grids |
| Name banks per nation | TBD | Distinct cultural flavors |

---

## 14. Implementation Constraints

- **All size limits configurable** — no hardcoded area values
- **Code for expansion** — world size, nation count, tier counts all configurable
- **Existing chunk loading stays** — not everything in memory at once
- **Sacred boundaries preserved** — no content JSON modifications, no formula changes (per CLAUDE.md)
- **Deterministic from seed** — same seed = same world, always

---

## 15. Existing Systems Affected

| System | Change Needed |
|--------|---------------|
| `systems/biome_generator.py` | Major rework — biomes now derive from regions, not drive everything |
| `systems/world_system.py` | Add finite boundary, integrate geographic hierarchy |
| `systems/chunk.py` | Chunks gain nation/region/province/district/biome fields |
| `world_system/world_memory/geographic_registry.py` | Rewrite — generated from world, not static JSON |
| `world_system/config/geographic-map.json` | Becomes nation templates + naming config |
| `world_system/world_memory/tag_library.py` | Add nation, region tags; update biome values later |
| `rendering/renderer.py` (render_map_ui) | Add borders/labels at all tiers with zoom levels |
| `data/models/world.py` | Add ChunkType expansions, geographic fields |
| `core/config.py` | Add world size, geographic config constants |

---

## 16. Summary Diagram

```
512×512 World (finite, coded for expansion)
 │
 ├── 5 Nations (STATIC templates + severe deformation)
 │    min 30K chunks, 12-chunk corridor, contiguous
 │    Nation ID randomly assigned per seed
 │
 │    └── 3-8 Regions each (PROCEDURAL, deformed)
 │         10-45% of nation area
 │         Geographic identity (drives biomes)
 │         │
 │         ├── POLITICAL: Provinces (600-2400 chunks)
 │         │    └── Districts (200-800 chunks)
 │         │
 │         ├── GEOGRAPHIC: Biomes (400-800 chunks)
 │         │    Crosses political boundaries
 │         │    Derived from region identity
 │         │
 │         └── POI: Localities (sparse, notable + adjacent)
 │
 └── Chunk Content: tiles, resources, enemies
      Driven by biome + danger (geography-based, not distance-based)

Naming: Procedural, per-nation banks, all tiers
Map: Everything visible, zoom for detail
```

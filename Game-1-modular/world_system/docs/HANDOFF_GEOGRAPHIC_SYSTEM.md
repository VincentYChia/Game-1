# Geographic System — Handoff Status

**Date**: 2026-04-06
**Branch**: `claude/review-world-system-BcN51`
**Session**: Full geographic system implementation + WMS integration

---

## What Was Built

### Core Geographic System (`systems/geography/`, ~4,000 LOC)

| Module | Lines | Purpose |
|--------|-------|---------|
| `models.py` | 580 | Enums (ChunkType 21, DangerLevel 6, RegionIdentity 10), dataclasses, WorldMap with save/load |
| `config.py` | 160 | All limits configurable via JSON |
| `noise.py` | 230 | Deterministic hash noise, fractal noise, Voronoi subdivision |
| `nation_generator.py` | 280 | Template + severe deformation + constraints |
| `region_generator.py` | 180 | Noise-perturbed Voronoi, identity assignment |
| `political_generator.py` | 200 | Province + district subdivision |
| `biome_generator.py` | 100 | Chunk types from region identity |
| `ecosystem_generator.py` | 200 | 3x3 danger grouping, 6 levels, ±2 gradient |
| `name_generator.py` | 280 | 5 cultural flavors, procedural naming |
| `world_generator.py` | 210 | Full pipeline orchestrator including villages |
| `village_generator.py` | 300 | Config-driven village placement with tiers |
| `setting_resolver.py` | 75 | Setting tag resolution from chunk features |

### WMS Integration

| File | What Changed |
|------|-------------|
| `tag_library.py` | Added `nation`, `region`, `resource_harvesting` tags. Updated `biome` values to 15 chunk types. Fixed `class` and `title_tier` values. |
| `geographic_registry.py` | Added `load_from_world_map()` to populate from WorldMap |
| `world_memory_system.py` | Prefers WorldMap over static JSON. Passes world_map to event_recorder. |
| `event_recorder.py` | Accepts world_map reference (for future use). No tag injection — respects layer boundaries. |
| `evaluators/ecosystem_resource_depletion.py` | NEW — Layer 2 evaluator producing `resource_harvesting` milestone events |

### Game Integration

| System | What Changed |
|--------|-------------|
| `systems/world_system.py` | Geographic map generation, finite bounds, village overlay (walls persist on every chunk load), debug stats, village NPC definitions |
| `systems/chunk.py` | Geographic data bridge table (NewChunkType → ChunkType), danger-aware resource spawning |
| `Combat/combat_manager.py` | 6 danger levels, 21 chunk type mappings |
| `core/game_engine.py` | Village NPC spawning from geographic data |
| `rendering/renderer.py` | Procedural terrain, pre-scaled map UI with labels |
| `rendering/terrain_renderer.py` | Noise-varied tile colors with detail textures |
| `rendering/map_cache.py` | Pre-rendered blurred map image with borders |
| `data/models/world.py` | 9 new ChunkType enum values |
| `data/databases/resource_node_db.py` | Mixed-resource chunk types |
| `entities/character.py` | Death handler kwargs fix |

### JSON Files Created/Modified

| File | Purpose |
|------|---------|
| `Definitions.JSON/village-config.JSON` | 5 village tiers (2x2→5x5), danger-based selection, NPC templates |
| `Definitions.JSON/Chunk-templates-2.JSON` | 9 new chunk templates (21 total) |
| `Definitions.JSON/combat-config.JSON` | 6 danger level spawn configs |
| `Definitions.JSON/world_generation.JSON` | Dungeon rate 0.01 (~2500 per world) |
| `Definitions.JSON/map-waypoint-config.JSON` | Zoom range 0.08-4.0 |
| `Update-1/npcs-village-dummy.JSON` | Village NPC definitions |

---

## Tag Architecture Decisions

### What was added/modified

- **Layer 2 `resource_harvesting`**: NEW. Values: `depleted_50`, `scarce`, `exhausted`, `completely_harvested`. Produced as own InterpretedEvent by ecosystem_resource_depletion evaluator. Feeds into Layer 3 `resource_status` via tag inheritance.
- **Layer 2 `biome`**: Updated values to match 15 new chunk types.
- **Layer 2 `nation`, `region`**: NEW address tags added.

### What was NOT changed (by design)

- **Layer 3 `setting`**: Stays at Layer 3. Environmental interpretation, not raw geography. Values need review to reflect new chunk types (future task).
- **Layer 3 `terrain`**: Unchanged. Values may need alignment with new biomes (future task).
- **Layer 3 `population_status`**: Unchanged. No population cap system exists to drive it meaningfully. Deferred.
- **Layer 3 `resource_status`**: Unchanged. Will be produced by Layer 3 evaluators that inherit `resource_harvesting` from Layer 2.
- **Event recorder**: Does NOT inject any Layer 3+ tags. Respects layer boundaries.

---

## Current World Stats

- **World size**: 512×512 chunks (262,144 total)
- **Generation time**: ~15s first run, ~1s cached
- **Nations**: 5 (configurable 3-12)
- **Regions**: ~23 with 10 identity types
- **Provinces**: ~200
- **Districts**: ~600
- **Villages**: ~2500 (5 tiers, danger-based selection)
- **Village NPCs**: ~13,000
- **Dungeons**: ~2500
- **Wetland distribution**: ~12% (rebalanced from 20%)

---

## Known Issues & Next Steps

### High Priority

1. **`setting` tag values need review** — current Layer 3 values (village, settlement, wilderness, dungeon, underground, ruins, crossroads, market, camp) don't fully reflect new chunk types. Need alignment pass.

2. **`terrain` tag values need review** — current Layer 3 values (forest, hills, cave, clearing, path, rocky, dense, water, plains, swamp) overlap with `biome` but are coarser. May need alignment.

3. **Layer 3 evaluators don't exist yet** — `resource_status` should be produced by Layer 3 from inherited `resource_harvesting` events. `setting` and `terrain` need Layer 3 evaluators that consolidate Layer 2 geographic data. `population_status` deferred (no population cap system).

4. **Village walls breakability** — config says breakable=true, collectible=false, base_health=200 but the actual wall tiles are just stone tiles with walkable=False. No HP/breakability system implemented on non-resource tiles.

### Medium Priority

5. **Deformation needs more randomness** — angular sector template is predictable. Need alternate base maps.
6. **Entity visual scaling** — `ENTITY_VISUAL_SCALE` at 1.0, needs proper implementation.
7. **Promote testing enemies** — inferno_drake, void_archon, storm_titan ready in Update-1.
8. **`overgrown_ruins` fallback** — `_spawn_resources_fallback()` doesn't recognize "ruins" substring.

### Lower Priority / Future

9. **Map UI polish** — clearer boundaries, zone highlighting, label readability.
10. **Alternate nation templates** — 2-3 more for variety.
11. **Ecosystem same-chunk-type** — enforce within 3×3 groups.
12. **Layers 3-7 activation** — schemas exist but no code writes to them.
13. **Deferred tags** — faction, political, military, migration, diplomacy, etc.

---

## Architecture Notes

### Generation Pipeline
```
Seed → Nations (template+deform) → Regions (Voronoi+noise)
  → Provinces → Districts  [political branch]
  → Biomes (from region identity)  [geographic branch]
  → Ecosystems (3x3 danger groups)  [danger branch]
  → Villages (config-driven, danger-tiered)  [POI branch]
  → Names (5 cultural flavors)
```

### Tag Flow for Resource Depletion
```
Player gathers resources → RESOURCE_GATHERED event (Layer 0/1)
  → EventRecorder records with Layer 1 tags (resource, tier, etc.)
  → TriggerManager fires at thresholds
  → ecosystem_resource_depletion evaluator (Layer 2)
    → Produces InterpretedEvent with resource_harvesting:{milestone}
    → Tags: resource_harvesting, domain:gathering, action:deplete,
            scope:local, metric:percentage, target:node
  → [Future] Layer 3 inherits resource_harvesting tags
    → Produces resource_status:{interpretation} (scarce/critical/etc.)
```

### Chunk Type System
ChunkType enum values must contain "forest"/"quarry"/"cave" substrings for resource spawning. Resource system supports compound types. Danger level from geographic ecosystem determines resource tier range.

---

## Update 2026-04-16: Hierarchy Alignment

The WMS `RegionLevel` enum now maps 1:1 to the game's 6-tier geography
(`World → Nation → Region → Province → District → Locality`).
Previously the WMS used 5 shifted labels (`REALM/NATION/PROVINCE/DISTRICT/
LOCALITY`) where WMS "REALM" held the game World and every other level was
off by one. That shift is gone:

- `RegionLevel` gained `WORLD` and `REGION` values.
- `geographic_registry.load_from_world_map()` now assigns each game tier
  to its matching WMS level.
- Game `Locality` (POI) is represented as a sparse 6th tier — only
  present when a chunk has a POI, otherwise Layer 2 capture falls back
  to the `district:` tag as the finest address.
- Address tag prefixes `world: / nation: / region: / province: /
  district: / locality:` are now reserved facts assigned at L2 capture
  and propagated unchanged up the layer stack. See
  `ARCHITECTURAL_DECISIONS.md` §6.
- Layer 5 was renamed from `RealmSummaryEvent` to `RegionSummaryEvent`
  and retargeted from world-aggregation to region-aggregation (one tier
  up from Layer 4's province summaries). Layers 6 and 7 are future
  copies of L5's pattern at nation and world scope respectively.

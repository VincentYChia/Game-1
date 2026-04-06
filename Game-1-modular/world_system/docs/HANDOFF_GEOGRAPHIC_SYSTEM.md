# Geographic System — Handoff Status

**Date**: 2026-04-06
**Branch**: `claude/review-world-system-BcN51`
**Session**: Full geographic system implementation

---

## What Was Built

### Core Geographic System (`systems/geography/`, ~3,500 LOC)

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
| `world_generator.py` | 200 | Full pipeline orchestrator |
| `village_generator.py` | 300 | Config-driven village placement |
| `setting_resolver.py` | 105 | Setting/population/resource tag resolution |

### Integration Points

| System | What Changed |
|--------|-------------|
| `systems/world_system.py` | Geographic map generation, finite bounds, village overlay, debug stats |
| `systems/chunk.py` | Geographic data on chunks, bridge table, danger-aware resources |
| `Combat/combat_manager.py` | 6 danger levels, 21 chunk type mappings |
| `core/game_engine.py` | Village NPC spawning |
| `rendering/renderer.py` | Procedural terrain, map UI with pre-scaled image + labels |
| `rendering/terrain_renderer.py` | Noise-varied tile colors with detail textures |
| `rendering/map_cache.py` | Pre-rendered blurred map image with borders |
| `data/models/world.py` | 9 new ChunkType enum values |
| `data/databases/resource_node_db.py` | Mixed-resource chunk types |
| `data/databases/map_waypoint_db.py` | Biome colors for all chunk types |
| `world_system/world_memory/tag_library.py` | `nation`, `region` address tags, updated biome values |
| `world_system/world_memory/geographic_registry.py` | `load_from_world_map()` method |
| `world_system/world_memory/world_memory_system.py` | Prefers WorldMap over static JSON |
| `entities/character.py` | Death handler kwargs fix |

### JSON Files

| File | Purpose |
|------|---------|
| `Definitions.JSON/village-config.JSON` | Village tiers, entrances, NPC templates, placement rules |
| `Definitions.JSON/Chunk-templates-2.JSON` | 9 new chunk templates (21 total) |
| `Definitions.JSON/combat-config.JSON` | 6 danger level spawn configs |
| `Definitions.JSON/world_generation.JSON` | Dungeon rate tuned (0.01) |
| `Definitions.JSON/map-waypoint-config.JSON` | Zoom range (0.08-4.0) |
| `Update-1/npcs-village-dummy.JSON` | Village NPC definitions |

---

## Current World Stats (Typical Generation)

- **World size**: 512×512 chunks (262,144 total)
- **Generation time**: ~15s first run, ~1s cached
- **Nations**: 5 (configurable 3-12)
- **Regions**: ~23 with 10 identity types
- **Provinces**: ~200 (600-2400 chunks each)
- **Districts**: ~600 (200-800 chunks each)
- **Villages**: 30 (3 tiers: Hamlet/Village/Town)
- **Village NPCs**: ~150-170
- **Dungeons**: ~2500 across world
- **Danger distribution**: ~35% moderate, ~27% dangerous, ~23% peaceful, ~7% perilous, ~6% tranquil, ~1% lethal

---

## Known Issues & Next Steps

### High Priority

1. **Wetland distribution imbalance** — marshlands + lakeland regions both heavily generate wetland chunks, causing up to 20% wetland. Rebalance `REGION_PRIMARY_CHUNKS` mappings.

2. **Missing `overgrown_ruins` chunk type** — the `_spawn_resources_fallback()` in chunk.py doesn't recognize "ruins" substring. Works fine when ResourceNodeDB is loaded but fallback path breaks.

3. **Village walls don't persist across saves** — walls are applied when chunk loads but aren't saved. If a chunk is saved and reloaded, walls need to be re-applied.

4. **Map image not regenerated on cache load** — if nation colors change (different seed), cached map images from a different session may be stale.

### Medium Priority

5. **Deformation needs more randomness** — current angular sector template produces somewhat predictable nation shapes. Need alternate base templates and stronger deformation parameters.

6. **Entity visual scaling** — `Config.ENTITY_VISUAL_SCALE` exists at 1.0 but needs proper implementation with coordinated movement/range/attack scaling.

7. **Setting tag not wired to event recorder** — `setting_resolver.py` exists but the WMS event recorder doesn't call it when enriching events.

8. **Population/resource status are baselines only** — currently derived from danger level. WMS evaluators should override based on actual kill/gather event data.

9. **Promote testing enemies** — inferno_drake, void_archon, storm_titan are production-ready in Update-1 but need proper chunk template integration.

### Lower Priority / Future

10. **Map UI polish** — clearer boundaries, zone highlighting, better label readability at all zooms.
11. **Alternate base maps** — 2-3 more nation templates for variety.
12. **Ecosystem same-chunk-type** — enforce same chunk types within 3×3 ecosystem groups.
13. **Layers 3-7 activation** — WMS layers above 2 have schemas but no code writes to them.
14. **Deferred tags** — faction, political, military, migration, diplomacy, relation_effect, narrative_role, era_effect, world_theme.
15. **BalanceValidator** — spec only in Development-Plan, no code.
16. **Async agent runner** — for background AI tasks.
17. **Debug dashboard** — F1 overlay showing geographic info.

---

## Architecture Notes

### Generation Pipeline
```
Seed → Nations (template+deform) → Regions (Voronoi+noise)
  → Provinces → Districts  [political branch]
  → Biomes (from region identity)  [geographic branch]
  → Ecosystems (3x3 danger groups)  [danger branch]
  → Villages (config-driven)  [POI branch]
  → Names (5 cultural flavors)
```

### Map Rendering
Pre-rendered 2048×2048 image (blurred, bordered). Scaled once on zoom change, blit offset only during drag. Labels drawn fresh each frame with overlap prevention and zoom-dependent tiers.

### Chunk Type System
ChunkType enum values must contain "forest"/"quarry"/"cave" substrings for resource spawning. Resource system supports compound types (e.g., "rocky_forest_quarry" → both trees and stones). Danger level from geographic ecosystem determines resource tier range.

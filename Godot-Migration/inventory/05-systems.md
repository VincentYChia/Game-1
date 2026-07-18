# 05 — `systems/` Managers: Porting Contract (Python/Pygame → Godot 4 .NET)

**Source root**: `Game-1-modular/systems/` (21 top-level modules + `__init__.py` = ~12,357 LOC, plus the
`systems/geography/` subpackage = 13 files / ~3,329 LOC that the "21 files" framing missed but which IS the
world-gen determinism core). **Total ≈ 15,686 LOC.**

All line numbers verified against the working tree on 2026-07-17 (branch `crux-foundry`). The CODE is the source
of truth; several doc claims are corrected inline.

---

## 1. File Table

| File | LOC | Responsibility | Disposition |
|---|---|---|---|
| `world_system.py` | 1,677 | `WorldSystem` — chunk load/unload/stream, finite geographic world, villages, dungeons entrances, stations, placed entities, spawn/death chests, per-chunk save files, world save state | **port-to-C#** (pure logic) + thin engine glue for viewport queries |
| `chunk.py` | 723 | `Chunk` — 16×16 tile generation, resource spawning (template/DB/fallback paths), template-lock, modification tracking, save/restore | **port-to-C#** (pure logic; bit-exact RNG required) |
| `biome_generator.py` | 604 | Legacy `BiomeGenerator` — hash-based chunk typing, chunk seed derivation (Szudzik pairing), dungeon spawn rolls. **Still load-bearing**: `WorldSystem` always constructs it and dungeon spawns + chunk seeds route through it (world_system.py:57, 631, chunk.py:98) | **port-to-C#** (the hash functions verbatim) |
| `geography/` (13 files) | 3,329 | Finite 512×512 world: nations→regions→provinces→districts→biomes→ecosystems→names→villages. Deterministic hash/Voronoi pipeline, gzip'd WorldMap cache | **port-to-C#** (pure math, no engine deps, no numpy) |
| `save_manager.py` | 740 | `SaveManager` — full game-state JSON serialization, atomic write + `.bak`, corrupt-save recovery, save-file listing | **port-to-C#** |
| `dungeon.py` | 805 | `LootChest`, `DungeonInstance`, `DungeonManager` — instanced 32×32 dungeons, waves, loot generation, serialization | **port-to-C#** |
| `collision_system.py` | 599 | `CollisionSystem` — Bresenham LoS, walkability, slide movement, A* pathfinding (A* is dead code, see §2) | **decompose**: LoS/walkability port-to-C#; A* **drop-dead-code**; long-term Godot physics may replace LoS raycast |
| `quest_system.py` | 595 | `Quest`, `QuestManager` — objectives, baselines, reward grant, LLM reward adapt hooks (sidecar), archive hook | **port-to-C#**; LLM adapt/pregen calls become IPC to sidecar |
| `npc_system.py` | 169 | `NPC` — speechbank dialogue cycling, quest offer/turn-in helpers, proximity check | **port-to-C#** |
| `title_system.py` | 143 | `TitleSystem` — title award w/ RNG acquisition methods, bonus-key normalization (camelCase/snake_case/typo tolerance) | **port-to-C#** |
| `class_system.py` | 100 | `ClassSystem` — class bonuses, JSON-driven tag→tool bonus table | **port-to-C#** |
| `skill_unlock_system.py` | 205 | `SkillUnlockSystem` — trigger-based skill unlock checks, pending/cost flow | **port-to-C#** |
| `natural_resource.py` | 202 | `NaturalResource` — HP/deplete/respawn, JSON loot tables + hardcoded fallback, `get_color()` (render-only) | **port-to-C#**; `get_color()` moves to view layer |
| `map_waypoint_system.py` | 720 | `MapWaypointSystem` — explored-chunk tracking, waypoints, teleport cooldown, map UI state (zoom/scroll/drag), save/load | **decompose**: exploration/waypoint/teleport logic port-to-C#; map UI state (zoom, scroll, drag, `map_open`) **engine-replaces** (Godot Control) |
| `turret_system.py` | 566 | `TurretSystem` — placed-entity AI (turrets, traps, bombs, healing beacon, net launcher, EMP), tag-effect dispatch | **port-to-C#** (depends on effect executor + combat manager ports) |
| `potion_system.py` | 388 | `PotionEffectExecutor` — tag-driven potion effects → `ActiveBuff` | **port-to-C#** |
| `encyclopedia.py` | 332 | `Encyclopedia` — UI state (tab/scroll) + text formatting for guide/invented-recipes | **decompose**: recipe-text formatting port-to-C# (or into UI); tab/scroll state **engine-replaces** |
| `training_dummy.py` | 298 | `TrainingDummy(Enemy)` — dev/test target with console-print tag validation | **port-to-C#** (low priority, dev tool; keep — it's the tag-system test harness) |
| `attack_effects.py` | 269 | `AttackEffectsManager` — tag→color mapping, transient combat VFX records (slash/thrust/burst/blocked/area) | **engine-replaces**: Godot particles/Node2D-3D VFX. **Must preserve**: tag→color table + effect-selection rules (§9) |
| `quest_log_overlay.py` | 248 | Pygame quest-log panel drawing + abandon-button hit rects | **engine-replaces** (Godot Control scene); keep objective/progress format strings as parity checklist |
| `llm_item_generator.py` | 1,531 | Claude-based invented-item generation, threading, loading-state, cache, sanitizer, fallback items | **stays-python-sidecar** (generation); **port-to-C#**: `_sanitize_item_data` gate, `calculate_minimum_tier`, `extract_placement_data`, loading-state UI notion. IPC contract in §2.13 |
| `crafting_classifier.py` | 1,421 | CNN/LightGBM recipe validation: color encoder, image renderers, feature extractors, model backends | **stays-python-sidecar** entirely (feature/image encoding MUST stay next to the models — it's training-coupled). Game sends placement JSON; sidecar returns verdict. IPC contract in §2.14 |
| `__init__.py` | 22 | Re-exports `Quest, QuestManager, NPC, TitleSystem, ClassSystem, Encyclopedia, NaturalResource, Chunk, WorldSystem` | n/a (namespace) |

Geography subpackage detail (all **port-to-C#**, pure deterministic math, zero engine deps):

| File | LOC | Responsibility |
|---|---|---|
| `geography/noise.py` | 265 | `hash_2d`, `hash_2d_int`, value/fractal noise, contiguity checks, Voronoi subdivide, farthest-point seed placement |
| `geography/models.py` | 583 | `NewChunkType`(15), `DangerLevel`(6) + tier weights, `RegionIdentity`(10) + primary/secondary chunk tables, `GeographicData`, `WorldMap` + gzip save/load |
| `geography/config.py` | 170 | `GeographicConfig` dataclasses + JSON override loader (`geography-config.json`) |
| `geography/world_generator.py` | 221 | 9-phase pipeline orchestrator (nations→…→villages) |
| `geography/nation_generator.py` | 392 | Angular-sector template + severe noise deformation + constraint repair |
| `geography/region_generator.py` | 219 | Voronoi subdivision of nations; identity assignment |
| `geography/political_generator.py` | 259 | Provinces + districts (Voronoi within parents) |
| `geography/biome_generator.py` | 128 | Chunk-type patches from region identity (70/30 primary/secondary) |
| `geography/ecosystem_generator.py` | 252 | 3×3 danger grouping, ±2 gradient smoothing, spawn-safe radius |
| `geography/name_generator.py` | 315 | Procedural names, 5 cultural flavors |
| `geography/village_generator.py` | 423 | Village placement (JSON config), walls/entrances/buildings, NPC templates |
| `geography/setting_resolver.py` | 76 | Chunk → setting tag ("village"/"underground"/…); consumed by WMS |
| `geography/__init__.py` | 26 | Exports |

---

## 2. Public Surface (what other subsystems actually call)

### 2.1 `WorldSystem` (world_system.py:28)
Constructed at `core/game_engine.py` (`self.world`); `defer_init=True` boot path calls
`initialize_world(progress_callback)` from the loading screen (game_engine.py:1988).

| Member | Callers |
|---|---|
| `initialize_world(cb)` (l.104) | game_engine.py:1988 |
| `get_chunk(cx,cy)` (l.404) | game_engine.py:7589; internal streaming |
| `update_loaded_chunks(pos)` (l.812) | game_engine.py:8436 (once per frame) |
| `register_chunk_unload_callback(cb)` (l.804) | game_engine.py:265, 1967 (combat manager enemy cleanup) |
| `get_tile(pos)` (l.1034) | collision_system.py:237,299; renderer via `get_visible_tiles` |
| `is_walkable(pos)` (l.1054) | entities/character.py:759,821,829,836; Combat/enemy.py:998,1009,1019; game_engine.py:7312 |
| `get_visible_tiles / _resources / _stations / _placed_entities / _dungeon_entrances` (l.1105-1232) | rendering/renderer.py:1014,1305,1033,1078,1262 |
| `get_resource_at(pos, tol)` (l.1171) | game_engine.py:3042; collision_system.py:248,305 |
| `get_station_at` (l.1279) / `get_entity_at` (l.1363) / `get_dungeon_entrance_at` (l.1234) | game_engine.py:2971 / 2728,2903,2975,3094 / 2958 |
| `place_entity(...)` (l.1302) / `remove_entity` (l.1343) | game_engine.py:2785,7326 |
| `spawn_death_chest(pos, rich_items)` (l.710) | entities/character.py:2021 (on death) |
| `remove_death_chest` (l.762) / `get_nearby_death_chest` (l.785) | game_engine.py:7978,7998,8141 |
| `spawn_storage_chest` attr | game_engine.py:2936,7838-7895,8698; renderer.py:1175 |
| `get_save_state()` (l.1442) / `restore_from_save(dict)` (l.1527) | save_manager.py:392; game_engine.py:1253,2119,2207 |
| `set_chunk_save_directory(name)` (l.1020) | game_engine.py:2096,2187 |
| `get_village_npc_definitions()` (l.453) | game_engine.py:1825 (NPC spawn) |
| `inject_test_village()` (l.481) | game_engine.py:1998 (test/temp world only) |
| `mark_resource_modified(res)` (l.1421) | harvesting path in game_engine |
| `update(dt)` (l.1408) | main loop (resource respawn ticks) |
| `map_images` attr (l.61) | renderer map view (pre-rendered LOD surfaces — pygame Surfaces, see §4) |
| Legacy props `tiles/resources/dungeon_entrances/chunks` (l.1633-1677) | misc; inefficient — drop in port, migrate callers |

### 2.2 `Chunk` (chunk.py:22)
Constructed only by `WorldSystem` (world_system.py:438,986) and directly in game_engine debug spawns
(game_engine.py:2106,2194). Surface: `tiles` dict (`"x,y,z"` string keys), `resources` list,
`chunk_type`, `dungeon_entrance`, `mark_rendered()` (chunk.py:612, called from
`WorldSystem.get_visible_tiles` l.1137-1141), `has_modifications()`, `get_save_data()`,
`restore_modifications()`, `prepare_for_unload()`. Classmethod `restore_water_chunks` (l.53) = legacy save compat.

### 2.3 `BiomeGenerator` (biome_generator.py:39)
`get_chunk_seed(cx,cy)` (l.95) — used by every `Chunk` (chunk.py:98); `get_chunk_type` (l.312) — legacy path;
`should_spawn_dungeon` (l.436) — world_system.py:631; `is_water_chunk` (l.419).

### 2.4 `SaveManager` (save_manager.py:16)
`save_game(...)` (l.461), `load_game(name)` (l.527), `restore_game_settings` (l.579),
`restore_dungeon_state` (l.603), `restore_faction_state` (l.642), `restore_npc_state` (l.446, static),
`get_save_files()` (l.667), `delete_save_file` (l.717). Caller: game_engine (import at l.55); tests.

### 2.5 `Quest` / `QuestManager` (quest_system.py:11/252)
Owned by `Character` (`character.quests`; import at entities/character.py:23-30).
`start_quest(quest_def, character)` (l.258), `complete_quest(quest_id, character)` (l.337),
`abandon_quest` (l.538), `has_completed` (l.560), `restore_from_save` (l.564), `active_quests` /
`completed_quests` dicts read by quest_log_overlay.py:79-80 and `NPC` helpers.
Sidecar hooks: `world_system.wes.quest_reward_adapter.get_reward_adapter().pregenerate/adapt`
(l.319-335, 519-536) and `QuestArchiveDatabase.archive` (l.441-504).

### 2.6 `NPC` (npc_system.py:31)
Instantiated in game_engine (import l.53). `is_near(pos)` (l.52), `get_next_dialogue()` (l.69),
`get_quest_offer_line/`\ `get_quest_complete_line/get_farewell_line` (l.110-152), `reset_dialogue_state` (l.59),
`get_available_quests(qm)` (l.154), `has_quest_to_turn_in(qm, character)` (l.162).
State serialized: `current_dialogue_index` only (save_manager.py:439-443).

### 2.7 `TitleSystem` / `ClassSystem` / `SkillUnlockSystem` / `Encyclopedia` / `NaturalResource`
All owned by `Character` (entities/character.py:23-31). Key surface:
`TitleSystem.check_for_title(character)` (title_system.py:58), `get_total_bonus(bonus_type)` (l.109) — read by
combat/crafting bonus math; `ClassSystem.set_class` (class_system.py:58), `get_bonus`, `get_tool_efficiency_bonus`
(l.82), `get_tool_damage_bonus` (l.94); `SkillUnlockSystem.check_for_unlocks` + trigger variants
(skill_unlock_system.py:35,144-196); `Encyclopedia` state read heavily by renderer.py:3609-4799;
`NaturalResource.take_damage` (natural_resource.py:137), `get_loot` (l.159), `update(dt)` (l.163),
`get_color()` (l.176, render-only).

### 2.8 `CollisionSystem` (collision_system.py:74)
Singleton via `get_collision_system()` (l.587). **`init_collision_system` (l.595) is never called — dead.**
The world ref is wired lazily by Combat/combat_manager.py:1469-1470 (`set_world_system` on first LoS check).
Live surface: `has_line_of_sight(src, tgt, attack_tags)` (l.120) — combat_manager.py:1480,1957;
turret_system.py:120. `is_position_walkable`/`can_move_to` (l.274/323).
**`find_path`/`get_next_step` (l.364/521) have zero production callers** — enemies move by
`world_system.is_walkable` + axis-slide (Combat/enemy.py:998-1019). Do not port the A*.

### 2.9 `DungeonManager` (dungeon.py:638)
`self.dungeon_manager` in game_engine (created l.261; ~50 call sites). Surface: `enter_dungeon(pos, rarity)`
(l.677), `exit_dungeon()` (l.697), `get_player_dungeon_position`, `start_next_wave` (l.726), `on_enemy_killed`
(l.732), `is_wave_complete`, `is_dungeon_cleared`, `get_chest`/`open_chest` (l.749/755), `get_visible_tiles`
(l.768, renderer), `to_dict`/`from_dict` (l.785/794, save). `WorldSystem.is_walkable` consults
`dungeon_manager.in_dungeon` (world_system.py:1064-1072). `LootChest` also used directly by `WorldSystem`
(spawn/death chests, world_system.py:19,700,740).

### 2.10 `MapWaypointSystem` (map_waypoint_system.py:109)
`self.map_system` in game_engine (created l.208; ~40 call sites incl. 833-919, 3300-3441, 7274-7600).
`mark_chunk_explored` (l.194), `set_death_chest_marker` (l.231, called by WorldSystem via `self.map_system`
back-ref, world_system.py:757,781), `add/remove/rename_waypoint` (l.348/410/433), `teleport_to_waypoint`
(l.511), `can_teleport` (l.482), `adjust_zoom`/`start_drag`/`update_drag`/`end_drag` (UI),
`get_save_data`/`restore_from_save` (l.648/664).

### 2.11 `TurretSystem` (turret_system.py:14)
`update(placed_entities, combat_manager, dt)` (l.21) — game_engine main loop (created l.350). Everything else
internal. Depends on `core.effect_executor.get_effect_executor()` (l.7) and publishes `ENEMY_KILLED` (l.194).

### 2.12 `PotionEffectExecutor` / `AttackEffectsManager` / quest log overlay / training dummy
`get_potion_executor().apply_potion_effect(character, potion_def, crafted_stats)` — entities/character.py:2593.
`get_attack_effects_manager()` — combat_manager.py:1462,1943; Combat/enemy.py:1305; skill_manager.py:1066;
turret_system.py:107; game_engine.py:3957; renderer.py:7761 (drains `get_active_effects()`).
`render_quest_log_overlay(...)` — game_engine.py:8672. `spawn_training_dummy(combat_manager, pos)` —
game_engine.py:281,2069,2156,2244,2275 (debug key).

### 2.13 `LLMItemGenerator` — **SIDECAR IPC CONTRACT (invented items)**
Game-side call sites: `init_item_generator(project_root, materials_db)` + `get_item_generator()`
(game_engine.py:4882,5751), `start_background_generation(discipline, ui, narrative)` /
`get_background_result()` / `clear_background_result()` / `abandon_background_generation()`
(game_engine.py:4984,5288,653), `get_loading_state()` polled by renderer.py:7964 and game_engine.py:602,4475.

**IPC request** (replaces `generate(discipline, interactive_ui, narrative)`, llm_item_generator.py:623): the
recipe context the Python side builds in `_extract_recipe_context` (l.783-897) — Godot sends this JSON verbatim:
```jsonc
{
  "recipeId": "invented_<ts>", "stationTier": 1-4, "stationType": "<discipline>",
  // discipline-specific, one of:
  "inputs":            [{"materialId","quantity","materialName","materialTier","materialRarity","materialNarrative","materialTags"}], // smithing (aggregated grid counts)
  "vertices": {"x,y": {...}}, "shapes": [{"type","vertices"}],   // adornments/enchanting
  "ingredients":       [{"slot":1..6, "materialId","quantity",...}],  // alchemy
  "coreInputs": [...], "surroundingInputs": [...],               // refining
  "slots":             [{"slotType","materialId","quantity",...}],    // engineering
  "narrative": "Player-invented recipe. Create an appropriate item."
}
```
**IPC response** = `GeneratedItem` (l.376-394): `{success, item_data (game item JSON), item_id, item_name,
discipline, error?, from_cache, recipe_inputs:[{materialId,quantity}], station_tier, narrative}`.
Async protocol: request-id + progress events (maps to `LoadingState` start/update/finish, l.109-263) + a
**cancel** message (maps to `abandon_background_generation` l.355-369 — worker result discarded, materials only
consumed on success). Caching key = md5 of sorted context JSON (l.1014-1017).
**Port to C# (do NOT leave in sidecar)**: `_sanitize_item_data` (l.951-995: tier clamp 1-4, id-collision
`invented_` prefix, tier-scaled stat ceilings `{1:60, 2:120, 3:240, 4:480}` on
`damage/baseDamage/defense/armor/healAmount/healing/attackSpeed`, l.947-949) — the game must never trust sidecar
output; also `calculate_minimum_tier` (l.1127-1227) and `extract_placement_data` (l.1031-1125) which are pure
placement math used by save/recipe-recreation. The fallback item templates (l.1229-1372) should ALSO be ported
to C# so an unreachable sidecar still yields a playable item. Model config (l.80-99): `claude-haiku-4-5`,
max_tokens 2000, temperature 0.4 (never send top_p with temperature — Haiku 4.5 400s, l.505-523), timeout 30s.

### 2.14 `CraftingClassifierManager` — **SIDECAR IPC CONTRACT (recipe validation)**
Game-side: `init_classifier_manager(project_root, materials_db)` / `get_classifier_manager()`
(game_engine.py:4454,4496,4898), `validate(discipline, interactive_ui)` (crafting_classifier.py:1144),
`preload(discipline)` (l.1298, on crafting-UI open — TF warmup), `unload()` (l.1385, on UI close),
`get_status()` (l.1284).

**IPC request**: `{op:"validate", discipline, placement:{...}}` where placement is the same UI-state shape as
§2.13 (grid dict for smithing; vertices+shapes for adornments; slot lists for alchemy/refining/engineering) plus
`station_tier`. The ENTIRE transform pipeline stays Python-side because it is training-coupled and marked
"DO NOT MODIFY without retraining": `MaterialColorEncoder` HSV encoding (l.64-219: category hues l.77-85,
element hues l.88-92, tier brightness `{1:0.50, 2:0.65, 3:0.80, 4:0.95}` l.95, saturation rules l.205-213),
`SmithingImageRenderer` 36×36 (9×9 cells × 4px, tier-aware shape masks l.256-304),
`AdornmentImageRenderer` 56×56 (coord range ±7, `px=(x+7)*4, py=(7-y)*4` l.449-453), and the LightGBM feature
vectors: refining **19** features (l.568-656), alchemy **34** (l.658-743), engineering **28** (l.745-830),
category vocab `{elemental:0, metal:1, monster_drop:2, stone:3, wood:4}` (l.512-518).
**IPC response** = `ClassifierResult` (l.34-45): `{valid, confidence, probability, discipline, error?}`.
Threshold 0.5 per discipline (configs l.1011-1047). Also expose `preload`/`unload`/`status` ops so Godot can
warm the TF graph when the crafting panel opens. Note the sidecar needs the material JSON
(`items.JSON/items-materials-1.JSON`, l.1099) — it reads content directly, no game round-trip needed.

---

## 3. Dependency Edges

**systems/ imports FROM:**
- `data.models` (Position, WorldTile, TileType, ChunkType, StationType, CraftingStation, PlacedEntity,
  DungeonRarity, DUNGEON_CONFIG, ResourceType, RESOURCE_TIERS, LootDrop, NPCDefinition, QuestDefinition,
  QuestRewards, TitleDefinition, ClassDefinition, SkillUnlock, MaterialDefinition) — world_system.py:14-18,
  chunk.py:11, dungeon.py:31-34, quest_system.py:6-7, npc_system.py:27, potion_system.py:7, etc.
- `data.databases` — `WorldGenerationConfig` (chunk.py:13), `ResourceNodeDatabase` (chunk.py:12),
  `ChunkTemplateDatabase` (chunk.py:14), `MapWaypointConfig` (map_waypoint_system.py:19),
  `TitleDatabase/MaterialDatabase/SkillDatabase` (quest_system.py:8), `SkillUnlockDatabase`
  (skill_unlock_system.py:6), `quest_archive_db` (quest_system.py:441).
- `core` — `Config` (world_system.py:24, chunk.py:16, dungeon.py:35, natural_resource.py:7),
  `core.paths.get_save_path/PathManager/get_resource_path` (world_system.py:25, save_manager.py:13,
  class_system.py:29), `core.effect_executor` + `core.tag_debug` (turret_system.py:7-8).
- `entities` — `entities.components.buffs.ActiveBuff` (potion_system.py:8), `entities.status_manager`
  (training_dummy.py:13).
- `Combat` — `Combat.enemy.Enemy/EnemyDefinition/AIPattern` (training_dummy.py:12). Turret/collision reach
  Combat objects only via duck-typed parameters.
- `events.event_bus` (lazy, inside try/except) — quest_system.py:292,397,551; title_system.py:48;
  class_system.py:62; natural_resource.py:147; turret_system.py:192.
- `world_system/` package (the WMS sidecar-bound tree — NOTE the unfortunate name collision with
  `systems/world_system.py`): factions save/restore (save_manager.py:76,660), ContentRegistry flush
  (save_manager.py:90), graceful_degrade (save_manager.py:110), `world_system.wes.quest_reward_adapter`
  (quest_system.py:319,520). **These become IPC calls in Godot.**
- `rendering.map_cache.generate_map_images` (world_system.py:374) — pygame surface generation. Engine-replaces.
- Third-party: `numpy` (crafting_classifier.py:10 only), `anthropic` (lazy, llm_item_generator.py:497),
  `tensorflow`/`lightgbm` (lazy, crafting_classifier.py:885/943), `pygame` (quest_log_overlay.py:71 only).

**Who imports systems/:**
- `core/game_engine.py` (l.53-57 + ~30 lazy imports) — primary orchestrator.
- `entities/character.py` (l.23-31, 2593) — owns QuestManager, TitleSystem, ClassSystem, Encyclopedia,
  SkillUnlockSystem; calls `world.is_walkable`, `world.spawn_death_chest`, potion executor.
- `rendering/renderer.py` (l.40, 7761, 7964) — visible-set queries, attack effects, loading state, encyclopedia.
- `Combat/combat_manager.py` (l.589,1462-1470,1943-1951,2585) — collision LoS + attack effects + PlacedEntityType.
- `Combat/enemy.py` (l.998-1019, 1305) — walkability + attack effects.
- `entities/components/skill_manager.py` (l.1066) — attack effects.
- `world_system/world_memory/geographic_registry.py` (l.336) — consumes `systems.geography.models.WorldMap`
  (WMS reads geography; in Godot the sidecar keeps its own Python copy of geography models — see §11 risk R6).
- Tests: tests/test_chunk_density_spawn.py:39, tests/test_npc_speechbank.py:35, tests/save/test_save_system.py,
  world_system/tests/test_claude_request_params.py:63, wes/tests/test_quest_lifecycle_e2e.py:32, etc.

---

## 4. Engine Coupling (pygame / rendering / input / clock touchpoints)

`systems/` is remarkably clean — only ONE module imports pygame:

1. **`quest_log_overlay.py:71-181`** — imports pygame, draws Surfaces/Rects/fonts, computes abandon-button hit
   rects from mouse pos. Wholesale replace with a Godot `Control` scene; keep `_format_objective`/`_format_progress`
   (l.191-245) as the parity spec for objective text.
2. **`world_system.py:367-387` `_generate_map_images`** — calls `rendering.map_cache.generate_map_images`
   producing pygame Surfaces stored in `self.map_images` for the map screen. In Godot: replace with
   `Image`/`ImageTexture` generation (or a shader) fed by the same `WorldMap` + `MapWaypointConfig.get_biome_color`
   data. The data inputs are engine-free; only the raster output is pygame.
3. **Viewport-query API** — `get_visible_tiles/resources/stations/placed_entities/dungeon_entrances`
   (world_system.py:1105-1232, dungeon.py:768-783) take `(camera_pos, viewport_width_px, viewport_height_px)` and
   divide by `Config.TILE_SIZE` (32 px, core/config.py:25). This is a 2D-camera assumption baked into the logic
   layer. In Godot 3D the renderer culls; these functions survive only as chunk/AOI queries (see §9). Note the
   hidden render→logic side channel: `get_visible_tiles` **mutates** chunks via `mark_rendered()`
   (world_system.py:1128-1141) to lock chunk templates — this "player has seen it" signal must be re-plumbed from
   the Godot view layer (e.g., VisibleOnScreenNotifier3D or AOI enter events).
4. **Wall-clock (`time.time()`) instead of game clock** — semantic timing that must move to game-time or
   deterministic counters in Godot: `AttackEffect.start_time/age` (attack_effects.py:89-105);
   `LootChest.chest_id` default `chest_{ms}_{rand}` (dungeon.py:203) and `DungeonInstance.dungeon_id` (l.438),
   `entrance_time` (l.443); `Quest.received_at_game_time/turned_in_at` (quest_system.py:39,371) — mixes
   wall-clock into save data and archive `duration`; turret attack cooldowns `time.time()` (turret_system.py:24,67);
   `LoadingState` animation clock (llm_item_generator.py:135-254 — UI-side, fine to keep wall-clock).
   By contrast `WorldSystem.game_time` (world_system.py:69, +dt at l.1414) and resource respawns are already dt-driven — keep that model.
5. **Input state held in logic classes** — `MapWaypointSystem.map_open/map_zoom/map_scroll_*/map_dragging`
   (map_waypoint_system.py:140-151, 569-642) and `Encyclopedia.is_open/current_tab/scroll_offset`
   (encyclopedia.py:12-14): move to Godot UI layer; keep pure helpers.
6. **`print()`-based debug/UX everywhere** (e.g., world_system.py:143-244, turret_system.py:125-184,
   training_dummy.py:109-233, quest_system.py:339-383) — route to a logger; training_dummy's prints are its whole
   feature (tag validation console) — give it an in-game debug panel in Godot.
7. **Colors in logic layer** — `NaturalResource.get_color()` (natural_resource.py:176-202),
   `attack_effects._ELEMENT_COLORS` (attack_effects.py:39-60), dungeon rarity colors
   (data/models/world.py:560-565): move to view config, but the tag→color TABLE itself is player-facing parity
   data — preserve values.
8. **Threading for LLM** (llm_item_generator.py:277-369, 1462-1499) — daemon thread + poll pattern becomes
   async IPC to sidecar + C# `Task`/signal; the cancel semantics ("worker keeps running, result discarded,
   materials only consumed on success", l.294-303) must be preserved exactly.

---

## 5. Constants & Formulas (exact values from code)

### World structure
- `Config.CHUNK_SIZE = 16` tiles/chunk (core/config.py:24); `Config.TILE_SIZE = 32` px (l.25);
  `Config.CLICK_TOLERANCE = 0.7` (l.185).
- World size 512×512 chunks, coords `[-256, 256)`, spawn (0,0) (geography/config.py:20-23, models.py:371-379).
- Chunk streaming: `load_radius = 4`, `spawn_always_loaded_radius = 1` (defaults world_generation_db.py:18-19;
  overridable by `Definitions.JSON/world_generation.JSON`), prefetch budget `prefetch_loads_per_frame` default 2
  (world_system.py:853), player 3×3 never deferred (l.864), unload hysteresis = load_radius + 1 (l.875).

### Deterministic seeds & hashes (bit-exact contract for the 3D terrain port)
- World seed: `random.randint(0, 2**32 - 1)` if unset (world_system.py:53). (`self._world_rng` at l.54 is
  assigned and never used — dead.)
- **Per-chunk seed** (biome_generator.py:95-125): fold negatives `a = x*2 if x>=0 else -x*2-1`; Szudzik pair
  `ax>=ay ? ax*ax+ax+ay : ay*ay+ax`; then `h=seed; h^=pair; h=(h^(h>>16))*0x85ebca6b; h=(h^(h>>13))*0xc2b2ae35;
  h^=(h>>16); return h & 0xFFFFFFFF`. **Python ints are arbitrary-precision — the multiplies are NOT 32-bit
  wrapped before the final mask.** A C# port must use BigInteger-equivalent semantics or accept different worlds
  (see §11 R1).
- Legacy `_hash_2d` (biome_generator.py:127-145): `h=seed+offset; h^=x*374761393; h^=y*668265263;
  h=(h^(h>>13))*1274126177; h^=(h>>16); return (h & 0x7FFFFFFF)/0x7FFFFFFF`. Offsets: 100=biome roll,
  3000=type cluster, 5000=danger roll, 10000=dungeon roll (l.223,248,269,468).
- Geography `hash_2d` (geography/noise.py:20-26) — DIFFERENT mixing, fully 32-bit masked at each step:
  `h=((seed^(x*374761393))+(y*668265263))&0xFFFFFFFF; h=((h^(h>>13))*1274126177)&0xFFFFFFFF; h=(h^(h>>16))&0xFFFFFFFF;
  return (h&0x7FFFFFFF)/0x7FFFFFFF`. This one IS portable with uint arithmetic.
- Fractal noise octave seed step `+ i*31337` (noise.py:75); Voronoi boundary noise seed `+77777` (l.207);
  seed-point sampling seed `+999` (l.244).
- Derived seeds: villages `seed+777777` (village_generator.py:150; world_system.py:318), village names
  `seed+888888` (village_generator.py:249), test village `seed+424242` (world_system.py:506), building layout
  `seed + locality_id` (village_generator.py:382).
- Chunk-level RNG: `random.Random(chunk_seed)` (chunk.py:106) drives tile dirt rolls, resource
  placement/choice/weighted `choices`, fishing `sample` — **Python MT19937**; see §11 R1.
- Geographic-map cache: `world_map_seed_{seed}.gz` in save dir (world_system.py:250), gzip JSON level 6
  (models.py:497).

### Chunk/tile generation
- Land: stone base if `"quarry" in chunk_type or "cave" in chunk_type` else grass; 10% dirt roll (chunk.py:227-234).
- Lake: outer 2-tile land border; water where dist-from-center < 5 (chunk.py:263-269). Swamp: 4-way paths where
  `|local-center| < 2`, else 50% water (l.273-279). River: center band `dist<3` with 80% water (l.283-287).
  Water tiles non-walkable (l.289-291).
- Resource placement: up to 10 attempts, inside `[1, CHUNK_SIZE-2]`, respects `spawn_area.resource_exclusion_radius`
  from world_generation.JSON, no overlap (chunk.py:459-479). Tier cap per slot `min(randint(*tier_range), 4)`
  (l.363,428). Danger→config mapping: geo danger ≤2 peaceful, ≤4 dangerous, else rare (l.313-320).
- Legacy chunk-type distribution (no geo data): spawn 3×3 always peaceful; roll d10: 1-5 peaceful, 6-8 dangerous,
  else rare with 25% cursed swamp (chunk.py:175-204).
- Fishing spots: per-tier types (chunk.py:547-568), count/tier from `water_chunks.normal_water|cursed_swamp` config.

### Danger / safety
- Legacy safe zone radius 8 chunks (biome_generator.py:59); progressive peaceful threshold
  `0.40 + 0.60*safety`, dangerous `+0.45*(1-safety)` (l.275-286); outer zone 40/40/20 (l.288-295).
- Geographic danger tier weights (models.py:79-86): TRANQUIL {1:1.00}; PEACEFUL {1:.80,2:.15,3:.05};
  MODERATE {1:.60,2:.30,3:.10}; DANGEROUS {1:.25,2:.35,3:.30,4:.10}; PERILOUS {1:.15,2:.20,3:.45,4:.20};
  LETHAL {2:.15,3:.45,4:.40}. Gradient max ±2 (l.98). Base danger weights + spawn-safe radius 2 ecosystems
  (config.py:84-93). Region primary/secondary chunk weight 0.70/0.30 (models.py:206-207).

### Dungeons
- Hardcoded fallback `DUNGEON_CONFIG` (data/models/world.py:510-547): spawn weights C50/U25/R15/E7/L2/Uq1; mob
  counts 20/30/40/50/50/50; tier weights per rarity as listed. **JSON `Definitions.JSON/dungeon-config-1.JSON`
  takes priority** (dungeon.py:47-128; docstring "Common 25%..." at dungeon.py:7-13 does NOT match the code —
  trust weights). Size 2×2 chunks = 32×32 tiles (dungeon.py:39-40), waves = 3, remainder mobs to later waves
  (l.491-502), player spawn center+5 south (l.537-540), exit portal center-3 north (l.566-570), enemy spawn
  margin 3, ≥5 from center (l.523-535). Geographic dungeon spawn chance 0.015/chunk, min 8 chunks from spawn
  (geography/config.py:97-101); legacy chance from world_generation.JSON (biome_generator.py:77).
- Chest loot: dilutive tier tables, default drop split materials/equipment/consumables 60/30/10
  (dungeon.py:160-168, 229-331); qty `randint(1, 3+tier)` for materials (l.305).

### Stations / spawn furniture
- Station grid: x ∈ {-8,-4,0,4,8} for smithing/refining/adornments/alchemy/engineering; tiers 1-4 at
  y = -10,-12,-14,-16 (world_system.py:678-692). Spawn storage chest at (3,-2) (l.700-708). Death chest id
  `death_chest_{x}_{y}_{seq}` deterministic monotonic (l.730-731).

### Resources
- Fallback HP by tier {1:100, 2:200, 3:400, 4:800}; trees respawn 60s; fishing spots HP {50,75,100,150}, respawn
  {30,45,60,90}s; ores don't respawn (natural_resource.py:33-50). Crit ×2 on gather damage (l.140).
  JSON path (`ResourceNodeDatabase`) overrides all of this.

### Quests / titles / classes / potions
- Quest baselines: progress counted from acceptance snapshot (quest_system.py:56-93). Reward resolution chain
  `adapted ?? pre_generated ?? quest_def.rewards` (l.20-26, 121-134). Archive day = `completed // 86400` (l.503).
- Title legacy random_drop tier chances {novice 1.0, apprentice .20, journeyman .10, expert .05, master .02}
  (title_system.py:96-103). Bonus-key renames: smithing_time→smithing_speed, refining_precision→refining_speed,
  critical_chance→crit_chance; typo tolerance elemental_affinity→elemental_afinity (l.17-26) — the titles JSON
  itself carries the typo; port must keep tolerance.
- Class fallback tag-tool bonuses (class_system.py:15-19): axe {nature .10, gathering .05}; pickaxe
  {gathering .10, explorer .05}; toolDamage {physical .05, melee .05}; JSON `progression/classes-1.JSON
  metadata.tagToolBonuses` overrides.
- Potions: potency/duration = crafted `potency%`/`duration%` /100 (potion_system.py:56-57); resistance cap 0.9
  (l.292); default durations buff 300s, resistance 360s, utility 3600s (l.225,290,334).
- Waypoints: slots by level via `map-waypoint config` (MapWaypointConfig), teleport cooldown + blocked in
  dungeon/combat flags all config-driven (map_waypoint_system.py:482-509); zoom step = 25% of current, min 0.005
  (l.579-582).
- Turret device numbers (hardcoded, turret_system.py): healing beacon 10 HP/s radius 5 (l.429-436); net launcher
  trigger 3.0, effect radius 5.0, slow 80% 10s (l.464-499); EMP delay 1s, radius 8, stun 30s constructs only
  (l.524-558); trap default trigger_radius 2.0 (l.234); bomb default fuse 3.0s, blast `circle_radius` default 3.0
  (l.314,349). Turret cooldown = `1.0/attack_speed` (l.62).
- Sacred constants: none of the damage/EXP/tier/durability/LCK formulas live in `systems/` — the only tier-multiplier
  echo is the invented-item stat ceiling table {1:60,2:120,3:240,4:480} (llm_item_generator.py:947) which mirrors
  T1..T4 = 1/2/4/8 ×60.

---

## 6. Event Topics (GameEventBus)

All publishes are wrapped in `try/except: pass` — silent-failure by design.

| Topic | Direction | Where | Payload keys |
|---|---|---|---|
| `QUEST_ACCEPTED` | publish | quest_system.py:293 | quest_id, quest_type, npc_id |
| `QUEST_COMPLETED` | publish | quest_system.py:402 | quest_id, player_id, quest_type, npc_id, rewards{experience, gold} |
| `QUEST_FAILED` | publish | quest_system.py:552 (abandon) | quest_id, quest_type |
| `TITLE_EARNED` | publish | title_system.py:49 | actor_id="player", title_id, tier |
| `CLASS_CHANGED` | publish | class_system.py:63 | actor_id="player", class_id |
| `NODE_DEPLETED` | publish | natural_resource.py:148 | resource_id, resource_type, position_x, position_y |
| `ENEMY_KILLED` | publish | turret_system.py:194 | enemy_id, enemy_type, tier, is_boss, source="turret", position_x/y |

No subscriptions inside `systems/` (subscribers live in world_system/ WMS — which becomes the sidecar; in Godot
these publishes become the event feed over IPC, so the topic strings + payload shapes above ARE the IPC event
schema). Non-bus callback registries that serve the same role: `WorldSystem._on_chunk_unload_callbacks`
(world_system.py:95, 804-810) and `ClassSystem._on_class_set_callbacks` (class_system.py:56, 73-75).

---

## 7. Content JSON Consumed (reused verbatim; loaders get ported)

| JSON | Loader | Used by |
|---|---|---|
| `Definitions.JSON/world_generation.JSON` | `WorldGenerationConfig` (data/databases/world_generation_db.py:187) | chunk.py:304-326 (resource counts/tier ranges, water/fishing config, spawn exclusion), world_system.py:391-392, 825-853 (radii, prefetch), biome_generator.py:70-84 (ratios, dungeon chance, debug flags) |
| `Definitions.JSON/dungeon-config-1.JSON` | inline `_load_dungeon_config` (dungeon.py:56-59) — NOT a db singleton | dungeon rarities, sizes, waves, tierWeights, chestLoot (v1/v2/v3 formats, l.81-168) |
| `world_system/config/geography-config.json` or `Definitions.JSON/geography-config.json` | `GeographicConfig.load` (geography/config.py:131-151) | whole geography pipeline |
| `Definitions.JSON/village-config.JSON` or `world_system/config/village-config.JSON` | `_load_config` (village_generator.py:31-61) | village tiers, NPC templates, naming, placement rules |
| `world_system/config/geo_chunk_dispatch.json` + chunk template JSONs | `ChunkTemplateDatabase` (data/databases/chunk_template_db.py:245) | chunk.py:152-163, 337-346 (geo-type → template, resourceDensity spawning) |
| `Definitions.JSON/Resource-node-1.JSON` (+Update-N) | `ResourceNodeDatabase` | chunk.py:50, natural_resource.py:62 (HP, tools, respawn, drops) |
| map/waypoint config JSON | `MapWaypointConfig` (data/databases/map_waypoint_db.py) | map_waypoint_system.py:127; world_system.py:376 (biome colors) |
| `progression/classes-1.JSON` (`metadata.tagToolBonuses`) | inline (class_system.py:24-44) | tool efficiency/damage bonuses |
| titles/materials/skills/skill-unlock JSONs | `TitleDatabase`, `MaterialDatabase`, `SkillDatabase`, `SkillUnlockDatabase` | quest rewards (quest_system.py:8), title checks, unlocks |
| `items.JSON/items-materials-1.JSON` | read DIRECTLY by classifier (crafting_classifier.py:1099) for metadata.tags | color encoding — stays sidecar-side |
| `Scaled JSON Development/LLM Training Data/Fewshot_llm/prompts/system_prompts/system_{1-5}.txt` + `examples/few_shot_examples.json` | `FewshotPromptLoader` (llm_item_generator.py:401-467) | stays sidecar-side |
| ML model files `Scaled JSON Development/crafting_classifier_models/{smithing/adornment/alchemy/refining/engineering}` | crafting_classifier.py:1011-1047 | stays sidecar-side |

---

## 8. Persistent State (save/load contribution)

Master save (SaveManager, version `"3.0"` save_manager.py:19; atomic tmp+fsync+`.bak` l.503-518; corrupt-file
`.bak` recovery l.550-562):

- `player` (l.139-198): position{x,y,z}, facing, stats, leveling, health/mana, class, inventory slots (full
  equipment_data incl. durability/enchantments/effect params), equipment slots, equipped/known skills, titles
  (ids), activities, stat_tracker dict, skill_unlocks {unlocked, pending}, `invented_recipes`
  (l.200-237: timestamp, discipline, item_id/name, item_data, recipe_inputs, station_tier, narrative,
  placement_data, icon_path).
- `world_state` = `WorldSystem.get_save_state()` (world_system.py:1442-1462): seed, game_time, placed_entities
  (position/type/tier/health/owner/time_remaining/tags/effect_params [+range/damage/attack_speed]),
  crafting_stations, discovered_dungeons (chunk key + pos + rarity), spawn_chest, death_chests (LootChest
  `to_dict` incl. rich_contents, dungeon.py:367-381).
- **Per-chunk side files**: `{save_base}_chunks/chunk_{x}_{y}.json` (world_system.py:912-1018) containing
  chunk_x/y, chunk_type, `template_locked` (default True on old saves, l.973), modified_resources
  (local_x/y, type, hp, depleted, time_until_respawn), dungeon_entrance, unload_timestamp. Respawn credit for
  elapsed offline time applied on load (chunk.py:698-704).
- `quest_state` (save_manager.py:399-423): active {status, progress, baseline_combat_kills, baseline_inventory},
  completed list. **`QuestManager.restore_from_save` (quest_system.py:564-595) never reconstructs active quests —
  it prints "Quest database not implemented" and drops them. Known gap; the Godot port should fix rather than
  replicate.** Note the adaptive-reward fields (pre_generated/adapted rewards, timestamps) are NOT serialized —
  in-flight generated quests lose their reward bundles on save/load.
- `npc_state` (l.425-443): per-npc `current_dialogue_index` only (speechbank cycle indices not saved).
- `dungeon_state` = `DungeonManager.to_dict` (dungeon.py:785-792) incl. full current dungeon (but NOT its tiles —
  regenerated randomly on load via `__post_init__`, dungeon.py:440-441 → mid-dungeon saves get a re-rolled floor
  layout; enemy positions survive via combat manager).
- `map_state` = MapWaypointSystem (map_waypoint_system.py:648-662): explored_chunks, waypoints, last_teleport_time,
  zoom/scroll, stats. Spawn waypoint force-reset from config on load (l.686-688).
- `game_settings`: `keep_inventory` (save_manager.py:127-137).
- `faction_state` / `content_registry_state` (l.74-124): sidecar-owned SQLite (faction.db, content_registry.db)
  — in Godot these save sections become an IPC "flush/save" command to the sidecar.
- **Geographic map cache** (not in the save): `world_map_seed_{seed}.gz` (world_system.py:250, models.py:431-501).
  **BUG (call out for port): `WorldMap.save()` omits `localities`, `biomes`, and per-chunk `locality_id`, but
  `_rebuild_villages_from_localities` (world_system.py:313-365) needs localities — on any boot that hits the
  cache, villages (walls, buildings, NPC defs) silently vanish.** The Godot port must persist localities (and
  locality_id per chunk) in the cache format, or always re-run `place_villages` deterministically on load
  (it is seed-deterministic: `seed+777777`).

---

## 9. 3D Notes (what NECESSARILY changes 2D→3D)

- **Positions**: `Position(x, y, z)` already exists with z defaulting to 0 (data/models/world.py) and
  `distance_to` is already 3D (l.16-17). Migration decision (standing): Python `(x, y)` ground plane →
  Godot `(x, 0, z)`. Everything in systems/ that does `dx=..x, dy=..y` planar math (turret targeting
  turret_system.py:93-96, chest proximity world_system.py:796, NPC `is_near` npc_system.py:52-57, waypoint
  distance map_waypoint_system.py:373-376) becomes horizontal-plane distance; keep as XZ-distance to preserve
  balance ranges (turret range 5/8, interaction_radius 2.5, etc.).
- **Tile keys**: `"x,y,z"` string keys via `math.floor` (world.py:28-33) — replace with `Vector3i`/packed-int
  keys; preserve floor() semantics for negative coords (world_system.py:1044-1047 comment is load-bearing).
- **Terrain**: `Chunk.tiles` flat 16×16 with walkable flags becomes heightmap/gridmap chunk. Water tiles
  (non-walkable, world_system.py:1076) become depth/collision volumes. Village walls/buildings currently
  overwrite tiles as non-walkable STONE (world_system.py:594-615) — become placed 3D meshes + collision, but
  the tile positions from `get_village_wall_tiles`/`get_village_building_tiles` stay the layout source of truth.
- **Visibility queries** (world_system.py:1105-1232): pixel-viewport math (`vw // TILE_SIZE + 2`) dies. Godot
  culls visually; what must survive is (a) an AOI/chunk-radius query for logic (spawning, WMS events), and
  (b) the `mark_rendered()` template-lock trigger, re-sourced from a 3D visibility signal (§4.3).
- **Line of sight** (collision_system.py:120-268): 2D Bresenham over tile grid, blocked by resources/barriers/
  non-walkable tiles. In 3D replace with a physics raycast against terrain+obstacle colliders; PRESERVE the rule
  set: `BYPASS_LOS_TAGS = {circle, aoe, ground}` (l.86), source/target tiles excluded (l.156-158), and the
  block-consumes-cooldown behavior (turret_system.py:119-133).
- **Movement collision**: distance-based blocking `dx<0.5 and dy<0.5` vs resources/barriers
  (world_system.py:1086-1101) and axis-slide `can_move_to` (collision_system.py:323-358) → Godot
  CharacterBody3D `move_and_slide` against colliders; the 0.5-tile blocking radius is the parity number.
- **Dungeons**: separate 32×32 instance with its own tile dict and `in_dungeon` flag hijacking walkability
  (world_system.py:1063-1072) → separate Godot scene/instance; return_position round-trip unchanged. Random
  floor tiles (dungeon.py:445-468, unseeded `random.random()`) can become cosmetic 3D variation.
- **Facing**: `character.facing` is saved (save_manager.py:156) — becomes a yaw angle; attack_effects
  `facing_angle`/`arc_degrees` (attack_effects.py:84-86) map directly to 3D swing VFX around Y axis.
- **Map screen**: pre-rendered chunk-color LOD images (world_system.py:367-387) → ImageTexture minimap; explored
  mask from MapWaypointSystem unchanged (chunk-resolution data is dimension-agnostic).
- **Teleport**: destination is a stored Position (map_waypoint_system.py:550) — needs ground-height resolution
  (raycast down) on arrival in 3D.
- **Crafting minigames** stay 2D Control overlays (standing decision) — the placement JSON shapes in §2.13/2.14
  are already screen-space-free (grid indices, slot indices, vertex coords), so 3D changes nothing there.

---

## 10. Godot Mapping (proposed)

**Pure-logic assembly `Game.Core` (plain C#, `dotnet test`-able, no Godot types):**
- `Game.Core.World`: `WorldSystem` (minus map_images + visibility pixel math), `Chunk`, `BiomeGenerator`
  (hash functions as `static class ChunkHashing`), `NaturalResource`, `LootChest`, `DungeonInstance`,
  `DungeonManager`, `CollisionRules` (LoS tag rules + walkability policy — actual raycasts injected via
  `ILineOfSightProvider` so tests can use the grid implementation).
- `Game.Core.Geography`: entire geography/ package — `Noise`, `GeographicConfig`, `Models` (+ WorldMap
  save/load in gzip JSON, same format), `WorldGenerator` + phase generators, `VillageGenerator`,
  `SettingResolver`. Zero engine deps today; keep it that way.
- `Game.Core.Progression`: `QuestSystem` (Quest/QuestManager with `IQuestRewardAdapter` interface → IPC impl),
  `TitleSystem`, `ClassSystem`, `SkillUnlockSystem`, `PotionEffectExecutor`, `NpcDialogue` (NPC speechbank
  logic detached from any node).
- `Game.Core.Persistence`: `SaveManager` (System.Text.Json; keep field names snake_case for save compat),
  chunk file store, `WorldMapCache`.
- `Game.Core.Sidecar`: IPC client + DTOs for §2.13/§2.14 (`InventedItemRequest/Result`,
  `ClassifierRequest/Result`, event publish stream from §6, faction/registry save commands).
- `Game.Core.Combat.Support`: `TurretLogic` (per-entity update decisions returned as commands, not applied
  directly — lets tests assert), `AttackEffectDescriptor` (tag→color/type/arc data only).

**Engine glue (Godot node layer):**
- `WorldRoot` (Node3D) — owns `WorldSystem`, streams `ChunkNode3D` scenes (GridMap/MeshInstance terrain +
  resource node scenes) from chunk data; forwards visibility → `Chunk.MarkRendered`; autoload not needed
  (single scene owner).
- Autoload singletons (mirroring the Python module singletons): `EventBus` (C# events or Godot signals — carries
  §6 topics; also mirrors to sidecar), `SidecarClient`, `AttackEffectsManager` → replaced by `CombatVfx`
  (spawns GPUParticles3D/meshes from `AttackEffectDescriptor`), `LoadingOverlay` (CanvasLayer; consumes sidecar
  progress events — replaces `LoadingState`).
- `DungeonRoot` (Node3D, separate scene) — builds from `DungeonInstance`; `MapScreen` (Control) — consumes
  MapWaypoint data + WorldMap colors; `QuestLogPanel` (Control) — replaces quest_log_overlay; `EncyclopediaPanel`
  (Control) — text from `Game.Core` formatters; `TrainingDummyNode` — wraps TrainingDummy logic with a 3D label
  readout instead of prints.
- Physics: obstacle/resource colliders on chunk scenes replace `is_walkable` distance checks for the player
  (CharacterBody3D), while `WorldSystem.IsWalkable` stays authoritative for AI/logic queries during transition.

**Sidecar (unchanged Python process):** `crafting_classifier.py` + `llm_item_generator.py` generation core +
WMS/WNS/WES + factions + quest reward adapter + geography models copy for the WMS geographic registry
(world_system/world_memory/geographic_registry.py:336). Godot talks JSON over local socket/stdio.

---

## 11. Port Complexity, Ordering, Risks

**Complexity:** WorldSystem+Chunk+streaming **XL** (RNG parity + save compat). geography/ **L** (big but pure;
mechanical port). SaveManager **L** (breadth of shapes). dungeon.py **M**. quest_system **M** (sidecar seam +
fixing restore). collision (LoS subset) **S-M**. map_waypoint **M** (logic S + UI rebuild). turret_system **M**
(depends on effect executor port). llm/classifier IPC wrappers **M** (protocol + cancel/progress semantics).
title/class/skill_unlock/npc/potion/natural_resource/encyclopedia **S** each. attack_effects/quest_log_overlay
**S** (rebuild in engine). training_dummy **S**.

**Ordering constraints:**
1. `data.models` + `data.databases` loaders (contract 02/03) must exist first — everything here consumes them
   (`WorldGenerationConfig`, `ResourceNodeDatabase`, `ChunkTemplateDatabase`, `MapWaypointConfig`, etc.).
2. `Game.Core.Geography` + `ChunkHashing` before `Chunk`/`WorldSystem`; write cross-language determinism
   fixtures FIRST (dump N chunk seeds + chunk types + WorldMap digests from Python, assert in C#).
3. `WorldSystem` before `CollisionRules`, `DungeonManager` wiring, `SaveManager`, and any Combat port (enemy
   movement calls `is_walkable`).
4. `EventBus` + `SidecarClient` before quest/title/class ports (they publish) — publishes can no-op initially
   (they already swallow errors).
5. Effect executor (core/ contract) before `TurretSystem` and potion tags.
6. Character/inventory (entities contract) before `Quest.grant_rewards`, `SaveManager`, potion executor.
7. Sidecar IPC protocol can be built and tested against the existing Python modules before any Godot UI exists
   (the request payloads are plain JSON already).

**Top risks / gotchas:**
- **R1 — Python RNG + arbitrary-precision hashing.** Chunk content uses `random.Random` (MT19937) with
  `randint/choice/choices(weights)/sample` (chunk.py:106,328,363,439,571) and `BiomeGenerator.get_chunk_seed`
  multiplies unmasked Python bigints (biome_generator.py:119-125). C# `System.Random` is incompatible; naive
  uint32 arithmetic changes chunk seeds. Either ship a C# MT19937 + Python-compatible `randint/choice/choices/
  sample` shim and BigInteger-faithful hash, or declare world-regeneration a breaking change (saved+rendered
  chunks are template-locked and re-restorable, chunk.py:81-86, which softens but does not eliminate this —
  resource positions inside never-modified chunks still re-roll).
- **R2 — Villages vanish on cached boots.** `WorldMap.save()`/`load()` drop `localities`/`biomes`/per-chunk
  `locality_id` (models.py:437-501 vs village_generator.py:257-268). Fix in the port (persist localities or
  re-run deterministic `place_villages` after cache load); do not copy the bug.
- **R3 — Save-format compatibility.** If old Python saves must load in Godot: keep exact JSON key names
  (snake_case player/world keys, camelCase inside item_data), the `"x,y,z"` chunk-tile mod keys, version "3.0"
  handling, `.bak` recovery, and the template_locked default-True rule (world_system.py:966-978).
- **R4 — Training-coupled ML encoders must NOT be ported.** The 36×36/56×56 image renderers and the
  19/34/28-feature vectors are pixel/feature-exact contracts with the trained models (crafting_classifier.py:69,
  234, 502-509). Port them to C# and validation silently breaks. Keep them in the sidecar; the IPC payload is UI
  placement state, not tensors.
- **R5 — Silent fallback layers everywhere.** Dungeon config, village config, class bonuses, resource defs,
  geography config all have hardcoded fallbacks behind missing-JSON try/excepts (dungeon.py:74-78,
  village_generator.py:46-61, class_system.py:15-19, natural_resource.py:32-51, config.py:124-128). In Godot,
  fail loudly in dev builds — the Python versions have already produced masked-degradation bugs
  (e.g. biome_generator docstring vs actual distribution; dungeon.py:7-13 rarity comment is stale).
- **R6 — Namespace collision + sidecar geography dependency.** `systems/world_system.py` (game logic, ported)
  vs `world_system/` package (WMS, sidecar). The WMS reads `systems.geography.models.WorldMap`
  (geographic_registry.py:336) — after the port, the sidecar still needs geography data: either the sidecar
  keeps the Python geography module (reading the same `.gz` cache file the C# side writes — format must stay
  identical), or Godot streams geo lookups over IPC. Decide before splitting.
- **R7 — Wall-clock in gameplay/save data.** `time.time()` in quest timestamps, chest/dungeon ids, turret
  cooldowns (§4.4) → replace with game-time; the archive `duration` and reward adaptation ("time taken") get
  wrong values if pause/timescale exists.
- **R8 — Hidden render→logic coupling.** Chunk template locking fires from the renderer path
  (`get_visible_tiles` → `mark_rendered`, world_system.py:1128-1141). If the Godot view layer forgets to signal
  first-visibility, chunk templates silently re-roll after `ChunkTemplateDatabase` changes — a correctness bug
  that only manifests much later.
- **R9 — Known-dead / stale code to drop, not port:** collision A* (`find_path`/`get_next_step`,
  collision_system.py:364-539, zero callers), `init_collision_system` (l.595, never called),
  `WorldSystem._world_rng` (world_system.py:54, never used), `Chunk._water_chunks` legacy water tracking
  (chunk.py:43-66, save-compat only), `QuestManager.restore_from_save` active-quest stub (quest_system.py:586-595
  — replace with a real implementation), legacy `tiles/resources/chunks` properties (world_system.py:1633-1677).

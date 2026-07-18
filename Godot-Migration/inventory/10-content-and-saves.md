# 10 — Content JSON, Assets & Save Format (Porting Contract)

**Subsystem**: all content directories under `Game-1-modular/` (`items.JSON/`, `recipes.JSON/`, `placements.JSON/`, `Skills/`, `Definitions.JSON/`, `progression/`, `Update-1/`, `Update-2/`, `world_system/config/`), the `assets/` tree, and the save format (`systems/save_manager.py`, `save_system/`, `saves/` including WMS SQLite files).

**Verified against code 2026-07-17 (branch `crux-foundry`).** Every load-bearing claim cites `file:line`. Paths are relative to `C:/Users/vipVi/PycharmProjects/Game-1/Game-1-modular/` unless absolute.

**Standing decisions honored here**: content JSON is reused VERBATIM (loaders port, files never change); `world_system/` stays a Python sidecar (its config JSONs and SQLite dbs stay sidecar-owned); rendering configs feed a Godot interpretation layer, not a line-by-line port.

---

## 1. File table

### 1.1 Save-format code

| File | ~LOC | Responsibility | Disposition |
|---|---|---|---|
| `systems/save_manager.py` | 740 | Master save/load: builds/parses `autosave.json`, atomic write + `.bak`, version check, faction/registry hooks | **port-to-C#** (pure logic; faction/registry hooks become IPC calls) |
| `core/paths.py` | 162 | `PathManager` singleton: resource root vs save dir (dev = `./saves`, bundled = `%APPDATA%/Game1/saves`), `get_resource_path` / `get_save_path` / `get_faction_db_path` (`core/paths.py:44-50, 66-77, 122-129`) | **port-to-C#** (maps to `res://` + `user://` in Godot) |
| `systems/world_system.py` (save slice: `get_save_state`/`restore_from_save`/`_serialize_*` at `:1442-1640`, chunk file IO at `:929-947`, geo cache path `:246-250`) | ~250 of 1,700 | World save state: seed, game_time, placed entities, stations, dungeons, chests; per-chunk JSON files | **port-to-C#** (the serialization contract; world sim itself is another subsystem's doc) |
| `systems/chunk.py` (save slice `:625-724`) | ~100 of 724 | Per-chunk modification save data (`chunk_{x}_{y}.json`), respawn-on-elapsed-time restore | **port-to-C#** |
| `systems/geography/models.py` (persistence slice `:431-560`) | ~130 | `WorldMap.save/load` — gzip-compressed JSON world map cache (`world_map_seed_<seed>.gz`) | **port-to-C#** (GZipStream + System.Text.Json) |
| `systems/map_waypoint_system.py` (save slice `:648-700`) | ~55 of 720 | Map/waypoint save blob (`map_state`) | **port-to-C#** |
| `save_system/create_default_save.py` | 237 | Dev utility: writes a `default_save.json` — **writes stale version "2.0"** (`create_default_save.py:17`) vs current `SAVE_VERSION = "3.0"` (`systems/save_manager.py:19`) | **drop-dead-code** (regenerate a C# equivalent if needed; flagged stale) |
| `save_system/*.md` (3 docs) | ~400 | Save-system docs | reference only |

### 1.2 Content loaders (the code that must port so the JSON can stay verbatim)

| File | ~LOC | Responsibility | Disposition |
|---|---|---|---|
| `data/databases/material_db.py` | 325 | Materials + stackables from 7 files (`material_db.py:17-31`); icon-path convention (`:141-152`); generated overlay `items-materials-generated-*.JSON` (`:32,116`) | **port-to-C#** |
| `data/databases/equipment_db.py` | 400 | Weapons/armor/tools/accessories/stations; stat derivation from `stats-calculations.JSON`; icon subdir convention (`equipment_db.py:322-337`) | **port-to-C#** |
| `data/databases/recipe_db.py` | 256 | 5 recipe files, 3 output formats (outputId / outputs[] / enchantmentId) (`recipe_db.py:28-33, 50-72`) | **port-to-C#** |
| `data/databases/placement_db.py` | 220 | 5 discipline placement files, per-discipline schema (`placement_db.py:33-45`) | **port-to-C#** |
| `data/databases/skill_db.py` | 222 | Sacred glob `Skills/skills-skills-*.JSON` + `skills-generated-*.JSON` (`skill_db.py:15-17`); translation delegation (`:28-46`) | **port-to-C#** |
| `data/databases/title_db.py` | 263 | `progression/titles-*.JSON` glob + generated + Update-N re-merge (`title_db.py:16-18, 94-108`) | **port-to-C#** |
| `data/databases/class_db.py` | 108 | `progression/classes-1.JSON` (loaded at `core/game_engine.py:174`) | **port-to-C#** |
| `data/databases/npc_db.py` | 455 | NPC v3 + quests v3 with v2 fallback (`npc_db.py:260-284`), generated overlays (`:422,435`) | **port-to-C#** |
| `data/databases/skill_unlock_db.py` | 137 | `progression/skill-unlocks.JSON` (loaded `core/game_engine.py:177`) | **port-to-C#** |
| `data/databases/translation_db.py` | 134 | Word→number tables: `skills-translation-table.JSON` + `Skills/skills-base-effects-1.JSON` (`translation_db.py:72, 91`) | **port-to-C#** |
| `data/databases/resource_node_db.py` | 359 | `Definitions.JSON/resource-node-1.JSON` + `Resource-node-generated-*` (`resource_node_db.py:14-19, 125`) | **port-to-C#** |
| `data/databases/chunk_template_db.py` | 453 | `Definitions.JSON/Chunk-templates-*.JSON` + generated; density word→weight table `DENSITY_WEIGHTS` (`chunk_template_db.py:50-57, 244, 309`) | **port-to-C#** |
| `data/databases/world_generation_db.py` | 440 | `Definitions.JSON/world_generation.JSON` (`world_generation_db.py:187`) | **port-to-C#** |
| `data/databases/visual_config_db.py` | 266 | `Definitions.JSON/visual-config.JSON` (`visual_config_db.py:44`) | **decompose** — schema port, values feed Godot VFX layer |
| `data/databases/map_waypoint_db.py` | 326 | `Definitions.JSON/map-waypoint-config.JSON` (`map_waypoint_db.py:106`) | **decompose** — waypoint logic ports; px/UI keys feed Godot UI |
| `data/databases/quest_archive_db.py` | 236 | Quest archive (WES/WNS substrate) | **stays-python-sidecar** (writes feed WNS continuity) |
| `data/databases/update_loader.py` | 363 | Update-N package discovery via `updates_manifest.json` (`update_loader.py:26-38`), per-type filename-pattern scan (`:41-73`), load-order layering (`:294-324`) | **port-to-C#** |
| `rendering/image_cache.py` | 111 | pygame Surface icon cache; `items/` prefix rule for item icons (`image_cache.py:59-64`) | **engine-replaces** (Godot Texture2D registry; the *path convention* must survive) |

### 1.3 Content JSON directories (files are **reused verbatim** — dispositions describe runtime relevance)

| Directory / file | Lines | Loaded by | Status |
|---|---|---|---|
| `items.JSON/` (8 files, 4,682 lines) | | | |
| — `items-materials-1.JSON` | 823 | MaterialDatabase (`material_db.py:17`) | live |
| — `items-refining-1.JSON` | ~450 | Material (`:18`) + not equipment | live |
| — `items-alchemy-1.JSON` | ~550 | Material (consumables, `:19`) + Equipment (`game_engine.py:165`) | live |
| — `items-engineering-1.JSON` | ~500 | Material (devices, `:21`) + Equipment (`game_engine.py:162`) | live |
| — `items-smithing-2.JSON` | ~1,250 | Material (stations, `:25`) + Equipment (`game_engine.py:163`) | live |
| — `items-tools-1.JSON` | ~230 | Equipment (`game_engine.py:164`) | live |
| — `items-testing-tags.JSON` | ~380 | Material (`:23`) + Equipment (`game_engine.py:149,167`) | live (test content ships) |
| — `items-testing-integration.JSON` | ~250 | **nothing** (the loaded copy is `Update-1/items-testing-integration.JSON` via update_loader) | **dead duplicate** |
| `recipes.JSON/` (6 files + archive, 4,806 lines) | | RecipeDatabase (`recipe_db.py:28-33`) | |
| — smithing-3 / alchemy-1 / refining-1 / engineering-1 / adornments-1 | ~4,500 | recipe_db | live |
| — `recipes-tag-tests.JSON` | ~230 | tests only | test-only |
| — `archive/` (2 files) | — | nothing | dead |
| `placements.JSON/` (6 files, 7,210 lines) | | PlacementDatabase (`placement_db.py:33-45`) | |
| — smithing-1.json / refining-1 / alchemy-1 / engineering-1 / adornments-1 | ~6,400 | placement_db | live |
| — `placements-smithing-1-pre-fish.JSON` | ~800 | **nothing** | **dead backup** |
| `Skills/` (3 files, 1,419 lines) | | | |
| — `skills-skills-1.JSON` | ~900 | SkillDatabase glob `skills-skills-*` (`skill_db.py:16`) | live |
| — `skills-base-effects-1.JSON` | ~200 | TranslationDatabase (`translation_db.py:91`) | live |
| — `skills-testing-integration.JSON` | ~250 | **not matched by sacred glob**; the Update-1 copy loads instead | **dead duplicate** |
| `Definitions.JSON/` (19 files + archive, 7,377 lines) | | | |
| — `tag-definitions.JSON` (95 tags, 11 categories) | ~700 | TagRegistry (`core/tag_system.py:63-65`) | live |
| — `stats-calculations.JSON` | ~500 | stats (`entities/components/stats.py:45`), equipment_db, game_engine (`:4111`), combat_manager | live |
| — `hostiles-1.JSON` (21 abilities + enemies) | ~900 | EnemyDatabase via `CombatManager.load_config` (`core/game_engine.py:255-258`; `Combat/enemy.py:178-182`) | live |
| — `resource-node-1.JSON` (40 nodes) | ~900 | ResourceNodeDatabase (`game_engine.py:135-136`) | live |
| — `Chunk-templates-2.JSON` (21 templates) | ~800 | ChunkTemplateDatabase (`chunk_template_db.py:309`) | live |
| — `crafting-stations-1.JSON` (12 stations) | ~300 | MaterialDatabase as stations (`material_db.py:27`) | live |
| — `combat-config.JSON` | ~120 | CombatManager (`game_engine.py:256`), PlayerActions dodge (`Combat/player_actions.py:36`) | live |
| — `dungeon-config-1.JSON` | ~250 | DungeonManager (`systems/dungeon.py:58`) | live |
| — `fishing-config.JSON` | ~100 | fishing minigame (`Crafting-subdisciplines/fishing.py:64`) | live |
| — `map-waypoint-config.JSON` | ~300 | MapWaypointDatabase (`map_waypoint_db.py:106`) | live (keybindings block is doc-only, see §4) |
| — `visual-config.JSON` | ~200 | VisualConfigDatabase (`visual_config_db.py:44`) | live |
| — `world_generation.JSON` | ~300 | WorldGenerationDatabase (`world_generation_db.py:187`) | live |
| — `village-config.JSON` | ~220 | village_generator (`systems/geography/village_generator.py:37-38`) | live |
| — `skills-translation-table.JSON` | ~300 | TranslationDatabase (`translation_db.py:72`) | live |
| — `hostiles-testing-integration.JSON` | ~300 | **nothing at boot** (Update-1 copy loads via update_loader `enemies` pattern) | **dead duplicate** |
| — `templates-crafting-1.JSON` | ~600 | **no Python consumer** (grep-verified) | **dead (design doc as JSON)** |
| — `value-translation-table-1.JSON` | ~200 | **no Python consumer** — density words are actually resolved by hardcoded `DENSITY_WEIGHTS` (`chunk_template_db.py:50-57`) | **dead (stale doc; real table lives in code)** |
| — `JSON Templates` (extensionless) | ~450 | nothing (LLM authoring reference) | doc-only |
| — `Tentative 3 new templates JSONS` (extensionless) | ~550 | nothing — **not even valid JSON** (parse fails) | doc-only |
| — `archive/` (1 backup) | — | nothing | dead |
| `progression/` (9 files, 2,122 lines) | | | |
| — `classes-1.JSON` (6 classes) | ~350 | ClassDatabase (`game_engine.py:174`; `systems/class_system.py:30`) | live |
| — `titles-1.JSON` (10 titles) | ~300 | TitleDatabase glob `titles-*.JSON` (`title_db.py:17`) | live |
| — `skill-unlocks.JSON` (13 unlocks) | ~350 | SkillUnlockDatabase (`game_engine.py:177`) | live |
| — `npcs-3.JSON` / `quests-3.JSON` | ~500 | NPCDatabase v3 path (`npc_db.py:260, 283`) | live |
| — `npcs-enhanced.JSON` / `quests-enhanced.JSON` | ~350 | fallback only if v3 missing (`npc_db.py:261, 284`) | dormant fallback |
| — `npcs-1.JSON` / `quests-1.JSON` | ~130 | **nothing** | **dead (superseded)** |
| `Update-1/` (8 files, 1,167 lines) | | update_loader pattern scan (`update_loader.py:41-73`) — items/skills/hostiles/recipes load; `npcs-village-dummy.JSON` and `placements-smithing-testing-modified.json` match **no pattern** → silently skipped | live + 2 dead files |
| `Update-2/` (4 files, 676 lines) | | update_loader: stations→materials, skills, titles, skill-unlocks (fishing content) | live |
| `updates_manifest.json` (root) | 10 | `update_loader.py:26-38`; lists `["Update-1","Update-2"]` | live |
| `world_system/config/` (50 files, 13,271 lines) | | WMS/WNS/WES prompt fragments, backend config, tag registries, stat manifests | **stays-python-sidecar** (never loaded by game-logic C#; one exception: `village-config.json` fallback path at `village_generator.py:38`) |

### 1.4 Assets (counts verified by extension scan)

Total **3,997 files**: 3,977 `.png`, 5 `.jpg`, 6 `.py` (tooling), 5 `.md`, 2 `.txt`, 2 `.json` (tooling registries).

| Dir | PNGs | Runtime-loaded? | Notes |
|---|---|---|---|
| `assets/items/` (9 subdirs: accessories, armor, consumables, devices, mace, materials, stations, tools, weapons) | 178 | **yes** — via `ImageCache` with `items/` prefix rule (`rendering/image_cache.py:59-64`) | icon path convention: `{subdir}/{item_id}.png` auto-derived (`material_db.py:141-152`, `equipment_db.py:322-337`) |
| `assets/enemies/` | 16 | yes (direct path) | `enemies/{enemy_id}.png` |
| `assets/resources/` | 48 | yes | `resources/{node_id}.png` |
| `assets/skills/` | 41 | yes | |
| `assets/titles/` | 10 | yes | |
| `assets/classes/` | 6 | yes | |
| `assets/npcs/` | 3 | yes (`rendering/renderer.py:967-969`: `npcs/{npc_id}.png`) | |
| `assets/quests/` | 3 | yes | |
| `assets/minigame_backgrounds/` | 0 png (5 jpg) | yes (`core/minigame_effects.py:23`) | crafting minigame backdrops |
| `assets/custom_icons/` | 5 | via remap tooling | |
| `assets/icons-generated-cycle-1..5/` | 2,969 | **no** — icon-generation working dirs (only referenced by `assets/*.py` tooling) | **do not ship** |
| `assets/replaced_placeholders/` | 465 | no | tooling archive |
| `assets/generated_icons/` | 233 | no | tooling |
| `assets/icons/` | 0 | no (md + generator script) | |

**Shippable asset set ≈ 305 PNGs + 5 JPGs**; the other ~3,670 PNGs are icon-pipeline intermediates. Invented items use a shared placeholder `{subdir}/invented_default.png` (`core/game_engine.py:5599, 6009-6032`).

---

## 2. Public surface (what other subsystems actually call)

| API | Callers (file:line) |
|---|---|
| `SaveManager.save_game(character, world, quests, npcs, filename, dungeon_manager, game_time, map_system)` | `core/game_engine.py:616, 691, 1191, 2018, 12023` (autosave on quit, death, hotkey, menu) |
| `SaveManager.load_game(filename)` → dict | `core/game_engine.py` boot/load flows (`:1247-1269, 2087-2139, 2178-2227`) |
| `SaveManager.restore_npc_state(npcs, npc_state)` (static) | `game_engine.py:1259, 2125, 2213` |
| `SaveManager.restore_dungeon_state / restore_faction_state / restore_game_settings` | `game_engine.py` load flows; `save_manager.py:579-665` |
| `SaveManager.get_save_files()` / `delete_save_file()` | save/load menu UI |
| `get_resource_path / get_save_path / get_faction_db_path` (module funcs, `core/paths.py:142-161`) | virtually every loader + `world_system/` sidecar (`faction_system.py:28,48`) |
| `WorldSystem.get_save_state()` / `restore_from_save()` | `save_manager.py:392`; `game_engine.py:1253, 2119, 2207` |
| `Chunk.get_save_data()` / `restore_modifications()` | `world_system.py:929-947` (`_save_chunk_to_file` / `_load_chunk_from_file`) |
| `WorldMap.save(path)` / `WorldMap.load(path)` | `world_system.py:262-292` (geo cache boot path) |
| `MapWaypointSystem.get_save_data()` / `restore_from_save()` | `save_manager.py:72`; `game_engine.py:1269, 2139, 2227` |
| `*.get_instance()` on every database singleton + `load_from_file(s)` | boot sequence `core/game_engine.py:135-182`; hot-reload path `world_system/content_registry/database_reloader.py` (sidecar) |
| `load_all_updates(root)` | `core/game_engine.py:181-182` |
| `GameEngine.register_saved_invented_recipes()` | `game_engine.py:1250, 2116, 2204` — re-registers `player.invented_recipes` into Recipe/Placement/Material DBs on load (`:6204-6226`) |

**Hidden coupling**: `save_manager.create_save_data` imports from the sidecar-bound `world_system.living_world.factions` (`save_manager.py:76`) and `world_system.content_registry` (`:90`) to embed `faction_state` and flush `content_registry.db` at save time. In Godot this becomes two IPC round-trips ("give me faction snapshot", "flush registry now") — both already degrade gracefully to `{}` on failure (`save_manager.py:78-80, 105-123`), which is the correct IPC-timeout posture too.

---

## 3. Dependency edges

**This subsystem imports**: `data.models.*` (dataclasses for materials/equipment/recipes/skills/world), `core.paths` (everywhere), `core.config` (`save_manager.py:134,594` for `KEEP_INventORY`; `chunk.py` for `CHUNK_SIZE`), `world_system.living_world.factions` + `world_system.content_registry` (save hooks, §2), `Combat.enemy` (update_loader `:132`).

**Who imports this subsystem**: everything. `core/game_engine.py` (boot + save/load + invented recipes), all `Crafting-subdisciplines/*` (recipe/placement/material lookups), `Combat/*` (equipment stats, hostiles, combat-config), `entities/*` (stats-calculations, skill/title/class DBs), `rendering/*` (icon paths via material/equipment defs), `systems/*` (world gen, dungeon, quest, npc), `world_system/content_registry/database_reloader.py` (sidecar reaches IN to call `reload()` on Material/Skill/Title/ResourceNode/ChunkTemplate/NPC DBs after committing generated files — in Godot this becomes an IPC "content-committed" notification that triggers C#-side reload).

**Sidecar boundary files on disk** (shared contract, not imports): `items.JSON/items-materials-generated-*.JSON`, `Definitions.JSON/hostiles-generated-*.JSON`, `Definitions.JSON/Resource-node-generated-*.JSON`, `Definitions.JSON/Chunk-templates-generated-*.JSON`, `Skills/skills-generated-*.JSON`, `progression/titles-generated-*.JSON`, `progression/npcs-generated-*.JSON`, `progression/quests-generated-*.JSON` (writer: `world_system/content_registry/generated_file_writer.py:10-14`; readers: each DB's `GENERATED_GLOB`). **The generated-file naming convention is the real WES→game API and must survive the port unchanged.**

---

## 4. Engine coupling (pygame / pixel / screen touchpoints to redesign)

| Touchpoint | file:line | Redesign |
|---|---|---|
| `ImageCache` returns `pygame.Surface`, uses `pygame.image.load`, `convert_alpha`, `smoothscale` | `rendering/image_cache.py:30-88` | Replace with Godot `Texture2D` registry autoload. **Keep** the path rules: `items/` prefix for item icons vs direct paths for `enemies/ resources/ skills/ titles/ npcs/ quests/ classes/` (`:59-64`) |
| `TILE_SIZE = 32` px/tile; `SCREEN 1600x900`; `FPS 60` | `core/config.py:14-16, 24-25` | Tile becomes a 3D world unit (1 tile = 1m recommended); screen constants die |
| `visual-config.JSON` px + ms fields: `stackOffsetPx: 18`, `facingIndicatorWidth: 2` (px), `lifetimeMs`, `idleBobPeriodMs`, RGB arrays for damage-type colors | file itself; loader `visual_config_db.py:44` | Interpretation layer: RGB arrays → `Color`; px offsets → screen-space label logic in Godot; **type→color mapping is game data and should survive** |
| `map-waypoint-config.JSON`: `map_window_size: [700,600]` px, `chunk_render_size: 12` px, RGBA colors | file, `ui_settings`/`map_display` blocks | Map UI is a Godot Control scene; zoom/radius/teleport *rules* port, px values become theme constants |
| `map-waypoint-config.JSON > keybindings` is **documentation only** — real bindings hardcoded in `core/game_engine.py:807-1249` (admitted in the file's own `_comment`, §15 trap 18) | file | Godot InputMap replaces both; do not "port" the JSON keybindings |
| `fishing-config.JSON > minigame.pond_dimensions {width:500, height:400, margin:50}`, `target_radius: 40`, `expand_speed: 80` (px, px/s) | file; consumer `Crafting-subdisciplines/fishing.py:64` | Minigames stay 2D Control overlays — px values stay valid inside a fixed-size SubViewport; classify **reusable-with-fixed-virtual-canvas** |
| `sprite_color` RGB on NPCs and village templates | `progression/npcs-3.JSON` (npcs[].sprite_color), `Definitions.JSON/village-config.JSON > npc_templates[].sprite_color` | Fallback tint when no sprite exists; keep as `Color` modulate fallback |
| `minigame_backgrounds` JPG loading | `core/minigame_effects.py:23-29` | TextureRect in minigame panels |
| Placement grids `"row,col"` string keys | `placements.JSON/*` (e.g. `placements-smithing-1.json` placements[0].placementMap) | **NOT pixels** — logical grid cells (smithing 3x3/5x5, from recipe `gridSize`). Reusable verbatim; only the grid *renderer* is engine work |
| World/entity positions in saves | tile coordinates, already `{x,y,z}` (`save_manager.py:151-155`) | Engine-agnostic; see §9 |
| `WorldMap` gz cache regeneration triggers pygame-free code but `_generate_map_images()` renders with pygame | `systems/world_system.py:270-297` | Map images regenerate in Godot; gz cache itself is pure JSON |

**Verdict on the content dirs themselves**: `items.JSON/`, `recipes.JSON/`, `Skills/`, `progression/`, `placements.JSON/`, and the gameplay configs (`stats-calculations`, `tag-definitions`, `hostiles-1`, `resource-node-1`, `Chunk-templates-2`, `combat-config`, `dungeon-config-1`, `world_generation`, `village-config`, `crafting-stations-1`, `skills-translation-table`, `skill-unlocks`) are **reusable-verbatim** — units are tiles, seconds, ms, and abstract words (`"moderate"`, `"very_high"`). Only three files carry pixel/screen semantics needing an interpretation layer: `visual-config.JSON`, `map-waypoint-config.JSON`, `fishing-config.JSON` (partially — its scoring/thresholds blocks are engine-agnostic).

---

## 5. Constants & formulas (exact values, from code and content)

Sacred constants that live **in this subsystem's files**:

| Constant | Value | Source |
|---|---|---|
| Tier multipliers | T1=1.0, T2=2.0, T3=4.0, T4=8.0 | `Definitions.JSON/stats-calculations.JSON > tierMultipliers` (also hardcoded in stats code) |
| Global bases | weaponDamage 10, armorDefense 10, toolGathering 10, durability 250, weight 1.0, attackSpeed 1.0 | `stats-calculations.JSON > globalBases` |
| Equipment damage formula | `base × tier × category × type × subtype × item`, variance 0.85–1.15 | `stats-calculations.JSON > damageSystem` (category: weapon 1.0 / tool 0.6 / shield 0.4; subtypes e.g. greatsword 1.4, maul 1.5, fishing_rod 0.5) |
| Armor defense formula | `10 × tier × slot × item` (head 0.8, chest 1.5, legs 1.2, feet 0.7, hands 0.6) | `stats-calculations.JSON > defenseSystem` |
| Durability effectiveness floor | `<=0 dur → 0.5`; `dur% >= 0.5 → 1.0`; else `1.0 - (0.5 - dur%) * 0.5` — items never break | `data/models/equipment.py:49-55` |
| EXP curve | `int(200 * 1.75**(lvl-1))`, max level 30 | `entities/components/leveling.py:9` |
| LCK crit | `0.12/pt` via env `CRUX_LCK_CRIT_PER_POINT` | `Combat/combat_manager.py:24` |
| Crit multiplier | 2.0 | `Definitions.JSON/combat-config.JSON > damageFormulas.critMultiplier` |
| Dodge | duration 250ms, speed ×3.0, cooldown 800ms, iframes 200ms | `combat-config.JSON > dodgeMechanics` (consumed `Combat/player_actions.py:36`) |
| Combat mechanics | attack range 2.0 tiles, base cooldown 1.0s, tool 0.5s, corpse 60s, regen timeout 5.0s | `combat-config.JSON > combatMechanics` |
| Chunk geometry | `CHUNK_SIZE = 16` tiles (`core/config.py:24` AND `world_generation.JSON > chunk_loading.chunk_size` — **dual-sourced, must stay in sync**), load_radius 4, spawn exclusion radius 8 | `world_generation.JSON` |
| Density words | very_low…very_high → weights, `very_high: 3.0` etc. | `chunk_template_db.py:50-57` (**in code, not JSON** — `value-translation-table-1.JSON` is a stale doc) |
| Save version | `"3.0"` | `systems/save_manager.py:19` |
| Default inventory stack | maxStack default 99 | `material_db.py:163` |
| WorldMap gz compression | gzip level 6, compact separators | `systems/geography/models.py:497-498` |

⚠ **Tension noted (do not relitigate, just know)**: `combat-config.JSON > damageFormulas` self-describes as "for reference, implemented in code" — the JSON strings are NOT the executable formula. The canonical damage pipeline lives in `Combat/combat_manager.py`. Port the code, not the JSON prose.

---

## 6. Event topics (GameEventBus)

**None.** `systems/save_manager.py`, `core/paths.py`, all `data/databases/*` loaders, and `save_system/` neither publish nor subscribe to `events/event_bus.py` (grep-verified: zero `event_bus`/`publish` references). Content loading is synchronous boot-time work; save/load is imperative. The content-reload trigger from WES arrives via direct method calls from `world_system/content_registry/database_reloader.py`, not the bus — in Godot that direct call becomes an IPC message that the C# side maps onto its own reload entry points.

---

## 7. Content JSON consumed — loader map + schema sketches

### 7.1 Boot load order (`core/game_engine.py:135-182`) — replicate exactly

1. ResourceNodeDatabase ← `Definitions.JSON/resource-node-1.JSON` (`:135`)
2. MaterialDatabase ← materials-1, refining-1, alchemy-1(consumable), engineering-1(device), testing-tags(device/weapon), smithing-2(station), crafting-stations-1(station) (`:138-155`)
3. TranslationDatabase ← skills-translation-table + skills-base-effects-1 (`:156`)
4. RecipeDatabase ← 5 files (`:157`)
5. PlacementDatabase ← 5 files (`:158`)
6. EquipmentDatabase ← engineering-1, smithing-2, tools-1, alchemy-1, testing-tags (`:162-167`)
7. TitleDatabase (glob), ClassDatabase, SkillDatabase (glob), SkillUnlockDatabase, NPCDatabase (v3+fallback) (`:173-178`)
8. `load_all_updates()` — Update-N overlay per `updates_manifest.json` (`:181-182`)
9. Combat config + hostiles via `CombatManager.load_config` (`:255-258`)

Order matters twice: (a) Equipment stat derivation reads stats-calculations; (b) Update-N **overwrites** same-id entries, and `reload()` paths must re-merge Update-N afterward (`skill_db.py:109-123`, `title_db.py:94-108`).

### 7.2 Schema sketches (top-level keys, from parse of every file)

- **items-materials-1**: `{metadata, materials[]}`; material: `materialId, name, tier, category, rarity, metadata{narrative, tags}` (77 entries).
- **items-refining/alchemy/engineering/smithing/tools**: `{metadata, <category-buckets>[]}` (e.g. `weapons, armor, tools, accessories, stations`); item: `itemId, name, tier, rarity, type, subtype, category, slot?, range?, stackSize?, statMultipliers{}, effectTags[], effectParams{}, requirements{}, flags{}, metadata{narrative, tags}`. Loader iterates **all list-valued top-level keys** — bucket names are cosmetic.
- **recipes-***: `{metadata, recipes[]}`; three shapes handled by `recipe_db.py:50-72`: standard `outputId/outputQty/stationTier`, refining `outputs[{materialId,quantity}] + stationTierRequired + fuelRequired`, enchanting `enchantmentId + applicableTo + effect`.
- **placements-smithing/adornments**: `{placements:[{recipeId, placementMap{"r,c": materialId}, metadata{gridSize}}]}` — grid-cell keys.
- **placements-alchemy**: `ingredients[{slot, materialId, quantity}]` (ordered slots); **-refining**: `coreInputs[] + surroundingInputs[]`; **-engineering**: `slots[{type: FRAME|FUNCTION|POWER, materialId, quantity}]`. All carry `narrative` used as minigame flavor.
- **skills-skills-1**: `{skills:[{skillId, name, tier, rarity, categories[], tags[], effect{}, cost{}, requirements{}, narrative}]}` (30); word-values (`manaCost: "moderate"`) resolved via TranslationDatabase.
- **tag-definitions**: `{categories{11}, tag_definitions{95: {category, description, priority, conflicts_with[]}}, conflict_resolution, context_inference}`.
- **hostiles-1**: `{abilities[21: {abilityId, cooldown, tags[], effectParams, triggerConditions}], enemies[{enemyId, tier, category, behavior, stats{health, damage[min,max], defense, speed(tiles/s), aggroRange(tiles), attackSpeed}, drops[{materialId, quantity[], chance-word}], aiPattern{}}]}`.
- **resource-node-1**: `{nodes[40: {resourceId, tier, category, baseHealth, requiredTool, respawnTime, drops[]}]}`.
- **Chunk-templates-2**: `{templates[21: {chunkType, category, theme, resourceDensity{node: {density-word, tierBias-word}}, enemySpawns{}, generationRules{rollWeight, spawnAreaAllowed, adjacencyPreference[]}}]}`.
- **classes-1**: `{classes[6: {classId, tags[], startingBonuses, startingSkill, preferredDamageTypes…}], classSwitching, statDescriptions}`.
- **titles-1**: `{titles[{titleId, titleType, difficultyTier, bonuses, acquisitionMethod, prerequisites, isHidden}], titleCategories, difficultyTiers}`.
- **npcs-3**: `{npcs[{npc_id, name, position{x,y,z} (tiles), interaction_radius, faction, locality, personality, narrative (immutable past), affinity_seeds, speechbank{greeting[], farewell[], idle_barks[], quest_offer[], quest_complete[]}, services, quests[], sprite_color, unlockConditions}]}`.
- **quests-3**: `{quests[{quest_id, quest_type, tier, objectives, rewards, rewards_prose, expiration, wns_thread_id, given_by/return_to, completion_dialogue}]}` — `wns_thread_id` is a sidecar correlation key; preserve verbatim.
- **skill-unlocks**: `{skillUnlocks[13: {unlockId, skillId, unlockMethod, unlockTrigger, conditions, cost}]}` plus doc keys `FIELD_DOCUMENTATION, USAGE_NOTES` (loader ignores unknown keys — porter must too).
- **stats-calculations / combat-config / world_generation / dungeon-config / fishing-config / village-config / map-waypoint-config / visual-config**: config objects; every file mixes real keys with `_comment`/`_note`/`metadata` doc keys. **Contract: ignore unknown keys, never fail on doc keys.**

### 7.3 Engine-agnosticism classification (per directory)

| Directory | Classification |
|---|---|
| `items.JSON/`, `recipes.JSON/`, `Skills/`, `progression/` | **reusable-verbatim** (tiles/seconds/words; icon paths derived, not stored) |
| `placements.JSON/` | **reusable-verbatim** (logical grid cells, never pixels) |
| `Definitions.JSON/` gameplay set (tags, stats, hostiles, nodes, chunk templates, stations, combat, dungeon, world_gen, village, translations, skill-unlocks) | **reusable-verbatim** |
| `Definitions.JSON/visual-config.JSON` | **needs-interpretation-layer** (px, ms, RGB triples → Godot VFX/UI) |
| `Definitions.JSON/map-waypoint-config.JSON` | **needs-interpretation-layer** (px window/render sizes, RGBA, doc-only keybindings) |
| `Definitions.JSON/fishing-config.JSON` | **split**: `minigame` block px-based (fine inside fixed-size 2D SubViewport); `scoring/success_thresholds/xp_rewards/tier_scaling` engine-agnostic |
| `Update-1/`, `Update-2/` | reusable-verbatim (same schemas as parents) |
| `world_system/config/` | sidecar-owned; not part of the C# content contract |

---

## 8. Persistent state — the save contract

### 8.1 Primary save file: `saves/autosave.json` (or any `*.json` in save dir)

Written by `SaveManager.create_save_data` (`save_manager.py:31-125`). Full key tree:

```
version: "3.0"                          (save_manager.py:19)
save_timestamp: ISO-8601
player:                                 (save_manager.py:139-198)
  position: {x, y, z}                   (floats, tile coords)
  facing: str                           ("up"/"down"/"left"/"right")
  stats: {strength, defense, vitality, luck, agility, intelligence}
  leveling: {level, current_exp, unallocated_stat_points}
  health, max_health, mana, max_mana
  class: classId | null
  inventory: [slot|null × 30]           (save_manager.py:239-310)
    slot: {item_id, quantity, max_stack, rarity,
           equipment_data?: {item_id, name, tier, rarity, slot, damage[2]|num,
             defense, durability_current, durability_max, attack_speed,
             efficiency, weight, range, hand_type, item_type, icon_path,
             soulbound, stat_multipliers?, tags?, effect_tags?, effect_params?,
             bonuses?, enchantments?, requirements?},
           crafted_stats?: {...}}
  equipment: {slot_name: equipment_data|null}   (same shape; save_manager.py:312-371)
  equipped_skills: [skillId]
  known_skills: {skillId: {level, experience}}
  titles: [titleId]
  activities: {activity: count}
  stat_tracker: {...}                   (SQL-backed analytics snapshot)
  skill_unlocks: {unlocked_skills[], pending_unlocks[]}
  invented_recipes: [{timestamp, discipline, item_id, item_name, item_data{},
                      from_cache, recipe_inputs[], station_tier, narrative,
                      placement_data{}, icon_path}]   (save_manager.py:200-237)
world_state:                            (world_system.py:1442-1462 + game_time)
  seed: int                             (drives deterministic world regen)
  game_time: float
  placed_entities: [{position{x,y,z}, item_id, entity_type(enum NAME), tier,
                     health, owner, time_remaining, tags?, effect_params?,
                     range?, damage?, attack_speed?}]
  crafting_stations: [{position, station_type(enum NAME), tier}]
  discovered_dungeons: [{chunk_x, chunk_y, position, rarity(enum VALUE)}]
  spawn_chest: LootChest.to_dict() | null
  death_chests: [LootChest.to_dict()]
quest_state:                            (save_manager.py:399-423)
  active_quests: {questId: {status, progress{}, baseline_combat_kills,
                            baseline_inventory}}
  completed_quests: [questId]
npc_state: {npcId: {current_dialogue_index}}    (save_manager.py:425-443)
game_settings: {keep_inventory}          (save_manager.py:127-137)
dungeon_state?: DungeonManager.to_dict() (in_dungeon, dungeons_completed,
  dungeons_by_rarity, current_dungeon?)  (save_manager.py:66-68, 603-640)
map_state?:                              (map_waypoint_system.py:648-662)
  explored_chunks: [ExploredChunk.to_dict()]
  waypoints: [Waypoint.to_dict()|null]
  last_teleport_time, map_zoom, map_scroll_x, map_scroll_y, stats{}
faction_state: {...}                     (sidecar-provided; save_manager.py:74-80)
content_registry_state: {db_path, stats} | {initialized:false} | {}   (:89-123)
```

**Enum encodings to preserve exactly**: `entity_type`/`station_type` serialize the enum **NAME** (`PlacedEntityType[...]`, `StationType[...]` — `world_system.py:1475, 1499, 1545, 1600`); dungeon `rarity` serializes the enum **VALUE** (`:1511, 1582`). Mixing these up silently corrupts loads.

### 8.2 Sidecar save files (same directory, verified in `saves/`)

| File | Format | Writer |
|---|---|---|
| `saves/chunks/chunk_{cx}_{cy}.json` | JSON: `{chunk_x, chunk_y, chunk_type, template_locked, modified_resources[{local_x, local_y, resource_type, current_hp, max_hp, depleted, time_until_respawn}], dungeon_entrance?, unload_timestamp}` | `chunk.py:631-667` via `world_system.py:929` — only chunks with modifications; `template_locked` defaults **true** on load for legacy files (`chunk.py:644-648`); respawn credit for elapsed offline time at `chunk.py:697-704` |
| `saves/world_map_seed_{seed}.gz` | gzip(JSON, level 6): `{seed, world_size, nations{}, regions{}, provinces{}, districts{}, ecosystems{}, chunk_data:[[cx,cy,nation,region,province,district,chunk_type,biome,ecosystem,danger]...]}` | `geography/models.py:431-501`; ~1.5 MB each; pure cache — safe to delete, regenerates deterministically from seed |
| `saves/faction.db` | SQLite | sidecar (`world_system/living_world/factions/faction_system.py:48` via `core/paths.py:129`) |
| `saves/world_memory.db` | SQLite (20 tables) | sidecar (`world_system/world_memory/event_store.py:378`) |
| `saves/layer_store.db` (+ `-shm`/`-wal`) | SQLite WAL | sidecar (`world_memory_system.py:122`) |
| `saves/world_narrative.db` | SQLite | sidecar (`world_system/wns/narrative_store.py:84`) |
| `saves/content_registry.db` | SQLite | sidecar (`content_registry/registry_store.py:192`); flushed at save time (`save_manager.py:89-100`) |

**Godot rule: the five `.db` files are sidecar-owned. The C# game must never open them.** The save-time flush and faction snapshot become IPC requests (§2).

### 8.3 Atomicity, backup, versioning

- Serialize fully in memory first — a serializer error can never truncate a good save (`save_manager.py:503`).
- Atomic write: `.tmp` + `flush` + `fsync` + `os.replace`; previous save rotated to `.bak` (`:508-518`). C#: `File.Replace` or write-temp + `File.Move(overwrite)` with `FileStream.Flush(true)`.
- Load falls back to `.bak` on `JSONDecodeError`/`UnicodeDecodeError` (`:547-562`).
- Version mismatch **warns but proceeds** (`:564-567`) — there is no migration machinery. Godot port should keep `"3.0"` and keep the warn-only posture; add a `godot_port` marker field only if needed (loader ignores unknown keys).
- Missing-key tolerance is the de-facto schema: every restore uses `.get(key, default)` (e.g. `world_system.py:1534, 1551-1556`; `map_waypoint_system.py:691-694`). The C# DTOs must make every field optional with the same defaults.

### 8.4 Save-compat goal (Python save loads in Godot)

Must-read: all §8.1 keys with defaults; `world_state.seed` (world regen must be re-implemented deterministically or chunk-cache-compatible — see risk R1); chunk files; enum name/value conventions. Must-write: identical shapes, 2-space-indent JSON (cosmetic), UTF-8. `datetime.now().isoformat()` timestamps parse fine with `DateTime.Parse`. Floats: Python emits full-precision doubles; C# `System.Text.Json` doubles round-trip fine.

---

## 9. 3D notes (what necessarily changes 2D→3D)

- **Positions are already 3-component**: every serialized position is `{x, y, z}` with z≈0 (`save_manager.py:151-155`, npcs-3 positions). Standing decision maps Python `(x, y)` → Godot `(x, 0, z)`: i.e. **Python `y` becomes Godot `z`; Godot `y` is height**. The save file keeps Python's meaning (`y` = north/south, `z` = height) — the mapping lives in one conversion function, never in the DTOs, or a Python save stops loading.
- **facing** is a 4-way string in the save (`character.facing`, `save_manager.py:156`). 3D uses continuous yaw; keep serializing the quantized cardinal string (derive from yaw on save, apply on load) for compatibility.
- **Distances/ranges in content are tile-radii** (`aggroRange: 5`, `playerAttackRange: 2.0`, `interaction_radius`). In 3D these become horizontal (XZ-plane) distances — do NOT include height, matching the ported `TargetFinder DistanceMode` decision.
- **Chunk system survives**: 16×16-tile chunks (`core/config.py:24`) become 16×16-unit ground patches; chunk keys `(cx, cy)` in saves map to `(cx, cz)` regions. `world_map_seed` gz and `chunk_*.json` need zero format changes.
- **Placement grids and minigames**: untouched — they're 2D UI logic (Control overlays per standing decision).
- **Camera/screen assumptions die**: `SCREEN_WIDTH/HEIGHT`, map px sizes, damage-number px offsets all become Godot UI/camera concerns; none are persisted in saves.
- **Hitboxes**: nothing in this subsystem's JSON encodes hitboxes (they're config-driven in `Combat/` — other doc). Enemy `stats.speed` (tiles/s) becomes units/s.

---

## 10. Godot mapping

### Pure-logic assembly (`Game1.Core.dll`, testable via `dotnet test`, zero Godot references)

| C# type | Replaces | Notes |
|---|---|---|
| `ContentPaths` | `core/paths.py` | interface `IContentRoot` with dev/exported implementations; save dir → `user://saves` (Godot) or plain dir (tests) |
| `MaterialDatabase, EquipmentDatabase, RecipeDatabase, PlacementDatabase, SkillDatabase, TitleDatabase, ClassDatabase, NpcDatabase, SkillUnlockDatabase, TranslationDatabase, ResourceNodeDatabase, ChunkTemplateDatabase, WorldGenerationConfig, TagRegistry, StatsCalculations, CombatConfig, DungeonConfig, FishingConfig, VillageConfig` | `data/databases/*` + config loaders | Keep singleton-ish access behind a `ContentServices` container (constructor-injected for tests, one shared instance at runtime). Parse with `System.Text.Json` + `JsonSerializerOptions { PropertyNameCaseInsensitive = false }` and **DTOs that ignore unknown members** (default behavior) — the doc-key convention (`_comment`, `metadata`, `FIELD_DOCUMENTATION`) requires it. Case-sensitive exact key names (`camelCase` in content, `snake_case` in some progression files — mirror the Python `.get` strings exactly, do not "normalize") |
| `UpdatePackageLoader` | `update_loader.py` | manifest read + the six filename-pattern scans (`update_loader.py:41-73`) + load order (`:315-321`) |
| `GeneratedContentWatcher` | `database_reloader.py` call-ins | applies `*-generated-*.JSON` overlays when the sidecar signals commit over IPC |
| `SaveModel` (DTO tree) + `SaveManager` | `systems/save_manager.py` | atomic write (`File.Replace`), `.bak` fallback, version warn; faction/registry sections filled from `ISidecarClient` with timeout→`{}` degrade |
| `WorldSaveState`, `ChunkSaveData`, `WorldMapCache` | world/chunk/geography save slices | `WorldMapCache` = GZipStream + JSON; enum-NAME vs enum-VALUE encodings preserved via explicit converters |
| `MapWaypointState` | map save slice | |
| `IconPathResolver` | icon-path conventions in `material_db.py:141-152` / `equipment_db.py:322-337` / `image_cache.py:59-64` | pure string logic; returns `"items/materials/copper_ore.png"`-style virtual paths |

### Engine glue (thin, in the Godot project)

| Godot piece | Role |
|---|---|
| `ContentServer` (autoload) | boots `ContentServices` in the documented order (§7.1) before any scene needs data; exposes to GDScript-free C# scenes |
| `TextureRegistry` (autoload) | replaces `ImageCache`: virtual icon path → `Texture2D`; content PNGs shipped as raw files loaded via `Image.LoadPngFromBuffer` (avoids 3,977-file import churn; only ship the ~305 runtime PNGs) |
| `SaveService` (autoload) | wraps `SaveManager`, owns the `user://saves` dir, triggers sidecar flush via `SidecarClient` |
| `SidecarClient` (autoload) | local IPC to the Python `world_system` process; the faction-snapshot, registry-flush, and content-committed messages defined in §2/§3 |
| Content files | ship the content dirs verbatim inside the .pck as raw resources (or alongside the executable) — loaders read them as text, not Godot Resources, so `.JSON` (uppercase ext) files need no importer |

### Placement in the repo
`Game1.Core/Content/*`, `Game1.Core/Persistence/*` (pure assembly); `godot/autoload/*.cs` (glue). Content dirs copied unmodified into the Godot project.

---

## 11. Port complexity, ordering, risks

**Complexity: L** overall.
- Loaders: **M** — ~4,700 LOC of Python but highly mechanical; the subtlety is replicating lenient parsing (`.get` defaults, unknown-key tolerance, three recipe shapes, category-bucket iteration).
- Save format: **M** — DTO tree is big but flat; enum-encoding traps and optional-everything discipline are the work.
- Assets: **S** — path conventions + pruning the 3.7k tooling PNGs.
- Interpretation layer (visual/map/fishing px configs): **S**, but coordinated with the rendering-replacement doc.

**Ordering constraints**
1. `ContentPaths` + JSON DTOs **first** — every other subsystem's port consumes these databases (equipment stats, combat, crafting, world gen all read them).
2. `TranslationDatabase` + `StatsCalculations` before `EquipmentDatabase`/`SkillDatabase` (stat derivation and word→number resolution happen at load).
3. Boot order §7.1 including `UpdatePackageLoader` before any gameplay test that touches fishing (Update-2) or test content (Update-1).
4. `SaveManager` after `WorldSystem`/`Character` DTO shapes exist; chunk save format after chunk generation port.
5. `GeneratedContentWatcher` + `SidecarClient` last — needs the IPC design from the world_system sidecar doc.

**Top risks / gotchas**
- **R1 — Seed-deterministic world regen is the real save format.** The JSON save stores only `seed` + diffs (`world_system.py:1455`); everything else regenerates. If the C# world generator (noise, `random.Random(seed)` sequences, village RNG `world_system.py:318`) doesn't reproduce Python's RNG streams bit-for-bit, an old save loads into a *different world* with orphaned chunk-diff files. Options: port Python's Mersenne-Twister usage faithfully, or treat `world_map_seed_{seed}.gz` as the authoritative map (ship it with the save instead of regenerating) — the gz cache already contains the full 512×512 chunk assignment and loads engine-agnostically.
- **R2 — Enum NAME vs VALUE serialization** (`entity_type`/`station_type` by NAME, dungeon `rarity` by VALUE, §8.1) — an innocent `JsonStringEnumConverter` everywhere breaks loads silently.
- **R3 — Update-N overlay + reload re-merge**: overlays mutate the same dictionaries as sacred content; the reload paths re-apply Update-N (`skill_db.py:109-123`) or fishing content vanishes. The C# reload triggered by sidecar commits must replicate the same layering: sacred → generated → Update-N.
- **R4 — Dead/stale content masquerading as live**: `value-translation-table-1.JSON` and `templates-crafting-1.JSON` have zero consumers; `npcs-1`/`quests-1`/`placements-smithing-1-pre-fish`/`items.JSON/items-testing-integration` are dead; `Definitions.JSON > combat-config.damageFormulas` and `map-waypoint-config.keybindings` are documentation, not behavior; `create_default_save.py` writes stale version "2.0"; `geography-config.json` is referenced (`systems/geography/config.py:141`) **but does not exist** — code defaults apply. Porting any of these as if live wastes effort or, worse, changes behavior.
- **R5 — Duplicate content-file loading into two databases**: `items-alchemy-1`, `items-engineering-1`, `items-smithing-2`, `items-testing-tags` each load into BOTH MaterialDatabase (filtered by category) and EquipmentDatabase — items are dict-shaped in two type systems. The C# `IGameItem` unification must preserve both views or crafting inputs / equippables diverge.
- **R6 — CHUNK_SIZE dual-sourcing**: 16 lives in `core/config.py:24` AND `world_generation.JSON`; the JSON warns "DO NOT CHANGE". Single-source it in C# with a load-time assert.
- **R7 — Sidecar file-boundary APIs**: the `*-generated-*.JSON` naming convention and the five SQLite files in the save dir are the WES↔game contract. Godot must read the generated JSONs and never touch the `.db`s; save-time faction/registry data arrives over IPC with graceful `{}` degrade (already the Python posture, `save_manager.py:78-123`).
- **R8 — Case-sensitive mixed naming**: content uses `camelCase` (`materialId`, `stationTier`), progression/NPC files mix `snake_case` (`npc_id`, `dialogue_lines`); files have mixed `.JSON`/`.json` extensions that matter on case-sensitive filesystems and in the update-loader glob patterns (`update_loader.py:47-67`). Mirror strings exactly; never auto-convert naming policy.

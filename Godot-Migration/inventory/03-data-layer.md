# 03 — Data Layer (data/ models + database singletons)

**Subsystem:** `Game-1-modular/data/` — 13 model files (dataclasses) + 16 database singletons + the Update-N overlay loader.
**Scope of this contract:** everything a C# porter needs to reproduce the typed loaders, their exact normalization behavior, the generated-content overlay semantics, and the consumers that depend on them.
**Ground truth:** code as of branch `crux-foundry`, 2026-07-17. All claims cite `file:line`.

Total: **28 Python files, 7,195 LOC** (measured via `wc -l`). This is the single most port-friendly subsystem in the codebase: **zero pygame imports, zero GameEventBus usage, zero clock/input dependence** anywhere under `data/` (verified by grep — no matches for `pygame|event_bus|publish|subscribe` in `data/`). It is almost pure "read JSON → typed record → dict lookup". The dragons are in the *silent normalizations* documented in §5-adjacent notes below and in the generated-content overlay ordering (§7.1).

---

## 1. File table

| File | LOC | Responsibility | Disposition |
|---|---|---|---|
| `data/__init__.py` | 4 | star-reexport of models + databases | port-to-C# (namespace only) |
| `data/models/__init__.py` | 25 | model re-exports | port-to-C# (namespace only) |
| `data/models/materials.py` | 35 | `MaterialDefinition` dataclass (incl. Phase-4 WES cross-ref fields) | port-to-C# |
| `data/models/equipment.py` | 360 | `EquipmentItem` — durability effectiveness, repair, enchant apply/conflict rules, requirement checks | port-to-C# (pure logic; contains balance rules — see §5) |
| `data/models/titles.py` | 34 | `TitleDefinition` dataclass | port-to-C# |
| `data/models/classes.py` | 46 | `ClassDefinition` + tag-affinity bonus formula (§5) | port-to-C# |
| `data/models/quests.py` | 127 | `QuestObjective` / `QuestRewards` / `QuestDefinition` (v3 schema, `source_origin` canonical/generated flag) | port-to-C# |
| `data/models/npcs.py` | 56 | `NPCDefinition` (v3: personality/locality/faction/speechbank dicts) | port-to-C# |
| `data/models/skills.py` | 143 | `SkillDefinition` tree + `PlayerSkill` (skill EXP curve, cooldown timer — §5) | port-to-C# |
| `data/models/world.py` | 566 | `Position` (already 3D!), `TileType`, `WorldTile`, `ResourceType` string-namespace, `RESOURCE_TIERS`, `ChunkType`, `StationType`, `CraftingStation`, `PlacedEntity` (+crafted-stat application), `DungeonRarity`, `DUNGEON_CONFIG`, `DungeonEntrance` | decompose — pure data ports to C#; the `get_color()` methods and RGB tables are engine-replaces (Godot materials/themes); `PlacedEntity.update_status_effects` couples to status-effect classes (belongs with entities port) |
| `data/models/recipes.py` | 52 | `Recipe`, `PlacementData` (5 discipline-specific placement shapes) | port-to-C# |
| `data/models/resources.py` | 92 | `ResourceNodeDefinition`, `ResourceDrop` — qualitative→numeric maps (§5) | port-to-C# |
| `data/models/unlock_conditions.py` | 481 | Tag-driven unlock condition system: 8 condition classes + `UnlockRequirements` + `ConditionFactory` (JSON→condition, legacy+new formats) | port-to-C# (duck-types against `Character` — needs an `ICharacterQuery` interface in C#) |
| `data/models/skill_unlocks.py` | 184 | `SkillUnlock` + `UnlockCost` (can_afford/pay mutate character) + `UnlockTrigger` | port-to-C# |
| `data/databases/__init__.py` | 27 | database re-exports (11 of 16 — 5 DBs are NOT re-exported here: chunk_template, map_waypoint, quest_archive, visual_config, world_generation) | port-to-C# (namespace) |
| `data/databases/material_db.py` | 325 | `MaterialDatabase` — 7-file sacred load sequence + generated overlay + placeholder fallback | port-to-C# |
| `data/databases/equipment_db.py` | 400 | `EquipmentDatabase` — stores **raw JSON dicts**, materializes `EquipmentItem` on demand; hardcodes weapon/armor/durability formulas (§5) | port-to-C# |
| `data/databases/recipe_db.py` | 256 | `RecipeDatabase` — 5 discipline files, 3 output-shape dialects; also owns inventory-consumption logic (misplaced — see §11 gotchas) | decompose: loader ports as-is; `can_craft/consume_materials/consume_materials_partial` should move to an inventory service in C# |
| `data/databases/placement_db.py` | 220 | `PlacementDatabase` — 5 per-discipline parsers into `PlacementData` | port-to-C# |
| `data/databases/skill_db.py` | 222 | `SkillDatabase` — sacred glob + generated overlay + Update-N re-merge; translation properties delegate to TranslationDatabase | port-to-C# |
| `data/databases/translation_db.py` | 134 | `TranslationDatabase` — mana/cooldown/duration/magnitude enum→number tables + hardcoded fallbacks (§5) | port-to-C# |
| `data/databases/title_db.py` | 263 | `TitleDatabase` — sacred glob + generated overlay + Update-N re-merge; bonus-key camelCase→snake_case map | port-to-C# |
| `data/databases/class_db.py` | 108 | `ClassDatabase` — bonus-key map, placeholder classes | port-to-C# |
| `data/databases/npc_db.py` | 455 | `NPCDatabase` — NPCs **and** quests; v3-preferred/v2-fallback adapters; `get_voice_excerpt` for WES; generated-file merge | port-to-C# (v2 adapter path is candidate dead code if `npcs-3.JSON` is guaranteed — keep for safety, see §11) |
| `data/databases/skill_unlock_db.py` | 137 | `SkillUnlockDatabase` — parses conditions via ConditionFactory | port-to-C# |
| `data/databases/resource_node_db.py` | 359 | `ResourceNodeDatabase` — nodes + category caches + tier map + **icon filename remap table** | port-to-C# (ICON_NAME_MAP becomes Godot asset remap) |
| `data/databases/chunk_template_db.py` | 453 | `ChunkTemplateDatabase` — sacred+generated overlay, geo-dispatch bridge, density/tier-bias allow-lists (§5) | port-to-C# |
| `data/databases/world_generation_db.py` | 440 | `WorldGenerationConfig` — 10 typed config sections, dilutive normalization of distributions (§5) | port-to-C# |
| `data/databases/map_waypoint_db.py` | 326 | `MapWaypointConfig` — map/waypoint/teleport settings + biome color table + UI pixel sizes | decompose: waypoint rules (unlock levels, cooldown, distances) port to C#; colors/window-pixel config are engine-replaces (Godot theme/UI) |
| `data/databases/visual_config_db.py` | 266 | `VisualConfig` — typed accessors over `visual-config.JSON` (damage numbers, telegraphs, particles, shake) | engine-replaces mostly: keep the JSON + a thin typed reader; consumers are the renderer, which Godot replaces. Port the reader (S) so tuning data survives |
| `data/databases/quest_archive_db.py` | 236 | `QuestArchiveDatabase` — in-memory archive of completed quests (WNS/WES retrieval substrate) | **stays-python-sidecar boundary object**: game writes on quest turn-in; consumers are the WNS/WES sidecar. Port the record type + write API to C#, mirror reads over IPC |
| `data/databases/update_loader.py` | 363 | Update-N package auto-discovery (`updates_manifest.json`) + per-type filename-glob routing into 7 databases | port-to-C# |

Dead/near-dead code called out: `MapWaypointConfig`/`VisualConfig` bypass `core.paths.get_resource_path` and hand-roll `Path(__file__)`-relative paths (`map_waypoint_db.py:106`, `visual_config_db.py:43-44`) — an inconsistency, not a feature. `RESOURCE_TIERS` "will be rebuilt after database loads" comment (`world.py:234`) is **false** — see §11. `EquipmentDatabase._create_placeholders` (`equipment_db.py:75-134`) and every `_create_placeholders` are dev-time fallbacks: port them or fail-fast, but decide (recommend fail-fast in Godot + keep placeholder path behind a debug flag; tests rely on them).

---

## 2. Public surface (what other subsystems actually call)

All 16 databases follow the same singleton contract: `X.get_instance()` (+ `reset()` test helper on the newer ones: material `material_db.py:49`, skill `skill_db.py:55`, title `title_db.py:31`, resource_node `resource_node_db.py:76`, chunk_template `chunk_template_db.py:260`, translation `translation_db.py:62`, visual `visual_config_db.py:37`, quest_archive `quest_archive_db.py:148`. **NPCDatabase has no `reset()`** despite `title_db.py:34-36` claiming it does — doc drift).

### Boot loader (the ordering contract)
`core/game_engine.py:135-182` is the canonical boot sequence (must be replicated exactly in Godot startup):
1. `ResourceNodeDatabase.load_from_file("Definitions.JSON/resource-node-1.JSON")` (`game_engine.py:135`) — FIRST, world gen depends on it.
2. `MaterialDatabase` 7-call sacred sequence (`game_engine.py:138-155`), mirrored in `MaterialDatabase.SACRED_LOAD_SEQUENCE` (`material_db.py:16-29`) so `reload()` replays it.
3. `TranslationDatabase.load_from_files()` (`:156`), `RecipeDatabase.load_from_files()` (`:157`), `PlacementDatabase.load_from_files()` (`:158`).
4. `EquipmentDatabase.load_from_file` ×5 (`:161-167`): items-engineering-1, items-smithing-2, items-tools-1, items-alchemy-1, items-testing-tags.
5. `TitleDatabase.load_from_files()` (`:173`), `ClassDatabase.load_from_file("progression/classes-1.JSON")` (`:174`), `SkillDatabase.load_from_files()` (`:175`), `SkillUnlockDatabase.load_from_file("progression/skill-unlocks.JSON")` (`:177`), `NPCDatabase.load_from_files()` (`:178`).
6. `load_all_updates(get_resource_path(""))` (`:181-182`) — Update-N overlay LAST.
`ChunkTemplateDatabase`, `WorldGenerationConfig`, `MapWaypointConfig`, `VisualConfig` self-load lazily on first `get_instance()` (`chunk_template_db.py:253-257`, `world_generation_db.py:146-162`, `map_waypoint_db.py:91`, `visual_config_db.py:30-34`).

### Per-database consumers (representative, verified call sites)
- **MaterialDatabase.get_material** — `entities/components/inventory.py:20,46,120` (max_stack, tooltips), `entities/character.py:2222,2578` (consumable use), `core/game_engine.py:1405,3067,4034` (drop/placement paths), `systems/potion_system.py`, `Crafting-subdisciplines/*` (input validation), `systems/llm_item_generator.py`. Invented-item writes: `game_engine.py:6078-6202` inserts new `MaterialDefinition`s directly into `mat_db.materials`.
- **EquipmentDatabase.is_equipment / create_equipment_from_id** — `entities/components/inventory.py:53,61-64` (stack-vs-equipment split at pickup: THE decision point for whether an item stacks), `entities/character.py:165,345,483` (starting gear, equip flows), `game_engine.py:5355`, invented-equipment insert `game_engine.py:6055-6074`.
- **RecipeDatabase** — `core/interactive_crafting.py` (12 refs), `Crafting-subdisciplines/*.py` (recipe lists per station), `rendering/renderer.py:5463` (recipe book UI), `entities/character.py:690` (invented recipe re-registration), `game_engine.py:5853-5859` (invented recipe insert). `consume_materials`/`can_craft`/`consume_materials_partial` called from crafting completion paths (`recipe_db.py:152-256`).
- **PlacementDatabase.get_placement/has_placement** — `rendering/renderer.py:122,279,422,602,775` (minigame grid display), `game_engine.py:4831-4843,5885-6002` (invented placement registration).
- **SkillDatabase** — `entities/components/skill_manager.py:58,150,219,302,833` (activation, mana, cooldown), `rendering/renderer.py:3251,3331,3397,4494` (skill UI), `systems/quest_system.py:161` (skill rewards), `data/models/skills.py:93` (`PlayerSkill.get_definition` back-reference — models→databases upward import, note for C# layering).
- **TranslationDatabase** — via `SkillDatabase.mana_costs/cooldowns/durations` properties (`skill_db.py:36-46`) and `skill_manager`; single source of truth per §15 trap 5 (`translation_db.py:3-13`).
- **TitleDatabase** — `systems/title_system.py:37` (unlock evaluation), `entities/character.py:331,559`, `rendering/renderer.py:4573,7661`, `systems/quest_system.py:215` (title rewards).
- **ClassDatabase** — `systems/class_system.py:6`, `entities/character.py:305,401`, `rendering/renderer.py:7514`.
- **NPCDatabase** — `game_engine.py:287,1568` (NPC spawn + interaction), `systems/npc_system.py` (builds runtime NPCs from `NPCDefinition`), `systems/quest_system.py` (quest defs), `rendering/renderer.py:4201,4231,4316` (dialogue UI), `world_system/living_world/npc/npc_agent.py:579` (`get_voice_excerpt` — the WES/LLM narrative surface, `npc_db.py:312-379`), `world_system/world_memory/world_memory_system.py:416`.
- **SkillUnlockDatabase** — `systems/skill_unlock_system.py:25` (the only runtime consumer).
- **ResourceNodeDatabase** — `systems/chunk.py:50` + `systems/natural_resource.py:63` (spawn pools, node health/drops), `rendering/renderer.py:1320` (icons via `get_icon_path`), `data/models/world.py:171` (RESOURCE_TIERS attempt).
- **ChunkTemplateDatabase** — `systems/chunk.py:152,337` (chunk dispatch + density-driven resource spawn), `Combat/combat_manager.py:235,296` (enemy spawn-pool weighting), `world_system/content_registry/database_reloader.py:97-110`.
- **WorldGenerationConfig** — `systems/world_system.py:391,825`, `systems/chunk.py:304,459,531`, `systems/biome_generator.py:70`.
- **MapWaypointConfig** — `systems/map_waypoint_system.py:127`, `systems/world_system.py:376`, `rendering/renderer.py:3718`, `game_engine.py:797-798,1347-1348`.
- **VisualConfig** — `rendering/visual_effects.py:47,165,207,272,290,303,392,498` only (pure rendering).
- **QuestArchiveDatabase.archive** — `systems/quest_system.py:504` (quest turn-in). Reads: WNS/WES via WorldQuery.
- **update_loader.load_all_updates** — `game_engine.py:181-182`; `load_skill_updates`/`load_title_updates` re-invoked by `SkillDatabase._remerge_updates` (`skill_db.py:108-123`) and `TitleDatabase._remerge_updates` (`title_db.py:93-108`) after WES reloads.

### Model consumers
`Position` is used everywhere (28+ files — combat, collision `systems/collision_system.py:22`, saves `systems/save_manager.py:12`, animation `animation/combat_particles.py:180`). `PlacedEntity`/`PlacedEntityType` — `systems/turret_system.py:6`, `systems/collision_system.py:27`, `rendering/renderer.py:1077`. `DUNGEON_CONFIG` — `systems/world_system.py:18`. `ChunkType`/`RESOURCE_TIERS` — `systems/chunk.py:11`, `systems/biome_generator.py:28`. `EquipmentItem` — `entities/components/equipment_manager.py:5`, `inventory.py:6`.

---

## 3. Dependency edges

### data/ imports FROM other subsystems (all must be broken or interfaced in C#)
| Import | Site | Why | C# resolution |
|---|---|---|---|
| `core.paths.get_resource_path` | `recipe_db.py:7`, `placement_db.py:7`, `npc_db.py:16`, `chunk_template_db.py:43`, `world_generation_db.py:12`, `translation_db.py:17`, plus lazy imports in `material_db.py:61`, `skill_db.py:70`, `title_db.py:51`, `resource_node_db.py:96` | resource-root resolution (PyInstaller vs source) | Godot `res://` + a `IResourceRoot` abstraction (also handles user:// for generated files — see §7.1 risk) |
| `core.config.Config` | `recipe_db.py:155,180,214` (`DEBUG_INFINITE_RESOURCES`), `data/models/world.py:59` (`WorldTile.get_color` tile colors) | debug bypass; render colors | inject debug flags; colors → Godot materials |
| `core.crafting_tag_processor.SmithingTagProcessor` | `equipment_db.py:249` (tag→slot inference) | slot mapping from metadata tags | port tag processor first or extract `get_equipment_slot` |
| `core.crafting_tag_processor.EnchantingTagProcessor` | `data/models/equipment.py:233` (enchant applicability) | tag-based enchant rules | same |
| `Combat.enemy.EnemyDatabase` | `update_loader.py:132` (`load_enemy_updates`) | Update-N hostiles | port EnemyDatabase (Combat contract) before update_loader completes |
| `entities.character.Character` | `unlock_conditions.py:12` (TYPE_CHECKING only); runtime duck-typing on `character.leveling.level`, `character.stats.*`, `character.activities`, `character.stat_tracker`, `character.titles`, `character.skills.known_skills`, `character.quests`, `character.class_system` (`unlock_conditions.py:54,74-81,111,141-171,194,219,244,268-270`) | condition evaluation | define `ICharacterQuery` interface in the pure-logic assembly |
| `data.databases.skill_db` (upward from models) | `data/models/skills.py:92-94` (`PlayerSkill.get_definition`) | convenience back-ref | invert: pass `SkillDatabase` in, or a static service locator in C# |
| `data.databases.resource_node_db` (upward from models) | `data/models/world.py:170` (`_build_resource_tiers`) | tier table attempt | see §11 — resolve the RESOURCE_TIERS lifecycle properly in C# |
| `world_system/config/geo_chunk_dispatch.json` | `chunk_template_db.py:245,359-383` | geo→chunkType bridge file lives under the sidecar's config dir | ship this JSON with game content; sidecar keeps its own copy or the file stays shared |

### Who imports data/ (inbound)
Practically everything: `core/` (game_engine 114 refs, interactive_crafting, difficulty_calculator, testing), `entities/` (character 25 refs, inventory, equipment_manager, skill_manager), `Combat/combat_manager.py` (7), `systems/` (world_system, chunk, npc_system, quest_system, title_system, class_system, skill_unlock_system, map_waypoint_system, save_manager, natural_resource, turret_system, collision_system, dungeon, potion_system, biome_generator, llm_item_generator, crafting_classifier), `rendering/renderer.py` (58 refs), `Crafting-subdisciplines/*`, `world_system/` (content_registry xref_rules + database_reloader, world_memory entity_registry + world_memory_system, living_world npc_agent, wes request_layer). **Conclusion: this layer must be the FIRST thing ported** — it is the root of the dependency DAG.

---

## 4. Engine coupling (pygame/rendering/input/clock touchpoints)

There are **no pygame imports** in `data/`. Coupling is indirect — presentation data baked into models/configs:

| Touchpoint | Site | Redesign |
|---|---|---|
| `WorldTile.get_color()` → `Config.COLOR_*` RGB | `world.py:56-65` | delete; Godot tile materials keyed by `TileType` |
| `CraftingStation.get_color()` RGB table | `world.py:303-311` | Godot scene/material per `StationType` |
| `PlacedEntity.get_color()` RGB table | `world.py:436-447` | Godot scene per `PlacedEntityType` |
| `DungeonEntrance.get_rarity_color()` RGB table | `world.py:557-566` | Godot material/shader per rarity |
| `NPCDefinition.sprite_color: Tuple[int,int,int]` | `npcs.py:51`, parsed `npc_db.py:58` | keep field (content JSON has it) but map to Godot modulate; do not drop — v3 JSON carries it |
| `icon_path` auto-generation (`"materials/{id}.png"`, `"weapons/{id}.png"`, `"skills/{id}.png"`, `"titles/{id}.png"`) | `material_db.py:140-152,221-224,283-295`, `equipment_db.py:321-337`, `skill_db.py:167-170`, `title_db.py:133-136` | preserve the path-derivation rules verbatim; remap prefix to `res://assets/...`. `ResourceNodeDatabase.ICON_NAME_MAP` (`resource_node_db.py:25-57`) is a **hand-maintained id→PNG-filename alias table** that must survive |
| `MapWaypointConfig.ui` pixel sizes, `biome_colors`, marker shapes | `map_waypoint_db.py:56-64,149-227,254-267` | UI portion → Godot Control themes; waypoint *rules* (`WaypointSystemConfig`, `map_waypoint_db.py:38-53`) are game logic and port as-is |
| `VisualConfig` — every accessor (damage number physics, telegraph colors, particle counts, shake decay) | `visual_config_db.py:66-261` | consumed only by `rendering/visual_effects.py`; carry the JSON forward as the tuning source for Godot VFX; port the typed reader thinly |
| `PlayerSkill.update_cooldown(dt)` / `PlacedEntity.update_status_effects(dt)` | `skills.py:136-139`, `world.py:466-495` | dt-driven timers — plain float seconds, engine-agnostic; feed Godot `_process` delta |
| `print()` logging with emoji throughout loaders | e.g. `material_db.py:177`, `equipment_db.py:24`, `models/equipment.py:304-308` | replace with proper logging; note `cp1252` console crashes were a real past bug class in this repo |

No wall-clock reads, no threading, no file *writes* in data/ (generated files are written by `world_system/content_registry`, data/ only reads them).

---

## 5. Constants & formulas (exact values, from code)

**Durability effectiveness (sacred: floor 50%, never breaks)** — `data/models/equipment.py:49-55`:
`durability<=0 → 0.5`; `dur_pct >= 0.5 → 1.0`; else `1.0 - (0.5 - dur_pct) * 0.5` (linear 1.0→0.75 as pct goes 0.5→0... note: at pct=0 formula gives 0.75, but the `<=0` branch overrides to 0.5 — the effectiveness curve is **discontinuous at 0**; port exactly).

**Crafted/enchant damage & defense multipliers** — `equipment.py:109-157`: `damage_mult = 1 + bonuses.damage_multiplier + Σ ench(damage_multiplier)`; tools additionally `damage_mult *= efficiency` (`:126-127`); result `int()`-truncated per bound. Defense analog `:137-157`.

**Enchant family/tier rules** — `equipment.py:261-301`: exact-duplicate reject; family/tier parsed from `id.rsplit('_',1)` (numeric suffix = tier, else tier 1); higher-tier same-family already present → reject; on apply, removes any enchant listed in `effect.conflictsWith` (bidirectional check `:286-290`).

**Requirement stat aliasing** — `equipment.py:162-177`: `str/def/vit/lck/agi/int` → full names; **`dex`/`dexterity` → `agility`** (legacy alias).

**Class skill-affinity** — `classes.py:33-46`: `min(matching_tags × 0.05, 0.20)` — the "class max 1.2×" sacred constant lives HERE, in the data layer.

**Skill EXP curve (player skills, NOT character levels)** — `skills.py:96-101`: to next level = `1000 × 2^(level-1)`, max level 10; level-scaling bonus `0.1 × (level-1)` (`:128-130`).

**Weapon damage formula (hardcoded mirror of stats-calculations.JSON)** — `equipment_db.py:136-167`: `globalBase=10 × tierMult{1,2,4,8} × categoryMult(1.0) × typeMult{sword 1.0, axe 1.1, spear 1.05, mace 1.15, dagger 0.8, bow 1.0, staff 0.9, shield 1.0} × subtypeMult{shortsword 0.9, longsword 1.0, greatsword 1.4, dagger 1.0, spear 1.0, pike 1.2, halberd 1.4, mace 1.0, warhammer 1.3, maul 1.5} × statMultipliers.damage`, then variance band `int(base×0.85)..int(base×1.15)`. **The comment claims it comes from stats-calculations.JSON but the DB never reads that file** — the numbers are hardcoded in Python (the JSON is read elsewhere by `entities/components/stats.py:45` and the balance stub). Port the hardcoded values verbatim; do not "fix" by reading JSON without diffing values first.

**Armor defense** — `equipment_db.py:169-187`: `10 × tierMult{1,2,4,8} × slotMult{helmet 0.8, chestplate 1.5, leggings 1.2, boots 0.7, gauntlets 0.6} × statMultipliers.defense`, int-truncated.

**Durability max** — `equipment_db.py:189-209`: `250 × tierMult{1,2,4,8} × statMultipliers.durability` → T1=250/T2=500/T3=1000/T4=2000; explicit `stats.durability` (scalar or `[cur,max]` list) overrides (`:311-319`).

**Tier multipliers T1..T4 = 1/2/4/8** appear three times in `equipment_db.py` (`:141,174,202`) — the sacred table's residence in this subsystem.

**Hand-type from tags** — `equipment_db.py:339-347`: `'1H'`/`'2H'`/`'versatile'` tag → hand_type, else `"default"`.

**Resource drop qualitative maps** — `resources.py:14-34`: quantity `few(1,2) several(2,4) many(3,5) abundant(4,8)`, default `(1,3)`; chance `guaranteed 1.0, high 0.8, moderate 0.5, low 0.25, rare 0.1, improbable 0.05`, default 1.0. Respawn `resources.py:56-76`: `quick 30, fast 30, normal 60, slow 120, very_slow 300` seconds, default 60, `None` = no respawn (the `"quick"` synonym is a deliberate code-side fix for sacred JSON — G18.4).

**Translation fallbacks (used iff JSON missing)** — `translation_db.py:26-42`: mana `{low 30, moderate 60, high 100, extreme 150}`; cooldown `{short 120, moderate 300, long 600, extreme 1200}` s; duration `{instant 0, brief 15, moderate 30, long 60, extended 120}` s; magnitude table for 10 effect types (empower minor 0.5 … transcend extreme 4). `SkillDatabase.get_mana_cost` default 60 (`skill_db.py:211`), `get_cooldown_seconds` default 300 (`:218`), duration default 0 (`:222`).

**Chunk density/tier-bias allow-lists** — `chunk_template_db.py:52-65`: `very_low 0.5, low 0.75, moderate 1.0, high 2.0, very_high 3.0`; tier bias ranks `low 1, mid 2, high 3, legendary 4`. Unknown density → 1.0 (`:80`), unknown bias → 1 (`:84`); enemy tier clamped 1..4 (`:169`).

**PlacedEntity crafted stats** — `world.py:384-434`: power `dmg × (1+power/100)` (also scales `effect_params.baseDamage`); durability `lifetime × (1+dur/100)`; efficiency `atkspeed × (1+min(eff,900)/100)`. Barrier HP by tier `{1:50, 2:100, 3:200, 4:400}` (`world.py:374-376`).

**DUNGEON_CONFIG fallback** — `world.py:510-547`: spawn weights common 50/uncommon 25/rare 15/epic 7/legendary 2/unique 1; mob counts 20/30/40/50/50/50; per-rarity tier weight tables (JSON `dungeon-config-1.JSON` takes priority at the consumer).

**WorldGenerationConfig defaults** — `world_generation_db.py:15-129`: chunk load_radius 4, chunk_size 16; biome water .10/forest .50/cave .40 (validated to sum 1.0, else proportionally normalized `:227-232`); danger-zone distributions safe (1,0,0)/transition (.4,.5,.1)/outer (.2,.5,.3) with **dilutive normalization** (`:344-368` — e.g. designer writes 6/3/1, code normalizes to .6/.3/.1: a silent normalization the C# port must keep); resource spawn peaceful (3-6, T1-2)/dangerous (5-8, T2-3)/rare (6-10, T3-4); water subtype chances .45/.45/.10 also dilutively normalized (`:296-300`); dungeon spawn chance 0.083/chunk, min distance 2.

**Waypoint rules** — `map_waypoint_db.py:38-53`: unlock levels [5,10,15,20,25,30], max 7 waypoints, 30 s teleport cooldown, min 32 tiles between waypoints; `get_max_waypoints_for_level` (`:291-311`).

**Difficulty tier points, EXP curve (200×1.75^n), STR/LCK/etc. scaling and crit** are NOT in this subsystem — they live in `core/difficulty_calculator.py`, `entities/components/leveling.py`/`stats.py`, and `Combat/combat_manager.py:24` (`_LCK_CRIT_PER_POINT = env CRUX_LCK_CRIT_PER_POINT, default 0.12`). Listed here to delimit ownership.

---

## 6. Event topics

**None.** `data/` neither publishes nor subscribes to GameEventBus (grep verified: zero matches for `event_bus|publish|subscribe` under `data/`). The `RECIPE_DISCOVERED` publish adjacent to invented-recipe registration happens in `core/game_engine.py:5800-5806`, outside this subsystem. The C# data assembly can therefore be a **zero-dependency pure library**.

---

## 7. Content JSON consumed (exact paths → loader)

All paths relative to `Game-1-modular/` via `core.paths.get_resource_path` unless noted.

| File | Loader (method) | Notes |
|---|---|---|
| `items.JSON/items-materials-1.JSON` | `MaterialDatabase.load_from_file` (`material_db.py:132`) | key `materials`; ids from `materialId` |
| `items.JSON/items-refining-1.JSON` | `MaterialDatabase.load_refining_items` (`:208`) | sections `basic_ingots`/`alloys`/`wood_planks`; **ids from `itemId`** (dialect!); default max_stack **256** (`:234`) vs 99 elsewhere; first-wins (no overwrite `:240`) |
| `items.JSON/items-alchemy-1.JSON` | `MaterialDatabase.load_stackable_items(categories=['consumable'])` + `EquipmentDatabase.load_from_file` | stackable path requires `flags.stackable||flags.placeable` (`:275`); equipment path takes only `category=='equipment'` (`equipment_db.py:46-47`) |
| `items.JSON/items-engineering-1.JSON` | `MaterialDatabase.load_stackable_items(['device'])` + `EquipmentDatabase.load_from_file` | |
| `items.JSON/items-testing-tags.JSON` | `MaterialDatabase.load_stackable_items(['device','weapon'])` + `EquipmentDatabase.load_from_file` | test content loaded in prod boot |
| `items.JSON/items-smithing-2.JSON` | `MaterialDatabase.load_stackable_items(['station'])` + `EquipmentDatabase.load_from_file` | stations stack; equipment doesn't |
| `items.JSON/items-tools-1.JSON` | `EquipmentDatabase.load_from_file` | |
| `Definitions.JSON/crafting-stations-1.JSON` | `MaterialDatabase.load_stackable_items(['station'])` | legacy backup |
| `recipes.JSON/recipes-smithing-3.json` (lowercase .json!), `recipes-alchemy-1.JSON`, `recipes-refining-1.JSON`, `recipes-engineering-1.JSON`, `recipes-adornments-1.json` | `RecipeDatabase.load_from_files` (`recipe_db.py:26-42`) | three output dialects: `enchantmentId` (adornments), `outputs[]` (refining, first entry only, `materialId` or `itemId`, tier key `stationTierRequired` fallback `stationTier`), `outputId` (`recipe_db.py:50-72`); empty output_id rows skipped `:74-77` |
| `placements.JSON/placements-smithing-1.json` (lowercase — case-sensitivity fix noted `placement_db.py:28-32`), `placements-refining-1.JSON`, `placements-alchemy-1.JSON`, `placements-engineering-1.JSON`, `placements-adornments-1.JSON` | `PlacementDatabase.load_from_files` (`placement_db.py:24-49`) | 5 discipline-specific shapes into one `PlacementData` |
| `Definitions.JSON/skills-translation-table.JSON` | `TranslationDatabase._load_translation_table` (`translation_db.py:71-88`) | keys `durationTranslations.*.seconds`, `manaCostTranslations.*.cost`, `cooldownTranslations.*.seconds` |
| `Skills/skills-base-effects-1.JSON` | `TranslationDatabase._load_base_effects` (`:90-105`) | `BASE_EFFECT_TYPES.*.magnitudeValues` |
| `Skills/skills-skills-*.JSON` (sacred glob) + `Skills/skills-generated-*.JSON` | `SkillDatabase.load_from_files` (`skill_db.py:59-87`) | generated overlays sacred, last-writer-wins |
| `progression/titles-*.JSON` + `progression/titles-generated-*.JSON` | `TitleDatabase.load_from_files` (`title_db.py:39-70`) | same overlay pattern |
| `progression/classes-1.JSON` | `ClassDatabase.load_from_file` (`class_db.py:21`) | |
| `progression/skill-unlocks.JSON` | `SkillUnlockDatabase.load_from_file` (`skill_unlock_db.py:30`) | key `skillUnlocks` |
| `progression/npcs-3.JSON` (v3 preferred) / `progression/npcs-enhanced.JSON` (v2 fallback); `progression/quests-3.JSON` / `quests-enhanced.JSON` | `NPCDatabase.load_from_files` (`npc_db.py:254-310`) | v1 removed; `progression/npcs-generated-*.JSON` + `quests-generated-*.JSON` merged by `reload()` only (`:410-455`) — **not at cold boot** (asymmetry vs skills/titles; see §11) |
| `Definitions.JSON/resource-node-1.JSON` (boot) / glob `[rR]esource-node-*.JSON` + `[rR]esource-node-generated-*.JSON` (reload) | `ResourceNodeDatabase.load_from_file` / `load_from_files` (`resource_node_db.py:80-147,149`) | key `nodes` |
| `Definitions.JSON/Chunk-templates-*.JSON` + `Chunk-templates-generated-*.JSON`; `world_system/config/geo_chunk_dispatch.json` | `ChunkTemplateDatabase.load_from_files` (`chunk_template_db.py:270-395`) | wrapper key `templates` (tolerates `chunkTemplates`); `geoTypes` auto-register with sacred-wins `setdefault` (`:385-395`) |
| `Definitions.JSON/world_generation.JSON` | `WorldGenerationConfig._load_config` (`world_generation_db.py:185-206`) | |
| `Definitions.JSON/map-waypoint-config.JSON` | `MapWaypointConfig._load_config` (`map_waypoint_db.py:104-132`) | |
| `Definitions.JSON/visual-config.JSON` | `VisualConfig._load` (`visual_config_db.py:40-52`) | |
| `updates_manifest.json` (project root) + `Update-N/*` globs | `update_loader.get_installed_updates` (`update_loader.py:26-38`) + `scan_update_directory` (`:41-73`) | manifest lists `installed_updates: ["Update-1","Update-2"]` (verified on disk); per-type filename globs: equipment `*items*/*weapons*/*armor*/*tools*`, skills `*skills*`, enemies `*hostiles*/*enemies*`, materials `*materials*/*consumables*/*devices*`, titles `*titles*`, skill_unlocks `*skill-unlocks*/*skill_unlocks*`, recipes `*recipes*` with **station type inferred from filename substring, defaulting to smithing** (`update_loader.py:270-284`) |

### 7.1 Generated/invented content merge — the three channels
1. **WES Content Registry (file-based)**: `world_system/content_registry` writes `*-generated-*.JSON` siblings, then `database_reloader.reload_for_tools` calls `reload()` on the mapped singleton (`database_reloader.py:40-111`: materials, hostiles, nodes, skills, titles, npcs, quests, chunks). Each `reload()` snapshots old state and restores on any failure ("stale-but-intact", e.g. `material_db.py:111-130`, `npc_db.py:381-408`). `SkillDatabase.reload` and `TitleDatabase.reload` additionally re-merge Update-N afterwards so a WES commit can't silently delete Update-2 fishing content (`skill_db.py:89-123`, `title_db.py:72-108`).
2. **LLM invented items (in-memory insert)**: `game_engine.py:5810-5876` builds a `Recipe` with `recipe_id = "invented_{item_id}"`, inserts directly into `RecipeDatabase.recipes` + `recipes_by_station`; `_register_invented_item_with_database` (`:6047-6202`) routes by discipline — smithing/adornments → `EquipmentDatabase.items[item_id] = raw dict`, refining/alchemy/engineering/unknown → `MaterialDatabase.materials[item_id] = MaterialDefinition`; placements → `PlacementDatabase.placements` (`:5943-6002`). **These in-memory inserts are lost by any `reload()`** unless re-registered — persistence is via the save file, restored by `register_all_invented_recipes` (`game_engine.py:6206+`) on load.
3. **Update-N packages (file-based, boot + re-merge)**: overlay after core load; ids overwrite (skills/titles/equipment last-writer-wins; materials first-wins per `material_db.py:317` — **asymmetry!** an Update-N material with a duplicate id will NOT override core, while an Update-N skill will).

---

## 8. Persistent state

The data layer holds definitions, not save state, but three contracts touch persistence:

- **Invented recipes**: `systems/save_manager.py:195,200-235` serializes `character.invented_recipes` list — keys per record: `timestamp, discipline, item_id, item_name, item_data, from_cache, recipe_inputs, station_tier, narrative, placement_data, icon_path`. On load these re-register into Recipe/Equipment/Material/Placement databases (`game_engine.py:6206+`). The C# save schema must preserve these keys verbatim to reload legacy saves.
- **Equipment instances**: `save_manager.py:248-329` persists `item_id` + `durability_current` (+ enchantments) per slot; on load, `EquipmentDatabase.create_equipment_from_id` re-materializes and durability is overwritten. Meaning: **base stats are re-derived from JSON at load, not stored** — a definition change retroactively changes existing items. Preserve this.
- **QuestArchiveDatabase** is explicitly **in-memory only, lost on restart** (`quest_archive_db.py:128-131` "Stateless across process restarts in v4"). If Godot sessions are expected to persist archives, that is a design gap to close (or the sidecar owns it).
- Generated `*-generated-*.JSON` files ARE the persistence for WES content — they live in the content tree and are re-read at boot by skills/titles/materials/nodes/chunks (`load_from_files` globs) but NPCs/quests only via `reload()` (see §11 risk #4).

---

## 9. 3D notes (2D → 3D)

- **`Position` is already 3D** — `world.py:9-36` has `x, y, z=0.0` and true 3D Euclidean `distance_to` (`:16-17`). The game currently uses x/y as ground plane with z≈0. For Godot 3D, map game `(x, y)` → world `(X, Z)` and game `z` → height `Y` (same convention the paused Unity plan chose: `(x,0,z)`). `snap_to_grid`/`to_key` floor all three axes (`:19-33`) — tile keys are strings `"x,y,z"`; keep the floor()-for-negatives semantics (a `-0.5 → -1` correctness point called out in code).
- `NPCDefinition.position` parsed from JSON with x/y/z already present (`npc_db.py:38-39`) — content is 3D-ready.
- `interaction_radius` (npcs), `PlacedEntity.range`, waypoint `min_distance_between_waypoints` are scalar distances — decide once whether interaction/turret checks are 2D (ground-plane) or 3D sphere; recommend ground-plane (XZ) distance to preserve balance, since all content was tuned with z=0.
- `RESOURCE_TIERS`, chunk types, density weights are geometry-independent — no change.
- Colors/markers/zoom in MapWaypointConfig assume a top-down 2D map render; the Godot 3D minimap/worldmap replaces the projection but should reuse `biome_colors` as the legend.
- `PlacedEntity`/`CraftingStation` occupy single tiles via `Position.to_key()`; in 3D these become grid cells on the terrain surface — keep integer tile keys, derive height from terrain.

---

## 10. Godot mapping (proposed)

**Pure-logic assembly `Game1.Data` (netstandard/net8, zero Godot references, dotnet-testable):**
- `Game1.Data.Models`: `MaterialDefinition`, `EquipmentItem`, `SkillDefinition`+`PlayerSkill`, `Recipe`, `PlacementData`, `TitleDefinition`, `ClassDefinition`, `QuestDefinition` et al., `NpcDefinition`, `ResourceNodeDefinition`, `ChunkTemplate`, `GamePosition` (struct; conversions to/from `Vector3` live in glue), `PlacedEntity` (logic part), condition system (`IUnlockCondition`, `UnlockRequirements`, `ConditionFactory`) against an `ICharacterQuery` interface.
- `Game1.Data.Databases`: one class per DB, same method names (`GetMaterial`, `CreateEquipmentFromId`, `GetRecipesForStation`, `GetForGeoType`, …). Implement as **plain singletons or a DI `GameDatabases` root object** — NOT Godot autoloads — so `dotnet test` can boot them headless exactly like the Python tests do (`reset()` maps to a `Reset()` for test isolation).
- `Game1.Data.Loading`: `IResourceRoot` (maps `"items.JSON/..."` → `res://` for sacred, `user://generated/` for WES-generated files — see risk #2), `BootLoader` encoding the §2 boot ordering, `UpdateLoader` (manifest + globs), `GeneratedOverlayLoader` (glob + last-writer-wins), `DatabaseReloadService` (the C# side of the sidecar's commit→reload handshake, replacing `world_system/content_registry/database_reloader.py`; triggered over IPC).
- JSON via `System.Text.Json` with `JsonDocument`/dictionaries where the Python keeps raw dicts (EquipmentDatabase stores raw JSON — mirror that: store `JsonElement`/DTO and materialize on demand), tolerant readers (missing key → default) to reproduce `.get(k, default)` semantics everywhere.

**Engine glue (Godot project):**
- `DataAutoload` (single autoload) that constructs `GameDatabases`, runs `BootLoader` at startup, and exposes it to scenes.
- Presentation tables (`get_color` maps, `biome_colors`, `VisualConfig`, marker shapes, `MapWaypointConfig.ui`) → Godot `Theme`/`Resource` assets keyed by the same enum/string ids; a small `VisualConfigBridge` reads `visual-config.JSON` so designers keep one tuning file.
- Icon paths: keep the derivation rules + `ICON_NAME_MAP` in `Game1.Data`, resolve to `res://assets/...` in glue.
- `QuestArchiveDatabase`: write API in C#; a mirror pushed to the Python sidecar over IPC (it is a WNS/WES read substrate — `quest_archive_db.py:10-15`).
- Minigame placements (`PlacementData`) feed the 2D Control-node overlay panels directly — no transformation needed.

---

## 11. Port complexity, ordering, risks

**Complexity: L overall.** Per-piece: models S-M (mostly mechanical; `unlock_conditions.py` M due to duck-typing and dual JSON formats); material/equipment/recipe/npc DBs M (dialect handling); chunk_template/world_gen M; update_loader + generated-overlay semantics M; visual/map configs S. The volume of *silent* normalization (aliases, defaults, first-wins vs last-wins, dialects) is what makes this L in verification effort rather than typing effort.

**Ordering constraints:**
1. `IResourceRoot`/paths + JSON tolerant-reader utilities first (everything uses them).
2. Models (no deps except `ICharacterQuery` stub) → then databases → then `UpdateLoader` (needs EnemyDatabase from the Combat port for `load_enemy_updates`; can stub it initially) → then `DatabaseReloadService` (needs sidecar IPC, can come last).
3. `crafting_tag_processor` (`SmithingTagProcessor.get_equipment_slot`, `EnchantingTagProcessor.can_apply_to_item`) must be ported before `EquipmentDatabase.create_equipment_from_id` and `EquipmentItem.can_apply_enchantment` are complete — it's a `core/` dependency that leaks into this subsystem.
4. Everything downstream (entities, combat, crafting, systems, world) depends on this assembly — port it FIRST and lock it with golden-master tests: boot both runtimes over the same content tree and diff every materialized item/recipe/skill/title (the Python side can dump JSON snapshots).

**Top risks / gotchas (each verified in code):**
1. **Hardcoded formula mirrors masquerading as JSON-driven** — `equipment_db.py:136-209` docstrings say "based on stats-calculations.JSON formula" but the DB never opens that file; values are Python literals. A porter who "helpfully" reads the JSON may get different numbers. Port literals; add a startup assert comparing them to the JSON.
2. **Generated-file write location vs `res://`** — Python writes `*-generated-*.JSON` siblings *into the content tree* and loaders glob the same directory (`material_db.py:31-32,87-99`, `title_db.py:16-18`, `chunk_template_db.py:242-244`). In an exported Godot build `res://` is read-only — the C# loaders must glob TWO roots (packed sacred + `user://` generated), which changes `IResourceRoot` semantics for every database with a GENERATED_GLOB.
3. **First-wins vs last-wins is per-database** — materials never overwrite (`material_db.py:240,317`: `if id not in self.materials`), but skills/titles/chunk-templates/npcs/quests/equipment DO overwrite (last-writer-wins, e.g. `skill_db.py:64-66`, `equipment_db.py:47`). Getting one of these backwards silently changes content resolution; encode as an explicit per-database merge policy enum with tests.
4. **NPC/quest generated files invisible at cold boot** — `NPCDatabase.load_from_files` (`npc_db.py:254-310`) does NOT merge `npcs-generated-*` / `quests-generated-*`; only `reload()` does (`:410-455`). Skills/titles/materials/nodes/chunks DO load generated at boot (fixed 2026-06-10 per `game_engine.py:169-172`). This is an existing asymmetry (probably a latent bug): WES-generated NPCs vanish on restart until the next registry reload. Decide deliberately in C# — recommend merging at boot and noting the behavior change.
5. **`RESOURCE_TIERS` stale-comment trap** — `world.py:234-235` claims it's "rebuilt after database loads"; nothing ever rebuilds it (grep: no reassignment anywhere). Since `data.models` imports before any DB load, the JSON-driven branch of `_build_resource_tiers` (`world.py:166-181`) is effectively dead and consumers (`systems/chunk.py:516,520`) always use the hardcoded fallback table (`world.py:184-231`). In C#, either freeze the fallback table as canonical (behavior-preserving) or make it a live view over ResourceNodeDatabase (behavior-changing if JSON ever diverges — currently they match by design).
6. **Filename case + dialect landmines** — `recipes-smithing-3.json` and `placements-smithing-1.json` are lowercase `.json` while siblings are `.JSON` (`placement_db.py:28-33` documents a real Linux bug); refining items use `itemId` not `materialId` (`material_db.py:218`) with max_stack default 256 vs 99; recipes have 3 output dialects incl. `stationTierRequired` (`recipe_db.py:50-72`); quest/NPC v2 fallback uses camelCase keys (`npc_db.py:143-184`); update recipes infer station type from filename with silent smithing default (`update_loader.py:270-284`). Every one of these must be reproduced bit-for-bit since content JSON is reused verbatim.
7. **In-memory invented content vs reload()** — a WES-triggered `MaterialDatabase.reload()` rebuilds from disk and will drop LLM-invented in-memory materials/equipment/recipes registered by `game_engine.py:5810-6202` until a save/load cycle re-registers them. If the Godot version keeps both channels, the reload path must re-apply the invented-content registry (or invented items must be written to a generated file). This hidden interaction exists today; don't carry it forward blindly.
8. **`is_equipment` drives stacking** — `inventory.py:53-64` decides stack-vs-unique purely by presence in `EquipmentDatabase.items`; any load-order or category-filter deviation (only `category=='equipment'` rows enter, `equipment_db.py:46-47`) silently turns swords into stackables or potions into uniques. Golden-master the full id sets of both databases after boot.

---

*Prepared as the porting contract for the data layer. Companion inventories: 01 (core), 02 (entities), 04 (combat), 05 (crafting), 06 (systems/world), 07 (rendering/animation parity checklist), 08 (world_system sidecar IPC).*

# 02 — core/ Pure Logic — Porting Contract (Godot 4 / .NET)

**Scope**: everything in `Game-1-modular/core/` EXCEPT `game_engine.py` (covered by a separate inventory).
**Verified against code**: 2026-07-17, branch `crux-foundry`. All file:line citations are from the live tree.
**In-scope LOC**: ~8,150 across 23 Python files (raw file line counts, incl. comments/blank).

The crown jewels here are the **tag pipeline** (`tag_system → tag_parser → geometry → effect_executor`) — the combat backbone — and the **difficulty/reward calculators** — the crafting economy. Both are almost pure functions over dicts/dataclasses and port to a pure C# assembly nearly 1:1.

---

## 1. File Table

| File | ~LOC | Responsibility | Disposition |
|---|---|---|---|
| `core/tag_system.py` | 193 | `TagRegistry` singleton: loads `Definitions.JSON/tag-definitions.JSON` (95 tags, 11 categories), alias resolution, category queries, geometry-conflict priority, mutual exclusion, default params | **port-to-C#** (pure logic assembly) |
| `core/tag_parser.py` | 192 | `TagParser`: tags+params → `EffectConfig` (categorize, resolve geometry conflict, infer context, merge defaults, apply synergies, warn on exclusions) | **port-to-C#** |
| `core/effect_context.py` | 57 | `EffectConfig` / `EffectContext` dataclasses — the unified effect representation | **port-to-C#** (records) |
| `core/effect_executor.py` | 644 | `EffectExecutor`: full effect application — damage (incl. per-target enemy defense), healing, status application, special-mechanic if/elif dispatch (see §2.4) | **port-to-C#** (replace duck-typing with interfaces) |
| `core/geometry/target_finder.py` | 436 | `TargetFinder`: single/chain/cone/circle-aoe/beam-line target selection with context filtering and enemy-perspective context flip | **port-to-C#** |
| `core/geometry/math_utils.py` | 113 | 2D vector math: distance, normalize, dot, angle, cone/circle tests, facing estimation | **port-to-C#** (largely replaced by `System.Numerics`/Godot `Vector3`, but keep as thin wrappers to preserve exact semantics) |
| `core/geometry/__init__.py` | 7 | Re-exports | n/a |
| `core/difficulty_calculator.py` | 809 | Material-points difficulty for all 5 minigames + per-discipline parameter interpolation + legacy tier fallbacks | **port-to-C#** |
| `core/reward_calculator.py` | 629 | Performance→reward for all 5 minigames: quality tiers, bonus %, failure penalty, first-try bonus | **port-to-C#** |
| `core/crafting_tag_processor.py` | 526 | 5 static tag processors (Smithing slot assignment/tag inheritance, Engineering role/behavior, Enchanting applicability rules, Alchemy potion-vs-transmutation, Refining probabilistic bonuses + rarity upgrade) | **port-to-C#** |
| `core/interactive_crafting.py` | 1,180 | Placement/recipe-matching state machines for 5 disciplines (grid, hub-spoke, sequential, slot-type, shape/vertex) + material borrow/return against inventory | **port-to-C#** as `*Session` classes (they are logic, not UI, despite the `*UI` names); Godot Control nodes render them |
| `core/config.py` | 233 | `Config` static class: world/gameplay constants + screen/UI-scale layout math + colors + debug toggles | **decompose**: gameplay constants → C# `GameConfig`; screen/UI-scale/layout half → **engine-replaces** (Godot anchors/stretch); pygame init → drop |
| `core/camera.py` | 33 | 2D camera follow + world↔screen (tile*32 px) + shake offset | **engine-replaces** (Godot `Camera3D`); keep the *feature list* (follow, shake) |
| `core/minigame_effects.py` | 1,523 | Pygame particle systems, 5 themed procedural minigame backgrounds, screen shake, animated progress bar/button, metadata overlay | **engine-replaces** (Godot `GpuParticles2D`/tweens/Control theme). Port only the **data**: color palettes, easing choices, `MinigameMetadataOverlay` content contract (§10) |
| `core/notifications.py` | 19 | `Notification` dataclass with lifetime countdown | **port-to-C#** (trivial record) |
| `core/paths.py` | 160 | `PathManager` singleton: dev vs PyInstaller-bundle resource/save paths, per-OS user-data dir, faction.db path | **engine-replaces** (`res://` / `user://`); keep API shape (`GetResourcePath`, `GetSavePath`) as a thin static class |
| `core/crash_handler.py` | 62 | Timestamped crash-report writer, never raises | **port-to-C#** (unhandled-exception hook writing to `user://crash_reports/`) |
| `core/tag_debug.py` | 277 | `TagDebugger`: leveled tag-system logger with specialized log methods; cp1252 emoji guard | **port-to-C#** as an `ITagLogger` interface + default console impl (executor/finder call ~20 of its methods — the call sites must compile) |
| `core/debug_display.py` | 220 | On-screen debug message queue with abbreviation/dedup (`debug_print`) | **port-to-C#** (logic) + Godot overlay for display; low priority |
| `core/tag_system_debugger.py` | 320 | Class-level tag *flow* validator (json→db→combat→damage stages) | **drop-dead-code** for the port — only consumed by `tests/test_tag_system.py:18` and docs; no game code calls it. Recreate as test-assembly helper only if the tag-flow tests are ported |
| `core/testing.py` | 211 | `CraftingSystemTester` — in-game F10 self-test of DBs/recipes/renderer method names | **drop** (superseded by `dotnet test`); its 6 checks become unit tests |
| `core/testing_difficulty_distribution.py` | 301 | CLI analysis of difficulty distribution across all recipe JSONs | **stays-python-sidecar** (designer tool; reads content JSON directly, no game deps) or optional dotnet console tool later |
| `core/__init__.py` | 11 | Exports `Config`, `Notification`, `Camera` | n/a |
| `core/README.md` | 174 | **STALE** module doc — claims 6 files and a 2,733-line game_engine (actual: 22 files, game_engine ≈10.3k non-blank lines). Do not trust it | drop / rewrite |
| `core/game_engine.py` | ~12,000 | Main loop / input / orchestration | **out of scope here** — separate inventory |

---

## 2. Public Surface (what other subsystems actually call)

### 2.1 Tag pipeline
- `get_effect_executor()` / `EffectExecutor.execute_effect(source, primary_target, tags, params, available_entities)` (`effect_executor.py:27,619`)
  Callers: `Combat/combat_manager.py:32,1282,1402,1697`; `Combat/enemy.py:13,1274`; `entities/components/skill_manager.py:10,784,1005`; `systems/turret_system.py:7,158,278,378`; tests `tests/test_knockback.py:12`, `tests/test_player_knockback.py:12`.
- `get_target_finder()` / `TargetFinder` (`geometry/target_finder.py:430,15`)
  Direct caller besides the executor: `Combat/combat_manager.py:1096` (imports `TargetFinder` directly for weapon-arc target queries); `tests/test_geometry_patterns.py:11`.
- `get_tag_registry()` (`tag_system.py:187`) — consumed inside the pipeline only (parser `tag_parser.py:17`, executor `effect_executor.py:22`). No external caller found; keep internal in C#.
- `get_tag_parser()` (`tag_parser.py:186`) — executor + `tests/test_knockback.py:89`.
- `get_tag_debugger()` (`tag_debug.py:257`) — `entities/status_manager.py:8`, `Combat/enemy.py:14`, `Combat/combat_manager.py:33`, `entities/components/skill_manager.py:11`, `systems/turret_system.py:8`, and all 5 crafting minigames (e.g. `Crafting-subdisciplines/smithing.py:743`).

### 2.2 Crafting calculators (all consumed by `Crafting-subdisciplines/`)
- `calculate_smithing_difficulty` / `get_legacy_smithing_params` — `smithing.py:102,146`
- `calculate_refining_difficulty` / `get_legacy_refining_params` — `refining.py:91,134`
- `calculate_alchemy_difficulty` — `alchemy.py:422`
- `calculate_engineering_difficulty` — `engineering.py:675`
- `calculate_enchanting_difficulty` — `enchanting.py:111`
- `calculate_smithing_rewards` — `smithing.py:418`; `calculate_alchemy_rewards` — `alchemy.py:662`; `calculate_engineering_rewards` — `engineering.py:974`; `calculate_enchanting_rewards` — `enchanting.py:379`; `calculate_failure_penalty` — `smithing.py:816`, `refining.py:312`, `alchemy.py:639,662`; `first_try_bonus(discipline)` — `engineering.py:969`, `enchanting.py:374`.
- `core/testing_difficulty_distribution.py:29` imports the whole difficulty API (tool).

### 2.3 Crafting tag processors
- `SmithingTagProcessor` — `data/databases/equipment_db.py:249` (slot + tag inheritance when registering crafted equipment), `Crafting-subdisciplines/smithing.py:742,876`
- `EnchantingTagProcessor` — `data/models/equipment.py:233` (enchantment applicability check on the item model itself)
- `EngineeringTagProcessor` — `core/game_engine.py:2735` (device behavior on placement)
- `AlchemyTagProcessor` — `alchemy.py:926,1046`
- `RefiningTagProcessor` — `refining.py:546,725`

### 2.4 The effect_executor dispatch chain — complete tag enumeration
**Damage path** (`_apply_damage`, `effect_executor.py:113-181`), applied once **per damage tag** in `config.damage_tags`:
1. `critical` special tag pre-roll: `crit_chance` (default **0.15**), `crit_multiplier` (default **2.0**) — `:119-126`. (Distinct from the combat_manager LCK crit — see §11 risks.)
2. Per-tag `context_behavior` vs `target.category`: `damage_multiplier` (`:139-145`), `converts_to_healing` (`:147-151` — **early-returns, skipping any remaining damage tags**).
3. Enemy defense (opt-in via `params['_apply_enemy_defense']`, set only by the melee path at `Combat/combat_manager.py:1691`): `reduction = min(0.75, defense*(1-_armor_penetration)*0.01)` — `:162-171`. Skill/spell damage intentionally bypasses defense (FINDINGS F5 comment `:153-161`).
4. `auto_apply_status` roll from the damage tag's definition (`auto_apply_chance`) — `:177-181` (e.g. fire → burn).

**Status path** (`_apply_status_effects` `:188-223`): every tag in `status_tags` → merge registry defaults, override only keys that exist in defaults (`:199-202` — params not in defaults are dropped; preserve this quirk), immunity check vs `target.category` (`:209-214`), then `target.status_manager.apply_status(tag, params)`.

**Special-mechanics if/elif chain** (`_apply_special_mechanics` `:225-254`) — every handled special tag:
| Tag(s) | Handler | Key params (defaults) | Line |
|---|---|---|---|
| `lifesteal`, `vampiric` | heal source | `lifesteal_percent` (0.15) | 228-229, 256-262 |
| `knockback` | velocity-over-time push away from source | `knockback_distance` (2.0), `knockback_duration` (0.5); writes `target.knockback_velocity_x/y`, `knockback_duration_remaining` | 231-232, 264-306 |
| `pull` | instant position pull toward source, capped at distance | `pull_distance`/`pull_strength` (2.0) | 234-235, 326-373 |
| `execute` | bonus damage below HP threshold | `threshold_hp` (0.2), `bonus_damage` (2.0, bonus portion only) | 237-238, 375-411 |
| `critical` | no-op here (handled in damage) | — | 240-242 |
| `teleport`, `blink` | instant move source→target pos, range-gated | `teleport_range` (10.0), `teleport_type` ('targeted'; 'forward' unimplemented) | 244-245, 413-466 |
| `dash`, `charge` | velocity move toward target (reuses knockback fields) | `dash_distance` (5.0), `dash_speed` (20.0); `damage_on_contact` TODO | 247-248, 468-543 |
| `phase`, `ethereal`, `intangible` | status `phase` on source | `phase_duration` (2.0), `can_pass_walls` (False) | 250-251, 545-568 |
| `summon` | **TODO — not implemented** (comment `:253-254`) | — | — |

**Geometry falloff** (`_calculate_magnitude_multiplier` `:98-111`): `chain` → `(1-chain_falloff[0.3])^index`; `pierce` → `(1-pierce_falloff[0.1])^index`; all else 1.0.

**Hidden state channel**: `self._current_source/_current_tags/_current_context` set per call (`:73-75`) and reflectively fed to `target.take_damage(...)` if its signature accepts `source/tags/context` (`_damage_target` `:573-592`, uses `inspect.signature`). Training dummies depend on this. In C#: replace with an explicit `DamageInfo` struct on an `IDamageable` interface — no reflection.

### 2.5 Interactive crafting
- `create_interactive_ui(station_type, tier, inventory)` factory (`interactive_crafting.py:1153-1179`) — `core/game_engine.py:4414`; `InteractiveAdornmentsUI` direct use `game_engine.py:4637,4644`; renderer reads the concrete classes for drawing `rendering/renderer.py:5822`; smoke test `test_interactive_crafting.py:21`.

### 2.6 Infrastructure
- `Config` — ubiquitous (renderer, character, chunk/world, combat, save_manager, fishing, tests…): e.g. `entities/character.py:51`, `systems/world_system.py:24`, `Combat/combat_manager.py:1119`, `systems/save_manager.py:134`.
- `Camera`, `Notification` — `rendering/renderer.py:10` (`from core import Config, Camera, Notification`).
- `paths.get_resource_path/get_save_path/get_faction_db_path` — 25+ call sites: every JSON DB loader (`data/databases/recipe_db.py:7`, `material_db.py:61`, …), `systems/save_manager.py:13`, `systems/world_system.py:25`, `world_system/living_world/factions/faction_system.py:28`, `rendering/image_cache.py:6`, tools/tests.
- `debug_print` (`debug_display.py:184`) — `entities/character.py:999`, `Combat/combat_manager.py:34`, `Combat/enemy.py:1423`, `entities/components/skill_manager.py:13`, `rendering/renderer.py:4938`.
- `write_crash_report` — `main.py:51`, `core/game_engine.py:11992`.

---

## 3. Dependency Edges

**core/ (in-scope files) imports FROM:**
- `data.models.world.Position` — `geometry/target_finder.py:7`, `geometry/math_utils.py:8`, `camera.py:4`, `effect_executor.py:321` (lazy)
- `data.databases` (`MaterialDatabase`, `RecipeDatabase`, `PlacementDatabase`) — `interactive_crafting.py:15`; `difficulty_calculator.py:153,224` (lazy, gracefully optional)
- `data.models.recipes` (`Recipe`, `PlacementData`) — `interactive_crafting.py:16`
- `entities.components.inventory` (`Inventory`, `ItemStack`) — `interactive_crafting.py:14`
- `Crafting-subdisciplines/rarity_utils` — `crafting_tag_processor.py:486-497` via a **sys.path injection hack** (§11 risk)
- `pygame` — `config.py:3`, `minigame_effects.py:10` only (in scope)
- `data` package facade — `testing.py:5`

**Who imports core/ (in-scope):** `Combat/` (combat_manager, enemy, player_actions), `entities/` (character, status_manager, components: skill_manager, stats, tool), `systems/` (turret_system, world_system, save_manager, class_system, natural_resource, chunk, dungeon), `data/` (models: world, equipment; databases: all loaders via paths, equipment_db, recipe_db), `rendering/` (renderer, image_cache, terrain_renderer, visual_colors), `animation/combat_particles.py:18`, `Crafting-subdisciplines/` (all 6 + fishing), `world_system/` (world_memory_system:336, content_registry ×2, factions), `main.py`, `tests/`, `tools/`.

**Zero imports** from core/ pure-logic into `rendering/`, `Combat/`, `world_system/` — the dependency arrow points inward only. This is why the pure-C# assembly split works.

---

## 4. Engine Coupling (pygame / input / clock touchpoints to redesign)

| Touchpoint | Location | Godot redesign |
|---|---|---|
| `import pygame`; `pygame.init()` + `pygame.display.Info()` in `Config.init_screen_settings` | `config.py:3,96-97` | Delete. Window/scale handled by Godot project settings + stretch mode |
| `Config.toggle_fullscreen` returns `pygame.FULLSCREEN` flag | `config.py:157-170` | `DisplayServer.WindowSetMode` |
| Entire UI-scale/layout block (`UI_SCALE`, `scale()`, `INVENTORY_*`, `MENU_*`, `inventory_grid_origin`) | `config.py:54-150,172-180` | Godot Control anchors/containers; **do not port pixel math**. Note it was §15-reconciled to be the single source of truth for click-vs-draw geometry (`config.py:67-85,132-136`) — in Godot that problem disappears (one Control owns both) |
| `AnimationTimer`/`ScreenShake` use `pygame.time.get_ticks()` | `minigame_effects.py:180-191,569-580` | `_Process(delta)` / `Time.GetTicksMsec()` |
| All particle/background/UI drawing (`pygame.Surface`, `draw`, `blit`, `SRCALPHA`, `BLEND_RGBA_ADD`, `pygame.font`, `pygame.image.load`) | `minigame_effects.py` throughout (e.g. `:224-231,617-623,1035-1043`) | `GpuParticles2D`, `ColorRect`/`TextureRect`, tweens, Godot theme. Keep `ColorPalette` (`:91-169`) and easing curves (`:48-84`) as data |
| `AnimatedButton.update(mouse_pos, mouse_pressed, dt)` — polling input | `minigame_effects.py:824-851` | Godot `Button` signals |
| `Camera.world_to_screen/screen_to_world` — tile→pixel math with `Config.TILE_SIZE` | `camera.py:22-32` | `Camera3D` + `Viewport` ray/unproject; shake via camera offset noise |
| `Camera.shake_offset` fed by ScreenEffects each frame | `camera.py:16` | Camera3D shake component |
| Console `print()` with emoji throughout executor/parser (crash-guarded for cp1252 in `tag_debug.py:57-64`) | `effect_executor.py:125,261,304,…` | Route through injected `ILogger`; delete emoji-guard workaround |
| PyInstaller `sys._MEIPASS` / `%APPDATA%` path logic | `paths.py:36-49,57-76` | `res://` (read-only content) + `user://` (saves, crash reports, faction.db) |
| Renderer-method-name assertions | `testing.py:193-199` | n/a (dropped) |

Everything else in scope is engine-free: `tag_system`, `tag_parser`, `effect_context`, `effect_executor`, `geometry/`, `difficulty_calculator`, `reward_calculator`, `crafting_tag_processor`, `interactive_crafting` (pure state + DB queries), `notifications`, `debug_display`, `crash_handler` — these compile into the pure-logic assembly with no engine references.

---

## 5. Constants & Formulas (exact values from code)

### 5.1 difficulty_calculator.py
- `TIER_POINTS = {1:1, 2:2, 3:3, 4:4}` per item (`:35-40`). **Note**: this linear scale is deliberately NOT the sacred T1..T4=1/2/4/8 tier multipliers; both must survive independently.
- `DIFFICULTY_THRESHOLDS`: common (0,4), uncommon (5,10), rare (11,20), epic (21,40), legendary (41,150) (`:47-53`). **The module docstring (`:18-23`) states different numbers (1-8/9-20/21-40/41-70/71+) — it is STALE; the constant is the truth** (matches CLAUDE.md).
- `DIFFICULTY_RANGES`: min_points 1.0, max_points 80.0 (`:56-59`) — shared with reward_calculator via import (`reward_calculator.py:25`, §15 trap 1).
- Material points: `sum(TIER_POINTS[tier] * quantity)`, min 1.0 (`:130-175`); tier looked up from MaterialDatabase, default 1.
- Diversity multiplier: `1.0 + (unique_count - 1) * 0.1` (`:178-204`).
- Weighted average tier (`:207-250`).
- Linear interpolation of params over normalized points (`:253-283`).
- `SMITHING_PARAMS` (`:66-97`): time_limit (60→25), temp_ideal_range (25→3), temp_decay_rate (0.3→0.6), temp_fan_increment (4→1.5), required_hits (3→12), target_width (100→30), perfect_width (50→10), hammer_speed (3.0→14.0). Temp ideal zone centered at 70, min clamped 55-75, max ≥min+3 capped 85 (`:311-318`).
- `REFINING_PARAMS` (`:104-123`): time_limit (45→15), cylinder_count (3→12), timing_window (0.05→0.01 s), rotation_speed (1.0→4.0), allowed_failures (2→0). Station multiplier `1.0 + station_tier*0.5` (T1=1.5x…T4=3.0x — comment at `:348` claiming "T4=4.5x" is wrong for tier values 1-4; formula is truth) (`:349-350`). `multi_speed` at points ≥ rare threshold 11 (`:363`).
- `ALCHEMY_PARAMS` (`:379-397`): time_limit (60→20), reaction_count (2→6), sweet_spot_duration (2.0→0.4), stage_duration (2.5→0.8), false_peaks (0→5), volatility (0→1). Total = base × diversity × `1.2^(avg_tier-1)` × `(1 + volatility*0.3)` (`:422-428`). Volatility = `clamp((vowel_ratio - 0.3) * 2.5, 0, 1)` over material-id letters (`:450-480`).
- `ENGINEERING_PARAMS` (`:487-509`): time_limit (300→120), puzzle_count (1→2), grid_size (3→4), complexity (1→3, clamped 1-4 at `:587`), hints_allowed (4→1), ideal_moves (6→8). Slot modifier `1.0 + (total_slots-1)*0.05` (`:574-577`). `ENGINEERING_IDEAL_MOVES_TIERS` 12-tier table (`:517-531`): ≤8→6, ≤13→6, ≤18→6, ≤23→6, ≤35→7, ≤44→7, ≤50→7, ≤56→7, ≤68→8, ≤76→8, ≤100→8, ≤999→8.
- `ENCHANTING_PARAMS` (`:609-627`): starting_currency 100, green_slices (12→6, clamp 4-14), red_slices (3→10, clamp 2-12), green_multiplier (1.5→1.2), red_multiplier (0.8→0.0), spin_count always 3; wheel forced to 20 slices with ≥2 grey (`:653-671`).
- Legacy tier fallbacks: `get_legacy_smithing_params` (`:686-717`) and `get_legacy_refining_params` (`:720-747`) — full per-tier tables, still called by minigames when material data is absent (`smithing.py:146`, `refining.py:134`).
- `get_difficulty_tier` iterates thresholds in insertion order (`:754-772`) — in C# use an ordered list, not a Dictionary.

### 5.2 reward_calculator.py
- `REWARD_MULTIPLIER`: min 1.0, max 2.5 (`:28-31`); `calculate_max_reward_multiplier` linear over DIFFICULTY_RANGES (`:81-104`).
- `QUALITY_TIERS`: [0,0.25) Normal, [0.25,0.5) Fine, [0.5,0.75) Superior, [0.75,0.9) Masterwork, [0.9,1.01) Legendary (`:34-40`).
- `FAILURE_PENALTY`: 30%→90% material loss, `0.3 + normalized*0.6` (`:43-46,497-519`); per-material integer loss `int(qty * loss_fraction)` (`:522-546`).
- `FIRST_TRY_BONUS`: default performance_boost 0.10; `eligible_threshold` 0.50; per-discipline overrides {smithing 0.10, enchanting 0.10, engineering **0.05**, alchemy 0.10, refining 0.10} (`:52-62`); accessor `first_try_bonus(discipline)` (`:65-74`).
- `bonus_pct = int(performance * (max_multiplier - 1) * 20)` (`:123-143`); `stat_multiplier = 1 + bonus_pct/100` (`:146-160`).
- Smithing: `base_performance = min(1, avg_hammer_score * (1.2 if temp_in_ideal else 1.0) / 120)`; +0.10 if attempt==1; special-attribute eligible if first try AND ≥0.50 (`:167-227`).
- Refining: rarity-upgrade cap = `min(int(1 + (max_mult-1)*2), quantity_cap)` where quantity_cap: ≥256→4, ≥64→3, ≥16→2, ≥4→1, else 0 (`:263-284`).
- Alchemy: `perf = clamp(chain_ratio*0.6 + timing/100*0.4 - explosions*0.15)`; potency `1 + (perf-0.5)*(max_mult-1)`, duration same ×0.6, both clamped 0.25–2.0 (`:319-358`).
- Engineering: `perf = clamp(completion + time_remaining*0.2 - hints*0.1)`; efficiency `1 + perf*(max_mult-1)*0.4`; durability bonus `int(perf*50)` (`:396-427`).
- Enchanting: efficacy `1 + (final_currency-100)/200`; performance `clamp(final_currency/200)` (`:463-481`).

### 5.3 effect_executor.py / tag_parser.py / geometry
- Chain falloff 0.3, pierce falloff 0.1 (`effect_executor.py:100-108`); crit special tag 0.15 / 2.0x (`:120-121`); enemy-defense `min(0.75, def*0.01)` with armor-pen scaling (`:162-171`) — **this is the sacred "def (max 75%)" term**; lifesteal 0.15 (`:258`); knockback 2.0 tiles / 0.5 s (`:266-267`); execute 20% HP / 2.0x (`:386-387`); teleport 10.0 (`:422`); dash 5.0 / 20.0 (`:477-478`); phase 2.0 s (`:553`).
- Parser: default geometry `single_target` (`tag_parser.py:75`); synergy bonuses multiply `param *= (1+bonus)` for `*_bonus` keys when both tags present (`:149-168`); context inference: damage/debuff→enemy, healing/buff→ally, default enemy (`:111-133`).
- Geometry defaults: chain_count 2, chain_range 5.0; cone_angle 60°, cone_range 8.0; circle_radius/radius 3.0, max_targets 0 (unlimited), origin 'target'; beam_range 10.0, beam_width 0.5, pierce_count 0 (`target_finder.py:57-97`). Facing fallback (1,0) (`math_utils.py:88-112`).
- Geometry conflict priority from JSON: `chain > cone > circle > beam > single_target` (`tag-definitions.JSON` conflict_resolution; loaded `tag_system.py:104-106`).

### 5.4 crafting_tag_processor.py
- `PROCESS_BONUSES` (`:326-357`): smelting {yield 15%/+1, quality 10%/+1}; crushing {25%/+1}; grinding {40%/+1}; purifying {quality 30%/+1}; alloying {quality 15%/+2}.
- Rarity ladder from `Crafting-subdisciplines/rarity_utils.RARITY_TIERS`, fallback `["common","uncommon","rare","epic","legendary"]` (`:485-504`).
- Smithing slot maps (`:30-53`), inheritable FUNCTIONAL_TAGS whitelist (`:95-102`); Engineering role priority `turret > trap > station > device > consumable > utility` (`:146-153`); trap triggers proximity/pressure/tripwire, default proximity (`:162-183`).

### 5.5 config.py (gameplay constants that survive; layout constants do not)
- `CHUNK_SIZE 16`, `TILE_SIZE 32` (`:24-25`), `CHUNK_LOAD_RADIUS 4`, `SPAWN_ALWAYS_LOADED 1` (defaults; real values from `world_generation.JSON`, `:28-33`), `TEMP_WORLD_SEED 13579` (`:44`), spawn (0,0,0) (`:47-49`), `SAFE_ZONE_RADIUS 8` (default, `:52`), `PLAYER_SPEED 0.15`, `INTERACTION_RANGE 3.5`, `CLICK_TOLERANCE 0.7` (`:183-185`), `FPS 60` (`:16`), `KEEP_INVENTORY True` (`:192`), debug toggles (`:188-189`), `RARITY_COLORS` (`:225-232`), deprecated `WORLD_SIZE 176` / `NUM_CHUNKS 11` (`:36-37` — do not port).

### 5.6 interactive_crafting.py structural constants
- Refining hub-spoke slots: T1 1c+2s, T2 1c+4s, T3 2c+5s, T4 3c+6s (`:196-201`). Alchemy sequential slots: T1 2, T2 3, T3 4, T4 6 (`:372`). Engineering slot types: T1/T2 [FRAME,FUNCTION,POWER], T3/T4 +[MODIFIER,UTILITY] (`:496-501`). Smithing grid: T1 3×3, T2 5×5, T3 7×7, T4 9×9 (`:634`, duplicated at `:766`). Adornments grid: T1 8, T2 10, T3 12, T4 14; coordinate range ±7; `SHAPE_TEMPLATES` vertex offsets for 6 shapes (`:822-832`); shape availability cumulative by tier (`:851-862`); rotation match tolerance <1° for non-square shapes (`:1101-1109`).
- Material palette sort: tier → category order `['metal','wood','stone','elemental','monster_drop','fabric','herb','gem','other']` → name (`:20-23,87-100`).
- Smithing/adornments matching normalizes placements to bounding-box origin (1,1) and tries current tier down to T1 (`:680-792`); alchemy is order+quantity exact with 1-indexed JSON slots (`:430-474`); engineering compares sorted (materialId,qty) lists per slot type (`:578-616`); refining compares sorted core and surrounding lists (`:308-348`).

**Sacred constants NOT in this subsystem** (do not go looking for them here): damage pipeline hand/STR/class multipliers and LCK crit (0.12/pt, `CRUX_LCK_CRIT_PER_POINT`) live in `Combat/combat_manager.py:21-24`; EXP curve in `entities/components/leveling.py`; durability floor in equipment logic. The only sacred term implemented here is the 75% defense cap (`effect_executor.py:167`).

---

## 6. Event Topics

**None.** Verified: zero `GameEventBus`/`publish`/`subscribe` references in any in-scope core/ file (grep over `core/` excluding `game_engine.py` — no matches). The tag pipeline is invoked synchronously by callers; crafting events (`CRAFT_COMPLETED` etc.) are published by GameEngine/minigames, not by these modules. For Godot: keep it that way — the pure assembly should stay event-bus-free; the engine glue publishes.

---

## 7. Content JSON Consumed

| File | Consumed via | Loader |
|---|---|---|
| `Definitions.JSON/tag-definitions.JSON` (95 tag defs, 11 categories, conflict_resolution.geometry_priority, mutually_exclusive, context_inference) | `TagRegistry.load()` — path built as `<repo>/Definitions.JSON/tag-definitions.JSON` (`tag_system.py:63-70`), **hardcoded relative to `__file__`, NOT via core.paths** — must go through the C# resource path API | itself |
| `items.JSON/items-materials-1.JSON` (+ Update-N merges) | tier lookups in `calculate_material_points`/`calculate_average_tier` (`difficulty_calculator.py:151-169,221-243`, lazy + optional) and `interactive_crafting.py` palette (`:62-101`) | `data/databases/material_db.py` |
| `recipes.JSON/*` | recipe matching `get_recipes_for_station` (`interactive_crafting.py:318,442,590,777,1044`) | `data/databases/recipe_db.py` |
| `placements.JSON/*` | placement lookups `get_placement` (`interactive_crafting.py:314,432,580,735,1026`) | `data/databases/placement_db.py` |
| `recipes.JSON/*` read **directly from disk** (path-guessing) | `testing_difficulty_distribution.py:41-87` (tool only) | none |
| `assets/minigame_backgrounds/<discipline>_bg.{png,jpg,jpeg}` (optional) | `find_background_image` (`minigame_effects.py:23-41`) | pygame image load — becomes Godot texture |

All content files are reused verbatim per the standing decision; only the loaders port.

---

## 8. Persistent State

- **`Config.KEEP_INVENTORY`** is the single core/-owned saved value: serialized under `game_settings.keep_inventory` (`systems/save_manager.py:127-137`) and restored on load (`:589-599`).
- **Reward output contract feeds saved item state**: the dicts returned by `calculate_*_rewards` (keys: `stat_multiplier`, `quality_tier`, `bonus_pct`, `performance_score`, `max_multiplier`, `first_try_eligible`, `first_try_bonus_applied`, discipline-specific `potency_multiplier`/`duration_multiplier`/`efficiency_multiplier`/`durability_bonus`/`efficacy_multiplier`/`max_rarity_upgrade`) are baked into crafted items' `crafted_stats` by the minigames and persisted by inventory serialization. The C# port must keep these key names/semantics stable or provide a save-migration shim.
- Debug toggles (`DEBUG_INFINITE_RESOURCES`, `DEBUG_INFINITE_DURABILITY`) are **not** saved.
- `interactive_crafting` borrowed materials are transient (returned on cancel via `return_all_materials`, `:144-156`) — nothing persists. A mid-session quit while materials are borrowed relies on GameEngine calling return-all; verify the Godot flow preserves this or materials dupe/vanish.
- `paths.py` defines where saves live (`saves/` next to source, or `%APPDATA%/Game1/saves` bundled — `paths.py:38-52`) and `faction.db` location (`:122-129`) → all becomes `user://`.

---

## 9. 3D Notes (what necessarily changes 2D→3D)

1. **Position is already 3D-shaped, math is not**: `Position(x,y,z=0)` with full 3D `distance_to` (`data/models/world.py:10-17`), but ALL geometry math ignores z: cone/beam/direction use only x/y (`math_utils.py:41-75`; beam projection `target_finder.py:400-424`), knockback/pull/teleport/dash mutate only x/y (`effect_executor.py:296-299,354-366,451-459,519-523`). Decision needed (mirrors the paused Unity plan's `DistanceMode`): implement `TargetFinder` with a toggleable planar-XZ vs full-3D mode. Recommended: planar XZ for parity, with vertical tolerance for target validity.
2. **Coordinate mapping**: Python (x,y) ground plane → Godot (x, z), height = y. Every formula in §5.3 is expressed in tile units — keep 1 tile = 1 world unit in Godot so `cone_range 8.0` etc. stay verbatim.
3. **Facing**: `estimate_facing_direction` falls back to `last_move_direction`/velocity/(1,0) (`math_utils.py:88-112`). In 3D the character has a real yaw — replace the heuristic with transform basis, but keep the "aim at primary target overrides facing" rule (`target_finder.py:179-183`).
4. **Knockback/dash as velocity-over-time** writes raw fields (`knockback_velocity_x/y`, `knockback_duration_remaining`) that entity movement integrates. In Godot these become impulses/overrides on `CharacterBody3D` movement — preserve distance÷duration velocity semantics exactly (`effect_executor.py:289-299`), and decide whether knockback can push into walls (Python has no collision check here; Godot's `MoveAndSlide` will add one — a behavior change to document in the parity checklist).
5. **Beam width / cone become 3D volumes**: keep them as 2D checks on the ground plane (cylinder/wedge with implicit infinite height) for parity; anything smarter is a design change.
6. **Camera** (`camera.py`) is entirely replaced by `Camera3D`; `screen_to_world` click-picking becomes viewport ray casting onto the ground plane — `CLICK_TOLERANCE 0.7` (`config.py:185`) must be reinterpreted as a world-space pick radius.
7. **Interaction range** `INTERACTION_RANGE 3.5` — decide planar vs 3D distance (same DistanceMode switch).
8. **Crafting minigames stay 2D** (standing decision): `interactive_crafting` sessions + difficulty/reward calculators are resolution- and dimension-agnostic already; the adornments Cartesian grid (±7) stays a 2D Control overlay. `rotate_point` (`interactive_crafting.py:864-873`) is pure 2D and stays.

---

## 10. Godot Mapping

### Pure-logic assembly `Game1.Core` (plain C#, dotnet-testable, no Godot refs)
- `Tags/TagDefinition` (record), `Tags/TagRegistry` (loads tag-definitions.JSON via injected `IContentSource`), `Tags/TagParser`, `Tags/EffectConfig`, `Tags/EffectContext`.
- `Effects/EffectExecutor` — dispatch table or switch over special tags (the current if/elif is fine as a C# switch; the CLAUDE.md "dispatch table" was aspirational). Replace duck typing with interfaces: `IDamageable { TakeDamage(DamageInfo) }`, `IHealable`, `IStatusReceiver { StatusManager }`, `IKnockbackable { SetImpulse(Vector3, float duration) }`, `IPositioned { Vector3 Position }`, `ICategorized { string Category }`. `DamageInfo { Amount, DamageType, Source, Tags, Context }` replaces the `inspect.signature` reflection (`effect_executor.py:577-592`).
- `Effects/TargetFinder` + `GeometryMath` (with `DistanceMode` planar/3D switch, §9.1). Replace `_is_valid_context`'s type-name string sniffing (`target_finder.py:338-374`) with a `TeamOrKind` enum on entities; preserve the enemy-source context flip (`:44-52`) exactly.
- `Crafting/DifficultyCalculator` (static), `Crafting/RewardCalculator` (static), `Crafting/TagProcessors/*` (5 static classes), `Crafting/RarityLadder` (absorb `rarity_utils`, killing the sys.path hack).
- `Crafting/Sessions/`: `RefiningSession`, `AlchemySession`, `EngineeringSession`, `SmithingSession`, `AdornmentsSession` (ports of the `Interactive*UI` classes minus the word "UI"), + `ISessionInventory` abstraction over borrow/return so they test without the real inventory. Factory `CraftingSessionFactory`.
- `Diagnostics/ITagLogger` (interface with the ~20 specialized methods of `tag_debug.py`) + `ConsoleTagLogger`; `Diagnostics/DebugMessageBuffer` (port of `debug_display.py` logic); `Diagnostics/CrashReporter`.
- `GameConfig` static class: only §5.5 gameplay constants + `RarityColors`. NO layout/scale members.
- `Notification` record.

### Engine glue (Godot project, thin)
- `GameServices` **autoload** (single entry): constructs/holds `TagRegistry`, `TagParser`, `EffectExecutor`, `TargetFinder`, DB singletons; injects `GodotContentSource` (`res://`) and `GodotTagLogger`. This replaces every `get_*()` module-global singleton accessor (`tag_system.py:184-192`, `tag_parser.py:183-191`, `effect_executor.py:616-624`, `target_finder.py:427-435`, `tag_debug.py:254-270`, `debug_display.py:164-181`, `minigame_effects.py:1515-1522`, `paths.py:132-133`).
- `PathService` → `res://` for content, `user://` for saves/crash/faction.db (replaces `paths.py`).
- `Camera3D` rig node (follow + shake) replaces `camera.py`.
- Crafting minigame overlay: `CanvasLayer` > `Control` panels per discipline rendering the Session state; `GpuParticles2D` + `Tween` recreate `minigame_effects` (port `ColorPalette` values and the `MinigameMetadataOverlay` content contract — discipline, difficulty_tier + tier colors (`minigame_effects.py:963-969`), difficulty_points, time_limit, max_bonus, special_params, blocking min-display 0.5 s / duration 8 s (`:885-930`) — as a `MetadataPanel.tscn`).
- Debug overlay `Control` consuming `DebugMessageBuffer` (replaces renderer's use at `rendering/renderer.py:4938`).
- C# `AppDomain.CurrentDomain.UnhandledException` + Godot crash hook → `CrashReporter` (replaces `main.py:51` boot guard and the frame guard at `game_engine.py:11992`).

### Feature-parity checklist items originating here (for the rendering-replacement doc)
Screen shake on craft events; 5 themed minigame backgrounds (optional custom image override per discipline); spark/ember/bubble/steam/spirit particle vocabularies; animated progress bar quarter-glow; metadata overlay gating minigame input; on-screen debug message dedup (`(xN)` counters).

---

## 11. Port Complexity, Ordering, Risks

### Complexity
| Unit | Size | Notes |
|---|---|---|
| tag_system + tag_parser + effect_context | **S** | Direct translation; JSON schema stable |
| geometry/ | **S/M** | Small code, but the 2D→3D DistanceMode decision + facing redesign is design work |
| effect_executor | **M** | Interface extraction (kills reflection + hasattr), preserve 6 behavioral quirks listed below |
| difficulty_calculator + reward_calculator | **S** | Pure math; port tables verbatim; golden-master test against Python outputs for all ~167 recipes |
| crafting_tag_processor | **S** | Static tables; absorb rarity_utils |
| interactive_crafting | **M/L** | 5 matching algorithms with exact-equality semantics; needs inventory + 3 DBs ported first; golden-master with recorded placements |
| config decomposition | **S** | Mostly deletion |
| minigame_effects re-creation | **L** (engine work, not logic) | Feature-parity, not line-parity |
| paths/crash/debug/notifications | **S** | |

### Ordering constraints
1. **First**: `data/models` (`Position`, `Recipe`, `PlacementData`, `ItemStack`) and the Material/Recipe/Placement database loaders — everything in scope leans on them.
2. `tag_system` → `tag_parser` → `geometry` → `effect_executor` (strict chain). `tag_debug`/`ITagLogger` interface must exist before executor/finder compile.
3. `difficulty_calculator` before `reward_calculator` (shared `DIFFICULTY_RANGES`, `reward_calculator.py:25`) — both before any minigame port.
4. `crafting_tag_processor` before `equipment_db`/`equipment` model ports (they call it at load time: `equipment_db.py:249`, `equipment.py:233`).
5. `interactive_crafting` sessions before the crafting UI scenes.
6. Combat (out of scope) consumes the executor — the tag pipeline is on the critical path for combat parity.

### Top risks / gotchas (each verified in code)
1. **Two independent crit systems.** `effect_executor` rolls its own `critical`-tag crit (0.15/2.0x, `effect_executor.py:119-126`) while the sacred LCK-driven crit (0.12/pt) lives in `Combat/combat_manager.py:21-24`. They are different mechanics (skill-tag crit vs weapon-swing crit). Do NOT unify them during the port; document both.
2. **Latent bug — `InteractiveEngineeringUI.clear_placement` KeyErrors on T1/T2 stations.** `self.slots` only contains the tier's available slot types (`interactive_crafting.py:508-510`) but clear iterates `ALL_SLOT_TYPES` (`:571-576` — `for slot_type in self.ALL_SLOT_TYPES: for mat in self.slots[slot_type]`) → `KeyError: 'MODIFIER'` on tier-1/2 engineering "clear". Fix in the C# port (iterate `slots.Keys`); optionally backport.
3. **First-try bonus inconsistency (§15 trap 3 half-applied).** The per-discipline override table exists (`reward_calculator.py:55-61`, engineering 0.05) and minigames call `first_try_bonus()` for their *local* performance value (`engineering.py:968-970`), but the reward functions themselves still add the flat default `FIRST_TRY_BONUS['performance_boost']` = 0.10 internally (`reward_calculator.py:203-206,341-345,416-420`). Engineering effectively gets 0.05 applied to its displayed performance and 0.10 inside the reward calc. Port the behavior as-is (bug-compatible) and flag for the designer; a "clean" port would silently change crafted-item stats.
4. **Duck typing everywhere in the executor/finder.** `hasattr(target,'status_manager')`, `hasattr(target,'knockback_velocity_x')`, `hasattr(source,'definition') and hasattr(source,'is_alive')` (Enemy detection, `target_finder.py:47`), type-name sniffing `'enemy' in type(entity).__name__.lower()` (`target_finder.py:339-373`), and `inspect.signature`-based `take_damage` dispatch (`effect_executor.py:577-592`). The C# interface design is the single biggest correctness surface of this port — a missed capability silently no-ops in Python but must be explicit in C#.
5. **Behavioral quirks that must survive verbatim** (write characterization tests before porting): (a) multi-damage-tag effects apply full base damage once per tag (`effect_executor.py:129-174`); (b) `converts_to_healing` early-returns and skips remaining damage tags (`:147-151`); (c) status param merge only overrides keys present in the tag's defaults (`:199-202`); (d) enemy-source context flip in targeting (`target_finder.py:44-52`); (e) synergy bonuses mutate merged params multiplicatively and are order-of-tag-list dependent (`tag_parser.py:149-168`); (f) `get_difficulty_tier` depends on dict insertion order (`difficulty_calculator.py:764-772`).
6. **Hidden coupling — sys.path hack.** `crafting_tag_processor.upgrade_rarity` injects `Crafting-subdisciplines/` into `sys.path` to import `rarity_utils` with a silent hardcoded fallback ladder (`crafting_tag_processor.py:485-497`). In C#, make `RarityLadder` a first-class shared type.
7. **Numeric semantics.** Python `round()` and C# `Math.Round` both bank-round (OK — used in `rotate_point`, `interactive_crafting.py:871-873`, and param rounding in difficulty calc), but Python `int()` truncates toward zero while param values are guaranteed positive here — audit each `int(...)` anyway (`reward_calculator.py:143,427,542`). Recipe matching relies on Python tuple `sorted()` over `(str,int)` — provide an explicit comparer. `random.random()` sites (`effect_executor.py:123,178`; `crafting_tag_processor.py:412-444`) need an injectable RNG for testability.
8. **Stale docs will mislead a porter.** `difficulty_calculator.py:18-23` docstring thresholds contradict the constant at `:47-53`; comment at `:348` says station mult "1.5x-4.5x" but the formula yields 1.5–3.0 for tiers 1–4; `core/README.md` describes a 6-file module from 2025. Code is truth.
9. **Near-dead code**: `tag_system_debugger.py` (tests/docs only), `testing.py` (F10 self-test), `Config.WORLD_SIZE/NUM_CHUNKS` (deprecated), `interactive_crafting.player_narrative` field (`:51-52`, LLM hook consumed by game_engine only). Don't spend port effort on them.
10. **TagRegistry path bypass**: it builds its JSON path from `__file__` (`tag_system.py:63-65`) instead of `core.paths` — in a packaged build this works only because PyInstaller mirrors the tree. In Godot everything must route through the `res://` content source, including this file.

# 07 — Crafting-subdisciplines/ Minigames — Porting Contract

**Subsystem root**: `Game-1-modular/Crafting-subdisciplines/`
**Verified against code**: 2026-07-17 (branch `crux-foundry`). Every claim cites `file:line`. Docs drift — `docs/GAME_MECHANICS_V6.md:3685-3689` still lists stale line counts (e.g. smithing 748 vs actual 929), and `docs/MODULE_REFERENCE.md:1621` documents `EnchantingMinigame` as the enchanting minigame even though the live one is `SpinningWheelMinigame`. Trust this file + the code.

**Scope decision (standing)**: these minigames remain 2D. Their *logic* (scoring, performance 0-1, timing windows, wheel/cylinder/puzzle state machines, material consumption contract incl. 30-90% failure loss) ports to the pure-logic C# assembly. Their *presentation* (currently pygame draws inside `core/game_engine.py`, NOT inside this directory) is replaced by Godot Control-node overlay panels in the 3D game.

---

## 1. File Table

| File | LOC | Responsibility | Disposition |
|---|---|---|---|
| `smithing.py` | 929 | `SmithingMinigame` (temperature + hammer timing, binned scoring) + `SmithingCrafter` (recipe load, can_craft, instant/minigame craft, tag inheritance) | **port-to-C#** (decompose: minigame logic → pure assembly; crafter collapses into shared `CrafterBase`) |
| `alchemy.py` | 1,083 | `AlchemyReaction` (5-stage oscillating reaction), `AlchemyMinigame` (chain/stabilize), `AlchemyCrafter` | **port-to-C#** (same decomposition) |
| `refining.py` | 839 | `RefiningMinigame` (rotating-cylinder lockpicking), `RefiningCrafter` (quantity-based rarity upgrade 4:1), `RefiningStation` (dead) | **port-to-C#**; **drop-dead-code** `RefiningStation` (refining.py:777-839 — "reference implementation", `validate_recipe` is a `return False` TODO at 829-839, zero external callers) |
| `engineering.py` | 1,323 | `RotationPipePuzzle`, `LogicSwitchPuzzle`, `EngineeringMinigame` (sequential puzzles, efficiency scoring), `EngineeringCrafter`; plus `SlidingTilePuzzle` (deprecated auto-solve, engineering.py:547-580), `TrafficJamPuzzle` / `PatternMatchingPuzzle` (empty placeholders, 584-619) | **port-to-C#** the two live puzzles + minigame + crafter; **drop-dead-code** the deprecated/placeholder puzzle classes (keep the `"slide"` action tolerated as no-op only if save compat demands — it doesn't, nothing persists puzzles) |
| `enchanting.py` | 1,422 | `SpinningWheelMinigame` (**the live minigame** — 3-spin gambling wheel, efficacy ±50%), `EnchantingCrafter` (applies enchantment to `EquipmentItem`); plus `PatternMatchingMinigame` (435-748) and `EnchantingMinigame` (751-1060) | **port-to-C#** SpinningWheel + crafter; **drop-dead-code** `PatternMatchingMinigame` and `EnchantingMinigame` — `create_minigame` only ever returns `SpinningWheelMinigame` (enchanting.py:1262) and no external file instantiates the other two (verified by repo-wide grep) |
| `fishing.py` | 879 | `FishingConfig` (JSON-config singleton), `Ripple` dataclass, `FishingMinigame` (OSU-style ripple clicking), `FishingManager` (can_fish, start, process_result incl. rod durability + loot) | **port-to-C#** (config POCO + logic; `FishingManager.process_result` touches Character/equipment — thin seam) |
| `rarity_utils.py` | 281 | `RARITY_TIERS` ladder (single source of truth, §15 trap 2), `RaritySystem` (uniformity check, modifier application, category inference), module-global `rarity_system` singleton | **port-to-C#** (make DI-injectable; kill module-global mutable singleton with `debug_mode` flag) |
| `crafting_simulator.py` | 2,337 | Standalone pygame dev harness (own window, own main loop, `__main__` at crafting_simulator.py:2326-2337) for testing all 5 crafters outside the game | **engine-replaces / drop** — do not port line-by-line. Its *test intent* is reborn as `dotnet test` golden-value suites + one Godot debug scene. Its one unique formula (`calculate_rarity_bonus`, 2.5%/rarity-level, crafting_simulator.py:289-337) is simulator-only and unused by the game — do not port into gameplay |
| `__init__.py` | 1 | comment only | drop (C# namespaces) |
| `rarity-modifiers.JSON` | data | Category×rarity stat modifiers (weapon/armor/tool/consumable/device/station) consumed by `rarity_utils.py:72` | **reuse verbatim** (this is content JSON living inside a code dir — relocate reference only, never edit) |
| `Crafting reference` (text), `smithing-crafting.html` (React prototype), `SIMPLIFIED_RARITY_SYSTEM.md`, `STAT_MODIFIER_DESIGN.md` | docs | Historical design prototypes/guides | drop-dead-code / archive |

Python LOC total: **9,094** (`wc -l`, 2026-07-17).

---

## 2. Public Surface (who actually calls what)

The **only production caller** is `core/game_engine.py`. It imports the modules flat (not as a package) after a `sys.path.insert` of the directory (game_engine.py:68-75):
`from smithing import SmithingCrafter` … `from fishing import FishingMinigame, FishingManager, get_fishing_manager`, plus `from rarity_utils import rarity_system`.

### Crafters (one instance each, constructed at engine init — game_engine.py:187-191)
| API | Called from |
|---|---|
| `SmithingCrafter()/RefiningCrafter()/AlchemyCrafter()/EngineeringCrafter()/EnchantingCrafter()` ctors (load recipes+placements) | game_engine.py:187-191 |
| `get_crafter_for_station(station_type)` maps `'smithing'/'refining'/'alchemy'/'engineering'/'adornments'` → crafter | game_engine.py:4166-4178 |
| `crafter.can_craft(recipe_id, inv_dict)` → `(bool, err)` | game_engine.py:7020 (instant-craft path) |
| `crafter.craft_instant(recipe_id, inv_dict)` | game_engine.py:7033 (instant craft = 0 EXP, game_engine.py:7062-7063) |
| `crafter.create_minigame(recipe_id, [target_item,] time_bonus, quality_bonus)` | game_engine.py:4272 (adornments variant) and 4280 (others) |
| `crafter.craft_with_minigame(recipe_id, inv_dict, result, …)` — adornments passes `target_item=` (8920); refining passes `alloy_quality_bonus=` from titles (8927-8930); others plain (8932) | game_engine.py:8916-8932 |
| `rarity_system.debug_mode = True/False` (F1 infinite resources) | game_engine.py:7008/7017, 8909/8914 |

### Minigame instances (duck-typed; engine drives them by `minigame_type` string)
| Method | Caller (game_engine.py) |
|---|---|
| `.start()` | 4393; fishing via `FishingManager.start_fishing` → fishing.py:765 |
| `.update(dt)` every frame while active (skipped when metadata overlay blocks) | 8556-8558 |
| `.result` polled; non-fishing auto-completes via `_complete_minigame()` | 8561-8566, 8870 |
| `.get_state()` → dict consumed by per-discipline render fns | `_render_smithing_minigame` 9113, alchemy 9645, refining 10039, engineering 10483, enchanting 11161, fishing 11669 |
| Smithing: `.handle_fan()` on SPACE (728); `.handle_hammer()` on button click (2486) | keyboard 727-728, mouse 2486 |
| Alchemy: `.chain()` on C / click (731, 2489); `.stabilize()` on S / click (733, 2499) | 729-733, 2489-2499 |
| Refining: `.handle_attempt()` on SPACE (735) | 734-735 |
| Engineering: `.handle_action('rotate'/'toggle'/'reset'/'slide', row=, col=)` (2418, 2421, 2434, 2439); `.check_current_puzzle()` (2443, 2492); per-puzzle bonus toast reads `.difficulty_points` and computes `max_bonus = 1.0 + difficulty_points * 0.02` (2471-2473) | 2418-2499 |
| Enchanting wheel: `.place_bet(amount)` (2378), `.spin_wheel()` (2385), `.advance_to_next_spin()` (2392), reads `.current_currency` (2395) | 2341-2400 |
| Fishing: `.handle_click(local_x, local_y)` (2515); completion is click-gated → `_complete_fishing_minigame()` (8563-8564, 11869) | 2505-2515 |
| ESC-ESC abandon (double-press within 1500 ms) nukes `active_minigame` with **no material loss** | 709-726 |

### Fishing manager
`get_fishing_manager()` singleton (fishing.py:874-879): `can_fish` (game_engine.py:11653), `start_fishing` (11659), `process_result(character)` (11886) which itself mutates rod durability and returns loot/xp.

### Other callers
- `tests/crafting/test_no_crash.py:14-18` + `tests/crafting/__init__.py:12` (same sys.path trick) — smoke tests instantiate all 5 crafters.
- `crafting_simulator.py:26-31` (dev harness).
- `core/crafting_tag_processor.py:490` reads `Crafting-subdisciplines/rarity-modifiers.JSON` by path (reverse content dependency into this folder).
- `Game1.spec:89` bundles the directory for PyInstaller.

**Dead public surface** (exists, zero callers): crafter `.get_placement()` / `self.placements` on the game path — the real game reads placements from `PlacementDatabase` (`data/databases/placement_db.py:214`) via `rendering/renderer.py:142,287,439,610,784`; only `crafting_simulator.py:1450-1453,1695` uses the crafter copies. Also `EngineeringMinigame.save_progress/load_progress` (engineering.py:891-913; `load_progress` body is `pass`), never called anywhere.

---

## 3. Dependency Edges

### Imports FROM other subsystems (mostly lazy/inline `try: import … except ImportError: fallback`)
| Target | Sites |
|---|---|
| `core.difficulty_calculator` — `calculate_{smithing,refining,alchemy,engineering,enchanting}_difficulty`, `get_legacy_*_params`, `get_difficulty_description` | smithing.py:102-106,146; refining.py:91-95,134; alchemy.py:422; engineering.py:675; enchanting.py:111 |
| `core.reward_calculator` — `calculate_*_rewards`, `calculate_failure_penalty`, `first_try_bonus` | smithing.py:418,817; alchemy.py:639,662; refining.py:312; engineering.py:969,974; enchanting.py:374,379 |
| `core.crafting_tag_processor` — `SmithingTagProcessor`, `AlchemyTagProcessor`, `RefiningTagProcessor` | smithing.py:742,876; alchemy.py:926,1046; refining.py:546,725 |
| `core.tag_debug.get_tag_debugger` | smithing.py:743,877; alchemy.py:927,1060; refining.py:547,738 |
| `core.paths.get_resource_path` (cwd-robust JSON resolution) | every `load_recipes`/`load_placements` (e.g. smithing.py:547, alchemy.py:803, refining.py:381, engineering.py:1062, enchanting.py:1086) |
| `entities.components.crafted_stats.generate_crafted_stats` | smithing.py:852; engineering.py:1272 |
| `data.databases.equipment_db.EquipmentDatabase` | smithing.py:853-861; engineering.py:1273-1283 |
| `data.models.ResourceType` | fishing.py:713 |
| `core.config.Config` (`DEBUG_INFINITE_DURABILITY`) | fishing.py:835-836 |
| intra-package: `from rarity_utils import rarity_system` / `RARITY_TIERS` | smithing.py:20; alchemy.py:31; refining.py:32,527,681; engineering.py:32; enchanting.py:33 |
| `target_item.apply_enchantment(...)` — enchanting calls into `EquipmentItem` behavior | enchanting.py:1351-1354 |
| fishing → `character.titles.get_total_bonus`, `character.buffs.get_total_bonus`, `character.stats.*`, `character.get_equipped_tool`, `character.stat_tracker.record_*`, `resource.get_loot()` | fishing.py:252-268, 719-729, 749-762, 793-857 |

### Who imports THIS subsystem
`core/game_engine.py:68-75` (only game path); `tests/crafting/*`; `crafting_simulator.py` (internal). Nothing in `world_system/`, `Combat/`, `systems/`, or `rendering/` imports it. **Port note**: the flat-module import style (`from smithing import …`, enabled by sys.path injection) means module names are effectively global — in C# use one namespace `Game1.Core.Crafting`.

---

## 4. Engine Coupling (every pygame / input / clock / pixel touchpoint)

Inside the subsystem itself the coupling is remarkably thin — but the *surrounding* coupling in game_engine is heavy:

1. **`pygame.time.get_ticks()` wall clock** — smithing.py:170 (`start`) and smithing.py:210-219: temperature decays once per >100 ms wall-clock tick, independent of the `dt` passed to `update()`. **Redesign**: accumulate `dt` to a 0.1 s tick in C#; behavior must match (decay per 100 ms tick = `TEMP_DECAY / (1+speed_bonus)`).
2. **Dead pygame imports** — alchemy.py:28, refining.py:28, engineering.py:29, enchanting.py:30, fishing.py:24 import pygame and never use it (verified: only smithing.py uses `pygame.` outside the simulator). Drop.
3. **`time.time()` wall clocks** — engineering.py:722-755 (`start_time`, `update` ignores its `dt` and diff's wall time; `get_time_remaining` too) and enchanting.py:227-247, 288-289 (wheel spin animation: 2000 ms duration, ease-out cubic `1-(1-p)^3`, `total_rotation = 360*5 + slice_index*18 + 9`). **Redesign**: dt-accumulated timers. Note the wheel *animation* (rotation easing) is embedded in the logic class — in Godot move easing to the Control scene (Tween), keep only "spin resolves after N seconds to slice X" in logic.
4. **Pixel-space logic constants** — hammer bar width 400 px (smithing.py:124,159) with all timing zones derived from it; enchanting dead-class workspace radius 300 px / center (400,400) (enchanting.py:789-790); fishing pond 500×400 px + margin 50 (fishing.py:177-179 via config). These are *logic units* masquerading as pixels; port as abstract units, let Control scenes scale.
5. **Rendering lives in the caller** — `_render_*_minigame` in game_engine.py:9113, 9645, 10039, 10483, 11161, 11669 draw from `get_state()` dicts (pygame.draw/Surface/font). All replaced by Godot Control scenes bound to the same state objects. The `get_state()` dict schemas (smithing.py:493-517, alchemy.py:751-779 & 302-316, refining.py:332-356, engineering.py:1020-1037 & per-puzzle 287-301/530-544, enchanting.py:414-432, fishing.py:651-686) are therefore the **render contract** — preserve them as typed C# state records.
6. **Input mapping lives in the caller** — keyboard: game_engine.py:707-738 (SPACE fan/attempt, C chain, S stabilize, double-ESC abandon w/ 1500 ms window at 714-715); mouse: game_engine.py:2341-2520 (bet slider, spin, engineering grid clicks incl. row/col hit-testing, hammer button, fishing pond-local coordinates via `fishing_pond_rect` at 11686-11688). Godot: InputEvent handling in the Control scenes → calls into logic API.
7. **World pause semantics** — game_engine.py:8431: the entire world/combat/WMS update is skipped while `active_minigame` is set; minigame `update(dt)` is also skipped while the metadata overlay blocks (8556-8558). In Godot: `get_tree().paused = true` + minigame layer `process_mode = ALWAYS`, and replicate the overlay-block gate.
8. **External mutation of minigame internals (hidden coupling)** — the INT-stat difficulty reduction *reaches into the constructed minigame and mutates attributes* via `hasattr`: `minigame.HAMMER_SPEED`, `.TEMP_DECAY`, `.time_limit`, `.rotation_speed`, `.speed_bonus` (game_engine.py:4325-4389, driven by `stats-calculations.JSON` config). C# port must expose an explicit `ApplyIntelligenceModifiers(IntTuning t)` on each minigame instead of attribute poking.
9. **stdout as UI** — dozens of `print()` feedback lines (e.g. smithing.py:441-443, fishing.py:407, 627-632). Replace with a feedback-event list on the state object or logger.
10. **`FishingManager.process_result` mutates game objects directly** — rod durability write (fishing.py:850), resource depletion (fishing.py:807-809), stat_tracker records (852-857), reads `Config.DEBUG_INFINITE_DURABILITY` (835-836). This is the one class in the folder that is *not* pure — split into pure result computation + an application seam in glue.

---

## 5. Constants & Formulas (exact values from code)

### 5.1 Shared (all disciplines)
- **Failure material loss 30%→90%**: `loss = 0.30 + normalized_difficulty * 0.60`, normalized over difficulty points 1.0→80.0 (`core/reward_calculator.py:43-46, 497-519`; ranges `core/difficulty_calculator.py:56-58`). Crafters fetch it via `calculate_failure_penalty` (smithing.py:816-819, refining.py:311-315, alchemy.py:639-641 explosion adds +0.10 capped 0.9).
- **Material consumption contract** (critical): crafters deduct from a **throwaway `inv_dict` copy**; the *real* inventory is charged by the engine — success: `RecipeDatabase.consume_materials` (game_engine.py:8973; recipe_db.py:211+), failure: `RecipeDatabase.consume_materials_partial(recipe, inventory, loss_fraction)` (game_engine.py:8944-8951; recipe_db.py:166-209). `loss_fraction` comes from crafter result `loss_fraction` or `loss_percentage/100`, default 1.0 (game_engine.py:8944-8947). The 2026-07 audit note in recipe_db.py:170-174 records that failures used to wrongly consume 100%. Instant-craft path likewise: crafter mutates dict, engine calls `consume_materials` (game_engine.py:7036-7039).
- **Rarity uniformity**: all inputs must share one rarity or craft is blocked; debug mode bypasses (rarity_utils.py:82-112). Uniformity check keys off `materialId` only (rarity_utils.py:104) while quantity checks accept `itemId` or `materialId` — port faithfully.
- **Rarity ladder**: `['common','uncommon','rare','epic','legendary']` single source (rarity_utils.py:27).
- **Rarity stat modifiers**: `stat = int(stat * (1 + bonus))` per category/rarity from `rarity-modifiers.JSON`; special_effects copied as flags; common = no-op (rarity_utils.py:129-173).
- **First-try bonus**: `first_try_bonus(discipline)` — default `performance_boost` with per-discipline overrides incl. alchemy 0.10, refining 0.10 (reward_calculator.py:48-71); consumed at engineering.py:967-970 and enchanting.py:372-375 (§15 trap 3).
- **Quality tiers by performance**: 0-.25 Normal / .25-.50 Fine / .50-.75 Superior / .75-.90 Masterwork / .90-1.0 Legendary (reward_calculator.py:34-40).
- **Skill/title bonus feed**: `total_time_bonus = quicken-buff + title time bonus`, `total_quality_bonus = max(empower, elevate, pierce) + title quality bonus`, per-discipline title keys `smithingTime/smithingQuality`, `refiningPrecision`, `alchemyTime/Quality`, `engineeringTime/Quality`, `enchantingTime/Quality`, refining reuses `smithingTime` (game_engine.py:4212-4261).

### 5.2 Smithing (`SmithingMinigame`)
- Difficulty params (temp band, decay, fan increment, hammer speed, required hits, target/perfect width, time limit) come from `calculate_smithing_difficulty(recipe)` (smithing.py:109-124); `HAMMER_BAR_WIDTH = 400` fixed (124).
- Speed bonus slows decay: `effective_decay = TEMP_DECAY / (1 + speed_bonus)` per 100 ms tick (smithing.py:213-218); fan: `temp = min(100, temp + TEMP_FAN_INCREMENT)` (236); hammer marker bounces across 0..400 at `HAMMER_SPEED` px/frame-update (222-226).
- **Binned timing score** (smithing.py:238-286): `w = (400/2)/9 ≈ 22.2`; distance-from-center thresholds `0.3w→100, 1w→90, 2w→80, 3w→70, 4w→60, 6w→50, 9w→30, else 0`.
- **Temperature multiplier** (288-320): 1.0 inside `[TEMP_IDEAL_MIN, TEMP_IDEAL_MAX]`; else `exp(-0.0433 * deviation²)` (k = ln2/16, 0.5 at 4° off), clamped to [0.1, 1.0].
- Strike score = `round(timing * temp_mult)` (344); categorized ≥100 perfect / ≥90 excellent / ≥70 good / ≥50 fair / ≥30 poor / else miss (355-366).
- End: `final_score = avg(strike scores)`; `earned_points = sum(scores)`, `max_points = REQUIRED_HITS * 100` (404-414); rewards via `calculate_smithing_rewards(difficulty_points, {avg_hammer_score, temp_in_ideal, attempt})` (418-432); buff quality adds `int(buff * 10)` percentage points to bonus (435-437). Legacy fallback thresholds 140/100/70 → +15/+10/+5% (464-471).
- Craft failure loss uses `calculate_failure_penalty(difficulty_points)`, fallback 0.5 (816-819).
- Crafted equipment stats via `generate_crafted_stats(minigame_result, recipe, item_type)` + rarity modifiers (852-873); tags inherited via `SmithingTagProcessor.get_inheritable_tags(recipe.metadata.tags)` (876-880).

### 5.3 Alchemy (`AlchemyReaction` / `AlchemyMinigame`)
- **Secret value from vowels of material id**: `clamp((vowel_ratio - 0.2) * 2, 0, 1)`, default 0.5 if no letters (alchemy.py:78-105). Oscillation count: `<0.25→1, <0.65→2, else→3` (107-127).
- **Stage durations (s) by ingredient type** (129-163): stable `[1.0,2.5,2.0,2.0,1.5]` sweet 2.0 no false peaks; moderate `[0.8,2.0,1.5,1.5,1.2]` sweet 1.5 peaks `[0.4,0.7]`; volatile `[0.5,1.5,1.0,1.0,0.8]` sweet 1.0 peaks `[0.3,0.5,0.7,0.9]`; legendary `[0.4,1.0,0.5,0.7,0.5]` sweet 0.5 peaks `[0.2,0.4,0.5,0.6,0.8]`. Speed bonus multiplies all durations by `(1 + speed_bonus)` (157-161). Stage >5 = explosion, locked quality 0 (178-188).
- **Quality-if-clicked-now** (227-290): `total_progress = (stage-1+progress)/5`; sine per cycle; amplitude `1.0` (1 osc) else `0.6 + 0.4*cycle/(osc-1)`; `base_fraction = min(0.45, 0.15 + (total/final_peak)*0.30)` where `final_peak = (osc-0.5)/osc`; `quality = (base + sin*amp*0.55) * max_quality`.
- **Per-ingredient max quality** = its vowel count / total vowels across inputs (equal split if zero vowels) (372-410) — sum of maxima = 100%.
- **Ingredient type assignment by difficulty tier** (446-479): common `[stable,stable,moderate]` … legendary `[volatile,volatile,legendary]`; extras by volatility thresholds 0.7/0.4/0.2.
- Explosion mid-game: `+0.10` progress, advance to next ingredient (558-571). Explosion at end(): loss `min(0.9, failure_penalty + 0.1)` (636-641).
- End: fail if `progress < 0.25` with `calculate_failure_penalty` loss (674-679); success uses `calculate_alchemy_rewards` (662-685); legacy ladder `<0.5 Weak(0.5/0.5), <0.75 Standard(0.75/0.75), <0.9 Quality(1.0/1.0), <0.99 Superior(1.2/1.1), ≥0.99 Perfect(1.5/1.25)` (687-724). Buff quality multiplies both mults by `(1+bonus)` (727-729). `earned_points = int(progress*100)`, max 100 (733-734).
- Potion stats: `potency = int(100*effect_mult)`, `duration = int(100*duration_mult)`, `quality = earned_points`; heal/damage effect types drop `duration` (1031-1057). Consumable vs transmutation + effect type from `AlchemyTagProcessor` (1046-1051).

### 5.4 Refining (`RefiningMinigame` / `RefiningCrafter`)
- Params from `calculate_refining_difficulty`: cylinder_count, timing_window, rotation_speed, allowed_failures, time_limit, multi_speed (refining.py:98-110). **Fixed angular window** `base_window_degrees = timing_window * rotation_speed * 360` computed once (114, 164) so INT slow-down doesn't shrink it.
- Cylinder init: random start angle, direction ±1; multi_speed: every 2nd ×0.7, every 3rd ×1.3; `speed = base / (1 + speed_bonus)` (178-199). Rotation `speed*360` deg/s (228-229).
- **Accept**: wraparound angular distance to target ≤ `base_window_degrees * 0.625` ("25% larger to fix sync", 253-261). Fail past `allowed_failures` ends game (277-278).
- Success result: `earned_points = aligned count`, `max_points = cylinder_count` (295-297); failure: loss via `calculate_failure_penalty` fallback 0.5, partial credit earned_points kept (310-330).
- Legacy hardcoded tier configs T1..T4 (138-151): time 45/30/20/15 s, cylinders 3/6/10/15, window 0.8/0.5/0.3/0.2 s, speed 1.0/1.3/1.6/2.0, failures 2/1/0/0.
- **Quantity→rarity upgrade (both instant & minigame)**: total input qty ≥4→+1, ≥16→+2, ≥64→+3, ≥256→+4 tiers, capped at legendary (531-543 instant, 685-699 minigame).
- **alloyQuality title proc** (minigame only): `quality = earned/max*100`; `quality_mult = (quality-50)/50`; `adjusted = clamp(alloy_bonus * (1+quality_mult), 0, 1)`; `random() < adjusted` → +1 rarity tier (702-722). Bonus fed from `character.titles.get_total_bonus('alloyQuality')` (game_engine.py:8927).
- Tag procs (crushing/grinding/purifying/alloying) via `RefiningTagProcessor.calculate_final_output` may add yield/quality (546-551, 724-731). Refining outputs use the `outputs[]` array format, no crafted stats (508-520, 663-674).

### 5.5 Engineering (`EngineeringMinigame` + puzzles)
- Params from `calculate_engineering_difficulty`: puzzle_count (min 2), grid_size, complexity, hints_allowed, time_limit, ideal_moves 6-8 (668-690). Time buff extends limit `*(1+bonus)` (657-659). Legacy: grid `3+tier`, hints `4-tier`, puzzles 2/2/3/4, ideal `min(8, 5+tier)` (697-718).
- Puzzle 0 is always `RotationPipePuzzle`, 1+ always `LogicSwitchPuzzle` (757-796) with difficulty by rarity tier.
- **RotationPipePuzzle**: connection map per piece/rotation (54-60); path gen biased 0.7 toward output (113); ideal path = Manhattan+1 (83-84); distractor fill `choice([1,2,2,3])` (143); scramble all non-cross pieces (154-157); solved = BFS reachability with mutual connections (222-285); efficiency = `min(1, ideal/actual)` (205-220).
- **LogicSwitchPuzzle** (lights-out): 4 modes (random→lit/dim, dim/lit→random) generated by exactly `max_moves` toggles on distinct cells (349-464); toggle flips cell + orthogonal neighbors (474-483); efficiency = `1.0 if moves≤ideal else exp(-(moves/ideal - 1))` (514-528); `reset()` restores initial grid (501-504).
- **Device stats**: base 100 each of durability/efficiency/accuracy/power; each solved puzzle adds `int(5 + 15*efficiency)` to the next stat round-robin (934-950).
- **Performance** = `completion*0.5 + avg_efficiency*0.3 + time_ratio*0.2` (time term only if finished before expiry; else `+0.1` if all solved) `- hints_used*0.05`, clamped 0-1 (952-965); +first_try_bonus if attempt 1 (967-970). `earned_points = int(performance*100)` (998-1001). `quality = mean(stats)/100` (996).
- **Abandon**: minigame's own `abandon()` claims 50% return (877-889), but the engine path uses the crafter's **tier-scaled** return `1 - {common .30, uncommon .45, rare .60, epic .75, legendary .90}` (1226-1253) — the two disagree; the crafter's table is what actually credits the inventory. Preserve the crafter behavior; flag the message mismatch.

### 5.6 Enchanting (`SpinningWheelMinigame` / `EnchantingCrafter`)
- Wheel = 20 slices, 3 spins, start currency 100 (75-94). **Spin multipliers**: spin1 `{green 1.2, grey 1.0, red 0.66}`, spin2 `{1.5, 0.95, 0.5}`, spin3 `{2.0, 0.8, 0.0}` (90-94).
- Wheel composition from difficulty (`green_slices`, `red_slices`, grey = remainder; 104-121). Per-spin drift: green `max(3, base-spin)`, red `min(12, base+spin)`, combined cap 17 leaving grey (157-201). Legacy tiers: green 10/8/7/5, red 3/5/7/9 (128-147).
- Result slice `randint(0,19)` chosen at spin start (294); winnings `int(bet*mult)`; currency = currency − bet + winnings (299-312).
- **Efficacy** = `clamp((currency-100)/100 * 50, ±50)%` → decimal ±0.5 (357-366). **Performance** = `clamp(currency/200, 0, 1)` (370) + first-try bonus (372-375). Always `success: True` (399).
- **Final enchant bonus** = `int(base_bonus * rarity_mult * (1 + efficacy))` where `base_bonus = max(5, difficulty_points/3)` and rarity_mult `{common 1.0, uncommon 1.1, rare 1.2, epic 1.35, legendary 2.0}` (1313-1332). Applied to gear via `target_item.apply_enchantment(id, name, recipe.effect)` (1351-1355) or emitted as a new accessory (1377-1389).
- Header comment says "REQUIRED minigame, cannot be skipped" (enchanting.py:7,27) while `craft_instant`'s docstring says "Enchanting does NOT have minigames - it's basic craft only" (1174-1180). Both code paths exist and are reachable from the engine (7033 / 4272). Preserve both; the docstrings lie in opposite directions.

### 5.7 Fishing (`FishingMinigame` / `FishingManager`) — config-driven via `Definitions.JSON/fishing-config.JSON` (defaults fishing.py:75-105)
- Defaults: pond 500×400 margin 50; base ripples 8, target radius 40, expand 80 px/s, tolerance 15, spawn delay 1.5 s, max active 2; scoring tolerances 5/10/15 → 100/75/50, min partial 25; success `hit_rate ≥ 0.5` and `avg ≥ 40`; quality tiers `.9/.75/.6/.4` → mult `1.5/1.3/1.15/1.0/0.8`; luck −0.1 ripple/pt (min 4, max 15); STR +0.5 tolerance/pt (cap 30); rod −0.15 speed/tier (floor 0.55); tier scaling +0.25 ripples, +0.2 speed per tier; XP 100/400/1600/6400; durability success 1.0, fail ×2.
- Difficulty calc (304-383): `effective_luck = luck*(1+title_luck)`; ripples = clamp(min..max, `(base − eff_luck*0.1) * (1+(tier-1)*0.25)`); tolerance = `base + eff_str*0.5 + base*title_accuracy` cap 30 with `eff_str = STR*(1+empower)`; speed mult = `max(0.3, (rod_mult − efficiency*0.75) * spot_mult * (1 − (quicken+title_speed)*0.5))` with rod_mult floored 0.55; spawn delay `clamp(0.8, 2.5, 1.5/rod_mult)`; `max_radius = target*2.5`.
- Click scoring (466-550): clickable radius = `max(current_radius, target_radius)`; ring distance ≤5→100 (perfect), ≤10→75, ≤15→50, ≤tolerance→`max(25, int(50*(1-d/tolerance)))`, else miss 0. Ring past max_radius = miss (435-440).
- End (552-632): `performance = min(1, (avg/100)*hit_rate*(1+elevate+rare_fish))`; `bonus_mult *= (1 + title_yield + enrich)` (599-600); `xp = int(base_xp * bonus_mult)` if success else 0 (base fallback `100*4^(tier-1)`, 605-606).
- `process_result` (769-868): loot qty `max(1, int(qty * (1+luck*0.02) * bonus_mult))` (797-801); depletes spot (807-809); durability loss × `character.stats.get_durability_loss_multiplier()` × Unbreaking `(1-value)` (838-850); records stat_tracker tool events (852-857).
- **can_fish gates** (701-731): fishing-spot type, rod equipped, `rod.tier ≥ spot.tier`, and `durability_current > 0` — see Risks: this "rod is broken" gate at fishing.py:727-729 conflicts with the project-wide "0% durability = 50% effectiveness, never breaks" sacred rule.

---

## 6. Event Topics (GameEventBus)

**Zero publishes/subscribes inside `Crafting-subdisciplines/`** (repo grep: no `publish(` in the folder). The caller publishes on this subsystem's behalf:

| Topic | Where | Payload |
|---|---|---|
| `ITEM_CRAFTED` | game_engine.py:8988-8999, **minigame-success path only** (the instant-craft path at 7035-7094 does not publish) | recipe_id, output_id, discipline, quality, station_tier, position_x/y, source="crafting" |
| `FISH_CAUGHT` | game_engine.py:11919-11936 | fish_id (first loot), total quantity, tier, rarity, position_x/y |

Port note: keep publication in glue (the C# engine layer), not in the pure assembly — matches the Python shape and keeps the sidecar IPC boundary (WMS consumes these) in one place. Preserve the asymmetry (instant craft silent) unless deliberately changed.

---

## 7. Content JSON Consumed (reused verbatim; loaders ported)

Each crafter has its **own bespoke loader** (`open` + `json.load` over a cwd-robust candidate list via `core.paths.get_resource_path`, then relative fallbacks) — duplicating `RecipeDatabase`/`PlacementDatabase` which load the same files for the UI. Both must agree on `recipeId` (see Risks #1).

| File(s) | Loader | Filter |
|---|---|---|
| `recipes.JSON/recipes-smithing-1.json`, `-2`, `-3`, `recipes-tag-tests.JSON` | smithing.py:538-589 | `stationType == 'smithing'` (default smithing) |
| Update-N packages: `<update>/​*recipes*smithing*.{JSON,json}` discovered via `updates_manifest.json` at project root | smithing.py:591-647 | none — **only smithing does Update-N loading**; the other four crafters do not (asymmetry to either replicate or unify) |
| `placements.JSON/placements-smithing-1.JSON` | smithing.py:649-672 (stores `placementMap`) | dead on game path (see §2) |
| `recipes.JSON/recipes-alchemy-1.json`, `recipes-tag-tests.JSON` | alchemy.py:800-837 | `stationType == 'alchemy'` |
| `placements.JSON/placements-alchemy-1.JSON` | alchemy.py:840-863 | dead on game path |
| `recipes.JSON/recipes-refining-1.json`, `recipes-tag-tests.JSON` | refining.py:378-415 | `stationType == 'refining'` |
| `placements.JSON/placements-refining-1.JSON` | refining.py:417-440 | dead on game path |
| `recipes.JSON/recipes-engineering-1.json` | engineering.py:1059-1084 | none (loads all recipes in file) |
| `placements.JSON/placements-engineering-1.JSON` | engineering.py:1087-1110 | dead on game path |
| `recipes.JSON/recipes-enchanting-1.json`, `recipes-adornments-1.json` | enchanting.py:1082-1113 | none |
| `placements.JSON/placements-adornments-1.JSON` | enchanting.py:1115-1142 (stores `placementMap`) | dead on game path |
| `items.JSON/items-materials-1.JSON` (materialId→rarity) | rarity_utils.py:52-68 (`Path(__file__).parent.parent`-relative) | — |
| `Crafting-subdisciplines/rarity-modifiers.JSON` | rarity_utils.py:70-80 | — |
| `Definitions.JSON/fishing-config.JSON` | fishing.py:59-73 (with full hardcoded default fallback 75-105) | — |
| Simulator only: assorted recipes/items lists | crafting_simulator.py:186-201, 344-361, 393-400 | dev harness, not ported |

Recipe input schema tolerance: every consumer accepts `itemId` **or** `materialId` per input (e.g. smithing.py:698, alchemy.py:882, refining.py:466, engineering.py:1129, enchanting.py:1161); refining also accepts `outputs[]` array vs `outputId/outputQty` (refining.py:508-520). The C# recipe model must preserve both spellings — content JSON is frozen.

---

## 8. Persistent State

**This subsystem contributes nothing directly to save/load.** `systems/save_manager.py` has zero references to minigame or fishing state (grep verified). Specifics:
- Active minigames are ephemeral; double-ESC abandons with no persistence and no material loss (game_engine.py:709-726).
- `EngineeringMinigame.save_progress()/load_progress()` (engineering.py:891-913) is designed-but-dead: never called, `load_progress` is `pass`. Do not port; note in feature-parity checklist as intentionally absent.
- What *does* persist flows through other subsystems: crafted items + rarity + `stats` dict land in inventory/equipment (game_engine.py:7052 `add_crafted_item_to_inventory`; equipment save owns them); enchantments persist on `EquipmentItem`; rod durability mutation (fishing.py:850) persists via equipment save; invented recipes/placements persist via `RecipeDatabase`/`PlacementDatabase` (LLM subsystem, doc 0X).
- `rarity_system.debug_mode` is runtime-only (F1).

---

## 9. 3D Notes (what necessarily changes going 2D→3D)

1. **The minigames themselves do not go 3D** — they are Godot `Control` overlays. All internal coordinates (hammer bar 0-400, wheel angles, pond x/y, puzzle grids) are already screen/abstract-space, not world-space. No hitbox/facing/distance math inside the subsystem needs 3D conversion.
2. **World-pause contract**: Python freezes the entire world while a minigame runs (game_engine.py:8431-8558). In 3D Godot decide explicitly: `SceneTree.paused` with the minigame CanvasLayer on `PROCESS_MODE_ALWAYS` reproduces current behavior. If the 3D world is ever allowed to keep running, enemy safety during crafting becomes a new design question — current game guarantees invulnerable crafting.
3. **Entry points move to 3D interaction**: opening a station / starting fishing is proximity+click on a world object today (outside this subsystem); in 3D that becomes raycast/Area3D interaction. `FishingManager.can_fish(resource, character)` (fishing.py:701-731) keeps working if the 3D fishing spot exposes `.tier`, `.resource_type`, `.get_loot()`, `.depleted`, `.current_hp`.
4. **Event payload positions**: `ITEM_CRAFTED`/`FISH_CAUGHT` carry `position_x/y` (game_engine.py:8996-8997, 11932-11933) consumed by the Python WMS sidecar. In 3D, map `(x, z)` (Godot ground plane) into these fields so the sidecar's geographic registry keeps working — decide once, project-wide.
5. **Pond click mapping**: fishing converts screen clicks to pond-local coords via a stored rect (game_engine.py:11686-11688, 2515). In Godot this is free (`Control` local coordinates), but ripple positions/radii must scale if the panel size differs from 500×400 — scale input tolerance (`hit_tolerance`, in px) by the same factor or keep a fixed-size virtual canvas (recommended: virtual 500×400 canvas inside a `SubViewport`/scaled Control to keep all px constants bit-exact).
6. **Camera assumptions**: none inside the subsystem. The overlay must capture mouse focus so the 3D camera/attack input (game_engine.py:8470-8531 runs only when no minigame) stays inert — replicate with input consumption on the overlay layer.

---

## 10. Godot Mapping

### Pure-logic assembly `Game1.Core` (namespace `Game1.Core.Crafting`) — testable via `dotnet test`, no Godot references
- `interface ICraftingMinigame { void Start(); void Update(double dt); MinigameState GetState(); MinigameResult? Result { get; } }` — mirrors the duck-typed Python contract (§2).
- `SmithingMinigameLogic`, `AlchemyMinigameLogic` (+ `AlchemyReaction`), `RefiningMinigameLogic`, `EngineeringMinigameLogic` (+ `IPuzzle`, `RotationPipePuzzle`, `LogicSwitchPuzzle`), `SpinningWheelMinigameLogic`, `FishingMinigameLogic` (+ `Ripple` record). Each exposes the explicit input methods (`HandleFan/HandleHammer`, `Chain/Stabilize`, `HandleAttempt`, `HandleAction(row,col)`, `PlaceBet/SpinWheel/AdvanceSpin`, `HandleClick(x,y)`), plus `ApplyIntelligenceModifiers(IntTuning)` replacing the game_engine.py:4322-4389 attribute-poking.
- `abstract class CrafterBase` — **collapses the 5-way duplicate-method pattern** (known tech debt): identical or near-identical `load_recipes` (smithing.py:538 / alchemy.py:800 / refining.py:378 / engineering.py:1059 / enchanting.py:1082), `load_placements`, `can_craft` (698-709 / 869-893 / 446-477 / 1116-1140 / 1148-1172), `craft_instant` preambles, `get_recipe`, `get_all_recipes`, `get_placement`. Virtual hooks: `StationTypeFilter`, `ShapeInstantResult`, `ShapeMinigameResult`, `CreateMinigame`. Concrete: `SmithingCrafter`, `AlchemyCrafter`, `RefiningCrafter` (outputs-array + 4:1 rarity upgrade + alloy proc), `EngineeringCrafter` (abandon table), `EnchantingCrafter` (enchant application via an `IEnchantable` seam instead of a direct `EquipmentItem` call).
- `RaritySystem` (constructor-injected material-rarity map + modifier table; `DebugMode` property replaces the module global) + `static RarityLadder` (`Tiers`, `Index`, `At` — rarity_utils.py:27-38).
- `FishingConfig` POCO deserialized from `Definitions.JSON/fishing-config.JSON` with the code defaults (fishing.py:75-105) as fallback; `FishingDifficulty` calculator; `FishingOutcome` pure result; `FishingRewardModel` (loot mult, durability loss) computed pure, applied by glue.
- **RNG**: inject `Random` (seedable) into every class using `random.*` (alchemy visuals, refining cylinder init + alloy proc, engineering generators, wheel, fishing spawn) — required for deterministic tests.
- Depends on (must exist in the assembly first): `DifficultyCalculator`, `RewardCalculator`, `CraftingTagProcessors`, `CraftedStatsGenerator`, `RecipeDatabase`/`PlacementDatabase` ports (owned by the core/data inventory docs).

### Engine glue (Godot project)
- `MinigameHost` (autoload or child of GameHud): owns `ActiveMinigame`, routes `_process(delta)` → `Update`, polls `Result`, pauses world (`get_tree().paused`), replicates overlay-block gating, and on completion runs the **engine-side completion contract**: build inv snapshot → `crafter.CraftWithMinigame` → real consumption via `RecipeDatabase.ConsumeMaterials` / `ConsumeMaterialsPartial(lossFraction)` → stat tracking → publish `ITEM_CRAFTED` over the event bus/IPC (mirrors game_engine.py:8870-9109).
- One `Control` scene per discipline (`SmithingPanel.tscn`, `AlchemyPanel.tscn`, `RefiningPanel.tscn`, `EngineeringPanel.tscn`, `EnchantWheelPanel.tscn`, `FishingPondPanel.tscn`), each binding to the state record each frame — direct replacement for `_render_*_minigame` (game_engine.py:9113-11868). Wheel spin easing and reaction-bubble glow move here (Tween/shader), fed by logic timestamps.
- `FishingInteractable` (Area3D on fishing spots) → `FishingManager` glue that adapts `Character`/rod/resource to the pure fishing logic and applies durability/loot/XP results.
- Input: keyboard/mouse handled by the panels (actions: `craft_fan`, `craft_chain`, `craft_stabilize`, `craft_attempt`, ESC-ESC abandon with the 1500 ms double-press window, game_engine.py:714-715).

### What is NOT in this subsystem (boundary notes)
- The **grid placement / recipe-match UI** (placing materials on the station grid before the minigame) lives in `core/interactive_crafting.py` (`InteractiveBaseUI` + per-discipline subclasses) — covered by the core inventory doc. This folder's `placements` dicts are dead on the game path (§2).
- `difficulty_calculator` / `reward_calculator` formulas are core/ property; this doc cites only what the minigames consume.

---

## 11. Port Complexity, Ordering, Risks

### Complexity
| Unit | Size | Why |
|---|---|---|
| `CrafterBase` + 5 crafters | **M** | Mostly mechanical; the subtle parts are the material-consumption contract and refining's rarity/proc pipeline |
| Smithing logic | **M** | Binned zones + exp temp falloff; wall-clock→dt conversion |
| Alchemy logic | **L** | Oscillation math, vowel-driven hidden values, explosion flow — most formula-dense file |
| Refining logic | **M** | Angular window math + wraparound; alloy proc |
| Engineering logic | **L** | Two puzzle generators (path gen w/ backtracking, lights-out inverse gen), efficiency scoring, wall-clock timer |
| Enchanting wheel | **M** | Simple state machine; separating animation from resolution |
| Fishing | **M** | Config plumbing + heavy Character/title/buff bonus extraction seam |
| Rarity utils | **S** | |
| Godot panels ×6 | **L** (aggregate) | Pure UI rebuild; the state contracts make it mechanical |
| Overall | **L/XL** aggregate | ~6.8k live logic LOC after dropping dead code (~2.3k simulator + ~700 dead classes) |

### Ordering constraints (must exist first)
1. `core` ports: `DifficultyCalculator` + `RewardCalculator` (every minigame ctor and `end()` calls them; the ImportError fallbacks in Python should NOT be ported — make the dependency hard), `CraftingTagProcessors`, `TagDebug` (or drop debug hooks).
2. `data` ports: `RecipeDatabase` (+ `consume_materials`/`consume_materials_partial` semantics recipe_db.py:166-256), `MaterialDatabase` (rarity source), `EquipmentDatabase` + `CraftedStatsGenerator` (smithing/engineering output stats), `EquipmentItem.ApplyEnchantment`.
3. `rarity_utils` + `rarity-modifiers.JSON` loading.
4. Then minigame logic classes (independent of each other; parallelizable), then crafters, then Godot panels, then fishing world interaction.
5. `tests/crafting/test_no_crash.py` scenarios re-expressed as dotnet tests early — they exercise ctor + loaders + can_craft against real content JSON.

### Top risks / gotchas (each verified in code)
1. **Dual recipe loading**: crafters keep their own `self.recipes` parsed from the same JSON that `RecipeDatabase` loads for the UI. A recipe visible in the UI but missed by the crafter's loader makes `create_minigame` return `None` on click — this bug class already happened (cwd bug note smithing.py:539-545). **Port fix**: crafters query the single ported `RecipeDatabase`; delete the private loaders. Also unify the smithing-only Update-N loading (smithing.py:591-647) at the database layer.
2. **Material consumption double-charge**: crafters mutate a throwaway dict; the engine charges the real inventory afterward (success 100% via `consume_materials`, failure `loss_fraction` 30-90% via `consume_materials_partial`; game_engine.py:8944-8973, recipe_db.py:166-209). A naive port that lets crafters touch real inventory will double-consume — the exact bug the 2026-07 audit fixed in reverse. Make the C# crafter API take a read-only inventory snapshot and *return* a consumption plan.
3. **Hidden coupling — INT stat mutation**: game_engine.py:4322-4389 pokes `HAMMER_SPEED`/`TEMP_DECAY`/`time_limit`/`rotation_speed`/`speed_bonus` on constructed minigames via `hasattr`, driven by `stats-calculations.JSON`. Silent breakage risk if C# fields are renamed — replace with an explicit modifier API and a test per discipline.
4. **Clock semantics**: smithing uses `pygame.time.get_ticks()` (100 ms decay ticks, smithing.py:210-219), engineering and the enchant wheel use `time.time()` (engineering.py:737-755, enchanting.py:227-247). Wall clocks keep running during pauses/overlays; dt does not (update is skipped while the metadata overlay blocks, game_engine.py:8556-8558). Converting to dt accumulation *changes* engineering's effective timer during overlays — accept the (more correct) change, note it in the parity checklist.
5. **Vowel-count mechanics are content-coupled**: alchemy's hidden oscillation counts and per-ingredient max qualities derive from vowel counts of material-id strings (alchemy.py:78-105, 372-410). Any C# string handling difference (or future non-ASCII ids) changes gameplay. Port with byte-exact ASCII vowel counting and add golden tests over the full `items-materials-1.JSON` id set.
6. **Sacred-constant tension — fishing rod "broken" gate**: `can_fish` refuses at `durability_current <= 0` (fishing.py:727-729), contradicting the project rule "0% durability = 50% effectiveness, never breaks". This is live Python behavior. Decision needed: port as-is for parity (recommended, then flag to design) — do not silently "fix" either direction.
7. **Contradictory enchanting docs**: header says minigame REQUIRED (enchanting.py:7,27); `craft_instant` docstring says enchanting has NO minigames (1174-1180); both paths are reachable (game_engine.py:7033, 4266-4272). Port both; trust neither comment.
8. **Engineering abandon mismatch**: minigame `abandon()` reports 50% return (engineering.py:877-889); crafter applies tier-scaled 30-90% penalty returns (1226-1253). The crafter wins at runtime. Preserve, and fix the player-facing message in the Godot panel.
9. **Python `random` → `System.Random`**: `random.shuffle` (wheel), `random.choice` weights (`[1,2,2,3]` distractor fill, engineering.py:143), `random.uniform` — behavior-compatible but sequence-incompatible. No gameplay depends on sequences, but golden tests must inject seeds and assert distributions/invariants, not sequences.
10. **`get_state()` is the render ABI**: six render functions consume loosely-typed dicts incl. nested puzzle states and per-cylinder `last_attempt_angle` (refining.py:332-356). Type these as C# records *first* and diff against Python output for a few scripted runs — cheapest way to catch dropped fields before UI work starts.
11. **Enchanting result missing `earned_points`**: `SpinningWheelMinigame.complete()` result has no `earned_points/max_points` keys (enchanting.py:398-410) unlike all other disciplines; downstream `generate_crafted_stats` defaulting handles it. Keep the asymmetry or normalize deliberately.
12. **Instant craft ≠ event**: `ITEM_CRAFTED` publishes only on the minigame path (game_engine.py:8988) — instant crafts are invisible to the WMS sidecar. Parity says keep; flag to design.

# 11 — Sacred Constants Sweep + Conformance Mining Guide

**Scope**: (A) the CONSTANTS LEDGER — every balance constant and formula found in code under
`Game-1-modular/`, with exact values, `file:line`, and env overrides; (B) the CONFORMANCE MINING
GUIDE — what `Game-1-modular/tests/` and `crux-foundry/` pin, which tests are portable as C# xunit
conformance tests, and how crux-foundry becomes the cross-engine behavioral oracle.

**Ground rule honored**: every load-bearing claim below cites code. Where docs (CLAUDE.md,
docstrings) disagree with code, the discrepancy is called out explicitly — **code wins**.

All paths are relative to `c:/Users/vipVi/PycharmProjects/Game-1/` unless absolute.

---

## 1. File table

Disposition legend: `port-to-C#` (logic reimplemented in the pure-logic assembly),
`port-as-test` (behavior pinned in the C# conformance test project), `engine-replaces`
(Godot supersedes), `stays-python-sidecar` (WMS/WNS/WES boundary), `oracle-tool`
(stays Python; consumed as golden-file generator), `drop-dead-code`.

### 1a. Constants-bearing source files

| File | ~LOC | Responsibility (constants-relevant) | Disposition |
|---|---|---|---|
| `Game-1-modular/Combat/combat_manager.py` | 2,622 | All three player damage paths, enemy→player damage, crit composition, EXP rewards, combat config defaults, env knobs `CRUX_STR_DMG_PER_POINT` / `CRUX_LCK_CRIT_PER_POINT`, seeded RNG | port-to-C# (decompose: DamageCalculator / CritComposer / CombatConfig / EnemyAttackResolver) |
| `Game-1-modular/entities/components/weapon_tag_calculator.py` | 173 | Pure static tag→bonus table (2H ×1.2, versatile ×1.1, fast +0.15, precision +0.10, reach +1.0, armor_breaker 0.25, crushing 0.20) | port-to-C# (verbatim; already pure) |
| `Game-1-modular/entities/components/stats.py` | 178 | 6-stat per-point scaling, JSON-driven with hardcoded fallbacks, durability-loss/carry multipliers, effective-luck composition | port-to-C# (verbatim; already pure) |
| `Game-1-modular/entities/components/leveling.py` | 49 | EXP curve `200 × 1.75^(lvl-1)`, max 30, cascading level-ups, 1 stat point/level | port-to-C# (verbatim; already pure except event publish) |
| `Game-1-modular/entities/character.py` | 2,593 | VIT regen wiring, gathering damage/loot luck math, AGI attack/move speed, shield reduction, get_effective_luck, durability drain | decompose (constants → pure assembly; entity shell is a separate subsystem doc) |
| `Game-1-modular/data/models/equipment.py` | 360 | Durability→effectiveness curve incl. the 50% floor; damage/defense effective-stat math | port-to-C# (verbatim; pure dataclass) |
| `Game-1-modular/core/difficulty_calculator.py` | 808 | Tier points, difficulty bands, per-discipline difficulty formulas + minigame parameter interpolation | port-to-C# (verbatim; pure module, one MaterialDatabase lookup) |
| `Game-1-modular/core/reward_calculator.py` | 628 | Quality bands, reward multiplier 1.0–2.5, failure loss 30–90%, first-try bonuses | port-to-C# (verbatim; pure) |
| `Game-1-modular/entities/status_effect.py` | 826 | Default magnitudes/durations for all status effects | port-to-C# (constants + tick logic) |
| `Game-1-modular/entities/components/skill_manager.py` | 1,168 | Buff magnitude tables (empower/quicken/fortify/pierce), restore tables, mana/cooldown application, class-affinity application | port-to-C# (decompose) |
| `Game-1-modular/data/databases/skill_db.py` | ~600 | Mana-cost / cooldown enum→number fallbacks (60 mana, 300 s) | port-to-C# (loader subsystem; constants noted here) |
| `Game-1-modular/data/models/classes.py` | ~60 | Class skill-affinity: +5%/matching tag, cap +20% (the "class max 1.2" sacred constant) | port-to-C# (verbatim) |
| `Game-1-modular/systems/class_system.py` | 100 | Tag→tool bonus table (JSON-driven w/ fallback), class bonus lookup | port-to-C# |
| `Game-1-modular/Combat/enemy.py` | 1,426 | Loot chance text→float map, enemy DB load (sacred + generated hostiles) | port-to-C# (loader + loot roll; AI elsewhere) |
| `Game-1-modular/systems/llm_item_generator.py` | 1,531 | **Only** the sanitizer portion (lines ~939–1035): invented-item stat ceilings 60/120/240/480, tier clamp, id-collision guard | sanitizer logic **port-to-C#** (defense-in-depth at the IPC boundary); LLM client itself stays-python-sidecar |
| `Game-1-modular/core/game_engine.py` | ~11,700 | Constants embedded: INT minigame-difficulty application (4303–4380), invented-item stat derivation w/ TIER_MULTIPLIERS + BASE_DURABILITY 250 (5506–5534), quest-turn-in affinity call site (~1628) | decompose (these blocks move to pure calculators; the engine itself is engine-replaces) |
| `Game-1-modular/Definitions.JSON/stats-calculations.JSON` | n/a (content) | Master stat/tier/item formula config: `tierMultipliers` 1/2/4/8, `globalBases`, `characterStatModifiers` (all six stats) | reused **verbatim** (content JSON; port the loader) |
| `Game-1-modular/Crafting-subdisciplines/smithing.py` (+refining/alchemy) | 909/826/1,070 | Failure-loss application via `calculate_failure_penalty` (smithing.py:817, refining.py:313, alchemy.py:994) | logic ports with minigame subsystem; constants noted here |
| `Game-1-modular/world_system/living_world/factions/faction_system.py` | ~700 | Affinity clamp −100..100 on every write | stays-python-sidecar (contract documented in §5.11) |
| `Game-1-modular/world_system/living_world/factions/quest_tool.py` | 196 | Quest turn-in affinity deltas (5/4/2, max 3 tags) + hardcoded example quest outcome map | stays-python-sidecar (game triggers over IPC) |
| `Game-1-modular/world_system/wns/affinity_resolver.py` | ~400 | WNS AffinityShift magnitude cap ±25.0 | stays-python-sidecar |
| `Game-1-modular/world_system/content_registry/balance_validator_stub.py` | ~230 | Loads `tierMultipliers`/`globalBases` from stats-calculations.JSON to sanity-check generated content | stays-python-sidecar (WES-side gate); C# side gets its own sanitizer (see llm_item_generator row) |

### 1b. Test files (unit tree, `Game-1-modular/tests/`)

| File | tests | Nature | Disposition |
|---|---|---|---|
| `test_progression_fixes.py` | 6 | pure (LevelingSystem + failure-loss) | **port-as-test** (EXP cascade + 30–90% loss) |
| `test_enchantments.py` | 8 | pure (isolated enchant logic, mock entities, "does NOT require pygame" per its docstring) | port-as-test |
| `test_status_effects.py` | 5 | pure (status effect apply/tick/expire with mock entity) | port-as-test |
| `test_knockback.py` / `test_player_knockback.py` | 2/2 | pure-ish (effect executor math) | port-as-test |
| `test_geometry_patterns.py` | 8 | pure (chain/cone/circle/beam target selection) | port-as-test (critical for 3D re-derivation, §9) |
| `test_class_tags.py` | 4 | pure (class tag bonuses) | port-as-test |
| `test_tag_system.py` / `test_tag_json_load.py` | 2/1 | pure (tag registry + JSON load) | port-as-test |
| `test_invented_item_sanitizer.py` | 6 | pure (ceilings 60/120/240/480, tier clamp, id collision) | **port-as-test** (guards the IPC boundary) |
| `test_invented_items_integration.py` | 5 | pure-ish (generator plumbing w/ mock backend) | partially port (C#-side parse/sanitize only) |
| `test_affinity_long_horizon.py` | 9 | pure (faction store, quest turn-in deltas, WNS bridge) | stays-python (sidecar suite); mirror the *IPC contract* in C# |
| `test_crafting_consumption.py`, `crafting/test_*` (4 files) | 7 | pure (recipe consumption, rarity logic, metadata) | port-as-test |
| `test_chain_harvest.py` | 1 | pure (AoE gathering) | port-as-test |
| `test_enemy_abilities_loading.py`, `test_chunk_density_spawn.py`, `test_chunk_template_db.py` | 1/4/23 | pure (loaders) | port-as-test with loader subsystem |
| `test_progression…/save/test_save_system.py`, `save/test_default_save.py` | 3/1 | pure (save round-trip on real SaveManager w/o engine) | port-as-test with save subsystem |
| `test_schema_validator.py`, `test_updaten_reload_remerge.py`, `test_database_reload_e2e.py` | 11/2/15 | pure (content pipeline) | split: content-validation ports; WES reload stays sidecar |
| `test_npc_speechbank.py`, `test_phase0-7*`, `test_context_budgets.py`, `test_wms_wns_layer_correspondence.py`, `test_graceful_degrade_observability_bridge.py`, `test_llm_generation_cancel.py` | ~120 | pure but **sidecar-domain** (WNS/WES/WMS) | stays-python-sidecar |
| `test_image_system.py`, `test_npc_agent_wiring.py`, `test_quest_log_overlay.py` | 1/11/7 | ENGINE (pygame surfaces / engine boot / UI overlay) | engine-replaces (behaviors → Godot feature-parity checklist) |

### 1c. Integration playtest suite (`Game-1-modular/tests/integration/`) — all boot the REAL GameEngine under SDL-dummy

| File | tests | What it pins | Disposition |
|---|---|---|---|
| `conftest.py` | – | Session-scoped engine boot, SDL dummy, save-path redirect, 1280×720 pin (conftest.py:1–30) | re-create as a **Godot headless harness** (see §10) |
| `harness.py` | – | `PlaytestHarness`: real event-queue input, `tick(dt)` via back-dated `last_tick` (harness.py:27–41), `melee_swing` → action path (133–146), `craft` → real `_complete_minigame` (158–185), `seed_all` (104–112) | re-create in Godot (engine glue); the *API shape* should be preserved so crux-foundry drivers translate 1:1 |
| `test_00_boot` … `test_08_test_village` | 27 | Boot, crafting E2E, combat E2E, save/load, chests/NPC, UI, chunk streaming, content xref, village | engine-replaces → re-derive on Godot harness (test_07_content_xref is pure and ports directly) |
| `test_09_determinism.py` | 2 | Two-RNG-source determinism contract (see §B.3) | **re-derive** in Godot (contract, not code) |
| `test_10_capture.py` | 1 | melee_swing feeds StatTracker capture | re-derive |
| `test_11_crux_foundry.py` | 1 | F4 regression guard: high LCK ⇒ crits on action path | **port-as-test** (pure once DamageCalculator is a class) |
| `test_12_combat_conformance.py` | 8 | THE damage-pipeline conformance suite (F3/F5/F6/F8, VIT regen, INT elemental, DEF armor-eff, 75% cap, crit ×2) | **port-as-test — highest priority** (see §B.2) |

### 1d. crux-foundry (deterministic hermetic playtester, `crux-foundry/`)

| File | LOC | Responsibility | Disposition |
|---|---|---|---|
| `runner.py` | 276 | The run unit: hermetic engine boot (`GAME1_HERMETIC=1`, isolated save dir), persona build via real APIs, fixed-compose gauntlet (seed 20260706), capture → `result.json` (schema v1) | **oracle-tool** (keep running against Python build); Godot needs a twin runner speaking the same result.json schema |
| `scoring.py` | 33 | Pure progression score (+100/level, +20/skill, +40/title, +5/discovery, tier-scaled gathering, 15/10/5 diminishing crafting) | **port-to-C#** (trivially pure; identical totals = cheap cross-engine check) |
| `viability_report.py` | 87 | Persona × seeds aggregation; viability = mean(kills)/size − 0.05·mean(deaths); spread verdict | oracle-tool (reads result.json — engine-agnostic once Godot emits the schema) |
| `optimizer.py` | 97 | Grid-search a `CRUX_*` knob to minimize viability spread; detects wiring-vs-tuning bugs | oracle-tool (same) |
| `life_runner.py` | 191 | 8-day varied life → WMS chronicle extraction | stays-python (depends on WMS sidecar; long-term: Godot drives sidecar over IPC) |
| `loop_runner.py` | 160 | Full loop craft→fight→level persona; makes score meaningful | oracle-tool; re-derive driver on Godot harness |
| `batch.py` / `run_shard.py` / `crux_job.pbs` | 81/55/– | Process-per-run fan-out; PBS array shard; `CRUX_RUN_TIMEOUT_S` (default 120 s, run_shard.py:20) | oracle-tool (engine-agnostic subprocess shape) |
| `smoke_run.py` | 143 | Local E2E spine check | oracle-tool |
| `test_scoring.py` | 66 | Pure unit tests for scoring | **port-as-test** with scoring.py |
| `SCORING.md`, `METHODOLOGY.md`, `DETERMINISM_LEDGER.md`, `FINDINGS.md`, `SHIP_READINESS_REPORT.md`, `AGENT_DESIGN.md` | docs | Determinism ledger D1–D9, findings F1–F20, suite totals (1,219 passed / 0 failed, SHIP_READINESS_REPORT.md:14) | keep as reference; DETERMINISM_LEDGER is the checklist to re-verify on Godot |

**Files covered by this doc: ≈ 90** (22 constants-bearing sources + 55 test files + 13 crux-foundry files/docs).
**In-scope LOC estimate: ≈ 15,000** (constants-relevant slices of the sources + the whole test/foundry trees; the full files the slices live in total ~29k).

---

## 2. Public surface (what other subsystems actually call)

Constants are consumed through these entry points — these are the API signatures the C# pure
assembly must expose:

| Symbol | Defined | Called by |
|---|---|---|
| `CombatManager.player_attack_enemy_with_tags(enemy, tags, params, skip_visual, skip_los)` | combat_manager.py:1449 | action-combat hit resolution `game_engine._ac_process_hit` (per harness.py:139–141); skills via `skill_manager` combat path; crux runner via `harness.melee_swing` (harness.py:133) |
| `CombatManager.player_attack_enemy(enemy, hand)` | combat_manager.py:884 | legacy click-attack path; `harness.attack` (harness.py:128–131) |
| `CombatManager._player_crit_chance(weapon_tags)` | combat_manager.py:857 | all three attack paths (766, 1000, 1678) — single source of truth (F3) |
| `CombatManager._calculate_exp_reward(enemy)` | combat_manager.py:2200 | kill handling on every path (811, 1768) |
| `CombatManager.seed_rng(seed)` | combat_manager.py:198 | `PlaytestHarness.seed_all` (harness.py:110–112) — determinism contract |
| `CharacterStats.get_bonus / get_flat_bonus / get_effective_luck / get_durability_loss_multiplier / get_carry_capacity_multiplier` | stats.py:111–178 | character.py (gathering 1060, luck 2357, durability 1108), renderer tooltips |
| `reload_stat_config()` | stats.py:92 | database_reloader + test fixtures (designer hot-reload) |
| `LevelingSystem.add_exp(amount, source, character)` | leveling.py:15 | combat kills (combat_manager.py:812, 1769), quest rewards, crux `apply_build` (runner.py:139) |
| `WeaponTagModifiers.*` (static) | weapon_tag_calculator.py:15–128 | combat_manager.py:936/1624; equipment tooltips |
| `EquipmentItem.get_effectiveness()` | equipment.py:49 | character harvest (character.py:1052), weapon/armor effective stats (equipment.py:115, 143) |
| `calculate_{smithing,refining,alchemy,engineering,enchanting}_difficulty(recipe)` | difficulty_calculator.py:290/329/400/553/630 | `game_engine` minigame setup; crafting simulator |
| `calculate_max_reward_multiplier / get_quality_tier / calculate_failure_penalty / calculate_material_loss / first_try_bonus` | reward_calculator.py:81/107/497/522/65 | minigame completion in each `Crafting-subdisciplines/*.py` (e.g. smithing.py:817, refining.py:313, alchemy.py:994) and `game_engine.py:8944–8951` |
| `ClassDefinition.get_skill_affinity_bonus(skill_tags)` | classes.py:33 | skill_manager.py:316/944 |
| `SkillDatabase.get_mana_cost / get_cooldown_seconds` | skill_db.py:206/213 | skill_manager.py:220/228/834/842 |
| `LLMItemGenerator._sanitize_item_data(item_data)` | llm_item_generator.py:951 | generation pipeline before inventory insert (llm_item_generator.py:720) |
| `QuestGenerator.apply_turn_in(player_id, giver_npc_id, quest_id, …)` | quest_tool.py:136 | quest turn-in in game_engine (affinity audit block near game_engine.py:1628) — **crosses the future IPC boundary** |
| `compute_score(stats, level)` | crux-foundry/scoring.py:12 | runner.py:236, loop_runner.py:132 |
| `run_once(seed, out_dir, persona)` | crux-foundry/runner.py:186 | batch.py, run_shard.py, viability_report.py:33, optimizer.py:39 (subprocess CLI) |

---

## 3. Dependency edges

**This subsystem imports from:**
- `data.databases.*` (MaterialDatabase for tier lookup in difficulty_calculator.py:224; EnemyDatabase; SkillDatabase; EquipmentDatabase in harness.py:151) — the loader subsystem must exist first.
- `core.paths.get_resource_path` (stats.py:44, class_system.py:29) — path service.
- `events.event_bus` (leveling.py:39, combat_manager.py:780/816/1045/2126, class_system.py:62) — try/except-guarded, optional.
- `core.effect_executor` (combat_manager.py:32; defense application flag `_apply_enemy_defense` handed to executor, combat_manager.py:1691) — the tag-effect subsystem.
- `entities.components.weapon_tag_calculator` (combat_manager.py:936/1624) — internal.
- crux-foundry imports the game via `sys.path` injection + `tests.integration.harness` (runner.py:31–36, 199).

**Who imports this subsystem:**
- `game_engine` (difficulty/reward calc at minigame setup 4303+, failure consumption 8944, invented-item stat build 5506+).
- All `Crafting-subdisciplines/*.py` (reward/difficulty).
- `renderer` (stat display; read-only).
- `world_system` StatTracker consumers (StatStore keys produced by combat, read by crux scoring) — one-way.
- **Hidden coupling called out**: reward_calculator imports DIFFICULTY_RANGES *from* difficulty_calculator (reward_calculator.py:25, §15 trap-1 dedup) — in C#, keep one shared `DifficultyRanges` constant, do not re-duplicate.
- **Hidden coupling**: `stats-calculations.JSON` is read at **module import time** in stats.py:89 — C# must not freeze values before the content root is known (make it an explicit `Load()`.)

---

## 4. Engine coupling (pygame / rendering / input / clock touchpoints)

The constants themselves are almost engine-free; the coupling lives in where they're *applied* and
in the test harness:

| Touchpoint | file:line | Redesign |
|---|---|---|
| Attack visuals interleaved in the damage path (`attack_effects.add_attack_effect`, arc degrees per weapon tag 25/50/55/65/75) | combat_manager.py:1462–1557 | split: damage math → pure assembly; visuals → Godot VFX reading the same tags. `skip_visual` flag already marks the seam |
| LOS check inside the damage path via `collision_system.has_line_of_sight` | combat_manager.py:1479–1504 | move to Godot physics ray query; `skip_los` marks the seam |
| Facing via `math.atan2(dy,dx)` in 2D world coords | combat_manager.py:1508–1511 | 3D: atan2 on XZ plane or `Basis` look-at (see §9) |
| Enemy screen-shake tier table (intensity {1:2,2:4,3:6,4:9}, duration {100,150,200,280} ms) | combat_manager.py:2010–2012 | Godot camera shake; values → config JSON |
| `PlaytestHarness` posts real pygame events; dt via back-dated `engine.last_tick` | harness.py:36–41, 49–69 | Godot: `Input.parse_input_event` + fixed-step `_physics_process` driving in headless mode |
| SDL dummy video/audio drivers for headless runs | runner.py:25–26, conftest.py:27–28 | `godot --headless`; keep 1280×720 pin equivalent (UI-scale determinism, conftest.py:13–17) |
| INT difficulty modifiers mutate live minigame fields (`minigame.HAMMER_SPEED`, `rotation_speed`, `time_limit`) | game_engine.py:4325–4380 | keep as a pure `IntDifficultyModifier.Apply(params)` returning modified minigame params, called by the Control-node minigame overlay |
| Unicode console prints throughout the damage path (`print(f"💥 CRITICAL HIT!")`) | combat_manager.py passim | replace with structured combat-log events; do NOT port prints (crux runner already redirects stdout, runner.py:193) |
| `pygame.time.get_ticks()` as the frame clock | harness.py:38 | Godot `_process(delta)`; the sim itself is dt-driven already (good) |

---

## 5. Constants & formulas — THE LEDGER

> Sacred-constants check against the migration brief: **all verified present in code**, with two
> nuances (LCK 0.12 is combat-path-only; durability floor has a 0.75→0.50 discontinuity at 0).

### 5.1 Player damage pipeline — ACTION path (the shipped melee path)

`combat_manager.py:1608–1693` (`player_attack_enemy_with_tags`), executed in this exact order:

1. `base_damage = params["baseDamage"]` (1609)
2. `+ get_weapon_damage() × hand_mult` (1632–1634); `hand_mult`: **2H ×1.2**, **versatile without offhand ×1.1**, else 1.0 — weapon_tag_calculator.py:32–35
3. `× (1 + STR × 0.05)` — combat_manager.py:1637; per-point value `_STR_DMG_PER_POINT` read once at import, **env `CRUX_STR_DMG_PER_POINT`, default 0.05** (combat_manager.py:17)
4. `× (1 + title meleeDamage total)` (1641–1642)
5. `× enemy-specific title multiplier` (beastDamage etc., 1648; impl character.py:2391+)
6. `× (1 + INT × 0.05)` **only when an elemental tag** (`fire, ice, lightning, poison, arcane, shadow, holy`) is present (1653–1659) — 2026-07 audit fix; INT does NOT scale physical
7. `× (1 + 0.20)` crushing if weapon has `crushing` AND `enemy.defense > 10` (1662–1663; magnitude weapon_tag_calculator.py:115)
8. `× (1 + max(empower_damage, empower_combat))` skill buff (1666–1672)
9. **crit: × 2.0** if `rng < _player_crit_chance(weapon_tags)` (1678–1682)
10. Defense applied executor-side via `_apply_enemy_defense=True` + `_armor_penetration` (1685–1692): `final = dmg × (1 − min(0.75, def × (1 − armor_pen) × 0.01))` — mirror of legacy at 1024–1026. **Cap: 75% reduction.** `armor_breaker` pen = 0.25 (weapon_tag_calculator.py:101).

Crit chance composition — single source of truth `_player_crit_chance` (combat_manager.py:857–882):
`chance = _LCK_CRIT_PER_POINT × get_effective_luck() + pierce_buffs + precision(+0.10) + title criticalChance`
- **`_LCK_CRIT_PER_POINT`: env `CRUX_LCK_CRIT_PER_POINT`, default 0.12** (combat_manager.py:24; retuned 2026-07-11 from 0.02 per optimizer, comment 18–23). Read once at import.
- `precision` weapon tag: +0.10 (weapon_tag_calculator.py:69).

### 5.2 Player damage — LEGACY path & AoE sub-path

`player_attack_enemy` (combat_manager.py:884–1231): unarmed damage **5** (922); tool-in-combat
effectiveness penalty (917); hand mult (940); STR 0.05 (963); title mult (967–968); enemy-type mult
(972); crushing (980); empower (986–995); crit ×2.0 via shared helper (999–1007); defense
`def × (1−pen) × 0.01`, cap 0.75 (1024–1026). Lifesteal enchant heal `min(value, 0.50)` of damage
(1069–1082, **cap 50%**).

AoE sub-path `_single_target_attack` (714–855): STR via `_STR_DMG_PER_POINT` (751 — F8 fix, was
0.01), crit via shared helper ×2.0 (764–767), defense `def × 0.01` cap 0.75 (770–771). Devastate
buff triggers AoE with `circle_radius = buff.bonus_value` (1581).

### 5.3 Enemy → player damage

`_enemy_attack_player` (combat_manager.py:2022–2110):
- `damage = enemy.perform_attack() × per-attack JSON multiplier` (2025)
- weaken status: defense stat −25% default (`stat_reduction` param, 2035)
- `def_multiplier = 1 − DEF × 0.02` (2042)
- `armor_bonus = equipment_total_defense × (1 + DEF × 0.03)` (2051–2052) — **DEF armor-effectiveness +3%/pt, wired 2026-07 (was a dead documented stat)**; pinned by source-assert test test_12:208–217
- `armor_multiplier = 1 − armor_bonus × 0.01` (2055)
- protection enchant: `× (1 − Σ damage_reduction values)` (2058–2073)
- shield block (active block only): reduction = `(1 − shield damage multiplier) × (1 + defense_multiplier bonus)`, clamped to config `shieldMechanics.maxDamageReduction` **default 0.75** (character.py:2482–2512)
- fortify buff: flat subtraction (2088–2094)
- **floor: minimum 1 damage** (2096)
- thorns/reflect: Σ armor reflect values, **cap 0.80**, reflects `final_damage × pct` (2153–2179)

### 5.4 EXP & leveling

- Curve: `exp_requirements[lvl] = int(200 × 1.75^(lvl−1))`, **max level 30** — leveling.py:8–9
- +1 unallocated stat point per level (leveling.py:34); level-ups **cascade in one call** (28–35, pinned by test_progression_fixes)
- Kill EXP defaults: tier1–4 = **100 / 400 / 1600 / 6400**, boss ×10 (combat_manager.py:44–45); overridable by `combat-config` JSON `experienceRewards` (76–83); **dungeon ×2** (2210–2212)

### 5.5 Six stats — per-point values

Loaded from `Definitions.JSON/stats-calculations.JSON > characterStatModifiers` at import with
hardcoded fallbacks (stats.py:21–30, 52–89). JSON values == fallbacks today:

| Stat | Effect | Value | Code | JSON key |
|---|---|---|---|---|
| STR | melee/mining damage | +0.05/pt | stats.py:22; combat_manager.py:17 (env-overridable on combat paths) | meleeDamagePerPoint 0.05 |
| STR | inventory slots / carry | +10/pt flat | stats.py:27 | inventorySlotsPerPoint 10 |
| STR | carry-capacity mult | +0.02/pt | stats.py:153–154 | – (code-only) |
| DEF | damage reduction | +0.02/pt | stats.py:22; applied combat_manager.py:2042 | damageReductionPerPoint 0.02 |
| DEF | armor effectiveness | +0.03/pt | combat_manager.py:2052 (hardcoded, NOT read from stats.py) | armorEffectivenessPerPoint 0.03 |
| DEF | durability-loss mult | ×(1−0.02/pt), floor 0.1 | stats.py:129–130 | – |
| VIT | max HP | +15/pt flat | stats.py:28 | maxHPPerPoint 15 |
| VIT | health regen | ×(1+0.01/pt) on the 5 HP/s base | character.py:1433–1434 (wired 2026-07) | healthRegenPerPoint 0.01 |
| VIT | max-durability mult | +0.01/pt | stats.py:141–142 | – |
| LCK | **combat** crit | **+0.12/pt (env CRUX_LCK_CRIT_PER_POINT)** | combat_manager.py:24, 866 | critChancePerPoint **0.02 — STALE vs code** |
| LCK | gathering crit | +0.02/pt (hardcoded) | character.py:1092 | – |
| LCK | loot quantity | ×(1+0.02/pt) + bonus roll `luck×0.02` (+class resource_quality) | character.py:1141, 1146 | resourceQualityPerPoint 0.02 |
| LCK | rare-drop→luck conversion | bonus / 0.02 | stats.py:176 | rareDropChancePerPoint 0.03 (**used only via titles path**) |
| AGI | forestry damage | +0.05/pt | stats.py:23 via get_bonus, character.py:1060 | forestryDamagePerPoint 0.05 |
| AGI | attack speed | +0.03/pt | character.py:2378 | attackSpeedPerPoint 0.03 |
| AGI | movement speed | +0.015/pt | character.py:784 (**undocumented in CLAUDE.md**) | – |
| INT | minigame difficulty | −0.02/pt, `maxEffectiveINT` 30; bounds: hammer ≥0.4×, temp-decay ≥0.5× (at half effect ×0.5), time ≤1.6×, refining rotation ≥0.4×, alchemy reaction ≤+0.6 | game_engine.py:4303–4380 (values from JSON, fallbacks inline) | reductionPerPoint 0.02 |
| INT | mana | +20/pt flat | stats.py:29 | maxManaPerPoint 20 |
| INT | elemental damage | +0.05/pt (elemental-tagged attacks only) | combat_manager.py:1656 (wired 2026-07) | – (code-only) |

Regen bases: **5 HP/s after 5 s** without dealing *or* taking damage (character.py:156–157,
1430–1434); mana regen **1% of max/s** always (1453–1454). Base HP 100, base mana 100
(character.py:113–114); `max = base + stat + class + equipment` (722–723).

### 5.6 Tier multipliers & item-stat formula system

- **T1/T2/T3/T4 = 1.0 / 2.0 / 4.0 / 8.0** — content master: `Definitions.JSON/stats-calculations.JSON > tierMultipliers`; code mirrors: game_engine.py:5522 (`TIER_MULTIPLIERS`), balance_validator_stub.py:121–137 (loads JSON).
- Item stat formula (content, applied by equipment loader): `globalBase × tier × category × type × subtype × item`; globalBases: weaponDamage 10, armorDefense 10, toolGathering 10, **durability 250**, weight 1.0, attackSpeed 1.0 (stats-calculations.JSON `globalBases`). Damage variance ±15% (`varianceRange` 0.85–1.15).
- Invented-item derivation: single damage number → range ×0.8/×1.2 (game_engine.py:5513–5516); durability `250 × tier_mult` (5521–5534).

### 5.7 Crafting difficulty (difficulty_calculator.py)

- Points: **T1=1, T2=2, T3=3, T4=4 per item, LINEAR** (`TIER_POINTS`, 35–40). *Note: this is the crafting-points scale, distinct from the 1/2/4/8 item-stat tier multipliers.*
- Bands (`DIFFICULTY_THRESHOLDS`, 47–53): common (0–4), uncommon (5–10), rare (11–20), epic (21–40), legendary (41–150). **The module's own docstring (lines 19–23: "Common 1–8, Uncommon 9–20…") is STALE — the dict is authoritative.**
- Interpolation range: min 1.0 → max 80.0 points (56–59); linear param lerp (254–288).
- Diversity multiplier: `1 + (unique_materials − 1) × 0.1` (178–204).
- Smithing: points only, no diversity (290–322); param ranges 66–97 (e.g. time 60→25 s, hammer speed 3.0→14.0, hits 3→12, temp window 25→3°).
- Refining: `points × diversity × (1 + stationTier × 0.5)` (344–352); params 104–123 (cylinders 3→12, window 0.05→0.01 s).
- Alchemy: `points × diversity × 1.2^(avg_tier−1) × (1 + volatility × 0.3)` (416–428); volatility = clamp((vowel_ratio − 0.3) × 2.5, 0, 1) (450–480); params 379–397.
- Engineering: `points × diversity × (1 + (slots − 1) × 0.05)` (569–579); ideal-moves 12-tier table (517–531: ≤8→6 … ≤56→7 … else 8); params 495–509.
- Enchanting: `points × diversity` (644–648); wheel: 20 slices total, green 12→6 (clamp 4–14), red 3→10 (clamp 2–12), grey ≥2, green mult 1.5→1.2, red mult 0.8→0.0, always 3 spins (609–671).
- Legacy per-tier fallback tables (686–747) — used when material data missing; port them (they are reachable).

### 5.8 Crafting rewards & failure (reward_calculator.py)

- Reward multiplier: 1.0 → **2.5** over difficulty 1→80 (`REWARD_MULTIPLIER`, 28–31; formula 81–104).
- Quality bands (`QUALITY_TIERS`, 34–40): Normal [0,0.25), Fine [0.25,0.50), Superior [0.50,0.75), Masterwork [0.75,0.90), Legendary [0.90,1.0].
- **Failure loss: 0.30 → 0.90** linear in normalized difficulty (`FAILURE_PENALTY` 43–46; `calculate_failure_penalty` = `0.3 + norm × 0.6`, 497–519; per-material `int(qty × loss)`, 522–546). Applied by smithing.py:817–837, refining.py:313–326, alchemy.py:994–1010; engine consumes at game_engine.py:8944–8951 (fallback 1.0 = lose all if crafter didn't declare — port this fallback exactly).
- First-try bonus: default +0.10 performance, engineering +0.05; special-attribute eligibility ≥ 0.50 (52–74).
- Alchemy result: performance `chain×0.6 + timing×0.4 − explosion_penalty` (338); potency/duration mult `1 + (perf − 0.5) × (max_mult − 1)` (duration ×0.6 of that), clamped **0.25–2.0** (351–358).
- Enchanting: efficacy from currency: `(currency − 100)/200` → −0.5..+0.5 (471).

### 5.9 Durability

- **Floor**: `durability_current <= 0 → 0.5` effectiveness — equipment.py:52–53. Above zero: `1.0` if pct ≥ 0.5, else `1.0 − (0.5 − pct) × 0.5` (54–55) — i.e. linearly 1.0→0.75 as pct 0.5→0, then a **discontinuous drop to 0.50 at exactly 0**. (Content doc `durabilitySystem.durabilityMechanics` in stats-calculations.JSON describes the same three-zone behavior.) Items never break (repair only, equipment.py:57–80).
- Gathering drain: 1.0/use proper tool, 2.0 improper (character.py:1104), × DEF loss-mult (1108), × (1 − Unbreaking value) (1111–1116).
- Effectiveness multiplies weapon damage (equipment.py:110–119) and armor defense (142–143).

### 5.10 Enchantments & status effects

Enchant **magnitudes are content** (`recipes.JSON/recipes-adornments-1.json`, reused verbatim —
e.g. a 0.12 value at line 1236). Code-side constants:

| Enchant behavior | Constant | file:line |
|---|---|---|
| Lifesteal | default 0.10, **cap 0.50** of damage | combat_manager.py:1074, 1720 |
| Thorns/reflect | **cap 0.80** total across armor | combat_manager.py:2175 |
| On-hit DoT defaults | duration 5.0 s, 10.0 dps | combat_manager.py:1268–1270 |
| Knockback default | 2.0 tiles | combat_manager.py:1279 |
| Frost-touch slow default | 30% for 3.0 s | combat_manager.py:1290–1292 |
| Health-regen enchant | value HP/s, additive, always active | character.py:1437–1450 |

Status-effect default params (entities/status_effect.py; all overridable by tag params):
burn 5.0 dps (:97) · bleed 3.0 (:131) · poison 2.0 (:163) · slow 50% (:249) · regen 5.0 HP/s (:379) ·
shield 50 HP (:412) · haste +30% (:456) · empower +25% (:507) · fortify 20% reduction (:546) ·
weaken −25% damage (:589) · vulnerable +25% taken (:624) · shock 5.0/tick @ 2.0 ticks/s (:659–660) ·
default duration 5.0 s (:824).

Skill-buff magnitude tables (skill_manager.py:42–45): empower 0.5/1.0/2.0/4.0 · quicken
0.3/0.5/0.75/1.0 · fortify 10/20/40/80 flat · pierce 0.1/0.15/0.25/0.4 (minor/moderate/major/extreme).
Restore: 15/30/50/75% or 50/100/200/400 flat (:428–429). Mana-cost enum fallback **60**, cooldown
fallback **300 s** (skill_db.py:211, 218).

Class skill affinity: **+0.05 per matching tag, cap +0.20** (classes.py:43–44) → the sacred
"class max ×1.2"; applied to skill magnitude (skill_manager.py:329) and combat skill
damage/healing (:949–951). Class tag→tool bonuses fallback table (class_system.py:15–19), JSON
override `progression/classes-1.JSON > metadata.tagToolBonuses`.

### 5.11 Invented-item ceilings (LLM boundary)

`llm_item_generator.py:947`: `_STAT_CEILING_BY_TIER = {1: 60, 2: 120, 3: 240, 4: 480}` over keys
`damage, baseDamage, defense, armor, healAmount, healing, attackSpeed` (:948–949); tier clamped
1–4 first (:962–972); id collisions with existing content prefixed `invented_` (:975–984). This is
the STOPGAP for the unimplemented BalanceValidator (comment :939–946). **Port to C#** even though
generation stays in the sidecar: the Godot side must never trust sidecar output unsanitized.

### 5.12 Affinity (sidecar-owned; IPC contract)

- Clamp **−100..+100** on every player/NPC/location write — faction_system.py:225, 266, 316, 338, 407, 621.
- Generic quest turn-in (quest_tool.py:130–133): giver NPC → player **+5.0**; player → giver's faction tags: primary **+4.0**, next two **+2.0**, max **3 tags**. Resolution order explicit_deltas → per-quest map → NPC belonging tags (:143–176).
- Hand-written example quest outcome map (smith_contract ±15/20…, quest_tool.py:38–78) — placeholder content, flagged TODO :35–36.
- WNS `AffinityShift` per-directive cap **±25.0** (affinity_resolver.py:43, applied :276–293) — F15.

### 5.13 Combat config defaults (CombatConfig, combat_manager.py:44–67; JSON-overridable)

EXP rewards (above) · boss ×10 · safe zone: origin, radius 15 · density spawn weights
very_low 0.5 / low 0.75 / moderate 1.0 / high 2.0 / very_high 3.0 · base attack cooldown 1.0 s ·
tool attack cooldown 0.5 s · corpse lifetime 30 s · combat timeout 5.0 s · respawn base 300 s ×
tier {1.0, 1.5, 2.0, 3.0} · boss respawn 1800 s. Enemy loot chance words (enemy.py:192–199):
guaranteed 1.0 / high 0.75 / moderate 0.5 / low 0.25 / rare 0.10 / improbable 0.05.

### 5.14 Env overrides — complete list

| Env var | Default | Read at | Consumer |
|---|---|---|---|
| `CRUX_STR_DMG_PER_POINT` | 0.05 | import, combat_manager.py:17 | all 4 STR sites (751, 963, 1381, 1637) |
| `CRUX_LCK_CRIT_PER_POINT` | **0.12** | import, combat_manager.py:24 | `_player_crit_chance` :866 |
| `CRUX_GAUNTLET_SIZE` / `CRUX_GAUNTLET_TIER` | 8 / 2 | runner.py:44–45 | foundry challenge |
| `CRUX_RUN_TIMEOUT_S` | 120 | run_shard.py:20 | shard wall cap |
| `CRUX_REDUCE_ONLY` | unset | viability_report.py:24 | login-node reduce |
| `GAME1_HERMETIC` | unset (=1 in foundry) | game_engine.py:507, 5170; generated_file_writer.py:81 | disables WES generation + shared-tree writes |

**Tension (do not relitigate, but preserve):** LCK is 0.12/pt on combat crit (code+env), while
`stats-calculations.JSON` still says `critChancePerPoint: 0.02` and gathering crit hardcodes 0.02
(character.py:1092). These are **two different live values by design of the retune** — the C# port
must keep them separate constants, and the JSON's luck entry must NOT be "fixed" to 0.12 (it feeds
`stats.get_bonus('luck')`, not combat crit). Stale comment flagging: test_12:127 says
"50 * 0.02 = 100%" (pre-retune comment; assertion still valid since 50×0.12 ≥ 1.0).

---

## 6. Event topics (GameEventBus) published/consumed by this subsystem

All publishes are try/except-guarded (bus optional):

| Topic | Direction | file:line |
|---|---|---|
| `LEVEL_UP` | publish | leveling.py:40 |
| `DAMAGE_DEALT` | publish | combat_manager.py:781 (AoE), 1052 (legacy); action path via `rendering.visual_effect_bridge.publish_damage_dealt` :1743 |
| `ENEMY_KILLED` | publish | combat_manager.py:817 (+visual bridge :844) |
| `PLAYER_HIT` | publish | combat_manager.py:2127 (+visual bridge :2143) |
| `CLASS_CHANGED` | publish | class_system.py:63 |
| `FACTION_AFFINITY_CHANGED` | publish (sidecar) | faction_system.py:10 (from adjust/set_player_affinity) |
| `FACTION_AFFINITY_CONSOLIDATED` | publish (sidecar) | quest_tool.py:154 (via consolidator) |
| `QUEST_ACCEPTED` / `QUEST_COMPLETED` / `QUEST_FAILED` | publish | quest_system.py:293 / 402 / 552 |
| `ITEM_CRAFTED` | publish | via `_complete_minigame` pipeline (exercised by harness.py:158–185) |

Consumers relevant here: WMS `event_recorder` subscribes to ~60 types (sidecar); crux capture
reads the StatStore that these events feed. **In Godot these become C# events/signals on the game
side plus an IPC event stream to the sidecar.**

---

## 7. Content JSON consumed (verbatim reuse; loaders ported)

| Path | Loader | Constants carried |
|---|---|---|
| `Definitions.JSON/stats-calculations.JSON` | stats.py:33–89 (`_load_stat_config`); game_engine.py:4309 (`stat_modifiers_config`); balance_validator_stub.py:91–137 | tierMultipliers 1/2/4/8; globalBases (durability 250 etc.); all 6 stat per-point values; INT minigame bounds |
| `Definitions.JSON/combat-config.JSON` (name per CombatConfig.load_from_file caller) | combat_manager.py:69–120 | EXP rewards, safe zone, respawn, cooldowns, spawn weights, `shieldMechanics.maxDamageReduction` (character.py:2508–2510) |
| `Definitions.JSON/hostiles-1.JSON` + `hostiles-generated-*.JSON` | enemy.py:212+ (`EnemyDatabase.load_from_files`; sacred+generated overlay, :177–184) | enemy damage/defense/tier/loot tables |
| `progression/classes-1.JSON` | class_system.py:24–44 (`metadata.tagToolBonuses`) + ClassDatabase | class tags, bonuses |
| `Skills/skills-skills-1.JSON` | SkillDatabase (skill_db.py) | mana/cooldown enums, effect params |
| `recipes.JSON/recipes-adornments-1.json` | RecipeDatabase | enchantment magnitudes (content) |
| `recipes.JSON/*`, `items.JSON/*`, `placements.JSON/*` | respective DB singletons | recipe inputs feeding difficulty points |

---

## 8. Persistent state contributed to save/load

- Character stats block: `strength/defense/vitality/luck/agility/intelligence` ints (character.py:228–231 write; 286–289, 387–390 read; save_manager.py:163).
- `health`, `mana` restored AFTER `recalculate_stats()` (character.py:406–411) — ordering matters, port exactly.
- Leveling: `level`, `current_exp`, `unallocated_stat_points` (via character save block; leveling fields at leveling.py:6–10).
- Equipment durability: `durability_current` / `durability_max` per item (equipment.py:200–201 clone; serialized by save_manager) — the floor behavior depends on these surviving round-trip.
- Invented recipes/items persist across saves (invented ids possibly `invented_`-prefixed by sanitizer §5.11).
- Sidecar-owned (NOT in the C# save): faction/NPC affinity in `faction.db` SQLite (faction_system tables), WMS StatStore/EventStore SQLite. Save-path redirection pattern (conftest/`paths._path_manager.save_path`, runner.py:66) becomes: Godot save dir + sidecar DB dir handshake at IPC session start.
- crux-foundry artifact contract: `result.json` schema v1 (runner.py:221–252) — `manifest{run_id, seed, persona, config{weapon, gauntlet_size, gauntlet_tier, compose_seed}, git_sha}`, `outcome ∈ {cleared, partial, wiped, capture_blind}`, `score{total, breakdown}`, `metrics{...}`, `combat_stats`, `progression_stats`. **Treat this schema as frozen** — it is the cross-engine oracle format.

---

## 9. 3D notes (what necessarily changes 2D → 3D)

The ledger's *numbers* are dimension-agnostic; their *geometry inputs* are not:

1. **Distances**: all ranges/radii are 2D tile distances — weapon range (harness hitbox reach ~1.5 tiles, harness.py:141), knockback 2.0 tiles (combat_manager.py:1279), devastate `circle_radius`, safe-zone radius 15, AoE gathering radius (character.py:1010–1013 Euclidean 2D). Decision needed: XZ-plane distance (recommended; mirrors the paused Unity plan's `DistanceMode`) so numeric balance is untouched, vs true 3D distance (changes effective ranges on slopes → re-run the crux oracle to detect drift).
2. **Facing**: `atan2(dy, dx)` degrees (combat_manager.py:1508–1511) → yaw on the XZ plane; arc-degree tables (25–75°, :1539–1550) become horizontal swing arcs; a vertical arc/aim-assist parameter is NEW config (does not exist in 2D — put it in JSON per project philosophy).
3. **Hitboxes**: 2D shapes → Godot `Area3D` with cylinder/box `Shape3D`; the conformance seam is `skip_los`/`skip_visual` on `player_attack_enemy_with_tags` — the pure damage calc takes "hit confirmed" as an input, so hit *math* is unchanged while hit *detection* is re-derived. Geometry target-selection tests (`test_geometry_patterns.py`) must be re-derived with XZ semantics (chain/cone/circle/beam).
4. **LOS**: collision_system.has_line_of_sight (2D tile raycast, combat_manager.py:1480) → PhysicsRayQueryParameters3D; `bypass_tags = {circle, aoe, ground}` (:1478) must be preserved.
5. **Positions in events**: `position_x/position_y` in every bus payload (e.g. combat_manager.py:790–791) → decide `x,z` mapping ONCE for the sidecar IPC contract (WMS geographic layers key off these).
6. **Knockback/pull**: 2D displacement vectors → XZ displacement; do not introduce Y-launch without new config.
7. **Crux oracle in 3D**: runner teleports the player to `enemy.x − 1.0` (runner.py:159) — the Godot twin runner places the agent 1.0 unit away on the XZ plane facing the enemy; outcomes (kills, damage totals) must match the Python oracle within stochastic tolerance (§B.3).
8. **Camera/screen shake** tier tables (combat_manager.py:2010–2011) → Godot camera FX; values preserved but move to config JSON.

---

## 10. Godot mapping

**Pure-logic assembly `Game1.Core` (no Godot references; `dotnet test`-able):**

| C# type | Ports | Notes |
|---|---|---|
| `static class BalanceConstants` | combat_manager.py:17,24 env knobs; all §5 literals not in JSON | env read via `Environment.GetEnvironmentVariable` in a static `Load()` (NOT static ctor at unpredictable time); expose `LckCritPerPoint` (0.12), `StrDmgPerPoint` (0.05) |
| `StatScaling` (+ `StatsCalculationsConfig` DTO) | stats.py incl. JSON load + `reload_stat_config` | explicit `Load(path)`; keep fallback dict verbatim |
| `LevelingSystem` | leveling.py | cascade loop verbatim; event publish via injected `IEventSink` |
| `WeaponTagModifiers` | weapon_tag_calculator.py | verbatim static class |
| `DamageCalculator` / `CritComposer` / `EnemyAttackResolver` | combat_manager damage math (§5.1–5.3) | pure functions taking `AttackContext` (weapon tags, stats, buffs, enemy def, RNG); the *order of operations incl. int truncations* is the contract |
| `DifficultyCalculator`, `RewardCalculator` | both modules verbatim | share one `DifficultyRanges` (§3 hidden coupling) |
| `DurabilityModel` | equipment.py:49–107 | includes the 0.75→0.50 discontinuity |
| `StatusEffectDefs` + tick logic | status_effect.py | data-driven defaults table |
| `InventedItemSanitizer` | llm_item_generator.py:939–1035 | applied to sidecar IPC responses |
| `CruxScoring` | crux-foundry/scoring.py | identical breakdown keys |
| `IRandomSource` (+ `SeededRandom`) | `CombatManager._rng` + global-random split (combat_manager.py:139,198–201) | preserve the TWO-STREAM architecture: combat stream vs world/loot stream (test_09 contract) |

**Engine glue (Godot project):**
- `CombatManagerNode : Node` — orchestrates hitboxes (`Area3D`), calls `DamageCalculator`, emits signals mirroring §6 topics.
- Autoload singletons for DB loaders (matching the `get_instance()` pattern) and `EventBusAutoload` (bridges C# events → sidecar IPC).
- `IntDifficultyModifier` applied by the Control-node minigame overlays (crafting stays 2D per standing decision).
- `HeadlessHarness` (Godot `--headless` + `SceneTree` driver) re-implementing `PlaytestHarness`'s API (`tick`, `melee_swing`, `craft`, `seed_all`, `give`, `equip`) so crux drivers translate 1:1.

**Conformance test project `Game1.Conformance.Tests` (xunit):** ports of test_12, test_11,
test_progression_fixes, test_enchantments, test_status_effects, test_invented_item_sanitizer,
test_scoring, test_geometry_patterns (XZ), rarity/consumption crafting tests — plus golden-file
tests replaying crux `result.json` manifests (§B.3).

**Sidecar boundary:** faction/affinity constants (§5.12) stay in Python; the C# side documents them
as the IPC contract (turn-in message → sidecar applies 5/4/2, clamps ±100, returns consolidated
standing) and merely *validates* replies (range checks).

---

## 11. Port complexity, ordering, risks

**Complexity: L overall** — individual modules are S (leveling, scoring, weapon tags, stats) to M
(difficulty/reward, sanitizer, status defaults) — the L comes from combat_manager decomposition
(three paths + enemy path, ~1,200 relevant LOC entangled with visuals/LOS/prints) and from standing
up the Godot headless harness + oracle twin.

**Ordering constraints:**
1. `stats-calculations.JSON` loader + `BalanceConstants` **first** (everything reads them).
2. Content DB loaders (materials/equipment/recipes/enemies) — difficulty calc needs material tiers; damage needs weapon stats.
3. Pure calculators (damage/crit/EXP/difficulty/reward/durability) + their xunit ports — **before** any combat or crafting gameplay code, so gameplay is built against passing conformance tests.
4. `IRandomSource` two-stream plumbing before any combat port (retro-fitting determinism is what the Python side had to do the hard way — DETERMINISM_LEDGER D1–D9).
5. Godot HeadlessHarness → crux twin runner → oracle comparison, before balance sign-off.

**Top risks/gotchas:**
1. **The doc-vs-code trap**: CLAUDE.md's "LCK +2%/pt", stats-calculations.JSON's 0.02, the difficulty docstring's stale bands, and test_12:127's stale comment all disagree with live code. Port from the cited lines, then run the conformance suite — never from docs.
2. **Dual LCK values are intentional** (0.12 combat / 0.02 gathering+JSON). A well-meaning "unification" during port silently rebalances the game.
3. **Python float/int semantics**: `int()` truncation applied mid-pipeline (combat_manager.py:926, 960 truncate weapon damage before STR mult; `int(qty × loss_fraction)` floors material loss). C# must truncate at the SAME points; double vs float drift can flip band boundaries (use `double`).
4. **RNG non-portability**: Python's Mersenne Twister streams cannot be matched by `System.Random`. The cross-engine oracle must compare *outcomes/distributions* (kills, clear-rate, damage aggregates over ≥5 seeds), not RNG draws — or embed an MT19937 implementation in C# and match draw-for-draw (viable: the foundry draws are few and localized).
5. **Import-time config freeze**: stats.py:89 and combat_manager.py:17/24 read JSON/env at module import. In C#, an eager static ctor can freeze before content paths/env are set (the optimizer's per-process env pattern depends on read-at-startup). Make loading explicit and test the override path.
6. **Defense application is split across two components** on the action path (flag set in combat_manager.py:1691, applied inside effect_executor via `_apply_enemy_defense`/`_armor_penetration`). Porting DamageCalculator without porting the executor-side application reintroduces F5 (enemy DEF dead again). The test_12 port catches this — port it first.
7. **Whether SKILL damage respects enemy defense is an explicitly open design question** (comment combat_manager.py:1688–1690): melee-only today. Preserve as-is; do not "fix".
8. **Sidecar constants drift**: affinity deltas/caps live in Python (§5.12). If the C# side ever hardcodes expectations (UI previews of "+5 reputation"), they will drift. Fetch magnitudes over IPC or treat sidecar reply as sole truth.
9. **`game_engine`-embedded constants** (INT modifiers 4303–4380, invented-item stat build 5506+, tier multipliers 5522) are easy to miss because they live in an 11.7k-line engine file scheduled for engine-replaces. They must be extracted, not dropped.
10. **Minimum-1-damage floor** (combat_manager.py:2096) and lifesteal/reflect caps are the kind of one-liners that vanish in a rewrite; each has a ledger row above — turn every row into an xunit assertion.

---

# Part B — Conformance Mining Guide

## B.1 The three test strata and what each buys the port

1. **Pure-logic unit tests** (tests/ root + crafting/ + save/ + crux `test_scoring.py`): import game modules directly, no pygame/engine. ≈ 130 tests in the portable set (§1b "port-as-test" rows). These translate to xunit nearly mechanically (mock entities in test_enchantments/test_status_effects are plain dataclasses).
2. **Engine-integration playtests** (tests/integration/, 13 files, 40 tests): boot the REAL GameEngine headless (conftest.py session fixture, SDL dummy) and drive it through `PlaytestHarness`. These are **behavior specs, not portable code** — each maps to a Godot-headless re-derivation. test_12 + test_11 are the exception: their assertions are about pure math and port directly once DamageCalculator exists (their two source-assert tests, test_12:208–229, become real behavioral tests in C# — inspecting source text was a Python workaround).
3. **crux-foundry system runs**: whole-game seeded subprocess runs producing `result.json`. This is the **cross-engine behavioral oracle**.

Suite baseline at branch close: **1,219 passed / 0 failed** (SHIP_READINESS_REPORT.md:14).

## B.2 Priority conformance map (behavior → pinning test → C# target)

| Behavior (sacred) | Pinned by | Port target |
|---|---|---|
| Enemy DEF reduces action-path damage; cap 75% | test_12_combat_conformance.py:41–91 | xunit vs `DamageCalculator` (behavioral) |
| Crit composition unified; LCK+precision+titles; crit ×2 | test_12:94–137; test_11 (F4 guard) | xunit vs `CritComposer` |
| VIT +1%/pt regen | test_12:142–166 | xunit vs regen function |
| INT +5%/pt elemental only (physical unaffected) | test_12:169–205 | xunit |
| DEF +3%/pt armor effectiveness | test_12:208–217 (source-assert) | **upgrade to behavioral** xunit on `EnemyAttackResolver` |
| AoE sub-path STR 0.05 + shared crit | test_12:220–229 (source-assert) | upgrade to behavioral |
| EXP cascade + curve + max level | test_progression_fixes.py | xunit vs `LevelingSystem` |
| Failure loss 30–90% tier-scaled (not 100%) | test_progression_fixes.py (item 2) | xunit vs `RewardCalculator` + consumption |
| All 14 enchantments incl. caps | test_enchantments.py (8) | xunit vs enchant handlers |
| Status apply/tick/expire magnitudes | test_status_effects.py (5) | xunit |
| Invented ceilings 60/120/240/480 + tier clamp + id guard | test_invented_item_sanitizer.py (6) | xunit vs `InventedItemSanitizer` |
| Geometry target selection (chain/cone/circle/beam) | test_geometry_patterns.py (8) | xunit, XZ-plane re-derivation |
| Two-stream seeded determinism | test_09_determinism.py | Godot-headless: same-seed reproduce / different-seed diverge on `IRandomSource` streams |
| Action path feeds capture (no capture-blind) | test_10_capture.py; runner.py:208–219 outcome guard | Godot harness melee_swing → stat capture |
| Affinity turn-in moves affinity; persists; WNS bridge | test_affinity_long_horizon.py (9) | stays Python; C# adds an IPC-contract test (send turn-in msg → assert reply deltas 5/4/2 & clamp) |
| Score breakdown arithmetic | crux-foundry/test_scoring.py (5) | xunit vs `CruxScoring` (must be value-identical) |

## B.3 crux-foundry as the cross-engine oracle — protocol

**What makes it an oracle**: hermetic (`GAME1_HERMETIC=1` disables WES generation + shared-tree
writes, runner.py:28, game_engine.py:507/5170, generated_file_writer.py:81), isolated
(per-run save dir → private SQLite, runner.py:63–66), deterministic (challenge composition fixed by
`GAUNTLET_COMPOSE_SEED = 20260706` independent of the run seed, runner.py:46, 93–110; run seed
controls only combat RNG via the two-stream `seed_all`, harness.py:104–112 + runner.py:192–202),
and versioned (`git_sha` in every manifest, runner.py:50–60).

**Personas as build specs** (runner.py:119–127): `melee_basic` (L1, no stats) · `str_brawler`
(L10, STR 9) · `vit_tank` (L10, VIT 9) · `lck_crit` (L10, LCK 9) · `balanced` (L10,
2/2/2/1/1/1) — all with `iron_shortsword`. Builds are applied through the REAL APIs
(level-up loop + `allocate_stat_point` + equip, runner.py:130–145), which is exactly what the
Godot twin must do (no state poking).

**Fixed challenge**: tier-2 gauntlet of 8 (env-overridable, runner.py:44–45), enemies in a row at
`(2 + 2i, 0)`, player teleported adjacent, swing cap 30/enemy (runner.py:47, 148–168).

**Oracle procedure for the port**:
1. Freeze a golden corpus now: run `viability_report.py 8` (and `loop_runner.py` for N seeds) on the Python build at a recorded `git_sha`; archive `runs/**/result.json`.
2. Implement the Godot twin runner: same CLI shape (`seed, out_dir, persona`), same persona specs, same fixed gauntlet composition (requires porting or emulating the enemy-DB pick under the compose seed — simplest: serialize the Python-chosen `gauntlet_ids` from the golden manifests and spawn those exact enemies), same result.json schema v1.
3. Compare per persona across ≥5–8 seeds (multi-seed averaging cancels crit variance — F2 methodology, viability_report.py:8): `outcome` distribution, mean kills, mean damage_dealt/taken, viability index `kills/8 − 0.05·deaths`, and `score.breakdown` (deterministic, must match exactly for identical drives). Tolerance: viability within the Python per-seed spread; exact-match not expected unless MT19937 is ported.
4. Re-run `optimizer.py` shape against the Godot build to confirm knob responsiveness (a stat knob that produces bit-identical results across its grid = wiring bug, the F4 signature — optimizer.py:74–93).
5. Adopt `DETERMINISM_LEDGER.md` D1–D9 as the Godot determinism checklist (RNG injection, AI disabling, hermetic content, save-dir isolation).

**Engine-bound pieces that must be rebuilt, not ported**, for the oracle to run: engine boot to
world (runner.py:63–79), `PlaytestHarness.tick/melee_swing/craft` (harness.py), StatTracker→
StatStore capture (runner.py:171–183 reads `stat_tracker._store`; the Godot side needs an
equivalent stat-capture store with the same key names — `combat.damage_dealt`,
`crafting.success.recipe.<id>`, `progression.skills_learned`, etc., since scoring keys off them,
scoring.py:18–30).

**Not portable / stays Python**: `life_runner.py` chronicle extraction (reads WMS internals —
daily ledgers, interpretations, life_runner.py:71–112). Post-migration it becomes a sidecar-side
tool fed by the Godot game over IPC; until then it remains a Python-build-only regression check.

## B.4 Dead code / stale docs found during the sweep

- `difficulty_calculator.py:19–23` module docstring bands (1–8/9–20/21–40/41–70/71+) contradict the live `DIFFICULTY_THRESHOLDS` dict (:47–53). Dict is used (:764–772); docstring is stale.
- `stats-calculations.JSON > characterStatModifiers.luck.critChancePerPoint = 0.02` is stale for combat (live value 0.12 via env default, combat_manager.py:24) but still LIVE for `stats.get_bonus('luck')` consumers — dual truth, keep both (§5.14).
- `tests/integration/test_12_combat_conformance.py:127` comment "50 * 0.02 = 100% crit" — stale arithmetic, assertion unaffected.
- `combat_manager.py:1056` references `damage_type` in the legacy-path DAMAGE_DEALT publish; the variable is not defined in the visible flow of `player_attack_enemy` before that line — it's shielded by the blanket `except Exception` on the publish block (:1044–1067), so a NameError would silently kill the WMS event. Verify during port; in C# make the payload fields explicit.
- `QuestGenerator.get_affinity_deltas` hardcoded three-quest map (quest_tool.py:38–78) is acknowledged placeholder content (TODO :35); the generic `apply_turn_in` (:136) is the real runtime path.
- CombatConfig legacy respawn tier multipliers (1/1.5/2/3, combat_manager.py:98–101) differ from item tier multipliers (1/2/4/8) — same word "tier multiplier", different systems; label distinctly in C#.
- `attack()` on the harness (harness.py:128–131) is the legacy path and skips StatTracker — documented trap; the Godot harness should expose only the capture-complete swing plus an explicitly-named legacy call.

# Controls Map — Everything You Can Tune

*Authored 2026-06-03; v2 expanded 2026-06-04 with parallel-agent canvass of 5 game domains.*
*Companion to `feature-traces/00-consolidation.md`.*

This document indexes every tunable control across the v4 system: prompts, configs, thresholds, allow-lists, runtime constants, balance numbers, content fields. Each entry names what it controls, where it lives, its current value/state, and whether it's a designer call.

**Reading order**: §0 = runtime readiness; §1 = the v4 designer prose (the work the autonomous execution exposed); §2-§3 = behavior + scope tuning; §4-§8 = comprehensive domain canvass from parallel-agent research (combat, crafting, world gen, progression, WMS/factions); §9 = known follow-up survey gap; §10-§14 = allow-lists, sacred content, designer tools, suggested tuning order, references.

**Scope note**: §4-§8 list **>1100 individual tunables** drawn from the agent reports. Each entry includes file path + line number (Python) or JSON key path. P0/P1/P2 priorities reflect immediate-playtest-impact vs. polish.

---

## §0 — Runtime readiness

**Narrative-causal path**: ✓ Wired. WNS weavers fire `<WES>` directives → WES orchestrator subscribes to `WNS_CALL_WES_REQUESTED` → planner → hub → tool → ContentRegistry commits → DatabaseReloader publishes `EVT_DATABASE_RELOADED`. Existing wiring at [game_engine.py:4661-4665](Game-1-modular/core/game_engine.py#L4661-L4665).

**Behavior-causal path**: ✓ Wired 2026-06-03 at [game_engine.py:4673-4711](Game-1-modular/core/game_engine.py#L4673-L4711). `WMS_TRIGGER_FIRED` events from `TriggerManager` reach `BehaviorInterpreter` which publishes `WNS_CALL_WES_REQUESTED`. The user's potions example works end-to-end.

**Bundle contract**: ✓ Bridge populates all Phase 1 fields; slice propagates; planner + 8 hubs expose template variables.

**Reload pipeline**: ✓ All 8 databases reload on signal.

**Remaining runtime-wiring gaps** (substrate ships, not yet called):

| Component | What's needed | Suggested integration site | Priority |
|---|---|---|---|
| **QuestArchiveDatabase** | `archive(record)` invoked on quest turn-in | [quest_system.py:337](Game-1-modular/systems/quest_system.py#L337) `complete_quest` after `grant_rewards` | P1 |
| **MixedTriggerArbiter** | Called when narrative + behavior firings concur at same address within 30s | Inside BehaviorInterpreter before publish OR inside WNS weaver firing path | P2 |
| **PresenceDriftDetector** | `detector.scan(current_game_day)` invoked on daily ledger tick | `daily_ledger.check_day_boundary` callback | P2 |
| **StatStore `meta.last_activity_day.*`** | Written when player acts at a locality (so drift detector can read it) | StatTracker.record_chunk_entered / .record_npc_interaction etc. | Bundled with drift detector |

---

## §1 — Designer prose (v4 highest leverage)

**v4 PROSE WORK** — the 14 modular blocks + shared fragments seeded by Phase 3.

### §1.1 — The 14 modular blocks

| Block | File | Status |
|---|---|---|
| `prose_ambiguity_directive` (shared) | `world_system/config/prompt_fragments_designer_drafts.json` | Draft → refine |
| NPC manifestation framing | Same file → `npc_manifestation_framing` | Draft |
| NL2-NL7 layer voices (6 blocks) | Same file → `layer_voice.nl{2-7}_*` | Drafts |
| 8 purpose-shape blocks (new-material, new-node, new-hostile, new-skill, new-title, new-chunk, new-npc, new-quest) | Same file → `purpose_shape.new_*` | Drafts |

Assembly: weaver runtime composes `[layer-voice for NL<N>] + [purpose-shape for purpose] + [shared scope rules]`.

### §1.2 — Per-layer narrative fragments (existing)

`world_system/config/narrative_fragments_nl{2..7}.json` — system prompt + scope rules + `_wes_tool` per-purpose firing guidance per layer.

### §1.3 — WMS shared fragments

`world_system/config/prompt_fragments.json` — `_game_context` block (world tone, tier explanations, factions, magic, player role). **WORLD TONE placeholder unfilled — highest single-file leverage.**

### §1.4 — Per-tool prompts (16 files)

| Tool | Hub | Tool |
|---|---|---|
| hostiles / materials / nodes / skills / titles / chunks / npcs / quests | `prompt_fragments_hub_<tool>.json` | `prompt_fragments_tool_<tool>.json` |

Hub `user_template` carries Phase 1 vars; **system prompts still pre-v4** — Phase 3 designer work updates these to read the new variables.

### §1.5 — Orchestrator + Quest reward prompts

- `prompt_fragments_wes_execution_planner.json` — `SCOPE BY FIRING TIER` + `SCOPE BY BEHAVIOR THRESHOLD`
- `prompt_fragments_wes_supervisor.json` — 6 narrative checks + Phase 2 behavior checks 7/8/9
- `prompt_fragments_wes_quest_reward_pregen.json` + `prompt_fragments_wes_quest_reward_adapt.json`

### §1.6 — LLM training prompts (crafting LLM, separate from WES)

| File | Purpose |
|---|---|
| `Scaled JSON Development/LLM Training Data/Fewshot_llm/prompts/system_prompts/system_*.txt` | Per-system base prompts |
| `Fewshot_llm/prompts/enhanced/{smithing,alchemy,refining,engineering,enchanting}_items_prompt.txt` | Per-discipline item generation |
| `Fewshot_llm/prompts/components/base/system_*_base.txt` | 16 component base prompts |
| `Fewshot_llm/examples/few_shot_examples.json` | Examples (max 3 by default) |
| `Fewshot_llm/MANUAL_TUNING_GUIDE.md` | Official tuning manual |

---

## §2 — Behavior dispatch tuning (Phase 2)

### §2.1 — `behavior_dispatch_rules.json`

Per-category thresholds, cooldown windows, suppression rules. Targets: 10-20% dispatch rate, 80-90% journal-only/suppressed.

### §2.2 — `BehaviorInterpreter` heuristics + `CooldownArbiter` window + `MixedTriggerArbiter` window + `PresenceDriftDetector` thresholds

See `world_system/wns/behavior_interpreter.py`, `mixed_trigger_arbiter.py`, `presence_drift_detector.py`.

---

## §3 — Scope discipline

### §3.1 — Planner scope prose

`world_system/config/prompt_fragments_wes_execution_planner.json` → `_core.system`:
- `SCOPE BY FIRING TIER` (narrative permission table)
- `SCOPE BY BEHAVIOR THRESHOLD` (Phase 2 behavior permission table)

### §3.2 — Orchestrator runtime caps

`world_system/wes/wes_orchestrator.py`: `DEFAULT_RERUN_BUDGET=2`, `MAX_RUNTIME_CASCADE_DEPTH`, `MAX_CASCADE_STEPS_PER_PASS`.

---

## §4 — Combat & enemies (from parallel-agent canvass)

### §4.1 — Files most-tuned-by-designer

- `Definitions.JSON/hostiles-1.JSON` — 21 special abilities + 13 enemies (stats, drops, aiPattern)
- `Definitions.JSON/hostiles-testing-integration.JSON` — 3 test bosses (void_archon, storm_titan, inferno_drake)
- `Definitions.JSON/combat-config.JSON` — EXP rewards, safe zone, 7 spawn-density bands, respawn timers
- `Definitions.JSON/tag-definitions.JSON` — Master tag library: per-status-effect duration/tick/magnitude, geometry defaults (chain/cone/circle/beam), special tag params (lifesteal %, knockback distance)
- `Definitions.JSON/stats-calculations.JSON` — Master weapon/defense/attack-speed/range formulas; per-tier multipliers
- `Definitions.JSON/dungeon-config-1.JSON` — Per-dungeon-rarity mob count, wave count, tier weights, EXP multiplier, chest loot tables
- `recipes.JSON/recipes-adornments-1.json` — 14+ enchantment definitions (effect.type/value/duration, conflict groups, applicable slots, stack limits)
- `Definitions.JSON/visual-config.JSON` — Telegraph/feedback timings, damage-number lifetimes, screen-shake decay

### §4.2 — Files mostly code-internal with tunables

- `Combat/combat_manager.py` (2505 lines) — `CombatConfig.density_weights` (line 40-46), boss EXP cap, MAX_PER_CHUNK enemy cap (line 407), default crit-chance 0.10 (line 729)
- `Combat/enemy.py` — `_CATEGORY_BASE_SIZE`, `_TIER_SIZE_MULTIPLIER`, visual size formula, `chance_map` (guaranteed/high/moderate/low/rare/improbable → float)
- `Combat/attack_state_machine.py`, `hitbox_system.py`, `projectile_system.py`, `attack_profile_generator.py`, `combat_data_loader.py`, `player_actions.py`
- `entities/status_effect.py` (826 lines) — per-status-effect tick rates, durations, magnitudes, stack rules
- `core/effect_executor.py` (623 lines) — tag-based combat effect dispatch
- `core/tag_system.py`, `core/tag_parser.py`

### §4.3 — Combat tunables (selected — full per-enemy catalog in `hostiles-1.JSON`)

| Domain | Control | Path | Current | Priority |
|---|---|---|---|---|
| Damage formula | Crit multiplier | `combat-config.JSON > damageFormulas.critMultiplier` | 2.0 | P0 |
| Damage formula | Shield max damage reduction cap | `combat-config.JSON > shieldMechanics.maxDamageReduction` | 0.75 (75%) | P0 |
| Damage formula | Damage variance range | `stats-calculations.JSON > damageSystem.varianceRange` | 0.85 / 1.15 | P0 |
| Damage formula | Per-weapon-type multipliers | `damageSystem.typeMultipliers` (8 types) | varies | P1 |
| Damage formula | Per-weapon-subtype multipliers | `damageSystem.subtypeMultipliers` (28 subtypes) | varies | P1 |
| Defense | Per-slot multiplier | `defenseSystem.slotMultipliers` | head 0.8, chest 1.5, legs 1.2, feet 0.7, hands 0.6 | P0 |
| Attack speed | Per-type / per-subtype mults | `attackSpeedSystem.{type,subtype}Multipliers` | 8 / 21 entries | P1 |
| Combat config | Base attack cooldown | `combat-config.JSON > combatMechanics.baseAttackCooldown` | 1.0s | P0 |
| Combat config | Tool attack cooldown | same > `toolAttackCooldown` | 0.5s | P1 |
| Combat config | Player attack range | same > `playerAttackRange` | 2.0 tiles | P0 |
| Combat config | Combat timeout | same > `combatTimeout` | 5.0s | P1 |
| Combat config | Enemy corpse lifetime | same > `enemyCorpseLifetime` | 60s | P2 |
| Combat config | Boss EXP multiplier | `experienceRewards.bossMultiplier` | 10.0 | P0 |
| Combat config | Per-enemy-tier EXP | `combat-config.JSON > experienceRewards` | T1:100 / T2:400 / T3:1600 / T4:6400 | P0 |
| Combat config | Spawn density bands | `combat-config.JSON > spawnDensity` | 7 bands | P1 |
| Combat config | Density weights | `Combat/combat_manager.py:40-46 CombatConfig.density_weights` | (hardcoded) | P1 |
| Combat config | MAX_PER_CHUNK enemy cap | `Combat/combat_manager.py:407` | varies | P1 |
| Per-enemy | Health / damage range / defense / speed / aggro / attack speed | `hostiles-1.JSON > enemies[].stats` | per-enemy | P0 |
| Per-enemy | AI pattern (default_state, aggro_on_damage, aggro_on_proximity, flee_at_health, call_for_help_radius, pack_coordination) | `hostiles-1.JSON > enemies[].aiPattern` | per-enemy | P0 |
| Per-enemy | Drops (materialId, quantity, chance) | `hostiles-1.JSON > enemies[].drops[]` | per-enemy | P0 |
| Per-enemy | Special abilities | `hostiles-1.JSON > enemies[].specialAbilities[]` | per-enemy | P0 |
| Special ability defs | Trigger conditions, cooldowns, params (21 abilities) | `hostiles-1.JSON > abilities[]` | per-ability | P0 |
| Visual size | Category base size | `Combat/enemy.py:129-139 _CATEGORY_BASE_SIZE` | beast 1.0, dragon 1.5, etc. | P1 |
| Visual size | Tier size multiplier | `Combat/enemy.py:142-147 _TIER_SIZE_MULTIPLIER` | T1:1.0 / T4:3.0 | P1 |
| Visual size | Min/max clamp | `Combat/enemy.py:157` | 1.0 / 8.0 | P2 |
| Drop chance map | Qualitative → float | `Combat/enemy.py:177-184` | guaranteed=1.0 ... improbable=0.05 | P1 |
| Status effects (DoT) | Burn duration, tick rate, damage/tick | `tag-definitions.JSON > tags.burn.{duration, tick_rate, damage_per_tick}` | designer | P0 |
| Status effects (DoT) | Bleed, Poison, Shock — same shape | `tag-definitions.JSON > tags.{bleed, poison, shock}` | designer | P0 |
| Status effects (CC) | Freeze, Stun, Root, Slow/Chill durations | `tag-definitions.JSON > tags.{freeze, stun, root, chill}` | designer | P0 |
| Status effects (Buffs) | Empower, Fortify, Haste, Regen, Shield magnitudes | `tag-definitions.JSON > tags.{empower, fortify, haste, regen, shield}` | designer | P0 |
| Status effects (Debuffs) | Vulnerable, Weaken magnitudes | `tag-definitions.JSON > tags.{vulnerable, weaken}` | designer | P0 |
| Geometry tags | Chain range, count | `tag-definitions.JSON > tags.chain.{range, count}` | designer | P1 |
| Geometry tags | Cone angle, range | `tag-definitions.JSON > tags.cone.{angle, range}` | designer | P1 |
| Geometry tags | Circle radius | `tag-definitions.JSON > tags.circle.radius` | designer | P1 |
| Geometry tags | Beam length | `tag-definitions.JSON > tags.beam.length` | designer | P1 |
| Special tags | Knockback distance | `tag-definitions.JSON > tags.knockback.distance` | designer | P1 |
| Special tags | Lifesteal percentage | `tag-definitions.JSON > tags.lifesteal.percent` | designer | P1 |
| Special tags | Execute threshold | `tag-definitions.JSON > tags.execute.threshold` | designer | P1 |
| Special tags | Reflect percent | `tag-definitions.JSON > tags.reflect.percent` | designer | P1 |
| Enchantments | Sharpness I-III damage_multiplier | `recipes-adornments-1.json > enchantments.sharpness_*.effect.value` | designer | P0 |
| Enchantments | Protection I-III defense_multiplier | `recipes-adornments-1.json > enchantments.protection_*.effect.value` | designer | P0 |
| Enchantments | Efficiency I-II gathering_speed | same | designer | P0 |
| Enchantments | Fortune I-II bonus_yield_chance | same | designer | P0 |
| Enchantments | Unbreaking I-II durability_multiplier | same | designer | P0 |
| Enchantments | Fire Aspect / Poison damage_over_time | same | designer | P0 |
| Enchantments | Swiftness movement_speed_multiplier | same | designer | P0 |
| Enchantments | Thorns reflect_damage | same | designer | P0 |
| Enchantments | Knockback distance | same | designer | P0 |
| Enchantments | Lifesteal percent | same | designer | P0 |
| Enchantments | Health Regen rate | same | designer | P0 |
| Enchantments | Frost Touch slow params | same | designer | P0 |
| Enchantments | Chain Damage propagation | same | designer | P0 |
| Enchantments | Conflicts / stack limits | `recipes-adornments-1.json > enchantments.*.{conflictsWith[], stackable, applicableTo[]}` | per-enchant | P1 |

---

## §5 — Crafting, minigames, recipes, calculators

**~300 individual tunables.** The parallel-agent report identified by far the densest tuning surface in the game. Full table in agent report; selected highlights below.

### §5.1 — Files most-tuned-by-designer (P0)

- `core/difficulty_calculator.py` (808 lines) — all per-discipline difficulty bands, tier point values, difficulty cutoffs, parameter dicts (SMITHING_PARAMS, REFINING_PARAMS, ALCHEMY_PARAMS, ENGINEERING_PARAMS, ENCHANTING_PARAMS)
- `core/reward_calculator.py` (607 lines) — Quality tier cutoffs, max multiplier ceiling, failure-penalty bands, first-try bonus, per-discipline reward shaping
- `Definitions.JSON/fishing-config.JSON` — Fully JSON-driven fishing knobs (pond, ripples, tolerance, quality tiers, stat effects, XP, durability)
- `Definitions.JSON/crafting-stations-1.JSON` — Station tier definitions (forge/refinery/alchemy_table/engineering_bench/enchanting_table T1-T4). **MISSING T3/T4 for refinery/alchemy/engineering/enchanting.**
- `Crafting-subdisciplines/rarity-modifiers.JSON` — Per-category × rarity stat bonuses
- All `recipes.JSON/*.JSON` — 155 recipes (5 files: smithing 53, refining 43, alchemy 18, engineering 16, adornments 25)
- All `placements.JSON/*.JSON` — 193 placements (5 files)

### §5.2 — Difficulty/reward selected tunables (P0)

| Domain | Control | Path | Current |
|---|---|---|---|
| Difficulty | T1-T4 material point values | `core/difficulty_calculator.py:36-39` | 1, 2, 3, 4 |
| Difficulty | Common band | `core/difficulty_calculator.py:48` | (0, 4) |
| Difficulty | Uncommon band | `core/difficulty_calculator.py:49` | (5, 10) |
| Difficulty | Rare band | `core/difficulty_calculator.py:50` | (11, 20) |
| Difficulty | Epic band | `core/difficulty_calculator.py:51` | (21, 40) |
| Difficulty | Legendary band | `core/difficulty_calculator.py:52` | (41, 150) |
| Difficulty | Diversity slope per unique material | `core/difficulty_calculator.py:204` | +0.10 per unique |
| Difficulty | Refining station-tier multiplier | `core/difficulty_calculator.py:350` | 1.0 + tier×0.5 (T1=1.5x ... T4=4.5x) |
| Difficulty | Alchemy tier exponential base | `core/difficulty_calculator.py:422` | 1.2^(avg_tier-1) |
| Difficulty | Alchemy volatility weight | `core/difficulty_calculator.py:428` | 0.3 (max +30%) |
| Difficulty | Engineering slot modifier slope | `core/difficulty_calculator.py:577` | +0.05 per slot |
| Reward | Min/max difficulty (normalization) | `core/reward_calculator.py:24-25` | 1.0 / 80.0 |
| Reward | Min/max reward multiplier | `core/reward_calculator.py:30-31` | 1.0 / 2.5 |
| Reward | Quality tier Normal | `core/reward_calculator.py:36` | 0.00-0.25 |
| Reward | Quality tier Fine | `core/reward_calculator.py:37` | 0.25-0.50 |
| Reward | Quality tier Superior | `core/reward_calculator.py:38` | 0.50-0.75 |
| Reward | Quality tier Masterwork | `core/reward_calculator.py:39` | 0.75-0.90 |
| Reward | Quality tier Legendary | `core/reward_calculator.py:40` | 0.90-1.01 |
| Reward | Failure min/max material loss | `core/reward_calculator.py:45-46` | 0.30 / 0.90 |
| Reward | First-try bonus | `core/reward_calculator.py:51` | +0.10 |

### §5.3 — Per-discipline minigame parameters (P0)

Each discipline has its own `_PARAMS` dict in `difficulty_calculator.py` with easy→hard interpolation. The full per-discipline parameter table (Smithing 17, Refining 12, Alchemy 16, Engineering 19, Enchanting 26 entries) lives in the agent report.

Key knobs per discipline:

- **Smithing**: time limit (60→25s), temperature range width (25°→3°), temp decay (0.3→0.6 per 100ms), fan increment, hammer hit count, target zone width, hammer oscillation speed (3.0→14.0)
- **Refining**: time limit (45→15s), cylinder count (3→12), timing window (0.05→0.01s), rotation speed (1.0→4.0), allowed failures (2→0), hub-and-spoke slot config T1-T4
- **Alchemy**: time limit (60→20s), reaction count (2→6), sweet-spot duration (2.0→0.4s), stage duration (2.5→0.8s), false-peak count (0→5), volatility band (0.0→1.0), per-type stage durations
- **Engineering**: time limit (300→120s), puzzle count (1→2), grid size (3→4), complexity (1→3), hints (4→1), ideal moves band, **per-tier failure penalty (0.30/0.45/0.60/0.75/0.90)** — diverges from global formula
- **Enchanting**: starting currency 100, green slices (12→6), red slices (3→10), green mult (1.5→1.2), red mult (0.8→0.0), per-spin multiplier table (3 spins), efficacy cap ±50%, rarity multipliers (C1.0/U1.1/R1.2/E1.35/L2.0)

### §5.4 — Fishing knobs (`fishing-config.JSON`)

All 31 fishing tunables are JSON-driven. Key items:
- Base ripple count, target radius, expand speed (px/s), hit tolerance (px), spawn delay (s)
- Per-quality-tier scoring (perfect/good/fair tolerances and scores)
- Per-tier ripple/speed scaling
- Per-tier respawn (30/45/60/90s)
- XP per tier (100/400/1600/6400)
- Stat effects (LCK ripple reduction, STR tolerance bonus, rod tier speed)

### §5.5 — Crafting LLM config (`llm_item_generator.py`)

| Setting | Path | Current |
|---|---|---|
| Default model | `systems/llm_item_generator.py:84` | claude-sonnet-4-20250514 |
| max_tokens | line 85 | 2000 |
| temperature | line 86 | 0.4 |
| top_p | line 87 | 0.95 |
| timeout (s) | line 88 | 30.0 |
| cache_enabled | line 93 | True |
| max_few_shot_examples | line 97 | 3 |
| Loading-state smooth progress duration | line 109 | 15.0s |

### §5.6 — Crafting classifier (mostly LOCKED — retraining required)

Model paths and thresholds in `systems/crafting_classifier.py:1011-1047`. Threshold 0.5 uniform across 5 disciplines. Re-train via `Scaled JSON Development/train_all_classifiers.py`.

### §5.7 — Known content gaps

- **T3/T4 stations missing** for refinery, alchemy_table, engineering_bench, enchanting_table (`crafting-stations-1.JSON` only defines T1-T2)
- Engineering has 2 placeholder puzzle types (`TrafficJamPuzzle`, `PatternMatchingPuzzle`)
- Enchanting `PatternMatchingMinigame` and `EnchantingMinigame` (freeform) may be dead code — `create_minigame` returns `SpinningWheelMinigame`

### §5.8 — Duplicate-constant traps (FIX BEFORE TUNING)

- `DIFFICULTY_RANGES` (min_points=1.0, max_points=80.0) in BOTH `difficulty_calculator.py:57-58` AND `reward_calculator.py:24-25`
- `RARITY_TIERS` hardcoded in 4 places (refining.py:514, enchanting.py:1304-1310, crafting_tag_processor.py:485, rarity_utils.py:248-254)
- "First-try bonus" defined 3 places with different values (smithing +0.10, engineering +0.05, enchanting +0.10)
- Refining rarity-upgrade thresholds (4/16/64/256 → +1/2/3/4 tiers) duplicated in refining.py:519-527 AND reward_calculator.py:251-260

---

## §6 — World gen, chunks, biomes, dungeons, ecosystem

### §6.1 — Files most-tuned-by-designer

- **`Definitions.JSON/dungeon-config-1.JSON`** — **dungeon content** (per-rarity mob counts, tier weights, EXP multipliers, full chestLoot.tierTables). v3.1 "fully self-contained per rarity." **High-leverage P0 file** that v1 of this map missed entirely.
- `Definitions.JSON/world_generation.JSON` — chunk load radius, biome distribution, danger zones, safe zone, resource counts per danger tier, water-chunk subtype mix, **dungeon ENTRANCE spawn placement** (`spawn_chance_per_chunk`, `min_distance_from_spawn`), chunk-unloading toggles
- `Definitions.JSON/Chunk-templates-2.JSON` — 22 biome templates: resourceDensity, enemySpawns, rollWeight, adjacencyPreference, edgeOnly, minDistanceBetween, tilePattern (waterCoverage, hasIslands, shoreWidth, riverWidth, isToxic)
- `Definitions.JSON/resource-node-1.JSON` — 36 resource nodes (baseHealth, requiredTool, drops, respawnTime)
- `Definitions.JSON/village-config.JSON` — village placement (target_count=2500, min_distance=8), tier-by-danger weights, 5 tier definitions, walls.base_health, NPC templates with spawn_weight, naming prefix/suffix lists
- `Definitions.JSON/map-waypoint-config.JSON` — map zoom range, biome colors, marker shapes/colors/sizes, waypoint unlock schedule, teleport conditions

### §6.2 — Dungeons (user explicitly flagged — full coverage)

Per `dungeon-config-1.JSON`:

| Domain | Control | Current |
|---|---|---|
| Per-rarity definition | mob count per rarity | designer table |
| Per-rarity | wave count | designer table |
| Per-rarity | enemy tier weights | designer table |
| Per-rarity | EXP multiplier | 2.0x (per CLAUDE.md) |
| Per-rarity | chest loot tier tables | designer-authored |
| Per-rarity | drop modifiers (or no-drops flag in some) | varies |
| Entrance | spawn_chance_per_chunk | designer |
| Entrance | min_distance_from_spawn | designer |
| Per-rarity | difficulty curve | designer |

`systems/dungeon.py` (DungeonManager) carries Python-side dungeon runtime constants. The user flagged this domain so it deserves dedicated playtest tuning.

### §6.3 — World generation tunables

| Domain | Control | Path | Current |
|---|---|---|---|
| World | Tile size, chunk size | `core/config.py` | 16 tiles/chunk standard |
| World | World dimensions | `core/config.py` / `world_generation.JSON` | 100x100 tiles |
| Chunks | Load radius | `world_generation.JSON` | designer |
| Chunks | Safe zone radius around spawn | same | designer |
| Chunks | Biome distribution weights | same | varies |
| Chunks | Danger zone bands (4-5 named) | same | designer |
| Chunks | Resource count per danger tier | same | designer |
| Chunks | Water-chunk subtype mix | same | designer |
| Chunks | Chunk-unloading toggle | same | bool |
| Chunks | Per-chunk-template rollWeight | `Chunk-templates-2.JSON > templates[].rollWeight` | per-template |
| Chunks | Per-chunk resource density | `templates[].resourceDensity` (very_low → very_high) | per-resource |
| Chunks | Per-chunk enemy spawns + tier | `templates[].enemySpawns` | per-enemy |
| Chunks | Adjacency preference | `templates[].adjacencyPreference` | per-template |
| Chunks | minDistanceBetween (rare biomes) | `templates[].minDistanceBetween` | per-template |
| Chunks | tilePattern (water/shore/river) | `templates[].tilePattern` | per-template |
| Chunks | Density → weight mapping | `templates[].metadata.densityWeights` (or schema docs) | 0.5x / 0.75x / 1.0x / 2.0x / 3.0x |
| Resource nodes | Per-node baseHealth | `resource-node-1.JSON > nodes[].baseHealth` | per-tier 100/200/400/800 |
| Resource nodes | Per-node requiredTool | `resource-node-1.JSON > nodes[].requiredTool` | per-node |
| Resource nodes | Per-node drops (materialId, qty, chance) | `resource-node-1.JSON > nodes[].drops[]` | per-node |
| Resource nodes | Per-node respawnTime (quick/fast/normal/slow/very_slow) | `resource-node-1.JSON > nodes[].respawnTime` | per-node |
| Respawn map | Token → seconds | `data/models/resources.py:55-61` | quick=30, fast=30, normal=60, slow=120, very_slow=300 |
| Villages | target_count, min_distance | `village-config.JSON > placement` | 2500, 8 |
| Villages | Tier weights by danger | `village-config.JSON > tier_weights_by_danger` | designer |
| Villages | 5 tier definitions | `village-config.JSON > tiers[]` | designer |
| Villages | Wall base_health | `village-config.JSON > walls.base_health` | designer |
| Villages | NPC templates + spawn_weight | `village-config.JSON > npc_templates[]` | designer |
| Villages | Naming prefix/suffix lists | `village-config.JSON > naming` | designer |
| Map | Zoom range | `map-waypoint-config.JSON > map.zoom_range` | designer |
| Map | Biome colors | `map-waypoint-config.JSON > biome_colors` | designer |
| Map | Marker shapes/colors/sizes | `map-waypoint-config.JSON > markers` | designer |
| Map | Waypoint unlock schedule | `map-waypoint-config.JSON > waypoint_unlocks` | designer |
| Map | Teleport conditions | `map-waypoint-config.JSON > teleport` | designer |
| Initial enemies | Spawn count at start | `game_engine.py:228` | 5 |
| Ecosystem | Scarcity thresholds (scarce, critical) | `ecosystem-config.json > scarcity_thresholds` | 0.7 / 0.9 |
| Ecosystem | Regeneration rates per token | `ecosystem-config.json > regeneration_rates` | 0/120/300/600/1200s |
| Ecosystem | Biome resource defaults (6 biomes) | `ecosystem-config.json > biome_resource_defaults` | designer |
| Ecosystem | Tick interval | `ecosystem-config.json > tick_interval_game_seconds` | 60.0 |

---

## §7 — Progression: classes, titles, skills, equipment

**212 individual tunables.** Full table in the agent report.

### §7.1 — Files most-tuned-by-designer

- `Definitions.JSON/stats-calculations.JSON` — master stat-effect formulas (lines 371-471 hold the 6 character stat modifiers + tier multipliers + variance ranges)
- `Definitions.JSON/skills-translation-table.JSON` — duration/mana/cooldown enums, max skill level, skill EXP curve, level scaling
- `Skills/skills-base-effects-1.JSON` — 10 base effect types × 4 magnitude rungs (canonical magnitude table)
- `Skills/skills-skills-1.JSON` — 30 skill defs
- `Update-2/skills-fishing.JSON` + `skill-unlocks-fishing.JSON` + `titles-fishing.JSON` — fishing progression suite
- `progression/classes-1.JSON` — 6 starting classes (startingBonuses, tags, preferredDamageTypes)
- `progression/titles-1.JSON` — title defs + `difficultyTiers` table
- `progression/skill-unlocks.JSON` — per-skill unlock methods (automatic / quest_reward / milestone_unlock / title_unlock)
- `Definitions.JSON/value-translation-table-1.JSON` — qualitative descriptors (yield, respawn, chance, density, tier bias, per-tier node HP, per-tier tool damage+durability)

### §7.2 — Core progression numbers (P0)

| Domain | Control | Path | Current |
|---|---|---|---|
| Leveling | Player max level | `entities/components/leveling.py:8` | 30 |
| Leveling | EXP formula | `entities/components/leveling.py:9` | 200 × 1.75^(level-1) |
| Leveling | Stat points per level | `entities/components/leveling.py:23` | +1 |
| Skill leveling | Per-skill max level | `data/models/skills.py:98` | 10 |
| Skill leveling | Skill EXP curve | `data/models/skills.py:101` | 1000 × 2^(level-1) |
| Skill leveling | EXP per skill use | `skill_manager.py:258,903` | 100 |
| Skill leveling | Per-level scaling | `skills-base-effects-1.JSON > skillProgressionSystem.levelScaling` | +10%/level |

### §7.3 — Character stat magnitudes (P0)

All in `stats-calculations.JSON > characterStatModifiers`:

| Stat | Effect | Current |
|---|---|---|
| STR | Melee damage / mining damage per point | 0.05 (5%) |
| STR | Inventory slots per point | 10 |
| DEF | Damage reduction per point | 0.02 |
| DEF | Armor effectiveness per point | 0.03 |
| VIT | Max HP per point | 15 |
| VIT | Health regen per point | 0.01 (1%) |
| LCK | Crit chance per point | 0.02 |
| LCK | Resource quality per point | 0.02 |
| LCK | Rare drop chance per point | 0.03 |
| AGI | Forestry damage per point | 0.05 |
| AGI | Attack speed per point | 0.03 |
| INT | Max mana per point | 20 |
| INT | Minigame difficulty reduction per point | 0.02 |
| INT | Max effective INT | 30 |

**Source-of-truth conflict**: `entities/components/stats.py:17-29` hardcodes the same values; the JSON values may not be read by code. **Verify before tuning via JSON.**

### §7.4 — Base resources (P0)

| Domain | Control | Path | Current |
|---|---|---|---|
| HP | Base max | `entities/character.py:113` | 100 |
| Mana | Base max | `entities/character.py:114` | 100 |
| Inventory | Base slots | `entities/components/inventory.py:110` | 30 |
| Carry | Base capacity | `entities/character.py:2245` | 100 |
| Health regen | Threshold | `entities/character.py:156` | 5.0s without combat |
| Health regen | Base rate | `entities/character.py:157` | 5 HP/s |
| Mana regen | Rate | `entities/character.py:1450` | 0.01 (1%/s) |
| Hotbar | Skill slots | `entities/components/skill_manager.py:19` | 5 |
| Equip | Slot count | `entities/components/equipment_manager.py:10-21` | 10 |

### §7.5 — Skills enum translation tables (P0)

`data/databases/skill_db.py:23-25`:
- mana_costs: low=30, moderate=60, high=100, extreme=150
- cooldowns (s): short=120, moderate=300, long=600, extreme=1200
- durations (s): instant=0, brief=15, moderate=30, long=60, extended=120

### §7.6 — Skill magnitude tables (P0)

`Skills/skills-base-effects-1.JSON > BASE_EFFECT_TYPES.*.magnitudeValues` (10 effect types × 4 rungs):
- empower: 0.5/1.0/2.0/4.0
- quicken: 0.3/0.5/0.75/1.0
- fortify: 10/20/40/80 (flat reduction)
- enrich: 1/3/6/12 (bonus items)
- pierce: 0.10/0.15/0.25/0.40 (crit chance)
- restore: 50/100/200/400 (flat HP)
- regenerate: 3/5/10/20 (per second)
- elevate: 0.15/0.25/0.40/0.60 (rarity upgrade chance)
- devastate: 3/5/7/10 (radius tiles)
- transcend: 1/2/3/4 (tiers bypassed)

Rarity multipliers: common 1.0 / uncommon 1.15 / rare 1.35 / epic 1.6 / legendary 2.0 / mythic 2.5

### §7.7 — Class system (P0)

6 starting classes in `progression/classes-1.JSON`. Per class: startingBonuses dict (stat/percent bonuses), tags, preferredDamageTypes, preferredArmorType, startingSkill, recommendedStats.

Class switching: cost 1000 gold (`metadata.switchingCost`), cooldown 0.

Skill affinity bonus per matching class tag: +0.05, max +0.20 (`data/models/classes.py:43-44`).

**Open question**: class starting skills reference IDs that don't exist in skills-skills-1.JSON (`battle_rage`, `forestry_frenzy`, etc.) — may be silently failing.

### §7.8 — Title system (P0)

`progression/titles-1.JSON`: per-title tier, bonuses dict, prerequisites.conditions list, acquisitionMethod (guaranteed_milestone / event_based_rng / hidden_discovery / special_achievement / random_drop), generationChance, isHidden.

`difficultyTiers` block (titles-1.JSON:256-286) — tier generation chances: novice 1.0, apprentice 0.20, journeyman 0.10, expert 0.05, master 0.02.

### §7.9 — Equipment & global formulas

`stats-calculations.JSON`:
- globalBases: weaponDamage 10, armorDefense 10, toolGathering 10, durability 250, weight 1.0, attackSpeed 1.0
- tierMultipliers: T1=1.0 / T2=2.0 / T3=4.0 / T4=8.0
- Damage variance: 0.85 / 1.15
- 8 weapon-type multipliers, 28 subtype multipliers
- 5 defense slot multipliers (head 0.8 / chest 1.5 / legs 1.2 / feet 0.7 / hands 0.6)
- Consumable scaling per tier
- Turret / bomb / trap damage formulas

### §7.10 — Weapon tag modifiers (`weapon_tag_calculator.py`)

- 2H damage +20%
- versatile (no offhand) damage +10%
- fast attack speed +15%
- precision crit +10%
- reach range +1.0
- armor_breaker armor pen 25%
- crushing vs armored +20%
- cleaving 50% adjacent damage

### §7.11 — Crafted-stat curves (from minigames)

`entities/components/crafted_stats.py:90-128`:
- Quality → durability multiplier: (quality-50)/100 → -0.5..+0.5
- Quality → damage multiplier: -0.5..+0.5
- Quality → attack speed: +0..+0.20 / -0.10..0 (split)
- Quality → defense: -0.5..+0.5
- Quality → block chance: +0..+0.10 / -0.05..0
- Quality → tool efficiency: 0.5..1.5

### §7.12 — Stat tracker (65 record_* methods)

Full list in agent report. Categories: Gathering, Crafting, Combat (offense/defense), Status effects, Items, Skills, Movement/Exploration, Economy, Progression, Dungeons, NPC/Quest, Building, Equipment, Session, Meta.

### §7.13 — Duplicate-constant traps in progression

- Magnitude tables in 3 places (skills-base-effects-1.JSON, skills-translation-table.JSON, skill_manager.py:42-46 hardcoded fallback)
- Mana/cooldown/duration enums in skill_db.py:23-25 (Python win) AND skills-translation-table.JSON (descriptive)
- Per-stat magnitudes in stats-calculations.JSON AND stats.py:17-29 (Python win)
- Class `tags` → tool efficiency hardcoded in class_system.py:53-76

### §7.14 — Known broken references

- Class starting skills reference non-existent skill IDs
- skill-unlocks.JSON references quests/titles that may not exist (tutorial_quest, gathering_quest, master_gatherer, etc.)
- `combat_tags` / `combat_params` on skills unpopulated in skills-skills-1.JSON — tag-based combat skill path dormant
- `additionalEffects` nested-effect arrays parsed into model but likely not iterated when applying buffs

---

## §8 — WMS, factions, NPC dialogue runtime, LLM backend chain

**250 individual tunables.** Full table in agent report.

### §8.1 — Files most-tuned-by-designer

- `world_system/config/memory-config.json` — WMS retention, layer 3/4/5/6/7 thresholds, all 33 evaluator parameters
- `world_system/config/backend-config.json` — Backend chain, model IDs, per-task routing, fallback chain, rate limits
- `world_system/config/narrative-config.json` — WNS cascade threshold (3), WMS-context budgets, distance filter, weaver caps
- `world_system/config/faction-definitions.json` — Faction dictionary (placeholder — will be overhauled)
- `world_system/config/faction-archetypes.json` — 7 NPC archetypes (suggested tags + significance + affinity_notes)
- `world_system/config/affinity-defaults.json` — Hierarchical affinity baselines (world → nation → region → district → locality)
- `world_system/config/npc-personalities.json` — 6 personality templates (voice, reactions, gossip interests), gossip timings, memory limits, relationship thresholds
- `world_system/config/stat-key-manifest.json` — 374 stat name patterns → tags + descriptions
- `world_system/config/tag-registry.json` — 40 base faction tags with human_gloss + aliases
- `world_system/config/layer1-stat-tags.json` — Alternate stat-tag mapping (may overlap with manifest)
- `world_system/config/ecosystem-config.json` — Scarcity, regeneration, biome defaults (sidelined — REFRAMING CANDIDATE)
- `progression/npcs-3.JSON` — Per-NPC static data
- `progression/quests-3.JSON` — Quest defs

### §8.2 — WMS layer cascade thresholds (P0)

`memory-config.json`:
- L3: trigger_interval=15, min_l2_per_district=3, min_categories=2
- L4: trigger_threshold=50 (tag-weighted points), max_l3_per_province=50
- L5: trigger_threshold=100, max_l4_per_region=50
- L6: trigger_threshold=200, max_l5_per_nation=40
- L7: trigger_threshold=200, max_l6_per_world=20

### §8.3 — WMS triggers (P0)

`world_memory/trigger_manager.py`:
- THRESHOLDS: [1, 3, 5, 10, 25, 50, 100, 250, 500, 1000, 2500, 5000, 10000, 25000, 100000]
- EVENT_CATEGORY_MAP: 35 event_type → category mappings
- _EXCLUDED_CATEGORIES: {"other"}

### §8.4 — WMS retention/pruning (P0)

`memory-config.json > retention`:
- prune_age_threshold: 50.0 (game-time)
- timeline_window: 1.0
- prune_interval: 10.0
- power_of_10_milestones: [100, 1000, 10000, 100000]

### §8.5 — 33 Layer-2 evaluators

All configurable via `memory-config.json > evaluators.<name>`. Key parameters per evaluator:
- lookback_time, expiration_offset
- thresholds (5-tier severity bands)
- narrative_templates (4 severity templates per evaluator)
- high_quality_types, lookback windows

**Divergent defaults** (P0 reconciliation needed):
- `progression_skills` — py `{1, 20, 50, 100}` vs JSON `{1, 10, 50, 200}`
- `exploration_territory` — py `{1, 20, 50, 100}` vs JSON `{1, 10, 30, 100}`
- `social_npc` — py `{1, 10, 30, 75}` vs JSON `{1, 5, 15, 50}`
- `combat_kills_regional_low_tier` — py lookback=100 vs JSON 50

**Evaluators not in memory-config.json (py-only)**:
- `faction_reputation` (lookback=300, min_delta=5.0)
- `ecosystem_resource_depletion` (4-rung thresholds in py)

### §8.6 — WNS cascade + distance filter (P0)

`narrative-config.json`:
- cascade.threshold: 3 (the single biggest WNS tuning knob — geometric)
- wms_context.char_budget_per_fire: 600
- distance_filter.char_caps: full=600 / brief=240 / fading=120 per row
- weaver_caps.max_threads_per_fragment: per-layer dict (nl2:3 → nl7:1)
- weaver_caps.max_wes_calls_per_run: 2
- weaver_caps.max_emergent_entities: 2 per fragment / 5 per run

### §8.7 — Backend chain (P0)

`backend-config.json`:
- Ollama: base_url, default_model (llama3.1:8b), timeout 30s
- Claude: model (claude-sonnet-4-20250514), max_tokens 2000, temperature 0.4, top_p 0.95, timeout 30s
- Fallback chain: [ollama, claude, mock]
- Rate limits: Ollama 2 concurrent / 100ms cooldown; Claude 1 / 1000ms; Mock 10 / 0

### §8.8 — Per-task backend routing (33 tasks) — P0

`backend-config.json > task_routing`. Selected:
- dialogue, lore, faction_narrative → ollama
- faction_dialogue, wms_layer2-7 → claude
- wns_layer2-4 → ollama; wns_layer5-7 → claude
- wes_execution_planner → claude; wes_supervisor → ollama
- wes_hub_* (all 8) → ollama
- wes_tool_npcs, wes_tool_quests → claude; other wes_tool_* → ollama
- wes_quest_reward_pregen → claude; wes_quest_reward_adapt → ollama

### §8.9 — Env-flag toggles (P0)

- `WES_DISABLE_FIXTURES` — bypass Fixture Registry into real backends
- `WES_REQUIRE_REAL_LLM` — strip MockBackend; surface visible failure
- `WES_VERBOSE` — stream live pipeline events to stdout
- `ANTHROPIC_API_KEY` — Claude API key (env or `.env`)

### §8.10 — NPC personalities (P0)

`npc-personalities.json`:
- 6 personality templates (voice, knowledge_domains, reaction_modifiers, gossip_interests, dialogue_style.max_response_length 120-250)
- gossip_propagation: immediate_radius 0, short_delay 1ch/60s, medium 4ch/180s, global 420s, minimum_significance 0.1
- memory_limits: max_knowledge=30, max_conversation_summary=500, relationship_decay_rate_per_day 0.001
- emotional_states: 13 values
- relationship_thresholds: 7-bin map -0.75..+0.75
- NPC agent dialogue temperature: 0.6 (hardcoded in npc_agent.py:176)

### §8.11 — Factions (placeholder — will be overhauled)

`faction-definitions.json`:
- 4 placeholder factions: village_guard, crafters_guild, forest_wardens, miners_collective
- Per-faction hostile_threshold (-0.5 to -0.75), allied_threshold (0.4 to 0.5)
- 4×4 inter-faction relationship matrix
- Reputation events per action type (ENEMY_KILLED, ITEM_CRAFTED, RESOURCE_GATHERED, LEVEL_UP) → per-faction deltas
- Reputation milestones: 6 entries -0.75 to +0.75
- Ripple config: ally_ripple 0.3 / enemy_ripple -0.2 / threshold 0.1

### §8.12 — Faction archetypes (P0)

`faction-archetypes.json`: 7 NPC archetypes (blacksmith/merchant/guard/mayor/fisher/scholar/wanderer). Per archetype: suggested_tags with significance (0.1-0.9), narrative_seed paragraph, affinity_notes.

### §8.13 — Affinity defaults (P0)

`affinity-defaults.json`: hierarchical baselines world → nation (4) → region (4) → district (4) → locality (4). Per level: 13 tag affinities.

### §8.14 — Per-NPC static data (P0)

`npcs-3.JSON > npcs[]`:
- narrative (immutable past)
- personality (per-NPC override of template)
- locality.home_chunk
- faction.primary + belonging_tags (tag, significance, role, narrative_hooks)
- affinity_seeds (tag → -100..100, includes `_player`)
- services (canTrade/canRepair/canTeach + teachableSkills)
- unlockConditions
- **speechbank**: greeting, farewell, idle_barks, quest_offer, quest_complete

### §8.15 — Per-quest static data (P0)

`quests-3.JSON > quests[]`:
- rewards (exp/gold/health/mana/skills/items/title/stat_points)
- rewards_prose (LLM-generated, resolved at accept time)
- requirements
- expiration
- progression (repeatable, cooldown, nextQuest, questChain)
- completion_dialogue (preferred over speechbank.quest_complete)
- objectives (type, items, count)

### §8.16 — Tag taxonomy / stats manifest (P0)

- `world_memory/tag_library.py:37-223` — Layer-1 closed enums (22 categories: domain, action, metric, actor, target, tier, element, quality, rarity, discipline, material_category, item_category, rank, attack_type, weapon_type, status_effect, slot, result, source, tool, class, title_tier)
- `tag_library.py:264-292` — Layer-2 closed enums (4: biome, scope, significance, resource_harvesting)
- `stat-key-manifest.json` — 374 stat name patterns (4800 lines)
- `layer1-stat-tags.json` — alternate mapping (may be redundant)

### §8.17 — Known structural issues

- 4 evaluators have divergent py/JSON defaults (reconciliation needed)
- 3 overlapping stat-tag sources (manifest vs layer1-stat-tags vs tag-registry)
- MockBackend.TEMPLATES (5 hardcoded fallback responses) can silently masquerade as real LLM unless `WES_REQUIRE_REAL_LLM=1`
- `_calculate_gossip_delay()` in npc_agent.py:425 ignores per-NPC distance — always returns short_delay (medium/global delay configs inert)
- Faction system flagged as throwaway placeholder
- Ecosystem flagged as REFRAMING CANDIDATE

---

## §9 — Rendering, animation, UI, audio, input

**~542 individual tunables** cataloged across 35 categories. Full unabridged tables at [Development-Plan/controls-agent-render-ui.md](Development-Plan/controls-agent-render-ui.md). Highlights below.

### §9.1 — Files most-tuned-by-designer

- **`Definitions.JSON/visual-config.JSON`** — Master VFX/animation timing JSON: damage numbers, telegraphs, particles, screen effects, entity visuals, enemy tier scale. **The first place to tune anything visual.**
- **`Definitions.JSON/map-waypoint-config.JSON`** — Map UI tuning: zoom, biome colors, marker icons, waypoint unlock, teleport cooldown, UI window size (and declarative keybindings — see §9.10 known issues)
- **`core/config.py`** — Hardcoded global constants: screen, FPS, tile size, viewport %, 76 UI colors (palette + RARITY_COLORS), debug flags
- **`animation/weapon_visuals.py`** — Tag→VFX tables (ELEMENT_COLORS, weapon type profiles, tier intensity). Python-coded, not JSON.

### §9.2 — Files mostly code-internal with tunables

- `rendering/renderer.py` (8029 lines) — many hardcoded layout numbers per UI panel, embedded `_ETAG_COLORS`, `_STATE_COLORS`, `_ELEMENT_COLORS`
- `rendering/visual_effect_bridge.py` — `_KILL_SHAKE` (per-tier) + `_TIER_COLORS` (per-tier)
- `rendering/terrain_renderer.py` — procedural tile color palettes + `_CACHE_MAX = 4096`
- `rendering/map_cache.py` — `ppc=4` pixels per chunk, border colors, blur radius
- `animation/combat_particles.py` — hit-spark/dodge-dust/trail counts, lifetimes, gravity, drag; `DAMAGE_SPARK_COLORS` per element
- `animation/procedural.py` — arc degrees / radius / num_frames / colors as function defaults
- `core/minigame_effects.py` — covered from VFX angle now (color palettes per discipline, particle pool 200, sparking/embers/bubbles/steam/spirit life ranges, screen-shake 5px/200ms default)
- `Combat/screen_effects.py` — afterimage life (300ms), shake/flash logic
- `Combat/player_actions.py` — dodge duration/cooldown/iframe duration/dodge speed mult (**hardcoded with "can be tuned via JSON" comment but no JSON wire** — see §9.10)
- `world_system/wes/observability_overlay.py` — F12 overlay color map, max_events=15, width=600
- `core/notifications.py` — `lifetime: float = 3.0` default
- `core/debug_display.py` — max_messages = 5

### §9.3 — Audio: NOT IMPLEMENTED

**Agent confirmed**: no `audio/`, `sound/`, `sfx/`, `music/` directory exists. No `pygame.mixer` usage anywhere. **Audio is entirely unimplemented**. No sound triggers, volume sliders, music params, UI click sounds. (Only `pygame.font` is initialized.) If audio is planned, the entire system would need to be built.

### §9.4 — Screen / engine / world / player constants (selected — `core/config.py`)

| Domain | Control | Path | Current | Priority |
|---|---|---|---|---|
| Screen | Default window W×H | `core/config.py:14-15` | 1600×900 | P1 |
| Screen | FPS cap | `core/config.py:16` | 60 | P0 |
| Screen | UI scale (auto-derived from height) | `core/config.py:20` | 1.0 | P1 |
| Viewport | Width % of screen | `core/config.py:95` | 75% | P1 |
| World | Chunk size (tiles) | `core/config.py:24` | 16 | P0 |
| World | Tile pixel size | `core/config.py:25` | 32 | P0 |
| World | Entity visual scale | `core/config.py:26` | 1.0 | P1 |
| World | Chunk load radius | `core/config.py:32` | 4 | P1 |
| World | Safe zone radius | `core/config.py:45` | 8 | P1 |
| Player | Speed (tiles/tick) | `core/config.py:151` | 0.15 | P0 |
| Player | Interaction range (tiles) | `core/config.py:152` | 3.5 | P0 |
| Player | Click tolerance | `core/config.py:153` | 0.7 | P1 |

### §9.5 — UI menu/inventory layout (P0/P1)

- Menu size presets: Small 600×500, Medium 800×600, Large 1000×700, XLarge 1200×750 (`config.py:111-118`, all scaled by UI_SCALE)
- Inventory slot pixel size: `INVENTORY_SLOT_SIZE=50` (scaled)
- Slots per row: auto-computed from width (currently 10)
- Slot spacing: hardcoded `10` in **4 separate places** (renderer.py:5063, game_engine.py:1401/2203/6903) — **see §9.10 cleanup**
- Equipment slot rendering, tool slot positions, weight bar (`renderer.py:4943-4978`)

### §9.6 — Color palette (76 controls — all P1/P2)

`core/config.py:164-199` defines 76 color constants:
- 28 standard UI colors (background, grid, biomes, health, slots, tooltips, etc.)
- RARITY_COLORS dict: common (200,200,200), uncommon (30,255,0), rare (0,112,221), epic (163,53,238), legendary (255,128,0), artifact (230,204,128)

### §9.7 — visual-config.JSON (the master VFX file)

Hundreds of knobs grouped:

| Group | Controls |
|---|---|
| `damageNumbers` | Lifetime (1200ms), velocity, gravity, shrink rate, crit scale, anti-stack offset, 9 type colors (physical/fire/ice/lightning/poison/arcane/shadow/holy/heal/shield), crit/miss/block/dodge text + colors |
| `entityVisuals` (player) | Render radius (0.33), body color (80,180,255 — overrides config.py's gold), outline, facing indicator, weapon arc preview/alpha, shadow alpha/scale, idle bob amplitude/period |
| `enemyVisuals` | Per-state indicators, tier scale multipliers, HP bar over body, boss glow color, state indicator colors |
| `telegraphs` | Pre-attack flash/charge/circle params, duration, alpha, ring colors |
| `particles` | Pool sizes, default lifetimes, spawn rates, gravity, drag |
| `screenEffects` | Shake intensity/duration, flash params, hit-pause (**dead code**) |
| `debug` | Debug hitbox visualization, debug line colors |

### §9.8 — Combat particles (`animation/combat_particles.py`)

Hit sparks: count, lifetime, gravity, drag. Dodge dust trail. `DAMAGE_SPARK_COLORS` per element (fire/ice/lightning/poison/arcane/shadow/holy/physical).

### §9.9 — Keybindings (all hardcoded in `game_engine.py`)

The agent enumerated **40+ bindings**. Selected:

| Key | Action | Path | Priority |
|---|---|---|---|
| W/A/S/D | Move | `game_engine.py:850-856` | P0 |
| SPACE | Dodge roll | `game_engine.py:843` | P0 |
| 1-5 | Skill hotbar slots | `game_engine.py:883-923` | P0 |
| Left/Right click | Attack/harvest, UI interaction / unequip hotbar | global | P0 |
| X | Block (held — shield/parry) | `game_engine.py:7352` | P0 |
| F | NPC interact / dungeon exit | `game_engine.py:824` | P0 |
| ESC | Close menu / quit | `game_engine.py:711` | P0 |
| TAB | Switch tool | `game_engine.py:767` | P1 |
| C / E / K / L / M / P | Stats / Equipment / Skills / Encyclopedia / Map / Place waypoint | various | P1 |
| Q | Drop item (Shift+Q = stack) | `game_engine.py:838` | P1 |
| F1 | Debug: infinite resources + maxed level/stats | `game_engine.py:924` | P1 |
| F2 | Debug: learn all skills | `game_engine.py:957` | P2 |
| F3 | Debug: grant all titles | `game_engine.py:997` | P2 |
| F4 | (Debug — implied max stats; agent didn't fully read body) | `game_engine.py:1030` | P2 |
| F5 | Toggle keep-inventory-on-death | `game_engine.py:1080` | P1 |
| F6 | Quick timestamped save | `game_engine.py:1094` | P2 |
| F7 | Toggle infinite durability | `game_engine.py:1113` | P2 |
| F8 | Enter/exit dungeon (Shift+F8 = biome debug) | `game_engine.py:1127` | P1 |
| F9 | Load autosave (Shift+F9 = default save) | `game_engine.py:1139` | P1 |
| F10 | Run automated test suite | `game_engine.py:1196` | P2 |
| F11 | Toggle fullscreen | `game_engine.py:1202` | P0 |
| F12 | Toggle WES observability overlay | `game_engine.py:1211` | P1 |
| MOUSEWHEEL | Map zoom / recipe scroll | `game_engine.py:1249` | P1 |

### §9.10 — Known structural issues in rendering/UI

These are bugs / dead code / duplication problems the agent identified. **Fix before tuning** — they cause silent breakages where designer changes don't propagate or actively conflict:

1. **5-source duplication of element→color**: `_ETAG_COLORS` (renderer.py:1347), `_ELEMENT_COLORS` (renderer.py:1811), `ELEMENT_COLORS` (weapon_visuals.py:18), `damageNumbers.typeColors` (visual-config.JSON), `DAMAGE_SPARK_COLORS` (combat_particles.py:22). Changing one ≠ changing the others.
2. **3-source duplication of enemy tier color**: `_TIER_COLORS` (visual_effect_bridge.py:32), `tier_colors` dict (renderer.py:1377), boss override at renderer.py:1380.
3. **3-source duplication of state colors**: `_STATE_COLORS` (renderer.py:1362) duplicates `enemyVisuals.stateIndicatorColors` (visual-config.JSON).
4. **Hit-pause is dead code**: `Combat/screen_effects.py:35` explicitly says "Time is always constant — freeze frames removed by design" but `visual_effect_bridge.py:113,135` still calls `hit_pause(40)` / `hit_pause(60)`. `visual-config.JSON` exposes `hitPauseEnabled` / `slowMotionEnabled` flags that do nothing.
5. **Tooltip z-order bug** (CLAUDE.md mention): `self.pending_tooltip` is set in `render_equipment_ui:6800` but the flush path is unclear. Deferred tooltips can be covered by chest/death/spawn-chest UIs.
6. **Enchantment selection UI not scaled**: `renderer.py:7143` uses raw `600, 500` instead of `Config.scale(...)`. Will appear tiny at 4K.
7. **Inventory slot spacing constant duplicated 4 places** with "Must match renderer spacing" comments. Tuning one breaks click-targeting.
8. **`map-waypoint-config.JSON` keybindings are decorative**: JSON declares `open_map: "M"`, `place_waypoint: "W"`, `zoom_in: "PLUS"` but `game_engine.py:807,820,1249` hardcodes K_m / K_p / MOUSEWHEEL. **`place_waypoint` JSON says "W" but code uses "P" — direct conflict.**
9. **Procedural animation defaults not in JSON**: all numbers in `animation/procedural.py` are Python function defaults. No `animation-config.json` exists.
10. **No per-skill VFX override**: element color comes from skill's first matching element tag; no per-skill particle count / lifetime / spread override possible.
11. **`bossGlowColor` in visual-config.JSON not actually read** (renderer.py:1380 hardcodes gold).
12. **Dodge fully Python-side**: `Combat/player_actions.py:74-77` hardcodes duration / speed / cooldown / iframe with "can be tuned via config/JSON" comment **but no JSON wire**.
13. **Fonts loaded once at Renderer init**: F11 fullscreen toggle doesn't refresh `self.font / self.small_font / self.tiny_font` — possible bug for dynamic UI scaling.
14. **`shrinkRate: 0.997`** per-frame at 60fps = ~0.3%/frame = ~20% total across 1200ms lifetime. Easy to mis-tune to invisibility.
15. **No "tile rendering distance" param** beyond `CHUNK_LOAD_RADIUS=4`. No fog of war / draw distance.
16. **Time-of-day / lighting NOT implemented** (confirmed).
17. **No status effect visualizers** (burn icon, freeze tint) — agent found no per-status visual config. Where would designer tune freeze-blue body tint duration?

### §9.11 — Open designer questions surfaced by the agent

1. Should `weapon_visuals.py` (ELEMENT_COLORS, weapon profiles, tier intensity) move to JSON? Big designer win.
2. Should `INVENTORY_SLOT_SPACING` be added to Config (currently 4× hardcoded)?
3. Dodge tuning: visual-config.JSON? combat-config.JSON? New file?
4. Tooltip z-order: is the intent that `pending_tooltip` flushes at frame-end? Where's the flush?
5. Map waypoint JSON keybindings: drive bindings or documentation-only? Either way, the "W vs P" conflict needs resolving.
6. Triple-coloring cleanup priority: fix the 5-source "fire = orange" duplication now or accept tech debt?

---

## §10 — Content allow-lists (per-tool vocabularies)

Carried over from v1:

- Materials: category [metal, wood, stone, elemental, monster_drop]; rarity [common, uncommon, rare, epic, legendary]; tag library in `prompt_fragments_tool_materials.json`
- Chunks: category [peaceful, dangerous, rare, water, rare_water]; theme [forest, quarry, cave, water]; density [very_low → very_high]; tierBias [low, mid, high, legendary]
- Resource node respawn map: `data/models/resources.py:55-61` — quick=30, fast=30, normal=60, slow=120, very_slow=300
- Skills enum translation tables: `data/databases/skill_db.py:23-25`
- Tag registry: `world_system/config/tag-registry.json` + `narrative-tag-definitions.JSON`

---

## §11 — Sacred content paths

Per-tool sacred file + generated glob + wrapper key:

| Tool | Sacred | Generated | Wrapper |
|---|---|---|---|
| materials | `items.JSON/items-materials-1.JSON` (+ 6 boot calls) | `items-materials-generated-*.JSON` | `materials` |
| hostiles | `Definitions.JSON/hostiles-1.JSON` | `hostiles-generated-*.JSON` | `enemies` |
| nodes | `Definitions.JSON/resource-node-1.JSON` | `Resource-node-generated-*.JSON` | `nodes` |
| skills | `Skills/skills-skills-1.JSON` | `skills-generated-*.JSON` | `skills` |
| titles | `progression/titles-1.JSON` | `titles-generated-*.JSON` | `titles` |
| chunks | `Definitions.JSON/Chunk-templates-2.JSON` | `Chunk-templates-generated-*.JSON` | `templates` |
| npcs | `progression/npcs-3.JSON` | `npcs-generated-*.JSON` | `npcs` |
| quests | `progression/quests-3.JSON` | `quests-generated-*.JSON` | `quests` |

---

## §12 — Designer tools

| Tool | Path | What it does |
|---|---|---|
| **Prompt Studio** | `tools/prompt_studio_main.py` | 33-task themed multi-panel editor |
| **F12 overlay** | `world_system/wes/observability_runtime.py` | Last-15 pipeline events + counters |
| **WES_VERBOSE env** | shell | Streams pipeline events to stdout |
| **WES_REQUIRE_REAL_LLM env** | shell | Guards against MockBackend masquerade |
| **Real-LLM smoketest** | `tools/wes_real_llm_smoketest.py` | Pre-playtest CLI: probe + round-trip |
| **F1-F7 debug keys** | game | F1 debug, F2 auto-learn skills, F3 grant titles, F4 max level, F7 infinite durability |

---

## §13 — Suggested tuning order (refined)

The order with most player-perceived impact per tuning hour:

1. **§1.3 `_game_context` WORLD TONE** — single block in `prompt_fragments.json`, every prompt reads it
2. **§1.1 `prose_ambiguity_directive`** — shared by all 8 tools
3. **§1.1 Per-layer voice (NL2 → NL7)** — 6 blocks, sets how each layer sounds
4. **§1.1 Per-purpose shape** — 8 blocks
5. **§3.1 Planner scope rules** (both `SCOPE BY FIRING TIER` + `SCOPE BY BEHAVIOR THRESHOLD`)
6. **§2.1 `behavior_dispatch_rules.json`** — tune dispatch cadence
7. **§1.5 Supervisor checks 7/8/9**
8. **§4 Combat tuning** — start with `combat-config.JSON` formulas, then per-enemy `hostiles-1.JSON`
9. **§6.2 Dungeon configs** — `dungeon-config-1.JSON` per-rarity tables (user-flagged priority)
10. **§5.2-§5.3 Crafting calculators** (difficulty + reward) + per-discipline param dicts
11. **§7.2-§7.3 Core progression** (EXP curve, stat magnitudes) — **first reconcile py/JSON duplication**
12. **§7.5-§7.6 Skill enums + magnitude tables** — first reconcile py/JSON duplication
13. **§8.2-§8.5 WMS thresholds + evaluator tunables** — first reconcile 4 divergent defaults
14. **§8.6 WNS cascade threshold** (single biggest WNS knob)
15. **§8.10 NPC personality templates** + gossip propagation
16. **§4.3 Status effect + enchantment tunables** (`tag-definitions.JSON`, `recipes-adornments-1.json`)
17. **§1.4 Per-tool prompts** (16 files) — update to use Phase 1 vars
18. **§1.2 Per-layer firing guidance** in NL fragments

---

## §14 — Companion docs

- `Development-Plan/feature-traces/00-consolidation.md` — the build plan + architectural conclusions
- `Development-Plan/feature-traces/11-trigger-taxonomy.md` — unification thesis
- `Development-Plan/feature-traces/01-quests.md` through `10-orchestration.md` — per-feature design depth
- Memory `phase0_complete_state.md` — file changes + integration points
- CLAUDE.md — project conventions; immutable game constants
- `Scaled JSON Development/LLM Training Data/Fewshot_llm/MANUAL_TUNING_GUIDE.md` — crafting LLM tuning manual
- Agent reports (all 6 returned successfully): for the unabridged tables, see the saved persisted-output JSONs at `C:\Users\vipVi\.claude\projects\c--Users-vipVi-PycharmProjects-Game-1\ec30dec9-d678-4643-82c8-b26148fd7ab7\tool-results\`. The rendering/UI/audio report is also reformatted as standalone markdown at `Development-Plan/controls-agent-render-ui.md` (~810 lines).

---

## §15 — Reconciliation backlog (status as of 2026-06-05)

**Session 2026-06-05 swept 11 of 20 traps; trap 10 deferred (not an actual dup); trap 11 superseded by Claude-only posture. 656/656 phase + WMS + WES + WNS tests green; 0 regressions.**

Critical "two-source" traps where the same constant lives in multiple files and the runtime may not read your tuned value:

1. **[DONE 2026-06-05]** `DIFFICULTY_RANGES` — `reward_calculator.py:24` now imports from `difficulty_calculator`. Single source.
2. **[DONE 2026-06-05]** `RARITY_TIERS` — centralized in `Crafting-subdisciplines/rarity_utils.py` with `rarity_index()` / `rarity_at()` helpers. `refining.py` (both sites) + `core/crafting_tag_processor.py` consume it.
3. **[DONE 2026-06-05]** First-try bonus — `reward_calculator.FIRST_TRY_BONUS.per_discipline` dict + `first_try_bonus(discipline)` accessor. Engineering and enchanting call sites updated.
4. **[DONE 2026-06-05]** Magnitude tables — `skill_manager.py:663` hardcoded dict replaced with `self.magnitude_values` (JSON-loaded). Restore-amounts also routed through it.
5. **[DONE 2026-06-05]** Mana/cooldown/duration enums — `SkillDatabase.mana_costs/cooldowns/durations` are now @properties delegating to `TranslationDatabase`. JSON wins.
6. **[DONE 2026-06-05]** Per-stat magnitudes — `entities/components/stats.py` reads `Definitions.JSON/stats-calculations.JSON > characterStatModifiers` at import; `reload_stat_config()` hook added.
7. **[DONE 2026-06-05]** Class tag → tool efficiency — `progression/classes-1.JSON > metadata.tagToolBonuses` block; `class_system.py` reads it via `_load_tag_tool_bonuses()`.
8. **[DONE 2026-06-05]** 4 evaluator divergent defaults — py fallbacks aligned to memory-config.json values (progression_skills, exploration_territory, social_npc, combat_kills_regional_low_tier).
9. **[DONE 2026-06-05]** 2 evaluators missing from JSON — `faction_reputation` + `ecosystem_resource_depletion` blocks added to memory-config.json; `ecosystem_resource_depletion.py` now reads thresholds + reset% + min_nodes_to_track + chunk_size from config.
10. **[DEFERRED]** 3 overlapping stat-tag sources — investigation shows they serve distinct purposes (manifest = SQL pre-population, layer1-stat-tags = tag mapping, tag-registry = faction tags). Not an actual duplicate. Documented in WMS_TOOLS_AND_SIMULATION.md.
11. **[SUPERSEDED]** MockBackend templates — Claude-only posture (2026-06-05) makes MockBackend a test-only fallback. `WES_REQUIRE_REAL_LLM=1` strips it from the live chain. Tuning the templates is no longer relevant for playtest.
12. **[DONE 2026-06-05]** `_calculate_gossip_delay()` — now reads NPC `home_chunk` via `NPCDatabase.get_voice_excerpt()` and computes Chebyshev chunk distance to gossip source. immediate / short / medium / global delays all reachable per radius config.
13. **[DONE 2026-06-05]** 5-source element→color — new `rendering/visual_colors.py` is the single source. `visual-config.JSON > damageNumbers.typeColors` is authoritative; `weapon_visuals.ELEMENT_COLORS`, `renderer._ETAG_COLORS`, `renderer._ELEMENT_COLORS` all seed from it. `combat_particles.DAMAGE_SPARK_COLORS` kept as palette-specialized (intentional artistic variation, documented).
14. **[DONE 2026-06-05]** 3-source enemy tier color — `visual-config.JSON > enemyVisuals.tierColors` block added; `visual_effect_bridge._tier_color()` + `renderer.py:1377-1380` both read it.
15. **[DONE 2026-06-05]** 3-source state colors — `renderer._STATE_COLORS` now seeds from `visual_colors.state_palette()` (which reads `enemyVisuals.stateIndicatorColors`).
16. **[DONE 2026-06-05]** Hit-pause dead code — call sites at `visual_effect_bridge.py:119-120 + 141-142` and `game_engine.py:3310 + 3324` removed. Inert `hitPauseEnabled`/`slowMotionEnabled` flags stripped from `visual-config.JSON`. `screen_effects.hit_pause()` stays as a no-op for backwards-compat.
17. **[DONE 2026-06-05]** Inventory slot spacing — `Config.INVENTORY_SLOT_SPACING` introduced. All 4 game_engine call sites + the renderer site at line 5056 consume it.
18. **[DONE 2026-06-05]** Map-waypoint keybindings — JSON marked DOCUMENTATION-ONLY with explicit note; `place_waypoint` corrected from "W" → "P" to match the actual `K_p` runtime binding. zoom_in/out updated to reflect mousewheel-only runtime.
19. **[DONE 2026-06-05]** Dodge JSON wire — `combat-config.JSON > dodgeMechanics` block added (dodgeDurationMs / dodgeSpeedMult / dodgeCooldownMs / iframeDurationMs). `Combat/player_actions.py` reads it via `_load_dodge_config()`; `reload_dodge_config()` exposed for hot-reload.
20. **[DONE 2026-06-05]** `bossGlowColor` — `renderer.py:1380` (the gold hardcode) now calls `visual_colors.boss_glow_color()` which reads `enemyVisuals.bossGlowColor` from visual-config.

---

## §16 — Backend hardening (NEW 2026-06-05)

User-direction Claude-only posture for playtest:

- **`backend-config.json`** — Ollama disabled; `fallback_chain = ["claude", "mock"]`. Mock kept enabled for tests but `WES_REQUIRE_REAL_LLM=1` strips it from the live chain at `generate()` time.
- **Comprehensive LLM dev log** — every `BackendManager.generate()` call appended to `llm_debug_logs/wes_<session>.jsonl`. Fields: task, backend, model, system_prompt, user_prompt, response, error, elapsed_s, temperature, max_tokens. Best-effort; never breaks the playtest.
- **Reader API** — `world_system.living_world.backends.llm_dev_log.tail_recent(n=15)` for the F12 overlay + Prompt Studio Simulator.
- **Playtest checklist** (in `backend-config.json._playtest_checklist`): set `ANTHROPIC_API_KEY`, `WES_REQUIRE_REAL_LLM=1`, `WES_DISABLE_FIXTURES=1` (if you want to bypass canned fixtures), optional `WES_VERBOSE=1`, then run `tools/wes_real_llm_smoketest.py`.

## §17 — Phase 7 wiring (NEW 2026-06-05)

All three Phase 7 substrates are now connected to runtime call sites:

- **QuestArchive on turn-in** — `QuestManager.complete_quest` builds an `ArchivedQuestRecord` (participating NPCs/entities, narrative tags, actual rewards, duration, result, def snapshot) and calls `QuestArchiveDatabase.get_instance().archive()`.
- **MixedTriggerArbiter** — `BehaviorInterpreter` now subscribes to `WNS_CALL_WES_REQUESTED` to capture recent narrative firings. Before publishing a behavior firing it consults the arbiter; `suppress_behavior` short-circuits the publish so the behavior trigger doesn't double the narrative at the same address.
- **PresenceDriftDetector** — `WorldMemorySystem._run_presence_drift_scan()` invoked at each daily-ledger boundary. Drift candidates publish `WMS_TRIGGER_FIRED` with `event_type="presence_drift"` so they enter the same downstream pipeline as threshold-crossings.

---

*End of controls map v2.1.*
*If you're tuning right now: §1.3 first (WORLD TONE — starter draft landed 2026-06-05), then §1.1 (14 modular blocks — still designer's call). For combat/dungeon: §4 + §6.2. §15 reconciliation is now mostly closed; remaining items are documented as deferred/superseded above. The 5 agent reports cover ~1100 individual tunables — this map indexes them; the unabridged tables live in the saved persisted-output JSONs referenced in §14.*

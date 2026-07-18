# 04 — entities/ Character + Components: Porting Contract

**Subsystem**: `Game-1-modular/entities/` (player character, character components, status effects, tools)
**Total LOC**: 7,468 (verified `wc -l`, 2026-07-17)
**Source of truth**: code as of branch `crux-foundry`. Every load-bearing claim cites `file:line`.
**Verdict in one line**: This is the heart of the pure-logic C# assembly. ~90% ports cleanly (dataclass-style state + arithmetic); the engine touchpoints are movement/collision (delegates to `WorldSystem.is_walkable`), console `print` feedback, and `stat_tracker` (sidecar boundary — writes to WMS SQLite).

---

## 1. File Table

| File | LOC | Responsibility | Disposition |
|---|---|---|---|
| `entities/character.py` | 2,634 | Player aggregate: position/facing/movement, HP/mana/shield, harvest & break-block damage math, death/death-chest, equip/unequip orchestration, weight/encumbrance, attack cooldowns, shield reduction, consumables, save restore | **decompose + port-to-C#** (split into PlayerState / GatheringService / DeathService / EquipOrchestrator / MovementIntent; movement collision goes to engine glue) |
| `entities/components/skill_manager.py` | 1,168 | Skill learn/equip/use, mana+cooldowns, buff creation from JSON magnitudes, combat-skill dispatch into effect_executor, skill-kill rewards, skill VFX generation | **port-to-C#** except `_generate_skill_visual` (1055-1168) and the kill-reward block (1023-1049) which are engine/Combat glue |
| `entities/components/stat_tracker.py` | 1,156 | 80+ `record_*` analytics methods writing hierarchical keys to WMS `StatStore` (SQLite); legacy dict serialization | **stays-python-sidecar** (boundary): port the `record_*` API surface as a thin C# client that fires stat events over IPC; SQL stays in the Python sidecar (`stat_tracker.py:25` imports `world_system.world_memory.stat_store`) |
| `entities/status_effect.py` | 826 | 18 StatusEffect classes (DoT/CC/buff/debuff) + factory + default params | **port-to-C#** (pure logic; `visual_effects` set is a render hint read by renderer) |
| `entities/status_manager.py` | 294 | Per-entity StatusEffectManager: stacking rules, mutual exclusions, resistance-scaled durations, immobilize/silence queries | **port-to-C#** |
| `entities/components/crafted_stats.py` | 295 | Minigame quality → equipment bonus generation/application (`VALID_STATS_BY_TYPE` filter) | **port-to-C#** (pure functions) |
| `entities/components/inventory.py` | 244 | `ItemStack` + 30-slot `Inventory`: stacking rules, add/remove, drag state | **port-to-C#**; drag-state fields (`dragging_slot/`_stack`/`_from_equipment`, lines 113-115) move to UI glue |
| `entities/components/equipment_manager.py` | 186 | 10-slot equipment dict, hand-type validation, weapon damage/range/speed getters, stat-bonus aggregation | **port-to-C#** |
| `entities/components/stats.py` | 178 | 6 core stats; scaling loaded from `stats-calculations.JSON` with hardcoded fallback; durability/carry/luck multipliers | **port-to-C#** (keep the JSON-first + fallback pattern) |
| `entities/components/weapon_tag_calculator.py` | 173 | Static tag→modifier math (2H/versatile/fast/precision/reach/armor_breaker/crushing/cleaving) | **port-to-C#** (trivial static class) |
| `entities/components/buffs.py` | 156 | `ActiveBuff` dataclass + `BuffManager` (stacking-additive by append, regen ticking, consume-on-use) | **port-to-C#** |
| `entities/components/leveling.py` | 49 | Level 1-30, EXP curve `200×1.75^(lvl-1)`, cascade level-ups, +1 stat point/level | **port-to-C#** (sacred; port verbatim) |
| `entities/tool.py` | 42 | Legacy `Tool` dataclass with own durability-effectiveness copy | **drop-dead-code** (see §11 gotchas — tools live in equipment slots as `EquipmentItem` since the slot refactor; only living use is an unreachable death-chest restore branch) |
| `entities/components/__init__.py` | 21 | Re-exports components | n/a (namespace) |
| `entities/damage_number.py` | 19 | Floating damage text entity (position drift + lifetime) | **engine-replaces** (Godot `Label3D`/particle billboard; keep the 1.0s lifetime / -1.0 y-velocity as config defaults) |
| `entities/components/activity_tracker.py` | 16 | Counter dict for 8 activity types (feeds title requirements) | **port-to-C#** (trivial) |
| `entities/__init__.py` | 11 | Re-exports Tool/DamageNumber/Character | n/a |

Files covered: **17**.

---

## 2. Public Surface (what other subsystems actually call)

### Character (`entities/character.py:60`)
Constructed at `core/game_engine.py:33` (import) and after load; renderer imports the type at `rendering/renderer.py:36`.

| Member | Callers (file:line) |
|---|---|
| `move(dx, dy, world)` | `core/game_engine.py:8426` |
| `update_health_regen(dt)` / `update_buffs(dt)` / `update_knockback(dt, world)` | `core/game_engine.py:8546-8548` |
| `harvest_resource(resource, nearby_resources)` | `core/game_engine.py:3062` |
| `break_placed_entity(placed)` | `core/game_engine.py:3103` |
| `use_consumable(item_id, crafted_stats, consume_from_inventory)` | `core/game_engine.py:1535, 2823` |
| `try_equip_from_inventory(idx)` | `core/game_engine.py:2710` |
| `try_unequip_to_inventory(slot)` | `core/game_engine.py:3231` |
| `switch_tool()` (TAB cycling, sets `_selected_slot`) | `core/game_engine.py:855` |
| `can_attack(hand)` / `reset_attack_cooldown(is_weapon, hand)` | `core/game_engine.py:3858, 3908, 4040, 8472, 8521` |
| `is_shield_active()` | `core/game_engine.py:7763, 8451`; `Combat/combat_manager.py:2079` |
| `get_shield_damage_reduction()` | `Combat/combat_manager.py:2080` |
| `take_damage(damage, damage_type, **kwargs)` | `Combat/combat_manager.py:2101`; status effects call it generically (`entities/status_effect.py:113,145,178,679`) |
| `get_weapon_damage()` | `Combat/combat_manager.py:720, 901, 1348, 1376, 1632` |
| `get_effective_luck()` | `Combat/combat_manager.py:866` (crit), plus internal gathering paths |
| `get_enemy_damage_multiplier(enemy)` | `Combat/combat_manager.py:972, 1648` |
| `get_tool_effectiveness_for_action(item, action)` | `Combat/combat_manager.py:732, 917, 1829` |
| `get_equipped_tool(tool_type)` | `Crafting-subdisciplines/fishing.py:719, 750, 783` |
| `get_effect_resistance(effect_type)` | `entities/status_manager.py:134-135` (duck-typed) |
| `restore_from_save(player_data)` | `core/game_engine.py:1247, 2113, 2201` |
| `recalculate_stats()` | `entities/components/equipment_manager.py:77, 107`; game_engine debug keys |
| `allocate_stat_point(name)` | stats UI in game_engine |
| `select_class(class_def)` / `check_skill_unlocks(...)` / `check_and_notify_new_skills()` | game_engine class-selection & progression flow |
| Attributes read broadly | `health/max_health/mana/max_mana/shield_amount`, `position`, `facing`, `facing_angle`, `_attack_facing_locked`, `stats`, `leveling`, `skills`, `buffs`, `titles`, `class_system`, `equipment`, `inventory`, `stat_tracker`, `quests`, `encyclopedia`, `invented_recipes`, UI flags (`crafting_ui_open` etc.), `dungeon_manager`/`world_system` back-refs (character.py:150-151) |

### SkillManager (`entities/components/skill_manager.py:16`)
- `use_skill(slot, character, combat_manager, mouse_world_pos)` — `core/game_engine.py:979-1011` (hotkeys 1-5)
- `use_skill_in_combat(...)` (`skill_manager.py:801`) — combat path
- `learn_skill` / `equip_skill` / `get_available_skills` / `can_learn_skill` — game_engine skills menu, `Character.restore_from_save` (character.py:546-556), `SkillUnlockSystem` via `unlock_skill` (skill_manager.py:129)

### StatusEffectManager / `add_status_manager_to_entity` (`entities/status_manager.py:266`)
- Attached to player at `entities/character.py:128`; to enemies at `Combat/enemy.py:12`; to training dummy at `systems/training_dummy.py:13`
- `apply_status` driven by `core/effect_executor.py:217-218` (all tag-based statuses) and `:557-562` (phase)
- `is_immobilized()` gates `Character.move` (character.py:774)

### WeaponTagModifiers (`entities/components/weapon_tag_calculator.py:15`)
- `Combat/combat_manager.py:877, 936, 1624` (crit/damage/cleave), `entities/components/equipment_manager.py:164` (range), `entities/character.py:2545` (attack speed)

### crafted_stats functions
- `generate_crafted_stats` — `Crafting-subdisciplines/smithing.py:852`, `engineering.py:1272`
- `apply_crafted_stats_to_equipment` — `core/game_engine.py:6448`

### Inventory / ItemStack
- `core/interactive_crafting.py:14`, `rendering/renderer.py:37, 6829`, `core/game_engine.py:50, 5356, 8012` (death chest restore), crafting simulators

### StatTracker
- ~60 call sites outside entities/: `core/game_engine.py` (menus, saves, debug keys, dodges, projectiles — e.g. 628-642, 963, 3652-3712), `Combat/combat_manager.py`, `Crafting-subdisciplines/fishing.py:853-856`, `data/models/skill_unlocks.py:62`. Store wired by WMS at `world_system/world_memory/world_memory_system.py:155` (`character.stat_tracker.set_store(self.stat_store)`).

### Save side
- `systems/save_manager.py:175-196` reads character fields directly (inventory, equipment, skills, activities, `stat_tracker.to_dict()`, `skill_unlocks`, invented recipes).

---

## 3. Dependency Edges

### entities/ imports FROM:
- `data.models` — `Position`, `CraftingStation`, `EquipmentItem`, `ClassDefinition` (character.py:34-39); `PlayerSkill` (skill_manager.py:7); `EquipmentItem`, `MaterialDefinition` (inventory.py:6); `Position` (damage_number.py:5)
- `data.databases` — Equipment/Class/Skill/Title/Material DB singletons (character.py:42-48); Material/Equipment DB (inventory.py:7); SkillDatabase (skill_manager.py:8); RecipeDatabase lazily (character.py:650)
- `systems` — `Encyclopedia`, `QuestManager`, `WorldSystem`, `TitleSystem`, `ClassSystem`, `NaturalResource` (character.py:23-30); `SkillUnlockSystem` (character.py:31); `systems.potion_system` lazily (character.py:2593); `systems.attack_effects` lazily (skill_manager.py:1066)
- `core` — `Config` (character.py:51; tool.py:5); `effect_executor` + `tag_debug` + `paths` + `debug_display` (skill_manager.py:10-13); `debug_display` lazily (character.py:999)
- `events` — `event_bus` lazily inside try/except at every publish site (see §6)
- `world_system` — **`world_system.world_memory.stat_store`** (stat_tracker.py:25). This is the ONLY hard import from the sidecar-bound world_system into entities/. It must be severed in the port (IPC client instead).

### Who imports entities/:
- `core/game_engine.py:33,50` (Character, DamageNumber, ItemStack, crafted_stats, tool)
- `rendering/renderer.py:36-37` (Character, Tool, DamageNumber, ItemStack)
- `Combat/combat_manager.py:877,936,1624` (WeaponTagModifiers); `Combat/enemy.py:12` (status_manager)
- `systems/`: title_system, skill_unlock_system, potion_system (TYPE_CHECKING + ActiveBuff at potion_system.py:8), training_dummy:13
- `core/interactive_crafting.py:14`, `Crafting-subdisciplines/smithing.py:852` / `engineering.py:1272` (crafted_stats), tests

**Circularity warning**: character ↔ systems is bidirectional (character imports TitleSystem/ClassSystem/QuestManager as owned components; systems type-hint Character). In C#, break this by making the pure assembly own interfaces (`ITitleBonusProvider`, `IClassBonusProvider`, `IPotionExecutor`) that `Character` consumes.

---

## 4. Engine Coupling (redesign points)

entities/ never imports pygame directly — coupling is indirect:

1. **Movement/collision** — `Character.move` calls `world.is_walkable(pos)` and implements axis-sliding manually (character.py:817-839); `update_knockback` same (759). In Godot this becomes `CharacterBody3D.MoveAndSlide()`; the *speed-multiplier computation* (character.py:782-807) stays pure and feeds the controller.
2. **Frame clock** — all `update_*(dt)` methods (character.py:743, 1421, 1457, 2514; buffs.py:46; status_manager.py:191; skill_manager.py:184) are dt-driven from the game loop (`core/game_engine.py:8546-8548`). Godot: `_PhysicsProcess(delta)` on the player node calling into the pure model.
3. **Input-adjacent state on the model** — `_selected_slot` TAB cycling (character.py:125, 1364-1410), `_attack_facing_locked` (character.py:86, set by `game_engine._ac_attack_angle` per comment at 854-857), `facing`/`facing_angle` quantized to 4 directions (character.py:84-85, 380-381, 852-859). Input handling moves to controller; keep the fields as pure state.
4. **UI flags on the model** — `crafting_ui_open`, `stats_ui_open`, `equipment_ui_open`, `skills_ui_open`, scroll offsets, `class_selection_open` (character.py:131-138, 1515-1524); inventory drag state (inventory.py:113-115, 186-222). Move to a Godot UI layer; do not port into the logic assembly.
5. **Console feedback as gameplay UX** — dozens of `print()` calls are the player-facing feedback channel (e.g. title earned character.py:1218, fortune proc 1165, durability warnings 1129-1133, shield absorb 1827, equip debug spam 1636-1692, 1696-1782). Replace with a `INotificationSink`/event stream consumed by Godot HUD.
6. **Skill VFX** — `SkillManager._generate_skill_visual` (skill_manager.py:1055-1168) builds pygame-era attack effects via `systems.attack_effects`. Engine-replaces: emit a `SkillVisualRequested(geometry, tags, positions)` event; Godot VFX layer interprets tags.
7. **`visual_effects` set** — status effects add/discard string hints (`'burn'`, `'freeze'`… status_effect.py:102-107 et al.; created at status_manager.py:285-286) that the renderer reads. Keep as state; Godot reads it for shaders/particles.
8. **DamageNumber** — pure drift math (damage_number.py:16-19) but exists only to be rendered; engine-replaces.
9. **StatTracker → SQLite** — `stat_tracker.py:25` hard-imports WMS `StatStore`; store swapped to the shared WMS SQLite connection at `world_memory_system.py:108,155`. **Sidecar boundary**: C# keeps the `record_*` façade + in-memory streak caches (stat_tracker.py:49-55) and ships records over IPC (batched; the Python side already batches via `_store.flush()`).
10. **Filesystem** — `Character._get_combat_config` reads `Definitions.JSON/combat-config.JSON` relative to `__file__` (character.py:69); stats.py uses `core.paths.get_resource_path` (stats.py:44-45); skill_manager loads `Skills/skills-base-effects-1.JSON` (skill_manager.py:27). Port to the shared content-loader used by the JSON-verbatim strategy.
11. **`random`** — module-level `random.random()` for crits/fortune (character.py:1096, 1147, 1163, 1327). Use one injectable RNG for testability.

---

## 5. Constants & Formulas (exact, from code)

### Leveling (SACRED — `entities/components/leveling.py`)
- Max level **30** (leveling.py:8); EXP table `int(200 * 1.75**(lvl-1))` (leveling.py:9)
- **+1 unallocated stat point per level** (leveling.py:34)
- Cascade semantics (SACRED, 2026-07 audit): one `add_exp` call resolves **multiple** level-ups in a `while` loop, subtracting `exp_needed` each iteration; at max level further EXP is refused (`return False`) (leveling.py:24-49). Each level publishes `LEVEL_UP` and records to stat_tracker inside the loop.
- Gathering EXP by resource tier: `{1:10, 2:40, 3:160, 4:640}` (character.py:1202, 1221) — note this is the tier 1/2/4/8 multiplier ladder × ~10... actually ×4 per tier; preserve verbatim.

### Core stats (`entities/components/stats.py`, values confirmed in `Definitions.JSON/stats-calculations.JSON`)
- Scaling per point (fallback stats.py:21-24 == JSON): STR `0.05` (JSON:441), DEF `0.02` (JSON:448), VIT `0.01` (JSON:455), LCK `0.02` (JSON:460), AGI `0.05` (JSON:467), INT `0.02` (JSON:379)
- Flat per point (stats.py:26-30, JSON:443/454/460): STR→`carry_capacity 10`, `inventory_slots 10`; VIT→`max_health 15`; INT→`mana 20`
- `get_durability_loss_multiplier` = `max(0.1, 1 - DEF*0.02)` (stats.py:129-130)
- `get_durability_bonus_multiplier` = `1 + VIT*0.01` (stats.py:141-142)
- `get_carry_capacity_multiplier` = `1 + STR*0.02` (stats.py:153-154)
- `get_effective_luck` = `LCK + title_luckStat + skill_luck + (rareDrop bonuses / 0.02)` (stats.py:176-178) — the `/0.02` conversion assumes 2%/pt and is **not** synced with the combat 0.12 retune (see risks)
- JSON hot-reload hook `reload_stat_config()` (stats.py:92-99)

### LCK / crit — **split-brain, preserve both**
- Combat crit: `_LCK_CRIT_PER_POINT = env CRUX_LCK_CRIT_PER_POINT default 0.12` × `get_effective_luck()` (`Combat/combat_manager.py:24, 866`)
- Gathering crit: `effective_luck * 0.02 + class crit_chance + pierce buffs` (character.py:1092-1094); block-breaking crit: same 0.02 formula, crit ×2 damage (character.py:1326-1332)
- Loot quantity: `qty × (1 + LCK*0.02)` then `+1` at chance `effective_luck*0.02 + class resource_quality` (character.py:1141-1148)
- `stats-calculations.JSON:460` still says `critChancePerPoint: 0.02`; the 0.12 lives only in combat_manager env default.

### Health / mana / regen (character.py)
- `base_max_health = 100`, `base_max_mana = 100` (113-114)
- `max_health = base + VIT*15 + class + equipment`; `max_mana = base + INT*20 + class + equipment`; current values scale **proportionally** on recalc (703-731)
- Health regen: after **5.0 s** without dealing AND taking damage (156-157, 1430-1431), regen `5.0 HP/s × (1 + VIT*0.01)` (1433-1435) — VIT multiplier newly wired (2026-07 audit note at 1426-1429)
- `health_regeneration` enchant: +value HP/s always-on from the 5 armor slots (1437-1450)
- Mana regen: `1% of max_mana per second`, always (1452-1455)

### Movement (character.py)
- Base speed `Config.PLAYER_SPEED = 0.15` tiles/tick-unit (config.py:183); interaction range `3.5` (config.py:184), 3D distance (`data/models/world.py:16-17`)
- Speed mult = `1 + AGI*0.015 + class movement_speed + buffs quicken/movement + armor movement_speed_multiplier enchants` (784-807); chill/slow multiplies by `(1 - slow_amount)` default 0.5 (794-796)
- Knockback: velocity applied over `knockback_duration_remaining`; player input damped to **10%** during knockback (778-780); blocked knockback still consumes duration (759-762)
- Immobilized (freeze/stun/root) → no movement (774-775, status_manager.py:235-237)
- Diagonal blocked → axis-slide X then Y (825-839)
- Encumbrance: capacity = `100 × (1+STR*0.02) + class carry_capacity` (2249-2257); **-2% speed per +1% over capacity**, floor 0 (2282-2288); default material weight `0.1`/item when DB lacks weight (2235-2236)

### Attack timing (character.py)
- Effective attack speed = `1.0 × (1 + AGI*0.03 + title attackSpeed + buffs quicken/combat)` (2374-2389)
- Weapon cooldown = `(1.0 / weapon.attack_speed) / (effective_speed + fast-tag 0.15)` (2534-2556); tool swing cooldown flat `0.5 s` (2560-2564)
- Per-hand cooldowns `mainhand_cooldown`/`offhand_cooldown` (141-143, 2514-2529)

### Gathering / tool math (character.py:1043-1173)
- Base damage = average of weapon damage tuple (1046-1049)
- Total effectiveness = `durability_effectiveness × tool_type_effectiveness`; tool-type: **1.0 optimal / 0.25 off-domain** (axe→forestry, pickaxe→mining, rod→fishing, weapons→combat) (925-973); placed-block breaking: **pickaxe 2.0 / others 0.5** (1312-1315)
- Damage mult = `1 + stat_bonus(STR mining / AGI forestry) + title {activity}_damage + buff empower{activity}` (1060-1063)
- Efficiency mult = `1 + enchant gathering_speed_multiplier + title {activity}Speed` — **multiplicative on damage** (1076-1098)
- Durability loss per swing: `1.0` proper / `2.0` improper tool, × DEF multiplier, × `(1 - unbreaking value)` (1102-1118); armor loses `1.0 × DEF mult × unbreaking` per piece across 5 slots on attack-sourced damage only (1833-1852)
- Fortune enchant: `bonus_yield_chance` roll → +1 item, max one proc per item type (1157-1166); `enrich` buff adds flat int qty (1151-1154)
- AoE gathering (devastate buff, e.g. Chain Harvest): all matching non-depleted nodes within `bonus_value` tile radius, 2D euclidean (993-1041)

### Durability (SACRED floor)
- `EquipmentItem.get_effectiveness`: `<=0 → 0.5`; `pct>=0.5 → 1.0`; else `1.0 - (0.5 - pct)*0.5` (`data/models/equipment.py:49-55`; duplicate copy in `entities/tool.py:30-36`). Items never break — 0 durability = 50% effectiveness forever.
- Effective max durability = `durability_max × (1+VIT*0.01) × (1+title durabilityBonus)` (character.py:2153-2177)
- Self-repair enchant (`durability_regeneration`): +value/s toward max (character.py:1469-1513)

### Combat-facing (character-side)
- `take_damage`: phase → full negate (1817-1819); `shield_amount` absorbs first (1822-1827); remainder to health; death at ≤0 (1868-1876). Enemy DEF/armor reduction happens in combat_manager, NOT here.
- Shield block: reduction = `(1 - shield.stat_multipliers['damage']) × (1 + bonuses.defense_multiplier)`, clamped to `[minDamageReduction 0.0, maxDamageReduction 0.75]` from `Definitions.JSON/combat-config.JSON:109-110` (character.py:2482-2512; config cache 64-80)
- Unarmed damage `(1, 2)` mainHand, `(0, 0)` offHand (equipment_manager.py:147-149); weapon range = `weapon.range + 1.0` (+1 for any held item) + reach-tag bonus; bare fists range `1.0` (equipment_manager.py:151-171)
- Title matrices: `{category}Damage` / `{tag}Damage` enemy multipliers (character.py:2391-2427); `{effect}Resistance` shortens status duration `max(0, 1 - resistance)` (2429-2454)

### Skills (`entities/components/skill_manager.py`, `data/models/skills.py`)
- 5 hotbar slots (skill_manager.py:19); skill EXP **100 per activation** (258, 909); skill max level **10**; level scaling `+10% per level above 1` (`data/models/skills.py:108, 128-130`)
- Magnitude fallbacks (JSON `Skills/skills-base-effects-1.JSON` is primary; fallback skill_manager.py:41-46): empower `0.5/1.0/2.0/4.0`, quicken `0.3/0.5/0.75/1.0`, fortify `10/20/40/80`, pierce `0.1/0.15/0.25/0.4`
- Restore: durability percents `{15,30,50,75}%`, HP/MP amounts `{50,100,200,400}` (428-429); instant-duration buffs get 60 s fallback + `consume_on_use=True` (319-325)
- Class affinity bonus applied to buff magnitudes and combat `baseDamage`/`baseHealing` (311-329, 939-951)
- DEX requirement maps to AGI (skill_manager.py:77)

### Status effects (`entities/status_effect.py`) — defaults if params omitted
| Effect | Default | Stacks (max) | Stacking rule (status_manager.py:26-51) |
|---|---|---|---|
| burn | 5.0 dps × stacks | 3 | additive |
| bleed | 3.0 dps × stacks | 5 | additive |
| poison | 2.0 dps × stacks^1.2 (line 176) | 10 | additive |
| shock | 5.0 dmg per 2.0 s tick × stacks | 3 | additive (rule table omits shock → NONE/replace; see gotchas) |
| freeze/stun/root | full immobilize/action-block | 1 | refresh |
| slow/chill | 50% speed | 1 | refresh |
| regeneration | 5.0 hps × stacks | 3 | additive |
| shield/barrier | 50.0 absorb | 1 | additive (amounts add) |
| haste/quicken | +30% move+attack speed | 1 | refresh |
| empower | +25% damage | 1 | (not in table → replace) |
| fortify | +20% reduction | 1 | (not in table → replace) |
| weaken | -25% damage dealt | 3 | additive |
| vulnerable | +25% damage taken | 3 | additive |
| phase/ethereal | damage immunity (+wall pass opt) | 1 | (not in table → replace) |
| invisible/stealth | undetectable | 1 | (not in table → replace) |
- Default duration `5.0 s` via `params.get(f'{tag}_duration', params.get('duration', 5.0))` (status_effect.py:824)
- Mutual exclusions: burn↔freeze, stun↔freeze (status_manager.py:12-15)
- Resistance scales duration keys before creation (status_manager.py:132-146)

### Weapon tags (`entities/components/weapon_tag_calculator.py`)
- 2H ×1.2 damage; versatile ×1.1 if no offhand (33-36); fast +0.15 attack speed (52); precision +0.10 crit (69); reach +1.0 range (86); armor_breaker 25% armor pen (101); crushing +20% vs armored (115); cleaving = AoE flag, 50% splash per summary string (168)

### Crafted stats (`entities/components/crafted_stats.py`)
- `quality = earned_points/max_points × 100` (81-83)
- `durability_multiplier = (quality-50)/100` → ±0.5 (90); weapon `damage_multiplier` ±0.5 (102); attack_speed `0..+0.20` above q50, `-0.10..0` below (105-109); armor/shield `defense_multiplier` ±0.5 (113); shield `block_chance` `0..+0.10` / `-0.05..0` (117-123); tool `efficiency = 0.5 + q/100` → 0.5-1.5 (128)
- Application writes to `equipment.bonuses` dict; durability multiplier mutates `durability_max` AND `durability_current` on fresh craft (190-202); `VALID_STATS_BY_TYPE` filter (24-51)

### Inventory / equipment slot math
- Inventory **30 slots** (character.py:121; `Inventory(max_slots=30)` inventory.py:110); material default `max_stack 99` (inventory.py:14), overridden by MaterialDatabase per-item (19-24); **equipment max_stack 1, never stacks** (30-34, 86-88)
- Stacking requires same item_id + same rarity + identical `crafted_stats` (66-106)
- Equipment slots (10): `mainHand, offHand, helmet, chestplate, leggings, boots, gauntlets, accessory, axe, pickaxe` (equipment_manager.py:10-21); armor set for defense/durability/enchant scans = 5 slots `helmet/chestplate/leggings/boots/gauntlets` (equipment_manager.py:135; character.py:800, 1440, 1839)
- Hand rules: 2H → mainHand only, auto-unequips offHand (character.py:1736-1748, validated equipment_manager.py:41-47); offHand accepts only 1H or shield; versatile mainHand allows 1H/shield offhand; `default` hand_type allows only shield offhand (equipment_manager.py:48-65); best-slot decision tree at character.py:1618-1692
- Death: `Config.KEEP_INVENTORY = True` default (config.py:192); if False, non-soulbound items → death chest at death position (dungeon → dungeon entrance `return_position`), player respawns at `PLAYER_SPAWN_X/Y/Z` (character.py:1878-2027); soulbound = flag or enchant type `soulbound` (`data/models/equipment.py:35-47`)
- Facing quantization: right 0° / down 90° / left 180° / up 270° (character.py:85, 380-381, 858)

---

## 6. Event Topics (GameEventBus)

All publishes are lazy `try/except` imports of `events.event_bus.get_event_bus()` — deliberately fire-and-forget so entities never crash if the bus is absent. entities/ **subscribes to nothing**.

| Topic | Payload keys | Publish site |
|---|---|---|
| `PLAYER_DIED` | position_x, position_y | `entities/character.py:1918` |
| `LEVEL_UP` | new_level, stat_points, source (source="leveling") | `entities/components/leveling.py:40` |
| `ITEM_ACQUIRED` | actor_id, item_id, quantity, category(equipment/material), rarity | `entities/components/inventory.py:130` |
| `SKILL_LEARNED` | actor_id, skill_id | `entities/components/skill_manager.py:120` |
| `SKILL_ACTIVATED` | skill_id, mana_cost, category, value, targets | `entities/components/skill_manager.py:247, 873, 898` |
| `EQUIPMENT_CHANGED` | item_id, slot, equipped(bool) | `entities/components/equipment_manager.py:89, 115` |
| `REPAIR_PERFORMED` | actor_id, items_repaired | `entities/components/skill_manager.py:729` |

These topics feed WMS EventRecorder in the sidecar — in Godot they must be forwarded over IPC verbatim (topic string + payload) or WMS layers starve.

---

## 7. Content JSON Consumed (verbatim reuse; loaders port)

| File | Loader | Used for |
|---|---|---|
| `Definitions.JSON/combat-config.JSON` | `Character._get_combat_config` class-cache, path relative to `entities/` (character.py:64-80) | `shieldMechanics.min/maxDamageReduction` (0.0 / 0.75, JSON:109-110) |
| `Definitions.JSON/stats-calculations.JSON` | `stats._load_stat_config` via `core.paths.get_resource_path`, module-import time + `reload_stat_config()` (stats.py:33-99) | per-stat scaling + flat bonuses (`characterStatModifiers.*`) |
| `Skills/skills-base-effects-1.JSON` | `SkillManager._load_magnitude_values` (skill_manager.py:24-46) | `BASE_EFFECT_TYPES.*.magnitudeValues` per effect type |
| Indirect (via database singletons) | Material/Equipment/Recipe/Skill/Title/Class DBs (character.py:42-48, inventory.py:7, skill_manager.py:8) | item defs, `max_stack`, equipment creation, skill defs incl. `get_mana_cost`/`get_cooldown_seconds`/`get_duration_seconds` word→number tables (skill_manager.py:220, 228, 305) |

Class starting-skill remap table is **hardcoded** in character.py:1536-1543 (`battle_rage→combat_strike` etc.) — content-adjacent logic to preserve.

---

## 8. Persistent State (save/load contribution)

Live path: `SaveManager._serialize_player` (save_manager.py:~160-196) writes; `Character.restore_from_save(player_data)` (character.py:365-638) reads. Keys under `save["player"]`:

- `position {x,y,z}`, `facing` (string; facing_angle re-derived, 379-381)
- `stats {strength, defense, vitality, luck, agility, intelligence}` (ints)
- `leveling {level, current_exp, unallocated_stat_points}`
- `class` (class_id or null), `health`, `mana` (restored AFTER `recalculate_stats()`, 406-411)
- `inventory`: 30-element array of null | `{item_id, quantity, max_stack, rarity, equipment_data?, crafted_stats?}`; `equipment_data` = full EquipmentItem dump: item_id, name, tier, rarity, slot, damage (list→tuple on load, 433-436), defense, durability_current/max, attack_speed, efficiency, weight, range, hand_type, item_type, icon_path, stat_multipliers, tags, effect_tags, effect_params, soulbound, + optional bonuses/enchantments/requirements (413-478)
- `equipment`: `{slot_name: eq_data-dict | legacy item_id string | null}` (480-540)
- `known_skills {skill_id: {level, experience}}`, `equipped_skills` [5] (542-556)
- `titles` [title_id], `activities {activity: count}` (558-571)
- `stat_tracker`: `StatTracker.to_dict()` v2.0 — `{version:"2.0", session_start_time, total_playtime_seconds, session_count, stats:{category:{subkey:{count,total,max_value}}}, gathering_totals, combat_damage, combat_kills, crafting_by_discipline, unique_chunks_visited}` (stat_tracker.py:806-844); `from_dict` accepts v1.0 legacy dicts too (919-1055). **Note**: stats also live in WMS SQLite; the save carries a flattened snapshot re-imported via `import_flat`.
- `skill_unlocks {unlocked_skills[], pending_unlocks[]}` (585-592)
- `invented_recipes` []: `{timestamp, discipline, item_id, item_name, item_data, from_cache, recipe_inputs, station_tier, narrative, placement_data (REQUIRED for placement display, 621), icon_path}`; each re-registered into RecipeDatabase as `invented_{item_id}` (601-701)

Death chest uses the **exact save-format** item serialization (`_serialize_item_for_chest`/`_serialize_slot_for_chest`, character.py:2029-2151) so `game_engine._restore_item_from_chest_data` (game_engine.py:8006+) can reuse restore logic. C# must keep this format identity (one serializer, two consumers).

Dead legacy: `Character.save_to_file`/`load_from_file` (character.py:219-363) have **zero callers** — do not port.

---

## 9. 3D Notes (what necessarily changes)

1. **Position is already 3-component** (`Position(x,y,z)`, distance_to is true 3D — `data/models/world.py:16-17`), but z is effectively unused; all movement/knockback math is XY (character.py:746-770, 810-811). Godot mapping per project convention: Python `(x,y)` → world `(x, 0, z)`; interaction range 3.5 keeps working since distance_to is already 3D.
2. **Facing**: 4-direction string + `facing_angle` degrees in screen-space (0=right, 90=down — character.py:85). In 3D this becomes a yaw around Y with inverted sense (90° down has no meaning); keep `facing_angle` as authoritative yaw, derive the 4-way string only if animation states need it. `_attack_facing_locked` (86) becomes "aim locked to cursor ray" — mouse_world_pos for directional skills (skill_manager.py:967) must come from a camera raycast onto the ground plane.
3. **Collision/sliding**: hand-rolled axis-slide (character.py:825-839) is replaced by `MoveAndSlide`; the *behavioral contract* to preserve: diagonal blocked → still slide along the free axis; knockback can be blocked by walls but still ticks down; phase `ignore_collisions` flag (status_effect.py:707-710) must toggle collision masks.
4. **AoE radii are 2D circles** (gathering radius character.py:1010-1013; skill circle/cone/beam params). In 3D decide cylinder-vs-sphere; recommend XZ-plane cylinder to preserve tile-radius balance exactly.
5. **Chunk coords** from `x // Config.CHUNK_SIZE (16)` for movement tracking (character.py:864-866) — becomes X/Z.
6. **DamageNumber** floats up via `velocity_y=-1.0` in world Y-up-negative screen space (damage_number.py:14) — in 3D it's +Y billboard drift.
7. **Knockback** velocity 2D pair (character.py:91-93) → Vector3 (keep Y=0 unless the combat overhaul adds launch).
8. **`is_walkable` point-check** becomes navmesh/physics queries; encumbrance and slow multipliers just scale controller velocity.

---

## 10. Godot Mapping

### Pure-logic assembly (`Game.Core.dll`, dotnet-testable, no Godot references)
- `CharacterStats` (+ `StatScalingConfig` loaded from stats-calculations.JSON with fallback constants) — mirrors stats.py
- `LevelingSystem` — verbatim, incl. cascade loop
- `BuffManager` / `ActiveBuff`; `StatusEffectManager` + `StatusEffect` hierarchy (or data-driven single class + behavior enum; keep stacking table + exclusions + factory defaults)
- `Inventory` / `ItemStack` (minus drag fields); `EquipmentManager` (slot dict + hand rules + getters); `WeaponTagModifiers` (static); `CraftedStatsGenerator`; `ActivityTracker`
- `PlayerCharacterModel` — decomposition of character.py: health/mana/shield state, recalc, harvesting service, break-block service, weight/encumbrance, attack cooldowns, shield reduction, effective-luck/attack-speed, death resolution (returns a `DeathOutcome {respawnPos, chestPos, droppedItems, soulboundKept}` instead of mutating world), consumable use (via `IPotionExecutor`)
- `SkillManager` core (learn/equip/use/cooldowns/mana/buff creation) with `IEffectExecutor`, `ICombatQuery` interfaces; skill-kill rewards move to combat layer
- Interfaces owned here: `IWalkabilityProvider`, `ITitleBonusProvider`, `IClassBonusProvider`, `INotificationSink`, `IStatSink` (stat_tracker façade), `IEventBus`
- `PlayerSaveData` DTOs matching §8 exactly (System.Text.Json, camel/snake preserved)

### Engine glue (Godot project)
- `PlayerController : CharacterBody3D` — reads `PlayerCharacterModel` speed multipliers, does MoveAndSlide, feeds actual displacement back for stat tracking (distance moved, character.py:843-845); owns facing/aim, knockback velocity application
- `PlayerVisuals` — consumes `visual_effects` set + status events for shaders/particles
- `DamageNumberSpawner` — Label3D pool replacing damage_number.py
- `SkillVfxInterpreter` — subscribes to `SkillVisualRequested`, replaces `_generate_skill_visual` tag→geometry mapping (skill_manager.py:1055-1168)
- `HudNotifications` — replaces gameplay `print()`s
- UI panels (inventory drag, equipment, skills, stats) — own the UI flags currently on Character

### Autoload singletons
- `EventBusBridge` (autoload): in-process C# pub/sub + IPC forwarder of the §6 topics to the Python sidecar
- `StatSinkBridge` (autoload): implements `IStatSink`; batches `record_*` calls over IPC to WMS StatStore (replaces stat_tracker.py's direct import); keeps streak caches locally (stat_tracker.py:49-55) so gameplay-visible streaks don't round-trip
- Database singletons (Material/Equipment/Skill/Title/Class/Recipe) stay `get_instance()`-style services in Game.Core, loaded at boot from the verbatim JSON

---

## 11. Port Complexity, Ordering, Risks

### Complexity
- **Overall: L.** Breakdown: character.py decomposition **L** (2,634 lines, many concerns, but mostly arithmetic); skill_manager **M/L** (depends on effect_executor + skill DB word-tables); status system **M**; stat_tracker façade **M** (API is wide but mechanical; IPC design is the work); inventory/equipment/stats/leveling/buffs/crafted_stats/weapon_tags **S each**; tool.py/damage_number **S/drop**.

### Ordering constraints (must exist first)
1. `data.models` (Position, EquipmentItem incl. `get_effectiveness`/`get_actual_damage`/`is_soulbound`, PlayerSkill) and `data.databases` loaders — entities is unusable without them (character.py:34-48)
2. `Config` constants + content-path resolver (`core.paths`)
3. `IEventBus` bridge (topics in §6) — can be a no-op stub initially (the Python code already tolerates absence via try/except)
4. Then: stats → leveling → buffs → inventory → equipment_manager → status system → PlayerCharacterModel
5. `SkillManager` last among entities — needs `IEffectExecutor` (core/effect_executor port) and SkillDatabase word→number tables
6. Combat_manager port consumes the Character surface in §2 — freeze that C# API before Combat work starts
7. StatSink IPC can lag (stub locally, flush later) but the **topic/key strings must be final early** — WMS evaluators key off them

### Top risks / gotchas (includes dead code & hidden coupling found)
1. **LCK split-brain**: combat crit 0.12/pt (env `CRUX_LCK_CRIT_PER_POINT`, combat_manager.py:24) vs gathering/break crit 0.02/pt hardcoded (character.py:1092, 1326) vs `stats-calculations.JSON:460` still 0.02, and `get_effective_luck`'s rare-drop→luck conversion divides by 0.02 (stats.py:176). Port all four as-is; do NOT "unify" — the 0.12 retune was combat-only by design.
2. **`take_damage` damage_type bug**: `_handle_death` reads `kwargs.get('damage_type', 'physical')` (character.py:1875) but `damage_type` is a named parameter and can never be in kwargs — death-by-element stat recording is always "physical". Decide: replicate bug-for-bug or fix and note in parity checklist.
3. **RegenerationEffect is a no-op on the player**: it calls `target.heal()` or `target.current_health` (status_effect.py:393-396); Character has neither (`health`, no `heal` method — grep confirms zero `def heal` in entities/). Regen status only works on enemies. Player regen actually flows through BuffManager `regenerate` (buffs.py:49-56). Preserve or consciously fix.
4. **Stored-speed restore pattern**: Freeze/Slow/Root/Haste snapshot absolute `movement_speed` and restore it on removal (status_effect.py:202-229, 252-272, 329-355, 460-487). Overlapping effects can clobber each other's snapshots. In C#, recompute from base + modifiers instead — but verify parity on overlap scenarios.
5. **Sidecar boundary in the hot path**: `stat_tracker.py:25` imports WMS StatStore; `record_movement` fires **every frame the player moves** (character.py:874). The IPC client must batch (StatStore already batches internally; mirror that) or the frame budget dies.
6. **Dead code — do not port**: `Character.save_to_file`/`load_from_file` (219-363, zero callers); `Character._serialize_tool_for_chest` (2078-2096, zero callers); `entities/tool.py` `Tool` — tools are `EquipmentItem`s in `axe`/`pickaxe` equipment slots since the slot refactor (character.py:163-177). The only `Tool(...)` construction is the death-chest `tool_data` branch at game_engine.py:8019-8027, which is unreachable (nothing writes `tool_data` anymore) **and would crash if reached** (omits required `damage` field, tool.py:14). Character.tools / selected_tool (122-123) are vestigial.
7. **Shock stacking gap**: `STACKING_RULES` (status_manager.py:26-51) has no `shock` entry → falls to NONE/replace despite ShockEffect supporting `max_stacks=3` (status_effect.py:655). Empower/fortify/phase/invisible also replace-on-reapply. Port the table verbatim; don't "fix" silently.
8. **Latent `Dict` NameError**: character.py:2566 annotates `crafted_stats: Dict` but `Dict` is never imported — only safe because of `from __future__ import annotations` (character.py:3). C# is immune, but flags that annotations were never runtime-validated.
9. **STR inventory-slots is doc-fiction**: CLAUDE.md claims "+10 inventory slots per STR"; the flat bonus exists in config (stats.py:27, JSON:443) but nothing reads `get_flat_bonus('strength','inventory_slots')` — inventory is fixed at 30 (character.py:121). `recalculate_stats` reads only VIT max_health and INT mana flats (706-707). Feature-parity checklist should say 30 fixed slots.
10. **Stale doc**: `docs/CODEBASE-CONTEXT.md:111-117` claims `get_weapon_damage()` ignores enchantments for `_selected_slot`; current code calls `get_actual_damage()` (character.py:2317-2325). Trust code.
11. **Format identity between save and death chest** (§8) — one C# serializer, or drift corrupts chest restores.
12. **Hidden coupling**: death handling needs `dungeon_manager`/`world_system` back-refs injected by game_engine (character.py:150-151, 1898-1901) because status-effect damage can kill without kwargs. In C#, make these constructor-injected interfaces (`IDungeonContext`, `IDeathChestSpawner`) instead of mutable public fields.
13. **`ItemStack.__post_init__` hits databases** (inventory.py:19-34): constructing a stack queries Material + Equipment DBs and may synthesize equipment instances. Port as a factory (`ItemStackFactory(dbs)`), not a bare struct, or deserialization order breaks.
14. **Movement speed AGI is 1.5%/pt** (character.py:784), not the 5% forestry figure — three distinct AGI constants exist (0.015 move, 0.03 attack speed, 0.05 forestry damage). Keep all three separate.

---

*End of porting contract. A C# porter should need only this file plus the cited sources.*

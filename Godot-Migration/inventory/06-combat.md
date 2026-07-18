# 06 — Combat/ Subsystem Porting Contract (Python → Godot 4 .NET/C#)

**Scope**: `Game-1-modular/Combat/` — all 11 files, 5,991 LOC (verified `wc -l`, 2026-07-17), plus the
action-combat glue in `core/game_engine.py` (`_init_action_combat` → `_ac_process_hit`, lines 3464–4078)
which is functionally part of this subsystem and documented here because the critical damage path runs
through it.

**Ground truth**: the code as of branch `crux-foundry` (post F5–F9 conformance fixes, July 2026). Where
docs and code disagree, code wins. Behavior locked by `tests/integration/test_12_combat_conformance.py`.

---

## 1. File table

| File | LOC | Responsibility | Disposition |
|---|---|---|---|
| `combat_manager.py` | 2,622 | `CombatConfig` (JSON config), `CombatManager`: enemy spawning (weighted pools, chunk templates, danger tiers), enemy AI orchestration + phased-attack resolution, **all three player damage pipelines**, enemy→player damage pipeline, crit resolution, EXP/loot, dungeon waves, corpses, action-combat registration | **decompose** → port to C# as ~5 pure-logic classes (SpawnDirector, DamagePipeline, EnemyCombatDirector, ExpLootResolver, CombatState) + thin engine glue |
| `enemy.py` | 1,426 | `EnemyDefinition`/`EnemyDatabase` (hostiles JSON loader, sacred+generated overlay, reload), `Enemy` runtime instance: AI FSM (9 states), phased attacks (windup/active/recovery), special abilities, knockback, loot rolls, chunk-bounds clamping | **port-to-C#** (split: loader → data assembly; `Enemy` runtime → pure logic class + `CharacterBody3D` glue) |
| `attack_state_machine.py` | 245 | `AttackPhase` enum, `AttackDefinition` dataclass, `AttackStateMachine`: IDLE→WINDUP→ACTIVE→RECOVERY→COOLDOWN cycle + combo window. Timing only — no damage | **port-to-C#** pure, near line-for-line |
| `hitbox_system.py` | 282 | `HitboxDefinition` (circle/arc/rect/line), `ActiveHitbox`, `Hurtbox` (circle), `HitboxSystem`: per-frame shape-vs-circle collision → `HitEvent` list. Pure 2D math, zero engine deps | **port-to-C#** pure math (recommended over Godot Areas for exact parity), geometry re-derived for 3D (§9) |
| `projectile_system.py` | 193 | `ProjectileDefinition`, `Projectile` (velocity integration, homing steer, gravity, piercing, AoE-on-hit spawns hitbox), `ProjectileSystem` | **port-to-C#** pure simulation; visuals engine-side |
| `attack_profile_generator.py` | 342 | Derives per-enemy `EnemyAttackDef` lists (primary/secondary/heavy) from category/tier/behavior/stats/metadata-tags/abilities — zero JSON modification. All archetype tables are code constants | **port-to-C#** pure (tables → static readonly data) |
| `combat_data_loader.py` | 450 | `CombatDataLoader`: **dynamic** generation (no JSON) of weapon `AttackDefinition`s, enemy attacks, `ProjectileDefinition`s from weapon type/range/speed/tags; caches; `hitbox_def_from_attack` | **port-to-C#** pure |
| `player_actions.py` | 234 | `PlayerActionSystem`: dodge roll, i-frames, cooldown; `InputBuffer` (200 ms); dodge tuning loaded from `combat-config.JSON > dodgeMechanics` | **port-to-C#** pure timers; input capture is engine glue |
| `screen_effects.py` | 122 | `ScreenEffects`: screen shake (pixel offsets), entity flash registry, dodge afterimages. `hit_pause` is a deliberate no-op | **engine-replaces** (Camera3D trauma shake, shader flash, GPUParticles) — keep the *parameters* (intensities/durations table §5.9) |
| `combat_event.py` | 35 | `CombatEvent`, `HitEvent` dataclasses — inter-system contract | **port-to-C#** (readonly record structs) |
| `__init__.py` | 40 | Re-exports + `USE_ACTION_COMBAT = True` master toggle (`__init__.py:17`) | **port** as a config flag; consider dropping the legacy fallback entirely (§11) |

Related but outside `Combat/` (documented because the critical path runs through them):
- `core/game_engine.py:3464–4078` — action combat orchestration incl. `_ac_process_hit` (**port**: becomes the CombatManagerNode glue).
- `core/effect_executor.py:153–171` — enemy-defense application for the tag path (**owned by the tag-system port**, contract restated in §5.2 step 10).
- `entities/components/weapon_tag_calculator.py` — hand/precision/armor-pen/crushing modifiers (owned by entities port; values in §5.4).
- `systems/training_dummy.py` (subclasses `Enemy`), `systems/turret_system.py` (attacks enemies) — downstream consumers.

---

## 2. Public surface (what other subsystems actually call)

### CombatManager (`combat_manager.py:130`)
| Member | Callers (file:line) |
|---|---|
| `CombatManager(world, character, rng=None)` | `core/game_engine.py:254` |
| `load_config(config_path, enemies_path)` | `core/game_engine.py:255–258` |
| `update(dt, shield_blocking, is_night)` | `core/game_engine.py:8537` (overworld frame update) |
| `update_dungeon_enemies(dt, pos, aggro, speed, shield_blocking)` | `core/game_engine.py:7766` |
| `spawn_initial_enemies(pos, count)` | `core/game_engine.py:278` (startup) |
| `spawn_dungeon_wave()` / `clear_dungeon_enemies()` | `core/game_engine.py:7658–7659, 7687–7688, 8359` |
| `player_attack_enemy_with_tags(enemy, tags, params, skip_visual, skip_los)` | **THE critical path**: `core/game_engine.py:3726` (`_ac_process_hit`, action combat), `:3973` (legacy sweep fallback), `combat_manager.py:1353` (instant AoE self-call) |
| `player_attack_enemy(enemy, hand)` | legacy click path — no live caller found outside tests/`_single_target_attack` family; kept for API compat (see §11 risks) |
| `_enemy_attack_player(enemy, shield_blocking)` | `core/game_engine.py:3827` (enemy hit routed via `_ac_process_hit`) — *private-by-name but called cross-module* |
| `_calculate_exp_reward(enemy)` | `entities/components/skill_manager.py:1031` (skill kills) — *private-by-name, cross-module* |
| `on_dungeon_enemy_killed(enemy, exp_earned)` | `entities/components/skill_manager.py:1049` |
| `get_all_active_enemies()` | `rendering/renderer.py:1404, 1906, 1923`; `core/game_engine.py` (many); `systems/turret_system.py:426+` |
| `get_enemy_entity_id(enemy)` / `find_enemy_by_entity_id(id)` | `core/game_engine.py:3603, 3706, 3814` |
| `get_enemies_in_range(pos, radius)` | turret targeting (`systems/turret_system.py`), skills |
| `get_enemy_at_position` / `get_corpse_at_position` / `loot_corpse` | `core/game_engine.py:2062–2273` (click handling) |
| `setup_action_combat(hitbox_system, combat_data)` | `core/game_engine.py:3504` |
| `on_chunk_unloaded(chunk_key)` | WorldSystem chunk-unload callback |
| `seed_rng(seed)` | `tests/integration/harness.py` (deterministic playtests) |
| `execute_instant_player_aoe(radius, skill_name)` | skill system (Whirlwind-type skills) |
| `.enemies` dict mutated directly | `systems/training_dummy.py:290–292` (`spawn_training_dummy`) |
| `.dungeon_manager` set directly | `core/game_engine.py:262` |

### Enemy / EnemyDatabase (`enemy.py`)
| Member | Callers |
|---|---|
| `Enemy` (class) | subclassed by `TrainingDummy` (`systems/training_dummy.py:46`, overrides `take_damage`/`update_ai`); type-imported by `systems/turret_system.py:11` |
| `Enemy.take_damage(damage, ...)` | effect_executor `_damage_target`, thorns (`combat_manager.py:2180` direct HP write), turrets |
| `Enemy.generate_loot()` | `entities/components/skill_manager.py:1037`, combat_manager kill paths |
| `EnemyDatabase.get_instance()` | `combat_manager.py:141`, `tools/content_xref_report.py:85`, tests |
| `EnemyDatabase.load_additional_file(path)` | `data/databases/update_loader.py:132` (Update-N content packs) |
| `EnemyDatabase.reload()` / `load_from_files()` | `world_system/content_registry/database_reloader` (WES generated hostiles hot-reload) |
| `AIState` enum | game_engine, renderer, dungeon logic |

### Action-combat classes
All constructed in `core/game_engine.py:_init_action_combat` (`:3478–3517`): `HitboxSystem`, `ProjectileSystem(hitbox_system)`, `AttackStateMachine('player')`, `PlayerActionSystem`, `ScreenEffects`, `CombatDataLoader`. `FACING_TO_ANGLE` used at `game_engine.py:938`. `USE_ACTION_COMBAT` checked at `game_engine.py:3471`. Renderer reads `ScreenEffects.shake_offset` / `flash_entities` / `afterimages` and `ProjectileSystem.get_active_projectiles()` for drawing; renderer also reads `Enemy.attack_anim_*` and `Enemy._attack_arc_degrees/_attack_radius/_attack_shape` fields directly for telegraphs (fields set at `enemy.py:1078–1142`).

---

## 3. Dependency edges

### Combat/ imports FROM other subsystems
| Import | Site |
|---|---|
| `data.models.world` (`Position`, `PlacedEntityType`) | `combat_manager.py:30`, `enemy.py:15` |
| `data.databases.chunk_template_db` (`ChunkTemplateDatabase`) | `combat_manager.py:31` (spawn pools read WES-generated chunk templates) |
| `core.effect_executor.get_effect_executor` | `combat_manager.py:32`, `enemy.py:13` — the tag pipeline executes all tag attacks and (F5) applies enemy defense |
| `core.tag_debug`, `core.debug_display` | `combat_manager.py:33–34`, `enemy.py:14` |
| `core.config.Config` | `enemy.py:939` (CHUNK_SIZE=16), `combat_manager.py:1119+` (DEBUG_INFINITE_DURABILITY) |
| `core.paths.get_resource_path` | `enemy.py:227`, `player_actions.py:35` |
| `entities.status_manager.add_status_manager_to_entity` | `enemy.py:12` (every Enemy gets a status manager) |
| `entities.components.weapon_tag_calculator.WeaponTagModifiers` | `combat_manager.py:877, 936, 1624` |
| `core.geometry.target_finder.TargetFinder` | `combat_manager.py:1096` (chain-damage enchant) |
| `systems.attack_effects` (visuals) | `combat_manager.py:1462, 1943`; `enemy.py:1305` |
| `systems.collision_system` (LOS raycast) | `combat_manager.py:1463, 1944` |
| `systems.world_system.PlacedEntityType` | `combat_manager.py:589` (turret targeting; duplicate of the `data.models.world` import at :30) |
| `events.event_bus.get_event_bus` | inline at every publish site (§6) |
| `rendering.visual_effect_bridge` | inline publishes (§6) |
| `core.config.Config` via `core.config` | durability debug flag |
| `Combat.attack_profile_generator` | `enemy.py:371, 487` (definition load-time attack generation) |

### Who imports Combat/
`core/game_engine.py` (:64, :938, :3471–3483, :3608); `systems/turret_system.py:11`; `systems/training_dummy.py:12`; `data/databases/update_loader.py:132`; `world_system/content_registry` (reloader → `EnemyDatabase`); `tools/content_xref_report.py:85`, `tools/prompt_editor.py:29` (path only); `rendering/renderer.py` (indirectly, through `engine.combat_manager`); tests (`tests/test_enemy_abilities_loading.py`, `tests/integration/test_02_combat.py`, `test_10/11/12`, `test_database_reload_e2e.py`, `test_phase4_npc_hub.py:180`).

**Hidden coupling call-outs**:
- `skill_manager.py:1031/1049` and `game_engine.py:3827` call **underscore-private** CombatManager methods. In C#, make `CalculateExpReward`, `EnemyAttackPlayer` internal/public.
- Thorns writes `enemy.current_health` directly (`combat_manager.py:2180`) instead of `take_damage` — bypasses aggro/flee triggers. Preserve or consciously fix.
- Renderer reads Enemy private-ish `_attack_*` fields — define a proper telegraph read-model in C#.
- `TrainingDummy` relies on `Enemy.update_ai`'s exact signature (`enemy.py:731` comment).

---

## 4. Engine coupling (pygame / rendering / input / clock)

The `Combat/` package itself imports **zero pygame** — it is already engine-clean. Coupling is at the seams:

| Touchpoint | Site | Godot redesign |
|---|---|---|
| Angle convention: degrees, 0=right, **90=down** (pygame y-down) | `hitbox_system.py:5–6`, `player_actions.py:14–19` (`FACING_TO_ANGLE down=90`), all `atan2(dy,dx)` uses (`combat_manager.py:1510`, `enemy.py:780,1123`, `game_engine.py:3875`) | XZ plane mapping with one documented sign convention (§9) |
| Mouse aim: cursor→screen-center delta | `game_engine.py:3684–3691` (`pygame.mouse.get_pos` for combo aim), `:3870–3877` (initial attack aim) | camera ray → ground-plane intersection |
| Shield-block input: right-mouse or X held | `game_engine.py:7763–7764` | InputMap action, passed into pipeline unchanged |
| Clock units **mixed**: seconds in `CombatManager.update`/`Enemy.update_ai`; **milliseconds** in ASM/hitbox/projectile/player_actions | conversions at `combat_manager.py:598` (`dt*1000`), `enemy.py:784`, `game_engine.py:3541` | standardize on seconds (double) in C#; keep ms only in data values, convert once at load |
| Console `print()` as combat log throughout the pipeline | `combat_manager.py` everywhere (e.g. :898, :1032, :2022) | replace with structured combat-log events; do NOT keep stdout in hot path |
| `ScreenEffects.shake_offset` in **pixels**, applied by renderer | `screen_effects.py:70–73` | Camera3D trauma shake; convert magnitudes |
| Entity flash / afterimages consumed by renderer | `screen_effects.py:38–55` | shader param / ghost mesh instances |
| Attack telegraph render data on Enemy (`attack_anim_timer/angle/tags/lunge`, `_attack_arc_degrees/_radius/_shape`, `windup_progress`) | `enemy.py:609–627, 1078–1142, 1179–1193` | keep as read-model; drive Godot telegraph decals/meshes |
| Visual dispatch inside logic: `attack_effects.add_attack_effect` / `add_blocked_indicator` / `add_area_effect` | `combat_manager.py:1493–1557, 1997–2005`; `enemy.py:1297–1376` | strip out; emit typed events, VFX layer subscribes |
| Damage numbers spawned by engine glue | `game_engine.py:3754–3763` | Label3D pool |
| `enemy._pending_screen_shake` tuple polled by engine | `combat_manager.py:2012`, `game_engine.py:4080–4087` | event instead of poll |
| Dungeon/turret world queries (`world.placed_entities`) | `combat_manager.py:588–593, 1929–1932` | world service interface |
| LOS via tile-grid collision system | `combat_manager.py:1480–1504, 1957–1977` | `PhysicsDirectSpaceState3D.intersect_ray` behind an `ILineOfSight` interface |

---

## 5. Constants & formulas (exact, from code)

### 5.1 Tunable knobs (env-read once at import — port as config)
- `_STR_DMG_PER_POINT = float(env CRUX_STR_DMG_PER_POINT, default 0.05)` — `combat_manager.py:17`
- `_LCK_CRIT_PER_POINT = float(env CRUX_LCK_CRIT_PER_POINT, default 0.12)` — `combat_manager.py:24` (**retuned 0.02→0.12** 2026-07-11; sacred per migration brief)

### 5.2 THE critical path — `player_attack_enemy_with_tags` (`combat_manager.py:1449–1913`) → effect executor
This is the ONLY melee path real players hit (action combat is shipped mode). Exact composition order when
`"baseDamage" in effect_params` (`:1608–1693`):

1. **Start**: `base = effect_params["baseDamage"]`. Upstream (`game_engine.py:_get_weapon_effect_data:523–570`): weapon `effectParams`, with `baseDamage` defaulted to avg of weapon damage range and multiplied by Sharpness-type `damage_multiplier` enchants.
2. **Weapon add**: `weapon_damage = character.get_weapon_damage() * hand_mult`; if `> 0`, `base += weapon_damage` (`:1630–1634`). `hand_mult`: 2H ×1.2, versatile without offhand ×1.1 (`weapon_tag_calculator.py:29–37`). ⚠ **Weapon damage is effectively counted twice** (once inside `baseDamage`, once added here). This is shipped, test-locked behavior — replicate, do not "fix".
3. **STR**: `base *= 1.0 + STR * 0.05` (`:1637–1638`).
4. **Titles**: `base *= 1.0 + titles.get_total_bonus('meleeDamage')` (`:1641–1642`).
5. **Enemy-type titles**: `base *= character.get_enemy_damage_multiplier(enemy)` (beastDamage etc., primary target's multiplier shared across multi-target geometry — documented approximation, `:1648`).
6. **INT elemental** (F9): if any tag ∈ {fire, ice, lightning, poison, arcane, shadow, holy}: `base *= 1.0 + INT * 0.05` (`:1653–1659`).
7. **Crushing**: if weapon has `crushing` tag AND `enemy.definition.defense > 10`: `base *= 1.20` (`:1662–1663`; value from `weapon_tag_calculator.py:114–116`).
8. **Skill buffs (empower)**: `base *= 1.0 + max(get_damage_bonus('damage'), get_damage_bonus('combat'))` (`:1666–1672`).
9. **Crit — applied LAST on fully-bonused damage** (F4/F6): `if rng.random() < _player_crit_chance(weapon_tags): base *= 2.0` (`:1678–1682`).
10. **Enemy defense — applied per-target inside the effect executor** (F5): caller sets `effect_params["_apply_enemy_defense"]=True` and `"_armor_penetration"` (`:1691–1692`); executor (`core/effect_executor.py:162–171`): `effective_def = def * (1 - armor_pen)`; `reduction = min(0.75, effective_def * 0.01)`; `damage *= (1 - reduction)`. Armor pen: `armor_breaker` tag = 0.25 (`weapon_tag_calculator.py:100–101`). **Skill/spell damage does NOT get defense** (historical; flagged open question in code comment `:1685–1690`).
11. **Damage application**: `effect_executor._damage_target` → `Enemy.take_damage` subtracts **float** — no rounding anywhere in the pipeline. UI casts `int(damage)` for numbers only (`game_engine.py:3755`).

**Post-hit, same call** (order): lifesteal enchant heal = `final_damage * min(value, 0.50)` (`:1714–1728`); consume-on-use buffs (`:1731–1732`); weapon onHit enchant statuses (`_apply_weapon_enchantment_effects` `:1233–1296`: `damage_over_time`→burn/poison/bleed with duration+dps from enchant, `knockback`→executor `_apply_knockback`, `slow`→duration+`speed_reduction` default 0.3); kill handling → EXP (`:1766–1770`), auto-loot outside dungeons (`:1773–1783`), on_kill triggers (`:1796`); durability loss 1 (proper) / 2 (tool-as-weapon) (`:1825–1846`); stat-tracker records (`:1848–1904`).

### 5.3 Crit resolution — `_player_crit_chance` (`combat_manager.py:857–882`), single source of truth (F3)
```
chance = 0.12 * character.get_effective_luck()            # LCK incl. title/skill luck bonuses (character.py:2332)
       + pierce buff (buffs.get_total_bonus('pierce','damage') or fallback ('pierce','combat'))
       + 0.10 if weapon has 'precision' tag               # weapon_tag_calculator.py:68–69
       + titles.get_total_bonus('criticalChance')
Crit multiplier = 2.0 exactly. No cap on chance.
```

### 5.4 Weapon-tag modifiers (`entities/components/weapon_tag_calculator.py`)
2H ×1.2; versatile-no-offhand ×1.1 (:32–35) · precision +0.10 crit (:68–69) · armor_breaker 25% armor pen (:100–101) · crushing +20% vs defense>10 (:114–116).

### 5.5 Legacy paths (divergences to be aware of — see §11 for drop recommendation)
- `player_attack_enemy` (`:884–1231`): **int-casts** weapon damage twice (`:926`, `:960`) — rounding differs from action path; defense applied inline (`:1024–1026`) same 0.75-cap formula; **durability charged TWICE** (`:1117–1148` with DEF-multiplier+Unbreaking, then again `:1209–1229` flat 1/2) — a real bug on this path.
- `_single_target_attack` (AoE devastate sub-path, `:714–855`): F8-aligned to STR×0.05 and shared crit; simplified (no hand/title/INT), defense without armor pen (`:770–771`).
- `_execute_tag_attack_aoe` (`:1357–1447`): STR + meleeDamage + empower, **no crit**, no defense flag — devastate AoE bypasses both (executor applies defense only when flag set — it is NOT set here).

### 5.6 Enemy → player pipeline — `_enemy_attack_player` (`combat_manager.py:1938–2198`)
```
damage       = uniform(damage_min, damage_max)            # enemy.perform_attack, enemy.py:1195–1199
             * attack.damage_multiplier                    # per-attack from generated profile (:2025)
def_stat     = DEF * (1 - weaken_reduction if 'defense' affected)   (:2029–2040)
def_mult     = 1 - def_stat * 0.02                                   (:2042)
armor_bonus  = equipment.get_total_defense() * (1 + DEF * 0.03)      (:2049–2052, F7: DEF armor-effectiveness)
armor_mult   = 1 - armor_bonus * 0.01                                (:2055)
prot_mult    = 1 - Σ(armor 'damage_reduction' enchants)              (:2057–2073)
final        = damage * def_mult * armor_mult * prot_mult
if shield_blocking and shield active: final *= (1 - shield_reduction)  # cap 0.75 via combat-config shieldMechanics (:2079–2085, character.py:2485)
final       -= fortify flat reduction (min 0)                         (:2087–2094)
final        = max(1, final)                              # minimum 1 damage (:2096)
```
Then: `character.take_damage(final, from_attack=True, ...)` (`:2101–2109`; armor durability loss inside character), thorns reflect = `final * min(Σ reflect enchants, 0.80)` written directly to enemy HP (`:2153–2191`), regen timer reset (`:2194`).
⚠ **No i-frame or range re-check at damage time** — see §11 risk #3.

### 5.7 EXP / loot / spawn
- EXP: T1/T2/T3/T4 = 100/400/1600/6400; boss ×10.0; dungeon ×2; `int()` truncation (`:2200–2214`; values also in `combat-config.JSON/experienceRewards`).
- Drop chance words → prob: guaranteed 1.0, high .75, moderate .5, low .25, rare .10, improbable .05 (`enemy.py:192–199`); qty uniform int in [min,max] (`enemy.py:682–689`).
- Spawning: MAX_PER_CHUNK=3 (`:431`); chunk = 16 tiles; spawn pos uniform(2,14) within chunk (`:453–454`) or (4,12) initial (`:514`); danger-level tier caps (`:302–319`): tranquil {1}, peaceful {1,2}, moderate {1,2,3}, dangerous/perilous/lethal {1..4}, normal {1}, rare {1..4}; density weights very_low .5 / low .75 / moderate 1 / high 2 / very_high 3 (`:55–61`); night: aggro ×1.3, speed ×1.15 (`:558–560`); safe zone: JSON radius 30 (code default 15, `:49`); respawn config §7.
- Corpse lifetime: 30 s code default (`:66`), 60 s in JSON.

### 5.8 Enemy AI & phased attacks (`enemy.py`)
- Melee engage range 1.5 tiles (`:871`, `combat_manager.py:606, 2599`); disengage at range×1.5 (`:891`); leash: dist > aggro_range×2 → reset (`:877`); flee threshold `flee_at_health` fraction (`:677`); wander cooldown uniform(2,5) s (`:563`); move speed = `definition.speed * 2` tiles/s (× night mult) (`:971`); enemies clamped to 3×3-chunk box around spawn chunk (`:932–951`); collision sliding X-then-Y (`:993–1022`); safe-zone entry forbidden (`:980–990`).
- Phased attack: windup→active→recovery in **ms**; per-attack from generated profile; `speed_factor = 1/max(0.3, attack_speed)`; tier speed mult {1:1.0, 2:0.95, 3:0.9, 4:0.85} (`:1071–1076`); damage fires at `active_start` (`combat_manager.py:598–601`); cooldown after = full cycle + `1/attack_speed` (`:1145`); ability lunge ids {leap_attack, charge_attack, pounce} (`:1417`).
- Visual size = category base {beast 1.0, ooze 1.0, insect 1.0, construct 1.2, undead 1.0, elemental 1.1, aberration 1.3, dragon 1.5, humanoid 1.0} × tier mult {1:1.0, 2:1.4, 3:2.0, 4:3.0}, clamp [1.0, 8.0] (`:135–163`). Hurtbox radius = `max(0.4, visual_size*0.4)` (`:166–168`). Player hurtbox radius 0.35 (`game_engine.py:3501`).

### 5.9 Action-combat data tables
- Weapon profiles (`combat_data_loader.py:29–40`): sword_1h arc 55° w300/a200/r240 · sword_2h 75° 500/300/400 · dagger 25° 160/120/160 · axe 65° 400/240/360 · mace 50° 440/260/400 · hammer_2h 75° 600/360/500 · spear 15° 360/200/300 · staff 30° 400/240/320 · bow projectile 600/100/400 · unarmed 50° 200/160/200. All × `1/max(0.3, attack_speed)`; cooldown 100 ms × factor; hitbox radius = actual weapon range; `offset_forward 0.8`; movement mult during attack 0.7.
- Enemy attack archetypes: full tables in `attack_profile_generator.py:33–105` (9 categories × primary/secondary/heavy with shape/arc/range/windup/active/recovery/weight/dmg_mult) + behavior mods (passive 1.15/1.1, docile 1.2/1.15, stationary 1.3/1.2, territorial 1/1, aggressive 0.85/0.9+heavy, boss 0.9/0.85+heavy `:97–105`); tier range mult {1:1.0, 2:1.15, 3:1.3, 4:1.5} (`:179`); tanky (def>20, speed≤0.8): arc ×1.2, windup ×1.1, active ×1.15; agile (speed≥1.3, def<15): windup/recovery ×0.85, arc ×0.85, range ×1.1 (`:188–189, 316–327`); heavy attack for boss/aggressive/T3+; secondary for T2+.
- Projectiles (`combat_data_loader.py:230–296`): speed 12 t/s, range 10 t, hitbox radius 0.3, homing 0.5 if homing/seeking tag, gravity 0, piercing from pierce tag; element colors table `attack_profile_generator.py:43–53`.
- Dodge (`combat-config.JSON > dodgeMechanics`, defaults `player_actions.py:109–112`): duration 250 ms, speed ×3.0, cooldown 800 ms, i-frames 200 ms; input buffer window 200 ms (`:57`).
- Screen shake: enemy-attack {tier: 2/4/6/9} intensity, {100/150/200/280} ms (`combat_manager.py:2010–2011`); kill {2/3/5/8} @150 ms (`game_engine.py:3787`); player-hit {2/3/5/7} @ {80/120/180/250} ms (`game_engine.py:3832–3834`).
- Sacred constants cross-check: tier multipliers T1–T4 = 1/2/4/8 and EXP curve live in progression/leveling, not Combat; damage formula and 75% def cap and LCK 0.12 verified above. Durability floor (50% effectiveness at 0) is enforced in equipment effectiveness code, not Combat — Combat only decrements with `max(0, ...)`.

---

## 6. Event topics

### GameEventBus (`events/event_bus.py`) — publish-only from Combat
| Topic | Site | Status |
|---|---|---|
| `"DAMAGE_DEALT"` | `combat_manager.py:781` (`_single_target_attack`), `:1052` (`player_attack_enemy`) | ⚠ `:1052` publish is **dead**: `:1056` references undefined `damage_type` → NameError swallowed by `except Exception` — legacy-path WMS damage events silently never fire |
| `"ENEMY_KILLED"` | `combat_manager.py:817, 1163` | works (legacy paths) |
| `"PLAYER_HIT"` | `combat_manager.py:2127` | works (all enemy melee) |
| `"STATUS_APPLIED"` | `combat_manager.py:1897` | works (tag path) |
| `"DODGE_PERFORMED"` | `player_actions.py:165` | ⚠ **dead**: `:167` references undefined `position` → NameError swallowed — never publishes |

⚠ Note the tag path (`player_attack_enemy_with_tags`) publishes **no** bus `DAMAGE_DEALT`/`ENEMY_KILLED` itself — WMS coverage on the shipped path comes from `stat_tracker.record_*` calls (`:1868–1888`) and the visual bridge. Porter must preserve which sink fires on which path, or consolidate deliberately.

### visual_effect_bridge (rendering-side pub) — fire-and-forget, ImportError-guarded
`publish_damage_dealt` (`combat_manager.py:798, 1740`; `game_engine.py:3776, 3998`), `publish_enemy_killed` (`:843, 1800`; `game_engine.py:3801, 4021`), `publish_player_hit` (`:2142`; `game_engine.py:3838`), `publish_attack_started` (`game_engine.py:3911`).

### Internal contract objects (not bus): `CombatEvent` (`phase_change` etc.) from ASM; `HitEvent` from HitboxSystem/ProjectileSystem consumed by `game_engine._ac_process_hit` (`:3697`).

### Subscriptions: none. Combat/ never subscribes to the bus.

---

## 7. Content JSON consumed (reused verbatim in Godot)

| File | Loader | Notes |
|---|---|---|
| `Definitions.JSON/combat-config.JSON` | `CombatConfig.load_from_file` (`combat_manager.py:69–124`) via `game_engine.py:255`; `dodgeMechanics` separately by `player_actions.py:27–45` | keys: experienceRewards (100/400/1600/6400, boss ×10), safeZone (r=30), spawnRates per danger level (min/max/interval/tierWeights), enemyRespawn (300 s base, tier mult 1/1.5/2/3, boss 1800 s — **loaded but never used**: no respawn-timer consumer found; dynamic spawnInterval drives repopulation instead), combatMechanics (cooldowns 1.0/0.5, corpse 60, timeout 5.0), damageFormulas (reference-only strings), shieldMechanics (max 0.75), dodgeMechanics |
| `Definitions.JSON/hostiles-1.JSON` + sacred glob `hostiles-*.JSON` + generated overlay `hostiles-generated-*.JSON` | `EnemyDatabase.load_from_file` / `load_from_files` (`enemy.py:212–247, 270–385`) | parses abilities[] (triggerConditions), enemies[] (stats.damage as [min,max], drops with word-chances, aiPattern, metadata.tags/narrative); icon path auto-derived `enemies/{id}.png`; `visual_size`/`hurtbox_radius` computed NOT loaded |
| `Definitions.JSON/Chunk-templates-*.JSON` (+generated) | `ChunkTemplateDatabase` singleton (`combat_manager.py:235–237`; `data/databases/chunk_template_db.py`) | spawn pools read `enemy_spawns[id].density/spawn_weight` |
| `Update-*/hostiles*.JSON` | `EnemyDatabase.load_additional_file` via `data/databases/update_loader.py:132` | append semantics |
| *(none)* for weapon attacks, hitboxes, projectiles | `CombatDataLoader` generates dynamically (`combat_data_loader.py:1–13`) | stale-doc alert: older docs mention attack/projectile JSONs — they do not exist |

---

## 8. Persistent state (save/load)

- **Live enemies, corpses, spawn timers, active hitboxes/projectiles, ASM state: NOT persisted.** `systems/save_manager.py` contains no combat keys (verified — only `dungeon_state`, `map_state`, `faction_state`, `content_registry_state` at `save_manager.py:68–123` plus character/world data). World enemies respawn fresh via chunk spawning after load. Port contract: same (no combat serialization needed).
- `PlayerActionSystem.to_dict/from_dict` (`player_actions.py:224–234`, keys `total_dodges`/`successful_dodges`) — **dead code**: no caller in the save path. Real dodge stats persist via StatTracker SQL (`stat_tracker.py:893`, key `combat.dodge_rolls.successful`). Do not port the dead serializer.
- Dungeon progress persists through `dungeon_manager.to_dict()` (`save_manager.py:68`) — dungeon *enemies* are not saved; `clear_dungeon_enemies` on exit (`game_engine.py:8359`).
- Weapon/armor `durability_current` mutations made by Combat persist via equipment serialization (entities subsystem's contract).
- Combat's long-term memory footprint is the WMS SQLite (event publishes + 65 `stat_tracker.record_*` calls) — stays in the Python sidecar; Godot sends the same events over IPC.

---

## 9. 3D notes (what necessarily changes)

1. **Coordinate/angle convention**: everything is 2D tile-space (x, y), y-down, angles in degrees with 0=+x, 90=+y(down) (`hitbox_system.py:5–6`). Godot 3D: map game-plane (x, y) → (X, Z), Y=up. Define ONE conversion (`angle_godot = -angle_py` around Y, or keep atan2(z, x) with z≡y_py) and apply it at the glue boundary only — the ported math should keep the Python convention internally for test parity.
2. **Recommended architecture: flat combat plane.** All combat math (distances `enemy.py:640–644`, hitbox shapes, projectile motion, aggro/leash ranges, chunk clamps) is 2D. Port it as-is operating on XZ; ignore Y for combat except visuals. This preserves every constant and passes conformance tests unmodified. Matches the paused Unity plan's `GamePosition`/`DistanceMode` decision.
3. **Hitboxes**: arc/circle/rect/line vs circle (`hitbox_system.py:170–283`) stay 2D-on-plane. If/when vertical combat is wanted, add a height band check (|Δy| < h) rather than true 3D solids. Godot `Area3D` shapes are an alternative but introduce physics-tick timing and broadphase differences — keep the pure-math port for parity, use Areas only for optional debug visualization.
4. **Projectiles**: `gravity` field exists but is always 0 in generated data (`combat_data_loader.py:292`). In 3D, arrow arcs would move into Y — keep gravity=0 on the combat plane initially; homing steering math (`projectile_system.py:74–86`) ports unchanged on-plane.
5. **LOS**: tile-grid raycast (`systems/collision_system`) → `intersect_ray` on obstacle layer; keep the tag-based bypass set {circle, aoe, ground} (`combat_manager.py:1478`).
6. **Aim**: screen-center-to-cursor angle (`game_engine.py:3684–3691`) → camera ray to ground plane; facing lock during windup/active (`_attack_facing_locked`, `game_engine.py:3594–3597, 3907`) maps to rotation lock.
7. **Telegraphs**: renderer-drawn arcs from `Enemy._attack_arc_degrees/_radius` + `windup_progress` → decal/mesh sector on the ground; this is the single most important player-facing combat visual to preserve.
8. **Screen shake pixels → camera trauma**; entity flash → shader; afterimages → ghost meshes; damage numbers → billboard Label3D.
9. **Chunk system (16-tile)** is dimension-agnostic; spawn logic ports unchanged.
10. **Enemy positions are mutable `[x, y]` lists (`enemy.py:547`) vs Character's `Position` object** — unify on one `Vector2`/`GamePosition` struct in C#; renderer/anim glue reads both today.

---

## 10. Godot mapping

### Pure-logic assembly `Game1.Combat` (no Godot references; `dotnet test`-able)
| C# type | Ports |
|---|---|
| `CombatConfig` + `CombatConfigLoader` | `CombatConfig` (`combat_manager.py:40–124`), reads combat-config.JSON verbatim |
| `DamagePipeline` (static, RNG injected) | §5.2 composition + `_player_crit_chance` + enemy-defense step (co-owned with EffectExecutor port); `EnemyDamagePipeline` for §5.6 |
| `SpawnDirector` | danger levels, tier caps, weighted pools, chunk template lookup (`:250–546`) |
| `EnemyCombatDirector` | per-frame enemy orchestration: ability triggers, phased-attack start/resolve (`:548–670, 1915–1936, 2559–2622`) |
| `ExpLootResolver` | `_calculate_exp_reward`, loot rolls, dungeon 2x/no-loot rules |
| `EnemyDefinition`, `EnemyAttackDef`, `SpecialAbility`, `AIPattern`, `DropDefinition` | records from `enemy.py:36–168` incl. computed `VisualSize`/`HurtboxRadius` |
| `EnemyDatabase` | loader with sacred+generated overlay + `Reload()` (`enemy.py:174–536`) — hot-reload path for WES sidecar content |
| `EnemyBrain` (AI FSM) | `enemy.py:629–1251` states, movement intent output (glue applies movement) |
| `AttackStateMachine`, `AttackDefinition`, `AttackPhase` | `attack_state_machine.py` verbatim |
| `HitboxSystem`, `HitboxDefinition`, `Hurtbox`, `ActiveHitbox` | `hitbox_system.py` verbatim (plane math) |
| `ProjectileSystem`, `Projectile`, `ProjectileDefinition` | `projectile_system.py` verbatim |
| `AttackProfileGenerator`, `CombatDataGenerator` | `attack_profile_generator.py`, `combat_data_loader.py` (tables as static readonly) |
| `PlayerActionLogic`, `InputBuffer` | `player_actions.py` timers/i-frames/buffer |
| `CombatEvent`, `HitEvent` | `combat_event.py` as readonly record structs |
| `ScreenEffectParams` | just the §5.9 shake/flash tables (logic engine-side) |

### Engine glue (Godot nodes, thin)
- **`CombatSystemNode`** (child of World, NOT autoload — needs world/character refs like Python): owns the pure systems, runs the per-frame sequence from `game_engine.py:8537+3543–3622` (enemy update → phased damage → hurtbox position sync → hitbox/projectile update → `ProcessHit`), replaces `_ac_process_hit`.
- **`EnemyActor : CharacterBody3D`** — visual + movement application from `EnemyBrain` intents; telegraph child node reading windup progress; hurtbox registration mirrors `_register_enemy_action_combat` (`combat_manager.py:2243–2276`) with **stable GUID entity ids** replacing `f"enemy_{id(enemy)}"`.
- **`PlayerCombatController`** — input (attack toward cursor-ray, dodge, shield-hold), calls `AttackStateMachine.StartAttack` with the damage context built like `game_engine.py:3894–3904`; applies dodge velocity (`:3557–3576`).
- **`ProjectileVisual : Node3D`** pool driven by `ProjectileSystem` state; **`CombatVfx`** subscribes to typed C# events (flash/shake/sparks/death) replacing `attack_effects`/`ScreenEffects`/`combat_particles` calls; **`CameraShake`** on Camera3D.
- **Event bridge**: typed C# events in-process; serialized copies of the §6 bus topics over IPC to the Python WMS sidecar (topic strings preserved exactly).

---

## 11. Port complexity, ordering, risks

**Complexity: L** (XL if the tag/effect-executor port is counted; that is a separate subsystem but the damage
pipeline is inseparable from it — step 10 of §5.2 lives in `effect_executor.py`).

**Ordering constraints (must exist first)**:
1. `data.models` + JSON loaders (Position, Config, hostiles/combat-config/chunk-template loaders).
2. Entities: Character stats/equipment/buffs/titles (`get_weapon_damage`, `get_effective_luck`, `get_enemy_damage_multiplier`, `get_total_defense`, shield API), StatusManager, WeaponTagModifiers.
3. Tag system + EffectExecutor (executes every tag attack, applies defense, statuses, knockback).
4. Event bus + StatTracker IPC stubs (combat records ~20 stat types).
5. World/chunk system + collision/LOS interface.
6. Then Combat pure-logic, then Godot glue. Suggested internal order: combat_event → hitbox → projectile → ASM → data generators → enemy (def/db → brain) → player_actions → combat_manager decomposition → engine node.

**Top risks / gotchas**:
1. **Three divergent player damage paths.** Action tag path (shipped, §5.2), legacy click path (`player_attack_enemy`, int-rounding + double durability bug, no live caller), and devastate-AoE path (no crit, no defense). Recommendation: port ONLY the tag path + devastate path; drop `player_attack_enemy`/`_single_target_attack` as dead code after confirming nothing revives them (`USE_ACTION_COMBAT=False` fallback at `game_engine.py:3921–4039` also uses the tag path, so the legacy method is safe to drop).
2. **Weapon-damage double count** on the shipped path (§5.2 step 2) is intentional-as-shipped and test-locked (`test_12_combat_conformance.py`). Replicate byte-exact; do not "fix" silently — file a balance ticket instead.
3. **Enemy melee never uses hitboxes and ignores i-frames.** Enemy ASM instances are created and ticked (`enemy.py:783–784`) but their events are discarded; damage flows Enemy.phased-attack → `_enemy_phased_damage` → `_enemy_attack_player` with **no range/i-frame re-check at active_start** (`combat_manager.py:598–601, 1938+`). The i-frame check at `game_engine.py:3819` only guards enemy-owned hitbox/projectile hits — which are never created. Dodging enemy melee currently works only via LOS blockers, not distance or i-frames. Porting this asymmetry faithfully preserves balance; "fixing" it (enemy hitboxes in Godot) changes difficulty substantially. Decide explicitly.
4. **Silently-dead event publishes** (swallowed NameErrors): `DAMAGE_DEALT` on legacy path (`combat_manager.py:1056`, undefined `damage_type`) and `DODGE_PERFORMED` (`player_actions.py:167`, undefined `position`). In C#, these become compile errors — you must decide the intended payloads. The WMS sidecar currently receives no dodge events at all.
5. **Entity identity**: `f"enemy_{id(enemy)}"` (`combat_manager.py:2250, 2280`) uses CPython object identity — unstable and unportable. Replace with GUID/sequential id assigned at spawn; audit every string-id consumer (hitboxes, flashes, find_enemy_by_entity_id scans which are O(n) per hit).
6. **Mixed time units** (seconds vs ms across module boundaries, §4) — highest-probability source of subtle port bugs; normalize once.
7. **Cross-module private calls** (`_enemy_attack_player`, `_calculate_exp_reward` from skill_manager/game_engine) and **direct field mutation** (training dummy inserting into `.enemies`; thorns writing `current_health`) must become explicit APIs.
8. **RNG determinism**: `CombatManager._rng` is injectable (D1, `:133–201`) and the headless harness depends on it — thread a `System.Random` seam through DamagePipeline, SpawnDirector, Enemy loot/AI (note: `Enemy` uses the *global* `random` module today, not the injected one — loot/wander are NOT covered by `seed_rng`; replicate or consciously unify).
9. **Hot-reload contract**: `EnemyDatabase.reload()` (never-raise, keep-stale-on-failure semantics, `enemy.py:249–268`) is called by the WES content registry after the sidecar writes `hostiles-generated-*.JSON` — the C# database must expose the same file-watch/reload entry point for the sidecar IPC loop.
10. **Dead/vestigial code to drop, not port**: `EnemyDatabase._create_placeholders` wolf fallback (`enemy.py:504–524`) — keep or simplify; `CombatDataLoader.get_enemy_hurtbox_radius` hardcoded 0.5 (`combat_data_loader.py:356–358`, shadowed by `definition.hurtbox_radius` which is always > 0 at `combat_manager.py:2252–2258`); `ScreenEffects.hit_pause`/`is_paused`/`get_effective_dt` no-ops (`screen_effects.py:34–36, 99–106`); `PlayerActionSystem.to_dict/from_dict` (§8); `enemyRespawn` config block with no consumer (§7); `AttackDefinition.combo_next` — never set by generators, so the combo window at `attack_state_machine.py:167–168` never opens (combo counting at `game_engine.py:3667–3695` still runs off buffered input).

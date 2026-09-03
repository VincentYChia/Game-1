# The Resolute Backend Contract — terrain + combat rules the forward model must own

**Status:** identification pass (2026-07-28). This is the "encompass and identify everything" deliverable.
The *next* pass brings each item below to bit-fidelity.
**Branch:** `crux-foundry`. **Authoritative sources:** `AGENT_DESIGN.md` (obs/action/fitness law),
`GODOT_PORT_PLAN.md` (the forward-model fork, now resolved to the shared kernel), and
`../Godot-Migration/inventory/06-combat.md` (the combat port contract — trusted for damage constants).

---

## 0. Why this document exists

The combat-AI foundry evolves metadata-conditioned agents (hostile-pack + player) that train against a
**forward model** — a deterministic simulator of the game's rules. `GODOT_PORT_PLAN.md` resolved which
simulator: **`Game-1-Godot/src/Game1.Core/`**, the pure, headless, `dotnet test`-able C# kernel — *not*
the Godot node scripts (`scripts/*.cs`), *not* (long-term) the heavy Python engine.

The **Design Law** (`AGENT_DESIGN.md`) says an agent can only learn a tactic its **observation, action,
AND fitness** all afford — and all three bottom out on the **transition function** (the terrain + combat
rules). So "get combat to highest fidelity / solve pathing / visuals whatever, backend resolute" =
**make every rule below exist in `Game1.Core`, deterministically, at the right fidelity.** This document
is the complete list, each item tagged by two axes:

| Axis | Values |
|---|---|
| **Authority** | `[2D-AUTH]` a faithful 2D-Python rule exists → match it bit-for-bit · `[NET-NEW]` 3D-only, no authority → author then FREEZE as the new authority |
| **Kernel status** | ✅ RESOLUTE (in `Game1.Core`, golden-tested) · 🟡 DEAD (in-kernel but unwired/untested at runtime) · 🟠 NODE-ONLY (only in `scripts/*.cs` — trainer cannot use) · 🔴 ABSENT (nowhere in Core) |

The headline: **the computational hot path is already RESOLUTE**; the gaps are structural (spawn director,
enemy-ability execution, dodge, the walkability/LOS oracle) and one cascading **fork** (flat plane vs 3D physics).

---

## 1. THE FORK that decides everything — movement / collision / verticality

> **DECIDED (2026-07-28): B — True 3D physics, with verticality as a first-class combat input.**
> Scope: **faithful core + author key net-new verbs** (port the 2D-authoritative pieces bit-for-bit AND
> author dodge/i-frames + player-facing now, freezing each as new authority).
>
> **Physics authority — RESOLVED (2026-07-28): train in HEADLESS GODOT.** Godot (already C#/.NET 8) owns
> movement / collision / verticality / jump / gravity via its physics; the headless Godot host calls
> **`Game1.Core` in-process (no IPC)** for all **combat resolution** (hitbox overlap, damage pipeline,
> crit/defense, status, enemy-attack resolution) fed the positions from Godot bodies. So `Game1.Core` stays the
> certified combat authority; Godot becomes the movement authority. The enemy tile-step (`EnemyRuntime.MoveTowards`)
> **retires** — enemy AI splits along the adapter line: **decision** (target/commit) stays in kernel+policy,
> **movement actuation** (velocity + `MoveAndSlide`) goes to Godot.
>
> **Determinism posture (why this is acceptable):** the evolved policy is a *reactive heuristic over abstract
> features*, not an input replay, so it tolerates small physics drift ("engine-agnostic by construction").
> We rely on **same-platform** determinism only — Godot 4 on **Jolt** (deterministic same-build; kinematic
> character movement, not dynamic rigid bodies) + fixed physics tick + seeded scenario RNG (`PythonRandom`) —
> which is enough for common-random-number fitness and same-machine reproducibility. Cross-platform bit-identity
> (train-on-Crux → deploy-on-Windows) is *given up* and does not matter for a reactive policy.
> **Costs accepted:** lower throughput than a tight .NET loop (mitigate: many episodes/process, step physics
> headless-fast, process-per-core on Crux); heavier Crux packaging (a headless Godot export vs a DLL).
> **Wins:** zero sim-to-real gap; real, well-tuned 3D physics for free; pathing/LOS/collision come free from
> `NavigationServer3D` + `intersect_ray` (the unported 2D A*/Bresenham LOS are moot).
> **First task of the fidelity pass = a determinism self-check** (seeds 1,2,1: fixed scenario, step headless
> twice, assert identical) to confirm Jolt + fixed-tick + seeded-RNG reproduces same-platform before investing.

This is the single decision the whole fidelity pass hangs on, because it cascades into determinism,
pathing, FOV, and the obs schema.

Today the game runs a **split, inconsistent movement model**:

- **Enemy** = the ported deterministic **2D-plane tile-step** — `EnemyRuntime.MoveTowards`
  (`Game1.Core/Combat/EnemyRuntime.cs:370-427`): `speed*dt*2`, 3×3-chunk clamp, X-then-Y collision slide,
  safe-zone block. In the *kernel*, deterministic, golden-pinned. **This is the authority the trainer sees.**
- **Player** = a **Godot 3D physics body** — `PlayerController.cs` (`CharacterBody3D` + `MoveAndSlide` +
  gravity 24 + jump 10 + camera-relative WASD). **Node-only, non-deterministic, frame-coupled, and the
  trainer cannot use it.** In 2D there was *one* shared plane-step for both (`character.py:772-841`); the
  3D rebuild diverged the player onto physics.

Plus **verticality snuck in as gameplay**: `TerrainHeightField` height feeds a real **combat height-gate**
(melee only connects if `|playerY − enemyTerrainH| ≤ 2.0`, `CombatWorld.cs:837-844`) and **fall damage**
(`excess*8`) — both `[NET-NEW]`, both **NODE-ONLY**, both invisible to the kernel/trainer. A doc comment
claims height is "presentation only"; it is not.

**The decision:**

| | **A · Flat combat plane** (recommended by all 3 design docs) | **B · True 3D physics** |
|---|---|---|
| Movement | keep the deterministic tile-step in the kernel for BOTH player + enemy (port `character.py` player step) | player + enemy on Godot kinematics (gravity/jump/slide) |
| Verticality | height is visual; combat is planar; drop the height-gate OR demote it to an optional band-check | height/jump/gravity are first-class combat inputs |
| Determinism | ✅ bit-reproducible today (resolves the 0.5% Python drift by construction) | ⚠️ cross-platform float non-determinism → **invalidates trained policies** (the exact reason `GODOT_PORT_PLAN` PAUSED) |
| Authority | `[2D-AUTH]` — matches the whole ported kernel, conformance stays valid | `[NET-NEW]` — every movement rule authored + frozen from scratch, no golden oracle |
| Pathing | A* / walkability / LOS are planar (2D authority exists to port) | pathing becomes 3D nav-mesh — net-new |
| Agent obs | 2D bearings/distances (already computable) | must add height/vertical terms to the schema |

**06-combat §9.2, AGENT_DESIGN, and GODOT_PORT_PLAN all recommend A** (flat plane), keeping height as an
*optional* height-band overlay only if vertical combat is genuinely wanted. Choosing A means the kernel is
already ~80% resolute; choosing B means re-authoring the movement authority and re-proving determinism.

Everything in §2–§5 is written assuming the answer is pending; items marked `[FORK]` change meaning based on it.

---

## 2. The FORWARD MODEL — world & movement rules (the transition function's world half)

What the world does to an entity: where it can stand, what blocks it, how it moves, where things spawn.

| Rule | Authority | Kernel | Evidence | Note |
|---|---|---|---|---|
| Tile walkability (WATER or `walkable=False` blocks) | `[2D-AUTH]` | 🟡 partial | gen half ported (`ChunkGenerator.cs`); the **runtime `is_walkable` query** is only an injected `Func<Position,bool>` (`EnemyRuntime.cs:81`) | `world_system.py:1054-1103` |
| Resource + BARRIER occupancy blocking (sub-0.5-tile box) | `[2D-AUTH]` | 🔴 absent | folded into the injected delegate, no owned impl | `world_system.py:1086-1101` |
| **Collision-slide mover** (full→X-only→Y-only) | `[2D-AUTH]` | 🟡 DEAD | logic ported (`EnemyRuntime.cs:394-419`) but `IsWalkable` is **never assigned** → enemies phase through everything live | `collision_system.py:323-358` |
| **LOS raycast** (Bresenham tile-walk; `{circle,aoe,ground}` bypass) | `[2D-AUTH]` `[FORK]` | 🔴 absent | *no* `has_line_of_sight` anywhere in Core — biggest targeting gap | `collision_system.py:120-268` |
| A* pathfinding (8-way, octile, no corner-cut) | `[2D-AUTH]` | 🔴 absent | enemies use the simpler chunk-clamped seek, so this may be dead-for-training | `collision_system.py:364-538` |
| Enemy **chunk-clamp** (3×3 around spawn) | `[2D-AUTH]` | ✅ | `EnemyRuntime.cs:358-368` | no player analog |
| Enemy **safe-zone** exclusion (r=15) | `[2D-AUTH]` | 🟡 DEAD (movement) / 🟠 (spawn) | movement-block ported (`EnemyRuntime.cs:386-392`) but **unwired** (`CombatWorld.cs:890` passes no safe-zone); the spawn-gate half is node-only | `combat_manager.py:250-255` |
| Resource-exclusion radius (r≈8, DISTINCT from the r=15 above) | `[2D-AUTH]` | ✅ | `ChunkGenerator.cs:352-361` | two different radii, two owners — do not conflate |
| Chunk-type / biome roll, tile grid, water patterns | `[2D-AUTH]` | ✅ | `ChunkGenerator.cs` + `BiomeGenerator.cs`, golden-hashed | seed→identical world holds |
| Resource spawn director (count, tier cap, weighted pool) | `[2D-AUTH]` | ✅ | `ChunkGenerator.cs:220-400` | |
| **Enemy spawn director** (tier caps by danger, weighted pool, density weights, MAX_PER_CHUNK=3, night mults) | `[2D-AUTH]` | 🔴 absent → 🟠 **divergent** | Core has none; `CombatWorld.cs:246-288` does an **ad-hoc, wrong** spawn (danger≤2 skip, tier=danger≤4?1:2, cap 150) | `combat_manager.py:302-546` — **pack composition is authoritative for metadata agents and is currently wrong** |
| Chunk determinism (seed → reproducible) | `[2D-AUTH]` | ✅ | `PythonRandom.cs` + `BiomeGenerator.cs:30-45` | MT19937 byte-exact |
| Elevation / height | **NONE in 2D** → `[NET-NEW]` | 🟠 node-only | `TerrainHeightField.cs` (visual + height-gate); `Position.z` always 0 in 2D | `[FORK]` — see §1 |
| Player movement | `[2D-AUTH]` (2D) / `[NET-NEW]` (3D physics) | 🟠 node-only | `PlayerController.cs:27-93` vs `character.py:772-841` | `[FORK]` — the divergence |
| Gravity / Jump / Fall damage | `[NET-NEW]` | 🟠 node-only | `PlayerController.cs:16-92`, `CombatWorld.cs:234-241` | `[FORK]` — 3D-only verbs |
| World collision (StaticBody3D floor/walls) | `[NET-NEW]` | 🟠 node-only | `WorldBootstrap.cs:479-485` | **two collision systems**: player=physics, enemy=plane |

**Structural conclusion:** the *generation* of the world is resolute; the *runtime queries an agent needs*
(walkability, LOS) and the *enemy spawn director* are the real world-side holes, plus the movement `[FORK]`.

---

## 3. The FORWARD MODEL — combat resolution (the transition function's fight half)

What one entity does to another. **This layer is the strongest — nearly all RESOLUTE.**

| Rule | Authority | Kernel | Evidence |
|---|---|---|---|
| Player melee pipeline (§5.2 full composition, crit-LAST, defense seam) | `[2D-AUTH]` | ✅ | `TagAttackOrchestrator.cs:129-278` + `DamageComposition.cs` + `EffectExecutor.cs:110-172`; golden `TagAttackTests` |
| Enemy→player pipeline (§5.6: DEF mult, armor-eff F7, protection, shield, fortify, min-1, thorns) | `[2D-AUTH]` | ✅ | `EnemyAttackResolver.cs:15-108`; golden `GatheringTests.EnemyHits` |
| Crit chance (LCK 0.12 + pierce + precision + title) | `[2D-AUTH]` | ✅ | `CritChance.cs`; golden matrix |
| Defense reduction (`min(0.75, def*(1-pen)*0.01)`) | `[2D-AUTH]` | ✅ | `DefenseReduction.cs`; golden grid |
| Effect executor (geometry targeting, per-tag dmg, status, special mechanics) | `[2D-AUTH]` | ✅ | `EffectExecutor.cs:1-440`; golden |
| Enemy AI FSM + phased attacks (windup/active/recovery) | `[2D-AUTH]` | ✅ | `EnemyRuntime.cs:191-612`; golden `EnemyAiTests.EnemyAi_Scenarios_MatchPython` |
| Hitbox collision → HitEvent (arc/circle/rect/line vs circle) | `[2D-AUTH]` `[FORK]` | ✅ | `HitboxSystem.cs:78-286`; golden matrix — *plane math; 3D needs a height-band only if §1=B* |
| Projectile sim (homing, gravity, piercing, AoE-on-hit) | `[2D-AUTH]` | ✅ | `ProjectileSystem.cs:24-194`; golden |
| Attack state machine (player ASM + combo window) | `[2D-AUTH]` | ✅ | `AttackStateMachine.cs:69-227`; golden |
| Attack profile / combat-data generators | `[2D-AUTH]` | ✅ | `AttackProfileGenerator.cs`, `CombatDataLoader.cs`; golden |
| Status effects — DoT (burn 5/bleed 3/poison 2·stacks^1.2) | `[2D-AUTH]` | ✅ | `StatusEffects.cs:101-127`; golden |
| Status effects — CC (freeze/stun/root immobilize; slow/haste no-op on enemies, bug-compatible) | `[2D-AUTH]` | ✅ | `StatusEffects.cs:130-197`; golden |
| Special mechanics (knockback/pull/execute/lifesteal/dash/teleport/phase — all 2D X/Y) | `[2D-AUTH]` `[FORK]` | ✅ | `EffectExecutor.cs:212-405` — *no Z; 3D height decision needed for dash/charge across gaps* |
| EXP / loot (T1-4 100/400/1600/6400, boss ×10, seeded rolls) | `[2D-AUTH]` | ✅ | `TagAttackOrchestrator.cs:121-127`, `Enemies.cs:85-92`; golden — *dungeon 2×/no-loot NOT implemented* |
| **EnemyCombatDirector** (per-frame: ability-trigger vs attack-start → active_start → Resolve) | `[2D-AUTH]` | 🟠 node-only | pieces exist + tested individually; the **frame-sequencing loop** is only in `CombatWorld.cs` / hand-rolled in `GatheringTests` — trainer must own it | `combat_manager.py:548-670` |
| **Enemy special-ability EXECUTION** (route ability tags→executor, pay cooldown, inc uses) | `[2D-AUTH]` | 🔴 absent | only the **gating** (`CanUseSpecialAbility`) is ported; nothing *fires* the ability → enemy action space today = **{basic phased attack only}** | `enemy.py:1378-1426` |
| Enemy lunge (leap/charge/pounce) | `[2D-AUTH]` (planar) `[FORK]` | 🟡 partial | kernel knows the lunge *flag*; the gap-close movement + payload need the missing execution path; **3D arc height is NET-NEW** | `enemy.py:1417-1418` |
| Player skill activation (mana→cooldown→dispatch, class-affinity, buff/combat paths) | `[2D-AUTH]` | 🟡 **untested** | ported (`SkillRuntime.cs:258-445`) but **ZERO kernel tests**; leans on 3 glue callbacks (`InstantAoe`/`LiveEnemies`/`OnSkillKill`) | `skill_manager.py:190-262` |
| **Player dodge / i-frames / InputBuffer** | **`[NET-NEW]`** (no 2D authority — Phase 1.7 visual work) | 🔴 absent | `player_actions.py` (234 LOC) **completely unported**; only a debug tint token exists | the single biggest **player-agent** hole |

---

## 4. The ACTION space — what agents actuate (Design-Law leg 2)

| Action | Authority | Kernel | Note |
|---|---|---|---|
| `move_toward(x,y)` | `[2D-AUTH]` | 🟡 partial | `MoveTowards` is **private** + `EnemyRuntime` is **sealed** → need the **C0 policy-delegate hook** (~15 lines, composition not subclass) |
| `face(angle)` | `[2D-AUTH]` | ✅ | `FacingAngle` public settable — but `UpdateAi` re-writes it in Chase/Attack; hook must set it at the right tick point |
| `commit` (leave in ATTACK) | `[2D-AUTH]` | ✅ | set `State=Attack`; harness drives `CanAttack→StartPhasedAttack→Resolve` (as `ActionCombatTests` does); the hardcoded 1.5 melee trigger ports (L1 finding #2) |
| `target_idx` (pick target) | `[NET-NEW]` | 🟡 partial | `UpdateAi` is single-target (one `playerPosition`); multi-opponent selection is a harness/`TargetFinder` concern for the adversarial regime |
| `ability(id)` | `[2D-AUTH]` | 🔴 absent (execution) | gating ported; **no execution entry** — see §3 enemy-ability hole; player path needs a glue-free `ability(slot/id, target, aim)` API |
| `dodge` | `[NET-NEW]` | 🔴 absent | no 2D authority; author distance/duration/i-frame/cooldown + a `PlayerCharacter` invulnerability state, then freeze |
| Camera-relative aim/move | `[NET-NEW]` | 🟠 node-only | player WASD + skill aim are **camera-relative** (`PlayerController.cs:44-56`); a headless agent has no camera → must reframe **world-absolute** |

---

## 5. The OBSERVATION space + FITNESS + DETERMINISM (Design-Law legs 1 & 3)

**Observations** — the proven L1 policy's features are **all computable from Core today** (hp/reach/cooldown/
speed/tier/category/pos/dist/bearing off `EnemyRuntime`+`EnemyDefinition`; ally features derived by the encoder
from a harness-held roster). The gaps are L2+ and player-side:

| Obs feature | Authority | Kernel | Note |
|---|---|---|---|
| L1 self + geometry (hp_frac, reach, cooldown, dist, bearing…) | `[2D-AUTH]` | ✅ | direct reads; golden-pinned |
| ally_count / bearings / flank | `[NET-NEW]` | 🟠 harness | Core has no `pack` field — the encoder receives the roster (as `spawn_policy_pack` wires `e.pack`) |
| target windup / `is_in_windup` / `windup_progress` | `[NET-NEW]` | ✅ (enemy target) / 🔴 (player target) | public on `EnemyRuntime`; **absent on `PlayerCharacter`** |
| **target facing ("is it facing me?")** | `[NET-NEW]` | 🟡 partial | `EnemyRuntime.FacingAngle` yes; **`PlayerCharacter` has NO facing** — `LastMoveDirection` hardcoded null → `TargetFinder` returns constant (1,0). **Breaks the pincer's telegraph leg in the adversarial regime.** |
| LOS / obstacle flags | `[NET-NEW]` `[FORK]` | 🔴 absent | only the per-tile `IsWalkable` predicate; no LOS helper (segment-sample as a cheap proxy now) |
| mana_frac (player), target hp/reach | `[2D-AUTH]` | ✅ / partial | player mana public; enemies have no mana (gate on cooldown/health/distance) |

**Fitness** — mostly unwritten and the load-bearing piece:

| Term | Kernel | Note |
|---|---|---|
| progression score (`scoring.py`) | 🟠 node-only | balance-foundry currency, NOT combat fitness — keep separate |
| **hit-efficiency (landed/thrown)** | 🔴 absent | *the* signal L2 exists to validate; instrument `StartPhasedAttack→active` as "thrown" and an in-arc+range check at `Resolve` as "landed" |
| paired battery / CRN average | 🔴 absent | `DifficultyCalculator.cs` ported → the par/handicap normalizer has a source; the battery harness is net-new (.NET, C2) |
| Elo / TrueSkill + Hall of Fame | 🔴 absent | adversarial stage (C4); mandatory-with-HoF or co-evolution forgets |

**Determinism** — Core's strongest suit and the reason the fork matters:

- ✅ `PythonRandom.cs` (MT19937, **injected** per-`EnemyRuntime`) + `PyMath.cs` (divisor-signed mod for
  angle wrap) make the kernel **bit-reproducible**, golden-pinned including the damage field.
- ✅ This **RESOLVES the ~0.5% Python enemy-damage drift** (it came from Python's *global* `random.uniform`
  under `PYTHONHASHSEED`; Core injects the stream so it cannot recur).
- ⚠️ **Open risk 1 — the fork:** 3D-physics movement would reintroduce cross-platform float non-determinism
  and invalidate trained policies. This is *why* `GODOT_PORT_PLAN` paused.
- ⚠️ **Open risk 2 — harness:** each fight/candidate must get its **own** `PythonRandom` instance; sharing
  one across parallel Crux fights re-creates the ordering hazard the injection removed.

---

## 6. The gaps, tiered (what the fidelity pass actually does)

**Tier 1 — structural holes (must port/author before any real training):**
1. **Enemy spawn director** → port `combat_manager.py:302-546` into Core (or author+freeze a deterministic
   Core spawner). Pack composition is authoritative and currently *wrong* (`CombatWorld.cs` diverges).
2. **EnemyCombatDirector** → promote the per-frame orchestration loop from the node script into a testable
   Core class so the headless trainer drives the *same* sequencing the game does.
3. **Enemy special-ability execution** → port `use_special_ability`/`attack_with_tags` so `ability(id)`
   resolves damage/status and pays cooldown; wire the increment/reset-on-new-fight semantics.
4. **Walkability + LOS oracle** → give Core an owned `WorldWalkability` (WATER + flag + 0.5-box resource/
   barrier) and a Bresenham LOS, so the trainer has a pure, testable substrate instead of an injected
   hand-rolled predicate that can silently diverge. **Then wire it** (§Tier 2 #6).
5. **Player dodge / i-frames** `[NET-NEW]` → author `PlayerActionLogic` + an invulnerability state on
   `PlayerCharacter`; decide the i-frame semantics given enemy melee ignores i-frames today (§11 #3).

**Tier 2 — wiring / fidelity reconciliation (implemented but dead or divergent):**
6. Wire `EnemyRuntime.IsWalkable` + pass `safeZone` at runtime — **or** consciously declare enemies
   collision-free and delete the dead code so *training == shipping*. (Today `CombatWorld.cs:890` wires neither.)
7. Resolve the **player-movement `[FORK]`** so player + enemy share one model the trainer can see.
8. Add golden tests for `SkillManager.UseSkill` (the whole player ability space is ported but **unverified**).
9. A **headless full-fight integration test** (spawn → enemy tick → hitbox HitEvent → player damage → dodge)
   — coverage is per-class today; the assembled loop is only realized in the untested node script.

**Tier 3 — net-new-3D, author-then-freeze (in-scope only if §1 = B or you want combat verticality):**
10. Height-gate / fall-damage / jump-as-action → move into the kernel + `EnemyRuntime` state, or drop.
11. Player facing field (needed for the adversarial player regime's telegraph read).
12. 3D lunge/pounce arc; 3D FOV/LOS cone.

**Tier 4 — training plumbing (mostly harness-side, .NET, after the kernel is resolute):**
13. The **C0 policy hook** on `EnemyRuntime` (~15 lines; composition, non-breaking).
14. **Hit-efficiency instrumentation** (landed/thrown) — the fitness signal L2 validates.
15. World-absolute action reframing (drop camera-relative aim for headless).
16. Battery / Elo / Hall-of-Fame (C2 / C4).

---

## 7. Decisions required (the forks the user must resolve to start the fidelity pass)

1. **Movement/verticality (§1) — THE fork. ✅ DECIDED: B (true 3D physics + verticality as combat input).**
   **Pending sub-decision (the pivot):** does the **kernel own a deterministic 3D kinematic controller** that
   both Godot and the trainer defer to (recommended — preserves determinism + lean-.NET/Crux), OR do we **train
   in Godot headless** (accepts Godot's physics as the sim, abandons the pure-.NET forward model)? Everything
   downstream depends on this.
2. **Scope of "resolute." ✅ DECIDED: faithful core + author key net-new verbs.** Port the 2D-authoritative
   pieces bit-for-bit AND author dodge/i-frames + player-facing now (freeze as new authority). Tier-3 items
   (height-gate into kernel, 3D lunge arcs) are therefore **in scope**.
3. **Spawn director ownership.** Port `combat_manager` faithfully into Core, or author a fresh deterministic
   Core spawner and freeze it as the training distribution.
4. **Enemy ability layer for v1.** Port enemy special-ability execution now (rich pack behavior), or ship v1
   pack training with only the basic phased attack.
5. **Enemy collision/safe-zone at runtime.** Wire the ported (currently dead) collision + safe-zone so
   live == kernel, or declare enemies collision-free and delete the dead code.
6. **i-frame semantics.** Keep the Python asymmetry (enemy melee ignores i-frames; dodge only matters vs
   player-owned projectiles / future enemy hitboxes) or promote enemy melee to hitboxes in 3D (changes difficulty).

---

*Generated from a 5-way code sweep (terrain/walkability, Godot movement, kernel completeness, skills/abilities,
obs/fitness/determinism). Every claim is file:line-cited in the sweep; this doc is the synthesis.*

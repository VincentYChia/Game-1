# Combat-AI Foundry × Godot foundation — diagnosis & plan

> **STATUS 2026-07-24 — PAUSED (deliberately).** Do not resume training/porting until the
> *physical* combat is concrete and semi-frozen. The foundry optimizes behavior over a combat
> substrate that is still a 2D placeholder about to become 3D; the 2D→3D shift changes the
> observation/action space itself, and rule churn during active combat dev invalidates any
> trained policy. Combat's tactical *depth* is the hard ceiling on emergent intelligence, so
> compute should follow depth, not precede it.
>
> **Durable (keep):** the *method* — control-surface/policy-hook pattern, obs/action/fitness
> architecture, adapter split, scoring (paired battery → Elo), the three L1 gotchas. Survives 2D→3D.
> **Provisional (don't invest yet):** specific policies, the C# port (C0–C4), and the feature
> schema — **draft it, don't freeze it** (freezing now locks in the 2D placeholder's shape).
>
> **Resume when:** (1) movement/collision model (2D-plane vs 3D physics) chosen + stable;
> (2) core combat verbs (attack, dodge, abilities, ranged) live in `Game1.Core` and not churning;
> (3) a representative encounter exists to train against; (4) determinism survives the new movement
> model (3D physics → cross-platform float-determinism hazard).
>
> **Cheap high-leverage move meanwhile (only if convenient during combat dev):** build combat
> *trainable-by-design* — keep decision logic deterministic + separable from physics, expose a clean
> queryable state surface (target facing, ally positions, cooldowns, metadata), preserve the
> policy-hook seam. Then resuming is a port, not a retrofit.



**Context:** the game is being rebuilt on a **Godot foundation**. This does NOT invalidate
the combat-AI foundry — it *clarifies* its architecture. The whole bet (metadata-conditioned
policy = math over an abstract feature vector = a tiny portable file) is **engine-agnostic by
construction**. What the Godot move forces is one real decision: *which simulator do we train
against?* This doc diagnoses where L1 landed and lays out that fork.

---

## L1 diagnosis — the control surface works

Proven green across seeds / pack sizes / tiers (7·6·T2, 42·4·T2, 3·8·T1): a policy-driven pack
closes distance, spaces just inside reach, **pincers** (flank gaps hit the ideal 360/n within a
degree), commits swings, and deals damage — all by overriding one method (`update_ai`) and
actuating through the game's own primitives. Zero changes to combat_manager or content.

Three real findings surfaced (each a genuine engine interaction, not test noise):
1. **Origin safe-zone (r=15)** forbids enemies from approaching a player near spawn — real
   gameplay rule; a training arena must disable it or sit far from origin.
2. **Hardcoded 1.5 melee-trigger vs policy spacing** — long-reach enemies could park *outside*
   where a swing actually fires. Policy now caps approach inside the real envelope.
3. **Terrain/chunk noise strands members** — spawning on a wide ring drops members into
   unloaded/water chunks. Fixed with a controlled arena (clear a walkable plane, which also
   force-loads chunks), then stamp deliberate obstacles.

**Determinism caveat (open):** *decisions* are bit-identical run-to-run (positions, commits,
flank all match), but enemy *damage rolls* drift ~0.5% — almost certainly hash-seed-dependent
RNG ordering (`PYTHONHASHSEED`). Not yet pinned. **Lower priority now** — see forward-model fork;
if we don't train against the Python engine long-term, its determinism matters less.

---

## The architecture already transfers — the adapter pattern

The design (AGENT_DESIGN.md) already separates the portable core from the engine coupling:

```
   ENGINE STATE ──[Obs Encoder]──► Observation ──►┐
                    (per-engine)   (portable schema)│
                                                    ├─► POLICY ─► Action ──[Actuator Adapter]──► ENGINE
   feature schema is FROZEN & versioned            │  (portable)  (portable   (per-engine)
   (floats: distances, bearings, hp fracs,         │   = tiny      schema)
    tier, tag one-hot, cooldown/phase)             ┘   param file)
```

- **Portable (write once, runs anywhere):** the feature schema, the policy (a weight vector +
  fixed feature order — a few lines of arithmetic), the trainer, the fitness/scoring.
- **Per-engine (two thin adapters):** *encode observation* from engine state; *apply the action*
  via engine actuators. Python today: `PolicyEnemy._build_obs` + `_move_towards`/`start_phased_attack`.
  Godot later: read `CharacterBody2D` state + set velocity / trigger attack state.

Current code already honours this: `heuristic_pack_policy(Observation) -> Action` is **pure** (no
game imports); `PolicyEnemy` is the Python adapter. To "optimize for Godot" we make that split
*formal*: freeze the feature schema as a versioned, serializable spec both engines target.

**Corollary — the heuristic-not-NN choice pays off double under Godot.** A parameterized heuristic
(weights over interpretable features) ports to ~20 lines of GDScript/C# and stays inspectable. A
neural net would need a tensor runtime in Godot. Keep the policy a weight vector as long as it holds.

---

## The one real fork: which forward model do we train against?

| | A · Train-on-Python, export to Godot | B · Godot headless sim | C · Shared combat kernel |
|---|---|---|---|
| **What** | Keep Python engine as trainer; reimplement only the cheap runtime in Godot | Build a headless Godot sim loop; train against the deployment engine itself | Factor the pure combat rules (movement, hitbox geometry, damage, cooldowns, status) into a small deterministic kernel both engines + the trainer share |
| **Pro** | Reuses all L1–L4 work; runnable today | No sim-to-real gap; policy is native | Kills rule-drift by construction; trainer runs the kernel at C-speed (no engine boot) → huge Crux parallelism win; matches "rules never change, world grows" |
| **Con** | **Rule drift**: Python vs Godot combat differ → learned spacing/timing may not transfer | Godot determinism + Crux packaging less proven; rebuild harness in GDScript/C# | Highest upfront refactor; Godot must call the kernel (GDExtension/C#) or hold a lockstep port verified by golden vectors |
| **Risk it addresses** | none (fastest) | deployment fidelity | fidelity **and** training throughput |

### ✅ CONFIRMED (2026-07-23): the fork collapses to C — the kernel already exists

Verified in-repo: the Godot rebuild is **C#/.NET 8** under `Game-1-Godot/`, and combat is factored
into **`Game1.Core`** (`src/Game1.Core/`), a pure headless class library separate from the Godot
node scripts (`scripts/*.cs`). Evidence:
- `src/Game1.Core/Combat/EnemyRuntime.cs` is a **faithful line-for-line port of `Combat/enemy.py`** —
  identical `UpdateAi` FSM, `MoveTowards` (chunk clamp + collision slide + safe-zone block), the
  `State == Attack` commit gate, the hardcoded 1.5 melee trigger, `StartPhasedAttack`/`UpdateAttackPhase`.
- `PythonRandom.cs` + `PyMath.cs` = **determinism/parity by construction** (injected RNG; resolves the
  Python-side `PYTHONHASHSEED` drift caveat for the real target).
- `tests/Game1.Core.Tests/` already **drives headless fights** the way our probes do
  (`new EnemyRuntime(...)` → loop `UpdateAi(dt, playerPos)` → `StartPhasedAttack`), with
  `EnemyAttackResolver` as the damage applier and `EnemyAi_Scenarios_MatchPython` asserting parity.

**Implication:** the entire L1 control-surface design transfers ~1:1 to C#, and **all three L1 findings
apply identically** (same safe-zone block, same 1.5-vs-spacing envelope, same arena/chunk noise) — the
Python prototype de-risked the real target for free. Train against `Game1.Core` directly: lean .NET,
in-process, multi-threaded, deterministic, no Godot, no GPU — a far better forward model than booting
the heavy Python `GameEngine`, and Crux-native (just the .NET runtime + the DLL).

**One small enabler:** `EnemyRuntime` is `sealed`, so the C# control surface uses **composition, not
subclassing** — add an optional policy delegate checked at the top of `UpdateAi` (null ⇒ stock FSM, so
non-breaking), or expose `MoveTowards`/set `State` for an external driver. ~15 lines in `Game1.Core`.

### Revised roadmap (C# forward model)
- **C0** — add the policy hook to `EnemyRuntime` (delegate; null = stock FSM). Port `Observation`/`Action`
  structs + the pincer policy from `crux-foundry/agents/enemy_control.py`.
- **C1** — headless pack-fight harness in a `Game1.Foundry` console/test project (arena reset, spawn ring,
  obstacles, tick loop via `UpdateAi`+`UpdateAttackPhase`+`EnemyAttackResolver`) → re-run L1's 4 gates in C#.
- **C2–C4** — port L2–L4 (smart scripted policy → scenario battery/paired fitness → evolutionary trainer),
  all in .NET against `Game1.Core`. Elo/Hall-of-Fame + player policy at the adversarial stage.
- **Crux** — .NET job array over the trainer; policy artifact is a tiny weight vector the Godot game loads
  and evaluates in ~20 lines (the same `Game1.Core` the trainer used → zero sim-to-real gap).

The Python `crux-foundry/` tree stays as the **validated prototype** (proved the contract + control
surface + surfaced the three gotchas). Optionally keep it for fast concept iteration; the shippable
trainer is C#.

**Recommendation (phased) — original A/B/C reasoning, now resolved to C:**
1. **Now — prove the concept on Python (A-style, throwaway-tolerant).** Continue L2–L4 on the
   existing Python forward model to answer the *research* question: *does evolution over metadata
   actually yield smart, generalizing packs?* This is cheap, already built, and de-risks everything
   — if it fails on Python it fails on Godot too. Treat the Python trainer as a **prototype**, not
   the shippable pipeline.
2. **Then — align with Godot via C (shared kernel), if combat is the kind of thing that can be
   factored.** A shared, deterministic combat kernel is the most robust answer: one rule set, many
   front-ends, and a trainer that runs the rules directly at scale. Whether this is cheap or costly
   depends entirely on **how the Godot foundation implements combat** (see the open question).

Do these *regardless* of the fork, starting now, because they're pure win and make any path easier:
- **Freeze the feature schema** as a versioned, serializable spec (fixed float ordering, tag
  one-hot table, normalization rules). The policy artifact references a schema version.
- **Keep the policy pure** (no engine imports; already true) and the two adapters thin.
- **Specify actions as engine-neutral intents** (`move_toward(vec)`, `face(angle)`, `commit`,
  `target_idx`, later `dodge`, `ability(id)`), each engine mapping intents to its actuators.

---

## Open question that decides B vs C

**How is combat being implemented in the Godot foundation?**
- (i) Reimplemented in GDScript/C# from scratch → then that C# combat *is* the natural kernel;
  lean **C** (train against a port of it / call it directly), verified against Python via golden
  vectors during transition.
- (ii) Godot as a rendering/UX shell over a shared logic core (Python or native) → **C** is nearly
  free; the core is already the kernel.
- (iii) Undecided / physics-driven movement in Godot (real kinematics vs Python's tile-step) →
  rule drift is large; either commit to **B** (train in Godot) or design the kernel to own movement
  so both engines defer to it.

Until this is known, the safe, useful work is: prove the concept on Python (L2–L4) **and** freeze
the portable schema — both of which every path needs.

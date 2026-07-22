# Combat-AI Foundry — Design & Local Roadmap

**Status:** design locked, pre-implementation. Physics thread dropped.
**Branch:** `crux-foundry`. **Rule:** local-first; nothing touches Crux until it works on a laptop.

## The vision (kept large, on purpose)

Evolve, on CPU, combat agents that are **conditioned on metadata, not identity** — so any
procedurally-generated hostile is handled because the policy reasons over *features* (tags,
tier, HP, reach, effects), not a lookup of "wolf_grey". Two agents, eventually adversarial:

- a **hostile-pack agent** — shared, metadata-conditioned policy every pack member queries →
  emergent coordination (spacing, flank, focus-fire), scales to any pack size/composition;
- a **player-combat agent** — build-conditioned; becomes a sparring/difficulty/PvP bot.

Endgame is **competitive co-evolution** (arms race → emergent tactics). We get there in baby
steps, and we do **not** start there — two dumb populations against each other never bootstrap.
Order: single-agent vs fixed opponents → ramp difficulty → adversarial.

The compute is embarrassingly parallel evolution over the *real headless engine* (no GPU, no RL,
no gradients). Runtime artifact is a **tiny parameter file** evaluated with cheap arithmetic —
storable, realtime, no dependency in the shipped game.

---

## Design law (why tactics emerge, or don't)

> An agent can only learn a tactic that its **observation, action, AND fitness** all afford.

The pincer example makes this concrete. "Don't attack at max range and whiff; close to optimal
distance / flank with an ally" emerges **only if**:

| Requirement | Must expose / allow / reward |
|---|---|
| Observation | distance-to-target, target **facing & reach**, ally angles/positions, own cooldown |
| Action | move + face + **choose when to commit the swing** + pick target (not "attack nearest") |
| Fitness | **hits landed / swings thrown** (efficiency) + coordination — never raw swing count |

If any leg is missing, the tactic is unreachable no matter how much Crux time we spend. So the
obs/action/fitness contract below is the load-bearing artifact — get it right before scaling.

---

## The contract

### Observation (per-agent, all cheap floats, all already computable)

**Self / build metadata** — from `Character` (player) or `EnemyDefinition` (hostile):
- hp_frac, stamina/mana_frac (if applicable), own damage, own defense, own speed
- reach (weapon range / attack `range`), attack windup/recovery timing, cooldown_remaining
- offensive tags one-hot-ish (fire/ice/physical/...), tier, category

**Target** (the opponent, relative):
- distance, bearing (angle to target), target facing (are they facing me?), target hp_frac
- target reach, target windup phase (is it telegraphing? — `is_in_windup`, `windup_progress`)

**Allies** (pack coordination — the piece the FSM lacks):
- count, nearest-ally bearing/distance, is a teammate already engaging this target (focus-fire),
  angular spread of allies around the target (the pincer signal)

**Situation:**
- in a safe/aggro-gated region? number of live enemies; simple wall/LOS flags (later stages)

All of the above are derivable **today** from `enemy.position/definition/distance_to`,
`Character`, and an ally list we pass in. No content JSON, no new tags.

### Action (a small discrete/continuous set, mapped onto existing actuators)

Driven through primitives that already exist — we actuate, not rewrite:

| Action | Actuator (exists) |
|---|---|
| move toward (x,y) | `Enemy._move_towards(target, dt)` / harness move for player |
| face angle | set `facing_angle` |
| commit melee attack | `Enemy.start_phased_attack(target_pos, tags)` / `harness.melee_swing` |
| use ability | `Enemy.use_special_ability(...)` |
| pick target | select among available_targets |
| retreat / hold | move away / no-op |

Minimal v1 action head: **{move_dir (8-way or angle), commit_attack (bool), target_idx}**. That's
enough for spacing + focus-fire + flank. Dodge/ability come in later stages.

### Policy representation — start as a **parameterized heuristic, not a neural net**

Generation 0 is the hand-written policy; its knobs are the genome. Each action score is a
weighted sum of interpretable features (e.g. `commit_attack = w0·(dist<optimal_reach) +
w1·(target_in_windup) + w2·(ally_focusing_same_target) + ...`). Why start here:

- trivially CPU / realtime / storable (a vector of floats);
- **interpretable** — you can *read* what it learned ("it raised the weight on target-telegraph");
- immediately evolvable (mutate = perturb weights);
- the hand-written policy **is** the seed, so evolution starts from competent, not random.

Graduate to a tiny fixed-size MLP later **only if** the heuristic hits a ceiling. (A small MLP is
still gradient-free/CPU/realtime — just less readable.)

### Fitness — different in the two regimes (this resolves the "random gear" worry)

Randomized gear/spawns confound outcome with difficulty. Wood-vs-5-strong and iron-vs-3-weak
aren't comparable on raw HP-left. Resolution:

- **Single-agent regime — score a *policy*, not a *run*.** Evaluate every candidate on the **same
  fixed battery** of randomized (gear, mob, terrain) seeds (common random numbers), rank by
  **average**. Draw-luck is *held constant* across competitors, so it cancels; LLN turns "noisy
  setups" into a stable signal. Optional readability layer: a **par/handicap** term from the
  existing `difficulty_calculator` + tier multipliers, used as a **normalizer** (subtract expected),
  **never an additive bonus** — paying points for *drawing* a hard setup rewards luck, not skill.
- **Adversarial regime — the opponent *is* the normalizer → use a rating (Elo/TrueSkill).** Your
  "more points for beating a stronger opponent, tier modifiers" is *exactly* the Elo update. Fitness
  = rating; tiers seed the initial rating. Pair with a **Hall of Fame** (rate against archived past
  opponents, not just the current generation) — mandatory, or co-evolution cycles and forgets.

Base outcome terms (both regimes): hp_frac_remaining, enemies_down / survival, **hit efficiency**
(landed/thrown), time-to-resolve. Behavior terms (hit efficiency, coordination) are what push
toward *smart*, not just *winning*.

---

## Local baby-step roadmap (each step ships something runnable on a laptop)

**L0 — this doc.** Contract locked. ✅

**L1 — enemy control surface.** A `PolicyEnemy` that overrides `update_ai` (same move as
`TrainingDummy`) and actuates via `_move_towards` / `start_phased_attack`. Ship with a **hand-written
heuristic** policy (no learning). Harness verb to spawn a policy-driven pack. *Local test:* a pack
chases, spaces, and attacks coherently. **Proves the surface — the blocker for everything.**

**L2 — observation/action structs + a deliberately "smart" scripted policy.** Implement the obs
vector + action head; write a policy that demonstrates 1a (approach to optimal reach instead of
whiffing; simple 2-agent flank; focus-fire). *Local test:* hit-efficiency beats the stock FSM
baseline on the same scenario. **Validates the fitness signal before we optimize against it.**

**L3 — scenario generator + fitness harness.** Domain-randomize gear (reuse `apply_build`/personas)
+ mob composition; fixed seed battery; paired policy scoring. *Local test:* the L2 policy gets a
stable battery-average number; re-running is deterministic.

**L4 — tiny evolutionary trainer (local).** Population of *heuristic weight vectors* → evaluate over
a short battery → select → mutate → repeat. Small pop, few generations, on the laptop. *Local test:*
battery-average fitness **improves across generations**, seeded from the hand-written policy.
**The "it learns" milestone — entirely local.**

**L5+ (later, Crux):** scale pop/battery; add the **player** control surface + policy; **adversarial
co-evolution + Elo + Hall of Fame**; realism tail (aggro-gated control, dungeons, bounded world) so
training distribution == deployment distribution.

---

## What we reuse vs build

| Reuse (exists) | Build (new) |
|---|---|
| headless engine forward model, hermetic, determinism, seeded RNG | `PolicyEnemy` (override `update_ai`) — L1 |
| `_move_towards`, `start_phased_attack`, `use_special_ability` | obs encoder + action head — L2 |
| `EnemyDefinition` metadata, `Character` build | scenario/domain-randomizer + battery — L3 |
| harness (`melee_swing`, `equip`, `spawn`), `apply_build`/personas | evolutionary trainer (real EA) — L4 |
| Crux fan-out (`run_shard`, `crux_job.pbs`), StatStore capture | player policy surface, Elo, Hall of Fame — L5+ |

Note: the current `optimizer.py` is **grid-search only** — it is *not* the trainer. L4 is a new module.

## Non-negotiables (carried from the balance foundry)
- Deterministic (seeded, bit-reproducible), hermetic (no WES gen, no TF, no content pollution),
  isolated (process-per-run + private DB). No GPU, no RL, no gradients. Runtime = tiny param file.
- No content JSON / tag / formula changes. The policy **reads** metadata; it never edits the world.

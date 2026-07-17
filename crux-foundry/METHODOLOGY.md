# Crux Foundry — Methodology (Main Planning Run)

**Branch:** `crux-foundry`  **Scope:** offline, CPU-only, deterministic automated playtesting & relative-balance
tuning of Game-1's *hardcoded, non-AI* systems, using the real headless engine and the game's own history
mechanism as the capture layer.

This document traces every effect and outcome that follows from the locked design decisions. It is grounded in a
four-part code investigation (file:line evidence retained in the conversation record).

---

## 0. The one-sentence objective

> Find the *relative* balance parameters under which **every viable path/playstyle is roughly equally viable** —
> holding global difficulty/pacing fixed (the user hand-tunes those) — measured by simulating a large roster of
> playstyle personas on the real headless engine and capturing outcomes through the World Memory System.

"Balanced" here means **relative viability**, not difficulty. Two derived requirements fall out immediately and
govern the whole design:
- **(R1) A common yardstick.** Heterogeneous paths (a brawler vs a harvester) must be scored on one scale (§2.2).
- **(R2) Persona competence parity.** Each path must be *played equally well*, or we measure scripting skill, not
  balance (§2.5 — the central validity threat).

---

## 1. Locked design decisions

| # | Decision | Source |
|---|----------|--------|
| DC1 | **Real headless engine** (not a pure-logic model) — to run real systems and dogfood the history layer. | user |
| DC2 | **Balance = relative viability** ("everything viable"); global pacing/difficulty is hand-tuned and held fixed. | user |
| DC3 | **Many personas** — combat builds, crafters, specializations, generalist, hunter, harvester, … as many as feasible. | user |
| DC4 | **Combat-centric first**, expand to the full loop. | user |
| DC5 | **May modify code for determinism**, on this branch, under a strict ledger (`DETERMINISM_LEDGER.md`). | user |
| DC6 | **Disable everything AI** (LLM item gen, WNS/WES, NPC agents, faction, affinity, generated quests, classifiers). Gold/economy out. Crux cannot run AI. | user |
| DC7 | **Capture via the history mechanism** (WMS/StatStore/EventStore) — also validating it. | user |
| DC8 | **Only the large playtest jobs run on Crux**; analytical calculator sweeps run locally. | user |

---

## 2. What "balance" means here — formalized

### 2.1 Paths and personas
A **path** is a playstyle the game should support. A **persona** is a fixed, deterministic policy that plays that
path. Starter roster (each is a policy over the strategic decision layer — stat allocation, skill/weapon choice,
activity mix, risk tolerance, milestone targets):

- **Combat (v1 focus):** STR-brawler (2H melee), LCK-crit (glass cannon), VIT-tank, INT-caster (skills), AGI-speed
  (attack-speed/dual-wield), balanced-fighter.
- **Production / economy:** crafter-first (rush crafting tiers), harvester (gathering-optimized), hunter
  (kill-for-materials), toolsmith (tool progression).
- **Cross-cutting:** generalist (even spread), min-maxer/"exploit-hunter" (greedy toward the strongest option — used
  to *find* dominance, not as a balance target).

DC3 says maximize persona count; each added persona is one more path the optimizer must keep viable.

### 2.2 The common-yardstick problem (R1) — the hard part
There is **no win condition** (level 30 is the only engine terminal; death just respawns). So "viable" needs an
external, path-neutral yardstick. Two framings, used at different phases:

- **v1 (combat-centric): power-at-matched-investment.** Give every combat persona equal progression (same level /
  same playtime budget) and score **combat capability against a fixed, explicitly-spawned enemy gauntlet** —
  time-to-clear, survivability (HP lost), and clear-rate over seeds. This cleanly compares *combat* builds.
- **v2 (cross-domain): the standardized challenge gauntlet.** To compare a harvester against a brawler you need one
  currency. Proposal: define a **standard challenge** (e.g. "produce a tier-3 item AND clear gauntlet G, starting
  from the fixed temp-world spawn"), and score each persona by **effort/time to complete it**. Every path is then
  measured by the same external goal, regardless of how it gets there. This is the load-bearing design object of the
  cross-domain phase and must be authored deliberately (it *is* the definition of "viable").

> Consequence traced: the yardstick is not neutral — whatever challenge we pick *defines* which paths look viable.
> A combat-heavy gauntlet will make combat paths look strong. The gauntlet must therefore reward *all* the paths we
> want viable (some crafting, some combat, some gathering), or it silently biases the balance result. **This is a
> design decision the user must own, not the optimizer.**

### 2.3 Relative vs global knobs (the split that makes DC2 well-posed)
DC2 (hold global difficulty fixed, tune relative balance) maps directly onto the game's parameter surface:

- **Relative knobs (the optimizer tunes these):** per-stat effects (STR 0.05, DEF 0.02, VIT 15, LCK 0.02/0.03,
  AGI 0.03, INT); per-skill `magnitudeValues`; per-discipline crafting difficulty/reward modifiers; per-weapon-type
  damage multipliers; tier-multiplier *spacing* (T1-T4 relative); per-resource EXP; drop-chance map. These
  differentiate paths → they are what makes paths uneven.
- **Global knobs (held fixed; user hand-tunes):** EXP curve constants (200, 1.75), overall enemy HP/damage scale,
  base crit. These set difficulty/pace, not relative balance.

The optimizer searches **only the relative knobs**, with global knobs pinned. This is the precise mechanization of
"everything even, but I set the overall feel myself."

### 2.4 The objective function
"Even" is not enough — all-equally-*weak* is even but not viable. So the objective encodes **both** low spread and a
viability floor:

```
For parameter vector θ (relative knobs), personas P = {p_1..p_n}, seeds S:
  V(p_i, θ) = mean over S of yardstick_score(p_i, θ)          # §2.2
  L(θ) = spread({V(p_i,θ)})            # e.g. max-min gap or coefficient of variation
        + Σ_i floor_penalty(V(p_i,θ))  # penalize any path below the viability threshold
minimize L(θ) over relative knobs, global knobs fixed.
```

Output: θ* where all paths clear the floor and the spread is minimized, plus a **per-persona viability report** and
**per-knob sensitivity** (which number most affects which path).

### 2.5 The central validity threat — persona-competence confound (R2)
If persona A is scripted *better* than persona B, the tester concludes A's *path* is stronger when really A's
*policy* is stronger. For a relative-balance-via-personas method this is **the** correctness risk, and it's exactly
what the prior-art literature (procedural personas; human-like MCTS) exists to address. Mitigations, in order of
strength:

1. **Play each path near its own optimum.** For "is every path viable" we want each path played *well* (its ceiling),
   so a weak path isn't masked by good play nor a strong path by bad. This argues for **light per-path search**
   (MCTS/greedy rollout over that path's decision subset) rather than brittle hand-scripting — a real design
   implication of DC2 (it nudges personas from pure scripts toward path-constrained search).
2. **Calibrate against a known-balanced reference.** Construct a trivially-symmetric scenario where paths *should*
   score equally; require the persona harness to reproduce that equality before trusting any real result.
3. **Human-in-the-loop ("verify by playing").** Periodically render/inspect actual persona runs — a scalar can lie;
   a persona flailing is obvious on screen.
4. **Report competence proxies** (idle time, wasted actions, deaths from avoidable causes) alongside viability, so a
   low score can be attributed to *path weakness* vs *policy weakness*.

This threat is why DC1 (real engine, watchable) matters beyond fidelity: it keeps the human check possible.

---

## 3. Architecture — four layers over one contract

```
 ┌─ Optimizer (local; active-learning / Bayesian opt over RELATIVE knobs) ─┐
 │        proposes θ                              consumes L(θ)            │
 ▼                                                                         ▲
 Persona layer  ──drives──►  Real headless engine  ──emits──►  Capture (WMS/StatStore)
 (policies / path-search)     (SDL dummy, seeded)              per-run SQLite → export → reduce
```

### 3.1 Forward substrate — the real headless engine (DC1)
- Boot exactly as `tests/integration/conftest.py` does: `SDL_VIDEODRIVER=dummy`, no API key, `WES_*` unset →
  Mock/fixtures; enter temp world (`handle_start_menu_selection(3)`, seed 13579), auto-pick class.
- Step via the frame loop with controlled `dt` (`harness.tick`). `update()` is cleanly separable from `render()`
  (`game_engine.py:8329` vs `:8544`); render is simply never called.
- **Cost/consequence:** full-engine ticks are Python-heavy and each event triggers WMS SQLite writes + geographic
  enrichment + tagging. This bounds runs/node-hour and is *why* only the large jobs go to Crux (DC8). Mitigation
  lever: run WMS **Layer-1 factual capture only** (leave `WmsAI`/Layers 2-7 narrative uninitialized → templates, no
  LLM, less write cost) for mass sweeps, and run **full WMS** on a smaller validation subset to dogfood the whole
  pipeline (still satisfies DC7).

### 3.2 Persona/agent layer (DC3)
- Each persona = a policy exposing `choose_action(state) -> Action` over the strategic decision layer; real-time
  combat/minigames are executed as macro-actions (attack-until-dead, craft-at-quality) since the damage pipeline is
  closed-form and minigames are deterministic.
- Per §2.5, personas range from scripted (cheap, for coverage) to path-constrained search (for competence parity on
  the paths whose viability verdict must be trustworthy).
- **Bootstrap consequence (traced):** the temp-world start is bare-handed, empty inventory, T1 tools. A "pure combat"
  persona therefore can't fight until it has a weapon. For **combat-first isolation**, inject a tier-appropriate
  weapon + fixed loadout via `harness.give` and spawn an explicit enemy gauntlet — this removes the crafting
  dependency and RNG spawn noise from the combat measurement. The craft/equip bootstrap is *reintroduced* only when
  testing the full economic loop (v2), where the gate itself is under test.

### 3.3 Capture layer — the history mechanism (DC7)
- **Primary metrics cube:** `StatTracker → StatStore` (SQLite, ~65 `record_*` methods) — combat, crafting, gathering,
  progression, skills, exploration. **Timeline:** `EventStore` (queryable per-event log). **Rollups:** daily ledger.
- The recording path **never calls an LLM** (verified) — it populates fully offline. Reusing it exercises the
  record→evaluator→trigger pipeline, so the balance runs *also* stress-test the WMS (a real secondary payoff of DC7).
- **Additions required (don't exist today):** (a) a **run manifest** row — `{run_id, seed, persona, θ, git_sha}`;
  (b) an explicit **run-outcome event** — `reached_milestone | died_out | timeout | stuck | crash`. Emit both as
  bus events so they land in the same store.
- **Guardrail (traced from a real hazard):** the event bus **swallows handler exceptions** (`event_bus.py:152`). A
  silently-failing recorder loses data without failing the run. Every run must assert
  `EventRecorder.stats["events_recorded"] > 0` and `bus.stats["handler_errors"] == 0`.

### 3.4 Optimizer layer (local)
- Classical, CPU, non-RL: active learning / Bayesian optimization / CMA-ES over the relative-knob vector, minimizing
  `L(θ)` (§2.4). Each evaluation of `L(θ)` = a persona×seed batch (a Crux job array); the optimizer runs locally and
  dispatches evaluation batches to Crux. This is the only genuinely "supercomputer-scale" component (evaluations ×
  personas × seeds).

---

## 4. Determinism plan (DC5) — see `DETERMINISM_LEDGER.md` for the authoritative list

Disabling AI is necessary but **not** what makes runs reproducible. The real blockers are unseeded global `random`
in combat and scattered wall-clock. Planned, behavior-preserving changes (D1–D7 in the ledger):
- **D1/D2/D3:** inject one seeded `random.Random` through combat crit / enemy tier-count-position / loot / enemy
  damage, seeded from the world seed at new-game. Default path reproduces today's behavior when no seed is supplied.
- **D4/D5:** replace `time.time()` in the WMS position sampler and death-chest ids with `game_time`/counters (behind
  a headless flag).
- **D6/D7:** additive harness verbs (`attack/gather/use_skill/allocate_stat`) + a single `seed_all(seed)` switch.

Governance: every change is one ledger entry, additive-by-default, verified against the full + integration suites
before "VERIFIED". Nothing that alters normal play ships without explicit sign-off.

---

## 5. Disable plan (DC6) — and what therefore goes untested

**Config (already the integration-test posture):** no `ANTHROPIC_API_KEY`, no Ollama, `WES_*` unset → Mock/fixtures;
optionally `claude.enabled=false` in a test `backend-config.json`; never trigger the *invent* action; only canonical
quests (or drive the quest engine directly); leave `WmsAI` uninitialized (templates) for mass runs.

**Verified safe to disable (zero balance coverage lost):**
- **Faction, Affinity** — purely observational; no combat/economy/progression/loot/crafting reads them.
- **NPC dialogue / NPC agents** — provide only dialogue + quest give/turn-in (no shops/vendors/stations).
- **LLM item generator + crafting classifiers** — only on the player *invent* action; normal crafting untouched.
- **WNS/WES, generated quests + LLM reward adaptation** — optional, non-load-bearing.

**Consequently NOT tested (accepted):** faction/affinity dynamics, NPC/LLM dialogue, generated-quest reward
adaptation, invented items, CNN/LightGBM validation. The **quest *reward* economy** (XP/items/skills/titles/stat-points
grants) *is* balance-relevant and is **kept in** by driving the quest engine directly
(`character.quests.start_quest/complete_quest`) with canonical quest defs — no NPC/AI needed.

**Boundary (traced):** results are valid for the **deterministic hardcoded game**. When AI-generated content is later
enabled (invented items), it is *out of scope here* — that path is covered by a separate **empirical BalanceValidator**
(equip generated item → measure power-delta vs tier band), which reuses this same harness but is not part of the
relative-balance optimizer.

**One residual thread to guard:** a CNN "warmup" thread fires on crafting-UI open (`game_engine.py:4539`). Confirm the
programmatic `harness.craft` path does not open that UI; if it does, gate the warmup behind a headless flag (log as a
new ledger entry).

---

## 6. The combat-first vertical slice (DC4) — concrete v1

1. **Scenario:** temp world, seed S. Each combat persona is handed a fixed, tier-appropriate loadout via
   `harness.give`; a **fixed enemy gauntlet** is spawned explicitly (not via random spawns) at matched difficulty.
2. **Play:** persona fights the gauntlet using macro-actions (attack/skill), allocating stats per its policy at each
   level; capture through WMS/StatStore.
3. **Yardstick (§2.2 v1):** time-to-clear, HP lost, clear-rate over S seeds → `V(persona, θ)`.
4. **Optimize:** tune relative combat knobs (per-stat effects, skill magnitudes, weapon-type multipliers, tier
   spacing) to minimize spread + clear the floor across combat personas.
5. **Human check:** render a sample of runs per candidate θ (§2.5).

This slice needs only D1–D3, D6–D7 (combat determinism + verbs), not the crafting/economy machinery — the fastest
path to a real, trustworthy result, and the highest-transfer end-state backend.

---

## 7. Crux operations & scale (DC8)

- **What runs where:** analytical calculator sweeps (recipe/skill economy) and single-persona debugging → **local**.
  The persona×seed×θ evaluation batches and the optimizer's outer loop → **Crux job arrays**.
- **Isolation (mandatory, traced from the singleton finding):** all WMS/StatStore/EventStore/bus objects are
  process-global singletons keyed to one save path. Use **one process per shard**; within a shard run K sequential
  runs, each with a fresh per-run DB dir and a full singleton + RNG reset between runs
  (`GameEventBus.reset`, `StatStore.reset`, `WorldMemorySystem.reset`, `EventRecorder.reset`, re-`seed_all`). Never
  many concurrent writers to one SQLite file.
- **Job-array shape:** `#PBS -J 0-N`, each element owns a disjoint (seed × θ-block) chunk; `module load cray-python`;
  no `qsub -v/-V`; allocation on a bare `#PBS -A` line; atomic temp-then-rename per work-item; skip-if-exists for
  resume; per-shard `index.jsonl` summaries; a single-process reduce pass builds the report; count with `find|wc -l`.
- **Scale reality (honest):** a single combat-gauntlet run is cheap; the cost is `θ-evaluations × personas × seeds`.
  Baseline measurement (fixed θ, ~10³–10⁴ runs) is *local-feasible*. The **optimizer outer loop** (each iteration =
  a full persona×seed batch, over hundreds–thousands of θ candidates) is the genuine Crux workload. Per-run cost via
  the real engine is the dominant variable — profile it first; it decides how much of this actually needs Crux.

---

## 8. Effect/outcome trace — choice → consequence → cost → untested

| Decision | Consequence | Cost / risk | What it leaves untested |
|----------|-------------|-------------|-------------------------|
| DC1 real engine | Real behavior + dogfoods WMS | Heavy per-run; pygame-init + SQLite writes; singleton isolation | — |
| DC2 relative viability | Objective = spread+floor over personas; relative/global knob split | Needs a common yardstick (§2.2); results only as valid as persona competence (§2.5) | Absolute difficulty/pacing (by design — user-owned) |
| DC3 many personas | More paths kept viable; better coverage | Combinatorial scale; each persona must be competence-parity | Paths with no persona authored |
| DC4 combat-first | Fast, high-transfer v1; inject loadout + fixed gauntlet | Combat isolated from economy initially | Crafting/gather economy until v2 |
| DC5 determinism edits | Reproducible runs; resumable Crux jobs | Touches combat_manager/enemy/WMS — regression risk | — (mitigated: additive + ledger + tests) |
| DC6 disable AI | Deterministic, offline, no external calls | Must guard invent path + CNN warmup + canonical-only quests | faction/affinity/NPC/LLM-quests/invented-items/classifiers |
| DC7 WMS capture | Rich free metrics + stress-tests WMS | Write overhead; singletons; bus swallows errors (assert!) | fine movement (chunk-granular only) |
| DC8 Crux for big jobs | Optimizer scales; analytical stays local | Per-run cost gates budget; isolation via process-per-shard | — |

---

## 9. Open risks & human-in-the-loop

- **Yardstick bias (§2.2):** the chosen challenge *defines* viability; must reward every path we want viable. **User-owned.**
- **Persona competence (§2.5):** the correctness linchpin; mitigate with path-search + calibration + watched runs.
- **Per-run cost:** unknown until profiled on the real engine; determines the local↔Crux boundary.
- **"Even vs viable":** objective enforces both (floor + spread); confirm the floor definition with the user.
- **Determinism completeness:** after D1–D5, prove two `seed_all(S)` runs yield identical StatStore dumps before trusting any sweep.

## 10. Build sequence

- **P0 — Determinism & harness (branch, ledger):** D1–D7; prove reproducibility (identical dumps).
- **P1 — Capture wrapper:** per-run DB isolation, run manifest + outcome event, assertions, export→reduce.
- **P2 — Combat vertical slice (§6):** combat personas + fixed gauntlet + v1 yardstick, run **locally**.
- **P3 — Optimizer:** relative-knob search minimizing `L(θ)`; validate on the calibration scenario (§2.5).
- **P4 — Crux scale-out:** job-array the persona×seed×θ batches; resumable/atomic; reduce → viability report.
- **P5 — Expand paths (v2):** standardized challenge gauntlet; add production/economy personas; full-loop bootstrap.

---

## 11. Round-2 decisions (locked by user)

- **Yardstick = leveling-based progression score** → full spec in `SCORING.md`. The "beat the game" currency is
  *progression*, measured as **time-to-threshold**, not raw cumulative score.
- **Viability floor:** reach **level 10** or **2000 progression points** within time budget **T**; `T` calibrated by
  baseline trials (§SCORING calibration plan). Supersedes the abstract floor in §2.4.
- **Compute is not a constraint** — enables search-based (path-optimal) personas for competence parity (§2.5) and
  large persona×seed×θ sweeps. Removes the local/Crux boundary worry in §7; still resumable/atomic for safety.
- **Fork 4 confirmed:** combat-first uses an injected fixed loadout + explicitly-spawned enemy gauntlet (§6).
- **Scoring guardrails (new, from research):** the score is an optimization target → gaming-resistant by design.
  Dropped `+3 per WMS note` (event-volume proxy → Goodhart). WMS/daily-ledger are **observability**, not score
  inputs. Score paired with opposing indicators (deaths, efficiency, gear-power) as the multi-objective defense.
- **Open (defer to trials):** universal score (v1) vs per-persona utility (v2) — start v1; switch only if trials
  prove a legitimate path is structurally un-scorable on the universal currency.

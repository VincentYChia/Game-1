# Crux Foundry — Balance Findings

Findings the automated playtester surfaces. Each is stamped with the git sha of the
code it was observed against and its confidence. **Single-seed observations are
provisional** — combat has high-variance RNG (crit), so a finding is only
"confirmed" once it holds across many seeds (that's what the multi-seed
relative-viability report is for).

---

## F1 — Gauntlet difficulty calibration (tier 2 / size 8 differentiates builds)
**Status:** methodology result (not a game issue) · observed @ `ac8b2454`

A single-swing melee gauntlet only differentiates builds in a narrow difficulty band:
- tier 1 / size 3 → every mid-game build trivially clears (no signal).
- **tier 2 / size 8 → builds rank distinctly** (chosen default).
- tier 3+ / size 8 → everything wipes (no signal, though the tank dies *fewest* times).

Calibration sweep (seed 1, level-10 builds, iron_shortsword):

| tier·size | str_brawler | vit_tank | lck_crit |
|---|---|---|---|
| 2·8 | 7/8, 2 deaths, 179 dmg | 7/8, 2 deaths, 326 dmg | 6/8, 4 deaths, 292 dmg |
| 3·8 | wiped, 54 deaths | wiped, **26** deaths | wiped, 58 deaths |
| 4·8 | 2/8, 74 deaths | wiped, 44 deaths | 1/8, 84 deaths |

Note "deaths" = respawn count (death is a setback, not a run-ender), so it is a
graded viability signal even in a loss (the tank consistently dies fewest).

---

## F2 — pure-LCK build is non-competitive; STR/VIT/balanced are well-balanced (CONFIRMED, 5 seeds)
**Status:** CONFIRMED (multi-seed) · observed @ `a0732bc5`

Relative-viability report — level-10 builds, all 9 points in one stat, tier-2/size-8
gauntlet, **mean over 5 seeds** (viability = mean(kills)/8 − 0.05·mean(deaths)):

| build | kills | deaths | dmg_taken | clear% | viability |
|---|---|---|---|---|---|
| str_brawler | 7.20 | 2.00 | 170.4 | 20% | **0.800** |
| vit_tank | 7.00 | 2.00 | 315.3 | 0% | 0.775 |
| balanced | 7.20 | 2.80 | 274.1 | 60% | 0.760 |
| lck_crit | 5.80 | 4.40 | 318.3 | 0% | **0.505** |

**Verdict:** STR / VIT / balanced cluster within ~5% (well-balanced with each other);
`lck_crit` is the sole outlier ~35% below. So the imbalance is specific: **pure-LCK is
non-competitive** — +2%/pt crit (≈+18% *conditional* damage) is a weaker combat
investment than STR's +5%/pt flat damage or VIT's +15 HP/pt survivability.
**Recommendation:** raise LCK's crit value (or add a small base crit — see F3) so
luck builds are viable. Single-seed provisionality is now resolved by the 5-seed mean.

Interpretation note: +2%/pt crit (≈+18% *conditional* damage) is a weaker combat
investment than STR's +5%/pt flat damage or VIT's +15 HP/pt survivability.

**Corrected mid-investigation:** an earlier single-seed run made `lck_crit` look
*identical* to a no-crit build (LCK "dead"). Code check refuted the "dead" reading —
LCK **is** wired to crit: `base_crit_chance = 0.02 * effective_luck`
(`combat_manager.py:958-959`). The identical result was just crit not firing in a
short fight (18% × few hits). Lesson: never conclude a balance finding from one seed;
crit variance demands multi-seed averaging.

---

## F3 — Two divergent crit implementations (code inconsistency, to verify)
**Status:** note · observed @ `ac8b2454`

`combat_manager.py` has two crit computations:
- `:747` `crit_chance = 0.10` (hardcoded, no LCK) — a secondary/legacy attack path.
- `:958-959` `base_crit_chance = 0.02 * effective_luck` (LCK-scaled) — the action-combat
  path the player actually uses.

Note there is **no base crit** in the LCK path (luck 0 → 0% crit), whereas the legacy
path gives a flat 10%. Worth reconciling: a 0-LCK character crits 10% via one path and
0% via the other depending on which attack code runs. Not blocking the playtester, but
a real balance/consistency question for the game.

---

## F4 — LCK is a DEAD stat on the action-combat path (ROOT CAUSE of F2) — CONFIRMED
**Status:** CONFIRMED (code + knob test + optimizer) · observed @ `f9158c4e`+

Real melee runs `player_attack_enemy_with_tags` (reached via the hitbox resolver
`_ac_process_hit`). Reading it (`combat_manager.py:1580-1607`): it applies the STR
multiplier (`strength * 0.05`, :1590) and title/skill bonuses, then executes the tag
effect system — but has **NO crit computation at all** (no luck, no ×2). The
luck→crit wiring (`base_crit_chance = 0.02 * effective_luck`) exists ONLY in the
legacy `player_attack_enemy` (:965), which action combat never calls.

**Proof:** a tunable `CRUX_LCK_CRIT_PER_POINT` injected at the legacy site and swept
0.02→0.10 produced **bit-identical** persona results — the personas never execute that
code. And `optimizer.py` finds `lck_crit` is the viability FLOOR at every STR-knob value.

**Impact:** a player investing in LCK for crit gets **zero** combat benefit in real
(action) melee — this is the root cause of F2 (pure-LCK non-competitive).
**Fix (dev CODE, not a tune):** apply luck-based crit in `player_attack_enemy_with_tags`
(and/or the effect executor), reconciling F3's two crit paths. *Then* the optimizer
could tune the crit value to make luck builds viable.

**Optimizer corollary (the key lesson):** this is the archetypal problem the optimizer
**cannot** fix — a value can't be auto-tuned if the code never reads it. The tester's
job was to FIND it; the fix is a code change. Auto-tuning tunes PARAMETERS, not WIRING.

### F4 — FIXED ✅ (the measure -> fix -> verify loop, closed)
Wired luck-based crit into `player_attack_enemy_with_tags` (mirrors the legacy path;
`crit_chance = _LCK_CRIT_PER_POINT * effective_luck + title bonus`, applied last on the
fully-bonused damage; threaded to the return, StatStore `was_crit`, and DAMAGE_DEALT).
This is an intentional GAME BEHAVIOR change (adds the missing crit), not a
determinism-preserving injection — luck now matters in real combat.

**Verified (single build, seed 1, default 0.02 crit/pt):** `lck_crit` went from
`6 kills / 4 deaths / partial` (dead LCK) to **`8 kills / 2 deaths / cleared`** — just
fixing the wiring (9 luck now = 18% crit instead of 0%) made it competitive. It also
now *responds* to the knob (dmg 886 -> 1078 as crit/pt 0.02 -> 0.10). Guarded by `tests/integration/test_11_crux_foundry.py`; full game suite green (1143 passed).

**Aggregate (8-seed viability report):** the wiring fix lifted `lck_crit` from **0.505**
(pre-fix, weakest) to **0.566** and cut the spread **0.295 → 0.209**. It stays weakest at
the DEFAULT 0.02 crit (crit is *undertuned*), but `optimizer.py` shows tuning
`CRUX_LCK_CRIT_PER_POINT` up to ~0.10–0.14 lifts lck_crit to ~0.900 and cuts the spread a
further 32%. So the **FIX makes luck matter; the OPTIMIZER prescribes the value** the game
devs would set — the full find → fix → tune → verify loop, run entirely locally.

---

## F5–F9 — Action-path conformance cluster (siblings of F4) — FIXED ✅
**Status:** FIXED @ `234990c4` · verified by `tests/integration/test_12_combat_conformance.py`

Firsthand re-audit of the F4 site surfaced that the action path (the ONLY melee path
players hit) was missing MORE documented pipeline components than crit:

- **F5 (major):** enemy DEFENSE was never applied — players did full damage to armored
  enemies. Now applied per-target in the effect executor (`_apply_enemy_defense`),
  honoring armor penetration, capped at 75%. Skill-path damage intentionally still
  bypasses enemy defense (open design question — see report).
- **F6:** crit composition lacked pierce-buff and weapon-tag components; three divergent
  implementations unified into `CombatManager._player_crit_chance` (closes F3).
- **F7:** hand-requirement damage bonus (×1.1–1.2) was absent on the action path.
- **F8:** the legacy AoE sub-path used `STR × 0.01` (docs: 0.05) and a flat LCK-ignoring
  10% crit; both now use the shared constants/helper.
- **F9:** enemy-type title bonuses (`get_enemy_damage_multiplier`) never applied.

**Balance impact (8-seed report, post-fix):** spread HELD at 0.209 — relative balance
preserved; absolute difficulty up slightly (enemy DEF now real). No rebalance emergency.
lck_crit remains the undertuned floor (0.566); prescription unchanged (~0.10–0.14/pt).

---

## F10 — Synchronous LLM calls on the game loop (WMS) — L2 FIXED ✅, L3–L7 mitigated
**Status:** L2 FIXED · observed via firsthand audit of `interpreter.py` / `world_memory_system.py`

Every L2 trigger ran `WmsAI.generate_narration` SYNCHRONOUSLY inside the gameplay event
path (bus publish → trigger → interpreter) — instant with fixtures, but a 300–1500ms
frame stall per trigger with the real Claude backend, and triggers fire *during combat*.
This was the same class of playtest-killer as the 30s NPC-dialogue freeze fixed in June.

**Fix:** the template narrative is recorded immediately; a worker thread runs the LLM
call (bounded at 4 in flight, graceful skip beyond); the result patches EventStore +
LayerStore rows on the main thread via `drain_narrative_upgrades()` in
`WorldMemorySystem.update()`. Workers never touch SQLite (LayerStore is not
thread-safe). Verified by `world_system/tests/test_async_narrative_upgrade.py` (10 tests).

**Residual:** L3–L7 consolidation/summarization still run their LLM calls synchronously
in `update()` — rare (cadence-gated) but each can stall ~1s+ with a real backend. Now
LOGGED when >250ms so playtest hitching is attributable. Full async needs a thread-safe
LayerStore first — recommended follow-up, not a pre-playtest blocker.

---

## F11 — Retention prune was N+1 (up to 5,000 unindexed LIKE scans) — FIXED ✅
**Status:** FIXED · `retention.py` Rule 5

Each prune pass called `is_referenced_by_interpretation(event_id)` — an unindexed
`LIKE '%id%'` full scan of the interpretations table — once per candidate event
(limit 5,000), on the game loop. Replaced with ONE batched pass
(`EventStore.get_all_referenced_event_ids()`), identical semantics (parses the same
`cause_event_ids_json` chains), set-membership per event.

---

## F12 — Test runs leaked WES-generated content into the live content tree — FIXED ✅
**Status:** FIXED · `generated_file_writer.py` + `tests/integration/conftest.py`

In-engine test/soak runs drove real WES ContentRegistry commits, which wrote
`skills-generated-*.JSON`, `hostiles-generated-*.JSON`, and
`items-materials-generated-*.JSON` siblings into `Skills/`, `Definitions.JSON/`, and
`items.JSON/`. Every subsequent boot (game OR test) then auto-loaded them as real
content — the test world was silently playing with machine-generated skills.

**Fix:** `GAME1_GENERATED_CONTENT_ROOT` env redirect honored first by the writer's root
resolver; the integration conftest sets it to a temp dir; `GAME1_HERMETIC=1` now also
forces a temp root as a writer-side backstop (the runner-side gate had been bypassed).
The 12 leaked artifact files (all stamped `"generated": true` with plan ids) deleted.

**Lesson:** the sacred-tree guarantee needs enforcement at the WRITER, not just at
dispatch — any future caller that reaches commit gets the same protection.

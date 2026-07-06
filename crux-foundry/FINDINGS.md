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
now *responds* to the knob (dmg 886 -> 1078 as crit/pt 0.02 -> 0.10). Guarded by
`tests/integration/test_11_crux_foundry.py`. Game combat suites green (43 passed).
Aggregate (viability report, post-fix): see below / commit message.

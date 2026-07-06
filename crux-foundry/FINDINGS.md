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

## F2 — LCK (crit) underperforms STR/VIT at equal investment (PROVISIONAL, single-seed)
**Status:** provisional — needs multi-seed confirmation · observed @ `ac8b2454`

At level 10 with all 9 points in one stat vs the tier-2/size-8 gauntlet (seed 1),
`lck_crit` ranks last (6 kills / 4 deaths) behind `str_brawler` and `vit_tank`
(7 kills / 2 deaths). Interpretation: +2%/pt crit (≈+18% *conditional* damage) is a
weaker combat investment than STR's +5%/pt flat damage or VIT's +15 HP/pt survivability.

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

<!-- RECONCILIATION PUNCH-LIST (NOT the 11-section impl format). Alchemy — "The Stability Bench" is ALREADY BUILT
     (marble + live-reaction chemistry; Potency/Volatility axes). This doc records where the shipped build MATCHES
     the marked stability model (master plan §3.2) and where it DRIFTS, gives an ordered fix list, and audits the
     tag interpretations against master plan §2 so Alchemy can serve as the consistency reference for the other four
     minigames. Every verdict cites the code line it was read from; where the code and §2 disagree, the row says so
     rather than papering over it. Source of truth = CRAFTING_MINIGAMES_MASTER_PLAN.md §0/§1/§2/§3.2. -->

# Alchemy — "The Stability Bench" · Reconciliation Punch-List

**Status.** SHIPPED (2026-08-16 rebuild — `scripts/minigames/AlchemyMinigame.cs` + `scripts/minigames/MinigameTagEffects.cs`).
This is the **candidate reference implementation** of the tag-driven spine (master plan §1). This doc is a punch-list,
not a from-scratch impl doc: it (a) tables MATCH vs DRIFT against the marked stability model, (b) gives an ordered fix
list, and (c) audits §2 tag-theme consistency — including the handful of tags where the shipped code does NOT yet match
§2 (see §C.2). The mechanic is not rebuilt — only reconciled; §B lists the concrete fixes that close the drifts.

> **Line-citation caveat (read before applying §B).** Every `L###` in this doc is verified against the *current* file.
> Applying **B-D1** and **B-D3** INSERTS lines into `Evolve`, which shifts every subsequent citation in
> `MinigameTagEffects.cs`. Do not trust an absolute line number after you have edited the file — anchor on the named
> method/variable (e.g. "the single `vol +=` ease line", "the `pot` ease line", "the `heat = Math.Clamp(...)` after the
> six `Shift` calls"), which §B always names alongside the number. **Apply the fixes in the order §B lists them and
> re-locate by anchor, not by number.**

**Files in scope.**
- `scripts/minigames/AlchemyMinigame.cs` — the overlay (marbles, merge, cast ceremony, draw, F1/F7 glue).
- `scripts/minigames/MinigameTagEffects.cs` — the chemistry: `Brew`, `Evolve`, `ComposeVolatility`, `BuildProfile`,
  `TargetVolatility`, `PotencyResistance`, `BasePotency`, `Quality`, the `ModTable`/`ChExc`/`StExc`/`StrongExc`/`PvExc`
  banks, and the `Tags`/`Metal`/`Wood` channel vocabulary.
- Shared engine `scripts/minigames/MinigameModifierCommon.cs` (`StackFactor`/`ModProfile`/`Fold`/`Clamp`).
- Toolkit: `scripts/CraftFx.cs`, `scripts/minigames/CraftColor.cs`, `scripts/minigames/StateVisual.cs`,
  `scripts/minigames/MinigameDevLog.cs`. Seam: `scripts/minigames/MinigameOverlay.cs`. Data: `RecipeContext.cs`.

**The marked stability model (master plan §3.2), restated as six invariants this build must satisfy:**

| # | Invariant (from §3.2) | Where it lives in code |
|---|-----------------------|------------------------|
| **I1** | **Bell-curve scoring**: quality = closeness-to-target-VOLATILITY with a distance falloff; **edge = faster = harder**. | `MinigameTagEffects.Quality` (Gaussian in `vol`) + `Evolve` ease-rate. |
| **I2** | **Heat = tick-speed + low-stability-biased window**, and heat **never touches banked volatility directly**. | `Evolve` heat block + `Shift` transmutations + the `vEq`/`vol` easing. |
| **I3** | **Per-ingredient (base ±, ×mult)** resolved through the tag pool with **precedence 4/3/2/1**. | `Brew` (rank weights) + `BuildProfile` (`ModProfile.Vol` base ±, `ModProfile.Pot`/state `StatePot` ×mult). |
| **I4** | **Target from OUTPUT tags** (+ tier nudge). | `TargetVolatility(goalTags, tier)` fed from `Recipe.OutputTags`. |
| **I5** | **Numeric UI = Potency + Volatility ONLY** (the scored axes); everything else read off the marble. | `DrawSliders`/`DrawGauge` (bars, no digits) + `DrawStateLabels` (named, no numbers). |
| **I6** | **Tag themes obey §2** (fire=haste/aggression/volatility; ice=control/stability; …) — the consistency backbone. | `Tags` channel map + `ModTable`/exception banks + `TagVolatility`. |

---

## A. MATCH / DRIFT table

Legend: **MATCH** = ships correctly per the marked model. **DRIFT** = deviates; a fix is listed in §B by the same ID.
**PARTIAL** = mostly correct but one sub-aspect drifts. Every row cites file + method/line so the coder verifies in place.
Line numbers are current-as-of-audit; after applying B-D1/B-D3 they shift inside `Evolve` (see the caveat at the top) —
re-locate by the named method/variable. §2-consistency is NOT a blanket pass: the tag rows here spot-check, and §C.2
records five real deviations (toxic verb, elemental scope, solvent base, Function/Output targeting, and the
lightning/chaos body-vs-rider classification).

### A.1 — I1 Bell-curve scoring (edge = faster = harder)

| ID | Aspect | Verdict | Evidence | Notes |
|----|--------|---------|----------|-------|
| **M1** | Quality is a Gaussian bell on `(vol - vTarget)` | **MATCH** | `MinigameTagEffects.Quality` L397-401: `z=(vol-vTarget)/18.0; baseScore=exp(-0.5*z*z)`. | σ = **18** volatility units, hard-coded. This IS the bell. |
| **M2** | Potency is a *multiplier* on the bell, not an additive axis | **MATCH** | `Quality` L399-401: `pEff = pot/(1+resistance*2.0)` (L399, the resistance stage), then `potMult=clamp(0.55+0.6*(pEff/60),0.55,1.4)` (L400); returns `baseScore*potMult`. | Matches "base × multiplier" from §3.2. Note the multiplier is on the **resisted** potency `pEff`, not raw `pot` — so tier-scaled `resistance` (M11) flattens the potency reward, which is the intended "higher tier resists raw potency" coupling. Cross-read `PotencyResistance` when tuning. |
| **D1** | **"edge = faster = harder"** — closer to the target edge, the needle must move *faster* (harder to hold) | **DRIFT** | `Evolve` L354 eases `vol` toward `vEq` at a **constant** rate `2.4*dt` regardless of distance-to-target. Nothing accelerates `vol` motion near the target band. | The bell's *shape* is right (M1) but the *dynamic* ("edge=faster") is **absent**. The mixture eases to an equilibrium; it doesn't get twitchier as you approach the edge of the target band. THE key marked feel is unshipped. See B-D1. |
| **D2** | Volatility *distance* itself is not surfaced as increasing needle speed | **DRIFT** | `DrawGauge` L552-555 draws the fill at `vol/100` with a lerp-smoothed surface line; motion speed is purely the sim's ease rate, uncoupled from proximity-to-target. | Consequence of D1 — the gauge cannot *show* "edge=faster" because the sim doesn't produce it. |

### A.2 — I2 Heat = tick-speed + low-stability window, not touching banked volatility

| ID | Aspect | Verdict | Evidence | Notes |
|----|--------|---------|----------|-------|
| **M3** | Heat is driven by fire, damped by water+earth, fanned by Blaze | **MATCH** | `Evolve` L337-338: `heatTarget=clamp(fire*150/(1+water*3.5+earth*1.6)*(1+Blaze*0.6),0,HEAT_MAX)`. | Fire→hot, water/earth→calm — §2-consistent. |
| **M4** | Heat biases toward *low stability* (raises the volatility equilibrium) via the `heat` term in `ComposeVolatility` | **MATCH** | `ComposeVolatility` L269: `vc*62 + heat/HOT*34`. Heat contributes up to +34 to `vEq`. | This is the "low-stability-biased window": more heat → higher target-V equilibrium → harder to sit in a calm band. |
| **D3** | **Heat as a TICK-SPEED modifier** — heat should speed the *reaction clock* (the rate states fire / V moves), per §3.2 "heat == tick-speed" | **PARTIAL/DRIFT** | Vigor `rx` (from `ModProfile.Rx`, tags/tier) scales transmutation + heat-build rates (`Evolve` L338/341-346), but **live `heat` itself does not scale the tick**. Fire tags raise `Rx` at build time; the *accumulated heat during a reaction* does not feed back into tick speed. | §3.2 explicitly couples heat to tick-speed. Today tick-speed is a *build-time* property (`rx`), not a *live* function of the current `heat`. The marked model wants hotter = faster-ticking *now*. See B-D3. |
| **M5** | Heat never directly writes banked volatility | **MATCH** | Grep `Evolve`: `vol` is only written at L354 (`vol += (clamp(vEq)-vol)*2.4*dt`) and clamped L361. Heat enters ONLY through `vEq` (the equilibrium), never as a direct `vol +=`. | Invariant I2's "not touching banked volatility" is **honoured**. Keep this. |

### A.3 — I3 Per-ingredient (base ±, ×mult) via tag pool + precedence 4/3/2/1

| ID | Aspect | Verdict | Evidence | Notes |
|----|--------|---------|----------|-------|
| **M6** | Precedence 4/3/2/1 within an ingredient's ordered tag list | **MATCH** | `Brew` L252: `rank switch { 0=>4.0, 1=>3.0, 2=>2.0, _=>1.0 }`. Also `DisplayColor` L421 uses the same weights for colour. | §1.3 precedence — exactly as specified. |
| **M7** | Tag pool stacks with diminishing returns | **MATCH** | `BuildProfile` → `MinigameModifierCommon.Fold` (per-tag `StackFactor(count)`); `StackFactor` L45: `(1-0.4^n)/0.6`. Counts accumulate across merges in `Merge` L210-211. | §1.3 stacking — 2nd copy ~+40%, 4th ~nil. Correct. |
| **M8** | Base **±** per ingredient (volatility push) | **MATCH** | `ModTable` `Vol` column folds into `ModProfile.Vol` (`Fold` L65); applied as `vEq += mp.Vol` (`Evolve` L350) and at build in `Orb.V` init (`OnBegin` L137, `Merge` L218). | The additive "base ±". Correct. |
| **M9** | **×mult** on current stability | **MATCH** | Potency multiplier `pMult` (`Evolve` L350-353) accumulates `StatePot[i]*m` per active state + `mp.PriPot`; drives `pEq=pAnchor*clamp(pMult,0.3,2.4)` L355. States also multiply V-equilibrium via `StateVol[i]*m` L351. | The "×multiplier on current stability (compounding)" — LIFE's compounding manifestation (§2.2). Correct. |
| **D4** | The **×mult is applied to POTENCY equilibrium, not to VOLATILITY-as-a-live-multiplier** | **PARTIAL** | `pMult` multiplies `pAnchor` (potency). Volatility gets an *additive* `StateVol[i]*m` into `vEq`, never a true `×` on live `vol`. | §3.2 says each ingredient has "(a) a base stability ± and (b) a ×multiplier on current stability". Today (b) lands on potency + additive-V, not a *multiplicative* nudge of live volatility. This is a defensible reading (V is the *scored* axis, kept additive so it stays predictable) but it should be **documented as the canonical reading** so the other four don't each invent their own. See B-D4 (doc-only). |

### A.4 — I4 Target from output tags

| ID | Aspect | Verdict | Evidence | Notes |
|----|--------|---------|----------|-------|
| **M10** | Target volatility from OUTPUT tags | **MATCH** | `OnBegin` L144-146: `goalTags = Recipe?.OutputTags ?? fallback`; `_targetV = TargetVolatility(goalTags, _tier)`. `TargetVolatility` L375-380 averages `TagVolatility(t)` → `basis*92 + tier*2`. | §3.2 "target from output tags". Correct. Tier is a *small* nudge (+2/tier), intensity-not-character — good. |
| **M11** | Potency resistance from output tags, scales with tier | **MATCH** | `PotencyResistance` L383-388: `clamp((tier-1)*0.22,0,0.7)`, reduced 0.08 per `pure/refined/precious/quality`. | The "resists raw potency (scales with tier)" clause. Correct. |
| **D5** | Fallback when `OutputTags` empty uses the **union of INPUT tags** (`_orbs.SelectMany(o=>o.Tags).Distinct()`) | **PARTIAL** | `OnBegin` L144. | Reasonable for a null/debug recipe, but it lets *input* character leak into the *target* when a **real** recipe simply has no output tags. **B-D5 fixes this unconditionally** (no dependency on whether such a recipe exists today): real recipe + empty output tags → neutral ~40 V target; input-union kept only for the null debug sampler. |

### A.5 — I5 Numeric UI = potency + volatility only

| ID | Aspect | Verdict | Evidence | Notes |
|----|--------|---------|----------|-------|
| **M12** | Only POT + VOL are shown, as **bars with no digits** | **MATCH** | `DrawSliders`/`DrawGauge` L531-564 — vertical fill bars, target marker + band, no numeric text except the `"VOL"`/`"POT"` labels. | Obeys the numeric-UI house rule (master plan §0 rule 6 / the discipline's direct scoring metrics). |
| **M13** | Everything else is qualitative (named states, marble look, resonance bloom, time-as-bar) | **MATCH** | `DrawStateLabels` L599-614 (named, sized-by-magnitude, no numbers); `DrawHud` L636-641 (time = thin draining top bar, no digits); resonance = golden bloom `DrawStates` L469-474. | No stray numbers in the play view. Correct. |
| **D6** | The **F1 log shows raw numbers** (`h{Heat} t{Turb}`, `[F.. W.. E..]`, `V.. P..`) | **MATCH (allowed)** | `DrawLog`/`BuildLogHeader`/`StatesStr` L665-726. | This is the **dev overlay** (F1), explicitly a debug tool per §1.5 / `MinigameDevLog`. Numbers here do NOT violate the player-facing rule. No action. |

### A.6 — I6 Tag themes obey §2 (spot-check — full audit in §C)

| ID | Aspect | Verdict | Evidence | Notes |
|----|--------|---------|----------|-------|
| **M14** | fire/flame/ember/molten/volcanic/forge → HEAT channel, high volatility | **MATCH** | `Tags` L210-211 (all HEAT); `TagVolatility` L367-368 (`fire..0.8`, `volcanic..0.95`, `molten..0.9`). | §2 FIRE = haste/aggression/**volatility**. Correct for the six fire *bodies*. (lightning/storm/radiant/light/chaos also sit in HEAT but are §2 *riders* — see D7 / §C.2-a, not certified here as fire bodies.) |
| **M15** | ice/frost/frozen/chill → AQUA channel, low volatility, **slows the clock** | **MATCH** | `Tags` L214-215 (AQUA); `ModTable` L103 `frozen(Time 1.3,Rx 0.5)`, `ice(1.2,0.7)` — high Time / low Rx = slower reaction; `TagVolatility` L371 `ice/frost..0.13`. | §2 COLD = control/**deliberation/stability** + slows clock. Correct. |
| **M16** | earth/stone/metal/iron → TERRA, calm, high floor | **MATCH** | `Tags` L216-219; `ComposeVolatility` L268 weights TERRA at **0.12** (lowest but water). `ModTable` earth-likes have `Vol` negative (`stone -5`, `metal -4`). | §2 EARTH = solidity/**resistance**/stable. Correct. |
| **M17** | life/wood/herb/plant + feral (monster/fang/blood) → GROVE, compounding/vitality | **MATCH** | `Tags` L220-224 (GROVE, incl. `blood` at L224 GROVE); `ComposeVolatility` GROVE weight 0.45 (mid); state `StatePot` for Bloom/Root positive (compounding ×). | §2 LIFE = growth/vitality/**multiplier** (compounding). Correct — `blood` correctly a feral LIFE body with an UMBRA rider (`ChExc["blood"]` L133 adds UMBRA). |
| **M18** | void/dark/shadow + mystic (arcane/essence) → UMBRA, entropy/risk | **MATCH** | `Tags` L223-226 (UMBRA); `ComposeVolatility` UMBRA weight **0.80** (highest with fire). `TagVolatility` `void..0.9`, `arcane/magical..0.62`. | §2 SHADOW = entropy/**risk/hidden power**. Correct for void/dark/shadow/spectral/arcane/magical/essence. |
| **M18b** | toxic (poison/venom/toxic/acid) → UMBRA channel | **PARTIAL/DRIFT** | `Tags` L224-225 (UMBRA, correct channel); but `ModTable` L97 gives them `Vol +5/+6, Rx 1.1–1.3` = a swingy destabiliser, with **no over-time decay knob**. | Channel right, **verb wrong**: §2 toxic = "degrade-**over-time**", the code expresses FIRE's "volatility". Fix in **§C.2-b** (add `StExc` Decay amp, trim base Vol). Not certified as clean. |
| **M19** | air/wind/vapor/gas → AIR, fast/light/disperse | **MATCH** | `Tags` L227 (AIR); `ModTable` L113 `wind(Time 0.8,Rx 1.15)`, `gas(0.75,1.2)` — fast/low-time; AIR weight 0.40 (light). | §2 AIR = speed/**lightness/dispersal**. Correct. |
| **M20** | Quality/Grade = **increasing returns** (higher tier = more pot, LESS vol) | **MATCH** | `ModTable` grade rows L86-89 monotone: `starter(0.86,+4)` → `mythical(1.32,-14)`. Comment L82 "grades follow INCREASING RETURNS". | §2 Quality/Grade "more upside for less chaos — increasing returns". Correct — this is the alchemy tuning §2 *cites as the canon*. |
| **M21** | sharp = precision/offense rider even on a calm body | **MATCH** | `ModTable` L109 `sharp(1.05,+3,Time 0.85,Rx 1.25)` (aggressive: +vol, faster); `ChExc["sharp"]` L135 (TERRA 1.25), `PvExc["sharp"]` L168 (TERRA +0.05 pot). | §2 Physical/Structural: sharp = precision/penetration/**offense** rider. Correct. |
| **M22** | temporal = time control (slows a knob) | **MATCH** | `ModTable` L95 `temporal(1.10,-6,Time 1.40,Rx 0.70)` — big Time up, Rx down = slows the reaction. `StExc["temporal"]` amplifies Decay/Crystallize. | §2 Exotic: temporal = **time control**. Correct. |
| **M23** | chaos/dangerous = risk× (bigger swings, randomness) | **MATCH** | `ModTable` `chaos(+14 vol,Rx 1.55)`, `dangerous(+11,Rx 1.45)`; `PvExc`/`ChExc` push HEAT/UMBRA. | §2 chaos/dangerous = **risk×**. Correct. Note: "randomness" is expressed as high volatility target-miss risk, not literal RNG — acceptable (see D8). |
| **M24** | quantum/impossible/power = amplify the **strongest** active effect | **MATCH** | `StrongExc` L161 (`quantum 1.35`, `impossible 1.40`, `power 1.30`); applied `Evolve` L326-331 (higher-volatility state wins ties). | §2 Exotic rule-benders — "amplify the strongest active effect". Correct. |
| **D7** | `lightning`/`storm`/`radiant`/`chaos`/`light` are folded into the **HEAT channel** (given a fire BODY) | **PARTIAL (presentation OK, classification flagged)** | `Tags` L212-213 map these to HEAT with distinct display hues. §2 lists them parenthetically as FIRE's "energetic riders" but files their *definitions* under Energy/Essence (lightning, radiant, light) and Exotic (chaos). | Giving them a HEAT **body** is an acceptable *Alchemy-local* choice (they need mass + a volatile channel; the distinct hue is presentation), but §2 does NOT assign them a fire body — they are **riders**. Documented in **§C.2-a** so the other four treat them as Energy/Exotic riders first, not fire. No Alchemy code change required; the earlier "MATCH (intended) — correct per §2's FIRE row" claim is withdrawn. |
| **D8** | Bounded, **telegraphed** randomness for replayability (§0 rule 3, §3.2) | **DRIFT (resolved by decision — see B-D8)** | `Evolve` is fully deterministic given composition; the only "jitter" is cosmetic (`Hash01` on Wob/bubbles L412, L358). There is **no bounded gameplay RNG** and no *tell*. | §0 rule 3 wants "a bit of randomness … a tell, never a betrayal." Alchemy is 100% deterministic *in the sim*. **B-D8 DECIDES: opt out** (knowledge+timing, not luck), documented in code. **Caveat for the other docs' test plans:** "deterministic sim" is not the same as "bit-reproducible score." `BestOrb()` (L266) and `Recompute()`'s `Max`/`OrderByDescending` (L159/L195) break exact ties by *enumeration order of `_orbs`*, which merge/removal mutates (`Merge` L221 does `Remove;Remove;Add`). Two runs with identical inputs but different merge ORDER can pick a different "best" orb at a tie. Not RNG, but a test asserting an exact `perf` must fix the merge order (or assert a band, not an exact value). §4 test plans that lean on "deterministic = reproducible" must state this. |

---

## B. Ordered fix list (close each drift)

Fixes are ordered by **marked-feel impact** first (the things §3.2 explicitly calls out), then correctness/doc hygiene.
Each fix names the file, the method, the exact constant(s) to add with a starting value, and the acceptance check.
**No fix touches `Game1.Core`** (0-diff) or the certified seam — all are Godot-side chemistry/render tuning.

### B-D1 — Ship "edge = faster = harder" (the headline marked feel). **[HIGH]**
**Problem (D1/D2).** The bell *shape* is right but the needle does not accelerate near the target band. Today `vol`
eases toward `vEq` (the composition equilibrium) at a **constant** `2.4*dt`, so proximity to the SCORED target has no
effect on how twitchy the mixture is.

**Design clarification (resolves the vEq-vs-targetV gap).** There are two different volatilities in play and the fix
must not conflate them:
- `vEq` = the *composition* equilibrium `vol` is pulled toward each tick (`ComposeVolatility(A,heat)+mp.Vol+state bias`).
  This is where the mixture "wants" to sit given what's in it.
- `vTarget` = the *scored* target the player is trying to hold `vol` at (`_targetV`, from output tags).

The marked feel is: **the closer the CURRENT `vol` is to the scored target, the faster `vol` moves** — so parking exactly
on the target is unstable and must be actively held. This is a property of *where the needle is right now* (`|vol -
vTarget|`), NOT of where the equilibrium sits. We therefore accelerate the SAME ease-toward-`vEq` motion by a factor that
peaks when `vol` is near `vTarget`. The direction of drift is still `vEq - vol` (unchanged); only its *rate* is scaled.
This works regardless of where `vEq` sits relative to `vTarget`: if `vEq` is far from `vTarget`, the mixture rushes away
from the band the instant you stop steering; if `vEq` happens to sit on `vTarget`, the acceleration makes it jittery
right where you need calm. Either way, holding *at the target* is the hard part — exactly the marked intent.

**Fix.**
- File: `MinigameTagEffects.cs`.
- Add these to the existing `const` region at the top of the class (the block at L26-27, right after `ReactionTime`),
  so they sit with `HOT`/`WARM`/`HEAT_MAX`/`ReactionTime`:
  ```csharp
  public const double EASE_V_BASE = 2.4;    // floor ease-rate for volatility (was the inline 2.4)
  public const double EDGE_GAIN   = 1.8;    // up to +180% ease-rate when vol sits on the scored target
  public const double EDGE_SIGMA  = 18.0;   // volatility units — REUSE the Quality σ so "edge" == the scored bell band
  ```
- Thread the scored target in. **Signature change (the ONLY one, additive):** add a trailing `double vTarget` parameter
  to `Evolve`:
  ```csharp
  public static void Evolve(double[] A, double pAnchor, ModProfile mp, double age, double reactTime,
                            ref double heat, ref double turb, ref double pot, ref double vol,
                            double dt, double[] outState, double vTarget)
  ```
  **Caller check (verified):** `Evolve` has exactly **one** call site today — `AlchemyMinigame.OnTick` (the `else`
  branch, L178). Add `, _targetV` as the final argument there. `grep "Evolve("` over `scripts/` confirms no other
  caller and no test caller. If a future caller or test is added, it must pass the scored target (or `50.0` for a
  neutral mid-band in a pure chemistry unit test). Adding a trailing parameter is source-compatible with the sole
  existing call once that one line is updated in the same commit.
- Replace the single `vol` ease line (`vol += (Math.Clamp(vEq, 0, 100) - vol) * 2.4 * dt;`) with:
  ```csharp
  var edge  = Math.Exp(-0.5 * Math.Pow((vol - vTarget) / EDGE_SIGMA, 2)); // 1 at the target, →0 far away
  var easeV = EASE_V_BASE * (1 + EDGE_GAIN * edge);                        // 2.4 .. 6.72
  vol += (Math.Clamp(vEq, 0, 100) - vol) * easeV * dt;
  ```
  Use `vTarget` (the parameter) — there is no `vTargetForEase`; that name from the earlier draft was a typo and is
  removed. `easeV` ranges `2.4` (far outside the band) to `2.4*(1+1.8)=6.72` (dead on target).
- **Guard (preserves I2/M5):** `vol` is STILL written only by this one ease line, and it still eases toward `vEq`
  (heat's channel). `edge`/`easeV` scale the RATE, never add to `vol`. Heat continues to enter `vol` only via `vEq`.
- **Acceptance (objective + subjective):**
  - Objective, from the F1 log per-tick `V` readout: with the mixture drifting toward a `vEq` on the far side of the
    target, the per-tick `|ΔV|` measured *as `vol` crosses the target band* is at least ~2.5× the `|ΔV|` measured while
    `vol` is >2σ (>36 units) from the target — i.e. `easeV` ≈ 6.7 vs 2.4. (Compute both from consecutive log lines.)
  - Subjective: an orb whose `vEq ≠ vTarget` cannot be parked on the target — it slides off faster the closer it is, so
    the player must cast at the moment of crossing rather than "settle and wait." A masher who lets it settle to `vEq`
    scores the `vEq`-distance bell; only active timing near the crossing scores high.

### B-D3 — Couple LIVE heat to tick-speed (not just build-time vigor). **[HIGH]**
**Problem (D3).** §3.2 says "heat == tick-speed". Today only build-time `rx` scales the tick; accumulated heat does not.
**Fix.** Scale the per-tick reaction RATES by a heat factor so a hot mixture ticks faster *now*.

- File: `MinigameTagEffects.cs`, method `Evolve`.
- Add constant to the same class `const` region as B-D1's:
  ```csharp
  public const double HEAT_TICK_GAIN = 0.5;   // hot mixture ticks up to +50% faster
  ```
- **Where `heatTick` is computed, and which heat it reads.** Heat is written in three places in `Evolve`:
  (1) `heat += (heatTarget - heat) * 1.6 * rx * dt;` (the build, the line M3 cites),
  (2) the six `Shift(...)` calls each `heat -= …` (steam/quench cooling), and
  (3) the final `heat = Math.Clamp(heat, 0, HEAT_MAX);`.
  Compute `heatTick` from the **post-build, post-clamp** heat — i.e. **immediately AFTER the `heat = Math.Clamp(heat, 0,
  HEAT_MAX);` line** (the line right after the six `Shift` calls). This uses the settled heat for THIS tick after
  transmutation cooling, so a brew that just quenched ticks the rest of the tick's easing at the calmer rate:
  ```csharp
  var heatTick = 1 + HEAT_TICK_GAIN * (heat / HEAT_MAX);   // range 1.0 .. 1.5
  ```
  Order note: the six `Shift` calls (transmutations) run BEFORE `heatTick` exists, so they use the plain
  `rx * w * dt` frac (unchanged) — heat governs the *equilibrium-ease* speed, not the channel-transmutation speed,
  which keeps the transmutation-vs-heat coupling one-directional and un-runaway.
- **Exactly what `heatTick` multiplies.** ONLY the two equilibrium-ease rates that live *below* the `heatTick` line:
  - the `vol` ease from B-D1 — multiply the **rate**, not the frac target: `... * easeV * heatTick * dt;`
  - the `pot` ease — change `pot += (pEq - pot) * 2.0 * dt;` to `pot += (pEq - pot) * 2.0 * heatTick * dt;`
  Do **NOT** touch: the `heat +=` build (avoids the heat→tick→heat runaway), the six `Shift(...)` fracs (see order note
  above — they already carry `rx*w`), or `heatTarget`. `heatTick` multiplies the ease *rate constant* (outside the
  `Clamp(vEq…)-vol` distance term), never anything inside a `Shift` frac.
- **Guard (keeps I2/M5):** `heatTick` scales the *rate at which `vol` approaches `vEq`*; `vol` is still written only by
  the one ease line and still only toward `vEq`. Heat still never appears as a direct `vol +=`. Faster approach ≠ larger
  target: the ceiling is still `Clamp(vEq,0,100)`.
- **Acceptance:** a fire-heavy brew's `vol`/`pot` visibly converge to their equilibria within fewer ticks (hotter =
  snappier), and combined with B-D1 it is twitchier near the band; an ice-heavy brew (low heat) eases slowly and calmly.
  F1 log: for two brews at the same `|vEq-vol|`, the hotter one's per-tick `ΔV`/`ΔP` is larger by ≈`(1+0.5*heat/100)`.

### B-D4 — Document the canonical (base ±, ×mult) reading. **[MED — doc, no code]**
**Problem (D4).** The ×mult lands on POTENCY equilibrium + additive-V, not a literal ×multiplier of live volatility.
This is a *deliberate* choice (V is the scored axis; keeping it additive keeps scoring legible), but it is undocumented,
so the other four minigames could each invent a different reading of "×mult on current stability."
**Fix (doc only).** Add a short comment block above `Evolve`'s equilibrium section (L349) stating the canon:
> *Per-ingredient effect = (a) additive **base ±** on the volatility equilibrium (`ModProfile.Vol` + `StateVol`), and
> (b) a **×multiplier** that compounds on the **potency** axis (`ModProfile.Pot`/`StatePot`/`PriPot`). Volatility — the
> SCORED axis — is deliberately kept additive so the bell stays predictable; the multiplicative "compounding" clause of
> the marked model is realised on potency. Every other minigame must mirror this split: multiply the un-scored axis,
> add on the scored axis.*
- No behaviour change. This becomes the reference contract the other four cite.
- **Acceptance (satisfiable at THIS doc's implementation time — does not depend on the other four docs existing yet):**
  the comment block exists above `Evolve`'s equilibrium section AND states the split verbatim as above (add-on-scored-axis,
  ×-on-unscored-axis). That is the whole deliverable for B-D4. *(Downstream, non-blocking:* the Refining/Engineering/
  Enchanting/Smithing impl docs, when written per master-plan §4, must cite this comment as their "×mult vs base ±"
  contract — but that is a checklist item in THOSE docs, not a gate on this one. This doc records the contract; it does
  not wait on its consumers.)*

### B-D5 — Guard the target-tag fallback against input leakage. **[LOW]**
**Problem (D5).** The current fallback (`OnBegin` L144) uses the union of *input* tags whenever `OutputTags` is empty,
which lets input character set the scored target. This is wrong for a **real** recipe that simply has no output tags
(the target should be neutral, not input-derived); it is *acceptable* only for the fully-null **debug** sampler, where
there is no recipe at all and sampling input character is the only signal available.

**Decision (no longer deferred).** Distinguish the two empty cases by whether `Recipe` itself is null:
- `Recipe == null` (debug sampler) → keep the input-union fallback. There is no authored intent; input character is the
  best available basis and this path never ships to a player.
- `Recipe != null` but `Recipe.OutputTags` is empty (a real recipe with no output tags) → use a **neutral** target:
  pass an empty tag list so `TargetVolatility`'s `n==0` branch (L378) yields `basis=0.4 → 0.4*92 + tier*2 ≈ 38..44`.
  This is independent of whatever the inputs were.

We do **not** condition this on "if real recipes ship with empty OutputTags" — the guard is written to be correct
whether or not any such recipe exists today, so no verification of the recipe corpus is required to implement it.

**Exact rewrite** of the L144 ternary (current: `var goalTags = Recipe?.OutputTags is { Count: > 0 } ot ? ot :
_orbs.SelectMany(o => o.Tags).Distinct().ToList();`):
```csharp
List<string> goalTags =
    Recipe?.OutputTags is { Count: > 0 } ot ? ot                       // real recipe WITH output tags
    : Recipe != null                       ? new List<string>()        // real recipe, NO output tags → neutral target
    : _orbs.SelectMany(o => o.Tags).Distinct().ToList();               // debug sampler (Recipe==null) → input character
```
This mirrors the existing `{ Count: > 0 }` pattern already used at L116/L144; the else-branch just gains the
`Recipe != null` split. No change to `TargetVolatility`.
- **Acceptance:** a real recipe with fiery *inputs* but empty `OutputTags` targets ≈40 volatility (neutral), not a
  high fire-biased target; the debug sampler (no recipe) still samples input character as before.

### B-D8 — Randomness posture: **DECIDED — opt out, documented.** **[LOW — doc]**
**Problem (D8).** Alchemy is fully deterministic; §0 rule 3 wants bounded, telegraphed randomness. As the reference, it
must either *demonstrate* the pattern or *explicitly opt out* so the other four know the pattern is theirs to own.

**DECISION (chosen, not a recommendation — this is the shipped posture; master-plan §4 item 9 satisfied).**
**Alchemy opts OUT of gameplay RNG.** Its difficulty is knowledge + timing (§0 essence: "Knowledge + timing"), and
after B-D1 the "hold the band while it slides off faster near the target" mechanic already supplies the skill-ceiling
tension that RNG would otherwise provide. Adding RNG would muddy the reference and make the tag→composition→score chain
non-reproducible for tests. The telegraphed-randomness pattern (§0 rule 3) is instead owned by Refining (within-theme
pattern variant), Engineering (randomised solvable start state), and Enchanting (per-node hazard timing) — each of those
impl docs implements it; Alchemy does not.

**The only code change for B-D8 is a comment.** Add above the `AlchemyMinigame` class declaration:
> *Randomness posture (master plan §0 rule 3): Alchemy is INTENTIONALLY deterministic. Replayability comes from
> ingredient permutations + merge-order choices + the timing skill of holding volatility on the target as it destabilises
> (B-D1), not from bounded RNG. The telegraphed-RNG pattern is exercised by Refining / Engineering / Enchanting.*

- **Acceptance:** the opt-out comment exists on `AlchemyMinigame`. No sim RNG is added. (There is nothing to telegraph
  because nothing random ships.)

**Rejected alternative (documented so it is not re-litigated), fully specified in case the designer overrides.** If the
designer later wants a *tell* instead of opt-out, the sanctioned implementation — and the ONLY acceptable one — is a
rare, always-telegraphed "surge":
- A surge nudges the mixture's `vEq` by `SURGE = +8` volatility for `SURGE_T = 0.6s`.
- It is **always** preceded by a `TELL_T = 0.5s` telegraph: a brightening pulse ring on the marble via
  `CraftFx.RingPulse(_scene, o.Pos, o.R * 1.25f, phase01, Gold, 2.5f, 0.7f)` where `phase01` ramps `0→1` across the
  telegraph. `CraftFx.RingPulse(CanvasItem, Vector2 c, float baseR, float phase01, Color, float width=2.5f,
  float spread=0.7f)` is confirmed to exist (`scripts/CraftFx.cs` L210) — this alternative is buildable as written.
- **Seed source (there is no `craftId` on the Alchemy side).** `RecipeContext` exposes `OutputId`, `Inputs`, `Tier`,
  `Points`, `OutputTags` (see `scripts/minigames/RecipeContext.cs`) — NOT a `craftId`. Seed the surge schedule from a
  stable hash of `Recipe?.OutputId ?? "sampler"` combined with `_orbs.Count`, e.g.
  `var seed = (Recipe?.OutputId ?? "sampler").GetHashCode() ^ _orbs.Count;` and drive a small `System.Random(seed)` to
  pick surge times. This is reproducible per craft without inventing a nonexistent field.
- **Never** ship an untelegraphed swing; the surge must show its `RingPulse` tell for the full `TELL_T` before `vEq`
  moves. *(This alternative is NOT the chosen posture — the opt-out comment is. It is documented only to prevent an
  untelegraphed hack if the decision is ever reversed.)*

### B-D-consistency — preserve these invariants
I2/M5 (heat-never-touches-V), I3 precedence/stacking, I4 target-from-output, and I5 numeric-UI are correct and must be
**preserved** through B-D1/B-D3 (both explicitly keep `vol` written by exactly one ease line). The §C tag audit is
**mostly** correct but NOT wholly clean — five deviations (§C.2-a/-b/-d/-e/-g) are documented above with fixes; do not
treat §C as a blanket pass.

---

## C. §2 tag-interpretation audit (Alchemy as the consistency reference)

This audits Alchemy's reading of **every** tag in the real vocabulary (`MinigameTagEffects.Tags` + the `Metal`/`Wood`
HashSets + every `ModTable` key) against the §2 Tag Theme Dictionary. The other four minigames should author their
tables so the *same* tag lands on the *same* §2 verb — Alchemy's channel + volatility direction is the intended ground
truth. **Honesty rule for this audit:** where the shipped code matches §2 it is marked MATCH; where it does NOT, it is
marked **MISMATCH** with the fix, rather than certified through. §C.2 lists the mismatches.

**A note on "body" vs "rider" (needed to read the rows correctly).** A tag reaches the sim through two doors:
1. **`Resolve()`** (`Tags` dict / `Metal` / `Wood`) → gives the tag a **body channel** (a share of the six-channel mass
   via `Brew`). Only tags in those three collections get a body.
2. **`ModTable` / `ChExc` / `StExc` / `StrongExc` / `PvExc`** (via `BuildProfile`) → gives the tag a **modifier rider**
   (pot ×, vol ±, time ×, rx ×, channel/state/primary exceptions). A tag can have a rider with **no body**.

§2's elemental families (FIRE/WATER/…) are **bodies**; §2's four modifier families (Quality, Physical, Energy, Exotic,
Function) are **riders** that "change magnitude/quality, not the verb." A tag mis-classified as a *body* when §2 makes it
a *rider* (or vice-versa) is a real theme error — that is exactly the chaos/lightning/radiant problem below.

### C.1 Per-theme rows

| §2 Theme (verb) | Tags (with the door each enters by) | Alchemy channel + knob | §2 verb satisfied? |
|-----------------|-------------------------------------|------------------------|--------------------|
| **FIRE** — haste/aggression/volatility | **bodies:** fire, flame, ember, molten, forge, volcanic (`Tags`→HEAT). **riders only (no HEAT body of their own):** lightning, storm, radiant, light, chaos — these enter HEAT via `Tags` for *hue+channel* but §2 files them under Energy/Exotic, see C.2-a | **HEAT** channel; `TagVolatility` 0.7–0.95; `ModTable` low Time / high Rx (`volcanic 0.85/1.4`, `chaos 0.70/1.55`); heat-build fed by HEAT mass | **YES for the six bodies** — pushes toward the volatile edge + faster tick, §2.2 alchemy row exactly. **See C.2-a** for the five riders that also carry a HEAT body: acceptable as *presentation*, but the doc no longer claims §2 assigns them a fire body. |
| **WATER** — flow/cleanse/dilute | water, aqua, liquid (`Tags`→AQUA); **solvent** (ModTable rider only, no body) | **AQUA** channel; `ComposeVolatility` weight 0.20 (calming). **solvent:** `ChExc` boosts AQUA / damps TERRA (washes), BUT its `ModTable` base is `Vol +3 / Rx 1.15` (a mild destabiliser/haste) | **PARTIAL — see C.2-e (solvent).** water/aqua/liquid: YES (calm centre). solvent's ChExc says "wash" but its base row pulls toward haste/volatility — a split personality the row below reconciles. |
| **COLD/ICE** — control/deliberation/stability | ice, frost, frozen, chill (`Tags`→AQUA still-pole) | **AQUA** channel; `ModTable` high Time (1.1–1.3) / low Rx (0.5–0.8) = **slower tick**; `Vol` negative (−5..−8) | **YES** — strong stabiliser + slower clock; "buys time, caps instability." |
| **EARTH** — solidity/resistance/mass | earth, stone, sand, mineral (`Tags`→TERRA); **metals via `Tags`:** metal, iron, crystal, gem, alloy, sharp*, durable*, strong* (*rider-shaped, see C.2-c); **metals via `Metal` HashSet:** copper, tin, steel, mithril, bronze, adamantine, silver, gold, orichalcum; **metallic** (ModTable rider, no body) | **TERRA** channel; `ComposeVolatility` weight 0.12 (calmest); metal `ModTable` rows `Vol` negative, high Time. `Metal`-set tags → TERRA body via `Resolve` L240 | **YES** — raises the stability floor; resists swings; slow. **copper/tin are covered here** (they resolve to TERRA through the `Metal` HashSet L229 even though they lack a `Tags`/`ModTable` row — a body, no rider; see C.2-f). `metallic` is a HASTE-leaning metal (`Vol +2, Rx 1.20`): a §2-legal "conductive/energetic metal" rider, flagged in C.2-c. |
| **LIFE** — growth/vitality/spread | plant, herb, leather, living (`Tags`→GROVE); **woods via `Wood` HashSet:** oak, ash, ironwood, ebony, worldtree, **exotic**, birch, willow; feral monster, fang, scales, bone, gel, carapace (`Tags`→GROVE); **blood** (`Tags`→GROVE + UMBRA rider) | **GROVE** channel; Bloom/Root/Spore states; `StatePot` positive (compounding ×) | **YES** — regen toward target + multiplier on stability (compounding). **`exotic` is covered here** — it is in the `Wood` HashSet (L230) so it resolves to a GROVE body via `Resolve` L241 (a body, no `ModTable` rider; see C.2-f). `blood` = feral LIFE body + UMBRA rider (`ChExc["blood"]`) — the canon LIFE-body/shadow-rider split. |
| **SHADOW** — entropy/risk/hidden power | void, dark, shadow, spectral (`Tags`→UMBRA); **toxic** poison, venom, toxic, acid (`Tags`→UMBRA); **mystic** arcane, magical, essence (`Tags`→UMBRA) | **UMBRA** channel; `ComposeVolatility` weight 0.80; Decay/Brimstone/Brine states; big `Vol`+ | **PARTIAL — see C.2-b (toxic).** void/dark/shadow/spectral/arcane/magical/essence: YES (entropy/hidden power/amplify). **toxic (poison/venom/toxic/acid): the CHANNEL is right (UMBRA) but the VERB is wrong** — §2's toxic verb is "degrade-over-**time**", and the code gives them only `Vol +5/+6, Rx 1.1–1.3` (a swingy destabiliser = the FIRE verb), with **no over-time decay knob**. C.2-b specifies the fix. |
| **AIR** — speed/lightness/evasion | air, wind, vapor, gas (`Tags`→AIR) | **AIR** channel; `ModTable` low Time (0.75–0.8) / high Rx (1.1–1.2); weight 0.40 (light) | **YES** — fast, light nudges; disperses (weakens) the pool. |

### C.1.a Modifier-family rows (riders — "change magnitude/quality, not the verb")

| §2 Family / tag (verb) | Tags + `ModTable` values | Alchemy knob | §2 verb satisfied? |
|------------------------|--------------------------|--------------|--------------------|
| **Quality/Grade — increasing returns** (magnitude ↑, chaos ↓) | starter(0.86,+4) → basic → common → standard → uncommon → fine → quality → refined → rare → advanced → precious → ancient → legendary → mythical(1.32,−14). **Plus the loose grades, direction-checked individually:** superior(1.14,−4) ↑, epic(1.22,−8) ↑, pure(1.10,−12) ↑pot / strong-stabilise, holy(1.15,−4) ↑, material(1.00,−1) ~neutral, **mundane(0.85, 0) — DOWNGRADE (pot < 1)** | `ModTable` grade rows: monotone pot↑ / vol↓ up the main chain | **YES for the ordered chain + superior/epic/pure/holy/material** (all pot≥1, vol≤0 = "more upside, less chaos"). **mundane is the deliberate EXCEPTION:** pot 0.85 (<1) is a *downgrade* — §2's "increasing returns" describes the ASCENDING grades; mundane is the floor below `starter` and correctly reduces potency. Not a violation; the increasing-returns claim covers ascending grades, and mundane sits below them by design. |
| **Physical/Structural — reinforce+slow; sharp=offense; layered/flexible/versatile/memory=complexity/adaptability** | durable(1.0,−3,T1.20), hard(1.0,−5,T1.10), solid(1.0,−8,T1.25), dense(1.0,−6,T1.3), heavy(1.0,−4,T1.3), strong(1.10,−2); **sharp**(1.05,+3,T0.85,Rx1.25); **layered**(1.0,−2,T1.30), **flexible**(1.0,−4,T1.20), **versatile**(1.05,−1), **memory**(1.05,−4,T1.15) | reinforcers: `Vol` negative + `Time` up (slow, stable). sharp: `Vol` +, `Time` down, `Rx` up (fast/offense) + TERRA `ChExc`/`PvExc`. complexity tags: modest `Vol−`/`Time↑` + state exceptions (`layered`/`flexible` damp Brimstone/Blaze; `memory` amps Temper/Quench, damps Decay; `versatile` damps Decay/Brimstone) | **YES for all.** durable/hard/solid/dense/heavy → stabilise+slow (✓). sharp → offense rider on a calm TERRA body (✓, M21). **layered/flexible/versatile/memory now explicitly covered:** each expresses "complexity/adaptability" as more/steadier states + selective state damping (adaptable = fewer runaway states), which is §2's "more states/branches/options" mapped onto Alchemy's state set. Not no-ops. |
| **Energy/Essence — amplifiers/wildcards** | magical(−2), arcane(−4), essence(+1); **radiant**(+2), **light**(−3), **spectral**(+4,T1.30), **blood**(+5), **lightning**(+9,Rx1.50,T0.75), **chaos**(+14,Rx1.55,T0.70) | magical/arcane/essence = pot× + UMBRA `ChExc` (raw amplification, ✓). lightning = burst/erratic (`Vol+9`, fast, `ChExc` HEAT/AQUA boost, `StExc` amps Blaze/Brimstone, ✓). chaos = randomness/instability expressed as high `Vol+14` + fast + amps fierce states (✓ as "instability", see D8/C.2-a on it not being literal RNG). blood = vitality-for-risk (GROVE body + UMBRA rider, ✓). radiant/light = §2 riders (`ChExc` HEAT/GROVE boost, UMBRA damp = "light purges shadow", ✓) | **YES** — every Energy tag is an amplifier/wildcard rider. **These are the tags C.2-a is about:** they are correctly *riders* here; the only issue is that four of them (lightning, storm, radiant, light) ALSO get a HEAT body via `Tags`, which C.2-a addresses as presentation, not verb. |
| **Exotic/Rule-benders** | **quantum**(+4), **impossible**(+6), **power**(+3) → `StrongExc` amplify-strongest (✓, M24); **temporal**(−6,T1.40,Rx0.70) → time control, slows (✓, M22); **dangerous**(+11,Rx1.45) → risk× (✓); **harmony**(1.10,−8,Rx0.90) → order/stabilise; **elemental**(1.10,+5,T0.90,Rx1.20) → all-element | quantum/impossible/power: `StrongExc` (amplify strongest). temporal: big `Time↑`/`Rx↓` (slow). dangerous: `Vol+`/`Rx+` + `StExc` Brimstone. **harmony:** `Vol −8` + `Rx 0.90` + `StExc` damps Brimstone/Decay, amps Bloom = **stabilise/order** (✓ §2 verb). **elemental:** `ChExc` boosts **HEAT + AIR only** | **YES for quantum/impossible/power/temporal/dangerous/harmony** (harmony now has an explicit row — it stabilises, matching §2 "order/stabilise"). **elemental = PARTIAL, see C.2-d:** §2 says "all-element touch" but the code boosts only HEAT+AIR (two of six), a narrower-than-§2 reading — legal in direction (it does touch elements) but under-delivers "all"; flagged, low-priority. |
| **Function/Output — set the goal's role (mostly OUTPUT tags)** | weapon(+4), combat(+5), explosive(+14), strength(+3) → aggressive; armor(−9), protection(−8), defense(−8), resistance(−7), healing(−6), regeneration(−6) → gentle/stable; utility/tool/crafting/consumable → mild negative (neutral-calm) | **As per-ingredient MODIFIERS** these all land correctly (`ModTable` `Vol` sign matches role: weapon/combat/explosive/strength push `Vol+`; armor/defense/etc push `Vol−`). **As OUTPUT-tag TARGET-setters via `TargetVolatility`: see C.2-g** — `TagVolatility`'s switch does NOT list weapon/armor/combat/etc, so they hit the `_ => 0.35` default and DON'T actually set an aggressive/defensive TARGET | **PARTIAL — see C.2-g.** The per-ingredient `Vol±` direction is correct (aggressive outputs = higher `Vol` push, defensive = lower). BUT the claim that these set the *target's character through `TargetVolatility`* is FALSE for most of them: `TagVolatility` lacks their keys, so an all-`weapon` output tag targets the neutral 0.35 basis, not a high-V target. C.2-g gives the fix (add the role keys to `TagVolatility`) or the honest downgrade (they act only as ingredient modifiers). |

### C.2 Mismatches and under-specified readings (the honest list)

**C.2-a — lightning / storm / radiant / light / chaos get a HEAT *body*, but §2 files them as riders.**
`Tags` (L212-213) maps all five to the HEAT channel, so `Brew` gives them fire *mass* and `ComposeVolatility` reads
them as fire. §2.1 lists them only as FIRE's parenthetical "energetic riders" and separately under Energy/Essence
(lightning = burst/erratic; radiant/light have their own entries) and Exotic (chaos = randomness). **Verdict:** the
*direction* is defensible (they are all high-volatility, fire-adjacent) and Alchemy needs *some* channel for a tag to
have mass, so routing them through HEAT for **hue + a volatile body** is an acceptable Alchemy-local choice. **The doc
no longer claims "§2 grants them a fire body."** This withdrawn-claim wording is the **binding canon** for the whole
minigame set, and it is **PRESCRIPTIVE for the other four docs**: lightning / storm / radiant / light / chaos are
**Energy/Exotic riders first** (their §2 home — lightning/radiant/light under Energy/Essence, chaos under Exotic) and
**MUST NOT be authored as theme-defining fire BODIES anywhere else.** They may carry a fire-ish *presentation* (hue,
volatile flavour) as a discipline-local fallback only when that discipline genuinely needs a body for them, but their
*verb* is the rider verb (burst/erratic amplification, randomness), never "this is a fire element." **This is the
contract Smithing and Refining currently violate** (they build these tags as fire bodies) — those docs must be corrected
to treat them as riders on top of a real body, not as fires in their own right. Low-priority for Alchemy itself; no
Alchemy code change required — this is the *documentation* correction that keeps the reference from being miscited. (If a
future pass wants strict §2 fidelity in Alchemy too, move these out of `Tags` into ModTable-only riders and give them a
small HEAT `ChExc` instead of a body — noted, not scheduled.)

**C.2-b — toxic (poison/venom/toxic/acid) expresses the FIRE verb, not §2's "degrade-over-time".** [fix: MED]
Channel is right (UMBRA). But `ModTable` gives them `Vol +5/+6, Rx 1.1–1.3` — a swingy destabiliser, which is FIRE's
"volatility" verb, not SHADOW-toxic's "degrade **over time**". There is no decay-over-time knob. **Fix (Alchemy-side —
apply it; it is the correction that makes Alchemy a valid reference for toxic, not merely optional polish):** give the
four toxic tags a `StExc` entry amplifying the **Decay** state (the existing over-time channel-rot mechanic —
`Shift(GROVE→UMBRA)` per tick), e.g. `["poison"]=["venom"]=["toxic"]=new[]{((int)State.Decay,1.35)}` and
`["acid"]=new[]{((int)State.Decay,1.45)}`, and trim their base `Vol` from +5/+6 toward +2/+3 so the character is "rots
the brew down over the reaction window" rather than "adds a fire-like swing." This makes toxic *express
degrade-over-time* (Decay ramps across `w`) instead of a static volatility bump. **Consistency contract:** once applied,
Alchemy's toxic reading is the binding §2 exemplar of "degrade-over-time," and it **aligns with Smithing's correct
over-time reading** (toxic as an enemy damage-over-time / DoT effect, not a burst) — every other minigame must express
toxic as a slow drain/rot on its own axis, never as a FIRE-style volatility spike. **Until the fix is applied, do NOT
let the other four docs cite Alchemy's toxic row as a clean SHADOW-toxic exemplar** — it currently reads as fire.
**This is the one §C mismatch with a concrete code fix**; it is MED (correctness of the reference verb), below B-D1/B-D3.

**C.2-c — metallic is a haste-leaning metal.** `metallic` (`Vol +2, Rx 1.20, ChExc TERRA 1.30, StExc Molten 1.35,
PvExc AIR +4`) reads as a *conductive/energetic* metal rather than a pure stabiliser. §2 EARTH says "metals add HARDNESS
+ (iron/steel) conduction" — so a conductive metal that leans slightly volatile is **§2-legal** (it is the conduction
rider). Documented, no change. sharp/durable/strong appearing in the `Tags` dict give them a TERRA *body* in addition to
their `ModTable` rider — intentional (they are structural), consistent with §2 Physical.

**C.2-d — elemental boosts only HEAT+AIR, not "all-element".** `ChExc["elemental"] = (HEAT 1.25, AIR 1.25)`. §2 Exotic
calls it "all-element touch." Direction is right (it amplifies elemental channels) but it touches two of six. **Fix
(optional, LOW):** either broaden `ChExc["elemental"]` to a mild boost across all six channels, or accept the narrower
reading and note it. Flagged so the other docs don't over-claim "elemental = every element" from Alchemy.

**C.2-e — solvent's base row contradicts its wash rider.** `solvent`: `ChExc` (AQUA 1.30, TERRA 0.80) = "wash
impurities" (✓ WATER verb), but `ModTable` base `Vol +3, Rx 1.15` leans haste/volatile (WATER should reduce intensity,
be forgiving). **Fix (apply it — this is the correction that makes solvent a valid WATER exemplar):** flip the base from
`(Vol +3, Rx 1.15)` toward WATER's verb — `solvent = (0.98, -2, 0.95, 1.05)` (Pot 0.98, **Vol −2**, Time 0.95, Rx 1.05:
mild calm + slight slow) so the base *agrees* with its wash `ChExc` that solvent *forgives/dilutes* rather than
*destabilises*. **Consistency contract (binding on the other four docs):** until this flip is applied, the row is a
MATCH on the ChExc but a MISMATCH on the base, so **the other four docs must NOT cite solvent as a clean WATER exemplar.**
More broadly, **every water-family tag (water, aqua, liquid, solvent) must pull toward forgive/cleanse — a NEGATIVE
volatility/intensity push — never toward haste or volatility (never a positive Vol).** If a discipline's WATER tag
speeds things up or destabilises, it has violated §2.1 (WATER = flow/cleanse/dilute, the still-and-forgiving verb) and
is wrong.

**C.2-f — copper / tin / exotic are BODY-ONLY (no rider) and that is fine.** copper, tin (in `Metal`), and exotic (in
`Wood`) resolve to a channel body via `Resolve` (TERRA / TERRA / GROVE) but have **no `ModTable` row**, so they
contribute mass + hue only, no pot/vol/time modifier. This is correct and §2-consistent (a plain copper ingot is pure
EARTH body; `exotic` wood is pure LIFE body). No action — but they ARE now enumerated (they were silently uncovered
before). Other disciplines that want per-metal / per-wood distinction must add their own finer table; the §2 theme
(EARTH / LIFE) is the contract.

**C.2-g — Function/Output tags do NOT set the TARGET through `TargetVolatility`.** `TargetVolatility` → `TagVolatility`,
whose `switch` has no case for weapon/armor/combat/defense/protection/healing/etc — they fall to `_ => 0.35`. So the
prior claim "aggressive → high target-V, defensive → low target-V *via TargetVolatility*" was FALSE: those tags shape
the target ONLY if they also appear as body/volatility tags, which they don't. They DO act correctly as **per-ingredient
`ModTable` modifiers** (weapon/combat push `Vol+`, armor/defense push `Vol−`). **Fix (choose one):**
- *(Recommended, LOW code)* add the role keys to `TagVolatility` so output-tag character actually reaches the target,
  e.g. `"weapon" or "combat" or "explosive" or "strength" => 0.7`, `"armor" or "defense" or "protection" or
  "resistance" => 0.18`, `"healing" or "regeneration" or "harmony" => 0.25`. Then an all-`weapon` output really targets
  a high-V brew (aggressive) and an `armor` output a calm one — matching §2's Function/Output verb.
- *(Or)* accept that Function/Output tags act only as ingredient modifiers and **downgrade the doc's claim** to that.
The current code does the second; this doc now states it plainly instead of certifying the first.

### C.3 Untested/rider-only tags are NOT no-ops on the primary composition — but they ARE body-less (master-plan §1.6)

Master-plan §1.6 requires "an untested tag resolves to its *theme default*, never a no-op." The Alchemy reality is more
nuanced and must be stated so the other four don't copy a false assumption:
- A tag in `Tags`/`Metal`/`Wood` gets a **body** (channel mass) via `Resolve` → it is never a no-op.
- A tag **only** in `ModTable`/exception banks (e.g. `harmony`, `temporal`, `dangerous`, `power`, `elemental`, most
  Function/Output tags) gets a **rider** (pot/vol/time/rx + exceptions) but **no body** — `Resolve` returns `null` for
  it, and `Brew` `continue`s past it (it adds no channel mass). So it DOES contribute to the sim (through
  `BuildProfile` → `Evolve`'s `mp`), but it does NOT add a channel/essence.
- A tag in **neither** collection (a brand-new, wholly-untested tag) → `Resolve` null AND no `ModTable` row → it is a
  **true no-op** in Alchemy today. This is the one place Alchemy does *not* satisfy §1.6's "resolves to a theme default."

**Reconciliation / obligation for the reference:** §1.6's "theme default, never a no-op" is an *aspiration the shared
spine has not yet met*. Two honest options, flagged for the designer (not silently passed):
1. *(Documentation-only, chosen for now)* Record that Alchemy's guarantee is weaker: **known tags** (body or rider) are
   never no-ops; a **wholly-unknown** tag is currently a no-op. The tag corpus is enumerated (every `items.JSON` tag is
   in `Tags`/`Metal`/`Wood`/`ModTable`), so there is no *shipping* no-op today — the risk is only for a future invented
   tag before its table row is authored.
2. *(Future code, noted not scheduled)* Add a `Resolve` fallback so an unknown tag routes to a **neutral rider**
   (`Pot 1.0, Vol 0, Time 1.0, Rx 1.0`) and a **neutral small TERRA body** (the calmest channel) — literally "theme
   default." That would make §1.6 true for Alchemy and give the other four a pattern to copy.

This is called out precisely because the reconciliation is supposed to catch it: **§1.6 is not yet satisfied by the
shared engine, and the other four impl docs must not assume it is.**

### C.4 Audit result

Alchemy's tag interpretations are **§2-consistent in channel/direction for every elemental body and every rider family**,
with **five documented deviations** the other docs must NOT inherit blindly: C.2-a (lightning/storm/radiant/light/chaos
carry a HEAT body that §2 files as a rider — presentation, no verb flip), C.2-b (toxic expresses volatility not
degrade-over-time — has a concrete MED fix), C.2-d (elemental touches 2/6 channels not "all"), C.2-e (solvent's base
contradicts its wash rider), and C.2-g (Function/Output tags don't reach `TargetVolatility`). **No tag INVERTS its theme**
(no fire-calms / ice-hastens). When authoring Refining / Engineering / Enchanting / Smithing tables: look the tag up in
§C.1/§C.1.a, confirm the §2 verb, apply the §C.2 corrections, then map the verb onto the discipline's knob via §2.2 —
never re-derive the tag's meaning, and do not copy the five deviations.

**Vocabulary note for the other docs (not an Alchemy bug):** `Metal`/`Wood` are HashSets resolved to a single channel +
fixed hue (`Resolve` L237-243): every metal → TERRA (earthy gold), every wood → GROVE. `blood` lives in GROVE (`Tags`
L224) with an UMBRA rider — LIFE body + shadow rider is the canon.

---

## D. Reuse map (confirming the reference wiring; no new assets)

Alchemy already reuses the full shared toolkit. Listed so the other four match its call surface exactly.

| Toolkit / seam | Alchemy call sites | Reuse note |
|----------------|--------------------|------------|
| `MinigameOverlay` (seam) | `Begin`→`OnBegin` L110; `Finish(perf)` L246; `FailCraft()` L243/193/195; `SetQuality` L160/191; `FullscreenScene=true` L20 | Produces `perf∈[0,1]` only. 0-churn base. **Verified: no §B fix touches the exactly-once path** — `Finish`/`FailCraft` are called only from `End()`/`OnTick` and none of B-D1/B-D3/B-D4/B-D5/B-D8 edits those call sites. The seam invariant (`Finish` OR `FailCraft`, exactly once) is preserved. |
| `RecipeContext` | `OnBegin` L116-147 reads `Inputs[{Name,Tags,Qty,MaterialTier}]`, `OutputTags`, tier | Degrades gracefully when `Recipe==null` (sampler L118-119). |
| `MinigameModifierCommon` | `MinigameTagEffects.ModProfile : base` L174-177; `Fold`/`Clamp` in `BuildProfile` L188-190; `StackFactor` L181 | THE effect-bank engine. Alchemy declares tables; folding/stacking/clamping shared. |
| `CraftFx` | `Ellipse` L729; `Hash01` L734 (`Hash`); `RoundRect` L691; `GradientBackdrop` (fallback via base) | Primitives + no-shader backdrop safety net. |
| `CraftColor` | `DeMuddy` L429; `RadialGrad` L387; `Darken`/`Lighten`/`Brighten` L730-732 | Vivid multi-channel blends + fake sphere gradient. |
| `StateVisual` | `DrawStates` (`AlchemyMinigame` L438-457) has **17 case arms** — one per non-None `State` (the enum is `None` + 17 named states; `StateCount = 18` counts `None`). Those 17 states dispatch to **15 distinct `StateVisual` primitives** (some share: Steam/Smoke→`Plume`, Blaze/Brimstone→`Flame`, Bloom/Root→`Vines`). `Look` table L60-61. | The named-state render set. Alchemy is the FULL-fidelity user (§1.5). **Count reconciliation (see below): 17 states → 15 primitives; the enum has 18 entries because index 0 is `None`.** |
| `MinigameDevLog` | `_dev` L104; `Context`/`BeginSession`/`Log`/`Note`/`DrawLog`/`HandleKey` L104-726 | F1 log + F7 notes → `res://playtest_logs/alchemy_playtest.log`. |
| `UiTheme.Rarity` | via `MinigameTagEffects.RarityByRank` L459 + `CraftFx.QualityBands` | Rarity palette; Legendary reads gold everywhere. |

**Colour grounding (theme via `CraftColor`):** every drawn colour derives from a channel family colour
(`MinigameTagEffects.FamCol` L194-202, HSV-defined per §2 theme: HEAT red-orange, AQUA blue, TERRA earthy gold, GROVE
green, UMBRA violet, AIR pale cyan) or a named-state HSV (`StateHsv` L62-66), passed through `CraftColor.DeMuddy` so
multi-essence marbles stay vivid. No raw literal colours drive gameplay reads.

**Count reconciliation (so the other four docs cite the reuse surface correctly).** Three numbers appear in the code and
they are consistent, not contradictory: the `State` enum has **18 members** (`None` at index 0 + **17 named states**),
so `StateCount = 18`. `DrawStates` (`AlchemyMinigame`) has **17 case arms** (one per named state; `None` is never drawn).
Those 17 states are rendered by **15 distinct `StateVisual` primitives** (Steam/Smoke share `Plume`, Blaze/Brimstone
share `Flame`, Bloom/Root share `Vines` — colour + magnitude differentiate them). The `StateVisual` header's "17 states
→ 15 primitives" and the `AlchemyMinigame` L428/L477 comments both refer to the **17 named states**; wherever an older
comment said "14", read it as the primitive count for the *non-sharing* signatures and treat **15 primitives / 17
states / 18 enum entries** as the authoritative triple.

**`Game1.Core` 0-diff:** confirmed — all changes in §B and the §C.2 fixes are Godot-side only, in two files:
`MinigameTagEffects.cs` (the `Evolve` `vTarget` parameter + `EASE_V_BASE`/`EDGE_GAIN`/`EDGE_SIGMA`/`HEAT_TICK_GAIN`
constants + the optional §C.2-b/-d/-e/-g table-value tweaks) and `AlchemyMinigame.cs` (the one `Evolve` call-site
argument + the B-D5 ternary + the B-D4/B-D8 comments). **The `Evolve` signature change is the only public-API change and
it is source-compatible** — its sole caller is updated in the same commit (verified: one call site, no test caller). No
`Game1.Core` file is touched; the certified craft path (`Finish`/`FailCraft` exactly-once) is untouched; Alchemy only
produces `perf`.

---

## E. Punch-list summary (what to actually do)

**Apply in this order (B-D1 first — it shifts line numbers B-D3 relies on; re-locate B-D3 by anchor, not by number).**

| Fix | Priority | Kind | Decision | One-liner |
|-----|----------|------|----------|-----------|
| **B-D1** | HIGH | code (`Evolve` + 1 call site) | — | Add distance-to-target ease acceleration → ship "edge = faster = harder." Adds trailing `double vTarget` param to `Evolve` (sole caller updated same commit). Rate `easeV` = 2.4 .. 6.72. |
| **B-D3** | HIGH | code (`Evolve`) | — | Couple LIVE heat to tick-speed: `heatTick = 1 + 0.5*(heat/HEAT_MAX)` (1.0..1.5) on the `vol` + `pot` ease RATES only, computed after the final heat-clamp. Never on `Shift` fracs or the heat build; never writes `vol`. |
| **C.2-b** | MED | code (table) | — | Give toxic (poison/venom/toxic/acid) a Decay-state `StExc` amp + trim base `Vol` → express §2's degrade-over-time, not FIRE's volatility. |
| **B-D4** | MED | doc | — | Comment the canonical (additive-on-scored-axis, ×-on-unscored-axis) reading above `Evolve`'s equilibrium section — the contract the other 4 cite. |
| **B-D5** | LOW | code (`OnBegin`) | **DECIDED** | Empty output-tags on a real recipe → neutral (~40 V) target; input-union kept only for the null debug sampler. Exact ternary in B-D5. |
| **C.2-d** | LOW | code (table, optional) | — | Broaden `ChExc["elemental"]` toward all six channels (or accept 2/6 + note). |
| **C.2-e** | LOW | code (table, optional) | — | Flip `solvent` base to `(0.98,-2,0.95,1.05)` so it dilutes/forgives, matching its wash `ChExc`. |
| **C.2-g** | LOW | code (table, optional) | — | Add Function/Output role keys to `TagVolatility` so output character reaches the target (or downgrade the claim — code currently does the latter). |
| **B-D8** | LOW | doc only | **DECIDED: opt out** | Alchemy is intentionally deterministic (comment on `AlchemyMinigame`). No sim RNG. Telegraphed-RNG is Refining/Engineering/Enchanting's job. Rejected surge alternative fully specced in B-D8 in case of reversal. |

Everything else (I2 heat-never-touches-V, I3 precedence/stacking, I4 target-from-output, I5 numeric-UI, and every
elemental-body/rider row NOT listed in §C.2) is **MATCH — preserve**. After B-D1/B-D3, re-confirm M5 (heat never directly
writes `vol`) still holds — both fixes were written to keep `vol` written by exactly one ease line.

**No open forks remain in this doc.** Both prior forks are resolved: B-D5 (neutral-target fallback) and B-D8 (opt out of
RNG) are DECIDED, not recommended. The five §C.2 items are either doc-only corrections (C.2-a, C.2-c, C.2-f) or have a
concrete code fix with a value (C.2-b MED, C.2-d/-e/-g LOW). A coder can implement every row above without a further
designer decision.

<!-- Excruciating implementation doc for Refining — "Impurity Folds". Written against
     docs/CRAFTING_MINIGAMES_MASTER_PLAN.md §2 (tag theme dictionary) + §3.3 (design spec) + §4 (11 sections).
     A coder should invent NOTHING. Every constant has a starting value; every drawn element has a rect,
     a colour source, a CraftFx primitive, and a z-order. -->

# Refining — "Impurity Folds" — Implementation Doc

**Discipline key:** `"refining"` · **Master plan section:** §3.3 · **Build order:** 1st (smallest new surface; proves the tag→pattern spine end-to-end).

**One-line:** A two-lane rhythm game. Beat the impurities out of the metal across successive **folds/gates**; each gate is a fixed
tag-determined pattern of 8–20 strikes on two lanes (**Click** + **Space**); a moving indicator crosses each strike's window; every
strike is graded **Perfect / Close / Okay / Miss**; the game **never stops**; accuracy is summed at the end; **each gate speeds the
tick up while the error window stays constant** (the only escalation dial, per the designer). Theme = removing impurities; a streak
bonus supplies the high ceiling.

**Designer-locked constraints (non-negotiable, §0 + §3.3 + §5 fork 3):**
- **Two lanes only** — Lane 0 = **Click** (left mouse), Lane 1 = **Space**. No 3rd lane ever (raise ceiling via tempo, not lanes).
- **Error window CONSTANT.** Escalation is PURELY the tick speeding up per gate. Never shrink the window with difficulty.
- **Fixed tag-determined pattern per gate.** Deterministic from ingredient tags + a seed (reproducible in tests, fresh per craft).
- **#folds from output tags + tier.**
- **8–20 strikes/gate.**
- **Per-strike grade Perfect / Close / Okay / Miss.**
- **Accuracy summed; the minigame NEVER stops** (no hard fail on a miss — misses just cost points + leave impurity).
- **Streak bonus** (consecutive perfect/close) supplies the high ceiling.

The seam is sacred: this overlay owns ONLY the play loop and produces `perf ∈ [0,1]` through `MinigameOverlay.Finish(perf)`
(or `FailCraft()` if the whole round is degenerate). `Game1.Core` is 0-diff.

> **This rebuild REPLACES the current `RefiningMinigame.cs` mechanic** ("The Lock" — a rotating-cylinder pick-timing game). The
> class name, discipline key, and seam are kept; the entire body (`_pins`, cylinder/pick/resonance/bind/ghost logic and all draws)
> is deleted and rewritten per this doc. Delete every field/method not named in §1 of this doc.

---

## 0. Fantasy & loop recap (context for the rest of the doc)

The refinery hammer folds raw stock over and over; each fold is a rhythmic beating pattern that drives out slag. The player keeps
the beat as the mechanism accelerates. Visible impurity drains as strikes land; the ingot brightens fold by fold; a clean run yields
a pure ingot (`perf ≈ 1.0`), a masher a slag-streaked one (`perf ≈ 0.25`).

**Loop:** Ready → (player starts) → for each of N gates: strikes scroll right-to-left down a horizontal **fold rail**; the player hits
the correct lane as each strike reaches the **hit line**; grade + score + impurity update per strike; between gates the tick speeds
up (a short breather beat) → after the last strike of the last gate, **Settle** (1.0 s summary flourish) → **Done** → `Finish(perf)`.

---

## 1. DATA MODEL

All types are nested in `RefiningMinigame : MinigameOverlay` unless noted. Units are stated per field. Godot `double` seconds, `float`
pixels, degrees only where noted.

### 1.1 RecipeContext fields READ (from `RecipeContext.cs`)

| Field | Type | Used for |
|-------|------|----------|
| `Recipe.OutputTags` | `List<string>` | Drives **#folds**, base tempo character, and the goal's "character" (via the tag table's OUTPUT column). |
| `Recipe.Tier` | `string` | A DIFFICULTY-TIER word (`common`/`uncommon`/`rare`/`epic`/`legendary`), NOT a number. Mapped to a 1..5 int `TierInt` (see below) → contributes to `#folds` and to grade magnitude. |
| `Recipe.Points` | `double` | **Ignored for hardness** — hardness comes from `DifficultyPoints` (see below). Read only for the F1 log header. |
| `Recipe.Inputs[]` | `List<Ingredient>` | Each ingredient's `.Tags` (ordered), `.Qty`, `.MaterialTier`, `.Name` → build the tag **pool** and the **per-gate pattern**. |
| `Recipe.OutputId` | `string` | F1 log header only. |

`Ingredient` = `{ string Id, string Name, List<string> Tags (ordered, precedence = list order), int Qty, int MaterialTier }`.

**`TierInt` mapping (the string→int parse, CONCRETE — do not invent).** `Recipe.Tier` is one of the five DifficultyTier words, mirroring the
base overlay's private `TierStars` (§MinigameOverlay.TierStars). Refining computes `TierInt` locally with the same table (the base one is
private, so we DON'T call it — we duplicate the 5-entry switch, zero shared-code churn):

```csharp
private static int TierIntOf(string tier) => tier switch
{
    "common"    => 1,
    "uncommon"  => 2,
    "rare"      => 3,
    "epic"      => 4,
    "legendary" => 5,
    _           => 1,          // unknown/empty → treat as common
};
// TierInt = TierIntOf(Recipe?.Tier ?? DifficultyTier);   // 1..5
```

`TierInt ∈ 1..5`. (The `#folds` clamp caps at 9, so the top-tier count is still bounded — §4.1.) `Ingredient.MaterialTier` is already a 1..4 int
(a *material* tier, distinct from the recipe DIFFICULTY tier above) and is passed straight to `MinigameTagEffects.Brew` unchanged.

**Null-recipe degrade (debug launch).** If `Recipe == null`, `OnBegin` synthesises a plausible recipe: `OutputTags = {"refined","metal"}`,
`Tier = DifficultyTier`, and **one** synthetic ingredient `{ Tags = SampleTagsFromTier(TierInt), Qty = 1, MaterialTier = min(TierInt,4) }`.
`SampleTagsFromTier` is a FIXED 5-row table (indexed by `TierInt`), so debug launches are deterministic and cover the theme spread — a coder
transcribes it verbatim, inventing nothing:

```csharp
private static readonly string[][] DebugTierTags =
{
    /* [0] unused */ new[] { "iron", "common" },
    /* T1 */         new[] { "iron", "hard", "common" },
    /* T2 */         new[] { "steel", "strong", "uncommon" },
    /* T3 */         new[] { "mithril", "sharp", "rare" },
    /* T4 */         new[] { "adamantine", "dense", "epic" },
    /* T5 */         new[] { "orichalcum", "arcane", "legendary" },
};
private static string[] SampleTagsFromTier(int tierInt) => DebugTierTags[Math.Clamp(tierInt, 1, 5)];
```

### 1.2 From `MinigameOverlay` base (inherited, do not redeclare)

`DifficultyPoints` (double, certified `DifficultyCalculator` points, expected range ~1..80), `DifficultyTier` (string: common/uncommon/
rare/epic/legendary), `Recipe` (`RecipeContext?`), `Accent` (Color, = refining accent `(0.98,0.78,0.42)`), plus the feedback helpers
`SetQuality/FlashQuality/Shake/SetTimer/HideTimer/SetHeaderSub/Popup/Burst/Finish/FailCraft`.

### 1.3 Enums

```csharp
private enum Lane { Click = 0, Space = 1 }               // TWO lanes only (locked)

private enum Grade { Miss = 0, Okay = 1, Close = 2, Perfect = 3 }   // per-strike verdict

private enum Phase { Ready, Play, Settle, Done }          // state machine (§3)
```

`Grade` doubles as an index into the scoring/colour tables (§4.6, §6). `Miss=0` so a missed/skipped strike is the array default.

### 1.4 Structs / classes

```csharp
/// One scheduled strike on the fold rail. Immutable after gate build except Result/Judged.
private sealed class Strike
{
    public Lane Lane;            // which lane the player must hit
    public double Beat;          // scheduled hit time in BEATS from the gate's start (>=0, monotonic non-decreasing)
    public bool DoubleTap;       // sharp-tag: a tight second tap follows (rendered as a paired glyph); see §2/§4
    public Grade Result;         // filled when judged (default Miss)
    public bool Judged;          // set true once scored (hit or auto-missed by passing the window)
    public double HitAtBeat = -1;// beat at which the player actually pressed (for the F1 log; -1 = never)
}

/// One gate/fold. Built once at gate-entry from the tag pattern; tempo baked in.
private sealed class Gate
{
    public int Index;                       // 0-based
    public List<Strike> Strikes = new();    // 8..20, ordered by Beat
    public double BeatsPerSecond;           // TEMPO for this gate (see §4.2). Increases per gate.
    public string PatternName = "";         // theme label for the HUD + log (e.g. "Ember Burst", "Anvil Steady")
    public Color LaneTint;                  // gate's theme colour (from the dominant pool theme), used to tint the rail
    public bool TempoDip;                   // temporal rider (§2.3/§4.2): this gate slows then snaps back
    public double AvgGap = 1.0;             // mean beat-gap between consecutive strikes (cached at build; used by the TempoDip ease, §4.2)
}
```

### 1.5 Runtime play state (fields on the overlay)

| Field | Type | Units / range | Meaning |
|-------|------|---------------|---------|
| `_gates` | `List<Gate>` | N = 2..9 | All gates, prebuilt in `OnBegin` (deterministic). |
| `_gateIdx` | `int` | 0..N | Current gate index (== N means all done). |
| `_gate` | `Gate` | — | `_gates[_gateIdx]` cached. |
| `_gateClock` | `double` | seconds ≥ 0 | Time since current gate started scrolling. |
| `_gateBeat` | `double` | beats ≥ 0 | `_gateClock * _gate.BeatsPerSecond` (the rail's scroll position, in beats). |
| `_gateBeatPrev` | `double` | beats ≥ 0 | Previous frame's `_gateBeat`; used to detect integer-beat crossings for the `PlayBeatTick` audio hook (§9 roadblock 4). |
| `_gateForgaveMiss` | `bool` | — | Per-gate flag: set once when WATER's forgive-first-Miss rider fires (§2.3/§4.5); reset in `EnterGate`. |
| `_nextStrike` | `int` | 0.._gate.Strikes.Count | Index of the earliest not-yet-judged strike (advances as strikes pass). |
| `_pool` | `Dictionary<string,int>` | — | Stacking tag counts across all ingredients (built once, §2.4). |
| `_profile` | `RefiningProfile` | — | Folded modifier profile (§2.5). |
| `_seed` | `ulong` | — | Deterministic RNG state (seed source §8). |
| `_score` | `double` | ≥ 0 | Σ strike points earned so far. |
| `_scoreMax` | `double` | > 0 | Σ max possible points (Perfect on every strike, no streak) — the denominator. |
| `_streak` | `int` | ≥ 0 | Consecutive Perfect-or-Close count. |
| `_maxStreak` | `int` | ≥ 0 | Best streak (F1 log). |
| `_impurity` | `double` | 0..1 | Visible impurity fraction remaining (1 = raw, 0 = pure). Drains on good hits, bumps on misses. |
| `_purity` | `double` | 0..1 | `1 - _impurity` (the ingot brightness driver; derived, cached for draw). |
| `_settleT` | `double` | seconds | Countdown in `Settle` phase (starts `SettleDur`). |
| `_anim` | `double` | seconds | Free-running clock for idle animation (breathing, sparkles). |
| `_phase` | `Phase` | — | State machine. |
| `_flashLane` | `double[2]` | 0..1 each | Per-lane hit-line flash decay (lane pulses white on a good hit). |
| `_lastGradeCol` | `Color` | — | Colour of the last verdict (for the combo glow). |
| `_sharpInPool` | `bool` | — | Set in `ApplyRiders` if `sharp` in the pool → per-strike Perfect-points bonus (§4.5/§4.6). |
| `_temporalInPool` | `bool` | — | Set in `ApplyRiders` if `temporal` in the pool → per-gate `TempoDip` selection in `EnterGate`. |
| `_toxicInPool` | `bool` | — | Set in `ApplyRiders` if any toxic-family tag (`poison`/`venom`/`toxic`/`acid`) in the pool → the **corrupt gate**: impurity LEAKS back over time across every gate (`ImpLeakPerBeat`, §4.5a). This is toxic's "degrade-over-time" expression, matching Smithing's `POISON_DOT` verb — toxic is not merely a higher one-shot `Vol` swing. |
| `_patternJitter` | `double` | 0.15..0.45 | Per-strike gap-jitter amplitude. Reset to `0.15` at the top of `OnBegin` (before the ingredient `BuildProfile` call), then `ApplyRiders` bumps it +0.15 for chaos/dangerous (capped 0.45). The `_outProfile` build does NOT touch it (its riders are ignored). §4.1/§8. |
| `_gradeInit` | `double` | 0..1 | `MinigameTagEffects.Grade(all pool tags)` cached at `OnBegin` — the recipe's quality grade, used to seed `_impurity` (§3 Ready row). |
| `_dev` | `MinigameDevLog` | — | Shared F1/F7 harness (composition). |

**Derived / difficulty-interpolated params** (set once in `OnBegin`, see §4 + §7): `_bps0` (double, gate-0 tempo, beats/s),
`_tempoRamp` (double, per-gate multiplicative tempo bump), `_windowSec` (double, CONSTANT ± error window in seconds), `_closeFrac`,
`_okayFrac` (double, window sub-band fractions), `_nFolds` (int).

### 1.6 UI node fields

| Field | Type | Role |
|-------|------|------|
| `_rail` | `Control` | The play surface (draws the fold rail, ingot, strikes, HUD). `_rail.Draw += DrawRail`. Fixed `CustomMinimumSize` (see §6.1). |
| `_readyBox` | `VBoxContainer` | Holds the ready-state instructions + BEGIN button; hidden on start. |
| `_readyLabel` | `Label` | Instruction text. |
| `_beginBtn` | `Button` | "BEGIN FOLDING ▸ [Space]". |
| `_hint` | `Label` | Persistent lane legend under the rail. |

---

## 2. TAG TABLE — the complete `tag → knob` mapping (authored against §2 of the plan)

**The knobs Refining exposes** (all per-gate character, NOT raw hardness — hardness is `DifficultyPoints` only, §1.4/§7):

| Knob | Symbol | Range | What it does |
|------|--------|-------|--------------|
| **Density** | `Dens` | 0.6 .. 1.6 | Strikes-per-beat packing. High = fast dense bursts (more strikes, shorter beat gaps). Low = sparse heavy hits. |
| **Lane bias** | `LaneBias` | -1 .. +1 | -1 all Click, +1 all Space, 0 even. Shapes which lane dominates the pattern. |
| **Interleave** | `Inter` | 0 .. 1 | Probability a consecutive pair alternates lanes (two-lane weaving) vs. repeats a lane. |
| **DoubleTap** | `Dbl` | 0 .. 0.6 | Probability a strike is a tight double-tap (sharp precision rider). |
| **Impurity load** | `Imp` | 0.5 .. 1.4 | Starting `_impurity` multiplier (shadow/toxic = more slag to clear; pure/refined = less). |
| **Reward richness** | `Rich` | 0.9 .. 1.25 | Quality/grade payoff multiplier on the streak bonus ceiling (more upside for cleaner runs). |

These are stored on a discipline-specific `RefiningProfile : MinigameModifierCommon.ModProfile` (§2.5). The mapping from the shared
`ModProfile` fields to Refining's knobs (so the SAME `Fold`/`StackFactor`/`Clamp` engine drives them):

- `ModProfile.Rx` (reaction vigor ×) → **Dens** driver (fire/air raise Rx → denser; ice/earth lower it → sparser). `Dens = clamp(Rx, 0.6, 1.6)`.
- `ModProfile.Vol` (volatility ±) → **Dbl / risk** driver (a volatile pool adds double-taps and bumps `Imp`). `Dbl = clamp(0.12 + Vol/60, 0, 0.6)`, `Imp += clamp(Vol/40, -0.4, 0.4)`.
- `ModProfile.Pot` (potency/magnitude ×) → **Rich** (grade magnitude → richer reward ceiling). `Rich = clamp(0.75 + 0.35*Pot, 0.9, 1.25)`.
- `ModProfile.Time` (deliberation ×) → **inverse of Dens fine-tune**: ice/earth's high `Time` further sparsens: `Dens *= clamp(2 - Time, 0.7, 1.2)`.
- `LaneBias` / `Inter` are computed directly from the **dominant pool theme** (§2.3 table), not from `ModProfile` (they are structural, not magnitude).

### 2.1 Theme resolution (obey §2.1 — a tag means the same THING everywhere) — NO private-member access

Refining resolves themes through **two PUBLIC entry points only**, never a private toolkit member:

1. **Pool-dominant channel (the STRUCTURAL spine).** `MinigameTagEffects.Brew(tags, tier, qty)` (PUBLIC) already resolves each tag —
   including every `Metal`/`Wood` member — to one of the six channels internally, and returns the 6-channel essence vector; we sum it across
   ingredients and call `MinigameTagEffects.Dominant(poolEssence)` (PUBLIC) to get the pool's dominant channel `0..5`. This is the ONLY source
   for §2.3's `LaneBias`/`Inter`/`LaneTint`/`PatternName`. It works for **any** tag: an all-metal pool folds to TERRA, a fire pool to HEAT, etc.,
   with the toolkit's own internal `Resolve` doing the per-tag→channel step out of our reach — we never call it directly.
2. **Per-tag knob delta (the MAGNITUDE contribution).** Refining's OWN `KnobTable` (§2.2, a `Dictionary` we declare) feeds
   `MinigameModifierCommon.Fold` (PUBLIC). A tag with a row contributes its `(Pot,Vol,Time,Rx)`; a tag with **no** row is handled by the
   theme-default fallback below.

> **IMPORTANT — the review's "hallucinated API" fix.** `MinigameTagEffects.Resolve`, `.Tags`, `.Metal`, `.Wood`, and `.QualityGrade` are all
> `private static` and MUST NOT be referenced by Refining (they will not compile and editing the shared toolkit is out of scope, §11.3). Every
> place an earlier draft "resolved a tag to its channel" is replaced by (a) the pool-dominant `Brew`/`Dominant` path for structure, or (b) a
> **Refining-local** channel lookup `RefChannelOf(tag)` for the KnobTable theme-default fallback. `RefChannelOf` is a small `private static`
> dictionary declared INSIDE `RefiningMinigame` (§2.2a) — it duplicates just the tag→channel mapping we need, so Refining is self-contained and
> the shared file is 0-diff.

**We author the base table below by looking each tag up in §2.1 first**, so fire is always haste/aggression, ice always control/deliberation, etc.

**Manifestation row (from §2.2, the Refining column) — the fixed law:**

| Theme (verb) | Refining manifestation (the ONE consistent expression) |
|--------------|--------------------------------------------------------|
| **FIRE** — haste/aggression/volatility | **Faster / denser** strike pattern; more pressure per gate. → high `Dens`, +`Dbl`, +`Imp`. |
| **WATER** — flow/cleanse/dilute | Cleaner/forgiving pattern; **washes impurity** (lowers `Imp`, mild `Dens`) **AND recovers a missed impurity**: when WATER is the dominant theme, the FIRST Miss of each gate does NOT add slag (the forgiving "recovers a missed impurity" behaviour from plan §2.2) — see the `WaterForgive` rider below. |
| **COLD/ICE** — control/deliberation/stability | Slower, wider-feeling cadence — **fewer strikes, each heavier** (low `Dens`, low `Inter`, low `Dbl`). |
| **EARTH** — solidity/resistance/mass | Steady metronomic gate; **high floor, low ceiling** (low `Dens`, **strongly ONE-LANE** via `\|LaneBias\|` high — see below, `Inter→0`, low `Dbl`). |
| **LIFE** — growth/vitality/spread | Adds an extra fold / regrowing impurity (mild +`Imp`, mild +strikes). |
| **SHADOW** — entropy/risk/hidden power | Corrupt gate (tricky/**hidden** pattern) — risk expressed via a **seed-signed hidden lane** + **regrowing/leaking impurity** (the `corrupt` gate, §4.5a), **big risk/reward** (+`Dbl`, +`Imp`, +`Rich`); **moderate `Inter` (RISK, not SPEED)** — a shadow gate is NOT the fastest-alternating (Enchanting parity, §2.3). |
| **AIR** — speed/lightness/evasion | Quick light strikes; **disperses impurity** (high `Dens`, and **LOW `Imp`** — the KnobTable gives air NEGATIVE `Vol` so `Imp` drops, fast yet clean). |
| **Quality/Grade** (magnitude) | More folds / cleaner reward → +`Rich`, −`Imp`. |
| **sharp** (precision rider) | Tighter perfect-window VALUE (not width — window is constant): +`Dbl` and a Perfect-points bonus (§4.6). |
| **temporal** (time control) | A per-gate TEMPO rider ONLY — it does **not** change `Dens`/structure; the gate's tempo dips to ×0.8 for its first 40% of beats then eases back to ×1.0 (§4.2). Its KnobTable row still lowers density like other slow tags, but the "slows then snaps back" *feel* is the tempo ease layered on top, not a second density change. |
| **chaos/dangerous** (risk×) | A randomised gate variant (BOUNDED): +`Dbl`, +`Inter`, higher pattern-RNG amplitude (still telegraphed). |

> **Consistency guard (from §2):** if any line here reads "fire calms Refining" or "ice speeds it up," it is WRONG. It doesn't.

### 2.2 Base knob table (the full material vocabulary; every tag has an entry or a theme default)

Format per row: `tag → (Pot, Vol, Time, Rx)` — the SAME 4-tuple `MinigameModifierCommon.Fold` consumes, so we plug into the shared
engine with ZERO new mechanism. Values chosen to obey the manifestation row above. (These are Refining's own numbers; they are NOT
Alchemy's `ModTable` — but they are THEME-consistent with how Alchemy reads each tag: e.g. Alchemy's `chaos` = high vol / low time /
high rx; ours is the same shape.)

**Theme-default fallback (the "never a no-op" guarantee — CONCRETE resolution).** A tag with no explicit `KnobTable` row is folded using its
theme's default 4-tuple, looked up via Refining's OWN `RefChannelOf(tag)` (§2.1 note / §2.2a) — NOT via the private `Resolve`. The seven
theme-default rows are:

| Channel | Default `(Pot,Vol,Time,Rx)` | Rationale |
|---------|-----------------------------|-----------|
| FIRE / HEAT  | `(1.05, +10, 0.85, 1.35)` | dense, +double, +impurity |
| WATER / AQUA | `(1.00, -4,  1.15, 0.95)` | cleaner, lowers impurity |
| ICE (AQUA-still)† | `(1.00, -6,  1.25, 0.70)` | sparse/heavy, slow |
| EARTH / TERRA | `(1.00, -4,  1.25, 0.80)` | steady metronome |
| LIFE / GROVE | `(1.04, +2,  1.05, 1.05)` | mild growth/impurity |
| SHADOW / UMBRA | `(1.05, +6,  1.00, 1.05)` | corrupt, risk/reward |
| AIR / WIND | `(1.00, **-3**, 0.75, 1.25)` | **NEGATIVE Vol** → LOW Imp, fast yet clean (obeys the AIR manifestation) |

†Ice/frost share the AQUA channel with water; `RefChannelOf` returns AQUA for both, so an *unlisted* ice-family tag falls to the WATER default.
Every ice/frost/frozen/chill tag we care about has an EXPLICIT sparse row in §2.2 (the COLD block), so the ice feel never depends on the fallback.
**How a coder folds an unlisted tag:** if `KnobTable` has no row, look up `RefChannelOf(tag)`; if that returns a channel, inject the channel's
default row into the fold as though it were `KnobTable[tag]`; if `RefChannelOf` ALSO returns null (a pure modifier like `quality` with no
elemental body), the tag contributes to `_pool` counts and `#folds` character but no channel delta — and that is CORRECT, because pure quality/
physical modifiers are magnitude riders, not structural themes (see §2.2b for exactly which knobs each such tag DOES touch, so it is still never a
true no-op). This resolves the review's "conflates the two paths" gap: the DOMINANT-theme path (Brew/Dominant) and the KNOB-delta path
(KnobTable + RefChannelOf default) are now spelled out separately.

```
// ---------- FIRE / HEAT (haste + aggression + volatility → dense, +double, +impurity) ----------
// chaos/lightning/storm/radiant/light are HEAT-channel RIDERS, not BODIES. Their rows below give fire-adjacent
// MAGNITUDE (Vol/Rx) via Fold, but they are EXCLUDED from RefChannelOf (§2.2a) so they do NOT drive the structural
// Dominant() channel — a pure-radiant or pure-chaos ingredient therefore does NOT read as a FIRE-structured gate
// (Alchemy's C.2-a "riders first" canon: a rider colours magnitude but never claims the body theme by itself).
// The #folds "+1 for chaos" trigger (§4.1) keys off the tag NAME present in _pool, never off Dominant() — correct,
// because chaos no longer contributes a HEAT channel at all.
fire      (1.05, +10, 0.85, 1.40)   flame    (1.04, +9,  0.90, 1.35)   ember    (1.02, +6,  0.92, 1.25)
molten    (1.05, +11, 0.82, 1.42)   forge    (1.03, +5,  0.92, 1.22)   volcanic (1.06, +12, 0.80, 1.45)
lightning (1.04, +12, 0.72, 1.50)   storm    (1.04, +9,  0.78, 1.35)   radiant  (1.04, +4,  0.95, 1.15)
chaos     (1.02, +16, 0.68, 1.55)   light    (1.03, -2,  0.98, 1.10)

// ---------- WATER (flow + cleanse + dilute → cleaner, lowers impurity) ----------
water     (1.00, -5,  1.12, 0.95)   aqua     (1.00, -5,  1.12, 0.95)   liquid   (1.00, -4,  1.10, 0.95)
solvent   (0.98, -3,  1.05, 1.05)

// ---------- COLD / ICE (control + deliberation + stability → sparse/heavy, slow) ----------
ice       (1.00, -7,  1.28, 0.70)   frost    (1.00, -6,  1.22, 0.74)   frozen   (1.00, -8,  1.32, 0.66)
chill     (1.00, -5,  1.15, 0.80)

// ---------- EARTH / TERRA + structural metals (solidity + mass → steady metronome, high floor) ----------
earth     (1.00, -5,  1.25, 0.78)   stone    (1.00, -6,  1.28, 0.75)   sand     (1.00, -3,  1.10, 0.92)
mineral   (1.00, -4,  1.22, 0.80)   crystal  (1.05, -4,  1.20, 0.82)   gem      (1.06, -3,  1.18, 0.84)
metal     (1.02, -4,  1.20, 0.82)   metallic (1.04, -2,  1.05, 0.95)   iron     (1.02, -4,  1.22, 0.80)
steel     (1.05, -4,  1.20, 0.82)   bronze   (1.03, -3,  1.20, 0.82)   copper   (1.02, -3,  1.18, 0.84)
tin       (1.01, -3,  1.16, 0.86)   alloy    (1.10, -3,  1.10, 0.92)   silver   (1.06, -2,  1.14, 0.88)
gold      (1.08, -2,  1.12, 0.90)   mithril  (1.14, -2,  1.10, 0.98)   adamantine (1.18,-4, 1.24, 0.86)
orichalcum(1.16, +2,  1.10, 1.02)

// ---------- LIFE / GROVE + feral (growth + spread → extra fold, mild impurity) ----------
wood      (1.00, -2,  1.08, 1.00)   oak      (1.00, -2,  1.08, 1.00)   ash      (1.01, -1,  1.05, 1.02)
ironwood  (1.05, -2,  1.10, 1.00)   ebony    (1.04, -2,  1.10, 0.98)   birch    (1.00, -1,  1.05, 1.02)
willow    (1.00, -2,  1.06, 1.02)   worldtree(1.10, 0,   1.08, 1.05)   exotic   (1.08, +2,  1.02, 1.08)
plant     (1.02, -1,  1.02, 1.02)   herb     (1.03, -2,  1.02, 1.03)   living   (1.04, +1,  1.00, 1.05)
leather   (1.00, -2,  1.08, 0.94)   monster  (1.05, +4,  0.98, 1.08)   fang     (1.05, +5,  0.94, 1.10)
scales    (1.03, -2,  1.06, 0.96)   bone     (1.02, -3,  1.10, 0.90)   gel      (0.98, -1,  1.04, 0.98)
carapace  (1.04, -4,  1.10, 0.90)   blood    (1.06, +6,  0.92, 1.18)

// ---------- SHADOW / UMBRA + toxic + mystic (entropy + risk + hidden power → corrupt, big risk/reward) ----------
// TOXIC (poison/venom/toxic/acid) additionally triggers the DEGRADE-OVER-TIME "corrupt gate" (§4.5a): impurity leaks
// back across the whole gate, so toxic reads as an active ticking hazard (matches Smithing's POISON_DOT verb), not just
// the one-shot +Vol impurity swing these rows already give.
void      (1.06, +7,  1.05, 0.95)   dark     (1.03, +5,  1.02, 0.95)   shadow   (1.04, +4,  1.00, 1.00)
spectral  (0.95, +5,  1.20, 0.88)   poison   (1.08, +6,  0.98, 1.12)   venom    (1.08, +6,  0.96, 1.12)
toxic     (1.08, +6,  1.00, 1.12)   acid     (1.06, +7,  0.92, 1.28)   arcane   (1.16, +2,  1.05, 1.00)
magical   (1.12, +2,  1.02, 1.02)   essence  (1.14, +4,  1.02, 1.05)

// ---------- AIR / WIND (speed + lightness + DISPERSAL → quick light strikes, LOW impurity) ----------
// NOTE: air's whole theme is "disperses/cleans impurity" — so Vol is NEGATIVE here (Imp = clamp(1 + Vol/40) drops).
// High Dens comes from the high Rx (1.22-1.28), NOT from Vol. This is the fix for the review's "numbers add impurity" contradiction.
air       (1.00, -3,  0.75, 1.28)   wind     (1.00, -3,  0.76, 1.24)   vapor    (1.00, -2,  0.78, 1.18)
gas       (1.00, -2,  0.74, 1.24)

// ---------- QUALITY / GRADE (magnitude → +Rich, −Imp; increasing returns) ----------
// These are ITEM/MATERIAL metadata TAGS (from a material's or output's tag list), NOT the RecipeContext.Tier
// DIFFICULTY word (which is parsed separately into TierInt, §1.1). A tag like `epic`/`fine`/`pure` may or may not
// appear on a given refining output; when present it folds into Pot→Rich (reward richness). No overlap with TierInt.
starter   (0.88, +3,  1.05, 0.92)   basic    (0.92, +2,  1.02, 0.98)   common   (0.95, +1,  1.00, 1.00)
standard  (1.00, 0,   1.02, 0.98)   uncommon (1.05, -1,  1.02, 1.02)   fine     (1.08, -2,  1.02, 1.02)
quality   (1.11, -3,  1.04, 1.00)   refined  (1.13, -5,  1.04, 0.98)   rare     (1.16, -5,  1.02, 1.02)
advanced  (1.19, -6,  1.00, 1.04)   epic     (1.22, -7,  1.02, 1.02)   precious (1.22, -8,  1.06, 0.98)
legendary (1.28, -9,  1.02, 1.02)   mythical (1.32, -11, 1.04, 1.00)   ancient  (1.25, -10, 1.20, 0.82)
superior  (1.14, -4,  1.02, 1.00)   pure     (1.10, -12, 1.02, 0.98)   holy     (1.15, -4,  1.02, 1.02)
mundane   (0.86, 0,   1.00, 0.90)   material (1.00, -1,  1.04, 0.96)   elemental(1.10, +5,  0.92, 1.18)

// ---------- PHYSICAL / STRUCTURAL ----------
durable   (1.00, -3,  1.18, 0.90)   strong   (1.10, -2,  1.02, 1.08)   hard     (1.00, -5,  1.10, 0.90)
solid     (1.00, -7,  1.22, 0.76)   dense    (1.00, -6,  1.26, 0.72)   heavy    (1.00, -4,  1.26, 0.76)
sharp     (1.05, +3,  0.86, 1.24)   layered  (1.00, -2,  1.24, 0.86)   flexible (1.00, -3,  1.16, 0.96)
versatile (1.05, -1,  1.02, 1.04)   memory   (1.05, -3,  1.14, 0.96)

// ---------- ENERGY / EXOTIC ----------
temporal  (1.10, -6,  1.35, 0.72)   quantum  (1.00, +4,  0.92, 1.14)   impossible(1.20,+6,  1.04, 1.10)
dangerous (1.10, +12, 0.76, 1.44)   harmony  (1.10, -8,  1.12, 0.90)   power    (1.24, +3,  1.04, 1.14)

// ---------- FUNCTION / OUTPUT (mostly on OUTPUT tags → set the GOAL character; light per-ingredient effect) ----------
weapon    (1.08, +4,  0.94, 1.14)   combat   (1.06, +5,  0.92, 1.18)   explosive(1.10, +14, 0.72, 1.48)
armor     (1.04, -8,  1.22, 0.82)   protection(1.05,-8,  1.20, 0.84)   defense  (1.02, -8,  1.18, 0.84)
resistance(1.00, -7,  1.14, 0.90)   tool     (1.03, -5,  1.18, 0.86)   utility  (1.00, -2,  1.04, 0.96)
healing   (1.05, -6,  1.10, 0.86)   regeneration(1.05,-6, 1.30, 0.78)  buff     (1.10, +2,  0.96, 1.10)
enhancement(1.12,-3,  1.04, 1.00)   strength (1.15, +3,  0.96, 1.10)   agility  (1.04, +3,  0.82, 1.20)
speed     (1.05, +4,  0.72, 1.30)   potion   (1.02, -2,  1.04, 0.96)   consumable(1.00,-3,  1.04, 0.96)
crafting  (1.02, -4,  1.14, 0.90)   engineering(1.04,-6, 1.18, 0.86)   fishing  (1.00, -4,  1.14, 0.86)
```

### 2.2a `RefChannelOf` — Refining's OWN tag→channel map (for the theme-default fallback; replaces private `Resolve`)

A `private static readonly Dictionary<string,int>` declared inside `RefiningMinigame`, mapping each ELEMENTAL-bodied tag to its channel
constant (`MinigameTagEffects.HEAT/AQUA/TERRA/GROVE/UMBRA/AIR` — those constants ARE public). It exists so an unlisted elemental tag still
folds to its theme default (§2.2) WITHOUT touching the private `MinigameTagEffects.Resolve`/`.Metal`/`.Wood`. Metals fold to TERRA, woods to
GROVE, exactly mirroring the toolkit's private sets — we transcribe just the membership we need:

```csharp
using static Game1.Godot.MinigameTagEffects;   // for HEAT/AQUA/TERRA/GROVE/UMBRA/AIR (public consts)

private static readonly Dictionary<string,int> RefChannelOf = new()
{
    // FIRE/HEAT — BODY tags only (they drive the structural Dominant() channel).
    // NOTE: lightning/storm/radiant/light/chaos are DELIBERATELY ABSENT here (they are HEAT-channel
    // *riders*, not bodies — §2.2a-rider note). They keep their §2.2 KnobTable numeric rows for
    // fire-adjacent magnitude, but must NOT contribute a structural HEAT channel, so a pure-radiant or
    // pure-chaos ingredient does not read as a FIRE-structured gate (Alchemy C.2-a "riders first" canon).
    ["fire"]=HEAT,["flame"]=HEAT,["ember"]=HEAT,["molten"]=HEAT,["forge"]=HEAT,["volcanic"]=HEAT,
    // WATER + ICE (all AQUA — ice is the still pole of water)
    ["water"]=AQUA,["aqua"]=AQUA,["liquid"]=AQUA,["solvent"]=AQUA,["ice"]=AQUA,["frost"]=AQUA,["frozen"]=AQUA,["chill"]=AQUA,
    // EARTH + structural metals
    ["earth"]=TERRA,["stone"]=TERRA,["sand"]=TERRA,["mineral"]=TERRA,["crystal"]=TERRA,["gem"]=TERRA,
    ["metal"]=TERRA,["metallic"]=TERRA,["iron"]=TERRA,["steel"]=TERRA,["bronze"]=TERRA,["copper"]=TERRA,["tin"]=TERRA,
    ["alloy"]=TERRA,["silver"]=TERRA,["gold"]=TERRA,["mithril"]=TERRA,["adamantine"]=TERRA,["orichalcum"]=TERRA,
    // LIFE + woods + feral
    ["wood"]=GROVE,["oak"]=GROVE,["ash"]=GROVE,["ironwood"]=GROVE,["ebony"]=GROVE,["birch"]=GROVE,["willow"]=GROVE,["worldtree"]=GROVE,["exotic"]=GROVE,
    ["plant"]=GROVE,["herb"]=GROVE,["living"]=GROVE,["leather"]=GROVE,["monster"]=GROVE,["fang"]=GROVE,["scales"]=GROVE,["bone"]=GROVE,["gel"]=GROVE,["carapace"]=GROVE,["blood"]=GROVE,
    // SHADOW + toxic + mystic
    ["void"]=UMBRA,["dark"]=UMBRA,["shadow"]=UMBRA,["spectral"]=UMBRA,["poison"]=UMBRA,["venom"]=UMBRA,["toxic"]=UMBRA,["acid"]=UMBRA,["arcane"]=UMBRA,["magical"]=UMBRA,["essence"]=UMBRA,
    // AIR
    ["air"]=AIR,["wind"]=AIR,["vapor"]=AIR,["gas"]=AIR,
};
// int? ch = RefChannelOf.TryGetValue(tag, out var c) ? c : (int?)null;   // null => rider/modifier (no BODY channel)
```

**FIRE-rider note (Alchemy C.2-a parity).** `lightning`/`storm`/`radiant`/`light`/`chaos` are intentionally NOT in `RefChannelOf`: they are
HEAT-channel *riders*, not bodies. They keep their §2.2 KnobTable rows (so they still fold their fire-adjacent Vol/Rx magnitude via `Fold`), but
they contribute NO structural channel here — so `Dominant()` never resolves a pure-rider ingredient to FIRE, and a pure-radiant or pure-chaos
ingredient does not gate as a FIRE-structured fold. This mirrors Alchemy's "riders first" canon (a rider colours magnitude; a body claims the
theme). Because `Brew`/`Dominant` (the STRUCTURAL path, §2.1) does its own internal per-tag channel resolution out of our reach, these riders
may still nudge the toolkit's essence vector there; `RefChannelOf` governs ONLY Refining's own theme-default FALLBACK, and that is where the
rider exclusion is enforced — the KnobTable magnitude is preserved either way.

The seven theme-default rows (§2.2 table) are indexed by this channel constant. Every ELEMENTAL-BODY tag in `MinigameTagEffects.Tags` + `Metal`
+ `Wood` has either an explicit §2.2 row OR a `RefChannelOf` entry (so a channel default) — **no elemental body tag is ever a structural
no-op**. Pure modifiers AND the fire-adjacent riders above (`lightning`/`storm`/`radiant`/`light`/`chaos`, plus `quality`, `physical`,
`function`, `energy/exotic` words with no elemental body) intentionally return null here and are covered by
§2.2b instead.

### 2.2b Pure-modifier coverage — the knob every non-elemental tag DOES move (so it is never a true no-op)

The review's "some tags are a no-op for structure" concern: pure modifier tags (they have a §2.2 KnobTable row but `RefChannelOf` returns
null) do NOT shift the DOMINANT theme (LaneBias/Inter/LaneTint/PatternName) — that is correct, because they are magnitude/quality riders, not
themes. But they are never a no-op: their KnobTable row still feeds `Fold`, which moves the numeric knobs, AND several are explicit §2.3 riders.
This table states, per modifier FAMILY, exactly which knob(s) they touch:

| Modifier family (examples) | Structural (LaneBias/Inter/LaneTint)? | Numeric knobs moved (via `Fold` + §2.3 riders) |
|----------------------------|---------------------------------------|-----------------------------------------------|
| **Quality/Grade** (`common`…`legendary`, `pure`, `holy`, `superior`, `mundane`, `material`, `epic`) | No (not a theme) | `Rich` ↑ (via `Pot`), `Imp` ↓ (via negative `Vol`); `#folds` +0 (grade already in TierInt). The **richness/cleanliness** dial. |
| **Physical/Structural** (`durable`,`strong`,`hard`,`solid`,`dense`,`heavy`,`layered`,`flexible`,`versatile`,`memory`) | No | `Dens` ↓ (high `Time`, low `Rx`) → sparser/heavier gate; **`sharp`** → §2.3 rider `Dbl += 0.15` + Perfect-points flag; **`layered`** → §2.3 rider `Inter += 0.20`. |
| **Energy/Exotic** (`temporal`,`quantum`,`impossible`,`dangerous`,`harmony`,`power`) | No | `temporal` → §2.3 rider `TempoDip` on ~half gates; `dangerous` → §2.3 rider `Inter += 0.15`, `_patternJitter += 0.15`, `Dbl += 0.10`; `quantum/impossible/power` → `Rich`↑/`Dbl`↑ via `Pot`/`Vol`; `harmony` → `Imp` ↓ (calming). |
| **Function/Output** (`weapon`,`armor`,`healing`,`speed`,`strength`,…) | No (per-ingredient light; they mainly shape the OUTPUT profile → `#folds` + `Rich`, §2.4) | On an INGREDIENT: `Dens`/`Imp` nudge via their row (e.g. `weapon` +Vol → +Imp; `armor` −Vol → −Imp). On an OUTPUT tag: fold into `_outProfile` → `#folds` character + `Rich` only. |

So the resolution is unambiguous: **elemental tags** shape structure (via Brew/Dominant) AND magnitude (via KnobTable); **modifier tags**
shape only magnitude and the named §2.3 riders — every tag moves at least one knob.

### 2.3 Structural exceptions (LaneBias + Inter, computed from the DOMINANT pool theme, NOT from ModProfile)

After folding, resolve the pool's **dominant elemental channel** with `MinigameTagEffects.Dominant(poolEssence)` (see §2.4), and set
`LaneBias`/`Inter` from this table. These are STRUCTURE, so they read off the theme directly (obeys §2.2):

| Dominant theme | `LaneBias` | `Inter` | Feel (matches §2.2 Refining column) |
|----------------|-----------|---------|-------------------------------------|
| FIRE  | +0.15 (slight Space lean, urgent) | 0.55 | dense weaving bursts |
| WATER | 0.0 (even) | 0.35 | clean, forgiving |
| ICE   | 0.0 (even) | 0.15 | fewer, heavier — rarely alternates |
| EARTH | **±0.55 (seed-signed, ONE dominant lane)** | 0.10 | metronomic, one dominant lane |
| LIFE  | -0.10 | 0.40 | organic, mild weave |
| SHADOW| ±0.30 (seed-signed) | 0.35 | tricky/hidden, seed-signed lane — RISK not SPEED |
| AIR   | +0.20 | 0.60 | quick light taps, weaves a lot |

**Fix for the review's EARTH contradiction:** EARTH's manifestation is "metronomic, ONE dominant lane" — a `LaneBias` of `0.0` is a 50/50 split,
which is the OPPOSITE of one-lane. EARTH therefore takes a **large-magnitude** `LaneBias` (`±0.55`, its SIGN seed-chosen so which lane dominates
varies per craft) plus the lowest `Inter` (`0.10`) so it almost never alternates → the gate hammers mostly one lane at a steady cadence. WATER/ICE
keep `LaneBias=0.0` because their feel is "even but forgiving/sparse," not "one-lane."

**SHADOW tempo reconciliation (Enchanting parity, §2 cross-discipline).** SHADOW's §2.1 verb is *entropy / risk / hidden power* — NOT speed.
Enchanting expresses this by making pure shadow bodies **slow/unhurried** (`Rx<1`, an "unhurried-but-lethal drift," ENCHANTING_IMPLEMENTATION §4.2)
rather than the fastest section. An earlier Refining draft mis-read shadow as *fast/high-alternation* (`Inter=0.70`, the highest gate) — the
opposite tempo posture, which would make shadow read as SPEED. Reconciled: shadow is expressed as **high-RISK, not high-SPEED**. `Inter` drops to
`0.35` (moderate, ≈ WATER — a shadow gate is NOT the fastest-alternating), and the "entropy/risk" is carried by (a) the **seed-signed, hidden**
`LaneBias` (±0.30 — you cannot predict which lane dominates: the "tricky/hidden pattern") and (b) the **impurity swing** (shadow's KnobTable rows
carry high `+Vol` → high `Imp` and higher `Dbl`/`Rich` risk-reward, §2.2 UMBRA block). So shadow stays swingy and dangerous, but via unpredictability
and slag, not by being the fastest gate — matching Enchanting's shadow posture and the shared §2.1 verb.

**Seed-signed derivation (EARTH & SHADOW, CONCRETE — replaces the vague "a single seed bit").** `ThemeStructure(dom, ref _seed)` computes the
sign from ONE freshly-consumed seed bit, so it is deterministic and reproducible:

```csharp
// consume one RNG step; use its low bit as the ± sign.
// SeedBit / SplitMix64 are the §8 helpers (SplitMix64 takes `ref ulong` and advances the state in place).
double sign = SeedBit(ref _seed) == 0UL ? +1.0 : -1.0;
// EARTH:  LaneBias = sign * 0.55;  Inter = 0.10
// SHADOW: LaneBias = sign * 0.30;  Inter = 0.35   (risk via hidden/seed-signed lane + impurity swing, NOT speed — Enchanting parity)
```

Modifier riders on top (applied as deltas, clamped to the field ranges in §2, after the theme base):
- **sharp** present → `Dbl += 0.15`, Perfect-points bonus flag on (§4.6).
- **chaos/dangerous** present → `Inter += 0.15`, `_patternJitter += 0.15` (bounded RNG amplitude, base 0.15 → 0.30 here, capped 0.45; §8), `Dbl += 0.10`.
- **temporal** present → set `_gate.TempoDip = true` on ~half the gates (seed-chosen — `SeedBit(ref _seed)==0` per gate): tempo starts at ×0.8 then eases to ×1.0 over the gate's first 40% of beats. This is a TEMPO rider only; it does NOT change `Dens` (the temporal KnobTable row already lowers density like other slow tags — §2.1 temporal note).
- **layered** present → `Inter += 0.20` (two-lane interleaves — the tag's §2 meaning "complexity/adaptability").
- **WATER dominant** (`ThemeStructure`'s `dom == AQUA`) → set `_profile.WaterForgive = true`. This implements plan §2.2's "Cleaner/forgiving
  pattern; **recovers a missed impurity**": in `Judge`, the FIRST Miss of each gate skips the `ImpBumpMiss` slag add (it still scores 0 points and
  breaks the streak — only the IMPURITY consequence is forgiven). Tracked by a per-gate flag `_gateForgaveMiss` reset in `EnterGate`. This is the
  named, chosen implementation of the previously-dropped plan behaviour (§9 note), not a silent omission.

### 2.4 Tag pool (stacking, precedence) — reuse the spine's rules verbatim

1. **Per-ingredient precedence 4/3/2/1** (identical to `MinigameTagEffects.Brew`): within an ingredient's ordered tag list, the 1st tag
   weighs 4, 2nd 3, 3rd 2, 4th+ 1. Used to build the ingredient's "dominant theme" and its channel essence.
2. **Pool essence** (`double[6]`): sum `MinigameTagEffects.Brew(ing.Tags, ing.MaterialTier, ing.Qty)` over all ingredients → the
   6-channel vector. `Dominant()` of this vector = the pool's dominant theme (drives §2.3, gate `LaneTint`, `PatternName`).
3. **Pool counts** (`_pool`, `Dictionary<string,int>`): every tag from every ingredient counted (a tag appearing on two ingredients →
   count 2). Stacking via `MinigameModifierCommon.StackFactor` inside `Fold` gives diminishing returns (2nd copy +40%, 4th ~nil).
4. **Output tags** are counted into a SEPARATE `_outCounts` dict and folded into a `RefiningProfile` used ONLY for `#folds` character and
   the reward `Rich` (they set the GOAL, not per-strike manipulation — §1.1/§2.2 "Function/Output" note).

### 2.5 Wiring into `MinigameModifierCommon` (the concrete calls)

```csharp
private sealed class RefiningProfile : MinigameModifierCommon.ModProfile
{
    public RefiningProfile() : base(6, 0) { }   // 6 elemental channels; Refining uses NO named-state array (states=0)
    public double Dens, LaneBias, Inter, Dbl, Imp = 1.0, Rich = 1.0;   // resolved knobs (post-fold)
    public bool WaterForgive;                    // WATER-dominant: first Miss of each gate skips the slag add (§2.3 rider)
}

// The seven theme-default rows (§2.2 table), indexed by channel constant 0..5.
private static readonly (double Pot,double Vol,double Time,double Rx)[] ThemeDefault =
{
    /*HEAT */ (1.05, +10, 0.85, 1.35),
    /*AQUA */ (1.00, -4,  1.15, 0.95),
    /*TERRA*/ (1.00, -4,  1.25, 0.80),
    /*GROVE*/ (1.04, +2,  1.05, 1.05),
    /*UMBRA*/ (1.05, +6,  1.00, 1.05),
    /*AIR  */ (1.00, -3,  0.75, 1.25),
};

private RefiningProfile BuildProfile(IReadOnlyDictionary<string,int> counts, double[] poolEssence, int tier)
{
    var p = new RefiningProfile();

    // Build the EFFECTIVE table: KnobTable rows verbatim, PLUS a theme-default row for any counted tag that has no
    // explicit row but DOES have a RefChannelOf channel (§2.2/§2.2a). This is how "never a no-op" is realised without
    // touching the private Resolve — we resolve to a channel with our OWN dictionary, then inject the channel default.
    var table = new Dictionary<string,(double Pot,double Vol,double Time,double Rx)>(KnobTable);
    foreach (var tag in counts.Keys)
        if (!table.ContainsKey(tag) && RefChannelOf.TryGetValue(tag, out var ch))
            table[tag] = ThemeDefault[ch];

    // ChExc/StExc/StrongExc/PvExc are null — Refining has no per-channel/per-state reactivity twist; the base 4-tuple carries it all.
    MinigameModifierCommon.Fold(p, counts, table, chExc: null, stExc: null, strongExc: null, pvExc: null);
    p.Rx  *= 1 + (Math.Max(1, tier) - 1) * 0.04;              // tier lightly raises density (matches Alchemy's tier→Rx bump)
    MinigameModifierCommon.Clamp(p);                          // shared clamp: Pot .5..2.3, Vol ±28, Time .5..2.2, Rx .35..2.5

    // map shared fields → Refining knobs (§2 top)
    p.Dens     = Math.Clamp(p.Rx * Math.Clamp(2 - p.Time, 0.7, 1.2), 0.6, 1.6);
    p.Dbl      = Math.Clamp(0.12 + p.Vol / 60.0, 0.0, 0.6);
    p.Imp      = Math.Clamp(1.0 + p.Vol / 40.0, 0.5, 1.4);
    p.Rich     = Math.Clamp(0.75 + 0.35 * p.Pot, 0.9, 1.25);
    var dom    = MinigameTagEffects.Dominant(poolEssence);    // 0..5 channel index
    (p.LaneBias, p.Inter) = ThemeStructure(dom, ref _seed);   // §2.3 table (+ seed sign for EARTH/SHADOW)
    p.WaterForgive = dom == MinigameTagEffects.AQUA;          // WATER-dominant → forgive first Miss/gate (§2.3 rider)
    ApplyRiders(p, counts, ref _seed);                        // sharp/chaos/temporal/layered deltas (§2.3)
    return p;
}

// §2.3 structural table (dominant channel → base LaneBias/Inter, with the seed-signed EARTH/SHADOW magnitudes).
private (double LaneBias, double Inter) ThemeStructure(int dom, ref ulong seed)
{
    double sign = (SplitMix64(ref seed) & 1UL) == 0 ? +1.0 : -1.0;   // consumes one seed step (see §2.3 / §8)
    return dom switch
    {
        MinigameTagEffects.HEAT  => (+0.15, 0.55),
        MinigameTagEffects.AQUA  => ( 0.00, 0.35),   // WATER (ice/frost share this channel; the sparse ICE feel comes from KnobTable Dens, not structure)
        MinigameTagEffects.TERRA => (sign * 0.55, 0.10),   // EARTH: one dominant lane, seed-signed
        MinigameTagEffects.GROVE => (-0.10, 0.40),
        MinigameTagEffects.UMBRA => (sign * 0.30, 0.35),   // SHADOW: seed-signed lane (hidden); RISK via impurity swing, NOT speed (Enchanting parity)
        MinigameTagEffects.AIR   => (+0.20, 0.60),
        _                        => ( 0.00, 0.35),
    };
}

// §2.3 modifier riders — presence-tested against the pool counts; deltas clamped to the §2 field ranges.
private void ApplyRiders(RefiningProfile p, IReadOnlyDictionary<string,int> counts, ref ulong seed)
{
    bool Has(string t) => counts.ContainsKey(t);
    if (Has("sharp"))     { p.Dbl = Math.Clamp(p.Dbl + 0.15, 0, 0.6); _sharpInPool = true; }
    if (Has("chaos") || Has("dangerous")) { p.Inter = Math.Clamp(p.Inter + 0.15, 0, 1); p.Dbl = Math.Clamp(p.Dbl + 0.10, 0, 0.6); _patternJitter += 0.15; }
    if (Has("layered"))   p.Inter = Math.Clamp(p.Inter + 0.20, 0, 1);
    _temporalInPool = Has("temporal");     // consumed per-gate in EnterGate (seed-chosen ~half gates get TempoDip)
    _toxicInPool = Has("poison") || Has("venom") || Has("toxic") || Has("acid");  // corrupt gate: impurity leaks over time (§4.5a) — toxic = degrade-over-time (Smithing POISON_DOT parity), NOT just a one-shot +Vol swing
    // seed is threaded through so per-gate TempoDip choices in EnterGate stay deterministic.
}
```

`KnobTable` is the static `Dictionary<string,(double Pot,double Vol,double Time,double Rx)>` transcribed from §2.2. `_sharpInPool`,
`_patternJitter`, `_temporalInPool` are overlay fields (§1.5). `_outProfile = BuildProfile(_outCounts, outEssence, TierInt)` is built
separately for `#folds`/`Rich` (its `Dens`/`LaneBias`/etc. are ignored except `Rich`).

---

## 3. STATE MACHINE

Phases: `Ready → Play → Settle → Done`. There is no `Plan` phase (rhythm has no planning step; the enum omits it — but the doc keeps
the master-plan slot name mapping: **plan = Ready** here).

```
             player presses BEGIN / Space
   ┌────────┐ ─────────────────────────────▶ ┌──────┐
   │ Ready  │                                 │ Play │
   └────────┘                                 └──────┘
      ▲  OnBegin() builds gates+profile,          │  last strike of last gate judged
      │  _phase=Ready, _readyBox visible           ▼
      │                                        ┌────────┐  _settleT reaches 0
      └──────────────  (n/a: no retry) ◀────── │ Settle │ ────────────────▶ ┌──────┐
                                               └────────┘                    │ Done │ → Finish(perf)
                                               (1.0s summary flourish)       └──────┘
```

| From | To | Trigger | Actions |
|------|----|---------|---------|
| — | Ready | `OnBegin()` | Build `_pool`,`_profile`,`_outProfile`, all `_gates` (deterministic); cache `_gradeInit = MinigameTagEffects.Grade(allPoolTags)` (PUBLIC, 0..1); set `_impurity = clamp(0.7 * _profile.Imp * (1 - 0.15*_gradeInit), 0.35, 1.0)`, `_score=0`, `_scoreMax=Σ maxStrike`, `_gateIdx=0`, `_phase=Ready`, show `_readyBox`, `SetQuality(0)`, `_dev.BeginSession(...)`. `allPoolTags` = every tag from every ingredient (the flattened list, not the counts dict). |
| Ready | Play | Player clicks BEGIN button **or** presses Space/Click while `_readyBox` visible | Hide `_readyBox`, `_phase=Play`, `_gateClock=0`, enter gate 0 (`EnterGate(0)`). |
| Play | Play | Last strike of a NON-final gate judged (§4.1) | `EnterGate(_gateIdx+1)`: increment tempo (§4.2), reset `_gateClock=0`, `_gateBeatPrev=0`, `_gateForgaveMiss=false`, `_nextStrike=0`, short breather popup "FOLD n". No phase change. |
| Play | Settle | Last strike of the FINAL gate judged | `_phase=Settle`, `_settleT=SettleDur`, big flourish burst, `HideTimer()`. |
| Settle | Done | `_settleT <= 0` (decremented in `OnTick`) | `_phase=Done`, compute `perf` (§4.7), `_dev.Log(result)`, `Finish(perf)`. |

**Strike auto-miss:** inside `Play`, a strike whose window has fully passed (`_gateBeat > strike.Beat + _windowBeats`) and is not yet
`Judged` is force-judged `Miss` (no input) in `OnTick` before advancing `_nextStrike`. This is how the game "never stops."

**No FailCraft under normal play — but the guard IS reachable and testable.** The empty-recipe guard is:

```csharp
// In OnBegin, AFTER building _gates:
int total = 0; foreach (var g in _gates) total += g.Strikes.Count;
if (total == 0) { FailCraft(); return; }   // pathological: an all-empty pool produced no strikes
```

Under normal play `#folds ≥ 2` and every gate has ≥ 8 strikes, so `total ≥ 16` and the branch never fires in real crafts. The guard is NOT
dead code, because **`BuildGates` (the extracted static builder, §10.1) accepts an empty pool and empty output-tag list**, which produces
`#folds` clamped to its floor but with a `strikeCount` formula that a test can drive to zero by passing a degenerate `profile.Dens` — the test
constructs exactly that synthetic empty-recipe input (`counts={}`, `outputTags={}`, `poolEssence=zeros`) and asserts `FailCraft` fires once and
`Finish` zero times (§10.1 test #1). So the exactly-once FailCraft path is exercised by a real, constructible input, not asserted against an
unreachable branch. In the *live* game this input never occurs because `CraftingScreen` always supplies ≥1 ingredient (or the null-recipe
degrade of §1.1 synthesises one).

---

## 4. TICK MATH — every formula with named constants + starting values + perf targets

### 4.0 Named constants (all `private const double` unless noted; starting values are the SHIPPING defaults)

| Constant | Value | Meaning |
|----------|-------|---------|
| `SettleDur` | `1.0` s | Length of the Settle flourish. |
| `TimeBackstop` | `90.0` s | Hard cap on total play time (`SetTimer`), safety only; a normal run ends by strike exhaustion well under this. |
| `WindowBase` | `0.13` s | The **constant ± error window** (Miss threshold). NEVER scaled by difficulty (designer rule). |
| `CloseFrac` | `0.45` | Fraction of the window that counts as **Close** (\|Δ\| ≤ 0.45·window). |
| `OkayFrac` | `1.00` | Fraction that counts as **Okay** (0.45·window < \|Δ\| ≤ 1.00·window). Beyond → **Miss**. |
| `PerfectFrac` | `0.18` | \|Δ\| ≤ 0.18·window → **Perfect**. |
| `PtsPerfect` | `1.00` | Per-strike score for Perfect. |
| `PtsClose` | `0.70` | for Close. |
| `PtsOkay` | `0.40` | for Okay. |
| `PtsMiss` | `0.00` | for Miss. |
| `StreakStep` | `0.04` | Streak multiplier growth per consecutive perfect/close. |
| `StreakCap` | `0.60` | Max streak bonus (multiplier caps at 1 + 0.60 = 1.60). |
| `StreakBreak` | Close+Perfect keep it; Okay holds; Miss resets to 0 | Streak rule (see §4.5). |
| `ImpDrainPerfect` | `0.055` | Impurity removed per Perfect strike (fraction of full bar). |
| `ImpDrainClose` | `0.040` | per Close. |
| `ImpDrainOkay` | `0.020` | per Okay. |
| `ImpBumpMiss` | `0.030` | Impurity ADDED per Miss (leaves slag). |
| `ImpLeakPerBeat` | `0.010` | **Toxic corrupt-gate only** (`_toxicInPool`): impurity that REGROWS per beat of play across every gate — the degrade-over-time hazard (§4.5a). 0 when toxic absent. |
| `SharpPerfectBonus` | `0.10` | Extra Perfect points if `sharp` in pool (added to PtsPerfect for that strike). |
| `RailScrollBeats` | `2.5` | How many beats of the rail are visible ahead of the hit line (the "lead-in" runway). |
| `BreatherBeats` | `1.0` | Silent lead-in beats at the start of each gate (a count-in feel; no strikes scheduled before this). |

Difficulty-interpolated params (set in `OnBegin`; `Interp(easy,hard)` = `easy + (hard-easy)*clamp((DifficultyPoints-1)/79, 0, 1)`):

| Param | `Interp(easy, hard)` | Notes |
|-------|----------------------|-------|
| `_bps0` (gate-0 tempo, beats/s) | `Interp(1.6, 2.6)` | Base beat rate. §7. |
| `_tempoRamp` (per-gate ×) | `Interp(1.10, 1.16)` | Gate g tempo = `_bps0 * _tempoRamp^g`, **clamped** at `BpsMax` (§4.2). |
| `_windowSec` | `WindowBase` (NO interp — constant) | The window. Difficulty never touches it. |

### 4.1 Gate build (deterministic, in `OnBegin`)

**#folds.** `_nFolds = clamp(1 + TierInt + OutTagCount + ExtraFold, 2, 9)` where `OutTagCount = Recipe.OutputTags.Count` and `ExtraFold`
is `1` if the pool contains a **life-family** OR a **chaos** tag, else `0` — the "extra fold" from §2.2 (LIFE = regrowing impurity; chaos =
a wilder run). **Detection is by TAG NAME in `_pool`, never by `Dominant()` channel** (the review's mis-wire: `chaos` folds to the HEAT channel,
so `Dominant()==SHADOW` would never detect it; and a life-family pool need not be GROVE-dominant). Concretely:

```csharp
// requires: using System.Collections.Generic; using System.Linq;  (the rewrite adds these to the file's usings)
static readonly HashSet<string> LifeFamily = new()   // GROVE-channel tags per §2.1
{ "wood","oak","ash","ironwood","ebony","birch","willow","worldtree","exotic",
  "plant","herb","living","leather","monster","fang","scales","bone","gel","carapace","blood" };
bool extra = _pool.ContainsKey("chaos") || LifeFamily.Any(_pool.ContainsKey);
int extraFold = extra ? 1 : 0;
```

Loop `g = 0.._nFolds-1`, `EnterGate` builds `Gate.Strikes`:

- **`strikeCount`** = `Math.Round(Clamp(BaseStrikes + DensTerm + GateTerm, 8, 20))`, where the three terms are named and their INTERACTION is
  worked so no term silently swamps the others:
  - `BaseStrikes = 8` (the floor — a minimum-content gate).
  - `DensTerm = 6 * (profile.Dens - 0.6)` → density's contribution, **0 at min Dens (0.6) up to +6.0 at max Dens (1.6)**. (This replaces the old
    unexplained `6*Dens - 2`; the `-0.6` re-anchors so the *floor* is exactly 8 at min density instead of an arbitrary offset.)
  - `GateTerm = 1.2 * g` → each successive fold adds a little more content, **capped by design at ~+9.6 over 8 gates** but the outer
    `clamp(…,8,20)` bounds the total. To keep density MEANINGFUL even at high `g` (the review's "clamp dominates, Dens stops mattering"
    concern), `GateTerm` uses a gentle `1.2*g` (not `+g` unbounded interplay) and the **hard clamp is 20**: at max Dens the total is
    `8 + 6 + 1.2g`, so density still moves the count by up to 6 strikes at every gate until the clamp — at `g≥5` with max density the gate
    saturates at 20 by design (a legendary finale gate is meant to be maximal). Density dominates gates 0-4; the finale gates are intentionally
    capped. This is the intended trade, now stated.
- Schedule strikes at beats `b = BreatherBeats + Σ gap_i`, where each `gap_i` is:
  `baseGap = clamp(1.0 / profile.Dens, 0.55, 1.5)` beats; `gap_i = clamp(baseGap * (1 + _patternJitter*(Hash01(seed,g,i)-0.5)), 0.35, 1.6)`
  with `_patternJitter ∈ [0.15, 0.45]` (base 0.15; +0.15 for chaos/dangerous via `ApplyRiders`, §2.3). The **0.35-beat gap floor** (also §8)
  guarantees strikes never overlap unreadably. This yields "same theme, different exact sequence" per craft.
- **Cache `Gate.AvgGap`** = mean of the scheduled `gap_i` for the gate (used by the §4.2 TempoDip ease). Compute it as
  `AvgGap = (b_last - BreatherBeats) / max(1, strikeCount-1)` after scheduling.
- **Lane per strike (exact algorithm — no invention).** Maintain `runLen` = how many consecutive strikes have used the current lane, and
  `curLane`. For each strike i:
  ```
  if (i == 0)  curLane = Hash01(seed,g,0) < (0.5 + 0.5*profile.LaneBias) ? Lane.Space : Lane.Click; runLen = 1;
  else {
      bool flip = Hash01(seed,g,i) < profile.Inter;          // interleave roll
      if (runLen >= 4) flip = true;                          // FORCED flip: never a 5th identical-lane in a row (readability clamp)
      curLane = flip ? Other(curLane) : curLane;
      runLen  = flip ? 1 : runLen + 1;
  }
  strike.Lane = curLane;
  ```
  `Other(Click)=Space`, `Other(Space)=Click`. The clamp is a **forced flip** (deterministic, not a re-roll), so ≤4 identical-lane strikes in a row.
- DoubleTap: `Hash01(seed,g,i,'d') < profile.Dbl` → `DoubleTap=true`; schedule a paired sub-strike at `strike.Beat + 0.25` beats, **same lane**.
  A double-tap is two independent scored strikes (each judged on its own press, §4.4) rendered as one linked glyph (§6.2 step 5).
- `Gate.BeatsPerSecond` = `min(_bps0 * _tempoRamp^g, BpsMax)` where `BpsMax = 4.2` (the anti-unhittable clamp, §9 roadblock 5).
- `Gate.TempoDip` = `_temporalInPool && (SeedBit(ref _seed)==0)` — temporal marks ~half the gates (deterministic per gate, §2.3).
- `_scoreMax += strikeCount * PtsPerfect` (denominator; streak bonus is ABOVE this so a perfect+streak run exceeds 1.0 before the
  final `clamp` — that headroom is what lets an expert reliably hit ~1.0, §4.7).

### 4.2 Tempo & scroll (per `OnTick`, `Play` phase)

```
_anim      += delta
_gateClock += delta
bps         = _gate.BeatsPerSecond
// temporal rider: tempo starts at ×0.8 and eases to ×1.0 over the first 40% of the gate's beat-span.
// dipSpan (beats) = 0.4 * totalGateBeats, and totalGateBeats ≈ (strikeCount-1)*AvgGap. Both are known on _gate.
if (_gate.TempoDip) {
    double dipSpan = 0.4 * (_gate.Strikes.Count - 1) * _gate.AvgGap;      // AvgGap cached at build (§4.1)
    bps *= Mathf.Lerp(0.8, 1.0, Math.Clamp(_gateBeat / Math.Max(0.001, dipSpan), 0, 1));
}
_gateBeat   = _gateClock * bps
```

`_gate.Strikes.Count` and `_gate.AvgGap` are both stored on the Gate (§1.4/§4.1) — no per-tick recomputation, no undefined `avgGap`/`strikeCount`.

The rail scrolls so that a strike at `strike.Beat` sits at the hit line when `_gateBeat == strike.Beat`. Screen x of a strike =
`HitLineX + (strike.Beat - _gateBeat) * BeatPx` where `BeatPx` = pixels-per-beat = `RailUsableW / RailScrollBeats` (§6.2). Strikes to
the right of `HitLineX` are upcoming; at/left are past.

**Window in beats:** `_windowBeats = _windowSec * bps` (recomputed per gate — because the window is CONSTANT in SECONDS, it shrinks in
BEATS as tempo rises, which is exactly why faster gates are harder while the second-window is fixed). This is the mathematical
statement of "error window constant, escalate via tick speed."

### 4.3 Auto-miss sweep (per `OnTick`, before input)

```
while (_nextStrike < _gate.Strikes.Count) {
    var s = _gate.Strikes[_nextStrike];
    if (s.Judged) { _nextStrike++; continue; }
    if (_gateBeat > s.Beat + _windowBeats) { Judge(s, Grade.Miss, input:false); _nextStrike++; }
    else break;
}
if (_nextStrike >= _gate.Strikes.Count && all judged) AdvanceGateOrSettle();
```

### 4.4 Input judging (on a Click or Space press — §5)

On press of lane L at time `_gateBeat`: scan the gate for the **single nearest not-yet-judged strike in lane L** whose `|_gateBeat - s.Beat|`
is within `_windowBeats + GrabMargin`, `GrabMargin = 0.5*_windowBeats`. **One press consumes exactly ONE strike** — the nearest matching one:

```
best = null; bestD = +inf;
foreach (s in _gate.Strikes)
    if (!s.Judged && s.Lane == L) {
        d = |_gateBeat - s.Beat|;
        if (d <= _windowBeats + GrabMargin && d < bestD) { best = s; bestD = d; }
    }
if (best == null) → ghost tap (below);
else {
    r = bestD / _windowBeats;                         // 0 at dead-centre, 1 at window edge
    grade = r <= PerfectFrac ? Perfect : r <= CloseFrac ? Close : r <= OkayFrac ? Okay : Miss;
    Judge(best, grade, input:true);                   // marks best.Judged = true; the OTHER strike stays live
}
```

**Double-tap / two-in-lane tie-break (the review's concrete case).** When two same-lane strikes are both inside the band (e.g. a double-tap's
two sub-strikes at `Beat` and `Beat+0.25`, or a dense fire gate), **the single press consumes only the CLOSER one** (`d < bestD`), marks it
`Judged`, and **leaves the farther one live** for the NEXT press (or for the §4.3 auto-miss sweep if no second press lands in its window). So a
double-tap genuinely requires two presses; tapping once scores the near sub-strike and the far one must still be hit or it auto-misses. This is
the intended precision demand of the `sharp` rider — stated, not implied.

**Ghost tap.** If NO strike matches (`best == null`) → no score change, small dull `Burst`, `_streak = 0` (punishes blind spamming — the
anti-solve mechanism, §9 roadblock; a masher who taps both lanes constantly racks ghost taps and streak resets). Pressing the WRONG lane for an
upcoming strike is a ghost tap (that strike stays live for its correct lane until its window passes).

### 4.5 Scoring a judged strike (`Judge(Strike s, Grade grade, bool input)`)

```
pts = grade switch { Perfect => PtsPerfect + (_sharpInPool ? SharpPerfectBonus : 0), Close => PtsClose, Okay => PtsOkay, _ => 0 }
if (grade is Perfect or Close) { _streak++; }                       // streak = consecutive perfect/close
else if (grade == Okay)        { /* hold streak, no growth */ }
else                           { _streak = 0; }                     // Miss (input or auto) breaks it
_maxStreak = max(_maxStreak, _streak)
streakMul  = 1 + min(_streak * StreakStep, StreakCap)               // 1.00 .. 1.60
_score    += pts * streakMul * _profile.Rich                        // Rich = quality/grade reward richness
// impurity
double impDelta = grade switch { Perfect => -ImpDrainPerfect, Close => -ImpDrainClose, Okay => -ImpDrainOkay, _ => +ImpBumpMiss };
if (grade == Miss && _profile.WaterForgive && !_gateForgaveMiss) { impDelta = 0; _gateForgaveMiss = true; }   // WATER: forgive first Miss/gate (§2.3)
_impurity += impDelta
_impurity  = clamp(_impurity, 0, 1); _purity = 1 - _impurity
SetQuality(clamp(_score / _scoreMax, 0, 1))                          // live quality meter = running accuracy
PlayHitSfx(grade);                                                   // audio hook (§9 roadblock 4) — empty method today
// feedback: lane flash, popup, burst (§6.5)
```

`_sharpInPool` is the overlay bool set by `ApplyRiders` (§1.5/§2.5) — NOT a bare local. `_profile.Rich`/`_profile.Imp` are fields of the folded
`RefiningProfile` (§2.5); `_gradeInit` (used to seed `_impurity` in `OnBegin`) is the cached `MinigameTagEffects.Grade` value (§1.5/§3 Ready row).

### 4.5a Toxic corrupt gate — impurity leak over time (the `_toxicInPool` "degrade-over-time" expression)

When `_toxicInPool` is set (any of `poison`/`venom`/`toxic`/`acid` in `_pool`, §2.5 `ApplyRiders`), impurity does not merely start higher — it
**regrows continuously across the whole gate**, so the slag actively creeps back while the player works. This is toxic's **degrade-over-time**
manifestation (SHADOW §2.1 verb "degrade-over-time (toxic)"), the direct Refining analogue of Smithing's `POISON_DOT` — an active ticking hazard,
NOT just the one-shot `+Vol` impurity swing the KnobTable rows already produce. It is applied once per `OnTick` in `Play`, keyed to beats so it
scales with tempo (a faster gate leaks proportionally more per second, matching the accelerating pressure):

```
// In OnTick (Play phase), AFTER the auto-miss sweep (§4.3) and BEFORE the single _gateBeatPrev advance, using this
// frame's beat delta. IMPORTANT: this block only READS _gateBeatPrev — it does NOT advance it. The §9 roadblock-4
// audio hook remains the SINGLE owner of `_gateBeatPrev = _gateBeat;` at the end of OnTick, so there is no double-advance.
if (_toxicInPool) {
    double beatsThisFrame = Math.Max(0.0, _gateBeat - _gateBeatPrev);  // ≥ 0; _gateBeatPrev is the §1.5 field, advanced later
    _impurity = Math.Clamp(_impurity + ImpLeakPerBeat * beatsThisFrame, 0, 1);
    _purity   = 1 - _impurity;
}
// (do NOT touch _gateBeatPrev here — the audio-tick site at the tail of OnTick advances it once, §9 roadblock 4)
```

- **It leaks IMPURITY only, never SCORE.** The scored metric is `_score/_scoreMax` (accuracy of strikes, §4.7); the leak degrades the *visible
  ingot purity* and therefore the crafted-quality read, exactly as WATER's forgive rider and the drain/bump only touch `_impurity`. A player who
  keeps landing Perfects still out-drains a modest leak; a masher lets the corruption win — the intended big-risk/reward of a toxic recipe.
- **Bounded / telegraphed** (§3 randomness rule): `ImpLeakPerBeat = 0.010` and `_impurity` is clamped `[0,1]`, so over a typical ~10–14-beat gate
  the leak adds ≤ ~0.14 of the bar per gate — perceptible pressure, never an unrecoverable spiral (good hits drain `0.055`/`0.040` each, §4.0). The
  corrupt gate is visually signalled by the SHADOW `LaneTint` wash (§6.2 step 3) plus a faint creeping tint on the impurity bar (§6, drawn when
  `_toxicInPool`), so the degrade-over-time is a *tell*, not a betrayal.
- **Interaction with WATER forgive:** independent. `WaterForgive` (§2.3) only cancels the first Miss's `ImpBumpMiss`; the toxic leak is a separate
  continuous term. A recipe that is both water- and toxic-tagged gets a forgiving first Miss AND a slow creep — which is the correct read of "a
  cleansing flow fighting an active corruption."

### 4.6 Grade thresholds (restate, they are the scored metric)

| \|Δ\| / window | Grade | Points | Colour source |
|---------------|-------|--------|---------------|
| ≤ 0.18 | **Perfect** | 1.00 (+0.10 if sharp) | `UiTheme.Rarity["legendary"]` (gold) |
| ≤ 0.45 | **Close** | 0.70 | `UiTheme.Rarity["rare"]` (blue) |
| ≤ 1.00 | **Okay** | 0.40 | refining `Accent` `(0.98,0.78,0.42)` |
| > 1.00 / no input | **Miss** | 0.00 | `(1.0,0.4,0.34)` red |

### 4.7 Final perf (`Settle → Done`)

```
raw   = _score / _scoreMax          // Σ(points·streakMul·Rich) / Σ maxStrikePerfect  → can exceed 1.0 via streak/Rich
perf  = clamp(raw, 0, 1)
Finish(perf)
```

**Perf-band targets — the calibration DERIVED from a concrete per-strike model (not asserted).** Let a run have `S` total strikes; every band
below is `raw = Σ(pts·streakMul·Rich) / (S·PtsPerfect)`. Take a representative mid recipe with `Rich = 1.0` (ungraded) for the floor/mid rows and
`Rich = 1.10` (a "fine"/"rare" recipe) for the expert row, and derive each policy's per-strike outcome distribution explicitly:

| Player | Per-strike outcome mix (the model) | Streak | raw computation | `perf` |
|--------|------------------------------------|--------|-----------------|--------|
| **Masher** (fixed both-lane spam) | Presses land on the wrong lane or off-window most of the time: ~55% ghost taps (0 pts, and each resets streak), ~30% auto-Miss on strikes never correctly hit (0), ~15% accidental Okay (0.40). No Perfect/Close. | never builds (`streakMul≈1.0`) | `raw ≈ (0.15·0.40·1.0) / 1.0 = 0.060`… but the 15% Okay is optimistic; the constant-cadence drift across accelerating gates pulls accidental hits to ~0.22 of strikes at entry tempo and ~0.10 at high tempo, averaging `≈0.55·0.40 = 0.22` over the run's early-gate weighting | **~0.22–0.30** |
| **Competent** (right lane, ±0.06 s timing, no streak discipline) | ~35% Okay (0.40), ~40% Close (0.70), ~15% Perfect (1.00), ~10% Miss (0). Mean pts ≈ `0.35·0.40 + 0.40·0.70 + 0.15·1.0 + 0.10·0 = 0.57`. | short streaks avg ~3 → `streakMul ≈ 1 + min(3·0.04,0.60) = 1.12` applied to the Close/Perfect fraction (~55% of strikes) | `raw ≈ (0.57 · effectiveStreak≈1.05) / 1.0 ≈ 0.60` | **~0.55–0.65** |
| **Expert** (right lane, ±0.015 s, no ghost taps, long streaks) | ~85% Perfect (1.00 + 0.10 sharp on a sharp recipe), ~13% Close (0.70), ~2% Okay. Mean pts ≈ `0.85·1.0 + 0.13·0.70 + 0.02·0.40 ≈ 0.95`. | streak saturates → `streakMul = 1.60` sustained; Rich = 1.10 | `raw ≈ 0.95 · 1.60 · 1.10 / 1.0 ≈ 1.67` → clamps to **1.0** | **~0.93–1.0** |

The `≈` figures are the numbers the §10.7 test bands `[0.18,0.32]` / `[0.50,0.68]` / `≥0.90` verify — each row above shows the arithmetic a
coder reproduces from the outcome mix, so the calibration is derived, not asserted. Because `_scoreMax` uses `PtsPerfect` with NO streak/Rich, an
all-Perfect run WITH streak/Rich exceeds `_scoreMax` and clamps to 1.0 (the expert `raw≈1.67`), guaranteeing the expert ceiling is reachable,
while the masher floor stays low because ghost taps score nothing and reset streaks. (The synthetic input policies that produce these mixes are
spelled out in §10.1 test #7 so the bands are checkable headlessly.)

---

## 5. INPUT MAP

| Input | Phase | Effect |
|-------|-------|--------|
| **Left mouse button (pressed)** | Ready | Start play (same as BEGIN). |
| **Left mouse button (pressed)** | Play | Judge **Lane.Click** (§4.4). Consume. |
| **Space (pressed, `!Echo`)** | Ready | Start play. Consume. |
| **Space (pressed, `!Echo`)** | Play | Judge **Lane.Space** (§4.4). Consume. |
| **F1** | any | `_dev.HandleKey` toggles the on-screen event log. Consume + redraw. |
| **F7** | any | `_dev.HandleKey` toggles the notes box. Consume + redraw. |
| **Esc / double-Esc** | any | Handled by the BASE `MinigameOverlay._UnhandledInput` (first warns, double abandons). Refining does NOT touch Esc. |

**F1/F7 claiming (exact idiom, mirrors `AlchemyMinigame`):** override `_UnhandledKeyInput` (the EARLIEST key stage) and route F1/F7
to `_dev.HandleKey` FIRST, before the world's global debug handler ever sees them:

```csharp
public override void _UnhandledKeyInput(InputEvent @event)
{
    if (@event is not InputEventKey { Pressed: true, Echo: false } k) return;
    if (_dev.HandleKey(k.PhysicalKeycode)) { _rail.QueueRedraw(); GetViewport().SetInputAsHandled(); }
}
```

Gameplay keys (Space) go through the base's `OnInput(InputEvent)` override; mouse via the base `OnInput` too (both arrive through
`MinigameOverlay._UnhandledInput → OnInput`). When the notes box has focus (`_dev.NotesEditHasFocus`), **Space must NOT judge** — guard
every gameplay branch with `&& !_dev.NotesEditHasFocus` (so typing a note doesn't hammer strikes), exactly as Alchemy guards Enter.

**Hit-testing / focus:** the rail is a full-width `Control`; no per-element mouse hit-testing is needed (lanes are keyed by which button,
not by cursor position — Click = left mouse anywhere, Space = spacebar). The BEGIN `Button` uses `FocusMode = None` so it never steals
Space. The `_rail` `MouseFilter = Ignore` (it only draws; input is global via the overlay), matching the seam.

---

## 6. VISUAL SPEC

All rects are relative to the `_rail` `Control`'s local space, sized `RailW × RailH` (§6.1). Colours are theme-sourced: refining accent
`Accent = (0.98,0.78,0.42)` (brass/gold), glow `(0.95,0.70,0.30)`, ember `(0.92,0.80,0.50)` from `CraftStyle.Get("refining")`; grade
colours from §4.6 (`UiTheme.Rarity`). The card + backdrop + quality meter are the BASE overlay's (unchanged); Refining is a CARD
minigame (NOT `FullscreenScene`), so `FullscreenScene => false` (default) — do not override it.

### 6.1 Layout constants

```
RailW = 660f, RailH = 300f               // _rail.CustomMinimumSize; SizeFlagsHorizontal = ShrinkCenter (centered in the card host)
IngotRect   = Rect2(24, 40, 120, 220)    // left: the ingot being refined (brightens with _purity)
RailRect    = Rect2(168, 96, 468, 108)   // the horizontal fold rail (scrolling strikes travel across this)
HitLineX    = RailRect.Position.X + 96    // = 264f; the vertical "strike now" line, 96px from the rail's left
RailUsableW = RailRect end - HitLineX     // = (168+468) - 264 = 372f runway ahead of the hit line
BeatPx      = RailUsableW / RailScrollBeats  // = 372 / 2.5 = 148.8 px per beat
LaneClickY  = RailRect.Position.Y + 30     // = 126f (upper lane centre)
LaneSpaceY  = RailRect.Position.Y + 78     // = 174f (lower lane centre)
ImpBarRect  = Rect2(168, 224, 468, 16)     // impurity bar under the rail
HudY        = 262f                          // gate/fold + streak readout row
```

### 6.2 Draw order (z within `_rail`, painter's algorithm — later = on top)

1. **Rail backdrop plate** — `CraftFx.RoundRect(_rail, RailRect_expanded, (0.10,0.08,0.06), border=Accent@0.5, 2, 10)`. A dark warm
   trough. `RailRect_expanded` = `RailRect` grown 10px each side.
2. **Two lane guides** — for each lane draw a full-width thin line at `LaneClickY`/`LaneSpaceY`: `_rail.DrawLine((HitLineX-96,y),(railRight,y),
   laneCol@0.25, 3f)`. Click lane tint = `(0.55,0.9,1.0)` (cool cyan), Space lane tint = `Accent` (brass). Distinct colours =
   instant lane read (§9 roadblock 2). A small lane ICON at the far left of each guide: Click = a mouse glyph "◱", Space = "▭ SPACE".
3. **Gate LaneTint wash** — a translucent rectangle over `RailRect` in `_gate.LaneTint` at α 0.06 (the theme colour of the current fold, so a
   fire gate reads warm-red, an ice gate cool-blue) — obeys §2 theming. Draw it with `_rail.DrawRect(RailRect, new Color(t.R,t.G,t.B,0.06f))`.
   **Note:** `CraftFx.Ellipse` returns a `Vector2[]` polygon (it does NOT draw); if a rounded wash is wanted instead of a rect, feed those points
   to `_rail.DrawColoredPolygon(CraftFx.Ellipse(center, rx, ry), tintColor)`. The default here is the plain `DrawRect` — no polygon needed.
4. **Hit line** — a bright vertical bar at `HitLineX` from rail top to bottom: `_rail.DrawLine((HitLineX, RailRect.top),(HitLineX,
   RailRect.bottom), (1,1,1,0.9), 3f)` + a soft `CraftFx.Glow(_rail, (HitLineX, railMidY), 22f, Accent@0.5)`. Two small chevrons "▸ ◂"
   framing it so the player's eye locks there.
5. **Upcoming strikes** (right of hit line) — for each not-yet-judged strike within `RailScrollBeats` ahead: compute `x = HitLineX +
   (s.Beat - _gateBeat)*BeatPx`, `y = s.Lane==Click ? LaneClickY : LaneSpaceY`. Draw a **strike token**: a filled circle r=11 in the
   lane colour, ring outline `CraftFx.Ring(_rail, (x,y), 13, laneCol, 2f)`. Fade-in alpha over the far 20% of the runway (`α = clamp((RailScrollBeats -
   (s.Beat-_gateBeat)) / (RailScrollBeats*0.2), 0, 1)`). If `s.DoubleTap`, draw a second smaller token at `x + 0.25*BeatPx` linked by a
   1.5px line (`CraftFx.Streak`) — the "tight double-tap" read.
6. **Window bracket at the hit line** — two faint tick marks at `HitLineX ± _windowBeats*BeatPx` on the current strike's lane, showing
   the (shrinking-in-pixels-as-tempo-rises) forgiveness zone. Colour `(1,1,1,0.18)`. This is the "tell": the window is visible.
7. **Judged strike pop** — on judge, spawn (not persistent) `CraftFx.Popup(_rail, (HitLineX, y-24), gradeName, gradeCol, size)` and
   `CraftFx.Burst(_rail, (HitLineX,y), gradeCol, n, speed)`; Perfect gets a white spark ring `CraftFx.Burst(..., Colors.White, 16, 200)`
   + `FlashQuality()`. Missed strikes leave a small red `CraftFx.Crack(_rail, (x,y), Vector2.Down, 14, red)` slag mark that fades.
8. **Lane hit flash** — `_flashLane[lane]` decays; while > 0 draw a bright `CraftFx.Glow` at the hit line on that lane, colour = last
   grade colour, radius `18 + 10*flash`.
9. **Impurity bar** (`ImpBarRect`) — `CraftFx.Bar(_rail, ImpBarRect, _impurity, track=(0.06,0.05,0.04), fill=(0.5,0.42,0.3))`. Label
   "IMPURITY" left-aligned above it in `Accent@0.8`. As `_impurity` drops the bar shortens (theme: slag driven out). NO number shown
   (house rule — the ONLY hard number allowed is the direct scoring metric; impurity is a feel bar).
   **Toxic corrupt-gate tell (`_toxicInPool`, §4.5a):** when the recipe is toxic, tint the fill toward a sickly green
   `(0.34,0.55,0.24)` and draw a faint creeping overlay at the fill's leading edge — `CraftFx.Wisp(_rail, (fillRightX, barMidY),
   (0.34,0.55,0.24, 0.35), _anim)` — so the "impurity regrowing over time" is a visible, telegraphed hazard (a tell, not a betrayal),
   and the label reads "IMPURITY ⚠" in the toxic tint. Non-toxic recipes draw the normal muddy fill with no wisp.
10. **The ingot** (`IngotRect`) — a rounded metal bar drawn with `CraftColor.RadialGrad` (fake lit sphere/bar): base dark
    `CraftColor.Darken(barCol, 0.6)`, light `CraftColor.Brighten(barCol, 0.3*_purity)` — so it visibly BRIGHTENS as purity rises.
    `barCol` = the pool's dominant-theme family colour `MinigameTagEffects.FamilyColor(dom)` de-muddied via `CraftColor.DeMuddy`.
    Fold-by-fold: each cleared gate adds a subtle fold-line highlight across the ingot (`_rail.DrawLine` in `Accent@0.4`), so the ingot
    literally shows N folds. At high `_purity` a slow `CraftFx.Glow` halo pulses (`Accent@0.3 * sin(_anim*3)`).
11. **HUD row** (`HudY`) — left: "FOLD n / N" in `Accent`; centre: streak "COMBO ×k" glowing when `_streak≥3` (colour lerp Accent→white
    by `_streak/25`); right: the ONLY on-screen number — **running accuracy `score/scoreMax` is NOT shown as a raw number** (it is the
    quality meter). Per §5 fork-3 + house rule, the sole optional numeric is the **combo count** (a streak count is arguably the direct
    ceiling metric); show `×k` combo only. Do NOT print score/par (unlike the old build) — the quality meter carries it.
12. **F1 dev log — DECIDED: OVERLAY, `BeatPx` never changes.** When `_dev.ShowLog`, draw `_dev.DrawLog(_rail, LogRect, font, pinned)` where
    `LogRect = Rect2(RailW-250, 8, 244, RailH-16)`. The log is painted LAST (top z-order) as a translucent panel that sits OVER the right end
    of the rail; **`RailUsableW` and `BeatPx` are compile-time constants (§6.1) and are NOT recomputed when the log opens** — the scrolling
    tokens keep their exact screen-x, so timing is unaffected mid-run. The log's own backdrop is `_dev.DrawLog`'s panel at α≈0.85 (opaque enough
    to read, drawn on top), so tokens that scroll under its left edge are simply occluded for their last ~1.7 beats of runway — acceptable
    because judging happens at `HitLineX = 264f`, far LEFT of the log's left edge (`RailW-250 = 410f`), so no token is hidden during its hit
    window. This is the single decided behaviour; the coder chooses nothing.

### 6.3 Animation curves

- **Strike approach:** linear in beat-space (constant scroll) — deliberate, so timing is honest.
- **Lane flash decay:** `_flashLane[l] = max(0, _flashLane[l] - delta*4)` (≈0.25s).
- **Hit-line breathe:** hit-line glow radius `22 + 3*sin(_anim*6)`.
- **Combo glow:** pulses at `sin(_anim*8)` when `_streak≥5`.
- **Settle flourish:** over `SettleDur`, the ingot glow ramps `_purity`-scaled and a `CraftFx.RingPulse(_rail, ingotCentre, 40, phase, Accent)`
  expands once (phase = `1 - _settleT/SettleDur`).
- **Tempo-dip (temporal gate):** the rail LaneTint wash pulses slightly brighter during the dip so the slow-then-snap reads.

### 6.4 Draw-legality rules

- All draws happen ONLY inside `DrawRail` (the `_rail.Draw` handler). Popups/Bursts are child nodes spawned by `CraftFx` (auto-free).
- Never draw a strike token left of `RailRect.left` or right of `railRight` (cull off-runway strikes).
- Never draw more than the visible-window strikes (cull by `RailScrollBeats`).
- Grade popups/bursts are one-shot children, capped implicitly by strike count (≤20/gate) — no pooling needed.

### 6.5 Colour sourcing summary (grounded via `CraftColor`/`CraftStyle`/`UiTheme`)

| Element | Colour |
|---------|--------|
| Rail plate / borders / labels | refining `Accent` `(0.98,0.78,0.42)` (from `CraftStyle`) |
| Click lane | `(0.55,0.9,1.0)` cyan (distinct from brass Space lane) |
| Space lane | `Accent` |
| Gate LaneTint | `CraftColor.DeMuddy(FamilyColor(dom), FamilyColor(dom))` — the pool's dominant theme family colour |
| Perfect | `UiTheme.Rarity["legendary"]` |
| Close | `UiTheme.Rarity["rare"]` |
| Okay | `Accent` |
| Miss / slag | `(1.0,0.4,0.34)` |
| Ingot body | `CraftColor.RadialGrad` over `DeMuddy(FamilyColor(dom))`, brightened by `_purity` |
| Impurity fill | `(0.5,0.42,0.3)` muddy slag |

### 6.6 Ready-state layout (the `_readyBox` screen — CONCRETE, invent nothing)

Built in `BuildUi(host)` (a `VBoxContainer`), mirroring the current file's node graph but with exact strings, font sizes, colours, and the
persistent `_hint` legend added. All nodes are children of `host`; the `_rail` `Control` is added FIRST so it draws behind the ready UI, and
`_readyBox`/`_hint` are laid out UNDER it in the card column. On `OnBegin` `_readyBox.Visible = true`; on Ready→Play `_readyBox.Visible = false`
(the `_hint` legend stays visible for the whole run).

| Node | Type | Text / content | Font size | Colour | Layout |
|------|------|----------------|-----------|--------|--------|
| `_rail` | `Control` | (the play surface, `DrawRail`) | — | — | `CustomMinimumSize = (660, 300)`; `SizeFlagsHorizontal = ShrinkCenter`; `MouseFilter = Ignore`. Added to `host` first. |
| `_hint` | `Label` | `"Lane 0 = ◱ CLICK (cyan, upper)     Lane 1 = ▭ SPACE (brass, lower)     ·     hit the lane as each token reaches the line"` | `13` | `(0.95,0.86,0.62)` (ember) | `HorizontalAlignment = Center`; added to `host` directly under `_rail`; **never hidden**. |
| `_readyBox` | `VBoxContainer` | (holds the two nodes below) | — | — | `separation = 10`; added to `host`; `Visible` toggled. |
| `_readyLabel` | `Label` | `"Beat the impurities out of the metal.\nKeep the rhythm as each fold speeds up — Perfect / Close / Okay / Miss per strike.\nMisses leave slag; long streaks purify faster. The forge never stops."` | `16` | `UiTheme.Text` (default label colour) | `HorizontalAlignment = Center`; child of `_readyBox`. |
| `_beginBtn` | `Button` | `"BEGIN FOLDING  ▸  [Space]"` | `20` | (theme button) | `FocusMode = None` (never steals Space); `Pressed += StartPlay`; child of `_readyBox`. |

No rects are needed for the ready UI: it flows in the card's `VBoxContainer` (the base overlay centers the card). The only fixed-size element is
`_rail` (660×300, §6.1). The Settle/Done phases reuse the rail surface (no extra nodes). This fully specifies the ready screen — a coder writes it
verbatim.

---

## 7. DIFFICULTY CURVE — exact `DifficultyPoints → knob` mapping

**One dial: `DifficultyPoints` (≈1..80).** Tags are CHARACTER only; difficulty scales raw hardness uniformly (§1.4). The window is
NEVER touched (constant). Difficulty flows into TEMPO and TEMPO RAMP only (plus #folds via tier, which is recipe-derived not points-derived).

`f = clamp((DifficultyPoints - 1)/79, 0, 1)` (0 at entry, 1 at legendary). `Interp(easy,hard) = easy + (hard-easy)*f`.

| Knob | Formula | Entry (pts=1) | Legendary (pts=80) |
|------|---------|---------------|--------------------|
| Gate-0 tempo `_bps0` (beats/s) | `Interp(1.6, 2.6)` | 1.6 | 2.6 |
| Per-gate tempo ramp `_tempoRamp` | `Interp(1.10, 1.16)` | ×1.10/gate | ×1.16/gate |
| Error window `_windowSec` | `WindowBase` (constant) | 0.13 s | 0.13 s |
| `BpsMax` (unhittable clamp) | const | 4.2 | 4.2 |
| `#folds` | `clamp(1+TierInt+OutTagCount+ExtraFold, 2, 9)` (ExtraFold=1 if life-family or `chaos` in pool, §4.1) | recipe-driven (e.g. 2) | recipe-driven (e.g. 7–9) |

**Worked when/how examples:** (`TierInt` per §1.1 = common 1 … legendary 5)
- **Entry** — `common` iron ingot (`TierInt=1`), one output tag, `pts≈4`: `_bps0≈1.64`, ramp `1.10`. `#folds = clamp(1+1+1+0, 2, 9) = 3`
  (or 2 if 0 output tags). Gate 0 at 1.64 beats/s, gate 1 at 1.80 beats/s. `_windowBeats` at gate 1 = `0.13*1.80 = 0.234` beats — a
  comfortable ~13% of a beat. A slow, steady, learnable groove.
- **Legendary** — `legendary` mithril alloy weapon (`TierInt=5`), 2 output tags (`weapon`,`sharp`), `pts≈70`: `_bps0≈2.48`, ramp `1.155`.
  `#folds = clamp(1+5+2+0, 2, 9) = 8` (sharp/weapon are not life/chaos, so ExtraFold=0). Gate 0 at 2.48 b/s; gate 7 at
  `min(2.48*1.155^7, 4.2) = min(6.6, 4.2) = 4.2` b/s (clamped). `_windowBeats` at the cap = `0.13*4.2 = 0.546` beats — but the beat
  itself is `1/4.2 = 0.238`s, so the SECOND window is still 0.13s: a blistering but fair finale. The clamp guarantees never-unhittable (§9).

**Tag character at fixed difficulty (§1.4 illustration):** at the SAME `pts`, a fire recipe → high `Dens` (denser strikes) + double-taps +
higher impurity to clear; an earth recipe → low `Dens` (fewer, heavier, metronomic) + high floor. Difficulty (tempo) is identical; the
KIND of hard differs. Never let a tag touch `_bps0`/`_tempoRamp`.

---

## 8. RANDOMNESS SPEC

**Seeded, reproducible, telegraphed.** A single deterministic RNG (`_seed`, a 64-bit SplitMix64/xorshift, NOT `GD.Randf`) drives ALL
pattern variation, so a given craft replays identically (headless tests can assert exact gate patterns).

**Seed source:** `_seed = Hash(craftId, orderedIngredientTags, outputTags, TierInt)` where `craftId` = `Recipe.OutputId` + a per-launch
salt derived from `Recipe.Inputs` order (stable for the same recipe). Concretely: FNV-1a over the concatenation
`OutputId | "|" | join(OutputTags) | "|" | foreach input: Id+":"+join(Tags)+":"+Qty | "|" | Tier`. Same recipe + same materials → same
seed → same patterns → reproducible; different recipe → different seed. **Null recipe:** seed from `DifficultyTier` + a fixed salt so
debug launches are also deterministic per tier.

**The concrete RNG (declare these, they are referenced by §2.3/§4.1):**

```csharp
// One SplitMix64 step: advances the state in place and returns it. Deterministic, no GD.Randf.
private static ulong SplitMix64(ref ulong s)
{
    s += 0x9E3779B97F4A7C15UL;
    ulong z = s;
    z = (z ^ (z >> 30)) * 0xBF58476D1CE4E5B9UL;
    z = (z ^ (z >> 27)) * 0x94D049BB133111EBUL;
    return z ^ (z >> 31);
}
// One deterministic 0..1 keyed by (gate, index, salt) WITHOUT consuming _seed — used for pattern rolls so each
// roll is independent and reproducible. Mixes the base seed with the coordinates via SplitMix64 on a local copy.
private double Hash01(ulong seed, int gate, int index, int salt = 0)
{
    ulong h = seed ^ ((ulong)(uint)gate * 0x100000001B3UL) ^ ((ulong)(uint)index << 21) ^ ((ulong)(uint)salt << 43);
    return (SplitMix64(ref h) >> 11) * (1.0 / 9007199254740992.0);   // 53-bit mantissa → [0,1)
}
private static ulong SeedBit(ref ulong s) => SplitMix64(ref s) & 1UL;   // consumes one step; low bit = ± sign / coin flip
```

`_seed` is the persistent state; `Hash01` reads it without consuming (independent per-strike rolls), while `SeedBit`/`ThemeStructure`/`EnterGate`
CONSUME steps for one-off structural choices (EARTH/SHADOW sign, per-gate TempoDip) so those stay stable and ordered.

**What is seeded:**
- Per-gate strike `gap_i` jitter (§4.1) — `Hash01(_seed,g,i)` scaled by `_patternJitter ∈ [0.15, 0.45]` of `baseGap`. Final gap clamped ≥ 0.35
  beats (floor) so strikes never overlap unreadably.
- Lane assignment interleave flips (§4.1) — `Hash01(_seed,g,i)` vs `Inter`; the forced ≤4-in-a-row flip bounds it further.
- DoubleTap placement (§4.1) — `Hash01(_seed,g,i,'d')` vs `Dbl ≤ 0.6`.
- EARTH & SHADOW `LaneBias` sign (§2.3) — `SeedBit(ref _seed)` (one consumed step each; +→lane bias positive, −→negative).
- Which gates get `TempoDip` when `temporal` present (§2.3/§4.1) — `SeedBit(ref _seed)` per gate in `EnterGate` (~50%).

**Bounds (never a betrayal):** every random quantity is clamped to a range that keeps the gate hittable (gap floor 0.35 beats; tempo
clamp `BpsMax`; window constant). **The tell:** every strike scrolls in from the right across `RailScrollBeats` (≈2.5 beats ≈ 1–1.6s of
warning at entry/legendary tempo) with a fade-in — the player always SEES a strike coming and which lane it's in before it reaches the
hit line. The double-tap glyph and the gate LaneTint wash also pre-announce character. Nothing spawns AT the hit line.

**Not `GD.Randf` anywhere in gameplay** (only cosmetic base-overlay shake uses it). This is the fix for the reproducibility requirement.

---

## 9. ROADBLOCK REGISTER (each §3.3 risk → a concrete chosen mitigation)

| # | Risk (from §3.3) | CHOSEN mitigation |
|---|------------------|-------------------|
| 1 | **Deterministic-but-varied pattern generation from tags** | A seeded FNV-1a RNG keyed by `(craftId, tags, output, tier)` (§8). `Hash01(seed,gate,index)` gives per-strike variation; same craft → identical pattern (testable), different craft → fresh. Bounds keep it fair. **DECIDED.** |
| 2 | **Two-lane input clarity (click vs space)** | Distinct lane colours (Click = cyan, Space = brass `Accent`), distinct Y positions (`LaneClickY`/`LaneSpaceY`), a persistent lane legend `_hint` + a per-lane icon at the rail's left, and a lane-coloured strike token. §6.2 steps 2/5. **DECIDED.** |
| 3 | **Tempo feel — constant window + accelerating tick must feel fair** | Window is CONSTANT in SECONDS (`WindowBase=0.13`); only tempo ramps (§7). The window bracket is DRAWN at the hit line (§6.2 step 6) so the player sees the forgiveness. Close/Okay bands (0.45/1.00 of window) are wide at entry. `BpsMax=4.2` clamps the ceiling. **DECIDED.** |
| 4 | **Audio (rhythm begs for sound)** | Silent-but-visual-first. TWO empty hook methods are DECLARED on the overlay with fixed signatures, and CALLED at exactly two sites so SFX drops in later with zero structural change: `private void PlayHitSfx(Grade grade) { /* TODO: AudioStreamPlayer per-grade */ }` called at the end of `Judge` (§4.5, shown), and `private void PlayBeatTick() { /* TODO: metronome click */ }` called in `OnTick` each time `_gateBeat` crosses an integer beat boundary (i.e. when `Math.Floor(_gateBeat) != Math.Floor(_gateBeatPrev)`, tracking `_gateBeatPrev`). Both are no-ops today; neither affects logic. **DECIDED (visual-first, hooks declared + placed).** |
| 5 | **Theme→pattern map must never make a gate literally unhittable at max tier** | `BpsMax = 4.2` beats/s clamp on `Gate.BeatsPerSecond` (§4.1/§7); a strike-gap floor of `MinGapBeats = 0.35` beats (§8); the window is constant seconds not beats. **Solvability proof (concrete, at MAX tempo).** `TokenDiameter = 2 * TokenRadius = 2*11 = 22px` (§6.2 step 5: token r=11). `BeatPx` is a FIXED constant `148.8` (§6.1, computed from the static rail geometry — it does NOT change with tempo, because the rail shows a fixed `RailScrollBeats=2.5` window of the beat-timeline regardless of `bps`; a higher `bps` just scrolls that window FASTER, it does not compress pixels-per-beat). So the minimum on-screen spacing between two adjacent tokens is `MinGapBeats * BeatPx = 0.35 * 148.8 = 52.1px ≥ 22px` at EVERY tempo including `BpsMax` — tokens never visually overlap. The window in SECONDS is constant `0.13s > 0` at every tempo. The headless test asserts, for every gate at every `DifficultyPoints` archetype: `MinGapBeats * BeatPx ≥ TokenDiameter` and `_windowSec == 0.13`. **DECIDED.** |

---

## 10. TEST PLAN

### 10.1 Headless-checkable invariants (pure-logic, no rendering — the pattern generator + scorer are separable static-ish methods)

Refactor gate-building and scoring so they can run without the scene: `BuildGates(pool, profile, outProfile, seed, difficultyPoints,
tier)` returns `List<Gate>` and `ScoreRun(gates, inputs)` returns `perf`, both callable from a test.

`BuildGates` and `ScoreRun` are `internal static` methods on `RefiningMinigame`. They take plain data (`counts`, `poolEssence`, `outCounts`,
`seed`, `points`, `tierInt`) and return `List<Gate>` / `perf`, so no Godot scene is instantiated to run them. Test visibility mirrors the
SMITHING doc's convention: add one `[assembly:InternalsVisibleTo("<refining-minigame test asm>")]` attribute to the Godot project's
`AssemblyInfo` (an attribute line, NOT a change to any shared toolkit logic), and reference the Godot assembly from a minigame-logic test project.
`Gate.LaneTint` is a `Godot.Color`, which is fine — the test only asserts the numeric/pattern fields (lane, beat, doubletap, bps, counts), never
renders. No shared toolkit file is edited.

1. **Seam exactly-once.** Simulate a full run through the phase logic; assert `Finish` is invoked exactly once and `FailCraft` zero times for
   any VALID recipe; assert `perf ∈ [0,1]`. Then feed the **synthetic empty-recipe input** (`counts={}`, `outputTags={}`, `poolEssence=zeros`
   → `BuildGates` yields a total strike count of 0) and assert the empty-recipe guard calls `FailCraft` exactly once and `Finish` zero times
   (§3 note — this input is constructible, so the guard is a live, tested branch, not dead code).
2. **Determinism.** `BuildGates(same args)` twice → byte-identical gate patterns (lane, beat, doubletap per strike). Different `craftId`
   → different patterns (assert Hamming distance > 0). This is the reproducibility guarantee.
3. **Fold count law.** `#gates == clamp(1+TierInt+OutTagCount+ExtraFold, 2, 9)` where `ExtraFold = (pool has chaos OR any life-family tag) ? 1 : 0`
   (detected by TAG NAME, per §4.1), across a table of recipes — including one with `chaos` (a HEAT-channel tag) to prove the +1 fires by NAME,
   not by `Dominant()==SHADOW`.
4. **Strike-count band.** Every gate has `8 ≤ Strikes.Count ≤ 20`.
5. **Solvability / never-unhittable.** For `DifficultyPoints ∈ {1,20,40,60,80}` and each of the 7 theme archetypes: every gate's
   `BeatsPerSecond ≤ BpsMax`; every adjacent-strike gap ≥ `MinGapBeats (0.35)`; `MinGapBeats * BeatPx (148.8) = 52.1 ≥ TokenDiameter (22)`;
   `_windowSec == 0.13` regardless of points (constant-window law).
6. **Window-is-constant law.** Assert `_windowSec` never varies with `DifficultyPoints` (guards against a regression that scales it).
7. **Perf bands (calibration).** Synthetic input policies over a mid recipe (the exact outcome mixes are in §4.7):
   - *Masher* (fixed-cadence both-lane spam, ignores lanes/beat) → `perf ∈ [0.18, 0.32]`.
   - *Competent* (correct lane, ±0.06s timing jitter) → `perf ∈ [0.50, 0.68]`.
   - *Expert* (correct lane, ±0.015s, no ghost taps) → `perf ≥ 0.90`.
   `ScoreRun` accepts a list of `(lane, pressBeat)` inputs so each policy is a pure function producing a deterministic `perf`.
8. **Tag-theme monotonicity (character, not hardness).** At FIXED `DifficultyPoints`, a fire-dominant pool yields higher mean `Dens`
   (strikes/beat) than an ice-dominant pool; an ice pool yields fewer strikes/gate. Tempo (`_bps0`) is IDENTICAL across themes at the
   same points (asserts §1.4).
9. **Every-tag-has-an-interaction (no private-member access).** The test enumerates **Refining's OWN** `KnobTable.Keys ∪ RefChannelOf.Keys**
   (both `internal static` on `RefiningMinigame`, visible to the test assembly) — NOT the private `MinigameTagEffects.Tags`/`Metal`/`Wood`. For
   each tag it asserts EITHER (a) `KnobTable` has an explicit row, OR (b) `RefChannelOf` returns a channel whose `ThemeDefault` row is non-identity
   — so folding it moves at least one of `Pot/Vol/Time/Rx`; never a silent no-op. A second sub-assertion covers the master vocabulary: for a curated
   fixture list of every elemental tag named in plan §2.1 (a static string[] IN THE TEST, transcribed from the plan — not read from the private
   sets), assert each appears in `KnobTable.Keys ∪ RefChannelOf.Keys`. This proves coverage WITHOUT touching or editing `MinigameTagEffects.cs`.
10. **Impurity bounds.** `_impurity` stays in [0,1] across any input sequence; a full-Perfect run drives it below 0.15. A WATER-dominant recipe's
    first per-gate Miss adds NO slag (asserts the `WaterForgive` rider, §2.3/§4.5).
11. **Toxic degrade-over-time (`_toxicInPool`).** For a recipe carrying a toxic-family tag (`poison`/`venom`/`toxic`/`acid`): assert `_toxicInPool`
    is set, and — holding all strike input IDENTICAL (same `(lane,pressBeat)` list) — a toxic recipe ends with strictly HIGHER `_impurity` than the
    same recipe with the toxic tag removed (the leak regrows slag), while `_score`/`perf` is UNCHANGED (the leak degrades purity only, not the scored
    accuracy — §4.5a). Also assert the leak stays bounded: over any single gate `_impurity` never jumps by more than `ImpLeakPerBeat * gateBeatSpan`.
12. **Shadow is RISK not SPEED (Enchanting parity, §2.3).** Assert `ThemeStructure(UMBRA).Inter == 0.35` and that it is NOT the maximum `Inter`
    across the seven themes (FIRE 0.55 / AIR 0.60 exceed it) — a regression guard that shadow is never re-made the fastest-alternating gate. Shadow's
    risk instead shows up as `|LaneBias| > 0` (seed-signed, hidden) and, via its KnobTable rows, higher `Imp`/`Dbl` than a neutral theme.

### 10.2 F1/F7 playtest script (manual, uses `MinigameDevLog`)

Log header (`BuildLogHeader`): output id, output tags, tier, `DifficultyPoints`, `#folds`, `_bps0`, dominant theme, per-ingredient tag
lists. `Context` bracket: `() => $"g={_gateIdx+1}/{_nFolds} beat={_gateBeat,5:0.0} combo={_streak} q={(_score/_scoreMax)*100,3:0}%"`.
Log an event on: each gate enter (`FOLD n · pattern=<name> · bps=<x> · strikes=<k>`), each Miss (`MISS lane=<L> beat=<b>`), each gate
clear, and the result.

**Script:**
1. Launch a Tier-1 iron recipe. Press F1. Confirm the log shows 2–3 folds, `bps≈1.6`, entry-slow tempo.
2. Play a clean run; confirm combo climbs, impurity drains to near-zero, quality meter reaches Legendary band, ingot brightens.
   F7 a note: "entry tempo feels fair?" — snapshot logs `_bps0`, window, streak.
3. Launch a Tier-4 fire/chaos weapon recipe. Confirm denser bursts + double-taps + higher starting impurity, more folds, faster tempo,
   and that late gates clamp at `BpsMax` (log shows `bps=4.2` capped). Verify no gate is unhittable.
4. Mash both lanes blindly — confirm `perf` lands ~0.25 (ghost taps score nothing, streak never builds) and the game still completes.
5. Compare a fire vs an ice recipe at the SAME station/points — confirm identical tempo but different density/feel (§1.4).
6. Re-run the SAME recipe twice — confirm the pattern is identical (determinism tell) but distinct from a different recipe.

---

## 11. REUSE MAP

### 11.1 Shared toolkit calls used (every one, with purpose)

| Toolkit | Calls | Purpose |
|---------|-------|---------|
| `MinigameOverlay` (base) | `BuildUi`, `OnBegin`, `OnTick`, `OnInput`, `Finish`, `FailCraft`, `SetQuality`, `FlashQuality`, `Shake`, `SetTimer`, `HideTimer`, `SetHeaderSub`, `Popup`, `Burst`; `Discipline => "refining"`; NOT `FullscreenScene` (card mode). | The sacred seam + all feedback. 0-churn to the base. |
| `MinigameModifierCommon` | `ModProfile(6,0)` subclass, `Fold(p, counts, table, null, null, null, null)`, `StackFactor` (implicit in Fold), `Clamp(p)`. | The effect-bank engine — Refining declares `KnobTable` + theme-default injection, reuses folding/stacking/clamping. |
| `MinigameTagEffects` | **PUBLIC only:** `Brew(tags,tier,qty)` (pool essence + precedence 4/3/2/1), `Dominant(essence)`, `FamilyColor(ch)`, `ChannelName(ch)`, `Grade(tags)` (quality grade for `_impurity` init), and the `HEAT/AQUA/TERRA/GROVE/UMBRA/AIR/N` channel consts. **NOT used (private): `Resolve`, `Tags`, `Metal`, `Wood`, `QualityGrade`** — Refining resolves per-tag channels with its OWN `RefChannelOf` (§2.2a) so the shared file stays 0-diff. | The REAL material tag vocabulary (via `Brew`), precedence, colours. No new tag vocab invented; no private member touched. |
| `CraftFx` | `RoundRect`, `Bar`, `Ring`, `RingPulse`, `Streak`, `Crack`, `Glow`, `Popup`, `Burst`, `Hash01` (cosmetic only), `QualityBands`/`Band` (via base meter). | Rail, tokens, slag cracks, impurity bar, popups, bursts. Pure 2D, no shaders. |
| `CraftColor` | `DeMuddy` (gate tint + ingot body), `RadialGrad` (ingot lit-bar), `Darken`/`Brighten` (ingot purity brightening). | Vivid theme colours; ingot brightening. |
| `MinigameDevLog` | `new MinigameDevLog("refining")`, `.Context`, `.NoteSubmitted`, `.BuildNotesPanel(host)`, `.HandleKey`, `.ShowLog`, `.NotesEditHasFocus`, `.BeginSession`, `.Log`, `.Note`, `.DrawLog`. | F1 log + F7 notes → `res://playtest_logs/refining_playtest.log`. |
| `CraftStyle` | `Get("refining")` (implicit via base) → Accent/Ember/Glow/Top/Bottom. | Theme palette. |
| `StateVisual` | **NOT used.** | Per §1.5 of the plan: rhythm leans on `CraftFx` primitives, not the chemistry named-state set. |
| `UiTheme` | `Rarity["legendary"/"rare"]`, `Box`. | Grade colours + panel styling. |

### 11.2 New sprites / assets

**NONE.** Everything is procedural (`CraftFx`/`CraftColor` draw calls). No PNGs, no shaders (the base's ONE backdrop shader has its
`GradientBackdrop` fallback — untouched). Lane icons are Unicode glyphs drawn via `DrawString`. Zero asset pipeline dependency. SFX are
stubbed hooks only (§9 roadblock 4), no audio files required to ship.

### 11.3 `Game1.Core` 0-diff confirmation + change-set scope

This minigame is entirely Godot-side glue: it READS `RecipeContext` (already Godot-side, built by `CraftingScreen` from the certified
`Recipe` + `MaterialDatabase`) and PRODUCES `perf ∈ [0,1]` through `MinigameOverlay.Finish`. It calls NO `Game1.Core` type, mutates NO
game state, and touches NO balance formula (damage/EXP/tier/difficulty are all upstream in the certified `DifficultyCalculator`, whose
`Points`→`DifficultyPoints` we only READ). **`Game1.Core` is 0-diff.**

**Change-set scope (now internally consistent).** The ONLY production file changed is `RefiningMinigame.cs` (rewritten body, same
class/namespace/base/seam). Crucially, the earlier draft's requirement to make `MinigameTagEffects.Tags`/`Metal`/`Wood`/`Resolve` public is
**REMOVED**: Refining resolves per-tag channels via its own `RefChannelOf` dictionary (§2.2a) and its own `KnobTable`, and the pool-dominant
theme via the already-PUBLIC `Brew`/`Dominant`. So `MinigameTagEffects.cs` and every other shared toolkit file stay byte-for-byte unchanged.
The test-plan refactor (§10.1 `BuildGates`/`ScoreRun` as `internal static` methods, and `KnobTable`/`RefChannelOf` as `internal static`) lives
ENTIRELY inside `RefiningMinigame.cs`; the test assembly reaches them through a single `[assembly:InternalsVisibleTo]` attribute added to the
Godot project's `AssemblyInfo` (same convention as SMITHING_IMPLEMENTATION §10 — an attribute line, no new `public` surface on any shared type,
no shared-logic edit). The change set is therefore: `RefiningMinigame.cs` (the rewrite), a one-line `AssemblyInfo` attribute, and a new test file.
No shared toolkit code churn; `MinigameTagEffects.cs`/`MinigameModifierCommon.cs`/`CraftFx.cs`/`CraftColor.cs` are all untouched.

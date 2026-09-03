<!-- ENGINEERING IMPLEMENTATION DOC — 2026-08-19. Authored against docs/CRAFTING_MINIGAMES_MASTER_PLAN.md
     (canonical). This REBUILDS EngineeringMinigame.cs: the current "Flow Router" pipe-rotation mechanic is
     SUPERSEDED by the master-plan §3.4 "Circuit Lights" ALL-IN LIGHTS-OUT mechanic. Coding this is mechanical —
     invent nothing; every constant, rect, colour, and formula is fixed below. -->

# Engineering — "Circuit Lights" (all-in Lights-Out) — Implementation Doc

**Discipline key:** `"engineering"` · **Overlay subclass:** `EngineeringMinigame : MinigameOverlay` (partial, `CanvasLayer`).
**Master plan cell:** §3.4. **Essence:** *plan-then-execute logic puzzle, scored on a gradient of correctness.*
**Seam:** `Begin(points, tier, RecipeContext?, onComplete(perf 0..1), onAbandon)` → play → `Finish(perf)` OR `FailCraft()` exactly once (Circuit Lights never calls `FailCraft` — a botched board still delivers a coverage floor; see §4.5).
**House rule:** the ONLY hard numbers on screen are the discipline's direct scoring metrics. Per designer ruling (master plan §5 fork 2, resolved SHOW): the **move count** is a legit direct metric and IS shown as a number. Everything else (time, correctness, elegance) is bars/feel.

This mechanic REPLACES the file's current pipe-router logic wholesale. Reuse only the file's *scaffolding conventions* (the `_readyBox` splash, `Interp()`, `CellAt/CellCenter/Origin/Cell` geometry helpers, the header/meter wiring) — the pipe/BFS/salvage machinery is deleted.

---

## 1. DATA MODEL

All types are nested in `EngineeringMinigame` unless noted. Grid is **row-major**, `[r, c]`, `r∈[0,_rows)`, `c∈[0,_cols)`.

### 1.1 Enums

```csharp
private enum Phase { Ready, Plan, Play, Settle, Done }
```
| Value | Meaning |
|-------|---------|
| `Ready` | Splash up (`_readyBox.Visible`); no clock, no scoring; awaits [Space]/button. |
| `Plan`  | Board revealed, clock frozen, move budget frozen. Player queues flips (ghosts). No clock. |
| `Play`  | Clock + move budget run. Player commits flips live; limited re-plan. |
| `Settle`| ~0.9s scored freeze-frame: final board vs target, cascade VFX, meter lands on final perf. No input. |
| `Done`  | `Finish(perf)` already called; overlay hiding. |

```csharp
// Per-tile RULE VARIANT — the tag-driven "character" of a tile (see §2). Difficulty never sets these; tags do.
private enum TileRule : byte
{
    Plus = 0,    // DEFAULT. Flip toggles self + 4 orthogonal neighbours (classic Lights-Out).
    Single,      // sharp/precision. Flip toggles ONLY self (no ripple).
    Spread,      // life. Flip toggles self + 8 neighbours (Moore neighbourhood — orthogonal + diagonal).
    Immovable,   // earth heavy. Cannot be flipped directly; only toggled as a NEIGHBOUR of another flip.
    Invert,      // shadow/cursed. HIGH-RISK/HIGH-REWARD. Flip toggles self + the 8 Moore neighbours
                 // (like Spread) BUT ALSO toggles the 4 cells two steps away orthogonally (the "curse ring"):
                 // a wide 13-cell blast. Well-placed it clears a whole cluster (reward); mis-placed it wrecks
                 // far more than a Plus (risk). Still an involution (each cell toggled once). See §4.2.
    Wild,        // chaos/dangerous. Flip toggles self + 4 neighbours + one EXTRA telegraphed cell (seeded, shown).
}
```

```csharp
// A pending planned flip during Phase.Plan (drawn as a ghost, applied on POWER ON).
private readonly record struct GhostFlip(int R, int C, int Order);   // Order = queue index for the ghost badge
```

### 1.2 Tile grid (parallel arrays, sized `[_rows,_cols]` in `BuildBoard`)

| Field | Type | Units / range | Meaning |
|-------|------|---------------|---------|
| `_state` | `bool[,]` | on/off | Current lit state of each cell. `true` = lit. |
| `_target` | `bool[,]` | on/off | Goal state each cell must match. |
| `_rule` | `TileRule[,]` | enum | Per-tile rule variant (from tags; §2). |
| `_wildExtra` | `(int R,int C)[,]` | cell idx or `(-1,-1)` | For `Wild` tiles: the seeded extra cell it also toggles (telegraphed). `(-1,-1)` if none / non-wild. |
| `_flipCount` | `int[,]` | ≥0 | Times each cell has been *directly flipped* by the player (for the ghost/echo draw + parity debug). |
| `_matchPulse` | `float[,]` | 0..1 | Per-cell decaying "just became matched" glow (drives `CraftFx.RingPulse`). Decays at `MatchPulseDecay`/s. |

### 1.3 Difficulty-interpolated params (set once in `OnBegin`)

| Field | Type | Units | Range (entry→legendary) | Source |
|-------|------|-------|--------------------------|--------|
| `_rows` | `int` | tiles | 3 → 9 | §7 |
| `_cols` | `int` | tiles | 3 → 9 | §7 |
| `_moveBudget` | `int` | flips | `_minSolution + slack` | §4.3, §7 |
| `_timeBudget` | `double` | seconds | 40 → 16 (× fire factor) | §4.4, §7 |
| `_scramble` | `int` | flips | 2 → 14 | §4.1 (# generator flips) |
| `_minSolution` | `int` | flips | derived | §4.3 (GF(2) or scramble-count) |

### 1.4 Tag-derived knobs (set in `ApplyTagProfile`, from §2)

| Field | Type | Units | Range | Meaning |
|-------|------|-------|-------|---------|
| `_timeMult` | `double` | × | 0.55 → 1.6 (clamp) | Multiplies `_timeBudget`. **fire** shrinks it; **ONLY water** grows it (no other theme — not even temporal — touches the clock; temporal takes the +moves/freeze-tile reading, §2.2 — §2.4 guard, test 6). |
| `_moveMult` | `double` | × | 0.6 → 1.35 (clamp) | Multiplies the budget SLACK (not the min). **ice** shrinks it (fewer moves); **water/quality/gentle/temporal** grow it; **air** nudges it only slightly (air's primary effect is the dispersing Single tile, not extra moves — §2.1). |
| `_ruleWeights` | `double[6]` | weights | index 1..5 each 0..1; index 0 (Plus) = residual, unused in the roll | Weights for `TileRule` values `[Plus,Single,Spread,Immovable,Invert,Wild]` — ADDITIVE per §2.4, selected via the normalized weighted pick in §7.4. |
| `_undoCharges` | `int` | count | `UndoBaseline`(1) → 2 | "undo last flip" charges usable in Play. Every recipe gets ≥`UndoBaseline` (R3 re-plan floor); **water** stacks more, capped at 2. |
| `_gridBonus` | `int` | tiles | -2 → +4 (§7.1 cap) | **earth/quality/slot-family** additive bump to `_rows`/`_cols`; `mundane` can push it negative (the §7.1 clamp floors the grid at 3). |

`_ruleWeights`, `_timeMult`, `_moveMult`, `_undoCharges`, `_gridBonus` are produced from the tag pool per §2.4 (the two `×` scalars via `MinigameModifierCommon.Fold`; the additive `R:`/`U`/`G` knobs via a hand-rolled `StackFactor`-weighted pass). They are the ONLY channel by which tags touch the board.

### 1.5 Run / economy / animation state

| Field | Type | Units | Meaning |
|-------|------|-------|---------|
| `_phase` | `Phase` | — | current phase |
| `_movesSpent` | `int` | flips | flips committed in Play (the SHOWN number) |
| `_planGhosts` | `List<GhostFlip>` | — | queued flips during Plan |
| `_timeLeft` | `double` | s | Play countdown; drives `SetTimer` |
| `_undoLeft` | `int` | count | remaining undo charges |
| `_flipHistory` | `Stack<(int R,int C)>` | — | committed flips this Play, for undo |
| `_settleT` | `double` | s | Settle-phase elapsed (0..`SettleDuration`) |
| `_finalPerf` | `double` | 0..1 | perf computed at Settle entry, handed to `Finish` |
| `_anim` | `double` | s | free-running clock for idle shimmer/telegraph |
| `_animAcc` | `double` | s | throttle accumulator; fires `_grid.QueueRedraw()` at ~20 Hz for animated draws (§6.5, R4) |
| `_cursor` | `(int R,int C)` | cell | keyboard focus cell (arrow keys); `(0,0)` default |
| `_rng` | `RandomNumberGenerator` | — | seeded (§8); the ONLY randomness source |

### 1.6 UI nodes

| Field | Type | Role |
|-------|------|------|
| `_grid` | `Control` | play surface; `Draw += DrawGrid`, `GuiInput += OnGridInput`; `CustomMinimumSize (560,420)` |
| `_hud` | `Control` | above grid; `Draw += DrawHud`; shows move-count number + bars; `CustomMinimumSize (560,54)` |
| `_readyBox` | `VBoxContainer` | splash (label + "OPEN THE BENCH ▸ [Space]" button) |
| `_readyLabel` | `Label` | splash rules text |
| `_goButton` | `Button` | "POWER ON ▸" — transitions Plan→Play |
| `_hint` | `Label` | one-line control hint under the grid |
| `_dev` | `MinigameDevLog` | F1/F7 harness (`new MinigameDevLog("engineering")`) |

### 1.7 RecipeContext fields READ (all optional — degrade if `Recipe == null`)

| Field | Use |
|-------|-----|
| `Recipe.Inputs[].Tags` (ordered) | Ingredient tag pool → `_ruleWeights`, `_timeMult`, `_moveMult`, `_undoCharges` (per-ingredient precedence 4/3/2/1, §2.4). |
| `Recipe.Inputs[].Qty` | Stacking count into the tag-pool dict (`StackFactor`). |
| `Recipe.Inputs[].MaterialTier` | minor vigor into grade folding (used only via tags; no direct board effect). |
| `Recipe.OutputTags` | The GOAL character + the **slot-count grid sizing** (§7.1): count of Frames/Function/Power/Modifier/Utility slot families present → `slots` term of `_gridBonus` (§7.1). Also folds into the tag pool at rank-1 weight for `T`/`M`/`R:` knobs (§2.3). (There is no separate "objective density" quantity — that term is dropped; slot count feeds grid size only.) |
| `Recipe.Tier` (string) | Maps `common..legendary`→`0..4` as a floor on the difficulty stars (already handled by base `TierStars`). Feeds `_gridBonus` via quality grade. |
| `Recipe.Points` | NOT read directly — `DifficultyPoints` (the `Begin` arg) is the intensity dial. |

If `Recipe == null` (debug/harvest), synthesize a plausible pool: `["engineering","metal","common"]` inputs + `["tool","utility"]` output, so the board is always playable (mirrors master-plan §1.2).

---

## 2. TAG TABLE — complete material vocabulary → Circuit-Lights knobs

Authored by looking each tag up in master-plan §2.1 (theme) then §2.2 (Engineering column). **The Engineering manifestation of each theme, verbatim from §2.2:**

| Theme (verb) | §2.2 Engineering knob |
|--------------|------------------------|
| FIRE — haste/aggression/volatility | **Less TIME** on the clock (designer's example) |
| WATER — flow/cleanse/dilute | **Extra time / an "undo" tile** |
| ICE/COLD — control/deliberation/stability | **Fewer MOVES** — must plan (designer's example). ICE touches MOVES only — never the clock (that's WATER). |
| EARTH — solidity/resistance/mass | **Bigger, more STABLE grid; heavy immovable tiles** |
| LIFE — growth/vitality/spread | **Tiles that SPREAD (toggle a larger neighbourhood)** |
| SHADOW — entropy/risk/hidden power | **Cursed tiles (INVERT); high-reward-high-risk** |
| AIR — speed/lightness/evasion | **Fewer, lighter constraints; a "skip/light" tile** |
| Quality/Grade — magnitude | **Larger grid / more chains, but richer payoff** |
| sharp — precision rider | **A single-target (non-rippling) toggle** |
| temporal — time control | **+moves or a time-freeze tile** |
| chaos/dangerous — risk× | **A tile that randomly toggles** (telegraphed `Wild`) |

Each tag below sets one or more of: `T` = `_timeMult` (×, fold-mult), `M` = `_moveMult` slack (×), `R:<rule>` = adds weight to a `TileRule` in `_ruleWeights`, `U` = `_undoCharges` (+), `G` = `_gridBonus` (+). Values are the FULL-STRENGTH (one copy) contribution; stacking scales via `StackFactor` (§2.4).

### 2.1 Elemental bodies (primary themes)

**FIRE / HEAT — haste/aggression/volatility → LESS TIME, pressure via `Wild`.**
| Tags | Knob |
|------|------|
| `fire, flame, ember, molten, forge, volcanic` | `T ×0.80` (less time). `molten,volcanic` stronger: `T ×0.72`. |
| `lightning, storm` | `T ×0.78`, `R:Wild +0.20` (erratic burst). |
| `radiant, light` | `T ×0.88`, `R:Single +0.10` (a clean precise spark — light is orderly fire). |
| `chaos` | `T ×0.82`, `R:Wild +0.35` (randomness — see Exotic). |

**WATER (flow) — flow/cleanse/dilute → EXTRA TIME + UNDO.**
| Tags | Knob |
|------|------|
| `water, aqua, liquid, solvent` | `T ×1.25` (extra time), `U +1` (the "undo tile"). `solvent` also `M ×1.10`. |

**COLD / ICE — control/deliberation/stability → FEWER MOVES.**
| Tags | Knob |
|------|------|
| `ice, frost, frozen, chill` | `M ×0.72` (fewer moves — plan harder). `frozen` strongest: `M ×0.66`. **No time knob.** ICE touches MOVES only (§2.2 Engineering ice cell = "Fewer MOVES"); granting extra clock time is WATER's manifestation, and blurring ice into a time-giver violates §2.1's ice=control/deliberation pole. "Slow down and think" is delivered by the tightened move budget forcing deliberation, NOT by a longer clock. (Fixes the review's ice-borrows-water-verb violation; the former `T ×1.10` is deleted.) |

**EARTH / TERRA — solidity/resistance/mass → BIGGER STABLE GRID + IMMOVABLE tiles.**
| Tags | Knob |
|------|------|
| `earth, stone, sand, mineral` | `G +1`, `R:Immovable +0.22`. (Earth's "steady/unhurried" is expressed as a bigger, immovable-heavy grid you must plan around — NOT extra clock, which is water's verb; test 6.) `sand` weaker: `R:Immovable +0.12`. |
| Structural metals `metal, metallic, iron, steel, bronze, copper, tin, silver, gold, alloy` | `R:Immovable +0.16`, `G +1`. (mass + hardness). |
| High metals `mithril, adamantine, orichalcum` | `R:Immovable +0.18`, `G +1`, `M ×1.05` (dependable). |
| `crystal, gem` | `G +1`, `R:Single +0.12` (faceted precision), `R:Immovable +0.08`. |

**LIFE / GROVE — growth/vitality/spread → SPREAD tiles.**
| Tags | Knob |
|------|------|
| Woods `wood, oak, ash, ironwood, ebony, birch, willow, worldtree, exotic` | `R:Spread +0.24`. (Life's growth/spread is the Spread rule, not clock time.) `worldtree` strongest: `R:Spread +0.34`. |
| `plant, herb, leather, living` | `R:Spread +0.20`. |
| Feral `monster, fang, scales, bone, gel, carapace, blood` | `R:Spread +0.16`, `R:Wild +0.08` (ferocity/unpredictable). |

**SHADOW / UMBRA — entropy/risk/hidden power → INVERT (cursed) tiles.**
| Tags | Knob |
|------|------|
| `void, dark, shadow, spectral` | `R:Invert +0.26` (cursed/high-risk). `void` strongest: `R:Invert +0.34`, `M ×0.92` (negation costs planning). |
| Toxic `poison, venom, toxic, acid` | `R:Invert +0.18` + `R:Spread +0.06` (**degrade-over-time**, gestured at for Smithing parity: the wide `Invert` curse-blast is corrosion *spreading outward* — a toxic flip degrades/creeps into its neighbourhood rather than resolving cleanly, and the small `Spread` rider adds the encroaching-decay reach so toxic reads as an over-time corruption verb, not just a risk-swing. Distinct from raw shadow, which is pure entropy/risk without the spreading-decay tell). |
| Mystic `arcane, magical, essence` | `R:Invert +0.14`, `R:Wild +0.08` (raw amplification = swingier board). |

**AIR / WIND — speed/lightness/evasion → SKIP/LIGHT tile, fewer constraints.**
| Tags | Knob |
|------|------|
| `air, wind, vapor, gas` | `R:Single +0.26` (the PRIMARY effect: a light, non-rippling "skip/light" tile — dispersal/lightness, the ripple disperses to nothing), `M ×1.04` (a slight rider only). **No time knob** — air is speed/lightness/dispersal (§2.1), not a clock-grower. Its manifestation is the **dispersing, non-rippling Single tile**, NOT a relaxed move budget: the former dominant `M ×1.10` is cut to a minor `×1.04` so air no longer primarily reads as "more moves = relaxation." Air's "fewer, lighter constraints" (§2.2 air cell "a skip/light tile") is delivered by the cascade-free light tile — a flip that lands lightly and disperses — matching Refining's air = fast-AND-clean (disperses tempo/impurity) rather than gifting budget. |

### 2.2 Cross-cutting modifier families

**Quality / Grade — magnitude → bigger grid, richer payoff.** (Larger board but higher perf ceiling — enforced via §4.5 scoring, not here; here it only sizes.)
| Tags | Knob |
|------|------|
| `basic, starter, common, standard, mundane, material` | none (baseline). `mundane` `G -1` (a plain unconditional negative grid delta; the §7.1 `[-2,+4]` cap + `[3,9]` clamp jointly guarantee the grid never drops below 3 — there is NO "only if it would push below 3" branch, §2.4 step 6). |
| `uncommon, fine, quality, refined, superior` | `G +1`. |
| `rare, advanced, epic, precious` | `G +1`, and `M ×1.05` (more chains but richer payoff — a touch more slack). |
| `legendary, mythical, ancient` | `G +2`, `M ×1.05`. |
| `pure, holy` | `G +1`, `M ×1.10` (clean = forgiving). |

**Physical / Structural.**
| Tags | Knob |
|------|------|
| `durable, hard, solid, dense, heavy` | `R:Immovable +0.16` (mass/reinforcement). `heavy,dense` strongest: `R:Immovable +0.22`. **No time knob** — earth-structural "slow" is expressed as MORE immovable tiles (harder to plan), NOT extra clock; growing the clock is WATER's verb (§2.1 water=flow/forgiveness), and only water may grow `_timeMult` (test 6). |
| `strong` | `R:Immovable +0.10`, `G +1`. |
| `sharp` | `R:Single +0.30` (the precision rider — single-target non-rippling toggle, §2.2). |
| `layered, flexible, versatile, memory` | `R:Spread +0.10` (complexity/more states) AND `M ×1.05` (adaptability = a little slack). |

**Energy / Essence (amplifiers / wildcards).**
| Tags | Knob |
|------|------|
| `magical, arcane, essence` | `R:Invert +0.14` (raw power ×; already in Shadow-mystic — do NOT double-add: the code has exactly ONE combined table entry per tag, §2.4 precedence note). |
| `lightning` | `R:Wild +0.20`, `T ×0.85` (burst/erratic; already in Fire). |
| `chaos` | `R:Wild +0.35` (randomness/instability). |
| `blood` | `R:Spread +0.12`, `T ×0.95` (vitality-for-risk). |
| `spectral, radiant` | `spectral R:Single +0.12` (ethereal/evasive → light); `radiant` per Fire row. |

**Exotic / Rule-benders.**
| Tags | Knob |
|------|------|
| `quantum, impossible, power` | **Amplify the STRONGEST active rule-weight** by ×1.30/1.35/1.30 (→ `MinigameModifierCommon.ModProfile.AmpStrongest`, applied to `_ruleWeights` post-fold; §2.4). |
| `temporal` | `M ×1.15` (+moves — deliberate pacing) + `R:Single +0.10` (a "time-freeze" tile: a non-rippling toggle that lets you set one cell without cascade, i.e. freeze a knob rather than gift raw clock). **No time knob** — of the master-plan §2.2 alternatives ("+moves OR a time-freeze tile"), Engineering takes the **+moves / freeze-tile** reading, NOT the clock extension. This keeps temporal's "slow/control a knob" verb consistent with Refining/Enchanting/Smithing (which all SLOW a knob rather than gift a resource), and — crucially — leaves **WATER as the SOLE clock-grower** (`_timeMult>1`), removing the only other time-growth exception. Temporal thus reads as *more deliberate* (more planning room + a cascade-free freeze), never as *easier* via a longer clock. |
| `harmony` | `M ×1.12` (order = a little more planning room), and `R:Invert -0.10`/`R:Wild -0.10` (order/stabilise — REDUCES chaotic rules). **No time knob** — harmony's "order/stabilise" is expressed as move-slack + chaos-reduction, NOT extra clock (that would borrow water's verb; test 6 forbids non-water time growth). |
| `dangerous` | `R:Wild +0.30`, `T ×0.85` (risk × — bigger swings). |
| `elemental` | small `+0.06` to EACH of `Spread,Single,Invert` (all-element touch). |

### 2.3 Function / Output tags (mostly on `OutputTags` → set the goal's character + grid sizing)

Per §2.1 these describe the target's ROLE; in Engineering the FIVE slot-family tags also size the grid (master plan §3.4 "Frames/Function/Power/Modifier/Utility slot counts → grid size + difficulty"). Mapping of output/recipe tags to the five slot families (`_slotFamilies`, a `HashSet<string>` counted in §7.1):

| Slot family | Tags counted | Effect |
|-------------|--------------|--------|
| **Frames** | `armor, protection, defense, resistance, tool, crafting` | +1 grid tile per family present (`_gridBonus`), leans `R:Immovable +0.06`. |
| **Function** | `weapon, combat, utility, fishing, potion, consumable` | +1 grid tile per family present. |
| **Power** | `explosive, strength, lightning, energy, power` | `T ×0.90` (aggressive/volatile goal → tighter clock), +1 grid tile. |
| **Modifier** | `buff, enhancement, healing, regeneration, speed, agility, resistance` | leans `M ×1.05` (gentler goal), +1 grid tile. |
| **Utility** | `utility, engineering, crafting, harmony` | `U +1` if `harmony` present; +1 grid tile. |

Role→feel (applied as additional soft folds, aligning with §2.2 goal character):
| Output theme | Feel knob |
|--------------|-----------|
| aggressive goal (`weapon, combat, explosive, strength`) | `T ×0.90`. |
| defensive goal (`armor, protection, defense, resistance`) | `M ×1.05`, `R:Immovable +0.06`. |
| gentle goal (`healing, regeneration, harmony, buff`) | `M ×1.10` (a gentler goal = a little more planning room). **No time knob** — "gentle" is expressed as move-slack, not clock time (only water grows the clock; test 6). |
| fast goal (`speed, agility, air`) | `R:Single +0.06`, `M ×1.05`. |

### 2.4 Precedence, stacking, and wiring into `MinigameModifierCommon`

This section is written against the **real** `MinigameModifierCommon` API (`MinigameModifierCommon.cs:25-88`). Verify each call against those signatures — nothing below invents a field or overload.

**What actually exists in `ModProfile` (`MinigameModifierCommon.cs:25-41`):**
- Scalars `Pot` (× mult, init 1), `Vol` (additive, init 0), `Time` (× mult, init 1), `Rx` (× mult, init 1), `AmpStrongest` (× mult, init 1).
- Arrays `Ch[]` (per-channel × mult, all init 1), `St[]`, `PriPot[]`, `PriVol[]` (sized by the ctor's `channels`/`states`).
- Ctor `new ModProfile(channels, states)`.

**What `Fold` does (`MinigameModifierCommon.cs:53-74`):** for each tag in `counts` (scaled by `StackFactor(count)`):
- base table entry `(Pot,Vol,Time,Rx)` — `Pot`/`Time`/`Rx` fold **multiplicatively** (`p.X *= 1 + (b.X-1)*sf`), `Vol` folds **additively** (`p.Vol += b.Vol*sf`).
- `chExc[tag]` = `(int Ch, double Mul)[]` folds `Ch[]` **multiplicatively** from base 1.0.
- `strongExc[tag]` = `double` folds the `AmpStrongest` **scalar** multiplicatively.
- `Fold` does NOT rank or amplify any "strongest channel" — `AmpStrongest` is a plain scalar you apply yourself later.

**Consequences for our knobs (why we DON'T force everything through `Fold`):**
- `T` (`_timeMult`) is a pure `×` scalar → maps cleanly to `ModProfile.Time`. Use `Fold`'s base table.
- `M` (`_moveMult`) is a pure `×` scalar → repurpose `ModProfile.Rx` (the shared struct has no engineering-named field; `Rx` is unused by us, documented in code). Use `Fold`'s base table `Rx` slot.
- `R:<rule>` weights are **ADDITIVE** (`+0.26`), and `Ch[]`/`chExc` are **MULTIPLICATIVE from 1.0** — a units mismatch. **Do NOT route `R:` through `Ch[]`/`chExc`.** Instead accumulate them in a discipline-local additive pass (below), exactly like `U`/`G`. This is the concrete resolution of the additive-vs-multiplicative mismatch the review flagged.
- `U` (undo) and `G` (grid) have no `ModProfile` field → discipline-local additive accumulators.
- `AmpStrongest` — `Fold` only builds the scalar via `strongExc`; the actual "amplify the strongest rule weight" is a **hand-rolled post-pass we write** (Alchemy likewise applies its amp inside its own `Evolve`, `MinigameTagEffects.cs:326-331` — NOT inside `Fold`). See step 5 below.

**The concrete build (`ApplyTagProfile`), step by step:**

1. **Assemble `counts`.** Per-ingredient precedence 4/3/2/1 (master plan §1.3): within one input's ordered `Tags`, the 1st tag counts 4, 2nd 3, 3rd 2, 4th+ 1 (the same rank weights as `MinigameTagEffects.Brew`, `MinigameTagEffects.cs:252`). Accumulate `counts[tag] += (int)Math.Round(rankWeight * Math.Max(1, ingredient.Qty))`, floored to ≥1 per occurrence. `OutputTags` fold in at rank-1 weight (count 1). Result: `Dictionary<string,int> counts`.

2. **Fold the two `×` scalars via the shared engine.** Build ONE profile sized to the 6 `TileRule` values purely so the struct is well-formed (we do not use `Ch[]`): `var prof = new MinigameModifierCommon.ModProfile(6, 0);`. Declare the Engineering **base table** `Dictionary<string,(double Pot,double Vol,double Time,double Rx)> engBase` where each tag sets `Time = its T value` (default 1.0) and `Rx = its M value` (default 1.0), with `Pot = 1.0, Vol = 0` always (unused). Then:
   ```csharp
   var amp = new Dictionary<string,double>{ ["quantum"]=1.30, ["impossible"]=1.35, ["power"]=1.30 };
   MinigameModifierCommon.Fold(prof, counts, engBase, chExc: null, stExc: null, strongExc: amp);
   MinigameModifierCommon.Clamp(prof, timeLo: 0.55, timeHi: 1.6, rxLo: 0.6, rxHi: 1.35);   // named args — see below
   _timeMult = prof.Time;  _moveMult = prof.Rx;
   ```
   **`Clamp` note:** the real signature is `Clamp(ModProfile p, double potLo=…, potHi=…, volLo=…, volHi=…, double timeLo=…, timeHi=…, double rxLo=…, rxHi=…, …)` (`MinigameModifierCommon.cs:78-81`). There is **no positional `(timeLo,timeHi,rxLo,rxHi)` 4-arg overload** — you MUST pass them by NAME (`timeLo:`, `timeHi:`, `rxLo:`, `rxHi:`) as above, or the call will not compile / will clamp the wrong fields.

3. **Accumulate the additive `R:`/`U`/`G` knobs in a manual pass** (NOT through `Fold`). Declare three additive tables:
   - `Dictionary<string,(TileRule Rule,double W)[]> ruleAdd` — each tag → its `R:<rule> +w` entries.
   - `Dictionary<string,double> undoAdd` — each tag → its `U +n`.
   - `Dictionary<string,double> gridAdd` — each tag → its `G ±n`.
   Then:
   ```csharp
   double[] rw = new double[6];   // indexed by (int)TileRule; Plus(0) left 0 (residual)
   double uAcc = 0, gAcc = 0;
   foreach (var (tag, n) in counts) {
       var sf = MinigameModifierCommon.StackFactor(n);
       if (ruleAdd.TryGetValue(tag, out var ra)) foreach (var (rule, w) in ra) rw[(int)rule] += w * sf;
       if (undoAdd.TryGetValue(tag, out var u)) uAcc += u * sf;
       if (gridAdd.TryGetValue(tag, out var g)) gAcc += g * sf;
   }
   ```
   Every additive accumulation is `StackFactor`-weighted, so a 2nd copy adds ~40%, 4th almost nothing — identical stacking behaviour to `Fold`.

4. **Clamp / finalize `R:`, `U`, `G`.** `for (i in 1..5) rw[i] = Math.Clamp(rw[i], 0, 1);` (Plus stays 0). `_ruleWeights = rw;` `_undoCharges = Math.Clamp((int)Math.Round(uAcc) + UndoBaseline, 0, 2);` (`UndoBaseline = 1` const — every recipe gets at least one re-plan charge so R3 holds even with zero water tags, see §1.4/R3). `_gridBonus` is finalized in step 6.

5. **Hand-rolled `AmpStrongest` pass.** After step 4, apply the folded scalar to the single largest NON-Plus rule weight:
   ```csharp
   if (prof.AmpStrongest != 1.0) {
       int bi = 1; for (int i = 2; i <= 5; i++) if (rw[i] > rw[bi]) bi = i;
       if (rw[bi] > 0) rw[bi] = Math.Clamp(rw[bi] * prof.AmpStrongest, 0, 1);
   }
   ```
   This is the hand-roll the review requires — `Fold` produced only the `prof.AmpStrongest` scalar; the amplify-strongest-rule step is ours (mirrors Alchemy's own `Evolve` amp, which is likewise custom code, not `Fold`).

6. **Grid bonus (with the `mundane` conditional).** `_gridBonus` combines the tag `gAcc` (step 3) and the slot-family count (§2.3, §7.1). The `mundane` `G -1` is **not** a pre-sizing additive that could push rows below 3 (the review's no-op-or-contradiction). Resolve it deterministically: fold `mundane` into `gAcc` as `-1` like any other `gridAdd` entry, accumulate `gAcc`, THEN when sizing (§7.1) the final `Math.Clamp(baseRows + _gridBonus, 3, 9)` naturally floors at 3. So `mundane` simply subtracts one bonus tile and the clamp guarantees ≥3 — there is no special "only if it would push below 3" branch; the clamp IS the guard. Set `_gridBonus = (int)Math.Round(gAcc);` (may be negative; the §7.1 clamp handles it). No conditional knob, no ambiguity.

**Precedence for double-role tags** (resolve at table-authoring time — the code has exactly ONE entry per tag per table):
- Tags appearing in two RATIONALE families (e.g. `lightning` in Fire + Energy, `arcane` in Shadow + Energy) get ONE combined entry per table (base table + rule table). The §2.1–2.3 rows are the *rationale*; author the single combined value shown.
- **`power`** is listed both as a Power slot-family tag (§2.3: `T ×0.90` + grid) AND as an Exotic `AmpStrongest ×1.30` tag (§2.2). **Both apply — they are different tables, not a conflict:** `power` gets a `strongExc` entry (`amp["power"]=1.30`, step 2) AND, when it appears as an OUTPUT slot-family tag, contributes `T ×0.90` via the base table + `G +1` via `gridAdd`. There is no "which wins": the amp scalar and the time/grid knobs stack on different channels by design. (Clarifies the review's `energy`/`power` precedence gap.)

**Theme default (never a no-op).** An untested tag with no entry in ANY Engineering table resolves to its elemental-theme default via a discipline-local `ThemeOf(tag)` helper. **This helper is Engineering's own** — it does NOT call `MinigameTagEffects.Resolve` (private, `MinigameTagEffects.cs:237`) or read `MinigameTagEffects.Metal`/`Wood` (private HashSets, lines 229-230); those are inaccessible. Copy the small classification into Engineering as private static sets:
```csharp
private static readonly HashSet<string> ThemeMetal = new(){ "copper","tin","steel","mithril","bronze","adamantine","silver","gold","orichalcum" };
private static readonly HashSet<string> ThemeWood  = new(){ "oak","ash","ironwood","ebony","worldtree","exotic","birch","willow" };
```
`ThemeOf(tag)` returns the default knobs: a metal-set member → Earth default (`R:Immovable +0.14, G +1`); a wood-set member → Life default (`R:Spread +0.20`); anything else → mild `Plus` bias (no change, still playable). This is a copied classification, not a shared API call — no new public surface on `MinigameTagEffects` is required. Guarantees master-plan §1.6: every tag has an interaction.
- **`copper`/`tin` (and the other structural metals)** ARE listed explicitly in the §2.1 Structural-metals base row, so they never reach `ThemeOf`. To avoid the review's double-handling concern, the rule is: **a tag present in ANY Engineering table is handled by that table; `ThemeOf` fires ONLY for tags absent from every table.** `ThemeMetal`/`ThemeWood` are therefore a fallback classifier for *un-tabled* metals/woods only; tabled `copper`/`tin` win via their explicit entry.

**Consistency guard (the crisp, testable form — encoded in test 6, §10.1):**
- **The clock (`_timeMult > 1`) is granted by WATER ONLY.** No other theme — not even temporal — grows time. Temporal expresses its "control a knob / deliberate pace" verb through MOVES + a freeze-tile (`_moveMult>1` + `R:Single`), NOT the clock (§2.2), so water is the single, sole clock-grower. earth/life/air/harmony/temporal/quality/gentle-goal all express their "unhurried/gentle/slow/deliberate" character through MOVES (`_moveMult`), the rule mix, or grid size, never the clock. This is the single rule that prevents the ice-borrows-water (and temporal-borrows-water) violation from recurring anywhere.
- Fire (and fire riders lightning/dangerous) NEVER grow time — `_timeMult < 1` only.
- Ice NEVER touches the clock at all — ice sets `_moveMult`/`Rx < 1` only (its former `T ×1.10` is deleted).
- Earth NEVER adds `Spread`; life NEVER adds `Immovable`; etc. — each theme owns its rules.

If a future edit makes fire calm the board, ice extend the clock, or ANY non-water tag (temporal included) grow `_timeMult`, the edit is wrong (master plan §2 final rule) and test 6 fails.

---

## 3. STATE MACHINE

```
        Begin()                [Space]/button              POWER ON              solved OR budget/time out
Ready ───────────► (splash) ─────────────────► Plan ──────────────► Play ───────────────────────────► Settle ──(SettleDuration)──► Done → Finish(perf)
  ▲                                              ▲                     │                                                              
  └─ OnBegin resets all state ──────────────────┘        (undo / re-plan within Play)                                               
```

| From | To | Trigger | Actions |
|------|----|---------|---------|
| — | Ready | `OnBegin()` | Interp params (§7), `ApplyTagProfile` (§2), `BuildBoard` (§4.1), `_readyBox.Visible=true`, `HideTimer()`, `SetQuality(0)`, `_dev.BeginSession(...)`. |
| Ready | Plan | [Space] or "OPEN THE BENCH" pressed | `_readyBox.Visible=false`, `_phase=Plan`, `_goButton.Visible=true`, header sub = board dims + `budget N`. Clock stays hidden. |
| Plan | Play | `_goButton` "POWER ON" pressed (always enabled — you may commit an empty plan, it just scores low) | Apply all `_planGhosts` in queue order (each = one committed flip via `ApplyFlip`, spends a move), clear ghosts, `_phase=Play`, `_timeLeft=_timeBudget`, `_undoLeft=_undoCharges`, `SetTimer`, `_goButton.Visible=false`. |
| Play | Play | flip / undo / arrow-move | see §5; each committed flip: `ApplyFlip`, `_movesSpent++`, recompute matched cells, `UpdateLiveQuality`. |
| Play | Settle | `AllMatched()` **OR** `_movesSpent >= _moveBudget` **OR** `_timeLeft <= 0` | compute `_finalPerf` (§4.5), `_phase=Settle`, `_settleT=0`, cascade VFX, `SetQuality(_finalPerf)`. |
| Settle | Done | `_settleT >= SettleDuration` | `Popup` band name, `Finish(_finalPerf)`. |
| any (running) | (abandon) | double-[Esc] within 1.5s | handled by BASE `MinigameOverlay._UnhandledInput` → `onAbandon` (materials lost). Circuit Lights adds nothing here. |

Notes:
- **No hard fail.** Running out of moves/time still routes to Settle with a coverage-floor perf (§4.5). `FailCraft()` is NEVER called — a partially-correct device is still a device (master plan §3.4 "gradient of correctness, not solved/unsolved").
- **Limited live re-plan** (master plan §3.4 roadblock 3): in Play you may flip (spend moves) and undo (spend an undo charge). You cannot return to Plan. Undo is available whenever water tags granted a charge; for the common no-water case a **minimum baseline of `_undoCharges` still applies** so re-plan is never fully absent — see §1.4 and R3.

**Overrides to DELETE from the current file.** The rebuild removes the `EngineeringMinigame._Process(double)` override (`EngineeringMinigame.cs:310`) entirely. That override existed only to reveal the old `_goButton` when `_reachOut` became true (a Flow-Router concept that no longer exists). Do NOT keep it: leaving the old `_Process` alongside new `OnTick` logic would call `base._Process` twice / diverge the shake+meter drive. All per-frame work now lives in the base `_Process` → `OnTick(delta)` seam (`MinigameOverlay.cs:305`, which the base calls once while `Running`). The `_goButton.Visible` reveal is handled purely by the **state-machine transitions**, not by any per-frame check:
- Ready → Plan (Space/OPEN THE BENCH): set `_goButton.Visible = true` (the button is always enabled — POWER ON may commit an empty plan; §3 transition table).
- Plan → Play (POWER ON): set `_goButton.Visible = false`.
- OnBegin: `_goButton.Visible = false` (splash is up).
There is no `_reachOut`-style gate — Circuit Lights has no "connection" precondition, so the button never needs a per-frame visibility recompute.

---

## 4. TICK MATH — every formula, named constants + starting values

Named constants (all `private const`, in `EngineeringMinigame`):

| Const | Value | Unit | Role |
|-------|-------|------|------|
| `SettleDuration` | `0.9` | s | Settle freeze-frame length |
| `MatchPulseDecay` | `2.5` | 1/s | per-cell match glow decay |
| `LiveTravelW` | `0.75` | — | live-quality weight on coverage (mirrors final) |
| `LiveElegW` | `0.15` | — | live weight on move elegance |
| `LiveTimeW` | `0.10` | — | live weight on time elegance |
| `PerfCoverageW` | `0.75` | — | final: cells-matched fraction weight |
| `PerfMoveW` | `0.15` | — | final: move elegance weight |
| `PerfTimeW` | `0.10` | — | final: time elegance weight |
| `CoverageFloorCap` | `0.55` | — | max perf a coverage-only (no elegance) run can reach |
| `MashCoverageBaseline` | `0.40` | — | expected coverage from random flipping (calibration target) |
| `SlackBase` | `4` | flips | budget slack at entry |
| `SlackHardMin` | `2` | flips | budget slack at legendary (before tag mult) — kept ≥2 so ice's `_moveMult<1` still visibly bites at max difficulty (§4.3) |
| `TargetLitFrac` | `0.50` | — | per-cell probability a target cell is lit (§4.1a — target is a real pattern, not all-off) |
| `UndoBaseline` | `1` | charges | minimum `_undoLeft` every recipe gets (R3 re-plan floor, even with zero water tags) |

### 4.1 Board generation (guaranteed solvable within budget)

Lights-Out with an arbitrary neighbourhood (Plus/Spread/Single/Invert/Wild) is a **linear system over GF(2)**: each flip is a fixed toggle vector; a target is reachable iff it lies in the column space of the flip matrix `A` (columns = flip vectors, rows = cells). To *guarantee* solvability within a move budget WITHOUT solving GF(2) live, generate the target BY flipping:

```
1. Seed a NON-TRIVIAL target: for each cell, _target[r,c] = (_rng.Randf() < TargetLitFrac).  // TargetLitFrac §4.1a
2. Seed _rule[r,c] from _ruleWeights (weighted _rng pick per cell); set _wildExtra for Wild tiles.
3. _state = copy(_target)                       // start AT the goal
4. Pick _scramble distinct cells (weighted toward non-Immovable, since Immovable can't be player-flipped);
   apply ApplyFlip on each into _state (NOT counting moves).  // now _state is scrambled AWAY from goal
5. _minSolution = (# of those scramble flips that were on FLIPPABLE tiles)   // an UPPER BOUND on the solve
   (because re-applying the same flip set returns _state→_target; each flip is its own inverse over GF(2)).
6. _moveBudget = _minSolution + slack   (slack from §4.3).   // budget ≥ a known solution ⇒ SOLVABLE in budget.
```

**The target is a real seeded pattern, NOT all-off.** `_target` is a per-cell coin-flip at density `TargetLitFrac` (§4.1a), seeded from `_rng` (§8), so the goal is a distinct lit/unlit pattern the player must reproduce — not the trivial "make everything dark." This is what makes element #2 (Plan hides mismatch to avoid solving-by-colour), element #9 (target ghost overlay), and R-VIS (target recall on large boards) all meaningful. It also makes the masher baseline derivable (§4.1b). Solvability is unaffected: any target reachable by flipping from itself is trivially reachable (0 flips before scramble), and after scramble the recorded set re-applied still returns `_state→_target`.

**§4.1a `TargetLitFrac`.** `TargetLitFrac = 0.5` (const). A 50% lit target maximises pattern entropy (hardest to memorise-by-eye, most legitimate goal) and makes the masher's expected coverage exactly derivable (§4.1b). It is NOT difficulty-scaled — difficulty scales grid size, scramble depth, and budget tightness (§7), not target density. (If a future playtest wants sparser goals on tiny boards, this is the one const to touch; leave at 0.5 for ship.)

**§4.1b Masher-coverage derivation (grounds `MashCoverageBaseline`).** After generation, `_state` differs from `_target` in exactly the cells net-toggled an odd number of times by the `_scramble` flips. A masher who flips random cells ignoring the target performs a random walk in GF(2) space; because each flip is its own inverse and the flip vectors span a large subspace, the masher's end `_state` is effectively a uniform-random pattern **uncorrelated** with `_target`. Two independent uniform-random binary patterns agree on each cell with probability 0.5 → expected `MatchedFrac ≈ 0.5`. BUT a masher spends the whole budget (so ~`_moveBudget` random flips over a board of `_rows·_cols` cells); for small boards/short budgets the walk under-mixes and coverage sits slightly BELOW 0.5. Empirically (and by the test-3 calibration band, §10.3) this lands at ~`0.40` across the difficulty range — hence `MashCoverageBaseline = 0.40`. **Tuning procedure if a headless run misses [0.35,0.45]:** the coverage is a monotone function of `budget/cells` (more random flips → closer to 0.5) and `_scramble` (deeper scramble → the masher starts further away). To LOWER masher coverage, reduce `slack` (const `SlackBase`); to RAISE it, increase `slack`. `_scramble` sets the *floor* of `_minSolution` (difficulty), so tune SLACK, not scramble, for the masher band. This is the concrete relationship the review asked for — 0.40 is derived (0.5 ceiling, under-mixing pulls it to ~0.4), not magic.

**Why solvability is correct:** every `TileRule` toggle is an involution over GF(2) (applying it twice = identity), including `Invert` (its ≤13-cell blast toggles each affected cell exactly once, so re-applying returns the board — §4.2). The only non-involutive rule is `Immovable`, which is never a player flip (and step 4 excludes it from the scramble set). So the exact scramble set re-applied is a guaranteed solution of length ≤ `_scramble`. Therefore a budget of `_scramble + slack` ALWAYS admits a solution. Solvability is generator-guaranteed; no live GF(2) needed. (If any scramble cell landed on an `Immovable`, exclude it from `_minSolution` since the player can't reproduce it — but scramble in step 4 already avoids Immovable-direct flips, so the reproduced set is always player-executable.)

**§4.1c Scramble-cell selection weight (concrete).** Step 4's "weighted toward non-Immovable": build the candidate list = all cells with `_rule != Immovable`, assign each a uniform weight 1.0, and draw `_scramble` DISTINCT cells without replacement via `_rng` (Fisher–Yates shuffle of the candidate list, take the first `_scramble`). No cell-position weighting beyond excluding Immovable — uniform over flippable cells. If a scramble flip's ripple happens to toggle an Immovable NEIGHBOUR, that is fine and intended: Immovable cells DO receive neighbour-toggles during scramble (they are only forbidden as the DIRECT target of a flip, §4.2), and re-applying the identical flip set re-toggles that same Immovable neighbour identically, so `_state→_target` still holds. The coder does not special-case Immovable neighbours.

**Randomness telegraph:** the scrambled start IS the puzzle the player sees in Plan (no hidden reshuffle). `Wild` extra-cells are drawn as a dotted tether (§6) so their "random" extra toggle is a TELL, not a betrayal.

### 4.2 Flip semantics — `ApplyFlip(int r,int c, bool countMove)`

For a flip at `(r,c)` with rule `_rule[r,c]`, build the affected-cell list `cells`:

| Rule | `cells` | Per-cell op |
|------|---------|-------------|
| `Plus` | self + 4 orthogonal (in-bounds) | toggle once (`_state ^= true`) |
| `Single` | self only | toggle once |
| `Spread` | self + 8 Moore neighbours (in-bounds) | toggle once |
| `Immovable` | **direct flip forbidden** — `ApplyFlip` returns false, no move spent. (Immovable cells are only ever toggled as NEIGHBOURS of other rules' flips.) | — |
| `Invert` | self + 8 Moore neighbours + the 4 orthogonal cells at distance 2 (the "curse ring": `(r±2,c)`,`(r,c±2)`), all in-bounds → up to **13 cells** | toggle **once** each. A genuinely WIDE blast: bigger reach than Spread. **This is real risk, not cosmetic** — every one of those 13 cells actually changes state, so a mis-placed Invert flips far more cells away from the target than a Plus ever could (the shadow "entropy/risk"), while a well-placed one clears a whole neighbourhood in one move (the "hidden power" reward). Net state effect is distinct from BOTH `Single` (1 cell) and `Plus` (5 cells). Still a GF(2) involution: each of the ≤13 cells is toggled exactly once, so applying the same Invert flip twice returns the board (needed for §4.1 solvability + the §10.3 involution test). |
| `Wild` | self + 4 orthogonal + `_wildExtra[r,c]` (if valid) | toggle once each |

After toggles: for each cell whose `_state[c]==_target[c]` transitioned true, set `_matchPulse[cell]=1`. If `countMove` and the flip was legal (not Immovable), do NOT increment here — the caller increments `_movesSpent` (keeps Plan-ghost application and Play commit uniform).

`AllMatched()` = `∀ cell: _state[r,c] == _target[r,c]`.
`MatchedFrac()` = `(# cells where _state==_target) / (_rows*_cols)` ∈ [0,1].

### 4.3 Move budget

```
slackRaw   = SlackBase + (SlackHardMin - SlackBase) * DiffFrac          // 4 → 2 across difficulty (DiffFrac §7)
slack      = Math.Max(1, (int)Math.Round(slackRaw * _moveMult))          // _moveMult: ice shrinks, water grows
_moveBudget = _minSolution + slack
```
Shown as a number (house-rule exception). Displayed `moves N/_moveBudget` and a pip row (§6). Over-budget is impossible — reaching `_movesSpent==_moveBudget` ends the run (Settle).

**Ice still bites at max difficulty (resolves the "ice vanishes where it matters" gap).** With `SlackHardMin = 2`, legendary `slackRaw = 2`. Ice's `_moveMult` reaches ~0.66 (`frozen`): `round(2×0.66)=round(1.32)=1` vs the no-ice `round(2×1.0)=2` — a real 1-flip reduction that survives the `Max(1,·)` floor. (The former `SlackHardMin=1` collapsed both to 1, hiding ice; raising the floor to 2 is the fix.) The budget can never drop below `_minSolution + 1`, so a known solution always fits (§4.1). Ice therefore ALWAYS removes at least one slack flip whenever `_moveMult ≤ 0.75`, at every difficulty — the "fewer MOVES" manifestation is never silently a no-op.

### 4.4 Time budget

```
timeRaw    = 40 + (16 - 40) * DiffFrac        // 40s → 16s across difficulty
_timeBudget = Math.Clamp(timeRaw * _timeMult, 8, 60)   // _timeMult: fire shrinks, water grows (sole clock-grower)
```
Only counts down in Play. `SetTimer(_timeLeft, warnAt: Math.Min(8, _timeBudget*0.25))`. Time is a BAR/feel + the base timer readout (the base overlay's timer is allowed — it's the standard header element; it is not an Engineering-specific added number).

### 4.5 Scoring

**Live (during Play), every committed flip / each 0.25s tick:**
```
coverage = MatchedFrac()
moveEleg = Clamp((_moveBudget - _movesSpent) / _moveBudget, 0, 1)         // unspent budget fraction
timeEleg = Clamp(_timeLeft / _timeBudget, 0, 1)
live = LiveTravelW*coverage + LiveElegW*moveEleg + LiveTimeW*timeEleg
SetQuality(Clamp(live, 0, 0.97))                                          // cap <1 until Settle confirms
```

**Final (at Settle entry):**
```
coverage = MatchedFrac()
solved   = AllMatched()
moveEleg = Clamp((_moveBudget - _movesSpent) / Math.Max(1,_moveBudget), 0, 1)
timeEleg = Clamp(_timeLeft / _timeBudget, 0, 1)                           // 0 if timed out
perf = PerfCoverageW*coverage + PerfMoveW*moveEleg + PerfTimeW*timeEleg   // 0.75/0.15/0.10
if (!solved) perf = Math.Min(perf, CoverageFloorCap)                      // elegance only pays off on a solve
_finalPerf = Clamp(perf, 0, 1)
```
Rationale (master plan §3.4 formula `0.75·cellsMatchedFrac + 0.15·moveElegance + 0.10·timeElegance`): matches the plan exactly. The `CoverageFloorCap` on non-solves ensures elegance can't inflate a partial; a fully-solved board with spare moves+time → ~1.0.

**Calibration targets (must hit — if a headless run misses the masher band, tune SLACK per the §4.1b procedure, NOT `_scramble`):**
| Player | Behaviour | Expected perf |
|--------|-----------|---------------|
| **Masher** | random flips, ignores target, likely doesn't fully solve | coverage ≈ `MashCoverageBaseline` (0.40, **derived** in §4.1b: two uncorrelated 50%-lit patterns agree ~0.5, under-mixing on small boards pulls it to ~0.4) → `perf ≈ 0.75*0.40 = 0.30`, capped `≤0.55`. Floor delivers ~0.30. |
| **Competent** | solves the board, spends most of budget/time | solved, moveEleg≈0.2, timeEleg≈0.3 → `perf ≈ 0.75 + 0.15*0.2 + 0.10*0.3 = 0.81`. |
| **Expert** | solves in ~minimal moves with time to spare | solved, moveEleg≈0.8, timeEleg≈0.6 → `perf ≈ 0.75 + 0.15*0.8 + 0.10*0.6 = 0.93`. |

---

## 5. INPUT MAP

**Godot input-pipeline placement — the load-bearing point.** Godot delivers an input event through three stages in this order: `_Input` (earliest, sees ALL input before any Control) → focused-Control `GuiInput`/`_gui_input` → `_UnhandledInput` (latest, only fires for input NOT already consumed). The base `MinigameOverlay` handles [Esc] and forwards gameplay by overriding **`_UnhandledInput`**, which then calls the virtual **`OnInput`** (`MinigameOverlay.cs:308-331`). That is the LATE stage: it is skipped entirely whenever a focused Control (e.g. the `_dev` notes `LineEdit`) or an earlier `_Input` override has already consumed the key. **The world's global F1/F7 debug handler also lives in `_UnhandledInput`**, so a key routed only through `OnInput` can lose the race and reach the world handler.

Therefore F1/F7 MUST be claimed in an **`_Input` override** (the earliest stage — exactly as `AlchemyMinigame._Input`, `AlchemyMinigame.cs:250-256`), NOT in `OnInput`. `RefiningMinigame` does gameplay in `OnInput` but does NOT reliably beat the world handler for F1/F7 for this reason — do not copy that part of it. The claim order is:

1. **`_Input(InputEvent)`** (overridden — the EARLIEST stage, runs before every Control and before `_UnhandledInput`). Claims F1/F7 ONLY, so the world debug handler never sees them. Nothing else is done here (so a focused notes box still types normally):

```csharp
public override void _Input(InputEvent e)
{
    if (!Running) return;
    if (e is not InputEventKey { Pressed: true, Echo: false } k) return;
    // claim F1/F7 at the EARLIEST input stage so they never reach the world's global debug handler
    if (_dev.HandleKey(k.PhysicalKeycode)) { _grid.QueueRedraw(); GetViewport().SetInputAsHandled(); }
}
```
2. **`_UnhandledInput`** (base — the LATE stage) handles [Esc]/[Esc-Esc] abandon, then forwards to `OnInput`. Circuit Lights does NOT override `_UnhandledInput`.
3. **`OnInput(InputEvent)`** (overridden — reached via the base `_UnhandledInput` forward, i.e. only for keys no Control consumed) handles ALL gameplay keys. F1/F7 are already consumed upstream in `_Input`, so they never arrive here. Guard against the notes box: if `_dev.NotesEditHasFocus`, suppress gameplay keys (the `LineEdit` grabbed focus via stage-2, so `_UnhandledInput` normally would not fire while it is focused; the guard is belt-and-suspenders for the frame the focus changes):

```csharp
protected override void OnInput(InputEvent e)
{
    if (e is not InputEventKey { Pressed: true, Echo: false } k) return;
    if (_dev.NotesEditHasFocus) return;   // let the notes LineEdit type freely
    switch (k.PhysicalKeycode)
    {
        case Key.Space:
            if (_phase == Phase.Ready) DismissSplash();
            else if (_phase == Phase.Plan) PowerOn();          // Space == POWER ON in Plan
            GetViewport().SetInputAsHandled(); break;
        case Key.Z:  if (_phase == Phase.Play) TryUndo(); GetViewport().SetInputAsHandled(); break;
        case Key.Left:  MoveCursor(0,-1); GetViewport().SetInputAsHandled(); break;
        case Key.Right: MoveCursor(0, 1); GetViewport().SetInputAsHandled(); break;
        case Key.Up:    MoveCursor(-1,0); GetViewport().SetInputAsHandled(); break;
        case Key.Down:  MoveCursor( 1,0); GetViewport().SetInputAsHandled(); break;
        case Key.Enter: case Key.KpEnter: FlipAtCursor(); GetViewport().SetInputAsHandled(); break;
    }
}
```
4. **`_grid.GuiInput += OnGridInput`** (stage-2, focused-Control) handles mouse clicks on the play surface. `_grid.FocusMode = None` so the grid never grabs keyboard focus; keys always fall through to `_Input`/`_UnhandledInput`.

| Input | Phase(s) | Action | Focus / hit-test |
|-------|----------|--------|------------------|
| Left-click a cell | Plan | queue/unqueue a `GhostFlip` (toggle in queue; Immovable cells rejected with a small `Fuse` burst) | `CellAt(mb.Position)` (§ geometry) |
| Left-click a cell | Play | `CommitFlip(r,c)` if flippable & moves remain | `CellAt` |
| Left-click | Settle/Done | ignored | — |
| Arrow keys | Plan/Play | move `_cursor` (clamped in-bounds) | — |
| Enter/KpEnter | Plan/Play | flip `_cursor` cell (queue in Plan, commit in Play) | — |
| Space | Ready | dismiss splash | — |
| Space | Plan | POWER ON | — |
| Z | Play | `TryUndo()` (spend 1 `_undoLeft`, pop `_flipHistory`, re-apply that flip to invert it, `_movesSpent--`) | — |
| F1 | any | `_dev` toggles on-screen log | claimed in the `_Input` override (earliest stage) — beats the world debug handler |
| F7 | any | `_dev` toggles notes box | claimed in the `_Input` override (earliest stage) — beats the world debug handler |
| Esc / Esc-Esc | running | base abandon | base |

`CommitFlip(r,c)`: reject if `_rule==Immovable` (Fuse burst + "locked" popup), if already `_movesSpent>=_moveBudget`, or not running. Else `ApplyFlip(r,c,true)`, push `_flipHistory`, `_movesSpent++`, `_flipCount[r,c]++`, `Burst` copper, recompute matched, `UpdateLiveQuality`, check end (§3). If `AllMatched()` → straight to Settle.

**Focus rule:** the `_grid` control has `FocusMode = None`; the overlay is modal (`UiHub.OpenScreens++`). F1/F7 are claimed in `_Input` (stage 1); gameplay keys flow to `OnInput` via the base `_UnhandledInput` forward (stage 3) — reached because no non-notes Control holds focus. The `_dev` notes `LineEdit` (built via `BuildNotesPanel(_grid)`) is the only focusable child; while `NotesEditHasFocus`, it consumes keys at stage 2 (so `_UnhandledInput`/`OnInput` never see them) AND `OnInput` guards on `_dev.NotesEditHasFocus` for the focus-transition frame.

---

## 6. VISUAL SPEC — every drawn element

**Discipline theme (from `CraftStyle.All["engineering"]`):** glyph `⚙`, Accent `Blueprint`=(0.55,0.78,0.98), backdrop Top (0.06,0.10,0.15) / Bottom (0.02,0.03,0.05) / Glow (0.4,0.7,1), Ember (0.55,0.82,1). All new colours below are theme-sourced or derived via `CraftColor`. The base overlay draws the backdrop (shader + `CraftFx.GradientBackdrop` fallback), header (glyph/title/stars/timer), the 5-band quality meter, ambient embers, and shake — the subclass never redraws those.

**Palette (private static readonly Color):**
| Name | Value | Source |
|------|-------|--------|
| `Blueprint` | (0.55,0.78,0.98) | = engineering Accent |
| `LitCol` | `CraftColor.Brighten(theme.Glow, 0.15f)` ≈ (0.55,0.85,1) | lit tile core |
| `DarkCol` | (0.10,0.13,0.19) | unlit tile fill |
| `MatchCol` | `UiTheme.Rarity["uncommon"]` (0.45,0.9,0.45) | cell matches target |
| `MismatchCol`| `UiTheme.Rarity["legendary"].Lerp(DarkCol, 0.25f)` ≈ (0.80,0.54,0.24) | cell != target (a "still wrong" warm cue). "Tinted" is defined: lerp the legendary warm-gold 25% toward `DarkCol` so it reads as a muted warning, not a bright celebratory gold. Verifiable against `Color.Lerp`. |
| `GhostCol` | (Blueprint, α 0.5) | queued Plan ghost |
| `ImmovableCol`| (0.42,0.40,0.36) | earth heavy tile frame |
| `WildCol` | `UiTheme.Rarity["epic"]` (0.78,0.45,0.98) | wild/invert rule accents |
| `Fuse` | (1,0.4,0.32) | reject/over cue |

### 6.0 Container wiring — how `_hud`/`_grid`/chrome mount in the base card (the coder does NOT invent this)

`BuildUi(VBoxContainer host)` is called by the base with `host` = the left column of the card's `contentRow` (the quality meter is the right column, mounted by the base — `MinigameOverlay.cs:154-160`). `host` has `separation = 8` and `SizeFlagsHorizontal = ExpandFill`. Add children to `host` **in this exact top-to-bottom order** (a `VBoxContainer` stacks children vertically in add order):

1. **`_hud`** — `new Control { CustomMinimumSize = new Vector2(560, 54) }`. `_hud.Draw += DrawHud`. The move-number + pips + time bar + correctness bar (§6.4). Mounted FIRST so it sits directly under the card header, above the board.
2. **`_grid`** — `new Control { CustomMinimumSize = new Vector2(560, 420), SizeFlagsHorizontal = ShrinkCenter, FocusMode = None }`. `_grid.Draw += DrawGrid`; `_grid.GuiInput += OnGridInput`. The play surface.
3. **`_hint`** — `new Label { … }`, `font_size 13`, centered, the one-line control hint. Text swaps per phase (§6.4 note).
4. **`_goButton`** — "POWER ON ▸", `FocusMode = None`, `Pressed += PowerOn`. `Visible=false` until Ready→Plan.
5. **`_readyBox`** — `VBoxContainer` splash (`_readyLabel` + "OPEN THE BENCH ▸ [Space]" button). Shown over the column while `Phase.Ready`; hidden on dismiss. (It is a sibling in the same `host` column — when visible the board is still behind it; that is fine, `_readyBox` is opaque-enough chrome and `_phase==Ready` suppresses grid input.)
6. **`_dev.BuildNotesPanel(_grid)`** — mounts the hidden F7 notes `LineEdit` as a child of `_grid` (centered-bottom, `MinigameDevLog.cs:62-63`). It is the only focusable child (§5 focus rule).

No manual anchors are needed: the `VBoxContainer` lays the five out top-to-bottom by their `CustomMinimumSize`; `_grid` expands to fill. The board is drawn in `_grid`-local space (`G = _grid.Size`, §6.1); the HUD in `_hud`-local space (`w = _hud.Size.X`, §6.4). The two Controls are independent draw surfaces — no shared coordinate space, so `DrawHud` and `DrawGrid` never need to reconcile offsets.

**Base header timer vs `_hud` move-number — no conflict.** The base card HEADER (built by `MinigameOverlay.BuildHeader`, a separate bar ABOVE `contentRow`) owns the `12.3s` countdown via `SetTimer`/`HideTimer` — that is the shared per-discipline timer readout, not an Engineering number. The `_hud` (inside `host`, below the header) owns the **move-count number** (`moves N/budget`) — the ONE Engineering-specific scored number the house rule permits. They live on different Controls at different heights and display different quantities (time vs moves), so there is no double-timer and no overlap. Engineering calls `SetTimer(_timeLeft, …)` only during Play (§4.4) and `HideTimer()` otherwise.

### 6.1 Layout (resolution-relative; all inside the `_grid` Control local space, size `G = _grid.Size`)

Geometry helpers (reuse the existing ones verbatim):
- `Cell() = Mathf.Min((G.X - 44)/_cols, (G.Y - 44)/_rows)` → square tile side `s`.
- `Origin() = ((G.X - _cols*s)*0.5, (G.Y - _rows*s)*0.5)` → centered board.
- `CellRect(r,c) = Rect2(Origin() + (c*s, r*s) + (3,3), (s-6, s-6))`.
- `CellCenter(r,c) = Origin() + (c*s + s/2, r*s + s/2)`.
- `CellAt(p)` = floor `((p - Origin())/s)` → `(r,c)` if in bounds else null.

### 6.2 Draw order (z within `DrawGrid`, painted back→front)

| # | Element | Rect / pos | Colour | CraftFx / draw primitive | Legality |
|---|---------|-----------|--------|--------------------------|----------|
| 0 | Board backing panel | `Rect2(Origin()-(8,8), (_cols*s+16,_rows*s+16))` | bg (0.05,0.08,0.13,0.85), border (Blueprint,α0.35) | `CraftFx.RoundRect(...,2,12)` | always |
| 1 | Tile fill | `CellRect(r,c)` | `_state? LitCol : DarkCol` | `CraftFx.RoundRect(...,radius 8)` | always |
| 2 | Tile match/mismatch edge | `CellRect(r,c)` outline | `_state==_target ? MatchCol : MismatchCol` (α 0.7) | `CraftFx.RoundRect(rect, transparent, border, bw=2, 8)` | **only in Play/Settle.** Meaningful because `_target` is a real pattern (§4.1): a matched cell (green edge) vs a still-wrong cell (warm edge) is genuine information the player earns by reading the tile against the goal. Plan draws a neutral (0.3,0.33,0.4) edge instead — so during planning you must reason from the target ghost (#9) rather than have the answer coloured in, but during execution the live match feedback rewards attention. |
| 3 | Lit glow | `CellCenter` | `LitCol` α0.25 | `CraftFx.Glow(_grid, ctr, s*0.42f, col, 3)` | only when `_state[r,c]` |
| 4 | Match pulse ring | `CellCenter` | `MatchCol` | `CraftFx.RingPulse(_grid, ctr, s*0.3f, 1-_matchPulse, col, 2.5f, 0.6f)` | only when `_matchPulse>0.02` |
| 5 | Rule glyph badge | top-left of `CellRect` (inset 5px) | per-rule | see §6.3 | always (rule is a persistent tell) |
| 6 | Wild tether | dotted line `CellCenter → CellCenter(_wildExtra)` | `WildCol` α0.5 | `CraftFx.Streak(from,to,col,2f,segs=8)` | only for `Wild` with valid extra, and only in Plan+Play |
| 7 | Plan ghost | `CellCenter` | `GhostCol` | `CraftFx.Ring(_grid, ctr, s*0.28f, GhostCol, 2f)` + small order-badge `DrawString` of `Order+1` | only in Plan, for queued flips |
| 8 | Cursor | `CellRect(_cursor)` outline | `UiTheme.Accent` (1,0.84,0.30) | `CraftFx.RoundRect(rect, transparent, Accent, bw=3, 8)` | Plan/Play |
| 9 | Target ghost dot | small faint dot in the TOP-RIGHT corner of `CellRect`, drawn ONLY where `_target[r,c]` is lit | `GhostCol` (Blueprint, α0.3) | `_grid.DrawCircle(CellRect.End - (5,−5), 3f, col)` | **always on (Plan + Play + Settle).** Chosen per §9 R-VIS: since `_target` is a real pattern, the goal must stay visible at all times so the player never loses it on a 9×9. The dot is faint and corner-offset so it never competes with the tile's own lit/unlit fill (#1) or the match edge (#2). This is the sole target read; there is no separate Plan-only preview. |

### 6.3 Rule glyph badges (element #5) — 14px `DrawString`, tinted, top-left inset

**Font-safety: use ASCII badge letters, NOT decorative Unicode.** The theme default font (`GetThemeDefaultFont()`) is only verified to render ASCII (the current file draws "IN"/"OUT"). Fancy glyphs (`✳ ▦ ⊘ ✦`) risk rendering as tofu (□). So each rule's badge is a **1–2 char ASCII code** plus a distinct SHAPE drawn with `CraftFx`/`DrawXxx` primitives (the shape, not the letter, is the primary tell — the letter is a redundant label). This removes the tofu risk entirely.

| Rule | ASCII badge | Colour | Primary shape tell (drawn, font-independent) |
|------|-------------|--------|----------------------------------------------|
| `Plus` | `+` | Blueprint α0.6 | the `+` char reads fine; no extra shape |
| `Single`| `.` | (0.7,0.9,1) | a small filled `DrawCircle(badgePos, 2f)` dot |
| `Spread`| `S` | `UiTheme.Rarity["uncommon"]` | faint `CraftFx.Ring(ctr, s*0.4f, MatchCol α0.25, 1f)` showing the 8-reach |
| `Immovable`| `X` | ImmovableCol | thicker frame `CraftFx.RoundRect(CellRect, transparent, ImmovableCol, bw=2, 8)` |
| `Invert`| `!` | WildCol | a `CraftFx.Ring(ctr, s*0.46f, WildCol α0.3, 1.5f)` — a WIDER ring than Spread's, telegraphing the 13-cell curse-blast reach so the risk is legible pre-commit |
| `Wild` | `?` | WildCol | animated badge alpha `0.5+0.4*sin(_anim*6)`; plus the dotted tether (#6) to `_wildExtra` |

The `⚙` discipline glyph in the header comes from `CraftStyle` and is the base overlay's concern (already shipped/rendered), not a badge — no ASCII substitution needed there. `IN`/`OUT` port labels are gone (Circuit Lights has no ports).

### 6.4 HUD (`_hud` Control, drawn in `DrawHud`, above the grid, size `(560,54)`)

| Element | Rect | Colour | Primitive | House-rule note |
|---------|------|--------|-----------|-----------------|
| Move-count NUMBER | left, `(6,20)` | `remaining>0 ? (0.7,0.82,1) : Fuse` | `DrawString(font, ..., $"moves {_moveBudget-_movesSpent}/{_moveBudget}", 16px)` | **allowed number** (direct scoring metric) |
| Move pip row | `y=36`, pips every 15px from x=6 | spent (0.28,0.30,0.36) / available Blueprint | `_hud.DrawCircle(cx, 36, 4.5f, col)` per budget slot | reinforces the number as feel |
| Time bar | right third, `Rect2(w*0.62, 14, w*0.34, 12)` | track (0.12,0.13,0.18), fill lerp green→Fuse by `1-timeEleg` | `CraftFx.Bar(_hud, rect, timeEleg, track, fill)` | time is a BAR (not a number here; base header timer is the standard readout) |
| Correctness bar | center, `Rect2(w*0.32, 14, w*0.26, 12)` | track, fill `MatchCol` | `CraftFx.Bar(_hud, rect, MatchedFrac(), track, MatchCol)` | correctness is a BAR (not a number) |

The base header **timer** (`SetTimer`) shows the standard `12.3s` countdown — this is the shared overlay element every discipline uses, not an Engineering-added number, so it does not violate the house rule.

### 6.5 Animation curves / juice

- Tile flip: on `ApplyFlip`, `CraftFx.Burst(_grid, CellCenter, _state? LitCol:DarkCol, 6, 120f, 0.4f, 3f, 60f)` per affected cell; a `CraftFx.RingPulse` seeded via `_matchPulse`.
- Objective/chain: when a flip newly matches ≥2 cells at once, `Shake(5f)` + `Popup(_grid, ctr-(0,26), "+N", MatchCol, 20)`.
- Solve: on `AllMatched()` → `Shake(13f)`, `CraftFx.Burst(centerOfBoard, MatchCol, 48, 340f)`, `FlashQuality()`, `Popup("POWERED!", theme.Glow, 32)`.
- Settle: over `SettleDuration`, sweep a left→right `CraftFx.Streak` "energise" line across matched cells at `_settleT/SettleDuration`.
- Over-budget attempt / Immovable click: `CraftFx.Burst(ctr, Fuse, 5, 70f)` + `Popup("locked"/"no moves", Fuse, 15)`.
- Idle shimmer: lit tiles pulse glow radius `s*0.42*(0.9+0.1*sin(_anim*3+r+c))`, evaluated inside `DrawGrid` from the free-running `_anim` clock. It does NOT force a per-frame redraw — see the throttle below.

**Redraw throttle (the R4 perf mitigation, concretely).** Add a `_animAcc` (double) field. In `OnTick(delta)`: advance `_anim += delta`; decay `_matchPulse[cell]` by `MatchPulseDecay*delta`; then throttle the animation redraw: `_animAcc += delta; if (_animAcc >= 0.05) { _animAcc = 0; _grid.QueueRedraw(); }`. This caps animated repaints at ~20 Hz regardless of frame rate. State-change events (flip, undo, phase transition, cursor move) call `_grid.QueueRedraw()` immediately (not throttled) so input feels instant. There is NO unconditional per-frame `QueueRedraw`.

**Draw-legality rules:** all `_grid.DrawXxx` calls only inside `DrawGrid` (the `Draw` callback); redraws are requested via `_grid.QueueRedraw()` (immediate on state change, throttled ~20 Hz for animation — above). `Burst`/`Popup` create child nodes (self-freeing) and are called from tick/input, never from `Draw`. Ghost/cursor overlays gated by `_phase` per the §6.2 table; the target dot (#9) and rule badges (#5) draw in all phases.

---

## 7. DIFFICULTY CURVE

`DifficultyPoints` is the single intensity dial (`Begin` arg, from the certified `DifficultyCalculator`). Define once:
```
DiffFrac = Math.Clamp((DifficultyPoints - 1.0) / 79.0, 0.0, 1.0)     // 1pt→0 .. 80pt→1
double Interp(double easy, double hard) => easy + (hard-easy)*DiffFrac;
```

### 7.1 Grid sizing (intensity + slot-count character)

**`_gridBonus` is a SINGLE deterministic accumulator: sum all sources, cap the total, then the final `Math.Clamp(...,3,9)` bounds the grid.** There is no per-source cap and no per-source conditional — the review's "caps per-source vs sums then clamps" ambiguity is resolved as **sum-then-cap-then-clamp**, defined once here:

```
// (A) accumulated in ApplyTagProfile (§2.4 step 6): tag grid deltas + slot-family count.
gAcc   = Σ over tags of (gridAdd[tag] * StackFactor(count))     // earth/quality/'mundane'(-1)/etc — may be negative
slots  = count of the 5 slot families present in OutputTags     // 0..5 (Frames/Function/Power/Modifier/Utility, §2.3)
_gridBonus = Math.Clamp((int)Math.Round(gAcc) + slots, -2, 4)   // TOTAL bonus, capped to [-2, +4]

// (B) sizing (here in §7.1):
baseRows = (int)Math.Round(Interp(3, 8));
baseCols = (int)Math.Round(Interp(3, 8));
_rows = Math.Clamp(baseRows + _gridBonus, 3, 9);
_cols = Math.Clamp(baseCols + _gridBonus, 3, 9);
```

- **Tag grid deltas AND slot-family count both feed the ONE `_gridBonus`** — they are summed, not applied at two different stages. (This removes the double-count the review flagged: §2.1 earth `G+1`, §2.3 slot `+1`, and §2.2 Quality/Grade `G+1` all land in the same `gAcc`+`slots` sum, once.)
- **`_gridBonus` is capped to `[-2, +4]`** so a legendary recipe stacking every source can add at most +4 tiles to the interpolated base — this is the "capped" the old worked example gestured at, now an explicit const range. The final `Math.Clamp(...,3,9)` is the hard floor/ceiling.
- **`mundane`'s `G -1`** flows in as a normal negative `gridAdd` entry (§2.4 step 6); the `[-2,+4]` cap and the `[3,9]` clamp jointly guarantee it can never push the grid below 3. No special branch.
- More slots / higher grade ⇒ bigger grid ⇒ more chains (master-plan §3.4).

### 7.2 Scramble depth & budget tightness

```
_scramble  = (int)Math.Round(Interp(2, 14));              // # generator flips = puzzle depth
slackRaw   = Interp(SlackBase, SlackHardMin);             // 4 → 2
slack      = Math.Max(1, (int)Math.Round(slackRaw * _moveMult));   // ice tightens, water loosens
_moveBudget= _minSolution + slack;
```

### 7.3 Time tightness

```
_timeBudget = Math.Clamp(Interp(40, 16) * _timeMult, 8, 60);       // fire tightens, water loosens (sole clock-grower)
```
Per master plan §3.4 "time budget shrinks with fire-tag weight" — `_timeMult<1` for fire, and `Interp` shrinks it with points regardless.

### 7.4 Rule mix intensity

Tag `_ruleWeights` set the CHARACTER; difficulty raises how MANY non-`Plus` tiles appear:
```
nonPlusChance = Interp(0.15, 0.55);   // fraction of cells that get a non-Plus rule (if tags provide weights)
```

**Per-cell rule selection — the exact algorithm (resolves the additive-weight normalization gap).** `_ruleWeights[1..5]` (Single/Spread/Immovable/Invert/Wild; index 0 = Plus is NOT in the roll) are additive floats each clamped to `[0,1]` (§2.4 step 4); their sum `W = Σ_{i=1..5} _ruleWeights[i]` may be anywhere in `[0,5]`. Per cell:
```
if (W <= 1e-6) { rule = Plus; continue; }              // no tags provided any non-Plus weight → all Plus
if (_rng.Randf() >= nonPlusChance) { rule = Plus; continue; }   // this cell stays Plus
// choose a non-Plus rule by NORMALIZING the weights into a probability distribution:
double roll = _rng.Randf() * W;                         // uniform in [0, W)
double acc = 0;
for (int i = 1; i <= 5; i++) { acc += _ruleWeights[i]; if (roll < acc) { rule = (TileRule)i; break; } }
```
This is a standard weighted pick over the NON-normalized additive weights: dividing the cumulative test by `W` handles any sum (>1, =1, <1) uniformly — there is no "weights must sum to 1" assumption. Edge cases are now total:
- **All weights 0** (`W≤1e-6`): every cell is `Plus` — fully playable (a plain Lights-Out board). The §2.4 theme-default fallback guarantees a bland-but-non-empty recipe still puts *some* weight in (e.g. an unknown metal → Immovable), so `W=0` only occurs for a genuinely tag-less debug board.
- **A single tiny weight + high `nonPlusChance`**: the `roll >= nonPlusChance` gate still makes most cells Plus; the few non-Plus cells all resolve to that single weighted rule (since it is the only nonzero entry, `roll < acc` fires on it). Well-defined, not undefined.
- Immovable is rolled here like any other non-Plus rule; if a cell rolls Immovable it simply cannot be player-flipped (§4.2) — that is intended difficulty, and step-4 scramble avoids DIRECT Immovable flips so solvability holds.

### 7.5 Worked examples (every number traced through the §7.1/§4.3 formulas)

**Entry (1 pt, recipe `["iron","common"]` inputs, `["tool"]` output):**
- `DiffFrac ≈ 0` → `baseRows = baseCols = round(Interp(3,8)) = 3`.
- `_gridBonus`: tag `gAcc` = iron `G +1` (§2.1 Structural metals) + common `G 0` = **+1**; `slots` = `tool` is in the Frames family (§2.3) = **1**. `_gridBonus = Clamp(round(1)+1, -2, 4) = 2`.
- `_rows = _cols = Clamp(3 + 2, 3, 9) = 5`. → **5×5 board.**
- `_scramble = round(Interp(2,14)) = 2`. `slackRaw = Interp(4,2) = 4`. iron→Immovable-leaning, no ice/water so `_moveMult ≈ 1.0` → `slack = Max(1, round(4×1.0)) = 4`. `_moveBudget = _minSolution(≤2) + 4`.
- `_timeMult ≈ 1.0` (no fire/water) → `_timeBudget = Clamp(Interp(40,16)×1.0, 8, 60) = 40s`.
- `nonPlusChance = Interp(0.15,0.55) ≈ 0.15`; `_ruleWeights` has iron→Immovable weight ⇒ a couple of Immovable tiles among mostly Plus.
- **Feel:** solvable in ≤2 flips, budget ~6, 40s clock — gentle entry.

**Legendary (80 pt, recipe `["voidsteel","chaos","legendary"]` inputs, `["weapon","explosive"]` output):**
- `DiffFrac = 1` → `baseRows = baseCols = round(Interp(3,8)) = 8`.
- `_gridBonus`: tag `gAcc` = legendary `G +2` + (voidsteel → `steel` metal `G +1`, `void` shadow `G 0`) = **+3**; `slots` = `weapon`(Function) + `explosive`(Power) = **2**. Raw total 5 → `_gridBonus = Clamp(round(3)+2, -2, 4) = 4` (hits the +4 cap).
- `_rows = _cols = Clamp(8 + 4, 3, 9) = 9`. → **9×9 board** (the cap + the `[3,9]` clamp both engage; no muddle).
- `_scramble = round(Interp(2,14)) = 14`. `slackRaw = Interp(4,2) = 2`. no ice → `_moveMult ≈ 1.0` → `slack = Max(1, round(2×1.0)) = 2`. `_moveBudget = _minSolution(≈14) + 2 = ~16`.
- void→`Invert`, chaos→`Wild` ⇒ `_ruleWeights` heavy on Invert+Wild; `nonPlusChance ≈ 0.55` ⇒ ~half the board is cursed (wide 13-cell Invert blasts) or wild.
- fire/explosive → `_timeMult ≈ 0.72` → `_timeBudget = Clamp(16×0.72, 8, 60) ≈ 11.5s`.
- **Feel:** a 9×9, 14-deep scramble with a tight ~16-move budget and ~11.5s of frantic invert/wild ripples — brutal but generator-solvable. (Note: if this recipe also carried ice, `slack = round(2×0.66)=1`, budget ~15 — one flip tighter, the ice bite from §4.3.)

---

## 8. RANDOMNESS SPEC

**Seed source (reproducible):** derive a deterministic seed from the craft identity so tests replay and the same recipe feels consistent yet a re-craft varies. Build the seed string from `Recipe.OutputId + "|" + string.Join(",", allInputIds) + "|" + string.Join(",", allTags) + "|" + DifficultyPoints.ToString("0")`, hash with a stable FNV-1a over the UTF-8 bytes, and seed `_rng`:
```csharp
_rng = new RandomNumberGenerator();
_rng.Seed = Fnv1a(seedString);      // ulong; stable across runs
```
For `Recipe == null`, seed from `Time.GetTicksMsec()` (debug variety). All board randomness (target pattern, rule assignment, scramble cell choice, wild-extra pick, cursor start) uses `_rng` ONLY — never `GD.Randi()`/`GD.Randf()` (those are non-reproducible). This differs from the current file, which uses `GD.Randi/Randf`; the rebuild replaces them with `_rng` for test determinism.

**What is seeded:** (1) the `_target` pattern (per-cell coin-flip at `TargetLitFrac`, §4.1a), (2) per-cell `TileRule`, (3) the `_scramble` set of cells, (4) `_wildExtra` target per Wild tile, (5) tie-breaks in generation. **What is NOT random:** `TargetLitFrac` itself (fixed 0.5), budgets/time (deterministic from points+tags), scoring. The target is a genuine seeded pattern (NOT all-off) — this is what makes the target ghost (element #9), the Plan mismatch-hide (element #2), and R-VIS meaningful (§6.2, §4.1).

**Bounds:** `_scramble ∈ [2,14]`; rule weights clamped `[0,1]`; wild-extra chosen from in-bounds non-self cells within Chebyshev distance 2. Because the target is generated by flipping (§4.1), the board is ALWAYS solvable within `_moveBudget` regardless of the seed — no seed yields an impossible board.

**Telegraph (tell, not betrayal):**
- The scrambled start IS shown in Plan; no post-Plan reshuffle.
- Every `Wild` tile draws its extra-toggle tether (§6, element 6) so its "random" reach is visible before the player commits.
- `Invert` tiles show the `!` badge + a WIDE curse-ring (§6.3) so the player sees the 13-cell blast reach before committing.
- Rule badges are persistent (drawn every frame), so nothing about a tile's behaviour is hidden.

---

## 9. ROADBLOCK REGISTER (each §3.4 risk → chosen mitigation)

| # | Risk (master plan §3.4) | Chosen mitigation |
|---|-------------------------|-------------------|
| R1 | **Guaranteeing solvability within budget under tag rule variants** (GF(2) reachability). | **Generate-by-flipping** (§4.1): start at the goal, apply `_scramble` involutive flips; re-applying that set is a guaranteed ≤`_scramble`-move solution ⇒ `_moveBudget=_minSolution+slack` always solvable. No live GF(2) solve needed. Immovable excluded from player-flip scramble so the reproduced solution is always executable. |
| R2 | **Rule-variant clarity** (spread/invert/immovable must be obvious). | Persistent per-tile **rule glyph badges** (§6.3) + Spread's faint 8-reach ring + Wild's dotted tether + Immovable's thick frame. A tile's behaviour is always readable pre-commit. |
| R3 | **Plan-vs-execute pacing / limited re-plan.** | Explicit `Ready→Plan(no clock)→Play(clock)` phases (§3). Plan = unlimited free queueing of ghosts. Play = live flips + `_undoLeft` undos. **Re-plan is guaranteed for EVERY recipe, not just water ones:** `_undoCharges = Clamp(round(uAcc) + UndoBaseline, 0, 2)` with `UndoBaseline = 1` (§2.4 step 4, §1.4) — so even a zero-water recipe gets 1 undo (a limited mid-run re-plan, per designer "limited"); water tags stack up to the cap of 2. This closes the review's "re-plan absent for the common no-water case" gap. No return to Plan phase. |
| R4 | **Bigger grids on a Control — draw perf + hit-testing.** | Single `DrawGrid` callback, all primitives are cheap `DrawRect/Line/Circle/Arc` + one `DrawString` glyph per cell (no shaders — confirmed, only the base backdrop shader with its `GradientBackdrop` fallback). Grid capped `9×9=81` cells. Hit-testing is O(1) arithmetic (`CellAt`), not iteration. **Honest redraw budget:** the board redraws (a) on every state change (flip/undo/phase), and (b) at a THROTTLED ~20 Hz for animated elements (idle shimmer, Wild badge pulse, match-pulse decay) — NOT every rendered frame. Throttle via an accumulator in `OnTick`: `_animAcc += delta; if (_animAcc >= 0.05) { _animAcc = 0; _grid.QueueRedraw(); }` (§6.5). At 81 cells × [1 RoundRect fill + up to 3 Glow layers only on the ~40% LIT cells + 1 badge DrawString] × 20 Hz this is a few thousand draw calls/sec — comfortably cheap for Godot's 2D canvas, and the *worst* case (all-lit, all-animated) is bounded and rare. The former "every frame except idle shimmer" claim is corrected: idle shimmer is the throttled path, and it does not run at full frame rate. |
| R5 | **Exact move/time-number UI decision** (§5 fork 2). | **Resolved by designer ruling:** SHOW the move count as a number (`moves N/budget`, §6.4). Time stays a bar + the standard base header timer. Correctness stays a bar. This is the ONLY hard number Engineering adds — house-rule compliant. |
| R-VIS | (impl-surfaced) With a real (non-trivial) target pattern, recalling the goal on a 9×9 during Play could over-tax memory. | **CHOSEN (not deferred): always-on target ghost.** Because `_target` is now a genuine seeded pattern (§4.1), the goal is NOT self-evident and MUST stay visible. Element #9 (§6.2) draws a small, faint target-lit corner dot in EVERY phase (Plan and Play), not Plan-only — so the player always has the goal on-screen without it dominating the tile's own lit/unlit read. This is a decided mechanic, not a playtest fork. (The dot is faint α0.3 and offset to a corner so it never competes with the tile fill; §6.2 element #9 is updated to match.) |
| R-DET | (impl-surfaced) current file uses `GD.Randi/Randf` (non-reproducible). | Replace ALL randomness with a seeded `RandomNumberGenerator` (§8) so headless tests replay boards. |

---

## 10. TEST PLAN

### 10.1 Headless-checkable invariants (xUnit-style, no scene tree — construct board logic via a testable seam)

Refactor board generation + flip math into pure methods callable without Godot nodes (pass `_rng` seed + params in, get arrays out). Tests:

1. **Seam exactly-once.** Drive a full run via a stub `onComplete`/`onAbandon`; assert exactly one of `Finish`/`FailCraft` fires, and `Finish` never with the other. Circuit Lights must NEVER call `FailCraft` (assert `onAbandon` uncalled on every non-Esc path). Perf ∈ [0,1].
2. **Solvability guarantee (R1).** For 10,000 seeds × the difficulty range × representative tag pools: generate board, then re-apply the recorded scramble set; assert `AllMatched()` true and the reproduced move count ≤ `_moveBudget`. NO seed may produce an unsolvable-within-budget board.
3. **Involution + rule-distinctness.** (a) For each `TileRule` except Immovable: applying `ApplyFlip` twice returns `_state` unchanged (GF(2) self-inverse). Immovable: `ApplyFlip` returns false and spends no move. (b) **Distinctness (guards the Invert theme):** on a board large enough to fit the full blast (≥5×5), a single `Invert` flip at an interior cell must change a DIFFERENT set of cells than `Single` (1 cell) AND than `Plus` (5 cells) AND than `Spread` (9 cells) — assert `|toggled(Invert)| > 9` (the 13-cell curse-blast). This test would FAIL if Invert were ever reduced to a self-toggle/cosmetic-ripple, so it actively catches the old "risk is cosmetic" regression rather than silently passing.
4. **Reachability under variants (R1 corollary).** With Invert/Wild/Spread present, the scramble-solution invariant (test 2) still holds (proves the flip vectors' span includes the target).
5. **Budget/time monotonicity (difficulty).** `_moveBudget` slack and `_timeBudget` are monotone non-increasing in `DifficultyPoints` at fixed tags; `_rows*_cols` non-decreasing.
6. **Tag theme guards (§2 consistency).** Assert: fire tags yield `_timeMult<1` and never `>1`; **ice yields `_moveMult<1` AND leaves `_timeMult==1` (ice never touches the clock — the fixed violation)**; water yields `_timeMult>1` and `_undoCharges≥UndoBaseline+1`; earth yields `_gridBonus≥1` and Immovable weight `>0`; life yields Spread weight `>0`; shadow yields Invert weight `>0`; **every recipe (incl. zero-water) yields `_undoCharges≥UndoBaseline` (the R3 re-plan floor)**; **ONLY water tags produce `_timeMult>1` (assert no non-water tag pool — including temporal — grows the clock; temporal instead yields `_moveMult>1`)**. (Directly encodes the §2 "never flip a tag's theme" rule — including ice≠time and water-is-the-SOLE-time-grower — as tests.)
7. **Scoring bands (calibration §4.5).** Simulate masher (random flips) → mean perf ∈ [0.20,0.40]; competent (solved, ~full budget) → ∈ [0.75,0.85]; expert (solved, min moves + spare time) → ∈ [0.90,0.97]. Non-solve perf ≤ `CoverageFloorCap`.
8. **Determinism (§8).** Same seed string ⇒ identical `_rule`, `_scramble`, `_target`, `_wildExtra`, budgets.
9. **Null recipe.** `Recipe==null` builds a playable all-`Plus`-or-themed board (no crash, `_rows,_cols≥3`).

### 10.2 F1/F7 playtest script (manual, via `MinigameDevLog`)

`_dev.Context` returns `$"{_phase} | moves {_movesSpent}/{_moveBudget} | match {MatchedFrac():P0} | {_timeLeft:0.0}s"`. Header lines: recipe id, tags, `DifficultyPoints`, `_rows×_cols`, `_scramble`, `_moveBudget`, `_timeBudget`, dominant rule mix. `_dev.Log(...)` on: phase transitions, each committed flip (cell + rule + Δmatched), each undo, solve/timeout/budget-out, final perf.

Playtest checklist (log an F7 note at each):
1. Entry board (1 pt) solvable calmly within budget; masher gets ~0.3, careful play ~0.8+.
2. Fire recipe visibly tightens the clock; note whether ~11s feels frantic-fair. (Confirm ice recipes do NOT extend the clock — theme guard.)
3. Ice recipe visibly cuts the MOVE budget (not the clock); note whether "plan harder" reads even at legendary (the `SlackHardMin=2` bite, §4.3).
4. Earth recipe: Immovable tiles obvious? bigger grid feel stable?
5. Life recipe: Spread 8-reach ring readable? cascades satisfying?
6. Shadow recipe: Invert's WIDE 13-cell curse-blast — does the wider curse-ring badge (§6.3) telegraph the risk before commit? Does a well-placed Invert feel like a rewarding cluster-clear and a mis-placed one like a real setback (high-risk/high-reward, not cosmetic)?
7. Wild tether: does the extra-toggle telegraph read before commit?
8. 9×9 legendary: draw perf ok at the ~20 Hz throttle (§6.5/R4)? Target ghost dots (#9, always-on) keep the goal readable without clutter?
9. Move-count number: does it read as the scored resource (house-rule intent)?
10. Undo: confirm a zero-water recipe still grants ≥1 undo (R3 re-plan floor) and it feels like a real mid-run correction.

---

## 11. REUSE MAP

### 11.1 Shared toolkit calls used (exact list)

| Toolkit | Calls used |
|---------|-----------|
| `MinigameOverlay` (base) | `Begin/Finish` seam; `SetQuality`, `FlashQuality`, `Shake`, `SetTimer`, `HideTimer`, `SetHeaderSub`, `Popup`, `Burst`; `OnBegin`/`OnTick`/`OnInput`/`BuildUi` overrides; `Discipline="engineering"`; base backdrop/header/meter/ambient/shake. NOT `FullscreenScene` (stays a card — bigger `_grid` min-size). |
| `MinigameModifierCommon` | `StackFactor(n)`; `new ModProfile(6, 0)`; `Fold(prof, counts, engBase, chExc: null, stExc: null, strongExc: amp)` — folds ONLY the `Time`(=`_timeMult`) and `Rx`(=`_moveMult`) `×` scalars + the `AmpStrongest` scalar (NOT `Ch[]`, since `R:` weights are additive — §2.4); `Clamp(prof, timeLo: 0.55, timeHi: 1.6, rxLo: 0.6, rxHi: 1.35)` using the REAL NAMED args (no positional 4-arg overload exists). The additive `R:`/`U`/`G` knobs and the amplify-strongest-rule pass are hand-rolled over `counts` (§2.4 steps 3–6), not via `Fold`. |
| `MinigameDevLog` | `new MinigameDevLog("engineering")`, `BuildNotesPanel(_grid)`, `HandleKey`, `NotesEditHasFocus`, `BeginSession`, `Log`, `Note`, `DrawLog`, `Context`. F1/F7 claimed in the **`_Input` override** (earliest stage) before world debug — NOT `OnInput` (§5). |
| `CraftFx` | `RoundRect` (board/tile fills, borders), `Glow` (lit tiles, badge rings), `Bar` (time/correctness HUD bars), `Ring` (Spread reach, Invert curse-ring, Wild tell), `RingPulse` (match pulse), `Streak` (Wild tether, Settle energise sweep), `Burst`/`Popup` (flip/solve/reject juice — called from tick/input, never `Draw`), `Band`/`QualityBands` (Settle band name + meter), `GradientBackdrop`/`Backdrop` (via base). Idle shimmer uses `Mathf.Sin(_anim…)` directly (no `Hash01` needed). |
| `CraftColor` | `Brighten` (LitCol); `Color.Lerp` for `MismatchCol` tint (§6). (`DeMuddy`/`Darken`/`Lighten` not required — no blended objective colours in Circuit Lights.) |
| `StateVisual` | **NOT used** — per master plan §1.5, lights-out leans on `CraftFx` primitives, not the chemistry named-state set. |
| `CraftStyle` | `Get("engineering")` via base for glyph/accent/backdrop/embers. |
| `UiTheme` | `Rarity[...]` colours, `Box`, `Accent`, `Text`, `TextButton`/`Section` for splash chrome. |
| `RecipeContext` | reads per §1.7. |

### 11.2 New sprites / assets

**None.** Fully procedural (`DrawRect/Line/Circle/Arc/ColoredPolygon` + `DrawString` for **ASCII-only** badge letters `+ . S X ! ?`, whose meaning is carried by drawn SHAPES not the glyph — §6.3, so no font-dependent tofu). The `⚙` header glyph comes from `CraftStyle`/base (already rendered). No PNGs, no shaders (only the base backdrop shader, which has the `GradientBackdrop` fallback). Consistent with the pure-2D hard rule.

### 11.3 Game1.Core 0-diff confirmation

All logic is Godot-side glue inside `EngineeringMinigame` (+ optional pure helper class for testable board math). No `Game1.Core` type is added or modified; the minigame only PRODUCES `perf ∈ [0,1]` through the certified `MinigameOverlay.Finish` seam. `DifficultyCalculator`, `CraftingSystem`, and the recipe/material databases are untouched. **Game1.Core remains 0-diff.**

---

*Consistency check performed: every tag knob traces to master-plan §2.1 theme → §2.2 Engineering column. Fire→less time; ice→fewer MOVES (never the clock); WATER is the SOLE clock-grower; earth→bigger/immovable (not time); life→spread; shadow→INVERT as a genuinely wide 13-cell high-risk/high-reward blast (not a cosmetic self-toggle); toxic→INVERT + a Spread rider (degrade/corrosion spreading over-time, Smithing parity); air→single/light DISPERSAL tile as the primary effect (a cascade-free light tile, NOT primarily extra moves); quality→bigger+richer; sharp→single; temporal→+moves/freeze-tile (deliberate pace, NOT a longer clock); chaos/dangerous→wild. No tag's theme was flipped; the ice-borrows-water, temporal-borrows-water, air-as-relaxation, and cosmetic-invert violations are all fixed and are guarded by test 6 and test 3(b).*

<!-- CANONICAL PLAN — 2026-08-19. Overwrites the per-minigame designs in MINIGAMES_REDESIGN_PREP.md (that doc's
     8 lessons + extraction-pass infrastructure remain valid; its per-discipline *mechanics* are SUPERSEDED here).
     Source of truth for the per-minigame concepts = the user's 2026-08-11 16:18 message (quoted in §0). -->

# Crafting Minigames — Master Plan (tag-driven modular system)

**This is the canonical design.** It replaces the per-minigame mechanics in `MINIGAMES_REDESIGN_PREP.md`. The unifying
idea — the one the designer called "the most transferable thing" — is a **tag-driven modular effect bank** that feeds
*both* the ingredient tags *and* the crafting-recipe/output tags into every minigame, where **each tag's THEME is
consistent across all disciplines** (fire is never volatile in one game and stabilising in another) and only its
*manifestation* changes per minigame.

This master plan owns: the canonical decisions (§0), the shared architecture / seam (§1), and — most importantly — the
**Tag Theme Dictionary** (§2), which is the consistency backbone every minigame must obey. §3 gives a complete design
spec per minigame. §4 lays out the five *excruciating* implementation docs (one per minigame) that this plan spawns, so
that coding each is a breeze. §5 holds the few genuine open forks.

---

## 0. Canonical decisions (as marked by the designer)

**Provenance.** Per-minigame concepts are taken verbatim-in-intent from the designer's 2026-08-11 message (the "more
specific notes," delivered right before the alchemy revamp). Kept **as marked** — i.e. each idea stays on the discipline
it was assigned to in that message. The 2026-08-10 brief ("mechanically rewarding, easy entry, very high skill ceiling,
NOT solvable" + visible crafted quality + tooltips-by-default) supplies the cross-cutting bar.

| Discipline | Canonical mechanic (as marked) | One-line essence |
|-----------|--------------------------------|------------------|
| **Smithing** | **Top-down StarCraft-2-style micro-battle** (pixelated). Hero by default; material tags grant/tier hero abilities; some tags spawn controllable allies; the enemy wave is material-driven. Survive the wave. | Game *knowledge* lives in recipe-crafting; the minigame is pure **micro**. |
| **Alchemy** | **Stability bell-curve** + heat. Hit a per-recipe **target stability**; the scale is a bell curve (closer to the edge → the needle moves faster → harder). Heat = a low-stability-biased window **and** a tick-speed modifier. Each ingredient added has (a) a base stability ± and (b) a ×multiplier on current stability, both bent by tag interactions with the mixture's tag-pool. | **Knowledge + timing.** Already built — the reference. |
| **Refining** | **Rhythm "gates/folds".** Theme = *remove impurities*. Each gate has a fixed pattern (tag-determined); #folds from output tags+tier; each gate speeds the tick up (error window constant); every strike graded **perfect / close / okay / miss**; two keys (click + space); 8–20 strikes/gate; accuracy summed at the end (minigame never stops). | **Timing under escalating tempo.** |
| **Engineering** | **All-in lights-out (on/off tiles)**, escalating. Tag modifiers: fire → less time; ice → fewer moves. Frames/Function/Power/Modifier/Utility slots set grid size + difficulty. | **Plan-then-execute puzzle**, gradient of correctness. |
| **Enchanting** | **Celeste/Flappy parkour.** The crafting pattern *flips up off the board* into a navigable 2D space; traverse it **clockwise**; each node is a mechanical-control challenge **typed by that node's material tag**; nodes **branch** (you needn't hit every material — but memorising the pattern earns the optimal route). | **Mechanical control / platforming.** |
| **Fishing** | **Untouched** — it is a *gathering* minigame, not a crafting one. Out of scope. | — |

**Cross-cutting rules (all disciplines).**
1. **Mechanically rewarding, easy entry, very high skill ceiling, NOT "solvable."** Difficulty accessible at entry, scales up. State exactly *when/how* it scales (no vague "gets harder").
2. **Tag-driven & modular.** Both ingredient tags and output/recipe tags drive the minigame through one shared effect-bank mechanism. Every available material tag (incl. Update-folder tags) must have an interaction.
3. **A bit of randomness for replayability** — but bounded/telegraphed (a *tell*, never a betrayal).
4. **Consistent tag themes** (§2) — the non-negotiable. Fire's meaning is fixed game-to-game.
5. **Crafted quality is visible** on the item (stamped + shown in inventory/tooltip).
6. **Tooltips by default** = flavor text; **advanced** = stats. (Not: a toggle between "advanced/not-advanced" — the toggle turns detail on/off; default is flavor.)
7. **Difficulty points = intensity; tags = character.** `DifficultyPoints` scales raw hardness; tags shape *what kind* of hard.

**Superseded.** `MINIGAMES_REDESIGN_PREP.md` per-minigame mechanics (Heat-&-Rhythm smithing, purification-chemistry
refining, circuit-assembly engineering, push-your-luck enchanting) are **replaced** by the table above. What survives
from that doc: the 8 quality lessons (§1 there), the numeric-UI house rule, and the **extraction-pass shared toolkit**
(`CraftFx`, `CraftColor`, `StateVisual`, `MinigameModifierCommon`, `MinigameDevLog`) — see §1 for how each is reused.

---

## 1. The tag-driven modular spine (shared architecture)

### 1.1 Two tag streams, one bank
Every craft supplies two streams of tags, and **both** feed the minigame:

- **Ingredient tags** — per input material (`inputs[].Tags`), *ordered* (precedence matters, see §1.3), with a quantity.
  These are the *pieces the player manipulates* inside the minigame (the reagents to add, the abilities on the hero, the
  keys in the fold pattern, the tiles on the grid, the node challenges).
- **Recipe / output tags** — the finished item's tags (`outputTags`) + tier. These set the *goal/character* of the round
  (alchemy's target stability, refining's fold count, engineering's grid size, enchanting's pattern, smithing's enemy
  wave difficulty). The output is what the player is *trying to become*.

Both resolve through **one effect-bank mechanism** already extracted as `MinigameModifierCommon` (StackFactor +
`ModProfile` + `Fold`/`Clamp`). Each discipline declares its OWN table (tag → that discipline's knobs) but the folding,
stacking (diminishing returns), and clamping are shared. This is literally the designer's "effect bank for every tag →
compute every unique ingredient's effect."

### 1.2 The seam (unchanged, sacred)
`MinigameOverlay.Begin(points, tier, RecipeContext?, onComplete(perf 0..1), onAbandon)` → play → `Finish(perf)` OR
`FailCraft()` exactly once. `RecipeContext { OutputId, OutputTags, Inputs[{ Id, Tags, Qty, Tier }], Tier, Points }`
already exists (Godot-side; `Game1.Core` untouched). No minigame changes the certified craft path; each only *produces*
`perf ∈ [0,1]`. If a recipe is null (debug), each minigame samples plausible tags so it is always playable.

### 1.3 Tag precedence (per ingredient) & tag pool (per mixture/loadout)
- **Precedence 4/3/2/1** — within one ingredient's ordered tag list, the 1st tag weighs 4, 2nd 3, 3rd 2, 4th-onward 1.
  So `["fire","sharp","common"]` is dominantly a fire ingredient. (Already implemented as the rank weights in
  `MinigameTagEffects.Brew`; the spine reuses this for every discipline's ingredient→effect resolution.)
- **Tag pool (stacking)** — across all placed ingredients, tags accumulate into a count dict; the 2nd copy of a tag adds
  ~40% more, the 4th almost nothing (`StackFactor`). This is what lets "two fire reagents" or "an all-metal loadout" read
  as a theme without a hard cliff, and it's how the mixture/loadout's *character* is computed.

### 1.4 Difficulty = intensity, tags = character
`DifficultyPoints` (from the certified `DifficultyCalculator`) scales the raw hardness knobs uniformly (enemy HP in
smithing, tick speed in refining/alchemy, grid size in engineering, node speed in enchanting). Tags never touch raw
hardness directly — they shape *which kind* of hard (a fire recipe is fast-and-punishing; an earth recipe is
slow-and-heavy) at a fixed difficulty. This keeps balance tunable from one dial while tags stay expressive.

### 1.5 Shared toolkit reuse (from the extraction pass)
| Toolkit | Role under this plan |
|---------|----------------------|
| `MinigameModifierCommon` (StackFactor/ModProfile/Fold/Clamp) | **The effect-bank engine.** Each discipline declares a tag table; folding+stacking+clamping is shared. |
| `MinigameDevLog` (F1 log + F7 notes) | Per-discipline playtest harness → `res://playtest_logs/<disc>_playtest.log`. Free instrumentation for every rebuild. |
| `CraftFx` (Ring/RingPulse/Streak/Wisp/Crack/Wake/Ellipse/Hash01/Glow/Burst/Bar/…) + `GradientBackdrop` fallback | The pure-2D primitive vocabulary; no-shader backdrop safety net. |
| `CraftColor` (DeMuddy/RadialGrad/tints) | Vivid blended colours + fake gradients (no shaders). |
| `StateVisual` (Look enum + Plume/Flame/Molten/… + DrawLook) | Reusable **only where a "named-state" read applies** (alchemy). SC2/rhythm/lights-out/parkour lean on `CraftFx` primitives + their own sprite/particle work, not the chemistry state set. |
| `MinigameOverlay` (seam, header, quality meter, `FullscreenScene`, shake/popup/burst) | The cradle. Smithing/enchanting will use `FullscreenScene`. 0-churn. |

### 1.6 Tag-usage map obligation
Because everything now hinges on tags, **`Development-Plan/TAG_USAGE_MAP.md`** (the "if we add/invent a tag, here is
everything to update" list) is load-bearing and MUST list all five minigame effect tables among a tag's consumers.
Every discipline's table is authored against the **full** material tag vocabulary (incl. Update folders); an untested
tag resolves to its *theme default* (§2), never to a no-op.

---

## 2. THE TAG THEME DICTIONARY (consistency backbone — obey this everywhere)

This is the contract that makes the system feel coherent: **a tag means the same THING in every minigame.** A tag's
theme is a small set of "verbs/physics"; each minigame has a fixed mapping from those verbs onto its own knobs (§2.2).
Author every discipline's table by looking the tag up here first — never invent a contradicting behaviour.

### 2.1 The seven elemental themes (+ modifier families)

| Theme | Tags (primary + variants) | The fixed "physics" (verbs) | Feel |
|-------|---------------------------|-----------------------------|------|
| **FIRE / HEAT** | **bodies:** fire, flame, ember, molten, forge, volcanic. *(lightning/storm/radiant/light/chaos read fire-ish but are Energy/Exotic RIDERS — §2.3 ruling 1, NOT fire bodies.)* | **HASTE + AGGRESSION + VOLATILITY.** Speeds things up, adds pressure, destabilises, offense-oriented, high-risk/high-reward. | Hot, urgent, dangerous. |
| **WATER (flow)** | water, aqua, liquid, solvent | **FLOW + CLEANSE + DILUTE.** Smooths, reduces intensity of the next thing, adaptable, washes impurities. | Cool, fluid, forgiving. |
| **COLD / ICE** (the still pole of water) | ice, frost, frozen, chill | **CONTROL + DELIBERATION + STABILITY.** Slows the clock, locks things, *fewer but heavier* actions, defensive, "slow down and think." | Crisp, measured, brittle. |
| **EARTH / TERRA** | earth, stone, sand, mineral; (structural metals) metal, iron, steel, bronze, copper, tin, mithril, adamantine, silver, gold, orichalcum, crystal, gem, alloy, metallic | **SOLIDITY + RESISTANCE + MASS.** Stable, defensive, slow to change, structural, high floor / low ceiling. Metals add HARDNESS + (iron/steel) conduction. | Heavy, dependable, inert. |
| **LIFE / GROVE** | wood, oak, ash, ironwood, ebony, birch, willow, worldtree; plant, herb, leather, living; (feral) monster, fang, scales, bone, gel, carapace, blood | **GROWTH + VITALITY + SPREAD.** Regenerates, multiplies, sustains, organic/adaptive; feral variants add ferocity/lifesteal. | Alive, verdant, restless. |
| **SHADOW / UMBRA** | void, dark, shadow, spectral; (toxic) poison, venom, toxic, acid; (mystic) arcane, magical, essence | **ENTROPY + RISK + HIDDEN POWER.** Corrupts/decays, high-risk/high-reward, mystery, negation (void), degrade-over-time (toxic), raw magical amplification (arcane/essence). | Ominous, potent, unstable. |
| **AIR / WIND** | air, wind, vapor, gas | **SPEED + LIGHTNESS + EVASION/DISPERSAL.** Fast, mobile, light, spreads/disperses effects, lowers weight/cost. | Quick, airy, slippery. |

**Cross-cutting modifier families** (ride on top of a body theme; they change *magnitude/quality*, not the verb):

| Family | Tags | Effect on the theme |
|--------|------|---------------------|
| **Quality / Grade** | basic, starter, common, standard → uncommon, fine, quality, refined → rare, advanced, epic, precious → legendary, mythical, ancient; superior, pure, holy, material, mundane | **MAGNITUDE / PURITY.** Higher grade = stronger effect, and (per alchemy's tuning) *more upside for less chaos* — increasing returns. Sets the intensity dial that difficulty also feeds. |
| **Physical / Structural** | durable, strong, hard, solid, dense, heavy; sharp; layered, flexible, versatile, memory | durable/hard/solid/dense/heavy → **reinforce STABILITY/defense + slow**; sharp → **precision/penetration/offense** (an aggression rider even on a calm body); layered/flexible/versatile → **complexity/adaptability** (more states/branches/options). |
| **Energy / Essence** | magical, arcane, essence, radiant, spectral, blood, lightning, chaos | **AMPLIFIERS / WILDCARDS.** magical/arcane/essence = raw power ×; lightning = burst/erratic; chaos = randomness/instability; blood = vitality-for-risk; spectral = ethereal/evasive. |
| **Exotic / Rule-benders** | quantum, impossible, temporal, dangerous, harmony, power, elemental | quantum/impossible/power = amplify the **strongest** active effect; temporal = **time control** (slow/rewind a knob); harmony = **order/stabilise**; dangerous = **risk ×** (bigger swings); elemental = **all-element** touch. |
| **Function / Output** (mostly on OUTPUT tags → set the goal's character) | weapon, combat, tool, armor, protection, defense, resistance, healing, regeneration, buff, enhancement, strength, agility, speed, utility, potion, consumable, crafting, engineering, explosive, fishing | Describe the **target's role**: weapon/combat/explosive/strength → aggressive/volatile goal; armor/protection/defense/resistance → stable/defensive goal; healing/regeneration/harmony → gentle goal; speed/agility → fast goal. Rarely a per-ingredient behaviour. |

### 2.2 Per-minigame manifestation matrix (theme → each discipline's knob)

Read a row as: *"when a FIRE-themed ingredient shows up, here is the ONE consistent way it expresses in each game."*

| Theme (verb) | Smithing (SC2 micro) | Alchemy (stability) | Refining (rhythm folds) | Engineering (lights-out) | Enchanting (parkour) |
|--------------|----------------------|---------------------|-------------------------|--------------------------|----------------------|
| **FIRE** — haste/aggression/volatility | Offensive/AoE hero ability; aggressive fast enemy adds | Pushes stability toward the **volatile edge** + faster tick (destabiliser, high risk) | **Faster / denser** strike pattern; more pressure per gate | **Less TIME** on the clock (the designer's example) | **Fast, dangerous** node (spike-timing, speed section) |
| **WATER** — flow/cleanse/dilute | Sustain/heal-flow or wash-debuff ability | **Dilutes** the next ingredient's effect; nudges toward centre | Cleaner/forgiving pattern; recovers a missed impurity | Extra time / an "undo" tile | Flow/slide section; forgiving checkpoint |
| **COLD/ICE** — control/deliberation/stability | Slow/root/freeze control ability | Strong **stabiliser** + **slower tick** (buys time, caps max instability) | Slower, wider-feeling cadence (fewer strikes, each heavier) | **Fewer MOVES** (the designer's example) — must plan | Precision/slow node; "hold still" platform |
| **EARTH** — solidity/resistance/mass | Tanky/armored hero or ally; wall/defense | Raises the stability **floor**; resists swings; slow | Steady metronomic gate; high floor, low ceiling | Bigger, more **stable** grid; heavy immovable tiles | Solid, heavy platform; grounded section |
| **LIFE** — growth/vitality/spread | Spawns/heals **allies**; regen; ferocity (feral) | Regen toward target; **multiplier** on current stability (compounding) | Adds an extra fold / regrowing impurity to clear | Tiles that **spread** (toggle neighbours); regen | Moving/organic node; growing hazard |
| **SHADOW** — entropy/risk/hidden power | High-risk lifesteal/debuff/summon; glass-cannon | Big **destabilise** + big multiplier (swingy); corrupt | Corrupt gate (hidden/tricky pattern); big risk/reward | Cursed tiles (invert), high-reward-high-risk | Dark/hidden node; blind section, big payoff |
| **AIR** — speed/lightness/evasion | Fast/mobile/blink ability; evasive units | Fast, light nudges; disperses (weakens) the pool | Quick light strikes; disperses tempo pressure | Fewer, lighter constraints; a "skip" tile | Jump/float/glide section; airy traversal |
| **Quality/Grade** (magnitude) | Higher-tier ability / stronger units | Bigger effect, more upside-for-less-chaos | More folds / cleaner reward | Larger grid / more chains, but richer payoff | Longer/richer pattern, better route rewards |
| **sharp** (precision rider) | +crit/precision on the ability | Precision destabiliser (small, exact swing) | Tighter perfect-window value | A "single-target" precise toggle | A precision-timing node |
| **temporal** (time control) | Ability CD/slow-time | Slows the whole tick temporarily | A gate that slows then snaps back | +moves or a time-freeze tile | A slow-motion section |
| **chaos/dangerous** (risk×) | Random strong ability; chaotic wave | Bigger random swings | A randomised gate variant (bounded) | A tile that randomly toggles | A randomised hazard (telegraphed) |

**The rule in one sentence:** if you ever find yourself writing "fire calms this minigame" or "ice speeds this one up,"
stop — you've violated §2.1. Fire always pushes toward *haste/aggression/volatility*; ice always toward
*control/deliberation/stability*; and so on for all seven.

### 2.3 Canonical clarifications (binding rulings from the impl-doc audit)

Four ambiguities in §2.1/§2.2 caused the five impl docs to drift; the cross-doc audit caught them and they are now
resolved here so nothing re-diverges. **These are binding on every discipline's tag table** (the alchemy reference and
all four rebuilds already comply after the audit fixes):

1. **Energetic riders are RIDERS, not fire bodies.** `lightning · storm · radiant · light · chaos` are Energy/Essence
   (lightning/radiant/light) and Exotic (chaos) riders — they AMPLIFY/destabilise/randomise whatever body an ingredient
   already has; they do NOT make it a fire *element*. A discipline may give them a fire-ish *presentation* (hue, volatile
   flavour) and, only for a genuinely body-less material, a fallback HEAT channel — but their VERB is the rider verb, and
   they must **never win an ingredient's dominant-theme/argmax as "fire."** (Alchemy routes them through HEAT for hue+mass
   as a local presentation choice; that is *not* a §2 fire-body grant.)
2. **Scored axis is ADDITIVE; un-scored axis is MULTIPLICATIVE.** The marked per-ingredient "(base ± , ×multiplier)"
   means: the **base ±** adds on the discipline's SCORED axis (keeps scoring legible), and the **×multiplier** compounds
   on an UN-scored axis (potency/power/intensity). Alchemy is the exemplar — base ± on volatility (scored), ×mult on
   potency (un-scored). Every discipline mirrors this split.
3. **Control/deliberation tags (ice, earth, temporal) express as a slower TEMPO or a tighter ACTION budget — never as
   leniency or free resource.** "Slow down and think" = the whole challenge runs at a more deliberate pace (slower
   tick/avatar/tempo, which scales hazard *and* player together) and/or fewer, heavier actions you must still place well
   (fewer moves/strikes). It must **NOT** be implemented as a wider error/forgiveness window or a bigger time/move bank
   handed back — those make the round *easier*, the opposite of a control demand. (So: slowing the clock uniformly is
   fine; widening only your tolerances, or gifting +time/+moves, is wrong. temporal *slows a knob*; it is not a freebie.)
4. **WATER-family always REDUCES intensity; AIR is speed/evasion/dispersal, not a difficulty-off switch.** water/aqua/
   liquid/solvent must be a NEGATIVE push on the scored axis (cleanse/dilute/forgive) — never haste or destabilise. AIR
   disperses by being *fast and light* (evasive, spreads/thins an effect); dispersal weakens a pool or clears impurity,
   but AIR is not a blanket "make it looser/easier" — express it as quickness/evasion/thinning, not generic leniency.

---

## 3. Per-minigame design specs

Each spec is complete at the **design** level (fantasy, loop, tag wiring, scoring, difficulty curve, randomness, visual
language, roadblocks). The **excruciating implementation** layer (every data structure, formula, sprite, state, edge
case) is the dedicated per-minigame doc in §4.

### 3.1 Smithing — "Forge Rush" (top-down SC2 micro-battle)

**Fantasy.** The forge isn't where you *make* the weapon — it's where you *prove* it. A pixelated top-down arena; you
command a hero forged from the recipe and survive a wave. Recipe knowledge = your loadout; the minigame = your micro.

**Core loop.** Spawn hero (+ any ally units) → a timed **survival** against an incoming enemy wave → use abilities +
positioning + ally control to live to the end (or clear the wave). `perf` = how well you survived (HP remaining, wave %
cleared, ability efficiency, no-death bonus).

**Tag wiring.** *Ingredient tags* build the **loadout**: precedence-4/3/2/1 picks each material's dominant theme → an
ability slot on the hero (fire→AoE nuke, ice→slow field, earth→shield/taunt, life→heal/summon ally, shadow→lifesteal or
risky burst, air→blink/haste); quantity/quality tier the ability. Some tags (life especially) spawn **controllable ally
units**. *Output tags* set the **enemy wave**: weapon/combat/explosive → aggressive fast swarm; armor/defense → tanky
slow bruisers; the output's dominant theme colours the enemy abilities (a fire weapon fights fire enemies — thematically
"you must master the element you're forging").

**Scoring.** `perf = clamp( 0.55·survivalFrac + 0.25·waveClearedFrac + 0.15·abilityEfficiency + 0.05·noDeathBonus )`.
Masher (a-move only) ≈ 0.2–0.35; competent (uses abilities on cooldown) ≈ 0.6; expert (kiting, ability combos, ally
micro) ≈ 0.95. **Not solvable:** enemy spawn timings/positions have bounded randomness (telegraphed), so there's no
fixed optimal input sequence.

**Difficulty scaling.** `DifficultyPoints` → enemy count/HP/damage + wave duration. *When/how:* +1 enemy per ~8 points;
enemy HP ×(1+0.03·points); a 2nd wave unlocks above the "rare" tier; a mini-boss at "legendary."

**Visual language.** Pixel-art top-down (new sprite work — the one discipline that needs authored sprites, not pure
procedural): hero + 2–4 ability icons on a cooldown bar, ally unit blips, enemy wave with telegraph markers, health
bars, a wave timer. Ability VFX reuse `CraftFx` bursts/rings tinted by theme colour. `FullscreenScene`.

**Roadblocks (design-level; detailed mitigations in §4 doc).** (1) *Real-time unit control in a 2D Control overlay* — needs
a lightweight ECS-ish tick (positions, cooldowns, simple steering) inside `OnTick`; no physics engine. (2) *Input model* —
click-to-move + ability hotkeys (Q/W/E/R) vs. controller-less feel; must be legible. (3) *Sprite pipeline* — we can't
author raster PNGs blind; plan a **procedural pixel-sprite** fallback (drawn shapes) so it renders even before art lands.
(4) *Scope creep* — cap at hero + ≤3 abilities + ≤2 ally types + 1–2 enemy archetypes for v1. (5) Balancing survival math
across tiers.

### 3.2 Alchemy — "The Stability Bench" (already built; the reference)

**Status.** Essentially shipped (the marble / live-reaction build). Its Volatility axis == the designer's *instability*;
target-volatility band == target stability; heat == tick-speed + low-stability-biased window; ingredients carry a base
push + a multiplier bent by the tag pool. **This spec exists to (a) certify it matches the canonical model and (b) make
it the worked example of the spine.**

**Reconciliation to the marked model.** Confirm/keep: bell-curve scoring (edge = faster = harder — closeness-to-target
with a distance falloff); heat as tick-speed + window bias, never touching banked volatility directly; per-ingredient
(base ± , ×mult) resolved through the tag pool with precedence 4/3/2/1; target from output tags. Numeric UI: **Potency +
Volatility only** (they ARE the scored axes) — everything else read from the marble. Any drift from this is the alchemy
doc's punch-list.

**Roadblocks.** Mostly done; remaining = feel/balance tuning via F1/F7 and confirming the bell-curve "edge = faster"
actually reads. No structural work expected.

### 3.3 Refining — "Impurity Folds" (rhythm)

**Fantasy.** Beat the impurities out of the metal across successive **folds**. Each fold is a fixed rhythm pattern; the
smith who keeps the beat as it accelerates gets a pure ingot.

**Core loop.** N **gates/folds** (from output tags+tier). Each gate = a fixed pattern of 8–20 **strikes** on two lanes
(**click** + **space**); the pattern for a gate is *deterministic from the ingredient tags*. A moving indicator crosses
each strike's window; you hit the correct lane at the right moment. Each strike graded **perfect / close / okay / miss**.
The minigame **never stops**; accuracy is summed at the end. Each successive gate **speeds the tick up** (the error
window stays constant, so it gets genuinely harder). Theme = removing impurities: a visible impurity meter drains as you
land strikes; misses leave impurities.

**Tag wiring.** *Ingredient tags* → the **pattern** (fire→dense/fast bursts, ice→sparse/heavy hits, earth→steady
metronome, air→quick light taps, sharp→tight double-taps, layered→two-lane interleaves). *Output tags + tier* → **#folds**
and the base tempo + speed ramp. Quality/grade → cleaner reward + more folds. Randomness: the *within-theme* pattern
variant is picked with bounded RNG each craft (same theme, different exact sequence) → replayable, not memorisable.

**Scoring.** Per strike: perfect 1.0 / close 0.7 / okay 0.4 / miss 0. `perf = Σ(strikeScore) / Σ(maxStrike)` across all
gates, lightly shaped so a clean run reaches ~1.0 and a masher ~0.25. Streaks (consecutive perfect/close) give a small
escalating multiplier (the designer's "bonuses for streaks / high ceiling"). No hard fail on a miss (misses just cost
points + leave impurity), keeping entry easy.

**Difficulty scaling.** `DifficultyPoints` → base tempo + per-gate speedup slope. *When/how:* base tick +2%/point; ramp
+12% tick per gate (window constant); #folds = 1 + floor(tier) + (output-tag count). Entry (tier 1, few folds) is a slow
steady beat; legendary (many folds, steep ramp) is a blistering finale.

**Visual language.** Pure-2D, `CraftFx`. A horizontal **fold rail** with the moving indicator; two lane markers (click
lane / space lane); strike windows as ticks that flash the grade colour on hit; an **impurity bar** draining; the ingot
visibly brightening/refining fold by fold; combo/streak glow. Numeric UI: none beyond an optional combo count.

**Roadblocks.** (1) *Deterministic-but-varied pattern generation from tags* — a seeded generator keyed by (tags, craftId)
so it's reproducible in tests yet fresh per craft. (2) *Two-lane input clarity* — click vs. space must read instantly
(distinct lane colours + icons). (3) *Tempo feel* — the constant window + accelerating tick must feel fair; tune the
"close/okay" band widths. (4) *Audio* — rhythm games beg for sound; plan silent-but-visual-first, hooks for SFX later.
(5) Ensuring the theme→pattern map never makes a gate literally unhittable at max tier (clamp the speed ramp).

### 3.4 Engineering — "Circuit Lights" (all-in lights-out)

**Fantasy.** Wire the device by flipping its logic tiles into the target state — but every flip ripples to its
neighbours. Plan the whole sequence before you start; a good plan is a smooth run, a bad one is frantic salvage.

**Core loop.** A grid of **on/off tiles** (size from the recipe's slot usage); flipping a tile toggles it + its
orthogonal neighbours (classic Lights-Out), possibly with tag-modified rules. Goal: reach the **target pattern** within a
**move budget** and/or **time budget**. **Gradient of correctness:** score by how many cells match the target at the end
(and elegance: unused moves), not just solved/unsolved. Plan-ahead phase (inspect, no clock) → execute (clock/moves run).

**Tag wiring.** *Ingredient tags* → tile behaviours & the target pattern seed: fire → **less time**; ice → **fewer
moves**; earth → larger/steadier grid + immovable tiles; life → tiles that spread (toggle a larger neighbourhood);
shadow → inverted/cursed tiles; air → a "skip/light" tile; sharp → a single-tile (non-rippling) toggle; temporal →
+moves or a freeze. *Output tags + Frames/Function/Power/Modifier/Utility slot counts* → **grid size + difficulty** (more
slots = bigger grid / more chains). Randomness: the solvable start state is randomised (guaranteed solvable within budget).

**Scoring.** `perf = clamp( 0.75·cellsMatchedFrac + 0.15·moveElegance + 0.10·timeElegance )`. Fully solved with spare
moves → ~1.0; a decent partial → mid; flailing → coverage floor. **Not solvable-by-rote:** random solvable start + tag
rule variants each craft.

**Difficulty scaling.** `DifficultyPoints` → grid size + tightness of the move/time budget. *When/how:* grid grows 3×3 →
9×9 across tiers; move budget = optimal + slack, slack shrinks with points; time budget shrinks with fire-tag weight.

**Visual language.** Pure-2D grid of tiles (lit = glowing theme colour, dark = dim), ripple animation on flip (`CraftFx`
rings/pulse), target-pattern ghost overlay, move/time budget readouts as **bars** (not the exact numbers, per the
UI rule — though a move *count* is arguably a legit scoring metric; decide in §5). Plan phase dims the clock.

**Roadblocks.** (1) *Guaranteeing solvability within budget* under tag rule variants (Lights-Out solvability is
linear-algebra over GF(2); a generator must produce reachable targets). (2) *Rule-variant clarity* — spreading/inverted/
immovable tiles must be visually obvious. (3) *Plan-vs-execute pacing* — how long is the free planning phase; can you
re-plan mid-run (designer said "limited" live tuning). (4) *Bigger grids on a Control* — draw perf + input hit-testing.
(5) Deciding the exact move/time-number UI (see §5).

### 3.5 Enchanting — "Sigil Run" (Celeste/Flappy parkour)

**Fantasy.** The enchant pattern lifts off the board and becomes a course. Channel the enchantment by *running the sigil*
— clockwise, node to node, each node a control challenge shaped by the material bound there.

**Core loop.** The crafting placement pattern (vertices + edges) **flips up** into a 2D traversal space. A controllable
avatar runs the sigil **clockwise**; each **node** is a short mechanical-control challenge (a jump-timing, a
narrow-gap glide, a hold-steady, a dodge) whose **type + difficulty come from that node's material tag**. Nodes
**branch** — you don't have to hit every node, but the pattern is fixed per recipe, so memorising it earns the optimal
(higher-scoring, shorter or richer) route. Reach the end = enchantment sealed.

**Tag wiring.** *Node material tags* → the challenge archetype (fire → fast spike-dodge/speed; ice → precision/hold-still;
air → jump/float/glide; earth → heavy/grounded platforming; life → moving/growing hazard; shadow → dark/blind section;
sharp → tight-gap; temporal → slow-mo). *Output tags + tier* → course length, node count, branch density, avatar speed.
Randomness: micro-variation in node hazard timing (telegraphed) so a route is skill, not muscle-memory alone.

**Scoring.** `perf` = f(nodes cleared cleanly, route optimality, deaths/retries, time). Reaching the end at all →
baseline; a clean optimal-route run → ~1.0. Falling/failing a node = a setback (respawn at last node), not an instant
craft-fail (easy entry); repeated failure caps the score.

**Difficulty scaling.** `DifficultyPoints` → avatar speed + hazard tightness + node count. *When/how:* +1 node per output
tag; hazard windows shrink with points; branching (optional harder shortcuts) unlocks above "rare."

**Visual language.** `FullscreenScene`, pure-2D. The sigil rendered as glowing nodes + edges (the flip-up is a juicy
transition — `CraftFx` + a rotate/scale tween); avatar as a light-mote; per-node hazards drawn from `CraftFx` primitives
tinted by theme; a route trail; a clockwise progress indicator. No numeric UI beyond node progress.

**Roadblocks.** (1) *Platformer physics in a Control* — a small fixed-step kinematic controller (gravity, jump, a couple
of hazard types); keep it tiny. (2) *Turning an arbitrary placement graph into a traversable, always-completable course*
— a layout pass that guarantees a legal clockwise path with legal branches. (3) *The flip-up transition* selling the
"pattern becomes the space." (4) *Input* — jump/dash on 1–2 keys, must feel tight (coyote-time, input buffering).
(5) Death/respawn that keeps entry easy without trivialising the score.

---

## 4. The five excruciating implementation docs (next deliverable)

This master plan is the foundation; each minigame now gets a dedicated `docs/minigames/<DISC>_IMPLEMENTATION.md` written
to the "coding is a breeze" bar. **Every** impl doc must contain, in full:

1. **Data model** — every class/struct/enum, every field with type + units + range, the `RecipeContext` fields it reads.
2. **Tag table** — the discipline's complete `tag → knob` table for the *entire* material vocabulary, authored against §2
   (every tag's theme obeyed), with the exception/precedence rules and the `MinigameModifierCommon` wiring.
3. **State machine** — phases (ready/plan/play/settle/done), transitions, exact trigger conditions.
4. **Tick math** — every formula (spawn/HP/tempo/ripple/physics/scoring) with constants named + starting values + the
   masher/competent/expert perf targets they must hit.
5. **Input map** — every key/click, hit-testing, focus rules, and how F1/F7 are claimed.
6. **Visual spec** — *every* drawn element: layout rects (resolution-relative), colours (theme-sourced via `CraftColor`),
   `CraftFx` primitive per effect, animation curves, layer/z-order, the draw-legality rules. Enough that a coder draws it
   without inventing anything.
7. **Difficulty curve** — the exact `DifficultyPoints → knob` mapping with the "when/how it scales" numbers.
8. **Randomness spec** — what is seeded, the seed source (craftId+tags → reproducible), bounds, and the telegraph.
9. **Roadblock register** — each risk from §3 with a concrete, chosen mitigation (not "TBD").
10. **Test plan** — headless-checkable invariants (seam exactly-once, solvability/reachability guarantees, perf bands),
    plus the F1/F7 playtest script.
11. **Reuse map** — exactly which shared toolkit calls, which new sprites/assets, `Game1.Core` 0-diff confirmation.

**Recommended build order.** 1) **Refining** (smallest new surface: rhythm on the extracted toolkit — proves the
tag→pattern spine end-to-end). 2) **Engineering** (self-contained puzzle; proves tag→rules + gradient scoring). 3)
**Enchanting** (parkour controller; proves the pattern→course pipeline + `FullscreenScene`). 4) **Smithing** (biggest —
real-time units + sprite pipeline; do it last so the spine + toolkit are hardened). Alchemy is already the reference and
only needs the §3.2 reconciliation punch-list. *(Order is a recommendation; §5 lets the designer resequence.)*

---

## 5. Open forks (designer's call — small, deliberate)

1. **Smithing sprite path** — commission/author pixel sprites, or ship the **procedural-pixel fallback** first (drawn
   shapes) and layer art later? (Recommend: procedural first so it renders + plays before art exists.)
2. **Engineering numeric UI** — a **move counter** is arguably a legit "direct scoring metric" (like alchemy's pot/vol).
   Show the move count as a number, or only as a depleting bar? (Recommend: show the count — it's the scored resource.)
3. **Refining lanes** — two keys (click + space) as marked, or add a 3rd lane at high tier for ceiling? (Recommend: keep
   two as marked; raise ceiling via tempo, not lanes.)
4. **Enchanting failure** — respawn-at-last-node (forgiving) vs. a lives budget (tense)? (Recommend: respawn + score
   decay, per "easy entry.")
5. **Build order** — accept the §4 order (Refining→Engineering→Enchanting→Smithing), or lead with a different one?
6. **Alchemy** — is the current build accepted as "the reference," or do you want the §3.2 reconciliation punch-list run
   first before the others?

---

*Consistency check before writing any impl doc: open §2, confirm the tag's theme, confirm the manifestation row, then
author. If a mechanic wants a tag to mean something new, it's wrong — fix the mechanic, not the tag.*

<!-- DESIGN DOC (extraction in progress) — 2026-08-18. Prep for rebuilding the 4 non-alchemy CRAFTING minigames,
     applying the lessons from the Alchemy rebuild. Grounded in the actual Godot code.
     DESIGNER RULINGS FOLDED IN (2026-08-18):
       • Fishing is OUT of scope — it is a GATHERING minigame, not a crafting one. Removed from the target set
         (§3.5 kept only as a stub for the reasoning trail). Target set is now Smithing / Refining / Engineering / Enchanting.
       • NUMERIC-UI HOUSE RULE (locked): the ONLY hard numbers shown are the DIRECT SCORING METRIC(S) of that
         discipline — i.e. Alchemy's Potency & Volatility, because those two ARE the scored axes the player steers.
         Everything else (channel makeup, heat, turbulence, strain, integrity, timers, tag resolution) is hidden and
         read purely by feel / state visuals. F1 debug is the only place other raw numbers may appear. Goal: intuitive.
         (§5 Q2 is therefore RESOLVED; Q4 is MOOT — Fishing removed.) -->

> **⚠ SUPERSEDED (2026-08-19) for the per-minigame MECHANICS.** The canonical per-discipline designs now live in
> **[`CRAFTING_MINIGAMES_MASTER_PLAN.md`](CRAFTING_MINIGAMES_MASTER_PLAN.md)** — a tag-driven modular system where
> Smithing = SC2 micro-battle, Refining = rhythm folds, Engineering = lights-out, Enchanting = parkour, Alchemy =
> stability (the built reference). The chemistry/heat-rhythm mechanics in §2b/§3 below are **replaced**. What remains
> valid here: the **8 quality lessons (§1)**, the **numeric-UI house rule**, and the **extraction-pass shared toolkit
> (§2 A–G)** — the master plan reuses all of it. Read this doc for the *toolkit + principles*; read the master plan for
> *what each minigame is*.

# Crafting Minigames — Redesign Prep (lessons applied)

*Synthesis of four per-discipline redesign plans (Smithing, Refining, Engineering, Enchanting), reconciled against the actual Godot codebase (`Game-1-Godot/scripts/minigames/*.cs` + `scripts/CraftFx.cs`). The Alchemy rebuild is the reference bar. Everything below honours the sacred seam, pure-2D / no-shaders, and Game1.Core 0-diff. Fishing is deliberately excluded — it is a gathering minigame, not a crafting discipline.*

---

## 1. The lessons (the standard every minigame must hit)

A rebuild is not "done" until it passes all eight. Use this as the acceptance checklist.

1. **Real simulation, not a cosmetic QTE.** Reagents/inputs dissolve into a few PRIMARY channels; the process is a live, scored simulation the player actually manipulates — deep on the backend, intuitive on the surface. (Alchemy: 6 essence channels → heat/turbulence → potency & volatility.) A binary tap on an animation is a failure.
2. **Named states are the shared vocabulary of BOTH mechanics AND visuals.** A finite enumerated list (Alchemy has 17) — each with a magnitude 0..1, one distinct visual, and a scored effect. The player reads the process by *which states are firing*.
3. **Every tag has an effect.** Primary/process tags drive the core model (composition). Every OTHER tag is a MODIFIER: a mild uniform BASE (a few scalars) + 1–3 narrative EXCEPTIONS that fire only when a condition holds (a primary present / a state active). Modifiers STACK with diminishing returns. Tier is a moderate multiplier. Ground the bank in the REAL content-tag vocabulary.
4. **Two-axis scoring.** BASE = closeness to a recipe-derived TARGET, × a MULTIPLIER (potency, with a tier-scaled resistance). Quality = product, 0..1, fed to `Finish(perf)`. In Alchemy: `Quality(vol, pot, vTarget, resistance)`.
5. **A reaction window that then settles.** Combine → react a few seconds (states fire, scored axes ease toward composition-derived equilibria) → settle and HOLD. No endless drift, no runaway, no waiting-it-out. Raw inputs are INERT until combined. Order and timing matter because you act into an evolving state.
6. **Visual language (pure-2D, magnitude-scaled).** One distinct visual per named state (differ by FORM + COLOUR + SCREEN-REGION + MOTION so several read at once); OPACITY scaled by magnitude as the primary expressive channel; deliberate LAYERS (background / additive glow / main) with intra-object draw order; DYNAMIC HUE on the focal object; fake gradients from dense translucent shape stacks; DE-MUDDY blended colours (bias to dominant channel + saturation/value floor); dark RIMS on bold overlapping shapes; emphasise the ACTIVE event (swells/pulses, drawn ON TOP, focal thing BIG); a single qualitative RESONANCE cue (golden bloom) when good — no number; a named, ordered, PULSING readout that TEACHES (states strongest-first, transient ones grow/shrink, pulse slows as the effect fades — show STATES, not raw tags). **Numeric-UI house rule (locked):** the only hard numbers are the discipline's DIRECT SCORING METRIC(S) — Alchemy shows Potency & Volatility because those two literally ARE the scored axes; everything else is hidden and read by feel. Visual bars (with a target band) express hidden quantities; F1 debug is the only other place raw numbers appear.
7. **Dev harness.** F1 toggles an on-screen debug log of what's firing; F7 opens a notes box whose entries are timestamped and interleaved with the event log into `res://playtest_logs/<discipline>_playtest.log`. Reuse Alchemy's pattern (`StartSessionLog` / `Log` / `LogNote` / `LogEdges`).
8. **Reuse shared infra; extract what's missing.** Build on the `MinigameOverlay` seam, `CraftFx`, `CraftStyle`, and the modifier-profile pattern. Extract a state-visual primitive toolkit, the F1/F7 harness, a modifier-profile helper, and colour helpers so each minigame doesn't re-implement the toolkit.

**Anti-patterns (auto-fail):** inline shaders (flat fallback = garbage); cramming everything onto one tiny object (no scale/focus/naming = illegible); surfacing raw calculation numbers; abstract effects with no names; a binary QTE on an animation with no combo/flow/order.

---

## 2. Shared infrastructure to extract FIRST

Do this extraction as a preparatory commit *before* rebuilding any single discipline. Rationale: four of the five plans independently propose "a parallel `RefiningTagEffects` / `SmithingTagModifiers` / enchanting `BuildProfile`" and "copy Alchemy's F1/F7 harness" and "extract inline burst/ring draws into helpers." Left un-extracted, we get five divergent copies. The first rebuilt discipline becomes the proving ground (see §4).

What exists today vs. what to generalise:

| # | Extract | Where it lives now | Generalise to |
|---|---------|--------------------|---------------|
| A | **`MinigameOverlay` base** | `MinigameOverlay.cs` — `Begin/Finish/FailCraft`, `SetQuality/FlashQuality`, `Shake`, `SetTimer/HideTimer`, `SetHeaderSub`, `Popup`, `Burst`, the header (glyph + stars + timer) and the right-side 5-band quality meter. `FullscreenScene` hook already exists (Alchemy uses it; any immersive-scene discipline can). | **No change needed** — it is already the shared cradle and every plan reuses it verbatim. Keep it 0-churn; only add protected helpers if a genuinely cross-discipline need appears. |
| B | **`CraftFx` toolkit** | `scripts/CraftFx.cs` (root, not `minigames/`) — `QualityBands`, `Band`, `QualityColor`, `Popup`, `Burst`, `Ambient`, `RoundRect`, `Glow`, `Bar`, `Stars`, `DrawStar`, `Arc`, `Backdrop`. | Mostly reuse as-is. **Add** the primitives every plan re-invents inline: `Ring`/`RingPulse` (expanding fading circle — surge/telegraph/resonance), `Streak`/`Wisp` (flowing translucent line — polish/signal-flow), `Crack` (parametric fracture lines — enchanting/refining brittle), `Wake` (drifting historical trail — fishing dive). These belong in `CraftFx` so all five share one set. |
| C | **State-visual primitive toolkit** | **Does not exist as a shared unit.** Alchemy encodes it as `enum Look { Rise, Ring, Veins, Lava, Shards, Ripple, Core }` + `StateLook[]`/`StateHsv[]`/`StateName[]` lookup arrays in `MinigameTagEffects`, rendered by Alchemy's private `Fx*` draw methods. | Create `scripts/minigames/StateVisual.cs`: a small `enum Look` superset + a `DrawLook(CanvasItem, Look, Vector2 center, float radius, float magnitude, Color)` dispatcher that maps a look-kind + magnitude + colour to a pure-2D draw (built on B). Each discipline supplies its own `(name, look, hsv, effect-bias)` table (the *content*), but the *rendering machinery* is shared. This is the single biggest lever for consistency and is the thing the proving-ground discipline should harden. |
| D | **Modifier-profile helper** | **Alchemy-only.** `MinigameTagEffects` holds `StackFactor(n)`, `ModProfile`, `BuildProfile(counts, tier)`, plus the base `ModTable` and exception tables (`ChExc`/`StExc`/`StrongExc`/`PvExc`). **Flag: `MinigameTagEffects` is entirely alchemy-scoped** (channels are `HEAT/AQUA/TERRA/GROVE/UMBRA/AIR`; states are Alchemy's 17) — nothing else can call it without dragging in alchemy chemistry. | Extract the *mechanism* into `MinigameModifierCommon.cs`: `StackFactor(n)`, a generic `ModProfile<TChannel,TState>` (or a channel-count-parameterised version), and a generic `BuildProfile(counts, tier, baseTable, channelExc, stateExc, pvExc)` that folds tag counts with diminishing returns and clamps. Each discipline then declares only its own tables. Keep Alchemy's concrete tables where they are (or move them beside `AlchemyMinigame`), calling the shared folder. **Do not** try to share one giant tag→effect bank across disciplines — the *effect* of "sharp" differs per discipline (§5 open question). |
| E | **F1/F7 dev harness** | **Alchemy-only, hand-coded.** `AlchemyMinigame.cs`: `_log`/`_showLog`/`_notesPanel`/`_noteEdit`, `StartSessionLog`/`Append`/`Log`/`LogNote`/`LogEdges`, F1/F7 claimed in `OnInput` (`SetInputAsHandled` so they never reach the world's global debug handler), writes to `res://playtest_logs/alchemy_playtest.log`. | Extract into a `MinigameDevLog` helper (composition, not inheritance — a field the overlay owns) exposing: `Begin(discipline, headerLines)`, `Log(line)`, `Note(text, snapshot)`, `ToggleLog()`, `ToggleNotes()`, `Draw(ci, rect, font)`, and an F1/F7 input router. The overlay base can host the notes `LineEdit` + panel once. Discipline supplies the header block and the per-tick `LogEdges`-style rising-edge narration (naming *states*, not raw values). Saves ~120 LOC per discipline and guarantees the log speaks the state vocabulary. |
| F | **De-muddy / colour helpers** | **Alchemy-only, private.** `DisplayColor`/`BlendColor` (bias toward dominant channel, floor S≥0.5 / V≥0.58), `Darken`/`Lighten`/`Brighten`, a radial-gradient stack (dense translucent circles fake a smooth gradient — the "RadialGrad" idiom). | Promote to `CraftColor` static helpers: `DeMuddy(color, dominant, floorS, floorV)`, `RadialGrad(ci, center, radius, darkCol, lightCol, lightOffset, steps)`, `Darken/Lighten/Brighten`. These are the "no-shader smooth gradient" and "keep complex blends vivid" tools every discipline needs; today they'd be copy-pasted. |
| G | **`CraftStyle` per-discipline theming** | Consumed via `CraftStyle.Get(Discipline)` in `MinigameOverlay._Ready` (Accent/Ember/Rise/Top/Bottom/Glow/Glyph/Name). Styles for smithing/alchemy/refining/engineering/adornments appear present. | Reuse. Verify each of the four target disciplines (smithing/refining/engineering/adornments-enchanting) has a complete style entry (accent/ember/glyph/backdrop tint); add any missing. No structural change. |

**Backdrop shader caveat (all five inherit it).** `CraftFx.Backdrop(...)` returns a `ShaderMaterial` — it is the *one* shader in the stack and every overlay uses it via the base `_backdrop`. This is exactly the "inline shader silently fails → flat garbage" hazard the lessons warn about. Extraction task: give `Backdrop` a graceful fallback (a plain layered `ColorRect`/gradient stack) if shader compilation fails in `_Ready`. It is visual-only (input still works), but on an old GPU the player currently sees a black card. Fix once, centrally, before rebuilds multiply the exposure.

### 2b. Per-minigame comparison

| Minigame | Core process model (1 line) | # named states | Scoring axes | Biggest risk | Rough effort |
|----------|-----------------------------|----------------|--------------|--------------|--------------|
| **Smithing** | Heat & rhythm: strike-timing on a moving needle within a heat-coupled sweet-zone, steer the hot-zone across N sections to FORM without WARPing | 14 (mostly re-labelling existing logic) | BASE = mean strike timing (target-closeness) × MULT = heat × evenness × combo − flaws | Visually FLAT vs. Alchemy's chemistry; combo rewards spamming one section | 80–120 h (~2.5–4 wk) |
| **Refining** | Purification: raw ore → 4 channels (Hardness/Purity/Conductivity/Resonance); discrete gesture-actions fire transient states; window then settles | 13 | BASE = closeness-to-target STABILITY × MULT = resisted POTENCY | Complexity ceiling (4 ch + 13 states + tag bank); 4 simultaneous hues muddy | 6–8 d |
| **Engineering** | Circuit assembly: place typed component tiles (Frame/Function/Power/Modifier/Utility); signal flows → 4 channels (Throughput/Stability/Efficiency/Integrity); settles at COMMIT | 12 | BASE = avg closeness to per-channel targets × MULT = integrity-survival + tag-match + tier-elegance | Particle/BFS overhead; illegible if the grid isn't clear; it's a puzzle, not a rhythm game (no timers) | 9–13 d |
| **Enchanting** | Essence resonance under stratified hidden risk: PULSE (charge-timing clean/dirty) pushes STRAIN toward a hidden fracture line vs. superlinear POT; read tells, PUSH/VENT/BANK | ~13 (lifecycle states, not composition states) | BASE = banked_pot / par × MULT = hazard-management (clean vs. near-edge exit) | Hidden-threshold "felt cheated"; tells frozen during charge; RNG-feel of arc/surge | 5–7 d |

Effort estimates come from the individual plans and use different units (Smithing in hours, others in days). Normalising to ~6h/day, Smithing's 80–120h ≈ 13–20 days — an outlier, because its plan front-loads a from-scratch state-enum + visual-primitive + tag-layer + harness refactor of already-working logic. See §4 for why that argues *against* doing Smithing first.

---

## 3. Per-minigame sections

### 3.1 Smithing

**Current state.** `SmithingMinigame.cs` is a working three-layer skill-action game — MICRO (needle-timing on a strike bar: Perfect 1.0 / Good 0.7 / graze 0.35 / Miss 0), MESO (heat decays, striking costs heat, E reheats and steers the hot-zone; ideal band 52–88), MACRO (N sections each need K Good+ strikes to FORM; over-work WARPs). Output `perf = meanTiming × heatFactor × (1 − variance) × comboBonus − flawPenalty`, clamped. Mechanically complete but has **no named-state vocabulary** and inline (un-extracted) visuals.

**Process model.** HEAT & RHYTHM — and per the designer brief (2026-08-10: *"Smithing: is all about heating and rhythm… A mechanical minigame. Large visual improvement"*), **RHYTHM is the LEAD axis**: the player locks into a sustained strike CADENCE (a moving needle / beat), and HEAT is the coupled modifier that keeps that rhythm hittable — heat widens the timing window when hot, contracts + reddens it when cold, so managing heat is *in service of holding the groove*, not a separate resource game. EVENNESS (variance across sections) is the skill cap. Strike timing + heat + hot-zone placement (E-steer toward under-forged sections) are the three inputs. Unlike Alchemy there is **no settling** — only FORM (target completion) and WARP (over-work). The blade draws out as sections form. This is **execution-only** — a *re-labelling + big visual-lift* of already-correct logic, NOT a new simulation and NOT a composition model (see §5 Q7).

**Named states.**

| Name | Trigger | Effect | 2D visual |
|------|---------|--------|-----------|
| Strike | Space/click, needle in-band on lit section | Fill + timing/combo bonus; heat drops | Gold/orange burst at strike point; needle glows white; combo swells at ≥3 |
| Perfect | d ≤ 0.3×sweetzone | Fill + 1.0, extends combo, `FlashQuality` | Gold "PERFECT", large burst + light particles |
| Good | d ≤ 1.0×sweetzone | Fill + 0.7, extends combo, light flash | Orange "GOOD", medium burst |
| Graze | 1.0 < d ≤ 1.7×sweetzone | No fill, 0.35, breaks combo | Grey "graze (off)", minimal burst |
| Miss | way off | No fill, breaks combo, wasted beat | Red "MISS", red directional spark |
| Scorch | timing>0 AND heat>idealMax | No fill, flaws[seg]++, breaks combo | White-hot burst, "SCORCHED", 7px shake, flaw 'x' glyph |
| Form | section reaches K Good+ | Section FORMED, hot-zone drifts on, quality spikes | Pips/bar glow gold, "FORMED", 2× burst, white flash |
| Warp | (K+1)th strike on FORMED section | Section WARPED, flaws++, breaks combo | Red "WARP −", red burst, red diagonal cracks |
| Stoke | E pressed | Heat += , steers hot-zone one step toward neediest section | Gold sparks rise from gauge, forge glow pulse, over-band warning ring |
| In-Band | heat ∈ [min,max] | Sweet-zone at max width, heat bonus 0.85–1.0 | Gauge band green-tinted, sweet-zone glows gold and wide |
| Cold | heat < min | Sweet-zone shrinks ×0.4–0.6, strike value gated | Zone narrows orange-red, gauge amber outline |
| Scorching | heat > max | Next strike becomes Scorch | Gauge white-hot, "SCORCH", pulsing amber warning ring |
| Combo | ≥2 consecutive Perfect/Good on lit section | comboBonus = 1 + 0.15×min(combo,budget) | Combo x2/x3/x5 by hot-zone, "ON FIRE" at ≥5, rising embers |
| DriftHotZone | ~3.5s timer OR a section FORMs | Hot-zone auto-advances (wraps) | Spotlight shifts with pulse, arrow to next stoke target |

**Tag roles.** No composition channels — Smithing is **modifier-only** (this is its defining difference from Alchemy). PRIMARY/PROCESS drivers (`weapon`/`tool`/`armor` + `melee`/`slashing`/`piercing`) act uniformly and only inform difficulty scaling. All other input tags (`metal`, `durable`, `sharp`, `quality`, `refined`, `strong`, …) are GLOBAL modifiers applied *once at Begin* (a single `ModProfile` from recipe inputs), not per-state. Build the table for only the ~15 tags actually present in `recipes-smithing-3.json` (grep first); untested tags resolve to 1.0.

**Scoring.** BASE = `meanTiming` (Σ(timing×locality×heatGate)/budget). MULTIPLIER = heatFactor (0.85–1.0) × evennessFactor (1−variance) × comboBonus. Penalty −0.08×flaws. `Finish = clamp(BASE × MULT − flaws, 0, 1)`. Masher ≈0.2, competent ≈0.6, expert ≈0.95.

**Visual language + readout.** Focal element = the **blade**, which visibly lengthens as sections form (tip = progress) and shifts hue with heat (blue→orange→white). Per-state `Fx*` helpers (extract from inline draws). Readout: header "formed X/N · combo xN" or "SCORCHING — cool it!"; section pips (gold/orange/grey, crossed if warped); combo label; heat gauge with green working band and amber top-15% warning; flaw 'x' glyphs. Numeric UI = timer + combo only.

**Reuse vs. new.** Reuse: entire `MinigameOverlay` seam, `CraftFx`, `CraftStyle` smithing theme, the 5-band meter. New (per §2): refactor 14 states into an enum+table (feeds the state-vocabulary and the F1 log); extract `Fx*` primitives; a *simple* `SmithingTagModifiers` (global, no chemistry — the smallest consumer of extraction D); the F1/F7 harness (extraction E).

**Risks.** (1) Visually flat vs. Alchemy — lean hard on blade taper + heat hue + Form/Scorch bursts. (2) Difficulty-interp cliffs across 9 params (test points 1/40/80; clamp per-param swings). (3) Combo-as-crutch (spamming one lit section) — make Warp LOUD so over-work is punished in feel, and let evenness cap it. (4) Backdrop shader inherited (fix centrally, §2). (5) Heat-decay pace can feel twitchy at high tier (cap ~8 u/s). (6) 14-state enumeration needs explicit priority (Scorch > Form > Combo > Strike). (7) Modifier tuning surface; document each tag's rationale.

**Build sequence.** Ph1 state enum (16h) → Ph3 tag system (24h) → Ph2 visual primitives (20h) → Ph4 F1 log (12h, parallel with Ph2) → Ph5–6 polish & test at difficulty 1/40/80 (28h). `dotnet build` gate each phase.

---

### 3.2 Refining

**Current state.** `RefiningMinigame.cs` is a pure-timing rhythm game (a rotating pick indicator, tap Space when it crosses a golden arc; pins seat; resonance multiplier; Ghost/Bind special pins). No simulation, no named states — the plan proposes a **full replacement** with a chemistry model, so this is the highest-new-code-per-day of the three "process-model" rebuilds.

**Process model.** PURIFICATION CHANNELS. Raw ore dissolves into 4 primaries — Hardness / Purity / Conductivity / Resonance. Discrete gesture-actions (hammer-strike, tumble-roll, quench, resonance-bell, anneal, polish, …) each SELECT and BOOST one or two channels, firing a transient state. Raw material is INERT; a combine starts a ~3.5s reaction window (parameterise per recipe, 2–5s); states fire, channels evolve, potency P and stability S ease toward equilibria; then SETTLE and HOLD. Punishes rushed/oversaturated actions (brittle), rewards patience within the window.

**Named states.**

| Name | Trigger | Effect | 2D visual |
|------|---------|--------|-----------|
| Harden | Hammer-strike (Hardness) when cool | Hardness+0.25, Pot+0.08, Stab−2 | Tight gold rings contract inward; white spark |
| Purify | Tumble-roll (Purity) when Impurities>0.3 | Purity+0.20, Hard−0.05, Pot+0.12, Stab+1 | Soft cyan wisps expand; brighten; slow swirl |
| Conduct | Current touch (Conductivity) >0.5s | Cond+0.18, Res+0.10, Pot+0.05, Stab ±(heat) | Blue crackling arcs radiate; humming glow |
| Resonate | Pitch-bell (Resonance) rhythmic | Res+0.22, Stab+3, Pot−0.02, Purity+0.05 | Gold/violet rings pulse on the beat; singing shimmer |
| Temper | Rapid quench (Hard+Cond, heat>0.5→cool) | Hard+0.15, Cond+0.10, Pot+0.15, Stab−4 | Steam-blue bloom; orange→silver flash; shatter-lines |
| Anneal | Slow cool (Hard+Purity, no spikes 1.5s) | Purity+0.12, Hard+0.08, Pot+0.10, Stab+4 | Warm amber settles/deepens; gentle breathing |
| Polish | Fine buffing (Purity+Cond, low intensity) | Purity+0.15, Cond+0.08, Pot+0.06, Stab+2 | Pearly-white streaks track surface; mirror-shine |
| Burnish | Rhythmic light strikes (Res+Hard, beat) | Hard+0.10, Res+0.12, Pot+0.09, Stab+2 | Gold-pink sparks at each beat; metallic sheen |
| Equilibrate | No action 0.8–1.2s in window | All channels ease 20% to eq, Pot+0.02, Stab+5 | Colours blend to steady calm radiance |
| Corrupt | Misaligned/clashing action | Purity−0.15, Stab−6, Pot−0.08 | Grey-green murk; black cracks spider; dulls |
| Oversaturate | Same channel 3+× in <2s | Pot−0.10, Stab−8, channels −0.05 | Flare too bright then dim; chaotic stress-lines |
| Brittle | Hardness>0.7 while Stability<0.2 | Pot−0.15, Stab−10 (shatter risk) | Hairline fractures; grey-black; tense ring |
| Harmonize | Resonance>0.6 and ≥3 channels present | Pot+0.18, Stab+6, transmutations ×1.2 | Colours converge into iridescent shimmer; deep hum |

**Tag roles.** PRIMARY/PROCESS: `metal`, ore-type (copper/iron/mithril/…), `purify`/`harden`/`conduct`/`resonate`/`temper`/`anneal`/`polish`/`burnish` — set channel makeup + equilibrium targets. MODIFIERS (base + exceptions, `StackFactor` diminishing returns): tier/grade tags → base potency & resistance; quality tags (`refined`/`pure`/`ancient`/`precious`) → potency/stability; process tags (`smelting`/`crushing`/…) → dominant-channel weighting + reaction time; material-nature (`brittle`/`flexible`/`durable`/`strong`) → amplify specific states; elemental riders → channel biases.

**Scoring.** BASE = closeness of output STABILITY to a recipe target (quadratic penalty outside band). MULTIPLIER = POTENCY × tier-scaled resistance. Higher tier = more potency (buff) but a *lower* stability target (harder to hit). The axes decouple: a master builds potency while threading a narrow band.

**Visual language + readout.** Focal element = a glossy semi-transparent ORE/INGOT sphere; surface = 4-channel HSV blend (Hardness gold / Purity cyan / Conductivity electric-blue / Resonance violet), dominant channel pulls overall hue. Each state draws a distinct FORM (rings vs. wisps vs. arcs vs. cracks) — **form is the primary differentiator, colour secondary** (critical for 4-hue legibility). Layers: dull core → main sphere + state anims → additive glow. De-muddy toward dominant channel with S/V floor; dark rims. Readout: pulse-ordered transient state list (strongest-first, names + magnitude, no raw channel numbers); one STABILITY meter with a faint target-band stripe; golden BLOOM when quality>0.8.

**Reuse vs. new.** Reuse: overlay seam, `CraftFx`, `CraftStyle`, and — critically — the extracted `MinigameModifierCommon` (`StackFactor`/`BuildProfile`/`ModProfile`) and the state-visual toolkit. New: the 4-channel `Brew`/`ComposeStability`/`Evolve` (a Refining analogue of Alchemy's chemistry); the discrete **action-input grammar** (hammer/tumble/quench/bell — gestures, not continuous drag — this is genuinely new vs. Alchemy's marble merges); reaction-window settle semantics; two-axis scoring; per-state transient animations. Author `RefiningTagEffects` tables (start 20–30 tags, grow per recipe).

**Risks.** (1) Complexity ceiling (4 ch + 13 states + bank) — start with a minimal tag set. (2) 4-hue muddiness — enforce S/V floor, use form as primary differentiator, strict layer order. (3) Reaction-window timing — parameterise per recipe. (4) Anti-solve ("spam action X") — channel saturation caps + Corrupt/Oversaturate penalties + action cooldowns. (5) Settling trap — keep Equilibrate modest so passive-wait isn't optimal. (6) Potency/stability decoupling UX — teach via the stability bar + header. (7) Tag→channel→state cascade bugs — central `RefiningTagEffects` + F1 log of tag→exception resolution.

**Build sequence (6–8 d).** D1 `RefiningTagEffects` (channel Brew, ComposeStability, Evolve) + F1 log → D2 action-input grammar → D2–3 13 states + per-state chemistry → D3–4 window lifecycle + target-stability + scoring → D4–5 pure-2D render → D5–6 tag bank (~40 tags) → D6–7 UI gloss + F7 notes → D7–8 recipe mapping + playtest 5–10 recipes across difficulty 1–80.

---

### 3.3 Engineering

**Current state.** `EngineeringMinigame.cs` is a spatial pipe-routing puzzle (PLAN / EXECUTE / SALVAGE phases, rotate tiles to route IN→OUT threading objective gauges, scored on reach/gauges/length). Solid puzzle but no PROCESS MODEL, no named states, no pure-2D state vocabulary.

**Process model.** CIRCUIT ASSEMBLY. Place component TILES into typed SLOTS (Frame / Function / Power / Modifier / Utility). Core model = SIGNAL FLOW: power threads Frame → Function(with Power) → Modifiers → Utility output. As signal flows, 4 channels accumulate — THROUGHPUT / STABILITY / EFFICIENCY / INTEGRITY (stress; failure if >1.0). Real manipulation = COMPOSITION (which components), SEQUENCING (traversal order), TUNING (balance the 4 channels to recipe targets). Live during ASSEMBLY, SETTLES at COMMIT. **No timer — it is a puzzle, not a rhythm game** (a deliberate divergence from the reaction-window lessons: composition directly determines equilibrium, so there's no window to wait out).

**Named states.**

| Name | Trigger | Effect | 2D visual |
|------|---------|--------|-----------|
| Idle | Placed/removed; no flow | No channel movement | Greyed pipes, dim borders |
| Flowing | Signal traversing a connected path | Throughput↑, Stability by matches | Cyan/gold particle stream; pipe glow scales w/ throughput |
| Resonant | Signal through a tag-matching component | Thr+0.15, Stab+0.20, Eff+0.10 (once) | Gold spiral bloom at match; segment flashes gold |
| Degraded | Mismatch or Integrity>0.7 | Eff−0.08, Stab−0.05, Integ+0.03 /tick | Reddish distortion aura; signal stutters/dims |
| Bottleneck | Many paths converge on one Utility | Throughput capped 0.5, Eff−0.15 global | Overflow particles; vortex at convergence; frame red |
| Feedback | Circular path formed | Stab−0.20, Integ+0.10 /tick | Purple recursive spiral fills loop; intensity grows |
| Optimized | Reaches output with no Degraded/Bottleneck | Eff+0.12 (clean-routing reward) | Steady beam; green-gold glow; chime |
| Blocked | Dead-end reached | Thr−0.20, Stab→0, Integ+0.08 | Particles pile & reverse; red halo; micro-shake |
| Overloaded | Integrity>1.0 (breaks) | Signal can't pass; throughput→0 past break | Tile charred black; spark; red pulsating outline |
| Unstable | Stability<0.2 | Thr halved, Eff−0.25, path-loss risk | Signal blinks on/off; ghostly particles; static overlay |
| Harmonized | Two adjacent components share a tag, in sequence | Stab+0.12 both, Eff+0.08 /pair | Shared matching-hue aura; harmonic pulse links tiles |
| Miscalibrated | Component tier > target+1 | Integ+0.12 /tick, Eff−0.06 | Oversaturated glow (brighter than target) |

**Tag roles.** PRIMARY/PROCESS (bias the 4 channels): `metal`/`electrical`/`mechanical`/`refined`/`engineering` (electrical→Throughput, refined→Stability, mechanical→Efficiency). FUNCTION tags (recipe requirements / slot determination): `fire`/`lightning`/`cold`/`healing`/`projectile`/`summoning`/`utility`. MODIFIERS (stack, base + ≤3 exceptions each): `sharp`/`durable`/`alloy`/`gem`/`strong`/`light`/`dark`/`void`/`temporal`/`elemental`/`crafting` (e.g., sharp: Throughput↑ Stability↓; durable: Integrity-baseline↑ Efficiency↓). STRUCTURAL (Frame/Utility topology): `solid`/`dense`/`layered`/`flexible`/`crystal` (layered→richer branching). TIER tags scale channel equilibria + Integrity cap.

**Scoring.** BASE = avg closeness to per-channel targets [Throughput, Stability, Efficiency, Integrity-budget] (smooth clamp, 1.0 at target). MULTIPLIER = Integrity survival (no Overload) − 0.08/breach + unspent-tier-elegance (+0.04/pt) + tag-match bonus (+0.02/match, cap +0.20). `Quality = BASE × MULT`, clamped. Tier scales the Integrity cap.

**Visual language + readout.** Focal element = the CIRCUIT GRID (typed slots in column flow Frame→Function→Modifier→Utility); signal PARTICLES are the primary readout (colour/density/motion = state). Per-state visuals as above. Dynamic hue: particle colour = value-weighted blend of Throughput(cyan)/Stability(gold)/Efficiency(green)/Integrity(red). Readout: top line channel values + active-states strongest-first + a plain-English path status ("Frame → Func(fire) → Mod(sharp) → Util | FLOW OK | STRESS OK"). Four vertical channel meters (right) with target bands + a red Integrity danger zone. Layers: blueprint background → opaque signal → additive glow → UI.

**Reuse vs. new.** Reuse: overlay seam, `CraftFx` (extend `Burst`→continuous emitter), `CraftStyle`, extracted `ModProfile` pattern (build one profile per placed component, stack), state-visual toolkit, F1/F7 harness. New: typed-slot grid + drag-place-rotate + live connectivity BFS; the 4-channel signal simulation; component tile primitives (~40×40 cards with in/out connectors); a streaming-particle emitter; path visualisation (bottlenecks/loops); per-recipe channel targets.

**Risks.** (1) Particle overhead on complex paths — cap per segment, cull off-screen. (2) BFS recompute on every place/rotate — cache last good path, diff. (3) Overlapping halos/particles — layer aggressively, opacity-cull. (4) Tier-mismatch cheese — Integrity cap scales with tier (low-tier overloads easily, forcing elegance). Anti-patterns to hold the line on: no shader glow (opacity-scale particle size/density instead); ease channels to equilibria (don't drift unbounded); visualise every component (no black-box); no timers/QTE; no raw numbers; keep the committed signal path visible between ASSEMBLY and COMMIT.

**Build sequence (9–13 d).** Ph1 grid + tiles + connectivity BFS + stub 4-channel math (2–3d) → Ph2 signal simulation + `ModProfile` + tag-match + recipe targets (2–3d) → Ph3 visuals: particles + 12 state visuals + channel-hue blend + meters/readout (3–4d) → Ph4 F1/F7 + scoring calibration + edge cases (feedback/bottleneck/tier) + shake/popup (2–3d). `dotnet build` + hand-test a 3–4-component recipe each phase.

---

### 3.4 Enchanting

**Current state.** `EnchantingMinigame.cs` is already a rich "Runic Overcharge" push-your-luck game: PULSE = CHARGE (hold Space, spin a mote around a sweeping resonance arc) + RELEASE (in-arc = CLEAN low instability floor; out = DIRTY +40–90%); read three tells (rune-ring count, nonlinear hum-ring frequency, colour ramp), then PUSH / VENT / BANK against a **hidden, per-craft re-rolled SHATTER threshold**. Superlinear pulse power vs. widening instability band. This one is the closest to done — the plan is a *formalisation + polish + optional tag layer*, not a rebuild.

**Process model.** ESSENCE RESONANCE via STRATIFIED RISK. Two orthogonal channels: STRAIN (instability pushed toward a hidden fracture line, visible only via receding FOG + progressive crack etching) and POT (superlinear reward, spent via VENT or locked via BANK). A PULSE merges charge-timing quality with depth-scaled power into one decision: push deeper/riskier or retreat/lock. Core = ASYMMETRIC ESCALATION under probabilistic tells. Play loop: settle → read → decide → act → resolve → repeat/lock. Distinct from the others: **pure player agency + probabilistic hazard reading**, not composition chemistry.

**Named states (lifecycle, not composition).** Ready → Idle → Charging → Release → Settle → (Vent / Bank / loop) → Over, plus Surge-Telegraph, Shatter, Ambient, MilestoneFlash.

| Name | Trigger | Effect | 2D visual |
|------|---------|--------|-----------|
| Idle | Settle ends / post-Vent | Ready for Space/V/B | Gem bobs, tells legible, no blur |
| Charging | Hold Space (from Idle) | Builds charge; freezes tells | Gem swells ×1.05, glow↑, sweeping arc + orbiting mote (green in-arc / purple out), blur veil grows |
| Release | Release Space | Apply pulse: pot+power, strain+floor(+dirty), depth++, arm surge | Burst (clean purple 22 / dirty warm 12), shock-ring expands, power popup |
| Settle | 1.2s after Release | Finalise strain/pot; armed surge lands; crack etching updates | Steady glow, tells un-freeze, surge rune flares amber |
| Vent | [V] (Idle/Settle) | pot−18%, strain−relief, vents−− | Green burst from gauge, cost popup, fill shrinks, green wash |
| Bank | [B], depth>0 | banked=pot, quality=pot/par, `Finish` | Gold burst ×40 + band burst, "SEALED", gem swells & fades, golden bg |
| Surge (Telegraph) | depth≥4 rolls surge; armed in Settle | On settle: strain+spike | One rune flares amber (24Hz), "SURGE!", shake, red crack flash |
| Shatter | strain ≥ hidden threshold | banked = pot×0.20, `Finish` | 16 shards + gravity, "SHATTER!", big red burst, 18px shake |
| Ambient | Idle/Settle, no input | Visual only | Gem bob (2.1Hz), live strain-colour, glow pulse |
| MilestoneFlash | strain crosses 0.50/0.72/0.88×mean | Onboarding cue (no gameplay change) | Popup in milestone colour, shake by severity |

**Tag roles.** PRIMARY/PROCESS: `weapon`/`damage`/`advanced` + `basic`/`intermediate` → difficulty-point interpolation (time, threshold mean/variance, noise band, surge chance). MODIFIERS (a small `BuildProfile` analogue, ~50–100 LOC — enchanting is mechanically simpler): `radiant`/`lightning`/`essence`/`arcane`/`magical` → pot× + strain resistance; `durable`/`armor`/`protection` → strain dampening; `chaos`/`dangerous` → strain amplification + surge chance; `harmony`/`healing` → vent relief + lower push-cost; `crafting`/`engineering` → vent-resource bonuses; material tags → threshold-variance scaling. Fold `recipe.inputs[].Tags + recipe.outputTags` → count dict → `BuildProfile` → modulate threshold mean / noise-band width / surge chance / vent relief / pot floor. **The tag layer is optional for MVP** (tier as the only scalar); defer to v2 if needed.

**Scoring.** BASE = `clamp(banked_pot / par, 0, 1)`. MULTIPLIER = hazard management: clean exit (strain well below threshold) pays full; near-edge exit discounts. `perf = BASE × MULT`. Tier lowers par and raises resistance (same skill → lower score at higher tier).

**Visual language + readout.** Focal element = the central GEM — live readout of all state, colour-ramped by strain (cool→warm→hot→white-hot→crack), size-pulsing by activity, **accumulating visible CRACKS** as strain climbs. FOG overlay recedes with depth (the visual proxy for "what's revealed" — the honesty mechanism for the hidden threshold). Readout: pulsing state list ("Pulse 2 · Clean · Strain …"), depth as ordinal ("Pulse 3", not "3"); emphasise the readable tells (rune count / hum frequency / colour ramp / fog clearance). Strain gauge with milestone ticks (0.50/0.72/0.88); live pot top-right. Pure-2D: `DrawCircle/Arc/Line/ColoredPolygon` + `Glow`/`Burst`; bloom via layered transparency; no shaders.

**Reuse vs. new.** Reuse verbatim: overlay seam, `CraftFx` (`RoundRect`/`Glow`/`Burst`/`Popup`/`Band`/`Stars`/`Ambient`), `CraftStyle` "adornments" (purple/cool), the F1/F7 harness, the difficulty-interp pattern. New (enchanting-only): MESO tells (hum-ring, fog clearance, milestones); the CHARGE-timing sub-game (arc sweep + mote + clean/dirty); the surge telegraph (probabilistic arming); the VENT cost/relief economy; the optional `BuildProfile` for enchanting. **Explicitly do not** merge alchemy/enchanting/smithing into a shared "hazard base" — each has its own model; share only graphics/input primitives + the seam.

**Risks (all with the plan's own mitigations).** (1) Hidden-threshold "felt cheated" — the FOG + growing cracks + F1 debug reveal of the true threshold turn a shatter into a teaching moment. (2) Tells frozen during charge — `_windowSpeed` scales with difficulty, arc phase randomised to defeat muscle-memory; the player reads *before* charging. (3) Arc-randomisation feeling arbitrary — clean window is wide and forgiving. (4) Vent economy imbalance — relief `0.35 × BaseInstab(depth)` makes early vents weak, late vents powerful, at an 18% pot cost. (5) Performance floor/ceiling (masher ~0.20 / competent ~0.60 / expert ~0.95). Testing gate: shatter threshold must be *reachable* by good play; milestones must align with true risk; fog must be readable; difficulty curve fair at tiers 1–10 / 40–50 / 70–80.

**Build sequence (5–7 d).** Scaffold + Interp (0.5d) → state machine (1d) → charge timing (1d) → reading tells (1d) → strain + surge (1d) → vent + bank (1d) → pure-2D rendering (1.5d) → F1/F7 (0.5d) → tuning (0.5d) → QA (0.5d). MVP gate: playable, shatterable, bankable, decent visuals, no crashes; tag modulation is post-MVP.

---

### 3.5 Fishing — OUT OF SCOPE (gathering, not crafting)

**Removed from the target set (designer ruling, 2026-08-18).** Fishing is a *gathering* minigame — it produces a raw catch, it has no recipe / material palette / `placements.JSON` entry, and it does not run through the crafting seam the way the five disciplines do. It therefore does **not** belong to this crafting-minigame redesign and is intentionally excluded. `FishingMinigame.cs` stays as-is for now. (The earlier draft designed a tension-equilibrium + fish-lifecycle rebuild for it; that reasoning is preserved in git history if fishing is ever revisited as its own gathering-polish pass, but it is NOT part of this effort.)

---

## 4. Recommended sequence

The first rebuild is the **proving ground for the shared toolkit** (§2 C/D/E/F). Pick the discipline that exercises the toolkit hardest while carrying the least *new simulation* risk, so toolkit bugs surface against known-good mechanics rather than being tangled with a from-scratch chemistry model.

**Order: Smithing → Refining → Engineering → Enchanting.** (Fishing removed — gathering, not crafting.)

0. **Extraction pass (prerequisite, ~2–3 d) — IN PROGRESS (2026-08-18).** Ship §2 C/D/E/F + the `Backdrop` fallback + `CraftFx` primitive additions as one commit. Nothing else starts until `dotnet build` is green and Alchemy still runs unchanged (it now *calls* the extracted helpers instead of owning them). This keeps `MinigameTagEffects` alchemy-scoped but makes `StackFactor`/`ModProfile`/`BuildProfile` (→ `MinigameModifierCommon`), the state-visual dispatcher (→ `StateVisual`), the dev-log harness (→ `MinigameDevLog`), and the colour helpers (→ `CraftColor`) reusable.

1. **Smithing — proving ground.** Its logic is *already correct and shipping*; the whole rebuild is exactly the four extraction consumers (state enum + `Fx*`/`StateVisual` primitives + a *simple* global modifier profile + F1/F7 harness). It is the cleanest test of the shared toolkit with **zero new simulation risk** — if the state-visual toolkit or the modifier helper is wrong, it shows here against known-good mechanics. (Caveat: it's the least "chemistry-like" — accept that Smithing validates the *plumbing*, and Refining will validate the *chemistry* pattern.)

2. **Refining — second, first full chemistry rebuild.** This is where the extracted `MinigameModifierCommon` and the multi-hue state-visual toolkit get their real test — a 4-channel `Brew`/`Evolve` closely mirroring Alchemy. Doing it after Smithing means the toolkit is hardened; doing it before Engineering means the "4-channel composition + reaction window + two-axis scoring" pattern is proven and directly reusable.

3. **Engineering — third.** Also a 4-channel model, but with the most *new UI machinery* (typed-slot grid, drag-place-rotate, connectivity BFS, streaming-particle emitter) and the largest estimate (9–13 d). Its no-timer puzzle stance is a deliberate divergence — validate the shared toolkit doesn't assume a reaction clock.

4. **Enchanting — last.** It is *already the richest and closest to done*; its rebuild is formalisation + polish + an **optional** tag layer. Doing it last lets it adopt the mature extracted harness/primitives/colour helpers with zero churn, and defer its tag `BuildProfile` to a genuine v2 without blocking anything.

**Dependencies.** Extraction pass blocks everything. Smithing hardens C/D/E/F for all. Refining's channel+window+two-axis pattern feeds Engineering. Enchanting is independent of the tag bank (its tag layer is optional/deferred), so it can slip earlier if a second dev is free — but the *first* discipline (Smithing) must be solo/serial so the toolkit stabilises against one consumer before it forks.

---

## 5. Open questions for the designer

1. **Per-discipline modifier banks, or one shared bank?** Recommendation: each discipline owns its `(tag → effect)` tables while sharing only the *mechanism* (`StackFactor`/`ModProfile`/`BuildProfile`, now in `MinigameModifierCommon`), because `sharp` means different things per discipline. The alternative (one giant cross-discipline bank) is explicitly discouraged. *(Still open — but the extraction is built to support the recommended per-discipline-tables shape.)*
2. **How much numeric UI is allowed? — RESOLVED (2026-08-18).** House rule: the ONLY hard numbers shown are the discipline's DIRECT SCORING METRIC(S). For Alchemy that is Potency & Volatility (they literally ARE the two scored axes the player steers). Every other quantity — channel makeup, heat, turbulence, strain, integrity, timers, tag resolution — is hidden and expressed only through state visuals / bars-with-a-target-band / feel. F1 debug is the sole exception where other raw numbers may appear. Guiding intent: it should feel intuitive, not instrumented.
3. **Per-discipline vs. one shared state-visual set?** Recommendation (and how the extraction is built): a shared *dispatcher* (`StateVisual.DrawLook` over a shared `Look` enum) with per-discipline `(name, look, hue)` tables — don't force one visual vocabulary across every discipline. *(Still open for ratification, but the toolkit already assumes this.)*
4. ~~**Does Fishing stay tag-free?**~~ **MOOT** — Fishing removed from scope (gathering, not crafting).
5. **Enchanting's hidden threshold — keep it hidden?** Confirm the "felt cheated" risk is acceptable in exchange for tension (with FOG + growing-cracks + F1 post-mortem as the honesty mechanisms), or switch to a *visible-but-fuzzy* danger band. *(Still open — decide during the Enchanting rebuild, it's last.)*
6. **Reaction-window duration — global or per-recipe?** Alchemy uses fixed 3.5s; Refining wants per-recipe (2–5s); Engineering has *no* window. Recommendation: per-recipe tunable + Engineering's no-clock stance as an accepted divergence. *(Still open.)*
7. **Should Smithing gain a real composition model, or stay execution-only? — RESOLVED (per the 2026-08-10 designer brief).** Smithing stays **execution-only: heat + rhythm, mechanical, big visual lift**, with rhythm as the LEAD axis (*"is all about heating and rhythm… A mechanical minigame"*). No composition axis — tags act only as global modifiers applied once at Begin. It reads visually flatter than the chemistry disciplines *by design*; the fix is to lean into the rhythm/heat feel + blade-forging spectacle, NOT to add a composition model. (This was mistakenly re-floated as open; it was already settled by the brief.)
8. **Anti-solve enforcement level (Refining/Engineering).** Decide how aggressively to punish degenerate strategies (spam-one-action / brute-force-highest-tier) vs. letting evenness/target-closeness quietly cap the score. *(Still open.)*

---

*Grounding: seam + helpers verified in `MinigameOverlay.cs` and `scripts/CraftFx.cs`. The modifier-profile pattern + state-look tables live in `MinigameTagEffects.cs` and are alchemy-scoped today. The F1/F7 harness + de-muddy/RadialGrad idioms are private to `AlchemyMinigame.cs`. `CraftFx.Backdrop` is the one `ShaderMaterial` in the stack and needs a central fallback.*

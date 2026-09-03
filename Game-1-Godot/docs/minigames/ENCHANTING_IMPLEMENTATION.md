<!-- IMPLEMENTATION DOC — Enchanting "Sigil Run" (Celeste/Flappy parkour). Written to the "coding is a breeze" bar:
     a coder should INVENT NOTHING. Authored against CRAFTING_MINIGAMES_MASTER_PLAN.md §0/§1/§2/§3.5/§4. Every tag
     traces to §2 (Tag Theme Dictionary). All logic is Godot-side glue producing perf∈[0,1] through the certified seam;
     Game1.Core is 0-diff. Replaces the mechanic in scripts/minigames/EnchantingMinigame.cs (the "Runic Overcharge"
     push-your-luck build). File name / class name / Discipline key ("adornments") are PRESERVED. -->

# Enchanting — "Sigil Run" — Implementation Doc

**Class:** `EnchantingMinigame : MinigameOverlay` (Godot-side, `namespace Game1.Godot`)
**File (replace in place):** `Game-1-Godot/scripts/minigames/EnchantingMinigame.cs`
**Discipline key:** `"adornments"` (unchanged — drives `CraftStyle.All["adornments"]`: glyph `✦`, accent `#D18CFA`, purple backdrop, `Rise=26`)
**Master-plan cell:** §0 (Enchanting = Celeste/Flappy parkour), §3.5, §5 fork #4 resolved = **respawn-at-last-node + score decay** (NOT lives).
**FullscreenScene:** `true` (override `FullscreenScene => true`; the sigil owns the whole viewport).

**One-paragraph fantasy.** The placement pattern (the vertices + edges the player laid on the crafting bench) *flips up off the board* into a 2D parkour course. A light-mote avatar runs the sigil **clockwise**, node to node; each node is a short mechanical-control challenge **typed by the material tag bound to that node** (fire → fast spike section; ice → hold-still precision; air → glide; earth → heavy grounded jump; shadow → blind section; life → moving hazard). Nodes **branch** — you needn't hit every node — but the pattern is fixed per recipe, so memorising it earns the optimal route. Falling a node respawns you at the last cleared node and *decays* your score; reaching the end seals the enchantment. `perf ∈ [0,1]` is produced through the sacred seam and nothing else.

---

## §0. Grounding contracts (read once, obey everywhere)

| Contract | Source | What it pins for us |
|---|---|---|
| Seam | `MinigameOverlay.Begin(points, tier, RecipeContext?, onComplete(perf), onAbandon)` → `Finish(perf)` **OR** `FailCraft()` exactly once | We only ever produce `perf∈[0,1]`. Reaching the end → `Finish(perf)`. Double-Esc / total wipe-out is handled by the base's abandon path; we never call `FailCraft()` (a Sigil Run always yields *some* traversal → a scorable partial). **Exactly-once is guaranteed structurally AND by the base guard:** `MinigameOverlay.Finish` opens with `if (!_running) return;` and sets `_running=false` (base `MinigameOverlay.cs:270-271`), so any second `Finish` is a no-op. We rely on this explicitly — see §3's idempotency note for the two Settle-entry paths that could otherwise race. |
| Effect bank | `MinigameModifierCommon.{StackFactor, ModProfile, Fold, Clamp}` | We declare OUR OWN tables (`§2`) and call `Fold`+`Clamp`. We reuse `StackFactor` for the tag-pool character read. |
| Tag themes | Master plan §2.1 + manifestation matrix §2.2 (Enchanting column) | Every tag's meaning is fixed. Fire = fast/dangerous node; ice = precision/hold-still; air = glide; earth = grounded/heavy; life = moving/growing hazard; shadow = blind; sharp = tight-gap; temporal = slow-mo; chaos/dangerous = randomised (telegraphed) hazard. |
| Difficulty = intensity | `DifficultyPoints` (1..80 practical range) is the ONE hardness dial | It scales avatar speed, hazard-window tightness, node count, branch density (§7). Tags never touch raw hardness — only character. |
| Numeric-UI house rule | Master §0 rule 6 + `MINIGAMES_REDESIGN_PREP` | Enchanting's DIRECT scoring metric is **node progress** (nodes cleared / total on the taken route) → shown as a discrete pip trail. Everything else (speed, hazard tightness, decay) is bars/feel. NO raw numbers on screen. (Contrast: Engineering's move-count exception does NOT apply here.) |
| Toolkit | `CraftFx`, `CraftColor`, `StateVisual`, `MinigameDevLog` | Reuse per §11. No new shaders (the one backdrop shader has the `GradientBackdrop` fallback baked into the base). |
| Core 0-diff | `Game1.Core` untouched | All code lives in this one Godot `.cs`. |

**Theme colours (source of truth — never hardcode a raw hex that isn't derived from these):**
- `Accent` = `CraftStyle.Get("adornments").Accent` = `Color(0.82,0.55,0.98)` (purple). Assigned by the base into `MinigameOverlay.Accent`.
- Backdrop = adornments Top/Bottom/Glow (`(0.11,0.07,0.15)`/`(0.03,0.02,0.05)`/`(0.7,0.4,1)`), painted by the base. We may override `BackdropTint` (see §6.1).
- All node/hazard colours are derived from the node's dominant **theme family colour** via `MinigameTagEffects.FamilyColor(channel)` and re-vivified with `CraftColor.DeMuddy` / `CraftColor.Brighten`. See §2.4 for the theme→FamilyColor channel map and §6 for per-element colour.

---

## §1. DATA MODEL

All types are nested in `EnchantingMinigame` unless noted. Units: **px** (surface-local, on a virtual 1280×720 design surface scaled to the viewport — see §6.1), **s** (seconds), **[0,1]** normalized, **rad**. `enum` values listed with intent.

### 1.1 RecipeContext fields consumed

```
Recipe (MinigameOverlay.Recipe : RecipeContext?)   // null on debug launch → synthesize (see §8.4)
  .OutputTags : List<string>   // sets COURSE CHARACTER: node count bias, branch density, avatar base speed (§2.3, §7)
  .Inputs     : List<Ingredient>
      .Tags   : List<string>   // ORDERED → precedence 4/3/2/1 → this ingredient's NODE TYPE (§2.2)
      .Qty    : int            // ≥1 → how many NODES this ingredient contributes (clamped, §1.6)
      .MaterialTier : int      // 1..4 → per-node hazard magnitude rider (§2.3)
      .Id, .Name : string      // Id → node-seed salt (§8); Name → node label in F1 log only (never on the play HUD)
  .Tier   : string             // "common".."legendary" → star count (base handles) + a coarse difficulty floor
  .Points : double             // == DifficultyPoints; the base also passes it as `difficultyPoints` to Begin()
```

`DifficultyPoints` (base field `double DifficultyPoints`) is the authoritative hardness dial; `Recipe.Points` mirrors it.

### 1.2 `enum NodeKind` — the challenge archetype (typed by tag theme, §2.2)

| Value | Theme (§2.1) | The control challenge | Hazard element |
|---|---|---|---|
| `SpikeRun` | FIRE — haste/aggression/volatility | fast corridor; timed spike gates must be cleared before they close | pulsing spike bars |
| `HoldStill` | COLD/ICE — control/deliberation | stand on a fragile platform and hold within a shrinking safe band for a dwell time | crumbling ledge |
| `Glide` | AIR — speed/lightness/evasion | float across a gap; hold `[Space]` to slow-fall between two updrafts | wind gap |
| `HeavyLeap` | EARTH — solidity/resistance/mass | a single heavy, committed jump over an immovable block; low, deliberate arc | solid wall |
| `MovingHazard` | LIFE — growth/vitality/spread | dodge a sweeping/growing organic tendril while advancing | oscillating vine |
| `BlindDash` | SHADOW — entropy/hidden power | a fogged section; the hazard telegraph is dimmed; higher node payoff | shrouded gate |
| `TightGap` | `sharp` rider (precision) | thread a narrow static gap; unforgiving width | pinch walls |
| `SlowMoDodge` | `temporal` rider (time control) | one dodge in bullet-time; window feels wide, real time is slowed | slow bolt |
| `ChaosGate` | `chaos`/`dangerous` rider (risk×) | a randomised-but-telegraphed hazard (one of the above picked by seed each run) | flagged variant |
| `Plain` | fallback / unresolved tag → theme default = EARTH-lean grounded jog | a gentle jog-and-jump | none |

> Precedence/exception rules that pick the `NodeKind` from an ingredient's ordered tag list live in §2.

### 1.3 `struct NodeSpec` — one node on the course (built at OnBegin, immutable during play)

| Field | Type | Units/Range | Meaning |
|---|---|---|---|
| `Kind` | `NodeKind` | enum | archetype (§1.2) |
| `Pos` | `Vector2` | px (surface-local) | node centre on the flipped-up sigil |
| `IndexOnRing` | `int` | 0..N-1 | clockwise order index (0 = entry) |
| `IsBranchAlt` | `bool` | — | true if this is an *optional harder shortcut* node (skippable; higher reward) |
| `BranchFrom` | `int` | mainline node index or -1 | if `IsBranchAlt`, the mainline node `kFrom` this chord forks FROM (edge `kFrom→this`) |
| `BranchTo` | `int` | mainline node index or -1 | if `IsBranchAlt`, the mainline node `kTo=(kFrom+1)%N` this chord rejoins TO (edge `this→kTo`); the pair `(BranchFrom,BranchTo)` is the "covered span" used by routeFrac (§4.6) |
| `Family` | `int` | 0..5 (`MinigameTagEffects` channel const) | dominant theme channel → colour (§2.4) |
| `Tier` | `int` | 1..4 | material tier → hazard magnitude rider |
| `HazardWindow` | `double` | s, 0.18..1.20 | the timing window for a clean clear (shrinks with points, §7) |
| `HazardSpeed` | `double` | [0.5,2.5] | hazard tempo multiplier (fire>1, ice<1, §2.3) |
| `Reward` | `double` | [0.6,1.6] | per-node score weight (branch/quality riders, §4.6) |
| `SeedSalt` | `uint` | — | per-node RNG salt = `hash(craftId, Id, IndexOnRing)` (§8) |
| `Label` | `string` | — | material name (F1 log only) |

### 1.4 `struct Edge` — a walkable link between two nodes (the sigil's lines)

| Field | Type | Units | Meaning |
|---|---|---|---|
| `A`, `B` | `int` | node index | endpoints (directed A→B in clockwise flow) |
| `IsBranch` | `bool` | — | true = an optional shortcut edge |
| `Length` | `float` | px | cached `A.Pos.DistanceTo(B.Pos)` (for the walk-lerp speed) |

### 1.5 `class Avatar` — the light-mote kinematic body (mutable, one instance)

| Field | Type | Units/Range | Meaning |
|---|---|---|---|
| `Pos` | `Vector2` | px | current position |
| `Vel` | `Vector2` | px/s | velocity (kinematic; gravity + jump only during a node challenge) |
| `OnEdge` | `int` | edge index or -1 | while traversing between nodes we *walk the edge* (see §3 PLAY) |
| `EdgeT` | `double` | [0,1] | progress along the current edge |
| `AtNode` | `int` | node index or -1 | the node we're currently *inside the challenge of* (-1 = walking an edge) |
| `Grounded` | `bool` | — | touching a platform this frame (jump legality) |
| `CoyoteLeft` | `double` | s, 0..`COYOTE` | coyote-time remaining after leaving ground (§4.5) |
| `JumpBufferLeft` | `double` | s, 0..`JUMP_BUFFER` | buffered jump press remaining (§4.5) |
| `Facing` | `float` | ±1 | clockwise travel sign (visual trail) |

### 1.6 `class RunState` — the whole run (single instance, reset each OnBegin)

| Field | Type | Units/Range | Meaning |
|---|---|---|---|
| `Nodes` | `List<NodeSpec>` | — | full course (mainline + branch alts) |
| `Edges` | `List<Edge>` | — | walkable graph (guaranteed a legal clockwise mainline, §9-R2) |
| `Route` | `List<int>` | node indices | the nodes the player has actually CLEARED, in order (the "taken route") |
| `TotalMainline` | `int` | count | number of mainline nodes (denominator baseline for progress) |
| `LastCheckpoint` | `int` | node index | respawn target (last cleared node) |
| `DecayPenalty` | `double` | [0,1] accumulator | subtractive score decay from falls (§4.6) |
| `AvatarState` | `Avatar` | — | the body |
| `Phase` | `Phase` | enum (§3) | state machine |
| `RunClock` | `double` | s | elapsed play time (feeds a *soft* time bonus, not a limit) |
| `SettleClock` | `double` | s | time spent in `Settle` (drives the `Settle→Done` transition after `SETTLE_DUR`; `_settleClock` in §3) |
| `RespawnFlash` | `double` | s, 0..0.5 | decays a fall/respawn `RingPulse` (element #12); reset to 0.5 on FAIL |
| `Anim` | `double` | s | free-running clock for all VFX phase |
| `BestNodeReached` | `int` | count | high-water mark of TOTAL cleared discs (monotone; F1 log + `Route.Count` bookkeeping only — NOT the scoring denominator) |
| `MainlineReached` | `int` | 0..TotalMainline | high-water mark of MAINLINE index reached, advanced by a mainline hop OR a covering branch chord (§4.6); the routeFrac numerator |
| `CheapRouteReward` | `double` | — | precomputed Σ Reward over the all-mainline route `0→…→N-1→0`; the `rewardBonus` denominator (set once at OnBegin, §4.6) |
| `Rng` | seeded `RandomNumberGenerator` | — | Godot `RandomNumberGenerator`, `Seed` set from craftId+tags (§8) |

### 1.7 Per-node live challenge state — `struct NodeChallenge` (only the active node uses it)

| Field | Type | Units | Meaning |
|---|---|---|---|
| `Active` | `bool` | — | true while inside a node challenge |
| `HazardPhase` | `double` | [0,1) pingpong or wrap | the hazard's own timeline (drives spike open/close, vine sweep) |
| `Dwell` | `double` | s | accumulated in-band time (HoldStill) |
| `Cleared` | `bool` | — | set true on success; triggers checkpoint advance |
| `Failed` | `bool` | — | set true on hit; triggers respawn + decay |
| `SlowScale` | `double` | [0.25,1] | local time scale (SlowMoDodge = 0.35; else 1) |

### 1.8 Difficulty-interpolated params (fields, set once in `OnBegin` via `Interp`)

| Field | Type | Easy (pts=1) | Legendary (pts=80) | Drives |
|---|---|---|---|---|
| `_avatarSpeed` | double px/s | 210 | 340 | edge-walk + horizontal run speed |
| `_gravity` | double px/s² | 1500 | 1500 | constant (feel is tuned once; hardness comes from windows) |
| `_jumpVel` | double px/s | -560 | -560 | constant (see §4.4 note) |
| `_windowScale` | double [0,1] | 1.00 | 0.55 | multiplies every node's `HazardWindow` |
| `_nodeCountBias` | int | 0 | +3 | added to the base node count from output tags (§7) |
| `_decayPerFall` | double | 0.045 | 0.11 | subtractive score decay per fall (§4.6) |
| `_hazardSpeedGlobal` | double | 0.85 | 1.35 | global hazard tempo multiplier |

`Interp(easy, hard)` = `easy + (hard-easy) * clamp((DifficultyPoints-1)/79, 0, 1)` (same shape as the current build's `Interp`, line 434).

---

## §2. TAG TABLE — the complete `tag → knob` map (entire material vocabulary)

Authoring rule (master §2, one-sentence rule): **look the tag up in §2.1, obey its verb, then express it in the Enchanting column of §2.2.** A tag NEVER flips theme. Two independent resolutions happen:

- **(A) Per-node `NodeKind`** — from the *dominant* theme of one ingredient's ordered tag list (precedence 4/3/2/1). This decides the *challenge archetype*.
- **(B) Course/loadout character** — a `ModProfile` (via `MinigameModifierCommon.Fold`) folded over the *tag pool* of ALL inputs + output tags, resolved through OUR table below. This bends the *magnitude* knobs (`HazardWindow`, `HazardSpeed`, `Reward`, avatar speed) — NOT the archetype.

### 2.1 (A) Dominant-theme → `NodeKind` (precedence 4/3/2/1 over the ordered tag list)

For each ingredient, compute a channel-weight vector exactly like `MinigameTagEffects.Brew` does: 1st tag weight 4, 2nd 3, 3rd 2, 4th+ 1; resolve each tag → a channel via the map in §2.4; the **dominant channel** picks the base archetype. Then **rider tags override** (checked in this fixed priority, first match wins) because riders are the "character on top of a body theme" (§2.1 modifier families):

| Priority | Condition on the ingredient's tags | Resulting `NodeKind` | §2 trace |
|---|---|---|---|
| 1 (highest) | any of `chaos`, `dangerous` present | `ChaosGate` | §2.2 chaos/dangerous row = "randomised hazard (telegraphed)" |
| 2 | `temporal` present | `SlowMoDodge` | §2.2 temporal row = "a slow-motion section" |
| 3 | `sharp` present | `TightGap` | §2.2 sharp row = "a precision-timing node" (tight gap) |
| 4 | dominant channel == HEAT(fire) | `SpikeRun` | §2.2 FIRE = "fast, dangerous node (spike-timing, speed)" |
| 4 | dominant channel == AQUA **and** any cold tag (`ice`,`frost`,`frozen`,`chill`) in list | `HoldStill` | §2.2 COLD = "precision/slow node; hold still" |
| 4 | dominant channel == AQUA **and** NOT cold (`water`,`aqua`,`liquid`,`solvent`) | `Glide` biased to a **forgiving checkpoint** (wider window ×1.25) | §2.2 WATER = "flow/slide section; forgiving checkpoint" |
| 4 | dominant channel == AIR | `Glide` | §2.2 AIR = "jump/float/glide section" |
| 4 | dominant channel == TERRA(earth) | `HeavyLeap` | §2.2 EARTH = "solid, heavy platform; grounded section" |
| 4 | dominant channel == GROVE(life) | `MovingHazard` | §2.2 LIFE = "moving/organic node; growing hazard" |
| 4 | dominant channel == UMBRA(shadow) | `BlindDash` | §2.2 SHADOW = "dark/hidden node; blind section, big payoff" |
| 5 (fallback) | no channel resolves (unknown tags only) | `Plain` (theme default = earthy grounded jog, §2.2 EARTH lean) | master §1.6: an untested tag resolves to its *theme default*, never a no-op |

Note the WATER-vs-ICE split: water and ice are the two poles of the same family (§2.1) — water FLOWS (forgiving), ice CONTROLS (hold still). The presence of a cold tag disambiguates.

### 2.2 (B) Character `ModProfile` — OUR base table (the full vocabulary)

Channels for our `ModProfile` reuse the 6 alchemy channels (`N=6`: HEAT/AQUA/TERRA/GROVE/UMBRA/AIR) so `Ch[]` reads the same theme axes; we use **no state array** (`states=0`). The profile fields are re-interpreted for parkour:

| `ModProfile` field | Parkour meaning | Applied in |
|---|---|---|
| `Pot` | **Reward multiplier** on every node's `Reward` (quality/grade → bigger payoff) | §4.6 |
| `Vol` | **Hazard-window delta** in *window-fraction ×100* units: `+Vol` widens (calmer), `-Vol` tightens. Folded then mapped: `windowMul = 1 - Vol/120` clamped [0.6,1.4] | §4.3 |
| `Time` | **Avatar-speed multiplier** (fast themes speed the mote; slow themes calm it): `speedMul = Time` clamped [0.75,1.35] | §4.2 |
| `Rx` | **Hazard-tempo multiplier** (`HazardSpeed` global rider): `tempoMul = Rx` clamped [0.6,1.6] | §4.3 |
| `Ch[c]` | **Per-channel emphasis** — only used to break ties in dominant-theme reads and to tint the course glow toward the loadout's strongest family | §2.1(A), §6 |

Because the parkour reading of each field is *monotone-aligned* with alchemy's (fire → faster/more volatile → shorter window + higher tempo; ice → slower/less volatile → wider window + lower tempo), **we reuse the numeric intent of the alchemy tables** and only re-key them into our four scalars. The concrete base table (`_baseTable : Dictionary<string,(double Pot,double Vol,double Time,double Rx)>`) — full vocabulary, every entry authored to §2:

```
// ---- ELEMENTAL BODIES (verbs fixed by §2.1) ----
// FIRE bodies (fire/flame/ember/molten/forge/volcanic): haste+aggression+volatility → tighten window (Vol negative),
// speed up the mote (Time>1), high tempo (Rx>1). Body tags land dominant-HEAT → SpikeRun.
"fire"     =(1.00, -10, 1.15, 1.30)   "flame"   =(1.00, -9, 1.14, 1.25)   "ember"  =(1.00, -6, 1.10, 1.18)
"molten"   =(1.02, -12, 1.10, 1.35)   "forge"   =(1.02, -5, 1.08, 1.18)   "volcanic"=(1.03,-13,1.10,1.40)
// ENERGETIC RIDERS on the fire axis (§2.1 lists lightning/storm/radiant/light/chaos as HEAT-channel *riders*, not
// bodies): they resolve to the HEAT channel (§2.4) so their character is fire-flavoured — but they are AMPLIFIER/
// WILDCARD magnitude riders (§2.1 Energy/Essence family), so they tighten the window and lift tempo LESS aggressively
// than a raw fire BODY. radiant/light are the calm-feeling members: small Vol (barely tighter), modest Rx (~1.1) —
// they read as "bright and quick," not "burning." A pure radiant/light ingredient still dominant-HEATs → SpikeRun,
// but a fast, forgiving one. They stay RIDERS on the HEAT body here, never bodies of their own — the same posture the
// Alchemy reconciliation canonises (ALCHEMY_RECONCILIATION.md §C.2-a "Energy/Exotic riders first": lightning/radiant/
// light/chaos are filed under Energy/Essence + Exotic, applied as magnitude riders, NOT certified as fire bodies).
// [DESIGNER-CONFIRM tag: radiant/light window-tighten (Vol) magnitude — intentionally mild; keep aligned with the
// Alchemy §C.2-a riders-first calibration so radiant/light never out-punch a real fire body in either game.]
"lightning"=(1.02, -11, 1.25, 1.45)   "storm"   =(1.02,-9,1.20,1.30)      "radiant" =(1.05,-4,1.10,1.12)
"chaos"    =(1.00, -16, 1.05, 1.55)   "light"   =(1.06,-4,1.06,1.10)
// WATER (flow): cleanse/dilute/flow → widen window (Vol+), gentle tempo, mild slow. WATER IS THE FORGIVING POLE — a
// wider timing window is water's CORRECT expression here (§2.2 WATER = "forgiving checkpoint"), and this is the same
// posture the Alchemy fix restores for water (ALCHEMY_RECONCILIATION.md §C.2-e: solvent's base must lean WATER-forgiving,
// not haste/volatile — cite this row when closing that solvent contradiction). Water's widen (Vol +6..+8) is kept
// DELIBERATELY SMALLER than ice's (Vol +9..+13) so the two AQUA poles stay distinguishable: water = forgiving-but-flowing
// (Glide, moderate widen), ice = brittle/measured-and-slow (HoldStill, largest widen). NodeKind already splits them
// (water→Glide-forgiving vs ice→HoldStill, §2.1(A)); the Vol gap keeps the magnitudes from collapsing into each other.
"water"=(1.00,+8,0.95,0.85)  "aqua"=(1.00,+8,0.95,0.85)  "liquid"=(1.00,+6,0.96,0.88)  "solvent"=(0.98,+5,0.98,0.95)
// COLD/ICE (still pole): control/deliberation/stability → widen window a lot, slow avatar + tempo. ICE's Vol (+9..+13)
// is the LARGEST window-widen of any theme. DIVERGENCE FROM ENGINEERING, ACCEPTED & NOTED (option a): Engineering
// forbids ice from touching its clock/reaction-time (ENGINEERING_IMPLEMENTATION.md §4.3: "ICE touches MOVES only —
// never the clock") because in a turn-planned puzzle "deliberation" must NOT read as free reaction time. Enchanting is a
// REAL-TIME parkour game with no move budget, so ice's "control/deliberation" is legitimately expressed as a WIDER
// TIMING WINDOW plus a SLOWER avatar (Time 0.83..0.88) plus the precision HoldStill node (NodeKind.HoldStill, which
// makes ice DEMAND a held-still dwell — the measured/brittle feel). The wide window is thus paired with slow movement +
// a precision hold, so ice does NOT read as "the most forgiving theme": it is the SLOWEST-and-most-exacting, which is
// the correct opposite pole from fire. Water stays the forgiving pole (smaller widen, faster mote); ice is measured, not
// lenient. This window-vs-clock divergence between the two games is intentional and framing-driven, not a §2 violation.
"ice"=(1.00,+12,0.85,0.68)  "frost"=(1.00,+11,0.86,0.72)  "frozen"=(1.00,+13,0.83,0.62)  "chill"=(1.00,+9,0.88,0.78)
// EARTH/TERRA: solidity/resistance/mass → steady wide window, slower avatar, low tempo
"earth"=(1.00,+6,0.90,0.80)  "stone"=(1.00,+8,0.88,0.78)  "sand"=(1.00,+4,0.94,0.90)  "mineral"=(1.00,+6,0.90,0.80)
// metals (EARTH + hardness): reinforce stability + slow; iron/steel a touch of conduction (tiny Rx up)
"metal"=(1.02,+6,0.90,0.85)  "metallic"=(1.05,+2,0.95,1.05)  "iron"=(1.02,+6,0.90,0.90)  "steel"=(1.06,+5,0.90,0.90)
"bronze"=(1.04,+5,0.91,0.85) "copper"=(1.03,+5,0.92,0.90)   "tin"=(1.02,+5,0.92,0.88)   "alloy"=(1.10,+4,0.94,0.95)
"mithril"=(1.14,+3,0.98,1.0) "adamantine"=(1.18,+7,0.88,0.90) "silver"=(1.08,+3,0.94,0.95) "gold"=(1.10,+3,0.94,0.95)
"orichalcum"=(1.18,+2,0.98,1.05) "crystal"=(1.08,+5,0.92,0.88) "gem"=(1.10,+4,0.93,0.88)
// LIFE/GROVE: growth/vitality/spread → moving/growing hazards (Rx up = livelier), neutral window
"wood"=(1.00,+2,0.98,1.02) "oak"=(1.00,+2,0.98,1.02) "ash"=(1.00,+2,0.98,1.02) "ironwood"=(1.04,+2,0.96,1.02)
"ebony"=(1.03,+1,0.97,1.03) "birch"=(1.00,+2,0.99,1.02) "willow"=(1.00,+3,0.99,1.00) "worldtree"=(1.14,+1,0.98,1.05)
"exotic"=(1.10,0,0.98,1.08) "plant"=(1.02,+2,0.98,1.02) "herb"=(1.04,+2,0.98,1.02) "living"=(1.03,+1,0.99,1.05)
"leather"=(1.00,+2,0.97,0.98) "monster"=(1.04,-2,1.00,1.08) "fang"=(1.03,-2,1.02,1.08) "scales"=(1.03,+2,0.98,0.95)
"bone"=(1.02,+3,0.97,0.92) "gel"=(0.98,+3,0.98,0.95) "carapace"=(1.03,+4,0.96,0.90) "blood"=(1.06,-4,1.02,1.20)
// SHADOW/UMBRA: entropy/risk/hidden power → BlindDash payoff. The §2.1 verb is ENTROPY+RISK+HIDDEN-POWER, expressed
// here as BIG SWINGS (Vol negative → tighter/riskier window) with an ETHEREAL/EVASIVE feel (spectral/void = light,
// quick mote → Time>1). Tempo (Rx) is NOT uniformly "livelier": pure shadow bodies (void/dark/shadow/spectral) ride
// slightly BELOW 1 (Rx<1) because entropy/negation reads as an unhurried-but-lethal drift, not fire's frenzy; the
// TOXIC riders (poison/venom/toxic/acid) DO push tempo up (Rx>1) because degrade-over-time is an active, ticking hazard.
// CROSS-GAME SHADOW TEMPO (coordinated with Refining, NOT opposite): Refining's KnobTable runs the SAME split — its pure
// shadow bodies sit at Rx≤1.0 (REFINING_IMPLEMENTATION.md §2.2: void 0.95 / dark 0.95 / shadow 1.00 / spectral 0.88, so
// Dens does not rise from the body) while its toxic riders push Rx up (poison/venom/toxic 1.12, acid 1.28). Refining's
// shadow "big risk/reward" comes from tricky STRUCTURE (high Inter / +Dbl / +Imp), not raw pace — so shadow reads slow-
// bodied + toxic-fast in BOTH games. The shared direction is: pure shadow = unhurried drift (Rx<1), toxic = ticking-fast
// (Rx>1). Keep these two docs' shadow Rx on the same side of 1.0 whenever either is retuned.
"void"=(1.04,-4,1.06,0.96) "dark"=(1.00,-3,1.02,0.98) "shadow"=(1.02,-2,1.02,0.98) "spectral"=(0.92,-3,1.10,0.94)
"poison"=(1.06,-5,1.0,1.12) "venom"=(1.06,-5,1.0,1.12) "toxic"=(1.06,-5,1.0,1.12) "acid"=(1.05,-6,0.98,1.25)
"arcane"=(1.16,-4,1.05,0.98) "magical"=(1.14,-2,1.03,1.02) "essence"=(1.16,-1,1.02,1.05)
// AIR/WIND: speed/lightness/evasion → glide; fast+light (Time up), high tempo, slight widen (evasion is forgiving air)
"air"=(1.00,+3,1.15,1.10) "wind"=(1.00,+3,1.15,1.10) "vapor"=(1.00,+2,1.12,1.08) "gas"=(1.00,+1,1.12,1.12)
// ---- MODIFIER FAMILIES (magnitude/quality, ride on the body) ----
// Quality/Grade — MAGNITUDE: more reward, and per §2 "more upside for less chaos" → Pot up, window widens slightly
"starter"=(0.90,+3,0.98,0.98) "basic"=(0.92,+2,0.99,1.0) "common"=(0.95,+1,1.0,1.0) "standard"=(1.00,0,1.0,1.0)
"uncommon"=(1.05,-1,1.0,1.0) "fine"=(1.08,+1,1.0,1.0) "quality"=(1.11,+1,1.0,1.0) "refined"=(1.13,+2,1.0,1.0)
"rare"=(1.16,+1,1.0,1.0) "advanced"=(1.19,+1,1.0,1.02) "precious"=(1.22,+2,1.0,1.0) "epic"=(1.22,+2,1.0,1.02)
"legendary"=(1.28,+3,1.0,1.02) "mythical"=(1.32,+3,1.0,1.0) "ancient"=(1.25,+3,1.0,0.98)
"superior"=(1.14,+2,1.0,1.0) "pure"=(1.10,+4,1.0,0.98) "holy"=(1.15,+3,1.0,1.02) "material"=(1.00,0,1.0,1.0) "mundane"=(0.85,0,1.0,0.95)
// Physical/Structural
"durable"=(1.00,+4,0.95,0.90) "strong"=(1.10,+2,1.0,1.05) "hard"=(1.00,+5,0.94,0.90) "solid"=(1.00,+6,0.92,0.85)
"dense"=(1.00,+5,0.90,0.82) "heavy"=(1.00,+4,0.88,0.85)  // heavy/dense/solid → reinforce stability + SLOW (grounded)
"sharp"=(1.05,-6,1.05,1.20) // precision/penetration/offense rider (also forces TightGap in §2.1)
"layered"=(1.00,+2,0.98,0.95) "flexible"=(1.00,+3,1.02,0.98) "versatile"=(1.05,+1,1.0,1.02) "memory"=(1.05,+2,0.98,0.98)
// Energy/Essence (amplifiers/wildcards)
"lightning"/* see fire */    "chaos"/* see fire */
// Exotic/Rule-benders
"quantum"=(1.00,-4,1.05,1.15) "impossible"=(1.20,-6,1.05,1.10) "power"=(1.25,-3,1.05,1.15)
"temporal"=(1.10,+8,0.85,0.70)  // time control → slows tempo, widens window (also forces SlowMoDodge in §2.1)
"harmony"=(1.10,+8,0.98,0.90)   // order/stabilise → calmer
"dangerous"=(1.10,-12,1.02,1.45) // risk× (also forces ChaosGate) — bigger swings
"elemental"=(1.10,-3,1.02,1.15)
// Function/Output (mostly OUTPUT tags → course character)
"weapon"=(1.08,-6,1.05,1.20) "combat"=(1.06,-5,1.02,1.20) "explosive"=(1.10,-14,1.05,1.50) "strength"=(1.15,-3,1.0,1.10)
"armor"=(1.04,+9,0.90,0.80) "protection"=(1.05,+8,0.92,0.82) "defense"=(1.02,+8,0.92,0.82) "resistance"=(1.00,+7,0.94,0.85)
"healing"=(1.05,+6,0.95,0.85) "regeneration"=(1.05,+7,0.95,0.82) "harmony"/* above */ "buff"=(1.10,+2,1.0,1.05)
"enhancement"=(1.12,+2,1.0,1.02) "utility"=(1.00,+2,1.0,1.0) "tool"=(1.03,+4,0.96,0.90) "potion"=(1.02,+2,1.0,0.98)
"consumable"=(1.00,+2,1.0,0.98) "crafting"=(1.02,+3,0.98,0.95) "engineering"=(1.04,+4,0.96,0.90) "fishing"=(1.00,+3,0.98,0.90)
"speed"=(1.05,-3,1.20,1.30) "agility"=(1.04,-2,1.15,1.25)
```

**Exception tables** (folded via `MinigameModifierCommon.Fold`'s `chExc` arg — the ONLY exception kind we use; no `stExc`/`strongExc`/`pvExc` because we have no state array and no primary-present potency deltas). These only emphasise a channel for the tie-break/tint read, mirroring alchemy's `ChExc` intent:

```
_chExc : Dictionary<string,(int Ch,double Mul)[]>
  "lightning"=[(HEAT,1.5)] "radiant"=[(HEAT,1.4)] "chaos"=[(HEAT,1.5)] "void"=[(UMBRA,1.5)] "dark"=[(UMBRA,1.3)]
  "arcane"=[(UMBRA,1.25)] "essence"=[(GROVE,1.3),(UMBRA,1.25)] "spectral"=[(UMBRA,1.35)] "blood"=[(GROVE,1.3),(UMBRA,1.25)]
  "metallic"=[(TERRA,1.3)] "alloy"=[(TERRA,1.3)] "strong"=[(TERRA,1.3)] "sharp"=[(TERRA,1.25)] "hard"=[(TERRA,1.2)]
  "speed"=[(AIR,1.3)] "agility"=[(AIR,1.25)] "flexible"=[(AIR,1.2)] "elemental"=[(HEAT,1.25),(AIR,1.25)]
  "armor"=[(TERRA,1.3)] "protection"=[(TERRA,1.3)] "defense"=[(TERRA,1.3)] "solvent"=[(AQUA,1.3)]
```

**No-op guard — the theme-default fallback (mandatory; §2.6 is where it is wired).** `MinigameModifierCommon.Fold` only touches a tag that is a key in `_baseTable` (`MinigameModifierCommon.cs:64` gates on `baseTable.TryGetValue`); any tag NOT in `_baseTable` is silently skipped and leaves the identity profile (Pot 1, Vol 0, Time 1, Rx 1) — i.e. a **no-op**, which master §1.6 forbids ("an untested tag resolves to its *theme default*, never a no-op"). The `_baseTable` above is authored against the whole present vocabulary, but Update-folder additions (or any tag we did not enumerate) would slip through. We close this hole in code, NOT by hoping the table is complete:

- **Before folding**, `BuildCourseProfile` (§2.6) walks `counts` and, for every tag that is NOT a `_baseTable` key, resolves its **channel** via `ResolveChannel` (§2.4) and injects a **theme-default character tuple** into a working copy of the table so `Fold` has an entry to apply. The per-channel defaults are the "plain body" of each family (the same monotone intent as the keyed bodies, just the neutral centre of the family):

```
_channelDefault : (double Pot,double Vol,double Time,double Rx) indexed by channel
  HEAT  = (1.00, -8, 1.12, 1.25)   // fire body default → tighter+faster+hotter
  AQUA  = (1.00, +7, 0.94, 0.82)   // water/flow default → wider+calmer  (cold split handled in §2.1(A), not here)
  TERRA = (1.00, +6, 0.90, 0.82)   // earth body default → steady wide window, slow, low tempo
  GROVE = (1.00, +2, 0.98, 1.03)   // life body default → neutral window, livelier tempo
  UMBRA = (1.02, -3, 1.02, 0.98)   // shadow body default → big swing (tighter), unhurried drift
  AIR   = (1.00, +3, 1.14, 1.10)   // air body default → fast, light, slight widen
  (unresolvable) = (1.00, 0, 1.0, 1.0)  // only for a tag whose channel ResolveChannel cannot map → EARTH-lean Plain
```
If `ResolveChannel` returns a channel, the tag folds as that channel's default (NON-trivial: at least one of Vol/Time/Rx moves off identity). If `ResolveChannel` returns null (a genuinely unknown string), we fall the tag to the EARTH default (never the identity tuple) so even an invented tag reads as a grounded Plain-lean node, matching §2.1 priority-5. **A vocabulary tag can therefore never no-op.**

- **`ResolveChannel(tag)`** is our inline mirror of `MinigameTagEffects.Resolve` (§2.4 explains why it is copied, not called). Its channel map covers: the ~90 keyed tags in `MinigameTagEffects.Tags`; the `Metal` set = **`copper,tin,steel,mithril,bronze,adamantine,silver,gold,orichalcum`** → `TERRA`; the `Wood` set = **`oak,ash,ironwood,ebony,worldtree,exotic,birch,willow`** → `GROVE`. NOTE (correcting a common misread): `iron` and `steel` are **not symmetric** — `steel` IS in `MinigameTagEffects.Metal`, but `iron` is **not** in the `Metal` set (it lives only in `MinigameTagEffects.Tags`, mapped to `TERRA`). We key both `iron` and `steel` explicitly in `_baseTable` above, so neither depends on the fallback; the `Metal`/`Wood` set membership matters ONLY as the fallback channel source for *other* set members a future Update folder might add (e.g. a new `"platinum"` in `Metal` → `TERRA` default).

### 2.3 How tier & quantity enter (NOT via the base table)

- **`MaterialTier` (1..4)** → a per-node hazard-magnitude rider on the node built from that ingredient: `HazardSpeed *= 1 + (tier-1)*0.06` and `Reward *= 1 + (tier-1)*0.10`. (Tier is intensity-of-that-node's character, matching §2.2 "Quality/Grade (magnitude)" — bigger effect at higher tier.) It also lightly bumps `ModProfile.Rx` post-fold: `p.Rx *= 1 + (maxTier-1)*0.05`, exactly the alchemy tier-vigor bump (`BuildProfile` line 189).
- **`Qty`** → how many nodes this ingredient contributes: `nodesFromIngredient = clamp(Qty, 1, 3)`. (An all-of-one-material craft still branches; a stacked reagent reads as a *theme run* of same-kind nodes, matching §1.3's tag-pool stacking intent.) Total nodes are then clamped by §7's course-size cap.

### 2.4 Theme → channel → colour (the one map used for reads AND colours)

Resolve a tag → channel with **our own `ResolveChannel(string tag) : int?`**. `MinigameTagEffects.Resolve` / `.Tags` / `.Metal` / `.Wood` are all `private`, so we cannot call them — we re-implement the tag→channel lookup inline. This IS a duplication hazard (≈90 tag→channel entries plus the two sets); we treat it as a real maintenance surface, not a triviality, and defend it two ways:

1. **One-time transcription is bounded and verifiable.** Only the *channel int* of each entry is needed (not the display HSV), so each line is `["fire"]=HEAT`, `["void"]=UMBRA`, etc. — a flat `Dictionary<string,int>` mirroring `MinigameTagEffects.Tags`'s first field, plus `Metal→TERRA` / `Wood→GROVE` set membership, plus the null-return for anything unresolved. The full channel map is exactly the §2.4 table below (colour column) expanded per tag; author it once against `MinigameTagEffects.cs` lines 208–230.
2. **A drift-detection test pins it (test #10, §10).** Because `MinigameTagEffects.Resolve` is private, the test reaches the same ground truth through the one PUBLIC read that already exposes channel: `MinigameTagEffects.FamilyColor(ch)` is 1:1 with channel, and every keyed alchemy tag's channel is observable via the shipped `DisplayColor`/`Dominant` path in a single-tag `Brew`. Test #10 iterates the union vocabulary and asserts `FamilyColor(ResolveChannel(tag)) == FamilyColor(Dominant(MinigameTagEffects.Brew(new[]{tag},1,1)))` for every keyed tag — so any transcription drift (a mistyped channel) FAILS a headless test rather than silently mis-typing a node. If `MinigameTagEffects` promotes `Resolve` to `public` later, delete `ResolveChannel` and call it directly (reuse-map note in §11).

Channel → colour = `MinigameTagEffects.FamilyColor(channel)`:

| Channel const | `FamilyColor` | Node/hazard base colour |
|---|---|---|
| `HEAT`=0 | red-orange `Hsv(0.03,0.85,1)` | SpikeRun/fire |
| `AQUA`=1 | blue `Hsv(0.57,0.72,0.98)` | Glide-forgiving / HoldStill(ice) |
| `TERRA`=2 | earthy gold `Hsv(0.09,0.55,0.8)` | HeavyLeap |
| `GROVE`=3 | green `Hsv(0.32,0.66,0.85)` | MovingHazard |
| `UMBRA`=4 | violet `Hsv(0.78,0.6,0.85)` | BlindDash |
| `AIR`=5 | pale cyan `Hsv(0.53,0.2,0.98)` | Glide |

All node colours pass through `CraftColor.DeMuddy(familyColor, familyColor, lean:0.0, floorS:0.55, floorV:0.62)` then `CraftColor.Brighten(+0.05)` so the FullscreenScene stays vivid (master lesson: de-muddy always).

### 2.6 Fold wiring (exact call) — with the no-op guard

```
BuildCourseProfile(counts : Dictionary<string,int>, maxTier : int) -> ModProfile:
    var p = new ModProfile(channels:6, states:0);   // MinigameModifierCommon.ModProfile; St[] is EMPTY (states=0)

    // --- NO-OP GUARD (§2.2): build a working table = _baseTable + a theme-default entry for every unkeyed tag ---
    var table = new Dictionary<string,(double Pot,double Vol,double Time,double Rx)>(_baseTable);
    foreach (var tag in counts.Keys)
        if (!table.ContainsKey(tag))
            table[tag] = _channelDefault[ResolveChannel(tag) ?? TERRA];   // channel default, never identity → never a no-op

    MinigameModifierCommon.Fold(p, counts, table, _chExc);   // stExc/strongExc/pvExc null (no state array, no strongest-amp, no primary-present PV)
    p.Rx *= 1 + (max(1,maxTier)-1)*0.05;                     // tier vigor bump (alchemy parity)
    MinigameModifierCommon.Clamp(p,
        potLo:0.6, potHi:1.6,      // reward mult
        volLo:-24, volHi:24,       // window delta (mapped in §4.3)
        timeLo:0.75, timeHi:1.35,  // avatar-speed mult
        rxLo:0.6,  rxHi:1.6,       // hazard tempo mult
        chLo:0.35, chHi:2.5);      // St bounds OMITTED on purpose — states=0 → St[] is empty, so stLo/stHi would be
                                   // dead args. Clamp's defaults (stLo/stHi=0.35/2.5) apply to an empty array = a no-op
                                   // loop. We pass NEITHER an st array nor st bounds anywhere; this discipline has no states.
    return p;
```

`counts` = tag→count over the union of every input's tags (each input contributes its tags once *per Qty*, so stacking is honoured by `StackFactor` inside `Fold`) **plus** the output tags (each counted once). This is the "two tag streams, one bank" of master §1.1. Because the working `table` now has an entry for **every** tag in `counts`, `Fold`'s `baseTable.TryGetValue` gate (`MinigameModifierCommon.cs:64`) always hits, so no tag is skipped and no tag no-ops.

---

## §3. STATE MACHINE

`enum Phase { Ready, Plan, Play, Settle, Done }` (field `RunState.Phase`).

```
        Begin()                       [Space]/click             all nodes on route done
   ────────────────►  Ready  ──────────────────►  Plan  ──[Space]──►  Play  ───────────────►  Settle
                        ▲                            │                   │  (reach the SEAL node)      │
                        │                            │ (auto after       │                            │  after SETTLE_DUR
                        │                            │  PLAN_MAX_S or     │  fall a node → respawn     ▼
     (base handles Esc  │                            │  [Space])          │  at LastCheckpoint,       Done ──► Finish(perf)
      double-tap abandon)                            ▼                   │  DecayPenalty += _decayPerFall
                                                  (Plan is a free look:   │  (stays in Play)
                                                   camera pans the full   └── total-wipeout guard:
                                                   sigil, no clock)           RunClock > HARD_CAP_S → Settle (bail w/ partial)
```

| Phase | Entered when | What runs | Exits when |
|---|---|---|---|
| `Ready` | `OnBegin()` finishes building the course | draw the flipped-DOWN sigil flat on the board + a "CHANNEL ▸ [Space]" prompt; **the flip-up transition tween is armed but not started** | first `[Space]` or click → start flip-up tween, go to `Plan` |
| `Plan` | flip-up transition begins | the sigil tweens up into the course over `FLIP_DUR=0.9s` (rotate+scale, §6.3); when the tween ends, a free camera pan traces the clockwise route once; **no clock, no hazards armed** | `[Space]` (skip) OR `PLAN_MAX_S=6s` elapsed → `Play` |
| `Play` | plan skipped/timed-out | avatar spawns at node 0; `OnTick` runs the kinematic controller; entering a node arms its `NodeChallenge`; clearing advances checkpoint + appends to `Route`; falling respawns at `LastCheckpoint` and adds decay | avatar clears the SEAL node (last mainline node) → `Settle`; OR `RunClock > HARD_CAP_S` → `Settle` |
| `Settle` | course finished / hard-capped | a 1.1s sealing flourish (route trail lights gold, `CraftFx.Burst` at each cleared node, quality meter snaps to `perf`) | after `SETTLE_DUR=1.1s` → `Done` |
| `Done` | settle flourish ends | call `Finish(ComputePerf())` exactly once | — (base hides overlay) |

**Trigger details:**
- **Node ENTER**: when `Avatar.EdgeT ≥ 1` on the edge leading into node `k` (walking phase), set `Avatar.AtNode=k`, `Avatar.OnEdge=-1`, `NodeChallenge.Active=true`, seed hazard from `Nodes[k].SeedSalt` (§8). `Plain` nodes auto-clear after a short jog (no challenge).
- **Node CLEAR**: `NodeChallenge.Cleared=true` → append `k` to `Route` if new; `LastCheckpoint=k`; `BestNodeReached=max(BestNodeReached, Route.Count)`; pick the next edge (clockwise; if a branch alt is available AND player is holding the "take-branch" input, take it — §4). Then transition avatar to walking the chosen out-edge.
- **Node FAIL**: `NodeChallenge.Failed=true` → `DecayPenalty += _decayPerFall`; teleport `Avatar.Pos = Nodes[LastCheckpoint].Pos`; re-arm the *same* node's challenge with a *fresh hazard phase* (telegraph resets so a fall is never an instant re-hit). No lives — infinite retries (fork #4).
- **SEAL**: the final mainline node's clear sets `Phase=Settle`.

**Settle-entry idempotency (guarding a latent double-`Finish`).** `Settle` can be entered from TWO places: (a) clearing the SEAL node, and (b) `RunClock > HARD_CAP_S`. If a SEAL-clear and a hard-cap tick landed on the same frame — or if a fall's respawn re-armed the seal node — both paths could try to advance the machine. We make the transition **idempotent**: the ONLY thing that moves `Play→Settle` is a guarded assignment `if (Phase == Phase.Play) { Phase = Phase.Settle; _settleClock = 0; }` — a second trigger in the same frame sees `Phase != Play` and does nothing. `Finish` is called exactly once, later, from `Settle→Done` (`if (Phase==Phase.Settle && _settleClock >= SETTLE_DUR) { Phase = Phase.Done; Finish(ComputePerf()); }`). Even if that path somehow fired twice, `MinigameOverlay.Finish`'s `if (!_running) return;` guard (base `cls:270`) makes the second call a no-op. Respawn never re-arms the SEAL node: a fall re-arms `LastCheckpoint`'s challenge (§ FAIL trigger), and the SEAL node's clear already set `Phase=Settle`, so it is no longer the active node. Two independent guarantees (the Phase-guard + the base `_running` guard) → exactly-once holds under any frame race.

### 3.6 Per-node LOCAL PLAY FRAME (the sub-level each node hosts) — fully defined, invent nothing

A node is a single point `Nodes[k].Pos` on the ring, but its challenge plays out in a **fixed-size local frame** anchored to that point. The whole traversal happens in ONE surface-local coordinate system (design-space px, §6.1); "local frame" means a rectangle centred on the node, NOT a separate coordinate space — there is no camera swap, no rotation of the play axes. This is the single most load-bearing definition in the doc; everything in §4.4 reads from here.

**Axes are GLOBAL and constant (this resolves the "which way is run vs gravity" question):**
- **Gravity is always +Y (screen-down).** `GRAVITY` pulls toward larger Y everywhere, in every node, regardless of where the node sits on the ring. The ring is a *layout* device for where nodes are drawn; it does NOT rotate the platformer. A HeavyLeap at the top of the ring and one at the bottom both jump *up* (−Y) over a block that sits *below* (+Y). This keeps the platformer legible (master §4.4 "feel stays honest").
- **"Run" is always +X_local = the direction from this node toward the NEXT node on the taken route,** but FLATTENED to a pure horizontal traversal inside the frame. Concretely: the avatar does not physically slide along the tilted ring chord *during* a challenge; the edge-walk (a pure lerp along the chord, §4.2) is what moves it between nodes. When a challenge begins, the avatar is placed at the frame's LEFT edge and must reach the frame's RIGHT edge (the **exit line**); on clear it snaps to `Nodes[k].Pos` and the next edge-walk lerp begins. So the ring geometry never feeds gravity or run direction — it only orders nodes and draws the connecting lines.

**The local frame rectangle.** For active node `k`, the frame is centred on `Nodes[k].Pos`:
```
FRAME_W = 260 * S      // design px, horizontal extent of one node's sub-level
FRAME_H = 180 * S      // design px, vertical extent
frameLeft   = Nodes[k].Pos.X - FRAME_W/2
frameRight  = Nodes[k].Pos.X + FRAME_W/2
frameTop    = Nodes[k].Pos.Y - FRAME_H/2
frameBottom = Nodes[k].Pos.Y + FRAME_H/2
floorY      = Nodes[k].Pos.Y + 70 * S        // the ground plane the avatar stands/runs on
platformY   = floorY                          // §4.2 "platformY" == floorY for grounded kinds; HoldStill overrides (below)
spawnPos    = new Vector2(frameLeft + 16*S, floorY)   // avatar starts here when the challenge arms
exitX       = frameRight - 16*S               // §4.4 "exit-x" / "exit line" — cross this (grounded & alive) to CLEAR
```
The frame is clamped to stay inside the course inset `(80,80)–(1200,640)` (§6.1); nodes are on a 240px ring inside a 1280×720 box so a 260×180 frame never leaves the surface. Frames of adjacent nodes may visually overlap on the ring — harmless, because **only the `AtNode` frame draws its hazard and runs physics** (§6.4 draw-legality); the inactive neighbours show only their node disc.

**Per-kind geometry (every symbol §4.4 references, given a concrete value):** all relative to the frame above. `H` = half of the referenced span.
```
SpikeRun   : corridor spans frameLeft→exitX along floorY. A row of NB spike bars, NB = 3 + round(Interp(0,2)),
             evenly spaced across [frameLeft+40*S, exitX-20*S]. Each bar: width 14*S, max height 46*S rising from
             floorY upward; "closed" (lethal) when HazardPhase > SPIKE_OPEN_FRAC. Avatar runs +X at _avatarSpeed and
             may jump (arc clears a bar). "exit-x" = exitX.
TightGap   : one vertical pinch wall pair at  pinchX = Nodes[k].Pos.X  (frame centre). gapCenter (a Y) = floorY - 40*S;
             gapHalf = clamp(34*S * HazardWindow/baseWin, 12*S, 40*S)  (tighter window → smaller gap). Walls are solid
             above and below the gap. Avatar must be within |Pos.Y - gapCenter| < gapHalf as Pos.X crosses pinchX.
HeavyLeap  : one immovable block. blockLeft = Nodes[k].Pos.X - 30*S; blockRight = Nodes[k].Pos.X + 30*S;
             blockTop = floorY - 64*S (block rises from floorY to blockTop, 60*S wide, 64*S tall). CLEAR when
             Pos.X > blockRight while Pos.Y < blockTop (cleared its top); FAIL if the avatar AABB overlaps the block.
Glide      : two updraft columns. updraftX_near = frameLeft + 40*S; updraftX_far = exitX - 30*S. Between them the floor
             is a PIT (no floorY collision in x∈(updraftX_near, updraftX_far)); falling past  pitFloorY = frameBottom
             = FAIL. Holding [Space] applies GLIDE_FALL_MUL. CLEAR = reach updraftX_far with Pos.Y < floorY.
             "floorY" in the §4.4 Glide-fail row means pitFloorY (=frameBottom).
HoldStill  : a fragile platform at platformY_hold = Nodes[k].Pos.Y (frame centre, NOT floorY — the avatar stands
             mid-frame on a ledge). bandCenter (an X) = Nodes[k].Pos.X. The safe band is a HORIZONTAL X-window:
             currentBandHalf lerps HOLD_BAND_START→HOLD_BAND_END over Dwell (see §4.4/§6.4). Constrained motion:
             gravity OFF; [no jump]; left/right drift is a small auto-wander (§4.4 note) the player must NOT correct
             past the band. CLEAR when Dwell ≥ DWELL_TARGET*_windowScale while |Pos.X - bandCenter| < currentBandHalf.
             (Axis resolution: HoldStill is an X-axis hold — see the §4.4 clarifying note.)
MovingHazard: floor run frameLeft→exitX along floorY; one sweeping vine anchored at  vineAnchor = new Vector2(
             Nodes[k].Pos.X, frameTop). Its tip sweeps a horizontal arc  sweepX = Nodes[k].Pos.X + sin(HazardPhase*TAU)
             * 70*S  reaching down to  vineReachY = floorY - 8*S. FAIL if the vine segment overlaps the avatar AABB.
             CLEAR = reach exitX un-hit.
BlindDash  : identical geometry to SpikeRun (corridor + spike bars) but every hazard element draws at α0.35 (§6.4).
             Same exitX / floorY / bar spacing. The tell is dim, never absent.
SlowMoDodge: floor run; one horizontal bolt on a fixed  boltLineY = floorY - 30*S  ("bolt line"), a Streak crossing
             frameLeft→frameRight over the slowed window. Avatar dodges by leaving boltLineY (jump or duck-step) so
             |Pos.Y - boltLineY| > 18*S at the frame the bolt's X passes the avatar's X. localScale=0.35 (§1.7).
ChaosGate  : the seed picks one of {SpikeRun,TightGap,MovingHazard} (§8) and uses THAT kind's geometry verbatim, plus
             the amber flag ring (§6.4). No new geometry.
Plain      : flat floor at floorY, no hazard, no pit. Auto-clears after 0.6/_hazardSpeedGlobal s of jog to exitX.
```

**Edge-walk ↔ node hand-off (the seam between lerp-travel and platforming):**
1. While `Avatar.AtNode == -1`, the avatar is on an edge: `Pos = Nodes[A].Pos.Lerp(Nodes[B].Pos, EdgeT)` (§4.2). Gravity/jump are OFF during edge-walk; the mote simply glides along the drawn sigil line. `Facing` = sign of `(B.Pos - A.Pos).X` for the trail.
2. On arrival (`EdgeT ≥ 1-EDGE_ARRIVE_EPS`) at node `k=B`: set `AtNode=k`, `OnEdge=-1`, `NodeChallenge.Active=true`, and **place the avatar at `spawnPos` of k's frame**, `Vel = (0,0)`, `Grounded=true`. Physics now runs for THIS frame only.
3. On CLEAR: set `AtNode=-1`, snap `Pos = Nodes[k].Pos`, choose the out-edge (§3 CLEAR trigger), set `OnEdge` to it, `EdgeT=0`, and resume edge-walk. On FAIL: teleport to `Nodes[LastCheckpoint].Pos`, then immediately begin the edge-walk *into* the failed node again from LastCheckpoint (so the retry re-approaches through the same frame with a fresh, safe hazard phase, §3 FAIL trigger). This makes respawn a clean re-entry, never an in-frame mid-air resurrection.

**Why radial layout never fights the platformer:** the ring only decides `Nodes[k].Pos` (draw position + edge ordering) and the lerp path between nodes. Inside a frame, +X is screen-right and +Y is screen-down, unconditionally. There is no per-node rotation to reason about; "clockwise" (§6.2) is purely the *order* in which frames are visited and the direction the connecting lines are drawn — it does not rotate gravity or the run axis. A coder implements ONE platformer frame and reuses it at every node position.

---

## §4. TICK MATH

All constants are `private const double` unless noted. Starting values are the shipped defaults. `dt` is clamped to `≤0.05s` at the top of `OnTick` (spiral-of-death guard). `RunState.Anim += dt` always; `RunClock += dt` only in `Play`.

### 4.1 Constants (named, with starting values)

```
FLIP_DUR        = 0.90   // s, sigil flip-up transition
PLAN_MAX_S      = 6.00   // s, max free planning time
SETTLE_DUR      = 1.10   // s, sealing flourish
HARD_CAP_S      = 90.0   // s, absolute run cap (bail to Settle with a partial)
COYOTE          = 0.10   // s, jump grace after leaving ground
JUMP_BUFFER     = 0.12   // s, buffered jump before landing
GRAVITY         = 1500   // px/s^2  (== _gravity; constant across difficulty)
JUMP_VEL        = -560   // px/s    (== _jumpVel; constant)
GLIDE_FALL_MUL  = 0.35   // gravity multiplier while holding [Space] in Glide
DWELL_TARGET    = 0.80   // s, HoldStill required in-band dwell (× _windowScale)
HOLD_BAND_START = 60     // px, HoldStill safe-band half-width at node entry
HOLD_BAND_END   = 22     // px, band half-width it shrinks to over DWELL_TARGET
SPIKE_OPEN_FRAC = 0.55   // fraction of the spike cycle that is passable
EDGE_ARRIVE_EPS = 0.02   // EdgeT proximity to count as "arrived"
DECAY_MAX       = 0.55   // cap on total DecayPenalty (a wipe-out floor, never 0)
TIME_BONUS_MAX  = 0.06   // max soft speed bonus
PAR_TIME_S      = 22.0   // s, reference "good pace" for full course (scaled by node count)
```

### 4.2 Avatar kinematics (per frame, only in `Play`)

Edge-walk (between nodes): the avatar slides along the current edge at the run speed.
```
speed      = _avatarSpeed * profile.Time        // Time∈[0.75,1.35]  (§2.2)
EdgeT     += (speed / edge.Length) * dt
Pos        = Nodes[edge.A].Pos.Lerp(Nodes[edge.B].Pos, EdgeT)   // clockwise A→B
if EdgeT >= 1 - EDGE_ARRIVE_EPS: enter node edge.B
```
In-node kinematics (SpikeRun/HeavyLeap/TightGap/Glide use gravity+jump; HoldStill/MovingHazard/BlindDash/SlowMoDodge use constrained motion):
```
localScale = NodeChallenge.SlowScale            // 1, or 0.35 for SlowMoDodge
sdt        = dt * localScale
Vel.Y     += GRAVITY * (holdingSpace && Kind==Glide ? GLIDE_FALL_MUL : 1) * sdt
Pos       += Vel * sdt
Grounded   = (Pos.Y >= platformY - 1)  // per-node platform test
CoyoteLeft = Grounded ? COYOTE : max(0, CoyoteLeft - dt)
JumpBufferLeft = max(0, JumpBufferLeft - dt)
if JumpBufferLeft>0 && (Grounded || CoyoteLeft>0): Vel.Y = JUMP_VEL; JumpBufferLeft=0; CoyoteLeft=0
```

### 4.3 Hazard window & tempo (per node, computed at node build in OnBegin)

```
// base window by kind (seconds of "clean" opportunity), before difficulty & tags
baseWin(kind) = { SpikeRun:0.42, TightGap:0.34, MovingHazard:0.55, BlindDash:0.50,
                  Glide:0.90, HeavyLeap:0.70, HoldStill:DWELL_TARGET, SlowMoDodge:0.65, ChaosGate:0.44, Plain:1.0 }
windowMul_tags = clamp(1 - profile.Vol/120, 0.6, 1.4)      // §2.2 Vol → window
HazardWindow   = baseWin(kind) * _windowScale * windowMul_tags     // _windowScale from difficulty (§7)
HazardSpeed    = baseSpeed(kind) * _hazardSpeedGlobal * clamp(profile.Rx,0.6,1.6) * (1+(tier-1)*0.06)
  where baseSpeed(kind) = { SpikeRun:1.4, TightGap:1.0, MovingHazard:1.1, BlindDash:1.0,
                            Glide:0.8, HeavyLeap:0.9, HoldStill:1.0, SlowMoDodge:0.6, ChaosGate:1.3, Plain:1.0 }
```
Hazard timelines (per frame while `NodeChallenge.Active`): `HazardPhase += HazardSpeed * sdt` (wrap 0..1). The *pass window* is `HazardPhase ∈ [0, SPIKE_OPEN_FRAC]` for SpikeRun/ChaosGate; a sine-swept gap for MovingHazard; a shrinking band for HoldStill/TightGap. Clean-clear test is evaluated the frame the avatar crosses the node's exit line — see §4.4.

### 4.4 Per-kind clear/fail rule (exact)

| Kind | Clear when | Fail when |
|---|---|---|
| `SpikeRun` | avatar reaches exit-x while `HazardPhase ∈ [0,SPIKE_OPEN_FRAC]` | touches a spike (avatar rect overlaps a closed spike bar) |
| `TightGap` | avatar centre passes through the gap (|Pos.y - gapCenter| < gapHalf) | |Pos.y - gapCenter| ≥ gapHalf at the pinch x |
| `HeavyLeap` | avatar clears the block (Pos.x > blockRight while Pos.y < blockTop) | avatar rect overlaps the block |
| `Glide` | reaches `updraftX_far` with `Pos.Y < floorY` (§3.6) | `Pos.Y > pitFloorY` (=`frameBottom`) — fell into the pit |
| `HoldStill` | `Dwell ≥ DWELL_TARGET*_windowScale` while `|Pos.X - bandCenter| < currentBandHalf` (X-axis hold; bandCenter is `Nodes[k].Pos.X`, §3.6) | `|Pos.X - bandCenter| ≥ currentBandHalf` before dwell completes → ledge "cracks" → fail |
| `MovingHazard` | reaches exit-x without the sweeping vine overlapping avatar | vine overlaps avatar |
| `BlindDash` | reaches `exitX` while `HazardPhase ∈ [0,SPIKE_OPEN_FRAC]` (SpikeRun geometry, telegraph dimmed to α0.35 — the tell exists, faint) | touches a closed spike bar (SpikeRun collision, §3.6) |
| `SlowMoDodge` | `|Pos.Y - boltLineY| > 18*S` (§3.6) the frame the bolt's X passes the avatar's X, during the slowed window | bolt Streak overlaps the avatar AABB on `boltLineY` |
| `ChaosGate` | per the seeded sub-kind's rule | per the seeded sub-kind's rule |
| `Plain` | after `0.6/ _hazardSpeedGlobal` s of jog | (cannot fail) |

**HoldStill axis (resolving the §1.2/§6.4 ambiguity — it is an X hold):** HoldStill is a **horizontal (X-axis) balance**, not a vertical one. The avatar stands on a fragile ledge at `platformY_hold = Nodes[k].Pos.Y` (frame centre, §3.6) with **gravity OFF** (constrained motion, §4.2). A slow auto-wander nudges `Pos.X` left/right (deterministic from `SeedSalt`, amplitude ≤ `HOLD_BAND_START*0.5`); the player counter-nudges with left/right steps to stay inside the shrinking band `|Pos.X - bandCenter| < currentBandHalf`. `HOLD_BAND_START=60` / `HOLD_BAND_END=22` are **X half-widths in px** (the "of WHAT axis" the review flagged: X, around `bandCenter = Nodes[k].Pos.X`). The band shrinks from START→END over `DWELL_TARGET*_windowScale`. Visually the fragile ledge is a horizontal bar and the band is a vertical safe-corridor drawn on it (§6.4) — the "shrinking band" is the shrinking allowed X-excursion, made unmistakable by the crumbling-edge `Crack` etch.

**Design note on constant JUMP_VEL/GRAVITY:** platformer *feel* must stay identical across difficulty (a jump that changes height per craft is illegible). Hardness comes ONLY from `HazardWindow` (timing tightness), node count, and hazard tempo — never from mutating the jump arc. This is the master-plan "difficulty = intensity, tags = character, feel stays honest" principle applied concretely.

### 4.5 Coyote-time + input buffer (already in constants; the rule)

Jump fires if a jump was pressed within the last `JUMP_BUFFER` seconds AND the avatar is grounded OR left the ground within the last `COYOTE` seconds. This is the entire "keep it tight" input contract from §3.5 roadblock (4).

### 4.6 Scoring → `perf` (`ComputePerf()`, called once at `Done`)

**Progress accounting (this resolves the routeFrac contradiction — read first).** The self-contradiction the review flagged came from conflating "nodes cleared" with "mainline progress." We separate the two with an explicit **mainline-coverage** count that a branch route *advances*, so a shorter branch route never scores LESS progress than the mainline it replaced:

- Every branch alt `a` records `(a.BranchFrom, a.BranchTo) = (kFrom, kTo)` = the mainline pair it forks from and rejoins (`kFrom → a → kTo`, §6.2 always `kTo = (kFrom+1)%N` for a single-node chord). A branch alt **covers** the mainline span it bypasses: clearing the chord `kFrom→a→kTo` counts as having reached `kTo` on the mainline (it is a legal alternate path between the same two mainline nodes), PLUS credits the alt node itself in `rewardBonus`.
- `MainlineReached` = the highest mainline index the taken route has legally reached (via mainline edges OR via a covering branch chord). This is the monotone high-water mark; a branch route reaches the same `kTo` a mainline hop would, so it is never behind.

```
routeFrac   = MainlineReached / max(1, TotalMainline)          // PRIMARY metric: fraction of the mainline reached.
              // A branch chord kFrom→a→kTo advances MainlineReached to kTo exactly as the mainline hop kFrom→kTo would,
              // so a shorter/richer branch route is NEVER penalised on progress. routeFrac depends ONLY on how far
              // along the mainline you got, not on how many discs you happened to touch. (Fixes the old "fewer nodes
              // → smaller routeFrac" bug: branch traversal is progress-equivalent to the mainline it replaces.)
rewardBonus = clamp( (Σ Reward over cleared nodes) / cheapRouteReward - 1, 0, 0.20 )
              // taking richer/HARDER branches earns up to +0.20. Branches have Reward > the mainline node they bypass
              // (§2.3 branch rider, §7), so a branch route's numerator EXCEEDS the mainline baseline → positive bonus.
              // cheapRouteReward = Σ Reward over the all-MAINLINE route (the guaranteed no-branch path 0→1→…→N-1→0).
              // This sum is KNOWN at OnBegin (deterministic node Rewards, §1.3) — precompute once, store in RunState.
timeBonus   = clamp( (PAR_TIME_S*nodeScale - RunClock) / (PAR_TIME_S*nodeScale) , 0, 1) * TIME_BONUS_MAX
decay       = min(DecayPenalty, DECAY_MAX)                     // subtractive; falls hurt but never zero you
perfRaw     = 0.72*routeFrac + rewardBonus + timeBonus - decay
perf        = clamp(perfRaw, 0.0, 1.0)
```
`nodeScale = TotalMainline / 6.0` (par time scales with course length). `cheapRouteReward` is a single precomputed `double` on `RunState` (the mainline Reward sum), so `rewardBonus` needs no live search — the numerator is `Σ Reward` over `Route` members, the denominator is that constant.

**Worked check (why a branch route now scores higher, deterministically).** 6-node mainline, each mainline Reward 1.0 → `cheapRouteReward = 6.0`, full-mainline `routeFrac = 1.0`. A branch chord replaces node 3 with alt `a` (Reward 1.5) covering `2→a→4`: the expert route clears nodes 0,1,2,a,4,5 → `MainlineReached = 6` → `routeFrac = 1.0` (SAME progress, not less), `Σ Reward = 1+1+1+1.5+1+1 = 6.5` → `rewardBonus = clamp(6.5/6.0 - 1, 0, 0.20) = 0.083`. Mainline-only expert: `routeFrac=1.0, rewardBonus=0`. So the branch route beats the mainline by the reward term alone — never by inflating progress. The contradiction is gone.

**Perf-band targets (must hit — verified in §10 headless test). Bands quoted against `CraftFx.QualityBands` thresholds: Normal=[0,0.25), Fine=[0.25,0.50), Superior=[0.50,0.75), Masterwork=[0.75,0.90), Legendary=[0.90,1.0].**
| Player model | Behaviour | Expected `perf` | Band(s) it lands in |
|---|---|---|---|
| Masher | jumps randomly, falls each hard node ~3×, only clears easy/Plain nodes, mainline only | **0.20–0.30** | **Normal→Fine** (0.20–0.25 Normal; 0.25–0.30 Fine — the masher straddles the Normal/Fine seam by design; the target is "≤ Fine, never Superior") |
| Competent | clears mainline cleanly, ~1 fall total, ignores branches | **0.55–0.68** | Superior |
| Expert | memorised optimal branch route, ~0 falls, fast pace | **0.90–0.98** | Legendary |

Tuning levers if a band misses: the `0.72` routeFrac weight (raises the floor/mid), `_decayPerFall` (separates masher from competent), `rewardBonus` cap (separates competent from expert). The masher band is intentionally allowed to sit across the Normal/Fine boundary — the hard requirement (test #7) is masher `< 0.50` (never Superior), competent in `[0.50,0.75)`, expert `≥ 0.90`.

### 4.7 Live quality meter feed (`SetQuality`)

Every frame in `Play`/`Settle`:
```
liveRewardBonus = clamp( (Σ Reward over Route so far) / cheapRouteReward - 1, 0, 0.20 )   // SAME formula as §4.6,
                  // evaluated on the cleared-so-far Route against the precomputed constant cheapRouteReward. It is
                  // NOT an "estimate" — cheapRouteReward is known at OnBegin, so this is the exact partial bonus.
SetQuality( clamp( 0.72 * (MainlineReached / max(1,TotalMainline)) + liveRewardBonus - min(DecayPenalty,DECAY_MAX), 0, 1) )
```
(The earlier `currentRewardBonusEstimate` placeholder is removed — there is nothing to estimate, because `cheapRouteReward` is a precomputed constant, so the live meter uses the exact `liveRewardBonus` above.) `timeBonus` is intentionally excluded from the LIVE meter (it can only be finalised at `Done`) so the meter never ticks down as the clock runs — it climbs monotonically with progress + reward and only dips on a fall. Call `FlashQuality()` on each node CLEAR; `Shake(6f)` on each FAIL. This makes skill-becoming-quality felt moment to moment (base meter climbs Normal→Legendary).

---

## §5. INPUT MAP

The overlay is `FullscreenScene`; `OnInput` receives gameplay input (base handles Esc). F1/F7 are claimed in `_Input` (earliest stage) exactly like `AlchemyMinigame._Input` (line 250).

| Key / action | Phase(s) | Effect | Handling |
|---|---|---|---|
| `[Space]` press | `Ready` | start flip-up → `Plan` | `OnInput`; `SetInputAsHandled()` |
| `[Space]` press | `Plan` | skip plan → `Play` | `OnInput` |
| `[Space]` press | `Play` | **jump** (sets `JumpBufferLeft=JUMP_BUFFER`); in `Glide` also enables slow-fall while held | `OnInput`, press+release tracked (buffer on press, glide on hold) |
| `[Space]` release | `Play` | end Glide slow-fall | `OnInput` (`k.Pressed==false`) |
| `[Shift]` hold | `Play`, evaluated at the **moment node `k` CLEARs** | **take-branch**: if `k` has a branch alt (`∃ alt: alt.BranchFrom == k`) AND `[Shift]` is held on the clear frame, the out-edge chosen is `k→alt` instead of `k→(k+1)%N` | `OnInput` sets a `_shiftHeld` bool on press/release; the CLEAR trigger (§3) reads `_shiftHeld` at that instant |
| `[F1]` | any | toggle dev event log | `_Input` → `_dev.HandleKey` → `SetInputAsHandled()` |
| `[F7]` | any | toggle playtest notes box (a real `LineEdit`) | `_Input` → `_dev.HandleKey` |
| `[Esc]` / `[Esc][Esc]` | any while running | base warns then abandons (materials lost) | **base `_UnhandledInput`** — we do NOT override |

**Hit-testing / focus:**
- No mouse hit-testing on the play surface — the Sigil Run is keyboard-only (`[Space]`/`[Shift]`). A single `Button` ("CHANNEL ▸ [Space]") in the Ready overlay uses `FocusMode = None` so keyboard events flow to `OnInput` (Alchemy parity).
- Avatar/hazard collision uses AABB overlap in surface-local coords (no physics engine) — the avatar is a `12×12 px` box centred on `Avatar.Pos`.
- `_dev.NotesEditHasFocus` gate: while the F7 notes box has focus, ignore `[Space]` in `OnInput` (so typing a note never jumps the avatar) — mirror Alchemy line 263's guard.

**Branch-selection timing (fully pinned).** The take-branch decision is a **single instantaneous read on the clear frame of the forking node** — NOT held throughout traversal, not read at edge-selection-after-the-fact. Sequence: (1) the player holds `[Shift]` as they finish clearing node `k`; (2) at the exact frame `NodeChallenge.Cleared` flips true, the CLEAR trigger reads `_shiftHeld`; (3) if held AND a branch alt exists, the out-edge is `k→alt`, else `k→(k+1)%N`. Once the out-edge is committed, releasing `[Shift]` mid-traversal does nothing — the choice is latched into `Avatar.OnEdge` for that hop. If the player is NOT holding at the clear frame, the mainline edge is taken even if they press `[Shift]` a frame later (no retroactive switch). A node with no branch alt ignores `[Shift]` entirely. This makes the input unambiguous: "hold Shift as you finish the node you want to fork from."

**F1/F7 claim order (critical):** `_Input` runs before `_UnhandledInput`/`_UnhandledKeyInput`, so claiming F1/F7 in `_Input` and calling `GetViewport().SetInputAsHandled()` prevents them from reaching `WorldBootstrap`/`CombatWorld`'s global debug handlers (which also read F-keys). Copy the exact guard: `if (!Running) return; if (@event is not InputEventKey {Pressed:true, Echo:false} k) return; if (_dev.HandleKey(k.PhysicalKeycode)) { _surf.QueueRedraw(); GetViewport().SetInputAsHandled(); }`.

---

## §6. VISUAL SPEC

### 6.1 Surface & layout (resolution-relative)

`FullscreenScene => true` → the base mounts our `BuildUi(VBoxContainer scene)` filling the viewport. We add ONE `Control _surf` with `SetAnchorsPreset(FullRect)` and a `Draw += DrawSurface` handler. All drawing is in **surface-local px** on a virtual **design box `DESIGN = (1280, 720)`**; we compute `S = min(size.X/1280, size.Y/720)` and an origin offset to letterbox-centre, so layout rects below are given in design-space and multiplied by `S` (helper `P(x,y) => origin + new Vector2(x,y)*S`). This keeps the course legible at any window size.

`BackdropTint` override → a slightly lifted purple for the fullscreen scene so the course reads on top: `Top=(0.13,0.09,0.18)`, `Bottom=(0.04,0.03,0.07)`, `Glow=(0.72,0.42,1.0)`. `ShowAmbient => true` (drifting violet motes = arcane dust; base seats the emitter at the bottom).

Design-space rects:
| Element | Rect / anchor (design px) | Notes |
|---|---|---|
| Course region | full `(0,0,1280,720)` inset 80px | the sigil is laid out inside `(80,80)–(1200,640)` |
| Progress pip trail | top strip `(40, 28)` → one pip per mainline node, 26px pitch | the ONLY numeric-ish HUD (discrete pips, no number) |
| Ready prompt box | centred, `(−260..+260, +120..+210)` from centre | `PanelContainer`, hidden once `Play` |
| Hint line | bottom centre, y=`690` | one-line controls hint |
| F1 log gutter | right side, `250px` wide when `_dev.ShowLog` | `_dev.DrawLog` |
| F7 notes box | `_dev.BuildNotesPanel(_surf)` (centre-bottom) | shared harness owns it |

### 6.2 Sigil layout (the flip-up course generator)

The nodes' `Pos` are placed on a **clockwise ring** derived from the placement pattern. Because the actual bench placement graph isn't handed in (`RecipeContext` has no coordinates), we synthesize a canonical clockwise polygon (§9-R2 guarantees legality):
```
N = TotalMainline (mainline node count, §7)
center = P(640, 380); ringR = 240*S; 
for i in 0..N-1:
    ang = -PI/2 + i * TAU/N          // start at top, go CLOCKWISE (+ increasing angle = CW in screen space, y-down)
    Nodes[i].Pos = center + Vector2(cos(ang), sin(ang)) * ringR
Edges: mainline edge i -> (i+1)%N (the last edge i=N-1 -> 0 is the SEAL closing the sigil)
Branch alts (if unlocked): for a chosen subset of mainline nodes k, add an inner "chord" node at
    center + Vector2(cos(ang_k+halfStep), sin(ang_k+halfStep)) * ringR*0.55, with edges k->alt->(k+1)%N.
```
The polygon is always a simple convex ring → the mainline path `0→1→…→N-1→0` is always legal and clockwise. Branch alts are strictly-inner chords → always reachable and rejoin the mainline (never a dead end).

**"Clockwise" here means node VISIT ORDER + line-draw direction only — it does NOT rotate the platformer.** With `ang = -PI/2 + i*TAU/N` and Godot screen space (y-down), increasing `i` steps the node position clockwise around the ring (start at top, next node to the top-right, etc.), and the drawn edge `i→(i+1)%N` follows that winding. The avatar's clockwise *feel* comes from the edge-walk lerp visiting nodes in ascending `i`. This is fully independent of the per-node run axis: inside every node frame, run is +X and gravity is +Y (§3.6), regardless of where on the ring that node sits. So there is nothing to reconcile between "clockwise winding" and "per-node run direction" — the winding orders frames; the frame defines its own local axes. A coder need not derive run-direction from the chord angle; §3.6 fixes it globally.

### 6.3 Flip-up transition (`Ready`→`Plan`)

A `Tween` on a `_flip ∈ [0,1]` field, `FLIP_DUR=0.9s`, `TransCubic/EaseOut`. `DrawSurface` interpolates the sigil from a flat, foreshortened board (scale-y 0.25, alpha 0.5, drawn low) to the full upright ring (scale-y 1, alpha 1). Concretely: `drawScaleY = lerp(0.25,1,_flip)`, `drawAlpha = lerp(0.5,1,_flip)`, `yLift = lerp(120*S, 0, _flip)`. Plus a `CraftFx.RingPulse` emanating from centre at `phase=_flip` (the sigil "lifting"). This is the juicy "pattern becomes the space" beat (§3.5 roadblock 3).

### 6.4 EVERY drawn element (element · rect/anchor · colour source · CraftFx primitive · z-order · draw-legality)

Z-order via draw call order inside `DrawSurface` (later = on top). Legality = when it may draw.

| # | Element | Position/size (design px) | Colour source | Primitive | z | Draw-legality |
|---|---|---|---|---|---|---|
| 1 | Sigil edges (lines) | node→node, width `3*S` | `Accent` @ α0.35 (walkable), branch edges `Accent`@α0.22 dashed | `_surf.DrawLine` (dashed = manual segments) | 0 | `Plan`,`Play`,`Settle` |
| 2 | Sigil glow ring | centre, `ringR*1.1` | loadout-dominant `FamilyColor` @ α0.14 via `DeMuddy` | `CraftFx.Glow` | 0 | always after flip |
| 3 | Node discs (uncleared) | `Nodes[i].Pos`, r=`18*S` | node `Family` colour (§2.4) @ α0.7 | `_surf.DrawCircle` + `CraftFx.Ring` outline | 1 | `Plan`,`Play`,`Settle` |
| 4 | Node kind glyph | at node centre, glyph radius `GR = 9*S` | white @ α0.8 | tiny primitive per kind, all sized to `GR` (exact args below the table) | 2 | `Plan`,`Play` |
| 5 | Cleared-node fill | node centre, r=`18*S` | gold `UiTheme.Rarity["legendary"]` @ α0.9 | `_surf.DrawCircle` + `CraftFx.Glow` | 1 | when `i∈Route` |
| 6 | Active node hazard | around active node (see per-kind below) | node `Family` colour, brightened | per-kind (below) | 3 | only the `AtNode` while `Play` |
| 7 | Avatar (light-mote) | `Avatar.Pos`, r=`7*S` | `Hot`=`Brighten(Accent,0.25)` core + `Family` halo | `_surf.DrawCircle` + `CraftFx.Glow(r=16*S)` | 5 | `Play`,`Settle` |
| 8 | Avatar trail | last ~8 positions | avatar colour, fading | `CraftFx.Wake(prev,Pos)` each frame | 4 | `Play` |
| 9 | Route trail (cleared path) | along cleared edges | gold @ α0.6 | `CraftFx.Streak` per cleared edge | 2 | `Play`,`Settle` |
| 10 | Progress pip trail | top strip, per mainline node | pip lit = gold, dim = `Accent`@α0.22 | `_surf.DrawCircle` (r=`6*S`) | 6 | always |
| 11 | Clockwise arrow indicator | small arc-arrow near centre, spinning slowly | `Accent`@α0.5 | `CraftFx.Arc` + arrowhead poly | 2 | `Plan`,`Play` |
| 12 | Fall/respawn flash | at respawn node | `Crack`=`Color(1,0.35,0.35)` | `CraftFx.RingPulse(phase=respawnFlash)` + `Shake(6)` | 5 | on FAIL, decays 0.5s |
| 13 | Seal flourish | each cleared node + centre | band colour `CraftFx.Band(perf).Col` + gold | `CraftFx.Burst` (per node, staggered) + `RingPulse` | 5 | `Settle` |
| 14 | Ready prompt | centre box | `Text`=`UiTheme.Text`, accent border | `PanelContainer`+`Label` | 7 | `Ready` |
| 15 | Hint line | bottom | `Color(0.86,0.8,0.98)` | `Label` | 7 | `Ready`,`Plan`,`Play` |
| 16 | F1 log | right gutter | shared | `_dev.DrawLog` | 9 | `_dev.ShowLog` |
| 17 | Ambient dust | full (base emitter) | adornments `Ember` | base `CpuParticles2D` | 0 | always |

**Per-kind active-hazard drawing (element #6):**
- `SpikeRun`: a row of vertical spike bars across the corridor; each bar's height oscillates with `HazardPhase` (closed when `HazardPhase>SPIKE_OPEN_FRAC`). Draw spikes as `DrawColoredPolygon` triangles in `FamilyColor(HEAT)`; when closed, tint to `Crack`. Telegraph: a thin `CraftFx.Ring` pre-pulse 0.25s before close.
- `TightGap`: two `RoundRect` pinch walls with a fixed gap; gap edges glow (`CraftFx.Glow`) so the safe line is unmistakable.
- `HeavyLeap`: a solid `RoundRect` block in `FamilyColor(TERRA)` de-muddied; a faint arc preview of the ideal jump (`CraftFx.Arc`).
- `Glide`: two `CraftFx.Wisp` updraft columns (cyan) + a floor line; holding `[Space]` draws denser wisps (feedback that slow-fall is active).
- `HoldStill`: a shrinking safe-band rectangle (`RoundRect`) whose half-width lerps `HOLD_BAND_START→HOLD_BAND_END` over dwell; a `CraftFx.Crack` etches in as the ledge crumbles when you drift out.
- `MovingHazard`: a sweeping vine drawn with `StateVisual.Vines(ci:_surf, c:vineAnchor, R:60*S, col:FamilyColor(GROVE) de-muddied, m:0.9f, anim:(float)(RunState.Anim + (float)HazardPhase), down:true, flower:false)` — `m=0.9` gives a full, legible vine; `down:true` drapes it downward from `vineAnchor` (frame-top, §3.6); the sweep is the `vineAnchor.X` offset `sin(HazardPhase*TAU)*70*S` applied to `c` each frame (NOT a rotation of the Vines primitive, which draws its own internal wobble). Collision uses `vineReachY`/`sweepX` (§3.6), not the drawn spline.
- `BlindDash`: the whole node's hazard drawn at α0.35 (the fog) + a `_surf.DrawCircle` shroud disc at α0.55 over the gate; the tell is faint but present (never a betrayal, §8).
- `SlowMoDodge`: a slow bolt (`CraftFx.Streak`) crossing; a subtle desaturation vignette (`DrawRect` dark overlay α0.12) signals bullet-time.
- `ChaosGate`: draws whichever sub-kind the seed picked, plus an amber flag ring (`CraftFx.Ring` in `Amber=Color(1,0.72,0.18)`) so the player KNOWS it's the randomised gate (the tell).
- `Plain`: no hazard; a gentle ground line only.

**Node-kind glyph args (element #4, exact — `c = Nodes[i].Pos`, `GR = 9*S`, `a = (float)RunState.Anim`, glyph colour `g = white α0.8`):**
- `SpikeRun`/fire: `_surf.DrawColoredPolygon` upward triangle, verts `c+(0,-GR)`, `c+(-GR*0.8,GR*0.7)`, `c+(GR*0.8,GR*0.7)`.
- `HoldStill`/ice: `_surf.DrawColoredPolygon(CraftFx.Ellipse(c, GR*0.7, GR, 4))` — a 4-gon diamond.
- `Glide`/air: `CraftFx.Wisp(_surf, origin:c+(0,GR), dir:Vector2.Up, len:GR*1.8, col:g, phase:Mathf.PosMod(a*0.5f,1f), width:2f*S, wobble:5f*S, seed:i, segs:6)`.
- `HeavyLeap`/earth: `_surf.DrawRect(new Rect2(c-(GR*0.75f,GR*0.75f), (GR*1.5f,GR*1.5f)), g)` — a filled square.
- `MovingHazard`/life: `StateVisual.Vines(_surf, c, GR, g, m:0.6f, anim:a, down:false, flower:false)` — a small radiating vine cluster ("micro" = R passed as `GR`, `m=0.6`).
- `BlindDash`/shadow: `_surf.DrawCircle(c, GR*0.8f, new Color(g.R,g.G,g.B,0.4f))` — a dim disc.
- `TightGap`/sharp: two chevron lines `_surf.DrawPolyline([c+(-GR,-GR*0.5f), c, c+(-GR,GR*0.5f)], g, 2f*S)` and its mirror on +X.
- `SlowMoDodge`/temporal: `CraftFx.Arc(_surf, c, GR, 0.3f, Mathf.Tau-0.3f, g, 2f*S)` — a clock-face arc.
- `ChaosGate`/chaos: `CraftFx.Crack(_surf, origin:c, dir:Vector2.Right, len:GR*1.6f, col:g, width:2f*S, seed:i, segs:5)`.
- `Plain`: no glyph (a bare disc reads as "just a jog").

**Animation curves:** node-clear = quality flash (`FlashQuality`) + a 0.3s `Glow` bloom (ease-out). Fall = `Shake(6)` + red `RingPulse` (linear decay 0.5s). Flip-up = Cubic ease-out (§6.3). Seal bursts stagger 0.06s apart along `Route`. Avatar bob while walking = `sin(Anim*6)*2*S` on the trail only (Pos itself follows the edge lerp).

**Draw-legality rules (summary):** hazards draw ONLY for the active node; cleared-node fills draw ONLY for `Route` members; the flip-up scale/alpha gates every sigil element before `Plan` completes; the F1 gutter reserves 250px on the right so the course region shrinks when the log is open (recompute `S`/origin with `size.X - (ShowLog?250:0)`).

---

## §7. DIFFICULTY CURVE (exact `DifficultyPoints → knob`)

`DifficultyPoints` (1..80 practical) is the single dial. `Interp(easy,hard)` maps it linearly on `t=clamp((pts-1)/79,0,1)`. Tier thresholds for gating use `RARE_PTS=21`, `EPIC_PTS=41`, `LEGENDARY_PTS=61` (aligned to the game's Common/Uncommon/Rare/Epic/Legendary point bands from CLAUDE.md's difficulty table).

| Knob | Formula | pts=1 (entry) | pts=80 (legendary) |
|---|---|---|---|
| Node count (mainline) | `baseN = 3 + (# distinct output tags)`; `TotalMainline = clamp(baseN + _nodeCountBias + Σ nodesFromIngredient, 4, 12)` where `_nodeCountBias = round(Interp(0,3))` | ~4 | up to 12 |
| Window scale | `_windowScale = Interp(1.00, 0.55)` → multiplies every `HazardWindow` | 1.00 (roomy) | 0.55 (tight) |
| Avatar speed | `_avatarSpeed = Interp(210, 340)` px/s (then × `profile.Time`) | 210 | 340 |
| Hazard tempo | `_hazardSpeedGlobal = Interp(0.85, 1.35)` (× per-kind base × `profile.Rx`) | 0.85 | 1.35 |
| Decay per fall | `_decayPerFall = Interp(0.045, 0.11)` | forgiving | punishing |
| Branch density | branch alts spawn ONLY if `pts ≥ RARE_PTS`; count = `pts<RARE_PTS ? 0 : min(round(Interp'(0,3)) over [RARE_PTS,80], TotalMainline-2)` | 0 (no branches) | up to 3 optional shortcuts |
| SlowMo scale | `SlowMoDodge.SlowScale = 0.35` (constant; feel, not difficulty) | 0.35 | 0.35 |

**Node-count clamp vs. branch insertion (resolves the R2/clamp interaction the review flagged): branches DO NOT count toward the `[4,12]` cap.** The `clamp(…, 4, 12)` applies to `TotalMainline` ONLY. Branch alts are added *after* the mainline count is finalised and clamped, so `Nodes.Count` may be up to `12 + 3 = 15` while `TotalMainline ≤ 12`. Ordering, made explicit:
1. Compute `TotalMainline = clamp(baseN + _nodeCountBias + Σ nodesFromIngredient, 4, 12)`. This is the SEAL-closed ring size and the scoring denominator (§4.6).
2. Lay out the `TotalMainline` mainline nodes on the ring + their `i→(i+1)%N` edges (§6.2).
3. If `pts ≥ RARE_PTS`, insert `branchCount = min(round(Interp'(0,3)), TotalMainline-2)` inner-chord alts (never more than `TotalMainline-2`, so at least two mainline nodes stay un-forked → the mainline is always a distinct baseline route). Each alt is an *extra* node appended to `Nodes` with `IsBranchAlt=true`; it does NOT increment `TotalMainline`.

So the cap and branch insertion never contend: `TotalMainline` is frozen before any branch exists. `Σ nodesFromIngredient` can push the *pre-clamp* mainline above 12 — the clamp simply drops the excess mainline nodes (the highest-index ingredient contributions are truncated); branches are unaffected because they are computed from `pts`, not from the ingredient node budget.

**Entry example (pts=1, a common "wooden charm", output tags `["utility","wood"]`, one input `oak` Qty1 T1):**
4 mainline nodes, all wide windows (×1.0), avatar 210px/s, tempo 0.85, no branches, decay 0.045. Node kinds: `oak`→GROVE→`MovingHazard` (gentle sweep), plus Plain fillers. A first-timer clears it by jogging and one easy dodge → ~0.55 if clean, ~0.25 if they fall the vine a couple times.

**Legendary example (pts=75, "voidsteel warding sigil", output `["armor","protection","void","legendary"]`, inputs `voidsteel`(→metal/EARTH, T4, Qty2), `arcane essence`(UMBRA, T4), `dragonsteel`(EARTH+`sharp`, T4)):**
~11 mainline nodes + 3 branch alts, windows ×0.55 × (armor/void widen a little via Vol) ≈ still tight, avatar 340px/s, tempo 1.35, decay 0.11. Kinds: EARTH `HeavyLeap`s (heavy, from metals), an UMBRA `BlindDash` (essence, big payoff), a `TightGap` (sharp rider on dragonsteel), branch alts are harder `SpikeRun` chords worth +Reward. Only an expert who memorised the branch route and never falls hits ~0.95.

---

## §8. RANDOMNESS SPEC

**Seeded, reproducible.** All per-run randomness flows through `RunState.Rng` (a Godot `RandomNumberGenerator`), seeded deterministically so the SAME craft is the SAME course (testable, replayable) but different crafts differ (replayability):
```
craftId = Recipe?.OutputId ?? "debug"
tagSig  = concat of all input+output tags, sorted        // order-independent signature
Rng.Seed = (ulong) hash64(craftId + "|" + tagSig + "|" + DifficultyTier)
```
`hash64` = FNV-1a over the UTF-8 bytes (deterministic, no `System.Random`, no wall-clock). Per-node salt `SeedSalt = hash64(craftId + Id + IndexOnRing)` seeds a *local* RNG so each node's micro-variation is independent yet reproducible.

**What is seeded (bounded):**
| Thing | Source | Bounds / telegraph |
|---|---|---|
| Node hazard start-phase | `SeedSalt` | `HazardPhase0 ∈ [0,1)`; on FAIL it RESETS to a *safe* phase (start of the pass window) so a respawn is never an instant re-hit (the tell resets fairly) |
| `ChaosGate` sub-kind | node `SeedSalt` | one of {SpikeRun,TightGap,MovingHazard}; drawn with the amber flag ring so the player KNOWS it's the random gate (telegraph — a *tell*, not a betrayal) |
| Branch-alt placement | run `Rng` | which mainline nodes get an inner chord; always simple/reachable (§9-R2) |
| MovingHazard sweep offset | `SeedSalt` | phase offset only; amplitude fixed by kind |
| Ambient dust | base `CpuParticles2D` | cosmetic only, not gameplay |

**Telegraph rule (master §0.3 — a tell, never a betrayal):** every hazard has a visible pre-pulse (`CraftFx.Ring`/`RingPulse`) ≥0.2s before it becomes lethal; `BlindDash` dims but never removes the tell (α0.35); `ChaosGate` is flagged amber. No hazard can kill the avatar in a frame it just spawned in.

**What is NOT random:** node kinds (deterministic from tags §2.1), node positions (deterministic ring §6.2), scoring weights (deterministic from tags/tier), difficulty knobs (deterministic from points).

---

## §9. ROADBLOCK REGISTER (each §3.5 risk → concrete chosen mitigation)

| # | §3.5 risk | Chosen mitigation (concrete) |
|---|---|---|
| R1 | *Platformer physics in a Control* | A tiny fixed-step kinematic body (§4.2): gravity + jump only, AABB overlap collision, `dt` clamped ≤0.05s. NO physics engine, NO `RigidBody`. Only the ACTIVE node runs physics; edge-walking is a pure lerp. Constants `GRAVITY=1500`, `JUMP_VEL=-560`, `GLIDE_FALL_MUL=0.35`. The physics run inside ONE fixed `FRAME_W×FRAME_H` local frame (§3.6) with global +Y gravity / +X run — reused verbatim at every node position. |
| R2 | *Arbitrary placement graph → always-completable clockwise course* | We DON'T consume bench coordinates (they aren't in `RecipeContext`). We synthesize a **canonical convex ring** of `N` nodes with mainline edges `i→(i+1)%N` (§6.2) — provably a legal clockwise Hamiltonian cycle. Branch alts are strictly-inner chords `k→alt→(k+1)` — always reachable, always rejoin, never a dead end. `TotalMainline` is clamped to `[4,12]` BEFORE branches are inserted, and `branchCount ≤ TotalMainline-2`, so the clamp and branch insertion never contend (§7 "Node-count clamp vs. branch insertion"); `Nodes.Count ≤ 15`, `TotalMainline ≤ 12`. `AssertSolvable()` (§10 test #2) walks the mainline in-order confirming every edge exists AND that every branch alt has both an in-edge (`kFrom→alt`) and out-edge (`alt→kTo`) to mainline nodes. |
| R3 | *Flip-up transition selling "pattern becomes the space"* | A dedicated `Ready→Plan` tween on `_flip∈[0,1]` (§6.3): the sigil rotates/scales up from a foreshortened board with a `CraftFx.RingPulse`. `FLIP_DUR=0.9s`, Cubic ease-out. |
| R4 | *Input tightness (jump/dash, coyote, buffer)* | 1–2 keys only (`[Space]` jump/glide, `[Shift]` take-branch). `COYOTE=0.10s` + `JUMP_BUFFER=0.12s` (§4.5). No mouse in play. |
| R5 | *Death/respawn keeps entry easy without trivialising score* | **Respawn-at-last-node + subtractive score decay** (fork #4), NOT lives: infinite retries so entry is easy; each fall adds `_decayPerFall` (0.045→0.11) to `DecayPenalty`, capped at `DECAY_MAX=0.55` (a wipe-out floor, never 0). Masher vs competent separation lives entirely in this decay term (§4.6). |
| **R6 (doc-new)** | *A node is a single ring POINT, yet must host a 2D platformer sub-level with gravity/jump* — the largest new risk this design introduces (a node is `Nodes[k].Pos`, but SpikeRun/HeavyLeap/etc. need floors, blocks, gaps, an exit line). | **The per-node LOCAL PLAY FRAME (§3.6) is the mitigation.** Every node hosts a fixed `FRAME_W=260*S × FRAME_H=180*S` rectangle centred on `Nodes[k].Pos`, with a defined `floorY`/`spawnPos`/`exitX` and per-kind geometry (every symbol §4.4 uses is a concrete offset in §3.6). Gravity is global +Y, run is global +X (flattened), regardless of ring position — so the ring never rotates the platformer and the SAME frame code runs at every node. Edge-walk↔frame hand-off is a lerp→place-at-spawn→physics→snap-to-Pos→lerp cycle (§3.6). This turns "a point must be a level" from an open problem into one reused rectangle. |
| **R7 (doc-new)** | *Collision tunnelling at clamped-dt spikes* — an `_avatarSpeed*profile.Time` up to ~459px/s × 0.05s ≈ 23px/frame can skip a thin spike bar / narrow gap (12px avatar box). | **Swept-AABB is the pinned collision method** (§4.4/§10 test #9): each frame, sweep the avatar's AABB from `PrevPos`→`Pos` and test the swept rect against hazard rects, rather than point-sampling `Pos`. Thin bars (14px) and gaps thus can't be tunnelled at the 0.05s clamp. The `dt≤0.05s` clamp is a second guard, but the guarantee rests on swept-AABB, which §10 test #9 now asserts is the implemented method. |

---

## §10. TEST PLAN

Headless-checkable (Godot headless / a plain xUnit over the pure-math helpers extracted as `static`). Extract `BuildCourse`, `BuildCourseProfile`, `ResolveNodeKind`, `ResolveChannel`, `ComputePerf`, `AssertSolvable`, `SweptOverlaps` (the collision test), `Interp`, `hash64` as `internal static` pure functions so tests need no scene. The **union vocabulary** the tests iterate = `VOCAB` = every tag this doc's `_baseTable` keys, PLUS every key in `_channelDefault`'s source sets — since `MinigameTagEffects.Tags`/`Metal`/`Wood`/`QualityGrade` are `private`, `VOCAB` is a `static readonly string[]` we declare in the TEST assembly, hand-copied from `MinigameTagEffects.cs` lines 208–235 (the Tags keys ∪ the Metal set ∪ the Wood set ∪ the QualityGrade keys) and from this doc's Quality/Grade + Function/Output tag lists. (We cannot reflect over private members portably, so `VOCAB` is an explicit literal — test #10 guards it against drift.)

**Invariants:**
1. **Seam exactly-once.** Instrument `Finish`/`FailCraft`: assert exactly one is called per run, `perf∈[0,1]`. A run driven to completion calls `Finish` once; an abandoned run (base Esc path) calls neither from our code. (We never call `FailCraft`.)
2. **Solvability/reachability.** For 500 random `(craftId, tag-set, points∈1..80)`: `AssertSolvable(BuildCourse(...))` — the mainline `0→1→…→N-1→0` exists as edges; every branch alt has both an in-edge and an out-edge to a mainline node; no orphan nodes; N∈[4,12].
3. **Determinism.** `BuildCourse(seed)` twice → identical `Nodes`/`Edges`/kinds. Different `craftId` → different course with probability >0.99 over the sample.
4. **Tag→kind traceability.** Table-test: a pure-fire ingredient → `SpikeRun`; ice → `HoldStill`; air → `Glide`; earth → `HeavyLeap`; life → `MovingHazard`; shadow → `BlindDash`; `sharp` rider → `TightGap`; `temporal` → `SlowMoDodge`; `chaos`/`dangerous` → `ChaosGate`; unknown-only tags → `Plain`. (Confirms §2.1 obeyed.)
5. **Theme never flips.** Assert `_baseTable["fire"].Vol < 0` (tightens) AND `_baseTable["ice"].Vol > 0` (widens) AND `_baseTable["fire"].Rx > _baseTable["ice"].Rx` (fire faster). A regression guard against a §2 violation.
6. **Full-vocabulary coverage — NO tag no-ops (the real test, not a trivial pass).** For every tag in `VOCAB`, build `p = BuildCourseProfile({tag:1}, tier:1)` and assert BOTH:
   - (a) `p` is `Clamp`-valid (every field in range), AND
   - (b) **`p` is NOT the identity profile** — at least one of `|p.Vol| > 1e-6`, `|p.Time-1| > 1e-6`, `|p.Rx-1| > 1e-6`, `|p.Pot-1| > 1e-6` holds. Because `MinigameModifierCommon.Fold` skips any tag absent from the folded table (leaving identity), an unkeyed tag would FAIL (b) unless the §2.2 no-op guard injected its channel default. This test therefore actually catches the regression the review flagged (an unkeyed vocabulary tag silently resolving to a no-op). Additionally assert every `_channelDefault[c]` for `c∈{HEAT..AIR}` is itself non-identity, so the guard can never inject an identity tuple. (Master §1.6: an untested tag resolves to its theme default, never a no-op.)
7. **Perf bands.** Drive three scripted controllers (masher/competent/expert per §4.6's behaviour models) through a fixed mid-tier course (pts=40); assert masher `perf < 0.50` (Normal or Fine, never Superior) landing in `0.20–0.30`, competent in `0.55–0.68` (Superior), expert `≥ 0.90` landing in `0.90–0.98` (Legendary), each ±0.03 tolerance. The masher assertion is the seam-critical one (`< 0.50`); the exact sub-band (Normal vs Fine) is not asserted since 0.20–0.30 straddles the 0.25 boundary by design (§4.6).
8. **Decay floor.** A controller that falls every node infinitely still finishes with `perf ≥ (0.72*routeFrac_of_easy_nodes - DECAY_MAX) ≥ 0` — never negative, never NaN.
9. **dt robustness — swept-AABB pinned.** Feed `dt=0.5s` spikes (clamped to 0.05s at `OnTick` top). Assert the avatar never tunnels a thin hazard: collision is **swept-AABB** (`SweptOverlaps(prevPos, pos, avatarBox, hazardRect)` sweeps the box from previous to current position — this is the IMPLEMENTED method, not "either/or"; R7). Drive an avatar at max speed straight at a 14px spike bar across several 0.05s steps and assert exactly one clean CLEAR-or-FAIL is registered (no pass-through). Also assert no `Finish` fires before `Phase==Done`.
10. **ResolveChannel drift guard (§2.4).** For every keyed alchemy tag `t` in `VOCAB` that `MinigameTagEffects` resolves, assert `MinigameTagEffects.FamilyColor(ResolveChannel(t) ?? -1) == MinigameTagEffects.FamilyColor(MinigameTagEffects.Dominant(MinigameTagEffects.Brew(new[]{t}, 1, 1)))` — i.e. our inline channel map agrees with the shipped resolver on every tag (reaching ground truth through the PUBLIC `Brew`+`Dominant`+`FamilyColor` path, since `Resolve` is private). Any mistyped channel in the hand-copied `ResolveChannel` FAILS here, so nodes can never silently mis-type. Also asserts `VOCAB` itself hasn't drifted from `MinigameTagEffects` (a `Brew` of any listed tag resolves to some channel; a tag that resolves to nothing but is in Metal/Wood is caught by set membership).

**F1/F7 playtest script (manual, `res://playtest_logs/adornments_playtest.log`):**
- Wire `_dev = new MinigameDevLog("adornments")`; `_dev.Context = () => $"t={RunClock,5:0.0} | {Phase,-6} | main {MainlineReached}/{TotalMainline} | cleared {BestNodeReached} | dcy{DecayPenalty*100:0}%"` (shows both the scoring numerator `MainlineReached` and the raw disc count); `_dev.BuildNotesPanel(_surf)`; `_dev.BeginSession(header)` in `OnBegin` where `header` lists: output id, tier, points, node count, the resolved kind of each node, branch count.
- `_dev.Log(...)` on: flip-up start, each node ENTER (`"ENTER n{k} {Kind} win{HazardWindow:0.00} spd{HazardSpeed:0.00}"`), each CLEAR (`"CLEAR n{k} reward{Reward:0.00}"`), each FAIL (`"FAIL n{k} decay+{_decayPerFall:0.00}"`), branch taken, seal.
- Manual passes to confirm: (a) flip-up reads as "the pattern lifting"; (b) each node kind is *legible before* you hit it (telegraph); (c) fire nodes feel fast, ice nodes feel slow-and-precise (theme reads); (d) respawn is forgiving but decay is felt; (e) an all-fire vs all-ice recipe FEEL distinctly different at the same points. F7 a note at each and read the interleaved snapshot.

---

## §11. REUSE MAP

**Shared toolkit calls reused (exact):**
- `MinigameOverlay`: `Begin/Finish` seam; `OnBegin/OnTick/OnInput/BuildUi` overrides; `FullscreenScene=true`, `BackdropTint`, `ShowAmbient`; `SetQuality`, `FlashQuality`, `Shake`, `Popup`, `Burst`, `SetHeaderSub`, `HideTimer` (Sigil Run has no countdown), `Accent`, `Recipe`, `DifficultyPoints`, `DifficultyTier`.
- `MinigameModifierCommon`: `ModProfile(channels:6, states:0)`, `Fold(p, counts, _baseTable, _chExc)`, `Clamp(...)`, `StackFactor` (implicit, inside Fold).
- `MinigameTagEffects`: PUBLIC — `FamilyColor(channel)`, the `HEAT/AQUA/TERRA/GROVE/UMBRA/AIR`+`N` channel consts, `Dominant(double[])`, `Brew(tags,tier,qty)` (test-only, for the #10 drift guard), `RarityFromPerf` (F1 log label only). PRIVATE (we do NOT call — we re-mirror ONLY the tag→channel map as our own `ResolveChannel`): the first field of each `Tags` entry (the channel int), plus the `Metal`→TERRA / `Wood`→GROVE set memberships. We do NOT copy `QualityGrade` values, `ModTable`, or any HSV — this discipline needs only channel ints for typing/colour, and its own `_baseTable` (§2.2) for magnitudes. No alchemy chemistry (`Evolve`) is used on the play loop.
- `CraftFx`: `Glow`, `Ring`, `RingPulse`, `Streak`, `Wisp`, `Crack`, `Wake`, `Ellipse`, `Arc`, `RoundRect`, `Bar` (unused-but-available), `Burst`, `Popup`, `Band`, `QualityBands`, `Hash01` (deterministic jitter). Backdrop safety net (`GradientBackdrop`) is already wired by the base — we add nothing.
- `CraftColor`: `DeMuddy` (node colours), `Brighten` (avatar core), `Lighten` (cleared-node tint).
- `StateVisual`: `Vines` (MovingHazard vine + the life-node glyph). (No other state primitives — parkour leans on `CraftFx`.)
- `MinigameDevLog`: full F1/F7 harness (`Context`, `NoteSubmitted`, `BuildNotesPanel`, `BeginSession`, `Log`, `Note`, `HandleKey`, `ShowLog`, `NotesEditHasFocus`, `DrawLog`), claimed in `_Input` (Alchemy parity).
- `CraftStyle.Get("adornments")` / `UiTheme`: glyph/accent/backdrop/embers + `UiTheme.Box`, `UiTheme.Rarity` (gold cleared-node), `UiTheme.Text`.

**New sprites/assets:** NONE. Every element is a procedural `CraftFx`/`StateVisual` draw or a `DrawLine/DrawCircle/DrawColoredPolygon/DrawArc/DrawRect`. No PNGs, no shaders (the one backdrop shader has the base's `GradientBackdrop` fallback). Avatar, nodes, hazards, sigil, flip-up — all drawn.

**Migration / removal scope (replace in place — the deletion is total, itemized here so nothing is left dangling).** The current `EnchantingMinigame.cs` is the 712-line "Runic Overcharge" push-your-luck build. This is a **full-file replacement**: delete the ENTIRE existing body of the class and author the Sigil Run from the data model in §1. Concretely, every member of the old build is removed — none is reused:
- **Old fields (all deleted):** the palette `Cool/Warm/Hot/Amber/Green/Gold` (keep only what §6 re-derives from `CraftStyle`), `SurfW/SurfH/Center/RingR/GaugeRect` layout consts, and all push-your-luck state: `_hiddenThresholdMean, _thresholdVariance, _rewardBase, _windowHalf, _windowSpeed, _noiseBandBase, _surgeChancePerDepth, _par, _fogRecedeRate, _maxVents, _threshold, _pot, _strain, _bankedPot, _depth, _ventsLeft`, and any charge/surge/fog timers.
- **Old methods (all deleted):** `StartChannel, BeginCharge, ReleaseCharge, Vent, Bank, ApplySurge, CheckFracture, Milestones, UpdateQuality, PowerMult, BaseInstab, HumFreq, Gaussian, StrainColor, MoteWorldPos, DrawRuneCircle, DrawRuneGlyph, DrawStrainGauge, DrawGaugeTick, DrawHumRing, DrawState, DrawShards`, and the old `DrawSurface`. The old `Interp` is deleted too but re-authored identically (§1.8) — same signature/shape, so it reads as "kept" but is part of the fresh build.
- **Overridden members (deleted then re-authored fresh for Sigil Run):** `BuildUi`, `OnBegin`, `OnTick`, `OnInput` are rewritten wholesale; `Discipline => "adornments"` is the ONLY line that survives verbatim. Add the new overrides `FullscreenScene => true` and `BackdropTint` (§6.1) which the old build did not have.
- **Net:** after replacement the file contains only the Sigil Run (§1–§8 data model + draw). No dead helper from Overcharge remains; a coder should expect the diff to be "−712 / +N", not a patch. Because class name / file path / `Discipline` key are unchanged, `CraftStyle.All["adornments"]` and every caller/registration keep working with zero churn (verified: the current file already uses the `"adornments"` key).

**`Game1.Core` 0-diff confirmation:** All logic is in `Game-1-Godot/scripts/minigames/EnchantingMinigame.cs`. No Core type is referenced, subclassed, or modified. No new shader is added (the sole backdrop shader already has the base's `GradientBackdrop` fallback; all Sigil Run drawing is `CanvasItem` primitives + `CraftFx`/`StateVisual`). The only cross-boundary contract is the certified seam (`perf∈[0,1]` via the `_running`-guarded `Finish`), which routes material consumption / quality / output / XP / titles through the existing certified `CraftingSystem` — untouched. Class name, file path, and `Discipline => "adornments"` are preserved so no caller/registration changes.

---

*Consistency check performed before writing: every tag in §2 was looked up in master §2.1, its verb confirmed, and expressed only through the Enchanting column of §2.2. Fire always tightens+speeds; ice always widens+slows; air glides; earth grounds; shadow blinds (big payoff); life moves/grows; sharp→tight-gap; temporal→slow-mo; chaos/dangerous→telegraphed random. No tag flips theme.*

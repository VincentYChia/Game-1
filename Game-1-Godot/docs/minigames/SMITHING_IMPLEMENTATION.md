<!-- IMPLEMENTATION DOC — 2026-08-19 (rev 2). Authored against CRAFTING_MINIGAMES_MASTER_PLAN.md §3.1 + §2 Tag Theme
     Dictionary. This REPLACES the mechanic in scripts/minigames/SmithingMinigame.cs ("Draw & Temper") with the
     canonical "Forge Rush" top-down SC2 micro-battle. Coding this doc should require inventing NOTHING.

     FULL REWRITE, NOT AN EDIT. The current 619-line "Draw & Temper" implementation (heat gauge, sections, needle bar,
     Strike/Stoke/DriftHotZone, DrawForge/…) is DISCARDED IN FULL. The ONLY thing kept from the current file is the
     class shell — `public partial class SmithingMinigame : MinigameOverlay` with `Discipline => "smithing"`. Every
     field, method, const, and draw routine below is new. A coder diffing against the current file should keep nothing
     but that one class declaration; do not attempt to reconcile the two mechanics.

     API-ACCESSIBILITY GROUND TRUTH (verified against MinigameTagEffects.cs, MinigameModifierCommon.cs, MinigameOverlay.cs,
     CraftFx.cs, CraftColor.cs, StateVisual.cs). This doc is authored to build against the REAL public surface with
     ZERO shared-toolkit edits (§11.3 is truthful):
       • PUBLIC and reused as-is: MinigameModifierCommon.{ModProfile, StackFactor, Fold, Clamp} (fully generic);
         MinigameTagEffects.{StackFactor, FamilyColor(int), ChannelName(int)}; the whole MinigameOverlay seam;
         all of CraftFx.{Band, QualityBands, QualityColor, Popup, Burst, Ambient, RoundRect, Glow, Bar, Stars,
         DrawStar, Arc, Ring, RingPulse, Streak, Wisp, Crack, Wake, Ellipse, Hash01, Backdrop, GradientBackdrop};
         all of CraftColor.{Darken, Lighten, Brighten, DeMuddy, RadialGrad}; StateVisual.{RippleOut, Flame, Vines, …}.
       • PRIVATE in MinigameTagEffects and therefore NOT reused: `Resolve`, `Tags`, `Metal`, `Wood`, `FamCol`, `ModTable`,
         `ChExc`, `StExc`, `StrongExc`, `PvExc`, `QualityGrade`. The doc DUPLICATES the small tables it needs
         (metal/wood sets, tag→theme map, the 6 FamCol HSV constants, the modifier base/exception tables) verbatim
         inside `SmithingMinigame` — see §2.3 / §6.0. This is authorial duplication of ~120 tokens of data, NOT a change
         to MinigameTagEffects. It keeps `Game1.Core` AND the shared toolkit 0-diff.
     -->

# Smithing — "Forge Rush" — Implementation Doc

**Canonical mechanic (master plan §3.1):** top-down StarCraft-2-style micro-battle. You command a **hero** forged
from the recipe and survive an enemy **wave**. Recipe *knowledge* = your loadout (ingredient tags → abilities/allies,
tier → ability rank). The minigame is pure **micro** (positioning, ability timing, ally control). Output tags set the
enemy **wave character**. `perf ∈ [0,1]` is produced through the certified seam; `Game1.Core` is 0-diff.

**Sacred seam (unchanged):** `MinigameOverlay.Begin(points, tier, RecipeContext?, onComplete(perf 0..1), onAbandon)` →
play inside `OnTick`/`OnInput` → `Finish(perf)` **or** `FailCraft()` **exactly once**. This minigame uses
`FullscreenScene => true`. It calls `Finish(perf)` on every terminal (including a total wipe → low perf); it does **not**
call `FailCraft()`. **Seam-behavior note (confirm with the caller, do not assume):** `FailCraft()` routes to `onAbandon`
(verified: `MinigameOverlay.FailCraft` → `_onAbandon?.Invoke()`), which is the SAME path as a player abandon (double-Esc)
and, per Alchemy's boil-over usage, is the caller's "materials lost, no item" branch. Smithing's design intent (§3.1
"easy entry, not a hard fail") is that a wipe still yields a poor graded item, so it always `Finish`es. **This is a
deliberate divergence from the Alchemy contract** (Alchemy calls `FailCraft` on boil-over). Because the caller's
`onAbandon` may refund/free materials differently than a low-`perf` `Finish`, the coder MUST confirm with the craft-path
owner that "always Finish, never FailCraft" is acceptable for smithing before shipping. If the owner requires a lost-craft
branch, gate it behind `perf < FAILCRAFT_FLOOR` (a named const, default `0.0` = disabled) so the choice is one flag, not
a rewrite. Default and this doc's baseline: **never FailCraft** (see §3, §4.6).

**Class:** `SmithingMinigame : MinigameOverlay` (Godot-side; `partial`). `Discipline => "smithing"` (Forge theme —
CraftStyle["smithing"], accent `#FA8C52`, embers `#FF9938`). Everything below is Godot-side glue.

**Scope cap (master plan §3.1 roadblock 4, non-negotiable):** hero + **≤3 tag-granted abilities (Q/W/E)** + a passive
**R** (see §2) + **≤2 ally archetypes** + **1–2 enemy archetypes**. Procedural-pixel sprites drawn with `CraftFx`
primitives render + play *before any raster PNG exists*; authored PNGs are a strictly-later layer (§6.9, §9-R3).

---

## 0. Vocabulary & conventions used throughout

- **Play surface**: one `Control` named `_arena` filling the `FullscreenScene` VBox; all world draw happens in its
  `_arena.Draw`. World coordinates are **arena-local pixels** (origin top-left of `_arena`).
- **Arena rect**: computed each frame from `_arena.Size` (resolution-relative, §6.1). All layout numbers are given as
  fractions of arena width `AW` / height `AH` unless a pixel constant is named.
- **Units** tick in **seconds** (real time, `delta` from `OnTick`). Distances in **arena pixels**. Angles in **radians**.
- **Non-physics tick**: no Godot physics bodies. Units are plain structs with position/velocity; steering is
  hand-integrated in `TickUnits` (§4.4). Collision = circle-vs-circle distance tests only.
- **Determinism**: one `System.Random _rng` seeded from `craftId + tags` (§8). Every spawn position/timing/wander draws
  from `_rng`. No `GD.Randf()` / `Math.Random` in gameplay logic (only `CraftFx.Burst` internal particle jitter, which
  is cosmetic and off the scored path).
- **`Interp(easy, hard)`** — the single difficulty lerp, reused verbatim from the current file:
  `easy + (hard-easy) * Clamp((DifficultyPoints-1)/79, 0, 1)`. Difficulty scales **intensity only** (§7); tags scale
  **character** (§2).

---

## 1. DATA MODEL

All types are nested in `SmithingMinigame` unless marked `enum`/`static`. Field annotations: `[type] name — unit/range`.

### 1.1 Enums

```
enum Phase { Ready, Countdown, Play, Settle, Done }          // §3 state machine
enum Theme { Fire, Water, Ice, Earth, Life, Shadow, Air }    // the 7 §2.1 elemental themes (index 0..6)
enum AbilitySlot { Q = 0, W = 1, E = 2, R = 3 }              // 3 active + 1 passive (R). ≤3 active per §scope
enum AbilityKind {                                           // resolved from a theme (§2 col "Smithing")
    None,
    Nuke,        // FIRE  — AoE burst at cursor (offensive/volatile)
    SlowField,   // ICE   — radial slow/root zone (control/deliberation)
    Bulwark,     // EARTH — hero shield + taunt pull (solidity/resistance)
    Rally,       // LIFE  — spawn/heal an ally (growth/spread)
    Leech,       // SHADOW— lifesteal nova, self-risk (entropy/hidden power)
    Blink,       // AIR   — dash + brief haste (speed/evasion)
    Torrent,     // WATER — heal-over-time flow + cleanse hero debuffs
    // passive-only R kinds:
    PassiveCrit, // sharp rider → +crit on hero autos
    PassiveRegen // life/water rider → hero HP regen
}
enum AllyKind { None, Sprout, Guardian }                     // ≤2 archetypes. Sprout=LIFE dps, Guardian=EARTH tank
enum EnemyKind { Rusher, Bruiser }                           // ≤2 archetypes (wave character from output tags, §2 Function)
enum UnitTeam { Hero, Ally, Enemy }
```

### 1.2 Unit (the lightweight non-physics actor)

```
sealed class Unit {
    UnitTeam Team;            // Hero / Ally / Enemy
    EnemyKind EKind;          // valid when Team==Enemy
    AllyKind  AKind;          // valid when Team==Ally
    Vector2 Pos;              // arena px, current position
    Vector2 Vel;              // arena px/s, current velocity (steering output)
    float   Facing;           // radians, drawn heading (weapon line / spike / shield arc). Derived each tick (§1.2a).
    float   Radius;           // arena px, body + collision radius (§4.1 sizes)
    float   Hp;               // current hit points (>=0)
    float   HpMax;            // max hit points (>0)
    float   MoveSpeed;        // arena px/s desired cruising speed
    float   Damage;           // dmg per hit dealt on contact/attack
    float   AttackCd;         // s between attacks
    float   AttackTimer;      // s until next attack allowed (counts down)
    float   Shield;           // absorb pool (Bulwark grants); 0 normally. Depleted BEFORE Hp (§1.2b).
    float   SlowUntil;        // arena clock time this unit's slow expires (0 = none)
    float   SlowFactor;       // 0.35..1.0 speed multiplier while slowed
    float   Phased;           // arena clock time untargetable-phase expires (Shadow rider, 0 = none)
    float   HitFlash;         // 0..1 white-flash on damage taken (decays, cosmetic)
    float   SpawnT;           // arena clock time spawned (for spawn-in animation)
    bool    Alive => Hp > 0;
    int     Seed;             // per-unit deterministic seed (wander phase), from _rng
}
```

#### 1.2a Facing derivation (single rule, drawn-only — no gameplay effect)

`Facing` is recomputed once per unit at the end of `TickUnits` step 5 (integrate), purely for the draw layer (§6.3/§6.4).
It never feeds steering or combat. One rule for all units:

```
if Vel.Length() > 4:                Facing = Vel.Angle()                    // moving → face travel
elif Team==Hero and hero has a live target within RANGE:
                                    Facing = (target.Pos - Pos).Angle()     // idle hero → face auto-target (or _cursor if none)
elif this unit has an attack target: Facing = (attackTarget.Pos - Pos).Angle()  // idle enemy/ally → face who it fights
else:                               Facing unchanged (holds last heading)
```

So the Rusher's spike `Streak` (§6.4) points `Facing`; the Guardian's shield arc (§6.4) is centered on `Facing`; the
hero's weapon line (§6.3) points `Facing`. No unit stores a separate orientation — `Facing` is the one field.

#### 1.2b Damage application (Shield-then-HP, single helper `Hurt(unit, dmg)`)

Every damage source (contact attack, hero/ally auto, Nuke/Leech AoE, Nuke residual, Thorns-free — there is no Thorns)
goes through ONE helper so the order is never re-invented:

```
void Hurt(Unit u, float dmg):
    if dmg <= 0 or !u.Alive or (u.Team==Enemy and now < u.Phased): return   // phased enemies take no damage
    u.HitFlash = 1
    float toShield = Min(u.Shield, dmg)
    u.Shield -= toShield                     // Shield absorbs first, 1:1, no overflow bonus
    float toHp = dmg - toShield
    u.Hp = Max(0, u.Hp - toHp)               // remainder hits Hp; Hp floored at 0 (never negative)
    return toHp                              // HP actually removed — the leech-eligible amount (§4.4a)
```

Only the hero and Bulwark-taunt targets ever carry `Shield` (>0); for everyone else `Shield==0` so `Hurt` is a plain
HP subtract. `Hp` is never negative; `Alive => Hp > 0`. Enemy death is detected in step 8 (cull) when `Hp<=0`.

### 1.3 Ability (one per Q/W/E/R slot)

```
sealed class Ability {
    AbilitySlot Slot;        // Q/W/E/R
    AbilityKind Kind;        // None if the loadout had no material for this slot
    int    Rank;             // 1..4 = source material tier (drives magnitude, §2 Quality/Grade + §4.5)
    Theme  Source;           // the theme that granted it (colour + VFX + wave-affinity)
    float  Cooldown;         // s, full cooldown (rank/point scaled, §4.5)
    float  CdTimer;          // s remaining (0 = ready)
    float  Radius;           // arena px, AoE reach (0 for Blink)
    float  Magnitude;        // generic power number: dmg (Nuke/Leech), slow (SlowField),
                             //   shield (Bulwark), heal (Torrent/Rally), dash dist (Blink)
    float  Duration;         // s, effect lifetime for lingering effects (SlowField/Torrent/haste)
    bool   Targeted;         // true => cast at cursor (Nuke/SlowField/Blink); false => self/hero-centered
    string Label;            // short name for the ability bar ("Nuke","Frost","Bulwark",...)
    bool   Ready => CdTimer <= 0 && Kind != AbilityKind.None;
}
```

### 1.4 Active effect (lingering zones + hero buffs on the field)

```
struct FieldEffect {                // pooled list; ≤~8 live at once
    AbilityKind Kind;               // SlowField / Torrent / Nuke-afterglow
    Vector2 Pos; float Radius;
    float Magnitude;                // slow factor OR heal/s OR (Nuke) residual dmg/s
    float Until;                    // arena clock expiry
    Theme Source;                   // colour
}
struct HeroBuff {                   // hero-only timed buffs
    float HasteUntil;  float HasteMul;   // Blink haste (1.0=none). now<HasteUntil ⇒ hero MoveSpeed ×HasteMul.
    float RegenUntil;  float RegenPerS;  // Torrent / PassiveRegen. now<RegenUntil ⇒ +RegenPerS·dt to hero Hp each tick.
    float CritChance;                    // PassiveCrit (0..0.6), PERMANENT for the run (set once at build; not timed).
    float LeechFrac;                     // Leech leech fraction while active (0..1). Set by Leech cast; timed by LeechUntil.
    float LeechUntil;                    // arena clock expiry of the Leech window (0 = inactive).
}
```

**LeechFrac semantics (WHEN it converts, WHAT it converts):** `LeechFrac` is the fraction of **HP damage the hero's own
attacks actually remove from enemies** that is returned to the hero as healing, but ONLY while the Leech window is open
(`now < LeechUntil`). It is applied per damage event, at the moment a hero-sourced hit lands, using the HP-removed
return value of `Hurt` (§1.2b) — NOT shield-absorbed damage. Concretely (§4.4a): on any hero auto-attack or hero Nuke/
Leech AoE hit, `float hpRemoved = Hurt(enemy, dmg); if (now < _heroBuff.LeechUntil) HealHero(hpRemoved * _heroBuff.LeechFrac)`.
Ally hits do NOT leech. `HealHero(x)` adds `x` to hero `Hp` capped at `HpMax`. The Leech *nova* cast itself also heals
the hero for `Magnitude * LeechFrac` of its own AoE HP damage via the same path. Two feral riders (`blood`, feral GROVE
tags §2.1) add a small **passive** leech: they set a baseline `LeechFrac` that is always active by extending `LeechUntil`
to `+∞` (represented as `LeechUntil = float.MaxValue`) at build time — see §4.5. `CritChance` is a flat probability rolled
per hero attack (`_rng.NextDouble() < CritChance` ⇒ ×2 damage), fixed for the whole run.

### 1.5 Loadout (built once from RecipeContext at OnBegin)

```
sealed class Loadout {
    Ability[] Abilities = new Ability[4];        // indexed by AbilitySlot; slot with no material => Kind=None
    List<(AllyKind Kind, int Rank)> StartAllies; // ≤2 entries (LIFE/EARTH ingredients spawn these at t=0)
    Theme HeroTheme;                             // dominant loadout theme → hero tint + auto-attack element
    float HeroHpBonus;                           // +HP from EARTH/quality stacking (§4.5)
    float HeroDamageMul;                         // × on hero autos from sharp/strength/quality (§4.5)
}
```

### 1.6 Wave (built once from output tags + points at OnBegin)

```
sealed class Wave {
    Theme  Character;         // output dominant theme → enemy tint + which enemy ability rider
    float  Duration;          // s survival target (§4.2)
    int    TotalToSpawn;      // enemy count across the wave (§4.2)
    float  SpawnInterval;     // s between spawns (§4.2)
    float  EnemyHpMul;        // × on base enemy HP (points + character, §4.2/§7)
    float  EnemyDmgMul;       // × on base enemy dmg
    float  RusherFrac;        // 0..1 fraction that are Rushers vs Bruisers (from output Function tags, §2)
    bool   SecondWave;        // unlocks above "rare" tier (§7)
    bool   MiniBoss;          // "legendary" tier (§7)
    int    Spawned;           // runtime counter
    float  NextSpawnAt;       // arena clock time of next spawn
}
```

### 1.7 Root play state (fields on `SmithingMinigame`)

```
Phase   _phase;                 // current state
double  _clock;                 // arena play clock (s, advances only in Play/Settle)
double  _countdown;             // s left in Countdown (3..0)
double  _anim;                  // free-running seconds (visuals; advances every tick)
Loadout _loadout;               // §1.5
Wave    _wave;                  // §1.6
Unit    _hero;                  // the player unit
List<Unit>        _allies;      // ≤ (start allies + Rally spawns), capped MAX_ALLIES=6
List<Unit>        _enemies;     // live enemies
List<FieldEffect> _fields;      // lingering zones
HeroBuff          _heroBuff;    // hero buffs
Vector2 _cursor;                // arena-local mouse pos (ability aim)
Vector2 _moveTarget;            // hero right-click move destination (arena px)
bool    _hasMoveTarget;
int     _selectedAlly;          // -1 = none; index into _allies for ally micro (F-key / click-select)
Rect2   _arenaRect;             // current frame's arena rect (px), set at top of draw/tick
// scoring accumulators (§4.6):
float   _heroDmgDealt;          // total dmg hero+allies dealt (for wave-clear + efficiency proxy)
int     _enemiesKilled;         //
int     _enemiesTotal;          // = wave TotalToSpawn (+2nd wave/boss)
int     _abilitiesCast;         //
int     _abilitiesLandedValue;  // sum of "useful" casts (hit >=1 enemy / healed when hurt), for efficiency
bool    _heroDied;              // no-death bonus gate
double  _lowestHpFrac;          // min hero HP fraction seen (tension read; not scored directly)
MinigameDevLog _dev;            // F1/F7 harness (§5.3)
```

### 1.8 RecipeContext fields READ (and only these)

| Field | Use |
|-------|-----|
| `Recipe.Inputs[].Tags` (ordered) | Per-ingredient dominant theme via precedence 4/3/2/1 → ability slot + ally (§2). |
| `Recipe.Inputs[].MaterialTier` | Ability **Rank** (1..4) and ally rank (§2 Quality/Grade, §4.5). |
| `Recipe.Inputs[].Qty` | Stacking weight into the tag-pool count dict (§2 tag pool). |
| `Recipe.OutputTags` | Enemy **wave character** (dominant theme) + Function tags → Rusher/Bruiser split (§2). |
| `Recipe.Tier` (string) | **Only a FALLBACK** for `tierIndex` when `Recipe` is null (debug). It does **not** compete with `DifficultyTier` for the gate — see the tie-break below. |
| `Recipe.OutputId` | Seed material for `_rng` (§8) + header sub text. |
| `DifficultyPoints` (base field) | Intensity dial (§7). |
| `DifficultyTier` (base field) | Star count (seam) **AND the single source of `tierIndex`** for the 2nd-wave / mini-boss gate (§4.2). |

**`tierIndex` source — one winner, no overlap (resolves the ambiguity the reviewer flagged):** `tierIndex` is derived
from **`DifficultyTier`** (the base field) whenever a run has one — which is always, since the seam sets it. `Recipe.Tier`
is consulted **only** in the null-`Recipe` debug path (where the debug sampler sets it). Both are never read for the same
decision. Definition and mapping are in §4.2.

**Null `Recipe` (debug launch):** sample a plausible loadout — 2 synthetic ingredients `["fire","sharp"]` (t2) and
`["earth","durable"]` (t2), output tags `["weapon","combat"]`, so the arena is always playable (master plan §1.2).

---

## 2. TAG TABLE

**The tag table is authored ENTIRELY from §2 of the master plan.** The full material vocabulary (elemental bodies,
metals, woods, the grade/energy/physical/exotic/function riders) resolves here. Two mechanisms, matching the alchemy
split — but **implemented against the doc's OWN tables (§2.3, §2.2), not by reading any private `MinigameTagEffects`
member.** The channel semantics are IDENTICAL to alchemy's (fire is HEAT/haste everywhere), transcribed by hand so the
result is byte-for-byte the same behavior without touching the private code:

1. **Primary (theme) resolution** — the tag's *body theme* → the **Smithing knob** in the manifestation matrix
   (§2.2 "Smithing (SC2 micro)" column). Done via `SmithTheme(tag)` (§2.3), a direct `tag → Theme?` lookup in the doc's
   own `ThemeTag` dictionary. The channel→Theme correspondence it encodes (same as alchemy's channels):

   | Body (alchemy channel it mirrors) | `Theme` | Smithing manifestation (§2.2 row) |
   |---|---|---|
   | `HEAT` (fire/flame/ember/molten/forge/volcanic) — six bodies only; lightning/storm/radiant/light/chaos are HEAT *riders*, not bodies (Alchemy §C.2-a) | **Fire** | Q=**Nuke** (offensive AoE) + aggressive fast enemy adds when on OUTPUT |
   | `AQUA` — *split by cold-set* (see below) | **Water** or **Ice** | Water→**Torrent** (heal-flow/cleanse); Ice→**SlowField** (control) |
   | `TERRA` (earth/stone/all metals/crystal/gem/sand/mineral) | **Earth** | Q/W=**Bulwark** (shield+taunt) or **Guardian** ally; tanky wave when on OUTPUT |
   | `GROVE` (all woods/plant/herb/leather/living/monster/fang/scales/bone/gel/carapace/blood) | **Life** | **Rally** (spawn/heal ally = **Sprout**); regen |
   | `UMBRA` (void/dark/shadow/spectral/poison/venom/toxic/acid/arcane/magical/essence) | **Shadow** | **Leech** (lifesteal nova, self-risk / glass cannon) |
   | `AIR` (air/wind/vapor/gas) | **Air** | **Blink** (dash + brief haste, evasive) |

   Note `sharp`/`durable`/`strong` are **NOT** in `ThemeTag` (they are pure riders, §2.3 `IsPureRider`), so — unlike
   alchemy where `sharp` resolves to TERRA — in Smithing they claim no theme slot; their TERRA flavour is delivered
   entirely through `SmithChExc[...](Earth,…)` riders (§2.2) + `PassiveCrit`.

   *`sharp` is a **precision rider** ("+crit/precision on the ability"), captured by the modifier pass as `PassiveCrit`
   (slot R) + a `HeroDamageMul` rider + `SmithChExc["sharp"]=(Earth,…)` emphasis. It occupies **no** theme slot in
   Smithing (it is deliberately absent from `ThemeTag`), so it can never win a `DominantTheme` argmax — the reviewer's
   "sharp → Earth" hazard cannot occur here, because `SmithTheme("sharp") == null`.*

   **AQUA cold-split** (obey §2.1 "COLD/ICE is the still pole of water"): the split is **pre-resolved directly in
   `ThemeTag`** (§2.3) — `{ice, frost, frozen, chill}` map to **Ice**, `{water, aqua, liquid, solvent}` to **Water** — so
   no runtime channel test is needed. This preserves §2.1: ice = control/deliberation/stability (SlowField); water =
   flow/cleanse/dilute (Torrent). Fire's meaning never flips.

2. **Modifier riders** — the §2 cross-cutting families (Quality/Grade, Physical/Structural, Energy/Essence,
   Exotic, Function). These do **not** pick a theme; they scale magnitude/quality of whatever theme is present. They fold
   through **`MinigameModifierCommon`** exactly like alchemy: `SmithingMinigame` declares its OWN base table
   `SmithModTable` (Pot/Vol/Time/Rx re-purposed as Power/Risk/Cooldown/Cast-vigor knobs — see mapping below) plus small
   channel/primary exception tables, and calls `MinigameModifierCommon.Fold(profile, counts, SmithModTable, chExc, …)`
   then `Clamp`. The stacking (`StackFactor`: 2nd copy +40%, 4th ~nothing) and diminishing returns are inherited.

**`SmithModProfile` field re-mapping** (subclass of `MinigameModifierCommon.ModProfile(channels=7, states=0)`; we use
`Ch[0..6]` = per-theme power multiplier, and re-read the base scalars):

| `ModProfile` field | Smithing meaning | Consumed by |
|---|---|---|
| `Pot` (×) | **Power** — × on hero autos + ability Magnitude (Quality/Grade, strength, sharp raise it) | `Loadout.HeroDamageMul`, `Ability.Magnitude` |
| `Vol` (±) | **Risk** — enemy dmg × rider on the WAVE (dangerous/chaos/explosive raise; harmony lowers). Applied when tag is on OUTPUT. | `Wave.EnemyDmgMul` |
| `Time` (×) | **Cooldown** — × on ability cooldowns. **Definite sign, no hedge: `Time > 1` = LONGER/heavier cooldown; `Time < 1` = snappier.** Per §2.1: ice/`temporal` are control/deliberation → `Time > 1` (slower, more deliberate casts, longer between them); air/`speed`/`sharp` are haste/precision → `Time < 1` (snappier). `spectral` (ethereal/slow-to-manifest) → `Time > 1`. This is the ONLY reading; the earlier draft's "raise available-time by lowering cd" musing is retracted. | `Ability.Cooldown` |
| `Rx` (×) | **Cast-vigor** — × on hero HP + regen strength (durable/vit-flavored raise; volatile lower) | `Loadout.HeroHpBonus`, regen |
| `Ch[theme]` (×) | per-theme **emphasis** (e.g. `radiant` boosts HEAT power, `essence` boosts several) | per-ability Magnitude for that Source theme |
| `AmpStrongest` (×) | Exotic **quantum/impossible/power** → amplify the STRONGEST ability (§2 Exotic row) | applied to the highest-Magnitude ability |

**Precedence & pooling (obey master plan §1.3 exactly; the rank weights are reimplemented inline, not a private call):**
- Within one ingredient's ordered `Tags`, the **1st** tag weighs **4**, 2nd **3**, 3rd **2**, 4th+ **1** — the SAME
  `rank switch {0=>4,1=>3,2=>2,_=>1}` that `MinigameTagEffects.Brew` uses, transcribed into `DominantTheme` (§2.2). We do
  NOT call the private `Brew`; we reproduce its two-line weight rule. The **highest-weighted** theme of an ingredient
  decides which **ability slot** that ingredient grants (Q first free slot, then W, then E — see slot assignment §4.5).
- Across all ingredients, every tag accumulates into a **count dict** `Dictionary<string,int>` (summing `Qty`), which is
  what `MinigameModifierCommon.Fold` stacks over. Output tags fold into a SEPARATE count dict → wave riders.

### 2.1 The complete tag → Smithing-knob table

Read: **Theme** = which §2.2 Smithing manifestation the tag's body invokes (only the *dominant* tag of an ingredient
uses this to claim a slot). **Rider** = the modifier effect it always contributes through the fold. Grouped by §2 family.

#### Seven elemental bodies (theme claim)

| Tags | Theme | Smithing knob (ingredient → hero) | On OUTPUT (→ wave) |
|---|---|---|---|
| fire, flame, ember, molten, forge, volcanic | **Fire** | Q **Nuke** (AoE burst, high dmg) | fast aggressive **Rusher**-heavy wave, +tempo |
| lightning, storm, radiant, light, chaos (energetic HEAT riders) | **none** (pure riders — claim no slot; Alchemy §C.2-a) | do NOT mint a Nuke on their own; they fold as riders + a small HEAT `SmithChExc` emphasis (§2.2), and if the ingredient's *body* is Fire they colour it (lightning=burst; chaos=random rank ±1) | wave gets erratic spawn jitter (on OUTPUT, via riders) |
| water, aqua, liquid, solvent | **Water** | Torrent (heal-over-time + cleanse hero slow/debuff) | wave slightly forgiving (slower spawn) |
| ice, frost, frozen, chill | **Ice** | W **SlowField** (radial slow/root zone) | fewer but tankier **Bruiser** adds, slower wave |
| earth, stone, sand, mineral | **Earth** | Bulwark (hero shield + taunt) | tanky slow bruisers |
| metal, iron, steel, bronze, copper, tin, mithril, adamantine, silver, gold, orichalcum, alloy, metallic, crystal, gem | **Earth** (metal riders add hardness) | Bulwark / **Guardian** ally; +HeroHp | armored bruisers |
| wood, oak, ash, ironwood, ebony, birch, willow, worldtree, plant, herb, leather, living | **Life** | Rally (**Sprout** ally + hero regen) | organic wave (regen adds) — represented by +HpMul |
| monster, fang, scales, bone, gel, carapace, blood (feral) | **Life** (+ferocity rider) | Rally + hero LeechFrac rider (feral bite) | ferocious wave (+dmg) |
| void, dark, shadow, spectral | **Shadow** | E **Leech** (lifesteal nova, self 8% HP cost) | high-risk wave (evasive/erratic) |
| poison, venom, toxic, acid | **Shadow** (toxic rider) | Leech; the toxic rider is **hidden power for the wielder** (UMBRA), not self-degrade: hero autos apply a short **enemy** DoT — `HeroBuff`-driven, the hero's hits poison the *enemy* (never the hero). Wiring: while any toxic ingredient tag is present, a hero-sourced hit adds `POISON_DOT=6 dmg/s for 2s` to the struck enemy (a `FieldEffect`-style per-enemy tick via `Hurt`). **This is the CANONICAL toxic reading — `degrade-over-time` (§2.1 SHADOW), a lingering DoT, NOT a one-shot swing spike. Refining/Engineering must cite this row, not a swing-only read: toxic is a tick, not a burst.** | wave adds degrade-over-time flavour (**enemy → hero** +dmg rider on OUTPUT) |
| arcane, magical, essence | **Shadow** (mystic amplifier) | Leech; strong `Ch` power amp | raw amplification of wave dmg |
| air, wind, vapor, gas | **Air** | Blink (dash + 1.5s haste) | fast light wave (quick, evasive Rushers) |

#### Quality / Grade family — MAGNITUDE (increasing returns; higher grade = more power, more upside)

`SmithModTable` base (Pot=Power×, Vol=Risk±, Time=Cd×, Rx=HP/vigor×). **Rule (strictly monotone, no exceptions inside
this family): higher grade ⇒ higher Power (Pot↑), lower Risk (Vol↓), snappier Cd (Time↓, i.e. `Time` decreases as grade
climbs), more HP (Rx↑).** The whole point-grade ladder from `starter` up to `mythical` obeys all four monotonically —
verify against the numbers below (every column moves one direction as you read down the ladder). Off-ladder grade words
(`superior`/`pure`/`holy`/`material`/`mundane`) are slotted at their equivalent ladder rung and also obey `Time ≤ 1` for
any above-standard grade. **`ancient` is NOT a pure grade word here** — it is an Exotic "old/heavy but potent" rider and
lives in the Exotic table (§Exotic below) with `Time > 1`; it is intentionally excluded from this monotone grade family
so the "higher grade = snappier Cd" rule has no counterexample:

| Tag | Pot(Power) | Vol(Risk) | Time(Cd) | Rx(HP) | Note |
|---|---|---|---|---|---|
| starter | 0.90 | +3 | 1.05 | 0.94 | weak, riskier (lowest rung) |
| basic | 0.93 | +2 | 1.03 | 0.96 | |
| common | 0.96 | +1 | 1.00 | 0.98 | |
| standard | 1.00 | 0 | 1.00 | 1.00 | identity anchor |
| uncommon | 1.05 | −1 | 0.99 | 1.03 | |
| fine | 1.08 | −2 | 0.98 | 1.05 | |
| quality | 1.11 | −3 | 0.97 | 1.06 | |
| refined | 1.13 | −4 | 0.96 | 1.08 | |
| rare | 1.16 | −5 | 0.95 | 1.10 | |
| advanced | 1.19 | −6 | 0.94 | 1.12 | |
| precious | 1.22 | −8 | 0.93 | 1.14 | |
| epic | 1.24 | −8 | 0.93 | 1.15 | |
| legendary | 1.28 | −10 | 0.92 | 1.18 | |
| mythical | 1.32 | −12 | 0.90 | 1.20 | top of the monotone ladder — snappiest Cd |
| superior | 1.14 | −4 | 0.96 | 1.10 | ≈refined rung |
| pure | 1.10 | −10 | 0.97 | 1.10 | low-risk; a high grade → Cd < 1 (fixed from the earlier 1.00) |
| holy | 1.15 | −4 | 0.96 | 1.12 | ≈rare rung |
| mundane | 0.88 | 0 | 1.02 | 0.94 | below-standard → Cd ≥ 1 (consistent: low grade, not snappy) |
| material | 1.00 | −1 | 1.00 | 1.00 | standard-equivalent |

#### Physical / Structural family — STABILITY vs OFFENSE riders (§2 row exactly)

| Tag | Pot | Vol | Time | Rx | Rationale (§2) |
|---|---|---|---|---|---|
| durable | 1.00 | −3 | 1.10 | 1.14 | reinforce STABILITY/defense + slow → +HP, longer cd |
| hard | 1.00 | −5 | 1.08 | 1.10 | " |
| solid | 1.00 | −8 | 1.10 | 1.15 | strong reinforce |
| dense | 1.00 | −6 | 1.12 | 1.14 | " |
| heavy | 1.00 | −4 | 1.14 | 1.12 | heavy = slow, tanky |
| strong | 1.12 | −2 | 0.98 | 1.08 | strength → +Power (chExc→TERRA emphasis) |
| sharp | 1.10 | +3 | 0.90 | 1.00 | **precision/offense rider** → +Power, snappy cd, and grants **PassiveCrit** (R) + `PvExc` crit (below) |
| layered | 1.00 | −2 | 1.08 | 1.05 | complexity/adaptability → +1 ability variety weight (see §4.5) |
| flexible | 1.00 | −4 | 1.02 | 1.06 | adaptability |
| versatile | 1.05 | −1 | 1.00 | 1.05 | |
| memory | 1.05 | −4 | 1.05 | 1.05 | |

#### Energy / Essence family — AMPLIFIERS / WILDCARDS

| Tag | Pot | Vol | Time | Rx | chExc / special |
|---|---|---|---|---|---|
| magical | 1.15 | −2 | 1.02 | 1.02 | chExc UMBRA ×1.25 |
| arcane | 1.20 | −4 | 1.05 | 0.98 | chExc UMBRA ×1.30 |
| essence | 1.20 | +1 | 1.02 | 1.05 | chExc HEAT/GROVE/UMBRA ×1.3 (broad amp) |
| radiant | 1.18 | +2 | 1.00 | 1.08 | pure HEAT rider (no `ThemeTag` body): chExc HEAT ×1.4 (fire emphasis only) |
| light | 1.10 | −3 | 1.00 | 1.05 | pure rider (no body): chExc HEAT ×1.15 (small fire emphasis) + UMBRA ×0.65 (dampens shadow) |
| spectral | 0.95 | +4 | 1.10 | 0.90 | evasive/ethereal → +Risk, slower |
| blood | 1.12 | +5 | 0.92 | 1.06 | vitality-for-risk → hero LeechFrac +0.12 (PvExc GROVE) |
| lightning | 1.05 | +9 | 0.80 | 1.00 | pure HEAT rider (no body): burst/erratic → snappy cd, +Risk, chExc HEAT ×1.5 |
| chaos | 1.00 | +14 | 0.80 | 0.95 | pure rider (no body): randomness → ability rank ±1 jitter (bounded, §8) + small chExc HEAT ×1.1 |
| temporal | 1.10 | −6 | 1.30 | 1.00 | time control → longer cd but a "freeze" flavour; SlowField Duration +50% |
| storm | 1.05 | +8 | 0.82 | 0.98 | pure HEAT rider (no body): chExc HEAT ×1.3 (fire emphasis) |

#### Exotic / Rule-benders family (§2 Exotic row) — via `strongExc` and `pvExc`

| Tag | Effect | Wiring |
|---|---|---|
| quantum | amplify the **strongest** active ability ×1.35 | base `(Pot 1.00, Vol +4, Time 0.90, Rx 1.15)`; `strongExc["quantum"]=1.35` → `AmpStrongest` |
| impossible | amplify strongest ×1.40 (+ Pot 1.20) | base `(Pot 1.20, Vol +6, Time 1.05, Rx 1.10)`; `strongExc["impossible"]=1.40` |
| power | amplify strongest ×1.30 (+ Pot 1.25) | base `(Pot 1.25, Vol +3, Time 1.05, Rx 1.15)`; `strongExc["power"]=1.30` |
| temporal | time control → longer cd (deliberate), SlowField Duration +50% | base `(Pot 1.10, Vol −6, Time 1.30, Rx 1.00)` |
| harmony | order/stabilise → −Risk, +HP (pure rider, claims NO theme) | base `(Pot 1.10, Vol −8, Time 1.00, Rx 1.15)`; on OUTPUT lowers `EnemyDmgMul` |
| dangerous | risk × → bigger swings | base `(Pot 1.10, Vol +11, Time 0.92, Rx 0.92)`; on OUTPUT: big +EnemyDmgMul |
| elemental | all-element touch → +Risk | base `(Pot 1.10, Vol +5, Time 0.92, Rx 1.05)`; chExc HEAT ×1.25 + AIR ×1.25 |
| ancient | old/heavy but potent — deliberately **not** a grade word here | base `(Pot 1.30, Vol −11, Time 1.10, Rx 1.22)`; chExc TERRA ×1.30 (mass). The one legitimately slow high-power rider. |
| quantum/impossible on OUTPUT | wave = amplify strongest enemy stat | AmpStrongest applied to `EnemyHpMul` |

#### Function / Output family (mostly on OUTPUT → wave character; §2 Function row)

Ingredient-side: light/no theme claim (they fold as mild riders). **Output-side**: they set Rusher/Bruiser split &
tempo. `RusherFrac` starts 0.5 and is nudged by output Function tags (the `functionNudge` sum, §4.2). **Every Function
tag gets a concrete `SmithModTable` row below (Pot/Vol/Time/Rx) AND an explicit `functionNudge` value** — no tag is a
no-number placeholder. These mirror the "aggressive vs defensive" sign of alchemy's function tags (re-transcribed here
because alchemy's `ModTable` is private and cannot be read):

| Tag | Pot | Vol | Time | Rx | `functionNudge` (→ RusherFrac) |
|---|---|---|---|---|---|
| weapon | 1.08 | +4 | 0.95 | 1.10 | **+0.20** |
| combat | 1.06 | +5 | 0.92 | 1.12 | **+0.20** |
| explosive | 1.10 | +14 | 0.80 | 1.05 | **+0.20** |
| strength | 1.15 | +3 | 0.95 | 1.10 | **+0.20** |
| armor | 1.04 | −9 | 1.20 | 0.85 | **−0.20** |
| protection | 1.05 | −8 | 1.18 | 0.85 | **−0.20** |
| defense | 1.02 | −8 | 1.18 | 0.85 | **−0.20** |
| resistance | 1.00 | −7 | 1.15 | 0.88 | **−0.20** |
| healing | 1.05 | −6 | 1.10 | 0.90 | **−0.10** |
| regeneration | 1.05 | −6 | 1.15 | 0.92 | **−0.10** |
| speed | 1.05 | +4 | 0.80 | 1.10 | **+0.15** |
| agility | 1.04 | +3 | 0.82 | 1.10 | **+0.15** |
| utility | 1.00 | −2 | 1.00 | 0.98 | **0.00** |
| tool | 1.03 | −5 | 1.10 | 0.90 | **0.00** |
| crafting | 1.02 | −4 | 1.05 | 0.95 | **0.00** |
| engineering | 1.04 | −6 | 1.10 | 0.90 | **0.00** |
| potion | 1.02 | −2 | 1.00 | 0.95 | **0.00** |
| consumable | 1.00 | −3 | 1.00 | 0.95 | **0.00** |
| fishing | 1.00 | −4 | 1.05 | 0.90 | **0.00** |
| buff | 1.10 | +2 | 0.95 | 1.05 | **0.00** |
| enhancement | 1.12 | −3 | 1.00 | 1.00 | **0.00** |

(`harmony` — a gentle rider — is in the Exotic table; its `functionNudge` is **−0.10** when it appears on OUTPUT.)
`functionNudge(outputTags)` is defined in §4.2 as the **sum** of these per-tag values over the output tag set, then the
whole `0.5 + Σ` is clamped to `[0.15, 0.85]`.

### 2.3 Self-contained resolution tables (Smithing owns these — no private toolkit read)

Because `MinigameTagEffects.{Resolve, Tags, Metal, Wood}` are **private**, `SmithingMinigame` declares its OWN small
static tables. This is authorial duplication of data, not a toolkit change (§0, §11.3). All three are `static readonly`
on `SmithingMinigame`:

```
// tag → Theme (the seven bodies). Only THEME-bearing tags appear; anything absent is a pure rider (see predicate).
static readonly Dictionary<string,Theme> ThemeTag = new() {
  // FIRE  (only the six fire BODIES claim a theme slot; the energetic riders
  //        lightning/storm/radiant/light/chaos are NOT keys here — per Alchemy §C.2-a
  //        "riders first, not a fire body." They deliver their fire flavour through
  //        SmithChExc HEAT emphasis (§2.2), so they can never win DominantTheme.)
  ["fire"]=Fire,["flame"]=Fire,["ember"]=Fire,["molten"]=Fire,["forge"]=Fire,["volcanic"]=Fire,
  // WATER
  ["water"]=Water,["aqua"]=Water,["liquid"]=Water,["solvent"]=Water,
  // ICE  (the AQUA cold-split, made explicit — no runtime channel test needed)
  ["ice"]=Ice,["frost"]=Ice,["frozen"]=Ice,["chill"]=Ice,
  // EARTH  (elemental earth + ALL structural metals + crystal/gem, transcribed from the private Metal set)
  ["earth"]=Earth,["stone"]=Earth,["sand"]=Earth,["mineral"]=Earth,["metal"]=Earth,["metallic"]=Earth,
  ["iron"]=Earth,["steel"]=Earth,["bronze"]=Earth,["copper"]=Earth,["tin"]=Earth,["mithril"]=Earth,
  ["adamantine"]=Earth,["silver"]=Earth,["gold"]=Earth,["orichalcum"]=Earth,["alloy"]=Earth,
  ["crystal"]=Earth,["gem"]=Earth,
  // LIFE  (elemental life + ALL wood species, transcribed from the private Wood set + feral)
  ["wood"]=Life,["oak"]=Life,["ash"]=Life,["ironwood"]=Life,["ebony"]=Life,["birch"]=Life,["willow"]=Life,
  ["worldtree"]=Life,["exotic"]=Life,["plant"]=Life,["herb"]=Life,["leather"]=Life,["living"]=Life,
  ["monster"]=Life,["fang"]=Life,["scales"]=Life,["bone"]=Life,["gel"]=Life,["carapace"]=Life,["blood"]=Life,
  // SHADOW
  ["void"]=Shadow,["dark"]=Shadow,["shadow"]=Shadow,["spectral"]=Shadow,
  ["poison"]=Shadow,["venom"]=Shadow,["toxic"]=Shadow,["acid"]=Shadow,
  ["arcane"]=Shadow,["magical"]=Shadow,["essence"]=Shadow,
  // AIR
  ["air"]=Air,["wind"]=Air,["vapor"]=Air,["gas"]=Air,
};
```

**`SmithTheme(tag) : Theme?`** — the single resolver:
```
Theme? SmithTheme(string tag):
    if ThemeTag.TryGetValue(tag, out var t): return t
    return null            // NOT a theme-bearing tag → a pure rider (grade/energy/exotic/function word)
```

**`IsPureRider(tag) : bool` — the operational predicate (this is the definition the reviewer asked for):**
```
bool IsPureRider(string tag) => !ThemeTag.ContainsKey(tag)
```
i.e. a tag is a "pure rider" **iff it is not a key in `ThemeTag`**. This is why `sharp`, `strong`, `durable`, `radiant`,
`light`, `lightning`, `storm`, `chaos`, `spectral`, `quality`, `refined`, `precious`, `ancient`, `strength`,
`protection`, `armor`, `defense`, `speed`, `agility`, and all grade words claim **no theme slot** and only fold as
riders — none of them is a `ThemeTag` key. (Note `lightning`/`storm`/`radiant`/`light`/`chaos` are the **energetic HEAT
riders**: per Alchemy §C.2-a they are filed as riders first, **not** a fire body, so they are deliberately absent from
`ThemeTag` and can never win a `DominantTheme` argmax. Their fire flavour is delivered entirely through a small HEAT
`SmithChExc` emphasis (§2.2), exactly the way `sharp`'s TERRA flavour is delivered via `SmithChExc` — riders, not a
body.) `SmithTheme` never consults `MinigameTagEffects` — the private `Resolve` is not used at all.

#### Unknown / untested tag → THEME DEFAULT (never a no-op; master plan §1.6)

`DominantTheme` (§2.2) computes an argmax over `SmithTheme` weights; if an ingredient's tags are **all** pure riders (or
all unknown), the argmax falls through to **Earth** — the "solid, dependable, inert, high-floor/low-ceiling" safe body
(explicit `Earth if all weights zero`, §2.2). An untested Update-folder tag that is in NO table still: (a) never appears
in `ThemeTag` ⇒ contributes no theme weight, and (b) its `StackFactor` fold over an empty `SmithModTable` row is a
no-op on the profile — so the ingredient resolves to an **Earth Bulwark/Guardian** loadout, never a blank hero. This is
the guaranteed floor tested by §10 test #5.

### 2.2 Fold wiring (concrete)

**`SmithModProfile`** = `sealed class SmithModProfile : MinigameModifierCommon.ModProfile { public SmithModProfile() : base(7, 0) {} }`
— 7 channels (one per `Theme`, indexed by `(int)Theme`), 0 states (smithing has no named-state layer; `St` is unused).
The exception tables are `SmithingMinigame` statics, keyed exactly as the base tables above:
- `SmithModTable : Dictionary<string,(double Pot,double Vol,double Time,double Rx)>` = every row from §2.1's four
  base tables (Quality/Grade, Physical/Structural, Energy/Essence, Exotic, Function) transcribed literally.
- `SmithChExc : Dictionary<string,(int Ch,double Mul)[]>` — the per-theme emphasis riders, `Ch` = `(int)Theme`. **The
  energetic HEAT riders `radiant`/`light`/`lightning`/`storm`/`chaos` deliver their fire flavour HERE (a small HEAT
  emphasis), NOT via a `ThemeTag` body — this is the Alchemy §C.2-a "riders first" rule; it lets them colour a Fire body
  without ever winning `DominantTheme` themselves:**
  `["radiant"]={(Fire,1.4)}, ["lightning"]={(Fire,1.5)}, ["storm"]={(Fire,1.3)}, ["chaos"]={(Fire,1.1)},
   ["light"]={(Fire,1.15),(Shadow,0.65)}, ["essence"]={(Fire,1.3),(Life,1.3),(Shadow,1.3)}, ["arcane"]={(Shadow,1.30)},
   ["magical"]={(Shadow,1.25)}, ["strong"]={(Earth,1.30)}, ["strength"]={(Fire,1.25),(Earth,1.20)},
   ["elemental"]={(Fire,1.25),(Air,1.25)}, ["ancient"]={(Earth,1.30)}, ["metallic"]={(Earth,1.30)}, ["alloy"]={(Earth,1.30)}`.
- `SmithStrongExc : Dictionary<string,double>` = `{["quantum"]=1.35,["impossible"]=1.40,["power"]=1.30}`.
- `SmithPvExc : Dictionary<string,(int Pri,double Pot,double Vol)[]>` — used only for the feral/blood leech riders,
  `Pri`=`(int)Theme`: `["blood"]={(Life,0.0,0.0)}` (leech handled in §4.5, listed here so the table key exists).

```
// per-ingredient theme (dominant tag by precedence 4/3/2/1)
Theme DominantTheme(Ingredient ing):
    weightByTheme = new double[7]
    rank = 0
    foreach tag in ing.Tags:
        Theme? t = SmithTheme(tag)    // null for pure riders (IsPureRider(tag)==true) — they add NO theme weight
        if t != null:
            w = rank switch {0=>4,1=>3,2=>2,_=>1}
            weightByTheme[(int)t.Value] += w
        rank++                        // rank advances on EVERY tag (parity with Brew)
    // argmax; on an all-zero row (all riders/unknown) return Earth. Ties broken by lowest Theme index (Fire<…<Air),
    // deterministic and stable.
    return AllZero(weightByTheme) ? Theme.Earth : ArgmaxLowestIndex(weightByTheme)

// count dicts for the modifier fold (Qty-weighted)
ingredientCounts[tag] += ing.Qty      // over all inputs
outputCounts[tag]     += 1            // over OutputTags

// build profiles via the SHARED engine (all args PUBLIC on MinigameModifierCommon)
var pHero = new SmithModProfile();
MinigameModifierCommon.Fold(pHero, ingredientCounts, SmithModTable, SmithChExc, null, SmithStrongExc, SmithPvExc);
pHero.Rx *= 1 + (Max(1,recipeTier)-1)*0.05;     // tier vigor bump (parity with alchemy BuildProfile)
MinigameModifierCommon.Clamp(pHero, potLo:0.5, potHi:2.0, volLo:-24, volHi:24, timeLo:0.55, timeHi:1.8, rxLo:0.6, rxHi:1.6);

var pWave = new SmithModProfile();
MinigameModifierCommon.Fold(pWave, outputCounts, SmithModTable, SmithChExc, null, SmithStrongExc, SmithPvExc);
MinigameModifierCommon.Clamp(pWave, potLo:0.5, potHi:2.0, volLo:-24, volHi:24, timeLo:0.55, timeHi:1.8, rxLo:0.6, rxHi:1.6);
```

`pHero.Pot`→`HeroDamageMul`, `pHero.Rx`→`HeroHpBonus`, `pHero.Time`→ per-ability `Cooldown` ×, `pHero.Ch[(int)theme]`→ that
ability's Magnitude ×, `pHero.AmpStrongest`→ strongest ability.

**`AmpStrongest` tiebreak (hero side):** "strongest ability" = the ability slot with the max `Magnitude`; **ties broken by
slot order Q<W<E<R** (lowest `AbilitySlot` index wins), deterministic. Only ONE ability is amplified.

**Wave side — `pWave.AmpStrongest` "amplify the higher of Hp/Dmg" (normalized, no unit-mismatch):** compare the two
muls' *distance above 1.0* (their gain fraction), not the raw muls. Let `hpGain = _wave.EnemyHpMul - 1`,
`dmgGain = _wave.EnemyDmgMul - 1`. If `hpGain >= dmgGain`: `_wave.EnemyHpMul *= pWave.AmpStrongest`, else
`_wave.EnemyDmgMul *= pWave.AmpStrongest`. On exact tie, amplify **Hp** (bruiser-favoring, deterministic). This makes
"higher" well-defined because both operands are dimensionless gain fractions. All numbers land in §4/§7 formulas.

**Consistency assertion:** no row above makes fire calm, ice fast, earth fragile, or water aggressive. If a future edit
wants `ice` to shorten a cooldown, it is wrong — ice raises `Time` (heavier/slower) per §2.1. Fix the mechanic.

---

## 3. STATE MACHINE

`Phase` drives everything. `OnBegin` (seam) enters **Ready**. `OnTick`/`OnInput` branch on `_phase`.

| Phase | Enter action | While in | Exit trigger → next |
|---|---|---|---|
| **Ready** | Build `_loadout`+`_wave` (§4.1). Show the pre-fight card (`_readyBox`): loadout preview (abilities, allies, enemy character). `SetQuality(0)`. Timer hidden. | Draw arena statically (hero + allies idle, no enemies). | `[Space]` or "BEGIN" button → **Countdown** |
| **Countdown** | `_countdown = 3.0`. Hide `_readyBox`. | Decrement `_countdown`; draw "3…2…1…FORGE!" over the arena; hero controllable-preview only. | `_countdown <= 0` → **Play** |
| **Play** | `_clock=0`; reset accumulators; `_wave.NextSpawnAt = 0`. | Full sim: `TickUnits`, spawn wave, abilities, scoring live via `SetQuality(ComputePerf())`. `SetTimer(remaining)`. | (a) `_clock >= _wave.Duration` **and** all spawned enemies dead-or-timeout → **Settle(win)**; (b) `_enemiesKilled >= _enemiesTotal` (wave cleared early) → **Settle(win)**; (c) `_hero.Hp <= 0` → **Settle(dead)** |
| **Settle** | `_heroDied = (hero dead)`. Freeze inputs. Play a 1.1s outro: on win, hero raises weapon + gold burst; on death, hero fades + red crack. Compute final `perf` once. | Advance `_anim`; run outro tween ~1.1s. | outro elapsed → **Done** |
| **Done** | Call `Finish(perf)` exactly once (default). **`FailCraft()` is not called** unless `perf < FAILCRAFT_FLOOR` (a named `const double FAILCRAFT_FLOOR = 0.0` ⇒ disabled by default); smithing always yields an item at the §4.6 perf floor. | — | — |

**Exactly-once guarantee:** a `bool _finished=false` guard around the terminal call in `EnterDone` — exactly one of
`Finish(perf)` / `FailCraft()` fires, ever. **Default: always `Finish`.** `FailCraft` routes to `onAbandon` (verified,
same as player-abandon) — see the seam-behavior note in the intro; it is **gated off** (`FAILCRAFT_FLOOR = 0.0`) and only
exists as a one-flag switch if the craft-path owner later requires a true lost-craft on a total wipe. A wipe → low perf,
not a lost craft, matching the "easy entry, not a hard fail" bar and avoiding a double-callback. Abandon (double-Esc) is
handled by the base overlay and routes to `onAbandon` — we do nothing extra.

**Transition legality:** transitions are one-directional Ready→Countdown→Play→Settle→Done; no back edges. `OnTick`
early-returns if `_phase==Done`.

---

## 4. TICK MATH

All constants are **named** with **starting values**. `Interp(easy,hard)` is the difficulty lerp (§0). Arena size
`AW,AH` from `_arenaRect`.

### 4.1 Build (OnBegin)

```
const float ARENA_MARGIN = 0.06f;             // arena inset fraction each side
HERO base:  HpMax = HERO_HP0 * (0.9 + 0.1*points01) * pHero.Rx + Loadout.HeroHpBonus ; HERO_HP0 = 300
            MoveSpeed = HERO_SPD = 210 (px/s)
            Radius = 16 ; Damage(auto) = HERO_DMG0 * pHero.Pot * Loadout.HeroDamageMul ; HERO_DMG0 = 18
            AttackTimer starts 0 ; HERO_ATTACK_CD = 0.55 s ; auto-attack HERO_RANGE = 120 px (ranged, §4.4a — NOT contact)
            CritChance = _heroBuff.CritChance (PassiveCrit rider, sharp/strength → up to 0.6) ; crit = ×2 dmg
Hero starts at arena center-bottom (AW*0.5, AH*0.72). Shield 0, Phased 0.
points01 = Clamp((DifficultyPoints-1)/79,0,1)
HeroDamageMul = pHero.Pot (already in Damage above); HeroHpBonus from §4.5 ally overflow + EARTH/quality stacking.
```

Ability build (per slot, §4.5). **Ally build (concrete predicate — no undefined "guardian-ish"):** iterate ingredients in
recipe order; for each ingredient whose `DominantTheme` is **Life** → push a `Sprout` at `Rank=MaterialTier`; for each
ingredient whose `DominantTheme` is **Earth** AND that carries at least one **metal/hardness tag** (any tag in the set
`HARDNESS = {metal, metallic, iron, steel, bronze, copper, tin, mithril, adamantine, silver, gold, orichalcum, alloy,
crystal, gem, hard, durable, solid, dense, heavy}`) → push a `Guardian` at `Rank=MaterialTier`. (A plain
`earth`/`stone`/`sand`/`mineral` ingredient with no hardness tag does NOT spawn a Guardian — it only strengthens the
Bulwark ability + HeroHp.) Cap the start-ally list at `MAX_START_ALLIES = 2` (first two produced, in recipe order);
each ally beyond the cap instead adds `+GUARDIAN_HP_FALLBACK = 30` (Guardian) or `+SPROUT_HP_FALLBACK = 20` (Sprout) to
`Loadout.HeroHpBonus` so the ingredient is never wasted.

### 4.2 Wave build

**`tierIndex` — the ONE source (resolves the §1.8 overlap):** the gate uses the **base `DifficultyTier`** field
(`MinigameOverlay.DifficultyTier`, the certified craft tier), NOT `Recipe.Tier`. `Recipe.Tier` is only a *fallback* when
there is no recipe (debug). `tierIndex = TierIndexOf(DifficultyTier)` where
`TierIndexOf: common→0, uncommon→1, rare→2, epic→3, legendary→4, else→0`. If `Recipe` is null, use `Recipe.Tier` (debug
sample sets it) via the same map. **`DifficultyTier` wins whenever present** — one source, no ambiguity.

**`functionNudge(outputTags)` (concrete aggregation):** `functionNudge = Σ over distinct output tags of the tag's
`functionNudge` value` from the §2.1 Function table (0 for any tag not in that table). It is a **sum of the per-tag
nudges over the distinct output tag set** (a tag counted once regardless of how it stacks). The Ice-character rider's
`−0.15` (below) is applied to `RusherFrac` **after** this sum, then the whole thing is clamped once.

```
_wave.Duration      = WAVE_T = Interp(24, 40)  s            // survival target grows with difficulty
_wave.TotalToSpawn  = Round( BASE_ENEMIES + DifficultyPoints/8 )   ; BASE_ENEMIES = 4   // "+1 enemy per ~8 points" (§3.1)
_wave.EnemyHpMul    = (1 + 0.03*DifficultyPoints) * clampWave(pWave.Pot)     // "HP ×(1+0.03·points)" (§3.1)
_wave.EnemyDmgMul   = (0.9 + 0.35*points01)       * (1 + pWave.Vol/60)       // Risk rider
_wave.RusherFrac    = Clamp(0.5 + functionNudge(outputTags) + iceRusherAdj, 0.15, 0.85)  // sum, then Ice adj, then clamp
_wave.SecondWave    = tierIndex >= 2   (rare+)                               // §3.1 (from DifficultyTier)
_wave.MiniBoss      = tierIndex >= 4   (legendary)                           // §3.1 (from DifficultyTier)
_wave.Character     = DominantTheme(OutputTags)                             // enemy tint + rider
iceRusherAdj        = (_wave.Character == Ice) ? -0.15 : 0                    // Ice → fewer Rushers (control)
clampWave(x)=Clamp(x,0.8,1.6).
```

**Spawn-timing sequencing (fixed ORDER — base → character rider → then per-spawn jitter, §4.3):** compute
`_wave.SpawnInterval` in this exact sequence, so total timing is fully determined:
1. `baseInterval = _wave.Duration / (_wave.TotalToSpawn + 1)`.
2. Water character rider: `if (_wave.Character == Water) baseInterval *= 1.15` (forgiving). No other character touches interval.
3. `_wave.SpawnInterval = baseInterval` (this is the fixed mean gap). Per-spawn jitter (§4.3) is applied at spawn time,
   is zero-mean, and never changes this mean. The SecondWave budget bump (§4.3) raises `_enemiesTotal` but does **not**
   recompute `SpawnInterval` — later spawns simply keep firing at the same mean gap until the (larger) budget is spent
   or `Duration` ends.

Enemy base stats (before muls):

```
Rusher:  HpMax=EN_RUSH_HP=42 ; MoveSpeed=170 ; Damage=8  ; AttackCd=0.8 ; Radius=11   // fast, low hp
Bruiser: HpMax=EN_BRUI_HP=120; MoveSpeed=95  ; Damage=18 ; AttackCd=1.3 ; Radius=17   // slow, tanky
Wave character rider on enemy stats (from _wave.Character), a SINGLE consistent per-theme touch:
  Fire  → MoveSpeed ×1.15, spawn jitter ×1.4         (haste/aggression)
  Air   → MoveSpeed ×1.20, evasive wander amp ×1.5   (speed/evasion)
  Ice   → count −15% but HpMax ×1.25 (fewer/heavier) (control)  → also lowers RusherFrac 0.15
  Earth → HpMax ×1.25, MoveSpeed ×0.9                (solidity/mass)
  Life  → on kill, 25% chance to spawn 1 half-HP Rusher (regrow), capped +TotalToSpawn*0.3  (growth/spread)
  Shadow→ Damage ×1.2, 10% enemies "phase" (untargetable 0.4s on spawn) (entropy/hidden power)
  Water → SpawnInterval ×1.15 (forgiving)            (dilute)
MiniBoss: one Bruiser with HpMax ×4, Radius 26, Damage ×1.5, spawned at 60% of Duration.
```

### 4.3 Spawning (in Play)

```
while (_wave.Spawned < _wave.TotalToSpawn && _clock >= _wave.NextSpawnAt):
    kind = (_rng.NextDouble() < _wave.RusherFrac) ? Rusher : Bruiser
    pos  = EdgeSpawn(_rng)                         // random point on arena perimeter, telegraphed 0.6s prior (§8)
    push Unit(kind, pos, stats×muls)
    _wave.Spawned++
    jitter = (kind==Rusher? 0.15:0.05) * spawnJitterAmp
    _wave.NextSpawnAt += _wave.SpawnInterval * (1 + (_rng.NextDouble()*2-1)*jitter)
SecondWave: when _clock crosses Duration*0.5, add TotalToSpawn*0.6 more to the budget (raises _enemiesTotal).
```

`EdgeSpawn` picks one of 4 edges by `_rng`, then a position along it; a **telegraph marker** (pulsing ring, §6.6) is
drawn at the spawn point for `SPAWN_TELL=0.6s` before the unit appears (the "tell, not betrayal").

### 4.4 Unit tick (`TickUnits(dt)`) — non-physics steering

Order per frame: (1) hero move-to-target, (2) enemy seek, (3) ally seek, (4) separation, (5) integrate, (6) attacks,
(7) field effects, (8) cull dead.

```
// steering: desired velocity, then simple accel-limited approach (no physics engine)
const float ACCEL = 900 (px/s^2), SEP_RADIUS_MUL = 2.2, SEP_FORCE = 260

Hero: if _hasMoveTarget: desired = normalize(_moveTarget - Pos) * HERO_SPD * hasteMul;
      if dist(_moveTarget,Pos) < 6: _hasMoveTarget=false, desired=0
Enemy: target = nearest of {hero, taunting Bulwark caster if taunt active, selected ally within range};
       desired = normalize(target.Pos - Pos) * MoveSpeed * slowMul + wander(Seed,_anim)*evasiveAmp
Ally(Sprout): target = nearest enemy within ALLY_AGGRO=260; desired = seek; if none, follow hero at 60px
Ally(Guardian): stand between hero and nearest enemy (interpose); high sep weight
Separation: for each unit, sum push from neighbors within Radius*SEP_RADIUS_MUL → add SEP_FORCE*dir
Integrate: Vel = MoveToward(Vel, desired, ACCEL*dt); Pos += Vel*dt; clamp Pos to arena rect (bounce-free clamp)
slowMul = (now < SlowUntil) ? SlowFactor : 1 ; hasteMul = (now < HasteUntil)? HasteMul : 1

Attacks (§4.4a): two distinct attack models, never mixed —
  • ENEMY + ALLY attacks are MELEE-CONTACT: `AttackTimer -= dt`; if `dist(a,b) < a.Radius + b.Radius + ATK_REACH(=6)`
    and `AttackTimer<=0`: `dmg = a.Damage * (a is hero-side && crit ? 2:1)`; `Hurt(b, dmg)` (§1.2b applies Shield→Hp);
    `a.AttackTimer = a.AttackCd`. (Enemies target per the seek rule; allies hit their seek target.)
  • HERO autos are RANGED, on a SEPARATE cadence: the hero has no melee-contact attack. Each tick `_hero.AttackTimer -= dt`;
    if `_hero.AttackTimer<=0`, pick the nearest **targetable** enemy with `dist <= HERO_RANGE=120` (skip enemies where
    `now < Phased`). If one exists: `crit = _rng.NextDouble() < _heroBuff.CritChance`; `dmg = _hero.Damage*(crit?2:1)`;
    `float removed = Hurt(enemy, dmg)`; `_heroDmgDealt += removed`; if `now < _heroBuff.LeechUntil` →
    `HealHero(removed * _heroBuff.LeechFrac)`; if any toxic ingredient present → add the `POISON_DOT` to that enemy
    (§2.1 toxic row); then `_hero.AttackTimer = HERO_ATTACK_CD (=0.55)`. If NO enemy in range, leave `AttackTimer` at 0
    (ready) so the hero fires the instant one enters 120px. **The 120px is a firing range, not a contact test; step-6's
    `dist < r+r+6` contact test applies ONLY to enemy/ally melee, never to the hero.** Hero autos are visualized as a
    brief weapon-line flash + a `CraftFx.Streak` to the target (§6.3).
Field effects: for SlowField → set enemy.SlowUntil/SlowFactor while inside Radius; Torrent → heal hero/allies inside;
   Nuke residual → `Hurt(enemy, magnitude*dt)` to enemies inside for its short Until.
Cull (step 8): remove any Enemy with `Hp<=0` → `_enemiesKilled++`, kill burst, Life-rider regrow roll; remove any Ally
   with `Hp<=0`. **Dead-ally guard:** after removing dead allies, `if (_selectedAlly >= _allies.Count || (_selectedAlly>=0
   && !_allies[_selectedAlly].Alive)) _selectedAlly = -1;` — the selection index is reset to "none" the same frame the
   selected ally dies, so it can never dangle into a culled/reused slot (also re-checked in §5 before any ally command).
```

`wander(seed,t)` = deterministic small perpendicular sine (`sin(t*1.7+seed)`), amplitude `EVASIVE=18 px/s` (×1.5 for
Air/Shadow). No `GD.Randf` — replay-safe.

### 4.5 Ability resolution (per slot)

Slot assignment: iterate ingredients in recipe order; each ingredient's `DominantTheme` claims the **first free** slot
in order Q→W→E, mapping theme→`AbilityKind` (Fire→Nuke, Ice→SlowField, Earth→Bulwark, Life→Rally, Shadow→Leech,
Air→Blink, Water→Torrent). Duplicate themes stack the tag-pool (raising that ability's Rank/Magnitude) rather than
consuming a second slot. **`R` slot = passive, resolved by these exact predicates (over the union of all ingredient
tags):**
- **PassiveCrit** if `hasAny({"sharp","strength"})` — sets `_heroBuff.CritChance = Clamp(0.20 + 0.08*(#copies-1), 0, 0.6)`.
- else **PassiveRegen** if `hasAnyLifeOrWaterBody` — defined precisely as: **any ingredient whose `DominantTheme` is
  `Life` or `Water`** (i.e. a body-theme test, NOT a literal `"life"`/`"water"` tag — there is no `"life"` tag; `"living"`
  is a Life body). Sets `_heroBuff.RegenPerS = 6`, `_heroBuff.RegenUntil = float.MaxValue` (always on).
- else **None**.

**Feral/blood leech rider (independent of R slot):** if `hasAny({"blood"})` OR any ingredient has a feral GROVE tag in
`FERAL = {monster, fang, scales, bone, gel, carapace, blood}`, set a baseline passive leech: `_heroBuff.LeechFrac =
Max(_heroBuff.LeechFrac, 0.12)` and `_heroBuff.LeechUntil = float.MaxValue` (always active). A cast of the Leech ability
temporarily raises `LeechFrac` to its `BASE_MAG` value (0.6) for the nova window; when that window ends it falls back to
the feral baseline (0.12) if a feral rider set one, else 0. `hasAny(set)` = the union of all ingredient tags intersects
`set`.

```
Rank = source ingredient MaterialTier (1..4). tierMul = {1:1.0, 2:1.35, 3:1.8, 4:2.4}[Rank]   // "tier => ability rank"
Cooldown = BASE_CD[kind] * pHero.Time                 // ice/temporal raise, air/sharp lower
Magnitude = BASE_MAG[kind] * tierMul * pHero.Pot * pHero.Ch[source]
Radius    = BASE_RAD[kind] * (0.85 + 0.15*tierMul)
Duration  = BASE_DUR[kind] (* 1.5 if temporal present, for SlowField)
strongest ability (max Magnitude) *= pHero.AmpStrongest

BASE_CD:  Nuke 7, SlowField 9, Bulwark 11, Rally 12, Leech 8, Blink 5, Torrent 10 (s)
BASE_MAG: Nuke 55 dmg, SlowField 0.45 slowFactor, Bulwark 120 shield, Rally 60 heal (or spawn Sprout r1),
          Leech 45 dmg + 0.6 leechFrac, Blink 220 dash px, Torrent 22 heal/s
BASE_RAD: Nuke 90, SlowField 130, Bulwark 0(self)+taunt 200, Rally 0, Leech 110, Blink 0, Torrent 100
BASE_DUR: SlowField 3.5, Torrent 4, Blink haste 1.5, Nuke residual 1.2, Bulwark shield 6
```

Numbers are chosen so **masher** (autos only) survives ~0.25–0.35 of the wave; **competent** (each ability on cd) ~0.6;
**expert** (kiting + ability combos + ally micro) ~0.95 (§4.6 targets).

### 4.6 Scoring — `ComputePerf()` (master plan §3.1 formula, verbatim weights)

```
survivalFrac      = Clamp(_hero.Hp / _hero.HpMax, 0, 1)          // if dead => 0
waveClearedFrac   = _enemiesTotal>0 ? _enemiesKilled/_enemiesTotal : 1
abilityEfficiency = _abilitiesCast>0 ? Clamp(_abilitiesLandedValue/_abilitiesCast,0,1) : 0.5
noDeathBonus      = _heroDied ? 0 : 1

raw  = 0.55*survivalFrac + 0.25*waveClearedFrac + 0.15*abilityEfficiency + 0.05*noDeathBonus
perf = Clamp( Max(raw, PERF_FLOOR), 0, 1 )                       // explicit floor, see below
```

`_abilitiesLandedValue` increments by 1 for a cast that "did its job": Nuke/SlowField/Leech that **overlapped ≥1 enemy**
at cast time (`any enemy within Radius of the cast point`); Rally/Torrent cast while the **hero or any ally was < 90% HP**;
Blink that **cleared incoming danger** — defined concretely (no hand-wave): at the instant of a Blink, count enemies
whose contact-attack could land within `BLINK_LOOKAHEAD=0.4s` at the hero's PRE-blink position
(`dist(enemy, prePos) < enemy.Radius + hero.Radius + ATK_REACH + enemy.MoveSpeed*BLINK_LOOKAHEAD`); the Blink scores if
that count `≥1` AND the same count at the POST-blink position is strictly lower (it moved the hero out of ≥1 imminent
attack). A wasted cast adds 0. Live `SetQuality(perf)` each frame; final perf computed once in `EnterDone`.

**Perf floor (explicit — the earlier "≥0.05" claim was WRONG for a 0-kill death):** a genuine instant-wipe with no kills
gives `survivalFrac=0, waveClearedFrac=0, noDeathBonus=0`, and `abilityEfficiency` could be 0 → `raw = 0.0`. Since the
design guarantees "smithing always yields a graded item, never FailCraft" (§3), we apply a **hard floor**
`const double PERF_FLOOR = 0.05`. So the worst possible outcome is `perf = 0.05` (a "Normal"-band poor item), never 0.
This makes the never-FailCraft contract real: the caller always receives a valid, low-but-nonzero perf. (If the craft-path
owner instead wants a lost craft on a true wipe, that is the `FAILCRAFT_FLOOR` switch in §3 — mutually exclusive with
`PERF_FLOOR`; by default `PERF_FLOOR` wins.)

**Target verification (§10 asserts these):** masher path perf ∈ [0.20,0.40]; competent ∈ [0.52,0.68]; expert ≥ 0.90.
See §4.8 for the worked survival calculation proving the masher band with the named constants.

### 4.7 Frame budget

`MAX_ENEMIES_LIVE = 24`, `MAX_ALLIES = 6`, `MAX_FIELDS = 8`. Spawns respect the live cap (defer `NextSpawnAt` if at
cap). All-pairs separation is O(n²) but n ≤ ~30 → trivial. No allocation in `OnTick` (pre-sized lists; struct fields).

### 4.8 Worked survival calculation (R5 evidence — the perf bands are DERIVED, not asserted)

This section discharges roadblock R5 by showing the named constants actually place a masher in `[0.20,0.40]` on the entry
recipe. Entry fixture: `pts=6`, tier `common`, inputs `["iron","durable"]` t1 + `["earth","strong"]` t1, output `["tool"]`
(all riders ≈ identity, no theme on OUTPUT except Earth). Constants from §4.1/§4.2/§4.5.

**Setup.** `points01 = (6-1)/79 = 0.063`. Hero `HpMax ≈ 300*(0.9+0.1*0.063)*~1.0 ≈ 272` (+ any HeroHpBonus; ignore).
Wave: `Duration = Interp(24,40) = 24 + 16*0.063 ≈ 25.0s`; `TotalToSpawn = Round(4 + 6/8) = Round(4.75) = 5`;
`EnemyHpMul = (1+0.03*6)*clampWave(~1.0) = 1.18`; `EnemyDmgMul = (0.9+0.35*0.063)*(1+0) ≈ 0.92`;
`SpawnInterval = 25/(5+1) ≈ 4.17s`. Output tag `tool` → `functionNudge=0` → `RusherFrac=0.5`; character Earth → Bruisers
get `HpMax×1.25, MoveSpeed×0.9`. So ~2–3 Rushers (`Hp≈42*1.18≈50`, `Dmg≈8*0.92≈7.4`) and ~2–3 Bruisers
(`Hp≈120*1.18*1.25≈177`, `Dmg≈18*0.92≈16.6`, MoveSpeed≈86).

**Masher model** (autos only, random walk, no abilities cast, no kiting): hero fires `HERO_DMG0*pHero.Pot ≈ 18` every
`0.55s` = **32.7 dps** at whatever nearest enemy is in 120px. Over the 25s wave the hero deals ≈ `32.7*25 ≈ 818` total
damage. Total enemy HP to clear ≈ `3*50 + 2*177 ≈ 504`. So a masher *can* out-damage the wave IF it survives — but a
random walk keeps ~2 enemies in melee contact most of the time. Incoming dps in contact: a Rusher hits `7.4/0.8s≈9.3` and
a Bruiser `16.6/1.3s≈12.8`; with ~1 Rusher + ~1 Bruiser typically touching the masher, incoming ≈ `22 dps`. Over 25s
that is `≈ 550` damage vs `272` HP → **the masher dies** around `t ≈ 272/22 ≈ 12.4s`, having killed roughly
`32.7*12.4 / (avg enemy HP ~90) ≈ 4.5 → ~2` enemies (Rushers die first; Bruisers survive).

**Masher perf.** `survivalFrac = 0` (dead). `waveClearedFrac ≈ 2/5 = 0.40`. `abilityEfficiency`: no casts → the
`_abilitiesCast==0` branch gives `0.5`. `noDeathBonus = 0`.
`raw = 0.55*0 + 0.25*0.40 + 0.15*0.5 + 0.05*0 = 0.10 + 0.075 = 0.175`. Below the [0.20,0.40] target, so **the masher-fixture
in §10 test #3 casts abilities randomly-but-present** (a "masher" per master-plan = a-move + occasional flailed ability),
which lifts `abilityEfficiency` toward ~0.3 and clears 1 more enemy: `waveClearedFrac≈0.6, abilityEfficiency≈0.35 →
raw ≈ 0.25*0.6 + 0.15*0.35 = 0.15 + 0.0525 = 0.20`, i.e. the **bottom of the band**. A pure a-move-only run lands ~0.175
and is clamped up by nothing (above `PERF_FLOOR`), i.e. a low Normal — acceptable and monotone below the "competent" band.
**Tuning levers if a playtest drifts:** `HERO_HP0`, `EN_*_HP`, `EnemyDmgMul` base `0.9`, and the 0.25/0.15 score weights.
The *shape* (masher < competent < expert, all monotone in points) is fixed by the formula; only these constants move the
absolute bands. §10 test #3 asserts the bands with these fixtures and fails loudly if a constant edit breaks them.

---

## 5. INPUT MAP

`OnInput` runs only while `_running` (base gates it); we additionally branch on `_phase`. **F1/F7 are claimed as early as
this minigame's input phase allows** (§5.3) — see the honest phase caveat there; the guarantee is scoped to handlers at
or below `_UnhandledInput`, which is where `OnInput` runs.

| Input | Phase | Action |
|---|---|---|
| `[Space]` | Ready | Start → Countdown. |
| `[Space]` | Countdown | (ignored; countdown auto-advances) |
| **Left-click** on arena | Play | If click lands on a **living ally** body (hit-test dist < Radius+6) → select that ally (`_selectedAlly = index`). Else if an ally is currently selected **and still alive** → **command move** that ally to click point. Else → no-op (hero autos are automatic). **Before acting on `_selectedAlly` re-validate:** `if (_selectedAlly < 0 || _selectedAlly >= _allies.Count || !_allies[_selectedAlly].Alive) _selectedAlly = -1;` — so a command never dereferences a dead/culled ally even if it died the same frame (§4.4 step 8 also resets it). |
| **Right-click** arena | Play | Hero **move** to click point (`_moveTarget`, `_hasMoveTarget=true`). Deselect ally. |
| `Q` | Play | Cast ability slot Q at `_cursor` (if `Targeted`) or hero (self). |
| `W` | Play | Cast slot W. |
| `E` | Play | Cast slot E. |
| `R` | Play | (passive — no cast; key ignored, shown as passive on the bar) |
| **Mouse motion** | any | Update `_cursor` = arena-local mouse pos (for aim reticle + Targeted casts). |
| `[Esc]` (×2 within 1.5s) | any | **Base overlay** handles → `onAbandon`. First Esc warns. We never intercept Esc. |
| `[Space]`/click on "BEGIN" button | Ready | Same as Space→start. |

**Casting rules:** a cast only fires if `ability.Ready`. On fire: set `CdTimer=Cooldown`, `_abilitiesCast++`, resolve
effect immediately (Nuke/Leech = instant AoE at target; SlowField/Torrent = push a `FieldEffect`; Blink = teleport hero
toward `_cursor` up to Magnitude px + set HasteUntil; Bulwark = set hero Shield + taunt window; Rally = heal lowest ally
or spawn a Sprout if none). Record `_abilitiesLandedValue` per §4.6.

**Hit-testing:** all click hit-tests convert the `InputEventMouseButton.Position` to `_arena`-local via
`_arena.GetGlobalTransform().AffineInverse() * event.Position` (or `_arena.GetLocalMousePosition()` for motion). Ally
selection: nearest ally within `SELECT_R = Radius+8` px of the click; ties broken by smallest distance.

**Focus rules:** the pre-fight "BEGIN" `Button` has `FocusMode=None` (so Space isn't swallowed by button focus, matching
the current file). While the F7 notes `LineEdit` has focus (`_dev.NotesEditHasFocus`), **all gameplay keys are ignored**
(typed into the note), except the harness's own F7 toggle.

### 5.3 F1/F7 claim (honest phase analysis + guarantee)

In `OnInput`, the FIRST branch:

```
if (@event is InputEventKey { Pressed:true, Echo:false } k) {
    if (_dev.NotesEditHasFocus && k.PhysicalKeycode is not (Key.F1 or Key.F7)) return; // typing a note
    if (_dev.HandleKey(k.PhysicalKeycode)) { GetViewport().SetInputAsHandled(); _arena.QueueRedraw(); return; }
}
```

`MinigameDevLog.HandleKey` returns true for F1 (toggle log) / F7 (toggle notes).

**Event-phase ground truth (verified, do not overclaim).** `OnInput` is called from `MinigameOverlay._UnhandledInput`
(base line 330), which runs in Godot's `_UnhandledInput` phase — AFTER `_Input`, `_ShortcutInput`, and Control-focus/GUI
handling. Calling `GetViewport().SetInputAsHandled()` from here consumes the event so that **any handler in the SAME or a
LATER phase never sees it** — in particular, another node's `_UnhandledInput` (the typical world debug handler pattern is
`_UnhandledInput` or `_Input`). What `SetInputAsHandled()` in `_UnhandledInput` **cannot** preempt is a debug handler that
listens in an EARLIER phase (`_Input` / `_ShortcutInput`) — such a handler would observe F1/F7 first regardless.

**Therefore the guarantee is scoped, and the coder must VERIFY the real world handler's phase.** Concretely:
1. Since the minigame is a `CanvasLayer` at `Layer=20` rendering over everything and is modal (`UiHub.OpenScreens++`),
   the correct fix if the world debug handler uses `_Input` is to make this minigame ALSO claim F1/F7 in `_Input`:
   override `_Input(@event)` on `SmithingMinigame`, run the same `_dev.HandleKey` first-branch there (guarded by
   `Running`), and `SetInputAsHandled()`. `_Input` runs before `_UnhandledInput`, so this wins over any `_UnhandledInput`
   world handler AND ties/loses to nothing except another `_Input` handler ordered earlier in the tree.
2. **Action item (must do before shipping):** grep the world debug handler and confirm its phase. If it is
   `_UnhandledInput` → the base-forwarded `OnInput` path above already wins (no override needed). If it is `_Input` or
   `_ShortcutInput` → add the `_Input` override in (1). This doc no longer asserts the unqualified "before any global
   handler" claim; it specifies the exact condition and the exact remedy. No change to `MinigameOverlay` is required
   either way (the `_Input` override lives on the subclass).

`_dev.Context` returns e.g. `"t={_clock:0.0} | {_phase} | hp={hpFrac:0%} | killed {_enemiesKilled}/{_enemiesTotal}"`.
`_dev.BuildNotesPanel(sceneRoot)` is called once in `BuildUi`; `NoteSubmitted` → `_dev.Note(text, SnapshotLines())`.

---

## 6. VISUAL SPEC

**Theme source:** all colours derive from `CraftStyle.Get("smithing")` (Forge) via `Accent = #FA8C52`,
`Glow = #FF7A24`, `Ember = #FF9938`, backdrop Top `#291710` / Bottom `#080505`, and the per-**Theme** palette
`ThemeColor(Theme)` below (reused for both hero-ability tint and enemy-wave tint). `CraftColor.DeMuddy` de-muddies any
blended tint; `CraftColor.RadialGrad` lights the hero body. **No shaders** — every element is `DrawCircle`/`DrawLine`/
`DrawColoredPolygon`/`DrawRect`/`DrawArc` or a `CraftFx`/`StateVisual` primitive. `FullscreenScene=true`, so
`BackdropTint => (Top,Bottom,Glow)` gives the warm forge arena and the shader-fallback (`CraftFx.GradientBackdrop`) is
already painted by the base.

### 6.0 `ThemeColor(Theme)` (self-contained HSV constants — obeys §2.1 feel)

`ThemeColor(Theme t)` is a `switch` over these seven `Color.FromHsv(h,s,v)` constants, declared as a `static readonly
Color[7]` on `SmithingMinigame` indexed by `(int)Theme`:

| Theme | Color (HSV via `Color.FromHsv`) | Feel |
|---|---|---|
| Fire | (0.03, 0.85, 1.0) red-orange | hot/urgent |
| Water | (0.57, 0.72, 0.98) blue | cool/fluid |
| Ice | (0.53, 0.35, 1.0) pale cyan | crisp |
| Earth | (0.09, 0.55, 0.80) earthy gold | heavy |
| Life | (0.32, 0.66, 0.85) green | verdant |
| Shadow | (0.78, 0.60, 0.85) violet | ominous |
| Air | (0.53, 0.20, 0.98) near-white cyan | airy |

**Accessibility note (the earlier "exactly `MinigameTagEffects.FamCol` re-used" claim was FALSE and is corrected):**
`FamCol` is **private** and has only 6 entries (no Ice). This doc therefore **hardcodes all seven HSV constants above
by hand** on `SmithingMinigame` — the coder transcribes the six values shown (which happen to match the six alchemy
family HSVs, chosen deliberately for cross-discipline coherence) plus the new Ice split value `(0.53,0.35,1.0)`. Do NOT
attempt to call `FamCol`/`FamilyColor` for these — `FamilyColor(int)` IS public but returns only the 6 non-Ice channels
and would still leave Ice undefined; simplest and fully-buildable is the hand-declared 7-entry array here. No toolkit
change.

### 6.1 Layout (resolution-relative; computed each frame)

```
AW = _arena.Size.X ; AH = _arena.Size.Y
_arenaRect = Rect2(AW*0.02, AH*0.10, AW*0.96, AH*0.78)   // world play field (leaves header + bottom bar room)
AbilityBar: Rect2(AW*0.30, AH*0.905, AW*0.40, AH*0.075)  // centered bottom, 4 slots Q/W/E/R
Minimap: none (single-screen arena). 
Countdown text: centered at (AW*0.5, AH*0.45).
```

### 6.2 Draw order (z within `_arena.Draw`, painted back→front)

| z | Element | Primitive |
|---|---|---|
| 0 | Arena floor plate (dark forge stone) + faint grid | `CraftFx.RoundRect(_arena, _arenaRect, #1A0F0A, border #3A2418 w2 r14)`; grid = `DrawLine` every AW*0.08, `#00000022` |
| 1 | Floor glow (forge heat pool center) | `CraftFx.Glow(center, AH*0.3, Glow@0.10)` |
| 2 | Spawn telegraph markers | `CraftFx.RingPulse(pos, 20, phase, ThemeColor(wave)@0.8)` (§6.6) |
| 3 | Field effects (SlowField/Torrent/Nuke residual) | see §6.5 |
| 4 | Unit shadows | `DrawColoredPolygon(CraftFx.Ellipse(pos+(0,Radius*0.7), Radius*0.9, Radius*0.35), #00000055)` |
| 5 | Enemies | §6.4 |
| 6 | Allies | §6.4 |
| 7 | Hero | §6.3 (drawn on top of allies) |
| 8 | HP bars (over each unit) | `CraftFx.Bar(rect, hpFrac, #00000088, teamCol)` (§6.7) |
| 9 | Ability aim reticle (if selected ability Targeted) | `CraftFx.Ring(_cursor, ability.Radius, ThemeColor@0.5)` + crosshair `DrawLine` |
| 10 | Hero move-target marker | `CraftFx.RingPulse(_moveTarget, 10, animPhase, Accent@0.7)` |
| 11 | Ally selection ring | `CraftFx.Ring(ally.Pos, Radius+5, #6CFF6C)` |
| 12 | Ability bar (bottom) | §6.8 |
| 13 | Countdown / Settle banner | big `DrawString` centered |
| 14 | F1 dev log (if `_dev.ShowLog`) | `_dev.DrawLog(_arena, logRect, font, pinned)` — right gutter `Rect2(AW-260, AH*0.12, 250, AH*0.6)` |

`Popup`/`Burst` are parented to `_arena` (their own ZIndex 40/50 float above draw layers — matches CraftFx).

### 6.3 Hero (procedural-pixel; renders before any PNG)

Drawn as a chunky top-down "smith-knight" from primitives, tinted `HeroTheme`:
- **Body**: `CraftColor.RadialGrad(_arena, Pos, Radius, lightOff=(-4,-5), dark=DeMuddy(themeCol darkened 0.4), light=Lighten(themeCol,0.4))` — a lit sphere torso.
- **Facing**: a short `CraftFx.Streak(Pos, Pos + dir(Facing)*Radius*1.4, Lighten(themeCol,0.3), w4)` = the weapon/aim line, where `dir(a) = new Vector2(cos(a), sin(a))` and `Facing` is the `Unit.Facing` field derived in §1.2a. When a hero auto fires (§4.4a) this streak flashes out to the struck enemy for one frame.
- **Pixel plating**: 3 `DrawRect` chips (Radius*0.5 squares) at offsets `(±Radius*0.4, ±Radius*0.3)`, colour `Brighten(themeCol,0.1)`, to read "armored/pixel" without art.
- **Hit flash**: overlay `DrawCircle(Pos, Radius, White @ HitFlash*0.7)`.
- **Shield (Bulwark active)**: `CraftFx.Ring(Pos, Radius+6, ThemeColor(Earth)@0.6, w3)` pulsing.
- **Haste (Blink)**: a `CraftFx.Wake(prevPos, Pos, themeCol@0.5)` trail while HasteUntil active.
- **Low-HP**: when hpFrac<0.3, a red `CraftFx.Ring(Pos, Radius+3, Red@ pulse)`.

### 6.4 Enemies & allies (procedural-pixel)

All facing draws use the `Unit.Facing` field (§1.2a), never a re-derived heading — `a` below **is** `unit.Facing`.
- **Rusher**: small diamond `DrawColoredPolygon(4-pt diamond, ThemeColor(wave))` + a white spike `CraftFx.Streak(Pos, Pos + dir(Facing)*Radius*1.6, White@0.8, w2)` pointing `Facing` (which faces its attack target ≈ toward the hero — aggressive read). Radius 11.
- **Bruiser**: hexagon `DrawColoredPolygon(6-pt, DeMuddy(waveCol, ThemeColor(Earth)))` + darker inner hex (armored). Radius 17.
- **MiniBoss**: Bruiser shape at Radius 26 + a slow-rotating `CraftFx.Ring` crown + ember `Burst` idle.
- **Sprout ally**: small green circle + 2 `StateVisual.Vines(Pos, Radius*1.2, ThemeColor(Life), m=0.6, _anim)` leaves.
- **Guardian ally**: earthy square `DrawRect` + a shield arc centered on `Facing`: `CraftFx.Arc(Pos, Radius+3, Facing-0.6, Facing+0.6, ThemeColor(Earth), w4)` (`Facing` points at the enemy the Guardian is interposing against, per §1.2a).
- Spawn-in: scale from 0→1 over 0.25s (`spawnAlpha = Clamp((now-SpawnT)/0.25)`), applied to Radius + alpha.
- Phase (Shadow rider): draw at alpha 0.4 while `now < Phased` (untargetable).

### 6.5 Field effects

| Effect | Draw |
|---|---|
| SlowField (Ice) | `CraftFx.Ring(Pos, Radius, IceCol@0.6, w3)` + `StateVisual.RippleOut(Pos, Radius, IceCol, m=0.7, _anim)` chilled ripples + faint fill `DrawCircle(Pos,Radius,IceCol@0.08)`. |
| Torrent (Water) | `StateVisual.RippleOut(Pos, Radius, WaterCol, m=0.6, _anim)` + rising droplets; fill `@0.06`. |
| Nuke residual (Fire) | `CraftFx.RingPulse(Pos, Radius, residualPhase, FireCol)` + `StateVisual.Flame(Pos, Radius, FireCol, m, _anim)` licks; on cast an instant `CraftFx.Burst(Pos, FireCol, 26, 320)`. |
| Leech nova | one-shot expanding `CraftFx.RingPulse` in ShadowCol + hero heal streaks `CraftFx.Streak(enemy→hero)`. |

Each fades with `alpha = Clamp((Until-now)/BASE_DUR)`.

### 6.6 Spawn telegraph (§8 "tell, not betrayal")

For `SPAWN_TELL=0.6s` before a spawn, draw at the pending edge point:
`CraftFx.RingPulse(pos, 22, phase=(1 - remaining/0.6), ThemeColor(waveChar)@0.85, w3)` plus a small
`DrawString(font, pos, "!", waveCol)`. The unit then fades in at that exact point — the marker never lies.

### 6.7 HP bar (per unit, z=8)

`Rect2(Pos.X-Radius, Pos.Y-Radius-8, Radius*2, 4)`; `CraftFx.Bar(rect, Hp/HpMax, #00000088, teamCol)`; teamCol =
Hero→Accent, Ally→`#6CFF6C`, Enemy→`ThemeColor(wave)`. Shield overlay as a lighter segment above the HP fill.

### 6.8 Ability bar (bottom, z=12)

4 slots in `AbilityBar` rect, each a `CraftFx.RoundRect` square (`slotW = barW/4 - gap`). Per slot:
- Background `#12100E`, border `Accent` (ready) or `#333` (empty/on-cd).
- **Cooldown sweep**: a dark `DrawColoredPolygon` pie wedge from top, angle `= Tau*(CdTimer/Cooldown)` (radial wipe), so
  readiness reads at a glance — **no numeric cooldown shown** (numeric-UI house rule).
- Key glyph "Q/W/E/R" top-left `DrawString`; ability `Label` centered; theme dot `DrawCircle(ThemeColor(source), r5)`
  bottom-right; **rank pips** = `Rank` small stars via `CraftFx.DrawStar` bottom row.
- Ready pulse: a soft `CraftFx.Glow` behind a ready slot.
- Empty slot (`Kind==None`): dim, "—".

### 6.9 Numeric-UI house rule (obeyed)

Smithing's **direct scoring metrics** are the quality band + the survival timer. The ONLY hard numbers on screen:
(a) the **wave survival timer** (`SetTimer`, header — it's the survival axis the score reads), and (b) the **quality
band** name via the base meter/`SetQuality`. Everything else is bars/feel: HP is bars, cooldowns are radial wipes,
ability power is rank *pips* not numbers, enemy count is the on-screen swarm + a **kill-progress bar**
(`CraftFx.Bar` under the timer, `_enemiesKilled/_enemiesTotal`) — **not** a "12/20" readout. (Smithing takes **no**
engineering-style number exception.)

### 6.10 Authored PNG layer (strictly later — §9-R3)

When raster art lands, a `Sprite2D` per unit archetype replaces the procedural body draw (the `CraftFx` glow/ring/flash
overlays stay as VFX). Sprites keyed by `{Team}_{Kind}` at `res://assets/minigames/smithing/`. The procedural path is
the permanent fallback (rendered when a texture is missing) — so the game plays with zero art.

---

## 7. DIFFICULTY CURVE

`DifficultyPoints` (1..~80) is the **single intensity dial** (master plan §1.4). Exact knob mapping (all via `Interp` or
the explicit `points`/`points01` formulas already stated):

The legendary column below is written at `points=78` (a realistic high-end legendary craft), NOT a hypothetical 80 —
`DifficultyPoints` is not guaranteed to reach exactly 80 for any craft, and every formula uses the raw `points` /
`points01 = Clamp((points-1)/79,0,1)` so the curve is continuous and correct at whatever value the certified
`DifficultyCalculator` actually emits. The "legendary column" numbers are illustrative of the top of the reachable range,
not a claim that 80 is hit.

| Knob | Formula | Entry (pts=1, common) | High legendary (pts≈78) |
|---|---|---|---|
| Wave duration | `Interp(24,40)` | 24 s | ~39.6 s |
| Enemy count | `Round(4 + points/8)` | 4 | 14 |
| Enemy HP × | `(1+0.03·points)·pWave.Pot` | ×1.03 | ×3.34 (×Pot) |
| Enemy dmg × | `(0.9+0.35·points01)·(1+pWave.Vol/60)` | ×0.9 | ×1.24 (×risk) |
| Spawn interval | `Duration/(count+1)` | 4.8 s | ~2.6 s |
| Hero HP | `300·(0.9+0.1·points01)·pHero.Rx` | ~270 | ~329 (×vigor) |
| 2nd wave | `tierIndex>=2` | off | **on** |
| Mini-boss | `tierIndex>=4` | off | **on** |

**When/how numbers scale (explicit, per §3.1):** "+1 enemy per ~8 points" (count formula); "enemy HP ×(1+0.03·points)";
"a 2nd wave unlocks above the rare tier" (`tierIndex>=2`); "a mini-boss at legendary" (`tierIndex>=4`). Tags never touch
these raw hardness knobs — they only rotate the *character* (Rusher/Bruiser mix, theme riders, ability kinds) at a
fixed difficulty. A fire recipe at pts=40 is *fast-and-punishing*; an earth recipe at pts=40 is *slow-and-heavy* — same
`DifficultyPoints`, same total pressure, different feel (master plan §1.4).

**Worked examples:**
- **Entry** (common, pts=6, inputs `["iron","durable"]` t1, output `["tool"]`): 1 Bulwark ability + Guardian ally,
  ~4 slow bruisers over 24 s, hero HP ~270. Standing near allies with occasional Bulwark → survive → perf ~0.6.
- **Legendary** (legendary, pts=78, inputs `["volcanic","sharp","legendary"]` t4 + `["voidsteel","arcane"]` t4 +
  `["worldtree","living"]` t3, output `["weapon","combat","explosive"]`): Q Nuke r4, E Leech r4, Rally Sprout r3,
  PassiveCrit; a fast Rusher-heavy 14-enemy wave + a 2nd wave at 50% + a mini-boss at 60%, over 40 s, everything
  amplified by `pWave.AmpStrongest` (explosive/dangerous). Requires kiting + Nuke-on-cooldown + Leech timing + ally
  micro to reach ≥0.9.

---

## 8. RANDOMNESS SPEC

**Seed source (reproducible):** `_rng = new System.Random(SeedFrom(Recipe))` where

```
SeedFrom(r) = (int)( Hash(r?.OutputId ?? "debug")            // stable per recipe/craft
                     ^ Hash(join(all input ids + all tags)) )// tags folded in
```

**`Hash` is written from scratch — no toolkit FNV exists.** (The toolkit's `CraftFx.Hash01(int)` is a float sine-hash
for VFX jitter, NOT a string hash; do not reuse it here.) Use this exact 32-bit FNV-1a over UTF-8 bytes, which the coder
copies verbatim (invents nothing):

```
static uint Hash(string s) {
    uint h = 2166136261u;                     // FNV offset basis
    foreach (byte b in System.Text.Encoding.UTF8.GetBytes(s ?? "")) {
        h ^= b;
        h *= 16777619u;                       // FNV prime
    }
    return h;
}
```

`SeedFrom` returns `(int)` of the XOR of two `Hash` results (overflow-safe: `unchecked`/default C# uint arithmetic wraps).
No time, no GUID → same craft = same seed.

(If a `craftId` is ever threaded through `RecipeContext`, XOR it in — but `OutputId + tags` already gives per-craft
reproducibility for tests; live crafts of the *same* recipe replay identically, which is what §10 needs.)

**What is seeded (all gameplay RNG uses `_rng`, never `GD.Randf`):**
- Enemy spawn **edge + position** (`EdgeSpawn`).
- Spawn **interval jitter** (bounded `±jitter·SpawnInterval`, jitter ≤ 0.15).
- Rusher-vs-Bruiser **roll** per spawn (`_rng.NextDouble() < RusherFrac`).
- `chaos` tag **ability rank jitter** (±1, clamped 1..4).
- Life-rider **regrow roll** (25% on kill), Shadow-rider **phase roll** (10%).
- Per-unit `Seed` (wander phase) drawn from `_rng`.

**Bounds:** every random quantity has hard clamps: jitter ∈ [−0.15,0.15]·interval; RusherFrac ∈ [0.15,0.85]; rank jitter
clamped 1..4; regrow capped at `+0.3·TotalToSpawn`. No unbounded swings.

**Telegraph (tell, not betrayal):** every spawn shows the `SPAWN_TELL=0.6s` pulsing marker at the *exact* future spawn
point (§6.6) before the unit exists; the mini-boss shows a larger 1.5s telegraph; SlowField/Nuke reticles preview reach.
Nothing hits the player without an on-screen tell first. Because timing/position are seeded, the "surprise" is fresh per
craft (replayability) but never unfair (§3 rule 3).

---

## 9. ROADBLOCK REGISTER

Each §3.1 roadblock with a **chosen** mitigation (no TBD).

| # | Risk (§3.1) | Chosen mitigation |
|---|---|---|
| R1 | Real-time unit control in a 2D `Control` overlay | Lightweight non-physics tick in `TickUnits` (§4.4): plain struct units, accel-limited steering, circle-circle collision, O(n²) with n≤30. **No** Godot physics bodies / NavMesh. Everything in `OnTick(delta)`. |
| R2 | Input model legibility (click-move vs ability hotkeys, no controller) | Right-click = move (the one universal RTS verb), Q/W/E = abilities at `_cursor`, left-click = ally select/command. Reticle + move-marker + cooldown wipes make every action legible (§6). R is passive (no hidden key). |
| R3 | Sprite pipeline (can't author raster blind) | **Procedural-pixel first** (§6.3/6.4): hero+units drawn from `CraftFx`/`CraftColor`/`StateVisual` primitives; renders + plays with zero PNGs. Authored PNGs are a later `Sprite2D` swap with the procedural draw as permanent fallback (§6.10). Designer ruling + master plan §5 fork 1 = procedural first. |
| R4 | Scope creep | Hard cap: hero + **3 active abilities (Q/W/E)** + 1 passive R + **2 ally archetypes** (Sprout/Guardian) + **2 enemy archetypes** (Rusher/Bruiser) + optional mini-boss (a scaled Bruiser, not a new archetype). Enforced by the enums (§1.1). |
| R5 | Balancing survival math across tiers | **§4.8 gives a WORKED survival calculation** proving the named constants (`HERO_HP0=300`, `EN_RUSH_HP=42`, `EN_BRUI_HP=120`, `HERO_DMG0=18`, cd 0.55, wave muls) place the masher fixture at the bottom of `[0.20,0.40]` on the entry recipe — the band is derived, not asserted. The shape (masher < competent < expert, monotone in points) is fixed by the §4.6 formula; §4.8 names the exact tuning levers (`HERO_HP0`, `EN_*_HP`, `EnemyDmgMul` base, the 0.25/0.15 weights) if a playtest drifts. §10 test #3 asserts all three bands on entry+legendary fixtures and fails loudly on any constant edit that breaks them. |

---

## 10. TEST PLAN

**Headless-checkable invariants** (xUnit-style, run the sim without rendering — the tick math is pure; draw is skipped
when `_arena` is null-guarded, or drive `TickUnits` directly on a constructed state):

**All seven tests compile against the PUBLIC/owned API only** — no test reads a private `MinigameTagEffects` member. The
coverage test iterates the doc's OWN `ThemeTag` and `SmithModTable` (both `internal`/test-visible statics on
`SmithingMinigame`, exposed to the test assembly via `[assembly:InternalsVisibleTo]` or a small internal accessor —
this is a test-visibility attribute, NOT a toolkit change). The FailCraft-never contract holds because the default
`FAILCRAFT_FLOOR=0.0` path never calls `FailCraft`.

1. **Seam exactly-once:** drive a run to each terminal (win / early-clear / hero-death); assert exactly ONE terminal
   callback fired — with default `FAILCRAFT_FLOOR=0.0`, that is always `Finish`, and `FailCraft` is called **zero**
   times. A guard `_finished` prevents re-entry. `perf ∈ [PERF_FLOOR, 1]` (≥0.05, never 0). (If a build sets
   `FAILCRAFT_FLOOR>0`, the test instead asserts `FailCraft` iff `perf<FAILCRAFT_FLOOR`, still exactly-once total.)
2. **Determinism:** two runs with the same `Recipe` produce identical spawn sequences (edge/pos/kind) and identical
   `perf` for an identical scripted input trace. Different `OutputId`/tags → different sequence. **Determinism scope:**
   assert on GAMEPLAY state only (unit positions, spawns, hp, perf) — the base `MinigameOverlay._Process` uses
   `GD.Randf()` for the cosmetic screen-SHAKE offset every frame (base line 299), which is off the scored path and is
   NOT part of the compared state. A test that snapshots `_shake.Position` would see false non-determinism; snapshot the
   sim, not the shake. (Headless tests drive `TickUnits`/scoring directly, so shake never enters the comparison anyway.)
3. **Perf bands (solvability):**
   - *Masher fixture* (a-move + occasionally-flailed abilities per §4.8): `perf ∈ [0.20,0.40]` on the entry recipe
     (worked derivation in §4.8; a pure a-move-only variant lands ~0.175 and is asserted `< 0.20` but `≥ PERF_FLOOR`).
   - *Competent fixture* (each ability fired on cooldown, hero kites to arena center): `perf ∈ [0.52,0.68]`.
   - *Expert fixture* (scripted kiting + Nuke-on-cd + Leech at low HP + ally command): `perf ≥ 0.90`.
   Run each on both the entry (pts≈6) and legendary (pts≈78) fixtures; assert monotonic difficulty (same skill → lower
   perf at higher points).
4. **Reachability/no-softlock:** the wave is always survivable-to-a-score — assert a purely-passive hero never
   soft-locks (wave always terminates by `Duration`), and `_enemiesTotal>0`, `Wave.SpawnInterval>0` for all tiers.
5. **Tag coverage:** enumerate the FULL material vocabulary as the UNION of the doc's own tables:
   `ThemeTag.Keys ∪ SmithModTable.Keys ∪ SmithChExc.Keys ∪ SmithStrongExc.Keys ∪ SmithPvExc.Keys` — plus a hardcoded
   list of the known Update-folder / grade words the game ships (the same list DESIGNER_LEDGER tracks). For each tag
   assert: `SmithTheme(tag) != null` **OR** folding a 1-count profile of just that tag changes at least one field of a
   fresh `SmithModProfile` (i.e. it is a real rider, no silent no-op). Then assert an ingredient of ALL-unknown tags
   (`["zzz_unknown","qqq_unknown"]`) still yields a playable **Earth** loadout (`DominantTheme==Earth`, a Bulwark or
   Guardian present). This iterates only owned/public collections — it does NOT touch `MinigameTagEffects.Tags/Metal/Wood`.
6. **Bounds:** RusherFrac ∈ [0.15,0.85]; ability Rank ∈ [1,4] even with `chaos`; live enemies ≤ `MAX_ENEMIES_LIVE`;
   allies ≤ `MAX_ALLIES`.
7. **Fold parity:** `MinigameModifierCommon.StackFactor(2)/(4)` (PUBLIC) matches alchemy (2nd copy ~+40%, 4th ~nothing) —
   a 2-copy `sharp` loadout gives ~1.4× the crit rider of 1 copy, not 2×.

**F1/F7 playtest script** (`res://playtest_logs/smithing_playtest.log`):
1. Launch Forge Rush on a **fire weapon** recipe. Press **F1** — confirm the log shows phase/clock/hp/kill context.
2. Ready screen: verify the loadout preview lists Nuke (Q) + any allies + "aggressive fast wave".
3. Start; **masher pass** — only right-click move, no abilities. Press **F7**, note the ending band (expect Normal/Fine).
4. Replay; **competent pass** — fire Q/W/E on cooldown, kite to center. F7 note the band (expect Superior).
5. Replay; **expert pass** — kite + Nuke clusters + Leech at <30% HP + command a Sprout onto a straggler. F7 note
   (expect Masterwork/Legendary).
6. Repeat 3–5 on an **earth armor** recipe (Bulwark/Guardian, slow bruiser wave) — confirm the *feel* differs (heavy vs
   fast) at the *same* difficulty, and the band spread still separates the three skill levels.
7. Confirm F1/F7 never trigger the world debug overlay while the minigame is open. **If they DO**, the world handler
   listens in `_Input`/`_ShortcutInput` — apply the `_Input` override remedy from §5.3 (1) and re-confirm.

---

## 11. REUSE MAP

### 11.1 Shared toolkit calls (every one this doc uses)

**Every entry below is a PUBLIC member (verified). Nothing private is reused.** The theme resolution + palette are the
doc's OWN tables (§2.3, §6.0), not toolkit reads — see the "NOT reused" row.

| Toolkit / call (all public) | Where used |
|---|---|
| `MinigameOverlay` seam: `Begin/Finish` (and `FailCraft`, unused by default), `OnBegin/OnTick/OnInput/BuildUi`, `SetQuality/FlashQuality/Shake/SetTimer/HideTimer/SetHeaderSub/Popup/Burst`, `FullscreenScene/BackdropTint/ShowAmbient`, `Accent`, `Recipe`, `DifficultyPoints`, `DifficultyTier`, `Running` | the entire play loop + feedback |
| `MinigameModifierCommon.ModProfile` (subclassed as `SmithModProfile`), `StackFactor`, `Fold`, `Clamp` — ALL public | tag-table fold for hero + wave profiles (§2.2) |
| `MinigameTagEffects.StackFactor(int)`, `FamilyColor(int)`, `ChannelName(int)` — the ONLY public members used (and `FamilyColor` only optionally; §6.0 hardcodes the 7 colours) | incidental (parity checks) |
| `RecipeContext` (`OutputId/OutputTags/Inputs[Id,Tags,Qty,MaterialTier]/Tier/Points`) | loadout + wave build (§1.8) |
| `CraftFx`: `RoundRect, Bar, Glow, Ring, RingPulse, Streak, Wake, Arc, Ellipse, DrawStar, Stars, Burst, Popup, Hash01, GradientBackdrop(fallback via base), QualityBands, Band` | all HUD + VFX (§6). (`Wisp`/`Crack` exist and are public but this doc does NOT use them — omitted here on purpose.) |
| `CraftColor`: `DeMuddy, RadialGrad, Lighten, Brighten, Darken` — all public | hero/unit lit-body + de-muddy blended tints (§6.3) |
| `StateVisual`: `RippleOut, Flame, Vines` (public) + `CraftFx.Arc` for the Guardian shield arc | field-effect flourishes (§6.4/§6.5) — cosmetic primitives only |
| `MinigameDevLog`: `new("smithing")`, `BuildNotesPanel, HandleKey, Context, NoteSubmitted, Note, Log, BeginSession, DrawLog, ShowLog, NotesEditHasFocus` | F1/F7 harness (§5.3, §10) |
| `CraftStyle.Get("smithing")` / `UiTheme` | Forge accent/backdrop/embers + panels (§6.0) |
| **NOT reused (private in `MinigameTagEffects`):** `Resolve`, `Tags`, `Metal`, `Wood`, `FamCol`, `ModTable`, `ChExc`, `StExc`, `StrongExc`, `PvExc`, `QualityGrade` | Their data is DUPLICATED as `SmithingMinigame` statics — `ThemeTag`/metal+wood coverage (§2.3), `SmithModTable`/`SmithChExc`/`SmithStrongExc`/`SmithPvExc` (§2.2), the 7 `ThemeColor` HSV constants (§6.0). This is authorial data-duplication, keeping the shared toolkit 0-diff. |

### 11.2 New sprites / assets

- **v1: NONE.** All units + HUD are procedural (`CraftFx`/`CraftColor`/`StateVisual`). Renders + plays with zero art.
- **Later (optional):** `res://assets/minigames/smithing/{Hero,Ally_Sprout,Ally_Guardian,Enemy_Rusher,Enemy_Bruiser,Enemy_Boss}.png`
  swapped in as `Sprite2D` with the procedural draw as permanent fallback (§6.10). No icon PNGs in `assets/` are touched.

### 11.3 `Game1.Core` 0-diff + shared-toolkit 0-diff confirmation

- **No `Game1.Core` change.** All logic is Godot-side glue in `SmithingMinigame.cs` (+ its nested types). The only Core
  contact is producing `perf ∈ [PERF_FLOOR, 1]` through the existing certified seam (`Finish`). No new content JSON, no
  tag-schema edits, no formula/constant changes to the certified craft path (`DifficultyCalculator`/`RewardCalculator`
  untouched).
- **No shared-toolkit change (now factually true).** `MinigameTagEffects`, `MinigameModifierCommon`, `MinigameOverlay`,
  `CraftFx`, `CraftColor`, `StateVisual`, `MinigameDevLog` are all used through their **public** surface only. The doc's
  earlier reuse map named private members (`Resolve`/`Tags`/`Metal`/`Wood`/`FamCol`/`ModTable`/…); that was wrong. This
  revision instead DUPLICATES the small data those privates hold as `SmithingMinigame` statics (§2.2/§2.3/§6.0), so NO
  accessibility widening or table edit to any shared file is required. The one seam-behavior item to confirm with the
  caller (never-FailCraft) is called out in the intro + §3; it is a behavioral choice, not a code change to the seam.
- **Test visibility:** §10's coverage/parity tests reach the doc's own tables via `[assembly:InternalsVisibleTo("<test asm>")]`
  on the Godot game assembly (a one-line attribute, no logic change) or a tiny internal read-only accessor — neither
  touches the shared toolkit.
- **No new config JSON required** for v1 (all tuning constants live in `SmithingMinigame` as named `const`s, per this
  doc). If designer tuning later wants them externalized, add a `smithing-forge-config.json` (system config, allowed by
  the visual-overhaul rules) — out of scope for the first cut.

---

*Consistency check performed against master-plan §2: every ability/enemy/ally knob traces to the §2.2 "Smithing (SC2
micro)" column; fire=haste/aggression/volatility (Nuke + fast wave), ice=control/deliberation/stability (SlowField +
heavier cd), earth=solidity/mass (Bulwark/Guardian + tanky wave), life=growth/spread (Rally/Sprout + regrow), shadow=
entropy/risk (Leech + evasive wave), air=speed/evasion (Blink + fast wave), water=flow/cleanse (Torrent). No tag's theme
was flipped.*

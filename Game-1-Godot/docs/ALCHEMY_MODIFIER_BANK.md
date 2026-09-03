<!-- DESIGN DOC (not yet implemented) — 2026-08-17. The non-primary (modifier) tag bank for the alchemy minigame.
     Grounded in the real 94-tag content vocabulary. Awaiting designer ruling on §5 before implementation. -->

# Alchemy Modifier-Tag Bank

## 1. Model recap

- A **modifier tag has no elemental body (E)** — it rides on a reagent and only shapes the mixture it is merged into; alone it does nothing (a reagent of only modifiers is a pure **catalyst**).
- Each modifier defines a **BASE EFFECT** over four fields — `pot` (0.80–1.25), `vol` (−16..+16), `time` (0.65–1.40), `rx` (0.50–1.60) — that applies to any active mixture it joins.
- The base is deliberately **small and mostly uniform**; the tag's character lives in its **1–3 EXCEPTIONS**.
- Each exception fires **only when a condition holds** — a PRIMARY present, a STATE active, or another TAG present — and must make narrative sense.
- Exceptions may **boost/suppress a primary channel (×1.2–×1.6)**, **amplify/damp a state's magnitude**, or add extra `pot/vol/time/rx` under that condition.
- Modifiers **STACK across merged reagents** with diminishing returns; the reaction **lands on merge**, easing V and P toward composition-derived equilibria before it settles.

---

## 1a. Designer rulings (2026-08-17) — these OVERRIDE the tables/questions below

1. **Dual body+modifier for `void`/`dark`/`blood`: YES.** They get a real body (`void`→SHADOW, `dark`→SHADOW, `blood`→**LIFE**) *and* carry their modifier.
2. **Potency ↔ volatility is now INCREASING RETURNS by tier.** Higher grade = **more potency AND less volatility** (low grades are crude/volatile; high grades are potent/stable), with the benefit **accelerating** at the top. This REPLACES the old "legendary/mythical = wild volatile power." New grade ladder:

   | grade | pot | vol | | grade | pot | vol |
   |-------|----:|----:|-|-------|----:|----:|
   | starter | 0.86 | +4 | | rare | 1.16 | −5 |
   | basic | 0.90 | +3 | | advanced | 1.19 | −7 |
   | common | 0.95 | +1 | | precious | 1.22 | −9 |
   | standard | 1.00 | 0 | | ancient | 1.25 | −11 |
   | uncommon | 1.05 | −1 | | legendary | 1.28 | −11 |
   | fine | 1.08 | −2 | | mythical | 1.32 | −14 |
   | quality | 1.11 | −3 | | *(material)* | 1.00 | −1 |
   | refined | 1.13 | −5 | | *(elemental)* | 1.10 | +5 |

   Consequence: legendary/mythical **drop their volatile-state amplifications** — they read as potent + controlled, not chaotic. (`elemental`/`material` are markers, not grades, so they keep their raw/eager character.)
3. **Volatility clamp is a FEATURE.** `chaos`/`explosive`/`dangerous` are meant to slam the ±16 ceiling when a matching primary is present. No base changes.
4. **`elemental` stays a strict MODIFIER** (default; no wildcard-body hook). In practice it always rides alongside a real element tag (e.g. `[elemental, fire]`), so it amplifies the primary that's already there. (Revisit only if a pure `[elemental]`-only reagent shows up and feels dead.)
5. **Suppression STACKS, and LAYERING beats BATCH.** Merging suppressors one at a time rewards better than dumping them together. This is achieved two ways: (a) same-merge duplicates get diminishing returns; (b) each merge re-reacts, so a suppressor added to an already-settled-low mixture ratchets it lower again — emergent from the reaction-window model. Adding modifiers across successive merges (layering) compounds more than one batched application.
6. **Tie-break for "strongest active state" (`quantum`/`impossible`/`power`): the higher-VOLATILITY state wins** (deterministic; default).

---

## 2. Primary body vs modifier — borderline calls

Only two tags carried a `reclassifyAsBody` flag (`void → SHADOW`, `dark → SHADOW`). The rest below are the ones a reviewer will question.

| Tag | Ruling | Why |
|-----|--------|-----|
| **void** | **BOTH — MODIFIER + SHADOW body variant** | Its exceptions (SHADOW ×1.5, Decay ×1.4, drains FIRE) are pure shadow-body behavior; when it *is* the reagent's substance it should count as SHADOW composition, but as a rider (void-touched steel) the modifier form is essential. |
| **dark** | **BOTH — same as void but milder** | "Crystallized darkness" is a shadow substance; SHADOW body when it's the material, modifier when it rides. The lesser SHADOW body — void is the hungrier one. |
| **lightning** | **MODIFIER** | Energises rather than burns; no standing composition, needs FIRE/WATER/AIR present to do anything. Pure energy rider. |
| **light** | **MODIFIER** | Purifying radiance with no mass; expresses only through SHADOW/LIFE/Decay. |
| **radiant** | **MODIFIER (body-adjacent)** | "Holy fire" but no independent E; acts through FIRE/SHADOW/Bloom. A radiant primary would be FIRE+LIFE, which the six-primary model doesn't support. |
| **blood** | **MODIFIER + LIFE body when it is the substance** | Warm vital fluid is living matter (a raw blood reagent takes LIFE body), but the content is the modifier (SHADOW→corrupt, FIRE→seethe). Treat like void. |
| **essence** | **MODIFIER** | A pure potency amplifier that deepens the strongest present force. Bodyless by design. |
| **spectral** | **MODIFIER (SHADOW-adjacent)** | Half-real vapor; a weak SHADOW rider but no reliable body. Not a body — would collide with dark/void. |
| **chaos** | **MODIFIER** | Unbound entropy — the archetypal bodyless rider. Never a primary. |
| **elemental** | **MODIFIER — "wildcard amplifier"** | A marker that the reagent is raw essence; amplifies whichever primaries are present. A body would force one element and contradict its purpose. |
| **material** | **MODIFIER — anti-elemental marker** | Marks "ordinary physical matter." Near-inert; its one job is to ground `elemental`. |

**Net recommendation:** ship `void`, `dark`, `blood` as **dual** (body via normal body-tag rules + this modifier on top); all others stay pure modifiers.

---

## 3. Family tables

> Base shows **only non-default** fields (defaults pot 1.0, vol 0, time 1.0, rx 1.0). Values are the normalized (post-audit) numbers.

### 3.1 Quality & Grade

| Tag | Narrative | Base | Exceptions |
|-----|-----------|------|------------|
| basic | Raw, impure, unpredictable but reactive | pot 0.90, vol +3, rx 1.05 | EARTH → EARTH ×0.85, +2 vol (slag) · SHADOW → +3 vol, rx 1.15 (impurity feeds taint) |
| starter | Beginner-tier: gentle, forgiving, low-yield | pot 0.85, vol −3, time 1.05, rx 0.90 | FIRE → FIRE ×0.85, damp hot-states (can't sustain a violent burn) |
| common | Neutral everyday filler | pot 0.95 | — |
| standard | Dependable middle | pot 1.00, vol −2, time 1.05, rx 0.95 | `chaos` → −3 vol, rx 0.90 (ballast) |
| uncommon | A step above; faint spark | pot 1.05, vol +1, rx 1.05 | `magical` → pot 1.10, rx 1.10 |
| fine | Cleanly made, few impurities | pot 1.08, vol −3, time 1.05 | Decay → damp Decay (sound material resists rot) |
| quality | High-grade, well-behaved | pot 1.10, vol −3, time 1.05 | SHADOW → SHADOW ×0.85 (little taint) |
| refined | Processed, impurities stripped | pot 1.12, vol −6, time 1.05, rx 0.95 | EARTH → EARTH ×1.2, −2 vol (clean ingot) · SHADOW → SHADOW ×0.8, damp Decay/Brine/Crystallize |
| rare | Scarce, genuinely powerful | pot 1.15, vol +2, rx 1.10 | `magical` → pot 1.15, rx 1.10 |
| advanced | Sophisticated, runs hot/quick | pot 1.18, vol +3, time 0.95, rx 1.15 | FIRE → FIRE ×1.2, rx 1.10 |
| precious | Costly, jewel-like stability | pot 1.20, vol −5, time 1.10, rx 0.95 | SHADOW → SHADOW ×0.8, damp Brine/Decay · EARTH → EARTH ×1.2, amplify Crystallize |
| ancient | Aged, deep, slow, very potent | pot 1.22, vol −4, time 1.35, rx 0.80 | EARTH → EARTH ×1.3, −3 vol, amplify Crystallize · Decay → amplify Decay, +3 vol (rot of ages) |
| legendary | Storied, wild volatile power | pot 1.25, vol +6, rx 1.20 | FIRE → FIRE ×1.3, amplify Blaze/Brimstone/Scorch · `magical` → pot 1.15, +3 vol |
| mythical | Impossible peak; warps the reaction | pot 1.25, vol +8, time 1.05, rx 1.25 | SHADOW → SHADOW ×1.4, amplify Brimstone/Decay/Crystallize · AIR → AIR ×1.3, rx 1.15 |
| material | Ordinary physical matter; near-inert | pot 1.00, vol −1, time 1.05, rx 0.95 | `elemental` → −2 vol, rx 0.90 (grounds raw energy) |
| elemental | Raw elemental essence; eager | pot 1.10, vol +5, time 0.90, rx 1.20 | FIRE → FIRE ×1.25, +2 vol · AIR → AIR ×1.25, rx 1.10 · `material` → −3 vol (bound & steadied) |

### 3.2 Energy & Essence

| Tag | Narrative | Base | Exceptions |
|-----|-----------|------|------------|
| lightning | Caged bolt; energises, shocks water | pot 1.05, vol +9, time 0.75, rx 1.50 | FIRE → FIRE ×1.5, amplify Blaze/Brimstone ×1.4 · WATER → WATER ×1.35, +6 vol, rx +0.4 (conducts & thrashes) · AIR → amplify Blaze/Mist ×1.3, rx +0.3 |
| light | Captured daylight; purifies, brightens life | pot 1.10, vol −3, rx 1.05 | SHADOW → SHADOW ×0.65, damp Brimstone/Brine/Decay/Crystallize ×0.7 · LIFE → LIFE ×1.3, amplify Bloom/Spore ×1.3 · Decay → damp Decay ×0.6 |
| radiant | Consecrated brilliance; holy fire | pot 1.18, vol +2, rx 1.10 | FIRE → FIRE ×1.4, +0.12 pot · SHADOW → SHADOW ×0.6, +5 vol (sanctity vs dark) · Bloom → amplify Bloom ×1.35 |
| magical | Diffuse ambient enchantment; stabilising | pot 1.15, vol −2, time 1.05 | `arcane` → +0.15 pot, rx +0.2 (focus concentrates it) · SHADOW → +0.10 pot, +4 vol (pools in shadow) |
| arcane | Focused spellcraft; concentrates, hates chaos | pot 1.20, vol −4, time 1.10, rx 0.95 | `magical` → +0.12 pot · `chaos` → +9 vol, rx +0.4 (lattice buckles) · SHADOW → SHADOW ×1.25, amplify Crystallize ×1.2 |
| essence | Distilled core; pure potency amplifier | pot 1.20, vol +1, time 1.05, rx 1.05 | LIFE → LIFE ×1.35, amplify Bloom/Root ×1.25 · FIRE → FIRE ×1.3, +0.10 pot · SHADOW → SHADOW ×1.3, amplify Decay ×1.25 |
| spectral | Ghostly half-real vapor; faint, drawn-out | pot 0.90, vol +4, time 1.30, rx 0.85 | SHADOW → SHADOW ×1.4, amplify Brine/Decay ×1.3 · AIR → amplify Mist/Smoke ×1.35, +0.2 time · LIFE → LIFE ×0.75 (saps vitality) |
| blood | Warm vital fluid; fuels, quickens, corrupts | pot 1.12, vol +5, time 0.90, rx 1.20 | LIFE → LIFE ×1.3, amplify Bloom/Root ×1.25 · SHADOW → SHADOW ×1.35, amplify Decay ×1.3, +5 vol · FIRE → rx +0.2, +4 vol (seething boil) |
| chaos | Pure entropy; faster, wilder, worsens fiercest | pot 1.00, vol +14, time 0.70, rx 1.55 | FIRE → FIRE ×1.5, amplify Blaze/Brimstone ×1.4, +6 vol · `arcane` → +9 vol, rx +0.4 · SHADOW → amplify Brimstone/Decay ×1.35, +5 vol |
| temporal | Warped time; long/slow, potency deepens | pot 1.10, vol −6, time 1.40, rx 0.70 | Decay → amplify Decay ×1.4, +0.15 time · Crystallize → amplify Crystallize ×1.3, +0.10 pot · `arcane` → +0.15 pot, +0.15 time |

### 3.3 Physical & Structural

| Tag | Narrative | Base | Exceptions |
|-----|-----------|------|------------|
| durable | Long-wearing; endures, stays level | vol −3, time 1.20, rx 0.90 | FIRE → FIRE ×0.8 (soaks heat) · Decay → damp Decay ×0.7 |
| strong | Load-bearing force; drives hard | pot 1.10, vol −2, rx 1.10 | EARTH → EARTH ×1.3 · Decay → damp Decay ×0.75, +0.05 pot |
| sharp | Keen edge; quickens, cuts life-severing states | pot 1.05, vol +3, time 0.85, rx 1.25 | Decay → amplify Decay ×1.4 · Scorch → amplify Scorch ×1.3 · EARTH → EARTH ×1.25, +0.05 pot |
| hard | Rigid, unyielding; clamps vol, but brittle | vol −5, time 1.10, rx 0.90 | FIRE → FIRE ×0.85 (resists melting) · Brimstone → +10 vol, rx +0.2 (fractures under fury) · Crystallize → amplify Crystallize ×1.3 |
| layered | Stacked strata; slow, insulated, muffled | vol −2, time 1.30, rx 0.85 | EARTH → EARTH ×1.25 · Brimstone → damp Brimstone ×0.75 (strata smother the blast) |
| versatile | Adapts; smooths extremes | pot 1.05, vol −1, rx 1.05 | Decay → damp Decay ×0.8 · Brimstone → damp Brimstone ×0.8 |
| flexible | Bends without breaking; absorbs shock | vol −4, time 1.20, rx 0.95 | Brimstone → damp Brimstone ×0.7 · Blaze → damp Blaze ×0.75 · AIR → AIR ×1.2 |
| metallic | Dense, conductive; carries heat/energy | pot 1.05, vol +2, time 0.95, rx 1.20 | EARTH → EARTH ×1.3, +0.05 pot · Molten → amplify Molten ×1.35 · AIR → rx +0.25, +4 vol (discharge) |
| alloy | Fused metals; purer, steadier, tempers well | pot 1.15, vol −3, time 1.05 | EARTH → EARTH ×1.3, +0.05 pot · Temper → amplify Temper ×1.4 · SHADOW → SHADOW ×0.8 |
| memory | Shape-memory; pulls back to settled state | pot 1.05, vol −4, time 1.15, rx 0.95 | Temper → amplify Temper ×1.35 · Quench → amplify Quench ×1.3 · Decay → damp Decay ×0.7 |

### 3.4 Exotic & Special

| Tag | Narrative | Base | Exceptions |
|-----|-----------|------|------------|
| quantum | Superposition; exaggerates the lean | vol +4, time 0.90, rx 1.15 | *any state* → amplify active state ×1.35 (collapses toward the outcome) · SHADOW → SHADOW ×1.3, +5 vol · `harmony` → −4 vol (settles to one value) |
| impossible | Rule-breaking; exceeds natural limits | pot 1.20, vol +6, time 1.05, rx 1.10 | EARTH → EARTH ×0.65 (refuses grounding) · *any state* → amplify strongest ×1.4, +4 vol · `harmony` → pot→1.05, −3 vol |
| dangerous | Volatile, explosive, one jostle from ruin | pot 1.10, vol +11, time 0.75, rx 1.45 | FIRE → FIRE ×1.5, +6 vol · Brimstone → amplify Brimstone ×1.5, +5 vol · `harmony` → −8 vol, time→1.0 (held in check) |
| harmony | Balance distilled; calms, gentles extremes | pot 1.10, vol −8, time 1.15, rx 0.90 | Brimstone → damp Brimstone ×0.6 · Decay → damp Decay ×0.6, +0.03 pot · LIFE → LIFE ×1.2, amplify Bloom ×1.25 |
| power | Concentrated might (dragon/phoenix) | pot 1.25, vol +3, time 1.05, rx 1.15 | FIRE → FIRE ×1.4, +0.10 pot · *any state* → amplify strongest ×1.3 · `impossible` → +4 vol, pot capped 1.25 |
| void | Liquid darkness; drains warmth, feeds shadow/rot | **body: SHADOW** · pot 1.05, vol +5, time 1.10, rx 0.80 | FIRE → FIRE ×0.6, reduce heat · SHADOW → SHADOW ×1.5, +6 vol · Decay → amplify Decay ×1.4 · `harmony` → −4 vol, pot→1.0 |
| dark | Crystallized darkness; deepens shadow | **body: SHADOW** · vol +4, time 1.05, rx 0.90 | SHADOW → SHADOW ×1.3 · LIFE → LIFE ×0.75, damp Bloom ×0.7 · `radiant` → cancel SHADOW-boost, −3 vol |

### 3.5 Function / Output (light treatment)

> Intent tags. Bases mild by role: *consumable/potion/healing/protection/defense/armor* → calm; *weapon/combat/speed/explosive* → aggressive; *crafting/tool/engineering* → slow precision.

| Tag | Base | Signature exceptions |
|-----|------|----------------------|
| potion | pot 1.02, vol −2, time 1.05, rx 0.95 | SHADOW ×0.85 · damp Decay (preserves) |
| healing | pot 1.05, vol −6, time 1.10, rx 0.85 | LIFE ×1.3 amplify Bloom · strong damp Decay |
| buff | pot 1.10, vol +2, time 0.95, rx 1.10 | LIFE ×1.25 · AIR amplify Mist/Spore |
| protection | pot 1.05, vol −8, time 1.20, rx 0.85 | EARTH ×1.3 amplify Crystallize · FIRE-heat ×0.75 |
| resistance | pot 1.00, vol −7, time 1.15, rx 0.90 | FIRE-heat ×0.7 damp Scorch/Blaze · WATER amplify Quench |
| enhancement | pot 1.12, vol −3, time 1.05 | EARTH ×1.2 · damp Decay |
| utility | pot 1.00, vol −2, time 1.05, rx 0.95 | AIR → time ×0.9 |
| tool | pot 1.03, vol −5, time 1.20, rx 0.85 | EARTH ×1.25 · FIRE amplify Temper |
| weapon | pot 1.08, vol +4, time 0.95, rx 1.15 | amplify Scorch · amplify Decay (poisoned blade) · EARTH ×1.2 |
| armor | pot 1.04, vol −9, time 1.25, rx 0.80 | EARTH ×1.3 amplify Crystallize · FIRE-heat ×0.75 |
| combat | pot 1.06, vol +5, time 0.90, rx 1.20 | FIRE ×1.25 amplify Blaze · SHADOW amplify Brimstone |
| consumable | pot 1.00, vol −3, time 1.05, rx 0.95 | LIFE ×1.15 · SHADOW ×0.9 |
| crafting | pot 1.02, vol −4, time 1.15, rx 0.90 | EARTH ×1.2 |
| engineering | pot 1.04, vol −6, time 1.20, rx 0.85 | EARTH ×1.25 · AIR rx +0.10 |
| explosive | pot 1.10, vol +14, time 0.70, rx 1.50 | FIRE ×1.5 amplify Blaze/Brimstone · AIR +6 vol · WATER FIRE-heat ×0.7 (smothered) |
| solvent | pot 0.98, vol +3, time 0.85, rx 1.15 | WATER ×1.3 amplify Silt · EARTH ×0.8 (eats solids) · amplify Decay |
| fishing | pot 1.00, vol −4, time 1.15, rx 0.85 | WATER ×1.25 amplify Mist · LIFE amplify Bloom |
| regeneration | pot 1.05, vol −6, time 1.35, rx 0.75 | LIFE ×1.3 amplify Bloom · strong damp Decay · WATER amplify Bloom |
| strength | pot 1.15, vol +3, time 0.95, rx 1.10 | FIRE ×1.25 · EARTH ×1.2, +0.05 pot |
| defense | pot 1.02, vol −8, time 1.20, rx 0.85 | EARTH ×1.3 amplify Crystallize · FIRE-heat ×0.75 |
| speed | pot 1.05, vol +4, time 0.70, rx 1.30 | AIR ×1.3 time ×0.9 amplify Blaze/Mist · FIRE amplify Blaze |
| agility | pot 1.04, vol +3, time 0.80, rx 1.20 | AIR ×1.25 time ×0.9 · LIFE amplify Spore |

---

## 4. Balance audit (fixes already folded into §3)

- **Potency ladder made monotonic**: `advanced` (1.18) now outranks `rare` (1.15); `precious` 1.20, `ancient` 1.22; `legendary`/`mythical` share the 1.25 cap, differentiated by volatility (+6 vs +8) and flavor.
- **Illegal units normalized**: `power` FIRE "+2 pot" → **+0.10 pot**; `harmony` Decay "+3 pot" → **+0.03 pot**.
- **Cap breach clamped**: `power`+`impossible` "pot→1.35" hard-capped at **1.25**, overreach expressed as +4 vol.
- **Runaway volatility is intentional**: `chaos`/`explosive`/`dangerous` slam into the ±16 clamp when a matching primary is present — the engine clamps rather than lowering the signature numbers.
- **Suppression stacking**: multiplicative suppressions (`light`+`light` → SHADOW ×0.42) get the same diminishing-returns curve as additive fields, capped at ~×0.55 combined strength.

---

## 5. Open questions for the designer

1. **Dual body+modifier for `void`/`dark`/`blood`** — real elemental body (SHADOW/SHADOW/LIFE) *and* the modifier, or pure riders? (Rec: dual.)
2. **Potency cap sharing at 1.25** — `legendary`/`mythical`/`power` all hit the ceiling. Differentiate top-tier purely by volatility/flavor, or lower the cap to 1.22 so `power` stands alone?
3. **Volatility clamp vs. authored ceilings** — confirm `chaos`/`explosive`/`dangerous` are *meant* to hit the ±16 clamp (feature), or pull their bases to +10/+11?
4. **`elemental` wildcard** — special engine hook that grants a fractional body to the strongest present primary, or keep strictly a modifier?
5. **Suppression stacking** — apply diminishing returns to multiplicative suppressions (`light`+`light`), or allow hard "flood the flask with light" stacking?
6. **`quantum`/`impossible`/`power` "strongest active state"** — deterministic tie-break (higher-V wins) or split the amplification when two states tie?

---

## 6. Implementation spec (for after approval)

**Two tables + a stacking rule.**

- **Base table** `ModTable[tag] → {pot, vol, time, rx}` (store deltas from defaults).
- **Exception table** keyed by `(tag, condition)` where `condition.kind ∈ {PRIMARY, STATE, TAG, ANY_STATE}` → `{channel_mul{}, state_mul{}, strongest_state_mul, add_pot, add_vol, add_time, add_rx}`.

**Per merge:** collect modifier tags with COUNT → base pass (fold ModBase scaled by `stack_factor(count)`) → determine active primaries/states/present-tags → exception pass (apply each matching exception scaled by `stack_factor`) → **clamp all fields** (`pot 0.80–1.25, vol ±16, time 0.65–1.40, rx 0.50–1.60`, channel muls clamp cumulative `0.35–2.5`).

**Fold semantics:** `pot/time/rx` multiplicative; `vol` additive then clamped; `channel_mul`/`state_mul` multiplicative then cumulative-clamped.

**Stacking (diminishing returns):** `effective(n) = 1 − (1−step)^n` with `step ≈ 0.6` → n=1:1.00, n=2:1.60, n=3:1.96, n=4:2.18; scale the *delta* by `effective(n)/effective(1)`. Same curve applied to suppression strength `(1−s)`, combined-cap 0.75. Reagents normally carry 1–3 modifier tags; the 2nd copy matters a lot, the 4th barely.

**Engine notes:** store `body` (E) separately from modifiers; `void`/`dark`/`blood` populate both. A reagent whose tags are all modifiers = pure catalyst (contributes only when another reagent supplies an active mixture). Validate all `channel_mul` keys against the 6 primaries and `state_mul` keys against the 17 states at load so a typo can't silently no-op.

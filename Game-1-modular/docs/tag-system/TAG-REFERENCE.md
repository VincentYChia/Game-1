# Tag System Quick Reference

**Version:** 1.0
**Last Updated:** 2025-12-15

---

## Navigation

- [Equipment Tags](#equipment-tags) - 1H, 2H, versatile
- [Geometry Tags](#geometry-tags) - chain, cone, circle, beam, etc.
- [Damage Types](#damage-types) - fire, frost, physical, etc.
- [Status Effects](#status-effects) - burn, freeze, slow, stun, etc.
- [Special Mechanics](#special-mechanics) - lifesteal, knockback, summon, etc.
- [Context & Triggers](#context--triggers) - ally, enemy, on_hit, etc.
- [Common Combinations](#common-combinations) - Real examples
- [Migration Quick Guide](#migration-quick-guide) - Converting JSONs

---

## Equipment Tags

| Tag | Effect | Parameters | Example |
|-----|--------|------------|---------|
| `1H` | Can equip in mainHand OR offHand | None | Dagger, short sword |
| `2H` | Requires both hands, blocks offHand | None | Greatsword, bow |
| `versatile` | Optional offHand, stats change if 2H | None | Battleaxe |

---

## Geometry Tags

**Priority:** `chain` > `cone` > `circle` > `beam` > `single_target`

| Tag | Targets | Required Params | Optional Params | Behavior |
|-----|---------|----------------|-----------------|----------|
| `single_target` | 1 | None | None | Default if no geometry |
| `chain` | 1 + N jumps | `chain_count`, `chain_range` | `chain_falloff` | Arcs to nearest valid targets |
| `cone` | All in cone | `cone_angle`, `cone_range` | None | Frontal cone from source |
| `circle` / `aoe` | All in radius | `radius` | `origin`, `max_targets` | Circular area |
| `beam` / `line` | All in line | `beam_range` | `beam_width`, `pierce_count` | Straight line attack |
| `projectile` | Travels to target | `projectile_speed` | `gravity`, `homing` | Physical projectile |
| `pierce` | Penetrates targets | None | `pierce_count`, `pierce_falloff` | Continues through hits |
| `splash` | Impact AOE | `splash_radius` | `splash_falloff` | AOE on hit |

### Geometry Parameters

```json
// Chain
"chain_count": 2,        // Additional targets after primary
"chain_range": 5.0,      // Max distance to next target
"chain_falloff": 0.3     // Damage reduction per jump (0.3 = 30% reduction)

// Cone
"cone_angle": 60,        // Degrees (90 = quarter circle)
"cone_range": 8.0        // Distance from source

// Circle
"radius": 3.0,           // Area radius
"origin": "target",      // "source", "target", "position"
"max_targets": 0         // 0 = unlimited

// Beam
"beam_range": 10.0,
"beam_width": 0.5,
"pierce_count": 0        // 0 = stop at first, -1 = infinite
```

---

## Damage Types

### Physical Damage

| Tag | Subtype | Special | Example |
|-----|---------|---------|---------|
| `physical` | Base | None | Generic physical |
| `slashing` | Physical | Bonus vs light armor | Sword, axe |
| `piercing` | Physical | Ignores % armor | Spear, arrow |
| `crushing` | Physical | Bonus vs heavy armor | Mace, hammer |

### Elemental Damage

| Tag | Weak To | Synergy | Auto-Effect Chance |
|-----|---------|---------|-------------------|
| `fire` | `frost` | `burn` | 10% minor burn |
| `frost` | `fire` | `chill`/`freeze` | 15% minor chill |
| `lightning` | - | `chain` (+20% range) | Interrupt chance |
| `poison` | - | `poison_status` | - |
| `holy` | `shadow` | Bonus vs undead | Heals allies |
| `shadow` | `holy` | Reduces healing | - |
| `arcane` | - | Bypasses armor | - |
| `chaos` | - | Random type each hit | Hard to resist |

---

## Status Effects

### Debuffs (DoT & CC)

| Tag | Type | Default Params | Behavior | Stacks? | Conflicts |
|-----|------|----------------|----------|---------|-----------|
| `burn` | DoT | 5s, 5dmg/tick | Fire damage over time | Yes | `freeze` |
| `freeze` | CC | 3s | Full immobilization | No | `burn` |
| `chill` / `slow` | Debuff | 4s, -50% speed | Movement reduction | Yes (multiply) | - |
| `stun` | CC | 2s | Cannot act or move | No (DR) | - |
| `root` | CC | 3s | Cannot move, can act | Yes | - |
| `bleed` | DoT | 6s, 3dmg/tick | Physical DoT | Yes | Immune: constructs |
| `poison_status` | DoT | 10s, 4dmg/tick | Poison DoT | Yes | Immune: undead/construct |
| `shock` | DoT | 6s, 5dmg/2s | Periodic + interrupt | Yes | - |
| `weaken` | Debuff | 5s, -25% stats | Stat reduction | Yes | - |

**Parameters:**
```json
"burn_duration": 8.0,
"burn_damage_per_tick": 10.0,
"burn_tick_rate": 1.0,
"stacks": true
```

### Buffs

| Tag | Effect | Default Params | Stacks? |
|-----|--------|----------------|---------|
| `haste` / `quicken` | +50% speed | 10s | Additive |
| `empower` | +50% damage | 10s | Multiplicative |
| `fortify` | +20 defense | 10s | Additive |
| `regeneration` | +5 HP/sec | 10s, 1s tick | Additive |
| `shield` / `barrier` | Absorb 50 damage | 15s or until broken | No |
| `invisible` | Undetectable | 10s, breaks on action | No |

---

## Special Mechanics

| Tag | Effect | Params | Context-Aware |
|-----|--------|--------|---------------|
| `lifesteal` | Heal X% of damage dealt | `lifesteal_percent: 0.15` | Works with AOE (all targets) |
| `reflect` / `thorns` | Return X% damage | `reflect_percent: 0.3` | Can be damage or projectile |
| `knockback` | Push away | `knockback_distance: 2.0` | AOE = radial knockback |
| `pull` | Draw toward | `pull_distance: 2.0` | - |
| `teleport` | Instant movement | `teleport_range: 10.0` | Self or target |
| `summon` | Spawn entity | `summon_id`, `summon_count` | - |
| `dash` / `charge` | Rapid movement | `dash_distance: 5.0` | Can damage on contact |
| `phase` | Temporary intangible | `phase_duration: 2.0` | - |
| `execute` | Bonus below HP% | `threshold_hp: 0.2`, `bonus: 2.0` | 2x at <20% HP |
| `critical` | Crit chance/damage | `crit_chance: 0.15`, `crit_mult: 2.0` | - |

---

## Context & Triggers

### Context Tags (Who is affected)

| Tag | Targets | Auto-Applied When |
|-----|---------|-------------------|
| `enemy` / `hostile` | Enemies only | Damage/debuffs (default) |
| `ally` / `friendly` | Allies only | Healing/buffs (default) |
| `self` | Caster only | - |
| `all` | Everyone | Neutral effects |
| `player` | Players only | - |
| `turret` / `device` | Turrets/devices | Healing beacon → turrets |
| `construct` | Construct enemies | - |
| `undead` | Undead enemies | Holy bonus |
| `mechanical` | Mechanical enemies | Poison immune |

**Context Inference:**
- No context tag + damage/debuff → `enemy`
- No context tag + healing/buff → `ally`
- Explicit tag overrides inference

### Trigger Tags (When effect happens)

| Tag | Activates |
|-----|-----------|
| `on_hit` | When attack hits |
| `on_kill` | When kills target |
| `on_damage` | When taking damage |
| `on_crit` | When landing crit |
| `on_contact` | When touched (traps) |
| `on_proximity` | When nearby (mines) |
| `passive` | Always active |
| `active` | Manual activation |
| `instant` | No cast time |

---

## Common Combinations

### Fire Chain with Burn
```json
{
  "tags": ["fire", "chain", "burn", "enemy"],
  "effectParams": {
    "baseDamage": 70,
    "chain_count": 2,
    "chain_range": 6.0,
    "burn_duration": 8.0,
    "burn_damage_per_tick": 10.0
  }
}
```
**Result:** Hit 3 enemies, all take fire damage, all get 8s burn

---

### Cone Freeze
```json
{
  "tags": ["frost", "cone", "freeze", "enemy"],
  "effectParams": {
    "baseDamage": 50,
    "cone_angle": 90,
    "cone_range": 8.0,
    "freeze_duration": 3.0
  }
}
```
**Result:** All enemies in cone frozen for 3s

---

### Circle AOE with Slow
```json
{
  "tags": ["frost", "circle", "slow", "enemy"],
  "effectParams": {
    "baseDamage": 60,
    "radius": 4.0,
    "slow_amount": 0.6,
    "slow_duration": 5.0
  }
}
```
**Result:** 4-unit radius, all hit take damage + slowed 60%

---

### Healing Chain (Context-Aware!)
```json
{
  "tags": ["healing", "chain", "ally"],
  "effectParams": {
    "baseHealing": 50,
    "chain_count": 2,
    "chain_range": 7.0
  }
}
```
**Result:** Heals caster, chains to 2 nearest allies (prioritizes lowest HP%)

---

### Lifesteal AOE
```json
{
  "tags": ["physical", "circle", "lifesteal", "enemy"],
  "effectParams": {
    "baseDamage": 30,
    "radius": 3.0,
    "lifesteal_percent": 0.2
  }
}
```
**Result:** Hit all in radius, heal 20% of TOTAL damage dealt (all targets combined)

---

### Pierce Projectile with Poison
```json
{
  "tags": ["projectile", "pierce", "poison", "poison_status", "enemy"],
  "effectParams": {
    "baseDamage": 40,
    "pierce_count": 3,
    "poison_duration": 10.0,
    "poison_damage_per_tick": 4.0
  }
}
```
**Result:** Projectile penetrates 3 targets, each gets poison damage + poison DoT

---

## Migration Quick Guide

### Step 1: Extract Keywords from Effect Text

**Before:**
```json
"effect": "Fires lightning bolts, 70 damage + chain, 10 unit range"
```

**Extract:**
- "Fires" → `projectile`
- "lightning" → `lightning`
- "70 damage" → `baseDamage: 70`
- "+ chain" → `chain`
- "10 unit range" → `attackRange: 10.0`

### Step 2: Add Tags & Parameters

**After:**
```json
{
  "tags": ["turret", "lightning", "projectile", "chain", "enemy"],
  "effectParams": {
    "baseDamage": 70,
    "attackRange": 10.0,
    "chain_count": 2,
    "chain_range": 6.0,
    "chain_falloff": 0.2
  }
}
```

### Step 3: Remove Old Effect Field

❌ Delete: `"effect": "Fires lightning bolts..."`

---

## Keyword → Tag Mapping

| Keyword in Description | Tag(s) to Add | Parameters |
|----------------------|---------------|------------|
| "chain" | `chain` | `chain_count`, `chain_range` |
| "cone" | `cone` | `cone_angle`, `cone_range` |
| "radius" / "area" | `circle` | `radius` |
| "beam" / "laser" | `beam` | `beam_range` |
| "penetrates" | `pierce` | `pierce_count` |
| "burn" / "burning" | `burn` | `burn_duration`, `burn_damage_per_tick` |
| "slow" / "slows" | `slow` | `slow_amount`, `slow_duration` |
| "freeze" / "frozen" | `freeze` | `freeze_duration` |
| "bleed" / "bleeding" | `bleed` | `bleed_duration`, `bleed_damage_per_tick` |
| "immobilize" | `root` | `root_duration` |
| "stun" | `stun` | `stun_duration` |
| "heal" / "heals" | `healing` + `ally` | `baseHealing` |
| "poison" | `poison`, `poison_status` | `poison_duration`, `poison_damage_per_tick` |
| "fire" / "flame" | `fire` | - |
| "frost" / "ice" | `frost` | - |
| "lightning" | `lightning` | - |

---

## Conflict Resolution

### Multiple Geometry Tags
```json
"tags": ["chain", "cone", "circle"]  // CONFLICT!
```
**Resolution:** Priority order: `chain` > `cone` > `circle`
- Uses `chain`, ignores others
- Logs warning

### Mutually Exclusive Statuses
```json
target.has_status("burn") + apply("freeze")
```
**Resolution:** `freeze` overrides `burn`
- Last applied wins
- Logs: "Target frozen - burn extinguished"

### Opposite Elements
`fire` vs `frost`:
- Active burn + freeze → freeze wins, removes burn
- Active freeze + burn → thaw, burn applies

---

## Default Parameters

If not specified, use these defaults:

```json
{
  // Geometry
  "chain_count": 2,
  "chain_range": 5.0,
  "chain_falloff": 0.3,
  "cone_angle": 60,
  "cone_range": 8.0,
  "radius": 3.0,
  "beam_range": 10.0,
  "beam_width": 0.5,

  // Status (Debuffs)
  "burn_duration": 5.0,
  "burn_damage_per_tick": 5.0,
  "burn_tick_rate": 1.0,
  "freeze_duration": 3.0,
  "slow_amount": 0.5,
  "slow_duration": 4.0,
  "stun_duration": 2.0,
  "bleed_duration": 6.0,
  "bleed_damage_per_tick": 3.0,
  "poison_duration": 10.0,
  "poison_damage_per_tick": 4.0,
  "poison_tick_rate": 2.0,

  // Status (Buffs)
  "haste_increase": 0.5,
  "haste_duration": 10.0,
  "empower_increase": 0.5,
  "empower_duration": 10.0,
  "shield_amount": 50.0,
  "shield_duration": 15.0,
  "regen_amount": 5.0,
  "regen_duration": 10.0,
  "regen_tick_rate": 1.0,

  // Special
  "lifesteal_percent": 0.15,
  "reflect_percent": 0.3,
  "knockback_distance": 2.0,
  "crit_chance": 0.15,
  "crit_multiplier": 2.0
}
```

---

## Context-Aware Behavior Examples

### Chain Healing (Smart Targeting)
```
Skill: "Healing Chain"
Tags: ["healing", "chain", "ally"]

Player casts:
1. Heals self for 50 HP
2. Chain to nearest ally (Turret at 40% HP)
3. Chain to next ally (Player 2 at 60% HP)

Does NOT chain to enemies!
```

### Holy Damage (Target-Dependent)
```
Skill: "Holy Blast"
Tags: ["holy", "circle", "all"]

Targets in radius:
- Undead Wraith: 150 damage (1.5x bonus)
- Wolf: 100 damage (normal)
- Player: +50 HP (heals instead of damages)
```

### Poison (Immunity)
```
Skill: "Poison Cloud"
Tags: ["poison", "poison_status", "circle"]

Targets:
- Wolf (organic): 40 damage + poison DoT ✓
- Stone Golem (construct): 0 damage (immune) ✗
- Clockwork (mechanical): 20 damage (50% reduced) ⚠
```

---

## Tag Combination Rules

### Additive Principle
All tags combine, they don't replace:
```
fire + chain = fire damage that chains
NOT: fire REPLACES chain
```

### Geometry + Status = Status on All Targets
```
cone + freeze = all in cone frozen
chain + burn = all chained targets burned
circle + slow = all in radius slowed
```

### Damage Type + Geometry = Typed Damage to All
```
fire + chain = fire damage chains
frost + cone = frost damage in cone
lightning + beam = lightning beam
```

### Status Stacking
**Additive (stacks):** `slow`, `burn`, `bleed`, `poison`, `weaken`
**Non-stacking:** `freeze`, `stun`, `shield`, `invisible`

---

## Implementation Priority (Phase 3)

**Week 1 - Foundation:**
1. Effect registry
2. Tag parser
3. Context detector
4. Debug logger

**Week 2 - Geometry:**
1. Chain calculator
2. Cone calculator
3. Circle calculator
4. Beam calculator

**Week 3 - Status:**
1. DoT system
2. CC system
3. Buff integration

**Week 4 - Integration:**
1. Turret system
2. Combat system
3. Skill system

---

## Files Reference

- **TAG-REFERENCE.md** (this file) - Quick lookup
- **TAG-DEFINITIONS-PHASE2.md** - Detailed explanations
- **TAG-COMBINATIONS-EXAMPLES.md** - Extended examples
- **MIGRATION-GUIDE.md** - Full migration steps
- **tag-inventory.json** - All current tags in codebase

---

**END OF QUICK REFERENCE**

# Tag Combination Examples & Context-Aware Behavior

**Date:** 2025-12-15
**Purpose:** Practical examples of how tags combine and behave in different contexts
**Version:** 1.0

---

## Table of Contents

1. [Basic Combinations](#1-basic-combinations)
2. [Context-Aware Behavior](#2-context-aware-behavior)
3. [Geometry + Status Combinations](#3-geometry--status-combinations)
4. [Complex Multi-Tag Examples](#4-complex-multi-tag-examples)
5. [Real-World Item Conversions](#5-real-world-item-conversions)
6. [Edge Cases & Conflicts](#6-edge-cases--conflicts)

---

## 1. Basic Combinations

### Example 1.1: Fire + Chain

**Tags:** `["fire", "chain"]`

**Behavior:**
```
Initial Target: Fire damage
Chain Target 1: Fire damage (arcs from initial target)
Chain Target 2: Fire damage (arcs from target 1)
```

**Parameters:**
```json
{
  "tags": ["fire", "chain"],
  "effectParams": {
    "baseDamage": 70,
    "chain_count": 2,
    "chain_range": 6.0,
    "chain_falloff": 0.3
  }
}
```

**Execution:**
```
Target A: 70 fire damage
Target B: 49 fire damage (70 * 0.7 falloff)
Target C: 34 fire damage (49 * 0.7 falloff)
```

**Visual:**
```
[Turret] --⚡--> [Enemy A] --⚡--> [Enemy B] --⚡--> [Enemy C]
           70      └─49─┘          └─34─┘
```

---

### Example 1.2: Fire + Chain + Burn

**Tags:** `["fire", "chain", "burn"]`

**Behavior:**
- All chained targets take fire damage
- All chained targets get burn status

**Execution:**
```
Target A: 70 fire damage + 5 damage/sec for 8 seconds
Target B: 49 fire damage + 5 damage/sec for 8 seconds
Target C: 34 fire damage + 5 damage/sec for 8 seconds
```

**Key Insight:** Status effects apply to ALL targets hit by the attack, not just primary.

---

### Example 1.3: Frost + Cone + Slow

**Tags:** `["frost", "cone", "slow"]`

**Behavior:**
- Calculate cone from turret facing direction
- All enemies in cone take frost damage
- All enemies in cone get slow status

**Parameters:**
```json
{
  "tags": ["frost", "cone", "slow"],
  "effectParams": {
    "baseDamage": 50,
    "cone_angle": 90,
    "cone_range": 8.0,
    "slow_amount": 0.5,
    "slow_duration": 4.0
  }
}
```

**Visual:**
```
         [Enemy A]
            / \
           /   \
          /     \
    [Turret] --- [Enemy B]
          \     /
           \   /
            \ /
         [Enemy C]

All three enemies: 50 frost damage + slowed by 50% for 4 seconds
```

---

### Example 1.4: Projectile + Pierce + Poison

**Tags:** `["projectile", "pierce", "poison"]`

**Behavior:**
- Spawn projectile that travels in a line
- Projectile penetrates through first target
- Each target takes poison damage

**Parameters:**
```json
{
  "tags": ["projectile", "pierce", "poison"],
  "effectParams": {
    "baseDamage": 40,
    "pierce_count": 3,
    "pierce_falloff": 0.1,
    "projectile_speed": 15.0
  }
}
```

**Execution:**
```
[Turret] --→ [Enemy A] --→ [Enemy B] --→ [Enemy C]
             40 poison    36 poison    32 poison
```

---

### Example 1.5: Circle + Fire + Burn

**Tags:** `["circle", "fire", "burn"]`

**Behavior:**
- Fire explosion at detonation point
- All targets in radius take fire damage + burn

**Parameters:**
```json
{
  "tags": ["circle", "fire", "burn"],
  "effectParams": {
    "baseDamage": 75,
    "radius": 4.0,
    "origin": "position",
    "burn_duration": 6.0,
    "burn_damage_per_tick": 8.0
  }
}
```

**Visual:**
```
        [Enemy A]

  [Enemy B]  💥  [Enemy C]
           (bomb)

        [Enemy D]

All enemies within 4 units: 75 fire damage + burn (8 dmg/sec × 6 sec)
```

---

## 2. Context-Aware Behavior

### Example 2.1: Healing + Chain (Ally Context)

**Tags:** `["healing", "chain"]`

**Context:** Healing effect defaults to ally targeting

**Behavior:**
```
Caster: Heals self for 50 HP
Chain to Ally 1 (nearest, lowest HP%): Heals for 50 HP
Chain to Ally 2 (nearest, lowest HP%): Heals for 50 HP
```

**Key:** Chain intelligently selects **allies** not enemies, prioritizes **lowest HP%**

**Example Scenario:**
```
[Healing Beacon]
     ↓ 50 HP
  [Player] (80% HP)
     ↓ chain
  [Turret 1] (40% HP) ← Prioritized (lowest HP%)
     ↓ chain
  [Turret 2] (60% HP)

Nearby [Enemy] ← NOT targeted (context = ally)
```

---

### Example 2.2: Holy Damage on Undead vs Ally

**Tags:** `["holy", "circle"]`

**Context-Aware:**
- **On Undead Enemy:** Deals 150% damage (bonus)
- **On Living Enemy:** Deals 100% damage (normal)
- **On Ally:** Heals instead of damages

**Execution:**
```
Holy explosion at position:
- [Undead Wraith]: 150 damage (100 base × 1.5 multiplier)
- [Wolf]: 100 damage (normal)
- [Player]: +50 HP healing (damage converted to heal)
```

**Implementation:**
```python
def apply_holy_damage(target, base_damage):
    if target.is_ally():
        # Holy damage heals allies
        target.heal(base_damage * 0.5)
    elif target.is_undead():
        # Bonus damage to undead
        target.take_damage(base_damage * 1.5, "holy")
    else:
        # Normal damage
        target.take_damage(base_damage, "holy")
```

---

### Example 2.3: Poison on Construct vs Organic

**Tags:** `["poison", "poison_status"]`

**Context-Aware:**
- **On Organic Enemy:** Full poison damage + poison DoT
- **On Construct/Golem:** Immune (no effect)
- **On Mechanical Enemy:** Reduced effect (50%)

**Execution:**
```
Poison bomb detonates:
- [Wolf]: 40 poison damage + 5 dmg/sec for 10 seconds
- [Stone Golem]: 0 damage (immune - construct)
- [Clockwork Turret]: 20 poison damage (50% reduced - mechanical)
```

---

### Example 2.4: Lifesteal + AOE (Context Healing)

**Tags:** `["physical", "circle", "lifesteal"]`

**Behavior:**
- Deal damage to all enemies in radius
- Heal caster based on total damage dealt

**Execution:**
```
AOE attack hits 5 enemies, each takes 30 damage:
- Total damage: 150
- Lifesteal 15%: Heal caster for 22.5 HP

Caster heals from ALL targets hit, not just primary!
```

---

### Example 2.5: Buff on Enemy (Unusual Context)

**Tags:** `["empower", "enemy"]`

**Behavior:**
- Buff applies to enemy (unusual but valid)
- **Warning Logged:** "Buff effect applied to enemy - intentional?"

**Use Case:**
- Mind control effects
- Confusion/chaos mechanics
- Feeding enemy to make them stronger (challenge mode)

---

## 3. Geometry + Status Combinations

### Example 3.1: Cone + Freeze

**Tags:** `["frost", "cone", "freeze"]`

**Behavior:**
```
[Frost Turret]
   \  |  /
    \ | /
     \|/
[E1][E2][E3]

All enemies in cone: Frost damage + Frozen for 3 seconds
```

**Tactical:** Immobilizes group of enemies approaching from one direction.

---

### Example 3.2: Chain + Lifesteal

**Tags:** `["lightning", "chain", "lifesteal"]`

**Behavior:**
```
Chain lightning hits 3 targets:
Target 1: 70 damage → Heal caster 10.5 HP
Target 2: 49 damage → Heal caster 7.35 HP
Target 3: 34 damage → Heal caster 5.1 HP
Total heal: 22.95 HP
```

**Key:** Lifesteal applies to each hit in chain.

---

### Example 3.3: Circle + Slow + Poison

**Tags:** `["poison", "circle", "slow", "poison_status"]`

**Behavior:**
- All targets in radius: Poison damage + slow + poison DoT

**Execution:**
```
Toxic cloud detonates:
All enemies in 5-unit radius:
- 60 poison damage (instant)
- Movement speed -60% for 5 seconds
- 4 poison damage/sec for 10 seconds
```

**Tactical:** Area denial - enemies can't escape cloud quickly due to slow.

---

### Example 3.4: Beam + Pierce (Redundant but Valid)

**Tags:** `["beam", "pierce"]`

**Behavior:**
- Beam naturally hits all in line
- Pierce tag is redundant but doesn't conflict

**Result:** Works as expected, no issues.

---

### Example 3.5: Circle + Chain (Conflict!)

**Tags:** `["circle", "chain"]`

**Conflict Resolution:**
- Priority: `chain` > `circle`
- **Resolution:** Use chain geometry, ignore circle
- **Warning Logged:** "Multiple geometry tags - using 'chain', ignoring 'circle'"

---

## 4. Complex Multi-Tag Examples

### Example 4.1: Ultimate Fire Chain AOE

**Tags:** `["fire", "chain", "burn", "projectile"]`

**Scenario:** Fire projectile that chains and burns

**Execution:**
```
1. Turret fires projectile
2. Projectile hits Enemy A: 80 fire damage + burn
3. Projectile chains to Enemy B: 56 fire damage + burn
4. Projectile chains to Enemy C: 39 fire damage + burn

All three enemies burning for 10 damage/sec
```

**JSON:**
```json
{
  "itemId": "inferno_chainer",
  "tags": ["turret", "fire", "chain", "burn", "projectile"],
  "effectParams": {
    "baseDamage": 80,
    "chain_count": 2,
    "chain_range": 7.0,
    "chain_falloff": 0.3,
    "burn_duration": 8.0,
    "burn_damage_per_tick": 10.0,
    "projectile_speed": 12.0
  }
}
```

---

### Example 4.2: Healing Beacon with Chain and Regeneration

**Tags:** `["healing", "circle", "regeneration", "ally"]`

**Scenario:** Beacon heals in radius and applies regen buff

**Execution:**
```
Healing beacon active:
1. All allies in 5-unit radius: +15 HP instant
2. All allies in radius: +5 HP/sec for 10 seconds (regen buff)

Every second, beacon pulses:
- Instant heal to new allies entering radius
- Regen buff refreshed to 10 seconds
```

**JSON:**
```json
{
  "itemId": "healing_beacon",
  "tags": ["device", "healing", "circle", "regeneration", "ally"],
  "effectParams": {
    "baseHealing": 15,
    "radius": 5.0,
    "regen_amount": 5.0,
    "regen_duration": 10.0,
    "pulse_rate": 1.0
  }
}
```

---

### Example 4.3: Cluster Bomb (Multiple Explosions)

**Tags:** `["explosive", "fire", "cluster", "burn"]`

**Scenario:** Bomb splits into 8 smaller explosions

**Execution:**
```
1. Main bomb detonates at position
2. Spawns 8 sub-bombs in circular pattern
3. Each sub-bomb:
   - Explodes for 15 fire damage in 1.5-unit radius
   - Applies burn to all hit

Total coverage: ~12-unit diameter
Total damage: Up to 120 (if enemy hit by all 8)
```

**JSON:**
```json
{
  "itemId": "cluster_bomb",
  "tags": ["device", "bomb", "explosive", "fire", "cluster", "burn"],
  "effectParams": {
    "cluster_count": 8,
    "cluster_radius": 4.0,
    "sub_explosion_damage": 15,
    "sub_explosion_radius": 1.5,
    "burn_duration": 5.0,
    "burn_damage_per_tick": 3.0
  }
}
```

---

### Example 4.4: Lightning Cannon with Chain and Shock

**Tags:** `["lightning", "projectile", "chain", "shock"]`

**Scenario:** Lightning bolt chains and applies shock status

**Execution:**
```
1. Fire lightning projectile
2. Hit Enemy A: 70 lightning damage + shock
3. Chain to Enemy B (within 8 units): 63 lightning damage + shock
4. Chain to Enemy C: 57 lightning damage + shock

Shock effect: 5 damage every 2 seconds, interrupts actions
```

**Note:** Lightning has synergy with chain (+20% chain range bonus)
- Base chain_range: 6.0 → Effective: 7.2 units

**JSON:**
```json
{
  "itemId": "lightning_cannon",
  "tags": ["turret", "lightning", "projectile", "chain", "shock"],
  "effectParams": {
    "baseDamage": 70,
    "chain_count": 2,
    "chain_range": 6.0,  // Auto-boosted to 7.2 for lightning
    "chain_falloff": 0.1,
    "shock_duration": 6.0,
    "shock_damage_per_tick": 5.0,
    "shock_tick_rate": 2.0
  }
}
```

---

### Example 4.5: Vampiric Whirlwind (Melee AOE with Lifesteal)

**Tags:** `["physical", "slashing", "circle", "lifesteal"]`

**Scenario:** Player skill - spin attack that heals

**Execution:**
```
Player activates whirlwind:
1. Hit all enemies in 3-unit radius
2. Each enemy takes slashing damage
3. Player heals 20% of total damage dealt

Example:
- 4 enemies hit, each takes 50 damage
- Total: 200 damage
- Lifesteal: 40 HP healed
```

**Tactical:** Sustain in melee combat against multiple enemies.

---

## 5. Real-World Item Conversions

### Example 5.1: Basic Arrow Turret (Current)

**Current JSON:**
```json
{
  "itemId": "basic_arrow_turret",
  "effect": "Fires arrows at enemies, 20 damage, 5 unit range",
  "tags": ["device", "turret", "basic", "projectile"]
}
```

**Converted JSON:**
```json
{
  "itemId": "basic_arrow_turret",
  "tags": ["device", "turret", "basic", "projectile", "single_target", "physical", "piercing"],
  "effectParams": {
    "baseDamage": 20,
    "attackRange": 5.0,
    "attackSpeed": 1.0,
    "projectile_speed": 15.0
  }
}
```

**New Behavior:**
- Projectile attack (visually travels)
- Single target (default)
- Physical piercing damage
- All from tags!

---

### Example 5.2: Lightning Cannon (Current)

**Current JSON:**
```json
{
  "itemId": "lightning_cannon",
  "effect": "Fires lightning bolts, 70 damage + chain, 10 unit range",
  "tags": ["device", "turret", "lightning", "advanced"]
}
```

**Converted JSON:**
```json
{
  "itemId": "lightning_cannon",
  "tags": ["device", "turret", "lightning", "advanced", "projectile", "chain"],
  "effectParams": {
    "baseDamage": 70,
    "attackRange": 10.0,
    "attackSpeed": 1.2,
    "chain_count": 2,
    "chain_range": 6.0,  // Boosted to 7.2 for lightning
    "chain_falloff": 0.2
  }
}
```

**New Behavior:**
- Lightning projectile
- Chains to 2 additional targets
- Automatic chain range bonus (lightning synergy)
- "chain" tag fully implemented!

---

### Example 5.3: Flamethrower Turret (Current)

**Current JSON:**
```json
{
  "itemId": "flamethrower_turret",
  "effect": "Sweeps cone of fire, 60 damage + lingering burn",
  "tags": ["device", "turret", "fire", "area"]
}
```

**Converted JSON:**
```json
{
  "itemId": "flamethrower_turret",
  "tags": ["device", "turret", "fire", "cone", "burn"],
  "effectParams": {
    "baseDamage": 60,
    "attackRange": 8.0,
    "attackSpeed": 0.8,
    "cone_angle": 60,
    "cone_range": 8.0,
    "burn_duration": 6.0,
    "burn_damage_per_tick": 8.0,
    "burn_tick_rate": 1.0
  }
}
```

**New Behavior:**
- Cone geometry (from tag!)
- All targets in cone take fire damage
- All targets get burn status
- "cone" and "burn" fully implemented!

---

### Example 5.4: Spike Trap (Current)

**Current JSON:**
```json
{
  "itemId": "spike_trap",
  "effect": "Triggers on contact, 30 damage + bleed",
  "tags": ["device", "trap", "physical", "basic"]
}
```

**Converted JSON:**
```json
{
  "itemId": "spike_trap",
  "tags": ["device", "trap", "physical", "slashing", "bleed", "on_contact", "single_target"],
  "effectParams": {
    "baseDamage": 30,
    "trigger_type": "contact",
    "bleed_duration": 6.0,
    "bleed_damage_per_tick": 5.0,
    "bleed_tick_rate": 1.0
  }
}
```

**New Behavior:**
- Triggers on contact (from tag)
- Slashing physical damage
- Applies bleed status
- "bleed" fully implemented!

---

### Example 5.5: Frost Mine (Current)

**Current JSON:**
```json
{
  "itemId": "frost_mine",
  "effect": "Triggers on proximity, 50 damage + slow",
  "tags": ["device", "trap", "frost", "elemental"]
}
```

**Converted JSON:**
```json
{
  "itemId": "frost_mine",
  "tags": ["device", "trap", "frost", "elemental", "circle", "slow", "on_proximity"],
  "effectParams": {
    "baseDamage": 50,
    "trigger_type": "proximity",
    "trigger_radius": 2.0,
    "explosion_radius": 3.0,
    "slow_amount": 0.6,
    "slow_duration": 5.0
  }
}
```

**New Behavior:**
- Proximity trigger
- Circle AOE explosion
- Frost damage to all in radius
- Slow effect to all in radius

---

## 6. Edge Cases & Conflicts

### Edge Case 6.1: Healing Damage to Enemy

**Tags:** `["healing", "enemy"]`

**Behavior:**
- Technically valid (healing enemy)
- **Warning Logged:** "Healing effect applied to enemy - is this intentional?"
- Could be used for:
  - Mind control ("help the enemy to control it")
  - Challenge modes (heal boss periodically)
  - Confusion effects

---

### Edge Case 6.2: Damage to Self

**Tags:** `["fire", "self"]`

**Behavior:**
- Damages the caster
- Used for:
  - Berserker skills (hurt self for power)
  - Blood magic
  - Risk/reward mechanics

---

### Edge Case 6.3: Chain with No Additional Targets

**Tags:** `["fire", "chain"]`

**Scenario:** Only one enemy in range

**Behavior:**
```
Hit Enemy A: 70 fire damage
Attempt chain: No valid targets within range
Result: Acts like single-target attack
```

**No Error:** Graceful degradation to single target.

---

### Edge Case 6.4: AOE with Max Targets = 1

**Tags:** `["circle"]`
**Params:** `max_targets: 1`

**Behavior:**
- Calculate circle normally
- Only hit nearest target in radius
- Effectively single-target with range check

**Use Case:** "AOE" visualization but single-target execution.

---

### Edge Case 6.5: Freeze + Burn Simultaneously

**Tags:** Apply freeze, then apply burn

**Conflict Resolution:**
```python
if target.has_status("freeze") and applying_status == "burn":
    # Thaw target
    target.remove_status("freeze")
    target.apply_status("burn")
    log_info("Target thawed by fire - burn applied")

elif target.has_status("burn") and applying_status == "freeze":
    # Freeze overrides burn
    target.remove_status("burn")
    target.apply_status("freeze")
    log_info("Target frozen - burn extinguished")
```

**Rule:** Freeze and burn are mutually exclusive, last applied wins.

---

### Edge Case 6.6: Pierce + Single Enemy

**Tags:** `["projectile", "pierce"]`

**Scenario:** Only one enemy in projectile path

**Behavior:**
- Projectile hits enemy
- Continues past enemy (no more targets)
- Dissipates at max range

**Result:** Works as expected, no issues.

---

### Edge Case 6.7: Lifesteal + Zero Damage

**Tags:** `["physical", "lifesteal"]`

**Scenario:** Target has 100% damage reduction

**Behavior:**
```
Damage dealt: 0 (blocked)
Lifesteal: 0 HP (15% of 0 damage)
```

**Rule:** Lifesteal based on actual damage dealt, not pre-mitigation.

---

### Edge Case 6.8: NPC with Combat Tags

**Scenario:** NPC JSON has `["chain", "fire"]` tags

**Behavior:**
- NPC is non-combat entity
- Tags present but context invalid (NPC has no attack)
- **Debug Log:** "NPC 'blacksmith' has combat tags ['chain', 'fire'] - no attack system, tags ignored"
- **No Error:** Silent ignore (expected behavior)

**This is the "purposeful failure" mentioned - tags do nothing but don't crash.**

---

### Edge Case 6.9: Multiple Geometry Tags

**Tags:** `["chain", "cone", "circle"]`

**Conflict Resolution:**
- Priority: `chain` > `cone` > `circle`
- **Warning:** "Multiple geometry tags detected: ['chain', 'cone', 'circle']"
- **Resolution:** "Using 'chain' (highest priority), ignoring ['cone', 'circle']"

---

### Edge Case 6.10: Empty Tags Array

**Tags:** `[]`

**Behavior:**
- No tags provided
- **Default Behavior:**
  - Geometry: `single_target`
  - Context: Infer from item type (turret → enemy, beacon → ally)
  - Damage: None (item must specify baseDamage in params)

**Result:** Minimal valid effect (single-target, no special behavior).

---

## 7. Summary & Design Principles

### Principle 1: Additive Behavior
**All tags are additive** - they combine, not replace.
- `fire` + `chain` = Fire damage that chains
- Not: `fire` REPLACES `chain`

### Principle 2: Context-Aware
**Tags automatically adjust to context:**
- `chain` + damage = chain to enemies
- `chain` + healing = chain to allies

### Principle 3: Graceful Degradation
**Missing targets don't cause errors:**
- Chain with no nearby enemies = single target
- AOE with no enemies in radius = no hits, no crash

### Principle 4: Conflict Resolution
**Clear priority for conflicts:**
- Geometry: chain > cone > circle > beam > single
- Status: Last applied wins for mutually exclusive statuses
- Log warnings for unusual combinations

### Principle 5: Debug Transparency
**Comprehensive logging:**
- Tag conflicts → Warning
- Unusual contexts (heal enemy) → Info
- Silent failures (NPC with combat tags) → Debug log
- Clear messages for developers and debugging

---

**END OF COMBINATION EXAMPLES**

**Next:** Begin implementation or proceed with migration guide?

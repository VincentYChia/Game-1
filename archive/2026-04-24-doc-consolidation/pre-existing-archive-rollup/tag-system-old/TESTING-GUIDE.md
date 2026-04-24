# Tag System Testing Guide

**Purpose:** Comprehensive testing plan for validating tag-to-effects system
**Status:** Ready for testing
**Date:** 2025-12-16

---

## Overview

This guide provides a systematic approach to testing all aspects of the tag-to-effects system, from individual tags to complex combinations. Use the training dummy system for detailed feedback.

---

## Test Environment Setup

### 1. Enable Debug Logging

```bash
export TAG_DEBUG_LEVEL=DEBUG
```

This will show detailed logs for:
- Tag parsing
- Geometry calculations
- Target finding
- Status effect application
- Damage/healing

### 2. Place Training Dummy

```python
from systems.training_dummy import create_training_dummy_entity
from data.models import Position

# Place dummy at a visible location
dummy_pos = Position(50, 50)
dummy = create_training_dummy_entity(dummy_pos)

# Add to world
placed_entities.append(dummy)
```

Or craft/place "Training Dummy" from engineering station (tier 1).

### 3. Adjust Turret Damage

For testing without one-shots, reduce `baseDamage` in turret `effect_params`:

```python
# Example: Fire Arrow Turret with reduced damage for testing
turret = PlacedEntity(
    item_id="fire_arrow_turret",
    tags=["fire", "single_target", "burn"],
    effect_params={
        "baseDamage": 15,  # Reduced from 35
        "burn_duration": 5.0,
        "burn_damage_per_second": 3.0  # Reduced from 5.0
    }
)
```

---

## Testing Categories

### Category 1: Geometry Types

Test each geometry individually to verify targeting works correctly.

#### Test 1.1: Single Target ✓
**Tags:** `["physical", "single_target"]`
**Expected:** Hits only primary target
**Params:**
```python
{
    "baseDamage": 50
}
```
**Validation:**
- ✓ Only 1 target hit
- ✓ Damage matches baseDamage
- ✓ No falloff

#### Test 1.2: Chain ✓
**Tags:** `["lightning", "chain"]`
**Expected:** Arcs to nearby enemies with falloff
**Params:**
```python
{
    "baseDamage": 70,
    "chain_count": 2,      # Hits 3 total
    "chain_range": 5.0,
    "chain_falloff": 0.3   # 30% less per jump
}
```
**Validation:**
- ✓ Primary target: 70 damage
- ✓ Chain 1: ~49 damage (70 × 0.7)
- ✓ Chain 2: ~34 damage (49 × 0.7)
- ✓ Total 3 targets if available
- ✓ Chain range respected

**Synergy Bonus:** `lightning + chain` gives +20% chain range

#### Test 1.3: Cone ✓
**Tags:** `["fire", "cone"]`
**Expected:** Hits all enemies in frontal cone
**Params:**
```python
{
    "baseDamage": 50,
    "cone_angle": 60.0,   # 60 degree cone
    "cone_range": 8.0
}
```
**Validation:**
- ✓ Hits all enemies in 60° arc
- ✓ Respects 8 unit range
- ✓ No damage falloff
- ✓ Direction based on target

**Test Setup:**
- Place multiple training dummies in arc pattern
- Fire should hit all in cone

#### Test 1.4: Circle/AOE ✓
**Tags:** `["fire", "circle"]`
**Expected:** Hits all enemies in radius
**Params:**
```python
{
    "baseDamage": 60,
    "circle_radius": 4.0,
    "circle_max_targets": 10
}
```
**Validation:**
- ✓ Hits all within 4 units
- ✓ Respects max targets limit
- ✓ No damage falloff
- ✓ Range from center/target

#### Test 1.5: Beam ✓
**Tags:** `["energy", "beam"]`
**Expected:** Line projectile with pierce
**Params:**
```python
{
    "baseDamage": 80,
    "beam_range": 12.0,
    "beam_width": 1.0,
    "pierce_count": 3
}
```
**Validation:**
- ✓ Hits enemies in line
- ✓ Respects beam width
- ✓ Pierces up to 3 enemies
- ✓ Damage consistent (no built-in falloff)

#### Test 1.6: Pierce ✓
**Tags:** `["physical", "pierce"]`
**Expected:** Penetrating projectile with falloff
**Params:**
```python
{
    "baseDamage": 70,
    "pierce_count": 4,
    "pierce_falloff": 0.1   # 10% less per hit
}
```
**Validation:**
- ✓ Hit 1: 70 damage
- ✓ Hit 2: 63 damage (70 × 0.9)
- ✓ Hit 3: 57 damage (63 × 0.9)
- ✓ Hit 4: 51 damage (57 × 0.9)
- ✓ Stops after pierce_count hits

---

### Category 2: Damage Types

Test each damage type for proper application and context behavior.

#### Test 2.1: Physical ✓
**Tags:** `["physical", "single_target"]`
**Expected:** Standard physical damage
**Context Tests:**
- ✓ vs Enemy: Normal damage
- ✓ vs Ally: Should not convert
- ✓ vs Construct: Normal damage

#### Test 2.2: Fire ✓
**Tags:** `["fire", "single_target"]`
**Expected:** Fire damage
**Context Tests:**
- ✓ Auto-apply burn chance (10% default)
- ✓ Synergy with burn tag

#### Test 2.3: Frost ✓
**Tags:** `["frost", "single_target"]`
**Expected:** Frost damage
**Context Tests:**
- ✓ Auto-apply freeze chance (if configured)
- ✓ Synergy with slow tag

#### Test 2.4: Lightning ✓
**Tags:** `["lightning", "single_target"]`
**Expected:** Lightning damage
**Context Tests:**
- ✓ Synergy with chain (+20% range)
- ✓ Auto-apply shock chance

#### Test 2.5: Holy ✓
**Tags:** `["holy", "single_target"]`
**Expected:** Holy damage with context awareness
**Context Tests:**
- ✓ vs Undead: 150% damage (1.5x multiplier)
- ✓ vs Ally: Converts to healing
- ✓ vs Enemy (non-undead): Normal damage

**Critical Test:**
```python
# Holy damage on ally should heal, not damage!
tags = ["holy", "ally"]
params = {"baseDamage": 50}
# Expected: 50 HP healing, not damage
```

#### Test 2.6: Poison ✓
**Tags:** `["poison", "single_target"]`
**Expected:** Poison damage
**Context Tests:**
- ✓ vs Construct: Reduced or immune
- ✓ vs Undead: Immune
- ✓ vs Organic: Full damage

#### Test 2.7: Shadow/Void ✓
**Tags:** `["shadow", "single_target"]`
**Expected:** Shadow damage
**Context Tests:**
- ✓ vs constructs: Bonus damage
- ✓ Dark-themed effects

---

### Category 3: Status Effects

Test each status effect for proper application, stacking, and duration.

#### Test 3.1: Burn (DoT) ✓
**Tags:** `["fire", "burn"]`
**Expected:** Fire DoT that stacks
**Params:**
```python
{
    "baseDamage": 50,
    "burn_duration": 5.0,
    "burn_damage_per_second": 10.0
}
```
**Validation:**
- ✓ Applied after damage
- ✓ Ticks every second
- ✓ Deals 10 damage per second
- ✓ Lasts 5 seconds (50 total damage)
- ✓ Stacks up to 3 times
- ✓ Visual effect appears

**Stacking Test:**
- Hit 3 times with burn
- Expected: 30 DPS (10 × 3 stacks)

#### Test 3.2: Bleed (DoT) ✓
**Tags:** `["physical", "bleed"]`
**Expected:** Physical DoT that stacks
**Params:**
```python
{
    "baseDamage": 40,
    "bleed_duration": 6.0,
    "bleed_damage_per_second": 5.0
}
```
**Validation:**
- ✓ Applied after damage
- ✓ Stacks up to 5 times
- ✓ Ticks every second
- ✓ Visual effect (blood)

#### Test 3.3: Poison (DoT) ✓
**Tags:** `["poison", "poison_status"]`
**Expected:** Poison DoT with exponential stacking
**Params:**
```python
{
    "baseDamage": 20,
    "poison_duration": 10.0,
    "poison_damage_per_second": 3.0
}
```
**Validation:**
- ✓ Applied after damage
- ✓ Stacks up to 10 times
- ✓ Scales exponentially (stacks^1.2)
- ✓ Stack 1: 3 DPS
- ✓ Stack 5: ~9 DPS
- ✓ Stack 10: ~19 DPS
- ✓ Immunity: construct, undead

#### Test 3.4: Freeze (CC) ✓
**Tags:** `["frost", "freeze"]`
**Expected:** Complete immobilization
**Params:**
```python
{
    "baseDamage": 30,
    "freeze_duration": 3.0
}
```
**Validation:**
- ✓ Prevents movement
- ✓ Prevents attacks
- ✓ Speed set to 0
- ✓ Visual effect (ice)
- ✓ Mutual exclusion: removes burn

**Mutual Exclusion Test:**
- Apply burn, then freeze
- Expected: Burn removed, freeze applied
- Apply freeze, then burn
- Expected: Freeze removed, burn applied

#### Test 3.5: Slow (CC) ✓
**Tags:** `["frost", "slow"]`
**Expected:** Movement speed reduction
**Params:**
```python
{
    "baseDamage": 25,
    "slow_duration": 6.0,
    "slow_percent": 0.5  # 50% slow
}
```
**Validation:**
- ✓ Reduces movement speed by 50%
- ✓ Does not prevent actions
- ✓ Visual effect
- ✓ Restores speed on removal

#### Test 3.6: Stun (CC) ✓
**Tags:** `["physical", "stun"]`
**Expected:** Prevents all actions
**Params:**
```python
{
    "baseDamage": 40,
    "stun_duration": 2.0
}
```
**Validation:**
- ✓ Prevents attacks
- ✓ Prevents movement
- ✓ Prevents ability use
- ✓ Visual effect (stars)

#### Test 3.7: Root (CC) ✓
**Tags:** `["nature", "root"]`
**Expected:** Prevents movement only
**Params:**
```python
{
    "baseDamage": 30,
    "root_duration": 4.0
}
```
**Validation:**
- ✓ Speed set to 0
- ✓ Can still attack
- ✓ Can still use abilities
- ✓ Visual effect (vines)

#### Test 3.8: Regeneration (Buff) ✓
**Tags:** `["healing", "ally", "regeneration"]`
**Expected:** Heal over time
**Params:**
```python
{
    "baseHealing": 50,        # Instant
    "regen_heal_per_second": 10.0,
    "regen_duration": 5.0
}
```
**Validation:**
- ✓ Instant 50 HP
- ✓ Then 10 HP/sec for 5 sec
- ✓ Total: 100 HP
- ✓ Stacks up to 3 times
- ✓ Visual effect

#### Test 3.9: Shield (Buff) ✓
**Tags:** `["ally", "shield"]`
**Expected:** Damage absorption
**Params:**
```python
{
    "shield_amount": 100.0,
    "shield_duration": 10.0
}
```
**Validation:**
- ✓ Adds 100 shield HP
- ✓ Absorbs damage before HP
- ✓ Expires after duration
- ✓ Visual effect

#### Test 3.10: Haste (Buff) ✓
**Tags:** `["ally", "haste"]`
**Expected:** Speed increase
**Params:**
```python
{
    "haste_speed_bonus": 0.3,  # 30% faster
    "haste_duration": 8.0
}
```
**Validation:**
- ✓ Movement speed +30%
- ✓ Attack speed +30%
- ✓ Visual effect
- ✓ Speed restored on removal

---

### Category 4: Tag Combinations

Test complex tag combinations to verify additive behavior.

#### Test 4.1: Fire + Chain + Burn ✓
**Tags:** `["fire", "chain", "burn"]`
**Expected:** Chain fire damage with burn on all targets
**Params:**
```python
{
    "baseDamage": 50,
    "chain_count": 2,
    "chain_range": 5.0,
    "burn_duration": 5.0,
    "burn_damage_per_second": 8.0
}
```
**Validation:**
- ✓ Chains to 3 total targets
- ✓ All take fire damage
- ✓ All get burn status
- ✓ Damage falls off per chain
- ✓ Burn damage constant

**Expected Damage:**
- Target 1: 50 fire + 40 burn = 90 total
- Target 2: 35 fire + 40 burn = 75 total
- Target 3: 25 fire + 40 burn = 65 total

#### Test 4.2: Lightning + Chain + Shock ✓
**Tags:** `["lightning", "chain", "shock"]`
**Expected:** Chain lightning with stuns
**Params:**
```python
{
    "baseDamage": 70,
    "chain_count": 3,
    "chain_range": 6.0,  # Base 5.0 + 20% synergy = 6.0
    "shock_duration": 2.0
}
```
**Validation:**
- ✓ Chains to 4 total targets
- ✓ Synergy bonus: +20% chain range
- ✓ All targets stunned 2 sec
- ✓ Damage falls off

#### Test 4.3: Frost + Circle + Freeze ✓
**Tags:** `["frost", "circle", "freeze"]`
**Expected:** AOE freeze
**Params:**
```python
{
    "baseDamage": 40,
    "circle_radius": 5.0,
    "freeze_duration": 3.0
}
```
**Validation:**
- ✓ Hits all in radius
- ✓ All frozen 3 seconds
- ✓ Removes burn from targets

#### Test 4.4: Holy + Circle + Ally ✓
**Tags:** `["holy", "circle", "ally"]`
**Expected:** AOE healing
**Params:**
```python
{
    "baseDamage": 60,  # Converts to healing
    "circle_radius": 6.0
}
```
**Validation:**
- ✓ Finds allies in radius
- ✓ Heals instead of damages
- ✓ 60 HP per ally

#### Test 4.5: Poison + Circle + Poison_Status + Slow ✓
**Tags:** `["poison", "circle", "poison_status", "slow"]`
**Expected:** Poison cloud with slow
**Params:**
```python
{
    "baseDamage": 30,
    "circle_radius": 4.0,
    "poison_duration": 12.0,
    "poison_damage_per_second": 4.0,
    "slow_duration": 8.0,
    "slow_percent": 0.4
}
```
**Validation:**
- ✓ Hits all in radius
- ✓ Applies poison (4 DPS × 12 sec = 48 damage)
- ✓ Applies slow (40% for 8 sec)
- ✓ Constructs/undead immune to poison

#### Test 4.6: Physical + Pierce + Bleed ✓
**Tags:** `["physical", "pierce", "bleed"]`
**Expected:** Piercing attack that bleeds all hit
**Params:**
```python
{
    "baseDamage": 60,
    "pierce_count": 3,
    "pierce_falloff": 0.15,
    "bleed_duration": 6.0,
    "bleed_damage_per_second": 5.0
}
```
**Validation:**
- ✓ Pierces 3 enemies
- ✓ Damage: 60, 51, 43
- ✓ All bleed for 30 total damage
- ✓ Total damage per target: 90, 81, 73

---

### Category 5: Context Awareness

Test that tags behave differently based on target type.

#### Test 5.1: Holy vs Different Targets ✓
**Setup:** Same attack, different targets

**Test A: Holy vs Undead**
```python
tags = ["holy", "single_target"]
params = {"baseDamage": 100}
target = undead_skeleton  # category = "undead"
# Expected: 150 damage (1.5x multiplier)
```

**Test B: Holy vs Ally**
```python
tags = ["holy", "single_target"]
params = {"baseDamage": 100}
target = ally_player  # category = "player"
# Expected: 100 healing (converted)
```

**Test C: Holy vs Beast**
```python
tags = ["holy", "single_target"]
params = {"baseDamage": 100}
target = wolf  # category = "beast"
# Expected: 100 damage (normal)
```

#### Test 5.2: Poison Immunity ✓
**Setup:** Poison against different categories

**Test A: vs Beast (Vulnerable)**
```python
tags = ["poison", "poison_status"]
target = wolf  # category = "beast"
# Expected: Full poison damage and status
```

**Test B: vs Construct (Immune)**
```python
tags = ["poison", "poison_status"]
target = golem  # category = "construct"
# Expected: Damage reduced/none, status immune
```

**Test C: vs Undead (Immune)**
```python
tags = ["poison", "poison_status"]
target = skeleton  # category = "undead"
# Expected: Poison status not applied
```

---

### Category 6: Special Mechanics

Test special tag mechanics.

#### Test 6.1: Lifesteal ✓
**Tags:** `["physical", "single_target", "lifesteal"]`
**Expected:** Damage heals caster
**Params:**
```python
{
    "baseDamage": 100,
    "lifesteal_percent": 0.2  # 20%
}
```
**Validation:**
- ✓ Deals 100 damage
- ✓ Heals caster 20 HP (100 × 0.2)

#### Test 6.2: Knockback ✓
**Tags:** `["physical", "single_target", "knockback"]`
**Expected:** Pushes target away
**Params:**
```python
{
    "baseDamage": 50,
    "knockback_distance": 3.0
}
```
**Validation:**
- ✓ Deals damage
- ✓ Pushes target 3 units
- ✓ (Currently logged, physics not implemented)

#### Test 6.3: Vampiric (Alias) ✓
**Tags:** `["shadow", "vampiric"]`
**Expected:** Same as lifesteal
**Validation:**
- ✓ Alias resolves to lifesteal
- ✓ Behavior identical

---

### Category 7: Edge Cases

Test boundary conditions and error handling.

#### Test 7.1: No Targets Available ✓
**Setup:** Chain with no nearby enemies
**Expected:** Falls back to single-target
**Validation:**
- ✓ Hits primary target only
- ✓ Warning logged
- ✓ No crash

#### Test 7.2: Conflicting Geometry ✓
**Tags:** `["chain", "cone", "circle"]`
**Expected:** Priority resolution (chain wins)
**Validation:**
- ✓ Only chain geometry used
- ✓ Other geometries ignored
- ✓ Warning in logs

#### Test 7.3: Missing Parameters ✓
**Tags:** `["chain"]`
**Params:** `{}` (empty)
**Expected:** Uses defaults
**Validation:**
- ✓ chain_count = 2 (default)
- ✓ chain_range = 5.0 (default)
- ✓ chain_falloff = 0.3 (default)

#### Test 7.4: Invalid Tags ✓
**Tags:** `["invalid_tag_xyz"]`
**Expected:** Graceful handling
**Validation:**
- ✓ Warning logged
- ✓ Tag ignored
- ✓ No crash

#### Test 7.5: Zero Damage ✓
**Tags:** `["fire", "burn"]`
**Params:** `{"baseDamage": 0}`
**Expected:** Status applied, no damage
**Validation:**
- ✓ No damage dealt
- ✓ Burn still applied
- ✓ Burn ticks normally

---

## Recommended Test Scenarios

### Scenario 1: Flamethrower Gauntlet
**Objective:** Test cone geometry + fire + burn

**Setup:**
1. Place 5 training dummies in arc (60° cone)
2. Place flamethrower turret
3. Configure with reduced damage

**Expected Results:**
- All dummies in cone hit
- All take fire damage
- All get burn status
- Burn ticks independently
- Total damage = initial + burn DoT

### Scenario 2: Chain Lightning Storm
**Objective:** Test chain geometry + lightning + synergy

**Setup:**
1. Place 4 training dummies close together
2. Place lightning cannon
3. Enable debug logging

**Expected Results:**
- Chain jumps to all 4 (if in range)
- Synergy bonus: +20% chain range
- Damage falls off per jump
- Debug shows chain calculations

### Scenario 3: Poison Gas Trap
**Objective:** Test circle + poison + immunity

**Setup:**
1. Place mixed targets: beasts, constructs, undead
2. Trigger poison trap
3. Observe different reactions

**Expected Results:**
- Beasts: Full poison + status
- Constructs: Reduced/no poison status
- Undead: Immune to poison status
- All take initial damage

### Scenario 4: Holy Healer
**Objective:** Test damage-to-healing conversion

**Setup:**
1. Damage self or ally
2. Use holy + ally tags
3. Verify healing

**Expected Results:**
- No damage dealt
- HP restored instead
- Healing equals "damage" value

### Scenario 5: Status Effect Stacking
**Objective:** Test stacking limits

**Setup:**
1. Place training dummy
2. Hit repeatedly with burn
3. Observe stack count

**Expected Results:**
- Stack 1: 5 DPS
- Stack 2: 10 DPS
- Stack 3: 15 DPS
- Stack 4+: Still 15 DPS (max 3)

---

## Performance Testing

### Test P1: Single Effect
**Measure:** Time to execute single-target effect
**Target:** < 0.5ms
**Method:**
```python
import time
start = time.perf_counter()
executor.execute_effect(...)
end = time.perf_counter()
print(f"Execution time: {(end-start)*1000:.2f}ms")
```

### Test P2: Chain Effect (10 targets)
**Measure:** Time to execute chain with 10 targets
**Target:** < 2ms
**Method:** Same as P1, with 10 available entities

### Test P3: AOE Effect (20 targets)
**Measure:** Time to execute circle with 20 targets
**Target:** < 3ms

### Test P4: Status Updates (100 entities)
**Measure:** Time to update 100 entities with status effects
**Target:** < 10ms total (< 0.1ms per entity)

---

## Regression Testing

After any code changes, run these quick tests:

### Quick Smoke Test (5 minutes)
1. ✓ Fire arrow turret hits enemy
2. ✓ Chain lightning chains to 3 targets
3. ✓ Burn DoT ticks correctly
4. ✓ Freeze immobilizes enemy
5. ✓ Training dummy shows detailed report

### Full Test Suite (30 minutes)
1. All geometry types (6 tests)
2. All damage types (7 tests)
3. All status effects (10 tests)
4. Key combinations (6 tests)
5. Context awareness (3 tests)
6. Edge cases (5 tests)

**Total:** 37 individual tests

---

## Bug Reporting Template

When reporting issues:

```
**Test:** [Test name/number]
**Tags:** [Tags used]
**Params:** [Parameters]
**Expected:** [What should happen]
**Actual:** [What happened]
**Debug Output:** [Paste relevant logs]
**Reproduce:** [Steps to reproduce]
```

---

## Success Criteria

System passes testing if:

✅ All geometry types work as documented
✅ All damage types apply correctly
✅ All status effects function properly
✅ Context awareness works (holy vs undead, poison immunity, etc.)
✅ Tag combinations are additive (all effects happen)
✅ Performance targets met (< 1ms average)
✅ No crashes or unhandled exceptions
✅ Debug output is clear and helpful
✅ Training dummy reports are accurate

---

## Known Limitations (Expected Behavior)

1. **Knockback/Pull:** Physics not implemented (logged only)
2. **VFX:** Visual effects not connected yet
3. **Skill Integration:** Skills use buff system (not tag system yet)
4. **Weapon Tags:** Weapons don't support tags yet
5. **Abilities:** Enemy abilities not implemented

These are planned features, not bugs.

---

## Next Steps After Testing

1. **Balance Pass:** Adjust damage values based on testing
2. **Skill Integration:** Add tag-based attack skills
3. **Combat Integration:** Player attacks use tag system
4. **VFX Integration:** Connect visual effects
5. **Enemy Abilities:** Add hostile ability system

---

**END OF TESTING GUIDE**

For questions or issues, see `docs/tag-system/README.md` or `IMPLEMENTATION-STATUS.md`.

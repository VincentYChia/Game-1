# Critical Skill System Bugs: Analysis and Root Cause

**Date**: 2025-12-23
**Status**: 🔴 CRITICAL - Multiple skill types completely non-functional

---

## User Report

**Power Strike Issue**:
- Skill shows: "+150% damage for 0s"
- Expected: Massive damage boost on next attack
- Actual: No damage increase at all

---

## Root Cause Analysis

### Bug #1: Hardcoded Magnitude Values Are WRONG

**Location**: `entities/components/skill_manager.py:193-198`

**The Problem**:
```python
magnitude_values = {
    'minor': {'empower': 0.25, ...},      # 25% ❌ Should be 50% (0.5)
    'moderate': {'empower': 0.50, ...},   # 50% ❌ Should be 100% (1.0)
    'major': {'empower': 1.00, ...},      # 100% ❌ Should be 200% (2.0)
    'extreme': {'empower': 1.50, ...}     # 150% ❌ Should be 400% (4.0)
}
```

**Source of Truth**: `Skills/skills-base-effects-1.JSON:14-19`
```json
"empower": {
  "magnitudeValues": {
    "minor": 0.5,      // ✅ 50%
    "moderate": 1.0,   // ✅ 100%
    "major": 2.0,      // ✅ 200%
    "extreme": 4.0     // ✅ 400%
  }
}
```

**Impact**: ALL empower skills (and quicken, pierce, etc.) deal far less bonus than designed!

---

### Bug #2: "Instant" Duration = 0 Seconds (Expires Immediately)

**Location**: `Definitions.JSON/skills-translation-table.JSON:9-12`

```json
"instant": {
  "seconds": 0,  // ❌ WRONG for buffs!
  "description": "No duration - effect applies once immediately"
}
```

**The Flow**:
1. User activates Power Strike
2. Skill creates buff with duration=0, duration_remaining=0
3. Buff is added to character.buffs list
4. **Next frame** (before attack): `buffs.update(dt)` removes all buffs with duration_remaining <= 0
5. Buff is GONE before the attack happens!
6. Attack does normal damage (no buff applied)

**What Should Happen**:
For "instant" skills that create buffs, the buff should persist until consumed (next relevant action), NOT expire by time.

---

### Bug #3: No Consume-on-Use Mechanism

**Current System**: Buffs only expire by time
**Problem**: "Instant" buffs expire before they can be used

**What's Needed**:
- Flag: `consume_on_use=True` for instant buffs
- Logic: When buffed action is performed (attack, gather, craft), remove the buff
- Duration: Set to high value (60s) as fallback, but consume on first use

---

## Affected Skills (21 Total)

### Combat Skills (BROKEN)
1. **Power Strike** (combat_strike) - empower/damage/extreme
   - Should: +400% damage on next hit
   - Actually: +0% (buff expires immediately)

2. **Whirlwind Strike** (whirlwind_strike) - devastate/damage/moderate
   - Should: Hit 5-tile radius on next attack
   - Actually: Normal single-target attack

3. **Absolute Destruction** - devastate/damage/extreme
   - Should: Massive AoE on next attack
   - Actually: Normal attack

### Gathering Skills (BROKEN)
4. **Chain Harvest** (chain_harvest) - devastate/mining/moderate
   - Should: Mine 5-tile radius
   - Actually: Mines single node

### Crafting Skills (BROKEN)
5. **Smith's Focus** - quicken/smithing/major
   - Should: Extra time for next smithing minigame
   - Actually: No benefit

6. **Alchemist's Insight** - quicken/alchemy/moderate + empower/alchemy/minor
   - Should: Time boost + quality boost for next craft
   - Actually: No benefit

7. **Engineer's Precision** - quicken/engineering/major + empower/engineering/minor
   - Should: Time + quality for next engineering craft
   - Actually: No benefit

8. **Refiner's Touch** - quicken/refining/major + elevate/refining/minor
   - Should: Time + rarity boost for next refining
   - Actually: No benefit

9. **Enchanter's Grace** - pierce/enchanting/major + elevate/enchanting/minor
   - Should: Crit + rarity for next enchanting
   - Actually: No benefit

10. **Master Craftsman** - empower/smithing/major + elevate/smithing/moderate
    - Should: Massive stat + rarity boost for next smith
    - Actually: No benefit

### Restoration Skills (WORK CORRECTLY ✅)
These don't create buffs - they apply instantly:
- **Quick Repair** - restore/durability
- **Field Medic** - restore/defense (HP)
- **Second Wind** - restore/defense (HP)

---

## Data Comparison

### Power Strike Example

**JSON Definition**:
```json
{
  "skillId": "combat_strike",
  "name": "Power Strike",
  "effect": {
    "type": "empower",
    "category": "damage",
    "magnitude": "extreme",  // Should be 4.0x (400%)
    "duration": "instant"     // Should persist until next hit
  }
}
```

**What Code Calculates**:
```python
# Wrong magnitude value
base_bonus = magnitude_values['extreme']['empower']  # 1.50 ❌
# Wrong duration
duration = 0  # from "instant" translation ❌

# Buff created:
ActiveBuff(
    bonus_value=1.50,           # Should be 4.0
    duration=0,                  # Should be 60+ with consume_on_use
    duration_remaining=0         # Expires immediately!
)
```

**UI Shows**: "+150% damage for 0s" ❌
**Should Show**: "+400% damage for next attack" ✅

---

## Impact Summary

### Working Skills
- ✅ Restore type (Quick Repair, Field Medic, Second Wind)
- ✅ Buff skills with timed duration (Rockbreaker, Iron Will, etc.)

### Broken Skills
- ❌ ALL empower/instant skills (Power Strike, Master Craftsman, etc.)
- ❌ ALL quicken/instant skills (Smith's Focus, Alchemist's Insight, etc.)
- ❌ ALL pierce/instant skills (Enchanter's Grace)
- ❌ ALL devastate/instant skills (Whirlwind Strike, Chain Harvest)
- ❌ ALL elevate/instant skills (Refiner's Touch, Enchanter's Grace)

**Estimate**: ~18 out of ~30 skills are completely non-functional!

---

## Fix Requirements

### 1. Load Magnitude Values from JSON

Replace hardcoded values in skill_manager.py with values from skills-base-effects-1.JSON.

**Files to Read**:
- `Skills/skills-base-effects-1.JSON` - magnitudeValues for each effect type

### 2. Handle "Instant" Duration Properly

**Option A - Consume on Use** (Recommended):
- Set duration to 60 seconds for instant buffs
- Add `consume_on_use=True` flag to buff
- Remove buff when relevant action is performed (attack, gather, craft)

**Option B - Immediate Application** (Like Restore):
- Don't create buffs for instant empower/quicken/etc.
- Apply effect directly to next action
- Requires tracking "next action bonus" state

### 3. Add Buff Consumption Logic

**Combat Manager** (`Combat/combat_manager.py`):
- After applying empower buff to damage, remove buffs with `consume_on_use=True` and category='damage' or 'combat'

**Gathering System**:
- After applying empower buff to yield, remove buffs with `consume_on_use=True` and matching category

**Crafting System**:
- After applying buffs to minigame, remove buffs with `consume_on_use=True` and matching category

---

## Testing Recommendations

### Before Fix:
- Power Strike: 171.2 damage
- With buff (if it worked): 171.2 × 5.0 = 856 damage

### After Fix:
1. Use Power Strike
2. Attack training dummy
3. Should see: **~856 damage** (5x base damage)
4. Second attack: **171.2 damage** (buff consumed)

---

## Why Debug Display Doesn't Show

**Separate Issue**: Debug display system (`core/debug_display.py`) only captures messages sent via `debug_print()`.

Current code uses `print()` everywhere, so nothing shows on screen.

**Quick Fix Options**:
1. Replace key `print()` statements with `debug_print()`
2. Or: Patch `print()` globally to also feed debug display
3. Or: Add explicit calls at key points

---

**Status**: Bugs identified, ready for fix implementation

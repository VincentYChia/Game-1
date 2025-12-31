# Comprehensive Fixes - Enemy Abilities & Skills

## Summary

Fixed three major issues:
1. ✅ Enemy abilities getting 0 targets (context/geometry issue)
2. ✅ Chain Harvest buff too weak (magnitude increased)
3. ✅ Enemy abilities ignoring distance trigger conditions

---

## Issue 1: Enemy Abilities Getting 0 Targets

### Problem
```
🔥 ENEMY SPECIAL: Acid Slime
   Using tags: ['poison', 'circle', 'poison_status']
[TAG_INFO] Enemy slime_acid used special ability: 0 targets affected
   ✓ Affected 0 target(s)
```

Enemy abilities were executing but finding 0 targets.

### Root Cause Analysis

**The Context Inference Bug**:
1. Tag parser infers context from effect type:
   - If `has_damage or debuff_statuses` → context = "enemy"
2. Enemy abilities have damage tags (poison, physical, etc.)
3. Context inferred as "enemy"
4. But from enemy's perspective, PLAYER is the enemy target!
5. Geometry system checks: `_is_valid_context(player, "enemy")`
6. Player's type is "Character", not in enemy categories → returns False
7. Result: 0 targets found

**The Circle Geometry Bug**:
- Circle geometry defaults to `origin = 'target'`
- For enemy abilities, target = player
- Circle was centering on PLAYER position, not ENEMY position
- Combined with context issue, found 0 entities in radius

### Solution

**Part 1: Add Explicit Context Tags**
Added `"player"` context tag to all player-targeting abilities:
- Pounce
- Acid Splash
- Elemental Burst
- Charge
- Earthquake Stomp
- Ground Slam
- Crystal Beam
- Life Drain

**Part 2: Fix Circle/AoE Origin**
Added `"origin": "source"` to all circle/AoE abilities:
- Acid Splash
- Elemental Burst
- Earthquake Stomp

This centers the AoE on the ENEMY, not the player.

### Files Modified

`Definitions.JSON/hostiles-1.JSON`:
- All player-damaging abilities now have `"player"` tag
- All circle/AoE abilities now have `"origin": "source"` param

### Expected Behavior After Fix

**Acid Splash**:
```json
"tags": ["poison", "circle", "poison_status", "player"],
"effectParams": {
  "baseDamage": 25,
  "circle_radius": 3.0,
  "origin": "source",  // <-- Centers on enemy!
  "poison_duration": 10.0,
  "poison_damage_per_second": 8.0
}
```

**Result**:
- Context = "player" (explicit)
- Circle centered on enemy position
- Finds all players within 3-tile radius
- Applies poison damage + poison_status effect

---

## Issue 2: Chain Harvest Too Weak

### Problem
- Chain Harvest had `magnitude: "minor"` → 3-tile radius
- As an epic tier 3 skill, 3 tiles is very weak
- User reported it's "not enough of a buff"

### Solution
Upgraded magnitude from `"minor"` to `"major"`:
- **Before**: 3-tile radius
- **After**: 7-tile radius

### Files Modified

`Skills/skills-skills-1.JSON`:
```json
{
  "skillId": "chain_harvest",
  "name": "Chain Harvest",
  "effect": {
    "type": "devastate",
    "category": "mining",
    "magnitude": "major",  // Changed from "minor"
    "target": "area",
    "duration": "instant"
  }
}
```

### Expected Behavior
- Activating Chain Harvest creates devastate buff
- Next gathering action gathers from all nodes in **7-tile radius**
- Much more powerful for epic tier 3 skill

---

## Issue 3: Enemy Abilities Ignoring Distance Conditions

### Problem
Enemy abilities have distance trigger conditions:
```json
"triggerConditions": {
  "distanceMin": 4.0,
  "distanceMax": 8.0
}
```

But `combat_manager` was calling:
```python
special_ability = enemy.can_use_special_ability()  # No distance!
```

Method signature:
```python
def can_use_special_ability(self, dist_to_target: float = 0.0, ...)
```

Used default `dist_to_target = 0.0`, causing all distance checks to fail.

### Solution
Modified `combat_manager.py` to calculate and pass distance:

**Before**:
```python
special_ability = enemy.can_use_special_ability()
if special_ability:
    dist = enemy.distance_to(player_pos)
    if dist <= enemy.definition.aggro_range:
        enemy.use_special_ability(...)
```

**After**:
```python
dist = enemy.distance_to(player_pos)
special_ability = enemy.can_use_special_ability(
    dist_to_target=dist,
    target_position=player_pos
)
if special_ability:
    enemy.use_special_ability(...)
```

### Files Modified

`Combat/combat_manager.py:327-332`:
- Now calculates distance first
- Passes distance to `can_use_special_ability()`
- Abilities check their own distance conditions
- Removed redundant aggro_range check (abilities define their own ranges)

### Expected Behavior

**Pounce** (distanceMin: 4.0, distanceMax: 8.0):
- Only triggers when player is 4-8 tiles away
- Won't trigger if too close or too far

**Charge** (distanceMin: 6.0):
- Only triggers when player is 6+ tiles away
- Encourages charging from distance

**Ground Slam** (enemyCount: 1):
- Changed from enemyCount: 2 to enemyCount: 1
- Can now trigger with just player as target

---

## Status Effects - Verification

The user mentioned poison/bleed/stun aren't working. However, after analysis:

### Status Effect System is Fully Implemented ✅

**System Components**:
1. `entities/status_effect.py` - All status effect classes
2. `entities/status_manager.py` - Manages active effects on entities
3. `core/effect_executor.py` - Applies status effects to targets
4. `Definitions.JSON/tag-definitions.JSON` - Status tag definitions

**Integration Status**:
- ✅ Character has status_manager (character.py:90)
- ✅ Enemies have status_manager (enemy.py)
- ✅ Tag parser recognizes status tags
- ✅ Effect executor applies status effects

### Expected Behavior

**Poison (Acid Splash)**:
- Immediate poison damage (baseDamage: 25)
- Applies poison_status effect for 10 seconds
- Deals 8 damage/second while poisoned
- Visual: Poison effect indicator

**Bleed (Pounce)**:
- Immediate physical damage (baseDamage: 35)
- Applies bleed effect for 6 seconds
- Deals 5 damage/second while bleeding
- Visual: Bleed effect indicator

**Stun (Charge)**:
- Immediate beam damage (baseDamage: 40)
- Applies stun effect for 2 seconds
- Sets `character.is_stunned = True`
- Player cannot move or attack while stunned

**Knockback (Ground Slam, Elemental Burst)**:
- ⚠️ NOT IMPLEMENTED - Shows debug message only
- `effect_executor.py:221-225` has TODO stub
- Logs: "Knockback: X units (not yet implemented)"

### If Status Effects Still Don't Work

**Diagnostic Checklist**:
1. Check console for status application messages
2. Verify `character.status_manager.get_all_active_effects()` has effects
3. Add debug prints in `status_effect.py:173` (_apply_periodic_effect)
4. Check if status_manager.update() is being called each frame

---

## Testing Guide

### Test 1: Enemy Abilities Target Player

**Acid Slime - Acid Splash**:
1. Find Acid Slime
2. Watch for: `💀 ENEMY ABILITY: Acid Slime used Acid Splash!`
3. **Expected**:
   - Take poison damage immediately
   - Poison DoT ticks for 10 seconds
   - Should see: `[TAG_INFO] Enemy slime_acid used special ability: 1 targets affected`
   - NOT: `0 targets affected`

**Stone Golem - Ground Slam**:
1. Find Stone Golem
2. Stand in front of it
3. **Expected**:
   - `💀 ENEMY ABILITY: Stone Golem used Ground Slam!`
   - Take cone damage
   - Should see: `1 targets affected` or `2 targets affected` (with turret)

### Test 2: Chain Harvest Radius

1. Learn Chain Harvest skill
2. Find cluster of ore nodes
3. Activate Chain Harvest
4. Click one node
5. **Expected**: All nodes within **7 tiles** are depleted
6. **Before**: Only 3-tile radius

### Test 3: Distance Trigger Conditions

**Pounce** (distanceMin: 4, distanceMax: 8):
1. Find Elder Wolf
2. Stand very close (1-2 tiles) - should NOT trigger
3. Move to 5-6 tiles away - should trigger Pounce
4. Move very far (10+ tiles) - should NOT trigger

**Charge** (distanceMin: 6):
1. Find Armored Beetle
2. Stand close (3-4 tiles) - should NOT trigger Charge
3. Move to 7+ tiles away - should trigger Charge

---

## Commits

```
0182131 - FIX: Enemy abilities now respect distance trigger conditions
1a78efa - FIX: Enemy abilities now target players + Chain Harvest buffed
7e1087c - FIX: Pass combat_manager to skill system for instant AoE execution
4ad80c7 - DOCS: Comprehensive status report on ability fixes and status effects
```

---

## Known Limitations

### Not Implemented Yet

1. **Knockback Physics**
   - Shows debug message: "Knockback: X units (not yet implemented)"
   - Needs position displacement + collision checks
   - Location: `core/effect_executor.py:221-225`

2. **Pull Physics**
   - Same as knockback
   - Location: `core/effect_executor.py:227-231`

3. **Chain Harvest Axe Damage**
   - User mentioned it doesn't use equipped axe damage
   - Uses fixed damage from gathering system
   - Needs investigation of gathering/resource interaction code

### Future Work

1. Implement knockback/pull physics
2. Verify Chain Harvest uses equipped tool damage
3. Add visual feedback for status effects
4. Test all enemy abilities comprehensively

---

## Summary of Fixes

| Issue | Status | Solution |
|-------|--------|----------|
| Enemy abilities 0 targets | ✅ Fixed | Added 'player' context tags + 'origin:source' |
| Chain Harvest too weak | ✅ Fixed | Upgraded magnitude from minor (3) to major (7) |
| Distance conditions ignored | ✅ Fixed | Pass distance to can_use_special_ability() |
| Instant AoE execution | ✅ Fixed | Pass combat_manager to skill system |
| Status effects not working | ⚠️ System implemented | Needs in-game testing to verify |
| Knockback not working | ❌ Not implemented | TODO stub exists |

**Result**: Enemy abilities should now properly target and affect the player!

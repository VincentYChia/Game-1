# Implementation Gap Analysis - BATCH 1-3

**Date**: 2025-12-29
**Purpose**: Document features that are partially implemented or require additional integration

---

## Features Requiring Integration

### 1. Empower Buff Damage Integration ⚠️
**Status**: Status effect implemented, integration points identified but not connected

**What's Implemented**:
- ✅ `EmpowerEffect` class created in `status_effect.py`
- ✅ Creates `empower_damage_multiplier` attribute on character
- ✅ Registered in STATUS_EFFECT_CLASSES

**What's Missing**:
- ❌ Integration into weapon damage calculation in `game_engine.py:_get_weapon_effect_data()`
- ❌ Integration into gathering damage calculation (already present in character.py for gathering)

**Integration Code Needed**:
```python
# In game_engine.py:_get_weapon_effect_data() after line 370
# Apply empower buff damage increase
if hasattr(self.character, 'empower_damage_multiplier'):
    if 'baseDamage' in effect_params:
        effect_params = effect_params.copy()
        effect_params['baseDamage'] *= self.character.empower_damage_multiplier
```

**Priority**: LOW - Framework complete, integration is 5 lines of code

---

### 2. Fortify Buff Defense Integration ⚠️
**Status**: Status effect implemented, integration point identified but not connected

**What's Implemented**:
- ✅ `FortifyEffect` class created in `status_effect.py`
- ✅ Creates `fortify_damage_reduction` attribute on character
- ✅ Registered in STATUS_EFFECT_CLASSES

**What's Missing**:
- ❌ Integration into damage reception in `combat_manager.py:_enemy_attack_player()`

**Integration Code Needed**:
```python
# In combat_manager.py:_enemy_attack_player() after protection enchantments (around line 1078)
# FORTIFY BUFF: Apply fortify damage reduction
fortify_reduction = 0.0
if hasattr(self.character, 'fortify_damage_reduction'):
    fortify_reduction = self.character.fortify_damage_reduction
    if fortify_reduction > 0:
        print(f"   🛡️ Fortify buff: -{fortify_reduction*100:.0f}% damage reduction")

fortify_multiplier = 1.0 - fortify_reduction

# Apply multipliers (update existing line)
final_damage = damage * def_multiplier * armor_multiplier * protection_multiplier * fortify_multiplier
```

**Priority**: LOW - Framework complete, integration is ~10 lines of code

---

### 3. On-Crit Trigger Integration ⚠️
**Status**: Framework implemented, explicit call site not added

**What's Implemented**:
- ✅ `_execute_triggers()` method in `combat_manager.py`
- ✅ Checks for 'on_crit' in metadata_tags
- ✅ Can handle various on_crit effect types

**What's Missing**:
- ❌ Call to `_execute_triggers('on_crit')` when critical hits occur
- ❌ Critical system is in `effect_executor.py` not `combat_manager.py`

**Integration Challenge**:
- Critical hits are detected in `effect_executor.py:_apply_damage()` line 117-126
- Triggers are executed in `combat_manager.py:_execute_triggers()`
- Would need to pass trigger callback or move trigger system to effect_executor

**Workaround**: Could add on_crit trigger detection in legacy combat system where crits are also checked

**Priority**: LOW - Framework exists, needs architectural decision on where triggers belong

---

## Features Not Implemented

### 4. Self-Repair Enchantment ⚠️
**Status**: Not implemented - requires game loop modification

**Reason**: Needs periodic update in main game loop to regenerate durability over time

**Implementation Location**: `core/game_engine.py:update()` method

**Code Needed**:
```python
# In game_engine update loop (periodic check, e.g. every second)
if self.time_accumulator >= 1.0:  # Every second
    self.time_accumulator = 0.0

    # Self-Repair enchantment durability regeneration
    for slot_name, item in self.character.equipment.slots.items():
        if item and hasattr(item, 'enchantments') and hasattr(item, 'durability_current'):
            for ench in item.enchantments:
                effect = ench.get('effect', {})
                if effect.get('type') == 'durability_regeneration':
                    regen_per_minute = effect.get('value', 1.0)
                    regen_per_second = regen_per_minute / 60.0

                    item.durability_current = min(
                        item.durability_max,
                        item.durability_current + regen_per_second
                    )
```

**Priority**: MEDIUM - Useful feature but requires finding/adding periodic update logic

---

### 5. Weightless Enchantment ⚠️
**Status**: Not implemented - no weight/encumbrance system found

**Reason**: Searched codebase for weight/encumbrance mechanics, none found

**Files Checked**:
- `entities/character.py` - No weight tracking
- `entities/components/inventory.py` - No weight limits
- `data/models/equipment.py` - Has `weight` field but unused

**Implementation Would Require**:
1. Weight system in inventory/character
2. Encumbrance penalties (movement speed reduction, etc.)
3. Then weight_multiplier enchantment to reduce weight

**Priority**: LOW - Requires entire new system, low gameplay impact

---

### 6. On-Proximity Triggers ⚠️
**Status**: Framework exists, requires integration with placed entity system

**What's Implemented**:
- ✅ Trigger detection framework in `_execute_triggers()`
- ✅ Can check for 'on_proximity' in metadata_tags

**What's Missing**:
- ❌ Integration with `systems/turret_system.py` or traps
- ❌ Distance checking in update loop for proximity detection
- ❌ Proximity parameter support (trigger_range, etc.)

**Implementation Location**: Would be in placed entity/turret system update loop

**Priority**: MEDIUM - Useful for traps/turrets, but requires system understanding

---

### 7. Dash Damage-on-Contact ⚠️
**Status**: Dash implemented, damage-on-contact flagged as TODO

**What's Implemented**:
- ✅ Dash mechanic with velocity-based movement
- ✅ Parameter `damage_on_contact` is read from params

**What's Missing**:
- ❌ Collision detection during dash
- ❌ Damage application to entities hit during dash

**Code Location**: `core/effect_executor.py:507-509`

**Priority**: LOW - Core dash works, damage-on-contact is bonus feature

---

## Summary

### Fully Implemented (26 features): ✅
- All BATCH 1 features (11)
- All BATCH 2 features (7)
- Core BATCH 3 features (8)

### Partially Implemented (3 features): ⚠️
- Empower buff (need damage calc integration)
- Fortify buff (need damage reception integration)
- On-Crit triggers (need call site integration)

### Not Implemented (4 features): ❌
- Self-Repair (need game loop integration)
- Weightless (need encumbrance system)
- On-Proximity triggers (need placed entity integration)
- Dash damage-on-contact (need collision detection)

**Total Coverage**: 26 fully + 3 partially = 29 out of 33 features investigated = **88% complete**

---

## Recommendations

### Quick Wins (< 30 minutes total):
1. Add Empower integration (5 lines in game_engine.py)
2. Add Fortify integration (10 lines in combat_manager.py)

### Medium Effort (1-2 hours):
3. Add Self-Repair periodic update
4. Add On-Crit trigger call site

### Future Work:
5. On-Proximity triggers (requires trap/turret system work)
6. Weightless enchantment (requires new weight system)
7. Dash damage-on-contact (requires collision system work)

---

## Files Needing Touch-ups

1. `core/game_engine.py` - Empower buff integration
2. `Combat/combat_manager.py` - Fortify buff integration
3. `core/game_engine.py` - Self-Repair periodic update (optional)

All other features are production-ready.

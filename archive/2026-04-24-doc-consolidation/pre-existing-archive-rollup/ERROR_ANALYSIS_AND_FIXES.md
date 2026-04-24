# Error Analysis and Systematic Fixes

## Overview
This document systematically analyzes all naming convention errors found in the codebase and documents their fixes.

---

## Error Categorization

### Category A: Method Name Mismatches (API Errors)
These are cases where main.py calls methods with incorrect names.

### Category B: Data Structure Mismatches
These are cases where data format doesn't match what's expected.

---

## Detailed Error Analysis

### ERROR #1: KeyError 'slime_gel' in smithing.py:427
**File:** Crafting-subdisciplines/smithing.py
**Line:** 427
**Error Type:** Category B - Data Structure Mismatch
**Traceback:**
```
File smithing.py, line 427, in craft_with_minigame
    inventory[inp['materialId']] -= inp['quantity']
KeyError: 'slime_gel'
```

**Root Cause:**
The `craft_with_minigame()` method expects `inventory` to be a Dict[str, int] mapping material_id -> quantity. However, main.py's Inventory is a complex object with slots. The inventory conversion is incomplete or materials are missing.

**Fix Required:**
1. Check inventory conversion in main.py before calling craft_with_minigame
2. Ensure ALL recipe inputs exist in the inventory dict
3. Handle materials that might not be in inventory (should fail earlier in can_craft check)

**Actual Method Signature:**
```python
def craft_with_minigame(self, recipe_id, inventory, minigame_result, item_metadata=None)
    # inventory: Dict[str, int] expected
```

**Fix Location:** main.py - inventory conversion before calling smithing_crafter.craft_with_minigame()

---

### ERROR #2: AttributeError - gain_exp vs add_exp
**File:** Combat/combat_manager.py
**Line:** 387
**Error Type:** Category A - Method Name Mismatch
**Traceback:**
```
File combat_manager.py, line 387
    self.character.leveling.gain_exp(exp_reward)
AttributeError: 'LevelingSystem' object has no attribute 'gain_exp'. Did you mean: 'add_exp'?
```

**Root Cause:**
combat_manager.py calls `gain_exp()` but LevelingSystem has `add_exp()`.

**Actual Method in LevelingSystem (main.py:2061):**
```python
def add_exp(self, amount: int, source: str = "") -> bool:
```

**Fix Required:**
Change `gain_exp` to `add_exp` in combat_manager.py line 387.

**Fix Location:** Combat/combat_manager.py:387

---

### ERROR #3: AttributeError - EquipmentManager.items() missing
**File:** main.py
**Line:** 5998
**Error Type:** Category A - Method Name Mismatch
**Traceback:**
```
File main.py, line 5998, in _open_enchantment_selection
    for slot_name, equipped_item in self.character.equipment.items():
AttributeError: 'EquipmentManager' object has no attribute 'items'
```

**Root Cause:**
EquipmentManager doesn't have an `items()` method. It has a `slots` dict attribute.

**Actual EquipmentManager Structure (main.py:~630):**
```python
class EquipmentManager:
    def __init__(self):
        self.slots: Dict[str, Optional[EquipmentItem]] = {
            'mainHand': None, 'offHand': None, ...
        }
```

**Fix Required:**
Change `self.character.equipment.items()` to `self.character.equipment.slots.items()`

**Fix Location:** main.py:5998

---

### ERROR #4: AttributeError - RefiningMinigame.align_cylinder
**File:** main.py
**Lines:** 4715
**Error Type:** Category A - Method Name Mismatch
**Traceback:**
```
File main.py, line 4715
    self.active_minigame.align_cylinder()
AttributeError: 'RefiningMinigame' object has no attribute 'align_cylinder'
```

**Root Cause:**
RefiningMinigame doesn't have `align_cylinder()` method.

**Actual Methods in RefiningMinigame (refining.py:158):**
```python
def handle_attempt(self):  # Line 158 - This is the correct method
```

**Fix Required:**
Change `align_cylinder()` to `handle_attempt()` at line 4715.

**Fix Location:** main.py:4715

---

### ERROR #5: AttributeError - AlchemyMinigame.chain_ingredient
**File:** main.py
**Lines:** 4711, 4802
**Error Type:** Category A - Method Name Mismatch
**Traceback:**
```
File main.py, line 4802
    self.active_minigame.chain_ingredient()
AttributeError: 'AlchemyMinigame' object has no attribute 'chain_ingredient'
```

**Root Cause:**
AlchemyMinigame has `chain()` not `chain_ingredient()`.

**Actual Methods in AlchemyMinigame (alchemy.py:304):**
```python
def chain(self):  # Line 304 - This is the correct method
def stabilize(self):  # Line 334 - Alternative action
```

**Fix Required:**
Change `chain_ingredient()` to `chain()` at lines 4711 and 4802.

**Fix Locations:** main.py:4711, main.py:4802

---

### ERROR #6: AttributeError - EngineeringMinigame.update missing
**File:** main.py
**Line:** ~6071 (in update loop)
**Error Type:** Category A - Method Name Mismatch
**Traceback:**
```
File main.py, line 6071
    self.active_minigame.update(dt)
AttributeError: 'EngineeringMinigame' object has no attribute 'update'
```

**Root Cause:**
EngineeringMinigame is puzzle-based, not time-based. It doesn't have an `update()` method.

**Actual EngineeringMinigame Methods (engineering.py):**
```python
def handle_action(self, action_type, **kwargs):  # Line 327
def check_current_puzzle(self):  # Line 354
# NO update(dt) method - it's turn-based!
```

**Fix Required:**
In main.py update loop, skip calling `update(dt)` for EngineeringMinigame. Add conditional:
```python
if self.minigame_type != 'engineering':
    self.active_minigame.update(dt)
```

**Fix Location:** main.py:~6071

---

## Comprehensive API Audit

### SmithingMinigame API
```python
def update(self, dt)            ✓ EXISTS
def handle_fan()                ✓ EXISTS
def handle_hammer()             ✓ EXISTS
def end(completed, reason)      ✓ EXISTS
def get_state()                 ✓ EXISTS
```

### RefiningMinigame API
```python
def update(self, dt)            ✓ EXISTS
def handle_attempt()            ✓ EXISTS (NOT align_cylinder!)
def end(success, reason)        ✓ EXISTS
def get_state()                 ✓ EXISTS
```

### AlchemyMinigame API
```python
def update(self, dt)            ✓ EXISTS
def chain()                     ✓ EXISTS (NOT chain_ingredient!)
def stabilize()                 ✓ EXISTS
def end(explosion)              ✓ EXISTS
def get_state()                 ✓ EXISTS
```

### EngineeringMinigame API
```python
def handle_action(type, **kw)  ✓ EXISTS
def check_current_puzzle()      ✓ EXISTS
def end()                       ✓ EXISTS
def get_state()                 ✓ EXISTS
NO update(dt)                   ✗ DOES NOT EXIST - PUZZLE BASED
```

### LevelingSystem API
```python
def add_exp(amount, source)     ✓ EXISTS (NOT gain_exp!)
def get_exp_for_next_level()    ✓ EXISTS
```

### EquipmentManager API
```python
self.slots                      ✓ EXISTS (Dict attribute)
NO items() method               ✗ Use .slots.items() instead
```

---

## Summary of Fixes Needed

| # | Error | File | Line(s) | Current Code | Fixed Code |
|---|-------|------|---------|--------------|------------|
| 1 | KeyError slime_gel | smithing.py | 427 | Inventory dict missing materials | Fix inventory conversion in main.py |
| 2 | gain_exp | combat_manager.py | 387 | `gain_exp(exp_reward)` | `add_exp(exp_reward)` |
| 3 | equipment.items() | main.py | 5998 | `equipment.items()` | `equipment.slots.items()` |
| 4 | align_cylinder | main.py | 4715 | `align_cylinder()` | `handle_attempt()` |
| 5 | chain_ingredient | main.py | 4711, 4802 | `chain_ingredient()` | `chain()` |
| 6 | update missing | main.py | ~6071 | `update(dt)` always | Skip for engineering |

---

## Naming Convention Violations Found

1. **Inconsistent method naming:**
   - LevelingSystem: `add_exp` (correct)
   - combat_manager calls: `gain_exp` (wrong)

2. **Inconsistent API assumptions:**
   - Assuming dict has `.items()` when it's an attribute not a method
   - Assuming all minigames have `update()` when engineering is turn-based

3. **Method name verbosity:**
   - `chain()` is correct, `chain_ingredient()` is overly verbose
   - `handle_attempt()` is correct, `align_cylinder()` is too specific

---

## Next Steps

1. Fix all 6 errors systematically
2. Create Naming Conventions document
3. Add reference to Naming Conventions in Game Mechanics v5
4. Test all fixes thoroughly
5. Search for similar patterns that might cause future errors

# Crafting System Analysis & Fixes
**Date**: 2026-01-17
**Status**: Analysis Complete, Ready for Implementation

---

## Executive Summary

After comprehensive investigation of all 5 crafting disciplines, I've identified the key issues and created a systematic plan for fixes.

### Critical Findings:

1. **Inventory Deduction**: Uses local dict modification - CORRECT approach
2. **materialId vs itemId**: Inconsistent usage across codebase
3. **Rarity None**: Missing fallback to 'common' in some places
4. **Backwards Compatibility**: Partially implemented for smithing/enchanting, MISSING for other disciplines

---

## Issue 1: Inventory Deduction Patterns

### Current State:
- **Crafters** (smithing.py, alchemy.py, etc.): Receive `inventory` as Dict[str, int], modify directly
- **RecipeDatabase.consume_materials()**: Works with Inventory object (slot-based), more robust

### Analysis:
- RecipeDatabase.consume_materials() is MORE ROBUST:
  ✓ Handles materials spread across multiple slots
  ✓ Proper error checking
  ✓ Centralized logic
- BUT crafters use dict because game_engine passes them dict format

### Decision: KEEP CURRENT SYSTEM (Dict-based)
**Reason**: The game engine converts inventory to dict before passing to crafters. Changing this would require major refactoring of game_engine.py. Current system works correctly.

**Action**: No change needed, just ensure consistent dict handling

---

## Issue 2: materialId vs itemId Inconsistency

### Current Usage:
- **Recipe JSON files**: Use `materialId` in inputs array
- **Recipe database**: Uses `materialId` when loading
- **Some crafters**: Have defensive code checking both: `inp.get('materialId') or inp.get('itemId')`
- **Inventory system**: Uses `item_id` as the key

### Problems Found:
```python
# smithing.py line 617
mat_id = inp.get('materialId') or inp.get('itemId')  # Defensive

# recipe_db.py line 162
if inventory.get_item_count(inp.get('materialId', '')) < inp.get('quantity', 0):
```

### Decision: Standardize to `itemId`
**Reason**: User requested this. `itemId` is more global/generic than `materialId`.

**Actions Required**:
1. Update all JSON loading to check both fields (backward compat)
2. Update all internal usage to prefer `itemId`
3. Add fallback: `item_id = inp.get('itemId') or inp.get('materialId')`

---

## Issue 3: Rarity None Fallback

### Current State:
- `rarity_system.get_material_rarity(mat_id)` can return `None`
- Some code assumes rarity is always a string
- Causes crashes in string operations

### Action Required:
Add fallback throughout:
```python
rarity = rarity_system.get_material_rarity(mat_id) or 'common'
```

**Files to Update**:
- smithing.py
- alchemy.py
- refining.py
- engineering.py
- enchanting.py

---

## Issue 4: Backwards Compatibility (MAIN ISSUE)

### Current State by Discipline:

#### **Smithing** ✅ Partial
- **Placement System**: Grid-based with 1-indexed coordinates (e.g., "1,1" to "3,3" for 3x3)
- **Tier Grids**: T1=3x3, T2=5x5, T3=7x7, T4=9x9
- **Offset Calculation**: IMPLEMENTED (lines 2691-2693 in game_engine.py)
  ```python
  offset_x = (station_grid_w - recipe_grid_w) // 2
  offset_y = (station_grid_h - recipe_grid_h) // 2
  ```
- **Status**: Should work but user reports it doesn't

**Potential Issues**:
1. Coordinate system confusion (1-indexed in JSON, needs careful handling)
2. Placement files might not exist for some recipes
3. Grid size detection might fail

#### **Alchemy** ❌ No Backwards Compatibility
- **Placement System**: Sequential slots (`seq_0`, `seq_1`, `seq_2`, ...)
- **Current Validation**: Expects EXACT slot matches
- **Problem**: T1 recipes have 2-3 ingredients, T2+ might have more slots available
- **Needed**: Allow T1 recipes (2 ingredients) to work in T2+ stations (4+ slots)

#### **Refining** ❌ No Backwards Compatibility
- **Placement System**: Hub-and-spoke (`core_0`, `surrounding_0`, `surrounding_1`, ...)
- **Tier Slot Config**:
  - T1: 1 core, 2 surrounding
  - T2: 1 core, 4 surrounding
  - T3: 2 core, 5 surrounding
  - T4: 3 core, 6 surrounding
- **Current Validation**: Expects EXACT slot matches
- **Problem**: T1 recipe (1 core + 2 surrounding) won't work in T2 station (1 core + 4 surrounding)
- **Needed**: Allow T1 recipes to use subset of T2+ slots

#### **Engineering** ❌ No Backwards Compatibility
- **Placement System**: Slot-type based (`eng_slot_0`, `eng_slot_1`, ...)
- **Current Validation**: Expects EXACT slot matches
- **Problem**: Similar to alchemy - recipes define specific slot counts
- **Needed**: Allow lower-tier recipes to use fewer slots in higher-tier stations

#### **Enchanting/Adornments** ✅ Partial
- **Placement System**: Grid-based (same as smithing)
- **Status**: Same offset system as smithing, should work
- **BUT**: Most complex validation logic with pattern matching

---

## Coordinate System Analysis (Smithing/Enchanting)

### JSON Coordinate Format:
```json
{
  "recipeId": "smithing_copper_axe",
  "placementMap": {
    "1,1": "material_a",
    "1,2": "material_b",
    "2,2": "material_c",
    "3,3": "material_d"
  },
  "metadata": {
    "gridSize": "3x3"
  }
}
```

### Coordinate System:
- **1-INDEXED**: Coordinates start at 1, not 0
- **Range for 3x3**: "1,1" to "3,3"
- **Range for 5x5**: "1,1" to "5,5"
- **Format**: "x,y" as string key

### Transformation Algorithm (Current):
```python
recipe_x = int("1")  # Parse from "1,1" -> 1
recipe_y = int("1")  # Parse from "1,1" -> 1

# For T1 recipe (3x3) in T2 station (5x5):
offset_x = (5 - 3) // 2 = 1
offset_y = (5 - 3) // 2 = 1

station_x = recipe_x + offset_x = 1 + 1 = 2
station_y = recipe_y + offset_y = 1 + 1 = 2

# Result: "1,1" maps to "2,2" in station grid
```

### Why It Might Fail:
1. **Placement file not found** for recipe
2. **Grid size not in metadata** (defaults to 3x3)
3. **Coordinate parsing errors** in edge cases
4. **User placement dict uses different key format** than expected

---

## Edge Cases Found

### 1. Alchemy Explosion ✅ IMPLEMENTED
- Lines 389-390 in alchemy.py: Checks if `stage >= 6` (explosion)
- Lines 454-471: Handles explosion with extra 10% material penalty
- **Status**: Fully implemented, no vestigial code

### 2. Engineering Timeout ✅ IMPLEMENTED
- No actual timeout - user can take unlimited time
- **Status**: Working as designed, no issues

### 3. First-Try Bonus Boundary ⚠️ NEEDS REVIEW
- Code checks: `first_try_eligible = (self.attempt == 1) and (performance >= 0.50)`
- **Question**: Should `performance == 0.50` qualify? Currently does (>=)
- **Status**: Probably correct, but worth confirming with user

### 4. Buff Consumption Timing ⚠️ LOW PRIORITY
- Should only consume on success, not failure
- Currently may consume on failure too
- **Action**: Add to master TODO if this is a large change

---

## Implementation Plan

### Phase 1: Standardization (30min)
1. ✅ Analysis complete
2. Add `itemId` fallback to all crafters (backward compat)
3. Add rarity None → 'common' fallback everywhere
4. Document inventory deduction decision

### Phase 2: Backwards Compatibility - Smithing/Enchanting (1hr)
5. Debug why T1 recipes fail in T2+ stations
6. Add logging to coordinate transformation
7. Fix any 0-index/1-index confusion
8. Test with multiple recipes across tiers

### Phase 3: Backwards Compatibility - Refining (45min)
9. Modify validation to allow T1 recipes in T2+ slots
10. Update slot matching to be "minimum required" not "exact match"
11. Test T1-in-T2, T1-in-T3, T2-in-T3 combinations

### Phase 4: Backwards Compatibility - Alchemy (45min)
12. Modify validation to allow fewer ingredients than station capacity
13. Update sequential slot matching
14. Test cross-tier crafting

### Phase 5: Backwards Compatibility - Engineering (45min)
15. Modify validation to allow fewer slots than station provides
16. Update slot matching logic
17. Test cross-tier crafting

### Phase 6: Testing & Verification (1hr)
18. Test ALL 5 disciplines with T1→T2, T1→T3, T1→T4 recipes
19. Verify no regressions in same-tier crafting
20. Document any JSONs that need updating (if any)

---

## Files to Modify

### Core Crafting Files:
- `Crafting-subdisciplines/smithing.py` - itemId, rarity fallback, coord debug
- `Crafting-subdisciplines/alchemy.py` - itemId, rarity fallback, sequential validation
- `Crafting-subdisciplines/refining.py` - itemId, rarity fallback, slot validation
- `Crafting-subdisciplines/engineering.py` - itemId, rarity fallback, slot validation
- `Crafting-subdisciplines/enchanting.py` - itemId, rarity fallback, coord debug

### Game Engine:
- `core/game_engine.py` - validate_placement() for all disciplines

### Database (if needed):
- `data/databases/recipe_db.py` - itemId backward compat

---

## Testing Checklist

### Smithing:
- [ ] T1 recipe (3x3) in T1 station (3x3) - same tier
- [ ] T1 recipe (3x3) in T2 station (5x5) - centered
- [ ] T1 recipe (3x3) in T3 station (7x7) - centered
- [ ] T1 recipe (3x3) in T4 station (9x9) - centered
- [ ] T2 recipe (5x5) in T2 station (5x5) - same tier
- [ ] T2 recipe (5x5) in T3 station (7x7) - centered
- [ ] T2 recipe (5x5) in T4 station (9x9) - centered

### Refining:
- [ ] T1 recipe (1 core + 2 surr) in T1 station (1 core + 2 surr)
- [ ] T1 recipe (1 core + 2 surr) in T2 station (1 core + 4 surr)
- [ ] T1 recipe (1 core + 2 surr) in T3 station (2 core + 5 surr)
- [ ] T1 recipe (1 core + 2 surr) in T4 station (3 core + 6 surr)

### Alchemy:
- [ ] T1 recipe (2 ingredients) in T1 station (2 slots)
- [ ] T1 recipe (2 ingredients) in T2 station (4 slots)
- [ ] T1 recipe (2 ingredients) in T3 station (6 slots)

### Engineering:
- [ ] T1 recipe (2 slots) in T1 station (2 slots)
- [ ] T1 recipe (2 slots) in T2 station (4 slots)
- [ ] T1 recipe (2 slots) in T3 station (6 slots)

### Enchanting:
- [ ] Same tests as Smithing (uses same grid system)

---

## Risk Assessment

### Low Risk:
- Adding `itemId` fallback (backward compatible)
- Adding rarity fallback (defensive coding)
- Refining/Alchemy/Engineering validation changes (isolated)

### Medium Risk:
- Smithing/Enchanting coordinate transformation fixes (affects core gameplay)

### Mitigation:
- Extensive logging during implementation
- Test each discipline independently
- Preserve original JSON files (no changes to data)
- All changes are system-side (code only)

---

## Success Criteria

1. ✅ All T1 recipes work in T2+ stations (all disciplines)
2. ✅ All T2 recipes work in T3+ stations (applicable disciplines)
3. ✅ No regressions in same-tier crafting
4. ✅ No JSON file changes required
5. ✅ Clear error messages when validation fails
6. ✅ Comprehensive logging for debugging

---

**Status**: Ready to begin Phase 1
**Estimated Time**: 5-6 hours total
**Complexity**: Medium (systematic but requires careful testing)

# Placement System Debug Analysis
**Date**: 2026-01-17
**Issue**: T1 recipes don't work in T2+ stations for smithing

---

## Current Implementation Analysis

### Coordinate System
- **1-INDEXED**: Coordinates range from "1,1" to "N,N" for NxN grid
- **3x3 grid**: "1,1" to "3,3"
- **5x5 grid**: "1,1" to "5,5"
- **7x7 grid**: "1,1" to "7,7"
- **9x9 grid**: "1,1" to "9,9"

### Grid Sizes by Tier (game_engine.py:2648-2653)
```python
tier_to_grid = {1: (3, 3), 2: (5, 5), 3: (7, 7), 4: (9, 9)}
```

### Recipe Filtering (recipe_db.py:150)
```python
return [r for r in self.recipes_by_station.get(station_type, []) if r.station_tier <= tier]
```
✅ **CORRECT**: T2 station shows T1 and T2 recipes

### Offset Logic (game_engine.py:2602-2604, 2691-2693)
```python
offset_x = (station_grid_w - recipe_grid_w) // 2
offset_y = (station_grid_h - recipe_grid_h) // 2
```

**Example: T1 recipe (3x3) in T2 station (5x5)**
- offset_x = (5 - 3) // 2 = 1
- offset_y = (5 - 3) // 2 = 1
- Recipe "1,1" → Station "2,2" ✅
- Recipe "3,3" → Station "4,4" ✅
- This centers the 3x3 pattern in the 5x5 grid ✅

### load_recipe_placement() Function
✅ Applies offset correctly
✅ Converts recipe coordinates to station coordinates
✅ Populates `self.user_placement` with offset coordinates

### validate_placement() Function
✅ Applies same offset logic
✅ Validates materials at offset positions
✅ Checks for extra materials outside pattern

---

## Potential Issues

### Issue 1: Interactive UI Coordinate System
**Hypothesis**: The interactive UI might not be using offset coordinates when user manually places materials.

**Where to check**:
- `core/interactive_crafting.py` - How does it handle grid coordinates?
- Does the interactive UI know about the offset when user clicks cells?

### Issue 2: Auto-load vs Manual Placement
**Hypothesis**: `load_recipe_placement()` works correctly, but when user manually places, coordinates aren't offset.

**Test scenario**:
1. Open T2 smithing station
2. Select T1 recipe (3x3)
3. Does it auto-load with offset? (should be centered)
4. If user manually places at "1,1", does system expect "1,1" or "2,2"?

### Issue 3: Station Tier Not Set Correctly
**Hypothesis**: `self.active_station_tier` might not be set when interactive UI opens.

**Where to check**:
- Line 2601: `station_tier = self.active_station_tier`
- Is this variable set correctly when opening interactive UI?

### Issue 4: PlacementDatabase Missing Recipes
**Hypothesis**: Some T1 recipes don't have placement data.

**Test**: Check if placement file has entries for all T1 smithing recipes.

---

## Recommended Fix Strategy

Since the offset logic already exists and appears correct, the issue is likely in ONE of these areas:

1. **Interactive UI doesn't apply offset** when rendering grid or handling clicks
2. **active_station_tier not set** when validating
3. **Placement data missing** for some recipes

### Next Steps:
1. Add comprehensive logging to validate_placement()
2. Add logging to load_recipe_placement()
3. Check if interactive_crafting.py uses offset coordinates
4. Test with a known T1 recipe + T2 station combination

---

## Logging to Add

```python
# In validate_placement():
print(f"DEBUG: Validating {recipe.recipe_id}")
print(f"DEBUG: Station tier: {self.active_station_tier}")
print(f"DEBUG: Recipe grid: {recipe_grid_w}x{recipe_grid_h}")
print(f"DEBUG: Station grid: {station_grid_w}x{station_grid_h}")
print(f"DEBUG: Offset: ({offset_x}, {offset_y})")
print(f"DEBUG: Expected positions: {expected_positions}")
print(f"DEBUG: User placement: {user_placement}")
```

This will reveal exactly where the mismatch occurs.

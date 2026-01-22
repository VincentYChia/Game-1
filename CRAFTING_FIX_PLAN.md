# Crafting System Fix Plan

## Executive Summary

Comprehensive plan to fix crafting system issues across all 5 disciplines (smithing, alchemy, refining, engineering, enchanting).

---

## Issue 1: Material Consumption

### Current State
- **Minigames**: Remove materials from `inv_dict` (temporary copy)
- **game_engine.py**: Calls `recipe_db.consume_materials()` on actual inventory
- **Problem**: Redundant removal logic, `inv_dict` changes are never synced back

### Investigation Needed
Test in-game to verify if materials are actually being consumed. Code analysis shows:
- Debug mode: `consume_materials()` returns True without consuming (CORRECT)
- Normal mode: `consume_materials()` should work (loops through slots, subtracts quantities)

### Potential Issues
1. **Double consumption attempt**: Minigame removes from dict, then consume_materials removes from actual inventory
2. **inv_dict never synced**: Changes to inv_dict are discarded
3. **Race condition**: If materials are equipment, they won't be in inv_dict (line 2009: `if not slot.is_equipment()`)

### Solution
**Option A (Recommended)**: Remove material consumption from minigames, let consume_materials() handle it
- Minigames should only calculate results, not modify inventory
- Single source of truth for consumption
- Clean separation of concerns

**Option B**: Sync inv_dict back to actual inventory, remove consume_materials() call
- More complex
- Need to create dict_to_inventory() sync function

### Files to Modify
- `Crafting-subdisciplines/smithing.py`: Lines 641-649 (remove material subtraction)
- `Crafting-subdisciplines/alchemy.py`: Lines 797-800 (remove material subtraction)
- `Crafting-subdisciplines/refining.py`: Lines 593-597 (remove material subtraction)
- `Crafting-subdisciplines/engineering.py`: Lines 1240-1244 (remove material subtraction)
- `Crafting-subdisciplines/enchanting.py`: Lines 1270-1274 (remove material subtraction)
- Verify consume_materials() is working correctly

---

## Issue 2: Speed Bonuses (CRITICAL BUG)

### Current State
```python
# game_engine.py lines 2054-2090
total_time_bonus = buff_time_bonus + title_time_bonus

# smithing.py lines 56-58
if self.buff_time_bonus > 0:
    self.time_limit = int(self.time_limit * (1.0 + self.buff_time_bonus))
```

### Problem
- **+50% speed bonus** → `time_limit * 1.5` = **50% MORE time** (slower!)
- **+200% speed bonus** → `time_limit * 3.0` = **200% MORE time** (much slower!)

**THIS IS BACKWARDS!**

### Correct Behavior
- **+50% speed** should mean **50% FASTER** = **less time**
- Formula should be: `time_limit / (1.0 + speed_bonus)` OR `time_limit * (1.0 - speed_bonus)`

### Solution Options

**Option A (Multiplicative Inverse)**: Faster = divide time
```python
# +50% speed = 1.5x faster = time / 1.5 = 0.67x time
self.time_limit = int(self.time_limit / (1.0 + self.buff_time_bonus))
```

**Option B (Subtractive)**: Direct percentage reduction
```python
# +50% speed = -50% time = 0.5x time
# But need to clamp: max 90% speed = 0.1x time minimum
speed_mult = max(0.1, 1.0 - min(0.9, self.buff_time_bonus))
self.time_limit = int(self.time_limit * speed_mult)
```

**Recommendation**: Option A (multiplicative inverse)
- More intuitive scaling
- No artificial caps needed
- +100% speed = 2x faster = 0.5x time
- +200% speed = 3x faster = 0.33x time

### Files to Modify
- `Crafting-subdisciplines/smithing.py`: Lines 56-58
- `Crafting-subdisciplines/alchemy.py`: Lines 239-241
- `Crafting-subdisciplines/refining.py`: Lines 68-70
- `Crafting-subdisciplines/engineering.py`: Lines ~68
- `Crafting-subdisciplines/enchanting.py`: (check if applicable)

---

## Issue 3: Crafted Stats System (MAJOR REDESIGN)

### Current Problems

1. **Stats disappear when equipped**:
   - Shown in tooltip but not applied to character
   - Root cause: Stats set as direct attributes, not in `equipment.bonuses` dict
   - `character.recalculate_stats()` only reads from `equipment.bonuses`

2. **Inappropriate stats generated**:
   - "power" stat doesn't belong in equipment system
   - Defense added to weapons
   - Damage added to armor
   - Random stats not related to item type

3. **Quality stat incorrect**:
   - Currently: `100 + bonus_pct`
   - Should be: `earned_points / max_possible_points` ratio

4. **Stat bonuses not properly categorized**:
   - Need item-type-specific filtering
   - Weapons: damage, attack_speed, range
   - Armor: defense, durability
   - Shields: defense, durability, (unique shield stats)
   - Tools: efficiency, durability

### Solution Design

#### A. Define Stat Categories by Item Type

```python
VALID_STATS_BY_TYPE = {
    'weapon': ['damage', 'attack_speed', 'range', 'durability', 'quality'],
    'armor': ['defense', 'durability', 'quality'],
    'shield': ['defense', 'block_chance', 'durability', 'quality'],
    'tool': ['efficiency', 'durability', 'quality']
}
```

#### B. Redesign Stat Generation

**Smithing (Weapons/Armor)**:
```python
def generate_crafted_stats(recipe, minigame_result, item_type, slot):
    tier = recipe.get('stationTier', 1)
    bonus_pct = minigame_result.get('bonus', 0)
    earned_points = minigame_result.get('earned_points', 0)
    max_points = minigame_result.get('max_points', 100)

    # Quality = performance ratio (0-100)
    quality = int((earned_points / max_points) * 100) if max_points > 0 else 50

    base_stats = {
        'durability': 100 + (tier * 20),  # Base durability
        'quality': quality  # Minigame performance
    }

    # Add type-specific stats
    if item_type == 'weapon':
        base_stats['damage'] = 25 + (tier * 10) + bonus_pct
        base_stats['attack_speed'] = bonus_pct * 0.01  # +X% as decimal
    elif item_type in ['armor', 'shield']:
        base_stats['defense'] = 20 + (tier * 8) + bonus_pct
        if item_type == 'shield':
            base_stats['block_chance'] = 0.05 + (bonus_pct * 0.001)  # 5% base
    elif item_type == 'tool':
        base_stats['efficiency'] = 1.0 + (tier * 0.2) + (bonus_pct * 0.01)

    return base_stats
```

#### C. Apply Stats to equipment.bonuses (NOT direct attributes)

**Current (WRONG)**:
```python
# game_engine.py lines 2500-2512
for stat_name, stat_value in stats.items():
    if hasattr(equipment, stat_name):
        setattr(equipment, stat_name, stat_value)  # ❌ Sets direct attribute
```

**Fixed (CORRECT)**:
```python
def apply_crafted_stats_to_equipment(equipment, stats):
    """Apply crafted stats to equipment, filtering by item type"""

    valid_stats = VALID_STATS_BY_TYPE.get(equipment.item_type, [])

    for stat_name, stat_value in stats.items():
        if stat_name not in valid_stats:
            print(f"   ⚠️ Skipping invalid stat '{stat_name}' for {equipment.item_type}")
            continue

        # Handle special cases
        if stat_name == 'damage':
            if equipment.item_type == 'weapon':
                # Apply as damage boost to base damage
                base_avg = sum(equipment.damage) / 2
                boost = stat_value - base_avg
                if boost > 0:
                    equipment.bonuses['damage_bonus'] = boost

        elif stat_name == 'defense':
            if equipment.item_type in ['armor', 'shield']:
                # Apply as defense boost
                boost = stat_value - equipment.defense
                if boost > 0:
                    equipment.bonuses['defense'] = boost

        elif stat_name == 'attack_speed':
            if equipment.item_type == 'weapon':
                # Apply as attack speed bonus (additive)
                equipment.bonuses['attack_speed'] = stat_value

        elif stat_name == 'durability':
            # Apply to max durability directly
            if stat_value > equipment.durability_max:
                equipment.durability_max = int(stat_value)
                equipment.durability_current = int(stat_value)

        elif stat_name == 'quality':
            # Store quality as metadata (doesn't affect stats)
            equipment.bonuses['quality'] = stat_value

        elif stat_name == 'efficiency':
            if equipment.item_type == 'tool':
                equipment.efficiency = stat_value
```

#### D. Update Minigames to Track Points

All minigames need to return:
- `earned_points`: Actual points earned during minigame
- `max_points`: Maximum possible points
- `bonus`: Percentage bonus (can be derived from points)

**Smithing**: Already tracks strikes and quality
**Alchemy**: Track successful placements vs total possible
**Refining**: Track temperature control accuracy
**Engineering**: Track precision measurements
**Enchanting**: Track rune placement accuracy

### Files to Modify

1. **Create new file**: `entities/components/crafted_stats.py`
   - Define VALID_STATS_BY_TYPE
   - Implement generate_crafted_stats()
   - Implement apply_crafted_stats_to_equipment()

2. **Modify**: `core/game_engine.py` (lines 2500-2512)
   - Replace direct setattr with apply_crafted_stats_to_equipment()

3. **Modify**: All 5 minigames to return earned_points/max_points
   - `Crafting-subdisciplines/smithing.py`
   - `Crafting-subdisciplines/alchemy.py`
   - `Crafting-subdisciplines/refining.py`
   - `Crafting-subdisciplines/engineering.py`
   - `Crafting-subdisciplines/enchanting.py`

4. **Modify**: `entities/components/equipment_manager.py`
   - Verify get_stat_bonuses() reads from bonuses dict correctly
   - Add methods to get weapon_damage_bonus(), armor_defense_bonus()

5. **Modify**: `entities/character.py`
   - Update recalculate_stats() to apply crafted bonuses
   - Add methods to get_total_weapon_damage(), get_total_defense()

---

## Issue 4: General Audit Items

### A. Equipment Stat Application Verification

**Test Cases**:
1. Craft weapon with +10 damage bonus → Check character damage increases when equipped
2. Craft armor with +15 defense bonus → Check character defense increases when equipped
3. Craft shield → Verify proper stats (defense, block_chance if implemented)
4. Craft tool → Verify efficiency applies to gathering

### B. Rarity System Integration

Verify rarity modifiers are applied AFTER crafted stats:
```
Base Stats → Rarity Multiplier → First-Try Bonus → Apply to Equipment
```

### C. Tooltip Display Accuracy

Ensure tooltips show:
- Base item stats (damage, defense, etc.)
- Durability effectiveness multiplier
- Enchantments
- **Crafted bonuses** (clearly labeled, accurate values)

### D. Save/Load Persistence

Verify crafted stats persist through save/load:
- ItemStack.crafted_stats saved
- EquipmentItem.bonuses saved
- Stats still apply after loading

### E. Stacking Rules

Items with different crafted_stats should not stack:
- Two iron swords with different quality values = separate stacks
- Same crafted_stats = can stack

### F. Edge Cases

1. **Shields**:
   - Should have defense like armor
   - May have unique block mechanics (future)
   - Currently treated as offHand weapon?

2. **Two-Handed Weapons**:
   - Verify hand_type="2H" prevents offHand equipping
   - Check if crafted bonuses apply correctly

3. **Versatile Weapons**:
   - hand_type="versatile" allows 1H or 2H use
   - Verify damage scaling

4. **Tools**:
   - Efficiency bonus should stack with STR/AGI bonuses
   - Durability should work same as equipment

---

## Implementation Order

### Phase 1: Investigation (1 task)
1. Test material consumption in normal mode - verify if bug exists

### Phase 2: Critical Fixes (2 tasks)
2. Fix speed bonus calculation (multiplicative inverse)
3. Create crafted stats system (new file, stat categories)

### Phase 3: Stat Application (3 tasks)
4. Modify minigames to return earned_points/max_points
5. Update game_engine.py to use apply_crafted_stats_to_equipment()
6. Update character.py recalculate_stats() to read from bonuses

### Phase 4: Material Consumption (1 task)
7. Remove redundant material removal from minigames (if needed)

### Phase 5: Testing (3 tasks)
8. Test each item type (weapon, armor, shield, tool)
9. Verify stats persist through equip/unequip/save/load
10. Audit for edge cases and additional issues

---

## Success Criteria

- [ ] Materials consumed correctly in normal mode, not consumed in debug mode
- [ ] Speed bonuses work correctly (+50% speed = faster crafting)
- [ ] Crafted stats apply when equipment is equipped
- [ ] Stats are appropriate for item type (no defense on weapons, etc.)
- [ ] Quality calculated as earned/max ratio (0-100)
- [ ] No "power" or other inappropriate stats
- [ ] Durability bonuses add to item durability
- [ ] Attack speed bonuses add to character attack speed
- [ ] Shields work correctly with appropriate stats
- [ ] Tooltips accurately reflect stats that will be applied
- [ ] Stats persist through save/load
- [ ] All 5 disciplines working consistently

---

## Risk Assessment

**High Risk**:
- Stat system redesign (touches many systems)
- Equipment bonus application (affects combat, character stats)

**Medium Risk**:
- Speed bonus fix (simple but widespread)
- Material consumption fix (may introduce bugs)

**Low Risk**:
- Minigame points tracking (isolated changes)
- Tooltip accuracy (display only)

---

## Testing Strategy

1. **Unit Tests**: Test stat generation logic in isolation
2. **Integration Tests**: Craft items, verify stats apply
3. **Edge Case Tests**: Shields, tools, two-handed weapons
4. **Regression Tests**: Verify existing features still work
5. **Save/Load Tests**: Verify persistence

---

## Dependencies

- Character stats system (existing)
- Equipment system (existing)
- Inventory system (existing)
- Minigame results (existing)
- Rarity system (existing)
- Title system (recently integrated)

---

## Notes

- Keep changes modular and JSON-driven where possible
- Maintain backwards compatibility with existing saves if possible
- Add comprehensive debug logging for troubleshooting
- Consider future features (block mechanics, parry, etc.)

---

**Created**: 2026-01-22
**Status**: Planning Complete - Ready for Implementation

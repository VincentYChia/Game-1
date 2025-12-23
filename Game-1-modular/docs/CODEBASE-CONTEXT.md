# Codebase Context - Game-1-modular

**Generated**: 2025-12-22
**Branch**: claude/tags-to-effects-019DhmtS6ScBeiY2gorfzexT
**Purpose**: Accurate context for tag system and enchantment debugging

---

## Current State

### Git Status
- Clean working directory (after rollback)
- Last commit: `280a232` - Documentation: Runtime Bug Fixes Analysis
- Rolled back 2 commits containing hallucinated content

### Known Issues
1. **Sharpness enchantment does NOT increase damage** (user confirmed)
2. Training dummy shows tooltip has increased damage but combat damage unchanged
3. Fire Aspect works (status effect)
4. Need debug deduplication for comprehensive testing

---

## Actual Enchantments in This Game

**Source**: `/Game-1-modular/recipes.JSON/recipes-enchanting-1.JSON`

### Weapon Enchantments
- `sharpness_1` - 10% damage multiplier (BROKEN - doesn't work)
- `sharpness_2` - 20% damage multiplier (likely BROKEN)
- `sharpness_3` - 35% damage multiplier (likely BROKEN)
- `fire_aspect` - DoT (10 dps, 5s) - WORKS
- `frost_touch` - Slow (30%, 4s)
- `lightning_strike` - Chain damage (2 chains, 50% damage)
- `knockback` - Knockback value 3
- `poison` - DoT (8 dps, 8s)
- `lifesteal` - 12% lifesteal

### Armor Enchantments
- `protection_1, protection_2, protection_3` - Damage reduction (10%/20%/35%)
- `thorns` - Reflect 15% damage
- `swiftness` - Movement speed +15% (stackable, max 3)
- `regeneration` - Health regen (1 hp/sec, stackable max 5)

### Tool Enchantments
- `efficiency_1, efficiency_2` - Gathering speed (20%/40%)
- `fortune_1, fortune_2` - Bonus yield chance (30%/60%)
- `silk_touch` - Harvest original form

### Universal Enchantments
- `unbreaking_1, unbreaking_2` - Durability (30%/60%)
- `weightless` - Weight -50%
- `self_repair` - Durability regen (1/min)
- `soulbound` - Returns on death

**IMPORTANT**: These are NOT Minecraft enchantments. No "Smite", "Bane of Arthropods", "Power", etc.

---

## Damage Calculation Code Flow

### Working Path (Equipment Manager)
```python
# File: entities/components/equipment_manager.py:115-122
def get_weapon_damage(self, hand: str = 'mainHand') -> Tuple[int, int]:
    weapon = self.slots.get(hand)
    if weapon:
        return weapon.get_actual_damage()  # ✅ CORRECT - includes enchantments
    return (1, 2) if hand == 'mainHand' else (0, 0)
```

### Broken Path (Character)
```python
# File: entities/character.py:1042-1061
def get_weapon_damage(self) -> float:
    if hasattr(self, '_selected_slot') and self._selected_slot:
        selected_item = self.equipment.slots.get(self._selected_slot)
        if selected_item and selected_item.damage:
            # ❌ BUG: Uses raw .damage instead of .get_actual_damage()
            if isinstance(selected_item.damage, tuple):
                return (selected_item.damage[0] + selected_item.damage[1]) / 2.0
            else:
                return float(selected_item.damage)

    # Fallback uses equipment manager (which works correctly)
    damage_range = self.equipment.get_weapon_damage()
    return (damage_range[0] + damage_range[1]) / 2.0
```

### Enchantment Application (Correct Implementation)
```python
# File: data/models/equipment.py:41-53
def get_actual_damage(self) -> Tuple[int, int]:
    """Get actual damage including durability and enchantment effects"""
    eff = self.get_effectiveness()
    base_damage = (self.damage[0] * eff, self.damage[1] * eff)

    # Apply enchantment damage multipliers
    damage_mult = 1.0
    for ench in self.enchantments:
        effect = ench.get('effect', {})
        if effect.get('type') == 'damage_multiplier':
            damage_mult += effect.get('value', 0.0)

    return (int(base_damage[0] * damage_mult), int(base_damage[1] * damage_mult))
```

### Combat Usage
```python
# File: Combat/combat_manager.py:403 (legacy path)
weapon_damage = self.character.get_weapon_damage()  # ❌ Uses broken function

# File: Combat/combat_manager.py:644 (tag-based path)
weapon_damage = self.character.get_weapon_damage()  # ❌ Uses broken function
```

**Root Cause**: When player has `_selected_slot`, `character.get_weapon_damage()` uses raw `.damage` property instead of calling `.get_actual_damage()` method.

**Why Tooltip Works**: Tooltip likely calls `equipment.get_actual_damage()` directly.

**Why Fire Aspect Works**: Status effects (DoT) use different code path, not `damage_multiplier` type.

---

## Tag System Architecture

### Effect Tags
**Source**: Test items and documentation

**Damage Types**: physical, fire, ice, lightning, poison, slashing, piercing, crushing
**Geometry Tags**: single, cone, circle, chain, beam, projectile
**Status Tags**: burn, freeze, slow, bleed, poison

### Tag Files for Testing
- `/items.JSON/items-testing-tags.JSON` - Edge case test weapons
- `/recipes.JSON/recipes-tag-tests.JSON` - Recipe tests

### Test Items Include
- Simple valid weapon
- Conflicting elements (fire + ice)
- Multiple geometry (cone + chain + circle)
- Missing parameters
- Unknown/invalid tags

---

## Training Dummy

**File**: `/systems/training_dummy.py:41-91`

**Features**:
- High HP (10,000) - doesn't die easily
- Auto-resets at 10% health
- Tracks hit count, total damage
- Detailed damage reporting with tags
- Accepts parameters from both legacy and tag-based systems

**Key Method**:
```python
def take_damage(self, damage: float, damage_type: str = "physical",
                from_player: bool = False, source_tags: list = None,
                attacker_name: str = None, source=None, tags=None, **kwargs):
```

---

## Key Files Map

### Enchantments
- `recipes.JSON/recipes-enchanting-1.JSON` - All 30 enchantment recipes
- `data/models/equipment.py` - EquipmentItem class with get_actual_damage()

### Character/Equipment
- `entities/character.py:1042-1061` - get_weapon_damage() (BROKEN)
- `entities/components/equipment_manager.py:115-122` - get_weapon_damage() (WORKS)

### Combat
- `Combat/combat_manager.py:393` - player_attack_enemy() (uses broken function)
- `Combat/combat_manager.py:617` - player_attack_enemy_with_tags() (uses broken function)

### Testing
- `systems/training_dummy.py` - Training dummy implementation
- `items.JSON/items-testing-tags.JSON` - Test items
- `recipes.JSON/recipes-tag-tests.JSON` - Test recipes

### Tag System
- `core/tags/effect_executor.py` - Tag-based effect execution
- `core/geometry/target_finder.py` - Geometry calculations (beam, cone, etc.)
- `docs/tag-system/` - Tag system documentation

---

## Test Methodology

### User's Reported Test
1. Equip weapon with no enchantments
2. Attack training dummy
3. Note damage
4. Apply sharpness enchantment
5. Tooltip shows increased damage ✅
6. Attack training dummy
7. Actual damage unchanged ❌

### Expected Behavior
- Tooltip damage = Combat damage
- Sharpness I should add 10% damage
- Sharpness II should add 20% damage
- Sharpness III should add 35% damage

---

## Next Steps (For Future Conversation)

1. Fix `character.get_weapon_damage()` to call `.get_actual_damage()` on selected_item
2. Test sharpness enchantments I, II, III
3. Test other `damage_multiplier` enchantments (if any exist)
4. Implement debug deduplication if needed
5. Document which enchantments actually work vs broken

---

## Important Notes

- **DO NOT** reference Minecraft enchantments (Smite, Bane of Arthropods, Power, etc.)
- **DO NOT** assume enchantments exist without checking recipes-enchanting-1.JSON
- **DO NOT** assume features from other games apply here
- **DO** check actual JSON files for ground truth
- **DO** trace code paths to understand bugs
- **DO** test with training dummy to verify fixes

---

**Status**: Context built, ready for fix validation in next conversation.

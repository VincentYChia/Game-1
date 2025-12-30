# Weapon Tag Implementation Plan

**Date:** 2025-12-17
**Priority:** MEDIUM (High Impact)
**Estimated Time:** 2-3 hours

---

## Overview

Weapon metadata tags (e.g., `["melee", "mace", "2H", "crushing", "armor_breaker"]`) currently exist in JSON but are **not used** for combat mechanics. This document details how to integrate them.

---

## Current State

### Where Weapon Tags Exist
- **File**: `items.JSON/items-smithing-2.JSON`
- **Field**: `metadata.tags` (array of strings)
- **Examples**:
  - Iron Warhammer: `["melee", "mace", "2H", "crushing", "armor_breaker"]`
  - Copper Dagger: `["melee", "dagger", "1H", "fast", "precision"]`
  - Composite Longbow: `["ranged", "bow", "2H", "precision"]`

### Current Combat Calculation
Damage is calculated using:
1. Weapon's `damage` field (tuple)
2. Weapon's `statMultipliers` (damage, attackSpeed, etc.)
3. Character stats (STR, AGI)
4. Buffs/debuffs

**Tags are NOT referenced anywhere in combat code.**

---

## Tag Semantics & Effects

### Position 0: Range Type (Informational)
- `melee` / `ranged` - Visual/cosmetic, no mechanical effect

### Position 1: Weapon Type (Informational)
- `sword`, `dagger`, `mace`, `bow`, `staff`, `spear`, `axe` - Type categorization

### Position 2: Hand Requirement (MECHANICAL - Already Partially Implemented)
- `1H` - One-handed, can equip offhand
- `2H` - Two-handed, +20% damage bonus (**NEW**)
- `versatile` - Can use 1H or 2H (+10% if no offhand equipped) (**NEW**)

**Current State**: Hand type affects equipping logic but NOT damage.

### Position 3+: Combat Properties (MECHANICAL - NEW IMPLEMENTATIONS)

| Tag | Effect | Implementation |
|-----|--------|----------------|
| `fast` | +15% attack speed | Modify attack cooldown calculation |
| `precision` | +10% critical hit chance | Bonus to crit calculation |
| `crushing` | +20% damage vs armored enemies | Extra damage if enemy defense > threshold |
| `armor_breaker` | Ignore 25% of enemy defense | Reduce enemy defense in damage calc |
| `reach` | +1 unit attack range | Bonus to weapon range |
| `cleaving` | Hit adjacent enemies for 50% damage | AOE check in attack handler |

---

## Implementation Steps

### Step 1: Read Weapon Tags in Equipment Model

**File**: `data/models/equipment.py`

**Action**: Add method to get metadata tags from EquipmentDatabase

```python
def get_metadata_tags(self) -> List[str]:
    """Get metadata tags from item definition"""
    from data.databases import EquipmentDatabase
    eq_db = EquipmentDatabase.get_instance()

    if hasattr(eq_db, 'items') and self.item_id in eq_db.items:
        item_def = eq_db.items[self.item_id]
        metadata = item_def.get('metadata', {})
        return metadata.get('tags', [])

    return []
```

---

### Step 2: Create Tag Modifier Calculator

**File**: `entities/components/weapon_tag_calculator.py` (NEW FILE)

**Purpose**: Centralized logic for converting tags → combat bonuses

```python
"""Weapon tag modifier calculator"""
from typing import Dict, List, Tuple

class WeaponTagModifiers:
    """Calculate combat bonuses from weapon metadata tags"""

    @staticmethod
    def get_damage_multiplier(tags: List[str], has_offhand: bool = False) -> float:
        """Calculate damage multiplier from tags"""
        multiplier = 1.0

        # Hand requirement bonuses
        if "2H" in tags:
            multiplier *= 1.2  # +20% damage for two-handed
        elif "versatile" in tags and not has_offhand:
            multiplier *= 1.1  # +10% if using versatile without offhand

        return multiplier

    @staticmethod
    def get_attack_speed_bonus(tags: List[str]) -> float:
        """Calculate attack speed bonus from tags"""
        bonus = 0.0

        if "fast" in tags:
            bonus += 0.15  # +15% attack speed

        return bonus

    @staticmethod
    def get_crit_chance_bonus(tags: List[str]) -> float:
        """Calculate critical hit chance bonus from tags"""
        bonus = 0.0

        if "precision" in tags:
            bonus += 0.10  # +10% crit chance

        return bonus

    @staticmethod
    def get_range_bonus(tags: List[str]) -> float:
        """Calculate attack range bonus from tags"""
        bonus = 0.0

        if "reach" in tags:
            bonus += 1.0  # +1 unit range

        return bonus

    @staticmethod
    def get_armor_penetration(tags: List[str]) -> float:
        """Calculate armor penetration (0.0-1.0)"""
        if "armor_breaker" in tags:
            return 0.25  # Ignore 25% of armor
        return 0.0

    @staticmethod
    def get_damage_vs_armored_bonus(tags: List[str]) -> float:
        """Get bonus damage vs armored targets"""
        if "crushing" in tags:
            return 0.20  # +20% vs armored
        return 0.0

    @staticmethod
    def has_cleaving(tags: List[str]) -> bool:
        """Check if weapon has cleaving (AOE) property"""
        return "cleaving" in tags
```

---

### Step 3: Integrate Tags into Combat Damage Calculation

**File**: `Combat/combat_manager.py`

**Location**: `player_attack_enemy()` method

**Before**:
```python
def player_attack_enemy(self, enemy, shield_blocking=False, hand='mainHand'):
    weapon_dmg_range = self.character.equipment.get_weapon_damage(hand)
    base_damage = random.randint(*weapon_dmg_range)

    stat_bonus = self.character.stats.get_bonus('strength')
    # ... damage calculation ...
```

**After**:
```python
def player_attack_enemy(self, enemy, shield_blocking=False, hand='mainHand'):
    weapon = self.character.equipment.slots.get(hand)
    weapon_dmg_range = self.character.equipment.get_weapon_damage(hand)
    base_damage = random.randint(*weapon_dmg_range)

    # WEAPON TAG MODIFIERS
    if weapon:
        weapon_tags = weapon.get_metadata_tags()
        from entities.components.weapon_tag_calculator import WeaponTagModifiers

        # Hand requirement damage bonus (2H, versatile)
        has_offhand = self.character.equipment.slots.get('offHand') is not None
        tag_damage_mult = WeaponTagModifiers.get_damage_multiplier(weapon_tags, has_offhand)

        # Armor penetration (armor_breaker)
        armor_pen = WeaponTagModifiers.get_armor_penetration(weapon_tags)
        effective_defense = enemy.definition.stats.get('defense', 0) * (1.0 - armor_pen)

        # Bonus vs armored (crushing)
        if effective_defense > 10:  # "Armored" threshold
            crushing_bonus = WeaponTagModifiers.get_damage_vs_armored_bonus(weapon_tags)
            tag_damage_mult *= (1.0 + crushing_bonus)

        # Apply tag damage multiplier
        base_damage = int(base_damage * tag_damage_mult)

    stat_bonus = self.character.stats.get_bonus('strength')
    # ... rest of damage calculation ...
```

---

### Step 4: Integrate Tags into Critical Hit Calculation

**File**: `Combat/combat_manager.py`

**Location**: Critical hit check

**Before**:
```python
crit_chance = self.character.stats.luck * 0.02 + self.character.class_system.get_bonus('crit_chance')
is_crit = random.random() < crit_chance
```

**After**:
```python
crit_chance = self.character.stats.luck * 0.02 + self.character.class_system.get_bonus('crit_chance')

# Add weapon tag crit bonus (precision)
if weapon:
    weapon_tags = weapon.get_metadata_tags()
    from entities.components.weapon_tag_calculator import WeaponTagModifiers
    crit_chance += WeaponTagModifiers.get_crit_chance_bonus(weapon_tags)

is_crit = random.random() < crit_chance
```

---

### Step 5: Integrate Tags into Attack Speed Calculation

**File**: `entities/character.py`

**Location**: `reset_attack_cooldown()` method

**Before**:
```python
def reset_attack_cooldown(self, is_weapon: bool = True, hand: str = 'mainHand'):
    if is_weapon:
        weapon_attack_speed = self.equipment.get_weapon_attack_speed(hand)
        base_cooldown = 1.0
        attack_speed_bonus = self.stats.agility * 0.03
        cooldown = (base_cooldown / weapon_attack_speed) / (1.0 + attack_speed_bonus)
```

**After**:
```python
def reset_attack_cooldown(self, is_weapon: bool = True, hand: str = 'mainHand'):
    if is_weapon:
        weapon = self.equipment.slots.get(hand)
        weapon_attack_speed = self.equipment.get_weapon_attack_speed(hand)
        base_cooldown = 1.0
        attack_speed_bonus = self.stats.agility * 0.03

        # Add weapon tag attack speed bonus (fast)
        if weapon:
            weapon_tags = weapon.get_metadata_tags()
            from entities.components.weapon_tag_calculator import WeaponTagModifiers
            attack_speed_bonus += WeaponTagModifiers.get_attack_speed_bonus(weapon_tags)

        cooldown = (base_cooldown / weapon_attack_speed) / (1.0 + attack_speed_bonus)
```

---

### Step 6: Integrate Tags into Attack Range

**File**: `entities/components/equipment_manager.py`

**Location**: `get_weapon_range()` method

**Before**:
```python
def get_weapon_range(self, hand: str = 'mainHand') -> float:
    weapon = self.slots.get(hand)
    if weapon:
        return weapon.range
    if hand == 'mainHand':
        return 1.0
    return 0.0
```

**After**:
```python
def get_weapon_range(self, hand: str = 'mainHand') -> float:
    weapon = self.slots.get(hand)
    if weapon:
        base_range = weapon.range

        # Add tag-based range bonus (reach)
        weapon_tags = weapon.get_metadata_tags()
        from entities.components.weapon_tag_calculator import WeaponTagModifiers
        range_bonus = WeaponTagModifiers.get_range_bonus(weapon_tags)

        return base_range + range_bonus

    if hand == 'mainHand':
        return 1.0
    return 0.0
```

---

### Step 7: Implement Cleaving (AOE Attacks)

**File**: `Combat/combat_manager.py`

**Location**: After primary attack damage is dealt

**New Logic**:
```python
# After damaging primary target
if weapon:
    weapon_tags = weapon.get_metadata_tags()
    from entities.components.weapon_tag_calculator import WeaponTagModifiers

    if WeaponTagModifiers.has_cleaving(weapon_tags):
        # Find adjacent enemies
        adjacent_enemies = [
            e for e in self.enemies
            if e != enemy and e.is_alive and e.distance_to(enemy.position) <= 1.5
        ]

        # Deal 50% damage to adjacent enemies
        cleave_damage = int(final_damage * 0.5)
        for adj_enemy in adjacent_enemies:
            adj_enemy.take_damage(cleave_damage, "physical")
            print(f"   ⚔️  Cleave hit {adj_enemy.definition.name} for {cleave_damage} damage")
```

---

## Testing Plan

### Test Case 1: Two-Handed Damage Bonus
- **Weapon**: Iron Warhammer (`["melee", "mace", "2H", "crushing", "armor_breaker"]`)
- **Expected**: +20% damage compared to base
- **Verify**: Check damage numbers against training dummy

### Test Case 2: Fast Attack Speed
- **Weapon**: Copper Dagger (`["melee", "dagger", "1H", "fast", "precision"]`)
- **Expected**: +15% faster attack cooldown
- **Verify**: Time attacks, should be ~0.87s instead of 1.0s

### Test Case 3: Precision Critical Hits
- **Weapon**: Composite Longbow (`["ranged", "bow", "2H", "precision"]`)
- **Expected**: +10% crit chance (base luck + class + 10%)
- **Verify**: Attack training dummy 100 times, count crits

### Test Case 4: Armor Penetration
- **Weapon**: Iron Warhammer (`armor_breaker` tag)
- **Expected**: Ignore 25% of enemy defense
- **Verify**: Damage vs high-defense enemy should be noticeably higher

### Test Case 5: Crushing vs Armored
- **Weapon**: Iron Warhammer (`crushing` tag)
- **Expected**: +20% damage vs enemies with defense > 10
- **Verify**: Damage vs armored beetle vs damage vs slime

### Test Case 6: Reach Bonus
- **Weapon**: Copper Spear (`["melee", "spear", "versatile", "reach"]`)
- **Expected**: Attack range increases from 2.0 to 3.0
- **Verify**: Can attack training dummy from farther away

### Test Case 7: Cleaving AOE
- **Weapon**: Steel Battleaxe (`["melee", "axe", "versatile", "cleaving"]`)
- **Expected**: Hits adjacent enemies for 50% damage
- **Verify**: Attack one wolf in a pack, adjacent wolves should take damage

---

## File Checklist

- [ ] `data/models/equipment.py` - Add `get_metadata_tags()` method
- [ ] `entities/components/weapon_tag_calculator.py` (NEW) - Tag modifier logic
- [ ] `Combat/combat_manager.py` - Integrate tags into damage, crit, and cleaving
- [ ] `entities/character.py` - Integrate tags into attack speed
- [ ] `entities/components/equipment_manager.py` - Integrate tags into range
- [ ] `docs/tag-system/WEAPON-TAG-IMPLEMENTATION.md` (THIS FILE) - Documentation

---

## Success Criteria

1. ✅ All weapon tags from JSON are read and applied
2. ✅ Damage bonuses visible when attacking training dummy
3. ✅ Attack speed changes detectable
4. ✅ Critical hit rate increases measurably
5. ✅ Range bonuses allow attacking from farther away
6. ✅ Cleaving hits multiple enemies
7. ✅ No crashes or errors
8. ✅ Backward compatible (weapons without tags still work)

---

## Estimated Impact

- **Gameplay**: HIGH - Makes weapon choice strategically meaningful
- **Code Complexity**: MEDIUM - Requires changes in 5 files
- **Risk**: LOW - All changes are additive, no removal of existing logic
- **Testing Required**: MEDIUM - Need to verify each tag effect

---

## Next Steps

1. Implement `get_metadata_tags()` in equipment model
2. Create `weapon_tag_calculator.py` module
3. Integrate into combat_manager and character
4. Test with training dummy
5. Document results

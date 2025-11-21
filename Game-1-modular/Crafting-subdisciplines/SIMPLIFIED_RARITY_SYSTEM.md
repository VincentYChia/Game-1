# Simplified Rarity Modifier System
**Based on User Requirements**

## Core Principles

1. **Category-Based Modifiers**: Weapons get different modifiers than armor/tools
2. **Same Rarity Requirement**: ALL input materials must be same rarity to craft
3. **Rarity Inheritance**: Output inherits input material rarity
4. **Single JSON File**: All modifier rules in one place
5. **No Mixing**: Can't craft with common + epic materials together

---

## System Overview

### Rarity Tiers:
- **Common**: Base stats (0% bonus)
- **Uncommon**: +10-15% to primary stats
- **Rare**: +20-30% to primary stats, +5-10% to secondary
- **Epic**: +35-50% to primary stats, +10-20% to secondary, unlock special effects
- **Legendary**: +50-75% to primary stats, +20-30% to secondary, multiple special effects

### Item Categories:
- **Weapon**: damage, durability, critical_chance, attack_speed, lifesteal
- **Armor**: defense, durability, resistance, damage_reduction
- **Tool**: efficiency, durability, gathering_speed, yield_bonus
- **Consumable**: potency, duration, effect_count
- **Device**: power, durability, range, cooldown

---

## Rarity Modifiers JSON Structure

**File: `rarity-modifiers.JSON`**

```json
{
  "metadata": {
    "version": "1.0",
    "description": "Category-based rarity modifiers for crafted items"
  },

  "weapon": {
    "common": {
      "description": "Basic weapon with no bonuses"
    },
    "uncommon": {
      "description": "Improved weapon with modest bonuses",
      "modifiers": {
        "damage": 0.10,
        "durability": 0.05
      }
    },
    "rare": {
      "description": "High-quality weapon with significant bonuses",
      "modifiers": {
        "damage": 0.20,
        "durability": 0.10,
        "critical_chance": 0.05
      }
    },
    "epic": {
      "description": "Exceptional weapon with major bonuses",
      "modifiers": {
        "damage": 0.35,
        "durability": 0.20,
        "critical_chance": 0.10,
        "attack_speed": 0.05
      }
    },
    "legendary": {
      "description": "Legendary weapon with massive bonuses",
      "modifiers": {
        "damage": 0.50,
        "durability": 0.30,
        "critical_chance": 0.15,
        "attack_speed": 0.10,
        "lifesteal": 0.05
      }
    }
  },

  "armor": {
    "common": {
      "description": "Basic armor with no bonuses"
    },
    "uncommon": {
      "description": "Improved armor with modest protection",
      "modifiers": {
        "defense": 0.10,
        "durability": 0.05
      }
    },
    "rare": {
      "description": "High-quality armor with significant protection",
      "modifiers": {
        "defense": 0.20,
        "durability": 0.10,
        "resistance": 0.05
      }
    },
    "epic": {
      "description": "Exceptional armor with major protection",
      "modifiers": {
        "defense": 0.35,
        "durability": 0.20,
        "resistance": 0.10,
        "damage_reduction": 0.05
      }
    },
    "legendary": {
      "description": "Legendary armor with massive protection",
      "modifiers": {
        "defense": 0.50,
        "durability": 0.30,
        "resistance": 0.15,
        "damage_reduction": 0.10,
        "thorns": 0.05
      }
    }
  },

  "tool": {
    "common": {
      "description": "Basic tool with no bonuses"
    },
    "uncommon": {
      "description": "Improved tool with better efficiency",
      "modifiers": {
        "efficiency": 0.10,
        "durability": 0.05
      }
    },
    "rare": {
      "description": "High-quality tool with significant efficiency",
      "modifiers": {
        "efficiency": 0.20,
        "durability": 0.10,
        "gathering_speed": 0.05
      }
    },
    "epic": {
      "description": "Exceptional tool with major efficiency",
      "modifiers": {
        "efficiency": 0.35,
        "durability": 0.20,
        "gathering_speed": 0.10,
        "yield_bonus": 0.05
      }
    },
    "legendary": {
      "description": "Legendary tool with massive efficiency",
      "modifiers": {
        "efficiency": 0.50,
        "durability": 0.30,
        "gathering_speed": 0.15,
        "yield_bonus": 0.10,
        "auto_smelt": true
      }
    }
  },

  "consumable": {
    "common": {
      "description": "Basic consumable"
    },
    "uncommon": {
      "description": "Improved consumable",
      "modifiers": {
        "potency": 0.15,
        "duration": 0.10
      }
    },
    "rare": {
      "description": "High-quality consumable",
      "modifiers": {
        "potency": 0.30,
        "duration": 0.20
      }
    },
    "epic": {
      "description": "Exceptional consumable",
      "modifiers": {
        "potency": 0.50,
        "duration": 0.35,
        "effect_count": 1
      }
    },
    "legendary": {
      "description": "Legendary consumable",
      "modifiers": {
        "potency": 0.75,
        "duration": 0.50,
        "effect_count": 2
      }
    }
  },

  "device": {
    "common": {
      "description": "Basic device"
    },
    "uncommon": {
      "description": "Improved device",
      "modifiers": {
        "power": 0.10,
        "durability": 0.05
      }
    },
    "rare": {
      "description": "High-quality device",
      "modifiers": {
        "power": 0.20,
        "durability": 0.10,
        "range": 0.05
      }
    },
    "epic": {
      "description": "Exceptional device",
      "modifiers": {
        "power": 0.35,
        "durability": 0.20,
        "range": 0.10,
        "cooldown": -0.10
      }
    },
    "legendary": {
      "description": "Legendary device",
      "modifiers": {
        "power": 0.50,
        "durability": 0.30,
        "range": 0.15,
        "cooldown": -0.20,
        "auto_reload": true
      }
    }
  }
}
```

---

## Crafting Flow

### Step 1: Check Rarity Uniformity
```python
def check_rarity_uniformity(inputs, material_rarities):
    """Check that all input materials have the same rarity"""
    rarities = set()
    for inp in inputs:
        mat_id = inp['materialId']
        rarity = material_rarities.get(mat_id, 'common')
        rarities.add(rarity)

    if len(rarities) > 1:
        return False, None  # Mixed rarities - can't craft

    return True, list(rarities)[0]  # All same rarity
```

### Step 2: Apply Category Modifiers
```python
def apply_rarity_modifiers(base_stats, output_category, output_rarity, rarity_modifiers):
    """Apply category-based rarity modifiers to output item"""
    # Get modifiers for this category and rarity
    category_mods = rarity_modifiers.get(output_category, {})
    rarity_mods = category_mods.get(output_rarity, {}).get('modifiers', {})

    # Apply each modifier to base stats
    modified_stats = base_stats.copy()
    for stat, bonus in rarity_mods.items():
        if stat in modified_stats:
            if isinstance(bonus, bool):
                modified_stats[stat] = bonus  # Special effects
            else:
                modified_stats[stat] = int(modified_stats[stat] * (1 + bonus))

    return modified_stats
```

### Step 3: Store with Rarity
```python
# Output inherits input rarity
crafted_items['iron_sword_rare'] = {
    'base_id': 'iron_sword',
    'rarity': 'rare',
    'quantity': 1,
    'stats': modified_stats,
    'enchantments': []
}
```

---

## Example Crafting Scenarios

### Scenario 1: Common Materials → Common Output
```python
# Inputs: 3x common iron_ingot, 2x common oak_plank
# All common → can craft
# Output: common_iron_sword
# Base stats: {damage: 25, durability: 100}
# Modifiers: None (common has no bonuses)
# Final stats: {damage: 25, durability: 100}
```

### Scenario 2: Rare Materials → Rare Output
```python
# Inputs: 3x rare iron_ingot, 2x rare oak_plank
# All rare → can craft
# Output: rare_iron_sword (category: weapon)
# Base stats: {damage: 25, durability: 100}
# Modifiers: damage +20%, durability +10%, critical_chance +5%
# Final stats: {damage: 30, durability: 110, critical_chance: 5}
```

### Scenario 3: Mixed Rarities → Can't Craft
```python
# Inputs: 3x rare iron_ingot, 2x common oak_plank
# Mixed rarities → CANNOT CRAFT
# Error: "All materials must be the same rarity to craft"
```

### Scenario 4: Epic Materials → Epic Output
```python
# Inputs: 5x epic steel_ingot, 3x epic leather
# All epic → can craft
# Output: epic_steel_armor (category: armor)
# Base stats: {defense: 50, durability: 150}
# Modifiers: defense +35%, durability +20%, resistance +10%, damage_reduction +5%
# Final stats: {defense: 67, durability: 180, resistance: 10, damage_reduction: 5}
```

---

## Implementation Steps

### 1. Create Rarity Modifiers JSON
- Create `rarity-modifiers.JSON` with all category definitions
- Define modifiers for each rarity tier per category

### 2. Update Item Metadata
- Add `category` field to item metadata (weapon, armor, tool, consumable, device)
- Determine category from recipe output type

### 3. Update can_craft() Functions
```python
def can_craft(self, recipe_id, inventory, material_rarities):
    # Check materials available
    if not has_materials(recipe_id, inventory):
        return False

    # Check rarity uniformity
    inputs = recipe['inputs']
    uniform, rarity = check_rarity_uniformity(inputs, material_rarities)
    if not uniform:
        return False  # Mixed rarities

    return True
```

### 4. Update craft_with_minigame() Functions
```python
def craft_with_minigame(self, recipe_id, inventory, minigame_result, material_rarities, rarity_modifiers):
    # ... existing code ...

    # Detect input rarity
    inputs = recipe['inputs']
    _, input_rarity = check_rarity_uniformity(inputs, material_rarities)

    # Get output category
    output_id = recipe['outputId']
    output_category = get_item_category(output_id)  # weapon/armor/tool/etc

    # Calculate base stats (from tier, minigame, etc)
    base_stats = calculate_base_stats(recipe, minigame_result)

    # Apply rarity modifiers
    final_stats = apply_rarity_modifiers(base_stats, output_category, input_rarity, rarity_modifiers)

    # Return with rarity
    return {
        'success': True,
        'outputId': output_id,
        'rarity': input_rarity,
        'stats': final_stats,
        ...
    }
```

### 5. Update Display
```python
# Item list shows rarity
"Epic Iron Sword: x1 [Q:180]"

# Tooltip shows rarity and modifiers
"""
Epic Iron Sword
Tier 2 | Weapon | Epic

A balanced steel longsword.

Stats:
  Damage: 30 (+20% from Epic)
  Durability: 110 (+10% from Epic)
  Critical Chance: 5 (+5% from Epic)
"""
```

---

## Benefits of This System

1. **Simple**: One JSON, category-based rules
2. **Clear**: All iron swords of same rarity have same bonuses
3. **Flexible**: Easy to adjust modifier values per category
4. **No Mixing**: Forces player to use consistent quality materials
5. **Scales Well**: Higher rarity = progressively better stats
6. **Easy to Display**: "Epic Iron Sword" is clear
7. **Future-Proof**: Can add more categories or refine per-item later

---

## Migration Notes

- Existing crafted items will be treated as "common" rarity
- Players will need to refine materials to rare/epic to craft higher rarity items
- Refining is the primary way to upgrade material rarity
- This creates a clear progression: refine → craft with rare materials → get rare items

---

## Questions Resolved

✅ Category-based modifiers (weapon/armor/tool) not per-material
✅ Higher rarity = better stats, category-specific
✅ Keep refining rarities
✅ No negative modifiers
✅ All materials must be same rarity
✅ Single JSON for all modifiers

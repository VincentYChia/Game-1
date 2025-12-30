# Crafting Tag Systems - Complete Implementation Guide

## Overview

This document describes the complete tag-driven crafting system for Game-1. All crafting disciplines (Smithing, Engineering, Enchanting, Alchemy, Refining) use metadata tags to determine functionality, slot assignment, applicability rules, and LLM generation templates.

**Design Philosophy:**
- Tags drive all crafting logic (LLM-friendly, extensible)
- User functionality and experience is paramount
- Redundant tags are eliminated automatically
- Wrong applications fail gracefully (no crashes, just no-ops)
- Single source of truth: `core/crafting_tag_processor.py`

## Tag Processor Location

**File:** `core/crafting_tag_processor.py`

Contains five processor classes:
1. `SmithingTagProcessor` - Slot assignment, item inheritance
2. `EngineeringTagProcessor` - Role/behavior assignment
3. `EnchantingTagProcessor` - Rule validation, graceful failure
4. `AlchemyTagProcessor` - Potion vs transmutation logic
5. `RefiningTagProcessor` - LLM scaling templates

---

## 1. Smithing Tag System

### Purpose
- Determine equipment slot from recipe tags
- Inherit functional tags to crafted items
- Eliminate redundant tags (recipe vs item)

### Tag Categories

#### Slot Assignment Tags
```python
{
    "weapon": "mainHand",     # Generic weapon → mainhand
    "tool": None,             # Tool → determined by sub-type
    "armor": None,            # Armor → determined by sub-type
    "shield": "offHand",      # Shield → offhand
    "accessory": "accessory", # Accessory → accessory slot
}
```

#### Tool Sub-Types
```python
{
    "pickaxe": "pickaxe",  # Pickaxe tool slot
    "axe": "axe",          # Axe tool slot
    "shovel": "tool",      # Generic tool slot
    "hoe": "tool",         # Generic tool slot
}
```

#### Armor Sub-Types
```python
{
    "helmet": "helmet",
    "chestplate": "chestplate",
    "leggings": "leggings",
    "boots": "boots",
    "gauntlets": "gauntlets",
}
```

#### Functional Tags (Inherited to Item)
```python
FUNCTIONAL_TAGS = [
    # Combat style
    "melee", "ranged", "magic",

    # Hand requirement
    "1H", "2H", "versatile",

    # Weapon type
    "sword", "axe", "spear", "bow",

    # Damage type
    "crushing", "slashing", "piercing",

    # Combat properties
    "fast", "precision", "reach",

    # Special mechanics
    "armor_breaker", "cleaving",
]
```

### Usage Example

```python
from core.crafting_tag_processor import SmithingTagProcessor

# Example recipe tags
recipe_tags = ["weapon", "sword", "2H", "starter", "crushing"]

# Get equipment slot
slot = SmithingTagProcessor.get_equipment_slot(recipe_tags)
# Returns: "mainHand"

# Get tags to inherit to crafted item
inheritable = SmithingTagProcessor.get_inheritable_tags(recipe_tags)
# Returns: ["sword", "2H", "crushing"]
# (Excludes "weapon" and "starter" as non-functional)

# Remove redundant tags
item_tags = ["sword", "2H", "melee"]
filtered_recipe_tags = SmithingTagProcessor.remove_redundant_tags(
    recipe_tags, item_tags
)
# Returns: ["crushing", "starter"]  (sword, 2H already on item)
```

### JSON Example

```json
{
  "metadata": {
    "narrative": "Two-handed greatsword for crushing blows",
    "tags": ["weapon", "sword", "2H", "crushing", "starter"]
  },
  "recipeId": "smithing_iron_greatsword",
  "outputId": "iron_greatsword",
  "outputs": "The item inherits: ['sword', '2H', 'crushing']",
  "slot": "Automatically determined as 'mainHand' from 'weapon' tag"
}
```

---

## 2. Engineering Tag System

### Purpose
- Determine placement/usage behavior from tags
- Assign combat functionality
- Determine trigger types for traps

### Tag Categories

#### Role Tags (Behavior Assignment)
```python
{
    "device": "placeable",           # Can be placed in world
    "turret": "placeable_combat",    # Placeable with combat AI
    "trap": "placeable_triggered",   # Placeable with trigger
    "station": "placeable_crafting", # Placeable crafting station
    "utility": "usable",             # Usable item (not placeable)
    "consumable": "consumable",      # Single-use (bombs, grenades)
}
```

#### Functional Tags
- `projectile`, `fire`, `lightning`, `area` - Combat effects
- `proximity`, `pressure`, `tripwire` - Trap triggers
- `basic`, `advanced` - Difficulty/tier

### Usage Example

```python
from core.crafting_tag_processor import EngineeringTagProcessor

# Example: Turret
turret_tags = ["turret", "fire", "projectile"]
behavior = EngineeringTagProcessor.get_behavior_type(turret_tags)
# Returns: "placeable_combat"

is_combat = EngineeringTagProcessor.is_combat_device(turret_tags)
# Returns: True

# Example: Trap
trap_tags = ["trap", "fire", "proximity"]
behavior = EngineeringTagProcessor.get_behavior_type(trap_tags)
# Returns: "placeable_triggered"

trigger = EngineeringTagProcessor.get_trigger_type(trap_tags)
# Returns: "proximity"

# Example: Utility item (not placeable)
utility_tags = ["utility", "teleport"]
behavior = EngineeringTagProcessor.get_behavior_type(utility_tags)
# Returns: "usable"
```

### Integration Points

**When creating engineering item:**
```python
from core.crafting_tag_processor import EngineeringTagProcessor

recipe_tags = recipe['metadata']['tags']
behavior_type = EngineeringTagProcessor.get_behavior_type(recipe_tags)

if behavior_type == "placeable_combat":
    # Create turret entity with combat AI
    create_turret(recipe, combat_enabled=True)
elif behavior_type == "placeable_triggered":
    # Create trap with trigger logic
    trigger_type = EngineeringTagProcessor.get_trigger_type(recipe_tags)
    create_trap(recipe, trigger=trigger_type)
elif behavior_type == "usable":
    # Create usable item (not placeable)
    create_usable_item(recipe)
```

### JSON Example

```json
{
  "metadata": {
    "narrative": "Fire arrow turret with proximity trigger",
    "tags": ["turret", "fire", "projectile"]
  },
  "recipeId": "engineering_fire_arrow_turret",
  "outputId": "fire_arrow_turret",
  "behaviorType": "placeable_combat (determined from 'turret' tag)",
  "combatEnabled": "true (determined from 'turret' and 'projectile' tags)"
}
```

---

## 3. Enchanting Tag System

### Purpose
- Validate enchantment applicability (weapon/armor/universal)
- Graceful failure on wrong application
- Extract functionality tags

### Tag Categories

#### Rule Tags (Applicability)
```python
{
    "universal": ["weapon", "armor", "tool"],  # Can apply to anything
    "weapon": ["weapon"],                       # Weapons only
    "armor": ["armor"],                         # Armor only
    "tool": ["tool"],                           # Tools only
}
```

#### Functionality Tags
- `damage`, `durability`, `speed`, `defense` - Stat modifiers
- `fire`, `lightning`, `ice` - Elemental effects
- `sharpness`, `unbreaking`, `protection` - Specific enchantments

#### Metadata Tags (Non-functional)
- `basic`, `advanced`, `legendary` - Tier/quality
- `starter`, `quality` - Descriptive only

### Usage Example

```python
from core.crafting_tag_processor import EnchantingTagProcessor

# Example: Weapon-only enchantment
weapon_ench_tags = ["weapon", "damage", "sharpness", "basic"]

applicable_types = EnchantingTagProcessor.get_applicable_item_types(weapon_ench_tags)
# Returns: ["weapon"]

# Try to apply to weapon
can_apply, reason = EnchantingTagProcessor.can_apply_to_item(weapon_ench_tags, "weapon")
# Returns: (True, "OK")

# Try to apply to armor (GRACEFUL FAILURE)
can_apply, reason = EnchantingTagProcessor.can_apply_to_item(weapon_ench_tags, "armor")
# Returns: (False, "Enchantment not applicable to armor items")
# IMPORTANT: Does NOT crash! Just returns False

# Get functionality tags
func_tags = EnchantingTagProcessor.get_functionality_tags(weapon_ench_tags)
# Returns: ["damage", "sharpness"]
# (Excludes "weapon" and "basic")
```

### Graceful Failure Example

**WRONG APPLICATION - NO CRASH:**
```python
# Trying to apply Sharpness to helmet
enchant_tags = ["weapon", "damage", "sharpness"]
item_type = "armor"

can_apply, reason = EnchantingTagProcessor.can_apply_to_item(enchant_tags, item_type)
if can_apply:
    apply_enchantment(item, enchantment)
else:
    # Gracefully fail - show message, don't crash
    print(f"Cannot apply: {reason}")
    # Game continues normally
```

### JSON Example

```json
{
  "metadata": {
    "narrative": "Basic sharpening enchantment",
    "tags": ["weapon", "damage", "basic"]
  },
  "recipeId": "enchanting_sharpness_basic",
  "enchantmentId": "sharpness_1",
  "applicableTo": ["weapon"],
  "note": "applicableTo field is REDUNDANT with 'weapon' tag - can be removed",
  "gracefulFailure": "If applied to armor, returns (False, reason) instead of crashing"
}
```

---

## 4. Alchemy Tag System

### Purpose
- Distinguish potions (consumable) from transmutations (item output)
- Determine effect types
- Extract rule tags

### Tag Categories

#### Rule Tags (Type Determination)
```python
# Priority: "potion" overrides "transmutation"
if "potion" in tags:
    is_consumable = True
elif "transmutation" in tags:
    is_consumable = False
else:
    is_consumable = False  # Default: transmutation (everything is an item)
```

#### Effect Tags
```python
{
    "healing": "heal",
    "buff": "buff",
    "damage": "damage",
    "utility": "utility",
    "strength": "buff_strength",
    "defense": "buff_defense",
    "speed": "buff_speed",
}
```

### Usage Example

```python
from core.crafting_tag_processor import AlchemyTagProcessor

# Example: Healing Potion (consumable)
potion_tags = ["potion", "healing", "starter"]
is_consumable = AlchemyTagProcessor.is_consumable(potion_tags)
# Returns: True

effect = AlchemyTagProcessor.get_effect_type(potion_tags)
# Returns: "heal"

# Example: Transmutation (item output, NOT consumable)
transmute_tags = ["transmutation", "gold", "alchemy"]
is_consumable = AlchemyTagProcessor.is_consumable(transmute_tags)
# Returns: False (outputs items, not consumed)

# Example: Default behavior (no potion or transmutation tag)
default_tags = ["iron", "alchemy"]
is_consumable = AlchemyTagProcessor.is_consumable(default_tags)
# Returns: False (defaults to transmutation - everything is an item)
```

### Integration Points

```python
from core.crafting_tag_processor import AlchemyTagProcessor

recipe_tags = recipe['metadata']['tags']
is_consumable = AlchemyTagProcessor.is_consumable(recipe_tags)

if is_consumable:
    # Create consumable potion
    item = create_consumable_potion(recipe)
    item.stack_size = 99  # Potions can stack
    item.on_use = apply_potion_effect
else:
    # Create transmutation output (item)
    item = create_material_item(recipe)
    item.stack_size = 999  # Materials can stack
```

### JSON Example

```json
{
  "metadata": {
    "narrative": "Healing potion from herbs",
    "tags": ["potion", "healing", "starter"]
  },
  "recipeId": "alchemy_minor_health_potion",
  "outputId": "minor_health_potion",
  "isConsumable": "true (determined from 'potion' tag)",
  "effectType": "heal (determined from 'healing' tag)"
}
```

**Transmutation Example:**
```json
{
  "metadata": {
    "narrative": "Transmute lead to gold",
    "tags": ["transmutation", "gold", "advanced"]
  },
  "recipeId": "alchemy_lead_to_gold",
  "outputId": "gold_ingot",
  "isConsumable": "false (transmutation outputs items)",
  "note": "If both 'potion' and 'transmutation' tags present, 'potion' wins"
}
```

---

## 5. Refining Tag System

### Purpose
- Provide LLM-friendly recipe templates
- Determine process type
- Calculate material tier

### Tag Categories

#### Process Type Tags
- `smelting`, `crushing`, `grinding`, `purifying`, `alloying`

#### Tier Tags
```python
{
    "basic": 1,
    "starter": 1,
    "advanced": 2,
    "quality": 3,
    "legendary": 4,
    "master": 4,
}
```

### Usage Example

```python
from core.crafting_tag_processor import RefiningTagProcessor

# Example: Basic smelting
refine_tags = ["smelting", "copper", "basic"]
process = RefiningTagProcessor.get_process_type(refine_tags)
# Returns: "smelting"

tier = RefiningTagProcessor.get_material_tier(refine_tags)
# Returns: 1

# Generate LLM template
template = RefiningTagProcessor.generate_recipe_template("mithril", tier=3)
# Returns complete recipe dict ready for LLM generation:
# {
#   "recipeId": "refining_mithril_ore_to_ingot",
#   "inputs": [{"materialId": "mithril_ore", "quantity": 1}],
#   "outputs": [{"materialId": "mithril_ingot", "quantity": 1, "rarity": "common"}],
#   "stationRequired": "refinery",
#   "stationTierRequired": 3,
#   "metadata": {
#     "narrative": "Refining mithril ore into usable ingots.",
#     "tags": ["smelting", "mithril", "advanced"]
#   }
# }
```

### LLM Scaling Logic

The `generate_recipe_template()` function provides a structured template that an LLM can use to generate new refining recipes. This enables:

1. **Automatic recipe generation** - LLM creates new recipes from material names
2. **Consistent structure** - All recipes follow same format
3. **Tier-based scaling** - Station tier requirements scale with material tier
4. **Narrative generation** - LLM can expand the narrative field

**Example LLM prompt:**
```
Using this template, generate a refining recipe for {material_name} at tier {tier}:
[Insert template from generate_recipe_template()]

Expand the narrative to describe the refining process in detail.
Add any special requirements or fuel needs for this material.
```

### JSON Example

```json
{
  "recipeId": "refining_steel_ore_to_ingot",
  "metadata": {
    "narrative": "Forging steel from carbon-rich ore. Requires intense heat.",
    "tags": ["smelting", "steel", "advanced"]
  },
  "processType": "smelting (from 'smelting' tag)",
  "tier": "2 (from 'advanced' tag)",
  "llmScalable": "true (use generate_recipe_template() to create similar recipes)"
}
```

---

## 6. Chunk Tag System (Future)

### Purpose
- Drive world generation logic
- Filter spawn tables by tags
- Modify resource generation rates

### Planned Tag Categories

#### Biome Tags
- `plains`, `forest`, `desert`, `mountains`, `swamp`

#### Resource Tags
- `ore_rich`, `wood_rich`, `crystal_rich`

#### Spawn Tags
- `hostile`, `passive`, `neutral`
- `undead`, `beast`, `construct`

### Integration Point (Placeholder)

```python
# Future implementation
def generate_chunk(chunk_coords, biome_tags):
    """Generate chunk using tag-driven logic"""

    # Filter spawn tables by tags
    if "hostile" in biome_tags:
        enemies = get_enemies_with_tags(["hostile"])

    # Modify resource generation
    if "ore_rich" in biome_tags:
        ore_density *= 2.0

    # ... generate chunk
```

---

## Integration Checklist

### Smithing Integration
- [x] Tag processor created (`SmithingTagProcessor`)
- [x] Slot assignment logic defined
- [x] Tag inheritance logic defined
- [x] Redundancy elimination logic defined
- [ ] Integrated into `data/databases/equipment_db.py::create_equipment_from_id()`
- [ ] Integrated into crafting completion handler

### Engineering Integration
- [x] Tag processor created (`EngineeringTagProcessor`)
- [x] Behavior type assignment defined
- [x] Combat device detection defined
- [x] Trap trigger logic defined
- [ ] Integrated into turret placement system
- [ ] Integrated into trap placement system
- [ ] Integrated into device usage system

### Enchanting Integration
- [x] Tag processor created (`EnchantingTagProcessor`)
- [x] Rule validation logic defined
- [x] Graceful failure implemented
- [x] Functionality tag extraction defined
- [ ] Integrated into enchantment application system
- [ ] Replace `applicableTo` field with tag-based validation

### Alchemy Integration
- [x] Tag processor created (`AlchemyTagProcessor`)
- [x] Potion vs transmutation logic defined
- [x] Effect type detection defined
- [ ] Integrated into alchemy crafting completion
- [ ] Consumable vs material item creation

### Refining Integration
- [x] Tag processor created (`RefiningTagProcessor`)
- [x] Process type detection defined
- [x] Tier calculation defined
- [x] LLM template generation defined
- [ ] Integrated into recipe validation
- [ ] LLM recipe generation system created

---

## Summary

All five crafting tag processors are fully implemented in `core/crafting_tag_processor.py`:

1. ✅ **SmithingTagProcessor** - Equipment slot assignment, tag inheritance, redundancy elimination
2. ✅ **EngineeringTagProcessor** - Behavior assignment (placeable/usable/consumable), combat detection
3. ✅ **EnchantingTagProcessor** - Rule validation, graceful failure, functionality extraction
4. ✅ **AlchemyTagProcessor** - Potion vs transmutation logic, effect typing
5. ✅ **RefiningTagProcessor** - LLM scaling templates, process/tier detection

**Next Steps:**
1. Integrate each processor into corresponding crafting systems
2. Test graceful failure paths (especially enchanting)
3. Implement LLM recipe generation using RefiningTagProcessor templates
4. Add chunk tag system for world generation

**Philosophy Maintained:**
- ✅ Tags drive all logic (LLM-friendly)
- ✅ User experience prioritized
- ✅ Redundancy eliminated
- ✅ Graceful failure (no crashes)
- ✅ Single source of truth

# Tag System Integration Examples

This document provides code examples for integrating the remaining tag processors (Alchemy and Refining) into crafting completion handlers.

## Alchemy Integration Example

### Integration Point
When an alchemy recipe is completed and the output item is created, use `AlchemyTagProcessor` to determine if it's a consumable potion or a transmutation item output.

### Example Code

```python
def complete_alchemy_recipe(recipe: Dict, quality: float = 1.0):
    """Complete an alchemy recipe and create output item"""
    from core.crafting_tag_processor import AlchemyTagProcessor
    from data.databases import MaterialDatabase

    # Get recipe tags
    recipe_tags = recipe.get('metadata', {}).get('tags', [])

    # Determine if consumable using tag processor
    is_consumable = AlchemyTagProcessor.is_consumable(recipe_tags)

    # Get effect type
    effect_type = AlchemyTagProcessor.get_effect_type(recipe_tags)

    # Create output item
    output_id = recipe['outputId']
    output_qty = recipe.get('outputQty', 1)

    if is_consumable:
        # Create consumable potion
        item = create_consumable_item(
            item_id=output_id,
            quantity=output_qty,
            effect_type=effect_type,
            quality=quality,
            max_stack=99  # Potions stack
        )
        print(f"✓ Created consumable potion: {output_id}")
    else:
        # Create transmutation output (material item)
        item = create_material_item(
            item_id=output_id,
            quantity=output_qty,
            quality=quality,
            max_stack=999  # Materials stack higher
        )
        print(f"✓ Created transmutation output: {output_id}")

    return item
```

### Tag Examples

**Potion (Consumable):**
```json
{
  "metadata": {
    "tags": ["potion", "healing", "starter"]
  },
  "recipeId": "alchemy_minor_health_potion",
  "outputId": "minor_health_potion"
}
```
Result: `is_consumable=True`, creates consumable potion with heal effect

**Transmutation (Item Output):**
```json
{
  "metadata": {
    "tags": ["transmutation", "gold", "advanced"]
  },
  "recipeId": "alchemy_lead_to_gold",
  "outputId": "gold_ingot"
}
```
Result: `is_consumable=False`, creates material item (gold ingot)

**Default (No Tags):**
```json
{
  "metadata": {
    "tags": ["iron", "alchemy"]
  },
  "recipeId": "alchemy_iron_processing",
  "outputId": "iron_ingot"
}
```
Result: `is_consumable=False` (defaults to transmutation - everything is an item)

---

## Refining Integration Example

### Integration Point
When a refining recipe is completed, use `RefiningTagProcessor` to modify output quantity (yield) and quality (rarity) based on process type tags.

### Example Code

```python
def complete_refining_recipe(recipe: Dict, base_success_rate: float = 1.0):
    """Complete a refining recipe with tag-based output modification"""
    from core.crafting_tag_processor import RefiningTagProcessor
    from data.databases import MaterialDatabase

    # Get recipe tags
    recipe_tags = recipe.get('metadata', {}).get('tags', [])

    # Get base output from recipe
    outputs = recipe.get('outputs', [])
    if not outputs:
        return None

    output_data = outputs[0]  # Primary output
    base_quantity = output_data.get('quantity', 1)
    base_rarity = output_data.get('rarity', 'common')
    material_id = output_data.get('materialId')

    # Apply tag-based modifications
    final_quantity = RefiningTagProcessor.calculate_output_quantity(base_quantity, recipe_tags)
    final_rarity = RefiningTagProcessor.upgrade_rarity(base_rarity, recipe_tags)

    # Get process type for logging
    process_type = RefiningTagProcessor.get_process_type(recipe_tags)
    yield_mult = RefiningTagProcessor.get_yield_multiplier(recipe_tags)
    quality_bonus = RefiningTagProcessor.get_quality_bonus(recipe_tags)

    # Create output item
    item = create_material_item(
        item_id=material_id,
        quantity=final_quantity,
        rarity=final_rarity,
        max_stack=999
    )

    # Log modifications
    if yield_mult != 1.0 or quality_bonus > 0:
        print(f"✓ Refining complete: {material_id}")
        print(f"   Process: {process_type}")
        if yield_mult != 1.0:
            print(f"   Yield: {base_quantity} → {final_quantity} ({int((yield_mult-1)*100):+d}% from {process_type})")
        if quality_bonus > 0:
            print(f"   Quality: {base_rarity} → {final_rarity} (+{quality_bonus} tiers from {process_type})")

    return item
```

### Tag Examples

**Smelting (Standard):**
```json
{
  "metadata": {
    "tags": ["smelting", "copper", "basic"]
  },
  "outputs": [
    {"materialId": "copper_ingot", "quantity": 1, "rarity": "common"}
  ]
}
```
Result: 1x copper ingot (common) - no modifications (1.0x yield, +0 quality)

**Crushing (+10% Yield):**
```json
{
  "metadata": {
    "tags": ["crushing", "iron", "basic"]
  },
  "outputs": [
    {"materialId": "iron_powder", "quantity": 10, "rarity": "common"}
  ]
}
```
Result: 11x iron powder (common) - crushing gives +10% yield (10 → 11)

**Grinding (+15% Yield):**
```json
{
  "metadata": {
    "tags": ["grinding", "diamond", "advanced"]
  },
  "outputs": [
    {"materialId": "diamond_dust", "quantity": 4, "rarity": "rare"}
  ]
}
```
Result: 5x diamond dust (rare) - grinding gives +15% yield (4 → 4.6 → 5 rounded)

**Purifying (+1 Rarity Tier):**
```json
{
  "metadata": {
    "tags": ["purifying", "mithril", "quality"]
  },
  "outputs": [
    {"materialId": "mithril_ingot", "quantity": 1, "rarity": "uncommon"}
  ]
}
```
Result: 1x mithril ingot (rare) - purifying upgrades uncommon → rare (+1 tier)

**Alloying (+2 Rarity Tiers, -10% Yield):**
```json
{
  "metadata": {
    "tags": ["alloying", "steel", "legendary"]
  },
  "outputs": [
    {"materialId": "damascus_steel", "quantity": 10, "rarity": "uncommon"}
  ]
}
```
Result: 9x damascus steel (epic) - alloying gives -10% yield (10 → 9) but +2 quality tiers (uncommon → epic)

### Process Type Effects

| Process    | Yield Multiplier | Quality Bonus | Use Case                           |
|------------|------------------|---------------|------------------------------------|
| smelting   | 1.0x             | +0            | Standard refining                  |
| crushing   | 1.1x (+10%)      | +0            | More output, same quality          |
| grinding   | 1.15x (+15%)     | +0            | Maximum output, same quality       |
| purifying  | 1.0x             | +1            | Better quality, same quantity      |
| alloying   | 0.9x (-10%)      | +2            | Much better quality, less quantity |

### Rarity Upgrade Tiers

```
common (0) → uncommon (1) → rare (2) → epic (3) → legendary (4)
```

Quality bonus moves up the tier:
- +1: common → uncommon, rare → epic, etc.
- +2: common → rare, uncommon → epic, etc.

---

## Integration Checklist

### Completed Integrations ✓

1. **SmithingTagProcessor**
   - ✅ Integrated into `data/databases/equipment_db.py`
   - ✅ Equipment slot assignment from tags
   - ✅ Tag inheritance (functional tags copied to items)
   - ✅ Redundancy elimination

2. **EngineeringTagProcessor**
   - ✅ Integrated into `core/game_engine.py`
   - ✅ Behavior type assignment (turret/trap/device/station)
   - ✅ Entity type determination from tags
   - ✅ Fallback to legacy logic

3. **EnchantingTagProcessor**
   - ✅ Integrated into `data/models/equipment.py`
   - ✅ Rule validation (weapon/armor/universal)
   - ✅ Graceful failure on wrong application
   - ✅ Backward compatible with `applicableTo` field

### Pending Integrations (Examples Above)

4. **AlchemyTagProcessor**
   - ⏳ Needs integration at alchemy crafting completion
   - ⏳ Use `is_consumable()` to determine item type
   - ⏳ Use `get_effect_type()` for potion effects
   - See example code above for integration pattern

5. **RefiningTagProcessor**
   - ⏳ Needs integration at refining completion
   - ⏳ Use `calculate_output_quantity()` for yield bonuses
   - ⏳ Use `upgrade_rarity()` for quality improvements
   - See example code above for integration pattern

---

## Testing

### Test Smithing Tags
```python
# Create sword with tags
recipe_tags = ["weapon", "sword", "2H", "crushing"]
slot = SmithingTagProcessor.get_equipment_slot(recipe_tags)
assert slot == "mainHand"
inheritable = SmithingTagProcessor.get_inheritable_tags(recipe_tags)
assert "crushing" in inheritable
assert "starter" not in inheritable
```

### Test Engineering Tags
```python
# Create turret from tags
turret_tags = ["turret", "fire", "projectile"]
behavior = EngineeringTagProcessor.get_behavior_type(turret_tags)
assert behavior == "placeable_combat"
```

### Test Enchanting Tags (Graceful Failure)
```python
# Try to apply weapon enchant to armor
weapon_ench_tags = ["weapon", "damage", "sharpness"]
can_apply, reason = EnchantingTagProcessor.can_apply_to_item(weapon_ench_tags, "armor")
assert can_apply == False
assert "not applicable to armor" in reason.lower()
# No crash! Game continues normally
```

### Test Alchemy Tags
```python
# Potion vs transmutation
potion_tags = ["potion", "healing"]
assert AlchemyTagProcessor.is_consumable(potion_tags) == True

transmute_tags = ["transmutation", "gold"]
assert AlchemyTagProcessor.is_consumable(transmute_tags) == False
```

### Test Refining Tags
```python
# Crushing yield bonus
crushing_tags = ["crushing", "iron"]
quantity = RefiningTagProcessor.calculate_output_quantity(10, crushing_tags)
assert quantity == 11  # +10% from crushing

# Purifying quality bonus
purifying_tags = ["purifying", "steel"]
rarity = RefiningTagProcessor.upgrade_rarity("common", purifying_tags)
assert rarity == "uncommon"  # +1 tier from purifying
```

---

## Summary

All tag processors are implemented and ready for use:

- **Smithing**: ✅ Fully integrated into equipment creation
- **Engineering**: ✅ Fully integrated into entity placement
- **Enchanting**: ✅ Fully integrated into enchantment validation
- **Alchemy**: ⏳ Integration examples provided above
- **Refining**: ⏳ Integration examples provided above

The remaining integrations (Alchemy and Refining) can be completed by adding the example code to the appropriate crafting completion handlers.

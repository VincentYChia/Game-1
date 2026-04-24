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
When a refining recipe is completed, use `RefiningTagProcessor` for **probabilistic** bonus rolls (yield and quality upgrades) based on process type tags.

**Design Philosophy:** Tags enhance the base recipe with CHANCE-based bonuses, not deterministic modifiers. Core recipe output remains unchanged.

### Example Code

```python
def complete_refining_recipe(recipe: Dict, base_success_rate: float = 1.0):
    """Complete a refining recipe with probabilistic tag bonuses"""
    from core.crafting_tag_processor import RefiningTagProcessor
    from data.databases import MaterialDatabase

    # Get recipe tags
    recipe_tags = recipe.get('metadata', {}).get('tags', [])

    # Get base output from recipe (UNCHANGED by tags)
    outputs = recipe.get('outputs', [])
    if not outputs:
        return None

    output_data = outputs[0]  # Primary output
    base_quantity = output_data.get('quantity', 1)
    base_rarity = output_data.get('rarity', 'common')
    material_id = output_data.get('materialId')

    # Roll for probabilistic bonuses
    final_quantity, final_rarity = RefiningTagProcessor.calculate_final_output(
        base_quantity, base_rarity, recipe_tags
    )

    # Get bonus info for logging
    bonus_info = RefiningTagProcessor.get_bonus_info(recipe_tags)
    process_type = bonus_info['process_type']

    # Detect if bonuses proc'd
    got_bonus_yield = (final_quantity > base_quantity)
    got_quality_upgrade = (final_rarity != base_rarity)

    # Create output item
    item = create_material_item(
        item_id=material_id,
        quantity=final_quantity,
        rarity=final_rarity,
        max_stack=999
    )

    # Log results
    print(f"✓ Refining complete: {material_id}")
    print(f"   Process: {process_type}")
    print(f"   Base output: {base_quantity}x {base_rarity}")

    if got_bonus_yield:
        bonus_amt = final_quantity - base_quantity
        print(f"   🎲 BONUS YIELD! +{bonus_amt} (from {process_type})")
    elif bonus_info['bonus_yield_chance'] > 0:
        print(f"   No bonus yield ({int(bonus_info['bonus_yield_chance']*100)}% chance)")

    if got_quality_upgrade:
        print(f"   ✨ QUALITY UPGRADE! {base_rarity} → {final_rarity} (from {process_type})")
    elif bonus_info['quality_upgrade_chance'] > 0:
        print(f"   No quality upgrade ({int(bonus_info['quality_upgrade_chance']*100)}% chance)")

    print(f"   Final output: {final_quantity}x {final_rarity}")

    return item
```

### Tag Examples (Probabilistic System)

**Smelting (Standard - No Bonuses):**
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
Result: ALWAYS 1x copper ingot (common) - no bonus chances

**Crushing (25% Chance for +1 Bonus Yield):**
```json
{
  "metadata": {
    "tags": ["smelting", "crushing", "iron", "basic"]
  },
  "outputs": [
    {"materialId": "iron_ingot", "quantity": 1, "rarity": "common"}
  ]
}
```
Possible Results:
- 75% chance: 1x iron ingot (common) - base output
- 25% chance: 2x iron ingot (common) - bonus yield proc!

**Grinding (40% Chance for +1 Bonus Yield):**
```json
{
  "metadata": {
    "tags": ["smelting", "grinding", "diamond", "advanced"]
  },
  "outputs": [
    {"materialId": "diamond_dust", "quantity": 4, "rarity": "rare"}
  ]
}
```
Possible Results:
- 60% chance: 4x diamond dust (rare) - base output
- 40% chance: 5x diamond dust (rare) - bonus yield proc!

**Purifying (30% Chance for +1 Rarity Tier):**
```json
{
  "metadata": {
    "tags": ["smelting", "purifying", "mithril", "legendary"]
  },
  "outputs": [
    {"materialId": "mithril_ingot", "quantity": 1, "rarity": "rare"}
  ]
}
```
Possible Results:
- 70% chance: 1x mithril ingot (rare) - base output
- 30% chance: 1x mithril ingot (epic) - quality upgrade proc!

**Alloying (15% Chance for +2 Rarity Tiers - Very Rare!):**
```json
{
  "metadata": {
    "tags": ["alloying", "bronze", "basic"]
  },
  "outputs": [
    {"materialId": "bronze_ingot", "quantity": 3, "rarity": "common"}
  ]
}
```
Possible Results:
- 85% chance: 3x bronze ingot (common) - base output
- 15% chance: 3x bronze ingot (rare) - quality upgrade proc! (+2 tiers: common → rare)

### Process Type Effects (Probabilistic Bonuses)

| Process    | Bonus Yield Chance | Bonus Yield Amount | Quality Upgrade Chance | Quality Tiers | Use Case                       |
|------------|--------------------|--------------------|------------------------|---------------|--------------------------------|
| smelting   | 0%                 | 0                  | 0%                     | 0             | Standard refining (no bonuses) |
| crushing   | 25%                | +1                 | 0%                     | 0             | Bonus yield chance             |
| grinding   | 40%                | +1                 | 0%                     | 0             | Higher yield chance            |
| purifying  | 0%                 | 0                  | 30%                    | +1            | Quality upgrade chance         |
| alloying   | 0%                 | 0                  | 15%                    | +2            | Rare quality upgrade (+2!)     |

**Key Points:**
- All bonuses are CHANCE-based (probabilistic rolls)
- Base recipe output is NEVER modified (core recipe intact)
- Tags provide ENHANCEMENT opportunities
- Multiple process tags can stack (crushing + purifying = both chances roll)

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

# JSON Generation & Validation Checklist
**Purpose**: Quick reference checklist for creating and validating JSON files
**Last Updated**: November 17, 2025

---

## Pre-Generation Setup

### ✅ Before Starting Mass Generation:
- [ ] Read `JSON Templates` file in Definitions.JSON/
- [ ] Read `templates-crafting-1.JSON` for placement patterns
- [ ] Read `stats-calculations.JSON` for stat formulas
- [ ] Understand the tier progression system (1-4)
- [ ] Review existing JSON files for naming patterns

---

## Equipment Items (items-*.JSON)

### Required Fields:
- [ ] `itemId` - Unique identifier (lowercase, underscores)
- [ ] `name` - Display name
- [ ] `category` - MUST be "equipment" (case-sensitive!)
- [ ] `type` - weapon/sword/axe/mace/armor/helmet/etc
- [ ] `subtype` - shortsword/longsword/greatsword/etc
- [ ] `tier` - Integer 1-4
- [ ] `rarity` - common/uncommon/rare/epic/legendary/mythical/unique
- [ ] `slot` - mainHand/offHand/helmet/chestplate/leggings/boots/gauntlets/accessory
- [ ] `range` - **FLOAT** (1.0 not 1) - See weapon range guide
- [ ] `statMultipliers` - Object with damage/defense/attackSpeed/durability/weight
- [ ] `requirements` - Object with level and stats
- [ ] `flags` - Object with stackable/equippable/repairable
- [ ] `metadata` - Object with narrative and tags

### Weapons Checklist:
- [ ] `range` is appropriate for weapon type (see WEAPON_RANGE_GUIDE)
- [ ] `statMultipliers` includes: damage, attackSpeed, durability, weight
- [ ] `type` is from weapon_types: weapon, sword, axe, mace, dagger, spear, bow, staff
- [ ] `subtype` matches stats-calculations.JSON subtypes

### Armor Checklist:
- [ ] `statMultipliers` includes: defense, durability, weight
- [ ] `type` is from armor_types: armor, helmet, chestplate, leggings, boots, gauntlets
- [ ] `slot` matches type (helmet→helmet, chestplate→chestplate, etc)

### Stat Requirements:
- [ ] Use **AGI** not DEX (DEX is legacy only)
- [ ] Use stat abbreviations: STR, DEF, VIT, LCK, AGI, INT
- [ ] Requirements are reasonable for tier (T1: 10-20, T2: 20-40, T3: 40-70, T4: 70-100)

---

## Materials (materials-*.JSON)

### Required Fields:
- [ ] `materialId` - Unique identifier (lowercase, underscores)
- [ ] `name` - Display name
- [ ] `tier` - Integer 1-4
- [ ] `category` - material type (ore, metal, wood, gem, etc)
- [ ] `rarity` - common/uncommon/rare/epic/legendary
- [ ] `description` - Text description
- [ ] `maxStack` - Integer (99 for raw, 256 for processed)
- [ ] `properties` - Object (can be empty {})

### Material Naming:
- [ ] Raw materials: `{material}_ore`, `{wood}_log`, etc
- [ ] Processed: `{material}_ingot`, `{wood}_plank`, etc
- [ ] Consistency: copper_ore → copper_ingot, oak_log → oak_plank

---

## Crafting Recipes (recipes-*.JSON)

### Common Fields (All Disciplines):
- [ ] `recipeId` - Unique, format: `{discipline}_{item_name}`
- [ ] `stationTier` - Integer 1-4 (required crafting station tier)
- [ ] `stationType` - smithing/refining/alchemy/engineering/enchanting
- [ ] `inputs` - Array of {materialId, quantity}
- [ ] `miniGame` - Optional: {type, difficulty, baseTime}
- [ ] `metadata` - Optional: {narrative, tags}

### Smithing Recipes:
- [ ] `outputId` - Matches equipment itemId
- [ ] `outputQty` - Usually 1 for equipment
- [ ] Placement exists in placements-smithing-1.JSON

### Refining Recipes:
- [ ] `outputs` - Array [{materialId/itemId, quantity, rarity}]
- [ ] `stationTierRequired` - Use this instead of stationTier
- [ ] For ore→ingot: Usually 1:1 ratio
- [ ] For alloys: Multi-core with equal quantities

### Alchemy Recipes:
- [ ] `outputId` - Potion/consumable itemId
- [ ] `outputQty` - Usually 1-5
- [ ] Optional `sequenceLength` - Not used by code

### Engineering Recipes:
- [ ] `outputId` - Device itemId
- [ ] `outputQty` - Usually 1
- [ ] Optional `slotCount` - Not used by code

### Enchanting Recipes:
- [ ] `enchantmentId` - NOT outputId!
- [ ] `enchantmentName` - Display name
- [ ] `stationType` - MUST be "enchanting" NOT "adornments"
- [ ] `applicableTo` - Array: ["weapon"], ["armor"], ["weapon", "tool"]
- [ ] `effect` - Object with type, value, stackable, conflictsWith
- [ ] Effect types: damage_multiplier, defense_multiplier
- [ ] Effect value: Float (0.10 = 10% increase)
- [ ] `conflictsWith` - Array of other enchantment IDs

### Recipe Validation:
- [ ] `outputId` matches an existing itemId or materialId
- [ ] All `inputs[].materialId` exist in materials database
- [ ] Tier is appropriate (T1=basic, T2=intermediate, T3=advanced, T4=legendary)
- [ ] Input quantities are balanced (not too cheap, not too expensive)

---

## Placement Files (placements-*.JSON)

### Smithing Placements:
- [ ] `recipeId` - Matches recipe
- [ ] `gridSize` - "3x3" (T1), "5x5" (T2), "7x7" (T3), "9x9" (T4)
- [ ] `placementMap` - Object {"row,col": "materialId"}
- [ ] Rows and columns start at 1 (not 0!)
- [ ] Pattern fits within grid size
- [ ] Diagonal placement preferred for simple items
- [ ] Asymmetric items face RIGHT

### Refining Placements:
- [ ] `coreInputs` - Array [{materialId, quantity}]
- [ ] `surroundingInputs` - Array [{materialId, quantity}] or []
- [ ] Multi-core recipes: ALL cores have EQUAL quantities
- [ ] Use empty array [] not null for empty surroundingInputs

### Alchemy Placements:
- [ ] `ingredients` - Array [{slot, materialId, quantity}]
- [ ] Slots are sequential: 1, 2, 3, 4...
- [ ] Order matters - chronological addition sequence
- [ ] Slot count matches tier: T1=3, T2=5, T3=7, T4=9

### Engineering Placements:
- [ ] `slots` - Array [{type, materialId, quantity}]
- [ ] Types: FRAME, POWER, FUNCTION, MODIFIER (T3+), UTILITY (T3+)
- [ ] FUNCTION slot determines device type (turret/bomb/trap/utility)
- [ ] Use general materials (iron_ingot, oak_plank, fire_crystal)
- [ ] Slot count: T1=3, T2=5, T3=5, T4=7

### Enchanting Placements:
- [ ] Pattern-based system (see enchanting.py for specifics)

---

## Common Mistakes to Avoid

### ❌ ID Mismatches:
```json
// WRONG:
"recipe": {"outputId": "sword_copper"}
"item": {"itemId": "copper_sword"}

// CORRECT:
"recipe": {"outputId": "copper_sword"}
"item": {"itemId": "copper_sword"}
```

### ❌ Range as Integer:
```json
// WRONG:
"range": 1

// CORRECT:
"range": 1.0
```

### ❌ Wrong Category:
```json
// WRONG - Will not load into EquipmentDatabase:
"category": "weapon"

// CORRECT:
"category": "equipment"
```

### ❌ DEX Instead of AGI:
```json
// DEPRECATED - Use only in legacy items:
"stats": {"DEX": 20}

// CORRECT:
"stats": {"AGI": 20}
```

### ❌ Enchanting Naming:
```json
// WRONG:
"stationType": "adornments"
"recipeId": "adornments_sharpness"

// CORRECT:
"stationType": "enchanting"
"recipeId": "enchanting_sharpness"
```

---

## Quick Reference Values

### Tier Multipliers (from stats-calculations.JSON):
- T1: 1.0x (beginner)
- T2: 2.0x (intermediate)
- T3: 4.0x (advanced)
- T4: 8.0x (legendary)

### Weapon Ranges:
- Dagger: 0.5
- Shortsword: 1.0
- Longsword: 1.0
- Greatsword: 1.5
- Spear: 2.0
- Pike: 3.0
- Halberd: 2.5
- Shortbow: 10.0
- Longbow: 15.0
- Crossbow: 12.0
- Staff: 8.0

### Stack Sizes:
- Raw materials (ore, logs): 99
- Processed materials (ingots, planks): 256
- Equipment: 1 (not stackable)
- Consumables: 99
- Devices: 20

### Stat Requirements by Tier:
- T1: 10-20 stat requirement
- T2: 20-40 stat requirement
- T3: 40-70 stat requirement
- T4: 70-100 stat requirement

---

## Validation Workflow

### Step 1: Create JSON
1. Start with template from `JSON Templates` file
2. Fill in all required fields
3. Choose appropriate tier
4. Calculate stat multipliers if custom
5. Add narrative and tags

### Step 2: Cross-Reference
1. Verify outputId exists as itemId/materialId
2. Verify all input materialIds exist
3. Check tier consistency (T3 recipe shouldn't output T1 item)
4. Verify placement file exists if minigame recipe

### Step 3: Syntax Check
1. Validate JSON syntax (use jsonlint or IDE)
2. Check for trailing commas
3. Verify all strings are quoted
4. Check array and object brackets match

### Step 4: Load Test
1. Add JSON file to appropriate directory
2. Load game and check console for errors
3. Open crafting station to verify recipe appears
4. Attempt to craft item
5. Verify stats display correctly
6. Test in combat if weapon/armor

---

## Mass Generation Strategy

### Recommended Order:
1. **Materials** (foundation) - Create all T1-T4 ores, logs, gems
2. **Refined Materials** (intermediate) - Ingots, planks, alloys
3. **Equipment** (end products) - Weapons, armor, tools
4. **Recipes** (connections) - Link materials to equipment
5. **Placements** (optional) - Minigame patterns

### Batch Creation Tips:
1. Create all T1 items first, then T2, T3, T4
2. Use find-replace to create variants (copper → iron → steel → mithril)
3. Maintain naming consistency (always use pattern: `{material}_{item}`)
4. Keep a spreadsheet of all IDs to avoid duplicates
5. Test each batch before moving to next tier

### Quality Control:
1. Run JSON validator on all files
2. Load all files in game simultaneously
3. Check for missing material errors
4. Verify crafting progression makes sense
5. Test combat balance

---

## File Organization

### Where to Put Files:
- Materials: `materials.JSON/materials-{category}-1.JSON`
- Equipment: `items.JSON/items-{discipline}-2.JSON`
- Recipes: `recipes.JSON/recipes-{discipline}-{version}.JSON`
- Placements: `placements.JSON/placements-{discipline}-1.JSON`

### Naming Conventions:
- Use lowercase for file names
- Use underscores for item IDs
- Use version numbers for iterations
- Keep discipline names consistent

---

## Final Checklist Before Commit

- [ ] All JSON files have valid syntax
- [ ] No duplicate IDs across all files
- [ ] All recipe outputIds match existing items
- [ ] All input materialIds exist
- [ ] Range values are floats not integers
- [ ] Category is "equipment" for all equipment
- [ ] StationType is "enchanting" not "adornments"
- [ ] Stat requirements use AGI not DEX
- [ ] Tested loading in game without errors
- [ ] Tested crafting at least one item per tier
- [ ] Combat tested with weapons
- [ ] Defense tested with armor

---

## Resources

- **Templates**: `Definitions.JSON/JSON Templates`
- **Placement Patterns**: `Definitions.JSON/templates-crafting-1.JSON`
- **Stat Formulas**: `Definitions.JSON/stats-calculations.JSON`
- **Naming Guide**: `claude-context/NAMING_CONVENTIONS.md`
- **Validation Report**: `claude-context/JSON_VALIDATION_REPORT.md`
- **Existing Examples**: Check `items.JSON/items-smithing-2.JSON` for working examples

---

## Getting Help

### If Recipe Won't Craft:
1. Check outputId matches itemId exactly
2. Verify all input materialIds exist
3. Check stationTier requirement
4. Verify character has required materials
5. Check console for error messages

### If Item Won't Load:
1. Check category is "equipment"
2. Verify JSON syntax is valid
3. Check all required fields are present
4. Verify range is float not integer
5. Check console for loading errors

### If Stats Show as 0:
1. Check type is in weapon_types or armor_types
2. Verify statMultipliers are present
3. Check tier is 1-4
4. Verify subtype matches stats-calculations.JSON

---

**Remember**: When in doubt, copy from working examples and modify. Don't invent new field names!

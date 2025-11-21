# Game JSON Naming Conventions

**Version**: 1.0
**Last Updated**: 2025-11-21
**Purpose**: Official naming standards for JSON fields, files, and identifiers

---

## Critical Convention: Adornments vs Enchanting

### ⚠️ ALWAYS Use "adornments" NOT "enchanting"

**Rationale**: The game's internal systems use "adornments" as the official discipline name for the enchanting/adornment crafting system.

### Where This Applies

#### 1. Recipe Files
```
✓ CORRECT: recipes-adornments-1.json
❌ WRONG:   recipes-enchanting-1.JSON
```

**Current Status**: `recipes-enchanting-1.JSON` exists but is deprecated/incomplete (712 lines vs 1242 lines in adornments version)

#### 2. Placement Files
```
✓ CORRECT: placements-adornments-1.JSON
❌ WRONG:   placements-enchanting-1.JSON
```

#### 3. Station Type Field
```json
✓ CORRECT:
{
  "stationType": "adornments",
  ...
}

❌ WRONG:
{
  "stationType": "enchanting",
  ...
}
```

#### 4. Database/Code References
```python
✓ CORRECT:
recipes_by_station = {
    "smithing": [],
    "alchemy": [],
    "refining": [],
    "engineering": [],
    "adornments": []  # NOT "enchanting"
}

❌ WRONG:
recipes_by_station = {
    ...
    "enchanting": []  # Will not work!
}
```

### Why the Confusion?

The terms "enchanting" and "adornments" are sometimes used interchangeably in documentation and narrative text, but the game code **only recognizes "adornments"** as the official station type.

- **Narrative/Flavor Text**: Can use "enchanting" (e.g., "enchanting recipes with structured effects")
- **JSON Field Values**: MUST use "adornments"
- **File Names**: MUST use "adornments"
- **Code**: MUST use "adornments"

---

## File Naming Conventions

### Pattern: `{category}-{discipline}-{version}.{ext}`

#### Items
```
items-{discipline}-{version}.JSON

Examples:
  items-smithing-2.JSON      (equipment and stations)
  items-smithing-1.JSON      (devices - turrets, bombs, traps)
  items-alchemy-1.JSON       (consumables and equipment)
  items-tools-1.JSON         (pickaxes, axes)
  items-materials-1.JSON     (raw materials)
  items-refining-1.JSON      (processed materials)
```

#### Recipes
```
recipes-{discipline}-{version}.{ext}

Examples:
  recipes-smithing-3.JSON    (latest smithing recipes)
  recipes-alchemy-1.JSON
  recipes-refining-1.JSON
  recipes-engineering-1.JSON
  recipes-adornments-1.json  (NOTE: lowercase .json!)
```

#### Placements
```
placements-{discipline}-{version}.JSON

Examples:
  placements-smithing-1.JSON
  placements-alchemy-1.JSON
  placements-refining-1.JSON
  placements-engineering-1.JSON
  placements-adornments-1.JSON
```

#### Skills
```
skills-{type}-{version}.JSON

Examples:
  skills-skills-1.JSON        (main skills file)
  skills-base-effects-1.JSON  (supporting data)
```

#### Progression
```
{type}-{version}.JSON  OR  {type}-{variant}.JSON

Examples:
  classes-1.JSON
  titles-1.JSON
  quests-1.JSON
  quests-enhanced.JSON        (enhanced version)
  npcs-1.JSON
  npcs-enhanced.JSON          (enhanced version)
  skill-unlocks.JSON          (no version number)
```

### File Extension Rules

- **Standard**: Uppercase `.JSON`
- **Exceptions**: Some recipe files use lowercase `.json`
  - `recipes-smithing-3.json`
  - `recipes-adornments-1.json`

**Code Impact**: File loaders must handle both `.JSON` and `.json` extensions.

---

## Field Naming Conventions

### Item IDs

**Pattern**: `{material}_{item_type}`
**Format**: `snake_case`

```
✓ CORRECT:
  iron_sword
  copper_pickaxe
  health_potion
  basic_arrow_turret
  mithril_ingot

❌ WRONG:
  IronSword           (camelCase)
  iron-sword          (kebab-case)
  Iron_Sword          (PascalCase)
```

### Recipe IDs

**Pattern**: `{discipline}_{output_id}` OR `{discipline}_{enchantment_name}`
**Format**: `snake_case`

```
✓ CORRECT:
  smithing_iron_sword
  alchemy_health_potion
  refining_iron_ingot
  engineering_arrow_turret
  enchanting_sharpness_basic    (NOTE: recipe ID can use "enchanting")

❌ WRONG:
  iron_sword_recipe
  make_iron_sword
  IronSwordRecipe
```

**Special Case**: For adornments/enchanting recipes, the recipe ID can use "enchanting_" prefix for clarity, but the `stationType` field must be "adornments".

### Display Names

**Format**: `Title Case`

```
✓ CORRECT:
  "Iron Sword"
  "Health Potion"
  "Copper Pickaxe"

❌ WRONG:
  "iron sword"
  "IRON SWORD"
  "Iron sword"
```

### Category Field Values

**Valid Categories**:
- `"equipment"` - Weapons, armor, tools (goes in equipment database)
- `"consumable"` - Potions, food, temporary items
- `"device"` - Turrets, bombs, traps, gadgets
- `"station"` - Crafting stations
- `"material"` - Raw and processed materials

**Important**: Category determines which database loads the item!

---

## Discipline Names

**Official Discipline Names** (use exactly as shown):

1. `smithing` - NOT "blacksmithing", "forging", or "metalworking"
2. `alchemy` - NOT "brewing", "potion-making", or "herbalism"
3. `refining` - NOT "smelting", "processing", or "metallurgy"
4. `engineering` - NOT "tinkering", "gadgeteering", or "devices"
5. `adornments` - NOT "enchanting", "augmentation", or "enhancement"

---

## Station Type Values

**Valid stationType Values**:
```json
{
  "stationType": "smithing"      ✓
  "stationType": "alchemy"       ✓
  "stationType": "refining"      ✓
  "stationType": "engineering"   ✓
  "stationType": "adornments"    ✓
  "stationType": "enchanting"    ❌ INVALID - Use "adornments"!
}
```

---

## Special Field Naming Cases

### Refining Recipes

Refining uses **different field names** than other disciplines:

```json
// Standard recipes (smithing, alchemy, engineering, adornments)
{
  "outputId": "iron_sword",
  "outputQty": 1,
  "stationTier": 2
}

// Refining recipes (DIFFERENT!)
{
  "outputs": [                    // Note: array, not single value
    {
      "materialId": "iron_ingot", // Note: materialId not itemId
      "quantity": 1,
      "rarity": "common"
    }
  ],
  "stationTierRequired": 1        // Note: different field name!
}
```

### Items in items-refining-1.JSON

**Special Case**: Uses `itemId` not `materialId`:

```json
✓ CORRECT (in items-refining-1.JSON):
{
  "itemId": "iron_ingot",    // Use itemId, not materialId!
  "name": "Iron Ingot",
  "category": "material",
  ...
}
```

**Rationale**: Items-refining contains items, not materials, even though they're loaded into the materials database.

---

## Category-Specific Conventions

### Equipment Items

```json
{
  "itemId": "iron_sword",
  "name": "Iron Sword",
  "category": "equipment",        // MUST be "equipment"!
  "type": "weapon",               // weapon|armor|tool
  "subtype": "shortsword",        // Specific subtype
  "slot": "mainHand",             // Equipment slot
  ...
}
```

**Critical**: `category` must be `"equipment"` or the item won't load into the equipment database!

### Stackable Devices

```json
{
  "itemId": "basic_arrow_turret",
  "name": "Basic Arrow Turret",
  "category": "device",           // Category is "device"
  "type": "turret",
  "flags": {
    "stackable": true,            // MUST be stackable!
    "placeable": true
  },
  "stackSize": 5,
  ...
}
```

### Stackable Consumables

```json
{
  "itemId": "health_potion",
  "name": "Health Potion",
  "category": "consumable",       // Category is "consumable"
  "flags": {
    "stackable": true             // MUST be stackable!
  },
  "stackSize": 99,
  ...
}
```

---

## Common Mistakes

### ❌ Mistake 1: Using "enchanting" as stationType

```json
❌ WRONG:
{
  "stationType": "enchanting"
}

✓ CORRECT:
{
  "stationType": "adornments"
}
```

**Impact**: Recipe will not load, station type not recognized.

### ❌ Mistake 2: Wrong field name in refining recipes

```json
❌ WRONG (refining):
{
  "outputId": "iron_ingot",
  "stationTier": 1
}

✓ CORRECT (refining):
{
  "outputs": [{"materialId": "iron_ingot", "quantity": 1}],
  "stationTierRequired": 1
}
```

**Impact**: Recipe format not recognized, won't parse correctly.

### ❌ Mistake 3: Missing category for equipment

```json
❌ WRONG:
{
  "itemId": "iron_sword",
  "name": "Iron Sword",
  // Missing category field!
  "type": "weapon",
  ...
}

✓ CORRECT:
{
  "itemId": "iron_sword",
  "name": "Iron Sword",
  "category": "equipment",  // Required!
  "type": "weapon",
  ...
}
```

**Impact**: Item won't load as equipment, might be skipped entirely.

### ❌ Mistake 4: Non-stackable items as materials

```json
❌ WRONG:
{
  "itemId": "health_potion",
  "category": "consumable",
  "flags": {
    "stackable": false  // Should be true!
  }
}

✓ CORRECT:
{
  "itemId": "health_potion",
  "category": "consumable",
  "flags": {
    "stackable": true   // Must be stackable to load as material!
  }
}
```

**Impact**: Item won't load into materials database.

---

## Version Number Conventions

### Use Latest Version Only

When multiple versions exist, **only the latest version is loaded**:

```
✓ LOAD: recipes-smithing-3.JSON    (version 3)
❌ SKIP: recipes-smithing-2.JSON    (old version)
❌ SKIP: recipes-smithing-1.JSON    (old version)

✓ LOAD: items-smithing-2.JSON      (version 2)
❌ SKIP: items-smithing-1.JSON      (loaded for devices only, not equipment)
```

### Version Numbering

- Start at `1`
- Increment for each iteration
- No leading zeros (`-1` not `-01`)
- No decimal versions (`-1` not `-1.0`)

---

## Summary Checklist

When creating new JSONs, verify:

- [ ] Use "adornments" for enchanting discipline (NOT "enchanting")
- [ ] Item IDs in snake_case
- [ ] Display names in Title Case
- [ ] Category field present and correct
- [ ] Station type matches official names
- [ ] Refining recipes use `outputs` array format
- [ ] Stackable flag set for consumables/devices
- [ ] File named with correct discipline and version
- [ ] Using latest version number
- [ ] Extension matches convention (.JSON or .json for specific files)

---

**For Questions**: Refer to `FILE_VERSION_REGISTRY.txt` for file version details and `GAME_JSON_LOADING_ANALYSIS.md` for implementation details.

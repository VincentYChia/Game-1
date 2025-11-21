# JSON Loading Discrepancies and Game Implementation Analysis

**Date**: 2025-11-21
**Purpose**: Document actual JSON loading behavior in Game-1-modular vs initial assumptions
**Source**: Analysis of `data/databases/*.py` and `core/game_engine.py`

---

## Executive Summary

After investigating the actual game code, several important discrepancies were found between the initial schema assumptions and the real implementation:

1. **Version-Specific Loading**: Game loads specific file versions, not all versions
2. **Station Type**: Uses "adornments" not "enchanting"
3. **File Count**: ~500 items loaded, not 900+ (was counting duplicates from multiple versions)
4. **Mixed Extensions**: Some files use `.json` (lowercase), others `.JSON` (uppercase)
5. **Conditional Loading**: Equipment and materials loaded from same files with different filters

---

## Exact Files Loaded by Game

### Items/Equipment (Equipment Database)

**Load Logic**: `category == 'equipment'` only

Files loaded:
```python
# Line 95-98 in game_engine.py
equip_db.load_from_file("items.JSON/items-smithing-1.JSON")  # Equipment only
equip_db.load_from_file("items.JSON/items-smithing-2.JSON")  # Equipment only
equip_db.load_from_file("items.JSON/items-tools-1.JSON")     # Tools
equip_db.load_from_file("items.JSON/items-alchemy-1.JSON")   # Equipment only
```

**Important**:
- `items-smithing-1.JSON` is loaded for equipment
- `items-smithing-2.JSON` is ALSO loaded (contains additional weapons/armor)
- `items-smithing-3.JSON` is NOT loaded by the game

**NOT loaded for equipment**:
- `items-materials-1.JSON` (materials only)
- `items-refining-1.JSON` (ingots/planks only)

---

### Materials (Material Database)

**Load Logic**: Loads from multiple sources with different filters

Files loaded:
```python
# Lines 79-87 in game_engine.py
MaterialDatabase.get_instance().load_from_file("items.JSON/items-materials-1.JSON")
MaterialDatabase.get_instance().load_refining_items("items.JSON/items-refining-1.JSON")
MaterialDatabase.get_instance().load_stackable_items("items.JSON/items-alchemy-1.JSON", categories=['consumable'])
MaterialDatabase.get_instance().load_stackable_items("items.JSON/items-smithing-1.JSON", categories=['device'])
```

**Important**:
- `items-materials-1.JSON`: Expects `materials` array (not nested sections)
- `items-refining-1.JSON`: Loads from sections `basic_ingots`, `alloys`, `wood_planks` (uses `itemId` not `materialId`!)
- `items-alchemy-1.JSON`: Loads items where `flags.stackable == True` AND `category == 'consumable'`
- `items-smithing-1.JSON`: Loads items where `flags.stackable == True` AND `category == 'device'`

---

### Recipes (Recipe Database)

**Load Logic**: Discipline-specific files, version-specific

Files loaded:
```python
# Lines 27-30 in recipe_db.py
"recipes-smithing-3.json"      # Version 3, lowercase .json
"recipes-alchemy-1.JSON"       # Version 1, uppercase .JSON
"recipes-refining-1.JSON"      # Version 1, uppercase .JSON
"recipes-engineering-1.JSON"   # Version 1, uppercase .JSON
"recipes-adornments-1.json"    # Version 1, lowercase .json, uses "adornments" NOT "enchanting"
```

**Important**:
- Smithing uses version **3** (not 1 or 2)
- Mixed case extensions: `.json` vs `.JSON`
- Station type is **"adornments"** not "enchanting" (line 16, 30 in recipe_db.py)
- Refining recipes use `outputs` array instead of `outputId` (line 59-66)
- Enchanting recipes use `enchantmentId` instead of `outputId` (line 54)

---

### Placements (Placement Database)

**Load Logic**: One file per discipline, all version 1

Files loaded:
```python
# Lines 28-40 in placement_db.py
"placements.JSON/placements-smithing-1.JSON"
"placements.JSON/placements-refining-1.JSON"
"placements.JSON/placements-alchemy-1.JSON"
"placements.JSON/placements-engineering-1.JSON"
"placements.JSON/placements-adornments-1.JSON"  # Note: "adornments" not "enchanting"
```

**Important**:
- All placements expect `placements` array (line 57)
- Different loading functions for each discipline type

---

### Skills (Skill Database)

Files loaded:
```python
# Line 102 in game_engine.py
"Skills/skills-skills-1.JSON"
```

**Important**: Filename is `skills-skills-1.JSON` (double "skills")

---

### Titles (Title Database)

Files loaded:
```python
# Line 100 in game_engine.py
"progression/titles-1.JSON"
```

---

### Classes (Class Database)

Files loaded:
```python
# Line 101 in game_engine.py
"progression/classes-1.JSON"
```

---

### NPCs & Quests (NPC Database)

**Load Logic**: Tries enhanced format first, falls back to v1.0

Files loaded (in order of priority):
```python
# Lines 30-36 in npc_db.py
"progression/npcs-enhanced.JSON"  # Try first (v2.0 format)
"progression/npcs-1.JSON"         # Fallback (v1.0 format)
```

**Important**:
- Supports both dialogue formats
- Enhanced format has nested dialogue object
- v1.0 format has flat `dialogue_lines` array
- Quests loaded from `quests-1.JSON` separately (line 93-118 in npc_db.py)

---

## Schema Discrepancies

### 1. Recipe Station Types

**WRONG**:
```json
{
  "stationType": "enchanting"  // ❌ Not recognized
}
```

**CORRECT**:
```json
{
  "stationType": "adornments"  // ✓ Actual station type used in game
}
```

### 2. Refining Recipe Format

**WRONG**:
```json
{
  "outputId": "iron_ingot",  // ❌ Not used in refining
  "outputQty": 1
}
```

**CORRECT**:
```json
{
  "outputs": [  // ✓ Refining uses outputs array
    {
      "materialId": "iron_ingot",
      "quantity": 1,
      "rarity": "common"
    }
  ],
  "stationTierRequired": 1  // Note: different field name
}
```

### 3. Equipment vs Materials Split

**KEY INSIGHT**: Same JSON files are loaded TWICE with different filters:

- `items-smithing-1.JSON`:
  - Loaded by EquipmentDatabase with filter `category == 'equipment'`
  - Loaded by MaterialDatabase with filter `flags.stackable == True AND category == 'device'`

- `items-alchemy-1.JSON`:
  - Loaded by EquipmentDatabase with filter `category == 'equipment'`
  - Loaded by MaterialDatabase with filter `flags.stackable == True AND category == 'consumable'`

### 4. Items-Refining Field Names

**IMPORTANT**: `items-refining-1.JSON` uses `itemId` NOT `materialId`:

```json
{
  "itemId": "iron_ingot",  // ✓ Correct field name
  "name": "Iron Ingot",
  "category": "material",
  "stackSize": 256
}
```

---

## Item Count Reconciliation

### Initial Estimate: 900+ items
**Problem**: Was counting ALL versions of files

### Actual Count: ~500 items
**Reason**: Game only loads specific versions:

Equipment files:
- `items-smithing-1.JSON` (devices and some equipment) ~ 70 items
- `items-smithing-2.JSON` (weapons and armor) ~ 150 items
- `items-tools-1.JSON` (tools) ~ 20 items
- `items-alchemy-1.JSON` (potions as equipment) ~ 30 items

Material files:
- `items-materials-1.JSON` ~ 100 materials
- `items-refining-1.JSON` (ingots, planks) ~ 40 materials
- Stackable consumables from alchemy ~ 30 items
- Stackable devices from smithing ~ 20 items

Recipes:
- `recipes-smithing-3.json` ~ 60 recipes
- `recipes-alchemy-1.JSON` ~ 20 recipes
- `recipes-refining-1.JSON` ~ 20 recipes
- `recipes-engineering-1.JSON` ~ 15 recipes
- `recipes-adornments-1.json` ~ 25 recipes

**Total: ~500-600 total game objects**

---

## Database Field Mappings

### Equipment (from equipment_db.py)

**Fields Expected in JSON**:
```python
{
    "itemId": str,           # REQUIRED
    "name": str,             # REQUIRED
    "category": "equipment", # MUST be "equipment" to load!
    "type": str,            # weapon|armor|tool
    "subtype": str,         # shortsword|longsword|etc
    "tier": int,            # 1-4
    "rarity": str,          # common|uncommon|rare|epic|legendary
    "slot": str,            # mainHand|helmet|chestplate|etc
    "range": float,         # Weapon range (float required!)
    "statMultipliers": {    # Used for calculations
        "damage": float,
        "attackSpeed": float,
        "durability": float,
        "weight": float
    },
    "stats": {              # OLD FORMAT (placeholders)
        "damage": [int, int],
        "defense": int,
        "durability": [int, int],
        "attackSpeed": float
    },
    "requirements": {
        "level": int,
        "stats": {}
    }
}
```

**Important**:
- `stats` is legacy format for placeholders
- `statMultipliers` used for calculation formulas
- Both may exist in JSONs

### Materials (from material_db.py)

**Fields Expected**:
```python
{
    "materialId": str,  # Or "itemId" for refining items!
    "name": str,
    "tier": int,
    "category": str,    # ore|metal|wood|gem|consumable|device
    "rarity": str,
    "description": str,
    "maxStack": int,    # 99 for raw, 256 for processed
    "properties": {}
}
```

**For Stackable Items**:
```python
{
    "itemId": str,      # Note: uses itemId!
    "flags": {
        "stackable": True  # MUST be True to load as material
    },
    "stackSize": int    # Uses stackSize not maxStack
}
```

### Recipes (from recipe_db.py)

**Standard Format (smithing/alchemy/engineering)**:
```python
{
    "recipeId": str,
    "outputId": str,        # Item produced
    "outputQty": int,
    "stationType": str,     # "smithing"|"alchemy"|"engineering"|"adornments"
    "stationTier": int,     # 1-4
    "inputs": [
        {"materialId": str, "quantity": int}
    ]
}
```

**Refining Format**:
```python
{
    "recipeId": str,
    "outputs": [            # Uses outputs array!
        {
            "materialId": str,
            "quantity": int,
            "rarity": str
        }
    ],
    "stationTierRequired": int,  # Different field name!
    "inputs": [...]
}
```

**Enchanting Format (adornments)**:
```python
{
    "recipeId": str,
    "enchantmentId": str,   # NOT outputId!
    "enchantmentName": str,
    "stationType": "adornments",  # Must be "adornments"
    "stationTier": int,
    "applicableTo": [str],  # Item types that can be enchanted
    "effect": {},
    "inputs": [...]
}
```

---

## Recommendations for Unified JSON Creator

### 1. File Loading Strategy

**Load ONLY these specific files**:

```python
FILES_TO_LOAD = {
    "items": [
        "items.JSON/items-smithing-1.JSON",
        "items.JSON/items-smithing-2.JSON",  # Not 3!
        "items.JSON/items-tools-1.JSON",
        "items.JSON/items-alchemy-1.JSON",
        "items.JSON/items-materials-1.JSON",
        "items.JSON/items-refining-1.JSON",
    ],
    "recipes": [
        "recipes.JSON/recipes-smithing-3.json",    # Version 3!
        "recipes.JSON/recipes-alchemy-1.JSON",
        "recipes.JSON/recipes-refining-1.JSON",
        "recipes.JSON/recipes-engineering-1.JSON",
        "recipes.JSON/recipes-adornments-1.json",  # "adornments" not "enchanting"
    ],
    "placements": [
        "placements.JSON/placements-smithing-1.JSON",
        "placements.JSON/placements-refining-1.JSON",
        "placements.JSON/placements-alchemy-1.JSON",
        "placements.JSON/placements-engineering-1.JSON",
        "placements.JSON/placements-adornments-1.JSON",
    ],
    "skills": [
        "Skills/skills-skills-1.JSON",
    ],
    "titles": [
        "progression/titles-1.JSON",
    ],
    "classes": [
        "progression/classes-1.JSON",
    ],
    "npcs": [
        "progression/npcs-enhanced.JSON",  # Try first
        "progression/npcs-1.JSON",         # Fallback
    ],
    "quests": [
        "progression/quests-1.JSON",
    ]
}
```

### 2. Station Type Enum

**Update enum values**:
```python
enum_values=["smithing", "alchemy", "refining", "engineering", "adornments"]
# NOT "enchanting"!
```

### 3. Display File Source

Add metadata showing which file each JSON was loaded from:
```python
{
    "itemId": "iron_sword",
    "_source_file": "items.JSON/items-smithing-2.JSON",
    "_loaded_as": "equipment"
}
```

### 4. Category Filtering

When displaying library:
- Equipment: Show items with `category == 'equipment'` AND source from equipment files
- Materials: Show items from materials files OR stackable items
- Recipes: Show by discipline with correct station type

### 5. Validation Updates

**Add warnings for**:
- Using "enchanting" instead of "adornments"
- Using `outputId` in refining recipes (should use `outputs`)
- Using `stationTier` in refining (should use `stationTierRequired`)
- Using `materialId` in items-refining (should use `itemId`)

---

## Testing Validation

To verify correct implementation, check:

1. ✓ Total items loaded: ~500-600 (not 900+)
2. ✓ Smithing recipes from version 3 file
3. ✓ Station type "adornments" recognized
4. ✓ items-smithing-1 and -2 loaded, NOT -3
5. ✓ Materials include ingots from items-refining-1.JSON
6. ✓ Stackable consumables loaded from items-alchemy-1.JSON
7. ✓ Stackable devices loaded from items-smithing-1.JSON

---

## Unsupported/Unclear JSON Types

**Currently NOT loaded by game**:
- Enemies/Hostile entities (no loader found)
- Resource nodes (no loader found)

**Note**: These types were mentioned in documentation but have no corresponding database loaders in the current game code. They may be future additions or handled differently.

---

## File Extension Inconsistency

**Mixed case extensions found**:
- Lowercase `.json`: `recipes-smithing-3.json`, `recipes-adornments-1.json`
- Uppercase `.JSON`: Most other files

**Recommendation**: Support both patterns in glob matching.

---

## Conclusion

The game's JSON loading is more specific and nuanced than initially documented:
- Uses specific file versions, not all versions
- Loads same files multiple times with different filters
- Uses "adornments" not "enchanting"
- Has format variations between disciplines (refining uses `outputs`)
- Mixed field names (`itemId` vs `materialId`, `stationTier` vs `stationTierRequired`)

The Unified JSON Creator must match this exact behavior to provide accurate validation and prevent creating JSONs that won't be loaded by the game.

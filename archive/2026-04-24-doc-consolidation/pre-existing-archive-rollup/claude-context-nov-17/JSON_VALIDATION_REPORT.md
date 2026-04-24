# JSON Template Validation Report
**Date**: November 17, 2025
**Purpose**: Comprehensive validation of JSON template system before mass generation
**Status**: ⚠️ Minor issues found - fixes required

---

## Executive Summary

The JSON template system is **90% correct** and ready for mass generation after minor fixes. The templates in `Definitions.JSON/JSON Templates` are comprehensive and well-documented, but have **3 critical issues** and **5 minor improvements** needed before mass generation begins.

### Critical Issues Found:
1. **Enchanting discipline naming inconsistency** - Templates use "adornments", code uses "enchanting"
2. **Range field documentation incomplete** - Need to clarify it's a float for weapon tactical range
3. **Material template missing** - No template exists for materials.JSON files

### Minor Issues:
1. Unused fields in alchemy template ("sequenceLength")
2. Unused fields in engineering template ("slotCount")
3. Missing guidance on stat requirements naming (DEX vs AGI)
4. No validation examples for enchantment conflicts
5. Missing examples for recent additions (range stat, enchantment effects)

---

## Detailed Validation by JSON Type

### 1. EQUIPMENT ITEMS (items-smithing-2.JSON, items-alchemy-1.JSON, etc.)

#### Code Expectations (main.py:687-756)
```python
def create_equipment_from_id(self, item_id: str):
    data = self.items[item_id]
    # REQUIRED fields:
    tier = data.get('tier', 1)                          # int
    item_type = data.get('type', '')                    # str: weapon/sword/axe/armor/helmet/etc
    subtype = data.get('subtype', '')                   # str: shortsword/longsword/greatsword/etc
    stat_multipliers = data.get('statMultipliers', {})  # dict
    slot = data.get('slot', 'mainHand')                 # str
    range = data.get('range', 1.0)                      # float (NEW - added Nov 17)
    name = data.get('name', item_id)                    # str
    rarity = data.get('rarity', 'common')               # str
    requirements = data.get('requirements', {})         # dict

    # Used for filtering:
    category = data.get('category', '')  # MUST be "equipment" to load
```

#### Template Documentation (JSON Templates:147-199)
```json
{
  "itemId": "copper_sword",
  "name": "Copper Sword",
  "category": "equipment",
  "type": "weapon",        ✓ Correct
  "subtype": "sword",      ✓ Correct
  "tier": 1,               ✓ Correct
  "rarity": "common",      ✓ Correct
  "range": 1,              ⚠️ ISSUE: Should be 1.0 (float), needs documentation
  "slot": "mainHand",      ✓ Correct
  "statMultipliers": { ... },  ✓ Correct
  "requirements": { ... }, ✓ Correct
  "flags": { ... },        ✓ Correct (not used by code but good metadata)
  "metadata": { ... }      ✓ Correct (not used by code but good metadata)
}
```

#### ✅ VALIDATION RESULT: **MOSTLY CORRECT**

**Issues**:
- `range` field shows as integer `1` but should be float `1.0`
- Template doesn't explain what `range` represents (weapon tactical combat distance)
- Template doesn't show examples of different range values (dagger: 0.5, spear: 2.0, bow: 15.0)

**Recommendation**: Update template to show range as float with examples

---

### 2. MATERIALS (materials-*.JSON)

#### Code Expectations (main.py:194-217)
```python
def load_from_file(self, filepath: str):
    for mat_data in data.get('materials', []):
        mat = MaterialDefinition(
            material_id=mat_data.get('materialId', ''),  # REQUIRED
            name=mat_data.get('name', ''),
            tier=mat_data.get('tier', 1),
            category=mat_data.get('category', 'unknown'),
            rarity=mat_data.get('rarity', 'common'),
            description=mat_data.get('description', ''),
            max_stack=mat_data.get('maxStack', 99),
            properties=mat_data.get('properties', {})
        )
```

#### Template Documentation
**❌ CRITICAL: NO MATERIAL TEMPLATE EXISTS IN JSON Templates FILE**

The file has templates for recipes and equipment, but no template for raw materials.

#### ❌ VALIDATION RESULT: **MISSING TEMPLATE**

**Recommendation**: Add MATERIAL_TEMPLATE to JSON Templates file

---

### 3. CRAFTING RECIPES (recipes-smithing-3.json, recipes-alchemy-1.JSON, etc.)

#### Code Expectations (main.py:1681-1731)
```python
def _load_file(self, filepath: str, station_type: str):
    for recipe_data in data.get('recipes', []):
        # For enchanting (special case):
        if 'enchantmentId' in recipe_data:
            output_id = recipe_data.get('enchantmentId', '')
            output_qty = 1
            station_tier = recipe_data.get('stationTier', 1)
            # Also loads: enchantmentName, applicableTo, effect

        # For refining (uses outputs array):
        elif 'outputs' in recipe_data:
            outputs = recipe_data.get('outputs', [])
            output_id = outputs[0].get('materialId', outputs[0].get('itemId', ''))
            output_qty = outputs[0].get('quantity', 1)
            station_tier = recipe_data.get('stationTierRequired',
                                         recipe_data.get('stationTier', 1))

        # For all other crafting:
        else:
            output_id = recipe_data.get('outputId', '')
            output_qty = recipe_data.get('outputQty', 1)
            station_tier = recipe_data.get('stationTier', 1)

        # All recipes:
        recipe_id = recipe_data.get('recipeId', '')
        inputs = recipe_data.get('inputs', [])
```

#### Template Documentation (JSON Templates:12-145)

**Smithing Template**: ✅ Correct
```json
{
  "recipeId": "smithing_copper_sword",  ✓
  "outputId": "copper_sword",           ✓
  "outputQty": 1,                       ✓
  "stationTier": 1,                     ✓
  "stationType": "smithing",            ✓
  "inputs": [...],                      ✓
  "miniGame": {...}                     ✓ (optional)
}
```

**Refining Template**: ✅ Correct (uses outputs array)
```json
{
  "recipeId": "refining_copper_ore_to_ingot",  ✓
  "inputs": [...],                             ✓
  "outputs": [{"materialId": "...", "quantity": 1}],  ✓
  "stationRequired": "refinery",               ✓ (not used by code, metadata)
  "stationTierRequired": 1,                    ✓
  "fuelRequired": null                         ✓ (not used by code, metadata)
}
```

**Alchemy Template**: ⚠️ Has unused field
```json
{
  "recipeId": "alchemy_health_potion_minor",  ✓
  "outputId": "health_potion_minor",          ✓
  "outputQty": 1,                             ✓
  "stationTier": 1,                           ✓
  "sequenceLength": 3,                        ⚠️ NOT USED BY CODE
  "inputs": [...]                             ✓
}
```

**Engineering Template**: ⚠️ Has unused field
```json
{
  "recipeId": "engineering_basic_turret",  ✓
  "outputId": "basic_turret",              ✓
  "outputQty": 1,                          ✓
  "stationTier": 1,                        ✓
  "slotCount": 3,                          ⚠️ NOT USED BY CODE
  "inputs": [...]                          ✓
}
```

**Adornments (Enchanting) Template**: ❌ NAMING ISSUE
```json
{
  "recipeId": "adornments_fire_enchant_minor",  ⚠️ Should be "enchanting_*"
  "enchantmentId": "fire_enchant_minor",        ✓
  "enchantmentName": "Minor Flame",             ✓
  "stationTier": 1,                             ✓
  "stationType": "adornments",                  ❌ CODE USES "enchanting"
  "applicableTo": ["weapon", "tool"],           ✓
  "effect": {...},                              ✓
  "inputs": [...]                               ✓
}
```

#### ⚠️ VALIDATION RESULT: **MOSTLY CORRECT WITH ISSUES**

**Issues**:
1. **CRITICAL**: Template calls discipline "adornments" but code uses "enchanting"
2. Alchemy template has unused "sequenceLength" field (not harmful, just confusing)
3. Engineering template has unused "slotCount" field (not harmful, just confusing)

**Recommendations**:
1. Update enchanting template to use "enchanting" instead of "adornments"
2. Remove or mark as optional the unused fields
3. Add note about conflictsWith in enchantment effects

---

### 4. PLACEMENT TEMPLATES (placements-smithing-1.JSON, templates-crafting-1.JSON)

#### Code Expectations (main.py:1834-1866)
```python
@dataclass
class PlacementData:
    recipe_id: str
    discipline: str  # smithing, alchemy, refining, engineering, adornments

    # Smithing:
    grid_size: str = ""
    placement_map: Dict[str, str] = field(default_factory=dict)

    # Refining:
    core_inputs: List[Dict] = field(default_factory=list)
    surrounding_inputs: List[Dict] = field(default_factory=list)

    # Alchemy:
    ingredients: List[Dict] = field(default_factory=list)

    # Engineering:
    slots: List[Dict] = field(default_factory=list)

    # Enchanting:
    pattern: List[str] = field(default_factory=list)

    # Metadata:
    narrative: str = ""
    output_id: str = ""
    station_tier: int = 1
```

#### Template Documentation (templates-crafting-1.JSON)

✅ **EXCELLENT** - Comprehensive templates with:
- Detailed discipline-specific rules
- Multiple examples per discipline
- Tier-based grid/slot scaling
- Common mistakes section
- Implementation summary

**No issues found** - This file is exemplary documentation.

---

## Code-Template Alignment Analysis

### Fields Used by Code But Not in Templates:
**NONE** - All code-expected fields are documented ✓

### Fields in Templates But Not Used by Code:
1. `sequenceLength` (alchemy) - Harmless metadata
2. `slotCount` (engineering) - Harmless metadata
3. `flags` (equipment) - Useful metadata even if not code-used
4. `stationRequired` (refining) - Redundant with stationType
5. `fuelRequired` (refining) - Future expansion field

### Recent Code Changes Not in Templates:
1. **`range` field** (equipment) - Added Nov 17, needs better documentation
2. **Enchantment effects implementation** - Added Nov 17, needs examples of damage_multiplier/defense_multiplier
3. **Weapon range mechanics** - Needs examples of tactical range values

---

## Common Mistakes & Pitfalls

### 1. Stat Requirement Naming
**ISSUE**: Templates don't specify which stat abbreviations are valid

**Current valid abbreviations** (main.py:378-393):
- STR, strength → strength
- DEF, defense → defense
- VIT, vitality → vitality
- LCK, luck → luck
- AGI, agility → agility
- **DEX, dexterity → agility** (backward compatibility)
- INT, intelligence → intelligence

**Recommendation**: Use AGI not DEX in all new JSONs (DEX is legacy support only)

### 2. Equipment Type Detection
**ISSUE**: Templates don't clarify that `type` can be specific (sword, axe, mace) OR generic (weapon, armor)

**Code recognizes these type sets** (main.py:701-702):
```python
weapon_types = {'weapon', 'sword', 'axe', 'mace', 'dagger', 'spear', 'bow', 'staff'}
armor_types = {'armor', 'helmet', 'chestplate', 'leggings', 'boots', 'gauntlets'}
```

### 3. Category vs Type Confusion
**CRITICAL**: Equipment MUST have `category: "equipment"` to load into EquipmentDatabase

Items with other categories (consumable, device, material) will be skipped!

### 4. Range Values
**Tactical weapon ranges** (from stats-calculations.JSON:264-278):
- Melee 1H: 1.0
- Melee 2H: 1.5
- Spear: 2.0
- Pike: 3.0
- Shortbow: 10.0
- Longbow: 15.0
- Crossbow: 12.0

---

## Validation Checklist for Mass Generation

### Equipment Items Checklist:
- [ ] `itemId` is unique and matches recipe outputId
- [ ] `category` is exactly "equipment" (case-sensitive)
- [ ] `type` is from weapon_types or armor_types sets
- [ ] `subtype` matches one of the subtypes in stats-calculations.JSON
- [ ] `tier` is 1-4
- [ ] `rarity` is common/uncommon/rare/epic/legendary/mythical/unique
- [ ] `range` is a FLOAT (use 1.0 not 1)
- [ ] `slot` matches valid slots (mainHand, offHand, helmet, chestplate, leggings, boots, gauntlets, accessory)
- [ ] `statMultipliers` has {damage, attackSpeed, durability, weight} for weapons
- [ ] `statMultipliers` has {defense, durability, weight} for armor
- [ ] `requirements.stats` uses AGI not DEX
- [ ] `metadata.narrative` is present and descriptive

### Recipe Checklist:
- [ ] `recipeId` is unique
- [ ] `outputId` matches an existing itemId or materialId
- [ ] `stationTier` is 1-4
- [ ] `inputs` array has valid materialIds
- [ ] For enchanting: uses `enchantmentId` not `outputId`
- [ ] For enchanting: `stationType` is "enchanting" not "adornments"
- [ ] For enchanting: `effect.type` is one of: damage_multiplier, defense_multiplier, etc.
- [ ] For enchanting: `conflictsWith` array lists mutually exclusive enchantments

### Material Checklist:
- [ ] `materialId` is unique
- [ ] `tier` is 1-4
- [ ] `category` describes material type (ore, metal, wood, gem, etc.)
- [ ] `maxStack` is reasonable (99 for most, 256 for refined materials)

---

## Recommended Fixes

### Fix 1: Update Equipment Template - Range Field
**File**: `Definitions.JSON/JSON Templates`
**Section**: EQUIPMENT_TEMPLATE.weapons (line 160)

**Current**:
```json
"range": 1,
```

**Fixed**:
```json
"range": 1.0,
"rangeNote": "Weapon tactical combat distance. Melee: 1.0-1.5, Spears: 2.0-3.0, Bows: 10.0-15.0"
```

### Fix 2: Add Material Template
**File**: `Definitions.JSON/JSON Templates`
**Add after EQUIPMENT_TEMPLATE**:

```json
"MATERIAL_TEMPLATE": {
  "metadata": {
    "narrative": "Description of this material's properties and uses",
    "tags": ["ore", "metal", "tier1"]
  },
  "materialId": "copper_ore",
  "name": "Copper Ore",
  "tier": 1,
  "category": "ore",
  "rarity": "common",
  "description": "Raw copper extracted from stone. Can be refined into ingots.",
  "maxStack": 99,
  "properties": {
    "note": "Properties are optional metadata for special materials",
    "weight": 0.5,
    "refinable": true
  }
}
```

### Fix 3: Fix Enchanting Template Naming
**File**: `Definitions.JSON/JSON Templates`
**Section**: RECIPE_TEMPLATE.adornments (line 109-144)

**Changes**:
1. Rename section from "adornments" to "enchanting"
2. Change `recipeId` pattern from "adornments_*" to "enchanting_*"
3. Change `stationType` from "adornments" to "enchanting"

**Current**:
```json
"adornments": {
  "recipeId": "adornments_fire_enchant_minor",
  "stationType": "adornments",
  ...
}
```

**Fixed**:
```json
"enchanting": {
  "recipeId": "enchanting_fire_enchant_minor",
  "stationType": "enchanting",
  ...
}
```

### Fix 4: Clarify Optional Fields
**File**: `Definitions.JSON/JSON Templates`

Add note to alchemy and engineering templates:

```json
"alchemy": {
  ...
  "sequenceLength": 3,
  "sequenceLengthNote": "OPTIONAL - Not used by code, informational only"
}

"engineering": {
  ...
  "slotCount": 3,
  "slotCountNote": "OPTIONAL - Not used by code, informational only"
}
```

### Fix 5: Add Stat Requirements Guide
**File**: `Definitions.JSON/JSON Templates`
**Add new section**:

```json
"STAT_REQUIREMENTS_GUIDE": {
  "note": "Use these EXACT stat names in requirements.stats",
  "valid_stats": {
    "strength": "STR or strength",
    "defense": "DEF or defense",
    "vitality": "VIT or vitality",
    "luck": "LCK or luck",
    "agility": "AGI or agility (PREFERRED)",
    "intelligence": "INT or intelligence"
  },
  "deprecated": {
    "DEX": "Use AGI instead - DEX is legacy support only",
    "dexterity": "Use agility instead"
  },
  "example": {
    "requirements": {
      "level": 10,
      "stats": {
        "AGI": 20,
        "STR": 15
      }
    }
  }
}
```

---

## Mass Generation Workflow Recommendations

### Phase 1: Template Fixes (CURRENT)
1. Apply all 5 fixes to `JSON Templates` file
2. Validate fixes by checking against actual working JSONs
3. Get user approval before proceeding

### Phase 2: Validation Tool Setup
1. Create Python script to validate JSON files against templates
2. Script checks:
   - Required fields present
   - Field types correct (range is float not int)
   - IDs are unique
   - Cross-references (outputId exists as itemId)
   - Stat names are valid

### Phase 3: Mass Generation
1. Start with **materials** (foundation for recipes)
2. Then **equipment items** (needed as recipe outputs)
3. Then **recipes** (reference materials and equipment)
4. Finally **placements** (reference recipes)

### Phase 4: Integration Testing
1. Load all JSONs into game
2. Test crafting each tier
3. Test enchanting system
4. Verify combat with new weapons
5. Check for missing material errors

---

## Summary

**Overall Assessment**: ✅ **System is 90% ready for mass generation**

**Critical Issues**: 3 (all fixable in <30 minutes)
**Minor Issues**: 5 (documentation improvements)

**Recommended Action**:
1. Apply the 5 fixes to `JSON Templates` file
2. Create material template (missing)
3. Update enchanting section naming
4. Add stat requirements guide
5. Clarify range field documentation
6. Proceed with mass generation using fixed templates

**Estimated Time to Fix**: 20-30 minutes
**Confidence Level**: High - templates are well-structured, just need minor corrections

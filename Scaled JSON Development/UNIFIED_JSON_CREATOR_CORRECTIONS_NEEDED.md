# Unified JSON Creator - Required Corrections

**Status**: Initial version created but needs corrections based on game code analysis
**Date**: 2025-11-21

---

## Issues Found

### 1. **File Loading** ❌
- **Problem**: Loading ALL versions of files (items-smithing-1, -2, -3)
- **Actual**: Game only loads specific versions
  - Smithing: Uses version 2 for equipment, NOT version 3
  - Recipes: Uses smithing version 3 for recipes
- **Impact**: Counting 900+ items instead of ~500

### 2. **Station Type** ❌
- **Problem**: Using "enchanting" as station type
- **Actual**: Game uses "adornments"
- **Impact**: Validation will fail, recipes won't load

### 3. **Missing File Source Metadata** ❌
- **Problem**: No indication of which file each JSON came from
- **Needed**: Display source file for debugging

### 4. **Schema Inaccuracies** ⚠️
- Refining recipes use `outputs` array, not `outputId`
- Refining uses `stationTierRequired` not `stationTier`
- items-refining uses `itemId` not `materialId`
- Mixed field names not fully supported

### 5. **Location** ❌
- **Problem**: Tool in `Game-1-modular/tools/json_generators/`
- **Needed**: Should be in `Scaled JSON Development/`

---

## Correction Plan

### Phase 1: File Analysis (COMPLETE ✓)
- [x] Analyzed all database loaders
- [x] Documented exact files loaded
- [x] Identified schema discrepancies
- [x] Created GAME_JSON_LOADING_ANALYSIS.md

### Phase 2: Tool Corrections (TODO)
- [ ] Move tool to `Scaled JSON Development/`
- [ ] Update file loading to match game exactly
- [ ] Fix station type enum (s/enchanting/adornments/)
- [ ] Add file source metadata to loaded items
- [ ] Update refining recipe schema
- [ ] Add validation for common mistakes
- [ ] Test with actual game files

### Phase 3: Documentation (TODO)
- [ ] Update README with corrections
- [ ] Add troubleshooting section
- [ ] Document known limitations
- [ ] Create migration guide from old tool

---

## Exact Files to Load

Based on `core/game_engine.py`:

```python
GAME_LOADED_FILES = {
    # Equipment (loaded with category=='equipment' filter)
    "equipment": [
        "items.JSON/items-smithing-1.JSON",
        "items.JSON/items-smithing-2.JSON",  # Version 2, NOT 3!
        "items.JSON/items-tools-1.JSON",
        "items.JSON/items-alchemy-1.JSON",
    ],

    # Materials
    "materials": [
        "items.JSON/items-materials-1.JSON",
        "items.JSON/items-refining-1.JSON",  # Uses itemId!
    ],

    # Stackable consumables (from alchemy file, category=='consumable')
    "stackable_consumables": [
        "items.JSON/items-alchemy-1.JSON",
    ],

    # Stackable devices (from smithing file, category=='device')
    "stackable_devices": [
        "items.JSON/items-smithing-1.JSON",
    ],

    # Recipes (discipline-specific versions)
    "recipes": [
        "recipes.JSON/recipes-smithing-3.json",      # Version 3!
        "recipes.JSON/recipes-alchemy-1.JSON",
        "recipes.JSON/recipes-refining-1.JSON",
        "recipes.JSON/recipes-engineering-1.JSON",
        "recipes.JSON/recipes-adornments-1.json",    # adornments not enchanting!
    ],

    # Placements (all version 1)
    "placements": [
        "placements.JSON/placements-smithing-1.JSON",
        "placements.JSON/placements-refining-1.JSON",
        "placements.JSON/placements-alchemy-1.JSON",
        "placements.JSON/placements-engineering-1.JSON",
        "placements.JSON/placements-adornments-1.JSON",
    ],

    # Progression
    "skills": ["Skills/skills-skills-1.JSON"],
    "titles": ["progression/titles-1.JSON"],
    "classes": ["progression/classes-1.JSON"],
    "npcs": ["progression/npcs-enhanced.JSON", "progression/npcs-1.JSON"],  # Try enhanced first
    "quests": ["progression/quests-1.JSON"],
}
```

---

## Critical Schema Fixes

### 1. Station Types
```python
# WRONG
enum_values=["smithing", "alchemy", "refining", "engineering", "enchanting"]

# CORRECT
enum_values=["smithing", "alchemy", "refining", "engineering", "adornments"]
```

### 2. Refining Recipe Format
```python
# Standard recipes (smithing/alchemy/engineering)
{
    "outputId": "iron_sword",
    "outputQty": 1,
    "stationTier": 2
}

# Refining recipes (DIFFERENT format!)
{
    "outputs": [  # Note: array!
        {
            "materialId": "iron_ingot",
            "quantity": 1,
            "rarity": "common"
        }
    ],
    "stationTierRequired": 1  # Note: different field name!
}
```

### 3. Items-Refining Field Names
```python
# In items-refining-1.JSON, use itemId not materialId!
{
    "itemId": "iron_ingot",  # Correct
    # NOT "materialId"
}
```

---

## Recommended Implementation Changes

### DataLoader Class

```python
class DataLoader:
    # Hardcode exact files the game loads
    EXACT_FILES = {
        "items_equipment": [
            "items.JSON/items-smithing-1.JSON",
            "items.JSON/items-smithing-2.JSON",
            "items.JSON/items-tools-1.JSON",
            "items.JSON/items-alchemy-1.JSON",
        ],
        # ... etc
    }

    def _load_json_file(self, file_path: Path) -> List[Dict]:
        """Load and add source metadata"""
        items = # ... load as before

        # ADD SOURCE METADATA
        for item in items:
            item['_source_file'] = str(file_path)
            item['_loaded_as'] = self._determine_load_category(item)

        return items
```

### ValidationEngine Updates

```python
def _validate_specific(self, json_type: str, data: Dict) -> List[ValidationIssue]:
    issues = []

    # Check for enchanting/adornments confusion
    if json_type == "recipes":
        if data.get("stationType") == "enchanting":
            issues.append(ValidationIssue(
                "error", "stationType",
                "Invalid station type 'enchanting'. Use 'adornments' instead.",
                "Change stationType to 'adornments'"
            ))

    # Check refining format
    if json_type == "recipes" and data.get("stationType") == "refining":
        if "outputId" in data:
            issues.append(ValidationIssue(
                "warning", "outputId",
                "Refining recipes should use 'outputs' array, not 'outputId'",
                "Use outputs: [{materialId, quantity, rarity}]"
            ))

    return issues
```

---

## Testing Checklist

After corrections:

- [ ] Total items loaded: 400-600 (not 900+)
- [ ] Each item shows source file
- [ ] "adornments" recognized as valid station type
- [ ] "enchanting" shows error
- [ ] Refining recipes validated correctly
- [ ] items-refining items use itemId
- [ ] Only game-loaded file versions shown
- [ ] Duplicate detection works across files
- [ ] Cross-references validate correctly

---

## Next Steps

1. **Move and Rename**
   ```bash
   # Move to correct location
   mv Game-1-modular/tools/json_generators/unified_json_creator.py \
      "Scaled JSON Development/unified_json_creator.py"
   ```

2. **Apply Corrections**
   - Update EXACT_FILES dictionary
   - Fix station type enums
   - Add source file metadata
   - Update refining schema
   - Add enhanced validation

3. **Test Thoroughly**
   - Verify item counts
   - Check all file sources
   - Validate cross-references
   - Test duplicate detection

4. **Document**
   - Update README with corrections
   - Add known limitations
   - Document file version strategy

---

## Known Limitations

**Will NOT be supported** (at least initially):
- Enemies/Hostile entities (no game loader)
- Resource nodes (no game loader)
- Multiple file versions (game uses specific versions only)

**Partial Support**:
- Quest loading (complex relationship with NPCs)
- Enhanced NPC format (v2.0 vs v1.0 fallback)

---

## Estimated Effort

- File loading corrections: 2 hours
- Schema updates: 2 hours
- Testing: 2 hours
- Documentation: 1 hour
- **Total: ~7 hours**

---

## Priority

**HIGH**: Critical for tool accuracy and preventing bad JSON creation

Without these corrections:
- Tool will show ~900 items (incorrect)
- Validation will fail for "adornments" recipes
- Users will create "enchanting" recipes that won't load
- Refining recipes will be malformed
- No way to debug which file items came from

**Recommendation**: Apply all corrections before promoting tool for use.

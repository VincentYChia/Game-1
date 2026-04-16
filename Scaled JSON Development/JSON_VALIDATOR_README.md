# Game-1 JSON Validator

Production-quality JSON validator for Game-1 game files.

## Overview

Comprehensive validation tool for all Game-1 JSON files covering:
- **13+ file types**: Items, recipes, placements, skills, NPCs, quests, titles, classes, enemies, tags, world configs, update files, and chunk saves
- **Smart auto-detection**: Automatically identifies file type from path
- **Pragmatic validation**: Detects real issues, not schema pedantry
- **Cross-file validation**: Verifies references across different JSON files (recipes → items, placements → recipes, etc.)
- **Comprehensive reporting**: Detailed error messages with file paths and context

## Usage

### Full Repository Scan
```bash
python json_validator.py
```

Scans all JSON files in Game-1-modular directory including Update-1 and Update-2 directories.

### Validate Single File
```bash
python json_validator.py --file items.JSON/items-materials-1.JSON
```

### Verbose Output (Show Warnings)
```bash
python json_validator.py --verbose
```

### Skip Update Directories
```bash
python json_validator.py --no-updates
```

### Help
```bash
python json_validator.py --help
```

## Supported File Types

### Content Files
| Type | Validation | Examples |
|------|------------|----------|
| **Items** | Required fields (name, category, tier, rarity), no duplicate IDs | items-materials-1.JSON, items-smithing-2.JSON |
| **Recipes** | Output spec (outputId/enchantmentId/outputs), valid inputs | recipes-smithing-3.json, recipes-alchemy-1.JSON |
| **Placements** | Valid recipe references, layout data | placements-smithing-1.json, placements-alchemy-1.JSON |
| **Skills** | Valid skill IDs and names | skills-skills-1.JSON |
| **NPCs** | Valid NPC IDs and names | npcs-1.JSON, npcs-enhanced.JSON |
| **Quests** | Valid quest IDs and names | quests-1.JSON, quests-enhanced.JSON |
| **Titles** | Valid title IDs and names | titles-1.JSON |
| **Classes** | Valid class IDs and names | classes-1.JSON |
| **Enemies** | Required fields (name, tier, behavior, stats, drops), no duplicates | hostiles-1.JSON |

### Config Files
- **Tag Definitions**: Validates category structure (tag-definitions.JSON)
- **World Configs**: Validates backend configuration, world generation parameters
- **Update Files**: Validates update files in Update-1/ and Update-2/
- **Chunk Saves**: Validates world save chunk files

## What Gets Checked

### Per-File Validation
✓ Valid JSON syntax  
✓ Correct file structure (arrays, objects, required sections)  
✓ Required fields present  
✓ Data type correctness  
✓ No duplicate IDs within file  
✓ Tier/rarity enum values  
✓ Quantity > 0  

### Cross-File Validation
✓ Recipes reference valid items  
✓ Recipe inputs reference valid items  
✓ Placements reference valid recipes  
✓ Quests reference valid NPCs  

## Output Format

```
================================================================================
GAME-1 JSON VALIDATION REPORT
================================================================================

Files Scanned:  89
Valid Files:    55
Files with Errors: 34

Total Errors:   34
Total Warnings: 1

✓ ALL FILES VALID
  or
✗ VALIDATION FAILED - 34 errors found

────────────────────────────────────────────────────────────────────────────────
ERRORS:
────────────────────────────────────────────────────────────────────────────────
  [ERROR] items.JSON/items-materials-1.JSON: Missing metadata section
  [ERROR] recipes.JSON/recipes-smithing-3.json: Recipe 'weapon_x' references non-existent item 'sword_y'
  ... (showing first 30)

================================================================================
```

## Exit Codes

- `0` - All files valid
- `1` - One or more files have errors

## Integration

### CI/CD Pipeline
```bash
#!/bin/bash
python json_validator.py
if [ $? -ne 0 ]; then
  echo "JSON validation failed!"
  exit 1
fi
```

### Pre-Commit Hook
```bash
#!/bin/bash
python json_validator.py --no-updates
exit $?
```

### Development Workflow
Run after editing JSON files:
```bash
python json_validator.py --file path/to/edited/file.JSON
```

## Design Philosophy

The validator uses a **pragmatic approach**:

1. **Real issues, not pedantry**: Focuses on errors that will actually break the game (missing IDs, duplicates, cross-file refs) rather than enforcing strict schemas on optional fields

2. **Multiple data formats**: Game has evolved to use different schemas for different file types:
   - Smithing recipes: `outputId`, `outputQty`
   - Refining recipes: `outputs` array
   - Enchanting recipes: `enchantmentId`
   - Alchemy placements: `ingredients` array
   - Smithing placements: `placementMap` dict

   The validator understands and validates all of these.

3. **Automatic detection**: No need to specify file types - validator detects from path patterns

4. **Suitable for automation**: Clean exit codes, structured output, no external dependencies

## Limitations

### What It Does NOT Check

- ✗ Item descriptions/narratives (free text)
- ✗ stat/requirement/effect parameter value ranges
- ✗ Icon asset existence
- ✗ Crafting minigame difficulty calculations
- ✗ Experience/reward balance
- ✗ World seed parameters

These would require game-logic knowledge and aren't critical for data integrity.

## Adding New File Types

To add validation for a new file type:

1. Add pattern to `FILE_PATTERNS` dict:
   ```python
   'new_type': ['path/pattern/*.JSON'],
   ```

2. Add detector in `_detect_file_type()`:
   ```python
   if 'path/pattern' in filepath_lower:
       return 'new_type'
   ```

3. Create `_validate_new_type()` method

4. Add to main validation dispatch in `validate_file()`

## Performance

On current repo (89 files):
- Full scan: < 100ms
- Single file: < 10ms
- Memory: < 5MB

Suitable for real-time feedback during development.

## Future Enhancements

Possible additions if needed:
- JSON schema export to JSON Schema format
- Auto-fix for common issues (duplicate cleanup, missing fields)
- Diff validation (compare two versions)
- HTML report generation
- Integration with GitHub Actions

## Questions?

Refer to `docs/GAME_MECHANICS_V6.md` for game content definitions.
Refer to `CLAUDE.md` for project architecture and file organization.

# Unified JSON Creator

**A comprehensive, intelligent tool for creating and validating all JSON types in the game.**

## Overview

The Unified JSON Creator is a powerful GUI application that streamlines the process of creating, editing, and validating JSON data for all 13 JSON types in the game. It features smart validation, cross-reference checking, duplicate ID detection, and a split-screen interface for viewing existing JSONs while creating new ones.

## Key Features

### 1. **Handles All JSON Types**
Supports all 13 JSON types:
- Items (equipment, weapons, armor, tools, devices)
- Materials (ores, metals, gems, herbs, etc.)
- Recipes (smithing, alchemy, refining, engineering, enchanting)
- Placements (4 different formats: grid, hub-spoke, sequential, slot-based)
- Skills (abilities and effects)
- Quests (objectives and rewards)
- NPCs (characters and dialogue)
- Titles (achievements and bonuses)
- Classes (character archetypes)
- Enemies (hostile entities)
- Resource Nodes (gatherable objects)

### 2. **Preloaded Field Types**
- Dynamic form generation based on JSON type
- All fields are pre-defined with:
  - Data types (string, integer, float, boolean, object, array, enum, reference)
  - Required/optional status
  - Default values
  - Descriptions and tooltips
  - Enum options where applicable

### 3. **Library View with Split Screen**
- **Left Panel**: Form for creating/editing JSON
- **Middle Panel**: List of existing JSONs of the selected type
- **Right Panel**: Validation results and JSON preview
- **Search functionality**: Quickly filter existing JSONs
- **Click to load**: Click any existing JSON to load it as a template

### 4. **Single File Save**
- Saves all new JSONs to unified files (e.g., `items-unified.JSON`, `recipes-unified.JSON`)
- Maintains proper JSON structure with metadata
- Automatically handles discipline-specific files for recipes and items
- Preserves existing file structure when appending

### 5. **Smart Cross-Reference Validation** ⭐

The tool validates all linked JSONs and highlights missing references:

#### Validation Checks:
- **Recipes → Items**: `outputId` must exist in items
- **Recipes → Materials**: All `inputs[].materialId` must exist
- **Placements → Recipes**: `recipeId` must exist
- **Placements → Materials**: Materials in placement must match recipe inputs
- **Quests → NPCs**: `npc_id` must exist
- **Quests → Items**: All reward items must exist
- **Quests → Skills**: All reward skills must exist
- **Quests → Titles**: Reward title must exist
- **Classes → Skills**: Starting skill must exist
- **Skills → Skills**: Evolution chain references must exist
- **Enemies → Materials**: Drop table materials must exist
- **Resource Nodes → Materials**: Drop table materials must exist

#### Validation Display:
- ❌ **Red Errors**: Critical issues (missing references, duplicate IDs, invalid values)
- ⚠️ **Orange Warnings**: Non-critical issues (unknown fields, best practice violations)
- ✓ **Green Success**: No issues found
- 💡 **Blue Suggestions**: Helpful hints for fixing issues

### 6. **ID Duplication Checker**

Automatically checks for duplicate IDs within each JSON type:
- Compares against all existing JSONs of that type
- Shows clear error message with the duplicate ID
- Suggests choosing a unique ID or loading the existing item to edit

### 7. **Additional Smart Features**

- **Auto-complete dropdowns**: Reference fields show existing IDs from linked JSON types
- **Type-specific validation**:
  - Items: Warns if `category != "equipment"` (won't load in game)
  - Items: Ensures `range` is float (1.0 not 1)
  - Recipes: Validates discipline-specific formats
  - Recipes: Checks enchanting uses `enchantmentId` not `outputId`
  - Placements: Ensures materials match recipe inputs
- **Real-time preview**: JSON preview updates as you type
- **Nested object support**: Complex objects and arrays use scrollable text editors
- **Error recovery**: Option to save despite validation errors

## Usage

### Running the Tool

```bash
cd /path/to/Game-1/Game-1-modular/tools/json_generators
python3 unified_json_creator.py
```

Or make it executable and run directly:
```bash
chmod +x unified_json_creator.py
./unified_json_creator.py
```

### Workflow

1. **Select JSON Type**: Choose from the dropdown (e.g., "items", "recipes", "quests")

2. **Browse Existing JSONs** (Optional):
   - View existing JSONs in the middle panel
   - Search/filter using the search box
   - Click to load as a template

3. **Fill in Fields**:
   - Required fields are marked with `*`
   - Field descriptions appear below each field
   - Reference fields show dropdowns with valid options
   - Complex objects/arrays use text editors with JSON syntax

4. **Validate**:
   - Click "Validate" button (or it auto-validates)
   - Review issues in the right panel
   - Fix errors (red) before saving
   - Warnings (orange) are informational

5. **Preview**:
   - View formatted JSON in the preview panel
   - Verify structure before saving

6. **Save**:
   - Click "Save" button
   - Tool saves to appropriate file (discipline-specific or unified)
   - Data is automatically reloaded
   - Library updates to show new item

7. **Create Next**:
   - Click "New" to clear form
   - Repeat process

## File Locations

### Saved JSONs

All new JSONs are saved to unified files:

- **Items**: `items.JSON/items-unified.JSON`
- **Recipes**: `recipes.JSON/recipes-<discipline>-unified.JSON`
  - Discipline-specific (smithing, alchemy, refining, engineering, enchanting)
- **Placements**: `placements.JSON/placements-<discipline>-unified.JSON`
- **Skills**: `Skills/skills-unified.JSON`
- **Quests**: `progression/quests-1.JSON`
- **NPCs**: `progression/npcs-1.JSON`
- **Titles**: `progression/titles-1.JSON`
- **Classes**: `progression/classes-1.JSON`
- **Enemies**: `Definitions.JSON/hostile-entities-1.JSON`
- **Resource Nodes**: `Definitions.JSON/resource-nodes-1.JSON`

### Loaded JSONs

The tool automatically loads and validates against ALL existing JSON files in the codebase.

## Schema Highlights

### Items Schema

```json
{
  "itemId": "iron_sword",              // REQUIRED, unique, snake_case
  "name": "Iron Sword",                 // REQUIRED
  "category": "equipment",              // REQUIRED (must be "equipment" to load!)
  "type": "weapon",                     // weapon|armor|tool|consumable|device|station
  "subtype": "sword",                   // Specific subtype
  "tier": 2,                            // 1-4
  "rarity": "common",                   // common|uncommon|rare|epic|legendary|artifact
  "slot": "mainHand",                   // For equipment
  "range": 1.0,                         // FLOAT (must be 1.0 not 1)
  "statMultipliers": {...},
  "requirements": {...},
  "flags": {...},
  "metadata": {...}
}
```

### Recipes Schema

Varies by discipline:

**Smithing/Alchemy/Engineering:**
```json
{
  "recipeId": "smithing_iron_sword",
  "outputId": "iron_sword",             // Must exist in Items!
  "stationType": "smithing",
  "stationTier": 2,
  "inputs": [
    {"materialId": "iron_ingot", "quantity": 3}  // Must exist in Materials!
  ]
}
```

**Enchanting** (special format):
```json
{
  "recipeId": "enchanting_sharpness",
  "enchantmentId": "sharpness_1",       // NOT outputId!
  "stationType": "enchanting",          // NOT "adornments"!
  "applicableTo": ["weapon"],
  "effect": {...}
}
```

### Quests Schema

```json
{
  "quest_id": "tutorial_quest",
  "npc_id": "tutorial_guide",           // Must exist in NPCs!
  "rewards": {
    "items": [
      {"item_id": "health_potion", "quantity": 2}  // Must exist in Items!
    ],
    "skills": ["sprint"],               // Must exist in Skills!
    "title": "novice_forester"          // Must exist in Titles!
  }
}
```

## Common Validation Issues

### ❌ Errors (Must Fix)

1. **Duplicate ID**: `"Duplicate ID 'iron_sword' already exists in items"`
   - Solution: Choose a unique ID or load existing item to edit

2. **Missing Reference**: `"Reference 'iron_ingot' not found in materials"`
   - Solution: Create the referenced item first, or choose from existing

3. **Required Field**: `"Required field 'itemId' is missing"`
   - Solution: Fill in all required fields (marked with `*`)

4. **Invalid Enum**: `"Invalid value 'super-rare'. Must be one of: common, uncommon, rare, epic, legendary"`
   - Solution: Choose from the dropdown options

5. **Wrong Data Type**: `"Range must be a float (e.g., 1.0 not 1)"`
   - Solution: Use correct data type (1.0 instead of 1)

### ⚠️ Warnings (Best Practices)

1. **Category Warning**: `"Items with category != 'equipment' may not load in game"`
   - Info: Equipment items need `category: "equipment"`

2. **Unknown Field**: `"Unknown field 'customField' (not in schema)"`
   - Info: Field might be ignored or cause issues

3. **Placement Mismatch**: `"Material 'steel_ingot' not in recipe inputs"`
   - Info: Placement materials should match recipe inputs

## Tips for Efficient JSON Creation

1. **Use Existing JSONs as Templates**:
   - Load similar items from the library
   - Modify fields as needed
   - Save with new ID

2. **Create Dependencies First**:
   - Create materials before recipes that use them
   - Create items before recipes that produce them
   - Create NPCs before quests that reference them
   - Create skills before classes that start with them

3. **Validate Early and Often**:
   - Click "Validate" frequently
   - Fix errors as you go
   - Don't wait until the end

4. **Use Search to Verify**:
   - Before creating, search to see if it exists
   - Avoid duplicate efforts
   - Find examples of similar items

5. **Follow Naming Conventions**:
   - IDs: `snake_case` (e.g., `iron_sword`, `health_potion`)
   - Names: `Title Case` (e.g., "Iron Sword", "Health Potion")
   - Discipline prefixes: `smithing_`, `alchemy_`, `refining_`, etc.

## Architecture

### Component Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    Unified JSON Creator                      │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │   Schema     │  │  Validation  │  │  Data Loader │     │
│  │  Registry    │  │   Engine     │  │              │     │
│  │              │  │              │  │              │     │
│  │ • 13 Types   │  │ • Duplicate  │  │ • Load All   │     │
│  │ • Field Defs │  │   ID Check   │  │   JSONs      │     │
│  │ • Validation │  │ • Reference  │  │ • Cache Data │     │
│  │   Rules      │  │   Validator  │  │ • Extract    │     │
│  │              │  │ • Type-      │  │   References │     │
│  │              │  │   Specific   │  │              │     │
│  └──────────────┘  └──────────────┘  └──────────────┘     │
│         ▲                  ▲                  ▲             │
│         │                  │                  │             │
│         └──────────────────┼──────────────────┘             │
│                            │                                │
│                    ┌───────▼────────┐                       │
│                    │   GUI Layer    │                       │
│                    │                │                       │
│                    │  • Form Builder│                       │
│                    │  • Library View│                       │
│                    │  • Validation  │                       │
│                    │  • Preview     │                       │
│                    └────────────────┘                       │
└─────────────────────────────────────────────────────────────┘
```

### Key Classes

- **`JSONSchemas`**: Defines schemas for all 13 JSON types
- **`FieldDefinition`**: Defines individual field properties
- **`DataLoader`**: Loads and caches all existing JSONs
- **`ValidationEngine`**: Validates data with cross-reference checking
- **`UnifiedJSONCreatorGUI`**: Main GUI application

## Troubleshooting

### "No JSONs appearing in library"
- Check that JSON files exist in the expected directories
- Verify file permissions
- Check console for loading errors

### "Validation not working"
- Ensure all JSON files loaded successfully (check console)
- Reload data by switching JSON types
- Restart the application

### "Save failed"
- Check file permissions on target directory
- Verify directory exists
- Check disk space

### "Can't see all fields in form"
- Scroll down in the left panel
- Form is scrollable for long schemas

## Future Enhancements

Potential improvements for future versions:

- [ ] Undo/Redo functionality
- [ ] Bulk import from CSV
- [ ] JSON comparison/diff tool
- [ ] Template presets for common items
- [ ] Export validation report
- [ ] Dark mode
- [ ] Keyboard shortcuts
- [ ] Auto-save drafts
- [ ] Multi-item batch creation

## Support

For issues, bugs, or feature requests:
1. Check existing documentation in `Scaled JSON Development/General JSON Information/`
2. Review validation reports in `claude-context/`
3. Consult the comprehensive specs in `UNIFIED_JSON_CREATOR_SPECIFICATION.md`

## License

Part of Game-1 project. See main project documentation for licensing.

---

**Version**: 1.0
**Last Updated**: 2025-11-21
**Author**: Created via Claude Code
**Compatibility**: Python 3.7+, Tkinter

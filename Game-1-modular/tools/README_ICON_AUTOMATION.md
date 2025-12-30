# Icon Automation Workflow

## Overview

This directory contains tools for managing game icons, from placeholder generation to AI-powered icon creation.

## The Problem We Solved

Previously, there were discrepancies between:
- **Placeholder icons** (generated from JSON files): 210+ files
- **Icon catalog** (manually maintained): 169 entries

This meant:
1. Some entities had placeholders but no catalog entry (enemies, resources, titles)
2. Vheer-automation couldn't generate AI icons for missing catalog entries
3. Manual maintenance led to drift between systems

## The Solution: Unified Generation

We now have a **single source of truth**: the JSON definition files.

All icons and catalog entries are generated from the same data, guaranteeing they match perfectly.

---

## File Descriptions

### 1. `assets/icons/unified_icon_generator.py` ⭐ PRIMARY TOOL

**Purpose**: Generate BOTH placeholder icons AND the catalog markdown from JSON files.

**Location**: Moved to `assets/icons/` to keep icon generation tools co-located with icon assets.

**Usage**:
```bash
cd Game-1-modular
python assets/icons/unified_icon_generator.py
```

**What it does**:
1. Reads from all JSON definition files:
   - **Core content**: `items.JSON/*.JSON`, `Definitions.JSON/hostiles-1.JSON`, `progression/*.JSON`, `Skills/*.JSON`
   - **Update-N packages**: Scans `updates_manifest.json` to discover and extract all Update-N content
   - Hardcoded resources (from ResourceType enum)

2. Generates placeholder PNG images:
   - `assets/items/{materials,weapons,armor,tools,accessories,stations,devices,consumables}/*.png`
   - `assets/{enemies,resources,titles,skills}/*.png`
   - Colored rectangles with item IDs and tier indicators
   - Only creates missing files (won't overwrite existing)

3. Generates catalog markdown:
   - `assets/icons/ITEM_CATALOG_FOR_ICONS.md`
   - Contains: ITEM_ID, Category, Type, Subtype, Narrative
   - Used by Vheer-automation for AI icon generation
   - **Includes Update-N content** automatically

**When to run**:
- After adding new items to core JSON files
- After adding/updating Update-N packages
- After modifying item narratives
- When placeholders and catalog get out of sync

**Update-N Integration** 🆕:
- Automatically scans `updates_manifest.json` for installed updates
- Extracts items, skills, and enemies from all Update-N directories
- Deduplicates entries (Update-N overrides core items with same ID)
- Generates placeholders and catalog entries for Update-N content
- No manual intervention needed - just run the script!

---

### 2. `generate_placeholder_icons.py` (DEPRECATED)

**Status**: Superseded by `unified_icon_generator.py`

**Keep for**: Reference only. The new unified generator does everything this did, plus catalog generation.

---

### 3. `../assets/Vheer-automation.py`

**Purpose**: Generate AI-powered icons using Vheer.com

**Usage**:
```bash
cd Game-1-modular/assets
python Vheer-automation.py
```

**What it does**:
1. Reads the catalog markdown (`ITEM_CATALOG_FOR_ICONS.md`)
2. For each item, fills Vheer's AI generator with:
   - Persistent prompt: "Simple cel-shaded 3d stylized fantasy exploration item icons..."
   - Detail prompt: Category, Type, Subtype, Narrative
3. Waits for generation (up to 180s)
4. Downloads the generated icon
5. Saves to `generated_icons/{subfolder}/{item_name}.png`

**Modes**:
- Test mode (2 test items)
- Full catalog mode (all 219 items)

**Dependencies**:
- selenium
- webdriver-manager
- pillow
- Chrome browser

**When to run**:
- After running `unified_icon_generator.py`
- When you want to generate actual artwork to replace placeholders
- After adding new items and want AI-generated icons

---

## Complete Workflow

### Adding New Items

1. **Add item to JSON files** (e.g., `items.JSON/items-smithing-2.JSON`)
   - Include all required fields: itemId, name, category, type, subtype, tier
   - Add narrative in metadata: `"metadata": {"narrative": "..."}`

2. **Run unified generator**:
   ```bash
   cd Game-1-modular
   python assets/icons/unified_icon_generator.py
   ```

   This creates:
   - New placeholder PNG
   - Updates catalog with new entry

3. **(Optional) Generate AI icons**:
   ```bash
   cd Game-1-modular/assets
   python Vheer-automation.py
   ```

   Choose mode 2 (full catalog) to generate icons for all items, including new ones.

4. **(Optional) Replace placeholders**:
   - AI-generated icons are in `assets/generated_icons/`
   - Move them to `assets/items/{subfolder}/` or `assets/{category}/`
   - Overwrite the placeholder PNGs

---

## Current Statistics

**Total Entities**: 233 (includes Update-N content)
- **Items**: 147
  - Materials: 70
  - Weapons: 16 (includes 5 Update-1 weapons)
  - Armor: 6
  - Tools: 10
  - Accessories: 3
  - Stations: 11
  - Devices: 16
  - Consumables: 16
- **Enemies**: 16 (includes Update-1 enemies)
- **Resources**: 12
- **Titles**: 10
- **Skills**: 36 (includes Update-1 skills)
- **NPCs**: 3
- **Quests**: 3
- **Classes**: 6

**Placeholders**: 233 PNG files (all categories)
**Catalog Entries**: 233 (matches all loaded game content + Update-N)

---

## Troubleshooting

### "Numbers don't match!"

Run the unified generator. It reads the authoritative JSON files and regenerates everything.

### "Vheer-automation can't find an item"

Check if the item is in the catalog:
```bash
grep "### item_name" "assets/icons/ITEM_CATALOG_FOR_ICONS.md"
```

If missing, run `unified_icon_generator.py` again.

### "Placeholder exists but not in JSON"

This is normal for orphaned test files. The unified generator won't delete existing files.

To clean up:
1. Run `unified_icon_generator.py` to see what SHOULD exist
2. Manually delete orphaned placeholders if desired

### "New items not showing in catalog"

Ensure the JSON file:
1. Has proper structure (itemId or materialId or enemyId, etc.)
2. Has narrative in metadata: `"metadata": {"narrative": "..."}`
3. Is in the correct directory and named correctly

Then re-run `unified_icon_generator.py`.

---

## Architecture Notes

### Why Unified Generation?

**Before**: Two separate systems
- `generate_placeholder_icons.py` → read JSON → create PNGs
- Manual editing → create catalog markdown
- Result: Drift, missing entries, confusion

**After**: Single source of truth
- `unified_icon_generator.py` → read JSON → create PNGs AND catalog
- Result: Always synchronized, no manual maintenance

### Data Flow

```
JSON Definition Files
        ↓
unified_icon_generator.py
        ↓
   ┌────────────────────┐
   ↓                    ↓
Placeholder PNGs    Catalog MD
        ↓                ↓
   (manual)      Vheer-automation.py
        ↓                ↓
   AI Icons      AI Icons
```

### Future Improvements

- Add validation to ensure all items have narratives
- Auto-detect and warn about orphaned placeholders
- Generate different placeholder styles per category
- Support batch AI generation with rate limiting
- Add icon quality checks (size, format, transparency)

---

## Related Files

- `../assets/ICON_REQUIREMENTS.md` - Original requirements document
- `../assets/icons/ITEM_CATALOG_FOR_ICONS.md` - Generated catalog (AUTO-GENERATED, do not edit)
- `../assets/generated_icons/` - AI-generated icons from Vheer
- `../assets/items/` - Item icon directory structure
- `../assets/{enemies,resources,titles,skills}/` - Other icon directories

# Icon Management Tools - User Guide

## Investigation Summary

### Original Issue
When creating icons, not everything was included in the icon catalog (`ITEM_CATALOG_FOR_ICONS.md`). Specifically missing:
- NPCs
- Quests
- Classes
- Some resources

### What Was Found

**Original Icon Catalog (ITEM_CATALOG_FOR_ICONS.md):**
- Items: 154
- Enemies: 13
- Resources: 12
- Titles: 10
- Skills: 30
- **TOTAL: 219 entities**

**Complete Entity Scan (All JSON files):**
- CLASSES: 6 ❌ *Missing from icon catalog*
- ENEMIES: 13 ✓
- EQUIPMENT: 30
- MATERIALS: 65
- NPCS: 6 ❌ *Missing from icon catalog*
- PLACEMENTS: 171 *(minigame patterns, don't need icons)*
- QUESTS: 6 ❌ *Missing from icon catalog*
- RECIPES: 164 *(crafting recipes, don't need icons)*
- RESOURCES: 28 (16 more than catalog)
- SKILLS: 30 ✓
- STATIONS: 23
- TITLES: 10 ✓
- **TOTAL: 552 entities**

### Entities Missing From Icon Catalog
- **CLASSES**: 6 entities
  - warrior, ranger, scholar, artisan, scavenger, adventurer
- **NPCS**: 6 entities
  - tutorial_guide, mysterious_trader, combat_trainer (and duplicates)
- **QUESTS**: 6 entities
  - tutorial_quest, gathering_quest, combat_quest (and duplicates)
- **Additional RESOURCES**: ~16 entities

---

## New Tools Created

### 1. Complete Entity Catalog Generator

**File:** `/home/user/Game-1/Game-1-modular/tools/complete_entity_catalog.py`

**Purpose:** Scans ALL JSON files in the game and extracts every unique entity ID with metadata.

**Usage:**
```bash
cd /home/user/Game-1/Game-1-modular
python3 tools/complete_entity_catalog.py
```

**Outputs:**
1. **Console Report** - Full listing of all entities by category
2. **Text File** - `../Scaled JSON Development/COMPLETE_ENTITY_CATALOG.txt`
3. **JSON Export** - `../Scaled JSON Development/complete_entity_catalog.json`

**Features:**
- Automatically detects all entity types (items, NPCs, quests, classes, enemies, etc.)
- Handles JSON files with multiple entity types in one file
- Shows which entities are missing icon paths
- Provides complete metadata for each entity

**Example Output:**
```
SUMMARY
--------------------------------------------------------------------------------
  CLASSES: 6
  ENEMIES: 13
  EQUIPMENT: 30
  MATERIALS: 65
  NPCS: 6
  QUESTS: 6
  RESOURCES: 28
  SKILLS: 30
  STATIONS: 23
  TITLES: 10

  TOTAL: 552 entities
```

---

### 2. Enhanced Icon Selector

**File:** `/home/user/Game-1/Game-1-modular/assets/icon-selector-enhanced.py`

**Purpose:** Advanced icon selection tool with search and PNG remapping capabilities.

**New Features:**

#### 🔍 Search Bar
- Filter entities by ID or name
- Real-time search as you type
- Works across ALL 552 entities (not just the 219 in the old catalog)

#### 🔄 PNG Remapping
- Assign any PNG to any entity ID
- **Use Case:** Found a great sword icon but it doesn't match? Remap it to a different sword!
- Automatically renames and saves to `custom_icons/` directory
- Won't overwrite existing icons
- Remapped icons appear in the selector immediately

#### 📋 Catalog Refresh
- "Refresh Catalog" button to reload entity list from disk
- Useful after running the catalog generator or adding new JSON files

#### 💾 Custom Icons Directory
- Location: `/home/user/Game-1/Game-1-modular/assets/custom_icons/`
- All remapped PNGs are stored here
- Format: `{entity_id}.png`
- Registry file tracks all remappings: `icon_remap_registry.json`

**Usage:**
```bash
cd /home/user/Game-1/Game-1-modular/assets
python3 icon-selector-enhanced.py
```

**Requirements:**
```bash
pip install pillow
```

**Workflow:**

1. **Search for an Entity**
   - Type in the search bar (e.g., "copper", "warrior", "quest")
   - Results filter in real-time
   - Shows ID, name, and category

2. **Browse Available Icons**
   - Current placeholder (if exists)
   - All generated versions from icon generation cycles
   - Custom/remapped icons (labeled "Custom (Remapped)")

3. **Select an Icon**
   - Click on an icon to select it (green highlight)
   - Multiple selections = "Save for Later" (deferred decision)
   - Single selection = enables "Replace Placeholder" and "Remap to Different ID"

4. **Replace Placeholder**
   - Copies selected PNG to the correct location
   - Automatically backs up old version to `replaced_placeholders/`
   - Creates directory structure if needed

5. **Remap to Different ID**
   - Click "Remap to Different ID"
   - Search dialog opens with all 552 entities
   - Select target entity
   - PNG is copied to `custom_icons/{target_id}.png`
   - Appears immediately when viewing that entity

---

## Directories Created/Modified

### Created:
```
/home/user/Game-1/Game-1-modular/assets/custom_icons/
  └── (remapped PNG files with entity IDs as names)

/home/user/Game-1/Scaled JSON Development/
  ├── COMPLETE_ENTITY_CATALOG.txt
  ├── complete_entity_catalog.json
  └── ICON_TOOLS_GUIDE.md (this file)
```

### Modified:
```
/home/user/Game-1/Game-1-modular/tools/complete_entity_catalog.py (created)
/home/user/Game-1/Game-1-modular/assets/icon-selector-enhanced.py (created)
```

### Registry Files:
```
/home/user/Game-1/Game-1-modular/assets/icon_remap_registry.json
  └── Tracks all PNG remappings (source → target)

/home/user/Game-1/Game-1-modular/assets/deferred_icon_decisions.json
  └── Stores deferred decisions (unchanged from original tool)
```

---

## How PNG Remapping Works

### Problem Scenario
You generate icons and find:
- `iron_sword.png` looks perfect for a steel longsword
- `steel_sword.png` would work better as an iron shortsword
- You want to swap them without overwriting the originals

### Solution: Remapping

**Step 1:** Open enhanced icon selector
```bash
python3 icon-selector-enhanced.py
```

**Step 2:** Search for `iron_sword`
- You see the generated `iron_sword.png`

**Step 3:** Select the iron_sword icon you like

**Step 4:** Click "Remap to Different ID"
- Search dialog opens
- Search for "steel_longsword"
- Select it from the list

**Step 5:** Confirm
- The PNG is copied to `custom_icons/steel_longsword.png`
- Original `iron_sword.png` is untouched
- When you view "steel_longsword", this icon now appears as "Custom (Remapped)"

**Step 6:** Assign it permanently
- Select the "Custom (Remapped)" version
- Click "Replace Placeholder"
- Done! Now `steel_longsword` has that icon

### Registry Tracking
All remappings are logged in `icon_remap_registry.json`:
```json
{
  "steel_longsword": {
    "source_path": "icons-generation-cycle-1/generated_icons/items/weapons/iron_sword.png",
    "remapped_at": "2025-12-08T10:30:00",
    "target_id": "steel_longsword"
  }
}
```

---

## Entity Categories and Icon Paths

The tools automatically determine the correct icon path for each entity type:

| Entity Type | Base Folder | Subfolder | Example Path |
|------------|-------------|-----------|--------------|
| Equipment (Weapons) | `items` | `weapons` | `items/weapons/iron_shortsword.png` |
| Equipment (Armor) | `items` | `armor` | `items/armor/iron_helmet.png` |
| Equipment (Tools) | `items` | `tools` | `items/tools/copper_pickaxe.png` |
| Materials | `items` | `materials` | `items/materials/copper_ore.png` |
| Consumables | `items` | `consumables` | `items/consumables/health_potion.png` |
| Devices | `items` | `devices` | `items/devices/turret.png` |
| Stations | `items` | `stations` | `items/stations/forge.png` |
| Enemies | `enemies` | - | `enemies/slime_green.png` |
| Resources | `resources` | - | `resources/oak_tree.png` |
| Skills | `skills` | - | `skills/sprint.png` |
| Titles | `titles` | - | `titles/novice_warrior.png` |
| **Classes** | `classes` | - | `classes/warrior.png` *(new)* |
| **NPCs** | `npcs` | - | `npcs/tutorial_guide.png` *(new)* |
| **Quests** | `quests` | - | `quests/tutorial_quest.png` *(new)* |

---

## Recommendations

### 1. Create Icons for Missing Entities

You now have a complete list of all entities. Consider creating icons for:
- **Classes (6):** warrior, ranger, scholar, artisan, scavenger, adventurer
- **NPCs (6):** tutorial_guide, mysterious_trader, combat_trainer, etc.
- **Quests (6):** tutorial_quest, gathering_quest, combat_quest, etc.

Create directories:
```bash
cd /home/user/Game-1/Game-1-modular/assets
mkdir -p classes npcs quests
```

### 2. Update Icon Generator

Consider updating `tools/unified_icon_generator.py` to include these new categories in future catalog generations.

### 3. Use Enhanced Selector as Default

The enhanced icon selector is backward-compatible with the original but has many improvements. Consider using it as your primary tool:
```bash
# Make it executable
chmod +x icon-selector-enhanced.py

# Optional: Create an alias
alias icon-selector='python3 /home/user/Game-1/Game-1-modular/assets/icon-selector-enhanced.py'
```

### 4. Regular Catalog Updates

Run the complete entity catalog generator periodically to catch new entities:
```bash
cd /home/user/Game-1/Game-1-modular
python3 tools/complete_entity_catalog.py
```

---

## Quick Reference

### Generate Complete Catalog
```bash
cd /home/user/Game-1/Game-1-modular
python3 tools/complete_entity_catalog.py
```

### Launch Enhanced Icon Selector
```bash
cd /home/user/Game-1/Game-1-modular/assets
python3 icon-selector-enhanced.py
```

### View Complete Entity List
```bash
cat "/home/user/Game-1/Scaled JSON Development/COMPLETE_ENTITY_CATALOG.txt"
```

### View JSON Export
```bash
cat "/home/user/Game-1/Scaled JSON Development/complete_entity_catalog.json" | python3 -m json.tool
```

### Check Remapping Registry
```bash
cat /home/user/Game-1/Game-1-modular/assets/icon_remap_registry.json
```

---

## Troubleshooting

### "No matches found" in search
- Check spelling
- Try searching by partial name (e.g., "copper" instead of "copper_ore")
- Click "Refresh Catalog" to reload

### "No icons found for this entity"
- Entity exists in JSON but no icons generated yet
- Check if entity needs icons (recipes/placements don't need visual icons)
- Generate icons for this entity type

### Remapped icon doesn't appear
- Click "Refresh Catalog" button
- Restart the icon selector
- Check `custom_icons/` directory to verify file exists

### Can't find a specific entity
- Run the catalog generator to see all entities
- Check `COMPLETE_ENTITY_CATALOG.txt` for the exact ID
- Some entities might be in the JSON but not loaded by the game yet

---

## Summary

**Problems Solved:**
1. ✅ Identified all missing entities from icon catalog (NPCs, Quests, Classes, Resources)
2. ✅ Created tool to scan and list ALL game entities (552 total)
3. ✅ Created enhanced icon selector with search functionality
4. ✅ Added PNG remapping feature to reassign icons to different entities
5. ✅ Automatic refresh and real-time updates
6. ✅ Custom icons directory prevents overwrites

**New Capabilities:**
- Search through all 552 entities by ID or name
- Remap any PNG to any entity
- Track all remappings in a registry
- Refresh catalog without restarting
- Support for ALL entity types (not just items)

**Files to Use:**
- Run: `/home/user/Game-1/Game-1-modular/tools/complete_entity_catalog.py`
- UI: `/home/user/Game-1/Game-1-modular/assets/icon-selector-enhanced.py`
- Read: `/home/user/Game-1/Scaled JSON Development/COMPLETE_ENTITY_CATALOG.txt`

---

**Last Updated:** 2025-12-08
**Tools Version:** 1.0

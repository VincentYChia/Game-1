# Update-N System — Authoring, Automation, and Deployment

**Last Updated**: 2026-04-24
**Status**: Production Ready
**Purpose**: Complete reference for adding unlimited game content via JSON with zero code changes. Covers authoring workflow, tool invocations, architecture, validation, troubleshooting, best practices, and scaling.

> **Doc history (2026-04-24)**: This consolidates two prior docs — `UPDATE_N_AUTOMATION_WORKFLOW.md` (workflow + templates) and `UPDATE_SYSTEM_DOCUMENTATION.md` (architecture + tools + conflict resolution). Nothing unique to either has been dropped.

---

## Table of Contents

1. [Overview & Key Features](#overview--key-features)
2. [Quick Start](#quick-start)
3. [System Architecture](#system-architecture)
4. [Step-by-Step Authoring Workflow](#step-by-step-authoring-workflow)
5. [JSON File Templates](#json-file-templates)
6. [Tools Reference](#tools-reference)
7. [Auto-Detection Logic](#auto-detection-logic)
8. [Icon Generation](#icon-generation)
9. [Validation & Conflict Detection](#validation--conflict-detection)
10. [Uninstalling Updates](#uninstalling-updates)
11. [Troubleshooting](#troubleshooting)
12. [Advanced Usage & Scaling](#advanced-usage--scaling)
13. [Integration with Tag System](#integration-with-tag-system)
14. [Performance Notes](#performance-notes)
15. [Best Practices](#best-practices)
16. [Future Enhancements](#future-enhancements)

---

## Overview & Key Features

The Update-N system lets you ship unlimited game content (weapons, skills, enemies, recipes, materials, consumables, devices) through JSON files with **zero code changes**. Content is discovered, loaded, and integrated automatically on game launch.

**Key features:**

- ✅ **Zero Code Changes** — Add content via JSON only
- ✅ **Automatic Discovery** — Databases auto-load Update-N content
- ✅ **Conflict Detection** — Warns about duplicate IDs across core + all updates
- ✅ **Version Tracking** — `updates_manifest.json` tracks installed updates
- ✅ **One-Command Deployment** — Single script handles validation, icons, catalog, install
- ✅ **Scalable** — Update-1 through Update-999+ (tested with 100+)
- ✅ **Uninstallable** — Remove content cleanly, keep files
- ✅ **Full Tag-System Integration** — Combat tags work automatically

---

## Quick Start

Deploy an update and launch the game:

```bash
python tools/deploy_update.py Update-1 --force
python main.py
```

That's it. Your content is in the game.

---

## System Architecture

### Directory Structure

```
Game-1-modular/
├── Update-1/                          # First content pack
│   ├── items-testing-integration.JSON
│   ├── skills-testing-integration.JSON
│   ├── hostiles-testing-integration.JSON
│   ├── README.md
│   └── QUICKSTART.md
├── Update-2/                          # Future content
│   └── ...
├── updates_manifest.json              # Tracks installed updates
└── tools/
    ├── deploy_update.py               # ONE COMMAND deployment
    ├── update_manager.py              # Install/uninstall/validate
    ├── create_placeholder_icons_simple.py
    └── update_catalog.py
```

### Database Auto-Discovery

**File**: `data/databases/update_loader.py`

On game launch, this module:

1. Reads `updates_manifest.json`
2. Scans all installed Update-N directories
3. Loads JSONs into appropriate databases (`EquipmentDatabase`, `SkillDatabase`, `EnemyDatabase`, `MaterialDatabase`, `RecipeDatabase`)
4. No code changes to core databases needed

**Integration point**: `core/game_engine.py` (~line 122):

```python
# Load content from installed Update-N packages
from data.databases.update_loader import load_all_updates
load_all_updates(get_resource_path(""))
```

### Manifest System

**File**: `updates_manifest.json`

```json
{
  "version": "1.0",
  "installed_updates": ["Update-1", "Update-2"],
  "schema_version": 1,
  "last_updated": "2025-12-25T22:08:14.928553"
}
```

Automatically managed — don't edit manually.

---

## Step-by-Step Authoring Workflow

### 1. Create Update Directory

```bash
mkdir Update-2
```

**Naming Convention**: `Update-{N}` where N is sequential (Update-1, Update-2, etc.).

### 2. Add Content JSONs

Create JSON files for your content in the Update directory:

```
Update-2/
├── items-my-weapons.JSON          # Equipment
├── skills-my-magic.JSON            # Skills
├── hostiles-my-bosses.JSON         # Enemies
├── recipes-smithing-my-weapons.JSON # Recipes
└── README.md                       # Optional documentation
```

**Required JSON files** (supported patterns):

- **Items**: `items-*.JSON`, `weapons-*.JSON`, `armor-*.JSON`, `tools-*.JSON`
- **Skills**: `skills-*.JSON`
- **Enemies**: `hostiles-*.JSON`, `enemies-*.JSON`
- **Recipes**: `recipes-{station}-*.JSON` (smithing, alchemy, refining, engineering, adornments)
- **Optional**: `materials-*.JSON`, `consumables-*.JSON`, `devices-*.JSON`

### 3. Deploy Update

```bash
python tools/deploy_update.py Update-2 --force
```

**What this does**:

1. Validates all JSON files
2. Checks for ID conflicts
3. Generates placeholder icons
4. Updates the Vheer AI catalog
5. Installs update (adds to `updates_manifest.json`)

**Options**:

- `--skip-icons`: Don't generate placeholder icons
- `--skip-catalog`: Don't update the Vheer catalog
- `--force`: Skip confirmation prompt

### 4. Generate Icons (Happens Automatically)

Icons are generated automatically during deployment. For manual generation:

```bash
python tools/create_placeholder_icons_simple.py --update Update-2
```

### 5. Update Catalog (For AI Icon Generation)

```bash
python tools/update_catalog.py --update Update-2
```

This appends to `assets/icon_catalog.json` / `tools/ITEM_CATALOG_FOR_ICONS.md` for Vheer AI icon generation.

### 6. Test In-Game

```bash
python main.py
```

On launch, the system:

1. Reads `updates_manifest.json`
2. Scans installed Update-N directories
3. Auto-loads: equipment, skills, enemies, materials, recipes
4. Content immediately available

**Expected console output**:

```
======================================================================
📦 Loading 1 Update-N package(s): Update-2
======================================================================

🔄 Loading equipment from 1 update(s)...
   📦 Loading: Update-2/items-my-weapons.JSON
✓ Loaded 5 equipment items

🔄 Loading skills from 1 update(s)...
   ⚡ Loading: Update-2/skills-my-magic.JSON
✓ Loaded 6 skills

🔄 Loading enemies from 1 update(s)...
   👾 Loading: Update-2/hostiles-my-bosses.JSON
✓ Loaded 3 additional enemies

🔄 Loading recipes from 1 update(s)...
   📜 Loading: Update-2/recipes-smithing-my-weapons.JSON
   ✓ Loaded 5 recipes for smithing

✅ Update-N packages loaded successfully
======================================================================
```

---

## JSON File Templates

### Items Template (`items-*.JSON`)

```json
{
  "metadata": {
    "version": "1.0",
    "description": "Your item description"
  },

  "test_weapons": [
    {
      "itemId": "my_sword",
      "name": "My Awesome Sword",
      "category": "equipment",
      "type": "weapon",
      "slot": "mainHand",
      "tier": 3,
      "rarity": "rare",
      "stats": {
        "damage": [40, 60],
        "bonuses": {
          "STR": 5
        }
      },
      "flags": {
        "tradeable": true
      },
      "metadata": {
        "narrative": "A legendary sword forged in dragon fire.",
        "tags": ["melee", "1H"]
      },
      "combatTags": ["fire", "cone", "burn"],
      "combatParams": {
        "baseDamage": 50,
        "cone_angle": 45.0,
        "cone_range": 5.0,
        "burn_duration": 10.0,
        "burn_damage_per_second": 5.0
      }
    }
  ]
}
```

### Skills Template (`skills-*.JSON`)

```json
{
  "metadata": {
    "version": "1.0",
    "description": "Your skill description"
  },

  "skills": [
    {
      "skillId": "my_fireball",
      "name": "Fireball",
      "tier": 3,
      "rarity": "rare",
      "categories": ["combat", "fire"],
      "description": "Launch a fireball",
      "narrative": "Harness the power of flame!",
      "tags": ["damage", "fire", "ranged"],

      "effect": {
        "type": "damage",
        "category": "damage",
        "magnitude": "high",
        "target": "area",
        "duration": "instant"
      },

      "combatTags": ["fire", "circle", "burn"],
      "combatParams": {
        "baseDamage": 100,
        "circle_radius": 5.0,
        "origin": "target",
        "burn_duration": 8.0,
        "burn_damage_per_second": 10.0
      },

      "cost": {
        "mana": "high",
        "cooldown": "moderate"
      },

      "requirements": {
        "characterLevel": 15,
        "stats": {"INT": 20}
      }
    }
  ]
}
```

### Enemies Template (`hostiles-*.JSON`)

```json
{
  "metadata": {
    "version": "1.0",
    "description": "Your enemy description"
  },

  "abilities": [
    {
      "abilityId": "fire_blast",
      "name": "Fire Blast",
      "tags": ["fire", "circle", "burn", "player"],
      "effectParams": {
        "baseDamage": 60,
        "circle_radius": 5.0,
        "origin": "source",
        "burn_duration": 8.0,
        "burn_damage_per_second": 5.0
      },
      "cooldown": 10.0,
      "triggerConditions": {
        "healthThreshold": 1.0,
        "distanceMax": 8.0
      }
    }
  ],

  "enemies": [
    {
      "metadata": {
        "narrative": "A fire elemental boss."
      },
      "enemyId": "fire_lord",
      "name": "Fire Lord",
      "tier": 4,
      "category": "elemental",
      "behavior": "aggressive_ranged",
      "stats": {
        "health": 1000,
        "damage": [50, 70],
        "defense": 40,
        "speed": 1.5,
        "aggroRange": 15,
        "attackSpeed": 1.2
      },
      "drops": [
        {
          "materialId": "fire_crystal",
          "quantity": [2, 5],
          "chance": "high"
        }
      ],
      "aiPattern": {
        "defaultState": "patrol",
        "aggroOnDamage": true,
        "aggroOnProximity": true,
        "fleeAtHealth": 0.0,
        "callForHelpRadius": 10.0,
        "packCoordination": false,
        "specialAbilities": ["fire_blast"]
      }
    }
  ]
}
```

### Recipes Template (`recipes-{station}-*.JSON`)

```json
{
  "metadata": {
    "version": "1.0",
    "description": "Smithing recipes for my weapons"
  },

  "recipes": [
    {
      "recipeId": "recipe_my_sword",
      "outputId": "my_sword",
      "outputQty": 1,
      "stationTier": 3,
      "inputs": [
        {"materialId": "steel_ingot", "quantity": 5},
        {"materialId": "fire_crystal", "quantity": 2}
      ]
    }
  ]
}
```

### Minimum Required Structure

All JSON files must have:

```json
{
  "metadata": {
    "version": "1.0",
    "description": "Description of content",
    "note": "Optional notes"
  },

  "items": [],      // Or skills, enemies, etc.
  "test_weapons": []  // Alternative key names supported
}
```

### Supported Content Types

| Type | Key Names | Example File |
|------|-----------|--------------|
| **Items (Equipment)** | `items`, `test_weapons`, `weapons`, `armor` | `items-*.JSON` |
| **Skills** | `skills` | `skills-*.JSON` |
| **Enemies** | `enemies` | `hostiles-*.JSON`, `enemies-*.JSON` |
| **Materials** | `materials` | `materials-*.JSON` |
| **Consumables** | `consumables` | `consumables-*.JSON` |
| **Devices** | `devices` | `devices-*.JSON` |

### ID Requirements

Every entity must have a unique ID:

- Items: `itemId`
- Skills: `skillId`
- Enemies: `enemyId`
- Recipes: `recipeId`

IDs must be unique **across all files** — including core game files AND all other installed updates.

---

## Tools Reference

### `deploy_update.py` (Recommended)

**One-command deployment with full automation**

```bash
# Deploy Update-1 (all steps)
python tools/deploy_update.py Update-1 --force

# Skip icon generation
python tools/deploy_update.py Update-1 --skip-icons

# Skip catalog update
python tools/deploy_update.py Update-1 --skip-catalog
```

**What it does**:

1. Validates JSON files
2. Generates placeholder icons
3. Updates the Vheer catalog
4. Installs update

### `update_manager.py`

**Lower-level control**

```bash
# List all updates
python tools/update_manager.py list

# Validate without installing
python tools/update_manager.py validate Update-1

# Install
python tools/update_manager.py install Update-1 [--force]

# Uninstall
python tools/update_manager.py uninstall Update-1
```

### `create_placeholder_icons_simple.py`

**Generate placeholder PNGs**

```bash
# All test content
python tools/create_placeholder_icons_simple.py --all-test-content

# Specific JSON
python tools/create_placeholder_icons_simple.py --json items.JSON/items-testing-integration.JSON
```

Creates 64x64 colored squares in `assets/generated_icons/`.

### `update_catalog.py`

**Add content to Vheer AI catalog**

```bash
# Update from Update-N
python tools/update_catalog.py --update Update-1

# Specific JSON
python tools/update_catalog.py --json items.JSON/items-testing-integration.JSON
```

Appends to `tools/ITEM_CATALOG_FOR_ICONS.md` for AI icon generation.

---

## Auto-Detection Logic

### Equipment Loading

- Scans for: `*items*.JSON`, `*weapons*.JSON`, `*armor*.JSON`, `*tools*.JSON`
- Filters by: `category: "equipment"` or equipment-specific slots
- Loads into: `EquipmentDatabase`

### Skill Loading

- Scans for: `*skills*.JSON`
- Loads into: `SkillDatabase`

### Enemy Loading

- Scans for: `*hostiles*.JSON`, `*enemies*.JSON`
- Loads into: `EnemyDatabase`
- Uses `load_additional_file()` to append to existing enemies

### Recipe Loading

- Scans for: `*recipes*.JSON`, `*crafting*.JSON`
- Station type detected from filename:
  - `recipes-smithing-*.JSON` → smithing station
  - `recipes-alchemy-*.JSON` → alchemy station
  - `recipes-refining-*.JSON` → refining station
  - `recipes-engineering-*.JSON` → engineering station
  - `recipes-adornments-*.JSON` → enchanting station
- Loads into: `RecipeDatabase`

---

## Icon Generation

### Only Generates for Update-N Content

Icons are ONLY generated for items in Update-N JSONs, **NOT** for core content.

**Example**:

- `Update-2/items-my-weapons.JSON` contains 5 weapons
- System generates 5 PNG icons in `assets/items/weapons/`
- Does NOT scan/generate for core `items.JSON/items-smithing-2.JSON`

### Icon Paths Follow Database Logic

Equipment Database auto-generates paths:

- Weapons → `weapons/{itemId}.png`
- Armor → `armor/{itemId}.png`
- Tools → `tools/{itemId}.png`
- Accessories → `accessories/{itemId}.png`
- Stations → `stations/{itemId}.png`

Material Database auto-generates paths:

- Consumables → `consumables/{itemId}.png`
- Devices → `devices/{itemId}.png`
- Materials → `materials/{itemId}.png`

Skill Database:

- Skills → `skills/{skillId}.png`

Enemy Database:

- Enemies → `enemies/{enemyId}.png`

Full per-item catalog used by the AI pipeline lives at `assets/icons/ITEM_CATALOG_FOR_ICONS.md` (auto-generated).

---

## Validation & Conflict Detection

### What Gets Validated

1. **JSON Syntax** — Must be valid JSON
2. **Required Fields** — `metadata` section must exist
3. **ID Uniqueness** — No duplicate item/skill/enemy IDs across all files (core + Update-N)
4. **Content Exists** — At least one content section (items, skills, enemies, or recipes)
5. **File Structure** — Recognizes items/skills/enemies JSONs

**Validation does NOT check**:

- Tag validity (checked at runtime)
- Parameter correctness (checked at runtime)
- Balance/gameplay (your responsibility)

### Conflict Detection

```bash
python tools/update_manager.py validate Update-2
```

**Checks**:

- Duplicate `itemId`, `skillId`, `enemyId`, `recipeId`
- Conflicts with core content
- Conflicts with other installed updates

**Example success output**:

```
✅ Validation passed:
   - 5 items found
   - 6 skills found
   - No ID conflicts
   - All required fields present
```

**Example conflict output**:

```
⚠️  Conflicts detected:
   - Item ID conflict: copper_sword (exists in items-smithing-2.JSON)
   - Skill ID conflict: fireball (exists in skills-skills-1.JSON)
```

### Resolution Options

**Option 1: Rename conflicting IDs**

```json
{
  "itemId": "copper_sword_v2",  // Changed from copper_sword
  "name": "Copper Sword"
}
```

**Option 2: Force install (overwrites)**

```bash
python tools/update_manager.py install Update-1 --force
```

**Best practice**: Use unique prefixes

```json
{
  "itemId": "update1_copper_sword",
  "skillId": "update1_fireball",
  "enemyId": "update1_demon_lord"
}
```

---

## Uninstalling Updates

```bash
python tools/update_manager.py uninstall Update-2
```

**What this does**:

1. Removes Update-2 from `updates_manifest.json`
2. Content won't load on next game launch
3. Does NOT delete the Update-2 directory or icons

**To fully remove**:

```bash
python tools/update_manager.py uninstall Update-2
rm -rf Update-2
```

---

## Troubleshooting

### Content Doesn't Appear In-Game

Check console output:

1. **Does the update appear in the installed list?**
   ```
   📦 Loading 1 Update-N package(s): Update-2
   ```

2. **Did files load?**
   ```
   📦 Loading: Update-2/items-my-weapons.JSON
   ✓ Loaded 5 equipment items
   ```

3. **Any errors?**
   ```
   ⚠️  Error loading items-my-weapons.JSON: invalid JSON
   ```

**Common issues**:

- JSON syntax error → Fix JSON
- Missing `itemId` field → Add required fields
- ID conflict → Change ID to be unique
- Wrong file name pattern → Rename to match scan patterns

### "Update directory not found"

```
Error: Update directory not found: Update-1
```

**Fix**: Directory must be at project root.

```bash
ls -la | grep Update
# Should show: drwxr-xr-x Update-1/
```

### "No .JSON files found"

```
Error: No .JSON files found in Update-1/
```

**Fix**: JSON files must use the `.JSON` extension (uppercase).

```bash
# Wrong
items.json

# Correct
items.JSON
```

### "Validation failed: Invalid JSON"

```
Error: items-testing.JSON: Invalid JSON - Expecting ',' delimiter
```

**Fix**: Check JSON syntax with a validator.

```bash
python -m json.tool items-testing.JSON
```

### Recipes Not Found

**Requirements**:

1. Recipe file must match pattern: `*recipes*.JSON` or `*crafting*.JSON`
2. Recipe `outputId` must match equipment `itemId`
3. Station type must be detected (from filename) or defaulted to smithing
4. Material IDs in `inputs` must exist in MaterialDatabase

### Skills Show Warnings

**Area-effect skills**:

```
⚡ Meteor Strike: Combat skill using tags ['fire', 'circle', 'burn']
   ⚠ Area skill requires combat context
```

**This is correct behavior**:

- Area skills (`"target": "area"`) only work in combat
- Enemy skills (`"target": "enemy"`) only work in combat
- Self skills (`"target": "self"`) work anytime

**Solution**: Use skills during combat, not outside.

### Manifest Corrupted

```bash
cat updates_manifest.json
# Should list your update in installed_updates
```

If corrupted, reinstall:

```bash
python tools/update_manager.py install Update-N --force
```

### Game Caching Old Data

```bash
# Clear Python cache
find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null
```

### False-Positive Conflicts

This happens when test files exist in both Update-N and core directories.

**Fix**: Use `--force` flag on install.

---

## Advanced Usage & Scaling

### Multiple Updates

Install multiple updates:

```bash
python tools/deploy_update.py Update-1 --force
python tools/deploy_update.py Update-2 --force
python tools/deploy_update.py Update-3 --force
```

All will load automatically on game launch.

### Selective Loading

Uninstall unwanted updates:

```bash
python tools/update_manager.py uninstall Update-2
```

Update-1 and Update-3 remain installed.

### Update Priority

Updates load in **alphabetical order**. For load order control:

```
Update-001-base-content/
Update-002-expansion-1/
Update-003-hotfix/
```

Later updates can override earlier ones (if IDs conflict with `--force`).

### Creating 100 Updates

```bash
for i in {1..100}; do
  mkdir Update-$i
  # Add your JSON files
  python tools/deploy_update.py Update-$i --force
done

python main.py  # All 100 updates auto-load
```

### Content Pipeline

```
1. Designer creates JSON in Update-N/
2. Run: python tools/deploy_update.py Update-N
3. Test in-game
4. Iterate on JSON (no recompile needed)
5. When ready: git commit Update-N/
6. CI/CD deploys to production
```

### No-Code Deployment

```bash
# Production server
git pull
python tools/update_manager.py install Update-42
# Content live immediately
```

### Hotfixes

```bash
# Create hotfix
mkdir Update-43-hotfix
# Add fixed JSON
python tools/deploy_update.py Update-43-hotfix
# Deployed in seconds
```

---

## Integration with Tag System

Updates fully integrate with the tag system:

```json
{
  "itemId": "update1_plasma_rifle",
  "name": "Plasma Rifle",
  "type": "weapon",
  "slot": "mainHand",
  "effectTags": ["beam", "pierce", "lightning", "shock"],
  "effectParams": {
    "baseDamage": 120,
    "beam_range": 15.0,
    "pierce_count": 5,
    "shock_duration": 8.0,
    "damage_per_tick": 15.0
  }
}
```

**No code changes needed** — the tag system processes these automatically. See `docs/tag-system/` for the full tag vocabulary.

---

## Performance Notes

### Loading Time

- **Per Update**: ~50-200ms depending on content count
- **5 Updates**: ~250ms-1s additional load time
- **100 Updates**: ~5-20 seconds total load time
- **Negligible** for reasonable update counts (<10)

### Memory

- Each JSON loaded into memory
- ~1-5 MB per update (typical)
- Minimal impact

### Runtime

- **Zero** performance impact
- Updates load once at game start
- After loading, content is identical to core content

---

## Best Practices

### 1. Organize by Feature

```
Update-1/  # Tag system test content
Update-2/  # Fire magic expansion
Update-3/  # Desert biome enemies
Update-4/  # Halloween event
```

### 2. Use Descriptive IDs

```json
// Bad
{"itemId": "sword1"}

// Good
{"itemId": "halloween_pumpkin_sword"}
```

### 3. Version Your Updates

```
Update-001-base/
Update-002-hotfix-balance/
Update-003-expansion-desert/
```

### 4. Test Before Deploying

```bash
# Validate first
python tools/update_manager.py validate Update-1

# Then deploy
python tools/deploy_update.py Update-1 --force
```

### 5. Document Your Updates

Create README.md in each Update-N directory:

```markdown
# Update-2: Fire Magic Expansion

## Contents
- 10 fire magic skills
- 3 fire-themed weapons
- 5 fire elemental enemies

## Testing Checklist
- [ ] All skills load
- [ ] Fire damage works
- [ ] Burn status applies
```

---

## Before vs. After

### Before the Update System

**To add 5 weapons:**

1. Edit `items.JSON/items-smithing-2.JSON`
2. Risk breaking existing content
3. Hard to track changes
4. Merge conflicts in git
5. Can't easily remove

**To deploy:**

1. Modify core files
2. Restart game
3. Hope nothing broke

### After the Update System

**To add 5 weapons:**

1. Create `Update-N/weapons.JSON`
2. `python tools/deploy_update.py Update-N`
3. Done

**To deploy:**

1. Copy Update-N/ to server
2. One command
3. Live immediately

---

## Future Enhancements

**Planned**:

- [ ] Schema validation (JSON schemas for each type)
- [ ] Dependency system (Update-2 requires Update-1)
- [ ] Hot-reload (load updates without restart)
- [ ] Web UI for update management
- [ ] Automatic conflict resolution
- [ ] Update versioning (v1.0, v1.1, etc.)
- [ ] Rollback system
- [ ] Delta updates (only changed files)

**Community contributions welcome.**

---

## Summary Checklist

- ✅ Create Update-N directory
- ✅ Add content JSONs (items, skills, enemies, recipes)
- ✅ Run `deploy_update.py Update-N --force`
- ✅ Icons generate automatically (only for Update-N content)
- ✅ Catalog updated for AI icon generation
- ✅ Launch game
- ✅ Check console for loading confirmation
- ✅ Test content in-game (inventory, crafting, combat)

```bash
python tools/deploy_update.py Update-N --force
```

**One command. Zero friction. Infinite scale.**

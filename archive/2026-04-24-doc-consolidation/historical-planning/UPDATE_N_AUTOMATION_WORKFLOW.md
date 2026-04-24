# Update-N Automation Workflow

**Version**: 1.0
**Last Updated**: 2025-12-25
**Purpose**: Complete end-to-end workflow for creating game content through Update-N system

---

## Overview

The Update-N system enables adding unlimited game content (weapons, skills, enemies, recipes) through JSON files with **zero code changes**. Content is discovered, loaded, and integrated automatically on game launch.

---

## Step-by-Step Workflow

### 1. Create Update Directory

```bash
mkdir Update-2
```

**Naming Convention**: `Update-{N}` where N is sequential (Update-1, Update-2, etc.)

---

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

**Required JSON Files**:
- **Items**: items-*.JSON, weapons-*.JSON, armor-*.JSON
- **Skills**: skills-*.JSON
- **Enemies**: hostiles-*.JSON, enemies-*.JSON
- **Recipes**: recipes-{station}-*.JSON (recipes-smithing-*.JSON, recipes-alchemy-*.JSON, etc.)

**Optional**: materials-*.JSON, consumables-*.JSON, devices-*.JSON

---

### 3. Deploy Update

```bash
python tools/deploy_update.py Update-2 --force
```

**What This Does**:
1. Validates all JSON files
2. Checks for ID conflicts
3. Installs update (adds to `updates_manifest.json`)

**Options**:
- `--skip-icons`: Don't generate placeholder icons
- `--skip-catalog`: Don't update Vheer catalog
- `--force`: Skip confirmation prompt

---

### 4. Generate Icons (Automatic in deploy)

Icons are generated automatically during deployment. For manual generation:

```bash
python tools/create_placeholder_icons_simple.py --update Update-2
```

**Icon Paths** (auto-generated):
- Weapons → `assets/items/weapons/{itemId}.png`
- Armor → `assets/items/armor/{itemId}.png`
- Skills → `assets/skills/{skillId}.png`
- Enemies → `assets/enemies/{enemyId}.png`
- Devices → `assets/items/devices/{itemId}.png`
- Consumables → `assets/items/consumables/{itemId}.png`

**Note**: Only generates icons for items in Update-N JSON files, NOT core content.

---

### 5. Update Catalog (For AI Icon Generation)

```bash
python tools/update_catalog.py --update Update-2
```

This updates `assets/icon_catalog.json` for Vheer AI icon generation.

---

### 6. Test In-Game

```bash
python main.py
```

**On Launch**, the system:
1. Reads `updates_manifest.json`
2. Scans installed Update-N directories
3. Auto-loads: equipment, skills, enemies, materials, recipes
4. Content immediately available

**Check Console Output**:
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

### Items Template (items-*.JSON)

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

### Skills Template (skills-*.JSON)

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

### Enemies Template (hostiles-*.JSON)

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

### Recipes Template (recipes-{station}-*.JSON)

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

## Icon Generation Details

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

---

## Validation and Conflict Detection

### What Gets Validated

1. **JSON Syntax**: Must be valid JSON
2. **Required Fields**: metadata section must exist
3. **ID Uniqueness**: No duplicate item/skill/enemy IDs across all files (core + Update-N)
4. **Content Exists**: At least one content section (items, skills, enemies, or recipes)

### Conflict Detection

```bash
python tools/update_manager.py validate Update-2
```

**Checks**:
- Duplicate `itemId`, `skillId`, `enemyId`, `recipeId`
- Conflicts with core content
- Conflicts with other installed updates

**Example Output**:
```
✅ Validation passed:
   - 5 items found
   - 6 skills found
   - No ID conflicts
   - All required fields present
```

---

## Uninstalling Updates

```bash
python tools/update_manager.py uninstall Update-2
```

**What This Does**:
1. Removes Update-2 from `updates_manifest.json`
2. Content won't load on next game launch
3. Does NOT delete Update-2 directory or icons

**To fully remove**:
```bash
python tools/update_manager.py uninstall Update-2
rm -rf Update-2
```

---

## Troubleshooting

### Content Doesn't Appear In-Game

**Check Console Output**:
1. Does update appear in installed list?
   ```
   📦 Loading 1 Update-N package(s): Update-2
   ```

2. Did files load?
   ```
   📦 Loading: Update-2/items-my-weapons.JSON
   ✓ Loaded 5 equipment items
   ```

3. Any errors?
   ```
   ⚠️  Error loading items-my-weapons.JSON: invalid JSON
   ```

**Common Issues**:
- JSON syntax error → Fix JSON
- Missing `itemId` field → Add required fields
- ID conflict → Change ID to be unique
- Wrong file name pattern → Rename to match scan patterns

### Recipes Not Found

**Requirements**:
1. Recipe file must match pattern: `*recipes*.JSON` or `*crafting*.JSON`
2. Recipe `outputId` must match equipment `itemId`
3. Station type must be detected or defaulted to smithing
4. Material IDs in `inputs` must exist in MaterialDatabase

**Check Console**:
```
🔄 Loading recipes from 1 update(s)...
   📜 Loading: Update-2/recipes-smithing-my-weapons.JSON
   ✓ Loaded 5 recipes for smithing
```

### Skills Show Warnings

**Area-Effect Skills**:
```
⚡ Meteor Strike: Combat skill using tags ['fire', 'circle', 'burn']
   ⚠ Area skill requires combat context
```

**This is CORRECT behavior**:
- Area skills (`"target": "area"`) only work in combat
- Enemy skills (`"target": "enemy"`) only work in combat
- Self skills (`"target": "self"`) work anytime

**Solution**: Use skills during combat, not outside

---

## Advanced: Scaling to Production

### Creating 100 Updates

```bash
for i in {1..100}; do
  mkdir Update-$i
  # Add your JSON files
  python tools/deploy_update.py Update-$i --force
done

python main.py  # All 100 updates auto-load
```

### Performance

- **Per Update**: ~50-200ms load time
- **100 Updates**: ~5-20 seconds total load time
- **Memory**: ~1-5 MB per update
- **Runtime**: Zero impact (loads once at game start)

---

## Summary Checklist

✅ Create Update-N directory
✅ Add content JSONs (items, skills, enemies, recipes)
✅ Run `deploy_update.py Update-N --force`
✅ Icons generate automatically (only for Update-N content)
✅ Catalog updated for AI icon generation
✅ Launch game
✅ Check console for loading confirmation
✅ Test content in-game (inventory, crafting, combat)

---

**That's it!** The system handles everything else automatically.

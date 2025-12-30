# Developer Guide: Complete JSON Integration System

**Last Updated**: 2025-12-25
**Purpose**: Comprehensive guide for adding new content to the game via JSON

---

## Table of Contents

1. [System Overview](#system-overview)
2. [JSON Definition Types](#json-definition-types)
3. [Complete Integration Paths](#complete-integration-paths)
4. [PNG/Asset Generation](#pngasset-generation)
5. [Adding New Content](#adding-new-content)
6. [Batch Update System](#batch-update-system)
7. [Tag System Reference](#tag-system-reference)
8. [Troubleshooting](#troubleshooting)

---

## System Overview

### Architecture

```
JSON Definitions → Loaders → Databases → Game Systems → Rendering
                                                      ↓
                                              Vheer Automation
                                                      ↓
                                              PNG Generation
```

### Core Principles

1. **Data-Driven**: All content defined in JSON
2. **Tag-Based**: Effects/behaviors defined by tags
3. **Hot-Reloadable**: Changes detected on load
4. **Auto-Generated Assets**: PNGs generated from catalog

---

## JSON Definition Types

### Current JSON Files

```
Definitions.JSON/
├── hostiles-1.JSON           # Enemy definitions
├── resource-node-1.JSON      # Harvestable nodes
├── crafting-stations-1.JSON  # Smithing, refining, etc.
├── tag-definitions.JSON      # Tag system config
├── skills-translation-table.JSON
├── value-translation-table-1.JSON
└── templates-crafting-1.JSON

Skills/
├── skills-base-effects-1.JSON  # Effect magnitude values
└── skills-skills-1.JSON        # Skill definitions

items.JSON/
├── items-smithing-2.JSON      # Weapons, armor, tools
├── items-materials-1.JSON     # Ores, wood, stone
├── items-alchemy-1.JSON       # Potions, bombs
├── items-engineering-1.JSON   # Turrets, devices
├── items-refining-1.JSON      # Ingots, refined materials
├── items-testing-tags.JSON    # Tag system tests
└── items-tools-1.JSON         # Pickaxes, axes, etc.

recipes.JSON/
├── recipes-smithing-3.JSON
├── recipes-alchemy-1.JSON
├── recipes-refining-1.JSON
├── recipes-engineering-1.JSON
├── recipes-enchanting-1.JSON
└── recipes-adornments-1.json

placements.JSON/
├── placements-smithing-1.JSON
├── placements-alchemy-1.JSON
├── placements-refining-1.JSON
└── placements-engineering-1.JSON
```

---

## Complete Integration Paths

### 1. SKILLS Integration Path

#### JSON → Loader → Database → Manager → Execution

**Step 1: JSON Definition**
```json
// Skills/skills-skills-1.JSON
{
  "skillId": "my_new_skill",
  "name": "My New Skill",
  "tier": 2,
  "rarity": "uncommon",
  "categories": ["combat"],
  "description": "A powerful attack",
  "narrative": "Channel your inner strength...",
  "tags": ["damage", "fire", "aoe"],

  "effect": {
    "type": "devastate",
    "category": "damage",
    "magnitude": "moderate",
    "target": "area",
    "duration": "instant"
  },

  "combatTags": ["fire", "circle", "burn"],
  "combatParams": {
    "baseDamage": 50,
    "circle_radius": 5.0,
    "burn_duration": 10.0
  },

  "cost": {
    "mana": "moderate",
    "cooldown": "long"
  },

  "requirements": {
    "characterLevel": 10,
    "stats": {"INT": 15}
  }
}
```

**Step 2: Loader**
- File: `data/databases/skill_db.py`
- Class: `SkillDatabase`
- Method: `load_from_file()`
- Auto-generates icon path: `skills/{skill_id}.png`

**Step 3: Database Storage**
```python
# Singleton pattern
skill_db = SkillDatabase.get_instance()
skill_db.load_from_file("Skills/skills-skills-1.JSON")
```

**Step 4: Character Learning**
- File: `entities/components/skill_manager.py`
- Character can learn if requirements met
- Stored in `character.skills.learned_skills`

**Step 5: Execution**
- User activates skill (press 1-5)
- `skill_manager.use_skill()` called
- Effects applied via tag system
- Combat manager executes damage/status effects

**Step 6: Rendering**
- UI shows skill icon
- Cooldown displayed
- Mana cost checked

---

### 2. ITEMS/EQUIPMENT Integration Path

#### JSON → Loader → Database → Inventory → Equipment → Stats

**Step 1: JSON Definition**
```json
// items.JSON/items-smithing-2.JSON
{
  "weapons": [
    {
      "itemId": "my_flaming_sword",
      "name": "Flaming Sword",
      "tier": 3,
      "rarity": "rare",
      "category": "equipment",
      "type": "weapon",
      "slot": "mainHand",

      "stats": {
        "damage": [15, 25],
        "attackSpeed": 1.2,
        "durability": 500
      },

      "effect_tags": ["fire", "burn"],
      "effect_params": {
        "burn_duration": 5.0,
        "burn_damage_per_second": 3.0
      },

      "crafting": {
        "station": "forge",
        "materials": {
          "steel_ingot": 5,
          "fire_crystal": 2
        }
      }
    }
  ]
}
```

**Step 2: Loader**
- File: `data/databases/equipment_db.py`
- Class: `EquipmentDatabase`
- Filters by `category == 'equipment'`
- Separates from consumables/materials

**Step 3: Inventory System**
- Items can be added to `character.inventory`
- Stackable if not equipment
- Equipment items are unique instances

**Step 4: Equipment Manager**
- File: `entities/components/equipment_manager.py`
- Equip to slots: mainHand, offHand, head, chest, legs, feet
- Stats calculated on equip

**Step 5: Combat Integration**
- Weapon damage used in attacks
- Tags applied to attacks
- Durability consumed on use

**Step 6: Rendering**
- Inventory UI displays items
- Equipment UI shows worn items
- Icons loaded from `items/{subfolder}/{item_id}.png`

---

### 3. ENEMIES/HOSTILES Integration Path

#### JSON → Loader → Spawner → AI → Combat

**Step 1: JSON Definition**
```json
// Definitions.JSON/hostiles-1.JSON
{
  "enemyId": "my_fire_demon",
  "name": "Fire Demon",
  "category": "elemental",
  "tier": 3,

  "stats": {
    "health": 500,
    "damage": 40,
    "speed": 1.5,
    "attackSpeed": 1.0
  },

  "ai": {
    "aggroRange": 10.0,
    "chaseRange": 15.0,
    "behavior": "aggressive"
  },

  "specialAbilities": [
    {
      "abilityId": "fireball",
      "name": "Fireball",
      "tags": ["fire", "single", "burn", "player"],
      "effectParams": {
        "baseDamage": 60,
        "burn_duration": 8.0,
        "burn_damage_per_second": 10.0
      },
      "cooldown": 12.0,
      "triggerConditions": {
        "healthThreshold": 1.0,
        "distanceMax": 15.0
      }
    }
  ],

  "loot": [
    {"itemId": "fire_crystal", "chance": 0.3, "minQuantity": 1, "maxQuantity": 3}
  ]
}
```

**Step 2: Loader**
- File: `Combat/enemy.py`
- Class: `EnemyDefinitionDatabase`
- Parses abilities with tag system

**Step 3: Spawning**
- World generator creates enemy instances
- Positioned in chunks
- AI state initialized

**Step 4: AI System**
- File: `Combat/enemy.py`
- States: IDLE, WANDER, CHASE, ATTACK
- Distance checks for abilities
- Cooldown management

**Step 5: Combat**
- File: `Combat/combat_manager.py`
- Calls `enemy.use_special_ability()`
- Tag-based effect execution
- Status effects applied to player

**Step 6: Loot**
- On death, drop items from loot table
- Items added to world as pickups

**Step 7: Rendering**
- Enemy sprite displayed
- Health bar shown
- Ability animations

---

### 4. RECIPES Integration Path

#### JSON → Loader → Crafting UI → Minigame → Output

**Step 1: JSON Definition**
```json
// recipes.JSON/recipes-smithing-3.JSON
{
  "recipes": [
    {
      "recipeId": "flaming_sword",
      "category": "smithing",
      "tier": 3,
      "station": "forge",

      "requirements": {
        "characterLevel": 15,
        "skillLevel": {"smithing": 5}
      },

      "materials": {
        "steel_ingot": 5,
        "fire_crystal": 2,
        "leather_strap": 1
      },

      "outputs": [
        {
          "itemId": "flaming_sword",
          "quantity": 1,
          "guaranteedRarity": "rare"
        }
      ],

      "minigame": {
        "difficulty": "moderate",
        "timeLimit": 45,
        "perfectBonus": 0.2
      }
    }
  ]
}
```

**Step 2: Loader**
- File: `Crafting-subdisciplines/` (multiple files)
- Loaded per discipline
- Validated for material existence

**Step 3: Crafting UI**
- Station interaction opens UI
- Recipes filtered by station type
- Materials checked

**Step 4: Minigame**
- Timing-based crafting challenge
- Success determines output quality
- Perfect = bonus stats/rarity

**Step 5: Output**
- Item created with rolled stats
- Rarity determined
- Skill XP awarded
- Materials consumed

---

### 5. RESOURCE NODES Integration Path

#### JSON → Spawner → Interaction → Gathering → Drops

**Step 1: JSON Definition**
```json
// Definitions.JSON/resource-node-1.JSON
{
  "nodeId": "mythril_ore_node",
  "name": "Mythril Ore Vein",
  "tier": 4,
  "category": "ore",

  "gathering": {
    "requiredTool": "pickaxe",
    "toolTier": 3,
    "health": 800,
    "respawnTime": 300
  },

  "loot": [
    {"itemId": "mythril_ore", "minQuantity": 2, "maxQuantity": 5, "chance": 1.0},
    {"itemId": "rare_gem", "minQuantity": 1, "maxQuantity": 1, "chance": 0.1}
  ]
}
```

**Step 2: World Generation**
- File: `systems/natural_resource.py`
- Nodes placed in world
- Tier-appropriate placement

**Step 3: Interaction**
- Player clicks node
- Tool tier checked
- Gathering starts

**Step 4: Durability/Health**
- Node takes damage from tool
- Depletes when health reaches 0

**Step 5: Loot**
- Items dropped based on loot table
- Quantity randomized
- Added to inventory

**Step 6: Respawn**
- Timer starts if respawns
- Node regenerates after time
- Visual indicator shows progress

---

## PNG/Asset Generation

### System Overview

Assets are automatically generated using Vheer AI automation.

### The Catalog System

**File**: `assets/icons/ITEM_CATALOG_FOR_ICONS.md`

**Format**:
```markdown
### item_name
- **Category**: equipment
- **Type**: weapon
- **Subtype**: sword
- **Narrative**: Description for AI generation
```

**Auto-Generated By**: `tools/unified_icon_generator.py`

### Asset Generation Flow

```
JSON Definitions
    ↓
unified_icon_generator.py (scans all JSONs)
    ↓
ITEM_CATALOG_FOR_ICONS.md
    ↓
Vheer-automation.py (reads catalog)
    ↓
AI generates PNG (3 versions)
    ↓
assets/generated_icons-{N}/
```

### Folder Structure

```
assets/
├── generated_icons-2/    # Version 2 prompts
│   ├── items/
│   │   ├── weapons/
│   │   ├── armor/
│   │   ├── tools/
│   │   └── consumables/
│   ├── enemies/
│   ├── resources/
│   ├── skills/
│   └── titles/
├── generated_icons-3/    # Version 3 prompts
└── Vheer-automation.py   # Generator script
```

### Adding New Item to Catalog

**Manual Method** (for immediate testing):
```markdown
### my_new_sword
- **Category**: equipment
- **Type**: weapon
- **Subtype**: longsword
- **Narrative**: A legendary blade forged in dragon fire...
```

**Automatic Method** (recommended):
1. Add item to appropriate JSON
2. Run `tools/unified_icon_generator.py`
3. Catalog automatically updated
4. Run `assets/Vheer-automation.py`
5. PNGs generated

### Vheer Automation Details

**File**: `assets/Vheer-automation.py`

**Features**:
- Selenium-based automation
- Batch generation (all items or test mode)
- 3 versions with different prompts
- Automatic folder organization
- Error recovery

**Usage**:
```bash
cd assets
python Vheer-automation.py
# Choose: [1] Test (2 items) or [2] Full catalog
```

**Configuration**:
- `PERSISTENT_PROMPT`: Base style guide
- `VERSION_PROMPTS`: Version-specific refinements
- `TYPE_ADDITIONS`: Per-category guidance
- `GENERATION_TIMEOUT`: 180 seconds per item
- `VERSIONS_TO_GENERATE`: 3

---

## Adding New Content

### Workflow: Adding a New Weapon

**Step 1: Define in JSON**

File: `items.JSON/items-smithing-2.JSON` (or create `items-smithing-3.JSON`)

```json
{
  "weapons": [
    {
      "itemId": "shadow_dagger",
      "name": "Shadow Dagger",
      "tier": 4,
      "rarity": "epic",
      "category": "equipment",
      "type": "weapon",
      "slot": "mainHand",

      "stats": {
        "damage": [25, 35],
        "attackSpeed": 1.8,
        "durability": 300,
        "critChance": 0.25
      },

      "effect_tags": ["shadow", "single", "bleed"],
      "effect_params": {
        "baseDamage": 30,
        "bleed_duration": 8.0,
        "bleed_damage_per_second": 5.0
      },

      "narrative": "Forged from void-touched steel, this dagger seems to drink in light. Strikes from the shadows leave lingering wounds that refuse to heal."
    }
  ]
}
```

**Step 2: Add to Catalog**

Run:
```bash
python tools/unified_icon_generator.py
```

This scans all JSONs and updates `ITEM_CATALOG_FOR_ICONS.md`

**Step 3: Generate PNG**

Run:
```bash
python assets/Vheer-automation.py
```

Choose full catalog mode. Icon generated at:
`assets/generated_icons-3/items/weapons/shadow_dagger-3.png`

**Step 4: Create Recipe**

File: `recipes.JSON/recipes-smithing-3.JSON`

```json
{
  "recipes": [
    {
      "recipeId": "shadow_dagger",
      "category": "smithing",
      "tier": 4,
      "station": "forge",

      "materials": {
        "void_steel_ingot": 3,
        "shadow_essence": 2,
        "leather_wrap": 1
      },

      "outputs": [{
        "itemId": "shadow_dagger",
        "quantity": 1
      }]
    }
  ]
}
```

**Step 5: Test In-Game**

1. Restart game (reloads JSONs)
2. Check equipment database loaded item
3. Craft at forge or spawn via debug
4. Verify stats, effects, icon display

---

### Workflow: Adding a New Skill

**Step 1: Define Effect in Base Effects**

File: `Skills/skills-base-effects-1.JSON` (if new effect type)

Usually use existing: empower, devastate, fortify, etc.

**Step 2: Define Skill**

File: `Skills/skills-skills-1.JSON`

```json
{
  "skillId": "volcanic_eruption",
  "name": "Volcanic Eruption",
  "tier": 4,
  "rarity": "legendary",
  "categories": ["combat", "fire"],

  "description": "Summon a volcanic eruption that devastates all nearby foes.",
  "narrative": "The earth trembles at your command. Lava bursts forth, consuming all who dare stand against you.",

  "tags": ["damage", "fire", "aoe", "elemental"],

  "effect": {
    "type": "devastate",
    "category": "damage",
    "magnitude": "extreme",
    "target": "area",
    "duration": "instant"
  },

  "combatTags": ["fire", "circle", "burn"],
  "combatParams": {
    "baseDamage": 120,
    "circle_radius": 10.0,
    "origin": "source",
    "burn_duration": 15.0,
    "burn_damage_per_second": 12.0
  },

  "cost": {
    "mana": "extreme",
    "cooldown": "extreme"
  },

  "requirements": {
    "characterLevel": 30,
    "stats": {"INT": 25, "STR": 20}
  }
}
```

**Step 3: Add to Catalog & Generate Icon**

```bash
python tools/unified_icon_generator.py
python assets/Vheer-automation.py
```

Icon at: `assets/generated_icons-3/skills/volcanic_eruption-3.png`

**Step 4: Test**

1. Learn skill (debug command or meet requirements)
2. Equip to hotbar
3. Activate
4. Verify: instant execution, 10-tile radius, fire damage, burn applied

---

### Workflow: Adding a New Enemy

**Step 1: Define Enemy**

File: `Definitions.JSON/hostiles-1.JSON`

```json
{
  "enemyId": "shadow_wraith",
  "name": "Shadow Wraith",
  "category": "undead",
  "tier": 4,

  "stats": {
    "health": 600,
    "damage": 50,
    "speed": 2.0,
    "attackSpeed": 1.5,
    "armor": 20
  },

  "ai": {
    "aggroRange": 12.0,
    "chaseRange": 18.0,
    "behavior": "aggressive",
    "attackCooldown": 2.0
  },

  "specialAbilities": [
    {
      "abilityId": "shadow_bolt",
      "name": "Shadow Bolt",
      "tags": ["shadow", "single", "weaken", "player"],
      "effectParams": {
        "baseDamage": 70,
        "weaken_percent": 0.3,
        "weaken_duration": 10.0
      },
      "cooldown": 8.0,
      "triggerConditions": {
        "healthThreshold": 1.0,
        "distanceMax": 15.0
      }
    },
    {
      "abilityId": "phase_shift",
      "name": "Phase Shift",
      "tags": ["self", "teleport", "invisible"],
      "effectParams": {
        "teleport_range": 8.0,
        "invisible_duration": 3.0
      },
      "cooldown": 20.0,
      "triggerConditions": {
        "healthThreshold": 0.5,
        "maxUsesPerFight": 2
      }
    }
  ],

  "loot": [
    {"itemId": "shadow_essence", "chance": 0.6, "minQuantity": 1, "maxQuantity": 3},
    {"itemId": "void_crystal", "chance": 0.15, "minQuantity": 1, "maxQuantity": 1}
  ],

  "narrative": "A being of pure darkness, the Shadow Wraith phases between dimensions. It weakens its prey before delivering fatal strikes from the void."
}
```

**Step 2: Add to Catalog & Generate Icon**

```bash
python tools/unified_icon_generator.py
python assets/Vheer-automation.py
```

Icon at: `assets/generated_icons-3/enemies/shadow_wraith-3.png`

**Step 3: Add Spawn Locations**

(World generation system - file needs investigation)

**Step 4: Test**

1. Spawn enemy via debug or encounter in world
2. Verify abilities trigger at correct conditions
3. Check loot drops

---

## Batch Update System

### Current State

Currently, updates are numbered per-discipline:
- `items-smithing-2.JSON`
- `items-smithing-3.JSON`
- `recipes-smithing-3.JSON`

### Proposed: Update-N System

```
Updates/
├── Update-1/
│   ├── metadata.json
│   ├── skills.JSON
│   ├── items.JSON
│   ├── enemies.JSON
│   └── recipes.JSON
├── Update-2/
│   ├── metadata.json
│   ├── skills.JSON
│   └── items.JSON
└── Update-3/
    ├── metadata.json
    └── enemies.JSON
```

### Metadata Format

```json
{
  "updateId": 3,
  "version": "1.3.0",
  "date": "2025-12-25",
  "title": "Shadow Realm Update",
  "description": "Adds shadow-themed enemies, weapons, and skills",

  "changelog": [
    "Added 5 new shadow enemies",
    "Added Shadow Dagger weapon",
    "Added 3 shadow-themed skills",
    "Buffed Chain Harvest skill"
  ],

  "files": [
    "skills.JSON",
    "items.JSON",
    "enemies.JSON"
  ],

  "dependencies": ["Update-1", "Update-2"]
}
```

### Loader Logic (Proposed)

```python
def load_updates():
    """Load all updates in order"""
    updates_dir = Path("Updates")

    # Find all update directories
    update_dirs = sorted(updates_dir.glob("Update-*"))

    for update_dir in update_dirs:
        metadata_path = update_dir / "metadata.json"
        if not metadata_path.exists():
            continue

        with open(metadata_path) as f:
            metadata = json.load(f)

        # Check dependencies
        if not check_dependencies(metadata['dependencies']):
            print(f"⚠ Skipping {update_dir.name}: missing dependencies")
            continue

        # Load each file type
        for filename in metadata['files']:
            filepath = update_dir / filename
            if filepath.exists():
                load_definition_file(filepath)

        print(f"✓ Loaded {metadata['title']} ({update_dir.name})")
```

---

## Tag System Reference

### Quick Tag Guide

**Damage Types**:
- `physical`, `fire`, `ice`, `lightning`, `poison`
- `arcane`, `shadow`, `holy`, `chaos`

**Geometry**:
- `single` - Single target
- `chain` - Chain to nearby targets
- `cone` - Cone AOE from source
- `circle` - Circle AOE (set `origin: source` or `origin: target`)
- `beam` - Line/beam attack
- `pierce` - Penetrates multiple targets
- `splash` - Impact splash damage

**Status Effects**:
- **DoT**: `burn`, `bleed`, `poison_status`
- **CC**: `freeze`, `stun`, `root`, `slow`
- **Debuffs**: `weaken`, `vulnerable`
- **Buffs**: `haste`, `shield`, `regeneration`

**Special Mechanics**:
- `lifesteal`, `knockback`, `pull`, `reflect`, `thorns`
- `critical`, `execute`, `summon`, `teleport`

**Context Tags**:
- `self` - Targets caster
- `ally` / `friendly` - Targets allies
- `enemy` / `hostile` - Targets enemies
- `player` - Specifically targets player (for enemy abilities)

### Tag Combination Examples

**Fire sword**:
```json
"effect_tags": ["fire", "burn"],
"effect_params": {
  "burn_duration": 5.0,
  "burn_damage_per_second": 3.0
}
```

**Chain lightning spell**:
```json
"combatTags": ["lightning", "chain", "shock"],
"combatParams": {
  "baseDamage": 40,
  "chain_count": 3,
  "chain_range": 5.0,
  "shock_duration": 3.0
}
```

**AoE knockback**:
```json
"combatTags": ["physical", "circle", "knockback", "player"],
"combatParams": {
  "baseDamage": 50,
  "circle_radius": 5.0,
  "origin": "source",
  "knockback_distance": 3.0
}
```

---

## Troubleshooting

### Common Issues

**Issue**: Item doesn't load
- **Check**: JSON syntax valid?
- **Check**: Item has correct `category` field
- **Check**: Item ID unique?
- **Fix**: Run JSON validator

**Issue**: Icon doesn't display
- **Check**: PNG exists at expected path?
- **Check**: Path matches `{type}/{subfolder}/{item_id}.png`?
- **Fix**: Regenerate via Vheer automation

**Issue**: Skill doesn't execute
- **Check**: Mana cost affordable?
- **Check**: Cooldown expired?
- **Check**: Requirements met?
- **Fix**: Check skill_manager debug output

**Issue**: Enemy ability shows "0 targets affected"
- **Check**: Ability has correct context tag (`player` for targeting player)
- **Check**: Geometry params match JSON param names (e.g., `circle_radius` not `radius`)
- **Check**: Distance conditions allow trigger
- **Fix**: Add `player` tag, verify param names

**Issue**: Tags not working
- **Check**: Tags defined in `tag-definitions.JSON`
- **Check**: Effect executor supports tag
- **Check**: Parameters match expected names
- **Fix**: Check tag_debug output

### Debug Tools

**Enable tag debugging**:
```python
from core.tag_debug import get_tag_debugger
debugger = get_tag_debugger()
# Check console for tag execution logs
```

**Check database loading**:
```python
from data.databases.skill_db import SkillDatabase
db = SkillDatabase.get_instance()
print(f"Skills loaded: {len(db.skills)}")
print(f"Skill IDs: {list(db.skills.keys())}")
```

**Verify JSON syntax**:
```bash
python -m json.tool your_file.JSON
```

---

## Next Steps for Developers

### Immediate Tasks

1. **Test Tag System**
   - Create test JSONs with all tag combinations
   - Verify damage types work
   - Verify geometry patterns work
   - Verify status effects apply

2. **Implement Batch Update System**
   - Create `Updates/` directory structure
   - Implement metadata loader
   - Add dependency checking
   - Migrate existing content

3. **Automate PNG Workflow**
   - Link unified_icon_generator to game startup
   - Auto-detect new items
   - Auto-run Vheer automation
   - Version control for PNGs

4. **Complete Tag Coverage**
   - Implement knockback physics
   - Implement pull physics
   - Add visual effects for all status effects
   - Test all special mechanics

### Long-term Goals

1. **Hot-Reload System**
   - Detect JSON changes during runtime
   - Reload without restart
   - Preserve game state

2. **Content Validation**
   - Schema validation for all JSON types
   - Lint for common errors
   - Balance checking

3. **Mod Support**
   - Load external JSON mods
   - Mod priority system
   - Conflict resolution

4. **Editor Tools**
   - Visual JSON editor
   - Tag autocomplete
   - Live preview

---

## Conclusion

This system is designed for rapid content creation via JSON. The tag system allows complex behaviors without code changes. Following this guide, designers can add:

- New weapons with unique effects
- New skills with complex mechanics
- New enemies with sophisticated AI
- New recipes and crafting chains

All without touching Python code!

**Key Principle**: Define it in JSON, let the systems handle the rest.

---

**For Questions**: Check `docs/` folder or trace code from database loaders.
**For Updates**: This guide should be updated as new systems are added.

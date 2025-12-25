# Quick Reference: File Paths for Each System

**Last Updated**: 2025-12-25
**Purpose**: Fast lookup for developers - where to find/modify code for each game system

---

## JSON to Code Mapping

### SKILLS System

```
JSON Definition:
📄 Skills/skills-skills-1.JSON
📄 Skills/skills-base-effects-1.JSON

Loader/Database:
📂 data/databases/skill_db.py
   └─ SkillDatabase.load_from_file()

Data Models:
📂 data/models/skills.py
   └─ SkillDefinition, SkillEffect, SkillCost

Manager:
📂 entities/components/skill_manager.py
   └─ SkillManager.use_skill()
   └─ SkillManager._apply_skill_effect()

Execution:
📂 core/effect_executor.py
   └─ execute_effect()

Combat Integration:
📂 Combat/combat_manager.py
   └─ execute_instant_player_aoe()
   └─ player_attack_enemy_with_tags()

Icon Path:
📁 assets/generated_icons-3/skills/{skill_id}-3.png
```

---

### ITEMS/EQUIPMENT System

```
JSON Definitions:
📄 items.JSON/items-smithing-2.JSON (weapons, armor, tools)
📄 items.JSON/items-materials-1.JSON (ores, wood, stone)
📄 items.JSON/items-alchemy-1.JSON (potions, bombs)
📄 items.JSON/items-engineering-1.JSON (turrets, devices)
📄 items.JSON/items-refining-1.JSON (ingots)
📄 items.JSON/items-tools-1.JSON (pickaxes, axes)

Loaders/Databases:
📂 data/databases/equipment_db.py
   └─ EquipmentDatabase.load_from_file()
   └─ Only loads category='equipment'

📂 data/databases/material_db.py
   └─ MaterialDatabase.load_from_file()
   └─ Loads consumables, materials, devices

Data Models:
📂 data/models/equipment.py
   └─ EquipmentItem

Inventory System:
📂 entities/components/inventory.py
   └─ Inventory.add_item()

Equipment Manager:
📂 entities/components/equipment_manager.py
   └─ EquipmentManager.equip()
   └─ EquipmentManager.calculate_stats()

Combat Integration:
📂 Combat/combat_manager.py
   └─ get_weapon_damage()
   └─ Reads effect_tags from equipped weapon

Icon Paths:
📁 assets/generated_icons-3/items/weapons/{item_id}-3.png
📁 assets/generated_icons-3/items/armor/{item_id}-3.png
📁 assets/generated_icons-3/items/tools/{item_id}-3.png
📁 assets/generated_icons-3/items/consumables/{item_id}-3.png
📁 assets/generated_icons-3/items/materials/{item_id}-3.png
```

---

### ENEMIES/HOSTILES System

```
JSON Definition:
📄 Definitions.JSON/hostiles-1.JSON

Loader/Database:
📂 Combat/enemy.py
   └─ EnemyDefinitionDatabase.load_from_file()
   └─ Enemy.__init__()

Enemy AI:
📂 Combat/enemy.py
   └─ Enemy.update_ai()
   └─ Enemy.can_use_special_ability()
   └─ Enemy.use_special_ability()
   └─ Enemy.attack_with_tags()

Combat Manager:
📂 Combat/combat_manager.py
   └─ combat_manager.update()
   └─ _enemy_attack_player()

Effect Execution:
📂 core/effect_executor.py
   └─ execute_effect()

Status Effects:
📂 entities/status_effect.py
   └─ BurnEffect, BleedEffect, PoisonEffect, etc.

📂 entities/status_manager.py
   └─ StatusEffectManager.apply_status()

Icon Path:
📁 assets/generated_icons-3/enemies/{enemy_id}-3.png
```

---

### RECIPES/CRAFTING System

```
JSON Definitions:
📄 recipes.JSON/recipes-smithing-3.JSON
📄 recipes.JSON/recipes-alchemy-1.JSON
📄 recipes.JSON/recipes-refining-1.JSON
📄 recipes.JSON/recipes-engineering-1.JSON
📄 recipes.JSON/recipes-enchanting-1.JSON
📄 recipes.JSON/recipes-adornments-1.json

Crafting Subdisciplines:
📂 Crafting-subdisciplines/smithing.py
📂 Crafting-subdisciplines/alchemy.py
📂 Crafting-subdisciplines/refining.py
📂 Crafting-subdisciplines/engineering.py
📂 Crafting-subdisciplines/enchanting.py

Shared Systems:
📂 Crafting-subdisciplines/rarity_utils.py
   └─ Rarity calculation

📂 Crafting-subdisciplines/crafting_simulator.py
   └─ Minigame simulation

Station Definitions:
📄 Definitions.JSON/crafting-stations-1.JSON

Crafting UI:
📂 rendering/ui_manager.py (needs investigation)
```

---

### RESOURCE NODES System

```
JSON Definition:
📄 Definitions.JSON/resource-node-1.JSON

Resource System:
📂 systems/natural_resource.py
   └─ NaturalResource.__init__()
   └─ take_damage()
   └─ get_loot()
   └─ update() (respawn logic)

World Generation:
(Needs investigation - likely in world/ or systems/)

Gathering Integration:
(Needs investigation - likely interaction with tools)

Icon Path:
📁 assets/generated_icons-3/resources/{node_id}-3.png
```

---

### PLACEMENT/DEVICE System

```
JSON Definitions:
📄 placements.JSON/placements-smithing-1.JSON
📄 placements.JSON/placements-alchemy-1.JSON
📄 placements.JSON/placements-refining-1.JSON
📄 placements.JSON/placements-engineering-1.JSON
📄 placements.JSON/placements-adornments-1.JSON

Placement System:
(Needs investigation - turrets, crafting stations)
```

---

## TAG SYSTEM

### Core Tag Files

```
Tag Definitions:
📄 Definitions.JSON/tag-definitions.JSON
   └─ Defines all tags, categories, behaviors

Tag Parser:
📂 core/tag_parser.py
   └─ TagParser.parse()
   └─ Converts tags → EffectConfig

Tag Registry:
📂 core/tag_registry.py
   └─ TagRegistry.get_definition()
   └─ In-memory tag database

Effect Executor:
📂 core/effect_executor.py
   └─ EffectExecutor.execute_effect()
   └─ Applies damage, geometry, status effects

Geometry System:
📂 core/geometry/target_finder.py
   └─ TargetFinder.find_targets()
   └─ find_circle_targets()
   └─ find_cone_targets()
   └─ find_beam_targets()
   └─ find_chain_targets()

📂 core/geometry/math_utils.py
   └─ distance(), is_in_cone(), is_in_circle()

Tag Debugger:
📂 core/tag_debug.py
   └─ get_tag_debugger()
   └─ Logs tag execution for debugging
```

---

## PNG/ASSET GENERATION

### Asset Pipeline

```
Catalog Generator:
📂 tools/unified_icon_generator.py
   └─ Scans all JSONs
   └─ Generates catalog

Catalog Output:
📄 Scaled JSON Development/ITEM_CATALOG_FOR_ICONS.md

Vheer Automation:
📂 assets/Vheer-automation.py
   └─ Reads catalog
   └─ Generates PNGs via Selenium

Output Directories:
📁 assets/generated_icons-2/ (version 2 prompts)
📁 assets/generated_icons-3/ (version 3 prompts)

Each version contains:
📁 items/
   ├─ weapons/
   ├─ armor/
   ├─ tools/
   ├─ accessories/
   ├─ consumables/
   ├─ materials/
   └─ devices/
📁 enemies/
📁 resources/
📁 skills/
📁 titles/
```

---

## GAME ENGINE INTEGRATION

### Core Engine

```
Main Game Loop:
📂 core/game_engine.py
   └─ GameEngine.__init__()
   └─ GameEngine.run()
   └─ Handle input
   └─ Update systems
   └─ Render

Database Initialization:
📂 data/databases/__init__.py
   └─ Load all databases on startup

Character:
📂 entities/character.py
   └─ Character.__init__()
   └─ take_damage()
   └─ Integrates all managers

Combat Manager:
📂 Combat/combat_manager.py
   └─ update() - Updates all enemies
   └─ player_attack_enemy_with_tags()
   └─ execute_instant_player_aoe()
```

---

## CONFIGURATION FILES

### Translation Tables

```
Value Translation:
📄 Definitions.JSON/value-translation-table-1.JSON
   └─ Maps text values to numbers
   └─ e.g., "moderate" → 60 mana

Skills Translation:
📄 Definitions.JSON/skills-translation-table.JSON
   └─ Magnitude values per effect type
   └─ Rarity multipliers

Stats Calculations:
📄 Definitions.JSON/stats-calculations.JSON
   └─ Stat formulas
   └─ Level scaling

Combat Config:
📄 Definitions.JSON/combat-config.JSON
   └─ Combat constants
   └─ Damage formulas
```

---

## RENDERING SYSTEM

```
Main Renderer:
📂 rendering/renderer.py
   └─ Render game world
   └─ Render entities
   └─ Load sprites/icons

Image Cache:
📂 rendering/image_cache.py
   └─ Cache loaded images
   └─ Prevent duplicate loads

UI Manager:
📂 rendering/ui_manager.py
   └─ Inventory UI
   └─ Equipment UI
   └─ Crafting UI
```

---

## WORLD/LEVEL SYSTEM

```
(Needs investigation)

Likely files:
📂 systems/world_generator.py
📂 systems/chunk_manager.py
📂 Definitions.JSON/Chunk-templates-1.JSON
```

---

## KEY LOOKUP PATTERNS

### When you need to...

**Add a new skill:**
1. Edit: `Skills/skills-skills-1.JSON`
2. Run: `tools/unified_icon_generator.py`
3. Run: `assets/Vheer-automation.py`
4. Check: `data/databases/skill_db.py` (loader)
5. Test: `entities/components/skill_manager.py` (execution)

**Add a new weapon:**
1. Edit: `items.JSON/items-smithing-2.JSON`
2. Run: `tools/unified_icon_generator.py`
3. Run: `assets/Vheer-automation.py`
4. Check: `data/databases/equipment_db.py` (loader)
5. Test: `entities/components/equipment_manager.py` (equipping)

**Add a new enemy:**
1. Edit: `Definitions.JSON/hostiles-1.JSON`
2. Run: `tools/unified_icon_generator.py`
3. Run: `assets/Vheer-automation.py`
4. Check: `Combat/enemy.py` (loader + AI)
5. Test: `Combat/combat_manager.py` (combat integration)

**Add a new tag:**
1. Edit: `Definitions.JSON/tag-definitions.JSON`
2. Check: `core/tag_registry.py` (auto-loaded)
3. Implement: `core/effect_executor.py` (if new behavior)
4. Test: `core/tag_debug.py` (debug output)

**Debug tag execution:**
1. Check: Console output from `core/tag_debug.py`
2. Enable: `from core.tag_debug import get_tag_debugger`
3. Check: `core/effect_executor.py` (execution logs)

**Update PNG assets:**
1. Update: `Scaled JSON Development/ITEM_CATALOG_FOR_ICONS.md`
2. Run: `assets/Vheer-automation.py`
3. Choose: Full catalog or test mode
4. Output: `assets/generated_icons-3/`

---

## COMMON FILE EXTENSIONS

- `.JSON` - Game data definitions
- `.json` - Same (lowercase variant)
- `.py` - Python code
- `.md` - Markdown documentation
- `.png` - Image assets

---

## DIRECTORY STRUCTURE OVERVIEW

```
Game-1-modular/
├── assets/                    # PNG generation
│   ├── Vheer-automation.py
│   └── generated_icons-3/
├── Combat/                    # Combat systems
│   ├── combat_manager.py
│   └── enemy.py
├── core/                      # Core systems
│   ├── game_engine.py
│   ├── tag_parser.py
│   ├── effect_executor.py
│   └── geometry/
├── Crafting-subdisciplines/   # Crafting systems
├── data/
│   ├── databases/             # JSON loaders
│   └── models/                # Data structures
├── Definitions.JSON/          # Core definitions
│   ├── hostiles-1.JSON
│   ├── tag-definitions.JSON
│   └── ...
├── entities/
│   ├── character.py
│   └── components/            # Character subsystems
├── items.JSON/                # Item definitions
├── recipes.JSON/              # Recipe definitions
├── placements.JSON/           # Placement definitions
├── Skills/                    # Skill definitions
├── systems/                   # Game systems
│   └── natural_resource.py
├── rendering/                 # Rendering systems
└── tools/                     # Dev tools
    └── unified_icon_generator.py
```

---

This quick reference should help you find any file you need without hunting through the codebase!

# Game-1 JSON File Paths Reference

**Last Updated**: 2026-01-09
**Purpose**: Comprehensive reference of all JSON files actively used by Game-1

This document lists the actual file paths to JSON files loaded by the game at runtime. These paths are relative to the `Game-1-modular/` directory.

---

## Materials

Materials are loaded by `MaterialDatabase` in `core/game_engine.py`.

| File Path | Purpose | Loaded By |
|-----------|---------|-----------|
| `items.JSON/items-materials-1.JSON` | Raw materials (ores, wood, stone, etc.) | game_engine.py:98 |
| `items.JSON/items-refining-1.JSON` | Refined materials (ingots, planks) | game_engine.py:100 |
| `items.JSON/items-alchemy-1.JSON` | Alchemy consumables and potions | game_engine.py:103 |
| `items.JSON/items-engineering-1.JSON` | Engineering devices (turrets, traps) | game_engine.py:106 |
| `items.JSON/items-testing-tags.JSON` | Testing items with tag examples | game_engine.py:109 |
| `items.JSON/items-smithing-2.JSON` | Crafting stations | game_engine.py:112 |

---

## Equipment

Equipment is loaded by `EquipmentDatabase` in `core/game_engine.py`.

| File Path | Purpose | Loaded By |
|-----------|---------|-----------|
| `items.JSON/items-engineering-1.JSON` | Engineering equipment | game_engine.py:123 |
| `items.JSON/items-smithing-2.JSON` | Smithing equipment and stations | game_engine.py:124 |
| `items.JSON/items-tools-1.JSON` | Tools (pickaxe, axe, hammer) | game_engine.py:125 |
| `items.JSON/items-alchemy-1.JSON` | Alchemy equipment | game_engine.py:126 |
| `items.JSON/items-testing-tags.JSON` | Testing equipment with tags | game_engine.py:128 |

---

## Crafting Recipes

Recipes are loaded by `RecipeDatabase` in `data/databases/recipe_db.py:28-31`.

| File Path | Discipline | Loaded By |
|-----------|------------|-----------|
| `recipes.JSON/recipes-smithing-3.json` | Smithing | recipe_db.py:28 |
| `recipes.JSON/recipes-alchemy-1.JSON` | Alchemy | recipe_db.py:28 |
| `recipes.JSON/recipes-refining-1.JSON` | Refining | recipe_db.py:29 |
| `recipes.JSON/recipes-engineering-1.JSON` | Engineering | recipe_db.py:30 |
| `recipes.JSON/recipes-adornments-1.json` | Enchanting/Adornments | recipe_db.py:31 |

**Note**: `recipes-adornments-1.json` contains enchanting recipes with `enchantmentId` instead of `outputId`.

---

## Placement Data (Interactive Crafting)

Placements are loaded by `PlacementDatabase` in `data/databases/placement_db.py:29-41`.

| File Path | Discipline | Loaded By |
|-----------|------------|-----------|
| `placements.JSON/placements-smithing-1.JSON` | Smithing grid layouts | placement_db.py:29 |
| `placements.JSON/placements-refining-1.JSON` | Refining hub-and-spoke layouts | placement_db.py:32 |
| `placements.JSON/placements-alchemy-1.JSON` | Alchemy sequential slots | placement_db.py:35 |
| `placements.JSON/placements-engineering-1.JSON` | Engineering slot types | placement_db.py:38 |
| `placements.JSON/placements-adornments-1.JSON` | Enchanting geometric patterns | placement_db.py:41 |

---

## Character Progression

Progression data is loaded in `core/game_engine.py:130-132`.

| File Path | Purpose | Loaded By |
|-----------|---------|-----------|
| `progression/titles-1.JSON` | Achievement titles (40+ titles) | game_engine.py:130 |
| `progression/classes-1.JSON` | Starting classes (6 classes with tags) | game_engine.py:131 |
| `Skills/skills-skills-1.JSON` | Player skills (100+ skills) | game_engine.py:132 |

---

## NPCs and Quests

NPCs and quests are loaded by `NPCDatabase` in `data/databases/npc_db.py:32-33, 80-81`.

| File Path | Purpose | Loaded By |
|-----------|---------|-----------|
| `progression/npcs-enhanced.JSON` | Enhanced NPC definitions | npc_db.py:32 |
| `progression/npcs-1.JSON` | Base NPC definitions | npc_db.py:33 |
| `progression/quests-enhanced.JSON` | Enhanced quest definitions | npc_db.py:80 |
| `progression/quests-1.JSON` | Base quest definitions | npc_db.py:81 |

**Loading Pattern**: Enhanced files are loaded first, then base files as fallback.

---

## System Definitions

System configuration files loaded by various databases.

| File Path | Purpose | Loaded By |
|-----------|---------|-----------|
| `Definitions.JSON/skills-translation-table.JSON` | Skill effect translations | translation_db.py:27 |
| `Skills/skills-base-effects-1.JSON` | Base skill effect definitions | skill_manager.py:27 |
| `Definitions.JSON/crafting-stations-1.JSON` | Crafting station definitions | game_engine.py:115 |
| `Definitions.JSON/resource-node-1.JSON` | Resource node definitions | (world generation) |
| `Definitions.JSON/tag-definitions.JSON` | Tag system definitions | (tag system) |
| `Definitions.JSON/stats-calculations.JSON` | Stat calculation formulas | (character stats) |
| `Definitions.JSON/combat-config.JSON` | Combat system configuration | (combat manager) |
| `Definitions.JSON/value-translation-table-1.JSON` | Value translation mappings | (various systems) |

---

## Crafting Modifiers

| File Path | Purpose | Loaded By |
|-----------|---------|-----------|
| `Crafting-subdisciplines/rarity-modifiers.JSON` | Rarity tier stat modifiers | (crafting system) |

---

## Save Files

Save files are managed by the save system.

| File Path | Purpose |
|-----------|---------|
| `saves/default_save.json` | Default save state for new games |
| `saves/autosave.json` | Automatic save slot |

---

## Testing and Development

These files are used for testing and development only.

| File Path | Purpose |
|-----------|---------|
| `items.JSON/items-testing-integration.JSON` | Integration testing items |
| `items.JSON/items-testing-tags.JSON` | Tag system testing items |
| `recipes.JSON/recipes-tag-tests.JSON` | Recipe tag testing |
| `Skills/skills-testing-integration.JSON` | Skill testing definitions |
| `Definitions.JSON/hostiles-testing-integration.JSON` | Enemy testing definitions |
| `Update-1/hostiles-testing-integration.JSON` | Update 1 testing enemies |
| `Update-1/items-testing-integration.JSON` | Update 1 testing items |
| `Update-1/recipes-smithing-testing.JSON` | Smithing recipe testing |
| `Update-1/skills-testing-integration.JSON` | Update 1 skill testing |

---

## Asset Support Files

JSON files supporting asset systems.

| File Path | Purpose |
|-----------|---------|
| `assets/deferred_icon_decisions.json` | Icon generation decisions |
| `assets/icon_remap_registry.json` | Icon path remapping |

---

## World Generation Templates

| File Path | Purpose |
|-----------|---------|
| `Definitions.JSON/Chunk-templates-1.JSON` | World chunk generation templates |
| `Definitions.JSON/templates-crafting-1.JSON` | Crafting-related templates |

---

## Notes

### File Naming Conventions

- **Uppercase `.JSON`**: Most game content files (legacy convention)
- **Lowercase `.json`**: Some newer files (recipes-smithing-3.json, saves)
- **Version Numbers**: `-1`, `-2`, `-3` indicate iterations (use highest number)
- **Enhanced Files**: `-enhanced` suffix indicates expanded versions

### Loading Priority

When multiple versions exist:
1. Enhanced versions loaded first (e.g., `npcs-enhanced.JSON` before `npcs-1.JSON`)
2. Higher version numbers take precedence (e.g., `recipes-smithing-3.json` is current)
3. Testing files only loaded in development mode

### Adding New JSON Files

To add new content:
1. Place file in appropriate directory (`items.JSON/`, `recipes.JSON/`, etc.)
2. Update the corresponding database loader in `data/databases/`
3. Test loading with the game's database initialization
4. Add entry to this documentation

---

## Quick Reference: Critical Files

These files are essential for the game to run:

**Materials & Equipment**:
- `items.JSON/items-materials-1.JSON`
- `items.JSON/items-refining-1.JSON`
- `items.JSON/items-smithing-2.JSON`
- `items.JSON/items-tools-1.JSON`

**Recipes**:
- `recipes.JSON/recipes-smithing-3.json`
- `recipes.JSON/recipes-alchemy-1.JSON`
- `recipes.JSON/recipes-refining-1.JSON`
- `recipes.JSON/recipes-engineering-1.JSON`
- `recipes.JSON/recipes-adornments-1.json`

**Placements**:
- All 5 files in `placements.JSON/`

**Progression**:
- `progression/titles-1.JSON`
- `progression/classes-1.JSON`
- `Skills/skills-skills-1.JSON`

**System**:
- `Definitions.JSON/skills-translation-table.JSON`
- `saves/default_save.json`

---

## Related Documentation

- **JSON Schema Reference**: See `Scaled JSON Development/json_templates/` for templates
- **Database Documentation**: See `docs/MODULE_REFERENCE.md` for database APIs
- **Tag System**: See `docs/tag-system/TAG-GUIDE.md` for tag definitions

---

**Maintenance**: Update this file when adding/removing JSON files from the game's loading routines.

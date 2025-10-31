# Claude.md - Game-1 Developer Guide

**Quick Reference for AI Assistants & Developers**

## Project Summary

**Game-1** is a crafting-focused RPG built with Python/Pygame featuring:
- 100×100 tile world with procedural chunk generation
- 5 crafting disciplines (Smithing, Alchemy, Refining, Engineering, Enchanting)
- Character progression (30 levels, 6 stats, titles, classes)
- Equipment system with enchantments
- Resource gathering with tool requirements

**Current State**: Core systems functional, advanced features designed but not implemented
**Main File**: `main.py` (3,559 lines)
**Design Doc**: `Development-logs/Most-Recent-Game-Mechanics-v5` (4,432 lines)

---

## Critical: What's Implemented vs Designed

### ✅ Fully Working
- World generation & rendering
- Resource gathering (mining, forestry)
- Inventory system (30 slots, drag-and-drop)
- Equipment system (weapons, armor, tools)
- Crafting system (100+ recipes across 5 disciplines)
- Character progression (levels, stats, exp)
- Class system (6 classes with bonuses)
- Title system (novice tier only)
- Enchantment application (effects don't apply stats yet)

### ⚠️ Partially Working
- **Title System**: Only novice titles grant bonuses (40+ higher tier titles defined but don't work)
- **Enchantments**: Apply to items but don't modify stats/damage yet
- **Material Database**: Some ID inconsistencies between files

### ❌ Designed But NOT Implemented
- **Skills**: 30+ skills fully defined in JSON, zero mechanics coded
- **Mini-Games**: Extensively designed (smithing timing, alchemy sequences) but crafting is instant
- **Combat**: 40+ enemies defined, none spawn or fight
- **Quests**: NPCs and quests in design doc only
- **Placement UI**: 170KB of grid layout data exists but crafting UI doesn't use it

**Important**: Don't assume features from the design doc exist in code. Check implementation first.

---

## Architecture Overview

### Main Systems (main.py structure)

```
Lines 16-82:     Configuration (Config class)
Lines 101-1,411: Database Systems (singletons)
Lines 303-605:   Equipment System
Lines 1,501-1,863: Character Progression
Lines 1,611-1,789: Inventory & Items
Lines 964-1,449: World Systems
Lines 2,140-2,972: Rendering & UI
Lines 2,973-end: Game Engine (main loop)
```

### Key Classes

**Database Singletons** (load on startup):
- `MaterialDatabase` - 60+ materials from JSON
- `EquipmentDatabase` - Weapons, armor, tools
- `RecipeDatabase` - 100+ recipes across 5 disciplines
- `TitleDatabase` - 40+ achievement titles
- `ClassDatabase` - 6 starting classes
- `SkillDatabase` - Skeleton only, doesn't load data

**Core Systems**:
- `Character` - Player entity with stats, inventory, equipment
- `Inventory` - 30-slot item storage with ItemStack objects
- `EquipmentManager` - Equip/unequip, stat calculations
- `WorldSystem` - 100×100 tiles, chunk-based generation
- `Renderer` - All drawing logic
- `GameEngine` - Main loop, event handling, UI

### Design Patterns

1. **Singleton Databases**: All data loaded once at startup via `get_instance()`
2. **Dataclasses**: Heavy use of `@dataclass` for data structures
3. **Enums**: `TileType`, `StationType`, `ResourceType`
4. **JSON-Driven Content**: All items, recipes, materials defined in JSON

---

## File Organization

```
Game-1/
├── main.py                          # Main game (3,559 lines)
├── Development-logs/                # Design documentation
│   └── Most-Recent-Game-Mechanics-v5  # Master design spec
├── Definitions.JSON/                # World & system definitions
│   ├── Chunk-templates-1.JSON        # 9 chunk biome types
│   ├── Resource-node-1.JSON          # Resource definitions
│   ├── Hostiles-1.JSON               # Enemy definitions (unused)
│   ├── Skills-translation-table.JSON # Skill value lookups
│   └── Templates-crafting-1.JSON     # Item templates (unused)
├── items.JSON/                      # Item definitions
│   ├── items-materials-1.JSON        # 60 raw materials ★
│   ├── items-smithing-1.JSON         # Weapons, armor
│   ├── items-smithing-2.JSON         # More equipment
│   ├── items-alchemy-1.JSON          # Potions, consumables
│   ├── items-refining-1.JSON         # Ingots, planks
│   └── items-tools-1.JSON            # Placeable tools
├── recipes.JSON/                    # Crafting recipes
│   ├── recipes-smithing-3.json       # ★ Most current smithing
│   ├── recipes-smithing-1/2.json     # Older versions
│   ├── recipes-alchemy-1.JSON        # Alchemy recipes
│   ├── recipes-refining-1.JSON       # Material processing
│   ├── recipes-engineering-1.JSON    # Turrets, devices
│   └── recipes-adornments-1.json     # Enchantments
├── placements.JSON/                 # Grid layouts (unused)
│   └── [5 files, 170KB, not integrated]
├── progression/                     # Character progression
│   ├── classes-1.JSON                # 6 classes ★
│   └── titles-1.JSON                 # 40+ titles ★
└── Skills/                          # Skill definitions (unused)
    ├── skills-skills-1.JSON          # 30+ skills defined
    └── skills-base-effects-1.JSON    # Effect types
```

**★ = Primary/most current files**

---

## Key Design Principles

### 1. Hardcode vs JSON Philosophy
- **Hardcode**: System mechanics (HOW things work)
- **JSON**: All content, values, balance numbers

### 2. Stats System (6 Core Stats)
All stats start at 0, gain 1 point per level (max 30):
- **STR**: +5% mining/melee damage, +10 inventory slots
- **DEF**: +2% damage reduction, +3% armor effectiveness
- **VIT**: +15 max HP, +1% health regen
- **LCK**: +2% crit chance, +2% resource quality, +3% rare drops
- **AGI**: +5% forestry damage, +3% attack speed
- **INT**: +2% alchemy time, +20 mana, +5% elemental damage

### 3. Multiplicative Scaling
`Final Value = Base × (1 + Stat Bonuses) × (1 + Title Bonuses) × (1 + Equipment Bonuses)`

### 4. EXP Sources
- **Gathering**: 10-640 EXP based on tier (T1=10, T2=40, T3=160, T4=640)
- **Crafting**: Only from mini-games (NOT instant craft) - 50-3,200 EXP
- **Combat**: 100-6,400 EXP per enemy (NOT IMPLEMENTED)

### 5. No Breaking
Durability declines but never destroys items:
- 100% durability = 100% effectiveness
- 0% durability = 50% effectiveness forever

### 6. Tier System
- **T1**: Common materials (oak, iron, limestone)
- **T2**: Uncommon (ash, steel, marble)
- **T3**: Rare (ironwood, mithril, obsidian)
- **T4**: Legendary (voidsteel, dragonsteel, voidstone)

Higher tiers = **LESS ABUNDANT** but **MORE VALUABLE**

---

## Common Development Tasks

### Adding a New Recipe

1. Choose discipline and locate file:
   - Smithing: `recipes.JSON/recipes-smithing-3.json`
   - Alchemy: `recipes.JSON/recipes-alchemy-1.JSON`
   - etc.

2. Add recipe object:
```json
{
  "recipeId": "smithing_iron_sword_001",
  "outputId": "iron_sword",
  "outputQty": 1,
  "stationTier": 1,
  "inputs": [
    {"materialId": "iron_ingot", "qty": 3},
    {"materialId": "oak_plank", "qty": 1}
  ],
  "miniGame": {
    "type": "smithing",
    "difficulty": "easy"
  }
}
```

3. Ensure `outputId` matches an item in `items.JSON/items-smithing-*.JSON`

4. Game auto-loads on restart (no code changes needed)

### Adding a New Material

1. Add to `items.JSON/items-materials-1.JSON`:
```json
{
  "materialId": "mythril_ore",
  "name": "Mythril Ore",
  "tier": 3,
  "category": "ore",
  "rarity": "rare",
  "description": "Shimmering blue ore...",
  "max_stack": 99
}
```

2. Add resource node to `Definitions.JSON/Resource-node-1.JSON`:
```json
{
  "resourceId": "mythril_vein_small",
  "materialId": "mythril_ore",
  "category": "ore",
  "tier": 3,
  "gatherTool": "pickaxe",
  "baseHP": [150, 200],
  "baseYield": [3, 6]
}
```

3. MaterialDatabase loads on startup

### Adding Equipment

1. Add to appropriate file (`items-smithing-2.JSON` for weapons/armor):
```json
{
  "itemId": "mythril_sword",
  "name": "Mythril Blade",
  "category": "equipment",
  "type": "weapon",
  "subtype": "sword",
  "tier": 3,
  "rarity": "rare",
  "slot": "mainHand",
  "damage": [45, 60],
  "attackSpeed": 1.4,
  "durability": 1000,
  "requirements": {"level": 15, "STR": 10}
}
```

2. Create recipe in `recipes-smithing-3.json`

3. EquipmentDatabase loads on startup

### Modifying Stats/Balance

**Character Leveling** (main.py:1501):
```python
class LevelingSystem:
    EXP_CURVE = [200, 350, 550, 800, ...]  # Modify here
```

**Stat Bonuses** (main.py:1851-1950, Character class methods):
```python
def get_mining_damage_multiplier(self):
    return 1.0 + (self.stats.strength * 0.05)  # 5% per STR point
```

**Tool Effectiveness** (main.py:1795):
```python
class Tool:
    def get_effectiveness(self) -> float:
        durability_factor = max(0.5, self.durability / self.max_durability)
        return self.tier * durability_factor
```

---

## Database Loading Patterns

All databases follow this pattern:

```python
class SomeDatabase:
    _instance = None

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = SomeDatabase()
        return cls._instance

    def load_from_file(self, filepath: str):
        # Load JSON, populate self.items dict
        pass
```

**Usage**:
```python
mat_db = MaterialDatabase.get_instance()
material = mat_db.materials.get("iron_ingot")
```

**Initialization** (main.py:3530-3570):
```python
def main():
    mat_db = MaterialDatabase.get_instance()
    mat_db.load_from_file("items.JSON/items-materials-1.JSON")

    eq_db = EquipmentDatabase.get_instance()
    eq_db.load_from_files([
        "items.JSON/items-smithing-1.JSON",
        "items.JSON/items-smithing-2.JSON",
        # etc
    ])
```

---

## Known Issues & Limitations

### 1. Skill System Not Functional
- `SkillDatabase` exists but doesn't load files
- `SkillManager` has no logic
- Skills defined in `Skills/skills-skills-1.JSON` are unused
- No mana/cooldown system implemented

**To Implement**:
- Parse skill JSON files
- Add mana pool to Character
- Implement skill activation mechanics
- Add cooldown tracking

### 2. Enchantment Effects Don't Apply
- Enchantments can be added to equipment
- They're stored in `EquipmentItem.enchantments[]`
- But `EquipmentManager.calculate_stat_bonuses()` doesn't read them

**Fix**: Update stat calculation methods to loop through enchantments

### 3. Higher Tier Titles Don't Grant Bonuses
- Only novice titles work (main.py:1711)
- Apprentice/Journeyman/Expert/Master defined but ignored

**Fix**: Update `TitleSystem.get_activity_bonus()` to handle all tiers

### 4. Mini-Games Not Implemented
- Recipes define mini-game types
- Crafting is instant regardless
- No timing/sequence/puzzle mechanics

**To Implement**: Full mini-game system (major undertaking)

### 5. Placement Data Unused
- 170KB of grid layout definitions exist
- Crafting UI is simple recipe list
- No visual grid placement

**Decision Needed**: Implement visual crafting grids or remove files?

### 6. ID Field Inconsistencies
- Some files use `itemId`, others `materialId`
- Causes loading issues occasionally
- Needs standardization pass

---

## Debugging Tips

### Check What's Loaded
```python
# In main.py, after database loading:
mat_db = MaterialDatabase.get_instance()
print(f"Loaded {len(mat_db.materials)} materials")

eq_db = EquipmentDatabase.get_instance()
print(f"Loaded {len(eq_db.equipment)} equipment items")

recipe_db = RecipeDatabase.get_instance()
print(f"Loaded {len(recipe_db.recipes)} recipes")
```

### Enable Debug Mode
Press **F1** in-game to toggle debug mode:
- Infinite resources (nodes don't deplete)
- Debug info overlays

### Check Item in Inventory
```python
# In Renderer.render_tooltip() or similar:
if item_stack.equipment_data:
    print(f"Equipment: {item_stack.equipment_data.name}")
    print(f"Damage: {item_stack.equipment_data.damage}")
    print(f"Enchantments: {item_stack.equipment_data.enchantments}")
```

### Verify Recipe Loading
```python
recipe_db = RecipeDatabase.get_instance()
for recipe_id, recipe in recipe_db.recipes.items():
    print(f"{recipe_id}: {recipe.station_type} T{recipe.station_tier}")
```

---

## Important Code Locations

### Character Stats & Bonuses
- **Stat Storage**: `Character.stats` (CharacterStats dataclass, main.py:1501)
- **Mining Bonus**: `Character.get_mining_damage_multiplier()` (main.py:1900)
- **Forestry Bonus**: `Character.get_forestry_damage_multiplier()` (main.py:1905)
- **Luck Effects**: `Character.get_luck_multiplier()` (main.py:1920)

### Equipment System
- **Equipment Data**: `EquipmentItem` class (main.py:303)
- **Equip Logic**: `EquipmentManager.equip_item()` (main.py:540)
- **Stat Calculation**: `EquipmentManager.calculate_stat_bonuses()` (main.py:590)

### Crafting System
- **Recipe Storage**: `Recipe` dataclass (main.py:606)
- **Crafting Logic**: `GameEngine.handle_craft_recipe()` (main.py:3280)
- **Material Consumption**: `Inventory.try_consume_materials()` (main.py:1750)

### World Generation
- **World Creation**: `WorldSystem.__init__()` (main.py:1200)
- **Chunk Generation**: `WorldSystem._generate_chunk()` (main.py:1250)
- **Resource Spawning**: `WorldSystem._spawn_resources()` (main.py:1320)

### Rendering
- **World Drawing**: `Renderer.render_world()` (main.py:2200)
- **UI Drawing**: `Renderer.render_ui()` (main.py:2600)
- **Inventory Display**: `Renderer.render_inventory()` (main.py:2700)

---

## Performance Notes

- **World Size**: 100×100 = 10,000 tiles, chunked into 16×16 (39 chunks)
- **JSON Loading**: ~35 files loaded at startup (~500ms on modern hardware)
- **Rendering**: Canvas-based, 60 FPS target
- **Inventory**: 30 slots max, no performance concerns

---

## Future Architecture Considerations

### LLM Integration Points (Designed, Not Implemented)
The design doc extensively mentions LLM features:
- **Procedural Title Generation**: Based on player behavior patterns
- **Skill Evolution**: Custom skill variants for player specializations
- **Dynamic Content**: Recipes, materials, quests generated on-demand

**Current State**: Zero LLM integration, all content is static JSON

**If Implementing**: Consider API costs, response times, content validation

### Save/Load System (Not Implemented)
No persistence currently. Design doc mentions:
- Auto-save every 5 minutes
- Save on exit
- Save before class switch
- JSON or binary format

**Priority**: High (game is unplayable without saves)

### 3D Rendering (Designed For)
Architecture is "3D-ready":
- `Position` uses x, y, z (z currently always 0)
- Distance calculations support 3D
- Renderer abstraction allows drop-in WebGL replacement

**Current**: Pure 2D with Pygame

---

## Quick Command Reference

### Run Game
```bash
cd Game-1
python main.py
```

### Check JSON Validity
```bash
python -m json.tool recipes.JSON/recipes-smithing-3.json > /dev/null
```

### Count Recipe
```bash
cat recipes.JSON/recipes-smithing-3.json | python -c "import sys, json; data=json.load(sys.stdin); print(len(data.get('recipes', [])))"
```

---

## When Working on This Project

### DO:
✅ Check if features are implemented before assuming they work
✅ Reference Game Mechanics v5 for design intent
✅ Test JSON changes by restarting the game
✅ Use singleton pattern for databases
✅ Follow existing naming conventions (`snake_case` for IDs)

### DON'T:
❌ Assume skills/mini-games/combat work (they don't)
❌ Modify hardcoded mechanics without understanding design principles
❌ Create new JSON schemas without checking existing patterns
❌ Hardcode values that should be in JSON

---

## Questions to Ask the Developer

Before implementing major features:
1. **Skills**: Implement skill system or focus elsewhere?
2. **Mini-Games**: Critical feature or can ship without?
3. **Combat**: Priority level for enemy AI?
4. **LLM Integration**: Planned or aspirational?
5. **Placement UI**: Implement grid system or remove files?
6. **Save System**: Next priority or can wait?

---

## Version History

- **v1.0** (Current): Initial Claude.md creation
  - Based on codebase analysis (January 2025)
  - Reflects main.py at 3,559 lines
  - Game Mechanics v5 at 4,432 lines

---

**Last Updated**: 2025-10-31
**For**: AI assistants and developers working on Game-1
**Maintained By**: Project developers

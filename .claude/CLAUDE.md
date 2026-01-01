# Claude.md - Game-1 Developer Guide

**Quick Reference for AI Assistants & Developers**
**Last Updated**: December 31, 2025

## Project Summary

**Game-1** is a production-ready crafting RPG built with Python/Pygame featuring:
- 100x100 tile world with procedural chunk generation
- 5 crafting disciplines (Smithing, Alchemy, Refining, Engineering, Enchanting) with unique minigames
- Full combat system with enemies, damage pipeline, enchantments, and status effects
- 100+ skills with mana, cooldowns, and level-based scaling
- Character progression (30 levels, 6 stats, titles, classes)
- Tag-driven effect system for combat and skills
- Complete save/load system preserving all game state
- Equipment system with durability, weight, and repairs

**Architecture**: Modular (70 Python files, ~22,000 lines)
**Master Reference**: `docs/GAME_MECHANICS_V6.md` (5,089 lines)
**Project Duration**: October 19 - December 31, 2025 (73 days, 468 commits)

---

## Critical: What's Implemented vs Designed

### Fully Working
- World generation & rendering (100x100 tiles, chunk-based)
- Resource gathering with tool requirements
- Inventory system (30 slots, drag-and-drop)
- Equipment system (8 slots: weapons, armor, tools)
- **All 5 crafting disciplines with minigames** (9,159 lines total)
- Character progression (30 levels, 6 stats, EXP curves)
- Class system (6 classes with tag-driven bonuses)
- Title system (all tiers: Novice through Master)
- **Full combat system** (damage pipeline, enchantments, dual wielding)
- **100+ skills** with mana, cooldowns, effects
- **Status effects** (DoT, CC, buffs, debuffs - 827 lines)
- **Enchantments** (12+ types affecting combat stats)
- **Full save/load system** (complete state preservation)
- **Durability, weight, and repair systems**
- **Tag-driven effect system** (combat, skills, items)

### Partially Implemented
- Minigames (all working but need polish)
- Skill effects (system exists, some effects not fully tuned)
- World generation (basic chunks, detailed templates pending)
- NPC/Quest system (basic functionality, needs expansion)

### Designed But NOT Implemented
- Advanced skill evolution chains
- LLM integration for procedural content
- Block/Parry combat mechanics
- Summon mechanics
- Advanced spell casting / combos

**Important**: Don't assume features from design docs exist in code. Check `GAME_MECHANICS_V6.md` for implementation status.

---

## Architecture Overview

### Modular Structure

```
Game-1-modular/
├── main.py                      # Entry point (~30 lines)
├── core/                        # Core game systems
│   ├── config.py                # Game configuration constants
│   ├── game_engine.py           # Main game engine (2,733 lines)
│   └── testing.py               # Crafting system tester
├── data/                        # Data layer
│   ├── models/                  # Pure data classes (dataclasses)
│   │   ├── materials.py         # MaterialDefinition
│   │   ├── equipment.py         # EquipmentItem
│   │   ├── skills.py            # SkillDefinition, PlayerSkill
│   │   ├── recipes.py           # Recipe, PlacementData
│   │   ├── world.py             # Position, TileType, WorldTile
│   │   ├── titles.py            # TitleDefinition
│   │   └── classes.py           # ClassDefinition with tags
│   └── databases/               # Singleton database loaders
│       ├── material_db.py       # MaterialDatabase
│       ├── equipment_db.py      # EquipmentDatabase
│       ├── recipe_db.py         # RecipeDatabase
│       ├── skill_db.py          # SkillDatabase
│       ├── title_db.py          # TitleDatabase
│       └── class_db.py          # ClassDatabase
├── entities/                    # Game entities
│   ├── character.py             # Character class (1,008 lines)
│   ├── tool.py                  # Tool class
│   └── components/              # Character components
│       ├── inventory.py         # Inventory, ItemStack
│       ├── equipment_manager.py # EquipmentManager
│       ├── skill_manager.py     # SkillManager (709 lines)
│       ├── stats.py             # CharacterStats
│       └── leveling.py          # LevelingSystem
├── systems/                     # Game system managers
│   ├── world_system.py          # WorldSystem (generation, chunks)
│   ├── title_system.py          # TitleSystem
│   └── class_system.py          # ClassSystem with tag bonuses
├── rendering/                   # All rendering code
│   └── renderer.py              # Renderer class (2,782 lines)
├── Combat/                      # Combat system
│   ├── combat_manager.py        # CombatManager (1,377 lines)
│   └── enemy.py                 # Enemy, EnemyDatabase
├── Crafting-subdisciplines/     # Crafting minigames
│   ├── smithing.py              # Smithing minigame
│   ├── alchemy.py               # Alchemy minigame
│   ├── refining.py              # Refining minigame
│   ├── engineering.py           # Engineering minigame
│   └── enchanting.py            # Enchanting minigame
├── save_system/                 # Save/load system
│   └── save_manager.py          # Full state persistence
└── docs/                        # Technical documentation
    ├── GAME_MECHANICS_V6.md     # MASTER REFERENCE (5,089 lines)
    └── tag-system/              # Tag system documentation
```

### Key Classes

**Database Singletons** (load on startup):
- `MaterialDatabase` - 57+ materials from JSON
- `EquipmentDatabase` - Weapons, armor, tools
- `RecipeDatabase` - 100+ recipes across 5 disciplines
- `TitleDatabase` - 40+ achievement titles
- `ClassDatabase` - 6 starting classes with tags
- `SkillDatabase` - 100+ skill definitions

**Core Systems**:
- `Character` - Player entity with stats, inventory, equipment, skills
- `CombatManager` - Full damage pipeline, enchantments, status effects
- `SkillManager` - Skill activation, mana, cooldowns, affinity bonuses
- `WorldSystem` - 100x100 tiles, chunk-based generation
- `Renderer` - All drawing logic (2,782 lines)
- `GameEngine` - Main loop, event handling, UI

### Design Patterns

1. **Singleton Databases**: All data loaded once at startup via `get_instance()`
2. **Component Pattern**: Character composed of pluggable components
3. **Dataclasses**: Heavy use of `@dataclass` for data structures
4. **Tag-Driven Effects**: Combat, skills, and items use composable tag system
5. **JSON-Driven Content**: All items, recipes, materials, skills defined in JSON

---

## Tag System (Major Feature)

The tag-driven effect system is the core combat mechanic. All effects are defined through composable tags:

### Tag Categories

**Damage Types**: `physical`, `fire`, `ice`, `lightning`, `poison`, `arcane`, `shadow`, `holy`

**Geometry Tags**: `single`, `chain`, `cone`, `circle`, `beam`, `pierce`

**Status Effects**: `burn`, `bleed`, `poison`, `freeze`, `chill`, `stun`, `root`, `shock`

**Special Behaviors**: `knockback`, `pull`, `lifesteal`, `execute`, `critical`, `reflect`

### Tag Flow
```
JSON Definition → Database → Equipment/Skills → Effect Executor → Game World
```

### Example: Fire Skill
```json
{
  "skillId": "fireball",
  "tags": ["fire", "circle", "burn"],
  "effectParams": {
    "baseDamage": 50,
    "circle_radius": 3.0,
    "burn_duration": 5.0,
    "burn_damage_per_second": 8.0
  }
}
```

**Documentation**: See `docs/tag-system/TAG-GUIDE.md` for comprehensive tag reference.

---

## File Organization

```
Game-1-modular/
├── items.JSON/                  # Item definitions
│   ├── items-materials-1.JSON   # 57 raw materials
│   ├── items-smithing-1.JSON    # Weapons, armor
│   ├── items-smithing-2.JSON    # More equipment
│   ├── items-alchemy-1.JSON     # Potions, consumables
│   ├── items-refining-1.JSON    # Ingots, planks
│   └── items-tools-1.JSON       # Placeable tools
├── recipes.JSON/                # Crafting recipes
│   ├── recipes-smithing-3.json  # Most current smithing
│   ├── recipes-alchemy-1.JSON   # Alchemy recipes
│   ├── recipes-refining-1.JSON  # Material processing
│   ├── recipes-engineering-1.JSON
│   └── recipes-adornments-1.json # Enchantments
├── placements.JSON/             # Grid layouts for minigames
├── progression/                 # Character progression
│   ├── classes-1.JSON           # 6 classes with tags
│   └── titles-1.JSON            # 40+ titles
├── Skills/                      # Skill definitions
│   └── skills-skills-1.JSON     # 100+ skills
└── Definitions.JSON/            # System definitions
    ├── stats-calculations.JSON  # Stat formulas
    ├── value-translation-table-1.JSON
    └── skills-translation-table.JSON
```

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
```
Final Value = Base × (1 + Stat Bonuses) × (1 + Title Bonuses) × (1 + Equipment Bonuses) × (1 + Class Affinity)
```

### 4. Tier System
- **T1**: Common materials (oak, iron, limestone)
- **T2**: Uncommon (ash, steel, marble)
- **T3**: Rare (ironwood, mithril, obsidian)
- **T4**: Legendary (voidsteel, dragonsteel, voidstone)

Tier multipliers: T1=1.0x, T2=2.0x, T3=4.0x, T4=8.0x

### 5. No Breaking (Durability)
- 100% durability = 100% effectiveness
- 0% durability = 50% effectiveness forever
- Items never destroyed, only degraded

---

## Combat System

### Damage Pipeline
```
Base Damage (weapon)
  × Hand Type Bonus (+10-20%)
  × Strength Multiplier (1.0 + STR × 0.05)
  × Skill Buff Bonus (+50% to +400%)
  × Class Affinity Bonus (up to +20%)
  × Title Bonus
  × Weapon Tag Bonuses
  × Critical Hit (2x if triggered)
  - Enemy Defense (max 75% reduction)
  = Final Damage
```

### Enchantment Effects (Combat Integration)
| Enchantment | Effect | Trigger |
|-------------|--------|---------|
| Sharpness | +X% damage | Passive |
| Protection | +X% defense | Passive |
| Fire Aspect | Apply burn DoT | On hit |
| Lifesteal | Heal % of damage | On hit |
| Knockback | Push enemy back | On hit |
| Chain Damage | Hit nearby enemies | On hit |
| Thorns | Reflect damage | On hit received |

### Status Effects
- **DoT**: Burn, Bleed, Poison, Shock (damage per second)
- **CC**: Freeze, Stun, Root, Slow (movement/action prevention)
- **Buffs**: Empower, Fortify, Haste (stat increases)
- **Debuffs**: Vulnerable, Weaken (increased damage taken/reduced damage dealt)

---

## Skill System

### Core Mechanics
- **100+ skills** defined in JSON
- **Mana-based** (base 100 + INT × 20 + level × 10)
- **Cooldown-based** (short: 2min, moderate: 5min, long: 10min, extreme: 20min)
- **Level scaling**: `effectValue × (1 + (level - 1) × 0.1)` (max +90% at level 10)

### Skill Affinity System
Class tags matching skill tags grant effectiveness bonuses:
```
matching_tags = intersection(class.tags, skill.tags)
bonus = min(len(matching_tags) * 5%, 20%)
```

Example: Warrior (melee, physical) using "Power Strike" (melee, physical) = +10% effectiveness

### Effect Types
| Effect | Description |
|--------|-------------|
| empower | Increases damage/power |
| quicken | Increases speed |
| fortify | Flat damage reduction |
| enrich | Extra item drops |
| pierce | Critical hit chance |
| restore | Instant HP/mana/durability |
| regenerate | HP/mana per second |
| elevate | Rarity upgrade chance |
| devastate | AoE tile radius |
| transcend | Tier bypass |

---

## Class System

### 6 Starting Classes

| Class | Tags | Key Bonuses |
|-------|------|-------------|
| **Warrior** | warrior, melee, physical, tanky | +30 HP, +10% melee damage |
| **Ranger** | ranger, ranged, agile, nature | +15% move speed, +10% forestry |
| **Scholar** | scholar, magic, alchemy, arcane | +100 mana, +10% recipe discovery |
| **Artisan** | artisan, crafting, smithing | +10% crafting time, +10% first-try |
| **Scavenger** | scavenger, luck, gathering | +20% rare drops, +15% pickaxe |
| **Adventurer** | adventurer, balanced, versatile | +5% all gathering/crafting |

### Tool Efficiency Bonuses
| Tag Combination | Tool | Bonus |
|-----------------|------|-------|
| nature | Axe | +10% |
| gathering | Pickaxe | +10% |
| physical + melee | All tools | +10% damage |

---

## Database Loading Patterns

All databases follow singleton pattern:

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

---

## Common Development Tasks

### Adding a New Recipe

1. Choose discipline and locate file:
   - Smithing: `recipes.JSON/recipes-smithing-3.json`
   - Alchemy: `recipes.JSON/recipes-alchemy-1.JSON`

2. Add recipe object with required fields:
```json
{
  "recipeId": "smithing_iron_sword_001",
  "outputId": "iron_sword",
  "outputQty": 1,
  "stationType": "smithing",
  "stationTier": 1,
  "inputs": [
    {"materialId": "iron_ingot", "qty": 3}
  ]
}
```

3. Game auto-loads on restart

### Adding a New Material

1. Add to `items.JSON/items-materials-1.JSON`:
```json
{
  "materialId": "mythril_ore",
  "name": "Mythril Ore",
  "tier": 3,
  "category": "ore",
  "rarity": "rare"
}
```

2. Add resource node to `Definitions.JSON/Resource-node-1.JSON` if gatherable

### Adding a Skill with Tags

1. Add to `Skills/skills-skills-1.JSON`:
```json
{
  "skillId": "flame_strike",
  "name": "Flame Strike",
  "tags": ["fire", "melee", "single", "burn"],
  "effectParams": {
    "baseDamage": 75,
    "burn_duration": 5.0,
    "burn_damage_per_second": 10.0
  },
  "manaCost": "moderate",
  "cooldown": "short"
}
```

---

## Known Issues & Current Work

**See**: `MASTER_ISSUE_TRACKER.md` for comprehensive bug list

### Critical Issues
- Inventory click misalignment after save load
- Default save missing icon_path data

### Testing Required
- 5 enchantments need integration testing
- Turret status effects verification
- Engineering device (traps, bombs) testing

---

## Debugging Tips

### Enable Debug Mode
Press **F1** in-game to toggle debug mode:
- Infinite resources
- Debug info overlays

### Check Database Loading
```python
mat_db = MaterialDatabase.get_instance()
print(f"Loaded {len(mat_db.materials)} materials")

skill_db = SkillDatabase.get_instance()
print(f"Loaded {len(skill_db.skills)} skills")
```

### Tag System Debugging
```python
from core.tag_debug import get_tag_debugger
debugger = get_tag_debugger()
debugger.enable()
# ... your code ...
debugger.disable()
```

---

## Quick Command Reference

### Run Game
```bash
cd Game-1-modular
python main.py
```

### Check JSON Validity
```bash
python -m json.tool recipes.JSON/recipes-smithing-3.json > /dev/null
```

---

## When Working on This Project

### DO:
- Check `GAME_MECHANICS_V6.md` for implementation status before assuming features exist
- Reference `NAMING_CONVENTIONS.md` for method names
- Use singleton pattern for databases
- Follow tag system conventions for new combat effects
- Test JSON changes by restarting the game

### DON'T:
- Assume design docs describe implemented features
- Create new JSON schemas without checking existing patterns
- Hardcode values that should be in JSON
- Skip checking tag documentation for combat/skill work

---

## Documentation Index

| Document | Purpose |
|----------|---------|
| **GAME_MECHANICS_V6.md** | Master reference - all mechanics (5,089 lines) |
| **MASTER_ISSUE_TRACKER.md** | Known bugs and improvements |
| **docs/tag-system/TAG-GUIDE.md** | Comprehensive tag system guide |
| **docs/ARCHITECTURE.md** | System architecture overview |
| **NAMING_CONVENTIONS.md** | API naming standards |
| **INDEX.md** | Documentation index |

---

## Version History

- **v2.0** (December 31, 2025): Major update for modular architecture, tag system, full combat, skills, save/load
- **v1.0** (November 17, 2025): Initial Claude.md creation (monolithic main.py)

---

**Last Updated**: 2025-12-31
**For**: AI assistants and developers working on Game-1
**Maintained By**: Project developers

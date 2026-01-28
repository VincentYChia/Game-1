# Claude.md - Game-1 Developer Guide

**Quick Reference for AI Assistants & Developers**
**Last Updated**: January 27, 2026

## Project Summary

**Game-1** is a production-ready crafting RPG built with Python/Pygame featuring:
- 100x100 tile world with procedural chunk generation
- 5 crafting disciplines (Smithing, Alchemy, Refining, Engineering, Enchanting) with unique minigames
- **LLM-powered "Invented Items" system** for procedural content generation (NEW)
- **ML classifiers** (CNN + LightGBM) for recipe validation (NEW)
- Full combat system with enemies, damage pipeline, enchantments, and status effects
- 100+ skills with mana, cooldowns, and level-based scaling
- Character progression (30 levels, 6 stats, titles, classes)
- Tag-driven effect system for combat and skills
- Complete save/load system preserving all game state
- Equipment system with durability, weight, and repairs

**Architecture**: Modular (136 Python files, ~62,380 lines)
**Master Reference**: `docs/GAME_MECHANICS_V6.md` (5,089 lines)
**Status Report**: `docs/REPOSITORY_STATUS_REPORT_2026-01-27.md`
**Project Duration**: October 19, 2025 - Present (ongoing development)

---

## Critical: What's Implemented vs Designed

### Fully Working
- World generation & rendering (100x100 tiles, chunk-based)
- Resource gathering with tool requirements
- Inventory system (30 slots, drag-and-drop)
- Equipment system (8 slots: weapons, armor, tools)
- **All 5 crafting disciplines with minigames** (5,346 lines total)
- **LLM Item Generation** via Claude API (systems/llm_item_generator.py - 1,393 lines) (NEW)
- **Crafting Classifiers** - CNN for smithing/adornments, LightGBM for others (NEW)
- **Invented Recipes** - Player-created content persisted across saves (NEW)
- Character progression (30 levels, 6 stats, EXP curves)
- Class system (6 classes with tag-driven bonuses)
- Title system (all tiers: Novice through Master)
- **Full combat system** (damage pipeline, enchantments, dual wielding)
- **100+ skills** with mana, cooldowns, effects
- **Status effects** (DoT, CC, buffs, debuffs - 827 lines)
- **14 Enchantments fully integrated** (see Combat section)
- **Full save/load system** (complete state preservation)
- **Durability, weight, and repair systems**
- **Tag-driven effect system** (combat, skills, items)
- **Difficulty/Reward calculators** (material-based scaling)

### Partially Implemented
- World generation (basic chunks, detailed templates pending)
- NPC/Quest system (basic functionality, needs expansion)

### Designed But NOT Implemented
- Advanced skill evolution chains
- Block/Parry combat mechanics (TODO in combat_manager.py)
- Summon mechanics (TODO in effect_executor.py:233)
- Advanced spell casting / combos

**Important**: Don't assume features from design docs exist in code. Check `GAME_MECHANICS_V6.md` for implementation status.

---

## LLM Integration System (NEW - January 2026)

### Overview
Players can **invent new items** by placing materials in unique arrangements. The system:
1. Validates placements using ML classifiers (CNN or LightGBM)
2. Generates item definitions via Claude API
3. Adds items to inventory
4. Persists invented recipes for re-crafting

### Key Files
```
systems/
├── llm_item_generator.py      # Claude API integration (1,393 lines)
└── crafting_classifier.py     # CNN + LightGBM validation (1,256 lines)

Scaled JSON Development/
├── LLM Training Data/Fewshot_llm/    # System prompts & examples
├── Convolution Neural Network (CNN)/ # Trained CNN models
└── Simple Classifiers (LightGBM)/    # Trained LightGBM models
```

### Classifier Mapping
| Discipline | Model Type | Input Format |
|------------|------------|--------------|
| Smithing | CNN | 36×36×3 RGB image |
| Adornments | CNN | 56×56×3 RGB image |
| Alchemy | LightGBM | 34 numeric features |
| Refining | LightGBM | 18 numeric features |
| Engineering | LightGBM | 28 numeric features |

### LLM Configuration
```python
# In systems/llm_item_generator.py
model = "claude-sonnet-4-20250514"
temperature = 0.4
max_tokens = 2000
timeout = 30.0
```

### API Key Setup
1. Set environment variable: `export ANTHROPIC_API_KEY="sk-ant-..."`
2. Or create `.env` file in Game-1-modular/: `ANTHROPIC_API_KEY=sk-ant-...`
3. Fallback: MockBackend generates placeholder items without API

### Debug Logs
All LLM API calls are logged to `llm_debug_logs/TIMESTAMP_discipline.json`

---

## Architecture Overview

### Modular Structure

```
Game-1-modular/
├── main.py                      # Entry point (~30 lines)
├── core/                        # Core game systems (23 files, 15,589 LOC)
│   ├── config.py                # Game configuration constants
│   ├── game_engine.py           # Main game engine (7,817 lines)
│   ├── interactive_crafting.py  # 5 discipline crafting UIs (1,078 lines)
│   ├── effect_executor.py       # Tag-based combat effects (624 lines)
│   ├── difficulty_calculator.py # Material-based difficulty (803 lines)
│   ├── reward_calculator.py     # Performance rewards (608 lines)
│   ├── tag_system.py            # Tag registry
│   ├── tag_parser.py            # Tag parsing
│   ├── crafting_tag_processor.py # Discipline tag processing
│   ├── minigame_effects.py      # Particle effects (~2,000 lines)
│   └── testing.py               # Crafting system tester
├── data/                        # Data layer (25 files, 3,745 LOC)
│   ├── models/                  # Pure data classes (dataclasses)
│   │   ├── materials.py         # MaterialDefinition
│   │   ├── equipment.py         # EquipmentItem
│   │   ├── skills.py            # SkillDefinition, PlayerSkill
│   │   ├── recipes.py           # Recipe, PlacementData
│   │   ├── world.py             # Position, TileType, WorldTile
│   │   ├── titles.py            # TitleDefinition
│   │   └── classes.py           # ClassDefinition with tags
│   └── databases/               # Singleton database loaders (10 files)
│       ├── material_db.py       # MaterialDatabase
│       ├── equipment_db.py      # EquipmentDatabase
│       ├── recipe_db.py         # RecipeDatabase
│       ├── skill_db.py          # SkillDatabase
│       ├── title_db.py          # TitleDatabase
│       ├── class_db.py          # ClassDatabase
│       ├── npc_db.py            # NPCDatabase
│       ├── placement_db.py      # PlacementDatabase
│       ├── translation_db.py    # TranslationDatabase
│       └── skill_unlock_db.py   # SkillUnlockDatabase
├── entities/                    # Game entities (17 files, 6,909 LOC)
│   ├── character.py             # Character class (1,008 lines)
│   ├── tool.py                  # Tool class
│   └── components/              # Character components
│       ├── inventory.py         # Inventory, ItemStack
│       ├── equipment_manager.py # EquipmentManager
│       ├── skill_manager.py     # SkillManager (709 lines)
│       ├── stats.py             # CharacterStats
│       ├── buffs.py             # Buff/debuff tracking
│       └── leveling.py          # LevelingSystem
├── systems/                     # Game system managers (16 files, 5,856 LOC)
│   ├── world_system.py          # WorldSystem (generation, chunks)
│   ├── title_system.py          # TitleSystem
│   ├── class_system.py          # ClassSystem with tag bonuses
│   ├── llm_item_generator.py    # LLM integration (1,393 lines) (NEW)
│   └── crafting_classifier.py   # ML classifiers (1,256 lines) (NEW)
├── rendering/                   # All rendering code (3 files, 5,679 LOC)
│   └── renderer.py              # Renderer class (2,782 lines)
├── Combat/                      # Combat system (3 files, 2,527 LOC)
│   ├── combat_manager.py        # CombatManager (1,655 lines)
│   └── enemy.py                 # Enemy, EnemyDatabase (867 lines)
├── Crafting-subdisciplines/     # Crafting minigames (8 files, 5,346 LOC)
│   ├── smithing.py              # Smithing minigame (749 lines)
│   ├── alchemy.py               # Alchemy minigame (1,052 lines)
│   ├── refining.py              # Refining minigame (820 lines)
│   ├── engineering.py           # Engineering minigame (1,315 lines)
│   └── enchanting.py            # Enchanting minigame (1,410 lines)
├── save_system/                 # Save/load system
│   └── save_manager.py          # Full state persistence
└── docs/                        # Technical documentation
    ├── GAME_MECHANICS_V6.md     # MASTER REFERENCE (5,089 lines)
    ├── REPOSITORY_STATUS_REPORT_2026-01-27.md # Current status
    └── tag-system/              # Tag system documentation
```

### Key Classes

**Database Singletons** (load on startup):
- `MaterialDatabase` - 57+ materials from JSON
- `EquipmentDatabase` - Weapons, armor, tools
- `RecipeDatabase` - 100+ recipes across 5 disciplines + invented recipes
- `TitleDatabase` - 40+ achievement titles
- `ClassDatabase` - 6 starting classes with tags
- `SkillDatabase` - 100+ skill definitions
- `PlacementDatabase` - Minigame grid layouts

**Core Systems**:
- `Character` - Player entity with stats, inventory, equipment, skills
- `CombatManager` - Full damage pipeline, enchantments, status effects
- `SkillManager` - Skill activation, mana, cooldowns, affinity bonuses
- `WorldSystem` - 100x100 tiles, chunk-based generation
- `Renderer` - All drawing logic (2,782 lines)
- `GameEngine` - Main loop, event handling, UI (7,817 lines)
- `LLMItemGenerator` - Claude API integration for invented items (NEW)
- `CraftingClassifierManager` - CNN/LightGBM validation (NEW)

### Design Patterns

1. **Singleton Databases**: All data loaded once at startup via `get_instance()`
2. **Component Pattern**: Character composed of pluggable components
3. **Dataclasses**: Heavy use of `@dataclass` for data structures
4. **Tag-Driven Effects**: Combat, skills, and items use composable tag system
5. **JSON-Driven Content**: All items, recipes, materials, skills defined in JSON
6. **Background Threading**: LLM generation runs async to avoid UI freeze (NEW)

---

## Crafting System

### Difficulty Calculator
Material-based difficulty scaling (core/difficulty_calculator.py):

**Point System** (Linear):
- T1 = 1 point, T2 = 2 points, T3 = 3 points, T4 = 4 points per item

**Difficulty Tiers**:
| Tier | Points | Distribution |
|------|--------|--------------|
| Common | 0-4 | ~20% |
| Uncommon | 5-10 | ~25% |
| Rare | 11-20 | ~30% |
| Epic | 21-40 | ~20% |
| Legendary | 41+ | ~5% |

**Discipline-Specific Modifiers**:
- Smithing: base_points only
- Refining: base × diversity × station_tier (1.5x-4.5x)
- Alchemy: base × diversity × tier_modifier × volatility
- Engineering: base × diversity × slot_modifier
- Enchanting: base × diversity

### Reward Calculator
Performance-based rewards (core/reward_calculator.py):

**Quality Tiers** (by performance 0.0-1.0):
| Score | Quality |
|-------|---------|
| 0-25% | Normal |
| 25-50% | Fine |
| 50-75% | Superior |
| 75-90% | Masterwork |
| 90-100% | Legendary |

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

### Enchantment Effects (14 Implemented - January 2026)
| Enchantment | Type | Trigger | Status |
|-------------|------|---------|--------|
| Sharpness I-III | damage_multiplier | Passive | ✅ Working |
| Protection I-III | defense_multiplier | Passive | ✅ Working |
| Efficiency I-II | gathering_speed_multiplier | Passive | ✅ Working |
| Fortune I-II | bonus_yield_chance | Passive | ✅ Working |
| Unbreaking I-II | durability_multiplier | Passive | ✅ Working |
| Fire Aspect | damage_over_time | On hit | ✅ Working |
| Poison | damage_over_time | On hit | ✅ Working |
| Swiftness | movement_speed_multiplier | Equip | ✅ Working |
| Thorns | reflect_damage | On hit received | ✅ Working |
| Knockback | knockback | On hit | ✅ Working |
| Lifesteal | lifesteal | On hit | ✅ Working |
| Health Regen | health_regeneration | Periodic | ✅ Working |
| Frost Touch | slow | On hit | ✅ Working |
| Chain Damage | chain_damage | On hit | ✅ Working |

**Deferred** (3 types - by design):
- Self-Repair, Weightless, Silk Touch

### Status Effects (All Implemented)
- **DoT**: Burn, Bleed, Poison, Shock (damage per second)
- **CC**: Freeze, Stun, Root, Slow/Chill (movement/action prevention)
- **Buffs**: Empower, Fortify, Haste, Regeneration, Shield
- **Debuffs**: Vulnerable, Weaken
- **Special**: Phase/Ethereal, Invisible

---

## File Organization

```
Game-1-modular/
├── items.JSON/                  # Item definitions
│   ├── items-materials-1.JSON   # 57 raw materials
│   ├── items-smithing-2.JSON    # Weapons, armor
│   ├── items-alchemy-1.JSON     # Potions, consumables
│   ├── items-refining-1.JSON    # Ingots, planks
│   ├── items-engineering-1.JSON # Devices
│   └── items-tools-1.JSON       # Placeable tools
├── recipes.JSON/                # Crafting recipes
│   ├── recipes-smithing-3.json  # Most current smithing
│   ├── recipes-alchemy-1.JSON   # Alchemy recipes
│   ├── recipes-refining-1.JSON  # Material processing
│   ├── recipes-engineering-1.JSON
│   ├── recipes-enchanting-1.JSON
│   └── recipes-adornments-1.json # Enchantments
├── placements.JSON/             # Grid layouts for minigames
├── progression/                 # Character progression
│   ├── classes-1.JSON           # 6 classes with tags
│   ├── titles-1.JSON            # 40+ titles
│   └── npcs-1.JSON              # NPC definitions
├── Skills/                      # Skill definitions
│   └── skills-skills-1.JSON     # 100+ skills
└── Definitions.JSON/            # System definitions
    ├── tag-definitions.JSON     # All tag definitions
    ├── hostiles-1.JSON          # Enemy definitions
    ├── stats-calculations.JSON  # Stat formulas
    └── crafting-stations-1.JSON # Station definitions
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

## Known Issues & Current Work

**See**: `MASTER_ISSUE_TRACKER.md` for comprehensive bug list
**See**: `docs/REPOSITORY_STATUS_REPORT_2026-01-27.md` for full status

### Recently Resolved (January 2026)
- ✅ Inventory click misalignment - spacing synchronized
- ✅ All 14 enchantments now working (Lifesteal, Knockback, Chain Damage, Health Regen, Frost Touch)
- ✅ Unused imports (`Path`, `copy`) removed from crafting files
- ✅ `import random` in enchanting.py - uses inline imports (functional)

### Code Quality Notes
- Duplicate singleton pattern across 10 database files (acceptable technical debt)
- Duplicate methods across 5 crafting minigame files (could be refactored)

### Not Yet Implemented (Despite Documentation)
- Block/Parry combat mechanics
- Summon mechanics
- Advanced skill evolution chains

### Open Issues
- Tooltip z-order (can be covered by equipment menu)
- Missing crafting station definitions (Tier 3/4)
- Missing station icons (forge_t4.png, enchanting_table_t2.png)

---

## Debugging Tips

### Enable Debug Mode
Press **F1** in-game to toggle debug mode:
- Infinite resources
- Debug info overlays

Additional debug keys:
- **F2**: Auto-learn all skills
- **F3**: Grant all titles
- **F4**: Max level + stats
- **F7**: Infinite durability

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

### LLM Debug Logs
Check `llm_debug_logs/` for full API request/response logs

---

## Quick Command Reference

### Run Game
```bash
cd Game-1-modular
python main.py
```

### Run Tests
```bash
cd Game-1-modular
python -m pytest tests/ -v
```

### Check JSON Validity
```bash
python -m json.tool recipes.JSON/recipes-smithing-3.json > /dev/null
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

## When Working on This Project

### DO:
- Check `GAME_MECHANICS_V6.md` for implementation status before assuming features exist
- Check `REPOSITORY_STATUS_REPORT_2026-01-27.md` for current system state
- Reference `NAMING_CONVENTIONS.md` for method names
- Use singleton pattern for databases
- Follow tag system conventions for new combat effects
- Test JSON changes by restarting the game
- Check `llm_debug_logs/` when debugging LLM issues

### DON'T:
- Assume design docs describe implemented features
- Create new JSON schemas without checking existing patterns
- Hardcode values that should be in JSON
- Skip checking tag documentation for combat/skill work
- Forget to add `import random` if using random functions

---

## Documentation Index

| Document | Purpose |
|----------|---------|
| **GAME_MECHANICS_V6.md** | Master reference - all mechanics (5,089 lines) |
| **REPOSITORY_STATUS_REPORT_2026-01-27.md** | Current system state (NEW) |
| **MASTER_ISSUE_TRACKER.md** | Known bugs and improvements |
| **docs/tag-system/TAG-GUIDE.md** | Comprehensive tag system guide |
| **docs/ARCHITECTURE.md** | System architecture overview |
| **NAMING_CONVENTIONS.md** | API naming standards |
| **INDEX.md** | Documentation index |
| **Fewshot_llm/README.md** | LLM system documentation (NEW) |
| **Fewshot_llm/MANUAL_TUNING_GUIDE.md** | LLM prompt editing guide (NEW) |

---

## Version History

- **v3.0** (January 27, 2026): Major update for LLM integration, crafting classifiers, invented items system
- **v2.0** (December 31, 2025): Major update for modular architecture, tag system, full combat, skills, save/load
- **v1.0** (November 17, 2025): Initial Claude.md creation (monolithic main.py)

---

**Last Updated**: 2026-01-27
**For**: AI assistants and developers working on Game-1
**Maintained By**: Project developers

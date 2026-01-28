# Game-1 Modular Architecture

**Last Updated**: 2026-01-27

This is the **modular refactored version** of Game-1, featuring a production-ready crafting RPG with **LLM-powered item generation** and **ML-based recipe validation**.

## Key Features

- 🎮 **136 Python files** (~62,380 lines of code)
- 🤖 **LLM Integration** - Claude API for procedural item generation
- 🧠 **ML Classifiers** - CNN + LightGBM for recipe validation
- ⚔️ **Full Combat System** - Damage pipeline, enchantments, status effects
- 🛠️ **5 Crafting Disciplines** - Each with unique minigames
- 💾 **Complete Save/Load** - Full state preservation

## Purpose

The modular architecture provides:
- **Better organization**: Find any system in seconds
- **Easier maintenance**: Isolated changes with minimal risk
- **Parallel development**: Multiple developers can work simultaneously
- **Scalable JSON production**: Clear data models with ML validation
- **Testing**: 13 test files with automated crafting tests

## Architecture Overview

```
Game-1-modular/
├── main.py                          # Entry point (~30 lines)
│
├── core/                            # Core game systems (23 files, ~15,589 LOC)
│   ├── config.py                    # Game configuration constants
│   ├── camera.py                    # Camera/viewport system
│   ├── game_engine.py               # Main game engine (7,817 lines)
│   ├── interactive_crafting.py      # 5 discipline crafting UIs (1,078 lines)
│   ├── effect_executor.py           # Tag-based combat effects (624 lines)
│   ├── difficulty_calculator.py     # Material-based difficulty (803 lines)
│   ├── reward_calculator.py         # Performance rewards (608 lines)
│   ├── tag_system.py                # Tag registry
│   ├── tag_parser.py                # Tag parsing
│   └── testing.py                   # Crafting system tester
│
├── data/                            # Data layer (25 files, ~3,745 LOC)
│   ├── models/                      # Pure data classes (dataclasses)
│   │   ├── materials.py, equipment.py, skills.py, recipes.py
│   │   ├── world.py, quests.py, npcs.py, titles.py, classes.py
│   └── databases/                   # Singleton database loaders (10 files)
│       ├── material_db.py, equipment_db.py, skill_db.py
│       ├── recipe_db.py, placement_db.py, npc_db.py
│       └── title_db.py, class_db.py, translation_db.py
│
├── entities/                        # Game entities (17 files, ~6,909 LOC)
│   ├── character.py                 # Character class (1,008 lines)
│   ├── status_effect.py             # Status effects (827 lines)
│   └── components/                  # Character components
│       ├── skill_manager.py         # SkillManager (709 lines)
│       ├── inventory.py, equipment_manager.py, buffs.py
│       └── stats.py, leveling.py, activity_tracker.py
│
├── systems/                         # Game system managers (16 files, ~5,856 LOC)
│   ├── world_system.py              # WorldSystem (generation, chunks)
│   ├── llm_item_generator.py        # LLM integration (1,393 lines) [NEW]
│   ├── crafting_classifier.py       # ML classifiers (1,256 lines) [NEW]
│   ├── title_system.py, class_system.py, quest_system.py
│   └── npc_system.py, encyclopedia.py, natural_resource.py
│
├── rendering/                       # All rendering code (3 files, ~5,679 LOC)
│   └── renderer.py                  # Renderer class (2,782 lines)
│
├── Combat/                          # Combat system (3 files, ~2,527 LOC)
│   ├── combat_manager.py            # CombatManager (1,655 lines)
│   └── enemy.py                     # Enemy, EnemyDatabase (867 lines)
│
├── Crafting-subdisciplines/         # Crafting minigames (8 files, ~5,346 LOC)
│   ├── smithing.py                  # Smithing minigame (749 lines)
│   ├── alchemy.py                   # Alchemy minigame (1,052 lines)
│   ├── refining.py                  # Refining minigame (820 lines)
│   ├── engineering.py               # Engineering minigame (1,315 lines)
│   ├── enchanting.py                # Enchanting minigame (1,410 lines)
│   └── rarity_utils.py              # Shared rarity system
│
├── tests/                           # Test files (13 files)
│   └── test_*.py                    # Unit and integration tests
│
├── assets/                          # Game assets
│   ├── icons/                       # Item and UI icons
│   └── items/                       # Item sprites
│
├── tools/                           # Development tools
│   ├── smithing-grid-designer.py    # Smithing pattern designer
│   └── enchanting-pattern-designer.py
│
└── [JSON Directories]               # Game data files
    ├── items.JSON/                  # Item definitions (57+ materials)
    ├── recipes.JSON/                # Crafting recipes (100+ recipes)
    ├── placements.JSON/             # Minigame grid layouts
    ├── Definitions.JSON/            # Game configuration, tags
    ├── progression/                 # Classes, titles, NPCs
    └── Skills/                      # 100+ skill definitions
```

## Module Breakdown

### Core (`core/`) - 23 files, ~15,589 LOC
**Purpose**: Fundamental game systems

- **game_engine.py** (7,817 lines): Main game loop, event handling, UI, minigames
- **interactive_crafting.py** (1,078 lines): 5 discipline crafting UIs
- **effect_executor.py** (624 lines): Tag-based combat effect execution
- **difficulty_calculator.py** (803 lines): Material-based difficulty scaling
- **reward_calculator.py** (608 lines): Performance-based reward calculation
- **config.py** (77 lines): Game constants (screen size, colors, speeds)
- **tag_system.py**: Tag registry and synergy system
- **testing.py** (195 lines): Automated crafting system tests

### Data Layer (`data/`) - 25 files, ~3,745 LOC
**Purpose**: Clean separation between data models and business logic

**Models** (`data/models/`): Pure dataclasses (no logic)
- Materials, Equipment, Skills, Recipes, World, Quests, NPCs, Titles, Classes

**Databases** (`data/databases/`): Singleton loaders for JSON files
- Load from JSON, provide lookup methods, cache data

### Entities (`entities/`) - 17 files, ~6,909 LOC
**Purpose**: Game entities and their components

- **character.py** (1,008 lines): Player character integrating all components
- **status_effect.py** (827 lines): All status effect implementations
- **components/**: Pluggable character systems (stats, inventory, skills, etc.)
- **skill_manager.py** (709 lines): Skill activation, mana, cooldowns, affinity bonuses

### Systems (`systems/`) - 16 files, ~5,856 LOC
**Purpose**: Game system managers

- **llm_item_generator.py** (1,393 lines): Claude API integration for invented items
- **crafting_classifier.py** (1,256 lines): CNN + LightGBM recipe validation
- World generation and management
- Quest and NPC systems
- Title and class systems

### Rendering (`rendering/`) - 3 files, ~5,679 LOC
**Purpose**: All visual rendering

- **renderer.py** (2,782 lines): Complete rendering pipeline
  - World rendering (tiles, resources, stations, NPCs, enemies)
  - UI rendering (health, mana, buffs, notifications)
  - Inventory, equipment, skills, crafting interfaces

### Combat (`Combat/`) - 3 files, ~2,527 LOC
**Purpose**: Full combat system with damage pipeline

- **combat_manager.py** (1,655 lines): Damage pipeline, enchantments, status effects
- **enemy.py** (867 lines): Enemy AI, spawning, loot drops
- 9 enchantments fully integrated (Sharpness, Protection, Fire Aspect, etc.)

### Crafting (`Crafting-subdisciplines/`) - 8 files, ~5,346 LOC
**Purpose**: 5 crafting disciplines with unique minigames

- **smithing.py** (749 lines): Hammer timing minigame
- **alchemy.py** (1,052 lines): Chain/stabilize reaction minigame
- **refining.py** (820 lines): Temperature control minigame
- **engineering.py** (1,315 lines): Wire puzzle minigame
- **enchanting.py** (1,410 lines): Spinning wheel minigame

## Running the Game

```bash
cd Game-1-modular
python3 main.py
```

**Requirements**:
- Python 3.8+
- pygame 2.0+ (`pip install pygame`)
- anthropic (for LLM features): `pip install anthropic`

## LLM Integration System (NEW - January 2026)

### Overview
Players can **invent new items** by placing materials in unique arrangements:
1. ML classifiers validate the placement (CNN for visual, LightGBM for feature-based)
2. Claude API generates item definitions based on materials used
3. Items are added to inventory with appropriate stats
4. Invented recipes are persisted for re-crafting

### Key Files
```
systems/
├── llm_item_generator.py      # Claude API integration (1,393 lines)
└── crafting_classifier.py     # CNN + LightGBM validation (1,256 lines)

Scaled JSON Development/       # ML training data and models
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

### API Configuration
```python
# Set environment variable
export ANTHROPIC_API_KEY="sk-ant-..."

# Or create .env file in Game-1-modular/
ANTHROPIC_API_KEY=sk-ant-...
```

### Debug Logs
All LLM API calls are logged to `llm_debug_logs/TIMESTAMP_discipline.json`

## Statistics

### Code Organization
- **Total Files**: 136 Python files
- **Total Lines**: ~62,380 lines of code
- **Original**: 1 file (10,327 lines) - monolithic main.py
- **Modular**: 136 files with clean separation of concerns

### Largest Modules
1. **game_engine.py**: 7,817 lines (main loop, UI, event handling)
2. **renderer.py**: 2,782 lines (all rendering)
3. **combat_manager.py**: 1,655 lines (damage pipeline, enchantments)
4. **llm_item_generator.py**: 1,393 lines (Claude API integration)
5. **enchanting.py**: 1,410 lines (enchanting minigame)
6. **engineering.py**: 1,315 lines (engineering minigame)
7. **crafting_classifier.py**: 1,256 lines (CNN + LightGBM)
8. **alchemy.py**: 1,052 lines (alchemy minigame)
9. **character.py**: 1,008 lines (player entity)
10. **skill_manager.py**: 709 lines (skill system)

### Module Sizes
- **core/**: ~15,589 lines (23 files)
- **data/**: ~3,745 lines (25 files)
- **entities/**: ~6,909 lines (17 files)
- **systems/**: ~5,856 lines (16 files)
- **rendering/**: ~5,679 lines (3 files)
- **Combat/**: ~2,527 lines (3 files)
- **Crafting-subdisciplines/**: ~5,346 lines (8 files)

## Validation

All 136 Python files compile successfully:

```bash
cd Game-1-modular
python3 -m py_compile **/*.py
# All files compile successfully
```

## Comparison: Singular vs Modular

### Game-1-singular (Original - October 2025)
```
Game-1-singular/
    main.py                    # 10,327 lines, 62 classes
```

### Game-1-modular (Current - January 2026)
```
Game-1-modular/
    136 Python files (~62,380 lines)
    Clean separation of concerns
    No circular dependencies
    LLM-powered item generation
    ML-validated crafting system
    13 test files for validation
    Ready for team development
```

## Key Systems

### 1. Tag-Driven Effects
All combat, skills, and items use composable tags:
- 75+ registered tags in `Definitions.JSON/tag-definitions.JSON`
- Synergy system (e.g., lightning + chain = +20% range)
- JSON-driven, no code changes needed for new effects

### 2. ML-Powered Crafting
Players can invent new items:
- CNN validates visual patterns (smithing, adornments)
- LightGBM validates feature-based patterns (alchemy, refining, engineering)
- Claude API generates balanced item definitions

### 3. Database Layer
Centralized loading with error handling:
- 10 singleton database loaders
- Graceful fallbacks for missing files
- Clear error messages

### 4. Data Models
All models in `data/models/` serve as documentation:
- Type hints show expected data types
- Dataclasses for immutability
- Docstrings explain each field

## Development Workflow

### Adding New Content

**1. Create JSON** (items, recipes, skills)
```bash
# Add to appropriate JSON file
# e.g., items.JSON/items-materials-1.JSON for materials
```

**2. Test in game**
```bash
python3 main.py
```

**3. Verify with debug mode**
- Press F1 for infinite resources
- Press F2 to auto-learn all skills
- Press L for Encyclopedia

### Modifying Systems

1. Find the relevant module (e.g., `systems/quest_system.py`)
2. Make changes in isolation
3. Test without affecting other systems
4. Commit changes with clear scope

## Notes

- Original code preserved in `Game-1-singular/`
- Maintains full compatibility with existing JSON files
- No circular dependencies
- Clean import structure
- LLM features gracefully degrade without API key

## Architecture Principles

1. **Single Responsibility**: Each module has one clear purpose
2. **Dependency Injection**: Systems receive dependencies rather than importing globally
3. **Data/Logic Separation**: Models are pure data, databases load them, systems use them
4. **Component Pattern**: Character built from pluggable components
5. **Singleton Pattern**: Databases ensure single instance
6. **Tag-Driven Effects**: Combat and skills use composable tag system

## Documentation

| Document | Purpose |
|----------|---------|
| **docs/GAME_MECHANICS_V6.md** | Master reference - all mechanics (5,089 lines) |
| **docs/REPOSITORY_STATUS_REPORT_2026-01-27.md** | Current system state |
| **.claude/CLAUDE.md** | Developer guide for AI assistants |
| **MASTER_ISSUE_TRACKER.md** | Known bugs and improvements |
| **docs/tag-system/TAG-GUIDE.md** | Comprehensive tag system guide |

---

**Original**: 10,327 lines in 1 file (October 2025)
**Modular**: 136 files, ~62,380 lines (January 2026)
**Features**: LLM item generation, ML validation, full combat, 5 crafting disciplines
**Last Updated**: 2026-01-27

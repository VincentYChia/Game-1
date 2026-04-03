# Game-1 Modular Architecture

**Last Updated**: 2026-03-29

This is the **modular refactored version** of Game-1, featuring a production-ready crafting RPG with **LLM-powered item generation**, **ML-based recipe validation**, and a **World Memory System** for Living World AI.

## Key Features

- 🎮 **239 Python files** (~96,400 lines of code)
- 🌍 **World Memory System** - 7-layer event tracking with 33 evaluators (SQLite)
- 🤖 **LLM Integration** - Claude API for procedural item generation
- 🧠 **ML Classifiers** - CNN + LightGBM for recipe validation
- ⚔️ **Full Combat System** - Damage pipeline, enchantments, hitboxes, projectiles
- 🛠️ **6 Crafting Disciplines** - Each with unique minigames (including Fishing)
- 💾 **Complete Save/Load** - Full state preservation

## Purpose

The modular architecture provides:
- **Better organization**: Find any system in seconds
- **Easier maintenance**: Isolated changes with minimal risk
- **Parallel development**: Multiple developers can work simultaneously
- **Scalable JSON production**: Clear data models with ML validation
- **Testing**: 24 test files with automated crafting tests + 56 WMS tests

## Architecture Overview

```
Game-1-modular/
├── main.py                          # Entry point (39 lines)
│
├── core/                            # Core game systems (23 files, ~18,764 LOC)
│   ├── config.py                    # Game configuration constants
│   ├── camera.py                    # Camera/viewport system
│   ├── game_engine.py               # Main game engine (10,809 lines)
│   ├── interactive_crafting.py      # 6 discipline crafting UIs (1,179 lines)
│   ├── effect_executor.py           # Tag-based combat effects (623 lines)
│   ├── difficulty_calculator.py     # Material-based difficulty (808 lines)
│   ├── reward_calculator.py         # Performance rewards (607 lines)
│   ├── tag_system.py                # Tag registry
│   ├── tag_parser.py                # Tag parsing
│   └── testing.py                   # Crafting system tester
│
├── data/                            # Data layer (30 files, ~5,424 LOC)
│   ├── models/                      # Pure data classes (dataclasses)
│   │   ├── materials.py, equipment.py, skills.py, recipes.py
│   │   ├── world.py, quests.py, npcs.py, titles.py, classes.py
│   │   └── resources.py, skill_unlocks.py, unlock_conditions.py
│   └── databases/                   # Singleton database loaders (16 files)
│       ├── material_db.py, equipment_db.py, skill_db.py
│       ├── recipe_db.py, placement_db.py, npc_db.py
│       ├── title_db.py, class_db.py, translation_db.py
│       └── skill_unlock_db.py, resource_node_db.py, visual_config_db.py, etc.
│
├── entities/                        # Game entities (17 files, ~7,263 LOC)
│   ├── character.py                 # Character class (2,593 lines)
│   ├── status_effect.py             # Status effects (826 lines)
│   └── components/                  # Character components
│       ├── skill_manager.py         # SkillManager (1,124 lines)
│       ├── stat_tracker.py          # SQL-backed player analytics (1,149 lines)
│       ├── inventory.py, equipment_manager.py, buffs.py
│       └── stats.py, leveling.py, activity_tracker.py, crafted_stats.py
│
├── systems/                         # Game system managers (21 files, ~10,631 LOC)
│   ├── world_system.py              # WorldSystem (generation, chunks)
│   ├── save_manager.py              # Full state persistence (634 lines)
│   ├── llm_item_generator.py        # LLM integration (1,392 lines)
│   ├── crafting_classifier.py       # ML classifiers (1,419 lines)
│   ├── title_system.py, class_system.py, quest_system.py
│   └── npc_system.py, dungeon.py, turret_system.py, etc.
│
├── world_system/                    # World Memory System (71 files, ~14,269 LOC)
│   ├── world_memory/                # Core WMS (stat_store, event_store, evaluators, tags)
│   ├── living_world/                # Consumer systems (backends, NPC, factions, ecosystem)
│   ├── config/                      # 7 JSON configs
│   ├── tests/                       # 56 passing tests
│   └── docs/                        # Canonical WMS design doc (1,864 lines)
│
├── events/                          # Event system (2 files, ~194 LOC)
│   └── event_bus.py                 # GameEventBus pub/sub
│
├── animation/                       # Animation system (7 files, ~1,008 LOC)
│   └── animation_manager.py, procedural.py, weapon_visuals.py, etc.
│
├── rendering/                       # All rendering code (5 files, ~8,841 LOC)
│   └── renderer.py                  # Renderer class (7,931 lines)
│
├── Combat/                          # Combat system (11 files, ~5,562 LOC)
│   ├── combat_manager.py            # CombatManager (2,317 lines)
│   ├── enemy.py                     # Enemy, EnemyDatabase (1,348 lines)
│   └── attack_state_machine.py, hitbox_system.py, projectile_system.py, etc.
│
├── Crafting-subdisciplines/         # Crafting minigames (9 files, ~8,994 LOC)
│   ├── smithing.py                  # Smithing minigame (909 lines)
│   ├── alchemy.py                   # Alchemy minigame (1,070 lines)
│   ├── refining.py                  # Refining minigame (826 lines)
│   ├── engineering.py               # Engineering minigame (1,312 lines)
│   ├── enchanting.py                # Enchanting minigame (1,408 lines)
│   ├── fishing.py                   # Fishing minigame (872 lines)
│   ├── crafting_simulator.py        # Crafting simulation (2,337 lines)
│   └── rarity_utils.py              # Shared rarity system
│
├── tests/                           # Test files (24 files, ~6,594 LOC)
│   └── test_*.py, crafting/, save/  # Unit and integration tests
│
├── tools/                           # Development tools (10 files)
│
├── assets/                          # Game assets (3,749 images)
│
└── [JSON Directories]               # Game data files (~90 files)
    ├── items.JSON/                  # Item definitions (57+ materials)
    ├── recipes.JSON/                # Crafting recipes (100+ recipes)
    ├── placements.JSON/             # Minigame grid layouts
    ├── Definitions.JSON/            # Game configuration, tags
    ├── progression/                 # Classes, titles, NPCs, quests
    └── Skills/                      # 100+ skill definitions
```

## Module Breakdown

### Core (`core/`) - 23 files, ~18,764 LOC
**Purpose**: Fundamental game systems

- **game_engine.py** (10,809 lines): Main game loop, event handling, UI, minigames
- **interactive_crafting.py** (1,179 lines): 6 discipline crafting UIs
- **effect_executor.py** (623 lines): Tag-based combat effect execution
- **difficulty_calculator.py** (808 lines): Material-based difficulty scaling
- **reward_calculator.py** (607 lines): Performance-based reward calculation
- **config.py**: Game constants (screen size, colors, speeds)
- **tag_system.py**: Tag registry and synergy system
- **testing.py**: Automated crafting system tests

### Data Layer (`data/`) - 30 files, ~5,424 LOC
**Purpose**: Clean separation between data models and business logic

**Models** (`data/models/`): Pure dataclasses (no logic)
- Materials, Equipment, Skills, Recipes, World, Quests, NPCs, Titles, Classes, Resources, SkillUnlocks

**Databases** (`data/databases/`): Singleton loaders for JSON files (16 files)
- Load from JSON, provide lookup methods, cache data

### Entities (`entities/`) - 17 files, ~7,263 LOC
**Purpose**: Game entities and their components

- **character.py** (2,593 lines): Player character integrating all components
- **status_effect.py** (826 lines): All status effect implementations
- **components/**: Pluggable character systems (stats, inventory, skills, etc.)
- **skill_manager.py** (1,124 lines): Skill activation, mana, cooldowns, affinity bonuses
- **stat_tracker.py** (1,149 lines): 65 SQL-backed recording methods for player analytics

### Systems (`systems/`) - 21 files, ~10,631 LOC
**Purpose**: Game system managers

- **llm_item_generator.py** (1,392 lines): Claude API integration for invented items
- **crafting_classifier.py** (1,419 lines): CNN + LightGBM recipe validation
- **save_manager.py** (634 lines): Full state persistence
- World generation, biomes, chunks, dungeons
- Quest, NPC, turret, encyclopedia systems
- Title and class systems

### World Memory System (`world_system/`) - 71 files, ~14,269 LOC
**Purpose**: 7-layer event tracking and Living World AI infrastructure

- **world_memory/**: Core WMS engine (StatStore, EventStore, evaluators, tags, triggers)
- **living_world/**: Consumer systems (BackendManager, NPC agents, factions, ecosystem)
- **config/**: 7 JSON configuration files
- **tests/**: 56 passing tests across 4 test files
- See `world_system/docs/HANDOFF_STATUS.md` for current state

### Rendering (`rendering/`) - 5 files, ~8,841 LOC
**Purpose**: All visual rendering

- **renderer.py** (7,931 lines): Complete rendering pipeline
  - World rendering (tiles, resources, stations, NPCs, enemies)
  - UI rendering (health, mana, buffs, notifications)
  - Inventory, equipment, skills, crafting interfaces

### Combat (`Combat/`) - 11 files, ~5,562 LOC
**Purpose**: Full combat system with damage pipeline

- **combat_manager.py** (2,317 lines): Damage pipeline, enchantments, status effects
- **enemy.py** (1,348 lines): Enemy AI, spawning, loot drops
- **attack_state_machine.py**: Phased attack states (IDLE→WINDUP→ACTIVE→RECOVERY)
- **hitbox_system.py**: Hitbox/hurtbox collision detection
- **projectile_system.py**: Projectile entities
- 14 enchantments fully integrated

### Crafting (`Crafting-subdisciplines/`) - 9 files, ~8,994 LOC
**Purpose**: 6 crafting disciplines with unique minigames

- **smithing.py** (909 lines): Hammer timing minigame
- **alchemy.py** (1,070 lines): Chain/stabilize reaction minigame
- **refining.py** (826 lines): Temperature control minigame
- **engineering.py** (1,312 lines): Wire puzzle minigame
- **enchanting.py** (1,408 lines): Spinning wheel minigame
- **fishing.py** (872 lines): Fishing minigame
- **crafting_simulator.py** (2,337 lines): Crafting simulation engine

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
├── llm_item_generator.py      # Claude API integration (1,392 lines)
└── crafting_classifier.py     # CNN + LightGBM validation (1,419 lines)

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
- **Total Files**: 239 Python files
- **Total Lines**: ~96,400 lines of code
- **Original**: 1 file (10,327 lines) - monolithic main.py
- **Modular**: 239 files with clean separation of concerns

### Largest Modules
1. **game_engine.py**: 10,809 lines (main loop, UI, event handling)
2. **renderer.py**: 7,931 lines (all rendering)
3. **character.py**: 2,593 lines (player entity)
4. **crafting_simulator.py**: 2,337 lines (crafting simulation)
5. **combat_manager.py**: 2,317 lines (damage pipeline, enchantments)
6. **enchanting.py**: 1,408 lines (enchanting minigame)
7. **llm_item_generator.py**: 1,392 lines (Claude API integration)
8. **crafting_classifier.py**: 1,419 lines (CNN + LightGBM)
9. **enemy.py**: 1,348 lines (enemy AI, spawning)
10. **engineering.py**: 1,312 lines (engineering minigame)

### Module Sizes
- **world_system/**: ~14,269 lines (71 files)
- **core/**: ~18,764 lines (23 files)
- **systems/**: ~10,631 lines (21 files)
- **Crafting-subdisciplines/**: ~8,994 lines (9 files)
- **rendering/**: ~8,841 lines (5 files)
- **entities/**: ~7,263 lines (17 files)
- **tests/**: ~6,594 lines (24 files)
- **Combat/**: ~5,562 lines (11 files)
- **data/**: ~5,424 lines (30 files)
- **animation/**: ~1,008 lines (7 files)

## Validation

All 239 Python files compile successfully:

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

### Game-1-modular (Current - March 2026)
```
Game-1-modular/
    239 Python files (~96,400 lines)
    Clean separation of concerns
    No circular dependencies
    World Memory System (7-layer event architecture)
    LLM-powered item generation
    ML-validated crafting system
    24 test files + 56 WMS tests
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
- 16 singleton database loaders
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
| **docs/GAME_MECHANICS_V6.md** | Master reference - all mechanics (5,154 lines) |
| **docs/REPOSITORY_STATUS_REPORT_2026-01-27.md** | Current system state |
| **.claude/CLAUDE.md** | Developer guide for AI assistants |
| **MASTER_ISSUE_TRACKER.md** | Known bugs and improvements |
| **docs/tag-system/TAG-GUIDE.md** | Comprehensive tag system guide |

---

**Original**: 10,327 lines in 1 file (October 2025)
**Modular**: 239 files, ~96,400 lines (March 2026)
**Features**: World Memory System, LLM item generation, ML validation, full combat, 6 crafting disciplines
**Last Updated**: 2026-03-29

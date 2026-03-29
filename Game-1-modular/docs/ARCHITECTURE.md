# Game-1-Modular Architecture Documentation

**Version**: 4.0 (Modular + LLM + World Memory System)
**Original Version**: 1.0 (10,327 lines, single file)
**Modular Version**: ~96,400 lines, 239 Python files
**Architecture Pattern**: Component-Based, Layered, Singleton Databases, Event-Driven
**Last Updated**: 2026-03-29

> **Note**: This document was largely written in January 2026. The header stats and major systems table have been updated, but some directory listings and line counts in lower sections may be outdated. For the most current architecture overview, see `.claude/CLAUDE.md` (v7.0).

---

## Table of Contents

1. [Overview](#overview)
2. [Design Principles](#design-principles)
3. [Directory Structure](#directory-structure)
4. [Layer Architecture](#layer-architecture)
5. [Component System](#component-system)
6. [Database Pattern](#database-pattern)
7. [Event Flow](#event-flow)
8. [Data Flow](#data-flow)
9. [Rendering Pipeline](#rendering-pipeline)
10. [File Organization Rules](#file-organization-rules)

---

## Overview

Game-1-Modular is a refactored version of a single-file Python/Pygame game (Game-1-singular) split into a maintainable, modular architecture. The refactoring preserves 100% feature parity while organizing code by responsibility and concern.

### Key Statistics

| Metric | Singular | Modular (Mar 2026) |
|--------|----------|---------|
| **Total Lines** | 10,327 | ~96,400 |
| **Files** | 1 | 239 |
| **Classes** | 62 | 200+ |
| **Avg Lines/File** | 10,327 | ~403 |
| **Import Depth** | N/A | Max 3 levels |
| **Circular Imports** | N/A | 0 |

### Major Systems (Line Counts)
| System | Lines | Key Files |
|--------|-------|-----------|
| Game Engine | 10,809 | `core/game_engine.py` |
| World Memory System | 14,269 | `world_system/` (71 files) |
| Crafting Minigames | 8,994 | `Crafting-subdisciplines/*.py` (9 files) |
| Rendering | 8,841 | `rendering/` (5 files) |
| Entities | 7,263 | `entities/` (17 files) |
| Combat | 5,562 | `Combat/` (11 files) |
| Core Systems | 18,764 | `core/` (23 files) |
| Systems | 10,631 | `systems/` (21 files) |
| Data Layer | 5,424 | `data/` (30 files) |
| Tests | 6,594 | `tests/` (24 files) |
| LLM Integration | 2,811 | `systems/llm_item_generator.py`, `crafting_classifier.py` |
| Animation | 1,008 | `animation/` (7 files) |
| Events | 194 | `events/event_bus.py` |

### Refactoring Benefits

✅ **Maintainability**: Each file has single, clear responsibility
✅ **Testability**: Components can be tested in isolation
✅ **Readability**: Navigate to specific features quickly
✅ **Scalability**: Add new systems without touching existing code
✅ **Collaboration**: Multiple developers can work on different modules
✅ **Debugging**: Easier to trace issues to specific modules

---

## Design Principles

### 1. Separation of Concerns
Each module has ONE clear responsibility:
- **Data models** define structure
- **Databases** manage collections
- **Components** add capabilities to entities
- **Systems** orchestrate game logic
- **Rendering** handles all visualization
- **Game engine** coordinates everything

### 2. Dependency Injection
```python
# Instead of:
class Character:
    def __init__(self):
        self.equipment_db = EquipmentDatabase.get_instance()  # Tight coupling

# We use:
class Character:
    def __init__(self, position):
        self.equipment = EquipmentManager()  # Component pattern
```

### 3. Composition Over Inheritance
```python
class Character:
    def __init__(self, start_position):
        # Character is COMPOSED of components
        self.stats = CharacterStats()
        self.leveling = LevelingSystem()
        self.skills = SkillManager()
        self.equipment = EquipmentManager()
        self.inventory = Inventory(30)
        # ... etc
```

### 4. Singleton Databases
All databases use singleton pattern for consistent state:
```python
class MaterialDatabase:
    _instance = None

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = MaterialDatabase()
        return cls._instance
```

### 5. Dataclasses for Models
Immutable, type-safe data structures:
```python
@dataclass
class Position:
    x: float
    y: float
    z: float = 0.0
```

### 6. No Circular Dependencies
Import hierarchy enforced:
```
core/config.py  (no game imports)
  ↓
data/models/    (import config only)
  ↓
data/databases/ (import models)
  ↓
entities/components/ (import databases)
  ↓
entities/ (import components)
  ↓
systems/ (import entities)
  ↓
rendering/ (import everything)
  ↓
core/game_engine.py (import everything)
```

---

## Directory Structure

> **Note**: This directory listing is from January 2026. For the current structure (including `world_system/`, `animation/`, `events/`, expanded `Combat/`), see `.claude/CLAUDE.md` or `README.md`.

```
Game-1-modular/
├── main.py                      # Entry point (~30 lines)
│
├── core/                        # Core game systems (23 files, 18,764 LOC)
│   ├── __init__.py
│   ├── config.py               # Global constants
│   ├── game_engine.py          # Main game loop (10,809 lines)
│   ├── interactive_crafting.py # 6 discipline crafting UIs (1,179 lines)
│   ├── effect_executor.py      # Tag-based combat effects (623 lines)
│   ├── difficulty_calculator.py # Material-based difficulty (808 lines)
│   ├── reward_calculator.py    # Performance rewards (607 lines)
│   ├── tag_system.py           # Tag registry
│   ├── tag_parser.py           # Tag parsing
│   └── testing.py              # Test framework
│
├── systems/                     # Game system managers (16 files, 5,856 LOC)
│   ├── world_system.py         # WorldSystem (generation, chunks)
│   ├── title_system.py         # TitleSystem
│   ├── class_system.py         # ClassSystem with tag bonuses
│   ├── llm_item_generator.py   # LLM integration (1,393 lines) - NEW
│   └── crafting_classifier.py  # ML classifiers (1,256 lines) - NEW
│
├── data/                        # All data structures
│   ├── __init__.py
│   ├── models/                 # Data models (dataclasses)
│   │   ├── __init__.py
│   │   ├── materials.py        # MaterialDefinition
│   │   ├── equipment.py        # EquipmentItem
│   │   ├── skills.py           # SkillDefinition, PlayerSkill
│   │   ├── recipes.py          # Recipe, PlacementData
│   │   ├── world.py            # Position, TileType, WorldTile, etc.
│   │   ├── titles.py           # TitleDefinition
│   │   ├── classes.py          # ClassDefinition
│   │   ├── npcs.py             # NPCDefinition
│   │   └── quests.py           # QuestObjective, QuestRewards, QuestDefinition
│   │
│   └── databases/              # Singleton data managers
│       ├── __init__.py
│       ├── material_db.py      # MaterialDatabase
│       ├── equipment_db.py     # EquipmentDatabase
│       ├── recipe_db.py        # RecipeDatabase
│       ├── skill_db.py         # SkillDatabase
│       ├── placement_db.py     # PlacementDatabase
│       ├── title_db.py         # TitleDatabase
│       ├── class_db.py         # ClassDatabase
│       ├── npc_db.py           # NPCDatabase
│       └── translation_db.py   # TranslationDatabase
│
├── entities/                    # Game entities
│   ├── __init__.py
│   ├── character.py            # Character class (740 lines)
│   ├── tool.py                 # Tool class
│   ├── damage_number.py        # DamageNumber class
│   │
│   └── components/             # Character components
│       ├── __init__.py
│       ├── inventory.py        # Inventory, ItemStack
│       ├── equipment_manager.py # EquipmentManager
│       ├── character_stats.py  # CharacterStats
│       ├── leveling_system.py  # LevelingSystem
│       ├── skill_manager.py    # SkillManager
│       ├── buff_manager.py     # BuffManager, ActiveBuff
│       └── activity_tracker.py # ActivityTracker
│
├── systems/                     # Game systems
│   ├── __init__.py
│   ├── world_system.py         # WorldSystem, NaturalResource
│   ├── combat_manager.py       # CombatManager, Enemy
│   ├── quest_system.py         # Quest, QuestManager
│   ├── encyclopedia.py         # Encyclopedia
│   ├── title_system.py         # TitleSystem
│   └── class_system.py         # ClassSystem
│
├── rendering/                   # All rendering code
│   ├── __init__.py
│   ├── renderer.py             # Renderer class (2,700 lines)
│   └── camera.py               # Camera class
│
├── Crafting-subdisciplines/    # Minigame modules (optional)
│   ├── smithing_crafter.py
│   ├── alchemy_crafter.py
│   ├── refining_crafter.py
│   ├── engineering_crafter.py
│   └── enchanting_crafter.py
│
├── items.JSON/                  # Item definitions
│   ├── items-materials-1.JSON
│   ├── items-smithing-1.JSON
│   ├── items-smithing-2.JSON
│   ├── items-tools-1.JSON
│   ├── items-alchemy-1.JSON
│   └── items-refining-1.JSON
│
├── recipes.JSON/                # Recipe definitions
│   ├── recipes-smithing-3.JSON
│   ├── recipes-alchemy-1.JSON
│   ├── recipes-refining-1.JSON
│   ├── recipes-engineering-1.JSON
│   └── recipes-enchanting-1.JSON
│
├── progression/                 # Progression data
│   ├── titles-1.JSON
│   ├── classes-1.JSON
│   ├── npcs-1.JSON
│   ├── npcs-enhanced.JSON
│   ├── quests-1.JSON
│   └── quests-enhanced.JSON
│
├── Skills/                      # Skill definitions
│   └── skills-skills-1.JSON
│
├── docs/                        # Documentation
│   ├── FEATURES_CHECKLIST.md
│   ├── ARCHITECTURE.md         # This file
│   ├── MODULE_REFERENCE.md
│   └── DEVELOPMENT_GUIDE.md
│
└── HOW_TO_RUN.md               # Quick start guide
```

---

## Layer Architecture

The codebase follows a strict layered architecture:

```
┌─────────────────────────────────────┐
│       main.py (Entry Point)         │  ← Starts game engine
└─────────────────────────────────────┘
                  ↓
┌─────────────────────────────────────┐
│    core/game_engine.py (Orchestrator)│  ← Coordinates all systems
│  - Init databases                    │  - Runs game loop
│  - Create world & character          │  - Handles input
│  - Run game loop                     │  - Delegates rendering
└─────────────────────────────────────┘
         ↓              ↓              ↓
┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│   Systems    │  │  Rendering   │  │   Entities   │
│              │  │              │  │              │
│ - World      │  │ - Renderer   │  │ - Character  │
│ - Combat     │  │ - Camera     │  │ - Enemy      │
│ - Quests     │  │              │  │ - Tool       │
│ - Encyclopedia│  │              │  │              │
└──────────────┘  └──────────────┘  └──────────────┘
         ↓              ↓              ↓
┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│  Components  │  │  Databases   │  │    Data      │
│              │  │              │  │   Models     │
│ - Inventory  │  │ - Material   │  │              │
│ - Equipment  │  │ - Equipment  │  │ - Position   │
│ - Skills     │  │ - Recipe     │  │ - ItemStack  │
│ - Stats      │  │ - Skill      │  │ - Recipe     │
│ - Leveling   │  │ - NPC        │  │ - Equipment  │
└──────────────┘  └──────────────┘  └──────────────┘
         ↓              ↓              ↓
┌─────────────────────────────────────┐
│        core/config.py (Constants)   │  ← No dependencies
└─────────────────────────────────────┘
```

### Layer Responsibilities

#### Layer 1: Entry Point
- **Files**: `main.py`
- **Responsibility**: Initialize and start game
- **Lines**: ~25
- **Dependencies**: Only `core.game_engine`

#### Layer 2: Game Engine
- **Files**: `core/game_engine.py`
- **Responsibility**: Orchestrate all systems, run game loop
- **Lines**: ~2,100
- **Dependencies**: Everything (top-level coordinator)

#### Layer 3: Systems & Rendering & Entities
- **Files**: `systems/*`, `rendering/*`, `entities/character.py`
- **Responsibility**: High-level game logic
- **Dependencies**: Components, databases, models

#### Layer 4: Components & Databases
- **Files**: `entities/components/*`, `data/databases/*`
- **Responsibility**: Reusable building blocks
- **Dependencies**: Models only

#### Layer 5: Data Models
- **Files**: `data/models/*`
- **Responsibility**: Data structures
- **Dependencies**: Config, type hints only

#### Layer 6: Configuration
- **Files**: `core/config.py`
- **Responsibility**: Global constants
- **Dependencies**: None

---

## Component System

The Character entity uses a **Component-Based Architecture**:

```python
class Character:
    def __init__(self, start_position: Position):
        # Core attributes
        self.position = start_position
        self.facing = "down"

        # Components (pluggable, reusable systems)
        self.stats = CharacterStats()              # Strength, defense, etc.
        self.leveling = LevelingSystem()           # XP, levels, stat points
        self.skills = SkillManager()               # Learned skills
        self.buffs = BuffManager()                 # Active buffs
        self.equipment = EquipmentManager()        # Equipped items
        self.inventory = Inventory(30)             # 30-slot inventory
        self.activities = ActivityTracker()        # Harvesting, combat counts
        self.encyclopedia = Encyclopedia()         # Discoveries
        self.quests = QuestManager()               # Active & completed quests
        self.titles = TitleSystem()                # Earned titles
        self.class_system = ClassSystem()          # Current class

        # ... initialization continues
```

### Component Benefits

1. **Modularity**: Each component is self-contained
2. **Testability**: Test components independently
3. **Reusability**: Components can be reused on other entities (NPCs, enemies)
4. **Extensibility**: Add new components without modifying Character
5. **Composition**: Mix and match capabilities

### Component Pattern

```python
# Component Interface (implicit duck typing)
class Component:
    def update(self, delta_time: float): pass
    def reset(self): pass

# Example Component
class SkillManager:
    def __init__(self):
        self.learned_skills: Dict[str, PlayerSkill] = {}
        self.active_slots: List[Optional[str]] = [None] * 5

    def learn_skill(self, skill_id: str, ...) -> bool:
        # Skill learning logic
        pass

    def activate_skill(self, slot: int, character) -> bool:
        # Skill activation logic
        pass
```

---

## Database Pattern

All databases follow the **Singleton Pattern** to ensure one shared instance:

```python
class MaterialDatabase:
    """Singleton database managing all materials"""
    _instance = None

    def __init__(self):
        self.materials: Dict[str, MaterialDefinition] = {}
        self.loaded = False

    @classmethod
    def get_instance(cls):
        """Get or create singleton instance"""
        if cls._instance is None:
            cls._instance = MaterialDatabase()
        return cls._instance

    def load_from_file(self, filepath: str):
        """Load materials from JSON file"""
        with open(filepath, 'r') as f:
            data = json.load(f)
        # ... parsing logic
        self.loaded = True

    def get_material(self, item_id: str) -> Optional[MaterialDefinition]:
        """Lookup material by ID"""
        return self.materials.get(item_id)
```

### Database Responsibilities

| Database | Contents | File Count |
|----------|----------|------------|
| **MaterialDatabase** | All materials (ores, logs, consumables) | 1 |
| **EquipmentDatabase** | All equipment (weapons, armor, tools) | 3 |
| **RecipeDatabase** | All crafting recipes | 5 |
| **SkillDatabase** | All skill definitions | 1 |
| **TitleDatabase** | All title definitions | 1 |
| **ClassDatabase** | All class definitions | 1 |
| **NPCDatabase** | All NPCs and quests | 2 |
| **PlacementDatabase** | Grid-based crafting layouts | 1 |
| **TranslationDatabase** | Multi-language text | Multiple |

### Database Initialization

Databases are initialized in `GameEngine.__init__()`:

```python
class GameEngine:
    def __init__(self):
        # Load databases in dependency order
        MaterialDatabase.get_instance().load_from_file("items.JSON/items-materials-1.JSON")

        equip_db = EquipmentDatabase.get_instance()
        equip_db.load_from_file("items.JSON/items-smithing-1.JSON")
        equip_db.load_from_file("items.JSON/items-smithing-2.JSON")
        equip_db.load_from_file("items.JSON/items-tools-1.JSON")

        RecipeDatabase.get_instance().load_from_files()
        SkillDatabase.get_instance().load_from_file()

        TitleDatabase.get_instance().load_from_file("progression/titles-1.JSON")
        ClassDatabase.get_instance().load_from_file("progression/classes-1.JSON")
        NPCDatabase.get_instance().load_from_files()
```

---

## Event Flow

### Input Processing

```
┌─────────────────┐
│   User Input    │  ← Keyboard/Mouse events
│  (Pygame events)│
└────────┬────────┘
         ↓
┌─────────────────┐
│  GameEngine     │
│ .handle_events()│  ← Process pygame events
└────────┬────────┘
         ↓
    ┌────┴────┬────────────┬──────────────┐
    ↓         ↓            ↓              ↓
┌────────┐ ┌────────┐ ┌────────────┐ ┌────────────┐
│  Menu  │ │  UI    │ │   World    │ │  Minigame  │
│ Events │ │ Events │ │ Interaction│ │   Events   │
└────────┘ └────────┘ └────────────┘ └────────────┘
```

### Event Handler Priority

1. **Start Menu** (if open)
2. **Minigame** (if active)
3. **Modal UIs** (enchantment, class selection)
4. **Window UIs** (skills, equipment, stats, encyclopedia)
5. **Crafting UI** (if at station)
6. **Inventory** (always visible bottom panel)
7. **World Interactions** (movement, harvesting, combat)

### Mouse Click Flow

```python
def handle_mouse_click(self, mouse_pos: Tuple[int, int]):
    # Priority-based event handling

    # 1. Start menu (blocks all other input)
    if self.start_menu_open:
        self.handle_start_menu_selection(...)
        return

    # 2. Minigame (blocks world interaction)
    if self.active_minigame:
        self.handle_minigame_click(...)
        return

    # 3. Modal dialogs
    if self.enchantment_selection_active:
        self.handle_enchantment_selection_click(...)
        return

    # 4. Window UIs (click inside = handle, click outside = close)
    if self.character.skills_ui_open:
        if self.skills_window_rect.collidepoint(mouse_pos):
            self.handle_skills_menu_click(...)
        else:
            self.character.toggle_skills_ui()
        return

    # 5. Crafting UI
    if self.character.crafting_ui_open:
        self.handle_craft_click(...)
        return

    # 6. Inventory (always active)
    if mouse_pos[1] >= Config.INVENTORY_PANEL_Y:
        # Handle inventory clicks (drag, equip, use)
        return

    # 7. World interactions
    # Click on enemies, resources, NPCs, stations, or ground movement
```

---

## Data Flow

### Character Stat Recalculation

```
┌──────────────────────────────────────────────────┐
│         Stat Modification Trigger                │
│  (equip item, level up, gain title, etc.)       │
└───────────────────┬──────────────────────────────┘
                    ↓
┌──────────────────────────────────────────────────┐
│    character.recalculate_stats()                 │
│    1. Start with base stats                      │
│    2. Add leveling bonuses                       │
│    3. Add equipment bonuses                      │
│    4. Add title bonuses                          │
│    5. Apply class multipliers                    │
│    6. Calculate derived stats (max HP/mana)      │
└───────────────────┬──────────────────────────────┘
                    ↓
┌──────────────────────────────────────────────────┐
│         Updated Character Stats                  │
│  - Final strength, defense, vitality, etc.       │
│  - Max health, max mana                          │
│  - Effective combat stats                        │
└──────────────────────────────────────────────────┘
```

### Crafting Flow

```
┌──────────────────┐
│  User selects    │
│  recipe & clicks │
│   CRAFT button   │
└────────┬─────────┘
         ↓
┌──────────────────┐     NO     ┌──────────────────┐
│ Has materials?   │ ─────────→ │ Show "Need more  │
└────────┬─────────┘             │   materials"     │
         │ YES                   └──────────────────┘
         ↓
┌──────────────────┐     NO     ┌──────────────────┐
│ Has minigame?    │ ─────────→ │ Instant craft    │
└────────┬─────────┘             │ - Consume mats   │
         │ YES                   │ - Create item    │
         ↓                       └──────────────────┘
┌──────────────────┐
│ Start minigame   │
│ - Consume mats   │
│ - Init state     │
└────────┬─────────┘
         ↓
┌──────────────────┐
│ User plays       │
│ minigame         │
└────────┬─────────┘
         ↓
┌──────────────────┐     FAIL   ┌──────────────────┐
│ Minigame result  │ ─────────→ │ No item created  │
└────────┬─────────┘             │ (mats consumed!) │
         │ SUCCESS               └──────────────────┘
         ↓
┌──────────────────┐
│ Create item      │
│ + bonus from     │
│   performance    │
└──────────────────┘
```

### Quest Completion Flow

```
┌──────────────────┐
│  User interacts  │
│    with NPC      │
└────────┬─────────┘
         ↓
┌──────────────────┐     NO     ┌──────────────────┐
│ Has complete     │ ─────────→ │ Show dialogue    │
│   quest?         │             │ or new quests    │
└────────┬─────────┘             └──────────────────┘
         │ YES
         ↓
┌──────────────────┐     NO     ┌──────────────────┐
│ Quest objectives │ ─────────→ │ "Not done yet"   │
│   complete?      │             └──────────────────┘
└────────┬─────────┘
         │ YES
         ↓
┌──────────────────┐
│ Consume items    │  ← For gather quests
│ (if gather quest)│
└────────┬─────────┘
         ↓
┌──────────────────┐
│ Grant rewards:   │
│ - XP             │
│ - Items          │
│ - Skills         │
│ - Titles         │
│ - Health/Mana    │
└────────┬─────────┘
         ↓
┌──────────────────┐
│ Mark complete    │
│ Show notification│
└──────────────────┘
```

---

## Rendering Pipeline

### Frame Rendering Order

```
render() called every frame (60 FPS)
│
├─ 1. Clear screen (black background)
│
├─ 2. Render world (via Renderer)
│   ├─ Visible tiles (grass, stone, water)
│   ├─ Grid lines
│   ├─ Resources (trees, nodes) with health bars
│   └─ Crafting stations
│
├─ 3. Render entities (via Renderer)
│   ├─ Character with facing indicator
│   ├─ Interaction range circle
│   ├─ Enemies with health bars
│   └─ NPCs with quest indicators (!/?/✓)
│
├─ 4. Render UI panels (via Renderer)
│   ├─ HUD (health, mana, XP bars, level, position, FPS)
│   ├─ Inventory panel (bottom, always visible)
│   ├─ Stats UI (if open)
│   ├─ Equipment UI (if open)
│   ├─ Skills UI (if open)
│   ├─ Encyclopedia UI (if open)
│   ├─ Crafting UI (if at station)
│   ├─ Class selection UI (if open)
│   └─ NPC dialogue UI (if talking to NPC)
│
├─ 5. Render effects (via Renderer & GameEngine)
│   ├─ Damage numbers (floating, fading)
│   ├─ Notifications (top-center, fading)
│   └─ Tooltips (mouse hover)
│
├─ 6. Render minigame (if active, via GameEngine)
│   ├─ Minigame-specific UI
│   └─ Game state visualization
│
├─ 7. Render start menu (if open, via Renderer)
│   ├─ Menu background
│   ├─ Title
│   └─ Menu buttons
│
└─ 8. pygame.display.flip() - Show frame
```

### Camera System

```python
class Camera:
    def __init__(self, viewport_width: int, viewport_height: int):
        self.x = 0.0  # Camera center X (world coords)
        self.y = 0.0  # Camera center Y (world coords)
        self.viewport_width = viewport_width
        self.viewport_height = viewport_height

    def center_on(self, world_x: float, world_y: float):
        """Center camera on world position"""
        self.x = world_x
        self.y = world_y

    def world_to_screen(self, world_x: float, world_y: float) -> Tuple[int, int]:
        """Convert world coordinates to screen coordinates"""
        screen_x = (world_x - self.x) * Config.TILE_SIZE + self.viewport_width // 2
        screen_y = (world_y - self.y) * Config.TILE_SIZE + self.viewport_height // 2
        return (int(screen_x), int(screen_y))
```

---

## File Organization Rules

### Naming Conventions

1. **Files**: `snake_case.py` (e.g., `character_stats.py`)
2. **Classes**: `PascalCase` (e.g., `CharacterStats`)
3. **Functions**: `snake_case` (e.g., `calculate_damage`)
4. **Constants**: `UPPER_SNAKE_CASE` (e.g., `MAX_LEVEL`)
5. **Private**: `_leading_underscore` (e.g., `_internal_method`)

### File Size Guidelines

- **Ideal**: < 300 lines
- **Warning**: > 500 lines (consider splitting)
- **Maximum**: < 1,000 lines (except game_engine.py, renderer.py)

### Import Order

```python
# 1. Standard library
import json
import os
from pathlib import Path
from typing import Dict, List, Optional

# 2. Third-party
import pygame

# 3. Local - absolute imports only
from core.config import Config
from data.models import Position, Recipe
from data.databases import MaterialDatabase
```

### Module Structure

Every module should have:

```python
"""Module docstring explaining purpose"""

# Imports

# Constants (if any)

# Classes/Functions

# If standalone script:
if __name__ == "__main__":
    # Test/demo code
```

---

## Summary

The modular architecture achieves:

✅ **Clear separation** of data, logic, and presentation
✅ **No circular dependencies** through careful layering
✅ **Easy navigation** - find features by directory structure
✅ **Testable components** - test in isolation
✅ **Singleton databases** - consistent state management
✅ **Component-based characters** - mix and match capabilities
✅ **100% feature parity** with original singular version

**Next Steps**: See `MODULE_REFERENCE.md` for detailed per-file documentation and `DEVELOPMENT_GUIDE.md` for contribution guidelines.

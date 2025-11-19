# Core Module

This module contains the core game engine and supporting systems.

## Files

### game_engine.py (2,733 lines, 127KB)
**The main game engine** - orchestrates all game systems.

**Class**: `GameEngine` (46 methods)

**Key Responsibilities**:
- Initialize pygame and all game systems
- Load all databases (Materials, Equipment, Skills, Recipes, NPCs, etc.)
- Manage game loop (events → update → render)
- Handle all user input (keyboard, mouse, wheel)
- Coordinate between all subsystems (World, Character, Combat, Crafting, NPCs)
- Manage game states (Start Menu, Playing, Crafting, UI Windows, Dialogue)
- Render game graphics (delegates to Renderer)

**Critical Methods**:
- `__init__`: Initialize everything (189 lines)
- `run`: Main game loop
- `handle_events`: Process all input events (300+ lines)
- `handle_mouse_click`: Handle mouse clicks (230+ lines)
- `update`: Update all game systems
- `render`: Render all graphics

**Crafting Integration**:
- Supports 5 crafting minigames (smithing, refining, alchemy, engineering, enchanting)
- Material placement validation
- Minigame state management
- Recipe browsing and crafting

**Import Structure**:
```python
from core import GameEngine

game = GameEngine()
game.run()
```

### testing.py (195 lines, 7.6KB)
**Automated testing framework** for the crafting system.

**Class**: `CraftingSystemTester` (8 methods)

**Purpose**: Validate crafting system integrity through automated tests.

**Test Coverage**:
- Database initialization
- Recipe loading for all disciplines
- Recipe tier sorting
- Placement data loading
- State initialization
- UI rendering methods

**Usage**:
```python
tester = CraftingSystemTester(game_engine)
success = tester.run_all_tests()  # Returns True if all tests pass
```

Press F10 in-game to run the test suite.

### config.py (75 lines, 2.1KB)
**Game configuration** - all constants and settings.

**Class**: `Config`

Contains:
- Screen dimensions and FPS
- World generation parameters
- UI layout constants
- Character movement settings
- Color definitions
- Rarity colors

### camera.py (22 lines, 788 bytes)
**Camera system** for viewport management.

**Class**: `Camera`

Handles:
- Viewport positioning
- Camera centering on player
- World-to-screen coordinate conversion

### notifications.py (18 lines, 485 bytes)
**Notification system** for in-game messages.

**Class**: `Notification`

Features:
- Timed notifications (fade-out)
- Colored messages
- Screen positioning

## Dependencies

The core module depends on:
- **pygame**: For graphics and input
- **entities**: Character, DamageNumber
- **data**: All database classes and models
- **systems**: WorldSystem, NPC
- **rendering**: Renderer
- **Combat**: CombatManager (from Combat/)
- **Crafting-subdisciplines**: 5 crafting minigames (optional)

## Module Exports

From `core/__init__.py`:
```python
from core import (
    Config,
    Notification,
    Camera,
    CraftingSystemTester,
    GameEngine
)
```

## Integration

The GameEngine is the **heart of the game** - it:
1. Initializes ALL other systems
2. Coordinates communication between systems
3. Manages the game loop
4. Handles ALL user input
5. Orchestrates rendering

Every other module is initialized and used by the GameEngine.

## Game Flow

```
GameEngine.__init__()
  ├─ Load all databases
  ├─ Initialize Combat system
  ├─ Initialize Crafting subdisciplines
  ├─ Create WorldSystem
  ├─ Create Character (after menu selection)
  ├─ Spawn NPCs
  └─ Initialize Renderer

GameEngine.run()
  └─ Game Loop:
       ├─ handle_events() → Process input
       ├─ update() → Update game state
       ├─ render() → Draw everything
       └─ clock.tick(60) → Maintain FPS
```

## File Size Breakdown

| File | Lines | Size | Purpose |
|------|-------|------|---------|
| game_engine.py | 2,733 | 127KB | Main game engine |
| testing.py | 195 | 7.6KB | Test framework |
| config.py | 75 | 2.1KB | Configuration |
| camera.py | 22 | 788B | Camera system |
| notifications.py | 18 | 485B | Notifications |
| __init__.py | 9 | 292B | Module exports |
| **TOTAL** | **3,052** | **138KB** | **Core module** |

## Notes

- The GameEngine is **CRITICAL** - any changes must be carefully tested
- The class is massive (2,733 lines) because it orchestrates everything
- Input handling is complex (handles keyboard, mouse, wheel, double-clicks)
- Supports multiple game states and UI windows simultaneously
- Crafting subdisciplines are optional (graceful fallback if not available)
- Extensive debug features (F1-F10 keys) for development

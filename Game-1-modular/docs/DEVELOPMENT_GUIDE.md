# Development Guide

Guide for developers working on or extending Game-1-Modular.

**Audience**: Contributors, maintainers, future developers
**Last Updated**: 2026-01-27

---

## Table of Contents

1. [Getting Started](#getting-started)
2. [Project Structure](#project-structure)
3. [Development Workflow](#development-workflow)
4. [Coding Standards](#coding-standards)
5. [Adding New Features](#adding-new-features)
6. [Common Tasks](#common-tasks)
7. [Debugging Guide](#debugging-guide)
8. [Testing](#testing)
9. [Performance Optimization](#performance-optimization)
10. [Troubleshooting](#troubleshooting)

---

## Getting Started

### Prerequisites

```bash
# Required
Python 3.8+
pygame 2.0+

# For LLM features (NEW - January 2026)
anthropic   # Claude API client
numpy       # ML preprocessing
pillow      # Image processing for CNN

# For ML classifiers
onnxruntime # CNN model inference
lightgbm    # LightGBM classifiers

# Optional (for development tools)
pytest      # Testing framework (13 test files exist)
pylint      # Code quality checks
```

### Environment Variables

```bash
# Required for LLM item generation
export ANTHROPIC_API_KEY="sk-ant-..."

# Or create .env file in Game-1-modular/
echo "ANTHROPIC_API_KEY=sk-ant-..." > .env
```

**Note**: Without API key, LLM features gracefully degrade to MockBackend.

### Setup

```bash
# Clone repository
cd Game-1/Game-1-modular

# Install dependencies
pip install pygame

# Test imports
python verify_imports.py

# Run game
python main.py
```

### First Run

1. Select "New World" from start menu
2. Use WASD to move, mouse to interact
3. Press F1 for debug mode (infinite materials)
4. Press L for Encyclopedia (game guide)

---

## Project Structure

### Directory Organization

```
Game-1-modular/
├── core/                  # Core game engine (23 files, ~15,589 LOC)
├── data/                  # Data models and databases (25 files)
├── entities/              # Game entities and components (17 files)
├── systems/               # Game systems including LLM (16 files)
│   ├── llm_item_generator.py    # Claude API integration (1,393 lines)
│   └── crafting_classifier.py   # ML classifiers (1,256 lines)
├── rendering/             # All rendering code (3 files)
├── Combat/                # Combat system (3 files, ~2,527 LOC)
├── Crafting-subdisciplines/  # Minigames (8 files, ~5,346 LOC)
├── tests/                 # Test files (13 files)
├── assets/                # Game assets (icons, sprites)
├── docs/                  # Documentation (you are here)
├── items.JSON/            # Item definitions (57+ materials)
├── recipes.JSON/          # Crafting recipes (100+ recipes)
├── placements.JSON/       # Minigame grid layouts
├── Definitions.JSON/      # Game config, tags
├── progression/           # Classes, titles, NPCs
├── Skills/                # 100+ skill definitions
├── save_system/           # Save/load system
└── llm_debug_logs/        # LLM API debug logs (auto-created)
```

### Import Hierarchy

```
main.py
  ↓
core/game_engine.py
  ↓
rendering/renderer.py, systems/*, entities/character.py
  ↓
entities/components/*, data/databases/*
  ↓
data/models/*
  ↓
core/config.py
```

**Rule**: Lower layers can't import from higher layers (prevents circular imports).

---

## Development Workflow

### Branching Strategy

```bash
# Main branch: stable releases
# Development branch: active development
# Feature branches: new features

git checkout -b feature/your-feature-name
# ... make changes ...
git commit -m "Add feature X"
git push origin feature/your-feature-name
# Create pull request
```

### Code Review Checklist

Before submitting PR:
- [ ] Code follows style guide
- [ ] No circular imports
- [ ] Docstrings added/updated
- [ ] No print() for debugging (use logging if needed)
- [ ] Tested manually
- [ ] No pygame warnings/errors
- [ ] Documentation updated if needed

---

## Coding Standards

### Python Style

Follow PEP 8 with these specifics:

```python
# Naming conventions
ClassName        # Classes: PascalCase
function_name    # Functions: snake_case
CONSTANT_NAME    # Constants: UPPER_SNAKE_CASE
_private_method  # Private: leading underscore

# Line length
Max 100 characters (120 acceptable for complex lines)

# Imports
# 1. Standard library
import json
from typing import Dict, List

# 2. Third-party
import pygame

# 3. Local (absolute imports only)
from core.config import Config
from data.models import Position
```

### Docstrings

```python
def function_name(param1: int, param2: str) -> bool:
    """
    Brief description of function (one line).

    Longer description if needed. Explain what the function does,
    not how it does it.

    Args:
        param1: Description of param1
        param2: Description of param2

    Returns:
        Description of return value

    Raises:
        ValueError: When param1 < 0
    """
    pass
```

### Type Hints

Use type hints for all function signatures:

```python
# Good
def calculate_damage(base: int, multiplier: float) -> int:
    return int(base * multiplier)

# Bad
def calculate_damage(base, multiplier):
    return int(base * multiplier)
```

### Error Handling

```python
# Fail gracefully with user-friendly messages
try:
    data = json.load(f)
except FileNotFoundError:
    print(f"⚠️  File not found: {filepath}")
    self._create_placeholders()  # Fallback
except json.JSONDecodeError as e:
    print(f"⚠️  Invalid JSON in {filepath}: {e}")
    return False
```

---

## Adding New Features

### Adding a New Item Type

**Example**: Adding "Accessories" (rings, necklaces)

#### 1. Update Data Model

```python
# data/models/equipment.py
# No changes needed - EquipmentItem already supports any slot

# core/config.py
# Add color constant if needed
COLOR_ACCESSORY = (150, 100, 255)
```

#### 2. Update Database

```python
# data/databases/equipment_db.py
# No changes needed - load_from_file() already handles all equipment
```

#### 3. Update Character

```python
# entities/components/equipment_manager.py
def __init__(self):
    self.slots = {
        # ... existing slots ...
        'accessory': None,  # Already exists
        'ring1': None,      # Add new slots
        'ring2': None,
    }
```

#### 4. Update Rendering

```python
# rendering/renderer.py
def render_equipment_ui(self, character):
    # Add rendering for new slots
    ring1_rect = pygame.Rect(x, y, slot_size, slot_size)
    # ... render ring1 slot ...
```

#### 5. Add JSON Data

```json
// items.JSON/items-accessories-1.JSON
{
  "metadata": {
    "version": "1.0",
    "category": "accessories"
  },
  "accessories": [
    {
      "itemId": "copper_ring",
      "name": "Copper Ring",
      "category": "equipment",
      "type": "accessory",
      "slot": "ring1",
      "tier": 1,
      "rarity": "common",
      "stats": {
        "bonuses": {"luck": 2}
      }
    }
  ]
}
```

#### 6. Test

```python
# Test in-game:
# 1. Load game with F6
# 2. Open Equipment UI (E key)
# 3. Verify new slots appear
# 4. Craft accessory and equip it
# 5. Check stats are applied
```

---

### Adding a New System

**Example**: Adding a "Fishing" system

#### 1. Create System Module

```python
# systems/fishing_system.py
from data.models import Position
from typing import Optional

class FishingSpot:
    def __init__(self, position: Position, fish_types: List[str]):
        self.position = position
        self.fish_types = fish_types
        self.cooldown = 0.0

class FishingSystem:
    def __init__(self):
        self.fishing_spots: List[FishingSpot] = []
        self.is_fishing = False
        self.current_spot: Optional[FishingSpot] = None

    def start_fishing(self, character, spot: FishingSpot) -> bool:
        """Start fishing at spot"""
        if not character.inventory.has_item("fishing_rod"):
            return False
        self.is_fishing = True
        self.current_spot = spot
        return True

    def update(self, delta_time: float, character):
        """Update fishing progress"""
        if self.is_fishing:
            self.current_spot.cooldown += delta_time
            if self.current_spot.cooldown >= 3.0:  # 3 seconds
                self.catch_fish(character)

    def catch_fish(self, character):
        """Catch a random fish"""
        fish_id = random.choice(self.current_spot.fish_types)
        character.inventory.add_item(fish_id, 1)
        self.is_fishing = False
        self.current_spot.cooldown = 0.0
```

#### 2. Integrate with Game Engine

```python
# core/game_engine.py
from systems.fishing_system import FishingSystem

class GameEngine:
    def __init__(self):
        # ... existing init ...
        self.fishing_system = FishingSystem()
        # Spawn fishing spots
        self.fishing_system.fishing_spots = [
            FishingSpot(Position(10, 10), ["salmon", "trout"]),
            FishingSpot(Position(50, 50), ["bass", "carp"]),
        ]

    def update(self, delta_time: float):
        # ... existing updates ...
        self.fishing_system.update(delta_time, self.character)

    def handle_mouse_click(self, mouse_pos):
        # ... existing click handlers ...

        # Check fishing spot clicks
        for spot in self.fishing_system.fishing_spots:
            screen_pos = self.camera.world_to_screen(spot.position.x, spot.position.y)
            if distance(mouse_pos, screen_pos) < 20:
                success = self.fishing_system.start_fishing(self.character, spot)
                if success:
                    self.add_notification("Started fishing!", (100, 255, 100))
                else:
                    self.add_notification("Need fishing rod!", (255, 100, 100))
                return
```

#### 3. Add Rendering

```python
# rendering/renderer.py
def render_fishing_spots(self, fishing_system: FishingSystem, camera):
    """Render fishing spots on world"""
    for spot in fishing_system.fishing_spots:
        screen_x, screen_y = camera.world_to_screen(spot.position.x, spot.position.y)
        # Draw water ripple circle
        pygame.draw.circle(self.screen, (100, 150, 255), (screen_x, screen_y), 10, 2)

        # Draw "FISHING" text if active
        if fishing_system.is_fishing and fishing_system.current_spot == spot:
            text = self.small_font.render("FISHING...", True, (255, 255, 255))
            self.screen.blit(text, (screen_x - 30, screen_y - 30))
```

---

## LLM Integration (NEW - January 2026)

### Overview

Players can **invent new items** by placing materials in unique arrangements:
1. ML classifiers validate the placement
2. Claude API generates item definitions
3. Items are added to inventory
4. Invented recipes are persisted

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

### Debugging LLM Issues

1. Check API key is set: `echo $ANTHROPIC_API_KEY`
2. Review debug logs in `llm_debug_logs/`
3. Test with MockBackend (works without API)

### Adding New Classifier

```python
# systems/crafting_classifier.py
class NewDisciplineLightGBM:
    def __init__(self):
        self.model = lightgbm.Booster(model_file="path/to/model.txt")

    def extract_features(self, placement: Dict) -> np.ndarray:
        """Extract features from placement grid."""
        # Define your feature extraction logic
        pass

    def predict(self, features: np.ndarray) -> Tuple[bool, float]:
        """Run inference, return (is_valid, confidence)."""
        prediction = self.model.predict(features)
        is_valid = prediction[0] > 0.5
        confidence = prediction[0]
        return is_valid, confidence
```

### Modifying LLM Prompts

Edit files in `Scaled JSON Development/LLM Training Data/Fewshot_llm/`:
- `system_prompts/` - System instructions per discipline
- `examples/` - Few-shot examples for each discipline

See `MANUAL_TUNING_GUIDE.md` for detailed editing instructions.

---

## Common Tasks

### Adding a New Stat

**Example**: Adding "critical_damage" stat

#### 1. Add to CharacterStats

```python
# entities/components/stats.py
class CharacterStats:
    # ... existing stats ...
    critical_damage: float = 1.5  # 150% damage on crit
```

#### 2. Use in Combat

```python
# In combat calculation:
if is_critical:
    damage *= character.stats.critical_damage
```

#### 3. Allow Equipment Bonuses

```python
# Equipment can now have:
{
  "bonuses": {
    "critical_damage": 0.2  # +20% crit damage
  }
}
```

---

### Adding a New Recipe Discipline

**Example**: Adding "Cooking" discipline

#### 1. Add Enum Value

```python
# data/models/world.py
class StationType(Enum):
    # ... existing ...
    COOKING = "cooking"
```

#### 2. Create Recipes

```json
// recipes.JSON/recipes-cooking-1.JSON
{
  "metadata": {
    "version": "1.0",
    "discipline": "cooking"
  },
  "recipes": [
    {
      "recipeId": "cooking_fish_stew",
      "outputId": "fish_stew",
      "outputQuantity": 1,
      "discipline": "cooking",
      "tier": 1,
      "inputs": [
        {"materialId": "salmon", "quantity": 2},
        {"materialId": "carrot", "quantity": 3}
      ],
      "baseCraftTime": 5.0
    }
  ]
}
```

#### 3. Create Minigame (Optional)

```python
# Crafting-subdisciplines/cooking.py
class CookingMinigame:
    """Cooking minigame - temperature + timing"""
    pass
```

#### 4. Update Recipe Database

```python
# data/databases/recipe_db.py
def load_from_files(self):
    files = [
        # ... existing ...
        "recipes.JSON/recipes-cooking-1.JSON",
    ]
```

---

### Adding a New UI Window

**Example**: Adding a "Map" UI window

#### 1. Add Character State

```python
# entities/character.py
class Character:
    def __init__(self, start_position):
        # ... existing ...
        self.map_ui_open = False

    def toggle_map_ui(self):
        self.map_ui_open = not self.map_ui_open
```

#### 2. Add Key Binding

```python
# core/game_engine.py
def handle_events(self):
    for event in pygame.event.get():
        if event.type == pygame.KEYDOWN:
            # ... existing keys ...
            if event.key == pygame.K_m:
                self.character.toggle_map_ui()
```

#### 3. Add Rendering

```python
# rendering/renderer.py
def render_map_ui(self, character, world):
    """Render map window"""
    if not character.map_ui_open:
        return

    # Window
    map_rect = pygame.Rect(200, 100, 800, 600)
    pygame.draw.rect(self.screen, Config.COLOR_UI_BG, map_rect)
    pygame.draw.rect(self.screen, (200, 200, 200), map_rect, 2)

    # Title
    title = self.font.render("MAP", True, (255, 255, 255))
    self.screen.blit(title, (map_rect.x + 10, map_rect.y + 10))

    # Draw minimap
    tile_size = 5  # Each world tile = 5 pixels on map
    for (x, y), tile in world.tiles.items():
        map_x = map_rect.x + 50 + x * tile_size
        map_y = map_rect.y + 50 + y * tile_size
        color = self._get_tile_color(tile.tile_type)
        pygame.draw.rect(self.screen, color, (map_x, map_y, tile_size, tile_size))

    # Draw player position
    player_x = map_rect.x + 50 + int(character.position.x * tile_size)
    player_y = map_rect.y + 50 + int(character.position.y * tile_size)
    pygame.draw.circle(self.screen, Config.COLOR_PLAYER, (player_x, player_y), 3)
```

#### 4. Add Click Handler

```python
# core/game_engine.py
def handle_mouse_click(self, mouse_pos):
    # ... priority order ...

    # Map UI
    if self.character.map_ui_open and self.map_window_rect:
        if self.map_window_rect.collidepoint(mouse_pos):
            # Handle map clicks
            return
        else:
            self.character.toggle_map_ui()
            return
```

---

## Debugging Guide

### Common Debugging Techniques

#### 1. Print Debug Info

```python
# Use descriptive prefixes
print(f"🎯 Attempting to equip: {item_id}")
print(f"✅ Successfully equipped")
print(f"❌ Failed to equip: {reason}")
print(f"⚠️  Warning: {issue}")
```

#### 2. Debug Mode (F1)

```python
# core/config.py
DEBUG_INFINITE_RESOURCES = False  # Toggle with F1

# Use in code:
if Config.DEBUG_INFINITE_RESOURCES:
    return True  # Skip resource checks
```

#### 3. Visual Debugging

```python
# rendering/renderer.py
def render_debug_info(self, character, world):
    """Draw debug overlays"""
    if not Config.DEBUG_MODE:
        return

    # Draw collision boxes
    # Draw interaction ranges
    # Draw pathfinding nodes
    # Show internal state
```

#### 4. Breakpoint Debugging

```python
# Insert breakpoint
import pdb; pdb.set_trace()

# Or use IDE breakpoints (VSCode, PyCharm)
```

### Common Issues

#### Issue: Import Errors

```
ModuleNotFoundError: No module named 'core'
```

**Solution**: Run from project root, ensure sys.path setup in main.py

```python
# main.py
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
```

#### Issue: Circular Imports

```
ImportError: cannot import name 'X' from partially initialized module 'Y'
```

**Solution**: Check import hierarchy. Use TYPE_CHECKING for type hints only:

```python
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from entities.character import Character  # Type hint only

def function(character: 'Character'):  # String literal for forward reference
    pass
```

#### Issue: Pygame Window Not Responding

```python
# Ensure event queue is processed
for event in pygame.event.get():
    if event.type == pygame.QUIT:
        pygame.quit()
        sys.exit()
```

#### Issue: Items Not Equipping

Check:
1. Is item recognized as equipment? `equip_db.is_equipment(item_id)`
2. Does equipment_data exist? `item_stack.equipment_data`
3. Does character meet requirements? `equipment.can_equip(character)`
4. Is slot valid? Check EquipmentManager.slots

---

## Testing

### Manual Testing Checklist

```markdown
## Character Systems
- [ ] Create new character
- [ ] Level up (gain stat points)
- [ ] Allocate stat points
- [ ] Equip weapons/armor/tools
- [ ] Learn skills
- [ ] Activate skills from hotbar
- [ ] Gain and activate titles
- [ ] Select class

## World Interaction
- [ ] Move with WASD
- [ ] Harvest trees (need axe)
- [ ] Mine ore (need pickaxe)
- [ ] Interact with crafting stations
- [ ] Talk to NPCs
- [ ] Accept quests
- [ ] Complete quests

## Combat
- [ ] Attack enemies (left-click)
- [ ] Take damage
- [ ] Die and respawn
- [ ] Use combat skills
- [ ] See damage numbers

## Crafting
- [ ] Craft at smithing station
- [ ] Craft at alchemy station
- [ ] Complete minigames
- [ ] Check crafted item stats

## UI
- [ ] Open/close all UI windows (C, E, K, L)
- [ ] Drag and drop inventory items
- [ ] Double-click to equip
- [ ] Right-click to use consumables
- [ ] Navigate encyclopedia tabs
- [ ] View tooltips

## Save/Load
- [ ] Save game (F5)
- [ ] Load game (F6)
- [ ] Verify state persists

## Debug Mode
- [ ] Toggle debug mode (F1)
- [ ] Verify infinite resources
- [ ] Verify max level/stats
```

### Automated Testing

The project has 13 test files in `tests/`:

```bash
# Run all tests
cd Game-1-modular
python -m pytest tests/ -v

# Run specific test file
python -m pytest tests/test_inventory.py -v

# Run with coverage
python -m pytest tests/ --cov=. --cov-report=html
```

**Example Test File**:
```python
# tests/test_inventory.py
import pytest
from entities.components import Inventory

def test_inventory_add_item():
    inv = Inventory(30)
    success = inv.add_item("copper_ore", 50)
    assert success
    assert inv.get_item_count("copper_ore") == 50

def test_inventory_stack_limit():
    inv = Inventory(30)
    inv.add_item("copper_ore", 99)  # Max stack
    inv.add_item("copper_ore", 50)  # Should create second stack
    assert len([s for s in inv.slots if s and s.item_id == "copper_ore"]) == 2
```

### Crafting System Tests

```bash
# Run crafting system tester
python -c "from core.testing import CraftingSystemTester; t = CraftingSystemTester(); t.run_all_tests()"
```

---

## Performance Optimization

### Profiling

```python
import cProfile
import pstats

def profile_game():
    profiler = cProfile.Profile()
    profiler.enable()

    # Run game for 100 frames
    game = GameEngine()
    for _ in range(100):
        game.update(1/60)
        game.render()

    profiler.disable()
    stats = pstats.Stats(profiler)
    stats.sort_stats('cumulative')
    stats.print_stats(20)  # Top 20 slowest functions

profile_game()
```

### Optimization Strategies

#### 1. Reduce Rendering

```python
# Only render visible entities
def render_entities(self, entities, camera):
    visible = []
    for entity in entities:
        screen_pos = camera.world_to_screen(entity.position.x, entity.position.y)
        if self._is_on_screen(screen_pos):
            visible.append(entity)

    for entity in visible:
        self._render_entity(entity, camera)
```

#### 2. Cache Calculations

```python
# Cache expensive calculations
class Character:
    def __init__(self):
        self._total_defense_cache = None
        self._cache_dirty = False

    def recalculate_stats(self):
        # ... stat calculation ...
        self._cache_dirty = True

    def get_total_defense(self):
        if self._cache_dirty or self._total_defense_cache is None:
            self._total_defense_cache = self.equipment.get_total_defense()
            self._cache_dirty = False
        return self._total_defense_cache
```

#### 3. Limit Update Frequency

```python
# Update some systems less frequently
class GameEngine:
    def __init__(self):
        self.npc_update_timer = 0.0

    def update(self, delta_time):
        # Update every frame
        self.character.update(delta_time)
        self.combat_manager.update(delta_time)

        # Update every 0.5 seconds
        self.npc_update_timer += delta_time
        if self.npc_update_timer >= 0.5:
            for npc in self.world.npcs:
                npc.update(self.npc_update_timer)
            self.npc_update_timer = 0.0
```

---

## Troubleshooting

### Problem: Game Runs Slow

**Check**:
- FPS counter (should be 60)
- Number of enemies (reduce spawn rate)
- Rendering complexity (reduce visual effects)
- Profile with cProfile to find bottleneck

**Solutions**:
- Implement entity culling (don't render off-screen)
- Reduce particle effects
- Optimize rendering loops
- Use sprite batching for similar objects

---

### Problem: Saves Corrupt

**Check**:
- JSON format valid? Use JSON validator
- All fields present?
- Character state serializable?

**Solutions**:
- Add validation to load_from_file()
- Add version field to save files
- Implement save file migration for breaking changes

---

### Problem: Imports Fail After Adding Module

**Check**:
- `__init__.py` updated?
- Circular imports?
- Import hierarchy correct?

**Solutions**:
- Run `python verify_imports.py`
- Check import order
- Use TYPE_CHECKING for type-only imports

---

## Best Practices

### DO

✅ Follow the layer architecture (no circular imports)
✅ Use type hints for all function signatures
✅ Write docstrings for public methods
✅ Test manually before committing
✅ Use Config constants instead of magic numbers
✅ Fail gracefully with user-friendly messages
✅ Cache expensive calculations
✅ Keep functions small and focused

### DON'T

❌ Import from higher layers (breaks architecture)
❌ Use global mutable state (except singletons)
❌ Hardcode file paths (use Path() or relative paths)
❌ Leave print() statements for debugging
❌ Modify character state in rendering code
❌ Create circular dependencies
❌ Copy-paste code (make reusable functions)

---

## Resources

### Documentation

- [ARCHITECTURE.md](ARCHITECTURE.md) - System architecture overview
- [MODULE_REFERENCE.md](MODULE_REFERENCE.md) - Per-file documentation
- [GAME_MECHANICS_V6.md](GAME_MECHANICS_V6.md) - Master reference (5,089 lines)
- [REPOSITORY_STATUS_REPORT_2026-01-27.md](REPOSITORY_STATUS_REPORT_2026-01-27.md) - Current status
- [HOW_TO_RUN.md](../HOW_TO_RUN.md) - Quick start guide

### LLM Integration

- [Fewshot_llm/README.md](../../Scaled%20JSON%20Development/LLM%20Training%20Data/Fewshot_llm/README.md) - LLM system overview
- [MANUAL_TUNING_GUIDE.md](../../Scaled%20JSON%20Development/LLM%20Training%20Data/Fewshot_llm/MANUAL_TUNING_GUIDE.md) - Prompt editing guide

### Tag System

- [docs/tag-system/TAG-GUIDE.md](tag-system/TAG-GUIDE.md) - Comprehensive tag guide
- [docs/tag-system/TAG-REFERENCE.md](tag-system/TAG-REFERENCE.md) - Tag catalog

### External Resources

- [Pygame Documentation](https://www.pygame.org/docs/)
- [Python Type Hints](https://docs.python.org/3/library/typing.html)
- [PEP 8 Style Guide](https://pep8.org/)
- [Python Dataclasses](https://docs.python.org/3/library/dataclasses.html)
- [Anthropic API Documentation](https://docs.anthropic.com/)

---

## Getting Help

### Where to Ask

1. Check existing documentation (docs/)
2. Search codebase for similar implementations
3. Review git history for context
4. Ask in project chat/issues

### Providing Context

When asking for help, include:
- What you're trying to do
- What you expected to happen
- What actually happened
- Relevant code snippets
- Error messages (full traceback)
- Steps to reproduce

---

## Contributing

### Pull Request Process

1. Fork repository
2. Create feature branch
3. Make changes following style guide
4. Test thoroughly
5. Update documentation
6. Submit PR with description

### Commit Messages

```
# Good commit messages
Add fishing system with rod requirement
Fix inventory click position mismatch
Optimize enemy pathfinding algorithm
Update docs with new systems

# Bad commit messages
Fixed stuff
WIP
Update
asdf
```

---

**Happy Coding!** 🎮

For questions or suggestions, see project README or contact maintainers.

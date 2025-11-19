# How to Run Game-1 Modular

## Quick Start

**IMPORTANT: Always run the game through main.py:**

```bash
cd Game-1-modular
python main.py
```

## Requirements

- Python 3.11 or higher
- pygame 2.6+

Install dependencies:
```bash
pip install pygame
```

## Common Issues

### ModuleNotFoundError: No module named 'core'

**Problem:** You're trying to run individual files instead of main.py.

**Solution:** Always run through main.py:
```bash
# ❌ WRONG - Don't do this
python rendering/renderer.py
python core/game_engine.py

# ✓ CORRECT - Do this
python main.py
```

**Why:** main.py sets up the Python path correctly so all modules can find each other.

### Imports not working on Windows

**Problem:** Path separators differ between Windows and Linux.

**Solution:** The code should work on both platforms. Make sure you:
1. Run from the `Game-1-modular` directory
2. Use `python main.py` (not individual files)
3. Have all dependencies installed

## Project Structure

```
Game-1-modular/
├── main.py                 # ← START HERE - main entry point
├── core/                   # Core game systems
│   ├── __init__.py
│   ├── game_engine.py
│   ├── camera.py
│   └── config.py
├── data/                   # Data models and databases
│   ├── models/            # Data classes
│   └── databases/         # Database loaders
├── entities/              # Game entities
│   ├── character.py
│   └── components/        # Character components
├── systems/               # Game systems
│   ├── world_system.py
│   ├── quest_system.py
│   └── ...
├── rendering/             # Rendering system
│   └── renderer.py
├── Combat/                # Combat system (copied from original)
└── Crafting-subdisciplines/  # Crafting minigames (copied from original)
```

## Verification

To verify the module structure is correct:

```bash
python verify_imports.py
```

This will check that all imports work correctly.

## Debug Mode

**Press F1 during gameplay to toggle debug mode!**

When debug mode is enabled:
- **Infinite Materials**: Craft anything without consuming materials
- **Level 30**: Automatically set to max level
- **100 Stat Points**: Ready to allocate
- **No Material Requirements**: All recipes show as craftable (green)
- **Instant Resources**: Trees/ores respawn in 1 second instead of 60
- **Infinite Durability**: Tools never break

**How to use:**
1. Run the game: `python main.py`
2. Press **F1** to enable debug mode
3. You'll see: "🔧 DEBUG MODE ENABLED"
4. Now you can craft anything without materials!
5. Press **F1** again to disable

**Note:** Debug mode does NOT fill your inventory with items. Instead, it lets you craft freely without needing materials. This is better for testing crafting recipes.

You can also enable it by default in `core/config.py`:
```python
DEBUG_INFINITE_RESOURCES = True  # Set to True for always-on debug mode
```

## Troubleshooting

1. **Clear Python cache:**
   ```bash
   find . -type d -name __pycache__ -exec rm -rf {} +
   find . -type f -name "*.pyc" -delete
   ```

2. **Verify Python version:**
   ```bash
   python --version  # Should be 3.11+
   ```

3. **Reinstall pygame:**
   ```bash
   pip uninstall pygame
   pip install pygame
   ```

4. **Check if all files are present:**
   ```bash
   python verify_imports.py
   ```

## Development

When adding new modules:
1. Add them to the appropriate directory (core/, data/, entities/, systems/, rendering/)
2. Create/update __init__.py to export public interfaces
3. Use absolute imports: `from core import Config` not `from .core import Config`
4. Test imports: `python verify_imports.py`

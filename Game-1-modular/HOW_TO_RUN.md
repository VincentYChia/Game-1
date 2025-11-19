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

Debug mode gives you:
- Level 30
- 100 stat points
- 50 copper ore
- 50 iron ore
- 50 oak logs
- 50 birch logs

To enable debug mode, modify `core/config.py`:
```python
DEBUG_INFINITE_RESOURCES = True
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

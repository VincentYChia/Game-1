# Save System

This folder contains all save system related code and documentation.

## Files

### Core Save System
- **`../systems/save_manager.py`** - Main save/load manager
  - Handles save file creation, loading, and validation
  - Located in `systems/` as it's a core game system

### Utilities
- **`create_default_save.py`** - Creates default save files for new games
  - Usage: `python save_system/create_default_save.py`
  - Generates a clean starter save in `saves/default_save.json`

### Testing
- **`test_save_system.py`** - Comprehensive save system tests
  - Tests save/load functionality
  - Validates data integrity
  - Usage: `python save_system/test_save_system.py`

- **`test_default_save.py`** - Tests default save generation
  - Validates default save structure
  - Ensures all required fields are present
  - Usage: `python save_system/test_default_save.py`

### Documentation
- **`SAVE_SYSTEM.md`** - Technical documentation
  - Save file format specification
  - Data structures and schemas
  - Implementation details

- **`README_DEFAULT_SAVE.md`** - Default save guide
  - Explains default save structure
  - How to customize starting conditions
  - Field descriptions

## Quick Start

### Create a Default Save
```bash
cd Game-1-modular
python save_system/create_default_save.py
```

### Run Tests
```bash
cd Game-1-modular
python save_system/test_save_system.py
python save_system/test_default_save.py
```

### Load a Save (from game code)
```python
from systems.save_manager import SaveManager

save_manager = SaveManager()
game_state = save_manager.load_save('default_save')
```

## Save File Location

Save files are stored in: `saves/`

Default saves:
- `saves/default_save.json` - New game starting state
- `saves/quick_save.json` - Quick save slot
- `saves/auto_save.json` - Auto-save slot

## Architecture

```
save_system/           # Save system utilities and tests
├── create_default_save.py
├── test_save_system.py
├── test_default_save.py
├── SAVE_SYSTEM.md
└── README_DEFAULT_SAVE.md

systems/              # Core game systems
└── save_manager.py   # Main save/load manager

saves/                # Save file directory
├── default_save.json
├── quick_save.json
└── auto_save.json
```

## Related Systems

- **Inventory System** (`systems/inventory.py`) - Manages item storage
- **Progression System** (`progression/`) - Tracks character advancement
- **World State** (`data/models/world.py`) - World and entity state

## Future Improvements

- [ ] Cloud save support
- [ ] Save file compression
- [ ] Multiple save slots UI
- [ ] Save file migration system
- [ ] Backup/restore functionality

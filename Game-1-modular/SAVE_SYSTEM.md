# Save/Load System Documentation

## Overview

This game now features a comprehensive save/load system that preserves:
- **Player state**: Inventory, equipment, stats, skills, level, titles, activities
- **World state**: Placed entities (turrets, traps, crafting stations), modified resources
- **Quest progress**: Active quests, completed quests, objective progress
- **NPC state**: Dialogue progression

## Architecture

### SaveManager (`systems/save_manager.py`)

The `SaveManager` class is the central hub for all save/load operations. It handles:
- Serializing game state to JSON
- Deserializing JSON to game state
- Managing save files
- Version tracking

### Save Data Structure

```json
{
  "version": "2.0",
  "save_timestamp": "2025-11-29T12:34:56",
  "player": {
    "position": {"x": 50.0, "y": 50.0, "z": 0.0},
    "facing": "down",
    "stats": { ... },
    "leveling": { ... },
    "health": 100.0,
    "max_health": 150.0,
    "mana": 50.0,
    "max_mana": 100.0,
    "class": "warrior",
    "inventory": [ ... ],
    "equipment": { ... },
    "equipped_skills": [ ... ],
    "known_skills": { ... },
    "titles": [ ... ],
    "activities": { ... }
  },
  "world_state": {
    "placed_entities": [
      {
        "position": {"x": 45.0, "y": 50.0, "z": 0.0},
        "item_id": "basic_turret",
        "entity_type": "TURRET",
        "tier": 1,
        "health": 100.0,
        "range": 5.0,
        "damage": 20.0,
        "attack_speed": 1.0,
        "time_remaining": 280.0
      }
    ],
    "modified_resources": [
      {
        "position": {"x": 30.0, "y": 40.0, "z": 0.0},
        "resource_type": "OAK_TREE",
        "tier": 1,
        "current_hp": 50,
        "max_hp": 100,
        "depleted": false,
        "time_until_respawn": 0.0
      }
    ],
    "crafting_stations": [ ... ]
  },
  "quest_state": {
    "active_quests": {
      "quest_gather_wood": {
        "status": "in_progress",
        "progress": {},
        "baseline_combat_kills": 5,
        "baseline_inventory": {"oak_log": 2}
      }
    },
    "completed_quests": ["quest_intro"]
  },
  "npc_state": {
    "npc_elder": {
      "current_dialogue_index": 2
    }
  }
}
```

## Key Features

### Minimal Data Storage

The system saves only necessary data:
- **Modified resources only**: Only resources that have been harvested or modified are saved
- **Placed entities only**: World generation is random each time, but placed items are preserved
- **Quest progress**: Only active and completed quest states
- **Compact inventory**: Equipment stats are preserved but stored efficiently

### World Generation

- **Random world each load**: The world regenerates randomly to keep exploration fresh
- **Placed items preserved**: All player-placed turrets, traps, and stations are restored
- **Resource modifications preserved**: Harvested trees/ores maintain their HP state
- **Crafting stations preserved**: All crafting stations are restored to their saved positions

### Equipment & Inventory

- **Full equipment preservation**: All equipment stats, bonus stats, and crafted stats are saved
- **Inventory stacking**: Materials stack correctly on load
- **Equipment instances**: Each equipment piece maintains its unique stats

## Usage

### Saving

**Autosave (F5)**: Quick save to `saves/autosave.json`
```python
# Game engine handles this automatically
if self.save_manager.save_game(
    self.character,
    self.world,
    self.character.quests,
    self.npcs,
    "autosave.json"
):
    print("Game saved!")
```

**Timestamped Save (F6)**: Creates a new save file with timestamp
```python
import datetime
timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
self.save_manager.save_game(
    self.character,
    self.world,
    self.character.quests,
    self.npcs,
    f"save_{timestamp}.json"
)
```

### Loading

**Quick Load (F9)**: Load from autosave
```python
save_data = self.save_manager.load_game("autosave.json")
if save_data:
    # Restore character
    self.character.restore_from_save(save_data["player"])

    # Restore world
    self.world.restore_from_save(save_data["world_state"])

    # Restore quests
    self.character.quests.restore_from_save(save_data["quest_state"])

    # Restore NPCs
    SaveManager.restore_npc_state(self.npcs, save_data["npc_state"])
```

**Load from Start Menu**: Select "Load World" to load autosave

### Managing Save Files

**List all saves**:
```python
save_files = self.save_manager.get_save_files()
for save in save_files:
    print(f"{save['filename']} - Level {save['level']} - {save['save_timestamp']}")
```

**Delete a save**:
```python
self.save_manager.delete_save_file("old_save.json")
```

## Implementation Details

### Character Restoration

The `Character.restore_from_save()` method handles:
1. Position and facing direction
2. Base stats (strength, defense, vitality, luck, agility, intelligence)
3. Leveling (level, exp, unallocated stat points)
4. Class assignment
5. Health/mana (after stat recalculation)
6. Inventory items with full equipment data
7. Equipped items
8. Skills (known and equipped)
9. Titles
10. Activity counters

### World State Restoration

The `WorldSystem.restore_from_save()` method handles:
1. Clearing existing placed entities
2. Recreating placed entities from save data
3. Applying resource modifications (HP, depletion, respawn timers)
4. Restoring crafting stations

### Quest State Restoration

The `QuestManager.restore_from_save()` method handles:
1. Clearing existing quest state
2. Restoring completed quest list
3. Recreating active quests with progress and baselines

### NPC State Restoration

The `SaveManager.restore_npc_state()` static method handles:
1. Restoring dialogue progression for each NPC

## Future Enhancements

Potential improvements for the save system:

1. **Multiple save slots UI**: Visual save slot selection instead of just autosave
2. **Save compression**: Compress JSON files to reduce disk usage
3. **Cloud saves**: Optional cloud backup integration
4. **Save validation**: Checksum verification to prevent corruption
5. **Backwards compatibility**: Handle loading saves from older versions
6. **Incremental saves**: Save only changed data for performance
7. **Auto-save on quit**: Automatically save when closing the game
8. **Save screenshots**: Store a thumbnail with each save for identification

## File Locations

- **Save files**: `saves/*.json`
- **Autosave**: `saves/autosave.json`
- **Timestamped saves**: `saves/save_YYYYMMDD_HHMMSS.json`

## Troubleshooting

### Save not working
- Check that you're not in temporary world mode (started with `--temp` flag)
- Ensure `saves/` directory exists (created automatically)
- Check console for error messages

### Load not restoring placed items
- Verify the save file contains `world_state.placed_entities` array
- Check that save version is compatible

### Quest progress lost
- Ensure quests were active (not just offered) before saving
- Check `quest_state.active_quests` in save file

## Migration from Old System

The old system (Character.save_to_file/load_from_file) saved only character data. The new system is backwards compatible but won't restore world/quest state from old saves. Old saves will:
- ✓ Restore player stats, inventory, equipment
- ✗ Not restore placed entities
- ✗ Not restore quest progress
- ✗ Not restore modified resources

To get full functionality, create a new save after loading an old one.

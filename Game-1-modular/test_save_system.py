"""
Test script for the new save/load system.
Tests serialization and deserialization without requiring pygame.
"""

import sys
import json
from pathlib import Path

# Add the current directory to path
sys.path.insert(0, str(Path(__file__).parent))

def test_save_manager_import():
    """Test that SaveManager can be imported"""
    try:
        from systems.save_manager import SaveManager
        print("✓ SaveManager imported successfully")
        return True
    except Exception as e:
        print(f"✗ Failed to import SaveManager: {e}")
        return False

def test_save_data_structure():
    """Test that save data structure is created correctly"""
    try:
        from systems.save_manager import SaveManager

        save_manager = SaveManager()

        # Create mock data
        mock_character = type('obj', (object,), {
            'position': type('obj', (object,), {'x': 50.0, 'y': 50.0, 'z': 0.0})(),
            'facing': 'down',
            'stats': type('obj', (object,), {
                'strength': 10,
                'defense': 5,
                'vitality': 8,
                'luck': 3,
                'agility': 7,
                'intelligence': 6
            })(),
            'leveling': type('obj', (object,), {
                'level': 5,
                'current_exp': 1000,
                'unallocated_stat_points': 2
            })(),
            'health': 100.0,
            'max_health': 150.0,
            'mana': 50.0,
            'max_mana': 100.0,
            'class_system': type('obj', (object,), {'current_class': None})(),
            'inventory': type('obj', (object,), {'slots': [None] * 30})(),
            'equipment': type('obj', (object,), {'equipment_slots': {}})(),
            'skills': type('obj', (object,), {
                'equipped_skills': [None] * 5,
                'known_skills': {}
            })(),
            'titles': type('obj', (object,), {'earned_titles': []})(),
            'activities': type('obj', (object,), {'activity_counts': {}})()
        })()

        mock_world = type('obj', (object,), {
            'placed_entities': [],
            'resources': [],
            'crafting_stations': []
        })()

        mock_quest_manager = type('obj', (object,), {
            'active_quests': {},
            'completed_quests': []
        })()

        mock_npcs = []

        # Create save data
        save_data = save_manager.create_save_data(
            mock_character,
            mock_world,
            mock_quest_manager,
            mock_npcs
        )

        # Verify structure
        assert "version" in save_data
        assert "save_timestamp" in save_data
        assert "player" in save_data
        assert "world_state" in save_data
        assert "quest_state" in save_data
        assert "npc_state" in save_data

        # Verify player data
        assert save_data["player"]["position"]["x"] == 50.0
        assert save_data["player"]["stats"]["strength"] == 10
        assert save_data["player"]["leveling"]["level"] == 5

        print("✓ Save data structure is correct")
        print(f"  Version: {save_data['version']}")
        print(f"  Player level: {save_data['player']['leveling']['level']}")
        print(f"  Player position: ({save_data['player']['position']['x']}, {save_data['player']['position']['y']})")

        return True

    except Exception as e:
        print(f"✗ Failed to create save data structure: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_json_serialization():
    """Test that save data can be serialized to JSON"""
    try:
        from systems.save_manager import SaveManager

        save_manager = SaveManager()

        # Create minimal mock data
        mock_character = type('obj', (object,), {
            'position': type('obj', (object,), {'x': 50.0, 'y': 50.0, 'z': 0.0})(),
            'facing': 'down',
            'stats': type('obj', (object,), {
                'strength': 10, 'defense': 5, 'vitality': 8,
                'luck': 3, 'agility': 7, 'intelligence': 6
            })(),
            'leveling': type('obj', (object,), {
                'level': 5, 'current_exp': 1000, 'unallocated_stat_points': 2
            })(),
            'health': 100.0,
            'max_health': 150.0,
            'mana': 50.0,
            'max_mana': 100.0,
            'class_system': type('obj', (object,), {'current_class': None})(),
            'inventory': type('obj', (object,), {'slots': [None] * 30})(),
            'equipment': type('obj', (object,), {'equipment_slots': {}})(),
            'skills': type('obj', (object,), {
                'equipped_skills': [None] * 5,
                'known_skills': {}
            })(),
            'titles': type('obj', (object,), {'earned_titles': []})(),
            'activities': type('obj', (object,), {'activity_counts': {}})()
        })()

        mock_world = type('obj', (object,), {
            'placed_entities': [],
            'resources': [],
            'crafting_stations': []
        })()

        mock_quest_manager = type('obj', (object,), {
            'active_quests': {},
            'completed_quests': []
        })()

        mock_npcs = []

        save_data = save_manager.create_save_data(
            mock_character, mock_world, mock_quest_manager, mock_npcs
        )

        # Try to serialize to JSON
        json_str = json.dumps(save_data, indent=2)

        # Try to deserialize
        loaded_data = json.loads(json_str)

        assert loaded_data["player"]["leveling"]["level"] == 5

        print("✓ JSON serialization works correctly")
        print(f"  JSON size: {len(json_str)} characters")

        return True

    except Exception as e:
        print(f"✗ Failed JSON serialization test: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Run all tests"""
    print("=" * 60)
    print("Testing Save/Load System")
    print("=" * 60)
    print()

    results = []

    print("Test 1: SaveManager Import")
    results.append(test_save_manager_import())
    print()

    print("Test 2: Save Data Structure")
    results.append(test_save_data_structure())
    print()

    print("Test 3: JSON Serialization")
    results.append(test_json_serialization())
    print()

    print("=" * 60)
    print(f"Results: {sum(results)}/{len(results)} tests passed")
    print("=" * 60)

    if all(results):
        print("✓ All tests passed!")
        return 0
    else:
        print("✗ Some tests failed")
        return 1

if __name__ == "__main__":
    sys.exit(main())

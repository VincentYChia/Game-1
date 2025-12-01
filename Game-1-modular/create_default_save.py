"""
Script to create a default save file with a well-equipped character for testing.
Run this script to generate saves/default_save.json
"""

import json
import os
from pathlib import Path

def create_default_save():
    """Create a default save with a medium-level character and good variety of items."""

    # Ensure saves directory exists
    Path("saves").mkdir(exist_ok=True)

    default_save = {
        "version": "2.0",
        "save_timestamp": "2025-11-29T00:00:00",
        "player": {
            "position": {"x": 50.0, "y": 50.0, "z": 0.0},
            "facing": "down",
            "stats": {
                "strength": 15,
                "defense": 12,
                "vitality": 14,
                "luck": 8,
                "agility": 10,
                "intelligence": 11
            },
            "leveling": {
                "level": 10,
                "current_exp": 5000,
                "unallocated_stat_points": 5
            },
            "health": 200.0,
            "max_health": 200.0,
            "mana": 150.0,
            "max_mana": 150.0,
            "class": "warrior",
            "inventory": [
                # Materials for crafting
                {"item_id": "copper_ore", "quantity": 25, "max_stack": 99, "rarity": "common"},
                {"item_id": "iron_ore", "quantity": 20, "max_stack": 99, "rarity": "common"},
                {"item_id": "steel_ore", "quantity": 10, "max_stack": 99, "rarity": "uncommon"},
                {"item_id": "oak_log", "quantity": 30, "max_stack": 99, "rarity": "common"},
                {"item_id": "birch_log", "quantity": 20, "max_stack": 99, "rarity": "common"},
                {"item_id": "maple_log", "quantity": 15, "max_stack": 99, "rarity": "uncommon"},
                {"item_id": "limestone", "quantity": 20, "max_stack": 99, "rarity": "common"},
                {"item_id": "granite", "quantity": 15, "max_stack": 99, "rarity": "common"},

                # Refined materials
                {"item_id": "copper_ingot", "quantity": 15, "max_stack": 99, "rarity": "common"},
                {"item_id": "iron_ingot", "quantity": 10, "max_stack": 99, "rarity": "common"},
                {"item_id": "oak_plank", "quantity": 20, "max_stack": 99, "rarity": "common"},
                {"item_id": "birch_plank", "quantity": 15, "max_stack": 99, "rarity": "common"},

                # Some consumables
                {"item_id": "minor_health_potion", "quantity": 5, "max_stack": 99, "rarity": "common"},
                {"item_id": "health_potion", "quantity": 3, "max_stack": 99, "rarity": "common"},

                # Equipment pieces in inventory (not equipped) - using items that actually exist
                {
                    "item_id": "iron_shortsword",
                    "quantity": 1,
                    "max_stack": 1,
                    "rarity": "common",
                    "equipment_data": {
                        "item_id": "iron_shortsword",
                        "name": "Iron Shortsword",
                        "tier": 1,
                        "rarity": "common",
                        "slot": "mainHand",
                        "damage": [8, 12],
                        "defense": 0,
                        "durability_current": 100,
                        "durability_max": 100,
                        "attack_speed": 1.2,
                        "weight": 2.0,
                        "range": 1.0,
                        "hand_type": "1H",
                        "item_type": "weapon"
                    }
                },
                {
                    "item_id": "steel_helm",
                    "quantity": 1,
                    "max_stack": 1,
                    "rarity": "uncommon",
                    "equipment_data": {
                        "item_id": "steel_helm",
                        "name": "Steel Helm",
                        "tier": 2,
                        "rarity": "uncommon",
                        "slot": "head",
                        "damage": [0, 0],
                        "defense": 12,
                        "durability_current": 120,
                        "durability_max": 120,
                        "attack_speed": 1.0,
                        "weight": 3.0,
                        "range": 1.0,
                        "hand_type": "default",
                        "item_type": "armor"
                    }
                },

                # Some devices for placement
                {"item_id": "basic_arrow_turret", "quantity": 3, "max_stack": 10, "rarity": "uncommon"},
                {"item_id": "spike_trap", "quantity": 5, "max_stack": 10, "rarity": "common"},

                # Empty slots
                None, None, None, None, None, None, None, None, None, None, None, None
            ],
            "equipment": {
                "mainHand": "steel_longsword",
                "offHand": None,
                "helmet": "steel_helm",
                "chestplate": "iron_chestplate",
                "leggings": "steel_leggings",
                "boots": "iron_boots",
                "gauntlets": "iron_studded_gauntlets",
                "accessory": None,
                "axe": "iron_axe",
                "pickaxe": "iron_pickaxe"
            },
            "equipped_skills": [
                "fireball",
                "heal",
                "shield_bash",
                None,
                None
            ],
            "known_skills": {
                "fireball": {"level": 2, "experience": 150},
                "heal": {"level": 1, "experience": 50},
                "shield_bash": {"level": 3, "experience": 300},
                "ice_shard": {"level": 1, "experience": 0},
                "power_strike": {"level": 2, "experience": 100}
            },
            "titles": [
                "novice_explorer",
                "apprentice_smith"
            ],
            "activities": {
                "mining": 50,
                "forestry": 40,
                "smithing": 25,
                "refining": 20,
                "alchemy": 10,
                "engineering": 15,
                "enchanting": 5,
                "combat": 60
            }
        },
        "world_state": {
            "placed_entities": [
                {
                    "position": {"x": 48.0, "y": 48.0, "z": 0.0},
                    "item_id": "basic_arrow_turret",
                    "entity_type": "TURRET",
                    "tier": 1,
                    "health": 100.0,
                    "owner": None,
                    "time_remaining": 300.0,
                    "range": 5.0,
                    "damage": 20.0,
                    "attack_speed": 1.0
                }
            ],
            "modified_resources": [
                {
                    "position": {"x": 45.0, "y": 45.0, "z": 0.0},
                    "resource_type": "OAK_TREE",
                    "tier": 1,
                    "current_hp": 50,
                    "max_hp": 100,
                    "depleted": False,
                    "time_until_respawn": 0.0
                }
            ],
            "crafting_stations": [
                {"position": {"x": 44.0, "y": 46.0, "z": 0.0}, "station_type": "SMITHING", "tier": 1},
                {"position": {"x": 44.0, "y": 48.0, "z": 0.0}, "station_type": "SMITHING", "tier": 2},
                {"position": {"x": 44.0, "y": 50.0, "z": 0.0}, "station_type": "SMITHING", "tier": 3},
                {"position": {"x": 44.0, "y": 52.0, "z": 0.0}, "station_type": "SMITHING", "tier": 4},
                {"position": {"x": 46.0, "y": 46.0, "z": 0.0}, "station_type": "REFINING", "tier": 1},
                {"position": {"x": 46.0, "y": 48.0, "z": 0.0}, "station_type": "REFINING", "tier": 2},
                {"position": {"x": 46.0, "y": 50.0, "z": 0.0}, "station_type": "REFINING", "tier": 3},
                {"position": {"x": 46.0, "y": 52.0, "z": 0.0}, "station_type": "REFINING", "tier": 4},
                {"position": {"x": 54.0, "y": 46.0, "z": 0.0}, "station_type": "ALCHEMY", "tier": 1},
                {"position": {"x": 54.0, "y": 48.0, "z": 0.0}, "station_type": "ALCHEMY", "tier": 2},
                {"position": {"x": 54.0, "y": 50.0, "z": 0.0}, "station_type": "ALCHEMY", "tier": 3},
                {"position": {"x": 54.0, "y": 52.0, "z": 0.0}, "station_type": "ALCHEMY", "tier": 4},
                {"position": {"x": 56.0, "y": 46.0, "z": 0.0}, "station_type": "ENGINEERING", "tier": 1},
                {"position": {"x": 56.0, "y": 48.0, "z": 0.0}, "station_type": "ENGINEERING", "tier": 2},
                {"position": {"x": 56.0, "y": 50.0, "z": 0.0}, "station_type": "ENGINEERING", "tier": 3},
                {"position": {"x": 56.0, "y": 52.0, "z": 0.0}, "station_type": "ENGINEERING", "tier": 4},
                {"position": {"x": 50.0, "y": 46.0, "z": 0.0}, "station_type": "ADORNMENTS", "tier": 1},
                {"position": {"x": 50.0, "y": 48.0, "z": 0.0}, "station_type": "ADORNMENTS", "tier": 2},
                {"position": {"x": 50.0, "y": 50.0, "z": 0.0}, "station_type": "ADORNMENTS", "tier": 3},
                {"position": {"x": 50.0, "y": 52.0, "z": 0.0}, "station_type": "ADORNMENTS", "tier": 4}
            ]
        },
        "quest_state": {
            "active_quests": {},
            "completed_quests": ["tutorial_quest"]
        },
        "npc_state": {
            "elder": {"current_dialogue_index": 1},
            "blacksmith": {"current_dialogue_index": 0}
        }
    }

    # Write to file
    filepath = os.path.join("saves", "default_save.json")
    with open(filepath, 'w') as f:
        json.dump(default_save, f, indent=2)

    print(f"✓ Default save created: {filepath}")
    print("\nDefault character setup:")
    print(f"  • Level: {default_save['player']['leveling']['level']}")
    print(f"  • Class: {default_save['player']['class']}")
    print(f"  • Unallocated stat points: {default_save['player']['leveling']['unallocated_stat_points']}")
    print(f"  • Known skills: {len(default_save['player']['known_skills'])}")
    print(f"  • Inventory items: {sum(1 for item in default_save['player']['inventory'] if item is not None)}")
    print(f"  • Equipped items: {sum(1 for item in default_save['player']['equipment'].values() if item is not None)}")
    print(f"\nLoad this save by selecting 'Load Default Save' from the start menu,")
    print(f"or press Shift+F9 during gameplay.")

if __name__ == "__main__":
    create_default_save()

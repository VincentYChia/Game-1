"""
Save Manager System
Handles comprehensive save/load functionality for all game state.
"""

import json
import os
from datetime import datetime
from typing import Dict, List, Optional, Any
from pathlib import Path

from data.models.world import Position


class SaveManager:
    """Centralized save/load manager for all game state."""

    SAVE_VERSION = "2.0"
    SAVE_DIR = "saves"

    def __init__(self):
        """Initialize the save manager."""
        self.ensure_save_directory()

    def ensure_save_directory(self):
        """Ensure the saves directory exists."""
        Path(self.SAVE_DIR).mkdir(exist_ok=True)

    def create_save_data(
        self,
        character,
        world_system,
        quest_manager,
        npcs
    ) -> Dict[str, Any]:
        """
        Create a comprehensive save data structure.

        Args:
            character: Character instance
            world_system: WorldSystem instance
            quest_manager: QuestManager instance
            npcs: List[NPC] instances

        Returns:
            Dictionary containing all save data
        """
        save_data = {
            "version": self.SAVE_VERSION,
            "save_timestamp": datetime.now().isoformat(),
            "player": self._serialize_character(character),
            "world_state": self._serialize_world_state(world_system),
            "quest_state": self._serialize_quest_state(quest_manager),
            "npc_state": self._serialize_npc_state(npcs)
        }

        return save_data

    def _serialize_character(self, character) -> Dict[str, Any]:
        """
        Serialize character data.

        Args:
            character: Character instance

        Returns:
            Dictionary containing character data
        """
        # Use existing character serialization
        char_data = {
            "position": {
                "x": character.position.x,
                "y": character.position.y,
                "z": character.position.z
            },
            "facing": character.facing,
            "stats": {
                "strength": character.stats.strength,
                "defense": character.stats.defense,
                "vitality": character.stats.vitality,
                "luck": character.stats.luck,
                "agility": character.stats.agility,
                "intelligence": character.stats.intelligence
            },
            "leveling": {
                "level": character.leveling.level,
                "current_exp": character.leveling.current_exp,
                "unallocated_stat_points": character.leveling.unallocated_stat_points
            },
            "health": character.health,
            "max_health": character.max_health,
            "mana": character.mana,
            "max_mana": character.max_mana,
            "class": character.class_system.current_class.class_id if character.class_system.current_class else None,
            "inventory": self._serialize_inventory(character.inventory),
            "equipment": self._serialize_equipment(character.equipment),
            "equipped_skills": [
                skill.skill_id if skill else None
                for skill in character.skills.equipped_skills
            ],
            "known_skills": {
                skill_id: {
                    "level": skill_data.level,
                    "experience": skill_data.experience
                }
                for skill_id, skill_data in character.skills.known_skills.items()
            },
            "titles": list(character.titles.earned_titles),
            "activities": {
                activity: count
                for activity, count in character.activities.activity_counts.items()
            }
        }

        return char_data

    def _serialize_inventory(self, inventory) -> List[Optional[Dict[str, Any]]]:
        """Serialize inventory slots."""
        serialized_slots = []

        for slot in inventory.slots:
            if slot is None:
                serialized_slots.append(None)
            else:
                slot_data = {
                    "item_id": slot.item_id,
                    "quantity": slot.quantity,
                    "max_stack": slot.max_stack,
                    "rarity": slot.rarity
                }

                # Save equipment data if present
                if slot.equipment_data:
                    slot_data["equipment_data"] = {
                        "item_id": slot.equipment_data.item_id,
                        "name": slot.equipment_data.name,
                        "tier": slot.equipment_data.tier,
                        "rarity": slot.equipment_data.rarity,
                        "slot": slot.equipment_data.slot,
                        "damage": list(slot.equipment_data.damage) if isinstance(slot.equipment_data.damage, tuple) else slot.equipment_data.damage,
                        "defense": slot.equipment_data.defense,
                        "durability_current": slot.equipment_data.durability_current,
                        "durability_max": slot.equipment_data.durability_max,
                        "attack_speed": slot.equipment_data.attack_speed,
                        "weight": slot.equipment_data.weight,
                        "range": slot.equipment_data.range,
                        "hand_type": slot.equipment_data.hand_type,
                        "item_type": slot.equipment_data.item_type
                    }

                    # Save bonuses if present
                    if slot.equipment_data.bonuses:
                        slot_data["equipment_data"]["bonuses"] = slot.equipment_data.bonuses

                    # Save enchantments if present
                    if slot.equipment_data.enchantments:
                        slot_data["equipment_data"]["enchantments"] = slot.equipment_data.enchantments

                    # Save requirements if present
                    if slot.equipment_data.requirements:
                        slot_data["equipment_data"]["requirements"] = slot.equipment_data.requirements

                # Save crafted stats if present
                if slot.crafted_stats:
                    slot_data["crafted_stats"] = slot.crafted_stats

                serialized_slots.append(slot_data)

        return serialized_slots

    def _serialize_equipment(self, equipment_manager) -> Dict[str, Optional[str]]:
        """Serialize equipped items."""
        return {
            slot_name: item.item_id if item else None
            for slot_name, item in equipment_manager.equipment_slots.items()
        }

    def _serialize_world_state(self, world_system) -> Dict[str, Any]:
        """
        Serialize world state (placed entities, modified resources).

        Args:
            world_system: WorldSystem instance

        Returns:
            Dictionary containing world state data
        """
        world_data = {
            "placed_entities": [],
            "modified_resources": [],
            "crafting_stations": []
        }

        # Serialize placed entities (turrets, traps, devices)
        for entity in world_system.placed_entities:
            entity_data = {
                "position": {
                    "x": entity.position.x,
                    "y": entity.position.y,
                    "z": entity.position.z
                },
                "item_id": entity.item_id,
                "entity_type": entity.entity_type.name,
                "tier": entity.tier,
                "health": entity.health,
                "owner": entity.owner,
                "time_remaining": entity.time_remaining
            }

            # Add turret-specific data
            if hasattr(entity, 'range'):
                entity_data["range"] = entity.range
                entity_data["damage"] = entity.damage
                entity_data["attack_speed"] = entity.attack_speed

            world_data["placed_entities"].append(entity_data)

        # Serialize modified resources (harvested or with items placed on them)
        for resource in world_system.resources:
            # Only save if resource has been modified (HP < max OR depleted OR respawning)
            if (resource.current_hp < resource.max_hp or
                resource.depleted or
                resource.time_until_respawn > 0):

                resource_data = {
                    "position": {
                        "x": resource.position.x,
                        "y": resource.position.y,
                        "z": resource.position.z
                    },
                    "resource_type": resource.resource_type.name,
                    "tier": resource.tier,
                    "current_hp": resource.current_hp,
                    "max_hp": resource.max_hp,
                    "depleted": resource.depleted,
                    "time_until_respawn": resource.time_until_respawn
                }

                world_data["modified_resources"].append(resource_data)

        # Serialize crafting stations (only player-placed ones if any)
        # Note: The current implementation has fixed crafting stations
        # We'll save them in case the player can place custom ones in the future
        for station in world_system.crafting_stations:
            station_data = {
                "position": {
                    "x": station.position.x,
                    "y": station.position.y,
                    "z": station.position.z
                },
                "station_type": station.station_type.name,
                "tier": station.tier
            }
            world_data["crafting_stations"].append(station_data)

        return world_data

    def _serialize_quest_state(self, quest_manager) -> Dict[str, Any]:
        """
        Serialize quest state.

        Args:
            quest_manager: QuestManager instance

        Returns:
            Dictionary containing quest state data
        """
        quest_data = {
            "active_quests": {},
            "completed_quests": list(quest_manager.completed_quests)
        }

        # Serialize active quests
        for quest_id, quest in quest_manager.active_quests.items():
            quest_data["active_quests"][quest_id] = {
                "status": quest.status,
                "progress": quest.progress,
                "baseline_combat_kills": quest.baseline_combat_kills,
                "baseline_inventory": quest.baseline_inventory
            }

        return quest_data

    def _serialize_npc_state(self, npcs) -> Dict[str, Any]:
        """
        Serialize NPC state.

        Args:
            npcs: List[NPC] instances

        Returns:
            Dictionary containing NPC state data
        """
        npc_data = {}

        # Save dialogue progress for each NPC
        for npc in npcs:
            npc_data[npc.npc_def.npc_id] = {
                "current_dialogue_index": npc.current_dialogue_index
            }

        return npc_data

    @staticmethod
    def restore_npc_state(npcs, npc_state: dict):
        """
        Restore NPC dialogue state from save data.

        Args:
            npcs: List[NPC] instances to restore state to
            npc_state: Dictionary containing NPC state data from save file
        """
        for npc in npcs:
            npc_id = npc.npc_def.npc_id
            if npc_id in npc_state:
                npc.current_dialogue_index = npc_state[npc_id].get("current_dialogue_index", 0)

        print(f"Restored state for {len(npc_state)} NPCs")

    def save_game(
        self,
        character,
        world_system,
        quest_manager,
        npcs,
        filename: str = "autosave.json"
    ) -> bool:
        """
        Save the current game state to a file.

        Args:
            character: Character instance
            world_system: WorldSystem instance
            quest_manager: QuestManager instance
            npcs: List[NPC] instances
            filename: Name of the save file

        Returns:
            True if save was successful, False otherwise
        """
        try:
            save_data = self.create_save_data(
                character,
                world_system,
                quest_manager,
                npcs
            )

            filepath = os.path.join(self.SAVE_DIR, filename)

            with open(filepath, 'w') as f:
                json.dump(save_data, f, indent=2)

            print(f"Game saved successfully to {filepath}")
            return True

        except Exception as e:
            print(f"Error saving game: {e}")
            return False

    def load_game(
        self,
        filename: str = "autosave.json"
    ) -> Optional[Dict[str, Any]]:
        """
        Load game state from a file.

        Args:
            filename: Name of the save file

        Returns:
            Dictionary containing save data, or None if load failed
        """
        try:
            filepath = os.path.join(self.SAVE_DIR, filename)

            if not os.path.exists(filepath):
                print(f"Save file not found: {filepath}")
                return None

            with open(filepath, 'r') as f:
                save_data = json.load(f)

            # Validate save version
            version = save_data.get("version", "1.0")
            if version != self.SAVE_VERSION:
                print(f"Warning: Save file version {version} may not be compatible with current version {self.SAVE_VERSION}")

            print(f"Game loaded successfully from {filepath}")
            return save_data

        except Exception as e:
            print(f"Error loading game: {e}")
            return None

    def get_save_files(self) -> List[Dict[str, Any]]:
        """
        Get list of all save files with metadata.

        Returns:
            List of dictionaries containing save file info
        """
        save_files = []

        if not os.path.exists(self.SAVE_DIR):
            return save_files

        for filename in os.listdir(self.SAVE_DIR):
            if filename.endswith('.json'):
                filepath = os.path.join(self.SAVE_DIR, filename)

                try:
                    # Get file metadata
                    stat = os.stat(filepath)
                    modified_time = datetime.fromtimestamp(stat.st_mtime)

                    # Try to read save timestamp from file
                    with open(filepath, 'r') as f:
                        data = json.load(f)
                        save_timestamp = data.get("save_timestamp", modified_time.isoformat())
                        version = data.get("version", "1.0")

                        # Get character level if available
                        level = 1
                        if "player" in data and "leveling" in data["player"]:
                            level = data["player"]["leveling"].get("level", 1)

                    save_files.append({
                        "filename": filename,
                        "filepath": filepath,
                        "save_timestamp": save_timestamp,
                        "modified_time": modified_time.isoformat(),
                        "version": version,
                        "level": level
                    })

                except Exception as e:
                    print(f"Error reading save file {filename}: {e}")

        # Sort by modified time (newest first)
        save_files.sort(key=lambda x: x["modified_time"], reverse=True)

        return save_files

    def delete_save_file(self, filename: str) -> bool:
        """
        Delete a save file.

        Args:
            filename: Name of the save file to delete

        Returns:
            True if deletion was successful, False otherwise
        """
        try:
            filepath = os.path.join(self.SAVE_DIR, filename)

            if os.path.exists(filepath):
                os.remove(filepath)
                print(f"Save file deleted: {filepath}")
                return True
            else:
                print(f"Save file not found: {filepath}")
                return False

        except Exception as e:
            print(f"Error deleting save file: {e}")
            return False

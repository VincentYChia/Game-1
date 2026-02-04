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
from core.paths import get_save_path


class SaveManager:
    """Centralized save/load manager for all game state."""

    SAVE_VERSION = "3.0"  # v3.0: Infinite world with seed-based generation

    def __init__(self):
        """Initialize the save manager."""
        self.ensure_save_directory()

    def ensure_save_directory(self):
        """Ensure the saves directory exists (handled by PathManager)."""
        # PathManager automatically creates save directory
        # This method kept for compatibility
        pass

    def create_save_data(
        self,
        character,
        world_system,
        quest_manager,
        npcs,
        dungeon_manager=None,
        game_time: float = 0.0,
        map_system=None
    ) -> Dict[str, Any]:
        """
        Create a comprehensive save data structure.

        Args:
            character: Character instance
            world_system: WorldSystem instance
            quest_manager: QuestManager instance
            npcs: List[NPC] instances
            dungeon_manager: DungeonManager instance (optional)
            game_time: Current game time for day/night cycle (optional)
            map_system: MapWaypointSystem instance (optional)

        Returns:
            Dictionary containing all save data
        """
        save_data = {
            "version": self.SAVE_VERSION,
            "save_timestamp": datetime.now().isoformat(),
            "player": self._serialize_character(character),
            "world_state": self._serialize_world_state(world_system, game_time),
            "quest_state": self._serialize_quest_state(quest_manager),
            "npc_state": self._serialize_npc_state(npcs),
            "game_settings": self._serialize_game_settings()
        }

        # Add dungeon state if dungeon system is active
        if dungeon_manager:
            save_data["dungeon_state"] = dungeon_manager.to_dict()

        # Add map/waypoint state if map system is active
        if map_system:
            save_data["map_state"] = map_system.get_save_data()

        return save_data

    def _serialize_game_settings(self) -> Dict[str, Any]:
        """
        Serialize game settings that should persist across saves.

        Returns:
            Dictionary containing game settings
        """
        from core.config import Config
        return {
            "keep_inventory": Config.KEEP_INVENTORY
        }

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
            "equipped_skills": list(character.skills.equipped_skills),
            "known_skills": {
                skill_id: {
                    "level": skill_data.level,
                    "experience": skill_data.experience
                }
                for skill_id, skill_data in character.skills.known_skills.items()
            },
            "titles": [title.title_id for title in character.titles.earned_titles],
            "activities": {
                activity: count
                for activity, count in character.activities.activity_counts.items()
            },
            "stat_tracker": character.stat_tracker.to_dict() if hasattr(character, 'stat_tracker') else {},
            "skill_unlocks": {
                "unlocked_skills": list(character.skill_unlocks.unlocked_skills) if hasattr(character, 'skill_unlocks') else [],
                "pending_unlocks": list(character.skill_unlocks.pending_unlocks) if hasattr(character, 'skill_unlocks') else []
            },
            "invented_recipes": self._serialize_invented_recipes(character)
        }

        return char_data

    def _serialize_invented_recipes(self, character) -> List[Dict[str, Any]]:
        """
        Serialize player-invented recipes for persistence.

        Args:
            character: Character instance

        Returns:
            List of invented recipe records with full recipe data
        """
        if not hasattr(character, 'invented_recipes'):
            return []

        serialized = []
        for recipe in character.invented_recipes:
            try:
                # Ensure all data is JSON-serializable
                recipe_record = {
                    "timestamp": recipe.get("timestamp", ""),
                    "discipline": recipe.get("discipline", "unknown"),
                    "item_id": recipe.get("item_id", ""),
                    "item_name": recipe.get("item_name", ""),
                    "item_data": recipe.get("item_data", {}),
                    "from_cache": recipe.get("from_cache", False),
                    # Recipe crafting data (for re-registering on load)
                    "recipe_inputs": recipe.get("recipe_inputs", []),
                    "station_tier": recipe.get("station_tier", 1),
                    "narrative": recipe.get("narrative", ""),
                    # Placement data for recipe recreation (new)
                    "placement_data": recipe.get("placement_data", {}),
                    # Icon path for invented item (new)
                    "icon_path": recipe.get("icon_path", "")
                }
                serialized.append(recipe_record)
            except Exception as e:
                print(f"Warning: Could not serialize invented recipe: {e}")

        return serialized

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
                        "efficiency": slot.equipment_data.efficiency,
                        "weight": slot.equipment_data.weight,
                        "range": slot.equipment_data.range,
                        "hand_type": slot.equipment_data.hand_type,
                        "item_type": slot.equipment_data.item_type,
                        "icon_path": slot.equipment_data.icon_path,
                        "soulbound": slot.equipment_data.soulbound,
                    }

                    # Save stat_multipliers if present
                    if slot.equipment_data.stat_multipliers:
                        slot_data["equipment_data"]["stat_multipliers"] = slot.equipment_data.stat_multipliers

                    # Save tags if present
                    if slot.equipment_data.tags:
                        slot_data["equipment_data"]["tags"] = slot.equipment_data.tags

                    # Save effect_tags if present
                    if slot.equipment_data.effect_tags:
                        slot_data["equipment_data"]["effect_tags"] = slot.equipment_data.effect_tags

                    # Save effect_params if present
                    if slot.equipment_data.effect_params:
                        slot_data["equipment_data"]["effect_params"] = slot.equipment_data.effect_params

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

    def _serialize_equipment(self, equipment_manager) -> Dict[str, Optional[Dict]]:
        """Serialize equipped items with full equipment data to preserve durability, enchantments, etc."""
        serialized_equipment = {}

        for slot_name, item in equipment_manager.slots.items():
            if item is None:
                serialized_equipment[slot_name] = None
            else:
                # Save full equipment data to preserve durability, enchantments, etc.
                equipment_data = {
                    "item_id": item.item_id,
                    "name": item.name,
                    "tier": item.tier,
                    "rarity": item.rarity,
                    "slot": item.slot,
                    "damage": list(item.damage) if isinstance(item.damage, tuple) else item.damage,
                    "defense": item.defense,
                    "durability_current": item.durability_current,
                    "durability_max": item.durability_max,
                    "attack_speed": item.attack_speed,
                    "efficiency": item.efficiency,
                    "weight": item.weight,
                    "range": item.range,
                    "hand_type": item.hand_type,
                    "item_type": item.item_type,
                    "icon_path": item.icon_path,
                    "soulbound": item.soulbound,
                }

                # Save stat_multipliers if present
                if item.stat_multipliers:
                    equipment_data["stat_multipliers"] = item.stat_multipliers

                # Save tags if present
                if item.tags:
                    equipment_data["tags"] = item.tags

                # Save effect_tags if present
                if item.effect_tags:
                    equipment_data["effect_tags"] = item.effect_tags

                # Save effect_params if present
                if item.effect_params:
                    equipment_data["effect_params"] = item.effect_params

                # Save bonuses if present
                if item.bonuses:
                    equipment_data["bonuses"] = item.bonuses

                # Save enchantments if present
                if item.enchantments:
                    equipment_data["enchantments"] = item.enchantments

                # Save requirements if present
                if item.requirements:
                    equipment_data["requirements"] = item.requirements

                serialized_equipment[slot_name] = equipment_data

        return serialized_equipment

    def _serialize_world_state(self, world_system, game_time: float = 0.0) -> Dict[str, Any]:
        """
        Serialize world state using the new infinite world system.

        The WorldSystem now handles its own serialization, including:
        - World seed for deterministic regeneration
        - Discovered dungeon entrances
        - Placed entities
        - Crafting stations
        - Modified chunks are saved to separate files

        Args:
            world_system: WorldSystem instance
            game_time: Current game time for day/night cycle

        Returns:
            Dictionary containing world state data
        """
        # Use WorldSystem's built-in save method
        world_data = world_system.get_save_state()

        # Ensure game_time is included (WorldSystem may use its internal time)
        world_data["game_time"] = game_time

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
        filename: str = "autosave.json",
        dungeon_manager=None,
        game_time: float = 0.0,
        map_system=None
    ) -> bool:
        """
        Save the current game state to a file.

        Args:
            character: Character instance
            world_system: WorldSystem instance
            quest_manager: QuestManager instance
            npcs: List[NPC] instances
            filename: Name of the save file
            dungeon_manager: DungeonManager instance (optional)
            game_time: Current game time for day/night cycle (optional)
            map_system: MapWaypointSystem instance (optional)

        Returns:
            True if save was successful, False otherwise
        """
        try:
            save_data = self.create_save_data(
                character,
                world_system,
                quest_manager,
                npcs,
                dungeon_manager,
                game_time,
                map_system
            )

            filepath = get_save_path(filename)

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
            filepath = get_save_path(filename)

            if not os.path.exists(filepath):
                print(f"Save file not found: {filepath}")
                return None

            with open(filepath, 'r') as f:
                save_data = json.load(f)

            # Validate save version
            version = save_data.get("version", "1.0")
            if version != self.SAVE_VERSION:
                print(f"Warning: Save file version {version} may not be compatible with current version {self.SAVE_VERSION}")

            # Restore game settings
            self.restore_game_settings(save_data)

            print(f"Game loaded successfully from {filepath}")
            return save_data

        except Exception as e:
            print(f"Error loading game: {e}")
            return None

    def restore_game_settings(self, save_data: Dict[str, Any]) -> bool:
        """
        Restore game settings from save data.

        Args:
            save_data: The loaded save data dictionary

        Returns:
            True if settings were restored, False otherwise
        """
        game_settings = save_data.get("game_settings")
        if not game_settings:
            # No game settings in save - use defaults
            return False

        from core.config import Config

        # Restore keep_inventory setting
        if "keep_inventory" in game_settings:
            Config.KEEP_INVENTORY = game_settings["keep_inventory"]
            print(f"   Restored Keep Inventory: {'ON' if Config.KEEP_INVENTORY else 'OFF'}")

        return True

    def restore_dungeon_state(self, save_data: Dict[str, Any], dungeon_manager) -> bool:
        """
        Restore dungeon state from save data.

        Args:
            save_data: The loaded save data dictionary
            dungeon_manager: DungeonManager instance to restore into

        Returns:
            True if dungeon state was restored, False otherwise
        """
        dungeon_state = save_data.get("dungeon_state")
        if not dungeon_state:
            # No dungeon state in save - that's fine for older saves
            return False

        try:
            # Import here to avoid circular dependency
            from systems.dungeon import DungeonManager

            # Restore dungeon manager state
            dungeon_manager.in_dungeon = dungeon_state.get("in_dungeon", False)
            dungeon_manager.dungeons_completed = dungeon_state.get("dungeons_completed", 0)
            dungeon_manager.dungeons_by_rarity = dungeon_state.get("dungeons_by_rarity", {})

            # Restore current dungeon if in dungeon
            if dungeon_state.get("current_dungeon"):
                from systems.dungeon import DungeonInstance
                dungeon_manager.current_dungeon = DungeonInstance.from_dict(
                    dungeon_state["current_dungeon"]
                )

            print(f"Restored dungeon state (in_dungeon={dungeon_manager.in_dungeon})")
            return True

        except Exception as e:
            print(f"Error restoring dungeon state: {e}")
            return False

    def get_save_files(self) -> List[Dict[str, Any]]:
        """
        Get list of all save files with metadata.

        Returns:
            List of dictionaries containing save file info
        """
        save_files = []

        save_dir = get_save_path()
        if not os.path.exists(save_dir):
            return save_files

        for filename in os.listdir(save_dir):
            if filename.endswith('.json'):
                filepath = get_save_path(filename)

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
            filepath = get_save_path(filename)

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

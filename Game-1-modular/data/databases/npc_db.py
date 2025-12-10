"""NPC Database - manages NPCs and quests"""

import json
from pathlib import Path
from typing import Dict
from data.models.npcs import NPCDefinition
from data.models.quests import QuestDefinition, QuestObjective, QuestRewards
from data.models.world import Position
from core.paths import get_resource_path


class NPCDatabase:
    """Singleton database of all NPCs"""
    _instance = None

    def __init__(self):
        self.npcs: Dict[str, NPCDefinition] = {}
        self.quests: Dict[str, QuestDefinition] = {}
        self.loaded = False

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def load_from_files(self):
        """Load NPCs and quests from JSON files (supports both v1.0 and v2.0 formats)"""
        try:
            # Try loading enhanced NPCs first, fallback to v1.0
            npc_files = [
                get_resource_path("progression/npcs-enhanced.JSON"),
                get_resource_path("progression/npcs-1.JSON")
            ]

            for npc_path in npc_files:
                if npc_path.exists():
                    with open(npc_path, 'r') as f:
                        data = json.load(f)
                        for npc_data in data.get("npcs", []):
                            pos_data = npc_data["position"]
                            position = Position(pos_data["x"], pos_data["y"], pos_data["z"])

                            # Support both old and new formats for dialogue
                            dialogue_lines = npc_data.get("dialogue_lines", [])
                            if not dialogue_lines and "dialogue" in npc_data:
                                # Enhanced format - extract dialogue_lines from dialogue object
                                dialogue_obj = npc_data["dialogue"]
                                if "dialogue_lines" in dialogue_obj:
                                    dialogue_lines = dialogue_obj["dialogue_lines"]
                                else:
                                    # Fallback to greeting messages
                                    greeting = dialogue_obj.get("greeting", {})
                                    dialogue_lines = [
                                        greeting.get("default", "Hello!"),
                                        greeting.get("questInProgress", "How goes your task?"),
                                        greeting.get("questComplete", "Well done!")
                                    ]

                            # Support both old and new interaction radius
                            interaction_radius = npc_data.get("interaction_radius", 3.0)
                            if "behavior" in npc_data:
                                interaction_radius = npc_data["behavior"].get("interactionRange", interaction_radius)

                            npc_def = NPCDefinition(
                                npc_id=npc_data["npc_id"],
                                name=npc_data["name"],
                                position=position,
                                sprite_color=tuple(npc_data["sprite_color"]),
                                interaction_radius=interaction_radius,
                                dialogue_lines=dialogue_lines,
                                quests=npc_data["quests"]
                            )
                            self.npcs[npc_def.npc_id] = npc_def
                    print(f"✓ Loaded {len(self.npcs)} NPCs from {npc_path.name}")
                    break

            # Try loading enhanced quests first, fallback to v1.0
            quest_files = [
                get_resource_path("progression/quests-enhanced.JSON"),
                get_resource_path("progression/quests-1.JSON")
            ]

            for quest_path in quest_files:
                if quest_path.exists():
                    with open(quest_path, 'r') as f:
                        data = json.load(f)
                        for quest_data in data.get("quests", []):
                            # Parse objectives (support both formats)
                            obj_data = quest_data["objectives"]

                            # Support both "type" and "objective_type"
                            obj_type = obj_data.get("type", obj_data.get("objective_type", "gather"))

                            objective = QuestObjective(
                                objective_type=obj_type,
                                items=obj_data.get("items", []),
                                enemies_killed=obj_data.get("enemies_killed", 0)
                            )

                            # Parse rewards (support both formats)
                            rew_data = quest_data["rewards"]
                            rewards = QuestRewards(
                                experience=rew_data.get("experience", 0),
                                gold=rew_data.get("gold", 0),
                                health_restore=rew_data.get("health_restore", 0),
                                mana_restore=rew_data.get("mana_restore", 0),
                                skills=rew_data.get("skills", []),
                                items=rew_data.get("items", []),
                                title=rew_data.get("title", ""),
                                stat_points=rew_data.get("statPoints", rew_data.get("stat_points", 0)),
                                status_effects=rew_data.get("status_effects", []),
                                buffs=rew_data.get("buffs", [])
                            )

                            # Support both "quest_id" and "questId", "title" and "name"
                            quest_id = quest_data.get("quest_id", quest_data.get("questId", ""))
                            title = quest_data.get("title", quest_data.get("name", "Untitled Quest"))

                            # Support both simple and complex description formats
                            description = quest_data.get("description", "")
                            if isinstance(description, dict):
                                description = description.get("long", description.get("short", ""))

                            # Support both "npc_id" and "givenBy"
                            npc_id = quest_data.get("npc_id", quest_data.get("givenBy", ""))

                            quest_def = QuestDefinition(
                                quest_id=quest_id,
                                title=title,
                                description=description,
                                npc_id=npc_id,
                                objectives=objective,
                                rewards=rewards,
                                completion_dialogue=quest_data.get("completion_dialogue", [])
                            )
                            self.quests[quest_def.quest_id] = quest_def
                    print(f"✓ Loaded {len(self.quests)} quests from {quest_path.name}")
                    break

            self.loaded = True
        except Exception as e:
            print(f"⚠ Failed to load NPCs/Quests: {e}")
            import traceback
            traceback.print_exc()
            self.loaded = False

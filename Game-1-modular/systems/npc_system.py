"""NPC system for managing non-player characters"""

import math
from typing import List, Optional

from data.models import NPCDefinition, Position
from systems.quest_system import QuestManager


class NPC:
    """Active NPC instance in the world"""
    def __init__(self, npc_def: NPCDefinition):
        self.npc_def = npc_def
        self.position = npc_def.position
        self.current_dialogue_index = 0

    def is_near(self, player_pos: Position) -> bool:
        """Check if player is within interaction radius"""
        dx = self.position.x - player_pos.x
        dy = self.position.y - player_pos.y
        distance = math.sqrt(dx * dx + dy * dy)
        return distance <= self.npc_def.interaction_radius

    def get_next_dialogue(self) -> str:
        """Get next dialogue line (cycles through)"""
        if not self.npc_def.dialogue_lines:
            return "..."

        dialogue = self.npc_def.dialogue_lines[self.current_dialogue_index]
        self.current_dialogue_index = (self.current_dialogue_index + 1) % len(self.npc_def.dialogue_lines)
        return dialogue

    def get_available_quests(self, quest_manager: QuestManager) -> List[str]:
        """Get list of quest_ids this NPC offers that player hasn't completed"""
        available = []
        for quest_id in self.npc_def.quests:
            if quest_id not in quest_manager.active_quests and quest_id not in quest_manager.completed_quests:
                available.append(quest_id)
        return available

    def has_quest_to_turn_in(self, quest_manager: QuestManager, character) -> Optional[str]:
        """Check if player has a completable quest from this NPC"""
        for quest_id in self.npc_def.quests:
            if quest_id in quest_manager.active_quests:
                quest = quest_manager.active_quests[quest_id]
                if quest.check_completion(character):
                    return quest_id
        return None

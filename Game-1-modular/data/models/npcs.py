"""NPC definition data model"""

from dataclasses import dataclass
from typing import List, Tuple
from .world import Position


@dataclass
class NPCDefinition:
    """NPC template from JSON"""
    npc_id: str
    name: str
    position: Position
    sprite_color: Tuple[int, int, int]
    interaction_radius: float
    dialogue_lines: List[str]
    quests: List[str]  # quest_ids this NPC offers

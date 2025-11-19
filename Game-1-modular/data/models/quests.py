"""Quest-related data models"""

from dataclasses import dataclass, field
from typing import List, Dict, Any


@dataclass
class QuestObjective:
    """Quest objective definition"""
    objective_type: str  # 'gather' or 'combat'
    items: List[Dict[str, Any]] = field(default_factory=list)  # For gather: [{"item_id": str, "quantity": int}]
    enemies_killed: int = 0  # For combat: number of enemies to kill


@dataclass
class QuestRewards:
    """Comprehensive quest rewards - supports multiple reward types"""
    # Core rewards
    experience: int = 0
    gold: int = 0

    # Restoration rewards
    health_restore: int = 0
    mana_restore: int = 0

    # Progression rewards
    skills: List[str] = field(default_factory=list)
    items: List[Dict[str, Any]] = field(default_factory=list)  # [{"item_id": str, "quantity": int}]
    title: str = ""  # Optional title reward
    stat_points: int = 0  # Free stat points to allocate

    # Future expansion - status effects, buffs, etc.
    status_effects: List[Dict[str, Any]] = field(default_factory=list)
    buffs: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class QuestDefinition:
    """Quest template from JSON"""
    quest_id: str
    title: str
    description: str
    npc_id: str
    objectives: QuestObjective
    rewards: QuestRewards
    completion_dialogue: List[str] = field(default_factory=list)

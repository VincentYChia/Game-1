"""Skill-related data models"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional


@dataclass
class SkillEffect:
    """Represents a skill's effect"""
    effect_type: str  # empower, quicken, fortify, etc.
    category: str  # mining, combat, smithing, etc.
    magnitude: str  # minor, moderate, major, extreme
    target: str  # self, enemy, area, resource_node
    duration: str  # instant, brief, moderate, long, extended
    additional_effects: List[Dict] = None

    def __post_init__(self):
        if self.additional_effects is None:
            self.additional_effects = []


@dataclass
class SkillCost:
    """Represents skill costs"""
    mana: str  # low, moderate, high, extreme
    cooldown: str  # short, moderate, long, extreme


@dataclass
class SkillEvolution:
    """Represents skill evolution data"""
    can_evolve: bool
    next_skill_id: Optional[str]
    requirement: str


@dataclass
class SkillRequirements:
    """Represents skill requirements"""
    character_level: int
    stats: Dict[str, int]
    titles: List[str]


@dataclass
class SkillDefinition:
    """Complete skill definition from JSON"""
    skill_id: str
    name: str
    tier: int
    rarity: str
    categories: List[str]
    description: str
    narrative: str
    tags: List[str]
    effect: SkillEffect
    cost: SkillCost
    evolution: SkillEvolution
    requirements: SkillRequirements


@dataclass
class PlayerSkill:
    """Player's learned skill instance"""
    skill_id: str
    level: int = 1
    experience: int = 0
    current_cooldown: float = 0.0  # Cooldown remaining in seconds
    is_equipped: bool = False  # Whether this skill is equipped to hotbar
    hotbar_slot: Optional[int] = None  # Which hotbar slot (1-5) or None

    def get_skill_def(self):
        """Get the skill definition from the database"""
        from data.databases.skill_db import SkillDatabase
        return SkillDatabase.get_instance().get_skill(self.skill_id)

    def can_use(self) -> bool:
        """Check if skill is off cooldown"""
        return self.current_cooldown <= 0

    def update_cooldown(self, dt: float):
        """Update cooldown timer"""
        if self.current_cooldown > 0:
            self.current_cooldown = max(0, self.current_cooldown - dt)

    def start_cooldown(self, cooldown_seconds: float):
        """Start cooldown timer"""
        self.current_cooldown = cooldown_seconds

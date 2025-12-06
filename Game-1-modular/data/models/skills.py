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
    icon_path: Optional[str] = None


@dataclass
class PlayerSkill:
    """Player's learned skill instance"""
    skill_id: str
    level: int = 1
    experience: int = 0
    current_cooldown: float = 0.0  # Cooldown remaining in seconds
    is_equipped: bool = False  # Whether this skill is equipped to hotbar
    hotbar_slot: Optional[int] = None  # Which hotbar slot (1-5) or None

    def get_definition(self) -> Optional['SkillDefinition']:
        """Get the full definition from SkillDatabase"""
        from data.databases.skill_db import SkillDatabase
        db = SkillDatabase.get_instance()
        return db.skills.get(self.skill_id, None)

    def get_exp_for_next_level(self) -> int:
        """Get EXP required to reach next level (exponential doubling)"""
        if self.level >= 10:
            return 0  # Max level
        # Level 1→2 = 1000, Level 2→3 = 2000, Level 3→4 = 4000, etc.
        return 1000 * (2 ** (self.level - 1))

    def add_exp(self, amount: int) -> tuple:
        """
        Add skill EXP and check for level up.
        Returns (leveled_up, new_level)
        """
        if self.level >= 10:
            return False, self.level  # Max level

        self.experience += amount
        leveled_up = False
        old_level = self.level

        # Check for level ups (can level multiple times if enough EXP)
        while self.level < 10:
            exp_needed = self.get_exp_for_next_level()
            if self.experience >= exp_needed:
                self.experience -= exp_needed
                self.level += 1
                leveled_up = True
                print(f"   🌟 Skill Level Up! {self.skill_id} → Level {self.level}")
            else:
                break

        return leveled_up, self.level if leveled_up else old_level

    def get_level_scaling_bonus(self) -> float:
        """Get effectiveness bonus from skill level (+10% per level)"""
        return 0.1 * (self.level - 1)  # Level 1 = +0%, Level 10 = +90%

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

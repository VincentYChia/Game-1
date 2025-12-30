"""Character class definition data model"""

from dataclasses import dataclass, field
from typing import Dict, List


@dataclass
class ClassDefinition:
    """Definition for a character class with tag-driven identity.

    Tags define the class's identity and can be used for:
    - Determining starting equipment affinities
    - Skill effectiveness bonuses (skills matching class tags get bonuses)
    - Narrative/lore classification
    - Future class-specific content gating
    """
    class_id: str
    name: str
    description: str
    bonuses: Dict[str, float]
    starting_skill: str = ""
    recommended_stats: List[str] = field(default_factory=list)
    # Tag-driven identity
    tags: List[str] = field(default_factory=list)
    # Combat style preferences (used for skill affinity)
    preferred_damage_types: List[str] = field(default_factory=list)
    preferred_armor_type: str = ""

    def has_tag(self, tag: str) -> bool:
        """Check if class has a specific tag"""
        return tag.lower() in [t.lower() for t in self.tags]

    def get_skill_affinity_bonus(self, skill_tags: List[str]) -> float:
        """Calculate skill affinity bonus based on tag overlap.

        Skills that match class tags get a damage/effectiveness bonus.
        Each matching tag adds 5% bonus, up to 20% max.
        """
        if not skill_tags or not self.tags:
            return 0.0

        matching_tags = set(t.lower() for t in self.tags) & set(t.lower() for t in skill_tags)
        bonus_per_tag = 0.05
        max_bonus = 0.20

        return min(len(matching_tags) * bonus_per_tag, max_bonus)

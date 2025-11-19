"""Character class definition data model"""

from dataclasses import dataclass, field
from typing import Dict, List


@dataclass
class ClassDefinition:
    """Definition for a character class"""
    class_id: str
    name: str
    description: str
    bonuses: Dict[str, float]
    starting_skill: str = ""
    recommended_stats: List[str] = field(default_factory=list)

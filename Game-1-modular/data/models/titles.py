"""Title definition data model"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class TitleDefinition:
    """Definition for an achievement title"""
    title_id: str
    name: str
    tier: str
    category: str
    activity_type: str
    acquisition_threshold: int
    bonus_description: str
    bonuses: Dict[str, float]
    prerequisites: List[str] = field(default_factory=list)
    hidden: bool = False
    acquisition_method: str = "guaranteed_milestone"  # or "random_drop", "hidden_discovery"
    icon_path: Optional[str] = None

"""Title definition data model"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional

from data.models.unlock_conditions import UnlockRequirements


@dataclass
class TitleDefinition:
    """Definition for an achievement title"""
    title_id: str
    name: str
    tier: str
    category: str
    bonus_description: str
    bonuses: Dict[str, float]
    requirements: UnlockRequirements  # NEW: Tag-driven requirements
    hidden: bool = False
    acquisition_method: str = "guaranteed_milestone"  # or "event_based_rng", "hidden_discovery", "special_achievement"
    generation_chance: float = 1.0  # For RNG-based acquisition (0.0-1.0)
    icon_path: Optional[str] = None

    # Legacy fields (deprecated but kept for backward compatibility)
    activity_type: str = "general"
    acquisition_threshold: int = 0
    prerequisites: List[str] = field(default_factory=list)

    # Phase 4 reverse cross-ref fields (2026-06-03). Optional; when set
    # by WES generation, signal that this title is bound to a specific
    # quest / NPC that birthed it. Tools use these for narrative
    # coherence (the title's prose can rhyme with the granting source).
    granted_by_quest_id: Optional[str] = None
    granted_by_npc_id: Optional[str] = None

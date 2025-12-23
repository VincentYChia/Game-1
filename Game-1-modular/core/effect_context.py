"""
Effect Context and Configuration
Defines the data structures for effect execution
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional


@dataclass
class EffectConfig:
    """
    Configuration for an effect parsed from tags
    This is the unified structure all effects use
    """
    # Source tags
    raw_tags: List[str] = field(default_factory=list)

    # Categorized tags
    geometry_tag: Optional[str] = None
    damage_tags: List[str] = field(default_factory=list)
    status_tags: List[str] = field(default_factory=list)
    context_tags: List[str] = field(default_factory=list)
    special_tags: List[str] = field(default_factory=list)
    trigger_tags: List[str] = field(default_factory=list)

    # Resolved context
    context: str = "enemy"  # "ally", "enemy", "self", "all", etc.

    # Base parameters
    base_damage: float = 0.0
    base_healing: float = 0.0

    # All effect parameters (merged defaults + user params)
    params: Dict[str, Any] = field(default_factory=dict)

    # Warnings/conflicts
    warnings: List[str] = field(default_factory=list)
    conflicts_resolved: List[str] = field(default_factory=list)


@dataclass
class EffectContext:
    """
    Runtime context for effect execution
    Contains source, target(s), and config
    """
    source: Any  # Entity that created the effect
    primary_target: Any  # Primary target entity
    config: EffectConfig  # Effect configuration
    timestamp: float = 0.0  # When effect was created
    targets: List[Any] = field(default_factory=list)  # All targets (after geometry)

    def __post_init__(self):
        if not self.targets and self.primary_target:
            self.targets = [self.primary_target]

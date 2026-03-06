"""
Combat event data structures for inter-system communication.

These events flow between the attack state machine, hitbox system,
projectile system, and the game engine. They are the contract between
combat subsystems.
"""

from dataclasses import dataclass, field
from typing import Optional, Tuple, Set, Dict, Any


@dataclass
class CombatEvent:
    """Emitted by combat systems for other systems to react to."""

    event_type: str          # "phase_change", "hit_landed", "attack_start", "projectile_spawn"
    source_id: str           # Entity that caused this event
    target_id: Optional[str] = None
    data: Optional[Dict[str, Any]] = None

    def __post_init__(self):
        if self.data is None:
            self.data = {}


@dataclass
class HitEvent:
    """Emitted when a hitbox or projectile overlaps a hurtbox."""

    attacker_id: str
    target_id: str
    damage_context: Dict[str, Any]                   # Preserved from attack start
    hit_position: Tuple[float, float] = (0.0, 0.0)   # World position of the hit
    is_projectile: bool = False                       # True if from projectile, not melee hitbox

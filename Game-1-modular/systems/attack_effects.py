"""
Attack Effects System - Visual feedback for combat

This module provides visual effects for attacks including:
- Attack lines (blue for player/turret, red for enemy)
- Hit particles
- Blocked attack indicators

Effects are rendered by the Renderer and fade out over time.
"""

from typing import List, Tuple, Optional, Dict, Any
from dataclasses import dataclass, field
from enum import Enum
import time


class AttackEffectType(Enum):
    """Types of attack effects"""
    LINE = "line"  # A line from attacker to target
    BLOCKED = "blocked"  # Attack blocked indicator (X mark)
    HIT_PARTICLE = "hit_particle"  # Small particles at hit location
    AREA = "area"  # Circle effect for AoE attacks


class AttackSourceType(Enum):
    """Source of the attack for color determination"""
    PLAYER = "player"  # Blue
    TURRET = "turret"  # Cyan/light blue
    ENEMY = "enemy"  # Red
    ENVIRONMENT = "environment"  # Orange


@dataclass
class AttackEffect:
    """A visual effect to render"""
    effect_type: AttackEffectType
    source_type: AttackSourceType
    start_pos: Tuple[float, float]  # World coordinates
    end_pos: Tuple[float, float]  # World coordinates (same as start for non-lines)
    start_time: float
    duration: float = 0.3  # Seconds before fade out
    blocked: bool = False  # If this attack was blocked
    damage: float = 0.0  # For scaling effect intensity
    tags: List[str] = field(default_factory=list)  # Attack tags for special effects

    @property
    def age(self) -> float:
        """Get the age of this effect in seconds"""
        return time.time() - self.start_time

    @property
    def alpha(self) -> float:
        """Get the alpha value (0.0-1.0) for fading"""
        age = self.age
        if age >= self.duration:
            return 0.0
        # Quick fade in, slow fade out
        fade_start = self.duration * 0.7
        if age < fade_start:
            return 1.0
        return 1.0 - ((age - fade_start) / (self.duration - fade_start))

    @property
    def is_expired(self) -> bool:
        """Check if this effect should be removed"""
        return self.age >= self.duration

    def get_color(self) -> Tuple[int, int, int, int]:
        """Get RGBA color based on source type"""
        alpha = int(self.alpha * 255)

        if self.blocked:
            # Blocked attacks are yellow with X
            return (255, 200, 0, alpha)

        if self.source_type == AttackSourceType.PLAYER:
            # Player attacks are blue
            return (50, 150, 255, alpha)
        elif self.source_type == AttackSourceType.TURRET:
            # Turret attacks are cyan
            return (0, 220, 255, alpha)
        elif self.source_type == AttackSourceType.ENEMY:
            # Enemy attacks are red
            return (255, 50, 50, alpha)
        else:
            # Environment/other is orange
            return (255, 150, 50, alpha)

    def get_line_width(self) -> int:
        """Get line width based on damage and effect type"""
        base_width = 2
        if self.damage > 50:
            base_width = 4
        elif self.damage > 20:
            base_width = 3

        # Fade line width slightly
        return max(1, int(base_width * self.alpha))


class AttackEffectsManager:
    """
    Manages all active attack effects.

    Usage:
        manager = get_attack_effects_manager()
        manager.add_attack_line(source_pos, target_pos, source_type, ...)
        manager.update()  # Call each frame to remove expired effects
        effects = manager.get_active_effects()  # Renderer draws these
    """

    def __init__(self):
        self.effects: List[AttackEffect] = []
        self.max_effects = 100  # Prevent memory issues

    def add_attack_line(self,
                        source_pos: Tuple[float, float],
                        target_pos: Tuple[float, float],
                        source_type: AttackSourceType,
                        damage: float = 0.0,
                        blocked: bool = False,
                        tags: Optional[List[str]] = None,
                        duration: float = 0.3):
        """
        Add an attack line effect.

        Args:
            source_pos: (x, y) world position of attacker
            target_pos: (x, y) world position of target
            source_type: Type of attacker for color
            damage: Damage amount for scaling effect
            blocked: True if attack was blocked
            tags: Attack tags for special effects
            duration: How long effect lasts
        """
        effect = AttackEffect(
            effect_type=AttackEffectType.LINE,
            source_type=source_type,
            start_pos=source_pos,
            end_pos=target_pos,
            start_time=time.time(),
            duration=duration,
            blocked=blocked,
            damage=damage,
            tags=tags or []
        )

        self._add_effect(effect)

    def add_blocked_indicator(self,
                              position: Tuple[float, float],
                              source_type: AttackSourceType,
                              duration: float = 0.5):
        """
        Add a blocked attack indicator (shows where attack was blocked).

        Args:
            position: (x, y) world position where blocked
            source_type: Type of attacker for color context
            duration: How long indicator lasts
        """
        effect = AttackEffect(
            effect_type=AttackEffectType.BLOCKED,
            source_type=source_type,
            start_pos=position,
            end_pos=position,
            start_time=time.time(),
            duration=duration,
            blocked=True
        )

        self._add_effect(effect)

    def add_area_effect(self,
                        center_pos: Tuple[float, float],
                        radius: float,
                        source_type: AttackSourceType,
                        duration: float = 0.4):
        """
        Add an area effect indicator (for AoE attacks).

        Args:
            center_pos: (x, y) center of AoE
            radius: Radius of effect in tiles
            source_type: Type of attacker for color
            duration: How long effect lasts
        """
        effect = AttackEffect(
            effect_type=AttackEffectType.AREA,
            source_type=source_type,
            start_pos=center_pos,
            # Use end_pos to store radius (hacky but works)
            end_pos=(center_pos[0] + radius, center_pos[1]),
            start_time=time.time(),
            duration=duration,
            damage=0.0,
            tags=['circle']
        )

        self._add_effect(effect)

    def _add_effect(self, effect: AttackEffect):
        """Add effect to list, pruning old ones if needed"""
        self.effects.append(effect)

        # Prune expired effects if over limit
        if len(self.effects) > self.max_effects:
            self.effects = [e for e in self.effects if not e.is_expired]

    def update(self):
        """Update effects and remove expired ones"""
        self.effects = [e for e in self.effects if not e.is_expired]

    def get_active_effects(self) -> List[AttackEffect]:
        """Get all currently active effects for rendering"""
        return [e for e in self.effects if not e.is_expired]

    def clear(self):
        """Clear all effects"""
        self.effects.clear()


# Global singleton instance
_attack_effects_manager: Optional[AttackEffectsManager] = None


def get_attack_effects_manager() -> AttackEffectsManager:
    """Get the global attack effects manager instance."""
    global _attack_effects_manager
    if _attack_effects_manager is None:
        _attack_effects_manager = AttackEffectsManager()
    return _attack_effects_manager

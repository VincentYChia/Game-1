"""
Attack Effects System — Tag-driven visual feedback for combat.

Replaces the old blue/red line system with prominent, tag-colored effects:
- Slash arcs (melee weapons)
- Impact bursts (on hit)
- Blocked indicators
- Area-of-effect rings

All colors are driven by damage type tags (fire, ice, etc.).
Effects are rendered by the Renderer and fade out over time.
"""

import math
import time
from typing import List, Tuple, Optional, Dict, Any
from dataclasses import dataclass, field
from enum import Enum


class AttackEffectType(Enum):
    """Types of attack effects"""
    SLASH_ARC = "slash_arc"       # Sweeping arc effect (replaces old LINE)
    IMPACT_BURST = "impact_burst" # Radial burst at hit point
    BLOCKED = "blocked"           # Attack blocked indicator
    AREA = "area"                 # Circle effect for AoE attacks
    THRUST = "thrust"             # Forward thrust line (spears, daggers)


class AttackSourceType(Enum):
    """Source of the attack for fallback color"""
    PLAYER = "player"
    TURRET = "turret"
    ENEMY = "enemy"
    ENVIRONMENT = "environment"


# Tag -> color mapping for element-driven visuals
_ELEMENT_COLORS = {
    "physical": (220, 220, 240),
    "slashing": (230, 230, 250),
    "crushing": (200, 200, 220),
    "piercing": (210, 220, 240),
    "fire": (255, 120, 30),
    "ice": (100, 200, 255),
    "frost": (100, 200, 255),
    "lightning": (255, 255, 80),
    "poison": (100, 255, 80),
    "arcane": (180, 80, 255),
    "shadow": (130, 80, 180),
    "holy": (255, 255, 180),
}

# Source type -> fallback color (only used when no tags)
_SOURCE_FALLBACK_COLORS = {
    AttackSourceType.PLAYER: (150, 200, 255),
    AttackSourceType.TURRET: (0, 220, 255),
    AttackSourceType.ENEMY: (255, 80, 60),
    AttackSourceType.ENVIRONMENT: (255, 150, 50),
}


def color_from_tags(tags: List[str],
                    source_type: AttackSourceType = AttackSourceType.PLAYER) -> Tuple[int, int, int]:
    """Get effect color from tags, falling back to source-based color."""
    for tag in tags:
        if tag in _ELEMENT_COLORS:
            return _ELEMENT_COLORS[tag]
    return _SOURCE_FALLBACK_COLORS.get(source_type, (220, 220, 240))


@dataclass
class AttackEffect:
    """A visual effect to render. Tag-driven colors."""
    effect_type: AttackEffectType
    source_type: AttackSourceType
    start_pos: Tuple[float, float]     # World coordinates (attacker)
    end_pos: Tuple[float, float]       # World coordinates (target/endpoint)
    start_time: float
    duration: float = 1.05             # Seconds (3x longer for visible animation)
    blocked: bool = False
    damage: float = 0.0
    tags: List[str] = field(default_factory=list)
    facing_angle: float = 0.0          # Degrees, for arc direction
    arc_degrees: float = 55.0          # Width of slash arc (default moderate)
    radius: float = 1.5               # Reach of the effect in tiles

    @property
    def age(self) -> float:
        return time.time() - self.start_time

    @property
    def alpha(self) -> float:
        age = self.age
        if age >= self.duration:
            return 0.0
        # Quick bright start, smooth fade
        fade_start = self.duration * 0.5
        if age < fade_start:
            return 1.0
        return 1.0 - ((age - fade_start) / (self.duration - fade_start))

    @property
    def is_expired(self) -> bool:
        return self.age >= self.duration

    def get_color(self) -> Tuple[int, int, int, int]:
        """Get RGBA color from tags."""
        if self.blocked:
            return (255, 200, 0, int(self.alpha * 255))
        base = color_from_tags(self.tags, self.source_type)
        return (*base, int(self.alpha * 255))

    def get_line_width(self) -> int:
        """Scale width with damage for impact effects."""
        base = 3
        if self.damage > 50:
            base = 5
        elif self.damage > 20:
            base = 4
        return max(2, int(base * max(0.4, self.alpha)))


class AttackEffectsManager:
    """Manages tag-driven attack visual effects."""

    def __init__(self):
        self.effects: List[AttackEffect] = []
        self.max_effects = 100

    def add_attack_effect(self,
                          source_pos: Tuple[float, float],
                          target_pos: Tuple[float, float],
                          source_type: AttackSourceType,
                          damage: float = 0.0,
                          blocked: bool = False,
                          tags: Optional[List[str]] = None,
                          duration: float = 1.5,
                          facing_angle: float = 0.0,
                          arc_degrees: float = 55.0,
                          radius: float = 1.5):
        """Add a prominent slash arc or thrust effect.

        Automatically picks SLASH_ARC for melee or THRUST for piercing/spear.
        """
        tags = tags or ['physical']

        # Determine effect type from tags
        is_thrust = any(t in tags for t in ('piercing', 'spear', 'thrust', 'dagger'))
        effect_type = AttackEffectType.THRUST if is_thrust else AttackEffectType.SLASH_ARC

        if blocked:
            effect_type = AttackEffectType.BLOCKED

        effect = AttackEffect(
            effect_type=effect_type,
            source_type=source_type,
            start_pos=source_pos,
            end_pos=target_pos,
            start_time=time.time(),
            duration=duration,
            blocked=blocked,
            damage=damage,
            tags=tags,
            facing_angle=facing_angle,
            arc_degrees=arc_degrees,
            radius=radius,
        )
        self._add_effect(effect)

    def add_attack_line(self,
                        source_pos: Tuple[float, float],
                        target_pos: Tuple[float, float],
                        source_type: AttackSourceType,
                        damage: float = 0.0,
                        blocked: bool = False,
                        tags: Optional[List[str]] = None,
                        duration: float = 1.05):
        """Backward-compatible: converts old line calls to slash arcs."""
        dx = target_pos[0] - source_pos[0]
        dy = target_pos[1] - source_pos[1]
        angle = math.degrees(math.atan2(dy, dx))
        dist = math.sqrt(dx * dx + dy * dy)
        self.add_attack_effect(
            source_pos, target_pos, source_type, damage, blocked,
            tags, duration, facing_angle=angle, radius=max(1.0, dist))

    def add_impact_burst(self,
                         position: Tuple[float, float],
                         source_type: AttackSourceType,
                         damage: float = 0.0,
                         tags: Optional[List[str]] = None,
                         duration: float = 1.35):
        """Add a radial impact burst at hit location. Prominent and bright."""
        tags = tags or ['physical']
        effect = AttackEffect(
            effect_type=AttackEffectType.IMPACT_BURST,
            source_type=source_type,
            start_pos=position,
            end_pos=position,
            start_time=time.time(),
            duration=duration,
            damage=damage,
            tags=tags,
            radius=max(0.5, damage / 30.0),  # Scale with damage
        )
        self._add_effect(effect)

    def add_blocked_indicator(self,
                              position: Tuple[float, float],
                              source_type: AttackSourceType,
                              duration: float = 1.5):
        """Add blocked attack indicator."""
        effect = AttackEffect(
            effect_type=AttackEffectType.BLOCKED,
            source_type=source_type,
            start_pos=position,
            end_pos=position,
            start_time=time.time(),
            duration=duration,
            blocked=True,
        )
        self._add_effect(effect)

    def add_area_effect(self,
                        center_pos: Tuple[float, float],
                        radius: float,
                        source_type: AttackSourceType,
                        tags: Optional[List[str]] = None,
                        duration: float = 1.8):
        """Add AoE ring effect."""
        tags = tags or ['physical']
        effect = AttackEffect(
            effect_type=AttackEffectType.AREA,
            source_type=source_type,
            start_pos=center_pos,
            end_pos=(center_pos[0] + radius, center_pos[1]),
            start_time=time.time(),
            duration=duration,
            tags=tags,
            radius=radius,
        )
        self._add_effect(effect)

    def _add_effect(self, effect: AttackEffect):
        self.effects.append(effect)
        if len(self.effects) > self.max_effects:
            self.effects = [e for e in self.effects if not e.is_expired]

    def update(self):
        self.effects = [e for e in self.effects if not e.is_expired]

    def get_active_effects(self) -> List[AttackEffect]:
        return [e for e in self.effects if not e.is_expired]

    def clear(self):
        self.effects.clear()


# Global singleton
_attack_effects_manager: Optional[AttackEffectsManager] = None


def get_attack_effects_manager() -> AttackEffectsManager:
    """Get the global attack effects manager instance."""
    global _attack_effects_manager
    if _attack_effects_manager is None:
        _attack_effects_manager = AttackEffectsManager()
    return _attack_effects_manager

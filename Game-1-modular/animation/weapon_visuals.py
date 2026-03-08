"""
Tag-driven weapon animation styling.

Resolves weapon tags, type, tier, weight, and element to concrete visual
parameters for attack animations. The renderer reads these to produce
visually distinct weapon swings.

Design philosophy: a fire-enchanted T3 greatsword should look and feel
fundamentally different from a T1 dagger or a lightning staff — different
arc width, trail length, color, particle density, and motion curve.
"""

import math
from typing import Dict, List, Tuple, Optional, Any


# Element tag -> base color (vibrant, saturated for readability)
ELEMENT_COLORS = {
    "physical": (220, 225, 245),
    "fire":     (255, 120, 25),
    "ice":      (90, 200, 255),
    "frost":    (90, 200, 255),
    "lightning": (255, 255, 70),
    "poison":   (90, 255, 70),
    "arcane":   (190, 70, 255),
    "shadow":   (140, 70, 200),
    "holy":     (255, 255, 170),
    "chaos":    (220, 50, 50),
}

# Weapon type -> base visual profile
# arc: sweep width in degrees
# trail: how many trailing frames linger
# thickness: line thickness multiplier (1.0 = default)
# motion: "swing" (decelerate), "thrust" (extend), "spin" (full rotation)
_WEAPON_VISUAL_PROFILES = {
    "sword_1h":  {"arc": 65, "trail": 3, "thickness": 1.0, "motion": "swing"},
    "sword_2h":  {"arc": 100, "trail": 4, "thickness": 1.4, "motion": "swing"},
    "dagger":    {"arc": 30, "trail": 2, "thickness": 0.6, "motion": "swing"},
    "axe":       {"arc": 80, "trail": 4, "thickness": 1.3, "motion": "swing"},
    "mace":      {"arc": 55, "trail": 3, "thickness": 1.2, "motion": "swing"},
    "hammer_2h": {"arc": 90, "trail": 5, "thickness": 1.6, "motion": "swing"},
    "spear":     {"arc": 12, "trail": 2, "thickness": 0.8, "motion": "thrust"},
    "staff":     {"arc": 35, "trail": 3, "thickness": 0.7, "motion": "swing"},
    "bow":       {"arc": 0, "trail": 0, "thickness": 0.5, "motion": "none"},
    "unarmed":   {"arc": 55, "trail": 2, "thickness": 0.8, "motion": "swing"},
}

# Tier -> visual intensity multiplier
_TIER_INTENSITY = {1: 0.7, 2: 1.0, 3: 1.3, 4: 1.6}


class WeaponVisualStyle:
    """Resolved visual parameters for a specific weapon's attack animation."""

    __slots__ = ('arc_degrees', 'trail_frames', 'thickness', 'motion_type',
                 'color', 'glow_color', 'glow_intensity', 'particle_density',
                 'screen_shake_intensity', 'trail_alpha_base',
                 'speed_feel', 'impact_flash')

    def __init__(self):
        # Geometry
        self.arc_degrees: float = 65.0
        self.trail_frames: int = 3
        self.thickness: float = 1.0
        self.motion_type: str = "swing"  # swing, thrust, spin, none

        # Color
        self.color: Tuple[int, int, int] = (220, 225, 245)
        self.glow_color: Tuple[int, int, int] = (255, 255, 255)
        self.glow_intensity: float = 0.3

        # Effects
        self.particle_density: float = 1.0
        self.screen_shake_intensity: float = 0.0
        self.trail_alpha_base: int = 180
        self.speed_feel: float = 1.0  # <1 = heavy/slow, >1 = fast/light
        self.impact_flash: bool = False


def resolve_weapon_visual(weapon_type: str,
                          weapon_tags: List[str],
                          tier: int = 1,
                          weight: float = 1.0,
                          attack_speed: float = 1.0) -> WeaponVisualStyle:
    """Resolve weapon properties into concrete visual parameters.

    Args:
        weapon_type: Equipment type (sword_1h, axe, dagger, etc.)
        weapon_tags: All tags on the weapon (element, material, special)
        tier: Weapon tier (1-4)
        weight: Weapon weight from JSON (affects swing feel)
        attack_speed: Weapon attack speed (affects animation speed)

    Returns:
        WeaponVisualStyle with all animation parameters resolved.
    """
    style = WeaponVisualStyle()

    # 1. Base profile from weapon type
    profile = _WEAPON_VISUAL_PROFILES.get(weapon_type, _WEAPON_VISUAL_PROFILES["unarmed"])
    style.arc_degrees = profile["arc"]
    style.trail_frames = profile["trail"]
    style.thickness = profile["thickness"]
    style.motion_type = profile["motion"]

    # 2. Element color from tags (first matching element wins)
    style.color = ELEMENT_COLORS.get("physical", (220, 225, 245))
    for tag in weapon_tags:
        if tag in ELEMENT_COLORS:
            style.color = ELEMENT_COLORS[tag]
            break

    # 3. Glow color: brighter version of element color
    style.glow_color = tuple(min(255, c + 60) for c in style.color)

    # 4. Tier scaling — higher tier = more intense visuals
    intensity = _TIER_INTENSITY.get(tier, 1.0)
    style.glow_intensity = 0.2 + intensity * 0.2
    style.particle_density = 0.5 + intensity * 0.5
    style.trail_alpha_base = int(140 + intensity * 40)
    style.trail_frames = max(2, int(style.trail_frames * (0.8 + intensity * 0.3)))

    # 5. Weight affects swing feel — heavier = slower but more impactful
    if weight > 3.0:
        style.speed_feel = max(0.6, 1.0 - (weight - 3.0) * 0.1)
        style.screen_shake_intensity = min(1.0, (weight - 3.0) * 0.15)
        style.thickness *= 1.0 + (weight - 3.0) * 0.1
        style.impact_flash = True
    elif weight < 1.0:
        style.speed_feel = min(1.5, 1.0 + (1.0 - weight) * 0.3)
        style.screen_shake_intensity = 0.0
    else:
        style.speed_feel = 1.0

    # 6. Attack speed modifies trail length and alpha
    if attack_speed > 1.2:
        style.trail_frames = max(2, style.trail_frames - 1)
        style.trail_alpha_base = max(100, style.trail_alpha_base - 30)
    elif attack_speed < 0.8:
        style.trail_frames += 1
        style.trail_alpha_base = min(220, style.trail_alpha_base + 20)

    # 7. Special tag modifiers
    if "critical" in weapon_tags or "execute" in weapon_tags:
        style.impact_flash = True
        style.screen_shake_intensity += 0.2

    if "lifesteal" in weapon_tags:
        # Lifesteal weapons get a reddish glow
        style.glow_color = (255, 80, 80)
        style.glow_intensity = min(1.0, style.glow_intensity + 0.15)

    if "chain" in weapon_tags or "chain_damage" in weapon_tags:
        style.particle_density *= 1.5

    return style


def get_attack_trail_color(style: WeaponVisualStyle,
                           progress: float) -> Tuple[int, int, int, int]:
    """Get trail color with alpha for a given animation progress (0.0-1.0).

    Trail brightens at the leading edge and fades behind.
    """
    # Leading edge is bright, trail fades
    if progress < 0.3:
        alpha = int(style.trail_alpha_base * (progress / 0.3))
    elif progress < 0.7:
        alpha = style.trail_alpha_base
    else:
        alpha = int(style.trail_alpha_base * (1.0 - (progress - 0.7) / 0.3))

    return (*style.color, max(0, min(255, alpha)))


def get_impact_color(style: WeaponVisualStyle) -> Tuple[int, int, int]:
    """Get the color for hit impact flash/sparks."""
    # Brighten the element color for impact
    return tuple(min(255, c + 80) for c in style.color)

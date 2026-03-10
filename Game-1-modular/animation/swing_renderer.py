"""
Procedural swing effect frame generator.

Pre-renders multi-layered attack animation frames at startup, replacing
raw pygame.draw.arc/polygon/line calls with polished, composited surfaces.

Each swing is rendered as stacked layers:
  Layer 1 — Motion Trail: Gradient-filled crescent with alpha falloff
  Layer 2 — Blade Edge: Bright leading edge with Gaussian-approximated glow
  Layer 3 — Afterimage Echoes: Fading copies of the blade at prior positions
  Layer 4 — Spark Particles: Bright dots scattered along the sweep path

Cache key = (weapon_type, element, tier) — typically <30 unique combinations.
Memory: ~8 frames × ~128x128 px × 4 bytes × 30 combos ≈ 15MB (negligible).
"""

import math
import random
from typing import Dict, List, Tuple, Optional

import pygame

from animation.weapon_visuals import (
    WeaponVisualStyle, resolve_weapon_visual,
    ELEMENT_COLORS, _WEAPON_VISUAL_PROFILES,
)


# Frame count per swing animation
DEFAULT_SWING_FRAMES = 8
DEFAULT_THRUST_FRAMES = 6
DEFAULT_RADIAL_FRAMES = 6

# Surface sizing: base size per tile-radius unit
BASE_SURFACE_SIZE = 128


def _ease_out_cubic(t: float) -> float:
    """Decelerating ease-out curve — fast start, slow finish."""
    return 1.0 - (1.0 - t) ** 3


def _ease_in_out_quad(t: float) -> float:
    """Smooth acceleration then deceleration."""
    if t < 0.5:
        return 2.0 * t * t
    return 1.0 - (-2.0 * t + 2.0) ** 2 / 2.0


def _brighten(color: Tuple[int, int, int], amount: int = 60) -> Tuple[int, int, int]:
    return tuple(min(255, c + amount) for c in color)


def _with_alpha(color: Tuple[int, int, int], alpha: int) -> Tuple[int, int, int, int]:
    return (*color, max(0, min(255, alpha)))


class SwingEffectRenderer:
    """Pre-renders procedural attack animation frames, cached by weapon style.

    Usage:
        renderer = SwingEffectRenderer.get_instance()
        frames = renderer.get_swing_frames(style, radius_px)
        # In render loop:
        frame_idx = int(progress * (len(frames) - 1))
        screen.blit(frames[frame_idx], (x - center, y - center))
    """

    _instance: Optional['SwingEffectRenderer'] = None

    @classmethod
    def get_instance(cls) -> 'SwingEffectRenderer':
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self):
        self._swing_cache: Dict[tuple, List[pygame.Surface]] = {}
        self._thrust_cache: Dict[tuple, List[pygame.Surface]] = {}
        self._radial_cache: Dict[tuple, List[pygame.Surface]] = {}

    def _cache_key(self, style: WeaponVisualStyle, radius_px: int) -> tuple:
        """Build a hashable cache key from style parameters."""
        return (
            int(style.arc_degrees),
            style.motion_type,
            style.color,
            int(style.thickness * 10),
            int(style.glow_intensity * 10),
            int(style.trail_alpha_base),
            radius_px,
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_swing_frames(self, style: WeaponVisualStyle,
                         radius_px: int) -> List[pygame.Surface]:
        """Get or generate cached swing animation frames."""
        key = self._cache_key(style, radius_px)
        if key not in self._swing_cache:
            self._swing_cache[key] = self._generate_swing(style, radius_px)
        return self._swing_cache[key]

    def get_thrust_frames(self, style: WeaponVisualStyle,
                          length_px: int) -> List[pygame.Surface]:
        """Get or generate cached thrust animation frames."""
        key = self._cache_key(style, length_px)
        if key not in self._thrust_cache:
            self._thrust_cache[key] = self._generate_thrust(style, length_px)
        return self._thrust_cache[key]

    def get_radial_frames(self, style: WeaponVisualStyle,
                          radius_px: int) -> List[pygame.Surface]:
        """Get or generate cached radial burst frames."""
        key = self._cache_key(style, radius_px)
        if key not in self._radial_cache:
            self._radial_cache[key] = self._generate_radial(style, radius_px)
        return self._radial_cache[key]

    def get_enemy_swing_frames(self, enemy_color: Tuple[int, int, int],
                               arc_degrees: float, radius_px: int,
                               thickness: float = 1.0) -> List[pygame.Surface]:
        """Get swing frames for enemy attacks with specific color."""
        # Build a lightweight style for the enemy
        style = WeaponVisualStyle()
        style.arc_degrees = arc_degrees
        style.color = enemy_color
        style.glow_color = _brighten(enemy_color, 40)
        style.thickness = thickness
        style.glow_intensity = 0.5
        style.trail_alpha_base = 160
        style.trail_frames = 3
        style.particle_density = 0.8
        return self.get_swing_frames(style, radius_px)

    def get_enemy_thrust_frames(self, enemy_color: Tuple[int, int, int],
                                length_px: int,
                                thickness: float = 0.8) -> List[pygame.Surface]:
        """Get thrust frames for enemy attacks."""
        style = WeaponVisualStyle()
        style.color = enemy_color
        style.glow_color = _brighten(enemy_color, 40)
        style.thickness = thickness
        style.glow_intensity = 0.5
        style.trail_alpha_base = 150
        style.motion_type = "thrust"
        return self.get_thrust_frames(style, length_px)

    def get_enemy_radial_frames(self, enemy_color: Tuple[int, int, int],
                                radius_px: int,
                                thickness: float = 1.0) -> List[pygame.Surface]:
        """Get radial burst frames for enemy circle attacks."""
        style = WeaponVisualStyle()
        style.color = enemy_color
        style.glow_color = _brighten(enemy_color, 40)
        style.thickness = thickness
        style.glow_intensity = 0.5
        style.trail_alpha_base = 140
        style.particle_density = 0.6
        return self.get_radial_frames(style, radius_px)

    def clear_cache(self):
        """Clear all cached frames."""
        self._swing_cache.clear()
        self._thrust_cache.clear()
        self._radial_cache.clear()

    # ------------------------------------------------------------------
    # Swing (arc) generation — Layer 1-4
    # ------------------------------------------------------------------

    def _generate_swing(self, style: WeaponVisualStyle,
                        radius_px: int) -> List[pygame.Surface]:
        """Generate swing arc frames.

        Frames are drawn pointing RIGHT (0°). The renderer rotates them
        to match the attack's facing_angle at blit time.
        """
        num_frames = DEFAULT_SWING_FRAMES
        glow_pad = int(10 * (0.6 + style.glow_intensity))
        surf_size = radius_px * 2 + glow_pad * 2
        center = surf_size // 2
        arc_deg = style.arc_degrees
        half_arc = arc_deg / 2.0

        color = style.color
        bright = _brighten(color, 60)
        white = (255, 255, 255)
        thickness = style.thickness

        frames: List[pygame.Surface] = []

        for f in range(num_frames):
            t = f / max(1, num_frames - 1)  # 0.0 → 1.0
            sweep = _ease_out_cubic(t)

            surf = pygame.Surface((surf_size, surf_size), pygame.SRCALPHA)

            # The sweep goes from -half_arc to +half_arc (centered on 0°/right)
            sweep_angle_rad = math.radians(-half_arc + arc_deg * sweep)

            # -- Layer 1: Motion Trail (gradient crescent) --
            self._draw_trail_crescent(
                surf, center, radius_px, glow_pad, color,
                arc_deg, half_arc, sweep, t, style)

            # -- Layer 3: Afterimage Echoes (draw before blade so blade is on top) --
            self._draw_afterimages(
                surf, center, radius_px, glow_pad, color, bright,
                half_arc, arc_deg, sweep, thickness, t, style)

            # -- Layer 2: Blade Edge with glow --
            self._draw_blade_edge(
                surf, center, radius_px, glow_pad, color, bright, white,
                sweep_angle_rad, thickness, t, style)

            # -- Layer 4: Spark Particles --
            self._draw_sparks(
                surf, center, radius_px, glow_pad, bright, white,
                half_arc, arc_deg, sweep, thickness, t, style)

            frames.append(surf)

        return frames

    def _draw_trail_crescent(self, surf: pygame.Surface, center: int,
                             radius_px: int, glow_pad: int,
                             color: Tuple[int, int, int],
                             arc_deg: float, half_arc: float,
                             sweep: float, t: float,
                             style: WeaponVisualStyle):
        """Layer 1: Gradient-filled crescent trailing behind the blade."""
        if sweep < 0.02:
            return

        num_trail_layers = 4
        for layer in range(num_trail_layers):
            # Each layer covers less of the swept arc and is more transparent
            layer_sweep = max(0.0, sweep - layer * 0.08)
            if layer_sweep <= 0:
                continue

            # Alpha decreases for outer layers and fades late in animation
            fade = 1.0 if t < 0.7 else max(0.0, (1.0 - t) / 0.3)
            base_alpha = int(style.trail_alpha_base * (0.5 - layer * 0.1) * fade)
            if base_alpha <= 0:
                continue

            # Inner/outer radii for the ribbon
            r_inner = int(radius_px * (0.3 + layer * 0.06))
            r_outer = radius_px + int(glow_pad * 0.3) - layer

            # Build ribbon polygon
            segs = max(6, int(arc_deg * layer_sweep / 5))
            outer_pts = []
            inner_pts = []
            for i in range(segs + 1):
                a = math.radians(-half_arc + arc_deg * layer_sweep * i / segs)
                outer_pts.append((
                    int(center + math.cos(a) * r_outer),
                    int(center + math.sin(a) * r_outer)))
                inner_pts.append((
                    int(center + math.cos(a) * r_inner),
                    int(center + math.sin(a) * r_inner)))

            ribbon = outer_pts + list(reversed(inner_pts))
            if len(ribbon) >= 3:
                pygame.draw.polygon(surf, _with_alpha(color, base_alpha), ribbon)

    def _draw_afterimages(self, surf: pygame.Surface, center: int,
                          radius_px: int, glow_pad: int,
                          color: Tuple[int, int, int],
                          bright: Tuple[int, int, int],
                          half_arc: float, arc_deg: float,
                          sweep: float, thickness: float,
                          t: float, style: WeaponVisualStyle):
        """Layer 3: 2-3 fading copies of the blade edge at prior positions."""
        if sweep < 0.15:
            return

        num_echoes = min(3, style.trail_frames)
        for echo_idx in range(num_echoes):
            echo_sweep = max(0.0, sweep - (echo_idx + 1) * 0.12)
            if echo_sweep <= 0:
                continue

            echo_angle = math.radians(-half_arc + arc_deg * echo_sweep)
            # Fading alpha
            fade = 1.0 if t < 0.6 else max(0.0, (1.0 - t) / 0.4)
            echo_alpha = int(120 * (0.5 - echo_idx * 0.15) * fade)
            if echo_alpha <= 0:
                continue

            blade_inner = int(radius_px * 0.2)
            blade_outer = radius_px + int(glow_pad * 0.3)
            bx1 = center + int(math.cos(echo_angle) * blade_inner)
            by1 = center + int(math.sin(echo_angle) * blade_inner)
            bx2 = center + int(math.cos(echo_angle) * blade_outer)
            by2 = center + int(math.sin(echo_angle) * blade_outer)

            w = max(2, int(3 * thickness * (0.7 - echo_idx * 0.15)))
            pygame.draw.line(surf, _with_alpha(color, echo_alpha),
                             (bx1, by1), (bx2, by2), w + 4)
            pygame.draw.line(surf, _with_alpha(bright, echo_alpha),
                             (bx1, by1), (bx2, by2), w)

    def _draw_blade_edge(self, surf: pygame.Surface, center: int,
                         radius_px: int, glow_pad: int,
                         color: Tuple[int, int, int],
                         bright: Tuple[int, int, int],
                         white: Tuple[int, int, int],
                         sweep_angle_rad: float,
                         thickness: float, t: float,
                         style: WeaponVisualStyle):
        """Layer 2: Bright leading blade edge with 3-pass Gaussian-approx glow."""
        blade_inner = int(radius_px * 0.12)
        blade_outer = radius_px + int(glow_pad * 0.4)
        bx1 = center + int(math.cos(sweep_angle_rad) * blade_inner)
        by1 = center + int(math.sin(sweep_angle_rad) * blade_inner)
        bx2 = center + int(math.cos(sweep_angle_rad) * blade_outer)
        by2 = center + int(math.sin(sweep_angle_rad) * blade_outer)

        fade = 1.0 if t < 0.65 else max(0.0, (1.0 - t) / 0.35)
        base_alpha = int(230 * fade)
        if base_alpha <= 0:
            return

        blade_w = max(3, int(4 * thickness))

        # Pass 1: Wide outer glow (element color, low alpha)
        pygame.draw.line(surf, _with_alpha(color, base_alpha // 4),
                         (bx1, by1), (bx2, by2), blade_w + 8)
        # Pass 2: Medium glow (brighter)
        pygame.draw.line(surf, _with_alpha(color, base_alpha // 2),
                         (bx1, by1), (bx2, by2), blade_w + 4)
        # Pass 3: Core blade (bright)
        pygame.draw.line(surf, _with_alpha(bright, base_alpha),
                         (bx1, by1), (bx2, by2), blade_w)
        # Pass 4: White-hot center
        inner_w = max(1, blade_w // 2)
        pygame.draw.line(surf, _with_alpha(white, min(255, base_alpha)),
                         (bx1, by1), (bx2, by2), inner_w)

        # Tip glow at blade end
        tip_size = max(3, int(4 * thickness * fade))
        pygame.draw.circle(surf, _with_alpha(white, min(255, base_alpha)),
                           (bx2, by2), tip_size)
        pygame.draw.circle(surf, _with_alpha(bright, base_alpha // 2),
                           (bx2, by2), tip_size + 4)

    def _draw_sparks(self, surf: pygame.Surface, center: int,
                     radius_px: int, glow_pad: int,
                     bright: Tuple[int, int, int],
                     white: Tuple[int, int, int],
                     half_arc: float, arc_deg: float,
                     sweep: float, thickness: float,
                     t: float, style: WeaponVisualStyle):
        """Layer 4: Small bright dots scattered along the sweep path."""
        if sweep < 0.1 or style.particle_density < 0.3:
            return

        fade = 1.0 if t < 0.6 else max(0.0, (1.0 - t) / 0.4)
        if fade <= 0:
            return

        # Use a deterministic seed per frame so sparks don't flicker
        rng = random.Random(int(t * 1000) + int(arc_deg))
        n_sparks = int(4 * style.particle_density)
        blade_outer = radius_px + int(glow_pad * 0.3)

        for _ in range(n_sparks):
            sp_t = rng.random() * sweep
            sp_angle = math.radians(-half_arc + arc_deg * sp_t)
            sp_r = blade_outer + rng.randint(-3, 5)
            spx = center + int(math.cos(sp_angle) * sp_r)
            spy = center + int(math.sin(sp_angle) * sp_r)
            sp_size = rng.randint(1, max(1, int(2 * thickness)))

            # Sparks brighter near the current blade position
            dist_to_blade = abs(sp_t - sweep)
            brightness = max(0.2, 1.0 - dist_to_blade * 4)
            sp_alpha = min(255, int(200 * fade * brightness))

            sp_color = white if rng.random() < 0.3 else bright
            pygame.draw.circle(surf, _with_alpha(sp_color, sp_alpha),
                               (spx, spy), sp_size)

    # ------------------------------------------------------------------
    # Thrust generation
    # ------------------------------------------------------------------

    def _generate_thrust(self, style: WeaponVisualStyle,
                         length_px: int) -> List[pygame.Surface]:
        """Generate thrust/stab animation frames (e.g. spear).

        Frames point RIGHT (0°). Rotated at blit time.
        """
        num_frames = DEFAULT_THRUST_FRAMES
        pad = 12
        # Surface wide enough for the full thrust + padding
        w = length_px + pad * 2
        h = int(20 * style.thickness) + pad * 2
        cy = h // 2
        origin_x = pad

        color = style.color
        bright = _brighten(color, 60)
        white = (255, 255, 255)
        thickness = style.thickness

        frames: List[pygame.Surface] = []

        for f in range(num_frames):
            t = f / max(1, num_frames - 1)
            # Thrust extends quickly then holds
            if t < 0.4:
                extend = _ease_out_cubic(t / 0.4)
            else:
                extend = 1.0

            fade = 1.0 if t < 0.6 else max(0.0, (1.0 - t) / 0.4)

            surf = pygame.Surface((w, h), pygame.SRCALPHA)
            current_len = int(length_px * extend)
            end_x = origin_x + current_len

            if current_len < 2:
                frames.append(surf)
                continue

            base_alpha = int(220 * fade)
            blade_w = max(3, int(4 * thickness))

            # Outer glow
            pygame.draw.line(surf, _with_alpha(color, base_alpha // 4),
                             (origin_x, cy), (end_x, cy), blade_w + 8)
            # Core
            pygame.draw.line(surf, _with_alpha(bright, base_alpha),
                             (origin_x, cy), (end_x, cy), blade_w)
            # White center
            pygame.draw.line(surf, _with_alpha(white, min(255, base_alpha)),
                             (origin_x, cy), (end_x, cy), max(1, blade_w // 2))

            # Tip glow
            tip_size = max(3, int(5 * thickness * fade))
            pygame.draw.circle(surf, _with_alpha(white, min(255, base_alpha)),
                               (end_x, cy), tip_size)
            pygame.draw.circle(surf, _with_alpha(bright, base_alpha // 2),
                               (end_x, cy), tip_size + 4)

            # Motion trail behind the tip (short afterglow)
            if extend > 0.3:
                trail_start = int(length_px * max(0, extend - 0.25))
                trail_alpha = int(60 * fade)
                pygame.draw.line(surf, _with_alpha(color, trail_alpha),
                                 (origin_x + trail_start, cy), (end_x, cy), blade_w + 3)

            frames.append(surf)

        return frames

    # ------------------------------------------------------------------
    # Radial burst generation (circle/unarmed)
    # ------------------------------------------------------------------

    def _generate_radial(self, style: WeaponVisualStyle,
                         radius_px: int) -> List[pygame.Surface]:
        """Generate radial burst frames for circle/AoE attacks."""
        num_frames = DEFAULT_RADIAL_FRAMES
        pad = 8
        surf_size = radius_px * 2 + pad * 2
        center = surf_size // 2

        color = style.color
        bright = _brighten(color, 60)
        white = (255, 255, 255)
        thickness = style.thickness

        frames: List[pygame.Surface] = []

        for f in range(num_frames):
            t = f / max(1, num_frames - 1)
            expand = _ease_out_cubic(t)
            fade = 1.0 if t < 0.5 else max(0.0, (1.0 - t) / 0.5)

            surf = pygame.Surface((surf_size, surf_size), pygame.SRCALPHA)
            current_r = max(2, int(radius_px * expand))

            base_alpha = int(180 * fade)

            # Outer glow fill
            pygame.draw.circle(surf, _with_alpha(color, base_alpha // 5),
                               (center, center), current_r + 4)
            # Inner fill
            pygame.draw.circle(surf, _with_alpha(color, base_alpha // 3),
                               (center, center), current_r)
            # Bright ring
            ring_w = max(2, int(3 * thickness))
            pygame.draw.circle(surf, _with_alpha(bright, min(255, base_alpha)),
                               (center, center), current_r, ring_w)
            # White-hot inner ring (smaller)
            inner_r = max(2, int(current_r * 0.6))
            inner_alpha = int(base_alpha * 0.4)
            pygame.draw.circle(surf, _with_alpha(white, inner_alpha),
                               (center, center), inner_r, max(1, ring_w - 1))

            # Radial spark lines
            if expand > 0.2 and style.particle_density > 0.3:
                rng = random.Random(int(t * 1000))
                n_lines = int(6 * style.particle_density)
                for _ in range(n_lines):
                    a = rng.uniform(0, math.pi * 2)
                    r1 = int(current_r * 0.8)
                    r2 = current_r + rng.randint(2, 6)
                    lx1 = center + int(math.cos(a) * r1)
                    ly1 = center + int(math.sin(a) * r1)
                    lx2 = center + int(math.cos(a) * r2)
                    ly2 = center + int(math.sin(a) * r2)
                    spark_alpha = int(200 * fade * rng.uniform(0.5, 1.0))
                    pygame.draw.line(surf, _with_alpha(bright, spark_alpha),
                                     (lx1, ly1), (lx2, ly2), max(1, int(thickness)))

            frames.append(surf)

        return frames


def get_swing_renderer() -> SwingEffectRenderer:
    """Module-level accessor for the singleton."""
    return SwingEffectRenderer.get_instance()

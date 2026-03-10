"""
Sprite-quality attack effect frame generator.

Pre-renders multi-layered attack animation frames at startup using
soft gradients, bloom glow, and proper alpha blending to produce
polished, game-quality visual effects.

Each swing frame is composited from multiple soft-edged layers:
  Layer 1 — Soft Gradient Trail: Multi-pass crescent with alpha falloff
  Layer 2 — Energy Core: Bright tapered blade shape with bloom glow
  Layer 3 — Afterimage Ghosts: Blurred copies of the blade at prior positions
  Layer 4 — Spark Particles: Elongated bright streaks along the sweep path
  Layer 5 — Weapon Sprite: Actual weapon icon rotated to match swing angle

All frames are pre-rendered to SRCALPHA surfaces and cached.
Cache key = (weapon_type, element, tier) — typically <30 unique combos.
"""

import math
import random
from typing import Dict, List, Tuple, Optional

import pygame

from animation.weapon_visuals import (
    WeaponVisualStyle, resolve_weapon_visual,
    ELEMENT_COLORS, _WEAPON_VISUAL_PROFILES,
)


# Frame count per animation type
DEFAULT_SWING_FRAMES = 10
DEFAULT_THRUST_FRAMES = 8
DEFAULT_RADIAL_FRAMES = 8

# Surface sizing
BASE_SURFACE_SIZE = 128

# Blur quality (number of down-up scale passes)
_BLUR_PASSES = 1
_BLUR_SCALE = 0.35  # Scale factor per pass (lower = more blur)


# ---------------------------------------------------------------------------
# Utility functions
# ---------------------------------------------------------------------------

def _ease_out_cubic(t: float) -> float:
    """Decelerating ease-out — fast start, slow finish."""
    return 1.0 - (1.0 - t) ** 3


def _ease_in_out_quad(t: float) -> float:
    """Smooth acceleration then deceleration."""
    if t < 0.5:
        return 2.0 * t * t
    return 1.0 - (-2.0 * t + 2.0) ** 2 / 2.0


def _ease_out_quad(t: float) -> float:
    return 1.0 - (1.0 - t) ** 2


def _clamp(val, lo, hi):
    return max(lo, min(hi, val))


def _brighten(color: Tuple[int, int, int], amount: int = 60) -> Tuple[int, int, int]:
    return tuple(min(255, c + amount) for c in color)


def _with_alpha(color: Tuple[int, int, int], alpha: int) -> Tuple[int, int, int, int]:
    return (*color, _clamp(alpha, 0, 255))


def _blur_surface(surface: pygame.Surface, passes: int = _BLUR_PASSES) -> pygame.Surface:
    """Cheap box blur via scale-down then scale-up.

    Each pass halves and restores, softening hard edges. Multiple passes
    produce a Gaussian-like blur at very low cost.
    """
    w, h = surface.get_size()
    if w < 4 or h < 4:
        return surface

    result = surface
    for _ in range(passes):
        rw, rh = result.get_size()
        small_w = max(2, int(rw * _BLUR_SCALE))
        small_h = max(2, int(rh * _BLUR_SCALE))
        small = pygame.transform.smoothscale(result, (small_w, small_h))
        result = pygame.transform.smoothscale(small, (rw, rh))
    return result


def _make_radial_gradient(radius: int, color: Tuple[int, int, int],
                          alpha_center: int = 255,
                          alpha_edge: int = 0) -> pygame.Surface:
    """Pre-render a radial gradient circle (soft glow dot)."""
    size = radius * 2 + 2
    surf = pygame.Surface((size, size), pygame.SRCALPHA)
    cx, cy = size // 2, size // 2

    if radius < 1:
        return surf

    # Draw concentric circles from outside to inside (painter's algorithm)
    steps = max(4, radius // 2)
    for i in range(steps):
        t = i / max(1, steps - 1)  # 0.0 (outer) → 1.0 (inner)
        r = max(1, int(radius * (1.0 - t)))
        a = int(alpha_edge + (alpha_center - alpha_edge) * t * t)  # Quadratic falloff
        pygame.draw.circle(surf, (*color, _clamp(a, 0, 255)), (cx, cy), r)

    return surf


def _make_glow_spot(radius: int, color: Tuple[int, int, int],
                    intensity: float = 1.0) -> pygame.Surface:
    """Create a soft glow spot (radial gradient with alpha falloff)."""
    alpha_center = _clamp(int(200 * intensity), 0, 255)
    return _make_radial_gradient(radius, color, alpha_center, 0)


def _draw_soft_arc_ribbon(surf: pygame.Surface, center: int,
                          inner_r: int, outer_r: int,
                          start_rad: float, end_rad: float,
                          color: Tuple[int, int, int],
                          alpha: int, num_layers: int = 5):
    """Draw a crescent/ribbon arc with soft gradient edges.

    Uses multiple overlapping polygon layers with varying radii and alpha
    to create a smooth gradient from inner to outer edge.
    """
    if abs(end_rad - start_rad) < 0.01 or alpha <= 0:
        return

    segs = max(8, int(abs(math.degrees(end_rad - start_rad)) / 3))

    for layer in range(num_layers):
        # Each layer interpolates between inner and outer edge
        t_lo = layer / num_layers
        t_hi = (layer + 1) / num_layers

        # Radius range for this layer
        r_inner = int(inner_r + (outer_r - inner_r) * t_lo)
        r_outer = int(inner_r + (outer_r - inner_r) * t_hi)

        # Alpha peaks in the middle layers (bell curve)
        mid = 0.5
        dist_from_mid = abs((t_lo + t_hi) / 2.0 - mid) / mid
        layer_alpha = int(alpha * (1.0 - dist_from_mid * 0.6))
        if layer_alpha <= 0:
            continue

        outer_pts = []
        inner_pts = []
        for i in range(segs + 1):
            a = start_rad + (end_rad - start_rad) * i / segs
            cos_a = math.cos(a)
            sin_a = math.sin(a)
            outer_pts.append((int(center + cos_a * r_outer),
                              int(center + sin_a * r_outer)))
            inner_pts.append((int(center + cos_a * r_inner),
                              int(center + sin_a * r_inner)))

        ribbon = outer_pts + list(reversed(inner_pts))
        if len(ribbon) >= 3:
            pygame.draw.polygon(surf, _with_alpha(color, layer_alpha), ribbon)


def _draw_tapered_blade(surf: pygame.Surface,
                        x1: int, y1: int, x2: int, y2: int,
                        color: Tuple[int, int, int], alpha: int,
                        base_width: float, tip_width: float):
    """Draw a tapered blade shape (wide at base, narrow at tip).

    Much more visually appealing than a uniform-width line.
    """
    if alpha <= 0:
        return

    dx = x2 - x1
    dy = y2 - y1
    length = math.sqrt(dx * dx + dy * dy)
    if length < 1:
        return

    # Perpendicular direction
    nx = -dy / length
    ny = dx / length

    hw_base = base_width / 2.0
    hw_tip = tip_width / 2.0

    # Four corners of the tapered quad
    pts = [
        (int(x1 + nx * hw_base), int(y1 + ny * hw_base)),
        (int(x1 - nx * hw_base), int(y1 - ny * hw_base)),
        (int(x2 - nx * hw_tip), int(y2 - ny * hw_tip)),
        (int(x2 + nx * hw_tip), int(y2 + ny * hw_tip)),
    ]
    pygame.draw.polygon(surf, _with_alpha(color, alpha), pts)


class SwingEffectRenderer:
    """Pre-renders game-quality attack animation frames, cached by weapon style.

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
    # Swing (arc) generation — soft gradient crescent + energy blade
    # ------------------------------------------------------------------

    def _generate_swing(self, style: WeaponVisualStyle,
                        radius_px: int) -> List[pygame.Surface]:
        """Generate swing arc frames with game-quality visuals.

        Frames are drawn pointing RIGHT (0 degrees). The renderer rotates
        them to match the attack's facing_angle at blit time.
        """
        num_frames = DEFAULT_SWING_FRAMES
        # Extra padding for glow bleed
        glow_pad = int(16 * (0.6 + style.glow_intensity))
        surf_size = radius_px * 2 + glow_pad * 2
        center = surf_size // 2
        arc_deg = style.arc_degrees
        half_arc = arc_deg / 2.0

        color = style.color
        bright = _brighten(color, 80)
        white = (255, 255, 255)
        thickness = style.thickness

        frames: List[pygame.Surface] = []

        for f in range(num_frames):
            t = f / max(1, num_frames - 1)
            sweep = _ease_out_cubic(t)

            # Work surface for compositing layers
            surf = pygame.Surface((surf_size, surf_size), pygame.SRCALPHA)

            if sweep < 0.01:
                frames.append(surf)
                continue

            sweep_angle_rad = math.radians(-half_arc + arc_deg * sweep)
            start_angle_rad = math.radians(-half_arc)

            # Fade: hold full brightness through 70%, then fade out
            fade = 1.0 if t < 0.7 else max(0.0, (1.0 - t) / 0.3)

            # -- Layer 1: Soft gradient trail (crescent) --
            self._draw_gradient_trail(
                surf, center, radius_px, glow_pad, color, bright,
                arc_deg, half_arc, sweep, fade, style)

            # -- Layer 2: Afterimage ghosts (blurred previous positions) --
            if sweep > 0.15:
                self._draw_ghost_afterimages(
                    surf, center, radius_px, glow_pad, color, bright,
                    half_arc, arc_deg, sweep, thickness, fade, style)

            # -- Layer 3: Energy blade core (tapered, with bloom) --
            self._draw_energy_blade(
                surf, center, radius_px, glow_pad, color, bright, white,
                sweep_angle_rad, thickness, fade, style)

            # -- Layer 4: Spark streaks (elongated, not dots) --
            self._draw_spark_streaks(
                surf, center, radius_px, glow_pad, color, bright, white,
                half_arc, arc_deg, sweep, thickness, fade, style)

            # Apply a gentle blur to soften hard edges
            if fade > 0.3:
                # Composite: blur a copy and blend it back at partial alpha
                blurred = _blur_surface(surf.copy(), 1)
                # The blurred version acts as a soft glow under the sharp version
                final = pygame.Surface((surf_size, surf_size), pygame.SRCALPHA)
                final.blit(blurred, (0, 0))
                final.blit(surf, (0, 0))
                frames.append(final)
            else:
                frames.append(surf)

        return frames

    def _draw_gradient_trail(self, surf: pygame.Surface, center: int,
                             radius_px: int, glow_pad: int,
                             color: Tuple[int, int, int],
                             bright: Tuple[int, int, int],
                             arc_deg: float, half_arc: float,
                             sweep: float, fade: float,
                             style: WeaponVisualStyle):
        """Layer 1: Multi-layer gradient crescent trail.

        Instead of a single hard-edged polygon, draws multiple overlapping
        layers with decreasing alpha to create a natural gradient.
        """
        if sweep < 0.03:
            return

        base_alpha = int(style.trail_alpha_base * fade)
        if base_alpha <= 5:
            return

        # The trail covers the swept portion of the arc
        start_rad = math.radians(-half_arc)
        end_rad = math.radians(-half_arc + arc_deg * sweep)

        # Outer glow layer (wide, dim) — creates the bloom
        outer_r = radius_px + int(glow_pad * 0.6)
        inner_r_glow = int(radius_px * 0.15)
        _draw_soft_arc_ribbon(surf, center, inner_r_glow, outer_r,
                              start_rad, end_rad, color,
                              int(base_alpha * 0.25), num_layers=6)

        # Main crescent (the visible trail body)
        inner_r = int(radius_px * 0.30)
        outer_r_main = radius_px + int(glow_pad * 0.3)
        _draw_soft_arc_ribbon(surf, center, inner_r, outer_r_main,
                              start_rad, end_rad, color,
                              int(base_alpha * 0.5), num_layers=5)

        # Bright inner edge (the hot core of the trail)
        inner_r_hot = int(radius_px * 0.45)
        outer_r_hot = int(radius_px * 0.85)
        _draw_soft_arc_ribbon(surf, center, inner_r_hot, outer_r_hot,
                              start_rad, end_rad, bright,
                              int(base_alpha * 0.35), num_layers=3)

        # Leading edge emphasis: a bright glow near the current sweep position
        if sweep > 0.1:
            emphasis_start = math.radians(-half_arc + arc_deg * max(0, sweep - 0.15))
            emphasis_end = end_rad
            _draw_soft_arc_ribbon(surf, center, inner_r, outer_r_main,
                                  emphasis_start, emphasis_end, bright,
                                  int(base_alpha * 0.4), num_layers=3)

    def _draw_ghost_afterimages(self, surf: pygame.Surface, center: int,
                                radius_px: int, glow_pad: int,
                                color: Tuple[int, int, int],
                                bright: Tuple[int, int, int],
                                half_arc: float, arc_deg: float,
                                sweep: float, thickness: float,
                                fade: float, style: WeaponVisualStyle):
        """Layer 2: Soft ghosted copies of the blade at prior positions.

        Uses tapered blade shapes instead of simple lines for a richer look.
        """
        num_echoes = min(3, style.trail_frames)
        for echo_idx in range(num_echoes):
            echo_sweep = max(0.0, sweep - (echo_idx + 1) * 0.14)
            if echo_sweep <= 0:
                continue

            echo_angle = math.radians(-half_arc + arc_deg * echo_sweep)
            echo_alpha = int(90 * (0.55 - echo_idx * 0.15) * fade)
            if echo_alpha <= 0:
                continue

            blade_inner = int(radius_px * 0.22)
            blade_outer = radius_px + int(glow_pad * 0.25)
            bx1 = center + int(math.cos(echo_angle) * blade_inner)
            by1 = center + int(math.sin(echo_angle) * blade_inner)
            bx2 = center + int(math.cos(echo_angle) * blade_outer)
            by2 = center + int(math.sin(echo_angle) * blade_outer)

            # Tapered blade shape instead of uniform line
            base_w = max(5, int(8 * thickness * (0.6 - echo_idx * 0.12)))
            tip_w = max(1, base_w // 3)

            # Outer glow
            _draw_tapered_blade(surf, bx1, by1, bx2, by2,
                                color, echo_alpha // 2,
                                base_w + 6, tip_w + 4)
            # Core
            _draw_tapered_blade(surf, bx1, by1, bx2, by2,
                                bright, echo_alpha,
                                base_w, tip_w)

    def _draw_energy_blade(self, surf: pygame.Surface, center: int,
                           radius_px: int, glow_pad: int,
                           color: Tuple[int, int, int],
                           bright: Tuple[int, int, int],
                           white: Tuple[int, int, int],
                           sweep_angle_rad: float,
                           thickness: float, fade: float,
                           style: WeaponVisualStyle):
        """Layer 3: The leading energy blade edge with bloom glow.

        Uses a tapered blade shape with multiple glow passes creating a
        bloom effect that looks like an actual energy slash.
        """
        blade_inner = int(radius_px * 0.10)
        blade_outer = radius_px + int(glow_pad * 0.35)
        bx1 = center + int(math.cos(sweep_angle_rad) * blade_inner)
        by1 = center + int(math.sin(sweep_angle_rad) * blade_inner)
        bx2 = center + int(math.cos(sweep_angle_rad) * blade_outer)
        by2 = center + int(math.sin(sweep_angle_rad) * blade_outer)

        base_alpha = int(240 * fade)
        if base_alpha <= 0:
            return

        blade_w = max(5, int(7 * thickness))

        # Pass 1: Wide outer bloom (element color, very soft)
        _draw_tapered_blade(surf, bx1, by1, bx2, by2,
                            color, base_alpha // 5,
                            blade_w + 16, blade_w // 2 + 8)

        # Pass 2: Medium glow
        _draw_tapered_blade(surf, bx1, by1, bx2, by2,
                            color, base_alpha // 3,
                            blade_w + 8, blade_w // 2 + 4)

        # Pass 3: Core blade (bright element)
        _draw_tapered_blade(surf, bx1, by1, bx2, by2,
                            bright, base_alpha,
                            blade_w, max(2, blade_w // 3))

        # Pass 4: White-hot center line
        inner_w = max(2, blade_w // 2)
        _draw_tapered_blade(surf, bx1, by1, bx2, by2,
                            white, min(255, base_alpha),
                            inner_w, max(1, inner_w // 3))

        # Tip glow bloom (radial gradient at blade tip)
        tip_glow_r = max(5, int(8 * thickness * fade))
        glow_spot = _make_glow_spot(tip_glow_r, bright, fade)
        gs = glow_spot.get_size()
        surf.blit(glow_spot, (bx2 - gs[0] // 2, by2 - gs[1] // 2),
                  special_flags=pygame.BLEND_RGBA_ADD)

        # Bright white tip dot
        white_glow = _make_glow_spot(max(3, tip_glow_r // 2), white, fade * 0.8)
        ws = white_glow.get_size()
        surf.blit(white_glow, (bx2 - ws[0] // 2, by2 - ws[1] // 2),
                  special_flags=pygame.BLEND_RGBA_ADD)

    def _draw_spark_streaks(self, surf: pygame.Surface, center: int,
                            radius_px: int, glow_pad: int,
                            color: Tuple[int, int, int],
                            bright: Tuple[int, int, int],
                            white: Tuple[int, int, int],
                            half_arc: float, arc_deg: float,
                            sweep: float, thickness: float,
                            fade: float, style: WeaponVisualStyle):
        """Layer 4: Elongated spark streaks scattered along the sweep path.

        Instead of tiny dots, draws short bright streaks that follow the
        arc direction, creating a more dynamic, energetic look.
        """
        if sweep < 0.1 or style.particle_density < 0.3 or fade <= 0.05:
            return

        rng = random.Random(int(sweep * 1000) + int(arc_deg))
        n_sparks = int(6 * style.particle_density)
        blade_outer = radius_px + int(glow_pad * 0.3)

        for _ in range(n_sparks):
            # Position along the swept arc
            sp_t = rng.random() * sweep
            sp_angle = math.radians(-half_arc + arc_deg * sp_t)
            sp_r = blade_outer + rng.randint(-4, 8)
            spx = center + int(math.cos(sp_angle) * sp_r)
            spy = center + int(math.sin(sp_angle) * sp_r)

            # Brightness: sparks near the current blade position are brighter
            dist_to_blade = abs(sp_t - sweep)
            brightness = max(0.15, 1.0 - dist_to_blade * 3)

            sp_alpha = min(255, int(220 * fade * brightness))
            if sp_alpha <= 10:
                continue

            # Spark streak: short line in the tangent direction of the arc
            tangent_angle = sp_angle + math.pi / 2  # perpendicular to radius
            streak_len = rng.randint(3, max(4, int(8 * thickness)))
            sx2 = spx + int(math.cos(tangent_angle) * streak_len)
            sy2 = spy + int(math.sin(tangent_angle) * streak_len)

            sp_color = white if rng.random() < 0.35 else bright
            streak_w = max(2, rng.randint(1, int(2 * thickness + 1)))

            # Glow around streak
            pygame.draw.line(surf, _with_alpha(color, sp_alpha // 3),
                             (spx, spy), (sx2, sy2), streak_w + 3)
            # Core streak
            pygame.draw.line(surf, _with_alpha(sp_color, sp_alpha),
                             (spx, spy), (sx2, sy2), streak_w)

            # Bright dot at one end for sparkle
            if brightness > 0.5:
                dot_r = max(1, streak_w)
                pygame.draw.circle(surf, _with_alpha(white, min(255, int(sp_alpha * 0.8))),
                                   (spx, spy), dot_r)

    # ------------------------------------------------------------------
    # Thrust generation — tapered energy beam
    # ------------------------------------------------------------------

    def _generate_thrust(self, style: WeaponVisualStyle,
                         length_px: int) -> List[pygame.Surface]:
        """Generate thrust/stab animation frames.

        Creates a tapered energy beam that extends outward, much more
        visually substantial than a simple line.
        Frames point RIGHT (0 degrees). Rotated at blit time.
        """
        num_frames = DEFAULT_THRUST_FRAMES
        pad = 20
        w = length_px + pad * 2
        h = int(30 * style.thickness) + pad * 2
        cy = h // 2
        origin_x = pad

        color = style.color
        bright = _brighten(color, 80)
        white = (255, 255, 255)
        thickness = style.thickness

        frames: List[pygame.Surface] = []

        for f in range(num_frames):
            t = f / max(1, num_frames - 1)

            # Thrust extends quickly then holds, with a slight overshoot
            if t < 0.35:
                extend = _ease_out_cubic(t / 0.35) * 1.05  # Slight overshoot
            elif t < 0.5:
                extend = 1.05 - 0.05 * ((t - 0.35) / 0.15)  # Settle back
            else:
                extend = 1.0

            fade = 1.0 if t < 0.55 else max(0.0, (1.0 - t) / 0.45)

            surf = pygame.Surface((w, h), pygame.SRCALPHA)
            current_len = int(length_px * min(1.0, extend))
            end_x = origin_x + current_len

            if current_len < 3:
                frames.append(surf)
                continue

            base_alpha = int(230 * fade)
            blade_w = max(6, int(8 * thickness))

            # Layer 1: Wide outer bloom
            _draw_tapered_blade(surf, origin_x, cy, end_x, cy,
                                color, base_alpha // 5,
                                blade_w + 14, 4)

            # Layer 2: Medium glow
            _draw_tapered_blade(surf, origin_x, cy, end_x, cy,
                                color, base_alpha // 3,
                                blade_w + 6, 3)

            # Layer 3: Core beam (bright)
            _draw_tapered_blade(surf, origin_x, cy, end_x, cy,
                                bright, base_alpha,
                                blade_w, 2)

            # Layer 4: White-hot center
            _draw_tapered_blade(surf, origin_x, cy, end_x, cy,
                                white, min(255, base_alpha),
                                max(2, blade_w // 2), 1)

            # Tip glow bloom
            tip_r = max(5, int(8 * thickness * fade))
            glow = _make_glow_spot(tip_r, bright, fade)
            gs = glow.get_size()
            surf.blit(glow, (end_x - gs[0] // 2, cy - gs[1] // 2),
                      special_flags=pygame.BLEND_RGBA_ADD)

            # White tip flash
            white_glow = _make_glow_spot(max(3, tip_r // 2), white, fade * 0.9)
            ws = white_glow.get_size()
            surf.blit(white_glow, (end_x - ws[0] // 2, cy - ws[1] // 2),
                      special_flags=pygame.BLEND_RGBA_ADD)

            # Motion streaks behind the tip
            if extend > 0.3 and style.particle_density > 0.3:
                rng = random.Random(int(t * 1000))
                n_streaks = int(3 * style.particle_density)
                for _ in range(n_streaks):
                    sx = end_x - rng.randint(5, max(6, current_len // 3))
                    sy = cy + rng.randint(-int(blade_w * 0.8), int(blade_w * 0.8))
                    streak_len = rng.randint(4, 10)
                    s_alpha = int(100 * fade * rng.uniform(0.4, 1.0))
                    s_color = white if rng.random() < 0.3 else bright
                    pygame.draw.line(surf, _with_alpha(s_color, s_alpha),
                                     (sx, sy), (sx - streak_len, sy), 2)

            # Apply subtle blur for soft edges
            if fade > 0.3:
                blurred = _blur_surface(surf.copy(), 1)
                final = pygame.Surface((w, h), pygame.SRCALPHA)
                final.blit(blurred, (0, 0))
                final.blit(surf, (0, 0))
                frames.append(final)
            else:
                frames.append(surf)

        return frames

    # ------------------------------------------------------------------
    # Radial burst generation — expanding shockwave ring
    # ------------------------------------------------------------------

    def _generate_radial(self, style: WeaponVisualStyle,
                         radius_px: int) -> List[pygame.Surface]:
        """Generate radial burst frames (expanding shockwave).

        Creates a proper expanding shockwave with gradient ring, inner
        flash, and radial energy lines — much more visually impactful
        than simple concentric circles.
        """
        num_frames = DEFAULT_RADIAL_FRAMES
        pad = 12
        surf_size = radius_px * 2 + pad * 2
        center = surf_size // 2

        color = style.color
        bright = _brighten(color, 80)
        white = (255, 255, 255)
        thickness = style.thickness

        frames: List[pygame.Surface] = []

        for f in range(num_frames):
            t = f / max(1, num_frames - 1)
            expand = _ease_out_cubic(t)
            fade = 1.0 if t < 0.45 else max(0.0, (1.0 - t) / 0.55)

            surf = pygame.Surface((surf_size, surf_size), pygame.SRCALPHA)
            current_r = max(3, int(radius_px * expand))
            base_alpha = int(200 * fade)

            if base_alpha <= 5:
                frames.append(surf)
                continue

            # Layer 1: Inner fill glow (radial gradient)
            if current_r > 4:
                inner_glow = _make_radial_gradient(
                    current_r, color,
                    alpha_center=int(base_alpha * 0.3),
                    alpha_edge=0)
                igs = inner_glow.get_size()
                surf.blit(inner_glow, (center - igs[0] // 2, center - igs[1] // 2))

            # Layer 2: Expanding ring (multiple passes for thickness + glow)
            ring_w = max(3, int(5 * thickness))

            # Outer glow ring (wide, dim)
            if current_r > 2:
                pygame.draw.circle(surf, _with_alpha(color, base_alpha // 4),
                                   (center, center), current_r + 3, ring_w + 6)

            # Main ring
            pygame.draw.circle(surf, _with_alpha(bright, min(255, base_alpha)),
                               (center, center), current_r, ring_w)

            # Bright inner ring edge
            inner_ring_r = max(2, current_r - ring_w // 2)
            pygame.draw.circle(surf, _with_alpha(white, min(255, int(base_alpha * 0.6))),
                               (center, center), inner_ring_r, max(1, ring_w // 2))

            # Layer 3: Center flash (bright at start, fades quickly)
            if t < 0.5:
                flash_intensity = 1.0 - t * 2
                flash_r = max(3, int(current_r * 0.3 * flash_intensity))
                flash = _make_glow_spot(flash_r, white, flash_intensity)
                fs = flash.get_size()
                surf.blit(flash, (center - fs[0] // 2, center - fs[1] // 2),
                          special_flags=pygame.BLEND_RGBA_ADD)

            # Layer 4: Radial energy lines (spokes extending from center)
            if expand > 0.2 and style.particle_density > 0.3:
                rng = random.Random(int(t * 1000))
                n_lines = int(8 * style.particle_density)
                for _ in range(n_lines):
                    a = rng.uniform(0, math.pi * 2)
                    r1 = max(3, int(current_r * 0.5))
                    r2 = current_r + rng.randint(2, 8)
                    lx1 = center + int(math.cos(a) * r1)
                    ly1 = center + int(math.sin(a) * r1)
                    lx2 = center + int(math.cos(a) * r2)
                    ly2 = center + int(math.sin(a) * r2)
                    line_alpha = int(180 * fade * rng.uniform(0.4, 1.0))
                    line_color = white if rng.random() < 0.3 else bright
                    line_w = max(2, int(thickness + rng.random()))
                    # Glow pass
                    pygame.draw.line(surf, _with_alpha(color, line_alpha // 3),
                                     (lx1, ly1), (lx2, ly2), line_w + 2)
                    # Core pass
                    pygame.draw.line(surf, _with_alpha(line_color, line_alpha),
                                     (lx1, ly1), (lx2, ly2), line_w)

            # Subtle blur for polish
            if fade > 0.3:
                blurred = _blur_surface(surf.copy(), 1)
                final = pygame.Surface((surf_size, surf_size), pygame.SRCALPHA)
                final.blit(blurred, (0, 0))
                final.blit(surf, (0, 0))
                frames.append(final)
            else:
                frames.append(surf)

        return frames


def get_swing_renderer() -> SwingEffectRenderer:
    """Module-level accessor for the singleton."""
    return SwingEffectRenderer.get_instance()

"""
Procedural animation generation.

Generates AnimationDefinition instances from static sprites using
rotation, scaling, color tinting, and geometric drawing.

All generated frames are pre-rendered pygame.Surfaces — no per-frame
transforms happen during gameplay. Cost is paid at generation time.
"""

import math
import random
from typing import Tuple, List, Optional

import pygame

from animation.animation_data import AnimationFrame, AnimationDefinition


def _ease_out_cubic(t: float) -> float:
    """Fast start, slow end — feels like a weapon decelerating."""
    return 1.0 - (1.0 - t) ** 3


def _ease_in_out_sine(t: float) -> float:
    """Smooth acceleration and deceleration."""
    return -(math.cos(math.pi * t) - 1.0) / 2.0


def _lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


def _tint_surface(surface: pygame.Surface, color: Tuple[int, int, int],
                  intensity: float) -> pygame.Surface:
    """Blend a surface toward a color. intensity 0.0=original, 1.0=full tint."""
    tinted = surface.copy()
    overlay = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
    overlay.fill((*color, int(255 * min(1.0, intensity))))
    tinted.blit(overlay, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
    # Additive blend for glow effect
    glow = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
    glow.fill((*color, int(80 * min(1.0, intensity))))
    tinted.blit(glow, (0, 0), special_flags=pygame.BLEND_RGBA_ADD)
    return tinted


def _white_flash_surface(surface: pygame.Surface,
                         color: Tuple[int, int, int] = (255, 255, 255)) -> pygame.Surface:
    """Create a white-flashed version of a surface."""
    flash = surface.copy()
    white_overlay = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
    white_overlay.fill((*color, 200))
    flash.blit(white_overlay, (0, 0), special_flags=pygame.BLEND_RGBA_ADD)
    return flash


class ProceduralAnimations:
    """Static methods that generate AnimationDefinitions procedurally."""

    @staticmethod
    def create_swing_arc(arc_degrees: float = 90.0,
                         radius_px: float = 24.0,
                         duration_ms: float = 350.0,
                         num_frames: int = 6,
                         color: Tuple[int, int, int] = (220, 220, 240),
                         thickness: int = 3) -> AnimationDefinition:
        """Generate a melee swing arc animation.

        Creates frames of a crescent/arc that sweeps through arc_degrees.
        The arc is drawn on SRCALPHA surfaces centered at (0, 0) offset.

        Args:
            arc_degrees: Total arc sweep (e.g., 90 for sword, 180 for cleave)
            radius_px: Radius of the arc in pixels
            duration_ms: Total animation time
            num_frames: Number of frames to generate
            color: RGB color of the arc
            thickness: Line thickness of the arc
        """
        frames = []
        frame_duration = duration_ms / max(num_frames, 1)
        size = int(radius_px * 2 + thickness * 2 + 4)

        for i in range(num_frames):
            t = (i + 1) / num_frames
            eased_t = _ease_out_cubic(t)

            # Arc grows from 0 to full coverage
            sweep = arc_degrees * eased_t
            # Alpha fades in the last quarter of the animation
            alpha = 255 if t < 0.75 else int(255 * (1.0 - (t - 0.75) / 0.25))

            surface = pygame.Surface((size, size), pygame.SRCALPHA)
            center = size // 2

            # Draw the arc
            half_sweep = sweep / 2.0
            start_angle = math.radians(-half_sweep)
            end_angle = math.radians(half_sweep)

            if sweep > 5:  # Avoid degenerate arcs
                rect = pygame.Rect(
                    center - int(radius_px),
                    center - int(radius_px),
                    int(radius_px * 2),
                    int(radius_px * 2)
                )
                # pygame.draw.arc angles: 0 = right, counter-clockwise
                pygame.draw.arc(surface, (*color, alpha), rect,
                                start_angle, end_angle,
                                max(1, int(thickness * (0.5 + eased_t * 0.5))))

            # Hitbox active during middle frames (30%-80% of animation)
            hitbox_active = 0.3 <= t <= 0.8

            frames.append(AnimationFrame(
                surface=surface,
                duration_ms=frame_duration,
                hitbox_active=hitbox_active
            ))

        defn = AnimationDefinition(
            animation_id="swing_arc",
            frames=frames,
            loop=False
        )
        defn.recalculate_duration()
        return defn

    @staticmethod
    def create_telegraph_pulse(base_sprite: pygame.Surface,
                               tint_color: Tuple[int, int, int],
                               scale_range: Tuple[float, float] = (1.0, 1.15),
                               duration_ms: float = 400.0,
                               num_frames: int = 4) -> AnimationDefinition:
        """Generate enemy telegraph (windup) animation.

        Enemy sprite scales up slightly and tints toward a warning color.

        Args:
            base_sprite: The enemy's static sprite
            tint_color: Warning color (red for physical, orange for fire, etc.)
            scale_range: (min_scale, max_scale) during windup
            duration_ms: Total windup time
            num_frames: Number of frames
        """
        frames = []
        frame_duration = duration_ms / max(num_frames, 1)

        for i in range(num_frames):
            t = (i + 1) / num_frames
            progress = _ease_in_out_sine(t)

            # Scale
            scale = _lerp(scale_range[0], scale_range[1], progress)
            scaled_w = int(base_sprite.get_width() * scale)
            scaled_h = int(base_sprite.get_height() * scale)
            scaled = pygame.transform.smoothscale(base_sprite, (scaled_w, scaled_h))

            # Tint intensity increases with progress
            tinted = _tint_surface(scaled, tint_color, progress * 0.4)

            frames.append(AnimationFrame(
                surface=tinted,
                duration_ms=frame_duration,
                scale=scale
            ))

        defn = AnimationDefinition(
            animation_id="telegraph_pulse",
            frames=frames,
            loop=False
        )
        defn.recalculate_duration()
        return defn

    @staticmethod
    def create_hit_flash(base_sprite: pygame.Surface,
                         flash_color: Tuple[int, int, int] = (255, 255, 255),
                         duration_ms: float = 80.0) -> AnimationDefinition:
        """2-frame flash when entity takes damage.

        Frame 1: White/colored flash version of sprite
        Frame 2: Original sprite (brief)
        """
        flash_surf = _white_flash_surface(base_sprite, flash_color)

        frames = [
            AnimationFrame(
                surface=flash_surf,
                duration_ms=duration_ms * 0.6,
            ),
            AnimationFrame(
                surface=base_sprite.copy(),
                duration_ms=duration_ms * 0.4,
            ),
        ]

        defn = AnimationDefinition(
            animation_id="hit_flash",
            frames=frames,
            loop=False
        )
        defn.recalculate_duration()
        return defn

    @staticmethod
    def create_idle_bob(amplitude_px: float = 2.0,
                        period_ms: float = 1200.0,
                        num_frames: int = 8) -> AnimationDefinition:
        """Subtle vertical oscillation to make entities feel alive.

        Uses sine wave for smooth motion. No surface changes — only offset_y.
        """
        frames = []
        frame_duration = period_ms / max(num_frames, 1)

        for i in range(num_frames):
            t = i / num_frames
            offset_y = amplitude_px * math.sin(2.0 * math.pi * t)

            frames.append(AnimationFrame(
                surface=None,  # No surface override — entity uses its own sprite
                duration_ms=frame_duration,
                offset_y=offset_y
            ))

        defn = AnimationDefinition(
            animation_id="idle_bob",
            frames=frames,
            loop=True
        )
        defn.recalculate_duration()
        return defn

    @staticmethod
    def create_slash_trail(arc_degrees: float = 90.0,
                           radius_px: float = 28.0,
                           color: Tuple[int, int, int] = (220, 230, 255),
                           thickness: int = 3,
                           duration_ms: float = 150.0,
                           num_frames: int = 4) -> AnimationDefinition:
        """Expanding arc trail that represents a weapon swing path.

        The trail starts narrow, expands to full arc, then fades.
        Drawn as a series of arc segments on SRCALPHA surfaces.
        """
        frames = []
        frame_duration = duration_ms / max(num_frames, 1)
        size = int(radius_px * 2 + thickness * 2 + 8)

        alphas = [255, 230, 180, 80]  # Progressive fade
        coverages = [0.25, 0.6, 1.0, 1.0]  # Arc fill progress

        for i in range(num_frames):
            alpha = alphas[i] if i < len(alphas) else 80
            coverage = coverages[i] if i < len(coverages) else 1.0

            surface = pygame.Surface((size, size), pygame.SRCALPHA)
            center = size // 2

            sweep = arc_degrees * coverage
            half_sweep = sweep / 2.0
            start_angle = math.radians(-half_sweep)
            end_angle = math.radians(half_sweep)

            if sweep > 5:
                rect = pygame.Rect(
                    center - int(radius_px),
                    center - int(radius_px),
                    int(radius_px * 2),
                    int(radius_px * 2)
                )
                line_w = max(1, thickness - (i // 2))
                pygame.draw.arc(surface, (*color, alpha), rect,
                                start_angle, end_angle, line_w)

            frames.append(AnimationFrame(
                surface=surface,
                duration_ms=frame_duration
            ))

        defn = AnimationDefinition(
            animation_id="slash_trail",
            frames=frames,
            loop=False
        )
        defn.recalculate_duration()
        return defn

    @staticmethod
    def create_ground_telegraph(shape: str,
                                radius_px: float,
                                color: Tuple[int, int, int],
                                duration_ms: float = 500.0,
                                num_frames: int = 5,
                                arc_degrees: float = 90.0,
                                facing_angle: float = 0.0) -> AnimationDefinition:
        """Ground indicator showing where an attack will land.

        Fills progressively during enemy windup so the player can react.

        Args:
            shape: "circle" or "arc"
            radius_px: Size of the telegraph in pixels
            color: Warning color
            duration_ms: Duration to fill
            num_frames: Number of frames
            arc_degrees: Arc width (only for "arc" shape)
            facing_angle: Direction of arc (only for "arc" shape)
        """
        frames = []
        frame_duration = duration_ms / max(num_frames, 1)
        size = int(radius_px * 2 + 8)

        for i in range(num_frames):
            t = (i + 1) / num_frames
            # Alpha increases as telegraph fills (40 -> 120)
            alpha = int(40 + t * 80)
            fill_radius = int(radius_px * t)

            surface = pygame.Surface((size, size), pygame.SRCALPHA)
            center = size // 2

            if shape == "circle":
                # Fill circle
                pygame.draw.circle(surface, (*color, alpha),
                                   (center, center), fill_radius)
                # Outline at full radius
                pygame.draw.circle(surface, (*color, min(255, alpha + 40)),
                                   (center, center), int(radius_px), 2)
            elif shape == "arc":
                half_arc = arc_degrees / 2.0
                start = math.radians(facing_angle - half_arc)
                end = math.radians(facing_angle + half_arc)

                rect = pygame.Rect(
                    center - fill_radius,
                    center - fill_radius,
                    fill_radius * 2,
                    fill_radius * 2
                )
                if fill_radius > 2:
                    pygame.draw.arc(surface, (*color, alpha), rect,
                                    -end, -start, max(1, fill_radius // 3))
                # Outline arc at full radius
                full_rect = pygame.Rect(
                    center - int(radius_px),
                    center - int(radius_px),
                    int(radius_px * 2),
                    int(radius_px * 2)
                )
                pygame.draw.arc(surface, (*color, min(255, alpha + 40)),
                                full_rect, -end, -start, 2)

            frames.append(AnimationFrame(
                surface=surface,
                duration_ms=frame_duration
            ))

        defn = AnimationDefinition(
            animation_id="ground_telegraph",
            frames=frames,
            loop=False
        )
        defn.recalculate_duration()
        return defn

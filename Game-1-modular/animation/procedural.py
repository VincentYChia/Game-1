"""
Procedural animation generation.

Generates AnimationDefinition instances from static sprites using
rotation, scaling, color tinting, and multi-layer drawing with soft glow.

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


def _clamp(val, lo, hi):
    return max(lo, min(hi, val))


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


def _draw_soft_arc(surface: pygame.Surface, center: int, radius_px: float,
                   start_angle: float, end_angle: float,
                   color: Tuple[int, int, int], alpha: int,
                   thickness: int, num_glow_layers: int = 3):
    """Draw an arc with soft glow using multiple passes."""
    if abs(end_angle - start_angle) < 0.05 or alpha <= 0:
        return

    # Outer glow passes
    for i in range(num_glow_layers):
        layer_t = i / max(1, num_glow_layers - 1)
        layer_alpha = int(alpha * (0.15 + 0.85 * (1.0 - layer_t)))
        layer_w = max(1, thickness + int((num_glow_layers - i) * 2))

        rect = pygame.Rect(
            center - int(radius_px),
            center - int(radius_px),
            int(radius_px * 2),
            int(radius_px * 2)
        )
        pygame.draw.arc(surface, (*color, _clamp(layer_alpha, 0, 255)),
                        rect, start_angle, end_angle, layer_w)


class ProceduralAnimations:
    """Static methods that generate AnimationDefinitions procedurally."""

    @staticmethod
    def create_swing_arc(arc_degrees: float = 90.0,
                         radius_px: float = 24.0,
                         duration_ms: float = 350.0,
                         num_frames: int = 8,
                         color: Tuple[int, int, int] = (220, 220, 240),
                         thickness: int = 3) -> AnimationDefinition:
        """Generate a melee swing arc animation with soft glow.

        Creates frames of a crescent/arc that sweeps through arc_degrees
        with multi-pass glow rendering for a polished look.
        """
        frames = []
        frame_duration = duration_ms / max(num_frames, 1)
        size = int(radius_px * 2 + thickness * 2 + 12)
        bright = tuple(min(255, c + 80) for c in color)

        for i in range(num_frames):
            t = (i + 1) / num_frames
            eased_t = _ease_out_cubic(t)

            sweep = arc_degrees * eased_t
            alpha = 255 if t < 0.75 else int(255 * (1.0 - (t - 0.75) / 0.25))

            surface = pygame.Surface((size, size), pygame.SRCALPHA)
            center = size // 2

            half_sweep = sweep / 2.0
            start_angle = math.radians(-half_sweep)
            end_angle = math.radians(half_sweep)

            if sweep > 5:
                # Multi-layer glow arc
                _draw_soft_arc(surface, center, radius_px,
                               start_angle, end_angle, color, alpha,
                               thickness, num_glow_layers=4)

                # Bright leading edge at the sweep tip
                tip_angle = end_angle
                tip_x = center + int(math.cos(tip_angle) * radius_px)
                tip_y = center + int(math.sin(tip_angle) * radius_px)
                if alpha > 30:
                    # Glow spot at tip
                    glow_r = max(3, thickness + 2)
                    glow_surf = pygame.Surface((glow_r * 4, glow_r * 4), pygame.SRCALPHA)
                    gc = glow_r * 2
                    for gr in range(glow_r, 0, -1):
                        ga = int(alpha * gr / glow_r * 0.4)
                        pygame.draw.circle(glow_surf, (*bright, _clamp(ga, 0, 255)),
                                           (gc, gc), gr)
                    surface.blit(glow_surf, (tip_x - gc, tip_y - gc),
                                 special_flags=pygame.BLEND_RGBA_ADD)

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
        """
        frames = []
        frame_duration = duration_ms / max(num_frames, 1)

        for i in range(num_frames):
            t = (i + 1) / num_frames
            progress = _ease_in_out_sine(t)

            scale = _lerp(scale_range[0], scale_range[1], progress)
            scaled_w = int(base_sprite.get_width() * scale)
            scaled_h = int(base_sprite.get_height() * scale)
            scaled = pygame.transform.smoothscale(base_sprite, (scaled_w, scaled_h))

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
        """2-frame flash when entity takes damage."""
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
        """Subtle vertical oscillation to make entities feel alive."""
        frames = []
        frame_duration = period_ms / max(num_frames, 1)

        for i in range(num_frames):
            t = i / num_frames
            offset_y = amplitude_px * math.sin(2.0 * math.pi * t)

            frames.append(AnimationFrame(
                surface=None,
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
        """Expanding arc trail with soft glow that represents a weapon swing path."""
        frames = []
        frame_duration = duration_ms / max(num_frames, 1)
        size = int(radius_px * 2 + thickness * 2 + 12)
        bright = tuple(min(255, c + 80) for c in color)

        alphas = [255, 230, 180, 80]
        coverages = [0.25, 0.6, 1.0, 1.0]

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
                _draw_soft_arc(surface, center, radius_px,
                               start_angle, end_angle, color, alpha,
                               max(1, thickness - (i // 2)),
                               num_glow_layers=3)

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
        Uses soft glow rendering for a polished look.
        """
        frames = []
        frame_duration = duration_ms / max(num_frames, 1)
        size = int(radius_px * 2 + 12)
        bright = tuple(min(255, c + 60) for c in color)

        for i in range(num_frames):
            t = (i + 1) / num_frames
            alpha = int(40 + t * 80)
            fill_radius = int(radius_px * t)

            surface = pygame.Surface((size, size), pygame.SRCALPHA)
            center = size // 2

            if shape == "circle":
                # Soft filled circle with gradient edge
                if fill_radius > 2:
                    # Inner fill (radial gradient approximation)
                    steps = max(3, fill_radius // 4)
                    for s in range(steps):
                        st = s / max(1, steps - 1)
                        r = max(1, int(fill_radius * (1.0 - st)))
                        sa = int(alpha * (0.3 + 0.7 * st))
                        pygame.draw.circle(surface, (*color, _clamp(sa, 0, 255)),
                                           (center, center), r)

                # Outline at full radius with glow
                outline_alpha = min(255, alpha + 40)
                pygame.draw.circle(surface, (*color, _clamp(outline_alpha + 20, 0, 255)),
                                   (center, center), int(radius_px), 4)
                pygame.draw.circle(surface, (*bright, _clamp(outline_alpha, 0, 255)),
                                   (center, center), int(radius_px), 2)

            elif shape == "arc":
                half_arc = arc_degrees / 2.0
                start = math.radians(facing_angle - half_arc)
                end = math.radians(facing_angle + half_arc)

                if fill_radius > 2:
                    rect = pygame.Rect(
                        center - fill_radius, center - fill_radius,
                        fill_radius * 2, fill_radius * 2
                    )
                    arc_w = max(1, fill_radius // 3)
                    pygame.draw.arc(surface, (*color, _clamp(alpha, 0, 255)),
                                    rect, -end, -start, arc_w)

                # Outline arc at full radius with glow
                full_rect = pygame.Rect(
                    center - int(radius_px), center - int(radius_px),
                    int(radius_px * 2), int(radius_px * 2)
                )
                outline_alpha = min(255, alpha + 40)
                pygame.draw.arc(surface, (*color, _clamp(outline_alpha + 20, 0, 255)),
                                full_rect, -end, -start, 4)
                pygame.draw.arc(surface, (*bright, _clamp(outline_alpha, 0, 255)),
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

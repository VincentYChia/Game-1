"""Enhanced visual effects for the combat visual overhaul.

Provides config-driven rendering helpers that the main Renderer calls.
All visual parameters are read from VisualConfig (Definitions.JSON/visual-config.JSON).

Modules:
    - Enhanced damage numbers: physics-based float, type-colored, crit scaling
    - Player rendering: facing indicator, weapon arc preview, idle bob, shadow
    - Enemy rendering: death fade/shrink, tier glow, spawn fade-in
    - Debug overlay: hitbox/hurtbox wireframes when F1 is active
"""

from __future__ import annotations

import math
import random
import time
from typing import Dict, List, Optional, Tuple

import pygame

from data.databases.visual_config_db import get_visual_config


# ============================================================================
# ENHANCED DAMAGE NUMBERS
# ============================================================================

class EnhancedDamageNumber:
    """Physics-based floating damage number with type coloring and crit effects.

    Replaces the basic DamageNumber with arc trajectory, type-driven color,
    crit bounce, and stack offset to prevent overlapping numbers.
    """

    def __init__(self, value: int, world_x: float, world_y: float,
                 is_crit: bool = False, damage_type: str = "physical",
                 special: str = ""):
        """
        Args:
            value: Damage amount (0 for special text like MISS/DODGE).
            world_x, world_y: World-space position.
            is_crit: Whether this was a critical hit.
            damage_type: Tag-based damage type for color.
            special: If set, overrides value display ("miss", "dodge", "block").
        """
        vc = get_visual_config()

        self.value = value
        self.world_x = world_x
        self.world_y = world_y
        self.is_crit = is_crit
        self.damage_type = damage_type
        self.special = special

        # Physics
        self.vel_y = vc.damage_number_velocity_y
        self.vel_x = random.uniform(
            -vc.damage_number_horizontal_spread,
            vc.damage_number_horizontal_spread)
        self.gravity = vc.damage_number_gravity

        # Lifecycle
        self.max_lifetime = vc.damage_number_lifetime_ms
        self.age_ms: float = 0.0
        self.alive: bool = True

        # Visual state
        self.alpha: float = 255.0
        self.scale: float = vc.damage_number_crit_scale if is_crit else 1.0
        self.shrink_rate = vc.damage_number_shrink_rate

        # Color
        if special:
            self.text, self.color = vc.damage_special_text(special)
        elif is_crit:
            self.text = f"{value}!"
            self.color = vc.damage_number_crit_color
        else:
            self.text = str(value)
            self.color = vc.damage_type_color(damage_type)

        # Crit bounce: initial upward burst then arc
        if is_crit:
            self.vel_y *= 1.4
            self.vel_x *= 0.5  # Less horizontal spread for crits

    def update(self, dt_ms: float) -> bool:
        """Update position and lifecycle. Returns True if still alive."""
        self.age_ms += dt_ms
        if self.age_ms >= self.max_lifetime:
            self.alive = False
            return False

        # Normalize to 60fps equivalent
        dt_norm = dt_ms / 16.67

        # Physics
        self.world_y += self.vel_y * dt_norm * 0.02  # World-space units
        self.world_x += self.vel_x * dt_norm * 0.02
        self.vel_y += self.gravity * dt_norm

        # Fade out in last 30% of lifetime
        life_ratio = self.age_ms / self.max_lifetime
        if life_ratio > 0.7:
            fade_progress = (life_ratio - 0.7) / 0.3
            self.alpha = 255 * (1.0 - fade_progress)
        else:
            self.alpha = 255.0

        # Subtle shrink
        self.scale *= self.shrink_rate

        return True

    def render(self, screen: pygame.Surface, camera, font: pygame.font.Font,
               crit_font: pygame.font.Font) -> None:
        """Render the damage number at its current position."""
        if not self.alive or self.alpha < 5:
            return

        from data.models import Position
        sx, sy = camera.world_to_screen(Position(self.world_x, self.world_y, 0))

        # Choose font based on crit/special
        use_font = crit_font if self.is_crit else font
        text_surf = use_font.render(self.text, True, self.color)

        # Scale
        if abs(self.scale - 1.0) > 0.01:
            new_w = max(1, int(text_surf.get_width() * self.scale))
            new_h = max(1, int(text_surf.get_height() * self.scale))
            text_surf = pygame.transform.smoothscale(text_surf, (new_w, new_h))

        # Alpha
        text_surf.set_alpha(max(0, int(self.alpha)))

        # Black outline for readability
        outline_color = (0, 0, 0)
        outline_surf = use_font.render(self.text, True, outline_color)
        if abs(self.scale - 1.0) > 0.01:
            outline_surf = pygame.transform.smoothscale(
                outline_surf, (text_surf.get_width(), text_surf.get_height()))
        outline_surf.set_alpha(max(0, int(self.alpha * 0.7)))

        rect = text_surf.get_rect(center=(sx, sy))
        # Draw outline offsets
        for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
            screen.blit(outline_surf, (rect.x + dx, rect.y + dy))
        # Draw main text
        screen.blit(text_surf, rect)


class DamageNumberManager:
    """Manages all active damage numbers with anti-stacking."""

    def __init__(self):
        self.numbers: List[EnhancedDamageNumber] = []
        self._recent_positions: Dict[str, float] = {}  # "x,y" -> last_spawn_time

    def spawn(self, value: int, world_x: float, world_y: float,
              is_crit: bool = False, damage_type: str = "physical",
              special: str = "") -> None:
        """Spawn a new damage number with anti-stack offset."""
        vc = get_visual_config()

        # Anti-stack: offset Y if multiple numbers near same position
        key = f"{world_x:.1f},{world_y:.1f}"
        now = time.time()
        if key in self._recent_positions:
            elapsed = now - self._recent_positions[key]
            if elapsed < 0.3:  # Within 300ms
                world_y -= vc.damage_number_stack_offset * 0.03  # World units
        self._recent_positions[key] = now

        num = EnhancedDamageNumber(value, world_x, world_y, is_crit, damage_type, special)
        self.numbers.append(num)

    def update(self, dt_ms: float) -> None:
        """Update all damage numbers, remove dead ones."""
        self.numbers = [n for n in self.numbers if n.update(dt_ms)]

        # Clean old position entries
        now = time.time()
        self._recent_positions = {
            k: v for k, v in self._recent_positions.items()
            if now - v < 1.0
        }

    def render(self, screen: pygame.Surface, camera,
               font: pygame.font.Font, crit_font: pygame.font.Font) -> None:
        """Render all active damage numbers."""
        for num in self.numbers:
            num.render(screen, camera, font, crit_font)


# ============================================================================
# PLAYER VISUAL ENHANCEMENTS
# ============================================================================

def render_player_enhanced(screen: pygame.Surface, camera, character,
                           tile_size: int, action_combat_systems: dict = None) -> None:
    """Render player with facing indicator, shadow, idle bob, and weapon arc preview.

    Replaces: pygame.draw.circle(screen, COLOR_PLAYER, (cx, cy), TILE_SIZE // 3)
    """
    vc = get_visual_config()
    from data.models import Position

    cx, cy = camera.world_to_screen(character.position)
    radius = int(tile_size * vc.player_radius_tiles)

    # Idle bob (subtle vertical oscillation)
    bob_offset = 0.0
    if not getattr(character, '_attack_facing_locked', False):
        t = time.time() * 1000.0
        period = vc.idle_bob_period_ms
        bob_offset = math.sin(2 * math.pi * t / period) * vc.idle_bob_amplitude
    cy_bobbed = cy + int(bob_offset)

    # Shadow
    if vc.shadow_enabled:
        shadow_rx = int(radius * vc.shadow_scale)
        shadow_ry = int(radius * vc.shadow_scale * 0.5)
        shadow_surf = pygame.Surface((shadow_rx * 2 + 4, shadow_ry * 2 + 4), pygame.SRCALPHA)
        pygame.draw.ellipse(shadow_surf, (0, 0, 0, vc.shadow_alpha),
                           (2, 2, shadow_rx * 2, shadow_ry * 2))
        screen.blit(shadow_surf, (cx - shadow_rx - 2, cy + radius - shadow_ry))

    # Player body
    pygame.draw.circle(screen, vc.player_color, (cx, cy_bobbed), radius)
    pygame.draw.circle(screen, vc.player_outline_color, (cx, cy_bobbed), radius, 2)

    # Facing direction indicator
    facing_angle = getattr(character, 'facing_angle', 0.0)
    facing_rad = math.radians(facing_angle)
    ind_len = int(tile_size * vc.facing_indicator_length)
    ind_x = cx + int(math.cos(facing_rad) * (radius + ind_len))
    ind_y = cy_bobbed + int(math.sin(facing_rad) * (radius + ind_len))

    # Triangular facing indicator
    perp = facing_rad + math.pi / 2
    tri_size = max(3, radius // 3)
    p1 = (ind_x + int(math.cos(facing_rad) * tri_size),
          ind_y + int(math.sin(facing_rad) * tri_size))
    p2 = (ind_x + int(math.cos(perp) * tri_size // 2),
          ind_y + int(math.sin(perp) * tri_size // 2))
    p3 = (ind_x - int(math.cos(perp) * tri_size // 2),
          ind_y - int(math.sin(perp) * tri_size // 2))
    pygame.draw.polygon(screen, vc.facing_indicator_color, [p1, p2, p3])

    # Blocking indicator (shield icon)
    if getattr(character, 'is_blocking', False):
        shield_radius = radius + 4
        shield_surf = pygame.Surface((shield_radius * 2 + 4, shield_radius * 2 + 4), pygame.SRCALPHA)
        pulse = 0.7 + 0.3 * math.sin(time.time() * 6)
        shield_alpha = int(120 * pulse)
        pygame.draw.circle(shield_surf, (100, 160, 255, shield_alpha),
                           (shield_radius + 2, shield_radius + 2), shield_radius, 3)
        screen.blit(shield_surf, (cx - shield_radius - 2, cy_bobbed - shield_radius - 2))


# ============================================================================
# ENEMY VISUAL ENHANCEMENTS
# ============================================================================

class EnemyDeathEffect:
    """Manages a single enemy's death animation (fade + shrink + particles)."""

    def __init__(self, world_x: float, world_y: float, sprite_or_color,
                 visual_size: float, tier: int, enemy_color: Tuple[int, int, int]):
        vc = get_visual_config()
        self.world_x = world_x
        self.world_y = world_y
        self.sprite_or_color = sprite_or_color  # pygame.Surface or None
        self.visual_size = visual_size
        self.tier = tier
        self.enemy_color = enemy_color
        self.fade_duration = vc.death_fade_duration_ms
        self.shrink_target = vc.death_shrink_factor
        self.linger_ms = vc.corpse_linger_ms
        self.corpse_fade_ms = self._get("enemyVisuals", "corpseFadeMs", 1000)
        self.age_ms: float = 0.0
        self.alive: bool = True
        self.phase: str = "dying"  # "dying" -> "corpse" -> dead
        self.rotation: float = 0.0

    @staticmethod
    def _get(*keys, default=None):
        vc = get_visual_config()
        return vc._get(*keys, default=default)

    def update(self, dt_ms: float) -> bool:
        self.age_ms += dt_ms

        if self.phase == "dying":
            if self.age_ms >= self.fade_duration:
                self.phase = "corpse"
                self.age_ms = 0.0
            else:
                # Spin slightly during death
                progress = self.age_ms / self.fade_duration
                vc = get_visual_config()
                max_rot = vc._get("enemyVisuals", "deathRotationDegrees", default=15)
                self.rotation = max_rot * progress * (1 if random.random() > 0.5 else -1)

        elif self.phase == "corpse":
            if self.age_ms >= self.linger_ms:
                self.alive = False
                return False

        return True

    @property
    def alpha(self) -> float:
        if self.phase == "dying":
            return 255 * (1.0 - self.age_ms / self.fade_duration)
        elif self.phase == "corpse":
            # Full alpha until last corpse_fade_ms
            remaining = self.linger_ms - self.age_ms
            if remaining < self.corpse_fade_ms:
                return 255 * (remaining / self.corpse_fade_ms)
            return 180  # Dimmed but visible
        return 0

    @property
    def scale(self) -> float:
        if self.phase == "dying":
            progress = self.age_ms / self.fade_duration
            return 1.0 - progress * (1.0 - self.shrink_target)
        return self.shrink_target

    def render(self, screen: pygame.Surface, camera, tile_size: int) -> None:
        from data.models import Position
        sx, sy = camera.world_to_screen(Position(self.world_x, self.world_y, 0))
        base_size = int(tile_size // 2 * self.visual_size)
        current_size = max(2, int(base_size * self.scale))
        a = max(0, int(self.alpha))

        if a < 5:
            return

        # Draw greyed-out circle with alpha
        surf_size = current_size * 2 + 4
        death_surf = pygame.Surface((surf_size, surf_size), pygame.SRCALPHA)
        center = surf_size // 2

        # Grey tint of original color
        grey_color = tuple(max(40, c // 2) for c in self.enemy_color)
        pygame.draw.circle(death_surf, (*grey_color, a), (center, center), current_size)
        pygame.draw.circle(death_surf, (0, 0, 0, a // 2), (center, center), current_size, 1)

        # Rotation during death phase
        if abs(self.rotation) > 0.5:
            death_surf = pygame.transform.rotate(death_surf, self.rotation)

        rect = death_surf.get_rect(center=(sx, sy))
        screen.blit(death_surf, rect)


class EnemyDeathManager:
    """Tracks all active enemy death effects."""

    def __init__(self):
        self.effects: List[EnemyDeathEffect] = []

    def spawn(self, world_x: float, world_y: float, visual_size: float,
              tier: int, enemy_color: Tuple[int, int, int]) -> None:
        self.effects.append(EnemyDeathEffect(
            world_x, world_y, None, visual_size, tier, enemy_color))

    def update(self, dt_ms: float) -> None:
        self.effects = [e for e in self.effects if e.update(dt_ms)]

    def render(self, screen: pygame.Surface, camera, tile_size: int) -> None:
        for effect in self.effects:
            effect.render(screen, camera, tile_size)


# ============================================================================
# DEBUG HITBOX VISUALIZATION
# ============================================================================

def render_debug_hitboxes(screen: pygame.Surface, camera, hitbox_system,
                          tile_size: int) -> None:
    """Render hitbox/hurtbox wireframes for debug mode (F1).

    - Red: active attack hitboxes
    - Green: entity hurtboxes
    - Blue: invulnerable hurtboxes (i-frames)
    """
    vc = get_visual_config()
    from data.models import Position

    # Hurtboxes (green/blue circles)
    if hasattr(hitbox_system, 'hurtboxes'):
        for entity_id, hurtbox in hitbox_system.hurtboxes.items():
            sx, sy = camera.world_to_screen(
                Position(hurtbox.world_x, hurtbox.world_y, 0))
            radius_px = int(hurtbox.radius * tile_size)

            if hurtbox.invulnerable:
                color = vc.debug_iframe_color()
                alpha = vc._get("debug", "iframeHurtboxAlpha", default=60)
            else:
                color = vc.debug_hurtbox_color()
                alpha = vc.debug_hurtbox_alpha

            if radius_px > 1:
                surf_size = radius_px * 2 + 4
                debug_surf = pygame.Surface((surf_size, surf_size), pygame.SRCALPHA)
                center = surf_size // 2
                # Fill
                pygame.draw.circle(debug_surf, (*color, alpha // 3), (center, center), radius_px)
                # Outline
                pygame.draw.circle(debug_surf, (*color, alpha), (center, center), radius_px, 2)
                screen.blit(debug_surf, (sx - center, sy - center))

                # Entity ID label
                if vc._get("debug", "showEntityIds", default=False):
                    font = pygame.font.Font(None, 14)
                    id_surf = font.render(entity_id, True, color)
                    screen.blit(id_surf, (sx - id_surf.get_width() // 2, sy - radius_px - 14))

    # Active hitboxes (red wireframes with shape-accurate rendering)
    if hasattr(hitbox_system, 'active_hitboxes'):
        for hitbox in hitbox_system.active_hitboxes:
            sx, sy = camera.world_to_screen(
                Position(hitbox.world_x, hitbox.world_y, 0))

            color = vc.debug_hitbox_color()
            alpha = vc.debug_hitbox_alpha

            shape = hitbox.definition.shape

            if shape == "circle":
                r_px = int(hitbox.definition.radius * tile_size)
                if r_px > 1:
                    surf_size = r_px * 2 + 4
                    debug_surf = pygame.Surface((surf_size, surf_size), pygame.SRCALPHA)
                    c = surf_size // 2
                    pygame.draw.circle(debug_surf, (*color, alpha // 4), (c, c), r_px)
                    pygame.draw.circle(debug_surf, (*color, alpha), (c, c), r_px, 2)
                    screen.blit(debug_surf, (sx - c, sy - c))

            elif shape == "arc":
                r_px = int(hitbox.definition.radius * tile_size)
                arc_deg = hitbox.definition.arc_degrees
                facing_rad = math.radians(hitbox.facing_angle)
                half_arc = math.radians(arc_deg / 2)

                if r_px > 2:
                    surf_size = r_px * 2 + 4
                    debug_surf = pygame.Surface((surf_size, surf_size), pygame.SRCALPHA)
                    c = surf_size // 2
                    num_seg = max(8, int(arc_deg / 5))
                    points = [(c, c)]
                    for i in range(num_seg + 1):
                        a = facing_rad - half_arc + math.radians(arc_deg) * i / num_seg
                        points.append((
                            int(c + math.cos(a) * r_px),
                            int(c + math.sin(a) * r_px)))
                    if len(points) >= 3:
                        pygame.draw.polygon(debug_surf, (*color, alpha // 4), points)
                        pygame.draw.polygon(debug_surf, (*color, alpha), points, 2)
                    screen.blit(debug_surf, (sx - c, sy - c))

            elif shape == "rect":
                w_px = int(hitbox.definition.width * tile_size)
                h_px = int(hitbox.definition.height * tile_size)
                rect_surf = pygame.Surface((w_px + 4, h_px + 4), pygame.SRCALPHA)
                pygame.draw.rect(rect_surf, (*color, alpha // 4), (2, 2, w_px, h_px))
                pygame.draw.rect(rect_surf, (*color, alpha), (2, 2, w_px, h_px), 2)
                rotated = pygame.transform.rotate(rect_surf, -hitbox.facing_angle)
                screen.blit(rotated, rotated.get_rect(center=(sx, sy)))

            elif shape == "line":
                length_px = int(hitbox.definition.length * tile_size)
                facing_rad = math.radians(hitbox.facing_angle)
                end_x = sx + int(math.cos(facing_rad) * length_px)
                end_y = sy + int(math.sin(facing_rad) * length_px)
                line_surf = pygame.Surface(
                    (abs(end_x - sx) + 20, abs(end_y - sy) + 20), pygame.SRCALPHA)
                # Simple line overlay for debug
                pygame.draw.line(screen, (*color, alpha), (sx, sy), (end_x, end_y), 3)

            # Owner label
            if vc.debug_show_attack_phase:
                font = pygame.font.Font(None, 12)
                label = f"{hitbox.owner_id} {hitbox.remaining_ms:.0f}ms"
                label_surf = font.render(label, True, color)
                screen.blit(label_surf, (sx - label_surf.get_width() // 2, sy + 8))


def render_debug_projectiles(screen: pygame.Surface, camera, projectile_system,
                             tile_size: int) -> None:
    """Render projectile debug info (trajectory lines, hitbox circles)."""
    vc = get_visual_config()
    from data.models import Position

    if not hasattr(projectile_system, 'projectiles'):
        return

    trail_color = vc._get("debug", "projectileTrailColor", default=[255, 255, 100])
    trail_color = tuple(trail_color)

    for proj in projectile_system.projectiles:
        sx, sy = camera.world_to_screen(Position(proj.x, proj.y, 0))
        # Hitbox circle
        r_px = max(2, int(proj.definition.hitbox_radius * tile_size))
        pygame.draw.circle(screen, (*trail_color, 150), (sx, sy), r_px, 1)

        # Velocity vector
        vel_scale = 10
        end_x = sx + int(proj.vx * vel_scale)
        end_y = sy + int(proj.vy * vel_scale)
        pygame.draw.line(screen, trail_color, (sx, sy), (end_x, end_y), 1)

        # Range remaining
        font = pygame.font.Font(None, 12)
        dist_left = proj.definition.max_range - proj.distance_traveled
        label = f"{dist_left:.1f}t"
        label_surf = font.render(label, True, trail_color)
        screen.blit(label_surf, (sx + r_px + 2, sy - 6))

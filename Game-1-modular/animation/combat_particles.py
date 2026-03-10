"""
World-space particle system for combat visual effects.

Follows the architecture of core/minigame_effects.py but operates in world
coordinates (tiles) instead of screen-space pixels. Particles are converted
to screen coordinates during render() via the camera.

Particle types: hit sparks (elongated streaks), slash trails, impact bursts,
dodge dust, projectile trails. All particles use proper glow rendering with
multi-pass alpha blending for game-quality visuals.
"""

import math
import random
from typing import List, Tuple, Optional

import pygame

from core.config import Config


# Damage type -> spark color palette (brighter, more saturated)
DAMAGE_SPARK_COLORS = {
    "physical": [(230, 230, 250), (255, 255, 255), (200, 200, 220)],
    "fire": [(255, 220, 80), (255, 140, 30), (255, 100, 10)],
    "ice": [(120, 210, 255), (180, 240, 255), (220, 250, 255)],
    "lightning": [(255, 255, 120), (255, 255, 220), (220, 220, 255)],
    "poison": [(120, 255, 120), (70, 220, 70), (180, 255, 120)],
    "arcane": [(220, 120, 255), (170, 70, 255), (240, 170, 255)],
    "shadow": [(170, 120, 220), (120, 70, 170), (200, 150, 240)],
    "holy": [(255, 255, 220), (255, 250, 170), (255, 255, 255)],
}


class CombatParticle:
    """A single world-space particle with velocity-based streak rendering."""

    __slots__ = ('x', 'y', 'vx', 'vy', 'life', 'max_life', 'size',
                 'color', 'alpha', 'gravity', 'drag', 'streak')

    def __init__(self, x: float, y: float,
                 vx: float = 0.0, vy: float = 0.0,
                 life: float = 1.0, size: float = 3.0,
                 color: Tuple[int, int, int] = (255, 255, 255),
                 gravity: float = 0.0, drag: float = 0.0,
                 streak: bool = False):
        self.x = x
        self.y = y
        self.vx = vx
        self.vy = vy
        self.life = life
        self.max_life = life
        self.size = size
        self.color = color
        self.alpha = 255
        self.gravity = gravity
        self.drag = drag
        self.streak = streak  # If True, render as elongated streak in velocity direction

    def update(self, dt_sec: float) -> bool:
        """Update particle physics. Returns False when dead."""
        self.x += self.vx * dt_sec
        self.y += self.vy * dt_sec
        self.vy += self.gravity * dt_sec

        if self.drag > 0:
            factor = max(0.0, 1.0 - self.drag * dt_sec)
            self.vx *= factor
            self.vy *= factor

        self.life -= dt_sec
        life_ratio = max(0.0, self.life / self.max_life)
        self.alpha = int(255 * life_ratio)
        return self.life > 0


class CombatParticleSystem:
    """Manages world-space combat particles with game-quality rendering."""

    def __init__(self, max_particles: int = 600):
        self.particles: List[CombatParticle] = []
        self.max_particles = max_particles

    def _add(self, particle: CombatParticle) -> None:
        if len(self.particles) < self.max_particles:
            self.particles.append(particle)

    def emit_hit_sparks(self, world_x: float, world_y: float,
                        damage_type: str = "physical",
                        intensity: float = 1.0) -> None:
        """Burst of elongated spark streaks at hit location."""
        colors = DAMAGE_SPARK_COLORS.get(damage_type,
                                          DAMAGE_SPARK_COLORS["physical"])
        count = int(8 + intensity * 5)

        for _ in range(count):
            angle = random.uniform(0, math.pi * 2)
            speed = random.uniform(2.0, 5.0) * intensity
            self._add(CombatParticle(
                x=world_x + random.uniform(-0.08, 0.08),
                y=world_y + random.uniform(-0.08, 0.08),
                vx=math.cos(angle) * speed,
                vy=math.sin(angle) * speed - 1.5,  # Bias upward
                life=random.uniform(0.25, 0.55),
                size=random.uniform(2.5, 5.0),
                color=random.choice(colors),
                gravity=6.0,
                drag=2.5,
                streak=True
            ))

        # Add a few bright flash dots at center
        for _ in range(3):
            self._add(CombatParticle(
                x=world_x + random.uniform(-0.03, 0.03),
                y=world_y + random.uniform(-0.03, 0.03),
                vx=random.uniform(-0.5, 0.5),
                vy=random.uniform(-0.5, 0.5),
                life=random.uniform(0.08, 0.15),
                size=random.uniform(5.0, 8.0),
                color=(255, 255, 255),
                drag=8.0,
                streak=False
            ))

    def emit_slash_trail(self, world_x: float, world_y: float,
                         angle_deg: float, arc_degrees: float,
                         radius: float) -> None:
        """Particles along a slash arc path — more particles, streaked."""
        count = int(6 + arc_degrees / 15)
        half_arc = arc_degrees / 2.0
        for _ in range(count):
            a = math.radians(angle_deg + random.uniform(-half_arc, half_arc))
            r = radius * random.uniform(0.5, 1.1)
            px = world_x + math.cos(a) * r
            py = world_y + math.sin(a) * r

            # Tangential velocity (along the arc)
            tangent = a + math.pi / 2
            speed = random.uniform(0.5, 1.5)

            self._add(CombatParticle(
                x=px, y=py,
                vx=math.cos(tangent) * speed + math.cos(a) * 0.3,
                vy=math.sin(tangent) * speed + math.sin(a) * 0.3,
                life=random.uniform(0.12, 0.3),
                size=random.uniform(2.0, 4.0),
                color=(220, 230, 255),
                drag=4.0,
                streak=True
            ))

    def emit_dodge_dust(self, world_x: float, world_y: float) -> None:
        """Dust cloud at dodge start position."""
        for _ in range(8):
            angle = random.uniform(0, math.pi * 2)
            speed = random.uniform(0.5, 2.0)
            self._add(CombatParticle(
                x=world_x + random.uniform(-0.15, 0.15),
                y=world_y + random.uniform(-0.15, 0.15),
                vx=math.cos(angle) * speed,
                vy=math.sin(angle) * speed,
                life=random.uniform(0.3, 0.7),
                size=random.uniform(4.0, 7.0),
                color=(180, 170, 150),
                gravity=-0.5,
                drag=3.5,
                streak=False
            ))

    def emit_projectile_trail(self, world_x: float, world_y: float,
                              trail_type: str) -> None:
        """Trail particles at projectile position — streaked for motion."""
        trail_colors = {
            "fire_trail": [(255, 170, 60), (255, 120, 30)],
            "ice_trail": [(120, 210, 255), (170, 240, 255)],
            "arcane_trail": [(210, 120, 255), (170, 70, 255)],
            "acid_trail": [(120, 255, 120), (70, 220, 70)],
            "lightning_trail": [(255, 255, 120), (255, 255, 210)],
            "shadow_trail": [(120, 70, 170), (100, 50, 140)],
            "arrow_trail": [(190, 170, 130), (160, 150, 110)],
        }
        colors = trail_colors.get(trail_type, [(200, 200, 200)])

        self._add(CombatParticle(
            x=world_x + random.uniform(-0.05, 0.05),
            y=world_y + random.uniform(-0.05, 0.05),
            vx=random.uniform(-0.3, 0.3),
            vy=random.uniform(-0.4, 0.0),
            life=random.uniform(0.15, 0.35),
            size=random.uniform(2.5, 4.5),
            color=random.choice(colors),
            drag=2.0,
            streak=True
        ))

    def update(self, dt_ms: float) -> None:
        """Update all particles, remove dead ones."""
        dt_sec = dt_ms / 1000.0
        self.particles = [p for p in self.particles if p.update(dt_sec)]

    def render(self, screen: pygame.Surface, camera,
               shake_ox: int = 0, shake_oy: int = 0) -> None:
        """Convert world positions to screen, draw all particles.

        Streak particles render as elongated shapes in their velocity
        direction. Regular particles render as soft glowing circles.
        """
        from data.models import Position

        for p in self.particles:
            if p.alpha <= 0:
                continue

            sx, sy = camera.world_to_screen(Position(p.x, p.y, 0))
            sx += shake_ox
            sy += shake_oy

            # Cull off-screen particles
            if sx < -30 or sx > Config.VIEWPORT_WIDTH + 30:
                continue
            if sy < -30 or sy > Config.VIEWPORT_HEIGHT + 30:
                continue

            life_ratio = p.life / p.max_life
            size = max(1, int(p.size * life_ratio))

            if p.streak and (abs(p.vx) > 0.3 or abs(p.vy) > 0.3):
                # Elongated streak in velocity direction
                speed = math.sqrt(p.vx * p.vx + p.vy * p.vy)
                streak_len = max(3, int(speed * size * 0.8))

                # Streak direction
                if speed > 0.01:
                    dx = p.vx / speed
                    dy = p.vy / speed
                else:
                    dx, dy = 1.0, 0.0

                # Trail end (behind the particle)
                tx = int(sx - dx * streak_len)
                ty = int(sy - dy * streak_len)
                isx, isy = int(sx), int(sy)

                # Outer glow pass (wider, dimmer)
                glow_w = max(3, size + 2)
                glow_alpha = max(0, min(255, p.alpha // 3))
                if glow_alpha > 10:
                    glow_surf = pygame.Surface((abs(isx - tx) + glow_w * 2 + 4,
                                                abs(isy - ty) + glow_w * 2 + 4), pygame.SRCALPHA)
                    ox = min(isx, tx) - glow_w - 2
                    oy = min(isy, ty) - glow_w - 2
                    pygame.draw.line(glow_surf, (*p.color, glow_alpha),
                                     (isx - ox, isy - oy), (tx - ox, ty - oy), glow_w)
                    screen.blit(glow_surf, (ox, oy))

                # Core streak (narrow, bright)
                core_w = max(2, size)
                core_alpha = max(0, min(255, p.alpha))
                bright_color = tuple(min(255, c + 60) for c in p.color)
                core_surf = pygame.Surface((abs(isx - tx) + core_w * 2 + 4,
                                            abs(isy - ty) + core_w * 2 + 4), pygame.SRCALPHA)
                ox = min(isx, tx) - core_w - 2
                oy = min(isy, ty) - core_w - 2
                pygame.draw.line(core_surf, (*bright_color, core_alpha),
                                 (isx - ox, isy - oy), (tx - ox, ty - oy), core_w)
                screen.blit(core_surf, (ox, oy))

                # Bright head dot
                if size >= 2:
                    dot_surf = pygame.Surface((size * 2 + 4, size * 2 + 4), pygame.SRCALPHA)
                    dc = size + 2
                    pygame.draw.circle(dot_surf, (*p.color, min(255, int(p.alpha * 0.5))),
                                       (dc, dc), size + 1)
                    pygame.draw.circle(dot_surf, (255, 255, 255, min(255, p.alpha)),
                                       (dc, dc), max(1, size // 2))
                    screen.blit(dot_surf, (isx - dc, isy - dc))
            else:
                # Soft glowing circle particle
                if size <= 1:
                    try:
                        screen.set_at((int(sx), int(sy)), p.color)
                    except (IndexError, TypeError):
                        pass
                else:
                    # Multi-pass glow: outer dim + inner bright
                    surf_size = size * 2 + 6
                    particle_surf = pygame.Surface((surf_size, surf_size), pygame.SRCALPHA)
                    c = surf_size // 2

                    # Outer glow
                    glow_alpha = max(0, min(255, p.alpha // 3))
                    if glow_alpha > 5:
                        pygame.draw.circle(particle_surf, (*p.color, glow_alpha),
                                           (c, c), size + 2)

                    # Core
                    pygame.draw.circle(particle_surf, (*p.color, min(255, p.alpha)),
                                       (c, c), size)

                    # Bright center
                    if size >= 3:
                        inner_r = max(1, size // 2)
                        bright_alpha = max(0, min(255, int(p.alpha * 0.7)))
                        pygame.draw.circle(particle_surf,
                                           (255, 255, 255, bright_alpha),
                                           (c, c), inner_r)

                    screen.blit(particle_surf, (int(sx) - c, int(sy) - c))

    def clear(self) -> None:
        self.particles.clear()

    @property
    def count(self) -> int:
        return len(self.particles)

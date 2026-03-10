"""
World-space particle system for combat visual effects.

Follows the architecture of core/minigame_effects.py but operates in world
coordinates (tiles) instead of screen-space pixels. Particles are converted
to screen coordinates during render() via the camera.

Particle types: hit sparks, slash trails, blood splatter, dodge dust,
projectile trails.
"""

import math
import random
from typing import List, Tuple, Optional

import pygame

from core.config import Config


# Damage type -> spark color palette
DAMAGE_SPARK_COLORS = {
    "physical": [(220, 220, 240), (255, 255, 255), (180, 180, 200)],
    "fire": [(255, 200, 50), (255, 120, 20), (255, 80, 10)],
    "ice": [(100, 200, 255), (150, 230, 255), (200, 240, 255)],
    "lightning": [(255, 255, 100), (255, 255, 200), (200, 200, 255)],
    "poison": [(100, 255, 100), (50, 200, 50), (150, 255, 100)],
    "arcane": [(200, 100, 255), (150, 50, 255), (230, 150, 255)],
    "shadow": [(150, 100, 200), (100, 50, 150), (180, 130, 230)],
    "holy": [(255, 255, 200), (255, 240, 150), (255, 255, 255)],
}


class CombatParticle:
    """A single world-space particle."""

    __slots__ = ('x', 'y', 'vx', 'vy', 'life', 'max_life', 'size',
                 'color', 'alpha', 'gravity', 'drag')

    def __init__(self, x: float, y: float,
                 vx: float = 0.0, vy: float = 0.0,
                 life: float = 1.0, size: float = 3.0,
                 color: Tuple[int, int, int] = (255, 255, 255),
                 gravity: float = 0.0, drag: float = 0.0):
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
    """Manages world-space combat particles."""

    def __init__(self, max_particles: int = 400):
        self.particles: List[CombatParticle] = []
        self.max_particles = max_particles

    def _add(self, particle: CombatParticle) -> None:
        if len(self.particles) < self.max_particles:
            self.particles.append(particle)

    def emit_hit_sparks(self, world_x: float, world_y: float,
                        damage_type: str = "physical",
                        intensity: float = 1.0) -> None:
        """Burst of sparks at hit location."""
        colors = DAMAGE_SPARK_COLORS.get(damage_type,
                                          DAMAGE_SPARK_COLORS["physical"])
        count = int(5 + intensity * 3)

        for _ in range(count):
            angle = random.uniform(0, math.pi * 2)
            speed = random.uniform(1.5, 4.0) * intensity
            self._add(CombatParticle(
                x=world_x + random.uniform(-0.1, 0.1),
                y=world_y + random.uniform(-0.1, 0.1),
                vx=math.cos(angle) * speed,
                vy=math.sin(angle) * speed - 1.0,  # Bias upward
                life=random.uniform(0.2, 0.5),
                size=random.uniform(2.0, 4.0),
                color=random.choice(colors),
                gravity=5.0,
                drag=3.0
            ))

    def emit_slash_trail(self, world_x: float, world_y: float,
                         angle_deg: float, arc_degrees: float,
                         radius: float) -> None:
        """Particles along a slash arc path."""
        count = 4
        half_arc = arc_degrees / 2.0
        for _ in range(count):
            a = math.radians(angle_deg + random.uniform(-half_arc, half_arc))
            r = radius * random.uniform(0.6, 1.0)
            px = world_x + math.cos(a) * r
            py = world_y + math.sin(a) * r

            self._add(CombatParticle(
                x=px, y=py,
                vx=math.cos(a) * 0.5,
                vy=math.sin(a) * 0.5,
                life=random.uniform(0.1, 0.25),
                size=random.uniform(1.5, 3.0),
                color=(220, 230, 255),
                drag=5.0
            ))

    def emit_dodge_dust(self, world_x: float, world_y: float) -> None:
        """Small dust cloud at dodge start position."""
        for _ in range(6):
            angle = random.uniform(0, math.pi * 2)
            speed = random.uniform(0.5, 1.5)
            self._add(CombatParticle(
                x=world_x + random.uniform(-0.15, 0.15),
                y=world_y + random.uniform(-0.15, 0.15),
                vx=math.cos(angle) * speed,
                vy=math.sin(angle) * speed,
                life=random.uniform(0.3, 0.6),
                size=random.uniform(3.0, 6.0),
                color=(180, 170, 150),
                gravity=-0.5,
                drag=4.0
            ))

    def emit_projectile_trail(self, world_x: float, world_y: float,
                              trail_type: str) -> None:
        """Single trail particle at projectile position."""
        trail_colors = {
            "fire_trail": [(255, 150, 50), (255, 100, 20)],
            "ice_trail": [(100, 200, 255), (150, 230, 255)],
            "arcane_trail": [(200, 100, 255), (150, 50, 255)],
            "acid_trail": [(100, 255, 100), (50, 200, 50)],
            "lightning_trail": [(255, 255, 100), (255, 255, 200)],
            "shadow_trail": [(100, 50, 150), (80, 30, 120)],
            "arrow_trail": [(180, 160, 120), (150, 140, 100)],
        }
        colors = trail_colors.get(trail_type, [(200, 200, 200)])

        self._add(CombatParticle(
            x=world_x + random.uniform(-0.05, 0.05),
            y=world_y + random.uniform(-0.05, 0.05),
            vx=random.uniform(-0.2, 0.2),
            vy=random.uniform(-0.3, 0.0),
            life=random.uniform(0.15, 0.3),
            size=random.uniform(2.0, 3.5),
            color=random.choice(colors),
            drag=2.0
        ))

    def update(self, dt_ms: float) -> None:
        """Update all particles, remove dead ones."""
        dt_sec = dt_ms / 1000.0
        self.particles = [p for p in self.particles if p.update(dt_sec)]

    def render(self, screen: pygame.Surface, camera,
               shake_ox: int = 0, shake_oy: int = 0) -> None:
        """Convert world positions to screen, draw all particles."""
        from data.models import Position

        for p in self.particles:
            if p.alpha <= 0:
                continue

            sx, sy = camera.world_to_screen(Position(p.x, p.y, 0))
            sx += shake_ox
            sy += shake_oy

            # Cull off-screen particles
            if sx < -20 or sx > Config.VIEWPORT_WIDTH + 20:
                continue
            if sy < -20 or sy > Config.VIEWPORT_HEIGHT + 20:
                continue

            size = max(1, int(p.size * (p.life / p.max_life)))
            if size <= 1:
                # Single pixel for tiny particles
                screen.set_at((int(sx), int(sy)), p.color)
            else:
                particle_surf = pygame.Surface((size * 2, size * 2), pygame.SRCALPHA)
                pygame.draw.circle(particle_surf, (*p.color, p.alpha),
                                   (size, size), size)
                screen.blit(particle_surf, (int(sx) - size, int(sy) - size))

    def clear(self) -> None:
        self.particles.clear()

    @property
    def count(self) -> int:
        return len(self.particles)

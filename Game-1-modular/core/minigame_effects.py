"""
Minigame Effects Module - Visual effects and animation infrastructure for crafting minigames.

This module provides reusable particle systems, animations, and visual effects
for all 5 crafting disciplines (Smithing, Refining, Alchemy, Engineering, Enchanting).

Created: January 2026
"""

import pygame
import math
import random
from typing import List, Dict, Tuple, Optional, Callable
from dataclasses import dataclass, field


# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

def ease_out_cubic(t: float) -> float:
    """Ease-out cubic: decelerating to zero velocity."""
    return 1 - (1 - t) ** 3


def ease_in_out_sine(t: float) -> float:
    """Ease-in-out sine: smooth acceleration/deceleration."""
    return -(math.cos(math.pi * t) - 1) / 2


def ease_out_quad(t: float) -> float:
    """Ease-out quadratic: gentle deceleration."""
    return 1 - (1 - t) ** 2


def ease_in_quad(t: float) -> float:
    """Ease-in quadratic: gentle acceleration."""
    return t * t


def lerp(a: float, b: float, t: float) -> float:
    """Linear interpolation between two values."""
    return a + (b - a) * t


def lerp_color(color1: Tuple[int, int, int], color2: Tuple[int, int, int], t: float) -> Tuple[int, int, int]:
    """Linear interpolation between two RGB colors."""
    return (
        int(color1[0] + (color2[0] - color1[0]) * t),
        int(color1[1] + (color2[1] - color1[1]) * t),
        int(color1[2] + (color2[2] - color1[2]) * t),
    )


def clamp(value: float, min_val: float, max_val: float) -> float:
    """Clamp a value between min and max."""
    return max(min_val, min(max_val, value))


# =============================================================================
# COLOR PALETTES
# =============================================================================

class ColorPalette:
    """Color palettes for each discipline."""

    # Smithing - Forge fire colors
    SMITHING = {
        'flame_core': (255, 200, 50),
        'flame_mid': (255, 120, 20),
        'flame_outer': (200, 50, 0),
        'ember': (255, 100, 0),
        'spark': (255, 255, 200),
        'metal_cold': (100, 100, 110),
        'metal_warm': (200, 100, 50),
        'metal_hot': (255, 150, 50),
        'metal_white_hot': (255, 240, 200),
        'anvil': (60, 60, 70),
        'background_dark': (30, 20, 15),
        'background_glow': (80, 40, 20),
    }

    # Refining - Bronze/kiln colors
    REFINING = {
        'bronze_light': (205, 150, 80),
        'bronze_mid': (180, 120, 60),
        'bronze_dark': (140, 90, 40),
        'fire_bronze': (255, 180, 80),
        'fire_orange': (255, 140, 40),
        'kiln_glow': (255, 200, 120),
        'gear_brass': (180, 150, 90),
        'gear_dark': (100, 80, 50),
        'molten': (255, 180, 50),
        'background': (50, 35, 25),
    }

    # Alchemy - Lab/wizard mix
    ALCHEMY = {
        'potion_blue': (80, 150, 220),
        'potion_green': (80, 220, 120),
        'potion_purple': (160, 80, 220),
        'bubble': (200, 240, 255),
        'steam': (220, 230, 240),
        'cauldron': (60, 50, 55),
        'liquid_base': (100, 180, 150),
        'liquid_active': (120, 255, 180),
        'liquid_critical': (255, 200, 80),
        'background_light': (240, 245, 250),
        'background_warm': (250, 248, 240),
        'wood_light': (180, 150, 120),
        'wood_dark': (120, 90, 60),
    }

    # Engineering - Workbench/workshop
    ENGINEERING = {
        'wood_light': (180, 140, 100),
        'wood_mid': (140, 100, 70),
        'wood_dark': (90, 65, 45),
        'metal': (150, 155, 160),
        'metal_shine': (200, 205, 210),
        'copper': (200, 120, 80),
        'brass': (200, 180, 100),
        'tool_steel': (120, 125, 130),
        'background': (60, 50, 45),
        'light_warm': (255, 240, 200),
        'shadow': (40, 35, 30),
    }

    # Enchanting - Light blue spirit theme
    ENCHANTING = {
        'spirit_light': (200, 230, 255),
        'spirit_mid': (150, 200, 255),
        'spirit_core': (100, 180, 255),
        'glow_white': (240, 250, 255),
        'particle': (180, 220, 255),
        'rune_active': (120, 200, 255),
        'rune_dormant': (80, 120, 160),
        'nature_green': (150, 220, 180),
        'background_light': (20, 35, 50),
        'background_dark': (10, 20, 35),
        'aura': (100, 180, 240),
    }


# =============================================================================
# ANIMATION TIMER
# =============================================================================

class AnimationTimer:
    """Utility for frame-independent animation timing."""

    def __init__(self):
        self.last_time = pygame.time.get_ticks()

    def tick(self) -> float:
        """Returns delta time in seconds since last tick."""
        current = pygame.time.get_ticks()
        delta = (current - self.last_time) / 1000.0
        self.last_time = current
        return min(delta, 0.1)  # Cap at 100ms to prevent huge jumps

    def reset(self):
        """Reset the timer."""
        self.last_time = pygame.time.get_ticks()


# =============================================================================
# BASE PARTICLE CLASS
# =============================================================================

@dataclass
class Particle:
    """Base particle class for all particle effects."""
    x: float
    y: float
    vx: float = 0.0
    vy: float = 0.0
    life: float = 1.0
    max_life: float = 1.0
    size: float = 5.0
    color: Tuple[int, int, int] = (255, 255, 255)
    alpha: int = 255
    gravity: float = 0.0
    drag: float = 0.0

    def update(self, dt: float) -> bool:
        """Update particle state. Returns False if particle should be removed."""
        self.x += self.vx * dt
        self.y += self.vy * dt
        self.vy += self.gravity * dt
        self.vx *= (1 - self.drag * dt)
        self.vy *= (1 - self.drag * dt)
        self.life -= dt
        self.alpha = int(255 * (self.life / self.max_life))
        return self.life > 0

    def draw(self, surface: pygame.Surface):
        """Draw the particle."""
        if self.alpha <= 0:
            return
        size = max(1, int(self.size * (self.life / self.max_life)))
        particle_surf = pygame.Surface((size * 2, size * 2), pygame.SRCALPHA)
        pygame.draw.circle(particle_surf, (*self.color, self.alpha), (size, size), size)
        surface.blit(particle_surf, (int(self.x - size), int(self.y - size)))


# =============================================================================
# PARTICLE SYSTEM
# =============================================================================

class ParticleSystem:
    """Manages a collection of particles with efficient batch updates."""

    def __init__(self, max_particles: int = 200):
        self.particles: List[Particle] = []
        self.max_particles = max_particles
        self.timer = AnimationTimer()

    def add(self, particle: Particle):
        """Add a particle to the system."""
        if len(self.particles) < self.max_particles:
            self.particles.append(particle)

    def add_burst(self, particles: List[Particle]):
        """Add multiple particles at once."""
        remaining = self.max_particles - len(self.particles)
        self.particles.extend(particles[:remaining])

    def update(self, dt: float = None):
        """Update all particles."""
        if dt is None:
            dt = self.timer.tick()
        self.particles = [p for p in self.particles if p.update(dt)]

    def draw(self, surface: pygame.Surface):
        """Draw all particles."""
        for p in self.particles:
            p.draw(surface)

    def clear(self):
        """Remove all particles."""
        self.particles.clear()

    @property
    def count(self) -> int:
        """Get current particle count."""
        return len(self.particles)


# =============================================================================
# SPECIALIZED PARTICLE TYPES
# =============================================================================

class SparkParticle(Particle):
    """Bright spark particle for metal work effects."""

    def __init__(self, x: float, y: float, intensity: float = 1.0):
        angle = random.uniform(0, math.pi * 2)
        speed = random.uniform(50, 200) * intensity
        super().__init__(
            x=x, y=y,
            vx=math.cos(angle) * speed,
            vy=math.sin(angle) * speed - 50,  # Bias upward
            life=random.uniform(0.3, 0.8),
            max_life=random.uniform(0.3, 0.8),
            size=random.uniform(2, 5),
            color=random.choice([
                (255, 255, 200),
                (255, 220, 150),
                (255, 200, 100),
            ]),
            gravity=200,
            drag=2.0
        )

    def draw(self, surface: pygame.Surface):
        """Draw spark with trail effect."""
        if self.alpha <= 0:
            return
        # Draw trail
        trail_length = 3
        for i in range(trail_length):
            trail_alpha = int(self.alpha * (1 - i / trail_length) * 0.5)
            trail_x = self.x - self.vx * 0.01 * i
            trail_y = self.y - self.vy * 0.01 * i
            size = max(1, int(self.size * (1 - i / trail_length)))
            trail_surf = pygame.Surface((size * 2, size * 2), pygame.SRCALPHA)
            pygame.draw.circle(trail_surf, (*self.color, trail_alpha), (size, size), size)
            surface.blit(trail_surf, (int(trail_x - size), int(trail_y - size)))
        # Draw main spark
        super().draw(surface)


class EmberParticle(Particle):
    """Glowing ember particle that floats upward."""

    def __init__(self, x: float, y: float, color: Tuple[int, int, int] = None):
        if color is None:
            color = random.choice([
                (255, 150, 50),
                (255, 100, 20),
                (255, 80, 0),
            ])
        super().__init__(
            x=x + random.uniform(-10, 10),
            y=y,
            vx=random.uniform(-20, 20),
            vy=random.uniform(-80, -40),
            life=random.uniform(1.5, 3.0),
            max_life=random.uniform(1.5, 3.0),
            size=random.uniform(3, 8),
            color=color,
            gravity=-10,  # Float upward
            drag=1.0
        )
        self.flicker_phase = random.uniform(0, math.pi * 2)
        self.flicker_speed = random.uniform(5, 15)

    def update(self, dt: float) -> bool:
        self.flicker_phase += self.flicker_speed * dt
        self.vx += math.sin(self.flicker_phase) * 20 * dt  # Gentle sway
        return super().update(dt)

    def draw(self, surface: pygame.Surface):
        if self.alpha <= 0:
            return
        # Flickering glow effect
        flicker = 0.7 + 0.3 * math.sin(self.flicker_phase)
        size = max(1, int(self.size * (self.life / self.max_life) * flicker))

        # Outer glow
        glow_size = size * 2
        glow_surf = pygame.Surface((glow_size * 2, glow_size * 2), pygame.SRCALPHA)
        glow_alpha = int(self.alpha * 0.3 * flicker)
        pygame.draw.circle(glow_surf, (*self.color, glow_alpha), (glow_size, glow_size), glow_size)
        surface.blit(glow_surf, (int(self.x - glow_size), int(self.y - glow_size)))

        # Core
        core_surf = pygame.Surface((size * 2, size * 2), pygame.SRCALPHA)
        core_color = lerp_color(self.color, (255, 255, 200), 0.3)
        pygame.draw.circle(core_surf, (*core_color, self.alpha), (size, size), size)
        surface.blit(core_surf, (int(self.x - size), int(self.y - size)))


class BubbleParticle(Particle):
    """Bubble particle for alchemy effects."""

    def __init__(self, x: float, y: float, size: float = None):
        if size is None:
            size = random.uniform(4, 15)
        super().__init__(
            x=x + random.uniform(-20, 20),
            y=y,
            vx=random.uniform(-10, 10),
            vy=random.uniform(-60, -30),
            life=random.uniform(1.0, 2.5),
            max_life=random.uniform(1.0, 2.5),
            size=size,
            color=(200, 240, 255),
            gravity=-20,
            drag=0.5
        )
        self.wobble_phase = random.uniform(0, math.pi * 2)
        self.wobble_speed = random.uniform(3, 8)

    def update(self, dt: float) -> bool:
        self.wobble_phase += self.wobble_speed * dt
        self.vx = math.sin(self.wobble_phase) * 15
        return super().update(dt)

    def draw(self, surface: pygame.Surface):
        if self.alpha <= 0:
            return
        size = max(2, int(self.size))

        # Bubble body (semi-transparent)
        bubble_surf = pygame.Surface((size * 2 + 4, size * 2 + 4), pygame.SRCALPHA)
        bubble_alpha = int(self.alpha * 0.4)
        pygame.draw.circle(bubble_surf, (200, 240, 255, bubble_alpha), (size + 2, size + 2), size)

        # Bubble outline
        pygame.draw.circle(bubble_surf, (255, 255, 255, int(self.alpha * 0.6)), (size + 2, size + 2), size, 1)

        # Highlight
        highlight_size = max(1, size // 3)
        highlight_pos = (size + 2 - size // 3, size + 2 - size // 3)
        pygame.draw.circle(bubble_surf, (255, 255, 255, int(self.alpha * 0.8)), highlight_pos, highlight_size)

        surface.blit(bubble_surf, (int(self.x - size - 2), int(self.y - size - 2)))


class SteamParticle(Particle):
    """Rising steam/vapor particle."""

    def __init__(self, x: float, y: float, color: Tuple[int, int, int] = (220, 230, 240)):
        super().__init__(
            x=x + random.uniform(-15, 15),
            y=y,
            vx=random.uniform(-15, 15),
            vy=random.uniform(-40, -20),
            life=random.uniform(2.0, 4.0),
            max_life=random.uniform(2.0, 4.0),
            size=random.uniform(15, 30),
            color=color,
            gravity=-5,
            drag=0.3
        )
        self.expansion_rate = random.uniform(5, 15)

    def update(self, dt: float) -> bool:
        self.size += self.expansion_rate * dt
        return super().update(dt)

    def draw(self, surface: pygame.Surface):
        if self.alpha <= 0:
            return
        size = max(5, int(self.size))
        steam_alpha = int(self.alpha * 0.3)

        steam_surf = pygame.Surface((size * 2, size * 2), pygame.SRCALPHA)
        pygame.draw.circle(steam_surf, (*self.color, steam_alpha), (size, size), size)
        surface.blit(steam_surf, (int(self.x - size), int(self.y - size)))


class SpiritParticle(Particle):
    """Gentle spirit/magical particle for enchanting."""

    def __init__(self, x: float, y: float, bounds: pygame.Rect = None):
        color = random.choice([
            (180, 220, 255),
            (150, 200, 255),
            (200, 230, 255),
            (170, 230, 200),  # Slight green tint
        ])
        super().__init__(
            x=x,
            y=y,
            vx=random.uniform(-20, 20),
            vy=random.uniform(-20, 20),
            life=random.uniform(3.0, 6.0),
            max_life=random.uniform(3.0, 6.0),
            size=random.uniform(2, 6),
            color=color,
            gravity=0,
            drag=0.5
        )
        self.bounds = bounds
        self.pulse_phase = random.uniform(0, math.pi * 2)
        self.pulse_speed = random.uniform(2, 5)
        self.drift_phase = random.uniform(0, math.pi * 2)

    def update(self, dt: float) -> bool:
        self.pulse_phase += self.pulse_speed * dt
        self.drift_phase += dt

        # Gentle drifting motion
        self.vx = math.sin(self.drift_phase * 0.5) * 30
        self.vy = math.cos(self.drift_phase * 0.7) * 20

        result = super().update(dt)

        # Wrap around bounds if specified
        if self.bounds:
            if self.x < self.bounds.left:
                self.x = self.bounds.right
            elif self.x > self.bounds.right:
                self.x = self.bounds.left
            if self.y < self.bounds.top:
                self.y = self.bounds.bottom
            elif self.y > self.bounds.bottom:
                self.y = self.bounds.top
            return True  # Don't die if within bounds

        return result

    def draw(self, surface: pygame.Surface):
        if self.alpha <= 0:
            return

        pulse = 0.6 + 0.4 * math.sin(self.pulse_phase)
        size = max(1, int(self.size * pulse))
        current_alpha = int(self.alpha * pulse)

        # Soft glow
        glow_size = size * 3
        glow_surf = pygame.Surface((glow_size * 2, glow_size * 2), pygame.SRCALPHA)
        glow_alpha = int(current_alpha * 0.2)
        pygame.draw.circle(glow_surf, (*self.color, glow_alpha), (glow_size, glow_size), glow_size)
        surface.blit(glow_surf, (int(self.x - glow_size), int(self.y - glow_size)))

        # Core
        core_surf = pygame.Surface((size * 2, size * 2), pygame.SRCALPHA)
        pygame.draw.circle(core_surf, (*self.color, current_alpha), (size, size), size)
        surface.blit(core_surf, (int(self.x - size), int(self.y - size)))


class GearToothParticle(Particle):
    """Small metallic particle for gear/mechanical effects."""

    def __init__(self, x: float, y: float):
        super().__init__(
            x=x,
            y=y,
            vx=random.uniform(-100, 100),
            vy=random.uniform(-150, -50),
            life=random.uniform(0.5, 1.2),
            max_life=random.uniform(0.5, 1.2),
            size=random.uniform(2, 4),
            color=random.choice([
                (180, 150, 90),   # Brass
                (200, 180, 100),  # Gold-ish
                (150, 130, 80),   # Dark brass
            ]),
            gravity=400,
            drag=1.0
        )
        self.rotation = random.uniform(0, 360)
        self.rotation_speed = random.uniform(-500, 500)

    def update(self, dt: float) -> bool:
        self.rotation += self.rotation_speed * dt
        return super().update(dt)


# =============================================================================
# VISUAL EFFECTS
# =============================================================================

class ScreenShake:
    """Screen shake effect for impact feedback."""

    def __init__(self):
        self.intensity = 0
        self.duration = 0
        self.start_time = 0
        self.decay = True

    def trigger(self, intensity: float = 5, duration_ms: int = 200, decay: bool = True):
        """Trigger a screen shake."""
        self.intensity = intensity
        self.duration = duration_ms
        self.start_time = pygame.time.get_ticks()
        self.decay = decay

    def get_offset(self) -> Tuple[int, int]:
        """Get current shake offset."""
        if self.duration <= 0:
            return (0, 0)

        elapsed = pygame.time.get_ticks() - self.start_time
        if elapsed >= self.duration:
            self.duration = 0
            return (0, 0)

        if self.decay:
            remaining = 1 - (elapsed / self.duration)
            current_intensity = self.intensity * remaining
        else:
            current_intensity = self.intensity

        return (
            random.randint(-int(current_intensity), int(current_intensity)),
            random.randint(-int(current_intensity), int(current_intensity))
        )

    @property
    def is_active(self) -> bool:
        return self.duration > 0


class GlowEffect:
    """Pulsing glow effect."""

    def __init__(self, color: Tuple[int, int, int], base_radius: int = 20,
                 pulse_amount: int = 5, pulse_speed: float = 3.0):
        self.color = color
        self.base_radius = base_radius
        self.pulse_amount = pulse_amount
        self.pulse_speed = pulse_speed
        self.phase = 0

    def update(self, dt: float):
        self.phase += self.pulse_speed * dt

    def draw(self, surface: pygame.Surface, center: Tuple[int, int], intensity: float = 1.0):
        pulse = math.sin(self.phase) * 0.5 + 0.5
        radius = int(self.base_radius + self.pulse_amount * pulse)
        alpha = int(100 * intensity * (0.5 + 0.5 * pulse))

        glow_surf = pygame.Surface((radius * 2, radius * 2), pygame.SRCALPHA)
        for r in range(radius, 0, -2):
            layer_alpha = int(alpha * (r / radius))
            pygame.draw.circle(glow_surf, (*self.color, layer_alpha), (radius, radius), r)

        surface.blit(glow_surf, (center[0] - radius, center[1] - radius),
                    special_flags=pygame.BLEND_RGBA_ADD)


class FlameEffect:
    """Animated flame effect for forges and kilns."""

    def __init__(self, base_rect: pygame.Rect, flame_count: int = 8,
                 colors: List[Tuple[int, int, int]] = None):
        self.base_rect = base_rect
        self.flame_count = flame_count
        self.colors = colors or [
            (255, 200, 50),   # Yellow core
            (255, 120, 20),   # Orange mid
            (200, 50, 0),     # Red outer
        ]
        self.flames = []
        self._generate_flames()

    def _generate_flames(self):
        for i in range(self.flame_count):
            x = self.base_rect.left + (i + 0.5) * (self.base_rect.width / self.flame_count)
            self.flames.append({
                'x': x,
                'base_y': self.base_rect.bottom,
                'phase': random.uniform(0, math.pi * 2),
                'speed': random.uniform(4, 8),
                'base_height': random.uniform(30, 60),
                'width': self.base_rect.width / self.flame_count * 0.8,
            })

    def update(self, dt: float):
        for flame in self.flames:
            flame['phase'] += flame['speed'] * dt

    def draw(self, surface: pygame.Surface, intensity: float = 1.0):
        for flame in self.flames:
            height = flame['base_height'] * intensity
            height += math.sin(flame['phase']) * 15 * intensity
            height += math.sin(flame['phase'] * 2.3) * 8 * intensity

            # Draw flame layers (back to front)
            for layer, color in enumerate(reversed(self.colors)):
                layer_height = height * (1 - layer * 0.2)
                layer_width = flame['width'] * (1 - layer * 0.15)

                # Create flame shape points
                points = [
                    (flame['x'] - layer_width / 2, flame['base_y']),
                    (flame['x'] - layer_width / 3, flame['base_y'] - layer_height * 0.3),
                    (flame['x'], flame['base_y'] - layer_height),
                    (flame['x'] + layer_width / 3, flame['base_y'] - layer_height * 0.3),
                    (flame['x'] + layer_width / 2, flame['base_y']),
                ]

                # Draw with alpha
                flame_surf = pygame.Surface((int(layer_width) + 10, int(layer_height) + 10), pygame.SRCALPHA)
                adjusted_points = [(p[0] - flame['x'] + layer_width / 2 + 5,
                                   p[1] - flame['base_y'] + layer_height + 5) for p in points]
                alpha = int(200 * intensity)
                pygame.draw.polygon(flame_surf, (*color, alpha), adjusted_points)

                surface.blit(flame_surf,
                           (int(flame['x'] - layer_width / 2 - 5),
                            int(flame['base_y'] - layer_height - 5)))


class RotatingGear:
    """Decorative rotating gear."""

    def __init__(self, center: Tuple[int, int], radius: int, teeth: int = 8,
                 color: Tuple[int, int, int] = (180, 150, 90), rotation_speed: float = 30):
        self.center = center
        self.radius = radius
        self.teeth = teeth
        self.color = color
        self.rotation_speed = rotation_speed
        self.angle = random.uniform(0, 360)

    def update(self, dt: float):
        self.angle = (self.angle + self.rotation_speed * dt) % 360

    def draw(self, surface: pygame.Surface, alpha: int = 255):
        gear_surf = pygame.Surface((self.radius * 3, self.radius * 3), pygame.SRCALPHA)
        center = (self.radius * 1.5, self.radius * 1.5)

        # Outer ring
        pygame.draw.circle(gear_surf, (*self.color, alpha),
                          (int(center[0]), int(center[1])), self.radius, 3)

        # Inner ring
        inner_radius = int(self.radius * 0.6)
        pygame.draw.circle(gear_surf, (*self.color, alpha),
                          (int(center[0]), int(center[1])), inner_radius, 2)

        # Teeth
        tooth_length = self.radius * 0.25
        for i in range(self.teeth):
            tooth_angle = math.radians(self.angle + i * (360 / self.teeth))
            inner_x = center[0] + math.cos(tooth_angle) * self.radius
            inner_y = center[1] + math.sin(tooth_angle) * self.radius
            outer_x = center[0] + math.cos(tooth_angle) * (self.radius + tooth_length)
            outer_y = center[1] + math.sin(tooth_angle) * (self.radius + tooth_length)
            pygame.draw.line(gear_surf, (*self.color, alpha),
                           (inner_x, inner_y), (outer_x, outer_y), 3)

        # Center hole
        pygame.draw.circle(gear_surf, (40, 35, 30, alpha),
                          (int(center[0]), int(center[1])), int(self.radius * 0.2))

        # Spokes
        spoke_count = 4
        for i in range(spoke_count):
            spoke_angle = math.radians(self.angle + i * (360 / spoke_count) + 45)
            pygame.draw.line(gear_surf, (*self.color, alpha),
                           (center[0] + math.cos(spoke_angle) * self.radius * 0.25,
                            center[1] + math.sin(spoke_angle) * self.radius * 0.25),
                           (center[0] + math.cos(spoke_angle) * self.radius * 0.55,
                            center[1] + math.sin(spoke_angle) * self.radius * 0.55), 2)

        surface.blit(gear_surf, (self.center[0] - self.radius * 1.5,
                                self.center[1] - self.radius * 1.5))


# =============================================================================
# UI COMPONENTS
# =============================================================================

class AnimatedProgressBar:
    """Progress bar with smooth fill animation and effects."""

    def __init__(self, rect: pygame.Rect, color: Tuple[int, int, int],
                 bg_color: Tuple[int, int, int] = (50, 50, 50),
                 border_color: Tuple[int, int, int] = (100, 100, 100)):
        self.rect = rect
        self.color = color
        self.bg_color = bg_color
        self.border_color = border_color
        self.displayed_progress = 0.0
        self.target_progress = 0.0
        self.glow_intensity = 0.0
        self.animation_speed = 5.0

    def set_progress(self, value: float, instant: bool = False):
        old_quarter = int(self.target_progress * 4)
        new_quarter = int(value * 4)
        if new_quarter > old_quarter:
            self.glow_intensity = 1.0
        self.target_progress = clamp(value, 0, 1)
        if instant:
            self.displayed_progress = self.target_progress

    def update(self, dt: float):
        diff = self.target_progress - self.displayed_progress
        self.displayed_progress += diff * self.animation_speed * dt
        self.glow_intensity = max(0, self.glow_intensity - dt * 2)

    def draw(self, surface: pygame.Surface):
        # Background
        pygame.draw.rect(surface, self.bg_color, self.rect, border_radius=3)

        # Fill
        fill_width = int(self.rect.width * self.displayed_progress)
        if fill_width > 0:
            fill_rect = pygame.Rect(self.rect.left, self.rect.top, fill_width, self.rect.height)

            color = self.color
            if self.glow_intensity > 0:
                color = lerp_color(self.color, (255, 255, 255), self.glow_intensity * 0.5)

            pygame.draw.rect(surface, color, fill_rect, border_radius=3)

            # Shine effect
            shine_rect = pygame.Rect(fill_rect.left, fill_rect.top,
                                    fill_rect.width, fill_rect.height // 3)
            shine_color = lerp_color(color, (255, 255, 255), 0.3)
            pygame.draw.rect(surface, shine_color, shine_rect, border_radius=2)

        # Border
        pygame.draw.rect(surface, self.border_color, self.rect, 2, border_radius=3)


class AnimatedButton:
    """Button with hover and press animations."""

    def __init__(self, rect: pygame.Rect, text: str,
                 base_color: Tuple[int, int, int] = (80, 80, 90),
                 hover_color: Tuple[int, int, int] = (100, 100, 120),
                 press_color: Tuple[int, int, int] = (60, 60, 70),
                 text_color: Tuple[int, int, int] = (255, 255, 255)):
        self.rect = rect
        self.text = text
        self.base_color = base_color
        self.hover_color = hover_color
        self.press_color = press_color
        self.text_color = text_color
        self.current_color = base_color
        self.scale = 1.0
        self.target_scale = 1.0
        self.hovered = False
        self.pressed = False

    def update(self, mouse_pos: Tuple[int, int], mouse_pressed: bool, dt: float) -> bool:
        """Update button state. Returns True if clicked this frame."""
        was_pressed = self.pressed
        self.hovered = self.rect.collidepoint(mouse_pos)

        if self.hovered:
            if mouse_pressed:
                self.pressed = True
                self.target_scale = 0.95
            else:
                if self.pressed:
                    self.pressed = False
                    self.target_scale = 1.0
                    return True  # Click!
                self.target_scale = 1.02
        else:
            self.pressed = False
            self.target_scale = 1.0

        # Animate scale
        self.scale += (self.target_scale - self.scale) * 10 * dt

        # Animate color
        target_color = self.press_color if self.pressed else (
            self.hover_color if self.hovered else self.base_color)
        self.current_color = lerp_color(self.current_color, target_color, 8 * dt)

        return False

    def draw(self, surface: pygame.Surface, font: pygame.font.Font):
        # Calculate scaled rect
        scaled_width = int(self.rect.width * self.scale)
        scaled_height = int(self.rect.height * self.scale)
        scaled_rect = pygame.Rect(
            self.rect.centerx - scaled_width // 2,
            self.rect.centery - scaled_height // 2,
            scaled_width, scaled_height
        )

        # Button background
        pygame.draw.rect(surface, self.current_color, scaled_rect, border_radius=5)

        # Top highlight
        highlight_rect = pygame.Rect(scaled_rect.left + 2, scaled_rect.top + 2,
                                    scaled_rect.width - 4, scaled_rect.height // 3)
        highlight_color = lerp_color(self.current_color, (255, 255, 255), 0.2)
        pygame.draw.rect(surface, highlight_color, highlight_rect, border_radius=3)

        # Border
        pygame.draw.rect(surface, (150, 150, 160), scaled_rect, 2, border_radius=5)

        # Text
        text_surf = font.render(self.text, True, self.text_color)
        text_rect = text_surf.get_rect(center=scaled_rect.center)
        surface.blit(text_surf, text_rect)


# =============================================================================
# METADATA DISPLAY OVERLAY
# =============================================================================

class MinigameMetadataOverlay:
    """Displays difficulty, timers, and rewards at minigame start."""

    def __init__(self, duration: float = 8.0):
        self.duration = duration
        self.display_time = 0
        self.active = False
        self.blocking = False  # Blocks minigame input while True
        self.metadata = {}
        self.fade_duration = 0.5
        self.min_display_time = 0.5  # Minimum time before can dismiss

    def show(self, metadata: Dict):
        """
        Show metadata overlay.

        metadata should contain:
        - discipline: str (e.g., "Smithing")
        - difficulty_tier: str (e.g., "Rare")
        - difficulty_points: float
        - time_limit: float (optional, can be None)
        - rewards: dict (optional)
        - special_params: dict (optional, discipline-specific)
        """
        self.metadata = metadata
        self.display_time = self.duration
        self.active = True
        self.blocking = True  # Block minigame until dismissed

    def dismiss(self):
        """Dismiss the overlay early (via click or key press)."""
        if self.active and (self.duration - self.display_time) >= self.min_display_time:
            self.display_time = min(self.display_time, self.fade_duration)
            self.blocking = False

    def is_blocking(self) -> bool:
        """Check if overlay is blocking minigame interaction."""
        return self.blocking and self.active

    def update(self, dt: float):
        if self.active:
            self.display_time -= dt
            if self.display_time <= 0:
                self.active = False
                self.blocking = False

    def draw(self, surface: pygame.Surface, center: Tuple[int, int], font: pygame.font.Font):
        if not self.active:
            return

        # Calculate fade
        if self.display_time < self.fade_duration:
            alpha = int(255 * (self.display_time / self.fade_duration))
        elif self.display_time > self.duration - self.fade_duration:
            alpha = int(255 * ((self.duration - self.display_time) / self.fade_duration))
        else:
            alpha = 255

        # Create overlay surface
        overlay_width = 350
        overlay_height = 200
        overlay = pygame.Surface((overlay_width, overlay_height), pygame.SRCALPHA)

        # Background
        pygame.draw.rect(overlay, (20, 20, 30, int(alpha * 0.9)),
                        (0, 0, overlay_width, overlay_height), border_radius=10)
        pygame.draw.rect(overlay, (100, 100, 120, alpha),
                        (0, 0, overlay_width, overlay_height), 2, border_radius=10)

        # Title
        discipline = self.metadata.get('discipline', 'Crafting')
        title_font = pygame.font.Font(None, 36)
        title = title_font.render(discipline.upper(), True, (255, 255, 255))
        title.set_alpha(alpha)
        overlay.blit(title, (overlay_width // 2 - title.get_width() // 2, 15))

        # Difficulty tier with color
        tier = self.metadata.get('difficulty_tier', 'Common')
        tier_colors = {
            'common': (180, 180, 180),
            'uncommon': (80, 200, 80),
            'rare': (80, 120, 255),
            'epic': (180, 80, 255),
            'legendary': (255, 200, 50),
        }
        tier_color = tier_colors.get(tier.lower(), (200, 200, 200))

        tier_text = font.render(f"Difficulty: {tier}", True, tier_color)
        tier_text.set_alpha(alpha)
        overlay.blit(tier_text, (20, 55))

        # Difficulty points
        points = self.metadata.get('difficulty_points', 0)
        points_text = font.render(f"Points: {points:.1f}", True, (200, 200, 200))
        points_text.set_alpha(alpha)
        overlay.blit(points_text, (20, 80))

        # Time limit if present and not None
        y_offset = 105
        time_limit = self.metadata.get('time_limit')
        if time_limit is not None:
            time_text = font.render(f"Time: {time_limit:.0f}s", True, (200, 200, 200))
            time_text.set_alpha(alpha)
            overlay.blit(time_text, (20, y_offset))
            y_offset += 25

        # Potential rewards
        if 'max_bonus' in self.metadata:
            max_bonus = self.metadata['max_bonus']
            reward_text = font.render(f"Max Bonus: +{(max_bonus-1)*100:.0f}%", True, (100, 255, 100))
            reward_text.set_alpha(alpha)
            overlay.blit(reward_text, (20, y_offset))
            y_offset += 25

        # Special parameters
        if 'special_params' in self.metadata:
            for key, value in list(self.metadata['special_params'].items())[:2]:
                param_text = font.render(f"{key}: {value}", True, (180, 180, 200))
                param_text.set_alpha(alpha)
                overlay.blit(param_text, (20, y_offset))
                y_offset += 25

        # Show remaining time and click hint
        remaining = max(0, self.display_time - self.fade_duration)
        if self.blocking:
            hint_msg = f"Starting in {remaining:.0f}s - Click to begin"
        else:
            hint_msg = "Starting..."
        hint_text = font.render(hint_msg, True, (150, 200, 150))
        hint_text.set_alpha(int(alpha * 0.8))
        overlay.blit(hint_text, (overlay_width // 2 - hint_text.get_width() // 2,
                                overlay_height - 30))

        # Blit to main surface
        surface.blit(overlay, (center[0] - overlay_width // 2,
                              center[1] - overlay_height // 2))


# =============================================================================
# BACKGROUND SYSTEM
# =============================================================================

class MinigameBackground:
    """Base class for minigame backgrounds with optional PNG support."""

    def __init__(self, rect: pygame.Rect):
        self.rect = rect
        self.background_image = None
        self.overlay_alpha = 180

    def load_image(self, path: str) -> bool:
        """Load a PNG background image. Returns True if successful."""
        try:
            self.background_image = pygame.image.load(path).convert_alpha()
            self.background_image = pygame.transform.scale(
                self.background_image, (self.rect.width, self.rect.height))
            return True
        except (pygame.error, FileNotFoundError):
            return False

    def draw_base(self, surface: pygame.Surface):
        """Draw the background (image or generated)."""
        if self.background_image:
            surface.blit(self.background_image, self.rect.topleft)
        else:
            self._draw_generated_background(surface)

    def _draw_generated_background(self, surface: pygame.Surface):
        """Override in subclasses for procedural backgrounds."""
        pygame.draw.rect(surface, (40, 40, 50), self.rect)

    def draw_overlay(self, surface: pygame.Surface, color: Tuple[int, int, int] = (0, 0, 0)):
        """Draw a semi-transparent overlay."""
        overlay = pygame.Surface((self.rect.width, self.rect.height), pygame.SRCALPHA)
        overlay.fill((*color, self.overlay_alpha))
        surface.blit(overlay, self.rect.topleft)


class SmithingBackground(MinigameBackground):
    """Forge-themed background for smithing minigame."""

    def __init__(self, rect: pygame.Rect):
        super().__init__(rect)
        self.flames = FlameEffect(
            pygame.Rect(rect.left + 50, rect.bottom - 80, rect.width - 100, 80),
            flame_count=12,
            colors=[ColorPalette.SMITHING['flame_core'],
                   ColorPalette.SMITHING['flame_mid'],
                   ColorPalette.SMITHING['flame_outer']]
        )
        self.embers = ParticleSystem(max_particles=50)
        self.ember_timer = 0

    def update(self, dt: float):
        self.flames.update(dt)
        self.embers.update(dt)

        self.ember_timer += dt
        if self.ember_timer > 0.1:
            self.ember_timer = 0
            x = random.randint(self.rect.left + 50, self.rect.right - 50)
            self.embers.add(EmberParticle(x, self.rect.bottom - 60))

    def _draw_generated_background(self, surface: pygame.Surface):
        # Dark gradient background
        for y in range(self.rect.height):
            ratio = y / self.rect.height
            color = lerp_color(ColorPalette.SMITHING['background_dark'],
                             ColorPalette.SMITHING['background_glow'], ratio)
            pygame.draw.line(surface, color,
                           (self.rect.left, self.rect.top + y),
                           (self.rect.right, self.rect.top + y))

        # Forge glow at bottom
        glow_height = 100
        for y in range(glow_height):
            alpha = int(100 * (1 - y / glow_height))
            glow_color = (*ColorPalette.SMITHING['ember'], alpha)
            glow_surf = pygame.Surface((self.rect.width, 1), pygame.SRCALPHA)
            glow_surf.fill(glow_color)
            surface.blit(glow_surf, (self.rect.left, self.rect.bottom - glow_height + y))

    def draw(self, surface: pygame.Surface, intensity: float = 1.0):
        self.draw_base(surface)
        self.flames.draw(surface, intensity)
        self.embers.draw(surface)


class RefiningBackground(MinigameBackground):
    """Kiln/foundry-themed background for refining minigame."""

    def __init__(self, rect: pygame.Rect):
        super().__init__(rect)
        self.gears = [
            RotatingGear((rect.left + 60, rect.top + 60), 40, 10,
                        ColorPalette.REFINING['gear_brass'], 20),
            RotatingGear((rect.right - 60, rect.top + 60), 35, 8,
                        ColorPalette.REFINING['gear_brass'], -25),
            RotatingGear((rect.left + 80, rect.bottom - 80), 30, 6,
                        ColorPalette.REFINING['gear_dark'], 15),
            RotatingGear((rect.right - 80, rect.bottom - 80), 45, 12,
                        ColorPalette.REFINING['gear_dark'], -18),
        ]
        self.flames = FlameEffect(
            pygame.Rect(rect.left + 30, rect.bottom - 60, rect.width - 60, 60),
            flame_count=10,
            colors=[ColorPalette.REFINING['kiln_glow'],
                   ColorPalette.REFINING['fire_bronze'],
                   ColorPalette.REFINING['fire_orange']]
        )
        self.molten_glow = GlowEffect(ColorPalette.REFINING['molten'], 150, 20, 2.0)

    def update(self, dt: float):
        for gear in self.gears:
            gear.update(dt)
        self.flames.update(dt)
        self.molten_glow.update(dt)

    def _draw_generated_background(self, surface: pygame.Surface):
        # Dark bronze gradient
        pygame.draw.rect(surface, ColorPalette.REFINING['background'], self.rect)

        # Kiln arch shape at bottom
        arch_rect = pygame.Rect(self.rect.centerx - 150, self.rect.bottom - 120, 300, 120)
        pygame.draw.ellipse(surface, ColorPalette.REFINING['bronze_dark'], arch_rect)

        # Inner kiln glow
        inner_rect = pygame.Rect(self.rect.centerx - 120, self.rect.bottom - 100, 240, 100)
        pygame.draw.ellipse(surface, (80, 50, 30), inner_rect)

    def draw(self, surface: pygame.Surface):
        self.draw_base(surface)

        # Draw gears in background
        for gear in self.gears:
            gear.draw(surface, alpha=120)

        self.flames.draw(surface, 0.8)
        self.molten_glow.draw(surface, (self.rect.centerx, self.rect.bottom - 50))


class AlchemyBackground(MinigameBackground):
    """Lab/wizard tower themed background for alchemy minigame."""

    def __init__(self, rect: pygame.Rect):
        super().__init__(rect)
        self.bubbles = ParticleSystem(max_particles=30)
        self.steam = ParticleSystem(max_particles=20)
        self.bubble_timer = 0
        self.steam_timer = 0
        self.cauldron_rect = pygame.Rect(
            rect.centerx - 80, rect.centery - 20, 160, 120)

    def update(self, dt: float, activity_level: float = 0.5):
        self.bubbles.update(dt)
        self.steam.update(dt)

        # Spawn bubbles based on activity
        self.bubble_timer += dt
        if self.bubble_timer > 0.2 / max(0.1, activity_level):
            self.bubble_timer = 0
            x = self.cauldron_rect.centerx + random.randint(-50, 50)
            y = self.cauldron_rect.centery + random.randint(-20, 20)
            self.bubbles.add(BubbleParticle(x, y))

        # Spawn steam
        self.steam_timer += dt
        if self.steam_timer > 0.3:
            self.steam_timer = 0
            x = self.cauldron_rect.centerx + random.randint(-40, 40)
            self.steam.add(SteamParticle(x, self.cauldron_rect.top - 10))

    def _draw_generated_background(self, surface: pygame.Surface):
        # Light professional background
        pygame.draw.rect(surface, ColorPalette.ALCHEMY['background_light'], self.rect)

        # Subtle wood panel at bottom
        wood_rect = pygame.Rect(self.rect.left, self.rect.bottom - 80,
                               self.rect.width, 80)
        pygame.draw.rect(surface, ColorPalette.ALCHEMY['wood_dark'], wood_rect)

        # Wood grain lines
        for i in range(5):
            y = wood_rect.top + 15 + i * 15
            pygame.draw.line(surface, ColorPalette.ALCHEMY['wood_light'],
                           (self.rect.left, y), (self.rect.right, y), 1)

    def draw_cauldron(self, surface: pygame.Surface, liquid_color: Tuple[int, int, int],
                     fill_level: float = 0.7):
        """Draw the central cauldron."""
        # Cauldron body
        pygame.draw.ellipse(surface, ColorPalette.ALCHEMY['cauldron'],
                           self.cauldron_rect)

        # Liquid
        liquid_height = int(self.cauldron_rect.height * fill_level * 0.6)
        liquid_rect = pygame.Rect(
            self.cauldron_rect.left + 15,
            self.cauldron_rect.centery - liquid_height // 2 + 20,
            self.cauldron_rect.width - 30,
            liquid_height
        )
        pygame.draw.ellipse(surface, liquid_color, liquid_rect)

        # Liquid highlight
        highlight_color = lerp_color(liquid_color, (255, 255, 255), 0.3)
        highlight_rect = pygame.Rect(
            liquid_rect.left + 10, liquid_rect.top + 5,
            liquid_rect.width - 40, liquid_rect.height // 3
        )
        pygame.draw.ellipse(surface, highlight_color, highlight_rect)

        # Cauldron rim
        rim_rect = pygame.Rect(
            self.cauldron_rect.left - 5,
            self.cauldron_rect.top - 10,
            self.cauldron_rect.width + 10,
            30
        )
        pygame.draw.ellipse(surface, (80, 70, 75), rim_rect)

    def draw(self, surface: pygame.Surface, liquid_color: Tuple[int, int, int] = None):
        self.draw_base(surface)

        if liquid_color is None:
            liquid_color = ColorPalette.ALCHEMY['liquid_base']

        self.draw_cauldron(surface, liquid_color)
        self.bubbles.draw(surface)
        self.steam.draw(surface)


class EngineeringBackground(MinigameBackground):
    """Workbench-themed background for engineering minigame."""

    def __init__(self, rect: pygame.Rect):
        super().__init__(rect)
        self.light_flicker = 0
        self.tool_positions = self._generate_tool_positions()

    def _generate_tool_positions(self) -> List[Dict]:
        """Generate positions for scattered tool decorations."""
        tools = []
        # Tools on left side
        tools.append({'type': 'wrench', 'x': self.rect.left + 30, 'y': self.rect.top + 50, 'angle': 25})
        tools.append({'type': 'screwdriver', 'x': self.rect.left + 60, 'y': self.rect.top + 80, 'angle': -15})
        # Tools on right side
        tools.append({'type': 'pliers', 'x': self.rect.right - 50, 'y': self.rect.top + 60, 'angle': 45})
        tools.append({'type': 'hammer', 'x': self.rect.right - 80, 'y': self.rect.bottom - 100, 'angle': -30})
        return tools

    def update(self, dt: float):
        self.light_flicker += dt * 5

    def _draw_generated_background(self, surface: pygame.Surface):
        # Workbench wood background
        pygame.draw.rect(surface, ColorPalette.ENGINEERING['wood_mid'], self.rect)

        # Wood grain texture
        for i in range(0, self.rect.height, 20):
            grain_color = ColorPalette.ENGINEERING['wood_light'] if i % 40 == 0 else ColorPalette.ENGINEERING['wood_dark']
            pygame.draw.line(surface, grain_color,
                           (self.rect.left, self.rect.top + i),
                           (self.rect.right, self.rect.top + i), 1)

        # Warm lighting effect from above
        light_intensity = 0.8 + 0.1 * math.sin(self.light_flicker)
        for y in range(min(150, self.rect.height)):
            alpha = int(40 * (1 - y / 150) * light_intensity)
            light_surf = pygame.Surface((self.rect.width, 1), pygame.SRCALPHA)
            light_surf.fill((*ColorPalette.ENGINEERING['light_warm'], alpha))
            surface.blit(light_surf, (self.rect.left, self.rect.top + y))

    def _draw_tool(self, surface: pygame.Surface, tool: Dict):
        """Draw a simple tool shape."""
        x, y, angle = tool['x'], tool['y'], tool['angle']
        color = ColorPalette.ENGINEERING['tool_steel']

        if tool['type'] == 'wrench':
            # Simple wrench shape
            pygame.draw.line(surface, color, (x, y), (x + 30, y + 10), 4)
            pygame.draw.circle(surface, color, (x + 30, y + 10), 8, 2)
        elif tool['type'] == 'screwdriver':
            pygame.draw.line(surface, ColorPalette.ENGINEERING['wood_dark'],
                           (x, y), (x + 15, y + 5), 6)
            pygame.draw.line(surface, color, (x + 15, y + 5), (x + 35, y + 12), 3)
        elif tool['type'] == 'pliers':
            pygame.draw.line(surface, color, (x, y), (x + 20, y + 15), 3)
            pygame.draw.line(surface, color, (x + 5, y), (x + 25, y + 15), 3)
        elif tool['type'] == 'hammer':
            pygame.draw.line(surface, ColorPalette.ENGINEERING['wood_light'],
                           (x, y), (x + 25, y + 8), 5)
            pygame.draw.rect(surface, color, (x + 20, y, 20, 15))

    def draw(self, surface: pygame.Surface):
        self.draw_base(surface)

        # Draw scattered tools
        for tool in self.tool_positions:
            self._draw_tool(surface, tool)


class EnchantingBackground(MinigameBackground):
    """Light blue spirit-themed background for enchanting minigame."""

    def __init__(self, rect: pygame.Rect):
        super().__init__(rect)
        self.spirits = ParticleSystem(max_particles=40)
        self.spirit_timer = 0
        self.aura_phase = 0

        # Initialize spirit particles
        for _ in range(30):
            x = random.randint(rect.left, rect.right)
            y = random.randint(rect.top, rect.bottom)
            self.spirits.add(SpiritParticle(x, y, rect))

    def update(self, dt: float):
        self.spirits.update(dt)
        self.aura_phase += dt * 2

        # Maintain spirit count
        self.spirit_timer += dt
        if self.spirit_timer > 0.5 and self.spirits.count < 30:
            self.spirit_timer = 0
            x = random.randint(self.rect.left, self.rect.right)
            y = random.randint(self.rect.top, self.rect.bottom)
            self.spirits.add(SpiritParticle(x, y, self.rect))

    def _draw_generated_background(self, surface: pygame.Surface):
        # Dark blue gradient with subtle variation
        for y in range(self.rect.height):
            ratio = y / self.rect.height
            color = lerp_color(ColorPalette.ENCHANTING['background_dark'],
                             ColorPalette.ENCHANTING['background_light'], ratio * 0.5)
            pygame.draw.line(surface, color,
                           (self.rect.left, self.rect.top + y),
                           (self.rect.right, self.rect.top + y))

        # Central aura glow
        aura_intensity = 0.5 + 0.3 * math.sin(self.aura_phase)
        aura_radius = 200
        center = (self.rect.centerx, self.rect.centery)

        for r in range(aura_radius, 0, -5):
            alpha = int(30 * (r / aura_radius) * aura_intensity)
            aura_surf = pygame.Surface((r * 2, r * 2), pygame.SRCALPHA)
            pygame.draw.circle(aura_surf, (*ColorPalette.ENCHANTING['aura'], alpha), (r, r), r)
            surface.blit(aura_surf, (center[0] - r, center[1] - r))

    def draw(self, surface: pygame.Surface):
        self.draw_base(surface)
        self.spirits.draw(surface)


# =============================================================================
# EFFECT MANAGER
# =============================================================================

class MinigameEffectsManager:
    """Central manager for all minigame visual effects."""

    def __init__(self):
        self.backgrounds: Dict[str, MinigameBackground] = {}
        self.particle_systems: Dict[str, ParticleSystem] = {}
        self.screen_shake = ScreenShake()
        self.metadata_overlay = MinigameMetadataOverlay()
        self.timer = AnimationTimer()
        self.current_discipline = None

    def initialize_discipline(self, discipline: str, rect: pygame.Rect):
        """Initialize effects for a specific discipline."""
        self.current_discipline = discipline.lower()

        # Create appropriate background
        if discipline.lower() == 'smithing':
            self.backgrounds[discipline] = SmithingBackground(rect)
        elif discipline.lower() == 'refining':
            self.backgrounds[discipline] = RefiningBackground(rect)
        elif discipline.lower() == 'alchemy':
            self.backgrounds[discipline] = AlchemyBackground(rect)
        elif discipline.lower() == 'engineering':
            self.backgrounds[discipline] = EngineeringBackground(rect)
        elif discipline.lower() in ('enchanting', 'adornment'):
            self.backgrounds[discipline] = EnchantingBackground(rect)
        else:
            self.backgrounds[discipline] = MinigameBackground(rect)

        # Create particle system for this discipline
        self.particle_systems[discipline] = ParticleSystem(max_particles=150)

    def show_metadata(self, metadata: Dict):
        """Show the metadata overlay at minigame start."""
        self.metadata_overlay.show(metadata)

    def trigger_shake(self, intensity: float = 5, duration_ms: int = 200):
        """Trigger screen shake effect."""
        self.screen_shake.trigger(intensity, duration_ms)

    def add_sparks(self, x: float, y: float, count: int = 10, intensity: float = 1.0):
        """Add spark particles at position."""
        if self.current_discipline and self.current_discipline in self.particle_systems:
            for _ in range(count):
                self.particle_systems[self.current_discipline].add(
                    SparkParticle(x, y, intensity))

    def add_embers(self, x: float, y: float, count: int = 5):
        """Add ember particles at position."""
        if self.current_discipline and self.current_discipline in self.particle_systems:
            for _ in range(count):
                self.particle_systems[self.current_discipline].add(
                    EmberParticle(x, y))

    def update(self, dt: float = None):
        """Update all effects."""
        if dt is None:
            dt = self.timer.tick()

        # Update current background
        if self.current_discipline and self.current_discipline in self.backgrounds:
            bg = self.backgrounds[self.current_discipline]
            if hasattr(bg, 'update'):
                bg.update(dt)

        # Update particle systems
        for ps in self.particle_systems.values():
            ps.update(dt)

        # Update metadata overlay
        self.metadata_overlay.update(dt)

    def draw(self, surface: pygame.Surface, font: pygame.font.Font = None):
        """Draw all effects."""
        # Apply screen shake offset
        offset = self.screen_shake.get_offset()
        if offset != (0, 0):
            # Create a temporary surface for shake effect
            temp = surface.copy()
            surface.fill((0, 0, 0))
            surface.blit(temp, offset)

        # Draw current background
        if self.current_discipline and self.current_discipline in self.backgrounds:
            self.backgrounds[self.current_discipline].draw(surface)

        # Draw particle systems
        if self.current_discipline and self.current_discipline in self.particle_systems:
            self.particle_systems[self.current_discipline].draw(surface)

        # Draw metadata overlay
        if font and self.current_discipline in self.backgrounds:
            bg = self.backgrounds[self.current_discipline]
            center = (bg.rect.centerx, bg.rect.centery)
            self.metadata_overlay.draw(surface, center, font)

    def cleanup(self):
        """Clean up effects when minigame ends."""
        for ps in self.particle_systems.values():
            ps.clear()
        self.current_discipline = None


# =============================================================================
# SINGLETON ACCESSOR
# =============================================================================

_effects_manager_instance = None

def get_effects_manager() -> MinigameEffectsManager:
    """Get the global effects manager instance."""
    global _effects_manager_instance
    if _effects_manager_instance is None:
        _effects_manager_instance = MinigameEffectsManager()
    return _effects_manager_instance

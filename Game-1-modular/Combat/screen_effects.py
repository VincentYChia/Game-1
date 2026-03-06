"""
Screen-wide visual effects for combat feedback.

Screen shake (restricted to boss/T4/big skill hits), hit pause (freeze frame),
and entity flash tracking. Slow motion removed by design.
"""

import random
from typing import Dict, List, Tuple


class ScreenEffects:
    """Global visual effects manager."""

    def __init__(self):
        # Screen shake
        self.shake_intensity: float = 0.0
        self.shake_duration: float = 0.0
        self.shake_decay: float = 0.0
        self.shake_offset: Tuple[int, int] = (0, 0)

        # Hit pause (freeze frame)
        self.hit_pause_remaining: float = 0.0

        # Entity flash tracking: entity_id -> (color, remaining_ms)
        self.flash_entities: Dict[str, Tuple[Tuple[int, int, int], float]] = {}

        # Dodge afterimage trail: list of (world_x, world_y, alpha, color)
        self.afterimages: List[dict] = []

    def screen_shake(self, intensity: float, duration_ms: float) -> None:
        """Trigger screen shake. Stacks with existing (takes max).

        Should only be called for boss attacks, T4 enemy abilities,
        and high-tier player skills. Not for regular melee hits.
        """
        self.shake_intensity = max(self.shake_intensity, intensity)
        self.shake_duration = max(self.shake_duration, duration_ms)
        self.shake_decay = self.shake_intensity / max(self.shake_duration, 1.0)

    def hit_pause(self, duration_ms: float) -> None:
        """Freeze game world for duration. UI still updates."""
        self.hit_pause_remaining = max(self.hit_pause_remaining, duration_ms)

    def flash_entity(self, entity_id: str,
                     color: Tuple[int, int, int] = (255, 255, 255),
                     duration_ms: float = 80.0) -> None:
        """Mark entity for color flash on next render."""
        self.flash_entities[entity_id] = (color, duration_ms)

    def add_afterimage(self, world_x: float, world_y: float,
                       alpha: int = 180,
                       color: Tuple[int, int, int] = (150, 200, 255),
                       size: float = 1.0) -> None:
        """Add a dodge afterimage ghost at a world position."""
        self.afterimages.append({
            'x': world_x, 'y': world_y,
            'alpha': alpha, 'color': color,
            'size': size, 'max_alpha': alpha,
            'life': 300.0,  # ms
            'max_life': 300.0,
        })

    def update(self, dt_ms: float) -> None:
        """Advance all effect timers."""
        # Hit pause — if active, only decay pause timer
        if self.hit_pause_remaining > 0:
            self.hit_pause_remaining -= dt_ms
            if self.hit_pause_remaining < 0:
                self.hit_pause_remaining = 0
            return  # Don't decay other effects during pause

        # Screen shake
        if self.shake_duration > 0:
            self.shake_duration -= dt_ms
            self.shake_intensity -= self.shake_decay * dt_ms
            if self.shake_duration <= 0 or self.shake_intensity <= 0:
                self.shake_intensity = 0
                self.shake_duration = 0
                self.shake_offset = (0, 0)
            else:
                mag = int(self.shake_intensity)
                if mag > 0:
                    self.shake_offset = (
                        random.randint(-mag, mag),
                        random.randint(-mag, mag)
                    )
                else:
                    self.shake_offset = (0, 0)

        # Entity flashes
        expired = []
        for eid in list(self.flash_entities.keys()):
            color, remaining = self.flash_entities[eid]
            remaining -= dt_ms
            if remaining <= 0:
                expired.append(eid)
            else:
                self.flash_entities[eid] = (color, remaining)
        for eid in expired:
            del self.flash_entities[eid]

        # Afterimages
        surviving = []
        for img in self.afterimages:
            img['life'] -= dt_ms
            if img['life'] > 0:
                ratio = img['life'] / img['max_life']
                img['alpha'] = int(img['max_alpha'] * ratio)
                surviving.append(img)
        self.afterimages = surviving

    @property
    def is_paused(self) -> bool:
        return self.hit_pause_remaining > 0

    def get_effective_dt(self, raw_dt_ms: float) -> float:
        """Return effective delta time (0 during hit pause)."""
        if self.is_paused:
            return 0.0
        return raw_dt_ms

    def is_entity_flashing(self, entity_id: str) -> bool:
        return entity_id in self.flash_entities

    def get_flash_color(self, entity_id: str) -> Tuple[int, int, int]:
        if entity_id in self.flash_entities:
            return self.flash_entities[entity_id][0]
        return (255, 255, 255)

    def clear(self) -> None:
        """Reset all effects."""
        self.shake_intensity = 0
        self.shake_duration = 0
        self.shake_offset = (0, 0)
        self.hit_pause_remaining = 0
        self.flash_entities.clear()
        self.afterimages.clear()

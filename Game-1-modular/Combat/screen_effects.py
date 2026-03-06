"""
Screen-wide visual effects for combat feedback.

Screen shake, hit pause (freeze frame), time dilation, and entity flash
tracking. These effects modify the entire render output and/or game timing.
"""

import random
from typing import Dict, Tuple


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

        # Time dilation
        self.time_scale: float = 1.0
        self.time_scale_duration: float = 0.0

        # Entity flash tracking: entity_id -> (color, remaining_ms)
        self.flash_entities: Dict[str, Tuple[Tuple[int, int, int], float]] = {}

    def screen_shake(self, intensity: float, duration_ms: float) -> None:
        """Trigger screen shake. Stacks with existing (takes max)."""
        self.shake_intensity = max(self.shake_intensity, intensity)
        self.shake_duration = max(self.shake_duration, duration_ms)
        self.shake_decay = self.shake_intensity / max(self.shake_duration, 1.0)

    def hit_pause(self, duration_ms: float) -> None:
        """Freeze game world for duration. UI still updates."""
        self.hit_pause_remaining = max(self.hit_pause_remaining, duration_ms)

    def slow_motion(self, time_scale: float, duration_ms: float) -> None:
        """Temporary time dilation. Lower = slower."""
        self.time_scale = time_scale
        self.time_scale_duration = duration_ms

    def flash_entity(self, entity_id: str,
                     color: Tuple[int, int, int] = (255, 255, 255),
                     duration_ms: float = 80.0) -> None:
        """Mark entity for color flash on next render."""
        self.flash_entities[entity_id] = (color, duration_ms)

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

        # Time dilation
        if self.time_scale_duration > 0:
            self.time_scale_duration -= dt_ms
            if self.time_scale_duration <= 0:
                self.time_scale = 1.0
                self.time_scale_duration = 0

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

    @property
    def is_paused(self) -> bool:
        return self.hit_pause_remaining > 0

    def get_effective_dt(self, raw_dt_ms: float) -> float:
        """Apply time dilation to delta time."""
        if self.is_paused:
            return 0.0
        return raw_dt_ms * self.time_scale

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
        self.time_scale = 1.0
        self.time_scale_duration = 0
        self.flash_entities.clear()

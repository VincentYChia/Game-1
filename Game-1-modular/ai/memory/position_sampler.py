"""Position Sampler — records player position breadcrumbs at regular intervals."""

from __future__ import annotations

import math
from typing import Optional


class PositionSampler:
    """Records player position every N seconds as a POSITION_SAMPLE event."""

    SAMPLE_INTERVAL = 10.0  # Real seconds between samples

    def __init__(self):
        self._last_sample_time: float = 0.0
        self._last_x: float = 0.0
        self._last_y: float = 0.0

    def update(self, current_real_time: float,
               player_x: float, player_y: float,
               health_pct: float = 1.0) -> bool:
        """Called each frame. Returns True if a sample was published."""
        if current_real_time - self._last_sample_time < self.SAMPLE_INTERVAL:
            return False

        self._last_sample_time = current_real_time

        # Calculate velocity since last sample
        dx = player_x - self._last_x
        dy = player_y - self._last_y
        velocity = math.sqrt(dx * dx + dy * dy) / self.SAMPLE_INTERVAL

        self._last_x = player_x
        self._last_y = player_y

        try:
            from events.event_bus import get_event_bus
            get_event_bus().publish("POSITION_SAMPLE", {
                "position_x": player_x,
                "position_y": player_y,
                "health_pct": health_pct,
                "velocity": velocity,
            }, source="position_sampler")
        except ImportError:
            pass

        return True

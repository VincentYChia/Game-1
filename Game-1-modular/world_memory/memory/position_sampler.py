"""Position Sampler — records player position breadcrumbs at regular intervals."""

from __future__ import annotations

import math
from typing import Optional

from world_memory.memory.config_loader import get_section


class PositionSampler:
    """Records player position every N seconds as a POSITION_SAMPLE event."""

    def __init__(self):
        cfg = get_section("position_sampler")
        self.sample_interval = cfg.get("sample_interval_seconds", 10.0)
        self._last_sample_time: float = 0.0
        self._last_x: float = 0.0
        self._last_y: float = 0.0

    def update(self, current_real_time: float,
               player_x: float, player_y: float,
               health_pct: float = 1.0) -> bool:
        """Called each frame. Returns True if a sample was published."""
        if current_real_time - self._last_sample_time < self.sample_interval:
            return False

        self._last_sample_time = current_real_time

        # Calculate velocity since last sample
        dx = player_x - self._last_x
        dy = player_y - self._last_y
        velocity = math.sqrt(dx * dx + dy * dy) / self.sample_interval

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

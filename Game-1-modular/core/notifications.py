"""Notification system"""

from dataclasses import dataclass
from typing import Tuple
from .config import Config


@dataclass
class Notification:
    """Temporary UI notification message"""
    message: str
    lifetime: float = 3.0
    color: Tuple[int, int, int] = Config.COLOR_NOTIFICATION

    def update(self, dt: float) -> bool:
        """Update notification timer. Returns True if still active."""
        self.lifetime -= dt
        return self.lifetime > 0

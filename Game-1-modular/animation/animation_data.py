"""
Animation data structures for the combat visual system.

Pure dataclasses — no rendering logic, no game logic.
These are the building blocks for sprite animations and procedural effects.
"""

from dataclasses import dataclass, field
from typing import List, Optional

import pygame


@dataclass
class AnimationFrame:
    """A single frame of animation with optional rendering metadata."""

    surface: Optional[pygame.Surface]  # Pre-rendered frame (None for offset-only frames)
    duration_ms: float                 # How long this frame displays
    offset_x: float = 0.0             # Pixel offset from entity center
    offset_y: float = 0.0
    hitbox_active: bool = False        # Whether the attack hitbox is live during this frame
    scale: float = 1.0                # Scale multiplier applied to entity sprite


@dataclass
class AnimationDefinition:
    """A complete animation: sequence of frames with playback metadata."""

    animation_id: str
    frames: List[AnimationFrame] = field(default_factory=list)
    loop: bool = False
    total_duration_ms: float = 0.0

    def __post_init__(self):
        if self.frames:
            self.total_duration_ms = sum(f.duration_ms for f in self.frames)

    def recalculate_duration(self):
        """Recalculate total duration after frames are modified."""
        self.total_duration_ms = sum(f.duration_ms for f in self.frames)

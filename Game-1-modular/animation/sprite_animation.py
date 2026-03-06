"""
Sprite animation player.

Plays an AnimationDefinition frame-by-frame, advancing based on elapsed time.
One SpriteAnimation instance per active animation on an entity.
"""

from typing import Optional, Callable

from animation.animation_data import AnimationDefinition, AnimationFrame


class SpriteAnimation:
    """Plays an AnimationDefinition instance. One per active animation."""

    def __init__(self, definition: AnimationDefinition,
                 on_complete: Optional[Callable] = None):
        self.definition = definition
        self.on_complete = on_complete
        self.elapsed_ms: float = 0.0
        self.current_frame_index: int = 0
        self.finished: bool = False

    def update(self, dt_ms: float) -> None:
        """Advance animation by dt milliseconds."""
        if self.finished:
            return

        self.elapsed_ms += dt_ms

        # Find the correct frame based on accumulated time
        accumulated = 0.0
        for i, frame in enumerate(self.definition.frames):
            accumulated += frame.duration_ms
            if self.elapsed_ms < accumulated:
                self.current_frame_index = i
                return

        # Reached end of frames
        if self.definition.loop:
            self.elapsed_ms %= max(self.definition.total_duration_ms, 0.001)
            self.current_frame_index = 0
        else:
            self.finished = True
            self.current_frame_index = len(self.definition.frames) - 1
            if self.on_complete:
                self.on_complete()

    def get_current_frame(self) -> AnimationFrame:
        """Get the current animation frame."""
        return self.definition.frames[self.current_frame_index]

    @property
    def is_hitbox_active(self) -> bool:
        """Whether the current frame has its hitbox flag set."""
        return self.get_current_frame().hitbox_active

    @property
    def progress(self) -> float:
        """Animation progress from 0.0 to 1.0."""
        if self.definition.total_duration_ms <= 0:
            return 1.0
        return min(1.0, self.elapsed_ms / self.definition.total_duration_ms)

    def reset(self) -> None:
        """Reset animation to beginning."""
        self.elapsed_ms = 0.0
        self.current_frame_index = 0
        self.finished = False

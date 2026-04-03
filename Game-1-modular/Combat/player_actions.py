"""
Player action system: dodge roll and input buffer.

The dodge roll provides invulnerability frames (i-frames) during which
hitbox collisions are ignored. The input buffer queues actions pressed
during animations so they execute when the current action completes.
"""

import math
from typing import Tuple, Optional

# Facing string to angle conversion (matches existing Character.facing values)
FACING_TO_ANGLE = {
    'right': 0.0,
    'down': 90.0,
    'left': 180.0,
    'up': 270.0,
}


class InputBuffer:
    """Queues player inputs during animations for responsive chaining."""

    BUFFER_WINDOW_MS = 200  # Accept inputs this far before current action ends

    def __init__(self):
        self.buffered_action: Optional[str] = None   # "attack", "dodge", "skill"
        self.buffered_data: Optional[dict] = None
        self.buffer_timer: float = 0.0

    def buffer(self, action: str, data: dict = None) -> None:
        """Queue an action."""
        self.buffered_action = action
        self.buffered_data = data or {}
        self.buffer_timer = self.BUFFER_WINDOW_MS

    def consume(self) -> Optional[Tuple[str, dict]]:
        """Get and clear buffered action if still valid."""
        if self.buffered_action and self.buffer_timer > 0:
            action = self.buffered_action
            data = self.buffered_data or {}
            self.buffered_action = None
            self.buffered_data = None
            self.buffer_timer = 0
            return (action, data)
        return None

    def update(self, dt_ms: float) -> None:
        if self.buffer_timer > 0:
            self.buffer_timer -= dt_ms
            if self.buffer_timer <= 0:
                self.buffered_action = None
                self.buffered_data = None
                self.buffer_timer = 0

    def clear(self) -> None:
        self.buffered_action = None
        self.buffered_data = None
        self.buffer_timer = 0


class PlayerActionSystem:
    """Manages dodge rolls and input buffering for the player."""

    def __init__(self):
        # Dodge state
        self.is_dodging: bool = False
        self.dodge_timer: float = 0.0
        self.dodge_cooldown: float = 0.0
        self.iframe_timer: float = 0.0
        self.dodge_direction: Tuple[float, float] = (0.0, 0.0)

        # Configurable parameters (can be tuned via config/JSON)
        self.dodge_duration_ms: float = 250.0
        self.dodge_speed_mult: float = 3.0
        self.dodge_cooldown_ms: float = 800.0
        self.iframe_duration_ms: float = 200.0

        # Input buffer
        self.input_buffer = InputBuffer()

        # Stats tracking
        self.total_dodges: int = 0
        self.successful_dodges: int = 0  # Dodges that avoided damage

    @property
    def is_invulnerable(self) -> bool:
        """Whether the player has active i-frames."""
        return self.iframe_timer > 0

    @property
    def dodge_cooldown_remaining(self) -> float:
        return max(0.0, self.dodge_cooldown)

    @property
    def can_dodge(self) -> bool:
        return not self.is_dodging and self.dodge_cooldown <= 0

    def try_dodge(self, direction: Tuple[float, float],
                  facing: str = "down") -> bool:
        """Initiate dodge roll.

        Args:
            direction: (dx, dy) from held movement keys
            facing: Current facing direction string (fallback if no input)

        Returns False if on cooldown or already dodging.
        """
        if not self.can_dodge:
            return False

        # Normalize direction
        mag = math.sqrt(direction[0] ** 2 + direction[1] ** 2)
        if mag < 0.01:
            # No direction input — dodge in facing direction
            angle = math.radians(FACING_TO_ANGLE.get(facing, 270.0))
            self.dodge_direction = (math.cos(angle), math.sin(angle))
        else:
            self.dodge_direction = (direction[0] / mag, direction[1] / mag)

        self.is_dodging = True
        self.dodge_timer = self.dodge_duration_ms
        self.iframe_timer = self.iframe_duration_ms
        self.dodge_cooldown = self.dodge_cooldown_ms
        self.total_dodges += 1

        # Publish DODGE_PERFORMED to GameEventBus for World Memory System
        try:
            from events.event_bus import get_event_bus
            get_event_bus().publish("DODGE_PERFORMED", {
                "actor_id": "player",
                "position_x": position[0] if position else 0,
                "position_y": position[1] if position else 0,
            })
        except Exception:
            pass

        return True

    def update(self, dt_ms: float) -> None:
        """Update dodge state and input buffer."""
        # Update dodge
        if self.is_dodging:
            self.dodge_timer -= dt_ms
            if self.dodge_timer <= 0:
                self.is_dodging = False
                self.dodge_timer = 0

        # Update i-frames (can outlast dodge roll)
        if self.iframe_timer > 0:
            self.iframe_timer -= dt_ms
            if self.iframe_timer <= 0:
                self.iframe_timer = 0

        # Update cooldown
        if self.dodge_cooldown > 0:
            self.dodge_cooldown -= dt_ms
            if self.dodge_cooldown <= 0:
                self.dodge_cooldown = 0

        # Update input buffer
        self.input_buffer.update(dt_ms)

    def get_dodge_velocity(self, base_speed: float) -> Tuple[float, float]:
        """Returns (dx, dy) movement during dodge roll.

        Args:
            base_speed: Player's normal movement speed (Config.PLAYER_SPEED)
        """
        if not self.is_dodging:
            return (0.0, 0.0)
        speed = base_speed * self.dodge_speed_mult
        return (self.dodge_direction[0] * speed,
                self.dodge_direction[1] * speed)

    def record_dodge_success(self) -> None:
        """Called when a dodge roll successfully avoided an attack."""
        self.successful_dodges += 1

    def force_reset(self) -> None:
        """Reset all state (used on death, load, etc.)."""
        self.is_dodging = False
        self.dodge_timer = 0
        self.dodge_cooldown = 0
        self.iframe_timer = 0
        self.dodge_direction = (0.0, 0.0)
        self.input_buffer.clear()

    def to_dict(self) -> dict:
        """Serialize stats for save system."""
        return {
            "total_dodges": self.total_dodges,
            "successful_dodges": self.successful_dodges,
        }

    def from_dict(self, data: dict) -> None:
        """Restore stats from save data."""
        self.total_dodges = data.get("total_dodges", 0)
        self.successful_dodges = data.get("successful_dodges", 0)

"""Damage number display entity"""

from dataclasses import dataclass

from data.models import Position


@dataclass
class DamageNumber:
    damage: int
    position: Position
    is_crit: bool
    lifetime: float = 1.0
    velocity_y: float = -1.0

    def update(self, dt: float) -> bool:
        self.lifetime -= dt
        self.position.y += self.velocity_y * dt
        return self.lifetime > 0

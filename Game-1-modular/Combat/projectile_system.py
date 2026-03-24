"""
Projectile system for ranged combat.

Projectiles are hitboxes that travel through space with velocity.
They check collision against hurtboxes each frame and can optionally
spawn AoE hitboxes on impact (explosions).
"""

import math
from dataclasses import dataclass, field
from typing import Dict, List, Tuple, Set, Optional, Any

from Combat.combat_event import HitEvent
from Combat.hitbox_system import HitboxSystem, HitboxDefinition


@dataclass
class ProjectileDefinition:
    """Static definition of a projectile type. Loaded from JSON."""

    projectile_id: str
    speed: float = 10.0               # Tiles per second
    max_range: float = 15.0           # Tiles before despawn
    hitbox_radius: float = 0.3        # Collision radius in tiles
    sprite_id: str = "magic_bolt"     # Visual asset key
    trail_type: Optional[str] = None  # "fire_trail", "ice_trail", etc.
    homing: float = 0.0              # 0 = straight, 1.0 = missile lock
    gravity: float = 0.0            # Tiles/sec² downward
    piercing: bool = False           # Pass through first target?
    aoe_on_hit: Optional[Dict[str, Any]] = None  # Hitbox def dict for explosion
    aoe_duration_ms: float = 100.0
    visual: Dict[str, Any] = field(default_factory=dict)  # shape, color, glow, etc.
    tags: List[str] = field(default_factory=list)           # element/behavior tags

    def __post_init__(self):
        if self.aoe_on_hit is None:
            self.aoe_on_hit = None


class Projectile:
    """A live projectile in the world."""

    def __init__(self, definition: ProjectileDefinition,
                 start_pos: Tuple[float, float],
                 direction_angle: float,
                 owner_id: str,
                 damage_context: Dict[str, Any]):
        self.definition = definition
        self.x, self.y = start_pos
        self.owner_id = owner_id
        self.damage_context = damage_context
        self.alive = True
        self.distance_traveled = 0.0
        self.hits: Set[str] = set()

        angle_rad = math.radians(direction_angle)
        self.vx = math.cos(angle_rad) * definition.speed
        self.vy = math.sin(angle_rad) * definition.speed
        self.facing_angle = direction_angle

        # Homing target position (set externally if needed)
        self.target_x: Optional[float] = None
        self.target_y: Optional[float] = None

    def update(self, dt_sec: float) -> None:
        if not self.alive:
            return

        # Gravity (arcing projectiles)
        if self.definition.gravity > 0:
            self.vy += self.definition.gravity * dt_sec

        # Homing (gentle steering)
        if self.definition.homing > 0 and self.target_x is not None:
            desired_dx = self.target_x - self.x
            desired_dy = self.target_y - self.y
            desired_angle = math.atan2(desired_dy, desired_dx)
            current_angle = math.atan2(self.vy, self.vx)

            angle_diff = (desired_angle - current_angle + math.pi) % (2 * math.pi) - math.pi
            steer = angle_diff * self.definition.homing * dt_sec * 5.0
            new_angle = current_angle + steer

            speed = math.sqrt(self.vx ** 2 + self.vy ** 2)
            self.vx = math.cos(new_angle) * speed
            self.vy = math.sin(new_angle) * speed

        # Move
        move_x = self.vx * dt_sec
        move_y = self.vy * dt_sec
        self.x += move_x
        self.y += move_y
        self.distance_traveled += math.sqrt(move_x ** 2 + move_y ** 2)

        # Update facing angle for rendering
        if abs(self.vx) > 0.001 or abs(self.vy) > 0.001:
            self.facing_angle = math.degrees(math.atan2(self.vy, self.vx))

        # Range check
        if self.distance_traveled >= self.definition.max_range:
            self.alive = False


class ProjectileSystem:
    """Manages all active projectiles."""

    def __init__(self, hitbox_system: HitboxSystem):
        self.projectiles: List[Projectile] = []
        self.hitbox_system = hitbox_system

    def spawn(self, proj_def: ProjectileDefinition,
              start: Tuple[float, float], direction_angle: float,
              owner_id: str, damage_context: Dict[str, Any],
              target_pos: Optional[Tuple[float, float]] = None) -> Projectile:
        proj = Projectile(proj_def, start, direction_angle, owner_id, damage_context)
        if target_pos and proj_def.homing > 0:
            proj.target_x, proj.target_y = target_pos
        self.projectiles.append(proj)
        return proj

    def update(self, dt_ms: float) -> List[HitEvent]:
        """Move all projectiles, check collisions, handle despawn."""
        dt_sec = dt_ms / 1000.0
        hits = []
        dead = []

        for proj in self.projectiles:
            proj.update(dt_sec)

            if not proj.alive:
                dead.append(proj)
                continue

            # Check collision against all hurtboxes
            for hurtbox in self.hitbox_system.hurtboxes.values():
                if hurtbox.entity_id == proj.owner_id:
                    continue
                if hurtbox.entity_id in proj.hits:
                    continue
                if hurtbox.invulnerable:
                    continue

                dx = hurtbox.world_x - proj.x
                dy = hurtbox.world_y - proj.y
                dist_sq = dx * dx + dy * dy
                combined_r = proj.definition.hitbox_radius + hurtbox.radius
                if dist_sq <= combined_r * combined_r:
                    proj.hits.add(hurtbox.entity_id)
                    hits.append(HitEvent(
                        attacker_id=proj.owner_id,
                        target_id=hurtbox.entity_id,
                        damage_context=proj.damage_context,
                        hit_position=(proj.x, proj.y),
                        is_projectile=True
                    ))

                    if not proj.definition.piercing:
                        proj.alive = False

                    # AoE explosion on impact
                    if proj.definition.aoe_on_hit:
                        aoe_data = proj.definition.aoe_on_hit
                        aoe_def = HitboxDefinition(
                            shape=aoe_data.get("shape", "circle"),
                            radius=aoe_data.get("radius", 2.0)
                        )
                        self.hitbox_system.spawn_hitbox(
                            aoe_def, (proj.x, proj.y), 0.0,
                            proj.owner_id,
                            proj.definition.aoe_duration_ms,
                            proj.damage_context
                        )

                    if not proj.alive:
                        dead.append(proj)
                        break

        for p in dead:
            if p in self.projectiles:
                self.projectiles.remove(p)

        return hits

    def get_active_projectiles(self) -> List[Projectile]:
        """For rendering."""
        return self.projectiles

    def clear(self) -> None:
        self.projectiles.clear()

    @property
    def count(self) -> int:
        return len(self.projectiles)

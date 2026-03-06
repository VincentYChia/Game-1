"""
Hitbox and hurtbox collision system.

Handles geometric collision detection for melee attacks.
All coordinates are in world space (tiles). Angles in degrees,
0 = right, 90 = down (matching pygame's y-down convention).

Hitboxes: Ephemeral attack shapes created during ACTIVE phase.
Hurtboxes: Persistent circles on damageable entities.
"""

import math
from dataclasses import dataclass, field
from typing import Dict, List, Tuple, Set, Optional, Any

from combat.combat_event import HitEvent


@dataclass
class HitboxDefinition:
    """Static definition of a hitbox shape. Loaded from JSON."""

    shape: str = "arc"                  # "circle", "arc", "rect", "line"
    radius: float = 1.5                # tiles (circle, arc)
    arc_degrees: float = 90.0          # degrees (arc only)
    width: float = 1.0                 # tiles (rect only)
    height: float = 0.5               # tiles (rect only)
    length: float = 2.0               # tiles (line only)
    offset_forward: float = 0.8       # tiles ahead of entity center
    offset_lateral: float = 0.0       # tiles left/right
    piercing: bool = False            # hit multiple targets?

    def compute_world_position(self, entity_x: float, entity_y: float,
                               facing_angle: float) -> Tuple[float, float]:
        """Compute hitbox center in world space from entity position and facing."""
        angle_rad = math.radians(facing_angle)
        wx = entity_x + math.cos(angle_rad) * self.offset_forward
        wy = entity_y + math.sin(angle_rad) * self.offset_forward

        if self.offset_lateral != 0:
            perp_rad = angle_rad + math.pi / 2.0
            wx += math.cos(perp_rad) * self.offset_lateral
            wy += math.sin(perp_rad) * self.offset_lateral

        return (wx, wy)


class ActiveHitbox:
    """A live hitbox in the world. Created during ACTIVE phase, expires after duration."""

    def __init__(self, definition: HitboxDefinition,
                 world_x: float, world_y: float, facing_angle: float,
                 owner_id: str, duration_ms: float,
                 damage_context: Dict[str, Any]):
        self.definition = definition
        self.world_x = world_x
        self.world_y = world_y
        self.facing_angle = facing_angle
        self.owner_id = owner_id
        self.remaining_ms = duration_ms
        self.damage_context = damage_context
        self.hits: Set[str] = set()  # Target IDs already hit this swing


class Hurtbox:
    """A persistent collision circle on a damageable entity."""

    __slots__ = ('entity_id', 'radius', 'world_x', 'world_y', 'invulnerable')

    def __init__(self, entity_id: str, radius: float):
        self.entity_id = entity_id
        self.radius = radius
        self.world_x: float = 0.0
        self.world_y: float = 0.0
        self.invulnerable: bool = False


class HitboxSystem:
    """Manages all hitboxes and hurtboxes. Checks collisions each frame."""

    def __init__(self):
        self.active_hitboxes: List[ActiveHitbox] = []
        self.hurtboxes: Dict[str, Hurtbox] = {}

    # --- Hurtbox management ---

    def register_hurtbox(self, entity_id: str, radius: float) -> Hurtbox:
        hb = Hurtbox(entity_id, radius)
        self.hurtboxes[entity_id] = hb
        return hb

    def unregister_hurtbox(self, entity_id: str) -> None:
        self.hurtboxes.pop(entity_id, None)

    def get_hurtbox(self, entity_id: str) -> Optional[Hurtbox]:
        return self.hurtboxes.get(entity_id)

    def update_hurtbox_position(self, entity_id: str,
                                world_x: float, world_y: float) -> None:
        hb = self.hurtboxes.get(entity_id)
        if hb:
            hb.world_x = world_x
            hb.world_y = world_y

    def update_hurtbox_positions(self, positions: Dict[str, Tuple[float, float]]) -> None:
        """Batch update hurtbox positions. Called each frame."""
        for eid, (wx, wy) in positions.items():
            hb = self.hurtboxes.get(eid)
            if hb:
                hb.world_x = wx
                hb.world_y = wy

    # --- Hitbox spawning ---

    def spawn_hitbox(self, definition: HitboxDefinition,
                     world_pos: Tuple[float, float],
                     facing_angle: float, owner_id: str,
                     duration_ms: float,
                     damage_context: Dict[str, Any]) -> ActiveHitbox:
        hb = ActiveHitbox(definition, world_pos[0], world_pos[1],
                          facing_angle, owner_id, duration_ms, damage_context)
        self.active_hitboxes.append(hb)
        return hb

    # --- Per-frame update ---

    def update(self, dt_ms: float) -> List[HitEvent]:
        """Advance hitbox timers, check collisions, return hits."""
        hits = []
        expired = []

        for hitbox in self.active_hitboxes:
            hitbox.remaining_ms -= dt_ms
            if hitbox.remaining_ms <= 0:
                expired.append(hitbox)
                continue

            for hurtbox in self.hurtboxes.values():
                # Skip self-hits
                if hurtbox.entity_id == hitbox.owner_id:
                    continue
                # Skip already-hit targets (unless piercing)
                if hurtbox.entity_id in hitbox.hits and not hitbox.definition.piercing:
                    continue
                # Skip invulnerable (dodge i-frames)
                if hurtbox.invulnerable:
                    continue

                if self._check_collision(hitbox, hurtbox):
                    hitbox.hits.add(hurtbox.entity_id)
                    hits.append(HitEvent(
                        attacker_id=hitbox.owner_id,
                        target_id=hurtbox.entity_id,
                        damage_context=hitbox.damage_context,
                        hit_position=(hurtbox.world_x, hurtbox.world_y),
                        is_projectile=False
                    ))

        for hb in expired:
            self.active_hitboxes.remove(hb)

        return hits

    def clear(self) -> None:
        """Remove all active hitboxes."""
        self.active_hitboxes.clear()

    # --- Collision detection ---

    def _check_collision(self, hitbox: ActiveHitbox, hurtbox: Hurtbox) -> bool:
        shape = hitbox.definition.shape
        if shape == "circle":
            return self._collides_circle_circle(hitbox, hurtbox)
        elif shape == "arc":
            return self._collides_arc_circle(hitbox, hurtbox)
        elif shape == "rect":
            return self._collides_rect_circle(hitbox, hurtbox)
        elif shape == "line":
            return self._collides_line_circle(hitbox, hurtbox)
        return False

    def _collides_circle_circle(self, hitbox: ActiveHitbox,
                                hurtbox: Hurtbox) -> bool:
        dx = hurtbox.world_x - hitbox.world_x
        dy = hurtbox.world_y - hitbox.world_y
        dist_sq = dx * dx + dy * dy
        combined_r = hitbox.definition.radius + hurtbox.radius
        return dist_sq <= combined_r * combined_r

    def _collides_arc_circle(self, hitbox: ActiveHitbox,
                             hurtbox: Hurtbox) -> bool:
        dx = hurtbox.world_x - hitbox.world_x
        dy = hurtbox.world_y - hitbox.world_y
        dist = math.sqrt(dx * dx + dy * dy)

        # Step 1: Distance check
        if dist > hitbox.definition.radius + hurtbox.radius:
            return False

        # Step 2: Angle check — is the hurtbox center within the arc?
        angle_to_target = math.degrees(math.atan2(dy, dx))
        angle_diff = (angle_to_target - hitbox.facing_angle + 180) % 360 - 180
        half_arc = hitbox.definition.arc_degrees / 2.0

        if abs(angle_diff) <= half_arc:
            return True

        # Step 3: Edge overlap — hurtbox center outside arc angle,
        # but the hurtbox circle might still overlap the arc's edge rays
        for sign in (1, -1):
            edge_angle = hitbox.facing_angle + sign * half_arc
            edge_rad = math.radians(edge_angle)
            # Check closest point on arc edge ray to hurtbox center
            # The edge ray goes from hitbox center to radius along edge_angle
            ray_end_x = hitbox.world_x + math.cos(edge_rad) * hitbox.definition.radius
            ray_end_y = hitbox.world_y + math.sin(edge_rad) * hitbox.definition.radius

            # Closest point on line segment to circle center
            seg_dx = ray_end_x - hitbox.world_x
            seg_dy = ray_end_y - hitbox.world_y
            seg_len_sq = seg_dx * seg_dx + seg_dy * seg_dy
            if seg_len_sq < 0.0001:
                continue

            t = max(0.0, min(1.0,
                ((hurtbox.world_x - hitbox.world_x) * seg_dx +
                 (hurtbox.world_y - hitbox.world_y) * seg_dy) / seg_len_sq))

            closest_x = hitbox.world_x + t * seg_dx
            closest_y = hitbox.world_y + t * seg_dy
            edge_dist_sq = ((hurtbox.world_x - closest_x) ** 2 +
                           (hurtbox.world_y - closest_y) ** 2)
            if edge_dist_sq <= hurtbox.radius * hurtbox.radius:
                return True

        return False

    def _collides_rect_circle(self, hitbox: ActiveHitbox,
                              hurtbox: Hurtbox) -> bool:
        # Rotate hurtbox into hitbox's local coordinate space
        dx = hurtbox.world_x - hitbox.world_x
        dy = hurtbox.world_y - hitbox.world_y
        angle_rad = math.radians(-hitbox.facing_angle)
        cos_a = math.cos(angle_rad)
        sin_a = math.sin(angle_rad)
        local_x = dx * cos_a - dy * sin_a
        local_y = dx * sin_a + dy * cos_a

        # Closest point on axis-aligned rect to circle center
        half_w = hitbox.definition.width / 2.0
        half_h = hitbox.definition.height / 2.0
        closest_x = max(-half_w, min(local_x, half_w))
        closest_y = max(-half_h, min(local_y, half_h))

        dist_sq = (local_x - closest_x) ** 2 + (local_y - closest_y) ** 2
        return dist_sq <= hurtbox.radius * hurtbox.radius

    def _collides_line_circle(self, hitbox: ActiveHitbox,
                              hurtbox: Hurtbox) -> bool:
        angle_rad = math.radians(hitbox.facing_angle)
        end_x = hitbox.world_x + math.cos(angle_rad) * hitbox.definition.length
        end_y = hitbox.world_y + math.sin(angle_rad) * hitbox.definition.length

        seg_dx = end_x - hitbox.world_x
        seg_dy = end_y - hitbox.world_y
        seg_len_sq = seg_dx * seg_dx + seg_dy * seg_dy

        if seg_len_sq < 0.0001:
            # Degenerate line — point collision
            dx = hurtbox.world_x - hitbox.world_x
            dy = hurtbox.world_y - hitbox.world_y
            return (dx * dx + dy * dy) <= hurtbox.radius * hurtbox.radius

        t = max(0.0, min(1.0,
            ((hurtbox.world_x - hitbox.world_x) * seg_dx +
             (hurtbox.world_y - hitbox.world_y) * seg_dy) / seg_len_sq))

        closest_x = hitbox.world_x + t * seg_dx
        closest_y = hitbox.world_y + t * seg_dy
        dist_sq = ((hurtbox.world_x - closest_x) ** 2 +
                   (hurtbox.world_y - closest_y) ** 2)
        return dist_sq <= hurtbox.radius * hurtbox.radius

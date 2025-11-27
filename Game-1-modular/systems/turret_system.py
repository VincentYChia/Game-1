"""Turret system for managing placed turret AI and behavior"""

from typing import List, Optional
import time

from data.models import PlacedEntity, PlacedEntityType, Position
from Combat.enemy import Enemy


class TurretSystem:
    """Manages turret AI, targeting, and attacking"""

    def __init__(self):
        pass

    def update(self, placed_entities: List[PlacedEntity], enemies: List[Enemy], dt: float):
        """Update all turrets - find targets and attack"""
        current_time = time.time()

        for entity in placed_entities:
            # Only process turrets
            if entity.entity_type != PlacedEntityType.TURRET:
                continue

            # Find nearest enemy in range
            target = self._find_nearest_enemy(entity, enemies)

            if target:
                entity.target_enemy = target

                # Check if enough time has passed since last attack
                time_since_attack = current_time - entity.last_attack_time
                cooldown = 1.0 / entity.attack_speed  # Convert attacks per second to cooldown

                if time_since_attack >= cooldown:
                    # Attack!
                    self._attack_enemy(entity, target)
                    entity.last_attack_time = current_time
            else:
                entity.target_enemy = None

    def _find_nearest_enemy(self, turret: PlacedEntity, enemies: List[Enemy]) -> Optional[Enemy]:
        """Find the nearest alive enemy within turret's range"""
        nearest = None
        nearest_dist = float('inf')

        for enemy in enemies:
            if not enemy.is_alive:
                continue

            # Calculate distance
            dist = turret.position.distance_to(enemy.position)

            if dist <= turret.range and dist < nearest_dist:
                nearest = enemy
                nearest_dist = dist

        return nearest

    def _attack_enemy(self, turret: PlacedEntity, enemy: Enemy):
        """Turret attacks an enemy"""
        # Apply damage to enemy
        enemy.current_hp -= turret.damage

        # Check if enemy died
        if enemy.current_hp <= 0:
            enemy.is_alive = False
            enemy.current_hp = 0

    def get_turret_target_line(self, turret: PlacedEntity) -> Optional[tuple]:
        """Get line from turret to its target for rendering"""
        if turret.target_enemy and turret.target_enemy.is_alive:
            return (turret.position, turret.target_enemy.position)
        return None

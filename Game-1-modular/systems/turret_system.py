"""Turret system for managing placed turret AI and behavior"""

from typing import List, Optional, TYPE_CHECKING
import time

from data.models import PlacedEntity, PlacedEntityType, Position
from core.effect_executor import get_effect_executor
from core.tag_debug import get_tag_debugger

if TYPE_CHECKING:
    from Combat.enemy import Enemy


class TurretSystem:
    """Manages turret AI, targeting, and attacking"""

    def __init__(self):
        self.effect_executor = get_effect_executor()
        self.debugger = get_tag_debugger()

    def update(self, placed_entities: List[PlacedEntity], combat_manager, dt: float):
        """Update all turrets - find targets and attack"""
        current_time = time.time()

        # Get all active enemies from combat manager
        all_enemies = combat_manager.get_all_active_enemies() if combat_manager else []

        entities_to_remove = []

        for entity in placed_entities:
            # Update lifetime for all placed entities
            entity.time_remaining -= dt
            if entity.time_remaining <= 0:
                entities_to_remove.append(entity)
                continue

            # Only process turrets for combat
            if entity.entity_type != PlacedEntityType.TURRET:
                continue

            # Find nearest enemy in range
            target = self._find_nearest_enemy(entity, all_enemies)

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

        # Remove expired entities
        for entity in entities_to_remove:
            placed_entities.remove(entity)

    def _find_nearest_enemy(self, turret: PlacedEntity, all_enemies: List) -> Optional:
        """Find the nearest alive enemy within turret's range"""
        nearest = None
        nearest_dist = float('inf')

        for enemy in all_enemies:
            if not enemy.is_alive:
                continue

            # Calculate distance - enemy.position is a tuple (x, y)
            enemy_x, enemy_y = enemy.position[0], enemy.position[1]
            dx = turret.position.x - enemy_x
            dy = turret.position.y - enemy_y
            dist = (dx * dx + dy * dy) ** 0.5

            if dist <= turret.range and dist < nearest_dist:
                nearest = enemy
                nearest_dist = dist

        return nearest

    def _attack_enemy(self, turret: PlacedEntity, enemy: 'Enemy'):
        """Turret attacks an enemy using tag system or legacy damage"""
        # Use tag system if turret has tags configured
        if turret.tags and len(turret.tags) > 0:
            # DEBUG: Console output for turret attack
            print(f"\n🏹 TURRET ATTACK")
            print(f"   Turret: {turret.item_id}")
            print(f"   Target: {enemy.definition.name}")
            print(f"   Tags: {', '.join(turret.tags)}")
            if hasattr(turret, 'effect_params') and turret.effect_params:
                print(f"   Effect Params: {turret.effect_params}")

            # Get all enemies for geometry calculations
            # For now, just use the primary target (could expand later)
            available_entities = [enemy]

            # Execute effect using tag system
            try:
                context = self.effect_executor.execute_effect(
                    source=turret,
                    primary_target=enemy,
                    tags=turret.tags,
                    params=turret.effect_params,
                    available_entities=available_entities
                )

                self.debugger.debug(
                    f"Turret {turret.item_id} used tags {turret.tags} on {enemy.definition.name}"
                )

                print(f"   ✓ Effect executed successfully")

            except Exception as e:
                self.debugger.error(f"Turret effect execution failed: {e}")
                print(f"   ✗ Effect execution FAILED: {e}")
                print(f"   Falling back to legacy damage: {turret.damage}")
                # Fall back to legacy damage
                enemy.current_health -= turret.damage
        else:
            # Legacy: Apply simple damage to enemy
            print(f"\n⚠️  TURRET LEGACY ATTACK (NO TAGS)")
            print(f"   Turret: {turret.item_id}")
            print(f"   Target: {enemy.definition.name}")
            print(f"   Damage: {turret.damage}")
            enemy.current_health -= turret.damage

        # Check if enemy died
        if enemy.current_health <= 0:
            enemy.is_alive = False
            enemy.current_health = 0

    def get_turret_target_line(self, turret: PlacedEntity) -> Optional[tuple]:
        """Get line from turret to its target for rendering"""
        if turret.target_enemy and turret.target_enemy.is_alive:
            return (turret.position, turret.target_enemy.position)
        return None

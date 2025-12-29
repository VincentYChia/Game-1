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

        # Update utility devices FIRST (healing beacon, etc.)
        self.update_utility_devices(placed_entities, combat_manager, dt)

        for entity in placed_entities:
            # Update status effects FIRST (before any other logic)
            if hasattr(entity, 'update_status_effects'):
                entity.update_status_effects(dt)

            # Update lifetime for all placed entities
            entity.time_remaining -= dt
            if entity.time_remaining <= 0:
                entities_to_remove.append(entity)
                continue

            # Only process turrets for combat
            if entity.entity_type != PlacedEntityType.TURRET:
                continue

            # Check if disabled by status effects
            if hasattr(entity, 'is_stunned') and entity.is_stunned:
                continue  # Cannot attack while stunned
            if hasattr(entity, 'is_frozen') and entity.is_frozen:
                continue  # Cannot attack while frozen

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

        # Check trap triggers (proximity-based activation)
        triggered_traps = self.check_trap_triggers(placed_entities, all_enemies)
        entities_to_remove.extend(triggered_traps)

        # Check bomb detonations (timed fuse)
        detonated_bombs = self.check_bomb_detonations(placed_entities, all_enemies, dt)
        entities_to_remove.extend(detonated_bombs)

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

    def check_trap_triggers(self, placed_entities: List[PlacedEntity], all_enemies: List) -> List[PlacedEntity]:
        """
        Check if any enemies trigger traps (proximity detection)

        Args:
            placed_entities: List of all placed entities
            all_enemies: List of all enemies to check against

        Returns:
            List of triggered traps to remove
        """
        triggered_traps = []

        for entity in placed_entities:
            if entity.entity_type != PlacedEntityType.TRAP:
                continue

            # Skip already triggered traps
            if hasattr(entity, 'triggered') and entity.triggered:
                continue

            # Get trigger radius from effect params (default 2.0 tiles)
            trigger_radius = entity.effect_params.get('trigger_radius', 2.0) if entity.effect_params else 2.0

            # Check all enemies for proximity
            for enemy in all_enemies:
                if not enemy.is_alive:
                    continue

                # Calculate distance to enemy
                enemy_x, enemy_y = enemy.position[0], enemy.position[1]
                dx = entity.position.x - enemy_x
                dy = entity.position.y - enemy_y
                dist = (dx * dx + dy * dy) ** 0.5

                if dist <= trigger_radius:
                    # TRIGGER TRAP!
                    self._trigger_trap(entity, enemy, all_enemies)
                    entity.triggered = True
                    triggered_traps.append(entity)
                    break  # One trigger per trap per update

        return triggered_traps

    def _trigger_trap(self, trap: PlacedEntity, primary_target, all_enemies: List):
        """
        Execute trap effect using tag system

        Args:
            trap: The trap entity that was triggered
            primary_target: The enemy that triggered the trap
            all_enemies: All enemies for AoE calculations
        """
        print(f"\n💥 TRAP TRIGGERED: {trap.item_id}")
        print(f"   Target: {primary_target.definition.name if hasattr(primary_target, 'definition') else 'Unknown'}")
        print(f"   Tags: {', '.join(trap.tags)}")

        if not trap.tags:
            print(f"   ⚠️ No tags defined for trap")
            return

        try:
            # Execute effect using existing tag system
            context = self.effect_executor.execute_effect(
                source=trap,  # Trap is the source
                primary_target=primary_target,
                tags=trap.tags,
                params=trap.effect_params if trap.effect_params else {},
                available_entities=all_enemies
            )

            print(f"   ✓ Affected {len(context.targets)} target(s)")

        except Exception as e:
            self.debugger.error(f"Trap effect execution failed: {e}")
            print(f"   ✗ Effect execution FAILED: {e}")

    def check_bomb_detonations(self, placed_entities: List[PlacedEntity], all_enemies: List, dt: float) -> List[PlacedEntity]:
        """
        Check if any bombs have expired fuses and detonate them

        Args:
            placed_entities: List of all placed entities
            all_enemies: List of all enemies to damage

        Returns:
            List of detonated bombs to remove
        """
        detonated_bombs = []

        for entity in placed_entities:
            if entity.entity_type != PlacedEntityType.BOMB:
                continue

            # Skip already detonated bombs
            if hasattr(entity, 'triggered') and entity.triggered:
                continue

            # Get fuse duration from effect params (default 3.0 seconds)
            fuse_duration = entity.effect_params.get('fuse_duration', 3.0) if entity.effect_params else 3.0

            # Check if bomb was just placed (initialize fuse timer)
            if not hasattr(entity, 'fuse_timer'):
                entity.fuse_timer = fuse_duration
                print(f"\n💣 BOMB ARMED: {entity.item_id} (fuse: {fuse_duration}s)")

            # Countdown fuse timer (use a separate timer, not time_remaining)
            entity.fuse_timer -= dt

            # Detonate when fuse expires
            if entity.fuse_timer <= 0:
                self._detonate_bomb(entity, all_enemies)
                entity.triggered = True
                detonated_bombs.append(entity)

        return detonated_bombs

    def _detonate_bomb(self, bomb: PlacedEntity, all_enemies: List):
        """
        Detonate bomb using tag system for AoE damage

        Args:
            bomb: The bomb entity that detonated
            all_enemies: All enemies for AoE calculations
        """
        print(f"\n💥💥💥 BOMB DETONATED: {bomb.item_id}")
        print(f"   Position: ({bomb.position.x:.1f}, {bomb.position.y:.1f})")
        print(f"   Tags: {', '.join(bomb.tags)}")

        if not bomb.tags:
            print(f"   ⚠️ No tags defined for bomb")
            return

        # Find all enemies in blast radius for targeting
        blast_radius = bomb.effect_params.get('circle_radius', 3.0) if bomb.effect_params else 3.0

        # Filter enemies within blast radius
        enemies_in_range = []
        for enemy in all_enemies:
            if not enemy.is_alive:
                continue

            # Calculate distance to bomb
            enemy_x, enemy_y = enemy.position[0], enemy.position[1]
            dx = bomb.position.x - enemy_x
            dy = bomb.position.y - enemy_y
            dist = (dx * dx + dy * dy) ** 0.5

            if dist <= blast_radius:
                enemies_in_range.append(enemy)

        print(f"   Enemies in blast radius ({blast_radius} units): {len(enemies_in_range)}")

        # If no enemies in range, still execute effect (for visual feedback)
        # Use closest enemy or first available enemy as primary target
        primary_target = enemies_in_range[0] if enemies_in_range else (all_enemies[0] if all_enemies else None)

        if not primary_target:
            print(f"   ⚠️ No valid targets for bomb effect")
            return

        try:
            # Execute effect using existing tag system
            context = self.effect_executor.execute_effect(
                source=bomb,  # Bomb is the source
                primary_target=primary_target,
                tags=bomb.tags,
                params=bomb.effect_params if bomb.effect_params else {},
                available_entities=all_enemies  # Pass all enemies for geometry calculations
            )

            print(f"   ✓ Affected {len(context.targets)} target(s)")

        except Exception as e:
            self.debugger.error(f"Bomb detonation failed: {e}")
            print(f"   ✗ Detonation FAILED: {e}")

    def update_utility_devices(self, placed_entities: List[PlacedEntity], combat_manager, dt: float):
        """
        Update utility devices (healing beacon, net launcher, EMP)

        Args:
            placed_entities: List of all placed entities
            combat_manager: Combat manager for accessing player
            dt: Delta time
        """
        for entity in placed_entities:
            if entity.entity_type != PlacedEntityType.UTILITY_DEVICE:
                continue

            # HEALING BEACON: Periodic heal in radius
            if entity.item_id == 'healing_beacon':
                self._update_healing_beacon(entity, combat_manager, dt)

            # NET LAUNCHER: Auto-deploy trap that slows/roots enemies
            elif entity.item_id == 'net_launcher':
                self._update_net_launcher(entity, combat_manager, dt)

            # EMP DEVICE: Stuns construct-type enemies
            elif entity.item_id == 'emp_device':
                self._update_emp_device(entity, combat_manager, dt)

    def _update_healing_beacon(self, beacon: PlacedEntity, combat_manager, dt: float):
        """
        Healing beacon heals player in radius periodically

        Effect: "Heals 10 HP/sec in 5 unit radius for 2 minutes"
        """
        if not combat_manager or not hasattr(combat_manager, 'character'):
            return

        player = combat_manager.character

        # Check if player is in range
        heal_radius = 5.0  # 5 unit radius
        dx = beacon.position.x - player.position.x
        dy = beacon.position.y - player.position.y
        dist = (dx * dx + dy * dy) ** 0.5

        if dist <= heal_radius and player.health < player.max_health:
            # Apply heal (10 HP/sec)
            heal_amount = 10.0 * dt
            old_health = player.health
            player.health = min(player.max_health, player.health + heal_amount)
            actual_heal = player.health - old_health

            if actual_heal > 0:
                # Only print every ~1 second to avoid spam
                if not hasattr(beacon, '_heal_print_timer'):
                    beacon._heal_print_timer = 0.0
                beacon._heal_print_timer += dt

                if beacon._heal_print_timer >= 1.0:
                    print(f"💚 Healing Beacon: +{actual_heal:.1f} HP (Player: {player.health:.0f}/{player.max_health:.0f})")
                    beacon._heal_print_timer = 0.0

    def _update_net_launcher(self, net_launcher: PlacedEntity, combat_manager, dt: float):
        """
        Net launcher auto-deploys to slow/root nearby enemies

        Effect: "Fires net that slows enemies by 80% for 10 seconds"
        """
        # Skip if already triggered
        if hasattr(net_launcher, 'triggered') and net_launcher.triggered:
            return

        # Get all enemies
        all_enemies = combat_manager.get_all_active_enemies() if combat_manager else []

        # Check for enemies in range (3 unit trigger radius)
        trigger_radius = 3.0
        for enemy in all_enemies:
            if not enemy.is_alive:
                continue

            # Calculate distance
            enemy_x, enemy_y = enemy.position[0], enemy.position[1]
            dx = net_launcher.position.x - enemy_x
            dy = net_launcher.position.y - enemy_y
            dist = (dx * dx + dy * dy) ** 0.5

            if dist <= trigger_radius:
                # DEPLOY NET!
                print(f"\n🕸️ NET LAUNCHER DEPLOYED: {net_launcher.item_id}")

                # Apply slow to all enemies in area (5 unit effect radius)
                effect_radius = 5.0
                affected_count = 0

                for target in all_enemies:
                    if not target.is_alive:
                        continue

                    # Calculate distance to net launcher
                    target_x, target_y = target.position[0], target.position[1]
                    tdx = net_launcher.position.x - target_x
                    tdy = net_launcher.position.y - target_y
                    tdist = (tdx * tdx + tdy * tdy) ** 0.5

                    if tdist <= effect_radius:
                        # Apply slow status (80% slow = 0.8 speed reduction)
                        if hasattr(target, 'status_manager'):
                            slow_params = {
                                'duration': 10.0,
                                'speed_reduction': 0.8
                            }
                            target.status_manager.apply_status('slow', slow_params, source=net_launcher)
                            affected_count += 1

                print(f"   ✓ Slowed {affected_count} enemies by 80% for 10 seconds")

                # Mark as triggered (one-time use)
                net_launcher.triggered = True
                break

    def _update_emp_device(self, emp: PlacedEntity, combat_manager, dt: float):
        """
        EMP device stuns construct-type enemies in radius

        Effect: "Disables all mechanical devices in 8 unit radius for 30 seconds"
        """
        # Skip if already triggered
        if hasattr(emp, 'triggered') and emp.triggered:
            return

        # Get all enemies
        all_enemies = combat_manager.get_all_active_enemies() if combat_manager else []

        # EMP triggers automatically after short delay (1 second)
        if not hasattr(emp, '_emp_timer'):
            emp._emp_timer = 1.0  # 1 second activation delay
            print(f"\n⚡ EMP DEVICE ARMED: {emp.item_id} (activating in 1s)")

        emp._emp_timer -= dt

        if emp._emp_timer <= 0:
            # ACTIVATE EMP!
            print(f"\n⚡⚡⚡ EMP ACTIVATED: {emp.item_id}")

            # Stun all construct-type enemies in 8 unit radius
            effect_radius = 8.0
            affected_count = 0

            for enemy in all_enemies:
                if not enemy.is_alive:
                    continue

                # Check if enemy is construct type
                enemy_type = enemy.definition.enemy_type if hasattr(enemy.definition, 'enemy_type') else None
                is_construct = enemy_type == 'construct' if enemy_type else False

                # Calculate distance
                enemy_x, enemy_y = enemy.position[0], enemy.position[1]
                dx = emp.position.x - enemy_x
                dy = emp.position.y - enemy_y
                dist = (dx * dx + dy * dy) ** 0.5

                if dist <= effect_radius and is_construct:
                    # Apply stun (30 seconds)
                    if hasattr(enemy, 'status_manager'):
                        stun_params = {'duration': 30.0}
                        enemy.status_manager.apply_status('stun', stun_params, source=emp)
                        affected_count += 1
                        print(f"   🤖 Disabled {enemy.definition.name} (construct)")

            print(f"   ✓ Disabled {affected_count} construct enemies for 30 seconds")

            # Mark as triggered (one-time use)
            emp.triggered = True

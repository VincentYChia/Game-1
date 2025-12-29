"""
Effect Executor - Applies effects to targets
Ties together tag parsing, geometry, status effects, and damage
"""

from typing import List, Any, Optional
import random
from core.tag_system import get_tag_registry
from core.tag_parser import get_tag_parser
from core.effect_context import EffectConfig, EffectContext
from core.geometry import get_target_finder
from core.tag_debug import get_tag_debugger


class EffectExecutor:
    """
    Main executor for tag-based effects
    Coordinates all effect application
    """

    def __init__(self):
        self.registry = get_tag_registry()
        self.parser = get_tag_parser()
        self.target_finder = get_target_finder()
        self.debugger = get_tag_debugger()

    def execute_effect(self, source: Any, primary_target: Any,
                      tags: List[str], params: dict,
                      available_entities: Optional[List[Any]] = None) -> EffectContext:
        """
        Execute an effect from tags

        Args:
            source: Source entity (caster, turret, etc.)
            primary_target: Primary target
            tags: List of tag strings
            params: Effect parameters from JSON
            available_entities: List of all available entities (for geometry)

        Returns:
            EffectContext with execution results
        """
        # Parse tags into config
        config = self.parser.parse(tags, params)
        self.debugger.log_config_parse(config)

        # Create effect context
        context = EffectContext(
            source=source,
            primary_target=primary_target,
            config=config,
            timestamp=0.0  # TODO: Add proper timestamp
        )

        # Find all targets based on geometry
        if available_entities is None:
            available_entities = []

        targets = self.target_finder.find_targets(
            geometry=config.geometry_tag,
            source=source,
            primary_target=primary_target,
            params=config.params,
            context=config.context,
            available_entities=available_entities
        )

        context.targets = targets

        self.debugger.log_effect_application(context)

        # Store current execution context for training dummies and debug
        self._current_source = source
        self._current_tags = tags
        self._current_context = context

        # Apply effects to all targets
        for i, target in enumerate(targets):
            # Calculate damage falloff for geometry
            magnitude_mult = self._calculate_magnitude_multiplier(config, i, len(targets))

            # Apply damage
            if config.base_damage > 0:
                self._apply_damage(source, target, config, magnitude_mult)

            # Apply healing
            if config.base_healing > 0:
                self._apply_healing(source, target, config, magnitude_mult)

            # Apply status effects
            self._apply_status_effects(target, config)

            # Apply special mechanics
            self._apply_special_mechanics(source, target, config, magnitude_mult)

        return context

    def _calculate_magnitude_multiplier(self, config: EffectConfig, target_index: int, total_targets: int) -> float:
        """Calculate damage/healing multiplier based on geometry and position"""
        if config.geometry_tag == 'chain':
            # Chain falloff
            falloff = config.params.get('chain_falloff', 0.3)
            return (1.0 - falloff) ** target_index

        elif config.geometry_tag == 'pierce':
            # Pierce falloff
            falloff = config.params.get('pierce_falloff', 0.1)
            return (1.0 - falloff) ** target_index

        # No falloff for other geometries
        return 1.0

    def _apply_damage(self, source: Any, target: Any, config: EffectConfig, magnitude_mult: float):
        """Apply damage to target"""
        base_damage = config.base_damage * magnitude_mult

        # Check for critical hit mechanic
        crit_multiplier = 1.0
        if 'critical' in config.special_tags:
            crit_chance = config.params.get('crit_chance', 0.15)
            crit_multiplier_param = config.params.get('crit_multiplier', 2.0)

            if random.random() < crit_chance:
                crit_multiplier = crit_multiplier_param
                print(f"   💥 CRITICAL HIT! ({crit_multiplier}x damage)")
                self.debugger.debug(f"Critical hit! Multiplier: {crit_multiplier}x")

        # Apply damage for each damage type
        for damage_tag in config.damage_tags:
            damage = base_damage * crit_multiplier  # Apply crit multiplier

            # Check for type-specific bonuses
            tag_def = self.registry.get_definition(damage_tag)
            if tag_def and tag_def.context_behavior:
                target_category = getattr(target, 'category', None)
                if target_category in tag_def.context_behavior:
                    behavior = tag_def.context_behavior[target_category]

                    # Check for damage multiplier
                    if 'damage_multiplier' in behavior:
                        damage *= behavior['damage_multiplier']
                        self.debugger.info(
                            f"{damage_tag} damage bonus vs {target_category}",
                            multiplier=behavior['damage_multiplier']
                        )

                    # Check for conversion to healing
                    if behavior.get('converts_to_healing', False):
                        self._heal_target(target, damage)
                        self.debugger.info(f"{damage_tag} damage converted to healing for ally")
                        return

            # Actually apply damage
            self._damage_target(target, damage, damage_tag)

            # Auto-apply status chance
            if tag_def and tag_def.auto_apply_status and tag_def.auto_apply_chance > 0:
                if random.random() < tag_def.auto_apply_chance:
                    status_tag = tag_def.auto_apply_status
                    status_params = self.registry.get_default_params(status_tag)
                    self._apply_single_status(target, status_tag, status_params)

    def _apply_healing(self, source: Any, target: Any, config: EffectConfig, magnitude_mult: float):
        """Apply healing to target"""
        healing = config.base_healing * magnitude_mult
        self._heal_target(target, healing)

    def _apply_status_effects(self, target: Any, config: EffectConfig):
        """Apply all status effects to target"""
        for status_tag in config.status_tags:
            # Get parameters for this status
            status_params = {}
            tag_def = self.registry.get_definition(status_tag)

            if tag_def:
                # Merge defaults with config params
                status_params = tag_def.default_params.copy()

                # Override with specific params from config
                for param_key in status_params.keys():
                    if param_key in config.params:
                        status_params[param_key] = config.params[param_key]

            self._apply_single_status(target, status_tag, status_params)

    def _apply_single_status(self, target: Any, status_tag: str, params: dict):
        """Apply a single status effect to target"""
        # Check immunity
        tag_def = self.registry.get_definition(status_tag)
        if tag_def and tag_def.immunity:
            target_category = getattr(target, 'category', None)
            if target_category in tag_def.immunity:
                self.debugger.log_status_immune(target, status_tag)
                return

        # Check for status manager on target
        if hasattr(target, 'status_manager'):
            target.status_manager.apply_status(status_tag, params)
            self.debugger.log_status_application(target, status_tag, params)
        else:
            self.debugger.warning(
                f"Target {getattr(target, 'name', 'Unknown')} has no status_manager, cannot apply {status_tag}"
            )

    def _apply_special_mechanics(self, source: Any, target: Any, config: EffectConfig, magnitude_mult: float):
        """Apply special mechanics (lifesteal, knockback, etc.)"""
        for special_tag in config.special_tags:
            if special_tag == 'lifesteal' or special_tag == 'vampiric':
                self._apply_lifesteal(source, config.base_damage * magnitude_mult, config.params)

            elif special_tag == 'knockback':
                self._apply_knockback(source, target, config.params)

            elif special_tag == 'pull':
                self._apply_pull(source, target, config.params)

            elif special_tag == 'execute':
                self._apply_execute(source, target, config, magnitude_mult)

            elif special_tag == 'critical':
                # Critical is handled in _apply_damage as a damage multiplier
                pass

            elif special_tag == 'teleport' or special_tag == 'blink':
                self._apply_teleport(source, target, config.params)

            elif special_tag == 'dash' or special_tag == 'charge':
                self._apply_dash(source, target, config.params)

            # TODO: Implement other special mechanics
            # - summon
            # - phase

    def _apply_lifesteal(self, source: Any, damage_dealt: float, params: dict):
        """Apply lifesteal healing to source"""
        lifesteal_percent = params.get('lifesteal_percent', 0.15)
        heal_amount = damage_dealt * lifesteal_percent
        self._heal_target(source, heal_amount)
        self.debugger.debug(f"Lifesteal: {heal_amount:.1f} HP to {getattr(source, 'name', 'Unknown')}")

    def _apply_knockback(self, source: Any, target: Any, params: dict):
        """Apply knockback to target as smooth forced movement over time"""
        knockback_distance = params.get('knockback_distance', 2.0)
        knockback_duration = params.get('knockback_duration', 0.5)  # Default 0.5 seconds

        # Get positions
        source_pos = self._get_position(source)
        target_pos = self._get_position(target)

        if not source_pos or not target_pos:
            self.debugger.warning(f"Cannot apply knockback: missing position")
            return

        # Calculate knockback direction (away from source)
        dx = target_pos.x - source_pos.x
        dy = target_pos.y - source_pos.y

        # Normalize direction
        distance = (dx * dx + dy * dy) ** 0.5
        if distance < 0.1:  # Too close, use default direction
            dx, dy = 1.0, 0.0
        else:
            dx /= distance
            dy /= distance

        # Calculate velocity needed to move knockback_distance over knockback_duration
        # velocity = distance / time
        velocity_magnitude = knockback_distance / knockback_duration
        velocity_x = dx * velocity_magnitude
        velocity_y = dy * velocity_magnitude

        # Apply knockback velocity to target
        if hasattr(target, 'knockback_velocity_x'):
            target.knockback_velocity_x = velocity_x
            target.knockback_velocity_y = velocity_y
            target.knockback_duration_remaining = knockback_duration

            self.debugger.debug(
                f"Knockback: {getattr(target, 'name', 'Unknown')} - velocity ({velocity_x:.1f}, {velocity_y:.1f}) for {knockback_duration:.2f}s"
            )
            print(f"   💨 Knockback! {getattr(target, 'name', 'Target')} pushed back {knockback_distance:.1f} tiles over {knockback_duration:.2f}s")
        else:
            self.debugger.warning(f"Target has no knockback velocity fields - cannot apply smooth knockback")

    def _get_position(self, entity: Any):
        """Get position from entity"""
        if not hasattr(entity, 'position'):
            return None

        pos = entity.position

        # Handle Position object
        if hasattr(pos, 'x') and hasattr(pos, 'y'):
            return pos

        # Handle list/tuple [x, y, z]
        if isinstance(pos, (list, tuple)) and len(pos) >= 2:
            from data.models.world import Position
            return Position(pos[0], pos[1], pos[2] if len(pos) > 2 else 0.0)

        return None

    def _apply_pull(self, source: Any, target: Any, params: dict):
        """Apply pull to target"""
        pull_distance = params.get('pull_distance', 2.0)

        # Get positions
        source_pos = self._get_position(source)
        target_pos = self._get_position(target)

        if not source_pos or not target_pos:
            self.debugger.warning(f"Cannot apply pull: missing position")
            return

        # Calculate pull direction (toward source)
        dx = source_pos.x - target_pos.x
        dy = source_pos.y - target_pos.y

        # Normalize direction
        distance = (dx * dx + dy * dy) ** 0.5
        if distance < 0.1:  # Already at source, no pull needed
            return

        # Don't pull past the source
        actual_pull = min(pull_distance, distance)

        dx /= distance
        dy /= distance

        # Calculate new position
        new_x = target_pos.x + dx * actual_pull
        new_y = target_pos.y + dy * actual_pull

        # Apply pull based on entity type
        if hasattr(target, 'position'):
            # Character uses Position object
            if hasattr(target.position, 'x'):
                target.position.x = new_x
                target.position.y = new_y
            # Enemy uses list [x, y, z]
            elif isinstance(target.position, list):
                target.position[0] = new_x
                target.position[1] = new_y

            self.debugger.debug(
                f"Pull: {getattr(target, 'name', 'Unknown')} pulled {actual_pull:.1f} tiles"
            )
            print(f"   🧲 Pull! {getattr(target, 'name', 'Target')} pulled {actual_pull:.1f} tiles")
        else:
            self.debugger.warning(f"Target has no position attribute for pull")

    def _apply_execute(self, source: Any, target: Any, config: EffectConfig, magnitude_mult: float):
        """
        Apply execute mechanic - bonus damage when target is below HP threshold

        Args:
            source: Source entity
            target: Target entity
            config: Effect configuration
            magnitude_mult: Magnitude multiplier
        """
        # Get execute parameters
        threshold_hp = config.params.get('threshold_hp', 0.2)  # Default 20% HP
        bonus_damage = config.params.get('bonus_damage', 2.0)  # Default 2x multiplier

        # Check if target has HP tracking
        if not hasattr(target, 'current_health') or not hasattr(target, 'max_health'):
            return

        # Check HP percentage
        hp_percent = target.current_health / target.max_health if target.max_health > 0 else 0.0

        if hp_percent <= threshold_hp:
            # Target is below threshold - apply execute bonus damage
            base_damage = config.base_damage * magnitude_mult
            execute_damage = base_damage * (bonus_damage - 1.0)  # Bonus portion only

            # Apply the execute damage
            self._damage_target(target, execute_damage, 'execute')

            self.debugger.debug(
                f"Execute: {getattr(target, 'name', 'Unknown')} below {threshold_hp*100:.0f}% HP, "
                f"+{execute_damage:.1f} bonus damage ({bonus_damage}x)"
            )
            print(
                f"   ⚡ EXECUTE! {getattr(target, 'name', 'Target')} below {threshold_hp*100:.0f}% HP! "
                f"+{execute_damage:.1f} bonus damage"
            )

    def _apply_teleport(self, source: Any, target: Any, params: dict):
        """
        Apply teleport mechanic - instant movement to target position

        Args:
            source: Source entity (teleporting entity)
            target: Target position or entity
            params: Teleport parameters
        """
        teleport_range = params.get('teleport_range', 10.0)
        teleport_type = params.get('teleport_type', 'targeted')  # targeted or forward

        # Get source position
        source_pos = self._get_position(source)
        if not source_pos:
            return

        # Determine target position
        if teleport_type == 'targeted' and target:
            target_pos = self._get_position(target)
            if not target_pos:
                return
        else:
            # Forward teleport (not implemented yet - would need facing direction)
            self.debugger.warning("Forward teleport not implemented yet")
            return

        # Calculate distance
        dx = target_pos.x - source_pos.x
        dy = target_pos.y - source_pos.y
        distance = (dx * dx + dy * dy) ** 0.5

        # Check range
        if distance > teleport_range:
            print(f"   ⚠ Teleport failed: target too far ({distance:.1f} > {teleport_range:.1f})")
            return

        # Apply teleport based on entity type
        if hasattr(source, 'position'):
            # Character uses Position object
            if hasattr(source.position, 'x'):
                source.position.x = target_pos.x
                source.position.y = target_pos.y
            # Enemy uses list [x, y, z]
            elif isinstance(source.position, list):
                source.position[0] = target_pos.x
                source.position[1] = target_pos.y

            self.debugger.debug(
                f"Teleport: {getattr(source, 'name', 'Unknown')} teleported {distance:.1f} tiles"
            )
            print(f"   ✨ TELEPORT! {getattr(source, 'name', 'Source')} moved {distance:.1f} tiles instantly")
        else:
            self.debugger.warning(f"Source has no position attribute for teleport")

    def _apply_dash(self, source: Any, target: Any, params: dict):
        """
        Apply dash mechanic - rapid movement toward target

        Args:
            source: Source entity (dashing entity)
            target: Target position or entity
            params: Dash parameters
        """
        dash_distance = params.get('dash_distance', 5.0)
        dash_speed = params.get('dash_speed', 20.0)
        damage_on_contact = params.get('damage_on_contact', False)

        # Get source position
        source_pos = self._get_position(source)
        if not source_pos:
            return

        # Determine target position/direction
        if target:
            target_pos = self._get_position(target)
            if not target_pos:
                return

            # Calculate direction toward target
            dx = target_pos.x - source_pos.x
            dy = target_pos.y - source_pos.y
        else:
            # Would need facing direction - not implemented yet
            self.debugger.warning("Dash without target not implemented yet")
            return

        # Normalize direction
        distance = (dx * dx + dy * dy) ** 0.5
        if distance == 0:
            return

        norm_dx = dx / distance
        norm_dy = dy / distance

        # Calculate actual dash distance (capped at dash_distance)
        actual_dash = min(dash_distance, distance)

        # Calculate new position
        new_x = source_pos.x + norm_dx * actual_dash
        new_y = source_pos.y + norm_dy * actual_dash

        # Apply dash via velocity (similar to knockback but toward target)
        # Use dash_duration calculated from speed
        dash_duration = actual_dash / dash_speed

        if hasattr(source, 'knockback_velocity_x'):  # Reuse knockback system for dash
            # Set velocity toward target
            source.knockback_velocity_x = norm_dx * dash_speed
            source.knockback_velocity_y = norm_dy * dash_speed
            source.knockback_duration_remaining = dash_duration

            self.debugger.debug(
                f"Dash: {getattr(source, 'name', 'Unknown')} dashing {actual_dash:.1f} tiles"
            )
            print(f"   💨 DASH! {getattr(source, 'name', 'Source')} dashing {actual_dash:.1f} tiles")

            # TODO: Implement damage_on_contact during dash
            if damage_on_contact:
                self.debugger.debug("Dash damage_on_contact not implemented yet")
        else:
            # Fallback to instant movement if velocity system not available
            if hasattr(source, 'position'):
                if hasattr(source.position, 'x'):
                    source.position.x = new_x
                    source.position.y = new_y
                elif isinstance(source.position, list):
                    source.position[0] = new_x
                    source.position[1] = new_y

                print(f"   💨 DASH! {getattr(source, 'name', 'Source')} moved {actual_dash:.1f} tiles")

    # Low-level damage/heal functions
    # These should work with the game's entity system

    def _damage_target(self, target: Any, damage: float, damage_type: str):
        """Apply damage to a target entity"""
        # Try different damage methods that might exist
        if hasattr(target, 'take_damage'):
            # Check if target supports enhanced damage info (like training dummy)
            import inspect
            sig = inspect.signature(target.take_damage)
            params = list(sig.parameters.keys())

            # Pass additional context if supported
            if 'source' in params or 'tags' in params or 'context' in params:
                target.take_damage(
                    damage,
                    damage_type,
                    source=getattr(self, '_current_source', None),
                    tags=getattr(self, '_current_tags', []),
                    context=getattr(self, '_current_context', None)
                )
            else:
                target.take_damage(damage, damage_type)
        elif hasattr(target, 'current_health'):
            target.current_health -= damage
            if target.current_health < 0:
                target.current_health = 0
                if hasattr(target, 'is_alive'):
                    target.is_alive = False
        else:
            self.debugger.warning(f"Cannot apply damage to {type(target).__name__} - no damage method")

    def _heal_target(self, target: Any, healing: float):
        """Apply healing to a target entity"""
        if hasattr(target, 'heal'):
            target.heal(healing)
        elif hasattr(target, 'current_health') and hasattr(target, 'max_health'):
            target.current_health = min(target.current_health + healing, target.max_health)
        else:
            self.debugger.warning(f"Cannot apply healing to {type(target).__name__} - no healing method")


# Global executor instance
_executor = None

def get_effect_executor() -> EffectExecutor:
    """Get global effect executor instance"""
    global _executor
    if _executor is None:
        _executor = EffectExecutor()
    return _executor


def execute_effect(source: Any, target: Any, tags: List[str], params: dict,
                  available_entities: Optional[List[Any]] = None) -> EffectContext:
    """
    Convenience function to execute an effect

    Args:
        source: Source entity
        target: Primary target
        tags: List of tag strings
        params: Effect parameters
        available_entities: Available entities for geometry

    Returns:
        EffectContext with results
    """
    executor = get_effect_executor()
    return executor.execute_effect(source, target, tags, params, available_entities)

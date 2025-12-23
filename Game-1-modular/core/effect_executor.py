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

        # Apply damage for each damage type
        for damage_tag in config.damage_tags:
            damage = base_damage

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

            # TODO: Implement other special mechanics
            # - reflect/thorns
            # - summon
            # - teleport
            # - dash/charge
            # - execute
            # - critical

    def _apply_lifesteal(self, source: Any, damage_dealt: float, params: dict):
        """Apply lifesteal healing to source"""
        lifesteal_percent = params.get('lifesteal_percent', 0.15)
        heal_amount = damage_dealt * lifesteal_percent
        self._heal_target(source, heal_amount)
        self.debugger.debug(f"Lifesteal: {heal_amount:.1f} HP to {getattr(source, 'name', 'Unknown')}")

    def _apply_knockback(self, source: Any, target: Any, params: dict):
        """Apply knockback to target"""
        # TODO: Implement knockback physics
        knockback_distance = params.get('knockback_distance', 2.0)
        self.debugger.debug(f"Knockback: {knockback_distance} units (not yet implemented)")

    def _apply_pull(self, source: Any, target: Any, params: dict):
        """Apply pull to target"""
        # TODO: Implement pull physics
        pull_distance = params.get('pull_distance', 2.0)
        self.debugger.debug(f"Pull: {pull_distance} units (not yet implemented)")

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

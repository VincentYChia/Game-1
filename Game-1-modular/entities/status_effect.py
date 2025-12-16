"""
Status Effect System
Handles DoT, CC, buffs/debuffs, and other status effects from the tag system
"""

from dataclasses import dataclass, field
from typing import Dict, Any, Optional
from abc import ABC, abstractmethod


@dataclass
class StatusEffect(ABC):
    """
    Base class for all status effects

    Status effects are temporary conditions applied to entities that modify
    their behavior, stats, or apply damage/healing over time.
    """
    status_id: str                      # Unique ID for this status type (e.g., "burn")
    name: str                           # Display name
    duration: float                     # Total duration in seconds
    duration_remaining: float           # Time remaining in seconds
    stacks: int = 1                     # Current stack count
    max_stacks: int = 1                 # Maximum allowed stacks
    source: Optional[Any] = None        # Source entity that applied this
    params: Dict[str, Any] = field(default_factory=dict)  # Effect-specific parameters

    def update(self, dt: float, target: Any) -> bool:
        """
        Update status effect timer and apply periodic effects

        Args:
            dt: Delta time in seconds
            target: Entity this effect is applied to

        Returns:
            True if effect is still active, False if expired
        """
        self.duration_remaining -= dt

        # Apply periodic effect (DoT, HoT, etc.)
        self._apply_periodic_effect(dt, target)

        return self.duration_remaining > 0

    @abstractmethod
    def on_apply(self, target: Any):
        """Called when effect is first applied to target"""
        pass

    @abstractmethod
    def on_remove(self, target: Any):
        """Called when effect is removed from target"""
        pass

    @abstractmethod
    def _apply_periodic_effect(self, dt: float, target: Any):
        """Apply periodic effects like damage or healing"""
        pass

    def add_stack(self, amount: int = 1):
        """Add stacks to this effect (up to max_stacks)"""
        self.stacks = min(self.stacks + amount, self.max_stacks)

    def refresh_duration(self, new_duration: Optional[float] = None):
        """Refresh duration to original or specified value"""
        if new_duration is not None:
            self.duration = new_duration
            self.duration_remaining = new_duration
        else:
            self.duration_remaining = self.duration

    def get_progress_percent(self) -> float:
        """Get percentage of duration remaining (for UI)"""
        if self.duration <= 0:
            return 0.0
        return max(0.0, min(1.0, self.duration_remaining / self.duration))


# ============================================================================
# DAMAGE OVER TIME (DoT) EFFECTS
# ============================================================================

class BurnEffect(StatusEffect):
    """Fire damage over time"""

    def __init__(self, duration: float, params: Dict[str, Any], source: Any = None):
        super().__init__(
            status_id="burn",
            name="Burning",
            duration=duration,
            duration_remaining=duration,
            max_stacks=params.get('burn_max_stacks', 3),
            source=source,
            params=params
        )
        self.damage_per_second = params.get('burn_damage_per_second', 5.0)

    def on_apply(self, target: Any):
        """Visual: Set entity on fire"""
        if hasattr(target, 'visual_effects'):
            target.visual_effects.add('burn')

    def on_remove(self, target: Any):
        """Visual: Remove fire"""
        if hasattr(target, 'visual_effects'):
            target.visual_effects.remove('burn')

    def _apply_periodic_effect(self, dt: float, target: Any):
        """Apply fire damage"""
        damage = self.damage_per_second * self.stacks * dt
        if hasattr(target, 'take_damage'):
            target.take_damage(damage, 'fire')
        elif hasattr(target, 'current_health'):
            target.current_health = max(0, target.current_health - damage)


class BleedEffect(StatusEffect):
    """Physical damage over time"""

    def __init__(self, duration: float, params: Dict[str, Any], source: Any = None):
        super().__init__(
            status_id="bleed",
            name="Bleeding",
            duration=duration,
            duration_remaining=duration,
            max_stacks=params.get('bleed_max_stacks', 5),
            source=source,
            params=params
        )
        self.damage_per_second = params.get('bleed_damage_per_second', 3.0)

    def on_apply(self, target: Any):
        if hasattr(target, 'visual_effects'):
            target.visual_effects.add('bleed')

    def on_remove(self, target: Any):
        if hasattr(target, 'visual_effects'):
            target.visual_effects.remove('bleed')

    def _apply_periodic_effect(self, dt: float, target: Any):
        """Apply bleed damage"""
        damage = self.damage_per_second * self.stacks * dt
        if hasattr(target, 'take_damage'):
            target.take_damage(damage, 'physical')
        elif hasattr(target, 'current_health'):
            target.current_health = max(0, target.current_health - damage)


class PoisonEffect(StatusEffect):
    """Poison damage over time"""

    def __init__(self, duration: float, params: Dict[str, Any], source: Any = None):
        super().__init__(
            status_id="poison",
            name="Poisoned",
            duration=duration,
            duration_remaining=duration,
            max_stacks=params.get('poison_max_stacks', 10),
            source=source,
            params=params
        )
        self.damage_per_second = params.get('poison_damage_per_second', 2.0)

    def on_apply(self, target: Any):
        if hasattr(target, 'visual_effects'):
            target.visual_effects.add('poison')

    def on_remove(self, target: Any):
        if hasattr(target, 'visual_effects'):
            target.visual_effects.remove('poison')

    def _apply_periodic_effect(self, dt: float, target: Any):
        """Apply poison damage (scales heavily with stacks)"""
        # Poison scales multiplicatively with stacks
        damage = self.damage_per_second * (self.stacks ** 1.2) * dt
        if hasattr(target, 'take_damage'):
            target.take_damage(damage, 'poison')
        elif hasattr(target, 'current_health'):
            target.current_health = max(0, target.current_health - damage)


# ============================================================================
# CROWD CONTROL (CC) EFFECTS
# ============================================================================

class FreezeEffect(StatusEffect):
    """Completely immobilizes target"""

    def __init__(self, duration: float, params: Dict[str, Any], source: Any = None):
        super().__init__(
            status_id="freeze",
            name="Frozen",
            duration=duration,
            duration_remaining=duration,
            max_stacks=1,  # Freeze doesn't stack
            source=source,
            params=params
        )
        self.stored_speed = 0.0

    def on_apply(self, target: Any):
        """Store original speed and set to 0"""
        if hasattr(target, 'speed'):
            self.stored_speed = target.speed
            target.speed = 0.0
        elif hasattr(target, 'movement_speed'):
            self.stored_speed = target.movement_speed
            target.movement_speed = 0.0

        if hasattr(target, 'visual_effects'):
            target.visual_effects.add('freeze')

        # Set frozen flag for AI
        if hasattr(target, 'is_frozen'):
            target.is_frozen = True

    def on_remove(self, target: Any):
        """Restore original speed"""
        if hasattr(target, 'speed'):
            target.speed = self.stored_speed
        elif hasattr(target, 'movement_speed'):
            target.movement_speed = self.stored_speed

        if hasattr(target, 'visual_effects'):
            target.visual_effects.remove('freeze')

        if hasattr(target, 'is_frozen'):
            target.is_frozen = False

    def _apply_periodic_effect(self, dt: float, target: Any):
        """No periodic effect, just immobilization"""
        pass


class SlowEffect(StatusEffect):
    """Reduces movement speed"""

    def __init__(self, duration: float, params: Dict[str, Any], source: Any = None):
        super().__init__(
            status_id="slow",
            name="Slowed",
            duration=duration,
            duration_remaining=duration,
            max_stacks=params.get('slow_max_stacks', 1),  # Usually doesn't stack
            source=source,
            params=params
        )
        self.slow_percent = params.get('slow_percent', 0.5)  # 50% slow by default
        self.stored_speed = 0.0

    def on_apply(self, target: Any):
        """Reduce speed"""
        if hasattr(target, 'speed'):
            self.stored_speed = target.speed
            target.speed *= (1.0 - self.slow_percent)
        elif hasattr(target, 'movement_speed'):
            self.stored_speed = target.movement_speed
            target.movement_speed *= (1.0 - self.slow_percent)

        if hasattr(target, 'visual_effects'):
            target.visual_effects.add('slow')

    def on_remove(self, target: Any):
        """Restore speed"""
        if hasattr(target, 'speed'):
            target.speed = self.stored_speed
        elif hasattr(target, 'movement_speed'):
            target.movement_speed = self.stored_speed

        if hasattr(target, 'visual_effects'):
            target.visual_effects.remove('slow')

    def _apply_periodic_effect(self, dt: float, target: Any):
        """No periodic effect"""
        pass


class StunEffect(StatusEffect):
    """Prevents all actions"""

    def __init__(self, duration: float, params: Dict[str, Any], source: Any = None):
        super().__init__(
            status_id="stun",
            name="Stunned",
            duration=duration,
            duration_remaining=duration,
            max_stacks=1,  # Stun doesn't stack
            source=source,
            params=params
        )

    def on_apply(self, target: Any):
        """Set stunned flag"""
        if hasattr(target, 'is_stunned'):
            target.is_stunned = True

        if hasattr(target, 'visual_effects'):
            target.visual_effects.add('stun')

    def on_remove(self, target: Any):
        """Remove stunned flag"""
        if hasattr(target, 'is_stunned'):
            target.is_stunned = False

        if hasattr(target, 'visual_effects'):
            target.visual_effects.remove('stun')

    def _apply_periodic_effect(self, dt: float, target: Any):
        """No periodic effect"""
        pass


class RootEffect(StatusEffect):
    """Prevents movement but allows actions"""

    def __init__(self, duration: float, params: Dict[str, Any], source: Any = None):
        super().__init__(
            status_id="root",
            name="Rooted",
            duration=duration,
            duration_remaining=duration,
            max_stacks=1,
            source=source,
            params=params
        )
        self.stored_speed = 0.0

    def on_apply(self, target: Any):
        """Set speed to 0"""
        if hasattr(target, 'speed'):
            self.stored_speed = target.speed
            target.speed = 0.0
        elif hasattr(target, 'movement_speed'):
            self.stored_speed = target.movement_speed
            target.movement_speed = 0.0

        if hasattr(target, 'is_rooted'):
            target.is_rooted = True

        if hasattr(target, 'visual_effects'):
            target.visual_effects.add('root')

    def on_remove(self, target: Any):
        """Restore speed"""
        if hasattr(target, 'speed'):
            target.speed = self.stored_speed
        elif hasattr(target, 'movement_speed'):
            target.movement_speed = self.stored_speed

        if hasattr(target, 'is_rooted'):
            target.is_rooted = False

        if hasattr(target, 'visual_effects'):
            target.visual_effects.remove('root')

    def _apply_periodic_effect(self, dt: float, target: Any):
        """No periodic effect"""
        pass


# ============================================================================
# BUFF EFFECTS (Positive)
# ============================================================================

class RegenerationEffect(StatusEffect):
    """Heal over time"""

    def __init__(self, duration: float, params: Dict[str, Any], source: Any = None):
        super().__init__(
            status_id="regeneration",
            name="Regenerating",
            duration=duration,
            duration_remaining=duration,
            max_stacks=params.get('regen_max_stacks', 3),
            source=source,
            params=params
        )
        self.heal_per_second = params.get('regen_heal_per_second', 5.0)

    def on_apply(self, target: Any):
        if hasattr(target, 'visual_effects'):
            target.visual_effects.add('regen')

    def on_remove(self, target: Any):
        if hasattr(target, 'visual_effects'):
            target.visual_effects.remove('regen')

    def _apply_periodic_effect(self, dt: float, target: Any):
        """Apply healing"""
        healing = self.heal_per_second * self.stacks * dt

        if hasattr(target, 'heal'):
            target.heal(healing)
        elif hasattr(target, 'current_health') and hasattr(target, 'max_health'):
            target.current_health = min(target.current_health + healing, target.max_health)


class ShieldEffect(StatusEffect):
    """Temporary shield that absorbs damage"""

    def __init__(self, duration: float, params: Dict[str, Any], source: Any = None):
        super().__init__(
            status_id="shield",
            name="Shielded",
            duration=duration,
            duration_remaining=duration,
            max_stacks=1,  # Shields don't stack, they add to shield value
            source=source,
            params=params
        )
        self.shield_amount = params.get('shield_amount', 50.0)
        self.current_shield = self.shield_amount

    def on_apply(self, target: Any):
        """Add shield to target"""
        if hasattr(target, 'shield_health'):
            target.shield_health += self.shield_amount
        else:
            # Create shield attribute if it doesn't exist
            target.shield_health = self.shield_amount

        if hasattr(target, 'visual_effects'):
            target.visual_effects.add('shield')

    def on_remove(self, target: Any):
        """Remove shield from target"""
        if hasattr(target, 'shield_health'):
            target.shield_health = max(0, target.shield_health - self.current_shield)

        if hasattr(target, 'visual_effects'):
            target.visual_effects.remove('shield')

    def _apply_periodic_effect(self, dt: float, target: Any):
        """No periodic effect, shield is consumed by damage"""
        # Update current shield value from target
        if hasattr(target, 'shield_health'):
            self.current_shield = min(self.shield_amount, target.shield_health)


class HasteEffect(StatusEffect):
    """Increases movement and attack speed"""

    def __init__(self, duration: float, params: Dict[str, Any], source: Any = None):
        super().__init__(
            status_id="haste",
            name="Hasted",
            duration=duration,
            duration_remaining=duration,
            max_stacks=1,
            source=source,
            params=params
        )
        self.speed_bonus = params.get('haste_speed_bonus', 0.3)  # 30% faster
        self.original_speed = 0.0
        self.original_attack_speed = 0.0

    def on_apply(self, target: Any):
        """Increase speed"""
        if hasattr(target, 'speed'):
            self.original_speed = target.speed
            target.speed *= (1.0 + self.speed_bonus)
        elif hasattr(target, 'movement_speed'):
            self.original_speed = target.movement_speed
            target.movement_speed *= (1.0 + self.speed_bonus)

        if hasattr(target, 'attack_speed'):
            self.original_attack_speed = target.attack_speed
            target.attack_speed *= (1.0 + self.speed_bonus)

        if hasattr(target, 'visual_effects'):
            target.visual_effects.add('haste')

    def on_remove(self, target: Any):
        """Restore speed"""
        if hasattr(target, 'speed'):
            target.speed = self.original_speed
        elif hasattr(target, 'movement_speed'):
            target.movement_speed = self.original_speed

        if hasattr(target, 'attack_speed'):
            target.attack_speed = self.original_attack_speed

        if hasattr(target, 'visual_effects'):
            target.visual_effects.remove('haste')

    def _apply_periodic_effect(self, dt: float, target: Any):
        """No periodic effect"""
        pass


# ============================================================================
# DEBUFF EFFECTS (Negative stat modifiers)
# ============================================================================

class WeakenEffect(StatusEffect):
    """Reduces damage dealt"""

    def __init__(self, duration: float, params: Dict[str, Any], source: Any = None):
        super().__init__(
            status_id="weaken",
            name="Weakened",
            duration=duration,
            duration_remaining=duration,
            max_stacks=params.get('weaken_max_stacks', 3),
            source=source,
            params=params
        )
        self.damage_reduction = params.get('weaken_percent', 0.25)  # 25% less damage

    def on_apply(self, target: Any):
        if not hasattr(target, 'damage_multiplier'):
            target.damage_multiplier = 1.0
        target.damage_multiplier *= (1.0 - self.damage_reduction)

        if hasattr(target, 'visual_effects'):
            target.visual_effects.add('weaken')

    def on_remove(self, target: Any):
        if hasattr(target, 'damage_multiplier'):
            target.damage_multiplier /= (1.0 - self.damage_reduction)

        if hasattr(target, 'visual_effects'):
            target.visual_effects.remove('weaken')

    def _apply_periodic_effect(self, dt: float, target: Any):
        """No periodic effect"""
        pass


class VulnerableEffect(StatusEffect):
    """Increases damage taken"""

    def __init__(self, duration: float, params: Dict[str, Any], source: Any = None):
        super().__init__(
            status_id="vulnerable",
            name="Vulnerable",
            duration=duration,
            duration_remaining=duration,
            max_stacks=params.get('vulnerable_max_stacks', 3),
            source=source,
            params=params
        )
        self.damage_increase = params.get('vulnerable_percent', 0.25)  # 25% more damage taken

    def on_apply(self, target: Any):
        if not hasattr(target, 'damage_taken_multiplier'):
            target.damage_taken_multiplier = 1.0
        target.damage_taken_multiplier *= (1.0 + self.damage_increase)

        if hasattr(target, 'visual_effects'):
            target.visual_effects.add('vulnerable')

    def on_remove(self, target: Any):
        if hasattr(target, 'damage_taken_multiplier'):
            target.damage_taken_multiplier /= (1.0 + self.damage_increase)

        if hasattr(target, 'visual_effects'):
            target.visual_effects.remove('vulnerable')

    def _apply_periodic_effect(self, dt: float, target: Any):
        """No periodic effect"""
        pass


# ============================================================================
# STATUS EFFECT FACTORY
# ============================================================================

STATUS_EFFECT_CLASSES = {
    'burn': BurnEffect,
    'bleed': BleedEffect,
    'poison': PoisonEffect,
    'poison_status': PoisonEffect,  # Alias
    'freeze': FreezeEffect,
    'slow': SlowEffect,
    'chill': SlowEffect,  # Alias for slow
    'stun': StunEffect,
    'root': RootEffect,
    'regeneration': RegenerationEffect,
    'regen': RegenerationEffect,  # Alias
    'shield': ShieldEffect,
    'barrier': ShieldEffect,  # Alias
    'haste': HasteEffect,
    'quicken': HasteEffect,  # Alias
    'weaken': WeakenEffect,
    'vulnerable': VulnerableEffect,
}


def create_status_effect(status_tag: str, params: Dict[str, Any], source: Any = None) -> Optional[StatusEffect]:
    """
    Factory function to create status effects from tags

    Args:
        status_tag: Tag identifier (e.g., 'burn', 'freeze')
        params: Parameters dict containing duration and effect-specific params
        source: Source entity that applied the effect

    Returns:
        StatusEffect instance or None if unknown tag
    """
    effect_class = STATUS_EFFECT_CLASSES.get(status_tag)

    if not effect_class:
        return None

    # Get duration from params (with defaults)
    duration = params.get(f'{status_tag}_duration', params.get('duration', 5.0))

    return effect_class(duration=duration, params=params, source=source)

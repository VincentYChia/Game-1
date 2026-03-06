"""
Action combat system for Game-1.

Provides phased attacks (windup -> active -> recovery), hitbox collision,
projectiles, dodge rolls, and screen effects. Wraps around the existing
damage pipeline in Combat/combat_manager.py without modifying it.

Set USE_ACTION_COMBAT = False to revert to instant click-to-attack.
"""

# Master toggle: set to False to disable all action combat systems
USE_ACTION_COMBAT = True

from combat.combat_event import CombatEvent, HitEvent
from combat.attack_state_machine import AttackPhase, AttackDefinition, AttackStateMachine
from combat.hitbox_system import HitboxDefinition, ActiveHitbox, Hurtbox, HitboxSystem
from combat.projectile_system import ProjectileDefinition, Projectile, ProjectileSystem
from combat.player_actions import PlayerActionSystem, InputBuffer, FACING_TO_ANGLE
from combat.screen_effects import ScreenEffects
from combat.combat_data_loader import CombatDataLoader, get_combat_data_loader

__all__ = [
    'USE_ACTION_COMBAT',
    'CombatEvent', 'HitEvent',
    'AttackPhase', 'AttackDefinition', 'AttackStateMachine',
    'HitboxDefinition', 'ActiveHitbox', 'Hurtbox', 'HitboxSystem',
    'ProjectileDefinition', 'Projectile', 'ProjectileSystem',
    'PlayerActionSystem', 'InputBuffer', 'FACING_TO_ANGLE',
    'ScreenEffects',
    'CombatDataLoader', 'get_combat_data_loader',
]

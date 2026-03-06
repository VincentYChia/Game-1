"""
Combat system for Game-1.

Includes the original combat manager and enemy systems, plus the action combat
overlay: phased attacks (windup -> active -> recovery), hitbox collision,
projectiles, dodge rolls, and screen effects.

Set USE_ACTION_COMBAT = False to revert to instant click-to-attack.
"""

# --- Original combat system ---
from .enemy import Enemy, EnemyDefinition, EnemyDatabase, AIState
from .combat_manager import CombatManager, CombatConfig

# --- Action combat overlay ---
# Master toggle: set to False to disable all action combat systems
USE_ACTION_COMBAT = True

from .combat_event import CombatEvent, HitEvent
from .attack_state_machine import AttackPhase, AttackDefinition, AttackStateMachine
from .hitbox_system import HitboxDefinition, ActiveHitbox, Hurtbox, HitboxSystem
from .projectile_system import ProjectileDefinition, Projectile, ProjectileSystem
from .player_actions import PlayerActionSystem, InputBuffer, FACING_TO_ANGLE
from .screen_effects import ScreenEffects
from .combat_data_loader import CombatDataLoader, get_combat_data_loader

__all__ = [
    # Original
    'Enemy', 'EnemyDefinition', 'EnemyDatabase', 'AIState',
    'CombatManager', 'CombatConfig',
    # Action combat
    'USE_ACTION_COMBAT',
    'CombatEvent', 'HitEvent',
    'AttackPhase', 'AttackDefinition', 'AttackStateMachine',
    'HitboxDefinition', 'ActiveHitbox', 'Hurtbox', 'HitboxSystem',
    'ProjectileDefinition', 'Projectile', 'ProjectileSystem',
    'PlayerActionSystem', 'InputBuffer', 'FACING_TO_ANGLE',
    'ScreenEffects',
    'CombatDataLoader', 'get_combat_data_loader',
]

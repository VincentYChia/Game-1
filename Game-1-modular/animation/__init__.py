"""
Animation system for Game-1 combat visuals.

Pure visual layer — no knowledge of damage, health, or game logic.
Provides frame-based animation playback and procedural effect generation.
"""
from animation.animation_data import AnimationFrame, AnimationDefinition
from animation.sprite_animation import SpriteAnimation
from animation.animation_manager import AnimationManager, get_animation_manager
from animation.procedural import ProceduralAnimations
from animation.combat_particles import CombatParticleSystem, CombatParticle

__all__ = [
    'AnimationFrame', 'AnimationDefinition',
    'SpriteAnimation',
    'AnimationManager', 'get_animation_manager',
    'ProceduralAnimations',
    'CombatParticleSystem', 'CombatParticle',
]

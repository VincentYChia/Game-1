"""
Animation manager singleton.

Global registry mapping entity_id -> active SpriteAnimation.
Follows the project's module-level singleton pattern (like get_effect_executor()).
"""

from typing import Dict, Optional, Callable, List

from animation.animation_data import AnimationDefinition, AnimationFrame
from animation.sprite_animation import SpriteAnimation


class AnimationManager:
    """Singleton registry for all active animations and animation definitions."""

    _instance = None

    def __init__(self):
        self._animations: Dict[str, SpriteAnimation] = {}
        self._definitions: Dict[str, AnimationDefinition] = {}

    @classmethod
    def get_instance(cls) -> 'AnimationManager':
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        """Reset singleton (for testing)."""
        cls._instance = None

    # --- Definition management ---

    def register_definition(self, definition: AnimationDefinition) -> None:
        """Register a reusable animation definition by ID."""
        self._definitions[definition.animation_id] = definition

    def get_definition(self, animation_id: str) -> Optional[AnimationDefinition]:
        """Retrieve a registered animation definition."""
        return self._definitions.get(animation_id)

    def has_definition(self, animation_id: str) -> bool:
        return animation_id in self._definitions

    # --- Active animation management ---

    def play(self, entity_id: str, animation_id: str,
             on_complete: Optional[Callable] = None) -> bool:
        """Start playing an animation on an entity.

        Returns False if the animation_id is not registered.
        """
        defn = self._definitions.get(animation_id)
        if defn is None:
            return False
        self._animations[entity_id] = SpriteAnimation(defn, on_complete)
        return True

    def play_definition(self, entity_id: str, definition: AnimationDefinition,
                        on_complete: Optional[Callable] = None) -> None:
        """Start playing a directly-provided animation definition (not from registry)."""
        self._animations[entity_id] = SpriteAnimation(definition, on_complete)

    def stop(self, entity_id: str) -> None:
        """Stop and remove animation for an entity."""
        self._animations.pop(entity_id, None)

    def is_animating(self, entity_id: str) -> bool:
        """Check if an entity has an active animation."""
        anim = self._animations.get(entity_id)
        return anim is not None and not anim.finished

    def get_current_frame(self, entity_id: str) -> Optional[AnimationFrame]:
        """Get the current frame for an entity, or None if not animating."""
        anim = self._animations.get(entity_id)
        if anim and not anim.finished:
            return anim.get_current_frame()
        return None

    def get_animation(self, entity_id: str) -> Optional[SpriteAnimation]:
        """Get the active SpriteAnimation for an entity."""
        return self._animations.get(entity_id)

    # --- Batch operations ---

    def update_all(self, dt_ms: float) -> None:
        """Advance all active animations and clean up finished ones."""
        dead = []
        for entity_id, anim in self._animations.items():
            anim.update(dt_ms)
            if anim.finished:
                dead.append(entity_id)
        for eid in dead:
            del self._animations[eid]

    def clear_all(self) -> None:
        """Remove all active animations."""
        self._animations.clear()

    @property
    def active_count(self) -> int:
        return len(self._animations)

    @property
    def definition_count(self) -> int:
        return len(self._definitions)


# Module-level singleton accessor (matches project pattern)
_manager = None


def get_animation_manager() -> AnimationManager:
    """Get global animation manager instance."""
    global _manager
    if _manager is None:
        _manager = AnimationManager.get_instance()
    return _manager

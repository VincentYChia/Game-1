"""
Status Effect Manager
Manages active status effects on entities
"""

from typing import List, Dict, Any, Optional
from entities.status_effect import StatusEffect, create_status_effect
from core.tag_debug import get_tag_debugger


# Mutually exclusive status pairs
MUTUAL_EXCLUSIONS = [
    ('burn', 'freeze'),  # Fire and ice cancel each other
    ('stun', 'freeze'),  # Can't be both stunned and frozen (freeze takes priority)
]


# Stacking behavior types
class StackingBehavior:
    NONE = "none"           # New application replaces old (duration refreshes)
    ADDITIVE = "additive"   # Stacks add together (up to max_stacks)
    REFRESH = "refresh"     # Duration refreshes, stacks don't add


# Default stacking behaviors for each status
STACKING_RULES = {
    # DoT effects - stack additively
    'burn': StackingBehavior.ADDITIVE,
    'bleed': StackingBehavior.ADDITIVE,
    'poison': StackingBehavior.ADDITIVE,
    'poison_status': StackingBehavior.ADDITIVE,

    # CC effects - refresh duration, don't stack
    'freeze': StackingBehavior.REFRESH,
    'stun': StackingBehavior.REFRESH,
    'root': StackingBehavior.REFRESH,
    'slow': StackingBehavior.REFRESH,
    'chill': StackingBehavior.REFRESH,

    # Buffs - usually refresh
    'regeneration': StackingBehavior.ADDITIVE,
    'regen': StackingBehavior.ADDITIVE,
    'shield': StackingBehavior.ADDITIVE,  # Shield amounts add
    'barrier': StackingBehavior.ADDITIVE,
    'haste': StackingBehavior.REFRESH,
    'quicken': StackingBehavior.REFRESH,

    # Debuffs - stack additively
    'weaken': StackingBehavior.ADDITIVE,
    'vulnerable': StackingBehavior.ADDITIVE,
}


class StatusEffectManager:
    """
    Manages active status effects on an entity

    Handles:
    - Applying new status effects
    - Updating active effects
    - Removing expired effects
    - Stacking rules
    - Mutual exclusions
    - Immunity checks
    """

    def __init__(self, entity: Any):
        self.entity = entity
        self.active_effects: List[StatusEffect] = []
        self.debugger = get_tag_debugger()

    def apply_status(self, status_tag: str, params: Dict[str, Any], source: Any = None) -> bool:
        """
        Apply a status effect to the entity

        Args:
            status_tag: Status tag identifier (e.g., 'burn', 'freeze')
            params: Parameters dict containing duration and effect-specific params
            source: Source entity that applied this status

        Returns:
            True if status was applied, False if blocked (immunity, etc.)
        """
        # Check for existing effect of the same type
        existing = self._find_effect(status_tag)

        # Handle stacking
        if existing:
            stacking_behavior = STACKING_RULES.get(status_tag, StackingBehavior.NONE)

            if stacking_behavior == StackingBehavior.ADDITIVE:
                # Add stacks
                existing.add_stack(1)
                existing.refresh_duration()
                self.debugger.debug(
                    f"Status {status_tag} stacked on {getattr(self.entity, 'name', 'Unknown')} "
                    f"(now {existing.stacks} stacks)"
                )
                return True

            elif stacking_behavior == StackingBehavior.REFRESH:
                # Refresh duration
                existing.refresh_duration()
                self.debugger.debug(
                    f"Status {status_tag} refreshed on {getattr(self.entity, 'name', 'Unknown')}"
                )
                return True

            else:  # NONE - replace
                self._remove_effect(existing)
                # Continue to apply new effect below

        # Check mutual exclusions
        for status_a, status_b in MUTUAL_EXCLUSIONS:
            if status_tag == status_a:
                conflicting = self._find_effect(status_b)
                if conflicting:
                    self._remove_effect(conflicting)
                    self.debugger.info(
                        f"{status_tag} removed conflicting {status_b} from "
                        f"{getattr(self.entity, 'name', 'Unknown')}"
                    )
            elif status_tag == status_b:
                conflicting = self._find_effect(status_a)
                if conflicting:
                    self._remove_effect(conflicting)
                    self.debugger.info(
                        f"{status_tag} removed conflicting {status_a} from "
                        f"{getattr(self.entity, 'name', 'Unknown')}"
                    )

        # Apply resistance to duration if target has get_effect_resistance method
        modified_params = params.copy()
        if hasattr(self.entity, 'get_effect_resistance'):
            resistance_multiplier = self.entity.get_effect_resistance(status_tag)

            # Apply resistance to duration (reduce duration based on resistance)
            if 'duration' in modified_params:
                original_duration = modified_params['duration']
                modified_params['duration'] = original_duration * resistance_multiplier

            # Also check for effect-specific duration key (e.g., burn_duration)
            duration_key = f'{status_tag}_duration'
            if duration_key in modified_params:
                original_duration = modified_params[duration_key]
                modified_params[duration_key] = original_duration * resistance_multiplier

        # Create new effect
        effect = create_status_effect(status_tag, modified_params, source)

        if not effect:
            self.debugger.warning(f"Unknown status effect: {status_tag}")
            return False

        # Apply effect
        effect.on_apply(self.entity)
        self.active_effects.append(effect)

        self.debugger.log_status_application(
            self.entity,
            status_tag,
            params
        )

        return True

    def remove_status(self, status_tag: str) -> bool:
        """
        Remove a specific status effect by tag

        Args:
            status_tag: Status tag to remove

        Returns:
            True if status was removed, False if not found
        """
        effect = self._find_effect(status_tag)
        if effect:
            self._remove_effect(effect)
            return True
        return False

    def has_status(self, status_tag: str) -> bool:
        """Check if entity has a specific status effect"""
        return self._find_effect(status_tag) is not None

    def get_status(self, status_tag: str) -> Optional[StatusEffect]:
        """Get a specific status effect if active"""
        return self._find_effect(status_tag)

    def update(self, dt: float):
        """
        Update all active status effects

        Args:
            dt: Delta time in seconds
        """
        # Update effects and collect expired ones
        expired = []

        for effect in self.active_effects:
            if not effect.update(dt, self.entity):
                expired.append(effect)

        # Remove expired effects
        for effect in expired:
            self._remove_effect(effect)

    def clear_all(self):
        """Remove all status effects (useful for death, dispel, etc.)"""
        for effect in list(self.active_effects):
            self._remove_effect(effect)

    def clear_debuffs(self):
        """Remove all negative status effects (useful for cleanse abilities)"""
        debuff_tags = [
            'burn', 'bleed', 'poison', 'poison_status',
            'freeze', 'stun', 'root', 'slow', 'chill',
            'weaken', 'vulnerable'
        ]

        for effect in list(self.active_effects):
            if effect.status_id in debuff_tags:
                self._remove_effect(effect)

    def get_all_active_effects(self) -> List[StatusEffect]:
        """Get list of all active effects (for UI display)"""
        return list(self.active_effects)

    def is_crowd_controlled(self) -> bool:
        """Check if entity is under any crowd control effect"""
        cc_tags = ['freeze', 'stun', 'root', 'slow', 'chill']
        return any(self._find_effect(tag) for tag in cc_tags)

    def is_immobilized(self) -> bool:
        """Check if entity cannot move"""
        return any(self._find_effect(tag) for tag in ['freeze', 'stun', 'root'])

    def is_silenced(self) -> bool:
        """Check if entity cannot use abilities"""
        return any(self._find_effect(tag) for tag in ['stun', 'silence'])

    # Private helper methods

    def _find_effect(self, status_tag: str) -> Optional[StatusEffect]:
        """Find an active effect by status tag"""
        for effect in self.active_effects:
            if effect.status_id == status_tag:
                return effect
        return None

    def _remove_effect(self, effect: StatusEffect):
        """Remove an effect and call its on_remove handler"""
        if effect in self.active_effects:
            effect.on_remove(self.entity)
            self.active_effects.remove(effect)
            self.debugger.debug(
                f"Status {effect.status_id} removed from {getattr(self.entity, 'name', 'Unknown')}"
            )


# ============================================================================
# INTEGRATION HELPER
# ============================================================================

def add_status_manager_to_entity(entity: Any):
    """
    Helper function to add status manager to an entity

    Args:
        entity: Entity to add status manager to (Character, Enemy, etc.)
    """
    if not hasattr(entity, 'status_manager'):
        entity.status_manager = StatusEffectManager(entity)

    # Add flags for status effect checks (if not present)
    if not hasattr(entity, 'is_frozen'):
        entity.is_frozen = False
    if not hasattr(entity, 'is_stunned'):
        entity.is_stunned = False
    if not hasattr(entity, 'is_rooted'):
        entity.is_rooted = False

    # Add visual effects set (if not present)
    if not hasattr(entity, 'visual_effects'):
        entity.visual_effects = set()

    # Add damage/shield multipliers (if not present)
    if not hasattr(entity, 'damage_multiplier'):
        entity.damage_multiplier = 1.0
    if not hasattr(entity, 'damage_taken_multiplier'):
        entity.damage_taken_multiplier = 1.0
    if not hasattr(entity, 'shield_health'):
        entity.shield_health = 0.0

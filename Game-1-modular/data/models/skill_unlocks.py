"""Skill unlock data models"""

from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional

from data.models.unlock_conditions import UnlockRequirements


@dataclass
class UnlockCost:
    """Cost to unlock a skill after conditions are met."""
    gold: int = 0
    materials: List[Dict[str, Any]] = field(default_factory=list)  # [{materialId, quantity}]
    skill_points: int = 0

    def can_afford(self, character) -> tuple[bool, str]:
        """
        Check if character can afford the unlock cost.

        Args:
            character: Character to check

        Returns:
            (can_afford, reason): True if affordable, reason if not
        """
        # Check gold
        if hasattr(character, 'gold') and character.gold < self.gold:
            return False, f"Need {self.gold} gold"

        # Check materials
        for mat_req in self.materials:
            mat_id = mat_req.get('materialId')
            qty = mat_req.get('quantity', 1)
            if not character.inventory.has_item(mat_id, qty):
                return False, f"Need {qty}x {mat_id}"

        # Check skill points (if system uses them)
        if self.skill_points > 0:
            if hasattr(character, 'skill_points') and character.skill_points < self.skill_points:
                return False, f"Need {self.skill_points} skill points"

        return True, "OK"

    def pay(self, character) -> bool:
        """
        Pay the unlock cost.

        Args:
            character: Character paying the cost

        Returns:
            True if successfully paid
        """
        can_afford, reason = self.can_afford(character)
        if not can_afford:
            return False

        # Deduct gold
        if hasattr(character, 'gold'):
            character.gold -= self.gold

        # Remove materials
        for mat_req in self.materials:
            mat_id = mat_req.get('materialId')
            qty = mat_req.get('quantity', 1)
            character.inventory.remove_item(mat_id, qty)

        # Deduct skill points
        if self.skill_points > 0 and hasattr(character, 'skill_points'):
            character.skill_points -= self.skill_points

        return True


@dataclass
class UnlockTrigger:
    """Defines when/how a skill unlock actually happens."""
    type: str  # level_up, quest_complete, title_earned, activity_threshold, etc.
    trigger_value: Any  # Context-specific (questId, level, count, etc.)
    message: str  # Notification shown to player


@dataclass
class SkillUnlock:
    """
    Defines how a skill becomes available to the player.

    Uses tag-driven UnlockRequirements for conditions.
    """
    unlock_id: str
    skill_id: str
    unlock_method: str  # automatic, quest_reward, milestone_unlock, title_unlock, etc.

    requirements: UnlockRequirements
    trigger: UnlockTrigger
    cost: UnlockCost

    # Metadata
    narrative: str = ""
    category: str = ""

    def __post_init__(self):
        """Validate unlock definition."""
        if not self.unlock_id:
            raise ValueError("unlock_id is required")
        if not self.skill_id:
            raise ValueError("skill_id is required")
        if not self.unlock_method:
            raise ValueError("unlock_method is required")

    def check_conditions(self, character) -> bool:
        """
        Check if unlock conditions are satisfied.

        Args:
            character: Character to check

        Returns:
            True if all conditions met
        """
        return self.requirements.evaluate(character)

    def check_cost(self, character) -> tuple[bool, str]:
        """
        Check if character can afford unlock cost.

        Args:
            character: Character to check

        Returns:
            (can_afford, reason)
        """
        return self.cost.can_afford(character)

    def can_unlock(self, character) -> tuple[bool, str]:
        """
        Check if skill can be unlocked (conditions + cost).

        Args:
            character: Character to check

        Returns:
            (can_unlock, reason)
        """
        if not self.check_conditions(character):
            return False, "Conditions not met"

        can_afford, reason = self.check_cost(character)
        if not can_afford:
            return False, reason

        return True, "OK"

    def unlock(self, character) -> tuple[bool, str]:
        """
        Unlock the skill for the character.

        Args:
            character: Character unlocking the skill

        Returns:
            (success, message)
        """
        can_unlock, reason = self.can_unlock(character)
        if not can_unlock:
            return False, reason

        # Pay cost
        if not self.cost.pay(character):
            return False, "Failed to pay cost"

        # Add skill to character's skill manager
        if hasattr(character, 'skills'):
            # Mark skill as unlocked in skill manager
            # The skill manager will handle actually adding the skill
            success = character.skills.unlock_skill(self.skill_id)
            if success:
                return True, self.trigger.message
            else:
                return False, f"Failed to unlock skill {self.skill_id}"

        return False, "Character has no skill manager"

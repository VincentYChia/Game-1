"""Skill unlock system for managing skill availability"""

from typing import List, Optional, Set, TYPE_CHECKING

from data.models.skill_unlocks import SkillUnlock
from data.databases import SkillUnlockDatabase

if TYPE_CHECKING:
    from entities.character import Character


class SkillUnlockSystem:
    """
    Manages skill unlock progression for a character.

    Tracks:
    - Which skills have been unlocked
    - Which skills are currently unlockable (conditions met, awaiting payment)
    - Provides trigger-based checking for new unlocks
    """

    def __init__(self):
        self.unlocked_skills: Set[str] = set()  # skill_ids that have been unlocked
        self.pending_unlocks: Set[str] = set()  # unlock_ids awaiting cost payment
        self.unlock_db = SkillUnlockDatabase.get_instance()

    def is_skill_unlocked(self, skill_id: str) -> bool:
        """Check if a skill has been unlocked."""
        return skill_id in self.unlocked_skills

    def is_unlock_pending(self, unlock_id: str) -> bool:
        """Check if an unlock is pending cost payment."""
        return unlock_id in self.pending_unlocks

    def check_for_unlocks(self, character: 'Character', trigger_type: Optional[str] = None,
                          trigger_value: any = None) -> List[SkillUnlock]:
        """
        Check for new skill unlocks based on character state.

        Args:
            character: Character instance with full state access
            trigger_type: Optional trigger filter (level_up, title_earned, etc.)
            trigger_value: Optional trigger value (level, title_id, etc.)

        Returns:
            List of SkillUnlock definitions that became available
        """
        newly_unlockable = []

        for unlock in self.unlock_db.get_all_unlocks():
            # Skip if already unlocked
            if unlock.skill_id in self.unlocked_skills:
                continue

            # Skip if already pending
            if unlock.unlock_id in self.pending_unlocks:
                continue

            # If trigger filter specified, check if this unlock matches
            if trigger_type and unlock.trigger.type != trigger_type:
                continue

            # If trigger value specified, check if it matches
            if trigger_value is not None and unlock.trigger.trigger_value != trigger_value:
                continue

            # Check if conditions are met
            if not unlock.check_conditions(character):
                continue

            # Conditions met! Check if there's a cost
            can_afford, _ = unlock.check_cost(character)

            if unlock.cost.gold == 0 and len(unlock.cost.materials) == 0 and unlock.cost.skill_points == 0:
                # No cost - unlock immediately
                success, message = self._unlock_skill(character, unlock)
                if success:
                    newly_unlockable.append(unlock)
            elif can_afford:
                # Has cost but can afford - mark as pending for player confirmation
                self.pending_unlocks.add(unlock.unlock_id)
                newly_unlockable.append(unlock)
            else:
                # Has cost but can't afford yet - conditions met but not unlockable
                pass

        return newly_unlockable

    def unlock_skill(self, character: 'Character', unlock_id: str) -> tuple[bool, str]:
        """
        Unlock a skill by unlock_id (e.g., from player UI interaction).

        Args:
            character: Character unlocking the skill
            unlock_id: ID of the unlock to perform

        Returns:
            (success, message)
        """
        unlock = self.unlock_db.get_unlock(unlock_id)
        if not unlock:
            return False, f"Unknown unlock: {unlock_id}"

        # Check if already unlocked
        if unlock.skill_id in self.unlocked_skills:
            return False, "Skill already unlocked"

        # Attempt unlock
        success, message = self._unlock_skill(character, unlock)
        if success:
            # Remove from pending if it was there
            self.pending_unlocks.discard(unlock_id)

        return success, message

    def _unlock_skill(self, character: 'Character', unlock: SkillUnlock) -> tuple[bool, str]:
        """
        Internal method to unlock a skill.

        Args:
            character: Character unlocking the skill
            unlock: SkillUnlock definition

        Returns:
            (success, message)
        """
        # Final check: can unlock?
        can_unlock, reason = unlock.can_unlock(character)
        if not can_unlock:
            return False, reason

        # Pay cost and unlock
        success, message = unlock.unlock(character)
        if success:
            self.unlocked_skills.add(unlock.skill_id)
            return True, message

        return False, message

    def get_pending_unlocks(self) -> List[str]:
        """Get list of unlock_ids that are pending."""
        return list(self.pending_unlocks)

    def check_level_up_unlocks(self, character: 'Character', new_level: int) -> List[SkillUnlock]:
        """
        Check for unlocks triggered by level up.

        Args:
            character: Character that leveled up
            new_level: New level reached

        Returns:
            List of newly unlockable skills
        """
        return self.check_for_unlocks(character, trigger_type='level_up', trigger_value=new_level)

    def check_title_earned_unlocks(self, character: 'Character', title_id: str) -> List[SkillUnlock]:
        """
        Check for unlocks triggered by earning a title.

        Args:
            character: Character that earned the title
            title_id: ID of the title earned

        Returns:
            List of newly unlockable skills
        """
        return self.check_for_unlocks(character, trigger_type='title_earned', trigger_value=title_id)

    def check_quest_complete_unlocks(self, character: 'Character', quest_id: str) -> List[SkillUnlock]:
        """
        Check for unlocks triggered by quest completion.

        Args:
            character: Character that completed the quest
            quest_id: ID of the completed quest

        Returns:
            List of newly unlockable skills
        """
        return self.check_for_unlocks(character, trigger_type='quest_complete', trigger_value=quest_id)

    def check_activity_threshold_unlocks(self, character: 'Character') -> List[SkillUnlock]:
        """
        Check for unlocks triggered by activity thresholds.

        This is called periodically (e.g., after crafting, combat, gathering)
        to check milestone-based unlocks.

        Args:
            character: Character to check

        Returns:
            List of newly unlockable skills
        """
        return self.check_for_unlocks(character, trigger_type='activity_threshold')

    def get_unlocked_count(self) -> int:
        """Get number of skills unlocked."""
        return len(self.unlocked_skills)

    def reset_debug(self):
        """Reset unlock state (for debug/testing)."""
        self.unlocked_skills.clear()
        self.pending_unlocks.clear()

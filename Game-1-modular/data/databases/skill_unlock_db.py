"""Skill unlock database singleton"""

import json
from typing import Dict, Optional, List

from data.models.skill_unlocks import SkillUnlock, UnlockCost, UnlockTrigger
from data.models.unlock_conditions import ConditionFactory, UnlockRequirements


class SkillUnlockDatabase:
    """
    Singleton database for skill unlock definitions.

    Loads from progression/skill-unlocks.JSON and provides access to unlock data.
    """
    _instance = None

    def __init__(self):
        self.unlocks: Dict[str, SkillUnlock] = {}
        self.unlocks_by_skill: Dict[str, SkillUnlock] = {}  # skill_id -> unlock
        self.loaded = False

    @classmethod
    def get_instance(cls) -> 'SkillUnlockDatabase':
        """Get singleton instance."""
        if cls._instance is None:
            cls._instance = SkillUnlockDatabase()
        return cls._instance

    def load_from_file(self, filepath: str):
        """
        Load skill unlock definitions from JSON file.

        Args:
            filepath: Path to skill-unlocks.JSON
        """
        print(f"Loading skill unlocks from {filepath}...")

        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)

            unlocks_data = data.get('skillUnlocks', [])
            for unlock_data in unlocks_data:
                unlock = self._parse_skill_unlock(unlock_data)
                if unlock:
                    self.unlocks[unlock.unlock_id] = unlock
                    self.unlocks_by_skill[unlock.skill_id] = unlock

            self.loaded = True
            print(f"✓ Loaded {len(self.unlocks)} skill unlocks")

        except FileNotFoundError:
            print(f"⚠ Warning: {filepath} not found")
        except json.JSONDecodeError as e:
            print(f"⚠ Warning: Error parsing {filepath}: {e}")
        except Exception as e:
            print(f"⚠ Warning: Error loading skill unlocks: {e}")

    def _parse_skill_unlock(self, data: Dict) -> Optional[SkillUnlock]:
        """
        Parse skill unlock definition from JSON.

        Args:
            data: JSON data for one skill unlock

        Returns:
            SkillUnlock instance or None if parsing fails
        """
        try:
            unlock_id = data.get('unlockId')
            skill_id = data.get('skillId')
            unlock_method = data.get('unlockMethod')

            if not unlock_id or not skill_id or not unlock_method:
                print(f"⚠ Warning: Incomplete unlock definition: {data}")
                return None

            # Parse conditions using ConditionFactory
            conditions_data = data.get('conditions', [])
            requirements = ConditionFactory.create_requirements_from_json({'conditions': conditions_data})

            # Parse trigger
            trigger_data = data.get('unlockTrigger', {})
            trigger = UnlockTrigger(
                type=trigger_data.get('type', 'unknown'),
                trigger_value=trigger_data.get('triggerValue'),
                message=trigger_data.get('message', f"Unlocked {skill_id}!")
            )

            # Parse cost
            cost_data = data.get('cost', {})
            cost = UnlockCost(
                gold=cost_data.get('gold', 0),
                materials=cost_data.get('materials', []),
                skill_points=cost_data.get('skillPoints', 0)
            )

            # Parse metadata
            metadata = data.get('metadata', {})
            narrative = metadata.get('narrative', '')
            category = metadata.get('category', '')

            return SkillUnlock(
                unlock_id=unlock_id,
                skill_id=skill_id,
                unlock_method=unlock_method,
                requirements=requirements,
                trigger=trigger,
                cost=cost,
                narrative=narrative,
                category=category
            )

        except Exception as e:
            print(f"⚠ Warning: Error parsing skill unlock {data.get('unlockId', 'unknown')}: {e}")
            return None

    def get_unlock(self, unlock_id: str) -> Optional[SkillUnlock]:
        """Get skill unlock by unlock_id."""
        return self.unlocks.get(unlock_id)

    def get_unlock_for_skill(self, skill_id: str) -> Optional[SkillUnlock]:
        """Get skill unlock definition for a specific skill."""
        return self.unlocks_by_skill.get(skill_id)

    def get_unlocks_by_method(self, unlock_method: str) -> List[SkillUnlock]:
        """Get all unlocks using a specific unlock method."""
        return [unlock for unlock in self.unlocks.values() if unlock.unlock_method == unlock_method]

    def get_unlocks_by_trigger_type(self, trigger_type: str) -> List[SkillUnlock]:
        """Get all unlocks with a specific trigger type."""
        return [unlock for unlock in self.unlocks.values() if unlock.trigger.type == trigger_type]

    def get_all_unlocks(self) -> List[SkillUnlock]:
        """Get all skill unlock definitions."""
        return list(self.unlocks.values())

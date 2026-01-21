"""
Tag-Driven Unlock Condition System
Modular, composable conditions for titles, skills, and other unlockables.
Designed to be LLM-extensible via JSON.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional, TYPE_CHECKING
from abc import ABC, abstractmethod

if TYPE_CHECKING:
    from entities.character import Character


class UnlockCondition(ABC):
    """
    Base class for unlock conditions.

    Tag-driven design: Each condition has a type tag and can be composed with others.
    LLMs can add new condition types by extending the JSON schema.
    """

    @abstractmethod
    def evaluate(self, character: 'Character') -> bool:
        """
        Check if the character meets this condition.

        Args:
            character: Character to evaluate

        Returns:
            True if condition is met, False otherwise
        """
        pass

    @abstractmethod
    def get_description(self) -> str:
        """Get human-readable description of this condition."""
        pass

    @abstractmethod
    def to_dict(self) -> Dict[str, Any]:
        """Serialize condition to dictionary (for saving/debugging)."""
        pass


class LevelCondition(UnlockCondition):
    """Requires character level >= minimum."""

    def __init__(self, min_level: int):
        self.min_level = min_level

    def evaluate(self, character: 'Character') -> bool:
        return character.leveling.level >= self.min_level

    def get_description(self) -> str:
        return f"Level {self.min_level}+"

    def to_dict(self) -> Dict[str, Any]:
        return {"type": "level", "min_level": self.min_level}


class StatCondition(UnlockCondition):
    """Requires specific stat values (e.g., strength >= 10)."""

    def __init__(self, stat_requirements: Dict[str, int]):
        """
        Args:
            stat_requirements: Dict like {"strength": 10, "luck": 5}
        """
        self.stat_requirements = stat_requirements

    def evaluate(self, character: 'Character') -> bool:
        stat_mapping = {
            'strength': character.stats.strength,
            'defense': character.stats.defense,
            'vitality': character.stats.vitality,
            'luck': character.stats.luck,
            'agility': character.stats.agility,
            'intelligence': character.stats.intelligence
        }

        for stat_name, required_value in self.stat_requirements.items():
            current_value = stat_mapping.get(stat_name.lower(), 0)
            if current_value < required_value:
                return False

        return True

    def get_description(self) -> str:
        parts = [f"{name.title()} {val}+" for name, val in self.stat_requirements.items()]
        return ", ".join(parts)

    def to_dict(self) -> Dict[str, Any]:
        return {"type": "stat", "requirements": self.stat_requirements}


class ActivityCondition(UnlockCondition):
    """Requires activity count (e.g., 100 ores mined)."""

    def __init__(self, activity_type: str, min_count: int):
        """
        Args:
            activity_type: Activity name (mining, forestry, smithing, etc.)
            min_count: Minimum times this activity must be performed
        """
        self.activity_type = activity_type
        self.min_count = min_count

    def evaluate(self, character: 'Character') -> bool:
        current_count = character.activities.get_count(self.activity_type)
        return current_count >= self.min_count

    def get_description(self) -> str:
        return f"{self.activity_type.title()}: {self.min_count}+"

    def to_dict(self) -> Dict[str, Any]:
        return {"type": "activity", "activity": self.activity_type, "min_count": self.min_count}


class StatTrackerCondition(UnlockCondition):
    """
    Requires specific stat tracker values (e.g., iron_ore_mined >= 50).

    This is the NEW condition type that leverages our comprehensive stat tracking.
    Supports nested lookups like:
    - gathering_totals.total_ores_mined >= 1000
    - combat_kills.dragon_boss_defeated >= 1
    - crafting_by_discipline.smithing.perfect_crafts >= 100
    """

    def __init__(self, stat_path: str, min_value: float):
        """
        Args:
            stat_path: Dot-notation path to stat (e.g., "gathering_totals.fire_resources_gathered")
            min_value: Minimum value required
        """
        self.stat_path = stat_path
        self.min_value = min_value

    def evaluate(self, character: 'Character') -> bool:
        if not hasattr(character, 'stat_tracker'):
            return False

        # Navigate nested path
        parts = self.stat_path.split('.')
        current = character.stat_tracker

        try:
            for part in parts:
                if isinstance(current, dict):
                    current = current[part]
                elif hasattr(current, part):
                    current = getattr(current, part)
                else:
                    # Try per-entity tracking
                    if part == 'resources_gathered' and hasattr(current, 'resources_gathered'):
                        # For specific resources like "iron_ore_node"
                        # Path would be: resources_gathered.iron_ore_node.count
                        continue
                    return False

            # Handle StatEntry objects
            if hasattr(current, 'count'):
                current = current.count
            elif hasattr(current, 'total_value'):
                current = current.total_value

            return float(current) >= self.min_value
        except (KeyError, AttributeError, TypeError):
            return False

    def get_description(self) -> str:
        # Make human-readable
        readable = self.stat_path.replace('_', ' ').replace('.', ' → ').title()
        return f"{readable}: {int(self.min_value)}+"

    def to_dict(self) -> Dict[str, Any]:
        return {"type": "stat_tracker", "stat_path": self.stat_path, "min_value": self.min_value}


class TitleCondition(UnlockCondition):
    """Requires specific titles to be earned."""

    def __init__(self, required_titles: List[str]):
        """
        Args:
            required_titles: List of title_ids that must be earned
        """
        self.required_titles = required_titles

    def evaluate(self, character: 'Character') -> bool:
        for title_id in self.required_titles:
            if not character.titles.has_title(title_id):
                return False
        return True

    def get_description(self) -> str:
        if len(self.required_titles) == 1:
            return f"Title: {self.required_titles[0]}"
        return f"Titles: {', '.join(self.required_titles)}"

    def to_dict(self) -> Dict[str, Any]:
        return {"type": "title", "required_titles": self.required_titles}


class SkillCondition(UnlockCondition):
    """Requires specific skills to be learned."""

    def __init__(self, required_skills: List[str]):
        """
        Args:
            required_skills: List of skill_ids that must be known
        """
        self.required_skills = required_skills

    def evaluate(self, character: 'Character') -> bool:
        for skill_id in self.required_skills:
            if skill_id not in character.skills.known_skills:
                return False
        return True

    def get_description(self) -> str:
        if len(self.required_skills) == 1:
            return f"Skill: {self.required_skills[0]}"
        return f"Skills: {', '.join(self.required_skills)}"

    def to_dict(self) -> Dict[str, Any]:
        return {"type": "skill", "required_skills": self.required_skills}


class QuestCondition(UnlockCondition):
    """Requires specific quests to be completed."""

    def __init__(self, required_quests: List[str]):
        """
        Args:
            required_quests: List of quest_ids that must be completed
        """
        self.required_quests = required_quests

    def evaluate(self, character: 'Character') -> bool:
        for quest_id in self.required_quests:
            if not character.quests.is_quest_completed(quest_id):
                return False
        return True

    def get_description(self) -> str:
        if len(self.required_quests) == 1:
            return f"Quest: {self.required_quests[0]}"
        return f"Quests: {', '.join(self.required_quests)}"

    def to_dict(self) -> Dict[str, Any]:
        return {"type": "quest", "required_quests": self.required_quests}


class ClassCondition(UnlockCondition):
    """Requires specific character class."""

    def __init__(self, required_class: str):
        """
        Args:
            required_class: class_id required
        """
        self.required_class = required_class

    def evaluate(self, character: 'Character') -> bool:
        if not character.class_system.current_class:
            return False
        return character.class_system.current_class.class_id == self.required_class

    def get_description(self) -> str:
        return f"Class: {self.required_class}"

    def to_dict(self) -> Dict[str, Any]:
        return {"type": "class", "required_class": self.required_class}


@dataclass
class UnlockRequirements:
    """
    Composite unlock requirements (AND logic).

    All conditions must be met for the requirements to pass.
    This is the main class used by titles and skills.
    """
    conditions: List[UnlockCondition] = field(default_factory=list)

    def evaluate(self, character: 'Character') -> bool:
        """Check if all conditions are met."""
        return all(condition.evaluate(character) for condition in self.conditions)

    def get_missing_conditions(self, character: 'Character') -> List[UnlockCondition]:
        """Get list of conditions that are NOT yet met."""
        return [condition for condition in self.conditions if not condition.evaluate(character)]

    def get_description(self) -> str:
        """Get human-readable description of all requirements."""
        if not self.conditions:
            return "No requirements"
        return " AND ".join(condition.get_description() for condition in self.conditions)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize all conditions."""
        return {
            "conditions": [condition.to_dict() for condition in self.conditions]
        }


class ConditionFactory:
    """
    Factory for creating UnlockCondition objects from JSON data.

    Tag-driven: Looks at the "type" tag to determine which condition class to create.
    LLMs can extend this by adding new condition types to JSON.
    """

    @staticmethod
    def create_from_json(data: Dict[str, Any]) -> Optional[UnlockCondition]:
        """
        Create a condition from JSON data.

        Args:
            data: Dictionary with "type" tag and parameters

        Returns:
            UnlockCondition instance or None if invalid
        """
        condition_type = data.get("type", "").lower()

        if condition_type == "level":
            return LevelCondition(data.get("min_level", 1))

        elif condition_type == "stat":
            return StatCondition(data.get("requirements", {}))

        elif condition_type == "activity":
            return ActivityCondition(
                data.get("activity", "mining"),
                data.get("min_count", 0)
            )

        elif condition_type == "stat_tracker":
            return StatTrackerCondition(
                data.get("stat_path", ""),
                data.get("min_value", 0)
            )

        elif condition_type == "title":
            return TitleCondition(data.get("required_titles", []))

        elif condition_type == "skill":
            return SkillCondition(data.get("required_skills", []))

        elif condition_type == "quest":
            return QuestCondition(data.get("required_quests", []))

        elif condition_type == "class":
            return ClassCondition(data.get("required_class", ""))

        else:
            print(f"⚠ Unknown condition type: {condition_type}")
            return None

    @staticmethod
    def create_requirements_from_json(json_data: Dict[str, Any]) -> UnlockRequirements:
        """
        Create UnlockRequirements from JSON structure.

        Supports both legacy format (flat requirements) and new format (condition list).

        Args:
            json_data: JSON data from titles or skill-unlocks

        Returns:
            UnlockRequirements with all conditions
        """
        requirements = UnlockRequirements()

        # New format: explicit conditions list
        if "conditions" in json_data and isinstance(json_data["conditions"], list):
            for condition_data in json_data["conditions"]:
                condition = ConditionFactory.create_from_json(condition_data)
                if condition:
                    requirements.conditions.append(condition)

        # Legacy format: parse from top-level fields
        else:
            # Level
            if "characterLevel" in json_data and json_data["characterLevel"] > 0:
                requirements.conditions.append(LevelCondition(json_data["characterLevel"]))

            # Stats
            if "stats" in json_data and json_data["stats"]:
                requirements.conditions.append(StatCondition(json_data["stats"]))

            # Titles
            if "titles" in json_data and json_data["titles"]:
                requirements.conditions.append(TitleCondition(json_data["titles"]))

            # Required titles (alternate key)
            if "requiredTitles" in json_data and json_data["requiredTitles"]:
                requirements.conditions.append(TitleCondition(json_data["requiredTitles"]))

            # Quests
            if "completedQuests" in json_data and json_data["completedQuests"]:
                requirements.conditions.append(QuestCondition(json_data["completedQuests"]))

            # Activity milestones
            if "activityMilestones" in json_data:
                for milestone in json_data["activityMilestones"]:
                    milestone_type = milestone.get("type", "")

                    # Map milestone types to conditions
                    if milestone_type == "craft_count":
                        discipline = milestone.get("discipline", "smithing")
                        count = milestone.get("count", 0)
                        requirements.conditions.append(
                            StatTrackerCondition(
                                f"crafting_by_discipline.{discipline}.total_crafts",
                                count
                            )
                        )

                    elif milestone_type == "kill_count":
                        count = milestone.get("count", 0)
                        requirements.conditions.append(
                            StatTrackerCondition("combat_kills.total_kills", count)
                        )

                    elif milestone_type == "gather_count":
                        count = milestone.get("count", 0)
                        # Total resources across all types
                        requirements.conditions.append(
                            ActivityCondition("mining", count // 2)  # Approximate split
                        )
                        requirements.conditions.append(
                            ActivityCondition("forestry", count // 2)
                        )

            # Activities (legacy title format)
            if "activities" in json_data and json_data["activities"]:
                for activity_key, count in json_data["activities"].items():
                    # Map JSON keys to internal activity types
                    activity_mapping = {
                        'oresMined': 'mining',
                        'treesChopped': 'forestry',
                        'itemsSmithed': 'smithing',
                        'materialsRefined': 'refining',
                        'potionsBrewed': 'alchemy',
                        'itemsEnchanted': 'enchanting',
                        'devicesCreated': 'engineering',
                        'enemiesDefeated': 'combat',
                        'bossesDefeated': 'combat'
                    }

                    activity_type = activity_mapping.get(activity_key, activity_key)
                    requirements.conditions.append(ActivityCondition(activity_type, count))

        return requirements

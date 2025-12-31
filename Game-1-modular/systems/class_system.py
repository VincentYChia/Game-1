"""Class system for managing character class selection and bonuses"""

from typing import Optional, Dict, Callable, List

from data.models import ClassDefinition


class ClassSystem:
    def __init__(self):
        self.current_class: Optional[ClassDefinition] = None
        self._on_class_set_callbacks: List[Callable[[ClassDefinition], None]] = []

    def set_class(self, class_def: ClassDefinition):
        self.current_class = class_def
        # Notify any registered callbacks
        for callback in self._on_class_set_callbacks:
            callback(class_def)

    def register_on_class_set(self, callback: Callable[[ClassDefinition], None]):
        """Register a callback to be called when a class is set."""
        self._on_class_set_callbacks.append(callback)

    def get_bonus(self, bonus_type: str) -> float:
        if not self.current_class:
            return 0.0
        return self.current_class.bonuses.get(bonus_type, 0.0)

    def get_tool_efficiency_bonus(self, tool_type: str) -> float:
        """Get tool efficiency bonus based on class tags.

        Tag-driven bonuses:
        - 'nature' or 'gathering' tags: +10% axe efficiency
        - 'gathering' or 'explorer' tags: +10% pickaxe efficiency
        - 'crafting' or 'smithing' tags: +5% all tool durability (handled elsewhere)
        - 'physical' or 'melee' tags: +5% tool damage
        """
        if not self.current_class or not self.current_class.tags:
            return 0.0

        tags = set(t.lower() for t in self.current_class.tags)
        bonus = 0.0

        if tool_type == 'axe':
            if 'nature' in tags:
                bonus += 0.10  # Rangers excel at forestry
            if 'gathering' in tags:
                bonus += 0.05
        elif tool_type == 'pickaxe':
            if 'gathering' in tags:
                bonus += 0.10  # Scavengers excel at mining
            if 'explorer' in tags:
                bonus += 0.05

        return bonus

    def get_tool_damage_bonus(self) -> float:
        """Get tool damage bonus for combat use based on class tags."""
        if not self.current_class or not self.current_class.tags:
            return 0.0

        tags = set(t.lower() for t in self.current_class.tags)
        bonus = 0.0

        if 'physical' in tags:
            bonus += 0.05
        if 'melee' in tags:
            bonus += 0.05

        return bonus

"""Class system for managing character class selection and bonuses"""

from typing import Optional

from data.models import ClassDefinition


class ClassSystem:
    def __init__(self):
        self.current_class: Optional[ClassDefinition] = None

    def set_class(self, class_def: ClassDefinition):
        self.current_class = class_def

    def get_bonus(self, bonus_type: str) -> float:
        if not self.current_class:
            return 0.0
        return self.current_class.bonuses.get(bonus_type, 0.0)

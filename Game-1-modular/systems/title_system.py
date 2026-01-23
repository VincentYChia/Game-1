"""Title system for managing earned titles and bonuses"""

import random
from typing import List, Optional, TYPE_CHECKING

from data.models import TitleDefinition
from data.databases import TitleDatabase

if TYPE_CHECKING:
    from entities.character import Character


class TitleSystem:
    def __init__(self):
        self.earned_titles: List[TitleDefinition] = []
        self.title_db = TitleDatabase.get_instance()

    def check_for_title(self, character: 'Character', activity_type: Optional[str] = None, count: Optional[int] = None) -> Optional[TitleDefinition]:
        """
        Check if any new titles should be awarded based on character state.

        Args:
            character: Character instance with full state access
            activity_type: Optional legacy parameter (for backward compatibility)
            count: Optional legacy parameter (for backward compatibility)

        Returns:
            TitleDefinition if a new title was earned, None otherwise
        """
        for title_id, title_def in self.title_db.titles.items():
            # Skip if already earned
            if any(t.title_id == title_id for t in self.earned_titles):
                continue

            # Check if all requirements are met
            if not title_def.requirements.evaluate(character):
                continue

            # Requirements met - handle acquisition method
            if title_def.acquisition_method == "guaranteed_milestone":
                # Automatically granted
                self.earned_titles.append(title_def)
                return title_def

            elif title_def.acquisition_method == "event_based_rng":
                # RNG-based acquisition using generationChance from JSON
                if random.random() < title_def.generation_chance:
                    self.earned_titles.append(title_def)
                    return title_def

            elif title_def.acquisition_method == "hidden_discovery":
                # Hidden titles auto-granted when conditions met (like guaranteed but hidden)
                self.earned_titles.append(title_def)
                return title_def

            elif title_def.acquisition_method == "special_achievement":
                # Special achievements auto-granted (usually with very low chance from JSON)
                if random.random() < title_def.generation_chance:
                    self.earned_titles.append(title_def)
                    return title_def

            # Legacy fallback: random_drop (deprecated in favor of event_based_rng)
            elif title_def.acquisition_method == "random_drop":
                tier_chances = {
                    'novice': 1.0,
                    'apprentice': 0.20,
                    'journeyman': 0.10,
                    'expert': 0.05,
                    'master': 0.02
                }
                chance = tier_chances.get(title_def.tier, 0.10)
                if random.random() < chance:
                    self.earned_titles.append(title_def)
                    return title_def

        return None

    def get_total_bonus(self, bonus_type: str) -> float:
        total = 0.0
        for title in self.earned_titles:
            if bonus_type in title.bonuses:
                total += title.bonuses[bonus_type]
        return total

    def has_title(self, title_id: str) -> bool:
        return any(t.title_id == title_id for t in self.earned_titles)

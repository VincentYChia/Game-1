"""Title system for managing earned titles and bonuses"""

import random
from typing import List, Optional

from data.models import TitleDefinition
from data.databases import TitleDatabase


class TitleSystem:
    def __init__(self):
        self.earned_titles: List[TitleDefinition] = []
        self.title_db = TitleDatabase.get_instance()

    def check_for_title(self, activity_type: str, count: int) -> Optional[TitleDefinition]:
        import random

        for title_id, title_def in self.title_db.titles.items():
            if any(t.title_id == title_id for t in self.earned_titles):
                continue
            if title_def.activity_type != activity_type:
                continue
            if count < title_def.acquisition_threshold:
                continue
            if title_def.prerequisites:
                has_prereqs = all(
                    any(t.title_id == prereq for t in self.earned_titles)
                    for prereq in title_def.prerequisites
                )
                if not has_prereqs:
                    continue

            # Check acquisition method
            if title_def.acquisition_method == "guaranteed_milestone":
                # Automatically granted
                self.earned_titles.append(title_def)
                return title_def
            elif title_def.acquisition_method == "random_drop":
                # RNG-based acquisition with tier-based chances
                tier_chances = {
                    'novice': 1.0,      # 100% (shouldn't use random_drop)
                    'apprentice': 0.20,  # 20%
                    'journeyman': 0.10,  # 10%
                    'expert': 0.05,      # 5%
                    'master': 0.02       # 2%
                }
                chance = tier_chances.get(title_def.tier, 0.10)
                if random.random() < chance:
                    self.earned_titles.append(title_def)
                    return title_def
            elif title_def.acquisition_method == "hidden_discovery":
                # Hidden titles auto-granted when conditions met (like guaranteed but hidden)
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

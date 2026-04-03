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

    def _award_title(self, title_def: TitleDefinition, character=None) -> TitleDefinition:
        """Award a title and publish to GameEventBus."""
        self.earned_titles.append(title_def)

        # Track in stat tracker
        if character and hasattr(character, 'stat_tracker'):
            character.stat_tracker.record_title_earned(title_def.title_id, tier=getattr(title_def, 'tier', 'novice'))

        try:
            from events.event_bus import get_event_bus
            get_event_bus().publish("TITLE_EARNED", {
                "actor_id": "player",
                "title_id": title_def.title_id,
                "tier": getattr(title_def, 'tier', 'novice'),
            })
        except Exception:
            pass
        return title_def

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
                return self._award_title(title_def, character)

            elif title_def.acquisition_method == "event_based_rng":
                if random.random() < title_def.generation_chance:
                    return self._award_title(title_def, character)

            elif title_def.acquisition_method == "hidden_discovery":
                return self._award_title(title_def, character)

            elif title_def.acquisition_method == "special_achievement":
                if random.random() < title_def.generation_chance:
                    return self._award_title(title_def, character)

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
                    return self._award_title(title_def, character)

        return None

    def get_total_bonus(self, bonus_type: str) -> float:
        total = 0.0
        for title in self.earned_titles:
            if bonus_type in title.bonuses:
                total += title.bonuses[bonus_type]
        return total

    def has_title(self, title_id: str) -> bool:
        return any(t.title_id == title_id for t in self.earned_titles)

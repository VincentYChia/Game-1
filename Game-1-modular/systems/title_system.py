"""Title system for managing earned titles and bonuses"""

import random
import re
from typing import List, Optional, TYPE_CHECKING

from data.models import TitleDefinition
from data.databases import TitleDatabase

if TYPE_CHECKING:
    from entities.character import Character


# title_db._map_title_bonuses normalizes JSON camelCase -> snake_case storage, with a
# few specific renames that change the semantic key (not just casing). The resolver
# below lets callers query with any spelling and still hit the stored key.
_BONUS_KEY_RENAMES = {
    'smithing_time': 'smithing_speed',        # JSON 'smithingTime' -> stored 'smithing_speed'
    'refining_precision': 'refining_speed',   # JSON 'refiningPrecision' -> stored 'refining_speed'
    'critical_chance': 'crit_chance',         # JSON 'criticalChance' -> stored 'crit_chance'
}

# Tolerates the 'elementalAfinity' typo in current titles-1.JSON without migrating data.
_BONUS_KEY_TYPO_FIXES = {
    'elemental_affinity': 'elemental_afinity',
}


def _to_snake_case(name: str) -> str:
    """Convert camelCase to snake_case. Passes snake_case through unchanged."""
    return re.sub(r'(?<!^)(?=[A-Z])', '_', name).lower()


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
        """Sum a bonus across all earned titles.

        Accepts camelCase, snake_case, or known aliases. Normalization order:
        1. Literal match (already-correct queries)
        2. camelCase -> snake_case conversion
        3. Known renames (e.g. smithing_time -> smithing_speed)
        4. Known typo tolerance (e.g. elemental_affinity -> elemental_afinity)
        """
        candidates = self._resolve_bonus_keys(bonus_type)
        total = 0.0
        for title in self.earned_titles:
            for candidate in candidates:
                if candidate in title.bonuses:
                    value = title.bonuses[candidate]
                    # Skip non-numeric values (e.g. "elementalAfinity": "fire" in legacy data)
                    if isinstance(value, (int, float)):
                        total += value
                    break
        return total

    def _resolve_bonus_keys(self, bonus_type: str) -> List[str]:
        """Build candidate-key list for matching a query to stored bonus keys."""
        candidates = [bonus_type]
        snake = _to_snake_case(bonus_type)
        if snake != bonus_type:
            candidates.append(snake)
        if snake in _BONUS_KEY_RENAMES:
            candidates.append(_BONUS_KEY_RENAMES[snake])
        if snake in _BONUS_KEY_TYPO_FIXES:
            candidates.append(_BONUS_KEY_TYPO_FIXES[snake])
        return candidates

    def has_title(self, title_id: str) -> bool:
        return any(t.title_id == title_id for t in self.earned_titles)

"""Title Database - manages achievement titles and bonuses"""

import json
from typing import Dict, Tuple
from data.models.titles import TitleDefinition


class TitleDatabase:
    _instance = None

    def __init__(self):
        self.titles: Dict[str, TitleDefinition] = {}
        self.loaded = False

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = TitleDatabase()
        return cls._instance

    def load_from_file(self, filepath: str):
        try:
            with open(filepath, 'r') as f:
                data = json.load(f)
            for title_data in data.get('titles', []):
                prereqs = title_data.get('prerequisites', {})
                activities = prereqs.get('activities', {})
                activity_type, threshold = self._parse_activity(activities)
                prereq_titles = prereqs.get('requiredTitles', [])
                bonuses = self._map_title_bonuses(title_data.get('bonuses', {}))

                title = TitleDefinition(
                    title_id=title_data.get('titleId', ''),
                    name=title_data.get('name', ''),
                    tier=title_data.get('difficultyTier', 'novice'),
                    category=title_data.get('titleType', 'general'),
                    activity_type=activity_type,
                    acquisition_threshold=threshold,
                    bonus_description=self._create_bonus_description(bonuses),
                    bonuses=bonuses,
                    prerequisites=prereq_titles,
                    hidden=title_data.get('isHidden', False),
                    acquisition_method=title_data.get('acquisitionMethod', 'guaranteed_milestone')
                )
                self.titles[title.title_id] = title
            self.loaded = True
            print(f"✓ Loaded {len(self.titles)} titles")
            return True
        except Exception as e:
            print(f"⚠ Error loading titles: {e}")
            self._create_placeholders()
            return False

    def _parse_activity(self, activities: Dict) -> Tuple[str, int]:
        activity_mapping = {
            'oresMined': 'mining', 'treesChopped': 'forestry', 'itemsSmithed': 'smithing',
            'materialsRefined': 'refining', 'potionsBrewed': 'alchemy', 'itemsEnchanted': 'enchanting',
            'devicesCreated': 'engineering', 'enemiesDefeated': 'combat', 'bossesDefeated': 'combat',
            'areasExplored': 'exploration'
        }

        if activities:
            for json_key, threshold in activities.items():
                activity_type = activity_mapping.get(json_key, 'general')
                return activity_type, threshold

        return 'general', 0

    def _map_title_bonuses(self, bonuses: Dict) -> Dict[str, float]:
        mapping = {
            'miningDamage': 'mining_damage', 'miningSpeed': 'mining_speed', 'forestryDamage': 'forestry_damage',
            'forestrySpeed': 'forestry_speed', 'smithingTime': 'smithing_speed', 'smithingQuality': 'smithing_quality',
            'refiningPrecision': 'refining_speed', 'meleeDamage': 'melee_damage', 'criticalChance': 'crit_chance',
            'attackSpeed': 'attack_speed', 'firstTryBonus': 'first_try_bonus', 'rareOreChance': 'rare_ore_chance',
            'rareWoodChance': 'rare_wood_chance', 'fireOreChance': 'fire_ore_chance', 'alloyQuality': 'alloy_quality',
            'materialYield': 'material_yield', 'combatSkillExp': 'combat_skill_exp', 'counterChance': 'counter_chance',
            'durabilityBonus': 'durability_bonus', 'legendaryChance': 'legendary_chance',
            'dragonDamage': 'dragon_damage',
            'fireResistance': 'fire_resistance', 'legendaryDropRate': 'legendary_drop_rate', 'luckStat': 'luck_stat',
            'rareDropRate': 'rare_drop_rate'
        }

        mapped_bonuses = {}
        for json_key, value in bonuses.items():
            internal_key = mapping.get(json_key, json_key.lower())
            mapped_bonuses[internal_key] = value

        return mapped_bonuses

    def _create_bonus_description(self, bonuses: Dict[str, float]) -> str:
        if not bonuses:
            return "No bonuses"
        first_bonus = list(bonuses.items())[0]
        bonus_name, bonus_value = first_bonus
        percent = f"+{int(bonus_value * 100)}%"
        readable = bonus_name.replace('_', ' ').title()
        return f"{percent} {readable}"

    def _create_placeholders(self):
        novice_titles = [
            TitleDefinition('novice_miner', 'Novice Miner', 'novice', 'gathering', 'mining', 100,
                            '+10% mining damage', {'mining_damage': 0.10}),
            TitleDefinition('novice_lumberjack', 'Novice Lumberjack', 'novice', 'gathering', 'forestry', 100,
                            '+10% forestry damage', {'forestry_damage': 0.10}),
            TitleDefinition('novice_smith', 'Novice Smith', 'novice', 'crafting', 'smithing', 50,
                            '+10% smithing speed', {'smithing_speed': 0.10}),
            TitleDefinition('novice_refiner', 'Novice Refiner', 'novice', 'crafting', 'refining', 50,
                            '+10% refining speed', {'refining_speed': 0.10}),
            TitleDefinition('novice_alchemist', 'Novice Alchemist', 'novice', 'crafting', 'alchemy', 50,
                            '+10% alchemy speed', {'alchemy_speed': 0.10}),
        ]
        for title in novice_titles:
            self.titles[title.title_id] = title
        self.loaded = True
        print(f"✓ Created {len(self.titles)} placeholder titles")

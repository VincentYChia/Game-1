"""Class Database - manages character class definitions"""

import json
from typing import Dict
from data.models.classes import ClassDefinition


class ClassDatabase:
    _instance = None

    def __init__(self):
        self.classes: Dict[str, ClassDefinition] = {}
        self.loaded = False

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = ClassDatabase()
        return cls._instance

    def load_from_file(self, filepath: str):
        try:
            with open(filepath, 'r') as f:
                data = json.load(f)
            for class_data in data.get('classes', []):
                starting_bonuses = class_data.get('startingBonuses', {})
                bonuses = self._map_bonuses(starting_bonuses)
                skill_data = class_data.get('startingSkill', {})
                starting_skill = skill_data.get('skillId', '') if isinstance(skill_data, dict) else ''
                rec_stats_data = class_data.get('recommendedStats', {})
                rec_stats = rec_stats_data.get('primary', []) if isinstance(rec_stats_data, dict) else []

                cls_def = ClassDefinition(
                    class_id=class_data.get('classId', ''),
                    name=class_data.get('name', ''),
                    description=class_data.get('description', ''),
                    bonuses=bonuses,
                    starting_skill=starting_skill,
                    recommended_stats=rec_stats
                )
                self.classes[cls_def.class_id] = cls_def
            self.loaded = True
            print(f"✓ Loaded {len(self.classes)} classes")
            return True
        except Exception as e:
            print(f"⚠ Error loading classes: {e}")
            self._create_placeholders()
            return False

    def _map_bonuses(self, starting_bonuses: Dict) -> Dict[str, float]:
        mapping = {
            'baseHP': 'max_health', 'baseMana': 'max_mana', 'meleeDamage': 'melee_damage',
            'inventorySlots': 'inventory_slots', 'carryCapacity': 'carry_capacity', 'movementSpeed': 'movement_speed',
            'critChance': 'crit_chance', 'forestryBonus': 'forestry_damage', 'recipeDiscovery': 'recipe_discovery',
            'skillExpGain': 'skill_exp', 'allCraftingTime': 'crafting_speed', 'firstTryBonus': 'first_try_bonus',
            'itemDurability': 'durability_bonus', 'rareDropRate': 'rare_drops', 'resourceQuality': 'resource_quality',
            'allGathering': 'gathering_bonus', 'allCrafting': 'crafting_bonus', 'defense': 'defense_bonus',
            'miningBonus': 'mining_damage', 'attackSpeed': 'attack_speed'
        }

        bonuses = {}
        for json_key, value in starting_bonuses.items():
            internal_key = mapping.get(json_key, json_key.lower().replace(' ', '_'))
            bonuses[internal_key] = value

        return bonuses

    def _create_placeholders(self):
        classes_data = [
            ('warrior', 'Warrior', 'A melee fighter with high health and damage',
             {'max_health': 30, 'melee_damage': 0.10, 'carry_capacity': 20}, 'battle_rage', ['STR', 'VIT', 'DEF']),
            ('ranger', 'Ranger', 'A nimble hunter specializing in speed and precision',
             {'movement_speed': 0.15, 'crit_chance': 0.10, 'forestry_damage': 0.10}, 'forestry_frenzy',
             ['AGI', 'LCK', 'VIT']),
            ('scholar', 'Scholar', 'A learned mage with vast knowledge',
             {'max_mana': 100, 'recipe_discovery': 0.10, 'skill_exp': 0.05}, 'alchemist_touch', ['INT', 'LCK', 'AGI']),
            ('artisan', 'Artisan', 'A master craftsman creating quality goods',
             {'crafting_speed': 0.10, 'first_try_bonus': 0.10, 'durability_bonus': 0.05}, 'smithing_focus',
             ['AGI', 'INT', 'LCK']),
            ('scavenger', 'Scavenger', 'A treasure hunter with keen eyes',
             {'rare_drops': 0.20, 'resource_quality': 0.10, 'carry_capacity': 100}, 'treasure_luck',
             ['LCK', 'STR', 'VIT']),
            ('adventurer', 'Adventurer', 'A balanced jack-of-all-trades',
             {'gathering_bonus': 0.05, 'crafting_bonus': 0.05, 'max_health': 50, 'max_mana': 50}, '', ['Balanced'])
        ]
        for class_id, name, desc, bonuses, skill, stats in classes_data:
            self.classes[class_id] = ClassDefinition(class_id, name, desc, bonuses, skill, stats)
        self.loaded = True
        print(f"✓ Created {len(self.classes)} placeholder classes")

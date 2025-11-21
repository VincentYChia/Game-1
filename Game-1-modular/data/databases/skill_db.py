"""Skill Database - manages skill definitions and translation tables"""

import json
from typing import Dict
from data.models.skills import SkillDefinition, SkillEffect, SkillCost, SkillEvolution, SkillRequirements


class SkillDatabase:
    _instance = None

    def __init__(self):
        self.skills: Dict[str, SkillDefinition] = {}
        self.loaded = False
        # Translation table for text values
        self.mana_costs = {"low": 30, "moderate": 60, "high": 100, "extreme": 150}
        self.cooldowns = {"short": 120, "moderate": 300, "long": 600, "extreme": 1200}
        self.durations = {"instant": 0, "brief": 15, "moderate": 30, "long": 60, "extended": 120}

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = SkillDatabase()
        return cls._instance

    def load_from_file(self, filepath: str = ""):
        """Load skills from JSON file"""
        try:
            with open(filepath, 'r') as f:
                data = json.load(f)

            for skill_data in data.get('skills', []):
                # Parse effect
                effect_data = skill_data.get('effect', {})
                effect = SkillEffect(
                    effect_type=effect_data.get('type', ''),
                    category=effect_data.get('category', ''),
                    magnitude=effect_data.get('magnitude', ''),
                    target=effect_data.get('target', 'self'),
                    duration=effect_data.get('duration', 'instant'),
                    additional_effects=effect_data.get('additionalEffects', [])
                )

                # Parse cost
                cost_data = skill_data.get('cost', {})
                cost = SkillCost(
                    mana=cost_data.get('mana', 'moderate'),
                    cooldown=cost_data.get('cooldown', 'moderate')
                )

                # Parse evolution
                evo_data = skill_data.get('evolution', {})
                evolution = SkillEvolution(
                    can_evolve=evo_data.get('canEvolve', False),
                    next_skill_id=evo_data.get('nextSkillId'),
                    requirement=evo_data.get('requirement', '')
                )

                # Parse requirements
                req_data = skill_data.get('requirements', {})
                requirements = SkillRequirements(
                    character_level=req_data.get('characterLevel', 1),
                    stats=req_data.get('stats', {}),
                    titles=req_data.get('titles', [])
                )

                # Create skill definition
                skill = SkillDefinition(
                    skill_id=skill_data.get('skillId', ''),
                    name=skill_data.get('name', ''),
                    tier=skill_data.get('tier', 1),
                    rarity=skill_data.get('rarity', 'common'),
                    categories=skill_data.get('categories', []),
                    description=skill_data.get('description', ''),
                    narrative=skill_data.get('narrative', ''),
                    tags=skill_data.get('tags', []),
                    effect=effect,
                    cost=cost,
                    evolution=evolution,
                    requirements=requirements
                )

                self.skills[skill.skill_id] = skill

            self.loaded = True
            print(f"✓ Loaded {len(self.skills)} skills from {filepath}")
            return True

        except Exception as e:
            print(f"⚠ Error loading skills from {filepath}: {e}")
            self.loaded = False
            return False

    def get_skill(self, skill_id: str):
        """Get a skill definition by ID"""
        return self.skills.get(skill_id)

    def get_mana_cost(self, cost_text: str) -> int:
        """Convert text mana cost to numeric value"""
        return self.mana_costs.get(cost_text, 60)

    def get_cooldown_seconds(self, cooldown_text: str) -> float:
        """Convert text cooldown to seconds"""
        return self.cooldowns.get(cooldown_text, 300)

    def get_duration_seconds(self, duration_text: str) -> float:
        """Convert text duration to seconds"""
        return self.durations.get(duration_text, 0)

"""Skill Database - manages skill definitions and translation tables"""

import json
from typing import Dict, Union
from data.models.skills import SkillDefinition, SkillEffect, SkillCost, SkillEvolution, SkillRequirements


class SkillDatabase:
    _instance = None

    # Sacred + generated conventions (Phase 0 G07e, 2026-06-03).
    # Sacred skills file is ``Skills/skills-skills-1.JSON`` per
    # game_engine.py:143. Generated files use the convention from
    # ``world_system/content_registry/generated_file_writer.py:13``.
    SACRED_DIR = "Skills"
    SACRED_GLOB = "skills-skills-*.JSON"
    GENERATED_GLOB = "skills-generated-*.JSON"

    def __init__(self):
        self.skills: Dict[str, SkillDefinition] = {}
        self.loaded = False

    # §15 trap 5 (2026-06-05): the legacy in-class dicts ``mana_costs``,
    # ``cooldowns``, ``durations`` are now thin properties delegating
    # to :class:`TranslationDatabase`, which is the sole owner of the
    # JSON-loaded translation tables. Reads still work as
    # ``SkillDatabase.get_instance().mana_costs[key]``; writes raise.
    @staticmethod
    def _translations():
        from data.databases.translation_db import TranslationDatabase
        td = TranslationDatabase.get_instance()
        if not td.loaded:
            td.load_from_files()
        return td

    @property
    def mana_costs(self) -> Dict[str, int]:
        return self._translations().mana_costs

    @property
    def cooldowns(self) -> Dict[str, int]:
        return self._translations().cooldown_seconds

    @property
    def durations(self) -> Dict[str, int]:
        return self._translations().duration_seconds

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = SkillDatabase()
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        """Test helper — drop the singleton so the next get_instance reloads."""
        cls._instance = None

    def load_from_files(self) -> None:
        """Read all sacred + generated skill files from ``Skills/``.

        Idempotent. Clears the in-memory dict before reloading so a
        ``reload()`` cycle reflects the on-disk state precisely.
        Generated files overlay sacred (loaded second), so a WES-emitted
        skill sharing an id with a sacred skill wins — same precedence
        as ChunkTemplateDatabase / TitleDatabase.

        Never raises — failures degrade to whatever was already loaded.
        """
        from core.paths import get_resource_path
        try:
            self.skills = {}
            try:
                sacred_dir = get_resource_path(self.SACRED_DIR)
            except Exception:
                sacred_dir = None
            if sacred_dir is not None and sacred_dir.exists():
                for path in sorted(sacred_dir.glob(self.SACRED_GLOB)):
                    if "generated" in path.name.lower():
                        continue
                    self.load_from_file(str(path))
                for path in sorted(sacred_dir.glob(self.GENERATED_GLOB)):
                    self.load_from_file(str(path))
            self.loaded = bool(self.skills)
        except Exception as e:
            print(f"[SkillDatabase] load_from_files outer error: {e}")
            self.loaded = False

    def reload(self) -> None:
        """Re-read all skill files from disk after a WES content commit.

        Called by :func:`world_system.content_registry.database_reloader`
        once the Content Registry writes ``Skills/skills-generated-*.JSON``
        siblings. Drops the in-memory cache and reloads. Never raises;
        on any failure the previous in-memory state is preserved
        (prefer stale-but-intact over crashing skill evaluation).
        """
        old_skills = dict(self.skills)
        old_loaded = self.loaded
        try:
            self.load_from_files()
        except Exception as e:
            print(f"[SkillDatabase] reload failed, keeping previous: {e}")
            self.skills = old_skills
            self.loaded = old_loaded

    def load_from_file(self, filepath: str = ""):
        """Load skills from JSON file"""
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
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

                # Get or auto-generate icon path
                skill_id = skill_data.get('skillId', '')
                icon_path = skill_data.get('iconPath')
                if not icon_path and skill_id:
                    icon_path = f"skills/{skill_id}.png"

                # Create skill definition
                skill = SkillDefinition(
                    skill_id=skill_id,
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
                    requirements=requirements,
                    icon_path=icon_path,
                    combat_tags=skill_data.get('combatTags', []),
                    combat_params=skill_data.get('combatParams', {})
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

    def get_mana_cost(self, cost_value: Union[str, int, float]) -> int:
        """Convert mana cost to numeric value - supports both string enums and direct numeric values"""
        if isinstance(cost_value, (int, float)):
            return int(cost_value)
        # String enum - use translation table for backward compatibility
        return self.mana_costs.get(cost_value, 60)

    def get_cooldown_seconds(self, cooldown_value: Union[str, int, float]) -> float:
        """Convert cooldown to seconds - supports both string enums and direct numeric values"""
        if isinstance(cooldown_value, (int, float)):
            return float(cooldown_value)
        # String enum - use translation table for backward compatibility
        return self.cooldowns.get(cooldown_value, 300)

    def get_duration_seconds(self, duration_text: str) -> float:
        """Convert text duration to seconds"""
        return self.durations.get(duration_text, 0)

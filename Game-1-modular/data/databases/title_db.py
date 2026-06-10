"""Title Database - manages achievement titles and bonuses"""

import json
from typing import Dict, Tuple
from data.models.titles import TitleDefinition
from data.models.unlock_conditions import ConditionFactory


class TitleDatabase:
    _instance = None

    # Sacred + generated file conventions (Phase 0 G07, 2026-06-03).
    # Sacred files live under progression/ and follow the titles-*.JSON
    # pattern. WES-generated content writes titles-generated-*.JSON
    # siblings; reload() picks them up.
    SACRED_DIR = "progression"
    SACRED_GLOB = "titles-*.JSON"
    GENERATED_GLOB = "titles-generated-*.JSON"

    def __init__(self):
        self.titles: Dict[str, TitleDefinition] = {}
        self.loaded = False

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = TitleDatabase()
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        """Test helper — drop the singleton so the next get_instance reloads.

        Matches the ChunkTemplateDatabase / NPCDatabase reset() pattern
        used in E2E tests that need a fresh database state.
        """
        cls._instance = None

    def load_from_files(self) -> None:
        """Read all sacred + generated title files from ``progression/``.

        Idempotent. Clears the in-memory dict before reloading so a
        ``reload()`` cycle reflects the on-disk state precisely.
        Generated files overlay sacred (loaded second), so a WES-emitted
        title sharing an id with a sacred title wins — same precedence
        as ``ChunkTemplateDatabase``.

        Never raises — failures degrade to whatever was already loaded
        (or empty state on first call).
        """
        from core.paths import get_resource_path
        from pathlib import Path
        try:
            self.titles = {}
            try:
                sacred_dir: Path = get_resource_path(self.SACRED_DIR)
            except Exception:
                sacred_dir = None  # type: ignore[assignment]
            if sacred_dir and sacred_dir.exists():
                for path in sorted(sacred_dir.glob(self.SACRED_GLOB)):
                    # Skip generated — they are loaded second so they win.
                    if "generated" in path.name.lower():
                        continue
                    self.load_from_file(str(path))
                for path in sorted(sacred_dir.glob(self.GENERATED_GLOB)):
                    self.load_from_file(str(path))
            self.loaded = True
        except Exception as e:
            print(f"[TitleDatabase] load_from_files outer error: {e}")
            self.loaded = False

    def reload(self) -> None:
        """Re-read all title files from disk after a WES content commit.

        Called by :func:`world_system.content_registry.database_reloader`
        once the Content Registry writes ``titles-generated-*.JSON``
        siblings. Drops the in-memory cache and reloads. Never raises;
        on any failure the previous in-memory state is preserved (prefer
        stale-but-intact over crashing title evaluation).
        """
        old_titles = dict(self.titles)
        old_loaded = self.loaded
        try:
            self.load_from_files()
        except Exception as e:
            print(
                f"[TitleDatabase] reload failed, keeping previous: {e}"
            )
            self.titles = old_titles
            self.loaded = old_loaded

    def load_from_file(self, filepath: str):
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
            for title_data in data.get('titles', []):
                title = self._parse_title_definition(title_data)
                self.titles[title.title_id] = title
            self.loaded = True
            print(f"✓ Loaded {len(self.titles)} titles")
            return True
        except Exception as e:
            print(f"⚠ Error loading titles: {e}")
            import traceback
            traceback.print_exc()
            self._create_placeholders()
            return False

    def _parse_title_definition(self, title_data: dict) -> TitleDefinition:
        """Parse a single title definition from JSON."""
        # Parse bonuses
        bonuses = self._map_title_bonuses(title_data.get('bonuses', {}))

        # Get or auto-generate icon path
        title_id = title_data.get('titleId', '')
        icon_path = title_data.get('iconPath')
        if not icon_path and title_id:
            icon_path = f"titles/{title_id}.png"

        # Parse requirements using new condition system
        prereqs = title_data.get('prerequisites', {})
        requirements = ConditionFactory.create_requirements_from_json(prereqs)

        # Extract legacy activity type and threshold for backward compatibility
        activities = prereqs.get('activities', {})
        activity_type, threshold = self._parse_activity(activities)
        prereq_titles = prereqs.get('requiredTitles', [])

        # Parse acquisition method
        acquisition_method = title_data.get('acquisitionMethod', 'guaranteed_milestone')

        # Parse generation chance for RNG-based titles
        generation_chance = title_data.get('generationChance', 1.0)

        return TitleDefinition(
            title_id=title_id,
            name=title_data.get('name', ''),
            tier=title_data.get('difficultyTier', 'novice'),
            category=title_data.get('titleType', 'general'),
            bonus_description=self._create_bonus_description(bonuses),
            bonuses=bonuses,
            requirements=requirements,
            hidden=title_data.get('isHidden', False),
            acquisition_method=acquisition_method,
            generation_chance=generation_chance,
            icon_path=icon_path,
            # Legacy fields
            activity_type=activity_type,
            acquisition_threshold=threshold,
            prerequisites=prereq_titles
        )

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
            'rareDropRate': 'rare_drop_rate',
            # Fishing bonuses
            'fishingSpeed': 'fishing_speed', 'fishingAccuracy': 'fishing_accuracy',
            'rareFishChance': 'rare_fish_chance', 'fishingYield': 'fishing_yield'
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
        """Create placeholder titles with new requirement system."""
        from data.models.unlock_conditions import UnlockRequirements, ActivityCondition

        novice_titles = [
            TitleDefinition(
                'novice_miner', 'Novice Miner', 'novice', 'gathering',
                '+10% mining damage', {'mining_damage': 0.10},
                UnlockRequirements([ActivityCondition('mining', 100)]),
                False, 'guaranteed_milestone', 1.0, 'titles/novice_miner.png',
                'mining', 100, []
            ),
            TitleDefinition(
                'novice_lumberjack', 'Novice Lumberjack', 'novice', 'gathering',
                '+10% forestry damage', {'forestry_damage': 0.10},
                UnlockRequirements([ActivityCondition('forestry', 100)]),
                False, 'guaranteed_milestone', 1.0, 'titles/novice_lumberjack.png',
                'forestry', 100, []
            ),
            TitleDefinition(
                'novice_smith', 'Novice Smith', 'novice', 'crafting',
                '+10% smithing speed', {'smithing_speed': 0.10},
                UnlockRequirements([ActivityCondition('smithing', 50)]),
                False, 'guaranteed_milestone', 1.0, 'titles/novice_smith.png',
                'smithing', 50, []
            ),
            TitleDefinition(
                'novice_refiner', 'Novice Refiner', 'novice', 'crafting',
                '+10% refining speed', {'refining_speed': 0.10},
                UnlockRequirements([ActivityCondition('refining', 50)]),
                False, 'guaranteed_milestone', 1.0, 'titles/novice_refiner.png',
                'refining', 50, []
            ),
            TitleDefinition(
                'novice_alchemist', 'Novice Alchemist', 'novice', 'crafting',
                '+10% alchemy speed', {'alchemy_speed': 0.10},
                UnlockRequirements([ActivityCondition('alchemy', 50)]),
                False, 'guaranteed_milestone', 1.0, 'titles/novice_alchemist.png',
                'alchemy', 50, []
            ),
        ]
        for title in novice_titles:
            self.titles[title.title_id] = title
        self.loaded = True
        print(f"✓ Created {len(self.titles)} placeholder titles")

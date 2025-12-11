"""Placement Database - manages placement data for all crafting disciplines"""

import json
from pathlib import Path
from typing import Dict, Optional
from data.models.recipes import PlacementData
from core.paths import get_resource_path


class PlacementDatabase:
    """Manages placement data for all crafting disciplines"""
    _instance = None

    def __init__(self):
        self.placements: Dict[str, PlacementData] = {}  # recipeId -> PlacementData
        self.loaded = False

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = PlacementDatabase()
        return cls._instance

    def load_from_files(self, base_path: str = ""):
        """Load all placement JSON files"""
        total = 0

        # Smithing placements
        total += self._load_smithing(str(get_resource_path("placements.JSON/placements-smithing-1.JSON")))

        # Refining placements
        total += self._load_refining(str(get_resource_path("placements.JSON/placements-refining-1.JSON")))

        # Alchemy placements
        total += self._load_alchemy(str(get_resource_path("placements.JSON/placements-alchemy-1.JSON")))

        # Engineering placements
        total += self._load_engineering(str(get_resource_path("placements.JSON/placements-engineering-1.JSON")))

        # Enchanting/Adornments placements
        total += self._load_enchanting(str(get_resource_path("placements.JSON/placements-adornments-1.JSON")))

        self.loaded = True
        print(f"✓ Loaded {total} placement templates")
        return total

    def _load_smithing(self, filepath: str) -> int:
        """Load smithing grid-based placements"""
        if not Path(filepath).exists():
            print(f"⚠ Smithing placements not found: {filepath}")
            return 0

        try:
            with open(filepath, 'r') as f:
                data = json.load(f)

            count = 0
            for placement in data.get('placements', []):
                recipe_id = placement.get('recipeId', '')
                if not recipe_id:
                    continue

                self.placements[recipe_id] = PlacementData(
                    recipe_id=recipe_id,
                    discipline='smithing',
                    grid_size=placement.get('metadata', {}).get('gridSize', '3x3'),
                    placement_map=placement.get('placementMap', {}),
                    narrative=placement.get('metadata', {}).get('narrative', '')
                )
                count += 1

            print(f"  ✓ Loaded {count} smithing placements")
            return count
        except Exception as e:
            print(f"  ✗ Error loading smithing placements: {e}")
            return 0

    def _load_refining(self, filepath: str) -> int:
        """Load refining hub-and-spoke placements"""
        if not Path(filepath).exists():
            print(f"⚠ Refining placements not found: {filepath}")
            return 0

        try:
            with open(filepath, 'r') as f:
                data = json.load(f)

            count = 0
            for placement in data.get('placements', []):
                recipe_id = placement.get('recipeId', '')
                if not recipe_id:
                    continue

                self.placements[recipe_id] = PlacementData(
                    recipe_id=recipe_id,
                    discipline='refining',
                    core_inputs=placement.get('coreInputs', []),
                    surrounding_inputs=placement.get('surroundingInputs', []),
                    output_id=placement.get('outputId', ''),
                    station_tier=placement.get('stationTier', 1),
                    narrative=placement.get('narrative', '')
                )
                count += 1

            print(f"  ✓ Loaded {count} refining placements")
            return count
        except Exception as e:
            print(f"  ✗ Error loading refining placements: {e}")
            return 0

    def _load_alchemy(self, filepath: str) -> int:
        """Load alchemy sequential placements"""
        if not Path(filepath).exists():
            print(f"⚠ Alchemy placements not found: {filepath}")
            return 0

        try:
            with open(filepath, 'r') as f:
                data = json.load(f)

            count = 0
            for placement in data.get('placements', []):
                recipe_id = placement.get('recipeId', '')
                if not recipe_id:
                    continue

                self.placements[recipe_id] = PlacementData(
                    recipe_id=recipe_id,
                    discipline='alchemy',
                    ingredients=placement.get('ingredients', []),
                    output_id=placement.get('outputId', ''),
                    station_tier=placement.get('stationTier', 1),
                    narrative=placement.get('narrative', '')
                )
                count += 1

            print(f"  ✓ Loaded {count} alchemy placements")
            return count
        except Exception as e:
            print(f"  ✗ Error loading alchemy placements: {e}")
            return 0

    def _load_engineering(self, filepath: str) -> int:
        """Load engineering slot-type placements"""
        if not Path(filepath).exists():
            print(f"⚠ Engineering placements not found: {filepath}")
            return 0

        try:
            with open(filepath, 'r') as f:
                data = json.load(f)

            count = 0
            for placement in data.get('placements', []):
                recipe_id = placement.get('recipeId', '')
                if not recipe_id:
                    continue

                self.placements[recipe_id] = PlacementData(
                    recipe_id=recipe_id,
                    discipline='engineering',
                    slots=placement.get('slots', []),
                    output_id=placement.get('outputId', ''),
                    station_tier=placement.get('stationTier', 1),
                    narrative=placement.get('narrative', '')
                )
                count += 1

            print(f"  ✓ Loaded {count} engineering placements")
            return count
        except Exception as e:
            print(f"  ✗ Error loading engineering placements: {e}")
            return 0

    def _load_enchanting(self, filepath: str) -> int:
        """Load enchanting pattern placements"""
        if not Path(filepath).exists():
            print(f"⚠ Enchanting placements not found: {filepath}")
            return 0

        try:
            with open(filepath, 'r') as f:
                data = json.load(f)

            count = 0
            for placement in data.get('placements', []):
                recipe_id = placement.get('recipeId', '')
                if not recipe_id:
                    continue

                # Enchanting may have pattern or grid-based placement
                self.placements[recipe_id] = PlacementData(
                    recipe_id=recipe_id,
                    discipline='adornments',
                    pattern=placement.get('pattern', []),
                    placement_map=placement.get('placementMap', {}),
                    grid_size=placement.get('metadata', {}).get('gridSize', '3x3'),
                    output_id=placement.get('outputId', ''),
                    station_tier=placement.get('stationTier', 1),
                    narrative=placement.get('narrative', '')
                )
                count += 1

            print(f"  ✓ Loaded {count} enchanting placements")
            return count
        except Exception as e:
            print(f"  ✗ Error loading enchanting placements: {e}")
            return 0

    def get_placement(self, recipe_id: str) -> Optional[PlacementData]:
        """Get placement data for a recipe"""
        return self.placements.get(recipe_id)

    def has_placement(self, recipe_id: str) -> bool:
        """Check if a recipe has placement data"""
        return recipe_id in self.placements

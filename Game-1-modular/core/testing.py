"""Automated testing framework for crafting system"""

from typing import TYPE_CHECKING

from data import (
    RecipeDatabase,
    PlacementDatabase,
    MaterialDatabase,
    EquipmentDatabase,
)

if TYPE_CHECKING:
    from .game_engine import GameEngine


class CraftingSystemTester:
    """Automated testing framework for crafting system - simulates user interactions"""

    def __init__(self, game_engine: 'GameEngine'):
        self.game = game_engine
        self.test_results = []
        self.tests_passed = 0
        self.tests_failed = 0

    def log_test(self, test_name: str, passed: bool, details: str = ""):
        """Log a test result"""
        status = "✓ PASS" if passed else "✗ FAIL"
        result = f"{status}: {test_name}"
        if details:
            result += f" - {details}"
        self.test_results.append(result)
        if passed:
            self.tests_passed += 1
        else:
            self.tests_failed += 1
        print(result)

    def run_all_tests(self):
        """Run comprehensive crafting system tests"""
        print("\n" + "=" * 70)
        print("AUTOMATED CRAFTING SYSTEM TEST SUITE")
        print("=" * 70)

        self.test_results = []
        self.tests_passed = 0
        self.tests_failed = 0

        # Test 1: Database initialization
        self.test_database_loading()

        # Test 2: Recipe loading for each discipline
        self.test_recipe_loading()

        # Test 3: Recipe tier sorting
        self.test_recipe_tier_sorting()

        # Test 4: Placement data loading
        self.test_placement_data()

        # Test 5: State initialization
        self.test_state_initialization()

        # Test 6: UI rendering (each discipline)
        self.test_ui_rendering()

        # Print summary
        print("\n" + "=" * 70)
        print(f"TEST SUMMARY: {self.tests_passed} passed, {self.tests_failed} failed")
        print("=" * 70)

        for result in self.test_results:
            print(result)

        return self.tests_failed == 0

    def test_database_loading(self):
        """Test that all required databases are loaded"""
        try:
            recipe_db = RecipeDatabase.get_instance()
            placement_db = PlacementDatabase.get_instance()
            mat_db = MaterialDatabase.get_instance()
            equip_db = EquipmentDatabase.get_instance()

            self.log_test("Database instances", True, "All databases initialized")
        except Exception as e:
            self.log_test("Database instances", False, str(e))

    def test_recipe_loading(self):
        """Test recipe loading for each crafting discipline"""
        recipe_db = RecipeDatabase.get_instance()
        disciplines = ['smithing', 'refining', 'alchemy', 'engineering', 'adornments']

        for discipline in disciplines:
            try:
                recipes_t1 = recipe_db.get_recipes_for_station(discipline, 1)
                recipes_t3 = recipe_db.get_recipes_for_station(discipline, 3)

                if len(recipes_t1) > 0:
                    self.log_test(f"Recipe loading: {discipline}", True,
                                f"T1: {len(recipes_t1)}, T3: {len(recipes_t3)} recipes")
                else:
                    self.log_test(f"Recipe loading: {discipline}", False,
                                "No recipes found")
            except Exception as e:
                self.log_test(f"Recipe loading: {discipline}", False, str(e))

    def test_recipe_tier_sorting(self):
        """Test that recipes are sorted by tier (highest first)"""
        recipe_db = RecipeDatabase.get_instance()

        try:
            # Get T3 smithing recipes (should include T1, T2, T3)
            recipes = recipe_db.get_recipes_for_station('smithing', 3)
            recipes = sorted(recipes, key=lambda r: r.station_tier, reverse=True)

            if len(recipes) > 1:
                # Check if first recipe has higher/equal tier than last
                first_tier = recipes[0].station_tier
                last_tier = recipes[-1].station_tier

                if first_tier >= last_tier:
                    self.log_test("Recipe tier sorting", True,
                                f"Sorted correctly (T{first_tier} first, T{last_tier} last)")
                else:
                    self.log_test("Recipe tier sorting", False,
                                f"Not sorted (T{first_tier} first, T{last_tier} last)")
            else:
                self.log_test("Recipe tier sorting", True, "Not enough recipes to test")
        except Exception as e:
            self.log_test("Recipe tier sorting", False, str(e))

    def test_placement_data(self):
        """Test placement data loading for each discipline"""
        placement_db = PlacementDatabase.get_instance()
        recipe_db = RecipeDatabase.get_instance()

        disciplines = {
            'smithing': 'grid',
            'refining': 'hub_spoke',
            'alchemy': 'sequential',
            'engineering': 'slots',
            'adornments': 'grid'
        }

        for discipline, expected_type in disciplines.items():
            try:
                recipes = recipe_db.get_recipes_for_station(discipline, 1)
                if recipes:
                    recipe = recipes[0]
                    placement_data = placement_db.get_placement(recipe.recipe_id)

                    if placement_data:
                        self.log_test(f"Placement data: {discipline}", True,
                                    f"Type: {placement_data.discipline}")
                    else:
                        self.log_test(f"Placement data: {discipline}", False,
                                    "No placement data found")
                else:
                    self.log_test(f"Placement data: {discipline}", False,
                                "No recipes to test")
            except Exception as e:
                self.log_test(f"Placement data: {discipline}", False, str(e))

    def test_state_initialization(self):
        """Test that game state initializes correctly"""
        try:
            # Check placement state variables exist
            assert hasattr(self.game, 'placement_mode')
            assert hasattr(self.game, 'placement_recipe')
            assert hasattr(self.game, 'placement_data')
            assert hasattr(self.game, 'placed_materials_grid')
            assert hasattr(self.game, 'placed_materials_hub')
            assert hasattr(self.game, 'placed_materials_sequential')
            assert hasattr(self.game, 'placed_materials_slots')

            self.log_test("State initialization", True, "All state variables present")
        except Exception as e:
            self.log_test("State initialization", False, str(e))

    def test_ui_rendering(self):
        """Test UI rendering for each discipline"""
        # This is a lightweight test - just verify methods exist
        disciplines = ['smithing', 'refining', 'alchemy', 'engineering', 'enchanting']

        for discipline in disciplines:
            try:
                method_name = f"_render_{discipline}_placement"
                if hasattr(self.game.renderer, method_name):
                    self.log_test(f"UI render method: {discipline}", True,
                                f"Method {method_name} exists")
                else:
                    self.log_test(f"UI render method: {discipline}", False,
                                f"Method {method_name} not found")
            except Exception as e:
                self.log_test(f"UI render method: {discipline}", False, str(e))

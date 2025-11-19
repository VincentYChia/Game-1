#!/usr/bin/env python3
"""
Quick test to verify no crashes in basic operations
"""
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from smithing import SmithingCrafter
from refining import RefiningCrafter
from alchemy import AlchemyCrafter
from engineering import EngineeringCrafter
from enchanting import EnchantingCrafter

def test_basic_operations():
    """Test basic crafting operations"""
    print("=" * 80)
    print("TESTING BASIC CRAFTING OPERATIONS")
    print("=" * 80)

    # Test inventory
    test_inventory = {
        'copper_ore': 100,
        'copper_ingot': 100,
        'iron_ore': 100,
        'iron_ingot': 100,
        'oak_log': 100,
        'oak_plank': 100,
        'wolf_pelt': 100,
        'beetle_carapace': 100,
        'granite': 100,
        'fire_crystal': 100,
        'water_crystal': 100,
        'healing_herb': 100,
        'slime_gel': 100
    }

    # Test Smithing
    print("\n[SMITHING] Testing...")
    smithing = SmithingCrafter()
    recipes = smithing.get_all_recipes()
    if recipes:
        recipe_id = list(recipes.keys())[0]
        print(f"  Recipe: {recipe_id}")
        can_craft = smithing.can_craft(recipe_id, test_inventory)
        print(f"  Can craft: {can_craft}")

        # Test minigame result processing
        if can_craft:
            fake_result = {'success': True, 'bonus': 5, 'score': 100}
            result = smithing.craft_with_minigame(recipe_id, test_inventory.copy(), fake_result)
            print(f"  Result: success={result.get('success')}, stats={result.get('stats')}")
            assert 'stats' in result, "Smithing should return stats"
            assert result['stats']['durability'] > 0, "Stats should have values"

    # Test Refining
    print("\n[REFINING] Testing...")
    refining = RefiningCrafter()
    recipes = refining.get_all_recipes()
    if recipes:
        recipe_id = list(recipes.keys())[0]
        print(f"  Recipe: {recipe_id}")
        can_craft = refining.can_craft(recipe_id, test_inventory)
        print(f"  Can craft: {can_craft}")

        if can_craft:
            fake_result = {'success': True, 'quality': 0.95}
            result = refining.craft_with_minigame(recipe_id, test_inventory.copy(), fake_result)
            print(f"  Result: success={result.get('success')}, rarity={result.get('rarity')}")
            assert 'rarity' in result, "Refining should return rarity"

    # Test Alchemy
    print("\n[ALCHEMY] Testing...")
    alchemy = AlchemyCrafter()
    recipes = alchemy.get_all_recipes()
    if recipes:
        recipe_id = list(recipes.keys())[0]
        print(f"  Recipe: {recipe_id}")
        can_craft = alchemy.can_craft(recipe_id, test_inventory)
        print(f"  Can craft: {can_craft}")

        if can_craft:
            fake_result = {
                'success': True,
                'quality': 'Strong Success',
                'duration_mult': 1.5,
                'effect_mult': 1.3
            }
            result = alchemy.craft_with_minigame(recipe_id, test_inventory.copy(), fake_result)
            print(f"  Result: success={result.get('success')}, stats={result.get('stats')}")
            assert 'stats' in result, "Alchemy should return stats"

    # Test Engineering
    print("\n[ENGINEERING] Testing...")
    engineering = EngineeringCrafter()
    recipes = engineering.get_all_recipes()
    if recipes:
        recipe_id = list(recipes.keys())[0]
        print(f"  Recipe: {recipe_id}")
        can_craft = engineering.can_craft(recipe_id, test_inventory)
        print(f"  Can craft: {can_craft}")

        if can_craft:
            fake_result = {
                'success': True,
                'puzzles_solved': 3,
                'stats': {'durability': 115, 'efficiency': 130, 'accuracy': 100, 'power': 115},
                'quality': 1.15
            }
            result = engineering.craft_with_minigame(recipe_id, test_inventory.copy(), fake_result)
            print(f"  Result: success={result.get('success')}, stats={result.get('stats')}")
            assert 'stats' in result, "Engineering should return stats"

    # Test Enchanting
    print("\n[ENCHANTING] Testing...")
    enchanting = EnchantingCrafter()
    recipes = enchanting.get_all_recipes()
    if recipes:
        recipe_id = list(recipes.keys())[0]
        print(f"  Recipe: {recipe_id}")
        can_craft = enchanting.can_craft(recipe_id, test_inventory)
        print(f"  Can craft: {can_craft}")

    print("\n" + "=" * 80)
    print("ALL TESTS PASSED - No crashes detected")
    print("=" * 80)

if __name__ == "__main__":
    try:
        test_basic_operations()
    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

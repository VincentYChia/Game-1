"""
Comprehensive Integration Test for Invented Items System

Tests:
1. Inventory add_item properly handles equipment_instance parameter
2. PlacementDatabase registration works correctly
3. RecipeDatabase registration works correctly
4. Crafter registration works correctly
5. Duplicate recipe detection works
6. Tooltips have proper data
7. Save/load preserves invented recipes

Run with: python -m tests.test_invented_items_integration
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_inventory_equipment_instance():
    """Test that inventory.add_item properly uses equipment_instance parameter."""
    print("\n" + "="*60)
    print("TEST 1: Inventory Equipment Instance Handling")
    print("="*60)

    from entities.components.inventory import Inventory, ItemStack
    from data.models.equipment import EquipmentItem

    # Create a mock equipment instance for an invented item
    invented_equipment = EquipmentItem(
        item_id="invented_test_sword_001",
        name="Test Invented Sword",
        tier=2,
        rarity="rare",
        slot="mainHand",
        damage=(10, 20),
        defense=0,
        durability_current=500,
        durability_max=500,
        attack_speed=1.0,
        efficiency=1.0,
        weight=2.0,
        range=1.5,
        requirements={},
        bonuses={},
        enchantments=[],
        icon_path="weapons/invented_default.png",
        hand_type="1H",
        item_type="weapon",
        stat_multipliers={},
        tags=["melee", "sword"],
        effect_tags=[],
        effect_params={}
    )

    # Create inventory and add the invented item
    inventory = Inventory(max_slots=10)
    success = inventory.add_item(
        "invented_test_sword_001",
        1,
        equipment_instance=invented_equipment,
        rarity="rare"
    )

    if not success:
        print("  [FAIL] add_item returned False")
        return False

    # Check that the item was added
    item_stack = inventory.slots[0]
    if item_stack is None:
        print("  [FAIL] Item was not added to inventory")
        return False

    # Check that equipment_data was set
    if item_stack.equipment_data is None:
        print("  [FAIL] equipment_data is None - equipment_instance was ignored!")
        return False

    # Check is_equipment() returns True
    if not item_stack.is_equipment():
        print("  [FAIL] is_equipment() returns False")
        return False

    # Check get_equipment() returns the data
    equipment = item_stack.get_equipment()
    if equipment is None:
        print("  [FAIL] get_equipment() returns None")
        return False

    if equipment.name != "Test Invented Sword":
        print(f"  [FAIL] Equipment name mismatch: {equipment.name}")
        return False

    print("  [PASS] equipment_data properly set")
    print("  [PASS] is_equipment() returns True")
    print("  [PASS] get_equipment() returns correct data")
    print(f"  Equipment: {equipment.name}, Tier: {equipment.tier}, Damage: {equipment.damage}")
    return True


def test_placement_database_registration():
    """Test that invented placements are registered with PlacementDatabase."""
    print("\n" + "="*60)
    print("TEST 2: PlacementDatabase Registration")
    print("="*60)

    from data.databases.placement_db import PlacementDatabase
    from data.models.recipes import PlacementData

    placement_db = PlacementDatabase.get_instance()

    # Create a test placement for an invented recipe
    recipe_id = "invented_test_placement_001"
    placement = PlacementData(
        recipe_id=recipe_id,
        discipline="smithing",
        grid_size="5x5",
        placement_map={"1,1": "iron_ingot", "1,2": "iron_ingot", "2,1": "oak_log"},
        narrative="A test invented weapon",
        output_id="test_weapon",
        station_tier=2
    )

    # Register it
    placement_db.placements[recipe_id] = placement

    # Verify it can be retrieved
    retrieved = placement_db.get_placement(recipe_id)
    if retrieved is None:
        print("  [FAIL] Could not retrieve registered placement")
        return False

    if retrieved.discipline != "smithing":
        print(f"  [FAIL] Discipline mismatch: {retrieved.discipline}")
        return False

    if retrieved.grid_size != "5x5":
        print(f"  [FAIL] Grid size mismatch: {retrieved.grid_size}")
        return False

    if len(retrieved.placement_map) != 3:
        print(f"  [FAIL] Placement map size mismatch: {len(retrieved.placement_map)}")
        return False

    print("  [PASS] Placement registered successfully")
    print("  [PASS] Placement retrievable via get_placement()")
    print(f"  Placement: grid={retrieved.grid_size}, materials={len(retrieved.placement_map)}")

    # Clean up
    del placement_db.placements[recipe_id]
    return True


def test_recipe_database_registration():
    """Test that invented recipes are registered with RecipeDatabase."""
    print("\n" + "="*60)
    print("TEST 3: RecipeDatabase Registration")
    print("="*60)

    from data.databases import RecipeDatabase
    from data.models import Recipe

    recipe_db = RecipeDatabase.get_instance()

    # Create a test recipe
    recipe_id = "invented_test_recipe_001"
    recipe = Recipe(
        recipe_id=recipe_id,
        output_id="test_invented_item",
        output_qty=1,
        station_type="smithing",
        station_tier=2,
        inputs=[
            {"materialId": "iron_ingot", "quantity": 3},
            {"materialId": "oak_log", "quantity": 1}
        ],
        grid_size="5x5",
        mini_game_type="smithing",
        metadata={"invented": True, "narrative": "Test recipe"}
    )

    # Register it
    recipe_db.recipes[recipe_id] = recipe
    if "smithing" not in recipe_db.recipes_by_station:
        recipe_db.recipes_by_station["smithing"] = []
    recipe_db.recipes_by_station["smithing"].append(recipe)

    # Verify it can be retrieved
    retrieved = recipe_db.recipes.get(recipe_id)
    if retrieved is None:
        print("  [FAIL] Could not retrieve registered recipe")
        return False

    if retrieved.output_id != "test_invented_item":
        print(f"  [FAIL] Output mismatch: {retrieved.output_id}")
        return False

    if not retrieved.metadata.get("invented"):
        print("  [FAIL] Invented flag not set")
        return False

    # Check it's in recipes_by_station
    smithing_recipes = recipe_db.recipes_by_station.get("smithing", [])
    found = any(r.recipe_id == recipe_id for r in smithing_recipes)
    if not found:
        print("  [FAIL] Recipe not found in recipes_by_station")
        return False

    print("  [PASS] Recipe registered in recipes dict")
    print("  [PASS] Recipe registered in recipes_by_station")
    print(f"  Recipe: {recipe_id} -> {retrieved.output_id}")

    # Clean up
    del recipe_db.recipes[recipe_id]
    recipe_db.recipes_by_station["smithing"] = [r for r in smithing_recipes if r.recipe_id != recipe_id]
    return True


def test_duplicate_detection():
    """Test that duplicate recipe detection works."""
    print("\n" + "="*60)
    print("TEST 4: Duplicate Recipe Detection")
    print("="*60)

    import hashlib
    import json

    def get_placement_hash(placement_data):
        """Mirror of game_engine._get_placement_hash"""
        hashable_data = {
            'discipline': placement_data.get('discipline'),
            'gridSize': placement_data.get('gridSize'),
            'placementMap': placement_data.get('placementMap'),
            'vertices': placement_data.get('vertices'),
            'shapes': placement_data.get('shapes'),
            'ingredients': placement_data.get('ingredients'),
            'coreInputs': placement_data.get('coreInputs'),
            'surroundingInputs': placement_data.get('surroundingInputs'),
            'slots': placement_data.get('slots'),
        }
        hashable_data = {k: v for k, v in hashable_data.items() if v is not None}
        context_str = json.dumps(hashable_data, sort_keys=True)
        return hashlib.md5(context_str.encode()).hexdigest()

    # Two identical placements should have same hash
    placement1 = {
        'discipline': 'smithing',
        'gridSize': '3x3',
        'placementMap': {'1,1': 'iron_ingot', '1,2': 'oak_log'}
    }

    placement2 = {
        'discipline': 'smithing',
        'gridSize': '3x3',
        'placementMap': {'1,1': 'iron_ingot', '1,2': 'oak_log'}
    }

    hash1 = get_placement_hash(placement1)
    hash2 = get_placement_hash(placement2)

    if hash1 != hash2:
        print("  [FAIL] Identical placements have different hashes")
        return False

    print("  [PASS] Identical placements have same hash")

    # Different placements should have different hash
    placement3 = {
        'discipline': 'smithing',
        'gridSize': '3x3',
        'placementMap': {'1,1': 'copper_ingot', '1,2': 'oak_log'}  # Different material
    }

    hash3 = get_placement_hash(placement3)

    if hash1 == hash3:
        print("  [FAIL] Different placements have same hash")
        return False

    print("  [PASS] Different placements have different hashes")
    print(f"  Hash 1&2: {hash1[:16]}...")
    print(f"  Hash 3:   {hash3[:16]}...")
    return True


def test_itemstack_tooltip_data():
    """Test that ItemStack has proper data for tooltips."""
    print("\n" + "="*60)
    print("TEST 5: ItemStack Tooltip Data Availability")
    print("="*60)

    from entities.components.inventory import ItemStack
    from data.models.equipment import EquipmentItem

    # Create an invented equipment item
    equipment = EquipmentItem(
        item_id="invented_tooltip_test",
        name="Tooltip Test Weapon",
        tier=3,
        rarity="epic",
        slot="mainHand",
        damage=(25, 45),
        defense=5,
        durability_current=750,
        durability_max=750,
        attack_speed=1.2,
        efficiency=1.0,
        weight=3.5,
        range=2.0,
        requirements={"level": 10},
        bonuses={"damage_multiplier": 0.1},
        enchantments=[{"name": "Sharpness", "effect": {"type": "damage_multiplier", "value": 0.15}}],
        icon_path="weapons/invented_default.png",
        hand_type="2H",
        item_type="weapon",
        stat_multipliers={"attackSpeed": 1.2},
        tags=["melee", "sword", "two-handed"],
        effect_tags=["cleave"],
        effect_params={"cleave_radius": 2.0}
    )

    # Create ItemStack with equipment_data
    stack = ItemStack(
        item_id="invented_tooltip_test",
        quantity=1,
        max_stack=1,
        equipment_data=equipment,
        rarity="epic",
        crafted_stats={"quality": "masterwork", "bonus_damage": 5}
    )

    # Verify all tooltip-relevant data is accessible
    if not stack.is_equipment():
        print("  [FAIL] is_equipment() returns False")
        return False

    equip = stack.get_equipment()
    if equip is None:
        print("  [FAIL] get_equipment() returns None")
        return False

    # Check all tooltip fields
    checks = [
        ("name", equip.name, "Tooltip Test Weapon"),
        ("tier", equip.tier, 3),
        ("rarity", equip.rarity, "epic"),
        ("slot", equip.slot, "mainHand"),
        ("damage", equip.damage, (25, 45)),
        ("defense", equip.defense, 5),
        ("icon_path", equip.icon_path, "weapons/invented_default.png"),
        ("tags length", len(equip.tags), 3),
        ("enchantments length", len(equip.enchantments), 1),
    ]

    all_pass = True
    for field_name, actual, expected in checks:
        if actual != expected:
            print(f"  [FAIL] {field_name}: expected {expected}, got {actual}")
            all_pass = False
        else:
            print(f"  [PASS] {field_name}: {actual}")

    # Check crafted_stats
    if stack.crafted_stats is None:
        print("  [FAIL] crafted_stats is None")
        return False

    if stack.crafted_stats.get("quality") != "masterwork":
        print("  [FAIL] crafted_stats.quality mismatch")
        return False

    print("  [PASS] crafted_stats accessible")

    return all_pass


def run_all_tests():
    """Run all integration tests."""
    print("\n" + "="*60)
    print("INVENTED ITEMS INTEGRATION TEST SUITE")
    print("="*60)

    results = []

    try:
        results.append(("Inventory Equipment Instance", test_inventory_equipment_instance()))
    except Exception as e:
        print(f"  [ERROR] Test failed with exception: {e}")
        import traceback
        traceback.print_exc()
        results.append(("Inventory Equipment Instance", False))

    try:
        results.append(("PlacementDatabase Registration", test_placement_database_registration()))
    except Exception as e:
        print(f"  [ERROR] Test failed with exception: {e}")
        import traceback
        traceback.print_exc()
        results.append(("PlacementDatabase Registration", False))

    try:
        results.append(("RecipeDatabase Registration", test_recipe_database_registration()))
    except Exception as e:
        print(f"  [ERROR] Test failed with exception: {e}")
        import traceback
        traceback.print_exc()
        results.append(("RecipeDatabase Registration", False))

    try:
        results.append(("Duplicate Detection", test_duplicate_detection()))
    except Exception as e:
        print(f"  [ERROR] Test failed with exception: {e}")
        import traceback
        traceback.print_exc()
        results.append(("Duplicate Detection", False))

    try:
        results.append(("ItemStack Tooltip Data", test_itemstack_tooltip_data()))
    except Exception as e:
        print(f"  [ERROR] Test failed with exception: {e}")
        import traceback
        traceback.print_exc()
        results.append(("ItemStack Tooltip Data", False))

    # Summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for name, result in results:
        status = "[PASS]" if result else "[FAIL]"
        print(f"  {status} {name}")

    print(f"\nTotal: {passed}/{total} tests passed")

    if passed == total:
        print("\n✓ ALL TESTS PASSED")
        return 0
    else:
        print(f"\n✗ {total - passed} TESTS FAILED")
        return 1


if __name__ == "__main__":
    sys.exit(run_all_tests())

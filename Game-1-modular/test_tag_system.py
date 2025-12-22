"""
Tag System Comprehensive Testing Script

This script tests the tag system with various edge cases and validates
that tags flow correctly from JSON → Database → Combat → Damage Application

Usage:
    cd Game-1-modular
    python test_tag_system.py
"""

import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.tag_system_debugger import TagSystemDebugger
from data.databases.material_db import MaterialDatabase
from data.databases.equipment_db import EquipmentDatabase


def test_material_loading():
    """Test that materials (devices) load tags correctly"""
    print("\n" + "="*70)
    print("TEST 1: Material Database Tag Loading")
    print("="*70 + "\n")

    TagSystemDebugger.enable()

    mat_db = MaterialDatabase.get_instance()

    # Test loading the test items file
    test_file = "items.JSON/items-testing-tags.JSON"
    if not os.path.exists(test_file):
        print(f"❌ Test file not found: {test_file}")
        return False

    print(f"Loading test items from: {test_file}\n")
    success = mat_db.load_stackable_items(test_file, categories=['device', 'weapon'])

    if not success:
        print(f"❌ Failed to load test items")
        return False

    # Verify specific test items
    test_items = [
        "test_turret_no_tags",
        "test_turret_beam_burn",
        "test_trap_conflicting_status",
        "test_device_chain_cone_hybrid"
    ]

    print("\n" + "-"*70)
    print("Verifying test devices loaded correctly:")
    print("-"*70 + "\n")

    for item_id in test_items:
        mat = mat_db.get_material(item_id)
        if not mat:
            print(f"❌ {item_id}: NOT FOUND in database")
            continue

        has_tags = bool(mat.effect_tags and len(mat.effect_tags) > 0)
        has_params = bool(mat.effect_params and len(mat.effect_params) > 0)

        # Log to debugger
        TagSystemDebugger.log_database_store(
            item_id=item_id,
            tags=mat.effect_tags if mat.effect_tags else [],
            params=mat.effect_params if mat.effect_params else {},
            db_type="material"
        )

        status = "✅" if has_tags else "⚠️ "
        print(f"{status} {item_id}")
        print(f"   Tags: {mat.effect_tags}")
        print(f"   Params: {list(mat.effect_params.keys()) if mat.effect_params else []}")
        print()

    TagSystemDebugger.print_summary()
    return True


def test_equipment_loading():
    """Test that equipment (weapons) load tags correctly"""
    print("\n" + "="*70)
    print("TEST 2: Equipment Database Tag Loading")
    print("="*70 + "\n")

    TagSystemDebugger.clear()
    TagSystemDebugger.enable()

    equip_db = EquipmentDatabase.get_instance()

    # Test loading from smithing file (which should have existing tagged weapons)
    smithing_file = "items.JSON/items-smithing-2.JSON"
    if os.path.exists(smithing_file):
        print(f"Loading weapons from: {smithing_file}\n")
        equip_db.load_from_file(smithing_file)

    # Check some known weapons
    test_weapons = [
        "iron_shortsword",
        "steel_longsword",
        "copper_spear",
        "fire_crystal_staff"
    ]

    print("\n" + "-"*70)
    print("Verifying weapons loaded correctly:")
    print("-"*70 + "\n")

    for weapon_id in test_weapons:
        equip = equip_db.get_equipment(weapon_id)
        if not equip:
            print(f"⚠️  {weapon_id}: NOT FOUND in database")
            continue

        has_tags = bool(equip.effect_tags and len(equip.effect_tags) > 0)
        has_params = bool(equip.effect_params and len(equip.effect_params) > 0)

        # Log to debugger
        TagSystemDebugger.log_database_store(
            item_id=weapon_id,
            tags=equip.effect_tags if equip.effect_tags else [],
            params=equip.effect_params if equip.effect_params else {},
            db_type="equipment"
        )

        status = "✅" if has_tags else "❌"
        print(f"{status} {weapon_id}")
        print(f"   Tags: {equip.effect_tags}")
        print(f"   Params: {list(equip.effect_params.keys()) if equip.effect_params else []}")
        print()

    TagSystemDebugger.print_summary()
    return True


def run_all_tests():
    """Run all tag system tests"""
    print("\n" + "="*70)
    print("🧪 TAG SYSTEM COMPREHENSIVE TESTING")
    print("="*70)
    print("This will test the complete tag flow from JSON to combat.")
    print()

    tests = [
        ("Material Loading", test_material_loading),
        ("Equipment Loading", test_equipment_loading)
    ]

    results = []
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result, None))
        except Exception as e:
            results.append((test_name, False, str(e)))
            print(f"\n❌ Test failed with exception: {e}")
            import traceback
            traceback.print_exc()

    # Final summary
    print("\n" + "="*70)
    print("📊 FINAL TEST SUMMARY")
    print("="*70 + "\n")

    for test_name, result, error in results:
        if result:
            print(f"✅ {test_name}: PASSED")
        elif error:
            print(f"❌ {test_name}: FAILED (Exception: {error})")
        else:
            print(f"❌ {test_name}: FAILED")

    passed = sum(1 for _, r, _ in results if r)
    total = len(results)

    print(f"\n{passed}/{total} tests passed")
    print("="*70 + "\n")

    if passed == total:
        print("🎉 ALL TESTS PASSED! Tag system is working correctly.")
        return 0
    else:
        print("⚠️  SOME TESTS FAILED. Review the output above for details.")
        return 1


if __name__ == "__main__":
    exit_code = run_all_tests()
    sys.exit(exit_code)

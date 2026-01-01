"""
Test Enemy Special Abilities JSON Loading

Tests that the EnemyDatabase correctly loads special abilities from the hostiles JSON file.

Usage:
    cd Game-1-modular
    python test_enemy_abilities_loading.py
"""

import sys
import os
import json

# Add parent directory (Game-1-modular) to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from Combat.enemy import EnemyDatabase


def test_ability_json_loading():
    """Test that abilities load correctly from JSON"""
    print("\n" + "="*70)
    print("TEST: Enemy Special Abilities JSON Loading")
    print("="*70 + "\n")

    # Test 1: Verify JSON file has abilities array
    print("="*70)
    print("TEST 1: Verify JSON Structure")
    print("="*70 + "\n")

    json_path = "Definitions.JSON/hostiles-1.JSON"
    print(f"1. Loading JSON file: {json_path}")

    with open(json_path, 'r') as f:
        data = json.load(f)

    abilities_in_json = data.get('abilities', [])
    print(f"   Found {len(abilities_in_json)} abilities in JSON")

    test1_pass = len(abilities_in_json) > 0
    if test1_pass:
        print(f"✅ TEST 1 PASSED: JSON contains {len(abilities_in_json)} abilities")
    else:
        print("❌ TEST 1 FAILED: No abilities found in JSON")
    print()

    # Test 2: Check ability structure
    print("="*70)
    print("TEST 2: Verify Ability Structure")
    print("="*70 + "\n")

    print("2. Checking first few abilities have required fields...")
    required_fields = ['abilityId', 'name', 'tags', 'effectParams', 'cooldown']
    test2_pass = True

    for i, ability in enumerate(abilities_in_json[:5]):
        ability_id = ability.get('abilityId', 'UNKNOWN')
        print(f"\n   Ability {i+1}: {ability_id}")

        missing_fields = []
        for field in required_fields:
            if field in ability:
                print(f"      ✓ {field}: {ability[field] if field != 'effectParams' else '...'}")
            else:
                print(f"      ❌ MISSING: {field}")
                missing_fields.append(field)
                test2_pass = False

        # Check trigger conditions (optional but should be present)
        triggers = ability.get('triggerConditions', {})
        print(f"      Triggers: {list(triggers.keys()) if triggers else 'None'}")

    if test2_pass:
        print("\n✅ TEST 2 PASSED: All checked abilities have required fields")
    else:
        print("\n❌ TEST 2 FAILED: Some abilities missing required fields")
    print()

    # Test 3: Load abilities through EnemyDatabase
    print("="*70)
    print("TEST 3: Load Abilities via EnemyDatabase")
    print("="*70 + "\n")

    print("3. Creating EnemyDatabase and loading from file...")
    db = EnemyDatabase()
    success = db.load_from_file(json_path)

    print(f"   Load success: {success}")
    print(f"   Enemies loaded: {len(db.enemies)}")

    test3_pass = success and len(db.enemies) > 0
    if test3_pass:
        print(f"✅ TEST 3 PASSED: Successfully loaded {len(db.enemies)} enemy definitions")
    else:
        print("❌ TEST 3 FAILED: Failed to load enemy definitions")
    print()

    # Test 4: Verify enemies have abilities assigned
    print("="*70)
    print("TEST 4: Verify Enemies Have Abilities")
    print("="*70 + "\n")

    print("4. Checking which enemies have special abilities...")
    enemies_with_abilities = []

    for enemy_id, enemy_def in db.enemies.items():
        if enemy_def.special_abilities:
            enemies_with_abilities.append((enemy_id, len(enemy_def.special_abilities)))
            print(f"\n   {enemy_def.name} ({enemy_id}):")
            for ability in enemy_def.special_abilities:
                print(f"      - {ability.name} ({ability.ability_id})")
                print(f"        Tags: {ability.tags}")
                print(f"        Cooldown: {ability.cooldown}s")
                print(f"        Health threshold: {ability.health_threshold}")

    print(f"\n   Total enemies with abilities: {len(enemies_with_abilities)}")

    test4_pass = len(enemies_with_abilities) > 0
    if test4_pass:
        print(f"✅ TEST 4 PASSED: {len(enemies_with_abilities)} enemies have special abilities")
    else:
        print("❌ TEST 4 FAILED: No enemies have special abilities assigned")
    print()

    # Test 5: Verify ability fields are correctly parsed
    print("="*70)
    print("TEST 5: Verify Ability Field Parsing")
    print("="*70 + "\n")

    print("5. Checking detailed ability parsing...")
    test5_pass = True

    # Find an enemy with abilities
    test_enemy = None
    for enemy_def in db.enemies.values():
        if enemy_def.special_abilities:
            test_enemy = enemy_def
            break

    if test_enemy:
        ability = test_enemy.special_abilities[0]
        print(f"\n   Testing ability: {ability.name}")
        print(f"      ability_id: {ability.ability_id} (type: {type(ability.ability_id).__name__})")
        print(f"      name: {ability.name} (type: {type(ability.name).__name__})")
        print(f"      cooldown: {ability.cooldown} (type: {type(ability.cooldown).__name__})")
        print(f"      tags: {ability.tags} (type: {type(ability.tags).__name__}, count: {len(ability.tags)})")
        print(f"      params: {list(ability.params.keys())} (type: {type(ability.params).__name__})")
        print(f"      health_threshold: {ability.health_threshold} (type: {type(ability.health_threshold).__name__})")
        print(f"      distance_min: {ability.distance_min} (type: {type(ability.distance_min).__name__})")
        print(f"      distance_max: {ability.distance_max} (type: {type(ability.distance_max).__name__})")
        print(f"      once_per_fight: {ability.once_per_fight} (type: {type(ability.once_per_fight).__name__})")

        # Verify types
        checks = [
            isinstance(ability.ability_id, str),
            isinstance(ability.name, str),
            isinstance(ability.cooldown, (int, float)),
            isinstance(ability.tags, list),
            isinstance(ability.params, dict),
            isinstance(ability.health_threshold, (int, float)),
            isinstance(ability.distance_min, (int, float)),
            isinstance(ability.distance_max, (int, float)),
            isinstance(ability.once_per_fight, bool),
        ]

        test5_pass = all(checks)
        if test5_pass:
            print("\n✅ TEST 5 PASSED: All ability fields have correct types")
        else:
            print("\n❌ TEST 5 FAILED: Some fields have incorrect types")
    else:
        test5_pass = False
        print("\n❌ TEST 5 FAILED: Could not find enemy with abilities to test")
    print()

    # Summary
    print("="*70)
    print("TEST SUMMARY")
    print("="*70 + "\n")

    all_passed = test1_pass and test2_pass and test3_pass and test4_pass and test5_pass

    print(f"Test 1 (JSON Structure):          {'✅ PASS' if test1_pass else '❌ FAIL'}")
    print(f"Test 2 (Ability Fields):          {'✅ PASS' if test2_pass else '❌ FAIL'}")
    print(f"Test 3 (Database Loading):        {'✅ PASS' if test3_pass else '❌ FAIL'}")
    print(f"Test 4 (Enemy Abilities):         {'✅ PASS' if test4_pass else '❌ FAIL'}")
    print(f"Test 5 (Field Parsing):           {'✅ PASS' if test5_pass else '❌ FAIL'}")
    print()

    if all_passed:
        print("🎉 ALL TESTS PASSED! Enemy ability JSON loading working correctly!")
    else:
        print("⚠️  SOME TESTS FAILED - Review implementation")
    print()

    return all_passed


if __name__ == "__main__":
    try:
        success = test_ability_json_loading()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n❌ TEST CRASHED: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

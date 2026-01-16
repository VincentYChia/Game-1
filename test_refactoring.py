#!/usr/bin/env python3
"""
Comprehensive test script to validate skills and alchemy refactoring.
Tests:
1. Skills database loads with numeric mana/cooldown
2. Alchemy items load with effectTags/effectParams
3. PotionEffectExecutor can be imported and instantiated
4. Skill cost calculations work correctly
5. JSON validation for all modified files
"""

import sys
import os
import json
from pathlib import Path

# Add Game-1-modular to path
sys.path.insert(0, '/home/user/Game-1/Game-1-modular')

def test_json_validity():
    """Test all JSON files are valid"""
    print("\n=== Testing JSON File Validity ===")

    json_files = [
        '/home/user/Game-1/Game-1-modular/Skills/skills-skills-1.JSON',
        '/home/user/Game-1/Game-1-modular/items.JSON/items-alchemy-1.JSON',
        '/home/user/Game-1/Scaled JSON Development/json_templates/alchemy_items.json',
        '/home/user/Game-1/Scaled JSON Development/json_templates/skills.json',
        '/home/user/Game-1/Scaled JSON Development/LLM Training Data/system3_alchemy_recipe_to_item/full_dataset.json',
    ]

    for filepath in json_files:
        try:
            with open(filepath, 'r') as f:
                data = json.load(f)
            print(f"✓ {Path(filepath).name}: Valid JSON")
        except json.JSONDecodeError as e:
            print(f"✗ {Path(filepath).name}: INVALID - {e}")
            return False
        except FileNotFoundError:
            print(f"✗ {Path(filepath).name}: File not found")
            return False

    return True


def test_skills_database():
    """Test skills database loads and handles numeric costs"""
    print("\n=== Testing Skills Database ===")

    try:
        from data.databases.skill_db import SkillDatabase

        # Load database
        skill_db = SkillDatabase.get_instance()
        skill_db.load_from_file('/home/user/Game-1/Game-1-modular/Skills/skills-skills-1.JSON')

        print(f"✓ Loaded {len(skill_db.skills)} skills")

        # Test specific skills with numeric costs
        test_cases = [
            ('sprint', 20, 20),  # Low cost utility
            ('combat_strike', 50, 30),  # Standard combat
            ('omega_strike', 150, 600),  # Ultimate skill
        ]

        for skill_id, expected_mana, expected_cooldown in test_cases:
            if skill_id in skill_db.skills:
                skill = skill_db.skills[skill_id]
                mana = skill_db.get_mana_cost(skill.cost.mana)
                cooldown = skill_db.get_cooldown_seconds(skill.cost.cooldown)

                # Check if numeric values are preserved
                mana_match = mana == expected_mana
                cooldown_match = cooldown == expected_cooldown

                if mana_match and cooldown_match:
                    print(f"✓ {skill_id}: mana={mana}, cooldown={cooldown}s")
                else:
                    print(f"✗ {skill_id}: Expected mana={expected_mana}, cooldown={expected_cooldown}s, got mana={mana}, cooldown={cooldown}s")
                    return False
            else:
                print(f"✗ {skill_id}: Not found in database")
                return False

        # Test backward compatibility with string enums
        test_mana = skill_db.get_mana_cost("moderate")
        test_cooldown = skill_db.get_cooldown_seconds("long")
        print(f"✓ Backward compatibility: 'moderate' mana={test_mana}, 'long' cooldown={test_cooldown}s")

        return True

    except Exception as e:
        print(f"✗ Error loading skills database: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_alchemy_items():
    """Test alchemy items load with effectTags/effectParams"""
    print("\n=== Testing Alchemy Items ===")

    try:
        from data.databases.material_db import MaterialDatabase

        # Load database
        mat_db = MaterialDatabase.get_instance()
        mat_db.load_from_file('/home/user/Game-1/Game-1-modular/items.JSON/items-alchemy-1.JSON')

        print(f"✓ Loaded {len(mat_db.materials)} materials")

        # Test specific potions with new tag system
        test_potions = [
            ('minor_health_potion', ['healing', 'instant', 'self'], {'heal_amount': 50}),
            ('regeneration_tonic', ['healing', 'over_time', 'self'], {'heal_per_second': 5.0, 'duration': 60.0}),
            ('strength_elixir', ['buff', 'self'], {'buff_type': 'strength', 'buff_value': 0.20, 'duration': 300.0}),
        ]

        for item_id, expected_tags, expected_params_subset in test_potions:
            if item_id in mat_db.materials:
                item = mat_db.materials[item_id]

                # Check effectTags
                if hasattr(item, 'effect_tags') and item.effect_tags == expected_tags:
                    print(f"✓ {item_id}: effectTags={item.effect_tags}")
                else:
                    actual_tags = getattr(item, 'effect_tags', None)
                    print(f"✗ {item_id}: Expected tags={expected_tags}, got {actual_tags}")
                    return False

                # Check effectParams
                if hasattr(item, 'effect_params'):
                    params = item.effect_params
                    # Check that expected params are present with correct values
                    params_match = all(
                        key in params and params[key] == value
                        for key, value in expected_params_subset.items()
                    )
                    if params_match:
                        print(f"✓ {item_id}: effectParams contains {expected_params_subset}")
                    else:
                        print(f"✗ {item_id}: effectParams mismatch. Expected subset {expected_params_subset}, got {params}")
                        return False
                else:
                    print(f"✗ {item_id}: Missing effect_params attribute")
                    return False
            else:
                print(f"✗ {item_id}: Not found in database")
                return False

        return True

    except Exception as e:
        print(f"✗ Error loading alchemy items: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_potion_executor():
    """Test PotionEffectExecutor can be imported and instantiated"""
    print("\n=== Testing PotionEffectExecutor ===")

    try:
        from systems.potion_system import PotionEffectExecutor, get_potion_executor

        # Test singleton
        executor1 = get_potion_executor()
        executor2 = get_potion_executor()

        if executor1 is executor2:
            print("✓ PotionEffectExecutor singleton pattern works")
        else:
            print("✗ PotionEffectExecutor singleton broken")
            return False

        # Test instantiation
        executor = PotionEffectExecutor()
        print("✓ PotionEffectExecutor can be instantiated")

        # Check methods exist
        required_methods = ['apply_potion_effect', '_apply_healing', '_apply_buff', '_apply_resistance', '_apply_utility']
        for method in required_methods:
            if hasattr(executor, method):
                print(f"✓ Method '{method}' exists")
            else:
                print(f"✗ Method '{method}' missing")
                return False

        return True

    except Exception as e:
        print(f"✗ Error testing PotionEffectExecutor: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_scaled_json_templates():
    """Test Scaled JSON Development templates are valid and contain new fields"""
    print("\n=== Testing Scaled JSON Development Templates ===")

    # Test alchemy template
    try:
        with open('/home/user/Game-1/Scaled JSON Development/json_templates/alchemy_items.json', 'r') as f:
            alchemy_template = json.load(f)

        # Check for NEW_TAG_SYSTEM in _meta
        if 'NEW_TAG_SYSTEM' in alchemy_template.get('_meta', {}):
            print("✓ alchemy_items.json: NEW_TAG_SYSTEM documented in _meta")
        else:
            print("✗ alchemy_items.json: Missing NEW_TAG_SYSTEM in _meta")
            return False

        # Check for effectTags in _all_possible_values
        if 'effectTags' in alchemy_template.get('_all_possible_values', {}):
            print("✓ alchemy_items.json: effectTags in _all_possible_values")
        else:
            print("✗ alchemy_items.json: Missing effectTags in _all_possible_values")
            return False

        # Check for effectParams in _all_possible_values
        if 'effectParams' in alchemy_template.get('_all_possible_values', {}):
            print("✓ alchemy_items.json: effectParams in _all_possible_values")
        else:
            print("✗ alchemy_items.json: Missing effectParams in _all_possible_values")
            return False

    except Exception as e:
        print(f"✗ Error testing alchemy template: {e}")
        return False

    # Test skills template
    try:
        with open('/home/user/Game-1/Scaled JSON Development/json_templates/skills.json', 'r') as f:
            skills_template = json.load(f)

        # Check for NEW_NUMERIC_COST_SYSTEM in _meta
        if 'NEW_NUMERIC_COST_SYSTEM' in skills_template.get('_meta', {}):
            print("✓ skills.json: NEW_NUMERIC_COST_SYSTEM documented in _meta")
        else:
            print("✗ skills.json: Missing NEW_NUMERIC_COST_SYSTEM in _meta")
            return False

        # Check cost.mana has numeric values
        cost_mana = skills_template.get('_all_possible_values', {}).get('cost.mana', {})
        if 'values' in cost_mana and isinstance(cost_mana['values'][0], (int, float)):
            print("✓ skills.json: cost.mana contains numeric values")
        else:
            print("✗ skills.json: cost.mana missing numeric values")
            return False

        # Check cost.cooldown has numeric values
        cost_cooldown = skills_template.get('_all_possible_values', {}).get('cost.cooldown', {})
        if 'values' in cost_cooldown and isinstance(cost_cooldown['values'][0], (int, float)):
            print("✓ skills.json: cost.cooldown contains numeric values")
        else:
            print("✗ skills.json: cost.cooldown missing numeric values")
            return False

    except Exception as e:
        print(f"✗ Error testing skills template: {e}")
        return False

    return True


def main():
    """Run all tests"""
    print("=" * 60)
    print("REFACTORING VALIDATION TEST SUITE")
    print("=" * 60)

    results = []

    # Run all tests
    results.append(("JSON Validity", test_json_validity()))
    results.append(("Skills Database", test_skills_database()))
    results.append(("Alchemy Items", test_alchemy_items()))
    results.append(("Potion Executor", test_potion_executor()))
    results.append(("Scaled JSON Templates", test_scaled_json_templates()))

    # Print summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for test_name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{status:8} {test_name}")

    print(f"\nTotal: {passed}/{total} tests passed")

    if passed == total:
        print("\n✓ ALL TESTS PASSED - Refactoring is functional!")
        return 0
    else:
        print(f"\n✗ {total - passed} TEST(S) FAILED - Review errors above")
        return 1


if __name__ == '__main__':
    sys.exit(main())

#!/usr/bin/env python3
"""
JSON Schema validation test - no pygame dependencies.
Tests that all refactored JSON files have correct structure.
"""

import json
from pathlib import Path
from typing import Dict, List, Any


def validate_skills_json():
    """Validate skills JSON has numeric mana/cooldown"""
    print("\n=== Validating Skills JSON ===")

    filepath = '/home/user/Game-1/Game-1-modular/Skills/skills-skills-1.JSON'

    with open(filepath, 'r') as f:
        data = json.load(f)

    # Skills are in the 'skills' key
    skills_data = data.get('skills', [])

    if not isinstance(skills_data, list):
        print("✗ Skills data is not a list")
        return False

    print(f"✓ Found {len(skills_data)} skills")

    # Test specific skills
    skill_tests = {
        'sprint': {'mana': 20, 'cooldown': 20},
        'combat_strike': {'mana': 50, 'cooldown': 30},
        'omega_strike': {'mana': 150, 'cooldown': 600},
    }

    skills_by_id = {skill['skillId']: skill for skill in skills_data if 'skillId' in skill}

    for skill_id, expected_costs in skill_tests.items():
        if skill_id not in skills_by_id:
            print(f"✗ Skill '{skill_id}' not found")
            return False

        skill = skills_by_id[skill_id]
        cost = skill.get('cost', {})
        actual_mana = cost.get('mana')
        actual_cooldown = cost.get('cooldown')

        # Check types are numeric
        if not isinstance(actual_mana, (int, float)):
            print(f"✗ {skill_id}: mana is not numeric (type: {type(actual_mana)})")
            return False

        if not isinstance(actual_cooldown, (int, float)):
            print(f"✗ {skill_id}: cooldown is not numeric (type: {type(actual_cooldown)})")
            return False

        # Check values match
        if actual_mana == expected_costs['mana'] and actual_cooldown == expected_costs['cooldown']:
            print(f"✓ {skill_id}: mana={actual_mana}, cooldown={actual_cooldown}")
        else:
            print(f"✗ {skill_id}: Expected mana={expected_costs['mana']}, cooldown={expected_costs['cooldown']}, got mana={actual_mana}, cooldown={actual_cooldown}")
            return False

    # Validate all skills have numeric costs
    errors = []
    for skill in skills_data:
        skill_id = skill.get('skillId', 'unknown')
        cost = skill.get('cost', {})
        mana = cost.get('mana')
        cooldown = cost.get('cooldown')

        if mana is not None and not isinstance(mana, (int, float)):
            errors.append(f"{skill_id}: mana type is {type(mana)}")

        if cooldown is not None and not isinstance(cooldown, (int, float)):
            errors.append(f"{skill_id}: cooldown type is {type(cooldown)}")

    if errors:
        print(f"✗ Found {len(errors)} type errors:")
        for error in errors[:5]:  # Show first 5
            print(f"  - {error}")
        return False

    print(f"✓ All {len(skills_data)} skills have valid numeric mana/cooldown")
    return True


def validate_alchemy_json():
    """Validate alchemy JSON has effectTags and effectParams"""
    print("\n=== Validating Alchemy JSON ===")

    filepath = '/home/user/Game-1/Game-1-modular/items.JSON/items-alchemy-1.JSON'

    with open(filepath, 'r') as f:
        data = json.load(f)

    # Collect all items from different categories
    items_data = []
    for key, value in data.items():
        if key != 'metadata' and isinstance(value, list):
            items_data.extend(value)

    if not items_data:
        print("✗ No alchemy items found")
        return False

    print(f"✓ Found {len(items_data)} alchemy items")

    # Test specific potions
    potion_tests = {
        'minor_health_potion': {
            'effectTags': ['healing', 'instant', 'self'],
            'effectParams': {'heal_amount': 50}
        },
        'regeneration_tonic': {
            'effectTags': ['healing', 'over_time', 'self'],
            'effectParams': {'heal_per_second': 5.0, 'duration': 60.0}
        },
        'strength_elixir': {
            'effectTags': ['buff', 'self'],
            'effectParams': {'buff_type': 'strength', 'buff_value': 0.20, 'duration': 300.0}
        },
        'fire_resistance_potion': {
            'effectTags': ['resistance', 'self'],
            'effectParams': {'resistance_type': 'fire', 'damage_reduction': 0.5, 'duration': 360.0}
        },
        'efficiency_oil': {
            'effectTags': ['utility', 'self'],
            'effectParams': {'utility_type': 'efficiency', 'utility_value': 0.15, 'duration': 3600.0}
        }
    }

    items_by_id = {item['itemId']: item for item in items_data if 'itemId' in item}

    for item_id, expected in potion_tests.items():
        if item_id not in items_by_id:
            print(f"✗ Item '{item_id}' not found")
            return False

        item = items_by_id[item_id]

        # Check effectTags
        actual_tags = item.get('effectTags')
        if actual_tags != expected['effectTags']:
            print(f"✗ {item_id}: effectTags mismatch")
            print(f"  Expected: {expected['effectTags']}")
            print(f"  Actual: {actual_tags}")
            return False

        # Check effectParams
        actual_params = item.get('effectParams', {})
        for key, value in expected['effectParams'].items():
            if key not in actual_params:
                print(f"✗ {item_id}: Missing effectParams key '{key}'")
                return False
            if actual_params[key] != value:
                print(f"✗ {item_id}: effectParams['{key}'] = {actual_params[key]}, expected {value}")
                return False

        print(f"✓ {item_id}: effectTags and effectParams valid")

    # Count items with new tag system
    tagged_items = sum(1 for item in items_data if 'effectTags' in item and 'effectParams' in item)
    print(f"✓ {tagged_items}/{len(items_data)} items have effectTags/effectParams")

    if tagged_items < 16:  # We converted 16 consumables
        print(f"⚠ Warning: Expected at least 16 items with tags, found {tagged_items}")

    return True


def validate_training_data():
    """Validate system3 training data has new fields"""
    print("\n=== Validating Training Data ===")

    files = [
        '/home/user/Game-1/Scaled JSON Development/LLM Training Data/system3_alchemy_recipe_to_item/full_dataset.json',
        '/home/user/Game-1/Scaled JSON Development/LLM Training Data/system3_alchemy_recipe_to_item/train.json',
        '/home/user/Game-1/Scaled JSON Development/LLM Training Data/system3_alchemy_recipe_to_item/val.json',
    ]

    for filepath in files:
        filename = Path(filepath).name

        with open(filepath, 'r') as f:
            data = json.load(f)

        if not isinstance(data, list):
            print(f"✗ {filename}: Not a list")
            return False

        # Check all output items have effectTags and effectParams
        items_with_tags = 0
        for entry in data:
            output = entry.get('output', {})
            if 'effectTags' in output and 'effectParams' in output:
                items_with_tags += 1

        if items_with_tags == len(data):
            print(f"✓ {filename}: All {len(data)} items have effectTags/effectParams")
        else:
            print(f"✗ {filename}: Only {items_with_tags}/{len(data)} items have tags")
            return False

    return True


def validate_templates():
    """Validate JSON templates have new documentation"""
    print("\n=== Validating Templates ===")

    # Alchemy template
    with open('/home/user/Game-1/Scaled JSON Development/json_templates/alchemy_items.json', 'r') as f:
        alchemy = json.load(f)

    checks = [
        ('_meta.NEW_TAG_SYSTEM', 'NEW_TAG_SYSTEM' in alchemy.get('_meta', {})),
        ('_all_possible_values.effectTags', 'effectTags' in alchemy.get('_all_possible_values', {})),
        ('_all_possible_values.effectParams', 'effectParams' in alchemy.get('_all_possible_values', {})),
    ]

    for check_name, result in checks:
        if result:
            print(f"✓ alchemy_items.json: {check_name} present")
        else:
            print(f"✗ alchemy_items.json: {check_name} missing")
            return False

    # Skills template
    with open('/home/user/Game-1/Scaled JSON Development/json_templates/skills.json', 'r') as f:
        skills = json.load(f)

    checks = [
        ('_meta.NEW_NUMERIC_COST_SYSTEM', 'NEW_NUMERIC_COST_SYSTEM' in skills.get('_meta', {})),
        ('cost.mana is numeric', isinstance(skills.get('_all_possible_values', {}).get('cost.mana', {}).get('values', [None])[0], (int, float))),
        ('cost.cooldown is numeric', isinstance(skills.get('_all_possible_values', {}).get('cost.cooldown', {}).get('values', [None])[0], (int, float))),
    ]

    for check_name, result in checks:
        if result:
            print(f"✓ skills.json: {check_name}")
        else:
            print(f"✗ skills.json: {check_name} failed")
            return False

    return True


def validate_main_templates():
    """Validate main Definitions.JSON/JSON Templates"""
    print("\n=== Validating Definitions.JSON/JSON Templates ===")

    filepath = '/home/user/Game-1/Game-1-modular/Definitions.JSON/JSON Templates'

    with open(filepath, 'r') as f:
        templates = json.load(f)

    # Check for alchemy_potions section inside MATERIAL_TEMPLATE
    material_template = templates.get('MATERIAL_TEMPLATE', {})

    if 'alchemy_potions' in material_template:
        print("✓ MATERIAL_TEMPLATE.alchemy_potions present")

        alchemy = material_template['alchemy_potions']
        required_keys = ['effectTags', 'effectParams', 'tag_guide']

        for key in required_keys:
            if key in alchemy:
                print(f"✓ alchemy_potions.{key} present")
            else:
                print(f"✗ alchemy_potions.{key} missing")
                return False
    else:
        print("✗ MATERIAL_TEMPLATE.alchemy_potions missing")
        return False

    # Check for SKILLS_TEMPLATE section
    if 'SKILLS_TEMPLATE' in templates:
        print("✓ SKILLS_TEMPLATE present")

        skills = templates['SKILLS_TEMPLATE']
        if 'cost_ranges' in skills:
            print("✓ SKILLS_TEMPLATE.cost_ranges present")
        else:
            print("✗ SKILLS_TEMPLATE.cost_ranges missing")
            return False
    else:
        print("✗ SKILLS_TEMPLATE missing")
        return False

    return True


def main():
    """Run all validation tests"""
    print("=" * 60)
    print("JSON SCHEMA VALIDATION TEST SUITE")
    print("=" * 60)

    results = []

    # Run all tests
    results.append(("Skills JSON Schema", validate_skills_json()))
    results.append(("Alchemy JSON Schema", validate_alchemy_json()))
    results.append(("Training Data Schema", validate_training_data()))
    results.append(("Template Schema", validate_templates()))
    results.append(("Main Templates", validate_main_templates()))

    # Print summary
    print("\n" + "=" * 60)
    print("VALIDATION SUMMARY")
    print("=" * 60)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for test_name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{status:8} {test_name}")

    print(f"\nTotal: {passed}/{total} tests passed")

    if passed == total:
        print("\n✓ ALL SCHEMA VALIDATIONS PASSED!")
        print("JSON files are correctly structured for the refactored system.")
        return 0
    else:
        print(f"\n✗ {total - passed} VALIDATION(S) FAILED")
        return 1


if __name__ == '__main__':
    import sys
    sys.exit(main())

#!/usr/bin/env python3
"""
Update validation libraries for refactored alchemy and skills systems.
Adds new fields and updates existing ones to match the new schemas.
"""

import json
from pathlib import Path


def update_alchemy_validation(validation_data):
    """Add effectTags and effectParams to alchemy validation"""
    print("\n=== Updating Alchemy Validation ===")

    alchemy = validation_data.get('alchemy_items', {})

    # Add effectTags enumeration
    alchemy['effectTags'] = {
        "field_name": "effectTags",
        "description": "Array of effect tags defining potion behavior",
        "values": [
            ["healing", "instant", "self"],
            ["healing", "over_time", "self"],
            ["mana_restore", "instant", "self"],
            ["mana_restore", "over_time", "self"],
            ["buff", "self"],
            ["resistance", "self"],
            ["utility", "self"]
        ],
        "tag_categories": {
            "effect_types": ["healing", "mana_restore", "buff", "resistance", "utility"],
            "modifiers": ["instant", "over_time"],
            "targets": ["self"]
        }
    }

    # Add effectParams with statistical ranges
    if 'stat_ranges' not in alchemy:
        alchemy['stat_ranges'] = {}

    # Healing parameters
    alchemy['stat_ranges']['effectParams.heal_amount'] = {
        "1": {"min": 50.0, "max": 50.0, "mean": 50.0, "median": 50.0, "count": 1, "note": "Minor potions"},
        "2": {"min": 100.0, "max": 100.0, "mean": 100.0, "median": 100.0, "count": 1, "note": "Standard potions"},
        "3": {"min": 200.0, "max": 200.0, "mean": 200.0, "median": 200.0, "count": 1, "note": "Greater potions"}
    }

    alchemy['stat_ranges']['effectParams.heal_per_second'] = {
        "3": {"min": 5.0, "max": 10.0, "mean": 7.5, "median": 7.5, "count": 1, "note": "Regeneration effects"}
    }

    alchemy['stat_ranges']['effectParams.duration'] = {
        "2": {"min": 60.0, "max": 300.0, "mean": 180.0, "median": 180.0, "count": 3, "note": "Buff/regen durations"},
        "3": {"min": 300.0, "max": 3600.0, "mean": 1950.0, "median": 1950.0, "count": 3, "note": "Long-duration effects"}
    }

    # Mana restore parameters
    alchemy['stat_ranges']['effectParams.mana_amount'] = {
        "1": {"min": 50.0, "max": 50.0, "mean": 50.0, "median": 50.0, "count": 1},
        "2": {"min": 100.0, "max": 100.0, "mean": 100.0, "median": 100.0, "count": 1},
        "3": {"min": 200.0, "max": 200.0, "mean": 200.0, "median": 200.0, "count": 1}
    }

    # Buff parameters
    alchemy['stat_ranges']['effectParams.buff_value'] = {
        "2": {"min": 0.15, "max": 0.25, "mean": 0.20, "median": 0.20, "count": 3, "note": "15-25% stat buffs"},
        "3": {"min": 0.25, "max": 0.35, "mean": 0.30, "median": 0.30, "count": 2, "note": "25-35% stat buffs"}
    }

    # Resistance parameters
    alchemy['stat_ranges']['effectParams.damage_reduction'] = {
        "2": {"min": 0.5, "max": 0.5, "mean": 0.5, "median": 0.5, "count": 3, "note": "50% damage reduction"}
    }

    # Utility parameters
    alchemy['stat_ranges']['effectParams.utility_value'] = {
        "2": {"min": 0.15, "max": 0.20, "mean": 0.175, "median": 0.175, "count": 3, "note": "15-20% utility bonus"}
    }

    # Add buff_type enum
    if 'enums' not in alchemy:
        alchemy['enums'] = {}

    alchemy['enums']['effectParams.buff_type'] = {
        "field_name": "effectParams.buff_type",
        "values": ["strength", "defense", "speed", "max_hp", "max_mana"]
    }

    # Add resistance_type enum
    alchemy['enums']['effectParams.resistance_type'] = {
        "field_name": "effectParams.resistance_type",
        "values": ["fire", "ice", "lightning", "poison", "elemental"]
    }

    # Add utility_type enum
    alchemy['enums']['effectParams.utility_type'] = {
        "field_name": "effectParams.utility_type",
        "values": ["efficiency", "armor", "weapon"]
    }

    print("✓ Added effectTags field")
    print("✓ Added effectParams statistical ranges")
    print("✓ Added buff_type, resistance_type, utility_type enums")

    validation_data['alchemy_items'] = alchemy


def update_skills_validation(validation_data):
    """Update skills validation for numeric mana/cooldown"""
    print("\n=== Updating Skills Validation ===")

    skills = validation_data.get('skills', {})

    # Update cost.mana to numeric ranges
    if 'stat_ranges' not in skills:
        skills['stat_ranges'] = {}

    skills['stat_ranges']['cost.mana'] = {
        "1": {"min": 20.0, "max": 50.0, "mean": 35.0, "median": 35.0, "count": 10, "note": "Low-cost utility skills"},
        "2": {"min": 50.0, "max": 80.0, "mean": 65.0, "median": 65.0, "count": 12, "note": "Standard combat skills"},
        "3": {"min": 90.0, "max": 120.0, "mean": 105.0, "median": 105.0, "count": 6, "note": "Powerful tier 2 skills"},
        "4": {"min": 120.0, "max": 150.0, "mean": 135.0, "median": 135.0, "count": 2, "note": "Ultimate tier 3+ skills"}
    }

    skills['stat_ranges']['cost.cooldown'] = {
        "1": {"min": 20.0, "max": 60.0, "mean": 40.0, "median": 40.0, "count": 8, "note": "Quick utility skills"},
        "2": {"min": 150.0, "max": 240.0, "mean": 195.0, "median": 195.0, "count": 14, "note": "Standard combat skills"},
        "3": {"min": 360.0, "max": 480.0, "mean": 420.0, "median": 420.0, "count": 6, "note": "Powerful defensive skills"},
        "4": {"min": 500.0, "max": 600.0, "mean": 550.0, "median": 550.0, "count": 2, "note": "Ultimate abilities"}
    }

    # Remove old string enum validation if it exists
    if 'enums' in skills:
        if 'cost.mana' in skills['enums']:
            del skills['enums']['cost.mana']
            print("✓ Removed old string enum for cost.mana")
        if 'cost.cooldown' in skills['enums']:
            del skills['enums']['cost.cooldown']
            print("✓ Removed old string enum for cost.cooldown")

    print("✓ Added numeric cost.mana ranges (20-150)")
    print("✓ Added numeric cost.cooldown ranges (20-600)")

    validation_data['skills'] = skills


def main():
    """Update validation libraries"""
    filepath = Path('/home/user/Game-1/Scaled JSON Development/LLM Training Data/Fewshot_llm/config/validation_libraries.json')

    print("=" * 60)
    print("VALIDATION LIBRARY UPDATE")
    print("=" * 60)

    # Backup original
    backup_path = filepath.with_suffix('.json.backup')
    with open(filepath, 'r') as f:
        original_data = json.load(f)

    with open(backup_path, 'w') as f:
        json.dump(original_data, f, indent=2)
    print(f"\n✓ Created backup at {backup_path.name}")

    # Load and update
    validation_data = original_data.copy()

    update_alchemy_validation(validation_data)
    update_skills_validation(validation_data)

    # Write updated file
    with open(filepath, 'w') as f:
        json.dump(validation_data, f, indent=2)

    print(f"\n✓ Updated {filepath.name}")

    # Verify JSON is valid
    with open(filepath, 'r') as f:
        json.load(f)
    print("✓ Validated updated JSON")

    print("\n" + "=" * 60)
    print("UPDATE COMPLETE")
    print("=" * 60)
    print("\nChanges made:")
    print("  - Added alchemy effectTags array validation")
    print("  - Added alchemy effectParams statistical ranges")
    print("  - Added buff_type, resistance_type, utility_type enums")
    print("  - Updated skills cost.mana to numeric ranges (20-150)")
    print("  - Updated skills cost.cooldown to numeric ranges (20-600)")
    print("  - Removed old string enum validation for skills costs")


if __name__ == '__main__':
    main()

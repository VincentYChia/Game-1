#!/usr/bin/env python3
"""
Test rarity bonus logic without pygame
"""
import json

def test_rarity_calculation():
    """Test the rarity bonus calculation logic"""
    print("=" * 80)
    print("TESTING RARITY BONUS CALCULATION")
    print("=" * 80)

    # Rarity levels
    RARITY_LEVELS = {
        "common": 0,
        "uncommon": 1,
        "rare": 2,
        "epic": 3,
        "legendary": 4
    }

    def calculate_rarity_bonus(inputs, material_rarities):
        """Calculate rarity bonus multiplier"""
        total_bonus = 0.0

        for inp in inputs:
            mat_id = inp.get('materialId', '')
            quantity = inp.get('quantity', 0)

            # Get material rarity
            rarity = material_rarities.get(mat_id, 'common')
            rarity_level = RARITY_LEVELS.get(rarity, 0)

            # Calculate bonus: rarity_level * 2.5% * quantity
            bonus_per_item = rarity_level * 0.025
            total_bonus += bonus_per_item * quantity

        # Return as multiplier (1.0 + bonus percentage)
        multiplier = 1.0 + total_bonus
        return multiplier, total_bonus

    # Test cases
    test_cases = [
        {
            'name': 'All common materials (no bonus)',
            'inputs': [
                {'materialId': 'iron_ingot', 'quantity': 5},
                {'materialId': 'oak_plank', 'quantity': 2}
            ],
            'rarities': {
                'iron_ingot': 'common',
                'oak_plank': 'common'
            },
            'expected_bonus': 0.0,
            'expected_mult': 1.0
        },
        {
            'name': '1 rare + 2 epic (your example)',
            'inputs': [
                {'materialId': 'steel_ingot', 'quantity': 1},
                {'materialId': 'mithril_ingot', 'quantity': 2}
            ],
            'rarities': {
                'steel_ingot': 'rare',
                'mithril_ingot': 'epic'
            },
            'expected_bonus': 0.20,  # 1*2*2.5% + 2*3*2.5% = 5% + 15% = 20%
            'expected_mult': 1.20
        },
        {
            'name': 'Mixed rarities (6 common + 1 rare + 2 epic)',
            'inputs': [
                {'materialId': 'iron_ingot', 'quantity': 6},
                {'materialId': 'steel_ingot', 'quantity': 1},
                {'materialId': 'mithril_ingot', 'quantity': 2}
            ],
            'rarities': {
                'iron_ingot': 'common',
                'steel_ingot': 'rare',
                'mithril_ingot': 'epic'
            },
            'expected_bonus': 0.20,
            'expected_mult': 1.20
        },
        {
            'name': 'All legendary',
            'inputs': [
                {'materialId': 'dragonsteel', 'quantity': 5}
            ],
            'rarities': {
                'dragonsteel': 'legendary'
            },
            'expected_bonus': 0.50,  # 5 * 4 * 2.5% = 50%
            'expected_mult': 1.50
        }
    ]

    # Run tests
    all_passed = True
    for test in test_cases:
        mult, bonus = calculate_rarity_bonus(test['inputs'], test['rarities'])
        passed = abs(bonus - test['expected_bonus']) < 0.001 and abs(mult - test['expected_mult']) < 0.001

        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"\n{status}: {test['name']}")
        print(f"  Expected: {test['expected_bonus']:.1%} bonus → {test['expected_mult']:.2f}x")
        print(f"  Got:      {bonus:.1%} bonus → {mult:.2f}x")

        if not passed:
            all_passed = False

    print("\n" + "=" * 80)
    if all_passed:
        print("ALL RARITY TESTS PASSED ✓")
    else:
        print("SOME TESTS FAILED ✗")
    print("=" * 80)

    return all_passed

def test_stat_application():
    """Test that stats are correctly modified by rarity bonus"""
    print("\n" + "=" * 80)
    print("TESTING STAT APPLICATION")
    print("=" * 80)

    base_stats = {
        'durability': 120,
        'quality': 100,
        'power': 115
    }

    rarity_mult = 1.20  # 20% bonus

    modified_stats = {}
    for stat_name, stat_value in base_stats.items():
        modified_stats[stat_name] = int(stat_value * rarity_mult)

    print(f"\nBase stats: {base_stats}")
    print(f"Rarity multiplier: {rarity_mult:.2f}x (20% bonus)")
    print(f"Modified stats: {modified_stats}")

    expected = {
        'durability': 144,  # 120 * 1.20 = 144
        'quality': 120,     # 100 * 1.20 = 120
        'power': 138        # 115 * 1.20 = 138
    }

    passed = modified_stats == expected
    print(f"\nExpected: {expected}")
    print(f"Got:      {modified_stats}")
    print(f"Status:   {'✓ PASS' if passed else '✗ FAIL'}")

    return passed

if __name__ == "__main__":
    result1 = test_rarity_calculation()
    result2 = test_stat_application()

    if result1 and result2:
        print("\n🎉 ALL TESTS PASSED - Logic is correct!")
        exit(0)
    else:
        print("\n❌ SOME TESTS FAILED")
        exit(1)

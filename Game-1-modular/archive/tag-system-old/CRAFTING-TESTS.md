# Crafting Tag System - Quick Test Guide

## Test Recipes: `recipes.JSON/recipes-tag-tests.JSON`

### Smithing Tests (Tag Inheritance)
1. **test_smithing_max_tags** - All functional tags (should inherit 12 tags)
2. **test_smithing_conflicting_hands** - 1H+2H conflict (should not crash)
3. **test_smithing_no_functional_tags** - Only metadata (should inherit 0 tags)
4. **test_smithing_empty_tags** - Empty array (should not crash)

### Refining Tests (Probabilistic Bonuses)
5. **test_refining_all_bonuses** - All 4 bonus types (high proc rate)
6. **test_refining_high_probability** - 40%+30% chances (frequent bonuses)
7. **test_refining_no_bonuses** - Pure smelting (never procs)
8. **test_refining_empty_tags** - Empty array (should not crash)
9. **test_refining_alloying_upgrade** - +2 tier upgrade (15% chance)

### Alchemy Tests (Effect Detection)
10. **test_alchemy_explicit_potion** - is_consumable=True, effect="heal"
11. **test_alchemy_explicit_transmutation** - is_consumable=False
12. **test_alchemy_conflicting_type** - Both tags (potion wins)
13. **test_alchemy_default_type** - No type tag (defaults to transmutation)
14. **test_alchemy_multiple_effects** - Multiple effects (first wins)
15. **test_alchemy_empty_tags** - Empty array (should not crash)

## Expected Debug Output

### Smithing Success:
```
[TAG_INFO] ⚒️  Smithing: Recipe 'test_smithing_max_tags' tag inheritance |
  inherited=['1H', '2H', 'melee', 'slashing', ...]
```

### Refining Bonus Proc:
```
[TAG_INFO] 🔨 Refining: Recipe 'test_refining_all_bonuses' probabilistic bonuses |
  final_output=2x rare, yield_proc=True, quality_proc=True
[TAG_INFO]    🎲 PROBABILISTIC BONUS ACTIVATED!
```

### Alchemy Detection:
```
[TAG_INFO] ⚗️  Alchemy: Recipe 'test_alchemy_explicit_potion' effect detection |
  output_type=potion, effect_type=heal
```

## Quick Verification

✅ **Smithing**: Tags in result dict?
✅ **Refining**: Bonuses sometimes proc (not always)?
✅ **Alchemy**: Correct is_consumable and effect_type?
✅ **No crashes**: All 15 recipes craft without errors?

## Statistical Test (Refining)

Craft `test_refining_all_bonuses` 100 times:
- Expect ~25-45 with bonus yield (crushing 25% + grinding 40%)
- Expect ~30-45 with quality upgrade (purifying 30% + alloying 15%)
- Base recipe (1x common) should NEVER be modified, only enhanced


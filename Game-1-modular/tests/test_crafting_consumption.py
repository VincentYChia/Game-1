"""
Test Crafting Buff Consumption System

Tests that crafting-related buffs (Smith's Focus, Alchemist's Insight, Engineer's Precision)
are properly consumed after completing crafting minigames.

Usage:
    cd Game-1-modular
    python test_crafting_consumption.py
"""

import sys
import os

# Add parent directory (Game-1-modular) to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from entities.character import Character
from entities.components.buffs import ActiveBuff, BuffManager
from data.models.world import Position
from core.config import Config


def test_crafting_buff_consumption():
    """Test that crafting buffs are consumed after minigame completion"""
    print("\n" + "="*70)
    print("TEST: Crafting Buff Consumption System")
    print("="*70 + "\n")

    # Create a test character with buff manager
    print("1. Creating test character with buff manager...")
    start_pos = Position(x=0, y=0)
    character = Character(start_position=start_pos)

    # Ensure buff manager exists
    if not hasattr(character, 'buffs'):
        from systems.buff_manager import BuffManager
        character.buffs = BuffManager()
        print("   ✓ Added BuffManager to character")
    else:
        print("   ✓ Character already has BuffManager")

    print()

    # Test 1: Smith's Focus (smithing buff)
    print("="*70)
    print("TEST 1: Smith's Focus (Smithing Buff)")
    print("="*70 + "\n")

    # Create smithing buff (quicken effect for smithing)
    smithing_buff = ActiveBuff(
        buff_id="smiths_focus",
        name="Smith's Focus",
        effect_type="quicken",
        category="smithing",
        magnitude="major",
        bonus_value=2.0,  # Magnitude 'major' = 2.0x
        duration=0,  # Instant duration = consume on use
        duration_remaining=0,
        source="skill",
        consume_on_use=True
    )

    character.buffs.add_buff(smithing_buff)
    print("2. Added Smith's Focus buff to character")
    print(f"   Active buffs: {len(character.buffs.active_buffs)}")
    print(f"   Buff: {smithing_buff.name} (category={smithing_buff.category})")
    print()

    # Simulate crafting minigame completion
    print("3. Simulating smithing minigame completion...")
    buffs_before = len(character.buffs.active_buffs)
    character.buffs.consume_buffs_for_action("craft", category="smithing")
    buffs_after = len(character.buffs.active_buffs)
    consumed = buffs_before - buffs_after
    print(f"   Buffs consumed: {consumed}")
    print(f"   Remaining active buffs: {buffs_after}")
    print()

    # Verify buff was consumed
    test1_pass = consumed == 1 and buffs_after == 0
    if test1_pass:
        print("✅ TEST 1 PASSED: Smith's Focus consumed after smithing")
    else:
        print("❌ TEST 1 FAILED: Buff not consumed properly")
    print()

    # Test 2: Alchemist's Insight (alchemy buff)
    print("="*70)
    print("TEST 2: Alchemist's Insight (Alchemy Buff)")
    print("="*70 + "\n")

    # Create alchemy buffs (quicken + empower)
    alchemy_quicken = ActiveBuff(
        buff_id="alchemists_insight_quicken",
        name="Alchemist's Insight (Quicken)",
        effect_type="quicken",
        category="alchemy",
        magnitude="moderate",
        bonus_value=1.5,  # Moderate
        duration=0,
        duration_remaining=0,
        source="skill",
        consume_on_use=True
    )

    alchemy_empower = ActiveBuff(
        buff_id="alchemists_insight_empower",
        name="Alchemist's Insight (Empower)",
        effect_type="empower",
        category="alchemy",
        magnitude="minor",
        bonus_value=1.25,  # Minor
        duration=0,
        duration_remaining=0,
        source="skill",
        consume_on_use=True
    )

    character.buffs.add_buff(alchemy_quicken)
    character.buffs.add_buff(alchemy_empower)
    print("4. Added Alchemist's Insight buffs to character")
    print(f"   Active buffs: {len(character.buffs.active_buffs)}")
    for buff in character.buffs.active_buffs:
        print(f"   - {buff.name} (category={buff.category}, type={buff.effect_type})")
    print()

    # Simulate alchemy minigame completion
    print("5. Simulating alchemy minigame completion...")
    buffs_before = len(character.buffs.active_buffs)
    character.buffs.consume_buffs_for_action("craft", category="alchemy")
    buffs_after = len(character.buffs.active_buffs)
    consumed = buffs_before - buffs_after
    print(f"   Buffs consumed: {consumed}")
    print(f"   Remaining active buffs: {buffs_after}")
    print()

    # Verify both buffs consumed
    test2_pass = consumed == 2 and buffs_after == 0
    if test2_pass:
        print("✅ TEST 2 PASSED: Both Alchemist's Insight buffs consumed")
    else:
        print("❌ TEST 2 FAILED: Expected 2 buffs consumed, got", consumed)
    print()

    # Test 3: Engineer's Precision (engineering buff)
    print("="*70)
    print("TEST 3: Engineer's Precision (Engineering Buff)")
    print("="*70 + "\n")

    # Create engineering buffs
    eng_quicken = ActiveBuff(
        buff_id="engineers_precision_quicken",
        name="Engineer's Precision (Quicken)",
        effect_type="quicken",
        category="engineering",
        magnitude="major",
        bonus_value=2.0,  # Major
        duration=0,
        duration_remaining=0,
        source="skill",
        consume_on_use=True
    )

    eng_empower = ActiveBuff(
        buff_id="engineers_precision_empower",
        name="Engineer's Precision (Empower)",
        effect_type="empower",
        category="engineering",
        magnitude="moderate",
        bonus_value=1.5,  # Moderate
        duration=0,
        duration_remaining=0,
        source="skill",
        consume_on_use=True
    )

    character.buffs.add_buff(eng_quicken)
    character.buffs.add_buff(eng_empower)
    print("6. Added Engineer's Precision buffs to character")
    print(f"   Active buffs: {len(character.buffs.active_buffs)}")
    for buff in character.buffs.active_buffs:
        print(f"   - {buff.name} (category={buff.category}, type={buff.effect_type})")
    print()

    # Simulate engineering minigame completion
    print("7. Simulating engineering minigame completion...")
    buffs_before = len(character.buffs.active_buffs)
    character.buffs.consume_buffs_for_action("craft", category="engineering")
    buffs_after = len(character.buffs.active_buffs)
    consumed = buffs_before - buffs_after
    print(f"   Buffs consumed: {consumed}")
    print(f"   Remaining active buffs: {buffs_after}")
    print()

    # Verify both buffs consumed
    test3_pass = consumed == 2 and buffs_after == 0
    if test3_pass:
        print("✅ TEST 3 PASSED: Both Engineer's Precision buffs consumed")
    else:
        print("❌ TEST 3 FAILED: Expected 2 buffs consumed, got", consumed)
    print()

    # Test 4: Mixed buffs - only correct category consumed
    print("="*70)
    print("TEST 4: Category-Specific Consumption")
    print("="*70 + "\n")

    # Add buffs for multiple crafting types
    character.buffs.add_buff(ActiveBuff(
        buff_id="smiths_focus_mixed",
        name="Smith's Focus",
        effect_type="quicken",
        category="smithing",
        magnitude="major",
        bonus_value=2.0,
        duration=0,
        duration_remaining=0,
        source="skill",
        consume_on_use=True
    ))

    character.buffs.add_buff(ActiveBuff(
        buff_id="alchemists_insight_mixed",
        name="Alchemist's Insight",
        effect_type="quicken",
        category="alchemy",
        magnitude="moderate",
        bonus_value=1.5,
        duration=0,
        duration_remaining=0,
        source="skill",
        consume_on_use=True
    ))

    character.buffs.add_buff(ActiveBuff(
        buff_id="engineers_precision_mixed",
        name="Engineer's Precision",
        effect_type="quicken",
        category="engineering",
        magnitude="major",
        bonus_value=2.0,
        duration=0,
        duration_remaining=0,
        source="skill",
        consume_on_use=True
    ))

    print("8. Added mixed crafting buffs:")
    print(f"   Active buffs: {len(character.buffs.active_buffs)}")
    for buff in character.buffs.active_buffs:
        print(f"   - {buff.name} (category={buff.category})")
    print()

    # Consume only smithing buffs
    print("9. Consuming only smithing buffs...")
    buffs_before = len(character.buffs.active_buffs)
    character.buffs.consume_buffs_for_action("craft", category="smithing")
    buffs_after = len(character.buffs.active_buffs)
    consumed = buffs_before - buffs_after
    print(f"   Buffs consumed: {consumed}")
    print(f"   Remaining active buffs: {buffs_after}")
    for buff in character.buffs.active_buffs:
        print(f"   - {buff.name} (category={buff.category})")
    print()

    # Verify only smithing buff consumed
    test4_pass = consumed == 1 and buffs_after == 2
    if test4_pass:
        print("✅ TEST 4 PASSED: Only smithing buff consumed, others remain")
    else:
        print(f"❌ TEST 4 FAILED: Expected 1 consumed and 2 remaining")
    print()

    # Summary
    print("="*70)
    print("TEST SUMMARY")
    print("="*70 + "\n")

    all_passed = test1_pass and test2_pass and test3_pass and test4_pass

    print(f"Test 1 (Smith's Focus):           {'✅ PASS' if test1_pass else '❌ FAIL'}")
    print(f"Test 2 (Alchemist's Insight):     {'✅ PASS' if test2_pass else '❌ FAIL'}")
    print(f"Test 3 (Engineer's Precision):    {'✅ PASS' if test3_pass else '❌ FAIL'}")
    print(f"Test 4 (Category-Specific):       {'✅ PASS' if test4_pass else '❌ FAIL'}")
    print()

    if all_passed:
        print("🎉 ALL TESTS PASSED! Crafting buff consumption working correctly!")
    else:
        print("⚠️  SOME TESTS FAILED - Review implementation")
    print()

    return all_passed


if __name__ == "__main__":
    try:
        success = test_crafting_buff_consumption()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n❌ TEST CRASHED: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

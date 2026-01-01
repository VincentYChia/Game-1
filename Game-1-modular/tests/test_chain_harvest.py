"""
Test Chain Harvest AoE Gathering System

Tests that Chain Harvest skill properly harvests multiple resource nodes
in a radius using the devastate buff system.

Usage:
    cd Game-1-modular
    python test_chain_harvest.py
"""

import sys
import os

# Add parent directory (Game-1-modular) to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from entities.character import Character
from entities.components.buffs import ActiveBuff, BuffManager
from systems.natural_resource import NaturalResource
from data.models.world import Position, ResourceType
from core.config import Config


def test_chain_harvest_aoe():
    """Test that Chain Harvest harvests multiple nodes in a radius"""
    print("\n" + "="*70)
    print("TEST: Chain Harvest AoE Gathering System")
    print("="*70 + "\n")

    # Create a test character
    print("1. Creating test character...")
    start_pos = Position(x=10, y=10)
    character = Character(start_position=start_pos)

    # Create and equip a pickaxe by setting it directly in the equipment slot
    # (For testing, we bypass the full equip system and just set the tool in the slot)
    from data.models.equipment import EquipmentItem
    pickaxe = EquipmentItem(
        item_id="iron_pickaxe",
        name="Iron Pickaxe",
        slot="pickaxe",
        tier=2,
        rarity="common",
        damage=(45, 55),  # Tuple format (min, max)
        durability_max=100,
        durability_current=100,
        item_type="tool"
    )
    # Directly set the tool in the equipment slot for testing
    character.equipment.slots['pickaxe'] = pickaxe
    print(f"   ✓ Created character at position ({character.position.x}, {character.position.y})")
    print(f"   ✓ Equipped {pickaxe.name} (damage={pickaxe.damage}, tier={pickaxe.tier})")
    print()

    # Create resource nodes at various distances
    print("2. Creating resource nodes at various positions...")
    resources = []

    # Primary target (at character position)
    primary = NaturalResource(Position(x=10, y=10), ResourceType.COPPER_ORE, tier=1)
    primary.current_hp = 30  # Pre-damage so it can be one-shot
    resources.append(primary)
    print(f"   - Primary: Copper Ore at (10, 10) - distance 0 (HP: {primary.current_hp})")

    # Within radius 3 (should be harvested)
    close1 = NaturalResource(Position(x=12, y=10), ResourceType.COPPER_ORE, tier=1)
    close1.current_hp = 30
    resources.append(close1)
    print(f"   - Close 1: Copper Ore at (12, 10) - distance 2 (HP: {close1.current_hp})")

    close2 = NaturalResource(Position(x=10, y=12), ResourceType.COPPER_ORE, tier=1)
    close2.current_hp = 30
    resources.append(close2)
    print(f"   - Close 2: Copper Ore at (10, 12) - distance 2 (HP: {close2.current_hp})")

    close3 = NaturalResource(Position(x=12, y=12), ResourceType.COPPER_ORE, tier=1)
    close3.current_hp = 30
    resources.append(close3)
    print(f"   - Close 3: Copper Ore at (12, 12) - distance 2.83 (HP: {close3.current_hp})")

    # Outside radius 3 (should NOT be harvested)
    far1 = NaturalResource(Position(x=15, y=10), ResourceType.COPPER_ORE, tier=1)
    far1.current_hp = 30
    resources.append(far1)
    print(f"   - Far 1: Copper Ore at (15, 10) - distance 5 (HP: {far1.current_hp})")

    # Wrong tool type (tree, not ore - should NOT be harvested)
    tree = NaturalResource(Position(x=11, y=10), ResourceType.OAK_TREE, tier=1)
    tree.current_hp = 30
    resources.append(tree)
    print(f"   - Tree: Oak Tree at (11, 10) - distance 1 (wrong tool, HP: {tree.current_hp})")

    print(f"\n   Total resources: {len(resources)} (4 ore in range, 1 ore out of range, 1 tree)")
    print()

    # Test 1: Normal harvest WITHOUT Chain Harvest buff (single node)
    print("="*70)
    print("TEST 1: Normal Harvest (No AoE Buff)")
    print("="*70 + "\n")

    print("3. Harvesting primary node WITHOUT Chain Harvest buff...")
    result = character.harvest_resource(primary, nearby_resources=resources)

    # Count how many nodes are depleted
    depleted_count = sum(1 for r in resources if r.depleted)
    print(f"   Nodes depleted: {depleted_count}")

    test1_pass = depleted_count == 1
    if test1_pass:
        print("✅ TEST 1 PASSED: Only 1 node harvested (no AoE)")
    else:
        print(f"❌ TEST 1 FAILED: Expected 1 node depleted, got {depleted_count}")
    print()

    # Reset resources for next test
    for r in resources:
        r.depleted = False
        r.current_hp = 30  # Reset to test HP
    print("4. Reset all resources for next test")
    print()

    # Test 2: Chain Harvest WITH devastate buff (AoE harvest)
    print("="*70)
    print("TEST 2: Chain Harvest (With AoE Devastate Buff)")
    print("="*70 + "\n")

    # Add Chain Harvest devastate buff (mining, radius 3)
    print("5. Adding Chain Harvest devastate buff (radius=3, mining)...")
    chain_harvest_buff = ActiveBuff(
        buff_id="chain_harvest",
        name="Chain Harvest",
        effect_type="devastate",
        category="mining",
        magnitude="minor",
        bonus_value=3,  # Radius of 3 tiles
        duration=0,  # Instant = consume on use
        duration_remaining=0,
        source="skill",
        consume_on_use=True
    )

    character.buffs.add_buff(chain_harvest_buff)
    print(f"   Active buffs: {len(character.buffs.active_buffs)}")
    print(f"   Buff: {chain_harvest_buff.name} (radius={chain_harvest_buff.bonus_value})")
    print()

    # Harvest with Chain Harvest buff active
    print("6. Harvesting with Chain Harvest AoE effect...")
    result = character.harvest_resource(primary, nearby_resources=resources)

    # Check which nodes were depleted
    print("\n   Node status after harvest:")
    for i, r in enumerate(resources):
        status = "DEPLETED" if r.depleted else "intact"
        node_type = "Primary" if i == 0 else f"Close {i}" if i <= 3 else "Far" if i == 4 else "Tree"
        print(f"   - {node_type}: {status}")

    depleted_count = sum(1 for r in resources if r.depleted)
    print(f"\n   Total nodes depleted: {depleted_count}")

    # Verify buff was consumed
    buffs_remaining = len(character.buffs.active_buffs)
    print(f"   Buffs remaining: {buffs_remaining}")
    print()

    # Should harvest exactly 4 nodes (primary + 3 close ore nodes)
    # Should NOT harvest: far1 (out of range), tree (wrong tool)
    expected_depleted = 4
    test2_pass = depleted_count == expected_depleted and buffs_remaining == 0

    if test2_pass:
        print(f"✅ TEST 2 PASSED: {expected_depleted} ore nodes harvested in radius 3, buff consumed")
    else:
        print(f"❌ TEST 2 FAILED: Expected {expected_depleted} nodes depleted and 0 buffs, got {depleted_count} nodes and {buffs_remaining} buffs")
    print()

    # Test 3: Chain Harvest with Forestry (different category)
    print("="*70)
    print("TEST 3: Chain Harvest Forestry (Category Mismatch)")
    print("="*70 + "\n")

    # Reset resources
    for r in resources:
        r.depleted = False
        r.current_hp = 30  # Reset to test HP
    print("7. Reset all resources")
    print()

    # Add forestry devastate buff (should work on trees)
    print("8. Adding forestry devastate buff (radius=3)...")
    forestry_buff = ActiveBuff(
        buff_id="chain_harvest_forestry",
        name="Chain Harvest (Forestry)",
        effect_type="devastate",
        category="forestry",
        magnitude="minor",
        bonus_value=3,
        duration=0,
        duration_remaining=0,
        source="skill",
        consume_on_use=True
    )

    character.buffs.add_buff(forestry_buff)
    print(f"   Buff: {forestry_buff.name} (category={forestry_buff.category}, radius={forestry_buff.bonus_value})")
    print()

    # Try to harvest ore node with forestry buff (category mismatch)
    print("9. Attempting to harvest ore with forestry buff...")
    result = character.harvest_resource(primary, nearby_resources=resources)

    depleted_count = sum(1 for r in resources if r.depleted)
    print(f"   Nodes depleted: {depleted_count}")

    # Should harvest just the primary node (no AoE because category mismatch)
    # Actually, looking at the code, forestry buff should be consumed but not trigger AoE for ore
    test3_pass = depleted_count == 1
    if test3_pass:
        print("✅ TEST 3 PASSED: Category mismatch - no AoE, only primary node harvested")
    else:
        print(f"❌ TEST 3 FAILED: Expected 1 node (primary only), got {depleted_count}")
    print()

    # Summary
    print("="*70)
    print("TEST SUMMARY")
    print("="*70 + "\n")

    all_passed = test1_pass and test2_pass and test3_pass

    print(f"Test 1 (Normal Harvest):          {'✅ PASS' if test1_pass else '❌ FAIL'}")
    print(f"Test 2 (Chain Harvest AoE):       {'✅ PASS' if test2_pass else '❌ FAIL'}")
    print(f"Test 3 (Category Mismatch):       {'✅ PASS' if test3_pass else '❌ FAIL'}")
    print()

    if all_passed:
        print("🎉 ALL TESTS PASSED! Chain Harvest AoE gathering working correctly!")
    else:
        print("⚠️  SOME TESTS FAILED - Review implementation")
    print()

    return all_passed


if __name__ == "__main__":
    try:
        success = test_chain_harvest_aoe()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n❌ TEST CRASHED: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

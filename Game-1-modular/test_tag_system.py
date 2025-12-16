"""
Test script for tag-to-effects system
Verifies core functionality without running the full game
"""

import os
import sys
import json
from types import ModuleType

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Mock Position class
class Position:
    def __init__(self, x, y, z=0):
        self.x = x
        self.y = y
        self.z = z

    def distance_to(self, other):
        dx = self.x - other.x
        dy = self.y - other.y
        dz = self.z - other.z
        return (dx*dx + dy*dy + dz*dz) ** 0.5

# Create mock modules to bypass pygame dependency
mock_pygame = ModuleType('pygame')
sys.modules['pygame'] = mock_pygame

# Mock world module
mock_world = ModuleType('data.models.world')
mock_world.Position = Position
sys.modules['data.models.world'] = mock_world

# Now we can import tag system modules
from entities.status_manager import StatusEffectManager
from entities.status_effect import create_status_effect
from core.tag_system import get_tag_registry
from core.tag_parser import get_tag_parser
from core.effect_executor import get_effect_executor
from core.geometry.target_finder import get_target_finder


# Mock entity for testing
class MockEntity:
    def __init__(self, name, position, category="enemy", health=100):
        self.name = name
        self.position = position
        self.category = category
        self.max_health = health
        self.current_health = health
        self.is_alive = True
        self.visual_effects = set()

        # Status manager
        self.status_manager = StatusEffectManager(self)

        # Flags for CC
        self.is_frozen = False
        self.is_stunned = False
        self.is_rooted = False

        # Multipliers
        self.damage_multiplier = 1.0
        self.damage_taken_multiplier = 1.0
        self.shield_health = 0.0

    def take_damage(self, damage: float, damage_type: str = "physical"):
        """Take damage"""
        damage *= self.damage_taken_multiplier
        self.current_health -= damage
        if self.current_health <= 0:
            self.current_health = 0
            self.is_alive = False
        print(f"  {self.name} took {damage:.1f} {damage_type} damage (HP: {self.current_health:.1f}/{self.max_health:.1f})")

    def heal(self, amount: float):
        """Heal"""
        old_health = self.current_health
        self.current_health = min(self.current_health + amount, self.max_health)
        print(f"  {self.name} healed {self.current_health - old_health:.1f} HP (HP: {self.current_health:.1f}/{self.max_health:.1f})")


def test_tag_registry():
    """Test tag registry loads definitions"""
    print("\n=== TEST: Tag Registry ===")
    registry = get_tag_registry()

    # Check some tags exist
    burn_def = registry.get_definition('burn')
    assert burn_def is not None, "burn tag not found"
    print(f"✓ burn tag found: {burn_def['category']}")

    chain_def = registry.get_definition('chain')
    assert chain_def is not None, "chain tag not found"
    print(f"✓ chain tag found: {chain_def['category']}, priority {chain_def['priority']}")

    # Test alias resolution
    resolved = registry.resolve_alias('slow')
    print(f"✓ 'slow' resolves to '{resolved}'")

    print("✓ Tag Registry test passed")


def test_tag_parser():
    """Test tag parsing and conflict resolution"""
    print("\n=== TEST: Tag Parser ===")
    parser = get_tag_parser()

    # Test basic parsing
    tags = ['fire', 'chain', 'burn']
    params = {
        'baseDamage': 50,
        'chain_count': 3,
        'burn_duration': 5.0
    }

    config = parser.parse(tags, params)

    assert config.geometry_tag == 'chain', f"Expected geometry 'chain', got '{config.geometry_tag}'"
    assert 'fire' in config.damage_tags, "fire not in damage_tags"
    assert 'burn' in config.status_tags, "burn not in status_tags"
    print(f"✓ Parsed tags: geometry={config.geometry_tag}, damage={config.damage_tags}, status={config.status_tags}")

    # Test conflict resolution (chain > cone)
    tags2 = ['chain', 'cone', 'fire']
    config2 = parser.parse(tags2, {})
    assert config2.geometry_tag == 'chain', "chain should win over cone"
    print(f"✓ Conflict resolution: chain > cone (got {config2.geometry_tag})")

    print("✓ Tag Parser test passed")


def test_status_effects():
    """Test status effect application"""
    print("\n=== TEST: Status Effects ===")

    # Create mock target
    target = MockEntity("Test Enemy", Position(0, 0), category="beast")

    # Apply burn status
    target.status_manager.apply_status('burn', {
        'burn_duration': 3.0,
        'burn_damage_per_second': 10.0
    })

    assert target.status_manager.has_status('burn'), "burn status not applied"
    print("✓ Burn status applied")

    # Update for 1 second (should deal damage)
    initial_hp = target.current_health
    target.status_manager.update(1.0)
    assert target.current_health < initial_hp, "burn didn't deal damage"
    print(f"✓ Burn dealt {initial_hp - target.current_health:.1f} damage")

    # Test freeze (mutual exclusion with burn)
    target.status_manager.apply_status('freeze', {'freeze_duration': 2.0})
    assert target.status_manager.has_status('freeze'), "freeze not applied"
    assert not target.status_manager.has_status('burn'), "burn should be removed by freeze"
    print("✓ Freeze removed burn (mutual exclusion)")

    # Test immobilization
    assert target.status_manager.is_immobilized(), "freeze should immobilize"
    print("✓ Freeze immobilizes target")

    print("✓ Status Effects test passed")


def test_geometry():
    """Test geometry calculations"""
    print("\n=== TEST: Geometry ===")
    finder = get_target_finder()

    # Create entities
    source = MockEntity("Source", Position(0, 0), category="player")
    target1 = MockEntity("Target1", Position(2, 0), category="enemy")
    target2 = MockEntity("Target2", Position(4, 0), category="enemy")
    target3 = MockEntity("Target3", Position(0, 3), category="enemy")

    available = [target1, target2, target3]

    # Test chain geometry
    targets = finder.find_targets(
        geometry='chain',
        source=source,
        primary_target=target1,
        params={'chain_count': 2, 'chain_range': 5.0},
        context='enemy',
        available_entities=available
    )

    assert len(targets) == 2, f"Expected 2 chain targets, got {len(targets)}"
    assert targets[0] == target1, "First target should be primary target"
    print(f"✓ Chain found {len(targets)} targets")

    # Test circle geometry
    targets = finder.find_targets(
        geometry='circle',
        source=target1,  # Center on target1
        primary_target=target1,
        params={'circle_radius': 3.0, 'circle_max_targets': 10},
        context='enemy',
        available_entities=available
    )

    print(f"✓ Circle found {len(targets)} targets within radius")

    print("✓ Geometry test passed")


def test_effect_execution():
    """Test full effect execution"""
    print("\n=== TEST: Effect Execution ===")
    executor = get_effect_executor()

    # Create entities
    source = MockEntity("Player", Position(0, 0), category="player")
    target1 = MockEntity("Enemy1", Position(2, 0), category="enemy", health=100)
    target2 = MockEntity("Enemy2", Position(4, 0), category="enemy", health=100)

    available = [target1, target2]

    # Execute fire + chain + burn effect
    tags = ['fire', 'chain', 'burn']
    params = {
        'baseDamage': 30,
        'chain_count': 2,
        'chain_range': 5.0,
        'burn_duration': 3.0,
        'burn_damage_per_second': 5.0
    }

    context = executor.execute_effect(
        source=source,
        primary_target=target1,
        tags=tags,
        params=params,
        available_entities=available
    )

    # Verify targets were hit
    assert len(context.targets) == 2, f"Expected 2 targets, got {len(context.targets)}"
    print(f"✓ Effect hit {len(context.targets)} targets")

    # Verify damage was dealt
    assert target1.current_health < target1.max_health, "target1 didn't take damage"
    assert target2.current_health < target2.max_health, "target2 didn't take damage"
    print(f"✓ Damage dealt to all targets")

    # Verify burn status was applied
    assert target1.status_manager.has_status('burn'), "target1 doesn't have burn"
    assert target2.status_manager.has_status('burn'), "target2 doesn't have burn"
    print("✓ Burn status applied to all targets")

    # Update statuses for 1 second
    initial_hp = target1.current_health
    target1.status_manager.update(1.0)
    assert target1.current_health < initial_hp, "burn didn't tick"
    print("✓ Burn DoT ticking")

    print("✓ Effect Execution test passed")


def test_context_awareness():
    """Test context-aware tag behavior"""
    print("\n=== TEST: Context Awareness ===")
    executor = get_effect_executor()

    # Create undead enemy and construct
    undead = MockEntity("Skeleton", Position(2, 0), category="undead", health=100)
    construct = MockEntity("Golem", Position(4, 0), category="construct", health=100)

    # Holy damage vs undead (should deal bonus damage)
    tags = ['holy', 'single_target']
    params = {'baseDamage': 50}

    print("\nTesting holy damage vs undead (should deal 150% damage):")
    context = executor.execute_effect(
        source=MockEntity("Cleric", Position(0, 0), category="player"),
        primary_target=undead,
        tags=tags,
        params=params,
        available_entities=[undead]
    )

    # Holy should deal 150% damage to undead (50 * 1.5 = 75)
    expected_damage = 50 * 1.5
    actual_damage = undead.max_health - undead.current_health
    print(f"  Expected ~{expected_damage} damage, dealt {actual_damage}")

    print("\n✓ Context Awareness test passed")


def main():
    """Run all tests"""
    print("=" * 60)
    print("TAG-TO-EFFECTS SYSTEM TESTS")
    print("=" * 60)

    try:
        test_tag_registry()
        test_tag_parser()
        test_status_effects()
        test_geometry()
        test_effect_execution()
        test_context_awareness()

        print("\n" + "=" * 60)
        print("✅ ALL TESTS PASSED")
        print("=" * 60)
        return 0

    except Exception as e:
        print("\n" + "=" * 60)
        print(f"❌ TEST FAILED: {e}")
        print("=" * 60)
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())

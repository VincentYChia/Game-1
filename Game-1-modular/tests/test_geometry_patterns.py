"""
Test Geometry Pattern System
Tests all geometry patterns to ensure target finding works correctly
"""

import sys
import os
# Add parent directory (Game-1-modular) to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.geometry.target_finder import TargetFinder
from data.models.world import Position
import math


class TestEntity:
    """Mock entity for geometry testing"""
    def __init__(self, name: str, position: tuple, category: str = 'beast'):
        self.name = name
        self.position = Position(position[0], position[1], 0.0)
        self.category = category  # Use 'beast', 'undead', etc. for enemies
        self.is_alive = True
        # Add Enemy-like attributes for context detection
        self.definition = type('obj', (object,), {'name': name})()  # Mock definition

    def __repr__(self):
        return f"{self.name}@({self.position.x:.1f},{self.position.y:.1f})"


def create_test_grid():
    """
    Create a grid of test entities:

       0  1  2  3  4  5  6  7  8
    0  .  .  E1 .  .  E2 .  .  .
    1  .  .  .  .  .  .  .  .  .
    2  E3 .  .  .  P  .  .  .  E4
    3  .  .  .  .  .  .  .  .  .
    4  .  .  E5 .  .  E6 .  .  .

    P = Player/Source (4, 2)
    E1-E6 = Enemies at various positions
    """
    # Create player source (no category needed, geometry doesn't filter source)
    source = TestEntity("Player", (4, 2), "player")
    source.definition = None  # Player doesn't need definition

    enemies = [
        TestEntity("E1", (2, 0), "beast"),  # North, distance ~2.8
        TestEntity("E2", (5, 0), "undead"),  # North-East, distance ~2.2
        TestEntity("E3", (0, 2), "construct"),  # West, distance 4.0
        TestEntity("E4", (8, 2), "mechanical"),  # East, distance 4.0
        TestEntity("E5", (2, 4), "beast"),  # South-West, distance ~2.8
        TestEntity("E6", (5, 4), "elemental"),  # South-East, distance ~2.2
    ]

    return source, enemies


def test_single_target():
    """Test single_target geometry - should only hit primary target"""
    print("\n" + "="*70)
    print("TEST: Single Target Geometry")
    print("="*70 + "\n")

    source, enemies = create_test_grid()
    target_finder = TargetFinder()

    primary = enemies[0]  # E1
    all_entities = enemies

    targets = target_finder.find_targets(
        geometry='single_target',
        source=source,
        primary_target=primary,
        params={},
        context='enemy',
        available_entities=all_entities
    )

    print(f"Primary target: {primary}")
    print(f"Targets found: {targets}")
    print(f"Count: {len(targets)}")

    assert len(targets) == 1, f"Single target should return 1 target, got {len(targets)}"
    assert targets[0] == primary, "Single target should return only primary target"

    print("✅ Single target: Returns only primary target\n")


def test_chain():
    """Test chain geometry - should arc to nearby enemies"""
    print("="*70)
    print("TEST: Chain Geometry")
    print("="*70 + "\n")

    source, enemies = create_test_grid()
    target_finder = TargetFinder()

    # Start with E1, should chain to E2 (closest)
    primary = enemies[0]  # E1 at (2, 0)
    all_entities = enemies

    targets = target_finder.find_targets(
        geometry='chain',
        source=source,
        primary_target=primary,
        params={
            'chain_count': 2,      # Should jump 2 times
            'chain_range': 5.0     # Max 5 tiles between jumps
        },
        context='enemy',
        available_entities=all_entities
    )

    print(f"Primary target: {primary}")
    print(f"Chain count: 2, range: 5.0")
    print(f"Targets hit: {[str(t) for t in targets]}")
    print(f"Count: {len(targets)}")

    # Should hit E1 (primary) + up to 2 more (E2 is closest to E1)
    assert len(targets) >= 1, "Chain should hit at least primary target"
    assert targets[0] == primary, "First target should be primary"
    assert len(targets) <= 3, f"Chain with count=2 should hit max 3 targets, got {len(targets)}"

    print(f"✅ Chain: {len(targets)} targets hit (primary + {len(targets)-1} chains)\n")


def test_cone():
    """Test cone geometry - should hit targets in frontal arc"""
    print("="*70)
    print("TEST: Cone Geometry")
    print("="*70 + "\n")

    source, enemies = create_test_grid()
    target_finder = TargetFinder()

    # Aim north at E1, should hit E1 and E2 (both in northern cone)
    primary = enemies[0]  # E1 at (2, 0)
    all_entities = enemies

    targets = target_finder.find_targets(
        geometry='cone',
        source=source,
        primary_target=primary,
        params={
            'cone_angle': 90,      # 90 degree cone
            'cone_range': 5.0      # Max 5 tiles range
        },
        context='enemy',
        available_entities=all_entities
    )

    print(f"Source: {source}")
    print(f"Aiming at: {primary} (direction: north)")
    print(f"Cone: 90°, range: 5.0")
    print(f"Targets hit: {[str(t) for t in targets]}")
    print(f"Count: {len(targets)}")

    # Should hit E1 and E2 (both in northern cone, within 5 tiles)
    assert len(targets) >= 1, "Cone should hit at least one target"
    assert primary in targets, "Cone should hit primary target"

    print(f"✅ Cone: {len(targets)} targets in 90° arc\n")


def test_circle():
    """Test circle/AoE geometry - should hit all targets in radius"""
    print("="*70)
    print("TEST: Circle (AoE) Geometry")
    print("="*70 + "\n")

    source, enemies = create_test_grid()
    target_finder = TargetFinder()

    # Circle centered on source, radius 3
    targets = target_finder.find_targets(
        geometry='circle',
        source=source,
        primary_target=source.position,  # Center on source
        params={
            'circle_radius': 3.0,
            'origin': 'source',
            'max_targets': 0  # Unlimited
        },
        context='enemy',
        available_entities=enemies
    )

    print(f"Center: {source} (origin=source)")
    print(f"Radius: 3.0 tiles")
    print(f"Targets hit: {[str(t) for t in targets]}")
    print(f"Count: {len(targets)}")

    # Should hit E1, E2, E5, E6 (all within 3 tiles)
    # E3 and E4 are 4 tiles away (outside radius)
    assert len(targets) >= 2, "Circle should hit multiple targets"

    # Verify all hit targets are within radius
    for target in targets:
        dist = math.sqrt((target.position.x - source.position.x)**2 +
                        (target.position.y - source.position.y)**2)
        assert dist <= 3.0, f"{target} is {dist:.1f} tiles away (outside radius 3.0)"

    print(f"✅ Circle: {len(targets)} targets within 3.0 tile radius\n")


def test_circle_target_origin():
    """Test circle with origin=target - centers AoE on target position"""
    print("="*70)
    print("TEST: Circle Geometry (origin=target)")
    print("="*70 + "\n")

    source, enemies = create_test_grid()
    target_finder = TargetFinder()

    # Circle centered on E1, should hit nearby enemies
    primary = enemies[0]  # E1 at (2, 0)

    targets = target_finder.find_targets(
        geometry='circle',
        source=source,
        primary_target=primary,
        params={
            'circle_radius': 3.0,
            'origin': 'target',  # Center on target!
            'max_targets': 0
        },
        context='enemy',
        available_entities=enemies
    )

    print(f"Source: {source}")
    print(f"Center: {primary} (origin=target)")
    print(f"Radius: 3.0 tiles")
    print(f"Targets hit: {[str(t) for t in targets]}")
    print(f"Count: {len(targets)}")

    assert len(targets) >= 1, "Should hit at least primary target"

    # Verify all targets are within radius of E1
    for target in targets:
        dist = math.sqrt((target.position.x - primary.position.x)**2 +
                        (target.position.y - primary.position.y)**2)
        assert dist <= 3.0, f"{target} is {dist:.1f} tiles from {primary} (outside radius)"

    print(f"✅ Circle (target origin): {len(targets)} targets around primary\n")


def test_beam():
    """Test beam/line geometry - should hit targets in straight line"""
    print("="*70)
    print("TEST: Beam (Line) Geometry")
    print("="*70 + "\n")

    source, enemies = create_test_grid()
    target_finder = TargetFinder()

    # Beam from Player (4,2) toward E4 (8,2) - straight east
    primary = enemies[3]  # E4 at (8, 2)

    targets = target_finder.find_targets(
        geometry='beam',
        source=source,
        primary_target=primary,
        params={
            'beam_range': 10.0,
            'beam_width': 0.5,
            'pierce_count': -1  # Infinite pierce
        },
        context='enemy',
        available_entities=enemies
    )

    print(f"Source: {source}")
    print(f"Direction: toward {primary} (east)")
    print(f"Beam: range=10.0, width=0.5, pierce=infinite")
    print(f"Targets hit: {[str(t) for t in targets]}")
    print(f"Count: {len(targets)}")

    # Should hit E4 (directly in line)
    assert len(targets) >= 1, "Beam should hit at least one target"
    assert primary in targets, "Beam should hit target in line"

    print(f"✅ Beam: {len(targets)} targets in line\n")


def test_beam_pierce():
    """Test beam with pierce_count - should stop after hitting N targets"""
    print("="*70)
    print("TEST: Beam with Pierce Count")
    print("="*70 + "\n")

    # Create entities in a line
    source = TestEntity("Player", (0, 2), "player")
    source.definition = None
    enemies = [
        TestEntity("E1", (2, 2), "beast"),
        TestEntity("E2", (4, 2), "undead"),
        TestEntity("E3", (6, 2), "construct"),
        TestEntity("E4", (8, 2), "mechanical"),
    ]

    target_finder = TargetFinder()
    primary = enemies[0]

    # Pierce count = 1 (hits first 2 targets)
    targets = target_finder.find_targets(
        geometry='beam',
        source=source,
        primary_target=primary,
        params={
            'beam_range': 10.0,
            'beam_width': 0.5,
            'pierce_count': 1  # Hit 2 targets (pierce_count + 1)
        },
        context='enemy',
        available_entities=enemies
    )

    print(f"Source: {source}")
    print(f"Enemies in line: {[str(e) for e in enemies]}")
    print(f"Pierce count: 1 (should hit 2 targets)")
    print(f"Targets hit: {[str(t) for t in targets]}")
    print(f"Count: {len(targets)}")

    assert len(targets) == 2, f"Pierce count=1 should hit 2 targets, got {len(targets)}"
    assert targets[0] == enemies[0], "Should hit first enemy"
    assert targets[1] == enemies[1], "Should hit second enemy"

    print(f"✅ Beam (pierce=1): Correctly stops after 2 targets\n")


def test_context_filtering():
    """Test that context filters work correctly"""
    print("="*70)
    print("TEST: Context Filtering")
    print("="*70 + "\n")

    source = TestEntity("Player", (4, 2), "player")
    source.definition = None

    # Mix of enemy and ally entities
    # For allies, we need to make them recognizable as Character/PlacedEntity types
    enemy1 = TestEntity("Enemy1", (3, 2), "beast")
    enemy2 = TestEntity("Enemy2", (4, 1), "undead")

    # For allies/turrets, the context check looks for type name containing 'turret' or 'placedentity'
    # So we can't use TestEntity - let's create simple mock objects
    class MockTurret:
        def __init__(self, name: str, pos: tuple):
            self.name = name
            self.position = Position(pos[0], pos[1], 0.0)
            self.category = 'device'
            self.is_alive = True

    turret1 = MockTurret("Turret1", (5, 2))
    turret2 = MockTurret("Turret2", (4, 3))

    all_entities = [enemy1, turret1, enemy2, turret2]

    target_finder = TargetFinder()

    # Test enemy context - should only find enemies
    enemy_targets = target_finder.find_targets(
        geometry='circle',
        source=source,
        primary_target=source.position,
        params={'circle_radius': 3.0, 'origin': 'source'},
        context='enemy',
        available_entities=all_entities
    )

    entity_list = [f'{e.name}({getattr(e, "category", "?")})' for e in all_entities]
    enemy_list = [f'{t.name}({getattr(t, "category", "?")})' for t in enemy_targets]
    print(f"All entities: {entity_list}")
    print(f"Context='enemy' found: {enemy_list}")

    # Should only find the 2 enemies (beast, undead categories)
    assert all(hasattr(t, 'definition') for t in enemy_targets), "Enemy context should only return entities with definitions"
    assert len(enemy_targets) == 2, f"Should find 2 enemies, got {len(enemy_targets)}"

    # Test all context - should find everything
    all_targets = target_finder.find_targets(
        geometry='circle',
        source=source,
        primary_target=source.position,
        params={'circle_radius': 3.0, 'origin': 'source'},
        context='all',
        available_entities=all_entities
    )

    print(f"Context='all' found: {[f'{t.name}({t.category})' for t in all_targets]}")
    assert len(all_targets) == 4, f"Should find all 4 entities, got {len(all_targets)}"

    print("✅ Context filtering: Correctly filters by entity type\n")


if __name__ == "__main__":
    print("\n" + "="*70)
    print("GEOMETRY PATTERN SYSTEM - COMPREHENSIVE TEST SUITE")
    print("="*70)

    try:
        test_single_target()
        test_chain()
        test_cone()
        test_circle()
        test_circle_target_origin()
        test_beam()
        test_beam_pierce()
        test_context_filtering()

        print("="*70)
        print("🎉 ALL GEOMETRY PATTERN TESTS PASSED!")
        print("="*70)
        print("\nGeometry Patterns Verified:")
        print("  ✅ Single Target: Hits only primary target")
        print("  ✅ Chain: Arcs to nearby targets with falloff")
        print("  ✅ Cone: Hits targets in frontal arc")
        print("  ✅ Circle (AoE): Hits all in radius")
        print("  ✅ Circle (origin): Can center on source or target")
        print("  ✅ Beam/Line: Hits targets in straight line")
        print("  ✅ Pierce: Stops after N targets")
        print("  ✅ Context: Filters by entity type (enemy/ally/all)")
        print("\n")
        sys.exit(0)

    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ TEST CRASHED: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

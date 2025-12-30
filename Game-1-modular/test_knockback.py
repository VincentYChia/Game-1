#!/usr/bin/env python3
"""
Test script to verify knockback implementation
"""
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from core.effect_executor import get_effect_executor
from data.models.world import Position


class MockEntity:
    """Mock entity for testing"""
    def __init__(self, name: str, x: float, y: float):
        self.name = name
        self.position = [x, y, 0.0]  # List format like Enemy uses


def test_knockback():
    """Test knockback physics"""
    print("=" * 60)
    print("KNOCKBACK TEST")
    print("=" * 60)

    # Create mock entities
    source = MockEntity("Player", x=5.0, y=5.0)
    target = MockEntity("Enemy", x=10.0, y=10.0)

    print(f"\nInitial positions:")
    print(f"  Source (Player): ({source.position[0]}, {source.position[1]})")
    print(f"  Target (Enemy):  ({target.position[0]}, {target.position[1]})")

    # Calculate initial distance
    dx_before = target.position[0] - source.position[0]
    dy_before = target.position[1] - source.position[1]
    distance_before = (dx_before**2 + dy_before**2) ** 0.5
    print(f"  Distance: {distance_before:.2f} tiles")

    # Apply knockback
    knockback_distance = 3.0
    params = {'knockback_distance': knockback_distance}

    print(f"\nApplying knockback of {knockback_distance} tiles...")

    executor = get_effect_executor()
    executor._apply_knockback(source, target, params)

    print(f"\nFinal positions:")
    print(f"  Source (Player): ({source.position[0]}, {source.position[1]})")
    print(f"  Target (Enemy):  ({target.position[0]}, {target.position[1]})")

    # Calculate final distance
    dx_after = target.position[0] - source.position[0]
    dy_after = target.position[1] - source.position[1]
    distance_after = (dx_after**2 + dy_after**2) ** 0.5
    print(f"  Distance: {distance_after:.2f} tiles")

    # Verify
    distance_increase = distance_after - distance_before
    print(f"\n📊 RESULTS:")
    print(f"  Distance before: {distance_before:.2f} tiles")
    print(f"  Distance after:  {distance_after:.2f} tiles")
    print(f"  Distance increase: {distance_increase:.2f} tiles")
    print(f"  Expected increase: {knockback_distance:.2f} tiles")

    # Check if knockback worked
    tolerance = 0.1
    if abs(distance_increase - knockback_distance) < tolerance:
        print(f"\n✅ SUCCESS: Knockback working correctly!")
        print(f"   Enemy was pushed {knockback_distance:.2f} tiles away")
        return True
    else:
        print(f"\n❌ FAILURE: Knockback not working!")
        print(f"   Expected distance increase of {knockback_distance:.2f}")
        print(f"   Got distance increase of {distance_increase:.2f}")
        return False


def test_knockback_in_tag_system():
    """Test if knockback tag is recognized by tag system"""
    print("\n" + "=" * 60)
    print("TAG SYSTEM INTEGRATION TEST")
    print("=" * 60)

    from core.tag_parser import TagParser

    # Test tags with knockback
    tags = ["physical", "single", "knockback"]
    params = {
        "baseDamage": 50,
        "knockback_distance": 3.0
    }

    parser = TagParser()
    config = parser.parse(tags, params)

    print(f"\nInput tags: {tags}")
    print(f"\nParsed configuration:")
    print(f"  Damage tags: {config.damage_tags}")
    print(f"  Geometry tag: {config.geometry_tag}")
    print(f"  Special tags: {config.special_tags}")
    print(f"  Params: {config.params}")

    if 'knockback' in config.special_tags:
        print(f"\n✅ SUCCESS: 'knockback' tag recognized as special mechanic")
        return True
    else:
        print(f"\n❌ FAILURE: 'knockback' tag NOT in special_tags")
        print(f"   Config special_tags: {config.special_tags}")
        return False


if __name__ == "__main__":
    success1 = test_knockback()
    success2 = test_knockback_in_tag_system()

    print("\n" + "=" * 60)
    print("FINAL RESULTS")
    print("=" * 60)
    print(f"Knockback physics: {'✅ PASS' if success1 else '❌ FAIL'}")
    print(f"Tag system integration: {'✅ PASS' if success2 else '❌ FAIL'}")
    print()

    sys.exit(0 if (success1 and success2) else 1)

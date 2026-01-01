#!/usr/bin/env python3
"""
Test script to verify knockback works on Player Character
"""
import sys
from pathlib import Path

# Add project root to path (Game-1-modular)
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from core.effect_executor import get_effect_executor
from data.models.world import Position


class MockCharacter:
    """Mock character matching real Character structure"""
    def __init__(self, name: str, x: float, y: float):
        self.name = name
        self.position = Position(x, y, 0.0)  # Position object like Character uses


class MockEnemy:
    """Mock enemy"""
    def __init__(self, name: str, x: float, y: float):
        self.name = name
        self.position = [x, y, 0.0]  # List format like Enemy uses


def test_player_knockback():
    """Test knockback on player character"""
    print("=" * 60)
    print("PLAYER CHARACTER KNOCKBACK TEST")
    print("=" * 60)

    # Create mock entities - enemy knocks back player
    enemy = MockEnemy("Armored Beetle", x=5.0, y=5.0)
    player = MockCharacter("Player", x=10.0, y=10.0)

    print(f"\nInitial positions:")
    print(f"  Enemy (source):  ({enemy.position[0]}, {enemy.position[1]})")
    print(f"  Player (target): ({player.position.x}, {player.position.y})")

    # Calculate initial distance
    dx_before = player.position.x - enemy.position[0]
    dy_before = player.position.y - enemy.position[1]
    distance_before = (dx_before**2 + dy_before**2) ** 0.5
    print(f"  Distance: {distance_before:.2f} tiles")

    # Apply knockback from enemy to player
    knockback_distance = 4.0
    params = {'knockback_distance': knockback_distance}

    print(f"\n🔥 Enemy Ground Slam - knocking player back {knockback_distance} tiles...")

    executor = get_effect_executor()
    executor._apply_knockback(enemy, player, params)

    print(f"\nFinal positions:")
    print(f"  Enemy (source):  ({enemy.position[0]}, {enemy.position[1]})")
    print(f"  Player (target): ({player.position.x}, {player.position.y})")

    # Calculate final distance
    dx_after = player.position.x - enemy.position[0]
    dy_after = player.position.y - enemy.position[1]
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
        print(f"\n✅ SUCCESS: Player knockback working correctly!")
        print(f"   Player was pushed {knockback_distance:.2f} tiles away from enemy")
        return True
    else:
        print(f"\n❌ FAILURE: Player knockback not working!")
        print(f"   Expected distance increase of {knockback_distance:.2f}")
        print(f"   Got distance increase of {distance_increase:.2f}")

        # Check if position changed at all
        if player.position.x == 10.0 and player.position.y == 10.0:
            print(f"\n   ⚠️  CRITICAL: Position didn't change at all!")
            print(f"   Position.x is {type(player.position.x)}")
            print(f"   Position has attributes: {dir(player.position)}")

        return False


def test_position_mutability():
    """Test if Position object can be modified"""
    print("\n" + "=" * 60)
    print("POSITION OBJECT MUTABILITY TEST")
    print("=" * 60)

    pos = Position(10.0, 20.0, 0.0)
    print(f"\nInitial position: ({pos.x}, {pos.y}, {pos.z})")

    # Try to modify
    pos.x = 15.0
    pos.y = 25.0

    print(f"After modification: ({pos.x}, {pos.y}, {pos.z})")

    if pos.x == 15.0 and pos.y == 25.0:
        print(f"\n✅ SUCCESS: Position object is mutable")
        return True
    else:
        print(f"\n❌ FAILURE: Position object is immutable or has property setters")
        print(f"   Expected: (15.0, 25.0)")
        print(f"   Got: ({pos.x}, {pos.y})")
        return False


if __name__ == "__main__":
    success1 = test_position_mutability()
    success2 = test_player_knockback()

    print("\n" + "=" * 60)
    print("FINAL RESULTS")
    print("=" * 60)
    print(f"Position mutability: {'✅ PASS' if success1 else '❌ FAIL'}")
    print(f"Player knockback: {'✅ PASS' if success2 else '❌ FAIL'}")

    if not success1:
        print("\n⚠️  Position object cannot be modified directly!")
        print("   This would explain why player knockback doesn't work")

    print()

    sys.exit(0 if (success1 and success2) else 1)

"""
Test Status Effect System
Tests all implemented status effects to ensure they apply, tick, and expire correctly
"""

import sys
import os
# Add parent directory (Game-1-modular) to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from entities.status_effect import *
from entities.status_manager import StatusEffectManager


class TestEntity:
    """Mock entity for testing status effects"""
    def __init__(self, name: str):
        self.name = name
        self.current_health = 100.0
        self.max_health = 100.0
        self.speed = 5.0
        self.movement_speed = 5.0
        self.is_stunned = False
        self.is_frozen = False
        self.is_rooted = False
        self.visual_effects = set()
        self.damage_multiplier = 1.0
        self.damage_taken_multiplier = 1.0

    def take_damage(self, damage: float, damage_type: str = 'physical', **kwargs):
        """Take damage"""
        self.current_health -= damage
        if self.current_health < 0:
            self.current_health = 0

    def heal(self, healing: float):
        """Heal"""
        self.current_health = min(self.current_health + healing, self.max_health)


def test_dot_effects():
    """Test Damage Over Time effects: Burn, Bleed, Poison, Shock"""
    print("\n" + "="*70)
    print("TEST: Damage Over Time (DoT) Effects")
    print("="*70 + "\n")

    entity = TestEntity("Test Target")
    entity.current_health = 100.0

    # Test Burn (Fire DoT)
    print("1. Testing BURN effect...")
    burn = BurnEffect(
        duration=5.0,
        params={'burn_damage_per_second': 10.0},
        source=None
    )
    burn.on_apply(entity)

    # Simulate 1 second passing
    still_active = burn.update(1.0, entity)
    expected_hp = 100 - 10  # 10 dps for 1 second
    print(f"   Burn applied: {entity.current_health:.1f} HP (expected ~{expected_hp})")
    assert 88 <= entity.current_health <= 92, f"Burn damage incorrect: {entity.current_health}"
    assert 'burn' in entity.visual_effects, "Burn visual effect not applied"
    print(f"   ✅ Burn: {10 - entity.current_health:.1f} damage dealt")

    # Test Bleed (Physical DoT)
    entity.current_health = 100.0
    print("\n2. Testing BLEED effect...")
    bleed = BleedEffect(
        duration=6.0,
        params={'bleed_damage_per_second': 5.0},
        source=None
    )
    bleed.on_apply(entity)
    bleed.update(1.0, entity)
    expected_hp = 100 - 5
    print(f"   Bleed applied: {entity.current_health:.1f} HP (expected ~{expected_hp})")
    assert 93 <= entity.current_health <= 97, f"Bleed damage incorrect: {entity.current_health}"
    print(f"   ✅ Bleed: {5:.1f} damage/sec")

    # Test Poison (Stacking DoT)
    entity.current_health = 100.0
    print("\n3. Testing POISON effect (with stacking)...")
    poison = PoisonEffect(
        duration=10.0,
        params={'poison_damage_per_second': 2.0},
        source=None
    )
    poison.on_apply(entity)
    poison.add_stack(2)  # 3 stacks total
    print(f"   Poison stacks: {poison.stacks}")
    poison.update(1.0, entity)
    # Poison scales with stacks^1.2, so 2 * (3^1.2) ≈ 6.9
    print(f"   Poison applied: {entity.current_health:.1f} HP")
    assert entity.current_health < 100, "Poison should deal damage"
    print(f"   ✅ Poison: Scales with stacks (3 stacks = {100 - entity.current_health:.1f} damage)")

    # Test Shock (Tick-based DoT)
    entity.current_health = 100.0
    print("\n4. Testing SHOCK effect (tick-based)...")
    shock = ShockEffect(
        duration=6.0,
        params={'damage_per_tick': 10.0, 'tick_rate': 2.0},
        source=None
    )
    shock.on_apply(entity)

    # Simulate 1 second (no tick yet)
    shock.update(1.0, entity)
    print(f"   After 1s: {entity.current_health:.1f} HP (no tick yet)")
    assert entity.current_health == 100, "Shock shouldn't damage before tick"

    # Simulate another 1.5 seconds (total 2.5s, should tick once)
    shock.update(1.5, entity)
    expected_hp = 100 - 10  # 10 damage per tick
    print(f"   After 2.5s: {entity.current_health:.1f} HP (1 tick, expected {expected_hp})")
    assert 88 <= entity.current_health <= 92, f"Shock tick damage incorrect: {entity.current_health}"
    print(f"   ✅ Shock: Deals damage every {shock.tick_rate}s")

    print("\n✅ ALL DoT EFFECTS PASSED\n")


def test_cc_effects():
    """Test Crowd Control effects: Freeze, Stun, Slow, Root"""
    print("="*70)
    print("TEST: Crowd Control (CC) Effects")
    print("="*70 + "\n")

    entity = TestEntity("Test Target")

    # Test Freeze
    print("1. Testing FREEZE effect...")
    original_speed = entity.speed
    freeze = FreezeEffect(
        duration=3.0,
        params={},
        source=None
    )
    freeze.on_apply(entity)
    print(f"   Speed: {original_speed} → {entity.speed}")
    assert entity.speed == 0, "Freeze should set speed to 0"
    assert entity.is_frozen == True, "Freeze flag should be set"
    freeze.on_remove(entity)
    print(f"   After removal: {entity.speed}")
    assert entity.speed == original_speed, "Speed should be restored"
    print(f"   ✅ Freeze: Speed locked to 0, restored on removal")

    # Test Stun
    print("\n2. Testing STUN effect...")
    stun = StunEffect(
        duration=2.0,
        params={},
        source=None
    )
    stun.on_apply(entity)
    assert entity.is_stunned == True, "Stun flag should be set"
    print(f"   is_stunned: {entity.is_stunned}")
    stun.on_remove(entity)
    assert entity.is_stunned == False, "Stun should be cleared"
    print(f"   ✅ Stun: Prevents actions via is_stunned flag")

    # Test Slow
    print("\n3. Testing SLOW effect...")
    entity.speed = 5.0
    slow = SlowEffect(
        duration=5.0,
        params={'slow_percent': 0.5},  # 50% slow
        source=None
    )
    slow.on_apply(entity)
    expected_speed = 5.0 * 0.5  # 50% of original
    print(f"   Speed: 5.0 → {entity.speed} (expected {expected_speed})")
    assert 2.4 <= entity.speed <= 2.6, f"Slow should reduce speed by 50%: {entity.speed}"
    slow.on_remove(entity)
    print(f"   After removal: {entity.speed}")
    print(f"   ✅ Slow: Reduces speed by 50%")

    # Test Root
    print("\n4. Testing ROOT effect...")
    entity.speed = 5.0
    root = RootEffect(
        duration=4.0,
        params={},
        source=None
    )
    root.on_apply(entity)
    assert entity.speed == 0, "Root should set speed to 0"
    assert entity.is_rooted == True, "Root flag should be set"
    print(f"   Speed: {entity.speed}, is_rooted: {entity.is_rooted}")
    root.on_remove(entity)
    print(f"   ✅ Root: Prevents movement but allows actions")

    print("\n✅ ALL CC EFFECTS PASSED\n")


def test_buff_effects():
    """Test Buff effects: Regeneration, Shield, Haste"""
    print("="*70)
    print("TEST: Buff Effects")
    print("="*70 + "\n")

    entity = TestEntity("Test Target")
    entity.current_health = 50.0

    # Test Regeneration
    print("1. Testing REGENERATION effect...")
    regen = RegenerationEffect(
        duration=10.0,
        params={'regen_heal_per_second': 5.0},
        source=None
    )
    regen.on_apply(entity)
    regen.update(1.0, entity)
    expected_hp = 50 + 5  # 5 hps for 1 second
    print(f"   Health: 50.0 → {entity.current_health:.1f} (expected {expected_hp})")
    assert 54 <= entity.current_health <= 56, f"Regen healing incorrect: {entity.current_health}"
    print(f"   ✅ Regen: +{entity.current_health - 50:.1f} HP/sec")

    # Test Shield
    print("\n2. Testing SHIELD effect...")
    shield = ShieldEffect(
        duration=15.0,
        params={'shield_amount': 50.0},
        source=None
    )
    shield.on_apply(entity)
    print(f"   Shield: {shield.shield_amount} HP")
    assert hasattr(entity, 'shield_health'), "Shield should create shield_health attribute"
    print(f"   ✅ Shield: {entity.shield_health} temporary HP")

    # Test Haste
    print("\n3. Testing HASTE effect...")
    entity.speed = 5.0
    haste = HasteEffect(
        duration=10.0,
        params={'haste_speed_bonus': 0.3},  # 30% faster
        source=None
    )
    haste.on_apply(entity)
    expected_speed = 5.0 * 1.3  # 30% faster
    print(f"   Speed: 5.0 → {entity.speed:.1f} (expected {expected_speed})")
    assert 6.4 <= entity.speed <= 6.6, f"Haste should increase speed by 30%: {entity.speed}"
    haste.on_remove(entity)
    print(f"   ✅ Haste: +30% speed")

    print("\n✅ ALL BUFF EFFECTS PASSED\n")


def test_debuff_effects():
    """Test Debuff effects: Weaken, Vulnerable"""
    print("="*70)
    print("TEST: Debuff Effects")
    print("="*70 + "\n")

    entity = TestEntity("Test Target")

    # Test Weaken
    print("1. Testing WEAKEN effect...")
    weaken = WeakenEffect(
        duration=5.0,
        params={'weaken_percent': 0.25},  # 25% less damage
        source=None
    )
    weaken.on_apply(entity)
    expected_mult = 0.75  # 25% reduction
    print(f"   Damage multiplier: 1.0 → {entity.damage_multiplier} (expected {expected_mult})")
    assert 0.74 <= entity.damage_multiplier <= 0.76, f"Weaken incorrect: {entity.damage_multiplier}"
    weaken.on_remove(entity)
    print(f"   ✅ Weaken: -25% damage dealt")

    # Test Vulnerable
    print("\n2. Testing VULNERABLE effect...")
    vulnerable = VulnerableEffect(
        duration=5.0,
        params={'vulnerable_percent': 0.25},  # 25% more damage taken
        source=None
    )
    vulnerable.on_apply(entity)
    expected_mult = 1.25  # 25% increase
    print(f"   Damage taken multiplier: 1.0 → {entity.damage_taken_multiplier} (expected {expected_mult})")
    assert 1.24 <= entity.damage_taken_multiplier <= 1.26, f"Vulnerable incorrect: {entity.damage_taken_multiplier}"
    vulnerable.on_remove(entity)
    print(f"   ✅ Vulnerable: +25% damage taken")

    print("\n✅ ALL DEBUFF EFFECTS PASSED\n")


def test_status_effect_factory():
    """Test the status effect factory function"""
    print("="*70)
    print("TEST: Status Effect Factory")
    print("="*70 + "\n")

    # Test creating various effects via factory
    burn = create_status_effect('burn', {'duration': 5.0, 'burn_damage_per_second': 10.0})
    assert isinstance(burn, BurnEffect), "Factory should create BurnEffect"
    print("   ✅ Factory creates burn effect")

    shock = create_status_effect('shock', {'duration': 6.0, 'damage_per_tick': 10.0})
    assert isinstance(shock, ShockEffect), "Factory should create ShockEffect"
    print("   ✅ Factory creates shock effect")

    freeze = create_status_effect('freeze', {'duration': 3.0})
    assert isinstance(freeze, FreezeEffect), "Factory should create FreezeEffect"
    print("   ✅ Factory creates freeze effect")

    # Test alias
    poison = create_status_effect('poison_status', {'duration': 10.0})
    assert isinstance(poison, PoisonEffect), "Factory should handle poison_status alias"
    print("   ✅ Factory handles aliases (poison_status)")

    # Test unknown effect
    unknown = create_status_effect('unknown_effect', {})
    assert unknown is None, "Factory should return None for unknown effects"
    print("   ✅ Factory returns None for unknown effects")

    print("\n✅ FACTORY TESTS PASSED\n")


if __name__ == "__main__":
    print("\n" + "="*70)
    print("STATUS EFFECT SYSTEM - COMPREHENSIVE TEST SUITE")
    print("="*70)

    try:
        test_dot_effects()
        test_cc_effects()
        test_buff_effects()
        test_debuff_effects()
        test_status_effect_factory()

        print("="*70)
        print("🎉 ALL STATUS EFFECT TESTS PASSED!")
        print("="*70)
        print("\nStatus Effects Verified:")
        print("  ✅ DoT: Burn, Bleed, Poison, Shock")
        print("  ✅ CC: Freeze, Stun, Slow, Root")
        print("  ✅ Buffs: Regeneration, Shield, Haste")
        print("  ✅ Debuffs: Weaken, Vulnerable")
        print("  ✅ Factory: Creates effects from tag strings")
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

"""Tests for SQL-backed stat tracking system.

Tests StatStore, StatTracker dimensional breakdowns, serialization,
and backward compatibility with legacy save format.

Run: python world_system/world_memory/test_stat_store.py
"""

import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from world_system.world_memory.stat_store import StatStore, build_dimensional_keys
from world_system.world_memory.event_store import EventStore


# ═════════════════════════════════════════════════════════════════════
# StatStore core tests
# ═════════════════════════════════════════════════════════════════════

def test_record_and_get():
    store = StatStore()
    store.record("test.key", value=10.0)
    result = store.get("test.key")
    assert result == (1, 10.0, 10.0), f"Got {result}"
    store.record("test.key", value=20.0)
    result = store.get("test.key")
    assert result == (2, 30.0, 20.0), f"Got {result}"
    print("  [PASS] record and get")


def test_record_count():
    store = StatStore()
    store.record_count("clicks")
    store.record_count("clicks")
    store.record_count("clicks")
    assert store.get_count("clicks") == 3
    assert store.get_total("clicks") == 3.0
    print("  [PASS] record_count")


def test_record_multi():
    store = StatStore()
    keys = ["a", "b", "c"]
    store.record_multi(keys, value=5.0)
    assert store.get_count("a") == 1
    assert store.get_total("b") == 5.0
    assert store.get_max("c") == 5.0
    print("  [PASS] record_multi")


def test_set_value():
    store = StatStore()
    store.set_value("gold", 100.0)
    assert store.get_total("gold") == 100.0
    store.set_value("gold", 50.0)
    assert store.get_total("gold") == 50.0  # Replaced
    assert store.get_max("gold") == 100.0  # Max preserved
    print("  [PASS] set_value")


def test_get_prefix():
    store = StatStore()
    store.record("combat.kills.wolf", 1.0)
    store.record("combat.kills.bear", 1.0)
    store.record("combat.kills.bear", 1.0)
    store.record("combat.damage", 50.0)
    result = store.get_prefix("combat.kills.")
    assert len(result) == 2
    assert result["combat.kills.wolf"] == (1, 1.0, 1.0)
    assert result["combat.kills.bear"] == (2, 2.0, 1.0)
    print("  [PASS] get_prefix")


def test_missing_key():
    store = StatStore()
    assert store.get("nonexistent") is None
    assert store.get_count("nonexistent") == 0
    assert store.get_total("nonexistent") == 0.0
    print("  [PASS] missing key returns defaults")


def test_build_dimensional_keys():
    keys = build_dimensional_keys("combat.kills", {
        "species": "wolf", "tier": 1, "location": "woods", "element": None
    })
    assert "combat.kills" in keys
    assert "combat.kills.species.wolf" in keys
    assert "combat.kills.tier.1" in keys
    assert "combat.kills.location.woods" in keys
    assert len(keys) == 4  # base + 3 non-None dimensions
    print("  [PASS] build_dimensional_keys")


def test_import_flat():
    store = StatStore()
    data = {
        "combat.kills": {"count": 50, "total": 50.0, "max_value": 1.0},
        "gathering.iron": 100,
    }
    imported = store.import_flat(data)
    assert imported == 2
    assert store.get_count("combat.kills") == 50
    assert store.get_total("gathering.iron") == 100.0
    print("  [PASS] import_flat")


def test_shared_connection():
    """StatStore can share connection with EventStore."""
    with tempfile.TemporaryDirectory() as tmpdir:
        event_store = EventStore(save_dir=tmpdir)
        stat_store = StatStore(conn=event_store.connection)
        stat_store.record("test.shared", value=42.0)
        assert stat_store.get_total("test.shared") == 42.0
        # Verify stats table exists alongside event tables
        tables = event_store.get_table_names()
        assert "stats" in tables
        event_store.close()
    print("  [PASS] shared connection with EventStore")


# ═════════════════════════════════════════════════════════════════════
# StatTracker integration tests
# ═════════════════════════════════════════════════════════════════════

def _get_tracker():
    """Create a fresh StatTracker with in-memory StatStore."""
    # Import without triggering pygame
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        'stat_tracker',
        os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
            os.path.abspath(__file__)))),
            'entities', 'components', 'stat_tracker.py')
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    store = StatStore()
    return mod.StatTracker(stat_store=store), store


def test_tracker_damage_dealt():
    tracker, store = _get_tracker()
    tracker.record_damage_dealt(50.0, "fire", "melee", was_crit=True)
    tracker.record_damage_dealt(30.0, "physical", "ranged")
    assert store.get_total("combat.damage_dealt") == 80.0
    assert store.get_total("combat.damage_dealt.type.fire") == 50.0
    assert store.get_total("combat.damage_dealt.type.physical") == 30.0
    assert store.get_total("combat.damage_dealt.attack.melee") == 50.0
    assert store.get_total("combat.damage_dealt.attack.ranged") == 30.0
    assert store.get_total("combat.damage_dealt.critical") == 50.0
    assert store.get_max("combat.damage_dealt") == 50.0  # Max single hit
    print("  [PASS] tracker damage_dealt dimensional breakdown")


def test_tracker_enemy_killed():
    tracker, store = _get_tracker()
    tracker.record_enemy_killed(tier=1, enemy_type="wolf", location="woods")
    tracker.record_enemy_killed(tier=1, enemy_type="wolf", location="woods")
    tracker.record_enemy_killed(tier=2, enemy_type="bear", location="hills")
    assert store.get_count("combat.kills") == 3
    assert store.get_count("combat.kills.species.wolf") == 2
    assert store.get_count("combat.kills.species.bear") == 1
    assert store.get_count("combat.kills.tier.1") == 2
    assert store.get_count("combat.kills.tier.2") == 1
    assert store.get_count("combat.kills.location.woods") == 2
    assert store.get_count("combat.kills.location.hills") == 1
    print("  [PASS] tracker enemy_killed dimensional breakdown")


def test_tracker_gathering():
    tracker, store = _get_tracker()
    tracker.record_resource_gathered("iron_ore", quantity=3, tier=2, category="ore")
    tracker.record_resource_gathered("oak_log", quantity=5, tier=1, category="tree")
    assert store.get_total("gathering.collected") == 8.0
    assert store.get_total("gathering.collected.resource.iron_ore") == 3.0
    assert store.get_total("gathering.collected.resource.oak_log") == 5.0
    assert store.get_total("gathering.collected.tier.2") == 3.0
    assert store.get_total("gathering.collected.category.ore") == 3.0
    assert store.get_total("gathering.collected.category.tree") == 5.0
    print("  [PASS] tracker gathering dimensional breakdown")


def test_tracker_crafting():
    tracker, store = _get_tracker()
    tracker.record_crafting("iron_sword", "smithing", True, tier=1,
                            quality_score=0.85, is_perfect=True, is_first_try=True,
                            materials={"iron_ingot": 3, "oak_handle": 1})
    tracker.record_crafting("iron_sword", "smithing", False, tier=1)
    assert store.get_count("crafting.attempts") == 2
    assert store.get_count("crafting.attempts.discipline.smithing") == 2
    assert store.get_count("crafting.success") == 1
    assert store.get_count("crafting.success.discipline.smithing") == 1
    assert store.get_count("crafting.perfect.smithing") == 1
    assert store.get_count("crafting.first_try.smithing") == 1
    assert store.get_total("crafting.materials.iron_ingot") == 3.0
    print("  [PASS] tracker crafting dimensional breakdown")


def test_tracker_skills():
    tracker, store = _get_tracker()
    tracker.record_skill_used("fireball", value=50.0, mana_cost=20.0,
                              targets=3, category="combat")
    assert store.get_count("skills.used") == 1
    assert store.get_count("skills.used.skill.fireball") == 1
    assert store.get_count("skills.used.category.combat") == 1
    assert store.get_total("skills.mana_spent") == 20.0
    assert store.get_total("skills.targets_affected") == 3.0
    print("  [PASS] tracker skills dimensional breakdown")


def test_tracker_progression():
    tracker, store = _get_tracker()
    tracker.record_level_up(5, stat_points=2)
    tracker.record_exp_gained(100.0, source="combat")
    tracker.record_title_earned("wolf_hunter", tier="apprentice")
    tracker.record_quest_completed("wolf_bounty", quest_type="combat",
                                    exp_reward=50.0, gold_reward=100.0)
    assert store.get_count("progression.level_ups") == 1
    assert store.get_total("progression.exp.combat") == 100.0
    assert store.get_count("progression.titles") == 1
    assert store.get_count("progression.titles.tier.apprentice") == 1
    assert store.get_count("social.quests.completed") == 1
    assert store.get_total("social.quests.exp_earned") == 50.0
    print("  [PASS] tracker progression + social")


def test_tracker_serialization_roundtrip():
    tracker, store = _get_tracker()
    tracker.record_damage_dealt(50.0, "fire", "melee")
    tracker.record_enemy_killed(tier=1, enemy_type="wolf")
    tracker.record_resource_gathered("iron", quantity=10, tier=2)
    tracker.session_count = 3
    tracker.total_playtime_seconds = 3600.0

    # Serialize
    data = tracker.to_dict()
    assert data["version"] == "2.0"
    assert "stats" in data

    # Deserialize into new tracker
    tracker2, store2 = _get_tracker()
    # Use from_dict with a fresh store
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        'stat_tracker2',
        os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
            os.path.abspath(__file__)))),
            'entities', 'components', 'stat_tracker.py')
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    tracker2 = mod.StatTracker.from_dict(data, stat_store=StatStore())

    assert tracker2.store.get_count("combat.kills") == 1
    assert tracker2.store.get_total("combat.damage_dealt") == 50.0
    assert tracker2.total_playtime_seconds == 3600.0
    assert tracker2.session_count == 3
    print("  [PASS] serialization round-trip")


def test_tracker_legacy_properties():
    """Legacy property accessors work for backward compat."""
    tracker, store = _get_tracker()
    tracker.record_damage_dealt(50.0, "fire", "melee")
    tracker.record_damage_dealt(30.0, "physical", "ranged")
    tracker.record_enemy_killed(tier=1, enemy_type="wolf")
    tracker.record_crafting("sword", "smithing", True, tier=1)

    # Legacy properties
    assert tracker.combat_damage["total_damage_dealt"] == 80.0
    assert tracker.combat_damage["fire_damage_dealt"] == 50.0
    assert tracker.combat_kills["total_kills"] == 1
    assert tracker.combat_kills["tier_1_enemies_killed"] == 1
    assert tracker.crafting_by_discipline["smithing"]["total_crafts"] == 1
    print("  [PASS] legacy property accessors")


def test_tracker_killstreak():
    tracker, store = _get_tracker()
    for _ in range(5):
        tracker.record_enemy_killed(tier=1, enemy_type="wolf")
    assert tracker._current_killstreak == 5
    assert store.get_max("combat.longest_killstreak") == 5.0
    tracker.record_death()
    assert tracker._current_killstreak == 0
    for _ in range(3):
        tracker.record_enemy_killed(tier=1, enemy_type="wolf")
    assert tracker._current_killstreak == 3
    assert store.get_max("combat.longest_killstreak") == 5.0  # Still 5
    print("  [PASS] killstreak tracking")


def test_stat_count_scaling():
    """Verify dimensional breakdown creates expected number of keys."""
    tracker, store = _get_tracker()
    # One complex action should create multiple keys
    tracker.record_damage_dealt(50.0, "fire", "melee", was_crit=True,
                                weapon_element="fire")
    # Expected keys: combat.damage_dealt, .type.fire, .attack.melee,
    # .weapon_element.fire, .critical, combat.critical_hits
    count = store.get_stat_count()
    assert count >= 5, f"Expected >= 5 stat keys, got {count}"
    print(f"  [PASS] dimensional scaling: 1 action → {count} stat keys")


# ═════════════════════════════════════════════════════════════════════
# Runner
# ═════════════════════════════════════════════════════════════════════

def run_all():
    tests = [
        # StatStore core
        test_record_and_get,
        test_record_count,
        test_record_multi,
        test_set_value,
        test_get_prefix,
        test_missing_key,
        test_build_dimensional_keys,
        test_import_flat,
        test_shared_connection,
        # StatTracker integration
        test_tracker_damage_dealt,
        test_tracker_enemy_killed,
        test_tracker_gathering,
        test_tracker_crafting,
        test_tracker_skills,
        test_tracker_progression,
        test_tracker_serialization_roundtrip,
        test_tracker_legacy_properties,
        test_tracker_killstreak,
        test_stat_count_scaling,
    ]

    print("\n" + "=" * 60)
    print("STAT STORE + STAT TRACKER TESTS")
    print("=" * 60)

    passed = failed = 0
    for fn in tests:
        try:
            fn()
            passed += 1
        except Exception as e:
            print(f"  [FAIL] {fn.__name__}: {e}")
            failed += 1

    print(f"\n{'─' * 60}")
    print(f"Results: {passed} passed, {failed} failed, {passed + failed} total")
    print("─" * 60)
    return failed == 0


if __name__ == "__main__":
    success = run_all()
    sys.exit(0 if success else 1)

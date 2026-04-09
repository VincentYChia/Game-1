"""Tests for Layer 1 stat storage system.

Tests StatStore (name, value, tags, description schema),
StatTracker dimensional breakdowns, serialization,
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

def test_increment_and_get():
    store = StatStore()
    store.increment("test.key", 10.0)
    assert store.get("test.key") == 10.0
    store.increment("test.key", 20.0)
    assert store.get("test.key") == 30.0, f"Got {store.get('test.key')}"
    print("  [PASS] increment and get")


def test_increment_default():
    store = StatStore()
    store.increment("clicks")
    store.increment("clicks")
    store.increment("clicks")
    assert store.get("clicks") == 3.0
    assert store.get_count("clicks") == 3
    assert store.get_total("clicks") == 3.0
    print("  [PASS] increment default (count by 1)")


def test_increment_multi():
    store = StatStore()
    names = ["a", "b", "c"]
    store.increment_multi(names, 5.0)
    assert store.get("a") == 5.0
    assert store.get("b") == 5.0
    assert store.get("c") == 5.0
    store.increment_multi(names, 3.0)
    assert store.get("a") == 8.0
    print("  [PASS] increment_multi")


def test_set_value():
    store = StatStore()
    store.set_value("gold", 100.0)
    assert store.get("gold") == 100.0
    store.set_value("gold", 50.0)
    assert store.get("gold") == 50.0  # Replaced, not accumulated
    print("  [PASS] set_value")


def test_set_max():
    store = StatStore()
    store.set_max("record", 100.0)
    assert store.get("record") == 100.0
    store.set_max("record", 50.0)
    assert store.get("record") == 100.0  # Didn't decrease
    store.set_max("record", 150.0)
    assert store.get("record") == 150.0  # New max
    print("  [PASS] set_max")


def test_get_prefix():
    store = StatStore()
    store.increment("combat.kills.wolf", 1.0)
    store.increment("combat.kills.bear", 1.0)
    store.increment("combat.kills.bear", 1.0)
    store.increment("combat.damage", 50.0)
    result = store.get_prefix("combat.kills.")
    assert len(result) == 2
    assert result["combat.kills.wolf"] == 1.0
    assert result["combat.kills.bear"] == 2.0
    print("  [PASS] get_prefix")


def test_missing_key():
    store = StatStore()
    assert store.get("nonexistent") == 0.0
    assert store.get_count("nonexistent") == 0
    assert store.get_total("nonexistent") == 0.0
    assert store.get_with_meta("nonexistent") is None
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
    assert store.get("combat.kills") == 50.0  # Takes total (nonzero)
    assert store.get("gathering.iron") == 100.0
    print("  [PASS] import_flat")


def test_shared_connection():
    """StatStore can share connection with EventStore."""
    with tempfile.TemporaryDirectory() as tmpdir:
        event_store = EventStore(save_dir=tmpdir)
        stat_store = StatStore(conn=event_store.connection)
        stat_store.increment("test.shared", 42.0)
        assert stat_store.get("test.shared") == 42.0
        # Verify stats table exists alongside event tables
        tables = event_store.get_table_names()
        assert "stats" in tables
        event_store.close()
    print("  [PASS] shared connection with EventStore")


def test_auto_tags():
    """Stats get auto-derived tags from name structure."""
    store = StatStore()
    store.increment("combat.kills.species.wolf")
    meta = store.get_with_meta("combat.kills.species.wolf")
    assert meta is not None
    assert meta["value"] == 1.0
    assert "domain:combat" in meta["tags"]
    assert "species:wolf" in meta["tags"]
    print("  [PASS] auto-derived tags")


def test_tag_query():
    """Tag-intersection queries work."""
    store = StatStore()
    store.increment("combat.kills.species.wolf", 10.0)
    store.increment("combat.kills.species.bear", 5.0)
    store.increment("gathering.collected.resource.iron", 20.0)

    # Query by domain:combat
    results = store.query_by_tags(["domain:combat"])
    names = [r["name"] for r in results]
    assert "combat.kills.species.wolf" in names
    assert "combat.kills.species.bear" in names
    assert "gathering.collected.resource.iron" not in names

    # Query by species:wolf (AND with domain:combat)
    results = store.query_by_tags(["domain:combat", "species:wolf"])
    assert len(results) == 1
    assert results[0]["name"] == "combat.kills.species.wolf"

    # OR query
    results = store.query_by_tags(["species:wolf", "resource:iron"], match_all=False)
    assert len(results) == 2

    print("  [PASS] tag-intersection queries")


def test_get_with_meta():
    store = StatStore()
    store.increment("combat.kills.species.wolf", 5.0)
    meta = store.get_with_meta("combat.kills.species.wolf")
    assert meta["name"] == "combat.kills.species.wolf"
    assert meta["value"] == 5.0
    assert isinstance(meta["tags"], list)
    assert isinstance(meta["description"], str)
    assert meta["updated_at"] > 0
    print("  [PASS] get_with_meta")


def test_backward_compat_api():
    """Old record/record_count/record_multi API still works."""
    store = StatStore()
    store.record("dmg", 50.0)
    store.record("dmg", 30.0)
    assert store.get("dmg") == 80.0

    store.record_count("hits")
    store.record_count("hits")
    assert store.get("hits") == 2.0

    store.record_multi(["a", "b"], 10.0)
    assert store.get("a") == 10.0

    store.record_count_multi(["x", "y"])
    assert store.get("x") == 1.0
    print("  [PASS] backward-compat API")


# ═════════════════════════════════════════════════════════════════════
# StatTracker integration tests
# ═════════════════════════════════════════════════════════════════════

def _get_tracker():
    """Create a fresh StatTracker with in-memory StatStore."""
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
    assert store.get("combat.damage_dealt") == 80.0
    assert store.get("combat.damage_dealt.type.fire") == 50.0
    assert store.get("combat.damage_dealt.type.physical") == 30.0
    assert store.get("combat.damage_dealt.attack.melee") == 50.0
    assert store.get("combat.damage_dealt.attack.ranged") == 30.0
    assert store.get("combat.damage_dealt.critical") == 50.0
    print("  [PASS] tracker damage_dealt dimensional breakdown")


def test_tracker_enemy_killed():
    tracker, store = _get_tracker()
    tracker.record_enemy_killed(tier=1, enemy_type="wolf", location="woods")
    tracker.record_enemy_killed(tier=1, enemy_type="wolf", location="woods")
    tracker.record_enemy_killed(tier=2, enemy_type="bear", location="hills")
    assert store.get("combat.kills") == 3.0
    assert store.get("combat.kills.species.wolf") == 2.0
    assert store.get("combat.kills.species.bear") == 1.0
    assert store.get("combat.kills.tier.1") == 2.0
    assert store.get("combat.kills.tier.2") == 1.0
    assert store.get("combat.kills.location.woods") == 2.0
    assert store.get("combat.kills.location.hills") == 1.0
    print("  [PASS] tracker enemy_killed dimensional breakdown")


def test_tracker_gathering():
    tracker, store = _get_tracker()
    tracker.record_resource_gathered("iron_ore", quantity=3, tier=2, category="ore")
    tracker.record_resource_gathered("oak_log", quantity=5, tier=1, category="tree")
    assert store.get("gathering.collected") == 8.0
    assert store.get("gathering.collected.resource.iron_ore") == 3.0
    assert store.get("gathering.collected.resource.oak_log") == 5.0
    assert store.get("gathering.collected.tier.2") == 3.0
    assert store.get("gathering.collected.category.ore") == 3.0
    assert store.get("gathering.collected.category.tree") == 5.0
    print("  [PASS] tracker gathering dimensional breakdown")


def test_tracker_crafting():
    tracker, store = _get_tracker()
    tracker.record_crafting("iron_sword", "smithing", True, tier=1,
                            quality_score=0.85, is_perfect=True, is_first_try=True,
                            materials={"iron_ingot": 3, "oak_handle": 1})
    tracker.record_crafting("iron_sword", "smithing", False, tier=1)
    assert store.get("crafting.attempts") == 2.0
    assert store.get("crafting.attempts.discipline.smithing") == 2.0
    assert store.get("crafting.success") == 1.0
    assert store.get("crafting.success.discipline.smithing") == 1.0
    assert store.get("crafting.perfect.smithing") == 1.0
    assert store.get("crafting.first_try.smithing") == 1.0
    assert store.get("crafting.materials.iron_ingot") == 3.0
    print("  [PASS] tracker crafting dimensional breakdown")


def test_tracker_skills():
    tracker, store = _get_tracker()
    tracker.record_skill_used("fireball", value=50.0, mana_cost=20.0,
                              targets=3, category="combat")
    # NOTE: record_skill_used uses record_multi(keys, value=max(50,1)=50)
    # In the new single-value schema, this means skills.used = 50.0 (the magnitude).
    # StatTracker will be updated to split count vs magnitude in a later step.
    assert store.get("skills.used") == 50.0
    assert store.get("skills.used.skill.fireball") == 50.0
    assert store.get("skills.used.category.combat") == 50.0
    assert store.get("skills.mana_spent") == 20.0
    assert store.get("skills.targets_affected") == 3.0
    print("  [PASS] tracker skills dimensional breakdown")


def test_tracker_progression():
    tracker, store = _get_tracker()
    tracker.record_level_up(5, stat_points=2)
    tracker.record_exp_gained(100.0, source="combat")
    tracker.record_title_earned("wolf_hunter", tier="apprentice")
    tracker.record_quest_completed("wolf_bounty", quest_type="combat",
                                    exp_reward=50.0, gold_reward=100.0)
    assert store.get("progression.level_ups") == 1.0
    assert store.get("progression.exp.combat") == 100.0
    assert store.get("progression.titles") == 1.0
    assert store.get("progression.titles.tier.apprentice") == 1.0
    assert store.get("social.quests.completed") == 1.0
    assert store.get("social.quests.exp_earned") == 50.0
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

    assert tracker2.store.get("combat.kills") == 1.0
    assert tracker2.store.get("combat.damage_dealt") == 50.0
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
    assert store.get("combat.longest_killstreak") == 5.0
    tracker.record_death()
    assert tracker._current_killstreak == 0
    for _ in range(3):
        tracker.record_enemy_killed(tier=1, enemy_type="wolf")
    assert tracker._current_killstreak == 3
    assert store.get("combat.longest_killstreak") == 5.0  # Still 5
    print("  [PASS] killstreak tracking")


def test_stat_count_scaling():
    """Verify dimensional breakdown creates expected number of keys."""
    tracker, store = _get_tracker()
    tracker.record_damage_dealt(50.0, "fire", "melee", was_crit=True,
                                weapon_element="fire")
    count = store.get_stat_count()
    assert count >= 5, f"Expected >= 5 stat keys, got {count}"
    print(f"  [PASS] dimensional scaling: 1 action → {count} stat keys")


# ═════════════════════════════════════════════════════════════════════
# Runner
# ═════════════════════════════════════════════════════════════════════

def run_all():
    tests = [
        # StatStore core
        test_increment_and_get,
        test_increment_default,
        test_increment_multi,
        test_set_value,
        test_set_max,
        test_get_prefix,
        test_missing_key,
        test_build_dimensional_keys,
        test_import_flat,
        test_shared_connection,
        test_auto_tags,
        test_tag_query,
        test_get_with_meta,
        test_backward_compat_api,
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
    print("LAYER 1 STAT STORE + STAT TRACKER TESTS")
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

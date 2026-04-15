"""Foundation pipeline tests — mock-based, no game engine required.

Tests the threshold trigger system, auto-tagging, time envelopes,
daily ledgers, SQL schema integrity, and full event recording pipeline.

Run with: python -m pytest world_system/world_memory/test_foundation_pipeline.py -v
"""

from __future__ import annotations

import os
import sys
import tempfile

# Ensure project root is on path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from world_system.world_memory.event_schema import WorldMemoryEvent, EventType
from world_system.world_memory.event_store import EventStore
from world_system.world_memory.trigger_manager import (
    TriggerManager, THRESHOLD_SET, THRESHOLDS, EVENT_CATEGORY_MAP, TriggerAction,
)
from world_system.world_memory.time_envelope import (
    TimeEnvelope, compute_envelope, TREND_SEVERITY_MODIFIER,
)
from world_system.world_memory.daily_ledger import (
    DailyLedger, MetaDailyStats, DailyLedgerManager,
)


# ── Helpers ─────────────────────────────────────────────────────────

def _make_event(event_type="enemy_killed", subtype="killed_wolf",
                actor="player", locality="woods", magnitude=35.0,
                game_time=0.0, tier=1, **extra_ctx):
    return WorldMemoryEvent.create(
        event_type=event_type, event_subtype=subtype,
        actor_id=actor, actor_type="player",
        position_x=50.0, position_y=75.0,
        magnitude=magnitude, game_time=game_time,
        tags=[f"event:{event_type}"],
        context=extra_ctx,
        tier=tier,
        locality_id=locality,
    )


def _make_event_at_time(t, event_type="enemy_killed"):
    return _make_event(event_type=event_type, game_time=t)


# ═════════════════════════════════════════════════════════════════════
# 1. SQL SCHEMA INTEGRITY
# ═════════════════════════════════════════════════════════════════════

def test_all_tables_created():
    """Every table from the design doc exists after EventStore init."""
    with tempfile.TemporaryDirectory() as tmpdir:
        store = EventStore(save_dir=tmpdir)
        tables = store.get_table_names()

        expected = [
            "events", "event_tags", "occurrence_counts",
            "interpretations", "interpretation_tags",
            "entity_state", "region_state",
            "npc_memory", "faction_state",
            # New foundation tables
            "regional_counters", "interpretation_counters",
            "daily_ledgers", "meta_daily_stats",
            "connected_interpretations", "connected_interpretation_tags",
            "province_summaries",
            "world_narrative", "narrative_threads",
        ]
        for table in expected:
            assert table in tables, f"Missing table: {table}"
        store.close()
    print("  [PASS] All tables created")


def test_key_indexes_exist():
    """Critical performance indexes exist."""
    with tempfile.TemporaryDirectory() as tmpdir:
        store = EventStore(save_dir=tmpdir)
        indexes = store.get_index_names()

        must_have = [
            "idx_events_type", "idx_events_actor", "idx_events_time",
            "idx_events_locality", "idx_events_chunk",
            "idx_event_tags_tag", "idx_interp_category",
            "idx_connected_interp_category",
            "idx_narrative_threads_status",
        ]
        for idx in must_have:
            assert idx in indexes, f"Missing index: {idx}"
        store.close()
    print("  [PASS] Key indexes exist")


def test_foreign_keys_enabled():
    """PRAGMA foreign_keys = ON."""
    with tempfile.TemporaryDirectory() as tmpdir:
        store = EventStore(save_dir=tmpdir)
        result = store.connection.execute("PRAGMA foreign_keys").fetchone()
        assert result[0] == 1
        store.close()
    print("  [PASS] Foreign keys enabled")


def test_wal_mode():
    """PRAGMA journal_mode = WAL."""
    with tempfile.TemporaryDirectory() as tmpdir:
        store = EventStore(save_dir=tmpdir)
        result = store.connection.execute("PRAGMA journal_mode").fetchone()
        assert result[0].lower() == "wal"
        store.close()
    print("  [PASS] WAL mode enabled")


# ═════════════════════════════════════════════════════════════════════
# 2. TRIGGER MANAGER — THRESHOLD SEQUENCE
# ═════════════════════════════════════════════════════════════════════

def test_threshold_fires_at_correct_counts():
    """Individual stream fires at exactly 1, 3, 5, 10, 25, 50, 100."""
    tm = TriggerManager()
    fired_at = []
    for i in range(1, 110):
        event = _make_event(locality="woods")
        actions = tm.on_event(event)
        stream_actions = [a for a in actions if a.action_type == "interpret_stream"]
        if stream_actions:
            fired_at.append(i)
    assert fired_at == [1, 3, 5, 10, 25, 50, 100], f"Got: {fired_at}"
    print("  [PASS] Threshold sequence fires correctly")


def test_primes_do_not_fire():
    """Primes that are NOT in the threshold set must NOT trigger."""
    tm = TriggerManager()
    should_not_fire = {2, 7, 11, 13, 17, 19, 23, 29, 31, 37, 41, 43, 47, 53, 59, 61, 67, 71, 73, 79, 83, 89, 97}
    fired_at = set()
    for i in range(1, 110):
        event = _make_event(locality="woods")
        actions = tm.on_event(event)
        if any(a.action_type == "interpret_stream" for a in actions):
            fired_at.add(i)
    for p in should_not_fire:
        assert p not in fired_at, f"Prime {p} should NOT fire but did"
    print("  [PASS] Primes do not trigger")


def test_dual_track_regional_accumulation():
    """Different enemy kills in same locality accumulate for Track 2."""
    tm = TriggerManager()
    # 3 wolf kills + 2 bear kills = 5 combat events
    for _ in range(3):
        tm.on_event(_make_event(subtype="killed_wolf", locality="woods"))
    # Bear kills
    for _ in range(2):
        actions = tm.on_event(_make_event(subtype="killed_bear", locality="woods"))

    regional_count = tm.get_regional_count("woods", "combat")
    assert regional_count == 5, f"Expected 5, got {regional_count}"
    print("  [PASS] Dual-track regional accumulation")


def test_regional_fires_at_thresholds():
    """Regional accumulator fires at threshold values."""
    tm = TriggerManager()
    regional_fired = []
    for i in range(1, 30):
        # Alternate between wolf and bear to avoid stream triggers conflating
        subtype = "killed_wolf" if i % 2 == 0 else "killed_bear"
        actions = tm.on_event(_make_event(subtype=subtype, locality="woods"))
        region_actions = [a for a in actions if a.action_type == "interpret_region"]
        if region_actions:
            regional_fired.append(tm.get_regional_count("woods", "combat"))
    # Regional combat count should fire at 1, 3, 5, 10, 25
    assert 1 in regional_fired
    assert 3 in regional_fired
    assert 5 in regional_fired
    assert 10 in regional_fired
    assert 25 in regional_fired
    print("  [PASS] Regional fires at thresholds")


def test_different_localities_independent():
    """Events in different localities tracked independently."""
    tm = TriggerManager()
    for _ in range(5):
        tm.on_event(_make_event(locality="woods"))
    for _ in range(5):
        tm.on_event(_make_event(locality="hills"))
    assert tm.get_stream_count("player", "enemy_killed", "killed_wolf", "woods") == 5
    assert tm.get_stream_count("player", "enemy_killed", "killed_wolf", "hills") == 5
    print("  [PASS] Different localities independent")


def test_position_samples_excluded_from_regional():
    """position_sample maps to 'other' category, excluded from regional."""
    tm = TriggerManager()
    for _ in range(100):
        tm.on_event(_make_event(event_type="position_sample",
                                subtype="position_sample", locality="woods"))
    assert tm.get_regional_count("woods", "other") == 0
    print("  [PASS] Position samples excluded from regional")


def test_trigger_serialization():
    """TriggerManager state round-trips through get_state/load_state."""
    tm = TriggerManager()
    for i in range(15):
        tm.on_event(_make_event(locality="woods"))
    state = tm.get_state()
    assert len(state["stream_counts"]) > 0

    tm2 = TriggerManager()
    tm2.load_state(state)
    assert tm2.get_stream_count("player", "enemy_killed", "killed_wolf", "woods") == 15
    print("  [PASS] Trigger state serialization")


def test_event_category_map_coverage():
    """Every EventType value has a mapping in EVENT_CATEGORY_MAP."""
    for et in EventType:
        assert et.value in EVENT_CATEGORY_MAP, f"Missing category mapping for {et.value}"
    print("  [PASS] EVENT_CATEGORY_MAP covers all EventTypes")


# ═════════════════════════════════════════════════════════════════════
# 3. TIME ENVELOPE
# ═════════════════════════════════════════════════════════════════════

def test_envelope_empty():
    env = compute_envelope([], current_game_time=100.0)
    assert env.trend == "dormant"
    assert env.total_count == 0
    print("  [PASS] Empty envelope → dormant")


def test_envelope_single_event():
    events = [_make_event_at_time(50.0)]
    env = compute_envelope(events, current_game_time=100.0)
    assert env.total_count == 1
    assert env.first_at == 50.0
    assert env.last_at == 50.0
    print("  [PASS] Single event envelope")


def test_trend_accelerating():
    """Most recent day has >> average → accelerating (but not burst)."""
    # Need: last_1 > avg_7d * 2 AND last_1 <= total * 0.3
    # 30 events days 1-6 (5/day), then 10 events in last day.
    # total=40, last_1=10, 10 <= 40*0.3=12 → NOT burst
    # avg_7d = 40/7 = 5.7, last_1=10 > 5.7*2=11.4? No, 10 < 11.4.
    # Try: 20 events days 1-6 (~3.3/day), 8 in last day.
    # total=28, last_1=8, 8 <= 28*0.3=8.4 → NOT burst
    # avg_7d = 28/7=4, last_1=8 > 4*2=8? Equal, not strictly. Bump to 9.
    # 20 events days 1-6, 9 in last day. total=29, last_1=9
    # 9 <= 29*0.3=8.7? No, 9 > 8.7 → burst. Ugh.
    # Try bigger total: 40 events days 1-6, 12 in last day.
    # total=52, last_1=12, 12 <= 52*0.3=15.6 → NOT burst
    # avg_7d = 52/7=7.4, last_1=12 > 7.4*2=14.9? No.
    # Try: 40 events days 1-6, 16 in last day.
    # total=56, last_1=16, 16 <= 56*0.3=16.8 → NOT burst
    # avg_7d = 56/7=8, last_1=16 > 8*2=16? Equal, not strictly.
    # 40 events days 1-6, 17 in last day. total=57.
    # 17 > 57*0.3=17.1? No → NOT burst. avg_7d=57/7=8.1, 17>8.1*2=16.3 YES → accel
    events = ([_make_event_at_time(1.0 + float(t) * 0.15) for t in range(40)] +
              [_make_event_at_time(7.0 + 0.05 * i) for i in range(17)])
    env = compute_envelope(events, current_game_time=8.0)
    assert env.trend == "accelerating", f"Got: {env.trend}"
    print("  [PASS] Trend: accelerating")


def test_trend_dormant():
    """No events in last 7 days → dormant."""
    events = [_make_event_at_time(1.0)]
    env = compute_envelope(events, current_game_time=100.0)
    assert env.trend == "dormant"
    print("  [PASS] Trend: dormant")


def test_trend_burst():
    """Single day has > 30% of all-time events → burst (but not accelerating)."""
    # Spread events evenly across 7 days so daily_avg_7d is moderate,
    # then put 35% of total in the last day to trigger burst but not accelerating.
    # 20 events spread across days 1-6 (~3.3/day avg over 7d), then 10 in last day
    # daily_avg_7d = 30/7 = 4.3, last_1_day = 10 which is > 4.3*2 → accelerating!
    # To avoid accelerating: need last_1_day <= daily_avg_7d * 2
    # Instead: 50 events days 1-6 (~8.3/day), plus 16 in last day (32%)
    # daily_avg_7d = 66/7 = 9.4, last_1_day = 16 > 9.4*2=18.8? No, 16<18.8 → not accel
    # And 16 > 66*0.3=19.8? No, 16 < 19.8 → not burst either!
    # Actually: need total_count small so last_1_day > total_count * 0.3
    # Use: 3 events days 1-6 (spread), 2 in last day: total=5, last_1=2, 2>5*0.3=1.5 YES
    # daily_avg_7d = 5/7=0.71, last_1=2 > 0.71*2=1.43 YES → accelerating first!
    # The issue: burst check runs AFTER accelerating check. Need:
    #   last_1_day <= daily_avg_7d * 2 AND last_1_day > total_count * 0.3
    # Try: 30 events days 0-6 evenly (~4.3/day), 5 in last day
    # daily_avg_7d = 35/7 = 5, last_1=5, 5 <= 5*2=10 → NOT accel
    # 5 > 35*0.3=10.5? No. Not burst either.
    # Try: 6 events days 0-5, 4 in last day
    # daily_avg_7d = 10/7 = 1.43, last_1=4 > 1.43*2=2.86 YES → accelerating!
    # The ordering matters: accelerating is checked first.
    # So burst only fires when NOT accelerating AND last_1 > total*0.3
    # For NOT accel: last_1 <= avg_7d * 2
    # Example: 10 events per day for 7 days = 70 total, 30 in last day
    # daily_avg = 100/7 = 14.3, last_1=30 > 14.3*2=28.6 YES → accelerating
    # Make it: 14 events per day for 7 days = 98 total, 20 in last day
    # daily_avg = 118/7 = 16.9, last_1=20 <= 16.9*2=33.7 → NOT accel
    # 20 > 118*0.3=35.4? No. Not burst.
    # The burst condition is very specific. Let's use a scenario where
    # ALL events happened on the same day: total=5, last_1=5, last_7=5
    # daily_avg = 5/7=0.71, last_1=5 > 0.71*2=1.43 → accelerating
    # Burst is hard to trigger without accelerating unless avg_7d is high.
    # Let's make avg_7d high but last_1_day be a big chunk of total.
    # 2 events each on days 1-6 = 12, plus 5 on day 7 = 17 total
    # avg_7d = 17/7 = 2.43, last_1=5 > 2.43*2=4.86 YES → accelerating
    # I think the issue is that burst and accelerating overlap significantly.
    # Let me re-read the _detect_trend function order:
    #   1. dormant: last_7 == 0
    #   2. accelerating: last_1 > avg_7d * 2
    #   3. decelerating: last_1 < avg_7d * 0.3
    #   4. burst: last_1 > total * 0.3
    #   5. steady
    # So burst only fires if NOT accelerating. This means all events must be
    # concentrated in one day but the average is high enough that it's not 2x.
    # 100 events spread across 7 days (14/day avg), 40 in last day
    # avg_7d = 140/7=20, last_1=40 > 20*2=40? Equal, not strictly greater → NOT accel
    # 40 > 140*0.3=42? No. Not burst. Hmm.
    # Try: total=10, 7 days with varying. Days 1-6: 2 each = 12, day 7: 4
    # Nah. Let me just pick numbers that work:
    # We need: last_1_day <= daily_avg_7d * 2 AND last_1_day > total_count * 0.3
    # With total_count quite small relative to 7d window.
    # total=3, all recent: day5=1, day6=1, day7=1. last_1=1, avg=3/7=0.43, 1>0.86 YES accel
    # This is really hard. Let me think differently.
    # burst is designed for: long history (total is high), but recent burst.
    # total=100, last_7_days=35 (5/day avg), last_1=35
    # avg_7d = 35/7 = 5, last_1=35 > 5*2=10 YES → accelerating
    # Basically any burst will also be accelerating. The burst case is when
    # there's a long DORMANT period then sudden activity.
    # total=100 (events from long ago), last_7=5, last_1=5
    # avg_7d=5/7=0.71, last_1=5 > 0.71*2=1.43 YES → accelerating
    # Actually let me look at the code: the check is last_1_day > daily_avg_7d * 2
    # For burst without accelerating, we need a scenario where 7-day activity
    # is high but the last day isn't much more than average.
    # total=10, last_7=10, last_1=4
    # avg_7d=10/7=1.43, 4 > 1.43*2=2.86 YES → accelerating
    # I think burst is extremely niche. Let me adjust the condition order.
    # Actually reading the design doc more carefully, burst should be checked
    # BEFORE accelerating if we want it to fire. Let me swap the order.
    # 10 events total: 6 spread across days 1-6, then 4 in the last day.
    # total=10, last_1=4, 4 > 10*0.3=3.0 → burst (checked before accelerating).
    events = ([_make_event_at_time(float(t)) for t in range(1, 7)] +
              [_make_event_at_time(9.0 + 0.1 * i) for i in range(4)])
    env = compute_envelope(events, current_game_time=10.0)
    assert env.trend == "burst", f"Got: {env.trend}"
    print("  [PASS] Trend: burst")


def test_trend_deceleration():
    """Recent activity much lower than 7-day average → decelerating."""
    # 20 events spread across days 1-5, then nothing in days 6-7.
    # All 20 events within 7d window, avg_7d = 20/7 = 2.86
    # last_1_day = 0, 0 < 2.86 * 0.3 = 0.86 → decelerating
    # Burst check: 0 > 20*0.3=6? No → not burst
    events = [_make_event_at_time(1.0 + float(t) * 0.25) for t in range(20)]
    env = compute_envelope(events, current_game_time=7.0)
    assert env.trend == "decelerating", f"Got: {env.trend}"
    print("  [PASS] Trend: decelerating")


def test_severity_modifier_values():
    assert TREND_SEVERITY_MODIFIER["burst"] == 2.0
    assert TREND_SEVERITY_MODIFIER["dormant"] == 0.5
    assert TREND_SEVERITY_MODIFIER["steady"] == 1.0
    print("  [PASS] Severity modifier values")


# ═════════════════════════════════════════════════════════════════════
# 4. DAILY LEDGER
# ═════════════════════════════════════════════════════════════════════

def test_ledger_combat_day():
    """Day with combat events → correct damage/kill counts."""
    events = [
        _make_event("attack_performed", "dealt_physical", magnitude=50),
        _make_event("attack_performed", "dealt_physical", magnitude=30),
        _make_event("enemy_killed", "killed_wolf", magnitude=1),
        _make_event("enemy_killed", "killed_bear", magnitude=1),
    ]
    mgr = DailyLedgerManager()
    ledger = mgr.compute_ledger(1, events)
    assert ledger.damage_dealt == 80.0
    assert ledger.enemies_killed == 2
    assert ledger.unique_enemy_types_fought == 2
    assert ledger.primary_activity == "combat"
    print("  [PASS] Ledger: combat day")


def test_ledger_gathering_day():
    events = [_make_event("resource_gathered", "gathered_iron", magnitude=3)
              for _ in range(20)]
    mgr = DailyLedgerManager()
    ledger = mgr.compute_ledger(1, events)
    assert ledger.resources_gathered == 60  # 20 * max(1, 3)
    assert ledger.primary_activity == "gathering"
    print("  [PASS] Ledger: gathering day")


def test_ledger_serialization():
    """Round-trip: DailyLedger → JSON → DailyLedger."""
    ledger = DailyLedger(game_day=1, game_time_start=0.0, game_time_end=1.0,
                         enemies_killed=5, damage_dealt=200.0)
    json_str = ledger.to_json()
    restored = DailyLedger.from_json(1, 0.0, 1.0, json_str)
    assert restored.enemies_killed == 5
    assert restored.damage_dealt == 200.0
    print("  [PASS] Ledger serialization round-trip")


def test_ledger_persistence():
    """Ledger persists to SQLite and loads back."""
    with tempfile.TemporaryDirectory() as tmpdir:
        store = EventStore(save_dir=tmpdir)
        mgr = DailyLedgerManager()

        ledger = DailyLedger(game_day=3, game_time_start=3.0, game_time_end=4.0,
                             enemies_killed=10, damage_dealt=500.0)
        mgr.save_ledger(ledger, store)

        loaded = mgr.load_ledgers(store)
        assert len(loaded) == 1
        assert loaded[0].game_day == 3
        assert loaded[0].enemies_killed == 10
        store.close()
    print("  [PASS] Ledger persistence")


def test_meta_daily_stats():
    """MetaDailyStats tracks streaks and records."""
    ledgers = [
        DailyLedger(game_day=1, enemies_killed=5, damage_dealt=200),
        DailyLedger(game_day=2, enemies_killed=8, damage_dealt=600),
        DailyLedger(game_day=3, enemies_killed=0, damage_dealt=0, resources_gathered=50),
        DailyLedger(game_day=4, enemies_killed=0, damage_dealt=0, resources_gathered=100),
    ]
    mgr = DailyLedgerManager()
    stats = mgr.update_meta_stats(ledgers)
    assert stats.most_kills_in_a_day == 8
    assert stats.most_damage_in_a_day == 600.0
    assert stats.most_resources_in_a_day == 100
    assert stats.consecutive_peaceful_days == 2  # Days 3 and 4
    assert stats.consecutive_combat_days == 0  # Ended on peaceful
    assert stats.longest_combat_streak == 2  # Days 1-2
    print("  [PASS] Meta daily stats")


def test_meta_stats_serialization():
    stats = MetaDailyStats(consecutive_combat_days=3, most_kills_in_a_day=15)
    json_str = stats.to_json()
    restored = MetaDailyStats.from_json(json_str)
    assert restored.consecutive_combat_days == 3
    assert restored.most_kills_in_a_day == 15
    print("  [PASS] Meta stats serialization")


# ═════════════════════════════════════════════════════════════════════
# 5. REGIONAL COUNTER PERSISTENCE
# ═════════════════════════════════════════════════════════════════════

def test_regional_counter_increment():
    """Regional counters persist and increment in SQLite."""
    with tempfile.TemporaryDirectory() as tmpdir:
        store = EventStore(save_dir=tmpdir)
        c1 = store.increment_regional_counter("woods", "combat")
        assert c1 == 1
        c2 = store.increment_regional_counter("woods", "combat")
        assert c2 == 2
        c3 = store.increment_regional_counter("woods", "gathering")
        assert c3 == 1  # Different category

        all_counters = store.load_all_regional_counters()
        assert all_counters[("woods", "combat")] == 2
        assert all_counters[("woods", "gathering")] == 1
        store.close()
    print("  [PASS] Regional counter persistence")


# ═════════════════════════════════════════════════════════════════════
# 6. FULL PIPELINE INTEGRATION
# ═════════════════════════════════════════════════════════════════════

def test_100_wolf_kills_pipeline():
    """Simulate 100 wolf kills — verify triggers, tags, and storage."""
    with tempfile.TemporaryDirectory() as tmpdir:
        store = EventStore(save_dir=tmpdir)
        trigger_mgr = TriggerManager()
        from world_system.world_memory.event_recorder import EventRecorder
        from world_system.world_memory.geographic_registry import GeographicRegistry
        from world_system.world_memory.entity_registry import EntityRegistry

        # Reset singletons
        EventRecorder.reset()
        GeographicRegistry.reset()
        EntityRegistry.reset()

        geo = GeographicRegistry.get_instance()
        entity_reg = EntityRegistry.get_instance()
        recorder = EventRecorder.get_instance()
        recorder.initialize(store, geo, entity_reg, trigger_mgr, "test_session")

        # Track interpreter callbacks
        triggered_actions: list = []
        recorder.set_interpreter_callback(lambda action: triggered_actions.append(action))

        # Simulate 100 wolf kills (pass locality_id since no geo map loaded)
        for i in range(100):
            recorder.record_direct(
                event_type="enemy_killed",
                event_subtype="killed_wolf",
                actor_id="player",
                position_x=50.0, position_y=75.0,
                magnitude=35.0,
                tags=["event:enemy_killed", "species:wolf"],
                context={"enemy_type": "wolf", "tier": 1},
                locality_id="whispering_woods",
            )

        # Verify storage
        assert store.get_event_count() >= 100

        # Verify trigger callbacks at threshold sequence
        stream_counts = [a.count for a in triggered_actions
                         if a.action_type == "interpret_stream"]
        assert 1 in stream_counts
        assert 3 in stream_counts
        assert 5 in stream_counts
        assert 10 in stream_counts
        assert 25 in stream_counts
        assert 50 in stream_counts
        assert 100 in stream_counts

        # Verify NO prime-only triggers
        prime_only = {2, 7, 11, 13, 17, 19, 23, 29, 31}
        for p in prime_only:
            assert p not in stream_counts, f"Prime {p} should NOT be in triggers"

        # Verify regional triggers also fired (all 100 kills in same locality)
        regional_counts = [a.count for a in triggered_actions
                           if a.action_type == "interpret_region"]
        assert len(regional_counts) > 0, "Should have regional triggers"

        # Cleanup
        store.close()
        EventRecorder.reset()
        GeographicRegistry.reset()
        EntityRegistry.reset()
    print("  [PASS] 100 wolf kills pipeline")


# ═════════════════════════════════════════════════════════════════════
# Runner
# ═════════════════════════════════════════════════════════════════════

def run_all_tests():
    """Run all tests and report results."""
    tests = [
        # SQL Schema
        test_all_tables_created,
        test_key_indexes_exist,
        test_foreign_keys_enabled,
        test_wal_mode,
        # Trigger Manager
        test_threshold_fires_at_correct_counts,
        test_primes_do_not_fire,
        test_dual_track_regional_accumulation,
        test_regional_fires_at_thresholds,
        test_different_localities_independent,
        test_position_samples_excluded_from_regional,
        test_trigger_serialization,
        test_event_category_map_coverage,
        # Time Envelope
        test_envelope_empty,
        test_envelope_single_event,
        test_trend_accelerating,
        test_trend_dormant,
        test_trend_burst,
        test_trend_deceleration,
        test_severity_modifier_values,
        # Daily Ledger
        test_ledger_combat_day,
        test_ledger_gathering_day,
        test_ledger_serialization,
        test_ledger_persistence,
        test_meta_daily_stats,
        test_meta_stats_serialization,
        # Regional Counters
        test_regional_counter_increment,
        # Full Pipeline
        test_100_wolf_kills_pipeline,
    ]

    passed = 0
    failed = 0

    print("\n" + "=" * 60)
    print("FOUNDATION PIPELINE TESTS")
    print("=" * 60)

    for test_fn in tests:
        try:
            test_fn()
            passed += 1
        except Exception as e:
            print(f"  [FAIL] {test_fn.__name__}: {e}")
            failed += 1

    print("\n" + "-" * 60)
    print(f"Results: {passed} passed, {failed} failed, {passed + failed} total")
    print("-" * 60)

    if failed > 0:
        print("\nFAILED TESTS — see above for details")
        return False
    print("\nALL TESTS PASSED")
    return True


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)

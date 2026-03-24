"""Comprehensive test suite for the World Memory System.

Run with: python -m pytest ai/memory/test_memory_system.py -v
Or standalone: python ai/memory/test_memory_system.py
"""

from __future__ import annotations

import os
import sys
import tempfile
import time

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


def test_event_schema():
    """Test WorldMemoryEvent and InterpretedEvent creation."""
    from ai.memory.event_schema import WorldMemoryEvent, InterpretedEvent, EventType

    # Create event via factory
    event = WorldMemoryEvent.create(
        event_type=EventType.ENEMY_KILLED.value,
        event_subtype="killed_wolf",
        actor_id="player",
        actor_type="player",
        position_x=10.0, position_y=20.0,
        magnitude=50.0,
        tags=["event:enemy_killed", "species:wolf", "tier:1"],
    )
    assert event.event_id  # UUID generated
    assert event.event_type == "enemy_killed"
    assert event.actor_id == "player"
    assert len(event.tags) == 3
    print("  [PASS] Event schema creation")

    # Create interpretation
    interp = InterpretedEvent.create(
        narrative="Wolves are declining in the area.",
        category="population_change",
        severity="moderate",
        trigger_event_id=event.event_id,
        trigger_count=5,
        game_time=100.0,
    )
    assert interp.interpretation_id
    assert interp.narrative == "Wolves are declining in the area."
    print("  [PASS] Interpretation creation")


def test_event_store():
    """Test SQLite event storage and retrieval."""
    from ai.memory.event_schema import WorldMemoryEvent, InterpretedEvent
    from ai.memory.event_store import EventStore

    with tempfile.TemporaryDirectory() as tmpdir:
        store = EventStore(save_dir=tmpdir)

        # Record events
        events = []
        for i in range(10):
            e = WorldMemoryEvent.create(
                event_type="enemy_killed",
                event_subtype="killed_wolf",
                actor_id="player",
                position_x=float(i * 10),
                position_y=0.0,
                game_time=float(i),
                magnitude=float(i * 10),
                tags=["event:enemy_killed", "species:wolf"],
            )
            events.append(e)
        store.record_batch(events)
        assert store.get_event_count() == 10
        print("  [PASS] Batch recording")

        # Query by type
        results = store.query(event_type="enemy_killed")
        assert len(results) == 10
        print("  [PASS] Query by type")

        # Query with time filter
        results = store.query(since_game_time=5.0)
        assert len(results) == 5
        print("  [PASS] Query with time filter")

        # Count filtered
        count = store.count_filtered(event_type="enemy_killed", since_game_time=7.0)
        assert count == 3
        print("  [PASS] Count filtered")

        # Occurrence counter
        c = store.increment_occurrence("player", "enemy_killed", "killed_wolf")
        assert c == 1
        c = store.increment_occurrence("player", "enemy_killed", "killed_wolf")
        assert c == 2
        c = store.get_occurrence_count("player", "enemy_killed", "killed_wolf")
        assert c == 2
        print("  [PASS] Occurrence counter")

        # Get by IDs
        ids = [events[0].event_id, events[5].event_id]
        results = store.get_by_ids(ids)
        assert len(results) == 2
        print("  [PASS] Get by IDs")

        # Interpretation storage
        interp = InterpretedEvent.create(
            narrative="Wolves declining.",
            category="population_change",
            severity="moderate",
            trigger_event_id=events[0].event_id,
            trigger_count=5,
            game_time=50.0,
            affected_locality_ids=["loc_1_1"],
            affects_tags=["species:wolf"],
            is_ongoing=True,
            expires_at=150.0,
        )
        store.record_interpretation(interp)
        retrieved = store.get_interpretation(interp.interpretation_id)
        assert retrieved is not None
        assert retrieved.narrative == "Wolves declining."
        assert retrieved.is_ongoing
        print("  [PASS] Interpretation storage")

        # Query interpretations
        ongoing = store.get_ongoing_interpretations()
        assert len(ongoing) == 1
        print("  [PASS] Ongoing interpretations query")

        # Expire interpretations
        expired = store.expire_old_interpretations(200.0)
        assert expired == 1
        ongoing = store.get_ongoing_interpretations()
        assert len(ongoing) == 0
        print("  [PASS] Interpretation expiration")

        # Region state persistence
        store.save_region_state("loc_1_1", ["cond1"], ["ev1", "ev2"], "Summary text.", 100.0)
        state = store.load_region_state("loc_1_1")
        assert state is not None
        assert state["summary_text"] == "Summary text."
        assert len(state["active_conditions"]) == 1
        print("  [PASS] Region state persistence")

        # Delete events
        deleted = store.delete_events([events[0].event_id, events[1].event_id])
        assert deleted == 2
        assert store.get_event_count() == 8
        print("  [PASS] Event deletion")

        store.close()


def test_geographic_registry():
    """Test geographic region loading and lookup."""
    from ai.memory.geographic_registry import GeographicRegistry, Region, RegionLevel

    GeographicRegistry.reset()
    geo = GeographicRegistry.get_instance()

    # Load from JSON config
    config_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        "AI-Config.JSON", "geographic-map.json"
    )
    if os.path.exists(config_path):
        geo.load_base_map(config_path)
        assert len(geo.regions) > 0
        print(f"  [PASS] Loaded {len(geo.regions)} regions from JSON")

        # Test position lookup (spawn area should be in Elder's Grove)
        region = geo.get_region_at(-8.0, -8.0)
        assert region is not None
        print(f"  [PASS] Position lookup: ({-8},{-8}) → {region.name}")

        # Test full address
        address = geo.get_full_address(-8.0, -8.0)
        assert "locality" in address
        print(f"  [PASS] Full address: {address}")
    else:
        print(f"  [SKIP] No geographic-map.json found at {config_path}")

    # Test procedural generation
    GeographicRegistry.reset()
    geo2 = GeographicRegistry.get_instance()
    chunk_biomes = {
        (0, 0): "peaceful_forest",
        (1, 0): "peaceful_forest",
        (0, 1): "peaceful_quarry",
        (1, 1): "dangerous_cave",
        (-1, 0): "peaceful_forest",
        (0, -1): "water_lake",
    }
    geo2.generate_from_biomes(chunk_biomes, chunk_size=16)
    assert len(geo2.regions) > 0
    assert geo2.realm is not None
    print(f"  [PASS] Procedural generation: {len(geo2.regions)} regions")

    # Test nearby regions
    nearby = geo2.get_nearby_regions(8.0, 8.0, 50.0, RegionLevel.LOCALITY)
    assert len(nearby) > 0
    print(f"  [PASS] Nearby regions: found {len(nearby)}")

    GeographicRegistry.reset()


def test_tag_relevance():
    """Test tag matching and relevance scoring."""
    from ai.memory.tag_relevance import calculate_relevance, tags_overlap

    # Exact match should score high
    entity_tags = ["job:blacksmith", "domain:smithing", "resource:iron"]
    event_tags = ["event:crafting", "domain:smithing", "resource:iron"]
    score = calculate_relevance(entity_tags, event_tags)
    assert score > 0.5
    print(f"  [PASS] Blacksmith vs crafting/smithing: {score:.2f}")

    # Unrelated tags should score low
    entity_tags = ["job:herbalist", "domain:alchemy", "resource:herbs"]
    event_tags = ["event:combat", "species:wolf", "tier:2"]
    score = calculate_relevance(entity_tags, event_tags)
    assert score < 0.3
    print(f"  [PASS] Herbalist vs combat: {score:.2f}")

    # Empty tags
    assert calculate_relevance([], ["event:combat"]) == 0.0
    print("  [PASS] Empty tags → 0.0")

    # Overlap check
    assert tags_overlap(["a:1", "b:2"], ["b:2", "c:3"])
    assert not tags_overlap(["a:1"], ["b:2"])
    print("  [PASS] Tag overlap checks")


def test_entity_registry():
    """Test entity registration and lookup."""
    from ai.memory.entity_registry import EntityRegistry, WorldEntity, EntityType

    EntityRegistry.reset()
    reg = EntityRegistry.get_instance()

    # Register entities
    npc = WorldEntity(
        entity_id="npc_gareth",
        entity_type=EntityType.NPC,
        name="Gareth the Blacksmith",
        position_x=10.0, position_y=-5.0,
        tags=["job:blacksmith", "domain:smithing", "resource:iron"],
    )
    reg.register(npc)

    player = WorldEntity(
        entity_id="player",
        entity_type=EntityType.PLAYER,
        name="Player",
        position_x=0.0, position_y=0.0,
        tags=["type:player"],
    )
    reg.register(player)

    # Lookup
    assert reg.get("npc_gareth") is not None
    assert reg.get("nonexistent") is None
    print("  [PASS] Entity registration and lookup")

    # Tag search
    smiths = reg.find_by_tag("job:blacksmith")
    assert len(smiths) == 1
    assert smiths[0].name == "Gareth the Blacksmith"
    print("  [PASS] Tag search")

    # Nearby search
    nearby = reg.find_near(5.0, -3.0, 20.0)
    assert len(nearby) == 2  # Both are within 20 tiles
    print("  [PASS] Nearby search")

    # Tag update
    reg.update_entity_tags("npc_gareth", add_tags=["faction:miners_guild"])
    gareth = reg.get("npc_gareth")
    assert "faction:miners_guild" in gareth.tags
    print("  [PASS] Tag update")

    EntityRegistry.reset()


def test_event_recorder():
    """Test event recording pipeline with mock bus events."""
    from ai.memory.event_store import EventStore
    from ai.memory.geographic_registry import GeographicRegistry
    from ai.memory.entity_registry import EntityRegistry
    from ai.memory.event_recorder import EventRecorder, is_prime_trigger

    # Test prime detection
    assert is_prime_trigger(1)  # First occurrence
    assert is_prime_trigger(2)
    assert is_prime_trigger(3)
    assert not is_prime_trigger(4)
    assert is_prime_trigger(5)
    assert is_prime_trigger(7)
    assert not is_prime_trigger(9)
    assert is_prime_trigger(97)
    assert not is_prime_trigger(100)
    print("  [PASS] Prime trigger detection")

    # Test direct recording
    with tempfile.TemporaryDirectory() as tmpdir:
        store = EventStore(save_dir=tmpdir)

        GeographicRegistry.reset()
        EntityRegistry.reset()
        geo = GeographicRegistry.get_instance()
        entity_reg = EntityRegistry.get_instance()

        EventRecorder.reset()
        recorder = EventRecorder.get_instance()
        recorder.event_store = store
        recorder.geo_registry = geo
        recorder.entity_registry = entity_reg
        recorder.session_id = "test"
        recorder._game_time = 50.0

        # Record events directly
        triggered_events = []
        def on_trigger(event):
            triggered_events.append(event)
        recorder.set_interpreter_callback(on_trigger)

        for i in range(10):
            recorder.record_direct(
                event_type="enemy_killed",
                event_subtype="killed_wolf",
                actor_id="player",
                position_x=float(i), position_y=0.0,
                magnitude=10.0,
                tags=["species:wolf"],
            )

        assert recorder.events_recorded == 10
        assert store.get_event_count() == 10
        # Primes in 1-10: 1,2,3,5,7 = 5 triggers
        assert len(triggered_events) == 5
        print(f"  [PASS] Direct recording: {recorder.events_recorded} events, "
              f"{len(triggered_events)} triggers")

        EventRecorder.reset()
        GeographicRegistry.reset()
        EntityRegistry.reset()
        store.close()


def test_interpreter():
    """Test the interpreter with pattern evaluators."""
    from ai.memory.event_store import EventStore
    from ai.memory.geographic_registry import GeographicRegistry, Region, RegionLevel
    from ai.memory.entity_registry import EntityRegistry
    from ai.memory.interpreter import WorldInterpreter
    from ai.memory.event_schema import WorldMemoryEvent

    with tempfile.TemporaryDirectory() as tmpdir:
        store = EventStore(save_dir=tmpdir)

        GeographicRegistry.reset()
        geo = GeographicRegistry.get_instance()
        # Create a test region
        loc = Region(
            region_id="test_forest",
            name="Test Forest",
            level=RegionLevel.LOCALITY,
            bounds_x1=0, bounds_y1=0, bounds_x2=15, bounds_y2=15,
            biome_primary="forest",
            tags=["biome:forest"],
        )
        geo.regions["test_forest"] = loc

        EntityRegistry.reset()
        entity_reg = EntityRegistry.get_instance()

        WorldInterpreter.reset()
        interp = WorldInterpreter.get_instance()
        interp.initialize(store, geo, entity_reg)

        # Record enough wolf kills to trigger population evaluator
        for i in range(15):
            event = WorldMemoryEvent.create(
                event_type="enemy_killed",
                event_subtype="killed_wolf",
                actor_id="player",
                position_x=5.0, position_y=5.0,
                game_time=float(i),
                magnitude=10.0,
                tags=["species:wolf"],
            )
            event.locality_id = "test_forest"
            event.biome = "forest"
            event.interpretation_count = i + 1
            event.triggered_interpretation = True
            store.record(event)

        # Trigger interpretation
        trigger = WorldMemoryEvent.create(
            event_type="enemy_killed",
            event_subtype="killed_wolf",
            actor_id="player",
            position_x=5.0, position_y=5.0,
            game_time=15.0,
        )
        trigger.locality_id = "test_forest"
        trigger.biome = "forest"
        trigger.interpretation_count = 15

        interp.on_trigger(trigger)

        # Check interpretations were created
        interps = store.query_interpretations(category="population_change")
        assert len(interps) > 0
        print(f"  [PASS] Population interpretation: \"{interps[0].narrative[:60]}...\"")
        print(f"         Severity: {interps[0].severity}")

        # Check region state was updated
        assert len(loc.state.recent_events) > 0
        print(f"  [PASS] Region state updated: {len(loc.state.recent_events)} events")

        WorldInterpreter.reset()
        GeographicRegistry.reset()
        EntityRegistry.reset()
        store.close()


def test_query_interface():
    """Test the WorldQuery entity-first query interface."""
    from ai.memory.event_store import EventStore
    from ai.memory.geographic_registry import GeographicRegistry, Region, RegionLevel
    from ai.memory.entity_registry import EntityRegistry, WorldEntity, EntityType
    from ai.memory.query import WorldQuery, EventWindow
    from ai.memory.event_schema import WorldMemoryEvent

    with tempfile.TemporaryDirectory() as tmpdir:
        store = EventStore(save_dir=tmpdir)

        GeographicRegistry.reset()
        geo = GeographicRegistry.get_instance()
        loc = Region(
            region_id="test_loc", name="Test Area",
            level=RegionLevel.LOCALITY,
            bounds_x1=0, bounds_y1=0, bounds_x2=15, bounds_y2=15,
        )
        geo.regions["test_loc"] = loc

        EntityRegistry.reset()
        entity_reg = EntityRegistry.get_instance()
        npc = WorldEntity(
            entity_id="npc_test",
            entity_type=EntityType.NPC,
            name="Test NPC",
            position_x=5.0, position_y=5.0,
            home_region_id="test_loc",
            tags=["job:blacksmith", "resource:iron"],
        )
        entity_reg.register(npc)

        # Record some events
        for i in range(5):
            event = WorldMemoryEvent.create(
                event_type="resource_gathered",
                event_subtype="gathered_iron",
                actor_id="player",
                position_x=5.0, position_y=5.0,
                game_time=float(i),
                tags=["resource:iron", "event:resource_gathered"],
            )
            event.locality_id = "test_loc"
            store.record(event)
            # Add to NPC activity log
            npc.add_activity(event.event_id)

        WorldQuery.reset()
        query = WorldQuery.get_instance()
        query.initialize(entity_reg, geo, store)

        # Query NPC
        result = query.query_entity("npc_test", current_game_time=10.0)
        assert result.entity_id == "npc_test"
        assert result.metadata["name"] == "Test NPC"
        assert len(result.direct_events) > 0
        print(f"  [PASS] Entity query: {len(result.direct_events)} direct events")

        # Query location
        result = query.query_location("test_loc", current_game_time=10.0)
        assert result.entity_id == "region_test_loc"
        print(f"  [PASS] Location query")

        # World summary
        summary = query.get_world_summary(10.0)
        assert summary["total_events_recorded"] == 5
        print(f"  [PASS] World summary: {summary['total_events_recorded']} events")

        WorldQuery.reset()
        GeographicRegistry.reset()
        EntityRegistry.reset()
        store.close()


def test_retention():
    """Test event retention and pruning."""
    from ai.memory.event_store import EventStore
    from ai.memory.event_schema import WorldMemoryEvent
    from ai.memory.retention import EventRetentionManager

    with tempfile.TemporaryDirectory() as tmpdir:
        store = EventStore(save_dir=tmpdir)

        # Record 200 events with various occurrence counts
        for i in range(200):
            event = WorldMemoryEvent.create(
                event_type="resource_gathered",
                event_subtype="gathered_iron",
                actor_id="player",
                game_time=float(i * 0.5),  # Spread over 100 game-time units
            )
            event.interpretation_count = i + 1
            event.triggered_interpretation = (i + 1) in {1, 2, 3, 5, 7}
            store.record(event)

        assert store.get_event_count() == 200

        retention = EventRetentionManager()
        retention.PRUNE_AGE_THRESHOLD = 50.0
        deleted = retention.prune(store, current_game_time=200.0)

        remaining = store.get_event_count()
        print(f"  [PASS] Retention: {200} → {remaining} events ({deleted} pruned)")
        assert remaining < 200  # Some should be pruned
        assert remaining > 10   # But not all — milestones preserved

        store.close()


def test_full_pipeline():
    """End-to-end test: events flow through the entire pipeline."""
    from ai.memory.world_memory_system import WorldMemorySystem

    with tempfile.TemporaryDirectory() as tmpdir:
        WorldMemorySystem.reset()
        memory = WorldMemorySystem.get_instance()
        memory.initialize(save_dir=tmpdir)

        # Simulate game events via direct recording
        recorder = memory.event_recorder

        # Player kills wolves
        for i in range(20):
            recorder.record_direct(
                event_type="enemy_killed",
                event_subtype="killed_wolf",
                actor_id="player",
                position_x=5.0, position_y=5.0,
                magnitude=10.0 + i,
                tags=["species:wolf", "event:enemy_killed", "biome:forest"],
            )
            recorder._game_time = float(i)

        # Player gathers resources
        for i in range(15):
            recorder.record_direct(
                event_type="resource_gathered",
                event_subtype="gathered_iron",
                actor_id="player",
                position_x=20.0, position_y=20.0,
                magnitude=float(i + 1),
                tags=["resource:iron", "event:resource_gathered"],
            )
            recorder._game_time = 20.0 + i

        print(f"  Events recorded: {recorder.events_recorded}")
        print(f"  Events in store: {memory.event_store.get_event_count()}")

        # Check interpretations
        interps = memory.event_store.query_interpretations()
        print(f"  Interpretations created: {len(interps)}")
        for interp in interps:
            print(f"    [{interp.severity}] {interp.category}: {interp.narrative[:80]}")

        # Query the system
        query = memory.world_query
        summary = query.get_world_summary(35.0)
        print(f"  World summary: {summary}")

        # Save and verify
        save_data = memory.save()
        assert "memory_db_path" in save_data
        print(f"  [PASS] Save data: {save_data}")

        # Stats
        stats = memory.stats
        print(f"  System stats: {stats}")
        assert stats["initialized"]
        assert stats["recorder"]["events_recorded"] == 35

        print("  [PASS] Full pipeline test complete")

        WorldMemorySystem.reset()


def run_all_tests():
    """Run all tests and report results."""
    tests = [
        ("Event Schema", test_event_schema),
        ("Event Store (SQLite)", test_event_store),
        ("Geographic Registry", test_geographic_registry),
        ("Tag Relevance", test_tag_relevance),
        ("Entity Registry", test_entity_registry),
        ("Event Recorder", test_event_recorder),
        ("Interpreter", test_interpreter),
        ("Query Interface", test_query_interface),
        ("Retention", test_retention),
        ("Full Pipeline (E2E)", test_full_pipeline),
    ]

    passed = 0
    failed = 0
    print("\n" + "=" * 60)
    print("World Memory System — Test Suite")
    print("=" * 60)

    for name, test_fn in tests:
        print(f"\n--- {name} ---")
        try:
            test_fn()
            passed += 1
        except Exception as e:
            failed += 1
            import traceback
            print(f"  [FAIL] {e}")
            traceback.print_exc()

    print("\n" + "=" * 60)
    print(f"Results: {passed} passed, {failed} failed, {passed + failed} total")
    print("=" * 60)

    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)

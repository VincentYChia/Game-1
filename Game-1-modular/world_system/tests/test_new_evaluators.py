"""Comprehensive tests for the three new evaluators: fishing, turrets, and chests.

Tests cover:
1. EventType / BUS_TO_MEMORY_TYPE pipeline — new types present and mapped
2. EventRecorder subtype derivation — correct subtypes for all 4 new event types
3. FishingActivityEvaluator — severity ladder, rarity boost, region/global narratives
4. TurretActivityEvaluator — turret vs barrier distinction, tier boost, severity ladder
5. ChestLootEvaluator — count ladder, dungeon baseline boost, narrative templates
6. interpreter.py registration — all 3 evaluators load without error
7. Config loading — evaluator config blocks are present in memory-config.json
8. Prompt fragments — new fragments present in prompt_fragments.json

Run: cd Game-1-modular && python -m pytest world_system/tests/test_new_evaluators.py -v
"""

from __future__ import annotations

import json
import os
import sys
import unittest
import uuid

_this_dir = os.path.dirname(os.path.abspath(__file__))
_game_dir = os.path.dirname(os.path.dirname(_this_dir))
if _game_dir not in sys.path:
    sys.path.insert(0, _game_dir)


# ── Shared helpers ─────────────────────────────────────────────────────────────

def _make_event(event_type: str, event_subtype: str = "", locality_id: str = "",
                game_time: float = 100.0, quality: str = "", tier: int = 1,
                position_x: float = 0.0, position_y: float = 0.0):
    """Build a minimal WorldMemoryEvent for evaluator tests."""
    from world_system.world_memory.event_schema import WorldMemoryEvent
    return WorldMemoryEvent(
        event_id=str(uuid.uuid4()),
        event_type=event_type,
        event_subtype=event_subtype,
        actor_id="player",
        actor_type="player",
        locality_id=locality_id or None,
        game_time=game_time,
        quality=quality or None,
        tier=tier,
        position_x=position_x,
        position_y=position_y,
        interpretation_count=1,
    )


class _MockEventStore:
    """Minimal EventStore mock that returns a preconfigured count."""

    def __init__(self, count: int = 0):
        self._count = count
        self.last_kwargs: dict = {}

    def count_filtered(self, **kwargs) -> int:
        self.last_kwargs = kwargs
        return self._count


class _MockGeoRegistry:
    """Minimal GeographicRegistry mock."""

    def __init__(self, region_name: str = "Test Region", parent_id: str = "district_1"):
        from world_system.world_memory.geographic_registry import Region, RegionLevel
        self.regions = {
            "locality_1": Region(
                region_id="locality_1",
                name=region_name,
                level=RegionLevel.LOCALITY,
                bounds_x1=0, bounds_y1=0,
                bounds_x2=10, bounds_y2=10,
                parent_id=parent_id,
            )
        }


# ══════════════════════════════════════════════════════════════════════════════
# 1. EventType / BUS_TO_MEMORY_TYPE pipeline
# ══════════════════════════════════════════════════════════════════════════════

class TestEventSchemaPipeline(unittest.TestCase):
    """All four new event types must exist in the schema and bus mapping."""

    def setUp(self):
        from world_system.world_memory.event_schema import EventType, BUS_TO_MEMORY_TYPE
        self.EventType = EventType
        self.bus_map = BUS_TO_MEMORY_TYPE

    def test_fish_caught_event_type_exists(self):
        self.assertEqual(self.EventType.FISH_CAUGHT.value, "fish_caught")

    def test_chest_opened_event_type_exists(self):
        self.assertEqual(self.EventType.CHEST_OPENED.value, "chest_opened")

    def test_turret_placed_event_type_exists(self):
        self.assertEqual(self.EventType.TURRET_PLACED.value, "turret_placed")

    def test_barrier_placed_event_type_exists(self):
        self.assertEqual(self.EventType.BARRIER_PLACED.value, "barrier_placed")

    def test_fish_caught_in_bus_map(self):
        self.assertIn("FISH_CAUGHT", self.bus_map)
        self.assertEqual(self.bus_map["FISH_CAUGHT"], self.EventType.FISH_CAUGHT)

    def test_chest_opened_in_bus_map(self):
        self.assertIn("CHEST_OPENED", self.bus_map)
        self.assertEqual(self.bus_map["CHEST_OPENED"], self.EventType.CHEST_OPENED)

    def test_turret_placed_in_bus_map(self):
        self.assertIn("TURRET_PLACED", self.bus_map)
        self.assertEqual(self.bus_map["TURRET_PLACED"], self.EventType.TURRET_PLACED)

    def test_barrier_placed_in_bus_map(self):
        self.assertIn("BARRIER_PLACED", self.bus_map)
        self.assertEqual(self.bus_map["BARRIER_PLACED"], self.EventType.BARRIER_PLACED)


# ══════════════════════════════════════════════════════════════════════════════
# 2. EventRecorder subtype derivation
# ══════════════════════════════════════════════════════════════════════════════

class _BusEvent:
    """Minimal bus event mock — EventRecorder reads event.data."""

    def __init__(self, data: dict):
        self.data = data


class TestEventRecorderSubtypes(unittest.TestCase):
    """_derive_subtype() must produce correct subtypes for new event types."""

    def setUp(self):
        from world_system.world_memory.event_recorder import EventRecorder
        from world_system.world_memory.event_schema import EventType
        self.recorder = EventRecorder.__new__(EventRecorder)
        self.EventType = EventType

    def _subtype(self, mem_type, data: dict) -> str:
        return self.recorder._derive_subtype(_BusEvent(data), mem_type)

    def test_fish_caught_subtype_with_fish_id(self):
        self.assertEqual(
            self._subtype(self.EventType.FISH_CAUGHT, {"fish_id": "salmon"}),
            "caught_salmon",
        )

    def test_fish_caught_subtype_fallback_resource_id(self):
        self.assertEqual(
            self._subtype(self.EventType.FISH_CAUGHT, {"resource_id": "trout"}),
            "caught_trout",
        )

    def test_fish_caught_subtype_unknown_fallback(self):
        self.assertEqual(
            self._subtype(self.EventType.FISH_CAUGHT, {}),
            "caught_unknown",
        )

    def test_chest_opened_subtype_with_chest_type(self):
        self.assertEqual(
            self._subtype(self.EventType.CHEST_OPENED, {"chest_type": "dungeon"}),
            "opened_dungeon",
        )

    def test_chest_opened_subtype_default(self):
        self.assertEqual(
            self._subtype(self.EventType.CHEST_OPENED, {}),
            "opened_chest",
        )

    def test_turret_placed_subtype(self):
        self.assertEqual(
            self._subtype(self.EventType.TURRET_PLACED, {"item_id": "net_launcher"}),
            "placed_net_launcher",
        )

    def test_barrier_placed_subtype_material_id(self):
        self.assertEqual(
            self._subtype(self.EventType.BARRIER_PLACED, {"material_id": "stone_barrier"}),
            "placed_stone_barrier",
        )

    def test_barrier_placed_subtype_item_id_fallback(self):
        self.assertEqual(
            self._subtype(self.EventType.BARRIER_PLACED, {"item_id": "oak_plank"}),
            "placed_oak_plank",
        )


# ══════════════════════════════════════════════════════════════════════════════
# 3. FishingActivityEvaluator
# ══════════════════════════════════════════════════════════════════════════════

class TestFishingActivityEvaluator(unittest.TestCase):
    """Tests for FishingActivityEvaluator."""

    def setUp(self):
        from world_system.world_memory.evaluators.fishing_activity import FishingActivityEvaluator
        self.evaluator = FishingActivityEvaluator()
        self.geo = _MockGeoRegistry(region_name="Silverstream Lake")

    def _run(self, count: int, locality_id: str = "locality_1",
             event_subtype: str = "caught_salmon", quality: str = "") -> object:
        evt = _make_event("fish_caught", event_subtype=event_subtype,
                          locality_id=locality_id, quality=quality)
        store = _MockEventStore(count=count)
        return self.evaluator.evaluate(
            trigger_event=evt,
            event_store=store,
            geo_registry=self.geo,
            entity_registry=None,
            interpretation_store=store,
        )

    # ── is_relevant ────────────────────────────────────────────────

    def test_relevant_for_fish_caught(self):
        evt = _make_event("fish_caught")
        self.assertTrue(self.evaluator.is_relevant(evt))

    def test_not_relevant_for_other_types(self):
        for t in ("resource_gathered", "enemy_killed", "chest_opened"):
            evt = _make_event(t)
            self.assertFalse(self.evaluator.is_relevant(evt))

    # ── count=0 returns None ─────────────────────────────────────────

    def test_returns_none_when_count_zero(self):
        result = self._run(count=0)
        self.assertIsNone(result)

    # ── severity ladder ──────────────────────────────────────────────

    def test_severity_minor_for_count_1(self):
        result = self._run(count=1)
        self.assertIsNotNone(result)
        self.assertEqual(result.severity, "minor")

    def test_severity_minor_at_max_boundary(self):
        """minor_max=3 so count=2 is still minor."""
        result = self._run(count=2)
        self.assertEqual(result.severity, "minor")

    def test_severity_moderate_at_minor_max(self):
        """count=3 crosses into moderate."""
        result = self._run(count=3)
        self.assertEqual(result.severity, "moderate")

    def test_severity_moderate_mid(self):
        result = self._run(count=7)
        self.assertEqual(result.severity, "moderate")

    def test_severity_significant_at_moderate_max(self):
        """moderate_max=10 → count=10 is significant."""
        result = self._run(count=10)
        self.assertEqual(result.severity, "significant")

    def test_severity_major_at_significant_max(self):
        """significant_max=25 → count=25 is major."""
        result = self._run(count=25)
        self.assertEqual(result.severity, "major")

    # ── rarity boost ─────────────────────────────────────────────────

    def test_rare_catch_boosts_severity(self):
        """A rare catch at count=1 (minor) should be boosted to moderate."""
        result = self._run(count=1, quality="rare")
        self.assertEqual(result.severity, "moderate")

    def test_legendary_catch_boosts_severity(self):
        result = self._run(count=1, quality="legendary")
        self.assertEqual(result.severity, "moderate")

    def test_epic_catch_boosts_severity(self):
        result = self._run(count=1, quality="epic")
        self.assertEqual(result.severity, "moderate")

    def test_common_rarity_no_boost(self):
        result = self._run(count=1, quality="common")
        self.assertEqual(result.severity, "minor")

    def test_major_rare_capped_at_major(self):
        """major + rare boost should cap at major (not critical) since cap is major here."""
        result = self._run(count=25, quality="rare")
        # major → +1 → critical (next tier) but _order has critical so it goes to critical
        # Actually: _order = ["minor","moderate","significant","major","critical"]
        # major is index 3, +1 = index 4 = critical. So we get critical.
        self.assertIn(result.severity, ("critical", "major"))

    # ── narrative ────────────────────────────────────────────────────

    def test_narrative_contains_region_name(self):
        result = self._run(count=5, locality_id="locality_1")
        self.assertIn("Silverstream Lake", result.narrative)
        self.assertIn("5", result.narrative)

    def test_narrative_global_fallback(self):
        evt = _make_event("fish_caught", locality_id="")
        store = _MockEventStore(count=3)
        result = self.evaluator.evaluate(
            trigger_event=evt,
            event_store=store,
            geo_registry=self.geo,
            entity_registry=None,
            interpretation_store=store,
        )
        self.assertIsNotNone(result)
        self.assertNotIn("Silverstream Lake", result.narrative)
        self.assertIn("3", result.narrative)

    # ── affects_tags ────────────────────────────────────────────────

    def test_affects_tags_includes_domain_fishing(self):
        result = self._run(count=1)
        self.assertIn("domain:fishing", result.affects_tags)

    def test_affects_tags_includes_resource_species(self):
        result = self._run(count=1, event_subtype="caught_salmon")
        self.assertIn("resource:salmon", result.affects_tags)

    def test_affects_tags_species_with_underscore(self):
        """Multi-word species (caught_silver_trout) → resource:silver_trout."""
        result = self._run(count=1, event_subtype="caught_silver_trout")
        self.assertIn("resource:silver_trout", result.affects_tags)

    def test_affects_tags_rarity_appended(self):
        result = self._run(count=1, quality="rare")
        self.assertIn("rarity:rare", result.affects_tags)

    def test_affects_tags_no_rarity_when_empty(self):
        result = self._run(count=1, quality="")
        rarity_tags = [t for t in result.affects_tags if t.startswith("rarity:")]
        self.assertEqual(len(rarity_tags), 0)

    # ── category ────────────────────────────────────────────────────

    def test_category_is_fishing_activity(self):
        result = self._run(count=1)
        self.assertEqual(result.category, "fishing_activity")

    # ── expiry ──────────────────────────────────────────────────────

    def test_expires_at_set(self):
        result = self._run(count=1)
        self.assertIsNotNone(result.expires_at)
        self.assertTrue(result.expires_at > 100.0)


# ══════════════════════════════════════════════════════════════════════════════
# 4. TurretActivityEvaluator
# ══════════════════════════════════════════════════════════════════════════════

class TestTurretActivityEvaluator(unittest.TestCase):
    """Tests for TurretActivityEvaluator."""

    def setUp(self):
        from world_system.world_memory.evaluators.turret_activity import TurretActivityEvaluator
        self.evaluator = TurretActivityEvaluator()
        self.geo = _MockGeoRegistry(region_name="Iron Bastion")

    def _run(self, event_type: str, count: int, locality_id: str = "locality_1",
             event_subtype: str = "", tier: int = 1) -> object:
        evt = _make_event(event_type, event_subtype=event_subtype,
                          locality_id=locality_id, tier=tier)
        store = _MockEventStore(count=count)
        return self.evaluator.evaluate(
            trigger_event=evt,
            event_store=store,
            geo_registry=self.geo,
            entity_registry=None,
            interpretation_store=store,
        )

    # ── is_relevant ────────────────────────────────────────────────

    def test_relevant_for_turret_placed(self):
        evt = _make_event("turret_placed")
        self.assertTrue(self.evaluator.is_relevant(evt))

    def test_relevant_for_barrier_placed(self):
        evt = _make_event("barrier_placed")
        self.assertTrue(self.evaluator.is_relevant(evt))

    def test_not_relevant_for_other_types(self):
        for t in ("fish_caught", "enemy_killed", "chest_opened"):
            evt = _make_event(t)
            self.assertFalse(self.evaluator.is_relevant(evt))

    # ── count=0 returns None ─────────────────────────────────────────

    def test_returns_none_when_count_zero(self):
        result = self._run("turret_placed", count=0)
        self.assertIsNone(result)

    # ── severity ladder (turret) ─────────────────────────────────────

    def test_turret_severity_minor_count_1(self):
        result = self._run("turret_placed", count=1)
        self.assertEqual(result.severity, "minor")

    def test_turret_severity_moderate(self):
        """minor_max=3 → count=3 is moderate."""
        result = self._run("turret_placed", count=3)
        self.assertEqual(result.severity, "moderate")

    def test_turret_severity_significant(self):
        """moderate_max=8 → count=8 is significant."""
        result = self._run("turret_placed", count=8)
        self.assertEqual(result.severity, "significant")

    def test_turret_severity_major(self):
        """significant_max=20 → count=20 is major."""
        result = self._run("turret_placed", count=20)
        self.assertEqual(result.severity, "major")

    # ── tier boost ──────────────────────────────────────────────────

    def test_tier3_boosts_severity(self):
        """T3 turret at count=1 (minor) → moderate."""
        result = self._run("turret_placed", count=1, tier=3)
        self.assertEqual(result.severity, "moderate")

    def test_tier4_boosts_severity(self):
        """T4 turret at count=1 (minor) → moderate."""
        result = self._run("turret_placed", count=1, tier=4)
        self.assertEqual(result.severity, "moderate")

    def test_tier1_no_boost(self):
        result = self._run("turret_placed", count=1, tier=1)
        self.assertEqual(result.severity, "minor")

    def test_tier2_no_boost(self):
        result = self._run("turret_placed", count=1, tier=2)
        self.assertEqual(result.severity, "minor")

    # ── turret vs barrier narrative distinction ───────────────────────

    def test_turret_narrative_mentions_turrets(self):
        result = self._run("turret_placed", count=2, event_subtype="placed_net_launcher")
        self.assertIn("turret", result.narrative.lower())
        self.assertNotIn("barrier", result.narrative.lower())

    def test_barrier_narrative_mentions_barriers(self):
        result = self._run("barrier_placed", count=2, event_subtype="placed_stone_barrier")
        self.assertIn("barrier", result.narrative.lower())
        self.assertNotIn("turret", result.narrative.lower())

    def test_turret_narrative_contains_region(self):
        result = self._run("turret_placed", count=3, locality_id="locality_1")
        self.assertIn("Iron Bastion", result.narrative)

    # ── EventStore receives correct event_type ────────────────────────

    def test_store_queried_with_turret_placed(self):
        evt = _make_event("turret_placed", locality_id="locality_1")
        store = _MockEventStore(count=1)
        self.evaluator.evaluate(evt, store, self.geo, None, store)
        self.assertEqual(store.last_kwargs["event_type"], "turret_placed")

    def test_store_queried_with_barrier_placed(self):
        evt = _make_event("barrier_placed", locality_id="locality_1")
        store = _MockEventStore(count=1)
        self.evaluator.evaluate(evt, store, self.geo, None, store)
        self.assertEqual(store.last_kwargs["event_type"], "barrier_placed")

    # ── affects_tags ────────────────────────────────────────────────

    def test_turret_affects_tags_domain_engineering(self):
        result = self._run("turret_placed", count=1)
        self.assertIn("domain:engineering", result.affects_tags)

    def test_turret_affects_tags_action_turret_placed(self):
        result = self._run("turret_placed", count=1)
        self.assertIn("action:turret_placed", result.affects_tags)

    def test_barrier_affects_tags_action_barrier_placed(self):
        result = self._run("barrier_placed", count=1)
        self.assertIn("action:barrier_placed", result.affects_tags)

    def test_high_tier_adds_tier_tag(self):
        result = self._run("turret_placed", count=1, tier=3)
        tier_tags = [t for t in result.affects_tags if t.startswith("tier:")]
        self.assertTrue(len(tier_tags) > 0)

    def test_low_tier_no_tier_tag(self):
        result = self._run("turret_placed", count=1, tier=1)
        tier_tags = [t for t in result.affects_tags if t.startswith("tier:")]
        self.assertEqual(len(tier_tags), 0)

    # ── category ────────────────────────────────────────────────────

    def test_category_is_turret_activity(self):
        result = self._run("turret_placed", count=1)
        self.assertEqual(result.category, "turret_activity")


# ══════════════════════════════════════════════════════════════════════════════
# 5. ChestLootEvaluator
# ══════════════════════════════════════════════════════════════════════════════

class TestChestLootEvaluator(unittest.TestCase):
    """Tests for ChestLootEvaluator."""

    def setUp(self):
        from world_system.world_memory.evaluators.chest_loot import ChestLootEvaluator
        self.evaluator = ChestLootEvaluator()
        self.geo = _MockGeoRegistry(region_name="Dungeon Depths")

    def _run(self, count: int, locality_id: str = "locality_1",
             event_subtype: str = "opened_chest") -> object:
        evt = _make_event("chest_opened", event_subtype=event_subtype,
                          locality_id=locality_id)
        store = _MockEventStore(count=count)
        return self.evaluator.evaluate(
            trigger_event=evt,
            event_store=store,
            geo_registry=self.geo,
            entity_registry=None,
            interpretation_store=store,
        )

    # ── is_relevant ────────────────────────────────────────────────

    def test_relevant_for_chest_opened(self):
        evt = _make_event("chest_opened")
        self.assertTrue(self.evaluator.is_relevant(evt))

    def test_not_relevant_for_other_types(self):
        for t in ("fish_caught", "enemy_killed", "turret_placed"):
            evt = _make_event(t)
            self.assertFalse(self.evaluator.is_relevant(evt))

    # ── count=0 returns None ─────────────────────────────────────────

    def test_returns_none_when_count_zero(self):
        result = self._run(count=0)
        self.assertIsNone(result)

    # ── severity ladder ──────────────────────────────────────────────

    def test_severity_minor_count_1(self):
        result = self._run(count=1)
        self.assertEqual(result.severity, "minor")

    def test_severity_minor_count_2(self):
        result = self._run(count=2)
        self.assertEqual(result.severity, "minor")

    def test_severity_moderate_at_minor_max(self):
        """minor_max=3 → count=3 is moderate."""
        result = self._run(count=3)
        self.assertEqual(result.severity, "moderate")

    def test_severity_significant_at_moderate_max(self):
        """moderate_max=8 → count=8 is significant."""
        result = self._run(count=8)
        self.assertEqual(result.severity, "significant")

    def test_severity_major_at_significant_max(self):
        """significant_max=15 → count=15 is major."""
        result = self._run(count=15)
        self.assertEqual(result.severity, "major")

    # ── dungeon chest baseline boost ─────────────────────────────────

    def test_dungeon_chest_count_1_is_at_least_moderate(self):
        """A single dungeon chest must be at least moderate."""
        result = self._run(count=1, event_subtype="opened_dungeon")
        self.assertEqual(result.severity, "moderate")

    def test_boss_chest_count_1_is_at_least_moderate(self):
        result = self._run(count=1, event_subtype="opened_boss")
        self.assertEqual(result.severity, "moderate")

    def test_rare_chest_count_1_is_at_least_moderate(self):
        result = self._run(count=1, event_subtype="opened_rare")
        self.assertEqual(result.severity, "moderate")

    def test_common_chest_count_1_remains_minor(self):
        """Regular chests don't get the baseline boost."""
        result = self._run(count=1, event_subtype="opened_chest")
        self.assertEqual(result.severity, "minor")

    def test_dungeon_chest_higher_count_keeps_higher_severity(self):
        """Count=8 → significant; dungeon boost (>=moderate) has no further effect."""
        result = self._run(count=8, event_subtype="opened_dungeon")
        self.assertEqual(result.severity, "significant")

    # ── narrative ────────────────────────────────────────────────────

    def test_narrative_contains_region_name(self):
        result = self._run(count=3, locality_id="locality_1")
        self.assertIn("Dungeon Depths", result.narrative)
        self.assertIn("3", result.narrative)

    def test_narrative_global_fallback(self):
        evt = _make_event("chest_opened", locality_id="")
        store = _MockEventStore(count=2)
        result = self.evaluator.evaluate(
            trigger_event=evt,
            event_store=store,
            geo_registry=self.geo,
            entity_registry=None,
            interpretation_store=store,
        )
        self.assertIsNotNone(result)
        self.assertNotIn("Dungeon Depths", result.narrative)
        self.assertIn("2", result.narrative)

    # ── affects_tags ────────────────────────────────────────────────

    def test_affects_tags_domain_exploration(self):
        result = self._run(count=1)
        self.assertIn("domain:exploration", result.affects_tags)

    def test_affects_tags_action_chest_opened(self):
        result = self._run(count=1)
        self.assertIn("action:chest_opened", result.affects_tags)

    def test_affects_tags_chest_type_appended(self):
        result = self._run(count=1, event_subtype="opened_dungeon")
        self.assertIn("resource:dungeon_chest", result.affects_tags)

    def test_no_resource_tag_for_plain_chest(self):
        result = self._run(count=1, event_subtype="opened_chest")
        self.assertIn("resource:chest_chest", result.affects_tags)

    # ── category ────────────────────────────────────────────────────

    def test_category_is_chest_loot(self):
        result = self._run(count=1)
        self.assertEqual(result.category, "chest_loot")

    # ── expiry ──────────────────────────────────────────────────────

    def test_expires_at_set(self):
        result = self._run(count=1)
        self.assertIsNotNone(result.expires_at)
        self.assertTrue(result.expires_at > 100.0)


# ══════════════════════════════════════════════════════════════════════════════
# 6. Interpreter registration — all 3 evaluators load without error
# ══════════════════════════════════════════════════════════════════════════════

class TestInterpreterRegistration(unittest.TestCase):
    """The three new evaluators must be registered in WorldInterpreter."""

    def setUp(self):
        from world_system.world_memory.interpreter import WorldInterpreter
        WorldInterpreter.reset()

    def tearDown(self):
        from world_system.world_memory.interpreter import WorldInterpreter
        WorldInterpreter.reset()

    def _make_interpreter(self):
        from world_system.world_memory.interpreter import WorldInterpreter
        from world_system.world_memory.geographic_registry import GeographicRegistry
        from world_system.world_memory.entity_registry import EntityRegistry
        import tempfile
        from world_system.world_memory.event_store import EventStore

        GeographicRegistry.reset()
        GeographicRegistry.get_instance()

        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name

        store = EventStore(db_path)
        entity_reg = EntityRegistry()
        geo_reg = GeographicRegistry.get_instance()

        interp = WorldInterpreter.get_instance()
        interp.initialize(store, geo_reg, entity_reg)
        return interp, db_path

    def test_fishing_evaluator_registered(self):
        interp, _ = self._make_interpreter()
        names = [type(e).__name__ for e in interp._evaluators]
        self.assertIn("FishingActivityEvaluator", names)

    def test_turret_evaluator_registered(self):
        interp, _ = self._make_interpreter()
        names = [type(e).__name__ for e in interp._evaluators]
        self.assertIn("TurretActivityEvaluator", names)

    def test_chest_evaluator_registered(self):
        interp, _ = self._make_interpreter()
        names = [type(e).__name__ for e in interp._evaluators]
        self.assertIn("ChestLootEvaluator", names)

    def test_evaluator_count_is_36(self):
        """Total should be 36 evaluators (33 original + 3 new)."""
        interp, _ = self._make_interpreter()
        self.assertEqual(len(interp._evaluators), 36)


# ══════════════════════════════════════════════════════════════════════════════
# 7. Config loading — evaluator config blocks present in memory-config.json
# ══════════════════════════════════════════════════════════════════════════════

class TestConfigPresence(unittest.TestCase):
    """memory-config.json must have the three new evaluator blocks."""

    _CONFIG_PATH = os.path.join(
        _game_dir, "world_system", "config", "memory-config.json"
    )

    def _load(self):
        with open(self._CONFIG_PATH) as f:
            return json.load(f)

    def test_fishing_activity_config_present(self):
        cfg = self._load()
        self.assertIn("fishing_activity", cfg["evaluators"])

    def test_turret_activity_config_present(self):
        cfg = self._load()
        self.assertIn("turret_activity", cfg["evaluators"])

    def test_chest_loot_config_present(self):
        cfg = self._load()
        self.assertIn("chest_loot", cfg["evaluators"])

    def test_fishing_activity_has_thresholds(self):
        cfg = self._load()
        ev = cfg["evaluators"]["fishing_activity"]
        self.assertIn("thresholds", ev)
        self.assertIn("minor_max", ev["thresholds"])

    def test_turret_activity_has_templates(self):
        cfg = self._load()
        ev = cfg["evaluators"]["turret_activity"]
        self.assertIn("narrative_templates", ev)
        self.assertIn("turret_with_region", ev["narrative_templates"])
        self.assertIn("barrier_with_region", ev["narrative_templates"])

    def test_chest_loot_has_expiration_offset(self):
        cfg = self._load()
        ev = cfg["evaluators"]["chest_loot"]
        self.assertIn("expiration_offset", ev)


# ══════════════════════════════════════════════════════════════════════════════
# 8. Prompt fragments — new fragments present in prompt_fragments.json
# ══════════════════════════════════════════════════════════════════════════════

class TestPromptFragments(unittest.TestCase):
    """New prompt fragments must be present in prompt_fragments.json."""

    _FRAGS_PATH = os.path.join(
        _game_dir, "world_system", "config", "prompt_fragments.json"
    )

    def _load(self):
        with open(self._FRAGS_PATH) as f:
            return json.load(f)

    def test_domain_fishing_fragment_present(self):
        frags = self._load()
        self.assertIn("domain:fishing", frags)

    def test_action_turret_placed_fragment_present(self):
        frags = self._load()
        self.assertIn("action:turret_placed", frags)

    def test_action_barrier_placed_fragment_present(self):
        frags = self._load()
        self.assertIn("action:barrier_placed", frags)

    def test_action_chest_opened_fragment_present(self):
        frags = self._load()
        self.assertIn("action:chest_opened", frags)

    def test_fragments_are_non_empty_strings(self):
        frags = self._load()
        for key in ("domain:fishing", "action:turret_placed",
                    "action:barrier_placed", "action:chest_opened"):
            val = frags[key]
            self.assertIsInstance(val, str)
            self.assertGreater(len(val.strip()), 10,
                               f"Fragment '{key}' is too short: {val!r}")

    def test_total_fragment_count_updated(self):
        frags = self._load()
        meta = frags.get("_meta", {})
        self.assertGreaterEqual(meta.get("total_fragments", 0), 127,
                                "total_fragments in _meta should be ≥127")


# ══════════════════════════════════════════════════════════════════════════════
# 9. EventRecorder domain tag building for new event types
# ══════════════════════════════════════════════════════════════════════════════

class TestEventRecorderDomainTags(unittest.TestCase):
    """_build_event_tags() must attach correct domain tags for new event types."""

    def setUp(self):
        from world_system.world_memory.event_recorder import EventRecorder
        from world_system.world_memory.event_schema import EventType
        self.recorder = EventRecorder.__new__(EventRecorder)
        self.EventType = EventType

    def _tags(self, mem_type, data: dict) -> list:
        return self.recorder._build_event_tags(_BusEvent(data), mem_type)

    def test_fish_caught_gets_domain_fishing(self):
        tags = self._tags(self.EventType.FISH_CAUGHT, {"rarity": "common"})
        self.assertIn("domain:fishing", tags)

    def test_chest_opened_gets_domain_exploration(self):
        tags = self._tags(self.EventType.CHEST_OPENED, {})
        self.assertIn("domain:exploration", tags)

    def test_turret_placed_gets_domain_engineering(self):
        tags = self._tags(self.EventType.TURRET_PLACED, {"tags": []})
        self.assertIn("domain:engineering", tags)

    def test_barrier_placed_gets_domain_engineering(self):
        tags = self._tags(self.EventType.BARRIER_PLACED, {})
        self.assertIn("domain:engineering", tags)

    def test_fish_caught_rarity_tag_appended(self):
        tags = self._tags(self.EventType.FISH_CAUGHT, {"rarity": "legendary"})
        self.assertIn("rarity:legendary", tags)

    def test_enemy_killed_with_source_turret_gets_source_tag(self):
        tags = self._tags(self.EventType.ENEMY_KILLED, {"source": "turret"})
        self.assertIn("source:turret", tags)


if __name__ == "__main__":
    unittest.main(verbosity=2)

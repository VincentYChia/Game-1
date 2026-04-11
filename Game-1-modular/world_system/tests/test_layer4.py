"""Tests for Layer 4 province summarization system.

Tests cover:
1. TriggerRegistry and TriggerBucket
2. ProvinceSummaryEvent dataclass
3. Layer4Summarizer (is_applicable, summarize, XML block, L2 filtering)
4. Layer4Manager trigger logic and orchestration
5. PromptAssembler L4 assembly
6. Tag assignment for Layer 4
7. Full integration pipeline (L3 → L4)
"""

import json
import os
import sys
import unittest
import uuid

_this_dir = os.path.dirname(os.path.abspath(__file__))
_game_dir = os.path.dirname(os.path.dirname(_this_dir))
if _game_dir not in sys.path:
    sys.path.insert(0, _game_dir)

from world_system.world_memory.event_schema import (
    ProvinceSummaryEvent, SEVERITY_ORDER,
)
from world_system.world_memory.layer_store import LayerStore
from world_system.world_memory.geographic_registry import (
    GeographicRegistry, Region, RegionLevel,
)
from world_system.world_memory.trigger_registry import TriggerRegistry, TriggerBucket
from world_system.world_memory.layer4_summarizer import Layer4Summarizer
from world_system.world_memory.layer4_manager import Layer4Manager
from world_system.world_memory.prompt_assembler import PromptAssembler
from world_system.world_memory.tag_assignment import assign_higher_layer_tags


# ── Test Helpers ────────────────────────────────────────────────────


def _make_l3_event(category="regional_synthesis", severity="moderate",
                   narrative="", district_id="", province_id="",
                   game_time=100.0, extra_tags=None):
    """Create a Layer 3 event dict as stored in LayerStore."""
    tags = []
    if district_id:
        tags.append(f"district:{district_id}")
    if province_id:
        tags.append(f"province:{province_id}")
    tags.append(f"domain:{category.split('_')[0]}")
    if extra_tags:
        tags.extend(extra_tags)
    return {
        "id": str(uuid.uuid4()),
        "narrative": narrative or f"Test {category} event.",
        "category": category,
        "severity": severity,
        "tags": tags,
        "game_time": game_time,
    }


def _make_l2_event(category="combat_kills", severity="minor",
                   narrative="", province_id="", game_time=100.0,
                   extra_tags=None):
    """Create a Layer 2 event dict."""
    tags = []
    if province_id:
        tags.append(f"province:{province_id}")
    tags.append(f"domain:{category.split('_')[0]}")
    if extra_tags:
        tags.extend(extra_tags)
    return {
        "id": str(uuid.uuid4()),
        "narrative": narrative or f"Test L2 {category}.",
        "category": category,
        "severity": severity,
        "tags": tags,
        "game_time": game_time,
    }


def _setup_geo_registry():
    """Create a test geographic hierarchy with provinces and districts."""
    GeographicRegistry.reset()
    geo = GeographicRegistry.get_instance()

    realm = Region(
        region_id="realm_0", name="Test Realm",
        level=RegionLevel.REALM,
        bounds_x1=-100, bounds_y1=-100, bounds_x2=100, bounds_y2=100,
    )
    geo.regions["realm_0"] = realm
    geo.realm = realm

    # Province (WMS PROVINCE = game nation)
    province = Region(
        region_id="nation_1", name="Northern Kingdom",
        level=RegionLevel.PROVINCE,
        bounds_x1=-100, bounds_y1=-100, bounds_x2=100, bounds_y2=0,
        parent_id="realm_0",
    )
    geo.regions["nation_1"] = province
    realm.child_ids.append("nation_1")

    # Second province
    province2 = Region(
        region_id="nation_2", name="Southern Empire",
        level=RegionLevel.PROVINCE,
        bounds_x1=-100, bounds_y1=0, bounds_x2=100, bounds_y2=100,
        parent_id="realm_0",
    )
    geo.regions["nation_2"] = province2
    realm.child_ids.append("nation_2")

    # Districts (children of province)
    for i, (name, parent) in enumerate([
        ("Western Frontier", "nation_1"),
        ("Iron Reaches", "nation_1"),
        ("Southern Plains", "nation_2"),
    ]):
        district = Region(
            region_id=f"region_{i}",
            name=name,
            level=RegionLevel.DISTRICT,
            bounds_x1=-100 + i * 50, bounds_y1=-100,
            bounds_x2=-50 + i * 50, bounds_y2=0,
            parent_id=parent,
        )
        geo.regions[district.region_id] = district
        geo.regions[parent].child_ids.append(district.region_id)

    return geo


def _setup_layer_store():
    return LayerStore(db_path=":memory:")


# ══════════════════════════════════════════════════════════════════
# 1. TriggerRegistry Tests
# ══════════════════════════════════════════════════════════════════


class TestTriggerBucket(unittest.TestCase):

    def test_increment_below_threshold(self):
        bucket = TriggerBucket(name="test", threshold=3)
        self.assertFalse(bucket.increment("key_a"))
        self.assertFalse(bucket.increment("key_a"))
        self.assertEqual(bucket.get_count("key_a"), 2)
        self.assertFalse(bucket.has_fired())

    def test_increment_reaches_threshold(self):
        bucket = TriggerBucket(name="test", threshold=3)
        bucket.increment("key_a")
        bucket.increment("key_a")
        self.assertTrue(bucket.increment("key_a"))
        self.assertTrue(bucket.has_fired())

    def test_pop_fired_resets_counter(self):
        bucket = TriggerBucket(name="test", threshold=2)
        bucket.increment("key_a", 2)
        bucket.increment("key_b", 2)
        fired = bucket.pop_fired()
        self.assertEqual(sorted(fired), ["key_a", "key_b"])
        self.assertEqual(bucket.get_count("key_a"), 0)
        self.assertFalse(bucket.has_fired())

    def test_multiple_keys_independent(self):
        bucket = TriggerBucket(name="test", threshold=3)
        bucket.increment("key_a", 3)
        bucket.increment("key_b", 1)
        self.assertTrue(bucket.has_fired())
        fired = bucket.pop_fired()
        self.assertEqual(fired, ["key_a"])
        # key_b still tracked
        self.assertEqual(bucket.get_count("key_b"), 1)

    def test_serialization_roundtrip(self):
        bucket = TriggerBucket(name="test", threshold=5)
        bucket.increment("key_a", 3)
        bucket.increment("key_b", 5)  # fires
        state = bucket.get_state()
        restored = TriggerBucket.from_state(state)
        self.assertEqual(restored.name, "test")
        self.assertEqual(restored.threshold, 5)
        self.assertEqual(restored.get_count("key_a"), 3)
        self.assertIn("key_b", restored.fired)


class TestTriggerRegistry(unittest.TestCase):

    def setUp(self):
        TriggerRegistry.reset()
        self.registry = TriggerRegistry.get_instance()

    def tearDown(self):
        TriggerRegistry.reset()

    def test_register_and_increment(self):
        self.registry.register_bucket("test_bucket", threshold=3)
        self.assertFalse(self.registry.increment("test_bucket", "k1"))
        self.assertFalse(self.registry.increment("test_bucket", "k1"))
        self.assertTrue(self.registry.increment("test_bucket", "k1"))

    def test_get_and_clear_fired(self):
        self.registry.register_bucket("b", threshold=2)
        self.registry.increment("b", "x", 2)
        self.registry.increment("b", "y", 2)
        fired = self.registry.get_and_clear_fired("b")
        self.assertEqual(sorted(fired), ["x", "y"])
        self.assertFalse(self.registry.has_fired("b"))

    def test_nonexistent_bucket(self):
        self.assertFalse(self.registry.increment("nope", "k"))
        self.assertEqual(self.registry.get_and_clear_fired("nope"), [])

    def test_state_save_load(self):
        self.registry.register_bucket("b1", threshold=5)
        self.registry.increment("b1", "k", 3)
        state = self.registry.get_state()

        TriggerRegistry.reset()
        registry2 = TriggerRegistry.get_instance()
        registry2.register_bucket("b1", threshold=5)
        registry2.load_state(state)
        bucket = registry2.get_bucket("b1")
        self.assertEqual(bucket.get_count("k"), 3)

    def test_singleton(self):
        r1 = TriggerRegistry.get_instance()
        r2 = TriggerRegistry.get_instance()
        self.assertIs(r1, r2)


# ══════════════════════════════════════════════════════════════════
# 2. ProvinceSummaryEvent Tests
# ══════════════════════════════════════════════════════════════════


class TestProvinceSummaryEvent(unittest.TestCase):

    def test_create_factory(self):
        event = ProvinceSummaryEvent.create(
            province_id="nation_1",
            narrative="Test summary.",
            severity="moderate",
            source_consolidation_ids=["id1", "id2"],
            game_time=500.0,
        )
        self.assertTrue(event.summary_id)
        self.assertEqual(event.province_id, "nation_1")
        self.assertEqual(event.narrative, "Test summary.")
        self.assertEqual(event.severity, "moderate")
        self.assertEqual(event.created_at, 500.0)
        self.assertEqual(event.threat_level, "low")
        self.assertEqual(event.dominant_activities, [])

    def test_create_with_kwargs(self):
        event = ProvinceSummaryEvent.create(
            province_id="nation_2",
            narrative="Heavy mining.",
            severity="significant",
            source_consolidation_ids=["a"],
            game_time=100.0,
            dominant_activities=["mining", "combat"],
            threat_level="high",
        )
        self.assertEqual(event.dominant_activities, ["mining", "combat"])
        self.assertEqual(event.threat_level, "high")


# ══════════════════════════════════════════════════════════════════
# 3. Layer4Summarizer Tests
# ══════════════════════════════════════════════════════════════════


class TestLayer4Summarizer(unittest.TestCase):

    def setUp(self):
        self.summarizer = Layer4Summarizer()
        self.geo = _setup_geo_registry()

    def tearDown(self):
        GeographicRegistry.reset()

    def test_is_applicable_needs_province(self):
        events = [_make_l3_event()] * 3
        self.assertFalse(self.summarizer.is_applicable(events, ""))
        self.assertTrue(self.summarizer.is_applicable(events, "nation_1"))

    def test_is_applicable_needs_2_events(self):
        self.assertFalse(self.summarizer.is_applicable(
            [_make_l3_event()], "nation_1"))
        self.assertTrue(self.summarizer.is_applicable(
            [_make_l3_event()] * 2, "nation_1"))

    def test_summarize_produces_event(self):
        events = [
            _make_l3_event("regional_synthesis", "moderate",
                           "Western Frontier: heavy mining.",
                           district_id="region_0", province_id="nation_1",
                           extra_tags=["domain:gathering"]),
            _make_l3_event("cross_domain", "minor",
                           "Combat and gathering co-occurring.",
                           district_id="region_1", province_id="nation_1",
                           extra_tags=["domain:combat"]),
            _make_l3_event("regional_synthesis", "significant",
                           "Iron Reaches: combat-heavy.",
                           district_id="region_1", province_id="nation_1",
                           extra_tags=["domain:combat"]),
        ]
        geo_context = {
            "province_name": "Northern Kingdom",
            "districts": [
                {"id": "region_0", "name": "Western Frontier"},
                {"id": "region_1", "name": "Iron Reaches"},
            ],
        }
        result = self.summarizer.summarize(
            events, [], "nation_1", geo_context, game_time=500.0)

        self.assertIsNotNone(result)
        self.assertEqual(result.province_id, "nation_1")
        self.assertIn("Northern Kingdom", result.narrative)
        self.assertEqual(len(result.source_consolidation_ids), 3)
        self.assertIn("province:nation_1", result.tags)

    def test_summarize_empty(self):
        result = self.summarizer.summarize(
            [], [], "nation_1", {}, game_time=100.0)
        self.assertIsNone(result)

    def test_summarize_with_l2_context(self):
        l3 = [_make_l3_event(extra_tags=["domain:combat", "species:wolf"]),
              _make_l3_event(extra_tags=["domain:gathering"])]
        l2 = [_make_l2_event(extra_tags=["domain:combat", "species:wolf"])]
        result = self.summarizer.summarize(
            l3, l2, "nation_1",
            {"province_name": "NK", "districts": []}, 200.0)
        self.assertIsNotNone(result)
        self.assertEqual(len(result.relevant_l2_ids), 1)

    def test_determine_threat_level(self):
        # No danger tags → low
        events = [_make_l3_event(extra_tags=["domain:gathering"])]
        self.assertEqual(
            self.summarizer._determine_threat_level(events), "low")

        # Dangerous + significant → high
        events = [_make_l3_event(
            severity="significant",
            extra_tags=["sentiment:dangerous", "domain:combat"])]
        self.assertEqual(
            self.summarizer._determine_threat_level(events), "high")

    def test_extract_dominant_activities(self):
        events = [
            _make_l3_event(category="combat_kills",
                           extra_tags=["domain:combat"]),
            _make_l3_event(category="combat_kills",
                           extra_tags=["domain:combat"]),
            _make_l3_event(category="gathering_regional",
                           extra_tags=["domain:gathering"]),
        ]
        result = self.summarizer._extract_dominant_activities(events)
        # combat appears 4x (2 from category + 2 from extra), gathering 2x
        self.assertEqual(result[0], "combat")

    def test_determine_severity_boost(self):
        # 3+ districts → severity boost
        events = [
            _make_l3_event(severity="moderate",
                           extra_tags=["district:r0"]),
            _make_l3_event(severity="moderate",
                           extra_tags=["district:r1"]),
            _make_l3_event(severity="moderate",
                           extra_tags=["district:r2"]),
        ]
        sev = self.summarizer._determine_severity(events)
        self.assertEqual(sev, "significant")  # boosted from moderate


class TestLayer4SummarizerXML(unittest.TestCase):

    def setUp(self):
        self.summarizer = Layer4Summarizer()

    def test_build_xml_basic(self):
        l3 = [
            _make_l3_event("regional_synthesis", narrative="District active.",
                           district_id="region_0", game_time=100.0),
        ]
        districts = [{"id": "region_0", "name": "Western Frontier"}]
        xml = self.summarizer.build_xml_data_block(
            l3, [], "Northern Kingdom", districts, game_time=200.0)
        self.assertIn('<province name="Northern Kingdom">', xml)
        self.assertIn('<district name="Western Frontier">', xml)
        self.assertIn("District active.", xml)
        self.assertIn('when="', xml)

    def test_build_xml_with_global_events(self):
        l3 = [
            _make_l3_event("player_identity", narrative="Player is a miner."),
        ]
        xml = self.summarizer.build_xml_data_block(
            l3, [], "NK", [], game_time=200.0)
        self.assertIn("<cross-district>", xml)
        self.assertIn("Player is a miner.", xml)

    def test_build_xml_with_l2_support(self):
        l2 = [_make_l2_event(narrative="Killed 5 wolves.")]
        xml = self.summarizer.build_xml_data_block(
            [], l2, "NK", [], game_time=200.0)
        self.assertIn("<supporting-detail>", xml)
        self.assertIn("Killed 5 wolves.", xml)


class TestLayer4L2Filtering(unittest.TestCase):

    def test_filter_by_tag_overlap(self):
        l3 = [_make_l3_event(extra_tags=["domain:combat", "species:wolf"])]
        l2_relevant = [_make_l2_event(
            extra_tags=["domain:combat", "species:wolf"])]
        l2_irrelevant = [_make_l2_event(
            extra_tags=["domain:crafting", "discipline:alchemy"])]

        result = Layer4Summarizer.filter_relevant_l2(
            l2_relevant + l2_irrelevant, l3)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["id"], l2_relevant[0]["id"])

    def test_filter_needs_min_shared(self):
        l3 = [_make_l3_event(extra_tags=["domain:combat", "species:wolf"])]
        l2_one_tag = [_make_l2_event(extra_tags=["domain:combat"])]
        result = Layer4Summarizer.filter_relevant_l2(l2_one_tag, l3)
        self.assertEqual(len(result), 0)  # Only 1 shared tag, needs 2

    def test_filter_empty_l3(self):
        l2 = [_make_l2_event(extra_tags=["domain:combat"])]
        result = Layer4Summarizer.filter_relevant_l2(l2, [])
        self.assertEqual(len(result), 0)

    def test_filter_caps_at_15(self):
        l3 = [_make_l3_event(extra_tags=["domain:combat", "species:wolf"])]
        l2 = [_make_l2_event(extra_tags=["domain:combat", "species:wolf"])
              for _ in range(20)]
        result = Layer4Summarizer.filter_relevant_l2(l2, l3)
        self.assertLessEqual(len(result), 15)


# ══════════════════════════════════════════════════════════════════
# 4. Layer4Manager Tests
# ══════════════════════════════════════════════════════════════════


class TestLayer4Manager(unittest.TestCase):

    def setUp(self):
        Layer4Manager.reset()
        TriggerRegistry.reset()
        self.geo = _setup_geo_registry()
        self.layer_store = _setup_layer_store()
        self.manager = Layer4Manager.get_instance()
        self.manager.initialize(
            layer_store=self.layer_store,
            geo_registry=self.geo,
        )

    def tearDown(self):
        Layer4Manager.reset()
        TriggerRegistry.reset()
        GeographicRegistry.reset()

    def test_should_run_false_initially(self):
        self.assertFalse(self.manager.should_run())

    def test_on_layer3_created_increments(self):
        event = _make_l3_event(province_id="nation_1")
        self.manager.on_layer3_created(event)
        self.assertFalse(self.manager.should_run())  # 1 < 3

    def test_fires_after_threshold(self):
        for _ in range(3):
            self.manager.on_layer3_created(
                _make_l3_event(province_id="nation_1"))
        self.assertTrue(self.manager.should_run())

    def test_provinces_fire_independently(self):
        for _ in range(3):
            self.manager.on_layer3_created(
                _make_l3_event(province_id="nation_1"))
        self.manager.on_layer3_created(
            _make_l3_event(province_id="nation_2"))
        self.assertTrue(self.manager.should_run())
        # Only nation_1 should fire

    def test_run_with_no_stored_events_creates_nothing(self):
        """Trigger fires but LayerStore has no L3 data → 0 summaries."""
        for _ in range(3):
            self.manager.on_layer3_created(
                _make_l3_event(province_id="nation_1"))
        result = self.manager.run_summarization(500.0)
        self.assertEqual(result, 0)

    def test_extract_province(self):
        event = {"tags": ["district:region_0", "province:nation_1"]}
        self.assertEqual(self.manager._extract_province(event), "nation_1")

    def test_extract_province_json_tags(self):
        event = {"tags": '["province:nation_2"]'}
        self.assertEqual(self.manager._extract_province(event), "nation_2")

    def test_extract_province_missing(self):
        event = {"tags": ["district:region_0"]}
        self.assertIsNone(self.manager._extract_province(event))

    def test_stats(self):
        stats = self.manager.stats
        self.assertTrue(stats["initialized"])
        self.assertEqual(stats["summaries_created"], 0)
        self.assertIn("trigger", stats)


# ══════════════════════════════════════════════════════════════════
# 5. Layer4Manager Integration Tests
# ══════════════════════════════════════════════════════════════════


class TestLayer4Integration(unittest.TestCase):
    """Full pipeline: store L3 events → trigger L4 → verify stored."""

    def setUp(self):
        Layer4Manager.reset()
        TriggerRegistry.reset()
        self.geo = _setup_geo_registry()
        self.layer_store = _setup_layer_store()
        self.manager = Layer4Manager.get_instance()
        self.manager.initialize(
            layer_store=self.layer_store,
            geo_registry=self.geo,
        )

    def tearDown(self):
        Layer4Manager.reset()
        TriggerRegistry.reset()
        GeographicRegistry.reset()

    def _store_l3_events(self, province_id, count, district_ids=None):
        """Store L3 events in LayerStore and notify manager."""
        district_ids = district_ids or ["region_0", "region_1"]
        for i in range(count):
            d_id = district_ids[i % len(district_ids)]
            tags = [
                f"district:{d_id}",
                f"province:{province_id}",
                "domain:combat",
                "sentiment:dangerous",
            ]
            event_id = self.layer_store.insert_event(
                layer=3,
                narrative=f"L3 event {i} in {d_id}.",
                game_time=100.0 + i * 10,
                category="regional_synthesis",
                severity="moderate",
                significance="moderate",
                tags=tags,
                origin_ref="[]",
            )
            self.manager.on_layer3_created({
                "id": event_id,
                "tags": tags,
                "category": "regional_synthesis",
                "severity": "moderate",
                "narrative": f"L3 event {i}.",
                "game_time": 100.0 + i * 10,
            })

    def test_full_pipeline_creates_l4(self):
        self._store_l3_events("nation_1", 3)
        self.assertTrue(self.manager.should_run())
        created = self.manager.run_summarization(500.0)
        self.assertEqual(created, 1)
        self.assertFalse(self.manager.should_run())

        # Verify stored in LayerStore
        l4_events = self.layer_store.query_by_tags(
            layer=4, tags=["province:nation_1"], match_all=True)
        self.assertEqual(len(l4_events), 1)
        self.assertEqual(l4_events[0]["category"], "province_summary")
        self.assertIn("province:nation_1", l4_events[0]["tags"])

    def test_supersedes_previous_summary(self):
        # First summary
        self._store_l3_events("nation_1", 3)
        self.manager.run_summarization(500.0)

        # Second summary (3 more events)
        self._store_l3_events("nation_1", 3)
        self.manager.run_summarization(600.0)

        # Both exist in store
        l4_events = self.layer_store.query_by_tags(
            layer=4, tags=["province:nation_1"], match_all=True)
        self.assertEqual(len(l4_events), 2)

    def test_multiple_provinces(self):
        self._store_l3_events("nation_1", 3, ["region_0", "region_1"])
        self._store_l3_events("nation_2", 3, ["region_2"])
        created = self.manager.run_summarization(500.0)
        self.assertEqual(created, 2)

    def test_geo_context_built_correctly(self):
        ctx = self.manager._build_geo_context("nation_1")
        self.assertEqual(ctx["province_name"], "Northern Kingdom")
        self.assertEqual(len(ctx["districts"]), 2)
        names = [d["name"] for d in ctx["districts"]]
        self.assertIn("Western Frontier", names)
        self.assertIn("Iron Reaches", names)

    def test_stats_after_run(self):
        self._store_l3_events("nation_1", 3)
        self.manager.run_summarization(500.0)
        stats = self.manager.stats
        self.assertEqual(stats["summaries_created"], 1)
        self.assertEqual(stats["runs_completed"], 1)


# ══════════════════════════════════════════════════════════════════
# 6. PromptAssembler L4 Tests
# ══════════════════════════════════════════════════════════════════


class TestPromptAssemblerL4(unittest.TestCase):

    def setUp(self):
        config_dir = os.path.join(
            os.path.dirname(_this_dir), "config")
        self.assembler = PromptAssembler(
            os.path.join(config_dir, "prompt_fragments.json"))
        self.assembler.load()

    def test_l4_fragments_loaded(self):
        self.assertTrue(len(self.assembler._l4_fragments) > 0)

    def test_assemble_l4_has_system_and_user(self):
        prompt = self.assembler.assemble_l4("<province>test</province>")
        self.assertIn("province-level", prompt.system)
        self.assertIn("<province>test</province>", prompt.user)
        self.assertIn("narrative", prompt.user)  # output format
        self.assertGreater(prompt.token_estimate, 0)

    def test_get_l4_fragment(self):
        core = self.assembler.get_l4_fragment("_l4_core")
        self.assertIn("province", core.lower())

    def test_get_l4_fragment_fallback(self):
        # Non-existent L4 key falls back to L3/L2
        result = self.assembler.get_l4_fragment("nonexistent_key")
        # Should return empty string (no match in any layer)
        self.assertEqual(result, "")


# ══════════════════════════════════════════════════════════════════
# 7. Tag Assignment for Layer 4
# ══════════════════════════════════════════════════════════════════


class TestLayer4TagAssignment(unittest.TestCase):

    def test_inherits_from_l3(self):
        origin_tags = [
            ["district:region_0", "province:nation_1", "domain:combat",
             "significance:moderate", "sentiment:dangerous"],
            ["district:region_1", "province:nation_1", "domain:gathering",
             "significance:minor"],
        ]
        tags = assign_higher_layer_tags(
            layer=4,
            origin_event_tags=origin_tags,
            significance="significant",
            layer_specific_tags=["threat_level:high", "intensity:heavy"],
        )
        # Should have significance recreated
        self.assertIn("significance:significant", tags)
        # Should inherit province
        self.assertIn("province:nation_1", tags)
        # Should have layer-specific tags
        self.assertIn("threat_level:high", tags)
        self.assertIn("intensity:heavy", tags)
        # Should NOT have old significance
        old_sigs = [t for t in tags if t == "significance:moderate"
                    or t == "significance:minor"]
        self.assertEqual(len(old_sigs), 0)

    def test_rewrite_all_path(self):
        origin_tags = [["province:nation_1", "domain:combat"]]
        rewrite = [
            "province:nation_1", "domain:combat",
            "urgency_level:high", "event_status:escalating",
        ]
        tags = assign_higher_layer_tags(
            layer=4,
            origin_event_tags=origin_tags,
            significance="major",
            rewrite_all=rewrite,
        )
        self.assertIn("significance:major", tags)
        self.assertIn("urgency_level:high", tags)
        self.assertIn("event_status:escalating", tags)


# ══════════════════════════════════════════════════════════════════
# 8. Layer3Manager Callback Wiring
# ══════════════════════════════════════════════════════════════════


class TestL3ToL4Callback(unittest.TestCase):
    """Verify Layer3Manager callback notifies Layer4Manager."""

    def setUp(self):
        Layer4Manager.reset()
        TriggerRegistry.reset()
        from world_system.world_memory.layer3_manager import Layer3Manager
        Layer3Manager.reset()
        self.geo = _setup_geo_registry()
        self.layer_store = _setup_layer_store()

        self.l3_manager = Layer3Manager.get_instance()
        self.l3_manager.initialize(
            layer_store=self.layer_store,
            geo_registry=self.geo,
        )

        self.l4_manager = Layer4Manager.get_instance()
        self.l4_manager.initialize(
            layer_store=self.layer_store,
            geo_registry=self.geo,
        )
        self.l3_manager.set_layer4_callback(self.l4_manager.on_layer3_created)

    def tearDown(self):
        from world_system.world_memory.layer3_manager import Layer3Manager
        Layer3Manager.reset()
        Layer4Manager.reset()
        TriggerRegistry.reset()
        GeographicRegistry.reset()

    def test_callback_is_set(self):
        self.assertIsNotNone(self.l3_manager._layer4_callback)

    def test_callback_called_on_store(self):
        """Simulating L3 store should call the L4 callback."""
        from world_system.world_memory.event_schema import ConsolidatedEvent
        event = ConsolidatedEvent.create(
            narrative="Test consolidation.",
            category="regional_synthesis",
            severity="moderate",
            source_interpretation_ids=["src1"],
            game_time=200.0,
            affected_district_ids=["region_0"],
            affects_tags=["district:region_0", "province:nation_1",
                          "domain:combat"],
        )
        self.l3_manager._store_consolidation(event, 200.0)

        # L4 manager should have received the notification
        bucket = TriggerRegistry.get_instance().get_bucket("layer4_provinces")
        self.assertEqual(bucket.get_count("nation_1"), 1)


# ══════════════════════════════════════════════════════════════════


if __name__ == "__main__":
    unittest.main()

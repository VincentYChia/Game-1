"""Tests for Layer 4 province summarization system.

Tests cover:
1. TriggerRegistry — simple and weighted buckets
2. WeightedTriggerBucket — positional tag scoring
3. ProvinceSummaryEvent dataclass
4. Layer4Summarizer — template narrative, XML data block, L2 filtering
5. Layer4Manager — trigger flow, province grouping, storage
6. PromptAssembler L4 — fragment aggregation across layers
7. Geographic hierarchy — NATION level, province-level addressing
8. Full integration: L3 → weighted trigger → L4 storage
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
from world_system.world_memory.trigger_registry import (
    TriggerRegistry, TriggerBucket, WeightedTriggerBucket,
    tag_weight_for_position,
)
from world_system.world_memory.layer_store import LayerStore
from world_system.world_memory.geographic_registry import (
    GeographicRegistry, Region, RegionLevel,
)
from world_system.world_memory.layer4_summarizer import Layer4Summarizer
from world_system.world_memory.layer4_manager import Layer4Manager, BUCKET_PREFIX
from world_system.world_memory.tag_assignment import assign_higher_layer_tags
from world_system.world_memory.prompt_assembler import PromptAssembler


# ── Helpers ────────────────────────────────────────────────────────

def _make_l3_event(category="regional_synthesis", severity="moderate",
                   narrative="", district_id="", province_id="",
                   game_time=100.0, extra_tags=None):
    tags = []
    if province_id:
        tags.append(f"province:{province_id}")
    if district_id:
        tags.append(f"district:{district_id}")
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


def _setup_geo_registry():
    GeographicRegistry.reset()
    geo = GeographicRegistry.get_instance()

    realm = Region(region_id="realm_0", name="Test Realm",
                   level=RegionLevel.REALM,
                   bounds_x1=-100, bounds_y1=-100,
                   bounds_x2=100, bounds_y2=100)
    geo.regions["realm_0"] = realm
    geo.realm = realm

    nation = Region(region_id="nation_1", name="Northern Kingdom",
                    level=RegionLevel.NATION,
                    bounds_x1=-100, bounds_y1=-100,
                    bounds_x2=100, bounds_y2=0,
                    parent_id="realm_0")
    geo.regions["nation_1"] = nation
    realm.child_ids.append("nation_1")

    province = Region(region_id="region_1", name="Iron Reaches",
                      level=RegionLevel.PROVINCE,
                      bounds_x1=-100, bounds_y1=-100,
                      bounds_x2=0, bounds_y2=0,
                      parent_id="nation_1")
    geo.regions["region_1"] = province
    nation.child_ids.append("region_1")

    for i, name in enumerate(["Western Mines", "Eastern Fields"]):
        district = Region(region_id=f"province_{i}",
                         name=name, level=RegionLevel.DISTRICT,
                         bounds_x1=-100 + i*50, bounds_y1=-100,
                         bounds_x2=-50 + i*50, bounds_y2=-50,
                         parent_id="region_1")
        geo.regions[district.region_id] = district
        province.child_ids.append(district.region_id)

    return geo


# ══════════════════════════════════════════════════════════════════
# 1. Tag Weight Function
# ══════════════════════════════════════════════════════════════════

class TestTagWeights(unittest.TestCase):

    def test_position_weights(self):
        self.assertEqual(tag_weight_for_position(0), 10)
        self.assertEqual(tag_weight_for_position(1), 8)
        self.assertEqual(tag_weight_for_position(2), 6)
        self.assertEqual(tag_weight_for_position(3), 5)
        self.assertEqual(tag_weight_for_position(4), 4)
        self.assertEqual(tag_weight_for_position(5), 3)
        for i in range(6, 12):
            self.assertEqual(tag_weight_for_position(i), 2)
        self.assertEqual(tag_weight_for_position(12), 1)
        self.assertEqual(tag_weight_for_position(100), 1)


# ══════════════════════════════════════════════════════════════════
# 2. Simple TriggerBucket
# ══════════════════════════════════════════════════════════════════

class TestTriggerBucket(unittest.TestCase):

    def test_increment_and_fire(self):
        b = TriggerBucket(name="test", threshold=3)
        self.assertFalse(b.increment("k1"))
        self.assertFalse(b.increment("k1"))
        self.assertTrue(b.increment("k1"))
        self.assertTrue(b.has_fired())

    def test_pop_fired_resets(self):
        b = TriggerBucket(name="test", threshold=2)
        b.increment("k1", 2)
        b.increment("k2", 2)
        fired = b.pop_fired()
        self.assertEqual(sorted(fired), ["k1", "k2"])
        self.assertFalse(b.has_fired())
        self.assertEqual(b.get_count("k1"), 0)

    def test_serialization(self):
        b = TriggerBucket(name="test", threshold=5)
        b.increment("k1", 3)
        state = b.get_state()
        b2 = TriggerBucket.from_state(state)
        self.assertEqual(b2.get_count("k1"), 3)
        self.assertEqual(b2.threshold, 5)


# ══════════════════════════════════════════════════════════════════
# 3. WeightedTriggerBucket
# ══════════════════════════════════════════════════════════════════

class TestWeightedTriggerBucket(unittest.TestCase):

    def test_single_event_scoring(self):
        b = WeightedTriggerBucket(name="test", threshold=50)
        tags = ["province:region_1", "domain:combat", "intensity:heavy"]
        b.ingest_event("e1", tags)
        # Position 0=10, 1=8, 2=6
        self.assertEqual(b.get_score("province:region_1"), 10)
        self.assertEqual(b.get_score("domain:combat"), 8)
        self.assertEqual(b.get_score("intensity:heavy"), 6)

    def test_threshold_fires(self):
        b = WeightedTriggerBucket(name="test", threshold=20)
        # Position 0 = 10 points each time
        b.ingest_event("e1", ["province:region_1", "x:y"])
        self.assertFalse(b.has_fired())
        newly = b.ingest_event("e2", ["province:region_1", "x:y"])
        self.assertTrue(b.has_fired())
        self.assertIn("province:region_1", newly)

    def test_contributor_tracking(self):
        b = WeightedTriggerBucket(name="test", threshold=20)
        b.ingest_event("e1", ["province:region_1"])
        b.ingest_event("e2", ["province:region_1"])
        fired = b.pop_fired()
        self.assertIn("province:region_1", fired)
        self.assertEqual(sorted(fired["province:region_1"]), ["e1", "e2"])

    def test_skip_structural_tags(self):
        b = WeightedTriggerBucket(name="test", threshold=5)
        b.ingest_event("e1", ["significance:major", "scope:province"])
        self.assertEqual(b.get_score("significance:major"), 0)
        self.assertEqual(b.get_score("scope:province"), 0)

    def test_pop_resets_fired_tag(self):
        b = WeightedTriggerBucket(name="test", threshold=10)
        b.ingest_event("e1", ["province:region_1"])  # 10 pts
        self.assertTrue(b.has_fired())
        fired = b.pop_fired()
        self.assertFalse(b.has_fired())
        self.assertEqual(b.get_score("province:region_1"), 0)

    def test_serialization(self):
        b = WeightedTriggerBucket(name="test", threshold=50)
        b.ingest_event("e1", ["province:region_1", "domain:combat"])
        state = b.get_state()
        b2 = WeightedTriggerBucket.from_state(state)
        self.assertEqual(b2.get_score("province:region_1"), 10)
        self.assertEqual(b2.threshold, 50)

    def test_multiple_tags_fire_independently(self):
        b = WeightedTriggerBucket(name="test", threshold=15)
        b.ingest_event("e1", ["domain:combat", "province:region_1"])
        b.ingest_event("e2", ["domain:combat", "province:region_1"])
        # domain:combat = 10+10 = 20 (fires), province:region_1 = 8+8 = 16 (fires)
        fired = b.pop_fired()
        self.assertIn("domain:combat", fired)
        self.assertIn("province:region_1", fired)


# ══════════════════════════════════════════════════════════════════
# 4. TriggerRegistry
# ══════════════════════════════════════════════════════════════════

class TestTriggerRegistry(unittest.TestCase):

    def setUp(self):
        TriggerRegistry.reset()
        self.registry = TriggerRegistry.get_instance()

    def tearDown(self):
        TriggerRegistry.reset()

    def test_simple_bucket(self):
        self.registry.register_bucket("test", threshold=2)
        self.registry.increment("test", "k1")
        self.assertFalse(self.registry.has_fired("test"))
        self.registry.increment("test", "k1")
        self.assertTrue(self.registry.has_fired("test"))

    def test_weighted_bucket(self):
        self.registry.register_weighted_bucket("wt", threshold=20)
        self.registry.ingest_event_weighted("wt", "e1",
            ["province:region_1", "domain:combat"])
        self.assertFalse(self.registry.has_fired_weighted("wt"))
        self.registry.ingest_event_weighted("wt", "e2",
            ["province:region_1", "domain:combat"])
        self.assertTrue(self.registry.has_fired_weighted("wt"))

    def test_prefix_based_operations(self):
        self.registry.register_weighted_bucket("layer4_province_r1", threshold=10)
        self.registry.register_weighted_bucket("layer4_province_r2", threshold=10)
        self.registry.ingest_event_weighted("layer4_province_r1", "e1",
            ["domain:combat"])  # 10 → fires
        self.assertFalse(
            self.registry.any_weighted_fired_with_prefix("layer4_province_r2"))
        self.assertTrue(
            self.registry.any_weighted_fired_with_prefix("layer4_province_"))
        # Pop only fired buckets
        result = self.registry.pop_all_fired_weighted_with_prefix(
            "layer4_province_")
        self.assertIn("layer4_province_r1", result)
        self.assertNotIn("layer4_province_r2", result)
        # Verify bucket name listing
        names = self.registry.get_weighted_bucket_names("layer4_province_")
        self.assertEqual(sorted(names),
                         ["layer4_province_r1", "layer4_province_r2"])

    def test_save_load_state(self):
        self.registry.register_bucket("simple", threshold=5)
        self.registry.increment("simple", "k1", 3)
        self.registry.register_weighted_bucket("wt", threshold=50)
        self.registry.ingest_event_weighted("wt", "e1",
            ["province:region_1"])
        state = self.registry.get_state()

        TriggerRegistry.reset()
        reg2 = TriggerRegistry.get_instance()
        reg2.register_bucket("simple", threshold=5)
        reg2.register_weighted_bucket("wt", threshold=50)
        reg2.load_state(state)

        bucket = reg2.get_bucket("simple")
        self.assertEqual(bucket.get_count("k1"), 3)
        wbucket = reg2.get_weighted_bucket("wt")
        self.assertEqual(wbucket.get_score("province:region_1"), 10)


# ══════════════════════════════════════════════════════════════════
# 5. ProvinceSummaryEvent
# ══════════════════════════════════════════════════════════════════

class TestProvinceSummaryEvent(unittest.TestCase):

    def test_create_factory(self):
        evt = ProvinceSummaryEvent.create(
            province_id="region_1",
            narrative="Test summary.",
            severity="moderate",
            source_consolidation_ids=["id1", "id2"],
            game_time=500.0,
        )
        self.assertTrue(evt.summary_id)
        self.assertEqual(evt.province_id, "region_1")
        self.assertEqual(evt.narrative, "Test summary.")
        self.assertEqual(len(evt.source_consolidation_ids), 2)
        self.assertEqual(evt.created_at, 500.0)


# ══════════════════════════════════════════════════════════════════
# 6. Layer4Summarizer
# ══════════════════════════════════════════════════════════════════

class TestLayer4Summarizer(unittest.TestCase):

    def setUp(self):
        self.summarizer = Layer4Summarizer()
        self.geo = _setup_geo_registry()

    def tearDown(self):
        GeographicRegistry.reset()

    def test_is_applicable_needs_2_events(self):
        events = [_make_l3_event(province_id="region_1")]
        self.assertFalse(self.summarizer.is_applicable(events, "region_1"))
        events.append(_make_l3_event(province_id="region_1"))
        self.assertTrue(self.summarizer.is_applicable(events, "region_1"))

    def test_summarize_produces_event(self):
        events = [
            _make_l3_event("regional_synthesis", "moderate",
                          "Iron Reaches busy.", province_id="region_1",
                          district_id="province_0"),
            _make_l3_event("cross_domain", "minor",
                          "Combat and gathering.", province_id="region_1",
                          district_id="province_1"),
        ]
        geo_ctx = {
            "province_name": "Iron Reaches",
            "districts": [
                {"id": "province_0", "name": "Western Mines"},
                {"id": "province_1", "name": "Eastern Fields"},
            ],
        }
        result = self.summarizer.summarize(
            events, [], "region_1", geo_ctx, game_time=200.0)
        self.assertIsNotNone(result)
        self.assertEqual(result.province_id, "region_1")
        self.assertIn("Iron Reaches", result.narrative)

    def test_xml_data_block_includes_tags(self):
        events = [
            _make_l3_event("regional_synthesis", "moderate",
                          "Test event.", district_id="province_0",
                          province_id="region_1",
                          extra_tags=["domain:combat"]),
        ]
        xml = self.summarizer.build_xml_data_block(
            events, [], "Iron Reaches",
            [{"id": "province_0", "name": "Western Mines"}], 200.0)
        self.assertIn('tags="[', xml)
        self.assertIn("province:region_1", xml)

    def test_filter_relevant_l2_strict(self):
        l3 = [_make_l3_event(extra_tags=["domain:combat", "species:wolf"])]
        l2_match = {"id": "m1", "tags": ["domain:combat", "species:wolf", "tier:1"],
                    "severity": "minor"}
        l2_nomatch = {"id": "n1", "tags": ["domain:crafting", "discipline:smithing"],
                      "severity": "minor"}
        result = Layer4Summarizer.filter_relevant_l2([l2_match, l2_nomatch], l3)
        ids = [e["id"] for e in result]
        self.assertIn("m1", ids)
        self.assertNotIn("n1", ids)


# ══════════════════════════════════════════════════════════════════
# 7. Layer4Manager
# ══════════════════════════════════════════════════════════════════

class TestLayer4Manager(unittest.TestCase):

    def setUp(self):
        Layer4Manager.reset()
        TriggerRegistry.reset()
        self.geo = _setup_geo_registry()
        self.layer_store = LayerStore(db_path=":memory:")
        self.manager = Layer4Manager.get_instance()
        self.manager.initialize(
            layer_store=self.layer_store,
            geo_registry=self.geo,
            wms_ai=None,
            trigger_registry=TriggerRegistry.get_instance(),
        )

    def tearDown(self):
        Layer4Manager.reset()
        TriggerRegistry.reset()
        GeographicRegistry.reset()

    def test_on_layer3_created_scores_tags(self):
        evt = _make_l3_event(province_id="region_1",
                            district_id="province_0")
        self.manager.on_layer3_created(evt)
        # Per-province bucket: geo tags stripped, content tags scored
        bucket = TriggerRegistry.get_instance().get_weighted_bucket(
            f"{BUCKET_PREFIX}region_1")
        self.assertIsNotNone(bucket)
        # domain:regional is now at position 0 = 10 pts (geo tags stripped)
        self.assertGreater(bucket.get_score("domain:regional"), 0)
        # Province tag should NOT be in the bucket (stripped)
        self.assertEqual(bucket.get_score("province:region_1"), 0)

    def test_should_run_after_threshold(self):
        self.assertFalse(self.manager.should_run())
        # domain:regional at position 0 = 10 pts each (geo tags stripped)
        # Need 5 events for 50
        for i in range(5):
            evt = _make_l3_event(province_id="region_1",
                                district_id="province_0",
                                game_time=100 + i)
            self.manager.on_layer3_created(evt)
        self.assertTrue(self.manager.should_run())

    def test_province_isolation(self):
        """Tags from different provinces do NOT cross-contaminate."""
        # 3 events in region_1: domain:regional = 10*3 = 30 (below 50)
        for i in range(3):
            evt = _make_l3_event(province_id="region_1",
                                district_id="province_0",
                                game_time=100 + i)
            self.manager.on_layer3_created(evt)

        # 3 events in region_2: domain:regional = 10*3 = 30 (below 50)
        for i in range(3):
            evt = _make_l3_event(province_id="region_2",
                                district_id="province_1",
                                game_time=200 + i)
            self.manager.on_layer3_created(evt)

        # Neither should fire (30 < 50 each), even though 30+30=60 globally
        self.assertFalse(self.manager.should_run())

    def test_run_summarization_stores_event(self):
        # Seed L3 events in LayerStore
        for i in range(6):
            eid = str(uuid.uuid4())
            self.layer_store.insert_event(
                layer=3, narrative=f"L3 event {i}",
                game_time=100 + i, category="regional_synthesis",
                severity="moderate", significance="moderate",
                tags=["province:region_1", f"district:province_{i%2}",
                      "domain:combat"],
                origin_ref="[]", event_id=eid,
            )
            self.manager.on_layer3_created({
                "id": eid,
                "tags": ["province:region_1", f"district:province_{i%2}",
                         "domain:combat"],
                "game_time": 100 + i,
            })

        self.assertTrue(self.manager.should_run())
        created = self.manager.run_summarization(game_time=200.0)
        self.assertGreaterEqual(created, 1)

        # Verify stored in layer4_events
        rows = self.layer_store.query_by_tags(
            layer=4, tags=["province:region_1"], match_all=True)
        self.assertGreaterEqual(len(rows), 1)
        self.assertEqual(rows[0]["category"], "province_summary")

    def test_stats(self):
        stats = self.manager.stats
        self.assertTrue(stats["initialized"])
        self.assertIn("trigger", stats)


# ══════════════════════════════════════════════════════════════════
# 8. Geographic Hierarchy
# ══════════════════════════════════════════════════════════════════

class TestGeographicHierarchy(unittest.TestCase):

    def setUp(self):
        self.geo = _setup_geo_registry()

    def tearDown(self):
        GeographicRegistry.reset()

    def test_nation_level_exists(self):
        self.assertEqual(RegionLevel.NATION.value, "nation")

    def test_hierarchy_levels(self):
        self.assertEqual(
            self.geo.regions["realm_0"].level, RegionLevel.REALM)
        self.assertEqual(
            self.geo.regions["nation_1"].level, RegionLevel.NATION)
        self.assertEqual(
            self.geo.regions["region_1"].level, RegionLevel.PROVINCE)
        self.assertEqual(
            self.geo.regions["province_0"].level, RegionLevel.DISTRICT)

    def test_province_children_are_districts(self):
        province = self.geo.regions["region_1"]
        self.assertEqual(province.level, RegionLevel.PROVINCE)
        for child_id in province.child_ids:
            child = self.geo.regions[child_id]
            self.assertEqual(child.level, RegionLevel.DISTRICT)


# ══════════════════════════════════════════════════════════════════
# 9. Tag Assignment (L4 rewrite path)
# ══════════════════════════════════════════════════════════════════

class TestLayer4TagAssignment(unittest.TestCase):

    def test_rewrite_all_at_layer4(self):
        origin_tags = [["province:region_1", "domain:combat"]]
        rewrite = [
            "province:region_1", "domain:combat",
            "urgency_level:high", "event_status:escalating",
        ]
        tags = assign_higher_layer_tags(
            layer=4, origin_event_tags=origin_tags,
            significance="major", rewrite_all=rewrite,
        )
        self.assertIn("significance:major", tags)
        self.assertIn("urgency_level:high", tags)

    def test_rewrite_not_available_at_layer3(self):
        origin_tags = [["district:province_0", "domain:combat"]]
        rewrite = ["custom:tag"]
        tags = assign_higher_layer_tags(
            layer=3, origin_event_tags=origin_tags,
            significance="minor", rewrite_all=rewrite,
        )
        # Layer 3 ignores rewrite_all — falls through to inheritance
        self.assertNotIn("custom:tag", tags)
        self.assertIn("district:province_0", tags)

    def test_inheritance_path_without_rewrite(self):
        origin_tags = [
            ["province:region_1", "domain:combat", "species:wolf"],
            ["province:region_1", "domain:gathering", "resource:iron"],
        ]
        tags = assign_higher_layer_tags(
            layer=4, origin_event_tags=origin_tags,
            significance="moderate",
            layer_specific_tags=["threat_level:moderate"],
        )
        self.assertIn("province:region_1", tags)
        self.assertIn("significance:moderate", tags)
        self.assertIn("threat_level:moderate", tags)


# ══════════════════════════════════════════════════════════════════
# 10. PromptAssembler L4
# ══════════════════════════════════════════════════════════════════

class TestPromptAssemblerL4(unittest.TestCase):

    def setUp(self):
        self.assembler = PromptAssembler()
        self.assembler.load()

    def test_l4_assembly_has_core(self):
        prompt = self.assembler.assemble_l4("<province>test</province>")
        self.assertIn("province-level summaries", prompt.system)

    def test_l4_output_mentions_tag_rewrite(self):
        prompt = self.assembler.assemble_l4("")
        self.assertIn("rewriting", prompt.user.lower())

    def test_l4_aggregates_lower_fragments(self):
        prompt = self.assembler.assemble_l4(
            "test data", event_tags=["domain:combat", "tier:1"])
        self.assertIsNotNone(prompt.system)
        self.assertGreater(prompt.token_estimate, 0)


# ══════════════════════════════════════════════════════════════════
# 11. Full Integration: L3 → Weighted Trigger → L4
# ══════════════════════════════════════════════════════════════════

class TestLayer4Integration(unittest.TestCase):

    def setUp(self):
        Layer4Manager.reset()
        TriggerRegistry.reset()
        self.geo = _setup_geo_registry()
        self.layer_store = LayerStore(db_path=":memory:")
        self.manager = Layer4Manager.get_instance()
        self.manager.initialize(
            layer_store=self.layer_store,
            geo_registry=self.geo,
            trigger_registry=TriggerRegistry.get_instance(),
        )

    def tearDown(self):
        Layer4Manager.reset()
        TriggerRegistry.reset()
        GeographicRegistry.reset()

    def test_full_pipeline(self):
        """Simulate L3 events accumulating, triggering L4 summary."""
        event_ids = []
        for i in range(6):
            eid = str(uuid.uuid4())
            tags = ["province:region_1", f"district:province_{i%2}",
                    "domain:combat", "intensity:heavy",
                    f"species:wolf_{i}"]
            self.layer_store.insert_event(
                layer=3, narrative=f"Combat event {i}",
                game_time=100 + i * 10, category="regional_synthesis",
                severity="moderate", significance="moderate",
                tags=tags, origin_ref="[]", event_id=eid,
            )
            self.manager.on_layer3_created({"id": eid, "tags": tags,
                                            "game_time": 100 + i * 10})
            event_ids.append(eid)

        # domain:combat at position 0 (geo stripped) = 10*6 = 60 > 50
        self.assertTrue(self.manager.should_run())
        created = self.manager.run_summarization(game_time=300.0)
        self.assertEqual(created, 1)

        l4_events = self.layer_store.query_by_tags(
            layer=4, tags=["province:region_1"], match_all=True)
        self.assertEqual(len(l4_events), 1)
        l4 = l4_events[0]
        self.assertEqual(l4["category"], "province_summary")
        self.assertIn("Iron Reaches", l4["narrative"])

    def test_supersession(self):
        """Second summarization supersedes first."""
        for round_num in range(2):
            for i in range(6):
                eid = str(uuid.uuid4())
                tags = ["province:region_1", "district:province_0",
                        "domain:combat"]
                self.layer_store.insert_event(
                    layer=3, narrative=f"Round {round_num} event {i}",
                    game_time=100 + round_num*100 + i,
                    category="regional_synthesis",
                    severity="moderate", significance="moderate",
                    tags=tags, origin_ref="[]", event_id=eid)
                self.manager.on_layer3_created(
                    {"id": eid, "tags": tags})

            self.manager.run_summarization(game_time=200 + round_num*100)

        # Should have 2 L4 events total
        all_l4 = self.layer_store.query_by_tags(
            layer=4, tags=["province:region_1"], match_all=True)
        self.assertEqual(len(all_l4), 2)


if __name__ == "__main__":
    unittest.main()

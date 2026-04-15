"""Tests for Layer 5 region summarization system.

Layer 5 aggregates at the **game Region** tier. Each RegionSummaryEvent
consolidates Layer 4 province summaries across every province within
one game Region. Address tags (world/nation/region) are FACTS assigned
at L2 capture and propagated unchanged; the LLM never synthesizes
address tags. See docs/ARCHITECTURAL_DECISIONS.md.

Tests cover:
1. RegionSummaryEvent dataclass
2. Layer5Summarizer — is_applicable, summarize, XML data block,
   filter_relevant_l3 (fired-tag overlap)
3. Layer5Manager — on_layer4_created, region resolution via the
   `region:` address tag (no parent-chain walking), should_run,
   run_summarization, multi-region isolation, supersession, stats
4. PromptAssembler L5 — assemble_l5, fragments, L5→L4→L3→L2 cascade
5. Full integration: L4 events → weighted region trigger → L5 storage
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
    RegionSummaryEvent, SEVERITY_ORDER,
)
from world_system.world_memory.trigger_registry import TriggerRegistry
from world_system.world_memory.layer_store import LayerStore
from world_system.world_memory.geographic_registry import (
    GeographicRegistry, Region, RegionLevel,
)
from world_system.world_memory.layer5_summarizer import Layer5Summarizer
from world_system.world_memory.layer5_manager import (
    Layer5Manager, BUCKET_PREFIX,
)
from world_system.world_memory.tag_assignment import assign_higher_layer_tags
from world_system.world_memory.prompt_assembler import PromptAssembler


# ── Helpers ────────────────────────────────────────────────────────

def _make_l4_event(category="province_summary", severity="moderate",
                   narrative="", province_id="province_1",
                   region_id="region_1", nation_id="nation_1",
                   world_id="world_0",
                   game_time=100.0, extra_tags=None, event_id=None):
    """Build a Layer 4 event dict with full 6-tier address tags.

    Address tags are emitted coarsest → finest: world, nation,
    region, province. These are FACTS — assigned at L2 capture time
    from chunk position and propagated unchanged to every layer.
    """
    tags = [
        f"world:{world_id}",
        f"nation:{nation_id}",
        f"region:{region_id}",
        f"province:{province_id}",
        "scope:province",
    ]
    if extra_tags:
        tags.extend(extra_tags)
    return {
        "id": event_id or str(uuid.uuid4()),
        "narrative": narrative or f"Province {province_id} {category}.",
        "category": category,
        "severity": severity,
        "tags": tags,
        "game_time": game_time,
    }


def _setup_geo_registry_multi_region():
    """Setup a two-region geographic hierarchy.

        world_0 (The Known Lands)
          nation_1 (Northern Kingdom)
            region_1 (Iron Reaches)                 ← L5 target A
              province_1 (Iron Hill Province)
              province_2 (Miners Province)
            region_2 (Emerald Valley)               ← L5 target B (isolation)
              province_3 (Emerald Province)
              province_4 (Western Province)

    Both regions share the same nation/world so the isolation test
    proves the per-region bucketing works within a single nation.
    """
    GeographicRegistry.reset()
    geo = GeographicRegistry.get_instance()

    world = Region(region_id="world_0", name="The Known Lands",
                   level=RegionLevel.WORLD,
                   bounds_x1=-500, bounds_y1=-500,
                   bounds_x2=500, bounds_y2=500)
    geo.regions["world_0"] = world
    geo.world = world

    nation = Region(region_id="nation_1", name="Northern Kingdom",
                    level=RegionLevel.NATION,
                    bounds_x1=-500, bounds_y1=-500,
                    bounds_x2=500, bounds_y2=500,
                    parent_id="world_0")
    geo.regions["nation_1"] = nation
    world.child_ids.append("nation_1")

    region_specs = [
        ("region_1", "Iron Reaches"),
        ("region_2", "Emerald Valley"),
    ]
    for rid, rname in region_specs:
        region = Region(region_id=rid, name=rname,
                        level=RegionLevel.REGION,
                        bounds_x1=-500, bounds_y1=-500,
                        bounds_x2=500, bounds_y2=500,
                        parent_id="nation_1")
        geo.regions[rid] = region
        nation.child_ids.append(rid)

    province_specs = [
        ("province_1", "Iron Hill Province", "region_1"),
        ("province_2", "Miners Province", "region_1"),
        ("province_3", "Emerald Province", "region_2"),
        ("province_4", "Western Province", "region_2"),
    ]
    for pid, pname, parent in province_specs:
        province = Region(region_id=pid, name=pname,
                          level=RegionLevel.PROVINCE,
                          bounds_x1=0, bounds_y1=0,
                          bounds_x2=100, bounds_y2=100,
                          parent_id=parent)
        geo.regions[pid] = province
        geo.regions[parent].child_ids.append(pid)

    return geo


# ══════════════════════════════════════════════════════════════════
# 1. RegionSummaryEvent Dataclass
# ══════════════════════════════════════════════════════════════════

class TestRegionSummaryEvent(unittest.TestCase):

    def test_create_factory_sets_id_and_time(self):
        evt = RegionSummaryEvent.create(
            region_id="region_1",
            narrative="Iron Reaches mining boom with combat in the north.",
            severity="major",
            source_province_summary_ids=["p1", "p2", "p3"],
            game_time=1000.0,
        )
        self.assertTrue(evt.summary_id)
        self.assertEqual(evt.region_id, "region_1")
        self.assertEqual(evt.severity, "major")
        self.assertEqual(len(evt.source_province_summary_ids), 3)
        self.assertEqual(evt.created_at, 1000.0)
        self.assertEqual(evt.region_condition, "stable")
        self.assertEqual(evt.dominant_activities, [])

    def test_create_accepts_extra_kwargs(self):
        evt = RegionSummaryEvent.create(
            region_id="region_1",
            narrative="Test.",
            severity="moderate",
            source_province_summary_ids=["p1"],
            game_time=500.0,
            dominant_activities=["mining", "combat"],
            dominant_provinces=["province_1"],
            region_condition="volatile",
            relevant_l3_ids=["l3_a", "l3_b"],
            tags=["region:region_1", "scope:region", "domain:combat"],
        )
        self.assertEqual(evt.dominant_activities, ["mining", "combat"])
        self.assertEqual(evt.region_condition, "volatile")
        self.assertIn("scope:region", evt.tags)
        self.assertEqual(len(evt.relevant_l3_ids), 2)

    def test_supersedes_id_defaults_none(self):
        evt = RegionSummaryEvent.create(
            region_id="region_1",
            narrative="x", severity="minor",
            source_province_summary_ids=[], game_time=0.0,
        )
        self.assertIsNone(evt.supersedes_id)


# ══════════════════════════════════════════════════════════════════
# 2. Layer5Summarizer — is_applicable + summarize
# ══════════════════════════════════════════════════════════════════

class TestLayer5Summarizer(unittest.TestCase):

    def setUp(self):
        self.summarizer = Layer5Summarizer()
        self.geo = _setup_geo_registry_multi_region()

    def tearDown(self):
        GeographicRegistry.reset()

    def test_is_applicable_needs_two_events(self):
        events = [_make_l4_event(province_id="province_1",
                                 region_id="region_1")]
        self.assertFalse(
            self.summarizer.is_applicable(events, "region_1"))

        events.append(_make_l4_event(province_id="province_2",
                                     region_id="region_1"))
        self.assertTrue(
            self.summarizer.is_applicable(events, "region_1"))

    def test_is_applicable_requires_region(self):
        events = [
            _make_l4_event(province_id="province_1", region_id="region_1"),
            _make_l4_event(province_id="province_2", region_id="region_1"),
        ]
        self.assertFalse(self.summarizer.is_applicable(events, ""))

    def test_summarize_produces_event_with_tags(self):
        events = [
            _make_l4_event(
                province_id="province_1", region_id="region_1",
                severity="moderate",
                narrative="Iron Hill Province mining boom.",
                extra_tags=["domain:gathering", "resource:iron",
                            "intensity:heavy"]),
            _make_l4_event(
                province_id="province_2", region_id="region_1",
                severity="moderate",
                narrative="Miners Province gathering.",
                extra_tags=["domain:gathering", "resource:wood"]),
        ]
        geo_ctx = {
            "region_name": "Iron Reaches",
            "provinces": [
                {"id": "province_1", "name": "Iron Hill Province"},
                {"id": "province_2", "name": "Miners Province"},
            ],
        }
        result = self.summarizer.summarize(
            l4_events=events, l3_events=[], region_id="region_1",
            geo_context=geo_ctx, game_time=2000.0,
        )
        self.assertIsNotNone(result)
        self.assertEqual(result.region_id, "region_1")
        self.assertIn("Iron Reaches", result.narrative)
        self.assertIn("gathering", result.dominant_activities)
        # Address tags propagated as facts from inputs
        self.assertIn("region:region_1", result.tags)
        self.assertIn("nation:nation_1", result.tags)
        self.assertIn("world:world_0", result.tags)
        self.assertIn("scope:region", result.tags)

    def test_summarize_returns_none_when_not_applicable(self):
        result = self.summarizer.summarize(
            l4_events=[_make_l4_event(province_id="province_1",
                                      region_id="region_1")],
            l3_events=[], region_id="region_1",
            geo_context={"region_name": "Iron Reaches", "provinces": []},
            game_time=100.0,
        )
        self.assertIsNone(result)

    def test_severity_boost_from_multi_province(self):
        # 4 provinces → boost by 1 severity tier (moderate → significant)
        events = [
            _make_l4_event(province_id="province_1", region_id="region_1", severity="moderate"),
            _make_l4_event(province_id="province_2", region_id="region_1", severity="moderate"),
            _make_l4_event(province_id="province_3", region_id="region_1", severity="moderate"),
            _make_l4_event(province_id="province_4", region_id="region_1", severity="moderate"),
        ]
        geo_ctx = {"region_name": "Test", "provinces": []}
        result = self.summarizer.summarize(
            events, [], "region_1", geo_ctx, game_time=100.0)
        self.assertIsNotNone(result)
        self.assertEqual(
            SEVERITY_ORDER[result.severity],
            SEVERITY_ORDER["significant"],
        )

    def test_region_condition_crisis_on_critical(self):
        events = [
            _make_l4_event(province_id="province_1", region_id="region_1", severity="critical"),
            _make_l4_event(province_id="province_2", region_id="region_1", severity="minor"),
        ]
        geo_ctx = {"region_name": "Test", "provinces": []}
        result = self.summarizer.summarize(
            events, [], "region_1", geo_ctx, game_time=100.0)
        self.assertIsNotNone(result)
        self.assertEqual(result.region_condition, "crisis")

    def test_region_condition_volatile_on_two_majors(self):
        events = [
            _make_l4_event(province_id="province_1", region_id="region_1", severity="major"),
            _make_l4_event(province_id="province_2", region_id="region_1", severity="major"),
        ]
        geo_ctx = {"region_name": "Test", "provinces": []}
        result = self.summarizer.summarize(
            events, [], "region_1", geo_ctx, game_time=100.0)
        self.assertEqual(result.region_condition, "volatile")

    def test_dominant_provinces_by_count(self):
        events = [
            _make_l4_event(province_id="province_1", region_id="region_1"),
            _make_l4_event(province_id="province_1", region_id="region_1"),
            _make_l4_event(province_id="province_2", region_id="region_1"),
        ]
        geo_ctx = {"region_name": "Test", "provinces": []}
        result = self.summarizer.summarize(
            events, [], "region_1", geo_ctx, game_time=100.0)
        self.assertEqual(result.dominant_provinces[0], "province_1")


# ══════════════════════════════════════════════════════════════════
# 3. Layer5Summarizer — XML data block
# ══════════════════════════════════════════════════════════════════

class TestLayer5XmlBlock(unittest.TestCase):

    def setUp(self):
        self.summarizer = Layer5Summarizer()

    def test_xml_block_groups_by_province(self):
        events = [
            _make_l4_event(
                province_id="province_1", region_id="region_1",
                narrative="Iron mines busy.",
                extra_tags=["domain:gathering"], game_time=150.0),
            _make_l4_event(
                province_id="province_2", region_id="region_1",
                narrative="Forest expansion.",
                extra_tags=["domain:gathering"], game_time=160.0),
        ]
        xml = self.summarizer.build_xml_data_block(
            l4_events=events, l3_events=[], region_name="Iron Reaches",
            provinces=[
                {"id": "province_1", "name": "Iron Hill Province"},
                {"id": "province_2", "name": "Miners Province"},
            ],
            game_time=500.0,
        )
        self.assertIn('<region name="Iron Reaches">', xml)
        self.assertIn('<province name="Iron Hill Province">', xml)
        self.assertIn('<province name="Miners Province">', xml)
        self.assertIn("Iron mines busy.", xml)
        self.assertIn('tags="[', xml)
        self.assertIn("province:province_1", xml)
        self.assertIn("region:region_1", xml)

    def test_xml_block_includes_supporting_l3_detail(self):
        events = [
            _make_l4_event(province_id="province_1", region_id="region_1",
                           extra_tags=["domain:combat"]),
            _make_l4_event(province_id="province_1", region_id="region_1",
                           extra_tags=["domain:combat"]),
        ]
        l3_events = [
            {
                "id": "l3_a",
                "narrative": "Wolf pack sightings.",
                "category": "district_synthesis",
                "severity": "minor",
                "game_time": 140.0,
                "tags": ["domain:combat", "species:wolf"],
            },
        ]
        xml = self.summarizer.build_xml_data_block(
            l4_events=events, l3_events=l3_events,
            region_name="Iron Reaches",
            provinces=[{"id": "province_1", "name": "Iron Hill Province"}],
            game_time=300.0,
        )
        self.assertIn("<supporting-detail>", xml)
        self.assertIn("Wolf pack sightings.", xml)

    def test_xml_block_cross_province_bucket(self):
        """Events without province tags go into cross-province bucket."""
        events = [
            {
                "id": "g1",
                "narrative": "Region-wide festival.",
                "category": "province_summary",
                "severity": "moderate",
                "game_time": 200.0,
                "tags": ["world:world_0", "nation:nation_1",
                         "region:region_1", "scope:region",
                         "domain:social"],
            },
            _make_l4_event(province_id="province_1", region_id="region_1"),
        ]
        xml = self.summarizer.build_xml_data_block(
            l4_events=events, l3_events=[], region_name="Iron Reaches",
            provinces=[{"id": "province_1", "name": "Iron Hill Province"}],
            game_time=500.0,
        )
        self.assertIn("<cross-province>", xml)
        self.assertIn("Region-wide festival.", xml)


# ══════════════════════════════════════════════════════════════════
# 4. Layer5Summarizer — filter_relevant_l3
# ══════════════════════════════════════════════════════════════════

class TestFilterRelevantL3(unittest.TestCase):

    def test_filter_by_fired_tag_overlap(self):
        l3_candidates = [
            {
                "id": "hit_a",
                "game_time": 100.0,
                "tags": ["domain:combat", "species:wolf", "tier:2"],
            },
            {
                "id": "hit_b",
                "game_time": 200.0,
                "tags": ["species:wolf", "terrain:forest"],
            },
            {
                "id": "miss",
                "game_time": 150.0,
                "tags": ["domain:crafting", "discipline:smithing"],
            },
        ]
        fired = {"domain:combat", "species:wolf"}
        result = Layer5Summarizer.filter_relevant_l3(
            l3_candidates=l3_candidates, fired_tags=fired)
        ids = [e["id"] for e in result]
        self.assertIn("hit_a", ids)
        self.assertIn("hit_b", ids)
        self.assertNotIn("miss", ids)
        self.assertEqual(ids[0], "hit_a")

    def test_filter_strips_structural_fired_tags(self):
        """Structural / address fired tags must not match L3 events."""
        l3_candidates = [
            {
                "id": "e1",
                "game_time": 100.0,
                "tags": ["province:province_1", "scope:province"],
            },
        ]
        fired = {"province:province_1", "scope:region",
                 "significance:major", "world:world_0"}
        result = Layer5Summarizer.filter_relevant_l3(
            l3_candidates=l3_candidates, fired_tags=fired)
        self.assertEqual(result, [])

    def test_filter_fallback_to_l4_content_when_no_fired(self):
        l3_candidates = [
            {
                "id": "match",
                "game_time": 100.0,
                "tags": ["domain:combat", "tier:2"],
            },
        ]
        l4_events = [
            {"tags": ["province:province_1", "region:region_1",
                      "domain:combat"]},
        ]
        result = Layer5Summarizer.filter_relevant_l3(
            l3_candidates=l3_candidates, fired_tags=set(),
            l4_events=l4_events,
        )
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["id"], "match")

    def test_filter_returns_empty_when_no_signal(self):
        result = Layer5Summarizer.filter_relevant_l3(
            l3_candidates=[{"id": "a", "tags": ["x:y"], "game_time": 0}],
            fired_tags=set(),
        )
        self.assertEqual(result, [])

    def test_filter_respects_max_results_cap(self):
        l3_candidates = [
            {
                "id": f"e{i}",
                "game_time": 100.0 + i,
                "tags": ["domain:combat"],
            }
            for i in range(20)
        ]
        result = Layer5Summarizer.filter_relevant_l3(
            l3_candidates=l3_candidates,
            fired_tags={"domain:combat"},
        )
        self.assertLessEqual(len(result), 8)


# ══════════════════════════════════════════════════════════════════
# 5. Layer5Manager — on_layer4_created trigger ingestion
# ══════════════════════════════════════════════════════════════════

class TestLayer5Manager(unittest.TestCase):

    def setUp(self):
        Layer5Manager.reset()
        TriggerRegistry.reset()
        self.geo = _setup_geo_registry_multi_region()
        self.layer_store = LayerStore(db_path=":memory:")
        self.manager = Layer5Manager.get_instance()
        self.manager.initialize(
            layer_store=self.layer_store,
            geo_registry=self.geo,
            wms_ai=None,
            trigger_registry=TriggerRegistry.get_instance(),
        )

    def tearDown(self):
        Layer5Manager.reset()
        TriggerRegistry.reset()
        GeographicRegistry.reset()

    def test_on_layer4_created_strips_address_tags(self):
        evt = _make_l4_event(
            province_id="province_1", region_id="region_1",
            extra_tags=["domain:combat", "intensity:heavy"],
        )
        self.manager.on_layer4_created(evt)

        bucket = TriggerRegistry.get_instance().get_weighted_bucket(
            f"{BUCKET_PREFIX}region_1")
        self.assertIsNotNone(bucket)
        # Every address tag gets stripped before scoring
        self.assertEqual(bucket.get_score("world:world_0"), 0)
        self.assertEqual(bucket.get_score("nation:nation_1"), 0)
        self.assertEqual(bucket.get_score("region:region_1"), 0)
        self.assertEqual(bucket.get_score("province:province_1"), 0)
        # Content tags after strip: ["scope:province", "domain:combat",
        # "intensity:heavy"]. scope: is structural (skipped) but still
        # occupies position 0, so domain:combat lands at pos 1 = 8 pts
        # and intensity:heavy at pos 2 = 6 pts.
        self.assertEqual(bucket.get_score("scope:province"), 0)
        self.assertEqual(bucket.get_score("domain:combat"), 8)
        self.assertEqual(bucket.get_score("intensity:heavy"), 6)

    def test_region_resolution_from_region_tag(self):
        """The `region:` tag is always present — simple lookup."""
        evt = _make_l4_event(
            province_id="province_1", region_id="region_1",
            extra_tags=["domain:combat"],
        )
        self.manager.on_layer4_created(evt)
        names = TriggerRegistry.get_instance().get_weighted_bucket_names(
            BUCKET_PREFIX)
        self.assertIn(f"{BUCKET_PREFIX}region_1", names)

    def test_unresolvable_tags_drop_silently(self):
        """Events without a region: tag are dropped silently."""
        evt = {
            "id": str(uuid.uuid4()),
            "narrative": "No address info.",
            "category": "province_summary",
            "severity": "moderate",
            "game_time": 100.0,
            "tags": ["domain:combat", "intensity:heavy"],
        }
        self.manager.on_layer4_created(evt)
        names = TriggerRegistry.get_instance().get_weighted_bucket_names(
            BUCKET_PREFIX)
        self.assertEqual(names, [])

    def test_should_run_after_threshold_crossed(self):
        self.assertFalse(self.manager.should_run())

        # scope:province occupies position 0 (skipped), so
        # domain:combat lands at pos 1 = 8 pts per event.
        # Threshold is 100 → need 13 events (13 * 8 = 104).
        for i in range(13):
            evt = _make_l4_event(
                province_id="province_1", region_id="region_1",
                game_time=100 + i, extra_tags=["domain:combat"],
            )
            self.manager.on_layer4_created(evt)
        self.assertTrue(self.manager.should_run())

    def test_multi_region_isolation(self):
        """Events in region_1 should not trigger region_2 and vice versa."""
        # Fire region_1: 13 events * 8 pts = 104 > 100
        for i in range(13):
            self.manager.on_layer4_created(_make_l4_event(
                province_id="province_1", region_id="region_1",
                game_time=100 + i, extra_tags=["domain:combat"],
            ))
        # A few events into region_2 (not enough to fire)
        for i in range(3):
            self.manager.on_layer4_created(_make_l4_event(
                province_id="province_3", region_id="region_2",
                game_time=200 + i, extra_tags=["domain:combat"],
            ))

        reg = TriggerRegistry.get_instance()
        b1 = reg.get_weighted_bucket(f"{BUCKET_PREFIX}region_1")
        b2 = reg.get_weighted_bucket(f"{BUCKET_PREFIX}region_2")
        self.assertTrue(b1.has_fired())
        self.assertFalse(b2.has_fired())

    def test_run_summarization_stores_l5_event(self):
        for i in range(13):
            eid = str(uuid.uuid4())
            pid = f"province_{(i % 2) + 1}"
            tags = ["world:world_0", "nation:nation_1",
                    "region:region_1", f"province:{pid}",
                    "scope:province",
                    "domain:combat", "intensity:heavy"]
            self.layer_store.insert_event(
                layer=4, narrative=f"Province summary {i}",
                game_time=100 + i, category="province_summary",
                severity="moderate", significance="moderate",
                tags=tags, origin_ref="[]", event_id=eid,
            )
            self.manager.on_layer4_created({
                "id": eid, "tags": tags, "game_time": 100 + i,
            })

        self.assertTrue(self.manager.should_run())
        created = self.manager.run_summarization(game_time=500.0)
        self.assertGreaterEqual(created, 1)

        rows = self.layer_store.query_by_tags(
            layer=5, tags=["region:region_1"], match_all=True)
        self.assertGreaterEqual(len(rows), 1)
        self.assertEqual(rows[0]["category"], "region_summary")

    def test_supersession_on_second_run(self):
        """Second summarization should set supersedes_id on new event."""
        for round_num in range(2):
            for i in range(13):
                eid = str(uuid.uuid4())
                pid = f"province_{(i % 2) + 1}"
                tags = ["world:world_0", "nation:nation_1",
                        "region:region_1", f"province:{pid}",
                        "scope:province", "domain:combat"]
                game_time = 100 + round_num * 1000 + i
                self.layer_store.insert_event(
                    layer=4, narrative=f"Round {round_num} evt {i}",
                    game_time=game_time, category="province_summary",
                    severity="moderate", significance="moderate",
                    tags=tags, origin_ref="[]", event_id=eid,
                )
                self.manager.on_layer4_created({
                    "id": eid, "tags": tags, "game_time": game_time,
                })
            self.manager.run_summarization(
                game_time=500 + round_num * 1000)

        all_l5 = self.layer_store.query_by_tags(
            layer=5, tags=["region:region_1"], match_all=True)
        self.assertEqual(len(all_l5), 2)

    def test_stats_structure(self):
        stats = self.manager.stats
        self.assertTrue(stats["initialized"])
        self.assertIn("summaries_created", stats)
        self.assertIn("runs_completed", stats)
        self.assertIn("trigger", stats)

    def test_stats_reflects_region_buckets(self):
        evt = _make_l4_event(
            province_id="province_1", region_id="region_1",
            extra_tags=["domain:combat"])
        self.manager.on_layer4_created(evt)
        stats = self.manager.stats
        trigger = stats["trigger"]
        self.assertEqual(trigger["regions_tracked"], 1)
        self.assertEqual(trigger["threshold"], 100)
        self.assertIn("region_1", trigger["per_region"])


# ══════════════════════════════════════════════════════════════════
# 6. PromptAssembler L5
# ══════════════════════════════════════════════════════════════════

class TestPromptAssemblerL5(unittest.TestCase):

    def setUp(self):
        self.assembler = PromptAssembler()
        self.assembler.load()

    def test_l5_fragments_loaded(self):
        core = self.assembler.get_l5_fragment("_l5_core")
        self.assertTrue(core)
        self.assertIn("region", core.lower())

    def test_l5_output_fragment_exists(self):
        output = self.assembler.get_l5_fragment("_l5_output")
        self.assertTrue(output)

    def test_l5_context_fragment_exists(self):
        ctx = self.assembler.get_l5_fragment("l5_context:region_summary")
        self.assertTrue(ctx)

    def test_assemble_l5_has_core_system(self):
        prompt = self.assembler.assemble_l5("<region>test</region>")
        self.assertIn("region", prompt.system.lower())
        self.assertIn("<region>test</region>", prompt.user)
        self.assertGreater(prompt.token_estimate, 0)

    def test_assemble_l5_tags_layer_and_scope(self):
        prompt = self.assembler.assemble_l5("")
        self.assertIn("layer:5", prompt.tags)
        self.assertIn("scope:region", prompt.tags)

    def test_assemble_l5_cascade_from_lower_layers(self):
        """L5 prompt pulls tag fragments from L4/L3/L2 too."""
        prompt = self.assembler.assemble_l5(
            data_block="<region name='Iron Reaches'>data</region>",
            event_tags=["domain:combat", "species:wolf",
                        "tier:2", "intensity:heavy"],
        )
        self.assertIsNotNone(prompt.system)
        self.assertGreater(prompt.token_estimate, 0)
        frag_keys = [k for k, _ in prompt.fragments_used]
        self.assertIn("_l5_core", frag_keys)

    def test_assemble_l5_user_includes_output_instruction(self):
        prompt = self.assembler.assemble_l5("<region>x</region>")
        self.assertIn("<region>x</region>", prompt.user)


# ══════════════════════════════════════════════════════════════════
# 7. Full Integration: L4 events → weighted region trigger → L5 storage
# ══════════════════════════════════════════════════════════════════

class TestLayer5Integration(unittest.TestCase):

    def setUp(self):
        Layer5Manager.reset()
        TriggerRegistry.reset()
        self.geo = _setup_geo_registry_multi_region()
        self.layer_store = LayerStore(db_path=":memory:")
        self.manager = Layer5Manager.get_instance()
        self.manager.initialize(
            layer_store=self.layer_store,
            geo_registry=self.geo,
            wms_ai=None,
            trigger_registry=TriggerRegistry.get_instance(),
        )

    def tearDown(self):
        Layer5Manager.reset()
        TriggerRegistry.reset()
        GeographicRegistry.reset()

    def test_full_pipeline_l4_to_l5(self):
        """L4 events accumulating, triggering an L5 region summary."""
        # Seed some L3 events in the layer store so the fired-tag filter
        # has candidates to pull during summarization
        for i in range(3):
            self.layer_store.insert_event(
                layer=3,
                narrative=f"District-level combat report {i}",
                game_time=80 + i,
                category="district_synthesis",
                severity="moderate",
                significance="moderate",
                tags=["world:world_0", "nation:nation_1",
                      "region:region_1", "province:province_1",
                      "district:district_a",
                      "domain:combat", "species:wolf",
                      "intensity:heavy"],
                origin_ref="[]",
                event_id=f"l3_{i}",
            )

        # Seed L4 events across two provinces in region_1 until threshold.
        # domain:combat at pos 1 = 8 pts, need 13 events (13*8 = 104).
        for i in range(13):
            eid = str(uuid.uuid4())
            pid = f"province_{(i % 2) + 1}"
            tags = ["world:world_0", "nation:nation_1",
                    "region:region_1", f"province:{pid}",
                    "scope:province",
                    "domain:combat", "intensity:heavy",
                    "species:wolf", "tier:2"]
            self.layer_store.insert_event(
                layer=4, narrative=f"Province summary {i}",
                game_time=100 + i * 10,
                category="province_summary",
                severity="moderate", significance="moderate",
                tags=tags, origin_ref="[]", event_id=eid,
            )
            self.manager.on_layer4_created({
                "id": eid, "tags": tags, "game_time": 100 + i * 10,
            })

        self.assertTrue(self.manager.should_run())
        created = self.manager.run_summarization(game_time=1000.0)
        self.assertEqual(created, 1)

        l5_events = self.layer_store.query_by_tags(
            layer=5, tags=["region:region_1"], match_all=True)
        self.assertEqual(len(l5_events), 1)
        l5 = l5_events[0]
        self.assertEqual(l5["category"], "region_summary")
        self.assertIn("Iron Reaches", l5["narrative"])

        stats = self.manager.stats
        self.assertEqual(stats["summaries_created"], 1)
        self.assertEqual(stats["runs_completed"], 1)

    def test_no_run_when_insufficient_events(self):
        for i in range(3):
            eid = str(uuid.uuid4())
            tags = ["world:world_0", "nation:nation_1",
                    "region:region_1", "province:province_1",
                    "domain:combat"]
            self.layer_store.insert_event(
                layer=4, narrative=f"Province summary {i}",
                game_time=100 + i, category="province_summary",
                severity="moderate", significance="moderate",
                tags=tags, origin_ref="[]", event_id=eid,
            )
            self.manager.on_layer4_created({
                "id": eid, "tags": tags, "game_time": 100 + i,
            })

        self.assertFalse(self.manager.should_run())
        created = self.manager.run_summarization(game_time=200.0)
        self.assertEqual(created, 0)

        l5_events = self.layer_store.query_by_tags(
            layer=5, tags=["region:region_1"], match_all=True)
        self.assertEqual(l5_events, [])


if __name__ == "__main__":
    unittest.main()

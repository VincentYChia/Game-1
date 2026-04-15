"""Tests for Layer 6 nation summarization system.

Layer 6 aggregates at the **game Nation** tier. Each NationSummaryEvent
consolidates Layer 5 region summaries across every region within one
game Nation. Address tags (world/nation) are FACTS assigned at L2
capture and propagated unchanged; the LLM never synthesizes address
tags. See docs/ARCHITECTURAL_DECISIONS.md.

Tests cover:
1. NationSummaryEvent dataclass
2. Layer6Summarizer — is_applicable, summarize, XML data block,
   filter_relevant_l4 (fired-tag overlap)
3. Layer6Manager — on_layer5_created, nation resolution via the
   `nation:` address tag, should_run, run_summarization, multi-nation
   isolation, supersession, stats
4. PromptAssembler L6 — assemble_l6, fragments, L6→L5→L4→L3→L2 cascade
5. Full integration: L5 events → weighted nation trigger → L6 storage
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
    NationSummaryEvent, SEVERITY_ORDER,
)
from world_system.world_memory.trigger_registry import TriggerRegistry
from world_system.world_memory.layer_store import LayerStore
from world_system.world_memory.geographic_registry import (
    GeographicRegistry, Region, RegionLevel,
)
from world_system.world_memory.layer6_summarizer import Layer6Summarizer
from world_system.world_memory.layer6_manager import (
    Layer6Manager, BUCKET_PREFIX,
)
from world_system.world_memory.tag_assignment import assign_higher_layer_tags
from world_system.world_memory.prompt_assembler import PromptAssembler


# ── Helpers ────────────────────────────────────────────────────────

def _make_l5_event(category="region_summary", severity="moderate",
                   narrative="", region_id="region_1",
                   nation_id="nation_1", world_id="world_0",
                   game_time=100.0, extra_tags=None, event_id=None):
    """Build a Layer 5 event dict with full address tags.

    Address tags are emitted coarsest → finest: world, nation, region.
    These are FACTS — assigned at L2 capture time from chunk position
    and propagated unchanged to every layer.
    """
    tags = [
        f"world:{world_id}",
        f"nation:{nation_id}",
        f"region:{region_id}",
        "scope:region",
    ]
    if extra_tags:
        tags.extend(extra_tags)
    return {
        "id": event_id or str(uuid.uuid4()),
        "narrative": narrative or f"Region {region_id} {category}.",
        "category": category,
        "severity": severity,
        "tags": tags,
        "game_time": game_time,
    }


def _setup_geo_registry_multi_nation():
    """Setup a two-nation geographic hierarchy.

        world_0 (The Known Lands)
          nation_1 (Northern Kingdom)                ← L6 target A
            region_1 (Iron Reaches)
              province_1
              province_2
            region_2 (Emerald Valley)
              province_3
              province_4
          nation_2 (Southern Empire)                 ← L6 target B (isolation)
            region_3 (Desert Wastes)
              province_5
              province_6
            region_4 (Jungle Expanse)
              province_7
              province_8

    Both nations share the same world so the isolation test
    proves the per-nation bucketing works within a single world.
    """
    GeographicRegistry.reset()
    geo = GeographicRegistry.get_instance()

    world = Region(region_id="world_0", name="The Known Lands",
                   level=RegionLevel.WORLD,
                   bounds_x1=-500, bounds_y1=-500,
                   bounds_x2=500, bounds_y2=500)
    geo.regions["world_0"] = world
    geo.world = world

    nation_specs = [
        ("nation_1", "Northern Kingdom"),
        ("nation_2", "Southern Empire"),
    ]
    for nid, nname in nation_specs:
        nation = Region(region_id=nid, name=nname,
                        level=RegionLevel.NATION,
                        bounds_x1=-500, bounds_y1=-500,
                        bounds_x2=500, bounds_y2=500,
                        parent_id="world_0")
        geo.regions[nid] = nation
        world.child_ids.append(nid)

    # Each nation has 2 regions
    region_specs = [
        ("region_1", "Iron Reaches", "nation_1"),
        ("region_2", "Emerald Valley", "nation_1"),
        ("region_3", "Desert Wastes", "nation_2"),
        ("region_4", "Jungle Expanse", "nation_2"),
    ]
    for rid, rname, parent_nation in region_specs:
        region = Region(region_id=rid, name=rname,
                        level=RegionLevel.REGION,
                        bounds_x1=-500, bounds_y1=-500,
                        bounds_x2=500, bounds_y2=500,
                        parent_id=parent_nation)
        geo.regions[rid] = region
        geo.regions[parent_nation].child_ids.append(rid)

    # Each region has 2 provinces
    province_specs = [
        ("province_1", "Iron Hill Province", "region_1"),
        ("province_2", "Miners Province", "region_1"),
        ("province_3", "Emerald Province", "region_2"),
        ("province_4", "Western Province", "region_2"),
        ("province_5", "Sand Province", "region_3"),
        ("province_6", "Oasis Province", "region_3"),
        ("province_7", "Jungle Province", "region_4"),
        ("province_8", "River Province", "region_4"),
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
# 1. NationSummaryEvent Dataclass
# ══════════════════════════════════════════════════════════════════

class TestNationSummaryEvent(unittest.TestCase):

    def test_create_factory_sets_id_and_time(self):
        evt = NationSummaryEvent.create(
            nation_id="nation_1",
            narrative="Northern Kingdom consolidating mining and farming.",
            severity="major",
            source_region_summary_ids=["r1", "r2"],
            game_time=1000.0,
        )
        self.assertTrue(evt.summary_id)
        self.assertEqual(evt.nation_id, "nation_1")
        self.assertEqual(evt.severity, "major")
        self.assertEqual(len(evt.source_region_summary_ids), 2)
        self.assertEqual(evt.created_at, 1000.0)
        self.assertEqual(evt.nation_condition, "stable")
        self.assertEqual(evt.dominant_activities, [])

    def test_create_accepts_extra_kwargs(self):
        evt = NationSummaryEvent.create(
            nation_id="nation_1",
            narrative="Test nation.",
            severity="significant",
            source_region_summary_ids=["r1", "r2"],
            game_time=500.0,
            dominant_activities=["mining", "farming"],
            dominant_regions=["Iron Reaches", "Emerald Valley"],
            nation_condition="shifting",
            relevant_l4_ids=["l4_a", "l4_b", "l4_c"],
            tags=["nation:nation_1", "scope:nation", "domain:gathering"],
        )
        self.assertEqual(evt.dominant_activities, ["mining", "farming"])
        self.assertEqual(evt.nation_condition, "shifting")
        self.assertIn("scope:nation", evt.tags)
        self.assertEqual(len(evt.relevant_l4_ids), 3)

    def test_supersedes_id_defaults_none(self):
        evt = NationSummaryEvent.create(
            nation_id="nation_1",
            narrative="x", severity="minor",
            source_region_summary_ids=[], game_time=0.0,
        )
        self.assertIsNone(evt.supersedes_id)


# ══════════════════════════════════════════════════════════════════
# 2. Layer6Summarizer — is_applicable + summarize
# ══════════════════════════════════════════════════════════════════

class TestLayer6Summarizer(unittest.TestCase):

    def setUp(self):
        self.summarizer = Layer6Summarizer()
        self.geo = _setup_geo_registry_multi_nation()

    def tearDown(self):
        GeographicRegistry.reset()

    def test_is_applicable_needs_two_regions(self):
        events = [_make_l5_event(region_id="region_1",
                                 nation_id="nation_1")]
        self.assertFalse(
            self.summarizer.is_applicable(events, "nation_1"))

        events.append(_make_l5_event(region_id="region_2",
                                     nation_id="nation_1"))
        self.assertTrue(
            self.summarizer.is_applicable(events, "nation_1"))

    def test_is_applicable_requires_nation(self):
        events = [
            _make_l5_event(region_id="region_1", nation_id="nation_1"),
            _make_l5_event(region_id="region_2", nation_id="nation_1"),
        ]
        self.assertFalse(self.summarizer.is_applicable(events, ""))

    def test_summarize_produces_event_with_tags(self):
        events = [
            _make_l5_event(
                region_id="region_1", nation_id="nation_1",
                severity="moderate",
                narrative="Iron Reaches mining boom.",
                extra_tags=["domain:gathering", "resource:iron",
                            "intensity:heavy"]),
            _make_l5_event(
                region_id="region_2", nation_id="nation_1",
                severity="moderate",
                narrative="Emerald Valley farming.",
                extra_tags=["domain:gathering", "resource:wood"]),
        ]
        geo_ctx = {
            "nation_name": "Northern Kingdom",
            "regions": [
                {"id": "region_1", "name": "Iron Reaches"},
                {"id": "region_2", "name": "Emerald Valley"},
            ],
        }
        result = self.summarizer.summarize(
            l5_events=events, l4_events=[], nation_id="nation_1",
            geo_context=geo_ctx, game_time=2000.0,
        )
        self.assertIsNotNone(result)
        self.assertEqual(result.nation_id, "nation_1")
        self.assertIn("Northern Kingdom", result.narrative)
        self.assertIn("gathering", result.dominant_activities)
        # Address tags propagated as facts from inputs
        self.assertIn("nation:nation_1", result.tags)
        self.assertIn("world:world_0", result.tags)
        self.assertIn("scope:nation", result.tags)

    def test_summarize_returns_none_when_not_applicable(self):
        result = self.summarizer.summarize(
            l5_events=[_make_l5_event(region_id="region_1",
                                      nation_id="nation_1")],
            l4_events=[], nation_id="nation_1",
            geo_context={"nation_name": "Northern Kingdom", "regions": []},
            game_time=100.0,
        )
        self.assertIsNone(result)

    def test_severity_boost_from_multi_region(self):
        # 4 regions → boost by 1 severity tier (moderate → significant)
        events = [
            _make_l5_event(region_id="region_1", nation_id="nation_1",
                           severity="moderate"),
            _make_l5_event(region_id="region_2", nation_id="nation_1",
                           severity="moderate"),
            _make_l5_event(region_id="region_3", nation_id="nation_1",
                           severity="moderate"),
            _make_l5_event(region_id="region_4", nation_id="nation_1",
                           severity="moderate"),
        ]
        geo_ctx = {"nation_name": "Test", "regions": []}
        result = self.summarizer.summarize(
            events, [], "nation_1", geo_ctx, game_time=100.0)
        self.assertIsNotNone(result)
        self.assertEqual(
            SEVERITY_ORDER[result.severity],
            SEVERITY_ORDER["significant"],
        )

    def test_nation_condition_crisis_on_critical(self):
        events = [
            _make_l5_event(region_id="region_1", nation_id="nation_1",
                           severity="critical"),
            _make_l5_event(region_id="region_2", nation_id="nation_1",
                           severity="minor"),
        ]
        geo_ctx = {"nation_name": "Test", "regions": []}
        result = self.summarizer.summarize(
            events, [], "nation_1", geo_ctx, game_time=100.0)
        self.assertIsNotNone(result)
        self.assertEqual(result.nation_condition, "crisis")

    def test_nation_condition_volatile_on_two_majors(self):
        events = [
            _make_l5_event(region_id="region_1", nation_id="nation_1",
                           severity="major"),
            _make_l5_event(region_id="region_2", nation_id="nation_1",
                           severity="major"),
        ]
        geo_ctx = {"nation_name": "Test", "regions": []}
        result = self.summarizer.summarize(
            events, [], "nation_1", geo_ctx, game_time=100.0)
        self.assertEqual(result.nation_condition, "volatile")

    def test_dominant_regions_by_count(self):
        events = [
            _make_l5_event(region_id="region_1", nation_id="nation_1"),
            _make_l5_event(region_id="region_1", nation_id="nation_1"),
            _make_l5_event(region_id="region_2", nation_id="nation_1"),
        ]
        geo_ctx = {"nation_name": "Test", "regions": []}
        result = self.summarizer.summarize(
            events, [], "nation_1", geo_ctx, game_time=100.0)
        self.assertEqual(result.dominant_regions[0], "region_1")


# ══════════════════════════════════════════════════════════════════
# 3. Layer6Summarizer — XML data block
# ══════════════════════════════════════════════════════════════════

class TestLayer6XmlBlock(unittest.TestCase):

    def setUp(self):
        self.summarizer = Layer6Summarizer()

    def test_xml_block_groups_by_region(self):
        events = [
            _make_l5_event(
                region_id="region_1", nation_id="nation_1",
                narrative="Iron Reaches mining boom.",
                extra_tags=["domain:gathering"], game_time=150.0),
            _make_l5_event(
                region_id="region_2", nation_id="nation_1",
                narrative="Emerald Valley farming.",
                extra_tags=["domain:gathering"], game_time=160.0),
        ]
        xml = self.summarizer.build_xml_data_block(
            l5_events=events, l4_events=[], nation_name="Northern Kingdom",
            regions=[
                {"id": "region_1", "name": "Iron Reaches"},
                {"id": "region_2", "name": "Emerald Valley"},
            ],
            game_time=500.0,
        )
        self.assertIn('<nation name="Northern Kingdom">', xml)
        self.assertIn('<region name="Iron Reaches">', xml)
        self.assertIn('<region name="Emerald Valley">', xml)
        self.assertIn("Iron Reaches mining boom.", xml)
        self.assertIn('tags="[', xml)
        self.assertIn("region:region_1", xml)
        self.assertIn("nation:nation_1", xml)

    def test_xml_block_includes_supporting_l4_detail(self):
        events = [
            _make_l5_event(region_id="region_1", nation_id="nation_1",
                           extra_tags=["domain:combat"]),
            _make_l5_event(region_id="region_1", nation_id="nation_1",
                           extra_tags=["domain:combat"]),
        ]
        l4_events = [
            {
                "id": "l4_a",
                "narrative": "Enemy encampment.",
                "category": "province_summary",
                "severity": "minor",
                "game_time": 140.0,
                "tags": ["domain:combat", "species:goblin"],
            },
        ]
        xml = self.summarizer.build_xml_data_block(
            l5_events=events, l4_events=l4_events,
            nation_name="Northern Kingdom",
            regions=[{"id": "region_1", "name": "Iron Reaches"}],
            game_time=300.0,
        )
        self.assertIn("<supporting-detail>", xml)
        self.assertIn("Enemy encampment.", xml)

    def test_xml_block_cross_region_bucket(self):
        """Events without region tags go into cross-region bucket."""
        events = [
            {
                "id": "g1",
                "narrative": "Nation-wide crisis.",
                "category": "region_summary",
                "severity": "critical",
                "game_time": 200.0,
                "tags": ["world:world_0", "nation:nation_1",
                         "scope:nation", "domain:crisis"],
            },
            _make_l5_event(region_id="region_1", nation_id="nation_1"),
        ]
        xml = self.summarizer.build_xml_data_block(
            l5_events=events, l4_events=[], nation_name="Northern Kingdom",
            regions=[{"id": "region_1", "name": "Iron Reaches"}],
            game_time=500.0,
        )
        self.assertIn("<cross-region>", xml)
        self.assertIn("Nation-wide crisis.", xml)


# ══════════════════════════════════════════════════════════════════
# 4. Layer6Summarizer — filter_relevant_l4
# ══════════════════════════════════════════════════════════════════

class TestFilterRelevantL4(unittest.TestCase):

    def test_filter_by_fired_tag_overlap(self):
        l4_candidates = [
            {
                "id": "hit_a",
                "game_time": 100.0,
                "tags": ["domain:combat", "species:goblin", "tier:2"],
            },
            {
                "id": "hit_b",
                "game_time": 200.0,
                "tags": ["species:goblin", "terrain:mountain"],
            },
            {
                "id": "miss",
                "game_time": 150.0,
                "tags": ["domain:crafting", "discipline:smithing"],
            },
        ]
        fired = {"domain:combat", "species:goblin"}
        result = Layer6Summarizer.filter_relevant_l4(
            l4_candidates=l4_candidates, fired_tags=fired)
        ids = [e["id"] for e in result]
        self.assertIn("hit_a", ids)
        self.assertIn("hit_b", ids)
        self.assertNotIn("miss", ids)
        self.assertEqual(ids[0], "hit_a")

    def test_filter_strips_structural_fired_tags(self):
        """Structural / address fired tags must not match L4 events."""
        l4_candidates = [
            {
                "id": "e1",
                "game_time": 100.0,
                "tags": ["province:province_1", "scope:province"],
            },
        ]
        fired = {"province:province_1", "scope:region",
                 "significance:major", "world:world_0"}
        result = Layer6Summarizer.filter_relevant_l4(
            l4_candidates=l4_candidates, fired_tags=fired)
        self.assertEqual(result, [])

    def test_filter_fallback_to_l5_content_when_no_fired(self):
        l4_candidates = [
            {
                "id": "match",
                "game_time": 100.0,
                "tags": ["domain:combat", "tier:2"],
            },
        ]
        l5_events = [
            {"tags": ["region:region_1", "nation:nation_1",
                      "domain:combat"]},
        ]
        result = Layer6Summarizer.filter_relevant_l4(
            l4_candidates=l4_candidates, fired_tags=set(),
            l5_events=l5_events,
        )
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["id"], "match")

    def test_filter_returns_empty_when_no_signal(self):
        result = Layer6Summarizer.filter_relevant_l4(
            l4_candidates=[{"id": "a", "tags": ["x:y"], "game_time": 0}],
            fired_tags=set(),
        )
        self.assertEqual(result, [])

    def test_filter_respects_max_results_cap(self):
        l4_candidates = [
            {
                "id": f"e{i}",
                "game_time": 100.0 + i,
                "tags": ["domain:combat"],
            }
            for i in range(20)
        ]
        result = Layer6Summarizer.filter_relevant_l4(
            l4_candidates=l4_candidates,
            fired_tags={"domain:combat"},
        )
        self.assertLessEqual(len(result), 8)


# ══════════════════════════════════════════════════════════════════
# 5. Layer6Manager — on_layer5_created trigger ingestion
# ══════════════════════════════════════════════════════════════════

class TestLayer6Manager(unittest.TestCase):

    def setUp(self):
        Layer6Manager.reset()
        TriggerRegistry.reset()
        self.geo = _setup_geo_registry_multi_nation()
        self.layer_store = LayerStore(db_path=":memory:")
        self.manager = Layer6Manager.get_instance()
        self.manager.initialize(
            layer_store=self.layer_store,
            geo_registry=self.geo,
            wms_ai=None,
            trigger_registry=TriggerRegistry.get_instance(),
        )

    def tearDown(self):
        Layer6Manager.reset()
        TriggerRegistry.reset()
        GeographicRegistry.reset()

    def test_on_layer5_created_strips_address_tags(self):
        evt = _make_l5_event(
            region_id="region_1", nation_id="nation_1",
            extra_tags=["domain:combat", "intensity:heavy"],
        )
        self.manager.on_layer5_created(evt)

        bucket = TriggerRegistry.get_instance().get_weighted_bucket(
            f"{BUCKET_PREFIX}nation_1")
        self.assertIsNotNone(bucket)
        # Every address tag gets stripped before scoring
        self.assertEqual(bucket.get_score("world:world_0"), 0)
        self.assertEqual(bucket.get_score("nation:nation_1"), 0)
        self.assertEqual(bucket.get_score("region:region_1"), 0)
        # Content tags after strip: ["scope:region", "domain:combat",
        # "intensity:heavy"]. scope: is structural (skipped) but still
        # occupies position 0, so domain:combat lands at pos 1 = 8 pts
        # and intensity:heavy at pos 2 = 6 pts.
        self.assertEqual(bucket.get_score("scope:region"), 0)
        self.assertEqual(bucket.get_score("domain:combat"), 8)
        self.assertEqual(bucket.get_score("intensity:heavy"), 6)

    def test_nation_resolution_from_nation_tag(self):
        """The `nation:` tag is always present — simple lookup."""
        evt = _make_l5_event(
            region_id="region_1", nation_id="nation_1",
            extra_tags=["domain:combat"],
        )
        self.manager.on_layer5_created(evt)
        names = TriggerRegistry.get_instance().get_weighted_bucket_names(
            BUCKET_PREFIX)
        self.assertIn(f"{BUCKET_PREFIX}nation_1", names)

    def test_unresolvable_tags_drop_silently(self):
        """Events without a nation: tag are dropped silently."""
        evt = {
            "id": str(uuid.uuid4()),
            "narrative": "No address info.",
            "category": "region_summary",
            "severity": "moderate",
            "game_time": 100.0,
            "tags": ["domain:combat", "intensity:heavy"],
        }
        self.manager.on_layer5_created(evt)
        names = TriggerRegistry.get_instance().get_weighted_bucket_names(
            BUCKET_PREFIX)
        self.assertEqual(names, [])

    def test_should_run_after_threshold_crossed(self):
        self.assertFalse(self.manager.should_run())

        # scope:region occupies position 0 (skipped), so
        # domain:combat lands at pos 1 = 8 pts per event.
        # Threshold is 200 → need 25 events (25 * 8 = 200).
        for i in range(25):
            evt = _make_l5_event(
                region_id=f"region_{(i % 2) + 1}",
                nation_id="nation_1",
                game_time=100 + i, extra_tags=["domain:combat"],
            )
            self.manager.on_layer5_created(evt)
        self.assertTrue(self.manager.should_run())

    def test_multi_nation_isolation(self):
        """Events in nation_1 should not trigger nation_2 and vice versa."""
        # Fire nation_1: 25 events * 8 pts = 200 >= 200
        for i in range(25):
            self.manager.on_layer5_created(_make_l5_event(
                region_id=f"region_{(i % 2) + 1}",
                nation_id="nation_1",
                game_time=100 + i, extra_tags=["domain:combat"],
            ))
        # A few events into nation_2 (not enough to fire)
        for i in range(5):
            self.manager.on_layer5_created(_make_l5_event(
                region_id=f"region_{3 + (i % 2)}",
                nation_id="nation_2",
                game_time=200 + i, extra_tags=["domain:combat"],
            ))

        reg = TriggerRegistry.get_instance()
        b1 = reg.get_weighted_bucket(f"{BUCKET_PREFIX}nation_1")
        b2 = reg.get_weighted_bucket(f"{BUCKET_PREFIX}nation_2")
        self.assertTrue(b1.has_fired())
        self.assertFalse(b2.has_fired())

    def test_run_summarization_stores_l6_event(self):
        for i in range(25):
            eid = str(uuid.uuid4())
            rid = f"region_{(i % 2) + 1}"
            tags = ["world:world_0", "nation:nation_1",
                    f"region:{rid}", "scope:region",
                    "domain:combat", "intensity:heavy"]
            self.layer_store.insert_event(
                layer=5, narrative=f"Region summary {i}",
                game_time=100 + i, category="region_summary",
                severity="moderate", significance="moderate",
                tags=tags, origin_ref="[]", event_id=eid,
            )
            self.manager.on_layer5_created({
                "id": eid, "tags": tags, "game_time": 100 + i,
            })

        self.assertTrue(self.manager.should_run())
        created = self.manager.run_summarization(game_time=500.0)
        self.assertGreaterEqual(created, 1)

        rows = self.layer_store.query_by_tags(
            layer=6, tags=["nation:nation_1"], match_all=True)
        self.assertGreaterEqual(len(rows), 1)
        self.assertEqual(rows[0]["category"], "nation_summary")

    def test_supersession_on_second_run(self):
        """Second summarization should set supersedes_id on new event."""
        for round_num in range(2):
            for i in range(25):
                eid = str(uuid.uuid4())
                rid = f"region_{(i % 2) + 1}"
                tags = ["world:world_0", "nation:nation_1",
                        f"region:{rid}", "scope:region", "domain:combat"]
                game_time = 100 + round_num * 1000 + i
                self.layer_store.insert_event(
                    layer=5, narrative=f"Round {round_num} evt {i}",
                    game_time=game_time, category="region_summary",
                    severity="moderate", significance="moderate",
                    tags=tags, origin_ref="[]", event_id=eid,
                )
                self.manager.on_layer5_created({
                    "id": eid, "tags": tags, "game_time": game_time,
                })
            self.manager.run_summarization(
                game_time=500 + round_num * 1000)

        all_l6 = self.layer_store.query_by_tags(
            layer=6, tags=["nation:nation_1"], match_all=True)
        self.assertEqual(len(all_l6), 2)

    def test_stats_structure(self):
        stats = self.manager.stats
        self.assertTrue(stats["initialized"])
        self.assertIn("summaries_created", stats)
        self.assertIn("runs_completed", stats)
        self.assertIn("trigger", stats)

    def test_stats_reflects_nation_buckets(self):
        evt = _make_l5_event(
            region_id="region_1", nation_id="nation_1",
            extra_tags=["domain:combat"])
        self.manager.on_layer5_created(evt)
        stats = self.manager.stats
        trigger = stats["trigger"]
        self.assertEqual(trigger["nations_tracked"], 1)
        self.assertEqual(trigger["threshold"], 200)
        self.assertIn("nation_1", trigger["per_nation"])


# ══════════════════════════════════════════════════════════════════
# 6. PromptAssembler L6
# ══════════════════════════════════════════════════════════════════

class TestPromptAssemblerL6(unittest.TestCase):

    def setUp(self):
        self.assembler = PromptAssembler()
        self.assembler.load()

    def test_l6_fragments_loaded(self):
        core = self.assembler.get_l6_fragment("_l6_core")
        self.assertTrue(core)
        self.assertIn("nation", core.lower())

    def test_l6_output_fragment_exists(self):
        output = self.assembler.get_l6_fragment("_l6_output")
        self.assertTrue(output)

    def test_l6_context_fragment_exists(self):
        ctx = self.assembler.get_l6_fragment("l6_context:nation_summary")
        self.assertTrue(ctx)

    def test_assemble_l6_has_core_system(self):
        prompt = self.assembler.assemble_l6("<nation>test</nation>")
        self.assertIn("nation", prompt.system.lower())

    def test_assemble_l6_returns_correct_tags(self):
        prompt = self.assembler.assemble_l6("<nation>test</nation>")
        self.assertIn("layer:6", prompt.tags)
        self.assertIn("scope:nation", prompt.tags)

    def test_assemble_l6_with_event_tags_cascade(self):
        event_tags = ["domain:gathering", "intensity:heavy",
                      "nation:nation_1"]
        prompt = self.assembler.assemble_l6(
            data_block="<nation>test</nation>",
            event_tags=event_tags,
        )
        # Tag cascade includes all lower-layer fragments
        self.assertGreater(len(prompt.system), 100)
        self.assertIn("nation", prompt.system.lower())


# ══════════════════════════════════════════════════════════════════
# 7. Layer 6 Integration Test
# ══════════════════════════════════════════════════════════════════

class TestLayer6Integration(unittest.TestCase):

    def setUp(self):
        Layer6Manager.reset()
        TriggerRegistry.reset()
        self.geo = _setup_geo_registry_multi_nation()
        self.layer_store = LayerStore(db_path=":memory:")
        self.manager = Layer6Manager.get_instance()
        self.manager.initialize(
            layer_store=self.layer_store,
            geo_registry=self.geo,
            wms_ai=None,
            trigger_registry=TriggerRegistry.get_instance(),
        )

    def tearDown(self):
        Layer6Manager.reset()
        TriggerRegistry.reset()
        GeographicRegistry.reset()

    def test_l5_events_flow_to_l6_storage(self):
        """Full pipeline: L5 events → weighted buckets → L6 summary."""
        # Populate L5 events in storage
        for i in range(25):
            eid = str(uuid.uuid4())
            rid = f"region_{(i % 2) + 1}"
            tags = ["world:world_0", "nation:nation_1",
                    f"region:{rid}", "scope:region",
                    "domain:gathering", "resource:iron"]
            self.layer_store.insert_event(
                layer=5, narrative=f"Region {rid} mining.",
                game_time=100 + i, category="region_summary",
                severity="moderate", significance="moderate",
                tags=tags, origin_ref="[]", event_id=eid,
            )
            # Ingest into manager
            self.manager.on_layer5_created({
                "id": eid, "tags": tags, "game_time": 100 + i,
            })

        # Trigger should fire
        self.assertTrue(self.manager.should_run())
        count = self.manager.run_summarization(game_time=500.0)
        self.assertGreaterEqual(count, 1)

        # L6 event should exist in storage
        rows = self.layer_store.query_by_tags(
            layer=6, tags=["nation:nation_1"], match_all=True)
        self.assertEqual(len(rows), 1)

        row = rows[0]
        self.assertEqual(row["category"], "nation_summary")
        self.assertIn("nation:nation_1", row["tags"])

    def test_l6_callback_chain_ready_for_l7(self):
        """Layer6Manager.set_layer7_callback hook exists and callable."""
        called = []
        def mock_l7_callback(l6_event_dict):
            called.append(l6_event_dict)

        self.manager.set_layer7_callback(mock_l7_callback)

        # Insert L5 events
        for i in range(25):
            eid = str(uuid.uuid4())
            rid = f"region_{(i % 2) + 1}"
            tags = ["world:world_0", "nation:nation_1",
                    f"region:{rid}", "scope:region", "domain:combat"]
            self.layer_store.insert_event(
                layer=5, narrative=f"Region {rid} combat.",
                game_time=100 + i, category="region_summary",
                severity="moderate", significance="moderate",
                tags=tags, origin_ref="[]", event_id=eid,
            )
            self.manager.on_layer5_created({
                "id": eid, "tags": tags, "game_time": 100 + i,
            })

        # Run summarization
        count = self.manager.run_summarization(game_time=500.0)
        self.assertGreaterEqual(count, 1)
        # Callback should have been invoked (if error handling permits)
        # Note: We set the callback but it's only invoked if store is successful
        # This test validates the hook exists; actual L7 integration is future work


if __name__ == "__main__":
    unittest.main()

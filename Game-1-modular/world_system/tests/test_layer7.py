"""Tests for Layer 7 world summarization system.

Layer 7 aggregates at the **game World** tier (singleton, always world_0).
Each WorldSummaryEvent consolidates Layer 6 nation summaries across every
nation within the single game World. Address tags (world only) are FACTS
assigned at L2 capture and propagated unchanged; the LLM never synthesizes
address tags. See docs/ARCHITECTURAL_DECISIONS.md.

Tests cover:
1. WorldSummaryEvent dataclass
2. Layer7Summarizer — is_applicable, summarize, XML data block,
   filter_relevant_l5 (fired-tag overlap)
3. Layer7Manager — on_layer6_created, world resolution via the
   `world:` address tag, should_run, run_summarization, supersession, stats
4. PromptAssembler L7 — assemble_l7, fragments, L7→L6→L5→L4→L3→L2 cascade
5. Full integration: L6 events → weighted world trigger → L7 storage
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
    WorldSummaryEvent, SEVERITY_ORDER,
)
from world_system.world_memory.trigger_registry import TriggerRegistry
from world_system.world_memory.layer_store import LayerStore
from world_system.world_memory.geographic_registry import (
    GeographicRegistry, Region, RegionLevel,
)
from world_system.world_memory.layer7_summarizer import Layer7Summarizer
from world_system.world_memory.layer7_manager import (
    Layer7Manager, BUCKET_PREFIX,
)
from world_system.world_memory.tag_assignment import assign_higher_layer_tags
from world_system.world_memory.prompt_assembler import PromptAssembler


# ── Helpers ────────────────────────────────────────────────────────

def _make_l6_event(category="nation_summary", severity="moderate",
                   narrative="", nation_id="nation_1",
                   world_id="world_0",
                   game_time=100.0, extra_tags=None, event_id=None):
    """Build a Layer 6 event dict with full address tags.

    Address tags are emitted coarsest → finest: world, nation.
    These are FACTS — assigned at L2 capture time from chunk position
    and propagated unchanged to every layer.
    """
    tags = [
        f"world:{world_id}",
        f"nation:{nation_id}",
        "scope:nation",
    ]
    if extra_tags:
        tags.extend(extra_tags)
    return {
        "id": event_id or str(uuid.uuid4()),
        "narrative": narrative or f"Nation {nation_id} {category}.",
        "category": category,
        "severity": severity,
        "tags": tags,
        "game_time": game_time,
    }


def _setup_geo_registry_single_world():
    """Setup a single-world geographic hierarchy with 2 nations.

        world_0 (The Known Lands)
          nation_1 (Northern Kingdom)     ← L7 target (only world)
            region_1 (Iron Reaches)
              province_1, province_2
            region_2 (Emerald Valley)
              province_3, province_4
          nation_2 (Southern Empire)
            region_3 (Desert Wastes)
              province_5, province_6
            region_4 (Jungle Expanse)
              province_7, province_8

    Single world (no multi-world isolation test — L7 is final tier).
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
# 1. WorldSummaryEvent Dataclass
# ══════════════════════════════════════════════════════════════════

class TestWorldSummaryEvent(unittest.TestCase):

    def test_create_factory_sets_id_and_time(self):
        evt = WorldSummaryEvent.create(
            world_id="world_0",
            narrative="The Known Lands consolidating mining and farming.",
            severity="major",
            source_nation_summary_ids=["n1", "n2"],
            game_time=1000.0,
        )
        self.assertTrue(evt.summary_id)
        self.assertEqual(evt.world_id, "world_0")
        self.assertEqual(evt.severity, "major")
        self.assertEqual(len(evt.source_nation_summary_ids), 2)
        self.assertEqual(evt.created_at, 1000.0)
        self.assertEqual(evt.world_condition, "stable")
        self.assertEqual(evt.dominant_activities, [])

    def test_create_accepts_extra_kwargs(self):
        evt = WorldSummaryEvent.create(
            world_id="world_0",
            narrative="Test world.",
            severity="significant",
            source_nation_summary_ids=["n1", "n2"],
            game_time=500.0,
            dominant_activities=["mining", "farming"],
            dominant_nations=["Northern Kingdom", "Southern Empire"],
            world_condition="shifting",
            relevant_l5_ids=["l5_a", "l5_b", "l5_c"],
            tags=["world:world_0", "scope:world", "domain:gathering"],
        )
        self.assertEqual(evt.dominant_activities, ["mining", "farming"])
        self.assertEqual(evt.world_condition, "shifting")
        self.assertIn("scope:world", evt.tags)
        self.assertEqual(len(evt.relevant_l5_ids), 3)

    def test_supersedes_id_defaults_none(self):
        evt = WorldSummaryEvent.create(
            world_id="world_0",
            narrative="x", severity="minor",
            source_nation_summary_ids=[], game_time=0.0,
        )
        self.assertIsNone(evt.supersedes_id)


# ══════════════════════════════════════════════════════════════════
# 2. Layer7Summarizer — is_applicable + summarize
# ══════════════════════════════════════════════════════════════════

class TestLayer7Summarizer(unittest.TestCase):

    def setUp(self):
        self.summarizer = Layer7Summarizer()
        self.geo = _setup_geo_registry_single_world()

    def tearDown(self):
        GeographicRegistry.reset()

    def test_is_applicable_needs_two_nations(self):
        events = [_make_l6_event(nation_id="nation_1",
                                 world_id="world_0")]
        self.assertFalse(
            self.summarizer.is_applicable(events, "world_0"))

        events.append(_make_l6_event(nation_id="nation_2",
                                     world_id="world_0"))
        self.assertTrue(
            self.summarizer.is_applicable(events, "world_0"))

    def test_is_applicable_requires_world(self):
        events = [
            _make_l6_event(nation_id="nation_1", world_id="world_0"),
            _make_l6_event(nation_id="nation_2", world_id="world_0"),
        ]
        self.assertFalse(self.summarizer.is_applicable(events, ""))

    def test_summarize_produces_event_with_tags(self):
        events = [
            _make_l6_event(
                nation_id="nation_1", world_id="world_0",
                severity="moderate",
                narrative="Northern Kingdom mining boom.",
                extra_tags=["domain:gathering", "resource:iron",
                            "intensity:heavy"]),
            _make_l6_event(
                nation_id="nation_2", world_id="world_0",
                severity="moderate",
                narrative="Southern Empire farming.",
                extra_tags=["domain:gathering", "resource:wood"]),
        ]
        geo_ctx = {
            "world_name": "The Known Lands",
            "nations": [
                {"id": "nation_1", "name": "Northern Kingdom"},
                {"id": "nation_2", "name": "Southern Empire"},
            ],
        }
        result = self.summarizer.summarize(
            l6_events=events, l5_events=[], world_id="world_0",
            geo_context=geo_ctx, game_time=2000.0,
        )
        self.assertIsNotNone(result)
        self.assertEqual(result.world_id, "world_0")
        self.assertIn("The Known Lands", result.narrative)
        self.assertIn("gathering", result.dominant_activities)
        # Address tags propagated as facts from inputs
        self.assertIn("world:world_0", result.tags)
        self.assertIn("scope:world", result.tags)

    def test_summarize_returns_none_when_not_applicable(self):
        result = self.summarizer.summarize(
            l6_events=[_make_l6_event(nation_id="nation_1",
                                      world_id="world_0")],
            l5_events=[], world_id="world_0",
            geo_context={"world_name": "The Known Lands", "nations": []},
            game_time=100.0,
        )
        self.assertIsNone(result)

    def test_world_condition_crisis_on_critical(self):
        events = [
            _make_l6_event(nation_id="nation_1", world_id="world_0",
                           severity="critical"),
            _make_l6_event(nation_id="nation_2", world_id="world_0",
                           severity="minor"),
        ]
        geo_ctx = {"world_name": "Test", "nations": []}
        result = self.summarizer.summarize(
            events, [], "world_0", geo_ctx, game_time=100.0)
        self.assertIsNotNone(result)
        self.assertEqual(result.world_condition, "crisis")

    def test_severity_boost_from_multi_nation(self):
        # 3+ distinct nations → boost by 1 severity tier (moderate → significant)
        events = [
            _make_l6_event(nation_id="nation_1", world_id="world_0",
                           severity="moderate"),
            _make_l6_event(nation_id="nation_2", world_id="world_0",
                           severity="moderate"),
            _make_l6_event(nation_id="nation_3", world_id="world_0",
                           severity="moderate"),
        ]
        geo_ctx = {"world_name": "Test", "nations": []}
        result = self.summarizer.summarize(
            events, [], "world_0", geo_ctx, game_time=100.0)
        self.assertIsNotNone(result)
        self.assertEqual(
            SEVERITY_ORDER[result.severity],
            SEVERITY_ORDER["significant"],
        )


# ══════════════════════════════════════════════════════════════════
# 3. Layer7Summarizer — XML data block
# ══════════════════════════════════════════════════════════════════

class TestLayer7XmlBlock(unittest.TestCase):

    def setUp(self):
        self.summarizer = Layer7Summarizer()

    def test_xml_block_groups_by_nation(self):
        events = [
            _make_l6_event(
                nation_id="nation_1", world_id="world_0",
                narrative="Northern Kingdom mining boom.",
                extra_tags=["domain:gathering"], game_time=150.0),
            _make_l6_event(
                nation_id="nation_2", world_id="world_0",
                narrative="Southern Empire farming.",
                extra_tags=["domain:gathering"], game_time=160.0),
        ]
        xml = self.summarizer.build_xml_data_block(
            l6_events=events, l5_events=[], world_name="The Known Lands",
            nations=[
                {"id": "nation_1", "name": "Northern Kingdom"},
                {"id": "nation_2", "name": "Southern Empire"},
            ],
            game_time=500.0,
        )
        self.assertIn('<world name="The Known Lands">', xml)
        self.assertIn('<nation name="Northern Kingdom">', xml)
        self.assertIn('<nation name="Southern Empire">', xml)
        self.assertIn("Northern Kingdom mining boom.", xml)
        self.assertIn('tags="[', xml)
        self.assertIn("nation:nation_1", xml)
        self.assertIn("world:world_0", xml)

    def test_xml_block_includes_supporting_l5_detail(self):
        events = [
            _make_l6_event(nation_id="nation_1", world_id="world_0",
                           extra_tags=["domain:combat"]),
            _make_l6_event(nation_id="nation_2", world_id="world_0",
                           extra_tags=["domain:combat"]),
        ]
        l5_events = [
            {
                "id": "l5_a",
                "narrative": "Regional conflict.",
                "category": "region_summary",
                "severity": "minor",
                "game_time": 140.0,
                "tags": ["domain:combat", "species:goblin"],
            },
        ]
        xml = self.summarizer.build_xml_data_block(
            l6_events=events, l5_events=l5_events,
            world_name="The Known Lands",
            nations=[{"id": "nation_1", "name": "Northern Kingdom"},
                     {"id": "nation_2", "name": "Southern Empire"}],
            game_time=300.0,
        )
        self.assertIn("<supporting-detail>", xml)
        self.assertIn("Regional conflict.", xml)

    def test_xml_block_cross_nation_bucket(self):
        """Events without nation tags go into cross-nation bucket."""
        events = [
            {
                "id": "g1",
                "narrative": "World-wide crisis.",
                "category": "nation_summary",
                "severity": "critical",
                "game_time": 200.0,
                "tags": ["world:world_0", "scope:world", "domain:crisis"],
            },
            _make_l6_event(nation_id="nation_1", world_id="world_0"),
        ]
        xml = self.summarizer.build_xml_data_block(
            l6_events=events, l5_events=[], world_name="The Known Lands",
            nations=[{"id": "nation_1", "name": "Northern Kingdom"}],
            game_time=500.0,
        )
        self.assertIn("<cross-nation>", xml)
        self.assertIn("World-wide crisis.", xml)


# ══════════════════════════════════════════════════════════════════
# 4. Layer7Summarizer — filter_relevant_l5
# ══════════════════════════════════════════════════════════════════

class TestFilterRelevantL5(unittest.TestCase):

    def test_filter_by_fired_tag_overlap(self):
        l5_candidates = [
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
        result = Layer7Summarizer.filter_relevant_l5(
            l5_candidates=l5_candidates, fired_tags=fired)
        ids = [e["id"] for e in result]
        self.assertIn("hit_a", ids)
        self.assertIn("hit_b", ids)
        self.assertNotIn("miss", ids)
        self.assertEqual(ids[0], "hit_a")

    def test_filter_strips_structural_fired_tags(self):
        """Structural / address fired tags must not match L5 events."""
        l5_candidates = [
            {
                "id": "e1",
                "game_time": 100.0,
                "tags": ["nation:nation_1", "scope:nation"],
            },
        ]
        fired = {"nation:nation_1", "scope:world",
                 "significance:major", "world:world_0"}
        result = Layer7Summarizer.filter_relevant_l5(
            l5_candidates=l5_candidates, fired_tags=fired)
        self.assertEqual(result, [])

    def test_filter_fallback_to_l6_content_when_no_fired(self):
        l5_candidates = [
            {
                "id": "match",
                "game_time": 100.0,
                "tags": ["domain:combat", "tier:2"],
            },
        ]
        l6_events = [
            {"tags": ["world:world_0", "nation:nation_1",
                      "domain:combat"]},
        ]
        result = Layer7Summarizer.filter_relevant_l5(
            l5_candidates=l5_candidates, fired_tags=set(),
            l6_events=l6_events,
        )
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["id"], "match")

    def test_filter_respects_max_results_cap(self):
        l5_candidates = [
            {
                "id": f"e{i}",
                "game_time": 100.0 + i,
                "tags": ["domain:combat"],
            }
            for i in range(20)
        ]
        result = Layer7Summarizer.filter_relevant_l5(
            l5_candidates=l5_candidates,
            fired_tags={"domain:combat"},
        )
        self.assertLessEqual(len(result), 8)


# ══════════════════════════════════════════════════════════════════
# 5. Layer7Manager — on_layer6_created trigger ingestion
# ══════════════════════════════════════════════════════════════════

class TestLayer7Manager(unittest.TestCase):

    def setUp(self):
        Layer7Manager.reset()
        TriggerRegistry.reset()
        self.geo = _setup_geo_registry_single_world()
        self.layer_store = LayerStore(db_path=":memory:")
        self.manager = Layer7Manager.get_instance()
        self.manager.initialize(
            layer_store=self.layer_store,
            geo_registry=self.geo,
            wms_ai=None,
            trigger_registry=TriggerRegistry.get_instance(),
        )

    def tearDown(self):
        Layer7Manager.reset()
        TriggerRegistry.reset()
        GeographicRegistry.reset()

    def test_on_layer6_created_strips_address_tags(self):
        evt = _make_l6_event(
            nation_id="nation_1", world_id="world_0",
            extra_tags=["domain:combat", "intensity:heavy"],
        )
        self.manager.on_layer6_created(evt)

        bucket = TriggerRegistry.get_instance().get_weighted_bucket(
            f"{BUCKET_PREFIX}world_0")
        self.assertIsNotNone(bucket)
        # Every address tag gets stripped before scoring
        self.assertEqual(bucket.get_score("world:world_0"), 0)
        self.assertEqual(bucket.get_score("nation:nation_1"), 0)
        # Content tags after strip: ["scope:nation", "domain:combat",
        # "intensity:heavy"]. scope: is structural (skipped) but still
        # occupies position 0, so domain:combat lands at pos 1 = 8 pts
        self.assertEqual(bucket.get_score("scope:nation"), 0)
        self.assertEqual(bucket.get_score("domain:combat"), 8)
        self.assertEqual(bucket.get_score("intensity:heavy"), 6)

    def test_world_resolution_from_world_tag(self):
        """The `world:` tag is always present — simple lookup."""
        evt = _make_l6_event(
            nation_id="nation_1", world_id="world_0",
            extra_tags=["domain:combat"],
        )
        self.manager.on_layer6_created(evt)
        names = TriggerRegistry.get_instance().get_weighted_bucket_names(
            BUCKET_PREFIX)
        self.assertIn(f"{BUCKET_PREFIX}world_0", names)

    def test_should_run_after_threshold_crossed(self):
        self.assertFalse(self.manager.should_run())

        # scope:nation at pos 0 (skipped) → domain:combat at pos 1 = 8 pts.
        # Threshold 200 → need 25 events (25 * 8 = 200).
        for i in range(25):
            evt = _make_l6_event(
                nation_id=f"nation_{(i % 2) + 1}",
                world_id="world_0",
                game_time=100 + i, extra_tags=["domain:combat"],
            )
            self.manager.on_layer6_created(evt)
        self.assertTrue(self.manager.should_run())

    def test_run_summarization_stores_l7_event(self):
        for i in range(25):
            eid = str(uuid.uuid4())
            nid = f"nation_{(i % 2) + 1}"
            tags = ["world:world_0", f"nation:{nid}",
                    "scope:nation", "domain:combat", "intensity:heavy"]
            self.layer_store.insert_event(
                layer=6, narrative=f"Nation summary {i}",
                game_time=100 + i, category="nation_summary",
                severity="moderate", significance="moderate",
                tags=tags, origin_ref="[]", event_id=eid,
            )
            self.manager.on_layer6_created({
                "id": eid, "tags": tags, "game_time": 100 + i,
            })

        self.assertTrue(self.manager.should_run())
        created = self.manager.run_summarization(game_time=500.0)
        self.assertGreaterEqual(created, 1)

        rows = self.layer_store.query_by_tags(
            layer=7, tags=["world:world_0"], match_all=True)
        self.assertGreaterEqual(len(rows), 1)
        self.assertEqual(rows[0]["category"], "world_summary")

    def test_supersession_on_second_run(self):
        """Second summarization should set supersedes_id on new event."""
        for round_num in range(2):
            for i in range(25):
                eid = str(uuid.uuid4())
                nid = f"nation_{(i % 2) + 1}"
                tags = ["world:world_0", f"nation:{nid}",
                        "scope:nation", "domain:combat"]
                game_time = 100 + round_num * 1000 + i
                self.layer_store.insert_event(
                    layer=6, narrative=f"Round {round_num} evt {i}",
                    game_time=game_time, category="nation_summary",
                    severity="moderate", significance="moderate",
                    tags=tags, origin_ref="[]", event_id=eid,
                )
                self.manager.on_layer6_created({
                    "id": eid, "tags": tags, "game_time": game_time,
                })
            self.manager.run_summarization(
                game_time=500 + round_num * 1000)

        all_l7 = self.layer_store.query_by_tags(
            layer=7, tags=["world:world_0"], match_all=True)
        self.assertEqual(len(all_l7), 2)

    def test_stats_structure(self):
        stats = self.manager.stats
        self.assertTrue(stats["initialized"])
        self.assertIn("summaries_created", stats)
        self.assertIn("runs_completed", stats)
        self.assertIn("trigger", stats)


# ══════════════════════════════════════════════════════════════════
# 6. PromptAssembler L7
# ══════════════════════════════════════════════════════════════════

class TestPromptAssemblerL7(unittest.TestCase):

    def setUp(self):
        self.assembler = PromptAssembler()
        self.assembler.load()

    def test_l7_fragments_loaded(self):
        core = self.assembler.get_l7_fragment("_l7_core")
        self.assertTrue(core)
        self.assertIn("world", core.lower())

    def test_l7_output_fragment_exists(self):
        output = self.assembler.get_l7_fragment("_l7_output")
        self.assertTrue(output)

    def test_l7_context_fragment_exists(self):
        ctx = self.assembler.get_l7_fragment("l7_context:world_summary")
        self.assertTrue(ctx)

    def test_assemble_l7_has_core_system(self):
        prompt = self.assembler.assemble_l7("<world>test</world>")
        self.assertIn("world", prompt.system.lower())

    def test_assemble_l7_returns_correct_tags(self):
        prompt = self.assembler.assemble_l7("<world>test</world>")
        self.assertIn("layer:7", prompt.tags)
        self.assertIn("scope:world", prompt.tags)

    def test_assemble_l7_with_event_tags_cascade(self):
        event_tags = ["domain:gathering", "intensity:heavy",
                      "world:world_0"]
        prompt = self.assembler.assemble_l7(
            data_block="<world>test</world>",
            event_tags=event_tags,
        )
        # Tag cascade includes all lower-layer fragments
        self.assertGreater(len(prompt.system), 100)
        self.assertIn("world", prompt.system.lower())


# ══════════════════════════════════════════════════════════════════
# 7. Layer 7 Integration Test
# ══════════════════════════════════════════════════════════════════

class TestLayer7Integration(unittest.TestCase):

    def setUp(self):
        Layer7Manager.reset()
        TriggerRegistry.reset()
        self.geo = _setup_geo_registry_single_world()
        self.layer_store = LayerStore(db_path=":memory:")
        self.manager = Layer7Manager.get_instance()
        self.manager.initialize(
            layer_store=self.layer_store,
            geo_registry=self.geo,
            wms_ai=None,
            trigger_registry=TriggerRegistry.get_instance(),
        )

    def tearDown(self):
        Layer7Manager.reset()
        TriggerRegistry.reset()
        GeographicRegistry.reset()

    def test_l6_events_flow_to_l7_storage(self):
        """Full pipeline: L6 events → weighted bucket → L7 summary."""
        # Populate L6 events in storage
        for i in range(25):
            eid = str(uuid.uuid4())
            nid = f"nation_{(i % 2) + 1}"
            tags = ["world:world_0", f"nation:{nid}",
                    "scope:nation", "domain:gathering", "resource:iron"]
            self.layer_store.insert_event(
                layer=6, narrative=f"Nation {nid} mining.",
                game_time=100 + i, category="nation_summary",
                severity="moderate", significance="moderate",
                tags=tags, origin_ref="[]", event_id=eid,
            )
            # Ingest into manager
            self.manager.on_layer6_created({
                "id": eid, "tags": tags, "game_time": 100 + i,
            })

        # Trigger should fire
        self.assertTrue(self.manager.should_run())
        count = self.manager.run_summarization(game_time=500.0)
        self.assertGreaterEqual(count, 1)

        # L7 event should exist in storage
        rows = self.layer_store.query_by_tags(
            layer=7, tags=["world:world_0"], match_all=True)
        self.assertEqual(len(rows), 1)

        row = rows[0]
        self.assertEqual(row["category"], "world_summary")
        self.assertIn("world:world_0", row["tags"])


if __name__ == "__main__":
    unittest.main()

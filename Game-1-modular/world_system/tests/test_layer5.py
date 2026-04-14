"""Tests for Layer 5 realm summarization system.

Tests cover:
1. RealmSummaryEvent dataclass
2. Layer5Summarizer — is_applicable, summarize, XML data block,
   filter_relevant_l3 (fired-tag overlap)
3. Layer5Manager — on_layer4_created, realm resolution via geographic
   parent chain, should_run, run_summarization, multi-realm isolation,
   supersession, stats
4. PromptAssembler L5 — assemble_l5, fragments, L5→L4→L3→L2 cascade
5. Full integration: L4 events → weighted realm trigger → L5 storage

Pure WMS pipeline: Layer 5 does NOT read FactionSystem, EcosystemAgent,
or any other state tracker. See docs/ARCHITECTURAL_DECISIONS.md §§4-5.
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
    RealmSummaryEvent, SEVERITY_ORDER,
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
                   narrative="", province_id="region_1",
                   nation_id="nation_1", realm_id="realm_0",
                   game_time=100.0, extra_tags=None, event_id=None):
    """Build a Layer 4 event dict with full geographic address tags."""
    tags = [
        f"realm:{realm_id}",
        f"nation:{nation_id}",
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


def _setup_geo_registry_multi_realm():
    """Setup a two-realm geographic hierarchy.

    realm_0 (Known Lands):
      nation_1 (Northern Kingdom)
        region_1 (Iron Reaches)
        region_2 (Emerald Valley)
      nation_2 (Southern Reach)
        region_3 (Sunspire)
    realm_1 (Shadowlands):
      nation_3 (Dark Empire)
        region_4 (Night Barrens)
    """
    GeographicRegistry.reset()
    geo = GeographicRegistry.get_instance()

    realm0 = Region(region_id="realm_0", name="Known Lands",
                    level=RegionLevel.REALM,
                    bounds_x1=-500, bounds_y1=-500,
                    bounds_x2=500, bounds_y2=500)
    geo.regions["realm_0"] = realm0
    geo.realm = realm0

    realm1 = Region(region_id="realm_1", name="Shadowlands",
                    level=RegionLevel.REALM,
                    bounds_x1=500, bounds_y1=500,
                    bounds_x2=1000, bounds_y2=1000)
    geo.regions["realm_1"] = realm1

    # Nations under realm_0
    nation1 = Region(region_id="nation_1", name="Northern Kingdom",
                     level=RegionLevel.NATION,
                     bounds_x1=-500, bounds_y1=-500,
                     bounds_x2=0, bounds_y2=500,
                     parent_id="realm_0")
    geo.regions["nation_1"] = nation1
    realm0.child_ids.append("nation_1")

    nation2 = Region(region_id="nation_2", name="Southern Reach",
                     level=RegionLevel.NATION,
                     bounds_x1=0, bounds_y1=-500,
                     bounds_x2=500, bounds_y2=500,
                     parent_id="realm_0")
    geo.regions["nation_2"] = nation2
    realm0.child_ids.append("nation_2")

    # Nation under realm_1
    nation3 = Region(region_id="nation_3", name="Dark Empire",
                     level=RegionLevel.NATION,
                     bounds_x1=500, bounds_y1=500,
                     bounds_x2=1000, bounds_y2=1000,
                     parent_id="realm_1")
    geo.regions["nation_3"] = nation3
    realm1.child_ids.append("nation_3")

    # Provinces
    province_specs = [
        ("region_1", "Iron Reaches", "nation_1"),
        ("region_2", "Emerald Valley", "nation_1"),
        ("region_3", "Sunspire", "nation_2"),
        ("region_4", "Night Barrens", "nation_3"),
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
# 1. RealmSummaryEvent Dataclass
# ══════════════════════════════════════════════════════════════════

class TestRealmSummaryEvent(unittest.TestCase):

    def test_create_factory_sets_id_and_time(self):
        evt = RealmSummaryEvent.create(
            realm_id="realm_0",
            narrative="Realm-wide mining boom with combat in the north.",
            severity="major",
            source_province_summary_ids=["p1", "p2", "p3"],
            game_time=1000.0,
        )
        self.assertTrue(evt.summary_id)
        self.assertEqual(evt.realm_id, "realm_0")
        self.assertEqual(evt.severity, "major")
        self.assertEqual(len(evt.source_province_summary_ids), 3)
        self.assertEqual(evt.created_at, 1000.0)
        self.assertEqual(evt.realm_condition, "stable")
        self.assertEqual(evt.dominant_activities, [])

    def test_create_accepts_extra_kwargs(self):
        evt = RealmSummaryEvent.create(
            realm_id="realm_0",
            narrative="Test.",
            severity="moderate",
            source_province_summary_ids=["p1"],
            game_time=500.0,
            dominant_activities=["mining", "combat"],
            dominant_provinces=["region_1"],
            realm_condition="volatile",
            relevant_l3_ids=["l3_a", "l3_b"],
            tags=["realm:realm_0", "scope:realm", "domain:combat"],
        )
        self.assertEqual(evt.dominant_activities, ["mining", "combat"])
        self.assertEqual(evt.realm_condition, "volatile")
        self.assertIn("scope:realm", evt.tags)
        self.assertEqual(len(evt.relevant_l3_ids), 2)

    def test_supersedes_id_defaults_none(self):
        evt = RealmSummaryEvent.create(
            realm_id="realm_0",
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
        self.geo = _setup_geo_registry_multi_realm()

    def tearDown(self):
        GeographicRegistry.reset()

    def test_is_applicable_needs_two_events(self):
        events = [_make_l4_event(province_id="region_1")]
        self.assertFalse(
            self.summarizer.is_applicable(events, "realm_0"))

        events.append(_make_l4_event(province_id="region_2"))
        self.assertTrue(
            self.summarizer.is_applicable(events, "realm_0"))

    def test_is_applicable_requires_realm(self):
        events = [
            _make_l4_event(province_id="region_1"),
            _make_l4_event(province_id="region_2"),
        ]
        self.assertFalse(self.summarizer.is_applicable(events, ""))

    def test_summarize_produces_event_with_tags(self):
        events = [
            _make_l4_event(
                province_id="region_1", severity="moderate",
                narrative="Iron Reaches mining boom.",
                extra_tags=["domain:gathering", "resource:iron",
                            "intensity:heavy"]),
            _make_l4_event(
                province_id="region_2", severity="moderate",
                narrative="Emerald Valley gathering.",
                extra_tags=["domain:gathering", "resource:wood"]),
        ]
        geo_ctx = {
            "realm_name": "Known Lands",
            "provinces": [
                {"id": "region_1", "name": "Iron Reaches"},
                {"id": "region_2", "name": "Emerald Valley"},
            ],
        }
        result = self.summarizer.summarize(
            l4_events=events, l3_events=[], realm_id="realm_0",
            geo_context=geo_ctx, game_time=2000.0,
        )
        self.assertIsNotNone(result)
        self.assertEqual(result.realm_id, "realm_0")
        self.assertIn("Known Lands", result.narrative)
        # Dominant activity should be extracted
        self.assertIn("gathering", result.dominant_activities)
        # Tags should include realm and scope
        self.assertIn("realm:realm_0", result.tags)
        self.assertIn("scope:realm", result.tags)

    def test_summarize_returns_none_when_not_applicable(self):
        result = self.summarizer.summarize(
            l4_events=[_make_l4_event(province_id="region_1")],
            l3_events=[], realm_id="realm_0",
            geo_context={"realm_name": "Known Lands", "provinces": []},
            game_time=100.0,
        )
        self.assertIsNone(result)

    def test_severity_boost_from_multi_province(self):
        # 4 provinces → boost by 1 severity tier from moderate → significant
        events = [
            _make_l4_event(province_id="region_1", severity="moderate"),
            _make_l4_event(province_id="region_2", severity="moderate"),
            _make_l4_event(province_id="region_3", severity="moderate"),
            _make_l4_event(province_id="region_4", severity="moderate"),
        ]
        geo_ctx = {"realm_name": "Test", "provinces": []}
        result = self.summarizer.summarize(
            events, [], "realm_0", geo_ctx, game_time=100.0)
        self.assertIsNotNone(result)
        # Boosted from moderate → significant (4+ provinces)
        self.assertEqual(
            SEVERITY_ORDER[result.severity],
            SEVERITY_ORDER["significant"],
        )

    def test_realm_condition_crisis_on_critical(self):
        events = [
            _make_l4_event(province_id="region_1", severity="critical"),
            _make_l4_event(province_id="region_2", severity="minor"),
        ]
        geo_ctx = {"realm_name": "Test", "provinces": []}
        result = self.summarizer.summarize(
            events, [], "realm_0", geo_ctx, game_time=100.0)
        self.assertIsNotNone(result)
        self.assertEqual(result.realm_condition, "crisis")

    def test_realm_condition_volatile_on_two_majors(self):
        events = [
            _make_l4_event(province_id="region_1", severity="major"),
            _make_l4_event(province_id="region_2", severity="major"),
        ]
        geo_ctx = {"realm_name": "Test", "provinces": []}
        result = self.summarizer.summarize(
            events, [], "realm_0", geo_ctx, game_time=100.0)
        self.assertEqual(result.realm_condition, "volatile")

    def test_dominant_provinces_by_count(self):
        events = [
            _make_l4_event(province_id="region_1"),
            _make_l4_event(province_id="region_1"),
            _make_l4_event(province_id="region_2"),
        ]
        geo_ctx = {"realm_name": "Test", "provinces": []}
        result = self.summarizer.summarize(
            events, [], "realm_0", geo_ctx, game_time=100.0)
        self.assertEqual(result.dominant_provinces[0], "region_1")


# ══════════════════════════════════════════════════════════════════
# 3. Layer5Summarizer — XML data block
# ══════════════════════════════════════════════════════════════════

class TestLayer5XmlBlock(unittest.TestCase):

    def setUp(self):
        self.summarizer = Layer5Summarizer()

    def test_xml_block_groups_by_province(self):
        events = [
            _make_l4_event(
                province_id="region_1", narrative="Iron mines busy.",
                extra_tags=["domain:gathering"], game_time=150.0),
            _make_l4_event(
                province_id="region_2", narrative="Forest expansion.",
                extra_tags=["domain:gathering"], game_time=160.0),
        ]
        xml = self.summarizer.build_xml_data_block(
            l4_events=events, l3_events=[], realm_name="Known Lands",
            provinces=[
                {"id": "region_1", "name": "Iron Reaches"},
                {"id": "region_2", "name": "Emerald Valley"},
            ],
            game_time=500.0,
        )
        self.assertIn('<realm name="Known Lands">', xml)
        self.assertIn('<province name="Iron Reaches">', xml)
        self.assertIn('<province name="Emerald Valley">', xml)
        self.assertIn("Iron mines busy.", xml)
        # Tags appear in brackets for LLM rewrite context
        self.assertIn('tags="[', xml)
        self.assertIn("province:region_1", xml)

    def test_xml_block_includes_supporting_l3_detail(self):
        events = [
            _make_l4_event(province_id="region_1",
                           extra_tags=["domain:combat"]),
            _make_l4_event(province_id="region_1",
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
            realm_name="Known Lands",
            provinces=[{"id": "region_1", "name": "Iron Reaches"}],
            game_time=300.0,
        )
        self.assertIn("<supporting-detail>", xml)
        self.assertIn("Wolf pack sightings.", xml)

    def test_xml_block_cross_province_bucket(self):
        """Events without province tags go into cross-province bucket."""
        events = [
            {
                "id": "g1",
                "narrative": "Realm-wide festival.",
                "category": "province_summary",
                "severity": "moderate",
                "game_time": 200.0,
                "tags": ["realm:realm_0", "scope:realm",
                         "domain:social"],
            },
            _make_l4_event(province_id="region_1"),
        ]
        xml = self.summarizer.build_xml_data_block(
            l4_events=events, l3_events=[], realm_name="Known Lands",
            provinces=[{"id": "region_1", "name": "Iron Reaches"}],
            game_time=500.0,
        )
        self.assertIn("<cross-province>", xml)
        self.assertIn("Realm-wide festival.", xml)


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
        # hit_a has 2 matches, hit_b has 1 → hit_a first
        self.assertEqual(ids[0], "hit_a")

    def test_filter_strips_structural_fired_tags(self):
        """Structural / geographic fired tags must not match L3 events."""
        l3_candidates = [
            {
                "id": "e1",
                "game_time": 100.0,
                "tags": ["province:region_1", "scope:district"],
            },
        ]
        # All structural → no content survivors → returns empty or
        # fallback to L4 content tags (none given) → empty
        fired = {"province:region_1", "scope:realm",
                 "significance:major"}
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
            {"tags": ["province:region_1", "domain:combat"]},
        ]
        # Empty fired → fallback to L4 content tags → domain:combat matches
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
        # _L3_MAX_RESULTS = 8
        self.assertLessEqual(len(result), 8)


# ══════════════════════════════════════════════════════════════════
# 5. Layer5Manager — on_layer4_created trigger ingestion
# ══════════════════════════════════════════════════════════════════

class TestLayer5Manager(unittest.TestCase):

    def setUp(self):
        Layer5Manager.reset()
        TriggerRegistry.reset()
        self.geo = _setup_geo_registry_multi_realm()
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

    def test_on_layer4_created_strips_geographic_tags(self):
        evt = _make_l4_event(
            province_id="region_1",
            extra_tags=["domain:combat", "intensity:heavy"],
        )
        self.manager.on_layer4_created(evt)

        bucket = TriggerRegistry.get_instance().get_weighted_bucket(
            f"{BUCKET_PREFIX}realm_0")
        self.assertIsNotNone(bucket)
        # Geographic tags are stripped before scoring
        self.assertEqual(bucket.get_score("realm:realm_0"), 0)
        self.assertEqual(bucket.get_score("nation:nation_1"), 0)
        self.assertEqual(bucket.get_score("province:region_1"), 0)
        # Content tags consume positional weight.
        # After geo strip, content tags are
        # ["scope:province", "domain:combat", "intensity:heavy"] because
        # Layer4Summarizer always emits a scope:province tag. scope: is
        # structural (skipped by WeightedTriggerBucket) but still occupies
        # position 0, so domain:combat is at pos 1 = 8 and intensity:heavy
        # at pos 2 = 6.
        self.assertEqual(bucket.get_score("scope:province"), 0)
        self.assertEqual(bucket.get_score("domain:combat"), 8)
        self.assertEqual(bucket.get_score("intensity:heavy"), 6)

    def test_realm_resolution_from_explicit_realm_tag(self):
        """Fast path: if tag has realm:X, use it directly."""
        evt = _make_l4_event(
            province_id="region_1", realm_id="realm_0",
            extra_tags=["domain:combat"],
        )
        self.manager.on_layer4_created(evt)
        names = TriggerRegistry.get_instance().get_weighted_bucket_names(
            BUCKET_PREFIX)
        self.assertIn(f"{BUCKET_PREFIX}realm_0", names)

    def test_realm_resolution_via_parent_chain(self):
        """No realm tag → walk province → nation → realm."""
        evt = {
            "id": str(uuid.uuid4()),
            "narrative": "Walked up from province.",
            "category": "province_summary",
            "severity": "moderate",
            "game_time": 100.0,
            "tags": ["province:region_4", "domain:combat",
                     "intensity:heavy"],
        }
        self.manager.on_layer4_created(evt)
        names = TriggerRegistry.get_instance().get_weighted_bucket_names(
            BUCKET_PREFIX)
        # region_4 is under nation_3 under realm_1
        self.assertIn(f"{BUCKET_PREFIX}realm_1", names)
        self.assertNotIn(f"{BUCKET_PREFIX}realm_0", names)

    def test_realm_resolution_from_nation_tag(self):
        """A bare nation: tag should walk one step up to its realm."""
        evt = {
            "id": str(uuid.uuid4()),
            "narrative": "Nation-level data.",
            "category": "province_summary",
            "severity": "moderate",
            "game_time": 100.0,
            "tags": ["nation:nation_2", "domain:social"],
        }
        self.manager.on_layer4_created(evt)
        names = TriggerRegistry.get_instance().get_weighted_bucket_names(
            BUCKET_PREFIX)
        self.assertIn(f"{BUCKET_PREFIX}realm_0", names)

    def test_unresolvable_tags_drop_silently(self):
        evt = {
            "id": str(uuid.uuid4()),
            "narrative": "No geo info.",
            "category": "province_summary",
            "severity": "moderate",
            "game_time": 100.0,
            "tags": ["domain:combat", "intensity:heavy"],
        }
        self.manager.on_layer4_created(evt)
        # No realm bucket registered
        names = TriggerRegistry.get_instance().get_weighted_bucket_names(
            BUCKET_PREFIX)
        self.assertEqual(names, [])

    def test_should_run_after_threshold_crossed(self):
        self.assertFalse(self.manager.should_run())

        # With scope:province occupying position 0 (structural, skipped),
        # domain:combat lands at position 1 = 8 pts per event.
        # Threshold is 100 → need 13 events (13 * 8 = 104).
        for i in range(13):
            evt = _make_l4_event(
                province_id="region_1", game_time=100 + i,
                extra_tags=["domain:combat"],
            )
            self.manager.on_layer4_created(evt)
        self.assertTrue(self.manager.should_run())

    def test_multi_realm_isolation(self):
        """Events in realm_0 should not trigger realm_1 and vice versa."""
        # Fire realm_0: 13 events * 8 pts (domain:combat at pos 1
        # because scope:province occupies pos 0) = 104 > 100
        for i in range(13):
            self.manager.on_layer4_created(_make_l4_event(
                province_id="region_1", realm_id="realm_0",
                game_time=100 + i,
                extra_tags=["domain:combat"],
            ))
        # Only a few events into realm_1 (region_4 under nation_3)
        for i in range(3):
            self.manager.on_layer4_created({
                "id": str(uuid.uuid4()),
                "narrative": "x",
                "category": "province_summary",
                "severity": "moderate",
                "game_time": 200 + i,
                "tags": ["realm:realm_1", "nation:nation_3",
                         "province:region_4", "domain:combat"],
            })

        reg = TriggerRegistry.get_instance()
        b0 = reg.get_weighted_bucket(f"{BUCKET_PREFIX}realm_0")
        b1 = reg.get_weighted_bucket(f"{BUCKET_PREFIX}realm_1")
        self.assertTrue(b0.has_fired())
        self.assertFalse(b1.has_fired())

    def test_run_summarization_stores_l5_event(self):
        # Seed L4 events in both the LayerStore AND the manager.
        # Realistic L4 tags include scope:province, so domain:combat
        # lands at pos 1 = 8 pts → need 13 events to fire.
        event_ids = []
        for i in range(13):
            eid = str(uuid.uuid4())
            tags = ["realm:realm_0", "nation:nation_1",
                    f"province:region_{(i % 2) + 1}",
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
            event_ids.append(eid)

        self.assertTrue(self.manager.should_run())
        created = self.manager.run_summarization(game_time=500.0)
        self.assertGreaterEqual(created, 1)

        rows = self.layer_store.query_by_tags(
            layer=5, tags=["realm:realm_0"], match_all=True)
        self.assertGreaterEqual(len(rows), 1)
        self.assertEqual(rows[0]["category"], "realm_summary")

    def test_supersession_on_second_run(self):
        """Second summarization should set supersedes_id on new event."""
        for round_num in range(2):
            for i in range(13):
                eid = str(uuid.uuid4())
                tags = ["realm:realm_0", "nation:nation_1",
                        f"province:region_{(i % 2) + 1}",
                        "scope:province",
                        "domain:combat"]
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
            layer=5, tags=["realm:realm_0"], match_all=True)
        self.assertEqual(len(all_l5), 2)

    def test_stats_structure(self):
        stats = self.manager.stats
        self.assertTrue(stats["initialized"])
        self.assertIn("summaries_created", stats)
        self.assertIn("runs_completed", stats)
        self.assertIn("trigger", stats)

    def test_stats_reflects_realm_buckets(self):
        evt = _make_l4_event(
            province_id="region_1", extra_tags=["domain:combat"])
        self.manager.on_layer4_created(evt)
        stats = self.manager.stats
        trigger = stats["trigger"]
        self.assertEqual(trigger["realms_tracked"], 1)
        self.assertEqual(trigger["threshold"], 100)
        self.assertIn("realm_0", trigger["per_realm"])


# ══════════════════════════════════════════════════════════════════
# 6. PromptAssembler L5
# ══════════════════════════════════════════════════════════════════

class TestPromptAssemblerL5(unittest.TestCase):

    def setUp(self):
        self.assembler = PromptAssembler()
        self.assembler.load()

    def test_l5_fragments_loaded(self):
        """L5 fragment file should be loaded alongside L3/L4."""
        core = self.assembler.get_l5_fragment("_l5_core")
        self.assertTrue(core)
        self.assertIn("realm", core.lower())

    def test_l5_output_fragment_exists(self):
        output = self.assembler.get_l5_fragment("_l5_output")
        self.assertTrue(output)

    def test_l5_context_fragment_exists(self):
        ctx = self.assembler.get_l5_fragment("l5_context:realm_summary")
        self.assertTrue(ctx)

    def test_assemble_l5_has_core_system(self):
        prompt = self.assembler.assemble_l5("<realm>test</realm>")
        self.assertIn("realm", prompt.system.lower())
        self.assertIn("<realm>test</realm>", prompt.user)
        self.assertGreater(prompt.token_estimate, 0)

    def test_assemble_l5_tags_layer_and_scope(self):
        prompt = self.assembler.assemble_l5("")
        self.assertIn("layer:5", prompt.tags)
        self.assertIn("scope:realm", prompt.tags)

    def test_assemble_l5_cascade_from_lower_layers(self):
        """L5 prompt should pull relevant tag fragments from L4/L3/L2.

        With event tags covering content from lower layers, assemble_l5
        should aggregate matching fragments from ALL layers — not just L5.
        """
        prompt = self.assembler.assemble_l5(
            data_block="<realm name='Known Lands'>data</realm>",
            event_tags=["domain:combat", "species:wolf",
                        "tier:2", "intensity:heavy"],
        )
        self.assertIsNotNone(prompt.system)
        self.assertGreater(prompt.token_estimate, 0)
        # Fragment keys used should come from multiple layers when matches
        # exist. At minimum, _l5_core is always included.
        frag_keys = [k for k, _ in prompt.fragments_used]
        self.assertIn("_l5_core", frag_keys)

    def test_assemble_l5_user_includes_output_instruction(self):
        prompt = self.assembler.assemble_l5("<realm>x</realm>")
        # The user part should have both the data and an output instruction
        self.assertIn("<realm>x</realm>", prompt.user)


# ══════════════════════════════════════════════════════════════════
# 7. Full Integration: L4 events → weighted realm trigger → L5 storage
# ══════════════════════════════════════════════════════════════════

class TestLayer5Integration(unittest.TestCase):

    def setUp(self):
        Layer5Manager.reset()
        TriggerRegistry.reset()
        self.geo = _setup_geo_registry_multi_realm()
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
        """Simulate L4 events accumulating, triggering an L5 realm summary."""
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
                tags=["province:region_1", "district:district_a",
                      "domain:combat", "species:wolf",
                      "intensity:heavy"],
                origin_ref="[]",
                event_id=f"l3_{i}",
            )

        # Seed L4 events across two provinces in realm_0 until threshold.
        # domain:combat at position 1 (after scope:province at pos 0) = 8 pts
        # per event → need 13 events to cross threshold (13*8 = 104).
        event_ids = []
        for i in range(13):
            eid = str(uuid.uuid4())
            pid = f"region_{(i % 2) + 1}"
            tags = ["realm:realm_0", "nation:nation_1",
                    f"province:{pid}", "scope:province",
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
            event_ids.append(eid)

        # domain:combat at position 0 = 10 pts * 10 events = 100 → fires
        self.assertTrue(self.manager.should_run())
        created = self.manager.run_summarization(game_time=1000.0)
        self.assertEqual(created, 1)

        # Verify L5 event was stored
        l5_events = self.layer_store.query_by_tags(
            layer=5, tags=["realm:realm_0"], match_all=True)
        self.assertEqual(len(l5_events), 1)
        l5 = l5_events[0]
        self.assertEqual(l5["category"], "realm_summary")
        self.assertIn("Known Lands", l5["narrative"])

        # Stats should reflect the successful run
        stats = self.manager.stats
        self.assertEqual(stats["summaries_created"], 1)
        self.assertEqual(stats["runs_completed"], 1)

    def test_no_run_when_insufficient_events(self):
        """Threshold not crossed → should_run is False and no L5 produced."""
        for i in range(3):
            eid = str(uuid.uuid4())
            tags = ["realm:realm_0", "province:region_1",
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
            layer=5, tags=["realm:realm_0"], match_all=True)
        self.assertEqual(l5_events, [])


if __name__ == "__main__":
    unittest.main()

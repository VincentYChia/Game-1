"""Tests for Layer 3 consolidation system.

Tests cover:
1. ConsolidatorBase and ConsolidatedEvent
2. Layer3Manager trigger logic and orchestration
3. All 4 consolidators (regional, cross_domain, player_identity, faction)
4. PromptAssembler multi-file loading
5. Tag assignment for Layer 3
6. Full integration pipeline (L2 → L3)
"""

import json
import os
import sys
import time
import unittest
import uuid

# Ensure the Game-1-modular directory is on the path
_this_dir = os.path.dirname(os.path.abspath(__file__))
_game_dir = os.path.dirname(os.path.dirname(_this_dir))
if _game_dir not in sys.path:
    sys.path.insert(0, _game_dir)


from world_system.world_memory.event_schema import (
    ConsolidatedEvent, InterpretedEvent, WorldMemoryEvent, SEVERITY_ORDER,
)
from world_system.world_memory.layer_store import LayerStore
from world_system.world_memory.geographic_registry import (
    GeographicRegistry, Region, RegionLevel, RegionState,
)
from world_system.world_memory.consolidator_base import ConsolidatorBase
from world_system.world_memory.layer3_manager import Layer3Manager
from world_system.world_memory.consolidators.regional_synthesis import (
    RegionalSynthesisConsolidator,
)
from world_system.world_memory.consolidators.cross_domain import (
    CrossDomainConsolidator,
)
from world_system.world_memory.consolidators.player_identity import (
    PlayerIdentityConsolidator,
)
from world_system.world_memory.consolidators.faction_narrative import (
    FactionNarrativeConsolidator,
)
from world_system.world_memory.prompt_assembler import PromptAssembler
from world_system.world_memory.tag_assignment import assign_higher_layer_tags


# ── Test Helpers ────────────────────────────────────────────────────


def _make_l2_event(category: str, severity: str = "minor",
                   narrative: str = "", locality_id: str = "",
                   district_id: str = "", province_id: str = "",
                   game_time: float = 100.0,
                   extra_tags: list = None) -> dict:
    """Create a Layer 2 event dict as stored in LayerStore."""
    tags = []
    if locality_id:
        tags.append(f"locality:{locality_id}")
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


def _setup_geo_registry():
    """Create a test geographic hierarchy with districts and localities."""
    GeographicRegistry.reset()
    geo = GeographicRegistry.get_instance()

    realm = Region(
        region_id="realm_0", name="Test Realm",
        level=RegionLevel.REALM,
        bounds_x1=-100, bounds_y1=-100, bounds_x2=100, bounds_y2=100,
    )
    geo.regions["realm_0"] = realm
    geo.realm = realm

    province = Region(
        region_id="nation_1", name="Northern Kingdom",
        level=RegionLevel.PROVINCE,
        bounds_x1=-100, bounds_y1=-100, bounds_x2=100, bounds_y2=0,
        parent_id="realm_0",
    )
    geo.regions["nation_1"] = province
    realm.child_ids.append("nation_1")

    district = Region(
        region_id="region_1", name="Western Frontier",
        level=RegionLevel.DISTRICT,
        bounds_x1=-100, bounds_y1=-100, bounds_x2=0, bounds_y2=0,
        parent_id="nation_1",
    )
    geo.regions["region_1"] = district
    province.child_ids.append("region_1")

    # Add localities
    for i, (name, x1, y1) in enumerate([
        ("Whispering Woods", -100, -100),
        ("Iron Hills", -50, -100),
        ("Crystal Lake", -100, -50),
    ]):
        loc = Region(
            region_id=f"province_{i}",
            name=name,
            level=RegionLevel.LOCALITY,
            bounds_x1=x1, bounds_y1=y1,
            bounds_x2=x1 + 49, bounds_y2=y1 + 49,
            parent_id="region_1",
        )
        geo.regions[loc.region_id] = loc
        district.child_ids.append(loc.region_id)

    return geo


def _setup_layer_store():
    """Create an in-memory LayerStore."""
    return LayerStore(db_path=":memory:")


# ══════════════════════════════════════════════════════════════════
# 1. ConsolidatedEvent Tests
# ══════════════════════════════════════════════════════════════════


class TestConsolidatedEvent(unittest.TestCase):

    def test_create_factory(self):
        event = ConsolidatedEvent.create(
            narrative="Test synthesis.",
            category="regional_synthesis",
            severity="moderate",
            source_interpretation_ids=["id1", "id2", "id3"],
            game_time=100.0,
            affected_district_ids=["region_1"],
        )
        self.assertTrue(event.consolidation_id)
        self.assertEqual(event.narrative, "Test synthesis.")
        self.assertEqual(event.category, "regional_synthesis")
        self.assertEqual(event.severity, "moderate")
        self.assertEqual(len(event.source_interpretation_ids), 3)
        self.assertEqual(event.created_at, 100.0)

    def test_severity_order(self):
        self.assertLess(SEVERITY_ORDER["minor"], SEVERITY_ORDER["moderate"])
        self.assertLess(SEVERITY_ORDER["moderate"], SEVERITY_ORDER["significant"])
        self.assertLess(SEVERITY_ORDER["significant"], SEVERITY_ORDER["major"])
        self.assertLess(SEVERITY_ORDER["major"], SEVERITY_ORDER["critical"])


# ══════════════════════════════════════════════════════════════════
# 2. ConsolidatorBase Tests
# ══════════════════════════════════════════════════════════════════


class TestConsolidatorBase(unittest.TestCase):

    def test_build_xml_data_block(self):
        consolidator = RegionalSynthesisConsolidator()
        events = [
            _make_l2_event("combat_kills", "moderate",
                          "Player killed 15 wolves.", "province_0"),
            _make_l2_event("gathering_regional", "minor",
                          "Player gathered 8 oak.", "province_0"),
            _make_l2_event("gathering_regional", "significant",
                          "Player gathered 45 iron.", "province_1"),
        ]
        localities = {"province_0": "Whispering Woods",
                     "province_1": "Iron Hills"}

        xml = consolidator.build_xml_data_block(
            events, "Western Frontier", localities)

        self.assertIn('<district name="Western Frontier">', xml)
        self.assertIn('<locality name="Whispering Woods">', xml)
        self.assertIn('<locality name="Iron Hills">', xml)
        self.assertIn("Player killed 15 wolves.", xml)
        self.assertIn('category="combat_kills"', xml)

    def test_determine_severity(self):
        consolidator = RegionalSynthesisConsolidator()

        # Single minor → minor
        events = [_make_l2_event("combat", "minor")]
        self.assertEqual(consolidator.determine_severity(events), "minor")

        # One major → major
        events = [_make_l2_event("combat", "major"),
                  _make_l2_event("gathering", "minor")]
        self.assertEqual(consolidator.determine_severity(events), "major")

        # 3+ categories boost by 1
        events = [
            _make_l2_event("combat", "moderate"),
            _make_l2_event("gathering", "minor"),
            _make_l2_event("crafting", "minor"),
        ]
        self.assertEqual(consolidator.determine_severity(events), "significant")

    def test_determine_severity_empty(self):
        consolidator = RegionalSynthesisConsolidator()
        self.assertEqual(consolidator.determine_severity([]), "minor")


# ══════════════════════════════════════════════════════════════════
# 3. Regional Synthesis Consolidator Tests
# ══════════════════════════════════════════════════════════════════


class TestRegionalSynthesis(unittest.TestCase):

    def setUp(self):
        self.consolidator = RegionalSynthesisConsolidator()
        self.geo = _setup_geo_registry()

    def tearDown(self):
        GeographicRegistry.reset()

    def test_is_applicable_needs_district(self):
        events = [_make_l2_event("combat", district_id="region_1")] * 3
        self.assertFalse(self.consolidator.is_applicable(events, ""))
        self.assertTrue(self.consolidator.is_applicable(events, "region_1"))

    def test_is_applicable_3_events(self):
        events = [_make_l2_event("combat")] * 3
        self.assertTrue(self.consolidator.is_applicable(events, "region_1"))

    def test_is_applicable_2_categories(self):
        events = [
            _make_l2_event("combat_kills"),
            _make_l2_event("gathering_regional"),
        ]
        self.assertTrue(self.consolidator.is_applicable(events, "region_1"))

    def test_is_applicable_1_event_1_category(self):
        events = [_make_l2_event("combat")]
        self.assertFalse(self.consolidator.is_applicable(events, "region_1"))

    def test_consolidate_produces_event(self):
        events = [
            _make_l2_event("combat_kills", "moderate",
                          "Player killed 10 wolves.", "province_0",
                          district_id="region_1"),
            _make_l2_event("gathering_regional", "minor",
                          "Player gathered 20 iron.", "province_1",
                          district_id="region_1"),
            _make_l2_event("combat_kills", "minor",
                          "Player killed 5 goblins.", "province_0",
                          district_id="region_1"),
        ]

        geo_context = {
            "district_name": "Western Frontier",
            "province_name": "Northern Kingdom",
            "localities": [
                {"id": "province_0", "name": "Whispering Woods"},
                {"id": "province_1", "name": "Iron Hills"},
            ],
        }

        result = self.consolidator.consolidate(
            events, "region_1", geo_context, game_time=200.0)

        self.assertIsNotNone(result)
        self.assertEqual(result.category, "regional_synthesis")
        self.assertIn("Western Frontier", result.narrative)
        self.assertEqual(len(result.source_interpretation_ids), 3)
        self.assertIn("region_1", result.affected_district_ids)

    def test_consolidate_empty(self):
        result = self.consolidator.consolidate(
            [], "region_1", {}, game_time=100.0)
        self.assertIsNone(result)


# ══════════════════════════════════════════════════════════════════
# 4. Cross-Domain Consolidator Tests
# ══════════════════════════════════════════════════════════════════


class TestCrossDomain(unittest.TestCase):

    def setUp(self):
        self.consolidator = CrossDomainConsolidator()

    def test_is_applicable_needs_2_domains(self):
        events = [_make_l2_event("combat_kills"),
                  _make_l2_event("combat_style")]
        self.assertFalse(self.consolidator.is_applicable(events, "region_1"))

        events = [_make_l2_event("combat_kills"),
                  _make_l2_event("gathering_regional")]
        self.assertTrue(self.consolidator.is_applicable(events, "region_1"))

    def test_is_applicable_needs_district(self):
        events = [_make_l2_event("combat"),
                  _make_l2_event("gathering")]
        self.assertFalse(self.consolidator.is_applicable(events, ""))

    def test_consolidate_finds_pattern(self):
        events = [
            _make_l2_event("combat_kills", "moderate",
                          "Player killed 15 wolves.", "province_0",
                          district_id="region_1"),
            _make_l2_event("gathering_regional", "significant",
                          "Player gathered 45 iron.", "province_0",
                          district_id="region_1"),
        ]

        result = self.consolidator.consolidate(
            events, "region_1",
            {"district_name": "Western Frontier",
             "province_name": "Northern Kingdom",
             "localities": [{"id": "province_0", "name": "Whispering Woods"}]},
            game_time=200.0)

        self.assertIsNotNone(result)
        self.assertEqual(result.category, "cross_domain")
        self.assertIn("region_1", result.affected_district_ids)
        # Should detect co-location
        self.assertIn("Whispering Woods", result.narrative)

    def test_consolidate_single_domain(self):
        events = [_make_l2_event("combat_kills"),
                  _make_l2_event("combat_style")]
        result = self.consolidator.consolidate(
            events, "region_1", {"district_name": "Test"}, 100.0)
        self.assertIsNone(result)


# ══════════════════════════════════════════════════════════════════
# 5. Player Identity Consolidator Tests
# ══════════════════════════════════════════════════════════════════


class TestPlayerIdentity(unittest.TestCase):

    def setUp(self):
        self.consolidator = PlayerIdentityConsolidator()

    def test_is_applicable_global_only(self):
        events = [_make_l2_event("combat")] * 5
        # Must NOT run for district-scoped calls
        self.assertFalse(self.consolidator.is_applicable(events, "region_1"))
        # Runs for global (empty district_id)
        self.assertTrue(self.consolidator.is_applicable(events, ""))

    def test_is_applicable_needs_5_events(self):
        events = [_make_l2_event("combat")] * 4
        self.assertFalse(self.consolidator.is_applicable(events, ""))

    def test_consolidate_combat_focused(self):
        events = [
            _make_l2_event("combat_kills", district_id="region_1"),
            _make_l2_event("combat_kills", district_id="region_1"),
            _make_l2_event("combat_kills", district_id="region_1"),
            _make_l2_event("combat_kills", district_id="region_1"),
            _make_l2_event("gathering_regional", district_id="region_1"),
        ]

        result = self.consolidator.consolidate(
            events, "", {}, game_time=200.0)

        self.assertIsNotNone(result)
        self.assertEqual(result.category, "player_identity")
        self.assertIn("combatant", result.narrative)

    def test_consolidate_mixed(self):
        events = [
            _make_l2_event("combat_kills"),
            _make_l2_event("gathering_regional"),
            _make_l2_event("crafting_smithing"),
            _make_l2_event("exploration_territory"),
            _make_l2_event("social_quests"),
        ]

        result = self.consolidator.consolidate(
            events, "", {}, game_time=200.0)

        self.assertIsNotNone(result)
        # Multiple domains should show up
        self.assertIn("player_identity", result.category)


# ══════════════════════════════════════════════════════════════════
# 6. Faction Narrative Consolidator Tests
# ══════════════════════════════════════════════════════════════════


class TestFactionNarrative(unittest.TestCase):

    def setUp(self):
        self.consolidator = FactionNarrativeConsolidator()

    def test_is_applicable_global_only(self):
        events = [
            _make_l2_event("social_quests", extra_tags=["npc:combat_trainer"]),
            _make_l2_event("social_quests", extra_tags=["npc:combat_trainer"]),
            _make_l2_event("social_npc", extra_tags=["npc:combat_trainer"]),
        ]
        self.assertFalse(self.consolidator.is_applicable(events, "region_1"))
        self.assertTrue(self.consolidator.is_applicable(events, ""))

    def test_is_applicable_needs_faction_events(self):
        # No faction tags
        events = [_make_l2_event("combat_kills")] * 5
        self.assertFalse(self.consolidator.is_applicable(events, ""))

    def test_consolidate_faction_activity(self):
        events = [
            _make_l2_event("social_quests", "minor",
                          "Player completed quest.", extra_tags=["npc:combat_trainer"]),
            _make_l2_event("social_npc", "minor",
                          "Player talked to combat trainer.",
                          extra_tags=["npc:combat_trainer"]),
            _make_l2_event("social_quests", "moderate",
                          "Player accepted quest.",
                          extra_tags=["npc:mysterious_trader"]),
        ]

        result = self.consolidator.consolidate(
            events, "", {}, game_time=200.0)

        self.assertIsNotNone(result)
        self.assertEqual(result.category, "faction_narrative")
        # Should mention factions
        has_faction_tag = any(t.startswith("faction:")
                            for t in result.affects_tags)
        self.assertTrue(has_faction_tag)


# ══════════════════════════════════════════════════════════════════
# 7. Layer3Manager Tests
# ══════════════════════════════════════════════════════════════════


class TestLayer3Manager(unittest.TestCase):

    def setUp(self):
        Layer3Manager.reset()
        GeographicRegistry.reset()
        self.geo = _setup_geo_registry()
        self.store = _setup_layer_store()
        self.manager = Layer3Manager.get_instance()
        self.manager.initialize(
            layer_store=self.store,
            geo_registry=self.geo,
            wms_ai=None,
        )

    def tearDown(self):
        Layer3Manager.reset()
        GeographicRegistry.reset()

    def test_initialization(self):
        self.assertTrue(self.manager._initialized)
        self.assertEqual(len(self.manager._consolidators), 4)

    def test_trigger_interval(self):
        # Should not trigger before interval
        for i in range(14):
            self.manager.on_layer2_created(
                _make_l2_event("combat", district_id="region_1"))
            self.assertFalse(self.manager.should_run())

        # 15th event triggers
        self.manager.on_layer2_created(
            _make_l2_event("combat", district_id="region_1"))
        self.assertTrue(self.manager.should_run())

    def test_district_tracking(self):
        self.manager.on_layer2_created(
            _make_l2_event("combat", district_id="region_1"))
        self.manager.on_layer2_created(
            _make_l2_event("combat", district_id="region_2"))

        self.assertIn("region_1", self.manager._districts_with_new_l2)
        self.assertIn("region_2", self.manager._districts_with_new_l2)

    def test_run_consolidation_resets_counter(self):
        for i in range(15):
            self.manager.on_layer2_created(
                _make_l2_event("combat", district_id="region_1"))

        self.manager.run_consolidation(game_time=200.0)
        self.assertEqual(self.manager._l2_events_since_last_run, 0)
        self.assertEqual(len(self.manager._districts_with_new_l2), 0)

    def test_stats(self):
        stats = self.manager.stats
        self.assertTrue(stats["initialized"])
        self.assertEqual(stats["consolidators"], 4)


# ══════════════════════════════════════════════════════════════════
# 8. Full Integration Pipeline Tests
# ══════════════════════════════════════════════════════════════════


class TestLayer3Integration(unittest.TestCase):

    def setUp(self):
        Layer3Manager.reset()
        GeographicRegistry.reset()
        self.geo = _setup_geo_registry()
        self.store = _setup_layer_store()
        self.manager = Layer3Manager.get_instance()
        self.manager.initialize(
            layer_store=self.store,
            geo_registry=self.geo,
            wms_ai=None,
        )

    def tearDown(self):
        Layer3Manager.reset()
        GeographicRegistry.reset()

    def _insert_l2_events(self, events):
        """Insert L2 events into LayerStore and notify manager."""
        for event in events:
            self.store.insert_event(
                layer=2,
                narrative=event["narrative"],
                game_time=event["game_time"],
                category=event["category"],
                severity=event["severity"],
                significance=event["severity"],
                tags=event["tags"],
                origin_ref=event["category"],
                event_id=event["id"],
            )
            self.manager.on_layer2_created(event)

    def test_full_pipeline_regional(self):
        """Test L2 events → trigger → regional synthesis → L3 stored."""
        events = [
            _make_l2_event("combat_kills", "moderate",
                          "Player killed 15 wolves.", "province_0",
                          "region_1", "nation_1", game_time=100.0),
            _make_l2_event("gathering_regional", "minor",
                          "Player gathered 20 iron.", "province_1",
                          "region_1", "nation_1", game_time=101.0),
            _make_l2_event("combat_kills", "minor",
                          "Player killed 5 goblins.", "province_0",
                          "region_1", "nation_1", game_time=102.0),
        ]

        # Insert L2 events
        self._insert_l2_events(events)

        # Need 15 total events to trigger — add more
        for i in range(12):
            extra = _make_l2_event(
                "combat_kills", "minor",
                f"Extra event {i}.", "province_0",
                "region_1", "nation_1", game_time=103.0 + i)
            self._insert_l2_events([extra])

        # Should have triggered
        self.assertTrue(self.manager.should_run())

        # Run consolidation
        created = self.manager.run_consolidation(game_time=200.0)
        self.assertGreater(created, 0)

        # Check L3 events stored in LayerStore
        stats = self.store.get_table_stats()
        self.assertGreater(stats.get("layer3_events", 0), 0)

    def test_full_pipeline_player_identity(self):
        """Test global player identity consolidation."""
        # Create diverse events across districts
        events = []
        for i in range(8):
            cat = ["combat_kills", "gathering_regional",
                   "crafting_smithing", "exploration_territory"][i % 4]
            events.append(_make_l2_event(
                cat, "minor", f"Event {i}.",
                "province_0", "region_1", "nation_1",
                game_time=100.0 + i))

        # Add enough to trigger (15 total)
        for i in range(7):
            events.append(_make_l2_event(
                "combat_kills", "minor", f"Extra {i}.",
                "province_0", "region_1", "nation_1",
                game_time=110.0 + i))

        self._insert_l2_events(events)
        self.assertTrue(self.manager.should_run())

        created = self.manager.run_consolidation(game_time=200.0)
        # Should have at least regional + cross_domain + player_identity
        self.assertGreater(created, 0)

    def test_l3_event_has_correct_tags(self):
        """Verify L3 events have Layer 3 tag categories."""
        events = []
        for i in range(15):
            cat = "combat_kills" if i % 2 == 0 else "gathering_regional"
            events.append(_make_l2_event(
                cat, "minor", f"Event {i}.",
                "province_0", "region_1", "nation_1",
                game_time=100.0 + i))

        self._insert_l2_events(events)
        created = self.manager.run_consolidation(game_time=200.0)

        if created > 0:
            # Read L3 events from store
            c = self.store.connection
            rows = c.execute(
                "SELECT tags_json FROM layer3_events LIMIT 1"
            ).fetchall()
            if rows:
                tags = json.loads(rows[0]["tags_json"])
                # Should have consolidator tag
                has_consolidator = any(t.startswith("consolidator:")
                                      for t in tags)
                self.assertTrue(has_consolidator)


# ══════════════════════════════════════════════════════════════════
# 9. PromptAssembler Multi-File Loading Tests
# ══════════════════════════════════════════════════════════════════


class TestPromptAssemblerL3(unittest.TestCase):

    def setUp(self):
        self.assembler = PromptAssembler()
        self.assembler.load()

    def test_l3_fragments_loaded(self):
        """Verify L3 fragments file was loaded."""
        self.assertTrue(len(self.assembler._l3_fragments) > 0)
        self.assertIn("_l3_core", self.assembler._l3_fragments)
        self.assertIn("_l3_output", self.assembler._l3_fragments)

    def test_get_l3_fragment(self):
        core = self.assembler.get_l3_fragment("_l3_core")
        self.assertIn("chronicler", core.lower())

    def test_assemble_l3_regional(self):
        prompt = self.assembler.assemble_l3(
            "regional_synthesis",
            data_block='<district name="Test">events here</district>')

        self.assertIn("chronicler", prompt.system.lower())
        self.assertIn("Test", prompt.user)
        self.assertGreater(prompt.token_estimate, 0)

    def test_assemble_l3_uses_example(self):
        prompt = self.assembler.assemble_l3("regional_synthesis")
        # Should include the example fragment
        self.assertIn("EXAMPLE", prompt.system)

    def test_l2_fragments_still_work(self):
        """Ensure L2 assembly is not broken."""
        prompt = self.assembler.assemble(
            ["domain:combat", "species:wolf_grey"],
            data_block="Count: 15")
        self.assertIn("combat", prompt.system.lower())


# ══════════════════════════════════════════════════════════════════
# 10. Tag Assignment for Layer 3 Tests
# ══════════════════════════════════════════════════════════════════


class TestLayer3TagAssignment(unittest.TestCase):

    def test_assign_higher_layer_tags_layer3(self):
        origin_tags = [
            ["domain:combat", "species:wolf", "locality:province_0",
             "district:region_1", "significance:moderate"],
            ["domain:gathering", "resource:iron", "locality:province_1",
             "district:region_1", "significance:minor"],
        ]

        result = assign_higher_layer_tags(
            layer=3,
            origin_event_tags=origin_tags,
            significance="significant",
            layer_specific_tags=[
                "consolidator:regional_synthesis",
                "intensity:moderate",
                "sentiment:neutral",
            ],
        )

        # Should have inherited tags (without old significance)
        self.assertIn("domain:combat", result)
        self.assertIn("domain:gathering", result)
        # Should have new significance
        self.assertIn("significance:significant", result)
        # Should NOT have old significance
        self.assertNotIn("significance:moderate", result)
        self.assertNotIn("significance:minor", result)
        # Should have layer-specific tags
        self.assertIn("consolidator:regional_synthesis", result)
        self.assertIn("intensity:moderate", result)

    def test_tag_merge_frequency_ordering(self):
        """Tags appearing in more origin events should come first."""
        origin_tags = [
            ["domain:combat", "species:wolf"],
            ["domain:combat", "species:goblin"],
            ["domain:combat", "resource:iron"],
        ]

        result = assign_higher_layer_tags(
            layer=3,
            origin_event_tags=origin_tags,
            significance="minor",
        )

        # domain:combat appears in all 3 → should be first
        combat_idx = result.index("domain:combat")
        for tag in ["species:wolf", "species:goblin", "resource:iron"]:
            if tag in result:
                self.assertLess(combat_idx, result.index(tag))


# ══════════════════════════════════════════════════════════════════
# 11. LayerStore Layer 3 Table Tests
# ══════════════════════════════════════════════════════════════════


class TestLayerStoreL3(unittest.TestCase):

    def setUp(self):
        self.store = _setup_layer_store()

    def test_layer3_tables_exist(self):
        stats = self.store.get_table_stats()
        self.assertIn("layer3_events", stats)
        self.assertIn("layer3_tags", stats)

    def test_insert_and_query_l3(self):
        event_id = self.store.insert_event(
            layer=3,
            narrative="Test synthesis.",
            game_time=100.0,
            category="regional_synthesis",
            severity="moderate",
            significance="moderate",
            tags=["district:region_1", "consolidator:regional_synthesis",
                  "intensity:moderate"],
            origin_ref='["l2_id_1", "l2_id_2"]',
        )

        # Query by district tag
        results = self.store.query_by_tags(
            layer=3,
            tags=["district:region_1"],
            match_all=True,
        )
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["narrative"], "Test synthesis.")
        self.assertEqual(results[0]["category"], "regional_synthesis")

    def test_l3_tag_junction(self):
        self.store.insert_event(
            layer=3,
            narrative="Test.",
            game_time=100.0,
            category="cross_domain",
            severity="minor",
            significance="minor",
            tags=["district:region_1", "domain:combat", "domain:gathering"],
        )

        # Query by multiple tags
        results = self.store.query_by_tags(
            layer=3,
            tags=["district:region_1", "domain:combat"],
            match_all=True,
        )
        self.assertEqual(len(results), 1)

        # Query with match_all=False (OR)
        results = self.store.query_by_tags(
            layer=3,
            tags=["district:region_1", "district:region_2"],
            match_all=False,
        )
        self.assertEqual(len(results), 1)


# ══════════════════════════════════════════════════════════════════
# 12. Game Date Utility Tests
# ══════════════════════════════════════════════════════════════════


class TestGameDate(unittest.TestCase):

    def test_game_day(self):
        from world_system.world_memory.game_date import game_day, CYCLE_LENGTH
        self.assertEqual(game_day(0.0), 0)
        self.assertEqual(game_day(1439.9), 0)   # Just before day 1
        self.assertEqual(game_day(1440.0), 1)   # Exactly day 1
        self.assertEqual(game_day(2880.0), 2)   # Day 2
        self.assertEqual(game_day(43200.0), 30) # Day 30 = month boundary

    def test_game_month(self):
        from world_system.world_memory.game_date import game_month, CYCLE_LENGTH
        self.assertEqual(game_month(0.0), 0)
        self.assertEqual(game_month(43200.0), 1)       # Day 30 = month 1
        self.assertEqual(game_month(43199.0), 0)       # Day 29 = month 0

    def test_date_stamp(self):
        from world_system.world_memory.game_date import date_stamp
        stamp = date_stamp(46080.0)  # Day 32
        self.assertEqual(stamp["game_day"], 32)
        self.assertEqual(stamp["game_month"], 1)
        self.assertEqual(stamp["day_in_month"], 2)

    def test_format_relative_today(self):
        from world_system.world_memory.game_date import format_relative
        self.assertEqual(format_relative(100.0, 100.0), "today")
        self.assertEqual(format_relative(100.0, 1000.0), "today")  # Same day

    def test_format_relative_days(self):
        from world_system.world_memory.game_date import format_relative, CYCLE_LENGTH
        # 3 days ago
        event_time = 0.0
        current_time = 3 * CYCLE_LENGTH
        self.assertEqual(format_relative(event_time, current_time), "3 days ago")

    def test_format_relative_months(self):
        from world_system.world_memory.game_date import format_relative, CYCLE_LENGTH
        # 2 months and 5 days ago
        event_time = 0.0
        current_time = 65 * CYCLE_LENGTH  # 65 days = 2 months + 5 days
        self.assertEqual(format_relative(event_time, current_time),
                         "2 months and 5 days ago")

    def test_format_relative_exact_month(self):
        from world_system.world_memory.game_date import format_relative, CYCLE_LENGTH
        event_time = 0.0
        current_time = 30 * CYCLE_LENGTH  # Exactly 1 month
        self.assertEqual(format_relative(event_time, current_time),
                         "1 month ago")

    def test_format_date_label(self):
        from world_system.world_memory.game_date import format_date_label, CYCLE_LENGTH
        self.assertEqual(format_date_label(0.0), "Day 1")
        self.assertEqual(format_date_label(CYCLE_LENGTH), "Day 2")
        self.assertEqual(format_date_label(31 * CYCLE_LENGTH), "Month 2, Day 2")


# ══════════════════════════════════════════════════════════════════
# 13. LLM Tag Extraction Tests
# ══════════════════════════════════════════════════════════════════


class TestLLMTagExtraction(unittest.TestCase):

    def test_narration_result_has_tags(self):
        from world_system.world_memory.wms_ai import NarrationResult
        result = NarrationResult(
            text="Test narrative.",
            tags=["sentiment:dangerous", "trend:increasing"],
        )
        self.assertEqual(len(result.tags), 2)
        self.assertIn("sentiment:dangerous", result.tags)

    def test_prompt_includes_tag_categories(self):
        """L3 prompt must include tag category reference."""
        assembler = PromptAssembler()
        assembler.load()
        prompt = assembler.assemble_l3("regional_synthesis", "test data")
        # System prompt should include tag categories
        self.assertIn("sentiment", prompt.system)
        self.assertIn("trend", prompt.system)
        self.assertIn("intensity", prompt.system)
        # Output instruction should ask for JSON
        self.assertIn("JSON", prompt.user)
        self.assertIn("tags", prompt.user)


# ══════════════════════════════════════════════════════════════════
# 14. LayerStore game_day Column Tests
# ══════════════════════════════════════════════════════════════════


class TestLayerStoreGameDay(unittest.TestCase):

    def setUp(self):
        self.store = _setup_layer_store()

    def test_l2_event_has_game_day(self):
        from world_system.world_memory.game_date import CYCLE_LENGTH
        # Insert event at day 5
        game_time = 5 * CYCLE_LENGTH
        self.store.insert_event(
            layer=2, narrative="Day 5 event.", game_time=game_time,
            category="combat", severity="minor", significance="minor",
            tags=["domain:combat"], origin_ref="test", real_time=0.0)

        c = self.store.connection
        row = c.execute("SELECT game_day FROM layer2_events LIMIT 1").fetchone()
        self.assertEqual(row["game_day"], 5)

    def test_l3_event_has_game_day(self):
        from world_system.world_memory.game_date import CYCLE_LENGTH
        game_time = 10 * CYCLE_LENGTH
        self.store.insert_event(
            layer=3, narrative="Day 10 consolidation.", game_time=game_time,
            category="regional_synthesis", severity="minor",
            significance="minor", tags=["district:test"])

        c = self.store.connection
        row = c.execute("SELECT game_day FROM layer3_events LIMIT 1").fetchone()
        self.assertEqual(row["game_day"], 10)

    def test_game_day_zero_for_early_events(self):
        self.store.insert_event(
            layer=2, narrative="Early.", game_time=0.0,
            category="combat", severity="minor", significance="minor",
            tags=[], origin_ref="", real_time=0.0)

        c = self.store.connection
        row = c.execute("SELECT game_day FROM layer2_events LIMIT 1").fetchone()
        self.assertEqual(row["game_day"], 0)


if __name__ == "__main__":
    unittest.main()

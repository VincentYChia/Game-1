"""Tests for Pass 1 + Pass 2 orphan detection (§7.3)."""

from __future__ import annotations

import tempfile
import unittest

from world_system.content_registry.content_registry import ContentRegistry
from world_system.content_registry.orphan_detector import (
    validate_against_registry,
)


class OrphanDetectorTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.game_root = tempfile.TemporaryDirectory()
        self.addCleanup(self.game_root.cleanup)
        ContentRegistry.reset()
        self.registry = ContentRegistry.get_instance()
        self.registry.initialize(
            save_dir=self.tmp.name, game_root=self.game_root.name
        )

    def tearDown(self) -> None:
        ContentRegistry.reset()


class TestPass1(OrphanDetectorTestCase):
    def test_pass1_catches_bad_material_ref(self) -> None:
        hostile = {
            "enemyId": "wolf_ashen",
            "name": "Ashen Wolf",
            "tier": 3,
            "biome": "tundra",
            "drops": [{"material_id": "does_not_exist"}],
        }
        orphans = validate_against_registry(
            hostile, plan_id="p1", tool_name="hostiles",
            registry=self.registry,
        )
        self.assertEqual(orphans, ["does_not_exist"])

    def test_pass1_accepts_same_plan_staged_ref(self) -> None:
        # First stage the material, then check a hostile that refs it.
        self.registry.stage_content(
            "materials",
            {
                "materialId": "ashen_pelt",
                "name": "Ashen Pelt",
                "tier": 2,
            },
            plan_id="p1",
            source_bundle_id="b1",
        )
        hostile = {
            "enemyId": "wolf_ashen",
            "tier": 3,
            "biome": "tundra",
            "drops": [{"material_id": "ashen_pelt"}],
        }
        orphans = validate_against_registry(
            hostile, plan_id="p1", tool_name="hostiles",
            registry=self.registry,
        )
        self.assertEqual(orphans, [])

    def test_pass1_accepts_live_ref_from_different_plan(self) -> None:
        self.registry.stage_content(
            "materials",
            {"materialId": "iron_ore", "name": "Iron Ore", "tier": 1},
            plan_id="prior_plan",
            source_bundle_id="b",
        )
        self.registry.commit("prior_plan")

        hostile = {
            "enemyId": "goblin",
            "tier": 1,
            "drops": [{"material_id": "iron_ore"}],
        }
        orphans = validate_against_registry(
            hostile, plan_id="new_plan", tool_name="hostiles",
            registry=self.registry,
        )
        self.assertEqual(orphans, [])

    def test_pass1_unknown_tool_returns_empty(self) -> None:
        orphans = validate_against_registry(
            {"id": "x"}, "p1", "not_a_real_tool",
            registry=self.registry,
        )
        self.assertEqual(orphans, [])

    def test_pass1_no_registry_returns_empty(self) -> None:
        hostile = {
            "enemyId": "wolf",
            "tier": 1,
            "drops": [{"material_id": "anything"}],
        }
        orphans = validate_against_registry(
            hostile, "p1", "hostiles", registry=None,
        )
        self.assertEqual(orphans, [])

    def test_pass1_skips_duplicate_orphan_ids(self) -> None:
        hostile = {
            "enemyId": "h",
            "tier": 1,
            "drops": [
                {"material_id": "missing_one"},
                {"material_id": "missing_one"},
            ],
        }
        orphans = validate_against_registry(
            hostile, "p1", "hostiles", registry=self.registry,
        )
        self.assertEqual(orphans, ["missing_one"])

    def test_pass1_title_unlocks_skill_orphan(self) -> None:
        title = {
            "titleId": "icewalker",
            "category": "combat",
            "tier": "novice",
            "unlocks_skills": ["phantom_skill"],
        }
        orphans = validate_against_registry(
            title, "p1", "titles", registry=self.registry,
        )
        self.assertEqual(orphans, ["phantom_skill"])


class TestPass2(OrphanDetectorTestCase):
    def test_pass2_empty_when_no_xrefs(self) -> None:
        self.assertEqual(self.registry.find_orphans(), [])

    def test_pass2_reports_orphan_after_rollback_of_target(self) -> None:
        # Stage material + hostile in same plan, rollback material
        # while leaving xref — not realistic for atomic rollback,
        # but we exercise the pass 2 path by manually inserting xref.
        self.registry.stage_xref(
            src_type="hostiles",
            src_id="wolf_ashen",
            ref_type="materials",
            ref_id="ghost_material",
            relationship="drops",
            plan_id="p1",
        )
        orphans = self.registry.find_orphans()
        self.assertEqual(len(orphans), 1)
        self.assertEqual(orphans[0]["ref_id"], "ghost_material")
        self.assertEqual(orphans[0]["relationship"], "drops")

    def test_pass2_passes_when_target_is_staged(self) -> None:
        self.registry.stage_content(
            "materials",
            {"materialId": "ashen_pelt", "tier": 2, "name": "Pelt"},
            plan_id="p1",
            source_bundle_id="b",
        )
        self.registry.stage_content(
            "hostiles",
            {
                "enemyId": "wolf_ashen",
                "tier": 3,
                "drops": [{"material_id": "ashen_pelt"}],
            },
            plan_id="p1",
            source_bundle_id="b",
        )
        self.assertEqual(self.registry.find_orphans("p1"), [])

    def test_pass2_scoped_to_plan_id(self) -> None:
        # Plan A has a missing ref; plan B has a clean ref.
        self.registry.stage_xref(
            "hostiles", "hA", "materials", "missing_A", "drops", "p_A",
        )
        self.registry.stage_content(
            "materials",
            {"materialId": "m_B", "tier": 1},
            plan_id="p_B", source_bundle_id="b",
        )
        self.registry.stage_xref(
            "hostiles", "hB", "materials", "m_B", "drops", "p_B",
        )

        orphans_A = self.registry.find_orphans("p_A")
        orphans_B = self.registry.find_orphans("p_B")
        self.assertEqual(len(orphans_A), 1)
        self.assertEqual(orphans_A[0]["ref_id"], "missing_A")
        self.assertEqual(orphans_B, [])


if __name__ == "__main__":
    unittest.main()

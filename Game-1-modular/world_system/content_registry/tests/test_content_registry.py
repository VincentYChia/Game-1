"""Tests for :class:`ContentRegistry` — the public API facade."""

from __future__ import annotations

import os
import tempfile
import unittest

from world_system.content_registry.content_registry import ContentRegistry


def _material_payload(mat_id: str, tier: int = 2) -> dict:
    return {
        "materialId": mat_id,
        "name": mat_id.replace("_", " ").title(),
        "tier": tier,
        "category": "metal",
        "rarity": "uncommon",
        "biome": "tundra",
    }


def _hostile_payload(
    hostile_id: str, tier: int = 3, drops: list = None
) -> dict:
    return {
        "enemyId": hostile_id,
        "name": hostile_id.replace("_", " ").title(),
        "tier": tier,
        "biome": "tundra",
        "drops": [{"material_id": m} for m in (drops or [])],
        "skills": [],
    }


def _skill_payload(skill_id: str) -> dict:
    return {
        "skillId": skill_id,
        "name": skill_id.replace("_", " ").title(),
        "tags": ["frost"],
    }


def _title_payload(title_id: str, unlocks: list = None) -> dict:
    return {
        "titleId": title_id,
        "name": title_id,
        "category": "combat",
        "tier": "novice",
        "unlocks_skills": list(unlocks or []),
    }


class ContentRegistryTestCase(unittest.TestCase):
    """Common setUp / tearDown — one fresh registry per test."""

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


class TestInitialization(ContentRegistryTestCase):
    def test_singleton(self) -> None:
        r1 = ContentRegistry.get_instance()
        r2 = ContentRegistry.get_instance()
        self.assertIs(r1, r2)

    def test_initialize_creates_db_in_save_dir(self) -> None:
        self.assertTrue(self.registry.initialized)
        self.assertIsNotNone(self.registry.db_path)
        self.assertTrue(os.path.exists(self.registry.db_path))

    def test_query_on_uninitialized_registry_degrades_gracefully(self) -> None:
        ContentRegistry.reset()
        r = ContentRegistry.get_instance()
        self.assertFalse(r.initialized)
        self.assertEqual(r.list_live("materials"), [])
        self.assertEqual(r.counts()["materials"], 0)
        self.assertFalse(r.exists("materials", "anything"))

    def test_stage_on_uninitialized_raises(self) -> None:
        ContentRegistry.reset()
        r = ContentRegistry.get_instance()
        with self.assertRaises(RuntimeError):
            r.stage_content(
                "materials", _material_payload("x"), "p", "b"
            )


class TestStaging(ContentRegistryTestCase):
    def test_stage_material_returns_content_id(self) -> None:
        cid = self.registry.stage_content(
            "materials", _material_payload("ashen_ore"),
            plan_id="p1", source_bundle_id="b1",
        )
        self.assertEqual(cid, "ashen_ore")

    def test_staged_row_visible_only_with_include_staged(self) -> None:
        self.registry.stage_content(
            "materials", _material_payload("ashen_ore"), "p1", "b1"
        )
        self.assertTrue(
            self.registry.exists(
                "materials", "ashen_ore", include_staged=True
            )
        )
        self.assertFalse(
            self.registry.exists(
                "materials", "ashen_ore", include_staged=False
            )
        )

    def test_stage_unknown_tool_raises(self) -> None:
        with self.assertRaises(ValueError):
            self.registry.stage_content(
                "fake_unknown_tool", {"questId": "q1"}, "p1", "b1"
            )

    def test_stage_missing_id_raises(self) -> None:
        with self.assertRaises(ValueError):
            self.registry.stage_content(
                "materials", {"name": "no id"}, "p1", "b1"
            )

    def test_stage_extracts_hostile_drops_as_xref(self) -> None:
        self.registry.stage_content(
            "materials", _material_payload("ashen_pelt"), "p1", "b1"
        )
        self.registry.stage_content(
            "hostiles",
            _hostile_payload("wolf_ashen", drops=["ashen_pelt"]),
            "p1", "b1",
        )
        staged = self.registry.list_staged_by_plan("p1")
        self.assertEqual(len(staged["hostiles"]), 1)
        self.assertEqual(len(staged["materials"]), 1)
        # Orphan scan should find zero orphans for this plan.
        self.assertEqual(self.registry.find_orphans("p1"), [])


class TestCommitRollback(ContentRegistryTestCase):
    def test_commit_flips_staged_to_live(self) -> None:
        self.registry.stage_content(
            "materials", _material_payload("ashen_ore"), "p1", "b1"
        )
        result = self.registry.commit("p1")
        self.assertEqual(result["counts"]["materials"], 1)
        self.assertTrue(
            self.registry.exists(
                "materials", "ashen_ore", include_staged=False
            )
        )

    def test_commit_writes_generated_file(self) -> None:
        self.registry.stage_content(
            "materials", _material_payload("ashen_ore"), "p1", "b1"
        )
        result = self.registry.commit("p1")
        self.assertIn("materials", result["files"])
        path = result["files"]["materials"]
        self.assertTrue(os.path.exists(path))
        # Correct directory name.
        self.assertIn("items.JSON", path)
        # Sacred file is not touched — our generated file has the
        # "-generated-" marker.
        self.assertIn("-generated-", path)

    def test_commit_noop_for_empty_plan_does_not_raise(self) -> None:
        result = self.registry.commit("no_such_plan")
        self.assertEqual(result["files"], {})
        self.assertEqual(
            sum(result["counts"].values()), 0
        )

    def test_rollback_removes_staged_rows_and_xrefs(self) -> None:
        self.registry.stage_content(
            "materials", _material_payload("ashen_pelt"), "p1", "b1"
        )
        self.registry.stage_content(
            "hostiles",
            _hostile_payload("wolf_ashen", drops=["ashen_pelt"]),
            "p1", "b1",
        )
        counts = self.registry.rollback("p1")
        self.assertEqual(counts["materials"], 1)
        self.assertEqual(counts["hostiles"], 1)
        self.assertEqual(counts["content_xref"], 1)
        self.assertFalse(
            self.registry.exists(
                "materials", "ashen_pelt", include_staged=True
            )
        )

    def test_commit_then_list_live(self) -> None:
        self.registry.stage_content(
            "materials", _material_payload("m1"), "p1", "b1"
        )
        self.registry.stage_content(
            "materials", _material_payload("m2"), "p1", "b1"
        )
        self.registry.commit("p1")
        live = self.registry.list_live("materials")
        self.assertEqual(len(live), 2)
        ids = {r["content_id"] for r in live}
        self.assertEqual(ids, {"m1", "m2"})


class TestCountsAndLineage(ContentRegistryTestCase):
    def test_counts_returns_all_tools_when_none(self) -> None:
        self.registry.stage_content(
            "materials", _material_payload("m1"), "p1", "b1"
        )
        self.registry.commit("p1")
        counts = self.registry.counts()
        self.assertEqual(counts["materials"], 1)
        self.assertEqual(counts["hostiles"], 0)
        self.assertEqual(counts["skills"], 0)

    def test_counts_with_filter(self) -> None:
        self.registry.stage_content(
            "materials", _material_payload("m_tundra", tier=2), "p1", "b1"
        )
        self.registry.commit("p1")
        self.assertEqual(
            self.registry.counts("materials", {"biome": "tundra"})["materials"],
            1,
        )
        self.assertEqual(
            self.registry.counts("materials", {"biome": "desert"})["materials"],
            0,
        )

    def test_lineage_walks_content_to_plan_to_bundle(self) -> None:
        self.registry.stage_content(
            "materials", _material_payload("ashen_ore"),
            plan_id="plan_42", source_bundle_id="bundle_99",
        )
        self.registry.commit("plan_42")
        lin = self.registry.lineage("ashen_ore")
        self.assertEqual(lin["content_id"], "ashen_ore")
        self.assertEqual(lin["plan_id"], "plan_42")
        self.assertEqual(lin["source_bundle_id"], "bundle_99")
        self.assertEqual(lin["tool_name"], "materials")
        self.assertFalse(lin["staged"])

    def test_lineage_unknown_returns_empty(self) -> None:
        self.assertEqual(self.registry.lineage("not_real"), {})


class TestStats(ContentRegistryTestCase):
    def test_stats_before_init(self) -> None:
        ContentRegistry.reset()
        r = ContentRegistry.get_instance()
        s = r.stats
        self.assertFalse(s["initialized"])

    def test_stats_reflects_live_and_staged(self) -> None:
        self.registry.stage_content(
            "materials", _material_payload("m1"), "p1", "b1"
        )
        self.registry.stage_content(
            "materials", _material_payload("m2"), "p2", "b2"
        )
        self.registry.commit("p1")
        s = self.registry.stats
        self.assertTrue(s["initialized"])
        self.assertEqual(s["live_counts"]["materials"], 1)
        self.assertEqual(s["staged_rows"], 1)


class TestBalancePassthrough(ContentRegistryTestCase):
    def test_balance_check_surfaces_obvious_outlier(self) -> None:
        reason = self.registry.balance_check(
            field_value=1_000_000, tier=1, field_name="attack"
        )
        self.assertIsNotNone(reason)

    def test_balance_check_accepts_reasonable_value(self) -> None:
        # Nominal T1 weaponDamage = 10. Value of 10 is inside [5, 20].
        reason = self.registry.balance_check(
            field_value=10, tier=1, field_name="attack"
        )
        self.assertIsNone(reason)


if __name__ == "__main__":
    unittest.main()

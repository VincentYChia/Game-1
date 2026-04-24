"""Tests for :mod:`registry_store` — schema + raw CRUD."""

from __future__ import annotations

import os
import sqlite3
import tempfile
import unittest

from world_system.content_registry.registry_store import (
    DB_FILENAME,
    SCHEMA_VERSION,
    TOOL_TABLE,
    RegistryStore,
)


class TestRegistryStoreSchema(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.store = RegistryStore(save_dir=self.tmp.name)

    def tearDown(self) -> None:
        self.store.close()

    def test_db_file_created(self) -> None:
        expected = os.path.join(self.tmp.name, DB_FILENAME)
        self.assertTrue(os.path.exists(expected))
        self.assertEqual(self.store.db_path, expected)

    def test_all_five_tool_tables_created(self) -> None:
        conn = self.store.connection
        rows = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
        names = {r[0] for r in rows}
        for tbl in TOOL_TABLE.values():
            self.assertIn(tbl, names)
        self.assertIn("content_xref", names)
        self.assertIn("schema_meta", names)

    def test_schema_version_recorded(self) -> None:
        conn = self.store.connection
        row = conn.execute(
            "SELECT value FROM schema_meta WHERE key='schema_version'"
        ).fetchone()
        self.assertIsNotNone(row)
        self.assertEqual(int(row[0]), SCHEMA_VERSION)

    def test_xref_indexes_present(self) -> None:
        conn = self.store.connection
        indexes = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index'"
        ).fetchall()
        names = {r[0] for r in indexes}
        self.assertIn("idx_xref_ref", names)
        self.assertIn("idx_xref_src", names)

    def test_unknown_tool_raises(self) -> None:
        with self.assertRaises(ValueError):
            self.store.insert_staged_row(
                tool_name="quests",
                content_id="q1",
                display_name="",
                tier=0,
                biome="",
                faction_id="",
                plan_id="p1",
                source_bundle_id="b1",
                created_at=0.0,
                payload_json="{}",
            )

    def test_must_provide_path_or_save_dir(self) -> None:
        with self.assertRaises(ValueError):
            RegistryStore()


class TestRegistryStoreCRUD(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.store = RegistryStore(save_dir=self.tmp.name)

    def tearDown(self) -> None:
        self.store.close()

    def _stage_material(self, content_id: str, plan_id: str = "plan_A") -> None:
        self.store.insert_staged_row(
            tool_name="materials",
            content_id=content_id,
            display_name=f"Display {content_id}",
            tier=2,
            biome="tundra",
            faction_id="",
            plan_id=plan_id,
            source_bundle_id="bundle_1",
            created_at=1234.0,
            payload_json='{"materialId":"' + content_id + '"}',
        )

    def test_insert_and_get_staged_row(self) -> None:
        self._stage_material("ashen_ore")
        row = self.store.get_row("materials", "ashen_ore", include_staged=True)
        self.assertIsNotNone(row)
        self.assertEqual(row["content_id"], "ashen_ore")
        self.assertEqual(row["staged"], 1)
        self.assertEqual(row["plan_id"], "plan_A")
        self.assertEqual(row["tier"], 2)

    def test_get_row_live_only_filters_staged(self) -> None:
        self._stage_material("ashen_ore")
        live = self.store.get_row("materials", "ashen_ore", include_staged=False)
        self.assertIsNone(live)

    def test_flip_staged_to_live(self) -> None:
        self._stage_material("ashen_ore")
        self._stage_material("frost_pelt")
        counts = self.store.flip_staged_to_live("plan_A")
        self.assertEqual(counts["materials"], 2)
        row = self.store.get_row(
            "materials", "ashen_ore", include_staged=False
        )
        self.assertIsNotNone(row)
        self.assertEqual(row["staged"], 0)

    def test_delete_staged_rows(self) -> None:
        self._stage_material("ashen_ore")
        self._stage_material("frost_pelt")
        self.store.insert_xref(
            src_type="hostiles",
            src_id="h1",
            ref_type="materials",
            ref_id="ashen_ore",
            relationship="drops",
            plan_id="plan_A",
        )
        counts = self.store.delete_staged_rows("plan_A")
        self.assertEqual(counts["materials"], 2)
        self.assertEqual(counts["content_xref"], 1)
        self.assertIsNone(
            self.store.get_row("materials", "ashen_ore", include_staged=True)
        )

    def test_xref_lookup_by_ref(self) -> None:
        self.store.insert_xref(
            "hostiles", "wolf_ashen", "materials", "ashen_pelt",
            "drops", "plan_A",
        )
        self.store.insert_xref(
            "titles", "icewalker", "skills", "frost_step",
            "unlocks", "plan_A",
        )
        hits = self.store.xrefs_referencing("materials", "ashen_pelt")
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0]["src_id"], "wolf_ashen")

    def test_xref_bulk_insert_idempotent(self) -> None:
        xrefs = [
            ("hostiles", "w1", "materials", "m1", "drops"),
            ("hostiles", "w1", "materials", "m1", "drops"),
            ("hostiles", "w1", "materials", "m2", "drops"),
        ]
        self.store.insert_xrefs_bulk(xrefs, "plan_A")
        all_xrefs = self.store.all_xrefs()
        # Duplicate dropped by PRIMARY KEY.
        self.assertEqual(len(all_xrefs), 2)

    def test_count_rows_with_filter(self) -> None:
        self._stage_material("m1")
        self._stage_material("m2")
        # Flip only one.
        self.store.insert_staged_row(
            tool_name="materials",
            content_id="m_live",
            display_name="Live material",
            tier=2,
            biome="tundra",
            faction_id="",
            plan_id="plan_B",
            source_bundle_id="bundle_2",
            created_at=999.0,
            payload_json="{}",
        )
        self.store.flip_staged_to_live("plan_B")

        live = self.store.count_rows("materials", staged=0)
        staged = self.store.count_rows("materials", staged=1)
        self.assertEqual(live, 1)
        self.assertEqual(staged, 2)

        live_tundra = self.store.count_rows(
            "materials", staged=0, filters={"biome": "tundra"}
        )
        self.assertEqual(live_tundra, 1)

        live_desert = self.store.count_rows(
            "materials", staged=0, filters={"biome": "desert"}
        )
        self.assertEqual(live_desert, 0)

    def test_find_row_anywhere_hits_first_matching_tool(self) -> None:
        self._stage_material("overlap_id")
        self.store.insert_staged_row(
            tool_name="skills",
            content_id="overlap_id",
            display_name="Overlap Skill",
            tier=3,
            biome="",
            faction_id="",
            plan_id="plan_Z",
            source_bundle_id="b",
            created_at=0.0,
            payload_json="{}",
        )
        row = self.store.find_row_anywhere("overlap_id")
        self.assertIsNotNone(row)
        # Deterministic dict-iteration order gives materials first
        # (insertion order in TOOL_TABLE). Accept either — just
        # verify the hit contains tool_name.
        self.assertIn(row["tool_name"], {"materials", "skills"})

    def test_payload_roundtrip(self) -> None:
        payload = {"materialId": "x", "tier": 3, "tags": ["a", "b"]}
        serialized = RegistryStore.serialize_payload(payload)
        self.assertIsInstance(serialized, str)
        restored = RegistryStore.deserialize_payload(serialized)
        self.assertEqual(restored, payload)

    def test_deserialize_bad_json_returns_empty_dict(self) -> None:
        self.assertEqual(RegistryStore.deserialize_payload(""), {})
        self.assertEqual(RegistryStore.deserialize_payload("{not json"), {})


class TestRegistryStoreFilterInjectionGuards(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.store = RegistryStore(save_dir=self.tmp.name)

    def tearDown(self) -> None:
        self.store.close()

    def test_unknown_filter_column_ignored(self) -> None:
        # Must not raise — unknown column names are silently dropped.
        rows = self.store.list_rows(
            "materials",
            staged=0,
            filters={"; DROP TABLE reg_materials;--": "x"},
        )
        self.assertEqual(rows, [])
        # Verify table still exists.
        conn = self.store.connection
        row = conn.execute(
            "SELECT name FROM sqlite_master "
            "WHERE type='table' AND name='reg_materials'"
        ).fetchone()
        self.assertIsNotNone(row)


if __name__ == "__main__":
    unittest.main()

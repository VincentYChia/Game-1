"""Tests for :class:`GeneratedFileWriter` — atomic file emission on commit."""

from __future__ import annotations

import json
import os
import tempfile
import unittest

from world_system.content_registry.generated_file_writer import (
    GeneratedFileWriter,
)
from world_system.content_registry.xref_rules import (
    SACRED_OUTPUT_PREFIX,
    SACRED_OUTPUT_SUBDIR,
    SACRED_TOP_LEVEL_KEY,
)


def _row(content_id: str, payload: dict, tool: str = "materials") -> dict:
    return {
        "content_id": content_id,
        "tool_name": tool,
        "payload_json": json.dumps(payload),
    }


class TestGeneratedFileWriter(unittest.TestCase):
    def setUp(self) -> None:
        self.root = tempfile.TemporaryDirectory()
        self.addCleanup(self.root.cleanup)
        self.writer = GeneratedFileWriter(
            game_root=self.root.name, timestamp="2026-04-23T00-00-00"
        )

    def test_writes_materials_file_to_correct_directory(self) -> None:
        rows = [_row("ashen_ore", {"materialId": "ashen_ore", "tier": 2})]
        files = self.writer.write_commit_batch(
            {"materials": rows}, plan_id="p1"
        )
        self.assertIn("materials", files)
        path = files["materials"]
        self.assertTrue(os.path.exists(path))
        # Lives inside items.JSON/.
        self.assertIn(SACRED_OUTPUT_SUBDIR["materials"], path)
        self.assertIn(SACRED_OUTPUT_PREFIX["materials"], path)

    def test_generated_filename_has_generated_marker(self) -> None:
        rows = [_row("m1", {"materialId": "m1"})]
        files = self.writer.write_commit_batch(
            {"materials": rows}, plan_id="p1"
        )
        path = files["materials"]
        name = os.path.basename(path)
        self.assertIn("-generated-", name)

    def test_writes_correct_top_level_key(self) -> None:
        payload = {"materialId": "m1", "name": "Test", "tier": 2}
        rows = [_row("m1", payload)]
        files = self.writer.write_commit_batch(
            {"materials": rows}, "p1"
        )
        with open(files["materials"], "r", encoding="utf-8") as f:
            doc = json.load(f)
        top_key = SACRED_TOP_LEVEL_KEY["materials"]
        self.assertIn(top_key, doc)
        self.assertEqual(len(doc[top_key]), 1)
        self.assertEqual(doc[top_key][0]["materialId"], "m1")
        self.assertIn("metadata", doc)
        self.assertTrue(doc["metadata"]["generated"])
        self.assertEqual(doc["metadata"]["plan_id"], "p1")

    def test_does_not_touch_existing_sacred_files(self) -> None:
        # Simulate sacred file existence.
        sacred_dir = os.path.join(
            self.root.name, SACRED_OUTPUT_SUBDIR["materials"]
        )
        os.makedirs(sacred_dir, exist_ok=True)
        sacred_path = os.path.join(sacred_dir, "items-materials-1.JSON")
        with open(sacred_path, "w", encoding="utf-8") as f:
            json.dump({"materials": [{"materialId": "sacred"}]}, f)

        rows = [_row("m1", {"materialId": "m1", "tier": 2})]
        self.writer.write_commit_batch({"materials": rows}, "p1")

        # Sacred file contents unchanged.
        with open(sacred_path, "r", encoding="utf-8") as f:
            doc = json.load(f)
        self.assertEqual(doc["materials"][0]["materialId"], "sacred")

    def test_empty_rows_skips_tool(self) -> None:
        files = self.writer.write_commit_batch(
            {"materials": [], "hostiles": []}, "p1"
        )
        self.assertEqual(files, {})

    def test_unknown_tool_ignored(self) -> None:
        rows = [_row("q1", {"id": "q1"}, tool="fake_unknown_tool")]
        files = self.writer.write_commit_batch(
            {"fake_unknown_tool": rows}, "p1"
        )
        self.assertEqual(files, {})

    def test_rollback_removes_created_files(self) -> None:
        rows = [_row("m1", {"materialId": "m1", "tier": 2})]
        files = self.writer.write_commit_batch(
            {"materials": rows}, "p1"
        )
        path = files["materials"]
        self.assertTrue(os.path.exists(path))
        removed = self.writer.rollback()
        self.assertEqual(removed, 1)
        self.assertFalse(os.path.exists(path))

    def test_rollback_idempotent(self) -> None:
        rows = [_row("m1", {"materialId": "m1", "tier": 2})]
        self.writer.write_commit_batch({"materials": rows}, "p1")
        self.writer.rollback()
        # Second rollback is a no-op (no files tracked).
        self.assertEqual(self.writer.rollback(), 0)

    def test_writes_all_five_tool_types(self) -> None:
        rows_by_tool = {
            "materials": [_row("m1", {"materialId": "m1"})],
            "hostiles": [_row("h1", {"enemyId": "h1"})],
            "nodes": [_row("n1", {"nodeId": "n1"})],
            "skills": [_row("s1", {"skillId": "s1"})],
            "titles": [_row("t1", {"titleId": "t1"})],
        }
        files = self.writer.write_commit_batch(rows_by_tool, "p1")
        self.assertEqual(set(files.keys()),
                         {"materials", "hostiles", "nodes", "skills", "titles"})
        for tool, path in files.items():
            self.assertTrue(os.path.exists(path))
            with open(path, "r", encoding="utf-8") as f:
                doc = json.load(f)
            self.assertIn(SACRED_TOP_LEVEL_KEY[tool], doc)

    def test_timestamp_preserved(self) -> None:
        self.assertEqual(self.writer.timestamp, "2026-04-23T00-00-00")


if __name__ == "__main__":
    unittest.main()

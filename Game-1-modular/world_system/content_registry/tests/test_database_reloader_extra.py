"""Tests for the npcs/quests/chunks reload-target additions to
:mod:`world_system.content_registry.database_reloader`.

The reloader maps tool names to ``(module_path, class_name,
method_candidates)``. The dispatcher now routes generated content to
the live game databases for npcs + quests
(:meth:`NPCDatabase.reload`) and chunks
(:meth:`ChunkTemplateDatabase.reload`).
"""

from __future__ import annotations

import os
import sys
import unittest

_this_dir = os.path.dirname(os.path.abspath(__file__))
_game_dir = os.path.dirname(os.path.dirname(os.path.dirname(_this_dir)))
if _game_dir not in sys.path:
    sys.path.insert(0, _game_dir)

from world_system.content_registry.database_reloader import (  # noqa: E402
    registered_targets,
    reload_for_tools,
)


class TestReloadTargetRegistration(unittest.TestCase):
    def test_npcs_registered(self) -> None:
        targets = registered_targets()
        self.assertIn("npcs", targets)
        npc_targets = targets["npcs"]
        self.assertEqual(len(npc_targets), 1)
        module_path, class_name, methods = npc_targets[0]
        self.assertEqual(module_path, "data.databases.npc_db")
        self.assertEqual(class_name, "NPCDatabase")
        self.assertIn("reload", methods)

    def test_quests_registered(self) -> None:
        targets = registered_targets()
        self.assertIn("quests", targets)
        quest_targets = targets["quests"]
        self.assertEqual(len(quest_targets), 1)
        module_path, class_name, methods = quest_targets[0]
        # NPCDatabase holds both npcs and quests in one cache, so
        # quests routes to the same target as npcs.
        self.assertEqual(module_path, "data.databases.npc_db")
        self.assertEqual(class_name, "NPCDatabase")

    def test_chunks_registered(self) -> None:
        """As of the chunks runtime-integration pass, ``chunks`` routes
        to :class:`ChunkTemplateDatabase` so generated biome templates
        land in the live registry post-commit."""
        targets = registered_targets()
        self.assertIn("chunks", targets)
        chunk_targets = targets["chunks"]
        self.assertEqual(len(chunk_targets), 1)
        module_path, class_name, methods = chunk_targets[0]
        self.assertEqual(module_path, "data.databases.chunk_template_db")
        self.assertEqual(class_name, "ChunkTemplateDatabase")
        self.assertIn("reload", methods)

    def test_originals_still_present(self) -> None:
        """The 5 original tools must remain registered even after we
        added the new ones."""
        targets = registered_targets()
        for tool in ("materials", "hostiles", "nodes", "skills", "titles"):
            self.assertIn(tool, targets)


class TestReloadForNPCsRoutes(unittest.TestCase):
    """Smoke test: reload_for_tools(["npcs"]) actually invokes
    NPCDatabase.reload (which is graceful even on missing files)."""

    def test_reload_npcs_invokes_database(self) -> None:
        # NPCDatabase.reload is a no-op when source files are absent
        # (it logs and keeps stale state) — this just confirms the
        # routing reaches the right class.
        results = reload_for_tools(["npcs"])
        self.assertIn("NPCDatabase", results)
        # Result is True if reload completed without raising.
        self.assertIsInstance(results["NPCDatabase"], bool)

    def test_reload_chunks_invokes_database(self) -> None:
        """ChunkTemplateDatabase.reload is graceful even when no
        Chunk-templates files are present — confirms routing reaches
        the right class."""
        results = reload_for_tools(["chunks"])
        self.assertIn("ChunkTemplateDatabase", results)
        self.assertIsInstance(results["ChunkTemplateDatabase"], bool)

    def test_reload_unknown_tool_logs_no_target_silently(self) -> None:
        """Unknown tool names should be ignored without crashing — the
        dispatcher's fallback path for any non-registered tool name."""
        results = reload_for_tools(["nonexistent_tool_xyz"])
        self.assertEqual(results, {})


if __name__ == "__main__":
    unittest.main()

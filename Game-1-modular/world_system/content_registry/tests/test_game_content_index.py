"""Tests for GameContentIndex + ContentRegistry.exists() sacred-awareness.

Deterministic (fake providers) — no game databases, no LLM.
"""
from __future__ import annotations

import os
import sys
import tempfile
import unittest

_this = os.path.dirname(os.path.abspath(__file__))
_modular = os.path.dirname(os.path.dirname(os.path.dirname(_this)))
if _modular not in sys.path:
    sys.path.insert(0, _modular)

from world_system.content_registry.content_registry import ContentRegistry  # noqa: E402
from world_system.content_registry.game_content_index import (  # noqa: E402
    GameContentIndex,
)


class TestGameContentIndex(unittest.TestCase):
    def _idx(self) -> GameContentIndex:
        return GameContentIndex(providers={
            "materials": lambda: {"iron_ore", "moors_copper_ore"},
            "hostiles": lambda: {"goblin"},
        })

    def test_exists(self):
        idx = self._idx()
        self.assertTrue(idx.exists("materials", "iron_ore"))
        self.assertFalse(idx.exists("materials", "nonexistent"))

    def test_canonical_for_folds_drift(self):
        idx = self._idx()
        self.assertEqual(idx.canonical_for("materials", "Iron-Ore"), "iron_ore")
        self.assertEqual(idx.canonical_for("materials", "IRON ORE"), "iron_ore")
        self.assertIsNone(idx.canonical_for("materials", "unrelated"))

    def test_unknown_tool_is_empty(self):
        self.assertEqual(self._idx().ids_for("skills"), set())

    def test_refresh_picks_up_new_invention(self):
        state = {"materials": {"a"}}
        idx = GameContentIndex(
            providers={"materials": lambda: set(state["materials"])})
        self.assertTrue(idx.exists("materials", "a"))
        # Simulate WES inventing + reloading "b".
        state["materials"] = {"a", "b"}
        self.assertFalse(idx.exists("materials", "b"))  # still cached
        idx.refresh(["materials"])
        self.assertTrue(idx.exists("materials", "b"))   # now in sync


class TestRegistryExistsViaIndex(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.mkdtemp(prefix="cr_idx_")
        ContentRegistry.reset()
        self.reg = ContentRegistry.get_instance()
        self.reg.initialize(save_dir=self._tmp, game_root=self._tmp)
        self.reg.set_game_index(GameContentIndex(providers={
            "materials": lambda: {"iron_ore"},
        }))

    def tearDown(self):
        ContentRegistry.reset()
        import shutil
        shutil.rmtree(self._tmp, ignore_errors=True)

    def test_exists_resolves_sacred_via_index(self):
        # Not in the registry store (empty tempdir), but the game holds it.
        self.assertTrue(self.reg.exists("materials", "iron_ore"))
        self.assertFalse(self.reg.exists("materials", "not_a_material"))

    def test_known_ids_exposed_for_dispatcher(self):
        self.assertIn("iron_ore", self.reg.known_ids("materials"))
        self.assertEqual(self.reg.known_ids("skills"), set())


if __name__ == "__main__":
    unittest.main()

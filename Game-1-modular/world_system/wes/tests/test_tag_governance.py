"""Tests for WES content-tag governance (deterministic — no game DBs, no LLM)."""
from __future__ import annotations

import os
import sys
import unittest

_this = os.path.dirname(os.path.abspath(__file__))
_modular = os.path.dirname(os.path.dirname(os.path.dirname(_this)))
if _modular not in sys.path:
    sys.path.insert(0, _modular)

from world_system.wes.tag_governance import govern_content_tags  # noqa: E402
from world_system.content_registry.game_content_index import (  # noqa: E402
    GameContentIndex,
)


class TestTagGovernance(unittest.TestCase):
    def test_keeps_valid_drops_unknown_routes_new(self):
        content = {"materialId": "x", "metadata": {
            "tags": ["metal", "invented_junk", "NEW:trade-conflict"]}}
        out, kept, dropped, proposed = govern_content_tags(
            content, "materials", {"metal", "precious"})
        self.assertEqual(out["metadata"]["tags"], ["metal"])   # kept
        self.assertEqual(dropped, ["invented_junk"])           # invented -> drop
        self.assertEqual(proposed, ["trade-conflict"])         # NEW: -> review
        self.assertIn("metal", kept)

    def test_top_level_tags_for_skills(self):
        content = {"skillId": "s", "tags": ["fire", "made_up"]}
        out, kept, dropped, proposed = govern_content_tags(
            content, "skills", {"fire"})
        self.assertEqual(out["tags"], ["fire"])
        self.assertEqual(dropped, ["made_up"])

    def test_empty_vocab_is_noop(self):
        content = {"metadata": {"tags": ["anything"]}}
        out, kept, dropped, proposed = govern_content_tags(
            content, "materials", set())
        self.assertEqual(out["metadata"]["tags"], ["anything"])
        self.assertEqual((kept, dropped, proposed), ([], [], []))


class TestTagsFor(unittest.TestCase):
    def test_tags_for_harvests_and_refreshes(self):
        state = {"materials": {"metal", "durable"}}
        idx = GameContentIndex(
            providers={"materials": lambda: {"iron_ore"}},
            tag_providers={"materials": lambda: set(state["materials"])},
        )
        # Harvested tags are present (union also folds in TagRegistry effect
        # tags, so assert membership rather than exact equality).
        harvested = idx.tags_for("materials")
        self.assertIn("metal", harvested)
        self.assertIn("durable", harvested)
        # A designer-approved new tag becomes valid after refresh.
        state["materials"] = {"metal", "durable", "verdigris"}
        self.assertNotIn("verdigris", idx.tags_for("materials"))  # cached
        idx.refresh(["materials"])
        self.assertIn("verdigris", idx.tags_for("materials"))


if __name__ == "__main__":
    unittest.main()

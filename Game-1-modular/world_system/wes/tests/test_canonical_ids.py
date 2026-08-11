"""Tests for canonical-id coordination (approach A + normalizer fallback).

Reproduces the exact failure found in the first real-LLM end-to-end run
(2026-08-11): a node references its material by a different id than the
material tool actually emitted, so the cross-ref orphaned and the plan rolled
back. These are pure/deterministic — no LLM.
"""
from __future__ import annotations

import os
import sys
import unittest

_this = os.path.dirname(os.path.abspath(__file__))
_modular = os.path.dirname(os.path.dirname(os.path.dirname(_this)))
if _modular not in sys.path:
    sys.path.insert(0, _modular)

from world_system.wes.canonical_ids import (  # noqa: E402
    enforce_content_id,
    normalize_id,
    prune_orphan_refs,
    reconcile_refs,
    slugify,
)


class TestNormalize(unittest.TestCase):
    def test_folds_case_spaces_hyphens_punct(self):
        for raw in ["Moors Copper Ore", "moors-copper-ore",
                    "  Moors_Copper_Ore ", "moors--copper  ore",
                    "Moors, Copper. Ore!"]:
            self.assertEqual(normalize_id(raw), "moors_copper_ore")

    def test_non_string_empty(self):
        self.assertEqual(normalize_id(None), "")
        self.assertEqual(normalize_id(123), "")

    def test_slugify_caps_words(self):
        s = slugify("new T4 copper variant unique to ashfall moors verdigris")
        self.assertEqual(s.count("_"), 3)  # max_words=4 -> 3 separators


class TestReconcile(unittest.TestCase):
    def test_enforce_own_id(self):
        node = {"resourceId": "whatever", "drops": []}
        enforce_content_id(node, "nodes", "the_seam")
        self.assertEqual(node["resourceId"], "the_seam")

    def test_intended_ref_binds_to_single_parent(self):
        # Node depends_on a material whose ACTUAL id is moors_copper_ore, but
        # the node emitted a drop referencing the planner's intended name.
        node = {
            "resourceId": "seam",
            "drops": [{"materialId": "ashfall_verdigris_copper",
                       "quantity": "many", "chance": "high"}],
        }
        rec = reconcile_refs(
            node, "nodes",
            canonical_id="seam",
            parent_ids_by_tool={"materials": ["moors_copper_ore"]},
            live_ids_by_tool={"materials": {"moors_copper_ore"}},
            intended_ref_ids={"ashfall_verdigris_copper"},
        )
        self.assertEqual(
            rec["content"]["drops"][0]["materialId"], "moors_copper_ore")
        self.assertIn("ashfall_verdigris_copper -> moors_copper_ore",
                      rec["resolved"])
        self.assertEqual(rec["orphans"], [])

    def test_invented_extra_stays_orphan(self):
        # The intended material binds; a tool-invented extra drop does NOT get
        # force-mapped onto the parent — it stays a genuine orphan.
        node = {
            "resourceId": "seam",
            "drops": [
                {"materialId": "ashfall_verdigris_copper"},  # intended
                {"materialId": "copper_dust_vial"},          # invented
            ],
        }
        rec = reconcile_refs(
            node, "nodes",
            canonical_id="seam",
            parent_ids_by_tool={"materials": ["moors_copper_ore"]},
            live_ids_by_tool={"materials": {"moors_copper_ore"}},
            intended_ref_ids={"ashfall_verdigris_copper"},
        )
        mids = {d["materialId"] for d in rec["content"]["drops"]}
        self.assertIn("moors_copper_ore", mids)
        self.assertIn("copper_dust_vial", mids)         # untouched
        self.assertEqual(rec["orphans"], ["copper_dust_vial"])

    def test_normalizer_resolves_formatting_drift(self):
        # A ref that differs only by formatting from a co-emitted id resolves
        # even when it is NOT flagged intended (pure normalizer path).
        node = {
            "resourceId": "seam",
            "drops": [{"materialId": "Moors-Copper-Ore"}],
        }
        rec = reconcile_refs(
            node, "nodes",
            canonical_id="seam",
            parent_ids_by_tool={},
            live_ids_by_tool={"materials": {"moors_copper_ore"}},
            intended_ref_ids=set(),
        )
        self.assertEqual(
            rec["content"]["drops"][0]["materialId"], "moors_copper_ore")
        self.assertEqual(rec["orphans"], [])

    def test_chunk_dict_key_refs_rewritten(self):
        # Chunk cross-refs live as dict KEYS (resourceDensity / enemySpawns).
        chunk = {
            "chunkType": "ashfall_moors",
            "resourceDensity": {"the_seam_wrong": {"density": "high"}},
            "enemySpawns": {"the_raider_wrong": {"tier": 4}},
        }
        rec = reconcile_refs(
            chunk, "chunks",
            canonical_id="ashfall_moors",
            parent_ids_by_tool={"nodes": ["real_seam"],
                                "hostiles": ["real_raider"]},
            live_ids_by_tool={"nodes": {"real_seam"},
                              "hostiles": {"real_raider"}},
            intended_ref_ids={"the_seam_wrong", "the_raider_wrong"},
        )
        self.assertIn("real_seam", rec["content"]["resourceDensity"])
        self.assertIn("real_raider", rec["content"]["enemySpawns"])
        self.assertEqual(rec["orphans"], [])


class TestPrune(unittest.TestCase):
    def test_prunes_invented_drop_keeps_resolved(self):
        node = {
            "resourceId": "seam",
            "drops": [
                {"materialId": "moors_copper_ore"},  # resolved — keep
                {"materialId": "volcanic_stone"},    # invented — prune
            ],
        }
        out, removed = prune_orphan_refs(node, "nodes", {"volcanic_stone"})
        mids = {d["materialId"] for d in out["drops"]}
        self.assertEqual(mids, {"moors_copper_ore"})
        self.assertIn("volcanic_stone", removed)
        self.assertEqual(out["resourceId"], "seam")  # own id untouched

    def test_prunes_chunk_dict_key_refs(self):
        chunk = {
            "chunkType": "moors",
            "resourceDensity": {"real_seam": {"density": "high"},
                                "ash_residue": {"density": "low"}},
            "enemySpawns": {"real_raider": {"tier": 4},
                            "invented_scout": {"tier": 2}},
        }
        out, removed = prune_orphan_refs(
            chunk, "chunks", {"ash_residue", "invented_scout"})
        self.assertEqual(set(out["resourceDensity"]), {"real_seam"})
        self.assertEqual(set(out["enemySpawns"]), {"real_raider"})
        self.assertEqual(set(removed), {"ash_residue", "invented_scout"})

    def test_no_orphans_is_noop(self):
        node = {"resourceId": "seam", "drops": [{"materialId": "x"}]}
        out, removed = prune_orphan_refs(node, "nodes", set())
        self.assertEqual(out, node)
        self.assertEqual(removed, [])


if __name__ == "__main__":
    unittest.main()

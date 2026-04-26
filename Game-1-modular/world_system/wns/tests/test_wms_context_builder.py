"""Tests for build_wms_brief — the WMS slice rendering for WNS prompts."""

from __future__ import annotations

import os
import sys
import unittest
from dataclasses import dataclass, field
from typing import List, Optional

_this_dir = os.path.dirname(os.path.abspath(__file__))
_game_dir = os.path.dirname(os.path.dirname(os.path.dirname(_this_dir)))
if _game_dir not in sys.path:
    sys.path.insert(0, _game_dir)

from world_system.wns.wms_context_builder import (  # noqa: E402
    build_wms_brief,
    DEFAULT_CHAR_BUDGET,
    EMPTY_RENDER,
    TRUNCATION_MARKER,
)


# ── Test doubles ───────────────────────────────────────────────────────

@dataclass
class FakeInterp:
    interpretation_id: str
    narrative: str
    category: str = "combat"
    severity: str = "minor"
    affected_locality_ids: List[str] = field(default_factory=list)


@dataclass
class FakeRegion:
    region_id: str
    level_value: str  # mimics RegionLevel.value
    children: List["FakeRegion"] = field(default_factory=list)

    @property
    def level(self):
        # Mimic RegionLevel-like object with .value attribute
        return type("L", (), {"value": self.level_value})()


class FakeEventStore:
    def __init__(self, interpretations: List[FakeInterp]):
        self._interps = list(interpretations)

    def query_interpretations(self, *, limit: int = 50, **_kwargs):
        # Most-recent first (test fixtures are pre-sorted by caller).
        return list(self._interps[:limit])


class FakeRegistry:
    """Toy 6-tier registry. Children are pre-wired in __init__."""

    def __init__(self):
        # World w1 ⟵ nation n1 ⟵ region r1 ⟵ province p1 ⟵ district d1
        # ⟵ localities L1, L2, L3
        self.L1 = FakeRegion("L1", "locality")
        self.L2 = FakeRegion("L2", "locality")
        self.L3 = FakeRegion("L3", "locality")
        self.d1 = FakeRegion("d1", "district", [self.L1, self.L2, self.L3])
        self.d2 = FakeRegion("d2", "district", [])
        self.p1 = FakeRegion("p1", "province", [self.d1, self.d2])
        self.r1 = FakeRegion("r1", "region", [self.p1])
        self.n1 = FakeRegion("n1", "nation", [self.r1])
        self.w1 = FakeRegion("w1", "world", [self.n1])
        self._by_id = {
            r.region_id: r
            for r in (self.L1, self.L2, self.L3, self.d1, self.d2,
                      self.p1, self.r1, self.n1, self.w1)
        }

    def get_children(self, region_id: str):
        r = self._by_id.get(region_id)
        return list(r.children) if r else []


# ── Empty / degenerate paths ───────────────────────────────────────────

class TestEmptyPaths(unittest.TestCase):
    def test_empty_address_returns_empty(self) -> None:
        store = FakeEventStore([])
        out = build_wms_brief(firing_address="", event_store=store)
        self.assertEqual(out, "")

    def test_no_event_store_returns_empty(self) -> None:
        out = build_wms_brief(firing_address="locality:L1", event_store=None)
        self.assertEqual(out, "")

    def test_no_interpretations_returns_empty(self) -> None:
        store = FakeEventStore([])
        out = build_wms_brief(firing_address="locality:L1", event_store=store)
        self.assertEqual(out, "")

    def test_high_tier_without_registry_returns_empty(self) -> None:
        store = FakeEventStore([
            FakeInterp("i1", "Wolves prowl the moors.", affected_locality_ids=["L1"])
        ])
        out = build_wms_brief(
            firing_address="district:d1",
            event_store=store,
            geographic_registry=None,
        )
        self.assertEqual(out, "")

    def test_interpretation_with_no_locality_skipped(self) -> None:
        store = FakeEventStore([
            FakeInterp("i_global", "World shudders.", affected_locality_ids=[])
        ])
        out = build_wms_brief(firing_address="locality:L1", event_store=store)
        self.assertEqual(out, "")


# ── Locality-tier rendering ────────────────────────────────────────────

class TestLocalityTierRendering(unittest.TestCase):
    def test_single_interpretation_at_locality(self) -> None:
        store = FakeEventStore([
            FakeInterp("i1", "The wolves grow bold near the falls.",
                       category="combat", severity="moderate",
                       affected_locality_ids=["L1"])
        ])
        out = build_wms_brief(firing_address="locality:L1", event_store=store)
        self.assertIn("[moderate]", out)
        self.assertIn("combat:", out)
        self.assertIn("wolves grow bold", out)

    def test_unrelated_locality_filtered_out(self) -> None:
        store = FakeEventStore([
            FakeInterp("i1", "Wolves at L1.", affected_locality_ids=["L1"]),
            FakeInterp("i2", "Bandits at L2.", affected_locality_ids=["L2"]),
        ])
        out = build_wms_brief(firing_address="locality:L1", event_store=store)
        self.assertIn("Wolves", out)
        self.assertNotIn("Bandits", out)

    def test_multiple_interpretations_at_locality(self) -> None:
        store = FakeEventStore([
            FakeInterp(f"i{i}", f"Event {i}.", affected_locality_ids=["L1"])
            for i in range(5)
        ])
        out = build_wms_brief(firing_address="locality:L1", event_store=store)
        # All five should appear (well within budget)
        for i in range(5):
            self.assertIn(f"Event {i}.", out)


# ── High-tier rendering (descendant walk) ──────────────────────────────

class TestHighTierRendering(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = FakeRegistry()
        # One interp per locality under d1, plus one in unrelated d2.
        self.store = FakeEventStore([
            FakeInterp("iL1", "L1 event.", affected_locality_ids=["L1"]),
            FakeInterp("iL2", "L2 event.", affected_locality_ids=["L2"]),
            FakeInterp("iL3", "L3 event.", affected_locality_ids=["L3"]),
            FakeInterp("iLX", "Unrelated.", affected_locality_ids=["LX"]),
        ])

    def test_district_pulls_all_descendant_localities(self) -> None:
        out = build_wms_brief(
            firing_address="district:d1",
            event_store=self.store,
            geographic_registry=self.registry,
        )
        self.assertIn("L1 event.", out)
        self.assertIn("L2 event.", out)
        self.assertIn("L3 event.", out)
        self.assertNotIn("Unrelated.", out)

    def test_world_walks_full_tree(self) -> None:
        out = build_wms_brief(
            firing_address="world:w1",
            event_store=self.store,
            geographic_registry=self.registry,
        )
        # All four should match — they're all under world:w1 in some
        # district. (LX has no parent district registered in our toy
        # setup so it's skipped — good, that's the contract.)
        self.assertIn("L1 event.", out)
        self.assertIn("L2 event.", out)
        self.assertIn("L3 event.", out)

    def test_unknown_region_id_returns_empty(self) -> None:
        out = build_wms_brief(
            firing_address="district:does_not_exist",
            event_store=self.store,
            geographic_registry=self.registry,
        )
        self.assertEqual(out, "")


# ── Char budget enforcement ────────────────────────────────────────────

class TestCharBudget(unittest.TestCase):
    def test_budget_respected(self) -> None:
        long_narrative = "X" * 300
        store = FakeEventStore([
            FakeInterp(f"i{i}", long_narrative, affected_locality_ids=["L1"])
            for i in range(10)
        ])
        out = build_wms_brief(
            firing_address="locality:L1",
            event_store=store,
            char_budget=400,
        )
        # Length should be <= budget + truncation marker (already counted)
        self.assertLessEqual(
            len(out), 400 + len(TRUNCATION_MARKER) + 2,
            f"Output {len(out)} exceeded budget 400 (+ marker). out={out!r}",
        )

    def test_truncation_marker_appears_when_capped(self) -> None:
        long_narrative = "Y" * 200
        store = FakeEventStore([
            FakeInterp(f"i{i}", long_narrative, affected_locality_ids=["L1"])
            for i in range(20)
        ])
        out = build_wms_brief(
            firing_address="locality:L1",
            event_store=store,
            char_budget=300,
        )
        self.assertIn(TRUNCATION_MARKER.strip(), out)

    def test_per_line_cap_truncates_long_narratives(self) -> None:
        store = FakeEventStore([
            FakeInterp("i1", "Z" * 500, affected_locality_ids=["L1"])
        ])
        out = build_wms_brief(
            firing_address="locality:L1",
            event_store=store,
            char_budget=DEFAULT_CHAR_BUDGET,
            per_line_cap=50,
        )
        # The line should be truncated and end with ellipsis.
        self.assertIn("…", out)
        self.assertTrue(len(out) < 200, f"per-line cap not honored: {out!r}")

    def test_zero_budget_returns_empty(self) -> None:
        store = FakeEventStore([
            FakeInterp("i1", "anything", affected_locality_ids=["L1"])
        ])
        out = build_wms_brief(
            firing_address="locality:L1",
            event_store=store,
            char_budget=0,
        )
        self.assertEqual(out, "")


class TestRobustness(unittest.TestCase):
    def test_event_store_raises_returns_empty(self) -> None:
        class ExplodingStore:
            def query_interpretations(self, **_):
                raise RuntimeError("db gone")

        out = build_wms_brief(
            firing_address="locality:L1",
            event_store=ExplodingStore(),
        )
        self.assertEqual(out, "")

    def test_registry_get_children_raises_handled(self) -> None:
        class ExplodingRegistry:
            def get_children(self, _):
                raise RuntimeError("registry gone")

        store = FakeEventStore([
            FakeInterp("i1", "x", affected_locality_ids=["L1"])
        ])
        # Should return empty cleanly (descendant walk yields nothing).
        out = build_wms_brief(
            firing_address="district:d1",
            event_store=store,
            geographic_registry=ExplodingRegistry(),
        )
        self.assertEqual(out, "")

    def test_interp_missing_fields_uses_defaults(self) -> None:
        @dataclass
        class BareInterp:
            interpretation_id: str = "i"
            narrative: str = "A bare event."
            affected_locality_ids: List[str] = field(default_factory=lambda: ["L1"])

        store = FakeEventStore([BareInterp()])
        out = build_wms_brief(firing_address="locality:L1", event_store=store)
        self.assertIn("[minor]", out)
        self.assertIn("uncategorized:", out)


if __name__ == "__main__":
    unittest.main()

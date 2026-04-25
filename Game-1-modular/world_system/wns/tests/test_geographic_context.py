"""Tests for world_system.wns.geographic_context."""

from __future__ import annotations

import unittest
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional

from world_system.wns.geographic_context import (
    GeographicContext,
    TierBrief,
    build_geographic_context,
    parse_address,
    render_geo_context,
)


# ── Stub region/registry for tests (no WMS dep) ───────────────────────


class _StubLevel(Enum):
    LOCALITY = "locality"
    DISTRICT = "district"
    REGION = "region"
    NATION = "nation"
    WORLD = "world"


@dataclass
class _StubRegion:
    region_id: str
    name: str
    level: _StubLevel
    biome_primary: str = ""
    description: str = ""
    tags: List[str] = field(default_factory=list)
    parent_id: Optional[str] = None


@dataclass
class _StubRegistry:
    regions: Dict[str, _StubRegion]


def _make_test_registry() -> _StubRegistry:
    """Build a tiny moors-themed hierarchy for tests."""
    world = _StubRegion(
        region_id="world_root",
        name="The Known World",
        level=_StubLevel.WORLD,
        description="The explored world.",
        tags=["world"],
    )
    nation = _StubRegion(
        region_id="nation_stormguard",
        name="Stormguard",
        level=_StubLevel.NATION,
        biome_primary="temperate",
        description="A maritime nation balancing coastal trade and inland farming.",
        tags=["nation", "maritime"],
        parent_id="world_root",
    )
    region = _StubRegion(
        region_id="region_salt_moors",
        name="The Salt Moors",
        level=_StubLevel.REGION,
        biome_primary="salt-marsh",
        description="Wind-bitten heath where copper and brine meet.",
        tags=["moors", "harsh", "copper-trade"],
        parent_id="nation_stormguard",
    )
    district = _StubRegion(
        region_id="district_copperdocks",
        name="Copperdocks District",
        level=_StubLevel.DISTRICT,
        biome_primary="lowlands",
        description="The trade nerve of the salt moors — wharves and warehouses.",
        tags=["docks", "copper-trade"],
        parent_id="region_salt_moors",
    )
    locality = _StubRegion(
        region_id="tarmouth_copperdocks",
        name="Tarmouth Copperdocks",
        level=_StubLevel.LOCALITY,
        biome_primary="salt-marsh",
        description="A wharf town of brine and copper, recently swelled by trade pressure.",
        tags=["docks", "copper-trade", "mid-game"],
        parent_id="district_copperdocks",
    )
    return _StubRegistry(regions={
        r.region_id: r for r in [world, nation, region, district, locality]
    })


class TestParseAddress(unittest.TestCase):
    def test_well_formed_address(self) -> None:
        tier, rid = parse_address("locality:tarmouth_copperdocks")
        self.assertEqual(tier, "locality")
        self.assertEqual(rid, "tarmouth_copperdocks")

    def test_lowercases_tier(self) -> None:
        tier, _ = parse_address("Locality:tarmouth")
        self.assertEqual(tier, "locality")

    def test_missing_separator(self) -> None:
        tier, rid = parse_address("tarmouth")
        self.assertEqual(tier, "")
        self.assertEqual(rid, "")

    def test_extra_colons_kept_in_id(self) -> None:
        tier, rid = parse_address("region:foo:bar")
        self.assertEqual(tier, "region")
        self.assertEqual(rid, "foo:bar")

    def test_empty_input(self) -> None:
        self.assertEqual(parse_address(""), ("", ""))
        self.assertEqual(parse_address(None), ("", ""))


class TestBuildGeographicContext(unittest.TestCase):
    def test_full_chain_walk(self) -> None:
        reg = _make_test_registry()
        ctx = build_geographic_context("locality:tarmouth_copperdocks", reg)
        self.assertEqual(ctx.primary_tier, "locality")
        self.assertEqual(ctx.primary_id, "tarmouth_copperdocks")
        # Should walk locality -> district -> region -> nation -> world (5 tiers)
        self.assertEqual(len(ctx.tier_briefs), 5)
        tiers = [b.tier for b in ctx.tier_briefs]
        self.assertEqual(tiers, ["locality", "district", "region", "nation", "world"])
        # Names should be the human-readable ones, not region_ids
        self.assertEqual(ctx.tier_briefs[0].name, "Tarmouth Copperdocks")

    def test_rendered_includes_all_tiers(self) -> None:
        reg = _make_test_registry()
        ctx = build_geographic_context("locality:tarmouth_copperdocks", reg)
        for tier in ["locality", "district", "region", "nation", "world"]:
            self.assertIn(f"[{tier}]", ctx.rendered, f"{tier} missing from rendered")

    def test_rendered_includes_biome_and_description(self) -> None:
        reg = _make_test_registry()
        ctx = build_geographic_context("locality:tarmouth_copperdocks", reg)
        self.assertIn("biome=salt-marsh", ctx.rendered)
        self.assertIn("brine and copper", ctx.rendered)

    def test_rendered_includes_tags(self) -> None:
        reg = _make_test_registry()
        ctx = build_geographic_context("locality:tarmouth_copperdocks", reg)
        self.assertIn("docks", ctx.rendered)
        self.assertIn("copper-trade", ctx.rendered)


class TestGracefulDegradation(unittest.TestCase):
    def test_malformed_address(self) -> None:
        ctx = build_geographic_context("not_an_address", None)
        self.assertIn("malformed", ctx.rendered)
        self.assertEqual(ctx.tier_briefs, [])

    def test_no_registry(self) -> None:
        ctx = build_geographic_context("locality:tarmouth", None)
        self.assertEqual(ctx.primary_tier, "locality")
        self.assertEqual(ctx.primary_id, "tarmouth")
        self.assertIn("no registry", ctx.rendered)
        self.assertEqual(ctx.tier_briefs, [])

    def test_region_not_in_registry(self) -> None:
        reg = _make_test_registry()
        ctx = build_geographic_context("locality:nonexistent_place", reg)
        self.assertIn("not found", ctx.rendered)
        self.assertEqual(ctx.tier_briefs, [])

    def test_top_tier_has_no_parents(self) -> None:
        reg = _make_test_registry()
        ctx = build_geographic_context("world:world_root", reg)
        # Walking from world produces just world (no parent_id).
        self.assertEqual(len(ctx.tier_briefs), 1)
        self.assertEqual(ctx.tier_briefs[0].tier, "world")


class TestRenderGeoContext(unittest.TestCase):
    def test_empty_briefs_returns_empty_string(self) -> None:
        self.assertEqual(render_geo_context([]), "")

    def test_minimal_brief_renders(self) -> None:
        brief = TierBrief(tier="locality", region_id="x", name="Place")
        out = render_geo_context([brief])
        self.assertIn("[locality]", out)
        self.assertIn("Place", out)

    def test_brief_without_name_falls_back_to_id(self) -> None:
        brief = TierBrief(tier="locality", region_id="raw_id_xyz", name="")
        out = render_geo_context([brief])
        self.assertIn("raw_id_xyz", out)


if __name__ == "__main__":
    unittest.main()

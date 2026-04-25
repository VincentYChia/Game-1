"""Tests for affinity_shift_parser + affinity_resolver."""

from __future__ import annotations

import unittest
from typing import Any, List

from world_system.wns.affinity_resolver import (
    AffinityResolver,
    AffinityShiftRecord,
    KNOWN_SCOPE_TIERS,
    is_known_scope_tier,
    parse_effect,
    parse_scope,
)
from world_system.wns.affinity_shift_parser import (
    AffinityShift,
    parse_affinity_shifts,
)


class _StubFactionSystem:
    """Minimal stub recording calls."""

    def __init__(self, raises: bool = False) -> None:
        self.player_calls: List[Any] = []
        self.npc_calls: List[Any] = []
        self._raises = raises

    def adjust_player_affinity(self, *, player_id, tag, delta, game_time, source):
        if self._raises:
            raise RuntimeError("stub failure")
        self.player_calls.append({
            "player_id": player_id, "tag": tag, "delta": delta,
            "game_time": game_time, "source": source,
        })

    def adjust_npc_affinity_toward_player(self, *, npc_id, delta, game_time):
        if self._raises:
            raise RuntimeError("stub failure")
        self.npc_calls.append({
            "npc_id": npc_id, "delta": delta, "game_time": game_time,
        })


# ── Parser tests ─────────────────────────────────────────────────────


class TestAffinityShiftParser(unittest.TestCase):
    def test_no_blocks(self) -> None:
        shifts, cleaned = parse_affinity_shifts("Just a regular narrative.")
        self.assertEqual(shifts, [])
        self.assertEqual(cleaned, "Just a regular narrative.")

    def test_single_block(self) -> None:
        text = (
            "Pre. <AffinityShift>"
            "<Target>faction:moors_raiders</Target>"
            "<Scope>region:salt_moors</Scope>"
            "<Effect>standing_delta: -0.15</Effect>"
            "</AffinityShift> Post."
        )
        shifts, cleaned = parse_affinity_shifts(text)
        self.assertEqual(len(shifts), 1)
        self.assertEqual(shifts[0].target, "faction:moors_raiders")
        self.assertEqual(shifts[0].scope, "region:salt_moors")
        self.assertEqual(shifts[0].effect, "standing_delta: -0.15")
        self.assertNotIn("AffinityShift", cleaned)
        self.assertIn("Pre.", cleaned)
        self.assertIn("Post.", cleaned)

    def test_multiple_blocks(self) -> None:
        text = (
            "<AffinityShift>"
            "<Target>faction:a</Target><Scope>nation:x</Scope>"
            "<Effect>standing_delta: -0.10</Effect></AffinityShift>"
            "<AffinityShift>"
            "<Target>faction:a</Target><Scope>region:y</Scope>"
            "<Effect>standing_delta: 0.30</Effect></AffinityShift>"
        )
        shifts, _ = parse_affinity_shifts(text)
        self.assertEqual(len(shifts), 2)
        self.assertEqual(shifts[0].scope, "nation:x")
        self.assertEqual(shifts[1].scope, "region:y")

    def test_missing_child_skipped(self) -> None:
        text = (
            "<AffinityShift>"
            "<Target>faction:a</Target><Scope>nation:x</Scope>"
            "</AffinityShift>"  # no Effect
        )
        shifts, _ = parse_affinity_shifts(text)
        self.assertEqual(shifts, [])

    def test_multiline_body(self) -> None:
        text = (
            "<AffinityShift>\n"
            "  <Target>faction:moors</Target>\n"
            "  <Scope>region:salt</Scope>\n"
            "  <Effect>standing_delta: 0.05</Effect>\n"
            "</AffinityShift>"
        )
        shifts, _ = parse_affinity_shifts(text)
        self.assertEqual(len(shifts), 1)
        self.assertEqual(shifts[0].target, "faction:moors")

    def test_case_insensitive_outer_tag(self) -> None:
        text = (
            "<affinityshift><Target>faction:x</Target>"
            "<Scope>nation:y</Scope><Effect>standing_delta: 0.1</Effect>"
            "</affinityshift>"
        )
        shifts, _ = parse_affinity_shifts(text)
        self.assertEqual(len(shifts), 1)


# ── Effect parsing ───────────────────────────────────────────────────


class TestParseEffect(unittest.TestCase):
    def test_standing_delta_colon(self) -> None:
        kind, val = parse_effect("standing_delta: -0.15")
        self.assertEqual(kind, "standing_delta")
        self.assertAlmostEqual(val, -0.15)

    def test_standing_delta_equals(self) -> None:
        kind, val = parse_effect("standing_delta=-0.15")
        self.assertEqual(kind, "standing_delta")
        self.assertAlmostEqual(val, -0.15)

    def test_no_separator(self) -> None:
        kind, val = parse_effect("standing_delta -0.15")
        self.assertEqual(kind, "standing_delta")
        self.assertAlmostEqual(val, -0.15)

    def test_empty(self) -> None:
        kind, val = parse_effect("")
        self.assertEqual(kind, "unparsed")
        self.assertIsNone(val)

    def test_garbage(self) -> None:
        kind, val = parse_effect("not a key value pair at all")
        self.assertEqual(kind, "unparsed")
        self.assertIsNone(val)

    def test_positive_value(self) -> None:
        kind, val = parse_effect("influence_delta: 0.42")
        self.assertEqual(kind, "influence_delta")
        self.assertAlmostEqual(val, 0.42)


# ── Scope parsing ────────────────────────────────────────────────────


class TestParseScope(unittest.TestCase):
    def test_well_formed(self) -> None:
        tier, rid = parse_scope("region:salt_moors")
        self.assertEqual(tier, "region")
        self.assertEqual(rid, "salt_moors")

    def test_no_colon(self) -> None:
        tier, rid = parse_scope("salt_moors")
        self.assertEqual(tier, "")
        self.assertEqual(rid, "")

    def test_lowercases_tier(self) -> None:
        tier, _ = parse_scope("REGION:salt")
        self.assertEqual(tier, "region")


class TestIsKnownScopeTier(unittest.TestCase):
    def test_known(self) -> None:
        for t in KNOWN_SCOPE_TIERS:
            self.assertTrue(is_known_scope_tier(f"{t}:x"), f"{t} should be known")

    def test_unknown(self) -> None:
        self.assertFalse(is_known_scope_tier("garbage:x"))
        self.assertFalse(is_known_scope_tier("malformed"))


# ── Resolver tests ───────────────────────────────────────────────────


class TestResolver(unittest.TestCase):
    def setUp(self) -> None:
        self.resolver = AffinityResolver(faction_system=None)

    def _shift(self, target: str = "faction:moors_raiders",
               scope: str = "region:salt_moors",
               effect: str = "standing_delta: -0.15") -> AffinityShift:
        return AffinityShift(target=target, scope=scope, effect=effect)

    def test_no_faction_system_logs_only(self) -> None:
        records = self.resolver.resolve_batch(
            [self._shift()], weaver_layer=4,
            weaver_address="region:salt_moors",
            narrative_event_id="row_xyz", game_time=300.0,
        )
        self.assertEqual(len(records), 1)
        rec = records[0]
        self.assertFalse(rec.applied)
        self.assertIn("no faction_system wired", rec.apply_note)
        # Ledger captured the record
        self.assertEqual(len(self.resolver.ledger), 1)
        self.assertEqual(self.resolver.ledger[0].narrative_event_id, "row_xyz")

    def test_unknown_scope_skipped(self) -> None:
        records = self.resolver.resolve_batch(
            [self._shift(scope="garbage:x")], weaver_layer=4,
            weaver_address="region:y", narrative_event_id="row", game_time=1.0,
        )
        self.assertFalse(records[0].applied)
        self.assertIn("unknown scope tier", records[0].apply_note)

    def test_unknown_target_prefix_logged(self) -> None:
        records = self.resolver.resolve_batch(
            [self._shift(target="thing:weird")], weaver_layer=4,
            weaver_address="region:y", narrative_event_id="row", game_time=1.0,
        )
        self.assertFalse(records[0].applied)
        self.assertIn("unknown target prefix", records[0].apply_note)


class TestResolverWithFactionSystem(unittest.TestCase):
    def test_faction_target_applied(self) -> None:
        fs = _StubFactionSystem()
        resolver = AffinityResolver(faction_system=fs)
        records = resolver.resolve_batch(
            [AffinityShift(
                target="faction:moors_raiders",
                scope="region:salt_moors",
                effect="standing_delta: -0.15",
            )],
            weaver_layer=4, weaver_address="region:salt_moors",
            narrative_event_id="row_xyz", game_time=300.0,
        )
        self.assertTrue(records[0].applied)
        self.assertEqual(len(fs.player_calls), 1)
        call = fs.player_calls[0]
        self.assertEqual(call["tag"], "moors_raiders")
        self.assertEqual(call["player_id"], "region:salt_moors")
        self.assertAlmostEqual(call["delta"], -0.15)
        self.assertIn("wns:row_xyz", call["source"])

    def test_npc_target_applied(self) -> None:
        fs = _StubFactionSystem()
        resolver = AffinityResolver(faction_system=fs)
        records = resolver.resolve_batch(
            [AffinityShift(
                target="npc:moors_copperlash_captain",
                scope="locality:tarmouth",
                effect="standing_delta: 0.05",
            )],
            weaver_layer=2, weaver_address="locality:tarmouth",
            narrative_event_id="row_npc", game_time=100.0,
        )
        self.assertTrue(records[0].applied)
        self.assertEqual(len(fs.npc_calls), 1)
        call = fs.npc_calls[0]
        self.assertEqual(call["npc_id"], "moors_copperlash_captain")
        self.assertAlmostEqual(call["delta"], 0.05)

    def test_faction_system_error_logged_not_raised(self) -> None:
        fs = _StubFactionSystem(raises=True)
        resolver = AffinityResolver(faction_system=fs)
        records = resolver.resolve_batch(
            [AffinityShift(
                target="faction:x", scope="nation:y",
                effect="standing_delta: 0.1",
            )],
            weaver_layer=5, weaver_address="nation:y",
            narrative_event_id="row", game_time=1.0,
        )
        self.assertFalse(records[0].applied)
        self.assertIn("FactionSystem error", records[0].apply_note)

    def test_unparsed_effect_logged(self) -> None:
        fs = _StubFactionSystem()
        resolver = AffinityResolver(faction_system=fs)
        records = resolver.resolve_batch(
            [AffinityShift(
                target="faction:x", scope="nation:y",
                effect="totally garbage",
            )],
            weaver_layer=5, weaver_address="nation:y",
            narrative_event_id="row", game_time=1.0,
        )
        self.assertFalse(records[0].applied)
        # Stub should NOT have been called
        self.assertEqual(len(fs.player_calls), 0)


class TestRecordSerialization(unittest.TestCase):
    def test_to_dict_round_trip(self) -> None:
        rec = AffinityShiftRecord(
            target="faction:x", scope="nation:y",
            effect_raw="standing_delta: 0.1",
            effect_kind="standing_delta", effect_value=0.1,
            time=100.0, narrative_event_id="row",
            weaver_layer=5, weaver_address="nation:y",
            applied=True, apply_note="ok",
        )
        d = rec.to_dict()
        self.assertEqual(d["target"], "faction:x")
        self.assertEqual(d["weaver_layer"], 5)
        self.assertTrue(d["applied"])
        self.assertAlmostEqual(d["effect_value"], 0.1)


if __name__ == "__main__":
    unittest.main()

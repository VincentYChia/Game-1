"""Tests for world_system.wns.cascading_context."""

from __future__ import annotations

import unittest
import uuid

from world_system.living_world.infra.context_bundle import ThreadFragment
from world_system.wns.cascading_context import (
    WeaverContext,
    build_weaver_context,
    extract_active_threads,
    get_layer_snapshot,
)
from world_system.wns.narrative_store import NarrativeRow, NarrativeStore


def _frag(
    fragment_id: str,
    layer: int,
    address: str,
    headline: str,
    content_tags=None,
    thread_id=None,
    created_at: float = 0.0,
) -> ThreadFragment:
    return ThreadFragment(
        fragment_id=fragment_id,
        layer=layer,
        address=address,
        headline=headline,
        content_tags=list(content_tags or []),
        thread_id=thread_id,
        created_at=created_at,
    )


def _row(
    layer: int,
    address: str,
    narrative: str,
    threads,
    created_at: float,
) -> NarrativeRow:
    return NarrativeRow(
        id=str(uuid.uuid4()),
        created_at=created_at,
        layer=layer,
        address=address,
        narrative=narrative,
        tags=[address],
        payload={"threads": [t.to_dict() for t in threads]},
    )


def _make_store() -> NarrativeStore:
    return NarrativeStore(":memory:")


class TestExtractActiveThreads(unittest.TestCase):
    def test_empty_input(self) -> None:
        self.assertEqual(extract_active_threads([]), [])

    def test_dedup_keeps_newest_per_thread(self) -> None:
        rows = [
            _row(2, "loc:a", "n1", [
                _frag("f1", 2, "loc:a", "old", thread_id="t1", created_at=100.0),
            ], created_at=100.0),
            _row(2, "loc:a", "n2", [
                _frag("f2", 2, "loc:a", "new", thread_id="t1", created_at=200.0),
            ], created_at=200.0),
        ]
        threads = extract_active_threads(rows)
        self.assertEqual(len(threads), 1)
        self.assertEqual(threads[0].headline, "new")

    def test_distinct_threads_kept_separately(self) -> None:
        rows = [
            _row(2, "loc:a", "n", [
                _frag("f1", 2, "loc:a", "thread_a", thread_id="t1", created_at=100.0),
                _frag("f2", 2, "loc:a", "thread_b", thread_id="t2", created_at=100.0),
            ], created_at=100.0),
        ]
        threads = extract_active_threads(rows)
        self.assertEqual(len(threads), 2)
        self.assertEqual({t.thread_id for t in threads}, {"t1", "t2"})

    def test_retain_caps_count(self) -> None:
        # 6 distinct threads, retain=3 -> only 3 returned, newest first
        rows = []
        for i in range(6):
            rows.append(_row(2, "loc:a", f"n{i}", [
                _frag(f"f{i}", 2, "loc:a", f"h{i}", thread_id=f"t{i}", created_at=100.0 + i),
            ], created_at=100.0 + i))
        threads = extract_active_threads(rows, retain=3)
        self.assertEqual(len(threads), 3)
        # Newest 3 should be t5, t4, t3
        self.assertEqual([t.thread_id for t in threads], ["t5", "t4", "t3"])

    def test_legacy_fragments_without_thread_id_fold_in_when_room(self) -> None:
        rows = [
            _row(2, "loc:a", "n", [
                _frag("f1", 2, "loc:a", "modern", thread_id="t1", created_at=200.0),
                _frag("f2", 2, "loc:a", "legacy", thread_id=None, created_at=100.0),
            ], created_at=200.0),
        ]
        threads = extract_active_threads(rows, retain=5)
        self.assertEqual(len(threads), 2)
        # Modern (with thread_id) should come first since legacy is appended at end.
        self.assertEqual(threads[0].headline, "modern")


class TestGetLayerSnapshot(unittest.TestCase):
    def test_no_rows_returns_empty(self) -> None:
        store = _make_store()
        n, t = get_layer_snapshot(store, layer=2, address="loc:nonexistent")
        self.assertEqual(n, "")
        self.assertEqual(t, [])

    def test_returns_latest_narrative_and_threads(self) -> None:
        store = _make_store()
        store.insert_row(_row(2, "loc:a", "old narrative", [
            _frag("f1", 2, "loc:a", "h_old", thread_id="t1", created_at=100.0),
        ], created_at=100.0))
        store.insert_row(_row(2, "loc:a", "new narrative", [
            _frag("f2", 2, "loc:a", "h_new", thread_id="t1", created_at=200.0),
        ], created_at=200.0))
        n, t = get_layer_snapshot(store, layer=2, address="loc:a")
        self.assertEqual(n, "new narrative")
        self.assertEqual(len(t), 1)
        self.assertEqual(t[0].headline, "h_new")

    def test_invalid_layer_returns_empty(self) -> None:
        store = _make_store()
        self.assertEqual(get_layer_snapshot(store, layer=0, address="x"), ("", []))
        self.assertEqual(get_layer_snapshot(store, layer=8, address="x"), ("", []))


class TestBuildWeaverContext(unittest.TestCase):
    def test_full_context_build(self) -> None:
        store = _make_store()
        # NL3 narrative at parent district (above_primary)
        store.insert_row(_row(3, "district:cd", "district narrative", [
            _frag("f0", 3, "district:cd", "trade pressure",
                  thread_id="t_above", created_at=100.0),
        ], created_at=100.0))
        # NL4 narrative at grandparent region (above_fading)
        store.insert_row(_row(4, "region:moors",
                              "region-scale economic shift takes shape",
                              [], created_at=100.0))
        # NL2 firing context: same-layer prior + N-1 (NL1) at same address
        store.insert_row(_row(2, "loc:t", "earlier locality narrative", [
            _frag("f1", 2, "loc:t", "early thread",
                  thread_id="t_self", created_at=150.0),
        ], created_at=150.0))
        store.insert_row(_row(1, "loc:t", "NPC mentions copper rumor",
                              [], created_at=160.0))

        ctx = build_weaver_context(
            store, layer=2, address="loc:t",
            parent_address="district:cd",
            grandparent_address="region:moors",
        )
        self.assertEqual(ctx.layer, 2)
        self.assertEqual(ctx.address, "loc:t")
        self.assertEqual(ctx.self_latest_narrative, "earlier locality narrative")
        self.assertEqual(len(ctx.self_active_threads), 1)
        self.assertEqual(ctx.lower_primary_narrative, "NPC mentions copper rumor")
        self.assertEqual(ctx.above_primary_address, "district:cd")
        self.assertEqual(ctx.above_primary_narrative, "district narrative")
        self.assertEqual(len(ctx.above_primary_threads), 1)
        self.assertEqual(ctx.above_fading_address, "region:moors")
        self.assertIn("region-scale", ctx.above_fading_narrative)

    def test_no_parent_address_skips_above(self) -> None:
        store = _make_store()
        ctx = build_weaver_context(store, layer=2, address="loc:x")
        self.assertEqual(ctx.above_primary_address, "")
        self.assertEqual(ctx.above_primary_narrative, "")
        self.assertEqual(ctx.above_fading_address, "")

    def test_layer_2_has_no_lower_fading(self) -> None:
        # NL2's "fading lower" would be NL0 which doesn't exist.
        store = _make_store()
        store.insert_row(_row(1, "loc:x", "L1 mentions", [], created_at=100.0))
        ctx = build_weaver_context(store, layer=2, address="loc:x")
        self.assertEqual(ctx.lower_primary_narrative, "L1 mentions")
        self.assertEqual(ctx.lower_fading_narrative, "")

    def test_layer_7_has_no_above_context(self) -> None:
        store = _make_store()
        ctx = build_weaver_context(
            store, layer=7, address="world:root",
            parent_address="meta:beyond",  # would be N+1=8, out of range
        )
        self.assertEqual(ctx.above_primary_narrative, "")

    def test_fading_narrative_is_truncated(self) -> None:
        store = _make_store()
        long_narrative = "A " * 500  # ~1000 chars
        store.insert_row(_row(2, "region:r", long_narrative, [], created_at=100.0))
        ctx = build_weaver_context(
            store, layer=4, address="region:r",
            grandparent_address="region:r",  # forces L6 lookup; layer-2 used here
        )
        # layer 4's lower_fading = layer 2 at same address. But lower_fading
        # path is layer-2 narrative truncated.
        self.assertLess(len(ctx.lower_fading_narrative), len(long_narrative))


if __name__ == "__main__":
    unittest.main()

"""Tests for world_system.wns.thread_index."""

from __future__ import annotations

import unittest

from world_system.living_world.infra.context_bundle import ThreadFragment
from world_system.wns.thread_index import (
    DEFAULT_MATCH_THRESHOLD,
    DEFAULT_TIME_WINDOW_SECONDS,
    ThreadCluster,
    build_clusters_from_fragments,
    jaccard_similarity,
    make_thread_id,
    match_or_mint,
)


def _frag(
    fragment_id: str,
    address: str,
    content_tags,
    created_at: float,
    thread_id=None,
    layer: int = 2,
    headline: str = "",
) -> ThreadFragment:
    return ThreadFragment(
        fragment_id=fragment_id,
        layer=layer,
        address=address,
        headline=headline,
        content_tags=list(content_tags),
        thread_id=thread_id,
        created_at=created_at,
    )


class TestMakeThreadId(unittest.TestCase):
    def test_deterministic(self) -> None:
        a = make_thread_id("locality:tarmouth", ["copper", "rising_action"], 100.0)
        b = make_thread_id("locality:tarmouth", ["copper", "rising_action"], 100.0)
        self.assertEqual(a, b)

    def test_tag_order_invariant(self) -> None:
        a = make_thread_id("locality:tarmouth", ["copper", "rising_action"], 100.0)
        b = make_thread_id("locality:tarmouth", ["rising_action", "copper"], 100.0)
        self.assertEqual(a, b)

    def test_different_address_different_id(self) -> None:
        a = make_thread_id("locality:tarmouth", ["copper"], 100.0)
        b = make_thread_id("locality:hollow", ["copper"], 100.0)
        self.assertNotEqual(a, b)

    def test_different_tags_different_id(self) -> None:
        a = make_thread_id("locality:tarmouth", ["copper"], 100.0)
        b = make_thread_id("locality:tarmouth", ["iron"], 100.0)
        self.assertNotEqual(a, b)

    def test_returns_thread_prefix(self) -> None:
        tid = make_thread_id("a", ["b"], 1.0)
        self.assertTrue(tid.startswith("thread_"))


class TestJaccard(unittest.TestCase):
    def test_identical_tag_sets_score_1(self) -> None:
        self.assertEqual(jaccard_similarity(["a", "b"], ["a", "b"]), 1.0)

    def test_disjoint_sets_score_0(self) -> None:
        self.assertEqual(jaccard_similarity(["a", "b"], ["c", "d"]), 0.0)

    def test_partial_overlap_scores_correctly(self) -> None:
        # {a,b,c} ∩ {b,c,d} = {b,c} (2); union = {a,b,c,d} (4) => 0.5
        self.assertAlmostEqual(
            jaccard_similarity(["a", "b", "c"], ["b", "c", "d"]),
            0.5,
        )

    def test_empty_inputs_return_0(self) -> None:
        self.assertEqual(jaccard_similarity([], ["a"]), 0.0)
        self.assertEqual(jaccard_similarity(["a"], []), 0.0)
        self.assertEqual(jaccard_similarity([], []), 0.0)

    def test_duplicates_collapse(self) -> None:
        # ["a","a","b"] becomes {a,b}; vs {a,b} => 1.0
        self.assertEqual(jaccard_similarity(["a", "a", "b"], ["a", "b"]), 1.0)


class TestBuildClusters(unittest.TestCase):
    def test_empty_fragments_yields_empty_clusters(self) -> None:
        clusters = build_clusters_from_fragments([])
        self.assertEqual(clusters, [])

    def test_fragments_without_thread_id_skipped(self) -> None:
        frags = [_frag("f1", "a", ["x"], 1.0, thread_id=None)]
        self.assertEqual(build_clusters_from_fragments(frags), [])

    def test_single_fragment_one_cluster(self) -> None:
        f = _frag("f1", "loc:a", ["copper", "rising_action"], 100.0,
                  thread_id="thread_x")
        clusters = build_clusters_from_fragments([f])
        self.assertEqual(len(clusters), 1)
        c = clusters[0]
        self.assertEqual(c.thread_id, "thread_x")
        self.assertEqual(c.address, "loc:a")
        self.assertEqual(c.canonical_content_tags, {"copper", "rising_action"})
        self.assertEqual(c.fragment_count, 1)
        self.assertEqual(c.first_seen, 100.0)
        self.assertEqual(c.last_seen, 100.0)

    def test_multiple_fragments_same_thread_aggregate(self) -> None:
        frags = [
            _frag("f1", "loc:a", ["copper", "rumor"], 100.0, thread_id="t1",
                  headline="early"),
            _frag("f2", "loc:a", ["copper", "rising_action", "rumor"], 200.0,
                  thread_id="t1", headline="middle"),
            _frag("f3", "loc:a", ["copper", "complication"], 300.0, thread_id="t1",
                  headline="latest"),
        ]
        clusters = build_clusters_from_fragments(frags)
        self.assertEqual(len(clusters), 1)
        c = clusters[0]
        self.assertEqual(c.fragment_count, 3)
        self.assertEqual(c.first_seen, 100.0)
        self.assertEqual(c.last_seen, 300.0)
        # canonical_content_tags is the UNION across all fragments
        self.assertEqual(
            c.canonical_content_tags,
            {"copper", "rumor", "rising_action", "complication"},
        )
        # latest_headline tracks the newest fragment
        self.assertEqual(c.latest_headline, "latest")

    def test_multiple_threads_separate_clusters(self) -> None:
        frags = [
            _frag("f1", "loc:a", ["copper"], 100.0, thread_id="t1"),
            _frag("f2", "loc:a", ["iron"], 100.0, thread_id="t2"),
        ]
        clusters = build_clusters_from_fragments(frags)
        self.assertEqual(len(clusters), 2)


class TestMatchOrMint(unittest.TestCase):
    def test_no_existing_clusters_mints_new(self) -> None:
        tid = match_or_mint(
            new_address="loc:a",
            new_content_tags=["copper", "rising_action"],
            new_time=100.0,
            existing_clusters=[],
        )
        self.assertTrue(tid.startswith("thread_"))

    def test_high_similarity_matches_existing(self) -> None:
        existing = ThreadCluster(
            thread_id="t1",
            layer=2,
            address="loc:a",
            canonical_content_tags={"copper", "rumor", "rising_action"},
            first_seen=100.0,
            last_seen=200.0,
        )
        # New fragment shares 3 of 3 tags with existing.
        tid = match_or_mint(
            new_address="loc:a",
            new_content_tags=["copper", "rumor", "rising_action"],
            new_time=300.0,
            existing_clusters=[existing],
        )
        self.assertEqual(tid, "t1")

    def test_low_similarity_mints_new(self) -> None:
        existing = ThreadCluster(
            thread_id="t1",
            layer=2,
            address="loc:a",
            canonical_content_tags={"copper", "rumor"},
            first_seen=100.0,
            last_seen=200.0,
        )
        # Disjoint tags — Jaccard=0.
        tid = match_or_mint(
            new_address="loc:a",
            new_content_tags=["frost", "ominous"],
            new_time=300.0,
            existing_clusters=[existing],
        )
        self.assertNotEqual(tid, "t1")
        self.assertTrue(tid.startswith("thread_"))

    def test_different_address_does_not_match(self) -> None:
        existing = ThreadCluster(
            thread_id="t1",
            layer=2,
            address="loc:a",
            canonical_content_tags={"copper", "rumor"},
            first_seen=100.0,
            last_seen=200.0,
        )
        tid = match_or_mint(
            new_address="loc:b",  # different address
            new_content_tags=["copper", "rumor"],
            new_time=300.0,
            existing_clusters=[existing],
        )
        self.assertNotEqual(tid, "t1")

    def test_stale_thread_does_not_match(self) -> None:
        existing = ThreadCluster(
            thread_id="t1",
            layer=2,
            address="loc:a",
            canonical_content_tags={"copper", "rumor"},
            first_seen=100.0,
            last_seen=200.0,
        )
        # new_time is 2 weeks after last_seen — outside default window (1 week).
        new_time = 200.0 + (14 * 24 * 3600)
        tid = match_or_mint(
            new_address="loc:a",
            new_content_tags=["copper", "rumor"],
            new_time=new_time,
            existing_clusters=[existing],
        )
        self.assertNotEqual(tid, "t1")

    def test_threshold_boundary(self) -> None:
        existing = ThreadCluster(
            thread_id="t1",
            layer=2,
            address="loc:a",
            canonical_content_tags={"copper", "rumor"},
            first_seen=100.0,
            last_seen=200.0,
        )
        # New tags ["copper", "frost"] vs {"copper", "rumor"} =>
        # intersect={"copper"}=1, union={"copper","rumor","frost"}=3 => 0.333
        # Below default 0.5 threshold.
        tid = match_or_mint(
            new_address="loc:a",
            new_content_tags=["copper", "frost"],
            new_time=300.0,
            existing_clusters=[existing],
        )
        self.assertNotEqual(tid, "t1")

        # Lower threshold to 0.3 — should now match.
        tid_low = match_or_mint(
            new_address="loc:a",
            new_content_tags=["copper", "frost"],
            new_time=300.0,
            existing_clusters=[existing],
            similarity_threshold=0.3,
        )
        self.assertEqual(tid_low, "t1")

    def test_picks_best_match_when_multiple_candidates(self) -> None:
        weak = ThreadCluster(
            thread_id="t_weak",
            layer=2, address="loc:a",
            canonical_content_tags={"copper"},
            first_seen=100.0, last_seen=200.0,
        )
        strong = ThreadCluster(
            thread_id="t_strong",
            layer=2, address="loc:a",
            canonical_content_tags={"copper", "rumor", "rising_action"},
            first_seen=100.0, last_seen=200.0,
        )
        tid = match_or_mint(
            new_address="loc:a",
            new_content_tags=["copper", "rumor", "rising_action"],
            new_time=300.0,
            existing_clusters=[weak, strong],
        )
        self.assertEqual(tid, "t_strong")

    def test_empty_tags_always_mint(self) -> None:
        existing = ThreadCluster(
            thread_id="t1",
            layer=2, address="loc:a",
            canonical_content_tags={"copper"},
            first_seen=100.0, last_seen=200.0,
        )
        tid = match_or_mint(
            new_address="loc:a",
            new_content_tags=[],
            new_time=300.0,
            existing_clusters=[existing],
        )
        self.assertNotEqual(tid, "t1")


class TestEndToEnd(unittest.TestCase):
    """Walk a sequence of fragments through the index, verifying clustering."""

    def test_three_fragment_thread_continuity(self) -> None:
        # First fragment: no existing clusters -> mint t_initial
        clusters = build_clusters_from_fragments([])
        t1 = match_or_mint(
            new_address="loc:moors",
            new_content_tags=["copper", "rumor", "rising_action"],
            new_time=100.0,
            existing_clusters=clusters,
        )

        f1 = _frag("f1", "loc:moors", ["copper", "rumor", "rising_action"],
                   100.0, thread_id=t1)
        clusters = build_clusters_from_fragments([f1])

        # Second fragment with overlapping tags -> should match t1
        t2 = match_or_mint(
            new_address="loc:moors",
            new_content_tags=["copper", "rumor", "complication"],  # 2/4 overlap = 0.5
            new_time=200.0,
            existing_clusters=clusters,
        )
        self.assertEqual(t2, t1, "second fragment should join the same thread")

        f2 = _frag("f2", "loc:moors", ["copper", "rumor", "complication"],
                   200.0, thread_id=t2)
        clusters = build_clusters_from_fragments([f1, f2])

        # Third fragment, totally new content -> should mint a new thread
        t3 = match_or_mint(
            new_address="loc:moors",
            new_content_tags=["frost", "tragic", "ominous"],
            new_time=300.0,
            existing_clusters=clusters,
        )
        self.assertNotEqual(t3, t1, "unrelated fragment should not join existing thread")

        f3 = _frag("f3", "loc:moors", ["frost", "tragic", "ominous"],
                   300.0, thread_id=t3)
        clusters = build_clusters_from_fragments([f1, f2, f3])

        # Should have 2 clusters now: t1 (with f1+f2) and t3 (with f3)
        thread_ids = {c.thread_id for c in clusters}
        self.assertEqual(len(thread_ids), 2)
        self.assertIn(t1, thread_ids)
        self.assertIn(t3, thread_ids)


if __name__ == "__main__":
    unittest.main()

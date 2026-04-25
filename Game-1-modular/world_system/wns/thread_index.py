"""Thread index — content-cluster identity for WNS thread fragments.

A thread_id identifies a content-cluster at an address. The runtime
matches a new fragment against recent existing threads at the same
address using tag-set Jaccard similarity. If a sufficient match is
found, the new fragment joins the cluster (sharing thread_id);
otherwise a fresh thread_id is minted.

Thread IDs are deterministic — derived from
``(address + sorted content_tags + first_seen_time)`` — so they are
stable across re-runs when the input data is the same. The LLM does
NOT generate thread_ids; this module owns minting and the runtime
owns assignment.

A separate ``parent_thread_id`` field on ThreadFragment refers to a
thread at a LOWER layer that this fragment is aggregating from
(bottom-up promotion). That is a cross-layer link, not the same as
thread_id.

Design intent (from user direction): the thread system is in practice
a content-clustering / similarity index. Threads naturally form when
fragments at the same address share tag vocabulary; fragments diverge
into new threads when vocabulary diverges. The Jaccard threshold
controls how aggressively things cluster together.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Any, List, Optional, Sequence, Set


# ── Tunable knobs ─────────────────────────────────────────────────────

# Default Jaccard similarity threshold for thread matching.
# 0.5 = at least half the union of tag-sets must be shared.
DEFAULT_MATCH_THRESHOLD: float = 0.5

# Default time window (in the same units as fragment.created_at — wall
# seconds in current usage). Fragments whose containing cluster has not
# been touched within this window are considered stale and will not
# match — a new thread_id mints instead.
DEFAULT_TIME_WINDOW_SECONDS: float = 7 * 24 * 3600  # 1 week


# ── Cluster summary ───────────────────────────────────────────────────


@dataclass
class ThreadCluster:
    """In-memory summary of one thread (a cluster of related fragments).

    Built from a sequence of ThreadFragment-like records via
    :func:`build_clusters_from_fragments`. Used as the existing-clusters
    input to :func:`match_or_mint`.
    """
    thread_id: str
    layer: int
    address: str
    canonical_content_tags: Set[str] = field(default_factory=set)
    first_seen: float = 0.0
    last_seen: float = 0.0
    fragment_count: int = 0
    latest_headline: str = ""

    def __post_init__(self) -> None:
        # Normalize the canonical_content_tags into a real set (callers
        # often pass list/iterable).
        if not isinstance(self.canonical_content_tags, set):
            self.canonical_content_tags = set(self.canonical_content_tags)


# ── Pure helpers ──────────────────────────────────────────────────────


def make_thread_id(
    address: str, content_tags: Sequence[str], first_seen: float
) -> str:
    """Deterministic thread_id from address + sorted content tags + time.

    Returns 'thread_<16 hex>'. Stable for the same inputs across runs.
    """
    sig = (
        address
        + "|"
        + ",".join(sorted(content_tags))
        + "|"
        + f"{first_seen:.6f}"
    )
    digest = hashlib.sha256(sig.encode("utf-8")).hexdigest()
    return f"thread_{digest[:16]}"


def jaccard_similarity(a: Sequence[str], b: Sequence[str]) -> float:
    """Jaccard similarity coefficient between two tag sets.

    Returns 0..1. Returns 0 if either is empty (empty fragments cannot
    cluster — they always mint new threads).
    """
    set_a = set(a)
    set_b = set(b)
    if not set_a or not set_b:
        return 0.0
    intersect = set_a & set_b
    union = set_a | set_b
    return len(intersect) / len(union)


# ── Matching ──────────────────────────────────────────────────────────


def match_or_mint(
    *,
    new_address: str,
    new_content_tags: Sequence[str],
    new_time: float,
    existing_clusters: Sequence[ThreadCluster],
    similarity_threshold: float = DEFAULT_MATCH_THRESHOLD,
    time_window_seconds: float = DEFAULT_TIME_WINDOW_SECONDS,
) -> str:
    """Match a new fragment to an existing thread or mint a new thread_id.

    Args:
        new_address: address of the new fragment.
        new_content_tags: content tags of the new fragment (after
            address-tag scrubbing).
        new_time: timestamp of the new fragment.
        existing_clusters: candidate threads. Caller may pre-filter by
            address/recency; this function double-checks both.
        similarity_threshold: minimum Jaccard for a match (default 0.5).
        time_window_seconds: maximum (new_time - cluster.last_seen) for a
            match to be valid (default 1 week game-seconds).

    Returns:
        thread_id of the matched cluster, OR a freshly-minted thread_id.
        The returned id is suitable to assign to the new fragment's
        ``thread_id`` field.
    """
    if not new_content_tags:
        # Empty-tag fragments cannot cluster meaningfully — always mint.
        return make_thread_id(new_address, new_content_tags, new_time)

    best_match: Optional[ThreadCluster] = None
    best_score: float = 0.0
    for cluster in existing_clusters:
        if cluster.address != new_address:
            continue
        if (new_time - cluster.last_seen) > time_window_seconds:
            continue
        score = jaccard_similarity(new_content_tags, cluster.canonical_content_tags)
        if score > best_score:
            best_score = score
            best_match = cluster

    if best_match is not None and best_score >= similarity_threshold:
        return best_match.thread_id

    return make_thread_id(new_address, new_content_tags, new_time)


# ── Cluster aggregation ───────────────────────────────────────────────


def build_clusters_from_fragments(
    fragments: Sequence[Any],
) -> List[ThreadCluster]:
    """Aggregate ThreadFragment-like records into ThreadCluster summaries.

    Each fragment must expose: ``thread_id``, ``layer``, ``address``,
    ``content_tags``, ``created_at`` (and ideally ``headline``).
    Fragments with empty/None thread_id are skipped.

    The cluster's canonical_content_tags is the UNION of all member
    fragments' content_tags — vocabulary accumulates as a thread grows.
    """
    by_thread: dict = {}
    for f in fragments:
        tid = getattr(f, "thread_id", None)
        if not tid:
            continue
        ct = float(getattr(f, "created_at", 0.0))
        tags = list(getattr(f, "content_tags", []) or [])
        headline = str(getattr(f, "headline", "") or "")

        if tid not in by_thread:
            by_thread[tid] = ThreadCluster(
                thread_id=tid,
                layer=int(getattr(f, "layer", 0)),
                address=str(getattr(f, "address", "")),
                canonical_content_tags=set(tags),
                first_seen=ct,
                last_seen=ct,
                fragment_count=1,
                latest_headline=headline,
            )
        else:
            cluster = by_thread[tid]
            cluster.canonical_content_tags |= set(tags)
            cluster.first_seen = min(cluster.first_seen, ct)
            if ct >= cluster.last_seen:
                cluster.last_seen = ct
                cluster.latest_headline = headline
            cluster.fragment_count += 1

    return list(by_thread.values())


__all__ = [
    "DEFAULT_MATCH_THRESHOLD",
    "DEFAULT_TIME_WINDOW_SECONDS",
    "ThreadCluster",
    "make_thread_id",
    "jaccard_similarity",
    "match_or_mint",
    "build_clusters_from_fragments",
]

"""Cascading context — aggregate the inputs an NL_N weaver needs.

Per user direction: NL layers receive WMS events at their OWN layer
(trigger), and WNS narrative from N-1 PRIMARILY plus N-2 as fading
context. Higher-layer narrative (N+1, N+2 at parent geographic
addresses) is read as cascading-down framing — lower layers can't
WRITE upward, but they DO read what's already happened above.

This module builds the structured inputs from a NarrativeStore, with
two key operations:

1. :func:`extract_active_threads` — turn a list of NarrativeRows into
   a deduplicated thread-fragment list (most-recent fragment per
   thread_id). The "summative/most recent thread is what gets passed
   on, not every iteration" semantics from the user direction.

2. :func:`build_weaver_context` — compose all the cascading slots an
   NL_N weaver consumes: same-layer continuity, primary lower input,
   fading lower input, primary above input (cascading down), fading
   above input.

Empty/missing layers degrade to empty strings / empty lists — the
weaver still runs, just with less context.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable, List, Optional, Sequence, Tuple

from world_system.living_world.infra.context_bundle import ThreadFragment
from world_system.wns.narrative_store import NarrativeRow, NarrativeStore


# ── Tunables ──────────────────────────────────────────────────────────

# How many recent NL rows to scan when extracting active threads at
# (layer, address). Active threads dedup on thread_id, so this is the
# UPPER BOUND on rows considered, not threads returned.
DEFAULT_THREAD_SCAN_LIMIT: int = 30

# How many active threads to retain in the cascading context (most
# recent N by latest fragment timestamp).
DEFAULT_ACTIVE_THREADS_RETAIN: int = 5

# Char cap on fading-context narratives so the prompt stays bounded.
FADING_NARRATIVE_CHAR_CAP: int = 240


# ── Composite output ──────────────────────────────────────────────────


@dataclass
class WeaverContext:
    """All cascading inputs an NL_N weaver consumes at firing time."""
    layer: int
    address: str

    # Same-layer continuity (THIS layer's previous narrative + threads at THIS address)
    self_latest_narrative: str = ""
    self_active_threads: List[ThreadFragment] = field(default_factory=list)

    # Primary input from layer below (N-1) at THIS address
    lower_primary_narrative: str = ""
    lower_primary_threads: List[ThreadFragment] = field(default_factory=list)

    # Fading input from layer 2 below (N-2) at THIS address (1 sentence cap)
    lower_fading_narrative: str = ""

    # Cascading from above (N+1) at PARENT address — full narrative + active threads
    above_primary_narrative: str = ""
    above_primary_address: str = ""
    above_primary_threads: List[ThreadFragment] = field(default_factory=list)

    # Doubly-cascading (N+2) at GRANDPARENT address — fading sentence
    above_fading_narrative: str = ""
    above_fading_address: str = ""


# ── Active-thread extraction ──────────────────────────────────────────


def _threads_from_row(row: NarrativeRow) -> List[ThreadFragment]:
    """Decode the threads array from a NarrativeRow's payload."""
    raw = row.payload.get("threads") if row.payload else None
    if not isinstance(raw, list):
        return []
    out: List[ThreadFragment] = []
    for t in raw:
        if not isinstance(t, dict):
            continue
        try:
            out.append(ThreadFragment.from_dict(t))
        except (KeyError, ValueError, TypeError):
            continue
    return out


def extract_active_threads(
    rows: Iterable[NarrativeRow],
    *,
    retain: int = DEFAULT_ACTIVE_THREADS_RETAIN,
) -> List[ThreadFragment]:
    """Aggregate active threads from recent NL rows.

    "Active" means: keep ONE fragment per thread_id (the newest one), and
    drop fragments without a thread_id (legacy rows from before the
    thread-index was introduced). Returns up to ``retain`` threads,
    most-recently-touched first.

    Per user direction, the weaver downstream sees the "summative /
    most recent" state of each thread, not the iteration history.
    """
    by_thread: dict = {}  # thread_id -> ThreadFragment (newest)
    legacy_no_id: List[ThreadFragment] = []

    for row in rows:
        for frag in _threads_from_row(row):
            tid = frag.thread_id
            if not tid:
                legacy_no_id.append(frag)
                continue
            existing = by_thread.get(tid)
            if existing is None or frag.created_at >= existing.created_at:
                by_thread[tid] = frag

    deduped = list(by_thread.values())
    deduped.sort(key=lambda f: f.created_at, reverse=True)

    if len(deduped) >= retain:
        return deduped[:retain]

    # If we still have headroom, fold legacy fragments (newest first) into
    # the result so old saves don't appear empty.
    legacy_no_id.sort(key=lambda f: f.created_at, reverse=True)
    return (deduped + legacy_no_id)[:retain]


# ── Per-layer summary ─────────────────────────────────────────────────


def get_layer_snapshot(
    store: NarrativeStore,
    *,
    layer: int,
    address: str,
    scan_limit: int = DEFAULT_THREAD_SCAN_LIMIT,
    retain_threads: int = DEFAULT_ACTIVE_THREADS_RETAIN,
) -> Tuple[str, List[ThreadFragment]]:
    """Return (latest_narrative, active_threads) for a layer/address.

    Latest narrative is the single most-recent NL row's narrative
    string; active threads are deduplicated across the most-recent
    ``scan_limit`` rows.

    Returns ``("", [])`` if no rows exist at this (layer, address).
    """
    if layer < 1 or layer > 7:
        return "", []
    rows = store.query_by_address(layer, address, limit=scan_limit)
    if not rows:
        return "", []
    latest_narrative = rows[0].narrative or ""
    active = extract_active_threads(rows, retain=retain_threads)
    return latest_narrative, active


def _truncate_fading(text: str, cap: int = FADING_NARRATIVE_CHAR_CAP) -> str:
    """Truncate to a fading-context cap (~one short sentence)."""
    text = (text or "").strip()
    if len(text) <= cap:
        return text
    cut = text[:cap]
    last_space = cut.rfind(" ")
    if last_space > cap * 0.5:
        cut = cut[:last_space]
    return cut.rstrip(",.;:") + "…"


# ── Composite builder ─────────────────────────────────────────────────


def build_weaver_context(
    store: NarrativeStore,
    *,
    layer: int,
    address: str,
    parent_address: Optional[str] = None,
    grandparent_address: Optional[str] = None,
    scan_limit: int = DEFAULT_THREAD_SCAN_LIMIT,
    retain_threads: int = DEFAULT_ACTIVE_THREADS_RETAIN,
) -> WeaverContext:
    """Build a WeaverContext for an NL_N firing.

    Args:
        store: NarrativeStore to query.
        layer: firing layer (2..7).
        address: firing address (e.g. ``"locality:tarmouth"``).
        parent_address: address one geographic tier up (e.g.
            ``"district:copperdocks"``). Used for above-cascading at
            layer N+1. None -> empty above context.
        grandparent_address: address two geographic tiers up. Used for
            doubly-cascading at layer N+2. None -> empty fading-above.
        scan_limit / retain_threads: forwarded to
            :func:`get_layer_snapshot`.

    Returns:
        Populated :class:`WeaverContext`. Layers below 1 or above 7 are
        skipped silently (empty strings / lists).
    """
    ctx = WeaverContext(layer=layer, address=address)

    # Same-layer continuity at this address.
    self_n, self_t = get_layer_snapshot(
        store, layer=layer, address=address,
        scan_limit=scan_limit, retain_threads=retain_threads,
    )
    ctx.self_latest_narrative = self_n
    ctx.self_active_threads = self_t

    # Primary lower (N-1) at this address.
    if layer - 1 >= 1:
        n, t = get_layer_snapshot(
            store, layer=layer - 1, address=address,
            scan_limit=scan_limit, retain_threads=retain_threads,
        )
        ctx.lower_primary_narrative = n
        ctx.lower_primary_threads = t

    # Fading lower (N-2) at this address — narrative only, truncated.
    if layer - 2 >= 1:
        n2, _ = get_layer_snapshot(
            store, layer=layer - 2, address=address,
            scan_limit=scan_limit, retain_threads=0,
        )
        ctx.lower_fading_narrative = _truncate_fading(n2)

    # Above primary (N+1) at parent address.
    if parent_address and layer + 1 <= 7:
        ctx.above_primary_address = parent_address
        an, at = get_layer_snapshot(
            store, layer=layer + 1, address=parent_address,
            scan_limit=scan_limit, retain_threads=retain_threads,
        )
        ctx.above_primary_narrative = an
        ctx.above_primary_threads = at

    # Above fading (N+2) at grandparent address — sentence cap.
    if grandparent_address and layer + 2 <= 7:
        ctx.above_fading_address = grandparent_address
        an2, _ = get_layer_snapshot(
            store, layer=layer + 2, address=grandparent_address,
            scan_limit=scan_limit, retain_threads=0,
        )
        ctx.above_fading_narrative = _truncate_fading(an2)

    return ctx


__all__ = [
    "DEFAULT_THREAD_SCAN_LIMIT",
    "DEFAULT_ACTIVE_THREADS_RETAIN",
    "FADING_NARRATIVE_CHAR_CAP",
    "WeaverContext",
    "extract_active_threads",
    "get_layer_snapshot",
    "build_weaver_context",
]

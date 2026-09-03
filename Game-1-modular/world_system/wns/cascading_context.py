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

    # World-level currents cascading DOWN from the latest NL7 world summary
    # (M1): the dominant arcs / regions / factions currently shaping the world,
    # so every lower firing stays aligned with the top of the pyramid. Empty
    # until the world layer has fired.
    world_dominant: str = ""


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


def render_world_dominant(store: NarrativeStore) -> str:
    """Render the world's current dominant currents from the latest NL7 row's
    persisted ``world_state`` (M1 cascade-down framing). Returns "" until the
    world layer has fired or if no currents were recorded."""
    try:
        rows = store.query_by_layer(7, limit=1)
    except Exception:
        return ""
    if not rows:
        return ""
    ws = (rows[0].payload or {}).get("world_state")
    if not isinstance(ws, dict):
        return ""
    parts: List[str] = []
    for label, key in (("arcs", "dominant_arcs"),
                       ("regions", "dominant_regions"),
                       ("factions", "dominant_factions")):
        vals = ws.get(key) or []
        if vals:
            parts.append(f"{label}: " + ", ".join(str(v) for v in vals))
    if not parts:
        return ""
    sev = ws.get("severity") or "minor"
    return (f"The world is currently shaped by — {'; '.join(parts)} "
            f"(world state: {sev}).")


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


# ── Descendant aggregation (cross-layer continuity, audit C3) ─────────
# The heart of the continuity fix: a summarizing layer NL_N fires at a PARENT
# address (NL3 at district:X), but the child layer NL(N-1) wrote its rows at
# the DESCENDANT addresses (NL2 at the localities inside that district). The
# lower-layer context must therefore be gathered from the children — otherwise
# each layer summarizes nothing (the C3 break) and thread promotion has no
# lower thread_ids to promote. This mirrors how WMS gathers child-address
# events up the hierarchy. Bounded by recency so the prompt stays small.

_MAX_LOWER_SOURCES = 10  # cap child-narrative lines per weaver prompt


def _descendant_addresses(geo_registry: Any, address: str, depth: int) -> List[str]:
    """Addresses ``depth`` geographic tiers below ``address`` (depth=1 = direct
    children). Duck-typed on ``geo_registry.get_children(region_id) -> [Region]``
    where each Region has ``.level.value`` and ``.region_id``. Returns [] if the
    registry is absent or can't resolve the tree."""
    if geo_registry is None or depth < 1 or ":" not in address:
        return []
    frontier = [address]
    for _ in range(depth):
        nxt: List[str] = []
        for addr in frontier:
            _, _, rid = addr.partition(":")
            if not rid:
                continue
            try:
                children = geo_registry.get_children(rid)
            except Exception:
                children = []
            for c in children:
                try:
                    nxt.append(f"{c.level.value}:{c.region_id}")
                except Exception:
                    continue
        frontier = nxt
        if not frontier:
            break
    return frontier


def get_lower_snapshot_aggregated(
    store: NarrativeStore,
    addresses: List[str],
    *,
    lower_layer: int,
    scan_limit: int = DEFAULT_THREAD_SCAN_LIMIT,
    retain_threads: int = DEFAULT_ACTIVE_THREADS_RETAIN,
    max_sources: int = _MAX_LOWER_SOURCES,
) -> Tuple[str, List[ThreadFragment]]:
    """Aggregate NL(lower_layer) narrative + active threads across multiple
    child/descendant addresses. Narrative = latest line per source address
    (most-recent first, capped at ``max_sources``); threads are deduped across
    ALL sources (so parent_thread_id promotion gets real lower thread_ids).
    Returns ``("", [])`` when nothing is found."""
    if lower_layer < 1 or lower_layer > 7 or not addresses:
        return "", []
    all_rows: List[NarrativeRow] = []
    for addr in addresses:
        all_rows.extend(store.query_by_address(lower_layer, addr, limit=scan_limit))
    if not all_rows:
        return "", []
    all_rows.sort(key=lambda r: r.created_at, reverse=True)
    seen_addr: set = set()
    lines: List[str] = []
    for r in all_rows:
        if r.address in seen_addr:
            continue
        seen_addr.add(r.address)
        if r.narrative:
            lines.append(f"- {r.narrative}")
        if len(lines) >= max_sources:
            break
    narrative = "\n".join(lines)
    threads = extract_active_threads(all_rows, retain=retain_threads)
    return narrative, threads


# ── Composite builder ─────────────────────────────────────────────────


def build_weaver_context(
    store: NarrativeStore,
    *,
    layer: int,
    address: str,
    parent_address: Optional[str] = None,
    grandparent_address: Optional[str] = None,
    geo_registry: Any = None,
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

    # Primary lower (N-1). For NL3+ the child layer wrote at DESCENDANT
    # addresses, so aggregate the child-scope rows — the continuity link that
    # was silently empty before (audit C3). NL2's lower (NL1) sits at the SAME
    # locality, so the direct read is correct there. No registry -> old
    # behavior (keeps existing callers/tests working).
    if layer - 1 >= 1:
        if layer >= 3 and geo_registry is not None:
            n, t = get_lower_snapshot_aggregated(
                store, _descendant_addresses(geo_registry, address, 1),
                lower_layer=layer - 1, scan_limit=scan_limit,
                retain_threads=retain_threads,
            )
        else:
            n, t = get_layer_snapshot(
                store, layer=layer - 1, address=address,
                scan_limit=scan_limit, retain_threads=retain_threads,
            )
        ctx.lower_primary_narrative = n
        ctx.lower_primary_threads = t

    # Fading lower (N-2) — narrative only, truncated. NL1 sits at the locality
    # tier (same as NL2), so NL3's N-2 is one tier down; NL4+ is two tiers.
    if layer - 2 >= 1:
        if layer >= 3 and geo_registry is not None:
            fading_depth = 1 if layer == 3 else 2
            n2, _ = get_lower_snapshot_aggregated(
                store, _descendant_addresses(geo_registry, address, fading_depth),
                lower_layer=layer - 2, scan_limit=scan_limit, retain_threads=0,
            )
        else:
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

    # World currents cascade DOWN to every layer below the world (M1). NL7 is
    # the world itself — its self-continuity is its own prior narrative — so it
    # doesn't re-read its own dominant currents here.
    if layer <= 6:
        ctx.world_dominant = render_world_dominant(store)

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

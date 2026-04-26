"""WMS context builder — render the WMS slice of a WNS prompt.

Given a firing address (``locality:X`` / ``district:Y`` / etc.) and the
WMS event store, emit a single rendered text block of recent
interpretations relevant to that address. The block is char-capped to
keep the WMS contribution well under the soft 40% budget the user set
for total NL prompt context.

Design constraints:

- **Read-side only.** Builder never mutates WMS state.
- **Address-aware.** For high-tier addresses (district+), walk the
  geographic hierarchy to enumerate leaf localities, then query
  interpretations whose ``affected_locality_ids`` intersect that set.
- **Char budget enforced.** The rendered text is truncated at the cap
  with a trailing marker. Per-line render is bounded; we never blow
  past the budget by more than one line.
- **Fail-quiet.** Missing event store, registry, or address all
  produce ``""`` rather than raising — the weaver gets an empty
  ``${wms_context}`` slot in that case.

Default character budget (600) is roughly 60% of the existing
``distance_filter.full=600`` cap, intentionally sub-dominant to the
WNS-derived context (own threads + lower-layer narrative + parent
narrative). Designer can tune via ``narrative-config.json``.
"""

from __future__ import annotations

from typing import Any, List, Optional, Set

# ── Defaults ───────────────────────────────────────────────────────────

DEFAULT_CHAR_BUDGET: int = 600
DEFAULT_INTERPRETATION_LIMIT: int = 30
DEFAULT_PER_LINE_CAP: int = 200  # one interpretation's narrative slice
TRUNCATION_MARKER: str = "  [WMS context truncated to fit budget]"

# Empty render when there's nothing to show. Keeps the prompt template
# stable (the placeholder is always replaced; never left as ``${var}``).
EMPTY_RENDER: str = "(no recent WMS events)"


# ── Public API ─────────────────────────────────────────────────────────

def build_wms_brief(
    *,
    firing_address: str,
    event_store: Optional[Any],
    geographic_registry: Optional[Any] = None,
    char_budget: int = DEFAULT_CHAR_BUDGET,
    interpretation_limit: int = DEFAULT_INTERPRETATION_LIMIT,
    per_line_cap: int = DEFAULT_PER_LINE_CAP,
) -> str:
    """Render a char-capped brief of recent WMS interpretations
    relevant to ``firing_address``.

    Returns ``""`` (empty) on any unavailable input — the weaver's
    template should treat empty as ``EMPTY_RENDER`` if it wants a
    visible ``(no recent WMS events)`` slot. We deliberately return
    empty so callers can decide their own placeholder.

    Args:
        firing_address: ``"locality:X"``, ``"district:Y"``, etc.
        event_store: WMS EventStore instance. ``None`` -> ``""``.
        geographic_registry: Used to enumerate descendant localities
            for high-tier addresses. ``None`` -> only locality:* tier
            queries return content; higher tiers return ``""``.
        char_budget: Hard cap on rendered output (default 600).
        interpretation_limit: Max interpretations to consider before
            char-truncation (default 30).
        per_line_cap: Truncation cap per interpretation narrative line
            (default 200 chars).
    """
    if not firing_address or event_store is None:
        return ""

    locality_set = _resolve_descendant_localities(
        firing_address=firing_address,
        geographic_registry=geographic_registry,
    )
    if not locality_set:
        return ""

    interpretations = _fetch_relevant_interpretations(
        event_store=event_store,
        locality_set=locality_set,
        limit=interpretation_limit,
    )
    if not interpretations:
        return ""

    return _render_with_budget(
        interpretations=interpretations,
        char_budget=char_budget,
        per_line_cap=per_line_cap,
    )


# ── Internals ──────────────────────────────────────────────────────────

def _resolve_descendant_localities(
    *,
    firing_address: str,
    geographic_registry: Optional[Any],
) -> Set[str]:
    """Return the set of bare locality IDs that fall under ``firing_address``.

    ``locality:X`` always resolves to ``{X}`` even without a registry
    (so the simple/single-locality path keeps working in tests).
    Higher tiers require a registry to walk children.
    """
    if ":" not in firing_address:
        return set()
    tier, _, region_id = firing_address.partition(":")
    if not region_id:
        return set()
    if tier == "locality":
        return {region_id}
    if geographic_registry is None:
        return set()

    # BFS down the child tree, collecting any LOCALITY-tier descendants.
    out: Set[str] = set()
    seen: Set[str] = set()
    frontier: List[str] = [region_id]
    while frontier:
        current_id = frontier.pop()
        if current_id in seen:
            continue
        seen.add(current_id)
        try:
            children = geographic_registry.get_children(current_id)
        except Exception:
            children = []
        for child in children:
            child_id = getattr(child, "region_id", None)
            child_level = getattr(getattr(child, "level", None), "value", None)
            if not child_id:
                continue
            if child_level == "locality":
                out.add(child_id)
            else:
                frontier.append(child_id)
    return out


def _fetch_relevant_interpretations(
    *,
    event_store: Any,
    locality_set: Set[str],
    limit: int,
) -> List[Any]:
    """Pull recent interpretations whose ``affected_locality_ids``
    intersect ``locality_set``.

    Strategy: query a wider recent slice (up to 4× ``limit``) and
    intersect in-memory. Avoids one query per locality, which would
    be O(N localities) for high-tier fires.
    """
    try:
        # Pull a generous slice of recent interpretations across the
        # whole store; cap the working set to keep memory bounded.
        recent = event_store.query_interpretations(limit=limit * 4)
    except Exception:
        return []

    matched: List[Any] = []
    for interp in recent:
        affected = getattr(interp, "affected_locality_ids", None) or []
        if not affected:
            # Interpretations with no locality binding are skipped —
            # they apply globally and we don't want to flood every
            # WNS prompt with them. (Designer can revisit.)
            continue
        if any(loc in locality_set for loc in affected):
            matched.append(interp)
        if len(matched) >= limit:
            break
    return matched


def _render_with_budget(
    *,
    interpretations: List[Any],
    char_budget: int,
    per_line_cap: int,
) -> str:
    """Format interpretations as ``[severity] category: narrative``
    one per line, with hard char-budget enforcement.
    """
    lines: List[str] = []
    used = 0
    for interp in interpretations:
        line = _render_one(interp, per_line_cap=per_line_cap)
        if not line:
            continue
        line_cost = len(line) + 1  # newline
        if used + line_cost > char_budget:
            # Append a single truncation marker so the weaver knows
            # we capped — but only if at least one line fit.
            if lines:
                lines.append(TRUNCATION_MARKER)
            break
        lines.append(line)
        used += line_cost
    return "\n".join(lines) if lines else ""


def _render_one(interp: Any, *, per_line_cap: int) -> str:
    severity = getattr(interp, "severity", "minor") or "minor"
    category = getattr(interp, "category", "uncategorized") or "uncategorized"
    narrative = getattr(interp, "narrative", "") or ""
    narrative = narrative.strip()
    if not narrative:
        return ""
    if len(narrative) > per_line_cap:
        narrative = narrative[:per_line_cap - 1].rstrip() + "…"
    return f"[{severity}] {category}: {narrative}"


__all__ = [
    "build_wms_brief",
    "DEFAULT_CHAR_BUDGET",
    "DEFAULT_INTERPRETATION_LIMIT",
    "DEFAULT_PER_LINE_CAP",
    "EMPTY_RENDER",
]

"""Geographic context builder — turns a WNS firing address into a brief
multi-line descriptor of THIS territory and its parent chain.

Per user direction: "We will need dynamically generated prompt fragments
to tell the LLMs the position and brief characteristic of its territories."

The descriptor is injected into NL_N prompt templates as
``${geo_context}`` so each weaver knows where it sits in the world
hierarchy WITHOUT the prompt-author having to hand-write per-locality
versions.

Design choices:
- The renderer is deterministic and bounded — at most a sentence per
  parent tier so the prompt stays small.
- Missing registry / unresolvable addresses degrade gracefully to a
  single line stating the firing tier (the weaver can still produce
  output; it just won't have parent-tier color).
- Address tag format is ``<tier>:<region_id>`` (e.g.
  ``"locality:tarmouth_copperdocks"``). The same convention used by
  the WMS layer/address taxonomy.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, List, Optional, Tuple


# Description sentence cap (in characters) to keep the per-tier brief
# from blowing up the prompt budget.
DESCRIPTION_CHAR_CAP: int = 220

# Max tags shown per tier in the rendered output.
MAX_TAGS_PER_TIER: int = 5

# Order tiers should appear in the rendered descriptor (innermost-first).
# Mirrors WMS RegionLevel hierarchy.
TIER_ORDER: Tuple[str, ...] = (
    "locality", "district", "region", "province", "nation", "world",
)


@dataclass
class TierBrief:
    """One tier's contribution to the geographic descriptor."""
    tier: str             # "locality" / "district" / etc.
    region_id: str
    name: str = ""
    biome: str = ""
    description: str = ""
    tags: List[str] = field(default_factory=list)


@dataclass
class GeographicContext:
    """Structured descriptor of a firing address + its parent chain."""
    address: str
    primary_tier: str = ""
    primary_id: str = ""
    tier_briefs: List[TierBrief] = field(default_factory=list)
    rendered: str = ""


def parse_address(address: str) -> Tuple[str, str]:
    """Split an address tag ``<tier>:<region_id>`` into (tier, region_id).

    Returns ``("", "")`` if malformed. Tolerates extra colons in
    region_id (only first colon is the separator).
    """
    if not isinstance(address, str) or ":" not in address:
        return "", ""
    tier, _, region_id = address.partition(":")
    return tier.strip().lower(), region_id.strip()


def _truncate(text: str, cap: int = DESCRIPTION_CHAR_CAP) -> str:
    """Truncate text to ``cap`` chars, breaking at the last word boundary."""
    text = (text or "").strip()
    if len(text) <= cap:
        return text
    cut = text[:cap]
    last_space = cut.rfind(" ")
    if last_space > cap * 0.5:
        cut = cut[:last_space]
    return cut.rstrip(",.;:") + "…"


def _tier_brief_from_region(tier: str, region: Any) -> TierBrief:
    """Build a TierBrief from a Region-like object.

    Uses duck typing: any object with ``region_id``, ``name``,
    ``biome_primary``, ``description``, ``tags`` works.
    """
    return TierBrief(
        tier=tier,
        region_id=str(getattr(region, "region_id", "")),
        name=str(getattr(region, "name", "")),
        biome=str(getattr(region, "biome_primary", "")),
        description=_truncate(str(getattr(region, "description", ""))),
        tags=list(getattr(region, "tags", []) or [])[:MAX_TAGS_PER_TIER],
    )


def _walk_parent_chain(region: Any, registry: Any) -> List[Any]:
    """Walk parent_id chain upward, returning [region, parent, grandparent, ...].

    The walk stops at a region whose parent_id is None or missing from
    the registry. ``registry`` must have a ``regions`` dict keyed by
    region_id.
    """
    chain: List[Any] = [region]
    regions = getattr(registry, "regions", {})
    if not isinstance(regions, dict):
        return chain
    current = region
    while True:
        parent_id = getattr(current, "parent_id", None)
        if not parent_id or parent_id not in regions:
            break
        parent = regions[parent_id]
        chain.append(parent)
        current = parent
    return chain


def render_geo_context(briefs: List[TierBrief]) -> str:
    """Render a multi-line descriptor from a tier-brief list.

    Format::

        [locality] Tarmouth Copperdocks (biome=salt-marsh) — A wharf town
        of brine and copper, recently swelled by trade pressure.
        Tags: docks, copper-trade, mid-game.

        [district] Tarmouth (biome=lowlands) — ...

    Tiers without name/description still get a one-liner: ``[tier] <id>``.
    """
    parts: List[str] = []
    for b in briefs:
        header = f"[{b.tier}] " + (b.name or b.region_id)
        if b.biome:
            header += f" (biome={b.biome})"
        line = header
        if b.description:
            line += f" — {b.description}"
        if b.tags:
            line += f"\n  Tags: {', '.join(b.tags)}."
        parts.append(line)
    return "\n\n".join(parts)


def build_geographic_context(
    address: str,
    registry: Optional[Any],
) -> GeographicContext:
    """Build a structured geographic descriptor from an address.

    Args:
        address: a tag of the form ``"<tier>:<region_id>"``.
        registry: a GeographicRegistry-like object exposing
            ``.regions`` (Dict[region_id, Region]). Pass None if no
            registry is available — the result will still have
            ``rendered`` populated with a graceful fallback.

    Returns:
        :class:`GeographicContext` with structured fields and a
        ``.rendered`` string ready to interpolate into a prompt.
    """
    ctx = GeographicContext(address=address)

    tier, region_id = parse_address(address)
    ctx.primary_tier = tier
    ctx.primary_id = region_id

    if not tier or not region_id:
        ctx.rendered = (
            f"(geographic context unavailable — address {address!r} is "
            f"malformed; expected '<tier>:<region_id>')"
        )
        return ctx

    if registry is None:
        ctx.rendered = (
            f"[{tier}] {region_id} "
            f"(no registry — parent-tier briefs unavailable)"
        )
        return ctx

    regions = getattr(registry, "regions", None)
    if not isinstance(regions, dict) or region_id not in regions:
        ctx.rendered = (
            f"[{tier}] {region_id} "
            f"(region not found in registry)"
        )
        return ctx

    chain = _walk_parent_chain(regions[region_id], registry)
    # Build a TierBrief per region in the chain, using the region's own
    # level for its tier label (rather than assuming the address tier).
    briefs: List[TierBrief] = []
    for r in chain:
        level = getattr(r, "level", None)
        tier_label = (
            level.value if level is not None and hasattr(level, "value")
            else tier  # fallback to address tier for the primary
        )
        briefs.append(_tier_brief_from_region(tier_label, r))

    ctx.tier_briefs = briefs
    ctx.rendered = render_geo_context(briefs)
    return ctx


__all__ = [
    "DESCRIPTION_CHAR_CAP",
    "MAX_TAGS_PER_TIER",
    "TIER_ORDER",
    "TierBrief",
    "GeographicContext",
    "parse_address",
    "build_geographic_context",
    "render_geo_context",
]

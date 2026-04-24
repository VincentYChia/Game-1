"""Context bundle dataclasses (v4 P0 — CC2, §4.7).

The **context bundle** is the single artifact WNS authors and WES consumes.
Live queries from WES tiers are explicitly forbidden in v4; all context
that WES sees flows through this typed structure.

Three parts:

1. :class:`NarrativeDelta` — dialogue + WMS events between the previous
   firing at this layer/address and now.
2. :class:`NarrativeContextSlice` — current narrative state at the firing's
   layer + parent addresses (bottom-up, shallow-going-outward).
3. :class:`WNSDirective` — WNS's high-level instruction to WES on what to
   create. For WES bundles only.

The top-level :class:`WESContextBundle` owns all three.

Q11 (§9) flags the dataclass shape as "still open" — this P0 module is
the schema sketch. P5 will finalize the shape as a first-class WES input;
until then, downstream phases build against these types.

Every field is JSON-serializable via :meth:`to_dict` / :meth:`from_dict`;
logs persist bundles as ``bundle.json`` next to the plan logs.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


# ── Leaf types ────────────────────────────────────────────────────────

@dataclass
class NL1Row:
    """One NL1 capture entry — a pre-generated NPC dialogue fragment plus
    extracted mentions. See §4.4 / CC6."""

    event_id: str
    created_at: float
    npc_id: str
    address: str                        # e.g. "locality:tarmouth_ironrow"
    dialogue_text: str
    extracted_mentions: List[Dict[str, Any]] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "created_at": self.created_at,
            "npc_id": self.npc_id,
            "address": self.address,
            "dialogue_text": self.dialogue_text,
            "extracted_mentions": list(self.extracted_mentions),
            "tags": list(self.tags),
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "NL1Row":
        return cls(
            event_id=d["event_id"],
            created_at=float(d["created_at"]),
            npc_id=d["npc_id"],
            address=d["address"],
            dialogue_text=d["dialogue_text"],
            extracted_mentions=list(d.get("extracted_mentions", [])),
            tags=list(d.get("tags", [])),
        )


@dataclass
class WMSLayerRow:
    """Lightweight reference to a WMS layer event that WNS is bringing
    into the bundle as delta context."""

    event_id: str
    layer: int                          # 2..7
    created_at: float
    address: str
    narrative: str
    tags: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "layer": int(self.layer),
            "created_at": self.created_at,
            "address": self.address,
            "narrative": self.narrative,
            "tags": list(self.tags),
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "WMSLayerRow":
        return cls(
            event_id=d["event_id"],
            layer=int(d["layer"]),
            created_at=float(d["created_at"]),
            address=d["address"],
            narrative=d["narrative"],
            tags=list(d.get("tags", [])),
        )


@dataclass
class ThreadFragment:
    """A narrative thread fragment — first-class at every weaving layer
    (v4 change from v3 where threads lived only at NL2). See §4.5."""

    fragment_id: str
    layer: int                          # 2..7
    address: str
    headline: str
    content_tags: List[str] = field(default_factory=list)
    parent_thread_id: Optional[str] = None
    relationship: str = "open"          # open | continue | reframe | close
    created_at: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "fragment_id": self.fragment_id,
            "layer": int(self.layer),
            "address": self.address,
            "headline": self.headline,
            "content_tags": list(self.content_tags),
            "parent_thread_id": self.parent_thread_id,
            "relationship": self.relationship,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "ThreadFragment":
        return cls(
            fragment_id=d["fragment_id"],
            layer=int(d["layer"]),
            address=d["address"],
            headline=d["headline"],
            content_tags=list(d.get("content_tags", [])),
            parent_thread_id=d.get("parent_thread_id"),
            relationship=d.get("relationship", "open"),
            created_at=float(d.get("created_at", 0.0)),
        )


# ── Part 1: delta ─────────────────────────────────────────────────────

@dataclass
class NarrativeDelta:
    """Dialogue + WMS events between WNS's previous firing at this
    layer/address and now. See §4.7 bundle shape."""

    address: str                        # firing address
    layer: int                          # firing tier, 2..7
    start_time: float                   # game time of previous firing
    end_time: float                     # game time of this firing
    npc_dialogue_since_last: List[NL1Row] = field(default_factory=list)
    wms_events_since_last: List[WMSLayerRow] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "address": self.address,
            "layer": int(self.layer),
            "start_time": self.start_time,
            "end_time": self.end_time,
            "npc_dialogue_since_last": [r.to_dict() for r in self.npc_dialogue_since_last],
            "wms_events_since_last": [r.to_dict() for r in self.wms_events_since_last],
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "NarrativeDelta":
        return cls(
            address=d["address"],
            layer=int(d["layer"]),
            start_time=float(d["start_time"]),
            end_time=float(d["end_time"]),
            npc_dialogue_since_last=[
                NL1Row.from_dict(r) for r in d.get("npc_dialogue_since_last", [])
            ],
            wms_events_since_last=[
                WMSLayerRow.from_dict(r) for r in d.get("wms_events_since_last", [])
            ],
        )


# ── Part 2: narrative context ────────────────────────────────────────

@dataclass
class NarrativeContextSlice:
    """Current narrative state at the firing's layer + parent addresses.

    Shallow-going-outward (§8.8): full detail at firing layer; brief summaries
    at parent addresses; sibling addresses not included unless threaded.

    parent_summaries is keyed by ``"{layer}:{address}"`` (e.g. ``"5:nation:valdren"``)
    for deterministic ordering.
    """

    firing_layer_summary: str
    parent_summaries: Dict[str, str] = field(default_factory=dict)
    open_threads: List[ThreadFragment] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "firing_layer_summary": self.firing_layer_summary,
            "parent_summaries": dict(self.parent_summaries),
            "open_threads": [t.to_dict() for t in self.open_threads],
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "NarrativeContextSlice":
        return cls(
            firing_layer_summary=d.get("firing_layer_summary", ""),
            parent_summaries=dict(d.get("parent_summaries", {})),
            open_threads=[ThreadFragment.from_dict(t) for t in d.get("open_threads", [])],
        )


# ── Part 3: directive ─────────────────────────────────────────────────

@dataclass
class WNSDirective:
    """WNS's high-level instruction to WES. Authored by the weaving LLM
    that decided to call WES (preferred, §4.7). WES bundles only."""

    directive_text: str
    firing_tier: int                    # 2..7; drives planner scope
    scope_hint: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "directive_text": self.directive_text,
            "firing_tier": int(self.firing_tier),
            "scope_hint": dict(self.scope_hint),
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "WNSDirective":
        return cls(
            directive_text=d["directive_text"],
            firing_tier=int(d["firing_tier"]),
            scope_hint=dict(d.get("scope_hint", {})),
        )


# ── Top-level bundle ─────────────────────────────────────────────────

@dataclass
class WESContextBundle:
    """Top-level bundle handed from WNS to WES. The single artifact WES reads.

    Serialization is used for both observability logs (bundle.json next to
    plan logs) and (eventually) for replay-based testing.
    """

    bundle_id: str
    created_at: float
    delta: NarrativeDelta
    narrative_context: NarrativeContextSlice
    directive: WNSDirective
    source_narrative_layer_ids: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "bundle_id": self.bundle_id,
            "created_at": self.created_at,
            "delta": self.delta.to_dict(),
            "narrative_context": self.narrative_context.to_dict(),
            "directive": self.directive.to_dict(),
            "source_narrative_layer_ids": list(self.source_narrative_layer_ids),
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "WESContextBundle":
        return cls(
            bundle_id=d["bundle_id"],
            created_at=float(d["created_at"]),
            delta=NarrativeDelta.from_dict(d["delta"]),
            narrative_context=NarrativeContextSlice.from_dict(d["narrative_context"]),
            directive=WNSDirective.from_dict(d["directive"]),
            source_narrative_layer_ids=list(d.get("source_narrative_layer_ids", [])),
        )


# ── Tool-specific slice (hub input) ──────────────────────────────────

@dataclass
class BundleToolSlice:
    """A tool-specific view of a :class:`WESContextBundle`, extracted
    deterministically by code for a given hub. Hubs receive this instead
    of the full bundle so their context stays focused (§8.5).

    Populated from :class:`WESContextBundle` via :func:`slice_bundle_for_tool`.
    """

    tool_name: str
    bundle_id: str
    firing_tier: int
    directive_text: str
    address_hint: str
    threads_in_focal_address: List[ThreadFragment] = field(default_factory=list)
    recent_registry_entries: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "tool_name": self.tool_name,
            "bundle_id": self.bundle_id,
            "firing_tier": int(self.firing_tier),
            "directive_text": self.directive_text,
            "address_hint": self.address_hint,
            "threads_in_focal_address": [t.to_dict() for t in self.threads_in_focal_address],
            "recent_registry_entries": list(self.recent_registry_entries),
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "BundleToolSlice":
        return cls(
            tool_name=d["tool_name"],
            bundle_id=d["bundle_id"],
            firing_tier=int(d["firing_tier"]),
            directive_text=d["directive_text"],
            address_hint=d["address_hint"],
            threads_in_focal_address=[
                ThreadFragment.from_dict(t)
                for t in d.get("threads_in_focal_address", [])
            ],
            recent_registry_entries=list(d.get("recent_registry_entries", [])),
        )


def slice_bundle_for_tool(
    bundle: WESContextBundle,
    tool_name: str,
    recent_registry_entries: Optional[List[Dict[str, Any]]] = None,
) -> BundleToolSlice:
    """Deterministic extraction of a hub's view of the bundle.

    The hub gets:
    - the directive text (authoritative framing)
    - the firing address (so it weights same-address narrative)
    - the open threads in the focal address (flavor)
    - a caller-supplied slice of recent same-type registry entries (diversity)

    Hub does NOT get the full delta (irrelevant to a shape-filler) or
    parent-address summaries (only the planner needs the wide view).
    """

    return BundleToolSlice(
        tool_name=tool_name,
        bundle_id=bundle.bundle_id,
        firing_tier=bundle.directive.firing_tier,
        directive_text=bundle.directive.directive_text,
        address_hint=bundle.delta.address,
        threads_in_focal_address=[
            t for t in bundle.narrative_context.open_threads
            if t.address == bundle.delta.address
        ],
        recent_registry_entries=list(recent_registry_entries or []),
    )

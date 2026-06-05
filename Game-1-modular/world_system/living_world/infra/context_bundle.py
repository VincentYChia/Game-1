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
    (v4 change from v3 where threads lived only at NL2). See §4.5.

    Identity model:
    - fragment_id: unique per-instance UUID (one per LLM weaving emission).
    - thread_id: cluster identity at THIS layer/address. Multiple fragments
      share thread_id when their content_tags overlap enough (see
      world_system.wns.thread_index). Server-assigned, NOT LLM-emitted.
    - parent_thread_id: a thread_id at a LOWER layer that this fragment
      aggregates from (cross-layer bottom-up promotion).
    """

    fragment_id: str
    layer: int                          # 2..7
    address: str
    headline: str
    content_tags: List[str] = field(default_factory=list)
    thread_id: Optional[str] = None      # cluster id at this layer/address
    parent_thread_id: Optional[str] = None  # thread_id at LOWER layer
    relationship: str = "open"          # open | continue | reframe | close
    created_at: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "fragment_id": self.fragment_id,
            "layer": int(self.layer),
            "address": self.address,
            "headline": self.headline,
            "content_tags": list(self.content_tags),
            "thread_id": self.thread_id,
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
            thread_id=d.get("thread_id"),
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
class BehaviorSignal:
    """Phase 2 (2026-06-03) — the behavior-causal trigger payload.

    Populated by the WNS BehaviorInterpreter when a WMS milestone
    crosses a threshold that the dispatch-rules table says warrants
    a WES dispatch. Carries enough context for the planner to author
    a tier-appropriate plan and for the supervisor to verify the
    behavior-artifact fidelity (check 7).

    Field semantics:
        counter_path: the StatStore counter that fired (e.g.
            "combat.kills.locality.tarmouth"). Drives the
            BEHAVIOR FIDELITY supervisor check — staged content must
            reference this artifact (kills → hostile/skill).
        threshold_crossed: the THRESHOLD_SET value reached
            (e.g. 1000).
        stream_count: the current StatStore count (post-threshold).
        locality_id: the WMS locality where this fired
            (e.g. "tarmouth").
        activity_profile: per-locality discipline-mix dict from
            ``StatStore.activity_profile()`` (7 canonical categories).
        inferred_behavior_intent: 1-2 sentence interpretation of what
            the player has been DOING (the "Looking at the ledger
            the WNS thinks that the player is using them in combat"
            step from the user's pseudo-trace).
        matching_pool_entries: existing content IDs the
            BehaviorInterpreter already considered as candidates.
            Empty = pool gap; non-empty = pool overlap (supervisor
            check 8 — pool-gap rationality).
    """

    counter_path: str
    threshold_crossed: int
    stream_count: int
    locality_id: str
    activity_profile: Dict[str, float] = field(default_factory=dict)
    inferred_behavior_intent: str = ""
    matching_pool_entries: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "counter_path": self.counter_path,
            "threshold_crossed": int(self.threshold_crossed),
            "stream_count": int(self.stream_count),
            "locality_id": self.locality_id,
            "activity_profile": dict(self.activity_profile),
            "inferred_behavior_intent": self.inferred_behavior_intent,
            "matching_pool_entries": list(self.matching_pool_entries),
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "BehaviorSignal":
        return cls(
            counter_path=d["counter_path"],
            threshold_crossed=int(d["threshold_crossed"]),
            stream_count=int(d["stream_count"]),
            locality_id=d["locality_id"],
            activity_profile=dict(d.get("activity_profile", {})),
            inferred_behavior_intent=d.get("inferred_behavior_intent", ""),
            matching_pool_entries=list(d.get("matching_pool_entries", [])),
        )


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
    # Phase 2 (2026-06-03): behavior-causal payload. None on
    # narrative-causal firings (the only path that existed before
    # Phase 2). Populated by the WNS BehaviorInterpreter when a
    # WMS milestone trips. Mirrors trigger_archetype in scope_hint.
    behavior_signal: Optional[BehaviorSignal] = None

    def to_dict(self) -> Dict[str, Any]:
        out = {
            "bundle_id": self.bundle_id,
            "created_at": self.created_at,
            "delta": self.delta.to_dict(),
            "narrative_context": self.narrative_context.to_dict(),
            "directive": self.directive.to_dict(),
            "source_narrative_layer_ids": list(self.source_narrative_layer_ids),
        }
        if self.behavior_signal is not None:
            out["behavior_signal"] = self.behavior_signal.to_dict()
        return out

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "WESContextBundle":
        sig_dict = d.get("behavior_signal")
        return cls(
            bundle_id=d["bundle_id"],
            created_at=float(d["created_at"]),
            delta=NarrativeDelta.from_dict(d["delta"]),
            narrative_context=NarrativeContextSlice.from_dict(d["narrative_context"]),
            directive=WNSDirective.from_dict(d["directive"]),
            source_narrative_layer_ids=list(d.get("source_narrative_layer_ids", [])),
            behavior_signal=(
                BehaviorSignal.from_dict(sig_dict)
                if sig_dict else None
            ),
        )


# ── Tool-specific slice (hub input) ──────────────────────────────────

@dataclass
class BundleToolSlice:
    """A tool-specific view of a :class:`WESContextBundle`, extracted
    deterministically by code for a given hub. Hubs receive this instead
    of the full bundle so their context stays focused (§8.5).

    Populated from :class:`WESContextBundle` via :func:`slice_bundle_for_tool`.

    **Phase 1 extension (2026-06-03)**: post-trace-pass consolidation §2.2
    extends the slice with narrative-context fields that the prior shape
    stripped at the bundle→hub boundary. Every content tool now reads
    `firing_layer_summary`, `parent_summaries`, `geographic_chain`,
    `threads_in_parent_addresses`, `wms_events_since_last`,
    `npc_dialogue_since_last`, and `trigger_archetype`. This is THE
    fix that closes the "disconnected-from-narrative" failure mode
    across all 8 content tools — one slice extension, eight wins.
    """

    tool_name: str
    bundle_id: str
    firing_tier: int
    directive_text: str
    address_hint: str
    threads_in_focal_address: List[ThreadFragment] = field(default_factory=list)
    recent_registry_entries: List[Dict[str, Any]] = field(default_factory=list)
    # ── Phase 1 narrative-propagation fields ─────────────────────────
    firing_layer_summary: str = ""
    parent_summaries: Dict[str, str] = field(default_factory=dict)
    geographic_chain: List[Dict[str, Any]] = field(default_factory=list)
    threads_in_parent_addresses: List[ThreadFragment] = field(default_factory=list)
    wms_events_since_last: List["WMSLayerRow"] = field(default_factory=list)
    npc_dialogue_since_last: List["NL1Row"] = field(default_factory=list)
    # ── Phase 2 archetype + behavior signal ──────────────────────────
    # ``trigger_archetype`` defaults to "narrative" — the only path the
    # pipeline supports today. Phase 2 BehaviorInterpreter sets
    # "behavior" or "mixed". Tools/hubs can branch on this without a
    # schema migration.
    trigger_archetype: str = "narrative"
    behavior_signal: Optional[BehaviorSignal] = None

    def to_dict(self) -> Dict[str, Any]:
        out = {
            "tool_name": self.tool_name,
            "bundle_id": self.bundle_id,
            "firing_tier": int(self.firing_tier),
            "directive_text": self.directive_text,
            "address_hint": self.address_hint,
            "threads_in_focal_address": [t.to_dict() for t in self.threads_in_focal_address],
            "recent_registry_entries": list(self.recent_registry_entries),
            "firing_layer_summary": self.firing_layer_summary,
            "parent_summaries": dict(self.parent_summaries),
            "geographic_chain": list(self.geographic_chain),
            "threads_in_parent_addresses": [
                t.to_dict() for t in self.threads_in_parent_addresses
            ],
            "wms_events_since_last": [
                r.to_dict() for r in self.wms_events_since_last
            ],
            "npc_dialogue_since_last": [
                r.to_dict() for r in self.npc_dialogue_since_last
            ],
            "trigger_archetype": self.trigger_archetype,
        }
        if self.behavior_signal is not None:
            out["behavior_signal"] = self.behavior_signal.to_dict()
        return out

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
            firing_layer_summary=d.get("firing_layer_summary", ""),
            parent_summaries=dict(d.get("parent_summaries", {})),
            geographic_chain=list(d.get("geographic_chain", [])),
            threads_in_parent_addresses=[
                ThreadFragment.from_dict(t)
                for t in d.get("threads_in_parent_addresses", [])
            ],
            wms_events_since_last=[
                WMSLayerRow.from_dict(r)
                for r in d.get("wms_events_since_last", [])
            ],
            npc_dialogue_since_last=[
                NL1Row.from_dict(r)
                for r in d.get("npc_dialogue_since_last", [])
            ],
            trigger_archetype=d.get("trigger_archetype", "narrative"),
            behavior_signal=(
                BehaviorSignal.from_dict(d["behavior_signal"])
                if d.get("behavior_signal") else None
            ),
        )


def slice_bundle_for_tool(
    bundle: WESContextBundle,
    tool_name: str,
    recent_registry_entries: Optional[List[Dict[str, Any]]] = None,
) -> BundleToolSlice:
    """Deterministic extraction of a hub's view of the bundle.

    Phase 1 contract (2026-06-03): the slice now carries the full
    narrative-context fields (firing_layer_summary, parent_summaries,
    geographic_chain, parent-address threads, WMS events delta, NPC
    dialogue delta, trigger_archetype). The previous "thin shape-filler"
    contract caused every content tool to write narrative-blind
    content. One slice extension, eight tools win.

    The hub gets:
    - the directive text (authoritative framing)
    - the firing address (so it weights same-address narrative)
    - the open threads in the focal address (flavor) — full payloads
    - the open threads at parent addresses (cascading arc context)
    - the firing-layer summary (what the weaver just said)
    - the parent summaries (cascading-down narrative)
    - the geographic chain (locality→world tier briefs)
    - the WMS events + NPC dialogue delta since previous firing
    - the trigger archetype (narrative / behavior / mixed)
    - a caller-supplied slice of recent same-type registry entries
    """
    focal = bundle.delta.address
    return BundleToolSlice(
        tool_name=tool_name,
        bundle_id=bundle.bundle_id,
        firing_tier=bundle.directive.firing_tier,
        directive_text=bundle.directive.directive_text,
        address_hint=focal,
        threads_in_focal_address=[
            t for t in bundle.narrative_context.open_threads
            if t.address == focal
        ],
        recent_registry_entries=list(recent_registry_entries or []),
        firing_layer_summary=bundle.narrative_context.firing_layer_summary,
        parent_summaries=dict(bundle.narrative_context.parent_summaries),
        geographic_chain=list(
            bundle.directive.scope_hint.get("geographic_chain", []) or []
        ),
        threads_in_parent_addresses=[
            t for t in bundle.narrative_context.open_threads
            if t.address != focal
        ],
        wms_events_since_last=list(bundle.delta.wms_events_since_last),
        npc_dialogue_since_last=list(bundle.delta.npc_dialogue_since_last),
        trigger_archetype=bundle.directive.scope_hint.get(
            "trigger_archetype", "narrative",
        ),
        behavior_signal=bundle.behavior_signal,
    )

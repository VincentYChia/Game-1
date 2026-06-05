"""WNS → WES context inheritance.

Per user direction: "Ensure that the WES also automatically gets most
if not all the context the WNS had."

When an NL_N weaver emits an inline ``<WES purpose="...">body</WES>``
directive, the runtime needs to construct a :class:`WESContextBundle`
that carries:

- The weaver's firing address + layer (drives WES planner scope).
- The directive_text + purpose (the LLM's directive body).
- The narrative the weaver just wrote (firing_layer_summary).
- The cascading-down summary from above (parent_summaries).
- The active threads at the firing address (open_threads).
- The geographic context as a structured scope_hint (so the WES planner
  can read it without re-querying the registry).

This module is the BUILDER. It is a pure function — give it the parts,
get a bundle. The NL weaver wires it up at the call site and attaches
the serialized bundle to the published WNS_CALL_WES_REQUESTED event so
WES subscribers can dispatch against it directly.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence

from world_system.living_world.infra.context_bundle import (
    NarrativeContextSlice,
    NarrativeDelta,
    NL1Row,
    ThreadFragment,
    WESContextBundle,
    WMSLayerRow,
    WNSDirective,
)
from world_system.wns.cascading_context import WeaverContext
from world_system.wns.geographic_context import GeographicContext
from world_system.wns.wes_call_parser import WESCall


def _layer_to_firing_tier(nl_layer: int) -> int:
    """Map an NL layer (2-7) to the firing_tier the WES planner uses.

    The mapping is identity here — both systems use the same 1-7
    address-tier scale (chunk=1, locality=2, district=3, region=4,
    province=5, nation=6, world=7). Documented for clarity in case
    they ever drift apart.
    """
    return int(nl_layer)


def _trim_threads(
    threads: Sequence[ThreadFragment],
    max_count: int = 5,
) -> List[ThreadFragment]:
    """Keep the most recent N threads. The bundle should stay bounded
    so WES planners don't drown in context.
    """
    if not threads:
        return []
    sorted_t = sorted(
        threads, key=lambda t: t.created_at, reverse=True
    )
    return list(sorted_t[:max_count])


def _build_parent_summaries(
    weaver_ctx: WeaverContext,
) -> Dict[str, str]:
    """Construct ``parent_summaries`` keyed by ``"{layer}:{address}"``.

    Includes the cascade-from-above slots (N+1, N+2) where present, plus
    the same-layer self-narrative (so WES knows what the weaver just
    said). Empty entries are skipped.
    """
    summaries: Dict[str, str] = {}

    if weaver_ctx.self_latest_narrative:
        # Same-layer continuity is "what we just said at this address".
        summaries[f"{weaver_ctx.layer}:{weaver_ctx.address}"] = (
            weaver_ctx.self_latest_narrative
        )

    if weaver_ctx.above_primary_narrative and weaver_ctx.above_primary_address:
        summaries[f"{weaver_ctx.layer + 1}:{weaver_ctx.above_primary_address}"] = (
            weaver_ctx.above_primary_narrative
        )

    if weaver_ctx.above_fading_narrative and weaver_ctx.above_fading_address:
        summaries[f"{weaver_ctx.layer + 2}:{weaver_ctx.above_fading_address}"] = (
            weaver_ctx.above_fading_narrative
        )

    return summaries


def _build_scope_hint(
    address: str,
    geo_ctx: Optional[GeographicContext],
    weaver_layer: int,
) -> Dict[str, Any]:
    """Compose a scope_hint dict the WES planner can read.

    Includes:
    - ``firing_address`` (the WNS address that triggered)
    - ``geographic_descriptor`` (rendered text from GeographicContext)
    - ``geographic_chain`` (structured tier briefs, if available)
    - ``weaver_layer`` (the NL layer that fired)
    """
    scope: Dict[str, Any] = {
        "firing_address": address,
        "weaver_layer": int(weaver_layer),
    }
    if geo_ctx is not None:
        scope["geographic_descriptor"] = geo_ctx.rendered or ""
        if geo_ctx.tier_briefs:
            scope["geographic_chain"] = [
                {
                    "tier": b.tier,
                    "region_id": b.region_id,
                    "name": b.name,
                    "biome": b.biome,
                    "description": b.description,
                    "tags": list(b.tags),
                }
                for b in geo_ctx.tier_briefs
            ]
    return scope


def _build_narrative_delta(
    weaver_ctx: WeaverContext,
    just_written_narrative: str,
    game_time: float,
    *,
    npc_dialogue: Optional[Sequence["NL1Row"]] = None,
    wms_events: Optional[Sequence["WMSLayerRow"]] = None,
    previous_firing_time: Optional[float] = None,
) -> NarrativeDelta:
    """Synthesize a NarrativeDelta from the weaver's just-completed run.

    The delta carries (npc_dialogue, wms_events) between the previous
    WNS firing at this layer/address and now. Per Phase 0 G02
    (2026-06-03), this function accepts the per-firing rows as
    optional inputs so callers (the nl_weaver) can wire actual data
    when available; otherwise the lists stay empty without losing the
    address/layer/time framing.

    Phase 1 wires the data sources at the nl_weaver call site
    (`world_system/wns/nl_weaver.py`). For Phase 0 this just exposes
    the parameters so the contract is in place.

    Args:
        weaver_ctx: the WeaverContext the weaver consumed (carries
            address + layer).
        just_written_narrative: the narrative just written; unused at
            the delta level but retained for symmetry with the
            other builder signatures.
        game_time: this-firing timestamp.
        npc_dialogue: optional dialogue rows from NL1 between the
            previous firing and now.
        wms_events: optional WMS L2 interpretation rows in the same
            window.
        previous_firing_time: optional timestamp of the previous WNS
            firing at this address/layer; defaults to ``game_time``
            (zero-width window) when not provided.
    """
    del just_written_narrative  # retained for caller symmetry
    start = (
        float(previous_firing_time)
        if previous_firing_time is not None
        else float(game_time)
    )
    return NarrativeDelta(
        address=weaver_ctx.address,
        layer=int(weaver_ctx.layer),
        start_time=start,
        end_time=float(game_time),
        npc_dialogue_since_last=list(npc_dialogue) if npc_dialogue else [],
        wms_events_since_last=list(wms_events) if wms_events else [],
    )


def build_wes_bundle(
    *,
    layer: int,
    address: str,
    wes_call: WESCall,
    weaver_ctx: WeaverContext,
    geo_ctx: Optional[GeographicContext],
    just_written_narrative: str,
    source_row_id: str,
    game_time: Optional[float] = None,
    npc_dialogue_since_last: Optional[Sequence["NL1Row"]] = None,
    wms_events_since_last: Optional[Sequence["WMSLayerRow"]] = None,
    previous_firing_time: Optional[float] = None,
) -> WESContextBundle:
    """Assemble a WESContextBundle inheriting WNS state.

    Args:
        layer: the NL layer (2-7) firing this <WES> call.
        address: firing address.
        wes_call: the parsed inline <WES> directive (purpose + body).
        weaver_ctx: the WeaverContext the weaver consumed.
        geo_ctx: optional geographic descriptor for the firing address.
        just_written_narrative: the narrative the weaver just produced
            (post-WES-tag-cleaning).
        source_row_id: the NarrativeRow id this bundle traces back to.
        game_time: timestamp; defaults to wall clock.
        npc_dialogue_since_last: optional NL1 dialogue rows from the
            previous firing window. When provided, populates
            ``delta.npc_dialogue_since_last`` so WES tools can read
            recent NPC voice. Phase 0 G02 (2026-06-03) added this
            channel; Phase 1 wires the actual data source at the
            nl_weaver call site.
        wms_events_since_last: optional WMS L2 interpretation rows
            from the same window. When provided, populates
            ``delta.wms_events_since_last`` so WES tools can read the
            factual delta.
        previous_firing_time: optional timestamp of the previous WNS
            firing at this address/layer; used as the delta's
            ``start_time`` when populated.

    Returns:
        A WESContextBundle ready to feed to ``WESOrchestrator.run_plan``.
    """
    if game_time is None:
        game_time = time.time()

    # Phase 1 contract (2026-06-03): include BOTH focal-address threads
    # AND parent-address threads in open_threads, so the slice can
    # separate them by address downstream. Without parent threads in
    # the bundle, locality-tier content has no cascading arc context.
    focal_threads = _trim_threads(weaver_ctx.self_active_threads, max_count=5)
    parent_threads = _trim_threads(
        getattr(weaver_ctx, "above_primary_threads", []) or [],
        max_count=3,
    )
    all_threads = list(focal_threads) + list(parent_threads)

    narrative_context = NarrativeContextSlice(
        firing_layer_summary=just_written_narrative,
        parent_summaries=_build_parent_summaries(weaver_ctx),
        open_threads=all_threads,
    )

    directive = WNSDirective(
        directive_text=wes_call.body,
        firing_tier=_layer_to_firing_tier(layer),
        scope_hint=_build_scope_hint(address, geo_ctx, layer)
        | {"purpose": wes_call.purpose},
    )

    delta = _build_narrative_delta(
        weaver_ctx,
        just_written_narrative,
        game_time,
        npc_dialogue=npc_dialogue_since_last,
        wms_events=wms_events_since_last,
        previous_firing_time=previous_firing_time,
    )

    return WESContextBundle(
        bundle_id=f"wns_to_wes_{uuid.uuid4().hex[:12]}",
        created_at=game_time,
        delta=delta,
        narrative_context=narrative_context,
        directive=directive,
        source_narrative_layer_ids=[source_row_id] if source_row_id else [],
    )


__all__ = [
    "build_wes_bundle",
]

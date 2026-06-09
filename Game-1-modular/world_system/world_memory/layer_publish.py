"""Shared bus-publish helpers for WMS layer events (2026-06-05).

Layers 3-7 each publish a ``WMS_LAYER_{N}_SUMMARY_CREATED`` bus event
after the SQL write of a new summary, so the WMS→WNS bridge can fire
NL_N directly at the same address (Model C "peak path"). See
``Development-Plan/WMS_WNS_LAYER_CORRESPONDENCE.md`` §5.3.

The publish is best-effort: any failure here MUST NEVER corrupt SQL
state or block the next-layer callback. Each caller wraps its
``_publish_layer_summary_created`` call in a try/except for that
reason.

Also exposes ``_publish_dialogue_captured`` for NL1 ingestion to
feed WMS triggers (per user direction 2026-06-05: dialogue and
events count point-wise equal in the weighted-bucket system; Layer 3
subscribes to receive dialogue at the same intake granularity as
``on_layer2_created``).
"""

from __future__ import annotations

from typing import List, Optional


_LAYER_TO_EVENT: dict[int, str] = {
    3: "WMS_LAYER_3_SUMMARY_CREATED",
    4: "WMS_LAYER_4_SUMMARY_CREATED",
    5: "WMS_LAYER_5_SUMMARY_CREATED",
    6: "WMS_LAYER_6_SUMMARY_CREATED",
    7: "WMS_LAYER_7_SUMMARY_CREATED",
}


def _resolve_address_from_tags(layer: int, tags: List[str]) -> Optional[str]:
    """Return the tier-appropriate address tag for ``layer``.

    Layer 3 summaries are addressed at the ``district:`` tier;
    Layer 4 at ``province:``; Layer 5 at ``region:``; Layer 6 at
    ``nation:``; Layer 7 at ``world:``. Address tags are facts assigned
    at L2 capture per WORLD_MEMORY_SYSTEM.md §6 (the doc calls them
    "address tags") — so a single-tag lookup is sufficient.
    """
    prefix_for_layer = {
        3: "district:",
        4: "province:",
        5: "region:",
        6: "nation:",
        7: "world:",
    }.get(layer)
    if not prefix_for_layer:
        return None
    for tag in tags:
        if isinstance(tag, str) and tag.startswith(prefix_for_layer):
            return tag
    return None


def _publish_layer_summary_created(
    *,
    layer: int,
    event_id: str,
    tags: List[str],
    category: str,
    severity: str,
    game_time: float,
) -> None:
    """Publish ``WMS_LAYER_{N}_SUMMARY_CREATED`` on the GameEventBus.

    Best-effort: returns silently on any failure (no bus, publish
    raises, address unresolvable). Callers MUST wrap in their own
    try/except as a defence-in-depth measure — see the per-layer
    manager call sites.
    """
    topic = _LAYER_TO_EVENT.get(int(layer))
    if not topic:
        return
    address = _resolve_address_from_tags(layer, tags) or ""
    if not address:
        # No address tag — the summary still exists in SQL but the
        # bridge has nothing to fire NL_N at. Don't publish a partial
        # event; downstream depends on address.
        return
    try:
        from events.event_bus import get_event_bus
    except Exception:
        return
    try:
        bus = get_event_bus()
    except Exception:
        return
    try:
        bus.publish(
            topic,
            {
                "layer": int(layer),
                "event_id": event_id,
                "address": address,
                "tags": list(tags),
                "category": category,
                "severity": severity,
                "game_time": float(game_time),
            },
        )
    except Exception:
        return


def _publish_dialogue_captured(
    *,
    npc_id: str,
    address: str,
    tags: List[str],
    narrative: str,
    game_time: float,
) -> None:
    """Publish ``WMS_DIALOGUE_CAPTURED`` so Layer3Manager can feed
    dialogue into the same trigger machinery it uses for L2
    interpretations.

    Best-effort, same failure model as
    :func:`_publish_layer_summary_created`.
    """
    try:
        from events.event_bus import get_event_bus
    except Exception:
        return
    try:
        bus = get_event_bus()
    except Exception:
        return
    try:
        bus.publish(
            "WMS_DIALOGUE_CAPTURED",
            {
                "npc_id": npc_id,
                "address": address,
                "tags": list(tags),
                "narrative": narrative,
                "game_time": float(game_time),
            },
        )
    except Exception:
        return

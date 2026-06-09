"""Tests for the WMS↔WNS layer-correspondence wiring (Model C +
dialogue→WMS feed).

Design ref: ``Development-Plan/WMS_WNS_LAYER_CORRESPONDENCE.md``.

Each test covers one link in the chain and asserts behaviour against
the (file, line) of the relevant code change. Layered out so a
regression points the reader directly at the affected change.
"""

from __future__ import annotations

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ── Phase 1a: LayerStore reads ───────────────────────────────────────


def test_layer_store_get_recent_layer_event_returns_none_for_empty_store(tmp_path):
    """``get_recent_layer_event`` returns None when no rows match."""
    from world_system.world_memory.layer_store import LayerStore

    store = LayerStore(db_path=str(tmp_path / "ls.db"))
    out = store.get_recent_layer_event(5, "region:nowhere")
    assert out is None


def test_layer_store_get_recent_layer_event_returns_match(tmp_path):
    """A written L5 event is found by address."""
    from world_system.world_memory.layer_store import LayerStore

    store = LayerStore(db_path=str(tmp_path / "ls.db"))
    eid = store.insert_event(
        layer=5,
        narrative="Coastal trade flourishes in Silverdocks.",
        game_time=1.0,
        category="region_summary",
        severity="minor",
        significance="minor",
        tags=["region:silverdocks", "domain:economy"],
    )
    out = store.get_recent_layer_event(5, "region:silverdocks")
    assert out is not None
    assert out["id"] == eid
    assert "Coastal trade" in out["narrative"]


def test_layer_store_get_layer_events_for_address_limits(tmp_path):
    """Limit cap respected, ordering newest-first."""
    from world_system.world_memory.layer_store import LayerStore

    store = LayerStore(db_path=str(tmp_path / "ls.db"))
    for i in range(5):
        store.insert_event(
            layer=4,
            narrative=f"e{i}",
            game_time=float(i),
            category="province_summary",
            severity="minor",
            significance="minor",
            tags=["province:foo"],
        )
    rows = store.get_layer_events_for_address(4, "province:foo", limit=3)
    assert len(rows) == 3
    # Newest first (highest game_time first)
    assert rows[0]["narrative"] == "e4"
    assert rows[1]["narrative"] == "e3"
    assert rows[2]["narrative"] == "e2"


def test_layer_store_rejects_bad_layer_or_address(tmp_path):
    """Out-of-range layer or malformed address returns empty list."""
    from world_system.world_memory.layer_store import LayerStore

    store = LayerStore(db_path=str(tmp_path / "ls.db"))
    assert store.get_layer_events_for_address(1, "region:x") == []
    assert store.get_layer_events_for_address(8, "region:x") == []
    assert store.get_layer_events_for_address(5, "bad_no_colon") == []


# ── Phase 1c: layer_publish helpers + address resolution ─────────────


def test_layer_publish_resolves_correct_address_per_tier():
    """L_N picks the tier-correct address prefix from tags."""
    from world_system.world_memory.layer_publish import (
        _resolve_address_from_tags,
    )

    tags = ["district:eastside", "province:foo", "region:bar",
            "nation:baz", "world:earth", "domain:combat"]
    assert _resolve_address_from_tags(3, tags) == "district:eastside"
    assert _resolve_address_from_tags(4, tags) == "province:foo"
    assert _resolve_address_from_tags(5, tags) == "region:bar"
    assert _resolve_address_from_tags(6, tags) == "nation:baz"
    assert _resolve_address_from_tags(7, tags) == "world:earth"


def test_layer_publish_returns_none_for_invalid_layer():
    """Layer outside 3-7 → None (no publish)."""
    from world_system.world_memory.layer_publish import (
        _resolve_address_from_tags,
    )

    assert _resolve_address_from_tags(2, ["region:foo"]) is None
    assert _resolve_address_from_tags(8, ["region:foo"]) is None


def test_layer_publish_returns_none_when_address_tag_absent():
    """No matching address tag → None."""
    from world_system.world_memory.layer_publish import (
        _resolve_address_from_tags,
    )

    assert _resolve_address_from_tags(5, ["domain:combat"]) is None


# ── Phase 2: wms_context_builder cascade-down ────────────────────────


def test_wms_context_builder_cascade_picks_same_layer(tmp_path):
    """When firing at L5 region:X and an L5 summary exists, it's
    returned in preference to walking L2 interpretations."""
    from world_system.world_memory.layer_store import LayerStore
    from world_system.wns.wms_context_builder import build_wms_brief

    store = LayerStore(db_path=str(tmp_path / "ls.db"))
    store.insert_event(
        layer=5,
        narrative="The region is at peace; trade flows.",
        game_time=10.0,
        category="region_summary",
        severity="minor",
        significance="minor",
        tags=["region:silverdocks"],
    )

    brief = build_wms_brief(
        firing_address="region:silverdocks",
        event_store=None,
        firing_layer=5,
        layer_store=store,
    )
    assert "trade flows" in brief


def test_wms_context_builder_cascade_falls_through_to_lower_layer(tmp_path):
    """L5 missing but L4 present at same address → L4 used."""
    from world_system.world_memory.layer_store import LayerStore
    from world_system.wns.wms_context_builder import build_wms_brief

    store = LayerStore(db_path=str(tmp_path / "ls.db"))
    store.insert_event(
        layer=4,
        narrative="Province bustles with builders and traders.",
        game_time=5.0,
        category="province_summary",
        severity="minor",
        significance="minor",
        tags=["province:silverdocks_province"],
    )

    brief = build_wms_brief(
        firing_address="province:silverdocks_province",
        event_store=None,
        firing_layer=5,  # request L5 firing but no L5 row exists
        layer_store=store,
    )
    assert "Province bustles" in brief


def test_wms_context_builder_empty_when_no_layer_store_and_no_event_store():
    """Both stores absent → "" (deterministic fail-quiet)."""
    from world_system.wns.wms_context_builder import build_wms_brief

    assert build_wms_brief(
        firing_address="region:foo",
        event_store=None,
        firing_layer=5,
        layer_store=None,
    ) == ""


# ── Phase 4: Layer3Manager.on_dialogue_captured ──────────────────────


def test_layer3_on_dialogue_captured_routes_through_on_layer2_created():
    """``on_dialogue_captured`` synthesizes an L2-shaped dict and feeds
    it through ``on_layer2_created`` — counter advances + district set
    updated in lockstep."""
    from world_system.world_memory.layer3_manager import Layer3Manager

    Layer3Manager.reset()
    mgr = Layer3Manager.get_instance()
    # Minimal init bypassing consolidator load: mock-state mode.
    mgr._initialized = True
    mgr._trigger_interval = 5
    mgr._l2_events_since_last_run = 0
    mgr._districts_with_new_l2 = set()

    mgr.on_dialogue_captured({
        "npc_id": "n1",
        "address": "locality:tarmouth_copperdocks",
        "tags": ["locality:tarmouth_copperdocks",
                 "district:copperdocks",
                 "mention:bandits"],
        "narrative": "Bandits have been seen on the road north.",
        "game_time": 1.0,
    })

    assert mgr._l2_events_since_last_run == 1
    assert "copperdocks" in mgr._districts_with_new_l2

    Layer3Manager.reset()


def test_layer3_on_dialogue_captured_ignored_when_not_initialized():
    """``on_dialogue_captured`` is a no-op if the manager isn't initialized
    (defensive — bus subscription may fire before initialize completes)."""
    from world_system.world_memory.layer3_manager import Layer3Manager

    Layer3Manager.reset()
    mgr = Layer3Manager.get_instance()
    # Deliberately NOT calling initialize.
    mgr.on_dialogue_captured({
        "tags": ["district:foo"], "narrative": "x", "game_time": 1.0,
    })
    # No state changes; manager never tracked anything.
    assert not getattr(mgr, "_l2_events_since_last_run", None)

    Layer3Manager.reset()


def test_layer3_on_dialogue_captured_tolerates_gameevent_wrapper():
    """If a GameEvent wrapper (with ``data`` attribute) reaches the
    handler, it's unwrapped to the inner dict."""
    from world_system.world_memory.layer3_manager import Layer3Manager

    class FakeEvent:
        def __init__(self, data):
            self.data = data

    Layer3Manager.reset()
    mgr = Layer3Manager.get_instance()
    mgr._initialized = True
    mgr._trigger_interval = 5
    mgr._l2_events_since_last_run = 0
    mgr._districts_with_new_l2 = set()

    payload = {
        "tags": ["district:beachfront"], "narrative": "hi",
        "game_time": 1.0,
    }
    # Note: subscription delivers raw dict, but our handler uses
    # the dict shape directly. Wrapper unwrap is only triggered if
    # the payload comes nested under ``data`` — exercise that branch.
    mgr.on_dialogue_captured({"data": payload})
    assert mgr._l2_events_since_last_run == 1

    Layer3Manager.reset()


# ── Observability constants present ──────────────────────────────────


def test_new_observability_event_constants_present():
    """The new EVT_* names exist and have the expected string values."""
    from world_system.wes import observability_runtime as obs

    assert obs.EVT_WMS_LAYER_3_SUMMARY == "WMS_LAYER_3_SUMMARY_CREATED"
    assert obs.EVT_WMS_LAYER_4_SUMMARY == "WMS_LAYER_4_SUMMARY_CREATED"
    assert obs.EVT_WMS_LAYER_5_SUMMARY == "WMS_LAYER_5_SUMMARY_CREATED"
    assert obs.EVT_WMS_LAYER_6_SUMMARY == "WMS_LAYER_6_SUMMARY_CREATED"
    assert obs.EVT_WMS_LAYER_7_SUMMARY == "WMS_LAYER_7_SUMMARY_CREATED"
    assert obs.EVT_WMS_LAYER_FIRED_WNS == "WMS_LAYER_FIRED_WNS"
    assert obs.EVT_WMS_DIALOGUE_CAPTURED == "WMS_DIALOGUE_CAPTURED"


# ── Phase 3: WMSToWNSBridge subscribes to L_N topics ─────────────────


def test_wms_to_wns_bridge_layer_topics_include_3_through_7():
    """Bridge declares its layer-topic table covering L3-L7."""
    from world_system.wns.wms_to_wns_bridge import WMSToWNSBridge

    layers = [layer for layer, _topic in WMSToWNSBridge._LAYER_TOPICS]
    assert layers == [3, 4, 5, 6, 7]
    topics = [topic for _layer, topic in WMSToWNSBridge._LAYER_TOPICS]
    assert all(t.startswith("WMS_LAYER_") and t.endswith("_SUMMARY_CREATED")
               for t in topics)

"""Tests for WMSToWNSBridge — WMS interpretation event → WNS cascade fire."""

from __future__ import annotations

import os
import sys
import unittest
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

_this_dir = os.path.dirname(os.path.abspath(__file__))
_game_dir = os.path.dirname(os.path.dirname(os.path.dirname(_this_dir)))
if _game_dir not in sys.path:
    sys.path.insert(0, _game_dir)

from world_system.wns.wms_to_wns_bridge import (  # noqa: E402
    WMSToWNSBridge,
    WMS_INTERPRETATION_TOPIC,
)


# ── Fakes ─────────────────────────────────────────────────────────────

@dataclass
class FakeInterp:
    interpretation_id: str
    narrative: str = ""
    category: str = "combat"
    severity: str = "minor"
    affected_locality_ids: List[str] = field(default_factory=list)


class FakeEventStore:
    def __init__(self, interpretations: Optional[List[FakeInterp]] = None):
        self._interps = list(interpretations or [])

    def query_interpretations(self, **_kwargs):
        return list(self._interps)


@dataclass
class FakeRegion:
    region_id: str
    level_value: str
    children: List["FakeRegion"] = field(default_factory=list)

    @property
    def level(self):
        return type("L", (), {"value": self.level_value})()


class FakeRegistry:
    """Toy registry with parent-walk + descendants."""

    def __init__(self):
        # Hierarchy: world:w1 ⟵ ... ⟵ locality:L1, L2, L3 (under d1)
        self.L1 = FakeRegion("L1", "locality")
        self.L2 = FakeRegion("L2", "locality")
        self.L3 = FakeRegion("L3", "locality")
        self.d1 = FakeRegion("d1", "district", [self.L1, self.L2, self.L3])
        self.p1 = FakeRegion("p1", "province", [self.d1])
        self.r1 = FakeRegion("r1", "region", [self.p1])
        self.n1 = FakeRegion("n1", "nation", [self.r1])
        self.w1 = FakeRegion("w1", "world", [self.n1])
        self._children: Dict[str, List[FakeRegion]] = {
            "L1": [], "L2": [], "L3": [],
            "d1": [self.L1, self.L2, self.L3],
            "p1": [self.d1], "r1": [self.p1],
            "n1": [self.r1], "w1": [self.n1],
        }
        self._parents: Dict[str, str] = {
            "locality:L1": "district:d1",
            "locality:L2": "district:d1",
            "locality:L3": "district:d1",
            "district:d1": "province:p1",
            "province:p1": "region:r1",
            "region:r1": "nation:n1",
            "nation:n1": "world:w1",
        }

    def get_children(self, region_id: str):
        return self._children.get(region_id, [])

    def get_parent_address(self, address: str) -> Optional[str]:
        return self._parents.get(address)


class FakeWNS:
    """Captures every run_weaver call for assertions."""

    def __init__(self):
        self.calls: List[Dict[str, Any]] = []
        self.fail_layer: Optional[int] = None  # cause failures for a layer

    def run_weaver(self, **kwargs):
        if self.fail_layer is not None and kwargs.get("layer") == self.fail_layer:
            raise RuntimeError(f"weaver layer {self.fail_layer} failed")
        self.calls.append(dict(kwargs))
        return None


class FakeBus:
    """Minimal pub/sub bus with subscribe/unsubscribe."""

    def __init__(self):
        self._subs: Dict[str, List] = {}

    def subscribe(self, topic: str, handler) -> None:
        self._subs.setdefault(topic, []).append(handler)

    def unsubscribe(self, topic: str, handler) -> None:
        if topic in self._subs:
            try:
                self._subs[topic].remove(handler)
            except ValueError:
                pass

    def publish(self, topic: str, data) -> None:
        for h in list(self._subs.get(topic, [])):
            h(data)


# ── Bus injection helper ──────────────────────────────────────────────

class _BusPatch:
    """Patches events.event_bus.get_event_bus to return a FakeBus."""

    def __init__(self, bus: FakeBus):
        self.bus = bus

    def __enter__(self):
        import events.event_bus as eb
        self._original = eb.get_event_bus
        eb.get_event_bus = lambda: self.bus
        return self.bus

    def __exit__(self, *a):
        import events.event_bus as eb
        eb.get_event_bus = self._original


# ── Tests ─────────────────────────────────────────────────────────────

class TestLifecycle(unittest.TestCase):
    def test_connect_subscribes_and_disconnect_unsubscribes(self) -> None:
        bus = FakeBus()
        with _BusPatch(bus):
            bridge = WMSToWNSBridge(
                wns=FakeWNS(),
                event_store=FakeEventStore(),
                geographic_registry=FakeRegistry(),
            )
            bridge.connect()
            self.assertTrue(bridge.connected)
            self.assertEqual(
                len(bus._subs.get(WMS_INTERPRETATION_TOPIC, [])), 1
            )
            bridge.disconnect()
            self.assertFalse(bridge.connected)

    def test_connect_is_idempotent(self) -> None:
        bus = FakeBus()
        with _BusPatch(bus):
            bridge = WMSToWNSBridge(
                wns=FakeWNS(),
                event_store=FakeEventStore(),
                geographic_registry=FakeRegistry(),
            )
            bridge.connect()
            bridge.connect()
            bridge.connect()
            # Only one subscription registered.
            self.assertEqual(
                len(bus._subs.get(WMS_INTERPRETATION_TOPIC, [])), 1
            )

    def test_handler_no_op_after_disconnect(self) -> None:
        bus = FakeBus()
        wns = FakeWNS()
        with _BusPatch(bus):
            bridge = WMSToWNSBridge(
                wns=wns,
                event_store=FakeEventStore(),
                geographic_registry=FakeRegistry(),
            )
            bridge.connect()
            bridge.disconnect()
            # Even if a stale ref invokes _on_event, the connected
            # flag short-circuits.
            bridge._on_event({
                "interpretation_id": "i1",
                "affected_locality_ids": ["L1"],
            })
            self.assertEqual(wns.calls, [])


class TestEventIngestion(unittest.TestCase):
    def setUp(self) -> None:
        self.bus = FakeBus()
        self.wns = FakeWNS()
        self.bridge = WMSToWNSBridge(
            wns=self.wns,
            event_store=FakeEventStore(),
            geographic_registry=FakeRegistry(),
        )
        with _BusPatch(self.bus):
            self.bridge.connect()

    def _publish(self, locality_ids: List[str], interp_id: str = "i1") -> None:
        with _BusPatch(self.bus):
            self.bus.publish(WMS_INTERPRETATION_TOPIC, {
                "interpretation_id": interp_id,
                "narrative": "x",
                "category": "combat",
                "severity": "minor",
                "affected_locality_ids": list(locality_ids),
            })

    def test_three_events_at_locality_fires_nl2(self) -> None:
        for i in range(3):
            self._publish(["L1"], interp_id=f"i{i}")
        # Each interp ID is unique → all three count.
        self.assertEqual(len(self.wns.calls), 1)
        self.assertEqual(self.wns.calls[0]["layer"], 2)
        self.assertEqual(self.wns.calls[0]["address"], "locality:L1")

    def test_duplicate_interpretation_id_skipped(self) -> None:
        self._publish(["L1"], interp_id="dup")
        self._publish(["L1"], interp_id="dup")
        self._publish(["L1"], interp_id="dup")
        self.assertEqual(len(self.wns.calls), 0)
        self.assertEqual(self.bridge.stats["events_skipped_duplicate"], 2)

    def test_no_locality_skipped(self) -> None:
        self._publish([], interp_id="i1")
        self.assertEqual(len(self.wns.calls), 0)
        self.assertEqual(self.bridge.stats["events_skipped_no_locality"], 1)

    def test_multi_locality_advances_each_counter(self) -> None:
        # One interpretation affecting L1+L2 — both NL2 counters tick.
        self._publish(["L1", "L2"], interp_id="i1")
        self._publish(["L1", "L2"], interp_id="i2")
        self._publish(["L1", "L2"], interp_id="i3")
        # 3 ticks at each → 2 NL2 fires.
        addresses = sorted(c["address"] for c in self.wns.calls)
        self.assertEqual(addresses, ["locality:L1", "locality:L2"])

    def test_cascade_to_nl3(self) -> None:
        # 3 fires at each of L1, L2, L3 → 9 unique IDs → 3 NL2 fires
        # → 1 NL3 fire at district:d1.
        for j, loc in enumerate(("L1", "L2", "L3")):
            for i in range(3):
                self._publish([loc], interp_id=f"i_{j}_{i}")
        layers_fired = [c["layer"] for c in self.wns.calls]
        self.assertEqual(layers_fired.count(2), 3)
        self.assertEqual(layers_fired.count(3), 1)
        nl3 = next(c for c in self.wns.calls if c["layer"] == 3)
        self.assertEqual(nl3["address"], "district:d1")
        # parent_address resolved up one tier
        self.assertEqual(nl3["parent_address"], "province:p1")
        self.assertEqual(nl3["grandparent_address"], "region:r1")


class TestWMSBriefInjection(unittest.TestCase):
    def test_wms_brief_passed_to_weaver(self) -> None:
        bus = FakeBus()
        wns = FakeWNS()
        store = FakeEventStore([
            FakeInterp("i_a", "Wolves at L1.", affected_locality_ids=["L1"]),
            FakeInterp("i_b", "Bandits at L1.", affected_locality_ids=["L1"]),
        ])
        bridge = WMSToWNSBridge(
            wns=wns,
            event_store=store,
            geographic_registry=FakeRegistry(),
        )
        with _BusPatch(bus):
            bridge.connect()
            for i in range(3):
                bus.publish(WMS_INTERPRETATION_TOPIC, {
                    "interpretation_id": f"trigger_{i}",
                    "affected_locality_ids": ["L1"],
                })
        self.assertEqual(len(wns.calls), 1)
        brief = wns.calls[0]["wms_brief"] or ""
        self.assertIn("Wolves at L1.", brief)
        self.assertIn("Bandits at L1.", brief)


class TestRobustness(unittest.TestCase):
    def test_weaver_raise_does_not_break_cascade(self) -> None:
        bus = FakeBus()
        wns = FakeWNS()
        wns.fail_layer = 2  # NL2 always raises
        bridge = WMSToWNSBridge(
            wns=wns,
            event_store=FakeEventStore(),
            geographic_registry=FakeRegistry(),
        )
        with _BusPatch(bus):
            bridge.connect()
            # Drive 3 NL2 fires across L1, L2, L3 — each fires NL2
            # weaver (which raises), but cascade still advances and
            # NL3 should run successfully.
            for j, loc in enumerate(("L1", "L2", "L3")):
                for i in range(3):
                    bus.publish(WMS_INTERPRETATION_TOPIC, {
                        "interpretation_id": f"i_{j}_{i}",
                        "affected_locality_ids": [loc],
                    })
        # NL2 fires recorded as failures; NL3 fires recorded as success.
        nl3_calls = [c for c in wns.calls if c["layer"] == 3]
        self.assertEqual(len(nl3_calls), 1)
        self.assertEqual(bridge.stats["weaver_run_failures"], 3)

    def test_bus_unavailable_disables_bridge(self) -> None:
        # No _BusPatch — connect() will fail to import.
        bridge = WMSToWNSBridge(
            wns=FakeWNS(),
            event_store=FakeEventStore(),
            geographic_registry=FakeRegistry(),
        )
        # Make sure import resolves to a non-functional bus
        import events.event_bus as eb
        original = eb.get_event_bus
        eb.get_event_bus = lambda: (_ for _ in ()).throw(
            RuntimeError("bus unavailable")
        )
        try:
            bridge.connect()
            self.assertFalse(bridge.connected)
        finally:
            eb.get_event_bus = original

    def test_malformed_payload_does_not_crash(self) -> None:
        bus = FakeBus()
        bridge = WMSToWNSBridge(
            wns=FakeWNS(),
            event_store=FakeEventStore(),
            geographic_registry=FakeRegistry(),
        )
        with _BusPatch(bus):
            bridge.connect()
            # None payload, string payload, payload missing keys
            bus.publish(WMS_INTERPRETATION_TOPIC, None)
            bus.publish(WMS_INTERPRETATION_TOPIC, "garbage")
            bus.publish(WMS_INTERPRETATION_TOPIC, {})
            # Bridge should treat each as no-locality and count them
            # (received) without raising.
        self.assertGreaterEqual(bridge.stats["events_received"], 3)


class TestStats(unittest.TestCase):
    def test_stats_shape(self) -> None:
        bridge = WMSToWNSBridge(
            wns=FakeWNS(),
            event_store=FakeEventStore(),
            geographic_registry=FakeRegistry(),
        )
        s = bridge.stats
        for key in (
            "connected", "events_received", "events_processed",
            "events_skipped_duplicate", "events_skipped_no_locality",
            "weaver_run_failures", "address_resolution_failures",
            "cascade", "seen_ring_capacity", "seen_ring_size",
        ):
            self.assertIn(key, s)
        self.assertFalse(s["connected"])
        self.assertEqual(s["events_received"], 0)


if __name__ == "__main__":
    unittest.main()

"""End-to-end integration test: WMS interpretation → bus → bridge → cascade
→ WNS weaver run with the WMS context slice rendered into the prompt.

Uses real GeographicRegistry, real WorldNarrativeSystem (with mock backend
via fixture registry), real CascadeTriggerManager, real WMSToWNSBridge.
The WMS facade is faked just enough to expose ``event_store`` with a
``query_interpretations`` method — we don't spin up the full WMS pipeline
because the contract we're testing is publish→bridge→fire, not
event-recording.
"""

from __future__ import annotations

import os
import sys
import tempfile
import time
import unittest
from dataclasses import dataclass, field
from typing import List

_this_dir = os.path.dirname(os.path.abspath(__file__))
_game_dir = os.path.dirname(os.path.dirname(os.path.dirname(_this_dir)))
if _game_dir not in sys.path:
    sys.path.insert(0, _game_dir)

from events.event_bus import get_event_bus  # noqa: E402
from world_system.living_world.backends.backend_manager import BackendManager  # noqa: E402
from world_system.world_memory.geographic_registry import (  # noqa: E402
    GeographicRegistry,
    Region,
    RegionLevel,
)
from world_system.wns.world_narrative_system import WorldNarrativeSystem  # noqa: E402


@dataclass
class FakeInterp:
    interpretation_id: str
    narrative: str
    category: str = "combat"
    severity: str = "minor"
    affected_locality_ids: List[str] = field(default_factory=list)


class FakeEventStore:
    def __init__(self, interpretations=None):
        self._interps = list(interpretations or [])

    def query_interpretations(self, **_kwargs):
        return list(self._interps)


class FakeWMSFacade:
    """Just enough surface for WorldNarrativeSystem._build_wms_bridge."""

    def __init__(self, event_store):
        self.event_store = event_store


def _build_toy_registry() -> GeographicRegistry:
    """A 6-tier hierarchy with one path: w → n → r → p → d → L1.

    Provides enough structure for the cascade to walk all the way up.
    """
    GeographicRegistry.reset()
    reg = GeographicRegistry.get_instance()

    def _mk(level: RegionLevel, rid: str, parent_id=None) -> Region:
        return Region(
            region_id=rid,
            name=rid,
            level=level,
            bounds_x1=0,
            bounds_y1=0,
            bounds_x2=10,
            bounds_y2=10,
            parent_id=parent_id,
        )

    w = _mk(RegionLevel.WORLD, "w1")
    n = _mk(RegionLevel.NATION, "n1", parent_id="w1")
    r = _mk(RegionLevel.REGION, "r1", parent_id="n1")
    p = _mk(RegionLevel.PROVINCE, "p1", parent_id="r1")
    d = _mk(RegionLevel.DISTRICT, "d1", parent_id="p1")
    L1 = _mk(RegionLevel.LOCALITY, "L1", parent_id="d1")
    L2 = _mk(RegionLevel.LOCALITY, "L2", parent_id="d1")
    L3 = _mk(RegionLevel.LOCALITY, "L3", parent_id="d1")

    reg.world = w
    for region in (w, n, r, p, d, L1, L2, L3):
        reg.register_region(region)
    return reg


class TestEndToEnd(unittest.TestCase):
    def setUp(self) -> None:
        # Reset all singletons that might carry test pollution.
        WorldNarrativeSystem.reset()
        # Make BackendManager use fixtures (no real LLM calls).
        BackendManager.reset()
        BackendManager.get_instance().initialize()

        self._tmp = tempfile.TemporaryDirectory()
        self.tmpdir = self._tmp.name

        self.registry = _build_toy_registry()
        # Pre-populate one interpretation per locality so the WMS
        # context slice rendering has content to draw from.
        self.event_store = FakeEventStore([
            FakeInterp(
                f"i_{loc}",
                f"Wolves seen at {loc}.",
                affected_locality_ids=[loc],
            )
            for loc in ("L1", "L2", "L3")
        ])

        self.wms = FakeWMSFacade(event_store=self.event_store)

        self.wns = WorldNarrativeSystem.get_instance()
        self.wns.initialize(
            save_dir=self.tmpdir,
            geographic_registry=self.registry,
            wms_facade=self.wms,
            connect_wms_bridge=True,
        )

    def tearDown(self) -> None:
        WorldNarrativeSystem.reset()
        GeographicRegistry.reset()
        BackendManager.reset()
        self._tmp.cleanup()

    def _publish_interpretation(self, interp_id: str, locality_id: str) -> None:
        get_event_bus().publish("WMS_INTERPRETATION_CREATED", {
            "interpretation_id": interp_id,
            "narrative": f"event {interp_id}",
            "category": "combat",
            "severity": "minor",
            "affected_locality_ids": [locality_id],
            "affects_tags": [],
            "created_at": time.time(),
        })

    def test_bridge_attached_after_init(self) -> None:
        self.assertIsNotNone(self.wns.wms_bridge)
        self.assertTrue(self.wns.wms_bridge.connected)

    def test_three_events_at_locality_writes_nl2_row(self) -> None:
        """Bridge end-to-end: publish 3 WMS interpretations at L1 →
        cascade NL2 fires at locality:L1 → weaver runs → narrative
        row lands in the store."""
        for i in range(3):
            self._publish_interpretation(f"trig_{i}", "L1")

        # NL2 should have fired exactly once at locality:L1.
        bridge_stats = self.wns.wms_bridge.stats
        self.assertEqual(bridge_stats["events_processed"], 3)
        self.assertEqual(
            bridge_stats["cascade"]["fires_total_by_layer"][2], 1
        )
        # And the store should now contain at least one NL2 row at L1.
        rows = self.wns.store.query_by_address(2, "locality:L1", limit=10)
        self.assertGreaterEqual(
            len(rows), 1,
            "expected at least one NL2 row written by the cascade fire",
        )
        # The row's narrative came from the fixture-mock backend; we
        # only care that *something* was written.
        self.assertTrue(rows[0].narrative)

    def test_cascade_propagates_locality_to_district(self) -> None:
        """3 NL2 fires across L1, L2, L3 → cascade NL3 fire at d1."""
        # 9 unique events (3 each at L1/L2/L3).
        idx = 0
        for loc in ("L1", "L2", "L3"):
            for i in range(3):
                self._publish_interpretation(f"e_{idx}", loc)
                idx += 1

        cascade_fires = self.wns.wms_bridge.stats["cascade"]["fires_total_by_layer"]
        self.assertEqual(cascade_fires[2], 3)
        self.assertEqual(cascade_fires[3], 1)

        # Confirm a row was written at NL3 / district:d1.
        rows = self.wns.store.query_by_address(3, "district:d1", limit=10)
        self.assertGreaterEqual(len(rows), 1)

    def test_duplicate_interpretation_ignored(self) -> None:
        for _ in range(5):
            self._publish_interpretation("dup_id", "L1")
        bridge_stats = self.wns.wms_bridge.stats
        self.assertEqual(bridge_stats["events_processed"], 1)
        self.assertEqual(bridge_stats["events_skipped_duplicate"], 4)

    def test_disconnect_idempotent_and_stops_pumping(self) -> None:
        self.wns.wms_bridge.disconnect()
        self.assertFalse(self.wns.wms_bridge.connected)
        # Publish after disconnect — bridge should ignore the event.
        self._publish_interpretation("late", "L1")
        self.assertEqual(self.wns.wms_bridge.stats["events_received"], 0)


if __name__ == "__main__":
    unittest.main()

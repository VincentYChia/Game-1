"""Tests for NLWeaver — end-to-end run via fixture registry + MockBackend.

Exercises:
- NL2 weaver runs against the ``wns_layer2`` fixture (call_wes=false path).
- NL4 weaver runs against the ``wns_layer4`` fixture (call_wes=true path
  — must publish WNS_CALL_WES_REQUESTED on the GameEventBus).
- Row persistence — narrative + threads end up in the store.
"""

import os
import sys
import unittest

_this_dir = os.path.dirname(os.path.abspath(__file__))
_game_dir = os.path.dirname(os.path.dirname(os.path.dirname(_this_dir)))
if _game_dir not in sys.path:
    sys.path.insert(0, _game_dir)

# Trigger fixture registration.
from world_system.living_world.infra.llm_fixtures import (  # noqa: E402, F401
    get_fixture_registry,
)
from world_system.living_world.backends.backend_manager import (  # noqa: E402
    BackendManager,
    MockBackend,
)
from events.event_bus import GameEventBus  # noqa: E402
from world_system.wns.narrative_distance_filter import (  # noqa: E402
    NarrativeDistanceFilter,
)
from world_system.wns.narrative_store import NarrativeStore  # noqa: E402
from world_system.wns.narrative_tag_library import NarrativeTagLibrary  # noqa: E402
from world_system.wns.nl_weaver import (  # noqa: E402
    NLWeaver,
    WNS_CALL_WES_EVENT,
)


def _build_backend_manager_mock_only() -> BackendManager:
    """A BackendManager pinned to mock-first so fixture registry drives responses."""
    BackendManager._instance = None  # type: ignore[attr-defined]
    mgr = BackendManager.get_instance()
    # Load defaults; we override task routing to force MOCK for wns_*.
    mgr.initialize()
    mgr._task_routing["wns_layer2"] = "mock"  # type: ignore[attr-defined]
    mgr._task_routing["wns_layer3"] = "mock"  # type: ignore[attr-defined]
    mgr._task_routing["wns_layer4"] = "mock"  # type: ignore[attr-defined]
    mgr._task_routing["wns_layer5"] = "mock"  # type: ignore[attr-defined]
    mgr._task_routing["wns_layer6"] = "mock"  # type: ignore[attr-defined]
    mgr._task_routing["wns_layer7"] = "mock"  # type: ignore[attr-defined]
    return mgr


class TestNLWeaver(unittest.TestCase):
    def setUp(self):
        # Fresh singletons per test.
        NarrativeTagLibrary.reset()
        GameEventBus.reset()
        self.store = NarrativeStore(db_path=":memory:")
        self.lib = NarrativeTagLibrary.get_instance()
        self.backend = _build_backend_manager_mock_only()
        self.filt = NarrativeDistanceFilter()

        # Event capture.
        self.captured_events = []

        def _capture(evt):
            self.captured_events.append(evt)

        bus = GameEventBus.get_instance()
        bus.subscribe(WNS_CALL_WES_EVENT, _capture)

    def tearDown(self):
        self.store.close()
        MockBackend.set_current_task(None)

    def _new_weaver(self, layer: int) -> NLWeaver:
        return NLWeaver(
            layer=layer,
            store=self.store,
            tag_library=self.lib,
            backend_manager=self.backend,
            distance_filter=self.filt,
        )

    def test_nl2_weaver_writes_row_and_no_wes_event(self):
        weaver = self._new_weaver(layer=2)
        result = weaver.run_weaving(
            address="locality:tarmouth_copperdocks",
            lower_narratives=[],
            game_time=100.0,
        )
        self.assertTrue(result.success, f"error: {result.error}")
        self.assertIsNotNone(result.row)
        self.assertEqual(result.row.layer, 2)
        self.assertEqual(result.row.address, "locality:tarmouth_copperdocks")
        self.assertIn("copperdocks", result.row.narrative.lower())
        # Threads parsed from fixture.
        self.assertGreaterEqual(len(result.threads), 1)
        # call_wes=false in fixture — no event fired.
        self.assertFalse(result.call_wes)
        self.assertEqual(len(self.captured_events), 0)
        # Row persisted and queryable by address.
        got = self.store.query_by_address(
            layer=2, address="locality:tarmouth_copperdocks",
        )
        self.assertEqual(len(got), 1)

    def test_nl4_weaver_publishes_wes_event_on_call_wes_true(self):
        weaver = self._new_weaver(layer=4)
        result = weaver.run_weaving(
            address="region:ashfall_moors",
            lower_narratives=[],
            game_time=200.0,
        )
        self.assertTrue(result.success, f"error: {result.error}")
        self.assertTrue(result.call_wes)
        self.assertNotEqual(result.directive_hint, "")
        # Event fired with the firing address + directive text.
        self.assertEqual(len(self.captured_events), 1)
        evt = self.captured_events[0]
        self.assertEqual(evt.event_type, WNS_CALL_WES_EVENT)
        self.assertEqual(evt.data["layer"], 4)
        self.assertEqual(evt.data["address"], "region:ashfall_moors")
        self.assertEqual(evt.data["directive_text"], result.directive_hint)
        self.assertEqual(evt.data["source_row_id"], result.row.id)

    def test_layer_1_rejected(self):
        # NL1 is deterministic; a weaver is not allowed to wrap it.
        with self.assertRaises(ValueError):
            NLWeaver(
                layer=1,
                store=self.store,
                tag_library=self.lib,
                backend_manager=self.backend,
            )

    def test_threads_carry_firing_layer_and_address(self):
        weaver = self._new_weaver(layer=2)
        result = weaver.run_weaving(
            address="locality:tarmouth_copperdocks",
            lower_narratives=[],
            game_time=100.0,
        )
        self.assertTrue(result.success)
        for t in result.threads:
            self.assertEqual(t.layer, 2)
            self.assertEqual(t.address, "locality:tarmouth_copperdocks")


if __name__ == "__main__":
    unittest.main()

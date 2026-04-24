"""Facade integration tests for WorldNarrativeSystem."""

import os
import sys
import tempfile
import unittest

_this_dir = os.path.dirname(os.path.abspath(__file__))
_game_dir = os.path.dirname(os.path.dirname(os.path.dirname(_this_dir)))
if _game_dir not in sys.path:
    sys.path.insert(0, _game_dir)

# Side-effect imports to populate backend + fixtures.
from world_system.living_world.infra.llm_fixtures import (  # noqa: E402, F401
    get_fixture_registry,
)
from world_system.living_world.backends.backend_manager import (  # noqa: E402
    BackendManager,
)
from events.event_bus import GameEventBus  # noqa: E402
from world_system.wns.narrative_tag_library import NarrativeTagLibrary  # noqa: E402
from world_system.wns.nl_weaver import WNS_CALL_WES_EVENT  # noqa: E402
from world_system.wns.world_narrative_system import WorldNarrativeSystem  # noqa: E402


class TestWorldNarrativeSystem(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="wns_test_")

        # Reset singletons between tests.
        GameEventBus.reset()
        NarrativeTagLibrary.reset()
        WorldNarrativeSystem.reset()
        BackendManager._instance = None  # type: ignore[attr-defined]

        # Force all WNS tasks to mock so the fixture registry answers.
        self.backend = BackendManager.get_instance()
        self.backend.initialize()
        for layer in (2, 3, 4, 5, 6, 7):
            self.backend._task_routing[f"wns_layer{layer}"] = "mock"  # type: ignore[attr-defined]

    def tearDown(self):
        WorldNarrativeSystem.reset()
        # Best-effort cleanup of temp dir.
        for fn in os.listdir(self.tmpdir):
            try:
                os.remove(os.path.join(self.tmpdir, fn))
            except OSError:
                pass
        try:
            os.rmdir(self.tmpdir)
        except OSError:
            pass

    def test_initialize_creates_db_file(self):
        wns = WorldNarrativeSystem.get_instance()
        wns.initialize(save_dir=self.tmpdir, backend_manager=self.backend)
        self.assertTrue(wns._initialized)
        self.assertTrue(
            os.path.exists(os.path.join(self.tmpdir, "world_narrative.db")),
            "WNS did not create its own SQLite file",
        )

    def test_ingest_dialogue_writes_nl1_rows(self):
        wns = WorldNarrativeSystem.get_instance()
        wns.initialize(save_dir=self.tmpdir, backend_manager=self.backend)
        speech = {
            "greeting": "Bandits and copper rush — hard times.",
        }
        rows = wns.ingest_dialogue(
            npc_id="npc_1",
            speech_bank=speech,
            address="locality:tarmouth_copperdocks",
            game_time=100.0,
        )
        self.assertGreater(len(rows), 0)
        self.assertEqual(wns.store.count_by_layer(1), len(rows))

    def test_run_weaver_writes_nl2_row_and_queryable(self):
        wns = WorldNarrativeSystem.get_instance()
        wns.initialize(save_dir=self.tmpdir, backend_manager=self.backend)
        result = wns.run_weaver(
            layer=2,
            address="locality:tarmouth_copperdocks",
            lower_narratives=[],
            game_time=200.0,
        )
        self.assertIsNotNone(result)
        self.assertTrue(result.success)
        summary = wns.get_layer_summary(
            layer=2, address="locality:tarmouth_copperdocks",
        )
        self.assertIsNotNone(summary)
        self.assertIn("copperdocks", summary.lower())

    def test_query_threads_returns_expected_threads(self):
        wns = WorldNarrativeSystem.get_instance()
        wns.initialize(save_dir=self.tmpdir, backend_manager=self.backend)
        wns.run_weaver(
            layer=2,
            address="locality:tarmouth_copperdocks",
            lower_narratives=[],
            game_time=200.0,
        )
        threads = wns.query_threads(address="locality:tarmouth_copperdocks")
        self.assertGreater(len(threads), 0)
        # Each thread carries its firing layer + address.
        for t in threads:
            self.assertEqual(t.address, "locality:tarmouth_copperdocks")
            self.assertEqual(t.layer, 2)

    def test_maybe_weave_respects_trigger(self):
        wns = WorldNarrativeSystem.get_instance()
        wns.initialize(save_dir=self.tmpdir, backend_manager=self.backend)
        # With default N=5 for NL2, maybe_weave must return None for first
        # 4 calls and fire on the 5th.
        addr = "locality:test_loc"
        fires = 0
        for _ in range(5):
            result = wns.maybe_weave(layer=2, address=addr)
            if result is not None:
                fires += 1
        self.assertEqual(fires, 1)

    def test_ingest_dialogue_advances_nl2_bucket(self):
        wns = WorldNarrativeSystem.get_instance()
        wns.initialize(save_dir=self.tmpdir, backend_manager=self.backend)
        # One dialogue line with many entity mentions advances NL2 bucket.
        speech = {
            "greeting": "Bandits took the king's copper from the iron mine.",
        }
        rows = wns.ingest_dialogue(
            npc_id="npc_1",
            speech_bank=speech,
            address="locality:x",
            game_time=10.0,
        )
        self.assertGreater(len(rows), 0)
        peek = wns.trigger_manager.peek(layer=2, address="locality:x")
        self.assertEqual(peek["count"], len(rows))

    def test_stats_reports_structure(self):
        wns = WorldNarrativeSystem.get_instance()
        wns.initialize(save_dir=self.tmpdir, backend_manager=self.backend)
        s = wns.stats
        self.assertTrue(s["initialized"])
        self.assertEqual(sorted(s["weavers"]), [2, 3, 4, 5, 6, 7])
        self.assertIn("store", s)
        self.assertIn("tag_library", s)
        self.assertIn("trigger_manager", s)


if __name__ == "__main__":
    unittest.main()

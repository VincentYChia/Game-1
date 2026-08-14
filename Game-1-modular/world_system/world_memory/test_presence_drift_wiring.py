"""Presence-drift wiring (2026-08-13 Phase 3b).

PresenceDriftDetector reads meta.last_activity_day.locality.<id>, but nothing
wrote it at runtime (scan was always empty), and its presence_drift signal fell
to category "other" which BehaviorInterpreter suppresses. These lock the fix:
the recorder now stamps the stat, and the category is non-suppressed.
"""
from __future__ import annotations

import os
import sys
import unittest
from types import SimpleNamespace

_this = os.path.dirname(os.path.abspath(__file__))
_modular = os.path.dirname(os.path.dirname(_this))
if _modular not in sys.path:
    sys.path.insert(0, _modular)


class _FakeStatStore:
    def __init__(self):
        self.d = {}

    def set_max(self, name, value):
        self.d[name] = max(self.d.get(name, float("-inf")), value)

    def get(self, name):
        return self.d.get(name, 0.0)


def _event(locality_id="tarmouth"):
    return SimpleNamespace(
        locality_id=locality_id, district_id=None,
        actor_id="player", target_id=None, event_id="e1")


class TestPresenceDriftWiring(unittest.TestCase):
    def _recorder(self, store, game_time=42.0):
        from world_system.world_memory.event_recorder import EventRecorder
        EventRecorder.reset()
        rec = EventRecorder.get_instance()
        rec.set_stat_store(store)
        rec.set_game_time(game_time)
        rec.entity_registry = None  # write must run without it
        return rec

    def tearDown(self):
        from world_system.world_memory.event_recorder import EventRecorder
        EventRecorder.reset()

    def test_recorder_stamps_last_activity_day(self):
        store = _FakeStatStore()
        rec = self._recorder(store, game_time=42.0)
        rec._update_activity_logs(_event("tarmouth"))
        self.assertEqual(
            store.get("meta.last_activity_day.locality.tarmouth"), 42.0)

    def test_set_max_keeps_latest_day(self):
        store = _FakeStatStore()
        self._recorder(store, game_time=10.0)._update_activity_logs(_event("x"))
        # A LATER event advances the stamp; an earlier one does not.
        self._recorder(store, game_time=30.0)._update_activity_logs(_event("x"))
        self._recorder(store, game_time=20.0)._update_activity_logs(_event("x"))
        self.assertEqual(store.get("meta.last_activity_day.locality.x"), 30.0)

    def test_no_locality_no_write(self):
        store = _FakeStatStore()
        self._recorder(store)._update_activity_logs(_event(locality_id=None))
        self.assertEqual(store.d, {})

    def test_presence_drift_category_not_suppressed(self):
        from world_system.world_memory.trigger_manager import EVENT_CATEGORY_MAP
        # Default BehaviorInterpreter suppresses only "other".
        self.assertEqual(EVENT_CATEGORY_MAP.get("presence_drift"), "exploration")
        self.assertNotEqual(
            EVENT_CATEGORY_MAP.get("presence_drift", "other"), "other")


if __name__ == "__main__":
    unittest.main()

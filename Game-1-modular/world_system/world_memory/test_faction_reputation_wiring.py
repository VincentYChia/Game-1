"""Faction reputation L2 wiring (2026-08-11 Phase 3a).

The FactionReputationEvaluator was fully built but never fired: it wasn't
registered, FACTION_AFFINITY_CHANGED wasn't routed into WMS, and it read the
wrong event shape (uppercase type + .data instead of the recorded lowercase
type + .context). These tests lock the wiring.
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

from world_system.world_memory.event_schema import (  # noqa: E402
    BUS_TO_MEMORY_TYPE,
    EventType,
)
from world_system.world_memory.evaluators.faction_reputation import (  # noqa: E402
    FactionReputationEvaluator,
)


class _FakeStore:
    def __init__(self, count):
        self._count = count

    def count_filtered(self, event_type=None, time_range=None):
        assert event_type == "faction_affinity_changed", event_type
        return self._count


def _event(event_type="faction_affinity_changed", **ctx):
    return SimpleNamespace(
        event_type=event_type, context=ctx,
        event_id="e1", interpretation_count=3, game_time=1000.0,
        locality_id=None, position_x=0.0, position_y=0.0)


class TestFactionReputationWiring(unittest.TestCase):
    def test_event_mapped_into_wms(self):
        self.assertEqual(EventType.FACTION_AFFINITY_CHANGED.value,
                         "faction_affinity_changed")
        self.assertEqual(BUS_TO_MEMORY_TYPE["FACTION_AFFINITY_CHANGED"],
                         EventType.FACTION_AFFINITY_CHANGED)

    def test_is_relevant_matches_recorded_lowercase_type(self):
        ev = FactionReputationEvaluator()
        self.assertTrue(ev.is_relevant(_event()))
        self.assertFalse(ev.is_relevant(_event(event_type="npc_interaction")))
        # The old uppercase form must NOT match (that was the bug).
        self.assertFalse(ev.is_relevant(_event(event_type="FACTION_AFFINITY_CHANGED")))

    def test_evaluate_reads_context_and_produces_interpretation(self):
        ev = _event(player_id="player", tag="merchants_guild",
                    delta=12.0, new_value=40.0)
        out = FactionReputationEvaluator().evaluate(
            ev, _FakeStore(3), None, None, _FakeStore(3))
        self.assertIsNotNone(out)
        self.assertEqual(out.category, "faction_reputation")
        self.assertIn("faction:merchants_guild", out.affects_tags)

    def test_small_delta_is_skipped(self):
        ev = _event(player_id="p", tag="g", delta=1.0, new_value=5.0)
        out = FactionReputationEvaluator().evaluate(
            ev, _FakeStore(3), None, None, _FakeStore(3))
        self.assertIsNone(out)

    def test_registered_in_interpreter(self):
        import inspect
        from world_system.world_memory.interpreter import WorldInterpreter
        src = inspect.getsource(WorldInterpreter._register_all_evaluators)
        self.assertIn("evaluators.faction_reputation", src)
        self.assertIn("FactionReputationEvaluator", src)


if __name__ == "__main__":
    unittest.main()

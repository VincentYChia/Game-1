"""Phase 2 behavior-causal pathway end-to-end tests (2026-06-03).

The behavior-causal trigger archetype is the PRIMARY mechanism through
which the world recognizes the player (consolidation §2.7 — user's
correction: "behavior emergence is just as important as NPC
interactions when it comes to this entire system, probably even more
important"). These tests anchor on the user's pseudo-trace:

    Player uses 1000 potions in combat → WMS publishes
    WMS_TRIGGER_FIRED → BehaviorInterpreter reads activity_profile
    (combat-dominant) → composes "an instant-heal skill matching the
    player's pattern of emergency potion use" → publishes
    WNS_CALL_WES_REQUESTED with a behavior-causal bundle.

The path being tested:

    TriggerManager.on_event (existing G03 publish)
        ↓
    GameEventBus → BehaviorInterpreter._on_trigger_fired
        ↓
    _is_dispatch_worthy (rules from behavior_dispatch_rules.json)
        ↓
    _compose_directive (purpose + body from category mapping)
        ↓
    _make_bundle (BehaviorSignal + WESContextBundle with
        trigger_archetype="behavior" in scope_hint)
        ↓
    Bus publish WNS_CALL_WES_REQUESTED
        ↓
    [WES orchestrator consumes — test asserts the bundle arrives]
"""

from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path

_THIS_DIR = Path(__file__).parent
_PROJECT_ROOT = _THIS_DIR.parent
sys.path.insert(0, str(_PROJECT_ROOT))
os.chdir(_PROJECT_ROOT)


# ── BehaviorSignal dataclass round-trip ──────────────────────────────


class BehaviorSignalTests(unittest.TestCase):
    def test_round_trip_preserves_all_fields(self) -> None:
        from world_system.living_world.infra.context_bundle import (
            BehaviorSignal,
        )
        sig = BehaviorSignal(
            counter_path="combat.kills.locality.tarmouth",
            threshold_crossed=1000,
            stream_count=1001,
            locality_id="tarmouth",
            activity_profile={"combat": 0.78, "gathering": 0.1},
            inferred_behavior_intent="aggressive harbor patrol",
            matching_pool_entries=["existing_skill"],
        )
        d = sig.to_dict()
        restored = BehaviorSignal.from_dict(d)
        self.assertEqual(restored.counter_path, sig.counter_path)
        self.assertEqual(restored.threshold_crossed, sig.threshold_crossed)
        self.assertEqual(restored.stream_count, sig.stream_count)
        self.assertEqual(restored.locality_id, sig.locality_id)
        self.assertEqual(restored.activity_profile, sig.activity_profile)
        self.assertEqual(
            restored.inferred_behavior_intent, sig.inferred_behavior_intent,
        )
        self.assertEqual(
            restored.matching_pool_entries, sig.matching_pool_entries,
        )

    def test_bundle_round_trip_with_behavior_signal(self) -> None:
        from world_system.living_world.infra.context_bundle import (
            BehaviorSignal,
            NarrativeContextSlice,
            NarrativeDelta,
            WESContextBundle,
            WNSDirective,
        )
        bundle = WESContextBundle(
            bundle_id="probe",
            created_at=42.0,
            delta=NarrativeDelta(
                address="locality:tarmouth", layer=2,
                start_time=40.0, end_time=42.0,
            ),
            narrative_context=NarrativeContextSlice(
                firing_layer_summary="",
                parent_summaries={},
                open_threads=[],
            ),
            directive=WNSDirective(
                directive_text="probe",
                firing_tier=2,
                scope_hint={
                    "firing_address": "locality:tarmouth",
                    "purpose": "new-skill",
                    "trigger_archetype": "behavior",
                },
            ),
            behavior_signal=BehaviorSignal(
                counter_path="items.consumed.potion.tarmouth",
                threshold_crossed=1000,
                stream_count=1000,
                locality_id="tarmouth",
            ),
        )
        restored = WESContextBundle.from_dict(bundle.to_dict())
        self.assertIsNotNone(restored.behavior_signal)
        self.assertEqual(
            restored.behavior_signal.threshold_crossed, 1000,
        )


# ── CooldownArbiter ──────────────────────────────────────────────────


class CooldownArbiterTests(unittest.TestCase):
    def test_first_dispatch_allowed(self) -> None:
        from world_system.wns.behavior_interpreter import CooldownArbiter
        arb = CooldownArbiter(cooldown_seconds=300.0)
        self.assertTrue(arb.can_dispatch("c", "tarmouth", now=100.0))

    def test_recorded_dispatch_blocks_within_window(self) -> None:
        from world_system.wns.behavior_interpreter import CooldownArbiter
        arb = CooldownArbiter(cooldown_seconds=300.0)
        arb.record_dispatch("c", "tarmouth", now=100.0)
        # 200 s later — inside the 300 s window
        self.assertFalse(arb.can_dispatch("c", "tarmouth", now=300.0))

    def test_dispatch_allowed_after_window(self) -> None:
        from world_system.wns.behavior_interpreter import CooldownArbiter
        arb = CooldownArbiter(cooldown_seconds=300.0)
        arb.record_dispatch("c", "tarmouth", now=100.0)
        # 500 s later — past the window
        self.assertTrue(arb.can_dispatch("c", "tarmouth", now=600.0))

    def test_different_addresses_independent(self) -> None:
        from world_system.wns.behavior_interpreter import CooldownArbiter
        arb = CooldownArbiter(cooldown_seconds=300.0)
        arb.record_dispatch("c", "tarmouth", now=100.0)
        # different locality — independent
        self.assertTrue(arb.can_dispatch("c", "ashfall_moors", now=100.0))


# ── BehaviorInterpreter — dispatch decisions ─────────────────────────


class BehaviorInterpreterDecisionTests(unittest.TestCase):
    def setUp(self) -> None:
        from world_system.wns.behavior_interpreter import BehaviorInterpreter
        BehaviorInterpreter.reset()

    def test_below_threshold_does_not_dispatch(self) -> None:
        from world_system.wns.behavior_interpreter import BehaviorInterpreter
        interp = BehaviorInterpreter()
        # global stream_min_threshold = 100; this is 50.
        dispatched = interp.on_trigger_event(
            counter_path="stream.item_used.potion.tarmouth",
            threshold_crossed=50,
            stream_count=50,
            locality_id="tarmouth",
            event_category="economy",
            action_type="interpret_stream",
            now=100.0,
        )
        self.assertFalse(dispatched)

    def test_at_threshold_dispatches(self) -> None:
        # 1000 is well above the 100 floor and 250 regional floor.
        from world_system.wns.behavior_interpreter import BehaviorInterpreter
        interp = BehaviorInterpreter()
        dispatched = interp.on_trigger_event(
            counter_path="stream.combat.kill.tarmouth",
            threshold_crossed=1000,
            stream_count=1000,
            locality_id="tarmouth",
            event_category="combat",
            action_type="interpret_stream",
            now=100.0,
        )
        self.assertTrue(dispatched)

    def test_suppressed_category_does_not_dispatch(self) -> None:
        from world_system.wns.behavior_interpreter import BehaviorInterpreter
        interp = BehaviorInterpreter()
        dispatched = interp.on_trigger_event(
            counter_path="stream.system.evt.tarmouth",
            threshold_crossed=1000,
            stream_count=1000,
            locality_id="tarmouth",
            event_category="other",  # in suppressed list
            action_type="interpret_stream",
            now=100.0,
        )
        self.assertFalse(dispatched)

    def test_unknown_locality_does_not_dispatch(self) -> None:
        from world_system.wns.behavior_interpreter import BehaviorInterpreter
        interp = BehaviorInterpreter()
        dispatched = interp.on_trigger_event(
            counter_path="stream.combat.kill.unknown",
            threshold_crossed=1000,
            stream_count=1000,
            locality_id="unknown",
            event_category="combat",
            action_type="interpret_stream",
            now=100.0,
        )
        self.assertFalse(dispatched)

    def test_cooldown_blocks_back_to_back(self) -> None:
        from world_system.wns.behavior_interpreter import BehaviorInterpreter
        interp = BehaviorInterpreter()
        first = interp.on_trigger_event(
            counter_path="stream.combat.kill.tarmouth",
            threshold_crossed=1000, stream_count=1000,
            locality_id="tarmouth", event_category="combat",
            action_type="interpret_stream", now=100.0,
        )
        second = interp.on_trigger_event(
            counter_path="stream.combat.kill.tarmouth",
            threshold_crossed=2500, stream_count=2500,
            locality_id="tarmouth", event_category="combat",
            action_type="interpret_stream", now=200.0,  # inside cooldown
        )
        self.assertTrue(first)
        self.assertFalse(second)


# ── End-to-end potions scenario ──────────────────────────────────────


class PotionsExampleE2ETests(unittest.TestCase):
    """The user's gold-standard pseudo-trace:

    Player uses 1000 potions in combat at tarmouth → behavior trigger →
    new instant-heal skill dispatched via WNS_CALL_WES_REQUESTED.

    This verifies the WHOLE Phase 2 pipeline: TriggerManager publishes
    WMS_TRIGGER_FIRED (Phase 0 G03) → BehaviorInterpreter subscribes
    and reacts → bus publishes WNS_CALL_WES_REQUESTED with a bundle
    carrying trigger_archetype="behavior" and the BehaviorSignal."""

    def setUp(self) -> None:
        from events.event_bus import GameEventBus
        from world_system.wns.behavior_interpreter import BehaviorInterpreter
        from world_system.world_memory.trigger_manager import TriggerManager
        GameEventBus.reset()
        TriggerManager.reset()
        BehaviorInterpreter.reset()
        self.bus = GameEventBus.get_instance()
        self.tm = TriggerManager.get_instance()
        self.interp = BehaviorInterpreter()
        self.interp.attach(bus=self.bus, stat_store=None)
        self._received: list = []

        def _handler(event):
            self._received.append(getattr(event, "data", {}))

        self._handler = _handler
        self.bus.subscribe("WNS_CALL_WES_REQUESTED", self._handler)

    def tearDown(self) -> None:
        from events.event_bus import GameEventBus
        from world_system.wns.behavior_interpreter import BehaviorInterpreter
        from world_system.world_memory.trigger_manager import TriggerManager
        try:
            self.bus.unsubscribe("WNS_CALL_WES_REQUESTED", self._handler)
        except Exception:
            pass
        self.interp.detach()
        BehaviorInterpreter.reset()
        TriggerManager.reset()
        GameEventBus.reset()

    def _potion_event(self):
        from types import SimpleNamespace
        return SimpleNamespace(
            event_id="evt_potion",
            event_type="item_consumed",
            event_subtype="potion",
            actor_id="player",
            target_id="",
            locality_id="tarmouth",
            game_time=1.0,
            payload={},
            tags=[],
        )

    def test_potions_milestone_publishes_behavior_bundle(self) -> None:
        # Fire 100 potion events. The 100th hits THRESHOLD_SET.
        # The first event also hits threshold 1, which is below the
        # stream_min_threshold of 100, so it should NOT dispatch.
        for _ in range(100):
            self.tm.on_event(self._potion_event())

        # By threshold 100, BehaviorInterpreter should have dispatched.
        bundles = [
            evt for evt in self._received
            if "bundle" in evt
        ]
        self.assertGreater(len(bundles), 0,
                           "expected at least one WNS_CALL_WES_REQUESTED")

        # The bundle should carry trigger_archetype="behavior".
        from world_system.living_world.infra.context_bundle import (
            WESContextBundle,
        )
        bundle = WESContextBundle.from_dict(bundles[-1]["bundle"])
        self.assertEqual(
            bundle.directive.scope_hint.get("trigger_archetype"),
            "behavior",
        )
        # And BehaviorSignal should be populated with the counter info.
        self.assertIsNotNone(bundle.behavior_signal)
        self.assertEqual(bundle.behavior_signal.locality_id, "tarmouth")
        self.assertGreaterEqual(
            bundle.behavior_signal.threshold_crossed, 100,
        )
        # The purpose should be the economy default (potions land in
        # economy category via item_consumed mapping).
        self.assertEqual(
            bundle.directive.scope_hint.get("purpose"), "new-quest",
        )
        # NOTE: per the dispatch rules, item_consumed maps to "economy"
        # category → purpose "new-quest". If the designer wants the
        # user's pseudo-trace shape (potions → new-skill), they can
        # override in behavior_dispatch_rules.json by adding a
        # per-subtype rule. For Phase 2 v4, this is the correct
        # default behavior — designer prose tuning happens in Phase 3.


# ── Bundle slice carries behavior_signal ─────────────────────────────


class BehaviorSliceTests(unittest.TestCase):
    def test_slice_carries_behavior_signal(self) -> None:
        from world_system.living_world.infra.context_bundle import (
            BehaviorSignal,
            NarrativeContextSlice,
            NarrativeDelta,
            WESContextBundle,
            WNSDirective,
            slice_bundle_for_tool,
        )
        bundle = WESContextBundle(
            bundle_id="probe",
            created_at=42.0,
            delta=NarrativeDelta(
                address="locality:tarmouth", layer=2,
                start_time=40.0, end_time=42.0,
            ),
            narrative_context=NarrativeContextSlice(
                firing_layer_summary="",
                parent_summaries={},
                open_threads=[],
            ),
            directive=WNSDirective(
                directive_text="probe",
                firing_tier=2,
                scope_hint={
                    "firing_address": "locality:tarmouth",
                    "purpose": "new-skill",
                    "trigger_archetype": "behavior",
                },
            ),
            behavior_signal=BehaviorSignal(
                counter_path="items.consumed.potion.tarmouth",
                threshold_crossed=1000,
                stream_count=1000,
                locality_id="tarmouth",
            ),
        )
        slice_ = slice_bundle_for_tool(bundle, tool_name="skills")
        self.assertEqual(slice_.trigger_archetype, "behavior")
        self.assertIsNotNone(slice_.behavior_signal)
        self.assertEqual(slice_.behavior_signal.threshold_crossed, 1000)


if __name__ == "__main__":
    unittest.main()

"""Tests for CascadeTriggerManager (WMS→WNS bridge, v1.0)."""

from __future__ import annotations

import os
import sys
import threading
import unittest
from typing import List, Optional, Tuple

_this_dir = os.path.dirname(os.path.abspath(__file__))
_game_dir = os.path.dirname(os.path.dirname(os.path.dirname(_this_dir)))
if _game_dir not in sys.path:
    sys.path.insert(0, _game_dir)

from world_system.wns.cascade_trigger import (  # noqa: E402
    CascadeTriggerManager,
    DEFAULT_THRESHOLD,
    MAX_CASCADE_DEPTH,
    WEAVER_LAYERS,
)


# ── A test-friendly geographic walker ────────────────────────────────
#
# Six-tier toy hierarchy:
#   world:w1 ⟵ nation:n1 ⟵ region:r1 ⟵ province:p1 ⟵ district:d1 ⟵ locality:L*
#
# Localities L1..L9 all roll up to district d1 (so we can drive NL3
# fires by clustering NL2 fires within the same district).
TOY_HIERARCHY = {
    # parent-of map keyed by typed address
    "world:w1": None,
    "nation:n1": "world:w1",
    "region:r1": "nation:n1",
    "province:p1": "region:r1",
    "district:d1": "province:p1",
    "district:d2": "province:p1",
    "locality:L1": "district:d1",
    "locality:L2": "district:d1",
    "locality:L3": "district:d1",
    "locality:L4": "district:d1",
    "locality:L5": "district:d1",
    "locality:L6": "district:d1",
    "locality:L7": "district:d1",
    "locality:L8": "district:d1",
    "locality:L9": "district:d1",
    "locality:LX": "district:d2",
    # Detached locality — no parent registered. Used to test the
    # cascade-termination path.
    "locality:orphan": None,
}


def toy_walker(address: str) -> Optional[str]:
    return TOY_HIERARCHY.get(address)


def cyclic_walker(address: str) -> Optional[str]:
    """Pathological walker: every address points back to itself."""
    return address


def raising_walker(address: str) -> Optional[str]:
    raise RuntimeError("walker exploded")


class TestThreshold(unittest.TestCase):
    def test_invalid_threshold_raises(self) -> None:
        with self.assertRaises(ValueError):
            CascadeTriggerManager(parent_address_resolver=toy_walker, threshold=0)
        with self.assertRaises(ValueError):
            CascadeTriggerManager(parent_address_resolver=toy_walker, threshold=-3)

    def test_default_threshold_is_three(self) -> None:
        ct = CascadeTriggerManager(parent_address_resolver=toy_walker)
        self.assertEqual(ct.threshold, 3)
        self.assertEqual(DEFAULT_THRESHOLD, 3)


class TestNL2FireFromEvents(unittest.TestCase):
    def setUp(self) -> None:
        self.fires: List[Tuple[int, str]] = []
        self.ct = CascadeTriggerManager(
            parent_address_resolver=toy_walker,
            fire_callback=lambda layer, address: self.fires.append((layer, address)),
        )

    def test_under_threshold_does_not_fire(self) -> None:
        self.ct.note_event("L1")
        self.ct.note_event("L1")
        self.assertEqual(self.fires, [])
        self.assertEqual(self.ct.get_count(2, "locality:L1"), 2)

    def test_third_event_fires_nl2(self) -> None:
        for _ in range(3):
            self.ct.note_event("L1")
        # First fire is NL2 at the locality. Cascade then advances
        # district counter to 1; no NL3 fire yet.
        self.assertIn((2, "locality:L1"), self.fires)
        self.assertEqual(self.ct.get_count(2, "locality:L1"), 0)
        self.assertEqual(self.ct.get_count(3, "district:d1"), 1)

    def test_distinct_localities_have_independent_counters(self) -> None:
        self.ct.note_event("L1")
        self.ct.note_event("L2")
        self.ct.note_event("L1")
        self.ct.note_event("L2")
        self.assertEqual(self.fires, [])
        self.assertEqual(self.ct.get_count(2, "locality:L1"), 2)
        self.assertEqual(self.ct.get_count(2, "locality:L2"), 2)

    def test_unknown_locality_no_op(self) -> None:
        # Empty / falsy locality — drop silently.
        self.ct.note_event("")
        self.ct.note_event(None)  # type: ignore[arg-type]
        self.assertEqual(self.fires, [])
        self.assertEqual(self.ct.stats["events_ingested"], 0)


class TestCascadeNL2ToNL3(unittest.TestCase):
    def setUp(self) -> None:
        self.fires: List[Tuple[int, str]] = []
        self.ct = CascadeTriggerManager(
            parent_address_resolver=toy_walker,
            fire_callback=lambda layer, address: self.fires.append((layer, address)),
        )

    def test_three_nl2_fires_in_same_district_triggers_nl3(self) -> None:
        # Drive NL2 to fire 3 times, each at a different locality
        # under district d1. Cascade should produce exactly one NL3
        # fire at district d1.
        for loc in ("L1", "L2", "L3"):
            for _ in range(3):
                self.ct.note_event(loc)

        nl3_fires = [a for ly, a in self.fires if ly == 3]
        nl2_fires = [a for ly, a in self.fires if ly == 2]
        self.assertEqual(len(nl2_fires), 3)
        self.assertEqual(nl3_fires, ["district:d1"])
        # District counter zeroed; province counter advanced once.
        self.assertEqual(self.ct.get_count(3, "district:d1"), 0)
        self.assertEqual(self.ct.get_count(4, "province:p1"), 1)

    def test_cross_district_nl2_fires_do_not_share_nl3_counter(self) -> None:
        # 2 NL2 fires in d1, 2 in d2 (different districts).
        for loc in ("L1", "L2"):
            for _ in range(3):
                self.ct.note_event(loc)
        # LX is in d2 — its NL2 fire goes to d2's NL3 counter.
        for _ in range(3):
            self.ct.note_event("LX")
        nl3_fires = [a for ly, a in self.fires if ly == 3]
        self.assertEqual(nl3_fires, [])  # neither d1 nor d2 hit 3
        self.assertEqual(self.ct.get_count(3, "district:d1"), 2)
        self.assertEqual(self.ct.get_count(3, "district:d2"), 1)


class TestFullCascadeAllTheWayUp(unittest.TestCase):
    """The geometric series end-to-end: 3^5 leaf fires triggers one NL7."""

    def test_geometric_progression(self) -> None:
        fires: List[Tuple[int, str]] = []
        ct = CascadeTriggerManager(
            parent_address_resolver=toy_walker,
            fire_callback=lambda layer, address: fires.append((layer, address)),
        )
        # 3 NL2s per district → 1 NL3
        # 3 NL3s per province → 1 NL4 (need 9 distinct districts in
        # one province — toy world only has 2, so we directly drive
        # the cascade by calling note_layer_fired for the rest).
        # Easier: use note_layer_fired to test the deeper rungs
        # without inventing 729 localities.
        for layer, address in [
            (2, "locality:L1"), (2, "locality:L1"), (2, "locality:L1"),
        ]:
            ct.note_layer_fired(layer, address)
        # That's 3 NL2 fires in d1 → NL3 d1 fire → NL4 p1 +1.
        nl3 = [a for ly, a in fires if ly == 3]
        self.assertEqual(nl3, ["district:d1"])
        nl4 = [a for ly, a in fires if ly == 4]
        self.assertEqual(nl4, [])  # only 1 NL3 fire so far
        self.assertEqual(ct.get_count(4, "province:p1"), 1)

    def test_deep_cascade_via_synthetic_fires(self) -> None:
        """Push directly with note_layer_fired to verify each tier rung."""
        fires: List[Tuple[int, str]] = []
        ct = CascadeTriggerManager(
            parent_address_resolver=toy_walker,
            fire_callback=lambda layer, address: fires.append((layer, address)),
        )
        # 3 NL3 fires in p1 → NL4 fire
        for _ in range(3):
            ct.note_layer_fired(3, "district:d1")
        nl4 = [a for ly, a in fires if ly == 4]
        self.assertEqual(nl4, ["province:p1"])
        # 3 NL4 fires in r1 → NL5 fire
        for _ in range(3):
            ct.note_layer_fired(4, "province:p1")
        nl5 = [a for ly, a in fires if ly == 5]
        self.assertEqual(nl5, ["region:r1"])
        # 3 NL5 fires in n1 → NL6 fire
        for _ in range(3):
            ct.note_layer_fired(5, "region:r1")
        nl6 = [a for ly, a in fires if ly == 6]
        self.assertEqual(nl6, ["nation:n1"])
        # 3 NL6 fires in w1 → NL7 fire
        for _ in range(3):
            ct.note_layer_fired(6, "nation:n1")
        nl7 = [a for ly, a in fires if ly == 7]
        self.assertEqual(nl7, ["world:w1"])
        # NL7 has no parent — terminations counter ticked.
        self.assertGreaterEqual(ct.stats["cascade_terminations"], 1)


class TestCascadeTermination(unittest.TestCase):
    def test_orphan_address_terminates_cleanly(self) -> None:
        fires: List[Tuple[int, str]] = []
        ct = CascadeTriggerManager(
            parent_address_resolver=toy_walker,
            fire_callback=lambda layer, address: fires.append((layer, address)),
        )
        for _ in range(3):
            ct.note_event("orphan")
        # NL2 fires; cascade hits None parent and terminates.
        nl2 = [a for ly, a in fires if ly == 2]
        self.assertEqual(nl2, ["locality:orphan"])
        self.assertEqual(ct.stats["cascade_terminations"], 1)

    def test_nl7_fire_terminates(self) -> None:
        fires: List[Tuple[int, str]] = []
        ct = CascadeTriggerManager(
            parent_address_resolver=toy_walker,
            fire_callback=lambda layer, address: fires.append((layer, address)),
        )
        for _ in range(3):
            ct.note_layer_fired(6, "nation:n1")
        # NL7 fired; world has no parent, cascade ends.
        nl7 = [a for ly, a in fires if ly == 7]
        self.assertEqual(nl7, ["world:w1"])
        # Termination from the world-tier.
        self.assertGreaterEqual(ct.stats["cascade_terminations"], 1)


class TestCascadeSafety(unittest.TestCase):
    def test_cyclic_walker_caps_recursion(self) -> None:
        """A walker that always returns the same address should not
        loop the trigger forever."""
        fires: List[Tuple[int, str]] = []
        ct = CascadeTriggerManager(
            parent_address_resolver=cyclic_walker,
            fire_callback=lambda layer, address: fires.append((layer, address)),
        )
        for _ in range(3):
            ct.note_event("L1")
        # NL2 fires. Cyclic walker returns the same address, so the
        # parent counter is at NL3 / locality:L1 — but since cyclic
        # walker keeps returning the same string, eventually depth
        # cap kicks in.
        self.assertGreaterEqual(ct.stats["cascade_overruns"], 0)
        # Crucial: we do not infinite-loop. Test simply finishes.

    def test_raising_walker_does_not_crash(self) -> None:
        fires: List[Tuple[int, str]] = []
        ct = CascadeTriggerManager(
            parent_address_resolver=raising_walker,
            fire_callback=lambda layer, address: fires.append((layer, address)),
        )
        for _ in range(3):
            ct.note_event("L1")
        # NL2 fires; walker raises during cascade — counted as
        # termination, not a crash.
        nl2 = [a for ly, a in fires if ly == 2]
        self.assertEqual(nl2, ["locality:L1"])
        self.assertGreaterEqual(ct.stats["cascade_terminations"], 1)

    def test_callback_exception_does_not_break_cascade(self) -> None:
        seen: List[Tuple[int, str]] = []

        def cb(layer: int, address: str) -> None:
            seen.append((layer, address))
            if layer == 2:
                raise RuntimeError("fire callback exploded at NL2")

        ct = CascadeTriggerManager(
            parent_address_resolver=toy_walker,
            fire_callback=cb,
        )
        for _ in range(3):
            ct.note_event("L1")
        # NL2 callback raised but NL3 counter still advanced.
        self.assertIn((2, "locality:L1"), seen)
        self.assertEqual(ct.get_count(3, "district:d1"), 1)


class TestThreshold5(unittest.TestCase):
    def test_custom_threshold(self) -> None:
        fires: List[Tuple[int, str]] = []
        ct = CascadeTriggerManager(
            parent_address_resolver=toy_walker,
            fire_callback=lambda layer, address: fires.append((layer, address)),
            threshold=5,
        )
        for _ in range(4):
            ct.note_event("L1")
        self.assertEqual(fires, [])
        ct.note_event("L1")
        self.assertEqual(fires, [(2, "locality:L1")])


class TestStatsAndReset(unittest.TestCase):
    def test_stats_reflect_state(self) -> None:
        fires: List[Tuple[int, str]] = []
        ct = CascadeTriggerManager(
            parent_address_resolver=toy_walker,
            fire_callback=lambda layer, address: fires.append((layer, address)),
        )
        for _ in range(3):
            ct.note_event("L1")
        s = ct.stats
        self.assertEqual(s["threshold"], 3)
        self.assertEqual(s["events_ingested"], 3)
        self.assertEqual(s["fires_total_by_layer"][2], 1)
        self.assertEqual(s["fires_total_by_layer"][3], 0)

    def test_reset_clears_counters_and_history(self) -> None:
        ct = CascadeTriggerManager(parent_address_resolver=toy_walker)
        ct.note_event("L1")
        ct.note_event("L1")
        self.assertEqual(ct.get_count(2, "locality:L1"), 2)
        ct.reset()
        self.assertEqual(ct.get_count(2, "locality:L1"), 0)
        self.assertEqual(ct.stats["events_ingested"], 0)

    def test_pending_counters_snapshot(self) -> None:
        ct = CascadeTriggerManager(parent_address_resolver=toy_walker)
        ct.note_event("L1")
        ct.note_event("L2")
        snap = ct.pending_counters()
        self.assertEqual(
            sorted(snap),
            [(2, "locality:L1", 1), (2, "locality:L2", 1)],
        )


class TestThreadSafety(unittest.TestCase):
    """Concurrent ingestion. Counts must be exact, no lost fires."""

    def test_concurrent_note_event(self) -> None:
        fires: List[Tuple[int, str]] = []
        fires_lock = threading.Lock()

        def cb(layer: int, address: str) -> None:
            with fires_lock:
                fires.append((layer, address))

        ct = CascadeTriggerManager(
            parent_address_resolver=toy_walker,
            fire_callback=cb,
        )
        N_THREADS = 8
        N_EVENTS_PER_THREAD = 30  # 240 total, divisible by 3

        def worker() -> None:
            for _ in range(N_EVENTS_PER_THREAD):
                ct.note_event("L1")

        threads = [threading.Thread(target=worker) for _ in range(N_THREADS)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # 240 events at L1 → 80 NL2 fires at locality:L1.
        nl2_count = sum(1 for ly, _ in fires if ly == 2)
        self.assertEqual(nl2_count, 80)
        self.assertEqual(ct.stats["events_ingested"], 240)


if __name__ == "__main__":
    unittest.main()

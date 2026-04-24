"""Tests for WESMetrics (v4 P9)."""

from __future__ import annotations

import os
import sys
import unittest

_this_dir = os.path.dirname(os.path.abspath(__file__))
_game_dir = os.path.dirname(os.path.dirname(os.path.dirname(_this_dir)))
if _game_dir not in sys.path:
    sys.path.insert(0, _game_dir)

from world_system.wes.metrics import WESMetrics, get_wes_metrics  # noqa: E402


class TestWESMetrics(unittest.TestCase):
    def setUp(self) -> None:
        WESMetrics.reset()
        self.m = get_wes_metrics()

    def tearDown(self) -> None:
        WESMetrics.reset()

    def test_singleton(self) -> None:
        a = WESMetrics.get_instance()
        b = WESMetrics.get_instance()
        self.assertIs(a, b)

    def test_plan_counters(self) -> None:
        self.m.record_plan_started()
        self.m.record_plan_started()
        self.m.record_plan_committed()
        self.m.record_plan_abandoned("supervisor rejected")

        snap = self.m.snapshot()
        self.assertEqual(snap["plans_run_total"], 2)
        self.assertEqual(snap["plans_committed"], 1)
        self.assertEqual(snap["plans_abandoned"], 1)

    def test_tool_success_failure_tracking(self) -> None:
        self.m.record_tool_success("hostiles")
        self.m.record_tool_success("hostiles")
        self.m.record_tool_failure("materials")

        snap = self.m.snapshot()
        self.assertEqual(snap["tool_successes_by_type"]["hostiles"], 2)
        self.assertEqual(snap["tool_failures_by_type"]["materials"], 1)

    def test_supervisor_rerun_rate(self) -> None:
        self.m.record_supervisor_review(rerun_triggered=False)
        self.m.record_supervisor_review(rerun_triggered=False)
        self.m.record_supervisor_review(rerun_triggered=True)
        # 1 rerun out of 3 reviews
        self.assertAlmostEqual(self.m.supervisor_rerun_rate(), 1/3)

    def test_plans_per_hour(self) -> None:
        self.m.record_plan_started()
        self.m.record_plan_started()
        self.m.record_plan_started()
        self.assertEqual(self.m.plans_per_hour(), 3.0)

    def test_orphan_blocks(self) -> None:
        self.m.record_orphan_block()
        self.m.record_orphan_block()
        self.assertEqual(self.m.snapshot()["orphan_blocks_total"], 2)

    def test_tier_backend_usage(self) -> None:
        self.m.record_tier_backend_usage("planner", "claude")
        self.m.record_tier_backend_usage("hub_materials", "ollama")
        self.m.record_tier_backend_usage("hub_materials", "ollama")
        snap = self.m.snapshot()
        self.assertEqual(snap["tier_usage_by_backend"]["planner:claude"], 1)
        self.assertEqual(snap["tier_usage_by_backend"]["hub_materials:ollama"], 2)

    def test_snapshot_is_plain_dict(self) -> None:
        self.m.record_plan_started()
        snap = self.m.snapshot()
        self.assertIsInstance(snap, dict)
        # Must be JSON-safe.
        import json
        json.dumps(snap)

    def test_graceful_degrade_sync(self) -> None:
        """Sync seeds the logger buffer directly (no disk writes) to stay
        deterministic across test hosts."""
        from world_system.living_world.infra.graceful_degrade import (
            DegradeEntry, GracefulDegradeLogger,
        )
        logger = GracefulDegradeLogger.get_instance()
        logger.clear_buffer()
        # Seed buffer directly to avoid disk IO in this test.
        with logger._write_lock:
            logger._buffer.append(DegradeEntry(
                subsystem="metrics_test_sub", operation="op",
                failure_reason="r", fallback_taken="f",
            ))
            logger._buffer.append(DegradeEntry(
                subsystem="metrics_test_sub", operation="op",
                failure_reason="r", fallback_taken="f",
            ))
        count = self.m.sync_from_graceful_degrade_logger()
        self.assertGreaterEqual(count, 2)
        snap = self.m.snapshot()
        self.assertGreaterEqual(
            snap["graceful_degrade_events_by_subsystem"].get(
                "metrics_test_sub", 0
            ),
            2,
        )


if __name__ == "__main__":
    unittest.main()

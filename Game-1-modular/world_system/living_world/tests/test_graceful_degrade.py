"""Tests for the graceful-degrade logger (v4 P0 — CC3)."""

from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest

_this_dir = os.path.dirname(os.path.abspath(__file__))
_game_dir = os.path.dirname(os.path.dirname(os.path.dirname(_this_dir)))
if _game_dir not in sys.path:
    sys.path.insert(0, _game_dir)

from world_system.living_world.infra.graceful_degrade import (  # noqa: E402
    DegradeEntry,
    GracefulDegradeLogger,
    SEVERITY_ERROR,
    SEVERITY_INFO,
    SEVERITY_WARNING,
    get_graceful_degrade_logger,
    log_degrade,
    surface_visible_wes_failure,
)


class TestGracefulDegradeLogger(unittest.TestCase):

    def setUp(self) -> None:
        self.tempdir = tempfile.mkdtemp(prefix="graceful_degrade_test_")
        GracefulDegradeLogger.reset(log_dir=self.tempdir)
        self.logger = get_graceful_degrade_logger()

    def tearDown(self) -> None:
        # Leave temp files in place; OS cleans tempdirs.
        GracefulDegradeLogger.reset()

    def test_log_degrade_persists_to_disk(self) -> None:
        log_degrade(
            subsystem="test_subsys",
            operation="test_op",
            failure_reason="test_reason",
            fallback_taken="test_fallback",
            severity=SEVERITY_WARNING,
            context={"key": "value"},
        )

        # At least one file exists in the logger's dir.
        files = [f for f in os.listdir(self.tempdir) if f.endswith(".json")]
        self.assertEqual(len(files), 1)

        with open(os.path.join(self.tempdir, files[0])) as f:
            data = json.load(f)
        self.assertEqual(data["subsystem"], "test_subsys")
        self.assertEqual(data["operation"], "test_op")
        self.assertEqual(data["severity"], SEVERITY_WARNING)
        self.assertEqual(data["context"], {"key": "value"})
        self.assertTrue(data["timestamp_iso"])

    def test_invalid_severity_downgrades_to_warning(self) -> None:
        log_degrade(
            subsystem="s", operation="o", failure_reason="r", fallback_taken="f",
            severity="not_a_real_severity",
        )
        entries = self.logger.recent()
        self.assertEqual(entries[-1].severity, SEVERITY_WARNING)

    def test_ring_buffer_bounded(self) -> None:
        original = GracefulDegradeLogger.MAX_BUFFER
        GracefulDegradeLogger.MAX_BUFFER = 4
        try:
            for i in range(10):
                log_degrade("s", f"op_{i}", "r", "f", severity=SEVERITY_INFO)
            entries = self.logger.recent(n=50)
            self.assertLessEqual(len(entries), 4)
            self.assertEqual(entries[-1].operation, "op_9")
        finally:
            GracefulDegradeLogger.MAX_BUFFER = original

    def test_surface_sink_fires_on_error_only(self) -> None:
        received = []

        def sink(entry: DegradeEntry) -> None:
            received.append(entry)

        self.logger.register_surface_sink(sink)

        log_degrade("s", "o", "r", "f", severity=SEVERITY_INFO)
        log_degrade("s", "o", "r", "f", severity=SEVERITY_WARNING)
        log_degrade("s", "o", "r", "f", severity=SEVERITY_ERROR)
        self.assertEqual(len(received), 1)
        self.assertEqual(received[0].severity, SEVERITY_ERROR)

    def test_surface_sink_exception_swallowed(self) -> None:
        def bad_sink(entry: DegradeEntry) -> None:
            raise RuntimeError("intentional")
        self.logger.register_surface_sink(bad_sink)

        # Must not raise out of log_degrade.
        log_degrade("s", "o", "r", "f", severity=SEVERITY_ERROR)

    def test_surface_visible_wes_failure_is_error(self) -> None:
        received = []
        self.logger.register_surface_sink(received.append)

        surface_visible_wes_failure(
            operation="plan_commit",
            failure_reason="supervisor rejected after 2 reruns",
            fallback_taken="plan abandoned",
        )
        self.assertEqual(len(received), 1)
        self.assertEqual(received[0].subsystem, "wes")
        self.assertEqual(received[0].severity, SEVERITY_ERROR)

    def test_clear_buffer(self) -> None:
        log_degrade("s", "o", "r", "f")
        self.assertGreater(len(self.logger.recent()), 0)
        self.logger.clear_buffer()
        self.assertEqual(len(self.logger.recent()), 0)


if __name__ == "__main__":
    unittest.main()

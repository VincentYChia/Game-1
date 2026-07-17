"""Tests for the graceful_degrade → observability bridge (2026-06-09).

Closes Cross-cutting Risk #1 (silent fallback visibility). Every
``log_degrade`` call should mirror as an ``EVT_GRACEFUL_DEGRADE``
pipeline event so the F12 overlay shows live silent fallbacks.
"""

import os
import sys
import tempfile
import unittest
from pathlib import Path

_THIS_DIR = Path(__file__).parent
_GAME_DIR = _THIS_DIR.parent
if str(_GAME_DIR) not in sys.path:
    sys.path.insert(0, str(_GAME_DIR))

from world_system.living_world.infra.graceful_degrade import (  # noqa: E402
    GracefulDegradeLogger,
    SEVERITY_ERROR,
    SEVERITY_INFO,
    SEVERITY_WARNING,
    log_degrade,
)
from world_system.wes.observability_runtime import (  # noqa: E402
    EVT_GRACEFUL_DEGRADE,
    RuntimeObservability,
    install_graceful_degrade_bridge,
    obs_recent,
    obs_stats,
)


class _BridgeTestBase(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.mkdtemp()
        # Reset both singletons so each test starts clean.
        GracefulDegradeLogger.reset(log_dir=self.temp_dir)
        RuntimeObservability.reset()
        install_graceful_degrade_bridge()

    def tearDown(self) -> None:
        GracefulDegradeLogger.reset()
        RuntimeObservability.reset()
        try:
            for name in os.listdir(self.temp_dir):
                os.remove(os.path.join(self.temp_dir, name))
            os.rmdir(self.temp_dir)
        except Exception:
            pass


class TestBridgeBasicMirroring(_BridgeTestBase):
    """Every log_degrade entry becomes a pipeline event."""

    def test_info_severity_mirrors_to_observability(self) -> None:
        log_degrade(
            subsystem="npc_agent",
            operation="generate_dialogue",
            failure_reason="BackendManager not initialized",
            fallback_taken="hardcoded cycling dialogue",
            severity=SEVERITY_INFO,
            context={"npc_id": "blacksmith_1"},
        )
        events = obs_recent(50)
        degrade_events = [e for e in events if e.event_type == EVT_GRACEFUL_DEGRADE]
        self.assertEqual(len(degrade_events), 1)
        self.assertIn("npc_agent.generate_dialogue", degrade_events[0].message)
        self.assertIn("hardcoded cycling dialogue", degrade_events[0].message)

    def test_warning_severity_mirrors(self) -> None:
        log_degrade(
            subsystem="backend_manager",
            operation="generate",
            failure_reason="Timeout: 30s",
            fallback_taken="mock backend",
            severity=SEVERITY_WARNING,
        )
        events = obs_recent(50)
        self.assertEqual(len([e for e in events if e.event_type == EVT_GRACEFUL_DEGRADE]), 1)

    def test_error_severity_still_mirrors_and_still_fires_legacy_sink(self) -> None:
        # Legacy WES error sinks should still work — bridge adds; doesn't replace.
        legacy_received = []

        def _legacy_sink(entry):
            legacy_received.append(entry)

        GracefulDegradeLogger.get_instance().register_surface_sink(_legacy_sink)
        log_degrade(
            subsystem="wes",
            operation="dispatch_plan",
            failure_reason="RegistryStaleException",
            fallback_taken="rollback",
            severity=SEVERITY_ERROR,
        )
        # Bridge sink fired.
        events = obs_recent(50)
        self.assertEqual(len([e for e in events if e.event_type == EVT_GRACEFUL_DEGRADE]), 1)
        # Legacy WES error sink also fired.
        self.assertEqual(len(legacy_received), 1)


class TestBridgeIdempotency(_BridgeTestBase):
    """Installing the bridge twice does not double-mirror."""

    def test_install_twice_only_registers_once(self) -> None:
        install_graceful_degrade_bridge()
        install_graceful_degrade_bridge()
        log_degrade(
            subsystem="npc_agent",
            operation="generate_dialogue",
            failure_reason="boom",
            fallback_taken="static",
            severity=SEVERITY_INFO,
        )
        events = obs_recent(50)
        # Should be one mirror, not three.
        self.assertEqual(len([e for e in events if e.event_type == EVT_GRACEFUL_DEGRADE]), 1)


class TestBridgeCounterSurfaces(_BridgeTestBase):
    """obs_stats() exposes a counter for the new event so overlay can show it."""

    def test_counter_increments_per_degrade(self) -> None:
        for i in range(4):
            log_degrade(
                subsystem="npc_agent",
                operation="generate_dialogue",
                failure_reason=f"err_{i}",
                fallback_taken="static",
                severity=SEVERITY_INFO,
            )
        stats = obs_stats()
        self.assertEqual(stats.get(EVT_GRACEFUL_DEGRADE), 4)


class TestBridgeFieldsAreUseful(_BridgeTestBase):
    """The mirrored event carries enough info to be actionable."""

    def test_fields_include_severity_and_reason_prefix(self) -> None:
        log_degrade(
            subsystem="backend_manager",
            operation="generate",
            failure_reason="HTTPError: 429 Too Many Requests",
            fallback_taken="mock backend",
            severity=SEVERITY_WARNING,
        )
        events = [e for e in obs_recent(50) if e.event_type == EVT_GRACEFUL_DEGRADE]
        self.assertEqual(len(events), 1)
        evt = events[0]
        self.assertEqual(evt.fields.get("severity"), SEVERITY_WARNING)
        # Reason is truncated to 60 chars to keep overlay lines short.
        self.assertIn("HTTPError", evt.fields.get("reason", ""))


if __name__ == "__main__":
    unittest.main()

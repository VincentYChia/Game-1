"""Tests for :mod:`world_system.wes.observability_runtime`.

The module is small and pure: a singleton ring buffer + counters + an
env-gated stdout stream. These tests exercise:

- Singleton lifecycle (get_instance, reset).
- ``record`` stores events with the correct shape.
- ``WES_VERBOSE`` env truthy → stdout receives the formatted line.
- ``recent`` returns a snapshot (mutating the buffer doesn't change it).
- Buffer eviction respects the maxlen.
- ``stats`` reports per-type counts + meta.
- ``PipelineEvent.format_oneline`` produces a parseable tagged line.
"""

from __future__ import annotations

import io
import os
import sys
import unittest
from contextlib import redirect_stdout
from unittest import mock

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_GAME_DIR = os.path.dirname(os.path.dirname(os.path.dirname(_THIS_DIR)))
if _GAME_DIR not in sys.path:
    sys.path.insert(0, _GAME_DIR)

from world_system.wes.observability_runtime import (  # noqa: E402
    EVT_CASCADE_FIRED,
    EVT_WES_DISPATCHED,
    EVT_WMS_EVENT_RECEIVED,
    EVT_WNS_FIRED,
    PipelineEvent,
    RuntimeObservability,
    obs_clear,
    obs_record,
    obs_recent,
    obs_stats,
    obs_verbose_enabled,
)


class SingletonTestCase(unittest.TestCase):
    def setUp(self) -> None:
        RuntimeObservability.reset()

    def test_get_instance_returns_same(self) -> None:
        a = RuntimeObservability.get_instance()
        b = RuntimeObservability.get_instance()
        self.assertIs(a, b)

    def test_reset_creates_fresh_singleton(self) -> None:
        a = RuntimeObservability.get_instance()
        a.record(EVT_WNS_FIRED, "x")
        self.assertEqual(len(a.recent()), 1)
        RuntimeObservability.reset()
        b = RuntimeObservability.get_instance()
        self.assertIsNot(a, b)
        self.assertEqual(len(b.recent()), 0)


class RecordTestCase(unittest.TestCase):
    def setUp(self) -> None:
        RuntimeObservability.reset()
        # Make sure verbose is off for these tests.
        os.environ.pop("WES_VERBOSE", None)

    def test_record_stores_event_with_fields(self) -> None:
        obs_record(EVT_WNS_FIRED, "weaver done", layer=2, address="locality:hill")
        events = obs_recent()
        self.assertEqual(len(events), 1)
        evt = events[0]
        self.assertEqual(evt.event_type, EVT_WNS_FIRED)
        self.assertEqual(evt.message, "weaver done")
        self.assertEqual(evt.fields, {"layer": 2, "address": "locality:hill"})
        self.assertGreater(evt.timestamp, 0)

    def test_record_increments_counter(self) -> None:
        obs_record(EVT_WMS_EVENT_RECEIVED, "")
        obs_record(EVT_WMS_EVENT_RECEIVED, "")
        obs_record(EVT_WNS_FIRED, "")
        stats = obs_stats()
        self.assertEqual(stats[EVT_WMS_EVENT_RECEIVED], 2)
        self.assertEqual(stats[EVT_WNS_FIRED], 1)
        self.assertEqual(stats["_total"], 3)
        self.assertEqual(stats["_buffer_size"], 3)

    def test_record_swallows_internal_failures(self) -> None:
        """A weird recursive __repr__ in fields shouldn't break record."""

        class ExplodingRepr:
            def __repr__(self):
                raise RuntimeError("boom")

        # Should not raise even though field formatting could.
        obs_record(EVT_WNS_FIRED, "x", weird=ExplodingRepr())
        # Event should still be in the buffer (record itself succeeded).
        self.assertEqual(len(obs_recent()), 1)

    def test_recent_returns_snapshot(self) -> None:
        obs_record(EVT_WNS_FIRED, "first")
        snap = obs_recent()
        self.assertEqual(len(snap), 1)
        # Mutating later — the snapshot must not change.
        obs_record(EVT_WNS_FIRED, "second")
        self.assertEqual(len(snap), 1)
        self.assertEqual(len(obs_recent()), 2)

    def test_recent_n_returns_tail(self) -> None:
        for i in range(10):
            obs_record(EVT_WNS_FIRED, f"msg_{i}")
        tail = obs_recent(3)
        self.assertEqual(len(tail), 3)
        self.assertEqual(tail[-1].message, "msg_9")
        self.assertEqual(tail[0].message, "msg_7")

    def test_clear_resets_buffer_and_counters(self) -> None:
        obs_record(EVT_WNS_FIRED, "x")
        obs_clear()
        self.assertEqual(len(obs_recent()), 0)
        stats = obs_stats()
        self.assertEqual(stats["_total"], 0)


class BufferEvictionTestCase(unittest.TestCase):
    def setUp(self) -> None:
        RuntimeObservability.reset()
        # Inject a small instance so we can prove the maxlen path.
        small = RuntimeObservability(buffer_size=4)
        # Smuggle it into the singleton slot.
        with RuntimeObservability._instance_lock:
            RuntimeObservability._instance = small

    def test_eviction_at_maxlen(self) -> None:
        for i in range(10):
            obs_record(EVT_CASCADE_FIRED, f"i={i}")
        events = obs_recent()
        # Only the last 4 should remain.
        self.assertEqual(len(events), 4)
        self.assertEqual(events[0].message, "i=6")
        self.assertEqual(events[-1].message, "i=9")
        # Counters retain the full count even after eviction.
        stats = obs_stats()
        self.assertEqual(stats[EVT_CASCADE_FIRED], 10)
        self.assertEqual(stats["_buffer_size"], 4)


class VerboseEnvTestCase(unittest.TestCase):
    """``WES_VERBOSE`` truthy must produce a stdout line per record."""

    def setUp(self) -> None:
        RuntimeObservability.reset()

    def tearDown(self) -> None:
        os.environ.pop("WES_VERBOSE", None)

    def _record_with_env(self, env_value: str | None) -> str:
        if env_value is None:
            os.environ.pop("WES_VERBOSE", None)
        else:
            os.environ["WES_VERBOSE"] = env_value
        buf = io.StringIO()
        with redirect_stdout(buf):
            obs_record(EVT_WES_DISPATCHED, "test message", k=1)
        return buf.getvalue()

    def test_verbose_off_no_stdout(self) -> None:
        out = self._record_with_env(None)
        self.assertEqual(out, "")

    def test_verbose_on_writes_one_line(self) -> None:
        for value in ("1", "true", "yes", "on", "TRUE", "Yes"):
            RuntimeObservability.reset()
            out = self._record_with_env(value)
            self.assertIn(EVT_WES_DISPATCHED, out, f"value={value!r}")
            self.assertIn("test message", out)
            self.assertIn("k=1", out)
            self.assertEqual(out.count("\n"), 1)

    def test_verbose_off_for_falsy_values(self) -> None:
        for value in ("0", "false", "no", "off", ""):
            out = self._record_with_env(value)
            self.assertEqual(out, "", f"value={value!r}")

    def test_verbose_enabled_helper_matches_record(self) -> None:
        os.environ["WES_VERBOSE"] = "1"
        self.assertTrue(obs_verbose_enabled())
        os.environ["WES_VERBOSE"] = "0"
        self.assertFalse(obs_verbose_enabled())


class FormatOneLineTestCase(unittest.TestCase):
    def test_basic_format_includes_type_and_message(self) -> None:
        evt = PipelineEvent(
            timestamp=1700000000.5,
            event_type="X",
            message="hello",
        )
        line = evt.format_oneline()
        self.assertIn("[X]", line)
        self.assertIn("hello", line)

    def test_fields_serialize_inline(self) -> None:
        evt = PipelineEvent(
            timestamp=1700000000.5,
            event_type="X",
            message="msg",
            fields={"a": 1, "b": "two"},
        )
        line = evt.format_oneline()
        self.assertIn("a=1", line)
        self.assertIn("b=two", line)

    def test_no_fields_produces_no_paren_block(self) -> None:
        evt = PipelineEvent(
            timestamp=1700000000.5,
            event_type="X",
            message="msg",
        )
        line = evt.format_oneline()
        # No "()" empty block should appear.
        self.assertNotIn("()", line)


if __name__ == "__main__":
    unittest.main()

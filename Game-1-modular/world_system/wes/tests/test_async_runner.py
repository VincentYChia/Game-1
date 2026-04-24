"""Tests for AsyncLLMRunner (v4 P0.1, §5.7)."""

from __future__ import annotations

import os
import sys
import threading
import time
import unittest

_this_dir = os.path.dirname(os.path.abspath(__file__))
_game_dir = os.path.dirname(os.path.dirname(os.path.dirname(_this_dir)))
if _game_dir not in sys.path:
    sys.path.insert(0, _game_dir)

from world_system.wes.async_runner import (  # noqa: E402
    AsyncLLMRunner,
    get_async_runner,
)


class RunParallelTests(unittest.TestCase):
    def setUp(self) -> None:
        AsyncLLMRunner.reset()
        self.runner = get_async_runner()

    def test_runs_in_parallel_and_preserves_order(self) -> None:
        def make_task(value: int, sleep: float):
            def _task():
                time.sleep(sleep)
                return value
            return _task

        tasks = [
            make_task(1, 0.05),
            make_task(2, 0.05),
            make_task(3, 0.05),
            make_task(4, 0.05),
        ]
        t0 = time.monotonic()
        results = self.runner.run_parallel(tasks)
        elapsed = time.monotonic() - t0
        self.assertEqual(results, [1, 2, 3, 4])
        # Four 50ms sleeps sequentially would be 200ms; parallel must
        # be materially less. Be generous for CI flakiness.
        self.assertLess(elapsed, 0.18)

    def test_empty_list_returns_empty(self) -> None:
        self.assertEqual(self.runner.run_parallel([]), [])

    def test_task_exception_captured_per_slot(self) -> None:
        def ok():
            return "ok"

        def boom():
            raise ValueError("nope")

        results = self.runner.run_parallel([ok, boom, ok])
        self.assertEqual(results[0], "ok")
        self.assertIsInstance(results[1], BaseException)
        self.assertIsInstance(results[1], RuntimeError)
        # Original exception preserved as __cause__
        self.assertIsInstance(results[1].__cause__, ValueError)
        self.assertEqual(results[2], "ok")

    def test_timeout_records_timeout_error(self) -> None:
        def slow():
            time.sleep(2.0)
            return "never"

        def fast():
            return "ok"

        results = self.runner.run_parallel([slow, fast], timeout_s=0.1)
        self.assertIsInstance(results[0], TimeoutError)
        # fast task may have completed OR been skipped by deadline; accept both
        self.assertTrue(
            results[1] == "ok" or isinstance(results[1], TimeoutError),
            f"unexpected second slot: {results[1]!r}",
        )


class RunSingleTests(unittest.TestCase):
    def setUp(self) -> None:
        AsyncLLMRunner.reset()
        self.runner = get_async_runner()

    def test_simple_task_returns_value(self) -> None:
        self.assertEqual(self.runner.run_single(lambda: 42), 42)

    def test_exception_propagates(self) -> None:
        def boom():
            raise KeyError("missing")
        with self.assertRaises(KeyError):
            self.runner.run_single(boom)

    def test_timeout(self) -> None:
        with self.assertRaises(TimeoutError):
            self.runner.run_single(lambda: time.sleep(1.0), timeout_s=0.05)


class SingletonTests(unittest.TestCase):
    def test_singleton_identity(self) -> None:
        AsyncLLMRunner.reset()
        a = AsyncLLMRunner.get_instance()
        b = AsyncLLMRunner.get_instance()
        self.assertIs(a, b)

    def test_runs_on_daemon_threads(self) -> None:
        # Tasks should run on daemon threads so tests don't hang.
        AsyncLLMRunner.reset()
        runner = AsyncLLMRunner.get_instance()

        thread_is_daemon = {}

        def task():
            thread_is_daemon["daemon"] = threading.current_thread().daemon
            return 1

        runner.run_single(task)
        self.assertTrue(thread_is_daemon["daemon"])


if __name__ == "__main__":
    unittest.main()

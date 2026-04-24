"""AsyncLLMRunner — unified background-thread executor (v4 P0.1, §5.7).

Extracted from the crafting system's ``llm_item_generator.generate_async``
pattern into a reusable class. The WES dispatcher uses this to fan out
executor_tool calls within a plan step in parallel (§5.7). WNS weavers
will use the same class in later phases when their layer LLM scheduling
is non-trivial.

**Design invariants:**

- Uses ``threading.Thread(daemon=True)`` so background work never blocks
  interpreter shutdown.
- ``run_parallel`` is synchronous from the caller's perspective — it
  blocks until all tasks complete, collecting results in submission order.
- Exceptions raised inside a task are captured per-task and returned as
  ``RuntimeError`` shells on the task slot, never propagated through the
  barrier. Callers inspect results for exceptions explicitly.
- No ``concurrent.futures`` or ``asyncio`` dependency — matches the
  project's "no new pip dependencies" rule (see CLAUDE.md).

**Why not ``concurrent.futures.ThreadPoolExecutor``?** The project is
Python 3.13 — ThreadPoolExecutor would work — but the existing
``llm_item_generator`` pattern uses raw ``threading.Thread`` for its
loading-overlay integration, and matching that pattern keeps dispatcher
code consistent across the codebase.
"""

from __future__ import annotations

import threading
import time
from typing import Any, Callable, List, Optional


class _TaskSlot:
    """Holds the result or exception from one background task."""

    __slots__ = ("result", "error", "done", "_lock")

    def __init__(self) -> None:
        self.result: Any = None
        self.error: Optional[BaseException] = None
        self.done: bool = False
        self._lock = threading.Lock()

    def set_result(self, value: Any) -> None:
        with self._lock:
            self.result = value
            self.done = True

    def set_error(self, exc: BaseException) -> None:
        with self._lock:
            self.error = exc
            self.done = True


class AsyncLLMRunner:
    """Background-thread runner with parallel fan-out semantics.

    Stateless by design — all bookkeeping lives on the per-call slot
    objects. Safe to use as a singleton via :func:`get_async_runner` or
    to instantiate fresh per call.
    """

    _instance: Optional["AsyncLLMRunner"] = None
    _lock = threading.Lock()

    @classmethod
    def get_instance(cls) -> "AsyncLLMRunner":
        """Singleton accessor (matches project convention)."""
        with cls._lock:
            if cls._instance is None:
                cls._instance = cls()
            return cls._instance

    @classmethod
    def reset(cls) -> None:
        """Test helper."""
        with cls._lock:
            cls._instance = None

    # ── public API ────────────────────────────────────────────────────

    def run_single(
        self,
        task: Callable[[], Any],
        timeout_s: Optional[float] = None,
    ) -> Any:
        """Run ``task`` on a daemon thread and await its result.

        Equivalent to ``task()``, but executed on a background thread so
        the caller's thread never directly owns the call (matching
        dispatch semantics used by callers that do want separation).

        Args:
            task: A zero-argument callable.
            timeout_s: Optional wall-clock timeout. If the task doesn't
                complete in this time, raises ``TimeoutError``.

        Returns:
            Whatever ``task()`` returned.

        Raises:
            Whatever ``task()`` raised (re-raised on the caller's thread).
            TimeoutError if the timeout is exceeded.
        """
        slot = _TaskSlot()

        def _worker() -> None:
            try:
                slot.set_result(task())
            except BaseException as e:  # noqa: BLE001 — intentional capture
                slot.set_error(e)

        thread = threading.Thread(target=_worker, daemon=True)
        thread.start()
        thread.join(timeout=timeout_s)
        if thread.is_alive():
            raise TimeoutError(
                f"AsyncLLMRunner.run_single: task exceeded {timeout_s}s timeout"
            )
        if slot.error is not None:
            raise slot.error
        return slot.result

    def run_parallel(
        self,
        tasks: List[Callable[[], Any]],
        timeout_s: Optional[float] = None,
    ) -> List[Any]:
        """Run all ``tasks`` in parallel, return their results in order.

        **Error handling**: if a task raises, its slot in the returned
        list is a ``RuntimeError`` whose ``__cause__`` is the original
        exception. Callers inspect ``isinstance(r, BaseException)`` to
        detect per-task failure without forcing a global abort. This
        matches the dispatcher's need to catalog partial failures.

        Args:
            tasks: List of zero-argument callables.
            timeout_s: Optional per-runner wall-clock timeout. Applied
                to each thread's ``join`` call; does not terminate the
                underlying task (Python threads cannot be killed).

        Returns:
            List of length ``len(tasks)``. Each element is the task's
            return value, OR a ``RuntimeError`` wrapping the exception
            if the task failed, OR a ``TimeoutError`` if it exceeded
            the per-task timeout.
        """
        if not tasks:
            return []

        slots: List[_TaskSlot] = [_TaskSlot() for _ in tasks]
        threads: List[threading.Thread] = []

        for task, slot in zip(tasks, slots):
            def _worker(t: Callable[[], Any] = task,
                         s: _TaskSlot = slot) -> None:
                try:
                    s.set_result(t())
                except BaseException as e:  # noqa: BLE001
                    s.set_error(e)

            thread = threading.Thread(target=_worker, daemon=True)
            thread.start()
            threads.append(thread)

        deadline = None if timeout_s is None else time.monotonic() + timeout_s

        results: List[Any] = []
        for thread, slot in zip(threads, slots):
            remaining = (
                None if deadline is None
                else max(0.0, deadline - time.monotonic())
            )
            thread.join(timeout=remaining)
            if thread.is_alive():
                # Timed out — record a TimeoutError on this slot's result
                results.append(
                    TimeoutError(
                        f"task exceeded {timeout_s}s timeout in run_parallel"
                    )
                )
                continue
            if slot.error is not None:
                # Wrap original exception so the list stays pickleable
                # and the caller can see both class and message.
                wrapper = RuntimeError(
                    f"{type(slot.error).__name__}: {slot.error}"
                )
                wrapper.__cause__ = slot.error
                results.append(wrapper)
            else:
                results.append(slot.result)
        return results


def get_async_runner() -> AsyncLLMRunner:
    """Module-level accessor following the project's singleton pattern."""
    return AsyncLLMRunner.get_instance()


__all__ = ["AsyncLLMRunner", "get_async_runner"]

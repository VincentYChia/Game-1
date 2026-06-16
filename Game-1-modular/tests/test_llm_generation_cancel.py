"""
Guard for the invented-item generation cancel (ESC-to-cancel).

A player who triggers an invented-item generation used to be locked behind
the loading overlay until the LLM round-trip finished (or its 30s timeout).
ESC now abandons it: the overlay drops immediately, the worker's late
result is discarded, and because materials are only consumed on the success
path, cancelling costs the player nothing.
"""
import os
import sys

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

import systems.llm_item_generator as gen  # noqa: E402


def _start_fake_generation():
    """Put the module in the same state generate_async() would: a pending
    result + an active overlay (without spawning a real LLM worker)."""
    gen._background_result = gen.BackgroundGenerationResult()
    gen.get_loading_state().start(
        message="Generating Item...", overlay=True, subtitle="x")


def test_abandon_drops_overlay_and_marks_result():
    _start_fake_generation()
    ls = gen.get_loading_state()
    assert ls.is_loading and ls.overlay_mode

    had_pending = gen.abandon_background_generation()

    assert had_pending is True
    # Overlay is gone immediately (force_finish, no completion animation).
    assert not ls.is_loading
    assert not ls.overlay_mode
    assert gen._background_result.abandoned is True


def test_abandoned_late_result_is_discardable():
    """After cancel, the worker may still finish — the result is completed
    AND abandoned, which the engine poller uses to discard it."""
    _start_fake_generation()
    gen.abandon_background_generation()

    # Worker finishes after the cancel.
    gen._background_result.set_result(object())
    assert gen._background_result.completed is True
    assert gen._background_result.abandoned is True

    gen.clear_background_result()
    assert gen.get_background_result() is None


def test_abandon_with_nothing_pending_is_safe():
    gen.clear_background_result()
    gen.get_loading_state().force_finish()
    # Must not raise and reports nothing was pending.
    assert gen.abandon_background_generation() is False

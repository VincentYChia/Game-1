"""Tests for the ``WES_REQUIRE_REAL_LLM`` safety gate.

The smoking-gun question: when an operator sets
``WES_DISABLE_FIXTURES=1`` to issue real LLM calls, but Ollama isn't
running and no ``ANTHROPIC_API_KEY`` is set, does the chain silently
fall through to MockBackend's keyword-template responses?

Without the gate: yes, silently — and the operator doesn't know they
got a stale fixture instead of a real LLM response.

With ``WES_REQUIRE_REAL_LLM=1`` set: MockBackend is stripped from the
chain, the loop falls through to "All backends failed", and the failure
is surfaced visibly via :func:`surface_visible_wes_failure`.

These tests verify:

- ``_require_real_llm()`` correctly reads the env var.
- BackendManager's chain construction strips ``mock`` when the gate is
  on, regardless of where it appeared in the fallback chain.
- When the gate is off (default), MockBackend remains in the chain.
- A backend_override of ``"mock"`` is still respected even when the
  gate is on (operator opt-in escape hatch — they explicitly named
  the backend).
"""

from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path
from unittest import mock

_THIS_DIR = Path(__file__).parent
_GAME_DIR = _THIS_DIR.parent.parent.parent.parent
if str(_GAME_DIR) not in sys.path:
    sys.path.insert(0, str(_GAME_DIR))

from world_system.living_world.backends.backend_manager import (  # noqa: E402
    BackendManager,
    ModelBackend,
    _require_real_llm,
    _fixtures_disabled,
)


class _StubBackend(ModelBackend):
    """Test backend with controllable availability + canned responses."""

    def __init__(
        self, name: str, available: bool = True, response: str = "ok",
    ):
        self.name = name
        self._available = available
        self.response = response
        self.generate_calls = 0

    def generate(
        self, system_prompt: str, user_prompt: str,
        temperature: float = 0.4, max_tokens: int = 2000,
    ):
        self.generate_calls += 1
        return self.response, None

    def is_available(self) -> bool:
        return self._available

    def get_info(self):
        return {"name": self.name, "model": "stub", "type": "stub"}


def _make_manager_with_stubs(
    backends: dict, fallback_chain: list, task_routing: dict = None,
) -> BackendManager:
    """Build a BackendManager pre-loaded with stub backends."""
    BackendManager._instance = None
    mgr = BackendManager()
    mgr._backends = backends
    mgr._fallback_chain = fallback_chain
    mgr._task_routing = task_routing or {}
    mgr._defaults = {"temperature": 0.4, "max_tokens": 2000}
    mgr._rate_limits = {}
    mgr._initialized = True
    return mgr


# ── Env-var detection ───────────────────────────────────────────────────


class RequireRealLLMEnvDetectionTestCase(unittest.TestCase):
    def setUp(self) -> None:
        os.environ.pop("WES_REQUIRE_REAL_LLM", None)

    def tearDown(self) -> None:
        os.environ.pop("WES_REQUIRE_REAL_LLM", None)

    def test_unset_returns_false(self) -> None:
        self.assertFalse(_require_real_llm())

    def test_truthy_values_enable(self) -> None:
        for value in ("1", "true", "yes", "on", "TRUE", "Yes"):
            os.environ["WES_REQUIRE_REAL_LLM"] = value
            self.assertTrue(_require_real_llm(), f"failed on {value!r}")

    def test_falsy_values_disable(self) -> None:
        for value in ("0", "false", "no", "off", "", "anything_else"):
            os.environ["WES_REQUIRE_REAL_LLM"] = value
            self.assertFalse(_require_real_llm(), f"failed on {value!r}")

    def test_independent_from_disable_fixtures(self) -> None:
        """The two env vars are independent toggles — one doesn't imply
        the other. Operator can set REQUIRE without DISABLE for tests
        that want to assert "no fallback masquerading"."""
        os.environ["WES_DISABLE_FIXTURES"] = "1"
        self.assertFalse(_require_real_llm())
        os.environ["WES_REQUIRE_REAL_LLM"] = "1"
        self.assertTrue(_require_real_llm())
        self.assertTrue(_fixtures_disabled())
        os.environ.pop("WES_DISABLE_FIXTURES", None)


# ── Chain stripping ─────────────────────────────────────────────────────


class ChainStrippingTestCase(unittest.TestCase):
    def setUp(self) -> None:
        os.environ.pop("WES_REQUIRE_REAL_LLM", None)
        BackendManager._instance = None

    def tearDown(self) -> None:
        os.environ.pop("WES_REQUIRE_REAL_LLM", None)
        BackendManager._instance = None

    def test_mock_stripped_when_gate_on(self) -> None:
        os.environ["WES_REQUIRE_REAL_LLM"] = "1"
        ollama = _StubBackend("ollama", available=False)
        claude = _StubBackend("claude", available=False)
        mockb = _StubBackend("mock", available=True, response="MOCK_TEMPLATE")
        mgr = _make_manager_with_stubs(
            backends={"ollama": ollama, "claude": claude, "mock": mockb},
            fallback_chain=["ollama", "claude", "mock"],
        )
        text, err = mgr.generate(
            task="wes_tool_npcs",
            system_prompt="x",
            user_prompt="y",
        )
        # MockBackend was stripped — the chain failed instead of
        # silently returning a template.
        self.assertEqual(mockb.generate_calls, 0)
        self.assertEqual(text, "")
        self.assertIn("All backends failed", err or "")

    def test_mock_kept_when_gate_off(self) -> None:
        # Default behavior: gate not set → mock is final fallback.
        ollama = _StubBackend("ollama", available=False)
        mockb = _StubBackend("mock", available=True, response="MOCK_TEMPLATE")
        mgr = _make_manager_with_stubs(
            backends={"ollama": ollama, "mock": mockb},
            fallback_chain=["ollama", "mock"],
        )
        text, err = mgr.generate(
            task="wes_tool_npcs",
            system_prompt="x",
            user_prompt="y",
        )
        self.assertEqual(text, "MOCK_TEMPLATE")
        self.assertIsNone(err)
        self.assertEqual(mockb.generate_calls, 1)

    def test_real_backend_used_when_gate_on_and_available(self) -> None:
        os.environ["WES_REQUIRE_REAL_LLM"] = "1"
        ollama = _StubBackend("ollama", available=True, response="REAL")
        mockb = _StubBackend("mock", available=True, response="MOCK")
        mgr = _make_manager_with_stubs(
            backends={"ollama": ollama, "mock": mockb},
            fallback_chain=["ollama", "mock"],
        )
        text, err = mgr.generate(
            task="wes_tool_npcs",
            system_prompt="x", user_prompt="y",
        )
        self.assertEqual(text, "REAL")
        self.assertIsNone(err)
        self.assertEqual(ollama.generate_calls, 1)
        self.assertEqual(mockb.generate_calls, 0)

    def test_explicit_mock_override_respected(self) -> None:
        """Operator can still pass ``backend_override="mock"`` even with
        the gate on — they're naming the backend explicitly, the gate
        only blocks IMPLICIT fallback to mock."""
        os.environ["WES_REQUIRE_REAL_LLM"] = "1"
        mockb = _StubBackend("mock", available=True, response="EXPLICIT_MOCK")
        mgr = _make_manager_with_stubs(
            backends={"mock": mockb},
            fallback_chain=["mock"],
        )
        text, err = mgr.generate(
            task="wes_tool_npcs",
            system_prompt="x", user_prompt="y",
            backend_override="mock",
        )
        self.assertEqual(text, "EXPLICIT_MOCK")
        self.assertIsNone(err)
        self.assertEqual(mockb.generate_calls, 1)

    def test_chain_with_only_mock_falls_through_when_gate_on(self) -> None:
        """Edge case: the entire chain after stripping is empty. The
        loop's "All backends failed" path must still produce a clear
        error — no IndexError or silent empty success."""
        os.environ["WES_REQUIRE_REAL_LLM"] = "1"
        mockb = _StubBackend("mock", available=True, response="x")
        mgr = _make_manager_with_stubs(
            backends={"mock": mockb},
            fallback_chain=["mock"],
        )
        text, err = mgr.generate(
            task="wes_tool_npcs",
            system_prompt="x", user_prompt="y",
        )
        self.assertEqual(text, "")
        self.assertIn("All backends failed", err or "")
        self.assertEqual(mockb.generate_calls, 0)


if __name__ == "__main__":
    unittest.main()

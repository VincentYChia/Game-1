"""2026-07-10 real-LLM certification — Claude request-parameter contract.

claude-haiku-4-5 REJECTS requests that set temperature and top_p
together (400 invalid_request_error). Both API clients sent both on
every call, so every game-path Claude call had been broken since the
2026-06-15 model swap — fixtures/MockBackend masked it. These tests pin
the fix: temperature only; top_p only when temperature is unset.
"""
import os
import sys
import unittest
from unittest.mock import MagicMock

_MODULAR_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _MODULAR_ROOT not in sys.path:
    sys.path.insert(0, _MODULAR_ROOT)


def _capture_create(captured):
    client = MagicMock()

    def create(**kwargs):
        captured.update(kwargs)
        resp = MagicMock()
        resp.content = [MagicMock(text="ok")]
        return resp

    client.messages.create = create
    return client


class TestBackendManagerClaude(unittest.TestCase):
    def _backend(self, captured):
        from world_system.living_world.backends.backend_manager import (
            ClaudeBackend,
        )
        b = ClaudeBackend.__new__(ClaudeBackend)
        b.model = "claude-haiku-4-5"
        b.max_tokens_default = 2000
        b.top_p = 0.95
        b._client = _capture_create(captured)
        b._api_key = "test"
        return b

    def test_temperature_set_omits_top_p(self):
        captured = {}
        text, err = self._backend(captured).generate("sys", "user",
                                                     temperature=0.4)
        self.assertIsNone(err)
        self.assertIn("temperature", captured)
        self.assertNotIn("top_p", captured,
                         "Haiku 4.5 400s when both are sent")

    def test_no_temperature_falls_back_to_top_p(self):
        captured = {}
        self._backend(captured).generate("sys", "user", temperature=None)
        self.assertNotIn("temperature", captured)
        self.assertEqual(captured.get("top_p"), 0.95)


class TestItemGeneratorClient(unittest.TestCase):
    def test_temperature_set_omits_top_p(self):
        from systems.llm_item_generator import AnthropicBackend, LLMConfig
        captured = {}
        b = AnthropicBackend.__new__(AnthropicBackend)
        b.api_key = "test"
        b._client = _capture_create(captured)
        text, err = b.generate("sys", "user", LLMConfig(api_key="test"))
        self.assertIsNone(err)
        self.assertIn("temperature", captured)
        self.assertNotIn("top_p", captured,
                         "Haiku 4.5 400s when both are sent")


if __name__ == "__main__":
    unittest.main()

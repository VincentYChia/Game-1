"""2026-07 LLM-pipeline audit — WMS response parser conformance.

The old parser failed against its OWN prompt contract: the prompt
instructs ``significance:`` tags but the parser matched ``severity:``
only, so a fully compliant reply never set severity; the fallback
substring-searched the narrative so fantasy prose ("a critical blow")
silently inflated severity; fenced/preambled JSON fell through raw as
garbage narratives; invented tag categories entered the load-bearing
tag index unchecked. These tests pin the rewritten contract.
"""
import os
import sys
import unittest

_MODULAR_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _MODULAR_ROOT not in sys.path:
    sys.path.insert(0, _MODULAR_ROOT)

from world_system.world_memory.wms_ai import WmsAI, _extract_json_object  # noqa: E402


class FakeBackend:
    def __init__(self, reply=""):
        self.reply = reply

    def generate(self, **_kwargs):
        return (self.reply, None)


def _parse(reply, layer=2):
    ai = WmsAI.__new__(WmsAI)
    ai._backend = FakeBackend(reply)
    return ai._call_llm("sys", "user", task="wms_layer2",
                        temperature=0.3, max_tokens=300, layer=layer)


class TestJsonExtraction(unittest.TestCase):
    def test_plain_json(self):
        self.assertEqual(_extract_json_object('{"a": 1}'), {"a": 1})

    def test_fenced_json(self):
        self.assertEqual(
            _extract_json_object('```json\n{"a": 1}\n```'), {"a": 1})

    def test_prose_preamble(self):
        self.assertEqual(
            _extract_json_object('Here you go:\n{"a": 1}'), {"a": 1})

    def test_garbage_returns_none(self):
        self.assertIsNone(_extract_json_object("just prose, no json"))
        self.assertIsNone(_extract_json_object('{"truncated": "mid'))


class TestSeverityContract(unittest.TestCase):
    def test_significance_tag_sets_severity(self):
        """The prompt asks for significance: tags — they MUST work."""
        r = _parse('{"narrative": "Wolves culled.", '
                   '"tags": ["significance:significant", "domain:combat"]}')
        self.assertEqual(r.severity, "significant")
        self.assertEqual(r.tags, ["domain:combat"])  # consumed, not forwarded

    def test_severity_tag_also_accepted(self):
        r = _parse('{"narrative": "Quiet day.", "tags": ["severity:major"]}')
        self.assertEqual(r.severity, "major")

    def test_prose_mentioning_critical_does_not_inflate(self):
        """Fantasy prose contains 'critical'/'major' innocently — the old
        substring fallback promoted it to severity. Must stay minor."""
        r = _parse('{"narrative": "The warrior landed a critical blow, '
                   'a major turning point.", "tags": []}')
        self.assertEqual(r.severity, "minor")

    def test_invalid_severity_vocabulary_ignored(self):
        r = _parse('{"narrative": "X.", "tags": ["severity:catastrophic"]}')
        self.assertEqual(r.severity, "minor")


class TestRealOutputShapes(unittest.TestCase):
    def test_fenced_reply_parses_clean(self):
        r = _parse('```json\n{"narrative": "Player slew 25 wolves.", '
                   '"tags": ["significance:major"]}\n```')
        self.assertTrue(r.success)
        self.assertEqual(r.text, "Player slew 25 wolves.")
        self.assertEqual(r.severity, "major")

    def test_preambled_reply_parses_clean(self):
        r = _parse('Here is the narration:\n{"narrative": "Wolves fell.", '
                   '"tags": ["significance:moderate"]}')
        self.assertEqual(r.text, "Wolves fell.")
        self.assertEqual(r.severity, "moderate")

    def test_empty_reply_is_failure(self):
        """Empty must fail so callers use the template fallback."""
        self.assertFalse(_parse('').success)

    def test_truncated_json_is_failure(self):
        self.assertFalse(_parse('{"narrative": "The wolves of').success)


class TestTagAllowList(unittest.TestCase):
    def test_invented_categories_dropped(self):
        """Tag system is load-bearing — LLM-invented categories must not
        enter the retrieval index."""
        r = _parse('{"narrative": "Odd.", "tags": '
                   '["vibe:spooky", "notacategory:x", "domain:combat"]}')
        self.assertEqual(r.tags, ["domain:combat"])

    def test_no_layer_skips_filter(self):
        r = _parse('{"narrative": "Odd.", "tags": ["vibe:spooky"]}',
                   layer=None)
        self.assertEqual(r.tags, ["vibe:spooky"])


if __name__ == "__main__":
    unittest.main()

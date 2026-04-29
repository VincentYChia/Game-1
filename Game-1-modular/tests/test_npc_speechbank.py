"""Tests for the NL1 NPC dialogue speechbank runtime hookup.

Before this work, ``NPC.get_next_dialogue()`` only walked the legacy
flattened ``dialogue_lines`` list — speechbank fields (``greeting``,
``idle_barks``, ``quest_offer``, ``quest_complete``, ``farewell``) were
captured at NPC generation but never consulted at runtime.

These tests assert the new flow:

- First call after :meth:`reset_dialogue_state` returns a greeting,
  cycling through ``speechbank["greeting"]``.
- Subsequent calls cycle ``speechbank["idle_barks"]`` independently.
- Greeting / idle / farewell cycle indices each climb monotonically so
  re-greetings rotate through the bank rather than repeating verbatim.
- Quest accept / turn-in helpers return the per-NPC strings or
  ``None`` (so callers can fall through cleanly).
- NPCs without a speechbank fall back to the legacy ``dialogue_lines``
  cycle — backwards compatibility.
"""

from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path

_THIS_DIR = Path(__file__).parent
_PROJECT_ROOT = _THIS_DIR.parent
sys.path.insert(0, str(_PROJECT_ROOT))
os.chdir(_PROJECT_ROOT)

from data.models.npcs import NPCDefinition  # noqa: E402
from data.models.world import Position  # noqa: E402
from systems.npc_system import NPC  # noqa: E402


# ── Helpers ──────────────────────────────────────────────────────────

def _make_npc(
    *,
    speechbank: dict = None,
    dialogue_lines: list = None,
    npc_id: str = "test_npc",
) -> NPC:
    """Build an NPC with a synthetic NPCDefinition."""
    npc_def = NPCDefinition(
        npc_id=npc_id,
        name="Test NPC",
        title="Tester",
        narrative="",
        personality={},
        locality={},
        faction={},
        affinity_seeds={},
        services={},
        unlock_conditions={},
        speechbank=speechbank or {},
        quests=[],
        position=Position(0, 0, 0),
        sprite_color=(200, 200, 200),
        interaction_radius=3.0,
        tags=[],
        dialogue_lines=dialogue_lines or [],
    )
    return NPC(npc_def)


# ── Speechbank-driven dialogue ────────────────────────────────────────

class FreshGreetingTestCase(unittest.TestCase):
    """First call after reset returns a greeting; subsequent calls cycle idles."""

    def test_first_call_returns_greeting(self) -> None:
        npc = _make_npc(speechbank={
            "greeting": ["Hello!", "Hi there.", "Greetings."],
            "idle_barks": ["The sky is blue.", "It's a fine day."],
        })
        line = npc.get_next_dialogue()
        self.assertEqual(line, "Hello!")

    def test_second_call_returns_idle_not_greeting(self) -> None:
        npc = _make_npc(speechbank={
            "greeting": ["Hello!", "Hi there."],
            "idle_barks": ["The sky is blue.", "It's a fine day."],
        })
        npc.get_next_dialogue()  # consumes greeting
        line = npc.get_next_dialogue()
        self.assertEqual(line, "The sky is blue.")

    def test_idle_cycles(self) -> None:
        npc = _make_npc(speechbank={
            "greeting": ["Hi"],
            "idle_barks": ["A", "B", "C"],
        })
        npc.get_next_dialogue()  # greeting
        self.assertEqual(npc.get_next_dialogue(), "A")
        self.assertEqual(npc.get_next_dialogue(), "B")
        self.assertEqual(npc.get_next_dialogue(), "C")
        self.assertEqual(npc.get_next_dialogue(), "A")  # wraps

    def test_reset_re_greets(self) -> None:
        npc = _make_npc(speechbank={
            "greeting": ["Hello!", "Hi there."],
            "idle_barks": ["bark"],
        })
        npc.get_next_dialogue()  # consumes Hello!
        npc.get_next_dialogue()  # idle bark
        npc.reset_dialogue_state()
        # Cycle index advances → next greeting is the second one.
        line = npc.get_next_dialogue()
        self.assertEqual(line, "Hi there.")

    def test_repeated_resets_cycle_through_greetings(self) -> None:
        """Cycle indices keep climbing across resets so the player
        rotates through the full greeting bank, not the same first
        line every time."""
        npc = _make_npc(speechbank={
            "greeting": ["A", "B", "C"],
        })
        seen = []
        for _ in range(3):
            seen.append(npc.get_next_dialogue())
            npc.reset_dialogue_state()
        self.assertEqual(seen, ["A", "B", "C"])

    def test_only_idles_no_greeting_falls_through(self) -> None:
        npc = _make_npc(speechbank={
            "idle_barks": ["just an idle"],
        })
        # No greeting list → first call uses idle_bark.
        self.assertEqual(npc.get_next_dialogue(), "just an idle")


# ── Quest accept / turn-in helpers ────────────────────────────────────

class QuestSpeechbankHelpersTestCase(unittest.TestCase):
    def test_quest_offer_returns_string(self) -> None:
        npc = _make_npc(speechbank={
            "quest_offer": "Right, off you go!",
        })
        self.assertEqual(npc.get_quest_offer_line(), "Right, off you go!")

    def test_quest_offer_returns_none_when_missing(self) -> None:
        npc = _make_npc(speechbank={"greeting": ["Hi"]})
        self.assertIsNone(npc.get_quest_offer_line())

    def test_quest_offer_returns_none_for_empty_string(self) -> None:
        npc = _make_npc(speechbank={"quest_offer": "   "})
        self.assertIsNone(npc.get_quest_offer_line())

    def test_quest_complete_returns_string(self) -> None:
        npc = _make_npc(speechbank={
            "quest_complete": "Excellent work!",
        })
        self.assertEqual(npc.get_quest_complete_line(), "Excellent work!")

    def test_quest_complete_returns_none_when_missing(self) -> None:
        npc = _make_npc(speechbank={})
        self.assertIsNone(npc.get_quest_complete_line())

    def test_quest_complete_returns_none_for_non_string(self) -> None:
        npc = _make_npc(speechbank={"quest_complete": ["a", "b"]})  # wrong type
        self.assertIsNone(npc.get_quest_complete_line())


# ── Farewell ──────────────────────────────────────────────────────────

class FarewellTestCase(unittest.TestCase):
    def test_farewell_cycles(self) -> None:
        npc = _make_npc(speechbank={
            "farewell": ["Goodbye.", "Walk well."],
        })
        self.assertEqual(npc.get_farewell_line(), "Goodbye.")
        self.assertEqual(npc.get_farewell_line(), "Walk well.")
        self.assertEqual(npc.get_farewell_line(), "Goodbye.")

    def test_farewell_none_when_missing(self) -> None:
        npc = _make_npc(speechbank={"greeting": ["Hi"]})
        self.assertIsNone(npc.get_farewell_line())


# ── Legacy fallback ───────────────────────────────────────────────────

class LegacyDialogueLinesTestCase(unittest.TestCase):
    """NPCs without a structured speechbank still cycle dialogue_lines."""

    def test_no_speechbank_uses_dialogue_lines(self) -> None:
        npc = _make_npc(
            speechbank={},
            dialogue_lines=["Line A", "Line B", "Line C"],
        )
        self.assertEqual(npc.get_next_dialogue(), "Line A")
        self.assertEqual(npc.get_next_dialogue(), "Line B")
        self.assertEqual(npc.get_next_dialogue(), "Line C")
        self.assertEqual(npc.get_next_dialogue(), "Line A")

    def test_empty_speechbank_dict_uses_dialogue_lines(self) -> None:
        npc = _make_npc(
            speechbank={"greeting": [], "idle_barks": []},
            dialogue_lines=["Fallback"],
        )
        self.assertEqual(npc.get_next_dialogue(), "Fallback")

    def test_no_speechbank_no_dialogue_lines_returns_ellipsis(self) -> None:
        npc = _make_npc(speechbank={}, dialogue_lines=[])
        self.assertEqual(npc.get_next_dialogue(), "...")

    def test_malformed_speechbank_does_not_crash(self) -> None:
        # speechbank where greeting is a string, not a list — should
        # not raise; should fall through cleanly.
        npc = _make_npc(
            speechbank={"greeting": "not a list", "idle_barks": None},
            dialogue_lines=["Fallback"],
        )
        self.assertEqual(npc.get_next_dialogue(), "Fallback")


# ── Real loaded NPC integration ───────────────────────────────────────

class RealLoadedNPCTestCase(unittest.TestCase):
    """Smoke test against a real NPC loaded from progression/npcs-3.JSON.

    Catches the case where the v3 schema or _build_npc_from_v3 silently
    drops the speechbank — the field is on NPCDefinition but populated
    from {} which makes every helper return None.
    """

    @classmethod
    def setUpClass(cls) -> None:
        from data.databases.npc_db import NPCDatabase
        cls.db = NPCDatabase.get_instance()
        cls.db.load_from_files()

    def test_at_least_one_npc_has_structured_speechbank(self) -> None:
        # Designer-authored NPCs must have a speechbank populated for
        # the new dialogue path to actually trigger in-game.
        with_speechbank = [
            (nid, npc) for nid, npc in self.db.npcs.items()
            if isinstance(npc.speechbank, dict)
            and isinstance(npc.speechbank.get("greeting"), list)
            and npc.speechbank["greeting"]
        ]
        self.assertGreater(
            len(with_speechbank), 0,
            "Expected at least one NPC in npcs-3.JSON to ship a "
            "structured speechbank with a non-empty greeting list",
        )

    def test_loaded_npc_first_dialogue_is_greeting(self) -> None:
        for nid, npc_def in self.db.npcs.items():
            sb = npc_def.speechbank or {}
            greetings = sb.get("greeting") if isinstance(sb.get("greeting"), list) else []
            if greetings:
                npc = NPC(npc_def)
                line = npc.get_next_dialogue()
                self.assertEqual(line, greetings[0])
                return
        self.skipTest("no NPC with a non-empty greeting list to test")


if __name__ == "__main__":
    unittest.main()

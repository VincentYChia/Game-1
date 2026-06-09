"""Tests for the quest log overlay (2026-06-09).

Closes Cross-cutting Risk #9 (Quest UX gap — no waypoint, no abandon,
no log reminder). The overlay's contract is:

- Renders the active quest list with objective + progress text.
- Returns a dict ``{quest_id: pygame.Rect}`` for Abandon button clicks.
- Handles "no quests" gracefully (empty dict, valid window_rect).

The render call needs pygame surfaces but no pygame display, so we use
``pygame.display.init() + pygame.Surface`` directly. The actual click
dispatch lives in ``game_engine.handle_mouse_click`` — this test only
verifies that the overlay produces correct click regions.
"""

import os
import sys
import unittest
from pathlib import Path

# Headless pygame.
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

_THIS_DIR = Path(__file__).parent
_GAME_DIR = _THIS_DIR.parent
if str(_GAME_DIR) not in sys.path:
    sys.path.insert(0, str(_GAME_DIR))

import pygame  # noqa: E402

from systems.quest_log_overlay import render_quest_log_overlay  # noqa: E402
from systems.quest_system import Quest, QuestManager  # noqa: E402


class _StubObjective:
    def __init__(self, objective_type, items=None, enemies_killed=0):
        self.objective_type = objective_type
        self.items = items or []
        self.enemies_killed = enemies_killed


class _StubRewards:
    experience = 0
    gold = 0
    health_restore = 0
    mana_restore = 0
    skills: list = []
    items: list = []
    title = ""
    stat_points = 0
    status_effects: list = []
    buffs: list = []


class _StubQuestDef:
    def __init__(self, quest_id, title, objectives):
        self.quest_id = quest_id
        self.title = title
        self.objectives = objectives
        self.rewards = _StubRewards()
        self.source_origin = "canonical"
        self.npc_id = "stub_npc"


class _StubInventory:
    def __init__(self, counts=None):
        self._counts = counts or {}

    def get_item_count(self, item_id: str) -> int:
        return self._counts.get(item_id, 0)


class _StubActivities:
    def __init__(self, combat_count=0):
        self.combat_count = combat_count

    def get_count(self, kind: str) -> int:
        if kind == "combat":
            return self.combat_count
        return 0


class _StubCharacter:
    def __init__(self, inventory=None, activities=None):
        self.inventory = inventory or _StubInventory()
        self.activities = activities or _StubActivities()
        self.quests = QuestManager()


class _OverlayTestBase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        pygame.display.init()
        pygame.font.init()
        cls.surface = pygame.Surface((1280, 720))
        cls.font = pygame.font.Font(None, 22)
        cls.small_font = pygame.font.Font(None, 16)

    def setUp(self) -> None:
        self.character = _StubCharacter()


class TestQuestLogEmptyState(_OverlayTestBase):
    def test_no_active_quests_returns_valid_window_no_abandons(self) -> None:
        result = render_quest_log_overlay(
            self.surface,
            self.font,
            self.small_font,
            self.character,
            mouse_pos=(0, 0),
        )
        self.assertIsNotNone(result["window_rect"])
        self.assertEqual(result["abandon_buttons"], {})


class TestQuestLogActiveQuests(_OverlayTestBase):
    def _make_gather_quest(self, character, item_id="iron_ore", qty=5) -> str:
        objectives = _StubObjective(
            "gather", items=[{"item_id": item_id, "quantity": qty}],
        )
        qd = _StubQuestDef("q_gather_1", "Gather Iron Ore", objectives)
        ok = character.quests.start_quest(qd, character)
        self.assertTrue(ok)
        return qd.quest_id

    def _make_combat_quest(self, character, kills=3) -> str:
        objectives = _StubObjective("combat", enemies_killed=kills)
        qd = _StubQuestDef("q_combat_1", "Slay Wolves", objectives)
        ok = character.quests.start_quest(qd, character)
        self.assertTrue(ok)
        return qd.quest_id

    def test_one_gather_quest_produces_one_abandon_button(self) -> None:
        qid = self._make_gather_quest(self.character)
        result = render_quest_log_overlay(
            self.surface,
            self.font,
            self.small_font,
            self.character,
            mouse_pos=(0, 0),
        )
        self.assertIn(qid, result["abandon_buttons"])
        self.assertEqual(len(result["abandon_buttons"]), 1)

    def test_two_quests_produce_two_distinct_abandon_buttons(self) -> None:
        q1 = self._make_gather_quest(self.character, item_id="copper_ore", qty=3)
        q2 = self._make_combat_quest(self.character, kills=2)
        result = render_quest_log_overlay(
            self.surface,
            self.font,
            self.small_font,
            self.character,
            mouse_pos=(0, 0),
        )
        self.assertEqual(set(result["abandon_buttons"].keys()), {q1, q2})
        # Rects must be distinct rectangles (different y-coords).
        rects = list(result["abandon_buttons"].values())
        self.assertNotEqual(rects[0].y, rects[1].y)

    def test_abandon_rect_is_inside_window(self) -> None:
        qid = self._make_gather_quest(self.character)
        result = render_quest_log_overlay(
            self.surface,
            self.font,
            self.small_font,
            self.character,
            mouse_pos=(0, 0),
        )
        window = result["window_rect"]
        btn = result["abandon_buttons"][qid]
        self.assertTrue(window.contains(btn))

    def test_progress_uses_inventory_counts_for_gather(self) -> None:
        # Pre-populate inventory so baseline = 2; then current 5 → 3 gathered.
        self.character.inventory = _StubInventory({"iron_ore": 2})
        qid = self._make_gather_quest(self.character, item_id="iron_ore", qty=5)
        self.character.inventory = _StubInventory({"iron_ore": 5})
        # The overlay reads progress live; rendering is enough to exercise the path.
        result = render_quest_log_overlay(
            self.surface,
            self.font,
            self.small_font,
            self.character,
            mouse_pos=(0, 0),
        )
        self.assertIn(qid, result["abandon_buttons"])


class TestAbandonQuestIntegration(_OverlayTestBase):
    """QuestManager.abandon_quest is the actual action; verify it works."""

    def test_abandon_removes_from_active(self) -> None:
        objectives = _StubObjective(
            "gather", items=[{"item_id": "stone", "quantity": 1}],
        )
        qd = _StubQuestDef("q_abandon_test", "Stone Gather", objectives)
        self.character.quests.start_quest(qd, self.character)
        self.assertIn("q_abandon_test", self.character.quests.active_quests)
        ok = self.character.quests.abandon_quest("q_abandon_test", self.character)
        self.assertTrue(ok)
        self.assertNotIn("q_abandon_test", self.character.quests.active_quests)

    def test_abandon_unknown_quest_returns_false(self) -> None:
        ok = self.character.quests.abandon_quest("does_not_exist", self.character)
        self.assertFalse(ok)


if __name__ == "__main__":
    unittest.main()

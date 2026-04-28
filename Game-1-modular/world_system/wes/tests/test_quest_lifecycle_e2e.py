"""End-to-end test: QuestManager.start_quest → pregeneration →
QuestManager.complete_quest → adaptation → grant_rewards.

Verifies:
- Canonical (tutorial) quests untouched: no LLM calls, hand-tuned
  rewards granted verbatim.
- Generated quests: pregeneration on start, adaptation on complete,
  effective_rewards reflects the adapted bundle.
- Failure of pregeneration leaves design rewards (typically empty
  for generated quests).
- Failure of adaptation leaves the pre-generated bundle intact.
"""

from __future__ import annotations

import os
import sys
import unittest
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

_this_dir = os.path.dirname(os.path.abspath(__file__))
_game_dir = os.path.dirname(os.path.dirname(os.path.dirname(_this_dir)))
if _game_dir not in sys.path:
    sys.path.insert(0, _game_dir)

from data.models.quests import (  # noqa: E402
    QuestDefinition,
    QuestObjective,
    QuestRewards,
)
from systems.quest_system import QuestManager  # noqa: E402
from world_system.wes.quest_reward_adapter import (  # noqa: E402
    QuestRewardAdapter,
    TASK_ADAPT,
    TASK_PREGEN,
)


# ── Lightweight character double ──────────────────────────────────────


@dataclass
class _ItemStack:
    item_id: str
    quantity: int


class _Inventory:
    """Test-friendly inventory mirroring the real Inventory's surface.

    Quest completion uses ``get_item_count`` (baseline snapshot) and
    iterates ``slots`` to consume items at turn-in, so the fake
    populates both. ``gain()`` is a test helper that adds an
    :class:`_ItemStack` to slots.
    """

    def __init__(self):
        self.slots: List[Optional[_ItemStack]] = []

    def get_item_count(self, item_id: str) -> int:
        total = 0
        for s in self.slots:
            if s and s.item_id == item_id:
                total += s.quantity
        return total

    def add_item(self, item_id: str, qty: int) -> bool:
        self.slots.append(_ItemStack(item_id=item_id, quantity=int(qty)))
        return True

    def gain(self, item_id: str, qty: int) -> None:
        """Test helper — drop an item stack into the inventory."""
        self.slots.append(_ItemStack(item_id=item_id, quantity=int(qty)))


class _Activities:
    def __init__(self):
        self._counts: Dict[str, int] = {}

    def get_count(self, key: str) -> int:
        return self._counts.get(key, 0)

    def bump(self, key: str, n: int) -> None:
        self._counts[key] = self._counts.get(key, 0) + n


class _Leveling:
    def __init__(self, level: int = 5, exp: int = 0):
        self.level = level
        self.current_exp = exp

    def add_exp(self, amount: int) -> bool:
        self.current_exp += int(amount)
        return False


class _Skills:
    def __init__(self):
        self.learned: List[str] = []

    def learn_skill(self, sid: str, character=None, skip_checks: bool = False) -> bool:
        self.learned.append(sid)
        return True


class _Titles:
    def __init__(self):
        self.awarded: List[str] = []

    def award_title(self, title_def) -> bool:
        self.awarded.append(getattr(title_def, "title_id",
                                     getattr(title_def, "id", "unknown")))
        return True


@dataclass
class _Stats:
    strength: int = 5
    defense: int = 5
    vitality: int = 5
    luck: int = 5
    agility: int = 5
    intelligence: int = 5


@dataclass
class _Character:
    name: str = "Hero"
    health: int = 100
    max_health: int = 100
    mana: int = 50
    max_mana: int = 50
    gold: int = 0
    leveling: _Leveling = field(default_factory=_Leveling)
    inventory: _Inventory = field(default_factory=_Inventory)
    activities: _Activities = field(default_factory=_Activities)
    skills: _Skills = field(default_factory=_Skills)
    titles: _Titles = field(default_factory=_Titles)
    stats: _Stats = field(default_factory=_Stats)


class _ScriptedBackend:
    """Returns scripted responses per task. Records calls for assertions."""

    def __init__(self, scripted: Dict[str, Tuple[str, Optional[str]]]):
        self.scripted = dict(scripted)
        self.calls: List[Dict[str, Any]] = []

    def generate(self, *, task: str, system_prompt: str, user_prompt: str,
                 **_kwargs) -> Tuple[str, Optional[str]]:
        self.calls.append({"task": task})
        if task in self.scripted:
            return self.scripted[task]
        return ("", "no_scripted_response")


# ── Quest factories ───────────────────────────────────────────────────


def _generated_kill_quest() -> QuestDefinition:
    return QuestDefinition(
        quest_id="moors_hunt",
        title="Moors Hunt",
        description="Hunt three moors raiders.",
        npc_id="moors_captain",
        objectives=QuestObjective(
            objective_type="combat",
            enemies_killed=3,
        ),
        rewards=QuestRewards(),  # empty — LLM materializes
        rewards_prose={
            "experience_hint": "moderate",
            "tier_hint": 2,
            "title_hint": "moors_reaver",
        },
        tier=2,
        source_origin="generated",
    )


def _canonical_gather_quest() -> QuestDefinition:
    return QuestDefinition(
        quest_id="tutorial_oak",
        title="First Steps",
        description="Gather 5 oak logs.",
        npc_id="elder_sage",
        objectives=QuestObjective(
            objective_type="gather",
            items=[{"item_id": "oak_log", "quantity": 5}],
        ),
        rewards=QuestRewards(experience=100, gold=20, items=[
            {"item_id": "minor_health_potion", "quantity": 2}
        ]),
        source_origin="canonical",
    )


# ── Tests ─────────────────────────────────────────────────────────────


class TestCanonicalQuestUnchanged(unittest.TestCase):
    """Tutorial quests must behave EXACTLY as before — no LLM calls,
    hand-tuned rewards granted verbatim."""

    def setUp(self) -> None:
        QuestRewardAdapter.reset()
        self.backend = _ScriptedBackend({})  # No fixtures — any LLM call would fail
        # Inject backend into the adapter singleton
        adapter = QuestRewardAdapter.get_instance()
        adapter._backend = self.backend  # type: ignore[attr-defined]

    def tearDown(self) -> None:
        QuestRewardAdapter.reset()

    def test_no_llm_call_on_start_or_complete(self) -> None:
        mgr = QuestManager()
        char = _Character()
        quest_def = _canonical_gather_quest()

        ok = mgr.start_quest(quest_def, char)
        self.assertTrue(ok)
        # Simulate player gathering 5 oak logs after quest start.
        char.inventory.gain("oak_log", 5)
        success, msgs = mgr.complete_quest("tutorial_oak", char)
        self.assertTrue(success, f"messages: {msgs}")
        # Zero LLM calls.
        self.assertEqual(self.backend.calls, [])

    def test_canonical_rewards_granted_verbatim(self) -> None:
        mgr = QuestManager()
        char = _Character()
        mgr.start_quest(_canonical_gather_quest(), char)
        char.inventory.gain("oak_log", 5)
        success, msgs = mgr.complete_quest("tutorial_oak", char)
        self.assertTrue(success, f"messages: {msgs}")
        # 100 XP and 20 gold granted exactly per the canonical reward.
        self.assertEqual(char.leveling.current_exp, 100)
        self.assertEqual(char.gold, 20)


class TestGeneratedQuestPregeneration(unittest.TestCase):
    """Generated quests trigger pre-gen at start_quest."""

    def setUp(self) -> None:
        QuestRewardAdapter.reset()

    def tearDown(self) -> None:
        QuestRewardAdapter.reset()

    def _wire(self, scripted: Dict[str, Tuple[str, Optional[str]]]) -> _ScriptedBackend:
        backend = _ScriptedBackend(scripted)
        adapter = QuestRewardAdapter.get_instance()
        adapter._backend = backend
        return backend

    def test_pregeneration_fires_on_start(self) -> None:
        backend = self._wire({
            TASK_PREGEN: (
                '{"rewards": {"experience": 280, "gold": 65, "title": "moors_reaver"}, '
                '"completion_dialogue": ["You came back."]}',
                None,
            ),
        })
        mgr = QuestManager()
        char = _Character()
        ok = mgr.start_quest(_generated_kill_quest(), char)
        self.assertTrue(ok)

        # The pregen task was called.
        tasks_called = [c["task"] for c in backend.calls]
        self.assertIn(TASK_PREGEN, tasks_called)

        # Quest now carries pre-generated rewards.
        quest = mgr.active_quests["moors_hunt"]
        self.assertIsNotNone(quest.pre_generated_rewards)
        self.assertEqual(quest.pre_generated_rewards.experience, 280)
        self.assertEqual(quest.effective_rewards.experience, 280)
        self.assertEqual(len(quest.pre_generated_completion_dialogue), 1)

    def test_pregeneration_failure_keeps_design_rewards(self) -> None:
        backend = self._wire({
            TASK_PREGEN: ("", "ollama_offline"),
        })
        mgr = QuestManager()
        char = _Character()
        ok = mgr.start_quest(_generated_kill_quest(), char)
        self.assertTrue(ok)

        quest = mgr.active_quests["moors_hunt"]
        self.assertIsNone(quest.pre_generated_rewards)
        # effective_rewards points at the (empty) design rewards.
        self.assertEqual(quest.effective_rewards.experience, 0)
        self.assertEqual(quest.effective_rewards.gold, 0)


class TestGeneratedQuestAdaptation(unittest.TestCase):
    """Generated quests trigger adapt at complete_quest."""

    def setUp(self) -> None:
        QuestRewardAdapter.reset()

    def tearDown(self) -> None:
        QuestRewardAdapter.reset()

    def _wire(self, scripted: Dict[str, Tuple[str, Optional[str]]]) -> _ScriptedBackend:
        backend = _ScriptedBackend(scripted)
        adapter = QuestRewardAdapter.get_instance()
        adapter._backend = backend
        return backend

    def _drive_quest_to_complete(self, mgr: QuestManager, char: _Character) -> None:
        # Combat quest with enemies_killed=3. Bump activities.
        char.activities.bump("combat", 3)

    def test_adaptation_overrides_pregenerated(self) -> None:
        backend = self._wire({
            TASK_PREGEN: (
                '{"rewards": {"experience": 280, "gold": 65, "title": "moors_reaver"}, '
                '"completion_dialogue": ["x"]}',
                None,
            ),
            TASK_ADAPT: (
                '{"rewards": {"experience": 336, "gold": 78, "title": "moors_reaver"}}',
                None,
            ),
        })
        mgr = QuestManager()
        char = _Character()
        mgr.start_quest(_generated_kill_quest(), char)
        self._drive_quest_to_complete(mgr, char)

        # Snapshot the pre-gen state we can compare against.
        quest = mgr.active_quests["moors_hunt"]
        self.assertEqual(quest.pre_generated_rewards.experience, 280)

        success, _msgs = mgr.complete_quest("moors_hunt", char)
        self.assertTrue(success)

        # 336 xp granted (the adapted value), not 280 or 0.
        self.assertEqual(char.leveling.current_exp, 336)
        self.assertEqual(char.gold, 78)
        # Both LLM calls happened.
        tasks_called = [c["task"] for c in backend.calls]
        self.assertIn(TASK_PREGEN, tasks_called)
        self.assertIn(TASK_ADAPT, tasks_called)

    def test_adapt_failure_falls_back_to_pregenerated(self) -> None:
        backend = self._wire({
            TASK_PREGEN: (
                '{"rewards": {"experience": 280, "gold": 65}, '
                '"completion_dialogue": []}',
                None,
            ),
            TASK_ADAPT: ("garbage payload", None),  # Parse will fail.
        })
        mgr = QuestManager()
        char = _Character()
        mgr.start_quest(_generated_kill_quest(), char)
        self._drive_quest_to_complete(mgr, char)
        success, _ = mgr.complete_quest("moors_hunt", char)
        self.assertTrue(success)

        # Player gets the pre-generated reward (the floor) even
        # though adapt failed. No "click and wait + missed reward"
        # mishap.
        self.assertEqual(char.leveling.current_exp, 280)
        self.assertEqual(char.gold, 65)

    def test_pregen_fail_then_adapt_skipped_then_zero_reward(self) -> None:
        """When both LLM calls fail, the player gets the design
        rewards (which for generated quests are typically empty).
        Documenting this as the worst-case path so we know the
        floor."""
        self._wire({
            TASK_PREGEN: ("", "fail"),
            TASK_ADAPT: ("", "fail"),
        })
        mgr = QuestManager()
        char = _Character()
        mgr.start_quest(_generated_kill_quest(), char)
        self._drive_quest_to_complete(mgr, char)
        success, _ = mgr.complete_quest("moors_hunt", char)
        self.assertTrue(success)
        # Design rewards were empty -> player gets 0 xp/gold. This
        # is the worst-case but acceptable: at least the quest
        # completes cleanly.
        self.assertEqual(char.leveling.current_exp, 0)
        self.assertEqual(char.gold, 0)


if __name__ == "__main__":
    unittest.main()

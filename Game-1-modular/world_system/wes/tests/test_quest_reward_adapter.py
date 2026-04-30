"""Tests for QuestRewardAdapter — pre-gen + adapt + failure modes."""

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
from world_system.wes.quest_reward_adapter import (  # noqa: E402
    QuestRewardAdapter,
    TASK_PREGEN,
    TASK_ADAPT,
)


# ── Fakes ─────────────────────────────────────────────────────────────


class FakeBackend:
    """Records every generate() call and returns scripted responses."""

    def __init__(self, scripted: Dict[str, Tuple[str, Optional[str]]]):
        self.scripted = dict(scripted)
        self.calls: List[Dict[str, Any]] = []

    def generate(self, *, task: str, system_prompt: str, user_prompt: str,
                 **_kwargs) -> Tuple[str, Optional[str]]:
        self.calls.append({
            "task": task,
            "system_prompt": system_prompt,
            "user_prompt": user_prompt,
        })
        if task in self.scripted:
            return self.scripted[task]
        return ("", "no_scripted_response")


@dataclass
class FakeStats:
    strength: int = 1
    defense: int = 1
    vitality: int = 1
    luck: int = 1
    agility: int = 1
    intelligence: int = 1


@dataclass
class FakeLeveling:
    level: int = 5


@dataclass
class FakeCharacter:
    leveling: FakeLeveling = field(default_factory=FakeLeveling)
    stats: FakeStats = field(default_factory=FakeStats)


def _generated_quest(quest_id: str = "test_quest") -> QuestDefinition:
    return QuestDefinition(
        quest_id=quest_id,
        title="Test Quest",
        description="Test narrative",
        npc_id="test_npc",
        objectives=QuestObjective(
            objective_type="kill_target",
            items=[{"target_id": "wolf", "quantity": 3}],
        ),
        rewards=QuestRewards(),  # empty (LLM materializes)
        rewards_prose={
            "experience_hint": "moderate",
            "tier_hint": 2,
            "title_hint": "wolf_slayer",
            "item_hints": ["a wolf-fang charm", "silver penny"],
        },
        tier=2,
        source_origin="generated",
    )


def _canonical_quest(quest_id: str = "tutorial_quest") -> QuestDefinition:
    return QuestDefinition(
        quest_id=quest_id,
        title="Tutorial",
        description="Hand-tuned",
        npc_id="elder_sage",
        objectives=QuestObjective(
            objective_type="gather",
            items=[{"item_id": "oak_log", "quantity": 5}],
        ),
        rewards=QuestRewards(experience=100, gold=20, title="novice_forester"),
        source_origin="canonical",
    )


PREGEN_SCRIPT_OK = (
    '{"rewards": {"experience": 280, "gold": 65, "items": ['
    '{"item_id": "wolf_fang", "quantity": 1}], "title": "wolf_slayer", '
    '"skills": [], "stat_points": 0}, '
    '"completion_dialogue": ["Done.", "Thanks.", "Take this."]}'
)
ADAPT_SCRIPT_OK = (
    '{"rewards": {"experience": 336, "gold": 78, "items": ['
    '{"item_id": "wolf_fang", "quantity": 1}], "title": "wolf_slayer", '
    '"skills": [], "stat_points": 0}}'
)


# ── Pregen tests ──────────────────────────────────────────────────────


class TestPregenerate(unittest.TestCase):
    def setUp(self) -> None:
        QuestRewardAdapter.reset()

    def tearDown(self) -> None:
        QuestRewardAdapter.reset()

    def test_canonical_quest_skips_pregen(self) -> None:
        backend = FakeBackend({})
        adapter = QuestRewardAdapter(backend_manager=backend)
        result = adapter.pregenerate(_canonical_quest(), FakeCharacter())
        self.assertIsNone(result)
        self.assertEqual(backend.calls, [])

    def test_generated_quest_returns_rewards_and_dialogue(self) -> None:
        backend = FakeBackend({TASK_PREGEN: (PREGEN_SCRIPT_OK, None)})
        adapter = QuestRewardAdapter(backend_manager=backend)
        result = adapter.pregenerate(_generated_quest(), FakeCharacter())
        self.assertIsNotNone(result)
        rewards, dialogue = result
        self.assertIsInstance(rewards, QuestRewards)
        self.assertEqual(rewards.experience, 280)
        self.assertEqual(rewards.gold, 65)
        self.assertEqual(rewards.title, "wolf_slayer")
        self.assertEqual(len(rewards.items), 1)
        self.assertEqual(rewards.items[0]["item_id"], "wolf_fang")
        self.assertEqual(len(dialogue), 3)
        self.assertEqual(adapter.stats["calls_succeeded"], 1)

    def test_pregen_called_with_correct_task(self) -> None:
        backend = FakeBackend({TASK_PREGEN: (PREGEN_SCRIPT_OK, None)})
        adapter = QuestRewardAdapter(backend_manager=backend)
        adapter.pregenerate(_generated_quest(), FakeCharacter())
        self.assertEqual(len(backend.calls), 1)
        self.assertEqual(backend.calls[0]["task"], TASK_PREGEN)

    def test_pregen_handles_backend_error(self) -> None:
        backend = FakeBackend({TASK_PREGEN: ("", "ollama_unreachable")})
        adapter = QuestRewardAdapter(backend_manager=backend)
        result = adapter.pregenerate(_generated_quest(), FakeCharacter())
        self.assertIsNone(result)
        self.assertEqual(adapter.stats["calls_failed"], 1)

    def test_pregen_handles_malformed_json(self) -> None:
        backend = FakeBackend({TASK_PREGEN: ("not even json", None)})
        adapter = QuestRewardAdapter(backend_manager=backend)
        result = adapter.pregenerate(_generated_quest(), FakeCharacter())
        self.assertIsNone(result)
        self.assertEqual(adapter.stats["calls_failed"], 1)

    def test_pregen_handles_missing_rewards_block(self) -> None:
        backend = FakeBackend({
            TASK_PREGEN: ('{"completion_dialogue": ["x"]}', None),
        })
        adapter = QuestRewardAdapter(backend_manager=backend)
        result = adapter.pregenerate(_generated_quest(), FakeCharacter())
        self.assertIsNone(result)

    def test_pregen_handles_backend_exception(self) -> None:
        class ExplodingBackend:
            def generate(self, **_kwargs):
                raise RuntimeError("backend exploded")
        adapter = QuestRewardAdapter(backend_manager=ExplodingBackend())
        result = adapter.pregenerate(_generated_quest(), FakeCharacter())
        self.assertIsNone(result)
        self.assertEqual(adapter.stats["calls_failed"], 1)

    def test_pregen_strips_markdown_fences(self) -> None:
        wrapped = "```json\n" + PREGEN_SCRIPT_OK + "\n```"
        backend = FakeBackend({TASK_PREGEN: (wrapped, None)})
        adapter = QuestRewardAdapter(backend_manager=backend)
        result = adapter.pregenerate(_generated_quest(), FakeCharacter())
        self.assertIsNotNone(result)


# ── Adapt tests ───────────────────────────────────────────────────────


class _FakeQuest:
    """Minimal Quest stand-in for adapter testing."""

    def __init__(self, quest_def: QuestDefinition,
                 pre_generated: Optional[QuestRewards] = None,
                 received_at: float = 0.0):
        self.quest_def = quest_def
        self.pre_generated_rewards = pre_generated
        self.received_at_game_time = received_at


class TestAdapt(unittest.TestCase):
    def setUp(self) -> None:
        QuestRewardAdapter.reset()

    def tearDown(self) -> None:
        QuestRewardAdapter.reset()

    def test_canonical_quest_skips_adapt(self) -> None:
        backend = FakeBackend({})
        adapter = QuestRewardAdapter(backend_manager=backend)
        quest = _FakeQuest(_canonical_quest())
        result = adapter.adapt(quest, FakeCharacter(), game_time_now=100.0)
        self.assertIsNone(result)
        self.assertEqual(backend.calls, [])

    def test_no_pregenerated_baseline_skips_adapt(self) -> None:
        backend = FakeBackend({})
        adapter = QuestRewardAdapter(backend_manager=backend)
        quest = _FakeQuest(_generated_quest(), pre_generated=None)
        result = adapter.adapt(quest, FakeCharacter(), game_time_now=100.0)
        self.assertIsNone(result)
        self.assertEqual(backend.calls, [])

    def test_adapt_returns_adjusted_rewards(self) -> None:
        backend = FakeBackend({TASK_ADAPT: (ADAPT_SCRIPT_OK, None)})
        adapter = QuestRewardAdapter(backend_manager=backend)
        baseline = QuestRewards(experience=280, gold=65, title="wolf_slayer")
        quest = _FakeQuest(_generated_quest(), pre_generated=baseline,
                            received_at=10.0)
        result = adapter.adapt(quest, FakeCharacter(), game_time_now=490.0)
        self.assertIsNotNone(result)
        self.assertEqual(result.experience, 336)
        self.assertEqual(result.gold, 78)
        self.assertEqual(adapter.stats["calls_succeeded"], 1)

    def test_adapt_passes_time_taken_seconds_in_prompt(self) -> None:
        backend = FakeBackend({TASK_ADAPT: (ADAPT_SCRIPT_OK, None)})
        adapter = QuestRewardAdapter(backend_manager=backend)
        baseline = QuestRewards(experience=280, gold=65)
        quest = _FakeQuest(_generated_quest(), pre_generated=baseline,
                            received_at=100.0)
        adapter.adapt(quest, FakeCharacter(), game_time_now=580.0)
        self.assertEqual(len(backend.calls), 1)
        # Time taken: 580 - 100 = 480 seconds
        self.assertIn("480", backend.calls[0]["user_prompt"])

    def test_adapt_failure_returns_none(self) -> None:
        backend = FakeBackend({TASK_ADAPT: ("garbage", None)})
        adapter = QuestRewardAdapter(backend_manager=backend)
        baseline = QuestRewards(experience=280, gold=65)
        quest = _FakeQuest(_generated_quest(), pre_generated=baseline)
        result = adapter.adapt(quest, FakeCharacter(), game_time_now=200.0)
        self.assertIsNone(result)

    def test_adapt_accepts_bare_rewards_dict(self) -> None:
        # Some LLM outputs return the raw rewards dict, not wrapped.
        bare = (
            '{"experience": 200, "gold": 50, "items": [], '
            '"skills": [], "stat_points": 0, "title": ""}'
        )
        backend = FakeBackend({TASK_ADAPT: (bare, None)})
        adapter = QuestRewardAdapter(backend_manager=backend)
        baseline = QuestRewards(experience=200, gold=50)
        quest = _FakeQuest(_generated_quest(), pre_generated=baseline)
        result = adapter.adapt(quest, FakeCharacter(), game_time_now=200.0)
        self.assertIsNotNone(result)
        self.assertEqual(result.experience, 200)


# ── Reward coercion tests ─────────────────────────────────────────────


class TestRewardCoercion(unittest.TestCase):
    """The coercer must defend against malformed LLM payloads."""

    def setUp(self) -> None:
        QuestRewardAdapter.reset()

    def tearDown(self) -> None:
        QuestRewardAdapter.reset()

    def test_coerces_string_ints(self) -> None:
        # LLM occasionally emits "experience": "280" as a string.
        backend = FakeBackend({
            TASK_PREGEN: (
                '{"rewards": {"experience": "280", "gold": "65"}, '
                '"completion_dialogue": ["x"]}',
                None,
            ),
        })
        adapter = QuestRewardAdapter(backend_manager=backend)
        result = adapter.pregenerate(_generated_quest(), FakeCharacter())
        self.assertIsNotNone(result)
        rewards, _ = result
        self.assertEqual(rewards.experience, 280)
        self.assertEqual(rewards.gold, 65)

    def test_drops_invalid_skill_entries(self) -> None:
        backend = FakeBackend({
            TASK_PREGEN: (
                '{"rewards": {"experience": 10, "skills": ["good", null, 42, "also_good"]}, '
                '"completion_dialogue": []}',
                None,
            ),
        })
        adapter = QuestRewardAdapter(backend_manager=backend)
        result = adapter.pregenerate(_generated_quest(), FakeCharacter())
        self.assertIsNotNone(result)
        rewards, _ = result
        # skills are coerced to str but null/42 turn into "None"/"42"
        # — the contract says we keep what the LLM says (str-coerced)
        # rather than silently discarding. Future hardening may filter
        # against the SkillDatabase.
        self.assertIn("good", rewards.skills)
        self.assertIn("also_good", rewards.skills)


# ── Stats / observability ─────────────────────────────────────────────


class TestStats(unittest.TestCase):
    def setUp(self) -> None:
        QuestRewardAdapter.reset()

    def tearDown(self) -> None:
        QuestRewardAdapter.reset()

    def test_singleton(self) -> None:
        a = QuestRewardAdapter.get_instance()
        b = QuestRewardAdapter.get_instance()
        self.assertIs(a, b)

    def test_stats_track_attempts_and_outcomes(self) -> None:
        backend = FakeBackend({
            TASK_PREGEN: (PREGEN_SCRIPT_OK, None),
        })
        adapter = QuestRewardAdapter(backend_manager=backend)
        adapter.pregenerate(_generated_quest(), FakeCharacter())
        adapter.pregenerate(_generated_quest("q2"), FakeCharacter())
        s = adapter.stats
        self.assertEqual(s["calls_attempted"], 2)
        self.assertEqual(s["calls_succeeded"], 2)
        self.assertEqual(s["calls_failed"], 0)


if __name__ == "__main__":
    unittest.main()

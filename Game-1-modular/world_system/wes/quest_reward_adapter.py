"""Quest reward adapter — pre-gen at receive, adapt at turn-in.

The flow (per design 2026-04-26):

1. **Quest received**: WES materializes the quest's ``rewards_prose``
   into concrete :class:`QuestRewards` *and* a completion-dialogue
   list. Both are stored on the runtime :class:`Quest` instance and
   used as the floor.

2. **Quest in progress**: standard mechanics. No LLM calls.

3. **Quest objectives met**: the pre-generated reward is the floor.

4. **Quest turn-in**: WES is invoked again to *adapt* the reward
   based on actual play (time taken, urgency-met, narrative weight).
   The adapted reward overrides the pre-generated one. If the LLM
   call fails, the pre-generated reward is awarded instead — no
   click-and-wait, no missed reward.

This module is intentionally **failure-quiet**: every external call
is wrapped, every parse is best-effort, and ``None`` is the universal
"couldn't do it, fall through to the next layer" return value. The
caller (:class:`QuestManager`) chains the fallback.

Canonical quests (``quest_def.source_origin == "canonical"``) skip
this module entirely. Tutorial / hand-authored reward economy is
preserved exactly.
"""

from __future__ import annotations

import json
import os
import threading
from dataclasses import asdict
from typing import Any, ClassVar, Dict, List, Optional, Tuple

from data.models.quests import QuestDefinition, QuestRewards
from world_system.living_world.backends.backend_manager import BackendManager
from world_system.living_world.infra.graceful_degrade import log_degrade


# Task codes consumed by BackendManager. Both have prompt-fragment
# JSONs in ``world_system/config/`` and fixture entries in
# ``llm_fixtures/builtin.py``.
TASK_PREGEN: str = "wes_quest_reward_pregen"
TASK_ADAPT: str = "wes_quest_reward_adapt"


def _resolve_config_path(filename: str) -> str:
    here = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(os.path.dirname(here))
    return os.path.join(project_root, "world_system", "config", filename)


def _strip_markdown_fence(text: str) -> str:
    s = text.strip()
    if s.startswith("```"):
        first_nl = s.find("\n")
        if first_nl >= 0:
            s = s[first_nl + 1:]
        if s.endswith("```"):
            s = s[:-3]
    return s.strip()


def _parse_json_loose(text: str) -> Optional[Dict[str, Any]]:
    """Permissive JSON parse — strips fences and finds the first
    {...} block if the wrapper is sloppy."""
    if not text:
        return None
    try:
        data = json.loads(_strip_markdown_fence(text))
        if isinstance(data, dict):
            return data
    except Exception:
        pass
    s = _strip_markdown_fence(text)
    first = s.find("{")
    last = s.rfind("}")
    if first >= 0 and last > first:
        try:
            data = json.loads(s[first:last + 1])
            if isinstance(data, dict):
                return data
        except Exception:
            return None
    return None


def _coerce_rewards(payload: Dict[str, Any]) -> QuestRewards:
    """Build a :class:`QuestRewards` from a permissive dict.

    Unknown keys are dropped. Missing keys default per the dataclass.
    Type coercion: ints get int(), strings get str(), lists get list().
    """
    def _i(v: Any, default: int = 0) -> int:
        try:
            return int(v)
        except (TypeError, ValueError):
            return default

    def _s(v: Any, default: str = "") -> str:
        return str(v) if v is not None else default

    def _list(v: Any) -> List[Any]:
        if isinstance(v, list):
            return list(v)
        return []

    return QuestRewards(
        experience=_i(payload.get("experience"), 0),
        gold=_i(payload.get("gold"), 0),
        health_restore=_i(payload.get("health_restore"), 0),
        mana_restore=_i(payload.get("mana_restore"), 0),
        skills=[_s(x) for x in _list(payload.get("skills"))],
        items=[x for x in _list(payload.get("items")) if isinstance(x, dict)],
        title=_s(payload.get("title"), ""),
        stat_points=_i(payload.get("stat_points"), 0),
        status_effects=[
            x for x in _list(payload.get("status_effects")) if isinstance(x, dict)
        ],
        buffs=[x for x in _list(payload.get("buffs")) if isinstance(x, dict)],
    )


def _coerce_dialogue(payload: Dict[str, Any]) -> List[str]:
    raw = payload.get("completion_dialogue")
    if not isinstance(raw, list):
        return []
    return [str(x) for x in raw if x]


# ── Adapter (singleton) ───────────────────────────────────────────────


class QuestRewardAdapter:
    """Materializes prose rewards at receive, adapts them at turn-in.

    Singleton so the app holds one BackendManager reference. The
    :class:`QuestManager` picks the singleton via
    :func:`get_reward_adapter` at call time — easy to swap with a
    test double via :meth:`reset` + custom construction.
    """

    _instance: ClassVar[Optional["QuestRewardAdapter"]] = None
    _lock = threading.Lock()

    def __init__(self, backend_manager: Optional[BackendManager] = None) -> None:
        self._backend = backend_manager
        self._lock = threading.RLock()
        self._calls_attempted: int = 0
        self._calls_succeeded: int = 0
        self._calls_failed: int = 0

    @classmethod
    def get_instance(cls) -> "QuestRewardAdapter":
        with cls._lock:
            if cls._instance is None:
                cls._instance = cls()
            return cls._instance

    @classmethod
    def reset(cls) -> None:
        """Test helper — drop the singleton."""
        with cls._lock:
            cls._instance = None

    @property
    def stats(self) -> Dict[str, int]:
        with self._lock:
            return {
                "calls_attempted": self._calls_attempted,
                "calls_succeeded": self._calls_succeeded,
                "calls_failed": self._calls_failed,
            }

    # ── Public API ───────────────────────────────────────────────────

    def pregenerate(
        self,
        quest_def: QuestDefinition,
        character: Any = None,
    ) -> Optional[Tuple[QuestRewards, List[str]]]:
        """Materialize concrete rewards + completion dialogue.

        Returns ``(QuestRewards, completion_dialogue)`` on success,
        ``None`` on any failure. Caller treats None as "use the
        quest_def.rewards as-is" (typically zeroed for generated
        quests, hand-authored for canonical ones).

        Best-effort: a backend exception, parse failure, empty
        response, or schema mismatch all degrade quietly via
        :func:`log_degrade`.
        """
        if quest_def is None:
            return None
        if quest_def.source_origin != "generated":
            # Canonical quests bypass — preserve hand-tuned economy.
            return None
        return self._call_with_task(
            task=TASK_PREGEN,
            system_prompt_path=_resolve_config_path(
                "prompt_fragments_wes_quest_reward_pregen.json"
            ),
            variables=self._pregen_vars(quest_def, character),
            extract=self._extract_pregen,
        )

    def adapt(
        self,
        quest: Any,  # systems.quest_system.Quest
        character: Any,
        game_time_now: Optional[float] = None,
    ) -> Optional[QuestRewards]:
        """Adjust the pre-generated reward at turn-in.

        Returns adapted :class:`QuestRewards` on success, ``None`` if
        the LLM call fails or there is no pre-generated reward to
        adjust. Caller's resolution chain (adapted ?? pre_generated
        ?? quest_def.rewards) handles the None case.
        """
        if quest is None or character is None:
            return None
        quest_def = getattr(quest, "quest_def", None)
        if quest_def is None or quest_def.source_origin != "generated":
            return None
        # No pre-generated baseline -> nothing to "adapt". Skip.
        baseline = getattr(quest, "pre_generated_rewards", None)
        if baseline is None:
            return None
        return self._call_with_task(
            task=TASK_ADAPT,
            system_prompt_path=_resolve_config_path(
                "prompt_fragments_wes_quest_reward_adapt.json"
            ),
            variables=self._adapt_vars(quest, character, game_time_now),
            extract=self._extract_adapt,
        )

    # ── Internals ────────────────────────────────────────────────────

    def _backend_manager(self) -> BackendManager:
        if self._backend is None:
            self._backend = BackendManager.get_instance()
        return self._backend

    def _call_with_task(
        self,
        *,
        task: str,
        system_prompt_path: str,
        variables: Dict[str, Any],
        extract,
    ) -> Optional[Any]:
        with self._lock:
            self._calls_attempted += 1
        prompts = self._load_prompts(system_prompt_path, variables)
        if prompts is None:
            self._record_fail(task, "prompt_load_failed")
            return None
        try:
            text, err = self._backend_manager().generate(
                task=task,
                system_prompt=prompts["system"],
                user_prompt=prompts["user"],
            )
        except Exception as e:
            self._record_fail(task, f"backend_exception: {type(e).__name__}: {e}")
            return None
        if err or not text:
            self._record_fail(task, f"backend_error: {err or 'empty'}")
            return None
        payload = _parse_json_loose(text)
        if payload is None:
            self._record_fail(task, "json_parse_failed")
            return None
        try:
            extracted = extract(payload)
        except Exception as e:
            self._record_fail(task, f"extract_failed: {type(e).__name__}: {e}")
            return None
        if extracted is None:
            self._record_fail(task, "extract_returned_none")
            return None
        with self._lock:
            self._calls_succeeded += 1
        return extracted

    @staticmethod
    def _load_prompts(
        system_prompt_path: str, variables: Dict[str, Any]
    ) -> Optional[Dict[str, str]]:
        """Build ``{"system": ..., "user": ...}`` from the prompt JSON.

        Returns None if the file is missing or malformed (caller treats
        as a hard fail).
        """
        if not os.path.exists(system_prompt_path):
            log_degrade(
                subsystem="quest_reward_adapter",
                operation="load_prompts",
                failure_reason=f"FileNotFoundError: {system_prompt_path}",
                fallback_taken="skip LLM call",
                severity="warning",
                context={},
            )
            return None
        try:
            with open(system_prompt_path, "r", encoding="utf-8") as f:
                fragments = json.load(f)
        except Exception as e:
            log_degrade(
                subsystem="quest_reward_adapter",
                operation="load_prompts",
                failure_reason=f"{type(e).__name__}: {e}",
                fallback_taken="skip LLM call",
                severity="warning",
                context={"path": system_prompt_path},
            )
            return None
        core = fragments.get("_core", {}) if isinstance(fragments, dict) else {}
        system = str(core.get("system", "")) or "You are a quest reward materializer."
        user_template = str(core.get("user_template", ""))
        user = user_template
        for key, value in variables.items():
            user = user.replace("${" + key + "}", _stringify(value))
        return {"system": system, "user": user}

    def _record_fail(self, task: str, reason: str) -> None:
        with self._lock:
            self._calls_failed += 1
        log_degrade(
            subsystem="quest_reward_adapter",
            operation=task,
            failure_reason=reason,
            fallback_taken="caller falls back to pre-generated or design rewards",
            severity="info",
            context={"task": task},
        )

    # ── Variable builders ────────────────────────────────────────────

    @staticmethod
    def _pregen_vars(
        quest_def: QuestDefinition, character: Any
    ) -> Dict[str, Any]:
        return {
            "quest_id": quest_def.quest_id,
            "quest_title": quest_def.title or quest_def.name,
            "tier": quest_def.tier,
            "rewards_prose": quest_def.rewards_prose or {},
            "objectives": _summarize_objectives(quest_def),
            "player_level": _safe_attr_chain(character, "leveling.level", 1),
            "player_stats": _summarize_stats(character),
            "narrative": _safe_dict_get(
                quest_def.description_full, "narrative", quest_def.description
            ),
        }

    @staticmethod
    def _adapt_vars(
        quest: Any, character: Any, game_time_now: Optional[float]
    ) -> Dict[str, Any]:
        baseline = getattr(quest, "pre_generated_rewards", None)
        baseline_dict: Dict[str, Any] = (
            asdict(baseline) if baseline is not None else {}
        )
        received_at = float(getattr(quest, "received_at_game_time", 0.0))
        now = float(game_time_now if game_time_now is not None else 0.0)
        time_taken = max(0.0, now - received_at)
        quest_def = quest.quest_def
        return {
            "quest_id": quest_def.quest_id,
            "quest_title": quest_def.title or quest_def.name,
            "pre_generated_rewards": baseline_dict,
            "rewards_prose": quest_def.rewards_prose or {},
            "time_taken_seconds": int(time_taken),
            "tier": quest_def.tier,
            "narrative": _safe_dict_get(
                quest_def.description_full, "narrative", quest_def.description
            ),
            "expiration": quest_def.expiration or {},
            "player_level": _safe_attr_chain(character, "leveling.level", 1),
        }

    # ── Extractors ───────────────────────────────────────────────────

    @staticmethod
    def _extract_pregen(payload: Dict[str, Any]) -> Optional[Tuple[QuestRewards, List[str]]]:
        rewards_block = payload.get("rewards")
        if not isinstance(rewards_block, dict):
            return None
        rewards = _coerce_rewards(rewards_block)
        dialogue = _coerce_dialogue(payload)
        return rewards, dialogue

    @staticmethod
    def _extract_adapt(payload: Dict[str, Any]) -> Optional[QuestRewards]:
        # Two acceptable shapes: {"rewards": {...}} or a bare rewards dict
        candidate = payload.get("rewards") if "rewards" in payload else payload
        if not isinstance(candidate, dict):
            return None
        return _coerce_rewards(candidate)


# ── Helpers (module-private) ─────────────────────────────────────────


def _stringify(v: Any) -> str:
    if isinstance(v, str):
        return v
    try:
        return json.dumps(v)
    except Exception:
        return str(v)


def _safe_attr_chain(obj: Any, dotted: str, default: Any) -> Any:
    cur = obj
    for part in dotted.split("."):
        if cur is None:
            return default
        cur = getattr(cur, part, None)
    return cur if cur is not None else default


def _safe_dict_get(d: Any, key: str, default: Any) -> Any:
    if isinstance(d, dict) and key in d and d[key] is not None:
        return d[key]
    return default


def _summarize_objectives(quest_def: QuestDefinition) -> Dict[str, Any]:
    objs = quest_def.objectives
    return {
        "type": getattr(objs, "objective_type", ""),
        "items": list(getattr(objs, "items", []) or []),
        "enemies_killed": int(getattr(objs, "enemies_killed", 0)),
    }


def _summarize_stats(character: Any) -> Dict[str, int]:
    """Best-effort pull of character stats. Empty on absence."""
    stats = getattr(character, "stats", None)
    if stats is None:
        return {}
    out: Dict[str, int] = {}
    for stat_name in ("strength", "defense", "vitality", "luck", "agility", "intelligence"):
        try:
            out[stat_name] = int(getattr(stats, stat_name, 0))
        except (TypeError, ValueError):
            continue
    return out


def get_reward_adapter() -> QuestRewardAdapter:
    """Module-level accessor matching the project singleton pattern."""
    return QuestRewardAdapter.get_instance()


__all__ = [
    "QuestRewardAdapter",
    "get_reward_adapter",
    "TASK_PREGEN",
    "TASK_ADAPT",
]

"""QuestArchiveDatabase — separate substrate for completed-quest history.

Phase 7 (2026-06-03). Per consolidation §8.2 (user's correction):
**WMS is events; archive is narratives**. The WMS continues to see
quest facts via existing event types (``quest_accepted``,
``quest_completed``, ``quest_failed``) and the ``social_quests`` L2
evaluator. The archive holds *prose history* — the kind of metadata a
WNS chronicler or WES tool needs when narratively referencing a past
quest deed.

This database is NOT in ``world_system/world_memory/`` (the WMS-events
substrate). It lives at ``data/databases/`` like every other game
content database and is exposed via ``WorldQuery`` so WNS chroniclers
and WES tools can read from it when narratively relevant.

The archive populates on quest turn-in. ``QuestManager`` (existing
runtime) writes an :class:`ArchivedQuestRecord` per completed /
failed / abandoned quest. The record carries:

    - quest_id, original quest definition snapshot
    - duration, actual_result (succeeded/failed/abandoned)
    - actual_rewards_granted (concrete numbers post-adapt)
    - participating_npcs (npc_ids the quest touched)
    - participating_entities (material/hostile/chunk ids referenced)
    - archived_narrative_tags (for WNS tag-indexed retrieval)
    - wns_thread_id (the WNS thread this quest belonged to)
    - archived_at_game_day

The read API offers tag-filtered queries (the WNS chronicler asks:
"what archived quests at this address have tag `vendetta`?") and
recency queries (the chunks tool asks: "what are the last 5 quests
the player completed in this region?").

Stringency: this is NOT a WMS structural change. Per consolidation
§2.8 the WMS-is-sufficient stringency holds; the archive is a sibling
substrate with its own read surface, separate from ``WorldMemorySystem``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, ClassVar, Dict, List, Optional


@dataclass
class ArchivedQuestRecord:
    """One completed/failed/abandoned quest record.

    Field semantics:
        quest_id: the canonical id (matches QuestDefinition.quest_id).
        original_quest_def_json: snapshot of the quest's static
            design data at acceptance time (so the archive survives
            sacred-JSON updates).
        time_started, time_completed: game-time seconds.
        duration: convenience (time_completed - time_started).
        actual_result: "succeeded" | "failed" | "abandoned" | "partial".
        actual_rewards_granted: the concrete rewards the player actually
            received (post-adapt, post-balance-check).
        participating_npcs: NPC ids the quest touched (giver, mentioned,
            interacted-with).
        participating_entities: material / hostile / chunk ids the quest
            referenced or the player engaged.
        archived_narrative_tags: tags for WNS retrieval (e.g.
            ``["vendetta", "moors", "captain_vell"]``).
        wns_thread_id: the WNS narrative thread this quest belonged to.
        archived_at_game_day: game-day at archive time, for trajectory
            queries.
    """

    quest_id: str
    original_quest_def_json: Dict[str, Any]
    time_started: float
    time_completed: float
    duration: float
    actual_result: str
    actual_rewards_granted: Dict[str, Any] = field(default_factory=dict)
    participating_npcs: List[str] = field(default_factory=list)
    participating_entities: List[str] = field(default_factory=list)
    archived_narrative_tags: List[str] = field(default_factory=list)
    wns_thread_id: Optional[str] = None
    archived_at_game_day: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "quest_id": self.quest_id,
            "original_quest_def_json": dict(self.original_quest_def_json),
            "time_started": float(self.time_started),
            "time_completed": float(self.time_completed),
            "duration": float(self.duration),
            "actual_result": self.actual_result,
            "actual_rewards_granted": dict(self.actual_rewards_granted),
            "participating_npcs": list(self.participating_npcs),
            "participating_entities": list(self.participating_entities),
            "archived_narrative_tags": list(self.archived_narrative_tags),
            "wns_thread_id": self.wns_thread_id,
            "archived_at_game_day": int(self.archived_at_game_day),
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "ArchivedQuestRecord":
        return cls(
            quest_id=d["quest_id"],
            original_quest_def_json=dict(d.get("original_quest_def_json", {})),
            time_started=float(d.get("time_started", 0.0)),
            time_completed=float(d.get("time_completed", 0.0)),
            duration=float(d.get("duration", 0.0)),
            actual_result=d.get("actual_result", "succeeded"),
            actual_rewards_granted=dict(d.get("actual_rewards_granted", {})),
            participating_npcs=list(d.get("participating_npcs", [])),
            participating_entities=list(d.get("participating_entities", [])),
            archived_narrative_tags=list(d.get("archived_narrative_tags", [])),
            wns_thread_id=d.get("wns_thread_id"),
            archived_at_game_day=int(d.get("archived_at_game_day", 0)),
        )


class QuestArchiveDatabase:
    """Singleton substrate for archived quest records (Phase 7, 2026-06-03).

    Designed for query patterns the WNS chronicler and WES tools need:

        - tag-filtered: ``query_by_tags(tags, match_all=True)``
        - recency: ``recent_archived(limit=5)``
        - per-NPC: ``query_by_npc(npc_id)``
        - per-entity: ``query_by_entity(entity_id)``
        - per-result: ``query_by_result(result_kind)``

    Stateless across process restarts in v4 — the in-memory dict is the
    canonical store. Persistence (SQLite, JSON dump) is a future
    enhancement; the API is shaped so callers don't need to know.
    """

    _instance: ClassVar[Optional["QuestArchiveDatabase"]] = None

    def __init__(self) -> None:
        # quest_id → record. One archive per quest acceptance —
        # re-accepting a quest creates a new instance with a fresh
        # quest_id (e.g. ``vendetta_001#accept_2``); IDs do not collide.
        self._records: Dict[str, ArchivedQuestRecord] = {}

    @classmethod
    def get_instance(cls) -> "QuestArchiveDatabase":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        """Test helper — drop the singleton."""
        cls._instance = None

    # ── Write API ───────────────────────────────────────────────────

    def archive(self, record: ArchivedQuestRecord) -> None:
        """Persist a record. Idempotent — same quest_id overwrites."""
        self._records[record.quest_id] = record

    # ── Read APIs ───────────────────────────────────────────────────

    def get(self, quest_id: str) -> Optional[ArchivedQuestRecord]:
        return self._records.get(quest_id)

    def all_records(self) -> List[ArchivedQuestRecord]:
        return list(self._records.values())

    def query_by_tags(
        self,
        tags: List[str],
        *,
        match_all: bool = True,
        limit: int = 100,
    ) -> List[ArchivedQuestRecord]:
        """Return records whose ``archived_narrative_tags`` intersect
        ``tags``. When ``match_all`` is True (default), every tag must
        be present; when False, any single match qualifies.
        """
        if not tags:
            return []
        results: List[ArchivedQuestRecord] = []
        tag_set = set(tags)
        for record in self._records.values():
            record_tags = set(record.archived_narrative_tags)
            if match_all:
                if tag_set.issubset(record_tags):
                    results.append(record)
            else:
                if tag_set & record_tags:
                    results.append(record)
            if len(results) >= limit:
                break
        return results

    def recent_archived(self, limit: int = 5) -> List[ArchivedQuestRecord]:
        """Return the N most recent archived records by
        ``time_completed``."""
        sorted_records = sorted(
            self._records.values(),
            key=lambda r: r.time_completed,
            reverse=True,
        )
        return sorted_records[:limit]

    def query_by_npc(self, npc_id: str) -> List[ArchivedQuestRecord]:
        """Return all records mentioning ``npc_id``."""
        return [
            r for r in self._records.values()
            if npc_id in r.participating_npcs
        ]

    def query_by_entity(
        self, entity_id: str,
    ) -> List[ArchivedQuestRecord]:
        """Return all records mentioning ``entity_id`` (material,
        hostile, chunk, etc.)."""
        return [
            r for r in self._records.values()
            if entity_id in r.participating_entities
        ]

    def query_by_result(
        self, result_kind: str,
    ) -> List[ArchivedQuestRecord]:
        """Return all records with the given ``actual_result``."""
        return [
            r for r in self._records.values()
            if r.actual_result == result_kind
        ]

    # ── Stats / introspection ───────────────────────────────────────

    def count(self) -> int:
        """Total record count."""
        return len(self._records)


__all__ = ["ArchivedQuestRecord", "QuestArchiveDatabase"]

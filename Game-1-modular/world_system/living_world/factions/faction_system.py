"""Faction System Database Manager — Phase 2+.

Singleton manager for all faction data: NPC profiles, player affinity,
NPC affinity toward other tags (including the player), and location defaults.
Separate SQLite database (faction.db) from WMS.

Information flow (Recording):
- Game events (quests, combat) → quest/combat system provides affinity deltas
- Deltas → FactionSystem.adjust_player_affinity() → player_affinity table
- adjust_player_affinity() publishes FACTION_AFFINITY_CHANGED on GameEventBus
- WMS FactionReputationEvaluator listens to FACTION_AFFINITY_CHANGED and
  produces Layer 2 narratives.

Information flow (Retrieval — dialogue context):
- NPC dialogue requested → FactionSystem.get_npc_profile()
  + get_npc_affinity_toward_player()
- Player affinity with NPC's tags → get_all_player_affinities()
- Location affinity defaults → compute_inherited_affinity()
- Context assembled for LLM dialogue generation (see LLM_INTEGRATION.md)
"""

from __future__ import annotations

import json
import sqlite3
from typing import ClassVar, Dict, List, Optional, Tuple

from core.paths import get_faction_db_path
from events.event_bus import get_event_bus

from .models import FactionTag, NPCProfile
from .schema import (
    NPC_AFFINITY_PLAYER_TAG,
    FactionDatabaseSchema,
    bootstrap_location_defaults,
)


FACTION_AFFINITY_CHANGED = "FACTION_AFFINITY_CHANGED"


class FactionSystem:
    """Singleton manager for faction SQLite database."""

    _instance: ClassVar[Optional["FactionSystem"]] = None

    def __init__(self):
        self.db_path = get_faction_db_path()
        self.connection: Optional[sqlite3.Connection] = None
        self._initialized = False

    @classmethod
    def get_instance(cls) -> "FactionSystem":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        """Reset singleton (for testing)."""
        if cls._instance and cls._instance.connection:
            cls._instance.connection.close()
        cls._instance = None

    def initialize(self) -> None:
        """Initialize database connection, schema, and bootstrap defaults."""
        if self._initialized:
            return

        try:
            self.connection = sqlite3.connect(
                str(self.db_path),
                check_same_thread=False,
            )
            self.connection.row_factory = sqlite3.Row

            FactionDatabaseSchema.create_all_tables(self.connection)
            bootstrap_location_defaults(self.connection)

            self._initialized = True
            print(f"[FactionSystem] Initialized at {self.db_path}")
        except Exception as e:
            print(f"[FactionSystem] Initialization error: {e}")
            raise

    # ------------------------------------------------------------------
    # NPC profile operations
    # ------------------------------------------------------------------

    def add_npc(self, npc_id: str, narrative: str, game_time: float = 0.0) -> None:
        """Add or update NPC profile."""
        self._require_connection()
        cursor = self.connection.cursor()
        cursor.execute(
            "INSERT OR REPLACE INTO npc_profiles "
            "(npc_id, narrative, created_at, last_updated) VALUES (?, ?, ?, ?)",
            (npc_id, narrative, game_time, game_time),
        )
        self.connection.commit()

    def get_npc_profile(self, npc_id: str) -> Optional[NPCProfile]:
        """Get NPC profile with belonging tags and affinity toward tags.

        The NPC's personal affinity toward the player is stored under the
        reserved tag NPC_AFFINITY_PLAYER_TAG and appears in the returned
        profile.affinity dict. Callers who want tag-only affinity should
        filter it out, or use ``get_npc_affinity_toward_player`` directly.
        """
        self._require_connection()
        cursor = self.connection.cursor()

        cursor.execute(
            "SELECT narrative, created_at, last_updated FROM npc_profiles WHERE npc_id = ?",
            (npc_id,),
        )
        row = cursor.fetchone()
        if not row:
            return None

        profile = NPCProfile(
            npc_id=npc_id,
            narrative=row[0],
            created_at=row[1],
            last_updated=row[2],
        )

        cursor.execute(
            "SELECT tag, significance, role, narrative_hooks, since_game_time "
            "FROM npc_belonging_tags WHERE npc_id = ?",
            (npc_id,),
        )
        for tag_row in cursor.fetchall():
            hooks = json.loads(tag_row[3]) if tag_row[3] else []
            profile.add_tag(
                tag=tag_row[0],
                significance=tag_row[1],
                role=tag_row[2],
                narrative_hooks=hooks,
                game_time=tag_row[4],
            )

        cursor.execute(
            "SELECT tag, affinity_value FROM npc_affinity WHERE npc_id = ?",
            (npc_id,),
        )
        for aff_row in cursor.fetchall():
            profile.set_affinity(aff_row[0], aff_row[1])

        return profile

    def add_npc_belonging_tag(
        self,
        npc_id: str,
        tag: str,
        significance: float,
        role: Optional[str] = None,
        narrative_hooks: Optional[List[str]] = None,
        game_time: float = 0.0,
    ) -> None:
        """Add or update an NPC belonging tag."""
        self._require_connection()
        hooks_json = json.dumps(narrative_hooks or [])
        cursor = self.connection.cursor()
        cursor.execute(
            """INSERT OR REPLACE INTO npc_belonging_tags
               (npc_id, tag, significance, role, narrative_hooks, since_game_time)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (npc_id, tag, significance, role, hooks_json, game_time),
        )
        self.connection.commit()

    def get_npc_belonging_tags(self, npc_id: str) -> List[FactionTag]:
        """Get all belonging tags for an NPC."""
        self._require_connection()
        cursor = self.connection.cursor()
        cursor.execute(
            """SELECT tag, significance, role, narrative_hooks, since_game_time
               FROM npc_belonging_tags WHERE npc_id = ?""",
            (npc_id,),
        )
        tags = []
        for row in cursor.fetchall():
            hooks = json.loads(row[3]) if row[3] else []
            tags.append(
                FactionTag(
                    tag=row[0],
                    significance=row[1],
                    role=row[2],
                    narrative_hooks=hooks,
                    since_game_time=row[4],
                )
            )
        return tags

    def get_all_npcs_with_tag(self, tag: str) -> List[str]:
        """Get all NPC IDs that have a specific belonging tag."""
        self._require_connection()
        cursor = self.connection.cursor()
        cursor.execute(
            "SELECT DISTINCT npc_id FROM npc_belonging_tags WHERE tag = ?",
            (tag,),
        )
        return [row[0] for row in cursor.fetchall()]

    # ------------------------------------------------------------------
    # Player affinity
    # ------------------------------------------------------------------

    def set_player_affinity(
        self, player_id: str, tag: str, value: float, game_time: float = 0.0
    ) -> float:
        """Set player affinity with tag (-100 to 100). Returns clamped value.

        Publishes FACTION_AFFINITY_CHANGED with source="set".
        """
        self._require_connection()
        cursor = self.connection.cursor()
        cursor.execute(
            "SELECT affinity_value FROM player_affinity WHERE player_id = ? AND tag = ?",
            (player_id, tag),
        )
        row = cursor.fetchone()
        previous = row[0] if row else 0.0

        clamped = max(-100.0, min(100.0, value))
        cursor.execute(
            "INSERT OR REPLACE INTO player_affinity "
            "(player_id, tag, affinity_value, last_updated) VALUES (?, ?, ?, ?)",
            (player_id, tag, clamped, game_time),
        )
        self.connection.commit()

        delta = clamped - previous
        if delta != 0.0:
            self._publish_affinity_changed(
                player_id=player_id,
                tag=tag,
                delta=delta,
                new_value=clamped,
                source="set",
            )
        return clamped

    def adjust_player_affinity(
        self, player_id: str, tag: str, delta: float, game_time: float = 0.0
    ) -> float:
        """Adjust player affinity by delta, return new value.

        Publishes FACTION_AFFINITY_CHANGED with source="adjust".
        """
        self._require_connection()
        cursor = self.connection.cursor()
        cursor.execute(
            "SELECT affinity_value FROM player_affinity WHERE player_id = ? AND tag = ?",
            (player_id, tag),
        )
        row = cursor.fetchone()
        current = row[0] if row else 0.0
        new_value = max(-100.0, min(100.0, current + delta))

        cursor.execute(
            "INSERT OR REPLACE INTO player_affinity "
            "(player_id, tag, affinity_value, last_updated) VALUES (?, ?, ?, ?)",
            (player_id, tag, new_value, game_time),
        )
        self.connection.commit()

        actual_delta = new_value - current
        if actual_delta != 0.0:
            self._publish_affinity_changed(
                player_id=player_id,
                tag=tag,
                delta=actual_delta,
                new_value=new_value,
                source="adjust",
            )
        return new_value

    def get_player_affinity(self, player_id: str, tag: str) -> float:
        """Get player affinity with tag (default 0)."""
        self._require_connection()
        cursor = self.connection.cursor()
        cursor.execute(
            "SELECT affinity_value FROM player_affinity WHERE player_id = ? AND tag = ?",
            (player_id, tag),
        )
        row = cursor.fetchone()
        return row[0] if row else 0.0

    def get_all_player_affinities(self, player_id: str) -> Dict[str, float]:
        """Get all affinity values for a player (tag → -100..100)."""
        self._require_connection()
        cursor = self.connection.cursor()
        cursor.execute(
            "SELECT tag, affinity_value FROM player_affinity WHERE player_id = ?",
            (player_id,),
        )
        return {row[0]: row[1] for row in cursor.fetchall()}

    # ------------------------------------------------------------------
    # NPC affinity toward tags (and toward player via reserved tag)
    # ------------------------------------------------------------------

    def set_npc_affinity(
        self, npc_id: str, tag: str, value: float, game_time: float = 0.0
    ) -> float:
        """Set NPC affinity with a tag (-100 to 100). Returns clamped value."""
        self._require_connection()
        clamped = max(-100.0, min(100.0, value))
        cursor = self.connection.cursor()
        cursor.execute(
            "INSERT OR REPLACE INTO npc_affinity "
            "(npc_id, tag, affinity_value, last_updated) VALUES (?, ?, ?, ?)",
            (npc_id, tag, clamped, game_time),
        )
        self.connection.commit()
        return clamped

    def adjust_npc_affinity(
        self, npc_id: str, tag: str, delta: float, game_time: float = 0.0
    ) -> float:
        """Adjust NPC affinity with a tag by delta, return new value."""
        self._require_connection()
        cursor = self.connection.cursor()
        cursor.execute(
            "SELECT affinity_value FROM npc_affinity WHERE npc_id = ? AND tag = ?",
            (npc_id, tag),
        )
        row = cursor.fetchone()
        current = row[0] if row else 0.0
        new_value = max(-100.0, min(100.0, current + delta))
        return self.set_npc_affinity(npc_id, tag, new_value, game_time)

    def get_npc_affinity(self, npc_id: str, tag: str) -> float:
        """Get NPC affinity with a tag (default 0)."""
        self._require_connection()
        cursor = self.connection.cursor()
        cursor.execute(
            "SELECT affinity_value FROM npc_affinity WHERE npc_id = ? AND tag = ?",
            (npc_id, tag),
        )
        row = cursor.fetchone()
        return row[0] if row else 0.0

    # NPC personal opinion of the player — stored in npc_affinity under the
    # reserved NPC_AFFINITY_PLAYER_TAG.

    def set_npc_affinity_toward_player(
        self, npc_id: str, value: float, game_time: float = 0.0
    ) -> float:
        return self.set_npc_affinity(npc_id, NPC_AFFINITY_PLAYER_TAG, value, game_time)

    def adjust_npc_affinity_toward_player(
        self, npc_id: str, delta: float, game_time: float = 0.0
    ) -> float:
        return self.adjust_npc_affinity(npc_id, NPC_AFFINITY_PLAYER_TAG, delta, game_time)

    def get_npc_affinity_toward_player(self, npc_id: str) -> float:
        return self.get_npc_affinity(npc_id, NPC_AFFINITY_PLAYER_TAG)

    # ------------------------------------------------------------------
    # Location affinity defaults
    # ------------------------------------------------------------------

    def get_location_affinity_defaults(
        self, address_tier: str, location_id: Optional[str]
    ) -> Dict[str, float]:
        """Get all affinity defaults for a single location (tag → -100..100)."""
        self._require_connection()
        cursor = self.connection.cursor()
        cursor.execute(
            "SELECT tag, affinity_value FROM location_affinity_defaults "
            "WHERE address_tier = ? AND location_id IS ?",
            (address_tier, location_id),
        )
        return {row[0]: row[1] for row in cursor.fetchall()}

    def compute_inherited_affinity(
        self, address_hierarchy: List[Tuple[str, Optional[str]]]
    ) -> Dict[str, float]:
        """Sum location affinity defaults along an address hierarchy.

        Args:
            address_hierarchy: (tier, location_id) tuples in any order.
                Example: [("locality", "village_westhollow"),
                          ("district", "grain_fields"),
                          ("nation", "nation:stormguard"),
                          ("world", None)]

        Returns:
            Accumulated affinity dict (tag → -100..100, summed and clamped).
        """
        self._require_connection()
        accumulated: Dict[str, float] = {}
        for tier, location_id in address_hierarchy:
            for tag, value in self.get_location_affinity_defaults(tier, location_id).items():
                accumulated[tag] = accumulated.get(tag, 0.0) + value

        for tag, value in accumulated.items():
            accumulated[tag] = max(-100.0, min(100.0, value))
        return accumulated

    # ------------------------------------------------------------------
    # NPC dynamic state — runtime mutables (v3+).
    # Source of truth for current_emotion, last_interaction_time,
    # interaction_count, conversation_summary, knowledge, reputation tags,
    # quest_state. NOT relationship_score — that lives in npc_affinity
    # under NPC_AFFINITY_PLAYER_TAG.
    # ------------------------------------------------------------------

    def get_npc_dynamic_state(self, npc_id: str) -> Optional[Dict]:
        """Return the dynamic state row for an NPC, or None if no row exists.

        Returns a dict with deserialized JSON columns (knowledge, reputation_tags,
        quest_state become Python lists/dict).
        """
        self._require_connection()
        cursor = self.connection.cursor()
        cursor.execute(
            "SELECT npc_id, current_emotion, last_interaction_time, "
            "interaction_count, conversation_summary, knowledge_json, "
            "reputation_tags_json, quest_state_json, last_updated "
            "FROM npc_dynamic_state WHERE npc_id = ?",
            (npc_id,),
        )
        row = cursor.fetchone()
        if not row:
            return None
        return {
            "npc_id": row["npc_id"],
            "current_emotion": row["current_emotion"],
            "last_interaction_time": row["last_interaction_time"],
            "interaction_count": row["interaction_count"],
            "conversation_summary": row["conversation_summary"],
            "knowledge": json.loads(row["knowledge_json"] or "[]"),
            "reputation_tags": json.loads(row["reputation_tags_json"] or "[]"),
            "quest_state": json.loads(row["quest_state_json"] or "{}"),
            "last_updated": row["last_updated"],
        }

    def upsert_npc_dynamic_state(
        self,
        npc_id: str,
        *,
        current_emotion: Optional[str] = None,
        last_interaction_time: Optional[float] = None,
        interaction_count: Optional[int] = None,
        conversation_summary: Optional[str] = None,
        knowledge: Optional[List[str]] = None,
        reputation_tags: Optional[List[str]] = None,
        quest_state: Optional[Dict[str, str]] = None,
        game_time: float = 0.0,
    ) -> None:
        """Insert or update an NPC's dynamic state row.

        Only provided fields are updated; omitted fields keep their existing
        values (or defaults if the row is being created).
        """
        self._require_connection()
        cursor = self.connection.cursor()

        existing = self.get_npc_dynamic_state(npc_id)
        merged = {
            "current_emotion": current_emotion if current_emotion is not None
                else (existing["current_emotion"] if existing else "neutral"),
            "last_interaction_time": last_interaction_time if last_interaction_time is not None
                else (existing["last_interaction_time"] if existing else 0.0),
            "interaction_count": interaction_count if interaction_count is not None
                else (existing["interaction_count"] if existing else 0),
            "conversation_summary": conversation_summary if conversation_summary is not None
                else (existing["conversation_summary"] if existing else ""),
            "knowledge": knowledge if knowledge is not None
                else (existing["knowledge"] if existing else []),
            "reputation_tags": reputation_tags if reputation_tags is not None
                else (existing["reputation_tags"] if existing else []),
            "quest_state": quest_state if quest_state is not None
                else (existing["quest_state"] if existing else {}),
        }

        cursor.execute(
            "INSERT OR REPLACE INTO npc_dynamic_state "
            "(npc_id, current_emotion, last_interaction_time, "
            "interaction_count, conversation_summary, knowledge_json, "
            "reputation_tags_json, quest_state_json, last_updated) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                npc_id,
                merged["current_emotion"],
                merged["last_interaction_time"],
                merged["interaction_count"],
                merged["conversation_summary"],
                json.dumps(merged["knowledge"]),
                json.dumps(merged["reputation_tags"]),
                json.dumps(merged["quest_state"]),
                game_time,
            ),
        )
        self.connection.commit()

    # ------------------------------------------------------------------
    # NPC dialogue log — append-only, capped per NPC.
    # ------------------------------------------------------------------

    def append_dialogue_log(
        self,
        npc_id: str,
        timestamp: float,
        speaker: str,
        utterance: str,
        emotion_at_time: Optional[str] = None,
        max_rows: Optional[int] = None,
    ) -> int:
        """Append a single dialogue line. Returns the inserted row id.

        If max_rows is provided and the NPC's log exceeds it, oldest rows
        are pruned. Default cap from schema.DEFAULT_DIALOGUE_LOG_MAX_ROWS.
        """
        from .schema import DEFAULT_DIALOGUE_LOG_MAX_ROWS

        if speaker not in ("player", "npc"):
            raise ValueError(f"speaker must be 'player' or 'npc', got {speaker!r}")
        self._require_connection()
        cursor = self.connection.cursor()
        cursor.execute(
            "INSERT INTO npc_dialogue_log "
            "(npc_id, timestamp, speaker, utterance, emotion_at_time) "
            "VALUES (?, ?, ?, ?, ?)",
            (npc_id, timestamp, speaker, utterance, emotion_at_time),
        )
        row_id = cursor.lastrowid
        self.connection.commit()

        cap = max_rows if max_rows is not None else DEFAULT_DIALOGUE_LOG_MAX_ROWS
        self.prune_dialogue_log(npc_id, max_rows=cap)
        return row_id

    def get_dialogue_log(
        self, npc_id: str, limit: int = 50, oldest_first: bool = False
    ) -> List[Dict]:
        """Return up to `limit` dialogue entries for an NPC. Newest first by default."""
        self._require_connection()
        cursor = self.connection.cursor()
        order = "ASC" if oldest_first else "DESC"
        cursor.execute(
            f"SELECT id, timestamp, speaker, utterance, emotion_at_time "
            f"FROM npc_dialogue_log WHERE npc_id = ? "
            f"ORDER BY timestamp {order}, id {order} LIMIT ?",
            (npc_id, limit),
        )
        return [
            {
                "id": row["id"],
                "timestamp": row["timestamp"],
                "speaker": row["speaker"],
                "utterance": row["utterance"],
                "emotion_at_time": row["emotion_at_time"],
            }
            for row in cursor.fetchall()
        ]

    def prune_dialogue_log(self, npc_id: str, max_rows: int) -> int:
        """Trim dialogue log for an NPC to at most `max_rows` newest entries.

        Returns the number of rows deleted.
        """
        if max_rows <= 0:
            return 0
        self._require_connection()
        cursor = self.connection.cursor()
        cursor.execute(
            "SELECT COUNT(*) FROM npc_dialogue_log WHERE npc_id = ?",
            (npc_id,),
        )
        total = cursor.fetchone()[0]
        if total <= max_rows:
            return 0
        excess = total - max_rows
        cursor.execute(
            "DELETE FROM npc_dialogue_log "
            "WHERE id IN (SELECT id FROM npc_dialogue_log "
            "WHERE npc_id = ? ORDER BY timestamp ASC, id ASC LIMIT ?)",
            (npc_id, excess),
        )
        self.connection.commit()
        return excess

    # ------------------------------------------------------------------
    # NPC birth-time helpers — write affinity_seeds from a v3 NPCDefinition.
    # ------------------------------------------------------------------

    def seed_npc_affinity(
        self,
        npc_id: str,
        affinity_seeds: Dict[str, int],
        game_time: float = 0.0,
        overwrite: bool = False,
    ) -> int:
        """Write initial affinity values into npc_affinity at NPC birth.

        Args:
            npc_id: target NPC id (must exist in npc_profiles).
            affinity_seeds: dict of tag -> int in [-100, 100]. The reserved
                tag '_player' represents the NPC's starting opinion of the
                player (per NPC_AFFINITY_PLAYER_TAG).
            game_time: timestamp for last_updated.
            overwrite: if False (default), only writes seeds for tags that
                don't already have a value. If True, replaces existing values.

        Returns the number of rows written.
        """
        self._require_connection()
        written = 0
        for tag, value in affinity_seeds.items():
            value_clamped = max(-100.0, min(100.0, float(value)))
            if not overwrite:
                existing = self.get_npc_affinity(npc_id, tag)
                if existing != 0.0:
                    continue
            self.set_npc_affinity(npc_id, tag, value_clamped, game_time)
            written += 1
        return written

    # ------------------------------------------------------------------
    # Save / load — SQLite persists independently; these are placeholders
    # for the save manager contract.
    # ------------------------------------------------------------------

    def save(self) -> Dict:
        return {
            "version": FactionDatabaseSchema.get_schema_version(self.connection)
            if self.connection else 0,
            "db_path": str(self.db_path),
            "initialized": self._initialized,
        }

    def load(self, data: Dict) -> None:
        # SQLite file is authoritative; nothing to restore from the save blob.
        pass

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _require_connection(self) -> None:
        if not self.connection:
            raise RuntimeError("FactionSystem not initialized — call initialize() first")

    def _publish_affinity_changed(
        self,
        *,
        player_id: str,
        tag: str,
        delta: float,
        new_value: float,
        source: str,
    ) -> None:
        """Publish FACTION_AFFINITY_CHANGED. WMS evaluator listens for this.

        Best-effort: never raises — a broken event bus must not break affinity
        recording.
        """
        try:
            get_event_bus().publish(
                FACTION_AFFINITY_CHANGED,
                {
                    "player_id": player_id,
                    "tag": tag,
                    "delta": delta,
                    "new_value": new_value,
                    "source": source,
                },
                source="FactionSystem",
            )
        except Exception as e:
            print(f"[FactionSystem] Event publish failed ({e}); continuing")

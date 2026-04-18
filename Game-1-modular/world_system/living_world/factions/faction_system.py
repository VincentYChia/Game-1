"""Faction System Database Manager — Phase 2+.

Singleton manager for all faction data: NPC profiles, player affinity, NPC affinity toward player,
location defaults. Separate SQLite database (faction.db) from WMS.

Information flow (Recording):
- Game events (quests, combat) → quest/combat system provides affinity deltas
- Deltas → FactionSystem.adjust_player_affinity() → player_affinity table
- NPC personal opinion adjustments → FactionSystem.adjust_npc_affinity_toward_player()

Information flow (Retrieval — Dialogue Context):
- NPC dialogue requested → FactionSystem.get_npc_profile() + get_npc_affinity_toward_player()
- Player affinity with NPC's tags → get_all_player_affinities()
- Location affinity defaults → compute_inherited_affinity()
- Context assembled for LLM dialogue generation
"""

from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path
from typing import Dict, List, Optional, ClassVar

from core.paths import get_faction_db_path
from .models import NPCProfile, PlayerProfile, FactionTag, LocationAffinityDefault
from .schema import FactionDatabaseSchema, bootstrap_location_defaults


class FactionSystem:
    """Singleton manager for faction SQLite database."""

    _instance: ClassVar[Optional[FactionSystem]] = None

    def __init__(self):
        self.db_path = get_faction_db_path()
        self.connection: Optional[sqlite3.Connection] = None
        self._initialized = False

    @classmethod
    def get_instance(cls) -> FactionSystem:
        """Get or create singleton instance."""
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
        """Initialize database connection and schema."""
        if self._initialized:
            return

        try:
            self.connection = sqlite3.connect(
                str(self.db_path),
                check_same_thread=False
            )
            self.connection.row_factory = sqlite3.Row

            # Create schema
            FactionDatabaseSchema.create_all_tables(self.connection)

            # Bootstrap location affinity defaults
            bootstrap_location_defaults(self.connection)

            print(f"✓ Faction system initialized at {self.db_path}")
            self._initialized = True

        except Exception as e:
            print(f"✗ Error initializing faction system: {e}")
            raise

    # ========================================================================
    # NPC PROFILE OPERATIONS
    # ========================================================================

    def add_npc(self, npc_id: str, narrative: str, game_time: float = 0.0) -> None:
        """Add or update NPC profile."""
        if not self.connection:
            raise RuntimeError("Database not initialized")

        cursor = self.connection.cursor()
        cursor.execute(
            "INSERT OR REPLACE INTO npc_profiles (npc_id, narrative, created_at, last_updated) VALUES (?, ?, ?, ?)",
            (npc_id, narrative, game_time, game_time)
        )
        self.connection.commit()

    def get_npc_profile(self, npc_id: str) -> Optional[NPCProfile]:
        """Get NPC profile with belonging tags and affinity."""
        if not self.connection:
            raise RuntimeError("Database not initialized")

        cursor = self.connection.cursor()

        # Get NPC core
        cursor.execute("SELECT narrative, created_at, last_updated FROM npc_profiles WHERE npc_id = ?", (npc_id,))
        row = cursor.fetchone()
        if not row:
            return None

        profile = NPCProfile(
            npc_id=npc_id,
            narrative=row[0],
            created_at=row[1],
            last_updated=row[2]
        )

        # Get belonging tags
        cursor.execute("""
            SELECT tag, significance, role, narrative_hooks, since_game_time
            FROM npc_belonging_tags WHERE npc_id = ?
        """, (npc_id,))
        for tag_row in cursor.fetchall():
            hooks = json.loads(tag_row[3]) if tag_row[3] else []
            profile.add_tag(
                tag=tag_row[0],
                significance=tag_row[1],
                role=tag_row[2],
                narrative_hooks=hooks,
                game_time=tag_row[4]
            )

        # Get affinity
        cursor.execute("SELECT tag, affinity_value FROM npc_affinity WHERE npc_id = ?", (npc_id,))
        for aff_row in cursor.fetchall():
            profile.set_affinity(aff_row[0], aff_row[1])

        return profile

    def add_npc_belonging_tag(self, npc_id: str, tag: str, significance: float,
                             role: Optional[str] = None, narrative_hooks: Optional[List[str]] = None,
                             game_time: float = 0.0) -> None:
        """Add or update NPC belonging tag."""
        if not self.connection:
            raise RuntimeError("Database not initialized")

        hooks_json = json.dumps(narrative_hooks or [])
        cursor = self.connection.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO npc_belonging_tags
            (npc_id, tag, significance, role, narrative_hooks, since_game_time)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (npc_id, tag, significance, role, hooks_json, game_time))
        self.connection.commit()

    def get_npc_belonging_tags(self, npc_id: str) -> List[FactionTag]:
        """Get all belonging tags for an NPC."""
        if not self.connection:
            raise RuntimeError("Database not initialized")

        cursor = self.connection.cursor()
        cursor.execute("""
            SELECT tag, significance, role, narrative_hooks, since_game_time
            FROM npc_belonging_tags WHERE npc_id = ?
        """, (npc_id,))

        tags = []
        for row in cursor.fetchall():
            hooks = json.loads(row[3]) if row[3] else []
            tags.append(FactionTag(
                tag=row[0],
                significance=row[1],
                role=row[2],
                narrative_hooks=hooks,
                since_game_time=row[4]
            ))
        return tags

    def get_all_npcs_with_tag(self, tag: str) -> List[str]:
        """Get all NPC IDs that have a specific belonging tag."""
        if not self.connection:
            raise RuntimeError("Database not initialized")

        cursor = self.connection.cursor()
        cursor.execute("SELECT DISTINCT npc_id FROM npc_belonging_tags WHERE tag = ?", (tag,))
        return [row[0] for row in cursor.fetchall()]

    # ========================================================================
    # AFFINITY OPERATIONS
    # ========================================================================

    def set_player_affinity(self, player_id: str, tag: str, value: float, game_time: float = 0.0) -> None:
        """Set player affinity with tag (-100 to 100)."""
        if not self.connection:
            raise RuntimeError("Database not initialized")

        clamped = max(-100.0, min(100.0, value))
        cursor = self.connection.cursor()
        cursor.execute(
            "INSERT OR REPLACE INTO player_affinity (player_id, tag, affinity_value, last_updated) VALUES (?, ?, ?, ?)",
            (player_id, tag, clamped, game_time)
        )
        self.connection.commit()

    def adjust_player_affinity(self, player_id: str, tag: str, delta: float, game_time: float = 0.0) -> float:
        """Adjust player affinity by delta, return new value."""
        if not self.connection:
            raise RuntimeError("Database not initialized")

        cursor = self.connection.cursor()
        cursor.execute("SELECT affinity_value FROM player_affinity WHERE player_id = ? AND tag = ?",
                      (player_id, tag))
        row = cursor.fetchone()
        current = row[0] if row else 0.0
        new_value = max(-100.0, min(100.0, current + delta))
        self.set_player_affinity(player_id, tag, new_value, game_time)
        return new_value

    def get_player_affinity(self, player_id: str, tag: str) -> float:
        """Get player affinity with tag (default 0)."""
        if not self.connection:
            raise RuntimeError("Database not initialized")

        cursor = self.connection.cursor()
        cursor.execute("SELECT affinity_value FROM player_affinity WHERE player_id = ? AND tag = ?",
                      (player_id, tag))
        row = cursor.fetchone()
        return row[0] if row else 0.0

    def get_all_player_affinities(self, player_id: str) -> Dict[str, float]:
        """Get all affinity values for a player (tag → affinity)."""
        if not self.connection:
            raise RuntimeError("Database not initialized")

        cursor = self.connection.cursor()
        cursor.execute("SELECT tag, affinity_value FROM player_affinity WHERE player_id = ?", (player_id,))
        return {row[0]: row[1] for row in cursor.fetchall()}

    def set_npc_affinity(self, npc_id: str, tag: str, value: float, game_time: float = 0.0) -> None:
        """Set NPC affinity with tag (-100 to 100)."""
        if not self.connection:
            raise RuntimeError("Database not initialized")

        clamped = max(-100.0, min(100.0, value))
        cursor = self.connection.cursor()
        cursor.execute(
            "INSERT OR REPLACE INTO npc_affinity (npc_id, tag, affinity_value, last_updated) VALUES (?, ?, ?, ?)",
            (npc_id, tag, clamped, game_time)
        )
        self.connection.commit()

    def get_npc_affinity(self, npc_id: str, tag: str) -> float:
        """Get NPC affinity with tag (default 0)."""
        if not self.connection:
            raise RuntimeError("Database not initialized")

        cursor = self.connection.cursor()
        cursor.execute("SELECT affinity_value FROM npc_affinity WHERE npc_id = ? AND tag = ?",
                      (npc_id, tag))
        row = cursor.fetchone()
        return row[0] if row else 0.0

    def set_npc_affinity_toward_player(self, npc_id: str, value: float, game_time: float = 0.0) -> None:
        """Set NPC personal affinity toward player (-100 to 100)."""
        if not self.connection:
            raise RuntimeError("Database not initialized")

        clamped = max(-100.0, min(100.0, value))
        cursor = self.connection.cursor()
        cursor.execute(
            "INSERT OR REPLACE INTO npc_affinity_toward_player (npc_id, affinity, last_updated) VALUES (?, ?, ?)",
            (npc_id, clamped, game_time)
        )
        self.connection.commit()

    def adjust_npc_affinity_toward_player(self, npc_id: str, delta: float, game_time: float = 0.0) -> float:
        """Adjust NPC affinity toward player by delta, return new value."""
        if not self.connection:
            raise RuntimeError("Database not initialized")

        cursor = self.connection.cursor()
        cursor.execute("SELECT affinity FROM npc_affinity_toward_player WHERE npc_id = ?", (npc_id,))
        row = cursor.fetchone()
        current = row[0] if row else 0.0
        new_value = max(-100.0, min(100.0, current + delta))
        self.set_npc_affinity_toward_player(npc_id, new_value, game_time)
        return new_value

    def get_npc_affinity_toward_player(self, npc_id: str) -> float:
        """Get NPC personal affinity toward player (default 0)."""
        if not self.connection:
            raise RuntimeError("Database not initialized")

        cursor = self.connection.cursor()
        cursor.execute("SELECT affinity FROM npc_affinity_toward_player WHERE npc_id = ?", (npc_id,))
        row = cursor.fetchone()
        return row[0] if row else 0.0

    # ========================================================================
    # LOCATION AFFINITY OPERATIONS
    # ========================================================================

    def get_location_affinity_defaults(self, address_tier: str, location_id: Optional[str]) -> Dict[str, float]:
        """Get all affinity defaults for a location (tag → affinity, -100 to 100)."""
        if not self.connection:
            raise RuntimeError("Database not initialized")

        cursor = self.connection.cursor()
        cursor.execute(
            "SELECT tag, affinity FROM location_affinity_defaults WHERE address_tier = ? AND location_id = ?",
            (address_tier, location_id)
        )
        return {row[0]: row[1] for row in cursor.fetchall()}

    def compute_inherited_affinity(self, address_hierarchy: List[Tuple[str, Optional[str]]]) -> Dict[str, float]:
        """Compute accumulated affinity defaults by walking up address hierarchy.

        Args:
            address_hierarchy: List of (tier, location_id) tuples from finest to coarsest.
            Example: [("locality", "village_westhollow"), ("district", "grain_fields"), ...]

        Returns:
            Accumulated affinity dict (tag → affinity, -100 to 100, summed across hierarchy).
        """
        if not self.connection:
            raise RuntimeError("Database not initialized")

        accumulated = {}
        for tier, location_id in address_hierarchy:
            tier_defaults = self.get_location_affinity_defaults(tier, location_id)
            for tag, affinity in tier_defaults.items():
                # Additive: sum all defaults along the hierarchy
                accumulated[tag] = accumulated.get(tag, 0.0) + affinity

        return accumulated

    # ========================================================================
    # SAVE/LOAD
    # ========================================================================

    def save(self) -> Dict:
        """Prepare faction state for saving. Database persists independently."""
        return {
            "version": 1,
            "db_path": str(self.db_path),
            "initialized": self._initialized
        }

    def load(self, data: Dict) -> None:
        """Restore faction state from save. Database connection persists."""
        # Database already open; no action needed.
        pass

"""Faction System Database Manager - Singleton for all faction data persistence.

Handles all SQLite operations for NPC profiles, player affinity, and defaults.
Separate database from WMS (faction.db in save directory).

Pattern: Singleton, follows WMS and database manager patterns.

Usage:
    db = FactionDatabase.get_instance()
    db.initialize()

    npc = db.get_npc_profile("npc_1")
    db.add_player_affinity_delta("player_1", "guild:merchants", 5.0)
"""

from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path
from typing import Dict, List, Optional, ClassVar, Tuple

from .models import (
    NPCFactionProfile, NPCBelongingTag, PlayerAffinityProfile,
    AffinityDefaultEntry, CulturalAffinityEntry, QuestLogEntry, NPCContextForDialogue
)
from .schema import FactionDatabaseSchema, BOOTSTRAP_AFFINITY_DEFAULTS_SQL
from core.paths import get_faction_db_path


class FactionDatabase:
    """Singleton manager for faction system SQLite database."""

    _instance: ClassVar[Optional[FactionDatabase]] = None
    _initialized: bool = False

    def __init__(self):
        self.db_path = get_faction_db_path()
        self.connection: Optional[sqlite3.Connection] = None
        self._initialized = False

    @classmethod
    def get_instance(cls) -> FactionDatabase:
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
        """Initialize database connection and create schema if needed."""
        if self._initialized:
            return

        try:
            # Create connection
            self.connection = sqlite3.connect(
                str(self.db_path),
                check_same_thread=False  # Allow use from multiple threads
            )
            self.connection.row_factory = sqlite3.Row  # Access columns by name

            # Create schema
            FactionDatabaseSchema.create_all_tables(self.connection)

            # Seed bootstrap data if affinity_defaults is empty
            self._seed_bootstrap_data()

            print(f"✓ Faction database initialized at {self.db_path}")
            self._initialized = True

        except Exception as e:
            print(f"✗ Error initializing faction database: {e}")
            raise

    def _seed_bootstrap_data(self) -> None:
        """Seed affinity_defaults with bootstrap data if empty."""
        if not self.connection:
            return

        cursor = self.connection.cursor()
        cursor.execute("SELECT COUNT(*) FROM affinity_defaults")
        count = cursor.fetchone()[0]

        if count == 0:
            try:
                cursor.executescript(BOOTSTRAP_AFFINITY_DEFAULTS_SQL)
                self.connection.commit()
                print("✓ Seeded affinity_defaults with bootstrap data")
            except Exception as e:
                print(f"⚠ Warning: Could not seed bootstrap data: {e}")
                self.connection.rollback()

    # ========================================================================
    # NPC PROFILE OPERATIONS
    # ========================================================================

    def create_npc_profile(self, npc_id: str, location_id: str, narrative: str,
                          primary_tag: str, metadata: Optional[Dict] = None) -> NPCFactionProfile:
        """Create a new NPC profile.

        Args:
            npc_id: Unique NPC identifier
            location_id: Where the NPC is located
            narrative: Full background narrative
            primary_tag: Main identity tag
            metadata: Optional JSON metadata (archetype, etc.)

        Returns:
            Created NPCFactionProfile
        """
        if not self.connection:
            raise RuntimeError("Database not initialized")

        current_time = time.time()
        metadata_json = json.dumps(metadata or {})

        cursor = self.connection.cursor()
        try:
            cursor.execute("""
                INSERT INTO npc_profiles
                (npc_id, location_id, narrative, primary_tag, created_at, last_updated, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (npc_id, location_id, narrative, primary_tag, current_time, current_time, metadata_json))
            self.connection.commit()

            return NPCFactionProfile(
                npc_id=npc_id,
                location_id=location_id,
                narrative=narrative,
                primary_tag=primary_tag,
                created_at=current_time,
                last_updated=current_time,
                metadata=metadata or {}
            )
        except sqlite3.IntegrityError:
            raise ValueError(f"NPC {npc_id} already exists")

    def get_npc_profile(self, npc_id: str) -> Optional[NPCFactionProfile]:
        """Get an NPC profile by ID."""
        if not self.connection:
            return None

        cursor = self.connection.cursor()
        cursor.execute("""
            SELECT npc_id, location_id, narrative, primary_tag, created_at, last_updated, metadata
            FROM npc_profiles
            WHERE npc_id = ?
        """, (npc_id,))

        row = cursor.fetchone()
        if not row:
            return None

        metadata = json.loads(row[6] or '{}')
        return NPCFactionProfile(
            npc_id=row[0],
            location_id=row[1],
            narrative=row[2],
            primary_tag=row[3],
            created_at=row[4],
            last_updated=row[5],
            metadata=metadata
        )

    def update_npc_narrative(self, npc_id: str, new_narrative: str) -> bool:
        """Update NPC narrative (for evolution after events)."""
        if not self.connection:
            return False

        cursor = self.connection.cursor()
        current_time = time.time()
        cursor.execute("""
            UPDATE npc_profiles
            SET narrative = ?, last_updated = ?
            WHERE npc_id = ?
        """, (new_narrative, current_time, npc_id))
        self.connection.commit()
        return cursor.rowcount > 0

    def add_npc_belonging_tag(self, npc_id: str, tag: str, significance: float,
                             role: Optional[str] = None,
                             narrative_hooks: Optional[List[str]] = None) -> bool:
        """Add a belonging tag to an NPC.

        Args:
            npc_id: NPC identifier
            tag: Tag name
            significance: -100 to +100 or bucket name
            role: Optional role (member, elder, etc.)
            narrative_hooks: List of 3+ explanation strings

        Returns:
            True if added, False if already exists
        """
        if not self.connection:
            return False

        hooks_json = json.dumps(narrative_hooks or [])

        cursor = self.connection.cursor()
        try:
            cursor.execute("""
                INSERT INTO npc_belonging
                (npc_id, tag, significance, role, narrative_hooks)
                VALUES (?, ?, ?, ?, ?)
            """, (npc_id, tag, significance, role, hooks_json))
            self.connection.commit()
            return True
        except sqlite3.IntegrityError:
            # Tag already exists for this NPC, could update instead
            return False

    def get_npc_belonging_tags(self, npc_id: str) -> List[NPCBelongingTag]:
        """Get all belonging tags for an NPC."""
        if not self.connection:
            return []

        cursor = self.connection.cursor()
        cursor.execute("""
            SELECT tag, significance, role, narrative_hooks
            FROM npc_belonging
            WHERE npc_id = ?
        """, (npc_id,))

        tags = []
        for row in cursor.fetchall():
            hooks = json.loads(row[3] or '[]')
            tags.append(NPCBelongingTag(
                tag=row[0],
                significance=row[1],
                role=row[2],
                narrative_hooks=hooks
            ))
        return tags

    def get_all_npcs_with_tag(self, tag: str) -> List[str]:
        """Get all NPC IDs that have a specific tag."""
        if not self.connection:
            return []

        cursor = self.connection.cursor()
        cursor.execute("""
            SELECT DISTINCT npc_id
            FROM npc_belonging
            WHERE tag = ?
        """, (tag,))

        return [row[0] for row in cursor.fetchall()]

    def get_all_npcs_in_location(self, location_id: str) -> List[str]:
        """Get all NPCs at a specific location."""
        if not self.connection:
            return []

        cursor = self.connection.cursor()
        cursor.execute("""
            SELECT npc_id
            FROM npc_profiles
            WHERE location_id = ?
        """, (location_id,))

        return [row[0] for row in cursor.fetchall()]

    # ========================================================================
    # PLAYER AFFINITY OPERATIONS
    # ========================================================================

    def initialize_player_affinity(self, player_id: str) -> PlayerAffinityProfile:
        """Load or initialize player affinity profile.

        Reads all existing affinity values from the database, or returns
        an empty profile if no affinity exists yet.
        """
        if not self.connection:
            raise RuntimeError("Database not initialized")

        affinity = self.get_all_player_affinities(player_id)
        return PlayerAffinityProfile(player_id=player_id, affinity=affinity)

    def get_player_affinity(self, player_id: str, tag: str) -> float:
        """Get player's current affinity with a tag (default 0)."""
        if not self.connection:
            return 0.0

        cursor = self.connection.cursor()
        cursor.execute("""
            SELECT current_value
            FROM player_affinity
            WHERE player_id = ? AND tag = ?
        """, (player_id, tag))

        row = cursor.fetchone()
        return row[0] if row else 0.0

    def get_all_player_affinities(self, player_id: str) -> Dict[str, float]:
        """Get all player affinity values."""
        if not self.connection:
            return {}

        cursor = self.connection.cursor()
        cursor.execute("""
            SELECT tag, current_value
            FROM player_affinity
            WHERE player_id = ?
        """, (player_id,))

        return {row[0]: row[1] for row in cursor.fetchall()}

    def add_player_affinity_delta(self, player_id: str, tag: str, delta: float) -> float:
        """Apply affinity delta to player (additive, not replacement).

        Args:
            player_id: Player ID
            tag: Tag to modify
            delta: Amount to add (can be negative)

        Returns:
            New affinity value (clamped to -100 to 100)

        Note: Uses BEGIN IMMEDIATE for atomicity across concurrent writes.
        """
        if not self.connection:
            raise RuntimeError("Database not initialized")

        current_time = time.time()
        cursor = self.connection.cursor()

        try:
            # Begin immediate transaction to prevent concurrent writes
            cursor.execute("BEGIN IMMEDIATE")

            # Read current value atomically
            cursor.execute("""
                SELECT current_value, total_gained FROM player_affinity
                WHERE player_id = ? AND tag = ?
            """, (player_id, tag))
            row = cursor.fetchone()

            if row:
                # Update existing row
                current_value = row[0]
                current_total_gained = row[1]
            else:
                # New row
                current_value = 0.0
                current_total_gained = 0.0

            new_value = max(-100.0, min(100.0, current_value + delta))
            new_total_gained = current_total_gained + max(0.0, delta)

            # Atomic insert or replace
            cursor.execute("""
                INSERT OR REPLACE INTO player_affinity
                (player_id, tag, current_value, total_gained, updated_at)
                VALUES (?, ?, ?, ?, ?)
            """, (player_id, tag, new_value, new_total_gained, current_time))

            self.connection.commit()
            return new_value

        except Exception as e:
            self.connection.rollback()
            raise RuntimeError(f"Error applying affinity delta: {e}")

    def get_player_total_gained(self, player_id: str, tag: str) -> float:
        """Get total positive affinity gained for a tag (for tracking)."""
        if not self.connection:
            return 0.0

        cursor = self.connection.cursor()
        cursor.execute("""
            SELECT total_gained
            FROM player_affinity
            WHERE player_id = ? AND tag = ?
        """, (player_id, tag))

        row = cursor.fetchone()
        return row[0] if row else 0.0

    # ========================================================================
    # CULTURAL AFFINITY OPERATIONS
    # ========================================================================

    def calculate_cultural_affinity(self, tag: str, address_tiers: Dict[str, Optional[str]]) -> float:
        """Calculate NPC cultural affinity by summing all address tiers.

        Args:
            tag: Tag to calculate affinity for
            address_tiers: {tier → location_id or None}
                Example: {"nation": "nation:stormguard", "district": "district:iron_hills", ...}

        Returns:
            Sum of all affinity_defaults for this address and tag (-100 to +100)
        """
        if not self.connection:
            raise RuntimeError("Database not initialized")

        total_affinity = 0.0
        cursor = self.connection.cursor()

        # Sum affinity for each tier in the address
        for tier in ["world", "nation", "region", "province", "district", "locality"]:
            location_id = address_tiers.get(tier)

            if tier == "world":
                # World tier has NULL location_id
                cursor.execute("""
                    SELECT delta FROM affinity_defaults
                    WHERE tier = ? AND location_id IS NULL AND tag = ?
                """, (tier, tag))
            else:
                if location_id is None:
                    continue  # Skip if this tier doesn't apply to address

                cursor.execute("""
                    SELECT delta FROM affinity_defaults
                    WHERE tier = ? AND location_id = ? AND tag = ?
                """, (tier, location_id, tag))

            row = cursor.fetchone()
            if row:
                total_affinity += row[0]

        return max(-100.0, min(100.0, total_affinity))  # Clamp to range

    # ========================================================================
    # QUEST LOG OPERATIONS
    # ========================================================================

    def log_quest_offer(self, player_id: str, quest_id: str, npc_id: str) -> bool:
        """Log when an NPC offers a quest."""
        if not self.connection:
            return False

        cursor = self.connection.cursor()
        try:
            cursor.execute("""
                INSERT INTO quest_log
                (player_id, quest_id, npc_id, status, offered_at)
                VALUES (?, ?, ?, ?, ?)
            """, (player_id, quest_id, npc_id, "offered", time.time()))
            self.connection.commit()
            return True
        except sqlite3.IntegrityError:
            return False

    def log_quest_completion(self, player_id: str, quest_id: str, npc_id: str) -> bool:
        """Log when a quest is completed."""
        if not self.connection:
            return False

        cursor = self.connection.cursor()
        try:
            cursor.execute("""
                UPDATE quest_log
                SET status = ?, completed_at = ?
                WHERE player_id = ? AND quest_id = ?
            """, ("completed", time.time(), player_id, quest_id))
            self.connection.commit()
            return cursor.rowcount > 0
        except Exception as e:
            print(f"⚠ Error logging quest completion: {e}")
            return False

    def get_npc_quest_history(self, npc_id: str) -> List[QuestLogEntry]:
        """Get all quests involving a specific NPC."""
        if not self.connection:
            return []

        cursor = self.connection.cursor()
        cursor.execute("""
            SELECT player_id, quest_id, npc_id, status, offered_at, completed_at
            FROM quest_log
            WHERE npc_id = ?
            ORDER BY offered_at DESC
        """, (npc_id,))

        entries = []
        for row in cursor.fetchall():
            entries.append(QuestLogEntry(
                player_id=row[0],
                quest_id=row[1],
                npc_id=row[2],
                status=row[3],
                offered_at=row[4],
                completed_at=row[5]
            ))
        return entries

    # ========================================================================
    # CONTEXT ASSEMBLY (For LLM dialogue)
    # ========================================================================

    def build_npc_dialogue_context(self, player_id: str, npc_id: str,
                                  address_tiers: Dict[str, Optional[str]]) -> Optional[NPCContextForDialogue]:
        """Assemble all context for NPC dialogue generation.

        Args:
            player_id: Player identifier
            npc_id: NPC identifier
            address_tiers: NPC's location address tiers

        Returns:
            NPCContextForDialogue or None if NPC not found
        """
        if not self.connection:
            return None

        # Get NPC profile
        npc_profile = self.get_npc_profile(npc_id)
        if not npc_profile:
            return None

        # Get NPC belonging tags
        npc_tags = self.get_npc_belonging_tags(npc_id)

        # Calculate NPC cultural affinity for all tags (tag → affinity)
        npc_cultural_affinity = {}
        for tag in self.get_all_tags():
            npc_cultural_affinity[tag] = self.calculate_cultural_affinity(tag, address_tiers)

        # Get player affinity
        player_affinity_dict = self.get_all_player_affinities(player_id)

        # Get quest history
        quest_history = self.get_npc_quest_history(npc_id)

        return NPCContextForDialogue(
            npc_id=npc_id,
            npc_narrative=npc_profile.narrative,
            npc_primary_tag=npc_profile.primary_tag,
            npc_belonging_tags=npc_tags,
            npc_cultural_affinity=npc_cultural_affinity,
            player_id=player_id,
            player_affinity=player_affinity_dict,
            quest_history=quest_history,
            location_id=npc_profile.location_id
        )

    # ========================================================================
    # UTILITY OPERATIONS
    # ========================================================================

    def get_all_tags(self) -> List[str]:
        """Get all unique tags in the system from all sources."""
        if not self.connection:
            return []

        cursor = self.connection.cursor()
        cursor.execute("""
            SELECT DISTINCT tag FROM affinity_defaults
            UNION
            SELECT DISTINCT tag FROM npc_belonging
            UNION
            SELECT DISTINCT tag FROM player_affinity
            ORDER BY tag
        """)

        return [row[0] for row in cursor.fetchall()]

    def close(self) -> None:
        """Close database connection."""
        if self.connection:
            self.connection.close()
            self.connection = None
            self._initialized = False

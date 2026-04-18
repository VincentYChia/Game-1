"""Faction System SQLite Schema — Phase 2+.

Defines all tables for NPC profiles, player affinity, location affinity defaults.
Sparse storage: only non-zero values stored.

Corrected model:
- NPC: narrative + belonging_tags (tag + significance 0-1) + affinity (tag → -100 to 100)
- Player: affinity (tag → -100 to 100)
- Location: cultural_affinity_defaults (tag → significance 0-1, hierarchical)
"""

from __future__ import annotations
import sqlite3
import time
from typing import Optional, Dict, List

FACTION_SCHEMA_VERSION = 2


class FactionDatabaseSchema:
    """Schema definitions for faction system SQLite database."""

    # NPC PROFILES: Core NPC data
    CREATE_NPC_PROFILES = """
    CREATE TABLE IF NOT EXISTS npc_profiles (
        npc_id TEXT PRIMARY KEY,
        narrative TEXT NOT NULL,
        created_at REAL NOT NULL,
        last_updated REAL NOT NULL
    );
    """

    # NPC BELONGING TAGS: Which tags define each NPC (sparse: only non-zero significance)
    CREATE_NPC_BELONGING_TAGS = """
    CREATE TABLE IF NOT EXISTS npc_belonging_tags (
        npc_id TEXT NOT NULL,
        tag TEXT NOT NULL,
        significance REAL NOT NULL CHECK(significance >= 0 AND significance <= 1),
        role TEXT,
        narrative_hooks TEXT,
        since_game_time REAL NOT NULL,
        PRIMARY KEY (npc_id, tag),
        FOREIGN KEY (npc_id) REFERENCES npc_profiles(npc_id) ON DELETE CASCADE
    );
    """

    CREATE_NPC_BELONGING_TAGS_INDEX = """
    CREATE INDEX IF NOT EXISTS idx_npc_belonging_tags_tag ON npc_belonging_tags(tag);
    """

    # NPC AFFINITY: How NPCs feel about tags (-100 to 100, sparse)
    CREATE_NPC_AFFINITY = """
    CREATE TABLE IF NOT EXISTS npc_affinity (
        npc_id TEXT NOT NULL,
        tag TEXT NOT NULL,
        affinity_value REAL NOT NULL CHECK(affinity_value >= -100 AND affinity_value <= 100),
        last_updated REAL NOT NULL,
        PRIMARY KEY (npc_id, tag),
        FOREIGN KEY (npc_id) REFERENCES npc_profiles(npc_id) ON DELETE CASCADE
    );
    """

    CREATE_NPC_AFFINITY_INDEX = """
    CREATE INDEX IF NOT EXISTS idx_npc_affinity_tag ON npc_affinity(tag);
    """

    # PLAYER AFFINITY: How player is perceived by each tag (-100 to 100, sparse)
    CREATE_PLAYER_AFFINITY = """
    CREATE TABLE IF NOT EXISTS player_affinity (
        player_id TEXT NOT NULL,
        tag TEXT NOT NULL,
        affinity_value REAL NOT NULL CHECK(affinity_value >= -100 AND affinity_value <= 100),
        last_updated REAL NOT NULL,
        PRIMARY KEY (player_id, tag)
    );
    """

    CREATE_PLAYER_AFFINITY_INDEX = """
    CREATE INDEX IF NOT EXISTS idx_player_affinity_tag ON player_affinity(player_id, tag);
    """

    # LOCATION AFFINITY DEFAULTS: Cultural baseline for each location + tag (sparse, 0-1)
    # Inherited: locality → district → region → nation → world
    CREATE_LOCATION_AFFINITY_DEFAULTS = """
    CREATE TABLE IF NOT EXISTS location_affinity_defaults (
        address_tier TEXT NOT NULL,
        location_id TEXT,
        tag TEXT NOT NULL,
        significance REAL NOT NULL CHECK(significance >= 0 AND significance <= 1),
        PRIMARY KEY (address_tier, location_id, tag)
    );
    """

    CREATE_LOCATION_AFFINITY_DEFAULTS_INDEX = """
    CREATE INDEX IF NOT EXISTS idx_location_affinity_defaults_tier_tag
    ON location_affinity_defaults(address_tier, tag);
    """

    # SCHEMA VERSION
    CREATE_SCHEMA_VERSION = """
    CREATE TABLE IF NOT EXISTS faction_schema_version (
        version INTEGER PRIMARY KEY,
        updated_at REAL NOT NULL
    );
    """

    @staticmethod
    def get_all_create_statements() -> List[str]:
        """Get all CREATE statements in dependency order."""
        return [
            FactionDatabaseSchema.CREATE_NPC_PROFILES,
            FactionDatabaseSchema.CREATE_NPC_BELONGING_TAGS,
            FactionDatabaseSchema.CREATE_NPC_BELONGING_TAGS_INDEX,
            FactionDatabaseSchema.CREATE_NPC_AFFINITY,
            FactionDatabaseSchema.CREATE_NPC_AFFINITY_INDEX,
            FactionDatabaseSchema.CREATE_PLAYER_AFFINITY,
            FactionDatabaseSchema.CREATE_PLAYER_AFFINITY_INDEX,
            FactionDatabaseSchema.CREATE_LOCATION_AFFINITY_DEFAULTS,
            FactionDatabaseSchema.CREATE_LOCATION_AFFINITY_DEFAULTS_INDEX,
            FactionDatabaseSchema.CREATE_SCHEMA_VERSION,
        ]

    @staticmethod
    def create_all_tables(connection: sqlite3.Connection) -> None:
        """Create all tables if they don't exist."""
        cursor = connection.cursor()
        try:
            for statement in FactionDatabaseSchema.get_all_create_statements():
                cursor.execute(statement)

            # Initialize version if not present
            cursor.execute("SELECT COUNT(*) FROM faction_schema_version")
            if cursor.fetchone()[0] == 0:
                cursor.execute(
                    "INSERT INTO faction_schema_version (version, updated_at) VALUES (?, ?)",
                    (FACTION_SCHEMA_VERSION, time.time())
                )

            connection.commit()
            print(f"✓ Faction schema initialized (version {FACTION_SCHEMA_VERSION})")
        except Exception as e:
            connection.rollback()
            print(f"✗ Error creating faction schema: {e}")
            raise

    @staticmethod
    def get_schema_version(connection: sqlite3.Connection) -> int:
        """Get current schema version."""
        cursor = connection.cursor()
        try:
            cursor.execute("SELECT MAX(version) FROM faction_schema_version")
            result = cursor.fetchone()
            return result[0] if result and result[0] else 0
        except:
            return 0

    @staticmethod
    def verify_schema(connection: sqlite3.Connection) -> tuple[bool, str]:
        """Verify schema is up to date. Returns (is_valid, message)."""
        version = FactionDatabaseSchema.get_schema_version(connection)
        if version == FACTION_SCHEMA_VERSION:
            return True, f"Schema version {version} is current"
        else:
            return False, f"Schema version {version}, expected {FACTION_SCHEMA_VERSION}"


# ============================================================================
# Placeholder: Location Affinity Defaults (to be generated LLM)
# ============================================================================
# These will be generated by LLM or loaded from JSON eventually.
# For now, using a minimal set to get the system working.

BOOTSTRAP_LOCATION_AFFINITY_DEFAULTS = [
    # World-level baseline defaults (minimal set)
    ("world", None, "guild:merchants", 0.3),
    ("world", None, "guild:smiths", 0.5),
    ("world", None, "profession:guard", 0.4),
    ("world", None, "profession:merchant", 0.3),
    ("world", None, "rank:commoner", 0.5),

    # Nation-level (stormguard: military-focused)
    ("nation", "nation:stormguard", "guild:smiths", 0.7),
    ("nation", "nation:stormguard", "profession:guard", 0.8),
    ("nation", "nation:stormguard", "profession:merchant", 0.2),

    # Nation-level (blackoak: trade-focused)
    ("nation", "nation:blackoak", "guild:merchants", 0.8),
    ("nation", "nation:blackoak", "profession:merchant", 0.8),
    ("nation", "nation:blackoak", "profession:guard", 0.3),

    # District-level (iron_hills: smithing)
    ("district", "district:iron_hills", "guild:smiths", 0.9),
    ("district", "district:iron_hills", "profession:blacksmith", 0.8),

    # District-level (coastal_reach: fishing/trade)
    ("district", "district:coastal_reach", "guild:fishers", 0.7),
    ("district", "district:coastal_reach", "guild:merchants", 0.6),
]


def bootstrap_location_defaults(connection: sqlite3.Connection) -> None:
    """Load bootstrap location affinity defaults. Called on init."""
    cursor = connection.cursor()
    for address_tier, location_id, tag, significance in BOOTSTRAP_LOCATION_AFFINITY_DEFAULTS:
        cursor.execute(
            """INSERT OR IGNORE INTO location_affinity_defaults
               (address_tier, location_id, tag, significance)
               VALUES (?, ?, ?, ?)""",
            (address_tier, location_id, tag, significance)
        )
    connection.commit()

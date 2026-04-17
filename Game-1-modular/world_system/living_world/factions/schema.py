"""Faction System SQLite Schema and Management.

Defines all table schemas and handles creation/versioning.
Separate database from WMS for clean separation of concerns.

Usage:
    schema = FactionDatabaseSchema()
    schema.create_all_tables(connection)
"""

from __future__ import annotations

from typing import List, Tuple

FACTION_SCHEMA_VERSION = 1


class FactionDatabaseSchema:
    """Schema definitions for faction system SQLite database."""

    # ========================================================================
    # TABLE: affinity_defaults
    # ========================================================================
    # Source of truth for cultural sentiment at each geographic tier.
    # Entries sum to create NPC cultural affinity.
    # Example: world + nation:stormguard + district:iron_hills affinities sum to NPC sentiment.

    CREATE_AFFINITY_DEFAULTS = """
    CREATE TABLE IF NOT EXISTS affinity_defaults (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        tier TEXT NOT NULL,              -- 'world', 'nation', 'region', 'province', 'district', 'locality'
        location_id TEXT,                -- NULL for world tier, else location identifier
        tag TEXT NOT NULL,               -- e.g., 'guild:merchants'
        delta REAL NOT NULL,             -- -100 to +100
        created_at REAL NOT NULL,
        updated_at REAL NOT NULL,
        UNIQUE(tier, location_id, tag)
    );
    """

    CREATE_AFFINITY_DEFAULTS_INDEX = """
    CREATE INDEX IF NOT EXISTS idx_affinity_defaults_tier_tag
    ON affinity_defaults(tier, tag);
    """

    # ========================================================================
    # TABLE: cultural_affinity_cache
    # ========================================================================
    # Pre-calculated cultural affinity for each tier/location/tag combination.
    # Updated when affinity_defaults change.
    # NPCs query this table, sum relevant rows for their address.

    CREATE_CULTURAL_AFFINITY_CACHE = """
    CREATE TABLE IF NOT EXISTS cultural_affinity_cache (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        tier TEXT NOT NULL,              -- 'world', 'nation', 'region', 'province', 'district', 'locality'
        location_id TEXT,                -- NULL for world tier
        tag TEXT NOT NULL,
        cultural_affinity REAL NOT NULL, -- -100 to +100
        calculated_at REAL NOT NULL,     -- When this was last calculated
        UNIQUE(tier, location_id, tag)
    );
    """

    CREATE_CULTURAL_AFFINITY_CACHE_INDEX = """
    CREATE INDEX IF NOT EXISTS idx_cultural_affinity_tier_loc
    ON cultural_affinity_cache(tier, location_id);
    """

    # ========================================================================
    # TABLE: npc_profiles (MAIN)
    # ========================================================================
    # Core NPC identity: narrative, location, timestamps.
    # Belonging tags stored separately in npc_belonging table.

    CREATE_NPC_PROFILES = """
    CREATE TABLE IF NOT EXISTS npc_profiles (
        npc_id TEXT PRIMARY KEY,
        location_id TEXT NOT NULL,       -- Where NPC is located (resolves to full address)
        narrative TEXT NOT NULL,         -- Full background narrative (can evolve)
        primary_tag TEXT NOT NULL,       -- Main identity tag
        created_at REAL NOT NULL,        -- Game time of creation
        last_updated REAL NOT NULL,      -- Game time of last narrative update
        metadata TEXT,                   -- JSON: archetype, personality, version, etc.
        UNIQUE(npc_id)
    );
    """

    CREATE_NPC_PROFILES_INDEX = """
    CREATE INDEX IF NOT EXISTS idx_npc_location
    ON npc_profiles(location_id);
    """

    # ========================================================================
    # TABLE: npc_belonging (NORMALIZED)
    # ========================================================================
    # Queryable NPC belonging tags.
    # Allows efficient "get all NPCs with guild:merchants" queries.

    CREATE_NPC_BELONGING = """
    CREATE TABLE IF NOT EXISTS npc_belonging (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        npc_id TEXT NOT NULL,
        tag TEXT NOT NULL,
        significance REAL NOT NULL,     -- -100 to +100 or bucket equivalent
        role TEXT,                       -- e.g., 'member', 'elder', 'initiate'
        narrative_hooks TEXT,            -- JSON: list of 3+ explanation strings
        UNIQUE(npc_id, tag),
        FOREIGN KEY(npc_id) REFERENCES npc_profiles(npc_id)
    );
    """

    CREATE_NPC_BELONGING_INDEX = """
    CREATE INDEX IF NOT EXISTS idx_npc_belonging_tag
    ON npc_belonging(tag);
    """

    # ========================================================================
    # TABLE: player_affinity (MAIN)
    # ========================================================================
    # Player's earned reputation with tags.
    # Additive: quest completion adds deltas, never replaces.

    CREATE_PLAYER_AFFINITY = """
    CREATE TABLE IF NOT EXISTS player_affinity (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        player_id TEXT NOT NULL,
        tag TEXT NOT NULL,
        current_value REAL NOT NULL,    -- -100 to +100
        total_gained REAL NOT NULL,     -- Sum of all positive deltas (for tracking)
        updated_at REAL NOT NULL,       -- Last time this was modified
        UNIQUE(player_id, tag)
    );
    """

    CREATE_PLAYER_AFFINITY_INDEX = """
    CREATE INDEX IF NOT EXISTS idx_player_affinity_tag
    ON player_affinity(player_id, tag);
    """

    # ========================================================================
    # TABLE: quest_log
    # ========================================================================
    # Track NPC-player quest interactions.
    # Used for dialogue context and NPC evolution.

    CREATE_QUEST_LOG = """
    CREATE TABLE IF NOT EXISTS quest_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        player_id TEXT NOT NULL,
        quest_id TEXT NOT NULL,
        npc_id TEXT NOT NULL,
        status TEXT NOT NULL,           -- 'offered', 'in_progress', 'completed', 'failed'
        offered_at REAL NOT NULL,
        completed_at REAL,              -- NULL if not completed
        UNIQUE(player_id, quest_id),
        FOREIGN KEY(npc_id) REFERENCES npc_profiles(npc_id)
    );
    """

    CREATE_QUEST_LOG_INDEX = """
    CREATE INDEX IF NOT EXISTS idx_quest_log_npc
    ON quest_log(npc_id);
    """

    # ========================================================================
    # TABLE: schema_version
    # ========================================================================
    # Track schema version for migrations.

    CREATE_SCHEMA_VERSION = """
    CREATE TABLE IF NOT EXISTS faction_schema_version (
        version INTEGER PRIMARY KEY,
        created_at REAL NOT NULL
    );
    """

    @staticmethod
    def get_all_create_statements() -> List[str]:
        """Get all CREATE TABLE statements in dependency order."""
        return [
            FactionDatabaseSchema.CREATE_AFFINITY_DEFAULTS,
            FactionDatabaseSchema.CREATE_AFFINITY_DEFAULTS_INDEX,
            FactionDatabaseSchema.CREATE_CULTURAL_AFFINITY_CACHE,
            FactionDatabaseSchema.CREATE_CULTURAL_AFFINITY_CACHE_INDEX,
            FactionDatabaseSchema.CREATE_NPC_PROFILES,
            FactionDatabaseSchema.CREATE_NPC_PROFILES_INDEX,
            FactionDatabaseSchema.CREATE_NPC_BELONGING,
            FactionDatabaseSchema.CREATE_NPC_BELONGING_INDEX,
            FactionDatabaseSchema.CREATE_PLAYER_AFFINITY,
            FactionDatabaseSchema.CREATE_PLAYER_AFFINITY_INDEX,
            FactionDatabaseSchema.CREATE_QUEST_LOG,
            FactionDatabaseSchema.CREATE_QUEST_LOG_INDEX,
            FactionDatabaseSchema.CREATE_SCHEMA_VERSION,
        ]

    @staticmethod
    def create_all_tables(connection) -> None:
        """Create all tables if they don't exist.

        Args:
            connection: SQLite connection object
        """
        cursor = connection.cursor()
        try:
            for statement in FactionDatabaseSchema.get_all_create_statements():
                cursor.execute(statement)

            # Initialize version if not present
            cursor.execute("SELECT COUNT(*) FROM faction_schema_version")
            if cursor.fetchone()[0] == 0:
                cursor.execute(
                    "INSERT INTO faction_schema_version (version, created_at) VALUES (?, ?)",
                    (FACTION_SCHEMA_VERSION, __import__('time').time())
                )

            connection.commit()
            print(f"✓ Faction schema initialized (version {FACTION_SCHEMA_VERSION})")
        except Exception as e:
            connection.rollback()
            print(f"✗ Error creating faction schema: {e}")
            raise

    @staticmethod
    def get_schema_version(connection) -> int:
        """Get current schema version."""
        cursor = connection.cursor()
        cursor.execute("SELECT MAX(version) FROM faction_schema_version")
        result = cursor.fetchone()
        return result[0] if result and result[0] else 0

    @staticmethod
    def verify_schema(connection) -> Tuple[bool, str]:
        """Verify schema is up to date.

        Returns:
            (is_valid, message)
        """
        version = FactionDatabaseSchema.get_schema_version(connection)
        if version == FACTION_SCHEMA_VERSION:
            return True, f"Schema version {version} is current"
        else:
            return False, f"Schema version {version}, expected {FACTION_SCHEMA_VERSION}"


# ============================================================================
# BOOTSTRAP DATA: Pre-populate affinity_defaults
# ============================================================================

BOOTSTRAP_AFFINITY_DEFAULTS_SQL = """
-- World-level defaults (baseline sentiment)
INSERT OR IGNORE INTO affinity_defaults (tier, location_id, tag, delta, created_at, updated_at)
VALUES
    ('world', NULL, 'guild:merchants', -20, 0, 0),
    ('world', NULL, 'guild:smiths', 5, 0, 0),
    ('world', NULL, 'guild:fishers', 0, 0, 0),
    ('world', NULL, 'profession:guard', 10, 0, 0),
    ('world', NULL, 'profession:blacksmith', 5, 0, 0),
    ('world', NULL, 'profession:merchant', -5, 0, 0),
    ('world', NULL, 'profession:farmer', 0, 0, 0),
    ('world', NULL, 'profession:fisher', 0, 0, 0),
    ('world', NULL, 'ideology:separatist', -20, 0, 0),
    ('world', NULL, 'ideology:unifier', 0, 0, 0),
    ('world', NULL, 'rank:noble', 0, 0, 0),
    ('world', NULL, 'rank:commoner', 0, 0, 0),
    ('world', NULL, 'rank:serf', -10, 0, 0);

-- Nation-level overrides
INSERT OR IGNORE INTO affinity_defaults (tier, location_id, tag, delta, created_at, updated_at)
VALUES
    ('nation', 'nation:stormguard', 'guild:merchants', -15, 0, 0),
    ('nation', 'nation:stormguard', 'guild:smiths', 15, 0, 0),
    ('nation', 'nation:stormguard', 'profession:guard', 20, 0, 0),
    ('nation', 'nation:stormguard', 'profession:merchant', -15, 0, 0),
    ('nation', 'nation:stormguard', 'profession:blacksmith', 10, 0, 0),
    ('nation', 'nation:stormguard', 'ideology:separatist', -30, 0, 0),
    ('nation', 'nation:stormguard', 'ideology:unifier', 10, 0, 0),
    ('nation', 'nation:blackoak', 'guild:merchants', 20, 0, 0),
    ('nation', 'nation:blackoak', 'guild:smiths', 0, 0, 0),
    ('nation', 'nation:blackoak', 'profession:merchant', 25, 0, 0),
    ('nation', 'nation:blackoak', 'profession:guard', -5, 0, 0),
    ('nation', 'nation:blackoak', 'profession:blacksmith', -5, 0, 0),
    ('nation', 'nation:blackoak', 'ideology:unifier', 15, 0, 0),
    ('nation', 'nation:blackoak', 'ideology:separatist', -10, 0, 0),
    ('nation', 'nation:shattered_isles', 'guild:merchants', 10, 0, 0),
    ('nation', 'nation:shattered_isles', 'profession:merchant', 10, 0, 0),
    ('nation', 'nation:shattered_isles', 'profession:fisher', 15, 0, 0),
    ('nation', 'nation:shattered_isles', 'ideology:separatist', 20, 0, 0),
    ('nation', 'nation:shattered_isles', 'ideology:unifier', -20, 0, 0),
    ('nation', 'nation:shattered_isles', 'rank:noble', -10, 0, 0),
    ('nation', 'nation:verdant_reaches', 'guild:merchants', -30, 0, 0),
    ('nation', 'nation:verdant_reaches', 'profession:merchant', -25, 0, 0),
    ('nation', 'nation:verdant_reaches', 'profession:farmer', 15, 0, 0),
    ('nation', 'nation:verdant_reaches', 'profession:fisher', 10, 0, 0),
    ('nation', 'nation:verdant_reaches', 'ideology:wilderness_first', 20, 0, 0),
    ('nation', 'nation:verdant_reaches', 'ideology:separatist', 10, 0, 0),
    ('nation', 'nation:verdant_reaches', 'cult:verdant', 15, 0, 0);

-- Region-level overrides
INSERT OR IGNORE INTO affinity_defaults (tier, location_id, tag, delta, created_at, updated_at)
VALUES
    ('region', 'region:northern_marches', 'guild:merchants', -25, 0, 0),
    ('region', 'region:northern_marches', 'profession:guard', 30, 0, 0),
    ('region', 'region:northern_marches', 'profession:merchant', -20, 0, 0),
    ('region', 'region:northern_marches', 'ideology:unifier', 15, 0, 0),
    ('region', 'region:northern_marches', 'rank:noble', 5, 0, 0),
    ('region', 'region:central_heartland', 'guild:merchants', 10, 0, 0),
    ('region', 'region:central_heartland', 'profession:merchant', 15, 0, 0),
    ('region', 'region:central_heartland', 'profession:scholar', 10, 0, 0),
    ('region', 'region:central_heartland', 'ideology:unifier', 20, 0, 0),
    ('region', 'region:southern_reach', 'profession:farmer', 20, 0, 0),
    ('region', 'region:southern_reach', 'profession:merchant', 5, 0, 0),
    ('region', 'region:southern_reach', 'guild:merchants', -5, 0, 0),
    ('region', 'region:western_frontier', 'profession:merchant', 5, 0, 0),
    ('region', 'region:western_frontier', 'profession:guard', 10, 0, 0),
    ('region', 'region:western_frontier', 'ideology:separatist', 15, 0, 0),
    ('region', 'region:western_frontier', 'ideology:wilderness_first', 10, 0, 0);

-- District-level overrides
INSERT OR IGNORE INTO affinity_defaults (tier, location_id, tag, delta, created_at, updated_at)
VALUES
    ('district', 'district:iron_hills', 'guild:smiths', 25, 0, 0),
    ('district', 'district:iron_hills', 'profession:blacksmith', 30, 0, 0),
    ('district', 'district:iron_hills', 'guild:merchants', -35, 0, 0),
    ('district', 'district:iron_hills', 'profession:merchant', -20, 0, 0),
    ('district', 'district:grain_fields', 'profession:farmer', 25, 0, 0),
    ('district', 'district:grain_fields', 'guild:merchants', -15, 0, 0),
    ('district', 'district:grain_fields', 'profession:merchant', -10, 0, 0),
    ('district', 'district:coastal_reach', 'profession:fisher', 20, 0, 0),
    ('district', 'district:coastal_reach', 'guild:fishers', 20, 0, 0),
    ('district', 'district:coastal_reach', 'guild:merchants', 5, 0, 0),
    ('district', 'district:coastal_reach', 'profession:merchant', 10, 0, 0),
    ('district', 'district:whispering_woods', 'cult:verdant', 15, 0, 0),
    ('district', 'district:whispering_woods', 'ideology:wilderness_first', 20, 0, 0),
    ('district', 'district:whispering_woods', 'profession:merchant', -10, 0, 0),
    ('district', 'district:whispering_woods', 'guild:merchants', -15, 0, 0);

-- Locality-level overrides
INSERT OR IGNORE INTO affinity_defaults (tier, location_id, tag, delta, created_at, updated_at)
VALUES
    ('locality', 'village_westhollow', 'guild:merchants', -30, 0, 0),
    ('locality', 'village_westhollow', 'profession:farmer', 25, 0, 0),
    ('locality', 'village_westhollow', 'nation:stormguard', 5, 0, 0),
    ('locality', 'village_westhollow', 'profession:merchant', -20, 0, 0),
    ('locality', 'city_ironhold', 'guild:smiths', 30, 0, 0),
    ('locality', 'city_ironhold', 'profession:blacksmith', 25, 0, 0),
    ('locality', 'city_ironhold', 'guild:merchants', -10, 0, 0),
    ('locality', 'city_ironhold', 'nation:stormguard', 10, 0, 0),
    ('locality', 'city_ironhold', 'rank:noble', 5, 0, 0),
    ('locality', 'port_tidemark', 'guild:merchants', 25, 0, 0),
    ('locality', 'port_tidemark', 'profession:merchant', 30, 0, 0),
    ('locality', 'port_tidemark', 'profession:fisher', 15, 0, 0),
    ('locality', 'port_tidemark', 'guild:fishers', 10, 0, 0),
    ('locality', 'port_tidemark', 'nation:blackoak', 10, 0, 0),
    ('locality', 'forest_haven', 'cult:verdant', 25, 0, 0),
    ('locality', 'forest_haven', 'ideology:wilderness_first', 30, 0, 0),
    ('locality', 'forest_haven', 'profession:farmer', 10, 0, 0),
    ('locality', 'forest_haven', 'guild:merchants', -40, 0, 0),
    ('locality', 'forest_haven', 'nation:verdant_reaches', 15, 0, 0);
"""

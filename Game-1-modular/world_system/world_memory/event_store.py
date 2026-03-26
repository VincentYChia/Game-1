"""SQLite-backed event storage for the World Memory System.

Handles Layer 2 (raw events) and Layer 3 (interpreted events) persistence.
Designed for fast indexed queries by type, actor, location, time range, and tags.

All writes are auto-committed. Queries are read-only and return dataclass instances.
"""

from __future__ import annotations

import json
import os
import sqlite3
from typing import Any, Dict, List, Optional, Tuple

from world_system.world_memory.event_schema import InterpretedEvent, WorldMemoryEvent


# ──────────────────────────────────────────────────────────────────────
# Schema DDL
# ──────────────────────────────────────────────────────────────────────

_SCHEMA_SQL = """
-- Layer 2: Raw Event Records
CREATE TABLE IF NOT EXISTS events (
    event_id TEXT PRIMARY KEY,
    event_type TEXT NOT NULL,
    event_subtype TEXT NOT NULL,
    actor_id TEXT NOT NULL,
    actor_type TEXT NOT NULL,
    target_id TEXT,
    target_type TEXT,
    position_x REAL NOT NULL,
    position_y REAL NOT NULL,
    chunk_x INTEGER NOT NULL,
    chunk_y INTEGER NOT NULL,
    locality_id TEXT,
    district_id TEXT,
    province_id TEXT,
    biome TEXT,
    game_time REAL NOT NULL,
    real_time REAL NOT NULL,
    session_id TEXT,
    magnitude REAL DEFAULT 0.0,
    result TEXT DEFAULT 'success',
    quality TEXT,
    tier INTEGER,
    context_json TEXT DEFAULT '{}',
    interpretation_count INTEGER DEFAULT 0,
    triggered_interpretation INTEGER DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_events_type ON events(event_type);
CREATE INDEX IF NOT EXISTS idx_events_subtype ON events(event_type, event_subtype);
CREATE INDEX IF NOT EXISTS idx_events_actor ON events(actor_id);
CREATE INDEX IF NOT EXISTS idx_events_target ON events(target_id);
CREATE INDEX IF NOT EXISTS idx_events_time ON events(game_time);
CREATE INDEX IF NOT EXISTS idx_events_locality ON events(locality_id);
CREATE INDEX IF NOT EXISTS idx_events_district ON events(district_id);
CREATE INDEX IF NOT EXISTS idx_events_chunk ON events(chunk_x, chunk_y);
CREATE INDEX IF NOT EXISTS idx_events_triggered ON events(triggered_interpretation)
    WHERE triggered_interpretation = 1;

-- Event tags (separate table for efficient tag queries)
CREATE TABLE IF NOT EXISTS event_tags (
    event_id TEXT NOT NULL,
    tag TEXT NOT NULL,
    FOREIGN KEY (event_id) REFERENCES events(event_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_event_tags_tag ON event_tags(tag);
CREATE INDEX IF NOT EXISTS idx_event_tags_event ON event_tags(event_id);


-- Layer 3: Interpreted Events
CREATE TABLE IF NOT EXISTS interpretations (
    interpretation_id TEXT PRIMARY KEY,
    created_at REAL NOT NULL,
    narrative TEXT NOT NULL,
    category TEXT NOT NULL,
    severity TEXT NOT NULL,
    trigger_event_id TEXT,
    trigger_count INTEGER,
    cause_event_ids_json TEXT DEFAULT '[]',
    affected_locality_ids_json TEXT DEFAULT '[]',
    affected_district_ids_json TEXT DEFAULT '[]',
    affected_province_ids_json TEXT DEFAULT '[]',
    epicenter_x REAL,
    epicenter_y REAL,
    affects_tags_json TEXT DEFAULT '[]',
    is_ongoing INTEGER DEFAULT 0,
    expires_at REAL,
    supersedes_id TEXT,
    update_count INTEGER DEFAULT 1,
    archived INTEGER DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_interp_category ON interpretations(category);
CREATE INDEX IF NOT EXISTS idx_interp_severity ON interpretations(severity);
CREATE INDEX IF NOT EXISTS idx_interp_created ON interpretations(created_at);
CREATE INDEX IF NOT EXISTS idx_interp_ongoing ON interpretations(is_ongoing)
    WHERE is_ongoing = 1 AND archived = 0;

CREATE TABLE IF NOT EXISTS interpretation_tags (
    interpretation_id TEXT NOT NULL,
    tag TEXT NOT NULL,
    FOREIGN KEY (interpretation_id) REFERENCES interpretations(interpretation_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_interp_tags_tag ON interpretation_tags(tag);


-- Occurrence counters for threshold trigger tracking
CREATE TABLE IF NOT EXISTS occurrence_counts (
    actor_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    event_subtype TEXT NOT NULL,
    count INTEGER DEFAULT 0,
    PRIMARY KEY (actor_id, event_type, event_subtype)
);

-- Entity state (activity logs, dynamic tags)
CREATE TABLE IF NOT EXISTS entity_state (
    entity_id TEXT PRIMARY KEY,
    tags_json TEXT DEFAULT '[]',
    activity_log_json TEXT DEFAULT '[]',
    state_json TEXT DEFAULT '{}'
);

-- Region state (Layer 4/5 aggregation)
CREATE TABLE IF NOT EXISTS region_state (
    region_id TEXT PRIMARY KEY,
    active_conditions_json TEXT DEFAULT '[]',
    recent_events_json TEXT DEFAULT '[]',
    summary_text TEXT DEFAULT '',
    last_updated REAL DEFAULT 0.0
);


-- ══════════════════════════════════════════════════════════════════
-- Phase 2.3: NPC Memory (per-NPC persistent state)
-- ══════════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS npc_memory (
    npc_id TEXT PRIMARY KEY,
    relationship_score REAL DEFAULT 0.0,
    interaction_count INTEGER DEFAULT 0,
    last_interaction_time REAL DEFAULT 0.0,
    emotional_state TEXT DEFAULT 'neutral',
    knowledge_json TEXT DEFAULT '[]',
    conversation_summary TEXT DEFAULT '',
    reputation_tags_json TEXT DEFAULT '[]',
    quest_state_json TEXT DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_npc_memory_relationship ON npc_memory(relationship_score);


-- ══════════════════════════════════════════════════════════════════
-- Phase 2.4: Faction State (player reputation per faction)
-- ══════════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS faction_state (
    faction_id TEXT PRIMARY KEY,
    player_reputation REAL DEFAULT 0.0,
    crossed_milestones_json TEXT DEFAULT '[]',
    last_change_reason TEXT DEFAULT '',
    last_change_time REAL DEFAULT 0.0
);

CREATE TABLE IF NOT EXISTS faction_reputation_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    faction_id TEXT NOT NULL,
    delta REAL NOT NULL,
    new_score REAL NOT NULL,
    reason TEXT DEFAULT '',
    game_time REAL DEFAULT 0.0,
    is_ripple INTEGER DEFAULT 0,
    FOREIGN KEY (faction_id) REFERENCES faction_state(faction_id)
);

CREATE INDEX IF NOT EXISTS idx_faction_history_faction ON faction_reputation_history(faction_id);
CREATE INDEX IF NOT EXISTS idx_faction_history_time ON faction_reputation_history(game_time);


-- ══════════════════════════════════════════════════════════════════
-- Phase 2.5: Biome Resource State (ecosystem tracking)
-- ══════════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS biome_resource_state (
    biome_type TEXT NOT NULL,
    resource_id TEXT NOT NULL,
    initial_total INTEGER DEFAULT 100,
    current_total REAL DEFAULT 100.0,
    total_gathered INTEGER DEFAULT 0,
    regeneration_rate REAL DEFAULT 300.0,
    is_scarce INTEGER DEFAULT 0,
    is_critical INTEGER DEFAULT 0,
    PRIMARY KEY (biome_type, resource_id)
);

CREATE INDEX IF NOT EXISTS idx_biome_resource_biome ON biome_resource_state(biome_type);
CREATE INDEX IF NOT EXISTS idx_biome_resource_scarce ON biome_resource_state(is_scarce)
    WHERE is_scarce = 1;


-- ══════════════════════════════════════════════════════════════════
-- Phase 2.6+: Event Triggers and Pacing (future use)
-- ══════════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS event_triggers (
    trigger_id TEXT PRIMARY KEY,
    last_fired_time REAL DEFAULT 0.0,
    fire_count INTEGER DEFAULT 0,
    is_one_shot INTEGER DEFAULT 0,
    is_exhausted INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS pacing_state (
    key TEXT PRIMARY KEY,
    value_real REAL DEFAULT 0.0,
    value_text TEXT DEFAULT '',
    updated_at REAL DEFAULT 0.0
);


-- ══════════════════════════════════════════════════════════════════
-- Dual-track trigger counting (threshold-based, not prime-based)
-- ══════════════════════════════════════════════════════════════════

-- Regional accumulator for Track 2 counting
CREATE TABLE IF NOT EXISTS regional_counters (
    region_id TEXT NOT NULL,
    event_category TEXT NOT NULL,
    count INTEGER DEFAULT 0,
    PRIMARY KEY (region_id, event_category)
);

-- Interpretation similarity counting for Layer 3→4 escalation
CREATE TABLE IF NOT EXISTS interpretation_counters (
    category TEXT NOT NULL,
    primary_tag TEXT NOT NULL,
    region_id TEXT NOT NULL,
    count INTEGER DEFAULT 0,
    PRIMARY KEY (category, primary_tag, region_id)
);


-- ══════════════════════════════════════════════════════════════════
-- Time-based tracking (daily ledgers and meta-stats)
-- ══════════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS daily_ledgers (
    game_day INTEGER PRIMARY KEY,
    game_time_start REAL,
    game_time_end REAL,
    data_json TEXT NOT NULL DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS meta_daily_stats (
    stat_key TEXT PRIMARY KEY,
    data_json TEXT NOT NULL DEFAULT '{}'
);


-- ══════════════════════════════════════════════════════════════════
-- Layer 4: Connected Interpretations (cross-domain patterns)
-- ══════════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS connected_interpretations (
    id TEXT PRIMARY KEY,
    created_at REAL NOT NULL,
    narrative TEXT NOT NULL,
    category TEXT NOT NULL,
    severity TEXT NOT NULL,
    source_interpretation_ids_json TEXT DEFAULT '[]',
    affected_district_ids_json TEXT DEFAULT '[]',
    affects_tags_json TEXT DEFAULT '[]',
    is_ongoing INTEGER DEFAULT 0,
    expires_at REAL,
    archived INTEGER DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_connected_interp_category
    ON connected_interpretations(category);
CREATE INDEX IF NOT EXISTS idx_connected_interp_created
    ON connected_interpretations(created_at);

CREATE TABLE IF NOT EXISTS connected_interpretation_tags (
    id TEXT NOT NULL,
    tag TEXT NOT NULL,
    FOREIGN KEY (id) REFERENCES connected_interpretations(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_connected_interp_tags_tag
    ON connected_interpretation_tags(tag);


-- ══════════════════════════════════════════════════════════════════
-- Layer 5: Province Summaries
-- ══════════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS province_summaries (
    province_id TEXT PRIMARY KEY,
    summary_text TEXT DEFAULT '',
    dominant_activities_json TEXT DEFAULT '[]',
    notable_event_ids_json TEXT DEFAULT '[]',
    resource_state_json TEXT DEFAULT '{}',
    threat_level TEXT DEFAULT 'low',
    last_updated REAL DEFAULT 0.0
);


-- ══════════════════════════════════════════════════════════════════
-- Layer 6: Realm State
-- ══════════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS realm_state (
    realm_id TEXT PRIMARY KEY,
    faction_standings_json TEXT DEFAULT '{}',
    economic_summary TEXT DEFAULT '',
    player_reputation TEXT DEFAULT '',
    major_events_json TEXT DEFAULT '[]',
    last_updated REAL DEFAULT 0.0
);


-- ══════════════════════════════════════════════════════════════════
-- Layer 7: World Narrative and Threads
-- ══════════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS world_narrative (
    id TEXT PRIMARY KEY DEFAULT 'singleton',
    world_themes_json TEXT DEFAULT '[]',
    world_epoch TEXT DEFAULT 'unknown',
    active_thread_ids_json TEXT DEFAULT '[]',
    resolved_thread_ids_json TEXT DEFAULT '[]',
    world_history_json TEXT DEFAULT '[]',
    last_updated REAL DEFAULT 0.0
);

CREATE TABLE IF NOT EXISTS narrative_threads (
    thread_id TEXT PRIMARY KEY,
    source TEXT NOT NULL,
    theme TEXT NOT NULL,
    summary TEXT NOT NULL,
    canonical_facts_json TEXT DEFAULT '[]',
    unresolved_questions_json TEXT DEFAULT '[]',
    status TEXT DEFAULT 'rumor',
    significance REAL DEFAULT 0.0,
    origin_region TEXT,
    spread_radius REAL DEFAULT 0.0,
    created_at REAL NOT NULL,
    last_referenced REAL,
    generation_hints_json TEXT DEFAULT '{}'
);
CREATE INDEX IF NOT EXISTS idx_narrative_threads_status
    ON narrative_threads(status);
CREATE INDEX IF NOT EXISTS idx_narrative_threads_significance
    ON narrative_threads(significance);
"""


class EventStore:
    """Persistent event storage using SQLite.

    Handles both Layer 2 (raw events) and Layer 3 (interpreted events).
    One database file per save slot, stored alongside the save JSON.
    """

    DB_FILENAME = "world_memory.db"

    def __init__(self, db_path: Optional[str] = None, save_dir: Optional[str] = None):
        """Initialize with an explicit db_path or derive from save_dir.

        Args:
            db_path: Explicit path to .db file.
            save_dir: Directory containing save files; db created inside.
        """
        if db_path:
            self.db_path = db_path
        elif save_dir:
            os.makedirs(save_dir, exist_ok=True)
            self.db_path = os.path.join(save_dir, self.DB_FILENAME)
        else:
            raise ValueError("Must provide db_path or save_dir")

        self._conn: Optional[sqlite3.Connection] = None
        self._init_db()

    # ── Connection management ────────────────────────────────────────

    def _init_db(self) -> None:
        """Create tables and indexes if they don't exist."""
        self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._conn.executescript(_SCHEMA_SQL)
        self._conn.commit()

    @property
    def connection(self) -> sqlite3.Connection:
        if self._conn is None:
            self._init_db()
        return self._conn

    def close(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None

    def flush(self) -> None:
        """Ensure all writes are persisted (for save-game checkpoints)."""
        if self._conn:
            self._conn.commit()

    # ── Layer 2: Raw event CRUD ──────────────────────────────────────

    def record(self, event: WorldMemoryEvent) -> None:
        """Store a single Layer 2 event."""
        conn = self.connection
        conn.execute(
            """INSERT OR REPLACE INTO events (
                event_id, event_type, event_subtype,
                actor_id, actor_type, target_id, target_type,
                position_x, position_y, chunk_x, chunk_y,
                locality_id, district_id, province_id, biome,
                game_time, real_time, session_id,
                magnitude, result, quality, tier,
                context_json,
                interpretation_count, triggered_interpretation
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                event.event_id, event.event_type, event.event_subtype,
                event.actor_id, event.actor_type, event.target_id, event.target_type,
                event.position_x, event.position_y, event.chunk_x, event.chunk_y,
                event.locality_id, event.district_id, event.province_id, event.biome,
                event.game_time, event.real_time, event.session_id,
                event.magnitude, event.result, event.quality, event.tier,
                json.dumps(event.context),
                event.interpretation_count, int(event.triggered_interpretation),
            ),
        )
        # Insert tags
        if event.tags:
            conn.executemany(
                "INSERT INTO event_tags (event_id, tag) VALUES (?, ?)",
                [(event.event_id, tag) for tag in event.tags],
            )
        conn.commit()

    def record_batch(self, events: List[WorldMemoryEvent]) -> None:
        """Store multiple events in a single transaction."""
        conn = self.connection
        for event in events:
            conn.execute(
                """INSERT OR REPLACE INTO events (
                    event_id, event_type, event_subtype,
                    actor_id, actor_type, target_id, target_type,
                    position_x, position_y, chunk_x, chunk_y,
                    locality_id, district_id, province_id, biome,
                    game_time, real_time, session_id,
                    magnitude, result, quality, tier,
                    context_json,
                    interpretation_count, triggered_interpretation
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    event.event_id, event.event_type, event.event_subtype,
                    event.actor_id, event.actor_type, event.target_id, event.target_type,
                    event.position_x, event.position_y, event.chunk_x, event.chunk_y,
                    event.locality_id, event.district_id, event.province_id, event.biome,
                    event.game_time, event.real_time, event.session_id,
                    event.magnitude, event.result, event.quality, event.tier,
                    json.dumps(event.context),
                    event.interpretation_count, int(event.triggered_interpretation),
                ),
            )
            if event.tags:
                conn.executemany(
                    "INSERT INTO event_tags (event_id, tag) VALUES (?, ?)",
                    [(event.event_id, tag) for tag in event.tags],
                )
        conn.commit()

    def _row_to_event(self, row: sqlite3.Row) -> WorldMemoryEvent:
        """Convert a database row to a WorldMemoryEvent."""
        d = dict(row)
        # Fetch tags for this event
        tags_rows = self.connection.execute(
            "SELECT tag FROM event_tags WHERE event_id = ?", (d["event_id"],)
        ).fetchall()
        tags = [r["tag"] for r in tags_rows]
        return WorldMemoryEvent(
            event_id=d["event_id"],
            event_type=d["event_type"],
            event_subtype=d["event_subtype"],
            actor_id=d["actor_id"],
            actor_type=d["actor_type"],
            target_id=d["target_id"],
            target_type=d["target_type"],
            position_x=d["position_x"],
            position_y=d["position_y"],
            chunk_x=d["chunk_x"],
            chunk_y=d["chunk_y"],
            locality_id=d["locality_id"],
            district_id=d["district_id"],
            province_id=d["province_id"],
            biome=d["biome"],
            game_time=d["game_time"],
            real_time=d["real_time"],
            session_id=d["session_id"] or "",
            magnitude=d["magnitude"] or 0.0,
            result=d["result"] or "success",
            quality=d["quality"],
            tier=d["tier"],
            tags=tags,
            context=json.loads(d["context_json"]) if d["context_json"] else {},
            interpretation_count=d["interpretation_count"] or 0,
            triggered_interpretation=bool(d["triggered_interpretation"]),
        )

    def query(self, *,
              event_type: Optional[str] = None,
              event_subtype: Optional[str] = None,
              actor_id: Optional[str] = None,
              target_id: Optional[str] = None,
              locality_id: Optional[str] = None,
              district_id: Optional[str] = None,
              chunk: Optional[Tuple[int, int]] = None,
              since_game_time: Optional[float] = None,
              before_game_time: Optional[float] = None,
              tags: Optional[List[str]] = None,
              limit: int = 50,
              order_desc: bool = True) -> List[WorldMemoryEvent]:
        """Flexible query for Layer 2 events."""
        conn = self.connection
        conn.row_factory = sqlite3.Row
        clauses: List[str] = []
        params: List[Any] = []

        if event_type:
            clauses.append("e.event_type = ?")
            params.append(event_type)
        if event_subtype:
            clauses.append("e.event_subtype = ?")
            params.append(event_subtype)
        if actor_id:
            clauses.append("e.actor_id = ?")
            params.append(actor_id)
        if target_id:
            clauses.append("e.target_id = ?")
            params.append(target_id)
        if locality_id:
            clauses.append("e.locality_id = ?")
            params.append(locality_id)
        if district_id:
            clauses.append("e.district_id = ?")
            params.append(district_id)
        if chunk:
            clauses.append("e.chunk_x = ? AND e.chunk_y = ?")
            params.extend(chunk)
        if since_game_time is not None:
            clauses.append("e.game_time >= ?")
            params.append(since_game_time)
        if before_game_time is not None:
            clauses.append("e.game_time < ?")
            params.append(before_game_time)

        # Tag filtering: require ALL provided tags
        if tags:
            for i, tag in enumerate(tags):
                alias = f"t{i}"
                clauses.append(
                    f"EXISTS (SELECT 1 FROM event_tags {alias} "
                    f"WHERE {alias}.event_id = e.event_id AND {alias}.tag = ?)"
                )
                params.append(tag)

        where = " AND ".join(clauses) if clauses else "1=1"
        direction = "DESC" if order_desc else "ASC"
        sql = f"SELECT e.* FROM events e WHERE {where} ORDER BY e.game_time {direction} LIMIT ?"
        params.append(limit)

        rows = conn.execute(sql, params).fetchall()
        return [self._row_to_event(row) for row in rows]

    def count_filtered(self, *,
                       event_type: Optional[str] = None,
                       event_subtype: Optional[str] = None,
                       actor_id: Optional[str] = None,
                       locality_id: Optional[str] = None,
                       since_game_time: Optional[float] = None) -> int:
        """Count events matching filters (fast — no row materialization)."""
        conn = self.connection
        clauses: List[str] = []
        params: List[Any] = []
        if event_type:
            clauses.append("event_type = ?")
            params.append(event_type)
        if event_subtype:
            clauses.append("event_subtype = ?")
            params.append(event_subtype)
        if actor_id:
            clauses.append("actor_id = ?")
            params.append(actor_id)
        if locality_id:
            clauses.append("locality_id = ?")
            params.append(locality_id)
        if since_game_time is not None:
            clauses.append("game_time >= ?")
            params.append(since_game_time)
        where = " AND ".join(clauses) if clauses else "1=1"
        row = conn.execute(f"SELECT COUNT(*) FROM events WHERE {where}", params).fetchone()
        return row[0]

    def get_by_ids(self, event_ids: List[str]) -> List[WorldMemoryEvent]:
        """Fetch events by their IDs (for activity log lookups)."""
        if not event_ids:
            return []
        conn = self.connection
        conn.row_factory = sqlite3.Row
        placeholders = ",".join("?" for _ in event_ids)
        rows = conn.execute(
            f"SELECT * FROM events WHERE event_id IN ({placeholders}) ORDER BY game_time DESC",
            event_ids,
        ).fetchall()
        return [self._row_to_event(row) for row in rows]

    def delete_events(self, event_ids: List[str]) -> int:
        """Delete events by ID (for retention pruning). Returns count deleted."""
        if not event_ids:
            return 0
        conn = self.connection
        placeholders = ",".join("?" for _ in event_ids)
        # Tags cascade-deleted via foreign key
        cursor = conn.execute(
            f"DELETE FROM events WHERE event_id IN ({placeholders})", event_ids
        )
        conn.commit()
        return cursor.rowcount

    def get_event_count(self) -> int:
        """Total number of events in the store."""
        row = self.connection.execute("SELECT COUNT(*) FROM events").fetchone()
        return row[0]

    # ── Occurrence counter helpers ───────────────────────────────────

    def increment_occurrence(self, actor_id: str, event_type: str,
                             event_subtype: str) -> int:
        """Increment and return the new occurrence count."""
        conn = self.connection
        conn.execute(
            """INSERT INTO occurrence_counts (actor_id, event_type, event_subtype, count)
               VALUES (?, ?, ?, 1)
               ON CONFLICT(actor_id, event_type, event_subtype)
               DO UPDATE SET count = count + 1""",
            (actor_id, event_type, event_subtype),
        )
        conn.commit()
        row = conn.execute(
            "SELECT count FROM occurrence_counts WHERE actor_id=? AND event_type=? AND event_subtype=?",
            (actor_id, event_type, event_subtype),
        ).fetchone()
        return row[0]

    def get_occurrence_count(self, actor_id: str, event_type: str,
                             event_subtype: str) -> int:
        """Get current occurrence count without incrementing."""
        row = self.connection.execute(
            "SELECT count FROM occurrence_counts WHERE actor_id=? AND event_type=? AND event_subtype=?",
            (actor_id, event_type, event_subtype),
        ).fetchone()
        return row[0] if row else 0

    def get_all_occurrence_counts(self) -> Dict[Tuple[str, str, str], int]:
        """Load all occurrence counts into memory."""
        rows = self.connection.execute(
            "SELECT actor_id, event_type, event_subtype, count FROM occurrence_counts"
        ).fetchall()
        return {(r[0], r[1], r[2]): r[3] for r in rows}

    # ── Layer 3: Interpretation CRUD ─────────────────────────────────

    def record_interpretation(self, interp: InterpretedEvent) -> None:
        """Store a Layer 3 interpreted event."""
        conn = self.connection
        conn.execute(
            """INSERT OR REPLACE INTO interpretations (
                interpretation_id, created_at, narrative, category, severity,
                trigger_event_id, trigger_count, cause_event_ids_json,
                affected_locality_ids_json, affected_district_ids_json,
                affected_province_ids_json, epicenter_x, epicenter_y,
                affects_tags_json, is_ongoing, expires_at,
                supersedes_id, update_count, archived
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                interp.interpretation_id, interp.created_at,
                interp.narrative, interp.category, interp.severity,
                interp.trigger_event_id, interp.trigger_count,
                json.dumps(interp.cause_event_ids),
                json.dumps(interp.affected_locality_ids),
                json.dumps(interp.affected_district_ids),
                json.dumps(interp.affected_province_ids),
                interp.epicenter_x, interp.epicenter_y,
                json.dumps(interp.affects_tags),
                int(interp.is_ongoing), interp.expires_at,
                interp.supersedes_id, interp.update_count,
                int(interp.archived),
            ),
        )
        # Insert routing tags
        if interp.affects_tags:
            conn.executemany(
                "INSERT INTO interpretation_tags (interpretation_id, tag) VALUES (?, ?)",
                [(interp.interpretation_id, tag) for tag in interp.affects_tags],
            )
        conn.commit()

    def _row_to_interpretation(self, row: sqlite3.Row) -> InterpretedEvent:
        d = dict(row)
        return InterpretedEvent(
            interpretation_id=d["interpretation_id"],
            created_at=d["created_at"],
            narrative=d["narrative"],
            category=d["category"],
            severity=d["severity"],
            trigger_event_id=d["trigger_event_id"] or "",
            trigger_count=d["trigger_count"] or 0,
            cause_event_ids=json.loads(d["cause_event_ids_json"]),
            affected_locality_ids=json.loads(d["affected_locality_ids_json"]),
            affected_district_ids=json.loads(d["affected_district_ids_json"]),
            affected_province_ids=json.loads(d["affected_province_ids_json"]),
            epicenter_x=d["epicenter_x"] or 0.0,
            epicenter_y=d["epicenter_y"] or 0.0,
            affects_tags=json.loads(d["affects_tags_json"]),
            is_ongoing=bool(d["is_ongoing"]),
            expires_at=d["expires_at"],
            supersedes_id=d["supersedes_id"],
            update_count=d["update_count"] or 1,
            archived=bool(d["archived"]),
        )

    def query_interpretations(self, *,
                              category: Optional[str] = None,
                              severity_min: Optional[str] = None,
                              locality_id: Optional[str] = None,
                              ongoing_only: bool = False,
                              include_archived: bool = False,
                              limit: int = 50) -> List[InterpretedEvent]:
        """Query Layer 3 interpretations."""
        from world_system.world_memory.event_schema import SEVERITY_ORDER
        conn = self.connection
        conn.row_factory = sqlite3.Row
        clauses: List[str] = []
        params: List[Any] = []

        if not include_archived:
            clauses.append("archived = 0")
        if category:
            clauses.append("category = ?")
            params.append(category)
        if ongoing_only:
            clauses.append("is_ongoing = 1")
        if severity_min and severity_min in SEVERITY_ORDER:
            min_val = SEVERITY_ORDER[severity_min]
            valid_severities = [s for s, v in SEVERITY_ORDER.items() if v >= min_val]
            placeholders = ",".join("?" for _ in valid_severities)
            clauses.append(f"severity IN ({placeholders})")
            params.extend(valid_severities)

        where = " AND ".join(clauses) if clauses else "1=1"
        sql = f"SELECT * FROM interpretations WHERE {where} ORDER BY created_at DESC LIMIT ?"
        params.append(limit)

        rows = conn.execute(sql, params).fetchall()
        results = [self._row_to_interpretation(row) for row in rows]

        # Post-filter by locality if requested (stored as JSON array)
        if locality_id:
            results = [
                r for r in results if locality_id in r.affected_locality_ids
            ]
        return results

    def get_interpretation(self, interp_id: str) -> Optional[InterpretedEvent]:
        """Get a single interpretation by ID."""
        conn = self.connection
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT * FROM interpretations WHERE interpretation_id = ?", (interp_id,)
        ).fetchone()
        return self._row_to_interpretation(row) if row else None

    def get_ongoing_interpretations(self,
                                    locality_id: Optional[str] = None) -> List[InterpretedEvent]:
        """Get all active (non-expired, non-archived) ongoing interpretations."""
        return self.query_interpretations(ongoing_only=True, locality_id=locality_id)

    def archive_interpretation(self, interp_id: str) -> None:
        """Soft-delete by marking archived (when superseded)."""
        self.connection.execute(
            "UPDATE interpretations SET archived = 1 WHERE interpretation_id = ?",
            (interp_id,),
        )
        self.connection.commit()

    def find_supersedable(self, category: str, affects_tags: List[str],
                          locality_ids: List[str]) -> Optional[InterpretedEvent]:
        """Find an existing ongoing interpretation that this one would supersede."""
        candidates = self.query_interpretations(
            category=category, ongoing_only=True, include_archived=False
        )
        for c in candidates:
            # Match if same category and overlapping localities
            if set(c.affected_locality_ids) & set(locality_ids):
                # And overlapping tags
                if set(c.affects_tags) & set(affects_tags):
                    return c
        return None

    def is_referenced_by_interpretation(self, event_id: str) -> bool:
        """Check if a Layer 2 event is referenced by any Layer 3 interpretation."""
        row = self.connection.execute(
            "SELECT 1 FROM interpretations WHERE cause_event_ids_json LIKE ? LIMIT 1",
            (f"%{event_id}%",),
        ).fetchone()
        return row is not None

    def expire_old_interpretations(self, current_game_time: float) -> int:
        """Mark expired ongoing interpretations as no longer ongoing."""
        cursor = self.connection.execute(
            """UPDATE interpretations SET is_ongoing = 0
               WHERE is_ongoing = 1 AND expires_at IS NOT NULL AND expires_at <= ?""",
            (current_game_time,),
        )
        self.connection.commit()
        return cursor.rowcount

    # ── Entity state persistence ─────────────────────────────────────

    def save_entity_state(self, entity_id: str, tags: List[str],
                          activity_log: List[str],
                          state: Dict[str, Any]) -> None:
        self.connection.execute(
            """INSERT OR REPLACE INTO entity_state
               (entity_id, tags_json, activity_log_json, state_json)
               VALUES (?, ?, ?, ?)""",
            (entity_id, json.dumps(tags), json.dumps(activity_log), json.dumps(state)),
        )
        self.connection.commit()

    def load_entity_state(self, entity_id: str) -> Optional[Dict[str, Any]]:
        row = self.connection.execute(
            "SELECT * FROM entity_state WHERE entity_id = ?", (entity_id,)
        ).fetchone()
        if not row:
            return None
        return {
            "tags": json.loads(row[1]),
            "activity_log": json.loads(row[2]),
            "state": json.loads(row[3]),
        }

    # ── Region state persistence ─────────────────────────────────────

    def save_region_state(self, region_id: str, active_conditions: List[str],
                          recent_events: List[str], summary: str,
                          last_updated: float) -> None:
        self.connection.execute(
            """INSERT OR REPLACE INTO region_state
               (region_id, active_conditions_json, recent_events_json,
                summary_text, last_updated)
               VALUES (?, ?, ?, ?, ?)""",
            (region_id, json.dumps(active_conditions), json.dumps(recent_events),
             summary, last_updated),
        )
        self.connection.commit()

    def load_region_state(self, region_id: str) -> Optional[Dict[str, Any]]:
        row = self.connection.execute(
            "SELECT * FROM region_state WHERE region_id = ?", (region_id,)
        ).fetchone()
        if not row:
            return None
        return {
            "active_conditions": json.loads(row[1]),
            "recent_events": json.loads(row[2]),
            "summary_text": row[3],
            "last_updated": row[4],
        }

    def load_all_region_states(self) -> Dict[str, Dict[str, Any]]:
        rows = self.connection.execute("SELECT * FROM region_state").fetchall()
        result = {}
        for row in rows:
            result[row[0]] = {
                "active_conditions": json.loads(row[1]),
                "recent_events": json.loads(row[2]),
                "summary_text": row[3],
                "last_updated": row[4],
            }
        return result

    # ── NPC Memory persistence (Phase 2.3) ────────────────────────────

    def save_npc_memory(self, npc_id: str, memory_data: Dict[str, Any]) -> None:
        """Save NPC memory state to SQLite."""
        self.connection.execute(
            """INSERT OR REPLACE INTO npc_memory
               (npc_id, relationship_score, interaction_count,
                last_interaction_time, emotional_state,
                knowledge_json, conversation_summary,
                reputation_tags_json, quest_state_json)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                npc_id,
                memory_data.get("relationship_score", 0.0),
                memory_data.get("interaction_count", 0),
                memory_data.get("last_interaction_time", 0.0),
                memory_data.get("emotional_state", "neutral"),
                json.dumps(memory_data.get("knowledge", [])),
                memory_data.get("conversation_summary", ""),
                json.dumps(memory_data.get("player_reputation_tags", [])),
                json.dumps(memory_data.get("quest_state", {})),
            ),
        )
        self.connection.commit()

    def load_npc_memory(self, npc_id: str) -> Optional[Dict[str, Any]]:
        """Load NPC memory state from SQLite."""
        row = self.connection.execute(
            "SELECT * FROM npc_memory WHERE npc_id = ?", (npc_id,)
        ).fetchone()
        if not row:
            return None
        return {
            "npc_id": row[0],
            "relationship_score": row[1],
            "interaction_count": row[2],
            "last_interaction_time": row[3],
            "emotional_state": row[4],
            "knowledge": json.loads(row[5]),
            "conversation_summary": row[6],
            "player_reputation_tags": json.loads(row[7]),
            "quest_state": json.loads(row[8]),
        }

    def load_all_npc_memories(self) -> Dict[str, Dict[str, Any]]:
        """Load all NPC memories."""
        rows = self.connection.execute("SELECT * FROM npc_memory").fetchall()
        result = {}
        for row in rows:
            result[row[0]] = {
                "npc_id": row[0],
                "relationship_score": row[1],
                "interaction_count": row[2],
                "last_interaction_time": row[3],
                "emotional_state": row[4],
                "knowledge": json.loads(row[5]),
                "conversation_summary": row[6],
                "player_reputation_tags": json.loads(row[7]),
                "quest_state": json.loads(row[8]),
            }
        return result

    # ── Faction state persistence (Phase 2.4) ─────────────────────────

    def save_faction_state(self, faction_id: str, reputation: float,
                           milestones: List[float], reason: str,
                           game_time: float) -> None:
        """Save faction state to SQLite."""
        self.connection.execute(
            """INSERT OR REPLACE INTO faction_state
               (faction_id, player_reputation, crossed_milestones_json,
                last_change_reason, last_change_time)
               VALUES (?, ?, ?, ?, ?)""",
            (faction_id, reputation, json.dumps(milestones), reason, game_time),
        )
        self.connection.commit()

    def load_all_faction_states(self) -> Dict[str, Dict[str, Any]]:
        """Load all faction states."""
        rows = self.connection.execute("SELECT * FROM faction_state").fetchall()
        result = {}
        for row in rows:
            result[row[0]] = {
                "faction_id": row[0],
                "player_reputation": row[1],
                "crossed_milestones": json.loads(row[2]),
                "last_change_reason": row[3],
                "last_change_time": row[4],
            }
        return result

    def save_faction_history(self, entries: List[Dict[str, Any]]) -> None:
        """Save faction reputation history entries."""
        conn = self.connection
        for entry in entries:
            conn.execute(
                """INSERT INTO faction_reputation_history
                   (faction_id, delta, new_score, reason, game_time, is_ripple)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    entry.get("faction_id", ""),
                    entry.get("delta", 0.0),
                    entry.get("new_score", 0.0),
                    entry.get("reason", ""),
                    entry.get("game_time", 0.0),
                    int(entry.get("is_ripple", False)),
                ),
            )
        conn.commit()

    # ── Biome resource state persistence (Phase 2.5) ──────────────────

    def save_biome_resource(self, biome_type: str, resource_id: str,
                            data: Dict[str, Any]) -> None:
        """Save biome resource state to SQLite."""
        self.connection.execute(
            """INSERT OR REPLACE INTO biome_resource_state
               (biome_type, resource_id, initial_total, current_total,
                total_gathered, regeneration_rate, is_scarce, is_critical)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                biome_type, resource_id,
                data.get("initial_total", 100),
                data.get("current_total", 100.0),
                data.get("total_gathered", 0),
                data.get("regeneration_rate", 300.0),
                int(data.get("is_scarce", False)),
                int(data.get("is_critical", False)),
            ),
        )
        self.connection.commit()

    def load_all_biome_resources(self) -> Dict[str, Dict[str, Dict[str, Any]]]:
        """Load all biome resource states. Returns {biome → {resource → data}}."""
        rows = self.connection.execute(
            "SELECT * FROM biome_resource_state"
        ).fetchall()
        result: Dict[str, Dict[str, Dict[str, Any]]] = {}
        for row in rows:
            biome_type = row[0]
            if biome_type not in result:
                result[biome_type] = {}
            result[biome_type][row[1]] = {
                "initial_total": row[2],
                "current_total": row[3],
                "total_gathered": row[4],
                "regeneration_rate": row[5],
                "is_scarce": bool(row[6]),
                "is_critical": bool(row[7]),
            }
        return result

    # ── Regional counter persistence (dual-track triggers) ──────────

    def increment_regional_counter(self, region_id: str,
                                   event_category: str) -> int:
        """Increment and return the regional event category counter."""
        conn = self.connection
        conn.execute(
            """INSERT INTO regional_counters (region_id, event_category, count)
               VALUES (?, ?, 1)
               ON CONFLICT(region_id, event_category)
               DO UPDATE SET count = count + 1""",
            (region_id, event_category),
        )
        conn.commit()
        row = conn.execute(
            "SELECT count FROM regional_counters WHERE region_id=? AND event_category=?",
            (region_id, event_category),
        ).fetchone()
        return row[0] if row else 0

    def get_regional_counter(self, region_id: str,
                             event_category: str) -> int:
        """Get the current regional counter value."""
        row = self.connection.execute(
            "SELECT count FROM regional_counters WHERE region_id=? AND event_category=?",
            (region_id, event_category),
        ).fetchone()
        return row[0] if row else 0

    def load_all_regional_counters(self) -> Dict[Tuple[str, str], int]:
        """Load all regional counters. Returns {(region_id, category): count}."""
        rows = self.connection.execute(
            "SELECT region_id, event_category, count FROM regional_counters"
        ).fetchall()
        return {(r[0], r[1]): r[2] for r in rows}

    # ── Daily ledger persistence ────────────────────────────────────

    def store_daily_ledger(self, game_day: int, game_time_start: float,
                           game_time_end: float, data_json: str) -> None:
        """Store a daily ledger row."""
        self.connection.execute(
            """INSERT OR REPLACE INTO daily_ledgers
               (game_day, game_time_start, game_time_end, data_json)
               VALUES (?, ?, ?, ?)""",
            (game_day, game_time_start, game_time_end, data_json),
        )
        self.connection.commit()

    def load_daily_ledgers(self) -> List[Tuple[int, float, float, str]]:
        """Load all daily ledgers. Returns [(game_day, start, end, json), ...]."""
        rows = self.connection.execute(
            "SELECT game_day, game_time_start, game_time_end, data_json "
            "FROM daily_ledgers ORDER BY game_day"
        ).fetchall()
        return [(r[0], r[1], r[2], r[3]) for r in rows]

    def store_meta_daily_stats(self, data_json: str) -> None:
        """Store meta-daily stats (single row, keyed 'global')."""
        self.connection.execute(
            """INSERT OR REPLACE INTO meta_daily_stats (stat_key, data_json)
               VALUES ('global', ?)""",
            (data_json,),
        )
        self.connection.commit()

    def load_meta_daily_stats(self) -> Optional[str]:
        """Load meta-daily stats JSON string."""
        row = self.connection.execute(
            "SELECT data_json FROM meta_daily_stats WHERE stat_key='global'"
        ).fetchone()
        return row[0] if row else None

    # ── Schema introspection (for testing) ──────────────────────────

    def get_table_names(self) -> List[str]:
        """Return all table names in the database."""
        rows = self.connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        ).fetchall()
        return [r[0] for r in rows]

    def get_index_names(self) -> List[str]:
        """Return all index names in the database."""
        rows = self.connection.execute(
            "SELECT name FROM sqlite_master WHERE type='index' ORDER BY name"
        ).fetchall()
        return [r[0] for r in rows]

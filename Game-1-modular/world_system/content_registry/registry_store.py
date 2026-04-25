"""SQLite schema + CRUD for the Content Registry (§7.2).

This module owns the on-disk layout for generator-authored content:

- Five per-tool header tables (``reg_hostiles`` ... ``reg_titles``).
- A unified ``content_xref`` table.
- Minimal schema versioning for future migrations.

Design choices follow the pattern set by
:mod:`world_system.world_memory.event_store`:

- Connection is ``check_same_thread=False`` so async runners can share it.
- WAL journal mode + foreign_keys ON.
- ``INSERT OR REPLACE`` for idempotent staging.

The store is a low-level CRUD layer. Business logic (stage vs commit,
orphan scan, file writing) lives in :mod:`content_registry`. This
file deliberately has no singleton — the facade owns one instance.
"""

from __future__ import annotations

import json
import os
import sqlite3
import threading
from typing import Any, Dict, List, Optional, Tuple

from world_system.content_registry.xref_rules import VALID_TOOLS, XrefTuple


# Per-tool registry tables + unified xref table. ``reg_<tool>``
# columns are identical across tools for uniform CRUD — schema §7.2.
_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS reg_hostiles (
    content_id TEXT PRIMARY KEY,
    display_name TEXT,
    tier INTEGER,
    biome TEXT,
    faction_id TEXT,
    staged INTEGER DEFAULT 1,
    plan_id TEXT,
    created_at REAL,
    source_bundle_id TEXT,
    payload_json TEXT
);

CREATE TABLE IF NOT EXISTS reg_materials (
    content_id TEXT PRIMARY KEY,
    display_name TEXT,
    tier INTEGER,
    biome TEXT,
    faction_id TEXT,
    staged INTEGER DEFAULT 1,
    plan_id TEXT,
    created_at REAL,
    source_bundle_id TEXT,
    payload_json TEXT
);

CREATE TABLE IF NOT EXISTS reg_nodes (
    content_id TEXT PRIMARY KEY,
    display_name TEXT,
    tier INTEGER,
    biome TEXT,
    faction_id TEXT,
    staged INTEGER DEFAULT 1,
    plan_id TEXT,
    created_at REAL,
    source_bundle_id TEXT,
    payload_json TEXT
);

CREATE TABLE IF NOT EXISTS reg_skills (
    content_id TEXT PRIMARY KEY,
    display_name TEXT,
    tier INTEGER,
    biome TEXT,
    faction_id TEXT,
    staged INTEGER DEFAULT 1,
    plan_id TEXT,
    created_at REAL,
    source_bundle_id TEXT,
    payload_json TEXT
);

CREATE TABLE IF NOT EXISTS reg_titles (
    content_id TEXT PRIMARY KEY,
    display_name TEXT,
    tier INTEGER,
    biome TEXT,
    faction_id TEXT,
    staged INTEGER DEFAULT 1,
    plan_id TEXT,
    created_at REAL,
    source_bundle_id TEXT,
    payload_json TEXT
);

CREATE TABLE IF NOT EXISTS reg_chunks (
    content_id TEXT PRIMARY KEY,
    display_name TEXT,
    tier INTEGER,
    biome TEXT,
    faction_id TEXT,
    staged INTEGER DEFAULT 1,
    plan_id TEXT,
    created_at REAL,
    source_bundle_id TEXT,
    payload_json TEXT
);

CREATE TABLE IF NOT EXISTS reg_npcs (
    content_id TEXT PRIMARY KEY,
    display_name TEXT,
    tier INTEGER,
    biome TEXT,
    faction_id TEXT,
    staged INTEGER DEFAULT 1,
    plan_id TEXT,
    created_at REAL,
    source_bundle_id TEXT,
    payload_json TEXT
);

CREATE TABLE IF NOT EXISTS reg_quests (
    content_id TEXT PRIMARY KEY,
    display_name TEXT,
    tier INTEGER,
    biome TEXT,
    faction_id TEXT,
    staged INTEGER DEFAULT 1,
    plan_id TEXT,
    created_at REAL,
    source_bundle_id TEXT,
    payload_json TEXT
);

CREATE INDEX IF NOT EXISTS idx_reg_hostiles_plan   ON reg_hostiles(plan_id);
CREATE INDEX IF NOT EXISTS idx_reg_hostiles_stage  ON reg_hostiles(staged);
CREATE INDEX IF NOT EXISTS idx_reg_materials_plan  ON reg_materials(plan_id);
CREATE INDEX IF NOT EXISTS idx_reg_materials_stage ON reg_materials(staged);
CREATE INDEX IF NOT EXISTS idx_reg_nodes_plan      ON reg_nodes(plan_id);
CREATE INDEX IF NOT EXISTS idx_reg_nodes_stage     ON reg_nodes(staged);
CREATE INDEX IF NOT EXISTS idx_reg_skills_plan     ON reg_skills(plan_id);
CREATE INDEX IF NOT EXISTS idx_reg_skills_stage    ON reg_skills(staged);
CREATE INDEX IF NOT EXISTS idx_reg_titles_plan     ON reg_titles(plan_id);
CREATE INDEX IF NOT EXISTS idx_reg_titles_stage    ON reg_titles(staged);
CREATE INDEX IF NOT EXISTS idx_reg_chunks_plan     ON reg_chunks(plan_id);
CREATE INDEX IF NOT EXISTS idx_reg_chunks_stage    ON reg_chunks(staged);
CREATE INDEX IF NOT EXISTS idx_reg_npcs_plan       ON reg_npcs(plan_id);
CREATE INDEX IF NOT EXISTS idx_reg_npcs_stage      ON reg_npcs(staged);
CREATE INDEX IF NOT EXISTS idx_reg_quests_plan     ON reg_quests(plan_id);
CREATE INDEX IF NOT EXISTS idx_reg_quests_stage    ON reg_quests(staged);

CREATE TABLE IF NOT EXISTS content_xref (
    src_type TEXT,
    src_id TEXT,
    ref_type TEXT,
    ref_id TEXT,
    relationship TEXT,
    plan_id TEXT,
    PRIMARY KEY (src_type, src_id, ref_type, ref_id, relationship)
);

CREATE INDEX IF NOT EXISTS idx_xref_ref ON content_xref(ref_type, ref_id);
CREATE INDEX IF NOT EXISTS idx_xref_src ON content_xref(src_type, src_id);
CREATE INDEX IF NOT EXISTS idx_xref_plan ON content_xref(plan_id);

CREATE TABLE IF NOT EXISTS schema_meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""


# Mapping from tool name (plural) to SQL table name — for query
# dispatch. Table names intentionally match the tool names verbatim
# per §7.2.
TOOL_TABLE = {
    "hostiles": "reg_hostiles",
    "materials": "reg_materials",
    "nodes": "reg_nodes",
    "skills": "reg_skills",
    "titles": "reg_titles",
    "chunks": "reg_chunks",
    "npcs": "reg_npcs",
    "quests": "reg_quests",
}


DB_FILENAME = "content_registry.db"
SCHEMA_VERSION = 1


class RegistryStore:
    """Low-level SQLite CRUD for the content registry."""

    def __init__(
        self,
        db_path: Optional[str] = None,
        save_dir: Optional[str] = None,
    ) -> None:
        """Open (or create) the SQLite DB.

        Args:
            db_path: Explicit path to .db file.
            save_dir: Save directory; DB filename is appended.

        One of the two must be provided.
        """
        if db_path:
            self.db_path = str(db_path)
        elif save_dir:
            os.makedirs(save_dir, exist_ok=True)
            self.db_path = os.path.join(str(save_dir), DB_FILENAME)
        else:
            raise ValueError("Must provide db_path or save_dir")

        self._conn: Optional[sqlite3.Connection] = None
        self._lock = threading.RLock()
        self._init_db()

    # ── Connection lifecycle ─────────────────────────────────────────

    def _init_db(self) -> None:
        self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._conn.executescript(_SCHEMA_SQL)
        self._conn.execute(
            "INSERT OR REPLACE INTO schema_meta (key, value) VALUES (?, ?)",
            ("schema_version", str(SCHEMA_VERSION)),
        )
        self._conn.commit()

    @property
    def connection(self) -> sqlite3.Connection:
        if self._conn is None:
            self._init_db()
        return self._conn  # type: ignore[return-value]

    def close(self) -> None:
        with self._lock:
            if self._conn:
                self._conn.close()
                self._conn = None

    def flush(self) -> None:
        with self._lock:
            if self._conn:
                self._conn.commit()

    # ── Reg-table writes ─────────────────────────────────────────────

    def insert_staged_row(
        self,
        tool_name: str,
        content_id: str,
        display_name: str,
        tier: int,
        biome: str,
        faction_id: str,
        plan_id: str,
        source_bundle_id: str,
        created_at: float,
        payload_json: str,
    ) -> None:
        """Insert (or replace) a staged row in the ``reg_<tool>`` table."""
        table = self._require_table(tool_name)
        sql = (
            f"INSERT OR REPLACE INTO {table} "
            "(content_id, display_name, tier, biome, faction_id, "
            " staged, plan_id, created_at, source_bundle_id, payload_json) "
            "VALUES (?, ?, ?, ?, ?, 1, ?, ?, ?, ?)"
        )
        with self._lock:
            self.connection.execute(
                sql,
                (
                    content_id,
                    display_name,
                    tier,
                    biome,
                    faction_id,
                    plan_id,
                    created_at,
                    source_bundle_id,
                    payload_json,
                ),
            )
            self.connection.commit()

    def flip_staged_to_live(self, plan_id: str) -> Dict[str, int]:
        """Flip every staged row for this plan to staged=0. Returns
        counts per table for logging."""
        counts: Dict[str, int] = {}
        with self._lock:
            for tool_name, table in TOOL_TABLE.items():
                cur = self.connection.execute(
                    f"UPDATE {table} SET staged=0 "
                    "WHERE plan_id=? AND staged=1",
                    (plan_id,),
                )
                counts[tool_name] = cur.rowcount or 0
            self.connection.commit()
        return counts

    def delete_staged_rows(self, plan_id: str) -> Dict[str, int]:
        """Delete every staged row for this plan. Returns counts."""
        counts: Dict[str, int] = {}
        with self._lock:
            for tool_name, table in TOOL_TABLE.items():
                cur = self.connection.execute(
                    f"DELETE FROM {table} "
                    "WHERE plan_id=? AND staged=1",
                    (plan_id,),
                )
                counts[tool_name] = cur.rowcount or 0
            cur_x = self.connection.execute(
                "DELETE FROM content_xref WHERE plan_id=?",
                (plan_id,),
            )
            counts["content_xref"] = cur_x.rowcount or 0
            self.connection.commit()
        return counts

    # ── Xref writes ──────────────────────────────────────────────────

    def insert_xref(
        self,
        src_type: str,
        src_id: str,
        ref_type: str,
        ref_id: str,
        relationship: str,
        plan_id: str,
    ) -> None:
        with self._lock:
            self.connection.execute(
                "INSERT OR IGNORE INTO content_xref "
                "(src_type, src_id, ref_type, ref_id, relationship, plan_id) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (src_type, src_id, ref_type, ref_id, relationship, plan_id),
            )
            self.connection.commit()

    def insert_xrefs_bulk(
        self, xrefs: List[XrefTuple], plan_id: str
    ) -> None:
        rows = [
            (*tup, plan_id) for tup in xrefs
        ]
        with self._lock:
            self.connection.executemany(
                "INSERT OR IGNORE INTO content_xref "
                "(src_type, src_id, ref_type, ref_id, relationship, plan_id) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                rows,
            )
            self.connection.commit()

    # ── Reads ────────────────────────────────────────────────────────

    def get_row(
        self, tool_name: str, content_id: str, include_staged: bool
    ) -> Optional[Dict[str, Any]]:
        table = self._require_table(tool_name)
        if include_staged:
            sql = f"SELECT * FROM {table} WHERE content_id=?"
            params: Tuple[Any, ...] = (content_id,)
        else:
            sql = f"SELECT * FROM {table} WHERE content_id=? AND staged=0"
            params = (content_id,)
        with self._lock:
            cur = self.connection.execute(sql, params)
            row = cur.fetchone()
            if row is None:
                return None
            cols = [d[0] for d in cur.description]
            return dict(zip(cols, row))

    def list_rows(
        self,
        tool_name: str,
        staged: Optional[int] = None,
        plan_id: Optional[str] = None,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        table = self._require_table(tool_name)
        where: List[str] = []
        params: List[Any] = []
        if staged is not None:
            where.append("staged=?")
            params.append(int(staged))
        if plan_id is not None:
            where.append("plan_id=?")
            params.append(plan_id)
        if filters:
            for key, value in filters.items():
                # Only allow whitelisted filter columns to avoid SQL
                # injection via field names.
                if key not in {
                    "content_id",
                    "display_name",
                    "tier",
                    "biome",
                    "faction_id",
                    "source_bundle_id",
                }:
                    continue
                where.append(f"{key}=?")
                params.append(value)
        clause = (" WHERE " + " AND ".join(where)) if where else ""
        sql = f"SELECT * FROM {table}{clause} ORDER BY created_at ASC"
        with self._lock:
            cur = self.connection.execute(sql, tuple(params))
            cols = [d[0] for d in cur.description]
            return [dict(zip(cols, r)) for r in cur.fetchall()]

    def count_rows(
        self,
        tool_name: str,
        staged: Optional[int] = None,
        filters: Optional[Dict[str, Any]] = None,
    ) -> int:
        table = self._require_table(tool_name)
        where: List[str] = []
        params: List[Any] = []
        if staged is not None:
            where.append("staged=?")
            params.append(int(staged))
        if filters:
            for key, value in filters.items():
                if key not in {
                    "tier",
                    "biome",
                    "faction_id",
                }:
                    continue
                where.append(f"{key}=?")
                params.append(value)
        clause = (" WHERE " + " AND ".join(where)) if where else ""
        sql = f"SELECT COUNT(*) FROM {table}{clause}"
        with self._lock:
            cur = self.connection.execute(sql, tuple(params))
            return int(cur.fetchone()[0])

    def xrefs_referencing(
        self, ref_type: str, ref_id: str
    ) -> List[Dict[str, Any]]:
        with self._lock:
            cur = self.connection.execute(
                "SELECT * FROM content_xref "
                "WHERE ref_type=? AND ref_id=?",
                (ref_type, ref_id),
            )
            cols = [d[0] for d in cur.description]
            return [dict(zip(cols, r)) for r in cur.fetchall()]

    def xrefs_for_plan(self, plan_id: str) -> List[Dict[str, Any]]:
        with self._lock:
            cur = self.connection.execute(
                "SELECT * FROM content_xref WHERE plan_id=?",
                (plan_id,),
            )
            cols = [d[0] for d in cur.description]
            return [dict(zip(cols, r)) for r in cur.fetchall()]

    def all_xrefs(self) -> List[Dict[str, Any]]:
        with self._lock:
            cur = self.connection.execute("SELECT * FROM content_xref")
            cols = [d[0] for d in cur.description]
            return [dict(zip(cols, r)) for r in cur.fetchall()]

    # ── Lineage ──────────────────────────────────────────────────────

    def find_row_anywhere(self, content_id: str) -> Optional[Dict[str, Any]]:
        """Search every ``reg_<tool>`` table for a row with this id.

        Returns the first hit as a dict (``tool_name`` key added) or
        None. Used by ``ContentRegistry.lineage``.
        """
        with self._lock:
            for tool_name, table in TOOL_TABLE.items():
                cur = self.connection.execute(
                    f"SELECT * FROM {table} WHERE content_id=?",
                    (content_id,),
                )
                row = cur.fetchone()
                if row is None:
                    continue
                cols = [d[0] for d in cur.description]
                d = dict(zip(cols, row))
                d["tool_name"] = tool_name
                return d
        return None

    # ── Utilities ────────────────────────────────────────────────────

    @staticmethod
    def serialize_payload(payload: Dict[str, Any]) -> str:
        return json.dumps(payload, sort_keys=True, separators=(",", ":"))

    @staticmethod
    def deserialize_payload(text: str) -> Dict[str, Any]:
        if not text:
            return {}
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return {}

    def _require_table(self, tool_name: str) -> str:
        if tool_name not in VALID_TOOLS or tool_name not in TOOL_TABLE:
            raise ValueError(
                f"Unknown tool_name '{tool_name}'; expected one of "
                f"{sorted(VALID_TOOLS)}"
            )
        return TOOL_TABLE[tool_name]

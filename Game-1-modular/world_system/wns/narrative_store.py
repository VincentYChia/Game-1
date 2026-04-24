"""Narrative Store — SQLite schema + CRUD for WNS events.

Completely separate from the WMS event store. The database file is
``world_narrative.db`` inside the save directory (sibling of
``world_memory.db``). Per §4.10 of the working doc and CC5, WNS and WMS
are sibling systems — they share patterns but not infrastructure.

Schema (per-layer tables + junctions):

- ``nl1_events`` .. ``nl7_events`` — one row per captured narrative event.
- ``nl1_tags`` .. ``nl7_tags``    — tag junction (event_id, tag).
- Address index on each ``nl<N>_events`` table (``address`` column).

Row fields (per working doc scope comment):
``id, created_at, layer, address, narrative, payload_json, tags_json``.
"""

from __future__ import annotations

import json
import os
import sqlite3
import threading
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple


SCHEMA_VERSION = 1

# The set of NL layers WNS stores. NL1 is deterministic capture; NL2-NL7
# are LLM weaving outputs.
ALL_LAYERS: Tuple[int, ...] = (1, 2, 3, 4, 5, 6, 7)


@dataclass
class NarrativeRow:
    """One row in an ``nl<N>_events`` table."""

    id: str
    created_at: float
    layer: int
    address: str
    narrative: str
    tags: List[str] = field(default_factory=list)
    payload: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "created_at": float(self.created_at),
            "layer": int(self.layer),
            "address": self.address,
            "narrative": self.narrative,
            "tags": list(self.tags),
            "payload": dict(self.payload),
        }

    @classmethod
    def from_sql_row(cls, row: sqlite3.Row, tags: List[str]) -> "NarrativeRow":
        payload_json = row["payload_json"] or "{}"
        try:
            payload = json.loads(payload_json)
        except (json.JSONDecodeError, TypeError):
            payload = {}
        return cls(
            id=row["id"],
            created_at=float(row["created_at"]),
            layer=int(row["layer"]),
            address=row["address"],
            narrative=row["narrative"] or "",
            tags=list(tags),
            payload=payload,
        )


class NarrativeStore:
    """SQLite-backed per-layer storage for WNS.

    One connection, one file (``world_narrative.db``). Not a singleton —
    the facade :class:`WorldNarrativeSystem` owns the instance. This keeps
    tests isolated (each test can construct its own in-memory store).
    """

    DEFAULT_DB_FILENAME = "world_narrative.db"

    def __init__(self, db_path: str) -> None:
        """Open or create a WNS SQLite database.

        Args:
            db_path: Full path to the .db file. Use ``":memory:"`` for
                tests.
        """
        self._db_path = db_path
        self._lock = threading.Lock()

        if db_path != ":memory:":
            os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)

        self._conn = sqlite3.connect(
            db_path, check_same_thread=False, isolation_level=None,
        )
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA foreign_keys = ON;")
        self._create_schema()

    # ── Schema ───────────────────────────────────────────────────────

    def _create_schema(self) -> None:
        with self._lock:
            cur = self._conn.cursor()
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS wns_meta (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                )
                """
            )
            cur.execute(
                "INSERT OR IGNORE INTO wns_meta (key, value) VALUES (?, ?)",
                ("schema_version", str(SCHEMA_VERSION)),
            )

            for n in ALL_LAYERS:
                cur.execute(
                    f"""
                    CREATE TABLE IF NOT EXISTS nl{n}_events (
                        id           TEXT PRIMARY KEY,
                        created_at   REAL NOT NULL,
                        layer        INTEGER NOT NULL,
                        address      TEXT NOT NULL,
                        narrative    TEXT NOT NULL DEFAULT '',
                        payload_json TEXT NOT NULL DEFAULT '{{}}',
                        tags_json    TEXT NOT NULL DEFAULT '[]'
                    )
                    """
                )
                cur.execute(
                    f"""
                    CREATE INDEX IF NOT EXISTS idx_nl{n}_address
                    ON nl{n}_events(address)
                    """
                )
                cur.execute(
                    f"""
                    CREATE TABLE IF NOT EXISTS nl{n}_tags (
                        event_id TEXT NOT NULL,
                        tag      TEXT NOT NULL,
                        PRIMARY KEY (event_id, tag),
                        FOREIGN KEY (event_id) REFERENCES nl{n}_events(id)
                            ON DELETE CASCADE
                    )
                    """
                )
                cur.execute(
                    f"""
                    CREATE INDEX IF NOT EXISTS idx_nl{n}_tags_tag
                    ON nl{n}_tags(tag)
                    """
                )

    # ── Insert ───────────────────────────────────────────────────────

    def insert_row(self, row: NarrativeRow) -> None:
        """Insert a narrative row + its tag junction entries."""
        self._require_valid_layer(row.layer)
        table = f"nl{row.layer}_events"
        tag_table = f"nl{row.layer}_tags"
        payload_json = json.dumps(row.payload, ensure_ascii=False)
        tags_json = json.dumps(list(row.tags), ensure_ascii=False)

        with self._lock:
            cur = self._conn.cursor()
            cur.execute(
                f"""
                INSERT INTO {table}
                    (id, created_at, layer, address, narrative,
                     payload_json, tags_json)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    row.id,
                    float(row.created_at),
                    int(row.layer),
                    row.address,
                    row.narrative,
                    payload_json,
                    tags_json,
                ),
            )
            for tag in row.tags:
                cur.execute(
                    f"INSERT OR IGNORE INTO {tag_table} (event_id, tag) VALUES (?, ?)",
                    (row.id, tag),
                )

    # ── Queries ──────────────────────────────────────────────────────

    def get(self, layer: int, event_id: str) -> Optional[NarrativeRow]:
        self._require_valid_layer(layer)
        table = f"nl{layer}_events"
        with self._lock:
            cur = self._conn.cursor()
            cur.execute(f"SELECT * FROM {table} WHERE id = ?", (event_id,))
            r = cur.fetchone()
            if not r:
                return None
            tags = self._tags_for(layer, event_id, cur)
            return NarrativeRow.from_sql_row(r, tags)

    def query_by_address(
        self,
        layer: int,
        address: str,
        limit: int = 100,
    ) -> List[NarrativeRow]:
        """All events at ``layer`` whose ``address`` column matches.

        Ordered most-recent first.
        """
        self._require_valid_layer(layer)
        table = f"nl{layer}_events"
        with self._lock:
            cur = self._conn.cursor()
            cur.execute(
                f"""
                SELECT * FROM {table}
                WHERE address = ?
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (address, int(limit)),
            )
            rows = cur.fetchall()
            return [
                NarrativeRow.from_sql_row(r, self._tags_for(layer, r["id"], cur))
                for r in rows
            ]

    def query_by_layer(self, layer: int, limit: int = 100) -> List[NarrativeRow]:
        """All events at ``layer``, most-recent first."""
        self._require_valid_layer(layer)
        table = f"nl{layer}_events"
        with self._lock:
            cur = self._conn.cursor()
            cur.execute(
                f"SELECT * FROM {table} ORDER BY created_at DESC LIMIT ?",
                (int(limit),),
            )
            rows = cur.fetchall()
            return [
                NarrativeRow.from_sql_row(r, self._tags_for(layer, r["id"], cur))
                for r in rows
            ]

    def count_by_layer(self, layer: int) -> int:
        self._require_valid_layer(layer)
        with self._lock:
            cur = self._conn.cursor()
            cur.execute(f"SELECT COUNT(*) AS c FROM nl{layer}_events")
            row = cur.fetchone()
            return int(row["c"]) if row else 0

    # ── Internals ────────────────────────────────────────────────────

    def _require_valid_layer(self, layer: int) -> None:
        if layer not in ALL_LAYERS:
            raise ValueError(
                f"NarrativeStore: invalid layer {layer!r}; must be one of {ALL_LAYERS}"
            )

    def _tags_for(
        self,
        layer: int,
        event_id: str,
        cur: sqlite3.Cursor,
    ) -> List[str]:
        tag_table = f"nl{layer}_tags"
        cur.execute(
            f"SELECT tag FROM {tag_table} WHERE event_id = ?",
            (event_id,),
        )
        return [r["tag"] for r in cur.fetchall()]

    # ── Shutdown ─────────────────────────────────────────────────────

    def close(self) -> None:
        with self._lock:
            try:
                self._conn.close()
            except sqlite3.Error:
                pass

    @property
    def db_path(self) -> str:
        return self._db_path

    @property
    def stats(self) -> Dict[str, Any]:
        counts = {f"nl{n}": self.count_by_layer(n) for n in ALL_LAYERS}
        return {
            "db_path": self._db_path,
            "schema_version": SCHEMA_VERSION,
            "counts": counts,
            "total_rows": sum(counts.values()),
        }

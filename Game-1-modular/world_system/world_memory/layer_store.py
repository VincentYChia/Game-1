"""Per-layer SQL storage for the World Memory System (Layers 2-7).

Each layer (2-7) has its own table + junction table for tag-based retrieval.
This module manages creation, insertion, and querying across all layer tables.

Schema per layer:
- layer{N}_events: (id, narrative, origin_ids, game_time, category, severity, tags_json, ...)
- layer{N}_tags: (event_id, tag_category, tag_value) with index on (tag_category, tag_value)

Layer 1 (stats) is handled by StatStore directly — it has its own tags and
tag-intersection queries.  LayerStore does NOT duplicate Layer 1 data.
"""

from __future__ import annotations

import json
import sqlite3
import uuid
from typing import Any, Dict, List, Optional, Tuple

from world_system.world_memory.game_date import game_day as compute_game_day


class LayerStore:
    """Manages per-layer SQL tables for the World Memory System.

    Each layer has its own events table and tags junction table.
    Tag-based retrieval uses intersection queries on the junction tables.
    """

    def __init__(self, db_path: str = ":memory:"):
        self._db_path = db_path
        self._conn: Optional[sqlite3.Connection] = None
        self._ensure_connection()
        self._create_all_tables()

    def _ensure_connection(self) -> None:
        if self._conn is None:
            self._conn = sqlite3.connect(self._db_path)
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA foreign_keys=ON")
            self._conn.row_factory = sqlite3.Row

    @property
    def connection(self) -> sqlite3.Connection:
        self._ensure_connection()
        return self._conn

    def _create_all_tables(self) -> None:
        """Create tables for layers 2-7.

        Layer 1 (stats) is managed by StatStore — not duplicated here.
        """
        c = self.connection

        # Layer 2: Text events from evaluators
        c.execute("""
            CREATE TABLE IF NOT EXISTS layer2_events (
                id TEXT PRIMARY KEY,
                narrative TEXT NOT NULL,
                origin_stat_key TEXT NOT NULL,
                game_time REAL NOT NULL,
                real_time REAL NOT NULL,
                game_day INTEGER NOT NULL DEFAULT 0,
                category TEXT NOT NULL,
                severity TEXT NOT NULL,
                significance TEXT NOT NULL DEFAULT 'minor',
                tags_json TEXT DEFAULT '[]',
                evaluator_id TEXT
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS layer2_tags (
                event_id TEXT NOT NULL,
                tag_category TEXT NOT NULL,
                tag_value TEXT NOT NULL,
                FOREIGN KEY (event_id) REFERENCES layer2_events(id)
            )
        """)
        c.execute("CREATE INDEX IF NOT EXISTS idx_l2_tags ON layer2_tags(tag_category, tag_value)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_l2_tags_id ON layer2_tags(event_id)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_l2_time ON layer2_events(game_time)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_l2_cat ON layer2_events(category)")

        # Layers 3-7: Consolidated events (same schema pattern)
        for layer_num in range(3, 8):
            origin_col = f"origin_layer{layer_num - 1}_ids"
            table = f"layer{layer_num}_events"
            tag_table = f"layer{layer_num}_tags"

            c.execute(f"""
                CREATE TABLE IF NOT EXISTS {table} (
                    id TEXT PRIMARY KEY,
                    narrative TEXT NOT NULL,
                    {origin_col} TEXT NOT NULL DEFAULT '[]',
                    game_time REAL NOT NULL,
                    game_day INTEGER NOT NULL DEFAULT 0,
                    category TEXT NOT NULL,
                    severity TEXT NOT NULL,
                    significance TEXT NOT NULL DEFAULT 'minor',
                    tags_json TEXT DEFAULT '[]'
                )
            """)
            c.execute(f"""
                CREATE TABLE IF NOT EXISTS {tag_table} (
                    event_id TEXT NOT NULL,
                    tag_category TEXT NOT NULL,
                    tag_value TEXT NOT NULL,
                    FOREIGN KEY (event_id) REFERENCES {table}(id)
                )
            """)
            c.execute(f"CREATE INDEX IF NOT EXISTS idx_l{layer_num}_tags "
                      f"ON {tag_table}(tag_category, tag_value)")
            c.execute(f"CREATE INDEX IF NOT EXISTS idx_l{layer_num}_tags_id "
                      f"ON {tag_table}(event_id)")
            c.execute(f"CREATE INDEX IF NOT EXISTS idx_l{layer_num}_time "
                      f"ON {table}(game_time)")
            c.execute(f"CREATE INDEX IF NOT EXISTS idx_l{layer_num}_cat "
                      f"ON {table}(category)")

        c.commit()

    # ══════════════════════════════════════════════════════════════
    # LAYER 2-7: Events
    # ══════════════════════════════════════════════════════════════

    def insert_event(self, layer: int, narrative: str, game_time: float,
                     category: str, severity: str, significance: str,
                     tags: List[str], origin_ref: str = "",
                     evaluator_id: str = "", real_time: float = 0.0,
                     event_id: Optional[str] = None) -> str:
        """Insert an event at any layer (2-7). Returns the event id."""
        if layer < 2 or layer > 7:
            raise ValueError(f"Layer must be 2-7, got {layer}")

        event_id = event_id or str(uuid.uuid4())
        tags_json = json.dumps(tags)
        day = compute_game_day(game_time)
        c = self.connection
        table = f"layer{layer}_events"
        tag_table = f"layer{layer}_tags"

        if layer == 2:
            c.execute(f"""
                INSERT INTO {table}
                (id, narrative, origin_stat_key, game_time, game_day, real_time,
                 category, severity, significance, tags_json, evaluator_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (event_id, narrative, origin_ref, game_time, day, real_time,
                  category, severity, significance, tags_json, evaluator_id))
        else:
            origin_col = f"origin_layer{layer - 1}_ids"
            c.execute(f"""
                INSERT INTO {table}
                (id, narrative, {origin_col}, game_time, game_day,
                 category, severity, significance, tags_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (event_id, narrative, origin_ref, game_time, day,
                  category, severity, significance, tags_json))

        # Insert tags into junction table
        for tag in tags:
            if ":" in tag:
                cat, val = tag.split(":", 1)
                c.execute(f"INSERT INTO {tag_table} (event_id, tag_category, tag_value) "
                          "VALUES (?, ?, ?)", (event_id, cat, val))

        c.commit()
        return event_id

    # ══════════════════════════════════════════════════════════════
    # TAG-BASED RETRIEVAL
    # ══════════════════════════════════════════════════════════════

    def query_by_tags(self, layer: int, tags: List[str],
                      match_all: bool = True,
                      limit: int = 50,
                      since_game_time: Optional[float] = None) -> List[Dict[str, Any]]:
        """Query events at a layer by tag intersection.

        Args:
            layer: Which layer to search (2-7).
            tags: List of "category:value" tags to match.
            match_all: If True, ALL tags must match (AND). If False, ANY (OR).
            limit: Max results.
            since_game_time: Only events after this time.

        Returns:
            List of event dicts with all columns + tags.

        Note: Layer 1 (stats) queries should use StatStore.query_by_tags() directly.
        """
        if not tags:
            return []

        if layer == 1:
            raise ValueError("Layer 1 queries should use StatStore.query_by_tags()")

        c = self.connection

        table = f"layer{layer}_events"
        tag_table = f"layer{layer}_tags"

        # Build tag conditions
        tag_conditions = []
        params = []
        for tag in tags:
            if ":" in tag:
                cat, val = tag.split(":", 1)
                tag_conditions.append("(t.tag_category = ? AND t.tag_value = ?)")
                params.extend([cat, val])

        if not tag_conditions:
            return []

        tag_where = " OR ".join(tag_conditions)

        if match_all:
            # AND: event must have ALL tags
            query = f"""
                SELECT e.* FROM {table} e
                WHERE e.id IN (
                    SELECT event_id FROM {tag_table} t
                    WHERE {tag_where}
                    GROUP BY event_id
                    HAVING COUNT(DISTINCT t.tag_category || ':' || t.tag_value) >= ?
                )
            """
            params.append(len(tags))
        else:
            # OR: event must have ANY tag
            query = f"""
                SELECT DISTINCT e.* FROM {table} e
                JOIN {tag_table} t ON e.id = t.event_id
                WHERE {tag_where}
            """

        if since_game_time is not None:
            query += " AND e.game_time >= ?"
            params.append(since_game_time)

        query += f" ORDER BY e.game_time DESC LIMIT ?"
        params.append(limit)

        rows = c.execute(query, params).fetchall()
        return [self._row_to_dict(row) for row in rows]

    def get_tags_for_event(self, layer: int, event_id: str) -> List[str]:
        """Get all tags for a specific event (layers 2-7)."""
        if layer < 2:
            raise ValueError("Layer 1 tags: use StatStore.get_with_meta()")
        tag_table = f"layer{layer}_tags"
        id_col = "event_id"
        c = self.connection
        rows = c.execute(
            f"SELECT tag_category, tag_value FROM {tag_table} WHERE {id_col} = ?",
            (event_id,)
        ).fetchall()
        return [f"{row['tag_category']}:{row['tag_value']}" for row in rows]

    def count_by_tags(self, layer: int, tags: List[str],
                      match_all: bool = True) -> int:
        """Count events matching tags at a layer (2-7 only).

        Layer 1 stats: use StatStore.query_by_tags() instead.
        """
        if not tags or layer < 2 or layer > 7:
            return 0

        c = self.connection
        table = f"layer{layer}_tags"
        id_col = "event_id"

        tag_conditions = []
        params = []
        for tag in tags:
            if ":" in tag:
                cat, val = tag.split(":", 1)
                tag_conditions.append("(tag_category = ? AND tag_value = ?)")
                params.extend([cat, val])

        if not tag_conditions:
            return 0

        tag_where = " OR ".join(tag_conditions)

        if match_all:
            query = f"""
                SELECT COUNT(DISTINCT {id_col}) FROM {table}
                WHERE {id_col} IN (
                    SELECT {id_col} FROM {table}
                    WHERE {tag_where}
                    GROUP BY {id_col}
                    HAVING COUNT(DISTINCT tag_category || ':' || tag_value) >= ?
                )
            """
            params.append(len(tags))
        else:
            query = f"SELECT COUNT(DISTINCT {id_col}) FROM {table} WHERE {tag_where}"

        return c.execute(query, params).fetchone()[0]

    # ══════════════════════════════════════════════════════════════
    # UTILITIES
    # ══════════════════════════════════════════════════════════════

    def _row_to_dict(self, row: sqlite3.Row) -> Dict[str, Any]:
        """Convert a sqlite3.Row to a dict with parsed tags."""
        d = dict(row)
        if "tags_json" in d:
            d["tags"] = json.loads(d["tags_json"])
            del d["tags_json"]
        return d

    def get_table_stats(self) -> Dict[str, int]:
        """Row counts for all layer tables (layers 2-7)."""
        c = self.connection
        stats = {}
        for layer in range(2, 8):
            table = f"layer{layer}_events"
            tag_table = f"layer{layer}_tags"
            try:
                stats[table] = c.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                stats[tag_table] = c.execute(f"SELECT COUNT(*) FROM {tag_table}").fetchone()[0]
            except sqlite3.OperationalError:
                stats[table] = 0
                stats[tag_table] = 0
        return stats

    def flush(self) -> None:
        """Force commit."""
        if self._conn:
            self._conn.commit()

    def close(self) -> None:
        """Close the database connection."""
        if self._conn:
            self._conn.close()
            self._conn = None

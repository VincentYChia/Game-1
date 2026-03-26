"""SQL-backed stat storage for Layer 1 of the World Memory System.

Single flat table with hierarchical keys.  Every stat is a row.
Automatic dimensional breakdowns create rows on demand — new enemies,
regions, weapons get tracked without code changes.

Schema:
    CREATE TABLE stats (
        key TEXT PRIMARY KEY,
        count INTEGER DEFAULT 0,
        total REAL DEFAULT 0.0,
        max_value REAL DEFAULT 0.0,
        updated_at REAL DEFAULT 0.0
    );

Example keys:
    combat.kills                           → total kills
    combat.kills.species.wolf              → wolf kills
    combat.kills.tier.1                    → tier 1 kills
    combat.kills.location.whispering_woods → kills in that locality
    combat.damage_dealt                    → total damage
    combat.damage_dealt.type.fire          → fire damage
    gathering.resource.iron_ore            → iron gathered
    crafting.discipline.smithing.success   → successful smithing crafts
"""

from __future__ import annotations

import sqlite3
import time
from typing import Any, ClassVar, Dict, List, Optional, Tuple


# ── Schema DDL ──────────────────────────────────────────────────────

_STATS_SCHEMA = """
CREATE TABLE IF NOT EXISTS stats (
    key TEXT PRIMARY KEY,
    count INTEGER DEFAULT 0,
    total REAL DEFAULT 0.0,
    max_value REAL DEFAULT 0.0,
    updated_at REAL DEFAULT 0.0
);

CREATE INDEX IF NOT EXISTS idx_stats_prefix
    ON stats(key COLLATE NOCASE);
"""

# Precompiled UPSERT statement
_UPSERT_SQL = """
INSERT INTO stats (key, count, total, max_value, updated_at)
VALUES (?, 1, ?, ?, ?)
ON CONFLICT(key) DO UPDATE SET
    count = count + 1,
    total = total + excluded.total,
    max_value = MAX(max_value, excluded.max_value),
    updated_at = excluded.updated_at
"""

# For incrementing count only (value=1, no magnitude)
_UPSERT_COUNT_SQL = """
INSERT INTO stats (key, count, total, max_value, updated_at)
VALUES (?, 1, 1.0, 1.0, ?)
ON CONFLICT(key) DO UPDATE SET
    count = count + 1,
    total = total + 1.0,
    updated_at = excluded.updated_at
"""

# For setting a value directly (not incrementing)
_SET_SQL = """
INSERT INTO stats (key, count, total, max_value, updated_at)
VALUES (?, 0, ?, ?, ?)
ON CONFLICT(key) DO UPDATE SET
    total = excluded.total,
    max_value = MAX(max_value, excluded.max_value),
    updated_at = excluded.updated_at
"""


class StatStore:
    """SQL-backed stat storage.  One table, hierarchical keys.

    All writes use UPSERT — keys are created on first write.
    Reads are O(1) by key or O(n) by prefix scan.
    """

    _instance: ClassVar[Optional[StatStore]] = None

    def __init__(self, conn: Optional[sqlite3.Connection] = None,
                 db_path: Optional[str] = None):
        """Initialize with an existing connection or a new database.

        Args:
            conn: Existing SQLite connection (shared with EventStore).
            db_path: Path to create/open a standalone database.
        """
        self._owns_conn = False
        if conn:
            self._conn = conn
        elif db_path:
            self._conn = sqlite3.connect(db_path, check_same_thread=False)
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._owns_conn = True
        else:
            # In-memory for testing
            self._conn = sqlite3.connect(":memory:", check_same_thread=False)
            self._owns_conn = True

        self._conn.executescript(_STATS_SCHEMA)
        self._conn.commit()

    @classmethod
    def get_instance(cls) -> StatStore:
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        if cls._instance and cls._instance._owns_conn:
            cls._instance.close()
        cls._instance = None

    # ── Core write operations ───────────────────────────────────────

    def record(self, key: str, value: float = 1.0,
               timestamp: Optional[float] = None) -> None:
        """Increment a stat.  Creates the row if it doesn't exist.

        Args:
            key: Hierarchical stat key (e.g. "combat.kills.species.wolf").
            value: The magnitude to add to total and compare for max.
            timestamp: Override for updated_at (defaults to time.time()).
        """
        ts = timestamp or time.time()
        self._conn.execute(_UPSERT_SQL, (key, value, value, ts))

    def record_multi(self, keys: List[str], value: float = 1.0,
                     timestamp: Optional[float] = None) -> None:
        """Increment multiple stats atomically in a single transaction.

        All keys get the same value.  This is the primary method for
        dimensional breakdowns — one game action writes many stat keys.
        """
        ts = timestamp or time.time()
        with self._conn:
            self._conn.executemany(
                _UPSERT_SQL,
                [(k, value, value, ts) for k in keys],
            )

    def record_count(self, key: str,
                     timestamp: Optional[float] = None) -> None:
        """Increment a simple counter (count +1, total +1, no magnitude)."""
        ts = timestamp or time.time()
        self._conn.execute(_UPSERT_COUNT_SQL, (key, ts))

    def record_count_multi(self, keys: List[str],
                           timestamp: Optional[float] = None) -> None:
        """Increment multiple simple counters atomically."""
        ts = timestamp or time.time()
        with self._conn:
            self._conn.executemany(
                _UPSERT_COUNT_SQL,
                [(k, ts) for k in keys],
            )

    def set_value(self, key: str, value: float,
                  timestamp: Optional[float] = None) -> None:
        """Set a stat's total to a specific value (not increment).

        Useful for gauges like current_gold, current_health, etc.
        Still tracks max_value across all sets.
        """
        ts = timestamp or time.time()
        self._conn.execute(_SET_SQL, (key, value, value, ts))

    def flush(self) -> None:
        """Ensure all writes are committed to disk."""
        self._conn.commit()

    # ── Core read operations ────────────────────────────────────────

    def get(self, key: str) -> Optional[Tuple[int, float, float]]:
        """Get (count, total, max_value) for a single key.

        Returns None if the key doesn't exist.
        """
        row = self._conn.execute(
            "SELECT count, total, max_value FROM stats WHERE key = ?",
            (key,),
        ).fetchone()
        return (row[0], row[1], row[2]) if row else None

    def get_count(self, key: str) -> int:
        """Get just the count for a key.  Returns 0 if missing."""
        row = self._conn.execute(
            "SELECT count FROM stats WHERE key = ?", (key,),
        ).fetchone()
        return row[0] if row else 0

    def get_total(self, key: str) -> float:
        """Get just the total for a key.  Returns 0.0 if missing."""
        row = self._conn.execute(
            "SELECT total FROM stats WHERE key = ?", (key,),
        ).fetchone()
        return row[0] if row else 0.0

    def get_max(self, key: str) -> float:
        """Get just the max_value for a key.  Returns 0.0 if missing."""
        row = self._conn.execute(
            "SELECT max_value FROM stats WHERE key = ?", (key,),
        ).fetchone()
        return row[0] if row else 0.0

    def get_prefix(self, prefix: str,
                   limit: int = 1000) -> Dict[str, Tuple[int, float, float]]:
        """Get all stats whose key starts with prefix.

        Returns {key: (count, total, max_value)}.
        Example: get_prefix("combat.kills.species.") returns all species kill stats.
        """
        rows = self._conn.execute(
            "SELECT key, count, total, max_value FROM stats "
            "WHERE key LIKE ? || '%' ORDER BY key LIMIT ?",
            (prefix, limit),
        ).fetchall()
        return {r[0]: (r[1], r[2], r[3]) for r in rows}

    def get_all(self) -> Dict[str, Tuple[int, float, float]]:
        """Get all stats.  Use sparingly — for serialization/debugging."""
        rows = self._conn.execute(
            "SELECT key, count, total, max_value FROM stats ORDER BY key"
        ).fetchall()
        return {r[0]: (r[1], r[2], r[3]) for r in rows}

    def get_stat_count(self) -> int:
        """Total number of distinct stat keys."""
        row = self._conn.execute("SELECT COUNT(*) FROM stats").fetchone()
        return row[0] if row else 0

    # ── Bulk import (for old save migration) ────────────────────────

    def import_flat(self, data: Dict[str, Any],
                    timestamp: Optional[float] = None) -> int:
        """Import a flat dict of {key: value} pairs.

        Values can be int/float (treated as total) or
        dict with count/total/max_value fields.
        Returns the number of keys imported.
        """
        ts = timestamp or time.time()
        imported = 0
        with self._conn:
            for key, val in data.items():
                if isinstance(val, dict):
                    count = val.get("count", 0)
                    total = val.get("total_value", val.get("total", 0.0))
                    max_v = val.get("max_value", val.get("max", 0.0))
                else:
                    count = int(val) if isinstance(val, (int, float)) else 0
                    total = float(val) if isinstance(val, (int, float)) else 0.0
                    max_v = total
                self._conn.execute(
                    """INSERT OR REPLACE INTO stats
                       (key, count, total, max_value, updated_at)
                       VALUES (?, ?, ?, ?, ?)""",
                    (key, count, total, max_v, ts),
                )
                imported += 1
        return imported

    # ── Cleanup ─────────────────────────────────────────────────────

    def close(self) -> None:
        if self._conn and self._owns_conn:
            self._conn.close()
            self._conn = None

    def clear(self) -> None:
        """Delete all stats.  For testing only."""
        self._conn.execute("DELETE FROM stats")
        self._conn.commit()


# ── Dimensional breakdown helpers ───────────────────────────────────

def _safe_key(value: Any) -> str:
    """Sanitize a value for use as a stat key component."""
    s = str(value).lower().strip()
    # Replace spaces and special chars with underscores
    return s.replace(" ", "_").replace("-", "_").replace(".", "_")


def build_dimensional_keys(base: str,
                           dimensions: Dict[str, Any]) -> List[str]:
    """Build a list of hierarchical stat keys from a base and dimensions.

    Args:
        base: The root key (e.g. "combat.kills", "gathering.resource")
        dimensions: {dimension_name: value} pairs to create breakdowns.
            Values of None or empty string are skipped.

    Returns:
        List of keys: [base, base.dim1.val1, base.dim2.val2, ...]

    Example:
        build_dimensional_keys("combat.kills", {
            "species": "wolf",
            "tier": 1,
            "location": "whispering_woods",
            "element": "fire",
        })
        → [
            "combat.kills",
            "combat.kills.species.wolf",
            "combat.kills.tier.1",
            "combat.kills.location.whispering_woods",
            "combat.kills.element.fire",
        ]
    """
    keys = [base]
    for dim_name, dim_value in dimensions.items():
        if dim_value is not None and dim_value != "" and dim_value != "unknown":
            keys.append(f"{base}.{dim_name}.{_safe_key(dim_value)}")
    return keys

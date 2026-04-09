"""Layer 1 of the World Memory System — SQL-backed stat storage.

Layer 1 is pure cumulative counters.  No events, no narratives, just numbers.
Every stat is a single row: (name, value, tags, description).

Dimensional breakdowns create rows on demand — new enemies, regions, weapons
get tracked without code changes.  Tags and descriptions are populated from
a manifest on first write, enabling tag-intersection queries and LLM-readable
descriptions for downstream layers.

Schema:
    CREATE TABLE stats (
        name TEXT PRIMARY KEY,
        value REAL DEFAULT 0.0,
        tags TEXT DEFAULT '[]',
        description TEXT DEFAULT '',
        updated_at REAL DEFAULT 0.0
    );

    CREATE TABLE stat_tags (
        name TEXT NOT NULL,
        tag_category TEXT NOT NULL,
        tag_value TEXT NOT NULL
    );

Example:
    name:        "combat.kills.species.wolf"
    value:       47.0
    tags:        '["domain:combat", "action:kill", "species:wolf"]'
    description: "Wolves killed by player"
"""

from __future__ import annotations

import json
import sqlite3
import time
from typing import Any, ClassVar, Dict, List, Optional


# ── Schema DDL ──────────────────────────────────────────────────────

_STATS_SCHEMA = """
CREATE TABLE IF NOT EXISTS stats (
    name TEXT PRIMARY KEY,
    value REAL DEFAULT 0.0,
    tags TEXT DEFAULT '[]',
    description TEXT DEFAULT '',
    updated_at REAL DEFAULT 0.0
);

CREATE INDEX IF NOT EXISTS idx_stats_prefix
    ON stats(name COLLATE NOCASE);

CREATE TABLE IF NOT EXISTS stat_tags (
    name TEXT NOT NULL,
    tag_category TEXT NOT NULL,
    tag_value TEXT NOT NULL,
    FOREIGN KEY (name) REFERENCES stats(name) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_stat_tags
    ON stat_tags(tag_category, tag_value);

CREATE INDEX IF NOT EXISTS idx_stat_tags_name
    ON stat_tags(name);
"""

# ── Precompiled SQL ─────────────────────────────────────────────────

# Increment: value += amount
_INCREMENT_SQL = """
INSERT INTO stats (name, value, updated_at)
VALUES (?, ?, ?)
ON CONFLICT(name) DO UPDATE SET
    value = value + excluded.value,
    updated_at = excluded.updated_at
"""

# Set: value = new_value
_SET_SQL = """
INSERT INTO stats (name, value, updated_at)
VALUES (?, ?, ?)
ON CONFLICT(name) DO UPDATE SET
    value = excluded.value,
    updated_at = excluded.updated_at
"""

# Set max: value = max(current, new)
_SET_MAX_SQL = """
INSERT INTO stats (name, value, updated_at)
VALUES (?, ?, ?)
ON CONFLICT(name) DO UPDATE SET
    value = MAX(value, excluded.value),
    updated_at = excluded.updated_at
"""


class StatStore:
    """Layer 1 stat storage.  One table, hierarchical names, single value per stat.

    Three write operations:
        increment(name, amount)  — value += amount (counters, running totals)
        set_value(name, value)   — value = new_value (gauges, current state)
        set_max(name, value)     — value = max(current, new) (records, peaks)

    Tags and descriptions are populated from a manifest on first write.
    Tag-intersection queries via stat_tags junction table.
    """

    _instance: ClassVar[Optional[StatStore]] = None

    def __init__(self, conn: Optional[sqlite3.Connection] = None,
                 db_path: Optional[str] = None):
        self._owns_conn = False
        self._manifest: Dict[str, dict] = {}  # name_pattern → {tags, description}

        if conn:
            self._conn = conn
        elif db_path:
            self._conn = sqlite3.connect(db_path, check_same_thread=False)
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._owns_conn = True
        else:
            self._conn = sqlite3.connect(":memory:", check_same_thread=False)
            self._owns_conn = True

        self._conn.execute("PRAGMA foreign_keys=ON")
        self._conn.executescript(_STATS_SCHEMA)
        self._conn.commit()

        # Cache of names that already have tags populated
        self._tagged: set = set()
        self._load_existing_tagged()

    def _load_existing_tagged(self) -> None:
        """Load names that already have tags in the junction table."""
        rows = self._conn.execute(
            "SELECT DISTINCT name FROM stat_tags"
        ).fetchall()
        self._tagged = {r[0] for r in rows}

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

    # ── Manifest loading ───────────────────────────────────────────

    def load_manifest(self, manifest_path: str) -> int:
        """Load stat definitions manifest (name patterns → tags + descriptions).

        The manifest is a JSON file mapping stat name patterns to their
        tags and human-readable descriptions.  Patterns can use '*' as
        a wildcard segment.  When a stat is first written, its tags and
        description are looked up from the manifest.

        Returns number of patterns loaded.
        """
        import os
        if not os.path.exists(manifest_path):
            return 0

        with open(manifest_path) as f:
            data = json.load(f)

        patterns = data.get("patterns", {})
        self._manifest = patterns
        return len(patterns)

    def _lookup_manifest(self, name: str) -> Optional[dict]:
        """Find the best matching manifest entry for a stat name.

        Tries exact match first, then progressively wildcarded patterns.
        """
        # Exact match
        if name in self._manifest:
            return self._manifest[name]

        # Wildcard matching: replace segments from right with *
        parts = name.split(".")
        for i in range(len(parts) - 1, 0, -1):
            pattern = ".".join(parts[:i]) + ".*"
            if pattern in self._manifest:
                return self._manifest[pattern]
            # Try double wildcard: base.*.* etc
            if i >= 2:
                pattern2 = ".".join(parts[:i-1]) + ".*.*"
                if pattern2 in self._manifest:
                    return self._manifest[pattern2]

        return None

    def _ensure_tags(self, name: str) -> None:
        """Populate tags and description for a stat from the manifest.

        Called on first write.  If no manifest entry exists, derives
        basic tags from the name structure (e.g., "combat.kills.species.wolf"
        → ["domain:combat", "species:wolf"]).
        """
        if name in self._tagged:
            return

        entry = self._lookup_manifest(name)
        if entry:
            tags = list(entry.get("tags", []))
            desc = entry.get("description", "")
            # Resolve {dim} placeholders from the name.
            # Pattern "combat.kills.species.*" matched "combat.kills.species.wolf"
            # Tags like "species:{dim}" should become "species:wolf"
            # {dim} = the last segment of the name (the wildcard value)
            parts = name.split(".")
            wildcard_value = parts[-1] if len(parts) >= 2 else ""
            resolved_tags = []
            for tag in tags:
                if "{dim}" in tag:
                    resolved_tags.append(tag.replace("{dim}", wildcard_value))
                else:
                    resolved_tags.append(tag)
            tags = resolved_tags
        else:
            # Derive from name structure
            tags = self._derive_tags(name)
            desc = ""

        if tags or desc:
            self._write_metadata(name, tags, desc)

        self._tagged.add(name)

    def _derive_tags(self, name: str) -> List[str]:
        """Derive basic tags from the stat name structure.

        "combat.kills.species.wolf" → ["domain:combat", "species:wolf"]
        "gathering.collected.resource.iron_ore" → ["domain:gathering", "resource:iron_ore"]
        """
        parts = name.split(".")
        tags = []
        if parts:
            tags.append(f"domain:{parts[0]}")
        # Parse dimension.value pairs from the name
        i = 2  # Skip base (e.g., "combat.kills")
        while i + 1 < len(parts):
            dim = parts[i]
            val = parts[i + 1]
            tags.append(f"{dim}:{val}")
            i += 2
        return tags

    def _write_metadata(self, name: str, tags: List[str],
                        description: str) -> None:
        """Write tags and description to the stats row and junction table."""
        tags_json = json.dumps(tags)
        self._conn.execute(
            "UPDATE stats SET tags = ?, description = ? WHERE name = ?",
            (tags_json, description, name)
        )
        # If the row doesn't exist yet (UPDATE affected 0 rows), it will
        # be created by the UPSERT in increment/set_value/set_max.
        # We'll write junction tags after the UPSERT ensures the row exists.
        self._conn.execute("DELETE FROM stat_tags WHERE name = ?", (name,))
        for tag in tags:
            if ":" in tag:
                cat, val = tag.split(":", 1)
                self._conn.execute(
                    "INSERT INTO stat_tags (name, tag_category, tag_value) "
                    "VALUES (?, ?, ?)", (name, cat, val)
                )

    # ── Core write operations ──────────────────────────────────────

    def increment(self, name: str, amount: float = 1.0,
                  timestamp: Optional[float] = None) -> None:
        """Increment a stat's value.  Creates the row if it doesn't exist.

        This is the primary write for counters and running totals.
        For a kill count: increment("combat.kills.species.wolf")
        For damage dealt: increment("combat.damage_dealt", amount=50.0)
        """
        ts = timestamp or time.time()
        self._conn.execute(_INCREMENT_SQL, (name, amount, ts))
        self._ensure_tags(name)

    def increment_multi(self, names: List[str], amount: float = 1.0,
                        timestamp: Optional[float] = None) -> None:
        """Increment multiple stats atomically.

        All names get the same amount.  This is the primary method for
        dimensional breakdowns — one game action writes many stat names.
        """
        ts = timestamp or time.time()
        with self._conn:
            self._conn.executemany(
                _INCREMENT_SQL,
                [(n, amount, ts) for n in names],
            )
        for n in names:
            self._ensure_tags(n)

    def set_value(self, name: str, value: float,
                  timestamp: Optional[float] = None) -> None:
        """Set a stat to a specific value (not increment).

        For gauges: set_value("progression.current_level", 15.0)
        """
        ts = timestamp or time.time()
        self._conn.execute(_SET_SQL, (name, value, ts))
        self._ensure_tags(name)

    def set_max(self, name: str, value: float,
                timestamp: Optional[float] = None) -> None:
        """Set a stat only if the new value exceeds the current.

        For records: set_max("combat.longest_killstreak", 12.0)
        """
        ts = timestamp or time.time()
        self._conn.execute(_SET_MAX_SQL, (name, value, ts))
        self._ensure_tags(name)

    def flush(self) -> None:
        """Ensure all writes are committed to disk."""
        self._conn.commit()

    # ── Core read operations ───────────────────────────────────────

    def get(self, name: str) -> float:
        """Get the value of a stat.  Returns 0.0 if missing."""
        row = self._conn.execute(
            "SELECT value FROM stats WHERE name = ?", (name,),
        ).fetchone()
        return row[0] if row else 0.0

    def get_with_meta(self, name: str) -> Optional[dict]:
        """Get a stat with all its metadata.

        Returns {name, value, tags, description, updated_at} or None.
        """
        row = self._conn.execute(
            "SELECT name, value, tags, description, updated_at "
            "FROM stats WHERE name = ?", (name,),
        ).fetchone()
        if not row:
            return None
        return {
            "name": row[0],
            "value": row[1],
            "tags": json.loads(row[2]) if row[2] else [],
            "description": row[3] or "",
            "updated_at": row[4],
        }

    def get_prefix(self, prefix: str,
                   limit: int = 1000) -> Dict[str, float]:
        """Get all stats whose name starts with prefix.

        Returns {name: value}.
        """
        rows = self._conn.execute(
            "SELECT name, value FROM stats "
            "WHERE name LIKE ? || '%' AND value != 0.0 "
            "ORDER BY name LIMIT ?",
            (prefix, limit),
        ).fetchall()
        return {r[0]: r[1] for r in rows}

    def get_prefix_with_meta(self, prefix: str,
                             limit: int = 1000) -> List[dict]:
        """Get all stats with metadata whose name starts with prefix.

        Returns list of {name, value, tags, description}.
        Only returns stats with non-zero values.
        """
        rows = self._conn.execute(
            "SELECT name, value, tags, description FROM stats "
            "WHERE name LIKE ? || '%' AND value != 0.0 "
            "ORDER BY name LIMIT ?",
            (prefix, limit),
        ).fetchall()
        return [
            {
                "name": r[0], "value": r[1],
                "tags": json.loads(r[2]) if r[2] else [],
                "description": r[3] or "",
            }
            for r in rows
        ]

    def get_all(self) -> Dict[str, float]:
        """Get all stats with non-zero values.  For serialization."""
        rows = self._conn.execute(
            "SELECT name, value FROM stats WHERE value != 0.0 ORDER BY name"
        ).fetchall()
        return {r[0]: r[1] for r in rows}

    def get_all_with_meta(self) -> List[dict]:
        """Get all stats with metadata.  For full export."""
        rows = self._conn.execute(
            "SELECT name, value, tags, description, updated_at "
            "FROM stats WHERE value != 0.0 ORDER BY name"
        ).fetchall()
        return [
            {
                "name": r[0], "value": r[1],
                "tags": json.loads(r[2]) if r[2] else [],
                "description": r[3] or "",
                "updated_at": r[4],
            }
            for r in rows
        ]

    def get_stat_count(self) -> int:
        """Total number of stats with non-zero values."""
        row = self._conn.execute(
            "SELECT COUNT(*) FROM stats WHERE value != 0.0"
        ).fetchone()
        return row[0] if row else 0

    # ── Tag-based queries ──────────────────────────────────────────

    def query_by_tags(self, tags: List[str],
                      match_all: bool = True,
                      limit: int = 100) -> List[dict]:
        """Query stats by tag intersection.

        Args:
            tags: List of "category:value" tags to match.
            match_all: If True, ALL tags must match (AND). If False, ANY (OR).
            limit: Max results.

        Returns list of {name, value, tags, description}.
        """
        if not tags:
            return []

        tag_conditions = []
        params: list = []
        for tag in tags:
            if ":" in tag:
                cat, val = tag.split(":", 1)
                tag_conditions.append(
                    "(t.tag_category = ? AND t.tag_value = ?)")
                params.extend([cat, val])

        if not tag_conditions:
            return []

        tag_where = " OR ".join(tag_conditions)

        if match_all:
            query = f"""
                SELECT s.name, s.value, s.tags, s.description
                FROM stats s
                WHERE s.value != 0.0 AND s.name IN (
                    SELECT name FROM stat_tags t
                    WHERE {tag_where}
                    GROUP BY name
                    HAVING COUNT(DISTINCT t.tag_category || ':' || t.tag_value) >= ?
                )
                ORDER BY s.value DESC LIMIT ?
            """
            params.extend([len(tags), limit])
        else:
            query = f"""
                SELECT DISTINCT s.name, s.value, s.tags, s.description
                FROM stats s
                JOIN stat_tags t ON s.name = t.name
                WHERE s.value != 0.0 AND ({tag_where})
                ORDER BY s.value DESC LIMIT ?
            """
            params.append(limit)

        rows = self._conn.execute(query, params).fetchall()
        return [
            {
                "name": r[0], "value": r[1],
                "tags": json.loads(r[2]) if r[2] else [],
                "description": r[3] or "",
            }
            for r in rows
        ]

    # ── Backward-compatible read methods ───────────────────────────
    # These maintain the old API so existing code doesn't break during
    # migration.  They all read from the single 'value' column.

    def get_count(self, name: str) -> int:
        """Backward compat: get value as int.  Same as int(get(name))."""
        return int(self.get(name))

    def get_total(self, name: str) -> float:
        """Backward compat: get value as float.  Same as get(name)."""
        return self.get(name)

    def get_max(self, name: str) -> float:
        """Backward compat: get value as float.  Same as get(name)."""
        return self.get(name)

    # ── Backward-compatible write methods ──────────────────────────
    # Bridge from old API (record/record_count/record_multi) to new.

    def record(self, key: str, value: float = 1.0,
               timestamp: Optional[float] = None) -> None:
        """Backward compat: increment by value.  Same as increment()."""
        self.increment(key, value, timestamp)

    def record_multi(self, keys: List[str], value: float = 1.0,
                     timestamp: Optional[float] = None) -> None:
        """Backward compat: batch increment.  Same as increment_multi()."""
        self.increment_multi(keys, value, timestamp)

    def record_count(self, key: str,
                     timestamp: Optional[float] = None) -> None:
        """Backward compat: increment by 1.  Same as increment(name)."""
        self.increment(key, 1.0, timestamp)

    def record_count_multi(self, keys: List[str],
                           timestamp: Optional[float] = None) -> None:
        """Backward compat: batch increment by 1."""
        self.increment_multi(keys, 1.0, timestamp)

    # ── Bulk import (for old save migration) ───────────────────────

    def import_flat(self, data: Dict[str, Any],
                    timestamp: Optional[float] = None) -> int:
        """Import a flat dict of {name: value} pairs.

        Values can be int/float (treated as value) or
        dict with count/total/max_value fields (old format — takes
        the most meaningful number: total if nonzero, else count).
        Returns the number of stats imported.
        """
        ts = timestamp or time.time()
        imported = 0
        with self._conn:
            for name, val in data.items():
                if isinstance(val, dict):
                    # Old format: pick the most meaningful number
                    total = val.get("total_value", val.get("total", 0.0))
                    count = val.get("count", 0)
                    value = total if total != 0.0 else float(count)
                else:
                    value = float(val) if isinstance(val, (int, float)) else 0.0
                self._conn.execute(
                    "INSERT OR REPLACE INTO stats (name, value, updated_at) "
                    "VALUES (?, ?, ?)",
                    (name, value, ts),
                )
                imported += 1
        return imported

    def prepopulate_from_manifest(self, manifest_path: str) -> int:
        """Pre-populate stats table from manifest with tags and descriptions.

        Uses INSERT OR IGNORE so existing data is preserved.
        Returns number of stats inserted.
        """
        import os
        if not os.path.exists(manifest_path):
            return 0

        existing = self._conn.execute(
            "SELECT COUNT(*) FROM stats"
        ).fetchone()[0]
        if existing > 100:
            return 0

        loaded = self.load_manifest(manifest_path)
        if not loaded:
            return 0

        count = 0
        with self._conn:
            for pattern, entry in self._manifest.items():
                if "*" in pattern:
                    continue  # Skip wildcard patterns, only prepopulate exact
                tags_json = json.dumps(entry.get("tags", []))
                desc = entry.get("description", "")
                self._conn.execute(
                    "INSERT OR IGNORE INTO stats "
                    "(name, value, tags, description, updated_at) "
                    "VALUES (?, 0.0, ?, ?, 0.0)",
                    (pattern, tags_json, desc),
                )
                count += 1
        self._conn.commit()
        return count

    # ── Cleanup ────────────────────────────────────────────────────

    def close(self) -> None:
        if self._conn and self._owns_conn:
            self._conn.close()
            self._conn = None

    def clear(self) -> None:
        """Delete all stats.  For testing only."""
        self._conn.execute("DELETE FROM stat_tags")
        self._conn.execute("DELETE FROM stats")
        self._conn.commit()
        self._tagged.clear()


# ── Dimensional breakdown helpers ─────────────────────────────────

def _safe_key(value: Any) -> str:
    """Sanitize a value for use as a stat name component."""
    s = str(value).lower().strip()
    return s.replace(" ", "_").replace("-", "_").replace(".", "_")


def build_dimensional_keys(base: str,
                           dimensions: Dict[str, Any]) -> List[str]:
    """Build a list of hierarchical stat names from a base and dimensions.

    Args:
        base: The root name (e.g. "combat.kills", "gathering.collected")
        dimensions: {dimension_name: value} pairs to create breakdowns.
            Values of None or empty string are skipped.

    Returns:
        List of names: [base, base.dim1.val1, base.dim2.val2, ...]

    Example:
        build_dimensional_keys("combat.kills", {
            "species": "wolf",
            "tier": 1,
            "location": "whispering_woods",
        })
        → [
            "combat.kills",
            "combat.kills.species.wolf",
            "combat.kills.tier.1",
            "combat.kills.location.whispering_woods",
        ]
    """
    keys = [base]
    for dim_name, dim_value in dimensions.items():
        if dim_value is not None and dim_value != "" and dim_value != "unknown":
            keys.append(f"{base}.{dim_name}.{_safe_key(dim_value)}")
    return keys

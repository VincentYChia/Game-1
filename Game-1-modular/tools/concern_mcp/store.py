"""ConceptStore -- the SQLite substrate for the concern registry.

Directly mirrors the WMS pattern (world_system/world_memory/layer_store.py):
a `concepts` table (≈ WMS events) and a `binding_sites` junction (≈ WMS tags),
indexed on the concept identity, queried by equality join. The AND-intersection
idiom and the (category, value) index are lifted from layer_store.py; the
relevance ranking is adapted from tag_relevance.py.

Concept id scheme: "{taxonomy}|{concept_kind}|{concept_value}" (pipe-delimited so
values containing ':' don't collide, and same value across taxonomies stays
distinct -- e.g. combat_effect|tag_value|fire  vs  wms|tag_value|fire).
"""

from __future__ import annotations

import json
import os
import sqlite3
import time
from typing import Any, Dict, List, Optional

SCHEMA_VERSION = 1


def make_concept_id(taxonomy: str, concept_kind: str, concept_value: str) -> str:
    return f"{taxonomy}|{concept_kind}|{concept_value}"


class ConceptStore:
    """SQLite-backed store of concepts + their binding sites + concept edges."""

    def __init__(self, db_path: str = ":memory:"):
        self._db_path = db_path
        self._conn: Optional[sqlite3.Connection] = None
        self._ensure_connection()
        self._create_all_tables()

    # ── connection ────────────────────────────────────────────────
    def _ensure_connection(self) -> None:
        if self._conn is None:
            parent = os.path.dirname(self._db_path)
            if parent and self._db_path != ":memory:":
                os.makedirs(parent, exist_ok=True)
            self._conn = sqlite3.connect(self._db_path)
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.row_factory = sqlite3.Row

    @property
    def connection(self) -> sqlite3.Connection:
        self._ensure_connection()
        return self._conn  # type: ignore[return-value]

    # ── schema ────────────────────────────────────────────────────
    def _create_all_tables(self) -> None:
        c = self.connection
        c.execute("""
            CREATE TABLE IF NOT EXISTS concepts (
                id            TEXT PRIMARY KEY,
                concept_kind  TEXT NOT NULL,
                concept_value TEXT NOT NULL,
                taxonomy      TEXT NOT NULL,
                authority_ref TEXT,
                aliases_json  TEXT DEFAULT '[]',
                is_dynamic    INTEGER DEFAULT 0,
                governance    TEXT,
                summary       TEXT
            )
        """)
        # The WMS signature index: (kind, value) -- our (tag_category, tag_value).
        c.execute("CREATE INDEX IF NOT EXISTS idx_concept_pair "
                  "ON concepts(concept_kind, concept_value)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_concept_value "
                  "ON concepts(concept_value)")

        c.execute("""
            CREATE TABLE IF NOT EXISTS binding_sites (
                concept_id     TEXT NOT NULL,
                site_kind      TEXT NOT NULL,
                language       TEXT NOT NULL,
                file           TEXT NOT NULL,
                line           INTEGER NOT NULL,
                locator_extra  TEXT,
                coupling_type  TEXT NOT NULL,
                role           TEXT NOT NULL,
                silent_failure TEXT,
                mirror_group   TEXT,
                pinned_by_test TEXT,
                editable       INTEGER DEFAULT 1,
                content_hash   TEXT,
                FOREIGN KEY (concept_id) REFERENCES concepts(id)
            )
        """)
        c.execute("CREATE INDEX IF NOT EXISTS idx_bs_concept ON binding_sites(concept_id)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_bs_mirror  ON binding_sites(mirror_group)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_bs_file    ON binding_sites(file)")
        # Dedup: one row per (concept, kind, file, line, coupling). INSERT OR IGNORE relies
        # on this. Tolerant of a pre-existing db that still holds duplicates (the next
        # wipe+rebuild produces a clean, dedup'd index).
        try:
            c.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_bs_unique "
                      "ON binding_sites(concept_id, site_kind, file, line, coupling_type)")
        except sqlite3.IntegrityError:
            pass

        c.execute("""
            CREATE TABLE IF NOT EXISTS concept_edges (
                src_concept_id TEXT NOT NULL,
                dst_concept_id TEXT NOT NULL,
                edge_kind      TEXT NOT NULL,
                note           TEXT
            )
        """)
        c.execute("CREATE INDEX IF NOT EXISTS idx_edge_src ON concept_edges(src_concept_id)")

        # Per-file content hash for incremental reindex (Merkle-style, §5).
        c.execute("""
            CREATE TABLE IF NOT EXISTS file_index (
                file         TEXT PRIMARY KEY,
                content_hash TEXT NOT NULL,
                indexed_at   REAL NOT NULL
            )
        """)
        # index_meta: schema-version hard gate (mirrors event_store SCHEMA_VERSION).
        c.execute("""
            CREATE TABLE IF NOT EXISTS index_meta (
                key   TEXT PRIMARY KEY,
                value TEXT
            )
        """)
        c.commit()
        self.set_meta("schema_version", str(SCHEMA_VERSION))

    # ── concepts ──────────────────────────────────────────────────
    def upsert_concept(self, concept_kind: str, concept_value: str, taxonomy: str,
                       authority_ref: Optional[str] = None,
                       aliases: Optional[List[str]] = None,
                       is_dynamic: int = 0, governance: Optional[str] = None,
                       summary: Optional[str] = None) -> str:
        cid = make_concept_id(taxonomy, concept_kind, concept_value)
        c = self.connection
        # Merge aliases with any existing on re-upsert.
        existing = self.get_concept(cid)
        merged_aliases = set(aliases or [])
        if existing:
            merged_aliases |= set(json.loads(existing.get("aliases_json") or "[]"))
            authority_ref = authority_ref or existing.get("authority_ref")
            governance = governance or existing.get("governance")
            summary = summary or existing.get("summary")
        c.execute("""
            INSERT INTO concepts
            (id, concept_kind, concept_value, taxonomy, authority_ref,
             aliases_json, is_dynamic, governance, summary)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                authority_ref=excluded.authority_ref,
                aliases_json=excluded.aliases_json,
                is_dynamic=excluded.is_dynamic,
                governance=excluded.governance,
                summary=excluded.summary
        """, (cid, concept_kind, concept_value, taxonomy, authority_ref,
              json.dumps(sorted(merged_aliases)), int(is_dynamic), governance, summary))
        c.commit()
        return cid

    def get_concept(self, concept_id: str) -> Optional[Dict[str, Any]]:
        row = self.connection.execute(
            "SELECT * FROM concepts WHERE id = ?", (concept_id,)).fetchone()
        return dict(row) if row else None

    def find_concepts_by_value(self, value: str,
                               kind: Optional[str] = None,
                               taxonomy: Optional[str] = None) -> List[Dict[str, Any]]:
        """Resolve a bare value ('fire', 'aoe', 'geometry') to concept row(s).

        Matches by exact value OR by alias membership. Optional kind/taxonomy filter.
        """
        c = self.connection
        # Case-insensitive on BOTH the canonical value and the alias list (aliases already
        # matched case-insensitively via LIKE; make the exact match match too, so blast('Fire')
        # == blast('fire')).
        clauses = ["(concept_value = ? COLLATE NOCASE OR aliases_json LIKE ? COLLATE NOCASE)"]
        params: List[Any] = [value, f'%"{value}"%']
        if kind:
            clauses.append("concept_kind = ?")
            params.append(kind)
        if taxonomy:
            clauses.append("taxonomy = ?")
            params.append(taxonomy)
        q = "SELECT * FROM concepts WHERE " + " AND ".join(clauses)
        return [dict(r) for r in c.execute(q, params).fetchall()]

    def all_concepts(self, kind: Optional[str] = None) -> List[Dict[str, Any]]:
        c = self.connection
        if kind:
            rows = c.execute("SELECT * FROM concepts WHERE concept_kind = ?", (kind,)).fetchall()
        else:
            rows = c.execute("SELECT * FROM concepts").fetchall()
        return [dict(r) for r in rows]

    def delete_concepts_by_taxonomy(self, taxonomy: str) -> None:
        """Authorities are re-parsed wholesale; drop then rebuild their concepts."""
        self.connection.execute("DELETE FROM concepts WHERE taxonomy = ?", (taxonomy,))
        self.connection.commit()

    # ── binding sites ─────────────────────────────────────────────
    def add_binding_site(self, concept_id: str, site_kind: str, language: str,
                         file: str, line: int, coupling_type: str, role: str,
                         silent_failure: Optional[str] = None,
                         mirror_group: Optional[str] = None,
                         pinned_by_test: Optional[str] = None,
                         editable: int = 1,
                         locator_extra: Optional[Dict[str, Any]] = None,
                         content_hash: Optional[str] = None) -> None:
        self.connection.execute("""
            INSERT OR IGNORE INTO binding_sites
            (concept_id, site_kind, language, file, line, locator_extra,
             coupling_type, role, silent_failure, mirror_group, pinned_by_test,
             editable, content_hash)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (concept_id, site_kind, language, file, int(line),
              json.dumps(locator_extra) if locator_extra else None,
              coupling_type, role, silent_failure, mirror_group, pinned_by_test,
              int(editable), content_hash))

    def sites_for_concept(self, concept_id: str) -> List[Dict[str, Any]]:
        rows = self.connection.execute(
            "SELECT * FROM binding_sites WHERE concept_id = ?", (concept_id,)).fetchall()
        return [self._site_to_dict(r) for r in rows]

    def sites_for_concepts(self, concept_ids: List[str]) -> List[Dict[str, Any]]:
        if not concept_ids:
            return []
        ph = ",".join("?" * len(concept_ids))
        rows = self.connection.execute(
            f"SELECT * FROM binding_sites WHERE concept_id IN ({ph})",
            concept_ids).fetchall()
        return [self._site_to_dict(r) for r in rows]

    def sites_in_mirror_group(self, mirror_group: str) -> List[Dict[str, Any]]:
        rows = self.connection.execute(
            "SELECT * FROM binding_sites WHERE mirror_group = ?", (mirror_group,)).fetchall()
        return [self._site_to_dict(r) for r in rows]

    def delete_sites_for_file(self, file: str) -> None:
        self.connection.execute("DELETE FROM binding_sites WHERE file = ?", (file,))
        self.connection.commit()

    @staticmethod
    def _site_to_dict(row: sqlite3.Row) -> Dict[str, Any]:
        d = dict(row)
        if d.get("locator_extra"):
            try:
                d["locator_extra"] = json.loads(d["locator_extra"])
            except (json.JSONDecodeError, TypeError):
                pass
        return d

    # ── edges ─────────────────────────────────────────────────────
    def add_edge(self, src_concept_id: str, dst_concept_id: str,
                 edge_kind: str, note: Optional[str] = None) -> None:
        self.connection.execute(
            "INSERT INTO concept_edges (src_concept_id, dst_concept_id, edge_kind, note) "
            "VALUES (?, ?, ?, ?)", (src_concept_id, dst_concept_id, edge_kind, note))

    def edges_for(self, concept_id: str) -> List[Dict[str, Any]]:
        rows = self.connection.execute(
            "SELECT * FROM concept_edges WHERE src_concept_id = ? OR dst_concept_id = ?",
            (concept_id, concept_id)).fetchall()
        return [dict(r) for r in rows]

    def clear_edges(self) -> None:
        self.connection.execute("DELETE FROM concept_edges")
        self.connection.commit()

    # ── file index / meta ─────────────────────────────────────────
    def get_file_hash(self, file: str) -> Optional[str]:
        row = self.connection.execute(
            "SELECT content_hash FROM file_index WHERE file = ?", (file,)).fetchone()
        return row["content_hash"] if row else None

    def set_file_hash(self, file: str, content_hash: str) -> None:
        self.connection.execute("""
            INSERT INTO file_index (file, content_hash, indexed_at) VALUES (?, ?, ?)
            ON CONFLICT(file) DO UPDATE SET content_hash=excluded.content_hash,
                                            indexed_at=excluded.indexed_at
        """, (file, content_hash, time.time()))

    def indexed_files(self) -> List[str]:
        return [r["file"] for r in self.connection.execute(
            "SELECT file FROM file_index").fetchall()]

    def get_meta(self, key: str) -> Optional[str]:
        row = self.connection.execute(
            "SELECT value FROM index_meta WHERE key = ?", (key,)).fetchone()
        return row["value"] if row else None

    def set_meta(self, key: str, value: str) -> None:
        self.connection.execute("""
            INSERT INTO index_meta (key, value) VALUES (?, ?)
            ON CONFLICT(key) DO UPDATE SET value=excluded.value
        """, (key, value))
        self.connection.commit()

    # ── stats / lifecycle ─────────────────────────────────────────
    def stats(self) -> Dict[str, int]:
        c = self.connection
        return {
            "concepts": c.execute("SELECT COUNT(*) FROM concepts").fetchone()[0],
            "binding_sites": c.execute("SELECT COUNT(*) FROM binding_sites").fetchone()[0],
            "concept_edges": c.execute("SELECT COUNT(*) FROM concept_edges").fetchone()[0],
            "indexed_files": c.execute("SELECT COUNT(*) FROM file_index").fetchone()[0],
        }

    def commit(self) -> None:
        if self._conn:
            self._conn.commit()

    def close(self) -> None:
        if self._conn:
            self._conn.commit()
            self._conn.close()
            self._conn = None

"""DbRowProbe -- live, READ-ONLY row counts against the on-disk WMS/WNS databases.

This is the decisive Scenario-2 gap-closer: every other extractor walks SOURCE, but a tag
rename leaves STALE ROWS in the SQLite junctions (runtime state, no source delta). This
probe opens the real .db files read-only and turns "the junction exists" into "N historical
rows in these tables need this UPDATE, plus a tags_json rewrite."

Not part of the index build -- invoked at query time by junction_map(concept).
"""

from __future__ import annotations

import glob
import os
import sqlite3
from typing import Any, Dict, List, Optional

from ..coordinates import STORES, DB_SEARCH_GLOBS

_PLACEHOLDER = "<NEW_VALUE>"


def _candidate_dirs(repo_root: str, db_name: str) -> List[str]:
    out: List[str] = []
    override = os.environ.get("CONCERN_WMS_DB_DIR")
    if override and os.path.isfile(os.path.join(override, db_name)):
        out.append(override)
    for pat in DB_SEARCH_GLOBS:
        for d in sorted(glob.glob(os.path.join(repo_root, pat)), reverse=True):
            if os.path.isfile(os.path.join(d, db_name)) and d not in out:
                out.append(d)
    return out


def find_db(repo_root: str, db_name: str) -> Optional[str]:
    """The DB to probe: CONCERN_WMS_DB_DIR override wins, else the newest run dir."""
    dirs = _candidate_dirs(repo_root, db_name)
    return os.path.join(dirs[0], db_name) if dirs else None


def _ro_connect(path: str) -> sqlite3.Connection:
    uri = "file:" + path.replace("\\", "/").replace(" ", "%20") + "?mode=ro"
    try:
        return sqlite3.connect(uri, uri=True)
    except sqlite3.OperationalError:
        return sqlite3.connect(path)  # fallback (still only read queries issued)


def probe_rows(repo_root: str, value: str,
               new_value: str = _PLACEHOLDER) -> Dict[str, Any]:
    """Return, per store, matching junction-row counts + a migration SQL template."""
    stores_out: List[Dict[str, Any]] = []
    total_rows = 0
    dbs_found = 0

    for s in STORES:
        candidates = _candidate_dirs(repo_root, s["db"])
        db_path = os.path.join(candidates[0], s["db"]) if candidates else None
        entry: Dict[str, Any] = {
            "store": s["store"], "db": s["db"], "shape": s["shape"],
            "db_path": (os.path.relpath(db_path, repo_root).replace("\\", "/") if db_path else None),
            "candidate_db_dirs": len(candidates),
            "junctions": {}, "tags_json_rows": None,
            "version_gate": s["version_gate"],
            "migration_sql": _migration_sql(s, value, new_value),
        }
        if len(candidates) > 1:
            entry["multi_db_note"] = (f"{len(candidates)} dirs contain {s['db']}; probed the newest. "
                                      f"Set CONCERN_WMS_DB_DIR to the LIVE save dir to migrate real player state.")
        if not db_path:
            entry["note"] = "no on-disk DB found (probe skipped -- junction shape still reported)"
            stores_out.append(entry)
            continue
        dbs_found += 1
        conn = _ro_connect(db_path)
        try:
            for j in s["junctions"]:
                entry["junctions"][j] = _count_junction(conn, s, j, value)
                v = entry["junctions"][j]
                if isinstance(v, int):
                    total_rows += v
            if s["tags_json"]:
                entry["tags_json_rows"] = _count_tags_json(conn, s, value)
        finally:
            conn.close()
        stores_out.append(entry)

    return {
        "concept": value,
        "dbs_found": dbs_found,
        "total_matching_junction_rows": total_rows,
        "stores": stores_out,
        "atomicity_warning": ("apply the junction UPDATE and the tags_json UPDATE together -- "
                              "they are redundant copies and will desync if migrated separately"),
    }


def _count_junction(conn, s, table, value) -> Any:
    try:
        if s["shape"] == "split_column":
            return conn.execute(
                f"SELECT COUNT(*) FROM {table} WHERE {s['value_col']} = ?", (value,)).fetchone()[0]
        # single_opaque: opaque tag may be bare 'fire' or 'category:fire'
        return conn.execute(
            f"SELECT COUNT(*) FROM {table} WHERE {s['tag_col']} = ? OR {s['tag_col']} LIKE ?",
            (value, f"%:{value}")).fetchone()[0]
    except sqlite3.OperationalError:
        return "(table absent)"


def _count_tags_json(conn, s, value) -> Any:
    total = 0
    for ev in s["events_tables"]:
        col = "tags" if s["store"] == "stat_store" else "tags_json"
        try:
            total += conn.execute(
                f"SELECT COUNT(*) FROM {ev} WHERE {col} LIKE ?", (f'%"{value}"%',)).fetchone()[0]
        except sqlite3.OperationalError:
            continue
    return total


def _migration_sql(s, value, new_value) -> List[str]:
    out: List[str] = []
    for j in s["junctions"]:
        if s["shape"] == "split_column":
            out.append(f"UPDATE {j} SET {s['value_col']}='{new_value}' WHERE {s['value_col']}='{value}';")
        else:
            out.append(f"UPDATE {j} SET {s['tag_col']}='{new_value}' WHERE {s['tag_col']}='{value}';")
            out.append(f"-- also opaque 'cat:{value}' form: UPDATE {j} SET {s['tag_col']}=REPLACE({s['tag_col']}, ':{value}', ':{new_value}') WHERE {s['tag_col']} LIKE '%:{value}';")
    if s["tags_json"]:
        col = "tags" if s["store"] == "stat_store" else "tags_json"
        for ev in s["events_tables"]:
            out.append(f"UPDATE {ev} SET {col}=REPLACE({col}, '\"{value}\"', '\"{new_value}\"') WHERE {col} LIKE '%\"{value}\"%';")
    return out

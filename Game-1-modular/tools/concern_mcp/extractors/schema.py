"""SchemaExtractor -- the SQLite tag-junction coupling (db_junction).

Tags are stored as rows in tag-junction tables across 4 WMS/WNS databases (two shapes:
split-column and single-opaque). That coupling is generic (any tag can be stored), so we
register ONE shared concept `system|junction_shape|tag` with a db_schema site per store.
`concept_blast_radius` unions these into the db_junction group for any real tag value, and
`junction_map`/`DbRowProbe` do the live row-count + migration work.
"""

from __future__ import annotations

from ..coordinates import STORES


class SchemaExtractor:
    def run(self, store, repo_root: str) -> None:
        cid = store.upsert_concept(
            "junction_shape", "tag", "system",
            summary="tags are stored as rows in SQLite tag-junction tables across 4 WMS/WNS DBs")
        for s in STORES:
            store.add_binding_site(
                cid, "db_schema", "sql_ddl", s["module"], s["ddl_line"], "db_junction",
                f"{s['store']}: {s['shape']} junction {s['junctions']} in {s['db']}"
                + (f"; tags_json mirror: {s['tags_json_note']}" if s["tags_json"] else "; no tags_json mirror"),
                silent_failure=(f"renamed tag leaves STALE rows in {s['db']} (runtime state, no source delta, "
                                f"no error) -- call junction_map for counts + migration SQL"),
                editable=1,
                locator_extra={"store": s["store"], "shape": s["shape"], "db": s["db"],
                               "junctions": s["junctions"], "version_gate": s["version_gate"]})
        store.commit()

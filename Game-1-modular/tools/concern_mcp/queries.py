"""Query layer -- the logic behind the MCP tools.

concept_blast_radius(concept)  -- THE flagship. Returns the blast radius GROUPED by
coupling type and RANKED so authority/dispatch/silent-failure sites float to the top,
with a summary of how many sites fail *silently*. Every entry is an openable file:line.

authority_of(concept)  -- source of truth, legal values, aliases, and the
shadow/dead-but-dispatched hazards.

Both return plain dicts (JSON-serializable) so the MCP server and CLI share them.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from .store import ConceptStore

# Site importance for ranking (load-bearing sites first). Adapted in spirit from
# tag_relevance.calculate_relevance -- here it's site-kind priority + silent-failure boost.
_PRIORITY = {
    "definition": 100, "parser": 90, "output_contract_field": 88, "consumer": 80,
    "csharp_mirror": 70, "db_schema": 68, "ml_label": 66,
    "vfx": 60, "json_value": 40, "test": 30, "doc": 20,
}
_REAL_TAXONOMIES = {"combat_effect", "wms", "wns"}


def _group_of(site: Dict[str, Any]) -> str:
    sk, ck = site.get("site_kind"), site.get("coupling_type")
    if sk == "definition" or ck == "authority":
        return "authority"
    if ck == "json_value":
        return "json_value"
    if sk == "vfx":
        return "vfx"
    if sk == "test":
        return "test"
    if ck == "string_literal":
        return "code_dispatch"
    if ck == "db_junction":
        return "db_junction"
    if ck == "ml_label":
        return "ml_label"
    if ck == "csharp_mirror":
        return "csharp_mirror"
    if ck == "output_contract":
        return "output_contract"
    return "other"


def _rank(site: Dict[str, Any]) -> int:
    r = _PRIORITY.get(site.get("site_kind"), 50)
    if site.get("silent_failure"):
        r += 15
    if site.get("mirror_group") and not site.get("pinned_by_test"):
        r += 10  # unguarded mirror
    return r


def _present(site: Dict[str, Any]) -> Dict[str, Any]:
    """Trim a stored site to the openable, high-signal fields for the assistant."""
    return {
        "loc": f"{site['file']}:{site['line']}",
        "file": site["file"],
        "line": site["line"],
        "language": site.get("language"),
        "site_kind": site.get("site_kind"),
        "role": site.get("role"),
        "silent_failure": site.get("silent_failure"),
        "editable": bool(site.get("editable", 1)),
        "mirror_group": site.get("mirror_group"),
        "pinned_by_test": site.get("pinned_by_test"),
        "rank": _rank(site),
    }


def _resolve_ids(store: ConceptStore, concept: str,
                 taxonomy: str = "auto") -> List[Dict[str, Any]]:
    """Resolve a query string to concept row(s): id, bare value, or alias."""
    if "|" in concept:
        row = store.get_concept(concept)
        return [row] if row else []
    tax = None if taxonomy in ("auto", "", None) else taxonomy
    return store.find_concepts_by_value(concept, taxonomy=tax)


def concept_blast_radius(store: ConceptStore, concept: str,
                         taxonomy: str = "auto",
                         kinds: Optional[List[str]] = None,
                         include_symbolic: bool = True) -> Dict[str, Any]:
    matched = _resolve_ids(store, concept, taxonomy)

    if not matched:
        return {
            "concept": concept,
            "is_new": True,
            "nearest_siblings": _nearest_siblings(store, concept),
            "scaffold_hint": ("No binding sites -- this concept does not exist yet. "
                              "Treat as an ADD: pick a sibling concept in the target "
                              "category and clone its site shape (Phase 4 concept_scaffold)."),
            "groups": {},
            "summary": {"total": 0, "silent_sites": 0, "by_lang": {}},
        }

    ids = [m["id"] for m in matched]
    taxonomies = sorted({m["taxonomy"] for m in matched})
    aliases = sorted({a for m in matched
                      for a in _json_list(m.get("aliases_json"))})
    authority_ref = next((m.get("authority_ref") for m in matched
                          if m.get("authority_ref")), None)

    sites = store.sites_for_concepts(ids)
    # db_junction is generic (any tag can be stored) -- union the shared junction-shape sites
    # for any real tag value so the SQLite coupling is never missed.
    if any(m["concept_kind"] == "tag_value" and m["taxonomy"] in _REAL_TAXONOMIES for m in matched):
        js = store.get_concept("system|junction_shape|tag")
        if js:
            sites = sites + store.sites_for_concept(js["id"])

    groups: Dict[str, List[Dict[str, Any]]] = {}
    by_lang: Dict[str, int] = {}
    silent = 0
    for s in sites:
        g = _group_of(s)
        if kinds and g not in kinds:
            continue
        groups.setdefault(g, []).append(_present(s))
        by_lang[s.get("language", "?")] = by_lang.get(s.get("language", "?"), 0) + 1
        if s.get("silent_failure"):
            silent += 1
    for g in groups:
        groups[g].sort(key=lambda x: x["rank"], reverse=True)

    total = sum(len(v) for v in groups.values())
    real_shadows = [t for t in taxonomies if t in _REAL_TAXONOMIES]
    shadow_note = None
    if len(real_shadows) > 1:
        shadow_note = (f"'{concept}' exists in {len(real_shadows)} SEPARATE taxonomies "
                       f"({', '.join(real_shadows)}) -- they are decoupled; changing one "
                       f"does NOT change the other.")

    # Phase 5: symbolic call-spine (composed LSP provider, or a degraded pointer set)
    symbolic_layer = None
    if include_symbolic:
        from .symbolic import symbolic_refs
        from .paths import REPO_ROOT
        symbolic_layer = symbolic_refs(concept, REPO_ROOT)
        if symbolic_layer.get("available") and symbolic_layer.get("refs"):
            groups["symbolic"] = [
                {"loc": f"{r.get('file')}:{r.get('line')}", "file": r.get("file"),
                 "line": r.get("line"), "role": r.get("role"), "site_kind": "symbolic",
                 "rank": 82} for r in symbolic_layer["refs"]]

    next_tools = []
    if groups.get("db_junction"):
        next_tools.append("junction_map(concept) -- live row counts + migration SQL for the 4 stores")
    if groups.get("ml_label"):
        next_tools.append("ml_vocab_impact(concept) -- retrain scope + stale model artifacts")
    if any(s.get("mirror_group") for g in groups.values() for s in g):
        next_tools.append("mirror_check(concept) -- py<->C# mirror alignment + golden obligations")

    return {
        "concept": concept,
        "is_new": False,
        "taxonomies": taxonomies,
        "authority_ref": authority_ref,
        "resolved_aliases": aliases,
        "shadow_warning": shadow_note,
        "groups": groups,
        "related_concepts": _related(store, ids),
        "symbolic_layer": symbolic_layer,
        "next_tools": next_tools,
        "summary": {
            "total": total,
            "silent_sites": silent,
            "by_lang": by_lang,
            "group_counts": {g: len(v) for g, v in groups.items()},
        },
    }


def authority_of(store: ConceptStore, concept: str,
                 taxonomy: str = "auto") -> Dict[str, Any]:
    matched = _resolve_ids(store, concept, taxonomy)
    if not matched:
        return {"concept": concept, "found": False,
                "note": "No such concept in any authority (candidate ADD or typo)."}

    # Prefer a real-taxonomy authority as primary.
    matched.sort(key=lambda m: (m["taxonomy"] not in _REAL_TAXONOMIES,
                                m["taxonomy"] != "combat_effect"))
    primary = matched[0]
    pid = primary["id"]

    category = _category_of(store, pid)
    allowed = _category_members(store, category) if category else []
    sites = store.sites_for_concept(pid)
    has_code = any(s.get("coupling_type") == "string_literal" for s in sites)
    has_auth = any(s.get("site_kind") == "definition" for s in sites)

    shadows = [{"taxonomy": m["taxonomy"], "note": "same string, separate vocabulary"}
               for m in matched if m["id"] != pid and m["taxonomy"] in _REAL_TAXONOMIES]

    out = {
        "concept": concept,
        "found": True,
        "primary_id": pid,
        "taxonomy": primary["taxonomy"],
        "concept_kind": primary["concept_kind"],
        "authority_ref": primary.get("authority_ref"),
        "is_dynamic": bool(primary.get("is_dynamic")),
        "governance": primary.get("governance"),
        "category": category,
        "allowed_values": allowed,
        "aliases": _json_list(primary.get("aliases_json")),
        "shadow_warnings": shadows,
        "summary": primary.get("summary"),
    }
    if primary["taxonomy"] == "undefined" and has_code:
        out["dead_but_dispatched"] = True
        out["note"] = ("Dispatched in code but defined in NO authority -- an alias or a "
                       "stray literal. Add it to the authority or route via alias.")
    elif has_auth and not has_code:
        out["possibly_inert"] = True
        out["note"] = ("Declared in an authority but no code `== '<value>'` dispatch site "
                       "found -- may be table-driven, or dead (verify by opening the sites).")
    return out


# ── Phase 2 specialist tools ──────────────────────────────────────
def junction_map(store: ConceptStore, concept: str,
                 include_row_counts: bool = True) -> Dict[str, Any]:
    """Live SQLite tag-junction migration plan for a value (Scenario-2 gap-closer)."""
    from .extractors.db_probe import probe_rows
    from .paths import REPO_ROOT
    matched = _resolve_ids(store, concept)
    value = matched[0]["concept_value"] if matched else concept
    report = probe_rows(REPO_ROOT, value)
    report["note"] = ("Two junction shapes: split-column (layer{N}_tags, stat_tags) matched by "
                      "tag_value; single-opaque (event_tags, nl{N}_tags) matched by tag. "
                      "Apply junction + tags_json UPDATEs together (atomicity_warning).")
    return report


def ml_vocab_impact(store: ConceptStore, concept: str) -> Dict[str, Any]:
    """Retrain scope + stale model-artifact report for a value (Scenario-2 gap-closer)."""
    matched = _resolve_ids(store, concept)
    ids = [m["id"] for m in matched]
    ml_sites = [s for s in store.sites_for_concepts(ids) if s.get("coupling_type") == "ml_label"]
    if not ml_sites:
        return {
            "concept": concept, "is_ml_load_bearing": False, "labels_are_binary": True,
            "note": ("No ML encoder references this value -- NOT ml-load-bearing. "
                     "FORWARD WARNING: if this value is ever added to a material's "
                     "metadata.tags/category it becomes CNN-hue / LightGBM-count load-bearing."),
        }
    from .coordinates import CRAFTING_CLASSIFIER
    encoders, mirrors, artifacts = [], [], []
    count_sensitive = False
    for s in ml_sites:
        loc = f"{s['file']}:{s['line']}"
        extra = s.get("locator_extra") or {}
        if extra.get("artifact"):
            artifacts.append({"path": s["file"], "role": s["role"]})
        elif s["file"] == CRAFTING_CLASSIFIER:
            encoders.append({"loc": loc, "role": s["role"], "silent_failure": s.get("silent_failure")})
        elif s.get("mirror_group"):
            mirrors.append({"loc": loc, "role": s["role"]})
        else:
            encoders.append({"loc": loc, "role": s["role"], "silent_failure": s.get("silent_failure")})
        if "count-sensitive" in (s.get("role") or "") or "shape" in (s.get("silent_failure") or ""):
            count_sensitive = True
    return {
        "concept": concept, "is_ml_load_bearing": True, "labels_are_binary": True,
        "encoders": encoders, "training_mirrors": mirrors,
        "stale_artifacts": _dedupe_by(artifacts, "path"),
        "retrain_required": bool(artifacts),
        "feature_count_effect": ("shifts_count_or_column (LightGBM) -- verify against the shape guard"
                                 if count_sensitive else "hue/shape only (CNN) -- silent color shift, no shape change"),
        "retrain_inputs": ["Game-1-modular/items.JSON/items-materials-1.JSON",
                           "Game-1-modular/recipes.JSON/ + placements.JSON/ (positive examples)"],
        "note": "Labels are binary valid/invalid (NOT tag-derived). *_extractor.pkl are DEAD (ignored at runtime).",
    }


# ── Phase 4 tools ─────────────────────────────────────────────────
def concept_scaffold(store: ConceptStore, kind: str, name: str,
                     taxonomy: str = "combat_effect",
                     sibling: Optional[str] = None) -> Dict[str, Any]:
    """ADD playbook (Scenario 1): what a NEW category/value structurally requires.

    For a category: the fixed structural sites a new category needs (curated).
    For a value: clone the binding-site SHAPE of a sibling concept into required-new-edits.
    """
    from .coordinates import CATEGORY_REQUIRES, GOLDEN_TESTS

    if kind in ("tag_category", "category"):
        return {
            "kind": "tag_category", "name": name,
            "required_new_edits": CATEGORY_REQUIRES,
            "retrain_required": False, "db_migration_required": False,
            "tests_to_add": [GOLDEN_TESTS[0][0] + " (regenerate effect_stack.json)"],
            "note": ("A NEW category not matching a parser branch is dropped with NO warning "
                     "(worse than an unknown value). It must be bucketed into a new EffectConfig "
                     "field in BOTH languages and consumed, or it silently does nothing."),
        }

    # value add — clone a sibling's site shape
    if not sibling:
        return {"kind": "tag_value", "name": name,
                "error": "provide a sibling concept (an existing value in the target category) to clone its site shape",
                "hint": "call authority_of(<any value in the category>) to list siblings"}
    matched = _resolve_ids(store, sibling)
    if not matched:
        return {"kind": "tag_value", "name": name, "sibling": sibling,
                "error": f"sibling '{sibling}' not found"}
    sites = store.sites_for_concept(matched[0]["id"])
    edits, retrain, db_mig = [], False, False
    seen = set()
    for s in sites:
        k = (s["file"], s["site_kind"])
        if k in seen:
            continue
        seen.add(k)
        edits.append({
            "file": s["file"], "line_anchor": s["line"], "site_kind": s["site_kind"],
            "language": s["language"],
            "instruction": f"add '{name}' alongside '{sibling}' here",
            "editable": bool(s.get("editable", 1)),
        })
        if s["coupling_type"] == "ml_label":
            retrain = True
        if s["coupling_type"] == "db_junction":
            db_mig = True
    return {
        "kind": "tag_value", "name": name, "taxonomy": taxonomy, "sibling": sibling,
        "required_new_edits": edits,
        "retrain_required": retrain, "db_migration_required": db_mig,
        "tests_to_add": [GOLDEN_TESTS[0][0]],
        "note": f"cloned the binding-site shape of '{sibling}' ({len(edits)} distinct site kinds).",
    }


# ── Phase 3 tools ─────────────────────────────────────────────────
def mirror_check(store: ConceptStore, concept: str = "",
                 mirror_group: str = "") -> Dict[str, Any]:
    """py<->C# mirror alignment + unguarded-Godot surface + golden obligations."""
    from .coordinates import GOLDEN_FIXTURE, GOLDEN_TESTS
    matched = _resolve_ids(store, concept) if concept else []
    ids = [m["id"] for m in matched]
    concept_sites = store.sites_for_concepts(ids)

    if mirror_group:
        mgs = [mirror_group]
    else:
        mgs = sorted({s["mirror_group"] for s in concept_sites if s.get("mirror_group")})
    # UX: allow the concept arg to be a mirror_group name directly (e.g. 'effectconfig_contract')
    if concept and not mgs and store.sites_in_mirror_group(concept):
        mgs = [concept]

    groups_out = []
    for mg in mgs:
        members = store.sites_in_mirror_group(mg)
        seen, mem = set(), []
        for s in members:
            k = (s["file"], s["line"], s["language"])
            if k in seen:
                continue
            seen.add(k)
            mem.append({"loc": f"{s['file']}:{s['line']}", "language": s["language"]})
        pinned = sorted({s["pinned_by_test"] for s in members if s.get("pinned_by_test")})
        groups_out.append({
            "mirror_group": mg,
            "members": mem,
            "languages": sorted({s["language"] for s in members}),
            "pinned_by": pinned,
            "guarded": bool(pinned),
            "in_sync": "unknown -- open members to verify (cross-language content is not hash-comparable)",
        })

    unguarded = [{"loc": f"{s['file']}:{s['line']}", "role": s["role"]}
                 for s in concept_sites
                 if s["coupling_type"] == "csharp_mirror" and not s.get("mirror_group")]

    return {
        "concept": concept or None,
        "mirror_groups": groups_out,
        "unguarded_godot_sites": unguarded,
        "unguarded_count": len(unguarded),
        "golden": ({"fixture": GOLDEN_FIXTURE, "tests": [t[0] for t in GOLDEN_TESTS]} if groups_out else None),
        "obligation": (("touching a mirrored dispatch moves the golden effect_stack.json AND the C# tests; "
                        "regenerate via conformance/dump_databases.py, then run the Game1.Core.Tests")
                       if groups_out else None),
    }


def drift_report(store: ConceptStore) -> Dict[str, Any]:
    """Authority-vs-usage drift findings (lazy import to avoid an import cycle)."""
    from .drift import detect_drift
    return detect_drift(store)


def _dedupe_by(items: List[Dict[str, Any]], key: str) -> List[Dict[str, Any]]:
    seen, out = set(), []
    for it in items:
        if it.get(key) in seen:
            continue
        seen.add(it.get(key))
        out.append(it)
    return out


# ── helpers ───────────────────────────────────────────────────────
def _json_list(raw: Optional[str]) -> List[str]:
    import json
    if not raw:
        return []
    try:
        v = json.loads(raw)
        return v if isinstance(v, list) else []
    except (ValueError, TypeError):
        return []


def _category_of(store: ConceptStore, concept_id: str) -> Optional[str]:
    for e in store.edges_for(concept_id):
        if e["edge_kind"] == "member_of_category" and e["src_concept_id"] == concept_id:
            cat = store.get_concept(e["dst_concept_id"])
            if cat:
                return cat["concept_value"]
    return None


def _category_members(store: ConceptStore, category_value: str) -> List[str]:
    rows = store.find_concepts_by_value(category_value, kind="tag_category")
    members: set = set()
    for cat in rows:
        for e in store.edges_for(cat["id"]):
            if e["edge_kind"] == "member_of_category" and e["dst_concept_id"] == cat["id"]:
                src = store.get_concept(e["src_concept_id"])
                if src:
                    members.add(src["concept_value"])
    return sorted(members)


def _related(store: ConceptStore, ids: List[str]) -> List[Dict[str, Any]]:
    out, seen = [], set()
    for cid in ids:
        for e in store.edges_for(cid):
            if e["edge_kind"] == "member_of_category":
                continue
            other = e["dst_concept_id"] if e["src_concept_id"] == cid else e["src_concept_id"]
            if other in ids or other in seen:
                continue
            seen.add(other)
            row = store.get_concept(other)
            if row:
                out.append({"concept": row["concept_value"],
                            "edge_kind": e["edge_kind"],
                            "taxonomy": row["taxonomy"]})
    return out


def _nearest_siblings(store: ConceptStore, concept: str) -> List[str]:
    """Best-effort sibling suggestion for an unknown concept (for the ADD path)."""
    # Suggest distinct category names as scaffold anchors (dedupe across taxonomies:
    # e.g. 'class' exists in both combat_effect and wms).
    seen, cats = set(), []
    for c in store.all_concepts(kind="tag_category"):
        v = c["concept_value"]
        if v in seen:
            continue
        seen.add(v)
        cats.append(v)
        if len(cats) >= 12:
            break
    return cats

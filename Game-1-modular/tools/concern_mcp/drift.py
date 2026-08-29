"""DriftDetector + coverage self-check (§5).

detect_drift(store): authority-vs-usage set-diffs surfaced as findings -- the failures that
are silent in the running game (a used-but-undefined tag, a dispatched-but-undefined literal,
a declared-but-inert value, a cross-taxonomy twin, an unmirrored Godot table).

run_coverage_check(store, repo_root): guards against a curated coordinate going STALE -- if a
known-heavy file yields zero sites, the index silently under-reports; we warn instead.
"""

from __future__ import annotations

from typing import Any, Dict, List

from .store import ConceptStore
from .coordinates import CRAFTING_CLASSIFIER, GODOT_TAG_FILES
from .queries import _REAL_TAXONOMIES  # reuse the real-taxonomy set

_INERT_KINDS = {"definition"}  # only-authority sites => declared but never used


def detect_drift(store: ConceptStore) -> Dict[str, Any]:
    used_but_undefined: List[str] = []
    dispatched_but_undefined: List[Dict[str, str]] = []
    defined_but_inert: List[str] = []
    unmirrored_godot = 0
    by_value_tax: Dict[str, set] = {}

    for c in store.all_concepts():
        sites = store.sites_for_concept(c["id"])
        kinds = {s["site_kind"] for s in sites}
        couplings = {s["coupling_type"] for s in sites}

        if c["taxonomy"] == "undefined":
            if "json_value" in couplings:
                used_but_undefined.append(c["concept_value"])
            code = [s for s in sites if s["coupling_type"] == "string_literal"]
            if code:
                dispatched_but_undefined.append(
                    {"value": c["concept_value"], "at": f"{code[0]['file']}:{code[0]['line']}"})
        elif c["concept_kind"] == "tag_value" and c["taxonomy"] in _REAL_TAXONOMIES:
            # inert = declared but no usage found. Only meaningful for combat_effect, where
            # values are literal-dispatched; WMS values are runtime-assigned (dynamic), so a
            # missing literal is expected, not drift.
            if c["taxonomy"] == "combat_effect" and sites and kinds <= _INERT_KINDS:
                defined_but_inert.append(c["concept_value"])
            by_value_tax.setdefault(c["concept_value"], set()).add(c["taxonomy"])

        unmirrored_godot += sum(
            1 for s in sites if s["coupling_type"] == "csharp_mirror" and not s["mirror_group"])

    # cross-taxonomy twins that are NOT yet linked by a drifts_from/shadow edge
    cross_taxonomy_twins = []
    for val, taxes in by_value_tax.items():
        if len(taxes) > 1:
            cross_taxonomy_twins.append({"value": val, "taxonomies": sorted(taxes)})

    return {
        "used_but_undefined": sorted(set(used_but_undefined)),
        "dispatched_but_undefined": dispatched_but_undefined,
        "defined_but_inert": sorted(set(defined_but_inert)),
        "cross_taxonomy_twins": cross_taxonomy_twins,
        "unmirrored_godot_sites": unmirrored_godot,
        "summary": (f"{len(set(used_but_undefined))} used-but-undefined, "
                    f"{len(dispatched_but_undefined)} dispatched-but-undefined, "
                    f"{len(set(defined_but_inert))} defined-but-inert, "
                    f"{len(cross_taxonomy_twins)} cross-taxonomy twins, "
                    f"{unmirrored_godot} unmirrored Godot sites"),
    }


def run_coverage_check(store: ConceptStore, repo_root: str) -> List[str]:
    """Warn if a known-heavy source yields zero sites (a curated coordinate went stale)."""
    warnings: List[str] = []
    files_with_sites = {
        r["file"] for r in store.connection.execute("SELECT DISTINCT file FROM binding_sites").fetchall()
    }
    expected = [CRAFTING_CLASSIFIER] + GODOT_TAG_FILES + \
        ["Game-1-modular/Definitions.JSON/tag-definitions.JSON",
         "Game-1-modular/world_system/world_memory/tag_library.py"]
    for f in expected:
        if f not in files_with_sites:
            warnings.append(f"COVERAGE: expected sites from {f} but found NONE "
                            f"(curated coordinate may be stale, or the vocab gate excluded all its tags)")
    store.set_meta("coverage_warnings", "\n".join(warnings) if warnings else "OK")
    return warnings

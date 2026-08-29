"""Self-contained tests for the concern registry.

Builds a synthetic mini-repo in tmp_path (tiny tag-definitions.JSON + tag_library.py
+ one python dispatch file + one content JSON) and exercises the whole pipeline --
extraction, resolution, blast radius, authority, aliases, shadow, is_new, reindex --
without depending on the real 168k-LOC tree, so it is fast and deterministic.

Run:  cd Game-1-modular && python -m pytest tools/concern_mcp/tests -q
"""

from __future__ import annotations

import json
import os

import pytest

from tools.concern_mcp.store import ConceptStore
from tools.concern_mcp.indexer import PolyglotIndexer
from tools.concern_mcp import queries


TAG_DEFS = {
    "metadata": {"version": "1.0"},
    "categories": {
        "damage_type": ["fire", "frost"],
        "special": ["lifesteal", "vampiric"],
        "geometry": ["single_target", "circle"],
    },
    "tag_definitions": {
        "fire": {"category": "damage_type", "description": "fire damage"},
        "lifesteal": {"category": "special", "description": "heal on hit",
                      "aliases": ["drain"], "conflicts_with": ["thorns"]},
        "vampiric": {"category": "special", "description": "heal on hit"},
        "circle": {"category": "geometry", "aliases": ["aoe"]},
    },
}

TAG_LIBRARY_PY = '''\
from dataclasses import dataclass
@dataclass(frozen=True)
class TagCategory:
    category_id: str
    values: frozenset
    layer_unlocked: int = 1
    is_dynamic: bool = False

LAYER_1_CATEGORIES = {
    "element": TagCategory("element", frozenset({"fire", "water"}), layer_unlocked=1),
    "species": TagCategory("species", frozenset(), layer_unlocked=1, is_dynamic=True),
}
'''

EFFECT_EXECUTOR_PY = '''\
def apply(special_tag, config):
    if special_tag == 'lifesteal' or special_tag == 'vampiric':
        heal()
    elif special_tag == 'blink':      # dispatched but NOT in authority (dead_but_dispatched)
        teleport()

ELEMENT_HUES = {'fire': 0, 'frost': 1}   # ml/vfx-style dict-key coupling

def run(config):
    dmg = config.damage_tags          # output_contract field access
    sp = config.special_tags
    base = config.base_damage

def parse(category):
    if category == 'geometry':
        pass
'''

CONTENT_JSON = {
    "items": [
        {"itemId": "flame_sword", "tags": ["fire", "lifesteal"], "combatTags": ["frost"]},
        {"itemId": "ice_ring", "tags": ["frost"]},
    ]
}


@pytest.fixture()
def mini_repo(tmp_path):
    repo = tmp_path
    scan = repo / "proj"
    (scan / "Definitions.JSON").mkdir(parents=True)
    (scan / "Definitions.JSON" / "tag-definitions.JSON").write_text(
        json.dumps(TAG_DEFS, indent=2), encoding="utf-8")
    (scan / "world_system" / "world_memory").mkdir(parents=True)
    (scan / "world_system" / "world_memory" / "tag_library.py").write_text(
        TAG_LIBRARY_PY, encoding="utf-8")
    (scan / "core").mkdir()
    (scan / "core" / "effect_executor.py").write_text(EFFECT_EXECUTOR_PY, encoding="utf-8")
    (scan / "items.JSON").mkdir()
    (scan / "items.JSON" / "items-x.JSON").write_text(
        json.dumps(CONTENT_JSON, indent=2), encoding="utf-8")
    store = ConceptStore(str(repo / "concern.db"))
    idx = PolyglotIndexer(str(repo), str(scan))
    idx.build(store)
    return store, idx, str(repo)


def test_build_populates(mini_repo):
    store, _, _ = mini_repo
    s = store.stats()
    assert s["concepts"] > 0
    assert s["binding_sites"] > 0


def test_fire_spans_both_taxonomies_with_shadow(mini_repo):
    store, _, _ = mini_repo
    r = queries.concept_blast_radius(store, "fire")
    assert r["is_new"] is False
    assert set(r["taxonomies"]) == {"combat_effect", "wms"}
    assert r["shadow_warning"] and "SEPARATE" in r["shadow_warning"]
    # authority in BOTH the JSON and the WMS python library
    auth_files = {s["file"] for s in r["groups"].get("authority", [])}
    assert any(f.endswith("tag-definitions.JSON") for f in auth_files)
    assert any(f.endswith("tag_library.py") for f in auth_files)


def test_fire_catches_nonsymbolic_couplings(mini_repo):
    store, _, _ = mini_repo
    r = queries.concept_blast_radius(store, "fire")
    groups = r["groups"]
    # json-value coupling (content) + code dict-key coupling -- the call-graph blind spots
    assert groups.get("json_value"), "should find content tag arrays"
    code_files = {s["file"] for s in groups.get("code_dispatch", [])}
    assert any(f.endswith("effect_executor.py") for f in code_files)
    # every returned site carries a silent_failure note
    assert r["summary"]["silent_sites"] == r["summary"]["total"]


def test_lifesteal_dispatch_and_alias(mini_repo):
    store, _, _ = mini_repo
    r = queries.concept_blast_radius(store, "lifesteal")
    dispatch = r["groups"].get("code_dispatch", [])
    roles = " ".join(s["role"] for s in dispatch)
    assert "lifesteal" in roles  # the == 'lifesteal' dispatch branch is surfaced
    # alias resolution: querying the alias 'drain' finds the lifesteal concept's sites
    r2 = queries.concept_blast_radius(store, "drain")
    assert r2["is_new"] is False
    assert r2["summary"]["total"] > 0


def test_authority_of_lists_siblings_and_governance(mini_repo):
    store, _, _ = mini_repo
    a = queries.authority_of(store, "lifesteal")
    assert a["found"] and a["category"] == "special"
    assert "vampiric" in a["allowed_values"] and "lifesteal" in a["allowed_values"]
    assert a["taxonomy"] == "combat_effect"


def test_dead_but_dispatched(mini_repo):
    store, _, _ = mini_repo
    # 'blink' is compared in code but defined in no authority
    a = queries.authority_of(store, "blink")
    assert a.get("found") is True
    assert a.get("dead_but_dispatched") is True


def test_is_new_add_path(mini_repo):
    store, _, _ = mini_repo
    r = queries.concept_blast_radius(store, "element_resonance")
    assert r["is_new"] is True
    assert r["nearest_siblings"]
    assert "scaffold_hint" in r


def test_reindex_is_idempotent(mini_repo):
    store, idx, repo = mini_repo
    before = queries.concept_blast_radius(store, "fire")["summary"]["total"]
    idx.reindex(store, ["proj/core/effect_executor.py"])
    after = queries.concept_blast_radius(store, "fire")["summary"]["total"]
    assert before == after  # no duplication on re-extract


# ── Phase 2-4: curated couplings (ml/db/mirror/contract/scaffold/drift) ──
def test_ml_vocab_impact_and_group(mini_repo):
    store, _, _ = mini_repo
    # 'fire' is an ELEMENT_HUES key → ml-load-bearing; artifacts stale on rename
    mi = queries.ml_vocab_impact(store, "fire")
    assert mi["is_ml_load_bearing"] is True
    assert any("smithing_best.keras" in a["path"] for a in mi["stale_artifacts"])
    assert mi["labels_are_binary"] is True
    # and it shows in the blast radius ml_label group
    assert queries.concept_blast_radius(store, "fire")["groups"].get("ml_label")


def test_db_junction_group_and_two_shapes(mini_repo):
    store, _, _ = mini_repo
    r = queries.concept_blast_radius(store, "fire")
    assert len(r["groups"].get("db_junction", [])) == 4  # 4 stores
    jm = queries.junction_map(store, "fire")
    assert len(jm["stores"]) == 4
    assert {s["shape"] for s in jm["stores"]} == {"split_column", "single_opaque"}
    assert all(s["migration_sql"] for s in jm["stores"])


def test_output_contract_layer(mini_repo):
    store, _, _ = mini_repo
    # config.special_tags / config.base_damage attribute access → output_contract field concepts
    r = queries.concept_blast_radius(store, "special_tags")
    assert r["groups"].get("output_contract")
    r2 = queries.concept_blast_radius(store, "base_damage")
    assert r2["groups"].get("output_contract")


def test_mirror_check_category_switch(mini_repo):
    store, _, _ = mini_repo
    mc = queries.mirror_check(store, "geometry")  # a category → category_switch mirror
    assert any(g["mirror_group"] == "category_switch" for g in mc["mirror_groups"])
    assert any(g["guarded"] for g in mc["mirror_groups"])  # pinned by golden


def test_concept_scaffold(mini_repo):
    store, _, _ = mini_repo
    cat = queries.concept_scaffold(store, "category", "element_resonance")
    assert len(cat["required_new_edits"]) >= 6  # parser branch, config field x2, C# switch, ...
    val = queries.concept_scaffold(store, "tag_value", "flamestrike", sibling="lifesteal")
    assert val["required_new_edits"]
    assert val["sibling"] == "lifesteal"


def test_scaffold_is_new_flow(mini_repo):
    store, _, _ = mini_repo
    # blast returns is_new → scaffold gives the ADD playbook
    assert queries.concept_blast_radius(store, "element_resonance")["is_new"] is True
    sc = queries.concept_scaffold(store, "category", "element_resonance")
    assert sc["kind"] == "tag_category"


def test_drift_report_finds_blink(mini_repo):
    store, _, _ = mini_repo
    d = queries.drift_report(store)
    assert any(x["value"] == "blink" for x in d["dispatched_but_undefined"])
    assert "cross_taxonomy_twins" in d  # 'fire' is in combat + wms


def test_symbolic_layer_degrades(mini_repo):
    store, _, _ = mini_repo
    r = queries.concept_blast_radius(store, "fire")
    # no CONCERN_SYMBOLIC_CMD configured → degraded but informative
    assert r["symbolic_layer"]["available"] is False
    assert "anchors" in r["symbolic_layer"]


def test_case_insensitive_query(mini_repo):
    store, _, _ = mini_repo
    # canonical value matching is case-insensitive (blast('Fire') == blast('fire'))
    up = queries.concept_blast_radius(store, "Fire")
    lo = queries.concept_blast_radius(store, "fire")
    assert up["is_new"] is False
    assert up["summary"]["total"] == lo["summary"]["total"]
    assert queries.authority_of(store, "LIFESTEAL")["found"] is True


def test_no_duplicate_binding_sites(mini_repo):
    store, _, _ = mini_repo
    dup = store.connection.execute(
        "SELECT COUNT(*) FROM (SELECT concept_id,site_kind,file,line,coupling_type,"
        "COUNT(*) c FROM binding_sites GROUP BY 1,2,3,4,5 HAVING c>1)").fetchone()[0]
    assert dup == 0


def test_mirror_check_by_group_name(mini_repo):
    store, _, _ = mini_repo
    # the concept arg may be a mirror_group name directly
    mc = queries.mirror_check(store, "category_switch")
    assert any(g["mirror_group"] == "category_switch" for g in mc["mirror_groups"])

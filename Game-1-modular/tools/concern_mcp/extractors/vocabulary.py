"""VocabularyExtractor -- authorities first.

Seeds the concept table + alias/conflict/synergy/parent edges + a `definition`
binding site per value, from the two source-of-truth declarations:

- Definitions.JSON/tag-definitions.JSON  (taxonomy = "combat_effect")
- world_system/world_memory/tag_library.py  (taxonomy = "wms")

Parsed structurally (JSON load; Python `ast`) -- never imported/executed -- so a
module gaining import side-effects can't break the freshness path (§3.1).
"""

from __future__ import annotations

import ast
import json
import os
from dataclasses import dataclass, field
from typing import Dict, Set

from ..util import read_text, file_hash, rel


@dataclass
class VocabResult:
    """The known vocabulary, handed to the code/JSON extractors to gate on."""
    values: Set[str] = field(default_factory=set)
    categories: Set[str] = field(default_factory=set)
    value_to_taxonomies: Dict[str, Set[str]] = field(default_factory=dict)
    value_to_category: Dict[str, Set[str]] = field(default_factory=dict)
    param_keys: Set[str] = field(default_factory=set)

    def note(self, value: str, category: str, taxonomy: str) -> None:
        self.values.add(value)
        self.value_to_taxonomies.setdefault(value, set()).add(taxonomy)
        if category:
            self.categories.add(category)
            self.value_to_category.setdefault(value, set()).add(category)


def load_vocab(store) -> "VocabResult":
    """Reconstruct the gating vocabulary from already-indexed concepts.

    Used by incremental reindex so we DON'T re-run authority extraction (which would
    re-append definition sites/edges and duplicate them). Authorities only change on a
    full rebuild.
    """
    vr = VocabResult()
    for c in store.all_concepts():
        if c["concept_kind"] == "tag_value":
            vr.values.add(c["concept_value"])
            vr.value_to_taxonomies.setdefault(c["concept_value"], set()).add(c["taxonomy"])
        elif c["concept_kind"] == "tag_category":
            vr.categories.add(c["concept_value"])
    for c in store.all_concepts(kind="tag_value"):
        for e in store.edges_for(c["id"]):
            if e["edge_kind"] == "member_of_category" and e["src_concept_id"] == c["id"]:
                cat = store.get_concept(e["dst_concept_id"])
                if cat:
                    vr.value_to_category.setdefault(c["concept_value"], set()).add(
                        cat["concept_value"])
    return vr


class VocabularyExtractor:
    COMBAT_JSON = os.path.join("Definitions.JSON", "tag-definitions.JSON")
    WMS_LIB = os.path.join("world_system", "world_memory", "tag_library.py")

    def run(self, store, repo_root: str, scan_root: str) -> VocabResult:
        vocab = VocabResult()
        self._combat(store, repo_root, scan_root, vocab)
        self._wms(store, repo_root, scan_root, vocab)
        store.commit()
        return vocab

    # ── combat authority: tag-definitions.JSON ────────────────────
    def _combat(self, store, repo_root, scan_root, vocab: VocabResult) -> None:
        path = os.path.join(scan_root, self.COMBAT_JSON)
        text = read_text(path)
        if not text:
            return
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            return
        relp = rel(path, repo_root)
        h = file_hash(path)
        key_lines = _json_key_lines(text)
        tax = "combat_effect"

        # 1) categories block -> category concepts + value concepts + def sites
        for cat, values in (data.get("categories") or {}).items():
            cat_line = key_lines.get(cat, 1)
            cat_cid = store.upsert_concept(
                "tag_category", cat, tax, authority_ref=f"{relp}:{cat_line}",
                governance="content-frozen (SINGLE SOURCE OF TRUTH)",
                summary=f"combat tag category '{cat}'")
            store.add_binding_site(
                cat_cid, "definition", "json", relp, cat_line, "authority",
                f"category '{cat}' declared here",
                silent_failure="renaming a category needs a parser branch + EffectConfig field (both languages)",
                editable=0, content_hash=h)
            for val in values:
                line = key_lines.get(val, key_lines.get(cat, 1))
                cid = store.upsert_concept("tag_value", val, tax,
                                           authority_ref=f"{relp}:{line}",
                                           summary=f"combat tag {cat}:{val}")
                store.add_binding_site(cid, "definition", "json", relp, line,
                                       "authority", f"defined in '{cat}' category (source of truth)",
                                       silent_failure="rename here breaks every downstream string match",
                                       editable=0, content_hash=h)
                store.add_edge(cid, f"{tax}|tag_category|{cat}", "member_of_category")
                vocab.note(val, cat, tax)

        # 2) tag_definitions -> authority_ref + aliases + edges
        defs = data.get("tag_definitions") or {}
        for name, d in defs.items():
            cat = d.get("category", "")
            line = key_lines.get(name, 1)
            aliases = list(d.get("aliases", []) or [])
            cid = store.upsert_concept("tag_value", name, tax,
                                       authority_ref=f"{relp}:{line}",
                                       aliases=aliases,
                                       summary=d.get("description", "") or f"combat tag {cat}:{name}")
            if cat:
                store.add_edge(cid, f"{tax}|tag_category|{cat}", "member_of_category")
            vocab.note(name, cat, tax)

        # 3) edges (second pass -- all value concepts now exist)
        for name, d in defs.items():
            src = _cid(tax, name)
            for other in d.get("conflicts_with", []) or []:
                store.add_edge(src, _cid(tax, other), "conflicts_with")
            for syn in (d.get("synergies", {}) or {}).keys():
                store.add_edge(src, _cid(tax, syn), "synergy")
            parent = d.get("parent")
            if parent:
                store.add_edge(_cid(tax, parent), src, "parent_of")

    # ── WMS taxonomy: tag_library.py (ast) ────────────────────────
    def _wms(self, store, repo_root, scan_root, vocab: VocabResult) -> None:
        path = os.path.join(scan_root, self.WMS_LIB)
        text = read_text(path)
        if not text:
            return
        try:
            tree = ast.parse(text)
        except SyntaxError:
            return
        relp = rel(path, repo_root)
        h = file_hash(path)
        tax = "wms"

        for node in tree.body:
            if not isinstance(node, ast.Assign):
                continue
            targets = [t.id for t in node.targets if isinstance(t, ast.Name)]
            if not any(t.endswith("_CATEGORIES") for t in targets):
                continue
            if not isinstance(node.value, ast.Dict):
                continue
            for key_node, val_node in zip(node.value.keys, node.value.values):
                cat_id = _const_str(key_node)
                if not cat_id or not _is_tagcategory_call(val_node):
                    continue
                try:
                    self._wms_category(store, vocab, relp, h, tax, cat_id, val_node)
                except Exception:  # noqa: BLE001 -- tolerate an unexpected node shape
                    continue

    def _wms_category(self, store, vocab, relp, h, tax, cat_id, call: ast.Call) -> None:
        line = getattr(call, "lineno", 1)
        is_dynamic = 0
        for kw in call.keywords:
            if kw.arg == "is_dynamic" and _const_bool(kw.value):
                is_dynamic = 1
        store.upsert_concept("tag_category", cat_id, tax,
                             authority_ref=f"{relp}:{line}", is_dynamic=is_dynamic,
                             summary=f"WMS tag category '{cat_id}'")
        # frozenset({...}) of values -- find the frozenset call among args
        values = _frozenset_values(call)
        for val in values:
            cid = store.upsert_concept("tag_value", val, tax,
                                       authority_ref=f"{relp}:{line}",
                                       summary=f"WMS tag {cat_id}:{val}")
            store.add_binding_site(cid, "definition", "python", relp, line,
                                   "authority", f"defined in WMS category '{cat_id}'",
                                   silent_failure="rename here desyncs WMS tag junction rows",
                                   editable=1, content_hash=h)
            store.add_edge(cid, f"{tax}|tag_category|{cat_id}", "member_of_category")
            vocab.note(val, cat_id, tax)


# ── helpers ───────────────────────────────────────────────────────
def _cid(tax: str, value: str) -> str:
    return f"{tax}|tag_value|{value}"


def _json_key_lines(text: str) -> Dict[str, int]:
    """Map the first `"key":` occurrence of each key to its 1-based line."""
    out: Dict[str, int] = {}
    for i, line in enumerate(text.splitlines(), start=1):
        s = line.lstrip()
        if s.startswith('"'):
            end = s.find('"', 1)
            if end > 1 and s[end + 1:].lstrip().startswith(":"):
                key = s[1:end]
                out.setdefault(key, i)
    return out


def _const_str(node) -> str:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return ""


def _const_bool(node) -> bool:
    return isinstance(node, ast.Constant) and node.value is True


def _is_tagcategory_call(node) -> bool:
    if not isinstance(node, ast.Call):
        return False
    f = node.func
    if isinstance(f, ast.Name):
        return f.id == "TagCategory"
    if isinstance(f, ast.Attribute):
        return f.attr == "TagCategory"
    return False


def _frozenset_values(call: ast.Call):
    """Extract string literals from a frozenset({...}) argument of a TagCategory call."""
    for arg in call.args:
        if isinstance(arg, ast.Call) and isinstance(arg.func, ast.Name) \
                and arg.func.id == "frozenset" and arg.args:
            inner = arg.args[0]
            if isinstance(inner, (ast.Set, ast.List, ast.Tuple)):
                return [e.value for e in inner.elts
                        if isinstance(e, ast.Constant) and isinstance(e.value, str)]
        # also handle a bare set literal passed positionally
        if isinstance(arg, ast.Set):
            return [e.value for e in arg.elts
                    if isinstance(e, ast.Constant) and isinstance(e.value, str)]
    return []

"""PyExtractor -- Python string-literal couplings a call-graph misses.

Captures three site classes via `ast` (gated on the known vocabulary so 168k LOC of
unrelated `== 'player'` noise stays out):

1. `<name> == '<literal>'`  -- dispatch / category-branch sites
   (e.g. effect_executor.py `special_tag == 'lifesteal'`, tag_parser.py `category == 'geometry'`)
2. Dict literal string keys -- modifier/palette tables
   (e.g. crafting_classifier.py `ELEMENT_HUES = {'fire': 0, ...}`, combat_particles color maps)
3. `.get('<tag-key>')` -- param-key reads (combatTags / effectTags)

Returns raw site dicts; the PolyglotIndexer resolves value->concept_id and inserts.
"""

from __future__ import annotations

import ast
import os
from typing import Dict, List, Optional

from ..util import iter_files, read_text, file_hash, rel

TAG_KEYS = {"combatTags", "effectTags", "effect_tags", "tags"}
# Only these categories' VALUES are specific enough to index from `==`/dict-keys.
# (context/trigger/class values like 'player','self','active' are common English
#  words that would flood the index -- excluded.)
FOCUS_CATEGORIES = {"damage_type", "status_debuff", "status_buff", "special", "geometry"}
# Variable names that mark a `<var> == '<lit>'` as a TAG dispatch -- lets us capture a
# literal dispatched in code but absent from every authority (dead_but_dispatched drift)
# without flooding the index with unrelated string comparisons.
TAG_VARS = {"special_tag", "category", "tag", "damage_tag", "status_tag",
            "geometry_tag", "context_tag", "trigger_tag", "damage_type", "status"}


class PyExtractor:
    def collect(self, repo_root: str, scan_root: str, vocab,
                files: Optional[List[str]] = None) -> List[Dict]:
        sites: List[Dict] = []
        paths = files if files is not None else list(iter_files(scan_root, {".py"}))
        for path in paths:
            relp = rel(path, repo_root)
            if "tools/concern_mcp" in relp:
                continue  # never index ourselves
            sites.extend(self._file(path, relp, vocab))
        return sites

    def _file(self, path: str, relp: str, vocab) -> List[Dict]:
        src = read_text(path)
        if not src:
            return []
        try:
            tree = ast.parse(src)
        except SyntaxError:
            return []
        h = file_hash(path)
        visitor = _Visitor(vocab, relp, h)
        visitor.visit(tree)
        return visitor.sites


def _focus_value(vocab, val: str) -> bool:
    cats = vocab.value_to_category.get(val)
    return bool(cats and (cats & FOCUS_CATEGORIES))


class _Visitor(ast.NodeVisitor):
    def __init__(self, vocab, relp: str, h: str):
        self.vocab = vocab
        self.relp = relp
        self.h = h
        self.sites: List[Dict] = []
        low = relp.lower()
        self.pref = "wms" if "world_system" in low else "combat_effect"
        self.is_vfx = any(x in low for x in ("animation/", "rendering/", "visual"))
        self.is_test = "/tests/" in low or os.path.basename(low).startswith("test_")

    # 1) equality dispatch / category branches
    def visit_Compare(self, node: ast.Compare):
        if len(node.ops) == 1 and isinstance(node.ops[0], ast.Eq):
            lit, var = _eq_literal_and_var(node)
            if lit is not None:
                self._record_literal(lit, var, node.lineno)
        self.generic_visit(node)

    # 2) dict-key palette / modifier tables
    def visit_Dict(self, node: ast.Dict):
        for k in node.keys:
            if isinstance(k, ast.Constant) and isinstance(k.value, str):
                val = k.value
                if val in self.vocab.values and _focus_value(self.vocab, val):
                    self._add(val, "tag_value",
                              "vfx" if self.is_vfx else "consumer", "string_literal",
                              getattr(k, "lineno", node.lineno),
                              f"keyed in a dict/table in {os.path.basename(self.relp)}",
                              "missing/renamed key -> silent fallback (default color/modifier)")
        self.generic_visit(node)

    # 3) .get('<tag-key>') param reads
    def visit_Call(self, node: ast.Call):
        f = node.func
        if isinstance(f, ast.Attribute) and f.attr == "get" and node.args:
            a0 = node.args[0]
            if isinstance(a0, ast.Constant) and a0.value in TAG_KEYS:
                self._add(a0.value, "param_key", "consumer", "string_literal",
                          node.lineno,
                          f"reads the '{a0.value}' key from content JSON",
                          "misnamed key -> empty list -> effect silently dropped")
        self.generic_visit(node)

    # ── helpers ──
    def _record_literal(self, lit: str, var: Optional[str], line: int):
        if lit in self.vocab.categories:
            self._add(lit, "tag_category",
                      "test" if self.is_test else "parser", "string_literal", line,
                      f"category dispatch branch (== '{lit}')",
                      "new/renamed category not matching a branch -> tag dropped, no error")
        elif lit in self.vocab.values and _focus_value(self.vocab, lit):
            self._add(lit, "tag_value",
                      "test" if self.is_test else "consumer", "string_literal", line,
                      f"value dispatch branch (== '{lit}')",
                      "unknown value falls through the elif chain -> effect silently no-op")
        elif var in TAG_VARS:
            # dispatched in code but in no authority -- a drift worth surfacing
            self._add(lit, "tag_value",
                      "test" if self.is_test else "consumer", "string_literal", line,
                      f"dispatched (== '{lit}') but not defined in any authority",
                      "value defined in NO authority -> drift; only handled in code")

    def _add(self, value, kind_hint, site_kind, coupling, line, role, silent):
        self.sites.append({
            "value": value,
            "kind_hint": kind_hint,
            "site_kind": site_kind,
            "coupling_type": coupling,
            "language": "python",
            "file": self.relp,
            "line": int(line),
            "role": role,
            "silent_failure": silent,
            "editable": 1,
            "governance": None,
            "preferred_taxonomy": self.pref,
            "content_hash": self.h,
        })


def _eq_literal_and_var(node: ast.Compare):
    """Return (literal, var_name) for `<name> == '<lit>'` / `'<lit>' == <name>`."""
    left, right = node.left, node.comparators[0]
    if isinstance(left, ast.Name) and isinstance(right, ast.Constant) \
            and isinstance(right.value, str):
        return right.value, left.id
    if isinstance(right, ast.Name) and isinstance(left, ast.Constant) \
            and isinstance(left.value, str):
        return left.value, right.id
    return None, None

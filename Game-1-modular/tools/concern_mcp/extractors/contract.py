"""ContractExtractor -- the EffectConfig OUTPUT CONTRACT (output_contract_field).

The blast radius of a STRUCTURAL parser refactor is NOT the tag strings -- it is the
EffectConfig field contract (symbolic attribute access) + the 4 lockstep serializer sites +
the base-damage-before-synergies ordering invariant. Pure string indexing misses all of it,
so this extractor adds the symbolic-ish layer (ast attribute access on the distinctive
EffectConfig fields) plus the curated lockstep/ordering/golden coordinates.
"""

from __future__ import annotations

import ast
from typing import Set

from ..util import iter_files, read_text, file_hash, rel
from ..coordinates import EFFECTCONFIG_SITES, ORDERING_SITES, GOLDEN_TESTS, GOLDEN_FIXTURE

# Distinctive EffectConfig fields (skip generic params/warnings/context to avoid false hits).
DISTINCTIVE_FIELDS: Set[str] = {
    "geometry_tag", "damage_tags", "status_tags", "context_tags", "special_tags",
    "trigger_tags", "base_damage", "base_healing", "conflicts_resolved", "raw_tags",
}


class ContractExtractor:
    def run(self, store, repo_root: str, scan_root: str) -> None:
        # 1) the 4 lockstep serializer sites (must stay name/order aligned + regen golden)
        cc = store.upsert_concept(
            "output_contract_field", "EffectConfig", "system",
            summary="the 13-field EffectConfig wire contract -- 4 sites that MUST stay in lockstep")
        for f, l, lang, role in EFFECTCONFIG_SITES:
            store.add_binding_site(
                cc, "output_contract_field", lang, f, l, "output_contract", role,
                silent_failure="add/remove/rename/reorder a field must hit ALL 4 sites + regen effect_stack.json",
                mirror_group="effectconfig_contract",
                pinned_by_test=GOLDEN_TESTS[0][0])

        # 2) the ordering invariant (base_damage snapshotted BEFORE synergies)
        oc = store.upsert_concept(
            "output_contract_field", "base_damage_before_synergies", "system",
            summary="base_damage/base_healing extracted from params BEFORE synergies run")
        for f, l, note in ORDERING_SITES:
            lang = "csharp" if f.endswith(".cs") else "python"
            store.add_binding_site(
                oc, "output_contract_field", lang, f, l, "output_contract", note,
                silent_failure="reordering extraction after synergies breaks the golden (silent behavioral change)",
                mirror_group="ordering_invariant", pinned_by_test=GOLDEN_TESTS[0][0])
        store.add_edge(oc, "system|output_contract_field|base_damage", "ordering_invariant",
                       "base_damage is snapshotted before synergies mutate params")

        # 3) per-field attribute-access sites across the codebase (ast)
        for path in iter_files(scan_root, {".py"}):
            relp = rel(path, repo_root)
            if "tools/concern_mcp" in relp:
                continue
            self._scan_py(store, path, relp, cc)
        store.commit()

    def _scan_py(self, store, path, relp, contract_cid) -> None:
        src = read_text(path)
        if not src or not any(f in src for f in DISTINCTIVE_FIELDS):
            return
        try:
            tree = ast.parse(src)
        except SyntaxError:
            return
        h = file_hash(path)
        is_test = "/tests/" in relp.lower()
        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute) and node.attr in DISTINCTIVE_FIELDS:
                fid = store.upsert_concept(
                    "output_contract_field", node.attr, "system",
                    summary=f"EffectConfig.{node.attr} field")
                store.add_binding_site(
                    fid, "test" if is_test else "output_contract_field", "python", relp,
                    getattr(node, "lineno", 1), "output_contract",
                    f"reads/writes EffectConfig.{node.attr}",
                    silent_failure="a structural parser change to this field's shape ripples here",
                    content_hash=h)
                store.add_edge(fid, contract_cid, "member_of_contract")

"""CsExtractor -- the C# (Godot) tag surface (csharp_mirror), regex-based (zero-dep).

Two surfaces:
1. CURATED CORE MIRRORS (coordinates.MIRROR_PAIRS): the hand-ported Game1.Core dispatch
   that must stay byte-aligned with Python, each pinned by a golden. Attached per covered
   concept with a shared mirror_group + pinned_by_test.
2. UNMIRRORED GODOT TABLES: ~33 tag-keyed Dictionary/switch/HashSet tables across the
   minigame + VFX layer, no Game1.Core equivalent and ZERO test guards. Regex-scanned and
   gated on the known vocabulary (combat/WMS + ML material keys) so we surface where a KNOWN
   tag is hand-keyed in Godot. mirror_group=None => flagged as an unguarded drift surface.

Roslyn isn't needed (and would add a build step): the tag tables are dictionary-initializer /
case / Contains / Overlaps forms that regex matches reliably.
"""

from __future__ import annotations

import re
from typing import Dict, List, Set

from ..util import read_text, file_hash
from ..coordinates import MIRROR_PAIRS, GODOT_TAG_FILES, ENCODER_SPECS

# lines that look like a tag-table context (avoids matching comments / paths / identifiers)
_CTX = re.compile(r'\[\s*"|case\s+"|\.Contains\(\s*"|\.Overlaps\(|HashSet<string>|new\[\]|'
                  r'Dictionary<string|==\s*"|"\s+or\s+"|\bswitch\b')
_TOKEN = re.compile(r'"([a-z][a-z0-9_]*)"')


class CsExtractor:
    def collect(self, repo_root: str, vocab) -> List[Dict]:
        gate = set(vocab.values) | {k.lower() for spec in ENCODER_SPECS for k in spec["keys"]}
        sites: List[Dict] = []
        sites += self._core_mirrors(vocab)
        sites += self._godot_tables(repo_root, gate)
        return sites

    # 1) curated core mirrors -----------------------------------------
    def _core_mirrors(self, vocab) -> List[Dict]:
        out: List[Dict] = []
        cat_to_vals: Dict[str, List[str]] = {}
        for val, cats in vocab.value_to_category.items():
            for c in cats:
                cat_to_vals.setdefault(c, []).append(val)

        for m in MIRROR_PAIRS:
            covers = m["covers"]
            if "category" in covers:
                targets = cat_to_vals.get(covers["category"], [])
            elif covers.get("kind") == "tag_category":
                targets = list(vocab.categories)
            else:
                targets = covers.get("values", [])
            pyf, pyl = m["py"]
            csf, csl = m["cs"]
            for v in targets:
                # C# mirror site (the port that can drift)
                out.append(_site(v, "csharp_mirror", "csharp", csf, csl, "csharp_mirror",
                                 f"C# mirror [{m['group']}]: {m['note']}",
                                 "hand-ported dispatch can drift from Python (byte-compared by golden)",
                                 mirror_group=m["group"], pinned_by_test=m["pinned_by_test"]))
                # Python side of the pair (so mirror_check sees both members)
                out.append(_site(v, "consumer", "python", pyf, pyl, "symbolic",
                                 f"Python side of [{m['group']}] mirror",
                                 None, mirror_group=m["group"], pinned_by_test=m["pinned_by_test"]))
        return out

    # 2) unmirrored Godot tables --------------------------------------
    def _godot_tables(self, repo_root: str, gate: Set[str]) -> List[Dict]:
        out: List[Dict] = []
        for rel in GODOT_TAG_FILES:
            path = f"{repo_root}/{rel}"
            text = read_text(path)
            if not text:
                continue
            h = file_hash(path)
            base = rel.rsplit("/", 1)[-1]
            seen: Set[tuple] = set()
            for i, line in enumerate(text.splitlines(), start=1):
                if not _CTX.search(line):
                    continue
                for tok in _TOKEN.findall(line):
                    if tok not in gate:
                        continue
                    key = (tok, i)
                    if key in seen:
                        continue
                    seen.add(key)
                    out.append(_site(tok, "vfx" if base in ("SkillVfx.cs", "CombatWorld.cs") else "csharp_mirror",
                                     "csharp", rel, i, "csharp_mirror",
                                     f"hand-keyed in {base} (Godot presentation layer)",
                                     "renamed tag silently contributes 0 here -- UNMIRRORED, no test guards it",
                                     mirror_group=None, pinned_by_test=None, content_hash=h))
        return out


def _site(value, site_kind, language, file, line, coupling, role, silent,
          mirror_group=None, pinned_by_test=None, content_hash=None) -> Dict:
    return {
        "value": value, "kind_hint": "tag_value",
        "site_kind": site_kind, "coupling_type": coupling, "language": language,
        "file": file, "line": int(line), "role": role, "silent_failure": silent,
        "editable": 1, "governance": None, "preferred_taxonomy": "combat_effect",
        "mirror_group": mirror_group, "pinned_by_test": pinned_by_test,
        "locator_extra": None, "content_hash": content_hash,
    }

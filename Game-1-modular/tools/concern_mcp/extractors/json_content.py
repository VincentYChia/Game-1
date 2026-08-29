"""JsonContentExtractor -- the tag-bearing content JSON surface (json-value coupling).

Scans content JSON for tag-bearing string arrays and emits one raw binding-site per
(file, array-key, value) whose value is a KNOWN tag (gated on the vocabulary so the
index stays focused on the real tag web, not every string in 4.8k files).

Uses a small line-scanning state machine rather than json.load so each value keeps a
real, openable line number (json.load discards line info). Handles both inline
`"tags": ["a","b"]` and multi-line arrays, repeated per object in a list.

Returns raw site dicts; the PolyglotIndexer resolves value->concept_id and inserts.
"""

from __future__ import annotations

import os
import re
from typing import Dict, List, Optional

from ..util import iter_files, read_text, file_hash, rel

TAG_KEYS = {"tags", "combatTags", "effectTags", "effect_tags", "itemTags", "weaponTags"}
# Content dirs that CLAUDE.md marks OFF-LIMITS (sacred boundary -> steer to alias fix).
FROZEN_SEGMENTS = ("items.JSON/", "recipes.JSON/", "Skills/", "Definitions.JSON/",
                   "progression/", "placements.JSON/")

_ARRAY_OPEN = re.compile(r'"(?P<key>[A-Za-z_]+)"\s*:\s*\[(?P<rest>.*)$')
_STRING = re.compile(r'"([^"\\]*)"')


class JsonContentExtractor:
    def collect(self, repo_root: str, scan_root: str, vocab,
                files: Optional[List[str]] = None) -> List[Dict]:
        sites: List[Dict] = []
        paths = files if files is not None else list(
            iter_files(scan_root, {".json"}, extra_skip={"Scaled JSON Development"}))
        for path in paths:
            sites.extend(self._file(path, repo_root, vocab))
        return sites

    def _file(self, path: str, repo_root: str, vocab) -> List[Dict]:
        text = read_text(path)
        if not text or '"' not in text:
            return []
        relp = rel(path, repo_root)
        frozen = any(seg in relp for seg in FROZEN_SEGMENTS)
        h = file_hash(path)
        base = os.path.basename(relp)
        sites: List[Dict] = []

        in_array = False
        cur_key = None
        for i, line in enumerate(text.splitlines(), start=1):
            if not in_array:
                m = _ARRAY_OPEN.search(line)
                if not m or m.group("key") not in TAG_KEYS:
                    continue
                cur_key = m.group("key")
                rest = m.group("rest")
                if "]" in rest:  # inline array, closes on same line
                    seg = rest.split("]", 1)[0]
                    for val in _STRING.findall(seg):
                        s = self._site(val, cur_key, relp, i, base, frozen, h, vocab)
                        if s:
                            sites.append(s)
                    cur_key = None
                else:
                    in_array = True
            else:
                seg = line.split("]", 1)[0] if "]" in line else line
                for val in _STRING.findall(seg):
                    s = self._site(val, cur_key, relp, i, base, frozen, h, vocab)
                    if s:
                        sites.append(s)
                if "]" in line:
                    in_array = False
                    cur_key = None
        return sites

    @staticmethod
    def _site(val, key, relp, line, base, frozen, h, vocab) -> Optional[Dict]:
        if val not in vocab.values:
            return None  # gate: only index values that are KNOWN tags
        return {
            "value": val,
            "kind_hint": "tag_value",
            "site_kind": "json_value",
            "coupling_type": "json_value",
            "language": "json",
            "file": relp,
            "line": line,
            "role": f"listed in '{key}' array of {base}",
            "silent_failure": "renamed value silently stops matching code consumers (no error)",
            "editable": 0 if frozen else 1,
            "governance": "content-frozen (CLAUDE.md sacred boundary)" if frozen else None,
            "preferred_taxonomy": "combat_effect",
            "content_hash": h,
        }

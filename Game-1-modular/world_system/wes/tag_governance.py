"""WES content-tag governance.

The tag system is load-bearing (drives game logic / CNN input / stat-tracking /
UI + search), so generated content must not silently invent tags. The tool
prompts already instruct the model to propose new tags with a ``NEW:`` prefix
and otherwise use the existing vocabulary; this module enforces that
deterministically after generation:

  - tag in the valid vocabulary   -> kept
  - tag prefixed ``NEW:``         -> recorded as a designer-review proposal and
                                     dropped from the committed content (once a
                                     designer approves it into content/defs it
                                     becomes valid on the next run — the index
                                     re-harvests it)
  - unknown tag, no ``NEW:``      -> dropped (invented without the convention)

The valid vocabulary is "in sync with the existing system": tags existing
content of the same type already uses, plus the combat/effect TagRegistry
(see GameContentIndex.tags_for). If the vocabulary can't be read (empty),
governance is skipped so nothing is dropped spuriously.
"""

from __future__ import annotations

from typing import Any, Dict, List, Set, Tuple

_NEW_PREFIX = "NEW:"


def _govern_list(
    tags: List[Any], valid: Set[str],
    proposed: List[str], dropped: List[str],
) -> List[str]:
    kept: List[str] = []
    for t in tags:
        if not isinstance(t, str) or not t.strip():
            continue
        s = t.strip()
        if s.startswith(_NEW_PREFIX):
            name = s[len(_NEW_PREFIX):].strip()
            if name:
                proposed.append(name)
            continue  # proposals never enter committed content
        if s in valid:
            kept.append(s)
        else:
            dropped.append(s)
    return kept


def govern_content_tags(
    content_json: Dict[str, Any], tool: str, valid_tags: Set[str],
) -> Tuple[Dict[str, Any], List[str], List[str], List[str]]:
    """Validate + clean the tag fields of one generated artifact (in place).

    Returns ``(content, kept, dropped, proposed)``. If ``valid_tags`` is empty
    (vocabulary unavailable), returns the content unchanged.
    """
    if not valid_tags:
        return content_json, [], [], []

    dropped: List[str] = []
    proposed: List[str] = []
    kept: List[str] = []

    # Tags live at metadata.tags (materials/nodes/hostiles/chunks) or top-level
    # tags (skills). Govern whichever are present.
    meta = content_json.get("metadata")
    if isinstance(meta, dict) and isinstance(meta.get("tags"), list):
        meta["tags"] = _govern_list(meta["tags"], valid_tags, proposed, dropped)
        kept += meta["tags"]
    if isinstance(content_json.get("tags"), list):
        content_json["tags"] = _govern_list(
            content_json["tags"], valid_tags, proposed, dropped)
        kept += content_json["tags"]

    return content_json, kept, dropped, proposed


__all__ = ["govern_content_tags"]

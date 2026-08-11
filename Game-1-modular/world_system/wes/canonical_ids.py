"""Canonical content-id coordination for WES multi-step plans.

The problem this solves (found 2026-08-11 in the first real-LLM end-to-end run):
each executor_tool invents its OWN id from the intent, so co-emitted cross-refs
don't line up — a material becomes ``moors_copper_ore`` while the node/hostile/
chunk that depend on it reference ``ashfall_verdigris_copper``. Every reference
then orphans and the whole plan rolls back, even though each artifact is fine in
isolation (which is why per-hub certification never caught it).

Design (approved 2026-08-11):

  **A — canonical id (primary).** Each plan step carries a canonical
  ``content_id``. The step's artifact is forced to use it as its primary id, and
  every dependent step's cross-references are rewritten to the parent's canonical
  id. Deterministic — no LLM in the loop. Because the dispatcher runs steps in
  topological order, a step's parents are always resolved before it runs.

  **Fallback — a non-LLM normalizer.** For any residual reference that still
  doesn't match (formatting drift: casing, spaces, hyphens, punctuation), a pure
  string normalizer reconciles it against the known live + co-emitted ids and
  rewrites it to the canonical form. Never guesses semantically; only reconciles
  spelling of an id that is otherwise present.

This module is registry-agnostic and pure (easy to unit-test): the dispatcher
passes in the sets of known ids; this module decides + rewrites.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Set, Tuple

from world_system.content_registry.xref_rules import extract_xrefs, VALID_TOOLS


# The primary identifier field each tool's artifact carries. This is the field
# the ContentRegistry stages on (see xref_rules.extract_header_fields) and the
# one dependents reference. Kept here as the single source for id enforcement.
_PRIMARY_ID_FIELD: Dict[str, str] = {
    "materials": "materialId",
    "nodes": "resourceId",
    "hostiles": "enemyId",
    "skills": "skillId",
    "titles": "titleId",
    "chunks": "chunkType",
    "npcs": "npc_id",
    "quests": "quest_id",
}


def primary_id_field(tool: str) -> Optional[str]:
    return _PRIMARY_ID_FIELD.get(tool)


# ── The deterministic normalizer (the non-LLM fallback) ───────────────────────

def normalize_id(value: Any) -> str:
    """Fold an id-or-name to a canonical snake_case comparison key.

    Pure formatting reconciliation — NOT semantic matching. ``"Moors Copper
    Ore"``, ``"moors-copper-ore"`` and ``"moors_copper_ore"`` all fold to
    ``"moors_copper_ore"``. Returns ``""`` for non-strings/empties.
    """
    if not isinstance(value, str):
        return ""
    s = value.strip().lower()
    s = re.sub(r"[\s\-]+", "_", s)      # spaces + hyphens -> underscore
    s = re.sub(r"[^a-z0-9_]", "", s)    # drop any other punctuation
    s = re.sub(r"_+", "_", s).strip("_")
    return s


def slugify(text: str, *, max_words: int = 4) -> str:
    """Derive a compact snake_case id from a name/intent (deterministic).

    Used only as a last-resort canonical id when neither the planner nor the
    tool supplied one. Keeps the first ``max_words`` tokens so a verbose intent
    doesn't become an unwieldy id.
    """
    norm = normalize_id(text)
    if not norm:
        return ""
    parts = norm.split("_")
    return "_".join(parts[:max_words])


def get_emitted_id(content_json: Dict[str, Any], tool: str) -> str:
    """Read the id the tool actually emitted for its artifact (or "")."""
    field = primary_id_field(tool)
    if field:
        val = content_json.get(field)
        if isinstance(val, str) and val.strip():
            return val.strip()
    # Defensive: some tools may emit a generic "id".
    val = content_json.get("id")
    return val.strip() if isinstance(val, str) and val.strip() else ""


def enforce_content_id(content_json: Dict[str, Any], tool: str,
                       canonical_id: str) -> None:
    """Force the artifact's primary id field to ``canonical_id`` (in place)."""
    field = primary_id_field(tool)
    if field and canonical_id:
        content_json[field] = canonical_id


# ── Deep id rewrite (handles both dict values AND dict keys) ──────────────────
# Chunk cross-refs live as dict KEYS (resourceDensity/enemySpawns), so a value-
# only replace would miss them.

def _deep_replace_id(obj: Any, old: str, new: str) -> Any:
    if old == new or not old:
        return obj
    if isinstance(obj, dict):
        return {
            (new if k == old else k): _deep_replace_id(v, old, new)
            for k, v in obj.items()
        }
    if isinstance(obj, list):
        return [_deep_replace_id(v, old, new) for v in obj]
    if isinstance(obj, str):
        return new if obj == old else obj
    return obj


def reconcile_refs(
    content_json: Dict[str, Any],
    tool: str,
    *,
    canonical_id: str,
    parent_ids_by_tool: Dict[str, List[str]],
    live_ids_by_tool: Dict[str, Set[str]],
    intended_ref_ids: Optional[Set[str]] = None,
) -> Dict[str, Any]:
    """Enforce this artifact's id + rewrite its cross-refs to canonical ids.

    Args:
        content_json: the tool's generated artifact (mutated → returned).
        tool: this artifact's tool.
        canonical_id: the id this artifact MUST carry (approach A).
        parent_ids_by_tool: canonical ids of this step's ``depends_on`` parents,
            grouped by the parent's tool. The intended reference targets.
        live_ids_by_tool: every id already resolvable (registry-live + staged
            this plan), grouped by tool. Used by the normalizer fallback.
        intended_ref_ids: the ids the HUB declared as intended cross-refs (from
            ``spec.cross_ref_hints``). This disambiguates the dependency the
            planner meant from ids the tool *invented* on its own — only an
            intended ref may be force-mapped onto a single parent. Invented
            extras (a drop to a material nobody created) stay genuine orphans.

    Returns:
        ``{"content": <rewritten json>, "resolved": [...], "orphans": [...]}``.
    """
    intended = {normalize_id(x) for x in (intended_ref_ids or set()) if x}

    # 1. Approach A: pin this artifact's own id.
    if canonical_id:
        enforce_content_id(content_json, tool, canonical_id)

    resolved: List[str] = []
    orphans: List[str] = []
    handled: Set[str] = set()

    for (_src_type, _src_id, ref_type, ref_id, _rel) in extract_xrefs(
        tool, content_json
    ):
        if not ref_id or ref_id in handled:
            continue
        handled.add(ref_id)
        if ref_type not in VALID_TOOLS:
            continue  # tag/biome/enum ref — not a content id

        live = live_ids_by_tool.get(ref_type, set())
        if ref_id in live:
            continue  # already resolves exactly — nothing to do

        parents = parent_ids_by_tool.get(ref_type, [])
        was_intended = normalize_id(ref_id) in intended

        # (A) Primary: an INTENDED cross-ref to a depends_on parent. Only an
        # intended ref may bind to a single parent — this is what distinguishes
        # "the material the planner meant" from a tool-invented extra drop.
        target = _pick_target(ref_id, parents, allow_single=was_intended)

        # (Fallback) Non-LLM normalizer: formatting drift against any known id.
        if target is None:
            target = _pick_target(ref_id, sorted(live), allow_single=False)

        if target is not None and target != ref_id:
            content_json = _deep_replace_id(content_json, ref_id, target)
            resolved.append(f"{ref_id} -> {target}")
        elif target is None:
            orphans.append(ref_id)

    return {"content": content_json, "resolved": resolved, "orphans": orphans}


# id-bearing fields inside nested ref structures (drops[], skills[], etc.).
_REF_ID_KEYS = (
    "materialId", "material_id", "enemyId", "enemy_id", "skillId", "skill_id",
    "resourceId", "resource_id", "nodeId", "node_id", "id",
)


def prune_orphan_refs(
    content_json: Dict[str, Any], tool: str, orphan_ids: Set[str],
):
    """Remove cross-references to content that does not exist.

    After canonical reconciliation, any remaining orphan is a ref the tool
    *invented* (a drop to a material nobody created, a spawn of a nonexistent
    enemy). A generated artifact may only reference live or co-emitted content,
    so those refs are deterministically stripped — enforcing the tool prompts'
    own "cross-refs must resolve" rule without rolling back the whole plan. The
    artifact keeps all its RESOLVED refs; only the dangling ones are dropped.

    Handles refs stored as dict KEYS (chunk resourceDensity/enemySpawns), list
    ITEMS (skills[]), and nested id FIELDS (drops[].materialId). Never touches
    the artifact's own primary id (that is not a cross-ref). Returns
    ``(pruned_content, removed_ids)``.
    """
    if not orphan_ids:
        return content_json, []
    removed: List[str] = []

    def _prune(obj: Any) -> Any:
        if isinstance(obj, dict):
            new: Dict[str, Any] = {}
            for k, v in obj.items():
                # A dict KEY that is itself an orphan ref.
                if isinstance(k, str) and k in orphan_ids:
                    removed.append(k)
                    continue
                # An id FIELD whose value is an orphan ref.
                if (isinstance(k, str) and k in _REF_ID_KEYS
                        and isinstance(v, str) and v in orphan_ids):
                    removed.append(v)
                    continue
                new[k] = _prune(v)
            return new
        if isinstance(obj, list):
            out: List[Any] = []
            for item in obj:
                if isinstance(item, str) and item in orphan_ids:
                    removed.append(item)
                    continue
                if isinstance(item, dict):
                    idvals = {
                        item.get(k) for k in _REF_ID_KEYS
                        if isinstance(item.get(k), str)
                    }
                    hit = idvals & orphan_ids
                    if hit:
                        removed.append(next(iter(hit)))
                        continue
                out.append(_prune(item))
            return out
        return obj

    return _prune(content_json), removed


def _pick_target(ref_id: str, candidates: List[str],
                 *, allow_single: bool) -> Optional[str]:
    """Resolve ``ref_id`` to one of ``candidates`` deterministically.

    Exact match first; then a unique normalized (formatting-only) match. Only
    if ``allow_single`` (i.e. this was a hub-declared intended dependency) will
    a lone candidate be accepted as the target — that's the one case where the
    dependency edge unambiguously says "this ref is that parent". Otherwise an
    unmatched ref is left as a genuine orphan rather than guessed.
    """
    if not candidates:
        return None
    if ref_id in candidates:
        return ref_id
    n = normalize_id(ref_id)
    norm_matches = [c for c in candidates if normalize_id(c) == n]
    if len(norm_matches) == 1:
        return norm_matches[0]
    if len(norm_matches) > 1:
        return None  # ambiguous — do not guess
    if allow_single and len(candidates) == 1:
        return candidates[0]
    return None


__all__ = [
    "primary_id_field",
    "normalize_id",
    "slugify",
    "get_emitted_id",
    "enforce_content_id",
    "reconcile_refs",
    "prune_orphan_refs",
]

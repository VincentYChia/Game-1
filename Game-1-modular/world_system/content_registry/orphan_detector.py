"""Orphan detection — Pass 1 (inline) and Pass 2 (registry-wide).

Per §7.3 of the working doc there are three orphan passes:

- **Pass 1**: during tool output parsing. A tool's generated JSON
  is examined; every referenced id is checked against the registry
  (live OR staged in the same plan). Orphaned ids are reported back
  to the tool so it can retry, insert a create-step, or drop the
  reference.
- **Pass 2**: verification phase before commit. Walks the
  ``content_xref`` table and checks every ``ref_id`` against the
  live definitions + this plan's staged definitions.
- **Pass 3**: nightly / on-save scrub. Deferred per v4. See the
  module-level TODO near the bottom of this file.

Pass 1 is the function :func:`validate_against_registry`.
Pass 2 is implemented as :meth:`ContentRegistry.find_orphans`.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, TYPE_CHECKING

from world_system.content_registry.xref_rules import (
    VALID_TOOLS,
    extract_xrefs,
)

if TYPE_CHECKING:  # pragma: no cover - typing only
    from world_system.content_registry.content_registry import (
        ContentRegistry,
    )


def validate_against_registry(
    content_json: Dict[str, Any],
    plan_id: str,
    tool_name: str,
    registry: Optional["ContentRegistry"] = None,
) -> List[str]:
    """Pass 1 — orphan scan against a staging-aware registry view.

    Walks every cross-reference implied by ``content_json`` (via
    :func:`xref_rules.extract_xrefs`). For each referenced id, asks
    the registry whether it exists live OR is staged under this
    ``plan_id``. Returns the list of orphaned ``ref_id`` strings.

    A ``None`` registry (for tests / early bring-up) skips the check
    and returns an empty list — Pass 2 will still catch missing refs
    before commit.
    """
    if tool_name not in VALID_TOOLS:
        # Unknown tools can't be validated here; Pass 2 will catch
        # anything that slips through via the xref table.
        return []

    if registry is None:
        return []

    xrefs = extract_xrefs(tool_name, content_json)
    orphans: List[str] = []
    seen: set = set()

    for (_src_type, _src_id, ref_type, ref_id, _rel) in xrefs:
        if not ref_id or ref_id in seen:
            continue
        seen.add(ref_id)
        if ref_type not in VALID_TOOLS:
            # Non-registry references (tag ids, biome names, etc.)
            # aren't orphan candidates here.
            continue
        if not registry.exists(ref_type, ref_id, include_staged=False):
            # Not live — but might be staged in this plan.
            staged_in_plan = _is_staged_in_plan(
                registry, ref_type, ref_id, plan_id
            )
            if not staged_in_plan:
                orphans.append(ref_id)
    return orphans


def _is_staged_in_plan(
    registry: "ContentRegistry", ref_type: str, ref_id: str, plan_id: str
) -> bool:
    """Ask the registry whether ``ref_id`` is staged under ``plan_id``.

    Uses :meth:`ContentRegistry.list_staged_by_plan` which already
    groups by tool; this wrapper is defensive so malformed
    registry responses cannot raise back into caller code.
    """
    try:
        by_tool = registry.list_staged_by_plan(plan_id)
    except Exception:
        return False
    rows = by_tool.get(ref_type, []) or []
    for row in rows:
        if row.get("content_id") == ref_id:
            return True
    return False


# NOTE(placeholder — deferred):
#
# TODO(Development-Plan/WORLD_SYSTEM_WORKING_DOC.md §7.3): Pass 3 —
# "Nightly / on-save scrub" — is deferred per v4. When a play
# session loads or nightly maintenance runs, a full scrub walks
# every live xref and verifies the ref still resolves, auto-repairing
# (or flagging for repair) any orphans that slipped through due to
# manual JSON edits, corrupted saves, or designer intervention.
#
# The default repair is "downgrade reference to a safe fallback"
# (e.g., orphan material drop → generic tier-matched material). This
# policy is NOT yet designed; do not implement until the designer
# commits to a repair strategy.

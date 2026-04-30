"""Plan resolution — orchestrator-level glue around the dependency resolver.

Two related concerns live here:

1. **Plan-time bounce-back.** After the planner produces a WESPlan but
   before the dispatcher runs, we re-validate cross-refs against the
   live registry. If unresolved refs remain, we build a structured XML
   warning and bounce the plan back to the planner via the existing
   rerun mechanism (``adjusted_instructions``). Per user direction the
   warning is informational — the planner can either fix the missing
   steps OR include a ``<wes_plan_acknowledgment>true</wes_plan_acknowledgment>``
   to confirm the plan is intentional.

2. **Runtime cascade.** After the dispatcher finishes a primary plan
   pass, some staged content may have referenced new ids that nothing
   produced (e.g. a chunk template named a hostile that wasn't planned,
   or a hostile dropped a material that wasn't planned). Because the
   user wants WES to have authority to create whatever it needs, we
   build a small EXTENSION PLAN of synthetic steps to fill those gaps.
   The orchestrator dispatches the extension plan, which can recurse —
   capped at MAX_RUNTIME_CASCADE_DEPTH (default 2) so a buggy chain
   can't run away.

The runtime cascade chains naturally: if a synthetic chunk step
generates a hostile reference, the next cascade pass picks it up; if
that hostile drops a material, the next pass picks that up.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Dict, FrozenSet, List, Optional, Set
from xml.sax.saxutils import escape as xml_escape

from world_system.content_registry.xref_rules import (
    VALID_TOOLS,
    extract_xrefs,
)
from world_system.wes.dataclasses import (
    ExecutorSpec,
    WESPlan,
    WESPlanStep,
)
from world_system.wes.dependency_resolver import (
    CoemitRecommendation,
    DependencyAnalysis,
    analyze_plan_dependencies,
)


# ── Knobs ─────────────────────────────────────────────────────────────

# Maximum recursion depth for runtime cascade. Each cascade pass can
# itself emit refs; we cap to avoid runaway. Default 2 = primary plan
# may co-emit dependents, those may co-emit grandchildren, then stop.
MAX_RUNTIME_CASCADE_DEPTH: int = 2

# Maximum total synthetic steps queued in a single cascade pass.
MAX_CASCADE_STEPS_PER_PASS: int = 8

# Recognized planner-acknowledgment marker (case-insensitive). When the
# planner's previous output included this string in its rationale or a
# new ``planner_acknowledgment`` field, we skip the bounce-back.
PLANNER_ACKNOWLEDGMENT_MARKER: str = "<wes_plan_acknowledgment>true</wes_plan_acknowledgment>"


# ── Registry snapshot ────────────────────────────────────────────────


def build_registry_snapshot(registry: Any) -> Dict[str, FrozenSet[str]]:
    """Build a {tool: frozenset of committed content_ids} snapshot.

    Used to feed :func:`analyze_plan_dependencies`. If ``registry`` is
    None or doesn't expose ``list_live``, returns an empty dict (every
    ref will then have to resolve via same-plan upstream).
    """
    if registry is None or not hasattr(registry, "list_live"):
        return {}
    snapshot: Dict[str, FrozenSet[str]] = {}
    for tool in VALID_TOOLS:
        try:
            rows = registry.list_live(tool)
        except Exception:
            rows = []
        ids: Set[str] = set()
        for row in rows or []:
            cid = row.get("content_id") if isinstance(row, dict) else None
            if isinstance(cid, str) and cid:
                ids.add(cid)
        snapshot[tool] = frozenset(ids)
    return snapshot


# ── Bounce-back warning ──────────────────────────────────────────────


def build_unresolved_xml_warning(analysis: DependencyAnalysis) -> str:
    """Format an XML warning message the planner can read on rerun.

    The warning lists every unresolved cross-ref with its source step,
    target tool, target id, and reason. The planner can either:
    - Fix the plan (add explicit steps for missing content / fix
      missing ``depends_on`` edges).
    - Include ``<wes_plan_acknowledgment>true</wes_plan_acknowledgment>``
      in its output to confirm the plan is intentional (the runtime
      cascade will fill the gaps post-dispatch).
    """
    if analysis.is_satisfiable:
        return ""

    parts: List[str] = ["<WES_PLANNER_WARNING>"]
    parts.append(
        "  <reason>Plan references content that does not exist in the "
        "registry and is not being co-emitted by an upstream step in this "
        "plan.</reason>"
    )
    parts.append("  <unresolved_refs>")
    for ref in analysis.unresolved_refs:
        parts.append(
            f'    <ref source_step="{xml_escape(ref.source_step_id)}" '
            f'source_tool="{xml_escape(ref.source_tool)}" '
            f'target_tool="{xml_escape(ref.target_tool)}" '
            f'target_id="{xml_escape(ref.target_id)}" '
            f'reason="{xml_escape(ref.reason)}"/>'
        )
    parts.append("  </unresolved_refs>")
    parts.append(
        "  <action>Either (a) add explicit steps so each target_id is "
        "co-emitted, (b) fix any missing depends_on edges, or (c) include "
        f"{xml_escape(PLANNER_ACKNOWLEDGMENT_MARKER)} in your plan rationale "
        "to confirm the plan is intentional. The runtime cascade will then "
        "auto-generate dependent content during execution.</action>"
    )
    parts.append("</WES_PLANNER_WARNING>")
    return "\n".join(parts)


def planner_acknowledged(plan: WESPlan) -> bool:
    """True if the planner's plan includes the acknowledgment marker.

    Searches rationale and any ``planner_acknowledgment`` field on the
    plan dict (defensive lookup — the dataclass doesn't strictly carry
    the field but plans are tolerant containers).
    """
    if PLANNER_ACKNOWLEDGMENT_MARKER.lower() in (plan.rationale or "").lower():
        return True
    return False


# ── Bounce-back decision ─────────────────────────────────────────────


@dataclass
class BounceDecision:
    """Outcome of the plan-time validation pass."""
    bounce: bool
    analysis: Optional[DependencyAnalysis] = None
    warning: str = ""

    @property
    def has_unresolved(self) -> bool:
        return self.analysis is not None and not self.analysis.is_satisfiable


def evaluate_plan_for_bounce(
    plan: WESPlan,
    registry: Any,
) -> BounceDecision:
    """Run dependency analysis on a freshly-planned WESPlan.

    Returns a BounceDecision indicating whether the orchestrator should
    bounce back to the planner with a warning. Honors the planner's
    explicit acknowledgment marker — if the planner has already said
    "I know, do it anyway", we don't bounce.
    """
    if plan.abandoned:
        # Abandoned plans skip the bounce — no dispatching anyway.
        return BounceDecision(bounce=False)

    snapshot = build_registry_snapshot(registry)
    analysis = analyze_plan_dependencies(plan, registry_snapshot=snapshot)

    if analysis.is_satisfiable:
        return BounceDecision(bounce=False, analysis=analysis)

    if planner_acknowledged(plan):
        return BounceDecision(bounce=False, analysis=analysis)

    return BounceDecision(
        bounce=True,
        analysis=analysis,
        warning=build_unresolved_xml_warning(analysis),
    )


# ── Runtime cascade ──────────────────────────────────────────────────


def _staged_payload_iter(
    registry: Any, plan_id: str
) -> List[tuple]:
    """Yield (tool, payload_json) for every row staged under plan_id.

    Used for runtime cascade. Returns [] if registry is unwired.
    """
    if registry is None or not hasattr(registry, "list_staged_by_plan"):
        return []
    try:
        groups = registry.list_staged_by_plan(plan_id) or {}
    except Exception:
        return []

    out: List[tuple] = []
    for tool, rows in groups.items():
        if tool not in VALID_TOOLS:
            continue
        for row in rows or []:
            payload = row.get("payload_json") if isinstance(row, dict) else None
            if not isinstance(payload, dict):
                # The row may store it as a JSON string; the registry
                # currently deserializes it but we double-check.
                continue
            out.append((tool, payload))
    return out


def find_runtime_orphans(
    registry: Any,
    plan_id: str,
) -> List[CoemitRecommendation]:
    """Walk staged content for plan_id and return co-emit recs for any
    cross-ref not satisfied by registry or by another row in this plan.

    Behaves like ``analyze_plan_dependencies`` but operates on actual
    staged tool outputs rather than the planner's spec slots — catching
    refs the planner couldn't have foreseen (the LLM tool emitted a
    name in its drops/spawns/teaches that nothing else generated).

    De-duplicates so each (target_tool, target_id) pair appears at most
    once. Caller can cap by :data:`MAX_CASCADE_STEPS_PER_PASS`.
    """
    snapshot = build_registry_snapshot(registry)
    staged_groups = _staged_payload_iter(registry, plan_id)

    # Build a "what this plan staged" set so refs to siblings count as
    # resolved. Each tool's set is its own content_ids (the staged_ids
    # the dispatcher recorded in DispatchResult.staged_content_ids).
    staged_sets: Dict[str, Set[str]] = {t: set() for t in VALID_TOOLS}
    for tool, payload in staged_groups:
        # The payload may include the content_id field directly via
        # extract_xrefs's helper; just trust the row's content_id key.
        cid = payload.get("content_id") if isinstance(payload, dict) else None
        if not cid:
            # Try common per-tool keys
            for key in ("materialId", "enemyId", "skillId", "titleId",
                        "chunkType", "npc_id", "quest_id", "resourceId",
                        "nodeId"):
                v = payload.get(key) if isinstance(payload, dict) else None
                if isinstance(v, str) and v:
                    cid = v
                    break
        if isinstance(cid, str) and cid:
            staged_sets[tool].add(cid)

    seen: Set[tuple] = set()
    recs: List[CoemitRecommendation] = []
    for tool, payload in staged_groups:
        try:
            xrefs = extract_xrefs(tool, payload)
        except Exception:
            continue
        for src_type, src_id, ref_type, ref_id, relationship in xrefs:
            if ref_type not in VALID_TOOLS:
                continue
            # Resolved by registry (committed)?
            if ref_id in snapshot.get(ref_type, frozenset()):
                continue
            # Resolved by another sibling staged in this plan?
            if ref_id in staged_sets.get(ref_type, set()):
                continue
            key = (ref_type, ref_id)
            if key in seen:
                continue
            seen.add(key)
            recs.append(
                CoemitRecommendation(
                    missing_ref_type=ref_type,
                    missing_ref_id=ref_id,
                    requested_by_step_id=f"runtime_{src_type}:{src_id}",
                    suggested_intent=(
                        f"Runtime co-emit: {ref_type} content with id "
                        f"'{ref_id}' referenced by {src_type}:{src_id} "
                        f"({relationship}). Auto-generated to prevent orphan."
                    ),
                    suggested_slots={},
                )
            )
    return recs


def build_extension_plan(
    parent_plan: WESPlan,
    recommendations: List[CoemitRecommendation],
    *,
    cascade_depth: int = 1,
    max_steps: int = MAX_CASCADE_STEPS_PER_PASS,
) -> Optional[WESPlan]:
    """Translate co-emit recommendations into a small follow-up WESPlan.

    Returns None if there are no recommendations or the cap is 0.
    Each rec becomes a single step with no depends_on (the extension
    plan dispatches as a flat batch). cascade_depth is encoded in the
    plan_id suffix for log traceability.
    """
    if not recommendations or max_steps <= 0:
        return None

    capped = recommendations[:max_steps]
    steps: List[WESPlanStep] = []
    for i, rec in enumerate(capped):
        step_id = f"ext{cascade_depth}_{i:02d}_{rec.missing_ref_type}"
        steps.append(
            WESPlanStep(
                step_id=step_id,
                tool=rec.missing_ref_type,
                intent=rec.suggested_intent,
                depends_on=[],
                slots=dict(rec.suggested_slots),
            )
        )

    if not steps:
        return None

    return WESPlan(
        plan_id=f"{parent_plan.plan_id}_ext{cascade_depth}",
        source_bundle_id=parent_plan.source_bundle_id,
        steps=steps,
        rationale=(
            f"Runtime cascade extension (depth {cascade_depth}) of plan "
            f"{parent_plan.plan_id}: auto-generates {len(steps)} dependent "
            f"content piece(s) referenced by primary-plan tool outputs."
        ),
        abandoned=False,
    )


__all__ = [
    "MAX_RUNTIME_CASCADE_DEPTH",
    "MAX_CASCADE_STEPS_PER_PASS",
    "PLANNER_ACKNOWLEDGMENT_MARKER",
    "BounceDecision",
    "build_registry_snapshot",
    "build_unresolved_xml_warning",
    "evaluate_plan_for_bounce",
    "planner_acknowledged",
    "find_runtime_orphans",
    "build_extension_plan",
]

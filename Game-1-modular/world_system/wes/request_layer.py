"""Request Layer — code-driven, single-step orphan resolution.

When a Tier-3 executor_tool emits content that names a cross-reference
the registry can't satisfy (e.g. a quest with ``target_id="wolf_grey"``
but no such hostile staged), the orchestrator's runtime cascade detects
the orphan via :func:`world_system.wes.plan_resolution.find_runtime_orphans`.
The Request Layer is what runs next: it converts each
:class:`CoemitRecommendation` directly into an :class:`ExecutorSpec`
(no hub call, no synthetic plan) and hands the spec to the executor_tool
for the missing tool type.

Design rationale (per user direction, 2026-04-29):

- **Pure-code detection + spec construction.** Faster than asking a
  supervisor LLM to decide, more robust because the recommendation
  logic is deterministic and unit-testable.
- **No re-planning.** The chain is naturally self-propagating — the
  prompts each Tier-3 executor_tool expects are stable, so we can hand
  it a synthetic spec without going back through the planner or hub.
  This lets us "request" generation of one specific missing item
  without duplicating planner / hub work.
- **Context-aware.** The spec builder pulls the requesting item's
  payload out of the registry so flavor / cross-ref hints can mention
  what's drawing the request (the quest that named the missing enemy,
  the chunk that named the missing resource, etc.).

Module shape:

  RequestLayer
    ├─ build_specs(recommendations, registry, bundle)
    │      → Dict[tool_name, List[ExecutorSpec]]   (grouped by target tool)
    └─ build_one(recommendation, registry, bundle)
           → (tool_name, ExecutorSpec)             (single rec helper)

The dispatcher path that consumes these specs is
:meth:`world_system.wes.plan_dispatcher.PlanDispatcher.run_request_specs`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from world_system.wes.dataclasses import ExecutorSpec
from world_system.wes.plan_resolution import CoemitRecommendation


# ── Default tier inference ────────────────────────────────────────────
# When the requesting item declares a tier, we use it; otherwise we
# fall back to T1 (a safe lowest-common-denominator). Designer can
# override per-tool here when the heuristic gets sharper.

_DEFAULT_TIER: int = 1


# ── Per-tool ID-key probes ────────────────────────────────────────────
# When pulling a payload from the registry to mine for context, we
# need to identify the row by its content_id. Different tools use
# different field names for "the id"; this table mirrors the same
# mapping in xref_rules._get_content_id and the helpers in
# plan_resolution._staged_payload_iter.

_ID_KEY_CANDIDATES: Dict[str, Tuple[str, ...]] = {
    "materials": ("materialId", "material_id", "id"),
    "hostiles":  ("enemyId", "enemy_id", "hostileId", "hostile_id"),
    "nodes":     ("nodeId", "node_id", "resourceNodeId", "resource_node_id"),
    "skills":    ("skillId", "skill_id"),
    "titles":    ("titleId", "title_id"),
    "chunks":    ("chunkType", "chunk_type", "chunkTypeId"),
    "npcs":      ("npc_id", "npcId"),
    "quests":    ("quest_id", "questId"),
}


# ── Result container ─────────────────────────────────────────────────

@dataclass
class RequestSpecBatch:
    """Specs grouped by the target tool that should generate them.

    ``tool_specs[tool] = [ExecutorSpec, ...]`` — one fan-out per tool.
    The dispatcher's tool-only fan-out path consumes this directly.
    """
    tool_specs: Dict[str, List[ExecutorSpec]]
    cascade_depth: int = 0
    parent_plan_id: str = ""

    def is_empty(self) -> bool:
        return not any(self.tool_specs.values())

    def total_specs(self) -> int:
        return sum(len(v) for v in self.tool_specs.values())


# ── Helpers (pure functions, easily testable) ────────────────────────

def _parse_requested_by(
    requested_by_step_id: str,
) -> Tuple[Optional[str], Optional[str]]:
    """Parse ``runtime_<tool>:<content_id>`` produced by find_runtime_orphans.

    Returns ``(tool, content_id)``, or ``(None, None)`` if the format is
    unrecognized (e.g. plan-time recs use just step_ids).
    """
    if not isinstance(requested_by_step_id, str):
        return None, None
    if not requested_by_step_id.startswith("runtime_"):
        return None, None
    tail = requested_by_step_id[len("runtime_"):]
    if ":" not in tail:
        return None, None
    tool, content_id = tail.split(":", 1)
    return tool or None, content_id or None


def _find_staged_payload(
    registry: Any, plan_id: str, tool: str, content_id: str,
) -> Optional[Dict[str, Any]]:
    """Look up a staged row's payload by (tool, content_id).

    Returns ``None`` on any failure — registry unwired, plan not found,
    row not present, malformed payload. Callers fall back to a thin
    spec.
    """
    if registry is None or not hasattr(registry, "list_staged_by_plan"):
        return None
    try:
        groups = registry.list_staged_by_plan(plan_id) or {}
    except Exception:
        return None

    rows = groups.get(tool, []) or []
    candidates = _ID_KEY_CANDIDATES.get(tool, ("content_id", "id"))
    for row in rows:
        if not isinstance(row, dict):
            continue
        payload = row.get("payload_json")
        if not isinstance(payload, dict):
            continue
        # Match content_id field via tool-specific key probes; also
        # honor the registry's content_id column directly.
        row_id = row.get("content_id")
        if row_id == content_id:
            return payload
        for key in candidates:
            if payload.get(key) == content_id:
                return payload
    return None


def _infer_tier(payload: Optional[Dict[str, Any]]) -> int:
    """Pull a tier int out of a payload, defaulting to T1."""
    if not isinstance(payload, dict):
        return _DEFAULT_TIER
    val = payload.get("tier")
    if isinstance(val, int):
        return max(1, min(4, val))
    if isinstance(val, str) and val.isdigit():
        return max(1, min(4, int(val)))
    return _DEFAULT_TIER


def _extract_address_from_bundle(bundle: Any) -> str:
    """Pull a geographic address (e.g. ``"region:ashfall_moors"``) off the
    bundle. Empty string when the bundle is absent or unstructured."""
    if bundle is None:
        return ""
    delta = getattr(bundle, "delta", None)
    addr = getattr(delta, "address", None) if delta is not None else None
    if isinstance(addr, str) and addr:
        return addr
    # Older / fixture bundles may stash on .narrative_context or root.
    nc = getattr(bundle, "narrative_context", None)
    if nc is not None:
        a2 = getattr(nc, "firing_address", None)
        if isinstance(a2, str):
            return a2
    return ""


def _short_narrative(payload: Optional[Dict[str, Any]]) -> str:
    """Pull a short narrative blurb from the requesting payload — used
    as flavor_hints text. Tolerates several shapes."""
    if not isinstance(payload, dict):
        return ""
    metadata = payload.get("metadata")
    if isinstance(metadata, dict):
        for key in ("narrative", "description", "summary"):
            v = metadata.get(key)
            if isinstance(v, str) and v.strip():
                return v.strip()
    for key in ("narrative", "description", "summary", "title"):
        v = payload.get(key)
        if isinstance(v, str) and v.strip():
            return v.strip()
    return ""


def _humanize_id(content_id: str) -> str:
    """Convert ``"moors_copper_seam"`` → ``"Moors Copper Seam"``.

    Used as a fallback name hint when the requesting payload has no
    narrative context for us to mine.
    """
    if not isinstance(content_id, str):
        return ""
    return " ".join(part.capitalize() for part in content_id.split("_"))


# ── Spec builder ─────────────────────────────────────────────────────

class RequestLayer:
    """Stateless builder. The orchestrator uses one instance per
    cascade pass; nothing is cached across passes.

    Public API is :meth:`build_specs` (batch) and :meth:`build_one`
    (single, useful for tests).
    """

    def build_specs(
        self,
        recommendations: List[CoemitRecommendation],
        *,
        registry: Any,
        bundle: Any,
        plan_id: str,
        cascade_depth: int = 1,
    ) -> RequestSpecBatch:
        """Convert a list of recommendations into per-tool spec batches.

        Recommendations targeting the same tool are batched together so
        the dispatcher fan-outs one parallel call per tool, not one per
        recommendation. Specs are deduped by (tool, missing_ref_id) to
        match find_runtime_orphans's de-dup contract.
        """
        batch: Dict[str, List[ExecutorSpec]] = {}
        seen: set = set()
        for idx, rec in enumerate(recommendations):
            key = (rec.missing_ref_type, rec.missing_ref_id)
            if key in seen:
                continue
            seen.add(key)

            tool, spec = self.build_one(
                rec, registry=registry, bundle=bundle,
                plan_id=plan_id, cascade_depth=cascade_depth, idx=idx,
            )
            if tool is None or spec is None:
                continue
            batch.setdefault(tool, []).append(spec)

        return RequestSpecBatch(
            tool_specs=batch,
            cascade_depth=cascade_depth,
            parent_plan_id=plan_id,
        )

    def build_one(
        self,
        rec: CoemitRecommendation,
        *,
        registry: Any,
        bundle: Any,
        plan_id: str,
        cascade_depth: int = 1,
        idx: int = 0,
    ) -> Tuple[Optional[str], Optional[ExecutorSpec]]:
        """Build one spec for one recommendation.

        Returns ``(target_tool, spec)`` on success, ``(None, None)`` if
        the rec is malformed (missing target tool or id).
        """
        target_tool = rec.missing_ref_type
        target_id = rec.missing_ref_id
        if not target_tool or not target_id:
            return None, None

        # Pull the requesting item's payload from the registry so we
        # can mine context. Only supports runtime_* requested_by ids
        # (find_runtime_orphans's format); plan-time recs land here
        # without a payload, which is fine — we degrade to a thin spec.
        req_tool, req_id = _parse_requested_by(rec.requested_by_step_id)
        requesting_payload: Optional[Dict[str, Any]] = None
        if req_tool and req_id:
            requesting_payload = _find_staged_payload(
                registry, plan_id, req_tool, req_id,
            )

        spec_id = self._make_spec_id(
            target_tool, target_id, cascade_depth, idx,
        )
        plan_step_id = self._virtual_step_id(target_tool, cascade_depth)

        item_intent = self._build_intent(rec, target_id, req_tool, req_id)
        flavor_hints = self._build_flavor_hints(
            target_tool, target_id, req_tool, req_id,
            requesting_payload, bundle,
        )
        cross_ref_hints = self._build_cross_ref_hints(
            target_tool, target_id, req_tool, req_id, rec,
        )
        hard_constraints = self._build_hard_constraints(
            target_tool, target_id, requesting_payload, bundle,
        )

        spec = ExecutorSpec(
            spec_id=spec_id,
            plan_step_id=plan_step_id,
            item_intent=item_intent,
            flavor_hints=flavor_hints,
            cross_ref_hints=cross_ref_hints,
            hard_constraints=hard_constraints,
        )
        return target_tool, spec

    # ── per-field helpers (overridable subclasses may shape these) ───

    @staticmethod
    def _make_spec_id(
        target_tool: str, target_id: str, depth: int, idx: int,
    ) -> str:
        # spec ids ride along to logs and tier results, so include
        # enough provenance to read them at a glance.
        return f"req_d{depth}_{idx:02d}_{target_tool}_{target_id}"

    @staticmethod
    def _virtual_step_id(target_tool: str, depth: int) -> str:
        """We're not a real plan step — but ExecutorSpec requires
        ``plan_step_id``, so use a stable virtual one. Logs / metrics
        consumers can group by this prefix."""
        return f"request_layer_d{depth}_{target_tool}"

    def _build_intent(
        self,
        rec: CoemitRecommendation,
        target_id: str,
        requesting_tool: Optional[str],
        requesting_id: Optional[str],
    ) -> str:
        # Prefer the planner-suggested intent (when find_runtime_orphans
        # populated it), otherwise synthesize a sentence the LLM can
        # use as the executor_tool's "item_intent" anchor.
        if rec.suggested_intent:
            return rec.suggested_intent
        if requesting_tool and requesting_id:
            return (
                f"Generate {rec.missing_ref_type} entry '{target_id}' — "
                f"referenced by {requesting_tool} '{requesting_id}'."
            )
        return f"Generate {rec.missing_ref_type} entry '{target_id}'."

    def _build_flavor_hints(
        self,
        target_tool: str,
        target_id: str,
        requesting_tool: Optional[str],
        requesting_id: Optional[str],
        requesting_payload: Optional[Dict[str, Any]],
        bundle: Any,
    ) -> Dict[str, Any]:
        hints: Dict[str, Any] = {
            "name_hint": _humanize_id(target_id),
        }
        narrative = _short_narrative(requesting_payload)
        if narrative:
            hints["referenced_by_narrative"] = narrative
        if requesting_tool and requesting_id:
            hints["referenced_by"] = {
                "tool": requesting_tool,
                "id": requesting_id,
            }
        # Bundle's address gives a region/locality the item should fit.
        addr = _extract_address_from_bundle(bundle)
        if addr:
            hints["geographic_address"] = addr
        return hints

    def _build_cross_ref_hints(
        self,
        target_tool: str,
        target_id: str,
        requesting_tool: Optional[str],
        requesting_id: Optional[str],
        rec: CoemitRecommendation,
    ) -> Dict[str, Any]:
        # Echo the suggested_slots from the recommendation when present
        # (find_runtime_orphans currently leaves these empty, but the
        # plan-time analyzer fills them — keep the seam).
        hints: Dict[str, Any] = dict(rec.suggested_slots or {})
        # Always pin the canonical id we want — the executor_tool MUST
        # emit content with this id as its primary identifier so the
        # cross-ref resolves. The id-key column varies per tool but
        # the tool prompt knows; this hint is for the prompt to read.
        hints["required_id"] = target_id
        if requesting_tool and requesting_id:
            hints["referenced_by_tool"] = requesting_tool
            hints["referenced_by_id"] = requesting_id
        return hints

    def _build_hard_constraints(
        self,
        target_tool: str,
        target_id: str,
        requesting_payload: Optional[Dict[str, Any]],
        bundle: Any,
    ) -> Dict[str, Any]:
        constraints: Dict[str, Any] = {
            "tier": _infer_tier(requesting_payload),
        }
        # Address (region/locality) lets the executor_tool keep biome
        # consistent with the firing address the bundle points at.
        addr = _extract_address_from_bundle(bundle)
        if addr:
            constraints["address"] = addr
        return constraints


__all__ = [
    "RequestLayer",
    "RequestSpecBatch",
]

"""Hub Dependency Resolver — static analysis of a WESPlan's cross-refs.

Walks a WESPlan's steps, extracts the cross-references implied by each
step's slots, and verifies that every ref will resolve. A ref is satisfied
when it points to:

1. Existing content in the registry, OR
2. An upstream step in the SAME plan whose tool produces that ref-type
   AND which the dependent step declares in ``depends_on``.

A ref is UNRESOLVED when neither holds. The analyzer emits co-emit
recommendations for unresolved refs but does NOT mutate the plan —
auto-coemit policy is the orchestrator's call.

Design intent (memory: hub_dependency_resolution):
- "Hubs reactively trigger upstream tools when refs are missing;
  recursive through the dep graph (chunk→nodes+hostiles→materials→...)"
- This module ships the DETECTION half; the trigger half is policy that
  follows once we know what we want to do with unresolved refs.

Faction tags (e.g. ``guild:moors_raiders``) are NOT validated — they are
emergent vocabulary, not registry rows. WNS narrative thread ids are
likewise free-form. Recipe ids are skipped because recipes aren't a WES
tool yet.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, FrozenSet, List, Optional, Set, Tuple

from world_system.wes.dataclasses import WESPlan, WESPlanStep


# ── Dependency graph ──────────────────────────────────────────────────
# Maps a ref-type (target tool name) to the set of slot-keys per
# producing tool. The analyzer uses this to extract cross-refs from each
# step's slots. ``None`` target_tool means the slot is emergent / opaque
# (e.g. faction tags).

# Per-tool slot keys whose VALUE is an id (or list of ids) referencing
# another tool. Format: source_tool -> [(slot_key, target_tool, is_list)].
# ``target_tool=None`` means the ref isn't validated (faction tag, free
# string, recipe id, etc.).
SLOT_REF_KEYS: Dict[str, List[Tuple[str, Optional[str], bool]]] = {
    "materials": [],  # leaf
    "skills": [],     # leaf
    "titles": [
        ("required_title", "titles", False),
        ("required_titles", "titles", True),
    ],
    "nodes": [
        ("material_id", "materials", False),
    ],
    "hostiles": [
        ("drop_material_ids", "materials", True),
        ("known_skills", "skills", True),
    ],
    "chunks": [
        ("primary_resource_ids", "nodes", True),
        ("primary_enemy_ids", "hostiles", True),
    ],
    "npcs": [
        ("home_chunk", "chunks", False),
        ("teachable_skill_ids", "skills", True),
        ("known_quest_ids", "quests", True),
        # affinity_seed_factions tags are emergent — not validated.
    ],
    "quests": [
        ("given_by", "npcs", False),
        ("return_to", "npcs", False),
        ("recipient_npc_id", "npcs", False),
        ("expiration_npc_id", "npcs", False),
        ("expiration_chunk_id", "chunks", False),
        ("title_hint", "titles", False),
        ("skill_hint", "skills", False),
        ("previous_quest_id", "quests", False),
        ("next_quest_id", "quests", False),
        # target_id is special — its target_tool is in a sibling slot.
        # See _extract_quest_target_ref below.
    ],
}


# ── Result shapes ─────────────────────────────────────────────────────


@dataclass
class ResolvedRef:
    """A cross-ref that will resolve at dispatch time."""
    source_step_id: str
    source_tool: str
    target_tool: str
    target_id: str
    resolution: str  # "registry" | "same_plan_upstream"


@dataclass
class UnresolvedRef:
    """A cross-ref that will NOT resolve unless the orchestrator acts."""
    source_step_id: str
    source_tool: str
    target_tool: str
    target_id: str
    reason: str  # "not_in_registry_or_plan" | "missing_depends_on"


@dataclass
class CoemitRecommendation:
    """Synthetic step proposal for an unresolved ref.

    The orchestrator may choose to inject this as a new step before
    dispatching the plan, or it may bail and request a planner rerun
    with adjusted_instructions.
    """
    missing_ref_type: str           # e.g. "materials"
    missing_ref_id: str             # e.g. "moors_copper"
    requested_by_step_id: str       # the step that referenced it
    suggested_intent: str           # one-line goal for the upstream tool
    suggested_slots: Dict[str, Any] = field(default_factory=dict)


@dataclass
class DependencyAnalysis:
    """Result of analyzing a WESPlan's cross-refs."""
    plan_id: str
    resolved_refs: List[ResolvedRef] = field(default_factory=list)
    unresolved_refs: List[UnresolvedRef] = field(default_factory=list)
    coemit_recommendations: List[CoemitRecommendation] = field(default_factory=list)

    @property
    def is_satisfiable(self) -> bool:
        """True iff every cross-ref will resolve as the plan stands."""
        return not self.unresolved_refs


# ── Extraction logic ──────────────────────────────────────────────────


def _extract_simple_refs(
    step: WESPlanStep,
) -> List[Tuple[str, Optional[str], str]]:
    """Pull (slot_key, target_tool, value) tuples from a step's slots.

    Lists are flattened — each id becomes its own tuple. Missing /
    empty values are skipped. ``target_tool=None`` indicates an opaque
    ref the analyzer should ignore.
    """
    out: List[Tuple[str, Optional[str], str]] = []
    rules = SLOT_REF_KEYS.get(step.tool, [])
    for slot_key, target_tool, is_list in rules:
        value = step.slots.get(slot_key)
        if value is None:
            continue
        if is_list:
            if not isinstance(value, list):
                continue
            for item in value:
                if isinstance(item, str) and item:
                    out.append((slot_key, target_tool, item))
        else:
            if isinstance(value, str) and value:
                out.append((slot_key, target_tool, value))
    return out


def _extract_quest_target_ref(
    step: WESPlanStep,
) -> Optional[Tuple[str, str, str]]:
    """Special-case quest's target_id — its target tool is in target_tool slot.

    Returns (slot_key, target_tool, target_id) or None.
    """
    if step.tool != "quests":
        return None
    target_id = step.slots.get("target_id")
    target_tool = step.slots.get("target_tool")
    if not isinstance(target_id, str) or not target_id:
        return None
    if not isinstance(target_tool, str) or target_tool not in SLOT_REF_KEYS:
        # target_tool not declared or not a known tool — skip silently.
        # (objective_type might be 'combat' which has no specific target.)
        return None
    return ("target_id", target_tool, target_id)


def _extract_all_refs(
    step: WESPlanStep,
) -> List[Tuple[str, Optional[str], str]]:
    """All cross-refs for a step. Combines simple + quest-special-case."""
    refs = _extract_simple_refs(step)
    quest_target = _extract_quest_target_ref(step)
    if quest_target is not None:
        refs.append(quest_target)
    return refs


# ── Analysis ──────────────────────────────────────────────────────────


def _build_step_outputs(plan: WESPlan) -> Dict[str, str]:
    """Map step_id -> tool, used to resolve same-plan refs.

    Returned dict tells us 'step s2 produces tool nodes'. We DON'T know
    the content_id the step will produce — co-emit refs satisfy by tool
    match: a quests step depending on an npcs step is enough to assume
    the npc will be produced.
    """
    return {step.step_id: step.tool for step in plan.steps}


def _suggest_intent(
    target_tool: str, target_id: str, parent_step: WESPlanStep
) -> str:
    """Generate a 1-line synthetic intent for a co-emit step.

    Deterministic — no LLM. The intent names the target id and the
    parent step that referenced it. The orchestrator / planner can
    refine if it wants better narrative.
    """
    return (
        f"Co-emit {target_tool} content with id '{target_id}' "
        f"referenced by plan step {parent_step.step_id} "
        f"({parent_step.tool}: {parent_step.intent[:50]})"
    )


def _suggest_slots(
    target_tool: str, parent_step: WESPlanStep
) -> Dict[str, Any]:
    """Inherit thematic slots from the parent step where sensible.

    Conservative: copies tier + biome from parent if present. The hub
    will fill rest from intent / bundle context.
    """
    suggested: Dict[str, Any] = {}
    for inheritable in ("tier", "biome"):
        if inheritable in parent_step.slots:
            suggested[inheritable] = parent_step.slots[inheritable]
    return suggested


def analyze_plan_dependencies(
    plan: WESPlan,
    registry_snapshot: Optional[Dict[str, FrozenSet[str]]] = None,
) -> DependencyAnalysis:
    """Analyze a plan's cross-refs against the registry. Pure function.

    Args:
        plan: the WESPlan to analyze.
        registry_snapshot: dict {tool_name: frozenset of committed
            content_ids}. Tools missing from the dict are treated as
            empty (no committed content). If None, every ref must be
            satisfied by a same-plan upstream step.

    Returns:
        DependencyAnalysis with resolved refs, unresolved refs, and
        co-emit recommendations.
    """
    registry = registry_snapshot or {}
    step_outputs = _build_step_outputs(plan)
    step_map = {s.step_id: s for s in plan.steps}

    analysis = DependencyAnalysis(plan_id=plan.plan_id)
    seen_recommendations: Set[Tuple[str, str]] = set()

    for step in plan.steps:
        for slot_key, target_tool, target_id in _extract_all_refs(step):
            if target_tool is None:
                # Opaque ref — skip (faction tags, free strings, etc.)
                continue

            # 1. Registry-resolved?
            if target_id in registry.get(target_tool, frozenset()):
                analysis.resolved_refs.append(
                    ResolvedRef(
                        source_step_id=step.step_id,
                        source_tool=step.tool,
                        target_tool=target_tool,
                        target_id=target_id,
                        resolution="registry",
                    )
                )
                continue

            # 2. Same-plan upstream?
            #    Find any depends_on step that produces target_tool.
            upstream_match: Optional[str] = None
            for dep_id in step.depends_on:
                if step_outputs.get(dep_id) == target_tool:
                    upstream_match = dep_id
                    break

            if upstream_match is not None:
                analysis.resolved_refs.append(
                    ResolvedRef(
                        source_step_id=step.step_id,
                        source_tool=step.tool,
                        target_tool=target_tool,
                        target_id=target_id,
                        resolution="same_plan_upstream",
                    )
                )
                continue

            # 3. Check if any step in the plan produces this tool but
            #    isn't declared in depends_on — that's a missing-edge
            #    reason vs truly absent.
            any_producer = any(
                tool == target_tool and sid != step.step_id
                for sid, tool in step_outputs.items()
            )
            reason = (
                "missing_depends_on"
                if any_producer
                else "not_in_registry_or_plan"
            )

            analysis.unresolved_refs.append(
                UnresolvedRef(
                    source_step_id=step.step_id,
                    source_tool=step.tool,
                    target_tool=target_tool,
                    target_id=target_id,
                    reason=reason,
                )
            )

            # 4. Recommend a co-emit for "not_in_registry_or_plan" only —
            #    "missing_depends_on" is a planner bug, not a content gap.
            if reason == "not_in_registry_or_plan":
                key = (target_tool, target_id)
                if key in seen_recommendations:
                    continue
                seen_recommendations.add(key)
                analysis.coemit_recommendations.append(
                    CoemitRecommendation(
                        missing_ref_type=target_tool,
                        missing_ref_id=target_id,
                        requested_by_step_id=step.step_id,
                        suggested_intent=_suggest_intent(
                            target_tool, target_id, step
                        ),
                        suggested_slots=_suggest_slots(target_tool, step),
                    )
                )

    return analysis


# ── Public API ────────────────────────────────────────────────────────


__all__ = [
    "DependencyAnalysis",
    "ResolvedRef",
    "UnresolvedRef",
    "CoemitRecommendation",
    "SLOT_REF_KEYS",
    "analyze_plan_dependencies",
]

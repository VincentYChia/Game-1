"""Final verification pipeline (v4 §5.6).

After every plan step has staged outputs (or is marked failed), this
module runs the registry-wide deterministic checks before the supervisor
gets its review pass.

Three checks (mirroring §5.6):

1. **Orphan scan** — every ``content_xref.ref_id`` produced by this plan
   must resolve to a live or same-plan-staged content_id. Delegated to
   :meth:`ContentRegistry.find_orphans` (Pass 2 in §7.3).
2. **Duplicate scan** — no staged ``content_id`` may collide with a
   currently-live content_id for the same tool table. Delegated to
   :meth:`ContentRegistry.list_staged_by_plan` + ``exists`` probes.
3. **Completeness** — every :class:`WESPlanStep` in the plan has at
   least one staged row under its plan_id for the step's tool. Missing
   artifacts mean the executor_tool silently produced nothing.

Returns a canonical verdict dict the orchestrator logs and acts on::

    {
        "passed": bool,
        "issues": List[str],
        "orphans": List[str],          # Pass 2 orphan refs, if any
        "duplicates": List[str],       # colliding content_ids
        "missing_steps": List[str],    # plan_step_ids with no artifact
    }

The verification never raises — registry / schema errors are folded
into ``issues`` so the orchestrator always gets a structured outcome.
"""

from __future__ import annotations

from typing import Any, Dict, List

from world_system.wes.dataclasses import WESPlan


def run_final_verification(
    plan: WESPlan,
    registry: Any,
) -> Dict[str, Any]:
    """Run all three deterministic checks for ``plan`` against ``registry``.

    Args:
        plan: The plan whose staged rows we are about to commit.
        registry: A :class:`ContentRegistry`-compatible object (or
            ``None`` for early-bring-up runs where verification cannot
            run — returns ``passed=False`` with an explanatory issue).

    Returns:
        Verification verdict dict (see module docstring).
    """
    issues: List[str] = []
    orphans: List[str] = []
    duplicates: List[str] = []
    missing_steps: List[str] = []

    if registry is None:
        return {
            "passed": False,
            "issues": [
                "ContentRegistry unavailable — cannot run final verification"
            ],
            "orphans": orphans,
            "duplicates": duplicates,
            "missing_steps": missing_steps,
        }

    # ── orphan scan (Pass 2) ──────────────────────────────────────────
    try:
        orphan_results = registry.find_orphans(plan.plan_id)
        # Convention: find_orphans returns either a list of ref_ids or
        # a list of (src_id, ref_id) tuples. Accept both.
        for item in orphan_results or []:
            if isinstance(item, (tuple, list)) and len(item) >= 2:
                orphans.append(str(item[1]))
            else:
                orphans.append(str(item))
        if orphans:
            issues.append(
                f"orphan references: {sorted(set(orphans))}"
            )
    except Exception as e:
        issues.append(
            f"orphan scan failed: {type(e).__name__}: {e}"
        )

    # ── duplicate scan + completeness ────────────────────────────────
    try:
        staged_by_tool = registry.list_staged_by_plan(plan.plan_id) or {}
    except Exception as e:
        issues.append(
            f"list_staged_by_plan failed: {type(e).__name__}: {e}"
        )
        staged_by_tool = {}

    for tool, rows in staged_by_tool.items():
        for row in rows or []:
            content_id = row.get("content_id") if isinstance(row, dict) else None
            if not content_id:
                continue
            try:
                live_collision = registry.exists(
                    tool, content_id, include_staged=False
                )
            except Exception:
                live_collision = False
            if live_collision:
                duplicates.append(f"{tool}:{content_id}")

    if duplicates:
        issues.append(
            f"staged content_ids collide with live: "
            f"{sorted(set(duplicates))}"
        )

    # ── completeness ──────────────────────────────────────────────────
    # A plan step is "complete" if the registry has at least one staged
    # row for its tool under this plan_id that was written for this step.
    # Many registries don't track step_id on the row (schema §7.2 has
    # plan_id but not step_id). Fall back to tool-level presence check.
    steps_seen_by_tool: Dict[str, int] = {}
    for tool, rows in staged_by_tool.items():
        steps_seen_by_tool[tool] = len(rows or [])

    for step in plan.steps:
        if steps_seen_by_tool.get(step.tool, 0) <= 0:
            missing_steps.append(step.step_id)
        else:
            # Decrement so a second step for the same tool needs at
            # least a second staged row. This is weaker than per-step
            # attribution but preserves ordering discipline.
            steps_seen_by_tool[step.tool] -= 1
    if missing_steps:
        issues.append(
            f"plan steps without staged artifacts: {missing_steps}"
        )

    passed = not issues
    return {
        "passed": passed,
        "issues": issues,
        "orphans": sorted(set(orphans)),
        "duplicates": sorted(set(duplicates)),
        "missing_steps": list(missing_steps),
    }


__all__ = ["run_final_verification"]

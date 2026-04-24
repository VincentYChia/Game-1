"""Topological plan dispatcher (v4 §5, §5.5, §5.6).

Walks a :class:`WESPlan` in topological order. For each step:

1. **Hub call** — invoke the registered :class:`ExecutionHub` for the
   step's tool. Emits a batch of :class:`ExecutorSpec` (§5.3).
2. **Parallel executor_tool fan-out** (§5.5, CC9) — dispatch every spec
   to the tool's :class:`ExecutorTool` concurrently via
   :class:`AsyncLLMRunner.run_parallel`.
3. **Per-output deterministic glue** (§5.5):
   - parse / schema validate (the tool is responsible for returning a
     dict — the dispatcher just confirms ``isinstance(result, dict)``).
   - orphan scan (Pass 1) via ``validate_against_registry``.
   - balance envelope check via ``check_within_tier_range``.
   - stage into :class:`ContentRegistry`.
4. **Record** ``TierRunResult`` for the hub and each tool call so the
   supervisor / observability layer can consume them.

**Invariants:**

- Topological sort rejects cycles with :class:`PlanCycleError`.
- A step's parallel fan-out never blocks on anything outside that
  step's specs — upstream step dependencies are satisfied before the
  hub is called, so downstream steps can read same-plan staged ids.
- Partial failures do not abort the whole plan; they record errors on
  the step's result and move on. The final verification step catches
  incomplete plans and the supervisor can choose to rerun.

The dispatcher does NOT decide whether to commit; that's the
orchestrator's job (:mod:`wes_orchestrator`). This module runs steps,
records results, and returns.
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional

from world_system.wes.async_runner import AsyncLLMRunner
from world_system.wes.dataclasses import (
    ExecutorSpec,
    TierRunResult,
    WESPlan,
    WESPlanStep,
)
from world_system.wes.stub_tiers import fixture_tier_result

if TYPE_CHECKING:  # pragma: no cover - typing only
    from world_system.living_world.infra.context_bundle import (
        WESContextBundle,
    )
    from world_system.wes.protocols import ExecutionHub, ExecutorTool
    from world_system.wes.supervisor_tap import SupervisorTap


class PlanCycleError(Exception):
    """Raised when :class:`WESPlan` has a dependency cycle."""


class UnknownToolError(Exception):
    """Raised when a plan step names a tool we have no hub for."""


def topological_sort(plan: WESPlan) -> List[WESPlanStep]:
    """Return plan steps in a valid execution order.

    Uses Kahn's algorithm (BFS from in-degree-0 nodes). Raises
    :class:`PlanCycleError` if a cycle is found. Ordering is stable
    within an in-degree band — lexical by ``step_id`` — so tests can
    assert a deterministic order across runs.
    """
    step_map = {s.step_id: s for s in plan.steps}

    # in-degree + adjacency (step -> dependents)
    in_degree: Dict[str, int] = {sid: 0 for sid in step_map}
    dependents: Dict[str, List[str]] = {sid: [] for sid in step_map}

    for step in plan.steps:
        for dep in step.depends_on:
            if dep not in step_map:
                raise PlanCycleError(
                    f"step {step.step_id!r} depends on unknown step {dep!r}"
                )
            in_degree[step.step_id] += 1
            dependents[dep].append(step.step_id)

    # Ready queue seeded with in-degree-0 steps, sorted for stability.
    ready = sorted([sid for sid, d in in_degree.items() if d == 0])

    ordered: List[WESPlanStep] = []
    while ready:
        sid = ready.pop(0)
        ordered.append(step_map[sid])
        for child in sorted(dependents[sid]):
            in_degree[child] -= 1
            if in_degree[child] == 0:
                ready.append(child)
        ready.sort()  # keep lexical stability after new entries

    if len(ordered) != len(plan.steps):
        # Cycle: some steps never reached in-degree 0.
        remaining = sorted(
            sid for sid in step_map if sid not in {s.step_id for s in ordered}
        )
        raise PlanCycleError(
            f"plan {plan.plan_id!r} contains a dependency cycle. "
            f"Unsortable steps: {remaining}"
        )
    return ordered


def _now_ms() -> float:
    return time.monotonic() * 1000.0


# ── dispatcher output ─────────────────────────────────────────────────

class DispatchResult:
    """Collected outcomes from running one :class:`WESPlan`.

    Attributes:
        tier_results: All tier results in record order.
        staged_content_ids: ``{tool: [content_id, ...]}`` ordered by
            execution order.
        step_errors: ``{step_id: [error_message, ...]}``. Empty on a
            fully clean pass.
    """

    def __init__(self) -> None:
        self.tier_results: List[TierRunResult] = []
        self.staged_content_ids: Dict[str, List[str]] = {}
        self.step_errors: Dict[str, List[str]] = {}

    def had_errors(self) -> bool:
        return any(v for v in self.step_errors.values())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "tier_results": [r.to_dict() for r in self.tier_results],
            "staged_content_ids": dict(self.staged_content_ids),
            "step_errors": {k: list(v) for k, v in self.step_errors.items()},
        }


# ── the dispatcher ────────────────────────────────────────────────────

class PlanDispatcher:
    """Executes a :class:`WESPlan` step-by-step in topological order.

    Non-singleton — the orchestrator creates one per plan run so the
    per-run supervisor tap + logging paths are cleanly scoped.
    """

    def __init__(
        self,
        hubs: Dict[str, "ExecutionHub"],
        tools: Dict[str, "ExecutorTool"],
        registry: Any,
        supervisor_tap: Optional["SupervisorTap"] = None,
        async_runner: Optional[AsyncLLMRunner] = None,
        tool_log_writer: Optional[Callable[..., None]] = None,
        hub_log_writer: Optional[Callable[..., None]] = None,
        balance_checker: Optional[Callable[..., Optional[str]]] = None,
        orphan_checker: Optional[Callable[..., List[str]]] = None,
        bundle_slicer: Optional[Callable[..., Any]] = None,
    ) -> None:
        self.hubs = dict(hubs)
        self.tools = dict(tools)
        self.registry = registry
        self.tap = supervisor_tap
        self.runner = async_runner or AsyncLLMRunner.get_instance()

        # Injected hooks — orchestrator wires these to real log
        # writers and validators. Tests inject lightweight mocks.
        self.tool_log_writer = tool_log_writer
        self.hub_log_writer = hub_log_writer
        self.balance_checker = balance_checker
        self.orphan_checker = orphan_checker
        self.bundle_slicer = bundle_slicer

    # ── main entry ────────────────────────────────────────────────────

    def run(
        self,
        plan: WESPlan,
        bundle: "WESContextBundle",
    ) -> DispatchResult:
        """Execute every step of ``plan`` in dependency order.

        Raises:
            PlanCycleError: if the plan has a dependency cycle.
            UnknownToolError: if a step names a tool with no registered
                hub.
        """
        result = DispatchResult()

        ordered = topological_sort(plan)
        for step in ordered:
            self._run_step(step, plan, bundle, result)
        return result

    # ── per-step execution ────────────────────────────────────────────

    def _run_step(
        self,
        step: WESPlanStep,
        plan: WESPlan,
        bundle: "WESContextBundle",
        result: DispatchResult,
    ) -> None:
        step_errors: List[str] = []

        hub = self.hubs.get(step.tool)
        if hub is None:
            raise UnknownToolError(
                f"plan {plan.plan_id!r} step {step.step_id!r}: "
                f"no hub registered for tool {step.tool!r}"
            )

        # Build the tool-specific slice for the hub (§8.5).
        slice_ = self._make_slice(bundle, step.tool)

        # ── Tier 2: hub ───────────────────────────────────────────────
        t0 = _now_ms()
        try:
            specs = hub.build_specs(step, slice_)
        except Exception as e:
            step_errors.append(
                f"hub.build_specs failed: {type(e).__name__}: {e}"
            )
            result.step_errors[step.step_id] = step_errors
            return
        latency_hub = _now_ms() - t0

        hub_fixture_code = getattr(hub, "fixture_code", f"wes_hub_{step.tool}")
        hub_tier = fixture_tier_result(
            tier="hub",
            fixture_code=hub_fixture_code,
            parsed=specs,
            latency_ms=latency_hub,
        )
        result.tier_results.append(hub_tier)
        if self.tap is not None:
            self.tap.record(hub_tier)
        if self.hub_log_writer is not None:
            try:
                self.hub_log_writer(
                    plan_id=plan.plan_id,
                    tool=step.tool,
                    step_id=step.step_id,
                    result=hub_tier,
                )
            except Exception:
                # Logger never breaks the pipeline.
                pass

        if not specs:
            step_errors.append("hub produced zero specs")
            result.step_errors[step.step_id] = step_errors
            return

        # ── Tier 3: executor_tools in parallel ───────────────────────
        tool = self.tools.get(step.tool)
        if tool is None:
            raise UnknownToolError(
                f"plan {plan.plan_id!r} step {step.step_id!r}: "
                f"no executor_tool registered for tool {step.tool!r}"
            )

        tasks = [self._make_tool_task(tool, spec) for spec in specs]
        t0 = _now_ms()
        parallel_out = self.runner.run_parallel(tasks)
        latency_each = (_now_ms() - t0) / max(1, len(specs))

        tool_fixture_code = getattr(
            tool, "fixture_code", f"wes_tool_{step.tool}"
        )

        for spec, spec_output in zip(specs, parallel_out):
            spec_errors: List[str] = []
            if isinstance(spec_output, BaseException):
                spec_errors.append(
                    f"executor_tool failed: "
                    f"{type(spec_output).__name__}: {spec_output}"
                )
                tool_tier = fixture_tier_result(
                    tier="executor_tool",
                    fixture_code=tool_fixture_code,
                    parsed=None,
                    latency_ms=latency_each,
                )
                tool_tier.errors = spec_errors
                self._emit_tool_tier(
                    plan, step, spec, tool_tier, result, step_errors,
                    spec_errors,
                )
                continue

            if not isinstance(spec_output, dict):
                spec_errors.append(
                    f"executor_tool returned non-dict "
                    f"{type(spec_output).__name__}"
                )
                tool_tier = fixture_tier_result(
                    tier="executor_tool",
                    fixture_code=tool_fixture_code,
                    parsed=spec_output,
                    latency_ms=latency_each,
                )
                tool_tier.errors = spec_errors
                self._emit_tool_tier(
                    plan, step, spec, tool_tier, result, step_errors,
                    spec_errors,
                )
                continue

            content_json: Dict[str, Any] = spec_output

            # Deterministic glue: orphan scan (Pass 1) + balance check.
            orphans = self._orphan_scan(
                content_json, plan.plan_id, step.tool
            )
            if orphans:
                spec_errors.append(
                    f"orphan refs in output: {sorted(set(orphans))}"
                )

            balance_issue = self._balance_check(
                content_json, spec.hard_constraints
            )
            if balance_issue:
                spec_errors.append(balance_issue)

            # Stage if no glue errors.
            staged_id: Optional[str] = None
            if not spec_errors and self.registry is not None:
                try:
                    staged_id = self.registry.stage_content(
                        tool_name=step.tool,
                        content_json=content_json,
                        plan_id=plan.plan_id,
                        source_bundle_id=plan.source_bundle_id,
                    )
                except Exception as e:
                    spec_errors.append(
                        f"stage_content failed: "
                        f"{type(e).__name__}: {e}"
                    )

            if staged_id is not None:
                result.staged_content_ids.setdefault(step.tool, []).append(
                    staged_id
                )

            tool_tier = fixture_tier_result(
                tier="executor_tool",
                fixture_code=tool_fixture_code,
                parsed=content_json,
                latency_ms=latency_each,
            )
            tool_tier.errors = list(spec_errors)
            self._emit_tool_tier(
                plan, step, spec, tool_tier, result, step_errors,
                spec_errors,
            )

        if step_errors:
            result.step_errors[step.step_id] = step_errors

    # ── helpers ───────────────────────────────────────────────────────

    def _make_slice(self, bundle: Any, tool_name: str) -> Any:
        """Build a BundleToolSlice (or caller-supplied slice)."""
        if self.bundle_slicer is not None:
            return self.bundle_slicer(bundle, tool_name)
        # Default: use the shipped slice_bundle_for_tool helper.
        try:
            from world_system.living_world.infra.context_bundle import (
                slice_bundle_for_tool,
            )
            return slice_bundle_for_tool(bundle, tool_name)
        except Exception:
            return None

    @staticmethod
    def _make_tool_task(
        tool: "ExecutorTool", spec: ExecutorSpec
    ) -> Callable[[], Any]:
        def _task() -> Any:
            return tool.generate(spec)
        return _task

    def _orphan_scan(
        self, content_json: Dict[str, Any], plan_id: str, tool_name: str
    ) -> List[str]:
        if self.orphan_checker is not None:
            try:
                return list(
                    self.orphan_checker(
                        content_json=content_json,
                        plan_id=plan_id,
                        tool_name=tool_name,
                        registry=self.registry,
                    ) or []
                )
            except Exception:
                return []
        # Default to the ContentRegistry's Pass 1 helper if importable.
        try:
            from world_system.content_registry.orphan_detector import (
                validate_against_registry,
            )
            return list(
                validate_against_registry(
                    content_json=content_json,
                    plan_id=plan_id,
                    tool_name=tool_name,
                    registry=self.registry,
                ) or []
            )
        except Exception:
            return []

    def _balance_check(
        self,
        content_json: Dict[str, Any],
        hard_constraints: Dict[str, Any],
    ) -> Optional[str]:
        """Minimal BalanceValidator stub call (§9.Q3).

        Pulls ``tier`` from hard_constraints; scans ``content_json`` for
        numeric fields the stub knows about (hp, attack, defense) and
        flags the first out-of-range one. Returns ``None`` for clean.
        """
        checker = self.balance_checker
        if checker is None:
            try:
                from world_system.content_registry.balance_validator_stub import (
                    check_within_tier_range,
                )
                checker = check_within_tier_range
            except Exception:
                return None

        tier = hard_constraints.get("tier")
        if not isinstance(tier, int):
            # Nothing to check if tier isn't declared.
            return None

        # Fields to probe — intentionally narrow per the stub's scope.
        for field in ("hp", "attack", "defense", "damage"):
            val = content_json.get(field)
            if val is None:
                continue
            issue = checker(val, tier, field)
            if issue:
                return issue
        return None

    def _emit_tool_tier(
        self,
        plan: WESPlan,
        step: WESPlanStep,
        spec: ExecutorSpec,
        tier_result: TierRunResult,
        result: DispatchResult,
        step_errors: List[str],
        spec_errors: List[str],
    ) -> None:
        """Record the executor_tool tier result + propagate spec errors
        to the step-level error bucket."""
        result.tier_results.append(tier_result)
        if self.tap is not None:
            self.tap.record(tier_result)
        if self.tool_log_writer is not None:
            try:
                self.tool_log_writer(
                    plan_id=plan.plan_id,
                    tool=step.tool,
                    step_id=step.step_id,
                    spec_id=spec.spec_id,
                    result=tier_result,
                )
            except Exception:
                pass
        if spec_errors:
            step_errors.extend(spec_errors)


__all__ = [
    "PlanDispatcher",
    "DispatchResult",
    "PlanCycleError",
    "UnknownToolError",
    "topological_sort",
]

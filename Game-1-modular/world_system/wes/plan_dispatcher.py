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
        # Canonical-id map {step_id: {"tool", "ids": [...]}} — populated as each
        # step stages; read by dependents to reconcile their cross-refs.
        canonical_by_step: Dict[str, Dict[str, Any]] = {}
        for step in ordered:
            self._run_step(step, plan, bundle, result, canonical_by_step)
        return result

    # ── Request Layer: tool-only fan-out (no hub call) ─────────────────

    def run_request_specs(
        self,
        tool_specs: Dict[str, List[ExecutorSpec]],
        *,
        plan_id: str,
        source_bundle_id: str,
        cascade_depth: int = 1,
    ) -> DispatchResult:
        """Dispatch synthetic request-layer specs straight to executor_tools.

        Used by the orchestrator's runtime cascade (see
        :class:`world_system.wes.request_layer.RequestLayer`). For each
        target tool with one or more specs, the dispatcher:

        1. Resolves the tool's :class:`ExecutorTool` via :attr:`tools`.
        2. Fan-outs every spec in parallel via :class:`AsyncLLMRunner`.
        3. Reuses the same per-spec glue as ``run()``: orphan scan,
           balance check, ContentRegistry stage, tier-result emit.

        No hub is called and no synthetic plan is constructed — the
        request layer's whole point is that we know exactly what we
        want generated, so the planner / hub roles are unnecessary.

        Returns a :class:`DispatchResult` shaped exactly like
        :meth:`run`'s output (sans hub tier records). Errors are
        recorded against a synthetic step id ``request_layer_<tool>``
        so the orchestrator can route them through its existing
        ``step_errors`` aggregation without special-casing.
        """
        result = DispatchResult()
        for tool_name, specs in tool_specs.items():
            if not specs:
                continue
            self._run_request_specs_for_tool(
                tool_name=tool_name,
                specs=specs,
                plan_id=plan_id,
                source_bundle_id=source_bundle_id,
                cascade_depth=cascade_depth,
                result=result,
            )
        return result

    def _run_request_specs_for_tool(
        self,
        *,
        tool_name: str,
        specs: List[ExecutorSpec],
        plan_id: str,
        source_bundle_id: str,
        cascade_depth: int,
        result: DispatchResult,
    ) -> None:
        """Inner half of :meth:`run_request_specs` — one tool's batch."""
        tool = self.tools.get(tool_name)
        if tool is None:
            # Synthetic step id surfaces in step_errors for visibility.
            virtual_step_id = f"request_layer_d{cascade_depth}_{tool_name}"
            result.step_errors.setdefault(virtual_step_id, []).append(
                f"no executor_tool registered for tool {tool_name!r}"
            )
            return

        tasks = [self._make_tool_task(tool, spec) for spec in specs]
        t0 = _now_ms()
        parallel_out = self.runner.run_parallel(tasks)
        latency_each = (_now_ms() - t0) / max(1, len(specs))

        tool_fixture_code = getattr(
            tool, "fixture_code", f"wes_tool_{tool_name}"
        )

        for spec, spec_output in zip(specs, parallel_out):
            self._handle_request_spec_result(
                tool_name=tool_name,
                spec=spec,
                spec_output=spec_output,
                plan_id=plan_id,
                source_bundle_id=source_bundle_id,
                latency_each=latency_each,
                tool_fixture_code=tool_fixture_code,
                cascade_depth=cascade_depth,
                result=result,
            )

    def _handle_request_spec_result(
        self,
        *,
        tool_name: str,
        spec: ExecutorSpec,
        spec_output: Any,
        plan_id: str,
        source_bundle_id: str,
        latency_each: float,
        tool_fixture_code: str,
        cascade_depth: int,
        result: DispatchResult,
    ) -> None:
        """Per-spec glue, factored from ``_run_step`` so the request-layer
        path doesn't duplicate orphan-scan / balance-check / stage code.

        Differences from ``_run_step``'s body:
        - There's no real :class:`WESPlanStep` to attach the tool tier
          result to, so we emit with a synthetic ``step.step_id`` shaped
          like ``request_layer_d<depth>_<tool>``.
        - Errors land in ``result.step_errors[virtual_step_id]`` so the
          orchestrator's existing aggregation surfaces them.
        """
        virtual_step_id = f"request_layer_d{cascade_depth}_{tool_name}"
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
            self._record_request_spec_tier(
                tool_tier, virtual_step_id, spec_errors, result,
            )
            return

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
            self._record_request_spec_tier(
                tool_tier, virtual_step_id, spec_errors, result,
            )
            return

        content_json: Dict[str, Any] = spec_output

        # Same Pass-1 orphan + balance checks as the plan path. New
        # orphans found here will be picked up by the *next* cascade
        # iteration — request layer is one-shot per recommendation,
        # but the cascade loop in the orchestrator handles depth.
        orphans = self._orphan_scan(content_json, plan_id, tool_name)
        if orphans:
            spec_errors.append(
                f"orphan refs in output: {sorted(set(orphans))}"
            )

        balance_issue = self._balance_check(
            content_json, spec.hard_constraints
        )
        if balance_issue:
            spec_errors.append(balance_issue)

        staged_id: Optional[str] = None
        if not spec_errors and self.registry is not None:
            try:
                staged_id = self.registry.stage_content(
                    tool_name=tool_name,
                    content_json=content_json,
                    plan_id=plan_id,
                    source_bundle_id=source_bundle_id,
                )
            except Exception as e:
                spec_errors.append(
                    f"stage_content failed: "
                    f"{type(e).__name__}: {e}"
                )

        if staged_id is not None:
            result.staged_content_ids.setdefault(tool_name, []).append(
                staged_id
            )

        tool_tier = fixture_tier_result(
            tier="executor_tool",
            fixture_code=tool_fixture_code,
            parsed=content_json,
            latency_ms=latency_each,
        )
        tool_tier.errors = list(spec_errors)
        self._record_request_spec_tier(
            tool_tier, virtual_step_id, spec_errors, result,
        )

    def _record_request_spec_tier(
        self,
        tier_result: TierRunResult,
        virtual_step_id: str,
        spec_errors: List[str],
        result: DispatchResult,
    ) -> None:
        result.tier_results.append(tier_result)
        if self.tap is not None:
            self.tap.record(tier_result)
        if spec_errors:
            result.step_errors.setdefault(virtual_step_id, []).extend(
                spec_errors
            )

    # ── per-step execution ────────────────────────────────────────────

    def _run_step(
        self,
        step: WESPlanStep,
        plan: WESPlan,
        bundle: "WESContextBundle",
        result: DispatchResult,
        canonical_by_step: Optional[Dict[str, Any]] = None,
    ) -> None:
        step_errors: List[str] = []

        hub = self.hubs.get(step.tool)
        if hub is None:
            raise UnknownToolError(
                f"plan {plan.plan_id!r} step {step.step_id!r}: "
                f"no hub registered for tool {step.tool!r}"
            )

        # Build the tool-specific slice for the hub (§8.5).
        slice_ = self._make_slice(bundle, step.tool, plan_id=plan.plan_id)

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

            # Canonical-id coordination (approach A, 2026-08-11): pin this
            # artifact's id and rewrite its INTENDED cross-refs to co-emitted
            # parents' canonical ids (deterministic; non-LLM normalizer for
            # drift). Without this each tool invents its own id and every
            # multi-step plan orphan-rolls-back despite good content.
            canonical_id, content_json = self._canonical_reconcile(
                step, specs, spec, content_json, canonical_by_step, plan.plan_id,
            )

            # Content-tag governance: keep only tags the game understands, route
            # NEW:-prefixed proposals for designer review, drop invented tags —
            # so the load-bearing tag system can't silently drift.
            content_json = self._govern_tags(step, content_json)

            # Deterministic glue: orphan scan (Pass 1) + balance check.
            orphans = self._orphan_scan(
                content_json, plan.plan_id, step.tool
            )
            if orphans:
                # Prune LLM-invented dangling refs (content that doesn't exist
                # and wasn't co-emitted), then re-scan. Keeps every RESOLVED
                # ref; enforces "cross-refs must resolve" without rolling back
                # the whole plan over one invented reference.
                from world_system.wes.canonical_ids import prune_orphan_refs
                content_json, pruned = prune_orphan_refs(
                    content_json, step.tool, set(orphans))
                if pruned:
                    print(f"[WES] pruned invented refs from "
                          f"{step.tool}/{step.step_id}: {sorted(set(pruned))}")
                orphans = self._orphan_scan(
                    content_json, plan.plan_id, step.tool)
                if orphans:
                    spec_errors.append(
                        f"orphan refs after prune: {sorted(set(orphans))}"
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
                # Record this step's canonical id so dependents resolve to it.
                if canonical_by_step is not None and canonical_id:
                    entry = canonical_by_step.setdefault(
                        step.step_id, {"tool": step.tool, "ids": []})
                    if canonical_id not in entry["ids"]:
                        entry["ids"].append(canonical_id)

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

    def _make_slice(self, bundle: Any, tool_name: str,
                    plan_id: Optional[str] = None) -> Any:
        """Build a BundleToolSlice (or caller-supplied slice)."""
        if self.bundle_slicer is not None:
            return self.bundle_slicer(bundle, tool_name)
        # Default: use the shipped slice_bundle_for_tool helper.
        try:
            from world_system.living_world.infra.context_bundle import (
                slice_bundle_for_tool,
            )
            return slice_bundle_for_tool(
                bundle, tool_name,
                recent_registry_entries=self._recent_registry_summary(
                    tool_name, plan_id=plan_id,
                ),
            )
        except Exception:
            return None

    def _recent_registry_summary(
        self, tool_name: str,
        plan_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Compact recent-content summary for the hub's context.

        Two sources (2026-07-10 hub audit):
        - LIVE rows of the same tool type — dedup context. The slice's
          ``recent_registry_entries`` was ALWAYS empty before (the hub
          prompt says "avoid duplication" and the design describes "a
          caller-supplied slice of recent same-type registry entries",
          but no caller ever supplied one).
        - Rows STAGED BY THIS PLAN across ALL tool types — co-emission
          context. The pipeline's own dependency rule ("referenced ids
          must exist OR be co-emitted") was unenforceable because hubs
          were blind to sibling steps' outputs (adversarial prompt
          review, finding #2). Steps run in topological order, so
          upstream steps' staged content is visible to downstream hubs.
          Entries carry a ``source`` field so prompts can distinguish.

        Best-effort: registry errors yield [].
        """
        summary: List[Dict[str, Any]] = []
        try:
            rows = self.registry.list_live(tool_name) or []
        except Exception:
            rows = []
        for row in rows[-8:]:  # newest last per insert order; cap for budget
            summary.append({
                "content_id": row.get("content_id"),
                "display_name": row.get("display_name"),
                "tier": row.get("tier"),
                "biome": row.get("biome"),
                "source": "live",
            })
        if plan_id:
            try:
                staged_by_tool = self.registry.list_staged_by_plan(plan_id) or {}
            except Exception:
                staged_by_tool = {}
            for staged_tool, staged_rows in staged_by_tool.items():
                for row in staged_rows[-6:]:
                    summary.append({
                        "content_id": row.get("content_id"),
                        "display_name": row.get("display_name"),
                        "tool": staged_tool,
                        "source": "co_emitted_this_plan",
                    })
        return summary

    @staticmethod
    def _make_tool_task(
        tool: "ExecutorTool", spec: ExecutorSpec
    ) -> Callable[[], Any]:
        def _task() -> Any:
            return tool.generate(spec)
        return _task

    def _canonical_reconcile(
        self,
        step: WESPlanStep,
        specs: List[ExecutorSpec],
        spec: ExecutorSpec,
        content_json: Dict[str, Any],
        canonical_by_step: Optional[Dict[str, Any]],
        plan_id: str,
    ):
        """Approach A: decide this artifact's canonical id, enforce it, and
        rewrite its intended cross-refs to co-emitted parents' canonical ids.

        Returns ``(canonical_id, reconciled_content_json)``.
        """
        from world_system.wes.canonical_ids import (
            get_emitted_id,
            normalize_id,
            reconcile_refs,
            slugify,
        )

        # 1. Canonical id: planner-pinned (single-spec steps), else the tool's
        #    own emitted id (keeps id/name coherent), else a slug of intent.
        canonical_id = ""
        if getattr(step, "content_id", "") and len(specs) == 1:
            canonical_id = normalize_id(step.content_id)
        if not canonical_id:
            canonical_id = normalize_id(get_emitted_id(content_json, step.tool))
        if not canonical_id:
            canonical_id = slugify(step.intent)

        # 2. Parent canonical ids by tool (from depends_on).
        parent_ids_by_tool: Dict[str, List[str]] = {}
        if canonical_by_step:
            for pid in step.depends_on:
                entry = canonical_by_step.get(pid)
                if entry and entry.get("ids"):
                    parent_ids_by_tool.setdefault(
                        entry["tool"], []).extend(entry["ids"])

        # 3. Known-id pool for the drift fallback + "already resolves" skip:
        #    this plan's staged rows PLUS what the game currently holds (sacred
        #    + previously-invented), so refs to real content aren't treated as
        #    orphans and the normalizer can reconcile drift against them.
        live_ids_by_tool: Dict[str, set] = {}
        if self.registry is not None:
            try:
                for tname, rows in (
                    self.registry.list_staged_by_plan(plan_id) or {}
                ).items():
                    ids = {r.get("content_id") for r in rows
                           if r.get("content_id")}
                    if ids:
                        live_ids_by_tool[tname] = ids
            except Exception:
                pass
            for tname in ("materials", "nodes", "hostiles", "skills",
                          "titles", "chunks", "npcs", "quests"):
                try:
                    known = self.registry.known_ids(tname)
                except Exception:
                    known = set()
                if known:
                    live_ids_by_tool.setdefault(tname, set()).update(known)

        # 4. The hub's declared cross-refs = the INTENDED dependencies.
        intended: set = set()
        for v in (spec.cross_ref_hints or {}).values():
            if isinstance(v, str):
                intended.add(v)
            elif isinstance(v, (list, tuple)):
                intended.update(x for x in v if isinstance(x, str))

        rec = reconcile_refs(
            content_json, step.tool,
            canonical_id=canonical_id,
            parent_ids_by_tool=parent_ids_by_tool,
            live_ids_by_tool=live_ids_by_tool,
            intended_ref_ids=intended,
        )
        return canonical_id, rec["content"]

    def _govern_tags(self, step: WESPlanStep,
                     content_json: Dict[str, Any]) -> Dict[str, Any]:
        """Validate generated content tags against the game's vocabulary."""
        if self.registry is None:
            return content_json
        try:
            valid = self.registry.known_tags(step.tool)
        except Exception:
            valid = set()
        if not valid:
            return content_json  # can't read vocabulary -> don't strip
        from world_system.wes.tag_governance import govern_content_tags
        content_json, _kept, dropped, proposed = govern_content_tags(
            content_json, step.tool, valid)
        if dropped:
            print(f"[WES] dropped unknown tags from {step.tool}/{step.step_id}: "
                  f"{sorted(set(dropped))}")
        if proposed:
            print(f"[WES] NEW: tag proposals from {step.tool}/{step.step_id} "
                  f"(designer review): {sorted(set(proposed))}")
            self._record_tag_proposals(step.tool, proposed)
        return content_json

    def _record_tag_proposals(self, tool: str, proposed: List[str]) -> None:
        """Append NEW: tag proposals to a designer-review sink (best-effort)."""
        try:
            save_dir = getattr(self.registry, "_save_dir", None)
            if not save_dir:
                return
            import json as _json
            import os as _os
            path = _os.path.join(save_dir, "wes_tag_proposals.jsonl")
            with open(path, "a", encoding="utf-8") as f:
                for tag in sorted(set(proposed)):
                    f.write(_json.dumps({"tool": tool, "tag": tag}) + "\n")
        except Exception:
            pass

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

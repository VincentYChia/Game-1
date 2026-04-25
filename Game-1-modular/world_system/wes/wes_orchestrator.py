"""Public entry point for WES plan execution (v4 §5.6).

The orchestrator glues together:

- :class:`ExecutionPlanner` (Tier 1) → :class:`WESPlan`
- :class:`PlanDispatcher` → hub + executor_tool fan-out + staging
- :class:`Supervisor` → cross-tier review + rerun decision
- :mod:`verification` → registry-wide orphan/dup/completeness scan
- ContentRegistry commit / rollback
- :mod:`observability` → per-plan log writes

**Control flow** (matches §5.6):

1. Call ``planner.plan(bundle)`` → :class:`WESPlan`.
2. If plan is abandoned: log + return with ``abandoned`` status.
3. Else call :class:`PlanDispatcher.run` → :class:`DispatchResult`.
4. Call ``supervisor.review(plan, tier_results, bundle)`` → verdict.
5. If ``verdict["rerun"]`` and ``reruns_remaining > 0``:
   - rollback any staged content
   - recurse with decremented budget and the supervisor's
     ``adjusted_instructions`` (currently stored on the recursion
     call-site — the real wiring will live on Agent D's LLM planner).
6. Else run final verification.
7. If verification passes: commit.
8. Else: rollback + ``surface_visible_wes_failure`` (CC3).

**WNS_CALL_WES_REQUESTED**: the orchestrator subscribes to this
:class:`GameEventBus` event on initialization. When fired, it
constructs a fixture-driven bundle (P5 stub — real bundle assembly is
WNS's job) and queues a plan run.

**Graceful-degrade rules** (CC3):

- If :class:`ContentRegistry` cannot be imported at orchestrator init,
  the orchestrator logs a degrade entry and disables itself. Calls to
  ``run_plan`` return an ``{"status": "disabled"}`` marker.
- Any uncaught exception in the run path is caught, logged via
  :func:`surface_visible_wes_failure`, and surfaces as ``status="error"``.
"""

from __future__ import annotations

import threading
import time
import uuid
from typing import Any, Dict, List, Optional

from world_system.living_world.infra.graceful_degrade import (
    log_degrade,
    surface_visible_wes_failure,
)
from world_system.wes import observability
from world_system.wes.async_runner import AsyncLLMRunner
from world_system.wes.dataclasses import (
    TierRunResult,
    WESPlan,
)
from world_system.wes.plan_dispatcher import (
    DispatchResult,
    PlanDispatcher,
    UnknownToolError,
)
from world_system.wes.stub_tiers import (
    StubExecutionPlanner,
    build_default_stub_hubs,
    build_default_stub_tools,
    fixture_tier_result,
)
from world_system.wes.supervisor_tap import (
    StubSupervisor,
    SupervisorTap,
    supervisor_result_to_tier_record,
)
from world_system.wes.verification import run_final_verification


# Event name subscribed to on initialization. See WNS plan for who
# fires this (WNS weavers on call_wes decisions).
WNS_CALL_WES_REQUESTED = "WNS_CALL_WES_REQUESTED"


class WESOrchestrator:
    """Singleton entry point for WES plan execution.

    The orchestrator is a thin supervisor of the dispatcher +
    supervisor + verification stack. All the interesting logic lives
    elsewhere; this class just wires it up.
    """

    _instance: Optional["WESOrchestrator"] = None
    _lock = threading.Lock()

    # Default rerun budget per §9.Q12 (1-2 per plan).
    DEFAULT_RERUN_BUDGET = 2

    def __init__(self) -> None:
        self._initialized: bool = False
        self._disabled_reason: Optional[str] = None
        self._planner = None
        self._hubs: Dict[str, Any] = {}
        self._tools: Dict[str, Any] = {}
        self._supervisor = None
        self._registry = None
        self._runner: Optional[AsyncLLMRunner] = None
        self._bus_subscribed: bool = False

    # ── singleton ─────────────────────────────────────────────────────

    @classmethod
    def get_instance(cls) -> "WESOrchestrator":
        with cls._lock:
            if cls._instance is None:
                cls._instance = cls()
            return cls._instance

    @classmethod
    def reset(cls) -> None:
        """Test helper — drop the singleton and any bus subscriptions."""
        with cls._lock:
            inst = cls._instance
            if inst is not None:
                try:
                    inst.shutdown()
                except Exception:
                    pass
            cls._instance = None

    # ── initialization ────────────────────────────────────────────────

    def initialize(
        self,
        planner=None,
        hubs: Optional[Dict[str, Any]] = None,
        tools: Optional[Dict[str, Any]] = None,
        supervisor=None,
        registry: Any = None,
        subscribe_to_bus: bool = True,
    ) -> None:
        """Wire up tiers and (optionally) subscribe to the event bus.

        If ``registry`` is None, attempts to import :class:`ContentRegistry`
        and acquire its singleton. If that import fails, the
        orchestrator disables itself (CC3 graceful-degrade).

        All other parameters default to the P5 fixture-driven stubs, so
        the orchestrator can run end-to-end without Agent D's LLM tiers
        or Agent B's ContentRegistry facade landing first.
        """
        if self._initialized:
            return

        self._planner = planner or StubExecutionPlanner()
        self._hubs = hubs if hubs is not None else build_default_stub_hubs()
        self._tools = tools if tools is not None else build_default_stub_tools()
        self._supervisor = supervisor or StubSupervisor()

        # Resolve registry
        if registry is not None:
            self._registry = registry
        else:
            self._registry = self._try_acquire_registry()

        self._runner = AsyncLLMRunner.get_instance()

        if subscribe_to_bus:
            self._try_subscribe()

        self._initialized = True

    def _try_acquire_registry(self) -> Any:
        """Attempt to import ContentRegistry. Degrade gracefully."""
        try:
            from world_system.content_registry.content_registry import (
                ContentRegistry,
            )
            return ContentRegistry.get_instance()
        except Exception as e:
            log_degrade(
                subsystem="wes",
                operation="initialize.acquire_registry",
                failure_reason=f"{type(e).__name__}: {e}",
                fallback_taken=(
                    "WESOrchestrator disabled; run_plan will return "
                    "status=disabled until ContentRegistry is available"
                ),
                severity="warning",
                context={"phase": "P5"},
            )
            self._disabled_reason = (
                f"ContentRegistry unavailable: {type(e).__name__}: {e}"
            )
            return None

    def _try_subscribe(self) -> None:
        """Subscribe to WNS_CALL_WES_REQUESTED on the GameEventBus."""
        try:
            from events.event_bus import get_event_bus
            bus = get_event_bus()
            bus.subscribe(WNS_CALL_WES_REQUESTED, self._on_bus_event)
            self._bus_subscribed = True
        except Exception as e:
            log_degrade(
                subsystem="wes",
                operation="initialize.subscribe_bus",
                failure_reason=f"{type(e).__name__}: {e}",
                fallback_taken="orchestrator will not be auto-triggered",
                severity="warning",
            )

    def shutdown(self) -> None:
        """Tear down subscriptions. Test / reload helper."""
        if self._bus_subscribed:
            try:
                from events.event_bus import get_event_bus
                bus = get_event_bus()
                bus.unsubscribe(WNS_CALL_WES_REQUESTED, self._on_bus_event)
            except Exception:
                pass
            self._bus_subscribed = False

    # ── event handler ─────────────────────────────────────────────────

    def _on_bus_event(self, event: Any) -> None:
        """Handle a WNS_CALL_WES_REQUESTED event.

        If the event payload carries a serialized ``wes_bundle`` (built
        by WNS via :func:`world_system.wns.wns_to_wes_bridge.build_wes_bundle`),
        we deserialize and dispatch against it directly — WES inherits
        the WNS state at the call site (cascading narrative, active
        threads, geographic descriptor, purpose).

        If the bundle is missing (legacy publishers or serialization
        failed), we fall back to a minimal fixture bundle so the
        pipeline still exercises end-to-end.
        """
        try:
            bundle = self._extract_bundle_from_event(event)
            if bundle is None:
                bundle = self._build_fixture_bundle()
            # Fire-and-forget on the async runner so the game thread
            # isn't blocked.
            if self._runner is not None:
                self._runner.run_single(
                    lambda: self.run_plan(bundle),
                    timeout_s=None,
                )
            else:
                self.run_plan(bundle)
        except Exception as e:
            surface_visible_wes_failure(
                operation="_on_bus_event",
                failure_reason=f"{type(e).__name__}: {e}",
                fallback_taken="plan run aborted",
            )

    @staticmethod
    def _extract_bundle_from_event(event: Any) -> Any:
        """Pull a serialized WESContextBundle out of a bus event payload.

        Returns the deserialized bundle, or None if the payload doesn't
        carry one or deserialization fails.
        """
        from world_system.living_world.infra.context_bundle import (
            WESContextBundle,
        )

        # Event objects may expose data via .data attribute or be a
        # plain dict. Defensive lookup.
        data = getattr(event, "data", None)
        if data is None and isinstance(event, dict):
            data = event
        if not isinstance(data, dict):
            return None

        bundle_dict = data.get("wes_bundle")
        if not isinstance(bundle_dict, dict):
            return None
        try:
            return WESContextBundle.from_dict(bundle_dict)
        except (KeyError, ValueError, TypeError):
            return None

    @staticmethod
    def _build_fixture_bundle() -> Any:
        """Assemble a minimal :class:`WESContextBundle` for P5 testing.

        Uses the ``wes_execution_planner`` fixture as a sanity starting
        point but does not parse it — the bundle here is a pure
        synthetic input that exercises the pipeline. WNS's real bundle
        assembler replaces this in a later phase.
        """
        from world_system.living_world.infra.context_bundle import (
            NarrativeContextSlice,
            NarrativeDelta,
            WESContextBundle,
            WNSDirective,
        )

        delta = NarrativeDelta(
            address="region:ashfall_moors",
            layer=4,
            start_time=0.0,
            end_time=1.0,
        )
        narrative = NarrativeContextSlice(
            firing_layer_summary=(
                "Ashfall Moors restructuring around copper trade."
            ),
        )
        directive = WNSDirective(
            directive_text=(
                "Generate content responding to the moors' economic "
                "realignment: new faction interests, new NPCs drawn "
                "to copper trade."
            ),
            firing_tier=4,
        )
        return WESContextBundle(
            bundle_id=f"bundle_{uuid.uuid4().hex[:12]}",
            created_at=time.time(),
            delta=delta,
            narrative_context=narrative,
            directive=directive,
        )

    # ── main entry ────────────────────────────────────────────────────

    def run_plan(
        self,
        bundle,
        reruns_remaining: Optional[int] = None,
        adjusted_instructions: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Run a plan end-to-end for ``bundle``.

        Args:
            bundle: The WES context bundle (authored by WNS).
            reruns_remaining: Rerun budget. Defaults to
                :attr:`DEFAULT_RERUN_BUDGET`. Decremented on supervisor
                rerun; once 0, supervisor rerun becomes a hard fail.
            adjusted_instructions: Supervisor's rerun notes from the
                previous pass; stored in the returned status and
                available to the planner (Agent D wires this in).

        Returns:
            Status dict with ``status`` (``committed | abandoned |
            rolled_back | disabled | error``) plus relevant detail
            (plan, verification verdict, supervisor verdict).
        """
        if not self._initialized:
            self.initialize()

        if self._disabled_reason is not None:
            return {
                "status": "disabled",
                "reason": self._disabled_reason,
                "bundle_id": getattr(bundle, "bundle_id", None),
            }

        if reruns_remaining is None:
            reruns_remaining = self.DEFAULT_RERUN_BUDGET

        tap = SupervisorTap()

        try:
            # ── Tier 1 — planner ─────────────────────────────────────
            t0 = time.monotonic() * 1000.0
            plan: WESPlan = self._planner.plan(bundle)
            latency_planner = time.monotonic() * 1000.0 - t0

            planner_fixture_code = getattr(
                self._planner, "fixture_code", "wes_execution_planner"
            )
            planner_result = fixture_tier_result(
                tier="planner",
                fixture_code=planner_fixture_code,
                parsed=plan,
                latency_ms=latency_planner,
            )
            tap.record(planner_result)

            # ── Write bundle + planner logs ───────────────────────────
            try:
                observability.write_bundle(plan.plan_id, bundle.to_dict())
                observability.write_planner(plan.plan_id, planner_result)
            except Exception:
                pass  # logging never breaks execution

            if plan.abandoned:
                log_degrade(
                    subsystem="wes",
                    operation="run_plan.planner_abandoned",
                    failure_reason=plan.abandonment_reason or "(no reason)",
                    fallback_taken="plan not dispatched",
                    severity="info",
                    context={"plan_id": plan.plan_id},
                )
                return {
                    "status": "abandoned",
                    "plan_id": plan.plan_id,
                    "bundle_id": bundle.bundle_id,
                    "reason": plan.abandonment_reason,
                    "tier_results": [r.to_dict() for r in tap.results],
                }

            # ── Plan-time dependency check (bounce-back) ─────────────
            # If the plan has unresolved cross-refs and the planner
            # didn't explicitly acknowledge, bounce back with an XML
            # warning via the existing rerun mechanism. Runtime cascade
            # (post-dispatch) handles refs the planner couldn't foresee.
            from world_system.wes.plan_resolution import (
                evaluate_plan_for_bounce,
            )
            bounce = evaluate_plan_for_bounce(plan, self._registry)
            if bounce.bounce and reruns_remaining > 0:
                log_degrade(
                    subsystem="wes",
                    operation="run_plan.bounce_back",
                    failure_reason=(
                        f"unresolved refs: "
                        f"{len(bounce.analysis.unresolved_refs) if bounce.analysis else 0}"
                    ),
                    fallback_taken="bouncing plan back to planner with warning",
                    severity="info",
                    context={"plan_id": plan.plan_id,
                             "reruns_remaining": reruns_remaining},
                )
                return self.run_plan(
                    bundle,
                    reruns_remaining=reruns_remaining - 1,
                    adjusted_instructions=bounce.warning,
                )

            # ── Dispatch ──────────────────────────────────────────────
            dispatcher = PlanDispatcher(
                hubs=self._hubs,
                tools=self._tools,
                registry=self._registry,
                supervisor_tap=tap,
                async_runner=self._runner,
                tool_log_writer=observability.write_tool,
                hub_log_writer=observability.write_hub,
            )
            dispatch_result: DispatchResult = dispatcher.run(plan, bundle)

            # ── Runtime cascade ──────────────────────────────────────
            # After the primary plan dispatches, scan staged content for
            # cross-refs to NEW ids that nothing produced (LLM tools may
            # name things in drops/spawns/teaches that the planner didn't
            # foresee). For each such gap, generate a synthetic extension
            # plan and dispatch it. Capped at MAX_RUNTIME_CASCADE_DEPTH
            # to prevent runaway.
            self._run_runtime_cascade(
                primary_plan=plan,
                bundle=bundle,
                dispatcher=dispatcher,
                dispatch_result=dispatch_result,
                tap=tap,
            )

            # ── Supervisor review ────────────────────────────────────
            supervisor_verdict = self._run_supervisor(
                plan, tap.results, bundle
            )
            sup_tier = supervisor_result_to_tier_record(
                supervisor_verdict,
                latency_ms=0.0,
                backend_used=getattr(self._supervisor, "name", "stub"),
            )
            tap.record(sup_tier)
            try:
                observability.write_supervisor(plan.plan_id, sup_tier)
            except Exception:
                pass

            if supervisor_verdict.get("rerun") and reruns_remaining > 0:
                # Rollback + rerun
                self._safe_rollback(plan.plan_id)
                return self.run_plan(
                    bundle,
                    reruns_remaining=reruns_remaining - 1,
                    adjusted_instructions=supervisor_verdict.get(
                        "adjusted_instructions"
                    ),
                )

            # ── Final verification ────────────────────────────────────
            verification = run_final_verification(plan, self._registry)
            try:
                observability.write_verification(plan.plan_id, verification)
            except Exception:
                pass

            if verification.get("passed"):
                return self._commit_or_report(
                    plan, bundle, verification,
                    dispatch_result, supervisor_verdict, tap,
                )

            # Verification failed → rollback + surface.
            self._safe_rollback(plan.plan_id)
            surface_visible_wes_failure(
                operation="run_plan.verification_failed",
                failure_reason=(
                    f"verification issues: "
                    f"{verification.get('issues')}"
                ),
                fallback_taken="plan rolled back; no content committed",
                context={
                    "plan_id": plan.plan_id,
                    "bundle_id": bundle.bundle_id,
                },
            )
            return {
                "status": "rolled_back",
                "plan_id": plan.plan_id,
                "bundle_id": bundle.bundle_id,
                "verification": verification,
                "supervisor": supervisor_verdict,
                "tier_results": [r.to_dict() for r in tap.results],
                "dispatch": dispatch_result.to_dict(),
                "adjusted_instructions": adjusted_instructions,
            }

        except UnknownToolError as e:
            surface_visible_wes_failure(
                operation="run_plan.unknown_tool",
                failure_reason=str(e),
                fallback_taken="plan aborted before any staging",
                context={"bundle_id": getattr(bundle, "bundle_id", None)},
            )
            return {
                "status": "error",
                "error": f"UnknownToolError: {e}",
                "bundle_id": getattr(bundle, "bundle_id", None),
            }
        except Exception as e:
            surface_visible_wes_failure(
                operation="run_plan",
                failure_reason=f"{type(e).__name__}: {e}",
                fallback_taken=(
                    "plan aborted; check tier logs for root cause"
                ),
                context={"bundle_id": getattr(bundle, "bundle_id", None)},
            )
            return {
                "status": "error",
                "error": f"{type(e).__name__}: {e}",
                "bundle_id": getattr(bundle, "bundle_id", None),
            }

    # ── helpers ───────────────────────────────────────────────────────

    def _run_supervisor(
        self,
        plan: WESPlan,
        tier_results: List[TierRunResult],
        bundle: Any,
    ) -> Dict[str, Any]:
        """Invoke the supervisor, returning the canonical verdict dict.

        If the supervisor raises, log a degrade and default to pass so
        the pipeline isn't held hostage by a broken observer.
        """
        try:
            verdict = self._supervisor.review(plan, tier_results, bundle)
            if not isinstance(verdict, dict):
                raise TypeError(
                    f"Supervisor.review returned "
                    f"{type(verdict).__name__}, expected dict"
                )
            # Ensure canonical keys exist
            verdict.setdefault("verdict", "pass")
            verdict.setdefault("rerun", False)
            verdict.setdefault("notes", "")
            verdict.setdefault("adjusted_instructions", None)
            return verdict
        except Exception as e:
            log_degrade(
                subsystem="wes",
                operation="run_supervisor",
                failure_reason=f"{type(e).__name__}: {e}",
                fallback_taken="default to pass verdict",
                severity="warning",
                context={"plan_id": plan.plan_id},
            )
            return {
                "verdict": "pass",
                "rerun": False,
                "notes": (
                    f"supervisor errored: {type(e).__name__}; defaulting "
                    f"to pass"
                ),
                "adjusted_instructions": None,
            }

    def _run_runtime_cascade(
        self,
        primary_plan: WESPlan,
        bundle: Any,
        dispatcher: "PlanDispatcher",
        dispatch_result: "DispatchResult",
        tap: "SupervisorTap",
    ) -> None:
        """Repeatedly walk staged content for unresolved cross-refs and
        dispatch synthetic extension plans until either no orphans
        remain or :data:`MAX_RUNTIME_CASCADE_DEPTH` is reached.

        Per user direction: WES has authority to create whatever content
        it needs. When a chunk's enemySpawns names a new hostile, the
        hostile is auto-generated; when that hostile drops a new
        material, the material is auto-generated; etc.

        Cap controls runaway. Each pass is bounded by
        :data:`MAX_CASCADE_STEPS_PER_PASS` synthetic steps so a single
        malformed tool output can't queue dozens of follow-ups.
        """
        from world_system.wes.plan_resolution import (
            MAX_CASCADE_STEPS_PER_PASS,
            MAX_RUNTIME_CASCADE_DEPTH,
            build_extension_plan,
            find_runtime_orphans,
        )

        if self._registry is None:
            return

        for depth in range(1, MAX_RUNTIME_CASCADE_DEPTH + 1):
            try:
                recs = find_runtime_orphans(self._registry, primary_plan.plan_id)
            except Exception as e:
                log_degrade(
                    subsystem="wes",
                    operation=f"runtime_cascade.find_orphans (depth {depth})",
                    failure_reason=f"{type(e).__name__}: {e}",
                    fallback_taken="cascade halted; orphans may remain",
                    severity="warning",
                    context={"plan_id": primary_plan.plan_id, "depth": depth},
                )
                return

            if not recs:
                return

            ext_plan = build_extension_plan(
                primary_plan, recs,
                cascade_depth=depth,
                max_steps=MAX_CASCADE_STEPS_PER_PASS,
            )
            if ext_plan is None:
                return

            log_degrade(
                subsystem="wes",
                operation=f"runtime_cascade.dispatch (depth {depth})",
                failure_reason=(
                    f"runtime cascade dispatching {len(ext_plan.steps)} "
                    f"synthetic step(s) for unresolved refs"
                ),
                fallback_taken="orphans being auto-generated",
                severity="info",
                context={"plan_id": primary_plan.plan_id,
                         "ext_plan_id": ext_plan.plan_id,
                         "depth": depth,
                         "step_count": len(ext_plan.steps)},
            )

            try:
                ext_result = dispatcher.run(ext_plan, bundle)
            except Exception as e:
                log_degrade(
                    subsystem="wes",
                    operation=f"runtime_cascade.dispatch_failed (depth {depth})",
                    failure_reason=f"{type(e).__name__}: {e}",
                    fallback_taken="cascade halted; remaining orphans not generated",
                    severity="warning",
                    context={"plan_id": primary_plan.plan_id, "depth": depth},
                )
                return

            # Merge extension dispatch results into the parent's result.
            for tier_result in ext_result.tier_results:
                dispatch_result.tier_results.append(tier_result)
            for tool_name, ids in ext_result.staged_content_ids.items():
                dispatch_result.staged_content_ids.setdefault(
                    tool_name, []
                ).extend(ids)
            for sid, errs in ext_result.step_errors.items():
                dispatch_result.step_errors.setdefault(sid, []).extend(errs)

    def _commit_or_report(
        self,
        plan: WESPlan,
        bundle: Any,
        verification: Dict[str, Any],
        dispatch_result: DispatchResult,
        supervisor_verdict: Dict[str, Any],
        tap: SupervisorTap,
    ) -> Dict[str, Any]:
        """Attempt to commit the plan; report outcome to caller."""
        if self._registry is None:
            return {
                "status": "rolled_back",
                "plan_id": plan.plan_id,
                "bundle_id": bundle.bundle_id,
                "verification": verification,
                "supervisor": supervisor_verdict,
                "tier_results": [r.to_dict() for r in tap.results],
                "dispatch": dispatch_result.to_dict(),
                "note": "no registry; could not commit",
            }

        try:
            self._registry.commit(plan.plan_id)
        except Exception as e:
            surface_visible_wes_failure(
                operation="run_plan.commit",
                failure_reason=f"{type(e).__name__}: {e}",
                fallback_taken="attempted rollback",
                context={"plan_id": plan.plan_id},
            )
            self._safe_rollback(plan.plan_id)
            return {
                "status": "rolled_back",
                "plan_id": plan.plan_id,
                "bundle_id": bundle.bundle_id,
                "verification": verification,
                "supervisor": supervisor_verdict,
                "tier_results": [r.to_dict() for r in tap.results],
                "dispatch": dispatch_result.to_dict(),
                "error": f"commit failed: {type(e).__name__}: {e}",
            }

        return {
            "status": "committed",
            "plan_id": plan.plan_id,
            "bundle_id": bundle.bundle_id,
            "verification": verification,
            "supervisor": supervisor_verdict,
            "tier_results": [r.to_dict() for r in tap.results],
            "dispatch": dispatch_result.to_dict(),
        }

    def _safe_rollback(self, plan_id: str) -> None:
        """Call :meth:`ContentRegistry.rollback`, swallowing exceptions."""
        if self._registry is None:
            return
        try:
            self._registry.rollback(plan_id)
        except Exception as e:
            log_degrade(
                subsystem="wes",
                operation="safe_rollback",
                failure_reason=f"{type(e).__name__}: {e}",
                fallback_taken="registry may contain staged rows",
                severity="error",
                context={"plan_id": plan_id},
            )


def get_wes_orchestrator() -> WESOrchestrator:
    """Module-level accessor following the project singleton pattern."""
    return WESOrchestrator.get_instance()


__all__ = [
    "WESOrchestrator",
    "get_wes_orchestrator",
    "WNS_CALL_WES_REQUESTED",
]

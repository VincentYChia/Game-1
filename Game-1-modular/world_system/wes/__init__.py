"""World Executor System (WES) — deterministic shell.

Implements §5 of ``Development-Plan/WORLD_SYSTEM_WORKING_DOC.md`` (v4):
the three-tier LLM orchestration stack (execution_planner, execution_hub,
executor_tool) plus the cross-tier supervisor.

**v4 invariants this package enforces:**

- **Pure execution engine.** WES consumes the ``WESContextBundle`` that WNS
  authored; it never queries canonical stores live.
- **Deterministic glue between every tier.** Code owns parsing, schema
  validation, cross-reference checking, staging, and rollback. LLMs do
  nothing beyond their narrow transform.
- **Hubs are dispatchers, not orchestrators** (CC9). They emit an XML-tagged
  batch of specs in one pass; executor_tools fan out in parallel.
- **Supervisor is rerun-only** (CC1). It observes logs, may trigger a single
  rerun with adjusted instructions, and otherwise does nothing.
- **No backward flow to WNS.** If the bundle is under-specified, WES
  abandons. No clarification loop.

**P5 scope:** this package is the *deterministic shell* — dataclasses,
protocols, XML parser, plan dispatcher, async runner, verification, and
observability. The LLM tier implementations are stubs that consult the
P0 LLMFixture Registry. Agent D wires real LLM-backed tiers in P6+.

**Public surface** — the types and callables Agent D implements against:

- :class:`WESPlanStep` / :class:`WESPlan` / :class:`ExecutorSpec` /
  :class:`TierRunResult` (``dataclasses``).
- :class:`ExecutionPlanner` / :class:`ExecutionHub` / :class:`ExecutorTool`
  / :class:`Supervisor` (``protocols``).
- :class:`WESOrchestrator` (``wes_orchestrator``) — entry point.

**Observability:** every plan run writes ``llm_debug_logs/wes/<plan_id>/``
per §8.11 file layout.
"""

from world_system.wes.dataclasses import (
    ExecutorSpec,
    TierRunResult,
    WESPlan,
    WESPlanStep,
)
from world_system.wes.protocols import (
    ExecutionHub,
    ExecutionPlanner,
    ExecutorTool,
    Supervisor,
)

__all__ = [
    "ExecutorSpec",
    "TierRunResult",
    "WESPlan",
    "WESPlanStep",
    "ExecutionHub",
    "ExecutionPlanner",
    "ExecutorTool",
    "Supervisor",
]

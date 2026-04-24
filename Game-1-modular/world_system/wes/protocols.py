"""WES tier protocols (v4 §5).

The abstract interfaces Agent D's real-LLM-backed tiers implement against.
The deterministic shell (:mod:`plan_dispatcher`, :mod:`wes_orchestrator`)
consumes these protocols exclusively; swapping stub tiers for real ones is
a constructor parameter change, not a rewrite.

**Why Protocol rather than ABC:**
- Structural typing lets fixture-driven stubs, real-LLM-backed tiers, and
  test doubles all satisfy the contract without common inheritance.
- Matches the project's existing dispatch-by-duck-type patterns in the
  crafting / combat managers.

**Implementation contract** (binding on Agent D):

- ``plan``, ``build_specs``, ``generate`` and ``review`` MUST be thread-safe
  — the dispatcher fans out executor_tool calls in parallel (§5.7).
- Implementations MUST NOT perform live queries against WMS/WNS/Registry
  (v4 reversal — see §5.1 "No live queries anywhere in WES").
- Implementations MUST log full prompt + response to
  ``llm_debug_logs/wes/<plan_id>/`` per §8.11. The orchestrator will
  handle writing a normalized :class:`TierRunResult`, but implementations
  are responsible for producing one.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict, List, Optional, Protocol, runtime_checkable

if TYPE_CHECKING:
    # Avoid runtime import cycles — dataclasses imports nothing from here.
    from world_system.living_world.infra.context_bundle import (
        BundleToolSlice,
        WESContextBundle,
    )
    from world_system.wes.dataclasses import (
        ExecutorSpec,
        TierRunResult,
        WESPlan,
        WESPlanStep,
    )


@runtime_checkable
class ExecutionPlanner(Protocol):
    """Tier 1 (§5.2). Decomposes a bundle into a :class:`WESPlan`.

    Implementations MUST:
    - Read only the bundle (plus static game/task awareness blocks).
    - Emit a valid :class:`WESPlan`. Abandonment is represented by setting
      ``abandoned=True`` with a non-empty ``abandonment_reason``.
    - Honor the firing-tier scope rules from §5.8 via prompt discipline.
    """

    def plan(self, bundle: "WESContextBundle") -> "WESPlan":
        """Produce a plan (possibly abandoned) from ``bundle``."""
        ...


@runtime_checkable
class ExecutionHub(Protocol):
    """Tier 2 (§5.3). Non-adaptive dispatcher per tool type.

    Implementations MUST:
    - Carry a ``name`` attribute matching the tool name
      (``hostiles | materials | nodes | skills | titles``). Registries
      key hubs by this name.
    - Emit ALL specs for the plan step in one pass. No sequential feedback
      loop (CC9).
    - Never perform live queries.
    """

    name: str

    def build_specs(
        self,
        step: "WESPlanStep",
        slice: "BundleToolSlice",
    ) -> List["ExecutorSpec"]:
        """Unpack one plan step into a batch of per-item specs."""
        ...


@runtime_checkable
class ExecutorTool(Protocol):
    """Tier 3 (§5.4). One spec → one schema-valid JSON artifact.

    Implementations MUST:
    - Carry a ``name`` matching the tool type.
    - Be pure with respect to LLM-external state: the only inputs are the
      spec and the (thread-safe) backend. No cross-talk between parallel
      executor_tool calls.
    - Return a dict matching the tool's committed schema (see
      ``PLACEHOLDER_LEDGER §1`` for the fixture responses' target
      schemas).
    """

    name: str

    def generate(self, spec: "ExecutorSpec") -> Dict[str, Any]:
        """Produce one tool JSON for this spec."""
        ...


@runtime_checkable
class Supervisor(Protocol):
    """Cross-tier common-sense checker (CC1, §5.6).

    Implementations MUST:
    - Review plan + all tier results + the originating bundle.
    - Return a dict with keys::

          {
              "verdict": "pass" | "fail",
              "rerun": bool,
              "notes": str,
              "adjusted_instructions": Optional[str],
          }

    - Not mutate registry state or tier logs; supervisor's sole authority
      is the ``rerun`` flag and the ``adjusted_instructions`` that ride
      into the next planner invocation.
    - Be bounded in rerun budget by the orchestrator (1-2 reruns per
      plan, per §9.Q12).
    """

    def review(
        self,
        plan: "WESPlan",
        tier_results: List["TierRunResult"],
        bundle: "WESContextBundle",
    ) -> Dict[str, Any]:
        """Review a completed plan run, return verdict + rerun decision."""
        ...


# Re-export commonly-used typing symbols so call sites can import from here.
__all__ = [
    "ExecutionPlanner",
    "ExecutionHub",
    "ExecutorTool",
    "Supervisor",
    "Any",
    "Dict",
    "List",
    "Optional",
]

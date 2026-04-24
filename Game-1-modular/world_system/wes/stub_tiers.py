"""Stub tier implementations for P5 end-to-end testing.

Agent D will replace these with real LLM-backed tiers in P6+. Until
then, the stubs consult the P0 :class:`LLMFixtureRegistry` and return
the canonical fixture responses verbatim. That lets the full pipeline
(bundle → planner → hub → tool → staging → commit) run end-to-end
with zero real-LLM dependencies.

**Fixture codes used:**

- ``wes_execution_planner`` — ``StubExecutionPlanner``
- ``wes_hub_<tool>``         — ``StubExecutionHub``
- ``wes_tool_<tool>``         — ``StubExecutorTool``

The stubs validate that the fixture parses into the tier's expected
output shape — a mismatch surfaces as a clear error rather than
silently polluting the pipeline with malformed data.
"""

from __future__ import annotations

import json
import uuid
from typing import Any, Dict, List

from world_system.living_world.infra.llm_fixtures import get_fixture_registry
from world_system.wes.dataclasses import (
    ExecutorSpec,
    TierRunResult,
    WESPlan,
    WESPlanStep,
)
from world_system.wes.xml_batch_parser import parse_xml_batch


# Known tool names — the five mini-stacks shipping in P7/P8.
_VALID_TOOLS = frozenset(
    {"hostiles", "materials", "nodes", "skills", "titles"}
)


def _strip_json_fences(raw: str) -> str:
    """Remove ```json ... ``` fences if the fixture has them."""
    s = raw.strip()
    if s.startswith("```"):
        lines = s.splitlines()
        if lines[0].strip().startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        s = "\n".join(lines)
    return s.strip()


class StubExecutionPlanner:
    """Tier 1 stub. Consults the ``wes_execution_planner`` fixture.

    The fixture's canonical response is a JSON :class:`WESPlan`. The
    stub parses it, rewrites the plan_id/source_bundle_id so they
    reflect *this* run (not the fixture's canned values), and returns
    a real :class:`WESPlan`.
    """

    name: str = "stub_execution_planner"
    fixture_code: str = "wes_execution_planner"

    def plan(self, bundle) -> WESPlan:
        fixture = get_fixture_registry().require(self.fixture_code)
        raw = _strip_json_fences(fixture.canonical_response)
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError as e:
            raise RuntimeError(
                f"stub planner: fixture response is not valid JSON: {e}"
            ) from e

        # The fixture's plan_id/source_bundle_id are fixed strings; for
        # a real run we want identifiers derived from the bundle. That
        # way multiple runs with the same fixture produce distinct
        # plan directories in llm_debug_logs/.
        parsed["plan_id"] = f"plan_{uuid.uuid4().hex[:12]}"
        parsed["source_bundle_id"] = bundle.bundle_id

        plan = WESPlan.from_dict(parsed)

        # Filter steps so only valid tools survive — the fixture should
        # already honor this, but defensive here keeps test noise out
        # if the fixture drifts.
        plan.steps = [s for s in plan.steps if s.tool in _VALID_TOOLS]
        return plan


class StubExecutionHub:
    """Tier 2 stub. Consults ``wes_hub_<tool>`` fixture per tool type.

    Rewrites the parsed specs' ``plan_step_id`` to the *actual* step
    id being dispatched (the fixture's is a stand-in).
    """

    fixture_prefix: str = "wes_hub_"

    def __init__(self, tool_name: str) -> None:
        if tool_name not in _VALID_TOOLS:
            raise ValueError(
                f"StubExecutionHub: unknown tool {tool_name!r}. "
                f"Valid: {sorted(_VALID_TOOLS)}"
            )
        self.name = tool_name
        self.fixture_code = f"{self.fixture_prefix}{tool_name}"

    def build_specs(self, step: WESPlanStep, slice) -> List[ExecutorSpec]:
        fixture = get_fixture_registry().require(self.fixture_code)
        specs = parse_xml_batch(fixture.canonical_response)
        # Rewrite step id so specs match the actual plan this run.
        for s in specs:
            s.plan_step_id = step.step_id
        return specs


class StubExecutorTool:
    """Tier 3 stub. Consults ``wes_tool_<tool>`` fixture per tool type."""

    fixture_prefix: str = "wes_tool_"

    def __init__(self, tool_name: str) -> None:
        if tool_name not in _VALID_TOOLS:
            raise ValueError(
                f"StubExecutorTool: unknown tool {tool_name!r}. "
                f"Valid: {sorted(_VALID_TOOLS)}"
            )
        self.name = tool_name
        self.fixture_code = f"{self.fixture_prefix}{tool_name}"

    def generate(self, spec: ExecutorSpec) -> Dict[str, Any]:
        fixture = get_fixture_registry().require(self.fixture_code)
        raw = _strip_json_fences(fixture.canonical_response)
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError as e:
            raise RuntimeError(
                f"stub tool {self.name!r}: fixture response is not "
                f"valid JSON: {e}"
            ) from e
        if not isinstance(parsed, dict):
            raise RuntimeError(
                f"stub tool {self.name!r}: fixture parsed to "
                f"{type(parsed).__name__}, expected dict"
            )
        return parsed


# ── registry helpers ──────────────────────────────────────────────────

def build_default_stub_hubs() -> Dict[str, StubExecutionHub]:
    """Return one hub per tool name. The orchestrator uses this as
    the P5 default hub registry."""
    return {tool: StubExecutionHub(tool) for tool in _VALID_TOOLS}


def build_default_stub_tools() -> Dict[str, StubExecutorTool]:
    """Return one executor_tool per tool name. P5 default registry."""
    return {tool: StubExecutorTool(tool) for tool in _VALID_TOOLS}


# ── Tier-run wrapping helpers ─────────────────────────────────────────

def fixture_tier_result(
    tier: str,
    fixture_code: str,
    parsed: Any,
    latency_ms: float = 0.0,
) -> TierRunResult:
    """Build a :class:`TierRunResult` from a fixture + parsed output.

    Captures the fixture's canonical prompt as the ``prompt`` field so
    logs show what the stub "saw". Helpful for the supervisor and for
    downstream debugging when stubs are in the pipeline.
    """
    fx = get_fixture_registry().get(fixture_code)
    prompt = ""
    raw_response = ""
    if fx is not None:
        prompt = (
            (fx.canonical_system_prompt or "")
            + ("\n\n" if fx.canonical_system_prompt else "")
            + (fx.canonical_user_prompt or "")
        )
        raw_response = fx.canonical_response
    return TierRunResult(
        tier=tier,
        prompt=prompt,
        raw_response=raw_response,
        parsed=parsed,
        latency_ms=float(latency_ms),
        backend_used="fixture",
        errors=[],
    )


__all__ = [
    "StubExecutionPlanner",
    "StubExecutionHub",
    "StubExecutorTool",
    "build_default_stub_hubs",
    "build_default_stub_tools",
    "fixture_tier_result",
]

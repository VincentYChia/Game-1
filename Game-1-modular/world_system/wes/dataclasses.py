"""WES data model (v4 §5, Placeholder Ledger §11).

These are the typed artifacts that flow between WES tiers and between WES
and the rest of the Living World. Every dataclass round-trips through
``to_dict`` / ``from_dict`` for:

- Observability logs (``llm_debug_logs/wes/<plan_id>/...``).
- Serialization across async boundaries.
- Eventual replay-based testing.

Field shapes follow §5.2 / §5.3. The ``Dict[str, Any]`` fields
(``slots``, ``flavor_hints`` etc.) are placeholders — per the ledger,
designer may later commit to typed per-tool variants; this P5 scaffold
keeps them permissive.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List


# ── Tier 1 output: WESPlan ────────────────────────────────────────────

@dataclass
class WESPlanStep:
    """One node in the plan graph.

    Attributes:
        step_id: Unique identifier within the plan (e.g. ``"s1"``).
        tool: The tool mini-stack to invoke.
            One of ``hostiles | materials | nodes | skills | titles``.
        intent: Human-readable one-line goal for the step.
        depends_on: Upstream step_ids; enforced by the topological
            dispatcher. May reference sibling steps in the same plan.
        slots: Free-form parameters the hub consumes
            (e.g. ``{"tier": 2, "biome": "moors"}``). Placeholder shape —
            see PLACEHOLDER_LEDGER §11.
    """

    step_id: str
    tool: str
    intent: str
    depends_on: List[str] = field(default_factory=list)
    slots: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "step_id": self.step_id,
            "tool": self.tool,
            "intent": self.intent,
            "depends_on": list(self.depends_on),
            "slots": dict(self.slots),
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "WESPlanStep":
        return cls(
            step_id=d["step_id"],
            tool=d["tool"],
            intent=d["intent"],
            depends_on=list(d.get("depends_on", [])),
            slots=dict(d.get("slots", {})),
        )


@dataclass
class WESPlan:
    """Output of Tier 1 ``execution_planner``.

    Either an ordered, DAG-structured set of steps OR an explicit
    abandonment (with a reason).
    """

    plan_id: str
    source_bundle_id: str
    steps: List[WESPlanStep] = field(default_factory=list)
    rationale: str = ""
    abandoned: bool = False
    abandonment_reason: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "plan_id": self.plan_id,
            "source_bundle_id": self.source_bundle_id,
            "steps": [s.to_dict() for s in self.steps],
            "rationale": self.rationale,
            "abandoned": bool(self.abandoned),
            "abandonment_reason": self.abandonment_reason,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "WESPlan":
        return cls(
            plan_id=d["plan_id"],
            source_bundle_id=d["source_bundle_id"],
            steps=[WESPlanStep.from_dict(s) for s in d.get("steps", [])],
            rationale=d.get("rationale", ""),
            abandoned=bool(d.get("abandoned", False)),
            abandonment_reason=d.get("abandonment_reason", ""),
        )


# ── Tier 2 output: ExecutorSpec ───────────────────────────────────────

@dataclass
class ExecutorSpec:
    """One item of work for a Tier 3 ``executor_tool``.

    Emitted in batches by the hub (see :mod:`xml_batch_parser`). Field
    shapes are ``Dict[str, Any]`` placeholders — designer may commit to
    typed per-tool variants (PLACEHOLDER_LEDGER §11).

    Attributes:
        spec_id: Unique identifier within the hub batch.
        plan_step_id: Upstream plan step id this spec belongs to.
        item_intent: One-line goal for the executor_tool.
        flavor_hints: Name hints, prose fragments, narrative framing.
            Passed through from the plan step / bundle — hubs do not
            invent flavor (§5.3).
        cross_ref_hints: IDs this artifact should reference (e.g.
            ``{"material_id": "moors_copper"}``). Validated against
            ContentRegistry post-generation.
        hard_constraints: Tier range, biome, balance envelope. Enforced
            by the deterministic schema/balance check after generation.
    """

    spec_id: str
    plan_step_id: str
    item_intent: str = ""
    flavor_hints: Dict[str, Any] = field(default_factory=dict)
    cross_ref_hints: Dict[str, Any] = field(default_factory=dict)
    hard_constraints: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "spec_id": self.spec_id,
            "plan_step_id": self.plan_step_id,
            "item_intent": self.item_intent,
            "flavor_hints": dict(self.flavor_hints),
            "cross_ref_hints": dict(self.cross_ref_hints),
            "hard_constraints": dict(self.hard_constraints),
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "ExecutorSpec":
        return cls(
            spec_id=d["spec_id"],
            plan_step_id=d["plan_step_id"],
            item_intent=d.get("item_intent", ""),
            flavor_hints=dict(d.get("flavor_hints", {})),
            cross_ref_hints=dict(d.get("cross_ref_hints", {})),
            hard_constraints=dict(d.get("hard_constraints", {})),
        )


# ── Per-tier run metadata: TierRunResult ──────────────────────────────

@dataclass
class TierRunResult:
    """One tier's run output + metadata for the supervisor and logs.

    Attributes:
        tier: One of ``planner | hub | executor_tool | supervisor``.
        prompt: Assembled LLM prompt (system + user, concatenated or
            structured — stub tiers just store the fixture's canonical
            user prompt). Retained for observability.
        raw_response: Raw LLM response before parsing.
        parsed: The parsed artifact. Shape varies by tier:
            - ``planner`` -> :class:`WESPlan`
            - ``hub`` -> ``List[ExecutorSpec]``
            - ``executor_tool`` -> ``Dict[str, Any]`` (tool JSON)
            - ``supervisor`` -> ``Dict[str, Any]``
            Kept as ``Any`` to avoid circular typing; supervisors and
            dispatchers cast as needed.
        latency_ms: Wall-clock time for the tier's LLM call, in ms.
        backend_used: Backend name (e.g. ``mock``, ``ollama``,
            ``claude``, ``fixture``).
        errors: Any non-fatal errors encountered; fatal errors raise.
    """

    tier: str
    prompt: str = ""
    raw_response: str = ""
    parsed: Any = None
    latency_ms: float = 0.0
    backend_used: str = ""
    errors: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        # parsed may contain arbitrary types; try to_dict-ish serialization
        parsed_out: Any = self.parsed
        to_dict_method = getattr(self.parsed, "to_dict", None)
        if callable(to_dict_method):
            parsed_out = to_dict_method()
        elif isinstance(self.parsed, list):
            parsed_out = [
                (p.to_dict() if hasattr(p, "to_dict") else p)
                for p in self.parsed
            ]
        return {
            "tier": self.tier,
            "prompt": self.prompt,
            "raw_response": self.raw_response,
            "parsed": parsed_out,
            "latency_ms": float(self.latency_ms),
            "backend_used": self.backend_used,
            "errors": list(self.errors),
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "TierRunResult":
        return cls(
            tier=d["tier"],
            prompt=d.get("prompt", ""),
            raw_response=d.get("raw_response", ""),
            parsed=d.get("parsed"),
            latency_ms=float(d.get("latency_ms", 0.0)),
            backend_used=d.get("backend_used", ""),
            errors=list(d.get("errors", [])),
        )


__all__ = [
    "WESPlanStep",
    "WESPlan",
    "ExecutorSpec",
    "TierRunResult",
]

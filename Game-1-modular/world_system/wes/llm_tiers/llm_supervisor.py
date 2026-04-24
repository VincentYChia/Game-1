"""LLMSupervisor — cross-tier common-sense reviewer (§5.6, P6/P9).

Implements :class:`~world_system.wes.protocols.Supervisor`.

Flow:
    1. Summarize tier_results into a condensed log blob (one line each).
    2. Build prompts from ``prompt_fragments_wes_supervisor.json``.
    3. Include the bundle's directive + the staged content summaries.
    4. Call ``BackendManager.generate(task="wes_supervisor", ...)``.
    5. Parse response:
       ``{verdict, rerun, notes, adjusted_instructions}``.
    6. Return that dict.

**Important invariants:**
- Supervisor MUST NOT mutate plan/state. Its only lever is the returned
  ``rerun`` flag, which the orchestrator acts on.
- Rerun budget enforcement (max 1-2) is the orchestrator's concern, not
  the supervisor's.
"""

from __future__ import annotations

import json
import os
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from world_system.living_world.backends.backend_manager import BackendManager
from world_system.living_world.infra.graceful_degrade import log_degrade
from world_system.wes.llm_tiers.prompt_assembler import PromptAssembler

if TYPE_CHECKING:
    from world_system.living_world.infra.context_bundle import WESContextBundle
    from world_system.wes.dataclasses import TierRunResult, WESPlan


def _resolve_config_path(fragments_filename: str) -> str:
    this = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(this)))
    return os.path.join(
        project_root, "world_system", "config", fragments_filename
    )


def _strip_markdown_fence(text: str) -> str:
    s = text.strip()
    if s.startswith("```"):
        first_nl = s.find("\n")
        if first_nl >= 0:
            s = s[first_nl + 1 :]
        if s.endswith("```"):
            s = s[:-3]
    return s.strip()


def _parse_verdict(text: str) -> Optional[Dict[str, Any]]:
    if not text:
        return None
    try:
        data = json.loads(_strip_markdown_fence(text))
        if isinstance(data, dict):
            return data
    except Exception:
        s = _strip_markdown_fence(text)
        first = s.find("{")
        last = s.rfind("}")
        if first >= 0 and last > first:
            try:
                data = json.loads(s[first : last + 1])
                if isinstance(data, dict):
                    return data
            except Exception:
                return None
    return None


def _default_pass_verdict(reason: str = "") -> Dict[str, Any]:
    return {
        "verdict": "pass",
        "rerun": False,
        "notes": reason or "supervisor degraded to pass",
        "adjusted_instructions": None,
    }


def _summarize_tier_results(tier_results: List["TierRunResult"]) -> str:
    """Condense tier results into a short log blob for the supervisor."""
    lines: List[str] = []
    for r in tier_results:
        ok = "ok" if getattr(r, "ok", True) and not getattr(r, "errors", []) else "err"
        tier = getattr(r, "tier", "?")
        step = getattr(r, "step_id", None) or ""
        spec = getattr(r, "spec_id", None) or ""
        tool = getattr(r, "tool_name", None) or ""
        backend = getattr(r, "backend_used", "")
        raw = getattr(r, "raw_response", "") or ""
        excerpt = raw[:160].replace("\n", " ")
        ident = "/".join(x for x in [tier, tool, step, spec] if x)
        lines.append(f"- [{ok}] {ident} (backend={backend}) resp={excerpt!r}")
    if not lines:
        return "(no tier results)"
    return "\n".join(lines)


class LLMSupervisor:
    """Cross-tier reviewer. Rerun-only authority."""

    TASK_NAME = "wes_supervisor"

    def __init__(
        self,
        backend_manager: Optional[BackendManager] = None,
        fragments_path: Optional[str] = None,
    ):
        self._backend = backend_manager or BackendManager.get_instance()
        self._assembler = PromptAssembler(
            fragments_path or _resolve_config_path(
                "prompt_fragments_wes_supervisor.json"
            )
        )

    # ── Protocol method ──────────────────────────────────────────────

    def review(
        self,
        plan: "WESPlan",
        tier_results: List["TierRunResult"],
        bundle: "WESContextBundle",
    ) -> Dict[str, Any]:
        """Review a plan pass, return verdict + rerun decision."""
        variables = {
            "plan_id": plan.plan_id,
            "plan_rationale": plan.rationale,
            "plan_abandoned": plan.abandoned,
            "plan_steps": [s.to_dict() for s in plan.steps],
            "bundle_id": bundle.bundle_id,
            "bundle_directive": bundle.directive.directive_text,
            "bundle_firing_tier": bundle.directive.firing_tier,
            "tier_log_blob": _summarize_tier_results(tier_results),
            "staged_counts": {
                "steps": len(plan.steps),
                "tier_results": len(tier_results),
            },
        }

        prompts = self._assembler.build(
            variables,
            firing_tier=bundle.directive.firing_tier,
        )

        try:
            text, err = self._backend.generate(
                task=self.TASK_NAME,
                system_prompt=prompts["system"],
                user_prompt=prompts["user"],
            )
        except Exception as e:
            log_degrade(
                subsystem="wes",
                operation="supervisor.review",
                failure_reason=f"backend_exception: {e}",
                fallback_taken="default pass verdict",
                severity="warning",
                context={"plan_id": plan.plan_id},
            )
            return _default_pass_verdict("supervisor backend exception")

        if err or not text:
            log_degrade(
                subsystem="wes",
                operation="supervisor.review",
                failure_reason=f"backend_error: {err}" if err else "empty_response",
                fallback_taken="default pass verdict",
                severity="warning",
                context={"plan_id": plan.plan_id},
            )
            return _default_pass_verdict("supervisor empty response")

        parsed = _parse_verdict(text)
        if parsed is None:
            log_degrade(
                subsystem="wes",
                operation="supervisor.review",
                failure_reason="verdict_parse_failure",
                fallback_taken="default pass verdict",
                severity="warning",
                context={"plan_id": plan.plan_id, "response_excerpt": text[:200]},
            )
            return _default_pass_verdict("supervisor parse failure")

        # Normalize shape — keep every contract key present.
        return {
            "verdict": str(parsed.get("verdict", "pass")),
            "rerun": bool(parsed.get("rerun", False)),
            "notes": str(parsed.get("notes", "")),
            "adjusted_instructions": parsed.get("adjusted_instructions"),
        }


__all__ = ["LLMSupervisor"]

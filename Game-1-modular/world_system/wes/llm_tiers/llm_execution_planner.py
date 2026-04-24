"""LLMExecutionPlanner — Tier 1 LLM-backed planner (§5.2, P6).

Implements the :class:`~world_system.wes.protocols.ExecutionPlanner` Protocol.

Flow:
    1. Build system + user prompt from ``prompt_fragments_wes_execution_planner.json``
       via :class:`PromptAssembler`. Inject game + task awareness blocks.
    2. Inject firing-tier-keyed scope rules (§5.8).
    3. Call ``BackendManager.generate(task="wes_execution_planner", ...)``.
    4. Parse response as JSON → :class:`WESPlan`.
    5. On parse failure, retry ONCE with a stricter prompt that includes
       the canonical example from the fragments file.
    6. On second failure, log_degrade and return an abandoned plan.

No live queries. No retries beyond one. No state mutation.
"""

from __future__ import annotations

import json
import os
import time
import uuid
from typing import TYPE_CHECKING, Any, Dict, Optional

from world_system.living_world.backends.backend_manager import BackendManager
from world_system.living_world.infra.graceful_degrade import log_degrade
from world_system.wes.dataclasses import WESPlan
from world_system.wes.llm_tiers.prompt_assembler import PromptAssembler

if TYPE_CHECKING:
    from world_system.living_world.infra.context_bundle import WESContextBundle


# Default fragments path — relative to project root's world_system/config/
_DEFAULT_FRAGMENTS = os.path.join(
    "world_system", "config", "prompt_fragments_wes_execution_planner.json"
)


def _resolve_config_path(fragments_filename: str) -> str:
    """Return absolute path to a config file under world_system/config/."""
    # This module lives at .../Game-1-modular/world_system/wes/llm_tiers/<file>
    this = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(this)))
    return os.path.join(
        project_root, "world_system", "config", fragments_filename
    )


def _strip_markdown_fence(text: str) -> str:
    """Remove ```json ... ``` fences if present. Mirrors npc_agent pattern."""
    s = text.strip()
    if s.startswith("```"):
        first_nl = s.find("\n")
        if first_nl >= 0:
            s = s[first_nl + 1 :]
        if s.endswith("```"):
            s = s[:-3]
    return s.strip()


def _parse_json_blob(text: str) -> Optional[Dict[str, Any]]:
    """Attempt JSON parse with markdown-fence tolerance.

    Returns the dict on success, None on failure.
    """
    if not text:
        return None
    try:
        return json.loads(_strip_markdown_fence(text))
    except Exception:
        # Try to find the first balanced {...} block
        s = _strip_markdown_fence(text)
        first = s.find("{")
        last = s.rfind("}")
        if first >= 0 and last > first:
            try:
                return json.loads(s[first : last + 1])
            except Exception:
                return None
        return None


class LLMExecutionPlanner:
    """Tier 1 planner. See :mod:`world_system.wes.protocols`."""

    TASK_NAME = "wes_execution_planner"

    def __init__(
        self,
        backend_manager: Optional[BackendManager] = None,
        fragments_path: Optional[str] = None,
    ):
        self._backend = backend_manager or BackendManager.get_instance()
        self._assembler = PromptAssembler(
            fragments_path or _resolve_config_path(
                "prompt_fragments_wes_execution_planner.json"
            )
        )

    # ── Protocol method ──────────────────────────────────────────────

    def plan(self, bundle: "WESContextBundle") -> WESPlan:
        """Decompose ``bundle`` into an ordered :class:`WESPlan`.

        Abandonment is represented by ``abandoned=True`` with a non-empty
        ``abandonment_reason``.
        """
        variables = self._bundle_to_vars(bundle)
        prompts = self._assembler.build(
            variables,
            firing_tier=bundle.directive.firing_tier,
        )

        # First attempt
        plan, err = self._attempt(prompts["system"], prompts["user"])
        if plan is not None:
            # Authoritative: source_bundle_id is set from the input bundle,
            # not from whatever the LLM echoed back. The bundle is ground
            # truth; the LLM's field is advisory.
            plan.source_bundle_id = bundle.bundle_id
            return plan

        # Retry once with stricter prompt (embed canonical example)
        stricter = self._stricter_suffix(prompts["output_example"])
        retry_prompts = self._assembler.build(
            variables,
            firing_tier=bundle.directive.firing_tier,
            extra_system_suffix=stricter,
        )
        plan, err2 = self._attempt(
            retry_prompts["system"], retry_prompts["user"]
        )
        if plan is not None:
            plan.source_bundle_id = bundle.bundle_id
            return plan

        # Second failure — abandon
        log_degrade(
            subsystem="wes",
            operation="execution_planner.plan",
            failure_reason=f"JSON parse failed twice: {err} / {err2}",
            fallback_taken="return abandoned plan",
            severity="warning",
            context={
                "bundle_id": bundle.bundle_id,
                "firing_tier": bundle.directive.firing_tier,
            },
        )
        return WESPlan(
            plan_id=f"plan_{uuid.uuid4().hex[:8]}",
            source_bundle_id=bundle.bundle_id,
            steps=[],
            rationale="",
            abandoned=True,
            abandonment_reason=f"planner parse failure: {err2 or err}",
        )

    # ── internals ────────────────────────────────────────────────────

    def _bundle_to_vars(self, bundle: "WESContextBundle") -> Dict[str, Any]:
        """Extract the shallow variables the planner prompt template needs.

        Keeps the rendered user prompt compact — hub/tool context lives in
        bundle_slice, not here (§5.2).
        """
        return {
            "bundle_id": bundle.bundle_id,
            "firing_tier": bundle.directive.firing_tier,
            "bundle_directive": bundle.directive.directive_text,
            "bundle_narrative_context": (
                bundle.narrative_context.firing_layer_summary
            ),
            "bundle_delta": (
                f"npc_dialogue={len(bundle.delta.npc_dialogue_since_last)}, "
                f"wms_events={len(bundle.delta.wms_events_since_last)}"
            ),
            "registry_counts": "n/a",  # filled in by WNS in later phases
            "firing_address": bundle.delta.address,
        }

    def _attempt(
        self, system_prompt: str, user_prompt: str
    ) -> "tuple[Optional[WESPlan], Optional[str]]":
        try:
            text, err = self._backend.generate(
                task=self.TASK_NAME,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
            )
        except Exception as e:
            return None, f"backend exception: {e}"
        if err:
            return None, err
        parsed = _parse_json_blob(text)
        if parsed is None:
            return None, "parse_failure"
        try:
            # Fixture example uses ``source_bundle_id`` already; allow either.
            if "source_bundle_id" not in parsed and "source_summary_id" in parsed:
                parsed["source_bundle_id"] = parsed.pop("source_summary_id")
            plan = WESPlan.from_dict(parsed)
            # Synthesize plan_id if missing
            if not plan.plan_id:
                plan.plan_id = f"plan_{uuid.uuid4().hex[:8]}"
            return plan, None
        except Exception as e:
            return None, f"dataclass_mapping_error: {e}"

    def _stricter_suffix(self, example: str) -> str:
        """Build a stricter-retry system suffix that embeds the canonical
        example from the fragments file."""
        if not example:
            return (
                "Strict retry. Emit ONLY a single JSON object matching "
                "the schema: {plan_id, source_bundle_id, steps:[{step_id, "
                "tool, intent, depends_on, slots}], rationale, abandoned}."
            )
        return (
            "Strict retry. Emit ONLY a single JSON object. Do not include "
            "prose or markdown. The exact schema matches this example:\n"
            f"{example}"
        )


__all__ = ["LLMExecutionPlanner"]

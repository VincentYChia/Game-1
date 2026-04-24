"""LLMExecutionHub — Tier 2 LLM-backed hub (§5.3, P7/P8).

One instance per tool type (hostiles, materials, nodes, skills, titles).
Implements :class:`~world_system.wes.protocols.ExecutionHub`. Non-adaptive
per CC9: emits the entire XML batch of specs in a single LLM call.

Flow:
    1. Build prompts from ``prompt_fragments_hub_<tool>.json``.
    2. Include the slice's directive + address_hint + focal threads +
       recent registry entries.
    3. Call ``BackendManager.generate(task=f"wes_hub_{tool}", ...)``.
    4. Parse response as XML batch via the canonical
       :mod:`world_system.wes.xml_batch_parser` — falling back to the
       local fallback parser if Agent C's module isn't present yet.
    5. On parse failure, ``log_degrade`` and return an empty list. The
       dispatcher then decides plan fate.
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from world_system.living_world.backends.backend_manager import BackendManager
from world_system.living_world.infra.graceful_degrade import log_degrade
from world_system.wes.dataclasses import ExecutorSpec
from world_system.wes.llm_tiers.prompt_assembler import PromptAssembler

if TYPE_CHECKING:
    from world_system.living_world.infra.context_bundle import BundleToolSlice
    from world_system.wes.dataclasses import WESPlanStep


def _parse_specs(text: str, plan_step_id: str) -> List[ExecutorSpec]:
    """Adapter: use Agent C's canonical parser if available, fall back local.

    Both parsers return ``List[ExecutorSpec]``. Agent C's raises
    ``XMLBatchParseError``; the fallback returns ``[]``. We normalize
    exceptions to empty list here so callers get a uniform contract.
    """
    try:
        from world_system.wes.xml_batch_parser import parse_xml_batch  # type: ignore
        try:
            specs = parse_xml_batch(text)
        except Exception:
            return []
        # Rewrite plan_step_id so dispatcher owns the authoritative value;
        # mismatches between LLM output and dispatcher intent can't cross-wire.
        return [
            ExecutorSpec(
                spec_id=s.spec_id,
                plan_step_id=plan_step_id,
                item_intent=s.item_intent,
                flavor_hints=dict(s.flavor_hints),
                cross_ref_hints=dict(s.cross_ref_hints),
                hard_constraints=dict(s.hard_constraints),
            )
            for s in specs
        ]
    except ImportError:  # pragma: no cover
        from world_system.wes.llm_tiers._xml_parse_fallback import parse_specs_xml
        return parse_specs_xml(text, plan_step_id)


def _resolve_config_path(fragments_filename: str) -> str:
    this = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(this)))
    return os.path.join(
        project_root, "world_system", "config", fragments_filename
    )


_KNOWN_TOOLS = {"hostiles", "materials", "nodes", "skills", "titles"}


class LLMExecutionHub:
    """Tier 2 hub. Constructed once per tool type.

    ``name`` attribute satisfies the Protocol and keys the registry.
    """

    TASK_PREFIX = "wes_hub_"

    def __init__(
        self,
        tool_name: str,
        backend_manager: Optional[BackendManager] = None,
        fragments_path: Optional[str] = None,
    ):
        if tool_name not in _KNOWN_TOOLS:
            # Not a hard error — designer may add a new tool — but warn
            # via log_degrade so it's visible.
            log_degrade(
                subsystem="wes",
                operation="execution_hub.__init__",
                failure_reason=f"Unknown tool_name: {tool_name!r}",
                fallback_taken="accept and continue",
                severity="info",
                context={"tool_name": tool_name},
            )
        self.name: str = tool_name
        self._backend = backend_manager or BackendManager.get_instance()
        self._assembler = PromptAssembler(
            fragments_path or _resolve_config_path(
                f"prompt_fragments_hub_{tool_name}.json"
            )
        )

    @property
    def task_name(self) -> str:
        return f"{self.TASK_PREFIX}{self.name}"

    # ── Protocol method ──────────────────────────────────────────────

    def build_specs(
        self,
        step: "WESPlanStep",
        slice: "BundleToolSlice",
    ) -> List[ExecutorSpec]:
        """One LLM call; parse XML batch into ExecutorSpec list."""
        variables = self._make_vars(step, slice)
        prompts = self._assembler.build(
            variables,
            firing_tier=slice.firing_tier,
        )

        try:
            text, err = self._backend.generate(
                task=self.task_name,
                system_prompt=prompts["system"],
                user_prompt=prompts["user"],
            )
        except Exception as e:
            log_degrade(
                subsystem="wes",
                operation=f"execution_hub.{self.name}.build_specs",
                failure_reason=f"backend_exception: {e}",
                fallback_taken="return empty spec list",
                severity="warning",
                context={"plan_step_id": step.step_id, "tool": self.name},
            )
            return []

        if err or not text:
            log_degrade(
                subsystem="wes",
                operation=f"execution_hub.{self.name}.build_specs",
                failure_reason=f"backend_error: {err}" if err else "empty_response",
                fallback_taken="return empty spec list",
                severity="warning",
                context={"plan_step_id": step.step_id, "tool": self.name},
            )
            return []

        specs = _parse_specs(text, step.step_id)
        if not specs:
            log_degrade(
                subsystem="wes",
                operation=f"execution_hub.{self.name}.build_specs",
                failure_reason="xml_parse_failure_or_empty_batch",
                fallback_taken="return empty spec list",
                severity="warning",
                context={
                    "plan_step_id": step.step_id,
                    "tool": self.name,
                    "response_excerpt": text[:200],
                },
            )
        return specs

    # ── internals ────────────────────────────────────────────────────

    def _make_vars(
        self, step: "WESPlanStep", slice: "BundleToolSlice"
    ) -> Dict[str, Any]:
        thread_headlines = [
            t.headline for t in slice.threads_in_focal_address
        ]
        return {
            "tool_name": self.name,
            "plan_step_id": step.step_id,
            "step_intent": step.intent,
            "step_slots": step.slots,
            "directive_text": slice.directive_text,
            "address_hint": slice.address_hint,
            "firing_tier": slice.firing_tier,
            "thread_headlines": thread_headlines,
            "recent_registry_entries": slice.recent_registry_entries,
        }


__all__ = ["LLMExecutionHub"]

"""LLMExecutorTool — Tier 3 LLM-backed generator (§5.4, P7/P8).

One instance per tool type. Implements
:class:`~world_system.wes.protocols.ExecutorTool`.

Flow:
    1. Build prompts from ``prompt_fragments_tool_<tool>.json``.
    2. Embed the spec as structured JSON input.
    3. Call ``BackendManager.generate(task=f"wes_tool_{tool}", ...)``.
    4. Parse response as JSON. One retry on parse failure with stricter
       prompt (embeds the canonical example).
    5. On second failure, ``log_degrade`` and return ``{}``. The
       downstream deterministic validator treats empty dict as a schema
       violation → step marked failed.
"""

from __future__ import annotations

import json
import os
from typing import TYPE_CHECKING, Any, Dict, Optional, Tuple

from world_system.living_world.backends.backend_manager import BackendManager
from world_system.living_world.infra.graceful_degrade import log_degrade
from world_system.wes.llm_tiers.prompt_assembler import PromptAssembler

if TYPE_CHECKING:
    from world_system.wes.dataclasses import ExecutorSpec


_KNOWN_TOOLS = {"hostiles", "materials", "nodes", "skills", "titles"}


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


def _parse_json(text: str) -> Optional[Dict[str, Any]]:
    if not text:
        return None
    try:
        data = json.loads(_strip_markdown_fence(text))
        if isinstance(data, dict):
            return data
        return None
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


class LLMExecutorTool:
    """Tier 3 executor. Constructed once per tool type."""

    TASK_PREFIX = "wes_tool_"

    def __init__(
        self,
        tool_name: str,
        schema_path: Optional[str] = None,
        backend_manager: Optional[BackendManager] = None,
        fragments_path: Optional[str] = None,
    ):
        if tool_name not in _KNOWN_TOOLS:
            log_degrade(
                subsystem="wes",
                operation="executor_tool.__init__",
                failure_reason=f"Unknown tool_name: {tool_name!r}",
                fallback_taken="accept and continue",
                severity="info",
                context={"tool_name": tool_name},
            )
        self.name: str = tool_name
        # schema_path is retained for validator.generate signatures but
        # not enforced at this layer — deterministic glue owns schema
        # validation (§5.5).
        self.schema_path: str = schema_path or ""
        self._backend = backend_manager or BackendManager.get_instance()
        self._assembler = PromptAssembler(
            fragments_path or _resolve_config_path(
                f"prompt_fragments_tool_{tool_name}.json"
            )
        )

    @property
    def task_name(self) -> str:
        return f"{self.TASK_PREFIX}{self.name}"

    # ── Protocol method ──────────────────────────────────────────────

    def generate(self, spec: "ExecutorSpec") -> Dict[str, Any]:
        """Produce one tool JSON from one spec."""
        variables = self._make_vars(spec)
        prompts = self._assembler.build(variables)

        result, err = self._attempt(prompts["system"], prompts["user"])
        if result is not None:
            return result

        # Retry once with stricter prompt
        stricter = self._stricter_suffix(prompts["output_example"])
        retry_prompts = self._assembler.build(
            variables, extra_system_suffix=stricter
        )
        result, err2 = self._attempt(
            retry_prompts["system"], retry_prompts["user"]
        )
        if result is not None:
            return result

        log_degrade(
            subsystem="wes",
            operation=f"executor_tool.{self.name}.generate",
            failure_reason=f"JSON parse failed twice: {err} / {err2}",
            fallback_taken="return empty dict",
            severity="warning",
            context={"spec_id": spec.spec_id, "tool": self.name},
        )
        return {}

    # ── internals ────────────────────────────────────────────────────

    def _make_vars(self, spec: "ExecutorSpec") -> Dict[str, Any]:
        return {
            "tool_name": self.name,
            "spec_id": spec.spec_id,
            "plan_step_id": spec.plan_step_id,
            "item_intent": spec.item_intent,
            "spec_json": spec.to_dict(),
            "flavor_hints": spec.flavor_hints,
            "cross_ref_hints": spec.cross_ref_hints,
            "hard_constraints": spec.hard_constraints,
        }

    def _attempt(
        self, system_prompt: str, user_prompt: str
    ) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
        try:
            text, err = self._backend.generate(
                task=self.task_name,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
            )
        except Exception as e:
            return None, f"backend exception: {e}"
        if err or not text:
            return None, err or "empty_response"
        parsed = _parse_json(text)
        if parsed is None:
            return None, "parse_failure"
        return parsed, None

    def _stricter_suffix(self, example: str) -> str:
        if not example:
            return (
                "Strict retry. Emit ONLY a single JSON object matching the "
                f"{self.name} schema. No prose, no markdown fences."
            )
        return (
            "Strict retry. Emit ONLY a single JSON object matching this "
            f"exact schema (by example):\n{example}"
        )


__all__ = ["LLMExecutorTool"]

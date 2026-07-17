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
            # default_plan_step_id enables the tolerant element-children
            # dialect real models emit (2026-07-10 certification) — the
            # dispatcher owns the authoritative step id regardless.
            specs = parse_xml_batch(text, default_plan_step_id=plan_step_id)
        except Exception:
            # Terminal fallthrough — CC3: must not be silent (2026-06-10).
            # An empty spec list makes the orchestrator think no work was
            # requested, so the WES run quietly produces zero output.
            from world_system.living_world.infra.graceful_degrade import log_parse_failure
            log_parse_failure(
                "wes_execution_hub", text,
                fallback_taken=f"returned [] — plan_step {plan_step_id} yields no specs",
            )
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


_KNOWN_TOOLS = {
    "hostiles", "materials", "nodes", "skills", "titles",
    "chunks", "npcs", "quests",
}


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
        """LLM call; parse XML batch into ExecutorSpec list.

        2026-07-10 hub audit: the output schema+example are now
        INJECTED into the system prompt (include_output_format — they
        previously lived only in ``_output`` metadata that no prompt
        ever carried), and a parse failure triggers ONE retry with a
        stricter format suffix, matching the planner/tool tiers. The
        hub is the fan-out heart of WES — an empty batch means zero
        content for the whole step.
        """
        variables = self._make_vars(step, slice)
        prompts = self._assembler.build(
            variables,
            firing_tier=slice.firing_tier,
            include_output_format=True,
        )

        specs = self._filter_registry_collisions(
            self._attempt(prompts, step), slice, step)
        if specs:
            return specs

        # One strict retry (parity with planner/tool tiers).
        stricter = (
            "STRICT RETRY — your previous response did not parse. Emit "
            "ONLY the <specs> XML batch, no prose, no markdown fences. "
            "Follow the [OUTPUT FORMAT] example shape exactly."
        )
        retry_prompts = self._assembler.build(
            variables,
            firing_tier=slice.firing_tier,
            include_output_format=True,
            extra_system_suffix=stricter,
        )
        specs = self._filter_registry_collisions(
            self._attempt(retry_prompts, step), slice, step)
        if not specs:
            log_degrade(
                subsystem="wes",
                operation=f"execution_hub.{self.name}.build_specs",
                failure_reason="xml_parse_failure_or_empty_batch_after_retry",
                fallback_taken="return empty spec list",
                severity="warning",
                context={"plan_step_id": step.step_id, "tool": self.name},
            )
        return specs

    def _filter_registry_collisions(
        self, specs: List[ExecutorSpec], slice: "BundleToolSlice",
        step: "WESPlanStep",
    ) -> List[ExecutorSpec]:
        """Drop specs that would recreate EXISTING (source=live) content.

        2026-07-17 certification: small models occasionally re-emit a
        live registry entry's name despite the explicit "do NOT
        recreate" instruction (~1 in 2 gemma3:4b hostile batches).
        Prompt compliance is probabilistic; this guard is
        deterministic — dedup no longer depends on model obedience.
        Only source=live entries block; co_emitted_this_plan entries
        are legitimate reference targets.
        """
        if not specs:
            return specs
        live_names = set()
        for entry in getattr(slice, "recent_registry_entries", []) or []:
            if isinstance(entry, dict) and entry.get("source") == "live":
                name = str(entry.get("display_name") or "").strip().lower()
                if name:
                    live_names.add(name)
                cid = str(entry.get("content_id") or "").strip().lower()
                if cid:
                    live_names.add(cid.replace("_", " "))
        if not live_names:
            return specs
        kept: List[ExecutorSpec] = []
        for s in specs:
            hint = str((s.flavor_hints or {}).get("name_hint", "")).strip().lower()
            if hint and hint in live_names:
                log_degrade(
                    subsystem="wes",
                    operation=f"execution_hub.{self.name}.dedup_guard",
                    failure_reason=f"spec {s.spec_id!r} recreates live "
                                   f"registry entry {hint!r}",
                    fallback_taken="spec dropped from batch",
                    severity="info",
                    context={"plan_step_id": step.step_id,
                             "tool": self.name},
                )
                continue
            kept.append(s)
        return kept

    def _attempt(self, prompts: Dict[str, str],
                 step: "WESPlanStep") -> List[ExecutorSpec]:
        """One generate + parse pass. Returns [] on any failure (logged)."""
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

        return _parse_specs(text, step.step_id)

    # ── internals ────────────────────────────────────────────────────

    def _make_vars(
        self, step: "WESPlanStep", slice: "BundleToolSlice"
    ) -> Dict[str, Any]:
        thread_headlines = [
            t.headline for t in slice.threads_in_focal_address
        ]
        parent_thread_headlines = [
            t.headline for t in slice.threads_in_parent_addresses
        ]
        # Phase 1 contract (2026-06-03): hubs now expose the full
        # narrative-context propagation fields so prompts can refer
        # to them. The legacy thread_headlines var is retained for
        # backward-compatible prompts; new prompts should prefer
        # thread_fragments (full payloads with content_tags +
        # relationship) for richer downstream context.
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
            # ── Phase 1 narrative propagation ──────────────────────
            "firing_narrative": slice.firing_layer_summary,
            "parent_narratives": _render_parent_summaries(
                slice.parent_summaries
            ),
            "geographic_chain": slice.geographic_chain,
            "thread_fragments": [
                t.to_dict() for t in slice.threads_in_focal_address
            ],
            "parent_thread_fragments": [
                t.to_dict() for t in slice.threads_in_parent_addresses
            ],
            "parent_thread_headlines": parent_thread_headlines,
            "wms_events_summary": _render_wms_brief(
                slice.wms_events_since_last
            ),
            "npc_dialogue_summary": _render_dialogue_brief(
                slice.npc_dialogue_since_last
            ),
            "trigger_archetype": slice.trigger_archetype,
        }


def _render_parent_summaries(parent: Dict[str, str]) -> str:
    """Format ``parent_summaries`` dict as a short readable block.

    Empty dict renders as empty string (the prompt template handles
    the conditional). Each entry on its own line keyed
    ``[layer:address] summary``.
    """
    if not parent:
        return ""
    lines = [f"[{key}] {summary}" for key, summary in parent.items()]
    return "\n".join(lines)


def _render_wms_brief(rows: List[Any]) -> str:
    """Format a small block of recent WMS L2 events for the hub prompt.

    Empty rows → empty string so the template renders cleanly when no
    delta data is available (Phase 0 G02 caller; Phase 1 bridge wires
    actual data).
    """
    if not rows:
        return ""
    lines: List[str] = []
    for r in rows[:6]:  # cap at 6 to keep prompt budget bounded
        narrative = getattr(r, "narrative", "") or ""
        if not narrative:
            continue
        lines.append(f"- {narrative}")
    return "\n".join(lines)


def _render_dialogue_brief(rows: List[Any]) -> str:
    """Format a small block of recent NPC dialogue for the hub prompt.

    Empty rows → empty string. Each row renders as
    ``- <npc_id>: <text>``.
    """
    if not rows:
        return ""
    lines: List[str] = []
    for r in rows[:6]:  # cap at 6
        npc_id = getattr(r, "npc_id", "?") or "?"
        text = getattr(r, "dialogue_text", "") or ""
        if not text:
            continue
        lines.append(f"- {npc_id}: {text}")
    return "\n".join(lines)


__all__ = ["LLMExecutionHub"]

"""WMS AI Central — manages LLM calls for Layers 2-7 of the World Memory System.

This is the single LLM interface for all WMS narrative generation.
Uses BackendManager for model routing (Claude → Ollama → Mock fallback).
Uses PromptAssembler for tag-based prompt construction.

Layer 2 evaluators call this instead of formatting template strings.
Higher layers (3-7) will use this with their own prompt configurations.

Usage:
    ai = WmsAI.get_instance()
    ai.initialize()

    # Called by evaluators when a threshold trigger fires
    result = ai.generate_narration(
        event_type="enemy_killed",
        event_subtype="killed_wolf_grey",
        tier=1,
        tags=["species:wolf_grey", "tier:1"],
        data_block="Wolves killed today: 8\\nAll-time: 47\\nLocation: Whispering Woods",
    )
    # result.text = "Player has killed 8 wolves in Whispering Woods today, ..."
    # result.success = True
"""

from __future__ import annotations

import json
import time
import threading
from dataclasses import dataclass, field
from typing import Any, Callable, ClassVar, Dict, List, Optional

from world_system.world_memory.event_schema import SEVERITY_ORDER
from world_system.world_memory.tag_library import validate_tag


def _extract_json_object(text: str) -> Optional[dict]:
    """Best-effort extraction of a JSON object from an LLM reply.

    Real model outputs routinely wrap JSON in markdown fences or lead
    with prose ("Here is the narration: {...}"). The old parser only
    tried json.loads when the reply STARTED with '{' — a fenced or
    preambled but otherwise valid reply fell through raw, so the
    narrative became literal ```json garbage and tags were lost
    (2026-07 audit). Order: direct parse, fence-stripped parse, then
    the first-'{'-to-last-'}' substring.
    """
    candidates = [text]
    stripped = text.strip()
    if stripped.startswith("```"):
        inner = stripped.strip("`")
        # Drop a language hint like "json" on the first line
        first_newline = inner.find("\n")
        if first_newline != -1 and len(inner[:first_newline].split()) <= 1:
            inner = inner[first_newline + 1:]
        candidates.append(inner)
    start, end = text.find("{"), text.rfind("}")
    if start != -1 and end > start:
        candidates.append(text[start:end + 1])
    for candidate in candidates:
        try:
            parsed = json.loads(candidate)
            if isinstance(parsed, dict):
                return parsed
        except (json.JSONDecodeError, TypeError):
            continue
    return None


@dataclass
class NarrationResult:
    """Result from an LLM narration call."""
    text: str = ""
    severity: str = "minor"
    tags: List[str] = field(default_factory=list)
    success: bool = True
    from_fallback: bool = False
    error: str = ""
    model_used: str = ""
    tokens_estimated: int = 0
    generation_time_ms: float = 0.0


# Layer-specific LLM configuration.
# data_budget (chars, ~4 chars/token) bounds the DATA BLOCK handed to the
# prompt. 2026-07 audit: data blocks were unbounded — a burst district could
# stuff arbitrarily many events into one consolidation prompt, violating the
# design doctrine that budgets are enforced at assembly time (WORKING_DOC
# §8.4). Values are generous (typical blocks sit well under them) so normal
# behavior is unchanged; they exist to bound the tail. Whole-event
# truncation via text_budget.clamp_xml_events_to_budget.
LAYER_CONFIG = {
    2: {
        "task": "wms_layer2",
        "temperature": 0.3,
        "max_tokens": 150,
        "data_budget": 2400,
        "description": "Layer 2: one-sentence factual narrations from evaluator triggers",
    },
    3: {
        "task": "wms_layer3",
        "temperature": 0.4,
        "max_tokens": 300,
        "data_budget": 6000,
        "description": "Layer 3: cross-domain consolidation across districts",
    },
    4: {
        "task": "wms_layer4",
        "temperature": 0.4,
        "max_tokens": 400,
        "data_budget": 8000,
        "description": "Layer 4: provincial summaries",
    },
    5: {
        "task": "wms_layer5",
        "temperature": 0.5,
        "max_tokens": 500,
        "data_budget": 8000,
        "description": "Layer 5: region-level summaries",
    },
    6: {
        "task": "wms_layer6",
        "temperature": 0.5,
        "max_tokens": 500,
        "data_budget": 8000,
        "description": "Layer 6: nation-level summaries",
    },
    7: {
        "task": "wms_layer7",
        "temperature": 0.6,
        "max_tokens": 600,
        "data_budget": 9000,
        "description": "Layer 7: world narrative threads",
    },
}


class WmsAI:
    """Central LLM manager for the World Memory System.

    Coordinates between PromptAssembler (context construction)
    and BackendManager (model routing).
    """

    _instance: ClassVar[Optional[WmsAI]] = None

    def __init__(self):
        self._backend = None  # BackendManager
        self._assembler = None  # PromptAssembler
        self._initialized = False
        self._call_count = 0
        self._error_count = 0
        self._total_time_ms = 0.0

    @classmethod
    def get_instance(cls) -> WmsAI:
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reset(cls):
        cls._instance = None

    def initialize(self, backend_manager=None, assembler=None) -> None:
        """Wire up dependencies.

        Args:
            backend_manager: BackendManager instance (or None to auto-resolve).
            assembler: PromptAssembler instance (or None to create one).
        """
        # Backend manager — try to get existing instance
        if backend_manager:
            self._backend = backend_manager
        else:
            try:
                from world_system.living_world.backends.backend_manager import (
                    BackendManager,
                )
                self._backend = BackendManager.get_instance()
                if not self._backend._initialized:
                    self._backend.initialize()
            except Exception as e:
                print(f"[WmsAI] BackendManager init failed: {e}")
                self._backend = None

        # Prompt assembler
        if assembler:
            self._assembler = assembler
        else:
            from world_system.world_memory.prompt_assembler import PromptAssembler
            self._assembler = PromptAssembler()
            loaded = self._assembler.load()
            print(f"[WmsAI] Loaded {loaded} prompt fragments")

        self._initialized = True
        print("[WmsAI] Initialized")

    # ── Layer 2: Evaluator Narrations ───────────────────────────────

    def generate_narration(self,
                           event_type: str,
                           event_subtype: str = "",
                           tier: Optional[int] = None,
                           tags: Optional[List[str]] = None,
                           data_block: str = "",
                           layer: int = 2,
                           ) -> NarrationResult:
        """Generate a narrative interpretation for a Layer 2+ evaluator.

        This is the primary method called by evaluators. It:
        1. Builds tags from event data (if not provided)
        2. Assembles the prompt from matching fragments
        3. Calls the LLM via BackendManager
        4. Returns the narration text

        Args:
            event_type: The memory event type (e.g. "enemy_killed")
            event_subtype: Specific subtype (e.g. "killed_wolf_grey")
            tier: Entity tier if known
            tags: Pre-built tag list (or None to auto-derive)
            data_block: The stat/temporal data to include in the prompt
            layer: Which WMS layer (2-7) — affects temperature/token budget

        Returns:
            NarrationResult with text, success status, and metadata.
        """
        if not self._initialized:
            return NarrationResult(
                text=self._template_fallback(event_type, event_subtype, data_block),
                from_fallback=True,
                error="WmsAI not initialized",
            )

        start = time.time()

        # 1. Build tags if not provided
        if tags is None:
            tags = self._assembler.tags_from_event(event_type, event_subtype, tier)

        # 1.5 Enforce the per-layer data-block budget BEFORE assembly (whole-
        # event truncation; the <omitted/> marker tells the model the view
        # was capped). This is the single choke point every L2-L7 call
        # flows through, so all five XML builders are bounded transitively.
        config = LAYER_CONFIG.get(layer, LAYER_CONFIG[2])
        events_omitted = 0
        data_budget = config.get("data_budget", 0)
        if data_budget and data_block and len(data_block) > data_budget:
            from world_system.world_memory.text_budget import clamp_xml_events_to_budget
            data_block, events_omitted = clamp_xml_events_to_budget(data_block, data_budget)
            print(f"[WmsAI] L{layer} data block over budget "
                  f"({data_budget} chars): dropped {events_omitted} oldest events")

        # 2. Assemble prompt (layer-specific assembly for Layer 3+)
        if layer == 7:
            prompt = self._assembler.assemble_l7(data_block, event_tags=tags)
        elif layer == 6:
            prompt = self._assembler.assemble_l6(data_block, event_tags=tags)
        elif layer == 5:
            prompt = self._assembler.assemble_l5(data_block, event_tags=tags)
        elif layer == 4:
            prompt = self._assembler.assemble_l4(data_block, event_tags=tags)
        elif layer == 3:
            # Extract consolidator ID from event_type (e.g. "layer3_regional_synthesis")
            cons_id = event_type.replace("layer3_", "") if event_type.startswith("layer3_") else event_type
            prompt = self._assembler.assemble_l3(cons_id, data_block)
        else:
            prompt = self._assembler.assemble(tags, data_block)

        # 3. Call LLM (config resolved above at the budget step). The
        # log_extra rides into llm_debug_logs so designers can see WHICH
        # fragments composed each prompt — the observability the design
        # charter calls non-negotiable (WORKING_DOC §8.11).
        result = self._call_llm(
            system_prompt=prompt.system,
            user_prompt=prompt.user,
            task=config["task"],
            temperature=config["temperature"],
            max_tokens=config["max_tokens"],
            log_extra={
                "layer": layer,
                "fragments": [k for k, _ in prompt.fragments_used],
                "fragment_chars": sum(len(t) for _, t in prompt.fragments_used),
                "data_block_chars": len(data_block),
                "events_omitted": events_omitted,
                "token_estimate": prompt.token_estimate,
            },
            layer=layer,
        )

        elapsed_ms = (time.time() - start) * 1000
        self._call_count += 1
        self._total_time_ms += elapsed_ms

        if result.success:
            result.tokens_estimated = prompt.token_estimate
            result.generation_time_ms = elapsed_ms
            return result
        else:
            # Fallback to template
            self._error_count += 1
            return NarrationResult(
                text=self._template_fallback(event_type, event_subtype, data_block),
                from_fallback=True,
                error=result.error,
                generation_time_ms=elapsed_ms,
            )

    def generate_narration_async(self,
                                  event_type: str,
                                  event_subtype: str = "",
                                  tier: Optional[int] = None,
                                  tags: Optional[List[str]] = None,
                                  data_block: str = "",
                                  layer: int = 2,
                                  callback: Optional[Callable] = None,
                                  ) -> threading.Thread:
        """Async version — runs LLM call in background thread.

        The callback receives a NarrationResult when done.
        Use this from the game loop to avoid blocking.
        """
        def _worker():
            result = self.generate_narration(
                event_type, event_subtype, tier, tags, data_block, layer)
            if callback:
                callback(result)

        thread = threading.Thread(target=_worker, daemon=True)
        thread.start()
        return thread

    # ── LLM Call ────────────────────────────────────────────────────

    def _call_llm(self, system_prompt: str, user_prompt: str,
                  task: str, temperature: float,
                  max_tokens: int,
                  log_extra: Optional[Dict[str, Any]] = None,
                  layer: Optional[int] = None) -> NarrationResult:
        """Route an LLM call through BackendManager.

        Response parsing (2026-07 audit rewrite — the old parser failed
        against its own prompt contract):
        - JSON is extracted tolerantly (markdown fences, prose preamble)
          instead of requiring the reply to START with '{'.
        - Severity comes from a ``significance:``/``severity:`` tag with
          a validated vocabulary. The prompt asks for ``significance:``
          but the old code only matched ``severity:``, so a fully
          compliant reply never set severity — and the old fallback
          substring-searched the narrative, so innocent fantasy prose
          ("a critical blow") silently inflated severity. That fallback
          is REMOVED: no valid tag -> "minor", which downstream means
          "no override" (the evaluator's template severity stands).
        - Tags are validated against the tag library allow-list when the
          layer is known — the tag system is load-bearing; LLM-invented
          categories must not enter the retrieval index.
        - An empty narrative is a FAILURE (callers fall back to the
          template), not an empty success.
        """
        if not self._backend:
            return NarrationResult(
                success=False,
                error="No backend available",
            )

        try:
            text, error = self._backend.generate(
                task=task,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                temperature=temperature,
                max_tokens=max_tokens,
                log_extra=log_extra,
            )

            if error:
                return NarrationResult(success=False, error=error)

            text = (text or "").strip()
            llm_tags: List[str] = []

            parsed = _extract_json_object(text)
            if parsed is not None:
                text = parsed.get("narrative", parsed.get("text",
                       parsed.get("dialogue", text)))
                raw_tags = parsed.get("tags", [])
                if isinstance(raw_tags, list):
                    llm_tags = [t for t in raw_tags
                                if isinstance(t, str) and ":" in t]
            elif text.startswith("{") or text.startswith("```"):
                # Meant to be JSON but unparseable (usually truncated by
                # max_tokens) — fail to the template rather than persist
                # a broken-JSON fragment as the narrative.
                return NarrationResult(success=False,
                                       error="unparseable JSON in response")

            if isinstance(text, dict):
                text = str(text)
            text = str(text).strip().strip('"').strip("'")

            if not text:
                return NarrationResult(success=False,
                                       error="empty narrative in response")

            # Severity from significance:/severity: tags only, with a
            # validated vocabulary. These tags are consumed here and NOT
            # forwarded — the enriched tag set already carries the
            # canonical significance tag derived from the final severity.
            severity = "minor"
            kept_tags: List[str] = []
            for tag in llm_tags:
                category, _, value = tag.partition(":")
                if category in ("severity", "significance"):
                    value = value.strip().lower()
                    if value in SEVERITY_ORDER:
                        severity = value
                    else:
                        print(f"[WmsAI] Ignoring invalid severity value "
                              f"{value!r} from LLM ({task})")
                    continue
                kept_tags.append(tag)

            # Allow-list: the tag library is the single source of truth.
            if layer is not None and kept_tags:
                valid_tags = []
                for tag in kept_tags:
                    if validate_tag(tag, layer):
                        valid_tags.append(tag)
                    else:
                        print(f"[WmsAI] Dropping LLM-invented tag "
                              f"{tag!r} (not in tag library for layer "
                              f"{layer})")
                kept_tags = valid_tags

            return NarrationResult(
                text=text,
                severity=severity,
                tags=kept_tags,
                success=True,
                model_used=task,
            )

        except Exception as e:
            return NarrationResult(success=False, error=str(e))

    # ── Template Fallback ───────────────────────────────────────────

    def _template_fallback(self, event_type: str, event_subtype: str,
                           data_block: str) -> str:
        """Simple template narration when LLM is unavailable.

        This produces the same basic output as the current evaluator templates.
        Good enough for testing; the LLM provides richer narrations when available.
        """
        # Extract key info from data block
        lines = data_block.strip().split("\n")
        info = {}
        for line in lines:
            if ":" in line:
                k, v = line.split(":", 1)
                info[k.strip().lower()] = v.strip()

        count = info.get("count today", info.get("count", "?"))
        location = info.get("location", "the world")
        alltime = info.get("all-time", "?")

        # Build entity name from subtype
        entity = event_subtype
        for prefix in ("killed_", "gathered_", "crafted_", "used_",
                        "talked_to_", "accepted_", "completed_"):
            if entity.startswith(prefix):
                entity = entity[len(prefix):]
                break
        entity = entity.replace("_", " ")

        # Format based on event type
        if event_type == "enemy_killed":
            return f"Player has killed {count} {entity} in {location} today ({alltime} total)."
        elif event_type == "resource_gathered":
            return f"Player has gathered {count} {entity} in {location} today ({alltime} total)."
        elif event_type == "craft_attempted":
            return f"Player has crafted {count} items today ({alltime} total)."
        elif event_type == "level_up":
            return f"Player has reached a new level."
        else:
            return f"Player activity: {event_type} ({count} today, {alltime} total)."

    # ── Stats ───────────────────────────────────────────────────────

    @property
    def stats(self) -> Dict[str, Any]:
        return {
            "initialized": self._initialized,
            "calls": self._call_count,
            "errors": self._error_count,
            "avg_time_ms": (self._total_time_ms / max(self._call_count, 1)),
            "backend_available": self._backend is not None,
            "fragments_loaded": (
                self._assembler.fragment_count if self._assembler else 0),
        }

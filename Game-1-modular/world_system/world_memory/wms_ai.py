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


# Layer-specific LLM configuration
LAYER_CONFIG = {
    2: {
        "task": "wms_layer2",
        "temperature": 0.3,
        "max_tokens": 150,
        "description": "Layer 2: one-sentence factual narrations from evaluator triggers",
    },
    3: {
        "task": "wms_layer3",
        "temperature": 0.4,
        "max_tokens": 300,
        "description": "Layer 3: cross-domain consolidation across districts",
    },
    4: {
        "task": "wms_layer4",
        "temperature": 0.4,
        "max_tokens": 400,
        "description": "Layer 4: provincial summaries",
    },
    5: {
        "task": "wms_layer5",
        "temperature": 0.5,
        "max_tokens": 500,
        "description": "Layer 5: region-level summaries",
    },
    6: {
        "task": "wms_layer6",
        "temperature": 0.5,
        "max_tokens": 500,
        "description": "Layer 6: nation-level summaries",
    },
    7: {
        "task": "wms_layer7",
        "temperature": 0.6,
        "max_tokens": 600,
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

        # 2. Assemble prompt (layer-specific assembly for Layer 3+)
        if layer == 6:
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

        # 3. Call LLM
        config = LAYER_CONFIG.get(layer, LAYER_CONFIG[2])
        result = self._call_llm(
            system_prompt=prompt.system,
            user_prompt=prompt.user,
            task=config["task"],
            temperature=config["temperature"],
            max_tokens=config["max_tokens"],
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
                  max_tokens: int) -> NarrationResult:
        """Route an LLM call through BackendManager."""
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
            )

            if error:
                return NarrationResult(success=False, error=error)

            # Parse response — handle JSON with narrative + tags
            text = text.strip()
            llm_tags = []

            if text.startswith("{"):
                try:
                    parsed = json.loads(text)
                    text = parsed.get("narrative", parsed.get("text",
                           parsed.get("dialogue", text)))
                    # Extract LLM-assigned tags
                    raw_tags = parsed.get("tags", [])
                    if isinstance(raw_tags, list):
                        llm_tags = [t for t in raw_tags
                                    if isinstance(t, str) and ":" in t]
                except (json.JSONDecodeError, TypeError):
                    pass

            if isinstance(text, dict):
                text = str(text)
            text = text.strip().strip('"').strip("'")

            # Extract severity from tags first, then fallback to text search
            severity = "minor"
            for tag in llm_tags:
                if tag.startswith("severity:"):
                    severity = tag.split(":", 1)[1]
                    llm_tags = [t for t in llm_tags
                                if not t.startswith("severity:")]
                    break
            else:
                text_lower = text.lower()
                for sev in ("critical", "major", "significant",
                            "moderate", "minor"):
                    if sev in text_lower:
                        severity = sev
                        break

            return NarrationResult(
                text=text,
                severity=severity,
                tags=llm_tags,
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

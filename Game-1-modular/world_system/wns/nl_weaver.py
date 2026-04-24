"""NL Weaver — LLM weaving operation for NL2-NL7.

Per §4.3 of the working doc, weaving is **one operation parameterized by
scale**. This class holds the scale (layer) + address at construction,
reads lower-layer + parent-layer narrative, calls
``BackendManager.generate(task="wns_layer<N>")``, parses the JSON
response, persists the resulting NL row, and publishes a
``WNS_CALL_WES_REQUESTED`` event on the :class:`GameEventBus` if the
weaver's output has ``call_wes: true``.

This phase **does NOT invoke WES** — only publishes the request event.
WES is owned by a later phase (Agents C/D per the task brief).

The weaver is resilient to backend failure: if generation returns an
error, the run is logged via :func:`log_degrade` and no NL row is
written. If the LLM output cannot be parsed, same treatment.
"""

from __future__ import annotations

import json
import os
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from events.event_bus import get_event_bus
from world_system.living_world.backends.backend_manager import BackendManager
from world_system.living_world.infra.context_bundle import ThreadFragment
from world_system.living_world.infra.graceful_degrade import log_degrade
from world_system.wns.narrative_distance_filter import (
    FilteredNarrative,
    NarrativeDistanceFilter,
)
from world_system.wns.narrative_store import NarrativeRow, NarrativeStore
from world_system.wns.narrative_tag_library import NarrativeTagLibrary


# Event name published on call_wes=true. WES (later phase) subscribes.
WNS_CALL_WES_EVENT = "WNS_CALL_WES_REQUESTED"


@dataclass
class WeaverRunResult:
    """Outcome of a single :meth:`NLWeaver.run_weaving` call.

    Returned so callers / tests can inspect what happened without
    re-querying the store.
    """

    success: bool
    row: Optional[NarrativeRow] = None
    threads: List[ThreadFragment] = field(default_factory=list)
    call_wes: bool = False
    directive_hint: str = ""
    error: str = ""


class NLWeaver:
    """One weaver per layer. Holds layer-scoped prompt fragments + task name.

    Parameters:
        layer: NL layer (2..7). NL1 is not woven.
        store: The :class:`NarrativeStore` the weaver persists rows to.
        tag_library: For address-vs-content partitioning of LLM output.
        backend_manager: For ``BackendManager.generate(task=...)``.
        prompt_fragments_path: Path to ``narrative_fragments_nl<N>.json``.
        distance_filter: For trimming candidate-narrative input.
    """

    def __init__(
        self,
        layer: int,
        store: NarrativeStore,
        tag_library: NarrativeTagLibrary,
        backend_manager: BackendManager,
        prompt_fragments_path: Optional[str] = None,
        distance_filter: Optional[NarrativeDistanceFilter] = None,
    ) -> None:
        if layer < 2 or layer > 7:
            raise ValueError(
                f"NLWeaver: layer must be 2..7; NL1 is deterministic capture, got {layer}"
            )
        self._layer = int(layer)
        self._store = store
        self._tag_library = tag_library
        self._backend = backend_manager
        self._distance_filter = distance_filter or NarrativeDistanceFilter()
        self._prompt_fragments_path = prompt_fragments_path or self._default_prompt_path()
        self._prompt_fragments: Dict[str, Any] = {}
        self._load_prompt_fragments()

    # ── Loading ──────────────────────────────────────────────────────

    def _default_prompt_path(self) -> str:
        here = os.path.dirname(os.path.abspath(__file__))
        return os.path.normpath(
            os.path.join(
                here, os.pardir, "config",
                f"narrative_fragments_nl{self._layer}.json",
            )
        )

    def _load_prompt_fragments(self) -> None:
        if not os.path.exists(self._prompt_fragments_path):
            # Graceful — leave empty; run_weaving will degrade if needed.
            log_degrade(
                subsystem="wns",
                operation=f"nl_weaver.load_fragments (layer {self._layer})",
                failure_reason=f"FileNotFoundError: {self._prompt_fragments_path}",
                fallback_taken="empty prompt fragments; weaving will use bare scaffold",
                severity="warning",
                context={"layer": self._layer,
                         "path": self._prompt_fragments_path},
            )
            return
        try:
            with open(self._prompt_fragments_path, "r", encoding="utf-8") as f:
                self._prompt_fragments = json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            log_degrade(
                subsystem="wns",
                operation=f"nl_weaver.load_fragments (layer {self._layer})",
                failure_reason=f"{type(e).__name__}: {e}",
                fallback_taken="empty prompt fragments; weaving will use bare scaffold",
                severity="warning",
                context={"layer": self._layer,
                         "path": self._prompt_fragments_path},
            )

    # ── Prompt assembly ──────────────────────────────────────────────

    def _build_system_prompt(self) -> str:
        core = self._prompt_fragments.get("_core", {}) if isinstance(
            self._prompt_fragments, dict) else {}
        system = core.get("system", "")
        return str(system)

    def _build_user_prompt(
        self,
        address: str,
        filtered: FilteredNarrative,
        parent_narrative: str,
        threads_in_scope: List[ThreadFragment],
    ) -> str:
        core = self._prompt_fragments.get("_core", {}) if isinstance(
            self._prompt_fragments, dict) else {}
        template = core.get("user_template", "")

        # Render a simple text version of the filtered narrative.
        lower_parts = []
        for row in filtered.full_detail:
            lower_parts.append(f"- [L{row.layer} @ {row.address}] {row.narrative}")
        lower_narrative = "\n".join(lower_parts) if lower_parts else "(none)"

        threads_text = "\n".join(
            f"- {t.headline} ({t.relationship}, tags={t.content_tags})"
            for t in threads_in_scope
        ) if threads_in_scope else "(none)"

        # Fall back if no template was loaded — still produce a useful prompt.
        if not template:
            return (
                f"Layer {self._layer} weaving at address {address}.\n"
                f"Lower-layer narrative:\n{lower_narrative}\n"
                f"Parent-layer narrative:\n{parent_narrative}\n"
                f"Threads in scope:\n{threads_text}\n"
            )

        return (
            str(template)
            .replace("${address}", address)
            .replace("${lower_narrative}", lower_narrative)
            .replace("${parent_narrative}", parent_narrative or "(none)")
            .replace("${threads_in_scope}", threads_text)
        )

    # ── Main entry point ─────────────────────────────────────────────

    def run_weaving(
        self,
        address: str,
        lower_narratives: Optional[List[NarrativeRow]] = None,
        parent_narrative: str = "",
        threads_in_scope: Optional[List[ThreadFragment]] = None,
        game_time: Optional[float] = None,
    ) -> WeaverRunResult:
        """Run one weaving cycle.

        Args:
            address: Firing address (e.g. ``"locality:tarmouth_copperdocks"``).
            lower_narratives: Candidate NL rows (weaver filters by distance).
                If None, the weaver pulls recent rows at the target and
                lower layers for the same address from the store.
            parent_narrative: Brief summary of the parent layer(s). Free
                text. Caller deals with brevity.
            threads_in_scope: Existing :class:`ThreadFragment` instances to
                feed as context.
            game_time: Optional wall-clock override.
        """
        if game_time is None:
            game_time = time.time()
        threads_in_scope = list(threads_in_scope or [])

        # Pull default candidate pool if caller didn't supply one.
        if lower_narratives is None:
            lower_narratives = self._gather_candidates(address)

        filtered = self._distance_filter.filter_for_firing(
            layer=self._layer,
            address=address,
            all_narratives=lower_narratives,
        )

        task = f"wns_layer{self._layer}"
        system_prompt = self._build_system_prompt()
        user_prompt = self._build_user_prompt(
            address=address,
            filtered=filtered,
            parent_narrative=parent_narrative,
            threads_in_scope=threads_in_scope,
        )

        text, err = self._backend.generate(
            task=task,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
        )
        if err or not text:
            log_degrade(
                subsystem="wns",
                operation=f"nl_weaver.run (layer {self._layer})",
                failure_reason=err or "empty response",
                fallback_taken="no NL row written this tick",
                severity="warning",
                context={"layer": self._layer, "address": address,
                         "task": task},
            )
            return WeaverRunResult(success=False, error=err or "empty response")

        parsed = self._parse_response(text)
        if parsed is None:
            log_degrade(
                subsystem="wns",
                operation=f"nl_weaver.parse (layer {self._layer})",
                failure_reason="JSONDecodeError",
                fallback_taken="no NL row written this tick",
                severity="warning",
                context={"layer": self._layer, "address": address,
                         "task": task, "raw": text[:300]},
            )
            return WeaverRunResult(success=False, error="parse_failed")

        # Build narrative row + threads.
        narrative = str(parsed.get("narrative", "")).strip()
        raw_threads = parsed.get("threads", []) or []
        threads = self._materialize_threads(
            raw_threads=raw_threads,
            address=address,
            game_time=game_time,
        )
        call_wes = bool(parsed.get("call_wes", False))
        directive_hint = str(parsed.get("directive_hint", "")).strip()

        # Content tags: everything non-address in the parsed tags list,
        # if present. Address tags are facts about the event we control —
        # never from the LLM.
        raw_tags = parsed.get("tags") or []
        _, content_tags = self._tag_library.partition_address_and_content(
            [str(t) for t in raw_tags]
        )

        row = NarrativeRow(
            id=str(uuid.uuid4()),
            created_at=game_time,
            layer=self._layer,
            address=address,
            narrative=narrative,
            tags=[address] + content_tags,
            payload={
                "task": task,
                "threads": [t.to_dict() for t in threads],
                "call_wes": call_wes,
                "directive_hint": directive_hint,
                "raw_response": text,
            },
        )
        self._store.insert_row(row)

        # Publish WES request event (stub — WES invocation is a later phase).
        if call_wes:
            self._publish_wes_request(
                address=address,
                directive_text=directive_hint,
                source_row_id=row.id,
                game_time=game_time,
            )

        return WeaverRunResult(
            success=True,
            row=row,
            threads=threads,
            call_wes=call_wes,
            directive_hint=directive_hint,
        )

    # ── Helpers ──────────────────────────────────────────────────────

    def _gather_candidates(self, address: str) -> List[NarrativeRow]:
        """Default candidate pool — pull up to 25 recent rows at this
        layer's target and the next layer down. The distance filter will
        prune further. Chosen to be cheap; higher layers override.
        """
        out: List[NarrativeRow] = []
        # Current layer at address (prior fires), and lower-layer neighbors.
        out.extend(self._store.query_by_address(self._layer, address, limit=10))
        if self._layer > 1:
            out.extend(
                self._store.query_by_address(self._layer - 1, address, limit=25)
            )
        return out

    @staticmethod
    def _parse_response(text: str) -> Optional[Dict[str, Any]]:
        """Parse the LLM response as JSON. Accept a stray prelude/suffix
        the LLM might emit (strip to the first ``{`` / last ``}`` pair)."""
        if not text:
            return None
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass
        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end == -1 or end < start:
            return None
        candidate = text[start : end + 1]
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            return None

    def _materialize_threads(
        self,
        *,
        raw_threads: List[Dict[str, Any]],
        address: str,
        game_time: float,
    ) -> List[ThreadFragment]:
        """Build :class:`ThreadFragment` instances, scrubbing any address
        tags the LLM may have attempted to emit (they're facts we control)."""
        out: List[ThreadFragment] = []
        for t in raw_threads:
            if not isinstance(t, dict):
                continue
            _, content_tags = self._tag_library.partition_address_and_content(
                [str(x) for x in (t.get("content_tags") or [])]
            )
            out.append(
                ThreadFragment(
                    fragment_id=str(uuid.uuid4()),
                    layer=self._layer,
                    address=address,
                    headline=str(t.get("headline", "")).strip(),
                    content_tags=content_tags,
                    parent_thread_id=t.get("parent_thread_id"),
                    relationship=str(t.get("relationship", "open")),
                    created_at=game_time,
                )
            )
        return out

    def _publish_wes_request(
        self,
        *,
        address: str,
        directive_text: str,
        source_row_id: str,
        game_time: float,
    ) -> None:
        """Publish ``WNS_CALL_WES_REQUESTED`` — WES is a later phase, so
        this is observational only. Agents C/D will subscribe downstream."""
        try:
            bus = get_event_bus()
            bus.publish(
                event_type=WNS_CALL_WES_EVENT,
                data={
                    "layer": self._layer,
                    "address": address,
                    "directive_text": directive_text,
                    "source_row_id": source_row_id,
                    "game_time": game_time,
                },
                source=f"wns.nl_weaver.layer{self._layer}",
            )
        except Exception as e:
            log_degrade(
                subsystem="wns",
                operation=f"nl_weaver.publish_wes_request (layer {self._layer})",
                failure_reason=f"{type(e).__name__}: {e}",
                fallback_taken="event not published; WES will not be triggered for this firing",
                severity="warning",
                context={"layer": self._layer, "address": address,
                         "source_row_id": source_row_id},
            )

    # ── Accessors ────────────────────────────────────────────────────

    @property
    def layer(self) -> int:
        return self._layer

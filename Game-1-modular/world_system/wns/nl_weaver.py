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
from world_system.wns.affinity_resolver import AffinityResolver
from world_system.wns.affinity_shift_parser import (
    AffinityShift,
    parse_affinity_shifts,
)
from world_system.wns.cascading_context import (
    WeaverContext,
    build_weaver_context,
    extract_active_threads,
)
from world_system.wns.geographic_context import (
    GeographicContext,
    build_geographic_context,
)
from world_system.wns.narrative_distance_filter import (
    FilteredNarrative,
    NarrativeDistanceFilter,
)
from world_system.wns.narrative_store import NarrativeRow, NarrativeStore
from world_system.wns.narrative_tag_library import NarrativeTagLibrary
from world_system.wns.thread_index import (
    DEFAULT_MATCH_THRESHOLD,
    DEFAULT_TIME_WINDOW_SECONDS,
    build_clusters_from_fragments,
    match_or_mint,
)
from world_system.wns.wes_call_parser import (
    DEFAULT_MAX_CALLS_PER_RUN,
    WESCall,
    parse_wes_calls,
)


# Event name published on call_wes=true. WES (later phase) subscribes.
WNS_CALL_WES_EVENT = "WNS_CALL_WES_REQUESTED"


@dataclass
class WeaverRunResult:
    """Outcome of a single :meth:`NLWeaver.run_weaving` call.

    Returned so callers / tests can inspect what happened without
    re-querying the store.

    The ``call_wes`` / ``directive_hint`` legacy fields are populated
    from the FIRST extracted ``<WES>`` call (if any) for backward
    compatibility. ``wes_calls`` is the full list — cap-limited by
    :data:`DEFAULT_MAX_CALLS_PER_RUN` (default 2).

    ``affinity_shifts`` carries any ``<AffinityShift>`` directives the
    weaver embedded inline. The resolver in
    :mod:`world_system.wns.affinity_resolver` ledgers them; if the
    weaver was constructed with a ``faction_system`` it also applies
    them deterministically.
    """

    success: bool
    row: Optional[NarrativeRow] = None
    threads: List[ThreadFragment] = field(default_factory=list)
    call_wes: bool = False
    directive_hint: str = ""
    error: str = ""
    wes_calls: List[WESCall] = field(default_factory=list)
    affinity_shifts: List[AffinityShift] = field(default_factory=list)


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
        geographic_registry: Optional[Any] = None,
        faction_system: Optional[Any] = None,
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
        # Optional GeographicRegistry-like object. When supplied, the
        # weaver injects a ``${geo_context}`` block into the user prompt
        # describing where this firing sits in the world hierarchy.
        self._geographic_registry = geographic_registry
        # AffinityResolver — deterministic post-processor for inline
        # ``<AffinityShift>`` directives. Always exists; faction_system
        # is forwarded so applies actually hit the FactionSystem store
        # when wired (otherwise resolver is ledger-only).
        self._affinity_resolver = AffinityResolver(faction_system=faction_system)

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

    @staticmethod
    def _render_threads(threads: List[ThreadFragment]) -> str:
        if not threads:
            return "(none)"
        return "\n".join(
            f"- [{t.thread_id or 'no-id'}] {t.headline} "
            f"({t.relationship}, tags={t.content_tags})"
            for t in threads
        )

    def _build_user_prompt(
        self,
        address: str,
        weaver_ctx: WeaverContext,
        geo_ctx: GeographicContext,
        legacy_filtered: Optional[FilteredNarrative] = None,
    ) -> str:
        """Build the user prompt from a WeaverContext + GeographicContext.

        New template variables (replace these in the prompt JSON):
        - ${address}                      firing address
        - ${geo_context}                  rendered geographic descriptor
        - ${self_narrative}               this layer's previous narrative at this address
        - ${self_active_threads}          most recent state of THIS layer's threads
        - ${lower_primary_narrative}      latest narrative from N-1 at this address
        - ${lower_primary_threads}        active threads at N-1
        - ${lower_fading_narrative}       brief from N-2 (sentence cap)
        - ${above_primary_address}        parent address (N+1)
        - ${above_primary_narrative}      narrative at parent address (N+1)
        - ${above_primary_threads}        active threads at N+1
        - ${above_fading_narrative}       grandparent narrative (sentence cap)

        Legacy template variables (kept for backward compatibility):
        - ${lower_narrative}, ${parent_narrative}, ${threads_in_scope}
        """
        core = self._prompt_fragments.get("_core", {}) if isinstance(
            self._prompt_fragments, dict) else {}
        template = core.get("user_template", "")

        # New context blocks
        self_threads_text = self._render_threads(weaver_ctx.self_active_threads)
        lower_primary_threads_text = self._render_threads(weaver_ctx.lower_primary_threads)
        above_primary_threads_text = self._render_threads(weaver_ctx.above_primary_threads)

        # Legacy "lower_narrative" — concatenation of lower primary + fading.
        # If a legacy filtered pool was supplied (test paths), use its detail.
        if legacy_filtered is not None:
            lower_parts = [
                f"- [L{row.layer} @ {row.address}] {row.narrative}"
                for row in legacy_filtered.full_detail
            ]
            lower_narrative = "\n".join(lower_parts) if lower_parts else "(none)"
        else:
            lower_parts = []
            if weaver_ctx.lower_primary_narrative:
                lower_parts.append(
                    f"- [L{self._layer - 1} @ {address}] "
                    f"{weaver_ctx.lower_primary_narrative}"
                )
            if weaver_ctx.lower_fading_narrative:
                lower_parts.append(
                    f"- [L{self._layer - 2} @ {address}] "
                    f"{weaver_ctx.lower_fading_narrative}"
                )
            lower_narrative = "\n".join(lower_parts) if lower_parts else "(none)"

        # Legacy "parent_narrative" — above_primary + above_fading.
        parent_narrative_parts = []
        if weaver_ctx.above_primary_narrative:
            parent_narrative_parts.append(
                f"[L{self._layer + 1} @ {weaver_ctx.above_primary_address}] "
                f"{weaver_ctx.above_primary_narrative}"
            )
        if weaver_ctx.above_fading_narrative:
            parent_narrative_parts.append(
                f"[L{self._layer + 2} @ {weaver_ctx.above_fading_address}] "
                f"{weaver_ctx.above_fading_narrative}"
            )
        parent_narrative_legacy = (
            "\n".join(parent_narrative_parts) if parent_narrative_parts else "(none)"
        )

        # Legacy "threads_in_scope" — same-layer self-threads.
        threads_in_scope_legacy = self_threads_text

        # Fall back if no template was loaded.
        if not template:
            return (
                f"Layer {self._layer} weaving at address {address}.\n"
                f"Geographic context:\n{geo_ctx.rendered}\n\n"
                f"Self (this layer at this address) narrative:\n"
                f"{weaver_ctx.self_latest_narrative or '(none)'}\n"
                f"Self active threads:\n{self_threads_text}\n\n"
                f"Lower-layer narrative:\n{lower_narrative}\n"
                f"Above-layer narrative:\n{parent_narrative_legacy}\n"
            )

        return (
            str(template)
            # New variables
            .replace("${address}", address)
            .replace("${geo_context}", geo_ctx.rendered or "(none)")
            .replace("${self_narrative}", weaver_ctx.self_latest_narrative or "(none)")
            .replace("${self_active_threads}", self_threads_text)
            .replace(
                "${lower_primary_narrative}",
                weaver_ctx.lower_primary_narrative or "(none)",
            )
            .replace("${lower_primary_threads}", lower_primary_threads_text)
            .replace(
                "${lower_fading_narrative}",
                weaver_ctx.lower_fading_narrative or "(none)",
            )
            .replace("${above_primary_address}", weaver_ctx.above_primary_address or "(none)")
            .replace(
                "${above_primary_narrative}",
                weaver_ctx.above_primary_narrative or "(none)",
            )
            .replace("${above_primary_threads}", above_primary_threads_text)
            .replace(
                "${above_fading_narrative}",
                weaver_ctx.above_fading_narrative or "(none)",
            )
            # Legacy variables (still supported for unrevised prompts)
            .replace("${lower_narrative}", lower_narrative)
            .replace("${parent_narrative}", parent_narrative_legacy)
            .replace("${threads_in_scope}", threads_in_scope_legacy)
        )

    # ── Main entry point ─────────────────────────────────────────────

    def run_weaving(
        self,
        address: str,
        lower_narratives: Optional[List[NarrativeRow]] = None,
        parent_narrative: str = "",
        threads_in_scope: Optional[List[ThreadFragment]] = None,
        game_time: Optional[float] = None,
        parent_address: Optional[str] = None,
        grandparent_address: Optional[str] = None,
    ) -> WeaverRunResult:
        """Run one weaving cycle.

        Args:
            address: Firing address (e.g. ``"locality:tarmouth_copperdocks"``).
            lower_narratives: LEGACY — explicit candidate NL rows. When
                None (default), the weaver auto-builds a WeaverContext
                from the store via :func:`build_weaver_context`.
            parent_narrative: LEGACY — free-text parent summary. Ignored
                when ``parent_address`` is supplied (auto-built instead).
            threads_in_scope: LEGACY — explicit thread list. Ignored when
                building from store.
            game_time: Optional wall-clock override.
            parent_address: Address one geographic tier up. Required for
                above-cascading (NL_(N+1) at parent). Pass empty string
                or omit to skip above-cascading.
            grandparent_address: Address two tiers up. Used for
                doubly-cascading fading context (NL_(N+2) at grandparent).
        """
        if game_time is None:
            game_time = time.time()

        legacy_threads_in_scope = list(threads_in_scope or [])

        # Build the cascading context from the store. If callers passed
        # legacy lower_narratives, route that through a separate filtered
        # pool used ONLY for the legacy ${lower_narrative} variable in
        # old prompts; the new variables are filled from WeaverContext.
        weaver_ctx = build_weaver_context(
            self._store,
            layer=self._layer,
            address=address,
            parent_address=parent_address or None,
            grandparent_address=grandparent_address or None,
        )

        # Override self_active_threads with explicit legacy threads_in_scope
        # if the caller supplied them (test paths).
        if legacy_threads_in_scope:
            weaver_ctx.self_active_threads = legacy_threads_in_scope

        # Build geographic context if a registry was wired. None -> skipped.
        geo_ctx = build_geographic_context(address, self._geographic_registry)

        # Optional legacy filtered pool for ${lower_narrative} backward compat.
        legacy_filtered: Optional[FilteredNarrative] = None
        if lower_narratives is not None:
            legacy_filtered = self._distance_filter.filter_for_firing(
                layer=self._layer,
                address=address,
                all_narratives=lower_narratives,
            )

        task = f"wns_layer{self._layer}"
        system_prompt = self._build_system_prompt()
        user_prompt = self._build_user_prompt(
            address=address,
            weaver_ctx=weaver_ctx,
            geo_ctx=geo_ctx,
            legacy_filtered=legacy_filtered,
        )

        # Tuck a hint of the legacy parent_narrative kwarg into the prompt
        # if the caller passed one and the new ${above_*_narrative} slots
        # would otherwise be empty.
        if parent_narrative and not weaver_ctx.above_primary_narrative:
            user_prompt = user_prompt.replace(
                "(none)\n", parent_narrative + "\n", 1
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
        raw_narrative = str(parsed.get("narrative", "")).strip()

        # Extract any inline <WES purpose="...">...</WES> calls from the
        # narrative. The cleaned narrative is what gets persisted; the
        # extracted calls drive WES request events.
        wes_calls, narrative_after_wes = parse_wes_calls(raw_narrative)
        # Then extract any <AffinityShift> blocks from what remains.
        # Affinity shifts are NARRATIVE state-deltas (not new content);
        # they go through the deterministic resolver, not WES.
        affinity_shifts, narrative = parse_affinity_shifts(narrative_after_wes)

        # Backward compat: if the LLM emitted the legacy JSON-level
        # call_wes/directive_hint fields, honor them by synthesizing a
        # WESCall (so downstream sees one unified list).
        legacy_call_wes = bool(parsed.get("call_wes", False))
        legacy_directive_hint = str(parsed.get("directive_hint", "")).strip()
        if legacy_call_wes and legacy_directive_hint and not wes_calls:
            wes_calls = [WESCall(
                purpose="legacy",
                body=legacy_directive_hint,
            )]

        raw_threads = parsed.get("threads", []) or []
        threads = self._materialize_threads(
            raw_threads=raw_threads,
            address=address,
            game_time=game_time,
        )

        # Top-level for legacy callers: True if any WES call was made.
        call_wes = bool(wes_calls)
        directive_hint = wes_calls[0].body if wes_calls else ""

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
                "wes_calls": [
                    {"purpose": c.purpose, "body": c.body} for c in wes_calls
                ],
                "raw_response": text,
            },
        )
        self._store.insert_row(row)

        # Publish a WNS_CALL_WES_REQUESTED event per <WES> call. Each
        # carries a full WESContextBundle inheriting the WNS state at
        # the call site (cascading narrative + active threads + geo
        # descriptor + purpose) so WES subscribers can dispatch directly.
        from world_system.wns.wns_to_wes_bridge import build_wes_bundle
        for call in wes_calls:
            try:
                wes_bundle = build_wes_bundle(
                    layer=self._layer,
                    address=address,
                    wes_call=call,
                    weaver_ctx=weaver_ctx,
                    geo_ctx=geo_ctx,
                    just_written_narrative=narrative,
                    source_row_id=row.id,
                    game_time=game_time,
                )
            except Exception as e:
                log_degrade(
                    subsystem="wns",
                    operation=f"nl_weaver.build_wes_bundle (layer {self._layer})",
                    failure_reason=f"{type(e).__name__}: {e}",
                    fallback_taken="publishing minimal event without bundle",
                    severity="warning",
                    context={"layer": self._layer, "address": address,
                             "purpose": call.purpose},
                )
                wes_bundle = None
            self._publish_wes_request(
                address=address,
                directive_text=call.body,
                source_row_id=row.id,
                game_time=game_time,
                purpose=call.purpose,
                wes_bundle=wes_bundle,
            )

        # Resolve any <AffinityShift> directives the weaver embedded.
        # The resolver always ledgers; it ALSO applies via FactionSystem
        # if one was wired into the weaver at construction.
        if affinity_shifts:
            try:
                self._affinity_resolver.resolve_batch(
                    affinity_shifts,
                    weaver_layer=self._layer,
                    weaver_address=address,
                    narrative_event_id=row.id,
                    game_time=game_time,
                )
            except Exception as e:
                log_degrade(
                    subsystem="wns",
                    operation=f"nl_weaver.affinity_resolve (layer {self._layer})",
                    failure_reason=f"{type(e).__name__}: {e}",
                    fallback_taken="shifts not applied this tick",
                    severity="warning",
                    context={"layer": self._layer, "address": address,
                             "shift_count": len(affinity_shifts)},
                )

        return WeaverRunResult(
            success=True,
            row=row,
            threads=threads,
            call_wes=call_wes,
            directive_hint=directive_hint,
            wes_calls=wes_calls,
            affinity_shifts=affinity_shifts,
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
        """Build :class:`ThreadFragment` instances and assign thread_ids
        via content-cluster matching.

        - Address tags emitted by the LLM are scrubbed (we own those).
        - thread_id is server-assigned via :func:`match_or_mint` against
          existing clusters at this layer/address. The LLM does NOT
          generate thread_ids.
        - parent_thread_id is taken AS-IS from the LLM (cross-layer
          promotion link). Validation against the lower-layer registry is
          a future concern.
        """
        # Pre-fetch existing clusters at this layer/address for matching.
        recent_rows = self._store.query_by_address(
            self._layer, address, limit=30,
        )
        existing_fragments: List[ThreadFragment] = []
        for row in recent_rows:
            for raw_t in (row.payload.get("threads") if row.payload else []) or []:
                if not isinstance(raw_t, dict):
                    continue
                try:
                    existing_fragments.append(ThreadFragment.from_dict(raw_t))
                except (KeyError, ValueError, TypeError):
                    continue
        existing_clusters = build_clusters_from_fragments(existing_fragments)

        out: List[ThreadFragment] = []
        for t in raw_threads:
            if not isinstance(t, dict):
                continue
            _, content_tags = self._tag_library.partition_address_and_content(
                [str(x) for x in (t.get("content_tags") or [])]
            )
            tid = match_or_mint(
                new_address=address,
                new_content_tags=content_tags,
                new_time=game_time,
                existing_clusters=existing_clusters,
            )
            new_frag = ThreadFragment(
                fragment_id=str(uuid.uuid4()),
                layer=self._layer,
                address=address,
                headline=str(t.get("headline", "")).strip(),
                content_tags=content_tags,
                thread_id=tid,
                parent_thread_id=t.get("parent_thread_id"),
                relationship=str(t.get("relationship", "open")),
                created_at=game_time,
            )
            out.append(new_frag)
            # If the new fragment minted (or hit) a thread_id not yet in
            # existing_clusters, fold it in so subsequent threads in this
            # batch can match it (intra-batch clustering).
            existing_fragments.append(new_frag)
            existing_clusters = build_clusters_from_fragments(existing_fragments)
        return out

    def _publish_wes_request(
        self,
        *,
        address: str,
        directive_text: str,
        source_row_id: str,
        game_time: float,
        purpose: str = "unspecified",
        wes_bundle: Optional[Any] = None,
    ) -> None:
        """Publish ``WNS_CALL_WES_REQUESTED``. The event payload includes
        the directive_text + purpose for backward-compat plus the
        serialized :class:`WESContextBundle` (when available) so
        subscribers (the WES orchestrator) can dispatch directly without
        re-querying WNS state.
        """
        try:
            bus = get_event_bus()
            payload: Dict[str, Any] = {
                "layer": self._layer,
                "address": address,
                "directive_text": directive_text,
                "purpose": purpose,
                "source_row_id": source_row_id,
                "game_time": game_time,
            }
            if wes_bundle is not None:
                try:
                    payload["wes_bundle"] = wes_bundle.to_dict()
                except Exception:
                    pass  # never break event publish over a serialization quirk
            bus.publish(
                event_type=WNS_CALL_WES_EVENT,
                data=payload,
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

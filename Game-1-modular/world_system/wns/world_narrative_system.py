"""World Narrative System — facade singleton.

Parallel to :class:`WorldMemorySystem` but for WNS. Coordinates the NL1
ingestor, trigger manager, narrative store, tag library, and the six
per-layer weavers (NL2-NL7).

The facade does NOT call WES. When a weaver decides ``call_wes=true``,
it publishes a ``WNS_CALL_WES_REQUESTED`` event on :class:`GameEventBus`
(see :mod:`nl_weaver`). WES subscribers are the responsibility of a later
phase.
"""

from __future__ import annotations

import os
import uuid
from typing import Any, ClassVar, Dict, List, Optional

from world_system.living_world.backends.backend_manager import BackendManager
from world_system.living_world.infra.context_bundle import ThreadFragment
from world_system.living_world.infra.graceful_degrade import log_degrade
from world_system.wns.narrative_distance_filter import NarrativeDistanceFilter
from world_system.wns.narrative_store import NarrativeRow, NarrativeStore
from world_system.wns.narrative_tag_library import NarrativeTagLibrary
from world_system.wns.nl1_ingestor import NL1Ingestor
from world_system.wns.nl_trigger_manager import NLTriggerManager
from world_system.wns.nl_weaver import NLWeaver, WeaverRunResult


# Per §4.10: separate SQLite file (sibling of world_memory.db).
DEFAULT_WNS_DB_FILENAME = "world_narrative.db"


class WorldNarrativeSystem:
    """Facade for the entire World Narrative System. Singleton."""

    _instance: ClassVar[Optional["WorldNarrativeSystem"]] = None

    WEAVER_LAYERS = (2, 3, 4, 5, 6, 7)

    def __init__(self) -> None:
        self.store: Optional[NarrativeStore] = None
        self.tag_library: Optional[NarrativeTagLibrary] = None
        self.trigger_manager: Optional[NLTriggerManager] = None
        self.ingestor: Optional[NL1Ingestor] = None
        self.distance_filter: Optional[NarrativeDistanceFilter] = None
        self._weavers: Dict[int, NLWeaver] = {}
        self._backend_manager: Optional[BackendManager] = None
        # The WMS→WNS bridge — instantiated only when a WMS facade is
        # supplied to initialize(). Exposed as an attribute so tests
        # and the dev dashboard can read its stats / cascade trigger.
        self.wms_bridge = None  # type: ignore[assignment]
        self._initialized: bool = False
        self._session_id: str = str(uuid.uuid4())[:8]
        self._db_path: Optional[str] = None

    # ── Singleton protocol ───────────────────────────────────────────

    @classmethod
    def get_instance(cls) -> "WorldNarrativeSystem":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        """Test helper. Closes the store if any and drops the singleton."""
        if cls._instance:
            # Disconnect bridge before tearing down — leaving a stale
            # subscriber on the bus would leak across tests.
            try:
                if cls._instance.wms_bridge:
                    cls._instance.wms_bridge.disconnect()
            except Exception:
                pass
            if cls._instance.store:
                cls._instance.store.close()
        cls._instance = None
        NarrativeTagLibrary.reset()

    # ── Initialization ───────────────────────────────────────────────

    def initialize(
        self,
        save_dir: str,
        geo_map_path: Optional[str] = None,
        narrative_config_path: Optional[str] = None,
        narrative_tag_config_path: Optional[str] = None,
        backend_manager: Optional[BackendManager] = None,
        geographic_registry: Optional[Any] = None,
        faction_system: Optional[Any] = None,
        wms_facade: Optional[Any] = None,
        connect_wms_bridge: bool = True,
    ) -> None:
        """Initialize all subsystems.

        Args:
            save_dir: Save-game directory. WNS creates ``world_narrative.db``
                here — sibling of WMS's ``world_memory.db``.
            geo_map_path: Optional path to ``geographic-map.json`` (not
                used directly by WNS; kept in the signature for future
                address normalization / API parity with WMS).
            narrative_config_path: Optional override for
                ``narrative-config.json``.
            narrative_tag_config_path: Optional override for
                ``narrative-tag-definitions.JSON``.
            backend_manager: Optional override; defaults to the singleton.
            geographic_registry: Optional GeographicRegistry-like object
                used by weavers to render multi-tier geographic context
                in their prompts. If ``None``, WNS attempts to look up
                the project singleton; if that's unavailable, weavers
                degrade to address-only context.
            faction_system: Optional FactionSystem used by the deterministic
                AffinityShift resolver. If ``None``, WNS attempts to look up
                the project singleton; if it isn't initialized, the resolver
                runs in ledger-only mode (shifts are recorded but not applied
                to faction/NPC standings).
            wms_facade: Optional WorldMemorySystem facade. When supplied
                (and ``connect_wms_bridge`` is True), WNS constructs a
                :class:`WMSToWNSBridge` and subscribes to
                ``WMS_INTERPRETATION_CREATED`` on the bus. The cascade
                fires WNS weavers from real WMS interpretations.
            connect_wms_bridge: When False, the bridge is constructed
                but not connected — the consumer can call
                ``wns.wms_bridge.connect()`` explicitly. Useful for
                tests that want bridge state without subscription.
        """
        if self._initialized:
            return

        print("[WorldNarrative] Initializing...")

        # Tag library — load from default JSON or override.
        self.tag_library = NarrativeTagLibrary.get_instance()
        if narrative_tag_config_path:
            try:
                self.tag_library.load(narrative_tag_config_path)
            except FileNotFoundError as e:
                log_degrade(
                    subsystem="wns",
                    operation="initialize.tag_library_load",
                    failure_reason=f"FileNotFoundError: {e}",
                    fallback_taken="fallback to default; library may be empty",
                    severity="warning",
                    context={"path": narrative_tag_config_path},
                )

        # Store
        if save_dir == ":memory:":
            db_path = ":memory:"
        else:
            os.makedirs(save_dir, exist_ok=True)
            db_path = os.path.join(save_dir, DEFAULT_WNS_DB_FILENAME)
        self.store = NarrativeStore(db_path=db_path)
        self._db_path = db_path
        print(f"[WorldNarrative] NarrativeStore at {db_path}")

        # Backend
        self._backend_manager = backend_manager or BackendManager.get_instance()
        try:
            # Idempotent — BackendManager.initialize guards.
            self._backend_manager.initialize()
        except Exception as e:
            log_degrade(
                subsystem="wns",
                operation="initialize.backend_manager",
                failure_reason=f"{type(e).__name__}: {e}",
                fallback_taken="backend manager will fail-through to mock at generate time",
                severity="warning",
                context={},
            )

        # Trigger manager + distance filter — config paths
        config_path = narrative_config_path or self._default_narrative_config_path()
        self.trigger_manager = NLTriggerManager()
        self.trigger_manager.load_config(config_path)
        self.distance_filter = NarrativeDistanceFilter()
        self.distance_filter.load_config(config_path)

        # NL1 ingestor
        self.ingestor = NL1Ingestor(store=self.store)

        # Resolve optional dependencies the weavers can use to enrich
        # context (geographic descriptor) and apply emitted directives
        # (AffinityShift). Each is best-effort: weavers degrade
        # gracefully when either is absent.
        resolved_geo = self._resolve_geographic_registry(geographic_registry)
        resolved_factions = self._resolve_faction_system(faction_system)

        # Weavers — one per layer 2..7
        self._weavers.clear()
        for layer in self.WEAVER_LAYERS:
            self._weavers[layer] = NLWeaver(
                layer=layer,
                store=self.store,
                tag_library=self.tag_library,
                backend_manager=self._backend_manager,
                distance_filter=self.distance_filter,
                geographic_registry=resolved_geo,
                faction_system=resolved_factions,
            )

        # Wire the WMS→WNS bridge if a WMS facade was supplied. The
        # bridge takes ownership of the cascade trigger and the
        # ``WMS_INTERPRETATION_CREATED`` subscription.
        if wms_facade is not None:
            cascade_threshold, wms_char_budget = self._read_bridge_config(
                config_path
            )
            self._build_wms_bridge(
                wms_facade=wms_facade,
                geographic_registry=resolved_geo,
                connect=connect_wms_bridge,
                cascade_threshold=cascade_threshold,
                wms_char_budget=wms_char_budget,
            )

        self._initialized = True
        bridge_status = (
            "connected" if (self.wms_bridge and self.wms_bridge.connected)
            else ("constructed (not connected)" if self.wms_bridge else "absent")
        )
        print(
            f"[WorldNarrative] Initialized — session {self._session_id}, "
            f"{len(self._weavers)} weavers, "
            f"{self.store.stats['total_rows']} rows in store; "
            f"WMS bridge: {bridge_status}"
        )

    @staticmethod
    def _read_bridge_config(config_path: str) -> tuple:
        """Pull (cascade_threshold, wms_char_budget) from narrative-config.

        Returns sensible defaults on any failure — the bridge / cascade
        ship safe defaults internally, this is just an override pipe.
        """
        from world_system.wns.cascade_trigger import DEFAULT_THRESHOLD
        from world_system.wns.wms_context_builder import DEFAULT_CHAR_BUDGET
        threshold = DEFAULT_THRESHOLD
        char_budget = DEFAULT_CHAR_BUDGET
        try:
            import json as _json
            with open(config_path, "r", encoding="utf-8") as f:
                data = _json.load(f)
            cascade_block = data.get("cascade", {}) or {}
            wms_block = data.get("wms_context", {}) or {}
            t = cascade_block.get("threshold")
            if isinstance(t, int) and t >= 1:
                threshold = t
            cb = wms_block.get("char_budget_per_fire")
            if isinstance(cb, int) and cb >= 0:
                char_budget = cb
        except Exception as e:
            log_degrade(
                subsystem="wns",
                operation="_read_bridge_config",
                failure_reason=f"{type(e).__name__}: {e}",
                fallback_taken="using built-in defaults for cascade threshold + WMS char budget",
                severity="info",
                context={"config_path": config_path},
            )
        return threshold, char_budget

    def _build_wms_bridge(
        self,
        *,
        wms_facade: Any,
        geographic_registry: Optional[Any],
        connect: bool,
        cascade_threshold: int = 3,
        wms_char_budget: int = 600,
    ) -> None:
        """Construct + optionally connect the WMS→WNS bridge.

        Defensive on every step — if the bridge can't import, the
        WMS facade lacks ``event_store``, or no geographic registry
        is available, the bridge is left as ``None`` and a degrade
        is logged. WNS continues to function (manual ``run_weaver``
        calls still work); the bridge is purely additive.
        """
        try:
            from world_system.wns.wms_to_wns_bridge import WMSToWNSBridge
        except Exception as e:
            log_degrade(
                subsystem="wns",
                operation="initialize.wms_bridge_import",
                failure_reason=f"{type(e).__name__}: {e}",
                fallback_taken="bridge disabled; WNS will not fire from WMS events",
                severity="warning",
                context={},
            )
            return

        event_store = getattr(wms_facade, "event_store", None)
        if event_store is None:
            log_degrade(
                subsystem="wns",
                operation="initialize.wms_bridge_event_store",
                failure_reason="wms_facade.event_store is None",
                fallback_taken="bridge disabled; WMS facade not initialized?",
                severity="warning",
                context={},
            )
            return
        if geographic_registry is None:
            log_degrade(
                subsystem="wns",
                operation="initialize.wms_bridge_geo_registry",
                failure_reason="GeographicRegistry unavailable",
                fallback_taken="bridge disabled; cannot walk address parents",
                severity="warning",
                context={},
            )
            return

        try:
            self.wms_bridge = WMSToWNSBridge(
                wns=self,
                event_store=event_store,
                geographic_registry=geographic_registry,
                threshold=cascade_threshold,
                wms_char_budget=wms_char_budget,
            )
            if connect:
                self.wms_bridge.connect()
        except Exception as e:
            self.wms_bridge = None
            log_degrade(
                subsystem="wns",
                operation="initialize.wms_bridge_construct",
                failure_reason=f"{type(e).__name__}: {e}",
                fallback_taken="bridge disabled; WNS will not fire from WMS events",
                severity="warning",
                context={},
            )

    @staticmethod
    def _default_narrative_config_path() -> str:
        here = os.path.dirname(os.path.abspath(__file__))
        return os.path.normpath(
            os.path.join(here, os.pardir, "config", "narrative-config.json")
        )

    @staticmethod
    def _resolve_geographic_registry(override: Optional[Any]) -> Optional[Any]:
        """Return the override if provided, else the project singleton.

        Falls back to ``None`` (and a degrade log) on any failure, so
        weaver construction never blocks on geographic context being
        ready. ``build_geographic_context`` already handles None and
        empty registries gracefully.
        """
        if override is not None:
            return override
        try:
            from world_system.world_memory.geographic_registry import (
                GeographicRegistry,
            )
            return GeographicRegistry.get_instance()
        except Exception as e:
            log_degrade(
                subsystem="wns",
                operation="initialize.resolve_geographic_registry",
                failure_reason=f"{type(e).__name__}: {e}",
                fallback_taken="weavers run without geographic context",
                severity="info",
                context={},
            )
            return None

    @staticmethod
    def _resolve_faction_system(override: Optional[Any]) -> Optional[Any]:
        """Return the override if provided, else the project singleton —
        but only if it is initialized.

        Passing an uninitialized FactionSystem to AffinityResolver would
        cause shift-application to hit empty SQLite tables and silently
        no-op. The resolver's ledger-only path (``faction_system=None``)
        is the correct behavior in that case.
        """
        if override is not None:
            return override
        try:
            from world_system.living_world.factions.faction_system import (
                FactionSystem,
            )
            candidate = FactionSystem.get_instance()
            if getattr(candidate, "_initialized", False):
                return candidate
            return None
        except Exception as e:
            log_degrade(
                subsystem="wns",
                operation="initialize.resolve_faction_system",
                failure_reason=f"{type(e).__name__}: {e}",
                fallback_taken="AffinityResolver runs in ledger-only mode",
                severity="info",
                context={},
            )
            return None

    # ── Public API ───────────────────────────────────────────────────

    def ingest_dialogue(
        self,
        npc_id: str,
        speech_bank: Dict[str, Any],
        address: str,
        game_time: Optional[float] = None,
    ) -> List[NarrativeRow]:
        """Capture an NPC speech-bank into NL1 rows.

        See :meth:`NL1Ingestor.ingest_speech_bank`. After capture, the
        NL2 trigger bucket for ``address`` is advanced once per mention
        (so lots of mentions at a locality fire NL2 faster) — this is the
        canonical way NL1 drives the weaving pipeline.
        """
        if not self._initialized or not self.ingestor or not self.trigger_manager:
            return []
        rows = self.ingestor.ingest_speech_bank(
            npc_id=npc_id,
            speech_bank_json=speech_bank,
            address=address,
            game_time=game_time,
        )
        for _ in rows:
            # Each mention advances NL2's bucket at this locality.
            self.trigger_manager.note_event(layer=2, address=address)
        return rows

    def maybe_weave(
        self,
        layer: int,
        address: str,
        parent_narrative: str = "",
        threads_in_scope: Optional[List[ThreadFragment]] = None,
        game_time: Optional[float] = None,
    ) -> Optional[WeaverRunResult]:
        """Check the trigger, and if it fires, run the layer's weaver.

        Returns the :class:`WeaverRunResult` on fire, ``None`` otherwise.
        """
        if not self._initialized or not self.trigger_manager:
            return None
        if not self.trigger_manager.should_run(layer=layer, address=address):
            return None
        weaver = self._weavers.get(layer)
        if weaver is None:
            return None
        return weaver.run_weaving(
            address=address,
            parent_narrative=parent_narrative,
            threads_in_scope=threads_in_scope,
            game_time=game_time,
        )

    def run_weaver(
        self,
        layer: int,
        address: str,
        lower_narratives: Optional[List[NarrativeRow]] = None,
        parent_narrative: str = "",
        threads_in_scope: Optional[List[ThreadFragment]] = None,
        game_time: Optional[float] = None,
        parent_address: str = "",
        grandparent_address: str = "",
        wms_brief: Optional[str] = None,
    ) -> Optional[WeaverRunResult]:
        """Run a weaver regardless of trigger state. Useful for testing
        and for external callers driving the pipeline explicitly.

        ``parent_address`` and ``grandparent_address`` enable the
        WeaverContext's above-cascading slots (N+1 / N+2 narrative).
        ``wms_brief`` is a pre-rendered WMS context slice (see
        :func:`world_system.wns.wms_context_builder.build_wms_brief`)
        injected at the ``${wms_context}`` placeholder. The bridge
        passes both during cascade fires; tests / direct callers can
        omit them.
        """
        if not self._initialized:
            return None
        weaver = self._weavers.get(layer)
        if weaver is None:
            return None
        return weaver.run_weaving(
            address=address,
            lower_narratives=lower_narratives,
            parent_narrative=parent_narrative,
            threads_in_scope=threads_in_scope,
            game_time=game_time,
            parent_address=parent_address or None,
            grandparent_address=grandparent_address or None,
            wms_brief=wms_brief,
        )

    def query_threads(
        self,
        address: str,
        layer: Optional[int] = None,
    ) -> List[ThreadFragment]:
        """Return open thread fragments at ``address`` (and optionally at
        a specific layer). Reconstructed from each layer's rows'
        ``payload.threads``."""
        if not self._initialized or not self.store:
            return []
        layers = [layer] if layer is not None else list(self.WEAVER_LAYERS)
        out: List[ThreadFragment] = []
        for ly in layers:
            rows = self.store.query_by_address(ly, address, limit=100)
            for r in rows:
                for t in r.payload.get("threads", []) or []:
                    try:
                        out.append(ThreadFragment.from_dict(t))
                    except (KeyError, TypeError, ValueError):
                        continue
        return out

    def get_layer_summary(self, layer: int, address: str) -> Optional[str]:
        """Return the most recent narrative string at ``(layer, address)``."""
        if not self._initialized or not self.store:
            return None
        rows = self.store.query_by_address(layer, address, limit=1)
        if not rows:
            return None
        return rows[0].narrative

    # ── Shutdown ─────────────────────────────────────────────────────

    def shutdown(self) -> None:
        # Drop the bus subscription first so no late events arrive
        # after the store is closed.
        if self.wms_bridge:
            try:
                self.wms_bridge.disconnect()
            except Exception:
                pass
        if self.store:
            self.store.close()
        self._initialized = False

    # ── Debug / Stats ────────────────────────────────────────────────

    @property
    def stats(self) -> Dict[str, Any]:
        if not self._initialized:
            return {"initialized": False}
        return {
            "initialized": True,
            "session_id": self._session_id,
            "db_path": self._db_path,
            "store": self.store.stats if self.store else None,
            "tag_library": self.tag_library.stats if self.tag_library else None,
            "trigger_manager": self.trigger_manager.stats if self.trigger_manager else None,
            "distance_filter": self.distance_filter.stats if self.distance_filter else None,
            "weavers": sorted(self._weavers.keys()),
        }

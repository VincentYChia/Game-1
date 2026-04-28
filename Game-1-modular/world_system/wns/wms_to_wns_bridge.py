"""WMS → WNS bridge — drive the cascade from real game events.

Connects three systems:

- **WMS** (event source): publishes ``WMS_INTERPRETATION_CREATED`` on
  :class:`GameEventBus` whenever :class:`WorldInterpreter` records a
  new Layer-2 interpretation.
- **CascadeTriggerManager** (counter): per-layer per-address counters
  with the ``every-N-of-layer-below-at-common-ancestor`` rule
  (default N=3, geometric progression from leaf to NL7).
- **WNS** (sink): when the cascade fires, the bridge calls
  ``WorldNarrativeSystem.run_weaver`` at the fire's address, injecting
  a char-capped WMS context slice so the weaver has factual grounding.

Lifecycle:

    bridge = WMSToWNSBridge(
        wns=WorldNarrativeSystem.get_instance(),
        event_store=wms.event_store,
        geographic_registry=GeographicRegistry.get_instance(),
    )
    bridge.connect()    # subscribe to bus
    ...                 # game runs
    bridge.disconnect() # tear down on shutdown

Idempotency: the bridge keeps a bounded set of seen interpretation IDs
so accidental redelivery (replay, reconnection) doesn't double-count.

Failure model: every external call (bus subscribe, WNS run, registry
walk) is wrapped — the bridge never crashes the game; failures degrade
the cascade silently and are surfaced via :attr:`stats`.
"""

from __future__ import annotations

import threading
from collections import deque
from typing import Any, Callable, Deque, Optional, Set

from world_system.living_world.infra.graceful_degrade import log_degrade
from world_system.wes.observability_runtime import (
    EVT_CASCADE_FIRED,
    EVT_WMS_EVENT_RECEIVED,
    obs_record,
)
from world_system.wns.cascade_trigger import (
    CascadeTriggerManager,
    DEFAULT_THRESHOLD,
    WEAVER_LAYERS,
)
from world_system.wns.wms_context_builder import (
    DEFAULT_CHAR_BUDGET,
    build_wms_brief,
)


# Bus topic published by WorldInterpreter._publish_interpretation_created.
WMS_INTERPRETATION_TOPIC: str = "WMS_INTERPRETATION_CREATED"

# Bound on the seen-interpretation-id ring buffer. Plenty for a session;
# old IDs falling off don't matter — the worst case is double-counting
# a stale interpretation.
DEFAULT_SEEN_RING: int = 4096


class WMSToWNSBridge:
    """Pumps WMS interpretation events into the WNS cascade trigger."""

    def __init__(
        self,
        wns: Any,
        event_store: Any,
        geographic_registry: Any,
        *,
        threshold: int = DEFAULT_THRESHOLD,
        wms_char_budget: int = DEFAULT_CHAR_BUDGET,
        seen_ring_size: int = DEFAULT_SEEN_RING,
    ) -> None:
        self._wns = wns
        self._event_store = event_store
        self._geo = geographic_registry
        self._char_budget = int(wms_char_budget)
        self._connected: bool = False
        self._lock = threading.RLock()

        # Idempotency ring — bounded set + insertion-order queue
        self._seen_ids: Set[str] = set()
        self._seen_order: Deque[str] = deque(maxlen=int(seen_ring_size))

        # Cascade trigger — wraps geographic_registry's parent walk
        self._cascade = CascadeTriggerManager(
            parent_address_resolver=self._safe_parent_address,
            fire_callback=self._on_cascade_fire,
            threshold=int(threshold),
        )

        # Observability counters (additive to CascadeTriggerManager.stats)
        self._events_received: int = 0
        self._events_processed: int = 0
        self._events_skipped_duplicate: int = 0
        self._events_skipped_no_locality: int = 0
        self._weaver_run_failures: int = 0
        self._address_resolution_failures: int = 0

    # ── Lifecycle ────────────────────────────────────────────────────

    def connect(self) -> None:
        """Subscribe to ``WMS_INTERPRETATION_CREATED`` on GameEventBus.

        Idempotent. Failure to import / subscribe degrades to a no-op
        (bridge stays off); the WMS interpretation flow continues to
        write to SQLite but no cascade triggers happen.
        """
        with self._lock:
            if self._connected:
                return
            try:
                from events.event_bus import get_event_bus
                bus = get_event_bus()
                bus.subscribe(WMS_INTERPRETATION_TOPIC, self._on_event)
                self._connected = True
            except Exception as e:
                log_degrade(
                    subsystem="wns_bridge",
                    operation="connect",
                    failure_reason=f"{type(e).__name__}: {e}",
                    fallback_taken="bridge disabled; WNS will not fire from WMS events",
                    severity="warning",
                    context={},
                )

    def disconnect(self) -> None:
        """Unsubscribe from the bus and reset internal state.

        Idempotent. If unsubscribe isn't supported by the bus, the
        ``_connected`` flag still flips so the handler becomes a
        no-op even if it's invoked stale.
        """
        with self._lock:
            if not self._connected:
                return
            try:
                from events.event_bus import get_event_bus
                bus = get_event_bus()
                # Some bus implementations don't expose unsubscribe;
                # we tolerate that — handler short-circuits via the
                # ``_connected`` flag check.
                unsub = getattr(bus, "unsubscribe", None)
                if callable(unsub):
                    try:
                        unsub(WMS_INTERPRETATION_TOPIC, self._on_event)
                    except Exception:
                        pass
            except Exception:
                pass
            self._connected = False

    # ── Event ingestion ──────────────────────────────────────────────

    def _on_event(self, event_or_data: Any) -> None:
        """Handle one ``WMS_INTERPRETATION_CREATED`` delivery.

        The real :class:`GameEventBus` hands subscribers a
        :class:`GameEvent` object (with ``.data`` carrying the payload
        dict). Some test buses pass the dict directly. We accept both
        shapes and unwrap to the inner dict.
        """
        # Unwrap GameEvent → dict if needed.
        event_data = event_or_data
        if not isinstance(event_or_data, dict):
            inner = getattr(event_or_data, "data", None)
            if isinstance(inner, dict):
                event_data = inner
        with self._lock:
            if not self._connected:
                return
            self._events_received += 1

            interp_id = self._extract_id(event_data)
            if interp_id and interp_id in self._seen_ids:
                self._events_skipped_duplicate += 1
                return

            locality_ids = self._extract_locality_ids(event_data)
            if not locality_ids:
                self._events_skipped_no_locality += 1
                # Mark seen so we don't keep counting a no-op event.
                self._mark_seen(interp_id)
                return

            # Drive the cascade once per affected locality. Multi-
            # locality interpretations advance multiple NL2 counters.
            for locality_id in locality_ids:
                if not locality_id:
                    continue
                try:
                    self._cascade.note_event(locality_id)
                except Exception as e:
                    log_degrade(
                        subsystem="wns_bridge",
                        operation="cascade.note_event",
                        failure_reason=f"{type(e).__name__}: {e}",
                        fallback_taken="event dropped; cascade unaffected for this locality",
                        severity="warning",
                        context={"locality_id": locality_id},
                    )

            self._events_processed += 1
            self._mark_seen(interp_id)
            obs_record(
                EVT_WMS_EVENT_RECEIVED,
                "WMS interpretation routed to cascade",
                interp_id=interp_id or "?",
                localities=len(locality_ids),
            )

    # ── Cascade fire callback (runs the weaver) ──────────────────────

    def _on_cascade_fire(self, layer: int, address: str) -> None:
        """Run the layer's weaver at ``address`` with WMS context attached.

        Called by CascadeTriggerManager when a counter hits the
        threshold. Wraps the weaver call so failures are isolated —
        the cascade still advances (per CascadeTriggerManager contract)
        but a failed weaver invocation is logged and counted.
        """
        if layer not in WEAVER_LAYERS:
            return
        wms_brief = ""
        try:
            wms_brief = build_wms_brief(
                firing_address=address,
                event_store=self._event_store,
                geographic_registry=self._geo,
                char_budget=self._char_budget,
            )
        except Exception as e:
            log_degrade(
                subsystem="wns_bridge",
                operation="build_wms_brief",
                failure_reason=f"{type(e).__name__}: {e}",
                fallback_taken="weaver runs without WMS slice",
                severity="warning",
                context={"layer": layer, "address": address},
            )

        try:
            # Resolve ancestors once for above_* cascading context.
            parent_address = self._safe_parent_address(address)
            grandparent_address = (
                self._safe_parent_address(parent_address) if parent_address else None
            )
            obs_record(
                EVT_CASCADE_FIRED,
                f"NL{layer} weaver firing",
                layer=layer,
                address=address,
                wms_brief_chars=len(wms_brief or ""),
            )
            self._wns.run_weaver(
                layer=layer,
                address=address,
                parent_address=parent_address or "",
                grandparent_address=grandparent_address or "",
                wms_brief=wms_brief or None,
            )
        except Exception as e:
            self._weaver_run_failures += 1
            log_degrade(
                subsystem="wns_bridge",
                operation=f"wns.run_weaver(layer={layer})",
                failure_reason=f"{type(e).__name__}: {e}",
                fallback_taken="cascade still advances; no narrative produced this fire",
                severity="warning",
                context={"layer": layer, "address": address},
            )

    # ── Helpers ──────────────────────────────────────────────────────

    def _safe_parent_address(self, address: str) -> Optional[str]:
        """Wrap GeographicRegistry.get_parent_address with metrics."""
        if not self._geo or not address:
            return None
        try:
            parent = self._geo.get_parent_address(address)
        except Exception:
            self._address_resolution_failures += 1
            return None
        return parent

    @staticmethod
    def _extract_id(event_data: Any) -> Optional[str]:
        if isinstance(event_data, dict):
            v = event_data.get("interpretation_id")
            if isinstance(v, str):
                return v
        return None

    @staticmethod
    def _extract_locality_ids(event_data: Any) -> list:
        if not isinstance(event_data, dict):
            return []
        raw = event_data.get("affected_locality_ids", [])
        if not isinstance(raw, (list, tuple)):
            return []
        return [str(x) for x in raw if x]

    def _mark_seen(self, interp_id: Optional[str]) -> None:
        if not interp_id:
            return
        # If the deque is full, the oldest ID is evicted automatically;
        # mirror that eviction in the set so the set stays in sync.
        if len(self._seen_order) == self._seen_order.maxlen:
            evicted = self._seen_order[0]
            self._seen_ids.discard(evicted)
        self._seen_order.append(interp_id)
        self._seen_ids.add(interp_id)

    # ── Observability ────────────────────────────────────────────────

    @property
    def cascade(self) -> CascadeTriggerManager:
        """Direct access to the cascade trigger (for tests / dev tools)."""
        return self._cascade

    @property
    def connected(self) -> bool:
        return self._connected

    @property
    def stats(self) -> dict:
        with self._lock:
            return {
                "connected": self._connected,
                "events_received": self._events_received,
                "events_processed": self._events_processed,
                "events_skipped_duplicate": self._events_skipped_duplicate,
                "events_skipped_no_locality": self._events_skipped_no_locality,
                "weaver_run_failures": self._weaver_run_failures,
                "address_resolution_failures": self._address_resolution_failures,
                "cascade": self._cascade.stats,
                "seen_ring_capacity": self._seen_order.maxlen,
                "seen_ring_size": len(self._seen_order),
            }


__all__ = ["WMSToWNSBridge", "WMS_INTERPRETATION_TOPIC", "DEFAULT_SEEN_RING"]

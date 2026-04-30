"""Cascade trigger — every-N-of-layer-below at common ancestor (v2).

Replaces the earlier per-layer-N model (5/5/8/12/15/20 placeholders in
``narrative-config.json``) with a uniform geometric cascade:

    NL2 fires at locality X       when N WMS interpretations land at X.
    NL3 fires at district Y       when N NL2 fires occur within Y.
    NL4 fires at region Z         when N NL3 fires occur within Z.
    NL5 fires at province P       when N NL4 fires occur within P.
    NL6 fires at nation R         when N NL5 fires occur within R.
    NL7 fires at world W          when N NL6 fires occur within W.

Default N = 3 (per design discussion 2026-04-26). With N=3 a single
NL7 fire requires roughly 3^6 = 729 leaf events under the same world,
which gives the upper layers natural rarity without per-layer tuning.

The trigger is **address-tier aware**: each layer's counters are keyed
by the address tier appropriate for that layer (locality for NL2,
district for NL3, etc.). Walking from a fired layer's address up to the
parent layer's address is delegated to a ``parent_address_resolver``
callable so this module stays decoupled from
:class:`GeographicRegistry`. The default resolver in production wraps
``GeographicRegistry.get_parent_address``.

The cascade is **synchronous and recursive within a single call** but
each fire is mediated through a callback so the consumer can introduce
async/queueing if desired. The trigger never calls weavers directly —
it only signals the consumer.

Thread safety: all mutating methods take an internal lock. The cascade
recursion is bounded by ``MAX_CASCADE_DEPTH`` (6 — one per layer above
NL2) as a defensive guard against any accidental cycle in the parent
resolver.
"""

from __future__ import annotations

import threading
from typing import Callable, Dict, List, Optional, Tuple

# ── Defaults / invariants ─────────────────────────────────────────────

# N — uniform threshold per layer per address. Designer-tunable via
# ``narrative-config.json:cascade.threshold``. Three is the design
# default (see module docstring).
DEFAULT_THRESHOLD: int = 3

# Hard cap on cascade recursion depth. Bounded by the 6-tier hierarchy
# (NL2→NL3→...→NL7 = 5 hops, plus a safety margin).
MAX_CASCADE_DEPTH: int = 6

# Layers whose triggers we maintain.
WEAVER_LAYERS: Tuple[int, ...] = (2, 3, 4, 5, 6, 7)


# Type alias: signature of the address-walk callback.
# Given a fired layer's address (e.g. ``"locality:moors_falls"``),
# return the address one tier up (e.g. ``"district:falls_district"``)
# or ``None`` at the top of the hierarchy / on lookup failure.
ParentAddressResolver = Callable[[str], Optional[str]]

# Type alias: signature of the fire callback.
#   on_fire(layer, address) — invoked when a layer's counter at address
#   reaches the threshold. Called BEFORE the cascade increments the
#   parent counter, so consumers can synchronously observe the fire.
FireCallback = Callable[[int, str], None]


class CascadeTriggerManager:
    """Counts events per (layer, address) and fires when a counter hits N.

    Construction takes the parent-address resolver and (optionally) a
    fire callback. Counters are zeroed on construction; tests can call
    :meth:`reset` to clear state.

    Use :meth:`note_event` to feed leaf events (NL2 input). The
    cascade upward — NL2 fire → NL3 counter → NL3 fire → NL4 counter
    → ... — happens automatically inside :meth:`note_event` via
    :meth:`note_layer_fired`.
    """

    def __init__(
        self,
        parent_address_resolver: ParentAddressResolver,
        fire_callback: Optional[FireCallback] = None,
        threshold: int = DEFAULT_THRESHOLD,
    ) -> None:
        if threshold < 1:
            raise ValueError(
                f"CascadeTriggerManager: threshold must be >=1, got {threshold}"
            )
        self._resolver = parent_address_resolver
        self._fire_callback: Optional[FireCallback] = fire_callback
        self._threshold = int(threshold)
        # (layer, address) -> count toward the next fire
        self._counts: Dict[Tuple[int, str], int] = {}
        # Total fires per layer (observability; never reset by cascade)
        self._fires_total: Dict[int, int] = {ly: 0 for ly in WEAVER_LAYERS}
        # Total events ingested at the leaf (NL2 input)
        self._events_ingested: int = 0
        # Number of times the parent resolver returned None mid-cascade
        # (top-of-hierarchy hit, or address resolution failed)
        self._cascade_terminations: int = 0
        # Number of times the cascade safety cap was hit
        self._cascade_overruns: int = 0
        self._lock = threading.RLock()

    # ── Configuration ────────────────────────────────────────────────

    def set_fire_callback(self, callback: FireCallback) -> None:
        """Install the fire callback. Idempotent — replaces any existing."""
        with self._lock:
            self._fire_callback = callback

    @property
    def threshold(self) -> int:
        return self._threshold

    # ── Ingestion ────────────────────────────────────────────────────

    def note_event(self, locality_id: str) -> None:
        """One leaf event arrived at ``locality_id``.

        Increments the NL2 counter for ``locality:{locality_id}`` and
        cascades up if it hits the threshold. ``locality_id`` is the
        bare ID — the ``locality:`` prefix is added internally so
        callers don't have to remember the convention.

        No-ops on empty / falsy ``locality_id`` (events with no known
        locality can't drive the cascade).
        """
        if not locality_id:
            return
        with self._lock:
            self._events_ingested += 1
            self._increment_and_cascade(
                layer=2,
                address=f"locality:{locality_id}",
                cascade_depth=0,
            )

    def note_layer_fired(self, layer: int, address: str) -> None:
        """A layer just produced an output at ``address``. Drive the
        cascade by incrementing the layer-above counter at the parent
        address (resolved via the registered walker).

        Public for callers that want to feed cascade signals from sources
        other than ``note_event`` — e.g. NL1 ingestion or a future
        WMS L5+ trigger. Re-entrant; guards against infinite recursion
        via :data:`MAX_CASCADE_DEPTH`.
        """
        with self._lock:
            self._cascade_from(
                fired_layer=layer,
                fired_address=address,
                cascade_depth=0,
            )

    # ── Inspection / observability ────────────────────────────────────

    def get_count(self, layer: int, address: str) -> int:
        """Current pending count for ``(layer, address)``. Resets to 0
        on each fire."""
        with self._lock:
            return self._counts.get((layer, address), 0)

    @property
    def stats(self) -> Dict[str, object]:
        with self._lock:
            return {
                "threshold": self._threshold,
                "events_ingested": self._events_ingested,
                "fires_total_by_layer": dict(self._fires_total),
                "active_counters": len(self._counts),
                "cascade_terminations": self._cascade_terminations,
                "cascade_overruns": self._cascade_overruns,
            }

    def pending_counters(self) -> List[Tuple[int, str, int]]:
        """Snapshot of every (layer, address, count) that hasn't fired
        yet. Useful for the dev dashboard. Sorted by layer ascending."""
        with self._lock:
            out = [(ly, addr, n) for (ly, addr), n in self._counts.items() if n > 0]
            out.sort(key=lambda t: (t[0], t[1]))
            return out

    def reset(self) -> None:
        """Clear all counters and fire history. Test helper."""
        with self._lock:
            self._counts.clear()
            self._fires_total = {ly: 0 for ly in WEAVER_LAYERS}
            self._events_ingested = 0
            self._cascade_terminations = 0
            self._cascade_overruns = 0

    # ── Internal cascade machinery ───────────────────────────────────

    def _increment_and_cascade(
        self,
        layer: int,
        address: str,
        cascade_depth: int,
    ) -> None:
        """Increment counter, fire if threshold hit, cascade if fired.

        Caller must hold the lock.
        """
        if cascade_depth > MAX_CASCADE_DEPTH:
            self._cascade_overruns += 1
            return
        if layer not in WEAVER_LAYERS:
            # Anything above NL7 is out of bounds — silently drop.
            return

        key = (layer, address)
        new_count = self._counts.get(key, 0) + 1
        if new_count < self._threshold:
            self._counts[key] = new_count
            return

        # Threshold reached — clear and fire.
        self._counts[key] = 0
        self._fires_total[layer] = self._fires_total.get(layer, 0) + 1

        if self._fire_callback is not None:
            try:
                self._fire_callback(layer, address)
            except Exception:
                # Consumer bug should not poison the cascade. Surface
                # via stats; the upstream subsystem will see no
                # narrative produced.
                # (We deliberately do not log_degrade here to avoid
                # an import-time dependency cycle; the consumer is
                # expected to wrap its own work in try/except.)
                pass

        # Cascade up — even if the callback raised. The trigger's job
        # is purely accounting; whether the weaver succeeded is the
        # consumer's concern.
        self._cascade_from(
            fired_layer=layer,
            fired_address=address,
            cascade_depth=cascade_depth + 1,
        )

    def _cascade_from(
        self,
        fired_layer: int,
        fired_address: str,
        cascade_depth: int,
    ) -> None:
        """Walk one tier up and increment the parent counter.

        Caller must hold the lock.
        """
        if fired_layer >= max(WEAVER_LAYERS):
            # NL7 has no parent. Cascade naturally terminates.
            self._cascade_terminations += 1
            return
        try:
            parent_address = self._resolver(fired_address)
        except Exception:
            parent_address = None
        if parent_address is None:
            self._cascade_terminations += 1
            return
        self._increment_and_cascade(
            layer=fired_layer + 1,
            address=parent_address,
            cascade_depth=cascade_depth,
        )


__all__ = [
    "CascadeTriggerManager",
    "DEFAULT_THRESHOLD",
    "MAX_CASCADE_DEPTH",
    "WEAVER_LAYERS",
    "ParentAddressResolver",
    "FireCallback",
]

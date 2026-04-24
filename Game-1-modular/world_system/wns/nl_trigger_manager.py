"""NL Trigger Manager — every-N-events-per-layer-per-address buckets.

Parallel to ``world_memory.trigger_manager.TriggerManager`` but tracks
**narrative** buckets: one per ``(layer, address)`` key. Lower layers fire
more often; higher layers accumulate from wider scope and fire less often.

N values come from ``narrative-config.json``. See PLACEHOLDER_LEDGER.md §4.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Any, Dict, Optional, Tuple


# Placeholder defaults if the config JSON is missing. See §4 of the ledger.
_DEFAULT_N_PER_LAYER: Dict[int, int] = {
    2: 5,
    3: 5,
    4: 8,
    5: 12,
    6: 15,
    7: 20,
}


@dataclass
class _BucketState:
    """One trigger bucket for a ``(layer, address)`` key."""

    count: int = 0
    fires: int = 0  # number of times this bucket has fired


class NLTriggerManager:
    """Per-layer per-address every-N-events trigger manager.

    Usage::

        mgr = NLTriggerManager()
        mgr.load_config("world_system/config/narrative-config.json")

        if mgr.should_run(layer=2, address="locality:tarmouth_copperdocks"):
            # NL2 weaving fires at this address
            ...

    Internally ``should_run`` **increments** the bucket before checking
    whether its count equals N (and resets to 0 on fire). This means a
    caller that calls ``should_run`` for every new lower-layer event gets
    exactly one fire per N events, as designed.
    """

    def __init__(self) -> None:
        self._n_per_layer: Dict[int, int] = dict(_DEFAULT_N_PER_LAYER)
        self._buckets: Dict[Tuple[int, str], _BucketState] = {}
        self._source_path: Optional[str] = None

    # ── Config ───────────────────────────────────────────────────────

    def load_config(self, config_path: str) -> None:
        """Load N values from ``narrative-config.json``.

        Missing entries fall back to placeholder defaults.
        """
        if not os.path.exists(config_path):
            # Keep defaults; record for observability.
            self._source_path = None
            return
        with open(config_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        triggers = data.get("triggers", {})
        # Map "nlN" -> layer int -> pull any int-valued key under it.
        for key, block in triggers.items():
            if not key.startswith("nl"):
                continue
            try:
                layer = int(key[2:])
            except ValueError:
                continue
            if not isinstance(block, dict):
                continue
            # Pick the first int value (works for events_per_locality,
            # events_per_district, events_world, etc.). Ignore
            # "description".
            for sub_key, sub_val in block.items():
                if sub_key == "description":
                    continue
                if isinstance(sub_val, int) and sub_val > 0:
                    self._n_per_layer[layer] = sub_val
                    break
        self._source_path = config_path

    def n_for_layer(self, layer: int) -> int:
        return self._n_per_layer.get(layer, _DEFAULT_N_PER_LAYER.get(layer, 5))

    # ── Counting ─────────────────────────────────────────────────────

    def note_event(self, layer: int, address: str) -> int:
        """Increment the ``(layer, address)`` bucket without firing. Returns
        the post-increment count. Useful for testing and for external
        code that wants to advance a bucket deterministically.
        """
        key = (int(layer), address)
        bucket = self._buckets.setdefault(key, _BucketState())
        bucket.count += 1
        return bucket.count

    def should_run(self, layer: int, address: str) -> bool:
        """Advance the ``(layer, address)`` bucket by 1 and return True iff
        the bucket reached N and fires this tick. On fire the bucket
        resets to 0 and ``fires`` increments.

        This is the canonical entry point for weavers. Callers typically
        invoke it **for each new lower-layer event** at ``address``.
        """
        key = (int(layer), address)
        bucket = self._buckets.setdefault(key, _BucketState())
        bucket.count += 1
        n = self.n_for_layer(layer)
        if bucket.count >= n:
            bucket.count = 0
            bucket.fires += 1
            return True
        return False

    def peek(self, layer: int, address: str) -> Dict[str, int]:
        bucket = self._buckets.get((int(layer), address))
        if bucket is None:
            return {"count": 0, "fires": 0, "n": self.n_for_layer(layer)}
        return {
            "count": bucket.count,
            "fires": bucket.fires,
            "n": self.n_for_layer(layer),
        }

    # ── State / Debug ────────────────────────────────────────────────

    def reset_all(self) -> None:
        self._buckets.clear()

    @property
    def stats(self) -> Dict[str, Any]:
        return {
            "source_path": self._source_path,
            "n_per_layer": dict(self._n_per_layer),
            "active_buckets": len(self._buckets),
            "total_fires": sum(b.fires for b in self._buckets.values()),
        }

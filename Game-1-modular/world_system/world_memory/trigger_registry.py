"""Centralized per-key trigger tracking for WMS layer escalation.

Manages counters that accumulate per logical key (province_id, district_id,
faction_id, etc.) and fire when a threshold is reached. After firing, the
counter resets to zero.

Designed to be reusable across layers:
- Layer 3→4: key=province_id, counting Layer 3 events per province
- Layer 4→5: key=realm_id, counting Layer 4 events per realm
- Any future trigger: register a TriggerBucket and go

Usage:
    registry = TriggerRegistry()
    registry.register_bucket("layer4_provinces", threshold=3)
    registry.increment("layer4_provinces", "nation_1")
    registry.increment("layer4_provinces", "nation_1")
    registry.increment("layer4_provinces", "nation_1")
    fired = registry.get_and_clear_fired("layer4_provinces")
    # fired == ["nation_1"]
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, ClassVar, Dict, List, Optional, Set


@dataclass
class TriggerBucket:
    """A named collection of per-key counters with a shared threshold.

    Attributes:
        name: Unique bucket identifier (e.g., "layer4_provinces").
        threshold: Number of increments before a key fires.
        counters: Current count per key.
        fired: Keys that have reached the threshold since last check.
    """
    name: str
    threshold: int
    counters: Dict[str, int] = field(default_factory=dict)
    fired: Set[str] = field(default_factory=set)

    def increment(self, key: str, amount: int = 1) -> bool:
        """Increment counter for key. Returns True if threshold reached.

        Once a key fires, it is added to the `fired` set. The counter
        keeps accumulating (not auto-reset) until explicitly cleared
        via `pop_fired()` or `clear_key()`.
        """
        self.counters[key] = self.counters.get(key, 0) + amount
        if self.counters[key] >= self.threshold:
            self.fired.add(key)
            return True
        return False

    def pop_fired(self) -> List[str]:
        """Return all fired keys and reset their counters.

        Returns keys in sorted order for deterministic processing.
        """
        keys = sorted(self.fired)
        for key in keys:
            self.counters.pop(key, None)
        self.fired.clear()
        return keys

    def has_fired(self) -> bool:
        """Check if any key has reached the threshold."""
        return len(self.fired) > 0

    def clear_key(self, key: str) -> None:
        """Reset a specific key's counter and remove from fired set."""
        self.counters.pop(key, None)
        self.fired.discard(key)

    def get_count(self, key: str) -> int:
        """Get current count for a key."""
        return self.counters.get(key, 0)

    def get_state(self) -> Dict[str, Any]:
        """Serialize for save/load."""
        return {
            "name": self.name,
            "threshold": self.threshold,
            "counters": dict(self.counters),
            "fired": sorted(self.fired),
        }

    @classmethod
    def from_state(cls, state: Dict[str, Any]) -> TriggerBucket:
        """Restore from serialized state."""
        bucket = cls(
            name=state["name"],
            threshold=state["threshold"],
        )
        bucket.counters = dict(state.get("counters", {}))
        bucket.fired = set(state.get("fired", []))
        return bucket


class TriggerRegistry:
    """Central registry of trigger buckets for all WMS layers.

    Singleton. Each layer registers its buckets during initialization.
    The registry provides a uniform API for incrementing, checking, and
    clearing triggers regardless of which layer owns them.
    """

    _instance: ClassVar[Optional[TriggerRegistry]] = None

    def __init__(self):
        self._buckets: Dict[str, TriggerBucket] = {}

    @classmethod
    def get_instance(cls) -> TriggerRegistry:
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        cls._instance = None

    def register_bucket(self, name: str, threshold: int) -> TriggerBucket:
        """Register a new trigger bucket.

        If a bucket with this name already exists, its threshold is updated
        but counters are preserved (supports config reload).

        Args:
            name: Unique bucket name (e.g., "layer4_provinces").
            threshold: Fire when a key reaches this count.

        Returns:
            The registered TriggerBucket.
        """
        if name in self._buckets:
            self._buckets[name].threshold = threshold
        else:
            self._buckets[name] = TriggerBucket(name=name, threshold=threshold)
        return self._buckets[name]

    def get_bucket(self, name: str) -> Optional[TriggerBucket]:
        """Get a bucket by name. Returns None if not registered."""
        return self._buckets.get(name)

    def increment(self, bucket_name: str, key: str, amount: int = 1) -> bool:
        """Increment a key in a named bucket.

        Returns True if the key has now fired. Returns False if the
        bucket doesn't exist or the threshold hasn't been reached.
        """
        bucket = self._buckets.get(bucket_name)
        if bucket is None:
            return False
        return bucket.increment(key, amount)

    def get_and_clear_fired(self, bucket_name: str) -> List[str]:
        """Get all fired keys from a bucket and reset their counters.

        Returns empty list if bucket doesn't exist.
        """
        bucket = self._buckets.get(bucket_name)
        if bucket is None:
            return []
        return bucket.pop_fired()

    def has_fired(self, bucket_name: str) -> bool:
        """Check if any key has fired in a bucket."""
        bucket = self._buckets.get(bucket_name)
        return bucket.has_fired() if bucket else False

    def get_state(self) -> Dict[str, Any]:
        """Serialize all buckets for save/load."""
        return {
            name: bucket.get_state()
            for name, bucket in self._buckets.items()
        }

    def load_state(self, state: Dict[str, Any]) -> None:
        """Restore buckets from serialized state.

        Only restores counters for buckets that are already registered
        (threshold comes from config, not save data).
        """
        for name, bucket_state in state.items():
            if name in self._buckets:
                # Preserve the config-set threshold, restore counters
                self._buckets[name].counters = dict(
                    bucket_state.get("counters", {}))
                self._buckets[name].fired = set(
                    bucket_state.get("fired", []))
            else:
                # Bucket was registered in a previous session but not
                # in the current config — restore it anyway
                self._buckets[name] = TriggerBucket.from_state(bucket_state)

    @property
    def stats(self) -> Dict[str, Any]:
        """Summary stats for debugging."""
        return {
            "buckets": len(self._buckets),
            "details": {
                name: {
                    "threshold": b.threshold,
                    "keys_tracked": len(b.counters),
                    "keys_fired": len(b.fired),
                }
                for name, b in self._buckets.items()
            },
        }

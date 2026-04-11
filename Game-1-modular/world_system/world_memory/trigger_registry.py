"""Centralized trigger tracking for WMS layer escalation.

Two trigger modes:
1. **TriggerBucket** — simple per-key counter (Layer 3 uses this).
2. **WeightedTriggerBucket** — tag-positional weighting (Layer 4+ uses this).

Tag-positional weighting assigns points based on where a tag appears in the
event's tag list (earlier = more relevant):
    Position 1 = 10, 2 = 8, 3 = 6, 4 = 5, 5 = 4, 6 = 3, 7-12 = 2, 13+ = 1

When any tag accumulates enough points (default 50), it fires. All events
that contributed to that tag's score are returned as context for the
summarizer, pre-filtered to the most relevant inputs.

Usage:
    registry = TriggerRegistry()

    # Simple counter trigger (Layer 3)
    registry.register_bucket("layer3_districts", threshold=15)

    # Weighted tag trigger (Layer 4)
    bucket = registry.register_weighted_bucket("layer4_provinces",
                                                threshold=50)
    bucket.ingest_event("evt_1", ["province:region_1", "domain:combat", ...])
    fired = registry.get_and_clear_fired_weighted("layer4_provinces")
    # fired == {"province:region_1": ["evt_1", ...]}
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, ClassVar, Dict, List, Optional, Set, Tuple


# ── Positional weight table ────────────────────────────────────────

# Tag position → points. Position is 0-indexed.
_POSITION_WEIGHTS = (10, 8, 6, 5, 4, 3, 2, 2, 2, 2, 2, 2)
# Position 12+ all get 1 point

def tag_weight_for_position(position: int) -> int:
    """Return the point value for a tag at the given 0-indexed position."""
    if position < len(_POSITION_WEIGHTS):
        return _POSITION_WEIGHTS[position]
    return 1


# ── Simple counter bucket (unchanged from v1) ─────────────────────

@dataclass
class TriggerBucket:
    """A named collection of per-key counters with a shared threshold.

    Used by Layer 3 (simple event counting per district).
    """
    name: str
    threshold: int
    counters: Dict[str, int] = field(default_factory=dict)
    fired: Set[str] = field(default_factory=set)

    def increment(self, key: str, amount: int = 1) -> bool:
        """Increment counter for key. Returns True if threshold reached."""
        self.counters[key] = self.counters.get(key, 0) + amount
        if self.counters[key] >= self.threshold:
            self.fired.add(key)
            return True
        return False

    def pop_fired(self) -> List[str]:
        """Return all fired keys and reset their counters."""
        keys = sorted(self.fired)
        for key in keys:
            self.counters.pop(key, None)
        self.fired.clear()
        return keys

    def has_fired(self) -> bool:
        return len(self.fired) > 0

    def clear_key(self, key: str) -> None:
        self.counters.pop(key, None)
        self.fired.discard(key)

    def get_count(self, key: str) -> int:
        return self.counters.get(key, 0)

    def get_state(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "threshold": self.threshold,
            "counters": dict(self.counters),
            "fired": sorted(self.fired),
        }

    @classmethod
    def from_state(cls, state: Dict[str, Any]) -> TriggerBucket:
        bucket = cls(name=state["name"], threshold=state["threshold"])
        bucket.counters = dict(state.get("counters", {}))
        bucket.fired = set(state.get("fired", []))
        return bucket


# ── Weighted tag bucket (Layer 4+) ────────────────────────────────

@dataclass
class WeightedTriggerBucket:
    """Tag-weighted trigger bucket. Scores tags by positional importance.

    Each ingested event distributes points across its tags based on their
    position in the tag list. When any tag's score crosses the threshold,
    it fires. The bucket tracks which event IDs contributed to each tag so
    that the fired result includes all relevant context events.

    Attributes:
        name: Unique bucket name.
        threshold: Point threshold to fire (default 50).
        tag_scores: Current score per tag.
        tag_contributors: Map of tag → set of event IDs that contributed.
        fired_tags: Tags that crossed the threshold since last check.
    """
    name: str
    threshold: int = 50
    tag_scores: Dict[str, float] = field(default_factory=dict)
    tag_contributors: Dict[str, List[str]] = field(default_factory=dict)
    fired_tags: Set[str] = field(default_factory=set)

    # Tags that are purely structural and should not trigger on their own
    _SKIP_PREFIXES: ClassVar[Tuple[str, ...]] = (
        "significance:", "scope:", "consolidator:",
    )

    def ingest_event(self, event_id: str, tags: List[str]) -> List[str]:
        """Score all tags in an event by their position. Returns newly fired tags.

        Args:
            event_id: Unique event identifier.
            tags: Ordered tag list from the event (position matters!).

        Returns:
            List of tags that newly crossed the threshold from this event.
        """
        newly_fired = []
        for pos, tag in enumerate(tags):
            # Skip structural tags that shouldn't trigger
            if any(tag.startswith(p) for p in self._SKIP_PREFIXES):
                continue

            weight = tag_weight_for_position(pos)
            self.tag_scores[tag] = self.tag_scores.get(tag, 0) + weight

            # Track contributing event
            if tag not in self.tag_contributors:
                self.tag_contributors[tag] = []
            if event_id not in self.tag_contributors[tag]:
                self.tag_contributors[tag].append(event_id)

            # Check threshold
            if (self.tag_scores[tag] >= self.threshold
                    and tag not in self.fired_tags):
                self.fired_tags.add(tag)
                newly_fired.append(tag)

        return newly_fired

    def has_fired(self) -> bool:
        return len(self.fired_tags) > 0

    def pop_fired(self) -> Dict[str, List[str]]:
        """Return fired tags with their contributing event IDs, then reset.

        Returns:
            Dict mapping each fired tag to the list of event IDs that
            contributed points to it.
        """
        result = {}
        for tag in sorted(self.fired_tags):
            result[tag] = list(self.tag_contributors.get(tag, []))
            # Reset this tag's score and contributors
            self.tag_scores.pop(tag, None)
            self.tag_contributors.pop(tag, None)
        self.fired_tags.clear()
        return result

    def get_score(self, tag: str) -> float:
        return self.tag_scores.get(tag, 0)

    def get_state(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "threshold": self.threshold,
            "tag_scores": dict(self.tag_scores),
            "tag_contributors": {k: list(v)
                                 for k, v in self.tag_contributors.items()},
            "fired_tags": sorted(self.fired_tags),
        }

    @classmethod
    def from_state(cls, state: Dict[str, Any]) -> WeightedTriggerBucket:
        bucket = cls(name=state["name"], threshold=state["threshold"])
        bucket.tag_scores = dict(state.get("tag_scores", {}))
        bucket.tag_contributors = {
            k: list(v) for k, v in state.get("tag_contributors", {}).items()
        }
        bucket.fired_tags = set(state.get("fired_tags", []))
        return bucket


# ── Central Registry ───────────────────────────────────────────────

class TriggerRegistry:
    """Central registry of trigger buckets for all WMS layers. Singleton."""

    _instance: ClassVar[Optional[TriggerRegistry]] = None

    def __init__(self):
        self._buckets: Dict[str, TriggerBucket] = {}
        self._weighted_buckets: Dict[str, WeightedTriggerBucket] = {}

    @classmethod
    def get_instance(cls) -> TriggerRegistry:
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        cls._instance = None

    # ── Simple bucket API ──────────────────────────────────────────

    def register_bucket(self, name: str, threshold: int) -> TriggerBucket:
        """Register a simple counter bucket."""
        if name in self._buckets:
            self._buckets[name].threshold = threshold
        else:
            self._buckets[name] = TriggerBucket(name=name, threshold=threshold)
        return self._buckets[name]

    def get_bucket(self, name: str) -> Optional[TriggerBucket]:
        return self._buckets.get(name)

    def increment(self, bucket_name: str, key: str, amount: int = 1) -> bool:
        bucket = self._buckets.get(bucket_name)
        if bucket is None:
            return False
        return bucket.increment(key, amount)

    def get_and_clear_fired(self, bucket_name: str) -> List[str]:
        bucket = self._buckets.get(bucket_name)
        if bucket is None:
            return []
        return bucket.pop_fired()

    def has_fired(self, bucket_name: str) -> bool:
        bucket = self._buckets.get(bucket_name)
        return bucket.has_fired() if bucket else False

    # ── Weighted bucket API ────────────────────────────────────────

    def register_weighted_bucket(self, name: str,
                                  threshold: int = 50) -> WeightedTriggerBucket:
        """Register a tag-weighted trigger bucket."""
        if name in self._weighted_buckets:
            self._weighted_buckets[name].threshold = threshold
        else:
            self._weighted_buckets[name] = WeightedTriggerBucket(
                name=name, threshold=threshold)
        return self._weighted_buckets[name]

    def get_weighted_bucket(self, name: str) -> Optional[WeightedTriggerBucket]:
        return self._weighted_buckets.get(name)

    def ingest_event_weighted(self, bucket_name: str,
                               event_id: str,
                               tags: List[str]) -> List[str]:
        """Ingest an event into a weighted bucket. Returns newly fired tags."""
        bucket = self._weighted_buckets.get(bucket_name)
        if bucket is None:
            return []
        return bucket.ingest_event(event_id, tags)

    def get_and_clear_fired_weighted(
        self, bucket_name: str,
    ) -> Dict[str, List[str]]:
        """Get fired tags from a weighted bucket with contributor event IDs."""
        bucket = self._weighted_buckets.get(bucket_name)
        if bucket is None:
            return {}
        return bucket.pop_fired()

    def has_fired_weighted(self, bucket_name: str) -> bool:
        bucket = self._weighted_buckets.get(bucket_name)
        return bucket.has_fired() if bucket else False

    # ── Save/Load ──────────────────────────────────────────────────

    def get_state(self) -> Dict[str, Any]:
        return {
            "simple": {n: b.get_state() for n, b in self._buckets.items()},
            "weighted": {n: b.get_state()
                         for n, b in self._weighted_buckets.items()},
        }

    def load_state(self, state: Dict[str, Any]) -> None:
        for name, bs in state.get("simple", {}).items():
            if name in self._buckets:
                self._buckets[name].counters = dict(bs.get("counters", {}))
                self._buckets[name].fired = set(bs.get("fired", []))
            else:
                self._buckets[name] = TriggerBucket.from_state(bs)
        for name, bs in state.get("weighted", {}).items():
            if name in self._weighted_buckets:
                self._weighted_buckets[name].tag_scores = dict(
                    bs.get("tag_scores", {}))
                self._weighted_buckets[name].tag_contributors = {
                    k: list(v)
                    for k, v in bs.get("tag_contributors", {}).items()
                }
                self._weighted_buckets[name].fired_tags = set(
                    bs.get("fired_tags", []))
            else:
                self._weighted_buckets[name] = (
                    WeightedTriggerBucket.from_state(bs))

    @property
    def stats(self) -> Dict[str, Any]:
        return {
            "simple_buckets": len(self._buckets),
            "weighted_buckets": len(self._weighted_buckets),
            "details": {
                **{n: {"type": "simple", "threshold": b.threshold,
                       "keys_tracked": len(b.counters),
                       "keys_fired": len(b.fired)}
                   for n, b in self._buckets.items()},
                **{n: {"type": "weighted", "threshold": b.threshold,
                       "tags_tracked": len(b.tag_scores),
                       "tags_fired": len(b.fired_tags)}
                   for n, b in self._weighted_buckets.items()},
            },
        }

"""WNS BehaviorInterpreter — the Phase 2 behavior-causal trigger pathway.

Per consolidation §2.7 (corrected by user 2026-06-03): behavior-emergence
is the PRIMARY mechanism through which the world recognizes the player.
NPC interactions are the words; behavior-emergence is the actions and
body language. Words are clear and helpful, but body language reveals
more about what the system thinks of the player and what the player is
actually doing.

This module is the bridge between two streams the trace pass identified
as independently necessary:

1. **WMS_TRIGGER_FIRED** (Phase 0 G03) — the
   :class:`~world_system.world_memory.trigger_manager.TriggerManager`
   publishes a bus event each time a player counter crosses a
   ``THRESHOLD_SET`` value. The interpreter subscribes here.

2. **WNS_CALL_WES_REQUESTED** — the existing channel WES orchestrator
   subscribes to. The interpreter publishes here once it has built a
   behavior-causal :class:`WESContextBundle`.

Between subscribe and publish, the interpreter:

- Decides if the threshold warrants a WES dispatch (most don't — the
  ``_is_dispatch_worthy`` heuristics suppress low-significance counters,
  cooldown active counters, transit-mode events).
- Looks up the player's per-locality :class:`activity_profile` (Phase 0
  G14) to interpret what the milestone MEANS.
- Composes the :class:`BehaviorSignal` payload and a directive body
  ("an instant-heal skill matching the player's pattern of emergency
  potion use in combat").
- Builds the :class:`WESContextBundle` with ``trigger_archetype="behavior"``.
- Publishes ``WNS_CALL_WES_REQUESTED`` so the orchestrator runs the plan.

Per the user's pseudo-trace, the canonical example is: player crosses
1000 potions used → BehaviorInterpreter reads the ledger, sees combat
usage pattern, dispatches ``<WES purpose="new-skill">an instant-heal
skill matching the player's pattern of emergency potion use in
combat; tier 2-3; INT scaling</WES>``.

The :class:`CooldownArbiter` is a deterministic submodule that prevents
back-to-back dispatches on the same counter at the same address —
behavior triggers are higher-volume than narrative triggers, so without
a cooldown the player gets buried in new content. Targets: ~10-20% of
threshold events dispatch; 80-90% are journal-only or suppressed.
"""

from __future__ import annotations

import json
import os
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, ClassVar, Dict, List, Optional, Tuple  # noqa: F401


# ── Default dispatch rules (Wave 4 §5.4) ─────────────────────────────
#
# These are the in-code defaults. ``behavior_dispatch_rules.json`` in
# ``world_system/config/`` can override per-counter-category settings
# without touching code. The map is INTENTIONALLY conservative for
# v4 — designer playtest tuning expected.

_DEFAULT_DISPATCH_RULES: Dict[str, Any] = {
    "global": {
        # Minimum threshold rung for a stream-count to dispatch. Below
        # this the firing is journal-only (or suppressed entirely).
        # 100 is the "user has done this at scale" rung.
        "stream_min_threshold": 100,
        "regional_min_threshold": 250,
        # Cooldown window per (counter_path, locality) in game seconds.
        # 30 minutes = 1800 s. Designer-tunable.
        "cooldown_seconds": 1800.0,
        # Counters that should NEVER dispatch (transit, system events).
        "suppressed_categories": ["other"],
    },
    # Per-category overrides. Each entry can specify
    # min_threshold, cooldown_seconds, default_purpose. The purpose
    # is the WES directive purpose the interpreter composes for this
    # counter category.
    "categories": {
        # items.consumed.*  → utility/healing skills (the user's
        # potions example fits here when category derived from name).
        "combat": {"default_purpose": "new-skill"},
        "gathering": {"default_purpose": "new-material"},
        "crafting": {"default_purpose": "new-skill"},
        "exploration": {"default_purpose": "new-chunk",
                         "min_threshold": 1000},  # chunks are expensive
        "progression": {"default_purpose": "new-title"},
        "social": {"default_purpose": "new-npc"},
        "economy": {"default_purpose": "new-quest"},
    },
}


def _load_dispatch_rules() -> Dict[str, Any]:
    """Load ``behavior_dispatch_rules.json`` if present; deep-merge
    onto the in-code defaults.

    Designer-tunable file at
    ``Game-1-modular/world_system/config/behavior_dispatch_rules.json``.
    Missing or malformed file → use defaults (logged).
    """
    here = Path(__file__).parent
    project_root = here.parent.parent
    cfg = (
        project_root
        / "world_system" / "config" / "behavior_dispatch_rules.json"
    )
    if not cfg.exists():
        return _DEFAULT_DISPATCH_RULES
    try:
        with open(cfg, "r", encoding="utf-8") as f:
            user = json.load(f)
    except Exception:
        return _DEFAULT_DISPATCH_RULES
    return _merge_rules(_DEFAULT_DISPATCH_RULES, user)


def _merge_rules(base: Dict[str, Any], over: Dict[str, Any]) -> Dict[str, Any]:
    """Shallow deep-merge two rules dicts. The user's file overrides
    ``base`` per-key. Categories are merged per-name; global is merged
    flat."""
    out = {
        "global": {**base.get("global", {}), **over.get("global", {})},
        "categories": {**base.get("categories", {})},
    }
    for k, v in over.get("categories", {}).items():
        merged = {**out["categories"].get(k, {}), **v}
        out["categories"][k] = merged
    return out


# ── CooldownArbiter ──────────────────────────────────────────────────


class CooldownArbiter:
    """Deterministic per-counter-per-locality cooldown.

    Behavior triggers are higher-volume than narrative ones — without
    a cooldown, every threshold crossing dispatches a WES call. The
    player gets buried in new content. The arbiter remembers the last
    dispatch timestamp per (counter_path, locality) tuple and rejects
    new dispatches inside the window.

    Sub-millisecond per check (dict lookup). Stateless across saves
    by design — cooldowns reset on session start so they don't gate
    legitimate first-of-session dispatches.
    """

    def __init__(self, cooldown_seconds: float = 1800.0):
        self._cooldown = float(cooldown_seconds)
        self._last_dispatch: Dict[Tuple[str, str], float] = {}

    def can_dispatch(
        self, counter_path: str, locality_id: str, now: float,
    ) -> bool:
        """Return True if a new dispatch is allowed at this address."""
        last = self._last_dispatch.get((counter_path, locality_id))
        if last is None:
            return True
        return (now - last) >= self._cooldown

    def record_dispatch(
        self, counter_path: str, locality_id: str, now: float,
    ) -> None:
        """Mark a dispatch; subsequent checks within the window will
        return False."""
        self._last_dispatch[(counter_path, locality_id)] = float(now)

    def reset(self) -> None:
        """Test helper — clear all recorded dispatches."""
        self._last_dispatch.clear()


# ── BehaviorInterpreter ──────────────────────────────────────────────


@dataclass
class _Composed:
    """Internal — the result of interpreting a milestone."""
    directive_body: str
    purpose: str
    inferred_intent: str


class BehaviorInterpreter:
    """Phase 2 behavior-causal dispatch pathway.

    Singleton. Subscribes to ``WMS_TRIGGER_FIRED`` on instantiation if
    a bus is available; publishes ``WNS_CALL_WES_REQUESTED`` when a
    threshold warrants a dispatch.

    Usage:
        interp = BehaviorInterpreter.get_instance()
        # subscriptions happen at first attach() call; tests can pass
        # an explicit stat_store / bus for isolation.

    The interpreter is INTENTIONALLY thin — most of the work is rule
    lookup + signal composition. The actual content generation
    happens downstream in WES.
    """

    _instance: ClassVar[Optional[BehaviorInterpreter]] = None

    def __init__(
        self,
        stat_store=None,
        bus=None,
        rules: Optional[Dict[str, Any]] = None,
    ):
        self._stat_store = stat_store
        self._bus = bus
        self._rules = rules or _load_dispatch_rules()
        global_rules = self._rules.get("global", {})
        self._cooldown = CooldownArbiter(
            cooldown_seconds=float(
                global_rules.get("cooldown_seconds", 1800.0)
            )
        )
        self._stream_min = int(global_rules.get("stream_min_threshold", 100))
        self._regional_min = int(global_rules.get("regional_min_threshold", 250))
        self._suppressed_categories = set(
            global_rules.get("suppressed_categories", ["other"])
        )
        self._subscribed = False
        # Phase 7 wiring: recent narrative firings buffer for
        # MixedTriggerArbiter. List of (address, purpose, game_time).
        self._recent_narrative: List[Tuple[str, str, float]] = []
        # Arbiter is lazy-instantiated so tests can swap it.
        self._mixed_arbiter = None

    @classmethod
    def get_instance(cls) -> BehaviorInterpreter:
        if cls._instance is None:
            cls._instance = BehaviorInterpreter()
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        """Test helper — drop the singleton."""
        cls._instance = None

    # ── Attach / detach ─────────────────────────────────────────────

    def attach(self, bus=None, stat_store=None) -> None:
        """Subscribe to ``WMS_TRIGGER_FIRED`` and start interpreting.

        Idempotent — multiple calls are safe.
        """
        if bus is not None:
            self._bus = bus
        if stat_store is not None:
            self._stat_store = stat_store
        if self._bus is None or self._subscribed:
            return
        try:
            self._bus.subscribe("WMS_TRIGGER_FIRED", self._on_trigger_fired)
            # Phase 7 wiring: also observe narrative firings so the
            # MixedTriggerArbiter has a window to inspect.
            self._bus.subscribe(
                "WNS_CALL_WES_REQUESTED", self._on_narrative_firing,
            )
            self._subscribed = True
        except Exception:
            # Bus may not be available in test contexts; the caller can
            # still drive the interpreter directly via on_trigger_event.
            self._subscribed = False

    def detach(self) -> None:
        """Unsubscribe and stop interpreting. Idempotent."""
        if not self._subscribed or self._bus is None:
            return
        try:
            self._bus.unsubscribe(
                "WMS_TRIGGER_FIRED", self._on_trigger_fired,
            )
        except Exception:
            pass
        try:
            self._bus.unsubscribe(
                "WNS_CALL_WES_REQUESTED", self._on_narrative_firing,
            )
        except Exception:
            pass
        self._subscribed = False

    def _on_narrative_firing(self, event) -> None:
        """Track narrative WES requests for MixedTriggerArbiter window.

        We only care about firings published by the WNS weaver path, not
        echoes of our own behavior firings. The bundle's
        ``directive.scope_hint.trigger_archetype`` distinguishes them.
        """
        try:
            payload = getattr(event, "data", {}) or {}
            bundle = payload.get("bundle") or {}
            directive = bundle.get("directive") or {}
            scope = directive.get("scope_hint") or {}
            archetype = scope.get("trigger_archetype", "narrative")
            if archetype == "behavior":
                return  # ignore our own publishes
            address = scope.get("firing_address", "")
            purpose = scope.get("purpose", "")
            gt = float(bundle.get("created_at", time.time()))
            self._recent_narrative.append((address, purpose, gt))
            # Trim the buffer to a reasonable size — anything older than
            # 5x the arbiter window is no longer relevant.
            cutoff = gt - 150.0
            self._recent_narrative = [
                row for row in self._recent_narrative if row[2] >= cutoff
            ]
        except Exception:
            return

    # ── Core processing ─────────────────────────────────────────────

    def _on_trigger_fired(self, event) -> None:
        """GameEventBus handler — adapts the event payload to
        ``on_trigger_event``. Bus events carry a GameEvent dataclass
        with a ``data`` dict; we read the payload that
        ``TriggerManager._publish_trigger_fired`` writes (G03)."""
        try:
            payload = getattr(event, "data", {}) or {}
            self.on_trigger_event(
                counter_path=self._payload_counter_path(payload),
                threshold_crossed=int(payload.get("count", 0)),
                stream_count=int(payload.get("count", 0)),
                locality_id=str(payload.get("locality_id", "")),
                event_category=self._payload_category(payload),
                action_type=str(payload.get("action_type", "")),
            )
        except Exception:
            # The interpreter MUST NOT crash the bus. Swallow.
            return

    def on_trigger_event(
        self,
        counter_path: str,
        threshold_crossed: int,
        stream_count: int,
        locality_id: str,
        event_category: str,
        action_type: str,
        *,
        now: Optional[float] = None,
    ) -> bool:
        """Process one threshold-crossing event.

        Returns True if a dispatch was published, False otherwise.
        Designed to be testable independent of the bus subscription.
        """
        if not self._is_dispatch_worthy(
            threshold_crossed=threshold_crossed,
            locality_id=locality_id,
            event_category=event_category,
            action_type=action_type,
        ):
            return False

        if now is None:
            now = time.time()

        if not self._cooldown.can_dispatch(counter_path, locality_id, now):
            return False

        # Compose the directive body + WES purpose for this category.
        composed = self._compose_directive(
            counter_path=counter_path,
            threshold_crossed=threshold_crossed,
            locality_id=locality_id,
            event_category=event_category,
        )

        # Build the BehaviorSignal payload.
        activity_profile = self._activity_profile(locality_id)
        signal = self._make_signal(
            counter_path=counter_path,
            threshold_crossed=threshold_crossed,
            stream_count=stream_count,
            locality_id=locality_id,
            activity_profile=activity_profile,
            inferred_intent=composed.inferred_intent,
        )

        bundle = self._make_bundle(
            composed=composed,
            signal=signal,
            locality_id=locality_id,
            game_time=now,
        )

        # Phase 7 wiring: ask MixedTriggerArbiter whether a recent
        # narrative firing at the same address should suppress this
        # behavior firing.
        decision = self._arbitrate_against_narrative(
            address=f"locality:{locality_id}",
            purpose=composed.purpose,
            now=now,
        )
        if decision == "suppress_behavior":
            # Narrative firing already covered this ground.
            self._cooldown.record_dispatch(counter_path, locality_id, now)
            return False

        # Publish on the existing WNS→WES channel.
        if self._bus is not None:
            try:
                self._bus.publish(
                    "WNS_CALL_WES_REQUESTED",
                    {"bundle": bundle.to_dict()},
                    source="wns.behavior_interpreter",
                )
            except Exception:
                pass

        self._cooldown.record_dispatch(counter_path, locality_id, now)
        return True

    def _arbitrate_against_narrative(
        self, *, address: str, purpose: str, now: float,
    ) -> str:
        """Run MixedTriggerArbiter against any recent narrative firing
        at the same address. Returns one of "suppress_behavior",
        "issue_mixed", "issue_both" (default).

        Lazy-instantiates the arbiter on first call so tests that don't
        exercise this path don't pay the import.
        """
        if not self._recent_narrative:
            return "issue_both"
        try:
            from world_system.wns.mixed_trigger_arbiter import (
                FiringCandidate,
                MixedTriggerArbiter,
            )
        except Exception:
            return "issue_both"

        if self._mixed_arbiter is None:
            self._mixed_arbiter = MixedTriggerArbiter(window_seconds=30.0)

        # Find the most recent narrative firing at the same address.
        candidate_row = None
        for row in reversed(self._recent_narrative):
            if row[0] == address:
                candidate_row = row
                break
        if candidate_row is None:
            return "issue_both"

        narrative = FiringCandidate(
            archetype="narrative",
            address=address,
            purpose=candidate_row[1],
            bundle=None,
            game_time=candidate_row[2],
        )
        behavior = FiringCandidate(
            archetype="behavior",
            address=address,
            purpose=purpose,
            bundle=None,
            game_time=now,
        )
        try:
            return self._mixed_arbiter.decide(narrative, behavior)
        except Exception:
            return "issue_both"

    # ── Decision logic ──────────────────────────────────────────────

    def _is_dispatch_worthy(
        self,
        *,
        threshold_crossed: int,
        locality_id: str,
        event_category: str,
        action_type: str,
    ) -> bool:
        """Return True if this milestone warrants a WES dispatch.

        Most thresholds do NOT — 80-90% of crossings are journal-only
        or suppressed entirely. The heuristics live here:

        - Suppressed categories (e.g. "other" for system events).
        - Minimum threshold rung per track (stream vs regional).
        - Empty/unknown locality (we don't dispatch worldless content).
        - Per-category rule overrides.
        """
        if event_category in self._suppressed_categories:
            return False
        if not locality_id or locality_id == "unknown":
            return False
        # Per-category min threshold override falls through to global
        # if not set.
        cat_rule = self._rules.get("categories", {}).get(event_category, {})
        # Pick the appropriate global floor by action_type.
        if action_type == "interpret_region":
            min_thresh = int(cat_rule.get(
                "min_threshold", self._regional_min,
            ))
        else:
            min_thresh = int(cat_rule.get(
                "min_threshold", self._stream_min,
            ))
        if threshold_crossed < min_thresh:
            return False
        return True

    def _compose_directive(
        self,
        *,
        counter_path: str,
        threshold_crossed: int,
        locality_id: str,
        event_category: str,
    ) -> _Composed:
        """Choose the WES purpose and build the directive body.

        The purpose comes from the category's ``default_purpose`` rule
        (e.g. combat → new-skill). The body is a 1-2 sentence prose
        framing of what content should fire, mentioning the counter
        artifact and the locality.

        The inferred_intent string is the
        BehaviorInterpreter's interpretation of "what the player has
        been DOING" — this lands on the bundle and the supervisor's
        narrative-voice check (#5).
        """
        cat_rule = self._rules.get("categories", {}).get(
            event_category, {}
        )
        purpose = str(cat_rule.get("default_purpose", "new-skill"))

        # Extract the artifact noun from the counter_path so the body
        # mentions what the player DID. e.g.
        # "combat.kills.locality.tarmouth" → artifact "kills" at "tarmouth"
        # "items.consumed.potion.locality.tarmouth" → artifact "potion"
        artifact = _counter_artifact(counter_path)

        body = (
            f"At {locality_id} the player has done '{artifact}' "
            f"{threshold_crossed} times. The world should respond: "
            f"emit content responding to this {event_category} "
            f"pattern (tier 2-3) that references the {artifact} "
            f"artifact directly."
        )

        inferred = (
            f"The player has crossed {threshold_crossed} {event_category} "
            f"events at {locality_id}; signature artifact: {artifact}."
        )

        return _Composed(
            directive_body=body,
            purpose=purpose,
            inferred_intent=inferred,
        )

    # ── Helpers ─────────────────────────────────────────────────────

    def _activity_profile(self, locality_id: str) -> Dict[str, float]:
        """Look up StatStore.activity_profile if a store is attached."""
        if self._stat_store is None:
            return {}
        try:
            return self._stat_store.activity_profile(locality_id) or {}
        except Exception:
            return {}

    def _make_signal(
        self,
        *,
        counter_path: str,
        threshold_crossed: int,
        stream_count: int,
        locality_id: str,
        activity_profile: Dict[str, float],
        inferred_intent: str,
    ):
        from world_system.living_world.infra.context_bundle import (
            BehaviorSignal,
        )
        return BehaviorSignal(
            counter_path=counter_path,
            threshold_crossed=threshold_crossed,
            stream_count=stream_count,
            locality_id=locality_id,
            activity_profile=activity_profile,
            inferred_behavior_intent=inferred_intent,
            matching_pool_entries=[],
        )

    def _make_bundle(
        self,
        *,
        composed: _Composed,
        signal,
        locality_id: str,
        game_time: float,
    ):
        from world_system.living_world.infra.context_bundle import (
            NarrativeContextSlice,
            NarrativeDelta,
            WESContextBundle,
            WNSDirective,
        )

        delta = NarrativeDelta(
            address=f"locality:{locality_id}",
            layer=2,  # locality scope for stream-count thresholds
            start_time=game_time,
            end_time=game_time,
        )

        # Behavior-causal firings don't have a weaver-written narrative.
        # The "firing_layer_summary" is the BehaviorInterpreter's
        # inferred intent — what the world thinks the player is doing.
        ctx = NarrativeContextSlice(
            firing_layer_summary=signal.inferred_behavior_intent,
            parent_summaries={},
            open_threads=[],
        )

        directive = WNSDirective(
            directive_text=composed.directive_body,
            firing_tier=2,
            scope_hint={
                "firing_address": f"locality:{locality_id}",
                "weaver_layer": 2,
                "purpose": composed.purpose,
                # Phase 1 contract: the slice reads these.
                "trigger_archetype": "behavior",
            },
        )

        return WESContextBundle(
            bundle_id=f"behavior_{uuid.uuid4().hex[:12]}",
            created_at=game_time,
            delta=delta,
            narrative_context=ctx,
            directive=directive,
            source_narrative_layer_ids=[],
            behavior_signal=signal,
        )

    # ── Bus payload adapters ────────────────────────────────────────

    @staticmethod
    def _payload_counter_path(payload: Dict[str, Any]) -> str:
        """Build a synthetic counter_path from the TriggerManager
        payload. The published payload doesn't carry a true StatStore
        counter name — the trigger lives in TriggerManager — so we
        synthesize a path that uniquely identifies the stream for
        cooldown purposes.
        """
        action = payload.get("action_type", "stream")
        if action == "interpret_region":
            return (
                f"region.{payload.get('locality_id', '?')}."
                f"{payload.get('event_type', '?')}"
            )
        et = payload.get("event_type", "?")
        sub = payload.get("event_subtype", "")
        loc = payload.get("locality_id", "?")
        if sub:
            return f"stream.{et}.{sub}.{loc}"
        return f"stream.{et}.{loc}"

    @staticmethod
    def _payload_category(payload: Dict[str, Any]) -> str:
        """Resolve event_category from the published payload.

        We don't carry the category directly today — the
        TriggerManager publishes event_type and we derive category
        via the same EVENT_CATEGORY_MAP used in the WMS interpreter.
        """
        try:
            from world_system.world_memory.trigger_manager import (
                EVENT_CATEGORY_MAP,
            )
        except Exception:
            return "other"
        event_type = payload.get("event_type", "")
        return EVENT_CATEGORY_MAP.get(event_type, "other")


# ── Module-level helpers (used by both class and tests) ──────────────


def _counter_artifact(counter_path: str) -> str:
    """Extract a human-readable noun from a hierarchical counter path.

    Examples:
        "combat.kills.species.wolf.tarmouth" → "wolf"
        "items.consumed.potion.tarmouth" → "potion"
        "exploration.chunks.tarmouth" → "chunks"
        "stream.enemy_killed.copperlash_rider.tarmouth" → "copperlash_rider"

    Heuristic: the artifact is the second-to-last segment for paths
    ending in a locality, or the third segment for paths with a
    dimensional value pair, or the final segment otherwise.
    """
    parts = counter_path.split(".")
    if len(parts) < 2:
        return counter_path
    # Last segment is usually the locality value when path ends with
    # ``.locality.<id>`` or contains a single trailing locality.
    if "locality" in parts:
        idx = parts.index("locality")
        if idx > 0:
            return parts[idx - 1]
    # Stream payload synthetic path:
    # stream.<event_type>.<event_subtype>.<locality>
    # stream.<event_type>.<locality>
    if parts[0] == "stream" and len(parts) >= 4:
        return parts[2]
    if parts[0] == "stream" and len(parts) >= 3:
        return parts[1]
    # Fall through: drop trailing locality if present
    return parts[-2] if len(parts) >= 2 else parts[-1]


__all__ = [
    "BehaviorInterpreter",
    "CooldownArbiter",
    "_DEFAULT_DISPATCH_RULES",
]

"""MixedTriggerArbiter — deterministic concurrent-firing decision.

Phase 7 (2026-06-03). Per consolidation Wave 4 §9.3: when a
narrative-causal firing (from an NL weaver emitting ``<WES>`` inline)
and a behavior-causal firing (from the BehaviorInterpreter) target the
SAME address within a short window, the world is responding to BOTH
signals at once. The arbiter decides how to combine them.

Three outcomes:

- **issue_mixed** — fold both into a single bundle with
  ``trigger_archetype="mixed"`` (carries both narrative_context and
  behavior_signal). The planner reads both and emits a plan that
  leverages each. This is the canonical "world recognizes me AND is
  unfolding" case (the user's chunks pseudo-trace).
- **issue_both** — keep them as two separate firings. Used when the
  signals point at materially different purposes (e.g. one wants a
  new-skill, the other a new-chunk) and merging would create scope
  overflow.
- **suppress_behavior** — the narrative firing already covers the
  ground; the behavior firing is redundant. Tag the behavior trigger
  as journal-only.

The arbiter is deterministic. It runs in sub-millisecond on a small
queue of candidate firings. No LLM call.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional


@dataclass
class FiringCandidate:
    """A candidate WNS firing the arbiter inspects.

    Attributes:
        archetype: "narrative" or "behavior".
        address: the firing address (e.g. ``region:ashfall_moors``).
        purpose: the WES directive purpose (e.g. ``"new-skill"``).
        bundle: the prepared :class:`WESContextBundle`. The arbiter
            does not mutate it.
        game_time: when this candidate was prepared.
    """

    archetype: str
    address: str
    purpose: str
    bundle: Any
    game_time: float


class MixedTriggerArbiter:
    """Deterministic concurrent-firing arbiter.

    Usage:
        arbiter = MixedTriggerArbiter(window_seconds=30.0)
        decision = arbiter.decide(narrative_candidate, behavior_candidate)
        # decision is one of "issue_mixed" | "issue_both" | "suppress_behavior"
    """

    DECISION_MIXED = "issue_mixed"
    DECISION_BOTH = "issue_both"
    DECISION_SUPPRESS_BEHAVIOR = "suppress_behavior"

    def __init__(self, window_seconds: float = 30.0):
        # The window inside which two firings are considered
        # "concurrent" for arbitration purposes. Outside the window
        # they're independent — fire both.
        self._window = float(window_seconds)

    def decide(
        self,
        narrative: FiringCandidate,
        behavior: FiringCandidate,
    ) -> str:
        """Pick the arbitration outcome for two candidate firings.

        Decision rules (deterministic, prioritized):

        1. If firings are NOT concurrent (outside the time window),
           always ``issue_both``.
        2. If addresses don't match, always ``issue_both`` — the
           world is responding at two places, not the same place.
        3. If purposes match (both want a new-skill), the narrative
           firing covers the ground; ``suppress_behavior``.
        4. If purposes are complementary (one new-chunk, the other
           a downstream content type like new-material), merge them
           into ``issue_mixed`` — Phase 5 behavior inheritance will
           carry the flavor through the cascade.
        5. If purposes are at scope conflict (one new-faction, the
           other new-material — totally different tiers), ``issue_both``
           and let scope discipline handle it.

        The "complementary" set is hardcoded to the common chunks-
        cascade case from the user's pseudo-trace.
        """
        # Rule 1: outside the time window
        if abs(narrative.game_time - behavior.game_time) > self._window:
            return self.DECISION_BOTH

        # Rule 2: different addresses
        if narrative.address != behavior.address:
            return self.DECISION_BOTH

        # Rule 3: same purpose
        if narrative.purpose == behavior.purpose:
            return self.DECISION_SUPPRESS_BEHAVIOR

        # Rule 4: complementary purposes (chunks-cascade case)
        if self._is_complementary(narrative.purpose, behavior.purpose):
            return self.DECISION_MIXED

        # Rule 5: scope conflict (or unhandled combination)
        return self.DECISION_BOTH

    @staticmethod
    def _is_complementary(
        narrative_purpose: str, behavior_purpose: str,
    ) -> bool:
        """Return True if the two purposes are known to play well
        together at the same firing scope.

        The canonical chunks-cascade case: narrative says "new-chunk",
        behavior says one of the downstream-content purposes that the
        chunk would normally co-emit (materials / nodes / hostiles).
        Merging produces one chunk plan with flavored downstream
        cascade per Phase 5.
        """
        complementary_pairs = {
            ("new-chunk", "new-material"),
            ("new-chunk", "new-node"),
            ("new-chunk", "new-hostile"),
            ("new-material", "new-chunk"),
            ("new-node", "new-chunk"),
            ("new-hostile", "new-chunk"),
            ("new-npc", "new-quest"),
            ("new-quest", "new-npc"),
        }
        return (narrative_purpose, behavior_purpose) in complementary_pairs


__all__ = ["MixedTriggerArbiter", "FiringCandidate"]

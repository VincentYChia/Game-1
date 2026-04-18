"""Reputation Rules Engine — Phase 3.

Maps game events to affinity deltas via configurable rules.
Rules are tag-pattern based: "when event X targets tag Y, apply delta to tags Z".

This is the event → affinity bridge. Recording layer.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Callable
from dataclasses import dataclass
from fnmatch import fnmatch


@dataclass
class ReputationDelta:
    """A single affinity delta to apply."""
    tag: str
    delta: float
    description: str = ""


@dataclass
class ReputationRule:
    """A rule mapping event → deltas."""
    event_type: str                          # e.g., "QUEST_COMPLETED"
    target_tag_pattern: Optional[str]        # e.g., "guild:*", None = apply to all
    deltas: List[ReputationDelta]            # What to apply


class ReputationRulesEngine:
    """Engine for applying reputation rules to events."""

    def __init__(self):
        self.rules: Dict[str, List[ReputationRule]] = {}
        self._load_default_rules()

    def _load_default_rules(self) -> None:
        """Load default reputation rules (hardcoded for now; will be JSON later)."""
        # Quest completion: +10 to NPC's belonging tags
        self.add_rule(
            ReputationRule(
                event_type="QUEST_COMPLETED",
                target_tag_pattern=None,  # Apply to all tags on the NPC
                deltas=[
                    ReputationDelta("*", 10.0, "Quest completed for faction")
                ]
            )
        )

        # Enemy killed: faction of dead enemy gets -5, others +2 if allied
        self.add_rule(
            ReputationRule(
                event_type="ENEMY_KILLED",
                target_tag_pattern="allegiance:*",
                deltas=[
                    ReputationDelta("*", -5.0, "Member of faction killed")
                ]
            )
        )

        # Item crafted: crafting guilds +2
        self.add_rule(
            ReputationRule(
                event_type="ITEM_CRAFTED",
                target_tag_pattern="guild:*",
                deltas=[
                    ReputationDelta("guild:crafters", 2.0, "Crafted an item")
                ]
            )
        )

    def add_rule(self, rule: ReputationRule) -> None:
        """Add a reputation rule."""
        if rule.event_type not in self.rules:
            self.rules[rule.event_type] = []
        self.rules[rule.event_type].append(rule)

    def apply_rules(self, event_type: str, npc_tags: List[str]) -> Dict[str, float]:
        """Apply rules to an event for given NPC tags.

        Args:
            event_type: Type of event (e.g., "QUEST_COMPLETED")
            npc_tags: NPC's belonging tags

        Returns:
            Dict of tag → delta to apply
        """
        deltas = {}

        rules_for_event = self.rules.get(event_type, [])
        for rule in rules_for_event:
            # Check if this rule applies to any of the NPC's tags
            matching_tags = npc_tags
            if rule.target_tag_pattern:
                matching_tags = [t for t in npc_tags if fnmatch(t, rule.target_tag_pattern)]

            if not matching_tags:
                continue

            # Apply deltas to matching tags
            for rep_delta in rule.deltas:
                if rep_delta.tag == "*":
                    # Apply to all matching tags
                    for tag in matching_tags:
                        deltas[tag] = deltas.get(tag, 0.0) + rep_delta.delta
                else:
                    # Apply to specific tag
                    deltas[rep_delta.tag] = deltas.get(rep_delta.tag, 0.0) + rep_delta.delta

        return deltas


# Global instance
_engine: Optional[ReputationRulesEngine] = None


def get_rules_engine() -> ReputationRulesEngine:
    """Get global reputation rules engine."""
    global _engine
    if _engine is None:
        _engine = ReputationRulesEngine()
    return _engine

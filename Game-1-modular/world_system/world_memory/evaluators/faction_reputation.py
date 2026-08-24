"""Faction Reputation Evaluator — Layer 2 consolidation of affinity changes.

Observes FACTION_AFFINITY_CHANGED events (from quest completion, etc.) and
creates consolidated narratives about the player's reputation shifts with
factions, guilds, nations, and other social groups.

Layer 2 Purpose: Summarize affinity changes into human-readable narratives
for context assembly and dialogue generation.

Events monitored:
- FACTION_AFFINITY_CHANGED: Player affinity with a tag changed

Example narrative:
"The player has gained standing with the Merchants Guild through several quests."
"""

from __future__ import annotations

from typing import Optional, Dict, Any

from world_system.world_memory.config_loader import get_evaluator_config
from world_system.world_memory.event_schema import InterpretedEvent, WorldMemoryEvent
from world_system.world_memory.event_store import EventStore
from world_system.world_memory.geographic_registry import GeographicRegistry
from world_system.world_memory.entity_registry import EntityRegistry
from world_system.world_memory.interpreter import PatternEvaluator


class FactionReputationEvaluator(PatternEvaluator):
    """Consolidates player affinity changes into reputation narratives."""

    # The WMS stamps event_type = EventType.value (lowercase). This evaluator
    # was written against the uppercase bus name and so never matched — fixed
    # to the recorded value (2026-08-11) so it actually fires.
    RELEVANT_TYPES = {"faction_affinity_changed"}

    def __init__(self):
        cfg = get_evaluator_config("faction_reputation")
        self.lookback_time = cfg.get("lookback_time", 300.0)  # 5 minutes
        self.min_delta_threshold = cfg.get("min_delta_threshold", 5.0)
        self.delta_templates = cfg.get("delta_templates", {})
        self.consolidated_templates = cfg.get("consolidated_templates", {})

    def is_relevant(self, event: WorldMemoryEvent) -> bool:
        """Check if event is an affinity change."""
        return event.event_type == "faction_affinity_changed"

    def evaluate(
        self,
        trigger_event: WorldMemoryEvent,
        event_store: EventStore,
        geo_registry: GeographicRegistry,
        entity_registry: EntityRegistry,
        interpretation_store: EventStore,
    ) -> Optional[InterpretedEvent]:
        """Evaluate and consolidate affinity changes into reputation narratives.

        Returns a consolidated narrative about the player's reputation with a faction.
        """
        try:
            # The affinity payload rides in WorldMemoryEvent.context — the WMS
            # stores all non-standard event fields there (there is no .data
            # attr). This evaluator originally read .data and got nothing.
            ctx = getattr(trigger_event, "context", None) or {}
            player_id = ctx.get("player_id")
            tag = ctx.get("tag")
            delta = ctx.get("delta", 0.0)
            new_value = ctx.get("new_value", 0.0)

            if not player_id or not tag:
                return None

            if abs(delta) < self.min_delta_threshold:
                return None  # Too small to consolidate

            # Aggregate affinity changes (count_filtered has no game-time arg
            # here; WorldMemoryEvent has no .timestamp — that was another drift).
            recent_changes = event_store.count_filtered(
                event_type="faction_affinity_changed",
            )

            if recent_changes < 2:
                return None  # Need multiple changes to consolidate

            # Build narrative
            narrative = self._build_reputation_narrative(
                player_id, tag, delta, new_value, recent_changes
            )

            if not narrative:
                return None

            # Return via the CURRENT InterpretedEvent.create contract (this
            # evaluator predated it and used an obsolete event_type=/tags=/
            # interpretation= shape that no longer exists — 2026-08-11).
            severity = ("major" if abs(delta) > 20
                        else "significant" if abs(delta) > 10
                        else "moderate")
            locality_id = getattr(trigger_event, "locality_id", None)
            return InterpretedEvent.create(
                narrative=narrative,
                category="faction_reputation",
                severity=severity,
                trigger_event_id=trigger_event.event_id,
                trigger_count=getattr(trigger_event, "interpretation_count", 0),
                game_time=getattr(trigger_event, "game_time", 0.0),
                affects_tags=["type:player", f"faction:{tag}",
                              "reputation", "social"],
                affected_locality_ids=[locality_id] if locality_id else [],
                epicenter_x=getattr(trigger_event, "position_x", 0.0),
                epicenter_y=getattr(trigger_event, "position_y", 0.0),
                is_ongoing=True,
            )

        except Exception as e:
            print(f"[FactionReputationEvaluator] Error: {e}")
            return None

    def _build_reputation_narrative(
        self, player_id: str, tag: str, delta: float, new_value: float,
        change_count: int
    ) -> Optional[str]:
        """Build a narrative about reputation change.

        Args:
            player_id: Player identifier
            tag: Faction/guild/nation tag
            delta: Affinity change amount
            new_value: Current affinity value (-100 to +100)
            change_count: Number of recent changes

        Returns:
            Narrative string or None
        """
        # Determine reputation tier based on new_value
        if new_value >= 75:
            tier = "beloved"
        elif new_value >= 50:
            tier = "favored"
        elif new_value >= 25:
            tier = "respected"
        elif new_value > 0:
            tier = "liked"
        elif new_value == 0:
            tier = "neutral"
        elif new_value > -25:
            tier = "disliked"
        elif new_value >= -50:
            tier = "hated"
        else:
            tier = "reviled"

        # Build narrative based on delta direction and magnitude
        if delta > 20:
            strength = "significantly"
        elif delta > 10:
            strength = "noticeably"
        else:
            strength = "slightly"

        direction = "improved" if delta > 0 else "worsened"

        # Template-based narrative generation
        templates = [
            f"The player's reputation with {tag} has {strength} {direction}.",
            f"The player is becoming {tier} among {tag}.",
            f"Recent actions have {direction} the player's standing with {tag}.",
        ]

        # Choose template based on change count
        if change_count >= 3:
            narrative = f"The player has developed a {tier} relationship with {tag} through repeated interactions."
        else:
            narrative = templates[0]

        return narrative

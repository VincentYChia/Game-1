"""Faction Narrative Synthesizer — faction relationship narrative from L2 events.

Reads social, economy, and combat Layer 2 interpretations that involve
faction-tagged entities and synthesizes faction relationship narratives.

Scope: GLOBAL (per-faction, not per-district).
Trigger: 3+ L2 events with faction-relevant tags.
Output: "Player reputation with Miners Guild rising through sustained
         gathering activity and quest completion in their territory."
"""

from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any, Dict, List, Optional, Set

from world_system.world_memory.consolidator_base import ConsolidatorBase
from world_system.world_memory.event_schema import ConsolidatedEvent


# Domains that affect faction relationships
FACTION_RELEVANT_DOMAINS = {"social", "economy", "combat", "gathering", "crafting"}

# Tags that indicate faction relevance
FACTION_TAG_PREFIXES = {"npc:", "quest:", "faction:"}

# Known faction indicators from NPC/quest data
FACTION_INDICATORS = {
    "combat_trainer": "warriors_guild",
    "mysterious_trader": "merchants_guild",
    "tutorial_guide": "adventurers_guild",
    "miners": "miners_collective",
    "crafters": "crafters_guild",
    "forest": "forest_wardens",
    "village": "village_guard",
}


def _extract_factions(event: Dict[str, Any]) -> Set[str]:
    """Extract faction indicators from L2 event tags and narrative."""
    factions = set()
    tags = event.get("tags", [])

    for tag in tags:
        # Direct faction tag
        if tag.startswith("faction:"):
            factions.add(tag.split(":", 1)[1])
        # NPC-implied faction
        elif tag.startswith("npc:"):
            npc = tag.split(":", 1)[1]
            for indicator, faction in FACTION_INDICATORS.items():
                if indicator in npc:
                    factions.add(faction)

    # Check narrative for faction keywords
    narrative = event.get("narrative", "").lower()
    for indicator, faction in FACTION_INDICATORS.items():
        if indicator in narrative:
            factions.add(faction)

    return factions


def _is_faction_relevant(event: Dict[str, Any]) -> bool:
    """Check if an L2 event is relevant to faction narratives."""
    category = event.get("category", "")
    domain = category.split("_")[0] if "_" in category else category

    if domain in FACTION_RELEVANT_DOMAINS:
        # Check if it has any faction-relevant tags
        tags = event.get("tags", [])
        for tag in tags:
            for prefix in FACTION_TAG_PREFIXES:
                if tag.startswith(prefix):
                    return True

        # Social/quest events are always faction-relevant
        if domain == "social":
            return True

    return bool(_extract_factions(event))


class FactionNarrativeConsolidator(ConsolidatorBase):

    @property
    def consolidator_id(self) -> str:
        return "faction_narrative"

    @property
    def category(self) -> str:
        return "faction_narrative"

    def is_applicable(self, l2_events: List[Dict[str, Any]],
                      district_id: str = "") -> bool:
        """Applicable globally when 3+ faction-relevant L2 events exist."""
        if district_id:
            return False  # Global consolidator
        faction_events = [e for e in l2_events if _is_faction_relevant(e)]
        return len(faction_events) >= 3

    def consolidate(self, l2_events: List[Dict[str, Any]],
                    district_id: str,
                    geo_context: Dict[str, Any],
                    game_time: float) -> Optional[ConsolidatedEvent]:
        if not l2_events:
            return None

        # Filter to faction-relevant events
        faction_events = [e for e in l2_events if _is_faction_relevant(e)]
        if len(faction_events) < 3:
            return None

        # Group events by faction
        by_faction: Dict[str, List[Dict]] = defaultdict(list)
        unaffiliated: List[Dict] = []

        for event in faction_events:
            factions = _extract_factions(event)
            if factions:
                for faction in factions:
                    by_faction[faction].append(event)
            else:
                unaffiliated.append(event)

        if not by_faction:
            return None

        # Build narrative for each faction
        narrative_parts = []
        all_source_ids = []

        for faction, events in sorted(by_faction.items(),
                                       key=lambda x: -len(x[1])):
            faction_name = faction.replace("_", " ").title()
            event_count = len(events)

            # Analyze domain distribution for this faction
            domains = Counter()
            for event in events:
                cat = event.get("category", "")
                domain = cat.split("_")[0] if "_" in cat else cat
                domains[domain] += 1

            top_domain = domains.most_common(1)[0] if domains else ("social", 0)

            # Determine relationship direction
            quest_events = sum(1 for e in events
                             if "quest" in e.get("category", ""))
            combat_events = sum(1 for e in events
                              if "combat" in e.get("category", ""))
            social_events = sum(1 for e in events
                              if "social" in e.get("category", ""))

            if quest_events + social_events > combat_events:
                direction = "positive interactions"
            elif combat_events > quest_events + social_events:
                direction = "conflict-related activity"
            else:
                direction = "mixed interactions"

            narrative_parts.append(
                f"{faction_name}: {event_count} events, "
                f"primarily {top_domain[0]} ({direction})"
            )

            all_source_ids.extend(
                e.get("id", "") for e in events if e.get("id"))

        narrative = "Faction activity: " + ". ".join(narrative_parts) + "."

        severity = self.determine_severity(faction_events)

        # Build tags
        tags = [
            f"consolidator:{self.consolidator_id}",
            "scope:global",
        ]
        for faction in list(by_faction.keys())[:3]:
            tags.append(f"faction:{faction}")

        # Determine overall sentiment
        total_positive = sum(
            1 for e in faction_events
            if "quest" in e.get("category", "") or
               "social" in e.get("category", "")
        )
        total_negative = sum(
            1 for e in faction_events
            if "combat" in e.get("category", "")
        )
        if total_positive > total_negative:
            tags.append("sentiment:positive")
            tags.append("alignment:good")
        elif total_negative > total_positive:
            tags.append("sentiment:negative")
            tags.append("alignment:chaotic")
        else:
            tags.append("sentiment:neutral")

        return ConsolidatedEvent.create(
            narrative=narrative,
            category=self.category,
            severity=severity,
            source_interpretation_ids=list(set(all_source_ids)),
            game_time=game_time,
            affects_tags=tags,
        )

"""Player Identity Consolidator — behavioral profile from all player L2 events.

Reads ALL recent Layer 2 interpretations about the player regardless of
location and synthesizes a behavioral profile.

Scope: GLOBAL (not district-specific).
Trigger: 5+ total L2 events across all districts.
Output: "The player is primarily a melee combatant with growing smithing
         expertise, focused on the western regions. 3-day combat streak."
"""

from __future__ import annotations

from collections import Counter
from typing import Any, Dict, List, Optional

from world_system.world_memory.consolidator_base import ConsolidatorBase
from world_system.world_memory.event_schema import ConsolidatedEvent


# Playstyle archetypes based on domain dominance
PLAYSTYLE_MAP = {
    "combat": "combatant",
    "gathering": "gatherer",
    "crafting": "crafter",
    "exploration": "explorer",
    "social": "diplomat",
    "economy": "trader",
    "progression": "achiever",
}


class PlayerIdentityConsolidator(ConsolidatorBase):

    @property
    def consolidator_id(self) -> str:
        return "player_identity"

    @property
    def category(self) -> str:
        return "player_identity"

    def is_applicable(self, l2_events: List[Dict[str, Any]],
                      district_id: str = "") -> bool:
        """Applicable globally when 5+ L2 events exist. Skips district-scoped calls."""
        if district_id:
            return False  # Global consolidator only
        return len(l2_events) >= 5

    def consolidate(self, l2_events: List[Dict[str, Any]],
                    district_id: str,
                    geo_context: Dict[str, Any],
                    game_time: float) -> Optional[ConsolidatedEvent]:
        if not l2_events:
            return None

        # Analyze domain distribution
        domain_counts: Counter = Counter()
        for event in l2_events:
            cat = event.get("category", "unknown")
            # Map to broad domain
            domain = cat.split("_")[0] if "_" in cat else cat
            domain_counts[domain] += 1

        # Determine primary and secondary playstyle
        top_domains = domain_counts.most_common(3)
        if not top_domains:
            return None

        primary_domain = top_domains[0][0]
        primary_style = PLAYSTYLE_MAP.get(primary_domain, primary_domain)
        primary_count = top_domains[0][1]

        # Analyze geographic focus
        district_counts: Counter = Counter()
        for event in l2_events:
            for tag in event.get("tags", []):
                if tag.startswith("district:"):
                    district_counts[tag.split(":", 1)[1]] += 1
                    break

        # Analyze tier engagement
        tier_counts: Counter = Counter()
        for event in l2_events:
            for tag in event.get("tags", []):
                if tag.startswith("tier:"):
                    tier_counts[tag.split(":", 1)[1]] += 1
                    break

        # Build narrative
        narrative = f"The player is primarily a {primary_style}"

        if len(top_domains) >= 2:
            secondary = PLAYSTYLE_MAP.get(top_domains[1][0], top_domains[1][0])
            narrative += f" with {secondary} tendencies"

        narrative += f" ({primary_count} of {len(l2_events)} recent events). "

        # Geographic focus
        if district_counts:
            top_district = district_counts.most_common(1)[0]
            concentration = top_district[1] / len(l2_events)
            if concentration > 0.6:
                narrative += f"Concentrated activity in one region. "
            elif len(district_counts) >= 3:
                narrative += f"Activity spread across {len(district_counts)} regions. "

        # Tier focus
        if tier_counts:
            top_tier = tier_counts.most_common(1)[0]
            narrative += f"Primarily engaging T{top_tier[0]} content."

        severity = self.determine_severity(l2_events)
        source_ids = [e.get("id", "") for e in l2_events if e.get("id")]

        # Build tags
        tags = [
            f"consolidator:{self.consolidator_id}",
            f"domain:{primary_domain}",
            "scope:global",
        ]
        if len(top_domains) >= 2:
            tags.append(f"domain:{top_domains[1][0]}")
        # Determine trend
        if primary_count / max(len(l2_events), 1) > 0.7:
            tags.append("trend:stable")  # Strongly one domain
        else:
            tags.append("trend:volatile")  # Mixed activity

        # Determine sentiment based on playstyle
        if primary_domain == "combat":
            tags.append("sentiment:dangerous")
        elif primary_domain in ("crafting", "gathering"):
            tags.append("sentiment:prosperous")
        else:
            tags.append("sentiment:neutral")

        return ConsolidatedEvent.create(
            narrative=narrative,
            category=self.category,
            severity=severity,
            source_interpretation_ids=source_ids,
            game_time=game_time,
            affected_district_ids=list(district_counts.keys())[:5],
            affects_tags=tags,
        )

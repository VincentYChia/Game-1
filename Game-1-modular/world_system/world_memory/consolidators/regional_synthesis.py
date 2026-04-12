"""Regional Activity Synthesizer — summarizes all activity in a WMS district.

Reads all Layer 2 interpretations for a district, groups by locality,
and produces a 2-3 sentence overview of the district's activity state.

Scope: One WMS district (= one game region).
Trigger: District has 3+ L2 events or 2+ from different categories.
Output: "The Western Frontier is seeing concentrated activity.
         Iron Hills is under heavy resource extraction..."
"""

from __future__ import annotations

from collections import Counter
from typing import Any, Dict, List, Optional

from world_system.world_memory.consolidator_base import ConsolidatorBase
from world_system.world_memory.event_schema import ConsolidatedEvent


class RegionalSynthesisConsolidator(ConsolidatorBase):

    @property
    def consolidator_id(self) -> str:
        return "regional_synthesis"

    @property
    def category(self) -> str:
        return "regional_synthesis"

    def is_applicable(self, l2_events: List[Dict[str, Any]],
                      district_id: str = "") -> bool:
        """Applicable when a district has 3+ L2 events or 2+ categories."""
        if not district_id:
            return False  # Regional synthesis requires a district
        if len(l2_events) < 3:
            # Check if at least 2 different categories
            categories = {e.get("category", "") for e in l2_events}
            return len(categories) >= 2
        return True

    def consolidate(self, l2_events: List[Dict[str, Any]],
                    district_id: str,
                    geo_context: Dict[str, Any],
                    game_time: float) -> Optional[ConsolidatedEvent]:
        if not l2_events or not district_id:
            return None

        district_name = geo_context.get("district_name", district_id)

        # Analyze L2 events
        categories = Counter(e.get("category", "unknown") for e in l2_events)
        severities = [e.get("severity", "minor") for e in l2_events]

        # Count events per locality
        locality_counts: Counter = Counter()
        for event in l2_events:
            tags = event.get("tags", [])
            for tag in tags:
                if tag.startswith("locality:"):
                    locality_counts[tag.split(":", 1)[1]] += 1
                    break

        # Build template narrative
        top_categories = categories.most_common(3)
        activity_parts = []
        for cat, count in top_categories:
            domain = cat.split("_")[0] if "_" in cat else cat
            activity_parts.append(f"{domain} ({count} events)")

        narrative = (
            f"{district_name} shows activity across "
            f"{', '.join(activity_parts)}. "
        )

        # Add locality detail
        if locality_counts:
            localities_map = {
                loc["id"]: loc["name"]
                for loc in geo_context.get("localities", [])
            }
            top_loc = locality_counts.most_common(1)[0]
            loc_name = localities_map.get(top_loc[0], top_loc[0])
            narrative += (
                f"Most active area: {loc_name} "
                f"with {top_loc[1]} notable events."
            )

        severity = self.determine_severity(l2_events)
        source_ids = [e.get("id", "") for e in l2_events if e.get("id")]

        # Build Layer 3 tags
        tags = [
            f"district:{district_id}",
            f"consolidator:{self.consolidator_id}",
        ]
        # Add dominant domain
        if top_categories:
            domain = top_categories[0][0].split("_")[0]
            tags.append(f"domain:{domain}")
        # Add trend based on event count
        if len(l2_events) >= 10:
            tags.append("intensity:heavy")
        elif len(l2_events) >= 5:
            tags.append("intensity:moderate")
        else:
            tags.append("intensity:light")
        # Add sentiment based on event types
        combat_count = sum(1 for e in l2_events
                          if "combat" in e.get("category", ""))
        gathering_count = sum(1 for e in l2_events
                             if "gathering" in e.get("category", ""))
        if combat_count > gathering_count:
            tags.append("sentiment:dangerous")
        elif gathering_count > combat_count:
            tags.append("sentiment:prosperous")
        else:
            tags.append("sentiment:neutral")

        return ConsolidatedEvent.create(
            narrative=narrative,
            category=self.category,
            severity=severity,
            source_interpretation_ids=source_ids,
            game_time=game_time,
            affected_district_ids=[district_id],
            affects_tags=tags,
        )

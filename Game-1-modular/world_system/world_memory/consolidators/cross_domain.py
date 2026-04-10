"""Cross-Domain Pattern Detector — identifies connections between
different activity types in the same geographic area.

Reads Layer 2 interpretations from different categories in the same
district and finds co-occurring patterns.

Scope: One WMS district.
Trigger: District has 2+ L2 events from different categories.
Output: "Heavy combat and resource depletion co-occurring in
         Whispering Woods — intensive multi-domain activity."
"""

from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any, Dict, List, Optional, Set, Tuple

from world_system.world_memory.consolidator_base import ConsolidatorBase
from world_system.world_memory.event_schema import ConsolidatedEvent


# Domain pairs that have meaningful cross-domain relationships
DOMAIN_CONNECTIONS = {
    ("combat", "gathering"): "combat and resource activity co-occurring",
    ("combat", "crafting"): "combat driving crafting demand",
    ("gathering", "crafting"): "resource gathering feeding crafting output",
    ("combat", "progression"): "combat-driven progression",
    ("gathering", "economy"): "resource extraction affecting economy",
    ("crafting", "economy"): "crafting output affecting economy",
    ("exploration", "combat"): "exploration into hostile territory",
    ("exploration", "gathering"): "exploration-driven resource discovery",
    ("social", "economy"): "social interactions affecting trade",
    ("combat", "social"): "combat affecting social dynamics",
}


def _domain_from_category(category: str) -> str:
    """Extract broad domain from L2 category string."""
    domain_map = {
        "combat": "combat",
        "gathering": "gathering",
        "crafting": "crafting",
        "progression": "progression",
        "exploration": "exploration",
        "social": "social",
        "economy": "economy",
        "items": "economy",
        "population": "combat",
        "resource": "gathering",
    }
    for prefix, domain in domain_map.items():
        if category.startswith(prefix):
            return domain
    return category.split("_")[0] if "_" in category else category


class CrossDomainConsolidator(ConsolidatorBase):

    @property
    def consolidator_id(self) -> str:
        return "cross_domain"

    @property
    def category(self) -> str:
        return "cross_domain"

    def is_applicable(self, l2_events: List[Dict[str, Any]],
                      district_id: str = "") -> bool:
        """Applicable when a district has 2+ L2 events from different domains."""
        if not district_id:
            return False
        domains = {_domain_from_category(e.get("category", ""))
                   for e in l2_events}
        return len(domains) >= 2

    def consolidate(self, l2_events: List[Dict[str, Any]],
                    district_id: str,
                    geo_context: Dict[str, Any],
                    game_time: float) -> Optional[ConsolidatedEvent]:
        if not l2_events or not district_id:
            return None

        district_name = geo_context.get("district_name", district_id)

        # Group events by domain
        by_domain: Dict[str, List[Dict]] = defaultdict(list)
        for event in l2_events:
            domain = _domain_from_category(event.get("category", ""))
            by_domain[domain].append(event)

        if len(by_domain) < 2:
            return None

        # Find the strongest domain pair
        domains = sorted(by_domain.keys())
        best_pair = None
        best_score = 0

        for i, d1 in enumerate(domains):
            for d2 in domains[i + 1:]:
                pair = tuple(sorted([d1, d2]))
                # Score = combined event count, with bonus for known connections
                score = len(by_domain[d1]) + len(by_domain[d2])
                if pair in DOMAIN_CONNECTIONS:
                    score *= 1.5
                if score > best_score:
                    best_score = score
                    best_pair = pair

        if not best_pair:
            return None

        d1, d2 = best_pair

        # Check for co-location (same locality across domains)
        d1_localities = self._get_localities(by_domain[d1])
        d2_localities = self._get_localities(by_domain[d2])
        shared_localities = d1_localities & d2_localities

        # Build narrative
        connection_desc = DOMAIN_CONNECTIONS.get(
            best_pair, f"{d1} and {d2} activity co-occurring")

        narrative = (
            f"{district_name}: {connection_desc}. "
            f"{d1.capitalize()} ({len(by_domain[d1])} events) and "
            f"{d2.capitalize()} ({len(by_domain[d2])} events)"
        )

        if shared_localities:
            localities_map = {
                loc["id"]: loc["name"]
                for loc in geo_context.get("localities", [])
            }
            shared_names = [localities_map.get(lid, lid)
                           for lid in list(shared_localities)[:2]]
            narrative += f" converging in {', '.join(shared_names)}"
        narrative += "."

        # Collect all source IDs
        all_events = by_domain[d1] + by_domain[d2]
        source_ids = [e.get("id", "") for e in all_events if e.get("id")]
        severity = self.determine_severity(all_events)

        # Build tags
        tags = [
            f"district:{district_id}",
            f"consolidator:{self.consolidator_id}",
            f"domain:{d1}",
            f"domain:{d2}",
        ]
        if shared_localities:
            tags.append("trend:emerging")
        else:
            tags.append("trend:stable")

        return ConsolidatedEvent.create(
            narrative=narrative,
            category=self.category,
            severity=severity,
            source_interpretation_ids=source_ids,
            game_time=game_time,
            affected_district_ids=[district_id],
            affects_tags=tags,
        )

    def _get_localities(self, events: List[Dict]) -> Set[str]:
        """Extract unique locality IDs from event tags."""
        localities = set()
        for event in events:
            for tag in event.get("tags", []):
                if tag.startswith("locality:"):
                    localities.add(tag.split(":", 1)[1])
                    break
        return localities

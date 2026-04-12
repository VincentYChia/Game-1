"""ConsolidatorBase — abstract base class for Layer 3 consolidators.

Layer 3 consolidators differ from Layer 2 evaluators:
- Evaluators read single raw events through one lens
- Consolidators read MULTIPLE Layer 2 interpretations and synthesize

Visibility (two-layers-down rule):
- Full access: Layer 2 interpretations
- Limited access: Raw Event Pipeline (summary only)
- Cannot see: Layer 1 stats, Layers 4-7

Each consolidator has:
- is_applicable(): fast check — enough L2 data to run?
- consolidate(): synthesize multiple L2 events into one L3 narrative
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from world_system.world_memory.event_schema import ConsolidatedEvent


class ConsolidatorBase(ABC):
    """Abstract base class for Layer 3 consolidators.

    Subclasses implement:
    - is_applicable(): whether enough L2 data exists for consolidation
    - consolidate(): synthesis logic producing a ConsolidatedEvent
    """

    @property
    @abstractmethod
    def consolidator_id(self) -> str:
        """Unique identifier for this consolidator (e.g., 'regional_synthesis')."""

    @property
    @abstractmethod
    def category(self) -> str:
        """Layer 3 category this consolidator produces.

        One of: regional_synthesis, cross_domain, player_identity, faction_narrative
        """

    @abstractmethod
    def is_applicable(self, l2_events: List[Dict[str, Any]],
                      district_id: str = "") -> bool:
        """Fast check: is there enough Layer 2 data to run this consolidator?

        Args:
            l2_events: Layer 2 events for the scope (district or global).
            district_id: The district being consolidated (empty for global scope).

        Returns:
            True if consolidation should proceed.
        """

    @abstractmethod
    def consolidate(self, l2_events: List[Dict[str, Any]],
                    district_id: str,
                    geo_context: Dict[str, Any],
                    game_time: float) -> Optional[ConsolidatedEvent]:
        """Synthesize multiple Layer 2 events into a Layer 3 consolidated event.

        Args:
            l2_events: Layer 2 events to consolidate (dicts from LayerStore).
            district_id: The WMS district being consolidated.
            geo_context: Geographic context dict with keys:
                - district_name: str
                - province_name: str
                - localities: List[Dict] with {id, name} for each child locality
            game_time: Current game time.

        Returns:
            A ConsolidatedEvent if synthesis produced meaningful output, None otherwise.
        """

    def build_xml_data_block(self, l2_events: List[Dict[str, Any]],
                             district_name: str,
                             localities: Dict[str, str]) -> str:
        """Build XML-structured data block for LLM prompt.

        Groups L2 events by locality and formats as XML per the
        HANDOFF_STATUS.md prompt architecture design.

        Args:
            l2_events: Layer 2 events (dicts from LayerStore).
            district_name: Human-readable district name.
            localities: {locality_id: locality_name} mapping.

        Returns:
            XML string for the LLM prompt.
        """
        # Group events by locality
        by_locality: Dict[str, List[Dict]] = {}
        no_locality: List[Dict] = []

        for event in l2_events:
            tags = event.get("tags", [])
            loc_id = ""
            for tag in tags:
                if tag.startswith("locality:"):
                    loc_id = tag.split(":", 1)[1]
                    break
            if loc_id:
                by_locality.setdefault(loc_id, []).append(event)
            else:
                no_locality.append(event)

        # Build XML
        lines = [f'<district name="{district_name}">']

        for loc_id, events in sorted(by_locality.items()):
            loc_name = localities.get(loc_id, loc_id)
            lines.append(f'  <locality name="{loc_name}">')
            for event in events:
                cat = event.get("category", "unknown")
                sev = event.get("severity", "minor")
                narrative = event.get("narrative", "")
                lines.append(
                    f'    <event category="{cat}" severity="{sev}">'
                    f'{narrative}</event>'
                )
            lines.append('  </locality>')

        # Events without locality
        if no_locality:
            lines.append('  <general>')
            for event in no_locality:
                cat = event.get("category", "unknown")
                sev = event.get("severity", "minor")
                narrative = event.get("narrative", "")
                lines.append(
                    f'    <event category="{cat}" severity="{sev}">'
                    f'{narrative}</event>'
                )
            lines.append('  </general>')

        lines.append('</district>')
        return "\n".join(lines)

    def determine_severity(self, l2_events: List[Dict[str, Any]]) -> str:
        """Determine consolidated severity from source L2 events.

        Uses the highest severity among source events, with a boost
        if multiple categories are represented (cross-domain significance).
        """
        from world_system.world_memory.event_schema import SEVERITY_ORDER

        severity_values = [
            SEVERITY_ORDER.get(e.get("severity", "minor"), 0)
            for e in l2_events
        ]
        if not severity_values:
            return "minor"

        max_sev = max(severity_values)

        # Cross-domain boost: if 3+ different categories, bump severity by 1
        categories = {e.get("category", "") for e in l2_events}
        if len(categories) >= 3 and max_sev < 4:
            max_sev += 1

        reverse_order = {v: k for k, v in SEVERITY_ORDER.items()}
        return reverse_order.get(max_sev, "minor")

"""Layer 4 Province Summarizer — distills Layer 3 district events into
province-level summaries.

Unlike Layer 3's multi-consolidator pattern (4 specialised consolidators per
district), Layer 4 has a single summarizer per province. One province →
one summary. The LLM receives all recent Layer 3 events for the province's
child districts, plus optionally high-relevance Layer 2 events that share
tags with the Layer 3 input.

Data flow:
    Layer 3 events (tagged province:nation_X)
          ↓
    [Optional] Layer 2 events matching L3 tags (high relevance only)
          ↓
    Build XML data block with relative dates
          ↓
    LLM generates narrative + assigns Layer 4 tags
          ↓
    ProvinceSummaryEvent returned to Layer4Manager for storage

Visibility rule (two-layers-down):
    Layer 4 sees Layer 3 (full) and Layer 2 (filtered by tag overlap).
    Layer 4 does NOT see Layer 1 stats or Layers 5-7.
"""

from __future__ import annotations

from collections import Counter
from typing import Any, Dict, List, Optional, Set, Tuple

from world_system.world_memory.event_schema import (
    ProvinceSummaryEvent, SEVERITY_ORDER,
)
from world_system.world_memory.game_date import format_relative
from world_system.world_memory.geographic_registry import (
    RegionLevel, propagate_address_facts,
)


# Tag categories that indicate meaningful overlap between L2 and L3
_RELEVANCE_TAG_PREFIXES = frozenset({
    "domain:", "species:", "resource:", "setting:", "terrain:",
    "discipline:", "tier:",
})

# Minimum number of shared tags for an L2 event to qualify as "relevant"
_MIN_SHARED_TAGS = 2


class Layer4Summarizer:
    """Produces a single province-level summary from Layer 3 events.

    Not a subclass of ConsolidatorBase — Layer 4 has a different shape:
    - Input: Layer 3 events (not L2)
    - Scope: one province (not one district)
    - Output: ProvinceSummaryEvent (not ConsolidatedEvent)

    But follows the same contract pattern:
    - is_applicable(): fast boolean check
    - summarize(): main synthesis logic
    - build_xml_data_block(): format data for LLM
    """

    def is_applicable(self, l3_events: List[Dict[str, Any]],
                      province_id: str) -> bool:
        """Check if there is enough Layer 3 data to produce a summary.

        Requires at least 2 L3 events (from potentially different districts)
        for a province summary to be meaningful.
        """
        if not province_id or not l3_events:
            return False
        return len(l3_events) >= 2

    def summarize(
        self,
        l3_events: List[Dict[str, Any]],
        l2_events: List[Dict[str, Any]],
        province_id: str,
        geo_context: Dict[str, Any],
        game_time: float,
    ) -> Optional[ProvinceSummaryEvent]:
        """Synthesize Layer 3 events into a province summary.

        Args:
            l3_events: Layer 3 events for this province's child districts.
            l2_events: High-relevance Layer 2 events (pre-filtered by caller).
            province_id: WMS province ID (e.g. "nation_1").
            geo_context: Dict with province_name, districts[{id, name}].
            game_time: Current game time for relative date computation.

        Returns:
            ProvinceSummaryEvent or None if data is insufficient.
        """
        if not self.is_applicable(l3_events, province_id):
            return None

        province_name = geo_context.get("province_name", province_id)

        # Analyze dominant activities from L3 categories and tags
        dominant_activities = self._extract_dominant_activities(l3_events)

        # Determine threat level from severities
        threat_level = self._determine_threat_level(l3_events)

        # Compute aggregate severity
        severity = self._determine_severity(l3_events)

        # Build template narrative (will be replaced by LLM if available)
        narrative = self._build_template_narrative(
            l3_events, province_name, geo_context, dominant_activities,
            threat_level, game_time,
        )

        source_ids = [e.get("id", "") for e in l3_events if e.get("id")]
        relevant_l2_ids = [e.get("id", "") for e in l2_events if e.get("id")]

        # Build initial tags (before LLM enrichment)
        tags = self._build_tags(
            province_id, dominant_activities, threat_level, l3_events,
        )

        return ProvinceSummaryEvent.create(
            province_id=province_id,
            narrative=narrative,
            severity=severity,
            source_consolidation_ids=source_ids,
            game_time=game_time,
            dominant_activities=dominant_activities,
            threat_level=threat_level,
            relevant_l2_ids=relevant_l2_ids,
            tags=tags,
        )

    def build_xml_data_block(
        self,
        l3_events: List[Dict[str, Any]],
        l2_events: List[Dict[str, Any]],
        province_name: str,
        districts: List[Dict[str, str]],
        game_time: float,
    ) -> str:
        """Format Layer 3 + L2 events as XML for LLM consumption.

        Structure:
            <province name="...">
              <district name="...">
                <event category="..." severity="..." when="5 days ago">
                  narrative text
                </event>
                ...
              </district>
              <cross-district>
                <event>... (global-scope L3 events)</event>
              </cross-district>
              <supporting-detail>
                <event category="..." when="...">L2 detail</event>
              </supporting-detail>
            </province>
        """
        district_map = {d["id"]: d["name"] for d in districts}
        lines = [f'<province name="{province_name}">']

        # Group L3 events by district
        by_district: Dict[str, List[Dict]] = {}
        global_events: List[Dict] = []

        for event in l3_events:
            placed = False
            for tag in event.get("tags", []):
                if tag.startswith("district:"):
                    d_id = tag.split(":", 1)[1]
                    by_district.setdefault(d_id, []).append(event)
                    placed = True
                    break
            if not placed:
                global_events.append(event)

        # Emit per-district blocks (with full tag list for LLM rewrite)
        for d_id, events in sorted(by_district.items()):
            d_name = district_map.get(d_id, d_id)
            lines.append(f'  <district name="{d_name}">')
            for event in events:
                when = format_relative(event.get("game_time", 0), game_time)
                cat = event.get("category", "unknown")
                sev = event.get("severity", "minor")
                narrative = event.get("narrative", "").strip()
                tag_str = ", ".join(event.get("tags", []))
                lines.append(
                    f'    <event category="{cat}" severity="{sev}" '
                    f'when="{when}" tags="[{tag_str}]">'
                    f'{narrative}</event>'
                )
            lines.append('  </district>')

        # Global-scope L3 events (player_identity, faction_narrative)
        if global_events:
            lines.append('  <cross-district>')
            for event in global_events:
                when = format_relative(event.get("game_time", 0), game_time)
                cat = event.get("category", "unknown")
                sev = event.get("severity", "minor")
                narrative = event.get("narrative", "").strip()
                tag_str = ", ".join(event.get("tags", []))
                lines.append(
                    f'    <event category="{cat}" severity="{sev}" '
                    f'when="{when}" tags="[{tag_str}]">'
                    f'{narrative}</event>'
                )
            lines.append('  </cross-district>')

        # Supporting Layer 2 detail (with tags for context)
        if l2_events:
            lines.append('  <supporting-detail>')
            for event in l2_events[:10]:  # Cap to avoid prompt bloat
                when = format_relative(event.get("game_time", 0), game_time)
                cat = event.get("category", "unknown")
                narrative = event.get("narrative", "").strip()
                tag_str = ", ".join(event.get("tags", []))
                lines.append(
                    f'    <event category="{cat}" when="{when}" '
                    f'tags="[{tag_str}]">'
                    f'{narrative}</event>'
                )
            lines.append('  </supporting-detail>')

        lines.append('</province>')
        return "\n".join(lines)

    # ── Relevance Filtering ────────────────────────────────────────

    @staticmethod
    def filter_relevant_l2(
        l2_events: List[Dict[str, Any]],
        l3_events: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """Filter Layer 2 events to those sharing tags with the L3 input.

        Returns L2 events that share at least _MIN_SHARED_TAGS content tags
        with any of the L3 events. This surfaces granular detail that is
        directly relevant to the province narrative.

        Content tags are non-structural tags (not district/province/consolidator/
        scope/significance).
        """
        # Collect all content tags from L3 events
        l3_content_tags: Set[str] = set()
        for event in l3_events:
            for tag in event.get("tags", []):
                if any(tag.startswith(p) for p in _RELEVANCE_TAG_PREFIXES):
                    l3_content_tags.add(tag)

        if not l3_content_tags:
            return []

        # Filter L2 events by tag overlap
        relevant = []
        for event in l2_events:
            event_tags = set(event.get("tags", []))
            shared = event_tags & l3_content_tags
            if len(shared) >= _MIN_SHARED_TAGS:
                relevant.append(event)

        # Sort by severity (most severe first)
        relevant.sort(
            key=lambda e: SEVERITY_ORDER.get(e.get("severity", "minor"), 0),
            reverse=True,
        )

        return relevant[:15]  # Cap to prevent prompt explosion

    # ── Analysis Helpers ───────────────────────────────────────────

    def _extract_dominant_activities(
        self, l3_events: List[Dict[str, Any]],
    ) -> List[str]:
        """Determine top activities from L3 categories and domain tags."""
        domain_counts: Counter = Counter()
        for event in l3_events:
            # From category (e.g., "regional_synthesis" → skip, "cross_domain" → skip)
            # Better to use domain tags
            for tag in event.get("tags", []):
                if tag.startswith("domain:"):
                    domain_counts[tag.split(":", 1)[1]] += 1

        # Fall back to category if no domain tags
        if not domain_counts:
            for event in l3_events:
                cat = event.get("category", "")
                if cat not in ("regional_synthesis", "cross_domain",
                               "player_identity", "faction_narrative"):
                    domain_counts[cat] += 1

        return [domain for domain, _ in domain_counts.most_common(3)]

    def _determine_threat_level(
        self, l3_events: List[Dict[str, Any]],
    ) -> str:
        """Map aggregate L3 severities to a threat level.

        Threat is derived from combat/danger-related events, not all events.
        """
        danger_severities = []
        for event in l3_events:
            tags = event.get("tags", [])
            is_danger = any(
                t.startswith("sentiment:dangerous") or
                t.startswith("domain:combat") or
                t.startswith("intensity:heavy") or
                t.startswith("intensity:extreme")
                for t in tags
            )
            if is_danger:
                sev = event.get("severity", "minor")
                danger_severities.append(SEVERITY_ORDER.get(sev, 0))

        if not danger_severities:
            return "low"

        max_sev = max(danger_severities)
        avg_sev = sum(danger_severities) / len(danger_severities)

        if max_sev >= 4 or avg_sev >= 3:
            return "critical"
        elif max_sev >= 3 or avg_sev >= 2:
            return "high"
        elif max_sev >= 2 or avg_sev >= 1:
            return "moderate"
        return "low"

    def _determine_severity(
        self, l3_events: List[Dict[str, Any]],
    ) -> str:
        """Compute aggregate severity from L3 events.

        Uses the same logic as ConsolidatorBase.determine_severity:
        highest severity from inputs, boosted if multi-district.
        """
        if not l3_events:
            return "minor"

        severity_names = list(SEVERITY_ORDER.keys())
        max_sev = 0
        for event in l3_events:
            sev = event.get("severity", "minor")
            max_sev = max(max_sev, SEVERITY_ORDER.get(sev, 0))

        # Boost if events from 3+ districts (cross-district pattern)
        districts = set()
        for event in l3_events:
            for tag in event.get("tags", []):
                if tag.startswith("district:"):
                    districts.add(tag.split(":", 1)[1])
        if len(districts) >= 3:
            max_sev = min(max_sev + 1, len(severity_names) - 1)

        return severity_names[max_sev]

    def _build_template_narrative(
        self,
        l3_events: List[Dict[str, Any]],
        province_name: str,
        geo_context: Dict[str, Any],
        dominant_activities: List[str],
        threat_level: str,
        game_time: float,
    ) -> str:
        """Build a template narrative (used when LLM is unavailable)."""
        districts = geo_context.get("districts", [])
        district_count = len(districts)

        # Find most active district (most L3 events)
        district_event_counts: Counter = Counter()
        for event in l3_events:
            for tag in event.get("tags", []):
                if tag.startswith("district:"):
                    d_id = tag.split(":", 1)[1]
                    district_event_counts[d_id] += 1
                    break

        parts = [f"{province_name}:"]

        if dominant_activities:
            activities_str = ", ".join(dominant_activities[:3])
            parts.append(f" primary activity is {activities_str}.")
        else:
            parts.append(f" {len(l3_events)} consolidated events across "
                         f"{district_count} districts.")

        if threat_level in ("high", "critical"):
            parts.append(f" Threat level is {threat_level}.")

        if district_event_counts:
            top_district_id = district_event_counts.most_common(1)[0][0]
            top_name = top_district_id
            for d in districts:
                if d["id"] == top_district_id:
                    top_name = d["name"]
                    break
            parts.append(f" Most active district: {top_name}.")

        return "".join(parts)

    def _build_tags(
        self,
        province_id: str,
        dominant_activities: List[str],
        threat_level: str,
        l3_events: List[Dict[str, Any]],
    ) -> List[str]:
        """Build initial tag set for the summary event.

        Address tags (world, nation, region) are copied as FACTS from
        the input L3 events — we do NOT invent them. `district:` and
        `locality:` are NOT included because this layer aggregates
        across districts.

        The LLM later rewrites only the content tags; address tags
        are preserved untouched by layer code.
        """
        # ── Address tags (FACTS, propagated from L3 inputs) ──
        # Copy world/nation/region from any input event (all share the
        # same ancestry above the province level). `province:` is
        # this layer's own aggregation target, so we emit it from the
        # known `province_id` rather than reading it from inputs.
        tags: List[str] = propagate_address_facts(
            l3_events,
            (RegionLevel.WORLD, RegionLevel.NATION, RegionLevel.REGION),
        )
        tags.append(f"province:{province_id}")
        tags.append("scope:province")

        # ── Content tags (LLM-rewritable later) ──
        # Dominant activities as domain tags
        for activity in dominant_activities[:3]:
            tags.append(f"domain:{activity}")

        # Threat level
        tags.append(f"threat_level:{threat_level}")

        # Aggregate intensity based on event count
        count = len(l3_events)
        if count >= 8:
            tags.append("intensity:extreme")
        elif count >= 5:
            tags.append("intensity:heavy")
        elif count >= 3:
            tags.append("intensity:moderate")
        else:
            tags.append("intensity:light")

        return tags

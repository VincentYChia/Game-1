"""Layer 5 Region Summarizer — distills Layer 4 province events into
region-level summaries.

Aggregation tier: **game Region** (parent of game Province). Layer 5
produces a single holistic summary per game Region from all
contributing Layer 4 province summaries. The LLM receives every recent
Layer 4 event for the region's provinces, plus Layer 3 events filtered
by relevance to the tags that fired the region trigger.

Data flow:
    Layer 4 events (tagged world:, nation:, region:, province: — address
    facts assigned at L2 capture and propagated unchanged)
          ↓
    [Two-layers-down] Layer 3 events matching fired tags (filtered)
          ↓
    Build XML data block with relative dates and per-province grouping
          ↓
    Template narrative + LLM rewrite (CONTENT tags only)
          ↓
    RegionSummaryEvent returned to Layer5Manager for storage

Visibility rule (two-layers-down):
    Layer 5 sees Layer 4 (full) and Layer 3 (filtered by fired-tag overlap).
    Layer 5 does NOT see Layer 2, Layer 1 stats, or Layers 6-7.

Address immutability:
    Address tags (world/nation/region) are FACTS derived from the
    input events' address tags — never synthesized or rewritten.
    `province:`, `district:`, `locality:` are dropped at this layer
    because the aggregation spans multiple provinces. See
    docs/ARCHITECTURAL_DECISIONS.md §§4-5.

Pure WMS pipeline:
    Layer 5 does NOT read FactionSystem, EcosystemAgent, NPCMemory, or
    any other state tracker. All input is from the layer pipeline itself.
"""

from __future__ import annotations

from collections import Counter
from typing import Any, Dict, Iterable, List, Optional, Set

from world_system.world_memory.event_schema import (
    RegionSummaryEvent, SEVERITY_ORDER,
)
from world_system.world_memory.game_date import format_relative


# Tag categories that carry region-relevant meaning. Used for L3
# filtering when the fired-tag set is too narrow on its own.
_CONTENT_TAG_PREFIXES = frozenset({
    "domain:", "species:", "resource:", "setting:", "terrain:",
    "discipline:", "tier:", "sentiment:", "trend:", "intensity:",
    "resource_status:", "threat_level:",
    "urgency_level:", "event_status:", "player_impact:",
})

# Address tag prefixes that must NOT score in L3 filtering (facts, not
# content) plus other structural categories.
_GEO_STRUCTURAL_PREFIXES = frozenset({
    "world:", "nation:", "region:", "province:", "district:", "locality:",
    "scope:", "significance:", "consolidator:",
})

# L3 filter tuning — more permissive than L4's L2 filter because L3
# events are already consolidated summaries (higher signal-to-noise).
_L3_MIN_FIRED_TAG_MATCHES = 1
_L3_MAX_RESULTS = 8


class Layer5Summarizer:
    """Produces a single region-level summary from Layer 4 events.

    Follows the same contract pattern as Layer4Summarizer:
    - is_applicable(): fast boolean check
    - summarize(): main synthesis logic
    - build_xml_data_block(): format data for LLM

    Not a subclass of ConsolidatorBase — region summaries have unique shape.
    """

    def is_applicable(self, l4_events: List[Dict[str, Any]],
                      region_id: str) -> bool:
        """Check if there is enough Layer 4 data to produce a summary.

        Requires at least 2 L4 events (from potentially different
        provinces) for a region summary to be meaningful.
        """
        if not region_id or not l4_events:
            return False
        return len(l4_events) >= 2

    def summarize(
        self,
        l4_events: List[Dict[str, Any]],
        l3_events: List[Dict[str, Any]],
        region_id: str,
        geo_context: Dict[str, Any],
        game_time: float,
    ) -> Optional[RegionSummaryEvent]:
        """Synthesize Layer 4 events into a region summary.

        Args:
            l4_events: Layer 4 events for this region's provinces.
            l3_events: Relevant Layer 3 events (pre-filtered by caller).
            region_id: game Region ID (e.g. "region_17").
            geo_context: Dict with region_name, provinces[{id, name}].
            game_time: Current game time for relative date computation.

        Returns:
            RegionSummaryEvent or None if data is insufficient.
        """
        if not self.is_applicable(l4_events, region_id):
            return None

        region_name = geo_context.get("region_name", region_id)

        # Analyze dominant activities (from domain tags across L4 events)
        dominant_activities = self._extract_dominant_activities(l4_events)

        # Analyze dominant provinces (which provinces drove this summary)
        dominant_provinces = self._extract_dominant_provinces(l4_events)

        # Determine overall region condition from severity + threat levels
        region_condition = self._determine_region_condition(l4_events)

        # Compute aggregate severity
        severity = self._determine_severity(l4_events)

        # Build template narrative (replaced by LLM if available)
        narrative = self._build_template_narrative(
            l4_events, region_name, geo_context, dominant_activities,
            dominant_provinces, region_condition,
        )

        source_ids = [e.get("id", "") for e in l4_events if e.get("id")]
        relevant_l3_ids = [e.get("id", "") for e in l3_events if e.get("id")]

        # Build initial tags (before LLM enrichment). Address tags are
        # copied as facts from the input L4 events — never synthesized.
        tags = self._build_tags(
            region_id, dominant_activities, dominant_provinces,
            region_condition, l4_events,
        )

        return RegionSummaryEvent.create(
            region_id=region_id,
            narrative=narrative,
            severity=severity,
            source_province_summary_ids=source_ids,
            game_time=game_time,
            dominant_activities=dominant_activities,
            dominant_provinces=dominant_provinces,
            region_condition=region_condition,
            relevant_l3_ids=relevant_l3_ids,
            tags=tags,
        )

    def build_xml_data_block(
        self,
        l4_events: List[Dict[str, Any]],
        l3_events: List[Dict[str, Any]],
        region_name: str,
        provinces: List[Dict[str, str]],
        game_time: float,
    ) -> str:
        """Format Layer 4 + L3 events as XML for LLM consumption.

        Structure:
            <region name="...">
              <province name="...">
                <event category="..." severity="..." when="5 days ago"
                       tags="[...]">
                  L4 narrative text
                </event>
                ...
              </province>
              <cross-province>
                <event>... (region-scope L4 events, if any)</event>
              </cross-province>
              <supporting-detail>
                <event category="..." when="..." tags="[...]">
                  L3 detail
                </event>
              </supporting-detail>
            </region>
        """
        province_map = {p["id"]: p["name"] for p in provinces}
        lines = [f'<region name="{region_name}">']

        # Group L4 events by province
        by_province: Dict[str, List[Dict]] = {}
        global_events: List[Dict] = []

        for event in l4_events:
            placed = False
            for tag in event.get("tags", []):
                if tag.startswith("province:"):
                    p_id = tag.split(":", 1)[1]
                    by_province.setdefault(p_id, []).append(event)
                    placed = True
                    break
            if not placed:
                global_events.append(event)

        # Emit per-province blocks (with full tag list as LLM context)
        for p_id, events in sorted(by_province.items()):
            p_name = province_map.get(p_id, p_id)
            lines.append(f'  <province name="{p_name}">')
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
            lines.append('  </province>')

        # Region-scope L4 events (rare but possible)
        if global_events:
            lines.append('  <cross-province>')
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
            lines.append('  </cross-province>')

        # Supporting Layer 3 detail (two-layers-down, pre-filtered)
        if l3_events:
            lines.append('  <supporting-detail>')
            for event in l3_events[:_L3_MAX_RESULTS]:
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

        lines.append('</region>')
        return "\n".join(lines)

    # ── Relevance Filtering ────────────────────────────────────────

    @staticmethod
    def filter_relevant_l3(
        l3_candidates: List[Dict[str, Any]],
        fired_tags: Iterable[str],
        l4_events: Optional[List[Dict[str, Any]]] = None,
    ) -> List[Dict[str, Any]]:
        """Filter Layer 3 events using the fired tag set as relevance signal.

        The weighted trigger bucket has already told us which content
        tags crossed the threshold at the region level. Those fired
        tags ARE the set of "things the region cares about right now."
        We rank L3 candidates by how well they match that set.

        Algorithm:
          1. The fired_tags set represents the region's current focus.
          2. For each L3 candidate, count how many fired tags it contains.
          3. Filter: must match at least _L3_MIN_FIRED_TAG_MATCHES.
          4. Sort by:  match_count (desc)
                     → best matched tag position in L3's own tag list
                       (asc; L3 tags are frequency-sorted so earlier =
                       more representative)
                     → game_time (desc, most recent first)
          5. Return at most _L3_MAX_RESULTS.

        If the fired_tag set is empty (shouldn't happen in normal flow),
        fall back to matching by any content tag shared with L4 events.
        """
        # Narrow fired_tags to content tags only (strip address/structural)
        content_fired = {
            t for t in fired_tags
            if not any(t.startswith(p) for p in _GEO_STRUCTURAL_PREFIXES)
        }

        if not content_fired and l4_events:
            # Fallback: derive from L4 content tags
            for e in l4_events:
                for tag in e.get("tags", []):
                    if any(tag.startswith(p) for p in _CONTENT_TAG_PREFIXES):
                        if not any(tag.startswith(s)
                                   for s in _GEO_STRUCTURAL_PREFIXES):
                            content_fired.add(tag)

        if not content_fired:
            return []

        scored = []  # (match_count, best_position, game_time, event)
        for event in l3_candidates:
            event_tags = event.get("tags", [])
            event_tag_set = set(event_tags)
            matched = content_fired & event_tag_set

            if len(matched) < _L3_MIN_FIRED_TAG_MATCHES:
                continue

            best_pos = min(
                (i for i, t in enumerate(event_tags) if t in matched),
                default=999,
            )

            game_time = event.get("game_time", 0.0)
            scored.append((len(matched), best_pos, game_time, event))

        # Sort: match count desc → position asc → recency desc
        scored.sort(key=lambda x: (-x[0], x[1], -x[2]))
        return [item[3] for item in scored[:_L3_MAX_RESULTS]]

    # ── Analysis Helpers ───────────────────────────────────────────

    def _extract_dominant_activities(
        self, l4_events: List[Dict[str, Any]],
    ) -> List[str]:
        """Top activities (domain tags) aggregated across L4 events."""
        domain_counts: Counter = Counter()
        for event in l4_events:
            for tag in event.get("tags", []):
                if tag.startswith("domain:"):
                    domain_counts[tag.split(":", 1)[1]] += 1
        return [domain for domain, _ in domain_counts.most_common(3)]

    def _extract_dominant_provinces(
        self, l4_events: List[Dict[str, Any]],
    ) -> List[str]:
        """Provinces that contributed the most events to this region summary."""
        province_counts: Counter = Counter()
        for event in l4_events:
            for tag in event.get("tags", []):
                if tag.startswith("province:"):
                    province_counts[tag.split(":", 1)[1]] += 1
                    break  # one province tag per L4 event
        return [pid for pid, _ in province_counts.most_common(5)]

    def _determine_region_condition(
        self, l4_events: List[Dict[str, Any]],
    ) -> str:
        """Classify overall region condition.

        stable   → most L4 events minor/moderate, trend stable
        shifting → mixed severities OR multiple domains active
        volatile → several major events OR conflicting trends
        crisis   → any critical events OR widespread high/critical
                   threat/urgency levels
        """
        if not l4_events:
            return "stable"

        # Check for critical severity or threat_level:critical first
        for event in l4_events:
            if event.get("severity") == "critical":
                return "crisis"
            for tag in event.get("tags", []):
                if tag == "threat_level:critical" or tag == "urgency_level:critical":
                    return "crisis"
                if tag == "urgency_level:emergency":
                    return "crisis"

        # Count majors
        major_count = sum(
            1 for e in l4_events if e.get("severity") == "major"
        )
        if major_count >= 2:
            return "volatile"
        if major_count >= 1:
            return "shifting"

        # Check trend tags
        trends: Counter = Counter()
        for event in l4_events:
            for tag in event.get("tags", []):
                if tag.startswith("trend:"):
                    trends[tag.split(":", 1)[1]] += 1

        if trends.get("volatile", 0) >= 2 or trends.get("accelerating", 0) >= 2:
            return "volatile"
        if (trends.get("increasing", 0) + trends.get("decreasing", 0)
                + trends.get("emerging", 0) >= 3):
            return "shifting"

        return "stable"

    def _determine_severity(
        self, l4_events: List[Dict[str, Any]],
    ) -> str:
        """Compute aggregate severity — max from inputs, boosted if multi-province.

        Boost threshold: 4+ provinces = region-wide pattern.
        """
        if not l4_events:
            return "minor"

        severity_names = list(SEVERITY_ORDER.keys())
        max_sev = 0
        for event in l4_events:
            sev = event.get("severity", "minor")
            max_sev = max(max_sev, SEVERITY_ORDER.get(sev, 0))

        # Boost if events span 4+ provinces (region-wide pattern)
        provinces = set()
        for event in l4_events:
            for tag in event.get("tags", []):
                if tag.startswith("province:"):
                    provinces.add(tag.split(":", 1)[1])
                    break
        if len(provinces) >= 4:
            max_sev = min(max_sev + 1, len(severity_names) - 1)

        return severity_names[max_sev]

    def _build_template_narrative(
        self,
        l4_events: List[Dict[str, Any]],
        region_name: str,
        geo_context: Dict[str, Any],
        dominant_activities: List[str],
        dominant_provinces: List[str],
        region_condition: str,
    ) -> str:
        """Build a template narrative (used when LLM is unavailable)."""
        provinces_meta = geo_context.get("provinces", [])
        province_name_map = {p["id"]: p["name"] for p in provinces_meta}

        parts = [f"{region_name}:"]

        if dominant_activities:
            activities_str = ", ".join(dominant_activities[:3])
            parts.append(f" primary activity is {activities_str}.")
        else:
            parts.append(f" {len(l4_events)} province summaries recorded.")

        if dominant_provinces:
            named = [
                province_name_map.get(pid, pid)
                for pid in dominant_provinces[:3]
            ]
            parts.append(f" Most active provinces: {', '.join(named)}.")

        if region_condition != "stable":
            parts.append(f" Region condition is {region_condition}.")

        return "".join(parts)

    def _build_tags(
        self,
        region_id: str,
        dominant_activities: List[str],
        dominant_provinces: List[str],
        region_condition: str,
        l4_events: List[Dict[str, Any]],
    ) -> List[str]:
        """Build initial tag set for the region summary.

        Address tags (world, nation, region) are copied as facts from
        the input L4 events — we do NOT invent them. `province:`,
        `district:`, `locality:` are NOT included here because this
        layer aggregates across all provinces in the region.

        The LLM later rewrites only the content tags; address tags
        are preserved untouched by layer code.
        """
        tags: List[str] = []

        # ── Address tags (FACTS, propagated from L4 inputs) ──
        # Walk the inputs once and pick up the first world:/nation:/region:
        # value seen. All L4 events in the same region share the same
        # world/nation/region ancestry so this is deterministic.
        world_tag = ""
        nation_tag = ""
        for event in l4_events:
            for tag in event.get("tags", []):
                if not world_tag and tag.startswith("world:"):
                    world_tag = tag
                elif not nation_tag and tag.startswith("nation:"):
                    nation_tag = tag
            if world_tag and nation_tag:
                break

        if world_tag:
            tags.append(world_tag)
        if nation_tag:
            tags.append(nation_tag)
        # Region tag is the layer's own aggregation target
        tags.append(f"region:{region_id}")

        # Structural scope tag
        tags.append("scope:region")

        # ── Content tags (LLM-rewritable later) ──
        # Dominant activities as domain tags
        for activity in dominant_activities[:3]:
            tags.append(f"domain:{activity}")

        # Region condition
        tags.append(f"region_condition:{region_condition}")

        # Aggregate intensity based on L4 event count
        count = len(l4_events)
        if count >= 10:
            tags.append("intensity:extreme")
        elif count >= 6:
            tags.append("intensity:heavy")
        elif count >= 3:
            tags.append("intensity:moderate")
        else:
            tags.append("intensity:light")

        return tags

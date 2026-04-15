"""Layer 6 Nation Summarizer — distills Layer 5 region events into
nation-level summaries.

Aggregation tier: **game Nation** (parent of game Region). Layer 6
produces a single holistic summary per game Nation from all
contributing Layer 5 region summaries. The LLM receives every recent
Layer 5 event for the nation's regions, plus Layer 4 events filtered
by relevance to the tags that fired the nation trigger.

Data flow:
    Layer 5 events (tagged world:, nation:, region: — address facts
    assigned at L2 capture and propagated unchanged)
          ↓
    [Two-layers-down] Layer 4 events matching fired tags (filtered)
          ↓
    Build XML data block with relative dates and per-region grouping
          ↓
    Template narrative + LLM rewrite (CONTENT tags only)
          ↓
    NationSummaryEvent returned to Layer6Manager for storage

Visibility rule (two-layers-down):
    Layer 6 sees Layer 5 (full) and Layer 4 (filtered by fired-tag overlap).
    Layer 6 does NOT see Layer 3, Layer 2, Layer 1 stats, or Layer 7.

Address immutability:
    Address tags (world/nation) are FACTS derived from the input
    events' address tags — never synthesized or rewritten.
    `region:`, `province:`, `district:`, `locality:` are dropped at
    this layer because the aggregation spans multiple regions. See
    docs/ARCHITECTURAL_DECISIONS.md §6.

Pure WMS pipeline:
    Layer 6 does NOT read FactionSystem, EcosystemAgent, NPCMemory, or
    any other state tracker. All input is from the layer pipeline itself.
"""

from __future__ import annotations

from collections import Counter
from typing import Any, Dict, Iterable, List, Optional, Set

from world_system.world_memory.event_schema import (
    NationSummaryEvent, SEVERITY_ORDER,
)
from world_system.world_memory.game_date import format_relative
from world_system.world_memory.geographic_registry import (
    ADDRESS_TAG_PREFIXES, RegionLevel, propagate_address_facts,
)


# Tag categories that carry nation-relevant meaning. Used for L4
# filtering when the fired-tag set is too narrow on its own.
_CONTENT_TAG_PREFIXES = frozenset({
    "domain:", "species:", "resource:", "setting:", "terrain:",
    "discipline:", "tier:", "sentiment:", "trend:", "intensity:",
    "resource_status:", "threat_level:",
    "urgency_level:", "event_status:", "player_impact:",
    "region_condition:",
})

# Non-address structural prefixes that must also be excluded from L4
# filtering. Address prefixes are pulled from the single source of
# truth in geographic_registry.
_STRUCTURAL_NON_ADDRESS_PREFIXES = frozenset({
    "scope:", "significance:", "consolidator:",
})
_GEO_STRUCTURAL_PREFIXES = frozenset(ADDRESS_TAG_PREFIXES) | _STRUCTURAL_NON_ADDRESS_PREFIXES

# L4 filter tuning — mirrors L5's L3 cap since L4 events are already
# consolidated summaries (high signal-to-noise).
_L4_MIN_FIRED_TAG_MATCHES = 1
_L4_MAX_RESULTS = 8


class Layer6Summarizer:
    """Produces a single nation-level summary from Layer 5 events.

    Follows the same contract pattern as Layer5Summarizer:
    - is_applicable(): fast boolean check
    - summarize(): main synthesis logic
    - build_xml_data_block(): format data for LLM

    Not a subclass of ConsolidatorBase — nation summaries have unique shape.
    """

    def is_applicable(self, l5_events: List[Dict[str, Any]],
                      nation_id: str) -> bool:
        """Check if there is enough Layer 5 data to produce a summary.

        Requires at least 2 L5 events (from potentially different
        regions) for a nation summary to be meaningful.
        """
        if not nation_id or not l5_events:
            return False
        return len(l5_events) >= 2

    def summarize(
        self,
        l5_events: List[Dict[str, Any]],
        l4_events: List[Dict[str, Any]],
        nation_id: str,
        geo_context: Dict[str, Any],
        game_time: float,
    ) -> Optional[NationSummaryEvent]:
        """Synthesize Layer 5 events into a nation summary.

        Args:
            l5_events: Layer 5 events for this nation's regions.
            l4_events: Relevant Layer 4 events (pre-filtered by caller).
            nation_id: game Nation ID (e.g. "nation_3").
            geo_context: Dict with nation_name, regions[{id, name}].
            game_time: Current game time for relative date computation.

        Returns:
            NationSummaryEvent or None if data is insufficient.
        """
        if not self.is_applicable(l5_events, nation_id):
            return None

        nation_name = geo_context.get("nation_name", nation_id)

        # Analyze dominant activities (from domain tags across L5 events)
        dominant_activities = self._extract_dominant_activities(l5_events)

        # Analyze dominant regions (which regions drove this summary)
        dominant_regions = self._extract_dominant_regions(l5_events)

        # Determine overall nation condition from severity + threat levels
        nation_condition = self._determine_nation_condition(l5_events)

        # Compute aggregate severity
        severity = self._determine_severity(l5_events)

        # Build template narrative (replaced by LLM if available)
        narrative = self._build_template_narrative(
            l5_events, nation_name, geo_context, dominant_activities,
            dominant_regions, nation_condition,
        )

        source_ids = [e.get("id", "") for e in l5_events if e.get("id")]
        relevant_l4_ids = [e.get("id", "") for e in l4_events if e.get("id")]

        # Build initial tags (before LLM enrichment). Address tags are
        # copied as facts from the input L5 events — never synthesized.
        tags = self._build_tags(
            nation_id, dominant_activities, dominant_regions,
            nation_condition, l5_events,
        )

        return NationSummaryEvent.create(
            nation_id=nation_id,
            narrative=narrative,
            severity=severity,
            source_region_summary_ids=source_ids,
            game_time=game_time,
            dominant_activities=dominant_activities,
            dominant_regions=dominant_regions,
            nation_condition=nation_condition,
            relevant_l4_ids=relevant_l4_ids,
            tags=tags,
        )

    def build_xml_data_block(
        self,
        l5_events: List[Dict[str, Any]],
        l4_events: List[Dict[str, Any]],
        nation_name: str,
        regions: List[Dict[str, str]],
        game_time: float,
    ) -> str:
        """Format Layer 5 + L4 events as XML for LLM consumption.

        Structure:
            <nation name="...">
              <region name="...">
                <event category="..." severity="..." when="5 days ago"
                       tags="[...]">
                  L5 narrative text
                </event>
                ...
              </region>
              <cross-region>
                <event>... (nation-scope L5 events, if any)</event>
              </cross-region>
              <supporting-detail>
                <event category="..." when="..." tags="[...]">
                  L4 detail
                </event>
              </supporting-detail>
            </nation>
        """
        region_map = {r["id"]: r["name"] for r in regions}
        lines = [f'<nation name="{nation_name}">']

        # Group L5 events by region
        by_region: Dict[str, List[Dict]] = {}
        global_events: List[Dict] = []

        for event in l5_events:
            placed = False
            for tag in event.get("tags", []):
                if tag.startswith("region:"):
                    r_id = tag.split(":", 1)[1]
                    by_region.setdefault(r_id, []).append(event)
                    placed = True
                    break
            if not placed:
                global_events.append(event)

        # Emit per-region blocks (with full tag list as LLM context)
        for r_id, events in sorted(by_region.items()):
            r_name = region_map.get(r_id, r_id)
            lines.append(f'  <region name="{r_name}">')
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
            lines.append('  </region>')

        # Nation-scope L5 events (rare but possible)
        if global_events:
            lines.append('  <cross-region>')
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
            lines.append('  </cross-region>')

        # Supporting Layer 4 detail (two-layers-down, pre-filtered)
        if l4_events:
            lines.append('  <supporting-detail>')
            for event in l4_events[:_L4_MAX_RESULTS]:
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

        lines.append('</nation>')
        return "\n".join(lines)

    # ── Relevance Filtering ────────────────────────────────────────

    @staticmethod
    def filter_relevant_l4(
        l4_candidates: List[Dict[str, Any]],
        fired_tags: Iterable[str],
        l5_events: Optional[List[Dict[str, Any]]] = None,
    ) -> List[Dict[str, Any]]:
        """Filter Layer 4 events using the fired tag set as relevance signal.

        The weighted trigger bucket has already told us which content
        tags crossed the threshold at the nation level. Those fired
        tags ARE the set of "things the nation cares about right now."
        We rank L4 candidates by how well they match that set.

        Algorithm:
          1. The fired_tags set represents the nation's current focus.
          2. For each L4 candidate, count how many fired tags it contains.
          3. Filter: must match at least _L4_MIN_FIRED_TAG_MATCHES.
          4. Sort by:  match_count (desc)
                     → best matched tag position in L4's own tag list
                       (asc; L4 tags are already LLM-ordered so earlier =
                       more representative)
                     → game_time (desc, most recent first)
          5. Return at most _L4_MAX_RESULTS.

        If the fired_tag set is empty (shouldn't happen in normal flow),
        fall back to matching by any content tag shared with L5 events.
        """
        # Narrow fired_tags to content tags only (strip address/structural)
        content_fired = {
            t for t in fired_tags
            if not any(t.startswith(p) for p in _GEO_STRUCTURAL_PREFIXES)
        }

        if not content_fired and l5_events:
            # Fallback: derive from L5 content tags
            for e in l5_events:
                for tag in e.get("tags", []):
                    if any(tag.startswith(p) for p in _CONTENT_TAG_PREFIXES):
                        if not any(tag.startswith(s)
                                   for s in _GEO_STRUCTURAL_PREFIXES):
                            content_fired.add(tag)

        if not content_fired:
            return []

        scored = []  # (match_count, best_position, game_time, event)
        for event in l4_candidates:
            event_tags = event.get("tags", [])
            event_tag_set = set(event_tags)
            matched = content_fired & event_tag_set

            if len(matched) < _L4_MIN_FIRED_TAG_MATCHES:
                continue

            best_pos = min(
                (i for i, t in enumerate(event_tags) if t in matched),
                default=999,
            )

            game_time = event.get("game_time", 0.0)
            scored.append((len(matched), best_pos, game_time, event))

        # Sort: match count desc → position asc → recency desc
        scored.sort(key=lambda x: (-x[0], x[1], -x[2]))
        return [item[3] for item in scored[:_L4_MAX_RESULTS]]

    # ── Analysis Helpers ───────────────────────────────────────────

    def _extract_dominant_activities(
        self, l5_events: List[Dict[str, Any]],
    ) -> List[str]:
        """Top activities (domain tags) aggregated across L5 events."""
        domain_counts: Counter = Counter()
        for event in l5_events:
            for tag in event.get("tags", []):
                if tag.startswith("domain:"):
                    domain_counts[tag.split(":", 1)[1]] += 1
        return [domain for domain, _ in domain_counts.most_common(3)]

    def _extract_dominant_regions(
        self, l5_events: List[Dict[str, Any]],
    ) -> List[str]:
        """Regions that contributed the most events to this nation summary."""
        region_counts: Counter = Counter()
        for event in l5_events:
            for tag in event.get("tags", []):
                if tag.startswith("region:"):
                    region_counts[tag.split(":", 1)[1]] += 1
                    break  # one region tag per L5 event
        return [rid for rid, _ in region_counts.most_common(5)]

    def _determine_nation_condition(
        self, l5_events: List[Dict[str, Any]],
    ) -> str:
        """Classify overall nation condition.

        stable   → most L5 events minor/moderate, trend stable
        shifting → mixed severities OR multiple domains active
        volatile → several major events OR conflicting trends
        crisis   → any critical events OR widespread high/critical
                   threat/urgency levels
        """
        if not l5_events:
            return "stable"

        # Check for critical severity or threat_level:critical first
        for event in l5_events:
            if event.get("severity") == "critical":
                return "crisis"
            for tag in event.get("tags", []):
                if tag == "threat_level:critical" or tag == "urgency_level:critical":
                    return "crisis"
                if tag == "urgency_level:emergency":
                    return "crisis"

        # Count majors
        major_count = sum(
            1 for e in l5_events if e.get("severity") == "major"
        )
        if major_count >= 2:
            return "volatile"
        if major_count >= 1:
            return "shifting"

        # Check trend tags
        trends: Counter = Counter()
        for event in l5_events:
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
        self, l5_events: List[Dict[str, Any]],
    ) -> str:
        """Compute aggregate severity — max from inputs, boosted if multi-region.

        Boost threshold: 4+ regions = nation-wide pattern.
        """
        if not l5_events:
            return "minor"

        severity_names = list(SEVERITY_ORDER.keys())
        max_sev = 0
        for event in l5_events:
            sev = event.get("severity", "minor")
            max_sev = max(max_sev, SEVERITY_ORDER.get(sev, 0))

        # Boost if events span 4+ regions (nation-wide pattern)
        regions = set()
        for event in l5_events:
            for tag in event.get("tags", []):
                if tag.startswith("region:"):
                    regions.add(tag.split(":", 1)[1])
                    break
        if len(regions) >= 4:
            max_sev = min(max_sev + 1, len(severity_names) - 1)

        return severity_names[max_sev]

    def _build_template_narrative(
        self,
        l5_events: List[Dict[str, Any]],
        nation_name: str,
        geo_context: Dict[str, Any],
        dominant_activities: List[str],
        dominant_regions: List[str],
        nation_condition: str,
    ) -> str:
        """Build a template narrative (used when LLM is unavailable)."""
        regions_meta = geo_context.get("regions", [])
        region_name_map = {r["id"]: r["name"] for r in regions_meta}

        parts = [f"{nation_name}:"]

        if dominant_activities:
            activities_str = ", ".join(dominant_activities[:3])
            parts.append(f" primary activity is {activities_str}.")
        else:
            parts.append(f" {len(l5_events)} region summaries recorded.")

        if dominant_regions:
            named = [
                region_name_map.get(rid, rid)
                for rid in dominant_regions[:3]
            ]
            parts.append(f" Most active regions: {', '.join(named)}.")

        if nation_condition != "stable":
            parts.append(f" Nation condition is {nation_condition}.")

        return "".join(parts)

    def _build_tags(
        self,
        nation_id: str,
        dominant_activities: List[str],
        dominant_regions: List[str],
        nation_condition: str,
        l5_events: List[Dict[str, Any]],
    ) -> List[str]:
        """Build initial tag set for the nation summary.

        Address tags (world, nation) are copied as facts from the
        input L5 events — we do NOT invent them. `region:`,
        `province:`, `district:`, `locality:` are NOT included here
        because this layer aggregates across all regions in the nation.

        The LLM later rewrites only the content tags; address tags
        are preserved untouched by layer code.
        """
        # ── Address tags (FACTS, propagated from L5 inputs) ──
        # Copy world/ from any input event (all share the same ancestry
        # above the nation level). `nation:` is this layer's own
        # aggregation target, so we emit it from `nation_id` rather
        # than reading it from inputs.
        tags: List[str] = propagate_address_facts(
            l5_events,
            (RegionLevel.WORLD,),
        )
        tags.append(f"nation:{nation_id}")

        # Structural scope tag
        tags.append("scope:nation")

        # ── Content tags (LLM-rewritable later) ──
        # Dominant activities as domain tags
        for activity in dominant_activities[:3]:
            tags.append(f"domain:{activity}")

        # Nation condition
        tags.append(f"nation_condition:{nation_condition}")

        # Aggregate intensity based on L5 event count
        count = len(l5_events)
        if count >= 10:
            tags.append("intensity:extreme")
        elif count >= 6:
            tags.append("intensity:heavy")
        elif count >= 3:
            tags.append("intensity:moderate")
        else:
            tags.append("intensity:light")

        return tags

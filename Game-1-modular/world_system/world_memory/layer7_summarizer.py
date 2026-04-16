"""Layer 7 World Summarizer — distills Layer 6 nation events into a
world-level summary.

Aggregation tier: **game World** (parent of game Nation). Layer 7
produces a single holistic summary for the singleton game World from
all contributing Layer 6 nation summaries. The LLM receives every
recent Layer 6 event for the world, plus Layer 5 events filtered by
relevance to the tags that fired the world trigger.

This is the **final aggregation tier** — no Layer 8 is planned.

Data flow:
    Layer 6 events (tagged world:, nation: — address facts
    assigned at L2 capture and propagated unchanged)
          ↓
    [Two-layers-down] Layer 5 events matching fired tags (filtered)
          ↓
    Build XML data block with relative dates and per-nation grouping
          ↓
    Template narrative + LLM rewrite (CONTENT tags only)
          ↓
    WorldSummaryEvent returned to Layer7Manager for storage

Visibility rule (two-layers-down):
    Layer 7 sees Layer 6 (full) and Layer 5 (filtered by fired-tag overlap).
    Layer 7 does NOT see Layer 4, Layer 3, Layer 2, Layer 1 stats.

Address immutability:
    Address tags (world only) are FACTS derived from the input
    events' address tags — never synthesized or rewritten.
    `nation:`, `region:`, `province:`, `district:`, `locality:` are
    dropped at this layer because the aggregation spans all nations.
    See docs/ARCHITECTURAL_DECISIONS.md §6.

Pure WMS pipeline:
    Layer 7 does NOT read FactionSystem, EcosystemAgent, NPCMemory, or
    any other state tracker. All input is from the layer pipeline itself.
"""

from __future__ import annotations

from collections import Counter
from typing import Any, Dict, Iterable, List, Optional, Set

from world_system.world_memory.event_schema import (
    WorldSummaryEvent, SEVERITY_ORDER,
)
from world_system.world_memory.game_date import format_relative
from world_system.world_memory.geographic_registry import (
    ADDRESS_TAG_PREFIXES, RegionLevel, propagate_address_facts,
)


# Tag categories that carry world-relevant meaning. Used for L5
# filtering when the fired-tag set is too narrow on its own.
_CONTENT_TAG_PREFIXES = frozenset({
    "domain:", "species:", "resource:", "setting:", "terrain:",
    "discipline:", "tier:", "sentiment:", "trend:", "intensity:",
    "resource_status:", "threat_level:",
    "urgency_level:", "event_status:", "player_impact:",
    "nation_condition:", "region_condition:", "world_condition:",
})

# Non-address structural prefixes that must also be excluded from L5
# filtering. Address prefixes are pulled from the single source of
# truth in geographic_registry.
_STRUCTURAL_NON_ADDRESS_PREFIXES = frozenset({
    "scope:", "significance:", "consolidator:",
})
_GEO_STRUCTURAL_PREFIXES = frozenset(ADDRESS_TAG_PREFIXES) | _STRUCTURAL_NON_ADDRESS_PREFIXES

# L5 filter tuning — mirrors L6's L4 cap.
_L5_MIN_FIRED_TAG_MATCHES = 1
_L5_MAX_RESULTS = 8


class Layer7Summarizer:
    """Produces a single world-level summary from Layer 6 events.

    Follows the same contract pattern as Layer6Summarizer:
    - is_applicable(): fast boolean check
    - summarize(): main synthesis logic
    - build_xml_data_block(): format data for LLM

    Not a subclass of ConsolidatorBase — world summaries have unique shape.
    """

    def is_applicable(self, l6_events: List[Dict[str, Any]],
                      world_id: str) -> bool:
        """Check if there is enough Layer 6 data to produce a summary.

        Requires at least 2 L6 events (from potentially different
        nations) for a world summary to be meaningful.
        """
        if not world_id or not l6_events:
            return False
        return len(l6_events) >= 2

    def summarize(
        self,
        l6_events: List[Dict[str, Any]],
        l5_events: List[Dict[str, Any]],
        world_id: str,
        geo_context: Dict[str, Any],
        game_time: float,
    ) -> Optional[WorldSummaryEvent]:
        """Synthesize Layer 6 events into a world summary.

        Args:
            l6_events: Layer 6 events for this world's nations.
            l5_events: Relevant Layer 5 events (pre-filtered by caller).
            world_id: game World ID (always "world_0").
            geo_context: Dict with world_name, nations[{id, name}].
            game_time: Current game time for relative date computation.

        Returns:
            WorldSummaryEvent or None if data is insufficient.
        """
        if not self.is_applicable(l6_events, world_id):
            return None

        world_name = geo_context.get("world_name", world_id)

        # Analyze dominant activities (from domain tags across L6 events)
        dominant_activities = self._extract_dominant_activities(l6_events)

        # Analyze dominant nations (which nations drove this summary)
        dominant_nations = self._extract_dominant_nations(l6_events)

        # Determine overall world condition from severity + threat levels
        world_condition = self._determine_world_condition(l6_events)

        # Compute aggregate severity
        severity = self._determine_severity(l6_events)

        # Build template narrative (replaced by LLM if available)
        narrative = self._build_template_narrative(
            l6_events, world_name, geo_context, dominant_activities,
            dominant_nations, world_condition,
        )

        source_ids = [e.get("id", "") for e in l6_events if e.get("id")]
        relevant_l5_ids = [e.get("id", "") for e in l5_events if e.get("id")]

        # Build initial tags (before LLM enrichment). Address tags are
        # copied as facts from the input L6 events — never synthesized.
        tags = self._build_tags(
            world_id, dominant_activities, dominant_nations,
            world_condition, l6_events,
        )

        return WorldSummaryEvent.create(
            world_id=world_id,
            narrative=narrative,
            severity=severity,
            source_nation_summary_ids=source_ids,
            game_time=game_time,
            dominant_activities=dominant_activities,
            dominant_nations=dominant_nations,
            world_condition=world_condition,
            relevant_l5_ids=relevant_l5_ids,
            tags=tags,
        )

    def build_xml_data_block(
        self,
        l6_events: List[Dict[str, Any]],
        l5_events: List[Dict[str, Any]],
        world_name: str,
        nations: List[Dict[str, str]],
        game_time: float,
    ) -> str:
        """Format Layer 6 + L5 events as XML for LLM consumption.

        Structure:
            <world name="...">
              <nation name="...">
                <event category="..." severity="..." when="5 days ago"
                       tags="[...]">
                  L6 narrative text
                </event>
                ...
              </nation>
              <cross-nation>
                <event>... (world-scope L6 events, if any)</event>
              </cross-nation>
              <supporting-detail>
                <event category="..." when="..." tags="[...]">
                  L5 detail
                </event>
              </supporting-detail>
            </world>
        """
        nation_map = {n["id"]: n["name"] for n in nations}
        lines = [f'<world name="{world_name}">']

        # Group L6 events by nation
        by_nation: Dict[str, List[Dict]] = {}
        global_events: List[Dict] = []

        for event in l6_events:
            placed = False
            for tag in event.get("tags", []):
                if tag.startswith("nation:"):
                    n_id = tag.split(":", 1)[1]
                    by_nation.setdefault(n_id, []).append(event)
                    placed = True
                    break
            if not placed:
                global_events.append(event)

        # Emit per-nation blocks (with full tag list as LLM context)
        for n_id, events in sorted(by_nation.items()):
            n_name = nation_map.get(n_id, n_id)
            lines.append(f'  <nation name="{n_name}">')
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
            lines.append('  </nation>')

        # World-scope L6 events (rare but possible)
        if global_events:
            lines.append('  <cross-nation>')
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
            lines.append('  </cross-nation>')

        # Supporting Layer 5 detail (two-layers-down, pre-filtered)
        if l5_events:
            lines.append('  <supporting-detail>')
            for event in l5_events[:_L5_MAX_RESULTS]:
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

        lines.append('</world>')
        return "\n".join(lines)

    # ── Relevance Filtering ────────────────────────────────────────

    @staticmethod
    def filter_relevant_l5(
        l5_candidates: List[Dict[str, Any]],
        fired_tags: Iterable[str],
        l6_events: Optional[List[Dict[str, Any]]] = None,
    ) -> List[Dict[str, Any]]:
        """Filter Layer 5 events using the fired tag set as relevance signal.

        The weighted trigger bucket has already told us which content
        tags crossed the threshold at the world level. Those fired
        tags ARE the set of "things the world cares about right now."
        We rank L5 candidates by how well they match that set.

        Algorithm:
          1. The fired_tags set represents the world's current focus.
          2. For each L5 candidate, count how many fired tags it contains.
          3. Filter: must match at least _L5_MIN_FIRED_TAG_MATCHES.
          4. Sort by:  match_count (desc)
                     → best matched tag position in L5's own tag list
                       (asc; L5 tags are already LLM-ordered so earlier =
                       more representative)
                     → game_time (desc, most recent first)
          5. Return at most _L5_MAX_RESULTS.

        If the fired_tag set is empty (shouldn't happen in normal flow),
        fall back to matching by any content tag shared with L6 events.
        """
        # Narrow fired_tags to content tags only (strip address/structural)
        content_fired = {
            t for t in fired_tags
            if not any(t.startswith(p) for p in _GEO_STRUCTURAL_PREFIXES)
        }

        if not content_fired and l6_events:
            # Fallback: derive from L6 content tags
            for e in l6_events:
                for tag in e.get("tags", []):
                    if any(tag.startswith(p) for p in _CONTENT_TAG_PREFIXES):
                        if not any(tag.startswith(s)
                                   for s in _GEO_STRUCTURAL_PREFIXES):
                            content_fired.add(tag)

        if not content_fired:
            return []

        scored = []  # (match_count, best_position, game_time, event)
        for event in l5_candidates:
            event_tags = event.get("tags", [])
            event_tag_set = set(event_tags)
            matched = content_fired & event_tag_set

            if len(matched) < _L5_MIN_FIRED_TAG_MATCHES:
                continue

            best_pos = min(
                (i for i, t in enumerate(event_tags) if t in matched),
                default=999,
            )

            game_time = event.get("game_time", 0.0)
            scored.append((len(matched), best_pos, game_time, event))

        # Sort: match count desc → position asc → recency desc
        scored.sort(key=lambda x: (-x[0], x[1], -x[2]))
        return [item[3] for item in scored[:_L5_MAX_RESULTS]]

    # ── Analysis Helpers ───────────────────────────────────────────

    def _extract_dominant_activities(
        self, l6_events: List[Dict[str, Any]],
    ) -> List[str]:
        """Top activities (domain tags) aggregated across L6 events."""
        domain_counts: Counter = Counter()
        for event in l6_events:
            for tag in event.get("tags", []):
                if tag.startswith("domain:"):
                    domain_counts[tag.split(":", 1)[1]] += 1
        return [domain for domain, _ in domain_counts.most_common(3)]

    def _extract_dominant_nations(
        self, l6_events: List[Dict[str, Any]],
    ) -> List[str]:
        """Nations that contributed the most events to this world summary."""
        nation_counts: Counter = Counter()
        for event in l6_events:
            for tag in event.get("tags", []):
                if tag.startswith("nation:"):
                    nation_counts[tag.split(":", 1)[1]] += 1
                    break  # one nation tag per L6 event
        return [nid for nid, _ in nation_counts.most_common(5)]

    def _determine_world_condition(
        self, l6_events: List[Dict[str, Any]],
    ) -> str:
        """Classify overall world condition.

        stable   → most L6 events minor/moderate, trends stable
        shifting → mixed severities OR multiple domains active
        volatile → several major events OR conflicting trends
        crisis   → any critical events OR widespread high/critical
                   threat/urgency levels
        """
        if not l6_events:
            return "stable"

        # Check for critical severity or threat_level:critical first
        for event in l6_events:
            if event.get("severity") == "critical":
                return "crisis"
            for tag in event.get("tags", []):
                if tag == "threat_level:critical" or tag == "urgency_level:critical":
                    return "crisis"
                if tag == "urgency_level:emergency":
                    return "crisis"

        # Count majors
        major_count = sum(
            1 for e in l6_events if e.get("severity") == "major"
        )
        if major_count >= 2:
            return "volatile"
        if major_count >= 1:
            return "shifting"

        # Check trend tags
        trends: Counter = Counter()
        for event in l6_events:
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
        self, l6_events: List[Dict[str, Any]],
    ) -> str:
        """Compute aggregate severity — max from inputs, boosted if multi-nation.

        Boost threshold: 3+ nations = world-wide pattern.
        """
        if not l6_events:
            return "minor"

        severity_names = list(SEVERITY_ORDER.keys())
        max_sev = 0
        for event in l6_events:
            sev = event.get("severity", "minor")
            max_sev = max(max_sev, SEVERITY_ORDER.get(sev, 0))

        # Boost if events span 3+ nations (world-wide pattern)
        nations = set()
        for event in l6_events:
            for tag in event.get("tags", []):
                if tag.startswith("nation:"):
                    nations.add(tag.split(":", 1)[1])
                    break
        if len(nations) >= 3:
            max_sev = min(max_sev + 1, len(severity_names) - 1)

        return severity_names[max_sev]

    def _build_template_narrative(
        self,
        l6_events: List[Dict[str, Any]],
        world_name: str,
        geo_context: Dict[str, Any],
        dominant_activities: List[str],
        dominant_nations: List[str],
        world_condition: str,
    ) -> str:
        """Build a template narrative (used when LLM is unavailable)."""
        nations_meta = geo_context.get("nations", [])
        nation_name_map = {n["id"]: n["name"] for n in nations_meta}

        parts = [f"{world_name}:"]

        if dominant_activities:
            activities_str = ", ".join(dominant_activities[:3])
            parts.append(f" primary activity is {activities_str}.")
        else:
            parts.append(f" {len(l6_events)} nation summaries recorded.")

        if dominant_nations:
            named = [
                nation_name_map.get(nid, nid)
                for nid in dominant_nations[:3]
            ]
            parts.append(f" Most active nations: {', '.join(named)}.")

        if world_condition != "stable":
            parts.append(f" World condition is {world_condition}.")

        return "".join(parts)

    def _build_tags(
        self,
        world_id: str,
        dominant_activities: List[str],
        dominant_nations: List[str],
        world_condition: str,
        l6_events: List[Dict[str, Any]],
    ) -> List[str]:
        """Build initial tag set for the world summary.

        Address tags (world only) are copied as facts from the input
        L6 events — we do NOT invent them. `nation:`, `region:`,
        `province:`, `district:`, `locality:` are NOT included here
        because this layer aggregates across all nations in the world.

        The LLM later rewrites only the content tags; address tags
        are preserved untouched by layer code.
        """
        # ── Address tags (FACTS, propagated from L6 inputs) ──
        # Copy world: from any input event (all share the same world).
        # `nation:` is dropped at this layer — the aggregation spans
        # all nations. We always emit `world:world_0` as the sole
        # address tag on world-level output.
        tags: List[str] = propagate_address_facts(
            l6_events,
            (RegionLevel.WORLD,),
        )
        # Ensure world_id is present even if propagate_address_facts
        # finds no world: tag in the inputs (defensive fallback).
        if not any(t.startswith("world:") for t in tags):
            tags.append(f"world:{world_id}")

        # Structural scope tag
        tags.append("scope:world")

        # ── Content tags (LLM-rewritable later) ──
        # Dominant activities as domain tags
        for activity in dominant_activities[:3]:
            tags.append(f"domain:{activity}")

        # World condition
        tags.append(f"world_condition:{world_condition}")

        # Aggregate intensity based on L6 event count
        count = len(l6_events)
        if count >= 10:
            tags.append("intensity:extreme")
        elif count >= 6:
            tags.append("intensity:heavy")
        elif count >= 3:
            tags.append("intensity:moderate")
        else:
            tags.append("intensity:light")

        return tags

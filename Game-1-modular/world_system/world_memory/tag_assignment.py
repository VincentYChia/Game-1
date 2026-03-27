"""Procedural Tag Assignment — assigns tags to data at each layer.

Layer 1: Manual mapping from stat key patterns to tags (from config JSON).
Layer 2: Inherits Layer 1 tags + adds Layer 2 categories. LLM placeholder
         writes event name and can add optional new tags.
Layer 3+: Inherits from below + adds layer-specific tags. Layer 4+ gains
          ability to rewrite/reorder all tags (configurable).

Design notes for future LLM integration:
- Layer 2 LLM receives: origin stat + its tags, geographic context (locality,
  district, province, biome), event magnitude, trigger count, game time,
  evaluator category. LLM writes: event narrative + optional new tags.
- Layer 3 LLM receives: list of Layer 2 events + their tags, locality context.
  LLM writes: consolidated narrative + layer-specific tags (sentiment,
  alignment, trend, etc.). Inherits Layer 2 tags by default.
- Layer 4+ LLM receives: inherited tags as INPUT CONTEXT + layer events.
  Can REWRITE entire tag set (reorder by importance, add/remove).
  This is configurable — may start at Layer 4 or Layer 3.
- Significance is ALWAYS recreated at each layer.
- Key tags (scope, urgency, address) are always updated.

In-game date system: not yet implemented. Date fields use game_time float
for now. When date system exists, convert to in-game calendar dates.
"""

from __future__ import annotations

import json
import os
import re
from typing import Any, Dict, List, Optional, Set, Tuple

from world_system.world_memory.tag_library import (
    ALL_CATEGORIES, get_categories_for_layer, validate_tag,
    format_tag, parse_tag, get_key_tags, get_recreated_tags,
)


# ══════════════════════════════════════════════════════════════════
# LAYER 1: Manual stat-to-tag mapping
# ══════════════════════════════════════════════════════════════════

class Layer1TagMapper:
    """Maps Layer 1 stat keys to tags using a manual mapping file.

    The mapping file (layer1-stat-tags.json) contains patterns with
    wildcards (*) that match dimensional stat keys. More specific
    patterns override less specific ones. {dim} placeholders in tag
    values are filled from the matched wildcard segment.
    """

    def __init__(self, config_path: Optional[str] = None):
        self._mappings: List[Dict[str, Any]] = []
        self._cache: Dict[str, List[str]] = {}
        self._load(config_path)

    def _load(self, config_path: Optional[str] = None) -> None:
        """Load mapping from JSON config."""
        if config_path is None:
            this_dir = os.path.dirname(os.path.abspath(__file__))
            config_path = os.path.join(this_dir, "..", "config", "layer1-stat-tags.json")
            config_path = os.path.normpath(config_path)

        if not os.path.isfile(config_path):
            self._mappings = []
            return

        with open(config_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        self._mappings = data.get("mappings", [])
        # Sort by specificity: more segments = more specific = checked first
        self._mappings.sort(key=lambda m: -m["pattern"].count("."))

    def get_tags(self, stat_key: str) -> List[str]:
        """Get tags for a stat key, resolving wildcards and {dim} placeholders.

        Returns a list of "category:value" tag strings, ordered by relevance
        (as defined in the mapping file).
        """
        if stat_key in self._cache:
            return self._cache[stat_key]

        tags = self._resolve(stat_key)
        self._cache[stat_key] = tags
        return tags

    def _resolve(self, stat_key: str) -> List[str]:
        """Find best matching pattern and resolve tags."""
        parts = stat_key.split(".")

        best_match = None
        best_specificity = -1
        captured_dims: List[str] = []

        for mapping in self._mappings:
            pattern = mapping["pattern"]
            pattern_parts = pattern.split(".")

            match, dims = self._match_pattern(parts, pattern_parts)
            if match:
                specificity = sum(1 for p in pattern_parts if p != "*")
                if specificity > best_specificity:
                    best_specificity = specificity
                    best_match = mapping
                    captured_dims = dims

        if best_match is None:
            # Fallback: derive minimal tags from key structure
            return self._fallback_tags(stat_key)

        # Resolve {dim} placeholders in tags
        tags = []
        for tag_template in best_match["tags"]:
            if "{dim}" in tag_template and captured_dims:
                # Use the LAST captured dimension (most specific)
                tag = tag_template.replace("{dim}", captured_dims[-1])
            else:
                tag = tag_template
            tags.append(tag)

        return tags

    def _match_pattern(self, key_parts: List[str],
                       pattern_parts: List[str]) -> Tuple[bool, List[str]]:
        """Match a stat key against a pattern. Returns (matched, captured_dims)."""
        if len(key_parts) != len(pattern_parts):
            return False, []

        captured = []
        for kp, pp in zip(key_parts, pattern_parts):
            if pp == "*":
                captured.append(kp)
            elif kp != pp:
                return False, []
        return True, captured

    def _fallback_tags(self, stat_key: str) -> List[str]:
        """Generate minimal tags from stat key when no mapping matches."""
        parts = stat_key.split(".")
        tags = []
        if parts:
            tags.append(f"domain:{parts[0]}")
        tags.append("actor:player")
        tags.append("metric:count")
        return tags

    @property
    def pattern_count(self) -> int:
        return len(self._mappings)


# ══════════════════════════════════════════════════════════════════
# LAYER 2: Inheritance + Layer 2 categories
# ══════════════════════════════════════════════════════════════════

class Layer2TagAssigner:
    """Assigns tags to Layer 2 events.

    Inherits all tags from the origin Layer 1 stat, then adds Layer 2
    categories based on geographic and event context.

    LLM integration point: When LLM is wired in, it receives:
    - The origin stat key + its Layer 1 tags
    - Geographic context (locality, district, province, biome)
    - Event magnitude, trigger count, evaluator category
    - Game time (future: in-game calendar date)
    LLM writes: event narrative + optional new tags to add.
    Currently uses template placeholder.
    """

    def assign_tags(self, origin_stat_tags: List[str],
                    locality_id: str = "",
                    district_id: str = "",
                    province_id: str = "",
                    biome: str = "",
                    scope: str = "local",
                    significance: str = "minor",
                    evaluator_category: str = "",
                    extra_tags: Optional[List[str]] = None) -> List[str]:
        """Build complete Layer 2 tag set.

        Args:
            origin_stat_tags: Inherited tags from Layer 1.
            locality_id: Geographic locality.
            district_id: Geographic district.
            province_id: Geographic province.
            biome: Chunk biome type.
            scope: Geographic scope of this event.
            significance: Evaluator-assessed significance (RECREATED here).
            evaluator_category: Which evaluator produced this.
            extra_tags: Any additional tags from the evaluator.

        Returns:
            Complete tag list for this Layer 2 event, ordered by relevance.
        """
        tags = []

        # 1. Inherit Layer 1 tags (these come first — most factual/specific)
        tags.extend(origin_stat_tags)

        # 2. Add Layer 2 geographic address tags
        if locality_id:
            tags.append(format_tag("locality", locality_id))
        if district_id:
            tags.append(format_tag("district", district_id))
        if province_id:
            tags.append(format_tag("province", province_id))
        if biome:
            tags.append(format_tag("biome", biome))

        # 3. Add scope (KEY TAG — will be updated at higher layers)
        tags.append(format_tag("scope", scope))

        # 4. RECREATE significance (not inherited — fresh judgment)
        tags.append(format_tag("significance", significance))

        # 5. Add any evaluator-specific extra tags
        if extra_tags:
            for tag in extra_tags:
                if tag not in tags:
                    tags.append(tag)

        # Deduplicate while preserving order
        seen = set()
        deduped = []
        for tag in tags:
            if tag not in seen:
                seen.add(tag)
                deduped.append(tag)

        return deduped


# ══════════════════════════════════════════════════════════════════
# LAYER 3+: Inheritance with layer-specific additions
# ══════════════════════════════════════════════════════════════════

class HigherLayerTagAssigner:
    """Assigns tags to Layer 3+ events.

    Default behavior: inherit from origin layer events + add layer-specific tags.
    Significance is RECREATED. Key tags (scope, urgency, address) are UPDATED.

    At Layer 4+ (configurable), gains ability to REWRITE entire tag set.
    This is where LLM rewrites all tags ordered by importance, not just appends.

    LLM integration point: receives inherited tags as INPUT CONTEXT plus:
    - Layer 3: origin Layer 2 events + locality context
    - Layer 4: origin Layer 3 events + district context + faction data
    - Layer 5: origin Layer 4 events + province context + political data
    - Layer 6: origin Layer 5 events + cross-province data
    - Layer 7: origin Layer 6 events + world context
    """

    # Which layer gains full rewrite capability (configurable)
    REWRITE_ENABLED_FROM_LAYER = 4

    def assign_tags(self, layer: int,
                    origin_event_tags: List[List[str]],
                    significance: str = "minor",
                    layer_specific_tags: Optional[List[str]] = None,
                    rewrite_all: Optional[List[str]] = None) -> List[str]:
        """Build tag set for a higher-layer event.

        Args:
            layer: Which layer this is (3-7).
            origin_event_tags: List of tag arrays from origin events.
            significance: RECREATED significance for this layer.
            layer_specific_tags: New tags from this layer's categories.
            rewrite_all: If provided (Layer 4+), replaces entire tag set.
                         This is the LLM's complete rewrite output.

        Returns:
            Complete tag list for this event.
        """
        # Full rewrite path (Layer 4+ when LLM provides it)
        if rewrite_all is not None and layer >= self.REWRITE_ENABLED_FROM_LAYER:
            # LLM has rewritten everything — trust its ordering
            # But ensure significance is recreated (LLM should include it,
            # but we enforce it)
            tags = list(rewrite_all)
            self._ensure_significance(tags, significance)
            return tags

        # Inheritance path: merge origin tags + add new
        inherited = self._merge_origin_tags(origin_event_tags)

        # Remove recreated tags (significance) — will be added fresh
        recreated_categories = {k for k in get_recreated_tags()}
        inherited = [t for t in inherited
                     if parse_tag(t)[0] not in recreated_categories]

        # Update key tags if layer-specific values provided
        if layer_specific_tags:
            key_categories = {k for k in get_key_tags()}
            # Remove old key tag values that are being updated
            new_key_cats = {parse_tag(t)[0] for t in layer_specific_tags
                           if parse_tag(t)[0] in key_categories}
            inherited = [t for t in inherited
                         if parse_tag(t)[0] not in new_key_cats]

        # Build final tag set
        tags = list(inherited)

        # Add recreated significance
        tags.append(format_tag("significance", significance))

        # Add layer-specific tags
        if layer_specific_tags:
            for tag in layer_specific_tags:
                if tag not in tags:
                    tags.append(tag)

        # Deduplicate
        seen = set()
        deduped = []
        for tag in tags:
            if tag not in seen:
                seen.add(tag)
                deduped.append(tag)

        return deduped

    def _merge_origin_tags(self, origin_event_tags: List[List[str]]) -> List[str]:
        """Merge tags from multiple origin events, preserving order by frequency.

        Tags that appear in more origin events come first (more representative).
        Within same frequency, order of first appearance is preserved.
        """
        tag_count: Dict[str, int] = {}
        tag_first_seen: Dict[str, int] = {}
        idx = 0

        for event_tags in origin_event_tags:
            for tag in event_tags:
                tag_count[tag] = tag_count.get(tag, 0) + 1
                if tag not in tag_first_seen:
                    tag_first_seen[tag] = idx
                    idx += 1

        # Sort by frequency (desc) then first appearance (asc)
        sorted_tags = sorted(
            tag_count.keys(),
            key=lambda t: (-tag_count[t], tag_first_seen[t])
        )
        return sorted_tags

    def _ensure_significance(self, tags: List[str], significance: str) -> None:
        """Ensure significance tag is present and correct."""
        sig_tag = format_tag("significance", significance)
        # Remove any existing significance
        tags[:] = [t for t in tags if not t.startswith("significance:")]
        # Add the correct one
        tags.append(sig_tag)


# ══════════════════════════════════════════════════════════════════
# CONVENIENCE: Single entry point
# ══════════════════════════════════════════════════════════════════

_layer1_mapper: Optional[Layer1TagMapper] = None
_layer2_assigner = Layer2TagAssigner()
_higher_assigner = HigherLayerTagAssigner()


def get_layer1_mapper() -> Layer1TagMapper:
    """Get or create the Layer 1 tag mapper (singleton-ish, lazy load)."""
    global _layer1_mapper
    if _layer1_mapper is None:
        _layer1_mapper = Layer1TagMapper()
    return _layer1_mapper


def assign_layer1_tags(stat_key: str) -> List[str]:
    """Get tags for a Layer 1 stat key."""
    return get_layer1_mapper().get_tags(stat_key)


def assign_layer2_tags(origin_stat_key: str, **kwargs) -> List[str]:
    """Build Layer 2 tags by inheriting from Layer 1 + adding context."""
    origin_tags = assign_layer1_tags(origin_stat_key)
    return _layer2_assigner.assign_tags(origin_stat_tags=origin_tags, **kwargs)


def assign_higher_layer_tags(layer: int,
                             origin_event_tags: List[List[str]],
                             **kwargs) -> List[str]:
    """Build Layer 3+ tags by inheriting + adding layer-specific."""
    return _higher_assigner.assign_tags(layer=layer,
                                        origin_event_tags=origin_event_tags,
                                        **kwargs)


def reset_mapper() -> None:
    """Reset the Layer 1 mapper (for testing)."""
    global _layer1_mapper
    _layer1_mapper = None

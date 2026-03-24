"""Tag matching and relevance scoring for the interest tag system.

Tags follow the format "category:value" (e.g., "resource:iron", "biome:forest").
Relevance is scored by category overlap between entity interest tags and event tags.
"""

from __future__ import annotations

from typing import Dict, List, Set, Tuple


def parse_tag(tag: str) -> Tuple[str, str]:
    """Split a tag into (category, value). Plain tags become (tag, tag)."""
    if ":" in tag:
        cat, val = tag.split(":", 1)
        return cat, val
    return tag, tag


def build_tag_categories(tags: List[str]) -> Dict[str, Set[str]]:
    """Group tags by category for efficient matching."""
    cats: Dict[str, Set[str]] = {}
    for tag in tags:
        cat, val = parse_tag(tag)
        cats.setdefault(cat, set()).add(val)
    return cats


def calculate_relevance(entity_tags: List[str], event_tags: List[str]) -> float:
    """Score how relevant an event is to an entity based on tag overlap.

    Returns 0.0 (irrelevant) to 1.0 (directly relevant).

    Scoring:
    - Exact tag match (same category + value): full point
    - Category match (same category, different value): 0.3 points
    - Result is fraction of event categories matched
    """
    if not entity_tags or not event_tags:
        return 0.0

    entity_cats = build_tag_categories(entity_tags)
    event_cats = build_tag_categories(event_tags)

    matches = 0.0
    total = len(event_cats)
    if total == 0:
        return 0.0

    for cat, vals in event_cats.items():
        if cat in entity_cats:
            if entity_cats[cat] & vals:
                matches += 1.0  # Exact match
            else:
                matches += 0.3  # Same category, different value

    return min(1.0, matches / total)


def tags_overlap(tags_a: List[str], tags_b: List[str]) -> bool:
    """Quick check: do any tags match exactly?"""
    return bool(set(tags_a) & set(tags_b))


def tags_overlap_by_category(tags_a: List[str], tags_b: List[str]) -> bool:
    """Check if tags share any categories (even with different values)."""
    cats_a = {parse_tag(t)[0] for t in tags_a}
    cats_b = {parse_tag(t)[0] for t in tags_b}
    return bool(cats_a & cats_b)

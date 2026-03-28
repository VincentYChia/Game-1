"""Tag Pattern Browser — search, list, and inspect all tracked stat patterns.

Usage:
    python -m world_system.world_memory.tag_browser
    python -m world_system.world_memory.tag_browser search "combat.kills"
    python -m world_system.world_memory.tag_browser search "turret"
    python -m world_system.world_memory.tag_browser stats
"""

from __future__ import annotations

import json
import os
import sys
from typing import Dict, List, Optional


def load_patterns() -> List[Dict]:
    """Load all patterns from the Layer 1 tag mapping file."""
    this_dir = os.path.dirname(os.path.abspath(__file__))
    config_path = os.path.join(this_dir, "..", "config", "layer1-stat-tags.json")
    config_path = os.path.normpath(config_path)

    with open(config_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    return [m for m in data.get("mappings", []) if "pattern" in m]


def search_patterns(query: str, patterns: Optional[List[Dict]] = None) -> List[Dict]:
    """Search patterns by substring match on pattern or any tag."""
    if patterns is None:
        patterns = load_patterns()

    query = query.lower()
    results = []
    for p in patterns:
        if query in p["pattern"].lower():
            results.append(p)
        elif any(query in t.lower() for t in p["tags"]):
            results.append(p)
    return results


def get_stats(patterns: Optional[List[Dict]] = None) -> Dict:
    """Get summary statistics about tracked patterns."""
    if patterns is None:
        patterns = load_patterns()

    tags_per = [len(p["tags"]) for p in patterns]
    domains = {}
    tag_categories = {}

    for p in patterns:
        domain = p["pattern"].split(".")[0]
        domains[domain] = domains.get(domain, 0) + 1
        for tag in p["tags"]:
            if ":" in tag:
                cat = tag.split(":")[0]
                tag_categories[cat] = tag_categories.get(cat, 0) + 1

    return {
        "total_patterns": len(patterns),
        "tags_min": min(tags_per) if tags_per else 0,
        "tags_max": max(tags_per) if tags_per else 0,
        "tags_avg": sum(tags_per) / len(tags_per) if tags_per else 0,
        "patterns_8plus": sum(1 for t in tags_per if t >= 8),
        "domains": dict(sorted(domains.items(), key=lambda x: -x[1])),
        "tag_categories_used": dict(sorted(tag_categories.items(), key=lambda x: -x[1])),
    }


def print_patterns(patterns: List[Dict], max_show: int = 50) -> None:
    """Pretty-print patterns."""
    for i, p in enumerate(patterns[:max_show]):
        print(f"  {p['pattern']}")
        print(f"    Tags ({len(p['tags'])}): {p['tags']}")
    if len(patterns) > max_show:
        print(f"  ... and {len(patterns) - max_show} more")


def main():
    patterns = load_patterns()

    if len(sys.argv) < 2:
        # Default: show summary
        stats = get_stats(patterns)
        print(f"=== Layer 1 Tag Pattern Browser ===")
        print(f"Total patterns: {stats['total_patterns']}")
        print(f"Tags per pattern: {stats['tags_min']}-{stats['tags_max']} (avg {stats['tags_avg']:.1f})")
        print(f"Patterns with 8+ tags: {stats['patterns_8plus']}")
        print(f"\nPatterns by domain:")
        for domain, count in stats["domains"].items():
            print(f"  {domain}: {count}")
        print(f"\nTag categories used (top 15):")
        for cat, count in list(stats["tag_categories_used"].items())[:15]:
            print(f"  {cat}: {count}")
        return

    command = sys.argv[1]

    if command == "search" and len(sys.argv) > 2:
        query = sys.argv[2]
        results = search_patterns(query, patterns)
        print(f"=== Search: '{query}' — {len(results)} results ===")
        print_patterns(results)

    elif command == "stats":
        stats = get_stats(patterns)
        print(json.dumps(stats, indent=2))

    elif command == "list":
        domain_filter = sys.argv[2] if len(sys.argv) > 2 else None
        filtered = patterns
        if domain_filter:
            filtered = [p for p in patterns if p["pattern"].startswith(domain_filter)]
        print(f"=== All patterns{f' in {domain_filter}' if domain_filter else ''}: {len(filtered)} ===")
        print_patterns(filtered, max_show=200)

    elif command == "gaps":
        # Show which domains have fewer patterns
        stats = get_stats(patterns)
        print("=== Coverage by domain ===")
        for domain, count in stats["domains"].items():
            indicator = "✓" if count >= 10 else "⚠" if count >= 5 else "✗"
            print(f"  {indicator} {domain}: {count} patterns")

    else:
        print(f"Unknown command: {command}")
        print("Usage: tag_browser [search <query>|stats|list [domain]|gaps]")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Stat Catalog — Comprehensive inventory of all Layer 1 stats tracked by the World Memory System.

Generates a full catalog of:
- All record_* methods and their parameters
- All stat key patterns written to StatStore
- Dimensional breakdowns (what sub-keys each method creates)
- Wiring status (called from game code or orphaned)
- Coverage gaps (methods that exist but have no call site)

Usage:
    python tools/stat_catalog.py                  # Full catalog to stdout
    python tools/stat_catalog.py --json           # JSON output
    python tools/stat_catalog.py --summary        # Quick summary only
    python tools/stat_catalog.py --orphans        # Show only orphaned methods
    python tools/stat_catalog.py --search combat  # Search stat keys by prefix
"""

import ast
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Optional, Set


@dataclass
class StatMethod:
    """A record_* method in StatTracker."""
    name: str
    params: List[str]
    line_number: int
    stat_keys: List[str] = field(default_factory=list)
    dimensional_keys: List[str] = field(default_factory=list)
    call_sites: List[str] = field(default_factory=list)
    is_orphaned: bool = True
    category: str = ""


@dataclass
class StatCatalog:
    """Complete catalog of Layer 1 stat tracking."""
    methods: List[StatMethod] = field(default_factory=list)
    total_methods: int = 0
    wired_methods: int = 0
    orphaned_methods: int = 0
    total_stat_keys: int = 0
    categories: Dict[str, int] = field(default_factory=dict)


def find_project_root() -> str:
    """Find Game-1-modular root."""
    d = os.path.dirname(os.path.abspath(__file__))
    while d != '/':
        if os.path.exists(os.path.join(d, 'main.py')) and os.path.exists(os.path.join(d, 'entities')):
            return d
        d = os.path.dirname(d)
    return os.path.dirname(os.path.abspath(__file__))


def parse_stat_tracker(filepath: str) -> List[StatMethod]:
    """Parse StatTracker to extract all record_* methods."""
    with open(filepath, 'r') as f:
        content = f.read()
        lines = content.split('\n')

    methods = []
    for i, line in enumerate(lines, 1):
        match = re.match(r'\s+def (record_\w+)\(self', line)
        if match:
            name = match.group(1)

            # Collect full signature (may span multiple lines)
            sig_lines = [line]
            j = i  # i is 1-based, j starts at next line (0-based index i)
            while j < len(lines) and ')' not in ''.join(sig_lines):
                sig_lines.append(lines[j])
                j += 1
            full_sig = ' '.join(l.strip() for l in sig_lines)

            # Extract params
            paren_match = re.search(r'\(self[,\s]*(.*?)\)', full_sig)
            params_str = paren_match.group(1) if paren_match else ""
            params = [p.strip().split(':')[0].split('=')[0].strip()
                      for p in params_str.split(',') if p.strip()]

            category = _categorize_method(name)
            stat_keys, dim_keys = _extract_keys(lines, i - 1)

            methods.append(StatMethod(
                name=name,
                params=params,
                line_number=i,
                stat_keys=stat_keys,
                dimensional_keys=dim_keys,
                category=category,
            ))

    return methods


def _categorize_method(name: str) -> str:
    """Categorize a record method by its prefix."""
    prefixes = {
        'record_resource': 'gathering', 'record_fish': 'gathering',
        'record_fishing': 'gathering', 'record_gathering': 'gathering',
        'record_tool': 'gathering', 'record_node': 'gathering',
        'record_crafting': 'crafting', 'record_invention': 'crafting',
        'record_recipe': 'crafting', 'record_enchantment': 'crafting',
        'record_damage': 'combat', 'record_enemy': 'combat',
        'record_status': 'combat', 'record_death': 'combat',
        'record_attack': 'combat', 'record_dodge': 'combat',
        'record_combo': 'combat', 'record_projectile': 'combat',
        'record_healing': 'combat', 'record_reflect': 'combat',
        'record_weapon': 'combat', 'record_items_lost': 'combat',
        'record_item': 'items', 'record_equipment': 'items',
        'record_repair': 'items', 'record_barrier': 'items',
        'record_skill': 'skills', 'record_movement': 'exploration',
        'record_chunk': 'exploration', 'record_landmark': 'exploration',
        'record_gold': 'economy', 'record_trade': 'economy',
        'record_level': 'progression', 'record_exp': 'progression',
        'record_title': 'progression', 'record_class': 'progression',
        'record_dungeon': 'dungeons', 'record_npc': 'social',
        'record_quest': 'social', 'record_activity': 'time',
        'record_session': 'time', 'record_menu': 'time',
        'record_idle': 'time', 'record_personal': 'records',
        'record_combat_dur': 'records', 'record_fastest': 'records',
        'record_rate': 'records', 'record_first': 'encyclopedia',
        'record_encyclopedia': 'encyclopedia', 'record_save': 'misc',
        'record_game': 'misc', 'record_debug': 'misc',
    }
    for prefix, cat in prefixes.items():
        if name.startswith(prefix):
            return cat
    return 'misc'


def _extract_keys(lines: List[str], method_start: int) -> tuple:
    """Extract stat keys written by a method."""
    stat_keys = []
    dim_keys = []

    # Find method body (until next def or class at same/less indent)
    indent = len(lines[method_start]) - len(lines[method_start].lstrip())
    end = method_start + 1
    while end < len(lines):
        line = lines[end]
        if line.strip() and not line.strip().startswith('#'):
            line_indent = len(line) - len(line.lstrip())
            if line_indent <= indent and (line.strip().startswith('def ') or line.strip().startswith('class ')):
                break
        end += 1

    body = '\n'.join(lines[method_start:end])

    # Extract direct stat keys
    for match in re.finditer(r'(?:record_count|record|set_value)\([f]?["\']([^"\']*)["\']', body):
        key = re.sub(r'\{[^}]*\}', '*', match.group(1))
        stat_keys.append(key)

    # Extract build_dimensional_keys calls
    for match in re.finditer(r'build_dimensional_keys\([f]?["\']([^"\']*)["\']', body):
        dim_keys.append(match.group(1) + '.*')

    return list(set(stat_keys)), list(set(dim_keys))


def find_call_sites(method_name: str, project_root: str) -> List[str]:
    """Find all call sites for a stat_tracker method."""
    try:
        result = subprocess.run(
            ['grep', '-rn', f'.{method_name}(', '--include=*.py', project_root],
            capture_output=True, text=True, timeout=10
        )
        sites = []
        for line in result.stdout.strip().split('\n'):
            if line and 'stat_tracker.py' not in line and '__pycache__' not in line and 'test_' not in line:
                # Simplify path
                path = line.split(':')[0].replace(project_root + '/', '')
                lineno = line.split(':')[1] if ':' in line else '?'
                sites.append(f"{path}:{lineno}")
        return sites
    except Exception:
        return []


def build_catalog(project_root: str) -> StatCatalog:
    """Build the complete stat catalog."""
    tracker_path = os.path.join(project_root, 'entities', 'components', 'stat_tracker.py')
    methods = parse_stat_tracker(tracker_path)

    # Find call sites for each method
    for method in methods:
        method.call_sites = find_call_sites(method.name, project_root)
        # Also check indirect calls via wrapper methods
        if not method.call_sites:
            method.call_sites = find_call_sites(method.name.replace('record_', ''), project_root)
        method.is_orphaned = len(method.call_sites) == 0

    # Build summary
    catalog = StatCatalog(methods=methods)
    catalog.total_methods = len(methods)
    catalog.wired_methods = sum(1 for m in methods if not m.is_orphaned)
    catalog.orphaned_methods = sum(1 for m in methods if m.is_orphaned)

    all_keys = set()
    for m in methods:
        all_keys.update(m.stat_keys)
        all_keys.update(m.dimensional_keys)
    catalog.total_stat_keys = len(all_keys)

    for m in methods:
        catalog.categories[m.category] = catalog.categories.get(m.category, 0) + 1

    return catalog


def print_catalog(catalog: StatCatalog, show_orphans_only: bool = False, search: str = ""):
    """Print human-readable catalog."""
    print("=" * 80)
    print("LAYER 1 STAT CATALOG — World Memory System")
    print("=" * 80)
    print(f"\nTotal record_* methods: {catalog.total_methods}")
    print(f"Wired (called from game code): {catalog.wired_methods}")
    print(f"Orphaned (no call site): {catalog.orphaned_methods}")
    print(f"Coverage: {catalog.wired_methods}/{catalog.total_methods} ({100*catalog.wired_methods//catalog.total_methods}%)")
    print(f"Unique stat key patterns: {catalog.total_stat_keys}")

    print(f"\nBy Category:")
    for cat, count in sorted(catalog.categories.items()):
        wired = sum(1 for m in catalog.methods if m.category == cat and not m.is_orphaned)
        print(f"  {cat:20s}: {wired}/{count} wired")

    # Group methods by category
    by_cat = {}
    for m in catalog.methods:
        by_cat.setdefault(m.category, []).append(m)

    for cat in sorted(by_cat.keys()):
        methods = by_cat[cat]
        if show_orphans_only:
            methods = [m for m in methods if m.is_orphaned]
            if not methods:
                continue

        print(f"\n{'─' * 80}")
        print(f"  {cat.upper()}")
        print(f"{'─' * 80}")

        for m in methods:
            if search and search.lower() not in m.name.lower() and not any(search.lower() in k.lower() for k in m.stat_keys + m.dimensional_keys):
                continue

            status = "✅" if not m.is_orphaned else "❌ ORPHANED"
            print(f"\n  {m.name}({', '.join(m.params)})")
            print(f"    Line: {m.line_number} | Status: {status}")

            if m.stat_keys:
                print(f"    Static keys: {', '.join(sorted(m.stat_keys)[:8])}")
            if m.dimensional_keys:
                print(f"    Dimensional: {', '.join(sorted(m.dimensional_keys))}")
            if m.call_sites:
                for site in m.call_sites[:3]:
                    print(f"    Called from: {site}")
                if len(m.call_sites) > 3:
                    print(f"    ... and {len(m.call_sites) - 3} more")

    print(f"\n{'=' * 80}")
    print("END OF CATALOG")
    print(f"{'=' * 80}")


def print_json(catalog: StatCatalog):
    """Print JSON catalog."""
    data = {
        'summary': {
            'total_methods': catalog.total_methods,
            'wired_methods': catalog.wired_methods,
            'orphaned_methods': catalog.orphaned_methods,
            'coverage_pct': round(100 * catalog.wired_methods / max(catalog.total_methods, 1), 1),
            'total_stat_keys': catalog.total_stat_keys,
            'categories': catalog.categories,
        },
        'methods': [asdict(m) for m in catalog.methods],
    }
    print(json.dumps(data, indent=2))


def main():
    project_root = find_project_root()
    args = sys.argv[1:]

    catalog = build_catalog(project_root)

    if '--json' in args:
        print_json(catalog)
    elif '--summary' in args:
        print(f"Layer 1 Stats: {catalog.wired_methods}/{catalog.total_methods} wired ({100*catalog.wired_methods//catalog.total_methods}%)")
        print(f"Orphaned: {catalog.orphaned_methods}")
        print(f"Stat key patterns: {catalog.total_stat_keys}")
        for cat, count in sorted(catalog.categories.items()):
            wired = sum(1 for m in catalog.methods if m.category == cat and not m.is_orphaned)
            print(f"  {cat}: {wired}/{count}")
    elif '--orphans' in args:
        print_catalog(catalog, show_orphans_only=True)
    elif '--search' in args:
        idx = args.index('--search')
        search = args[idx + 1] if idx + 1 < len(args) else ""
        print_catalog(catalog, search=search)
    else:
        print_catalog(catalog)


if __name__ == '__main__':
    main()

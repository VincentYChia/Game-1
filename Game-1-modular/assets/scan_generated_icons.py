#!/usr/bin/env python3
"""
Vheer Generated Icons Scanner

Scans all icons-generated-cycle-N folders and counts PNG files by category.
Helps identify missing or misnamed icons.

Usage:
    python scan_generated_icons.py [--detail] [--compare-catalog]
"""

import os
from pathlib import Path
from collections import defaultdict
import argparse

# Script location
SCRIPT_DIR = Path(__file__).parent

# Categories we expect to find
EXPECTED_CATEGORIES = ['classes', 'enemies', 'items', 'npcs', 'quests', 'resources', 'skills', 'titles']

# Resource name mapping (from Vheer-automation.py) - catalog name -> file name
RESOURCE_NAME_MAP = {
    'copper_vein': 'copper_ore_node',
    'iron_deposit': 'iron_ore_node',
    'limestone_outcrop': 'limestone_node',
    'granite_formation': 'granite_node',
    'mithril_cache': 'mithril_ore_node',
    'obsidian_flow': 'obsidian_node',
    'steel_node': 'steel_ore_node',
}

def get_base_name(filename):
    """Extract base name from versioned filename (e.g., 'iron_sword-2.png' -> 'iron_sword')"""
    name = filename.lower()
    if name.endswith('.png'):
        name = name[:-4]
    # Remove version suffix like -2, -3, etc.
    parts = name.rsplit('-', 1)
    if len(parts) == 2 and parts[1].isdigit():
        return parts[0]
    return name

def scan_folder(folder_path):
    """Scan a folder and return dict of {base_name: [versions]}"""
    files = defaultdict(list)
    if not folder_path.exists():
        return files

    for f in folder_path.iterdir():
        if f.is_file() and f.suffix.lower() == '.png':
            base = get_base_name(f.name)
            # Extract version number
            name_no_ext = f.stem.lower()
            parts = name_no_ext.rsplit('-', 1)
            if len(parts) == 2 and parts[1].isdigit():
                version = int(parts[1])
            else:
                version = 1
            files[base].append((version, f.name, f.stat().st_size))

    return files

def scan_cycle(cycle_path):
    """Scan a cycle folder and return stats"""
    results = {}

    # Find version folders (generated_icons-N)
    version_folders = sorted([d for d in cycle_path.iterdir()
                              if d.is_dir() and d.name.startswith('generated_icons')])

    for ver_folder in version_folders:
        ver_name = ver_folder.name
        results[ver_name] = {}

        for category in EXPECTED_CATEGORIES:
            cat_path = ver_folder / category
            if category == 'items':
                # Items has subfolders
                all_items = defaultdict(list)
                if cat_path.exists():
                    for subdir in cat_path.iterdir():
                        if subdir.is_dir():
                            items = scan_folder(subdir)
                            for base, versions in items.items():
                                all_items[base].extend(versions)
                results[ver_name][category] = all_items
            else:
                results[ver_name][category] = scan_folder(cat_path)

    return results

def print_summary(all_results):
    """Print summary of all cycles"""
    print("\n" + "="*80)
    print("VHEER GENERATED ICONS SCAN SUMMARY")
    print("="*80)

    for cycle_name, cycle_data in sorted(all_results.items()):
        print(f"\n📁 {cycle_name}")
        print("-"*60)

        for ver_name, categories in sorted(cycle_data.items()):
            print(f"\n  📂 {ver_name}:")
            total = 0
            for cat_name in EXPECTED_CATEGORIES:
                cat_data = categories.get(cat_name, {})
                count = len(cat_data)
                total += count
                if count > 0:
                    print(f"      {cat_name}: {count} unique items")
            print(f"      ─────────────────")
            print(f"      TOTAL: {total} unique items")

def print_detail(all_results, category_filter=None):
    """Print detailed file listing"""
    print("\n" + "="*80)
    print("DETAILED FILE LISTING")
    print("="*80)

    for cycle_name, cycle_data in sorted(all_results.items()):
        print(f"\n{'='*80}")
        print(f"📁 {cycle_name}")
        print("="*80)

        for ver_name, categories in sorted(cycle_data.items()):
            print(f"\n  📂 {ver_name}")

            for cat_name in EXPECTED_CATEGORIES:
                if category_filter and cat_name != category_filter:
                    continue

                cat_data = categories.get(cat_name, {})
                if cat_data:
                    print(f"\n    [{cat_name}] ({len(cat_data)} items)")
                    for base_name, versions in sorted(cat_data.items()):
                        versions_str = ', '.join(f"v{v[0]}" for v in sorted(versions))
                        print(f"      • {base_name}: {versions_str}")

def check_resource_mapping():
    """Check if resource files use mapped names or original names"""
    print("\n" + "="*80)
    print("RESOURCE NAME MAPPING CHECK")
    print("="*80)
    print("\nChecking if resources use catalog names or mapped file names...\n")

    # Check cycle-2/generated_icons-2/resources as sample
    sample_path = SCRIPT_DIR / "icons-generated-cycle-2" / "generated_icons-2" / "resources"

    if not sample_path.exists():
        print(f"Sample path not found: {sample_path}")
        return

    existing_files = [f.stem.lower() for f in sample_path.iterdir() if f.suffix.lower() == '.png']

    print("Resource Name Mapping Status:")
    print("-"*60)
    for catalog_name, file_name in RESOURCE_NAME_MAP.items():
        # Check both names (with version suffixes)
        catalog_found = any(f.startswith(catalog_name) for f in existing_files)
        file_found = any(f.startswith(file_name) for f in existing_files)

        status_catalog = "✓" if catalog_found else "✗"
        status_file = "✓" if file_found else "✗"

        print(f"  {catalog_name}:")
        print(f"    Catalog name ({catalog_name}): {status_catalog}")
        print(f"    Mapped name ({file_name}): {status_file}")

        if not catalog_found and not file_found:
            print(f"    ⚠️  NEITHER FOUND!")
        elif catalog_found and file_found:
            print(f"    ℹ️  Both names exist (possible duplicate)")
        print()

def compare_with_catalog():
    """Compare generated files against the item catalog"""
    print("\n" + "="*80)
    print("CATALOG COMPARISON")
    print("="*80)

    catalog_path = SCRIPT_DIR / "icons" / "ITEM_CATALOG_FOR_ICONS.md"
    if not catalog_path.exists():
        print(f"Catalog not found: {catalog_path}")
        return

    # Parse catalog to extract item names by category
    catalog_items = defaultdict(set)
    current_category = None

    with open(catalog_path, 'r') as f:
        for line in f:
            line = line.strip()
            if line.startswith('## '):
                # Section header like "## Resources" or "## Equipment"
                section = line[3:].lower()
                if 'resource' in section:
                    current_category = 'resources'
                elif 'equipment' in section or 'weapon' in section or 'armor' in section or 'tool' in section:
                    current_category = 'items'
                elif 'skill' in section:
                    current_category = 'skills'
                elif 'enemy' in section or 'hostile' in section:
                    current_category = 'enemies'
                elif 'class' in section:
                    current_category = 'classes'
                elif 'title' in section:
                    current_category = 'titles'
                elif 'npc' in section:
                    current_category = 'npcs'
                elif 'quest' in section:
                    current_category = 'quests'
            elif line.startswith('### ') and current_category:
                # Item name like "### iron_sword"
                item_name = line[4:].strip().lower()
                catalog_items[current_category].add(item_name)

    print(f"\nCatalog contains:")
    for cat, items in sorted(catalog_items.items()):
        print(f"  {cat}: {len(items)} items")

    # Now compare against generated files
    # Use cycle-2 as reference
    cycle_path = SCRIPT_DIR / "icons-generated-cycle-2" / "generated_icons-2"

    print(f"\nComparing against: {cycle_path}")
    print("-"*60)

    for category in ['resources', 'items', 'skills', 'enemies']:
        if category not in catalog_items:
            continue

        catalog_set = catalog_items[category]

        # Get generated files
        if category == 'items':
            cat_path = cycle_path / category
            generated = set()
            if cat_path.exists():
                for subdir in cat_path.iterdir():
                    if subdir.is_dir():
                        for f in subdir.iterdir():
                            if f.suffix.lower() == '.png':
                                generated.add(get_base_name(f.name))
        else:
            cat_path = cycle_path / category
            generated = set()
            if cat_path.exists():
                for f in cat_path.iterdir():
                    if f.suffix.lower() == '.png':
                        generated.add(get_base_name(f.name))

        # For resources, also check mapped names
        if category == 'resources':
            # Add reverse mapping
            reverse_map = {v: k for k, v in RESOURCE_NAME_MAP.items()}
            expanded_generated = set(generated)
            for g in generated:
                if g in reverse_map:
                    expanded_generated.add(reverse_map[g])
            generated = expanded_generated

        in_catalog_only = catalog_set - generated
        in_generated_only = generated - catalog_set

        print(f"\n[{category.upper()}]")
        print(f"  Catalog: {len(catalog_set)}, Generated: {len(generated)}")

        if in_catalog_only:
            print(f"  ⚠️  In catalog but NOT generated ({len(in_catalog_only)}):")
            for item in sorted(in_catalog_only)[:10]:
                print(f"      - {item}")
            if len(in_catalog_only) > 10:
                print(f"      ... and {len(in_catalog_only) - 10} more")

        if in_generated_only:
            print(f"  ℹ️  Generated but NOT in catalog ({len(in_generated_only)}):")
            for item in sorted(in_generated_only)[:5]:
                print(f"      - {item}")
            if len(in_generated_only) > 5:
                print(f"      ... and {len(in_generated_only) - 5} more")

def cross_cycle_comparison(all_results, category='resources'):
    """Compare a category across all cycles to find missing items"""
    print("\n" + "="*80)
    print(f"CROSS-CYCLE {category.upper()} COMPARISON")
    print("="*80)
    print(f"\nComparing {category} across all cycles to identify missing files...\n")

    # Build reverse map: file_name -> catalog_name
    reverse_map = {v: k for k, v in RESOURCE_NAME_MAP.items()}

    def normalize_name(name):
        """Normalize item name to canonical form (catalog name)"""
        # If it's a mapped file name, convert to catalog name
        if name in reverse_map:
            return reverse_map[name]
        # If it's already a catalog name or unmapped, use as-is
        return name

    # Build a matrix: {normalized_name: {cycle/version: [actual_names]}}
    all_items = set()
    item_presence = defaultdict(lambda: defaultdict(list))

    for cycle_name, cycle_data in all_results.items():
        for ver_name, categories in cycle_data.items():
            cat_data = categories.get(category, {})

            # Track all items found (normalized)
            for item_name in cat_data.keys():
                normalized = normalize_name(item_name) if category == 'resources' else item_name
                all_items.add(normalized)

            # Mark presence with actual name found
            key = f"{cycle_name}/{ver_name}"
            for item_name in cat_data.keys():
                normalized = normalize_name(item_name) if category == 'resources' else item_name
                item_presence[normalized][key].append(item_name)

    # Get all cycle/version keys
    all_keys = set()
    for cycle_name, cycle_data in all_results.items():
        for ver_name in cycle_data.keys():
            all_keys.add(f"{cycle_name}/{ver_name}")
    all_keys = sorted(all_keys)

    # Find items that are missing in at least one cycle/version
    items_with_gaps = []
    for item_name in sorted(all_items):
        presence = item_presence[item_name]
        missing_in = [k for k in all_keys if k not in presence]
        if missing_in:
            items_with_gaps.append((item_name, missing_in, len(all_keys) - len(missing_in)))

    # Sort by how many cycles have it (most coverage first)
    items_with_gaps.sort(key=lambda x: -x[2])

    if not items_with_gaps:
        print(f"✓ All {len(all_items)} {category} items are present in all cycles!")
    else:
        print(f"Found {len(items_with_gaps)} {category} items with incomplete coverage:\n")
        print("-"*80)

        for item_name, missing_in, count in items_with_gaps:
            coverage_pct = count / len(all_keys) * 100
            print(f"\n  {item_name} ({count}/{len(all_keys)} = {coverage_pct:.0f}% coverage)")
            print(f"    Missing in:")
            for m in missing_in[:10]:
                print(f"      - {m}")
            if len(missing_in) > 10:
                print(f"      ... and {len(missing_in) - 10} more")

    # Summary by cycle
    print("\n" + "-"*80)
    print("COVERAGE BY CYCLE:")
    print("-"*80)
    for key in all_keys:
        count = sum(1 for item in all_items if key in item_presence[item])
        pct = count / len(all_items) * 100 if all_items else 0
        status = "✓" if count == len(all_items) else "⚠"
        print(f"  {status} {key}: {count}/{len(all_items)} ({pct:.1f}%)")


def main():
    parser = argparse.ArgumentParser(description='Scan Vheer generated icon folders')
    parser.add_argument('--detail', '-d', action='store_true', help='Show detailed file listing')
    parser.add_argument('--category', '-c', help='Filter detail view by category')
    parser.add_argument('--compare-catalog', '-C', action='store_true', help='Compare against item catalog')
    parser.add_argument('--check-mapping', '-m', action='store_true', help='Check resource name mapping')
    parser.add_argument('--cross-cycle', '-x', action='store_true', help='Show cross-cycle comparison for resources')
    parser.add_argument('--cross-cycle-cat', help='Category for cross-cycle comparison (default: resources)')
    args = parser.parse_args()

    print("Scanning Vheer generated icon folders...")
    print(f"Script location: {SCRIPT_DIR}")

    # Find all cycle folders
    cycle_folders = sorted([d for d in SCRIPT_DIR.iterdir()
                            if d.is_dir() and d.name.startswith('icons-generated-cycle')])

    if not cycle_folders:
        print("No icons-generated-cycle-* folders found!")
        return

    print(f"Found {len(cycle_folders)} cycle folders")

    # Scan all cycles
    all_results = {}
    for cycle_folder in cycle_folders:
        all_results[cycle_folder.name] = scan_cycle(cycle_folder)

    # Print summary
    print_summary(all_results)

    # Print detail if requested
    if args.detail:
        print_detail(all_results, args.category)

    # Check resource mapping
    if args.check_mapping:
        check_resource_mapping()

    # Compare with catalog
    if args.compare_catalog:
        compare_with_catalog()

    # Cross-cycle comparison
    if args.cross_cycle:
        category = args.cross_cycle_cat or 'resources'
        cross_cycle_comparison(all_results, category)

    print("\n" + "="*80)
    print("Scan complete!")
    print("="*80)

if __name__ == '__main__':
    main()

#!/usr/bin/env python3
"""
Update Vheer Catalog with New Content

Automatically adds new items, skills, and enemies to ITEM_CATALOG_FOR_ICONS.md
so that Vheer AI can generate proper icons for them.

Usage:
    python tools/update_catalog.py --json items.JSON/items-testing-integration.JSON
    python tools/update_catalog.py --update Update-1
"""

import os
import sys
import json
import argparse
from pathlib import Path
from datetime import datetime

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


def load_catalog(catalog_path: Path) -> tuple[str, dict]:
    """Load existing catalog and parse structure"""
    if not catalog_path.exists():
        return "", {}

    with open(catalog_path, 'r') as f:
        content = f.read()

    # Parse existing sections
    sections = {}
    current_section = None
    current_items = []

    for line in content.split('\n'):
        if line.startswith('## '):
            if current_section:
                sections[current_section] = current_items
            current_section = line[3:].strip()
            current_items = []
        elif line.startswith('### '):
            item_id = line[4:].strip()
            current_items.append(item_id)

    if current_section:
        sections[current_section] = current_items

    return content, sections


def format_catalog_entry(entity_id: str, entity_data: dict, entity_type: str) -> str:
    """Format a catalog entry for an entity"""
    entry = f"### {entity_id}\n"

    # Add metadata based on entity type
    if entity_type == 'item':
        item_type = entity_data.get('type', 'unknown')
        rarity = entity_data.get('rarity', 'common')
        entry += f"- **Category**: equipment\n"
        entry += f"- **Type**: {item_type}\n"
        entry += f"- **Rarity**: {rarity}\n"

        # Add narrative description
        description = entity_data.get('description', f'A {rarity} {item_type}')
        if 'tags' in entity_data:
            tags_str = ', '.join(entity_data['tags'][:3])
            description += f". Features: {tags_str}"

        entry += f"- **Narrative**: {description}\n"

    elif entity_type == 'skill':
        skill_tier = entity_data.get('tier', 1)
        effect_type = entity_data.get('effect', {}).get('type', 'unknown')
        entry += f"- **Category**: skill\n"
        entry += f"- **Tier**: {skill_tier}\n"
        entry += f"- **Type**: {effect_type}\n"

        description = entity_data.get('description', f'A tier {skill_tier} {effect_type} skill')
        entry += f"- **Narrative**: {description}\n"

    elif entity_type == 'enemy':
        enemy_tier = entity_data.get('tier', 1)
        enemy_type = entity_data.get('type', 'beast')
        entry += f"- **Category**: enemy\n"
        entry += f"- **Type**: {enemy_type}\n"
        entry += f"- **Tier**: {enemy_tier}\n"

        description = entity_data.get('description', f'A tier {enemy_tier} {enemy_type} enemy')
        entry += f"- **Narrative**: {description}\n"

    entry += "\n"
    return entry


def append_to_catalog(catalog_path: Path, new_entries: dict):
    """Append new entries to catalog"""
    content, existing_sections = load_catalog(catalog_path)

    # Generate new sections
    new_sections = []

    for section_name, entries in new_entries.items():
        if not entries:
            continue

        # Check if section exists
        section_header = f"## {section_name}"

        if section_name in existing_sections:
            # Section exists - check for duplicates
            existing_ids = set(existing_sections[section_name])
            new_entries_filtered = [e for e in entries if e['id'] not in existing_ids]

            if not new_entries_filtered:
                print(f"  ℹ️  All entries already in section: {section_name}")
                continue

            entries = new_entries_filtered

        # Format entries
        section_content = f"\n{section_header}\n\n"
        for entry in entries:
            section_content += format_catalog_entry(
                entry['id'],
                entry['data'],
                entry['type']
            )

        new_sections.append((section_name, section_content))

    if not new_sections:
        print("  ℹ️  No new entries to add to catalog")
        return

    # Append to catalog
    with open(catalog_path, 'a') as f:
        f.write("\n---\n\n")
        f.write(f"# NEW CONTENT - Added {datetime.now().strftime('%Y-%m-%d')}\n\n")
        for section_name, section_content in new_sections:
            f.write(section_content)
            print(f"  ✅ Added section: {section_name} ({len([e for e in entries if e])} entries)")


def process_items_json(json_path: Path) -> dict:
    """Extract items from JSON for catalog"""
    with open(json_path, 'r') as f:
        data = json.load(f)

    items = data.get('items', [])
    entries = {}

    for item in items:
        item_id = item.get('itemId')
        item_type = item.get('type', 'material')

        # Categorize items
        if item_type in ['weapon', 'bow', 'staff', 'dagger']:
            category = 'EQUIPMENT - WEAPONS (Test)'
        elif item_type in ['armor', 'helmet', 'chestplate', 'boots']:
            category = 'EQUIPMENT - ARMOR (Test)'
        elif item_type in ['accessory', 'ring', 'amulet']:
            category = 'EQUIPMENT - ACCESSORIES (Test)'
        else:
            category = f'ITEMS - {item_type.upper()} (Test)'

        if category not in entries:
            entries[category] = []

        entries[category].append({
            'id': item_id,
            'data': item,
            'type': 'item'
        })

    return entries


def process_skills_json(json_path: Path) -> dict:
    """Extract skills from JSON for catalog"""
    with open(json_path, 'r') as f:
        data = json.load(f)

    skills = data.get('skills', [])
    entries = {'SKILLS (Test)': []}

    for skill in skills:
        skill_id = skill.get('skillId')
        entries['SKILLS (Test)'].append({
            'id': skill_id,
            'data': skill,
            'type': 'skill'
        })

    return entries


def process_enemies_json(json_path: Path) -> dict:
    """Extract enemies from JSON for catalog"""
    with open(json_path, 'r') as f:
        data = json.load(f)

    enemies = data.get('enemies', [])
    entries = {'ENEMIES (Test)': []}

    for enemy in enemies:
        enemy_id = enemy.get('enemyId')
        entries['ENEMIES (Test)'].append({
            'id': enemy_id,
            'data': enemy,
            'type': 'enemy'
        })

    return entries


def main():
    parser = argparse.ArgumentParser(description='Update Vheer catalog with new content')
    parser.add_argument('--json', help='Path to specific JSON file to process')
    parser.add_argument('--update', help='Process all JSONs in an Update-N directory')
    parser.add_argument('--catalog', default='tools/ITEM_CATALOG_FOR_ICONS.md',
                       help='Path to catalog file (default: tools/ITEM_CATALOG_FOR_ICONS.md)')

    args = parser.parse_args()

    catalog_path = project_root / args.catalog

    if not catalog_path.exists():
        print(f"❌ Error: Catalog not found: {catalog_path}")
        return 1

    new_entries = {}

    if args.update:
        print(f"\n📚 Processing Update: {args.update}\n")

        update_dir = project_root / args.update
        if not update_dir.exists():
            print(f"❌ Error: Update directory not found: {update_dir}")
            return 1

        # Find all JSONs in update directory
        for json_file in update_dir.glob('**/*.JSON'):
            print(f"  Processing: {json_file.name}")

            if 'items' in json_file.name:
                entries = process_items_json(json_file)
            elif 'skills' in json_file.name.lower():
                entries = process_skills_json(json_file)
            elif 'hostiles' in json_file.name or 'enemies' in json_file.name:
                entries = process_enemies_json(json_file)
            else:
                continue

            # Merge entries
            for section, items in entries.items():
                if section not in new_entries:
                    new_entries[section] = []
                new_entries[section].extend(items)

    elif args.json:
        json_path = Path(args.json)
        if not json_path.exists():
            print(f"❌ Error: JSON file not found: {json_path}")
            return 1

        print(f"\n📚 Processing: {json_path.name}\n")

        if 'items' in str(json_path):
            new_entries = process_items_json(json_path)
        elif 'skills' in str(json_path).lower():
            new_entries = process_skills_json(json_path)
        elif 'hostiles' in str(json_path) or 'enemies' in str(json_path):
            new_entries = process_enemies_json(json_path)
        else:
            print(f"❌ Error: Cannot determine JSON type from path: {json_path}")
            return 1

    else:
        parser.print_help()
        return 1

    # Update catalog
    print(f"\n📝 Updating catalog: {catalog_path.name}\n")
    append_to_catalog(catalog_path, new_entries)

    print(f"\n✅ Catalog updated successfully")
    print(f"📝 Next: Run Vheer to generate icons from updated catalog")

    return 0


if __name__ == '__main__':
    sys.exit(main())

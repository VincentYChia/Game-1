#!/usr/bin/env python3
"""
Create Placeholder Icons for New Content (Simple Version)

Generates minimal valid PNG files as placeholders.
No dependencies required - uses raw PNG format.

Usage:
    python tools/create_placeholder_icons_simple.py --all-test-content
"""

import os
import sys
import json
import argparse
import struct
import zlib
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


def create_minimal_png(output_path: Path, width: int = 64, height: int = 64, color: tuple = (128, 128, 128)):
    """
    Create a minimal valid PNG file without PIL

    Args:
        output_path: Where to save the PNG
        width: Image width in pixels
        height: Image height in pixels
        color: RGB color tuple
    """
    # PNG signature
    png_signature = b'\x89PNG\r\n\x1a\n'

    # IHDR chunk (image header)
    ihdr_data = struct.pack('>IIBBBBB', width, height, 8, 2, 0, 0, 0)
    ihdr_chunk = create_png_chunk(b'IHDR', ihdr_data)

    # IDAT chunk (image data)
    raw_data = bytearray()
    for y in range(height):
        raw_data.append(0)  # Filter type 0 (None)
        for x in range(width):
            raw_data.extend(color)  # RGB

    compressed = zlib.compress(bytes(raw_data), 9)
    idat_chunk = create_png_chunk(b'IDAT', compressed)

    # IEND chunk (end marker)
    iend_chunk = create_png_chunk(b'IEND', b'')

    # Write PNG file
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'wb') as f:
        f.write(png_signature)
        f.write(ihdr_chunk)
        f.write(idat_chunk)
        f.write(iend_chunk)

    print(f"  Created: {output_path.relative_to(project_root)}")


def create_png_chunk(chunk_type: bytes, data: bytes) -> bytes:
    """Create a PNG chunk with length, type, data, and CRC"""
    length = struct.pack('>I', len(data))
    crc = struct.pack('>I', zlib.crc32(chunk_type + data) & 0xffffffff)
    return length + chunk_type + data + crc


# Color schemes for different entity types
COLOR_SCHEMES = {
    'weapon': (180, 50, 50),      # Red
    'armor': (50, 100, 180),      # Blue
    'accessory': (200, 150, 50),  # Gold
    'consumable': (80, 180, 80),  # Green
    'material': (150, 150, 150),  # Gray
    'device': (200, 100, 200),    # Purple
    'skill': (100, 200, 200),     # Cyan
    'enemy': (220, 80, 80),       # Bright red
    'resource': (100, 150, 80),   # Olive
}


def process_items_json(json_path: Path) -> list:
    """Process items JSON and create placeholders"""
    created = []

    with open(json_path, 'r') as f:
        data = json.load(f)

    items = data.get('items', data.get('test_weapons', data.get('weapons', [])))

    for item in items:
        item_id = item.get('itemId')
        item_type = item.get('type', 'material')

        # Map item types to categories
        if item_type in ['weapon', 'bow', 'staff', 'dagger']:
            category = 'weapon'
        elif item_type in ['armor', 'helmet', 'chestplate', 'boots']:
            category = 'armor'
        elif item_type in ['accessory', 'ring', 'amulet']:
            category = 'accessory'
        else:
            category = item_type

        color = COLOR_SCHEMES.get(category, (128, 128, 128))

        # Determine output path - goes directly to assets/items/
        output_path = project_root / 'assets' / 'items' / category / f'{item_id}.png'

        create_minimal_png(output_path, 64, 64, color)
        created.append(str(output_path.relative_to(project_root)))

    return created


def process_skills_json(json_path: Path) -> list:
    """Process skills JSON and create placeholders"""
    created = []

    with open(json_path, 'r') as f:
        data = json.load(f)

    skills = data.get('skills', [])
    color = COLOR_SCHEMES['skill']

    for skill in skills:
        skill_id = skill.get('skillId')

        # Determine output path - goes directly to assets/skills/
        output_path = project_root / 'assets' / 'skills' / f'{skill_id}.png'

        create_minimal_png(output_path, 64, 64, color)
        created.append(str(output_path.relative_to(project_root)))

    return created


def process_enemies_json(json_path: Path) -> list:
    """Process enemies JSON and create placeholders"""
    created = []

    with open(json_path, 'r') as f:
        data = json.load(f)

    enemies = data.get('enemies', [])
    color = COLOR_SCHEMES['enemy']

    for enemy in enemies:
        enemy_id = enemy.get('enemyId')

        # Determine output path - goes directly to assets/enemies/
        output_path = project_root / 'assets' / 'enemies' / f'{enemy_id}.png'

        create_minimal_png(output_path, 64, 64, color)
        created.append(str(output_path.relative_to(project_root)))

    return created


def main():
    parser = argparse.ArgumentParser(description='Create placeholder icons for new content (simple)')
    parser.add_argument('--json', help='Path to specific JSON file to process')
    parser.add_argument('--all-test-content', action='store_true',
                       help='Process all testing-integration JSON files')
    parser.add_argument('--update', help='Process all JSON files in an Update-N directory (e.g., Update-1)')

    args = parser.parse_args()

    created_files = []

    if args.update:
        print(f"\n🎨 Creating placeholder icons for {args.update}...\n")

        update_dir = project_root / args.update
        if not update_dir.exists():
            print(f"❌ Error: Update directory not found: {update_dir}")
            return 1

        # Process all JSON files in the update directory
        for json_file in update_dir.glob("*.JSON"):
            print(f"📄 Processing: {json_file.name}")

            # Determine type from filename
            if 'items' in json_file.name or 'weapons' in json_file.name or 'armor' in json_file.name:
                created_files.extend(process_items_json(json_file))
            elif 'skills' in json_file.name.lower():
                created_files.extend(process_skills_json(json_file))
            elif 'hostiles' in json_file.name or 'enemies' in json_file.name:
                created_files.extend(process_enemies_json(json_file))
            else:
                print(f"  ⏭️  Skipped (unknown type)")

    elif args.all_test_content:
        print("\n🎨 Creating placeholder icons for all test content...\n")

        # Process test items
        items_json = project_root / 'items.JSON' / 'items-testing-integration.JSON'
        if items_json.exists():
            print(f"📦 Processing items: {items_json.name}")
            created_files.extend(process_items_json(items_json))

        # Process test skills
        skills_json = project_root / 'Skills' / 'skills-testing-integration.JSON'
        if skills_json.exists():
            print(f"\n⚡ Processing skills: {skills_json.name}")
            created_files.extend(process_skills_json(skills_json))

        # Process test enemies
        enemies_json = project_root / 'Definitions.JSON' / 'hostiles-testing-integration.JSON'
        if enemies_json.exists():
            print(f"\n👾 Processing enemies: {enemies_json.name}")
            created_files.extend(process_enemies_json(enemies_json))

    elif args.json:
        json_path = Path(args.json)
        if not json_path.exists():
            print(f"❌ Error: JSON file not found: {json_path}")
            return 1

        print(f"\n🎨 Processing: {json_path.name}\n")

        # Determine type from path
        if 'items' in str(json_path):
            created_files = process_items_json(json_path)
        elif 'skills' in str(json_path).lower():
            created_files = process_skills_json(json_path)
        elif 'hostiles' in str(json_path) or 'enemies' in str(json_path):
            created_files = process_enemies_json(json_path)
        else:
            print(f"❌ Error: Cannot determine JSON type from path: {json_path}")
            return 1

    else:
        parser.print_help()
        return 1

    print(f"\n✅ Created {len(created_files)} placeholder icons")
    print(f"\n📝 Note: These are simple colored squares. Update catalog and run Vheer to generate final art.")

    return 0


if __name__ == '__main__':
    sys.exit(main())

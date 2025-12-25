#!/usr/bin/env python3
"""
Create Placeholder Icons for New Content

Generates simple colored placeholder PNGs for items, skills, and enemies
that don't have icons yet. These can be replaced by Vheer-generated art later.

Usage:
    python tools/create_placeholder_icons.py --json items.JSON/items-testing-integration.JSON
    python tools/create_placeholder_icons.py --all-test-content
"""

import os
import sys
import json
import argparse
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


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


def create_placeholder_png(name: str, entity_type: str, output_path: Path, size: int = 64):
    """
    Create a simple placeholder PNG with colored background and text

    Args:
        name: Entity name (e.g., "lightning_chain_whip")
        entity_type: Type of entity (weapon, skill, enemy, etc.)
        output_path: Where to save the PNG
        size: Icon size in pixels (default 64x64)
    """
    # Create image with colored background
    color = COLOR_SCHEMES.get(entity_type, (128, 128, 128))
    img = Image.new('RGB', (size, size), color=color)
    draw = ImageDraw.Draw(img)

    # Draw border
    border_color = tuple(max(0, c - 50) for c in color)
    draw.rectangle([0, 0, size-1, size-1], outline=border_color, width=2)

    # Draw diagonal stripe pattern
    stripe_color = tuple(min(255, c + 30) for c in color)
    for i in range(0, size * 2, 8):
        draw.line([(i, 0), (0, i)], fill=stripe_color, width=2)

    # Try to add text (first 3 letters of name)
    try:
        # Try to use default font, fall back to basic if not available
        try:
            font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 16)
        except:
            font = ImageFont.load_default()

        # Get initials (first letter of each word, max 3)
        initials = ''.join(word[0].upper() for word in name.split('_'))[:3]

        # Center text
        bbox = draw.textbbox((0, 0), initials, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
        x = (size - text_width) // 2
        y = (size - text_height) // 2

        # Draw text with shadow
        draw.text((x+1, y+1), initials, fill=(0, 0, 0), font=font)
        draw.text((x, y), initials, fill=(255, 255, 255), font=font)
    except Exception as e:
        # If text fails, just skip it
        pass

    # Save image
    output_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(output_path)
    print(f"  Created: {output_path.relative_to(project_root)}")


def process_items_json(json_path: Path) -> list:
    """Process items JSON and create placeholders"""
    created = []

    with open(json_path, 'r') as f:
        data = json.load(f)

    items = data.get('items', [])

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

        # Determine output path
        output_path = project_root / 'assets' / 'generated_icons' / 'items' / category / f'{item_id}.png'

        create_placeholder_png(item_id, category, output_path)
        created.append(str(output_path.relative_to(project_root)))

    return created


def process_skills_json(json_path: Path) -> list:
    """Process skills JSON and create placeholders"""
    created = []

    with open(json_path, 'r') as f:
        data = json.load(f)

    skills = data.get('skills', [])

    for skill in skills:
        skill_id = skill.get('skillId')

        # Determine output path
        output_path = project_root / 'assets' / 'generated_icons' / 'skills' / f'{skill_id}.png'

        create_placeholder_png(skill_id, 'skill', output_path)
        created.append(str(output_path.relative_to(project_root)))

    return created


def process_enemies_json(json_path: Path) -> list:
    """Process enemies JSON and create placeholders"""
    created = []

    with open(json_path, 'r') as f:
        data = json.load(f)

    enemies = data.get('enemies', [])

    for enemy in enemies:
        enemy_id = enemy.get('enemyId')

        # Determine output path
        output_path = project_root / 'assets' / 'generated_icons' / 'enemies' / f'{enemy_id}.png'

        create_placeholder_png(enemy_id, 'enemy', output_path)
        created.append(str(output_path.relative_to(project_root)))

    return created


def main():
    parser = argparse.ArgumentParser(description='Create placeholder icons for new content')
    parser.add_argument('--json', help='Path to specific JSON file to process')
    parser.add_argument('--all-test-content', action='store_true',
                       help='Process all testing-integration JSON files')
    parser.add_argument('--size', type=int, default=64, help='Icon size in pixels (default 64)')

    args = parser.parse_args()

    created_files = []

    if args.all_test_content:
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
    print(f"\n📝 Note: These are temporary placeholders. Update catalog and run Vheer to generate final art.")

    return 0


if __name__ == '__main__':
    sys.exit(main())

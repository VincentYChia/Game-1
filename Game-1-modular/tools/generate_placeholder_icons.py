#!/usr/bin/env python3
"""
Placeholder Icon Generator

Generates simple placeholder PNG images for all game entities (items, enemies, resources).
Each placeholder is a colored rectangle with the item ID as text, making it easy to see
what needs to be replaced with actual artwork.

Usage:
    python tools/generate_placeholder_icons.py
"""

import os
import sys
import json
from pathlib import Path
from typing import List, Tuple, Dict

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    import pygame
    pygame.init()
except ImportError:
    print("ERROR: pygame not installed. Install with: pip install pygame")
    sys.exit(1)


# Placeholder image settings
PLACEHOLDER_SIZE = (64, 64)
FONT_SIZE = 10
FONT_SIZE_SMALL = 8

# Category colors (for visual distinction)
CATEGORY_COLORS = {
    'materials': (139, 69, 19),      # Brown
    'weapons': (192, 192, 192),      # Silver
    'armor': (70, 130, 180),         # Steel blue
    'tools': (160, 82, 45),          # Sienna
    'accessories': (218, 165, 32),   # Goldenrod
    'stations': (105, 105, 105),     # Dim gray
    'devices': (255, 140, 0),        # Dark orange
    'consumables': (147, 112, 219),  # Medium purple
    'enemies': (178, 34, 34),        # Firebrick
    'resources': (34, 139, 34),      # Forest green
    'titles': (138, 43, 226),        # Blue violet
    'skills': (255, 215, 0),         # Gold
}


def create_placeholder_image(item_id: str, category: str, tier: int = 1) -> pygame.Surface:
    """Create a placeholder image with item ID text"""
    surface = pygame.Surface(PLACEHOLDER_SIZE, pygame.SRCALPHA)

    # Fill with category color
    color = CATEGORY_COLORS.get(category, (128, 128, 128))
    surface.fill(color)

    # Add darker border
    border_color = tuple(max(0, c - 40) for c in color)
    pygame.draw.rect(surface, border_color, surface.get_rect(), 2)

    # Add text
    font = pygame.font.Font(None, FONT_SIZE)
    font_small = pygame.font.Font(None, FONT_SIZE_SMALL)

    # Item ID (wrapped if too long)
    words = item_id.replace('_', ' ').split()
    y_offset = 5

    if len(words) <= 2:
        # Single or two words - center them
        for word in words:
            text_surf = font.render(word, True, (255, 255, 255))
            text_rect = text_surf.get_rect(centerx=PLACEHOLDER_SIZE[0] // 2, y=y_offset)
            # Black outline for readability
            for dx, dy in [(-1,0), (1,0), (0,-1), (0,1)]:
                outline = font.render(word, True, (0, 0, 0))
                surface.blit(outline, (text_rect.x + dx, text_rect.y + dy))
            surface.blit(text_surf, text_rect)
            y_offset += 12
    else:
        # Multiple words - wrap text
        for word in words[:4]:  # Max 4 words
            text_surf = font_small.render(word[:8], True, (255, 255, 255))
            text_rect = text_surf.get_rect(centerx=PLACEHOLDER_SIZE[0] // 2, y=y_offset)
            for dx, dy in [(-1,0), (1,0), (0,-1), (0,1)]:
                outline = font_small.render(word[:8], True, (0, 0, 0))
                surface.blit(outline, (text_rect.x + dx, text_rect.y + dy))
            surface.blit(text_surf, text_rect)
            y_offset += 10

    # Tier indicator at bottom
    tier_text = f"T{tier}"
    tier_surf = font.render(tier_text, True, (255, 255, 255))
    tier_rect = tier_surf.get_rect(centerx=PLACEHOLDER_SIZE[0] // 2, bottom=PLACEHOLDER_SIZE[1] - 3)
    for dx, dy in [(-1,0), (1,0), (0,-1), (0,1)]:
        outline = font.render(tier_text, True, (0, 0, 0))
        surface.blit(outline, (tier_rect.x + dx, tier_rect.y + dy))
    surface.blit(tier_surf, tier_rect)

    return surface


def generate_item_placeholders(base_path: Path):
    """Generate placeholder images for all items from JSON files"""
    json_dirs = [
        ('items.JSON', 'materials'),
        ('items.JSON', 'equipment'),
        ('recipes.JSON', None),  # Skip recipes
    ]

    generated = 0

    # Process materials
    materials_file = base_path / 'items.JSON' / 'items-materials-1.JSON'
    if materials_file.exists():
        with open(materials_file, 'r') as f:
            data = json.load(f)
            for mat in data.get('materials', []):
                item_id = mat.get('materialId', '')
                tier = mat.get('tier', 1)
                category = mat.get('category', 'unknown')

                # Determine subdirectory
                if category in ['consumable']:
                    subdir = 'consumables'
                elif category in ['device']:
                    subdir = 'devices'
                elif category in ['station']:
                    subdir = 'stations'
                else:
                    subdir = 'materials'

                if item_id:
                    icon_path = base_path / 'assets' / 'items' / subdir / f"{item_id}.png"
                    if not icon_path.exists():  # Only create if doesn't exist
                        surface = create_placeholder_image(item_id, subdir, tier)
                        pygame.image.save(surface, str(icon_path))
                        generated += 1
                        if generated <= 10:
                            print(f"  Created: {subdir}/{item_id}.png")

    # Process equipment files
    equipment_files = [
        'items-engineering-1.JSON',
        'items-smithing-2.JSON',
        'items-tools-1.JSON',
        'items-alchemy-1.JSON',
        'items-refining-1.JSON',
    ]

    for filename in equipment_files:
        eq_file = base_path / 'items.JSON' / filename
        if not eq_file.exists():
            continue

        with open(eq_file, 'r') as f:
            data = json.load(f)
            for section_name, section_data in data.items():
                if section_name == 'metadata' or not isinstance(section_data, list):
                    continue

                for item in section_data:
                    item_id = item.get('itemId', '')
                    tier = item.get('tier', 1)
                    category_type = item.get('category', '')
                    item_type = item.get('type', '')
                    slot = item.get('slot', '')
                    flags = item.get('flags', {})
                    is_stackable = flags.get('stackable', False)

                    if not item_id:
                        continue

                    # Determine subdirectory - check stackable items first
                    if is_stackable or category_type in ['consumable', 'device', 'station']:
                        # Stackable items by category
                        if category_type == 'consumable' or item_type == 'potion':
                            subdir = 'consumables'
                        elif category_type == 'device' or item_type in ['turret', 'bomb', 'trap', 'utility']:
                            subdir = 'devices'
                        elif category_type == 'station' or item_type == 'station':
                            subdir = 'stations'
                        else:
                            subdir = 'materials'
                    elif category_type == 'equipment':
                        # Equipment items
                        if item_type in ['weapon', 'sword', 'axe', 'mace', 'dagger', 'spear', 'bow', 'staff'] or \
                           (slot in ['mainHand', 'offHand'] and item.get('stats', {}).get('damage')):
                            subdir = 'weapons'
                        elif item_type == 'armor' or slot in ['helmet', 'chestplate', 'leggings', 'boots', 'gauntlets']:
                            subdir = 'armor'
                        elif item_type == 'tool' or slot in ['tool', 'axe', 'pickaxe']:
                            subdir = 'tools'
                        elif item_type == 'accessory':
                            subdir = 'accessories'
                        else:
                            subdir = 'weapons'  # Default for equipment
                    else:
                        subdir = 'materials'  # Fallback

                    icon_path = base_path / 'assets' / 'items' / subdir / f"{item_id}.png"
                    if not icon_path.exists():
                        surface = create_placeholder_image(item_id, subdir, tier)
                        pygame.image.save(surface, str(icon_path))
                        generated += 1
                        if generated <= 10:
                            print(f"  Created: {subdir}/{item_id}.png")

    return generated


def generate_enemy_placeholders(base_path: Path):
    """Generate placeholder images for enemies"""
    enemies_file = base_path / 'Definitions.JSON' / 'hostiles-1.JSON'
    if not enemies_file.exists():
        return 0

    generated = 0
    enemy_dir = base_path / 'assets' / 'enemies'
    enemy_dir.mkdir(parents=True, exist_ok=True)

    with open(enemies_file, 'r') as f:
        data = json.load(f)
        for enemy in data.get('enemies', []):
            enemy_id = enemy.get('enemyId', '')
            tier = enemy.get('tier', 1)

            if enemy_id:
                icon_path = enemy_dir / f"{enemy_id}.png"
                if not icon_path.exists():
                    surface = create_placeholder_image(enemy_id, 'enemies', tier)
                    pygame.image.save(surface, str(icon_path))
                    generated += 1
                    print(f"  Created: enemies/{enemy_id}.png")

    return generated


def generate_resource_placeholders(base_path: Path):
    """Generate placeholder images for harvestable resources"""
    # Resources are defined in code (ResourceType enum), so we'll hardcode them
    resources = [
        ('oak_tree', 1), ('birch_tree', 2), ('maple_tree', 2), ('ironwood_tree', 3),
        ('copper_ore_node', 1), ('iron_ore_node', 1), ('steel_ore_node', 2), ('mithril_ore_node', 2),
        ('limestone_node', 1), ('granite_node', 1), ('obsidian_node', 3), ('star_crystal_node', 4),
    ]

    generated = 0
    resource_dir = base_path / 'assets' / 'resources'
    resource_dir.mkdir(parents=True, exist_ok=True)

    for resource_id, tier in resources:
        icon_path = resource_dir / f"{resource_id}.png"
        if not icon_path.exists():
            surface = create_placeholder_image(resource_id, 'resources', tier)
            pygame.image.save(surface, str(icon_path))
            generated += 1
            print(f"  Created: resources/{resource_id}.png")

    return generated


def generate_title_placeholders(base_path: Path):
    """Generate placeholder images for titles"""
    titles_file = base_path / 'progression' / 'titles-1.JSON'
    if not titles_file.exists():
        return 0

    generated = 0
    titles_dir = base_path / 'assets' / 'titles'
    titles_dir.mkdir(parents=True, exist_ok=True)

    with open(titles_file, 'r') as f:
        data = json.load(f)
        for title in data.get('titles', []):
            title_id = title.get('titleId', '')
            # Map difficulty tier to numeric tier
            tier_map = {'novice': 1, 'apprentice': 2, 'journeyman': 3, 'expert': 4, 'master': 5, 'special': 5}
            tier_str = title.get('difficultyTier', 'novice')
            tier = tier_map.get(tier_str, 1)

            if title_id:
                icon_path = titles_dir / f"{title_id}.png"
                if not icon_path.exists():
                    surface = create_placeholder_image(title_id, 'titles', tier)
                    pygame.image.save(surface, str(icon_path))
                    generated += 1
                    print(f"  Created: titles/{title_id}.png")

    return generated


def generate_skill_placeholders(base_path: Path):
    """Generate placeholder images for skills"""
    skills_file = base_path / 'Skills' / 'skills-skills-1.JSON'
    if not skills_file.exists():
        return 0

    generated = 0
    skills_dir = base_path / 'assets' / 'skills'
    skills_dir.mkdir(parents=True, exist_ok=True)

    with open(skills_file, 'r') as f:
        data = json.load(f)
        for skill in data.get('skills', []):
            skill_id = skill.get('skillId', '')
            tier = skill.get('tier', 1)

            if skill_id:
                icon_path = skills_dir / f"{skill_id}.png"
                if not icon_path.exists():
                    surface = create_placeholder_image(skill_id, 'skills', tier)
                    pygame.image.save(surface, str(icon_path))
                    generated += 1
                    print(f"  Created: skills/{skill_id}.png")

    return generated


def main():
    """Main entry point"""
    print("=" * 60)
    print("PLACEHOLDER ICON GENERATOR")
    print("=" * 60)

    # Determine base path
    script_dir = Path(__file__).parent
    base_path = script_dir.parent  # Game-1-modular directory

    print(f"\nBase path: {base_path}")
    print(f"Generating {PLACEHOLDER_SIZE[0]}x{PLACEHOLDER_SIZE[1]} PNG placeholders...")

    # Create directories
    assets_items = base_path / 'assets' / 'items'
    for subdir in ['materials', 'weapons', 'armor', 'tools', 'accessories', 'stations', 'devices', 'consumables']:
        (assets_items / subdir).mkdir(parents=True, exist_ok=True)

    # Generate placeholders
    print("\n[1/5] Generating item placeholders...")
    items_count = generate_item_placeholders(base_path)
    print(f"      Generated {items_count} item placeholders")

    print("\n[2/5] Generating enemy placeholders...")
    enemies_count = generate_enemy_placeholders(base_path)
    print(f"      Generated {enemies_count} enemy placeholders")

    print("\n[3/5] Generating resource placeholders...")
    resources_count = generate_resource_placeholders(base_path)
    print(f"      Generated {resources_count} resource placeholders")

    print("\n[4/5] Generating title placeholders...")
    titles_count = generate_title_placeholders(base_path)
    print(f"      Generated {titles_count} title placeholders")

    print("\n[5/5] Generating skill placeholders...")
    skills_count = generate_skill_placeholders(base_path)
    print(f"      Generated {skills_count} skill placeholders")

    total = items_count + enemies_count + resources_count + titles_count + skills_count
    print("\n" + "=" * 60)
    print(f"✓ COMPLETE: Generated {total} total placeholder icons")
    print("=" * 60)
    print("\nPlaceholders are labeled with their IDs for easy identification.")
    print("Replace them with actual artwork gradually as it's created.")
    print("\nDirectory structure:")
    print(f"  - {assets_items}/materials/      ({len(list((assets_items / 'materials').glob('*.png')))} files)")
    print(f"  - {assets_items}/weapons/        ({len(list((assets_items / 'weapons').glob('*.png')))} files)")
    print(f"  - {assets_items}/armor/          ({len(list((assets_items / 'armor').glob('*.png')))} files)")
    print(f"  - {assets_items}/tools/          ({len(list((assets_items / 'tools').glob('*.png')))} files)")
    print(f"  - {base_path}/assets/enemies/    ({len(list((base_path / 'assets' / 'enemies').glob('*.png')))} files)")
    print(f"  - {base_path}/assets/resources/  ({len(list((base_path / 'assets' / 'resources').glob('*.png')))} files)")
    print(f"  - {base_path}/assets/titles/     ({len(list((base_path / 'assets' / 'titles').glob('*.png')))} files)")
    print(f"  - {base_path}/assets/skills/     ({len(list((base_path / 'assets' / 'skills').glob('*.png')))} files)")


if __name__ == '__main__':
    main()

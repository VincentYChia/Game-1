#!/usr/bin/env python3
"""
Unified Icon & Catalog Generator

Generates BOTH placeholder icons AND the catalog markdown from the same JSON sources.
Guarantees 1:1 match between placeholders and catalog entries.

Usage:
    python tools/unified_icon_generator.py
"""

import os
import sys
import json
from pathlib import Path
from typing import List, Dict, Tuple
from datetime import datetime

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    import pygame
    pygame.init()
except ImportError:
    print("ERROR: pygame not installed. Install with: pip install pygame")
    sys.exit(1)


# ============================================================================
# CONFIGURATION
# ============================================================================

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
    'npcs': (255, 20, 147),          # Deep pink
    'quests': (255, 69, 0),          # Orange red
    'classes': (75, 0, 130),         # Indigo
}

# Hardcoded resources (from ResourceType enum in code)
RESOURCES = [
    {'id': 'oak_tree', 'name': 'Oak Tree', 'tier': 1, 'category': 'tree',
     'narrative': 'Oak tree (T1, requires axe). Reliable, sturdy timber from ancient oaks.'},
    {'id': 'birch_tree', 'name': 'Birch Tree', 'tier': 2, 'category': 'tree',
     'narrative': 'Birch tree (T2, requires axe). Elegant trees with creamy-white wood.'},
    {'id': 'maple_tree', 'name': 'Maple Tree', 'tier': 2, 'category': 'tree',
     'narrative': 'Maple tree (T2, requires axe). Dense hardwood with beautiful figuring.'},
    {'id': 'ironwood_tree', 'name': 'Ironwood Tree', 'tier': 3, 'category': 'tree',
     'narrative': 'Ironwood tree (T3, requires axe). Rare wood with metallic properties.'},
    {'id': 'copper_ore_node', 'name': 'Copper Ore Node', 'tier': 1, 'category': 'ore',
     'narrative': 'Copper ore deposit (T1, requires pickaxe). Soft, reddish metal from shallow veins.'},
    {'id': 'iron_ore_node', 'name': 'Iron Ore Node', 'tier': 1, 'category': 'ore',
     'narrative': 'Iron ore deposit (T1, requires pickaxe). Common deposits of sturdy grey metal.'},
    {'id': 'steel_ore_node', 'name': 'Steel Ore Node', 'tier': 2, 'category': 'ore',
     'narrative': 'Steel ore deposit (T2, requires pickaxe). Carbon-rich deposits for quality metal.'},
    {'id': 'mithril_ore_node', 'name': 'Mithril Ore Node', 'tier': 2, 'category': 'ore',
     'narrative': 'Mithril ore deposit (T2, requires pickaxe). Legendary silver-white metal veins.'},
    {'id': 'limestone_node', 'name': 'Limestone Node', 'tier': 1, 'category': 'stone',
     'narrative': 'Limestone deposit (T1, requires pickaxe). Common sedimentary rock for construction.'},
    {'id': 'granite_node', 'name': 'Granite Node', 'tier': 1, 'category': 'stone',
     'narrative': 'Granite deposit (T1, requires pickaxe). Speckled igneous rock with crystalline structure.'},
    {'id': 'obsidian_node', 'name': 'Obsidian Node', 'tier': 3, 'category': 'stone',
     'narrative': 'Obsidian deposit (T3, requires pickaxe). Volcanic glass born in eruptions.'},
    {'id': 'star_crystal_node', 'name': 'Star Crystal Node', 'tier': 4, 'category': 'stone',
     'narrative': 'Star crystal deposit (T4, requires pickaxe, rare). Crystallized starlight from the heavens.'},
]


# ============================================================================
# PLACEHOLDER IMAGE GENERATION (from generate_placeholder_icons.py)
# ============================================================================

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


def categorize_item(item: Dict) -> str:
    """Determine asset subfolder for an item"""
    category = item.get('category', '').lower()
    item_type = item.get('type', '').lower()
    is_stackable = item.get('flags', {}).get('stackable', False)

    # Stackable items first
    if is_stackable or category in ['consumable', 'device', 'station']:
        if category == 'consumable' or item_type == 'potion':
            return 'consumables'
        elif category == 'device' or item_type in ['turret', 'bomb', 'trap', 'utility']:
            return 'devices'
        elif category == 'station' or item_type == 'station':
            return 'stations'
        else:
            return 'materials'
    elif category == 'equipment':
        # Equipment items
        slot = item.get('slot', '')
        if item_type in ['weapon', 'sword', 'axe', 'mace', 'dagger', 'spear', 'bow', 'staff'] or \
           (slot in ['mainHand', 'offHand'] and item.get('stats', {}).get('damage')):
            return 'weapons'
        elif item_type == 'armor' or slot in ['helmet', 'chestplate', 'leggings', 'boots', 'gauntlets']:
            return 'armor'
        elif item_type == 'tool' or slot in ['tool', 'axe', 'pickaxe']:
            return 'tools'
        elif item_type == 'accessory':
            return 'accessories'
        else:
            return 'weapons'  # Default for equipment
    elif category in ['metal', 'wood', 'stone', 'elemental', 'monster_drop']:
        return 'materials'
    else:
        return 'materials'  # Fallback


# ============================================================================
# DATA EXTRACTION
# ============================================================================

class EntityEntry:
    """Represents a single entity with all needed data"""
    def __init__(self, entity_id: str, name: str, category: str, entity_type: str,
                 subtype: str, narrative: str, tier: int, subfolder: str):
        self.id = entity_id
        self.name = name
        self.category = category
        self.type = entity_type
        self.subtype = subtype
        self.narrative = narrative
        self.tier = tier
        self.subfolder = subfolder


def extract_materials(base_path: Path) -> List[EntityEntry]:
    """Extract all materials from items-materials-1.JSON"""
    entities = []
    materials_file = base_path / 'items.JSON' / 'items-materials-1.JSON'

    if not materials_file.exists():
        return entities

    with open(materials_file, 'r') as f:
        data = json.load(f)
        for mat in data.get('materials', []):
            mat_id = mat.get('materialId', '')
            if not mat_id:
                continue

            category = mat.get('category', 'material')
            narrative = mat.get('metadata', {}).get('narrative', 'No description available.')
            tier = mat.get('tier', 1)

            # Determine subfolder
            if category in ['consumable']:
                subfolder = 'consumables'
            elif category in ['device']:
                subfolder = 'devices'
            elif category in ['station']:
                subfolder = 'stations'
            else:
                subfolder = 'materials'

            entities.append(EntityEntry(
                entity_id=mat_id,
                name=mat.get('name', mat_id),
                category=category,
                entity_type='material',
                subtype=category,
                narrative=narrative,
                tier=tier,
                subfolder=subfolder
            ))

    return entities


def extract_equipment(base_path: Path) -> List[EntityEntry]:
    """Extract all equipment from equipment JSON files"""
    entities = []
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
                    if not item_id:
                        continue

                    category = item.get('category', 'equipment')
                    item_type = item.get('type', 'unknown')
                    subtype = item.get('subtype', item_type)
                    narrative = item.get('metadata', {}).get('narrative', 'No description available.')
                    tier = item.get('tier', 1)

                    # Determine subfolder
                    subfolder = categorize_item(item)

                    entities.append(EntityEntry(
                        entity_id=item_id,
                        name=item.get('name', item_id),
                        category=category,
                        entity_type=item_type,
                        subtype=subtype,
                        narrative=narrative,
                        tier=tier,
                        subfolder=subfolder
                    ))

    return entities


def extract_enemies(base_path: Path) -> List[EntityEntry]:
    """Extract all enemies from hostiles-1.JSON"""
    entities = []
    enemies_file = base_path / 'Definitions.JSON' / 'hostiles-1.JSON'

    if not enemies_file.exists():
        return entities

    with open(enemies_file, 'r') as f:
        data = json.load(f)
        for enemy in data.get('enemies', []):
            enemy_id = enemy.get('enemyId', '')
            if not enemy_id:
                continue

            category = enemy.get('category', 'beast')
            narrative = enemy.get('metadata', {}).get('narrative', 'No description available.')
            tier = enemy.get('tier', 1)

            entities.append(EntityEntry(
                entity_id=enemy_id,
                name=enemy.get('name', enemy_id),
                category='enemy',
                entity_type=category,
                subtype=category,
                narrative=narrative,
                tier=tier,
                subfolder='enemies'
            ))

    return entities


def extract_titles(base_path: Path) -> List[EntityEntry]:
    """Extract all titles from titles-1.JSON"""
    entities = []
    titles_file = base_path / 'progression' / 'titles-1.JSON'

    if not titles_file.exists():
        return entities

    with open(titles_file, 'r') as f:
        data = json.load(f)
        for title in data.get('titles', []):
            title_id = title.get('titleId', '')
            if not title_id:
                continue

            title_type = title.get('titleType', 'general')
            narrative = title.get('narrative', title.get('description', 'No description available.'))

            # Map difficulty tier to numeric tier
            tier_map = {'novice': 1, 'apprentice': 2, 'journeyman': 3, 'expert': 4, 'master': 5, 'special': 5}
            tier_str = title.get('difficultyTier', 'novice')
            tier = tier_map.get(tier_str, 1)

            entities.append(EntityEntry(
                entity_id=title_id,
                name=title.get('name', title_id),
                category='title',
                entity_type=title_type,
                subtype=tier_str,
                narrative=narrative,
                tier=tier,
                subfolder='titles'
            ))

    return entities


def extract_skills(base_path: Path) -> List[EntityEntry]:
    """Extract all skills from skills-skills-1.JSON"""
    entities = []
    skills_file = base_path / 'Skills' / 'skills-skills-1.JSON'

    if not skills_file.exists():
        return entities

    with open(skills_file, 'r') as f:
        data = json.load(f)
        for skill in data.get('skills', []):
            skill_id = skill.get('skillId', '')
            if not skill_id:
                continue

            effect_type = skill.get('effect', {}).get('type', 'unknown')
            effect_category = skill.get('effect', {}).get('category', 'general')
            narrative = skill.get('narrative', skill.get('description', 'No description available.'))
            tier = skill.get('tier', 1)

            entities.append(EntityEntry(
                entity_id=skill_id,
                name=skill.get('name', skill_id),
                category='skill',
                entity_type=effect_type,
                subtype=effect_category,
                narrative=narrative,
                tier=tier,
                subfolder='skills'
            ))

    return entities


def extract_resources(base_path: Path) -> List[EntityEntry]:
    """Extract resources from resource-node-1.JSON (actually used by game)"""
    entities = []
    resources_file = base_path / 'Definitions.JSON' / 'resource-node-1.JSON'

    if not resources_file.exists():
        # Fallback to hardcoded if file doesn't exist
        for res in RESOURCES:
            entities.append(EntityEntry(
                entity_id=res['id'],
                name=res['name'],
                category='resource',
                entity_type=res['category'],
                subtype=res['category'],
                narrative=res['narrative'],
                tier=res['tier'],
                subfolder='resources'
            ))
        return entities

    with open(resources_file, 'r') as f:
        data = json.load(f)
        for resource in data.get('nodes', []):
            resource_id = resource.get('resourceId', '')
            if not resource_id:
                continue

            category = resource.get('category', 'resource')
            narrative = resource.get('metadata', {}).get('narrative', 'No description available.')
            tier = resource.get('tier', 1)

            entities.append(EntityEntry(
                entity_id=resource_id,
                name=resource.get('name', resource_id),
                category='resource',
                entity_type=category,
                subtype=category,
                narrative=narrative,
                tier=tier,
                subfolder='resources'
            ))

    return entities


def extract_npcs(base_path: Path) -> List[EntityEntry]:
    """Extract NPCs from npcs-1.JSON or npcs-enhanced.JSON (actually loaded by game)"""
    entities = []

    # Try enhanced first, then fallback to v1.0 (same as game logic)
    npc_files = [
        base_path / 'progression' / 'npcs-enhanced.JSON',
        base_path / 'progression' / 'npcs-1.JSON'
    ]

    for npc_file in npc_files:
        if npc_file.exists():
            with open(npc_file, 'r') as f:
                data = json.load(f)
                for npc in data.get('npcs', []):
                    npc_id = npc.get('npc_id', '')
                    if not npc_id:
                        continue

                    # Extract dialogue for narrative
                    dialogue_lines = npc.get('dialogue_lines', [])
                    if not dialogue_lines and 'dialogue' in npc:
                        dialogue_obj = npc['dialogue']
                        if 'dialogue_lines' in dialogue_obj:
                            dialogue_lines = dialogue_obj['dialogue_lines']
                        else:
                            greeting = dialogue_obj.get('greeting', {})
                            dialogue_lines = [greeting.get('default', 'Hello!')]

                    narrative = ' '.join(dialogue_lines[:2]) if dialogue_lines else 'An NPC in the world.'

                    entities.append(EntityEntry(
                        entity_id=npc_id,
                        name=npc.get('name', npc_id),
                        category='npc',
                        entity_type='npc',
                        subtype='npc',
                        narrative=narrative,
                        tier=1,
                        subfolder='npcs'
                    ))
            break  # Only load from first file that exists

    return entities


def extract_quests(base_path: Path) -> List[EntityEntry]:
    """Extract quests from quests-1.JSON or quests-enhanced.JSON (actually loaded by game)"""
    entities = []

    # Try enhanced first, then fallback to v1.0 (same as game logic)
    quest_files = [
        base_path / 'progression' / 'quests-enhanced.JSON',
        base_path / 'progression' / 'quests-1.JSON'
    ]

    for quest_file in quest_files:
        if quest_file.exists():
            with open(quest_file, 'r') as f:
                data = json.load(f)
                for quest in data.get('quests', []):
                    quest_id = quest.get('quest_id', quest.get('questId', ''))
                    if not quest_id:
                        continue

                    title = quest.get('title', quest.get('name', 'Untitled Quest'))
                    description = quest.get('description', '')
                    if isinstance(description, dict):
                        description = description.get('long', description.get('short', ''))

                    narrative = description if description else 'A quest in the game.'

                    # Determine tier based on rewards
                    rewards = quest.get('rewards', {})
                    experience = rewards.get('experience', 0)
                    tier = 1 if experience < 200 else (2 if experience < 400 else (3 if experience < 600 else 4))

                    entities.append(EntityEntry(
                        entity_id=quest_id,
                        name=title,
                        category='quest',
                        entity_type='quest',
                        subtype=quest.get('objectives', {}).get('type', 'gather'),
                        narrative=narrative,
                        tier=tier,
                        subfolder='quests'
                    ))
            break  # Only load from first file that exists

    return entities


def extract_classes(base_path: Path) -> List[EntityEntry]:
    """Extract classes from classes-1.JSON (actually loaded by game)"""
    entities = []
    classes_file = base_path / 'progression' / 'classes-1.JSON'

    if not classes_file.exists():
        return entities

    with open(classes_file, 'r') as f:
        data = json.load(f)
        for char_class in data.get('classes', []):
            class_id = char_class.get('classId', '')
            if not class_id:
                continue

            description = char_class.get('description', '')
            narrative = char_class.get('narrative', description)
            playstyle = char_class.get('playstyle', '')
            if playstyle:
                narrative = f"{narrative} {playstyle}"

            entities.append(EntityEntry(
                entity_id=class_id,
                name=char_class.get('name', class_id),
                category='class',
                entity_type='character_class',
                subtype=char_class.get('thematicIdentity', 'general'),
                narrative=narrative,
                tier=1,
                subfolder='classes'
            ))

    return entities


# ============================================================================
# PLACEHOLDER GENERATION
# ============================================================================

def generate_placeholders(entities: List[EntityEntry], base_path: Path) -> int:
    """Generate placeholder PNG images for all entities (only if they don't exist)"""
    generated = 0

    for entity in entities:
        # Determine save path
        if entity.subfolder in ['enemies', 'resources', 'titles', 'skills', 'npcs', 'quests', 'classes']:
            save_dir = base_path / 'assets' / entity.subfolder
        else:
            save_dir = base_path / 'assets' / 'items' / entity.subfolder

        save_dir.mkdir(parents=True, exist_ok=True)
        save_path = save_dir / f"{entity.id}.png"

        # Skip if already exists (DON'T OVERWRITE)
        if save_path.exists():
            continue

        # Create placeholder
        surface = create_placeholder_image(entity.id, entity.subfolder, entity.tier)
        pygame.image.save(surface, str(save_path))
        generated += 1

        if generated <= 10:
            print(f"  Created: {entity.subfolder}/{entity.id}.png")

    return generated


# ============================================================================
# CATALOG GENERATION
# ============================================================================

def generate_catalog(entities: List[EntityEntry], output_path: Path):
    """Generate the catalog markdown file"""

    # Group entities by category
    grouped = {}
    for entity in entities:
        key = entity.subfolder
        if key not in grouped:
            grouped[key] = []
        grouped[key].append(entity)

    # Build markdown
    lines = []
    lines.append("# Item Catalog for Icon Creation")
    lines.append("")
    lines.append("**Purpose**: Reference guide for creating icons for all game items. Each entry includes the item's narrative description to guide visual design.")
    lines.append("")
    lines.append(f"**Generated**: {datetime.now().strftime('%B %d, %Y')}")
    lines.append(f"**Total Entities**: {len(entities)}")
    lines.append("")
    lines.append("**Note**: This file is AUTO-GENERATED by `tools/unified_icon_generator.py`. Do not edit manually.")
    lines.append("")
    lines.append("---")
    lines.append("")

    # Count by category
    lines.append("## Summary")
    lines.append("")
    total_items = sum(len(ents) for key, ents in grouped.items() if key in ['weapons', 'armor', 'tools', 'accessories', 'materials', 'stations', 'devices', 'consumables'])
    lines.append(f"- **Items**: {total_items}")
    lines.append(f"- **Enemies**: {len(grouped.get('enemies', []))}")
    lines.append(f"- **Resources**: {len(grouped.get('resources', []))}")
    lines.append(f"- **Titles**: {len(grouped.get('titles', []))}")
    lines.append(f"- **Skills**: {len(grouped.get('skills', []))}")
    lines.append(f"- **NPCs**: {len(grouped.get('npcs', []))}")
    lines.append(f"- **Quests**: {len(grouped.get('quests', []))}")
    lines.append(f"- **Classes**: {len(grouped.get('classes', []))}")
    lines.append("")
    lines.append("---")
    lines.append("")

    # Define section order
    section_order = [
        ('weapons', 'EQUIPMENT - WEAPONS'),
        ('armor', 'EQUIPMENT - ARMOR'),
        ('tools', 'EQUIPMENT - TOOLS'),
        ('accessories', 'EQUIPMENT - ACCESSORIES'),
        ('stations', 'STATIONS'),
        ('devices', 'DEVICES'),
        ('consumables', 'CONSUMABLES'),
        ('materials', 'MATERIALS'),
        ('enemies', 'ENEMIES'),
        ('resources', 'RESOURCES'),
        ('titles', 'TITLES'),
        ('skills', 'SKILLS'),
        ('npcs', 'NPCS'),
        ('quests', 'QUESTS'),
        ('classes', 'CLASSES'),
    ]

    for key, section_name in section_order:
        if key not in grouped:
            continue

        entities_in_section = sorted(grouped[key], key=lambda e: e.id)

        lines.append(f"## {section_name} ({len(entities_in_section)} items)")
        lines.append("")

        for entity in entities_in_section:
            lines.append(f"### {entity.id}")
            lines.append(f"- **Category**: {entity.category}")
            lines.append(f"- **Type**: {entity.type}")
            lines.append(f"- **Subtype**: {entity.subtype}")
            lines.append(f"- **Narrative**: {entity.narrative}")
            lines.append("")

        lines.append("---")
        lines.append("")

    # Write to file
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w') as f:
        f.write('\n'.join(lines))


# ============================================================================
# MAIN
# ============================================================================

def main():
    """Main entry point"""
    print("=" * 70)
    print("UNIFIED ICON & CATALOG GENERATOR (Enhanced)")
    print("=" * 70)

    # Determine base path
    script_dir = Path(__file__).parent
    base_path = script_dir.parent  # Game-1-modular directory
    # Save catalog in Scaled JSON Development (for backward compatibility with automation scripts)
    catalog_path = base_path.parent / "Scaled JSON Development" / "ITEM_CATALOG_FOR_ICONS.md"

    print(f"\nBase path: {base_path}")
    print(f"Catalog output: {catalog_path}")

    # Extract all entities (only those actually loaded by the game)
    print("\n[1/10] Extracting materials...")
    materials = extract_materials(base_path)
    print(f"       Found {len(materials)} materials")

    print("\n[2/10] Extracting equipment...")
    equipment = extract_equipment(base_path)
    print(f"       Found {len(equipment)} equipment items")

    print("\n[3/10] Extracting enemies...")
    enemies = extract_enemies(base_path)
    print(f"       Found {len(enemies)} enemies")

    print("\n[4/10] Extracting titles...")
    titles = extract_titles(base_path)
    print(f"       Found {len(titles)} titles")

    print("\n[5/10] Extracting skills...")
    skills = extract_skills(base_path)
    print(f"       Found {len(skills)} skills")

    print("\n[6/10] Extracting resources...")
    resources = extract_resources(base_path)
    print(f"       Found {len(resources)} resources")

    print("\n[7/10] Extracting NPCs...")
    npcs = extract_npcs(base_path)
    print(f"       Found {len(npcs)} NPCs")

    print("\n[8/10] Extracting quests...")
    quests = extract_quests(base_path)
    print(f"       Found {len(quests)} quests")

    print("\n[9/10] Extracting classes...")
    classes = extract_classes(base_path)
    print(f"       Found {len(classes)} classes")

    # Combine all entities
    all_entities = materials + equipment + enemies + titles + skills + resources + npcs + quests + classes
    print(f"\n✓ Total entities: {len(all_entities)}")

    # Generate placeholders
    print("\n[10/10] Generating placeholders...")
    generated = generate_placeholders(all_entities, base_path)
    print(f"        Generated {generated} new placeholder icons")
    print(f"        (Skipped {len(all_entities) - generated} existing icons)")

    # Generate catalog
    print("\nGenerating catalog markdown...")
    generate_catalog(all_entities, catalog_path)
    print(f"✓ Catalog saved to: {catalog_path}")

    # Final summary
    print("\n" + "=" * 70)
    print("✓ COMPLETE")
    print("=" * 70)
    print(f"Total entities: {len(all_entities)}")
    print(f"New placeholders: {generated}")
    print(f"Existing icons preserved: {len(all_entities) - generated}")
    print(f"Catalog entries: {len(all_entities)}")
    print("\n✓ Placeholders and catalog are now synchronized!")
    print("\n✓ Only entities ACTUALLY LOADED by the game are included.")
    print("\nDirectory structure:")

    # Count existing files
    for subdir in ['materials', 'weapons', 'armor', 'tools', 'accessories', 'stations', 'devices', 'consumables']:
        path = base_path / 'assets' / 'items' / subdir
        count = len(list(path.glob('*.png'))) if path.exists() else 0
        print(f"  - assets/items/{subdir:15s} {count:3d} files")

    for subdir in ['enemies', 'resources', 'titles', 'skills', 'npcs', 'quests', 'classes']:
        path = base_path / 'assets' / subdir
        count = len(list(path.glob('*.png'))) if path.exists() else 0
        print(f"  - assets/{subdir:20s} {count:3d} files")


if __name__ == '__main__':
    main()

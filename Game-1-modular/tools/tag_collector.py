#!/usr/bin/env python3
"""
Tag Collection and Analysis Tool
=================================
Robustly collects all tags from JSON files, detects inconsistencies,
and generates comprehensive documentation for the tag-to-effects system.

This tool will:
1. Recursively scan all JSON files
2. Extract tags from any location (handles schema variations)
3. Track usage locations for each tag
4. Detect potential typos (similar tag names)
5. Categorize tags by function
6. Generate detailed reports
"""

import json
import os
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Set, Tuple
from difflib import SequenceMatcher


class TagCollector:
    """Comprehensive tag collection and analysis system"""

    def __init__(self, root_dir: str):
        self.root_dir = Path(root_dir)
        self.tag_registry = defaultdict(list)  # tag -> [(file, entity_type, entity_id, context)]
        self.all_tags = set()
        self.files_scanned = []
        self.errors = []

    def scan_all_json_files(self):
        """Recursively scan all JSON files in the project"""
        print(f"Scanning directory: {self.root_dir}")

        json_files = list(self.root_dir.rglob("*.JSON")) + list(self.root_dir.rglob("*.json"))

        for json_file in json_files:
            try:
                self._scan_file(json_file)
            except Exception as e:
                self.errors.append(f"Error scanning {json_file}: {e}")

        print(f"\nScanned {len(self.files_scanned)} JSON files")
        print(f"Found {len(self.all_tags)} unique tags")
        if self.errors:
            print(f"Encountered {len(self.errors)} errors")

    def _scan_file(self, filepath: Path):
        """Scan a single JSON file for tags"""
        self.files_scanned.append(str(filepath))

        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)

        # Determine entity type from file structure
        relative_path = filepath.relative_to(self.root_dir)

        # Handle different JSON structures
        if 'items' in data:
            self._scan_items(data['items'], filepath, 'item')
        elif 'skills' in data:
            self._scan_items(data['skills'], filepath, 'skill')
        elif 'enemies' in data:
            self._scan_items(data['enemies'], filepath, 'hostile')
        elif 'recipes' in data:
            self._scan_items(data['recipes'], filepath, 'recipe')
        elif 'resources' in data:
            self._scan_items(data['resources'], filepath, 'resource')
        elif 'npcs' in data:
            self._scan_items(data['npcs'], filepath, 'npc')
        elif 'quests' in data:
            self._scan_items(data['quests'], filepath, 'quest')
        elif 'classes' in data:
            self._scan_items(data['classes'], filepath, 'class')
        elif 'titles' in data:
            self._scan_items(data['titles'], filepath, 'title')
        elif 'stations' in data:
            self._scan_items(data['stations'], filepath, 'station')
        elif 'chunks' in data:
            self._scan_items(data['chunks'], filepath, 'chunk')
        else:
            # Try to scan as a flat list
            if isinstance(data, list):
                self._scan_items(data, filepath, 'unknown')

    def _scan_items(self, items: list, filepath: Path, entity_type: str):
        """Scan a list of items/entities for tags"""
        for item in items:
            if not isinstance(item, dict):
                continue

            # Get entity ID
            entity_id = (
                item.get('itemId') or
                item.get('skillId') or
                item.get('enemyId') or
                item.get('recipeId') or
                item.get('resourceId') or
                item.get('npcId') or
                item.get('questId') or
                item.get('classId') or
                item.get('titleId') or
                item.get('stationId') or
                item.get('id') or
                'unknown'
            )

            # Recursively find all tags in this item
            self._extract_tags_recursive(item, filepath, entity_type, entity_id, [])

    def _extract_tags_recursive(self, obj, filepath: Path, entity_type: str, entity_id: str, path: List[str]):
        """Recursively extract tags from nested structures"""
        if isinstance(obj, dict):
            for key, value in obj.items():
                new_path = path + [key]

                # Check if this key is 'tags' or 'tag'
                if key.lower() in ['tags', 'tag']:
                    self._process_tag_field(value, filepath, entity_type, entity_id, '.'.join(new_path))
                else:
                    # Recurse deeper
                    self._extract_tags_recursive(value, filepath, entity_type, entity_id, new_path)

        elif isinstance(obj, list):
            for i, item in enumerate(obj):
                new_path = path + [f"[{i}]"]
                self._extract_tags_recursive(item, filepath, entity_type, entity_id, new_path)

    def _process_tag_field(self, tags, filepath: Path, entity_type: str, entity_id: str, context: str):
        """Process a field containing tags"""
        if isinstance(tags, list):
            for tag in tags:
                if isinstance(tag, str):
                    self._register_tag(tag, filepath, entity_type, entity_id, context)
        elif isinstance(tags, str):
            # Single tag as string
            self._register_tag(tags, filepath, entity_type, entity_id, context)

    def _register_tag(self, tag: str, filepath: Path, entity_type: str, entity_id: str, context: str):
        """Register a tag occurrence"""
        self.all_tags.add(tag)
        self.tag_registry[tag].append({
            'file': str(filepath.relative_to(self.root_dir)),
            'entity_type': entity_type,
            'entity_id': entity_id,
            'context': context
        })

    def detect_typos(self, similarity_threshold: float = 0.85) -> List[Tuple[str, str, float]]:
        """Detect potential typos by finding similar tag names"""
        potential_typos = []
        tags_list = sorted(self.all_tags)

        for i, tag1 in enumerate(tags_list):
            for tag2 in tags_list[i+1:]:
                similarity = SequenceMatcher(None, tag1, tag2).ratio()

                # Check for very similar tags that might be typos
                if similarity >= similarity_threshold:
                    potential_typos.append((tag1, tag2, similarity))

        return sorted(potential_typos, key=lambda x: x[2], reverse=True)

    def categorize_tags(self) -> Dict[str, Set[str]]:
        """Categorize tags by their likely function"""
        categories = {
            'hand_type': set(),
            'weapon_type': set(),
            'damage_type': set(),
            'attack_geometry': set(),
            'status_effect': set(),
            'equipment_slot': set(),
            'item_quality': set(),
            'item_category': set(),
            'speed_modifier': set(),
            'defensive': set(),
            'elemental': set(),
            'skill_category': set(),
            'enemy_type': set(),
            'ai_behavior': set(),
            'rarity': set(),
            'progression': set(),
            'crafting': set(),
            'gathering': set(),
            'device_type': set(),
            'uncategorized': set()
        }

        # Hand type tags
        hand_type_keywords = ['1H', '2H', 'versatile', 'dual', 'two-handed', 'one-handed']

        # Weapon type tags
        weapon_keywords = ['sword', 'axe', 'spear', 'mace', 'dagger', 'bow', 'staff',
                          'wand', 'hammer', 'polearm', 'crossbow', 'throwing']

        # Damage type tags
        damage_keywords = ['piercing', 'slashing', 'crushing', 'blunt', 'precision',
                          'armor_breaker', 'penetrating']

        # Attack geometry tags
        geometry_keywords = ['chain', 'cone', 'aoe', 'area', 'splash', 'cleave',
                            'sweep', 'beam', 'projectile', 'melee', 'ranged']

        # Status effect tags
        status_keywords = ['burn', 'burning', 'freeze', 'frozen', 'poison', 'poisoned',
                          'slow', 'stun', 'stunned', 'bleed', 'bleeding', 'shock',
                          'electrified', 'weakened', 'strengthened', 'fortified']

        # Speed modifier tags
        speed_keywords = ['fast', 'slow', 'quick', 'rapid', 'swift', 'sluggish']

        # Defensive tags
        defensive_keywords = ['shield', 'armor', 'defense', 'defensive', 'blocking',
                             'parry', 'dodge', 'evasion', 'resistant', 'immunity']

        # Elemental tags
        elemental_keywords = ['fire', 'ice', 'lightning', 'water', 'earth', 'wind',
                             'nature', 'arcane', 'holy', 'shadow', 'void', 'energy',
                             'electric', 'thermal', 'frost', 'flame']

        # Skill category tags
        skill_keywords = ['damage_boost', 'gathering', 'combat', 'crafting', 'mining',
                         'woodcutting', 'fishing', 'alchemy', 'smithing', 'engineering',
                         'enchanting', 'refining', 'efficiency', 'ultimate', 'basic']

        # Enemy type tags
        enemy_keywords = ['wolf', 'beetle', 'spider', 'skeleton', 'zombie', 'demon',
                         'dragon', 'entity', 'creature', 'beast', 'undead', 'construct']

        # AI behavior tags
        ai_keywords = ['passive', 'aggressive', 'defensive', 'ranged_attacker',
                      'melee_fighter', 'support', 'flee', 'charge']

        # Rarity tags
        rarity_keywords = ['common', 'uncommon', 'rare', 'epic', 'legendary', 'mythical',
                          'unique', 'starter', 'basic', 'advanced', 'elite', 'boss',
                          'end-game']

        # Progression tags
        progression_keywords = ['starter', 'beginner', 'intermediate', 'advanced',
                               'expert', 'master', 'tier1', 'tier2', 'tier3', 'tier4']

        # Crafting tags
        crafting_keywords = ['smithing', 'alchemy', 'engineering', 'enchanting',
                            'refining', 'ingredient', 'material', 'component']

        # Gathering tags
        gathering_keywords = ['mining', 'woodcutting', 'fishing', 'harvesting',
                             'gathering', 'extracting', 'foraging']

        # Device type tags
        device_keywords = ['device', 'turret', 'trap', 'bomb', 'utility', 'deployable',
                          'placed', 'automated']

        # Equipment slot tags
        slot_keywords = ['helmet', 'chestplate', 'leggings', 'boots', 'gauntlets',
                        'accessory', 'tool', 'mainhand', 'offhand']

        # Item category tags
        item_keywords = ['weapon', 'armor', 'consumable', 'potion', 'material',
                        'equipment', 'tool', 'resource']

        # Categorize each tag
        for tag in self.all_tags:
            tag_lower = tag.lower()
            categorized = False

            # Check each category
            if any(keyword in tag_lower for keyword in hand_type_keywords):
                categories['hand_type'].add(tag)
                categorized = True

            if any(keyword in tag_lower for keyword in weapon_keywords):
                categories['weapon_type'].add(tag)
                categorized = True

            if any(keyword in tag_lower for keyword in damage_keywords):
                categories['damage_type'].add(tag)
                categorized = True

            if any(keyword in tag_lower for keyword in geometry_keywords):
                categories['attack_geometry'].add(tag)
                categorized = True

            if any(keyword in tag_lower for keyword in status_keywords):
                categories['status_effect'].add(tag)
                categorized = True

            if any(keyword in tag_lower for keyword in speed_keywords):
                categories['speed_modifier'].add(tag)
                categorized = True

            if any(keyword in tag_lower for keyword in defensive_keywords):
                categories['defensive'].add(tag)
                categorized = True

            if any(keyword in tag_lower for keyword in elemental_keywords):
                categories['elemental'].add(tag)
                categorized = True

            if any(keyword in tag_lower for keyword in skill_keywords):
                categories['skill_category'].add(tag)
                categorized = True

            if any(keyword in tag_lower for keyword in enemy_keywords):
                categories['enemy_type'].add(tag)
                categorized = True

            if any(keyword in tag_lower for keyword in ai_keywords):
                categories['ai_behavior'].add(tag)
                categorized = True

            if any(keyword in tag_lower for keyword in rarity_keywords):
                categories['rarity'].add(tag)
                categorized = True

            if any(keyword in tag_lower for keyword in progression_keywords):
                categories['progression'].add(tag)
                categorized = True

            if any(keyword in tag_lower for keyword in crafting_keywords):
                categories['crafting'].add(tag)
                categorized = True

            if any(keyword in tag_lower for keyword in gathering_keywords):
                categories['gathering'].add(tag)
                categorized = True

            if any(keyword in tag_lower for keyword in device_keywords):
                categories['device_type'].add(tag)
                categorized = True

            if any(keyword in tag_lower for keyword in slot_keywords):
                categories['equipment_slot'].add(tag)
                categorized = True

            if any(keyword in tag_lower for keyword in item_keywords):
                categories['item_category'].add(tag)
                categorized = True

            if not categorized:
                categories['uncategorized'].add(tag)

        return categories

    def generate_report(self, output_file: str = None):
        """Generate comprehensive tag analysis report"""
        lines = []
        lines.append("=" * 80)
        lines.append("TAG COLLECTION AND ANALYSIS REPORT")
        lines.append("=" * 80)
        lines.append("")

        # Summary
        lines.append("SUMMARY")
        lines.append("-" * 80)
        lines.append(f"Total JSON files scanned: {len(self.files_scanned)}")
        lines.append(f"Total unique tags found: {len(self.all_tags)}")
        lines.append(f"Total tag occurrences: {sum(len(occurrences) for occurrences in self.tag_registry.values())}")
        lines.append("")

        # Errors
        if self.errors:
            lines.append("ERRORS ENCOUNTERED")
            lines.append("-" * 80)
            for error in self.errors:
                lines.append(f"  - {error}")
            lines.append("")

        # Tag categories
        categories = self.categorize_tags()
        lines.append("TAG CATEGORIES")
        lines.append("-" * 80)
        for category, tags in sorted(categories.items()):
            if tags:  # Only show non-empty categories
                lines.append(f"\n{category.upper().replace('_', ' ')} ({len(tags)} tags):")
                for tag in sorted(tags):
                    count = len(self.tag_registry[tag])
                    lines.append(f"  - {tag} ({count} occurrences)")
        lines.append("")

        # Potential typos
        typos = self.detect_typos()
        if typos:
            lines.append("POTENTIAL TYPOS / SIMILAR TAGS")
            lines.append("-" * 80)
            lines.append("These tags are very similar and might be typos or inconsistencies:")
            for tag1, tag2, similarity in typos:
                lines.append(f"  - '{tag1}' vs '{tag2}' (similarity: {similarity:.2%})")
            lines.append("")

        # Detailed tag registry
        lines.append("DETAILED TAG REGISTRY")
        lines.append("-" * 80)
        for tag in sorted(self.all_tags):
            occurrences = self.tag_registry[tag]
            lines.append(f"\n{tag} ({len(occurrences)} occurrences):")

            # Group by entity type
            by_type = defaultdict(list)
            for occ in occurrences:
                by_type[occ['entity_type']].append(occ)

            for entity_type, occs in sorted(by_type.items()):
                lines.append(f"  {entity_type}:")
                for occ in occs[:10]:  # Limit to first 10 per type
                    lines.append(f"    - {occ['entity_id']} ({occ['file']})")
                if len(occs) > 10:
                    lines.append(f"    ... and {len(occs) - 10} more")

        # Join all lines
        report = "\n".join(lines)

        # Output
        if output_file:
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(report)
            print(f"\nReport written to: {output_file}")

        return report

    def generate_json_export(self, output_file: str):
        """Export tag registry as JSON for programmatic use"""
        export_data = {
            'summary': {
                'total_files': len(self.files_scanned),
                'total_unique_tags': len(self.all_tags),
                'total_occurrences': sum(len(occurrences) for occurrences in self.tag_registry.values())
            },
            'tags': {},
            'categories': {},
            'potential_typos': []
        }

        # Tag registry
        for tag, occurrences in self.tag_registry.items():
            export_data['tags'][tag] = occurrences

        # Categories
        categories = self.categorize_tags()
        for category, tags in categories.items():
            export_data['categories'][category] = sorted(tags)

        # Typos
        typos = self.detect_typos()
        export_data['potential_typos'] = [
            {'tag1': t1, 'tag2': t2, 'similarity': sim}
            for t1, t2, sim in typos
        ]

        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(export_data, f, indent=2)

        print(f"JSON export written to: {output_file}")


def main():
    """Main execution"""
    import sys

    # Use provided directory or default to Game-1-modular
    if len(sys.argv) > 1:
        root_dir = sys.argv[1]
    else:
        root_dir = "/home/user/Game-1/Game-1-modular"

    print("=" * 80)
    print("TAG COLLECTION AND ANALYSIS TOOL")
    print("=" * 80)
    print()

    collector = TagCollector(root_dir)
    collector.scan_all_json_files()

    # Generate reports
    report_dir = Path(root_dir) / "docs" / "tag-system"
    report_dir.mkdir(parents=True, exist_ok=True)

    text_report = report_dir / "tag-inventory.txt"
    json_report = report_dir / "tag-inventory.json"

    collector.generate_report(str(text_report))
    collector.generate_json_export(str(json_report))

    print("\n" + "=" * 80)
    print("COLLECTION COMPLETE")
    print("=" * 80)
    print(f"Text report: {text_report}")
    print(f"JSON export: {json_report}")


if __name__ == "__main__":
    main()

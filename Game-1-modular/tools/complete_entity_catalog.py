#!/usr/bin/env python3
"""
Complete Entity Catalog Generator

Scans ALL JSON files in the game and extracts every unique entity ID.
This is comprehensive and includes everything: items, NPCs, quests, classes,
enemies, resources, skills, titles, recipes, placements, etc.

Author: Auto-generated
Date: 2025-12-08
"""

import json
import os
from pathlib import Path
from collections import defaultdict
from typing import Dict, List, Any, Set


class EntityCatalog:
    """Scans and catalogs all game entities from JSON files"""

    def __init__(self, base_path: str = None):
        if base_path is None:
            # Default to the Game-1-modular directory
            self.base_path = Path(__file__).parent.parent
        else:
            self.base_path = Path(base_path)

        self.entities = defaultdict(list)
        self.stats = defaultdict(int)

    def scan_all_json_files(self):
        """Scan all JSON files and extract entities"""
        print(f"Scanning directory: {self.base_path}")
        print("=" * 80)

        # Find all JSON files
        json_files = list(self.base_path.rglob("*.JSON"))
        json_files.extend(list(self.base_path.rglob("*.json")))

        print(f"Found {len(json_files)} JSON files\n")

        for json_file in sorted(json_files):
            try:
                self.process_json_file(json_file)
            except Exception as e:
                print(f"Error processing {json_file}: {e}")

    def process_json_file(self, file_path: Path):
        """Process a single JSON file"""
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        rel_path = file_path.relative_to(self.base_path)

        # Some files contain multiple entity types (e.g., items-smithing-2.JSON has both
        # weapons/armor/accessories AND stations). We need to check and extract ALL types.
        entities_found = False

        # Check for equipment categories first (weapons, armor, etc.)
        for category_name in ['weapons', 'armor', 'accessories', 'shields', 'tools']:
            if category_name in data:
                self.extract_items(data[category_name], rel_path)
                entities_found = True

        # Check for all other entity types
        if 'items' in data:
            self.extract_items(data['items'], rel_path)
            entities_found = True

        if 'materials' in data:
            self.extract_materials(data['materials'], rel_path)
            entities_found = True

        if 'recipes' in data:
            self.extract_recipes(data['recipes'], rel_path)
            entities_found = True

        if 'placements' in data:
            self.extract_placements(data['placements'], rel_path)
            entities_found = True

        if 'enemies' in data:
            self.extract_enemies(data['enemies'], rel_path)
            entities_found = True

        if 'resources' in data:
            self.extract_resources(data['resources'], rel_path)
            entities_found = True

        if 'skills' in data:
            self.extract_skills(data['skills'], rel_path)
            entities_found = True

        if 'titles' in data:
            self.extract_titles(data['titles'], rel_path)
            entities_found = True

        if 'npcs' in data:
            self.extract_npcs(data['npcs'], rel_path)
            entities_found = True

        if 'quests' in data:
            self.extract_quests(data['quests'], rel_path)
            entities_found = True

        if 'classes' in data:
            self.extract_classes(data['classes'], rel_path)
            entities_found = True

        if 'stations' in data:
            self.extract_stations(data['stations'], rel_path)
            entities_found = True

        if 'nodes' in data:
            # resource-node-1.JSON uses "nodes" instead of "resources"
            self.extract_resources(data['nodes'], rel_path)
            entities_found = True

        # If no entities were found, this might be a metadata-only or config file
        if not entities_found and 'metadata' in data:
            pass  # Just a configuration file, skip

    def extract_items(self, items: List[Dict], source_file: Path):
        """Extract equipment items"""
        for item in items:
            entity = {
                'id': item.get('itemId', 'UNKNOWN'),
                'name': item.get('name', 'Unnamed'),
                'category': 'equipment',
                'type': item.get('type', 'unknown'),
                'subtype': item.get('subtype', item.get('slot', 'unknown')),
                'tier': item.get('tier', 0),
                'source_file': str(source_file),
                'icon_path': item.get('iconPath', 'NOT_SPECIFIED'),
                'narrative': item.get('narrative', '')
            }
            self.entities['EQUIPMENT'].append(entity)
            self.stats['EQUIPMENT'] += 1

    def extract_materials(self, materials: List[Dict], source_file: Path):
        """Extract material items"""
        for mat in materials:
            entity = {
                'id': mat.get('materialId', 'UNKNOWN'),
                'name': mat.get('name', 'Unnamed'),
                'category': mat.get('category', 'material'),
                'type': mat.get('type', 'unknown'),
                'subtype': mat.get('subtype', 'unknown'),
                'tier': mat.get('tier', 0),
                'source_file': str(source_file),
                'icon_path': mat.get('iconPath', 'NOT_SPECIFIED'),
                'narrative': mat.get('narrative', '')
            }
            self.entities['MATERIALS'].append(entity)
            self.stats['MATERIALS'] += 1

    def extract_recipes(self, recipes: List[Dict], source_file: Path):
        """Extract crafting recipes"""
        for recipe in recipes:
            entity = {
                'id': recipe.get('recipeId', 'UNKNOWN'),
                'name': recipe.get('name', 'Unnamed'),
                'category': 'recipe',
                'discipline': recipe.get('discipline', 'unknown'),
                'type': recipe.get('type', 'unknown'),
                'tier': recipe.get('tier', 0),
                'source_file': str(source_file),
                'output': recipe.get('output', {}).get('materialId') or recipe.get('output', {}).get('itemId', 'UNKNOWN')
            }
            self.entities['RECIPES'].append(entity)
            self.stats['RECIPES'] += 1

    def extract_placements(self, placements: List[Dict], source_file: Path):
        """Extract placement patterns"""
        for placement in placements:
            entity = {
                'id': placement.get('placementId', 'UNKNOWN'),
                'name': placement.get('name', 'Unnamed'),
                'category': 'placement',
                'discipline': placement.get('discipline', 'unknown'),
                'tier': placement.get('tier', 0),
                'source_file': str(source_file),
                'related_item': placement.get('relatedItemId', 'NONE')
            }
            self.entities['PLACEMENTS'].append(entity)
            self.stats['PLACEMENTS'] += 1

    def extract_enemies(self, enemies: List[Dict], source_file: Path):
        """Extract enemy definitions"""
        for enemy in enemies:
            entity = {
                'id': enemy.get('enemyId', 'UNKNOWN'),
                'name': enemy.get('name', 'Unnamed'),
                'category': 'enemy',
                'type': enemy.get('type', 'hostile'),
                'tier': enemy.get('tier', 0),
                'source_file': str(source_file),
                'icon_path': enemy.get('iconPath', 'NOT_SPECIFIED'),
                'narrative': enemy.get('narrative', '')
            }
            self.entities['ENEMIES'].append(entity)
            self.stats['ENEMIES'] += 1

    def extract_resources(self, resources: List[Dict], source_file: Path):
        """Extract resource node definitions"""
        for resource in resources:
            entity = {
                'id': resource.get('resourceId', 'UNKNOWN'),
                'name': resource.get('name', 'Unnamed'),
                'category': 'resource',
                'type': resource.get('type', 'node'),
                'source_file': str(source_file),
                'icon_path': resource.get('iconPath', 'NOT_SPECIFIED'),
                'yields': resource.get('drops', [{}])[0].get('materialId', 'UNKNOWN') if resource.get('drops') else 'UNKNOWN'
            }
            self.entities['RESOURCES'].append(entity)
            self.stats['RESOURCES'] += 1

    def extract_skills(self, skills: List[Dict], source_file: Path):
        """Extract skill definitions"""
        for skill in skills:
            entity = {
                'id': skill.get('skillId', 'UNKNOWN'),
                'name': skill.get('name', 'Unnamed'),
                'category': 'skill',
                'type': skill.get('type', 'unknown'),
                'tier': skill.get('tier', 0),
                'source_file': str(source_file),
                'icon_path': skill.get('iconPath', 'NOT_SPECIFIED'),
                'description': skill.get('description', '')
            }
            self.entities['SKILLS'].append(entity)
            self.stats['SKILLS'] += 1

    def extract_titles(self, titles: List[Dict], source_file: Path):
        """Extract title definitions"""
        for title in titles:
            entity = {
                'id': title.get('titleId', 'UNKNOWN'),
                'name': title.get('name', 'Unnamed'),
                'category': 'title',
                'rarity': title.get('rarity', 'common'),
                'source_file': str(source_file),
                'icon_path': title.get('iconPath', 'NOT_SPECIFIED'),
                'description': title.get('description', '')
            }
            self.entities['TITLES'].append(entity)
            self.stats['TITLES'] += 1

    def extract_npcs(self, npcs: List[Dict], source_file: Path):
        """Extract NPC definitions"""
        for npc in npcs:
            entity = {
                'id': npc.get('npc_id', 'UNKNOWN'),
                'name': npc.get('name', 'Unnamed'),
                'category': 'npc',
                'type': 'npc',
                'source_file': str(source_file),
                'icon_path': npc.get('iconPath', npc.get('sprite', 'NOT_SPECIFIED')),
                'dialogue': npc.get('dialogue_lines', []),
                'quests': npc.get('quests', [])
            }
            self.entities['NPCS'].append(entity)
            self.stats['NPCS'] += 1

    def extract_quests(self, quests: List[Dict], source_file: Path):
        """Extract quest definitions"""
        for quest in quests:
            entity = {
                'id': quest.get('quest_id', 'UNKNOWN'),
                'name': quest.get('title', 'Unnamed'),
                'category': 'quest',
                'type': quest.get('objectives', {}).get('type', 'unknown'),
                'source_file': str(source_file),
                'icon_path': quest.get('iconPath', 'NOT_SPECIFIED'),
                'description': quest.get('description', ''),
                'npc': quest.get('npc_id', 'NONE')
            }
            self.entities['QUESTS'].append(entity)
            self.stats['QUESTS'] += 1

    def extract_classes(self, classes: List[Dict], source_file: Path):
        """Extract character class definitions"""
        for char_class in classes:
            entity = {
                'id': char_class.get('classId', 'UNKNOWN'),
                'name': char_class.get('name', 'Unnamed'),
                'category': 'class',
                'type': 'character_class',
                'source_file': str(source_file),
                'icon_path': char_class.get('iconPath', 'NOT_SPECIFIED'),
                'description': char_class.get('description', ''),
                'narrative': char_class.get('narrative', ''),
                'playstyle': char_class.get('playstyle', '')
            }
            self.entities['CLASSES'].append(entity)
            self.stats['CLASSES'] += 1

    def extract_stations(self, stations: List[Dict], source_file: Path):
        """Extract crafting station definitions"""
        for station in stations:
            entity = {
                'id': station.get('stationId', 'UNKNOWN'),
                'name': station.get('name', 'Unnamed'),
                'category': 'station',
                'type': station.get('type', 'crafting'),
                'source_file': str(source_file),
                'icon_path': station.get('iconPath', 'NOT_SPECIFIED')
            }
            self.entities['STATIONS'].append(entity)
            self.stats['STATIONS'] += 1

    def generate_report(self, output_file: str = None):
        """Generate a comprehensive report of all entities"""
        lines = []
        lines.append("=" * 80)
        lines.append("COMPLETE ENTITY CATALOG")
        lines.append("=" * 80)
        lines.append("")
        lines.append("This catalog includes EVERY entity defined in the game's JSON files.")
        lines.append("")

        # Summary
        lines.append("SUMMARY")
        lines.append("-" * 80)
        total = sum(self.stats.values())
        for category in sorted(self.stats.keys()):
            lines.append(f"  {category}: {self.stats[category]}")
        lines.append(f"\n  TOTAL: {total} entities")
        lines.append("")

        # Detailed listings
        for category in sorted(self.entities.keys()):
            lines.append("")
            lines.append("=" * 80)
            lines.append(f"{category} ({len(self.entities[category])} entities)")
            lines.append("=" * 80)
            lines.append("")

            for entity in sorted(self.entities[category], key=lambda x: x['id']):
                lines.append(f"### {entity['id']}")
                for key, value in sorted(entity.items()):
                    if key != 'id' and value:
                        # Format lists nicely
                        if isinstance(value, list):
                            if value:
                                lines.append(f"  - {key}: {', '.join(str(v) for v in value[:3])}{'...' if len(value) > 3 else ''}")
                        else:
                            lines.append(f"  - {key}: {value}")
                lines.append("")

        report = "\n".join(lines)

        # Print to console
        print(report)

        # Save to file if specified
        if output_file:
            output_path = Path(output_file)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(report)
            print(f"\nReport saved to: {output_path}")

        return report

    def generate_missing_icons_report(self):
        """Generate a report of entities missing icon paths"""
        lines = []
        lines.append("=" * 80)
        lines.append("ENTITIES MISSING ICON PATHS")
        lines.append("=" * 80)
        lines.append("")

        missing_by_category = defaultdict(list)

        for category, entities in self.entities.items():
            for entity in entities:
                icon_path = entity.get('icon_path', 'NOT_SPECIFIED')
                if icon_path == 'NOT_SPECIFIED' or not icon_path:
                    missing_by_category[category].append(entity)

        if not any(missing_by_category.values()):
            lines.append("All entities have icon paths defined!")
        else:
            for category in sorted(missing_by_category.keys()):
                if missing_by_category[category]:
                    lines.append(f"\n{category} ({len(missing_by_category[category])} missing):")
                    lines.append("-" * 80)
                    for entity in sorted(missing_by_category[category], key=lambda x: x['id']):
                        lines.append(f"  - {entity['id']}: {entity['name']}")

        report = "\n".join(lines)
        print("\n" + report)
        return report

    def export_to_json(self, output_file: str):
        """Export all entities to a JSON file"""
        output_path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        export_data = {
            'metadata': {
                'generated': '2025-12-08',
                'total_entities': sum(self.stats.values()),
                'categories': dict(self.stats)
            },
            'entities': dict(self.entities)
        }

        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(export_data, f, indent=2)

        print(f"JSON export saved to: {output_path}")


def main():
    """Main execution"""
    catalog = EntityCatalog()

    print("Scanning all JSON files in the game...")
    print("")

    catalog.scan_all_json_files()

    print("\n" + "=" * 80)
    print("SCAN COMPLETE")
    print("=" * 80)
    print("")

    # Generate reports
    catalog.generate_report(output_file="../Scaled JSON Development/COMPLETE_ENTITY_CATALOG.txt")
    catalog.generate_missing_icons_report()
    catalog.export_to_json(output_file="../Scaled JSON Development/complete_entity_catalog.json")


if __name__ == "__main__":
    main()

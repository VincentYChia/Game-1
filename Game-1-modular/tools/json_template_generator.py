#!/usr/bin/env python3
"""
JSON Template Generator for Game-1

This script analyzes all JSON files in the game and generates comprehensive
templates that show ALL possible values for each field across all files of
that type.

Usage:
    python json_template_generator.py [--output-dir OUTPUT_DIR]

Output:
    Creates a 'json_templates/' directory with:
    - One template file per JSON category
    - A master summary file
"""

import json
import os
import argparse
from pathlib import Path
from collections import defaultdict
from typing import Any, Dict, List, Set, Union
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class FieldInfo:
    """Tracks all values seen for a field across multiple files."""
    values: Set[Any] = field(default_factory=set)
    types: Set[str] = field(default_factory=set)
    is_array: bool = False
    array_item_values: Set[Any] = field(default_factory=set)
    nested_fields: Dict[str, 'FieldInfo'] = field(default_factory=dict)
    occurrences: int = 0
    source_files: Set[str] = field(default_factory=set)


class JSONTemplateGenerator:
    """Generates comprehensive JSON templates from all game data files."""

    # Define JSON categories and their file patterns
    CATEGORIES = {
        'items-materials': {
            'directory': 'items.JSON',
            'pattern': 'items-materials',
            'root_key': 'materials',
            'description': 'Raw materials and crafting ingredients'
        },
        'items-equipment': {
            'directory': 'items.JSON',
            'pattern': 'items-smithing',
            'root_keys': ['weapons', 'armor_helmets', 'armor_chests', 'armor_legs', 'armor_boots', 'shields'],
            'description': 'Weapons, armor, and shields'
        },
        'items-alchemy': {
            'directory': 'items.JSON',
            'pattern': 'items-alchemy',
            'root_keys': ['potions_healing', 'potions_mana', 'potions_buff', 'elixirs'],
            'description': 'Potions, elixirs, and consumables'
        },
        'items-refining': {
            'directory': 'items.JSON',
            'pattern': 'items-refining',
            'root_keys': ['basic_ingots', 'alloys', 'wood_planks'],
            'description': 'Processed materials (ingots, planks, alloys)'
        },
        'items-engineering': {
            'directory': 'items.JSON',
            'pattern': 'items-engineering',
            'description': 'Engineering devices and gadgets'
        },
        'items-tools': {
            'directory': 'items.JSON',
            'pattern': 'items-tools',
            'description': 'Placeable crafting tools and stations'
        },
        'recipes-smithing': {
            'directory': 'recipes.JSON',
            'pattern': 'recipes-smithing',
            'root_key': 'recipes',
            'description': 'Smithing recipes for weapons and armor'
        },
        'recipes-alchemy': {
            'directory': 'recipes.JSON',
            'pattern': 'recipes-alchemy',
            'root_key': 'recipes',
            'description': 'Alchemy recipes for potions'
        },
        'recipes-refining': {
            'directory': 'recipes.JSON',
            'pattern': 'recipes-refining',
            'root_key': 'recipes',
            'description': 'Refining recipes for material processing'
        },
        'recipes-engineering': {
            'directory': 'recipes.JSON',
            'pattern': 'recipes-engineering',
            'root_key': 'recipes',
            'description': 'Engineering recipes for devices'
        },
        'recipes-enchanting': {
            'directory': 'recipes.JSON',
            'pattern': 'recipes-enchanting',
            'root_key': 'recipes',
            'description': 'Enchanting recipes'
        },
        'recipes-adornments': {
            'directory': 'recipes.JSON',
            'pattern': 'recipes-adornments',
            'root_key': 'recipes',
            'description': 'Adornment and accessory recipes'
        },
        'placements': {
            'directory': 'placements.JSON',
            'pattern': 'placements-',
            'root_key': 'placements',
            'description': 'Minigame grid placement patterns'
        },
        'skills': {
            'directory': 'Skills',
            'pattern': 'skills-skills',
            'root_key': 'skills',
            'description': 'Player skill definitions'
        },
        'classes': {
            'directory': 'progression',
            'pattern': 'classes',
            'root_key': 'classes',
            'description': 'Starting class definitions'
        },
        'titles': {
            'directory': 'progression',
            'pattern': 'titles',
            'root_key': 'titles',
            'description': 'Achievement title definitions'
        },
        'npcs': {
            'directory': 'progression',
            'pattern': 'npcs',
            'description': 'NPC definitions'
        },
        'quests': {
            'directory': 'progression',
            'pattern': 'quests',
            'description': 'Quest definitions'
        },
        'resource-nodes': {
            'directory': 'Definitions.JSON',
            'pattern': 'resource-node',
            'root_key': 'nodes',
            'description': 'Gatherable resource node definitions'
        },
        'hostiles': {
            'directory': 'Definitions.JSON',
            'pattern': 'hostiles',
            'root_keys': ['enemies', 'abilities'],
            'description': 'Enemy and ability definitions'
        },
        'tag-definitions': {
            'directory': 'Definitions.JSON',
            'pattern': 'tag-definitions',
            'description': 'Master tag system definitions'
        },
        'value-translations': {
            'directory': 'Definitions.JSON',
            'pattern': 'value-translation',
            'description': 'Qualitative to numeric value mappings'
        },
        'crafting-stations': {
            'directory': 'Definitions.JSON',
            'pattern': 'crafting-stations',
            'description': 'Crafting station definitions'
        }
    }

    def __init__(self, base_path: str):
        self.base_path = Path(base_path)
        self.templates: Dict[str, Dict] = {}
        self.field_registry: Dict[str, Dict[str, FieldInfo]] = defaultdict(lambda: defaultdict(FieldInfo))
        self.all_tags: Set[str] = set()
        self.all_effect_types: Set[str] = set()
        self.all_item_ids: Set[str] = set()
        self.all_material_ids: Set[str] = set()
        self.all_skill_ids: Set[str] = set()

    def find_json_files(self) -> Dict[str, List[Path]]:
        """Find all JSON files organized by category."""
        files_by_category: Dict[str, List[Path]] = defaultdict(list)

        for category, config in self.CATEGORIES.items():
            directory = self.base_path / config['directory']
            if not directory.exists():
                continue

            pattern = config.get('pattern', '')
            for json_file in directory.glob('*.JSON'):
                if pattern in json_file.name.lower():
                    files_by_category[category].append(json_file)
            for json_file in directory.glob('*.json'):
                if pattern in json_file.name.lower():
                    files_by_category[category].append(json_file)

        return files_by_category

    def extract_values(self, obj: Any, path: str, category: str, source_file: str):
        """Recursively extract all values from a JSON object."""
        field_info = self.field_registry[category][path]
        field_info.occurrences += 1
        field_info.source_files.add(source_file)

        if obj is None:
            field_info.values.add(None)
            field_info.types.add('null')
        elif isinstance(obj, bool):
            field_info.values.add(obj)
            field_info.types.add('boolean')
        elif isinstance(obj, int):
            field_info.values.add(obj)
            field_info.types.add('integer')
        elif isinstance(obj, float):
            field_info.values.add(obj)
            field_info.types.add('number')
        elif isinstance(obj, str):
            field_info.values.add(obj)
            field_info.types.add('string')
            # Track special field values
            if 'tag' in path.lower():
                self.all_tags.add(obj)
            if path.endswith('.materialId') or path.endswith('.itemId'):
                self.all_material_ids.add(obj)
            if path.endswith('.skillId'):
                self.all_skill_ids.add(obj)
        elif isinstance(obj, list):
            field_info.is_array = True
            field_info.types.add('array')
            for i, item in enumerate(obj):
                if isinstance(item, dict):
                    self.extract_values(item, f"{path}[]", category, source_file)
                else:
                    field_info.array_item_values.add(self._make_hashable(item))
                    if isinstance(item, str) and 'tag' in path.lower():
                        self.all_tags.add(item)
        elif isinstance(obj, dict):
            field_info.types.add('object')
            for key, value in obj.items():
                new_path = f"{path}.{key}" if path else key
                self.extract_values(value, new_path, category, source_file)

    def _make_hashable(self, obj: Any) -> Any:
        """Convert an object to a hashable type."""
        if isinstance(obj, dict):
            return tuple(sorted((k, self._make_hashable(v)) for k, v in obj.items()))
        elif isinstance(obj, list):
            return tuple(self._make_hashable(item) for item in obj)
        return obj

    def process_category(self, category: str, files: List[Path]):
        """Process all files in a category."""
        config = self.CATEGORIES.get(category, {})

        for json_file in files:
            try:
                with open(json_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
            except (json.JSONDecodeError, UnicodeDecodeError) as e:
                print(f"  Warning: Could not parse {json_file.name}: {e}")
                continue

            # Handle root keys
            root_key = config.get('root_key')
            root_keys = config.get('root_keys', [])

            items_to_process = []

            if root_key and root_key in data:
                items_to_process = data[root_key]
            elif root_keys:
                for rk in root_keys:
                    if rk in data:
                        items_to_process.extend(data[rk])
            else:
                # Process the whole file as-is
                items_to_process = [data] if isinstance(data, dict) else data

            for item in items_to_process:
                if isinstance(item, dict):
                    self.extract_values(item, '', category, json_file.name)

    def generate_template(self, category: str) -> Dict:
        """Generate a comprehensive template for a category."""
        template = {
            '_meta': {
                'category': category,
                'description': self.CATEGORIES.get(category, {}).get('description', ''),
                'generated_at': datetime.now().isoformat(),
                'source_files': [],
                'total_items_analyzed': 0
            },
            '_field_documentation': {},
            '_all_possible_values': {},
            '_usable_template': {},  # Clean copy-paste template
            'template': {}
        }

        fields = self.field_registry.get(category, {})

        # Collect source files and count
        all_sources = set()
        for field_info in fields.values():
            all_sources.update(field_info.source_files)
        template['_meta']['source_files'] = sorted(all_sources)

        # Build template structure
        for path, field_info in sorted(fields.items()):
            if not path:  # Skip empty root path
                continue

            # Build the all_possible_values section
            values_key = path.replace('.', '_').replace('[]', '_array')

            if field_info.is_array and field_info.array_item_values:
                values = sorted([v for v in field_info.array_item_values if v is not None],
                              key=lambda x: str(x))
            else:
                values = sorted([v for v in field_info.values if v is not None and not isinstance(v, (dict, list))],
                              key=lambda x: str(x))

            if values:
                template['_all_possible_values'][path] = {
                    'values': values[:100],  # Limit to 100 values
                    'count': len(values),
                    'types': list(field_info.types),
                    'occurrences': field_info.occurrences
                }

            # Build nested template structure
            self._set_nested_value(template['template'], path, field_info)

        # Build the clean usable template
        template['_usable_template'] = self._build_usable_template(category, fields)

        return template

    def _build_usable_template(self, category: str, fields: Dict[str, FieldInfo]) -> Dict:
        """Build a clean, copy-paste ready template with placeholder comments."""
        usable = {}

        for path, field_info in sorted(fields.items()):
            if not path or '[]' in path:  # Skip empty and array element paths
                continue

            parts = path.split('.')
            current = usable

            for i, part in enumerate(parts[:-1]):
                if part not in current:
                    current[part] = {}
                current = current[part]

            final_key = parts[-1] if parts else 'value'

            # Determine the example value
            if field_info.is_array:
                sample_values = list(field_info.array_item_values)[:3]
                current[final_key] = sample_values if sample_values else ["<value>"]
            elif 'boolean' in field_info.types:
                current[final_key] = True
            elif 'integer' in field_info.types:
                int_vals = [v for v in field_info.values if isinstance(v, int)]
                current[final_key] = int_vals[0] if int_vals else 0
            elif 'number' in field_info.types:
                num_vals = [v for v in field_info.values if isinstance(v, (int, float))]
                current[final_key] = num_vals[0] if num_vals else 0.0
            elif 'string' in field_info.types:
                str_vals = [v for v in field_info.values if isinstance(v, str)]
                current[final_key] = str_vals[0] if str_vals else "<string>"
            elif 'object' in field_info.types:
                if final_key not in current:
                    current[final_key] = {}
            else:
                current[final_key] = None

        return usable

    def _set_nested_value(self, obj: Dict, path: str, field_info: FieldInfo):
        """Set a value in a nested dictionary using dot notation."""
        parts = path.replace('[]', '').split('.')
        current = obj

        for i, part in enumerate(parts[:-1]):
            if part not in current:
                current[part] = {}
            current = current[part]

        final_key = parts[-1] if parts else 'root'

        # Create field template
        if field_info.is_array:
            sample_values = list(field_info.array_item_values)[:5]
            current[final_key] = {
                '_type': 'array',
                '_sample_values': sample_values,
                '_total_unique_values': len(field_info.array_item_values)
            }
        elif 'object' in field_info.types:
            if final_key not in current:
                current[final_key] = {}
        else:
            sample_values = [v for v in list(field_info.values)[:10]
                          if not isinstance(v, (dict, list))]
            current[final_key] = {
                '_type': list(field_info.types)[0] if field_info.types else 'unknown',
                '_sample_values': sample_values,
                '_total_unique_values': len(field_info.values)
            }

    def generate_master_tag_list(self) -> Dict:
        """Generate a comprehensive list of all tags found."""
        # Collect more comprehensive value lists
        all_values = {
            '_meta': {
                'description': 'Master reference of all values found across all JSON files',
                'generated_at': datetime.now().isoformat(),
                'total_unique_tags': len(self.all_tags),
                'total_unique_material_ids': len(self.all_material_ids),
                'total_unique_skill_ids': len(self.all_skill_ids)
            },
            'all_tags': sorted(self.all_tags),
            'all_material_ids': sorted(self.all_material_ids),
            'all_skill_ids': sorted(self.all_skill_ids),
            'enum_values': {}
        }

        # Collect enum-like values from all categories
        enum_fields = {}
        for category, fields in self.field_registry.items():
            for path, field_info in fields.items():
                # Fields that look like enums (limited set of string values)
                if 'string' in field_info.types:
                    str_values = [v for v in field_info.values if isinstance(v, str)]
                    # If there are between 2 and 30 unique values, it's likely an enum
                    if 2 <= len(str_values) <= 30:
                        field_name = path.split('.')[-1] if path else 'unknown'
                        if field_name not in enum_fields:
                            enum_fields[field_name] = set()
                        enum_fields[field_name].update(str_values)

        # Convert sets to sorted lists
        for field_name, values in enum_fields.items():
            all_values['enum_values'][field_name] = sorted(values)

        return all_values

    def generate_all_templates(self, output_dir: str):
        """Main method to generate all templates."""
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        print("=" * 60)
        print("JSON Template Generator for Game-1")
        print("=" * 60)
        print(f"\nBase path: {self.base_path}")
        print(f"Output dir: {output_path}")
        print()

        # Find all JSON files
        files_by_category = self.find_json_files()

        print("Found JSON files by category:")
        for category, files in sorted(files_by_category.items()):
            print(f"  {category}: {len(files)} files")
        print()

        # Process each category
        for category, files in files_by_category.items():
            if not files:
                continue
            print(f"Processing {category}...")
            self.process_category(category, files)

        print()
        print("Generating templates...")

        # Generate individual templates
        for category in files_by_category:
            if not self.field_registry.get(category):
                continue

            template = self.generate_template(category)

            output_file = output_path / f"template_{category.replace('-', '_')}.json"
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(template, f, indent=2, default=str)
            print(f"  Created: {output_file.name}")

        # Generate master tag list
        tag_list = self.generate_master_tag_list()
        tag_file = output_path / "master_all_values.json"
        with open(tag_file, 'w', encoding='utf-8') as f:
            json.dump(tag_list, f, indent=2)
        print(f"  Created: {tag_file.name}")

        # Generate master summary
        summary = self.generate_summary(files_by_category)
        summary_file = output_path / "TEMPLATE_SUMMARY.json"
        with open(summary_file, 'w', encoding='utf-8') as f:
            json.dump(summary, f, indent=2)
        print(f"  Created: {summary_file.name}")

        # Also create a human-readable markdown summary
        self.generate_markdown_summary(output_path, files_by_category)

        print()
        print("=" * 60)
        print(f"Done! Templates saved to: {output_path}")
        print("=" * 60)

    def generate_summary(self, files_by_category: Dict[str, List[Path]]) -> Dict:
        """Generate a summary of all templates."""
        summary = {
            '_meta': {
                'description': 'Master summary of all JSON templates',
                'generated_at': datetime.now().isoformat(),
                'base_path': str(self.base_path)
            },
            'categories': {},
            'global_stats': {
                'total_unique_tags': len(self.all_tags),
                'total_unique_material_ids': len(self.all_material_ids),
                'total_unique_skill_ids': len(self.all_skill_ids)
            }
        }

        for category, files in files_by_category.items():
            fields = self.field_registry.get(category, {})
            summary['categories'][category] = {
                'description': self.CATEGORIES.get(category, {}).get('description', ''),
                'files': [f.name for f in files],
                'total_fields': len(fields),
                'fields': list(sorted(fields.keys()))[:50]  # First 50 fields
            }

        return summary

    def generate_markdown_summary(self, output_path: Path, files_by_category: Dict[str, List[Path]]):
        """Generate a human-readable markdown summary."""
        md_lines = [
            "# JSON Template Library - Game-1",
            "",
            f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "",
            "## Overview",
            "",
            f"- **Total Categories**: {len(files_by_category)}",
            f"- **Total Unique Tags**: {len(self.all_tags)}",
            f"- **Total Material IDs**: {len(self.all_material_ids)}",
            f"- **Total Skill IDs**: {len(self.all_skill_ids)}",
            "",
            "---",
            "",
            "## Categories",
            ""
        ]

        for category, files in sorted(files_by_category.items()):
            config = self.CATEGORIES.get(category, {})
            fields = self.field_registry.get(category, {})

            md_lines.append(f"### {category}")
            md_lines.append(f"**Description**: {config.get('description', 'N/A')}")
            md_lines.append(f"**Files**: {', '.join(f.name for f in files)}")
            md_lines.append(f"**Total Fields**: {len(fields)}")
            md_lines.append("")

            # List key fields with sample values
            md_lines.append("**Key Fields**:")
            for path, field_info in sorted(fields.items())[:20]:
                if not path:
                    continue
                types_str = ', '.join(field_info.types)
                sample = list(field_info.values)[:3] if not field_info.is_array else list(field_info.array_item_values)[:3]
                sample_str = ', '.join(str(s) for s in sample)
                md_lines.append(f"- `{path}` ({types_str}): {sample_str}")

            md_lines.append("")
            md_lines.append("---")
            md_lines.append("")

        # Add all tags section
        md_lines.append("## All Tags")
        md_lines.append("")
        for tag in sorted(self.all_tags):
            md_lines.append(f"- `{tag}`")

        md_file = output_path / "TEMPLATE_LIBRARY.md"
        with open(md_file, 'w', encoding='utf-8') as f:
            f.write('\n'.join(md_lines))
        print(f"  Created: {md_file.name}")


def main():
    parser = argparse.ArgumentParser(
        description='Generate comprehensive JSON templates from Game-1 data files'
    )
    parser.add_argument(
        '--base-path',
        default=None,
        help='Base path to Game-1-modular directory'
    )
    parser.add_argument(
        '--output-dir',
        default=None,
        help='Output directory for templates'
    )

    args = parser.parse_args()

    # Determine base path
    if args.base_path:
        base_path = Path(args.base_path)
    else:
        # Try to find Game-1-modular relative to script location
        script_dir = Path(__file__).parent
        base_path = script_dir.parent  # tools/ -> Game-1-modular/
        if not (base_path / 'items.JSON').exists():
            base_path = Path.cwd()

    # Determine output directory
    if args.output_dir:
        output_dir = args.output_dir
    else:
        output_dir = base_path / 'json_templates'

    generator = JSONTemplateGenerator(base_path)
    generator.generate_all_templates(output_dir)


if __name__ == '__main__':
    main()

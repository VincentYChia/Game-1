#!/usr/bin/env python3
"""
JSON Template Generator for Game-1

This script analyzes all JSON files in the game and generates comprehensive
templates that show ALL possible values for each field across all files of
that type.

IMPORTANT: Uses the same file discovery patterns as the game's database loaders
to ensure all content is captured, including Update-N directories.

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
from typing import Any, Dict, List, Set, Union, Tuple
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
    """Generates comprehensive JSON templates from all game data files.

    Uses filename pattern matching (like the game's update_loader.py) to
    categorize files, and dynamically discovers all root keys within each file.
    """

    # File patterns that match the game's loading logic (from update_loader.py)
    # Pattern -> (category_name, description)
    FILE_PATTERNS = [
        # Items (scanned by MaterialDatabase and EquipmentDatabase)
        ('items-materials', 'items', 'Raw materials and crafting ingredients'),
        ('items-smithing', 'items', 'Weapons, armor, and shields'),
        ('items-alchemy', 'items', 'Potions, elixirs, and consumables'),
        ('items-refining', 'items', 'Processed materials (ingots, planks, alloys)'),
        ('items-engineering', 'items', 'Engineering devices and gadgets'),
        ('items-tools', 'items', 'Placeable crafting tools and stations'),
        ('items-testing', 'items-testing', 'Test items for tag validation'),

        # Recipes (scanned by RecipeDatabase)
        ('recipes-smithing', 'recipes', 'Smithing recipes'),
        ('recipes-alchemy', 'recipes', 'Alchemy recipes'),
        ('recipes-refining', 'recipes', 'Refining recipes'),
        ('recipes-engineering', 'recipes', 'Engineering recipes'),
        ('recipes-enchanting', 'recipes', 'Enchanting recipes'),
        ('recipes-adornments', 'recipes', 'Adornment recipes'),
        ('recipes-tag-tests', 'recipes-testing', 'Test recipes'),

        # Placements (scanned by PlacementDatabase)
        ('placements-', 'placements', 'Minigame grid placement patterns'),

        # Skills (scanned by SkillDatabase)
        ('skills-skills', 'skills', 'Player skill definitions'),
        ('skills-base-effects', 'skills', 'Skill base effect definitions'),
        ('skills-testing', 'skills-testing', 'Test skills'),

        # Progression (scanned by various databases)
        ('classes', 'classes', 'Starting class definitions'),
        ('titles', 'titles', 'Achievement title definitions'),
        ('npcs', 'npcs', 'NPC definitions'),
        ('quests', 'quests', 'Quest definitions'),
        ('skill-unlocks', 'skill-unlocks', 'Skill unlock requirements'),

        # Definitions (core game definitions)
        ('resource-node', 'resource-nodes', 'Gatherable resource node definitions'),
        ('hostiles', 'hostiles', 'Enemy and ability definitions'),
        ('tag-definitions', 'tag-definitions', 'Master tag system definitions'),
        ('value-translation', 'value-translations', 'Qualitative to numeric mappings'),
        ('crafting-stations', 'crafting-stations', 'Crafting station definitions'),
        ('stats-calculations', 'stats-calculations', 'Stat calculation formulas'),
        ('skills-translation', 'skills-translation', 'Skill translation tables'),
        ('combat-config', 'combat-config', 'Combat configuration'),
        ('templates-crafting', 'templates-crafting', 'Crafting templates'),
        ('chunk-templates', 'chunk-templates', 'World generation templates'),
    ]

    # Directories to scan (matching game's loading paths)
    SCAN_DIRECTORIES = [
        'items.JSON',
        'recipes.JSON',
        'placements.JSON',
        'Skills',
        'progression',
        'Definitions.JSON',
        'Crafting-subdisciplines',
        'Update-1',  # Update packages
        'Update-2',
        'Update-3',
        # Add more Update-N as needed
    ]

    # Files/directories to skip
    SKIP_PATTERNS = [
        'json_templates',  # Our own output
        'saves',           # Save files
        'assets',          # Asset configs
        'docs',            # Documentation
    ]

    def __init__(self, base_path: str):
        self.base_path = Path(base_path)
        self.templates: Dict[str, Dict] = {}
        self.field_registry: Dict[str, Dict[str, FieldInfo]] = defaultdict(lambda: defaultdict(FieldInfo))
        self.all_tags: Set[str] = set()
        self.all_effect_types: Set[str] = set()
        self.all_item_ids: Set[str] = set()
        self.all_material_ids: Set[str] = set()
        self.all_skill_ids: Set[str] = set()
        self.all_recipe_ids: Set[str] = set()
        self.discovered_root_keys: Dict[str, Set[str]] = defaultdict(set)

    def find_all_json_files(self) -> List[Path]:
        """Find ALL JSON files in the project, matching the game's discovery pattern."""
        all_files = []

        # Scan specified directories
        for dir_name in self.SCAN_DIRECTORIES:
            dir_path = self.base_path / dir_name
            if dir_path.exists() and dir_path.is_dir():
                # Both .JSON and .json extensions
                all_files.extend(dir_path.glob('*.JSON'))
                all_files.extend(dir_path.glob('*.json'))

        # Also scan root for any stray JSON files
        all_files.extend(self.base_path.glob('*.JSON'))
        all_files.extend(self.base_path.glob('*.json'))

        # Filter out skipped patterns and directories
        filtered = []
        for f in all_files:
            # Skip directories (some directories end in .JSON)
            if f.is_dir():
                continue
            skip = False
            for pattern in self.SKIP_PATTERNS:
                if pattern in str(f):
                    skip = True
                    break
            if not skip:
                filtered.append(f)

        return list(set(filtered))  # Remove duplicates

    def categorize_file(self, filepath: Path) -> Tuple[str, str]:
        """Categorize a file based on its filename pattern (like game's update_loader.py)."""
        filename_lower = filepath.name.lower()

        for pattern, category, description in self.FILE_PATTERNS:
            if pattern.lower() in filename_lower:
                return category, description

        # Default: use parent directory name as category
        parent = filepath.parent.name
        return f"other-{parent.lower()}", f"Other files from {parent}"

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
            path_lower = path.lower()
            if 'tag' in path_lower:
                self.all_tags.add(obj)
            if path.endswith('.materialId') or path.endswith('.itemId'):
                self.all_material_ids.add(obj)
            if path.endswith('.skillId'):
                self.all_skill_ids.add(obj)
            if path.endswith('.recipeId'):
                self.all_recipe_ids.add(obj)
        elif isinstance(obj, list):
            field_info.is_array = True
            field_info.types.add('array')
            for i, item in enumerate(obj):
                if isinstance(item, dict):
                    self.extract_values(item, f"{path}[]", category, source_file)
                else:
                    field_info.array_item_values.add(self._make_hashable(item))
                    if isinstance(item, str):
                        path_lower = path.lower()
                        if 'tag' in path_lower:
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

    def process_file(self, json_file: Path, category: str):
        """Process a single JSON file, extracting all array sections dynamically."""
        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            print(f"  Warning: Could not parse {json_file.name}: {e}")
            return

        if not isinstance(data, dict):
            # Handle top-level arrays
            if isinstance(data, list):
                for item in data:
                    if isinstance(item, dict):
                        self.extract_values(item, '', category, json_file.name)
            return

        # Process ALL keys in the JSON, not just predefined ones
        for key, value in data.items():
            # Track discovered root keys
            self.discovered_root_keys[category].add(key)

            # Skip metadata sections
            if key.lower() == 'metadata':
                continue

            # If value is a list of objects, process each
            if isinstance(value, list):
                for item in value:
                    if isinstance(item, dict):
                        self.extract_values(item, '', category, json_file.name)
            # If value is a dict, it might be a nested structure
            elif isinstance(value, dict):
                # Check if it's a single object or a named collection
                # If all values are lists of dicts, treat as subsections
                all_lists = all(isinstance(v, list) for v in value.values())
                if all_lists:
                    for subkey, sublist in value.items():
                        if subkey.lower() == 'metadata':
                            continue
                        for item in sublist:
                            if isinstance(item, dict):
                                self.extract_values(item, '', category, json_file.name)
                else:
                    # Single object or mixed - extract as-is
                    self.extract_values(value, key, category, json_file.name)

    def generate_template(self, category: str, description: str) -> Dict:
        """Generate a comprehensive template for a category."""
        template = {
            '_meta': {
                'category': category,
                'description': description,
                'generated_at': datetime.now().isoformat(),
                'source_files': [],
                'discovered_root_keys': [],
                'total_items_analyzed': 0
            },
            '_field_documentation': {},
            '_all_possible_values': {},
            '_usable_template': {},
            'template': {}
        }

        fields = self.field_registry.get(category, {})

        # Collect source files
        all_sources = set()
        for field_info in fields.values():
            all_sources.update(field_info.source_files)
        template['_meta']['source_files'] = sorted(all_sources)
        template['_meta']['discovered_root_keys'] = sorted(self.discovered_root_keys.get(category, set()))

        # Build template structure
        for path, field_info in sorted(fields.items()):
            if not path:
                continue

            if field_info.is_array and field_info.array_item_values:
                values = sorted([v for v in field_info.array_item_values if v is not None],
                              key=lambda x: str(x))
            else:
                values = sorted([v for v in field_info.values if v is not None and not isinstance(v, (dict, list))],
                              key=lambda x: str(x))

            if values:
                template['_all_possible_values'][path] = {
                    'values': values[:100],
                    'count': len(values),
                    'types': list(field_info.types),
                    'occurrences': field_info.occurrences
                }

            self._set_nested_value(template['template'], path, field_info)

        template['_usable_template'] = self._build_usable_template(category, fields)

        return template

    def _build_usable_template(self, category: str, fields: Dict[str, FieldInfo]) -> Dict:
        """Build a clean, copy-paste ready template with placeholder comments."""
        usable = {}

        for path, field_info in sorted(fields.items()):
            if not path or '[]' in path:
                continue

            parts = path.split('.')
            current = usable

            # Navigate to the correct nested location
            valid_path = True
            for i, part in enumerate(parts[:-1]):
                if part not in current:
                    current[part] = {}
                elif not isinstance(current[part], dict):
                    # Path conflict - skip this field
                    valid_path = False
                    break
                current = current[part]

            if not valid_path:
                continue

            # Make sure current is a dict before assigning
            if not isinstance(current, dict):
                continue

            final_key = parts[-1] if parts else 'value'

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

    def generate_master_values(self) -> Dict:
        """Generate a comprehensive list of all values found."""
        all_values = {
            '_meta': {
                'description': 'Master reference of all values found across all JSON files',
                'generated_at': datetime.now().isoformat(),
                'total_unique_tags': len(self.all_tags),
                'total_unique_material_ids': len(self.all_material_ids),
                'total_unique_skill_ids': len(self.all_skill_ids),
                'total_unique_recipe_ids': len(self.all_recipe_ids)
            },
            'all_tags': sorted(self.all_tags),
            'all_material_ids': sorted(self.all_material_ids),
            'all_skill_ids': sorted(self.all_skill_ids),
            'all_recipe_ids': sorted(self.all_recipe_ids),
            'enum_values': {}
        }

        # Collect enum-like values
        enum_fields = {}
        for category, fields in self.field_registry.items():
            for path, field_info in fields.items():
                if 'string' in field_info.types:
                    str_values = [v for v in field_info.values if isinstance(v, str)]
                    if 2 <= len(str_values) <= 50:  # Increased limit
                        field_name = path.split('.')[-1] if path else 'unknown'
                        if field_name not in enum_fields:
                            enum_fields[field_name] = set()
                        enum_fields[field_name].update(str_values)

        for field_name, values in sorted(enum_fields.items()):
            all_values['enum_values'][field_name] = sorted(values)

        return all_values

    def generate_all_templates(self, output_dir: str):
        """Main method to generate all templates."""
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        print("=" * 70)
        print("JSON Template Generator for Game-1")
        print("(Using game's file discovery patterns)")
        print("=" * 70)
        print(f"\nBase path: {self.base_path}")
        print(f"Output dir: {output_path}")
        print()

        # Find ALL JSON files
        all_files = self.find_all_json_files()
        print(f"Found {len(all_files)} JSON files total")
        print()

        # Categorize and process files
        files_by_category: Dict[str, Tuple[List[Path], str]] = defaultdict(lambda: ([], ''))

        for json_file in all_files:
            category, description = self.categorize_file(json_file)
            if category not in files_by_category:
                files_by_category[category] = ([], description)
            files_by_category[category][0].append(json_file)

        # Show what we found
        print("Files by category:")
        for category, (files, desc) in sorted(files_by_category.items()):
            print(f"  {category}: {len(files)} files")
            for f in files:
                print(f"    - {f.parent.name}/{f.name}")
        print()

        # Process each category
        for category, (files, description) in files_by_category.items():
            if not files:
                continue
            print(f"Processing {category}...")
            for json_file in files:
                self.process_file(json_file, category)

        print()
        print("Generating templates...")

        # Generate individual templates
        for category, (files, description) in files_by_category.items():
            if not self.field_registry.get(category):
                continue

            template = self.generate_template(category, description)

            output_file = output_path / f"template_{category.replace('-', '_')}.json"
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(template, f, indent=2, default=str)
            print(f"  Created: {output_file.name}")

        # Generate master values list
        master_values = self.generate_master_values()
        master_file = output_path / "master_all_values.json"
        with open(master_file, 'w', encoding='utf-8') as f:
            json.dump(master_values, f, indent=2)
        print(f"  Created: {master_file.name}")

        # Generate summary
        summary = self.generate_summary(files_by_category)
        summary_file = output_path / "TEMPLATE_SUMMARY.json"
        with open(summary_file, 'w', encoding='utf-8') as f:
            json.dump(summary, f, indent=2)
        print(f"  Created: {summary_file.name}")

        # Generate markdown summary
        self.generate_markdown_summary(output_path, files_by_category)

        print()
        print("=" * 70)
        print(f"Done! Templates saved to: {output_path}")
        print(f"Total unique tags found: {len(self.all_tags)}")
        print(f"Total unique material IDs: {len(self.all_material_ids)}")
        print(f"Total unique skill IDs: {len(self.all_skill_ids)}")
        print("=" * 70)

    def generate_summary(self, files_by_category: Dict) -> Dict:
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
                'total_unique_skill_ids': len(self.all_skill_ids),
                'total_unique_recipe_ids': len(self.all_recipe_ids)
            },
            'discovered_root_keys_by_category': {
                cat: sorted(keys) for cat, keys in self.discovered_root_keys.items()
            }
        }

        for category, (files, description) in files_by_category.items():
            fields = self.field_registry.get(category, {})
            summary['categories'][category] = {
                'description': description,
                'files': [f.name for f in files],
                'total_fields': len(fields),
                'fields': list(sorted(fields.keys()))[:50]
            }

        return summary

    def generate_markdown_summary(self, output_path: Path, files_by_category: Dict):
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
            f"- **Total Recipe IDs**: {len(self.all_recipe_ids)}",
            "",
            "---",
            "",
            "## Categories",
            ""
        ]

        for category, (files, description) in sorted(files_by_category.items()):
            fields = self.field_registry.get(category, {})

            md_lines.append(f"### {category}")
            md_lines.append(f"**Description**: {description}")
            md_lines.append(f"**Files**: {', '.join(f.name for f in files)}")
            md_lines.append(f"**Total Fields**: {len(fields)}")
            md_lines.append(f"**Root Keys Found**: {', '.join(sorted(self.discovered_root_keys.get(category, set())))}")
            md_lines.append("")

            md_lines.append("**Key Fields**:")
            for path, field_info in sorted(fields.items())[:20]:
                if not path:
                    continue
                types_str = ', '.join(field_info.types)
                sample = list(field_info.values)[:3] if not field_info.is_array else list(field_info.array_item_values)[:3]
                sample_str = ', '.join(str(s)[:50] for s in sample)
                md_lines.append(f"- `{path}` ({types_str}): {sample_str}")

            md_lines.append("")
            md_lines.append("---")
            md_lines.append("")

        # Add all tags section
        md_lines.append("## All Tags (Sorted)")
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
        script_dir = Path(__file__).parent
        base_path = script_dir.parent
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

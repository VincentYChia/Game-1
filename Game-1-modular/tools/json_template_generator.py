#!/usr/bin/env python3
"""
JSON Template Generator for Game-1 - LLM Model Training Edition

Organizes game JSON data into categories matching the planned LLM architecture:

CRAFTING LLMs (2 per discipline × 5 disciplines = 10 model types):
  - {discipline}_recipes: Recipe definitions for that discipline
  - {discipline}_items: Items produced by that discipline

OTHER LLMs:
  - hostiles: Enemy mobs and abilities (combined for now)
  - skills: Player skill definitions
  - titles: Achievement title definitions
  - chunk_types: World generation chunk templates
  - node_types: Resource node definitions
  - npcs: NPC definitions
  - quests: Quest definitions
  - classifier_requirements: Compiled skill/title unlock requirements

Usage:
    python json_template_generator.py [--output-dir OUTPUT_DIR]
"""

import json
import os
import argparse
from pathlib import Path
from collections import defaultdict
from typing import Any, Dict, List, Set, Tuple, Optional
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class FieldInfo:
    """Tracks all values seen for a field across multiple items."""
    values: Set[Any] = field(default_factory=set)
    types: Set[str] = field(default_factory=set)
    is_array: bool = False
    array_item_values: Set[Any] = field(default_factory=set)
    occurrences: int = 0
    example_items: List[str] = field(default_factory=list)


class JSONTemplateGenerator:
    """Generates comprehensive JSON templates organized by LLM model type."""

    # Crafting disciplines
    DISCIPLINES = ['smithing', 'alchemy', 'refining', 'engineering', 'enchanting']

    # Files to completely skip (metadata/config only, not game content)
    SKIP_FILES = [
        'tag-definitions',
        'value-translation',
        'stats-calculations',
        'skills-translation',
        'rarity-modifiers',
        'templates-crafting',
        'combat-config',
        'updates_manifest',
    ]

    # Directories to scan
    SCAN_DIRECTORIES = [
        'items.JSON',
        'recipes.JSON',
        'placements.JSON',
        'Skills',
        'progression',
        'Definitions.JSON',
        'Crafting-subdisciplines',
        'Update-1',
        'Update-2',
        'Update-3',
    ]

    SKIP_PATTERNS = [
        'json_templates',
        'saves',
        'assets',
        'docs',
    ]

    def __init__(self, base_path: str):
        self.base_path = Path(base_path)
        self.items_by_category: Dict[str, List[Dict]] = defaultdict(list)
        self.field_registry: Dict[str, Dict[str, FieldInfo]] = defaultdict(lambda: defaultdict(FieldInfo))
        self.source_files_by_category: Dict[str, Set[str]] = defaultdict(set)
        self.all_tags: Set[str] = set()
        self.classifier_requirements: List[Dict] = []
        self.unclassified_items: List[Tuple[str, Dict]] = []

    def find_all_json_files(self) -> List[Path]:
        """Find all JSON files to process."""
        all_files = []

        for dir_name in self.SCAN_DIRECTORIES:
            dir_path = self.base_path / dir_name
            if dir_path.exists() and dir_path.is_dir():
                all_files.extend(dir_path.glob('*.JSON'))
                all_files.extend(dir_path.glob('*.json'))

        all_files.extend(self.base_path.glob('*.JSON'))
        all_files.extend(self.base_path.glob('*.json'))

        filtered = []
        for f in all_files:
            if f.is_dir():
                continue
            skip = False
            filename_lower = f.name.lower()
            for skip_file in self.SKIP_FILES:
                if skip_file in filename_lower:
                    skip = True
                    break
            for pattern in self.SKIP_PATTERNS:
                if pattern in str(f):
                    skip = True
                    break
            if not skip:
                filtered.append(f)

        return list(set(filtered))

    def classify_item(self, item: Dict, source_file: str) -> Optional[str]:
        """Classify an item into an LLM model category."""
        if not isinstance(item, dict):
            return None

        # === RECIPES (by discipline) ===
        if 'recipeId' in item:
            station_type = item.get('stationType', '').lower()
            if station_type in self.DISCIPLINES:
                return f"{station_type}_recipes"
            # Infer from recipeId prefix
            recipe_id = item.get('recipeId', '').lower()
            for disc in self.DISCIPLINES:
                if recipe_id.startswith(disc) or recipe_id.startswith(f"recipe_{disc}"):
                    return f"{disc}_recipes"
            # Check filename for discipline
            filename_lower = source_file.lower()
            for disc in self.DISCIPLINES:
                if disc in filename_lower:
                    return f"{disc}_recipes"
            # Default to smithing for unknown recipes
            return "smithing_recipes"

        # === PLACEMENTS (go with recipes for their discipline) ===
        if 'placementMap' in item or 'coreInputs' in item:
            # Placements support recipe creation, classify by discipline
            recipe_id = item.get('recipeId', '').lower()
            for disc in self.DISCIPLINES:
                if disc in recipe_id:
                    return f"{disc}_recipes"
            filename_lower = source_file.lower()
            for disc in self.DISCIPLINES:
                if disc in filename_lower:
                    return f"{disc}_recipes"
            return "smithing_recipes"

        # === SKILL UNLOCKS (check before skills since unlocks have skillId too) ===
        if 'unlockId' in item:
            # Extract requirements for classifier
            self._extract_unlock_requirements(item, 'skill')
            return "classifier_requirements"

        # === SKILLS ===
        if 'skillId' in item:
            return "skills"

        # === TITLES ===
        if 'titleId' in item:
            # Also extract requirements for classifier
            self._extract_title_requirements(item)
            return "titles"

        # === HOSTILES (enemies + abilities) ===
        if 'enemyId' in item or 'abilityId' in item:
            return "hostiles"

        # === QUESTS (check before NPCs since quests have npc_id too) ===
        if 'quest_id' in item:
            return "quests"

        # === NPCs ===
        if 'npc_id' in item:
            return "npcs"

        # === RESOURCE NODES ===
        if 'resourceId' in item:
            return "node_types"

        # === CHUNK TYPES ===
        if 'chunkType' in item:
            return "chunk_types"

        # === CLASSES (include with skills for now) ===
        if 'classId' in item:
            return "skills"

        # === CRAFTING STATIONS (smithing items) ===
        if item.get('category') == 'station':
            return "smithing_items"

        # === ITEMS (by what discipline produces them) ===
        item_type = item.get('type', '').lower()
        item_category = item.get('category', '').lower()

        # Smithing items: weapons, armor, shields, tools, accessories
        if item_type in ['weapon', 'armor', 'shield', 'accessory', 'tool']:
            return "smithing_items"
        if item_type in ['sword', 'mace', 'bow', 'staff', 'spear', 'dagger', 'axe',
                         'shortsword', 'longsword', 'greatsword', 'hammer', 'wand']:
            return "smithing_items"
        if item_category in ['weapon', 'armor', 'equipment']:
            return "smithing_items"

        # Alchemy items: potions, consumables, elixirs
        if item_category == 'consumable' or item_type == 'potion':
            return "alchemy_items"

        # Refining items: materials with itemId (crafted materials)
        if item_category == 'material' and 'itemId' in item:
            return "refining_items"

        # Raw materials: have materialId (gathered, not crafted)
        if 'materialId' in item:
            return "refining_items"  # Include raw materials for reference

        # Engineering items: devices, turrets, traps, bombs
        if item_category == 'device' or item_type in ['turret', 'trap', 'bomb']:
            return "engineering_items"

        # Enchanting items: check for enchantment-related fields
        if 'enchantmentId' in item or item_type == 'enchantment':
            return "enchanting_items"

        return None

    def _extract_unlock_requirements(self, item: Dict, unlock_type: str):
        """Extract requirements from skill unlock definitions."""
        requirements = {
            'type': unlock_type,
            'id': item.get('skillId', item.get('unlockId', 'unknown')),
            'unlockMethod': item.get('unlockMethod', 'unknown'),
            'conditions': item.get('conditions', {}),
            'cost': item.get('cost', {})
        }
        self.classifier_requirements.append(requirements)

    def _extract_title_requirements(self, item: Dict):
        """Extract requirements from title definitions."""
        requirements = {
            'type': 'title',
            'id': item.get('titleId', 'unknown'),
            'titleType': item.get('titleType', 'unknown'),
            'difficultyTier': item.get('difficultyTier', 'unknown'),
            'prerequisites': item.get('prerequisites', {}),
            'acquisitionMethod': item.get('acquisitionMethod', 'unknown')
        }
        self.classifier_requirements.append(requirements)

    def extract_items_from_json(self, data: Any, source_file: str) -> List[Tuple[str, Dict]]:
        """Extract individual items from a JSON structure."""
        items = []

        if isinstance(data, list):
            for item in data:
                if isinstance(item, dict):
                    category = self.classify_item(item, source_file)
                    if category:
                        items.append((category, item))
                    else:
                        self.unclassified_items.append((source_file, item))

        elif isinstance(data, dict):
            category = self.classify_item(data, source_file)
            if category:
                items.append((category, data))
            else:
                for key, value in data.items():
                    if key.lower() == 'metadata':
                        continue

                    if isinstance(value, list):
                        for item in value:
                            if isinstance(item, dict):
                                cat = self.classify_item(item, source_file)
                                if cat:
                                    items.append((cat, item))
                                else:
                                    self.unclassified_items.append((source_file, item))

                    elif isinstance(value, dict):
                        cat = self.classify_item(value, source_file)
                        if cat:
                            items.append((cat, value))
                        else:
                            for subkey, subvalue in value.items():
                                if subkey.lower() == 'metadata':
                                    continue
                                if isinstance(subvalue, list):
                                    for item in subvalue:
                                        if isinstance(item, dict):
                                            cat2 = self.classify_item(item, source_file)
                                            if cat2:
                                                items.append((cat2, item))

        return items

    def extract_field_values(self, item: Dict, category: str, source_file: str, prefix: str = ""):
        """Recursively extract all field values from an item."""
        for key, value in item.items():
            path = f"{prefix}.{key}" if prefix else key
            field_info = self.field_registry[category][path]
            field_info.occurrences += 1

            if len(field_info.example_items) < 3:
                item_id = (item.get('itemId') or item.get('materialId') or
                          item.get('recipeId') or item.get('skillId') or
                          item.get('enemyId') or item.get('quest_id') or
                          item.get('npc_id') or item.get('classId') or
                          item.get('titleId') or item.get('abilityId') or
                          item.get('name') or 'unknown')
                if item_id not in field_info.example_items:
                    field_info.example_items.append(str(item_id))

            if value is None:
                field_info.values.add(None)
                field_info.types.add('null')
            elif isinstance(value, bool):
                field_info.values.add(value)
                field_info.types.add('boolean')
            elif isinstance(value, int):
                field_info.values.add(value)
                field_info.types.add('integer')
            elif isinstance(value, float):
                field_info.values.add(value)
                field_info.types.add('number')
            elif isinstance(value, str):
                field_info.values.add(value)
                field_info.types.add('string')
                if 'tag' in path.lower():
                    self.all_tags.add(value)
            elif isinstance(value, list):
                field_info.is_array = True
                field_info.types.add('array')
                for item_val in value:
                    if isinstance(item_val, dict):
                        self.extract_field_values(item_val, category, source_file, f"{path}[]")
                    else:
                        field_info.array_item_values.add(self._make_hashable(item_val))
                        if isinstance(item_val, str) and 'tag' in path.lower():
                            self.all_tags.add(item_val)
            elif isinstance(value, dict):
                field_info.types.add('object')
                self.extract_field_values(value, category, source_file, path)

    def _make_hashable(self, obj: Any) -> Any:
        """Convert an object to a hashable type."""
        if isinstance(obj, dict):
            return tuple(sorted((k, self._make_hashable(v)) for k, v in obj.items()))
        elif isinstance(obj, list):
            return tuple(self._make_hashable(item) for item in obj)
        return obj

    def process_file(self, json_file: Path):
        """Process a single JSON file."""
        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            print(f"  Warning: Could not parse {json_file.name}: {e}")
            return

        source_name = f"{json_file.parent.name}/{json_file.name}"
        items = self.extract_items_from_json(data, source_name)

        for category, item in items:
            self.items_by_category[category].append(item)
            self.source_files_by_category[category].add(source_name)
            self.extract_field_values(item, category, source_name)

    def generate_category_template(self, category: str) -> Dict:
        """Generate a comprehensive template for a category."""
        items = self.items_by_category.get(category, [])
        fields = self.field_registry.get(category, {})

        # Determine LLM purpose
        purpose = self._get_category_purpose(category)

        template = {
            "_meta": {
                "category": category,
                "llm_purpose": purpose,
                "generated_at": datetime.now().isoformat(),
                "total_items": len(items),
                "source_files": sorted(self.source_files_by_category.get(category, set())),
            },
            "_all_possible_values": {},
            "_usable_template": {},
            "_sample_items": items[:5] if len(items) > 5 else items,
        }

        # Build field documentation
        for path, field_info in sorted(fields.items()):
            if not path:
                continue

            if field_info.is_array and field_info.array_item_values:
                values = sorted([v for v in field_info.array_item_values if v is not None],
                              key=lambda x: str(x))
            else:
                values = sorted([v for v in field_info.values
                               if v is not None and not isinstance(v, (dict, list))],
                              key=lambda x: str(x))

            if values:
                display_values = values[:100] if len(values) > 100 else values
                template["_all_possible_values"][path] = {
                    "values": display_values,
                    "total_unique": len(values),
                    "types": list(field_info.types),
                    "occurrences": field_info.occurrences,
                }

        template["_usable_template"] = self._build_usable_template(fields)

        return template

    def _get_category_purpose(self, category: str) -> str:
        """Get the LLM purpose description for a category."""
        purposes = {
            # Crafting disciplines
            'smithing_recipes': 'Recipe LLM for smithing - creates weapon/armor/tool crafting recipes',
            'smithing_items': 'Item LLM for smithing - creates weapons, armor, shields, tools with tags',
            'alchemy_recipes': 'Recipe LLM for alchemy - creates potion/consumable crafting recipes',
            'alchemy_items': 'Item LLM for alchemy - creates potions, elixirs, consumables with effects',
            'refining_recipes': 'Recipe LLM for refining - creates material processing recipes',
            'refining_items': 'Item LLM for refining - creates ingots, planks, alloys, processed materials',
            'engineering_recipes': 'Recipe LLM for engineering - creates device/gadget crafting recipes',
            'engineering_items': 'Item LLM for engineering - creates turrets, traps, bombs, devices',
            'enchanting_recipes': 'Recipe LLM for enchanting - creates enchantment/adornment recipes',
            'enchanting_items': 'Item LLM for enchanting - creates enchanted items and adornments',
            # Other models
            'hostiles': 'Hostile LLM - creates enemy mobs with stats, behavior, abilities, and drops',
            'skills': 'Skills LLM - creates player skills with effects, costs, and evolution paths',
            'titles': 'Titles LLM - creates achievement titles with prerequisites and bonuses',
            'chunk_types': 'Chunk Types LLM - creates world generation chunk templates',
            'node_types': 'Node Types LLM - creates gatherable resource node definitions',
            'npcs': 'NPC LLM - creates NPC definitions with dialogue and quest associations',
            'quests': 'Quest LLM - creates quest definitions with objectives and rewards',
            'classifier_requirements': 'Classifier LLM - determines when to trigger skill/title generation',
        }
        return purposes.get(category, f'Unknown LLM purpose for {category}')

    def _build_usable_template(self, fields: Dict[str, FieldInfo]) -> Dict:
        """Build a clean, copy-paste ready template."""
        usable = {}

        for path, field_info in sorted(fields.items()):
            if not path or '[]' in path:
                continue

            parts = path.split('.')
            current = usable

            valid_path = True
            for part in parts[:-1]:
                if part not in current:
                    current[part] = {}
                elif not isinstance(current[part], dict):
                    valid_path = False
                    break
                current = current[part]

            if not valid_path or not isinstance(current, dict):
                continue

            final_key = parts[-1] if parts else 'value'

            if field_info.is_array:
                sample = list(field_info.array_item_values)[:3]
                current[final_key] = sample if sample else ["<value>"]
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

    def generate_classifier_template(self) -> Dict:
        """Generate the classifier requirements template."""
        # Organize requirements by type
        skill_requirements = [r for r in self.classifier_requirements if r['type'] == 'skill']
        title_requirements = [r for r in self.classifier_requirements if r['type'] == 'title']

        return {
            "_meta": {
                "category": "classifier_requirements",
                "llm_purpose": "Classifier LLM - determines when to trigger new skill/title generation",
                "generated_at": datetime.now().isoformat(),
                "total_skill_unlocks": len(skill_requirements),
                "total_title_requirements": len(title_requirements),
            },
            "skill_unlock_requirements": skill_requirements,
            "title_requirements": title_requirements,
            "_summary": {
                "unlock_methods": list(set(str(r.get('unlockMethod', 'unknown')) for r in skill_requirements)),
                "title_types": list(set(str(r.get('titleType', 'unknown')) for r in title_requirements)),
                "difficulty_tiers": list(set(str(r.get('difficultyTier', 'unknown')) for r in title_requirements)),
                "acquisition_methods": list(set(str(r.get('acquisitionMethod', 'unknown')) for r in title_requirements)),
            }
        }

    def generate_master_reference(self) -> Dict:
        """Generate a master reference of all values."""
        return {
            "_meta": {
                "description": "Master reference for LLM fine-tuning",
                "generated_at": datetime.now().isoformat(),
                "total_categories": len(self.items_by_category),
                "total_items": sum(len(items) for items in self.items_by_category.values()),
                "total_unique_tags": len(self.all_tags),
            },
            "all_tags": sorted(self.all_tags),
            "categories_summary": {
                cat: {
                    "count": len(items),
                    "llm_purpose": self._get_category_purpose(cat),
                    "sources": sorted(self.source_files_by_category.get(cat, set()))
                }
                for cat, items in sorted(self.items_by_category.items())
            }
        }

    def generate_all_templates(self, output_dir: str):
        """Main method to generate all templates."""
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        print("=" * 70)
        print("JSON Template Generator - LLM Model Training Edition")
        print("=" * 70)
        print(f"\nBase path: {self.base_path}")
        print(f"Output dir: {output_path}")
        print()

        # Find and process all JSON files
        all_files = self.find_all_json_files()
        print(f"Found {len(all_files)} JSON files to process")
        print()

        for json_file in all_files:
            print(f"  Processing: {json_file.parent.name}/{json_file.name}")
            self.process_file(json_file)

        print()
        print("=" * 70)
        print("LLM Model Categories:")
        print("=" * 70)

        # Show what was classified
        print("\nCRAFTING LLMs:")
        for disc in self.DISCIPLINES:
            recipe_cat = f"{disc}_recipes"
            item_cat = f"{disc}_items"
            recipe_count = len(self.items_by_category.get(recipe_cat, []))
            item_count = len(self.items_by_category.get(item_cat, []))
            print(f"  {disc.upper()}: {recipe_count} recipes, {item_count} items")

        print("\nOTHER LLMs:")
        other_cats = ['hostiles', 'skills', 'titles', 'chunk_types', 'node_types', 'npcs', 'quests']
        for cat in other_cats:
            count = len(self.items_by_category.get(cat, []))
            print(f"  {cat}: {count} items")

        print(f"\nCLASSIFIER: {len(self.classifier_requirements)} requirements")

        if self.unclassified_items:
            print(f"\nUnclassified: {len(self.unclassified_items)} items")
            for source, item in self.unclassified_items[:5]:
                keys = list(item.keys())[:5]
                print(f"    - {source}: keys={keys}")

        print()
        print("Generating templates...")

        # Generate individual category templates
        for category in sorted(self.items_by_category.keys()):
            if category == 'classifier_requirements':
                continue  # Handle separately
            if not self.items_by_category[category]:
                continue

            template = self.generate_category_template(category)
            output_file = output_path / f"{category}.json"
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(template, f, indent=2, default=str)
            print(f"  Created: {output_file.name} ({len(self.items_by_category[category])} items)")

        # Generate classifier requirements
        classifier_template = self.generate_classifier_template()
        classifier_file = output_path / "classifier_requirements.json"
        with open(classifier_file, 'w', encoding='utf-8') as f:
            json.dump(classifier_template, f, indent=2, default=str)
        print(f"  Created: {classifier_file.name} ({len(self.classifier_requirements)} requirements)")

        # Generate master reference
        master = self.generate_master_reference()
        master_file = output_path / "MASTER_REFERENCE.json"
        with open(master_file, 'w', encoding='utf-8') as f:
            json.dump(master, f, indent=2)
        print(f"  Created: {master_file.name}")

        # Generate markdown summary
        self.generate_markdown_summary(output_path)

        print()
        print("=" * 70)
        print(f"Done! Templates saved to: {output_path}")
        print(f"Total LLM categories: {len(self.items_by_category)}")
        print(f"Total items classified: {sum(len(items) for items in self.items_by_category.values())}")
        print(f"Total unique tags: {len(self.all_tags)}")
        print("=" * 70)

    def generate_markdown_summary(self, output_path: Path):
        """Generate a human-readable markdown summary."""
        md_lines = [
            "# JSON Template Library - LLM Model Training",
            "",
            f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "",
            "## LLM Architecture Overview",
            "",
            "### Crafting LLMs (2 per discipline × 5 disciplines)",
            "",
            "| Discipline | Recipe LLM | Item LLM |",
            "|------------|------------|----------|",
        ]

        for disc in self.DISCIPLINES:
            recipe_count = len(self.items_by_category.get(f"{disc}_recipes", []))
            item_count = len(self.items_by_category.get(f"{disc}_items", []))
            md_lines.append(f"| {disc.capitalize()} | {recipe_count} recipes | {item_count} items |")

        md_lines.extend([
            "",
            "### Other LLMs",
            "",
            "| Model | Items | Purpose |",
            "|-------|-------|---------|",
        ])

        other_cats = [
            ('hostiles', 'Enemy mobs and abilities'),
            ('skills', 'Player skill definitions'),
            ('titles', 'Achievement titles'),
            ('chunk_types', 'World generation chunks'),
            ('node_types', 'Resource nodes'),
            ('npcs', 'NPC definitions'),
            ('quests', 'Quest definitions'),
        ]

        for cat, purpose in other_cats:
            count = len(self.items_by_category.get(cat, []))
            md_lines.append(f"| {cat} | {count} | {purpose} |")

        md_lines.extend([
            "",
            f"### Classifier LLM: {len(self.classifier_requirements)} requirements",
            "",
            "---",
            "",
            "## All Tags",
            "",
            f"Total unique tags: {len(self.all_tags)}",
            "",
        ])

        for tag in sorted(self.all_tags):
            md_lines.append(f"- `{tag}`")

        md_file = output_path / "TEMPLATE_LIBRARY.md"
        with open(md_file, 'w', encoding='utf-8') as f:
            f.write('\n'.join(md_lines))
        print(f"  Created: {md_file.name}")


def main():
    parser = argparse.ArgumentParser(
        description='Generate JSON templates organized by LLM model type'
    )
    parser.add_argument('--base-path', default=None, help='Base path to Game-1-modular directory')
    parser.add_argument('--output-dir', default=None, help='Output directory for templates')

    args = parser.parse_args()

    if args.base_path:
        base_path = Path(args.base_path)
    else:
        script_dir = Path(__file__).parent
        base_path = script_dir.parent
        if not (base_path / 'items.JSON').exists():
            base_path = Path.cwd()

    if args.output_dir:
        output_dir = args.output_dir
    else:
        output_dir = base_path / 'json_templates'

    generator = JSONTemplateGenerator(base_path)
    generator.generate_all_templates(output_dir)


if __name__ == '__main__':
    main()

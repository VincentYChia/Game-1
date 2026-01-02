#!/usr/bin/env python3
"""
JSON Template Generator for Game-1 - LLM Fine-Tuning Edition

This script analyzes all JSON files in the game and generates comprehensive
templates organized by CONTENT TYPE (not file source) for LLM fine-tuning.

Key Features:
- Classifies items by their fields, not their source file
- Handles mixed/update JSONs by sorting individual items
- Merges related content (e.g., all weapons go to "equipment")
- Excludes metadata-only files

LLM Categories:
- equipment: Weapons, armor, shields, accessories
- materials: Raw and processed materials
- consumables: Potions, elixirs, food
- devices: Turrets, traps, bombs
- stations: Placeable crafting tools
- recipes_smithing, recipes_alchemy, etc.: Recipes by discipline
- skills: Player skills
- enemies: Enemy definitions
- abilities: Enemy abilities
- npcs: NPC definitions
- quests: Quest definitions
- classes: Starting classes
- titles: Achievement titles
- resource_nodes: Gatherable resources

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


@dataclass
class ContentCategory:
    """Definition of a content category for LLM fine-tuning."""
    name: str
    description: str
    identifying_fields: Dict[str, Any]  # Fields that identify this category
    priority: int = 0  # Higher priority = checked first


class JSONTemplateGenerator:
    """Generates comprehensive JSON templates organized by content type."""

    # Content categories for LLM fine-tuning
    # Order matters - more specific categories should come first
    CONTENT_CATEGORIES = [
        # Equipment subtypes (check before generic equipment)
        # Check both type: "weapon" AND category: "weapon" for different JSON formats
        ContentCategory(
            name="equipment_weapons",
            description="Weapons (swords, axes, spears, bows, staffs) - smithing output",
            identifying_fields={"type": "weapon"},
            priority=100
        ),
        ContentCategory(
            name="equipment_weapons",
            description="Weapons (swords, axes, spears, bows, staffs) - smithing output",
            identifying_fields={"category": "weapon"},
            priority=100
        ),
        ContentCategory(
            name="equipment_armor",
            description="Armor pieces (helmets, chestplates, leggings, boots) - smithing output",
            identifying_fields={"type": "armor"},
            priority=100
        ),
        ContentCategory(
            name="equipment_armor",
            description="Armor pieces (helmets, chestplates, leggings, boots) - smithing output",
            identifying_fields={"category": "armor"},
            priority=100
        ),
        ContentCategory(
            name="equipment_shields",
            description="Shields and off-hand defensive items - smithing output",
            identifying_fields={"type": "shield"},
            priority=100
        ),
        ContentCategory(
            name="equipment_accessories",
            description="Accessories (rings, amulets, belts) - smithing/enchanting output",
            identifying_fields={"type": "accessory"},
            priority=100
        ),
        # Tools (pickaxes, axes) - have type: "tool"
        ContentCategory(
            name="equipment_tools",
            description="Gathering tools (pickaxes, axes) - smithing output",
            identifying_fields={"type": "tool"},
            priority=99
        ),
        # Catch-all for other weapon subtypes (mace, sword, bow, staff, etc.)
        ContentCategory(
            name="equipment_weapons",
            description="Weapons (swords, axes, spears, bows, staffs) - smithing output",
            identifying_fields={"type": "sword"},
            priority=98
        ),
        ContentCategory(
            name="equipment_weapons",
            description="Weapons (swords, axes, spears, bows, staffs) - smithing output",
            identifying_fields={"type": "mace"},
            priority=98
        ),
        ContentCategory(
            name="equipment_weapons",
            description="Weapons (swords, axes, spears, bows, staffs) - smithing output",
            identifying_fields={"type": "bow"},
            priority=98
        ),
        ContentCategory(
            name="equipment_weapons",
            description="Weapons (swords, axes, spears, bows, staffs) - smithing output",
            identifying_fields={"type": "staff"},
            priority=98
        ),
        ContentCategory(
            name="equipment_weapons",
            description="Weapons (swords, axes, spears, bows, staffs) - smithing output",
            identifying_fields={"type": "spear"},
            priority=98
        ),
        ContentCategory(
            name="equipment_weapons",
            description="Weapons (swords, axes, spears, bows, staffs) - smithing output",
            identifying_fields={"type": "dagger"},
            priority=98
        ),
        ContentCategory(
            name="equipment_weapons",
            description="Weapons (swords, axes, spears, bows, staffs) - smithing output",
            identifying_fields={"type": "axe"},
            priority=98
        ),

        # Consumables
        ContentCategory(
            name="consumables",
            description="Potions, elixirs, food, and other consumable items - alchemy output",
            identifying_fields={"category": "consumable"},
            priority=90
        ),

        # Devices (engineering)
        ContentCategory(
            name="devices_turrets",
            description="Automated turret defenses - engineering output",
            identifying_fields={"type": "turret"},
            priority=85
        ),
        ContentCategory(
            name="devices_traps",
            description="Trap devices - engineering output",
            identifying_fields={"type": "trap"},
            priority=85
        ),
        ContentCategory(
            name="devices_bombs",
            description="Explosive devices - engineering output",
            identifying_fields={"type": "bomb"},
            priority=85
        ),
        ContentCategory(
            name="devices",
            description="Engineering devices (turrets, traps, bombs)",
            identifying_fields={"category": "device"},
            priority=80
        ),

        # Stations (placeable crafting stations)
        ContentCategory(
            name="stations",
            description="Placeable crafting stations and tools",
            identifying_fields={"category": "station"},
            priority=75
        ),

        # Refined/crafted materials (have itemId and category: "material")
        ContentCategory(
            name="materials_refined",
            description="Refined crafting materials (ingots, planks, alloys) - refining output",
            identifying_fields={"category": "material"},
            priority=72
        ),

        # Raw materials (have materialId field)
        ContentCategory(
            name="materials_raw",
            description="Raw crafting materials (ores, logs, crystals) - gathered resources",
            identifying_fields={"_has_field": "materialId"},
            priority=70
        ),

        # Recipes by discipline
        ContentCategory(
            name="recipes_smithing",
            description="Smithing recipes for weapons, armor, and tools",
            identifying_fields={"stationType": "smithing"},
            priority=60
        ),
        ContentCategory(
            name="recipes_alchemy",
            description="Alchemy recipes for potions and consumables",
            identifying_fields={"stationType": "alchemy"},
            priority=60
        ),
        ContentCategory(
            name="recipes_refining",
            description="Refining recipes for processing raw materials",
            identifying_fields={"stationType": "refining"},
            priority=60
        ),
        ContentCategory(
            name="recipes_engineering",
            description="Engineering recipes for devices and gadgets",
            identifying_fields={"stationType": "engineering"},
            priority=60
        ),
        ContentCategory(
            name="recipes_enchanting",
            description="Enchanting recipes for magical enhancements",
            identifying_fields={"stationType": "enchanting"},
            priority=60
        ),
        ContentCategory(
            name="recipes_adornments",
            description="Adornment recipes for decorative items",
            identifying_fields={"stationType": "adornments"},
            priority=60
        ),
        # Fallback for recipes without stationType (test/placeholder recipes)
        ContentCategory(
            name="recipes_generic",
            description="Generic recipes (test/placeholder without specific discipline)",
            identifying_fields={"_has_field": "recipeId"},
            priority=55
        ),

        # Skills and skill unlocks
        ContentCategory(
            name="skill_unlocks",
            description="Skill unlock definitions - how players acquire skills",
            identifying_fields={"_has_field": "unlockId"},
            priority=52
        ),
        ContentCategory(
            name="skills",
            description="Player skills with effects, costs, and evolution paths",
            identifying_fields={"_has_field": "skillId"},
            priority=50
        ),

        # Enemies and abilities
        ContentCategory(
            name="abilities",
            description="Enemy abilities with tags and effect parameters",
            identifying_fields={"_has_field": "abilityId"},
            priority=45
        ),
        ContentCategory(
            name="enemies",
            description="Enemy definitions with stats, behavior, and loot",
            identifying_fields={"_has_field": "enemyId"},
            priority=44
        ),

        # NPCs and Quests
        ContentCategory(
            name="npcs",
            description="NPC definitions with dialogue and quest associations",
            identifying_fields={"_has_field": "npc_id"},
            priority=40
        ),
        ContentCategory(
            name="quests",
            description="Quest definitions with objectives and rewards",
            identifying_fields={"_has_field": "quest_id"},
            priority=40
        ),

        # Progression
        ContentCategory(
            name="classes",
            description="Starting class definitions with bonuses and skills",
            identifying_fields={"_has_field": "classId"},
            priority=35
        ),
        ContentCategory(
            name="titles",
            description="Achievement titles with prerequisites and bonuses",
            identifying_fields={"_has_field": "titleId"},
            priority=35
        ),

        # Resource nodes
        ContentCategory(
            name="resource_nodes",
            description="Gatherable resource node definitions",
            identifying_fields={"_has_field": "resourceId"},
            priority=30
        ),

        # World generation
        ContentCategory(
            name="world_chunks",
            description="World chunk templates for procedural generation",
            identifying_fields={"_has_field": "chunkType"},
            priority=25
        ),

        # Placements (minigame grids) - have placementMap field
        # Priority must be higher than recipes_generic (55) since placements also have recipeId
        ContentCategory(
            name="placements",
            description="Minigame placement patterns for crafting",
            identifying_fields={"_has_field": "placementMap"},
            priority=57
        ),
        # Refining placements use coreInputs/surroundingInputs instead of placementMap
        ContentCategory(
            name="placements_refining",
            description="Refining placement patterns (hub-and-spoke format)",
            identifying_fields={"_has_field": "coreInputs"},
            priority=56
        ),
    ]

    # Files to completely skip (metadata/config only, not game content)
    SKIP_FILES = [
        'tag-definitions',
        'value-translation',
        'stats-calculations',
        'skills-translation',
        'rarity-modifiers',      # Configuration file, not content
        'templates-crafting',    # Documentation/reference, not content
        'combat-config',         # Game config, not content
        'updates_manifest',      # Package manifest, not content
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

    # Skip patterns
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
        self.all_material_ids: Set[str] = set()
        self.all_item_ids: Set[str] = set()
        self.unclassified_items: List[Tuple[str, Dict]] = []

    def find_all_json_files(self) -> List[Path]:
        """Find all JSON files to process."""
        all_files = []

        for dir_name in self.SCAN_DIRECTORIES:
            dir_path = self.base_path / dir_name
            if dir_path.exists() and dir_path.is_dir():
                all_files.extend(dir_path.glob('*.JSON'))
                all_files.extend(dir_path.glob('*.json'))

        # Also scan root
        all_files.extend(self.base_path.glob('*.JSON'))
        all_files.extend(self.base_path.glob('*.json'))

        # Filter
        filtered = []
        for f in all_files:
            if f.is_dir():
                continue

            # Skip metadata files
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

    def classify_item(self, item: Dict) -> Optional[str]:
        """Classify an item based on its fields, returning the category name."""
        if not isinstance(item, dict):
            return None

        # Sort categories by priority (highest first)
        sorted_categories = sorted(self.CONTENT_CATEGORIES, key=lambda c: -c.priority)

        for category in sorted_categories:
            matches = True
            for field_key, expected_value in category.identifying_fields.items():
                if field_key == "_has_field":
                    # Special case: just check if field exists
                    if expected_value not in item:
                        matches = False
                        break
                elif field_key not in item:
                    matches = False
                    break
                elif item[field_key] != expected_value:
                    matches = False
                    break

            if matches:
                return category.name

        return None

    def extract_items_from_json(self, data: Any, source_file: str) -> List[Tuple[str, Dict]]:
        """Extract individual items from a JSON structure, classifying each one."""
        items = []

        if isinstance(data, list):
            # Top-level array
            for item in data:
                if isinstance(item, dict):
                    category = self.classify_item(item)
                    if category:
                        items.append((category, item))
                    else:
                        self.unclassified_items.append((source_file, item))

        elif isinstance(data, dict):
            # Check if it's a single item or a container
            category = self.classify_item(data)
            if category:
                items.append((category, data))
            else:
                # It's a container - iterate through all keys
                for key, value in data.items():
                    if key.lower() == 'metadata':
                        continue

                    if isinstance(value, list):
                        for item in value:
                            if isinstance(item, dict):
                                cat = self.classify_item(item)
                                if cat:
                                    items.append((cat, item))
                                else:
                                    self.unclassified_items.append((source_file, item))

                    elif isinstance(value, dict):
                        # Could be nested containers or a single item
                        cat = self.classify_item(value)
                        if cat:
                            items.append((cat, value))
                        else:
                            # Check if it's a container of lists
                            for subkey, subvalue in value.items():
                                if subkey.lower() == 'metadata':
                                    continue
                                if isinstance(subvalue, list):
                                    for item in subvalue:
                                        if isinstance(item, dict):
                                            cat2 = self.classify_item(item)
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
                item_id = item.get('itemId') or item.get('materialId') or item.get('recipeId') or \
                          item.get('skillId') or item.get('enemyId') or item.get('quest_id') or \
                          item.get('npc_id') or item.get('classId') or item.get('titleId') or \
                          item.get('abilityId') or item.get('name') or 'unknown'
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
                # Track special values
                if 'tag' in path.lower():
                    self.all_tags.add(value)
                if path.endswith('materialId') or path.endswith('itemId'):
                    self.all_material_ids.add(value)
                    self.all_item_ids.add(value)
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
        """Process a single JSON file, extracting and classifying all items."""
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
        # Find category description
        description = "Unknown category"
        for cat in self.CONTENT_CATEGORIES:
            if cat.name == category:
                description = cat.description
                break

        items = self.items_by_category.get(category, [])
        fields = self.field_registry.get(category, {})

        template = {
            "_meta": {
                "category": category,
                "description": description,
                "purpose": "LLM fine-tuning template",
                "generated_at": datetime.now().isoformat(),
                "total_items": len(items),
                "source_files": sorted(self.source_files_by_category.get(category, set())),
            },
            "_field_documentation": {},
            "_all_possible_values": {},
            "_usable_template": {},
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
                # Limit to reasonable number
                display_values = values[:100] if len(values) > 100 else values
                template["_all_possible_values"][path] = {
                    "values": display_values,
                    "total_unique": len(values),
                    "types": list(field_info.types),
                    "occurrences": field_info.occurrences,
                    "example_items": field_info.example_items[:3]
                }

        # Build usable template
        template["_usable_template"] = self._build_usable_template(fields)

        # Add sample items
        template["_sample_items"] = items[:5] if len(items) > 5 else items

        return template

    def _build_usable_template(self, fields: Dict[str, FieldInfo]) -> Dict:
        """Build a clean, copy-paste ready template."""
        usable = {}

        for path, field_info in sorted(fields.items()):
            if not path or '[]' in path:
                continue

            parts = path.split('.')
            current = usable

            # Navigate to correct nested location
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

    def generate_master_reference(self) -> Dict:
        """Generate a master reference of all values."""
        return {
            "_meta": {
                "description": "Master reference of all values for LLM fine-tuning",
                "generated_at": datetime.now().isoformat(),
                "total_categories": len(self.items_by_category),
                "total_items": sum(len(items) for items in self.items_by_category.values()),
                "total_unique_tags": len(self.all_tags),
                "total_unique_material_ids": len(self.all_material_ids),
            },
            "all_tags": sorted(self.all_tags),
            "all_material_ids": sorted(self.all_material_ids),
            "all_item_ids": sorted(self.all_item_ids),
            "categories_summary": {
                cat: {
                    "count": len(items),
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
        print("JSON Template Generator - LLM Fine-Tuning Edition")
        print("=" * 70)
        print(f"\nBase path: {self.base_path}")
        print(f"Output dir: {output_path}")
        print()

        # Find all JSON files
        all_files = self.find_all_json_files()
        print(f"Found {len(all_files)} JSON files to process")
        print()

        # Process each file
        for json_file in all_files:
            print(f"  Processing: {json_file.parent.name}/{json_file.name}")
            self.process_file(json_file)

        print()
        print("=" * 70)
        print("Content Classification Results:")
        print("=" * 70)

        # Show what was classified
        for category, items in sorted(self.items_by_category.items()):
            sources = self.source_files_by_category.get(category, set())
            print(f"  {category}: {len(items)} items from {len(sources)} files")

        if self.unclassified_items:
            print(f"\n  Unclassified: {len(self.unclassified_items)} items")
            for source, item in self.unclassified_items[:5]:
                keys = list(item.keys())[:5]
                print(f"    - {source}: keys={keys}")

        print()
        print("Generating templates...")

        # Generate individual category templates
        for category in sorted(self.items_by_category.keys()):
            if not self.items_by_category[category]:
                continue

            template = self.generate_category_template(category)
            output_file = output_path / f"template_{category}.json"
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(template, f, indent=2, default=str)
            print(f"  Created: {output_file.name} ({len(self.items_by_category[category])} items)")

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
        print(f"Total categories: {len(self.items_by_category)}")
        print(f"Total items classified: {sum(len(items) for items in self.items_by_category.values())}")
        print(f"Total unique tags: {len(self.all_tags)}")
        print("=" * 70)

    def generate_markdown_summary(self, output_path: Path):
        """Generate a human-readable markdown summary."""
        md_lines = [
            "# JSON Template Library - LLM Fine-Tuning",
            "",
            f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "",
            "## Purpose",
            "",
            "These templates are organized by **content type** for training specialized LLMs.",
            "Each category represents a distinct type of game content that could be handled",
            "by a dedicated fine-tuned model.",
            "",
            "## Categories Overview",
            "",
            "| Category | Items | Description |",
            "|----------|-------|-------------|",
        ]

        for category in sorted(self.items_by_category.keys()):
            items = self.items_by_category[category]
            desc = "Unknown"
            for cat in self.CONTENT_CATEGORIES:
                if cat.name == category:
                    desc = cat.description
                    break
            md_lines.append(f"| {category} | {len(items)} | {desc} |")

        md_lines.extend([
            "",
            "---",
            "",
            "## Category Details",
            "",
        ])

        for category in sorted(self.items_by_category.keys()):
            items = self.items_by_category[category]
            sources = self.source_files_by_category.get(category, set())
            fields = self.field_registry.get(category, {})

            desc = "Unknown"
            for cat in self.CONTENT_CATEGORIES:
                if cat.name == category:
                    desc = cat.description
                    break

            md_lines.append(f"### {category}")
            md_lines.append(f"**Description**: {desc}")
            md_lines.append(f"**Total Items**: {len(items)}")
            md_lines.append(f"**Source Files**: {', '.join(sorted(sources))}")
            md_lines.append("")
            md_lines.append("**Key Fields**:")

            for path, field_info in sorted(fields.items())[:15]:
                if not path or '[]' in path:
                    continue
                types_str = ', '.join(field_info.types)
                sample = list(field_info.values)[:3] if not field_info.is_array else list(field_info.array_item_values)[:3]
                sample_str = ', '.join(str(s)[:40] for s in sample)
                md_lines.append(f"- `{path}` ({types_str}): {sample_str}")

            md_lines.append("")
            md_lines.append("---")
            md_lines.append("")

        # Add all tags section
        md_lines.append("## All Tags")
        md_lines.append("")
        md_lines.append(f"Total unique tags: {len(self.all_tags)}")
        md_lines.append("")
        for tag in sorted(self.all_tags):
            md_lines.append(f"- `{tag}`")

        md_file = output_path / "TEMPLATE_LIBRARY.md"
        with open(md_file, 'w', encoding='utf-8') as f:
            f.write('\n'.join(md_lines))
        print(f"  Created: {md_file.name}")


def main():
    parser = argparse.ArgumentParser(
        description='Generate JSON templates organized by content type for LLM fine-tuning'
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

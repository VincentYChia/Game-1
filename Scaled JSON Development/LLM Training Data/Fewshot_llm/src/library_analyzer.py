"""
Library Analyzer - Extracts validation libraries from training data

Analyzes training data to build:
- Stat ranges by tier (for ±33% validation)
- Tag libraries per template
- Enum values (category, type, subtype, etc.)
- Text field patterns (if ≥20 examples)

This data is used by the validator and prompt generator.
"""

import json
from pathlib import Path
from typing import Dict, List, Any, Set, Optional, Tuple
from collections import defaultdict
from dataclasses import dataclass, asdict
import statistics


@dataclass
class StatRange:
    """Statistical range for a numeric field."""
    min_val: float
    max_val: float
    mean: float
    median: float
    count: int

    def within_tolerance(self, value: float, tolerance: float = 0.33) -> bool:
        """Check if value is within tolerance% of the range."""
        extended_min = self.min_val * (1 - tolerance)
        extended_max = self.max_val * (1 + tolerance)
        return extended_min <= value <= extended_max


@dataclass
class FieldLibrary:
    """Library of valid values for a field."""
    field_name: str
    values: Set[str]
    count: int
    is_enum: bool  # True if field has limited, consistent values

    def to_dict(self):
        return {
            'field_name': self.field_name,
            'values': sorted(list(self.values)),
            'count': self.count,
            'is_enum': self.is_enum
        }


@dataclass
class TemplateLibrary:
    """Complete validation library for a template."""
    template_name: str

    # Stat ranges by tier
    stat_ranges: Dict[str, Dict[int, StatRange]]  # field_name -> {tier -> StatRange}

    # Tag libraries
    metadata_tags: Set[str]
    effect_tags: Set[str]

    # Enum libraries
    enums: Dict[str, FieldLibrary]  # field_name -> FieldLibrary

    # Text patterns (if ≥20 examples)
    text_patterns: Dict[str, Set[str]]  # field_name -> Set of examples

    sample_count: int

    def to_dict(self):
        return {
            'template_name': self.template_name,
            'sample_count': self.sample_count,
            'stat_ranges': {
                field: {
                    tier: {
                        'min': sr.min_val,
                        'max': sr.max_val,
                        'mean': sr.mean,
                        'median': sr.median,
                        'count': sr.count
                    }
                    for tier, sr in tiers.items()
                }
                for field, tiers in self.stat_ranges.items()
            },
            'metadata_tags': sorted(list(self.metadata_tags)),
            'effect_tags': sorted(list(self.effect_tags)),
            'enums': {k: v.to_dict() for k, v in self.enums.items()},
            'text_patterns': {k: sorted(list(v)[:50]) for k, v in self.text_patterns.items()}  # Limit to 50 examples
        }


class LibraryAnalyzer:
    """Analyzes training data to extract validation libraries."""

    def __init__(self, training_data_dir: Path):
        """
        Initialize analyzer.

        Args:
            training_data_dir: Path to LLM Training Data directory
        """
        self.training_data_dir = Path(training_data_dir)
        self.libraries: Dict[str, TemplateLibrary] = {}

    def analyze_all_systems(self):
        """Analyze all training data systems."""
        print("\n" + "="*80)
        print("LIBRARY ANALYZER - Extracting Validation Data")
        print("="*80)

        # Map system directories to template names
        system_to_template = {
            'system1_smithing_recipe_to_item': 'smithing_items',
            'system2_refining_recipe_to_material': 'refining_items',
            'system3_alchemy_recipe_to_item': 'alchemy_items',
            'system4_engineering_recipe_to_device': 'engineering_items',
            'system5_enchanting_recipe_to_enchantment': 'enchanting_recipes',
            'system6_chunk_to_hostile': 'hostiles',
            'system7_drop_source_to_material': 'refining_items',  # Materials
            'system8_chunk_to_node': 'node_types',
            'system10_requirements_to_skill': 'skills',
            'system11_prerequisites_to_title': 'titles',
        }

        for system_dir, template_name in system_to_template.items():
            system_path = self.training_data_dir / system_dir
            if not system_path.exists():
                print(f"⚠️  System not found: {system_dir}")
                continue

            # Use full_dataset.json for analysis
            dataset_file = system_path / "full_dataset.json"
            if not dataset_file.exists():
                print(f"⚠️  Dataset not found: {dataset_file}")
                continue

            try:
                library = self.analyze_system(dataset_file, template_name)
                self.libraries[template_name] = library
                print(f"✓ Analyzed {template_name}: {library.sample_count} samples")
            except Exception as e:
                print(f"⚠️  Error analyzing {template_name}: {e}")

        return self.libraries

    def analyze_system(self, dataset_file: Path, template_name: str) -> TemplateLibrary:
        """Analyze a single system's training data."""
        with open(dataset_file, 'r') as f:
            pairs = json.load(f)

        # Extract outputs for analysis (inputs are recipes, outputs are the items)
        outputs = [pair['output'] for pair in pairs if 'output' in pair]

        if not outputs:
            raise ValueError(f"No outputs found in {dataset_file}")

        # Initialize collections
        metadata_tags = set()
        effect_tags = set()
        enums = defaultdict(lambda: {'values': set(), 'count': 0})
        text_patterns = defaultdict(set)
        stat_values_by_tier = defaultdict(lambda: defaultdict(list))  # field -> tier -> [values]

        # Analyze each output
        for output in outputs:
            tier = output.get('tier', 1)

            # Collect metadata tags
            if 'metadata' in output and 'tags' in output['metadata']:
                tags = output['metadata']['tags']
                if isinstance(tags, list):
                    metadata_tags.update(tags)

            # Collect effect tags
            if 'effectTags' in output:
                tags = output['effectTags']
                if isinstance(tags, list):
                    effect_tags.update(tags)

            # Collect tags from other locations
            if 'tags' in output and isinstance(output['tags'], list):
                metadata_tags.update(output['tags'])

            # Analyze all fields recursively
            self._analyze_fields(output, tier, enums, text_patterns, stat_values_by_tier)

        # Build stat ranges by tier
        stat_ranges = {}
        for field_name, tiers in stat_values_by_tier.items():
            stat_ranges[field_name] = {}
            for tier, values in tiers.items():
                if len(values) >= 2:  # Need at least 2 samples
                    stat_ranges[field_name][tier] = StatRange(
                        min_val=min(values),
                        max_val=max(values),
                        mean=statistics.mean(values),
                        median=statistics.median(values),
                        count=len(values)
                    )

        # Build enum libraries (fields with limited, consistent values)
        enum_libraries = {}
        for field_name, data in enums.items():
            values = data['values']
            count = data['count']

            # Consider it an enum if:
            # 1. Has at least 5 samples
            # 2. Has ≤20 unique values (suggesting it's not free text)
            is_enum = count >= 5 and len(values) <= 20

            enum_libraries[field_name] = FieldLibrary(
                field_name=field_name,
                values=values,
                count=count,
                is_enum=is_enum
            )

        # Filter text patterns (only keep if ≥20 examples)
        filtered_text_patterns = {
            k: v for k, v in text_patterns.items()
            if len(v) >= 20
        }

        return TemplateLibrary(
            template_name=template_name,
            stat_ranges=stat_ranges,
            metadata_tags=metadata_tags,
            effect_tags=effect_tags,
            enums=enum_libraries,
            text_patterns=filtered_text_patterns,
            sample_count=len(outputs)
        )

    def _analyze_fields(self, obj: Any, tier: int, enums: Dict, text_patterns: Dict, stat_values: Dict, prefix: str = ""):
        """Recursively analyze all fields in an object."""
        if not isinstance(obj, dict):
            return

        for key, value in obj.items():
            field_path = f"{prefix}.{key}" if prefix else key

            # Skip metadata fields
            if key.startswith('_'):
                continue

            # Handle numeric fields (potential stats)
            if isinstance(value, (int, float)) and key not in ['tier', 'slot', 'quantity']:
                stat_values[field_path][tier].append(float(value))

            # Handle string fields (potential enums or text patterns)
            elif isinstance(value, str):
                enums[field_path]['values'].add(value)
                enums[field_path]['count'] += 1

                # Also track as text pattern
                text_patterns[field_path].add(value)

            # Handle arrays of numbers (like [min, max] ranges)
            elif isinstance(value, list) and len(value) == 2 and all(isinstance(v, (int, float)) for v in value):
                # Track both min and max
                stat_values[f"{field_path}[0]"][tier].append(float(value[0]))
                stat_values[f"{field_path}[1]"][tier].append(float(value[1]))

            # Recurse into nested objects
            elif isinstance(value, dict):
                self._analyze_fields(value, tier, enums, text_patterns, stat_values, field_path)

            # Recurse into arrays
            elif isinstance(value, list) and value and isinstance(value[0], dict):
                # Analyze first item as representative
                self._analyze_fields(value[0], tier, enums, text_patterns, stat_values, field_path)

    def save_libraries(self, output_file: Path):
        """Save extracted libraries to JSON."""
        libraries_dict = {
            name: lib.to_dict()
            for name, lib in self.libraries.items()
        }

        with open(output_file, 'w') as f:
            json.dump(libraries_dict, f, indent=2)

        print(f"\n✓ Saved libraries to: {output_file}")

    def generate_prompt_guidance(self, template_name: str) -> str:
        """
        Generate inline guidance for system prompts.

        Returns formatted string with field-by-field guidance.
        """
        if template_name not in self.libraries:
            return f"// No guidance available for {template_name}"

        lib = self.libraries[template_name]
        lines = []

        lines.append(f"## Field Guidelines for {template_name.replace('_', ' ').title()}")
        lines.append("")

        # Tier ranges
        if lib.stat_ranges:
            lines.append("### Numeric Fields (by tier):")
            for field, tiers in sorted(lib.stat_ranges.items()):
                lines.append(f"\n**{field}**:")
                for tier in sorted(tiers.keys()):
                    sr = tiers[tier]
                    lines.append(f"  - T{tier}: {sr.min_val:.1f}-{sr.max_val:.1f} (avg: {sr.mean:.1f})")

        # Tag libraries
        if lib.metadata_tags:
            lines.append(f"\n### Metadata Tags:")
            lines.append(f"Pick 2-5 from: {', '.join(sorted(lib.metadata_tags))}")

        if lib.effect_tags:
            lines.append(f"\n### Effect Tags:")
            lines.append(f"Pick 2-5 from: {', '.join(sorted(lib.effect_tags))}")

        # Enums
        enum_fields = {k: v for k, v in lib.enums.items() if v.is_enum}
        if enum_fields:
            lines.append(f"\n### Enum Fields:")
            for field_name, field_lib in sorted(enum_fields.items()):
                values_str = ', '.join(sorted(field_lib.values))
                lines.append(f"  - **{field_name}**: Pick one from [{values_str}]")

        return "\n".join(lines)


def main():
    """Main function - analyze all systems and save libraries."""
    # From src/ go to Fewshot_llm/, then to LLM Training Data/
    training_data_dir = Path(__file__).parent.parent.parent

    analyzer = LibraryAnalyzer(training_data_dir)
    libraries = analyzer.analyze_all_systems()

    # Save libraries
    output_file = Path(__file__).parent.parent / "config" / "validation_libraries.json"
    output_file.parent.mkdir(exist_ok=True)
    analyzer.save_libraries(output_file)

    # Print summary
    print("\n" + "="*80)
    print("SUMMARY")
    print("="*80)
    for name, lib in libraries.items():
        print(f"\n{name}:")
        print(f"  Samples: {lib.sample_count}")
        print(f"  Stat ranges: {len(lib.stat_ranges)} fields")
        print(f"  Metadata tags: {len(lib.metadata_tags)}")
        print(f"  Effect tags: {len(lib.effect_tags)}")
        print(f"  Enums: {sum(1 for v in lib.enums.values() if v.is_enum)}/{len(lib.enums)}")

    print("\n" + "="*80)
    print("✓ Library analysis complete")
    print("="*80)


if __name__ == "__main__":
    main()

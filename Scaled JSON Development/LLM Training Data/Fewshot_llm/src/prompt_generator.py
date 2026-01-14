"""
Prompt Generator - Creates enhanced system prompts with inline guidance

Generates detailed system prompts that include:
- Valid options for enum fields
- Stat ranges by tier
- Tag libraries
- Formatting conventions
- Field-by-field guidance

This helps the LLM generate JSON that adheres to the existing game data.
"""

import json
from pathlib import Path
from typing import Dict, List, Any, Optional


class PromptGenerator:
    """Generates enhanced system prompts from validation libraries."""

    def __init__(self, validation_libraries_file: Path):
        """
        Initialize prompt generator.

        Args:
            validation_libraries_file: Path to validation_libraries.json
        """
        with open(validation_libraries_file, 'r') as f:
            self.libraries = json.load(f)

    def generate_prompt(self, template_name: str) -> str:
        """
        Generate enhanced prompt for a template.

        Args:
            template_name: Name of template (e.g., 'smithing_items')

        Returns:
            Enhanced prompt with inline guidance
        """
        if template_name not in self.libraries:
            return f"# No guidance available for {template_name}"

        lib = self.libraries[template_name]
        lines = []

        lines.append(f"# {template_name.replace('_', ' ').title()} - Field Guidelines")
        lines.append("")
        lines.append("Generate a JSON object following this structure with inline guidance:")
        lines.append("")

        # Build guided template
        lines.append("```json")
        lines.append("{")

        # Add metadata section if tags exist
        if lib.get('metadata_tags'):
            lines.append('  "metadata": {')
            lines.append('    "narrative": "Short narrative about the item (2-3 sentences). Describe its purpose and feel.",')
            tags_str = ', '.join(f'"{tag}"' for tag in sorted(lib['metadata_tags'])[:20])
            if len(lib['metadata_tags']) > 20:
                tags_str += f', ... ({len(lib["metadata_tags"])} total)'
            lines.append(f'    "tags": ["Pick 2-5 from: {tags_str}]')
            lines.append('  },')

        # Add core fields from enums
        enums = lib.get('enums', {})
        enum_fields = {k: v for k, v in enums.items() if v.get('is_enum', False)}

        for field_name, field_data in sorted(enum_fields.items()):
            if '.' in field_name:  # Skip nested fields for now
                continue

            values = sorted(field_data['values'])
            if len(values) <= 10:
                values_str = ', '.join(f'"{v}"' for v in values)
                lines.append(f'  "{field_name}": "Pick one: [{values_str}]",')
            else:
                # Show first 5 and indicate there are more
                values_str = ', '.join(f'"{v}"' for v in values[:5])
                lines.append(f'  "{field_name}": "Pick one: [{values_str}, ... ({len(values)} total)]",')

        # Add tier field with guidance
        lines.append('  "tier": 1,  // 1-4 (affects stat ranges below)')
        lines.append('  "rarity": "Pick one: [common, uncommon, rare, epic, legendary, unique]",')

        # Add stat ranges by tier
        stat_ranges = lib.get('stat_ranges', {})
        if stat_ranges:
            lines.append('')
            lines.append('  // === NUMERIC FIELDS (by tier) ===')

            for field_name, tiers in sorted(stat_ranges.items()):
                if '.' not in field_name or field_name.startswith('effectParams') or field_name.startswith('stats'):
                    # Build tier range string
                    tier_strs = []
                    for tier in sorted([int(t) for t in tiers.keys()]):
                        range_data = tiers[str(tier)]
                        tier_strs.append(f"T{tier}: {range_data['min']:.1f}-{range_data['max']:.1f}")

                    range_comment = ', '.join(tier_strs)

                    # Determine field path for JSON
                    if '.' in field_name:
                        # Nested field - show as comment for context
                        lines.append(f'  // {field_name}: {range_comment}')
                    else:
                        lines.append(f'  "{field_name}": 0,  // {range_comment}')

        # Add effect tags if present
        if lib.get('effect_tags'):
            lines.append('')
            tags_str = ', '.join(f'"{tag}"' for tag in sorted(lib['effect_tags'])[:15])
            if len(lib['effect_tags']) > 15:
                tags_str += f', ... ({len(lib["effect_tags"])} total)'
            lines.append(f'  "effectTags": ["Pick 2-5 from: {tags_str}],')

        # Add nested structures guidance
        if any('effectParams' in key for key in stat_ranges.keys()):
            lines.append('')
            lines.append('  "effectParams": {')
            for field_name, tiers in sorted(stat_ranges.items()):
                if field_name.startswith('effectParams.'):
                    param_name = field_name.replace('effectParams.', '')
                    tier_strs = []
                    for tier in sorted([int(t) for t in tiers.keys()]):
                        range_data = tiers[str(tier)]
                        tier_strs.append(f"T{tier}: {range_data['min']:.1f}-{range_data['max']:.1f}")
                    range_comment = ', '.join(tier_strs)
                    lines.append(f'    "{param_name}": 0,  // {range_comment}')
            lines.append('  },')

        if any(key.startswith('stats.') or key.startswith('statMultipliers.') for key in stat_ranges.keys()):
            lines.append('')
            lines.append('  "stats": {')
            for field_name, tiers in sorted(stat_ranges.items()):
                if field_name.startswith('stats.'):
                    stat_name = field_name.replace('stats.', '')
                    tier_strs = []
                    for tier in sorted([int(t) for t in tiers.keys()]):
                        range_data = tiers[str(tier)]
                        tier_strs.append(f"T{tier}: {range_data['min']:.1f}-{range_data['max']:.1f}")
                    range_comment = ', '.join(tier_strs)
                    lines.append(f'    "{stat_name}": 0,  // {range_comment}')
            lines.append('  },')

        # Add requirements section
        lines.append('')
        lines.append('  "requirements": {')
        lines.append('    "level": 1,  // Typically: T1: 1-5, T2: 6-15, T3: 16-25, T4: 26-30')
        lines.append('    "stats": {}  // Optional stat requirements')
        lines.append('  },')

        # Add flags
        lines.append('')
        lines.append('  "flags": {')
        lines.append('    "stackable": false,')
        lines.append('    "equippable": true,')
        lines.append('    "repairable": true')
        lines.append('  }')

        lines.append("}")
        lines.append("```")

        # Add important notes
        lines.append("")
        lines.append("## Important Guidelines:")
        lines.append("")
        lines.append("1. **IDs**: Use snake_case (e.g., `iron_sword`, `health_potion`)")
        lines.append("2. **Names**: Use Title Case matching ID (e.g., `Iron Sword`, `Health Potion`)")
        lines.append("3. **Tier Consistency**: Ensure all stats match the specified tier")
        lines.append("4. **Tags**: Only use tags from the library above")
        lines.append("5. **Narrative**: Keep it concise (2-3 sentences) and thematic")
        lines.append("6. **Stats**: Stay within ±33% of tier ranges (validation will flag outliers)")

        return "\n".join(lines)

    def generate_all_prompts(self, output_dir: Path):
        """
        Generate enhanced prompts for all templates.

        Args:
            output_dir: Directory to save prompt files
        """
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        for template_name in self.libraries.keys():
            prompt = self.generate_prompt(template_name)
            output_file = output_dir / f"{template_name}_prompt.txt"

            with open(output_file, 'w') as f:
                f.write(prompt)

            print(f"✓ Generated prompt for {template_name}")

        print(f"\n✓ Generated {len(self.libraries)} enhanced prompts")


def main():
    """Main function - generate all enhanced prompts."""
    libraries_file = Path(__file__).parent.parent / "config" / "validation_libraries.json"
    output_dir = Path(__file__).parent.parent / "prompts" / "enhanced"

    if not libraries_file.exists():
        print(f"❌ Validation libraries not found: {libraries_file}")
        print("   Run library_analyzer.py first to generate libraries.")
        return

    generator = PromptGenerator(libraries_file)
    generator.generate_all_prompts(output_dir)

    print("\n" + "="*80)
    print("✓ Enhanced prompts generated")
    print(f"  Location: {output_dir}")
    print("="*80)


if __name__ == "__main__":
    main()

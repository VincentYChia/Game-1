"""
Prompt Generator - Creates enhanced system prompts with inline guidance

Generates detailed system prompts that include:
- Complete tag libraries (no truncation)
- Stat ranges by tier (or combined for weight/range)
- Special formatting (~X for tight ranges)
- Template-specific layouts (e.g., hostiles with tier-based stats blocks)
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

    def _format_range(self, min_val: float, max_val: float) -> str:
        """
        Format a range, using ~X notation if range is tight.

        If range is within 15% of middle value, use ~X format.
        Otherwise use min-max format.
        """
        middle = (min_val + max_val) / 2
        tolerance = 0.15

        if max_val <= middle * (1 + tolerance) and min_val >= middle * (1 - tolerance):
            # Tight range - use ~X notation
            return f"~{middle:.1f}"
        else:
            # Wide range - use min-max
            return f"{min_val:.1f}-{max_val:.1f}"

    def _get_combined_range(self, tiers: Dict[str, Dict]) -> str:
        """Get combined range across all tiers."""
        all_mins = []
        all_maxs = []

        for tier_data in tiers.values():
            all_mins.append(tier_data['min'])
            all_maxs.append(tier_data['max'])

        if not all_mins or not all_maxs:
            return "0"  # Fallback if no data

        overall_min = min(all_mins)
        overall_max = max(all_maxs)

        return self._format_range(overall_min, overall_max)

    def _should_combine_tiers(self, field_name: str) -> bool:
        """Check if field should show combined range instead of per-tier."""
        combine_fields = ['weight', 'range']
        return any(f in field_name.lower() for f in combine_fields)

    def generate_prompt_hostiles(self, lib: Dict) -> str:
        """Generate special prompt for hostiles template with tier-based stats blocks."""
        lines = []

        lines.append("# Hostiles - Field Guidelines")
        lines.append("")
        lines.append("Generate a JSON object following this structure with inline guidance:")
        lines.append("")
        lines.append("```json")
        lines.append("{")

        # Metadata with tags
        if lib.get('metadata_tags'):
            lines.append('  "metadata": {')
            lines.append('    "narrative": "Short narrative about the enemy (2-3 sentences). Describe its nature and threat.",')
            tags = sorted(lib['metadata_tags'])
            tags_str = ', '.join(f'"{tag}"' for tag in tags)
            lines.append(f'    "tags": ["Pick 2-5 from: {tags_str}]')
            lines.append('  },')

        # Enums
        enums = lib.get('enums', {})
        for field_name, field_data in sorted(enums.items()):
            if not field_data.get('is_enum', False) or '.' in field_name:
                continue
            values = sorted(field_data['values'])
            values_str = ', '.join(f'"{v}"' for v in values)
            lines.append(f'  "{field_name}": "Pick one: [{values_str}]",')

        lines.append('  "tier": 1,  // 1-4 (determines stats block below)')
        lines.append('  "rarity": "Pick one: [common, uncommon, rare, epic, legendary, unique]",')
        lines.append('')

        # Stats blocks by tier
        stat_ranges = lib.get('stat_ranges', {})
        stat_fields = {}

        # Collect all stat fields
        for field_name, tiers in stat_ranges.items():
            if field_name.startswith('stats.'):
                stat_name = field_name.replace('stats.', '')
                stat_fields[stat_name] = tiers

        # Generate 4 tier blocks
        lines.append('  // === STATS BY TIER ===')
        lines.append('  // Use the stats block matching your tier')
        lines.append('')

        for tier in [1, 2, 3, 4]:
            lines.append(f'  // T{tier} Stats:')
            lines.append('  "stats": {')

            for stat_name, tiers in sorted(stat_fields.items()):
                if str(tier) in tiers:
                    tier_data = tiers[str(tier)]
                    range_str = self._format_range(tier_data['min'], tier_data['max'])
                    lines.append(f'    "{stat_name}": 0,  // {range_str}')
                else:
                    lines.append(f'    "{stat_name}": 0,')

            lines.append('  },')
            lines.append('')

        # Requirements
        lines.append('  "requirements": {')
        lines.append('    "level": 1,  // T1: 1-5, T2: 6-15, T3: 16-25, T4: 26-30')
        lines.append('    "stats": {}  // Stat requirements to fight this enemy')
        lines.append('  },')

        # Flags
        lines.append('')
        lines.append('  "flags": {')
        lines.append('    "stackable": false,')
        lines.append('    "equippable": false,')
        lines.append('    "hostile": true')
        lines.append('  }')

        lines.append("}")
        lines.append("```")

        # Guidelines
        lines.append("")
        lines.append("## Important Guidelines:")
        lines.append("")
        lines.append("1. **IDs**: Use snake_case (e.g., `iron_sword`, `health_potion`)")
        lines.append("2. **Names**: Use Title Case matching ID (e.g., `Iron Sword`, `Health Potion`)")
        lines.append("3. **Tier Consistency**: Ensure all stats match the specified tier")
        lines.append("4. **Tags**: Only use tags from the library above")
        lines.append("5. **Narrative**: Keep it concise (2-3 sentences) and thematic")
        lines.append("6. **Stats**: Stay within ±20% of tier ranges")

        return "\n".join(lines)

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

        # Special handling for hostiles
        if template_name == 'hostiles':
            return self.generate_prompt_hostiles(lib)

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
            # List ALL tags
            tags = sorted(lib['metadata_tags'])
            tags_str = ', '.join(f'"{tag}"' for tag in tags)
            lines.append(f'    "tags": ["Pick 2-5 from: {tags_str}]')
            lines.append('  },')

        # Add core fields from enums
        enums = lib.get('enums', {})
        enum_fields = {k: v for k, v in enums.items() if v.get('is_enum', False)}

        for field_name, field_data in sorted(enum_fields.items()):
            if '.' in field_name:  # Skip nested fields
                continue

            values = sorted(field_data['values'])
            values_str = ', '.join(f'"{v}"' for v in values)
            lines.append(f'  "{field_name}": "Pick one: [{values_str}]",')

        # Add tier field with guidance
        lines.append('  "tier": 1,  // 1-4 (affects stat ranges below)')
        # Always use standard rarity list
        lines.append('  "rarity": "Pick one: [common, uncommon, rare, epic, legendary, unique]",')

        # Add stat ranges
        stat_ranges = lib.get('stat_ranges', {})
        if stat_ranges:
            lines.append('')
            lines.append('  // === NUMERIC FIELDS (by tier) ===')

            # Top-level fields
            for field_name, tiers in sorted(stat_ranges.items()):
                if '.' not in field_name:
                    if self._should_combine_tiers(field_name):
                        # Show combined range
                        range_str = self._get_combined_range(tiers)
                        lines.append(f'  "{field_name}": 0,  // {range_str}')
                    else:
                        # Show per-tier ranges
                        tier_strs = []
                        for tier in sorted([int(t) for t in tiers.keys()]):
                            tier_data = tiers[str(tier)]
                            range_str = self._format_range(tier_data['min'], tier_data['max'])
                            tier_strs.append(f"T{tier}: {range_str}")
                        range_comment = ', '.join(tier_strs)
                        lines.append(f'  "{field_name}": 0,  // {range_comment}')

        # Add effect tags if present
        if lib.get('effect_tags'):
            lines.append('')
            # List ALL effect tags
            tags = sorted(lib['effect_tags'])
            tags_str = ', '.join(f'"{tag}"' for tag in tags)
            lines.append(f'  "effectTags": ["Pick 2-5 from: {tags_str}],')

        # Add nested structures guidance
        if any('effectParams' in key for key in stat_ranges.keys()):
            lines.append('')
            lines.append('  "effectParams": {')
            for field_name, tiers in sorted(stat_ranges.items()):
                if field_name.startswith('effectParams.'):
                    param_name = field_name.replace('effectParams.', '')

                    if self._should_combine_tiers(param_name):
                        range_str = self._get_combined_range(tiers)
                        lines.append(f'    "{param_name}": 0,  // {range_str}')
                    else:
                        tier_strs = []
                        for tier in sorted([int(t) for t in tiers.keys()]):
                            tier_data = tiers[str(tier)]
                            range_str = self._format_range(tier_data['min'], tier_data['max'])
                            tier_strs.append(f"T{tier}: {range_str}")
                        range_comment = ', '.join(tier_strs)
                        lines.append(f'    "{param_name}": 0,  // {range_comment}')
            lines.append('  },')

        if any(key.startswith('stats.') for key in stat_ranges.keys()):
            lines.append('')
            lines.append('  "stats": {')
            for field_name, tiers in sorted(stat_ranges.items()):
                if field_name.startswith('stats.'):
                    stat_name = field_name.replace('stats.', '')

                    if self._should_combine_tiers(stat_name):
                        range_str = self._get_combined_range(tiers)
                        lines.append(f'    "{stat_name}": 0,  // {range_str}')
                    else:
                        tier_strs = []
                        for tier in sorted([int(t) for t in tiers.keys()]):
                            tier_data = tiers[str(tier)]
                            range_str = self._format_range(tier_data['min'], tier_data['max'])
                            tier_strs.append(f"T{tier}: {range_str}")
                        range_comment = ', '.join(tier_strs)
                        lines.append(f'    "{stat_name}": 0,  // {range_comment}')
            lines.append('  },')

        # Add requirements section (NOT optional)
        lines.append('')
        lines.append('  "requirements": {')
        lines.append('    "level": 1,  // T1: 1-5, T2: 6-15, T3: 16-25, T4: 26-30')
        # Stat requirements are tier-based if we have data
        if any(key.startswith('requirements.stats') for key in stat_ranges.keys()):
            lines.append('    "stats": {')
            for field_name, tiers in sorted(stat_ranges.items()):
                if field_name.startswith('requirements.stats.'):
                    stat_name = field_name.replace('requirements.stats.', '')
                    tier_strs = []
                    for tier in sorted([int(t) for t in tiers.keys()]):
                        tier_data = tiers[str(tier)]
                        range_str = self._format_range(tier_data['min'], tier_data['max'])
                        tier_strs.append(f"T{tier}: {range_str}")
                    range_comment = ', '.join(tier_strs)
                    lines.append(f'      "{stat_name}": 0,  // {range_comment}')
            lines.append('    }')
        else:
            lines.append('    "stats": {}  // Stat requirements (tier-appropriate)')
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

        # Add important notes - USE PROVIDED TEMPLATE
        lines.append("")
        lines.append("## Important Guidelines:")
        lines.append("")
        lines.append("1. **IDs**: Use snake_case (e.g., `iron_sword`, `health_potion`)")
        lines.append("2. **Names**: Use Title Case matching ID (e.g., `Iron Sword`, `Health Potion`)")
        lines.append("3. **Tier Consistency**: Ensure all stats match the specified tier")
        lines.append("4. **Tags**: Only use tags from the library above")
        lines.append("5. **Narrative**: Keep it concise (2-3 sentences) and thematic")
        lines.append("6. **Stats**: Stay within ±20% of tier ranges")

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

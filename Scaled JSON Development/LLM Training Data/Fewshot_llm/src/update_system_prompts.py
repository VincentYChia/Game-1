"""
Update System Prompts - Combines base + enhanced prompts into final files

Reads:
  - Base prompts from prompts/components/base/
  - Enhanced prompts from prompts/enhanced/

Generates:
  - Complete combined prompts in prompts/system_prompts/

This ensures the LLM always uses the latest enhanced guidance while maintaining
the auto-generation capability.
"""

import json
from pathlib import Path


def update_system_prompts():
    """Update system prompts by combining base + enhanced guidance."""

    base_dir = Path(__file__).parent.parent
    components_base_dir = base_dir / "prompts" / "components" / "base"
    enhanced_dir = base_dir / "prompts" / "enhanced"
    output_dir = base_dir / "prompts" / "system_prompts"
    config_dir = base_dir / "config"

    # Load system metadata
    metadata_file = config_dir / "system_metadata.json"
    with open(metadata_file, 'r') as f:
        system_metadata = json.load(f)

    print("\n" + "="*80)
    print("UPDATING SYSTEM PROMPTS")
    print("="*80)

    updated_count = 0

    for system_key, metadata in system_metadata.items():
        template_name = metadata.get("template")

        # Load base prompt
        base_file = components_base_dir / f"system_{system_key}_base.md"
        if not base_file.exists():
            print(f"⚠️  Base prompt not found for system {system_key}, skipping...")
            continue

        with open(base_file, 'r') as f:
            base_prompt = f.read()

        # Load enhanced prompt if available
        enhanced_prompt = ""
        if template_name:
            enhanced_file = enhanced_dir / f"{template_name}_prompt.md"
            if enhanced_file.exists():
                with open(enhanced_file, 'r') as f:
                    enhanced_prompt = f.read()

        # Combine
        if enhanced_prompt:
            combined = f"{base_prompt}\n\n{enhanced_prompt}"
        else:
            combined = base_prompt

        # Save final prompt
        output_file = output_dir / f"system_{system_key}.md"
        with open(output_file, 'w') as f:
            f.write(combined)

        system_name = metadata["name"]
        print(f"✓ Updated system {system_key} ({system_name})")
        updated_count += 1

    print(f"\n✓ Updated {updated_count} system prompts")
    print(f"  Saved to: {output_dir}")
    print("="*80)


if __name__ == "__main__":
    update_system_prompts()

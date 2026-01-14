"""
Update System Prompts - Integrates enhanced prompts into system_prompts.json

Reads enhanced prompts from prompts/enhanced/ and updates system_prompts.json
to include the detailed field guidance.
"""

import json
from pathlib import Path


def update_system_prompts():
    """Update system_prompts.json with enhanced guidance."""

    # Map system keys to template names
    system_to_template = {
        "1": "smithing_items",
        "2": "refining_items",
        "3": "alchemy_items",
        "4": "engineering_items",
        "5": "enchanting_recipes",
        "6": "hostiles",
        "7": "refining_items",  # Drop source to material (uses refining template)
        "8": "node_types",
        "10": "skills",
        "11": "titles",
    }

    # Load existing system prompts
    config_dir = Path(__file__).parent.parent / "config"
    prompts_file = config_dir / "system_prompts.json"

    with open(prompts_file, 'r') as f:
        system_prompts = json.load(f)

    # Load enhanced prompts
    enhanced_dir = Path(__file__).parent.parent / "prompts" / "enhanced"

    updated_count = 0
    for system_key, template_name in system_to_template.items():
        if system_key not in system_prompts:
            print(f"⚠️  System {system_key} not found in system_prompts.json")
            continue

        enhanced_file = enhanced_dir / f"{template_name}_prompt.md"
        if not enhanced_file.exists():
            print(f"⚠️  Enhanced prompt not found: {enhanced_file}")
            continue

        # Read enhanced prompt
        with open(enhanced_file, 'r') as f:
            enhanced_prompt = f.read()

        # Get existing prompt
        existing = system_prompts[system_key]
        base_prompt = existing['prompt']

        # Combine: base prompt + enhanced guidance
        combined_prompt = f"{base_prompt}\n\n{enhanced_prompt}"

        # Update
        system_prompts[system_key]['prompt'] = combined_prompt
        updated_count += 1
        print(f"✓ Updated system {system_key} ({existing['name']})")

    # Save updated prompts
    with open(prompts_file, 'w') as f:
        json.dump(system_prompts, f, indent=2)

    print(f"\n✓ Updated {updated_count} system prompts")
    print(f"  Saved to: {prompts_file}")


if __name__ == "__main__":
    update_system_prompts()

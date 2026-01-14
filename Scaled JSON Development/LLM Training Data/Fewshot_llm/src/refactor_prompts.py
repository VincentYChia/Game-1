"""
Prompt Refactoring Script - Extracts and organizes system prompts

This script:
1. Extracts base prompts from system_prompts.json (before duplication)
2. Saves base prompts to prompts/components/base/
3. Combines base + enhanced prompts into final files
4. Saves complete prompts to prompts/system_prompts/

Each system gets its own complete prompt file that the LLM runner can load directly.
"""

import json
from pathlib import Path


# System to template mapping
SYSTEM_TO_TEMPLATE = {
    "1": "smithing_items",
    "2": "refining_items",
    "3": "alchemy_items",
    "4": "engineering_items",
    "5": "enchanting_recipes",
    "6": "hostiles",
    "7": "refining_items",
    "8": "node_types",
    "10": "skills",
    "11": "titles",
}

# Base prompts (the intro before enhanced guidance)
BASE_PROMPTS = {
    "1": "You are a crafting expert for an action fantasy sandbox RPG. Given smithing recipes with materials and metadata, generate complete item definitions with stats, tags, and properties. Return ONLY valid JSON matching the expected schema.",
    "2": "You are a refining expert for an action fantasy sandbox RPG. Given refining recipes, generate material definitions for refined outputs like ingots, planks, and processed goods. Return ONLY valid JSON.",
    "3": "You are an alchemy master for an action fantasy sandbox RPG. Given alchemy recipes with ingredients, generate complete potion and consumable definitions with effects and durations. Return ONLY valid JSON.",
    "4": "You are an engineering expert for an action fantasy sandbox RPG. Given engineering recipes, generate device definitions (turrets, traps, bombs) with mechanical effects and placement properties. Return ONLY valid JSON.",
    "5": "You are an enchantment crafter for an action fantasy sandbox RPG. Given enchanting recipes and base items, generate enchantment definitions with magical effects and stat bonuses. Return ONLY valid JSON.",
    "6": "You are a creature designer for an action fantasy sandbox RPG. Given world chunk data, generate hostile enemy definitions with behaviors, stats, and loot tables. Return ONLY valid JSON.",
    "7": "You are a loot designer for an action fantasy sandbox RPG. Given drop sources (enemies, nodes, chests), generate material drop definitions. Return ONLY valid JSON.",
    "8": "You are a world designer for an action fantasy sandbox RPG. Given chunk generation data, generate resource node definitions with yields, tiers, and spawn conditions. Return ONLY valid JSON.",
    "10": "You are a skill designer for an action fantasy sandbox RPG. Given character requirements and gameplay tags, generate skill definitions with effects, costs, and progression paths. Return ONLY valid JSON.",
    "11": "You are a progression designer for an action fantasy sandbox RPG. Given achievement prerequisites, generate title definitions with bonuses and unlock requirements. Return ONLY valid JSON.",
    "1x2": "You are a crafting designer for an action fantasy sandbox RPG. Given smithing recipes and grid constraints, determine optimal material placement patterns on the crafting grid. Return ONLY valid JSON with placement coordinates.",
    "2x2": "You are a refining designer for an action fantasy sandbox RPG. Given refining recipes, determine optimal material placement on refinery grids. Return ONLY valid JSON with placement coordinates.",
    "3x2": "You are an alchemy designer for an action fantasy sandbox RPG. Given alchemy recipes, determine optimal ingredient placement on brewing grids. Return ONLY valid JSON with placement coordinates.",
    "4x2": "You are an engineering designer for an action fantasy sandbox RPG. Given engineering recipes, determine optimal component placement on engineering grids. Return ONLY valid JSON with placement coordinates.",
    "5x2": "You are an enchantment designer for an action fantasy sandbox RPG. Given enchanting recipes, determine optimal rune and essence placement on enchanting grids. Return ONLY valid JSON with placement coordinates.",
}


def extract_and_save_base_prompts():
    """Extract base prompts and save to components/base/"""
    base_dir = Path(__file__).parent.parent
    components_base_dir = base_dir / "prompts" / "components" / "base"
    components_base_dir.mkdir(parents=True, exist_ok=True)

    print("\n" + "="*80)
    print("EXTRACTING BASE PROMPTS")
    print("="*80)

    for system_key, base_prompt in BASE_PROMPTS.items():
        filename = f"system_{system_key}_base.md"
        filepath = components_base_dir / filename

        with open(filepath, 'w') as f:
            f.write(base_prompt)

        print(f"✓ Saved: {filename}")

    print(f"\n✓ Extracted {len(BASE_PROMPTS)} base prompts")


def combine_prompts():
    """Combine base prompts + enhanced prompts into final complete prompts"""
    base_dir = Path(__file__).parent.parent
    components_base_dir = base_dir / "prompts" / "components" / "base"
    enhanced_dir = base_dir / "prompts" / "enhanced"
    output_dir = base_dir / "prompts" / "system_prompts"
    output_dir.mkdir(parents=True, exist_ok=True)

    print("\n" + "="*80)
    print("COMBINING PROMPTS")
    print("="*80)

    for system_key, template_name in SYSTEM_TO_TEMPLATE.items():
        # Load base prompt
        base_file = components_base_dir / f"system_{system_key}_base.md"
        if not base_file.exists():
            print(f"⚠️  Base prompt not found for system {system_key}, skipping...")
            continue

        with open(base_file, 'r') as f:
            base_prompt = f.read()

        # Load enhanced prompt
        enhanced_file = enhanced_dir / f"{template_name}_prompt.md"
        enhanced_prompt = ""
        if enhanced_file.exists():
            with open(enhanced_file, 'r') as f:
                enhanced_prompt = f.read()
        else:
            print(f"⚠️  No enhanced prompt for {template_name}")

        # Combine
        if enhanced_prompt:
            combined = f"{base_prompt}\n\n{enhanced_prompt}"
        else:
            combined = base_prompt

        # Save final prompt
        output_file = output_dir / f"system_{system_key}.md"
        with open(output_file, 'w') as f:
            f.write(combined)

        print(f"✓ Created: system_{system_key}.md ({len(combined)} chars)")

    # Also create placement system prompts (no enhanced guidance)
    for system_key in ["1x2", "2x2", "3x2", "4x2", "5x2"]:
        base_file = components_base_dir / f"system_{system_key}_base.md"
        if not base_file.exists():
            continue

        with open(base_file, 'r') as f:
            base_prompt = f.read()

        output_file = output_dir / f"system_{system_key}.md"
        with open(output_file, 'w') as f:
            f.write(base_prompt)

        print(f"✓ Created: system_{system_key}.md ({len(base_prompt)} chars)")

    print(f"\n✓ Generated complete prompt files in {output_dir}")


def create_system_metadata():
    """Create a simple metadata JSON with system names"""
    base_dir = Path(__file__).parent.parent
    config_dir = base_dir / "config"

    system_metadata = {
        "1": {"name": "Smithing Recipe→Item", "template": "smithing_items"},
        "2": {"name": "Refining Recipe→Material", "template": "refining_items"},
        "3": {"name": "Alchemy Recipe→Potion", "template": "alchemy_items"},
        "4": {"name": "Engineering Recipe→Device", "template": "engineering_items"},
        "5": {"name": "Enchanting Recipe→Enchantment", "template": "enchanting_recipes"},
        "6": {"name": "Chunk→Hostile Enemy", "template": "hostiles"},
        "7": {"name": "Drop Source→Material", "template": "refining_items"},
        "8": {"name": "Chunk→Resource Node", "template": "node_types"},
        "10": {"name": "Requirements→Skill", "template": "skills"},
        "11": {"name": "Prerequisites→Title", "template": "titles"},
        "1x2": {"name": "Smithing Placement", "template": None},
        "2x2": {"name": "Refining Placement", "template": None},
        "3x2": {"name": "Alchemy Placement", "template": None},
        "4x2": {"name": "Engineering Placement", "template": None},
        "5x2": {"name": "Enchanting Placement", "template": None},
    }

    metadata_file = config_dir / "system_metadata.json"
    with open(metadata_file, 'w') as f:
        json.dump(system_metadata, f, indent=2)

    print("\n✓ Created system_metadata.json")


def main():
    """Main execution"""
    print("\n" + "="*80)
    print("PROMPT REFACTORING")
    print("="*80)

    extract_and_save_base_prompts()
    combine_prompts()
    create_system_metadata()

    print("\n" + "="*80)
    print("REFACTORING COMPLETE")
    print("="*80)
    print("\nNew structure:")
    print("  prompts/components/base/       - Base prompts for each system")
    print("  prompts/enhanced/              - Auto-generated enhanced guidance")
    print("  prompts/system_prompts/        - Complete combined prompts (LLM uses these)")
    print("  config/system_metadata.json    - System names and template mappings")
    print("\n✓ Ready to update run.py to use new prompt files")


if __name__ == "__main__":
    main()

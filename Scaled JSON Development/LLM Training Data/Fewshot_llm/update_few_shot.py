"""
Update Few_shot_LLM.py with extracted examples and new prompts.
"""

import json
import re
from pathlib import Path


def load_extracted_examples():
    """Load the extracted examples."""
    from extracted_examples import EXTRACTED_EXAMPLES
    return EXTRACTED_EXAMPLES


def create_system_prompts():
    """Create improved system prompts using 'action fantasy sandbox RPG'."""
    return {
        "1": "You are a crafting expert for an action fantasy sandbox RPG. Given smithing recipes with materials and metadata, generate complete item definitions with stats, tags, and properties. Return ONLY valid JSON matching the expected schema.",
        "1x2": "You are a crafting designer for an action fantasy sandbox RPG. Given smithing recipes and grid constraints, determine optimal material placement patterns on the crafting grid. Return ONLY valid JSON with placement coordinates.",
        "2": "You are a refining expert for an action fantasy sandbox RPG. Given refining recipes, generate material definitions for refined outputs like ingots, planks, and processed goods. Return ONLY valid JSON.",
        "2x2": "You are a refining designer for an action fantasy sandbox RPG. Given refining recipes, determine optimal material placement on refinery grids. Return ONLY valid JSON with placement coordinates.",
        "3": "You are an alchemy master for an action fantasy sandbox RPG. Given alchemy recipes with ingredients, generate complete potion and consumable definitions with effects and durations. Return ONLY valid JSON.",
        "3x2": "You are an alchemy designer for an action fantasy sandbox RPG. Given alchemy recipes, determine optimal ingredient placement on brewing grids. Return ONLY valid JSON with placement coordinates.",
        "4": "You are an engineering specialist for an action fantasy sandbox RPG. Given engineering recipes, generate device definitions like traps, turrets, and mechanical contraptions. Return ONLY valid JSON.",
        "4x2": "You are an engineering designer for an action fantasy sandbox RPG. Given engineering recipes, determine optimal component placement on assembly grids. Return ONLY valid JSON with placement coordinates.",
        "5": "You are an enchantment crafter for an action fantasy sandbox RPG. Given enchanting recipes and base items, generate enchantment definitions with magical effects and stat bonuses. Return ONLY valid JSON.",
        "5x2": "You are an enchantment designer for an action fantasy sandbox RPG. Given enchanting recipes, determine optimal rune and essence placement on enchanting grids. Return ONLY valid JSON with placement coordinates.",
        "6": "You are an enemy designer for an action fantasy sandbox RPG. Given world chunk types and spawn data, generate complete hostile enemy definitions with stats, AI behaviors, and loot drops. Return ONLY valid JSON.",
        "7": "You are a loot designer for an action fantasy sandbox RPG. Given drop sources (enemies, nodes, chests), predict material drop tables with quantities and probabilities. Return ONLY valid JSON.",
        "8": "You are a world designer for an action fantasy sandbox RPG. Given world chunk characteristics, generate resource node definitions with gathering requirements and yield tables. Return ONLY valid JSON.",
        "10": "You are a skill designer for an action fantasy sandbox RPG. Given character requirements and gameplay tags, generate skill definitions with effects, costs, and progression paths. Return ONLY valid JSON.",
        "11": "You are a progression designer for an action fantasy sandbox RPG. Given achievement prerequisites, generate title definitions with bonuses and unlock requirements. Return ONLY valid JSON."
    }


def create_test_prompts():
    """Create test prompts for each system."""
    return {
        "1": """Create an item definition for this smithing recipe:

{
  "recipeId": "smithing_iron_axe",
  "stationTier": 1,
  "stationType": "smithing",
  "inputs": [
    {"materialId": "iron_ingot", "quantity": 3},
    {"materialId": "birch_plank", "quantity": 2}
  ],
  "narrative": "Solid iron axe for serious forestry work. Bites deep and true."
}

Return ONLY the JSON item definition, no extra text.""",
        "6": """Create an enemy definition for this chunk spawn:

{
  "chunkType": "dangerous_cave",
  "chunkCategory": "dangerous",
  "chunkTheme": "cave",
  "enemySpawns": {
    "beetle_armored": {
      "density": "moderate",
      "tier": 2
    }
  }
}

Return ONLY the JSON enemy definition, no extra text.""",
        "8": """Create a resource node definition for this chunk:

{
  "chunkType": "peaceful_forest",
  "chunkCategory": "peaceful",
  "chunkTheme": "forest",
  "resourceDensity": {
    "oak_tree": {
      "density": "very_high",
      "tierBias": "low"
    }
  }
}

Return ONLY the JSON node definition, no extra text.""",
        "10": """Create a skill definition for these requirements:

{
  "requiredLevel": 5,
  "requiredSkills": [],
  "discipline": "combat",
  "tags": ["damage_boost", "melee", "temporary"]
}

Return ONLY the JSON skill definition, no extra text."""
    }


def format_examples_for_insertion(examples):
    """Format examples for insertion into Python file."""
    lines = []
    for i, ex in enumerate(examples):
        lines.append("            {")

        # Parse JSON to get actual dict objects
        input_data = json.loads(ex["input"])
        output_data = json.loads(ex["output"])

        # Format with json.dumps
        lines.append(f"                \"input\": json.dumps({repr(input_data)}, indent=2),")
        lines.append(f"                \"output\": json.dumps({repr(output_data)}, indent=2)")

        if i < len(examples) - 1:
            lines.append("            },")
        else:
            lines.append("            }")

    return "\n".join(lines)


def update_few_shot_file():
    """Update the Few_shot_LLM.py file with new examples and prompts."""

    print("Loading extracted examples...")
    examples_dict = load_extracted_examples()

    print("Creating system prompts...")
    system_prompts = create_system_prompts()

    print("Creating test prompts...")
    test_prompts = create_test_prompts()

    print("\nUpdating Few_shot_LLM.py...")

    # Read the current file
    file_path = Path("Few_shot_LLM.py")
    with open(file_path, 'r') as f:
        content = f.read()

    # Build new SYSTEMS dictionary
    new_systems = []

    for system_key in ["1", "1x2", "2", "2x2", "3", "3x2", "4", "4x2", "5", "5x2", "6", "7", "8", "10", "11"]:
        examples = examples_dict.get(system_key, [])

        if len(examples) == 0:
            print(f"  Skipping system {system_key} - no examples")
            continue

        system_name = get_system_name(system_key)
        system_prompt = system_prompts.get(system_key, "Generic system prompt")
        test_prompt = test_prompts.get(system_key, "")

        # Build system entry
        system_entry = f'''    "{system_key}": {{
        "name": "{system_name}",
        "system_prompt": "{system_prompt}",
        "few_shot_examples": [
{format_examples_for_insertion(examples)}
        ],
        "test_prompt": """{test_prompt}"""
    }}'''

        new_systems.append(system_entry)
        print(f"  Added system {system_key} with {len(examples)} examples")

    # Join all systems
    new_systems_str = ",\n\n".join(new_systems)

    # Find and replace SYSTEMS section
    pattern = r'SYSTEMS = \{.*?\n\}\n\n'
    replacement = f'SYSTEMS = {{\n{new_systems_str}\n}}\n\n\n'

    new_content = re.sub(pattern, replacement, content, flags=re.DOTALL)

    # Write back
    with open(file_path, 'w') as f:
        f.write(new_content)

    print(f"\n✓ Updated Few_shot_LLM.py with {len(new_systems)} systems")


def get_system_name(system_key):
    """Get human-readable name for system."""
    names = {
        "1": "Smithing Recipe→Item",
        "1x2": "Smithing Placement",
        "2": "Refining Recipe→Material",
        "2x2": "Refining Placement",
        "3": "Alchemy Recipe→Potion",
        "3x2": "Alchemy Placement",
        "4": "Engineering Recipe→Device",
        "4x2": "Engineering Placement",
        "5": "Enchanting Recipe→Enchantment",
        "5x2": "Enchanting Placement",
        "6": "Chunk→Hostile Enemy",
        "7": "Drop Source→Material",
        "8": "Chunk→Resource Node",
        "10": "Requirements→Skill",
        "11": "Prerequisites→Title"
    }
    return names.get(system_key, f"System {system_key}")


if __name__ == "__main__":
    update_few_shot_file()

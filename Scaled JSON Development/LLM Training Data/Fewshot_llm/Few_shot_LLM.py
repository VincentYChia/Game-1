import anthropic
import json
from datetime import datetime
import os

# ============================================================================
# CONFIGURATION SECTION
# ============================================================================

# API Configuration
ANTHROPIC_API_KEY = "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"  # Replace with your API key
MODEL_NAME = "claude-sonnet-4-20250514"  # Current Sonnet model

# Model Parameters (modify as needed)
MAX_TOKENS = 2000
TEMPERATURE = 1.0
TOP_P = 0.999

# Output Configuration
OUTPUT_DIR = "fewshot_outputs"
os.makedirs(OUTPUT_DIR, exist_ok=True)

# ============================================================================
# SYSTEM PROMPTS & FEW-SHOT EXAMPLES
# ============================================================================

# Try to load extracted examples
try:
    from extracted_examples import EXTRACTED_EXAMPLES
    USING_EXTRACTED_EXAMPLES = True
    print(f"✓ Loaded {len(EXTRACTED_EXAMPLES)} systems from extracted_examples.py")
except ImportError:
    EXTRACTED_EXAMPLES = {}
    USING_EXTRACTED_EXAMPLES = False
    print("⚠ Warning: Could not load extracted_examples.py, using manual examples")


def build_systems_dict():
    """Build SYSTEMS dictionary with prompts and examples."""

    # System metadata (names, prompts, test prompts)
    system_info = {
        "1": {
            "name": "Smithing Recipe→Item",
            "system_prompt": "You are a crafting expert for an action fantasy sandbox RPG. Given smithing recipes with materials and metadata, generate complete item definitions with stats, tags, and properties. Return ONLY valid JSON matching the expected schema.",
            "test_prompt": """Create an item definition for this smithing recipe:

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

Return ONLY the JSON item definition, no extra text."""
        },
        "1x2": {
            "name": "Smithing Placement",
            "system_prompt": "You are a crafting designer for an action fantasy sandbox RPG. Given smithing recipes and grid constraints, determine optimal material placement patterns on the crafting grid. Return ONLY valid JSON with placement coordinates.",
            "test_prompt": ""
        },
        "2": {
            "name": "Refining Recipe→Material",
            "system_prompt": "You are a refining expert for an action fantasy sandbox RPG. Given refining recipes, generate material definitions for refined outputs like ingots, planks, and processed goods. Return ONLY valid JSON.",
            "test_prompt": ""
        },
        "2x2": {
            "name": "Refining Placement",
            "system_prompt": "You are a refining designer for an action fantasy sandbox RPG. Given refining recipes, determine optimal material placement on refinery grids. Return ONLY valid JSON with placement coordinates.",
            "test_prompt": ""
        },
        "3": {
            "name": "Alchemy Recipe→Potion",
            "system_prompt": "You are an alchemy master for an action fantasy sandbox RPG. Given alchemy recipes with ingredients, generate complete potion and consumable definitions with effects and durations. Return ONLY valid JSON.",
            "test_prompt": ""
        },
        "3x2": {
            "name": "Alchemy Placement",
            "system_prompt": "You are an alchemy designer for an action fantasy sandbox RPG. Given alchemy recipes, determine optimal ingredient placement on brewing grids. Return ONLY valid JSON with placement coordinates.",
            "test_prompt": ""
        },
        "5": {
            "name": "Enchanting Recipe→Enchantment",
            "system_prompt": "You are an enchantment crafter for an action fantasy sandbox RPG. Given enchanting recipes and base items, generate enchantment definitions with magical effects and stat bonuses. Return ONLY valid JSON.",
            "test_prompt": ""
        },
        "5x2": {
            "name": "Enchanting Placement",
            "system_prompt": "You are an enchantment designer for an action fantasy sandbox RPG. Given enchanting recipes, determine optimal rune and essence placement on enchanting grids. Return ONLY valid JSON with placement coordinates.",
            "test_prompt": ""
        },
        "6": {
            "name": "Chunk→Hostile Enemy",
            "system_prompt": "You are an enemy designer for an action fantasy sandbox RPG. Given world chunk types and spawn data, generate complete hostile enemy definitions with stats, AI behaviors, and loot drops. Return ONLY valid JSON.",
            "test_prompt": """Create an enemy definition for this chunk spawn:

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

Return ONLY the JSON enemy definition, no extra text."""
        },
        "7": {
            "name": "Drop Source→Material",
            "system_prompt": "You are a loot designer for an action fantasy sandbox RPG. Given drop sources (enemies, nodes, chests), predict material drop tables with quantities and probabilities. Return ONLY valid JSON.",
            "test_prompt": ""
        },
        "8": {
            "name": "Chunk→Resource Node",
            "system_prompt": "You are a world designer for an action fantasy sandbox RPG. Given world chunk characteristics, generate resource node definitions with gathering requirements and yield tables. Return ONLY valid JSON.",
            "test_prompt": """Create a resource node definition for this chunk:

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

Return ONLY the JSON node definition, no extra text."""
        },
        "10": {
            "name": "Requirements→Skill",
            "system_prompt": "You are a skill designer for an action fantasy sandbox RPG. Given character requirements and gameplay tags, generate skill definitions with effects, costs, and progression paths. Return ONLY valid JSON.",
            "test_prompt": """Create a skill definition for these requirements:

{
  "requiredLevel": 5,
  "requiredSkills": [],
  "discipline": "combat",
  "tags": ["damage_boost", "melee", "temporary"]
}

Return ONLY the JSON skill definition, no extra text."""
        },
        "11": {
            "name": "Prerequisites→Title",
            "system_prompt": "You are a progression designer for an action fantasy sandbox RPG. Given achievement prerequisites, generate title definitions with bonuses and unlock requirements. Return ONLY valid JSON.",
            "test_prompt": ""
        }
    }

    # Build complete SYSTEMS dictionary
    systems = {}

    for key, info in system_info.items():
        systems[key] = {
            "name": info["name"],
            "system_prompt": info["system_prompt"],
            "few_shot_examples": EXTRACTED_EXAMPLES.get(key, []) if USING_EXTRACTED_EXAMPLES else _get_manual_examples(key),
            "test_prompt": info["test_prompt"]
        }

    return systems


def _get_manual_examples(system_key):
    """Fallback manual examples if extracted examples not available."""
    # If extracted examples aren't available, return minimal examples
    return [
        {
            "input": '{"message": "Example input for system ' + system_key + '"}',
            "output": '{"message": "Example output for system ' + system_key + '"}'
        }
    ]


# Build the SYSTEMS dictionary
SYSTEMS = build_systems_dict()


# CORE FUNCTIONS
# ============================================================================

def build_prompt(system_config):
    """Build the complete prompt with few-shot examples."""
    prompt_parts = []

    # Add few-shot examples
    if system_config["few_shot_examples"]:
        prompt_parts.append("Here are some examples:\n")
        for i, example in enumerate(system_config["few_shot_examples"], 1):
            prompt_parts.append(f"Example {i}:")
            prompt_parts.append(f"Input: {example['input']}")
            prompt_parts.append(f"Output: {example['output']}\n")

    # Add test prompt
    if system_config["test_prompt"]:
        prompt_parts.append(f"Now solve this:\n{system_config['test_prompt']}")

    return "\n".join(prompt_parts)


def run_model(system_key):
    """Run the selected model system."""
    if system_key not in SYSTEMS:
        print(f"Error: System '{system_key}' not found.")
        print(f"Available systems: {', '.join(SYSTEMS.keys())}")
        return None

    system_config = SYSTEMS[system_key]
    print(f"\n{'=' * 60}")
    print(f"Running System: {system_config['name']}")
    print(f"{'=' * 60}\n")

    # Build prompt
    user_prompt = build_prompt(system_config)

    if not user_prompt.strip():
        print("Error: No test prompt provided. Please add a test_prompt to the system config.")
        return None

    # Initialize Anthropic client
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    # Make API call
    print("Calling API...")
    try:
        message = client.messages.create(
            model=MODEL_NAME,
            max_tokens=MAX_TOKENS,
            temperature=TEMPERATURE,
            top_p=TOP_P,
            system=system_config["system_prompt"],
            messages=[
                {"role": "user", "content": user_prompt}
            ]
        )

        response_text = message.content[0].text

        # Prepare result
        result = {
            "timestamp": datetime.now().isoformat(),
            "system_key": system_key,
            "system_name": system_config["name"],
            "model": MODEL_NAME,
            "parameters": {
                "max_tokens": MAX_TOKENS,
                "temperature": TEMPERATURE,
                "top_p": TOP_P
            },
            "system_prompt": system_config["system_prompt"],
            "few_shot_examples": system_config["few_shot_examples"],
            "test_prompt": system_config["test_prompt"],
            "response": response_text,
            "usage": {
                "input_tokens": message.usage.input_tokens,
                "output_tokens": message.usage.output_tokens
            }
        }

        # Save output
        filename = f"{OUTPUT_DIR}/system_{system_key}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(filename, 'w') as f:
            json.dump(result, f, indent=2)

        # Add output file path to result
        result["output_file"] = filename

        print(f"\n{'=' * 60}")
        print("RESPONSE:")
        print(f"{'=' * 60}")
        print(response_text)
        print(f"\n{'=' * 60}")
        print(f"Output saved to: {filename}")
        print(f"Tokens used - Input: {message.usage.input_tokens}, Output: {message.usage.output_tokens}")
        print(f"{'=' * 60}\n")

        return result

    except Exception as e:
        print(f"Error during API call: {e}")
        return None


# ============================================================================
# INTERACTIVE MENU
# ============================================================================

def display_systems_menu():
    """Display available systems with descriptions."""
    print("\n" + "="*80)
    print("FEW-SHOT LLM - ACTION FANTASY SANDBOX RPG")
    print("="*80)
    print("\nAvailable Systems:")
    print("-"*80)

    for key in sorted(SYSTEMS.keys(), key=lambda x: (x.replace("x", "."), len(x))):
        system = SYSTEMS[key]
        name = system["name"]
        examples_count = len(system.get("few_shot_examples", []))
        has_test = "✓" if system.get("test_prompt", "").strip() else "✗"
        print(f"  [{key:4s}] {name:30s} ({examples_count} examples) Test: {has_test}")

    print("-"*80)


def get_system_selection():
    """Get user's system selection."""
    while True:
        print("\nOptions:")
        print("  1. Run ALL systems with test prompts")
        print("  2. Run a SINGLE system")
        print("  3. Run a RANGE of systems (e.g., 1-6)")
        print("  4. Run SPECIFIC systems (e.g., 1,6,8)")
        print("  5. Exit")

        choice = input("\nEnter your choice (1-5): ").strip()

        if choice == "1":
            # All systems with test prompts
            return [key for key, system in SYSTEMS.items() if system.get("test_prompt", "").strip()]

        elif choice == "2":
            # Single system
            display_systems_menu()
            system_key = input("\nEnter system key (e.g., 1, 6, 1x2): ").strip()
            if system_key in SYSTEMS:
                return [system_key]
            else:
                print(f"Error: System '{system_key}' not found")
                continue

        elif choice == "3":
            # Range
            range_input = input("\nEnter range (e.g., 1-6): ").strip()
            try:
                start, end = range_input.split("-")
                start, end = int(start.strip()), int(end.strip())
                return [str(i) for i in range(start, end + 1) if str(i) in SYSTEMS]
            except:
                print("Error: Invalid range format")
                continue

        elif choice == "4":
            # Specific systems
            systems_input = input("\nEnter system keys separated by commas (e.g., 1,6,8): ").strip()
            systems = [s.strip() for s in systems_input.split(",")]
            valid_systems = [s for s in systems if s in SYSTEMS]

            if valid_systems:
                return valid_systems
            else:
                print("Error: No valid systems found")
                continue

        elif choice == "5":
            print("\nExiting...")
            return None

        else:
            print("Error: Invalid choice")


def run_interactive():
    """Run interactive mode."""
    display_systems_menu()

    systems_to_run = get_system_selection()

    if not systems_to_run:
        return

    print(f"\n{'='*80}")
    print(f"Running {len(systems_to_run)} system(s): {', '.join(systems_to_run)}")
    print(f"{'='*80}\n")

    results = []
    for system_key in systems_to_run:
        print(f"\n{'#'*80}")
        print(f"# System {system_key}: {SYSTEMS[system_key]['name']}")
        print(f"{'#'*80}\n")

        result = run_model(system_key)
        results.append((system_key, result))

        print(f"\n{'='*80}")
        print(f"Completed system {system_key}")
        print(f"{'='*80}\n")

        # Ask if user wants to continue
        if len(systems_to_run) > 1 and system_key != systems_to_run[-1]:
            continue_prompt = input("Press Enter to continue to next system (or 'q' to quit): ").strip().lower()
            if continue_prompt == 'q':
                break

    # Print summary
    print(f"\n{'='*80}")
    print("EXECUTION SUMMARY")
    print(f"{'='*80}")

    for system_key, result in results:
        if result:
            status = "✓ SUCCESS"
            tokens = result.get("usage", {})
            token_info = f"({tokens.get('input_tokens', 0)} in, {tokens.get('output_tokens', 0)} out)"
        else:
            status = "✗ FAILED"
            token_info = ""

        print(f"  System {system_key:4s}: {status:12s} {token_info}")

    print(f"{'='*80}\n")


# ============================================================================
# MAIN EXECUTION
# ============================================================================

if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        # Command-line mode
        system_key = sys.argv[1]
        if system_key in SYSTEMS:
            run_model(system_key)
        else:
            print(f"Error: System '{system_key}' not found")
            print(f"Available systems: {', '.join(SYSTEMS.keys())}")
    else:
        # Interactive mode
        run_interactive()
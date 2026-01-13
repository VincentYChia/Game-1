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

SYSTEMS = {
    "1": {
        "name": "Smith Recipe->Item",
        "system_prompt": "You are a crafting expert. Given smithing recipes, predict the resulting item.",
        "few_shot_examples": [
            {"input": "Iron Ingot + Iron Ingot = ?", "output": "Iron Plate"},
            {"input": "Steel Bar + Wood Plank = ?", "output": "Steel Hammer"},
        ],
        "test_prompt": ""  # Add your test prompt here
    },

    "1x2": {
        "name": "Smithing Placement",
        "system_prompt": "You determine optimal placement patterns for smithing recipes.",
        "few_shot_examples": [
            {"input": "Sword crafting", "output": "Vertical placement: Handle bottom, blade top"},
            {"input": "Shield crafting", "output": "Center placement with rim materials"},
        ],
        "test_prompt": ""
    },

    "2": {
        "name": "Refining Recipe->Material",
        "system_prompt": "You are a refining expert. Predict refined materials from raw inputs.",
        "few_shot_examples": [
            {"input": "Iron Ore + Heat = ?", "output": "Iron Ingot"},
            {"input": "Raw Gold + Flux = ?", "output": "Pure Gold Bar"},
        ],
        "test_prompt": ""
    },

    "2x2": {
        "name": "Refining Placement",
        "system_prompt": "You determine optimal placement for refining processes.",
        "few_shot_examples": [
            {"input": "Ore smelting", "output": "Ore in center, fuel below"},
            {"input": "Metal purification", "output": "Raw metal top, catalyst bottom"},
        ],
        "test_prompt": ""
    },

    "3": {
        "name": "Alchemy Recipe->Item",
        "system_prompt": "You are an alchemy master. Predict potion outcomes from ingredients.",
        "few_shot_examples": [
            {"input": "Red Herb + Blue Mushroom = ?", "output": "Health Potion"},
            {"input": "Spider Eye + Sugar = ?", "output": "Speed Potion"},
        ],
        "test_prompt": ""
    },

    "3x2": {
        "name": "Alchemy Placement",
        "system_prompt": "You determine ingredient placement for alchemical reactions.",
        "few_shot_examples": [
            {"input": "Brewing health potion", "output": "Base liquid bottom, herbs floating"},
            {"input": "Mixing mana elixir", "output": "Crystal dust dissolved first, essence after"},
        ],
        "test_prompt": ""
    },

    "4": {
        "name": "Engineering Recipe->Device",
        "system_prompt": "You are an engineering expert. Predict devices from component recipes.",
        "few_shot_examples": [
            {"input": "Gears + Spring + Casing = ?", "output": "Mechanical Clock"},
            {"input": "Wire + Battery + Bulb = ?", "output": "Flashlight"},
        ],
        "test_prompt": ""
    },

    "4x2": {
        "name": "Engineering Placement",
        "system_prompt": "You determine component placement for engineering assemblies.",
        "few_shot_examples": [
            {"input": "Building a motor", "output": "Rotor center, coils surrounding, casing last"},
            {"input": "Creating circuit", "output": "Power source left, components middle, output right"},
        ],
        "test_prompt": ""
    },

    "5": {
        "name": "Enchanting Recipe->Enchantment",
        "system_prompt": "You are an enchanting expert. Predict enchantments from materials.",
        "few_shot_examples": [
            {"input": "Diamond + Fire Essence = ?", "output": "Flame Edge Enchantment"},
            {"input": "Moonstone + Feather = ?", "output": "Levitation Enchantment"},
        ],
        "test_prompt": ""
    },

    "5x2": {
        "name": "Enchanting Placement",
        "system_prompt": "You determine rune and material placement for enchanting.",
        "few_shot_examples": [
            {"input": "Weapon enchanting", "output": "Runes on blade edge, essence at hilt"},
            {"input": "Armor enchanting", "output": "Protective runes at chest, enhancement runes at joints"},
        ],
        "test_prompt": ""
    },

    "6": {
        "name": "Chunk->Hostile",
        "system_prompt": "You predict hostile spawns based on chunk characteristics.",
        "few_shot_examples": [
            {"input": "Dark cave chunk, low light level", "output": "Zombies, Spiders"},
            {"input": "Nether chunk, lava present", "output": "Zombie Pigmen, Ghasts"},
        ],
        "test_prompt": ""
    },

    "7": {
        "name": "Drop Source->Material",
        "system_prompt": "You predict material drops from various sources.",
        "few_shot_examples": [
            {"input": "Mining iron ore", "output": "Raw Iron, Stone"},
            {"input": "Defeating zombie", "output": "Rotten Flesh, rarely Iron Ingot"},
        ],
        "test_prompt": ""
    },

    "8": {
        "name": "Chunk->Node",
        "system_prompt": "You predict resource nodes in chunks based on characteristics.",
        "few_shot_examples": [
            {"input": "Mountain chunk, high altitude", "output": "Iron Ore, Coal, Emeralds"},
            {"input": "Desert chunk, surface level", "output": "Sand, Sandstone, Cactus"},
        ],
        "test_prompt": ""
    },

    "10": {
        "name": "Req->Skill",
        "system_prompt": "You determine skill unlocks based on requirements met.",
        "few_shot_examples": [
            {"input": "Mining Level 10, 100 ore mined", "output": "Unlocked: Efficient Mining Skill"},
            {"input": "Combat Level 5, defeated 50 enemies", "output": "Unlocked: Power Strike Skill"},
        ],
        "test_prompt": ""
    },

    "11": {
        "name": "Pre->Title",
        "system_prompt": "You determine title unlocks based on prerequisites.",
        "few_shot_examples": [
            {"input": "Completed 10 quests, helped 20 NPCs", "output": "Title: 'The Helpful'"},
            {"input": "Defeated dragon, max level achieved", "output": "Title: 'Dragonslayer Supreme'"},
        ],
        "test_prompt": ""
    },

    "15": {
        "name": "Custom System",
        "system_prompt": "Custom system prompt here.",
        "few_shot_examples": [
            {"input": "Example input 1", "output": "Example output 1"},
        ],
        "test_prompt": ""
    }
}


# ============================================================================
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
# MAIN EXECUTION
# ============================================================================

if __name__ == "__main__":
    # SELECT WHICH SYSTEM TO RUN HERE
    # Options: "1", "1x2", "2", "2x2", "3", "3x2", "4", "4x2", "5", "5x2",
    #          "6", "7", "8", "10", "11", "15"

    SYSTEM_TO_RUN = "1"  # <<< CHANGE THIS TO SELECT SYSTEM

    # Run the selected system
    run_model(SYSTEM_TO_RUN)

    # To run multiple systems in sequence, uncomment:
    # for system_key in ["1", "2", "3"]:
    #     run_model(system_key)
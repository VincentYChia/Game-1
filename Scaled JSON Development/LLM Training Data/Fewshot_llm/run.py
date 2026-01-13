"""
Few-Shot LLM Runner - Main Entry Point

Simple interface to run few-shot LLM tests for game JSON generation.
"""
import json
import os
import sys

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from llm_runner import LLMRunner
from validator import JSONValidator


# ============================================================================
# CONFIGURATION
# ============================================================================

API_KEY = "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"
MODEL = "claude-sonnet-4-20250514"

MAX_TOKENS = 2000
TEMPERATURE = 1.0
TOP_P = 0.999

OUTPUT_DIR = "outputs"


# ============================================================================
# LOAD CONFIGURATION FILES
# ============================================================================

def load_config():
    """Load all configuration files."""
    print("Loading configuration...")

    with open('config/system_prompts.json', 'r') as f:
        system_prompts = json.load(f)

    with open('config/test_inputs.json', 'r') as f:
        test_inputs = json.load(f)

    with open('examples/few_shot_examples.json', 'r') as f:
        few_shot_examples = json.load(f)

    print(f"✓ Loaded {len(system_prompts)} system prompts")
    print(f"✓ Loaded {len(test_inputs)} test inputs")
    print(f"✓ Loaded {sum(len(ex) for ex in few_shot_examples.values())} total examples\n")

    return system_prompts, test_inputs, few_shot_examples


# ============================================================================
# INTERACTIVE MENU
# ============================================================================

def get_system_selection(available_systems):
    """Get user's system selection."""
    print("\n" + "="*80)
    print("FEW-SHOT LLM RUNNER - SELECT SYSTEMS TO TEST")
    print("="*80)
    print("\nOptions:")
    print("  1. Run ALL systems with test inputs")
    print("  2. Run a SINGLE system")
    print("  3. Run a RANGE of systems (e.g., 1-6)")
    print("  4. Run SPECIFIC systems (e.g., 1,3,5)")
    print("  5. Exit")

    choice = input("\nEnter your choice (1-5): ").strip()

    if choice == "1":
        return available_systems
    elif choice == "2":
        system = input(f"Enter system key ({', '.join(available_systems)}): ").strip()
        return [system] if system in available_systems else []
    elif choice == "3":
        range_input = input("Enter range (e.g., 1-6): ").strip()
        start, end = range_input.split('-')
        return [s for s in available_systems if start <= s <= end]
    elif choice == "4":
        specific = input("Enter systems (e.g., 1,3,5): ").strip()
        return [s.strip() for s in specific.split(',') if s.strip() in available_systems]
    elif choice == "5":
        print("Exiting...")
        sys.exit(0)
    else:
        print("Invalid choice. Please try again.")
        return get_system_selection(available_systems)


# ============================================================================
# MAIN EXECUTION
# ============================================================================

def main():
    """Main execution function."""
    # Load configuration
    system_prompts, test_inputs, few_shot_examples = load_config()

    # Get systems with test inputs
    available_systems = sorted(test_inputs.keys())

    if not available_systems:
        print("❌ No systems with test inputs found!")
        return

    # Get user selection
    selected_systems = get_system_selection(available_systems)

    if not selected_systems:
        print("❌ No valid systems selected!")
        return

    print(f"\n✓ Selected {len(selected_systems)} system(s): {', '.join(selected_systems)}\n")

    # Initialize LLM runner
    runner = LLMRunner(api_key=API_KEY, model=MODEL)

    # Run selected systems
    results = []
    for system_key in selected_systems:
        system_info = system_prompts[system_key]
        test_input = test_inputs[system_key]
        examples = few_shot_examples.get(system_key, [])

        if not examples:
            print(f"⚠ Warning: System {system_key} has no few-shot examples, skipping...\n")
            continue

        try:
            result = runner.run_system(
                system_key=system_key,
                system_name=system_info["name"],
                system_prompt=system_info["prompt"],
                few_shot_examples=examples,
                test_prompt=test_input["prompt"],
                max_tokens=MAX_TOKENS,
                temperature=TEMPERATURE,
                top_p=TOP_P
            )

            filepath = runner.save_result(result, OUTPUT_DIR)
            results.append((system_key, filepath, result))

        except Exception as e:
            print(f"❌ Error running system {system_key}: {e}\n")
            continue

    # Validate results
    if results:
        print("\n" + "="*80)
        print("VALIDATING OUTPUTS")
        print("="*80 + "\n")

        validator = JSONValidator("../../json_templates")

        for system_key, filepath, result in results:
            print(f"Validating system {system_key}...")
            # Extract JSON from response
            response = result["response"]
            try:
                # Try to parse response as JSON
                if response.strip().startswith('{'):
                    output_json = json.loads(response)
                else:
                    # Find JSON in response
                    start = response.find('{')
                    end = response.rfind('}') + 1
                    if start != -1 and end > start:
                        output_json = json.loads(response[start:end])
                    else:
                        print(f"  ❌ No valid JSON found in response\n")
                        continue

                # Validate (would need template mapping)
                print(f"  ✓ Valid JSON structure\n")

            except json.JSONDecodeError as e:
                print(f"  ❌ JSON parse error: {e}\n")

    print("\n" + "="*80)
    print(f"COMPLETED - {len(results)} system(s) processed")
    print("="*80 + "\n")


if __name__ == "__main__":
    main()

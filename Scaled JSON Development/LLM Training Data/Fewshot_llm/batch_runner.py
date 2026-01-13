"""
Batch Runner for Few-Shot LLM Testing

Runs all systems, collects outputs, and validates results.
"""

import json
import os
import sys
from datetime import datetime
from pathlib import Path

# Import the Few_shot_LLM module
sys.path.insert(0, str(Path(__file__).parent))
from Few_shot_LLM import SYSTEMS, run_model, MODEL_NAME, MAX_TOKENS, TEMPERATURE, TOP_P

# Import validator
from validator import JSONValidator


# System to template mapping for validation
SYSTEM_TEMPLATE_MAP = {
    "1": "smithing_items",
    "1x2": "smithing_recipes",  # For placement
    "2": "refining_items",
    "2x2": "refining_recipes",
    "3": "alchemy_items",
    "3x2": "alchemy_recipes",
    "4": "engineering_items",
    "4x2": "engineering_recipes",
    "5": "enchanting_recipes",
    "5x2": "enchanting_recipes",
    "6": "hostiles",
    "7": "MASTER_REFERENCE",
    "8": "node_types",
    "10": "skills",
    "11": "titles"
}


def run_all_systems(systems_to_run=None, skip_empty=True):
    """
    Run all systems (or specified subset) and collect results.

    Args:
        systems_to_run: List of system keys to run. If None, run all.
        skip_empty: Skip systems with empty test_prompt

    Returns:
        Dictionary with results for each system
    """
    results = {}

    if systems_to_run is None:
        systems_to_run = list(SYSTEMS.keys())

    print(f"\n{'='*80}")
    print(f"BATCH RUNNER - Testing {len(systems_to_run)} systems")
    print(f"Model: {MODEL_NAME}")
    print(f"Parameters: max_tokens={MAX_TOKENS}, temp={TEMPERATURE}, top_p={TOP_P}")
    print(f"{'='*80}\n")

    for system_key in systems_to_run:
        if system_key not in SYSTEMS:
            print(f"Warning: System '{system_key}' not found, skipping")
            continue

        system_config = SYSTEMS[system_key]

        # Skip if no test prompt
        if skip_empty and not system_config.get("test_prompt", "").strip():
            print(f"Skipping system '{system_key}' - no test prompt defined")
            results[system_key] = {"skipped": True, "reason": "no_test_prompt"}
            continue

        print(f"\n{'-'*80}")
        print(f"Running System {system_key}: {system_config['name']}")
        print(f"{'-'*80}")

        try:
            result = run_model(system_key)

            if result:
                results[system_key] = {
                    "success": True,
                    "output_file": result.get("output_file"),
                    "response": result.get("response"),
                    "usage": result.get("usage")
                }
            else:
                results[system_key] = {
                    "success": False,
                    "error": "run_model returned None"
                }

        except Exception as e:
            print(f"Error running system {system_key}: {e}")
            results[system_key] = {
                "success": False,
                "error": str(e)
            }

    return results


def validate_all_outputs(output_dir="fewshot_outputs"):
    """
    Validate all outputs using the validator.

    Args:
        output_dir: Directory containing output files

    Returns:
        Validation results dictionary
    """
    print(f"\n{'='*80}")
    print("VALIDATING OUTPUTS")
    print(f"{'='*80}")

    validator = JSONValidator()
    results = validator.batch_validate(output_dir, SYSTEM_TEMPLATE_MAP)
    validator.print_validation_report(results)

    return results


def generate_summary_report(run_results, validation_results):
    """
    Generate a comprehensive summary report.

    Args:
        run_results: Results from running all systems
        validation_results: Results from validation

    Returns:
        Summary statistics dictionary
    """
    summary = {
        "timestamp": datetime.now().isoformat(),
        "model": MODEL_NAME,
        "parameters": {
            "max_tokens": MAX_TOKENS,
            "temperature": TEMPERATURE,
            "top_p": TOP_P
        },
        "systems_tested": len(run_results),
        "systems_succeeded": sum(1 for r in run_results.values() if r.get("success")),
        "systems_failed": sum(1 for r in run_results.values() if not r.get("success") and not r.get("skipped")),
        "systems_skipped": sum(1 for r in run_results.values() if r.get("skipped")),
        "validation": {
            "total": validation_results.get("total", 0),
            "valid": validation_results.get("valid", 0),
            "invalid": validation_results.get("invalid", 0),
            "success_rate": (validation_results.get("valid", 0) / validation_results.get("total", 1) * 100)
                if validation_results.get("total", 0) > 0 else 0
        },
        "token_usage": {
            "total_input": sum(r.get("usage", {}).get("input_tokens", 0) for r in run_results.values() if r.get("usage")),
            "total_output": sum(r.get("usage", {}).get("output_tokens", 0) for r in run_results.values() if r.get("usage"))
        }
    }

    return summary


def print_summary_report(summary):
    """Print a formatted summary report."""
    print(f"\n{'='*80}")
    print("SUMMARY REPORT")
    print(f"{'='*80}")
    print(f"Timestamp: {summary['timestamp']}")
    print(f"Model: {summary['model']}")
    print(f"\nSystems:")
    print(f"  Tested: {summary['systems_tested']}")
    print(f"  Succeeded: {summary['systems_succeeded']}")
    print(f"  Failed: {summary['systems_failed']}")
    print(f"  Skipped: {summary['systems_skipped']}")
    print(f"\nValidation:")
    print(f"  Total outputs: {summary['validation']['total']}")
    print(f"  Valid: {summary['validation']['valid']}")
    print(f"  Invalid: {summary['validation']['invalid']}")
    print(f"  Success rate: {summary['validation']['success_rate']:.1f}%")
    print(f"\nToken Usage:")
    print(f"  Input tokens: {summary['token_usage']['total_input']}")
    print(f"  Output tokens: {summary['token_usage']['total_output']}")
    print(f"  Total tokens: {summary['token_usage']['total_input'] + summary['token_usage']['total_output']}")
    print(f"{'='*80}\n")


def save_summary_report(summary, output_file="batch_results/summary.json"):
    """Save summary report to JSON file."""
    os.makedirs(os.path.dirname(output_file), exist_ok=True)

    with open(output_file, 'w') as f:
        json.dump(summary, f, indent=2)

    print(f"Summary report saved to: {output_file}")


def main():
    """Main function for batch testing."""
    import argparse

    parser = argparse.ArgumentParser(description="Batch runner for few-shot LLM testing")
    parser.add_argument("--systems", nargs="+", help="Specific systems to run (e.g., 1 6 8)")
    parser.add_argument("--no-skip", action="store_true", help="Don't skip systems with empty test prompts")
    parser.add_argument("--no-validate", action="store_true", help="Skip validation step")
    parser.add_argument("--output-dir", default="fewshot_outputs", help="Output directory")

    args = parser.parse_args()

    # Run all systems
    run_results = run_all_systems(
        systems_to_run=args.systems,
        skip_empty=not args.no_skip
    )

    # Validate outputs
    validation_results = {}
    if not args.no_validate:
        validation_results = validate_all_outputs(args.output_dir)

    # Generate and print summary
    summary = generate_summary_report(run_results, validation_results)
    print_summary_report(summary)

    # Save summary
    save_summary_report(summary)

    # Return success if validation rate > 50%
    if validation_results and validation_results.get("total", 0) > 0:
        success_rate = validation_results.get("valid", 0) / validation_results.get("total", 1) * 100
        if success_rate < 50:
            print(f"\n⚠ Warning: Validation success rate ({success_rate:.1f}%) is below 50%")
            print("Consider improving few-shot examples and prompts.")
            return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())

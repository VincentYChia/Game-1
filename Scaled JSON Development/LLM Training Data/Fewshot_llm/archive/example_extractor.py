"""
Automated Example Extractor for Few-Shot LLM

Extracts high-quality examples from training data, organized by tier.
"""

import json
import os
from pathlib import Path
from collections import defaultdict
from typing import List, Dict, Any


class ExampleExtractor:
    """Extracts examples from training data files."""

    def __init__(self, training_data_dir: str = None):
        """Initialize with training data directory."""
        if training_data_dir is None:
            base_dir = Path(__file__).parent.parent
            training_data_dir = base_dir

        self.training_data_dir = Path(training_data_dir)

    def load_training_data(self, system_folder: str) -> List[Dict[str, Any]]:
        """Load training data from a system folder."""
        folder_path = self.training_data_dir / system_folder
        train_file = folder_path / "train.json"

        if not train_file.exists():
            print(f"Warning: Training file not found: {train_file}")
            return []

        try:
            with open(train_file, 'r') as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading {train_file}: {e}")
            return []

    def extract_by_tier(self, data: List[Dict], max_per_tier: int = 2, max_total: int = 8) -> List[Dict]:
        """
        Extract examples organized by tier.

        Args:
            data: List of training examples
            max_per_tier: Maximum examples per tier
            max_total: Maximum total examples

        Returns:
            List of selected examples
        """
        # Group by tier
        by_tier = defaultdict(list)

        for example in data:
            # Try to find tier in input or output
            tier = None

            if "input" in example and isinstance(example["input"], dict):
                tier = example["input"].get("tier")
                if tier is None and "stationTier" in example["input"]:
                    tier = example["input"]["stationTier"]

            if tier is None and "output" in example and isinstance(example["output"], dict):
                tier = example["output"].get("tier")

            # Default to tier 1 if not found
            if tier is None:
                tier = 1

            by_tier[tier].append(example)

        # Select examples
        selected = []

        # Sort tiers
        for tier in sorted(by_tier.keys()):
            examples = by_tier[tier]
            # Take up to max_per_tier from this tier
            for example in examples[:max_per_tier]:
                if len(selected) < max_total:
                    selected.append(example)

        # If we don't have enough, fill with random examples
        if len(selected) < max_total:
            all_examples = [ex for examples in by_tier.values() for ex in examples]
            for example in all_examples:
                if example not in selected and len(selected) < max_total:
                    selected.append(example)

        return selected[:max_total]

    def format_example(self, example: Dict[str, Any]) -> Dict[str, str]:
        """Format an example for Few_shot_LLM.py."""
        return {
            "input": json.dumps(example.get("input", {}), indent=2),
            "output": json.dumps(example.get("output", {}), indent=2)
        }

    def extract_examples_for_system(self, system_key: str, system_folder: str,
                                   max_per_tier: int = 2, max_total: int = 8) -> List[Dict[str, str]]:
        """
        Extract examples for a specific system.

        Args:
            system_key: System identifier (e.g., "1", "6")
            system_folder: Folder name in training data
            max_per_tier: Maximum examples per tier
            max_total: Maximum total examples

        Returns:
            List of formatted examples
        """
        print(f"Extracting examples for System {system_key} from {system_folder}...")

        data = self.load_training_data(system_folder)

        if not data:
            print(f"  No training data found")
            return []

        selected = self.extract_by_tier(data, max_per_tier, max_total)

        print(f"  Selected {len(selected)} examples")

        return [self.format_example(ex) for ex in selected]

    def generate_all_examples(self) -> Dict[str, List[Dict[str, str]]]:
        """Generate examples for all systems."""

        # System to folder mapping
        system_mapping = {
            "1": "system1_smithing_recipe_to_item",
            "1x2": "system1x2_smithing_placement",
            "2": "system2_refining_recipe_to_material",
            "2x2": "system2x2_refining_placement",
            "3": "system3_alchemy_recipe_to_item",
            "3x2": "system3x2_alchemy_placement",
            "4": "system4_engineering_recipe_to_device",
            "4x2": "system4x2_engineering_placement",
            "5": "system5_enchanting_recipe_to_enchantment",
            "5x2": "system5x2_enchanting_placement",
            "6": "system6_chunk_to_hostile",
            "7": "system7_drop_source_to_material",
            "8": "system8_chunk_to_node",
            "10": "system10_requirements_to_skill",
            "11": "system11_prerequisites_to_title"
        }

        all_examples = {}

        for system_key, folder in system_mapping.items():
            examples = self.extract_examples_for_system(system_key, folder)
            all_examples[system_key] = examples

        return all_examples

    def export_to_python(self, examples: Dict[str, List[Dict[str, str]]], output_file: str = "extracted_examples.py"):
        """Export examples to a Python file that can be imported."""

        with open(output_file, 'w') as f:
            f.write('"""\nAutomatically extracted few-shot examples from training data.\n"""\n\n')
            f.write('EXTRACTED_EXAMPLES = {\n')

            for system_key, system_examples in examples.items():
                f.write(f'    "{system_key}": [\n')

                for i, example in enumerate(system_examples):
                    f.write('        {\n')
                    f.write(f'            "input": """{example["input"]}""",\n')
                    f.write(f'            "output": """{example["output"]}"""\n')
                    f.write('        }')

                    if i < len(system_examples) - 1:
                        f.write(',')
                    f.write('\n')

                f.write('    ],\n')

            f.write('}\n')

        print(f"\nExported examples to: {output_file}")


def main():
    """Main function."""
    import argparse

    parser = argparse.ArgumentParser(description="Extract few-shot examples from training data")
    parser.add_argument("--system", help="Specific system to extract (e.g., 1, 6)")
    parser.add_argument("--max-per-tier", type=int, default=2, help="Max examples per tier")
    parser.add_argument("--max-total", type=int, default=8, help="Max total examples")
    parser.add_argument("--export", action="store_true", help="Export to Python file")

    args = parser.parse_args()

    extractor = ExampleExtractor()

    if args.system:
        # Extract for specific system
        system_mapping = {
            "1": "system1_smithing_recipe_to_item",
            "6": "system6_chunk_to_hostile",
            "8": "system8_chunk_to_node",
            "10": "system10_requirements_to_skill",
            # Add more as needed
        }

        if args.system not in system_mapping:
            print(f"Error: Unknown system '{args.system}'")
            return

        examples = extractor.extract_examples_for_system(
            args.system,
            system_mapping[args.system],
            args.max_per_tier,
            args.max_total
        )

        print(f"\nExtracted {len(examples)} examples for system {args.system}")
        print("\nFirst example:")
        print(examples[0]["input"] if examples else "No examples")
    else:
        # Extract all
        all_examples = extractor.generate_all_examples()

        print(f"\n{'='*80}")
        print("EXTRACTION SUMMARY")
        print(f"{'='*80}")
        for system_key, examples in all_examples.items():
            print(f"System {system_key}: {len(examples)} examples")
        print(f"{'='*80}\n")

        if args.export:
            extractor.export_to_python(all_examples)


if __name__ == "__main__":
    main()

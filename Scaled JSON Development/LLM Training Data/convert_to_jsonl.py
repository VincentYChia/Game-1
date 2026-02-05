"""
Convert Training Data to JSONL Format

Matches indexed recipe inputs (custom_data.json) with synthetic outputs
(Synthetic_outputs/*.json) and creates JSONL for fine-tuning.

Features:
- Reads custom_data files for indexed recipe inputs
- Reads all Synthetic_outputs files for generated item outputs
- Matches by index, handles gaps/missing indices
- Removes rarity field from all disciplines EXCEPT refining
- Creates Together.ai/OpenAI-compatible JSONL

Usage:
    python convert_to_jsonl.py
    (Follow the prompts)

Author: Claude
Created: 2026-02-05
"""

import json
import re
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple


# =============================================================================
# SYSTEM PROMPTS BY DISCIPLINE
# =============================================================================

SYSTEM_PROMPTS = {
    'smithing': """You are a crafting assistant for a fantasy RPG. Given a smithing recipe with materials and grid positions, generate the resulting item as JSON. Consider material tiers (T1-T4), tags, and properties.""",

    'adornment': """You are a crafting assistant for a fantasy RPG. Given an adornment recipe with materials, generate the resulting accessory/enchantment as JSON. Consider magical properties and tiers.""",

    'refining': """You are a crafting assistant for a fantasy RPG. Given a refining recipe, generate the resulting refined material as JSON. Rarity depends on input quality and process.""",

    'alchemy': """You are a crafting assistant for a fantasy RPG. Given an alchemy recipe with ingredients, generate the resulting potion/consumable as JSON. Consider ingredient properties and tiers.""",

    'engineering': """You are a crafting assistant for a fantasy RPG. Given an engineering recipe with components, generate the resulting device as JSON. Consider component types and tiers.""",
}


# =============================================================================
# DATA PROCESSING
# =============================================================================

def remove_rarity_recursive(obj: Any, discipline: str) -> Any:
    """Remove rarity field from object unless it's refining discipline."""
    if discipline == 'refining':
        return obj

    if isinstance(obj, dict):
        return {k: remove_rarity_recursive(v, discipline)
                for k, v in obj.items() if k != 'rarity'}
    elif isinstance(obj, list):
        return [remove_rarity_recursive(item, discipline) for item in obj]
    return obj


def format_recipe_as_text(recipe_data: Dict, discipline: str) -> str:
    """Format the recipe data as readable text for the user message."""
    recipe = recipe_data.get('recipe', {})

    lines = [f"Recipe: {recipe.get('recipeId', 'unknown')}"]
    lines.append(f"Station: {recipe.get('stationType', discipline)} (Tier {recipe.get('stationTier', 1)})")

    if recipe.get('gridSize'):
        lines.append(f"Grid: {recipe['gridSize']}")

    lines.append("")
    lines.append("Materials:")

    inputs = recipe.get('inputs', [])
    for inp in inputs:
        mat_id = inp.get('materialId', 'unknown')
        qty = inp.get('quantity', 1)
        pos = inp.get('position', '')
        meta = inp.get('material_metadata', {})

        mat_name = meta.get('name', mat_id)
        tier = meta.get('tier', 1)
        tags = meta.get('tags', [])

        line = f"  - {mat_name} x{qty} (Tier {tier})"
        if pos:
            line += f" at {pos}"
        if tags:
            line += f" [{', '.join(tags[:3])}]"
        lines.append(line)

    # Add narrative if present
    narrative = meta.get('narrative') if inputs else None
    if not narrative:
        narrative = recipe.get('narrative')
    if narrative:
        lines.append(f"\nContext: {narrative}")

    return "\n".join(lines)


def load_custom_data(filepath: Path) -> Tuple[str, Dict[int, Dict]]:
    """Load custom_data.json and return discipline and indexed entries."""
    with open(filepath, 'r', encoding='utf-8') as f:
        data = json.load(f)

    discipline = data.get('metadata', {}).get('discipline', 'unknown')

    # Build index -> entry map
    indexed = {}
    for entry in data.get('training_data', []):
        idx = entry.get('index')
        if idx is not None:
            indexed[idx] = entry

    return discipline, indexed


def load_synthetic_outputs(synthetic_dir: Path, discipline: str) -> Dict[int, Dict]:
    """Load all synthetic output files for a discipline and return indexed outputs."""
    indexed = {}

    # Find all files matching pattern: {discipline}_*.json
    pattern = f"{discipline}_*.json"
    files = list(synthetic_dir.glob(pattern))

    if not files:
        return indexed

    for filepath in sorted(files):
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)

            outputs = data.get('training_outputs', [])
            for entry in outputs:
                idx = entry.get('index')
                if idx is not None:
                    indexed[idx] = entry.get('output', {})
        except Exception as e:
            print(f"  Warning: Error reading {filepath.name}: {e}")

    return indexed


def create_jsonl_entry(input_data: Dict, output_data: Dict, discipline: str) -> Dict:
    """Create a single JSONL entry with messages array."""
    # Remove rarity from output unless refining
    cleaned_output = remove_rarity_recursive(output_data, discipline)

    messages = [
        {
            "role": "system",
            "content": SYSTEM_PROMPTS.get(discipline, SYSTEM_PROMPTS['smithing'])
        },
        {
            "role": "user",
            "content": format_recipe_as_text(input_data, discipline)
        },
        {
            "role": "assistant",
            "content": json.dumps(cleaned_output, indent=2)
        }
    ]

    return {"messages": messages}


def process_discipline(input_file: Path, synthetic_dir: Path, output_dir: Path) -> Tuple[int, int, int]:
    """Process a single discipline, matching inputs with outputs."""

    # Load input data
    discipline, inputs = load_custom_data(input_file)
    print(f"\n{discipline.upper()}:")
    print(f"  Loaded {len(inputs)} indexed inputs from {input_file.name}")

    # Load synthetic outputs
    outputs = load_synthetic_outputs(synthetic_dir, discipline)
    print(f"  Loaded {len(outputs)} synthetic outputs")

    if not outputs:
        print(f"  No synthetic outputs found for {discipline}")
        return 0, len(inputs), 0

    # Match and create JSONL entries
    matched = []
    missing_outputs = []

    for idx in sorted(inputs.keys()):
        if idx in outputs:
            entry = create_jsonl_entry(inputs[idx], outputs[idx], discipline)
            matched.append(entry)
        else:
            missing_outputs.append(idx)

    # Write JSONL
    if matched:
        output_file = output_dir / f"{discipline}_training.jsonl"
        with open(output_file, 'w', encoding='utf-8') as f:
            for entry in matched:
                f.write(json.dumps(entry) + '\n')
        print(f"  Created {output_file.name} with {len(matched)} entries")

    if missing_outputs:
        # Show ranges of missing indices
        ranges = []
        start = missing_outputs[0]
        end = start
        for idx in missing_outputs[1:]:
            if idx == end + 1:
                end = idx
            else:
                ranges.append(f"{start}-{end}" if start != end else str(start))
                start = end = idx
        ranges.append(f"{start}-{end}" if start != end else str(start))

        if len(ranges) <= 5:
            print(f"  Missing outputs for indices: {', '.join(ranges)}")
        else:
            print(f"  Missing outputs for {len(missing_outputs)} indices ({ranges[0]} ... {ranges[-1]})")

    return len(matched), len(missing_outputs), len(outputs)


def main():
    """Interactive main."""
    print("=" * 60)
    print("JSONL CONVERTER - Match Inputs with Synthetic Outputs")
    print("=" * 60)

    # Find directories
    script_dir = Path(__file__).parent
    training_outputs_dir = script_dir / "training_outputs"
    synthetic_dir = training_outputs_dir / "Synthetic_outputs"

    print(f"\nLooking in: {training_outputs_dir}")

    if not training_outputs_dir.exists():
        print(f"\nError: training_outputs directory not found")
        input("\nPress Enter to exit...")
        return

    # Find custom_data files
    custom_files = list(training_outputs_dir.glob("*_custom_data.json"))

    if not custom_files:
        print(f"\nNo *_custom_data.json files found")
        input("\nPress Enter to exit...")
        return

    # Show available files
    print(f"\nFound {len(custom_files)} input file(s):")
    print("-" * 50)
    for i, f in enumerate(custom_files, 1):
        try:
            with open(f, 'r') as fp:
                data = json.load(fp)
                count = len(data.get('training_data', []))
                discipline = data.get('metadata', {}).get('discipline', '?')
        except:
            count = '?'
            discipline = '?'
        print(f"  {i}. {f.name} [{discipline}] ({count} entries)")
    print(f"  {len(custom_files) + 1}. All files")

    # Check for synthetic outputs
    if not synthetic_dir.exists():
        print(f"\nWarning: Synthetic_outputs folder not found at {synthetic_dir}")
        print("No outputs to match with.")
        input("\nPress Enter to exit...")
        return

    synthetic_files = list(synthetic_dir.glob("*.json"))
    print(f"\nFound {len(synthetic_files)} synthetic output file(s) in Synthetic_outputs/")

    # Select file(s)
    print()
    selection = input(f"Select input file (1-{len(custom_files) + 1}): ").strip()

    try:
        sel_num = int(selection)
    except ValueError:
        print("Invalid selection.")
        input("\nPress Enter to exit...")
        return

    if sel_num < 1 or sel_num > len(custom_files) + 1:
        print("Invalid selection.")
        input("\nPress Enter to exit...")
        return

    # Output directory
    output_dir = script_dir / "jsonl_outputs"
    output_dir.mkdir(exist_ok=True)

    # Process
    total_matched = 0
    total_missing = 0

    if sel_num == len(custom_files) + 1:
        files_to_process = custom_files
    else:
        files_to_process = [custom_files[sel_num - 1]]

    for input_file in files_to_process:
        matched, missing, _ = process_discipline(input_file, synthetic_dir, output_dir)
        total_matched += matched
        total_missing += missing

    print("\n" + "=" * 60)
    print(f"COMPLETE")
    print(f"  Matched: {total_matched} entries")
    print(f"  Missing outputs: {total_missing} entries")
    print(f"  Output folder: {output_dir}")
    print("=" * 60)

    input("\nPress Enter to exit...")


if __name__ == "__main__":
    main()

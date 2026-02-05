"""
Convert Training Data to JSONL Format

Takes system training data (system1_smithing, system2_refining, etc.) and converts
to Together.ai/OpenAI-compatible JSONL format for fine-tuning.

Features:
- Reads from system folders with input/output format
- Converts to JSONL with messages array (system/user/assistant)
- Removes rarity field from all disciplines EXCEPT refining
- Handles missing indices and malformed data gracefully
- Interactive mode - just run the script

Usage:
    python convert_to_jsonl.py
    (Follow the prompts)

Author: Claude
Created: 2026-02-05
"""

import json
from pathlib import Path
from typing import Dict, List, Any


# =============================================================================
# SYSTEM PROMPTS BY DISCIPLINE
# =============================================================================

SYSTEM_PROMPTS = {
    'smithing': """You are a crafting assistant for a fantasy RPG. Given a smithing recipe with materials, generate the resulting item as JSON. Consider material tiers (T1-T4), tags, and properties.""",

    'refining': """You are a crafting assistant for a fantasy RPG. Given a refining recipe, generate the resulting refined material as JSON. Rarity depends on input quality and process.""",

    'alchemy': """You are a crafting assistant for a fantasy RPG. Given an alchemy recipe with ingredients, generate the resulting potion/consumable as JSON. Consider ingredient properties and tiers.""",

    'engineering': """You are a crafting assistant for a fantasy RPG. Given an engineering recipe with components, generate the resulting device as JSON. Consider component types and tiers.""",

    'enchanting': """You are a crafting assistant for a fantasy RPG. Given an enchanting recipe, generate the resulting enchantment as JSON. Consider magical properties and material tiers.""",
}

# Map folder names to disciplines
FOLDER_TO_DISCIPLINE = {
    'system1_smithing_recipe_to_item': 'smithing',
    'system2_refining_recipe_to_material': 'refining',
    'system3_alchemy_recipe_to_item': 'alchemy',
    'system4_engineering_recipe_to_device': 'engineering',
    'system5_enchanting_recipe_to_enchantment': 'enchanting',
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


def format_input_as_text(input_data: Dict, discipline: str) -> str:
    """Format the input recipe data as readable text for the user message."""
    lines = [f"Recipe: {input_data.get('recipeId', 'unknown')}"]
    lines.append(f"Station: {input_data.get('stationType', discipline)} (Tier {input_data.get('stationTier', 1)})")

    # Add narrative if present
    if input_data.get('narrative'):
        lines.append(f"Context: {input_data['narrative']}")

    lines.append("")
    lines.append("Materials:")

    inputs = input_data.get('inputs', [])
    for inp in inputs:
        mat_id = inp.get('materialId', 'unknown')
        qty = inp.get('quantity', 1)
        meta = inp.get('material_metadata', {})

        mat_name = meta.get('name', mat_id)
        tier = meta.get('tier', 1)
        tags = meta.get('tags', [])

        line = f"  - {mat_name} x{qty} (Tier {tier})"
        if tags:
            line += f" [{', '.join(tags[:3])}]"
        lines.append(line)

    return "\n".join(lines)


def convert_entry_to_jsonl(entry: Dict, discipline: str) -> Dict:
    """Convert a single input/output entry to JSONL messages format."""
    input_data = entry.get('input', {})
    output_data = entry.get('output', {})

    # Remove rarity from output unless refining
    cleaned_output = remove_rarity_recursive(output_data, discipline)

    # Build messages array
    messages = [
        {
            "role": "system",
            "content": SYSTEM_PROMPTS.get(discipline, SYSTEM_PROMPTS['smithing'])
        },
        {
            "role": "user",
            "content": format_input_as_text(input_data, discipline)
        },
        {
            "role": "assistant",
            "content": json.dumps(cleaned_output, indent=2)
        }
    ]

    return {"messages": messages}


def convert_file(input_path: Path, output_path: Path, discipline: str) -> int:
    """Convert a JSON file to JSONL format."""
    try:
        with open(input_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        print(f"  ERROR: Invalid JSON in {input_path.name}: {e}")
        return 0
    except Exception as e:
        print(f"  ERROR reading {input_path.name}: {e}")
        return 0

    if not isinstance(data, list):
        print(f"  ERROR: Expected list, got {type(data).__name__}")
        return 0

    # Convert each entry
    converted = []
    skipped = 0

    for i, entry in enumerate(data):
        # Validate entry has required structure
        if not isinstance(entry, dict):
            skipped += 1
            continue

        if 'input' not in entry or 'output' not in entry:
            skipped += 1
            continue

        try:
            jsonl_entry = convert_entry_to_jsonl(entry, discipline)
            converted.append(jsonl_entry)
        except Exception as e:
            print(f"    Warning: Skipped entry {i}: {e}")
            skipped += 1

    if not converted:
        print(f"  No valid entries to convert")
        return 0

    # Write JSONL
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        for entry in converted:
            f.write(json.dumps(entry) + '\n')

    if skipped > 0:
        print(f"  Converted {len(converted)} entries (skipped {skipped}) -> {output_path.name}")
    else:
        print(f"  Converted {len(converted)} entries -> {output_path.name}")

    return len(converted)


def find_system_folders(base_dir: Path) -> List[tuple]:
    """Find all system folders and their disciplines."""
    folders = []

    for folder_name, discipline in FOLDER_TO_DISCIPLINE.items():
        folder_path = base_dir / folder_name
        if folder_path.exists() and folder_path.is_dir():
            folders.append((folder_path, discipline, folder_name))

    return folders


def main():
    """Interactive main - just run the script."""
    print("=" * 60)
    print("JSONL CONVERTER FOR TRAINING DATA")
    print("=" * 60)

    # Find script directory
    script_dir = Path(__file__).parent
    print(f"\nLooking in: {script_dir}")

    # Find system folders
    system_folders = find_system_folders(script_dir)

    if not system_folders:
        print("\nNo system folders found (system1_*, system2_*, etc.)")
        print("Make sure training data folders exist.")
        input("\nPress Enter to exit...")
        return

    # Show available folders
    print(f"\nFound {len(system_folders)} system folder(s):")
    print("-" * 50)
    for i, (folder, discipline, name) in enumerate(system_folders, 1):
        # Count entries in full_dataset.json
        full_path = folder / "full_dataset.json"
        try:
            with open(full_path, 'r') as f:
                count = len(json.load(f))
        except:
            count = '?'
        print(f"  {i}. {name} [{discipline}] ({count} entries)")
    print(f"  {len(system_folders) + 1}. All folders")

    # Select folder(s)
    print()
    selection = input(f"Select folder (1-{len(system_folders) + 1}): ").strip()

    try:
        sel_num = int(selection)
    except ValueError:
        print("Invalid selection.")
        input("\nPress Enter to exit...")
        return

    if sel_num < 1 or sel_num > len(system_folders) + 1:
        print("Invalid selection.")
        input("\nPress Enter to exit...")
        return

    # Choose which file to convert
    print("\nWhich dataset to convert?")
    print("  1. full_dataset.json")
    print("  2. train.json")
    print("  3. val.json")
    print("  4. All (full, train, val)")

    file_choice = input("\nSelect (1-4, default 1): ").strip() or "1"

    file_map = {
        "1": ["full_dataset.json"],
        "2": ["train.json"],
        "3": ["val.json"],
        "4": ["full_dataset.json", "train.json", "val.json"]
    }
    files_to_convert = file_map.get(file_choice, ["full_dataset.json"])

    # Output directory
    output_dir = script_dir / "jsonl_outputs"
    output_dir.mkdir(exist_ok=True)

    # Process
    total_entries = 0

    if sel_num == len(system_folders) + 1:
        # All folders
        print(f"\nConverting all folders...")
        folders_to_process = system_folders
    else:
        folders_to_process = [system_folders[sel_num - 1]]

    for folder, discipline, folder_name in folders_to_process:
        print(f"\n{discipline.upper()} ({folder_name}):")

        for filename in files_to_convert:
            input_path = folder / filename
            if not input_path.exists():
                print(f"  {filename} not found, skipping")
                continue

            # Output: jsonl_outputs/{discipline}_{filename}.jsonl
            output_name = f"{discipline}_{filename.replace('.json', '.jsonl')}"
            output_path = output_dir / output_name

            count = convert_file(input_path, output_path, discipline)
            total_entries += count

    print("\n" + "=" * 60)
    print(f"COMPLETE: Converted {total_entries} total entries")
    print(f"Output folder: {output_dir}")
    print("=" * 60)

    input("\nPress Enter to exit...")


if __name__ == "__main__":
    main()

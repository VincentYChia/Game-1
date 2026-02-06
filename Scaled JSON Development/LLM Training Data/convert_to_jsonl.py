"""
Convert Training Data to JSONL Format

Matches indexed recipe inputs (custom_data.json) with synthetic outputs
(Synthetic_outputs/*.json) and creates JSONL for fine-tuning.

Features:
- Reads custom_data files for indexed recipe inputs
- Reads all Synthetic_outputs files for generated item outputs
- ROBUST PARSING: Handles multiple JSON format variations:
  * Raw arrays, objects with various array keys
  * Truncated files, missing array brackets
  * Various item wrapper formats (output, item, direct)
  * Subfolders per discipline
- Matches by index, handles gaps/missing indices
- Removes rarity field from all disciplines EXCEPT refining
- Loads system prompts from external text files
- Creates 80/20 train/validation split with random shuffling
- VLM FORMAT: Smithing & Adornment include image_base64 in multimodal format
- LLM FORMAT: Alchemy, Refining, Engineering use text-only format
- Creates Together.ai/OpenAI-compatible JSONL

Output files (12 total):
- train.jsonl, validation.jsonl (combined)
- {discipline}_train.jsonl, {discipline}_validation.jsonl (per-discipline)

Usage:
    python convert_to_jsonl.py
    (Follow the prompts)

Author: Claude
Created: 2026-02-05
Updated: 2026-02-06 (Added VLM multimodal format for vision disciplines)
"""

import json
import random
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass


# =============================================================================
# ROBUST JSON PARSING
# =============================================================================

@dataclass
class ParseResult:
    """Result of parsing a synthetic output file."""
    success: bool
    items: List[Dict]
    strategy: str
    error: Optional[str] = None


def robust_json_load(filepath: Path) -> ParseResult:
    """
    Load JSON file with multiple fallback strategies for malformed files.

    Strategies:
    1. Direct parse
    2. Wrap in array brackets (for missing [ ])
    3. Fix truncated files (add ]})
    """
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception as e:
        return ParseResult(False, [], "read_error", str(e))

    # Strategy 1: Direct parse
    try:
        data = json.loads(content)
        return ParseResult(True, [data] if isinstance(data, dict) else data, "direct")
    except json.JSONDecodeError:
        pass

    # Strategy 2: Wrap in array brackets (handles missing [ ])
    try:
        wrapped = "[" + content.strip().rstrip(',') + "]"
        data = json.loads(wrapped)
        return ParseResult(True, data, "wrapped_array")
    except json.JSONDecodeError:
        pass

    # Strategy 3: Fix truncated files (missing ]} at end)
    try:
        fixed = content.rstrip() + "]\n}"
        data = json.loads(fixed)
        return ParseResult(True, [data], "fixed_truncated")
    except json.JSONDecodeError:
        pass

    # Strategy 4: Try adding just ] for truncated arrays
    try:
        fixed = content.rstrip() + "\n]"
        data = json.loads(fixed)
        return ParseResult(True, data, "fixed_array_truncated")
    except json.JSONDecodeError:
        pass

    return ParseResult(False, [], "all_strategies_failed", "Could not parse JSON with any strategy")


def extract_items_array(data: Any) -> Tuple[List[Dict], str]:
    """
    Extract the items array from various format structures.

    Handles:
    - Raw arrays
    - Objects with 'training_outputs', 'items', 'enchantments', 'recipes' keys
    - 'final_item' special field appended to items
    """
    if isinstance(data, list):
        return data, "raw_array"

    if isinstance(data, dict):
        # Try various array keys in order of likelihood
        array_keys = ['training_outputs', 'items', 'enchantments', 'recipes']

        for key in array_keys:
            if key in data and isinstance(data[key], list):
                items = data[key]
                # Check for final_item special case (alchemy_450-500)
                if 'final_item' in data and isinstance(data['final_item'], dict):
                    items = items + [data['final_item']]
                return items, f"dict[{key}]"

        # If it's a single item dict (might be wrapped)
        if 'index' in data:
            return [data], "single_item"

    return [], "unknown_format"


def extract_item_content(item: Dict) -> Tuple[Optional[Dict], str]:
    """
    Extract the actual item content from various wrapper formats.

    Handles:
    - 'output' wrapper (some smithing files)
    - 'item' wrapper (some smithing files)
    - Direct content (most files)
    - Input data detection (has 'recipe', 'image_base64' = NOT output)
    """
    # Check if this is INPUT data accidentally in outputs folder
    if 'recipe' in item and 'image_base64' in item:
        return None, "input_data_not_output"

    # Check for wrappers
    if 'output' in item and isinstance(item['output'], dict):
        return item['output'], "output_wrapper"

    if 'item' in item and isinstance(item['item'], dict):
        return item['item'], "item_wrapper"

    # Direct content - check for item indicators
    item_indicators = ['itemId', 'enchantmentId', 'name', 'category', 'tier']
    if any(key in item for key in item_indicators):
        return item, "direct"

    # Unknown format but return anyway
    return item, "unknown"


def parse_synthetic_file(filepath: Path) -> Tuple[Dict[int, Dict], List[str]]:
    """
    Parse a synthetic output file and return indexed items.

    Returns:
        Tuple of (indexed_items, warnings)
    """
    warnings = []
    indexed = {}

    # Load file
    result = robust_json_load(filepath)
    if not result.success:
        warnings.append(f"Parse failed ({result.strategy}): {result.error}")
        return indexed, warnings

    if result.strategy != "direct":
        warnings.append(f"Used fallback strategy: {result.strategy}")

    # Extract items array from the parsed data
    # Handle case where robust_json_load returns a list (from wrapped_array strategy)
    if isinstance(result.items, list) and len(result.items) == 1 and isinstance(result.items[0], dict):
        items, array_format = extract_items_array(result.items[0])
    elif isinstance(result.items, list) and len(result.items) > 1:
        # Already a list of items from wrapped_array
        items = result.items
        array_format = "raw_array"
    else:
        items = result.items
        array_format = "direct"

    if not items:
        warnings.append(f"No items found (format: {array_format})")
        return indexed, warnings

    # Process each item
    input_data_count = 0
    for item in items:
        if not isinstance(item, dict):
            continue

        # Get index
        idx = item.get('index')
        if idx is None:
            continue

        # Extract actual content
        content, wrapper_format = extract_item_content(item)

        if content is None:
            if wrapper_format == "input_data_not_output":
                input_data_count += 1
            continue

        indexed[idx] = content

    if input_data_count > 0:
        warnings.append(f"Skipped {input_data_count} entries (input data, not outputs)")

    return indexed, warnings


# =============================================================================
# SYSTEM PROMPTS
# =============================================================================

# Default prompts (used if external file not found)
DEFAULT_SYSTEM_PROMPTS = {
    'smithing': """You are a crafting assistant for a fantasy RPG. Given a smithing recipe with materials and grid positions, generate the resulting item as JSON. Consider material tiers (T1-T4), tags, and properties.""",
    'adornment': """You are a crafting assistant for a fantasy RPG. Given an adornment recipe with materials, generate the resulting enchantment as JSON. Consider magical properties and tiers.""",
    'refining': """You are a crafting assistant for a fantasy RPG. Given a refining recipe, generate the resulting refined material as JSON. Rarity depends on input quality and process.""",
    'alchemy': """You are a crafting assistant for a fantasy RPG. Given an alchemy recipe with ingredients, generate the resulting potion/consumable as JSON. Consider ingredient properties and tiers.""",
    'engineering': """You are a crafting assistant for a fantasy RPG. Given an engineering recipe with components, generate the resulting device as JSON. Consider component types and tiers.""",
}

# Cache for loaded prompts
_loaded_prompts: Dict[str, str] = {}


def load_system_prompt(discipline: str, prompts_dir: Optional[Path] = None) -> str:
    """
    Load system prompt from external file or use default.

    Looks for: {prompts_dir}/{discipline}.txt
    Falls back to DEFAULT_SYSTEM_PROMPTS if file not found.
    """
    # Check cache first
    cache_key = f"{prompts_dir}:{discipline}" if prompts_dir else discipline
    if cache_key in _loaded_prompts:
        return _loaded_prompts[cache_key]

    prompt = None

    # Try loading from file
    if prompts_dir:
        prompt_file = prompts_dir / f"{discipline}.txt"
        if prompt_file.exists():
            try:
                prompt = prompt_file.read_text(encoding='utf-8').strip()
            except Exception:
                pass

    # Fall back to default
    if not prompt:
        prompt = DEFAULT_SYSTEM_PROMPTS.get(discipline, DEFAULT_SYSTEM_PROMPTS['smithing'])

    _loaded_prompts[cache_key] = prompt
    return prompt


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


def load_synthetic_outputs(synthetic_dir: Path, discipline: str) -> Tuple[Dict[int, Dict], List[str]]:
    """
    Load all synthetic output files for a discipline and return indexed outputs.

    Searches in:
    - synthetic_dir/{discipline}_*.json
    - synthetic_dir/{discipline}/{discipline}_*.json (subfolder)
    - synthetic_dir/{discipline}/*.json (any file in subfolder)

    Returns:
        Tuple of (indexed_outputs, all_warnings)
    """
    indexed = {}
    all_warnings = []

    # Collect all potential files
    files = []

    # Pattern 1: Direct files in synthetic_dir
    pattern1 = f"{discipline}_*.json"
    files.extend(synthetic_dir.glob(pattern1))

    # Pattern 2: Files in discipline subfolder
    subfolder = synthetic_dir / discipline
    if subfolder.exists():
        # Match both {discipline}_*.json and *.json in subfolder
        files.extend(subfolder.glob(f"{discipline}_*.json"))
        # Also match files with typos (like "adornemnt_82-119.json")
        files.extend(subfolder.glob("*.json"))

    # Remove duplicates while preserving order
    seen = set()
    unique_files = []
    for f in files:
        if f not in seen:
            seen.add(f)
            unique_files.append(f)

    if not unique_files:
        return indexed, [f"No files found for {discipline}"]

    # Process each file
    for filepath in sorted(unique_files):
        file_items, warnings = parse_synthetic_file(filepath)

        # Add file context to warnings
        if warnings:
            for w in warnings:
                all_warnings.append(f"{filepath.name}: {w}")

        # Merge items (later files can override earlier)
        for idx, content in file_items.items():
            indexed[idx] = content

    return indexed, all_warnings


# Disciplines that use VLM (Vision Language Model) format with images
VLM_DISCIPLINES = {'smithing', 'adornment'}


def create_jsonl_entry(input_data: Dict, output_data: Dict, discipline: str,
                       prompts_dir: Optional[Path] = None) -> Dict:
    """
    Create a single JSONL entry with messages array.

    For VLM disciplines (smithing, adornment): Uses multimodal format with image
    For LLM disciplines (alchemy, refining, engineering): Uses text-only format
    """
    # Remove rarity from output unless refining
    cleaned_output = remove_rarity_recursive(output_data, discipline)

    # Format recipe text
    recipe_text = format_recipe_as_text(input_data, discipline)

    # Check if this is a VLM discipline with an image
    image_base64 = input_data.get('image_base64')
    is_vlm = discipline in VLM_DISCIPLINES and image_base64

    # Build user content based on format
    if is_vlm:
        # VLM format: multimodal content with image and text
        # Together.ai expects data URL format for base64 images
        if not image_base64.startswith('data:'):
            image_url = f"data:image/png;base64,{image_base64}"
        else:
            image_url = image_base64

        user_content = [
            {
                "type": "image_url",
                "image_url": {"url": image_url}
            },
            {
                "type": "text",
                "text": recipe_text
            }
        ]
    else:
        # LLM format: text-only content
        user_content = recipe_text

    messages = [
        {
            "role": "system",
            "content": load_system_prompt(discipline, prompts_dir)
        },
        {
            "role": "user",
            "content": user_content
        },
        {
            "role": "assistant",
            "content": json.dumps(cleaned_output, indent=2)
        }
    ]

    return {"messages": messages}


def process_discipline(input_file: Path, synthetic_dir: Path,
                       prompts_dir: Optional[Path] = None,
                       verbose: bool = True) -> Tuple[str, List[Dict], int, int]:
    """
    Process a single discipline, matching inputs with outputs.

    Returns:
        Tuple of (discipline_name, matched_entries, missing_count, vlm_count)
    """
    # Load input data
    discipline, inputs = load_custom_data(input_file)
    print(f"\n{discipline.upper()}:")
    print(f"  Loaded {len(inputs)} indexed inputs from {input_file.name}")

    # Count entries with images (for VLM stats)
    entries_with_images = sum(1 for entry in inputs.values() if entry.get('image_base64'))
    if discipline in VLM_DISCIPLINES:
        print(f"  Entries with images: {entries_with_images}/{len(inputs)}")

    # Load synthetic outputs (now returns warnings too)
    outputs, warnings = load_synthetic_outputs(synthetic_dir, discipline)
    print(f"  Loaded {len(outputs)} synthetic outputs")

    # Show warnings if verbose
    if verbose and warnings:
        print(f"  Parsing notes ({len(warnings)}):")
        for w in warnings[:10]:  # Limit to first 10
            print(f"    - {w}")
        if len(warnings) > 10:
            print(f"    ... and {len(warnings) - 10} more")

    if not outputs:
        print(f"  No synthetic outputs found for {discipline}")
        return discipline, [], len(inputs), 0

    # Match and create JSONL entries
    matched = []
    missing_outputs = []
    vlm_count = 0

    for idx in sorted(inputs.keys()):
        if idx in outputs:
            entry = create_jsonl_entry(inputs[idx], outputs[idx], discipline, prompts_dir)
            matched.append(entry)
            # Count VLM entries (those with multimodal user content)
            user_content = entry['messages'][1]['content']
            if isinstance(user_content, list):
                vlm_count += 1
        else:
            missing_outputs.append(idx)

    print(f"  Matched: {len(matched)} entries")
    if discipline in VLM_DISCIPLINES:
        print(f"  VLM (with image): {vlm_count}, LLM (text-only): {len(matched) - vlm_count}")

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

    return discipline, matched, len(missing_outputs), vlm_count


def train_validation_split(entries: List[Dict], train_ratio: float = 0.8,
                           seed: Optional[int] = None) -> Tuple[List[Dict], List[Dict]]:
    """
    Split entries into train and validation sets with random shuffling.

    Args:
        entries: List of JSONL entries
        train_ratio: Fraction for training (default 0.8 = 80%)
        seed: Random seed for reproducibility (None for random)

    Returns:
        Tuple of (train_entries, validation_entries)
    """
    if seed is not None:
        random.seed(seed)

    # Shuffle a copy
    shuffled = entries.copy()
    random.shuffle(shuffled)

    # Split
    split_idx = int(len(shuffled) * train_ratio)
    train_entries = shuffled[:split_idx]
    val_entries = shuffled[split_idx:]

    return train_entries, val_entries


def write_jsonl(entries: List[Dict], filepath: Path) -> None:
    """Write entries to JSONL file."""
    with open(filepath, 'w', encoding='utf-8') as f:
        for entry in entries:
            f.write(json.dumps(entry) + '\n')


def main():
    """Interactive main with train/validation split."""
    print("=" * 60)
    print("JSONL CONVERTER - Match Inputs with Synthetic Outputs")
    print("=" * 60)

    # Find directories
    script_dir = Path(__file__).parent
    training_dir = script_dir / "Synthetic_Training"
    synthetic_dir = training_dir / "Synthetic_outputs"
    prompts_dir = training_dir / "system_prompts"

    print(f"\nLooking in: {training_dir}")

    if not training_dir.exists():
        print(f"\nError: Synthetic_Training directory not found")
        input("\nPress Enter to exit...")
        return

    # Find custom_data files
    custom_files = list(training_dir.glob("*_custom_data.json"))

    if not custom_files:
        print(f"\nNo *_custom_data.json files found")
        input("\nPress Enter to exit...")
        return

    # Show available files
    print(f"\nFound {len(custom_files)} input file(s):")
    print("-" * 50)
    for i, f in enumerate(sorted(custom_files), 1):
        try:
            with open(f, 'r') as fp:
                data = json.load(fp)
                count = len(data.get('training_data', []))
                discipline = data.get('metadata', {}).get('discipline', '?')
        except:
            count = '?'
            discipline = '?'
        print(f"  {i}. {f.name} [{discipline}] ({count} entries)")
    print(f"  {len(custom_files) + 1}. All files (recommended)")

    # Check for synthetic outputs
    if not synthetic_dir.exists():
        print(f"\nWarning: Synthetic_outputs folder not found at {synthetic_dir}")
        print("No outputs to match with.")
        input("\nPress Enter to exit...")
        return

    # Count all synthetic files including subfolders
    synthetic_files = list(synthetic_dir.glob("*.json"))
    synthetic_files.extend(synthetic_dir.glob("*/*.json"))
    print(f"\nFound {len(synthetic_files)} synthetic output file(s) in Synthetic_outputs/")

    # Show breakdown by subfolder
    subfolders = [d for d in synthetic_dir.iterdir() if d.is_dir()]
    if subfolders:
        print("  Subfolders:")
        for sf in sorted(subfolders):
            sf_count = len(list(sf.glob("*.json")))
            print(f"    - {sf.name}/: {sf_count} files")

    # Check for system prompts
    if prompts_dir.exists():
        prompt_files = list(prompts_dir.glob("*.txt"))
        print(f"\nSystem prompts: {prompts_dir}")
        for pf in sorted(prompt_files):
            print(f"  - {pf.name}")
    else:
        print(f"\nNote: No system_prompts folder found, using defaults")
        prompts_dir = None

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

    # Process all selected files and collect entries BY DISCIPLINE
    all_entries = []
    total_missing = 0
    total_vlm = 0
    discipline_entries = {}  # discipline -> list of entries
    discipline_vlm_counts = {}  # discipline -> vlm count

    if sel_num == len(custom_files) + 1:
        files_to_process = sorted(custom_files)
    else:
        files_to_process = [sorted(custom_files)[sel_num - 1]]

    print("\n" + "-" * 60)
    print("PROCESSING")
    print("-" * 60)

    for input_file in files_to_process:
        discipline, matched, missing, vlm_count = process_discipline(
            input_file, synthetic_dir, prompts_dir, verbose=True
        )
        all_entries.extend(matched)
        total_missing += missing
        total_vlm += vlm_count
        discipline_entries[discipline] = matched
        discipline_vlm_counts[discipline] = vlm_count

    # Train/Validation split
    print("\n" + "-" * 60)
    print("TRAIN/VALIDATION SPLIT (80/20)")
    print("-" * 60)

    train_ratio = 0.8
    seed = 42  # Fixed seed for reproducibility

    # Split combined dataset
    train_all, val_all = train_validation_split(all_entries, train_ratio, seed)

    print(f"\nCombined (all disciplines):")
    print(f"  Total: {len(all_entries)}")
    print(f"  Train: {len(train_all)} ({train_ratio*100:.0f}%)")
    print(f"  Validation: {len(val_all)} ({(1-train_ratio)*100:.0f}%)")

    # Split each discipline separately
    discipline_splits = {}
    for discipline, entries in discipline_entries.items():
        train_disc, val_disc = train_validation_split(entries, train_ratio, seed)
        discipline_splits[discipline] = (train_disc, val_disc)
        print(f"\n{discipline.capitalize()}:")
        print(f"  Total: {len(entries)}")
        print(f"  Train: {len(train_disc)}")
        print(f"  Validation: {len(val_disc)}")

    # Write output files
    print("\n" + "-" * 60)
    print("WRITING OUTPUT FILES")
    print("-" * 60)

    files_written = []

    # Combined files
    train_file = output_dir / "train.jsonl"
    val_file = output_dir / "validation.jsonl"
    write_jsonl(train_all, train_file)
    write_jsonl(val_all, val_file)
    files_written.append((train_file.name, len(train_all), "combined train"))
    files_written.append((val_file.name, len(val_all), "combined validation"))

    # Per-discipline files
    for discipline, (train_disc, val_disc) in discipline_splits.items():
        train_disc_file = output_dir / f"{discipline}_train.jsonl"
        val_disc_file = output_dir / f"{discipline}_validation.jsonl"
        write_jsonl(train_disc, train_disc_file)
        write_jsonl(val_disc, val_disc_file)
        files_written.append((train_disc_file.name, len(train_disc), f"{discipline} train"))
        files_written.append((val_disc_file.name, len(val_disc), f"{discipline} validation"))

    print("\n" + "=" * 60)
    print("COMPLETE - 12 FILES GENERATED")
    print("=" * 60)

    print(f"\nOutput files ({len(files_written)} total):")
    print("-" * 50)
    print("Combined (all disciplines):")
    for fname, count, desc in files_written[:2]:
        print(f"  {fname}: {count} entries")

    print("\nPer-discipline:")
    for fname, count, desc in files_written[2:]:
        print(f"  {fname}: {count} entries")

    print(f"\nTotal matched: {len(all_entries)}")
    print(f"  VLM entries (with images): {total_vlm}")
    print(f"  LLM entries (text-only): {len(all_entries) - total_vlm}")
    print(f"Total missing outputs: {total_missing}")
    print(f"Output folder: {output_dir}")
    print(f"Random seed: {seed}")

    # Show format info
    print("\n" + "-" * 50)
    print("FORMAT INFO:")
    print("  VLM disciplines (smithing, adornment):")
    print("    user.content = [{type: image_url, ...}, {type: text, ...}]")
    print("  LLM disciplines (alchemy, refining, engineering):")
    print("    user.content = \"text string\"")
    print("=" * 60)

    input("\nPress Enter to exit...")


if __name__ == "__main__":
    main()

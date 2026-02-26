"""
Convert Training Data to JSONL Format for Together.ai Fine-tuning

Matches indexed recipe inputs (custom_data.json) with synthetic outputs
(Synthetic_outputs/*.json) and creates JSONL for fine-tuning chat models.

Supports two output modes based on discipline type:
- VLM (Vision Language Model): smithing, adornment — multimodal with images
- Text-only (LLM): alchemy, refining, engineering — no images

Format: Together.ai CONVERSATION format ({"messages": [...]})
- VLM: all message content fields use list format [{"type":"text",...}, {"type":"image_url",...}]
- Text-only: all message content fields are plain strings

Together.ai's file checker treats ANY list-format content as multimodal,
so text-only disciplines MUST use plain strings to avoid:
  "The dataset is malformed, the example must contain at least one image if it is multimodal"

Features:
- Robust JSON parsing with multiple fallback strategies
- Auto-detects VLM vs text-only from data (image_base64 presence)
- Creates per-discipline files + separate VLM/text-only combined files
- 80/20 train/validation split with reproducible shuffling
- Integrated validation via Together.ai SDK (together files check)
- CLI arguments or interactive mode

Output files per discipline:
  {discipline}.jsonl, {discipline}_train.jsonl, {discipline}_validation.jsonl
Combined files:
  vlm_combined.jsonl (smithing + adornment with images)
  text_combined.jsonl (alchemy + refining + engineering text-only)
  + train/validation splits for each

Target models:
  VLM:       google/gemma-3-4b-it (vision) or similar VLM
  Text-only: google/gemma-3-4b-it or similar chat model

Usage:
    python convert_to_jsonl.py                    # interactive mode
    python convert_to_jsonl.py --all              # process all disciplines
    python convert_to_jsonl.py --all --validate   # process + validate output
    python convert_to_jsonl.py --discipline alchemy --validate

Author: Claude
Created: 2026-02-05
Updated: 2026-02-26 (Conversation format, VLM/text-only split, validation)
"""

import json
import random
import argparse
import sys
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field


# =============================================================================
# ROBUST JSON PARSING (unchanged — works well)
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

    Strategies tried in order:
    1. Direct parse
    2. Wrap in array brackets (for missing [ ])
    3. Fix truncated files (add ]})
    4. Fix truncated arrays (add ])
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
        array_keys = ['training_outputs', 'items', 'enchantments', 'recipes']

        for key in array_keys:
            if key in data and isinstance(data[key], list):
                items = data[key]
                if 'final_item' in data and isinstance(data['final_item'], dict):
                    items = items + [data['final_item']]
                return items, f"dict[{key}]"

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
    if 'recipe' in item and 'image_base64' in item:
        return None, "input_data_not_output"

    if 'output' in item and isinstance(item['output'], dict):
        return item['output'], "output_wrapper"

    if 'item' in item and isinstance(item['item'], dict):
        return item['item'], "item_wrapper"

    item_indicators = ['itemId', 'enchantmentId', 'name', 'category', 'tier']
    if any(key in item for key in item_indicators):
        return item, "direct"

    return item, "unknown"


def parse_synthetic_file(filepath: Path) -> Tuple[Dict[int, Dict], List[str]]:
    """Parse a synthetic output file and return indexed items."""
    warnings = []
    indexed = {}

    result = robust_json_load(filepath)
    if not result.success:
        warnings.append(f"Parse failed ({result.strategy}): {result.error}")
        return indexed, warnings

    if result.strategy != "direct":
        warnings.append(f"Used fallback strategy: {result.strategy}")

    if isinstance(result.items, list) and len(result.items) == 1 and isinstance(result.items[0], dict):
        items, array_format = extract_items_array(result.items[0])
    elif isinstance(result.items, list) and len(result.items) > 1:
        items = result.items
        array_format = "raw_array"
    else:
        items = result.items
        array_format = "direct"

    if not items:
        warnings.append(f"No items found (format: {array_format})")
        return indexed, warnings

    input_data_count = 0
    for item in items:
        if not isinstance(item, dict):
            continue

        idx = item.get('index')
        if idx is None:
            continue

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

DEFAULT_SYSTEM_PROMPTS = {
    'smithing': "You are a crafting assistant for a fantasy RPG. Given a smithing recipe with materials and grid positions, generate the resulting item as JSON. Consider material tiers (T1-T4), tags, and properties.",
    'adornment': "You are a crafting assistant for a fantasy RPG. Given an adornment recipe with materials, generate the resulting enchantment as JSON. Consider magical properties and tiers.",
    'refining': "You are a crafting assistant for a fantasy RPG. Given a refining recipe, generate the resulting refined material as JSON. Rarity depends on input quality and process.",
    'alchemy': "You are a crafting assistant for a fantasy RPG. Given an alchemy recipe with ingredients, generate the resulting potion/consumable as JSON. Consider ingredient properties and tiers.",
    'engineering': "You are a crafting assistant for a fantasy RPG. Given an engineering recipe with components, generate the resulting device as JSON. Consider component types and tiers.",
}

_loaded_prompts: Dict[str, str] = {}


def load_system_prompt(discipline: str, prompts_dir: Optional[Path] = None) -> str:
    """Load system prompt from external file or use default."""
    cache_key = f"{prompts_dir}:{discipline}" if prompts_dir else discipline
    if cache_key in _loaded_prompts:
        return _loaded_prompts[cache_key]

    prompt = None
    if prompts_dir:
        # Try exact name first, then common variants
        for name in [discipline, discipline.replace('adornment', 'adorment')]:
            prompt_file = prompts_dir / f"{name}.txt"
            if prompt_file.exists():
                try:
                    prompt = prompt_file.read_text(encoding='utf-8').strip()
                    break
                except Exception:
                    pass

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

    if recipe.get('outputId'):
        lines.append(f"Output: {recipe['outputId']}")

    lines.append("")
    lines.append("Materials:")

    all_narratives = []

    # REFINING: Core and Surrounding inputs
    if recipe.get('coreInputs'):
        for inp in recipe['coreInputs']:
            lines.append(format_material_line(inp, label="CORE"))
            if inp.get('material_metadata', {}).get('narrative'):
                all_narratives.append(inp['material_metadata']['narrative'])

    if recipe.get('surroundingInputs'):
        for inp in recipe['surroundingInputs']:
            lines.append(format_material_line(inp, label="SURROUNDING"))
            if inp.get('material_metadata', {}).get('narrative'):
                all_narratives.append(inp['material_metadata']['narrative'])

    # ALCHEMY: Ingredients with slot numbers
    if recipe.get('ingredients'):
        for inp in recipe['ingredients']:
            slot = inp.get('slot', '?')
            lines.append(format_material_line(inp, label=f"Slot {slot}"))
            if inp.get('material_metadata', {}).get('narrative'):
                all_narratives.append(inp['material_metadata']['narrative'])

    # ENGINEERING: Slots with type (FRAME, FUNCTION, POWER)
    if recipe.get('slots'):
        for inp in recipe['slots']:
            slot_type = inp.get('type', 'UNKNOWN')
            lines.append(format_material_line(inp, label=slot_type))
            if inp.get('material_metadata', {}).get('narrative'):
                all_narratives.append(inp['material_metadata']['narrative'])

    # SMITHING/ADORNMENT: Standard inputs with positions
    if recipe.get('inputs'):
        for inp in recipe['inputs']:
            pos = inp.get('position', '')
            positions = inp.get('positions', [])
            pos_label = None
            if pos:
                pos_label = f"at {pos}"
            elif positions:
                pos_label = f"at {', '.join(positions[:3])}"
            lines.append(format_material_line(inp, position_info=pos_label))
            if inp.get('material_metadata', {}).get('narrative'):
                all_narratives.append(inp['material_metadata']['narrative'])

    narrative = all_narratives[0] if all_narratives else recipe.get('narrative')
    if narrative:
        lines.append(f"\nNarrative: {narrative}")

    return "\n".join(lines)


def format_material_line(inp: Dict, label: str = None, position_info: str = None) -> str:
    """Format a single material input line."""
    mat_id = inp.get('materialId', 'unknown')
    qty = inp.get('quantity', 1)
    meta = inp.get('material_metadata', {})

    mat_name = meta.get('name', mat_id)
    tier = meta.get('tier', 1)
    tags = meta.get('tags', [])

    line = f"  - {mat_name} x{qty} (Tier {tier})"
    if label:
        line += f" [{label}]"
    if position_info:
        line += f" {position_info}"
    if tags:
        line += f" {{{', '.join(tags[:3])}}}"
    return line


# =============================================================================
# DATA LOADING
# =============================================================================

def load_custom_data(filepath: Path) -> Tuple[str, Dict[int, Dict]]:
    """Load custom_data.json and return discipline and indexed entries."""
    with open(filepath, 'r', encoding='utf-8') as f:
        data = json.load(f)

    discipline = data.get('metadata', {}).get('discipline', 'unknown')

    indexed = {}
    for entry in data.get('training_data', []):
        idx = entry.get('index')
        if idx is not None:
            indexed[idx] = entry

    return discipline, indexed


def load_synthetic_outputs(synthetic_dir: Path, discipline: str) -> Tuple[Dict[int, Dict], List[str]]:
    """Load all synthetic output files for a discipline and return indexed outputs."""
    indexed = {}
    all_warnings = []

    files = []

    # Pattern 1: Direct files in synthetic_dir
    files.extend(synthetic_dir.glob(f"{discipline}_*.json"))

    # Pattern 2: Files in discipline subfolder
    subfolder = synthetic_dir / discipline
    if subfolder.exists():
        files.extend(subfolder.glob(f"{discipline}_*.json"))
        files.extend(subfolder.glob("*.json"))

    # Deduplicate preserving order
    seen = set()
    unique_files = []
    for f in files:
        if f not in seen:
            seen.add(f)
            unique_files.append(f)

    if not unique_files:
        return indexed, [f"No files found for {discipline}"]

    for filepath in sorted(unique_files):
        file_items, warnings = parse_synthetic_file(filepath)
        for w in warnings:
            all_warnings.append(f"{filepath.name}: {w}")
        for idx, content in file_items.items():
            indexed[idx] = content

    return indexed, all_warnings


# =============================================================================
# JSONL ENTRY CREATION — FORMAT-AWARE
# =============================================================================

# Disciplines that have image data and should use VLM multimodal format
VLM_DISCIPLINES = {'smithing', 'adornment'}


def is_vlm_discipline(discipline: str) -> bool:
    """Check if a discipline uses VLM (vision) format with images."""
    return discipline in VLM_DISCIPLINES


def create_conversation_entry_text(system_text: str, user_text: str, assistant_text: str) -> Dict:
    """
    Create a conversation-format JSONL entry for TEXT-ONLY disciplines.

    All content fields are plain strings — Together.ai treats strings as
    non-multimodal, so no image requirement is triggered.

    Format:
    {"messages": [
        {"role": "system", "content": "..."},
        {"role": "user", "content": "..."},
        {"role": "assistant", "content": "..."}
    ]}
    """
    return {
        "messages": [
            {"role": "system", "content": system_text},
            {"role": "user", "content": user_text},
            {"role": "assistant", "content": assistant_text},
        ]
    }


def create_conversation_entry_vlm(system_text: str, user_text: str, assistant_text: str,
                                   image_base64: str) -> Dict:
    """
    Create a conversation-format JSONL entry for VLM (multimodal) disciplines.

    All content fields use list format for consistency — Together.ai requires
    that within a single example, ALL messages are either multimodal or text-only.

    Format:
    {"messages": [
        {"role": "system", "content": [{"type": "text", "text": "..."}]},
        {"role": "user", "content": [
            {"type": "text", "text": "..."},
            {"type": "image_url", "image_url": {"url": "data:image/png;base64,..."}}
        ]},
        {"role": "assistant", "content": [{"type": "text", "text": "..."}]}
    ]}
    """
    # Ensure proper data URI format
    if not image_base64.startswith('data:'):
        image_url = f"data:image/png;base64,{image_base64}"
    else:
        image_url = image_base64

    return {
        "messages": [
            {"role": "system", "content": [{"type": "text", "text": system_text}]},
            {"role": "user", "content": [
                {"type": "text", "text": user_text},
                {"type": "image_url", "image_url": {"url": image_url}},
            ]},
            {"role": "assistant", "content": [{"type": "text", "text": assistant_text}]},
        ]
    }


def create_jsonl_entry(input_data: Dict, output_data: Dict, discipline: str,
                       prompts_dir: Optional[Path] = None) -> Dict:
    """
    Create a single JSONL entry using the correct format for the discipline.

    Automatically selects VLM (multimodal) or text-only conversation format
    based on discipline type and data availability.
    """
    # Clean output
    cleaned_output = remove_rarity_recursive(output_data, discipline)
    if isinstance(cleaned_output, dict) and 'index' in cleaned_output:
        cleaned_output = {k: v for k, v in cleaned_output.items() if k != 'index'}

    # Build text content
    recipe_text = format_recipe_as_text(input_data, discipline)
    output_text = json.dumps(cleaned_output, indent=2)
    system_text = load_system_prompt(discipline, prompts_dir)

    # VLM: multimodal with image
    if is_vlm_discipline(discipline):
        image_base64 = input_data.get('image_base64')
        if image_base64:
            return create_conversation_entry_vlm(system_text, recipe_text, output_text, image_base64)
        # Fallback: VLM discipline but no image — use text-only format
        # (This entry won't have vision data, but at least it won't error)

    # Text-only: plain string content
    return create_conversation_entry_text(system_text, recipe_text, output_text)


# =============================================================================
# DISCIPLINE PROCESSING
# =============================================================================

@dataclass
class DisciplineResult:
    """Result of processing a single discipline."""
    discipline: str
    entries: List[Dict] = field(default_factory=list)
    missing_count: int = 0
    vlm_count: int = 0
    text_count: int = 0
    skipped_no_image: int = 0
    total_inputs: int = 0
    total_outputs: int = 0


def process_discipline(input_file: Path, synthetic_dir: Path,
                       prompts_dir: Optional[Path] = None,
                       verbose: bool = True) -> DisciplineResult:
    """Process a single discipline, matching inputs with outputs."""
    discipline, inputs = load_custom_data(input_file)
    result = DisciplineResult(discipline=discipline, total_inputs=len(inputs))

    print(f"\n{discipline.upper()}:")
    print(f"  Loaded {len(inputs)} indexed inputs from {input_file.name}")

    # Report image availability for VLM disciplines
    if is_vlm_discipline(discipline):
        entries_with_images = sum(1 for entry in inputs.values() if entry.get('image_base64'))
        print(f"  Entries with images: {entries_with_images}/{len(inputs)}")

    # Load synthetic outputs
    outputs, warnings = load_synthetic_outputs(synthetic_dir, discipline)
    result.total_outputs = len(outputs)
    print(f"  Loaded {len(outputs)} synthetic outputs")

    if verbose and warnings:
        print(f"  Parsing notes ({len(warnings)}):")
        for w in warnings[:10]:
            print(f"    - {w}")
        if len(warnings) > 10:
            print(f"    ... and {len(warnings) - 10} more")

    if not outputs:
        print(f"  No synthetic outputs found for {discipline}")
        result.missing_count = len(inputs)
        return result

    # Match and create JSONL entries
    missing_outputs = []

    for idx in sorted(inputs.keys()):
        if idx not in outputs:
            missing_outputs.append(idx)
            continue

        input_entry = inputs[idx]

        # For VLM disciplines, skip entries without images
        if is_vlm_discipline(discipline) and not input_entry.get('image_base64'):
            result.skipped_no_image += 1
            continue

        entry = create_jsonl_entry(input_entry, outputs[idx], discipline, prompts_dir)
        result.entries.append(entry)

        if is_vlm_discipline(discipline) and input_entry.get('image_base64'):
            result.vlm_count += 1
        else:
            result.text_count += 1

    result.missing_count = len(missing_outputs)

    print(f"  Matched: {len(result.entries)} entries", end="")
    if is_vlm_discipline(discipline):
        print(f" (VLM: {result.vlm_count})", end="")
    else:
        print(f" (text-only: {result.text_count})", end="")
    print()

    if result.skipped_no_image > 0:
        print(f"  Skipped (no image): {result.skipped_no_image} entries")

    if missing_outputs:
        _print_missing_ranges(missing_outputs)

    return result


def _print_missing_ranges(missing: List[int]) -> None:
    """Print missing index ranges in compact format."""
    ranges = []
    start = missing[0]
    end = start
    for idx in missing[1:]:
        if idx == end + 1:
            end = idx
        else:
            ranges.append(f"{start}-{end}" if start != end else str(start))
            start = end = idx
    ranges.append(f"{start}-{end}" if start != end else str(start))

    if len(ranges) <= 5:
        print(f"  Missing outputs for indices: {', '.join(ranges)}")
    else:
        print(f"  Missing outputs for {len(missing)} indices ({ranges[0]} ... {ranges[-1]})")


# =============================================================================
# TRAIN/VALIDATION SPLIT
# =============================================================================

def train_validation_split(entries: List[Dict], train_ratio: float = 0.8,
                           seed: Optional[int] = None) -> Tuple[List[Dict], List[Dict]]:
    """Split entries into train and validation sets with random shuffling."""
    if not entries:
        return [], []

    if seed is not None:
        random.seed(seed)

    shuffled = entries.copy()
    random.shuffle(shuffled)

    split_idx = int(len(shuffled) * train_ratio)
    return shuffled[:split_idx], shuffled[split_idx:]


# =============================================================================
# FILE I/O
# =============================================================================

def write_jsonl(entries: List[Dict], filepath: Path) -> int:
    """Write entries to JSONL file. Returns number of entries written."""
    with open(filepath, 'w', encoding='utf-8') as f:
        for entry in entries:
            f.write(json.dumps(entry, ensure_ascii=False) + '\n')
    return len(entries)


# =============================================================================
# VALIDATION via Together.ai SDK
# =============================================================================

def validate_jsonl_file(filepath: Path) -> Dict[str, Any]:
    """
    Validate a JSONL file using Together.ai's built-in file checker.

    Returns the validation report dict with 'is_check_passed' key.
    """
    try:
        from together.lib.utils import check_file
        return check_file(filepath)
    except ImportError:
        return {
            "is_check_passed": None,
            "message": "together package not installed. Install with: pip install together"
        }
    except Exception as e:
        return {
            "is_check_passed": False,
            "message": f"Validation error: {e}"
        }


def validate_all_outputs(output_dir: Path, files_written: List[Tuple[str, int, str]]) -> bool:
    """Validate all written JSONL files. Returns True if all pass."""
    print("\n" + "-" * 60)
    print("VALIDATING OUTPUT FILES (together files check)")
    print("-" * 60)

    all_passed = True
    for fname, count, desc in files_written:
        filepath = output_dir / fname
        if count == 0:
            print(f"  {fname}: SKIP (0 entries)")
            continue

        report = validate_jsonl_file(filepath)
        passed = report.get('is_check_passed')

        if passed is True:
            num = report.get('num_samples', '?')
            print(f"  {fname}: PASS ({num} samples)")
        elif passed is None:
            print(f"  {fname}: SKIP ({report.get('message', 'unknown')})")
        else:
            all_passed = False
            msg = report.get('message', 'unknown error')
            line = report.get('line_number', '?')
            print(f"  {fname}: FAIL — {msg}")
            if line != '?':
                print(f"    (line {line})")

    return all_passed


# =============================================================================
# MAIN
# =============================================================================

def find_directories() -> Tuple[Path, Path, Path, Optional[Path]]:
    """Locate script directory, training dir, synthetic dir, prompts dir."""
    script_dir = Path(__file__).parent
    training_dir = script_dir / "Synthetic_Training"
    synthetic_dir = training_dir / "Synthetic_outputs"
    prompts_dir = training_dir / "system_prompts"

    if not prompts_dir.exists():
        prompts_dir = None

    return script_dir, training_dir, synthetic_dir, prompts_dir


def discover_custom_files(training_dir: Path) -> List[Path]:
    """Find all *_custom_data.json files."""
    return sorted(training_dir.glob("*_custom_data.json"))


def print_discovery_info(training_dir: Path, synthetic_dir: Path,
                         prompts_dir: Optional[Path], custom_files: List[Path]) -> None:
    """Print discovered files and directories."""
    print(f"\nLooking in: {training_dir}")
    print(f"\nFound {len(custom_files)} input file(s):")
    print("-" * 50)

    for i, f in enumerate(custom_files, 1):
        try:
            with open(f, 'r') as fp:
                data = json.load(fp)
                count = len(data.get('training_data', []))
                disc = data.get('metadata', {}).get('discipline', '?')
                has_images = any(e.get('image_base64') for e in data.get('training_data', []))
                mode = "VLM" if has_images else "text"
        except Exception:
            count, disc, mode = '?', '?', '?'
        print(f"  {i}. {f.name} [{disc}] ({count} entries, {mode})")

    # Synthetic outputs
    if synthetic_dir.exists():
        syn_files = list(synthetic_dir.glob("*.json")) + list(synthetic_dir.glob("*/*.json"))
        print(f"\nSynthetic outputs: {len(syn_files)} file(s)")
        for sf in sorted(d for d in synthetic_dir.iterdir() if d.is_dir()):
            sf_count = len(list(sf.glob("*.json")))
            print(f"  - {sf.name}/: {sf_count} files")

    # System prompts
    if prompts_dir and prompts_dir.exists():
        prompt_files = sorted(prompts_dir.glob("*.txt"))
        print(f"\nSystem prompts: {len(prompt_files)} file(s)")
        for pf in prompt_files:
            print(f"  - {pf.name}")
    else:
        print("\nSystem prompts: using defaults")


def interactive_select(custom_files: List[Path]) -> List[Path]:
    """Interactive file selection. Returns list of files to process."""
    print(f"\n  {len(custom_files) + 1}. All files (recommended)")
    print()

    try:
        selection = input(f"Select input file (1-{len(custom_files) + 1}): ").strip()
        sel_num = int(selection)
    except (ValueError, EOFError):
        print("Invalid selection.")
        return []

    if sel_num < 1 or sel_num > len(custom_files) + 1:
        print("Invalid selection.")
        return []

    if sel_num == len(custom_files) + 1:
        return custom_files
    return [custom_files[sel_num - 1]]


def process_all(files_to_process: List[Path], synthetic_dir: Path,
                prompts_dir: Optional[Path]) -> Dict[str, DisciplineResult]:
    """Process all selected files. Returns discipline -> result mapping."""
    print("\n" + "-" * 60)
    print("PROCESSING")
    print("-" * 60)

    results = {}
    for input_file in files_to_process:
        result = process_discipline(input_file, synthetic_dir, prompts_dir, verbose=True)
        results[result.discipline] = result

    return results


def write_all_outputs(results: Dict[str, DisciplineResult], output_dir: Path,
                      train_ratio: float = 0.8, seed: int = 42) -> List[Tuple[str, int, str]]:
    """
    Write all output JSONL files.

    Creates:
    - Per-discipline files (combined + train + val)
    - Separate VLM combined and text-only combined files (not mixed)

    Returns list of (filename, count, description) tuples.
    """
    output_dir.mkdir(exist_ok=True)
    files_written = []

    # Separate VLM and text-only entries
    vlm_entries = []
    text_entries = []

    for discipline, result in results.items():
        if is_vlm_discipline(discipline):
            vlm_entries.extend(result.entries)
        else:
            text_entries.extend(result.entries)

    print("\n" + "-" * 60)
    print("TRAIN/VALIDATION SPLIT (80/20)")
    print("-" * 60)

    # --- Per-discipline files ---
    discipline_splits = {}
    for discipline, result in results.items():
        train_disc, val_disc = train_validation_split(result.entries, train_ratio, seed)
        discipline_splits[discipline] = (train_disc, val_disc)

        mode = "VLM" if is_vlm_discipline(discipline) else "text"
        print(f"\n{discipline.capitalize()} ({mode}):")
        print(f"  Total: {len(result.entries)}")
        print(f"  Train: {len(train_disc)}")
        print(f"  Validation: {len(val_disc)}")

    # --- Combined splits (separated by format) ---
    if vlm_entries:
        vlm_train, vlm_val = train_validation_split(vlm_entries, train_ratio, seed)
        print(f"\nVLM Combined (smithing + adornment):")
        print(f"  Total: {len(vlm_entries)}")
        print(f"  Train: {len(vlm_train)}")
        print(f"  Validation: {len(vlm_val)}")
    else:
        vlm_train, vlm_val = [], []

    if text_entries:
        text_train, text_val = train_validation_split(text_entries, train_ratio, seed)
        print(f"\nText Combined (alchemy + refining + engineering):")
        print(f"  Total: {len(text_entries)}")
        print(f"  Train: {len(text_train)}")
        print(f"  Validation: {len(text_val)}")
    else:
        text_train, text_val = [], []

    # --- Write files ---
    print("\n" + "-" * 60)
    print("WRITING OUTPUT FILES")
    print("-" * 60)

    # VLM combined files
    if vlm_entries:
        for name, data, desc in [
            ("vlm_combined.jsonl", vlm_entries, "VLM combined"),
            ("vlm_train.jsonl", vlm_train, "VLM train"),
            ("vlm_validation.jsonl", vlm_val, "VLM validation"),
        ]:
            write_jsonl(data, output_dir / name)
            files_written.append((name, len(data), desc))

    # Text-only combined files
    if text_entries:
        for name, data, desc in [
            ("text_combined.jsonl", text_entries, "text combined"),
            ("text_train.jsonl", text_train, "text train"),
            ("text_validation.jsonl", text_val, "text validation"),
        ]:
            write_jsonl(data, output_dir / name)
            files_written.append((name, len(data), desc))

    # Per-discipline files
    for discipline, result in results.items():
        train_disc, val_disc = discipline_splits[discipline]

        for name, data, desc in [
            (f"{discipline}.jsonl", result.entries, f"{discipline} combined"),
            (f"{discipline}_train.jsonl", train_disc, f"{discipline} train"),
            (f"{discipline}_validation.jsonl", val_disc, f"{discipline} validation"),
        ]:
            write_jsonl(data, output_dir / name)
            files_written.append((name, len(data), desc))

    return files_written


def print_summary(results: Dict[str, DisciplineResult],
                  files_written: List[Tuple[str, int, str]],
                  output_dir: Path, seed: int) -> None:
    """Print final summary."""
    total_entries = sum(r.vlm_count + r.text_count for r in results.values())
    total_vlm = sum(r.vlm_count for r in results.values())
    total_text = sum(r.text_count for r in results.values())
    total_missing = sum(r.missing_count for r in results.values())
    total_skipped = sum(r.skipped_no_image for r in results.values())

    print("\n" + "=" * 60)
    print(f"COMPLETE - {len(files_written)} FILES GENERATED")
    print("=" * 60)

    # Combined files
    combined_files = [(f, c, d) for f, c, d in files_written if 'combined' in d or 'train' in d or 'validation' in d]
    vlm_files = [(f, c, d) for f, c, d in files_written if d.startswith('VLM')]
    text_files = [(f, c, d) for f, c, d in files_written if d.startswith('text')]
    disc_files = [(f, c, d) for f, c, d in files_written if d not in [x[2] for x in vlm_files + text_files]]

    if vlm_files:
        print("\nVLM files (for vision model fine-tuning):")
        for fname, count, desc in vlm_files:
            print(f"  {fname}: {count} entries")

    if text_files:
        print("\nText files (for text model fine-tuning):")
        for fname, count, desc in text_files:
            print(f"  {fname}: {count} entries")

    print("\nPer-discipline files:")
    for fname, count, desc in disc_files:
        print(f"  {fname}: {count} entries")

    print(f"\nTotal matched: {total_entries}")
    print(f"  VLM entries (multimodal): {total_vlm}")
    print(f"  Text entries (text-only): {total_text}")
    if total_skipped:
        print(f"  Skipped (VLM without image): {total_skipped}")
    print(f"Total missing outputs: {total_missing}")
    print(f"Output folder: {output_dir}")
    print(f"Random seed: {seed}")

    print("\n" + "-" * 50)
    print("FORMAT INFO:")
    print("  All files use Together.ai CONVERSATION format:")
    print('  {"messages": [{"role": "system", ...}, {"role": "user", ...}, {"role": "assistant", ...}]}')
    print()
    print("  VLM (smithing, adornment):")
    print("    content = [{type: text}, {type: image_url}]  (multimodal list)")
    print("    Target: google/gemma-3-4b-it VLM or similar vision model")
    print()
    print("  Text (alchemy, refining, engineering):")
    print("    content = \"plain string\"  (NOT a list — avoids multimodal detection)")
    print("    Target: google/gemma-3-4b-it or similar chat model")
    print("=" * 60)


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Convert training data to Together.ai JSONL format for fine-tuning",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python convert_to_jsonl.py                         # interactive mode
  python convert_to_jsonl.py --all                   # all disciplines
  python convert_to_jsonl.py --all --validate        # all + validate
  python convert_to_jsonl.py --discipline alchemy    # single discipline
  python convert_to_jsonl.py --discipline smithing --discipline alchemy
        """,
    )
    parser.add_argument('--all', action='store_true',
                        help='Process all disciplines (no interactive prompt)')
    parser.add_argument('--discipline', '-d', action='append', dest='disciplines',
                        help='Process specific discipline(s). Can be repeated.')
    parser.add_argument('--validate', '-v', action='store_true',
                        help='Validate output files using Together.ai SDK')
    parser.add_argument('--seed', type=int, default=42,
                        help='Random seed for train/val split (default: 42)')
    parser.add_argument('--train-ratio', type=float, default=0.8,
                        help='Train split ratio (default: 0.8)')
    parser.add_argument('--output-dir', type=str, default=None,
                        help='Output directory (default: jsonl_outputs/ next to this script)')
    return parser.parse_args()


def main():
    args = parse_args()

    print("=" * 60)
    print("JSONL CONVERTER — Together.ai Conversation Format")
    print("  VLM: multimodal (smithing, adornment)")
    print("  Text: plain string (alchemy, refining, engineering)")
    print("=" * 60)

    # Find directories
    script_dir, training_dir, synthetic_dir, prompts_dir = find_directories()

    if not training_dir.exists():
        print(f"\nError: Synthetic_Training directory not found at {training_dir}")
        sys.exit(1)

    if not synthetic_dir.exists():
        print(f"\nError: Synthetic_outputs not found at {synthetic_dir}")
        sys.exit(1)

    custom_files = discover_custom_files(training_dir)
    if not custom_files:
        print("\nNo *_custom_data.json files found")
        sys.exit(1)

    print_discovery_info(training_dir, synthetic_dir, prompts_dir, custom_files)

    # Select files to process
    if args.all:
        files_to_process = custom_files
    elif args.disciplines:
        # Filter to requested disciplines
        files_to_process = []
        for f in custom_files:
            try:
                with open(f, 'r') as fp:
                    data = json.load(fp)
                    disc = data.get('metadata', {}).get('discipline', '')
                if disc in args.disciplines:
                    files_to_process.append(f)
            except Exception:
                pass
        if not files_to_process:
            print(f"\nNo matching files for disciplines: {args.disciplines}")
            sys.exit(1)
    else:
        files_to_process = interactive_select(custom_files)
        if not files_to_process:
            sys.exit(1)

    # Output directory
    if args.output_dir:
        output_dir = Path(args.output_dir)
    else:
        output_dir = script_dir / "jsonl_outputs"

    # Process
    results = process_all(files_to_process, synthetic_dir, prompts_dir)

    if not any(r.entries for r in results.values()):
        print("\nNo entries matched. Nothing to write.")
        sys.exit(1)

    # Write outputs
    files_written = write_all_outputs(results, output_dir, args.train_ratio, args.seed)

    # Summary
    print_summary(results, files_written, output_dir, args.seed)

    # Validation
    if args.validate:
        all_passed = validate_all_outputs(output_dir, files_written)
        if all_passed:
            print("\nAll files passed validation.")
        else:
            print("\nSome files FAILED validation. Check errors above.")
            sys.exit(1)

    # Interactive mode: wait for keypress
    if not args.all and not args.disciplines:
        input("\nPress Enter to exit...")


if __name__ == "__main__":
    main()

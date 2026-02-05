"""
Split Training Data into Indexed Chunks

Takes training data JSON files and splits them into smaller files
while maintaining proper index numbers.

Features:
- Split by custom chunk size (default 50)
- Maintains original index numbers
- Interactive prompts - just run the script

Usage:
    python split_training_data.py
    (Follow the prompts)

Author: Claude
Created: 2026-02-05
"""

import json
import os
from pathlib import Path
from typing import Dict, List, Tuple, Optional


def parse_range_string(range_str: str, max_index: int) -> List[Tuple[int, int]]:
    """
    Parse a range string like "1-50,101-150,200-250" into list of (start, end) tuples.

    Args:
        range_str: Comma-separated ranges like "1-50,101-150"
        max_index: Maximum valid index

    Returns:
        List of (start, end) tuples
    """
    ranges = []
    parts = range_str.split(',')

    for part in parts:
        part = part.strip()
        if '-' in part:
            start, end = part.split('-', 1)
            start = int(start.strip())
            end = int(end.strip())
        else:
            # Single number - treat as single item range
            start = end = int(part.strip())

        # Validate
        if start < 1:
            start = 1
        if end > max_index:
            end = max_index
        if start <= end:
            ranges.append((start, end))

    return ranges


def generate_auto_ranges(total: int, chunk_size: int) -> List[Tuple[int, int]]:
    """
    Generate automatic ranges based on chunk size.

    Args:
        total: Total number of entries
        chunk_size: Size of each chunk

    Returns:
        List of (start, end) tuples
    """
    ranges = []
    start = 1

    while start <= total:
        end = min(start + chunk_size - 1, total)
        ranges.append((start, end))
        start = end + 1

    return ranges


def split_file(input_path: str, output_base_dir: str, chunk_size: int = 50,
               custom_ranges: str = None) -> int:
    """
    Split a single training data file into chunks.
    Organizes output into discipline-named folders.

    Args:
        input_path: Path to input JSON file
        output_base_dir: Base directory for output files
        chunk_size: Number of entries per chunk (for auto mode)
        custom_ranges: Optional custom range string

    Returns:
        Number of files created
    """
    with open(input_path, 'r') as f:
        data = json.load(f)

    metadata = data.get('metadata', {})
    discipline = metadata.get('discipline', 'unknown')
    training_data = data.get('training_data', [])

    if not training_data:
        print(f"  No training data found in {input_path}")
        return 0

    total = len(training_data)
    print(f"\n  File: {Path(input_path).name}")
    print(f"  Discipline: {discipline}")
    print(f"  Total entries: {total}")

    # Build index lookup
    by_index = {entry.get('index', i+1): entry for i, entry in enumerate(training_data)}
    max_index = max(by_index.keys())

    # Determine ranges
    if custom_ranges:
        ranges = parse_range_string(custom_ranges, max_index)
        print(f"  Using custom ranges: {custom_ranges}")
    else:
        ranges = generate_auto_ranges(max_index, chunk_size)
        print(f"  Auto-splitting into chunks of {chunk_size}")

    print(f"  Creating {len(ranges)} files...")

    # Create discipline folder structure: training_outputs/{discipline}/split/
    discipline_dir = Path(output_base_dir) / discipline
    split_dir = discipline_dir / "split"
    split_dir.mkdir(parents=True, exist_ok=True)

    # Move original file to discipline folder if not already there
    input_file = Path(input_path)
    original_dest = discipline_dir / input_file.name
    if input_file.parent != discipline_dir and not original_dest.exists():
        import shutil
        shutil.move(str(input_file), str(original_dest))
        print(f"  Moved original to: {discipline}/{input_file.name}")

    files_created = 0

    for start, end in ranges:
        # Collect entries in this range
        chunk_data = []
        for idx in range(start, end + 1):
            if idx in by_index:
                chunk_data.append(by_index[idx])

        if not chunk_data:
            continue

        # Create output file with discipline prefix
        output_filename = f"{discipline}_{start:04d}-{end:04d}.json"
        output_path = split_dir / output_filename

        output = {
            'metadata': {
                **metadata,
                'split_range': f"{start}-{end}",
                'entries_in_chunk': len(chunk_data),
                'original_total': total,
            },
            'training_data': chunk_data
        }

        with open(output_path, 'w') as f:
            json.dump(output, f, indent=2)

        print(f"    Created: {discipline}/split/{output_filename} ({len(chunk_data)} entries)")
        files_created += 1

    return files_created


def interactive_mode(input_path: str, output_dir: str):
    """
    Interactive mode for selecting ranges.
    """
    with open(input_path, 'r') as f:
        data = json.load(f)

    metadata = data.get('metadata', {})
    discipline = metadata.get('discipline', 'unknown')
    training_data = data.get('training_data', [])

    if not training_data:
        print("No training data found.")
        return

    total = len(training_data)
    by_index = {entry.get('index', i+1): entry for i, entry in enumerate(training_data)}
    max_index = max(by_index.keys())

    print("\n" + "=" * 60)
    print("INTERACTIVE SPLIT MODE")
    print("=" * 60)
    print(f"\nFile: {Path(input_path).name}")
    print(f"Discipline: {discipline}")
    print(f"Total entries: {total}")
    print(f"Index range: 1 to {max_index}")

    print("\n" + "-" * 60)
    print("OPTIONS:")
    print("-" * 60)
    print("1. Auto-split by chunk size")
    print("2. Custom ranges")
    print("3. Preview entries by index")
    print("4. Cancel")

    choice = input("\nSelect option (1-4): ").strip()

    if choice == '1':
        size = input(f"Enter chunk size (default 50): ").strip()
        chunk_size = int(size) if size else 50
        split_file(input_path, output_dir, chunk_size=chunk_size)

    elif choice == '2':
        print("\nEnter ranges as comma-separated values.")
        print("Examples: '1-50' or '1-50,101-150,200-250'")
        ranges = input("Ranges: ").strip()
        if ranges:
            split_file(input_path, output_dir, custom_ranges=ranges)
        else:
            print("No ranges provided.")

    elif choice == '3':
        idx = input("Enter index to preview: ").strip()
        if idx.isdigit():
            idx = int(idx)
            if idx in by_index:
                print(f"\nEntry {idx}:")
                print(json.dumps(by_index[idx], indent=2)[:500] + "...")
            else:
                print(f"Index {idx} not found.")
        interactive_mode(input_path, output_dir)  # Return to menu

    else:
        print("Cancelled.")


def main():
    """Interactive main - just run the script and answer prompts."""

    print("=" * 60)
    print("TRAINING DATA SPLITTER")
    print("=" * 60)

    # Find training_outputs folder relative to script
    script_dir = Path(__file__).parent
    input_dir = script_dir / "training_outputs"

    print(f"\nLooking in: {input_dir}")

    if not input_dir.exists():
        print(f"\nError: Directory not found: {input_dir}")
        print("Make sure to run crafting_training_data.py first to generate data.")
        input("\nPress Enter to exit...")
        return

    # Find JSON files (in root or in discipline subfolders)
    json_files = list(input_dir.glob('*_data.json'))

    # Also check discipline subfolders
    for subdir in input_dir.iterdir():
        if subdir.is_dir():
            json_files.extend(subdir.glob('*_data.json'))

    if not json_files:
        print(f"\nNo *_data.json files found in {input_dir}")
        print("Make sure to run crafting_training_data.py first to generate data.")
        input("\nPress Enter to exit...")
        return

    # Show available files
    print(f"\nFound {len(json_files)} training data file(s):")
    print("-" * 40)
    for i, f in enumerate(json_files, 1):
        # Get entry count and discipline
        try:
            with open(f, 'r') as fp:
                data = json.load(fp)
                count = len(data.get('training_data', []))
                discipline = data.get('metadata', {}).get('discipline', 'unknown')
        except:
            count = '?'
            discipline = '?'
        print(f"  {i}. {f.name} [{discipline}] ({count} entries)")
    print(f"  {len(json_files) + 1}. All files")

    # Select file(s)
    print()
    selection = input(f"Select file (1-{len(json_files) + 1}): ").strip()

    try:
        sel_num = int(selection)
    except ValueError:
        print("Invalid selection.")
        input("\nPress Enter to exit...")
        return

    if sel_num < 1 or sel_num > len(json_files) + 1:
        print("Invalid selection.")
        input("\nPress Enter to exit...")
        return

    # Get chunk size
    print()
    size_input = input("Enter chunk size (default 50): ").strip()
    chunk_size = int(size_input) if size_input else 50

    if chunk_size < 1:
        print("Chunk size must be at least 1.")
        input("\nPress Enter to exit...")
        return

    # Process
    total_files = 0
    output_dir = str(input_dir)

    if sel_num == len(json_files) + 1:
        # All files
        print(f"\nSplitting all files into chunks of {chunk_size}...")
        for json_file in json_files:
            files = split_file(str(json_file), output_dir, chunk_size=chunk_size)
            total_files += files
    else:
        # Single file
        selected_file = json_files[sel_num - 1]
        print(f"\nSplitting {selected_file.name} into chunks of {chunk_size}...")
        total_files = split_file(str(selected_file), output_dir, chunk_size=chunk_size)

    print("\n" + "=" * 60)
    print(f"COMPLETE: Created {total_files} split file(s)")
    print("=" * 60)
    print("\nOutput structure:")
    print("  training_outputs/")
    print("    {discipline}/")
    print("      {original_file}.json")
    print("      split/")
    print("        {discipline}_0001-0050.json")
    print("        {discipline}_0051-0100.json")
    print("        ...")

    input("\nPress Enter to exit...")


if __name__ == "__main__":
    main()

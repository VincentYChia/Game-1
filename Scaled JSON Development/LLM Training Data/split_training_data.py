"""
Split Training Data into Indexed Chunks

Takes training data JSON files and splits them into smaller files
while maintaining proper index numbers.

Features:
- Split by custom chunk size (default 50)
- Maintains original index numbers
- Supports automatic or custom range selection
- Can process single file or all files in directory

Usage:
    python split_training_data.py --input ./training_outputs/alchemy_custom_data.json --size 50
    python split_training_data.py --input ./training_outputs/ --all --size 100
    python split_training_data.py --input ./training_outputs/smithing_custom_data.json --range 1-50,101-150

Author: Claude
Created: 2026-02-05
"""

import json
import os
import argparse
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


def split_file(input_path: str, output_dir: str, chunk_size: int = 50,
               custom_ranges: str = None) -> int:
    """
    Split a single training data file into chunks.

    Args:
        input_path: Path to input JSON file
        output_dir: Directory for output files
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

    # Create output directory
    input_stem = Path(input_path).stem
    split_dir = Path(output_dir) / f"{input_stem}_split"
    split_dir.mkdir(parents=True, exist_ok=True)

    files_created = 0

    for start, end in ranges:
        # Collect entries in this range
        chunk_data = []
        for idx in range(start, end + 1):
            if idx in by_index:
                chunk_data.append(by_index[idx])

        if not chunk_data:
            continue

        # Create output file
        output_filename = f"{input_stem}_{start:04d}-{end:04d}.json"
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

        print(f"    Created: {output_filename} ({len(chunk_data)} entries)")
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
    parser = argparse.ArgumentParser(
        description='Split training data into indexed chunks',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Auto-split single file into chunks of 50
  python split_training_data.py --input ./training_outputs/alchemy_custom_data.json --size 50

  # Auto-split all files in directory
  python split_training_data.py --input ./training_outputs/ --all --size 100

  # Split with custom ranges
  python split_training_data.py --input ./training_outputs/smithing_custom_data.json --range "1-50,101-150"

  # Interactive mode
  python split_training_data.py --input ./training_outputs/alchemy_custom_data.json --interactive
        """
    )

    parser.add_argument('--input', '-i', required=True,
                        help='Input JSON file or directory')
    parser.add_argument('--output', '-o', default=None,
                        help='Output directory (default: same as input)')
    parser.add_argument('--size', '-s', type=int, default=50,
                        help='Chunk size for auto-split (default: 50)')
    parser.add_argument('--range', '-r', default=None,
                        help='Custom ranges like "1-50,101-150"')
    parser.add_argument('--all', '-a', action='store_true',
                        help='Process all JSON files in directory')
    parser.add_argument('--interactive', action='store_true',
                        help='Interactive mode for selecting ranges')

    args = parser.parse_args()

    input_path = Path(args.input)
    output_dir = args.output or str(input_path.parent if input_path.is_file() else input_path)

    print("=" * 60)
    print("TRAINING DATA SPLITTER")
    print("=" * 60)

    if args.interactive and input_path.is_file():
        interactive_mode(str(input_path), output_dir)
        return

    total_files = 0

    if args.all and input_path.is_dir():
        # Process all JSON files
        json_files = list(input_path.glob('*_data.json'))

        if not json_files:
            print(f"\nNo *_data.json files found in {input_path}")
            return

        print(f"\nFound {len(json_files)} files to process:")
        for f in json_files:
            print(f"  - {f.name}")

        confirm = input("\nProceed? (y/n): ").strip().lower()
        if confirm != 'y':
            print("Cancelled.")
            return

        for json_file in json_files:
            files = split_file(str(json_file), output_dir,
                             chunk_size=args.size,
                             custom_ranges=args.range)
            total_files += files

    elif input_path.is_file():
        total_files = split_file(str(input_path), output_dir,
                                chunk_size=args.size,
                                custom_ranges=args.range)
    else:
        print(f"\nError: {input_path} not found")
        return

    print("\n" + "=" * 60)
    print(f"COMPLETE: Created {total_files} split files")
    print("=" * 60)


if __name__ == "__main__":
    main()

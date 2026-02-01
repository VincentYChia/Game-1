"""
Rename all files ending with -1.png to .png (remove the -1 suffix)
Run from the assets folder or modify SCRIPT_DIR
"""

from pathlib import Path

SCRIPT_DIR = Path(__file__).parent

# Find all cycle folders
cycle_dirs = list(SCRIPT_DIR.glob('icons-generated-cycle-*'))

renamed = 0
skipped = 0

for cycle_dir in sorted(cycle_dirs):
    # Only look in generated_icons (v1 folder), not generated_icons-2, etc.
    v1_dir = cycle_dir / 'generated_icons'

    if not v1_dir.exists():
        continue

    # Find all -1.png files
    for old_path in v1_dir.rglob('*-1.png'):
        # New name without -1
        new_name = old_path.name.replace('-1.png', '.png')
        new_path = old_path.parent / new_name

        if new_path.exists():
            print(f"  SKIP (exists): {old_path.relative_to(SCRIPT_DIR)}")
            skipped += 1
        else:
            old_path.rename(new_path)
            print(f"  ✓ {old_path.name} → {new_name}")
            renamed += 1

print(f"\nDone! Renamed: {renamed}, Skipped: {skipped}")
"""
Fill Missing Images for VLM Training Data

Scans custom_data.json files for entries missing image_base64 and generates
images from their recipe grid data.

Usage:
    python fill_missing_images.py
"""

import json
import base64
import io
from pathlib import Path
from typing import Dict, List, Optional
import numpy as np

try:
    from PIL import Image
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False
    print("Error: PIL required. Install with: pip install Pillow")
    exit(1)

# Material color mappings (simplified from crafting_training_data.py)
CATEGORY_COLORS = {
    'ore': (0.6, 0.5, 0.5),
    'ingot': (0.7, 0.7, 0.8),
    'wood': (0.55, 0.35, 0.2),
    'plank': (0.65, 0.45, 0.25),
    'stone': (0.5, 0.5, 0.55),
    'gem': (0.4, 0.8, 0.9),
    'crystal': (0.7, 0.85, 0.95),
    'elemental': (0.3, 0.6, 0.9),
    'leather': (0.5, 0.35, 0.25),
    'fabric': (0.85, 0.85, 0.8),
    'bone': (0.9, 0.88, 0.82),
    'monster': (0.6, 0.3, 0.5),
    'refined': (0.75, 0.75, 0.8),
    'default': (0.5, 0.5, 0.5),
}

TIER_BRIGHTNESS = {1: 0.7, 2: 0.8, 3: 0.9, 4: 1.0}


def load_materials(materials_path: Path) -> Dict:
    """Load materials database."""
    with open(materials_path) as f:
        data = json.load(f)
    return {m['materialId']: m for m in data.get('materials', [])}


def material_to_color(material: Dict) -> tuple:
    """Get RGB color for a material."""
    category = material.get('category', 'default')
    tier = material.get('tier', 1)

    base_color = CATEGORY_COLORS.get(category, CATEGORY_COLORS['default'])
    brightness = TIER_BRIGHTNESS.get(tier, 0.7)

    return tuple(c * brightness for c in base_color)


def recipe_to_grid(recipe: Dict, materials_dict: Dict) -> List[List[Optional[str]]]:
    """Convert recipe inputs to 9x9 grid."""
    grid = [[None] * 9 for _ in range(9)]

    for inp in recipe.get('inputs', []):
        mat_id = inp.get('materialId')

        # Handle both 'position' (single) and 'positions' (list) formats
        positions = inp.get('positions', [])
        if not positions and inp.get('position'):
            positions = [inp['position']]

        for pos_str in positions:
            try:
                # Parse "row,col" format
                parts = pos_str.split(',')
                row, col = int(parts[0]), int(parts[1])
                if 0 <= row < 9 and 0 <= col < 9:
                    grid[row][col] = mat_id
            except (ValueError, IndexError):
                continue

    return grid


def grid_to_image(grid: List[List[Optional[str]]], materials_dict: Dict, cell_size: int = 4) -> np.ndarray:
    """Convert 9x9 grid to RGB image."""
    img_size = 9 * cell_size
    img = np.zeros((img_size, img_size, 3), dtype=np.float32)

    for i in range(9):
        for j in range(9):
            mat_id = grid[i][j]
            if mat_id is None:
                continue

            material = materials_dict.get(mat_id, {})
            color = material_to_color(material)

            # Fill cell with color
            img[i * cell_size:(i + 1) * cell_size,
                j * cell_size:(j + 1) * cell_size] = color

    return img


def image_to_base64(img_array: np.ndarray) -> str:
    """Convert numpy array to base64-encoded PNG."""
    img_uint8 = (img_array * 255).astype(np.uint8)
    img = Image.fromarray(img_uint8, mode='RGB')

    buffer = io.BytesIO()
    img.save(buffer, format='PNG')
    buffer.seek(0)

    return base64.b64encode(buffer.read()).decode('utf-8')


def fill_missing_images(custom_data_path: Path, materials_dict: Dict) -> int:
    """Fill missing images in custom_data file. Returns count of filled entries."""
    with open(custom_data_path) as f:
        data = json.load(f)

    filled_count = 0

    for entry in data.get('training_data', []):
        if entry.get('image_base64'):
            continue  # Already has image

        recipe = entry.get('recipe', {})
        if not recipe:
            continue

        # Reconstruct grid from recipe
        grid = recipe_to_grid(recipe, materials_dict)

        # Check if grid has any materials
        has_materials = any(cell is not None for row in grid for cell in row)
        if not has_materials:
            continue

        # Generate image
        img_array = grid_to_image(grid, materials_dict)
        img_base64 = image_to_base64(img_array)

        entry['image_base64'] = img_base64
        filled_count += 1

    # Save updated file
    with open(custom_data_path, 'w') as f:
        json.dump(data, f, indent=2)

    return filled_count


def main():
    print("=" * 60)
    print("FILL MISSING IMAGES")
    print("=" * 60)

    script_dir = Path(__file__).parent
    training_dir = script_dir / "Synthetic_Training"

    # Load materials (relative to repo root)
    repo_root = script_dir.parent.parent.parent  # Game-1/
    materials_path = repo_root / "Game-1-modular" / "items.JSON" / "items-materials-1.JSON"
    if not materials_path.exists():
        print(f"Error: Materials file not found: {materials_path}")
        return

    materials_dict = load_materials(materials_path)
    print(f"Loaded {len(materials_dict)} materials")

    # Process VLM disciplines
    for discipline in ['smithing', 'adornment']:
        custom_data_path = training_dir / f"{discipline}_custom_data.json"

        if not custom_data_path.exists():
            print(f"\nSkipping {discipline}: file not found")
            continue

        # Count before
        with open(custom_data_path) as f:
            data = json.load(f)
        entries = data.get('training_data', [])
        missing_before = sum(1 for e in entries if not e.get('image_base64'))

        print(f"\n{discipline.upper()}:")
        print(f"  Total entries: {len(entries)}")
        print(f"  Missing images: {missing_before}")

        if missing_before == 0:
            print("  All entries have images!")
            continue

        # Fill missing
        filled = fill_missing_images(custom_data_path, materials_dict)
        print(f"  Filled: {filled} entries")

        # Verify
        with open(custom_data_path) as f:
            data = json.load(f)
        entries = data.get('training_data', [])
        missing_after = sum(1 for e in entries if not e.get('image_base64'))
        print(f"  Still missing: {missing_after}")

    print("\n" + "=" * 60)
    print("COMPLETE")
    print("=" * 60)


if __name__ == "__main__":
    main()

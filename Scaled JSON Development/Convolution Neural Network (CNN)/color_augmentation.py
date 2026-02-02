"""
Color Augmentation Module for CNN Training

Provides saturation/value variation augmentation to combat material overfitting.
The goal is to teach the CNN to recognize material PATTERNS and CATEGORIES
rather than memorizing exact RGB values.

Key Design Principles:
1. HUE stays CONSTANT - it encodes CATEGORY which is critical
2. VALUE (brightness) is varied - simulates materials at different tiers within category
3. SATURATION is varied - simulates materials with different tag combinations
4. This simulates "new materials" that belong to the same category but have different properties

Color Encoding Reference (from crafting_classifier.py):
- HUE = Category (metal=210°, wood=30°, stone=0°, monster_drop=300°)
- VALUE = Tier (T1=0.50, T2=0.65, T3=0.80, T4=0.95)
- SATURATION = Tags (stone=0.2, base=0.6, +0.2 legendary/mythical, +0.1 magical/ancient)

Usage:
    augmentor = ColorAugmentor(materials_dict)
    rgb_color = augmentor.material_to_color(material_id)

Created: 2026-02-02
Updated: 2026-02-02 - Fixed to vary saturation/value instead of hue
"""

import numpy as np
from colorsys import hsv_to_rgb, rgb_to_hsv
from typing import Dict, Optional, Tuple
import random


class ColorAugmentor:
    """
    Applies controlled saturation/value variation to material colors during CNN training.

    The variations are designed to:
    - Simulate new materials within the same category
    - Prevent CNN from memorizing exact color values
    - Maintain category distinctiveness (HUE stays constant)

    IMPORTANT: Hue is NOT varied because it encodes category, which must be preserved.
    """

    # Base category hues (same as MaterialColorEncoder) - NEVER VARIED
    CATEGORY_HUES = {
        'metal': 210,
        'wood': 30,
        'stone': 0,
        'monster_drop': 300,
        'gem': 280,
        'herb': 120,
        'fabric': 45,
    }

    # Elemental hues - NEVER VARIED
    ELEMENT_HUES = {
        'fire': 0, 'water': 210, 'earth': 120, 'air': 60,
        'lightning': 270, 'ice': 180, 'light': 45,
        'dark': 280, 'void': 290, 'chaos': 330,
    }

    # Tier to value mapping (base values)
    TIER_VALUES = {1: 0.50, 2: 0.65, 3: 0.80, 4: 0.95}

    # =========================================================================
    # SATURATION AND VALUE VARIATION RANGES
    # =========================================================================
    # These simulate materials with different tiers and tag combinations
    # within the same category.
    #
    # VALUE variation: Simulates different tiers (±0.10 allows ~1 tier shift)
    # SATURATION variation: Simulates different tag combinations

    # Value (tier/brightness) variation - significant to simulate tier differences
    VALUE_VARIATION = (-0.10, 0.10)  # Can shift by ~1 tier equivalent

    # Saturation (tag) variation - moderate to simulate different tag combos
    SATURATION_VARIATION = (-0.15, 0.15)

    def __init__(self, materials_dict: Dict, augmentation_enabled: bool = True):
        """
        Args:
            materials_dict: Dict of {material_id: material_data} from JSON
            augmentation_enabled: If False, produces exact colors (for validation set)
        """
        self.materials_dict = materials_dict
        self.augmentation_enabled = augmentation_enabled

    def get_base_hsv(self, material_id: str) -> Tuple[float, float, float]:
        """Get the base HSV values for a material (no augmentation)."""
        if material_id is None or material_id not in self.materials_dict:
            return (0, 0, 0)  # Black for missing

        material = self.materials_dict[material_id]
        category = material.get('category', 'unknown')
        tier = material.get('tier', 1)
        tags = material.get('metadata', {}).get('tags', [])

        # Determine base hue from category (CONSTANT - never varied)
        if category == 'elemental':
            hue = 280  # Default elemental
            for tag in tags:
                if tag in self.ELEMENT_HUES:
                    hue = self.ELEMENT_HUES[tag]
                    break
        else:
            hue = self.CATEGORY_HUES.get(category, 0)

        # Determine base value from tier
        value = self.TIER_VALUES.get(tier, 0.5)

        # Determine base saturation from tags
        base_saturation = 0.6
        if category == 'stone':
            base_saturation = 0.2
        if 'legendary' in tags or 'mythical' in tags:
            base_saturation = min(1.0, base_saturation + 0.2)
        elif 'magical' in tags or 'ancient' in tags:
            base_saturation = min(1.0, base_saturation + 0.1)

        return (hue, base_saturation, value)

    def material_to_color(self, material_id: Optional[str]) -> np.ndarray:
        """
        Convert material to RGB color, WITH saturation/value variation if enabled.

        Args:
            material_id: Material ID string, or None for empty cell

        Returns:
            np.ndarray of shape (3,) with RGB values in [0, 1]
        """
        if material_id is None:
            return np.array([0.0, 0.0, 0.0])

        if material_id not in self.materials_dict:
            return np.array([0.3, 0.3, 0.3])  # Unknown = gray

        base_hue, base_sat, base_val = self.get_base_hsv(material_id)

        if self.augmentation_enabled:
            # HUE stays CONSTANT - category must be preserved
            hue = base_hue

            # Vary VALUE (tier/brightness) - simulate different tiers
            val_offset = random.uniform(*self.VALUE_VARIATION)
            value = max(0.30, min(0.95, base_val + val_offset))

            # Vary SATURATION (tags) - simulate different tag combinations
            sat_offset = random.uniform(*self.SATURATION_VARIATION)
            saturation = max(0.10, min(1.0, base_sat + sat_offset))
        else:
            hue = base_hue
            saturation = base_sat
            value = base_val

        # Convert HSV to RGB
        rgb = hsv_to_rgb(hue / 360.0, saturation, value)
        return np.array(rgb)

    def material_to_color_exact(self, material_id: Optional[str]) -> np.ndarray:
        """Get exact color without augmentation (for reference/validation)."""
        orig_enabled = self.augmentation_enabled
        self.augmentation_enabled = False
        result = self.material_to_color(material_id)
        self.augmentation_enabled = orig_enabled
        return result


# Backwards compatibility alias
HueVariationAugmentor = ColorAugmentor


class MultiPassAugmentor:
    """
    Generates multiple augmented versions of the same recipe with saturation/value variations.
    This creates a richer training set that teaches the CNN to generalize to new materials.
    """

    def __init__(self, materials_dict: Dict, num_augment_passes: int = 3):
        """
        Args:
            materials_dict: Dict of {material_id: material_data}
            num_augment_passes: Number of augmented versions to generate per recipe
        """
        self.materials_dict = materials_dict
        self.num_augment_passes = num_augment_passes
        self.augmentor = ColorAugmentor(materials_dict, augmentation_enabled=True)
        self.exact_augmentor = ColorAugmentor(materials_dict, augmentation_enabled=False)

    def augment_grid(self, grid, grid_to_image_fn) -> list:
        """
        Generate multiple augmented images from a single grid.

        Args:
            grid: 9x9 list of material IDs
            grid_to_image_fn: Function that takes (grid, color_fn) and returns image

        Returns:
            List of augmented images (1 exact + N augmented)
        """
        images = []

        # Original exact colors
        img_exact = grid_to_image_fn(grid, self.exact_augmentor.material_to_color)
        images.append(img_exact)

        # Multiple augmented versions (varied saturation/value)
        for _ in range(self.num_augment_passes):
            img_varied = grid_to_image_fn(grid, self.augmentor.material_to_color)
            images.append(img_varied)

        return images

    # Backwards compatibility
    def augment_grid_multi_hue(self, grid, grid_to_image_fn) -> list:
        """Deprecated: Use augment_grid instead."""
        return self.augment_grid(grid, grid_to_image_fn)


def load_materials_from_multiple_sources(paths: list) -> Dict:
    """
    Load and merge materials from multiple JSON files.
    Useful for including Update-1, Update-2, etc.

    Args:
        paths: List of paths to materials JSON files

    Returns:
        Merged dict of {material_id: material_data}
    """
    import json

    merged = {}
    for path in paths:
        try:
            with open(path, 'r') as f:
                data = json.load(f)
            for mat in data.get('materials', []):
                mat_id = mat.get('materialId')
                if mat_id:
                    merged[mat_id] = mat
            print(f"  Loaded {len(data.get('materials', []))} materials from {path}")
        except Exception as e:
            print(f"  Warning: Could not load {path}: {e}")

    return merged


def load_placements_from_multiple_sources(paths: list) -> list:
    """
    Load and merge placements from multiple JSON files.
    Useful for including Update-1, Update-2, etc.

    Args:
        paths: List of paths to placements JSON files

    Returns:
        Merged list of placements
    """
    import json

    merged = []
    for path in paths:
        try:
            with open(path, 'r') as f:
                data = json.load(f)
            placements = data.get('placements', [])
            merged.extend(placements)
            print(f"  Loaded {len(placements)} placements from {path}")
        except Exception as e:
            print(f"  Warning: Could not load {path}: {e}")

    return merged


# Test the augmentor
if __name__ == "__main__":
    import json

    # Load materials
    MATERIALS_PATH = "../../Game-1-modular/items.JSON/items-materials-1.JSON"

    try:
        with open(MATERIALS_PATH, 'r') as f:
            data = json.load(f)
        materials_dict = {m['materialId']: m for m in data['materials']}
        print(f"Loaded {len(materials_dict)} materials\n")
    except Exception as e:
        print(f"Error loading materials: {e}")
        exit(1)

    # Test augmentor
    augmentor = ColorAugmentor(materials_dict, augmentation_enabled=True)
    exact = ColorAugmentor(materials_dict, augmentation_enabled=False)

    # Show variations for sample materials
    test_materials = ['iron_ingot', 'oak_plank', 'obsidian', 'fire_crystal', 'wolf_pelt']

    print("Saturation/Value Variation Test (3 samples each):\n")
    print(f"{'Material':<20} {'Exact RGB':<25} {'Augmented RGB samples...'}")
    print("-" * 100)

    for mat_id in test_materials:
        exact_rgb = exact.material_to_color(mat_id)
        exact_str = f"({exact_rgb[0]:.2f}, {exact_rgb[1]:.2f}, {exact_rgb[2]:.2f})"

        varied_strs = []
        for _ in range(3):
            varied = augmentor.material_to_color(mat_id)
            varied_strs.append(f"({varied[0]:.2f}, {varied[1]:.2f}, {varied[2]:.2f})")

        print(f"{mat_id:<20} {exact_str:<25} {' | '.join(varied_strs)}")

    print("\n\nCategory Hues (CONSTANT - never varied):")
    print("-" * 50)
    for cat, hue in ColorAugmentor.CATEGORY_HUES.items():
        print(f"  {cat:<15}: {hue}°")

    print("\n\nAugmentation Ranges:")
    print("-" * 50)
    print(f"  VALUE (tier):       {ColorAugmentor.VALUE_VARIATION}")
    print(f"  SATURATION (tags):  {ColorAugmentor.SATURATION_VARIATION}")

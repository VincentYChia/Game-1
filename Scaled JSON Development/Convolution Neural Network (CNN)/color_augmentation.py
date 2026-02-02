"""
Color Augmentation Module for CNN Training

Provides hue variation augmentation to combat material overfitting.
The goal is to teach the CNN to recognize material PATTERNS and CATEGORIES
rather than memorizing exact RGB values.

Key Design Principles:
1. Hue variations stay WITHIN category boundaries (metals stay blue-ish, wood stays orange-ish)
2. Tier brightness (Value) preserved - tier info is semantically important
3. Category-specific variation ranges prevent cross-category confusion
4. Elemental materials get element-specific variation ranges

Usage:
    augmentor = HueVariationAugmentor(materials_dict)
    rgb_color = augmentor.material_to_color_augmented(material_id)

Created: 2026-02-02
"""

import numpy as np
from colorsys import hsv_to_rgb, rgb_to_hsv
from typing import Dict, Optional, Tuple
import random


class HueVariationAugmentor:
    """
    Applies controlled hue variation to material colors during CNN training.

    The variations are designed to:
    - Simulate new materials that would be valid substitutes
    - Prevent CNN from memorizing exact color values
    - Maintain category distinctiveness (metals still look like metals)
    """

    # Base category hues (same as MaterialColorEncoder)
    CATEGORY_HUES = {
        'metal': 210,
        'wood': 30,
        'stone': 0,
        'monster_drop': 300,
        'gem': 280,
        'herb': 120,
        'fabric': 45,
    }

    # Elemental hues
    ELEMENT_HUES = {
        'fire': 0, 'water': 210, 'earth': 120, 'air': 60,
        'lightning': 270, 'ice': 180, 'light': 45,
        'dark': 280, 'void': 290, 'chaos': 330,
    }

    # Tier to value mapping
    TIER_VALUES = {1: 0.50, 2: 0.65, 3: 0.80, 4: 0.95}

    # =========================================================================
    # CATEGORY-SPECIFIC HUE VARIATION RANGES
    # =========================================================================
    # These ranges are carefully chosen to:
    # 1. Allow significant variation within each category
    # 2. NOT overlap with other categories
    # 3. Create "virtual" materials that could plausibly exist
    #
    # Format: (min_offset, max_offset) from base hue
    # Positive = clockwise on color wheel, Negative = counter-clockwise

    CATEGORY_HUE_RANGES = {
        # Metal (base 210, cyan/blue) - range 180-240 (avoiding wood at 30 and stone at 0)
        'metal': (-30, 30),

        # Wood (base 30, orange/brown) - range 10-60 (avoiding stone/red at 0)
        'wood': (-20, 30),

        # Stone (base 0, red/gray) - range 340-20 (wrapping, low sat makes it gray anyway)
        'stone': (-20, 20),

        # Monster drops (base 300, magenta/purple) - range 280-340
        'monster_drop': (-20, 40),

        # Gem (base 280) - range 260-300
        'gem': (-20, 20),

        # Herb (base 120, green) - range 100-140
        'herb': (-20, 20),

        # Fabric (base 45) - range 30-60
        'fabric': (-15, 15),
    }

    # Elemental-specific hue ranges (narrower to maintain element identity)
    ELEMENT_HUE_RANGES = {
        'fire': (-15, 15),      # Stay warm red/orange
        'water': (-20, 20),     # Stay blue
        'earth': (-20, 20),     # Stay green/brown
        'air': (-20, 20),       # Stay yellow/light
        'lightning': (-20, 20), # Stay purple
        'ice': (-20, 20),       # Stay cyan
        'light': (-15, 15),     # Stay yellow-orange
        'dark': (-15, 15),      # Stay dark purple
        'void': (-15, 15),      # Stay void purple
        'chaos': (-30, 30),     # Chaos gets more variation (fitting!)
    }

    # Saturation and value variation ranges (subtle)
    SATURATION_RANGE = (-0.1, 0.15)  # Slight variation
    VALUE_RANGE = (-0.05, 0.05)       # Very subtle - preserve tier info

    def __init__(self, materials_dict: Dict, augmentation_enabled: bool = True):
        """
        Args:
            materials_dict: Dict of {material_id: material_data} from JSON
            augmentation_enabled: If False, produces exact colors (for validation set)
        """
        self.materials_dict = materials_dict
        self.augmentation_enabled = augmentation_enabled

    def get_hue_range_for_material(self, material: Dict) -> Tuple[float, float]:
        """Get appropriate hue variation range for a material."""
        category = material.get('category', 'unknown')
        tags = material.get('metadata', {}).get('tags', [])

        # Elementals use element-specific ranges
        if category == 'elemental':
            for tag in tags:
                if tag in self.ELEMENT_HUE_RANGES:
                    return self.ELEMENT_HUE_RANGES[tag]
            # Default elemental range
            return (-15, 15)

        # Other categories use category ranges
        return self.CATEGORY_HUE_RANGES.get(category, (-15, 15))

    def get_base_hsv(self, material_id: str) -> Tuple[float, float, float]:
        """Get the base HSV values for a material (no augmentation)."""
        if material_id is None or material_id not in self.materials_dict:
            return (0, 0, 0)  # Black for missing

        material = self.materials_dict[material_id]
        category = material.get('category', 'unknown')
        tier = material.get('tier', 1)
        tags = material.get('metadata', {}).get('tags', [])

        # Determine base hue
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

        # Determine base saturation
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
        Convert material to RGB color, WITH hue variation if enabled.

        Args:
            material_id: Material ID string, or None for empty cell

        Returns:
            np.ndarray of shape (3,) with RGB values in [0, 1]
        """
        if material_id is None:
            return np.array([0.0, 0.0, 0.0])

        if material_id not in self.materials_dict:
            return np.array([0.3, 0.3, 0.3])  # Unknown = gray

        material = self.materials_dict[material_id]
        base_hue, base_sat, base_val = self.get_base_hsv(material_id)

        if self.augmentation_enabled:
            # Apply hue variation
            hue_min, hue_max = self.get_hue_range_for_material(material)
            hue_offset = random.uniform(hue_min, hue_max)
            hue = (base_hue + hue_offset) % 360

            # Apply subtle saturation variation
            sat_offset = random.uniform(*self.SATURATION_RANGE)
            saturation = max(0.0, min(1.0, base_sat + sat_offset))

            # Apply very subtle value variation (preserve tier mostly)
            val_offset = random.uniform(*self.VALUE_RANGE)
            value = max(0.1, min(1.0, base_val + val_offset))
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


class MultiPassAugmentor:
    """
    Generates multiple augmented versions of the same recipe with different hue variations.
    This creates a richer training set that teaches the CNN to generalize.
    """

    def __init__(self, materials_dict: Dict, num_hue_passes: int = 3):
        """
        Args:
            materials_dict: Dict of {material_id: material_data}
            num_hue_passes: Number of hue-varied versions to generate per recipe
        """
        self.materials_dict = materials_dict
        self.num_hue_passes = num_hue_passes
        self.augmentor = HueVariationAugmentor(materials_dict, augmentation_enabled=True)
        self.exact_augmentor = HueVariationAugmentor(materials_dict, augmentation_enabled=False)

    def augment_grid_multi_hue(self, grid, grid_to_image_fn) -> list:
        """
        Generate multiple hue-varied images from a single grid.

        Args:
            grid: 9x9 list of material IDs
            grid_to_image_fn: Function that takes (grid, color_fn) and returns image

        Returns:
            List of augmented images
        """
        images = []

        # Original exact colors
        img_exact = grid_to_image_fn(grid, self.exact_augmentor.material_to_color)
        images.append(img_exact)

        # Multiple hue-varied versions
        for _ in range(self.num_hue_passes):
            img_varied = grid_to_image_fn(grid, self.augmentor.material_to_color)
            images.append(img_varied)

        return images


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
    augmentor = HueVariationAugmentor(materials_dict, augmentation_enabled=True)
    exact = HueVariationAugmentor(materials_dict, augmentation_enabled=False)

    # Show variations for sample materials
    test_materials = ['iron_ingot', 'oak_plank', 'obsidian', 'fire_crystal', 'wolf_pelt']

    print("Hue Variation Test (5 samples each):\n")
    print(f"{'Material':<20} {'Exact RGB':<25} {'Varied RGB samples...'}")
    print("-" * 100)

    for mat_id in test_materials:
        exact_rgb = exact.material_to_color(mat_id)
        exact_str = f"({exact_rgb[0]:.2f}, {exact_rgb[1]:.2f}, {exact_rgb[2]:.2f})"

        varied_strs = []
        for _ in range(3):
            varied = augmentor.material_to_color(mat_id)
            varied_strs.append(f"({varied[0]:.2f}, {varied[1]:.2f}, {varied[2]:.2f})")

        print(f"{mat_id:<20} {exact_str:<25} {' | '.join(varied_strs)}")

    print("\n\nCategory Hue Ranges:")
    print("-" * 50)
    for cat, (min_off, max_off) in HueVariationAugmentor.CATEGORY_HUE_RANGES.items():
        base = HueVariationAugmentor.CATEGORY_HUES.get(cat, 0)
        print(f"  {cat:<15}: {base}° ± ({min_off}, {max_off}) = [{(base+min_off)%360}° - {(base+max_off)%360}°]")

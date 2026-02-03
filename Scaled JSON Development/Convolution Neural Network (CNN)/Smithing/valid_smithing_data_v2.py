"""
Smithing Recipe CNN Dataset Generator v2

SELF-CONTAINED: All color augmentation logic is integrated directly.

Key Design Principles:
1. HUE stays CONSTANT - it encodes CATEGORY which is critical for classification
2. VALUE (brightness) is varied - simulates materials at different tiers within category
3. SATURATION is varied - simulates materials with different tag combinations

Color Encoding Reference:
- HUE = Category (metal=210°, wood=30°, stone=0°, monster_drop=300°)
- VALUE = Tier (T1=0.50, T2=0.65, T3=0.80, T4=0.95)
- SATURATION = Tags (stone=0.2, base=0.6, +0.2 legendary/mythical, +0.1 magical/ancient)

Shape Encoding:
- Each category has a distinct shape pattern
- Tier determines how much of the cell is filled

Updates from v1:
- Saturation/value variation augmentation to combat material overfitting
- Support for Update-1 and Update-2 folders
- Multiple augmentation passes per recipe for richer training data
- Category-based shape indicators (metal=square, wood=lines, stone=X, etc.)
- Tier-based fill size (T1=1x1, T2=2x2, T3=3x3, T4=4x4)

Created: 2026-02-02
Updated: 2026-02-02 - Integrated color augmentation directly (no external imports)
"""

import json
import numpy as np
from colorsys import hsv_to_rgb
from pathlib import Path
import copy
import random
from typing import Dict, List, Optional, Tuple, Set


# ============================================================================
# INTEGRATED COLOR AUGMENTOR
# ============================================================================

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
    # VALUE variation: Simulates different tiers (±0.10 allows ~1 tier shift)
    VALUE_VARIATION = (-0.10, 0.10)

    # SATURATION variation: Simulates different tag combinations
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


# ============================================================================
# DATA LOADING UTILITIES
# ============================================================================

def load_materials_from_multiple_sources(paths: list) -> Dict:
    """
    Load and merge materials from multiple JSON files.
    Useful for including Update-1, Update-2, etc.

    Args:
        paths: List of paths to materials JSON files

    Returns:
        Merged dict of {material_id: material_data}
    """
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


# ============================================================================
# RECIPE DATA PROCESSOR
# ============================================================================

class RecipeDataProcessorV2:
    """
    Processes smithing recipes and materials into CNN training data.
    Version 2: With saturation/value augmentation + category shapes + tier fill.
    """

    # =========================================================================
    # CATEGORY SHAPE MASKS (4x4 binary patterns)
    # =========================================================================
    # Each category has a distinct visual shape to help CNN learn category
    # even if colors are slightly varied.
    #
    # 1 = filled pixel, 0 = background (black)

    CATEGORY_SHAPES = {
        # Metal: Full square (solid, industrial)
        'metal': np.array([
            [1, 1, 1, 1],
            [1, 1, 1, 1],
            [1, 1, 1, 1],
            [1, 1, 1, 1]
        ], dtype=np.float32),

        # Wood: Horizontal lines (grain pattern)
        'wood': np.array([
            [1, 1, 1, 1],
            [0, 0, 0, 0],
            [1, 1, 1, 1],
            [0, 0, 0, 0]
        ], dtype=np.float32),

        # Stone: X pattern (angular, rocky)
        'stone': np.array([
            [1, 0, 0, 1],
            [0, 1, 1, 0],
            [0, 1, 1, 0],
            [1, 0, 0, 1]
        ], dtype=np.float32),

        # Monster drop: Diamond shape (organic)
        'monster_drop': np.array([
            [0, 1, 1, 0],
            [1, 1, 1, 1],
            [1, 1, 1, 1],
            [0, 1, 1, 0]
        ], dtype=np.float32),

        # Elemental: Plus/cross pattern (radiating energy)
        'elemental': np.array([
            [0, 1, 1, 0],
            [1, 1, 1, 1],
            [1, 1, 1, 1],
            [0, 1, 1, 0]
        ], dtype=np.float32),
    }

    # Default shape for unknown categories
    DEFAULT_SHAPE = np.ones((4, 4), dtype=np.float32)

    # Tier fill sizes (centered in 4x4 cell)
    # T1=1x1, T2=2x2, T3=3x3, T4=full 4x4
    TIER_FILL_SIZES = {1: 1, 2: 2, 3: 3, 4: 4}

    def __init__(self, materials_dict: dict, placements: list, num_augment_passes: int = 3):
        """
        Args:
            materials_dict: Dict of {material_id: material_data}
            placements: List of placement objects
            num_augment_passes: Number of augmented versions per recipe (default 3)
        """
        self.materials_dict = materials_dict
        self.placements = placements
        self.num_augment_passes = num_augment_passes

        # Create augmentors (integrated, not imported)
        self.augmentor = ColorAugmentor(materials_dict, augmentation_enabled=True)
        self.exact_augmentor = ColorAugmentor(materials_dict, augmentation_enabled=False)

        print(f"Initialized with {len(materials_dict)} materials")
        print(f"Initialized with {len(placements)} placements")
        print(f"Augmentation passes per recipe: {num_augment_passes}")

    @classmethod
    def from_paths(cls, materials_paths: list, placements_paths: list, num_augment_passes: int = 3):
        """
        Create processor from file paths, merging multiple sources.

        Args:
            materials_paths: List of paths to materials JSON files
            placements_paths: List of paths to placements JSON files
            num_augment_passes: Number of augmented versions per recipe
        """
        print("\n=== Loading Materials ===")
        materials_dict = load_materials_from_multiple_sources(materials_paths)

        print("\n=== Loading Placements ===")
        placements = load_placements_from_multiple_sources(placements_paths)

        return cls(materials_dict, placements, num_augment_passes)

    def get_shape_mask(self, material_id: str) -> np.ndarray:
        """Get the 4x4 shape mask for a material's category."""
        if material_id is None or material_id not in self.materials_dict:
            return self.DEFAULT_SHAPE

        category = self.materials_dict[material_id].get('category', 'unknown')
        return self.CATEGORY_SHAPES.get(category, self.DEFAULT_SHAPE)

    def get_tier_fill_mask(self, material_id: str, cell_size: int = 4) -> np.ndarray:
        """
        Get a mask that limits fill based on tier.
        T1=1x1 center, T2=2x2 center, T3=3x3 center, T4=full 4x4
        """
        if material_id is None or material_id not in self.materials_dict:
            return np.zeros((cell_size, cell_size), dtype=np.float32)

        tier = self.materials_dict[material_id].get('tier', 1)
        fill_size = self.TIER_FILL_SIZES.get(tier, 4)

        mask = np.zeros((cell_size, cell_size), dtype=np.float32)
        offset = (cell_size - fill_size) // 2
        mask[offset:offset+fill_size, offset:offset+fill_size] = 1.0

        return mask

    def is_station(self, recipe_id: str) -> bool:
        """Check if recipe is a station/bench (ends with _t1, _t2, _t3, _t4)"""
        return any(recipe_id.endswith(f'_t{i}') for i in range(1, 5))

    def placement_to_grid(self, placement: dict) -> list:
        """Convert placement to centered 9x9 grid"""
        grid = [[None] * 9 for _ in range(9)]

        # Determine grid size from metadata
        grid_size_str = placement['metadata'].get('gridSize', '9x9')
        recipe_size = int(grid_size_str.split('x')[0])

        # Find actual bounding box of placements
        positions = []
        for pos_str in placement['placementMap'].keys():
            y_idx, x_idx = map(int, pos_str.split(','))
            positions.append((y_idx, x_idx))

        if not positions:
            return grid

        # Calculate actual placement dimensions
        min_y = min(p[0] for p in positions)
        max_y = max(p[0] for p in positions)
        min_x = min(p[1] for p in positions)
        max_x = max(p[1] for p in positions)
        actual_height = max_y - min_y + 1
        actual_width = max_x - min_x + 1

        # Use actual dimensions for centering
        offset_y = (9 - actual_height) // 2
        offset_x = (9 - actual_width) // 2

        # Parse placement map and center on 9x9 grid
        for pos_str, material_id in placement['placementMap'].items():
            y_idx, x_idx = map(int, pos_str.split(','))
            final_y = offset_y + (y_idx - min_y)
            final_x = offset_x + (x_idx - min_x)

            if 0 <= final_y < 9 and 0 <= final_x < 9:
                grid[final_y][final_x] = material_id
            else:
                print(f"Warning: Position ({y_idx},{x_idx}) exceeds 9x9 grid bounds")

        return grid

    def grid_to_image(self, grid: list, color_fn, cell_size: int = 4,
                      use_shapes: bool = True, use_tier_fill: bool = True) -> np.ndarray:
        """
        Convert 9x9 grid to 36x36 RGB image using provided color function.

        Args:
            grid: 9x9 list of material IDs
            color_fn: Function that takes material_id and returns RGB array
            cell_size: Pixels per grid cell (default 4)
            use_shapes: Apply category-based shape masks
            use_tier_fill: Apply tier-based fill size

        Returns:
            36x36x3 RGB image array
        """
        img_size = 9 * cell_size
        img = np.zeros((img_size, img_size, 3), dtype=np.float32)

        for i in range(9):
            for j in range(9):
                material_id = grid[i][j]

                if material_id is None:
                    # Empty cell = black
                    continue

                # Get base color from color function (may be augmented)
                color = color_fn(material_id)

                # Start with full cell
                cell = np.zeros((cell_size, cell_size, 3), dtype=np.float32)

                # Apply shape mask based on category
                if use_shapes:
                    shape_mask = self.get_shape_mask(material_id)
                else:
                    shape_mask = np.ones((cell_size, cell_size), dtype=np.float32)

                # Apply tier fill mask
                if use_tier_fill:
                    tier_mask = self.get_tier_fill_mask(material_id, cell_size)
                else:
                    tier_mask = np.ones((cell_size, cell_size), dtype=np.float32)

                # Combined mask: shape AND tier
                combined_mask = shape_mask * tier_mask

                # Apply color through mask
                for c in range(3):
                    cell[:, :, c] = color[c] * combined_mask

                # Place cell in image
                img[i * cell_size:(i + 1) * cell_size,
                    j * cell_size:(j + 1) * cell_size] = cell

        return img

    def flip_grid_horizontal(self, grid: list) -> list:
        """Flip 9x9 grid horizontally"""
        return [row[::-1] for row in grid]

    def find_substitutable_materials(self, material_id: str) -> list:
        """Find all materials that can substitute for the given material"""
        if material_id is None or material_id not in self.materials_dict:
            return []

        base_mat = self.materials_dict[material_id]
        base_tier = base_mat.get('tier', 1)
        base_tags = set(base_mat.get('metadata', {}).get('tags', []))
        base_category = base_mat.get('category', 'unknown')

        # Check for refined/basic constraint
        is_refined = 'refined' in base_tags
        is_basic = 'basic' in base_tags

        substitutes = []

        for mat_id, mat in self.materials_dict.items():
            if mat_id == material_id:
                continue

            # Must be same category
            if mat.get('category') != base_category:
                continue

            mat_tags = set(mat.get('metadata', {}).get('tags', []))
            mat_tier = mat.get('tier', 1)

            # HARD RULE: refined/basic must match
            if is_refined and 'refined' not in mat_tags:
                continue
            if is_basic and 'basic' not in mat_tags:
                continue

            # Rule 1: All tags match (any tier difference OK)
            if mat_tags == base_tags:
                substitutes.append(mat_id)
                continue

            # Rule 2: +/-1 tier and at least 2 matching tags
            if abs(mat_tier - base_tier) <= 1:
                matching_tags = base_tags & mat_tags
                if len(matching_tags) >= 2:
                    substitutes.append(mat_id)

        return substitutes

    def augment_recipe_materials(self, grid: list) -> list:
        """
        Generate variants by substituting materials (original augmentation).
        Returns list of grids.
        """
        variants = [grid]

        # Add horizontal flip
        flipped = self.flip_grid_horizontal(grid)
        variants.append(flipped)

        # Find unique materials in grid
        unique_materials = set()
        for row in grid:
            for mat in row:
                if mat is not None:
                    unique_materials.add(mat)

        # Generate substitution variants
        for material_id in unique_materials:
            substitutes = self.find_substitutable_materials(material_id)

            for sub_mat in substitutes:
                # Create variant by replacing ALL instances
                new_grid = copy.deepcopy(grid)
                for i in range(9):
                    for j in range(9):
                        if new_grid[i][j] == material_id:
                            new_grid[i][j] = sub_mat
                variants.append(new_grid)

                # Also add flipped version
                variants.append(self.flip_grid_horizontal(new_grid))

        # Remove duplicates
        unique_variants = []
        seen = set()
        for variant in variants:
            variant_tuple = tuple(tuple(row) for row in variant)
            if variant_tuple not in seen:
                seen.add(variant_tuple)
                unique_variants.append(variant)

        return unique_variants

    def augment_with_color_variation(self, grids: list, cell_size: int = 4) -> np.ndarray:
        """
        Convert grids to images with saturation/value variation augmentation.

        For each grid:
        - 1 image with exact colors (with shapes and tier fill)
        - N images with varied saturation/value (simulating new materials)

        Note: HUE is NOT varied - it encodes category which must be preserved.
        Only SATURATION (tags) and VALUE (tier) are varied.

        Args:
            grids: List of 9x9 grids
            cell_size: Pixels per cell

        Returns:
            Array of images
        """
        all_images = []

        for grid in grids:
            # Exact colors (1 image) - with shapes and tier fill
            img_exact = self.grid_to_image(
                grid,
                self.exact_augmentor.material_to_color,
                cell_size,
                use_shapes=True,
                use_tier_fill=True
            )
            all_images.append(img_exact)

            # Augmented colors (num_augment_passes images)
            for _ in range(self.num_augment_passes):
                img_varied = self.grid_to_image(
                    grid,
                    self.augmentor.material_to_color,
                    cell_size,
                    use_shapes=True,
                    use_tier_fill=True
                )
                all_images.append(img_varied)

        return np.array(all_images, dtype=np.float32)

    # Backwards compatibility alias
    def augment_with_hue_variation(self, grids: list, cell_size: int = 4) -> np.ndarray:
        """Deprecated: Use augment_with_color_variation instead."""
        return self.augment_with_color_variation(grids, cell_size)

    def create_valid_dataset(self, cell_size: int = 4) -> tuple:
        """
        Create complete dataset of valid recipes with augmentation.

        Returns:
            (images_array, grids_list)
        """
        all_grids = []

        print("\n=== Processing Recipes ===")

        # Filter out stations
        non_station_placements = [
            p for p in self.placements
            if not self.is_station(p['recipeId'])
        ]

        print(f"Total placements: {len(self.placements)}")
        print(f"Stations excluded: {len(self.placements) - len(non_station_placements)}")
        print(f"Processing: {len(non_station_placements)} non-station recipes\n")

        for placement in non_station_placements:
            recipe_id = placement['recipeId']

            # Convert to grid
            grid = self.placement_to_grid(placement)

            # Augment with material substitution
            variants = self.augment_recipe_materials(grid)

            print(f"  {recipe_id}: {len(variants)} material variants")
            all_grids.extend(variants)

        print(f"\n=== Material Augmentation Complete ===")
        print(f"Base recipes: {len(non_station_placements)}")
        print(f"Material-augmented grids: {len(all_grids)}")

        # Now apply color variation (saturation/value) and convert to images
        print(f"\n=== Applying Color Variation (Sat/Val) ===")
        print(f"Augmentation passes per grid: {self.num_augment_passes}")
        print(f"Using category shapes: True")
        print(f"Using tier fill: True")
        expected_images = len(all_grids) * (1 + self.num_augment_passes)
        print(f"Expected total images: {expected_images}")

        images = self.augment_with_color_variation(all_grids, cell_size)

        print(f"Generated images: {len(images)}")

        return images, all_grids

    def analyze_augmentation_potential(self):
        """Analyze how many substitutions are possible per material"""
        print("\n=== Augmentation Analysis ===")

        # Count materials used in recipes
        materials_in_recipes = set()
        for placement in self.placements:
            if not self.is_station(placement['recipeId']):
                for material_id in placement['placementMap'].values():
                    materials_in_recipes.add(material_id)

        print(f"Unique materials in recipes: {len(materials_in_recipes)}")

        sub_counts = []
        for mat_id in sorted(materials_in_recipes):
            subs = self.find_substitutable_materials(mat_id)
            sub_counts.append(len(subs))
            if subs:
                print(f"  {mat_id}: {len(subs)} substitutes")

        if sub_counts:
            print(f"\nSubstitution stats:")
            print(f"  Total materials with substitutes: {sum(1 for c in sub_counts if c > 0)}")
            print(f"  Average substitutes: {np.mean(sub_counts):.1f}")
            print(f"  Max substitutes: {max(sub_counts)}")


# ============================================================================
# INVALID RECIPE GENERATOR
# ============================================================================

class InvalidRecipeGenerator:
    """Generates invalid recipe examples for training"""

    def __init__(self, processor: RecipeDataProcessorV2):
        self.processor = processor
        self.materials_dict = processor.materials_dict

        # Get materials used in non-station recipes
        self.recipe_materials = set()
        for placement in processor.placements:
            if not processor.is_station(placement['recipeId']):
                for material_id in placement['placementMap'].values():
                    self.recipe_materials.add(material_id)

        self.all_materials = list(self.recipe_materials)
        print(f"\nInvalid generator using {len(self.all_materials)} materials")

    def generate_random(self) -> list:
        """Generate completely random recipe (2-40 materials)"""
        num_filled = random.randint(2, 40)
        grid = [[None] * 9 for _ in range(9)]

        all_positions = [(i, j) for i in range(9) for j in range(9)]
        positions = random.sample(all_positions, min(num_filled, 81))

        for i, j in positions:
            grid[i][j] = random.choice(self.all_materials)

        return grid

    def corrupt_valid(self, valid_grid: list) -> list:
        """Corrupt a valid recipe by swapping 1-2 materials"""
        corrupted = copy.deepcopy(valid_grid)

        # Find filled positions
        filled_positions = [
            (i, j) for i in range(9) for j in range(9)
            if corrupted[i][j] is not None
        ]

        if len(filled_positions) < 1:
            return self.generate_random()

        # Mostly 1-2 swaps, occasionally 3-4
        weights = [50, 35, 10, 5]
        num_swaps = random.choices([1, 2, 3, 4], weights=weights)[0]
        num_swaps = min(num_swaps, len(filled_positions))

        swap_positions = random.sample(filled_positions, num_swaps)

        for i, j in swap_positions:
            current = corrupted[i][j]
            available = [m for m in self.all_materials if m != current]
            corrupted[i][j] = random.choice(available)

        return corrupted

    def remove_materials(self, valid_grid: list) -> list:
        """Remove 1-3 materials from valid recipe"""
        incomplete = copy.deepcopy(valid_grid)

        filled_positions = [
            (i, j) for i in range(9) for j in range(9)
            if incomplete[i][j] is not None
        ]

        if len(filled_positions) <= 1:
            return self.generate_random()

        num_remove = min(random.randint(1, 3), len(filled_positions) - 1)
        remove_positions = random.sample(filled_positions, num_remove)

        for i, j in remove_positions:
            incomplete[i][j] = None

        return incomplete

    def generate_batch(self, count: int, valid_grids: list) -> list:
        """Generate batch of invalid recipes"""
        invalid_grids = []

        # 25% random
        num_random = count // 4
        for _ in range(num_random):
            invalid_grids.append(self.generate_random())

        # 50% corrupted
        num_corrupted = count // 2
        for _ in range(num_corrupted):
            base = random.choice(valid_grids)
            invalid_grids.append(self.corrupt_valid(base))

        # 25% incomplete
        num_incomplete = count // 4
        for _ in range(num_incomplete):
            base = random.choice(valid_grids)
            invalid_grids.append(self.remove_materials(base))

        # Fill to exact count
        while len(invalid_grids) < count:
            base = random.choice(valid_grids)
            invalid_grids.append(self.corrupt_valid(base))

        return invalid_grids[:count]

    def create_invalid_dataset(self, valid_grids: list) -> tuple:
        """
        Create invalid dataset with color variation.

        Returns:
            (images_array, grids_list)
        """
        count = len(valid_grids)

        print(f"\n=== Generating Invalid Recipes ===")
        print(f"Target grids: {count}")

        invalid_grids = self.generate_batch(count, valid_grids)

        print(f"Generated: {len(invalid_grids)} invalid grids")
        print(f"  - ~{count // 4} random")
        print(f"  - ~{count // 2} corrupted valid")
        print(f"  - ~{count // 4} incomplete")

        # Apply color variation (saturation/value) with shapes and tier fill
        print(f"\n=== Applying Color Variation to Invalid ===")
        images = self.processor.augment_with_color_variation(invalid_grids)
        print(f"Generated: {len(images)} invalid images")

        return images, invalid_grids


# ============================================================================
# MAIN EXECUTION
# ============================================================================

def get_default_paths():
    """Get default paths for materials and placements including updates."""
    # Determine base path relative to this file
    script_dir = Path(__file__).parent
    game_modular = script_dir.parent.parent.parent / "Game-1-modular"

    materials_paths = [
        game_modular / "items.JSON" / "items-materials-1.JSON",
    ]

    placements_paths = [
        game_modular / "placements.JSON" / "placements-smithing-1.json",  # lowercase .json
    ]

    # Check for Update folders
    for update_name in ["Update-1", "Update-2"]:
        update_dir = game_modular / update_name
        if update_dir.exists():
            # Add any materials files
            for pattern in ["*materials*.JSON", "*materials*.json"]:
                for f in update_dir.glob(pattern):
                    materials_paths.append(f)

            # Add any smithing placements
            for pattern in ["*placements*smithing*.JSON", "*placements*smithing*.json"]:
                for f in update_dir.glob(pattern):
                    placements_paths.append(f)

    return materials_paths, placements_paths


def main():
    """Main execution with color augmentation, shapes, and tier fill"""
    random.seed(42)
    np.random.seed(42)

    print("=" * 70)
    print("Smithing Recipe CNN Dataset Generator v2")
    print("With Saturation/Value Augmentation + Category Shapes + Tier Fill")
    print("=" * 70)

    # Get paths including updates
    materials_paths, placements_paths = get_default_paths()

    print("\nMaterials sources:")
    for p in materials_paths:
        print(f"  - {p}")
    print("\nPlacements sources:")
    for p in placements_paths:
        print(f"  - {p}")

    # Create processor with color augmentation (saturation/value variation)
    # num_augment_passes=3 means 4x images per grid (1 exact + 3 varied)
    processor = RecipeDataProcessorV2.from_paths(
        [str(p) for p in materials_paths],
        [str(p) for p in placements_paths],
        num_augment_passes=3
    )

    # Analyze augmentation potential
    processor.analyze_augmentation_potential()

    # Create valid dataset
    X_valid, valid_grids = processor.create_valid_dataset()

    # Create invalid dataset
    invalid_gen = InvalidRecipeGenerator(processor)
    X_invalid, invalid_grids = invalid_gen.create_invalid_dataset(valid_grids)

    # Combine datasets
    print(f"\n=== Combining Datasets ===")
    X_all = np.concatenate([X_valid, X_invalid], axis=0)
    y_all = np.concatenate([
        np.ones(len(X_valid), dtype=np.float32),
        np.zeros(len(X_invalid), dtype=np.float32)
    ])

    # Shuffle
    shuffle_indices = np.random.permutation(len(X_all))
    X_all = X_all[shuffle_indices]
    y_all = y_all[shuffle_indices]

    # Split into train/validation (80/20)
    split_idx = int(0.8 * len(X_all))
    X_train = X_all[:split_idx]
    y_train = y_all[:split_idx]
    X_val = X_all[split_idx:]
    y_val = y_all[split_idx:]

    print(f"\n=== Final Dataset ===")
    print(f"Total images: {len(X_all)}")
    print(f"  Valid: {len(X_valid)} ({len(X_valid) / len(X_all) * 100:.1f}%)")
    print(f"  Invalid: {len(X_invalid)} ({len(X_invalid) / len(X_all) * 100:.1f}%)")
    print(f"\nTraining set: {len(X_train)} images")
    print(f"  Valid: {int(y_train.sum())} ({y_train.sum() / len(y_train) * 100:.1f}%)")
    print(f"  Invalid: {int(len(y_train) - y_train.sum())} ({(len(y_train) - y_train.sum()) / len(y_train) * 100:.1f}%)")
    print(f"\nValidation set: {len(X_val)} images")
    print(f"  Valid: {int(y_val.sum())} ({y_val.sum() / len(y_val) * 100:.1f}%)")
    print(f"  Invalid: {int(len(y_val) - y_val.sum())} ({(len(y_val) - y_val.sum()) / len(y_val) * 100:.1f}%)")
    print(f"\nImage shape: {X_train.shape[1:]}")
    print(f"Data type: {X_train.dtype}")
    print(f"Value range: [{X_all.min():.3f}, {X_all.max():.3f}]")

    # Save dataset
    output_path = "recipe_dataset_v2.npz"
    np.savez_compressed(
        output_path,
        X_train=X_train,
        y_train=y_train,
        X_val=X_val,
        y_val=y_val
    )
    print(f"\nSaved complete dataset to: {output_path}")
    print(f"Ready for CNN training!")

    return X_train, y_train, X_val, y_val


if __name__ == "__main__":
    main()

"""
Adornment/Enchanting Recipe CNN Dataset Generator v2

SELF-CONTAINED: All color augmentation logic is integrated directly.

Key Design Principles:
1. HUE stays CONSTANT - it encodes CATEGORY which is critical for classification
2. VALUE (brightness) is varied - simulates materials at different tiers within category
3. SATURATION is varied - simulates materials with different tag combinations

Color Encoding Reference:
- HUE = Category (metal=210°, wood=30°, stone=0°, monster_drop=300°)
- VALUE = Tier (T1=0.50, T2=0.65, T3=0.80, T4=0.95)
- SATURATION = Tags (stone=0.2, base=0.6, +0.2 legendary/mythical, +0.1 magical/ancient)

Updates from v1:
- Saturation/value variation augmentation to combat material overfitting
- Support for Update-1 and Update-2 folders
- Multiple augmentation passes per recipe for richer training data
- Improved augmentation with both material substitution AND color variation

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


# Backwards compatibility alias
HueVariationAugmentor = ColorAugmentor


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
    Processes adornment recipes (vertex-based patterns) into CNN training data.
    Version 2: With saturation/value augmentation (hue stays constant).
    """

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

    def parse_placement(self, placement: dict) -> tuple:
        """Extract vertices and shapes from placement data"""
        vertices = placement['placementMap'].get('vertices', {})
        shapes = placement['placementMap'].get('shapes', [])
        return vertices, shapes

    def reflect_vertical(self, vertices: dict, shapes: list) -> tuple:
        """Reflect recipe vertically: (x,y) -> (x,-y)"""
        new_vertices = {}
        coord_mapping = {}

        # Reflect vertex coordinates
        for coord_str, vertex_data in vertices.items():
            x, y = map(int, coord_str.split(','))
            new_coord_str = f"{x},{-y}"
            new_vertices[new_coord_str] = copy.deepcopy(vertex_data)
            coord_mapping[coord_str] = new_coord_str

        # Update shape vertex references
        new_shapes = []
        for shape in shapes:
            new_shape = copy.deepcopy(shape)
            new_shape['vertices'] = [coord_mapping[v] for v in shape['vertices']]
            new_shapes.append(new_shape)

        return new_vertices, new_shapes

    def render_to_image(self, vertices: dict, shapes: list, color_fn, img_size: int = 56) -> np.ndarray:
        """
        Render vertices and shapes to RGB image using provided color function.

        Args:
            vertices: Dict of coord_str -> vertex data
            shapes: List of shape definitions
            color_fn: Function that takes material_id and returns RGB array
            img_size: Output image size (default 56)

        Returns:
            img_size x img_size x 3 RGB image array
        """
        img = np.zeros((img_size, img_size, 3), dtype=np.float32)

        # Coordinate conversion: [-7,7] -> [0,56]
        def coord_to_pixel(x, y):
            px = int((x + 7) * 4)  # 4 pixels per unit
            py = int((7 - y) * 4)  # Flip y-axis for image coordinates
            return px, py

        # Draw shape edges (lines)
        for shape in shapes:
            shape_vertices = shape['vertices']
            n = len(shape_vertices)

            # Draw all edges
            for i in range(n):
                v1_str = shape_vertices[i]
                v2_str = shape_vertices[(i + 1) % n]

                # Get coordinates
                x1, y1 = map(int, v1_str.split(','))
                x2, y2 = map(int, v2_str.split(','))
                px1, py1 = coord_to_pixel(x1, y1)
                px2, py2 = coord_to_pixel(x2, y2)

                # Get material colors
                mat1 = vertices.get(v1_str, {}).get('materialId')
                mat2 = vertices.get(v2_str, {}).get('materialId')

                if mat1 and mat2:
                    # Blend colors
                    color = (color_fn(mat1) + color_fn(mat2)) / 2
                elif mat1:
                    color = color_fn(mat1)
                elif mat2:
                    color = color_fn(mat2)
                else:
                    color = np.array([0.3, 0.3, 0.3])

                # Draw line
                self._draw_line(img, px1, py1, px2, py2, color, thickness=2)

        # Draw vertices (circles) on top
        for coord_str, vertex_data in vertices.items():
            x, y = map(int, coord_str.split(','))
            px, py = coord_to_pixel(x, y)
            material_id = vertex_data.get('materialId')
            color = color_fn(material_id)
            self._draw_circle(img, px, py, radius=3, color=color)

        return img

    def _draw_line(self, img: np.ndarray, x0: int, y0: int, x1: int, y1: int,
                   color: np.ndarray, thickness: int = 1):
        """Draw line using Bresenham's algorithm with blending for overlaps"""
        dx = abs(x1 - x0)
        dy = abs(y1 - y0)
        sx = 1 if x0 < x1 else -1
        sy = 1 if y0 < y1 else -1
        err = dx - dy

        while True:
            # Draw with blending
            for ty in range(-thickness // 2, thickness // 2 + 1):
                for tx in range(-thickness // 2, thickness // 2 + 1):
                    px, py = x0 + tx, y0 + ty
                    if 0 <= px < img.shape[1] and 0 <= py < img.shape[0]:
                        existing = img[py, px]
                        if np.any(existing > 0):
                            img[py, px] = (existing + color) / 2
                        else:
                            img[py, px] = color

            if x0 == x1 and y0 == y1:
                break
            e2 = 2 * err
            if e2 > -dy:
                err -= dy
                x0 += sx
            if e2 < dx:
                err += dx
                y0 += sy

    def _draw_circle(self, img: np.ndarray, cx: int, cy: int, radius: int, color: np.ndarray):
        """Draw filled circle"""
        for y in range(max(0, cy - radius), min(img.shape[0], cy + radius + 1)):
            for x in range(max(0, cx - radius), min(img.shape[1], cx + radius + 1)):
                if (x - cx) ** 2 + (y - cy) ** 2 <= radius ** 2:
                    img[y, x] = color

    def find_substitutable_materials(self, material_id: str) -> list:
        """Find all materials that can substitute for the given material"""
        if material_id is None or material_id not in self.materials_dict:
            return []

        base_mat = self.materials_dict[material_id]
        base_tier = base_mat.get('tier', 1)
        base_tags = set(base_mat.get('metadata', {}).get('tags', []))
        base_category = base_mat.get('category', 'unknown')

        is_refined = 'refined' in base_tags
        is_basic = 'basic' in base_tags

        substitutes = []

        for mat_id, mat in self.materials_dict.items():
            if mat_id == material_id:
                continue
            if mat.get('category') != base_category:
                continue

            mat_tags = set(mat.get('metadata', {}).get('tags', []))
            mat_tier = mat.get('tier', 1)

            if is_refined and 'refined' not in mat_tags:
                continue
            if is_basic and 'basic' not in mat_tags:
                continue

            # Same tags (any tier) OR +-1 tier with 2+ matching tags
            if mat_tags == base_tags:
                substitutes.append(mat_id)
            elif abs(mat_tier - base_tier) <= 1 and len(base_tags & mat_tags) >= 2:
                substitutes.append(mat_id)

        return substitutes

    def augment_recipe_materials(self, vertices: dict, shapes: list) -> list:
        """
        Generate variants by substituting materials.
        Returns list of (vertices, shapes) tuples.
        """
        variants = [(vertices, shapes)]

        # Add vertical reflection
        v_refl, s_refl = self.reflect_vertical(vertices, shapes)
        variants.append((v_refl, s_refl))

        # Find unique materials
        unique_materials = set()
        for vertex_data in vertices.values():
            mat_id = vertex_data.get('materialId')
            if mat_id is not None:
                unique_materials.add(mat_id)

        # Material substitutions
        for material_id in unique_materials:
            substitutes = self.find_substitutable_materials(material_id)

            for sub_mat in substitutes:
                # Substitute in original
                new_v = copy.deepcopy(vertices)
                for coord, data in new_v.items():
                    if data.get('materialId') == material_id:
                        data['materialId'] = sub_mat
                variants.append((new_v, shapes))

                # Substitute in reflection
                new_v_refl = copy.deepcopy(v_refl)
                for coord, data in new_v_refl.items():
                    if data.get('materialId') == material_id:
                        data['materialId'] = sub_mat
                variants.append((new_v_refl, s_refl))

        # Remove duplicates
        unique_variants = []
        seen = set()
        for v, s in variants:
            v_tuple = tuple(sorted((k, d.get('materialId')) for k, d in v.items()))
            if v_tuple not in seen:
                seen.add(v_tuple)
                unique_variants.append((v, s))

        return unique_variants

    def augment_with_color_variation(self, recipe_variants: list, img_size: int = 56) -> np.ndarray:
        """
        Convert recipe variants to images with saturation/value variation.

        For each variant:
        - 1 image with exact colors
        - N images with varied saturation/value colors

        Note: HUE is NOT varied - it encodes category which must be preserved.

        Args:
            recipe_variants: List of (vertices, shapes) tuples
            img_size: Output image size

        Returns:
            Array of images
        """
        all_images = []

        for vertices, shapes in recipe_variants:
            # Exact colors
            img_exact = self.render_to_image(
                vertices, shapes,
                self.exact_augmentor.material_to_color,
                img_size
            )
            all_images.append(img_exact)

            # Saturation/value-varied colors
            for _ in range(self.num_augment_passes):
                img_varied = self.render_to_image(
                    vertices, shapes,
                    self.augmentor.material_to_color,
                    img_size
                )
                all_images.append(img_varied)

        return np.array(all_images, dtype=np.float32)

    # Backwards compatibility alias
    def augment_with_hue_variation(self, recipe_variants: list, img_size: int = 56) -> np.ndarray:
        """Deprecated: Use augment_with_color_variation instead."""
        return self.augment_with_color_variation(recipe_variants, img_size)

    def create_valid_dataset(self, img_size: int = 56) -> tuple:
        """
        Create complete dataset of valid recipes with augmentation.

        Returns:
            (images_array, recipe_variants_list)
        """
        all_variants = []

        print("\n=== Processing Recipes ===")

        for placement in self.placements:
            recipe_id = placement['recipeId']
            vertices, shapes = self.parse_placement(placement)

            # Augment with material substitution
            variants = self.augment_recipe_materials(vertices, shapes)

            print(f"  {recipe_id}: {len(variants)} material variants")
            all_variants.extend(variants)

        print(f"\n=== Material Augmentation Complete ===")
        print(f"Base recipes: {len(self.placements)}")
        print(f"Material-augmented variants: {len(all_variants)}")

        # Apply color variation (saturation/value)
        print(f"\n=== Applying Color Variation (Sat/Val) ===")
        print(f"Augmentation passes per variant: {self.num_augment_passes}")
        expected_images = len(all_variants) * (1 + self.num_augment_passes)
        print(f"Expected total images: {expected_images}")

        images = self.augment_with_color_variation(all_variants, img_size)

        print(f"Generated images: {len(images)}")

        return images, all_variants

    def analyze_augmentation_potential(self):
        """Analyze augmentation potential"""
        print("\n=== Augmentation Analysis ===")

        materials_in_recipes = set()
        for placement in self.placements:
            vertices, _ = self.parse_placement(placement)
            for vertex_data in vertices.values():
                mat_id = vertex_data.get('materialId')
                if mat_id is not None:
                    materials_in_recipes.add(mat_id)

        print(f"Unique materials in recipes: {len(materials_in_recipes)}")

        sub_counts = []
        for mat_id in sorted(materials_in_recipes):
            subs = self.find_substitutable_materials(mat_id)
            sub_counts.append(len(subs))
            if subs:
                print(f"  {mat_id}: {len(subs)} substitutes")

        if sub_counts:
            print(f"\nSubstitution stats:")
            print(f"  Materials with substitutes: {sum(1 for c in sub_counts if c > 0)}")
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

        # Get materials used in recipes
        self.recipe_materials = set()
        for placement in processor.placements:
            vertices, _ = processor.parse_placement(placement)
            for vertex_data in vertices.values():
                mat_id = vertex_data.get('materialId')
                if mat_id is not None:
                    self.recipe_materials.add(mat_id)

        self.all_materials = list(self.recipe_materials)
        print(f"\nInvalid generator using {len(self.all_materials)} materials")

    def remove_vertices(self, vertices: dict, shapes: list) -> tuple:
        """Remove 20% or minimum 2 vertices"""
        num_vertices = len(vertices)
        num_remove = max(2, int(num_vertices * 0.2))
        num_remove = min(num_remove, num_vertices - 1)

        coords_to_remove = random.sample(list(vertices.keys()), num_remove)

        new_vertices = {k: v for k, v in vertices.items() if k not in coords_to_remove}

        # Clean up shapes
        new_shapes = []
        for shape in shapes:
            new_shape_vertices = [v for v in shape['vertices'] if v not in coords_to_remove]
            if len(new_shape_vertices) >= 2:
                new_shape = copy.deepcopy(shape)
                new_shape['vertices'] = new_shape_vertices
                new_shapes.append(new_shape)

        return new_vertices, new_shapes

    def swap_materials(self, vertices: dict) -> dict:
        """Randomly swap 5+ materials"""
        new_vertices = copy.deepcopy(vertices)

        coords_with_materials = [
            coord for coord, data in new_vertices.items()
            if data.get('materialId') is not None
        ]

        if not coords_with_materials:
            return new_vertices

        num_swaps = max(5, len(coords_with_materials) // 3)
        num_swaps = min(num_swaps, len(coords_with_materials))

        swap_coords = random.sample(coords_with_materials, num_swaps)

        for coord in swap_coords:
            current = new_vertices[coord]['materialId']
            available = [m for m in self.all_materials if m != current]
            if available:
                new_vertices[coord]['materialId'] = random.choice(available)

        return new_vertices

    def generate_batch(self, count: int, valid_variants: list) -> list:
        """Generate batch of invalid recipes"""
        invalid_variants = []

        # 50% remove vertices
        num_remove = count // 2
        for _ in range(num_remove):
            vertices, shapes = random.choice(valid_variants)
            new_v, new_s = self.remove_vertices(vertices, shapes)
            invalid_variants.append((new_v, new_s))

        # 50% swap materials
        num_swap = count - num_remove
        for _ in range(num_swap):
            vertices, shapes = random.choice(valid_variants)
            new_v = self.swap_materials(vertices)
            invalid_variants.append((new_v, shapes))

        return invalid_variants

    def create_invalid_dataset(self, valid_variants: list, img_size: int = 56) -> tuple:
        """
        Create invalid dataset with color variation.

        Returns:
            (images_array, variants_list)
        """
        count = len(valid_variants)

        print(f"\n=== Generating Invalid Recipes ===")
        print(f"Target variants: {count}")

        invalid_variants = self.generate_batch(count, valid_variants)

        print(f"Generated: {len(invalid_variants)} invalid variants")
        print(f"  - ~{count // 2} with removed vertices")
        print(f"  - ~{count // 2} with swapped materials")

        # Apply color variation (saturation/value)
        print(f"\n=== Applying Color Variation to Invalid ===")
        images = self.processor.augment_with_color_variation(invalid_variants, img_size)
        print(f"Generated: {len(images)} invalid images")

        return images, invalid_variants


# ============================================================================
# MAIN EXECUTION
# ============================================================================

def get_default_paths():
    """Get default paths for materials and placements including updates."""
    script_dir = Path(__file__).parent
    game_modular = script_dir.parent.parent.parent / "Game-1-modular"

    materials_paths = [
        game_modular / "items.JSON" / "items-materials-1.JSON",
    ]

    placements_paths = [
        game_modular / "placements.JSON" / "placements-adornments-1.JSON",
    ]

    # Check for Update folders
    for update_name in ["Update-1", "Update-2"]:
        update_dir = game_modular / update_name
        if update_dir.exists():
            # Add any materials files
            for pattern in ["*materials*.JSON", "*materials*.json"]:
                for f in update_dir.glob(pattern):
                    materials_paths.append(f)

            # Add any adornment/enchanting placements
            for pattern in ["*placements*adornment*.JSON", "*placements*adornment*.json",
                           "*placements*enchant*.JSON", "*placements*enchant*.json"]:
                for f in update_dir.glob(pattern):
                    placements_paths.append(f)

    return materials_paths, placements_paths


def main():
    """Main execution with color augmentation"""
    random.seed(42)
    np.random.seed(42)

    print("=" * 70)
    print("Adornment/Enchanting Recipe CNN Dataset Generator v2")
    print("With Saturation/Value Augmentation (Hue constant = category)")
    print("=" * 70)

    # Get paths including updates
    materials_paths, placements_paths = get_default_paths()

    print("\nMaterials sources:")
    for p in materials_paths:
        print(f"  - {p}")
    print("\nPlacements sources:")
    for p in placements_paths:
        print(f"  - {p}")

    # Create processor with color augmentation
    processor = RecipeDataProcessorV2.from_paths(
        [str(p) for p in materials_paths],
        [str(p) for p in placements_paths],
        num_augment_passes=3
    )

    # Analyze augmentation potential
    processor.analyze_augmentation_potential()

    # Create valid dataset
    X_valid, valid_variants = processor.create_valid_dataset()

    # Create invalid dataset
    invalid_gen = InvalidRecipeGenerator(processor)
    X_invalid, invalid_variants = invalid_gen.create_invalid_dataset(valid_variants)

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
    print(f"Validation set: {len(X_val)} images")
    print(f"\nImage shape: {X_train.shape[1:]}")
    print(f"Data type: {X_train.dtype}")
    print(f"Value range: [{X_all.min():.3f}, {X_all.max():.3f}]")

    # Save dataset
    output_path = "adornment_dataset_v2.npz"
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

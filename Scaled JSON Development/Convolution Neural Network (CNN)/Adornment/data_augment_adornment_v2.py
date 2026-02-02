"""
Adornment/Enchanting Recipe CNN Dataset Generator v2

Updates from v1:
- Hue variation augmentation to combat material overfitting
- Support for Update-1 and Update-2 folders
- Multiple hue passes per recipe for richer training data
- Improved augmentation with both material substitution AND color variation

The goal is to teach the CNN to recognize PATTERNS and STRUCTURAL relationships
(vertex positions, shape connectivity), not memorize specific material colors.

Created: 2026-02-02
"""

import json
import numpy as np
from colorsys import hsv_to_rgb
from pathlib import Path
import copy
import sys
import os
from collections import defaultdict

# Add parent directory to path for color_augmentation module
sys.path.insert(0, str(Path(__file__).parent.parent))
from color_augmentation import (
    HueVariationAugmentor,
    load_materials_from_multiple_sources,
    load_placements_from_multiple_sources
)


class RecipeDataProcessorV2:
    """
    Processes adornment recipes (vertex-based patterns) into CNN training data.
    Version 2: With hue variation augmentation.
    """

    def __init__(self, materials_dict: dict, placements: list, num_hue_passes: int = 3):
        """
        Args:
            materials_dict: Dict of {material_id: material_data}
            placements: List of placement objects
            num_hue_passes: Number of hue-varied versions per recipe (default 3)
        """
        self.materials_dict = materials_dict
        self.placements = placements
        self.num_hue_passes = num_hue_passes

        # Create augmentors
        self.hue_augmentor = HueVariationAugmentor(materials_dict, augmentation_enabled=True)
        self.exact_augmentor = HueVariationAugmentor(materials_dict, augmentation_enabled=False)

        print(f"Initialized with {len(materials_dict)} materials")
        print(f"Initialized with {len(placements)} placements")
        print(f"Hue passes per recipe: {num_hue_passes}")

    @classmethod
    def from_paths(cls, materials_paths: list, placements_paths: list, num_hue_passes: int = 3):
        """
        Create processor from file paths, merging multiple sources.

        Args:
            materials_paths: List of paths to materials JSON files
            placements_paths: List of paths to placements JSON files
            num_hue_passes: Number of hue variations per recipe
        """
        print("\n=== Loading Materials ===")
        materials_dict = load_materials_from_multiple_sources(materials_paths)

        print("\n=== Loading Placements ===")
        placements = load_placements_from_multiple_sources(placements_paths)

        return cls(materials_dict, placements, num_hue_passes)

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

    def augment_with_hue_variation(self, recipe_variants: list, img_size: int = 56) -> np.ndarray:
        """
        Convert recipe variants to images with hue variation.

        For each variant:
        - 1 image with exact colors
        - N images with hue-varied colors

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

            # Hue-varied colors
            for _ in range(self.num_hue_passes):
                img_varied = self.render_to_image(
                    vertices, shapes,
                    self.hue_augmentor.material_to_color,
                    img_size
                )
                all_images.append(img_varied)

        return np.array(all_images, dtype=np.float32)

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

        # Apply hue variation
        print(f"\n=== Applying Hue Variation ===")
        print(f"Hue passes per variant: {self.num_hue_passes}")
        expected_images = len(all_variants) * (1 + self.num_hue_passes)
        print(f"Expected total images: {expected_images}")

        images = self.augment_with_hue_variation(all_variants, img_size)

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
        import random

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
        import random

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
        import random

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
        Create invalid dataset with hue variation.

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

        # Apply hue variation
        print(f"\n=== Applying Hue Variation to Invalid ===")
        images = self.processor.augment_with_hue_variation(invalid_variants, img_size)
        print(f"Generated: {len(images)} invalid images")

        return images, invalid_variants


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
    """Main execution with hue augmentation"""
    import random

    random.seed(42)
    np.random.seed(42)

    print("=" * 70)
    print("Adornment/Enchanting Recipe CNN Dataset Generator v2")
    print("With Hue Variation Augmentation")
    print("=" * 70)

    # Get paths including updates
    materials_paths, placements_paths = get_default_paths()

    print("\nMaterials sources:")
    for p in materials_paths:
        print(f"  - {p}")
    print("\nPlacements sources:")
    for p in placements_paths:
        print(f"  - {p}")

    # Create processor with hue augmentation
    processor = RecipeDataProcessorV2.from_paths(
        [str(p) for p in materials_paths],
        [str(p) for p in placements_paths],
        num_hue_passes=3
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
    print(f"\n✓ Saved complete dataset to: {output_path}")
    print(f"  Ready for CNN training!")

    return X_train, y_train, X_val, y_val


if __name__ == "__main__":
    main()

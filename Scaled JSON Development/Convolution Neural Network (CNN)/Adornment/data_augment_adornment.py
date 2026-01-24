import json
import numpy as np
from colorsys import hsv_to_rgb
import copy
from collections import defaultdict


class RecipeDataProcessor:
    """Processes adornment recipes (vertex-based patterns) into CNN training data"""

    def __init__(self, materials_path, placements_path):
        with open(materials_path, 'r') as f:
            self.materials_data = json.load(f)
        with open(placements_path, 'r') as f:
            self.placements_data = json.load(f)

        # Create material lookup dictionary
        self.materials_dict = {
            mat['materialId']: mat
            for mat in self.materials_data['materials']
        }

        print(f"Loaded {len(self.materials_dict)} materials")
        print(f"Loaded {len(self.placements_data['placements'])} recipes")

    def material_to_color(self, material_id):
        """Convert material to RGB color (0-1 range) based on category, tier, tags"""
        if material_id is None:
            return np.array([0.5, 0.5, 0.5])  # Gray for missing materials

        material = self.materials_dict[material_id]
        category = material['category']
        tier = material['tier']
        tags = material['metadata']['tags']

        # CATEGORY → HUE
        if category == 'elemental':
            element_hues = {
                'fire': 0, 'water': 210, 'earth': 120, 'air': 60,
                'lightning': 270, 'ice': 180, 'light': 45,
                'dark': 280, 'void': 290, 'chaos': 330,
            }
            hue = 280  # Default purple
            for tag in tags:
                if tag in element_hues:
                    hue = element_hues[tag]
                    break
        else:
            category_hues = {
                'metal': 210, 'wood': 30, 'stone': 0, 'monster_drop': 300
            }
            hue = category_hues.get(category, 0)

        # TIER → VALUE/BRIGHTNESS
        tier_values = {1: 0.50, 2: 0.65, 3: 0.80, 4: 0.95}
        value = tier_values.get(tier, 0.5)

        # TAGS → SATURATION
        base_saturation = 0.6
        if category == 'stone':
            base_saturation = 0.2
        if 'legendary' in tags or 'mythical' in tags:
            base_saturation = min(1.0, base_saturation + 0.2)
        elif 'magical' in tags or 'ancient' in tags:
            base_saturation = min(1.0, base_saturation + 0.1)

        # Convert HSV to RGB
        rgb = hsv_to_rgb(hue / 360.0, base_saturation, value)
        return np.array(rgb)

    def parse_placement(self, placement):
        """Extract vertices and shapes from placement data"""
        vertices = placement['placementMap']['vertices']
        shapes = placement['placementMap']['shapes']
        return vertices, shapes

    def reflect_vertical(self, vertices, shapes):
        """Reflect recipe vertically: (x,y) → (x,-y)"""
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

    def render_to_image(self, vertices, shapes, img_size=56):
        """Render vertices and shapes to RGB image"""
        img = np.zeros((img_size, img_size, 3), dtype=np.float32)

        # Coordinate conversion: [-7,7] → [0,56]
        def coord_to_pixel(x, y):
            px = int((x + 7) * 4)  # 4 pixels per unit
            py = int((7 - y) * 4)  # Flip y-axis for image coordinates
            return px, py

        # Draw shape edges (lines)
        for shape in shapes:
            shape_vertices = shape['vertices']
            n = len(shape_vertices)

            # Draw all edges of the shape
            for i in range(n):
                v1_str = shape_vertices[i]
                v2_str = shape_vertices[(i + 1) % n]  # Close the loop

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
                    color = (self.material_to_color(mat1) + self.material_to_color(mat2)) / 2
                elif mat1:
                    color = self.material_to_color(mat1)
                elif mat2:
                    color = self.material_to_color(mat2)
                else:
                    color = np.array([0.3, 0.3, 0.3])  # Dark gray for no materials

                # Draw line using Bresenham's algorithm
                self._draw_line(img, px1, py1, px2, py2, color, thickness=2)

        # Draw vertices (circles) on top
        for coord_str, vertex_data in vertices.items():
            x, y = map(int, coord_str.split(','))
            px, py = coord_to_pixel(x, y)
            material_id = vertex_data.get('materialId')
            color = self.material_to_color(material_id)
            self._draw_circle(img, px, py, radius=3, color=color)

        return img

    def _draw_line(self, img, x0, y0, x1, y1, color, thickness=1):
        """Draw line using Bresenham's algorithm with blending for overlaps"""
        dx = abs(x1 - x0)
        dy = abs(y1 - y0)
        sx = 1 if x0 < x1 else -1
        sy = 1 if y0 < y1 else -1
        err = dx - dy

        while True:
            # Draw with blending for overlapping lines
            for ty in range(-thickness // 2, thickness // 2 + 1):
                for tx in range(-thickness // 2, thickness // 2 + 1):
                    px, py = x0 + tx, y0 + ty
                    if 0 <= px < img.shape[1] and 0 <= py < img.shape[0]:
                        # Blend with existing pixel
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

    def _draw_circle(self, img, cx, cy, radius, color):
        """Draw filled circle"""
        for y in range(max(0, cy - radius), min(img.shape[0], cy + radius + 1)):
            for x in range(max(0, cx - radius), min(img.shape[1], cx + radius + 1)):
                if (x - cx) ** 2 + (y - cy) ** 2 <= radius ** 2:
                    img[y, x] = color

    def find_substitutable_materials(self, material_id):
        """Find all materials that can substitute for the given material"""
        if material_id is None:
            return []

        base_mat = self.materials_dict[material_id]
        base_tier = base_mat['tier']
        base_tags = set(base_mat['metadata']['tags'])
        base_category = base_mat['category']

        is_refined = 'refined' in base_tags
        is_basic = 'basic' in base_tags

        substitutes = []

        for mat_id, mat in self.materials_dict.items():
            if mat_id == material_id:
                continue
            if mat['category'] != base_category:
                continue

            mat_tags = set(mat['metadata']['tags'])
            mat_tier = mat['tier']

            if is_refined and 'refined' not in mat_tags:
                continue
            if is_basic and 'basic' not in mat_tags:
                continue

            # Same tags (any tier) OR ±1 tier with 2+ matching tags
            if mat_tags == base_tags:
                substitutes.append(mat_id)
            elif abs(mat_tier - base_tier) <= 1 and len(base_tags & mat_tags) >= 2:
                substitutes.append(mat_id)

        return substitutes

    def augment_recipe(self, vertices, shapes):
        """Generate augmented variants of a recipe"""
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
            # Create hashable representation
            v_tuple = tuple(sorted((k, d.get('materialId')) for k, d in v.items()))
            if v_tuple not in seen:
                seen.add(v_tuple)
                unique_variants.append((v, s))

        return unique_variants

    def create_valid_dataset(self, img_size=56):
        """Create complete dataset of valid recipes with augmentation"""
        all_recipes = []

        print("\n=== Processing Recipes ===")

        for placement in self.placements_data['placements']:
            recipe_id = placement['recipeId']
            vertices, shapes = self.parse_placement(placement)

            # Augment
            variants = self.augment_recipe(vertices, shapes)

            print(f"{recipe_id}: {len(variants)} variants")
            all_recipes.extend(variants)

        print(f"\n=== Total Valid Recipes ===")
        print(f"Base recipes: {len(self.placements_data['placements'])}")
        print(f"Augmented recipes: {len(all_recipes)}")

        # Convert to images
        print("\n=== Converting to Images ===")
        images = []
        for vertices, shapes in all_recipes:
            img = self.render_to_image(vertices, shapes, img_size)
            images.append(img)

        return np.array(images, dtype=np.float32), all_recipes

    def analyze_augmentation_potential(self):
        """Analyze augmentation potential"""
        print("\n=== Augmentation Analysis ===")

        materials_in_recipes = set()
        for placement in self.placements_data['placements']:
            vertices, _ = self.parse_placement(placement)
            for vertex_data in vertices.values():
                mat_id = vertex_data.get('materialId')
                if mat_id is not None:
                    materials_in_recipes.add(mat_id)

        print(f"Unique materials in recipes: {len(materials_in_recipes)}")

        for mat_id in sorted(materials_in_recipes):
            subs = self.find_substitutable_materials(mat_id)
            if subs:
                print(f"  {mat_id}: {len(subs)} substitutes")


class InvalidRecipeGenerator:
    """Generates invalid recipe examples for training"""

    def __init__(self, processor):
        self.processor = processor
        self.materials_dict = processor.materials_dict

        # Get materials used in recipes
        self.recipe_materials = set()
        for placement in processor.placements_data['placements']:
            vertices, _ = processor.parse_placement(placement)
            for vertex_data in vertices.values():
                mat_id = vertex_data.get('materialId')
                if mat_id is not None:
                    self.recipe_materials.add(mat_id)

        self.all_materials = list(self.recipe_materials)
        print(f"\nInvalid generator using {len(self.all_materials)} materials")

    def remove_vertices(self, vertices, shapes):
        """Remove 20% or minimum 2 vertices"""
        import random

        num_vertices = len(vertices)
        num_remove = max(2, int(num_vertices * 0.2))
        num_remove = min(num_remove, num_vertices - 1)  # Keep at least 1

        # Select vertices to remove
        coords_to_remove = random.sample(list(vertices.keys()), num_remove)

        # Create new vertices dict
        new_vertices = {k: v for k, v in vertices.items() if k not in coords_to_remove}

        # Clean up shapes (remove references to deleted vertices)
        new_shapes = []
        for shape in shapes:
            # Keep only vertices that still exist
            new_shape_vertices = [v for v in shape['vertices'] if v not in coords_to_remove]

            # Only keep shape if it has at least 2 vertices
            if len(new_shape_vertices) >= 2:
                new_shape = copy.deepcopy(shape)
                new_shape['vertices'] = new_shape_vertices
                new_shapes.append(new_shape)

        return new_vertices, new_shapes

    def swap_materials(self, vertices):
        """Randomly swap 5+ materials"""
        import random

        new_vertices = copy.deepcopy(vertices)

        # Only swap vertices that have materials
        coords_with_materials = [
            coord for coord, data in new_vertices.items()
            if data.get('materialId') is not None
        ]

        if not coords_with_materials:
            return new_vertices

        num_swaps = max(5, len(coords_with_materials) // 3)  # At least 5 or ~33%
        num_swaps = min(num_swaps, len(coords_with_materials))

        swap_coords = random.sample(coords_with_materials, num_swaps)

        for coord in swap_coords:
            current = new_vertices[coord]['materialId']
            available = [m for m in self.all_materials if m != current]
            if available:
                new_vertices[coord]['materialId'] = random.choice(available)

        return new_vertices

    def generate_batch(self, count, valid_recipes):
        """Generate batch of invalid recipes"""
        import random

        invalid_recipes = []

        # 50% remove vertices
        num_remove = count // 2
        for _ in range(num_remove):
            vertices, shapes = random.choice(valid_recipes)
            new_v, new_s = self.remove_vertices(vertices, shapes)
            invalid_recipes.append((new_v, new_s))

        # 50% swap materials
        num_swap = count - num_remove
        for _ in range(num_swap):
            vertices, shapes = random.choice(valid_recipes)
            new_v = self.swap_materials(vertices)
            invalid_recipes.append((new_v, shapes))

        return invalid_recipes

    def create_invalid_dataset(self, valid_recipes, img_size=56):
        """Create invalid dataset matching valid count"""
        count = len(valid_recipes)

        print(f"\n=== Generating Invalid Recipes ===")
        print(f"Target count: {count}")

        invalid_recipes = self.generate_batch(count, valid_recipes)

        print(f"Generated: {len(invalid_recipes)} invalid recipes")
        print(f"  - ~{count // 2} with removed vertices")
        print(f"  - ~{count // 2} with swapped materials")

        # Convert to images
        print("\n=== Converting Invalid to Images ===")
        images = []
        for vertices, shapes in invalid_recipes:
            img = self.processor.render_to_image(vertices, shapes, img_size)
            images.append(img)

        return np.array(images, dtype=np.float32), invalid_recipes


# Example usage
if __name__ == "__main__":
    import random

    random.seed(42)
    np.random.seed(42)

    # File paths
    MATERIALS_PATH = "../../../Game-1-modular/items.JSON/items-materials-1.JSON"
    PLACEMENTS_PATH = "../../../Game-1-modular/placements.JSON/placements-adornments-1.JSON"

    processor = RecipeDataProcessor(MATERIALS_PATH, PLACEMENTS_PATH)

    # Analyze augmentation
    processor.analyze_augmentation_potential()

    # Create valid dataset
    X_valid, valid_recipes = processor.create_valid_dataset()

    # Create invalid dataset
    invalid_gen = InvalidRecipeGenerator(processor)
    X_invalid, invalid_recipes = invalid_gen.create_invalid_dataset(valid_recipes)

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

    # Split 80/20
    split_idx = int(0.8 * len(X_all))
    X_train = X_all[:split_idx]
    y_train = y_all[:split_idx]
    X_val = X_all[split_idx:]
    y_val = y_all[split_idx:]

    print(f"\n=== Final Dataset ===")
    print(f"Total examples: {len(X_all)}")
    print(f"  Valid: {len(X_valid)} ({len(X_valid) / len(X_all) * 100:.1f}%)")
    print(f"  Invalid: {len(X_invalid)} ({len(X_invalid) / len(X_all) * 100:.1f}%)")
    print(f"\nTraining set: {len(X_train)} examples")
    print(f"Validation set: {len(X_val)} examples")
    print(f"\nImage shape: {X_train.shape[1:]}")
    print(f"Value range: [{X_all.min():.3f}, {X_all.max():.3f}]")

    # Save dataset
    output_path = "adornment_dataset.npz"
    np.savez_compressed(
        output_path,
        X_train=X_train,
        y_train=y_train,
        X_val=X_val,
        y_val=y_val
    )
    print(f"\n✓ Saved dataset to: {output_path}")
import json
import numpy as np
from colorsys import hsv_to_rgb
from pathlib import Path
import copy


class RecipeDataProcessor:
    """Processes smithing recipes and materials into CNN training data"""

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

    def is_station(self, recipe_id):
        """Check if recipe is a station/bench (ends with _t1, _t2, _t3, _t4)"""
        return any(recipe_id.endswith(f'_t{i}') for i in range(1, 5))

    def material_to_color(self, material_id):
        """Convert material to RGB color (0-1 range) based on category, tier, tags"""
        if material_id is None:
            return np.array([0.0, 0.0, 0.0])

        material = self.materials_dict[material_id]
        category = material['category']
        tier = material['tier']
        tags = material['metadata']['tags']

        # CATEGORY → HUE (primary determinant)
        if category == 'elemental':
            # Parse element-specific tag for hue
            element_hues = {
                'fire': 0,  # Red
                'water': 210,  # Blue
                'earth': 120,  # Green
                'air': 60,  # Yellow
                'lightning': 270,  # Purple
                'ice': 180,  # Cyan
                'light': 45,  # Yellow-orange
                'dark': 280,  # Dark purple
                'void': 290,  # Dark magenta
                'chaos': 330,  # Pink-red
            }
            hue = 280  # Default purple for elementals
            for tag in tags:
                if tag in element_hues:
                    hue = element_hues[tag]
                    break
        else:
            category_hues = {
                'metal': 210,  # Blue
                'wood': 30,  # Orange/brown
                'stone': 0,  # Gray (will use low saturation)
                'monster_drop': 300  # Purple/magenta
            }
            hue = category_hues.get(category, 0)

        # TIER → VALUE/BRIGHTNESS (high importance)
        tier_values = {
            1: 0.50,
            2: 0.65,
            3: 0.80,
            4: 0.95
        }
        value = tier_values.get(tier, 0.5)

        # TAGS → SATURATION (tertiary)
        base_saturation = 0.6

        # Stone gets low saturation for gray appearance
        if category == 'stone':
            base_saturation = 0.2

        # Slight adjustments based on tags
        if 'legendary' in tags or 'mythical' in tags:
            base_saturation = min(1.0, base_saturation + 0.2)
        elif 'magical' in tags or 'ancient' in tags:
            base_saturation = min(1.0, base_saturation + 0.1)

        saturation = base_saturation

        # Convert HSV to RGB
        hue_normalized = hue / 360.0
        rgb = hsv_to_rgb(hue_normalized, saturation, value)

        return np.array(rgb)

    def placement_to_grid(self, placement):
        """Convert placement to centered 9x9 grid"""
        grid = [[None] * 9 for _ in range(9)]

        # Determine grid size from metadata
        grid_size_str = placement['metadata']['gridSize']
        recipe_size = int(grid_size_str.split('x')[0])

        # Find actual bounding box of placements to handle off-center recipes
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

        # Use actual dimensions for centering (handles recipes not starting at 1,1)
        offset_y = (9 - actual_height) // 2
        offset_x = (9 - actual_width) // 2

        # Parse placement map and center on 9x9 grid
        for pos_str, material_id in placement['placementMap'].items():
            y_idx, x_idx = map(int, pos_str.split(','))
            # Normalize to start at 0,0 then add centering offset
            final_y = offset_y + (y_idx - min_y)
            final_x = offset_x + (x_idx - min_x)

            # Bounds check
            if 0 <= final_y < 9 and 0 <= final_x < 9:
                grid[final_y][final_x] = material_id
            else:
                print(f"Warning: Position ({y_idx},{x_idx}) in {placement['recipeId']} exceeds 9x9 grid bounds")

        return grid

    def grid_to_image(self, grid, cell_size=4):
        """Convert 9x9 grid to 36x36 RGB image"""
        img_size = 9 * cell_size
        img = np.zeros((img_size, img_size, 3))

        for i in range(9):
            for j in range(9):
                color = self.material_to_color(grid[i][j])
                img[i * cell_size:(i + 1) * cell_size,
                j * cell_size:(j + 1) * cell_size] = color

        return img

    def flip_grid_horizontal(self, grid):
        """Flip 9x9 grid horizontally"""
        return [row[::-1] for row in grid]

    def find_substitutable_materials(self, material_id):
        """Find all materials that can substitute for the given material"""
        if material_id is None:
            return []

        base_mat = self.materials_dict[material_id]
        base_tier = base_mat['tier']
        base_tags = set(base_mat['metadata']['tags'])
        base_category = base_mat['category']

        # Check for refined/basic constraint
        is_refined = 'refined' in base_tags
        is_basic = 'basic' in base_tags

        substitutes = []

        for mat_id, mat in self.materials_dict.items():
            if mat_id == material_id:
                continue

            # Must be same category
            if mat['category'] != base_category:
                continue

            mat_tags = set(mat['metadata']['tags'])
            mat_tier = mat['tier']

            # HARD RULE: refined/basic must match
            if is_refined and 'refined' not in mat_tags:
                continue
            if is_basic and 'basic' not in mat_tags:
                continue

            # Rule 1: All tags match (any tier difference OK)
            if mat_tags == base_tags:
                substitutes.append(mat_id)
                continue

            # Rule 2: ±1 tier and at least 2 matching tags
            if abs(mat_tier - base_tier) <= 1:
                matching_tags = base_tags & mat_tags
                if len(matching_tags) >= 2:
                    substitutes.append(mat_id)

        return substitutes

    def augment_recipe(self, grid):
        """Generate all augmented variants of a recipe"""
        variants = [grid]

        # Add horizontal flip
        flipped = self.flip_grid_horizontal(grid)
        variants.append(flipped)

        # Find all unique materials in grid
        unique_materials = set()
        for row in grid:
            for mat in row:
                if mat is not None:
                    unique_materials.add(mat)

        # Generate substitution variants
        substitution_variants = []

        for material_id in unique_materials:
            substitutes = self.find_substitutable_materials(material_id)

            for sub_mat in substitutes:
                # Create variant by replacing ALL instances
                new_grid = copy.deepcopy(grid)
                for i in range(9):
                    for j in range(9):
                        if new_grid[i][j] == material_id:
                            new_grid[i][j] = sub_mat

                substitution_variants.append(new_grid)

                # Also add flipped version of substitution
                substitution_variants.append(
                    self.flip_grid_horizontal(new_grid)
                )

        variants.extend(substitution_variants)

        # Remove duplicates (convert to tuple for hashing)
        unique_variants = []
        seen = set()
        for variant in variants:
            variant_tuple = tuple(tuple(row) for row in variant)
            if variant_tuple not in seen:
                seen.add(variant_tuple)
                unique_variants.append(variant)

        return unique_variants

    def create_valid_dataset(self, cell_size=4):
        """Create complete dataset of valid recipes with augmentation (excluding stations)"""
        all_grids = []

        print("\n=== Processing Recipes ===")

        # Filter out stations
        non_station_placements = [
            p for p in self.placements_data['placements']
            if not self.is_station(p['recipeId'])
        ]

        print(f"Total recipes: {len(self.placements_data['placements'])}")
        print(f"Stations excluded: {len(self.placements_data['placements']) - len(non_station_placements)}")
        print(f"Processing: {len(non_station_placements)} non-station recipes\n")

        for placement in non_station_placements:
            recipe_id = placement['recipeId']

            # Convert to grid
            grid = self.placement_to_grid(placement)

            # Augment
            variants = self.augment_recipe(grid)

            print(f"{recipe_id}: {len(variants)} variants")
            all_grids.extend(variants)

        print(f"\n=== Total Valid Recipes ===")
        print(f"Base recipes (non-station): {len(non_station_placements)}")
        print(f"Augmented recipes: {len(all_grids)}")

        # Convert to images
        print("\n=== Converting to Images ===")
        images = []
        for grid in all_grids:
            img = self.grid_to_image(grid, cell_size)
            images.append(img)

        return np.array(images, dtype=np.float32), all_grids

    def analyze_augmentation_potential(self):
        """Analyze how many substitutions are possible per material (excluding stations)"""
        print("\n=== Augmentation Analysis (Excluding Stations) ===")

        # Count materials used in non-station recipes
        materials_in_recipes = set()
        for placement in self.placements_data['placements']:
            if not self.is_station(placement['recipeId']):
                for material_id in placement['placementMap'].values():
                    materials_in_recipes.add(material_id)

        print(f"Unique materials in non-station recipes: {len(materials_in_recipes)}")

        for mat_id in sorted(materials_in_recipes):
            subs = self.find_substitutable_materials(mat_id)
            if subs:
                print(f"  {mat_id}: {len(subs)} substitutes")


class InvalidRecipeGenerator:
    """Generates invalid recipe examples for training"""

    def __init__(self, processor):
        self.processor = processor
        self.materials_dict = processor.materials_dict

        # Get list of materials actually used in non-station recipes
        self.recipe_materials = set()
        for placement in processor.placements_data['placements']:
            if not processor.is_station(placement['recipeId']):
                for material_id in placement['placementMap'].values():
                    self.recipe_materials.add(material_id)

        self.all_materials = list(self.recipe_materials)
        print(f"\nInvalid generator using {len(self.all_materials)} materials from non-station recipes")

    def generate_random(self):
        """Generate completely random recipe (2-40 materials)"""
        import random

        num_filled = random.randint(2, 40)
        grid = [[None] * 9 for _ in range(9)]

        # Get random positions
        all_positions = [(i, j) for i in range(9) for j in range(9)]
        positions = random.sample(all_positions, min(num_filled, 81))

        for i, j in positions:
            grid[i][j] = random.choice(self.all_materials)

        return grid

    def corrupt_valid(self, valid_grid):
        """Corrupt a valid recipe by swapping 1-2 materials (occasionally more)"""
        import random

        corrupted = copy.deepcopy(valid_grid)

        # Find filled positions
        filled_positions = [
            (i, j) for i in range(9)
            for j in range(9)
            if corrupted[i][j] is not None
        ]

        if len(filled_positions) < 1:
            return self.generate_random()

        # Mostly 1-2 swaps, occasionally 3-4
        weights = [50, 35, 10, 5]  # 50% for 1, 35% for 2, 10% for 3, 5% for 4
        num_swaps = random.choices([1, 2, 3, 4], weights=weights)[0]
        num_swaps = min(num_swaps, len(filled_positions))

        swap_positions = random.sample(filled_positions, num_swaps)

        for i, j in swap_positions:
            # Swap with a different random material
            current = corrupted[i][j]
            available = [m for m in self.all_materials if m != current]
            corrupted[i][j] = random.choice(available)

        return corrupted

    def remove_materials(self, valid_grid):
        """Remove 1-3 materials from valid recipe"""
        import random

        incomplete = copy.deepcopy(valid_grid)

        # Find filled positions
        filled_positions = [
            (i, j) for i in range(9)
            for j in range(9)
            if incomplete[i][j] is not None
        ]

        if len(filled_positions) <= 1:
            return self.generate_random()

        num_remove = min(random.randint(1, 3), len(filled_positions) - 1)
        remove_positions = random.sample(filled_positions, num_remove)

        for i, j in remove_positions:
            incomplete[i][j] = None

        return incomplete

    def generate_batch(self, count, valid_grids):
        """Generate batch of invalid recipes matching the distribution"""
        import random

        invalid_grids = []

        # 25% random (completely random patterns)
        num_random = count // 4
        for _ in range(num_random):
            invalid_grids.append(self.generate_random())

        # 50% corrupted (swapped materials)
        num_corrupted = count // 2
        for _ in range(num_corrupted):
            base = random.choice(valid_grids)
            invalid_grids.append(self.corrupt_valid(base))

        # 25% incomplete (removed materials)
        num_incomplete = count // 4
        for _ in range(num_incomplete):
            base = random.choice(valid_grids)
            invalid_grids.append(self.remove_materials(base))

        # Fill to exact count with corrupted recipes
        while len(invalid_grids) < count:
            base = random.choice(valid_grids)
            invalid_grids.append(self.corrupt_valid(base))

        return invalid_grids[:count]

    def create_invalid_dataset(self, valid_grids, cell_size=4):
        """Create complete invalid dataset matching valid count"""
        count = len(valid_grids)

        print(f"\n=== Generating Invalid Recipes ===")
        print(f"Target count: {count}")

        invalid_grids = self.generate_batch(count, valid_grids)

        print(f"Generated: {len(invalid_grids)} invalid recipes")
        print(f"  - ~{count // 4} random")
        print(f"  - ~{count // 2} corrupted valid")
        print(f"  - ~{count // 4} incomplete")

        # Convert to images
        print("\n=== Converting Invalid to Images ===")
        images = []
        for grid in invalid_grids:
            img = self.processor.grid_to_image(grid, cell_size)
            images.append(img)

        return np.array(images, dtype=np.float32), invalid_grids


# Example usage
if __name__ == "__main__":
    import random

    random.seed(42)
    np.random.seed(42)

    # File paths - relative to CNN folder
    MATERIALS_PATH = "../../../Game-1-modular/items.JSON/items-materials-1.JSON"
    PLACEMENTS_PATH = "../../../Game-1-modular/placements.JSON/placements-smithing-1.JSON"

    processor = RecipeDataProcessor(MATERIALS_PATH, PLACEMENTS_PATH)

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
        np.ones(len(X_valid), dtype=np.float32),  # 1 = valid
        np.zeros(len(X_invalid), dtype=np.float32)  # 0 = invalid
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
    print(f"Total examples: {len(X_all)}")
    print(f"  Valid: {len(X_valid)} ({len(X_valid) / len(X_all) * 100:.1f}%)")
    print(f"  Invalid: {len(X_invalid)} ({len(X_invalid) / len(X_all) * 100:.1f}%)")
    print(f"\nTraining set: {len(X_train)} examples")
    print(f"  Valid: {int(y_train.sum())} ({y_train.sum() / len(y_train) * 100:.1f}%)")
    print(
        f"  Invalid: {int(len(y_train) - y_train.sum())} ({(len(y_train) - y_train.sum()) / len(y_train) * 100:.1f}%)")
    print(f"\nValidation set: {len(X_val)} examples")
    print(f"  Valid: {int(y_val.sum())} ({y_val.sum() / len(y_val) * 100:.1f}%)")
    print(f"  Invalid: {int(len(y_val) - y_val.sum())} ({(len(y_val) - y_val.sum()) / len(y_val) * 100:.1f}%)")

    print(f"\nImage shape: {X_train.shape[1:]}")
    print(f"Data type: {X_train.dtype}")
    print(f"Value range: [{X_all.min():.3f}, {X_all.max():.3f}]")

    # Save dataset
    output_path = "recipe_dataset.npz"
    np.savez_compressed(
        output_path,
        X_train=X_train,
        y_train=y_train,
        X_val=X_val,
        y_val=y_val
    )
    print(f"\n✓ Saved complete dataset to: {output_path}")
    print(f"  Ready for CNN training!")
import json
import numpy as np
from colorsys import hsv_to_rgb
import tensorflow as tf
from pathlib import Path


class RecipeValidator:
    """Uses trained CNN to validate smithing recipes.

    CRITICAL: This must match the training data generation exactly!
    Training uses: shape masks + tier fill masks + bounding box centering
    """

    # Shape masks by category - MUST MATCH valid_smithing_data_v2.py
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

    def __init__(self, model_path, materials_path):
        print(f"Loading model from: {model_path}")
        self.model = tf.keras.models.load_model(model_path)
        print("[OK] Model loaded successfully\n")

        # Load materials data
        with open(materials_path, 'r') as f:
            materials_data = json.load(f)

        self.materials_dict = {
            mat['materialId']: mat
            for mat in materials_data['materials']
        }
        print(f"[OK] Loaded {len(self.materials_dict)} materials\n")

    def get_shape_mask(self, material_id):
        """Get the 4x4 shape mask for a material's category."""
        if material_id is None or material_id not in self.materials_dict:
            return self.DEFAULT_SHAPE

        category = self.materials_dict[material_id].get('category', 'unknown')
        return self.CATEGORY_SHAPES.get(category, self.DEFAULT_SHAPE)

    def get_tier_fill_mask(self, material_id, cell_size=4):
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

    def material_to_color(self, material_id):
        """Convert material to RGB color (same as training)"""
        if material_id is None:
            return np.array([0.0, 0.0, 0.0])

        if material_id not in self.materials_dict:
            print(f"[!] Warning: Unknown material '{material_id}', treating as empty")
            return np.array([0.0, 0.0, 0.0])

        material = self.materials_dict[material_id]
        category = material['category']
        tier = material['tier']
        tags = material.get('metadata', {}).get('tags', [])

        # CATEGORY -> HUE
        if category == 'elemental':
            element_hues = {
                'fire': 0, 'water': 210, 'earth': 120, 'air': 60,
                'lightning': 270, 'ice': 180, 'light': 45, 'dark': 280,
                'void': 290, 'chaos': 330
            }
            hue = 280
            for tag in tags:
                if tag in element_hues:
                    hue = element_hues[tag]
                    break
        else:
            category_hues = {
                'metal': 210, 'wood': 30, 'stone': 0, 'monster_drop': 300
            }
            hue = category_hues.get(category, 0)

        # TIER -> VALUE
        tier_values = {1: 0.50, 2: 0.65, 3: 0.80, 4: 0.95}
        value = tier_values.get(tier, 0.5)

        # TAGS -> SATURATION
        base_saturation = 0.6
        if category == 'stone':
            base_saturation = 0.2
        if 'legendary' in tags or 'mythical' in tags:
            base_saturation = min(1.0, base_saturation + 0.2)
        elif 'magical' in tags or 'ancient' in tags:
            base_saturation = min(1.0, base_saturation + 0.1)

        # Convert HSV to RGB
        hue_normalized = hue / 360.0
        rgb = hsv_to_rgb(hue_normalized, base_saturation, value)

        return np.array(rgb)

    def grid_to_image(self, grid, cell_size=4):
        """
        Convert 9x9 grid to 36x36 RGB image.

        CRITICAL: Must use shape masks and tier fill to match training!
        """
        img_size = 9 * cell_size
        img = np.zeros((img_size, img_size, 3), dtype=np.float32)

        for i in range(9):
            for j in range(9):
                material_id = grid[i][j]

                if material_id is None:
                    # Empty cell = black
                    continue

                # Get base color
                color = self.material_to_color(material_id)

                # Get shape mask based on category
                shape_mask = self.get_shape_mask(material_id)

                # Get tier fill mask
                tier_mask = self.get_tier_fill_mask(material_id, cell_size)

                # Combined mask: shape AND tier
                combined_mask = shape_mask * tier_mask

                # Create cell with masked color
                cell = np.zeros((cell_size, cell_size, 3), dtype=np.float32)
                for c in range(3):
                    cell[:, :, c] = color[c] * combined_mask

                # Place cell in image
                img[i * cell_size:(i + 1) * cell_size,
                    j * cell_size:(j + 1) * cell_size] = cell

        return img

    def placement_to_grid(self, placement_map, grid_size):
        """
        Convert placement format to 9x9 grid using bounding box centering.

        CRITICAL: Must match training data generation algorithm!
        """
        grid = [[None] * 9 for _ in range(9)]

        # Parse all positions first to find bounding box
        positions = []
        for pos_str, material_id in placement_map.items():
            y_idx, x_idx = map(int, pos_str.split(','))
            positions.append((y_idx, x_idx, material_id))

        if not positions:
            return grid

        # Calculate actual bounding box (matching training)
        min_y = min(p[0] for p in positions)
        max_y = max(p[0] for p in positions)
        min_x = min(p[1] for p in positions)
        max_x = max(p[1] for p in positions)

        actual_height = max_y - min_y + 1
        actual_width = max_x - min_x + 1

        # Center using actual dimensions (matching training)
        offset_y = (9 - actual_height) // 2
        offset_x = (9 - actual_width) // 2

        # Place materials with normalization (subtract min to get 0-based)
        for y_idx, x_idx, material_id in positions:
            final_y = offset_y + (y_idx - min_y)
            final_x = offset_x + (x_idx - min_x)

            if 0 <= final_y < 9 and 0 <= final_x < 9:
                grid[final_y][final_x] = material_id
            else:
                print(f"[!] Warning: Position ({y_idx},{x_idx}) exceeds 9x9 grid bounds")

        return grid

    def validate_placement(self, placement_data):
        """Validate from placement JSON format"""
        grid = self.placement_to_grid(
            placement_data['placementMap'],
            placement_data['metadata']['gridSize']
        )

        # Convert to image (with shape masks and tier fill)
        img = self.grid_to_image(grid)

        # Add batch dimension and predict
        img_batch = np.expand_dims(img, axis=0)
        prediction = self.model.predict(img_batch, verbose=0)[0][0]

        # Interpret (threshold at 0.5)
        is_valid = prediction >= 0.5
        confidence = prediction if is_valid else (1 - prediction)

        return {
            'valid': bool(is_valid),
            'confidence': float(confidence),
            'prediction': float(prediction)
        }


def test_recipes_from_file():
    """Interactive test script"""

    print("=" * 70)
    print("RECIPE VALIDATOR - TEST MODE")
    print("=" * 70)
    print()

    # Get paths from user
    print("Configuration:")
    print("-" * 70)

    model_path = input("Enter path to model file (.keras): ").strip()
    if not model_path:
        model_path = "batch 4 (batch 3, no stations)/excellent_minimal_lr_0_0012.keras"
        print(f"  Using default: {model_path}")

    materials_path = input("Enter path to materials JSON: ").strip()
    if not materials_path:
        materials_path = "../../../Game-1-modular/items.JSON/items-materials-1.JSON"
        print(f"  Using default: {materials_path}")

    # Verify files exist
    if not Path(model_path).exists():
        print(f"\n[X] Error: Model file not found: {model_path}")
        return

    if not Path(materials_path).exists():
        print(f"\n[X] Error: Materials file not found: {materials_path}")
        return

    print("\n" + "=" * 70)
    print()

    # Initialize validator
    try:
        validator = RecipeValidator(model_path, materials_path)
    except Exception as e:
        print(f"[X] Error loading validator: {e}")
        return

    # Get test file path
    print("=" * 70)
    test_file = input("Enter path to test recipes JSON file: ").strip()

    if not test_file:
        print("[X] No file provided")
        return

    if not Path(test_file).exists():
        print(f"[X] Error: Test file not found: {test_file}")
        return

    print("\n" + "=" * 70)
    print(f"Testing recipes from: {test_file}")
    print("=" * 70)
    print()

    # Load and validate recipes
    try:
        with open(test_file, 'r') as f:
            data = json.load(f)

        placements = data.get('placements', [])
        total = len(placements)

        if total == 0:
            print("[X] No placements found in file")
            return

        print(f"Found {total} recipes to test\n")
        print("=" * 70)

        # Track results
        valid_count = 0
        invalid_count = 0
        results = []

        # Test each recipe
        for i, placement in enumerate(placements, 1):
            recipe_id = placement.get('recipeId', f'recipe_{i}')

            try:
                result = validator.validate_placement(placement)
                results.append((recipe_id, result))

                if result['valid']:
                    valid_count += 1
                    symbol = "[OK]"
                else:
                    invalid_count += 1
                    symbol = "[X] "

                # Print result
                conf_bar = "#" * int(result['confidence'] * 20)
                print(f"{i:3d}. {symbol} {recipe_id:40s} "
                      f"[{conf_bar:20s}] {result['confidence'] * 100:5.1f}%")

            except Exception as e:
                print(f"{i:3d}. [!]  {recipe_id:40s} ERROR: {str(e)[:30]}")
                invalid_count += 1

        # Summary
        print("\n" + "=" * 70)
        print("SUMMARY")
        print("=" * 70)
        print(f"Total recipes:       {total}")
        print(f"Valid:              {valid_count:3d} ({valid_count / total * 100:5.1f}%)")
        print(f"Invalid:            {invalid_count:3d} ({invalid_count / total * 100:5.1f}%)")

        if results:
            avg_confidence = np.mean([r[1]['confidence'] for r in results])
            print(f"Average confidence: {avg_confidence * 100:5.1f}%")

        # Show invalid recipes if any
        invalid_recipes = [(rid, r) for rid, r in results if not r['valid']]
        if invalid_recipes:
            print("\n" + "-" * 70)
            print("INVALID RECIPES:")
            print("-" * 70)
            for recipe_id, result in invalid_recipes:
                print(f"  {recipe_id:40s} {result['confidence'] * 100:5.1f}% confidence")

        # Show lowest confidence valid recipes
        valid_recipes = [(rid, r) for rid, r in results if r['valid']]
        if valid_recipes:
            valid_recipes.sort(key=lambda x: x[1]['confidence'])
            lowest_valid = valid_recipes[:5]

            print("\n" + "-" * 70)
            print("LOWEST CONFIDENCE VALID RECIPES (Review Recommended):")
            print("-" * 70)
            for recipe_id, result in lowest_valid:
                print(f"  {recipe_id:40s} {result['confidence'] * 100:5.1f}% confidence")

        print("\n" + "=" * 70)
        print("Testing complete!")
        print("=" * 70)

    except json.JSONDecodeError as e:
        print(f"[X] Error: Invalid JSON file: {e}")
    except Exception as e:
        print(f"[X] Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    test_recipes_from_file()

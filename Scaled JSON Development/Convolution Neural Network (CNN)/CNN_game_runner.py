import json
import numpy as np
from colorsys import hsv_to_rgb
from pathlib import Path
import tensorflow as tf


class RecipeValidator:
    """Uses trained CNN to validate smithing recipes"""

    def __init__(self, model_path, materials_path):
        """
        Initialize the validator

        Args:
            model_path: Path to trained .keras model
            materials_path: Path to items-materials-1.JSON
        """
        print(f"Loading model from: {model_path}")
        self.model = tf.keras.models.load_model(model_path)
        print("✓ Model loaded successfully")

        # Load materials data
        with open(materials_path, 'r') as f:
            materials_data = json.load(f)

        self.materials_dict = {
            mat['materialId']: mat
            for mat in materials_data['materials']
        }
        print(f"✓ Loaded {len(self.materials_dict)} materials")

    def material_to_color(self, material_id):
        """Convert material to RGB color (same as training)"""
        if material_id is None:
            return np.array([0.0, 0.0, 0.0])

        material = self.materials_dict[material_id]
        category = material['category']
        tier = material['tier']
        tags = material['metadata']['tags']

        # CATEGORY → HUE
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

        # TIER → VALUE
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
        hue_normalized = hue / 360.0
        rgb = hsv_to_rgb(hue_normalized, base_saturation, value)

        return np.array(rgb)

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

    def placement_to_grid(self, placement_map, grid_size):
        """Convert placement format to 9x9 grid"""
        grid = [[None] * 9 for _ in range(9)]

        recipe_size = int(grid_size.split('x')[0])
        offset = (9 - recipe_size) // 2

        for pos_str, material_id in placement_map.items():
            y_idx, x_idx = map(int, pos_str.split(','))
            grid[offset + y_idx - 1][offset + x_idx - 1] = material_id

        return grid

    def validate_grid(self, grid):
        """
        Validate a 9x9 grid

        Args:
            grid: 9x9 list of lists with material IDs (None for empty)

        Returns:
            dict with 'valid' (bool), 'confidence' (float), 'prediction' (float)
        """
        # Convert to image
        img = self.grid_to_image(grid)

        # Add batch dimension
        img_batch = np.expand_dims(img, axis=0)

        # Predict
        prediction = self.model.predict(img_batch, verbose=0)[0][0]

        # Interpret (threshold at 0.5)
        is_valid = prediction >= 0.5
        confidence = prediction if is_valid else (1 - prediction)

        return {
            'valid': bool(is_valid),
            'confidence': float(confidence),
            'prediction': float(prediction)
        }

    def validate_placement(self, placement_data):
        """
        Validate from placement JSON format

        Args:
            placement_data: Dict with 'placementMap' and 'metadata.gridSize'

        Returns:
            dict with validation results
        """
        grid = self.placement_to_grid(
            placement_data['placementMap'],
            placement_data['metadata']['gridSize']
        )
        return self.validate_grid(grid)

    def validate_recipe_file(self, recipe_path):
        """
        Validate recipe from JSON file

        Args:
            recipe_path: Path to placement JSON file

        Returns:
            dict mapping recipeId to validation results
        """
        with open(recipe_path, 'r') as f:
            data = json.load(f)

        results = {}
        for placement in data['placements']:
            recipe_id = placement['recipeId']
            result = self.validate_placement(placement)
            results[recipe_id] = result

        return results


def print_validation_result(recipe_id, result):
    """Pretty print validation result"""
    status = "✓ VALID" if result['valid'] else "✗ INVALID"
    confidence = result['confidence'] * 100

    print(f"\n{'=' * 60}")
    print(f"Recipe: {recipe_id}")
    print(f"Status: {status}")
    print(f"Confidence: {confidence:.1f}%")
    print(f"Raw Prediction: {result['prediction']:.4f}")
    print(f"{'=' * 60}")


# Example usage
if __name__ == "__main__":
    # Paths - adjust these to your setup
    MODEL_PATH = "excellent_minimal_lr_0_0012.keras"  # Your best model
    MATERIALS_PATH = "../../Game-1-modular/items.JSON/items-materials-1.JSON"
    PLACEMENTS_PATH = "../../Game-1-modular/placements.JSON/placements-smithing-1.JSON"

    # Initialize validator
    validator = RecipeValidator(MODEL_PATH, MATERIALS_PATH)

    print("\n" + "=" * 60)
    print("RECIPE VALIDATION SYSTEM")
    print("=" * 60)

    # Option 1: Validate all recipes from file
    print("\n--- Validating all recipes from file ---")
    results = validator.validate_recipe_file(PLACEMENTS_PATH)

    # Summary statistics
    total = len(results)
    valid_count = sum(1 for r in results.values() if r['valid'])
    invalid_count = total - valid_count
    avg_confidence = np.mean([r['confidence'] for r in results.values()])

    print(f"\nTotal recipes tested: {total}")
    print(f"Valid: {valid_count} ({valid_count / total * 100:.1f}%)")
    print(f"Invalid: {invalid_count} ({invalid_count / total * 100:.1f}%)")
    print(f"Average confidence: {avg_confidence * 100:.1f}%")

    # Show any recipes flagged as invalid (should be none for training data!)
    invalid_recipes = [rid for rid, r in results.items() if not r['valid']]
    if invalid_recipes:
        print(f"\n⚠️  Recipes flagged as invalid:")
        for rid in invalid_recipes:
            print(f"  - {rid}: {results[rid]['confidence'] * 100:.1f}% confidence")
    else:
        print("\n✓ All recipes validated successfully!")

    # Option 2: Test a custom grid
    print("\n\n--- Testing custom recipe ---")

    # Example: Simple 3x3 iron sword recipe
    custom_grid = [[None] * 9 for _ in range(9)]
    # Center a 3x3 pattern (iron ingots in shape of sword)
    custom_grid[3][4] = "iron_ingot"  # Top
    custom_grid[4][4] = "iron_ingot"  # Middle
    custom_grid[5][4] = "iron_ingot"  # Bottom
    custom_grid[6][4] = "oak_plank"  # Handle

    result = validator.validate_grid(custom_grid)
    print_validation_result("custom_sword", result)

    # Option 3: Test invalid recipe (random materials)
    print("\n--- Testing invalid recipe ---")
    invalid_grid = [[None] * 9 for _ in range(9)]
    invalid_grid[0][0] = "iron_ingot"
    invalid_grid[0][8] = "dragon_scale"
    invalid_grid[8][0] = "oak_plank"
    invalid_grid[8][8] = "phoenix_feather"

    result = validator.validate_grid(invalid_grid)
    print_validation_result("random_invalid", result)

    print("\n" + "=" * 60)
    print("Validation complete!")
    print("=" * 60)
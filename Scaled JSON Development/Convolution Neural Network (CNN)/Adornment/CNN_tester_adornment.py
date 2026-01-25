import numpy as np
import tensorflow as tf
from tensorflow import keras
import json
from pathlib import Path
import matplotlib.pyplot as plt
from matplotlib.patches import Circle
from datetime import datetime
import sys


class AdornmentCNNTester:
    """Test/run trained CNN on new adornment recipes"""

    def __init__(self, model_path, materials_path):
        """
        Args:
            model_path: Path to trained .keras model
            materials_path: Path to materials JSON file
        """
        print(f"Loading model from: {model_path}")
        self.model = keras.models.load_model(model_path)
        print("✓ Model loaded successfully")

        # Load materials for rendering
        with open(materials_path, 'r') as f:
            materials_data = json.load(f)

        self.materials_dict = {
            mat['materialId']: mat
            for mat in materials_data['materials']
        }
        print(f"✓ Loaded {len(self.materials_dict)} materials")

    def material_to_color(self, material_id):
        """Convert material to RGB color (same as processor)"""
        if material_id is None:
            return np.array([0.5, 0.5, 0.5])

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

        # SATURATION
        base_saturation = 0.6
        if category == 'stone':
            base_saturation = 0.2
        if 'legendary' in tags or 'mythical' in tags:
            base_saturation = min(1.0, base_saturation + 0.2)
        elif 'magical' in tags or 'ancient' in tags:
            base_saturation = min(1.0, base_saturation + 0.1)

        from colorsys import hsv_to_rgb
        rgb = hsv_to_rgb(hue / 360.0, base_saturation, value)
        return np.array(rgb)

    def render_recipe(self, vertices, shapes, img_size=56):
        """Render recipe to image (same as processor)"""
        img = np.zeros((img_size, img_size, 3), dtype=np.float32)

        def coord_to_pixel(x, y):
            px = int((x + 7) * 4)
            py = int((7 - y) * 4)
            return px, py

        # Draw lines
        for shape in shapes:
            shape_vertices = shape['vertices']
            n = len(shape_vertices)

            for i in range(n):
                v1_str = shape_vertices[i]
                v2_str = shape_vertices[(i + 1) % n]

                x1, y1 = map(int, v1_str.split(','))
                x2, y2 = map(int, v2_str.split(','))
                px1, py1 = coord_to_pixel(x1, y1)
                px2, py2 = coord_to_pixel(x2, y2)

                mat1 = vertices.get(v1_str, {}).get('materialId')
                mat2 = vertices.get(v2_str, {}).get('materialId')

                if mat1 and mat2:
                    color = (self.material_to_color(mat1) + self.material_to_color(mat2)) / 2
                elif mat1:
                    color = self.material_to_color(mat1)
                elif mat2:
                    color = self.material_to_color(mat2)
                else:
                    color = np.array([0.3, 0.3, 0.3])

                self._draw_line(img, px1, py1, px2, py2, color, thickness=2)

        # Draw vertices
        for coord_str, vertex_data in vertices.items():
            x, y = map(int, coord_str.split(','))
            px, py = coord_to_pixel(x, y)
            material_id = vertex_data.get('materialId')
            color = self.material_to_color(material_id)
            self._draw_circle(img, px, py, radius=3, color=color)

        return img

    def _draw_line(self, img, x0, y0, x1, y1, color, thickness=1):
        """Draw line with blending"""
        dx = abs(x1 - x0)
        dy = abs(y1 - y0)
        sx = 1 if x0 < x1 else -1
        sy = 1 if y0 < y1 else -1
        err = dx - dy

        while True:
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

    def _draw_circle(self, img, cx, cy, radius, color):
        """Draw filled circle"""
        for y in range(max(0, cy - radius), min(img.shape[0], cy + radius + 1)):
            for x in range(max(0, cx - radius), min(img.shape[1], cx + radius + 1)):
                if (x - cx) ** 2 + (y - cy) ** 2 <= radius ** 2:
                    img[y, x] = color

    def predict_recipe(self, vertices, shapes, threshold=0.5, visualize=False):
        """
        Predict if a recipe is valid/invalid

        Args:
            vertices: Dict of vertex positions and materials
            shapes: List of shape definitions
            threshold: Classification threshold (default 0.5)
            visualize: Whether to show the recipe image

        Returns:
            dict with prediction results
        """
        # Render recipe
        img = self.render_recipe(vertices, shapes)

        # Predict
        img_batch = np.expand_dims(img, axis=0)
        prob = self.model.predict(img_batch, verbose=0)[0][0]

        is_valid = prob >= threshold
        confidence = prob if is_valid else (1 - prob)

        result = {
            'is_valid': bool(is_valid),
            'probability': float(prob),
            'confidence': float(confidence),
            'label': 'VALID' if is_valid else 'INVALID'
        }

        # Visualize if requested
        if visualize:
            self._visualize_prediction(img, result)

        return result

    def _visualize_prediction(self, img, result):
        """Visualize recipe with prediction"""
        plt.figure(figsize=(8, 8))
        plt.imshow(img)
        plt.axis('off')

        # Add prediction text
        label = result['label']
        prob = result['probability']
        color = 'green' if result['is_valid'] else 'red'

        plt.title(f"{label} (p={prob:.4f})",
                  fontsize=16, fontweight='bold', color=color)

        plt.tight_layout()
        plt.show()

    def predict_from_json(self, recipe_json, visualize=False):
        """
        Predict from recipe JSON format

        Args:
            recipe_json: Dict with recipeId and placementMap
            visualize: Whether to show the recipe image
        """
        vertices = recipe_json['placementMap']['vertices']
        shapes = recipe_json['placementMap']['shapes']

        result = self.predict_recipe(vertices, shapes, visualize=visualize)

        print("\n" + "=" * 60)
        print(f"Recipe: {recipe_json.get('recipeId', 'Unknown')}")
        print("=" * 60)
        print(f"Prediction: {result['label']}")
        print(f"Probability: {result['probability']:.4f}")
        print(f"Confidence: {result['confidence']:.4f}")
        print("=" * 60 + "\n")

        return result

    def batch_predict(self, recipes_json_path, output_path=None, visualize_failures=False, model_name=None):
        """
        Predict on multiple recipes from JSON file

        Args:
            recipes_json_path: Path to JSON file with recipes
            output_path: Optional path to save results
            visualize_failures: Show images of failed predictions
            model_name: Optional model name to include in results
        """
        with open(recipes_json_path, 'r') as f:
            data = json.load(f)

        recipes = data['placements']
        results = []

        header = f"BATCH PREDICTION ON {len(recipes)} RECIPES"
        if model_name:
            header += f" - Model: {model_name}"

        print("\n" + "=" * 80)
        print(header)
        print("=" * 80 + "\n")

        for recipe in recipes:
            recipe_id = recipe['recipeId']
            vertices = recipe['placementMap']['vertices']
            shapes = recipe['placementMap']['shapes']

            result = self.predict_recipe(vertices, shapes)
            result['recipeId'] = recipe_id
            if model_name:
                result['model_name'] = model_name
            results.append(result)

            status = "✓" if result['is_valid'] else "✗"
            print(f"{status} {recipe_id:50s} | {result['label']:7s} (p={result['probability']:.4f})")

            # Visualize failures if requested
            if visualize_failures and not result['is_valid']:
                img = self.render_recipe(vertices, shapes)
                self._visualize_prediction(img, result)

        # Summary statistics
        valid_count = sum(1 for r in results if r['is_valid'])
        invalid_count = len(results) - valid_count
        avg_confidence = np.mean([r['confidence'] for r in results])

        print("\n" + "=" * 80)
        print("SUMMARY")
        print("=" * 80)
        print(f"Total recipes: {len(results)}")
        print(f"Predicted VALID: {valid_count} ({valid_count / len(results) * 100:.1f}%)")
        print(f"Predicted INVALID: {invalid_count} ({invalid_count / len(results) * 100:.1f}%)")
        print(f"Average confidence: {avg_confidence:.4f}")
        print("=" * 80 + "\n")

        # Save results if requested
        if output_path:
            summary = {
                'model_name': model_name,
                'total_recipes': len(results),
                'valid_count': valid_count,
                'invalid_count': invalid_count,
                'avg_confidence': avg_confidence,
                'predictions': results
            }
            with open(output_path, 'w') as f:
                json.dump(summary, f, indent=2)
            print(f"✓ Results saved to: {output_path}")

        return results

    def interactive_test(self):
        """Interactive testing mode"""
        print("\n" + "=" * 60)
        print("INTERACTIVE TESTING MODE")
        print("=" * 60)
        print("Enter recipe JSON or 'quit' to exit")
        print("Example format:")
        print("""
{
  "recipeId": "test_recipe",
  "placementMap": {
    "vertices": {
      "0,0": {"materialId": "iron_ingot", "isKey": false},
      "2,0": {"materialId": "iron_ingot", "isKey": false}
    },
    "shapes": [
      {
        "type": "line",
        "vertices": ["0,0", "2,0"]
      }
    ]
  }
}
        """)
        print("=" * 60 + "\n")

        while True:
            try:
                print("Enter recipe JSON (or 'quit'):")
                user_input = input().strip()

                if user_input.lower() == 'quit':
                    break

                recipe_json = json.loads(user_input)
                self.predict_from_json(recipe_json, visualize=True)

            except json.JSONDecodeError:
                print("Invalid JSON format. Please try again.")
            except KeyboardInterrupt:
                print("\nExiting...")
                break
            except Exception as e:
                print(f"Error: {e}")


# Example usage
if __name__ == "__main__":
    import sys
    from pathlib import Path

    # Default paths
    DEFAULT_MATERIALS_PATH = "C:/Users/Vincent/PycharmProjects/Game-1/Game-1-modular/items.JSON/items-materials-1.JSON"
    DEFAULT_RECIPES_PATH = "C:/Users/Vincent/PycharmProjects/Game-1/Game-1-modular/placements.JSON/placements-adornments-1.JSON"

    # Check if model path provided as argument
    if len(sys.argv) > 1:
        model_paths = [Path(sys.argv[1])]
        test_all_models = False
    else:
        # Interactive prompt
        print("\n" + "=" * 80)
        print("ADORNMENT RECIPE CNN TESTER")
        print("=" * 80)

        # List available models
        model_dirs = [
            Path("models"),
            Path("smart_search_results"),
            Path("targeted_results"),
            Path("experiment_results")
        ]

        available_models = []
        for model_dir in model_dirs:
            if model_dir.exists():
                models = list(model_dir.glob("*.keras"))
                available_models.extend(models)

        if available_models:
            # Sort by modification time (most recent first)
            available_models.sort(key=lambda p: p.stat().st_mtime, reverse=True)

            print(f"\nFound {len(available_models)} available models:")
            for i, model_file in enumerate(available_models, 1):
                size_mb = model_file.stat().st_size / (1024 * 1024)
                # Extract accuracy from filename if present
                name = model_file.name
                acc_str = ""
                if "acc" in name:
                    try:
                        acc_part = name.split("acc")[1].split("_")[0]
                        acc_str = f" - Acc: {acc_part}"
                    except:
                        pass
                print(f"  {i}. {model_file.name}{acc_str}")
                print(f"     ({size_mb:.1f} MB) - {model_file.parent.name}/{model_file.name}")

            print("\nOptions:")
            print("  - Enter 'all' to test ALL models")
            print("  - Enter model number (1-{})".format(len(available_models)))
            print("  - Enter full path to model file")
            print("  - Press Enter to use most recent model")

            user_input = input("\nYour choice: ").strip()

            if user_input.lower() == "all":
                # Test all models
                model_paths = available_models
                test_all_models = True
                print(f"\nWill test all {len(model_paths)} models!")
            elif user_input == "":
                # Use most recent model
                model_paths = [available_models[0]]
                test_all_models = False
                print(f"Using most recent model: {model_paths[0].name}")
            elif user_input.isdigit():
                # Use numbered selection
                idx = int(user_input) - 1
                if 0 <= idx < len(available_models):
                    model_paths = [available_models[idx]]
                    test_all_models = False
                    print(f"Selected: {model_paths[0].name}")
                else:
                    print("Invalid selection. Exiting.")
                    sys.exit(1)
            else:
                # Use provided path
                model_paths = [Path(user_input)]
                test_all_models = False
                if not model_paths[0].exists():
                    print(f"Error: Model file not found at {model_paths[0]}")
                    sys.exit(1)
        else:
            print("\nNo models found in standard directories.")
            model_path = input("Enter full path to model file: ").strip()
            model_paths = [Path(model_path)]
            test_all_models = False

            if not model_paths[0].exists():
                print(f"Error: Model file not found at {model_paths[0]}")
                sys.exit(1)

    # Get materials path
    materials_path = DEFAULT_MATERIALS_PATH
    if not Path(materials_path).exists():
        print(f"\nWarning: Materials file not found at default path")
        materials_path = input("Enter path to materials JSON file: ").strip()

    # If testing all models, run batch prediction on each
    if len(model_paths) > 1 or (len(sys.argv) <= 1 and 'test_all_models' in locals() and test_all_models):
        print(f"\n{'=' * 80}")
        print(f"TESTING ALL {len(model_paths)} MODELS")
        print(f"{'=' * 80}\n")

        # Get recipes path
        recipes_path = DEFAULT_RECIPES_PATH
        if not Path(recipes_path).exists():
            recipes_path = input("Enter path to recipes JSON file: ").strip()

        # Results directory
        all_results_dir = Path("all_models_comparison")
        all_results_dir.mkdir(exist_ok=True)

        # Store results for comparison
        all_model_results = []

        for i, model_path in enumerate(model_paths, 1):
            print(f"\n{'#' * 80}")
            print(f"MODEL {i}/{len(model_paths)}: {model_path.name}")
            print(f"{'#' * 80}")

            try:
                # Initialize tester
                tester = AdornmentCNNTester(
                    model_path=str(model_path),
                    materials_path=materials_path
                )

                # Run batch prediction
                output_file = all_results_dir / f"{model_path.stem}_predictions.json"
                results = tester.batch_predict(
                    recipes_json_path=recipes_path,
                    output_path=str(output_file),
                    visualize_failures=False,
                    model_name=model_path.name
                )

                # Store summary
                valid_count = sum(1 for r in results if r['is_valid'])
                all_model_results.append({
                    'model_name': model_path.name,
                    'model_path': str(model_path),
                    'total_recipes': len(results),
                    'valid_count': valid_count,
                    'invalid_count': len(results) - valid_count,
                    'valid_percentage': valid_count / len(results) * 100,
                    'avg_confidence': np.mean([r['confidence'] for r in results]),
                    'predictions': results
                })

            except Exception as e:
                print(f"ERROR testing {model_path.name}: {e}")
                continue

        # Save comparison summary
        comparison_file = all_results_dir / f"comparison_summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(comparison_file, 'w') as f:
            json.dump({
                'timestamp': datetime.now().isoformat(),
                'total_models_tested': len(all_model_results),
                'models': sorted(all_model_results, key=lambda x: x['valid_percentage'], reverse=True)
            }, f, indent=2)

        # Print comparison
        print(f"\n{'=' * 80}")
        print("ALL MODELS COMPARISON")
        print(f"{'=' * 80}")
        print(f"{'Model':<50} {'Valid %':>10} {'Avg Conf':>10}")
        print(f"{'-' * 80}")

        for result in sorted(all_model_results, key=lambda x: x['valid_percentage'], reverse=True):
            print(f"{result['model_name']:<50} {result['valid_percentage']:>9.1f}% {result['avg_confidence']:>10.4f}")

        print(f"\n✓ Comparison saved to: {comparison_file}")
        print(f"✓ Individual results saved to: {all_results_dir}/")
        print(f"{'=' * 80}\n")

        sys.exit(0)

    # Single model testing - interactive menu
    model_path = model_paths[0]

    # Initialize tester
    print(f"\n{'=' * 80}")
    tester = AdornmentCNNTester(
        model_path=str(model_path),
        materials_path=materials_path
    )
    print(f"{'=' * 80}")

    # Menu
    while True:
        print("\n" + "=" * 80)
        print("TESTING OPTIONS")
        print("=" * 80)
        print("1. Test on all recipes (batch prediction)")
        print("2. Test single recipe from JSON")
        print("3. Interactive testing mode")
        print("4. Exit")

        choice = input("\nSelect option (1-4): ").strip()

        if choice == "1":
            # Batch prediction
            recipes_path = DEFAULT_RECIPES_PATH
            if not Path(recipes_path).exists():
                recipes_path = input("Enter path to recipes JSON file: ").strip()

            output_path = input("Enter output path for results (or press Enter for 'predictions.json'): ").strip()
            if not output_path:
                output_path = "predictions.json"

            visualize = input("Visualize failures? (y/n): ").strip().lower() == 'y'

            results = tester.batch_predict(
                recipes_json_path=recipes_path,
                output_path=output_path,
                visualize_failures=visualize,
                model_name=model_path.name
            )

        elif choice == "2":
            # Single recipe
            recipe_path = input("Enter path to recipe JSON file: ").strip()
            try:
                with open(recipe_path, 'r') as f:
                    recipe_json = json.load(f)

                # If it's a full placements file, ask which recipe
                if 'placements' in recipe_json:
                    print(f"\nFound {len(recipe_json['placements'])} recipes in file:")
                    for i, p in enumerate(recipe_json['placements'][:10], 1):
                        print(f"  {i}. {p['recipeId']}")
                    if len(recipe_json['placements']) > 10:
                        print(f"  ... and {len(recipe_json['placements']) - 10} more")

                    idx = int(input("\nSelect recipe number: ").strip()) - 1
                    recipe_json = recipe_json['placements'][idx]

                result = tester.predict_from_json(recipe_json, visualize=True)

            except Exception as e:
                print(f"Error: {e}")

        elif choice == "3":
            # Interactive mode
            tester.interactive_test()

        elif choice == "4":
            print("\nExiting...")
            break

        else:
            print("Invalid option. Please select 1-4.")
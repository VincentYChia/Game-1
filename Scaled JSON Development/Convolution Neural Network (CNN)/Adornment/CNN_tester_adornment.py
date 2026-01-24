import numpy as np
import tensorflow as tf
from tensorflow import keras
import json
from pathlib import Path
import matplotlib.pyplot as plt
from matplotlib.patches import Circle
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

    def batch_predict(self, recipes_json_path, output_path=None, visualize_failures=False):
        """
        Predict on multiple recipes from JSON file

        Args:
            recipes_json_path: Path to JSON file with recipes
            output_path: Optional path to save results
            visualize_failures: Show images of failed predictions
        """
        with open(recipes_json_path, 'r') as f:
            data = json.load(f)

        recipes = data['placements']
        results = []

        print("\n" + "=" * 60)
        print(f"BATCH PREDICTION ON {len(recipes)} RECIPES")
        print("=" * 60 + "\n")

        for recipe in recipes:
            recipe_id = recipe['recipeId']
            vertices = recipe['placementMap']['vertices']
            shapes = recipe['placementMap']['shapes']

            result = self.predict_recipe(vertices, shapes)
            result['recipeId'] = recipe_id
            results.append(result)

            status = "✓" if result['is_valid'] else "✗"
            print(f"{status} {recipe_id:40s} | {result['label']:7s} (p={result['probability']:.4f})")

            # Visualize failures if requested
            if visualize_failures and not result['is_valid']:
                img = self.render_recipe(vertices, shapes)
                self._visualize_prediction(img, result)

        # Summary statistics
        valid_count = sum(1 for r in results if r['is_valid'])
        invalid_count = len(results) - valid_count
        avg_confidence = np.mean([r['confidence'] for r in results])

        print("\n" + "=" * 60)
        print("SUMMARY")
        print("=" * 60)
        print(f"Total recipes: {len(results)}")
        print(f"Predicted VALID: {valid_count} ({valid_count / len(results) * 100:.1f}%)")
        print(f"Predicted INVALID: {invalid_count} ({invalid_count / len(results) * 100:.1f}%)")
        print(f"Average confidence: {avg_confidence:.4f}")
        print("=" * 60 + "\n")

        # Save results if requested
        if output_path:
            with open(output_path, 'w') as f:
                json.dump(results, f, indent=2)
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
    # Initialize tester
    tester = AdornmentCNNTester(
        model_path="models/adornment_cnn_XXXXXX_best.keras",  # Update with your model
        materials_path="../../../Game-1-modular/items.JSON/items-materials-1.JSON"
    )

    # Test on full dataset
    results = tester.batch_predict(
        recipes_json_path="../../../Game-1-modular/placements.JSON/placements-adornments-1.JSON",
        output_path="predictions.json",
        visualize_failures=False
    )

    # Or test single recipe
    example_recipe = {
        "recipeId": "test_pattern",
        "placementMap": {
            "vertices": {
                "0,0": {"materialId": "iron_ingot", "isKey": False},
                "3,0": {"materialId": "copper_ingot", "isKey": False},
                "0,3": {"materialId": "iron_ingot", "isKey": False}
            },
            "shapes": [
                {
                    "type": "triangle",
                    "vertices": ["0,0", "3,0", "0,3"],
                    "rotation": 0
                }
            ]
        }
    }

    result = tester.predict_from_json(example_recipe, visualize=True)

    # Or run interactive mode
    # tester.interactive_test()
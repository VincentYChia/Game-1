"""
Refining Recipe Validator
Tests original recipes against trained model
"""

import json
import numpy as np
import lightgbm as lgb
import pickle
import os
from typing import Dict, List, Tuple
from collections import Counter


class RecipeFeatureExtractor:
    """Extract features from refining recipes."""

    def __init__(self, all_materials: Dict[str, Dict]):
        self.all_materials = all_materials
        self.category_to_idx = {}
        self.tag_to_idx = {}

        self._build_vocabularies()

    def _build_vocabularies(self):
        """Build category and tag vocabularies."""
        categories = set()
        tags = set()

        for mat in self.all_materials.values():
            categories.add(mat.get('category', 'unknown'))
            mat_tags = mat.get('metadata', {}).get('tags', [])
            for tag in mat_tags:
                tags.add(tag)

        self.category_to_idx = {cat: idx for idx, cat in enumerate(sorted(categories))}
        self.tag_to_idx = {tag: idx for idx, tag in enumerate(sorted(tags))}

        print(f"   Built vocabularies: {len(self.category_to_idx)} categories, {len(self.tag_to_idx)} tags")

    def extract_features(self, recipe: Dict) -> np.ndarray:
        """Extract feature vector from recipe."""
        features = []

        # Basic structure features
        num_cores = len(recipe.get('coreInputs', []))
        num_spokes = len(recipe.get('surroundingInputs', []))
        features.extend([num_cores, num_spokes])

        # Quantity features
        core_qty = sum(c.get('quantity', 0) for c in recipe.get('coreInputs', []))
        spoke_qty = sum(s.get('quantity', 0) for s in recipe.get('surroundingInputs', []))
        features.extend([core_qty, spoke_qty])

        # Ratio features
        spoke_to_core_ratio = num_spokes / max(1, num_cores)
        spoke_qty_to_core_qty = spoke_qty / max(1, core_qty)
        features.extend([spoke_to_core_ratio, spoke_qty_to_core_qty])

        # Material diversity
        all_mats = [c['materialId'] for c in recipe.get('coreInputs', [])]
        all_mats.extend([s['materialId'] for s in recipe.get('surroundingInputs', [])])
        unique_materials = len(set(all_mats))
        features.append(unique_materials)

        # Category distribution (cores)
        core_categories = [
            self.all_materials.get(c['materialId'], {}).get('category', 'unknown')
            for c in recipe.get('coreInputs', [])
        ]
        category_counts = Counter(core_categories)
        for cat in sorted(self.category_to_idx.keys()):
            features.append(category_counts.get(cat, 0))

        # Tier statistics
        core_tiers = [
            self.all_materials.get(c['materialId'], {}).get('tier', 1)
            for c in recipe.get('coreInputs', [])
        ]
        spoke_tiers = [
            self.all_materials.get(s['materialId'], {}).get('tier', 1)
            for s in recipe.get('surroundingInputs', [])
        ]

        features.append(np.mean(core_tiers) if core_tiers else 0)
        features.append(np.max(core_tiers) if core_tiers else 0)
        features.append(np.mean(spoke_tiers) if spoke_tiers else 0)
        features.append(np.max(spoke_tiers) if spoke_tiers else 0)

        # Tier mismatch
        if core_tiers and spoke_tiers:
            tier_mismatch = abs(np.mean(core_tiers) - np.mean(spoke_tiers))
        else:
            tier_mismatch = 0
        features.append(tier_mismatch)

        # Station tier
        features.append(recipe.get('stationTier', 1))

        return np.array(features)


def load_model(model_dir: str):
    """Load trained model and feature extractor."""
    model_path = os.path.join(model_dir, 'refining_model.txt')
    extractor_path = os.path.join(model_dir, 'refining_extractor.pkl')

    if not os.path.exists(model_path):
        raise FileNotFoundError(f"Model not found: {model_path}")
    if not os.path.exists(extractor_path):
        raise FileNotFoundError(f"Feature extractor not found: {extractor_path}")

    print(f"   Loading model from: {model_path}")
    model = lgb.Booster(model_file=model_path)

    with open(extractor_path, 'rb') as f:
        feature_extractor = pickle.load(f)

    return model, feature_extractor


def load_placements(filepath: str):
    """Load original placement recipes."""
    with open(filepath, 'r') as f:
        data = json.load(f)
    return data['placements']


def predict_recipe(recipe: Dict, model, feature_extractor) -> Tuple[int, float]:
    """Predict if recipe is valid."""
    features = feature_extractor.extract_features(recipe)
    features = features.reshape(1, -1)

    prob = model.predict(features, num_iteration=model.best_iteration)[0]
    prediction = 1 if prob > 0.5 else 0

    return prediction, prob


def format_recipe_summary(recipe: Dict) -> str:
    """Create brief recipe summary."""
    recipe_id = recipe.get('recipeId', 'unknown')
    output_id = recipe.get('outputId', 'unknown')
    num_cores = len(recipe.get('coreInputs', []))
    num_spokes = len(recipe.get('surroundingInputs', []))

    return f"{recipe_id} → {output_id} ({num_cores} cores, {num_spokes} spokes)"


def print_results(results: List[Tuple[Dict, int, float]]):
    """Print validation results."""
    print("\n" + "=" * 80)
    print("VALIDATION RESULTS")
    print("=" * 80)

    valid_count = sum(1 for _, pred, _ in results if pred == 1)
    invalid_count = len(results) - valid_count

    print(f"\nSummary:")
    print(f"  Total recipes tested: {len(results)}")
    print(f"  Predicted VALID:   {valid_count} ({valid_count / len(results) * 100:.1f}%)")
    print(f"  Predicted INVALID: {invalid_count} ({invalid_count / len(results) * 100:.1f}%)")

    print(f"\n{'Recipe':<60} {'Prediction':<12} {'Confidence':<10}")
    print("-" * 80)

    for recipe, prediction, probability in results:
        summary = format_recipe_summary(recipe)
        status = "✅ VALID" if prediction == 1 else "❌ INVALID"
        confidence = f"{probability:.4f}"

        if len(summary) > 58:
            summary = summary[:55] + "..."

        print(f"{summary:<60} {status:<12} {confidence:<10}")

    print("=" * 80)


def save_results(results: List[Tuple[Dict, int, float]], output_path: str):
    """Save results to JSON."""
    output_data = {
        'total_recipes': len(results),
        'valid_count': sum(1 for _, pred, _ in results if pred == 1),
        'invalid_count': sum(1 for _, pred, _ in results if pred == 0),
        'results': [
            {
                'recipeId': recipe.get('recipeId', 'unknown'),
                'outputId': recipe.get('outputId', 'unknown'),
                'prediction': 'valid' if pred == 1 else 'invalid',
                'confidence': float(prob),
                'recipe': recipe
            }
            for recipe, pred, prob in results
        ]
    }

    with open(output_path, 'w') as f:
        json.dump(output_data, f, indent=2)

    print(f"\n💾 Results saved to: {output_path}")


def main():
    print("=" * 70)
    print("REFINING RECIPE VALIDATOR")
    print("=" * 70)

    # Get inputs
    model_dir = input("Enter path to model directory: ").strip()
    placements_path = input("Enter path to original placements JSON: ").strip()

    save_output = input("Save results to JSON? (y/n): ").strip().lower()
    if save_output == 'y':
        output_path = input("Enter output path for results: ").strip()
    else:
        output_path = None

    # Load model
    print("\n📦 Loading model...")
    try:
        model, feature_extractor = load_model(model_dir)
        print("   ✅ Model loaded successfully")
    except Exception as e:
        print(f"   ❌ Error loading model: {e}")
        return

    # Load placements
    print("\n📂 Loading original recipes...")
    try:
        recipes = load_placements(placements_path)
        print(f"   Loaded {len(recipes)} recipes")
    except Exception as e:
        print(f"   ❌ Error loading placements: {e}")
        return

    # Validate each recipe
    print(f"\n🔍 Validating {len(recipes)} recipes...")
    results = []

    for i, recipe in enumerate(recipes, 1):
        try:
            prediction, probability = predict_recipe(recipe, model, feature_extractor)
            results.append((recipe, prediction, probability))

            if i % 10 == 0:
                print(f"   Processed {i}/{len(recipes)} recipes...")
        except Exception as e:
            print(f"   ⚠️  Error processing {recipe.get('recipeId', 'unknown')}: {e}")
            results.append((recipe, 0, 0.0))

    # Print results
    print_results(results)

    # Save if requested
    if output_path:
        save_results(results, output_path)

    print("\n✨ Validation complete!")


if __name__ == "__main__":
    main()
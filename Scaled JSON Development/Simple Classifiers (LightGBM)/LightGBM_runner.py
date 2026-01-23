"""
Recipe Validation Tester
Tests placement JSON files against trained LightGBM models.
"""

import json
import numpy as np
import lightgbm as lgb
import pickle
import os
from typing import Dict, List, Tuple
from collections import Counter


# ============================================================================
# FEATURE EXTRACTOR (Must match training script exactly!)
# ============================================================================

class RecipeFeatureExtractor:
    """Extract features from recipes for LightGBM."""

    def __init__(self, all_materials: Dict[str, Dict]):
        self.all_materials = all_materials
        self.material_to_idx = {mat_id: idx for idx, mat_id in enumerate(all_materials.keys())}
        self.category_to_idx = {}
        self.refinement_to_idx = {}
        self.tag_to_idx = {}

        # Build vocabulary
        self._build_vocabularies()

    def _build_vocabularies(self):
        """Build index mappings for categories, refinement levels, tags."""
        categories = set()
        refinements = set()
        tags = set()

        for mat in self.all_materials.values():
            categories.add(mat.get('category', 'unknown'))

            # Handle refinement_level - might be in metadata.tags
            refinement = mat.get('refinement_level')
            if refinement:
                refinements.add(refinement)
            else:
                # Try to infer from tags
                mat_tags = mat.get('metadata', {}).get('tags', [])
                for tag in mat_tags:
                    if tag in ['basic', 'refined', 'raw', 'processed']:
                        refinements.add(tag)

            # Get tags from metadata
            for tag in mat.get('metadata', {}).get('tags', []):
                tags.add(tag)

        if not refinements:
            refinements.add('basic')

        self.category_to_idx = {cat: idx for idx, cat in enumerate(sorted(categories))}
        self.refinement_to_idx = {ref: idx for idx, ref in enumerate(sorted(refinements))}
        self.tag_to_idx = {tag: idx for idx, tag in enumerate(sorted(tags))}

    def _get_refinement_level(self, material: Dict) -> str:
        """Get refinement level from material (handle different formats)."""
        # Direct field
        if 'refinement_level' in material:
            return material['refinement_level']

        # From tags
        tags = material.get('metadata', {}).get('tags', [])
        for tag in tags:
            if tag in ['basic', 'refined', 'raw', 'processed']:
                return tag

        return 'basic'

    def extract_refining_features(self, recipe: Dict) -> np.ndarray:
        """Extract features from refining recipe (hub-and-spoke)."""
        features = []

        # Basic counts
        num_cores = len(recipe.get('coreInputs', []))
        num_spokes = len(recipe.get('surroundingInputs', []))
        features.extend([num_cores, num_spokes])

        # Total quantities
        core_qty = sum(c.get('quantity', 0) for c in recipe.get('coreInputs', []))
        spoke_qty = sum(s.get('quantity', 0) for s in recipe.get('surroundingInputs', []))
        features.extend([core_qty, spoke_qty])

        # Ratio features
        features.append(num_spokes / max(1, num_cores))
        features.append(spoke_qty / max(1, core_qty))

        # Material diversity features
        all_materials_used = [c['materialId'] for c in recipe.get('coreInputs', [])]
        all_materials_used.extend([s['materialId'] for s in recipe.get('surroundingInputs', [])])
        features.append(len(set(all_materials_used)))  # Unique materials

        # Category distribution (cores)
        core_categories = [self.all_materials.get(c['materialId'], {}).get('category', 'unknown')
                           for c in recipe.get('coreInputs', [])]
        category_counts = Counter(core_categories)
        for cat_idx in range(len(self.category_to_idx)):
            cat_name = list(self.category_to_idx.keys())[cat_idx]
            features.append(category_counts.get(cat_name, 0))

        # Refinement level distribution (cores)
        core_refinements = [self._get_refinement_level(self.all_materials.get(c['materialId'], {}))
                            for c in recipe.get('coreInputs', [])]
        refinement_counts = Counter(core_refinements)
        for ref_idx in range(len(self.refinement_to_idx)):
            ref_name = list(self.refinement_to_idx.keys())[ref_idx]
            features.append(refinement_counts.get(ref_name, 0))

        # Tier statistics
        core_tiers = [self.all_materials.get(c['materialId'], {}).get('tier', 1)
                      for c in recipe.get('coreInputs', [])]
        spoke_tiers = [self.all_materials.get(s['materialId'], {}).get('tier', 1)
                       for s in recipe.get('surroundingInputs', [])]

        features.append(np.mean(core_tiers) if core_tiers else 0)
        features.append(np.max(core_tiers) if core_tiers else 0)
        features.append(np.mean(spoke_tiers) if spoke_tiers else 0)
        features.append(np.max(spoke_tiers) if spoke_tiers else 0)

        # Tier mismatch (cores vs spokes)
        if core_tiers and spoke_tiers:
            features.append(abs(np.mean(core_tiers) - np.mean(spoke_tiers)))
        else:
            features.append(0)

        # Station tier
        features.append(recipe.get('stationTier', 1))

        return np.array(features)

    def extract_alchemy_features(self, recipe: Dict) -> np.ndarray:
        """Extract features from alchemy recipe (sequential)."""
        features = []

        ingredients = recipe.get('ingredients', [])

        # Basic counts
        num_ingredients = len(ingredients)
        features.append(num_ingredients)

        # Total quantity
        total_qty = sum(ing.get('quantity', 0) for ing in ingredients)
        features.append(total_qty)

        # Average quantity
        features.append(total_qty / max(1, num_ingredients))

        # Position-based features (first 3 positions matter most)
        for pos in range(6):  # Fixed size for first 6 positions
            if pos < len(ingredients):
                ing = ingredients[pos]
                mat_id = ing['materialId']
                mat = self.all_materials.get(mat_id, {})

                # Material tier at this position
                features.append(mat.get('tier', 1))

                # Quantity at this position
                features.append(ing.get('quantity', 0))

                # Category at this position (one-hot-ish)
                cat = mat.get('category', 'unknown')
                cat_idx = self.category_to_idx.get(cat, 0)
                features.append(cat_idx)
            else:
                # Padding
                features.extend([0, 0, 0])

        # Material diversity
        unique_materials = len(set(ing['materialId'] for ing in ingredients))
        features.append(unique_materials)

        # Category distribution
        categories = [self.all_materials.get(ing['materialId'], {}).get('category', 'unknown')
                      for ing in ingredients]
        category_counts = Counter(categories)
        for cat_idx in range(len(self.category_to_idx)):
            cat_name = list(self.category_to_idx.keys())[cat_idx]
            features.append(category_counts.get(cat_name, 0))

        # Refinement distribution
        refinements = [self._get_refinement_level(self.all_materials.get(ing['materialId'], {}))
                       for ing in ingredients]
        refinement_counts = Counter(refinements)
        for ref_idx in range(len(self.refinement_to_idx)):
            ref_name = list(self.refinement_to_idx.keys())[ref_idx]
            features.append(refinement_counts.get(ref_name, 0))

        # Tier statistics
        tiers = [self.all_materials.get(ing['materialId'], {}).get('tier', 1)
                 for ing in ingredients]
        features.append(np.mean(tiers) if tiers else 0)
        features.append(np.max(tiers) if tiers else 0)
        features.append(np.std(tiers) if len(tiers) > 1 else 0)

        # Sequential patterns (tier progression)
        if len(tiers) >= 2:
            tier_increases = sum(1 for i in range(len(tiers) - 1) if tiers[i + 1] > tiers[i])
            tier_decreases = sum(1 for i in range(len(tiers) - 1) if tiers[i + 1] < tiers[i])
            features.extend([tier_increases, tier_decreases])
        else:
            features.extend([0, 0])

        # Station tier
        features.append(recipe.get('stationTier', 1))

        return np.array(features)

    def extract_engineering_features(self, recipe: Dict) -> np.ndarray:
        """Extract features from engineering recipe (slot-based)."""
        features = []

        slots = recipe.get('slots', [])

        # Basic counts
        num_slots = len(slots)
        features.append(num_slots)

        # Total quantity
        total_qty = sum(slot.get('quantity', 0) for slot in slots)
        features.append(total_qty)

        # Slot type distribution
        slot_types = [slot.get('type', 'unknown') for slot in slots]
        slot_type_counts = Counter(slot_types)

        # Count each standard slot type
        for slot_type in ['FRAME', 'FUNCTION', 'POWER', 'MODIFIER', 'UTILITY', 'ENHANCEMENT', 'CORE', 'CATALYST']:
            features.append(slot_type_counts.get(slot_type, 0))

        # Diversity: unique slot types
        features.append(len(set(slot_types)))

        # Critical slots present (binary)
        features.append(1 if 'FRAME' in slot_types else 0)
        features.append(1 if 'FUNCTION' in slot_types else 0)
        features.append(1 if 'POWER' in slot_types else 0)

        # Material diversity
        unique_materials = len(set(slot['materialId'] for slot in slots))
        features.append(unique_materials)

        # Category distribution
        categories = [self.all_materials.get(slot['materialId'], {}).get('category', 'unknown')
                      for slot in slots]
        category_counts = Counter(categories)
        for cat_idx in range(len(self.category_to_idx)):
            cat_name = list(self.category_to_idx.keys())[cat_idx]
            features.append(category_counts.get(cat_name, 0))

        # Refinement distribution
        refinements = [self._get_refinement_level(self.all_materials.get(slot['materialId'], {}))
                       for slot in slots]
        refinement_counts = Counter(refinements)
        for ref_idx in range(len(self.refinement_to_idx)):
            ref_name = list(self.refinement_to_idx.keys())[ref_idx]
            features.append(refinement_counts.get(ref_name, 0))

        # Tier statistics
        tiers = [self.all_materials.get(slot['materialId'], {}).get('tier', 1)
                 for slot in slots]
        features.append(np.mean(tiers) if tiers else 0)
        features.append(np.max(tiers) if tiers else 0)
        features.append(np.std(tiers) if len(tiers) > 1 else 0)

        # Quantity statistics per slot type
        frame_qty = sum(s.get('quantity', 0) for s in slots if s.get('type') == 'FRAME')
        power_qty = sum(s.get('quantity', 0) for s in slots if s.get('type') == 'POWER')
        function_qty = sum(s.get('quantity', 0) for s in slots if s.get('type') == 'FUNCTION')
        features.extend([frame_qty, power_qty, function_qty])

        # Station tier
        features.append(recipe.get('stationTier', 1))

        return np.array(features)


# ============================================================================
# LOAD MODEL AND FEATURE EXTRACTOR
# ============================================================================

def load_model_and_extractor(model_dir: str, discipline: str):
    """Load trained model and feature extractor for a discipline."""
    model_path = os.path.join(model_dir, f'{discipline}_model.txt')
    extractor_path = os.path.join(model_dir, f'{discipline}_extractor.pkl')

    if not os.path.exists(model_path):
        raise FileNotFoundError(f"Model file not found: {model_path}")
    if not os.path.exists(extractor_path):
        raise FileNotFoundError(f"Feature extractor not found: {extractor_path}")

    print(f"📦 Loading {discipline} model from: {model_path}")
    model = lgb.Booster(model_file=model_path)

    with open(extractor_path, 'rb') as f:
        feature_extractor = pickle.load(f)

    print(f"✅ Model and feature extractor loaded successfully")

    return model, feature_extractor


# ============================================================================
# LOAD PLACEMENTS
# ============================================================================

def load_placements(filepath: str) -> Tuple[List[Dict], str]:
    """Load placement JSON file."""
    with open(filepath, 'r') as f:
        data = json.load(f)

    placements = data.get('placements', [])
    discipline = data.get('metadata', {}).get('discipline', 'unknown')

    return placements, discipline


# ============================================================================
# PREDICT
# ============================================================================

def predict_recipe(recipe: Dict, model, feature_extractor, discipline: str) -> Tuple[int, float]:
    """
    Predict if a recipe is valid.

    Returns:
        prediction (int): 1 for valid, 0 for invalid
        probability (float): confidence score (0-1)
    """
    # Extract features based on discipline
    if discipline == 'refining':
        features = feature_extractor.extract_refining_features(recipe)
    elif discipline == 'alchemy':
        features = feature_extractor.extract_alchemy_features(recipe)
    elif discipline == 'engineering':
        features = feature_extractor.extract_engineering_features(recipe)
    else:
        raise ValueError(f"Unknown discipline: {discipline}")

    # Predict
    features = features.reshape(1, -1)
    prob = model.predict(features, num_iteration=model.best_iteration)[0]
    prediction = 1 if prob > 0.5 else 0

    return prediction, prob


# ============================================================================
# OUTPUT RESULTS
# ============================================================================

def format_recipe_summary(recipe: Dict, discipline: str) -> str:
    """Create a brief summary of the recipe."""
    recipe_id = recipe.get('recipeId', 'unknown')
    output_id = recipe.get('outputId', 'unknown')

    if discipline == 'refining':
        num_cores = len(recipe.get('coreInputs', []))
        num_spokes = len(recipe.get('surroundingInputs', []))
        return f"{recipe_id} → {output_id} ({num_cores} cores, {num_spokes} spokes)"

    elif discipline == 'alchemy':
        num_ingredients = len(recipe.get('ingredients', []))
        return f"{recipe_id} → {output_id} ({num_ingredients} ingredients)"

    elif discipline == 'engineering':
        num_slots = len(recipe.get('slots', []))
        slot_types = [s.get('type', '?') for s in recipe.get('slots', [])]
        slot_summary = ', '.join(set(slot_types))
        return f"{recipe_id} → {output_id} ({num_slots} slots: {slot_summary})"

    return f"{recipe_id} → {output_id}"


def print_results(results: List[Tuple[Dict, int, float]], discipline: str):
    """Print validation results in a nice format."""
    print("\n" + "=" * 80)
    print(f"VALIDATION RESULTS - {discipline.upper()}")
    print("=" * 80)

    valid_count = sum(1 for _, pred, _ in results if pred == 1)
    invalid_count = len(results) - valid_count

    print(f"\nSummary:")
    print(f"  Total recipes: {len(results)}")
    print(f"  Valid:   {valid_count} ({valid_count / len(results) * 100:.1f}%)")
    print(f"  Invalid: {invalid_count} ({invalid_count / len(results) * 100:.1f}%)")

    print(f"\n{'Recipe':<60} {'Status':<10} {'Confidence':<10}")
    print("-" * 80)

    for recipe, prediction, probability in results:
        summary = format_recipe_summary(recipe, discipline)
        status = "✅ VALID" if prediction == 1 else "❌ INVALID"
        confidence = f"{probability:.4f}"

        # Truncate summary if too long
        if len(summary) > 58:
            summary = summary[:55] + "..."

        print(f"{summary:<60} {status:<10} {confidence:<10}")

    print("=" * 80)


def save_results_json(results: List[Tuple[Dict, int, float]], output_path: str, discipline: str):
    """Save results to JSON file."""
    output_data = {
        'discipline': discipline,
        'total_recipes': len(results),
        'valid_count': sum(1 for _, pred, _ in results if pred == 1),
        'invalid_count': sum(1 for _, pred, _ in results if pred == 0),
        'results': [
            {
                'recipeId': recipe.get('recipeId', 'unknown'),
                'outputId': recipe.get('outputId', 'unknown'),
                'prediction': 'valid' if pred == 1 else 'invalid',
                'probability': float(prob),
                'recipe': recipe
            }
            for recipe, pred, prob in results
        ]
    }

    with open(output_path, 'w') as f:
        json.dump(output_data, f, indent=2)

    print(f"\n💾 Results saved to: {output_path}")


# ============================================================================
# MAIN
# ============================================================================

def main():
    print("="*80)
    print("RECIPE VALIDATION TESTER")
    print("="*80)

    # Get input paths - NOW INCLUDING MATERIALS!
    model_dir = input("\nEnter path to model directory: ").strip()
    materials_path = input("Enter path to materials JSON file: ").strip()  # ← ADD THIS LINE
    placements_path = input("Enter path to placements JSON file: ").strip()

    # Optional: save results
    save_results = input("Save results to JSON? (y/n): ").strip().lower()
    if save_results == 'y':
        output_path = input("Enter output path for results JSON: ").strip()
    else:
        output_path = None

    # Load placements
    print("\n📂 Loading placements...")
    try:
        placements, discipline = load_placements(placements_path)
        print(f"   Found {len(placements)} recipes")
        print(f"   Discipline: {discipline}")
    except Exception as e:
        print(f"❌ Error loading placements: {e}")
        return

    # Load model
    print(f"\n🤖 Loading {discipline} model...")
    try:
        model, feature_extractor = load_model_and_extractor(model_dir, discipline)
    except Exception as e:
        print(f"❌ Error loading model: {e}")
        return

    # Validate each recipe
    print(f"\n🔍 Validating {len(placements)} recipes...")
    results = []

    for i, recipe in enumerate(placements, 1):
        try:
            prediction, probability = predict_recipe(recipe, model, feature_extractor, discipline)
            results.append((recipe, prediction, probability))

            # Progress indicator
            if i % 10 == 0:
                print(f"   Processed {i}/{len(placements)} recipes...")
        except Exception as e:
            print(f"⚠️  Error processing recipe {recipe.get('recipeId', 'unknown')}: {e}")
            results.append((recipe, 0, 0.0))  # Mark as invalid if error

    # Print results
    print_results(results, discipline)

    # Save if requested
    if output_path:
        save_results_json(results, output_path, discipline)

    print("\n✨ Validation complete!")


if __name__ == "__main__":
    main()
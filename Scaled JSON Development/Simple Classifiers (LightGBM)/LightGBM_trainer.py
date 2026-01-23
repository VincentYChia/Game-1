"""
LightGBM Recipe Classifier - Train and Test
Trains classifiers for crafting recipe validation across three disciplines.
"""

import json
import numpy as np
import lightgbm as lgb
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score, classification_report, \
    confusion_matrix
from collections import Counter, defaultdict
import pickle
from typing import Dict, List, Tuple, Any
import os


# ============================================================================
# FEATURE ENGINEERING
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
            refinements.add(mat.get('refinement_level', 'basic'))
            for tag in mat.get('tags', []):
                tags.add(tag)

        self.category_to_idx = {cat: idx for idx, cat in enumerate(sorted(categories))}
        self.refinement_to_idx = {ref: idx for idx, ref in enumerate(sorted(refinements))}
        self.tag_to_idx = {tag: idx for idx, tag in enumerate(sorted(tags))}

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
        core_refinements = [self.all_materials.get(c['materialId'], {}).get('refinement_level', 'basic')
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
        refinements = [self.all_materials.get(ing['materialId'], {}).get('refinement_level', 'basic')
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
        refinements = [self.all_materials.get(slot['materialId'], {}).get('refinement_level', 'basic')
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
# TRAINING AND TESTING
# ============================================================================

def load_dataset(filepath: str) -> Tuple[List[Dict], List[int], str]:
    """Load augmented dataset."""
    with open(filepath, 'r') as f:
        data = json.load(f)

    recipes = [item['recipe'] for item in data['data']]
    labels = [item['label'] for item in data['data']]
    discipline = data['discipline']

    return recipes, labels, discipline


def train_lightgbm_classifier(X_train, y_train, X_test, y_test):
    """Train LightGBM classifier."""
    print("\n🎓 Training LightGBM classifier...")

    # Create datasets
    train_data = lgb.Dataset(X_train, label=y_train)
    test_data = lgb.Dataset(X_test, label=y_test, reference=train_data)

    # Parameters
    params = {
        'objective': 'binary',
        'metric': 'binary_logloss',
        'boosting_type': 'gbdt',
        'num_leaves': 31,
        'learning_rate': 0.05,
        'feature_fraction': 0.9,
        'bagging_fraction': 0.8,
        'bagging_freq': 5,
        'verbose': -1
    }

    # Train
    model = lgb.train(
        params,
        train_data,
        num_boost_round=200,
        valid_sets=[test_data],
        callbacks=[lgb.early_stopping(stopping_rounds=20), lgb.log_evaluation(period=0)]
    )

    return model


def evaluate_model(model, X_test, y_test):
    """Evaluate model performance."""
    print("\n📊 Evaluating model...")

    # Predictions
    y_pred_proba = model.predict(X_test, num_iteration=model.best_iteration)
    y_pred = (y_pred_proba > 0.5).astype(int)

    # Metrics
    accuracy = accuracy_score(y_test, y_pred)
    precision = precision_score(y_test, y_pred)
    recall = recall_score(y_test, y_pred)
    f1 = f1_score(y_test, y_pred)

    print(f"\n{'=' * 50}")
    print(f"PERFORMANCE METRICS")
    print(f"{'=' * 50}")
    print(f"Accuracy:  {accuracy:.4f}")
    print(f"Precision: {precision:.4f}")
    print(f"Recall:    {recall:.4f}")
    print(f"F1 Score:  {f1:.4f}")
    print(f"{'=' * 50}")

    # Confusion matrix
    cm = confusion_matrix(y_test, y_pred)
    print(f"\nConfusion Matrix:")
    print(f"                 Predicted")
    print(f"                 0      1")
    print(f"Actual  0     {cm[0][0]:5d}  {cm[0][1]:5d}")
    print(f"        1     {cm[1][0]:5d}  {cm[1][1]:5d}")

    # Classification report
    print(f"\nDetailed Classification Report:")
    print(classification_report(y_test, y_pred, target_names=['Invalid', 'Valid']))

    return accuracy, precision, recall, f1


def save_model(model, feature_extractor, discipline, output_dir):
    """Save trained model and feature extractor."""
    os.makedirs(output_dir, exist_ok=True)

    model_path = os.path.join(output_dir, f'{discipline}_model.txt')
    extractor_path = os.path.join(output_dir, f'{discipline}_extractor.pkl')

    # Save LightGBM model
    model.save_model(model_path)

    # Save feature extractor
    with open(extractor_path, 'wb') as f:
        pickle.dump(feature_extractor, f)

    print(f"\n✅ Model saved to: {model_path}")
    print(f"✅ Feature extractor saved to: {extractor_path}")


def load_model(discipline, model_dir):
    """Load trained model and feature extractor."""
    model_path = os.path.join(model_dir, f'{discipline}_model.txt')
    extractor_path = os.path.join(model_dir, f'{discipline}_extractor.pkl')

    model = lgb.Booster(model_file=model_path)

    with open(extractor_path, 'rb') as f:
        feature_extractor = pickle.load(f)

    return model, feature_extractor


def test_single_recipe(recipe: Dict, model, feature_extractor, discipline: str):
    """Test a single recipe."""
    # Extract features
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
# MAIN
# ============================================================================

def main():
    print("=" * 70)
    print("LIGHTGBM RECIPE CLASSIFIER - TRAIN & TEST")
    print("=" * 70)

    print("\nOptions:")
    print("  1. Train new model")
    print("  2. Test existing model")

    choice = input("\nEnter choice (1 or 2): ").strip()

    if choice == '1':
        # TRAINING MODE
        dataset_path = input("Enter path to augmented dataset JSON: ").strip()
        materials_path = input("Enter path to materials JSON: ").strip()
        model_output_dir = input("Enter directory to save model: ").strip()

        # Load data
        print("\n📂 Loading data...")
        recipes, labels, discipline = load_dataset(dataset_path)

        with open(materials_path, 'r') as f:
            materials_data = json.load(f)
        all_materials = {m['materialId']: m for m in materials_data['materials']}

        print(f"   Discipline: {discipline}")
        print(f"   Total recipes: {len(recipes)}")
        print(f"   Valid recipes: {sum(labels)}")
        print(f"   Invalid recipes: {len(labels) - sum(labels)}")
        print(f"   Materials: {len(all_materials)}")

        # Create feature extractor
        print("\n🔧 Building feature extractor...")
        feature_extractor = RecipeFeatureExtractor(all_materials)

        # Extract features
        print(f"🔧 Extracting features for {discipline}...")
        X = []
        for recipe in recipes:
            if discipline == 'refining':
                features = feature_extractor.extract_refining_features(recipe)
            elif discipline == 'alchemy':
                features = feature_extractor.extract_alchemy_features(recipe)
            elif discipline == 'engineering':
                features = feature_extractor.extract_engineering_features(recipe)
            X.append(features)

        X = np.array(X)
        y = np.array(labels)

        print(f"   Feature dimension: {X.shape[1]}")

        # Split data
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42, stratify=y
        )

        print(f"   Training set: {len(X_train)} samples")
        print(f"   Test set: {len(X_test)} samples")

        # Train model
        model = train_lightgbm_classifier(X_train, y_train, X_test, y_test)

        # Evaluate
        evaluate_model(model, X_test, y_test)

        # Save model
        save_model(model, feature_extractor, discipline, model_output_dir)

        print("\n✨ Training complete!")

    elif choice == '2':
        # TESTING MODE
        print("\nTesting mode coming soon! For now, please train a model first.")
        print("You can test recipes by loading the model in your own code.")

    else:
        print("❌ Invalid choice. Please enter 1 or 2.")


if __name__ == "__main__":
    main()
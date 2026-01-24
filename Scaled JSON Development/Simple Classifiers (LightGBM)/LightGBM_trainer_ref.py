"""
Refining Recipe Classifier - Training Script
Trains LightGBM model for recipe validation
"""

import json
import numpy as np
import lightgbm as lgb
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score, confusion_matrix
import pickle
import os
from typing import Dict, List
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


def load_dataset(filepath: str):
    """Load augmented dataset."""
    with open(filepath, 'r') as f:
        data = json.load(f)

    recipes = [item['recipe'] for item in data['data']]
    labels = [item['label'] for item in data['data']]

    return recipes, labels


def load_materials(filepath: str):
    """Load materials."""
    with open(filepath, 'r') as f:
        data = json.load(f)
    return {m['materialId']: m for m in data['materials']}


def train_model(X_train, y_train, X_test, y_test):
    """Train LightGBM classifier."""
    print("\n🎓 Training LightGBM model...")

    train_data = lgb.Dataset(X_train, label=y_train)
    test_data = lgb.Dataset(X_test, label=y_test, reference=train_data)

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

    y_pred_proba = model.predict(X_test, num_iteration=model.best_iteration)
    y_pred = (y_pred_proba > 0.5).astype(int)

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

    cm = confusion_matrix(y_test, y_pred)
    print(f"\nConfusion Matrix:")
    print(f"                 Predicted")
    print(f"                 Invalid  Valid")
    print(f"Actual  Invalid  {cm[0][0]:6d}  {cm[0][1]:6d}")
    print(f"        Valid    {cm[1][0]:6d}  {cm[1][1]:6d}")
    print(f"{'=' * 50}")


def save_model(model, feature_extractor, output_dir):
    """Save model and feature extractor."""
    os.makedirs(output_dir, exist_ok=True)

    model_path = os.path.join(output_dir, 'refining_model.txt')
    extractor_path = os.path.join(output_dir, 'refining_extractor.pkl')

    model.save_model(model_path)

    with open(extractor_path, 'wb') as f:
        pickle.dump(feature_extractor, f)

    print(f"\n✅ Model saved to: {model_path}")
    print(f"✅ Feature extractor saved to: {extractor_path}")


def main():
    print("=" * 70)
    print("REFINING RECIPE CLASSIFIER - TRAINING")
    print("=" * 70)

    # Get inputs
    dataset_path = input("Enter path to augmented dataset JSON: ").strip()
    materials_path = input("Enter path to materials JSON: ").strip()
    output_dir = input("Enter output directory for model: ").strip()

    # Load data
    print("\n📂 Loading data...")
    recipes, labels = load_dataset(dataset_path)
    all_materials = load_materials(materials_path)

    print(f"   Total recipes: {len(recipes)}")
    print(f"   Positive samples: {sum(labels)}")
    print(f"   Negative samples: {len(labels) - sum(labels)}")
    print(f"   Materials: {len(all_materials)}")

    # Build feature extractor
    print("\n🔧 Building feature extractor...")
    feature_extractor = RecipeFeatureExtractor(all_materials)

    # Extract features
    print("\n🔧 Extracting features...")
    X = np.array([feature_extractor.extract_features(r) for r in recipes])
    y = np.array(labels)

    print(f"   Feature dimension: {X.shape[1]}")

    # Split data
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )

    print(f"   Training set: {len(X_train)} samples")
    print(f"   Test set: {len(X_test)} samples")

    # Train
    model = train_model(X_train, y_train, X_test, y_test)

    # Evaluate
    evaluate_model(model, X_test, y_test)

    # Save
    save_model(model, feature_extractor, output_dir)

    print("\n✨ Training complete!")


if __name__ == "__main__":
    main()
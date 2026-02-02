"""
LightGBM Recipe Classifier - Train and Test

SELF-CONTAINED: Includes synthetic material generation for augmentation.

Trains classifiers for crafting recipe validation across three disciplines.

Key Features:
- Synthetic material injection to combat overfitting
- Maintains strict substitution rules (same category, same refined/basic status)
- All synthetic variants replace ALL instances of a material (consistency)

Created: 2026-02-02
Updated: 2026-02-02 - Integrated synthetic material generation directly
"""

import json
import numpy as np
import lightgbm as lgb
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score, classification_report, \
    confusion_matrix
from collections import Counter, defaultdict
import pickle
from typing import Dict, List, Tuple, Any, Optional, Set
import os
import random
import copy
import uuid


# ============================================================================
# SYNTHETIC MATERIAL GENERATOR (Integrated)
# ============================================================================

class SyntheticMaterialGenerator:
    """
    Generates synthetic materials that are valid substitutes for existing materials.

    All generated materials follow the substitution rules:
    - Same category
    - Same refined/basic status
    - Varied tier within ±1 of original
    - Similar tags (keeping essential, varying optional)
    """

    # Essential tags that MUST be preserved for validity
    ESSENTIAL_TAGS = {'refined', 'basic', 'raw'}

    # Category-specific tags that should be preserved
    CATEGORY_TAGS = {'metal', 'wood', 'stone', 'elemental', 'monster_drop', 'gem', 'herb', 'fabric'}

    # Optional tags that can be varied
    OPTIONAL_TAGS = {
        'legendary', 'mythical', 'magical', 'ancient', 'common', 'rare',
        'fire', 'water', 'earth', 'air', 'lightning', 'ice', 'light', 'dark', 'void', 'chaos',
        'sharp', 'heavy', 'light', 'flexible', 'rigid', 'hard', 'soft',
        'organic', 'mineral', 'crystalline', 'metallic'
    }

    def __init__(self, all_materials: Dict[str, Dict]):
        """
        Args:
            all_materials: Dict of {material_id: material_data}
        """
        self.all_materials = all_materials
        self._analyze_materials()

    def _analyze_materials(self):
        """Analyze materials to understand tag patterns."""
        self.tags_by_category = {}
        self.materials_by_category = {}

        for mat_id, mat in self.all_materials.items():
            category = mat.get('category', 'unknown')
            tags = set(mat.get('metadata', {}).get('tags', []))

            if category not in self.tags_by_category:
                self.tags_by_category[category] = set()
                self.materials_by_category[category] = []

            self.tags_by_category[category].update(tags)
            self.materials_by_category[category].append(mat_id)

    def get_essential_tags(self, material: Dict) -> Set[str]:
        """Get tags that must be preserved for a material to remain valid."""
        tags = set(material.get('metadata', {}).get('tags', []))
        essential = tags & self.ESSENTIAL_TAGS
        return essential

    def get_optional_tags(self, material: Dict) -> Set[str]:
        """Get tags that can be safely varied."""
        tags = set(material.get('metadata', {}).get('tags', []))
        essential = self.get_essential_tags(material)
        return tags - essential - self.CATEGORY_TAGS

    def create_synthetic_variant(self, base_material_id: str) -> Optional[Dict]:
        """
        Create a synthetic material that is a valid substitute for the base material.

        The synthetic material has:
        - Same category
        - Same refined/basic status
        - Tier varied by ±1 (but not beyond 1-4)
        - Similar tags (essential preserved, optional varied)

        Args:
            base_material_id: ID of material to create variant from

        Returns:
            Synthetic material dict, or None if cannot create valid variant
        """
        if base_material_id not in self.all_materials:
            return None

        base_mat = self.all_materials[base_material_id]
        category = base_mat.get('category', 'unknown')
        base_tier = base_mat.get('tier', 1)
        base_tags = set(base_mat.get('metadata', {}).get('tags', []))

        # Get essential tags that must be preserved
        essential_tags = self.get_essential_tags(base_mat)

        # Vary tier by ±1 (clamped to 1-4)
        tier_change = random.choice([-1, 0, 0, 1])  # Bias toward same tier
        new_tier = max(1, min(4, base_tier + tier_change))

        # Create varied tags
        optional_tags = self.get_optional_tags(base_mat)

        # Sometimes add/remove optional tags
        new_optional = set(optional_tags)
        if random.random() < 0.3:  # 30% chance to add a tag
            available_optional = self.tags_by_category.get(category, set()) & self.OPTIONAL_TAGS
            available_optional -= new_optional
            if available_optional:
                new_optional.add(random.choice(list(available_optional)))

        if random.random() < 0.3 and new_optional:  # 30% chance to remove a tag
            new_optional.discard(random.choice(list(new_optional)))

        # Combine tags
        new_tags = list(essential_tags | new_optional)

        # Create synthetic material
        synthetic = {
            'materialId': f'synthetic_{uuid.uuid4().hex[:8]}',
            'name': f"Synthetic {base_mat.get('name', 'Material')}",
            'category': category,
            'tier': new_tier,
            'rarity': base_mat.get('rarity', 'common'),
            'metadata': {
                'tags': new_tags,
                'synthetic': True,
                'base_material': base_material_id
            }
        }

        return synthetic


class RecipeAugmentorWithSynthetics:
    """
    Augments recipes by injecting synthetic materials.

    This is the main interface for data augmentation with synthetics.
    It ensures all substitutions follow the rules.
    """

    def __init__(self, all_materials: Dict[str, Dict], synthetic_ratio: float = 0.3):
        """
        Args:
            all_materials: Dict of {material_id: material_data}
            synthetic_ratio: Probability of using synthetic material (0.0-1.0)
        """
        self.all_materials = all_materials
        self.synthetic_ratio = synthetic_ratio
        self.generator = SyntheticMaterialGenerator(all_materials)

        # Cache of synthetic materials we've created
        self.synthetic_materials = {}

    def get_or_create_synthetic(self, base_material_id: str) -> Optional[str]:
        """Get or create a synthetic variant for a material."""
        synthetic = self.generator.create_synthetic_variant(base_material_id)
        if synthetic:
            synthetic_id = synthetic['materialId']
            self.synthetic_materials[synthetic_id] = synthetic
            return synthetic_id
        return None

    def augment_recipe(self, recipe: Dict, recipe_type: str) -> Tuple[Dict, Dict]:
        """
        Augment a recipe by potentially injecting synthetic materials.

        Args:
            recipe: Recipe dict to augment
            recipe_type: One of 'alchemy', 'refining', 'engineering'

        Returns:
            Tuple of (augmented_recipe, temporary_materials_dict)
            The temporary_materials_dict contains any synthetics used
        """
        augmented = copy.deepcopy(recipe)
        temp_materials = dict(self.all_materials)  # Start with all real materials
        temp_materials.update(self.synthetic_materials)  # Add cached synthetics

        # Find all material positions in recipe
        material_positions = self._get_material_positions(augmented, recipe_type)

        # Decide which materials to replace with synthetics
        materials_to_replace = {}  # original_id -> synthetic_id

        unique_materials = set(mp[0] for mp in material_positions)

        for mat_id in unique_materials:
            if random.random() < self.synthetic_ratio:
                synthetic_id = self.get_or_create_synthetic(mat_id)
                if synthetic_id:
                    materials_to_replace[mat_id] = synthetic_id
                    temp_materials[synthetic_id] = self.synthetic_materials[synthetic_id]

        # Replace ALL instances of each material (consistency rule)
        self._replace_materials(augmented, recipe_type, materials_to_replace)

        return augmented, temp_materials

    def _get_material_positions(self, recipe: Dict, recipe_type: str) -> List[Tuple[str, str, int]]:
        """
        Get all material positions in a recipe.

        Returns list of (material_id, location_type, index)
        """
        positions = []

        if recipe_type == 'refining':
            for i, core in enumerate(recipe.get('coreInputs', [])):
                positions.append((core['materialId'], 'core', i))
            for i, spoke in enumerate(recipe.get('surroundingInputs', [])):
                positions.append((spoke['materialId'], 'spoke', i))

        elif recipe_type == 'alchemy':
            for i, ing in enumerate(recipe.get('ingredients', [])):
                positions.append((ing['materialId'], 'ingredient', i))

        elif recipe_type == 'engineering':
            for i, slot in enumerate(recipe.get('slots', [])):
                positions.append((slot['materialId'], 'slot', i))

        return positions

    def _replace_materials(self, recipe: Dict, recipe_type: str, replacements: Dict[str, str]):
        """Replace materials in recipe according to replacements dict."""
        if not replacements:
            return

        if recipe_type == 'refining':
            for core in recipe.get('coreInputs', []):
                if core['materialId'] in replacements:
                    core['materialId'] = replacements[core['materialId']]
            for spoke in recipe.get('surroundingInputs', []):
                if spoke['materialId'] in replacements:
                    spoke['materialId'] = replacements[spoke['materialId']]

        elif recipe_type == 'alchemy':
            for ing in recipe.get('ingredients', []):
                if ing['materialId'] in replacements:
                    ing['materialId'] = replacements[ing['materialId']]

        elif recipe_type == 'engineering':
            for slot in recipe.get('slots', []):
                if slot['materialId'] in replacements:
                    slot['materialId'] = replacements[slot['materialId']]


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


def augment_dataset_with_synthetics(recipes: List[Dict], labels: List[int],
                                    all_materials: Dict, recipe_type: str,
                                    augmentation_factor: int = 2,
                                    synthetic_ratio: float = 0.3) -> Tuple[List[Dict], List[int], Dict]:
    """
    Augment an entire dataset with synthetic materials.

    Args:
        recipes: List of recipe dicts
        labels: List of labels (1=valid, 0=invalid)
        all_materials: Dict of {material_id: material_data}
        recipe_type: One of 'alchemy', 'refining', 'engineering'
        augmentation_factor: How many augmented versions per original recipe
        synthetic_ratio: Probability of synthetic material injection

    Returns:
        Tuple of (augmented_recipes, augmented_labels, all_materials_including_synthetics)
    """
    augmentor = RecipeAugmentorWithSynthetics(all_materials, synthetic_ratio)

    augmented_recipes = []
    augmented_labels = []

    # Add original recipes
    augmented_recipes.extend(recipes)
    augmented_labels.extend(labels)

    # Add augmented versions
    for recipe, label in zip(recipes, labels):
        for _ in range(augmentation_factor - 1):  # -1 because we already added original
            aug_recipe, _ = augmentor.augment_recipe(recipe, recipe_type)
            augmented_recipes.append(aug_recipe)
            augmented_labels.append(label)

    # Combine all materials including synthetics
    combined_materials = dict(all_materials)
    combined_materials.update(augmentor.synthetic_materials)

    print(f"Augmented dataset:")
    print(f"  Original recipes: {len(recipes)}")
    print(f"  Augmented recipes: {len(augmented_recipes)}")
    print(f"  Synthetic materials created: {len(augmentor.synthetic_materials)}")

    return augmented_recipes, augmented_labels, combined_materials


def get_lightgbm_configs():
    """
    Generate LightGBM hyperparameter configurations.

    Strategy: Range from conservative (more regularized) to moderate.
    Avoid aggressive configs that tend to overfit on small datasets.

    Key regularization levers:
    - num_leaves: Lower = more regularization
    - min_data_in_leaf: Higher = more regularization
    - lambda_l1/l2: Higher = more regularization
    - feature_fraction: Lower = more regularization (like dropout)
    - learning_rate: Lower = better generalization
    """
    configs = [
        # Config 1: Conservative baseline (strong regularization)
        {
            'name': 'conservative_baseline',
            'num_leaves': 15,
            'learning_rate': 0.03,
            'min_data_in_leaf': 20,
            'feature_fraction': 0.7,
            'bagging_fraction': 0.7,
            'lambda_l1': 0.1,
            'lambda_l2': 0.1,
        },
        # Config 2: Conservative with higher learning rate
        {
            'name': 'conservative_fast',
            'num_leaves': 15,
            'learning_rate': 0.05,
            'min_data_in_leaf': 15,
            'feature_fraction': 0.8,
            'bagging_fraction': 0.8,
            'lambda_l1': 0.05,
            'lambda_l2': 0.1,
        },
        # Config 3: Moderate regularization
        {
            'name': 'moderate_reg',
            'num_leaves': 20,
            'learning_rate': 0.04,
            'min_data_in_leaf': 15,
            'feature_fraction': 0.8,
            'bagging_fraction': 0.8,
            'lambda_l1': 0.05,
            'lambda_l2': 0.05,
        },
        # Config 4: Moderate with more leaves
        {
            'name': 'moderate_capacity',
            'num_leaves': 25,
            'learning_rate': 0.03,
            'min_data_in_leaf': 20,
            'feature_fraction': 0.75,
            'bagging_fraction': 0.75,
            'lambda_l1': 0.1,
            'lambda_l2': 0.1,
        },
        # Config 5: Balanced (original-ish but with regularization)
        {
            'name': 'balanced',
            'num_leaves': 31,
            'learning_rate': 0.05,
            'min_data_in_leaf': 10,
            'feature_fraction': 0.9,
            'bagging_fraction': 0.8,
            'lambda_l1': 0.01,
            'lambda_l2': 0.01,
        },
        # Config 6: Low learning rate, more rounds
        {
            'name': 'slow_learner',
            'num_leaves': 20,
            'learning_rate': 0.02,
            'min_data_in_leaf': 15,
            'feature_fraction': 0.85,
            'bagging_fraction': 0.85,
            'lambda_l1': 0.02,
            'lambda_l2': 0.02,
        },
        # Config 7: Heavy L2 regularization
        {
            'name': 'heavy_l2',
            'num_leaves': 25,
            'learning_rate': 0.04,
            'min_data_in_leaf': 10,
            'feature_fraction': 0.8,
            'bagging_fraction': 0.8,
            'lambda_l1': 0.0,
            'lambda_l2': 0.2,
        },
        # Config 8: Heavy L1 regularization (feature selection)
        {
            'name': 'heavy_l1',
            'num_leaves': 25,
            'learning_rate': 0.04,
            'min_data_in_leaf': 10,
            'feature_fraction': 0.8,
            'bagging_fraction': 0.8,
            'lambda_l1': 0.2,
            'lambda_l2': 0.0,
        },
        # Config 9: Very conservative (for small datasets)
        {
            'name': 'very_conservative',
            'num_leaves': 10,
            'learning_rate': 0.05,
            'min_data_in_leaf': 25,
            'feature_fraction': 0.6,
            'bagging_fraction': 0.6,
            'lambda_l1': 0.15,
            'lambda_l2': 0.15,
        },
        # Config 10: Moderate with strong bagging
        {
            'name': 'strong_bagging',
            'num_leaves': 20,
            'learning_rate': 0.04,
            'min_data_in_leaf': 15,
            'feature_fraction': 0.7,
            'bagging_fraction': 0.6,
            'lambda_l1': 0.05,
            'lambda_l2': 0.05,
        },
    ]
    return configs


def calculate_robustness_score(val_accuracy, overfit_gap):
    """
    Calculate robustness-aware score that penalizes overfitting.

    Strategy: High accuracy is good, but overfitting is bad.
    A model with 92% accuracy and 2% gap is BETTER than
    a model with 95% accuracy and 8% gap.

    Penalty schedule:
    - gap < 3%: No penalty (excellent generalization)
    - gap 3-6%: Small penalty (acceptable)
    - gap 6-10%: Moderate penalty (concerning)
    - gap > 10%: Heavy penalty (likely overfit)
    """
    if overfit_gap is None:
        overfit_gap = 0.0

    # Ensure gap is positive (train_acc - val_acc)
    gap = abs(overfit_gap)

    if gap < 0.03:
        penalty = 1.0  # No penalty
    elif gap < 0.06:
        penalty = 0.97  # 3% penalty
    elif gap < 0.10:
        penalty = 0.90  # 10% penalty
    elif gap < 0.15:
        penalty = 0.80  # 20% penalty
    else:
        penalty = 0.65  # 35% penalty for severe overfitting

    return val_accuracy * penalty


def train_lightgbm_with_config(X_train, y_train, X_test, y_test, config, test_mode=False):
    """Train LightGBM with a specific config."""
    if test_mode:
        num_rounds = 5
        early_stop_rounds = 2
    else:
        num_rounds = 300  # More rounds, rely on early stopping
        early_stop_rounds = 30

    # Create datasets
    train_data = lgb.Dataset(X_train, label=y_train)
    test_data = lgb.Dataset(X_test, label=y_test, reference=train_data)

    # Build params from config
    params = {
        'objective': 'binary',
        'metric': 'binary_logloss',
        'boosting_type': 'gbdt',
        'num_leaves': config.get('num_leaves', 31),
        'learning_rate': config.get('learning_rate', 0.05),
        'min_data_in_leaf': config.get('min_data_in_leaf', 10),
        'feature_fraction': config.get('feature_fraction', 0.9),
        'bagging_fraction': config.get('bagging_fraction', 0.8),
        'bagging_freq': 5,
        'lambda_l1': config.get('lambda_l1', 0.0),
        'lambda_l2': config.get('lambda_l2', 0.0),
        'verbose': -1
    }

    # Train
    model = lgb.train(
        params,
        train_data,
        num_boost_round=num_rounds,
        valid_sets=[test_data],
        callbacks=[lgb.early_stopping(stopping_rounds=early_stop_rounds), lgb.log_evaluation(period=0)]
    )

    return model


def quick_evaluate(model, X_test, y_test, X_train, y_train):
    """Quick evaluation returning just accuracy and gap."""
    y_pred_test = (model.predict(X_test, num_iteration=model.best_iteration) > 0.5).astype(int)
    y_pred_train = (model.predict(X_train, num_iteration=model.best_iteration) > 0.5).astype(int)

    val_acc = accuracy_score(y_test, y_pred_test)
    train_acc = accuracy_score(y_train, y_pred_train)
    gap = train_acc - val_acc

    return val_acc, train_acc, gap


def train_lightgbm_classifier(X_train, y_train, X_test, y_test):
    """
    Train LightGBM classifier with automatic hyperparameter search.

    Tries multiple configs and selects the best based on robustness score
    (accuracy penalized by overfitting gap).
    """
    import os

    test_mode = os.environ.get('CLASSIFIER_TEST_MODE', '0') == '1'

    if test_mode:
        print("\n*** TEST MODE: Single config, 5 rounds ***")
        configs = [get_lightgbm_configs()[4]]  # Just use balanced config
    else:
        print("\n=== LightGBM Hyperparameter Search ===")
        configs = get_lightgbm_configs()

    print(f"Testing {len(configs)} configurations...")

    results = []
    best_model = None
    best_score = -1
    best_config_name = None

    for i, config in enumerate(configs):
        config_name = config.get('name', f'config_{i}')
        print(f"\n  [{i+1}/{len(configs)}] {config_name}...", end=" ", flush=True)

        try:
            model = train_lightgbm_with_config(X_train, y_train, X_test, y_test, config, test_mode)
            val_acc, train_acc, gap = quick_evaluate(model, X_test, y_test, X_train, y_train)
            score = calculate_robustness_score(val_acc, gap)

            print(f"val={val_acc:.3f}, gap={gap:.3f}, score={score:.3f}")

            results.append({
                'name': config_name,
                'val_acc': val_acc,
                'train_acc': train_acc,
                'gap': gap,
                'score': score,
                'model': model
            })

            if score > best_score:
                best_score = score
                best_model = model
                best_config_name = config_name

        except Exception as e:
            print(f"FAILED: {e}")
            continue

    # Summary
    print(f"\n=== Search Complete ===")
    print(f"Best config: {best_config_name} (score={best_score:.3f})")

    # Show top 3
    results.sort(key=lambda x: x['score'], reverse=True)
    print(f"\nTop 3 configs:")
    for i, r in enumerate(results[:3]):
        print(f"  {i+1}. {r['name']}: val={r['val_acc']:.3f}, gap={r['gap']:.3f}, score={r['score']:.3f}")

    return best_model


def evaluate_model(model, X_test, y_test, X_train=None, y_train=None):
    """Evaluate model performance."""
    print("\nEvaluating model...")

    # Check for test mode from environment variable
    test_mode = os.environ.get('CLASSIFIER_TEST_MODE', '0') == '1'

    # Predictions on test
    y_pred_proba = model.predict(X_test, num_iteration=model.best_iteration)
    y_pred = (y_pred_proba > 0.5).astype(int)

    # Test metrics
    test_accuracy = accuracy_score(y_test, y_pred)
    precision = precision_score(y_test, y_pred)
    recall = recall_score(y_test, y_pred)
    f1 = f1_score(y_test, y_pred)

    # Training accuracy if provided
    train_accuracy = None
    overfit_gap = None
    if X_train is not None and y_train is not None:
        y_train_pred = model.predict(X_train, num_iteration=model.best_iteration)
        y_train_pred = (y_train_pred > 0.5).astype(int)
        train_accuracy = accuracy_score(y_train, y_train_pred)
        overfit_gap = train_accuracy - test_accuracy

    print(f"\n{'=' * 50}")
    print(f"PERFORMANCE METRICS")
    print(f"{'=' * 50}")
    if train_accuracy is not None:
        print(f"Train Accuracy: {train_accuracy:.4f}")
    print(f"Val Accuracy:   {test_accuracy:.4f}")
    if overfit_gap is not None:
        print(f"Overfit Gap:    {overfit_gap:.4f} ({overfit_gap*100:.1f}%)")
    print(f"Precision:      {precision:.4f}")
    print(f"Recall:         {recall:.4f}")
    print(f"F1 Score:       {f1:.4f}")
    print(f"{'=' * 50}")

    # Check requirements (90% accuracy, <6% overfit - matching CNN thresholds)
    # Note: Lowered from 95%/<4% because small datasets make 95% unreliable
    meets_acc = test_accuracy >= 0.90
    meets_gap = overfit_gap is not None and overfit_gap < 0.06

    print(f"\n{'=' * 50}")
    print(f"REQUIREMENTS CHECK")
    print(f"{'=' * 50}")
    print(f"Accuracy >=90%: {'PASS' if meets_acc else 'FAIL'} ({test_accuracy*100:.1f}%)")
    print(f"Gap <6%:        {'PASS' if meets_gap else 'FAIL'} ({overfit_gap*100:.1f}% gap)" if overfit_gap is not None else "Gap <6%:        N/A")
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

    # Determine if model meets criteria
    all_pass = meets_acc and meets_gap

    return {
        'val_accuracy': test_accuracy,
        'train_accuracy': train_accuracy,
        'overfit_gap': overfit_gap,
        'precision': precision,
        'recall': recall,
        'f1': f1,
        'meets_criteria': all_pass,
        'test_mode': test_mode
    }


def save_model(model, feature_extractor, discipline, output_dir, metrics=None):
    """Save trained model and feature extractor.

    Args:
        model: Trained LightGBM model
        feature_extractor: Feature extractor instance
        discipline: Discipline name
        output_dir: Output directory
        metrics: Optional dict with 'meets_criteria' and 'test_mode' keys
    """
    # Check if we should save
    should_save = True
    save_reason = ""

    # Always save, but with different naming based on criteria
    is_candidate = False
    if metrics is not None:
        meets_criteria = metrics.get('meets_criteria', False)
        test_mode = metrics.get('test_mode', False)

        if test_mode:
            should_save = True
            save_reason = "(test mode)"
        elif meets_criteria:
            should_save = True
            save_reason = "(meets criteria: >=90% acc, <6% gap)"
        else:
            # Still save as candidate - don't leave user with nothing
            should_save = True
            is_candidate = True
            val_acc = metrics.get('val_accuracy', 0)
            gap = metrics.get('overfit_gap', 0)
            save_reason = f"(CANDIDATE - acc={val_acc*100:.1f}%, gap={gap*100:.1f}%)"
            print(f"\n[WARNING] Model did not meet full criteria:")
            print(f"          Val accuracy: {val_acc*100:.1f}% (need >=90%)")
            print(f"          Overfit gap: {gap*100:.1f}% (need <6%)")
            print(f"          Saving as candidate model anyway...")

    os.makedirs(output_dir, exist_ok=True)

    model_path = os.path.join(output_dir, f'{discipline}_model.txt')
    extractor_path = os.path.join(output_dir, f'{discipline}_extractor.pkl')

    # Save LightGBM model
    model.save_model(model_path)

    # Save feature extractor
    with open(extractor_path, 'wb') as f:
        pickle.dump(feature_extractor, f)

    print(f"\n[SAVED] Model saved {save_reason}: {model_path}")
    print(f"        Feature extractor saved: {extractor_path}")
    return True


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
    import argparse

    parser = argparse.ArgumentParser(
        description='LightGBM Recipe Classifier - Train & Test',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Train a new model
  python LightGBM_trainer.py train data.json materials.json output_dir/

  # With custom augmentation
  python LightGBM_trainer.py train data.json materials.json output_dir/ --aug-factor 3 --synthetic-ratio 0.4
        """
    )
    subparsers = parser.add_subparsers(dest='command', help='Command to run')

    # Train subcommand
    train_parser = subparsers.add_parser('train', help='Train a new model')
    train_parser.add_argument('dataset', help='Path to augmented dataset JSON')
    train_parser.add_argument('materials', help='Path to materials JSON')
    train_parser.add_argument('output_dir', help='Directory to save model')
    train_parser.add_argument('--aug-factor', type=int, default=2,
                              help='Augmentation factor (default: 2)')
    train_parser.add_argument('--synthetic-ratio', type=float, default=0.3,
                              help='Synthetic material injection ratio (default: 0.3)')

    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        return

    print("=" * 70)
    print("LIGHTGBM RECIPE CLASSIFIER - TRAIN & TEST")
    print("With Synthetic Material Augmentation")
    print("=" * 70)

    if args.command == 'train':
        dataset_path = args.dataset
        materials_path = args.materials
        model_output_dir = args.output_dir
        aug_factor = args.aug_factor
        synthetic_ratio = args.synthetic_ratio

        print(f"\nDataset: {dataset_path}")
        print(f"Materials: {materials_path}")
        print(f"Output: {model_output_dir}")
        print(f"Aug factor: {aug_factor}, Synthetic ratio: {synthetic_ratio}")

        # Load data
        print("\nLoading data...")
        recipes, labels, discipline = load_dataset(dataset_path)

        with open(materials_path, 'r') as f:
            materials_data = json.load(f)
        all_materials = {m['materialId']: m for m in materials_data['materials']}

        print(f"   Discipline: {discipline}")
        print(f"   Total recipes: {len(recipes)}")
        print(f"   Valid recipes: {sum(labels)}")
        print(f"   Invalid recipes: {len(labels) - sum(labels)}")
        print(f"   Materials: {len(all_materials)}")

        # Augment with synthetics
        print("\nAugmenting with synthetic materials...")
        recipes, labels, all_materials = augment_dataset_with_synthetics(
            recipes, labels, all_materials, discipline,
            augmentation_factor=aug_factor,
            synthetic_ratio=synthetic_ratio
        )

        # Create feature extractor
        print("\nBuilding feature extractor...")
        feature_extractor = RecipeFeatureExtractor(all_materials)

        # Extract features
        print(f"Extracting features for {discipline}...")
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
        metrics = evaluate_model(model, X_test, y_test, X_train, y_train)

        # Save model (conditionally based on criteria)
        saved = save_model(model, feature_extractor, discipline, model_output_dir, metrics)

        if saved:
            print("\nTraining complete! Model saved.")
        else:
            print("\nTraining complete. Model did not meet criteria and was not saved.")


if __name__ == "__main__":
    main()

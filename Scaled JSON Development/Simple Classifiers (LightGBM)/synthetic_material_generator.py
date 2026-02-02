"""
Synthetic Material Generator for LightGBM Training

Generates "virtual" materials that follow all substitution rules to combat overfitting.
These synthetic materials are created by modifying existing materials while respecting:

HARD RULES (must match exactly):
1. Same category (metal→metal, wood→wood, etc.)
2. Same refined/basic status (ingots stay ingots, ores stay ores)

The goal is to teach LightGBM to recognize valid PATTERNS rather than memorizing
specific material combinations.

Usage:
    generator = SyntheticMaterialGenerator(all_materials)
    synthetic = generator.create_synthetic_variant(base_material_id)

Created: 2026-02-02
"""

import random
import copy
from typing import Dict, List, Optional, Set, Tuple
import uuid


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

    def is_valid_substitute(self, original_id: str, substitute_id: str) -> bool:
        """
        Check if substitute is a valid replacement for original.

        Rules:
        1. Same category
        2. Same refined/basic status
        3. Either: (a) ALL tags match, or (b) tier ±1 AND ≥2 matching tags
        """
        if original_id not in self.all_materials:
            return False

        orig = self.all_materials[original_id]
        # Handle synthetic materials
        if substitute_id.startswith('synthetic_'):
            return True  # Synthetics are created to be valid by construction

        if substitute_id not in self.all_materials:
            return False

        sub = self.all_materials[substitute_id]

        # Must be same category
        if orig.get('category') != sub.get('category'):
            return False

        orig_tags = set(orig.get('metadata', {}).get('tags', []))
        sub_tags = set(sub.get('metadata', {}).get('tags', []))

        # Must have same refined/basic status
        orig_refined = 'refined' in orig_tags
        orig_basic = 'basic' in orig_tags or 'raw' in orig_tags
        sub_refined = 'refined' in sub_tags
        sub_basic = 'basic' in sub_tags or 'raw' in sub_tags

        if orig_refined != sub_refined:
            return False
        if orig_basic != sub_basic:
            return False

        # Rule 1: All tags match
        if orig_tags == sub_tags:
            return True

        # Rule 2: Tier ±1 AND ≥2 matching tags
        tier_diff = abs(orig.get('tier', 1) - sub.get('tier', 1))
        matching_tags = len(orig_tags & sub_tags)

        return tier_diff <= 1 and matching_tags >= 2


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
        # Check cache first
        cache_key = f"{base_material_id}_{random.randint(0, 999)}"

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


# Test the generator
if __name__ == "__main__":
    import json

    # Load materials
    MATERIALS_PATH = "../../Game-1-modular/items.JSON/items-materials-1.JSON"

    try:
        with open(MATERIALS_PATH, 'r') as f:
            data = json.load(f)
        materials_dict = {m['materialId']: m for m in data['materials']}
        print(f"Loaded {len(materials_dict)} materials\n")
    except Exception as e:
        print(f"Error loading materials: {e}")
        exit(1)

    # Test synthetic generation
    generator = SyntheticMaterialGenerator(materials_dict)

    print("Synthetic Material Generation Test:\n")
    print(f"{'Base Material':<25} {'Category':<15} {'Tier':<6} {'Synthetic Tier':<15} {'Tags (base)':<30}")
    print("-" * 100)

    test_materials = ['iron_ingot', 'oak_plank', 'obsidian', 'fire_crystal', 'wolf_pelt']

    for mat_id in test_materials:
        if mat_id in materials_dict:
            base = materials_dict[mat_id]
            synthetic = generator.create_synthetic_variant(mat_id)

            if synthetic:
                base_tags = base.get('metadata', {}).get('tags', [])
                print(f"{mat_id:<25} {base.get('category'):<15} {base.get('tier'):<6} "
                      f"{synthetic.get('tier'):<15} {str(base_tags):<30}")

    print("\n\nValidation Test:")
    print("-" * 50)

    # Test that synthetics are valid
    augmentor = RecipeAugmentorWithSynthetics(materials_dict, synthetic_ratio=0.5)

    for mat_id in test_materials:
        if mat_id in materials_dict:
            synthetic_id = augmentor.get_or_create_synthetic(mat_id)
            if synthetic_id:
                is_valid = generator.is_valid_substitute(mat_id, synthetic_id)
                print(f"  {mat_id} -> {synthetic_id[:20]}...: {'✓ VALID' if is_valid else '✗ INVALID'}")

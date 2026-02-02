"""
Refining Recipe Data Augmentation
Generates training dataset with positive and negative samples
"""

import json
import random
import uuid
import copy
from typing import List, Dict, Tuple
from collections import Counter

def load_json(filepath: str) -> Dict:
    """Load JSON file."""
    with open(filepath, 'r') as f:
        return json.load(f)


def save_dataset(recipes: List[Dict], labels: List[int], output_path: str):
    """Save augmented dataset."""
    dataset = {
        'discipline': 'refining',
        'total_samples': len(recipes),
        'positive_samples': sum(labels),
        'negative_samples': len(labels) - sum(labels),
        'data': [
            {'recipe': recipe, 'label': label}
            for recipe, label in zip(recipes, labels)
        ]
    }

    with open(output_path, 'w') as f:
        json.dump(dataset, f, indent=2)

    print(f"✅ Saved {len(recipes)} samples ({sum(labels)} positive, {len(labels) - sum(labels)} negative)")


def find_same_category_materials(material_id: str, all_materials: Dict) -> List[str]:
    """Find materials with same category."""
    if material_id not in all_materials:
        return []

    base_category = all_materials[material_id].get('category', 'unknown')

    candidates = [
        mid for mid, mat in all_materials.items()
        if mat.get('category') == base_category and mid != material_id
    ]

    return candidates


def find_different_category_materials(material_id: str, all_materials: Dict) -> List[str]:
    """Find materials with different category."""
    if material_id not in all_materials:
        return []

    base_category = all_materials[material_id].get('category', 'unknown')

    candidates = [
        mid for mid, mat in all_materials.items()
        if mat.get('category') != base_category
    ]

    return candidates


def augment_recipe_simple(recipe: Dict, all_materials: Dict, num_variants: int = 5) -> List[Dict]:
    """
    Generate simple variants by substituting materials within same category.
    ALWAYS includes the original recipe.
    """
    variants = [copy.deepcopy(recipe)]  # Always include original

    for _ in range(num_variants - 1):
        variant = copy.deepcopy(recipe)
        variant['recipeId'] = f"{recipe['recipeId']}_var_{uuid.uuid4().hex[:8]}"

        # Randomly substitute one core material
        if variant['coreInputs'] and random.random() < 0.7:
            idx = random.randint(0, len(variant['coreInputs']) - 1)
            mat_id = variant['coreInputs'][idx]['materialId']
            substitutes = find_same_category_materials(mat_id, all_materials)
            if substitutes:
                variant['coreInputs'][idx]['materialId'] = random.choice(substitutes)

        # Randomly substitute one spoke material
        if variant['surroundingInputs'] and random.random() < 0.5:
            idx = random.randint(0, len(variant['surroundingInputs']) - 1)
            mat_id = variant['surroundingInputs'][idx]['materialId']
            substitutes = find_same_category_materials(mat_id, all_materials)
            if substitutes:
                variant['surroundingInputs'][idx]['materialId'] = random.choice(substitutes)

        variants.append(variant)

    return variants


def generate_negative_samples(valid_recipes: List[Dict], all_materials: Dict, num_per_recipe: int = 3) -> List[Dict]:
    """Generate invalid recipes."""
    negatives = []

    for recipe in valid_recipes:
        for _ in range(num_per_recipe):
            negative = copy.deepcopy(recipe)
            negative['recipeId'] = f"negative_{uuid.uuid4().hex[:8]}"

            # Type 1: Wrong category substitution (most common error)
            if negative['coreInputs'] and random.random() < 0.6:
                idx = random.randint(0, len(negative['coreInputs']) - 1)
                mat_id = negative['coreInputs'][idx]['materialId']
                wrong_materials = find_different_category_materials(mat_id, all_materials)
                if wrong_materials:
                    negative['coreInputs'][idx]['materialId'] = random.choice(wrong_materials)

            # Type 2: Too many spokes (violate ratio)
            elif random.random() < 0.3:
                num_extra = random.randint(4, 8)
                for _ in range(num_extra):
                    negative['surroundingInputs'].append({
                        'materialId': random.choice(list(all_materials.keys())),
                        'quantity': random.randint(1, 3)
                    })

            # Type 3: Random invalid combination
            else:
                negative['coreInputs'] = [
                    {'materialId': random.choice(list(all_materials.keys())), 'quantity': random.randint(1, 3)}
                    for _ in range(random.randint(1, 3))
                ]
                negative['surroundingInputs'] = [
                    {'materialId': random.choice(list(all_materials.keys())), 'quantity': random.randint(1, 3)}
                    for _ in range(random.randint(0, 5))
                ]

            negatives.append(negative)

    return negatives


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description='Refining Recipe Data Augmentation',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python data_augment_ref.py materials.json placements.json output.json
  python data_augment_ref.py ../items.json ../recipes.json refining_data.json
        """
    )
    parser.add_argument('materials', help='Path to materials JSON file')
    parser.add_argument('placements', help='Path to placements/recipes JSON file')
    parser.add_argument('output', help='Output path for augmented dataset')

    args = parser.parse_args()

    materials_path = args.materials
    placements_path = args.placements
    output_path = args.output

    print("=" * 70)
    print("REFINING RECIPE DATA AUGMENTATION")
    print("=" * 70)
    print(f"\nMaterials: {materials_path}")
    print(f"Placements: {placements_path}")
    print(f"Output: {output_path}")

    # Load data
    print("\n📂 Loading data...")
    materials_data = load_json(materials_path)
    placements_data = load_json(placements_path)

    all_materials = {m['materialId']: m for m in materials_data['materials']}
    original_recipes = placements_data['placements']

    print(f"   Loaded {len(original_recipes)} original recipes")
    print(f"   Loaded {len(all_materials)} materials")

    # Generate positive samples (augment originals)
    print("\n🔄 Generating positive samples...")
    all_positives = []
    for recipe in original_recipes:
        variants = augment_recipe_simple(recipe, all_materials, num_variants=8)
        all_positives.extend(variants)

    print(f"   Generated {len(all_positives)} positive samples (includes all originals)")

    # Generate negative samples
    print("\n❌ Generating negative samples...")
    negatives = generate_negative_samples(original_recipes, all_materials, num_per_recipe=5)
    print(f"   Generated {len(negatives)} negative samples")

    # Combine and shuffle
    all_recipes = all_positives + negatives
    all_labels = [1] * len(all_positives) + [0] * len(negatives)

    combined = list(zip(all_recipes, all_labels))
    random.shuffle(combined)
    all_recipes, all_labels = zip(*combined)

    # Save
    print("\n💾 Saving dataset...")
    save_dataset(list(all_recipes), list(all_labels), output_path)

    print("\n✨ Augmentation complete!")


if __name__ == "__main__":
    main()
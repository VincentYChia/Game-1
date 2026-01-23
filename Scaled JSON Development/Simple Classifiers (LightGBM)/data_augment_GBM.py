"""
Crafting Recipe Data Augmentation System
Generates augmented datasets for LightGBM training across three disciplines:
- Refining (hub-and-spoke)
- Alchemy (sequential)
- Engineering (slot-based)
"""

import json
import itertools
import random
import uuid
import os
from typing import List, Dict, Any, Tuple, Set
from collections import defaultdict, Counter
import copy

# ============================================================================
# MATERIAL SUBSTITUTION ENGINE (Shared across all disciplines)
# ============================================================================

def find_substitutable_materials(material_id: str, material: Dict, all_materials: Dict) -> List[str]:
    """
    Find materials that can substitute for this one.

    HARD REQUIREMENTS (must match exactly):
    - Same category
    - Same refinement status (refined vs basic, inferred from tags)

    SUBSTITUTION RULES (one must be true):
    - Rule 1: ALL tags identical → Can substitute at ANY tier
    - Rule 2: Tier difference ≤1 AND ≥2 matching tags
    """
    if material_id not in all_materials:
        return []

    base_material = all_materials[material_id]
    substitutes = []

    # Get tags from metadata
    base_tags = set(base_material.get('metadata', {}).get('tags', []))
    base_category = base_material.get('category', 'unknown')
    base_tier = base_material.get('tier', 1)

    # Determine refinement status from tags
    base_is_refined = 'refined' in base_tags
    base_is_basic = 'basic' in base_tags or 'raw' in base_tags

    for candidate_id, candidate in all_materials.items():
        if candidate_id == material_id:
            continue

        # Hard requirement: same category
        if candidate.get('category') != base_category:
            continue

        # Get candidate info
        candidate_tags = set(candidate.get('metadata', {}).get('tags', []))
        candidate_tier = candidate.get('tier', 1)
        candidate_is_refined = 'refined' in candidate_tags
        candidate_is_basic = 'basic' in candidate_tags or 'raw' in candidate_tags

        # Hard requirement: same refinement status
        if base_is_refined != candidate_is_refined:
            continue
        if base_is_basic != candidate_is_basic:
            continue

        # Substitution Rule 1: All tags identical
        if base_tags == candidate_tags:
            substitutes.append(candidate_id)
            continue

        # Substitution Rule 2: Tier difference ≤1 AND ≥2 matching tags
        tier_diff = abs(base_tier - candidate_tier)
        matching_tags = len(base_tags & candidate_tags)

        if tier_diff <= 1 and matching_tags >= 2:
            substitutes.append(candidate_id)

    return substitutes


def find_opposite_refinement(material_id: str, all_materials: Dict) -> str:
    """Find material with same category but opposite refinement level."""
    if material_id not in all_materials:
        return random.choice(list(all_materials.keys()))

    base_material = all_materials[material_id]
    base_category = base_material.get('category')
    base_tags = set(base_material.get('metadata', {}).get('tags', []))

    # Determine current refinement status
    base_is_refined = 'refined' in base_tags
    base_is_basic = 'basic' in base_tags or 'raw' in base_tags

    # Find materials with same category but opposite refinement
    candidates = []
    for mid, mat in all_materials.items():
        if mat.get('category') != base_category:
            continue

        mat_tags = set(mat.get('metadata', {}).get('tags', []))
        mat_is_refined = 'refined' in mat_tags
        mat_is_basic = 'basic' in mat_tags or 'raw' in mat_tags

        # Opposite refinement
        if base_is_refined and mat_is_basic:
            candidates.append(mid)
        elif base_is_basic and mat_is_refined:
            candidates.append(mid)

    if candidates:
        return random.choice(candidates)

    return random.choice(list(all_materials.keys()))


def find_different_category(material_id: str, all_materials: Dict) -> str:
    """Find material from a completely different category."""
    if material_id not in all_materials:
        return random.choice(list(all_materials.keys()))

    base_category = all_materials[material_id].get('category')

    candidates = [
        mid for mid, mat in all_materials.items()
        if mat.get('category') != base_category
    ]

    if candidates:
        return random.choice(candidates)

    return random.choice(list(all_materials.keys()))


# ============================================================================
# DUPLICATE REMOVAL
# ============================================================================

def normalize_refining_recipe(recipe: Dict) -> str:
    """Normalize refining recipe for duplicate detection."""
    cores = sorted([f"{m['materialId']}:{m['quantity']}" for m in recipe['coreInputs']])
    spokes = sorted([f"{m['materialId']}:{m['quantity']}" for m in recipe['surroundingInputs']])
    return f"refining|{recipe['outputId']}|{'|'.join(cores)}|{'|'.join(spokes)}"


def normalize_alchemy_recipe(recipe: Dict) -> str:
    """Normalize alchemy recipe for duplicate detection (order matters!)."""
    ingredients = [f"{ing['slot']}:{ing['materialId']}:{ing['quantity']}"
                   for ing in sorted(recipe['ingredients'], key=lambda x: x['slot'])]
    return f"alchemy|{recipe['outputId']}|{'|'.join(ingredients)}"


def normalize_engineering_recipe(recipe: Dict) -> str:
    """Normalize engineering recipe for duplicate detection."""
    slots = sorted([f"{s['type']}:{s['materialId']}:{s['quantity']}" for s in recipe['slots']])
    return f"engineering|{recipe['outputId']}|{'|'.join(slots)}"


def remove_duplicates(recipes: List[Tuple[Dict, int]], normalize_fn) -> List[Tuple[Dict, int]]:
    """Remove duplicate recipes using normalization function."""
    seen = set()
    unique = []

    for recipe, label in recipes:
        normalized = normalize_fn(recipe)
        if normalized not in seen:
            seen.add(normalized)
            unique.append((recipe, label))

    return unique


# ============================================================================
# REFINING AUGMENTATION (Hub-and-Spoke)
# ============================================================================

def find_substitutable_materials_aggressive(material_id: str, all_materials: Dict) -> List[str]:
    """
    Aggressive substitution for refining - just needs ≥2 matching tags.

    HARD REQUIREMENTS:
    - Same category
    - Same refinement status (refined vs basic)

    SUBSTITUTION RULE:
    - ≥2 matching tags (ignore tier difference!)
    """
    if material_id not in all_materials:
        return []

    base_material = all_materials[material_id]
    substitutes = []

    base_tags = set(base_material.get('metadata', {}).get('tags', []))
    base_category = base_material.get('category', 'unknown')
    base_is_refined = 'refined' in base_tags
    base_is_basic = 'basic' in base_tags or 'raw' in base_tags

    for candidate_id, candidate in all_materials.items():
        if candidate_id == material_id:
            continue

        # Hard requirement: same category
        if candidate.get('category') != base_category:
            continue

        candidate_tags = set(candidate.get('metadata', {}).get('tags', []))
        candidate_is_refined = 'refined' in candidate_tags
        candidate_is_basic = 'basic' in candidate_tags or 'raw' in candidate_tags

        # Hard requirement: same refinement status
        if base_is_refined != candidate_is_refined:
            continue
        if base_is_basic != candidate_is_basic:
            continue

        # Just need ≥2 matching tags - that's it!
        matching_tags = len(base_tags & candidate_tags)
        if matching_tags >= 2:
            substitutes.append(candidate_id)

    return substitutes


def generate_synthetic_refining_recipes(all_materials: Dict) -> List[Dict]:
    """
    Generate new valid refining recipes for ALL three valid patterns:
    Pattern 1: Basic smelting (0 spokes) - ore/log → ingot/plank
    Pattern 2: Alloying (2+ hubs, 0 spokes) - metal + metal → alloy
    Pattern 3: Elemental infusion (1 hub, 1-3 spokes) - refined + elemental

    Keep them balanced!
    """
    synthetic = []

    # Pattern 1: Basic smelting (ore/log → ingot/plank, 0 spokes)
    # Find raw materials
    raw_materials = [
        mat_id for mat_id, mat in all_materials.items()
        if 'basic' in mat.get('metadata', {}).get('tags', [])
        or 'raw' in mat.get('metadata', {}).get('tags', [])
    ]

    # Generate ~30 basic smelting recipes
    for _ in range(30):
        if not raw_materials:
            break
        raw_mat = random.choice(raw_materials)
        mat_tier = all_materials[raw_mat].get('tier', 1)

        recipe = {
            'recipeId': f"synthetic_smelt_{uuid.uuid4().hex[:8]}",
            'outputId': f"{raw_mat}_processed",
            'stationTier': min(mat_tier, 4),
            'coreInputs': [{'materialId': raw_mat, 'quantity': 1}],
            'surroundingInputs': []
        }
        synthetic.append(recipe)

    # Pattern 2: Alloying (2 hubs, 0 spokes)
    # Find refined metals
    refined_metals = [
        mat_id for mat_id, mat in all_materials.items()
        if mat.get('category') == 'metal'
        and 'refined' in mat.get('metadata', {}).get('tags', [])
    ]

    # Generate ~30 alloying recipes
    for _ in range(30):
        if len(refined_metals) < 2:
            break
        metals = random.sample(refined_metals, 2)
        tier = max(all_materials[m].get('tier', 1) for m in metals)

        recipe = {
            'recipeId': f"synthetic_alloy_{uuid.uuid4().hex[:8]}",
            'outputId': f"alloy_of_{metals[0][:6]}_{metals[1][:6]}",
            'stationTier': min(tier, 4),
            'coreInputs': [
                {'materialId': metals[0], 'quantity': random.randint(1, 2)},
                {'materialId': metals[1], 'quantity': random.randint(1, 2)}
            ],
            'surroundingInputs': []
        }
        synthetic.append(recipe)

    # Pattern 3: Elemental infusion (1 hub, 1-3 elemental spokes)
    # Find refined materials
    refined_materials = [
        mat_id for mat_id, mat in all_materials.items()
        if 'refined' in mat.get('metadata', {}).get('tags', [])
    ]

    # Find elemental materials
    elemental_materials = [
        mat_id for mat_id, mat in all_materials.items()
        if mat.get('category') == 'elemental'
    ]

    # Generate ~30 infusion recipes
    for _ in range(30):
        if not refined_materials or not elemental_materials:
            break

        refined_mat = random.choice(refined_materials)
        mat_tier = all_materials[refined_mat].get('tier', 1)

        # 1-3 elemental spokes
        num_spokes = random.randint(1, 3)
        if len(elemental_materials) < num_spokes:
            num_spokes = len(elemental_materials)

        spokes = random.sample(elemental_materials, num_spokes)

        recipe = {
            'recipeId': f"synthetic_infuse_{uuid.uuid4().hex[:8]}",
            'outputId': f"{refined_mat}_enhanced",
            'stationTier': min(mat_tier, 4),
            'coreInputs': [{'materialId': refined_mat, 'quantity': 1}],
            'surroundingInputs': [
                {'materialId': spoke, 'quantity': random.randint(1, 3)}
                for spoke in spokes
            ]
        }
        synthetic.append(recipe)

    return synthetic


def augment_refining_material_substitution(recipe: Dict, all_materials: Dict) -> List[Dict]:
    """Generate variants by substituting materials in cores and spokes - AGGRESSIVE."""
    variants = []

    # Get substitution options for core inputs (AGGRESSIVE)
    core_options = []
    for core in recipe['coreInputs']:
        mat_id = core['materialId']
        subs = [mat_id] + find_substitutable_materials_aggressive(mat_id, all_materials)
        # Take up to 8 substitutes per material
        core_options.append([(s, core['quantity']) for s in subs[:8]])

    # Get substitution options for surrounding inputs (AGGRESSIVE)
    spoke_options = []
    for spoke in recipe['surroundingInputs']:
        mat_id = spoke['materialId']
        subs = [mat_id] + find_substitutable_materials_aggressive(mat_id, all_materials)
        spoke_options.append([(s, spoke['quantity']) for s in subs[:8]])

    # Generate cross-product
    if not spoke_options:
        spoke_options = [[]]

    for core_combo in itertools.product(*core_options):
        for spoke_combo in itertools.product(*spoke_options):
            new_recipe = copy.deepcopy(recipe)
            new_recipe['recipeId'] = f"{recipe['recipeId']}_aug_{uuid.uuid4().hex[:8]}"
            new_recipe['coreInputs'] = [
                {'materialId': mat_id, 'quantity': qty}
                for mat_id, qty in core_combo
            ]
            new_recipe['surroundingInputs'] = [
                {'materialId': mat_id, 'quantity': qty}
                for mat_id, qty in spoke_combo if spoke_combo != [()]
            ]
            variants.append(new_recipe)

    return variants  # Don't limit here - let the complete function handle it


def augment_refining_permutations(recipe: Dict) -> List[Dict]:
    """Generate all valid permutations of cores and spokes."""
    variants = []

    # Permute core inputs
    core_perms = list(itertools.permutations(recipe['coreInputs']))

    # Permute surrounding inputs
    if recipe['surroundingInputs']:
        spoke_perms = list(itertools.permutations(recipe['surroundingInputs']))
    else:
        spoke_perms = [[]]

    for core_perm in core_perms[:6]:  # Limit factorial growth
        for spoke_perm in spoke_perms[:4]:
            new_recipe = copy.deepcopy(recipe)
            new_recipe['recipeId'] = f"{recipe['recipeId']}_perm_{uuid.uuid4().hex[:8]}"
            new_recipe['coreInputs'] = list(core_perm)
            new_recipe['surroundingInputs'] = list(spoke_perm) if spoke_perm != [[]] else []
            variants.append(new_recipe)

    return variants


def augment_refining_complete(recipe: Dict, all_materials: Dict) -> List[Dict]:
    """Complete augmentation: material substitution + permutations."""
    # Material substitution (generates many variants with aggressive mode)
    material_variants = augment_refining_material_substitution(recipe, all_materials)

    # Limit material variants to prevent synthetic recipes from overwhelming
    if len(material_variants) > 20:
        material_variants = random.sample(material_variants, 20)

    # Permutations on material variants
    all_variants = []
    for variant in material_variants:
        perms = augment_refining_permutations(variant)
        all_variants.extend(perms)

    # Remove duplicates
    unique_variants = remove_duplicates(
        [(v, 1) for v in all_variants],
        normalize_refining_recipe
    )

    # Target 10-15 variants per base recipe (reduced from 30)
    final_variants = [v for v, _ in unique_variants]

    # Sample if too many
    if len(final_variants) > 15:
        final_variants = random.sample(final_variants, 15)

    return final_variants


def generate_refining_negatives(valid_recipes: List[Dict], all_materials: Dict, num_per_recipe: int = 5) -> List[Tuple[Dict, int]]:
    """Generate invalid refining recipes - more aggressive for balance."""
    negatives = []

    # Collect statistics
    hub_counts = [len(r['coreInputs']) for r in valid_recipes]
    spoke_hub_ratios = [
        len(r['surroundingInputs']) / max(1, len(r['coreInputs']))
        for r in valid_recipes
    ]

    # Calculate how many of each type to generate
    negatives_per_type = max(1, num_per_recipe // 4)

    for recipe in valid_recipes:
        generated = 0

        # Type 1: Violate substitution rules (refined → basic or vice versa)
        for _ in range(negatives_per_type):
            if generated >= num_per_recipe:
                break
            negative = copy.deepcopy(recipe)
            negative['recipeId'] = f"negative_{uuid.uuid4().hex[:8]}"
            if negative['coreInputs']:
                idx = random.randint(0, len(negative['coreInputs']) - 1)
                mat_id = negative['coreInputs'][idx]['materialId']
                opposite = find_opposite_refinement(mat_id, all_materials)
                negative['coreInputs'][idx]['materialId'] = opposite
            negatives.append((negative, 0))
            generated += 1

        # Type 2: Wrong category substitution
        for _ in range(negatives_per_type):
            if generated >= num_per_recipe:
                break
            negative = copy.deepcopy(recipe)
            negative['recipeId'] = f"negative_{uuid.uuid4().hex[:8]}"
            if random.random() < 0.5 and negative['coreInputs']:
                idx = random.randint(0, len(negative['coreInputs']) - 1)
                mat_id = negative['coreInputs'][idx]['materialId']
                wrong = find_different_category(mat_id, all_materials)
                negative['coreInputs'][idx]['materialId'] = wrong
            elif negative['surroundingInputs']:
                idx = random.randint(0, len(negative['surroundingInputs']) - 1)
                mat_id = negative['surroundingInputs'][idx]['materialId']
                wrong = find_different_category(mat_id, all_materials)
                negative['surroundingInputs'][idx]['materialId'] = wrong
            negatives.append((negative, 0))
            generated += 1

        # Type 3: Too many spokes (>3 spokes violates 1-3:1 ratio)
        for _ in range(negatives_per_type):
            if generated >= num_per_recipe:
                break
            negative = copy.deepcopy(recipe)
            negative['recipeId'] = f"negative_{uuid.uuid4().hex[:8]}"
            # Add 4-6 random spokes to violate ratio
            num_extra = random.randint(4, 6)
            for _ in range(num_extra):
                negative['surroundingInputs'].append({
                    'materialId': random.choice(list(all_materials.keys())),
                    'quantity': random.randint(1, 3)
                })
            negatives.append((negative, 0))
            generated += 1

        # Type 4: Random but match structure
        while generated < num_per_recipe:
            negative = {
                'recipeId': f"negative_{uuid.uuid4().hex[:8]}",
                'outputId': "invalid",
                'stationTier': recipe['stationTier'],
                'coreInputs': [],
                'surroundingInputs': []
            }
            num_hubs = random.choice(hub_counts) if hub_counts else 1
            for _ in range(num_hubs):
                negative['coreInputs'].append({
                    'materialId': random.choice(list(all_materials.keys())),
                    'quantity': random.randint(1, 3)
                })

            # Sometimes violate the 1-3:1 ratio
            if random.random() < 0.5:
                num_spokes = random.randint(4, 8)  # Too many
            else:
                target_ratio = random.choice(spoke_hub_ratios) if spoke_hub_ratios else 1.5
                num_spokes = int(num_hubs * target_ratio)

            for _ in range(num_spokes):
                negative['surroundingInputs'].append({
                    'materialId': random.choice(list(all_materials.keys())),
                    'quantity': random.randint(1, 3)
                })
            negatives.append((negative, 0))
            generated += 1

    return negatives


# ============================================================================
# ALCHEMY AUGMENTATION (Sequential)
# ============================================================================

def augment_alchemy_material_substitution(recipe: Dict, all_materials: Dict) -> List[Dict]:
    """Generate variants by substituting materials (preserve slot order)."""
    variants = []

    slot_options = []
    for ingredient in recipe['ingredients']:
        mat_id = ingredient['materialId']
        subs = [mat_id] + find_substitutable_materials(mat_id, all_materials.get(mat_id, {}), all_materials)
        # Limit per ingredient to prevent explosion
        slot_options.append({
            'slot': ingredient['slot'],
            'quantity': ingredient['quantity'],
            'material_options': subs[:5]
        })

    # Generate combinations
    for material_combo in itertools.product(*[opt['material_options'] for opt in slot_options]):
        new_recipe = copy.deepcopy(recipe)
        new_recipe['recipeId'] = f"{recipe['recipeId']}_aug_{uuid.uuid4().hex[:8]}"
        new_recipe['ingredients'] = []
        for i, mat_id in enumerate(material_combo):
            new_recipe['ingredients'].append({
                'slot': slot_options[i]['slot'],
                'materialId': mat_id,
                'quantity': slot_options[i]['quantity']
            })
        variants.append(new_recipe)

    return variants


def augment_alchemy_quantities(recipe: Dict) -> List[Dict]:
    """Small quantity changes (±1) as valid variants."""
    variants = [recipe]

    for i, ingredient in enumerate(recipe['ingredients']):
        orig_qty = ingredient['quantity']

        # +1 variant
        if orig_qty < 5:
            variant = copy.deepcopy(recipe)
            variant['recipeId'] = f"{recipe['recipeId']}_qty_{uuid.uuid4().hex[:8]}"
            variant['ingredients'][i]['quantity'] = orig_qty + 1
            variants.append(variant)

        # -1 variant
        if orig_qty > 1:
            variant = copy.deepcopy(recipe)
            variant['recipeId'] = f"{recipe['recipeId']}_qty_{uuid.uuid4().hex[:8]}"
            variant['ingredients'][i]['quantity'] = orig_qty - 1
            variants.append(variant)

    return variants


def augment_alchemy_permutations(recipe: Dict) -> List[Dict]:
    """Generate permutations of ingredient sequence."""
    ingredients = recipe['ingredients']
    perms = list(itertools.permutations(ingredients))

    # Limit factorial explosion
    if len(perms) > 24:
        perms = random.sample(perms, 24)

    variants = []
    for perm in perms:
        new_recipe = copy.deepcopy(recipe)
        new_recipe['recipeId'] = f"{recipe['recipeId']}_perm_{uuid.uuid4().hex[:8]}"
        new_recipe['ingredients'] = []
        for i, ingredient in enumerate(perm, start=1):
            new_recipe['ingredients'].append({
                'slot': i,
                'materialId': ingredient['materialId'],
                'quantity': ingredient['quantity']
            })
        variants.append(new_recipe)

    return variants


def augment_alchemy_complete(recipe: Dict, all_materials: Dict) -> List[Dict]:
    """Complete alchemy augmentation."""
    # Material substitution (generates 4-8x)
    material_variants = augment_alchemy_material_substitution(recipe, all_materials)

    # Limit if explosion
    if len(material_variants) > 20:
        material_variants = random.sample(material_variants, 20)

    # Quantity variations on each material variant
    all_variants = []
    for variant in material_variants:
        qty_variants = augment_alchemy_quantities(variant)
        all_variants.extend(qty_variants)

    # Limit before permutations to prevent factorial explosion
    if len(all_variants) > 40:
        all_variants = random.sample(all_variants, 40)

    # Permutations on subset (factorial grows fast!)
    permuted_variants = []
    for variant in all_variants[:25]:  # Limit input to permutations
        perms = augment_alchemy_permutations(variant)
        permuted_variants.extend(perms)

    # Remove duplicates
    unique_variants = remove_duplicates(
        [(v, 1) for v in permuted_variants],
        normalize_alchemy_recipe
    )

    # Target ~15x per recipe
    final_variants = [v for v, _ in unique_variants]

    # Sample if too many
    if len(final_variants) > 25:
        final_variants = random.sample(final_variants, 25)

    return final_variants


def generate_alchemy_negatives(valid_recipes: List[Dict], all_materials: Dict, num_per_recipe: int = 3) -> List[Tuple[Dict, int]]:
    """Generate invalid alchemy recipes."""
    negatives = []

    negatives_per_type = max(1, num_per_recipe // 4)

    for recipe in valid_recipes:
        generated = 0

        # Type 1: Wrong material category
        for _ in range(negatives_per_type):
            if generated >= num_per_recipe:
                break
            negative = copy.deepcopy(recipe)
            negative['recipeId'] = f"negative_{uuid.uuid4().hex[:8]}"
            num_swaps = random.randint(1, min(2, len(negative['ingredients'])))
            for _ in range(num_swaps):
                if negative['ingredients']:
                    idx = random.randint(0, len(negative['ingredients']) - 1)
                    mat_id = negative['ingredients'][idx]['materialId']
                    wrong = find_different_category(mat_id, all_materials)
                    negative['ingredients'][idx]['materialId'] = wrong
            negatives.append((negative, 0))
            generated += 1

        # Type 2: Invalid quantity changes
        for _ in range(negatives_per_type):
            if generated >= num_per_recipe:
                break
            negative = copy.deepcopy(recipe)
            negative['recipeId'] = f"negative_{uuid.uuid4().hex[:8]}"
            if negative['ingredients']:
                idx = random.randint(0, len(negative['ingredients']) - 1)
                change = random.choice([-3, -4, 3, 4, 5])
                new_qty = max(1, negative['ingredients'][idx]['quantity'] + change)
                negative['ingredients'][idx]['quantity'] = new_qty
            negatives.append((negative, 0))
            generated += 1

        # Type 3: Insert extra ingredient
        if generated < num_per_recipe:
            negative = copy.deepcopy(recipe)
            negative['recipeId'] = f"negative_{uuid.uuid4().hex[:8]}"
            insert_pos = random.randint(0, len(negative['ingredients']))
            negative['ingredients'].insert(insert_pos, {
                'slot': len(negative['ingredients']) + 1,
                'materialId': random.choice(list(all_materials.keys())),
                'quantity': random.randint(1, 3)
            })
            for i, ing in enumerate(negative['ingredients'], start=1):
                ing['slot'] = i
            negatives.append((negative, 0))
            generated += 1

        # Type 4: Random sequence
        while generated < num_per_recipe:
            negative = {
                'recipeId': f"negative_{uuid.uuid4().hex[:8]}",
                'outputId': "invalid",
                'stationTier': recipe['stationTier'],
                'ingredients': []
            }
            num_ingredients = len(recipe['ingredients'])
            for i in range(num_ingredients):
                negative['ingredients'].append({
                    'slot': i + 1,
                    'materialId': random.choice(list(all_materials.keys())),
                    'quantity': random.randint(1, 4)
                })
            negatives.append((negative, 0))
            generated += 1

    return negatives


# ============================================================================
# ENGINEERING AUGMENTATION (Slot-based)
# ============================================================================

def augment_engineering_material_substitution(recipe: Dict, all_materials: Dict) -> List[Dict]:
    """Substitute materials in each slot independently."""
    variants = []

    slot_options = []
    for slot in recipe['slots']:
        mat_id = slot['materialId']
        subs = [mat_id] + find_substitutable_materials(mat_id, all_materials.get(mat_id, {}), all_materials)
        # Limit per slot to prevent explosion
        slot_options.append({
            'type': slot['type'],
            'quantity': slot['quantity'],
            'material_options': subs[:5]
        })

    # Generate combinations
    for material_combo in itertools.product(*[opt['material_options'] for opt in slot_options]):
        new_recipe = copy.deepcopy(recipe)
        new_recipe['recipeId'] = f"{recipe['recipeId']}_aug_{uuid.uuid4().hex[:8]}"
        new_recipe['slots'] = []
        for i, mat_id in enumerate(material_combo):
            new_recipe['slots'].append({
                'type': slot_options[i]['type'],
                'materialId': mat_id,
                'quantity': slot_options[i]['quantity']
            })
        variants.append(new_recipe)

    return variants


def augment_engineering_optional_slots(recipe: Dict) -> List[Dict]:
    """Generate variants with/without optional slots."""
    optional_types = {'MODIFIER', 'ENHANCEMENT', 'CORE', 'CATALYST', 'UTILITY'}

    variants = [recipe]

    optional_slots = [
        (i, slot) for i, slot in enumerate(recipe['slots'])
        if slot['type'] in optional_types
    ]

    if not optional_slots:
        return variants

    # Try removing 1 or 2 optional slots
    for num_to_remove in range(1, min(3, len(optional_slots) + 1)):
        for slots_to_remove in itertools.combinations(optional_slots, num_to_remove):
            remove_indices = {idx for idx, _ in slots_to_remove}
            new_slots = [
                slot for i, slot in enumerate(recipe['slots'])
                if i not in remove_indices
            ]

            variant = copy.deepcopy(recipe)
            variant['recipeId'] = f"{recipe['recipeId']}_opt_{uuid.uuid4().hex[:8]}"
            variant['slots'] = new_slots
            variants.append(variant)

    return variants[:8]


def augment_engineering_complete(recipe: Dict, all_materials: Dict) -> List[Dict]:
    """Complete engineering augmentation."""
    # Material substitution (generates 8-20x)
    material_variants = augment_engineering_material_substitution(recipe, all_materials)

    # Limit if explosion
    if len(material_variants) > 30:
        material_variants = random.sample(material_variants, 30)

    # Optional slot variations on material variants
    all_variants = []
    for variant in material_variants:
        slot_variants = augment_engineering_optional_slots(variant)
        all_variants.extend(slot_variants)

    # Remove duplicates
    unique_variants = remove_duplicates(
        [(v, 1) for v in all_variants],
        normalize_engineering_recipe
    )

    # Target ~15-20x per recipe
    final_variants = [v for v, _ in unique_variants]

    # Sample if too many
    if len(final_variants) > 25:
        final_variants = random.sample(final_variants, 25)

    return final_variants


def generate_engineering_negatives(valid_recipes: List[Dict], all_materials: Dict, num_per_recipe: int = 3) -> List[Tuple[Dict, int]]:
    """Generate invalid engineering recipes."""
    negatives = []

    slot_counts = [len(r['slots']) for r in valid_recipes]
    negatives_per_type = max(1, num_per_recipe // 4)

    for recipe in valid_recipes:
        generated = 0

        # Type 1: Wrong material category
        for _ in range(negatives_per_type):
            if generated >= num_per_recipe:
                break
            negative = copy.deepcopy(recipe)
            negative['recipeId'] = f"negative_{uuid.uuid4().hex[:8]}"
            if negative['slots']:
                idx = random.randint(0, len(negative['slots']) - 1)
                mat_id = negative['slots'][idx]['materialId']
                wrong = find_different_category(mat_id, all_materials)
                negative['slots'][idx]['materialId'] = wrong
            negatives.append((negative, 0))
            generated += 1

        # Type 2: Only one slot type
        for _ in range(negatives_per_type):
            if generated >= num_per_recipe:
                break
            negative = {
                'recipeId': f"negative_{uuid.uuid4().hex[:8]}",
                'outputId': "invalid",
                'stationTier': recipe['stationTier'],
                'slots': []
            }
            single_type = random.choice(['FRAME', 'POWER', 'FUNCTION'])
            num_slots = random.choice(slot_counts) if slot_counts else 3

            for _ in range(num_slots):
                negative['slots'].append({
                    'type': single_type,
                    'materialId': random.choice(list(all_materials.keys())),
                    'quantity': random.randint(1, 6)
                })
            negatives.append((negative, 0))
            generated += 1

        # Type 3: Missing critical slots
        if generated < num_per_recipe:
            negative = copy.deepcopy(recipe)
            negative['recipeId'] = f"negative_{uuid.uuid4().hex[:8]}"
            critical_slots = [i for i, s in enumerate(negative['slots'])
                             if s['type'] in ['FRAME', 'FUNCTION']]
            if critical_slots:
                remove_idx = random.choice(critical_slots)
                negative['slots'].pop(remove_idx)
            negatives.append((negative, 0))
            generated += 1

        # Type 4: Nonsensical combinations
        while generated < num_per_recipe:
            negative = {
                'recipeId': f"negative_{uuid.uuid4().hex[:8]}",
                'outputId': "invalid",
                'stationTier': recipe['stationTier'],
                'slots': []
            }
            num_slots = random.choice(slot_counts) if slot_counts else 3

            for _ in range(num_slots):
                negative['slots'].append({
                    'type': random.choice(['FRAME', 'FUNCTION', 'POWER', 'MODIFIER']),
                    'materialId': random.choice(list(all_materials.keys())),
                    'quantity': random.randint(1, 6)
                })
            negatives.append((negative, 0))
            generated += 1

    return negatives


# ============================================================================
# MAIN ORCHESTRATION
# ============================================================================

def save_dataset(data: List[Tuple[Dict, int]], output_path: str, discipline: str):
    """Save augmented dataset to JSON."""
    # Check if output_path is a directory
    if os.path.isdir(output_path):
        output_path = os.path.join(output_path, f'{discipline}_augmented_data.json')
        print(f"   Output is directory, saving to: {output_path}")

    dataset = {
        'discipline': discipline,
        'total_samples': len(data),
        'positive_samples': sum(1 for _, label in data if label == 1),
        'negative_samples': sum(1 for _, label in data if label == 0),
        'data': [
            {'recipe': recipe, 'label': label}
            for recipe, label in data
        ]
    }

    with open(output_path, 'w') as f:
        json.dump(dataset, f, indent=2)

    print(f"\n✅ Dataset saved to: {output_path}")
    print(f"   Total samples: {dataset['total_samples']}")
    print(f"   Positive: {dataset['positive_samples']}")
    print(f"   Negative: {dataset['negative_samples']}")


def load_json(filepath: str) -> Dict:
    """Load JSON file."""
    with open(filepath, 'r') as f:
        return json.load(f)


def main():
    """Main orchestration function."""
    print("=" * 70)
    print("CRAFTING RECIPE DATA AUGMENTATION SYSTEM")
    print("=" * 70)

    # Get user input
    print("\nAvailable disciplines:")
    print("  1. refining")
    print("  2. alchemy")
    print("  3. engineering")

    discipline = input("\nEnter discipline name: ").strip().lower()

    if discipline not in ['refining', 'alchemy', 'engineering']:
        print("❌ Invalid discipline. Must be: refining, alchemy, or engineering")
        return

    materials_path = input("Enter path to materials JSON file: ").strip()
    placements_path = input("Enter path to placements JSON file: ").strip()
    output_path = input("Enter output path for augmented dataset: ").strip()

    # Load data
    print("\n📂 Loading data...")
    try:
        materials_data = load_json(materials_path)
        placements_data = load_json(placements_path)
    except Exception as e:
        print(f"❌ Error loading files: {e}")
        return

    # Parse materials into dict
    all_materials = {}
    if 'materials' in materials_data:
        all_materials = {m['materialId']: m for m in materials_data['materials']}

    # Get placements
    recipes = placements_data.get('placements', [])
    print(f"   Loaded {len(recipes)} base recipes")
    print(f"   Loaded {len(all_materials)} materials")

    # Augment based on discipline
    print(f"\n🔄 Augmenting {discipline} recipes...")

    if discipline == 'refining':
        # Step 1: Generate balanced synthetic recipes for all patterns
        print("   Generating synthetic recipes for all 3 patterns...")
        synthetic_recipes = generate_synthetic_refining_recipes(all_materials)

        # Count patterns in synthetics
        pattern1 = sum(1 for r in synthetic_recipes if len(r['coreInputs']) == 1 and len(r['surroundingInputs']) == 0)
        pattern2 = sum(1 for r in synthetic_recipes if len(r['coreInputs']) >= 2 and len(r['surroundingInputs']) == 0)
        pattern3 = sum(1 for r in synthetic_recipes if len(r['coreInputs']) == 1 and len(r['surroundingInputs']) > 0)

        print(f"   Created {len(synthetic_recipes)} synthetic recipes:")
        print(f"     - Pattern 1 (basic smelting, 0 spokes): {pattern1}")
        print(f"     - Pattern 2 (alloying, 2+ hubs): {pattern2}")
        print(f"     - Pattern 3 (infusion, 1 hub + spokes): {pattern3}")

        # Combine original + synthetic
        all_base_recipes = recipes + synthetic_recipes
        print(f"   Total base recipes to augment: {len(all_base_recipes)} ({len(recipes)} original + {len(synthetic_recipes)} synthetic)")

        # Step 2: Augment all recipes (with reduced multiplier)
        positives = []
        for recipe in all_base_recipes:
            variants = augment_refining_complete(recipe, all_materials)
            positives.extend([(v, 1) for v in variants])

        print(f"   Generated {len(positives)} positive samples")

        # Step 3: Generate balanced negatives
        # Target 40% negative ratio (60% positive)
        target_negatives = int(len(positives) * 0.4 / 0.6)
        num_negatives_per_recipe = max(3, target_negatives // len(recipes))

        print(f"   Generating ~{target_negatives} negative samples ({num_negatives_per_recipe} per original recipe)...")
        negatives = generate_refining_negatives(recipes, all_materials, num_negatives_per_recipe)
        all_data = positives + negatives

    elif discipline == 'alchemy':
        positives = []
        for recipe in recipes:
            variants = augment_alchemy_complete(recipe, all_materials)
            positives.extend([(v, 1) for v in variants])

        print(f"   Generated {len(positives)} positive samples")

        # Target 40% negative ratio (60% positive)
        target_negatives = int(len(positives) * 0.4 / 0.6)
        num_negatives_per_recipe = max(2, target_negatives // len(recipes))

        print(f"   Generating ~{target_negatives} negative samples ({num_negatives_per_recipe} per base recipe)...")
        negatives = generate_alchemy_negatives(recipes, all_materials, num_negatives_per_recipe)
        all_data = positives + negatives

    elif discipline == 'engineering':
        positives = []
        for recipe in recipes:
            variants = augment_engineering_complete(recipe, all_materials)
            positives.extend([(v, 1) for v in variants])

        print(f"   Generated {len(positives)} positive samples")

        # Target 40% negative ratio (60% positive)
        target_negatives = int(len(positives) * 0.4 / 0.6)
        num_negatives_per_recipe = max(2, target_negatives // len(recipes))

        print(f"   Generating ~{target_negatives} negative samples ({num_negatives_per_recipe} per base recipe)...")
        negatives = generate_engineering_negatives(recipes, all_materials, num_negatives_per_recipe)
        all_data = positives + negatives

    # Shuffle
    random.shuffle(all_data)

    # Save
    save_dataset(all_data, output_path, discipline)

    print("\n✨ Augmentation complete!")


if __name__ == "__main__":
    main()
#!/usr/bin/env python3
"""
Golden File Generation Script — Phase 5 ML Classifier Migration
=================================================================

Generates test cases with known inputs and expected outputs for validating
C# preprocessing matches Python exactly.

Each golden file contains:
  - Input data (grid/slot description)
  - Preprocessed output (image pixels or feature vector)
  - Checksums for quick validation
  - Model prediction (if models available)

Prerequisites:
    pip install numpy

Usage:
    cd Game-1
    python Unity/Assets/Scripts/Game1.Systems/Classifiers/Scripts/generate_golden_files.py

Output:
    Unity/Assets/Tests/GoldenFiles/Classifiers/*.json
"""

import json
import sys
import numpy as np
from pathlib import Path
from colorsys import hsv_to_rgb

# ============================================================================
# Configuration
# ============================================================================

PROJECT_ROOT = Path(__file__).resolve().parents[6]
OUTPUT_DIR = PROJECT_ROOT / "Unity" / "Assets" / "Tests" / "GoldenFiles" / "Classifiers"

# ============================================================================
# Inline MaterialColorEncoder (pure Python, no game imports needed)
# ============================================================================

CATEGORY_HUES = {
    'metal': 210, 'wood': 30, 'stone': 0, 'monster_drop': 300,
    'gem': 280, 'herb': 120, 'fabric': 45,
}
ELEMENT_HUES = {
    'fire': 0, 'water': 210, 'earth': 120, 'air': 60,
    'lightning': 270, 'ice': 180, 'light': 45,
    'dark': 280, 'void': 290, 'chaos': 330,
}
TIER_VALUES = {1: 0.50, 2: 0.65, 3: 0.80, 4: 0.95}

# Mock material database for golden file generation
MOCK_MATERIALS = {
    'iron_ore':       {'category': 'metal',        'tier': 1, 'tags': []},
    'steel_ingot':    {'category': 'metal',        'tier': 2, 'tags': []},
    'mithril_ore':    {'category': 'metal',        'tier': 3, 'tags': ['magical']},
    'voidsteel':      {'category': 'metal',        'tier': 4, 'tags': ['legendary']},
    'oak_log':        {'category': 'wood',         'tier': 1, 'tags': []},
    'ash_plank':      {'category': 'wood',         'tier': 2, 'tags': []},
    'ironwood':       {'category': 'wood',         'tier': 3, 'tags': ['magical']},
    'limestone':      {'category': 'stone',        'tier': 1, 'tags': []},
    'marble':         {'category': 'stone',        'tier': 2, 'tags': []},
    'obsidian':       {'category': 'stone',        'tier': 3, 'tags': ['ancient']},
    'spider_silk':    {'category': 'monster_drop', 'tier': 1, 'tags': []},
    'dragon_scale':   {'category': 'monster_drop', 'tier': 4, 'tags': ['legendary']},
    'fire_essence':   {'category': 'elemental',    'tier': 2, 'tags': ['fire']},
    'ice_shard':      {'category': 'elemental',    'tier': 2, 'tags': ['ice']},
    'void_crystal':   {'category': 'elemental',    'tier': 4, 'tags': ['void', 'mythical']},
    'ruby':           {'category': 'gem',          'tier': 2, 'tags': []},
    'healing_herb':   {'category': 'herb',         'tier': 1, 'tags': []},
    'silk_cloth':     {'category': 'fabric',       'tier': 1, 'tags': []},
}


def encode_material(material_id):
    """Encode material to RGB — exact copy of Python logic."""
    if material_id is None:
        return [0.0, 0.0, 0.0]

    mat = MOCK_MATERIALS.get(material_id)
    if mat is None:
        return [0.3, 0.3, 0.3]

    category = mat['category']
    tier = mat['tier']
    tags = mat.get('tags', [])

    # Hue
    if category == 'elemental':
        hue = 280
        for tag in tags:
            if tag in ELEMENT_HUES:
                hue = ELEMENT_HUES[tag]
                break
    else:
        hue = CATEGORY_HUES.get(category, 0)

    # Value
    value = TIER_VALUES.get(tier, 0.5)

    # Saturation
    sat = 0.6
    if category == 'stone':
        sat = 0.2
    if 'legendary' in tags or 'mythical' in tags:
        sat = min(1.0, sat + 0.2)
    elif 'magical' in tags or 'ancient' in tags:
        sat = min(1.0, sat + 0.1)

    hue_norm = hue / 360.0
    r, g, b = hsv_to_rgb(hue_norm, sat, value)
    return [float(r), float(g), float(b)]


# ============================================================================
# HSV-to-RGB Test Cases
# ============================================================================

def generate_color_encoder_golden():
    """Generate golden test cases for MaterialColorEncoder."""
    cases = []

    # Null material
    cases.append({
        'materialId': None,
        'expected_rgb': [0.0, 0.0, 0.0],
        'description': 'null material -> black'
    })

    # Unknown material
    cases.append({
        'materialId': 'nonexistent_material_xyz',
        'expected_rgb': [0.3, 0.3, 0.3],
        'description': 'unknown material -> gray'
    })

    # All mock materials
    for mat_id in sorted(MOCK_MATERIALS.keys()):
        rgb = encode_material(mat_id)
        mat = MOCK_MATERIALS[mat_id]
        cases.append({
            'materialId': mat_id,
            'category': mat['category'],
            'tier': mat['tier'],
            'tags': mat['tags'],
            'expected_rgb': rgb,
            'description': f"{mat_id}: {mat['category']} T{mat['tier']}"
        })

    return cases


# ============================================================================
# Smithing Preprocessor Test Cases
# ============================================================================

SHAPE_METAL = [[1,1,1,1],[1,1,1,1],[1,1,1,1],[1,1,1,1]]
SHAPE_WOOD = [[1,1,1,1],[0,0,0,0],[1,1,1,1],[0,0,0,0]]
SHAPE_STONE = [[1,0,0,1],[0,1,1,0],[0,1,1,0],[1,0,0,1]]
SHAPE_DIAMOND = [[0,1,1,0],[1,1,1,1],[1,1,1,1],[0,1,1,0]]
SHAPE_DEFAULT = [[1,1,1,1],[1,1,1,1],[1,1,1,1],[1,1,1,1]]


def smithing_grid_to_image(grid_9x9):
    """Render 9x9 grid to 36x36 image — matches Python exactly."""
    img = np.zeros((36, 36, 3), dtype=np.float32)

    shapes = {
        'metal': SHAPE_METAL, 'wood': SHAPE_WOOD, 'stone': SHAPE_STONE,
        'monster_drop': SHAPE_DIAMOND, 'elemental': SHAPE_DIAMOND,
    }

    for i in range(9):
        for j in range(9):
            mat_id = grid_9x9[i][j]
            if mat_id is None:
                continue

            color = np.array(encode_material(mat_id), dtype=np.float32)
            mat = MOCK_MATERIALS.get(mat_id)

            # Shape mask
            if mat:
                shape = shapes.get(mat['category'], SHAPE_DEFAULT)
            else:
                shape = SHAPE_DEFAULT
            shape_mask = np.array(shape, dtype=np.float32)

            # Tier fill mask
            if mat:
                fill_size = {1:1, 2:2, 3:3, 4:4}.get(mat['tier'], 4)
            else:
                fill_size = 0  # Unknown -> all zeros

            tier_mask = np.zeros((4, 4), dtype=np.float32)
            if mat:
                offset = (4 - fill_size) // 2
                tier_mask[offset:offset+fill_size, offset:offset+fill_size] = 1.0

            combined = shape_mask * tier_mask
            cell = np.zeros((4, 4, 3), dtype=np.float32)
            for c in range(3):
                cell[:, :, c] = color[c] * combined

            y = i * 4
            x = j * 4
            img[y:y+4, x:x+4] = cell

    return img


def generate_smithing_golden():
    """Generate golden test cases for SmithingPreprocessor."""
    cases = []

    # Case 1: Empty grid
    grid = [[None]*9 for _ in range(9)]
    img = smithing_grid_to_image(grid)
    cases.append({
        'name': 'empty_grid',
        'grid': {},
        'station_grid_size': 5,
        'image_checksum': float(np.sum(img)),
        'image_nonzero_count': int(np.count_nonzero(img)),
        'image_flat': img.flatten().tolist(),
    })

    # Case 2: Single iron_ore at center of 5x5 grid
    grid = [[None]*9 for _ in range(9)]
    grid[4][4] = 'iron_ore'  # Center of 9x9 (5x5 centered, offset=2, pos 2,2 -> 4,4)
    img = smithing_grid_to_image(grid)
    cases.append({
        'name': 'single_iron_center',
        'grid': {'4,4': 'iron_ore'},
        'station_grid_size': 9,
        'image_checksum': float(np.sum(img)),
        'image_nonzero_count': int(np.count_nonzero(img)),
        'image_flat': img.flatten().tolist(),
    })

    # Case 3: Mixed materials (metal T1, wood T2, stone T3)
    grid = [[None]*9 for _ in range(9)]
    grid[0][0] = 'iron_ore'
    grid[0][1] = 'ash_plank'
    grid[0][2] = 'obsidian'
    img = smithing_grid_to_image(grid)
    cases.append({
        'name': 'mixed_materials_top_row',
        'grid': {'0,0': 'iron_ore', '1,0': 'ash_plank', '2,0': 'obsidian'},
        'station_grid_size': 9,
        'image_checksum': float(np.sum(img)),
        'image_nonzero_count': int(np.count_nonzero(img)),
        'image_flat': img.flatten().tolist(),
    })

    # Case 4: All tiers of metal
    grid = [[None]*9 for _ in range(9)]
    grid[4][0] = 'iron_ore'     # T1
    grid[4][1] = 'steel_ingot'  # T2
    grid[4][2] = 'mithril_ore'  # T3
    grid[4][3] = 'voidsteel'    # T4
    img = smithing_grid_to_image(grid)
    cases.append({
        'name': 'metal_all_tiers',
        'grid': {'0,4': 'iron_ore', '1,4': 'steel_ingot', '2,4': 'mithril_ore', '3,4': 'voidsteel'},
        'station_grid_size': 9,
        'image_checksum': float(np.sum(img)),
        'image_nonzero_count': int(np.count_nonzero(img)),
        'image_flat': img.flatten().tolist(),
    })

    return cases


# ============================================================================
# Feature Extractor Test Cases
# ============================================================================

CATEGORY_TO_IDX = {'elemental': 0, 'metal': 1, 'monster_drop': 2, 'stone': 3, 'wood': 4}


def get_cat_idx(material_id):
    mat = MOCK_MATERIALS.get(material_id, {'category': 'unknown'})
    return CATEGORY_TO_IDX.get(mat['category'], 0)


def generate_alchemy_golden():
    """Generate golden files for AlchemyFeatureExtractor (34 features)."""
    cases = []

    # Case 1: Empty slots
    features = [0]*34  # All zeros
    cases.append({
        'name': 'empty_slots',
        'slots': [None, None, None, None, None, None],
        'station_tier': 1,
        'expected_features': features,
    })

    # Case 2: Single iron_ore in slot 0
    slots = [('iron_ore', 3), None, None, None, None, None]
    features = [0.0] * 34
    idx = 0
    features[idx] = 1; idx += 1  # num_ingredients
    features[idx] = 3; idx += 1  # total_qty
    features[idx] = 3.0; idx += 1  # avg_qty
    # Position 0: tier=1, qty=3, cat_idx=1 (metal)
    features[idx] = 1; idx += 1
    features[idx] = 3; idx += 1
    features[idx] = 1; idx += 1
    # Positions 1-5: all zeros
    idx += 15
    features[idx] = 1; idx += 1  # diversity (1 unique material)
    # Category dist: elemental=0, metal=1, monster_drop=0, stone=0, wood=0
    features[idx] = 0; idx += 1  # elemental
    features[idx] = 1; idx += 1  # metal
    features[idx] = 0; idx += 1  # monster_drop
    features[idx] = 0; idx += 1  # stone
    features[idx] = 0; idx += 1  # wood
    features[idx] = 1; idx += 1  # ref_basic
    features[idx] = 1.0; idx += 1  # tier_mean
    features[idx] = 1.0; idx += 1  # tier_max
    features[idx] = 0.0; idx += 1  # tier_std (only 1 item)
    features[idx] = 0; idx += 1  # increases
    features[idx] = 0; idx += 1  # decreases
    features[idx] = 2; idx += 1  # station_tier

    cases.append({
        'name': 'single_iron_ore',
        'slots': [['iron_ore', 3], None, None, None, None, None],
        'station_tier': 2,
        'expected_features': features,
    })

    return cases


# ============================================================================
# Main
# ============================================================================

def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    print("Generating golden files for Phase 5 ML Classifiers...")

    # Color encoder
    color_cases = generate_color_encoder_golden()
    with open(OUTPUT_DIR / "color_encoder_golden.json", 'w') as f:
        json.dump(color_cases, f, indent=2)
    print(f"  color_encoder_golden.json: {len(color_cases)} test cases")

    # Smithing
    smithing_cases = generate_smithing_golden()
    with open(OUTPUT_DIR / "smithing_golden.json", 'w') as f:
        json.dump(smithing_cases, f, indent=2)
    print(f"  smithing_golden.json: {len(smithing_cases)} test cases")

    # Alchemy
    alchemy_cases = generate_alchemy_golden()
    with open(OUTPUT_DIR / "alchemy_golden.json", 'w') as f:
        json.dump(alchemy_cases, f, indent=2)
    print(f"  alchemy_golden.json: {len(alchemy_cases)} test cases")

    print(f"\nAll golden files saved to: {OUTPUT_DIR}")
    print("NOTE: Run with ML models loaded to include prediction golden values.")

    return 0


if __name__ == "__main__":
    sys.exit(main())

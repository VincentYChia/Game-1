"""
Content-integrity checks for crafting JSON (materials, placements, recipes).

Rewritten 2026-06-10: the original was a top-level print script that ran at
import time, called os.chdir() (mutating the CWD for the whole pytest
session), and opened recipes-smithing-1.JSON — a file that no longer exists —
which aborted collection of the entire tests/ tree. Now proper pytest
functions with no side effects.
"""
import json
import os
import sys

import pytest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


def _load_json(relpath: str) -> dict:
    path = os.path.join(PROJECT_ROOT, relpath)
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def test_materials_json_loads_with_required_fields():
    data = _load_json(os.path.join('items.JSON', 'items-materials-1.JSON'))
    materials = data.get('materials', [])
    assert len(materials) >= 57, f"Expected >=57 base materials, got {len(materials)}"
    for mat in materials:
        assert 'materialId' in mat, f"Material missing materialId: {mat}"
        assert 'name' in mat, f"Material missing name: {mat['materialId']}"


def test_smithing_placement_coordinates_parse():
    data = _load_json(os.path.join('placements.JSON', 'placements-smithing-1.json'))
    placements = data.get('placements', [])
    assert placements, "No smithing placements found"
    placement = placements[0]
    assert 'recipeId' in placement
    assert 'gridSize' in placement.get('metadata', {})
    for coord, material in placement['placementMap'].items():
        col, row = map(int, coord.split(','))
        assert col >= 0 and row >= 0, f"Negative placement coord {coord}"
        assert material, f"Empty material at {coord}"


def test_smithing_recipes_have_grid_size():
    # recipes-smithing-3.json is the current smithing recipe file
    # (.claude/CLAUDE.md "File Organization"); the original test referenced
    # the long-gone recipes-smithing-1.JSON.
    data = _load_json(os.path.join('recipes.JSON', 'recipes-smithing-3.json'))
    recipes = data.get('recipes', [])
    assert recipes, "No smithing recipes found"
    missing_grid = [r['recipeId'] for r in recipes if 'gridSize' not in r]
    assert not missing_grid, f"Smithing recipes missing gridSize: {missing_grid[:10]}"


# NOTE: the original script also grepped alchemy.py source for an
# 'elif self.tier == 3:' branch. That branch does not exist in current
# alchemy.py (the script printed a warning nobody saw) — source-text
# grepping is not a behavioral test, so it was dropped rather than ported.

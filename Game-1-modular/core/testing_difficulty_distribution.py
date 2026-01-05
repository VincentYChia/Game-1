"""
Difficulty Distribution Analysis Script

Analyzes all recipes across all disciplines to determine
if difficulty is well-distributed across the tiers.

Run: python -m core.testing_difficulty_distribution
"""

import json
import os
from pathlib import Path
from collections import defaultdict
from typing import Dict, List, Tuple

# Import difficulty calculators
try:
    from difficulty_calculator import (
        calculate_material_points,
        get_difficulty_tier,
        calculate_smithing_difficulty,
        calculate_refining_difficulty,
        calculate_alchemy_difficulty,
        calculate_engineering_difficulty,
        calculate_enchanting_difficulty,
        DIFFICULTY_THRESHOLDS
    )
except ImportError:
    from core.difficulty_calculator import (
        calculate_material_points,
        get_difficulty_tier,
        calculate_smithing_difficulty,
        calculate_refining_difficulty,
        calculate_alchemy_difficulty,
        calculate_engineering_difficulty,
        calculate_enchanting_difficulty,
        DIFFICULTY_THRESHOLDS
    )


def find_recipe_files() -> Dict[str, List[Path]]:
    """Find all recipe JSON files organized by discipline."""
    base_paths = [
        Path("recipes.JSON"),
        Path("../recipes.JSON"),
        Path("Game-1-modular/recipes.JSON"),
    ]

    recipe_files = {
        'smithing': [],
        'refining': [],
        'alchemy': [],
        'engineering': [],
        'enchanting': [],
    }

    for base_path in base_paths:
        if not base_path.exists():
            continue

        for f in base_path.glob("*.json"):
            name = f.name.lower()
            if 'smithing' in name:
                recipe_files['smithing'].append(f)
            elif 'refining' in name:
                recipe_files['refining'].append(f)
            elif 'alchemy' in name:
                recipe_files['alchemy'].append(f)
            elif 'engineering' in name:
                recipe_files['engineering'].append(f)
            elif 'enchanting' in name or 'adornment' in name:
                recipe_files['enchanting'].append(f)

    return recipe_files


def load_recipes(file_path: Path) -> List[Dict]:
    """Load recipes from a JSON file."""
    try:
        with open(file_path, 'r') as f:
            data = json.load(f)
            return data.get('recipes', [])
    except Exception as e:
        print(f"Error loading {file_path}: {e}")
        return []


def analyze_discipline(discipline: str, files: List[Path]) -> Dict:
    """Analyze difficulty distribution for a discipline."""
    all_recipes = []
    for f in files:
        all_recipes.extend(load_recipes(f))

    if not all_recipes:
        return {'error': f'No recipes found for {discipline}'}

    # Map discipline to calculator function
    calculators = {
        'smithing': calculate_smithing_difficulty,
        'refining': calculate_refining_difficulty,
        'alchemy': calculate_alchemy_difficulty,
        'engineering': calculate_engineering_difficulty,
        'enchanting': calculate_enchanting_difficulty,
    }

    calc_func = calculators.get(discipline, calculate_material_points)

    # Analyze each recipe
    results = []
    tier_counts = defaultdict(int)
    difficulty_points_list = []

    for recipe in all_recipes:
        try:
            if discipline in ('smithing', 'refining', 'alchemy', 'engineering', 'enchanting'):
                params = calc_func(recipe)
                diff_points = params.get('difficulty_points', 0)
                diff_tier = params.get('difficulty_tier', 'common')
            else:
                inputs = recipe.get('inputs', [])
                diff_points = calculate_material_points(inputs)
                diff_tier = get_difficulty_tier(diff_points)

            tier_counts[diff_tier] += 1
            difficulty_points_list.append(diff_points)

            results.append({
                'recipe_id': recipe.get('recipeId', 'unknown'),
                'output_id': recipe.get('outputId', recipe.get('enchantmentId', 'unknown')),
                'difficulty_points': diff_points,
                'difficulty_tier': diff_tier,
            })
        except Exception as e:
            print(f"  Error processing recipe {recipe.get('recipeId', 'unknown')}: {e}")

    # Calculate statistics
    if difficulty_points_list:
        min_pts = min(difficulty_points_list)
        max_pts = max(difficulty_points_list)
        avg_pts = sum(difficulty_points_list) / len(difficulty_points_list)

        # Calculate percentile distribution
        sorted_pts = sorted(difficulty_points_list)
        p25 = sorted_pts[len(sorted_pts) // 4] if len(sorted_pts) >= 4 else sorted_pts[0]
        p50 = sorted_pts[len(sorted_pts) // 2]
        p75 = sorted_pts[3 * len(sorted_pts) // 4] if len(sorted_pts) >= 4 else sorted_pts[-1]
    else:
        min_pts = max_pts = avg_pts = p25 = p50 = p75 = 0

    return {
        'discipline': discipline,
        'total_recipes': len(results),
        'tier_distribution': dict(tier_counts),
        'stats': {
            'min': min_pts,
            'max': max_pts,
            'avg': avg_pts,
            'p25': p25,
            'p50_median': p50,
            'p75': p75,
        },
        'recipes': results,
    }


def print_report(analysis: Dict):
    """Print a formatted report for a discipline."""
    if 'error' in analysis:
        print(f"\n{analysis['error']}")
        return

    print(f"\n{'='*60}")
    print(f"DISCIPLINE: {analysis['discipline'].upper()}")
    print(f"{'='*60}")
    print(f"Total Recipes: {analysis['total_recipes']}")

    # Tier distribution
    print(f"\nDifficulty Tier Distribution:")
    total = analysis['total_recipes']
    tier_order = ['common', 'uncommon', 'rare', 'epic', 'legendary']
    for tier in tier_order:
        count = analysis['tier_distribution'].get(tier, 0)
        pct = (count / total * 100) if total > 0 else 0
        bar = '#' * int(pct / 2)
        print(f"  {tier:12}: {count:3} ({pct:5.1f}%) {bar}")

    # Point statistics
    stats = analysis['stats']
    print(f"\nDifficulty Points Statistics:")
    print(f"  Min:    {stats['min']:6.1f}")
    print(f"  25th%:  {stats['p25']:6.1f}")
    print(f"  Median: {stats['p50_median']:6.1f}")
    print(f"  75th%:  {stats['p75']:6.1f}")
    print(f"  Max:    {stats['max']:6.1f}")
    print(f"  Avg:    {stats['avg']:6.1f}")

    # Show threshold ranges for context
    print(f"\nDifficulty Thresholds (reference):")
    for tier, (low, high) in DIFFICULTY_THRESHOLDS.items():
        print(f"  {tier:12}: {low:3} - {high:3}")

    # Concentration warning
    tier_dist = analysis['tier_distribution']
    if tier_dist.get('common', 0) / total > 0.5:
        print(f"\n  WARNING: {tier_dist['common']/total*100:.0f}% of recipes are in 'common' tier!")

    # Show some example recipes
    print(f"\nSample Recipes (sorted by difficulty):")
    sorted_recipes = sorted(analysis['recipes'], key=lambda x: x['difficulty_points'])

    # Show lowest, middle, and highest
    samples = []
    if len(sorted_recipes) >= 3:
        samples = [
            sorted_recipes[0],
            sorted_recipes[len(sorted_recipes)//2],
            sorted_recipes[-1],
        ]
    else:
        samples = sorted_recipes

    for r in samples:
        print(f"  {r['output_id']:30} | {r['difficulty_points']:5.1f} pts | {r['difficulty_tier']}")


def main():
    print("="*60)
    print("CRAFTING DIFFICULTY DISTRIBUTION ANALYSIS")
    print("="*60)

    # Find recipe files
    recipe_files = find_recipe_files()

    # Check if any found
    total_files = sum(len(files) for files in recipe_files.values())
    if total_files == 0:
        print("\nNo recipe files found. Make sure you're running from the correct directory.")
        print("Expected path: recipes.JSON/ or Game-1-modular/recipes.JSON/")
        return

    print(f"\nFound {total_files} recipe files:")
    for discipline, files in recipe_files.items():
        print(f"  {discipline}: {len(files)} files")

    # Analyze each discipline
    all_analyses = {}
    for discipline, files in recipe_files.items():
        if files:
            analysis = analyze_discipline(discipline, files)
            all_analyses[discipline] = analysis
            print_report(analysis)

    # Overall summary
    print(f"\n{'='*60}")
    print("OVERALL SUMMARY")
    print(f"{'='*60}")

    total_recipes = sum(a.get('total_recipes', 0) for a in all_analyses.values() if 'error' not in a)
    all_tiers = defaultdict(int)
    for a in all_analyses.values():
        if 'error' not in a:
            for tier, count in a.get('tier_distribution', {}).items():
                all_tiers[tier] += count

    print(f"\nTotal Recipes Analyzed: {total_recipes}")
    print(f"\nOverall Tier Distribution:")
    tier_order = ['common', 'uncommon', 'rare', 'epic', 'legendary']
    for tier in tier_order:
        count = all_tiers.get(tier, 0)
        pct = (count / total_recipes * 100) if total_recipes > 0 else 0
        bar = '#' * int(pct / 2)
        print(f"  {tier:12}: {count:3} ({pct:5.1f}%) {bar}")

    # Recommendations
    print(f"\n{'='*60}")
    print("RECOMMENDATIONS")
    print(f"{'='*60}")

    common_pct = all_tiers.get('common', 0) / total_recipes * 100 if total_recipes > 0 else 0
    if common_pct > 60:
        print(f"\n! HIGH CONCENTRATION IN 'COMMON': {common_pct:.0f}% of all recipes")
        print("  Consider:")
        print("  1. Lowering DIFFICULTY_THRESHOLDS['common'] upper bound")
        print("  2. Increasing tier points or diversity multipliers")
        print("  3. Adding more high-tier materials to recipes")

    legendary_count = all_tiers.get('legendary', 0)
    if legendary_count == 0:
        print(f"\n! NO LEGENDARY RECIPES")
        print("  Consider:")
        print("  1. Adding recipes with high-tier materials")
        print("  2. Lowering DIFFICULTY_THRESHOLDS['legendary'] lower bound")

    print("\n")


if __name__ == "__main__":
    main()

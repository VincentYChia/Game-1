"""
Systematic test script to verify all fixes
"""
import json
import os
import sys

# Add Game-1-modular to path and set working directory
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)
os.chdir(project_root)  # Change to project root for relative JSON paths

print("=" * 80)
print("TESTING MATERIAL INVENTORY")
print("=" * 80)

# Load actual materials from JSON
with open('items.JSON/items-materials-1.JSON', 'r') as f:
    data = json.load(f)
    materials_list = data.get('materials', [])

print(f"\nFound {len(materials_list)} materials in items-materials-1.JSON")
print("\nFirst 10 materials:")
for i, mat in enumerate(materials_list[:10]):
    print(f"  {i+1}. {mat['materialId']} - {mat['name']}")

print("\n" + "=" * 80)
print("TESTING SMITHING PLACEMENT COORDINATES")
print("=" * 80)

with open('placements.JSON/placements-smithing-1.JSON', 'r') as f:
    data = json.load(f)
    placements = data.get('placements', [])

# Test first placement
test_placement = placements[0]
print(f"\nTest recipe: {test_placement['recipeId']}")
print(f"Grid size: {test_placement['metadata']['gridSize']}")
print(f"\nPlacement map:")
for coord, material in test_placement['placementMap'].items():
    col, row = map(int, coord.split(','))
    print(f"  Position ({col},{row}) = {material}")

print("\n" + "=" * 80)
print("TESTING SMITHING RECIPE GRID SIZE")
print("=" * 80)

with open('recipes.JSON/recipes-smithing-1.JSON', 'r') as f:
    data = json.load(f)
    recipes = data.get('recipes', [])

# Check several recipes for gridSize field
print("\nChecking recipes for gridSize field:")
for recipe in recipes[:10]:
    recipe_id = recipe['recipeId']
    grid_size = recipe.get('gridSize', 'NOT FOUND')
    tier = recipe.get('stationTier', 'NOT FOUND')
    print(f"  {recipe_id}")
    print(f"    tier: {tier}, gridSize: {grid_size}")

print("\n" + "=" * 80)
print("TESTING ALCHEMY TIER 3+ DIFFICULTY")
print("=" * 80)

# Check if alchemy.py has tier 3/4 ingredient_types
with open('Crafting-subdisciplines/alchemy.py', 'r') as f:
    content = f.read()

if 'elif self.tier == 3:' in content:
    # Find the section
    lines = content.split('\n')
    for i, line in enumerate(lines):
        if 'elif self.tier == 3:' in line:
            print(f"\nFound tier 3 setup at line {i+1}")
            for j in range(10):
                if i+j < len(lines):
                    print(f"  {lines[i+j]}")
            break
else:
    print("\nWARNING: No tier 3 setup found in alchemy.py!")

print("\n" + "=" * 80)
print("ALL TESTS COMPLETE")
print("=" * 80)

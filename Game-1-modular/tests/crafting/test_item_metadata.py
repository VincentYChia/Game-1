"""
Test script to debug item metadata loading and enchanting filtering
"""
import json
import os
import sys

# Add Game-1-modular to path and set working directory
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)
os.chdir(project_root)  # Change to project root for relative JSON paths

def load_item_metadata():
    """Load all item metadata from recipes and items JSON files"""
    metadata = {}

    # Load from recipe files (recipes have metadata.narrative for outputs)
    recipe_paths = [
        "recipes.JSON/recipes-smithing-1.JSON",
        "recipes.JSON/recipes-smithing-2.JSON",
        "recipes.JSON/recipes-smithing-3.JSON",
    ]

    print("=" * 80)
    print("LOADING RECIPE DATA")
    print("=" * 80)

    for path in recipe_paths:
        try:
            with open(path, 'r') as f:
                data = json.load(f)
                recipes = data.get('recipes', [])
                print(f"\n{path}: Found {len(recipes)} recipes")
                for recipe in recipes[:3]:  # Sample first 3
                    output_id = recipe.get('outputId', 'unknown')
                    narrative = recipe.get('metadata', {}).get('narrative', '')
                    name = recipe.get('name', output_id.replace('_', ' ').title())
                    if narrative:
                        metadata[output_id] = {
                            'name': name,
                            'narrative': narrative,
                            'tier': recipe.get('stationTier', 1),
                            'source': 'recipe'
                        }
                        print(f"  - {output_id}: {name}")
        except (FileNotFoundError, json.JSONDecodeError) as e:
            print(f"  ERROR loading {path}: {e}")

    # Load from item files (items have metadata.narrative)
    item_paths = [
        "items.JSON/items-smithing-1.JSON",
        "items.JSON/items-smithing-2.JSON",
    ]

    print("\n" + "=" * 80)
    print("LOADING ITEM DATA")
    print("=" * 80)

    for path in item_paths:
        try:
            with open(path, 'r') as f:
                data = json.load(f)
                print(f"\n{path}:")
                print(f"  Keys in file: {list(data.keys())}")

                # Items can be in various arrays (weapons, armor, etc.)
                for key, items_list in data.items():
                    if isinstance(items_list, list) and key != 'metadata':
                        print(f"\n  Section '{key}': {len(items_list)} items")
                        for i, item in enumerate(items_list[:3]):  # Sample first 3
                            if isinstance(item, dict) and 'itemId' in item:
                                item_id = item['itemId']
                                narrative = item.get('metadata', {}).get('narrative', '')
                                name = item.get('name', item_id.replace('_', ' ').title())
                                item_type = item.get('type', 'NO_TYPE')
                                item_category = item.get('category', 'NO_CATEGORY')

                                print(f"    [{i}] {item_id}:")
                                print(f"        name: {name}")
                                print(f"        type: {item_type}")
                                print(f"        category: {item_category}")
                                print(f"        has narrative: {bool(narrative)}")
                                print(f"        already in metadata: {item_id in metadata}")

                                # UPDATE existing metadata or create new
                                # Items have more complete info (type, category) than recipes
                                if narrative:
                                    if item_id in metadata:
                                        # Update existing with type/category from item data
                                        print(f"        -> UPDATING existing metadata with type/category")
                                        metadata[item_id]['type'] = item_type
                                        metadata[item_id]['category'] = item_category
                                    else:
                                        # Create new entry
                                        print(f"        -> CREATING new metadata entry")
                                        metadata[item_id] = {
                                            'name': name,
                                            'narrative': narrative,
                                            'tier': item.get('tier', 1),
                                            'category': item_category,
                                            'type': item_type,
                                            'source': 'item'
                                        }
        except (FileNotFoundError, json.JSONDecodeError) as e:
            print(f"  ERROR loading {path}: {e}")

    print(f"\n{'=' * 80}")
    print(f"TOTAL METADATA LOADED: {len(metadata)} items")
    print(f"{'=' * 80}\n")
    return metadata


def test_enchanting_filtering():
    """Test enchanting item filtering"""
    print("\n" + "=" * 80)
    print("TESTING ENCHANTING FILTERING")
    print("=" * 80)

    metadata = load_item_metadata()

    # Simulate crafted items
    crafted_items = {
        'iron_shortsword': {'quantity': 1, 'enchantments': []},
        'copper_spear': {'quantity': 1, 'enchantments': []},
        'steel_longsword': {'quantity': 1, 'enchantments': []},
        'copper_pickaxe': {'quantity': 1, 'enchantments': []},
        'iron_axe': {'quantity': 1, 'enchantments': []},
        'leather_tunic': {'quantity': 1, 'enchantments': []},
        'iron_boots': {'quantity': 1, 'enchantments': []},
    }

    print(f"\nSimulated crafted items: {list(crafted_items.keys())}")

    # Test filtering for weapon enchantment
    applicable_to = ['weapon']
    print(f"\nFiltering for applicableTo: {applicable_to}")

    enchantable_items = []
    for item_id, item_data in crafted_items.items():
        qty = item_data.get('quantity', 0)

        if qty > 0:
            item_meta = metadata.get(item_id, {})
            item_type = item_meta.get('type', '')
            item_category = item_meta.get('category', '')

            print(f"\n  Checking '{item_id}':")
            print(f"    metadata exists: {item_id in metadata}")
            print(f"    type: '{item_type}'")
            print(f"    category: '{item_category}'")

            matches = False
            if 'any' in applicable_to:
                matches = True
                print(f"    ✓ MATCH: 'any' in applicableTo")
            elif item_type in applicable_to:
                matches = True
                print(f"    ✓ MATCH: type '{item_type}' in {applicable_to}")
            elif item_category in applicable_to:
                matches = True
                print(f"    ✓ MATCH: category '{item_category}' in {applicable_to}")
            elif any(app_type in item_id.lower() for app_type in applicable_to):
                matches = True
                print(f"    ✓ MATCH: item_id contains applicable type")
            else:
                print(f"    ✗ NO MATCH")

            if matches:
                enchantable_items.append(item_id)

    print(f"\n{'=' * 80}")
    print(f"ENCHANTABLE ITEMS FOUND: {len(enchantable_items)}")
    for item in enchantable_items:
        print(f"  - {item}")
    print(f"{'=' * 80}\n")


if __name__ == "__main__":
    test_enchanting_filtering()

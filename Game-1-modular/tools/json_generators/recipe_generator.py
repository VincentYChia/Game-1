"""
Recipe Generator - Generate crafting recipes in bulk

Automatically create recipes for items based on patterns.
"""

import json
from typing import List, Dict, Any


class RecipeGenerator:
    """Generate crafting recipe JSON definitions"""

    # Standard material costs by tier
    TIER_MATERIAL_COSTS = {
        1: 3,  # Tier 1 items require 3 base materials
        2: 4,
        3: 5,
        4: 6
    }

    def generate_equipment_recipes(self,
                                   equipment_items: List[Dict[str, Any]],
                                   material_mapping: Dict[str, str]) -> List[Dict[str, Any]]:
        """
        Generate recipes for equipment items

        Args:
            equipment_items: List of equipment item definitions
            material_mapping: Maps material names to material IDs
                             e.g., {'copper': 'copper_ingot', 'iron': 'iron_ingot'}
        """
        recipes = []

        for item in equipment_items:
            recipe = self._create_equipment_recipe(item, material_mapping)
            if recipe:
                recipes.append(recipe)

        return recipes

    def _create_equipment_recipe(self,
                                 item: Dict[str, Any],
                                 material_mapping: Dict[str, str]) -> Dict[str, Any]:
        """Create a single equipment recipe"""
        item_id = item.get('itemId', '')
        tier = item.get('tier', 1)
        slot = item.get('slot', 'mainHand')

        # Extract material from item_id (e.g., "copper_sword" ’ "copper")
        parts = item_id.split('_')
        if len(parts) < 2:
            return None

        material_name = parts[0]
        material_id = material_mapping.get(material_name)

        if not material_id:
            return None

        # Determine station based on slot
        station_type = 'smithing'  # Default
        if slot in ['tool']:
            station_type = 'smithing'
        elif slot in ['mainHand', 'offHand', 'helmet', 'chestplate', 'leggings', 'boots', 'gauntlets']:
            station_type = 'smithing'

        # Calculate material requirements
        base_cost = self.TIER_MATERIAL_COSTS.get(tier, 3)

        # Armor pieces cost more
        if slot in ['chestplate']:
            base_cost += 4
        elif slot in ['leggings']:
            base_cost += 3
        elif slot in ['helmet']:
            base_cost += 1

        recipe_id = f"{item_id}_recipe"

        return {
            'recipeId': recipe_id,
            'outputId': item_id,
            'outputQty': 1,
            'stationTier': tier,
            'inputs': [
                {
                    'materialId': material_id,
                    'quantity': base_cost
                }
            ],
            'metadata': {
                'gridSize': '3x3',
                'difficulty': 'normal',
                'baseTime': 5.0 + (tier * 2.0)
            }
        }

    def generate_refining_recipes(self,
                                   ore_to_ingot: Dict[str, str],
                                   conversion_ratio: int = 3) -> List[Dict[str, Any]]:
        """
        Generate refining recipes (ore ’ ingot)

        Args:
            ore_to_ingot: Maps ore IDs to ingot IDs
                         e.g., {'copper_ore': 'copper_ingot'}
            conversion_ratio: How many ore per ingot (default 3:1)
        """
        recipes = []

        for ore_id, ingot_id in ore_to_ingot.items():
            recipe_id = f"{ingot_id}_recipe"

            recipe = {
                'recipeId': recipe_id,
                'outputs': [
                    {
                        'materialId': ingot_id,
                        'quantity': 1
                    }
                ],
                'stationTierRequired': 1,
                'inputs': [
                    {
                        'materialId': ore_id,
                        'quantity': conversion_ratio
                    }
                ],
                'metadata': {
                    'difficulty': 'normal',
                    'baseTime': 3.0
                }
            }

            recipes.append(recipe)

        return recipes

    def save_to_json(self, recipes: List[Dict[str, Any]], filepath: str, recipe_type: str = 'smithing'):
        """Save generated recipes to a JSON file"""
        output = {
            'metadata': {
                'version': '2.0',
                'generated': True,
                'recipe_count': len(recipes),
                'recipe_type': recipe_type
            },
            'recipes': recipes
        }

        with open(filepath, 'w') as f:
            json.dump(output, f, indent=2)

        print(f" Generated {len(recipes)} {recipe_type} recipes ’ {filepath}")


# Example usage
if __name__ == "__main__":
    generator = RecipeGenerator()

    # Generate refining recipes
    refining_recipes = generator.generate_refining_recipes({
        'copper_ore': 'copper_ingot',
        'iron_ore': 'iron_ingot',
        'steel_ore': 'steel_ingot',
        'mithril_ore': 'mithril_ingot'
    })

    generator.save_to_json(refining_recipes, 'recipes-refining-generated.JSON', 'refining')
    print(f"Generated {len(refining_recipes)} refining recipes")

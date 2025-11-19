"""Recipe Database - manages crafting recipes for all disciplines"""

import json
from pathlib import Path
from typing import Dict, List
from data.models.recipes import Recipe


class RecipeDatabase:
    _instance = None

    def __init__(self):
        self.recipes: Dict[str, Recipe] = {}
        self.recipes_by_station: Dict[str, List[Recipe]] = {
            "smithing": [], "alchemy": [], "refining": [], "engineering": [], "adornments": []
        }
        self.loaded = False

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = RecipeDatabase()
        return cls._instance

    def load_from_files(self, base_path: str = ""):
        total = 0
        for station_type, filename in [("smithing", "recipes-smithing-3.json"), ("alchemy", "recipes-alchemy-1.JSON"),
                                       ("refining", "recipes-refining-1.JSON"),
                                       ("engineering", "recipes-engineering-1.JSON"),
                                       ("adornments", "recipes-adornments-1.json")]:
            for path in [f"recipes.JSON/{filename}", f"{base_path}recipes.JSON/{filename}"]:
                if Path(path).exists():
                    total += self._load_file(path, station_type)
                    break

        if total == 0:
            self._create_default_recipes()
            total = len(self.recipes)

        self.loaded = True
        print(f"✓ Loaded {total} recipes")

    def _load_file(self, filepath: str, station_type: str) -> int:
        try:
            with open(filepath, 'r') as f:
                data = json.load(f)
            loaded_count = 0
            for recipe_data in data.get('recipes', []):
                # Check if this is an enchanting recipe (has enchantmentId instead of outputId)
                is_enchanting = 'enchantmentId' in recipe_data

                if is_enchanting:
                    # For enchanting: use enchantmentId as the output_id
                    output_id = recipe_data.get('enchantmentId', '')
                    output_qty = 1  # Enchantments don't have quantity
                    station_tier = recipe_data.get('stationTier', 1)
                elif 'outputs' in recipe_data:
                    # New format: outputs array (used in refining recipes)
                    outputs = recipe_data.get('outputs', [])
                    if outputs and len(outputs) > 0:
                        output_id = outputs[0].get('materialId', outputs[0].get('itemId', ''))
                        output_qty = outputs[0].get('quantity', 1)
                    else:
                        output_id = ''
                        output_qty = 1
                    station_tier = recipe_data.get('stationTierRequired', recipe_data.get('stationTier', 1))
                else:
                    # Regular crafting: use outputId
                    output_id = recipe_data.get('outputId', '')
                    output_qty = recipe_data.get('outputQty', 1)
                    station_tier = recipe_data.get('stationTier', 1)

                # Skip recipes with empty output_id
                if not output_id or output_id.strip() == '':
                    print(f"⚠ Skipping recipe {recipe_data.get('recipeId', 'UNKNOWN')} - no valid output ID")
                    continue

                recipe = Recipe(
                    recipe_id=recipe_data.get('recipeId', ''),
                    output_id=output_id,
                    output_qty=output_qty,
                    station_type=station_type,
                    station_tier=station_tier,
                    inputs=recipe_data.get('inputs', []),
                    is_enchantment=is_enchanting,
                    enchantment_name=recipe_data.get('enchantmentName', ''),
                    applicable_to=recipe_data.get('applicableTo', []),
                    effect=recipe_data.get('effect', {})
                )
                self.recipes[recipe.recipe_id] = recipe
                self.recipes_by_station[station_type].append(recipe)
                loaded_count += 1
            return loaded_count
        except Exception as e:
            print(f"⚠ Error loading recipes from {filepath}: {e}")
            return 0

    def _create_default_recipes(self):
        """Create comprehensive default recipes for equipment and materials"""
        default_recipes = [
            # REFINING - Basic Ingots
            Recipe("copper_ingot_recipe", "copper_ingot", 1, "refining", 1,
                   [{"materialId": "copper_ore", "quantity": 3}]),
            Recipe("iron_ingot_recipe", "iron_ingot", 1, "refining", 1,
                   [{"materialId": "iron_ore", "quantity": 3}]),
            Recipe("steel_ingot_recipe", "steel_ingot", 1, "refining", 2,
                   [{"materialId": "steel_ore", "quantity": 3}]),

            # SMITHING - Weapons
            Recipe("copper_sword_recipe", "copper_sword", 1, "smithing", 1,
                   [{"materialId": "copper_ingot", "quantity": 3}, {"materialId": "oak_log", "quantity": 1}]),
            Recipe("iron_sword_recipe", "iron_sword", 1, "smithing", 1,
                   [{"materialId": "iron_ingot", "quantity": 3}, {"materialId": "birch_log", "quantity": 1}]),
            Recipe("steel_sword_recipe", "steel_sword", 1, "smithing", 2,
                   [{"materialId": "steel_ingot", "quantity": 3}, {"materialId": "maple_log", "quantity": 1}]),

            # SMITHING - Helmets
            Recipe("copper_helmet_recipe", "copper_helmet", 1, "smithing", 1,
                   [{"materialId": "copper_ingot", "quantity": 4}]),
            Recipe("iron_helmet_recipe", "iron_helmet", 1, "smithing", 1,
                   [{"materialId": "iron_ingot", "quantity": 4}]),

            # SMITHING - Chestplates
            Recipe("copper_chestplate_recipe", "copper_chestplate", 1, "smithing", 1,
                   [{"materialId": "copper_ingot", "quantity": 7}]),
            Recipe("iron_chestplate_recipe", "iron_chestplate", 1, "smithing", 1,
                   [{"materialId": "iron_ingot", "quantity": 7}]),

            # SMITHING - Leggings
            Recipe("copper_leggings_recipe", "copper_leggings", 1, "smithing", 1,
                   [{"materialId": "copper_ingot", "quantity": 6}]),
            Recipe("iron_leggings_recipe", "iron_leggings", 1, "smithing", 1,
                   [{"materialId": "iron_ingot", "quantity": 6}]),

            # SMITHING - Boots
            Recipe("copper_boots_recipe", "copper_boots", 1, "smithing", 1,
                   [{"materialId": "copper_ingot", "quantity": 3}]),
            Recipe("iron_boots_recipe", "iron_boots", 1, "smithing", 1,
                   [{"materialId": "iron_ingot", "quantity": 3}]),
        ]

        for recipe in default_recipes:
            self.recipes[recipe.recipe_id] = recipe
            self.recipes_by_station[recipe.station_type].append(recipe)

        print(f"✓ Created {len(default_recipes)} default recipes")

    def get_recipes_for_station(self, station_type: str, tier: int = 1) -> List[Recipe]:
        return [r for r in self.recipes_by_station.get(station_type, []) if r.station_tier <= tier]

    def can_craft(self, recipe: Recipe, inventory) -> bool:
        # Import Config here to avoid circular import
        try:
            from config import Config
            if Config.DEBUG_INFINITE_RESOURCES:
                return True
        except ImportError:
            pass

        for inp in recipe.inputs:
            if inventory.get_item_count(inp.get('materialId', '')) < inp.get('quantity', 0):
                return False
        return True

    def consume_materials(self, recipe: Recipe, inventory) -> bool:
        # Import Config here to avoid circular import
        try:
            from config import Config
            if Config.DEBUG_INFINITE_RESOURCES:
                return True
        except ImportError:
            pass

        if not self.can_craft(recipe, inventory):
            return False

        to_consume = {}
        for inp in recipe.inputs:
            mat_id = inp.get('materialId', '')
            qty = inp.get('quantity', 0)
            to_consume[mat_id] = qty

        for mat_id, needed in to_consume.items():
            remaining = needed
            for i in range(len(inventory.slots)):
                if inventory.slots[i] and inventory.slots[i].item_id == mat_id:
                    slot = inventory.slots[i]
                    if slot.quantity >= remaining:
                        slot.quantity -= remaining
                        if slot.quantity == 0:
                            inventory.slots[i] = None
                        remaining = 0
                        break
                    else:
                        remaining -= slot.quantity
                        inventory.slots[i] = None

            if remaining > 0:
                return False

        return True

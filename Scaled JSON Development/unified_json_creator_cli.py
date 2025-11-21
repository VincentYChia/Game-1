#!/usr/bin/env python3
"""
Unified JSON Creator - CLI Tool
Creates and validates JSONs for all game types with smart cross-reference checking

Usage:
    python3 unified_json_creator_cli.py
"""

import json
import os
import sys
from pathlib import Path
from typing import Dict, List, Any, Optional

# Add parent directories to path to access game modules
sys.path.insert(0, str(Path(__file__).parent.parent / "Game-1-modular"))

# Official files that the game actually loads (from game_engine.py and database loaders)
GAME_FILES = {
    "equipment": [
        "Game-1-modular/items.JSON/items-smithing-2.JSON",  # Version 2 for equipment
        "Game-1-modular/items.JSON/items-tools-1.JSON",
        # Note: items-smithing-1 loaded for devices, items-alchemy-1 loaded for consumables
    ],
    "materials": [
        "Game-1-modular/items.JSON/items-materials-1.JSON",
        "Game-1-modular/items.JSON/items-refining-1.JSON",
    ],
    "recipes": [
        "Game-1-modular/recipes.JSON/recipes-smithing-3.JSON",  # Version 3!
        "Game-1-modular/recipes.JSON/recipes-alchemy-1.JSON",
        "Game-1-modular/recipes.JSON/recipes-refining-1.JSON",
        "Game-1-modular/recipes.JSON/recipes-engineering-1.JSON",
        "Game-1-modular/recipes.JSON/recipes-adornments-1.json",  # adornments not enchanting!
    ],
    "placements": [
        "Game-1-modular/placements.JSON/placements-smithing-1.JSON",
        "Game-1-modular/placements.JSON/placements-alchemy-1.JSON",
        "Game-1-modular/placements.JSON/placements-refining-1.JSON",
        "Game-1-modular/placements.JSON/placements-engineering-1.JSON",
        "Game-1-modular/placements.JSON/placements-adornments-1.JSON",
    ],
    "skills": [
        "Game-1-modular/Skills/skills-skills-1.JSON",
    ],
    "titles": [
        "Game-1-modular/progression/titles-1.JSON",
    ],
    "classes": [
        "Game-1-modular/progression/classes-1.JSON",
    ],
    "npcs": [
        "Game-1-modular/progression/npcs-enhanced.JSON",
        "Game-1-modular/progression/npcs-1.JSON",
    ],
    "quests": [
        "Game-1-modular/progression/quests-1.JSON",
    ],
}

# Schema templates with correct station types
STATION_TYPES = ["smithing", "alchemy", "refining", "engineering", "adornments"]  # NOT "enchanting"!

class UnifiedJSONCreator:
    """CLI tool for creating and validating game JSONs"""

    def __init__(self):
        self.base_path = Path(__file__).parent.parent
        self.loaded_data = {}
        self.file_sources = {}  # Track which file each item came from

    def load_all_data(self):
        """Load all JSON data from game files"""
        print("Loading game data...")

        for category, files in GAME_FILES.items():
            self.loaded_data[category] = []

            for file_path in files:
                full_path = self.base_path / file_path
                if not full_path.exists():
                    print(f"  Warning: {file_path} not found")
                    continue

                try:
                    with open(full_path, 'r', encoding='utf-8') as f:
                        data = json.load(f)

                    # Extract items from nested structure
                    items = self._extract_items(data, category)

                    # Add source file metadata
                    for item in items:
                        item_id = self._get_item_id(item, category)
                        if item_id:
                            item['_source_file'] = str(file_path)
                            self.file_sources[item_id] = str(file_path)

                    self.loaded_data[category].extend(items)
                    print(f"  ✓ Loaded {len(items)} from {file_path}")

                except Exception as e:
                    print(f"  Error loading {file_path}: {e}")

        # Print summary
        print("\nData loaded:")
        for category, items in self.loaded_data.items():
            print(f"  {category}: {len(items)} items")
        print(f"Total: {sum(len(items) for items in self.loaded_data.values())} items\n")

    def _extract_items(self, data: Dict, category: str) -> List[Dict]:
        """Extract items from nested JSON structure"""
        items = []

        if isinstance(data, list):
            return data

        if isinstance(data, dict):
            # Skip metadata
            for key, value in data.items():
                if key == "metadata":
                    continue
                if isinstance(value, list):
                    items.extend(value)
                elif isinstance(value, dict) and key not in ["metadata"]:
                    items.append(value)

        return items

    def _get_item_id(self, item: Dict, category: str) -> Optional[str]:
        """Get ID field for an item based on category"""
        id_fields = {
            "equipment": "itemId",
            "materials": "materialId",
            "recipes": "recipeId",
            "placements": "recipeId",
            "skills": "skillId",
            "quests": "quest_id",
            "npcs": "npc_id",
            "titles": "titleId",
            "classes": "classId",
        }

        id_field = id_fields.get(category, "id")
        return item.get(id_field)

    def create_recipe(self):
        """Interactive recipe creator"""
        print("\n=== Create New Recipe ===\n")

        # Get discipline
        print("Select discipline:")
        for i, discipline in enumerate(STATION_TYPES, 1):
            print(f"  {i}. {discipline}")

        choice = input("\nEnter number: ").strip()
        try:
            discipline = STATION_TYPES[int(choice) - 1]
        except (ValueError, IndexError):
            print("Invalid choice")
            return

        print(f"\nCreating {discipline} recipe...")

        # Build recipe
        recipe = {
            "recipeId": input("Recipe ID (e.g., smithing_iron_sword): ").strip(),
            "stationType": discipline,  # Correctly uses "adornments" not "enchanting"
            "stationTier": int(input("Station Tier (1-4): ").strip()),
        }

        # Handle different formats
        if discipline == "adornments":
            recipe["enchantmentId"] = input("Enchantment ID: ").strip()
            recipe["enchantmentName"] = input("Enchantment Name: ").strip()
            recipe["applicableTo"] = input("Applicable to (comma-separated, e.g., weapon,armor): ").strip().split(",")
        elif discipline == "refining":
            # Refining uses outputs array
            mat_id = input("Output Material ID: ").strip()
            qty = int(input("Output Quantity: ").strip())
            recipe["outputs"] = [{"materialId": mat_id, "quantity": qty, "rarity": "common"}]
            recipe["stationTierRequired"] = recipe.pop("stationTier")  # Different field name
        else:
            recipe["outputId"] = input("Output Item ID: ").strip()
            recipe["outputQty"] = int(input("Output Quantity (default 1): ").strip() or "1")

        # Inputs
        print("\nAdd inputs (press Enter with empty ID to finish):")
        inputs = []
        while True:
            mat_id = input("  Material ID: ").strip()
            if not mat_id:
                break
            qty = int(input("  Quantity: ").strip())
            inputs.append({"materialId": mat_id, "quantity": qty})

        recipe["inputs"] = inputs

        # Validate
        issues = self.validate_recipe(recipe)
        if issues:
            print("\n⚠️  Validation Issues:")
            for issue in issues:
                print(f"  - {issue}")

            if not input("\nSave anyway? (y/n): ").lower().startswith('y'):
                return

        # Save
        self.save_recipe(recipe, discipline)

    def validate_recipe(self, recipe: Dict) -> List[str]:
        """Validate a recipe"""
        issues = []

        # Check duplicate ID
        recipe_id = recipe.get("recipeId")
        existing_ids = [self._get_item_id(r, "recipes") for r in self.loaded_data.get("recipes", [])]
        if recipe_id in existing_ids:
            issues.append(f"Duplicate recipe ID: {recipe_id}")

        # Validate station type
        station_type = recipe.get("stationType")
        if station_type not in STATION_TYPES:
            issues.append(f"Invalid stationType: {station_type}. Must be one of: {', '.join(STATION_TYPES)}")

        if station_type == "enchanting":
            issues.append("ERROR: Use 'adornments' not 'enchanting' for station type!")

        # Validate output exists
        output_id = recipe.get("outputId")
        if output_id:
            equipment_ids = [self._get_item_id(e, "equipment") for e in self.loaded_data.get("equipment", [])]
            material_ids = [self._get_item_id(m, "materials") for m in self.loaded_data.get("materials", [])]

            if output_id not in equipment_ids and output_id not in material_ids:
                issues.append(f"Output item '{output_id}' not found in equipment or materials")
                issues.append(f"  Available equipment: {', '.join(equipment_ids[:10])}...")

        # Validate inputs exist
        for inp in recipe.get("inputs", []):
            mat_id = inp.get("materialId")
            material_ids = [self._get_item_id(m, "materials") for m in self.loaded_data.get("materials", [])]
            if mat_id not in material_ids:
                issues.append(f"Input material '{mat_id}' not found")

        return issues

    def save_recipe(self, recipe: Dict, discipline: str):
        """Save recipe to appropriate file"""
        # Determine file
        if discipline == "smithing":
            file_path = self.base_path / "Game-1-modular/recipes.JSON/recipes-smithing-3.JSON"
        elif discipline == "adornments":
            file_path = self.base_path / "Game-1-modular/recipes.JSON/recipes-adornments-1.json"
        else:
            file_path = self.base_path / f"Game-1-modular/recipes.JSON/recipes-{discipline}-1.JSON"

        # Load existing
        try:
            with open(file_path, 'r') as f:
                data = json.load(f)
        except FileNotFoundError:
            data = {"metadata": {"version": "1.0"}, "recipes": []}

        # Append
        if "recipes" not in data:
            data["recipes"] = []

        data["recipes"].append(recipe)

        # Update metadata
        if "metadata" in data:
            data["metadata"]["totalRecipes"] = len(data["recipes"])

        # Save
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)

        print(f"\n✓ Recipe saved to {file_path}")
        print(f"  Total recipes in file: {len(data['recipes'])}")

    def list_items(self, category: str):
        """List all items in a category"""
        items = self.loaded_data.get(category, [])

        if not items:
            print(f"No {category} loaded")
            return

        print(f"\n=== {category.upper()} ({len(items)} items) ===\n")

        for i, item in enumerate(items, 1):
            item_id = self._get_item_id(item, category)
            name = item.get("name", item.get("title", ""))
            source = item.get("_source_file", "Unknown")

            print(f"{i:3d}. {item_id:30s} {name:30s} [{Path(source).name}]")

            if i >= 50:
                if not input("\nShow more? (y/n): ").lower().startswith('y'):
                    break

    def check_references(self):
        """Check for broken references"""
        print("\n=== Checking Cross-References ===\n")

        issues = []

        # Check recipes reference valid outputs
        for recipe in self.loaded_data.get("recipes", []):
            recipe_id = recipe.get("recipeId")
            output_id = recipe.get("outputId")

            if output_id:
                equipment_ids = [self._get_item_id(e, "equipment") for e in self.loaded_data.get("equipment", [])]
                material_ids = [self._get_item_id(m, "materials") for m in self.loaded_data.get("materials", [])]

                if output_id not in equipment_ids and output_id not in material_ids:
                    issues.append(f"Recipe '{recipe_id}' output '{output_id}' not found")

        if issues:
            print("Issues found:")
            for issue in issues:
                print(f"  ❌ {issue}")
        else:
            print("✓ No broken references found")

    def main_menu(self):
        """Main interactive menu"""
        while True:
            print("\n" + "="*60)
            print("UNIFIED JSON CREATOR")
            print("="*60)
            print("\n1. Create Recipe")
            print("2. List Equipment")
            print("3. List Materials")
            print("4. List Recipes")
            print("5. Check Cross-References")
            print("6. Reload Data")
            print("0. Exit")

            choice = input("\nEnter choice: ").strip()

            if choice == "1":
                self.create_recipe()
            elif choice == "2":
                self.list_items("equipment")
            elif choice == "3":
                self.list_items("materials")
            elif choice == "4":
                self.list_items("recipes")
            elif choice == "5":
                self.check_references()
            elif choice == "6":
                self.load_all_data()
            elif choice == "0":
                print("Goodbye!")
                break
            else:
                print("Invalid choice")

def main():
    print("Unified JSON Creator - CLI Tool")
    print("================================\n")

    creator = UnifiedJSONCreator()
    creator.load_all_data()
    creator.main_menu()

if __name__ == "__main__":
    main()

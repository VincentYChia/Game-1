"""
Material Enricher for LLM Training Data
Adds material metadata to recipe inputs for richer training context.

Place this file at: LLM Training Data/Fewshot_llm/src/material_enricher.py
"""

import json
from pathlib import Path
from typing import Dict, List, Any, Optional
from copy import deepcopy


class MaterialEnricher:
    """
    Enriches recipe inputs with material metadata for LLM training.

    Takes recipe inputs like:
        {"materialId": "iron_ingot", "quantity": 3}

    And enriches them to:
        {
            "materialId": "iron_ingot",
            "quantity": 3,
            "material_metadata": {
                "name": "Iron Ingot",
                "tier": 1,
                "category": "metal",
                "tags": ["refined", "common"],
                ...
            }
        }
    """

    def __init__(self, materials_path: str):
        """
        Initialize the enricher with a materials JSON file.

        Args:
            materials_path: Path to items-materials-1.JSON
        """
        self.materials_path = Path(materials_path)
        self.materials: Dict[str, Dict] = {}
        self._load_materials()

    def _load_materials(self):
        """Load and index materials by materialId"""
        try:
            with open(self.materials_path, 'r') as f:
                data = json.load(f)

            # Materials are in a "materials" array
            for material in data.get("materials", []):
                material_id = material.get("materialId")
                if material_id:
                    self.materials[material_id] = material

        except FileNotFoundError:
            raise FileNotFoundError(f"Materials file not found: {self.materials_path}")
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in materials file: {e}")

    def get_material(self, material_id: str) -> Optional[Dict]:
        """Get a material by its ID"""
        return self.materials.get(material_id)

    def extract_material_metadata(self, material: Dict) -> Dict:
        """
        Extract relevant metadata from a material for training context.

        Returns a subset of material data useful for LLM understanding.
        """
        metadata = {
            "name": material.get("name", ""),
            "tier": material.get("tier", 1),
            "category": material.get("category", ""),
            "rarity": material.get("rarity", "common"),
        }

        # Include tags if present
        mat_metadata = material.get("metadata", {})
        if "tags" in mat_metadata:
            metadata["tags"] = mat_metadata["tags"]

        # Include description if present (helps LLM understand material)
        if "description" in mat_metadata:
            metadata["description"] = mat_metadata["description"]

        # Include source info if present
        if "source" in mat_metadata:
            metadata["source"] = mat_metadata["source"]

        # Include elemental/damage type if present
        if "elementalType" in material:
            metadata["elementalType"] = material["elementalType"]
        if "damageType" in material:
            metadata["damageType"] = material["damageType"]

        return metadata

    def enrich_input(self, input_item: Dict) -> Dict:
        """
        Enrich a single recipe input with material metadata.

        Args:
            input_item: A recipe input dict, e.g. {"materialId": "iron_ingot", "quantity": 3}

        Returns:
            Enriched input with material_metadata added
        """
        enriched = deepcopy(input_item)

        # Handle different input formats
        material_id = input_item.get("materialId") or input_item.get("itemId")

        if material_id:
            material = self.get_material(material_id)
            if material:
                enriched["material_metadata"] = self.extract_material_metadata(material)
            else:
                # Material not found - might be an item, not a material
                enriched["material_metadata"] = {"note": "not_in_materials_db"}

        return enriched

    def enrich_recipe(self, recipe_input: Dict) -> Dict:
        """
        Enrich all inputs in a recipe with material metadata.

        Args:
            recipe_input: Recipe input dict containing an "inputs" array

        Returns:
            Enriched recipe input with all materials annotated
        """
        enriched = deepcopy(recipe_input)

        # Enrich standard inputs array
        if "inputs" in enriched:
            enriched["inputs"] = [
                self.enrich_input(inp) for inp in enriched["inputs"]
            ]

        # Enrich coreInput if present (refining recipes)
        if "coreInput" in enriched and enriched["coreInput"]:
            enriched["coreInput"] = self.enrich_input(enriched["coreInput"])

        # Enrich surroundingInputs if present (refining recipes)
        if "surroundingInputs" in enriched:
            enriched["surroundingInputs"] = [
                self.enrich_input(inp) for inp in enriched["surroundingInputs"]
            ]

        return enriched

    def enrich_training_pair(self, pair: Dict) -> Dict:
        """
        Enrich a complete training pair (input + output).

        Args:
            pair: Training pair with 'input' and 'output' keys

        Returns:
            Enriched training pair
        """
        enriched_pair = deepcopy(pair)

        if "input" in enriched_pair:
            enriched_pair["input"] = self.enrich_recipe(enriched_pair["input"])

        return enriched_pair


# Standalone usage example
if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python material_enricher.py <materials_json_path>")
        print("\nExample:")
        print("  python material_enricher.py ../Game-1-modular/items.JSON/items-materials-1.JSON")
        sys.exit(1)

    materials_path = sys.argv[1]

    try:
        enricher = MaterialEnricher(materials_path)
        print(f"✓ Loaded {len(enricher.materials)} materials")

        # Test enrichment
        test_input = {
            "recipeId": "test_recipe",
            "inputs": [
                {"materialId": "iron_ingot", "quantity": 3},
                {"materialId": "coal", "quantity": 1}
            ]
        }

        enriched = enricher.enrich_recipe(test_input)
        print("\nTest enrichment:")
        print(json.dumps(enriched, indent=2))

    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)
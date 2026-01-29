"""
LLM Training Data Generator for Game-1
Extracts training pairs from existing JSON files for all implemented systems.

Usage:
    python generate_training_data.py

Output:
    Creates LLM Training Data/ folder with JSON files for each system
    All training pairs are enriched with material metadata
"""

import json
from pathlib import Path
from typing import Dict, List, Optional, Any
from collections import defaultdict
from copy import deepcopy

# Configure paths (relative to where script is run from, expected: /home/user/Game-1/Scaled JSON Development/)
GAME_ROOT = Path("../Game-1-modular")
OUTPUT_DIR = Path("LLM Training Data")

# Keys to skip when iterating over JSON sections (metadata blurbs, etc.)
SKIP_KEYS = {"metadata", "version", "lastupdated", "description", "schema", "fileinfo"}

# File paths
PATHS = {
    # Crafting
    "smithing_recipes": GAME_ROOT / "recipes.JSON/recipes-smithing-3.JSON",
    "smithing_items_main": GAME_ROOT / "items.JSON/items-smithing-2.JSON",
    "smithing_items_tools": GAME_ROOT / "items.JSON/items-tools-1.JSON",
    "smithing_placements": GAME_ROOT / "placements.JSON/placements-smithing-1.JSON",

    "refining_recipes": GAME_ROOT / "recipes.JSON/recipes-refining-1.JSON",
    "refining_materials": GAME_ROOT / "items.JSON/items-materials-1.JSON",
    "refining_placements": GAME_ROOT / "placements.JSON/placements-refining-1.JSON",

    "alchemy_recipes": GAME_ROOT / "recipes.JSON/recipes-alchemy-1.JSON",
    "alchemy_items": GAME_ROOT / "items.JSON/items-alchemy-1.JSON",
    "alchemy_placements": GAME_ROOT / "placements.JSON/placements-alchemy-1.JSON",

    "engineering_recipes": GAME_ROOT / "recipes.JSON/recipes-engineering-1.JSON",
    "engineering_items": GAME_ROOT / "items.JSON/items-engineering-1.JSON",
    "engineering_placements": GAME_ROOT / "placements.JSON/placements-engineering-1.JSON",

    "enchanting_recipes": GAME_ROOT / "recipes.JSON/recipes-adornments-1.json",
    "enchanting_placements": GAME_ROOT / "placements.JSON/placements-adornments-1.JSON",

    # World systems
    "hostiles": GAME_ROOT / "Definitions.JSON/hostiles-1.JSON",
    "chunk_templates": GAME_ROOT / "Definitions.JSON/Chunk-templates-2.JSON",
    "materials": GAME_ROOT / "items.JSON/items-materials-1.JSON",
    "nodes": GAME_ROOT / "Definitions.JSON/resource-node-1.JSON",

    # Progression
    "skills": GAME_ROOT / "Skills/skills-skills-1.JSON",
    "titles": GAME_ROOT / "progression/titles-1.JSON",
}


# ============================================================================
# MATERIAL ENRICHER (Integrated)
# ============================================================================
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

            # Handle both "materials" array format and sectioned format
            if "materials" in data:
                for material in data.get("materials", []):
                    material_id = material.get("materialId")
                    if material_id:
                        self.materials[material_id] = material
            else:
                # Sectioned format - iterate all sections
                for key, value in data.items():
                    if key.lower() in SKIP_KEYS:
                        continue
                    if isinstance(value, list):
                        for material in value:
                            if isinstance(material, dict):
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


# Global enricher instance (initialized in main)
ENRICHER: Optional[MaterialEnricher] = None


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================
def load_json(filepath: Path) -> dict:
    """Load JSON file with error handling"""
    try:
        with open(filepath, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"⚠️  File not found: {filepath}")
        return {}
    except json.JSONDecodeError as e:
        print(f"⚠️  JSON decode error in {filepath}: {e}")
        return {}


def extract_all_items(data: dict, id_key: str = "itemId", skip_sections: set = None) -> Dict[str, Dict]:
    """
    Extract all items from a JSON file, iterating over all sections.
    Skips metadata and non-list values.

    Args:
        data: The loaded JSON data
        id_key: The key used for item IDs (e.g., "itemId", "materialId")
        skip_sections: Optional set of section names to skip (e.g., {"stations"})

    Returns:
        Dict mapping item IDs to their full data
    """
    items = {}
    skip_sections = skip_sections or set()

    for key, value in data.items():
        if key.lower() in SKIP_KEYS:
            continue
        if key.lower() in skip_sections:
            continue
        if isinstance(value, list):
            for item in value:
                if isinstance(item, dict) and id_key in item:
                    items[item[id_key]] = item
    return items


def save_training_pairs(system_name: str, pairs: List[Dict], split_ratio=0.9):
    """Save training pairs as JSON files with train/val split"""
    global ENRICHER

    # Enrich pairs if enricher available and pairs have inputs
    if ENRICHER:
        enriched_pairs = []
        for pair in pairs:
            inp = pair.get('input', {})
            if any(k in inp for k in ['inputs', 'coreInput', 'surroundingInputs']):
                enriched_pairs.append({
                    'input': ENRICHER.enrich_recipe(inp),
                    'output': pair.get('output', {})
                })
            else:
                enriched_pairs.append(pair)
        pairs = enriched_pairs

    output_path = OUTPUT_DIR / system_name
    output_path.mkdir(parents=True, exist_ok=True)

    # Calculate split
    total = len(pairs)
    train_size = int(total * split_ratio)

    train_pairs = pairs[:train_size]
    val_pairs = pairs[train_size:]

    # Save full dataset
    with open(output_path / "full_dataset.json", 'w') as f:
        json.dump(pairs, f, indent=2)

    # Save train/val split
    with open(output_path / "train.json", 'w') as f:
        json.dump(train_pairs, f, indent=2)

    with open(output_path / "val.json", 'w') as f:
        json.dump(val_pairs, f, indent=2)

    print(f"  ✓ Saved {total} pairs ({len(train_pairs)} train, {len(val_pairs)} val)")


# ============================================================================
# SYSTEM 1: SMITHING (Recipe → Item)
# ============================================================================
def extract_smithing_pairs():
    """Extract smithing recipe → item training pairs"""
    print("\n[System 1] Extracting Smithing Recipe → Item pairs...")

    recipes = load_json(PATHS["smithing_recipes"]).get("recipes", [])
    items_main = load_json(PATHS["smithing_items_main"])
    items_tools = load_json(PATHS["smithing_items_tools"])

    # Combine item sources, excluding stations
    all_items = extract_all_items(items_main, skip_sections={"stations"})
    all_items.update(extract_all_items(items_tools))

    pairs = []
    for recipe in recipes:
        output_id = recipe.get("outputId")
        if not output_id:
            continue

        item = all_items.get(output_id)
        if not item:
            print(f"  ⚠️  Missing item for recipe: {output_id}")
            continue

        # Build INPUT (recipe without placement data, item metadata without tags)
        input_data = {
            "recipeId": recipe["recipeId"],
            "stationTier": recipe.get("stationTier", 1),
            "stationType": recipe.get("stationType", "smithing"),
            "inputs": recipe.get("inputs", []),
            "narrative": recipe.get("metadata", {}).get("narrative", "")
        }

        # Build OUTPUT (complete item JSON)
        output_data = item

        pairs.append({
            "input": input_data,
            "output": output_data
        })

    save_training_pairs("system1_smithing_recipe_to_item", pairs)
    return pairs


# ============================================================================
# SYSTEM 1 x2: SMITHING PLACEMENT (Recipe + Item → Placement)
# ============================================================================
def extract_smithing_placement_pairs():
    """Extract smithing recipe + item → placement training pairs"""
    print("\n[System 1 x2] Extracting Smithing Placement pairs...")

    recipes = load_json(PATHS["smithing_recipes"]).get("recipes", [])
    items_main = load_json(PATHS["smithing_items_main"])
    items_tools = load_json(PATHS["smithing_items_tools"])
    placements = load_json(PATHS["smithing_placements"]).get("placements", [])

    # Combine items, excluding stations
    all_items = extract_all_items(items_main, skip_sections={"stations"})
    all_items.update(extract_all_items(items_tools))

    # Index placements by recipeId
    placements_by_recipe = {p["recipeId"]: p for p in placements}

    pairs = []
    for recipe in recipes:
        output_id = recipe.get("outputId")
        recipe_id = recipe.get("recipeId")

        if not output_id or not recipe_id:
            continue

        item = all_items.get(output_id)
        placement = placements_by_recipe.get(recipe_id)

        if not item or not placement:
            continue

        # Build INPUT (recipe data + item metadata with tier emphasis)
        input_data = {
            "recipeId": recipe_id,
            "itemId": output_id,
            "tier": recipe.get("stationTier", 1),
            "gridSize": recipe.get("gridSize", "3x3"),
            "inputs": recipe.get("inputs", []),
            "itemMetadata": item.get("metadata", {})
        }

        # Build OUTPUT (complete placement JSON)
        output_data = placement

        pairs.append({
            "input": input_data,
            "output": output_data
        })

    save_training_pairs("system1x2_smithing_placement", pairs)
    return pairs


# ============================================================================
# SYSTEM 2: REFINING (Recipe → Material)
# ============================================================================
def extract_refining_pairs():
    """Extract refining recipe → material training pairs"""
    print("\n[System 2] Extracting Refining Recipe → Material pairs...")

    recipes = load_json(PATHS["refining_recipes"]).get("recipes", [])
    materials_data = load_json(PATHS["refining_materials"])

    # Index materials - handle both formats
    if "materials" in materials_data:
        materials = {m["materialId"]: m for m in materials_data.get("materials", [])}
    else:
        materials = extract_all_items(materials_data, id_key="materialId")

    pairs = []
    for recipe in recipes:
        # Refining uses outputs[] array, not outputId
        outputs = recipe.get("outputs", [])
        if not outputs:
            continue

        # Get primary output (first in list)
        primary_output = outputs[0]
        material_id = primary_output.get("materialId")

        if not material_id:
            continue

        material = materials.get(material_id)
        if not material:
            print(f"  ⚠️  Missing material for recipe: {material_id}")
            continue

        # Build INPUT
        input_data = {
            "recipeId": recipe["recipeId"],
            "stationTier": recipe.get("stationTierRequired", 1),
            "stationType": recipe.get("stationRequired", "refinery"),
            "inputs": recipe.get("inputs", []),
            "narrative": recipe.get("metadata", {}).get("narrative", "")
        }

        # Build OUTPUT
        output_data = material

        pairs.append({
            "input": input_data,
            "output": output_data
        })

    save_training_pairs("system2_refining_recipe_to_material", pairs)
    return pairs


# ============================================================================
# SYSTEM 2 x2: REFINING PLACEMENT
# ============================================================================
def extract_refining_placement_pairs():
    """Extract refining recipe + material → placement training pairs"""
    print("\n[System 2 x2] Extracting Refining Placement pairs...")

    recipes = load_json(PATHS["refining_recipes"]).get("recipes", [])
    materials_data = load_json(PATHS["refining_materials"])
    placements = load_json(PATHS["refining_placements"]).get("placements", [])

    # Index materials and placements
    if "materials" in materials_data:
        materials = {m["materialId"]: m for m in materials_data.get("materials", [])}
    else:
        materials = extract_all_items(materials_data, id_key="materialId")

    placements_by_recipe = {p["recipeId"]: p for p in placements}

    pairs = []
    for recipe in recipes:
        recipe_id = recipe.get("recipeId")
        outputs = recipe.get("outputs", [])

        if not outputs or not recipe_id:
            continue

        material_id = outputs[0].get("materialId")
        material = materials.get(material_id)
        placement = placements_by_recipe.get(recipe_id)

        if not material or not placement:
            continue

        # Build INPUT
        input_data = {
            "recipeId": recipe_id,
            "materialId": material_id,
            "tier": recipe.get("stationTierRequired", 1),
            "coreInput": recipe.get("coreInput", {}),
            "surroundingInputs": recipe.get("surroundingInputs", []),
            "materialMetadata": material.get("metadata", {})
        }

        # Build OUTPUT
        output_data = placement

        pairs.append({
            "input": input_data,
            "output": output_data
        })

    save_training_pairs("system2x2_refining_placement", pairs)
    return pairs


# ============================================================================
# SYSTEM 3: ALCHEMY (Recipe → Item)
# ============================================================================
def extract_alchemy_pairs():
    """Extract alchemy recipe → item training pairs"""
    print("\n[System 3] Extracting Alchemy Recipe → Item pairs...")

    recipes = load_json(PATHS["alchemy_recipes"]).get("recipes", [])
    items_data = load_json(PATHS["alchemy_items"])
    materials_data = load_json(PATHS["materials"])

    # Alchemy outputs can be items (potions) OR materials (transmutation)
    items = extract_all_items(items_data)

    if "materials" in materials_data:
        materials = {m["materialId"]: m for m in materials_data.get("materials", [])}
    else:
        materials = extract_all_items(materials_data, id_key="materialId")

    # Combine both - check items first, then materials
    all_outputs = {**materials, **items}  # items override materials if same ID

    pairs = []
    for recipe in recipes:
        output_id = recipe.get("outputId")
        if not output_id:
            continue

        item = all_outputs.get(output_id)
        if not item:
            print(f"  ⚠️  Missing item/material for recipe: {output_id}")
            continue

        # Build INPUT
        input_data = {
            "recipeId": recipe["recipeId"],
            "stationTier": recipe.get("stationTier", 1),
            "stationType": recipe.get("stationType", "alchemy"),
            "inputs": recipe.get("inputs", []),
            "narrative": recipe.get("metadata", {}).get("narrative", "")
        }

        # Build OUTPUT
        output_data = item

        pairs.append({
            "input": input_data,
            "output": output_data
        })

    save_training_pairs("system3_alchemy_recipe_to_item", pairs)
    return pairs


# ============================================================================
# SYSTEM 3 x2: ALCHEMY PLACEMENT
# ============================================================================
def extract_alchemy_placement_pairs():
    """Extract alchemy recipe + item → placement training pairs"""
    print("\n[System 3 x2] Extracting Alchemy Placement pairs...")

    recipes = load_json(PATHS["alchemy_recipes"]).get("recipes", [])
    items_data = load_json(PATHS["alchemy_items"])
    materials_data = load_json(PATHS["materials"])
    placements = load_json(PATHS["alchemy_placements"]).get("placements", [])

    # Alchemy outputs can be items (potions) OR materials (transmutation)
    items = extract_all_items(items_data)

    if "materials" in materials_data:
        materials = {m["materialId"]: m for m in materials_data.get("materials", [])}
    else:
        materials = extract_all_items(materials_data, id_key="materialId")

    all_outputs = {**materials, **items}
    placements_by_recipe = {p["recipeId"]: p for p in placements}

    pairs = []
    for recipe in recipes:
        recipe_id = recipe.get("recipeId")
        output_id = recipe.get("outputId")

        if not recipe_id or not output_id:
            continue

        item = all_outputs.get(output_id)
        placement = placements_by_recipe.get(recipe_id)

        if not item or not placement:
            continue

        # Build INPUT
        input_data = {
            "recipeId": recipe_id,
            "itemId": output_id,
            "tier": recipe.get("stationTier", 1),
            "inputs": recipe.get("inputs", []),
            "itemMetadata": item.get("metadata", {})
        }

        # Build OUTPUT
        output_data = placement

        pairs.append({
            "input": input_data,
            "output": output_data
        })

    save_training_pairs("system3x2_alchemy_placement", pairs)
    return pairs


# ============================================================================
# SYSTEM 4: ENGINEERING (Recipe → Device)
# ============================================================================
def extract_engineering_pairs():
    """Extract engineering recipe → device training pairs"""
    print("\n[System 4] Extracting Engineering Recipe → Device pairs...")

    recipes = load_json(PATHS["engineering_recipes"]).get("recipes", [])
    items_data = load_json(PATHS["engineering_items"])

    # Index items - get all sections dynamically
    items = extract_all_items(items_data)

    pairs = []
    for recipe in recipes:
        output_id = recipe.get("outputId")
        if not output_id:
            continue

        item = items.get(output_id)
        if not item:
            print(f"  ⚠️  Missing item for recipe: {output_id}")
            continue

        # Build INPUT
        input_data = {
            "recipeId": recipe["recipeId"],
            "stationTier": recipe.get("stationTier", 1),
            "stationType": recipe.get("stationType", "engineering"),
            "inputs": recipe.get("inputs", []),
            "narrative": recipe.get("metadata", {}).get("narrative", "")
        }

        # Build OUTPUT
        output_data = item

        pairs.append({
            "input": input_data,
            "output": output_data
        })

    save_training_pairs("system4_engineering_recipe_to_device", pairs)
    return pairs


# ============================================================================
# SYSTEM 4 x2: ENGINEERING PLACEMENT
# ============================================================================
def extract_engineering_placement_pairs():
    """Extract engineering recipe + device → placement training pairs"""
    print("\n[System 4 x2] Extracting Engineering Placement pairs...")

    recipes = load_json(PATHS["engineering_recipes"]).get("recipes", [])
    items_data = load_json(PATHS["engineering_items"])
    placements = load_json(PATHS["engineering_placements"]).get("placements", [])

    # Index items dynamically
    items = extract_all_items(items_data)
    placements_by_recipe = {p["recipeId"]: p for p in placements}

    pairs = []
    for recipe in recipes:
        recipe_id = recipe.get("recipeId")
        output_id = recipe.get("outputId")

        if not recipe_id or not output_id:
            continue

        item = items.get(output_id)
        placement = placements_by_recipe.get(recipe_id)

        if not item or not placement:
            continue

        # Build INPUT
        input_data = {
            "recipeId": recipe_id,
            "itemId": output_id,
            "tier": recipe.get("stationTier", 1),
            "inputs": recipe.get("inputs", []),
            "itemMetadata": item.get("metadata", {})
        }

        # Build OUTPUT
        output_data = placement

        pairs.append({
            "input": input_data,
            "output": output_data
        })

    save_training_pairs("system4x2_engineering_placement", pairs)
    return pairs


# ============================================================================
# SYSTEM 5: ENCHANTING (Recipe → Enchantment)
# ============================================================================
def extract_enchanting_pairs():
    """Extract enchanting recipe → enchantment training pairs"""
    print("\n[System 5] Extracting Enchanting Recipe → Enchantment pairs...")

    recipes = load_json(PATHS["enchanting_recipes"]).get("recipes", [])

    # Enchanting is unique - recipe CONTAINS the enchantment definition
    # No separate item file needed

    pairs = []
    for recipe in recipes:
        enchantment_id = recipe.get("enchantmentId")
        if not enchantment_id:
            continue

        # Build INPUT (recipe inputs and tier)
        input_data = {
            "recipeId": recipe["recipeId"],
            "enchantmentId": enchantment_id,
            "stationTier": recipe.get("stationTier", 1),
            "stationType": recipe.get("stationType", "adornments"),
            "inputs": recipe.get("inputs", []),
            "narrative": recipe.get("metadata", {}).get("narrative", "")
        }

        # Build OUTPUT (complete enchantment definition)
        output_data = {
            "enchantmentId": enchantment_id,
            "name": recipe.get("name", ""),
            "applicableTo": recipe.get("applicableTo", []),
            "effect": recipe.get("effect", {}),
            "metadata": recipe.get("metadata", {})
        }

        pairs.append({
            "input": input_data,
            "output": output_data
        })

    save_training_pairs("system5_enchanting_recipe_to_enchantment", pairs)
    return pairs


# ============================================================================
# SYSTEM 5 x2: ENCHANTING PLACEMENT
# ============================================================================
def extract_enchanting_placement_pairs():
    """Extract enchanting recipe → placement training pairs"""
    print("\n[System 5 x2] Extracting Enchanting Placement pairs...")

    recipes = load_json(PATHS["enchanting_recipes"]).get("recipes", [])
    placements = load_json(PATHS["enchanting_placements"]).get("placements", [])

    placements_by_recipe = {p["recipeId"]: p for p in placements}

    pairs = []
    for recipe in recipes:
        recipe_id = recipe.get("recipeId")
        enchantment_id = recipe.get("enchantmentId")

        if not recipe_id or not enchantment_id:
            continue

        placement = placements_by_recipe.get(recipe_id)
        if not placement:
            continue

        # Build INPUT
        input_data = {
            "recipeId": recipe_id,
            "enchantmentId": enchantment_id,
            "tier": recipe.get("stationTier", 1),
            "inputs": recipe.get("inputs", []),
            "applicableTo": recipe.get("applicableTo", []),
            "effect": recipe.get("effect", {})
        }

        # Build OUTPUT
        output_data = placement

        pairs.append({
            "input": input_data,
            "output": output_data
        })

    save_training_pairs("system5x2_enchanting_placement", pairs)
    return pairs


# ============================================================================
# SYSTEM 6: HOSTILES (Chunk Assignment → Hostile)
# ============================================================================
def extract_hostile_pairs():
    """
    Extract chunk → hostile training pairs.

    For each chunk template, create pairs where:
    - INPUT: chunk metadata + enemySpawns object (with tier info)
    - OUTPUT: complete hostile JSON for each enemy in that chunk
    """
    print("\n[System 6] Extracting Chunk → Hostile pairs...")

    hostiles_data = load_json(PATHS["hostiles"])
    chunk_templates = load_json(PATHS["chunk_templates"])

    # Index hostiles by enemyId for quick lookup - handle both formats
    if "enemies" in hostiles_data:
        hostiles_by_id = {h["enemyId"]: h for h in hostiles_data.get("enemies", [])}
    else:
        hostiles_by_id = extract_all_items(hostiles_data, id_key="enemyId")

    # Extract pairs: one pair per (chunk, enemy) combination
    pairs = []
    for template in chunk_templates.get("templates", []):
        chunk_type = template["chunkType"]
        chunk_category = template["category"]
        chunk_theme = template["theme"]
        enemy_spawns = template.get("enemySpawns", {})

        # Create a training pair for each enemy in this chunk
        for enemy_id, spawn_info in enemy_spawns.items():
            hostile = hostiles_by_id.get(enemy_id)
            if not hostile:
                print(f"  ⚠️  Missing hostile definition for: {enemy_id}")
                continue

            # Build INPUT: chunk metadata + enemySpawns entry for this enemy
            input_data = {
                "chunkType": chunk_type,
                "chunkCategory": chunk_category,
                "chunkTheme": chunk_theme,
                "enemySpawns": {
                    enemy_id: spawn_info  # Includes density and tier
                }
            }

            # Build OUTPUT: complete hostile JSON
            output_data = hostile

            pairs.append({
                "input": input_data,
                "output": output_data
            })

    save_training_pairs("system6_chunk_to_hostile", pairs)
    return pairs


# ============================================================================
# SYSTEM 7: MATERIALS (Drop Source → Material)
# ============================================================================
def extract_material_pairs():
    """Extract drop source → material training pairs"""
    print("\n[System 7] Extracting Drop Source → Material pairs...")

    materials_data = load_json(PATHS["materials"])
    hostiles_data = load_json(PATHS["hostiles"])
    nodes_data = load_json(PATHS["nodes"])

    # Index materials - handle both formats
    if "materials" in materials_data:
        all_materials = {m["materialId"]: m for m in materials_data.get("materials", [])}
    else:
        all_materials = extract_all_items(materials_data, id_key="materialId")

    # Index hostiles - handle both formats
    if "enemies" in hostiles_data:
        hostiles = hostiles_data.get("enemies", [])
    else:
        hostiles = list(extract_all_items(hostiles_data, id_key="enemyId").values())

    # Index nodes - handle both formats
    if "nodes" in nodes_data:
        nodes = nodes_data.get("nodes", [])
    else:
        nodes = list(extract_all_items(nodes_data, id_key="resourceId").values())

    # Build drop source mapping
    material_sources = {}

    # From hostiles
    for hostile in hostiles:
        for drop in hostile.get("drops", []):
            material_id = drop.get("materialId")
            if material_id:
                if material_id not in material_sources:
                    material_sources[material_id] = []
                material_sources[material_id].append({
                    "source_type": "hostile",
                    "source_id": hostile["enemyId"],
                    "source_name": hostile["name"],
                    "source_tier": hostile["tier"]
                })

    # From nodes (drops are objects with materialId field)
    for node in nodes:
        for drop_obj in node.get("drops", []):
            material_id = drop_obj.get("materialId") if isinstance(drop_obj, dict) else drop_obj
            if material_id:
                if material_id not in material_sources:
                    material_sources[material_id] = []
                material_sources[material_id].append({
                    "source_type": "node",
                    "source_id": node.get("resourceId", ""),
                    "source_name": node.get("name", ""),
                    "source_tier": node.get("tier", 1)
                })

    # Extract pairs
    pairs = []
    for material_id, material in all_materials.items():
        sources = material_sources.get(material_id, [])
        if not sources:
            # Skip materials without drop sources (crafted materials)
            continue

        # Get primary source
        primary_source = sources[0]

        # Build INPUT
        input_data = {
            "sourceType": primary_source["source_type"],
            "sourceName": primary_source["source_name"],
            "sourceTier": primary_source["source_tier"],
            "materialTier": material.get("tier", 1),
            "materialCategory": material.get("category", ""),
            "allSources": [s["source_id"] for s in sources]
        }

        # Build OUTPUT (complete material JSON)
        output_data = material

        pairs.append({
            "input": input_data,
            "output": output_data
        })

    save_training_pairs("system7_drop_source_to_material", pairs)
    return pairs


# ============================================================================
# SYSTEM 8: NODES (Chunk Assignment → Resource Node)
# ============================================================================
def extract_node_pairs():
    """
    Extract chunk → resource node training pairs.

    For each chunk template, create pairs where:
    - INPUT: chunk metadata + resourceDensity entry (with density, tierBias)
    - OUTPUT: complete resource node JSON for each node in that chunk
    """
    print("\n[System 8] Extracting Chunk → Resource Node pairs...")

    nodes_data = load_json(PATHS["nodes"])
    chunk_templates = load_json(PATHS["chunk_templates"])

    # Index nodes by resourceId for quick lookup - handle both formats
    if "nodes" in nodes_data:
        nodes_by_id = {n["resourceId"]: n for n in nodes_data.get("nodes", [])}
    else:
        nodes_by_id = extract_all_items(nodes_data, id_key="resourceId")

    # Extract pairs: one pair per (chunk, resource) combination
    pairs = []
    for template in chunk_templates.get("templates", []):
        chunk_type = template["chunkType"]
        chunk_category = template["category"]
        chunk_theme = template["theme"]
        resource_density = template.get("resourceDensity", {})

        # Create a training pair for each resource in this chunk
        for resource_id, density_info in resource_density.items():
            node = nodes_by_id.get(resource_id)
            if not node:
                print(f"  ⚠️  Missing node definition for: {resource_id}")
                continue

            # Build INPUT: chunk metadata + resourceDensity entry for this node
            input_data = {
                "chunkType": chunk_type,
                "chunkCategory": chunk_category,
                "chunkTheme": chunk_theme,
                "resourceDensity": {
                    resource_id: density_info  # Includes density and tierBias
                }
            }

            # Build OUTPUT: complete node JSON
            output_data = node

            pairs.append({
                "input": input_data,
                "output": output_data
            })

    save_training_pairs("system8_chunk_to_node", pairs)
    return pairs


# ============================================================================
# SYSTEM 10: SKILLS (Requirements → Skill)
# ============================================================================
def extract_skill_pairs():
    """Extract requirements → skill training pairs"""
    print("\n[System 10] Extracting Requirements → Skill pairs...")

    skills_data = load_json(PATHS["skills"])

    # Handle both formats
    if "skills" in skills_data:
        skills = skills_data.get("skills", [])
    else:
        skills = list(extract_all_items(skills_data, id_key="skillId").values())

    pairs = []
    for skill in skills:
        skill_id = skill.get("skillId")
        if not skill_id:
            continue

        # Build INPUT (unlock conditions)
        input_data = {
            "requiredLevel": skill.get("requiredLevel", 1),
            "requiredSkills": skill.get("requiredSkills", []),
            "discipline": skill.get("discipline", ""),
            "tags": skill.get("tags", [])
        }

        # Build OUTPUT (complete skill JSON)
        output_data = skill

        pairs.append({
            "input": input_data,
            "output": output_data
        })

    save_training_pairs("system10_requirements_to_skill", pairs)
    return pairs


# ============================================================================
# SYSTEM 11: TITLES (Prerequisites → Title)
# ============================================================================
def extract_title_pairs():
    """Extract prerequisites → title training pairs"""
    print("\n[System 11] Extracting Prerequisites → Title pairs...")

    titles_data = load_json(PATHS["titles"])

    # Handle both formats
    if "titles" in titles_data:
        titles = titles_data.get("titles", [])
    else:
        titles = list(extract_all_items(titles_data, id_key="titleId").values())

    pairs = []
    for title in titles:
        title_id = title.get("titleId")
        if not title_id:
            continue

        # Build INPUT (unlock conditions)
        input_data = {
            "category": title.get("category", ""),
            "tier": title.get("tier", 1),
            "requirements": title.get("requirements", {}),
            "tags": title.get("metadata", {}).get("tags", [])
        }

        # Build OUTPUT (complete title JSON)
        output_data = title

        pairs.append({
            "input": input_data,
            "output": output_data
        })

    save_training_pairs("system11_prerequisites_to_title", pairs)
    return pairs


# ============================================================================
# MATERIAL METADATA ENRICHMENT (Post-processing alternative)
# ============================================================================
def enrich_all_training_data():
    """
    Enrich all training data files with material metadata.
    This is an alternative to inline enrichment during extraction.
    """
    global ENRICHER

    if not ENRICHER:
        print("\n⚠️  Skipping enrichment - MaterialEnricher not available")
        return

    print("\n" + "=" * 80)
    print("ENRICHING TRAINING DATA WITH MATERIAL METADATA")
    print("=" * 80)

    # List of all systems to enrich (recipe-based systems with inputs)
    systems_to_enrich = [
        "system1_smithing_recipe_to_item",
        "system1x2_smithing_placement",
        "system2_refining_recipe_to_material",
        "system2x2_refining_placement",
        "system3_alchemy_recipe_to_item",
        "system3x2_alchemy_placement",
        "system4_engineering_recipe_to_device",
        "system4x2_engineering_placement",
        "system5_enchanting_recipe_to_enchantment",
        "system5x2_enchanting_placement",
    ]

    enriched_count = 0
    for system_name in systems_to_enrich:
        system_dir = OUTPUT_DIR / system_name

        # Enrich all three files: full_dataset.json, train.json, val.json
        for filename in ["full_dataset.json", "train.json", "val.json"]:
            filepath = system_dir / filename
            if not filepath.exists():
                continue

            try:
                # Load training pairs
                with open(filepath, 'r') as f:
                    pairs = json.load(f)

                # Enrich each pair
                enriched_pairs = []
                for pair in pairs:
                    input_data = pair.get('input', {})

                    # Check if this input has an 'inputs' array to enrich
                    if 'inputs' in input_data or 'coreInput' in input_data or 'surroundingInputs' in input_data:
                        enriched_input = ENRICHER.enrich_recipe(input_data)
                        enriched_pair = {
                            'input': enriched_input,
                            'output': pair.get('output', {})
                        }
                        enriched_pairs.append(enriched_pair)
                    else:
                        # No inputs to enrich, keep as is
                        enriched_pairs.append(pair)

                # Save enriched data (overwrite)
                with open(filepath, 'w') as f:
                    json.dump(enriched_pairs, f, indent=2)

                enriched_count += 1
                print(f"  ✓ Enriched {system_name}/{filename} ({len(enriched_pairs)} pairs)")

            except Exception as e:
                print(f"  ⚠️  Error enriching {system_name}/{filename}: {e}")

    print(f"\n✓ Enriched {enriched_count} training data files")


# ============================================================================
# MAIN EXTRACTION
# ============================================================================
def main():
    """Run all extraction functions"""
    global ENRICHER

    print("=" * 80)
    print("LLM TRAINING DATA GENERATOR")
    print("=" * 80)

    # Create output directory
    OUTPUT_DIR.mkdir(exist_ok=True)

    # Initialize enricher
    materials_path = PATHS["materials"]
    if materials_path.exists():
        try:
            ENRICHER = MaterialEnricher(str(materials_path))
            print(f"✓ MaterialEnricher loaded with {len(ENRICHER.materials)} materials")
        except Exception as e:
            print(f"⚠️  MaterialEnricher failed to load: {e}")
            ENRICHER = None
    else:
        print("⚠️  Materials file not found - enrichment disabled")

    total_pairs = 0

    # Crafting systems
    total_pairs += len(extract_smithing_pairs())
    total_pairs += len(extract_smithing_placement_pairs())
    total_pairs += len(extract_refining_pairs())
    total_pairs += len(extract_refining_placement_pairs())
    total_pairs += len(extract_alchemy_pairs())
    total_pairs += len(extract_alchemy_placement_pairs())
    total_pairs += len(extract_engineering_pairs())
    total_pairs += len(extract_engineering_placement_pairs())
    total_pairs += len(extract_enchanting_pairs())
    total_pairs += len(extract_enchanting_placement_pairs())

    # World systems
    total_pairs += len(extract_hostile_pairs())
    total_pairs += len(extract_material_pairs())
    total_pairs += len(extract_node_pairs())

    # Progression systems
    total_pairs += len(extract_skill_pairs())
    total_pairs += len(extract_title_pairs())

    print("\n" + "=" * 80)
    print(f"✓ EXTRACTION COMPLETE")
    print(f"  Total training pairs generated: {total_pairs}")
    print(f"  Output directory: {OUTPUT_DIR}")
    print("=" * 80)


if __name__ == "__main__":
    main()
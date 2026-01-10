"""
LLM Training Data Generator for Game-1
Extracts training pairs from existing JSON files for all implemented systems.

Usage:
    python generate_training_data.py

Output:
    Creates LLM Training Data/ folder with JSON files for each system
"""

import json
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from collections import defaultdict

# Configure paths (relative to where script is run from, expected: /home/user/Game-1/)
GAME_ROOT = Path("Game-1-modular")
OUTPUT_DIR = Path("Scaled JSON Development/LLM Training Data")

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
    "engineering_items": GAME_ROOT / "items.JSON/items-alchemy-1.JSON",  # They share the same file
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


def save_training_pairs(system_name: str, pairs: List[Dict], split_ratio=0.9):
    """Save training pairs as JSON files with train/val split"""
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

    # Combine item sources (smithing items split across files)
    all_items = {}

    # Items from smithing file (organized in sections)
    for section in ["weapons", "armor", "accessories", "stations"]:
        for item in items_main.get(section, []):
            all_items[item["itemId"]] = item

    # Items from tools file (organized in sections)
    for section in ["tools"]:
        for item in items_tools.get(section, []):
            all_items[item["itemId"]] = item

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

    # Combine items
    all_items = {}
    for section in ["weapons", "armor", "accessories", "stations"]:
        for item in items_main.get(section, []):
            all_items[item["itemId"]] = item
    for section in ["tools"]:
        for item in items_tools.get(section, []):
            all_items[item["itemId"]] = item

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

    # Index materials
    materials = {m["materialId"]: m for m in materials_data.get("materials", [])}

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
            "stationTier": recipe.get("stationTier", 1),
            "stationType": recipe.get("stationType", "refining"),
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
    materials = {m["materialId"]: m for m in materials_data.get("materials", [])}
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
            "tier": recipe.get("stationTier", 1),
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

    # Index items (alchemy items organized in sections)
    items = {}
    for section in ["potions_healing", "potions_mana", "potions_utility", "elixirs"]:
        for item in items_data.get(section, []):
            items[item["itemId"]] = item

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
    placements = load_json(PATHS["alchemy_placements"]).get("placements", [])

    # Index items
    items = {}
    for section in ["potions_healing", "potions_mana", "potions_utility", "elixirs"]:
        for item in items_data.get(section, []):
            items[item["itemId"]] = item

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

    save_training_pairs("system3x2_alchemy_placement", pairs)
    return pairs


# ============================================================================
# SYSTEM 4: ENGINEERING (Recipe → Device)
# ============================================================================
def extract_engineering_pairs():
    """Extract engineering recipe → device training pairs"""
    print("\n[System 4] Extracting Engineering Recipe → Device pairs...")

    recipes = load_json(PATHS["engineering_recipes"]).get("recipes", [])
    # Engineering items share the alchemy file
    items_data = load_json(PATHS["engineering_items"])

    # Index items (engineering items in sections: turrets, bombs, traps)
    items = {}
    for section in ["turrets", "bombs", "traps"]:
        for item in items_data.get(section, []):
            items[item["itemId"]] = item

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

    # Index items
    items = {}
    for section in ["turrets", "bombs", "traps"]:
        for item in items_data.get(section, []):
            items[item["itemId"]] = item

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
    """Extract chunk assignment → hostile training pairs"""
    print("\n[System 6] Extracting Chunk Assignment → Hostile pairs...")

    hostiles_data = load_json(PATHS["hostiles"])
    chunk_templates = load_json(PATHS["chunk_templates"])

    # Build reverse mapping: hostile → chunks
    hostile_to_chunks = {}
    for template in chunk_templates.get("templates", []):
        chunk_type = template["chunkType"]
        chunk_category = template["category"]
        chunk_theme = template["theme"]

        for enemy_id, spawn_info in template.get("enemySpawns", {}).items():
            if enemy_id not in hostile_to_chunks:
                hostile_to_chunks[enemy_id] = []

            hostile_to_chunks[enemy_id].append({
                "chunkType": chunk_type,
                "category": chunk_category,
                "theme": chunk_theme,
                "density": spawn_info["density"]
            })

    # Extract pairs
    pairs = []
    for hostile in hostiles_data.get("enemies", []):
        enemy_id = hostile.get("enemyId")
        if not enemy_id:
            continue

        chunk_assignments = hostile_to_chunks.get(enemy_id, [])
        if not chunk_assignments:
            print(f"  ⚠️  No chunk assignments for hostile: {enemy_id}")
            continue

        # Get primary chunk (first assignment)
        primary_chunk = chunk_assignments[0]

        # Build INPUT
        input_data = {
            "primaryChunk": primary_chunk["chunkType"],
            "chunkCategory": primary_chunk["category"],
            "chunkTheme": primary_chunk["theme"],
            "spawnDensity": primary_chunk["density"],
            "allChunks": [c["chunkType"] for c in chunk_assignments],
            "tier": hostile.get("tier", 1),
            "category": hostile.get("category", ""),
            "tags": hostile.get("metadata", {}).get("tags", [])
        }

        # Build OUTPUT (complete hostile JSON)
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

    # Build drop source mapping
    material_sources = {}

    # From hostiles
    for hostile in hostiles_data.get("enemies", []):
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
    for node in nodes_data.get("nodes", []):
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
    for material in materials_data.get("materials", []):
        material_id = material.get("materialId")
        if not material_id:
            continue

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
    """Extract chunk assignment → resource node training pairs"""
    print("\n[System 8] Extracting Chunk Assignment → Resource Node pairs...")

    nodes_data = load_json(PATHS["nodes"])
    chunk_templates = load_json(PATHS["chunk_templates"])

    # Build reverse mapping: node → chunks (using drop IDs as node references)
    node_to_chunks = {}
    for template in chunk_templates.get("templates", []):
        chunk_type = template["chunkType"]
        chunk_category = template["category"]
        chunk_theme = template["theme"]

        for resource_id, resource_info in template.get("resourceDensity", {}).items():
            if resource_id not in node_to_chunks:
                node_to_chunks[resource_id] = []

            node_to_chunks[resource_id].append({
                "chunkType": chunk_type,
                "category": chunk_category,
                "theme": chunk_theme,
                "density": resource_info["density"],
                "tierBias": resource_info.get("tierBias", "low")
            })

    # Extract pairs
    pairs = []
    for node in nodes_data.get("nodes", []):
        node_id = node.get("nodeId")
        if not node_id:
            continue

        chunk_assignments = node_to_chunks.get(node_id, [])
        if not chunk_assignments:
            print(f"  ⚠️  No chunk assignments for node: {node_id}")
            continue

        # Get primary chunk
        primary_chunk = chunk_assignments[0]

        # Build INPUT
        input_data = {
            "primaryChunk": primary_chunk["chunkType"],
            "chunkCategory": primary_chunk["category"],
            "chunkTheme": primary_chunk["theme"],
            "spawnDensity": primary_chunk["density"],
            "tierBias": primary_chunk["tierBias"],
            "allChunks": [c["chunkType"] for c in chunk_assignments],
            "tier": node.get("tier", 1),
            "category": node.get("category", ""),
            "tags": node.get("metadata", {}).get("tags", [])
        }

        # Build OUTPUT (complete node JSON)
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

    pairs = []
    for skill in skills_data.get("skills", []):
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

    pairs = []
    for title in titles_data.get("titles", []):
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
# MAIN EXTRACTION
# ============================================================================
def main():
    """Run all extraction functions"""
    print("=" * 80)
    print("LLM TRAINING DATA GENERATOR")
    print("=" * 80)

    # Create output directory
    OUTPUT_DIR.mkdir(exist_ok=True)

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

#!/usr/bin/env python3
"""
Unified JSON Creator - Comprehensive tool for creating and validating all JSON types
Supports all 13 JSON types with cross-reference validation and smart linking
"""

import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox, filedialog
import json
import os
from pathlib import Path
from typing import Dict, List, Any, Tuple, Optional
from dataclasses import dataclass
from enum import Enum
import re


# ============================================================================
# SCHEMA DEFINITIONS
# ============================================================================

class FieldType(Enum):
    """Field data types"""
    STRING = "string"
    INTEGER = "integer"
    FLOAT = "float"
    BOOLEAN = "boolean"
    OBJECT = "object"
    ARRAY = "array"
    ENUM = "enum"
    REFERENCE = "reference"  # Links to another JSON type


@dataclass
class FieldDefinition:
    """Defines a field in a JSON schema"""
    name: str
    field_type: FieldType
    required: bool = False
    default: Any = None
    enum_values: List[str] = None
    reference_type: str = None  # Which JSON type this references
    description: str = ""
    nested_fields: Dict[str, 'FieldDefinition'] = None  # For objects
    array_item_type: FieldType = None  # For arrays


class JSONSchemas:
    """Complete schema definitions for all 13 JSON types"""

    @staticmethod
    def get_schema(json_type: str) -> Dict[str, FieldDefinition]:
        """Get schema for a specific JSON type"""
        schemas = {
            "items": JSONSchemas._items_schema(),
            "materials": JSONSchemas._materials_schema(),
            "recipes": JSONSchemas._recipes_schema(),
            "placements": JSONSchemas._placements_schema(),
            "skills": JSONSchemas._skills_schema(),
            "quests": JSONSchemas._quests_schema(),
            "npcs": JSONSchemas._npcs_schema(),
            "titles": JSONSchemas._titles_schema(),
            "classes": JSONSchemas._classes_schema(),
            "enemies": JSONSchemas._enemies_schema(),
            "resource_nodes": JSONSchemas._resource_nodes_schema(),
        }
        return schemas.get(json_type, {})

    @staticmethod
    def _items_schema() -> Dict[str, FieldDefinition]:
        """Items/Equipment schema"""
        return {
            "itemId": FieldDefinition(
                "itemId", FieldType.STRING, required=True,
                description="Unique identifier (snake_case)"
            ),
            "name": FieldDefinition(
                "name", FieldType.STRING, required=True,
                description="Display name"
            ),
            "category": FieldDefinition(
                "category", FieldType.ENUM, required=True,
                enum_values=["equipment", "consumable", "material"],
                description="MUST be 'equipment' for items to load!"
            ),
            "type": FieldDefinition(
                "type", FieldType.ENUM, required=True,
                enum_values=["weapon", "armor", "tool", "consumable", "device", "station"],
                description="Item type"
            ),
            "subtype": FieldDefinition(
                "subtype", FieldType.ENUM, required=False,
                enum_values=[
                    "dagger", "shortsword", "longsword", "greatsword", "spear", "pike",
                    "shortbow", "longbow", "staff", "wand",
                    "helmet", "chestplate", "leggings", "boots", "gloves",
                    "pickaxe", "axe", "hoe", "hammer"
                ],
                description="Specific subtype"
            ),
            "tier": FieldDefinition(
                "tier", FieldType.INTEGER, required=True,
                enum_values=["1", "2", "3", "4"],
                description="Tier (1-4): T1=1×, T2=2×, T3=4×, T4=8×"
            ),
            "rarity": FieldDefinition(
                "rarity", FieldType.ENUM, required=True,
                enum_values=["common", "uncommon", "rare", "epic", "legendary", "artifact"],
                description="Item rarity"
            ),
            "slot": FieldDefinition(
                "slot", FieldType.ENUM, required=False,
                enum_values=["mainHand", "offHand", "helmet", "chestplate", "leggings", "boots", "gloves", "ring", "necklace"],
                description="Equipment slot"
            ),
            "range": FieldDefinition(
                "range", FieldType.FLOAT, required=False, default=1.0,
                description="Weapon range (MUST be float: 1.0 not 1)"
            ),
            "statMultipliers": FieldDefinition(
                "statMultipliers", FieldType.OBJECT, required=False,
                nested_fields={
                    "damage": FieldDefinition("damage", FieldType.FLOAT, default=1.0),
                    "attackSpeed": FieldDefinition("attackSpeed", FieldType.FLOAT, default=1.0),
                    "durability": FieldDefinition("durability", FieldType.FLOAT, default=1.0),
                    "weight": FieldDefinition("weight", FieldType.FLOAT, default=1.0),
                }
            ),
            "requirements": FieldDefinition(
                "requirements", FieldType.OBJECT, required=False,
                nested_fields={
                    "level": FieldDefinition("level", FieldType.INTEGER, default=1),
                    "stats": FieldDefinition("stats", FieldType.OBJECT),
                }
            ),
            "flags": FieldDefinition(
                "flags", FieldType.OBJECT, required=False,
                nested_fields={
                    "stackable": FieldDefinition("stackable", FieldType.BOOLEAN, default=False),
                    "placeable": FieldDefinition("placeable", FieldType.BOOLEAN, default=False),
                    "repairable": FieldDefinition("repairable", FieldType.BOOLEAN, default=True),
                }
            ),
            "metadata": FieldDefinition(
                "metadata", FieldType.OBJECT, required=False,
                nested_fields={
                    "narrative": FieldDefinition("narrative", FieldType.STRING),
                    "tags": FieldDefinition("tags", FieldType.ARRAY, array_item_type=FieldType.STRING),
                }
            ),
        }

    @staticmethod
    def _materials_schema() -> Dict[str, FieldDefinition]:
        """Materials schema"""
        return {
            "materialId": FieldDefinition(
                "materialId", FieldType.STRING, required=True,
                description="Unique identifier (snake_case)"
            ),
            "name": FieldDefinition("name", FieldType.STRING, required=True),
            "tier": FieldDefinition(
                "tier", FieldType.INTEGER, required=True,
                enum_values=["1", "2", "3", "4"]
            ),
            "category": FieldDefinition(
                "category", FieldType.ENUM, required=True,
                enum_values=["ore", "metal", "wood", "gem", "elemental", "monster_drop", "herb", "reagent"]
            ),
            "rarity": FieldDefinition(
                "rarity", FieldType.ENUM, required=True,
                enum_values=["common", "uncommon", "rare", "epic", "legendary"]
            ),
            "description": FieldDefinition("description", FieldType.STRING),
            "maxStack": FieldDefinition(
                "maxStack", FieldType.INTEGER, default=99,
                description="99 for raw, 256 for processed"
            ),
            "properties": FieldDefinition("properties", FieldType.OBJECT),
        }

    @staticmethod
    def _recipes_schema() -> Dict[str, FieldDefinition]:
        """Recipes schema (varies by discipline)"""
        return {
            "recipeId": FieldDefinition(
                "recipeId", FieldType.STRING, required=True,
                description="Format: {discipline}_{item_id}"
            ),
            "outputId": FieldDefinition(
                "outputId", FieldType.REFERENCE, required=False,
                reference_type="items",
                description="Item produced (for smithing/alchemy/engineering)"
            ),
            "enchantmentId": FieldDefinition(
                "enchantmentId", FieldType.STRING, required=False,
                description="For enchanting only"
            ),
            "enchantmentName": FieldDefinition(
                "enchantmentName", FieldType.STRING, required=False,
                description="For enchanting only"
            ),
            "outputs": FieldDefinition(
                "outputs", FieldType.ARRAY, required=False,
                description="For refining only (uses outputs array instead of outputId)"
            ),
            "outputQty": FieldDefinition(
                "outputQty", FieldType.INTEGER, default=1,
                description="Quantity produced"
            ),
            "stationType": FieldDefinition(
                "stationType", FieldType.ENUM, required=True,
                enum_values=["smithing", "alchemy", "refining", "engineering", "enchanting"],
                description="Use 'enchanting' NOT 'adornments'"
            ),
            "stationTier": FieldDefinition(
                "stationTier", FieldType.INTEGER, required=True,
                enum_values=["1", "2", "3", "4"]
            ),
            "stationTierRequired": FieldDefinition(
                "stationTierRequired", FieldType.INTEGER, required=False,
                description="Alternative field name for refining"
            ),
            "gridSize": FieldDefinition(
                "gridSize", FieldType.STRING, required=False,
                description="Auto: T1=3x3, T2=5x5, T3=7x7, T4=9x9"
            ),
            "inputs": FieldDefinition(
                "inputs", FieldType.ARRAY, required=True,
                description="Array of {materialId, quantity} - references materials"
            ),
            "miniGame": FieldDefinition(
                "miniGame", FieldType.OBJECT, required=False,
                nested_fields={
                    "type": FieldDefinition("type", FieldType.STRING),
                    "difficulty": FieldDefinition("difficulty", FieldType.ENUM,
                        enum_values=["easy", "moderate", "hard", "extreme"]),
                    "baseTime": FieldDefinition("baseTime", FieldType.INTEGER),
                }
            ),
            "applicableTo": FieldDefinition(
                "applicableTo", FieldType.ARRAY, required=False,
                description="For enchanting: what item types can be enchanted"
            ),
            "effect": FieldDefinition(
                "effect", FieldType.OBJECT, required=False,
                description="For enchanting: the enchantment effect"
            ),
        }

    @staticmethod
    def _placements_schema() -> Dict[str, FieldDefinition]:
        """Placements schema (4 different formats)"""
        return {
            "recipeId": FieldDefinition(
                "recipeId", FieldType.REFERENCE, required=True,
                reference_type="recipes",
                description="Must reference existing recipe"
            ),
            "discipline": FieldDefinition(
                "discipline", FieldType.ENUM, required=True,
                enum_values=["smithing", "alchemy", "refining", "engineering", "enchanting"]
            ),
            "placementMap": FieldDefinition(
                "placementMap", FieldType.OBJECT, required=False,
                description="For grid-based (smithing/enchanting): {'row,col': 'materialId'}"
            ),
            "coreInputs": FieldDefinition(
                "coreInputs", FieldType.ARRAY, required=False,
                description="For refining (hub-spoke): center materials"
            ),
            "surroundingInputs": FieldDefinition(
                "surroundingInputs", FieldType.ARRAY, required=False,
                description="For refining (hub-spoke): surrounding materials"
            ),
            "ingredients": FieldDefinition(
                "ingredients", FieldType.ARRAY, required=False,
                description="For alchemy (sequential): [{slot, materialId, quantity}]"
            ),
            "slots": FieldDefinition(
                "slots", FieldType.ARRAY, required=False,
                description="For engineering (slot-based): [{type, materialId, quantity}]"
            ),
            "metadata": FieldDefinition(
                "metadata", FieldType.OBJECT, required=False,
                nested_fields={
                    "gridSize": FieldDefinition("gridSize", FieldType.STRING),
                    "narrative": FieldDefinition("narrative", FieldType.STRING),
                }
            ),
        }

    @staticmethod
    def _skills_schema() -> Dict[str, FieldDefinition]:
        """Skills schema"""
        return {
            "skillId": FieldDefinition(
                "skillId", FieldType.STRING, required=True,
                description="Unique identifier (snake_case)"
            ),
            "name": FieldDefinition("name", FieldType.STRING, required=True),
            "tier": FieldDefinition("tier", FieldType.INTEGER, required=True, enum_values=["1", "2", "3", "4"]),
            "rarity": FieldDefinition(
                "rarity", FieldType.ENUM, required=True,
                enum_values=["common", "uncommon", "rare", "epic", "legendary"]
            ),
            "categories": FieldDefinition(
                "categories", FieldType.ARRAY, required=True,
                description="Array of skill categories"
            ),
            "description": FieldDefinition("description", FieldType.STRING, required=True),
            "narrative": FieldDefinition("narrative", FieldType.STRING),
            "effect": FieldDefinition(
                "effect", FieldType.OBJECT, required=True,
                nested_fields={
                    "type": FieldDefinition("type", FieldType.ENUM,
                        enum_values=["empower", "quicken", "fortify", "regenerate", "leech", "pierce", "cleave", "channel", "transmute", "resonate"]),
                    "category": FieldDefinition("category", FieldType.STRING),
                    "magnitude": FieldDefinition("magnitude", FieldType.ENUM,
                        enum_values=["minor", "moderate", "major", "extreme"]),
                    "target": FieldDefinition("target", FieldType.ENUM,
                        enum_values=["self", "single", "area", "all"]),
                    "duration": FieldDefinition("duration", FieldType.ENUM,
                        enum_values=["instant", "brief", "moderate", "long", "extended"]),
                    "additionalEffects": FieldDefinition("additionalEffects", FieldType.ARRAY),
                }
            ),
            "cost": FieldDefinition(
                "cost", FieldType.OBJECT, required=True,
                nested_fields={
                    "mana": FieldDefinition("mana", FieldType.ENUM,
                        enum_values=["low", "moderate", "high", "extreme"]),
                    "cooldown": FieldDefinition("cooldown", FieldType.ENUM,
                        enum_values=["short", "moderate", "long", "extreme"]),
                }
            ),
            "evolution": FieldDefinition(
                "evolution", FieldType.OBJECT, required=False,
                nested_fields={
                    "canEvolve": FieldDefinition("canEvolve", FieldType.BOOLEAN),
                    "nextSkillId": FieldDefinition("nextSkillId", FieldType.REFERENCE, reference_type="skills"),
                    "requirement": FieldDefinition("requirement", FieldType.STRING),
                }
            ),
            "requirements": FieldDefinition(
                "requirements", FieldType.OBJECT, required=False,
                nested_fields={
                    "characterLevel": FieldDefinition("characterLevel", FieldType.INTEGER, default=1),
                    "stats": FieldDefinition("stats", FieldType.OBJECT),
                    "titles": FieldDefinition("titles", FieldType.ARRAY),
                }
            ),
        }

    @staticmethod
    def _quests_schema() -> Dict[str, FieldDefinition]:
        """Quests schema"""
        return {
            "quest_id": FieldDefinition(
                "quest_id", FieldType.STRING, required=True,
                description="Unique identifier (snake_case)"
            ),
            "title": FieldDefinition("title", FieldType.STRING, required=True),
            "description": FieldDefinition("description", FieldType.STRING, required=True),
            "npc_id": FieldDefinition(
                "npc_id", FieldType.REFERENCE, required=True,
                reference_type="npcs",
                description="Must reference existing NPC"
            ),
            "objectives": FieldDefinition(
                "objectives", FieldType.OBJECT, required=True,
                nested_fields={
                    "type": FieldDefinition("type", FieldType.ENUM,
                        enum_values=["gather", "combat", "craft", "explore"]),
                    "items": FieldDefinition("items", FieldType.ARRAY),
                    "enemies": FieldDefinition("enemies", FieldType.ARRAY),
                }
            ),
            "rewards": FieldDefinition(
                "rewards", FieldType.OBJECT, required=True,
                nested_fields={
                    "experience": FieldDefinition("experience", FieldType.INTEGER),
                    "health_restore": FieldDefinition("health_restore", FieldType.INTEGER),
                    "items": FieldDefinition("items", FieldType.ARRAY,
                        description="Array of {item_id (REFERENCE), quantity}"),
                    "skills": FieldDefinition("skills", FieldType.ARRAY,
                        description="Array of skill IDs (REFERENCES)"),
                    "title": FieldDefinition("title", FieldType.REFERENCE, reference_type="titles"),
                }
            ),
            "completion_dialogue": FieldDefinition(
                "completion_dialogue", FieldType.ARRAY, required=False,
                description="Array of dialogue strings"
            ),
        }

    @staticmethod
    def _npcs_schema() -> Dict[str, FieldDefinition]:
        """NPCs schema"""
        return {
            "npc_id": FieldDefinition(
                "npc_id", FieldType.STRING, required=True,
                description="Unique identifier (snake_case)"
            ),
            "name": FieldDefinition("name", FieldType.STRING, required=True),
            "position": FieldDefinition(
                "position", FieldType.OBJECT, required=True,
                nested_fields={
                    "x": FieldDefinition("x", FieldType.FLOAT),
                    "y": FieldDefinition("y", FieldType.FLOAT),
                    "z": FieldDefinition("z", FieldType.FLOAT, default=0.0),
                }
            ),
            "sprite_color": FieldDefinition(
                "sprite_color", FieldType.ARRAY, required=True,
                description="RGB array [R, G, B]"
            ),
            "interaction_radius": FieldDefinition(
                "interaction_radius", FieldType.FLOAT, default=3.0
            ),
            "dialogue_lines": FieldDefinition(
                "dialogue_lines", FieldType.ARRAY, required=True,
                description="Array of dialogue strings"
            ),
            "quests": FieldDefinition(
                "quests", FieldType.ARRAY, required=False,
                description="Array of quest IDs (REFERENCES)"
            ),
        }

    @staticmethod
    def _titles_schema() -> Dict[str, FieldDefinition]:
        """Titles schema"""
        return {
            "titleId": FieldDefinition(
                "titleId", FieldType.STRING, required=True,
                description="Unique identifier (snake_case)"
            ),
            "name": FieldDefinition("name", FieldType.STRING, required=True),
            "titleType": FieldDefinition(
                "titleType", FieldType.ENUM, required=True,
                enum_values=["gathering", "crafting", "combat", "exploration", "social"]
            ),
            "difficultyTier": FieldDefinition(
                "difficultyTier", FieldType.ENUM, required=True,
                enum_values=["novice", "apprentice", "journeyman", "master", "grandmaster"]
            ),
            "description": FieldDefinition("description", FieldType.STRING, required=True),
            "bonuses": FieldDefinition(
                "bonuses", FieldType.OBJECT, required=False,
                description="Stat bonuses as decimal multipliers (0.10 = +10%)"
            ),
            "prerequisites": FieldDefinition(
                "prerequisites", FieldType.OBJECT, required=True,
                nested_fields={
                    "activities": FieldDefinition("activities", FieldType.OBJECT),
                    "requiredTitles": FieldDefinition("requiredTitles", FieldType.ARRAY),
                    "characterLevel": FieldDefinition("characterLevel", FieldType.INTEGER, default=0),
                }
            ),
            "acquisitionMethod": FieldDefinition(
                "acquisitionMethod", FieldType.ENUM, required=True,
                enum_values=["guaranteed_milestone", "challenge_completion", "discovery", "rare_achievement"]
            ),
            "narrative": FieldDefinition("narrative", FieldType.STRING),
        }

    @staticmethod
    def _classes_schema() -> Dict[str, FieldDefinition]:
        """Classes schema"""
        return {
            "classId": FieldDefinition(
                "classId", FieldType.STRING, required=True,
                description="Unique identifier (snake_case)"
            ),
            "name": FieldDefinition("name", FieldType.STRING, required=True),
            "description": FieldDefinition("description", FieldType.STRING, required=True),
            "primaryStats": FieldDefinition(
                "primaryStats", FieldType.ARRAY, required=True,
                description="Array of stat names (e.g., ['STR', 'VIT'])"
            ),
            "startingSkill": FieldDefinition(
                "startingSkill", FieldType.OBJECT, required=True,
                nested_fields={
                    "skillId": FieldDefinition("skillId", FieldType.REFERENCE, reference_type="skills"),
                }
            ),
            "baseStats": FieldDefinition(
                "baseStats", FieldType.OBJECT, required=True,
                description="Starting stats (STR, AGI, VIT, INT, WIS, LUK)"
            ),
        }

    @staticmethod
    def _enemies_schema() -> Dict[str, FieldDefinition]:
        """Enemies schema"""
        return {
            "enemyId": FieldDefinition(
                "enemyId", FieldType.STRING, required=True,
                description="Unique identifier (snake_case)"
            ),
            "name": FieldDefinition("name", FieldType.STRING, required=True),
            "tier": FieldDefinition("tier", FieldType.INTEGER, required=True, enum_values=["1", "2", "3", "4"]),
            "baseStats": FieldDefinition(
                "baseStats", FieldType.OBJECT, required=True,
                description="Combat stats"
            ),
            "drops": FieldDefinition(
                "drops", FieldType.ARRAY, required=False,
                description="Array of {materialId (REFERENCE), chance, quantity}"
            ),
        }

    @staticmethod
    def _resource_nodes_schema() -> Dict[str, FieldDefinition]:
        """Resource nodes schema"""
        return {
            "nodeId": FieldDefinition(
                "nodeId", FieldType.STRING, required=True,
                description="Unique identifier (snake_case)"
            ),
            "name": FieldDefinition("name", FieldType.STRING, required=True),
            "tier": FieldDefinition("tier", FieldType.INTEGER, required=True, enum_values=["1", "2", "3", "4"]),
            "gatherType": FieldDefinition(
                "gatherType", FieldType.ENUM, required=True,
                enum_values=["mining", "woodcutting", "herbalism", "fishing"]
            ),
            "drops": FieldDefinition(
                "drops", FieldType.ARRAY, required=True,
                description="Array of {materialId (REFERENCE), chance, quantity}"
            ),
            "respawnTime": FieldDefinition(
                "respawnTime", FieldType.INTEGER, required=True,
                description="Seconds to respawn"
            ),
        }


# ============================================================================
# DATA LOADER - Loads all existing JSONs from files
# ============================================================================

class DataLoader:
    """Loads all existing JSON data for validation and reference"""

    def __init__(self, base_path: str = None):
        if base_path is None:
            # Auto-detect from current file location
            base_path = Path(__file__).parent.parent.parent
        self.base_path = Path(base_path)
        self.data_cache: Dict[str, List[Dict]] = {}
        self.file_mapping: Dict[str, List[str]] = {}  # Maps JSON type to file paths

    def load_all(self):
        """Load all JSON data into cache"""
        self._load_items()
        self._load_materials()
        self._load_recipes()
        self._load_placements()
        self._load_skills()
        self._load_quests()
        self._load_npcs()
        self._load_titles()
        self._load_classes()
        self._load_enemies()
        self._load_resource_nodes()

    def _load_json_file(self, file_path: Path) -> List[Dict]:
        """Load a single JSON file"""
        try:
            if file_path.exists():
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    # Handle both array and object formats
                    if isinstance(data, dict):
                        # If it's a dict, flatten nested arrays
                        all_items = []
                        for key, value in data.items():
                            if key == "metadata":
                                continue  # Skip metadata
                            if isinstance(value, list):
                                # Flatten the array
                                all_items.extend(value)
                            elif isinstance(value, dict) and key not in ["metadata"]:
                                # Could be a single item
                                all_items.append(value)
                        return all_items if all_items else [data]
                    return data if isinstance(data, list) else [data]
        except Exception as e:
            print(f"Error loading {file_path}: {e}")
        return []

    def _load_items(self):
        """Load all item files"""
        items_dir = self.base_path / "items.JSON"
        all_items = []
        files = []

        if items_dir.exists():
            # Handle both .JSON and .json extensions
            for pattern in ["items-*.JSON", "items-*.json"]:
                for file_path in items_dir.glob(pattern):
                    items = self._load_json_file(file_path)
                    all_items.extend(items)
                    if str(file_path) not in files:
                        files.append(str(file_path))

        self.data_cache["items"] = all_items
        self.file_mapping["items"] = files

    def _load_materials(self):
        """Load materials from definitions and items"""
        materials = []

        # Try to load from any dedicated materials file
        defs_dir = self.base_path / "Definitions.JSON"
        if defs_dir.exists():
            for pattern in ["*material*.JSON", "*material*.json"]:
                for file_path in defs_dir.glob(pattern):
                    materials.extend(self._load_json_file(file_path))

        # Also extract from items-materials file
        items_dir = self.base_path / "items.JSON"
        if items_dir.exists():
            for pattern in ["items-materials-*.JSON", "items-materials-*.json"]:
                for file_path in items_dir.glob(pattern):
                    mats = self._load_json_file(file_path)
                    materials.extend(mats)

        # Extract unique material IDs from recipes as fallback
        if not materials and "recipes" in self.data_cache:
            material_ids = set()
            for recipe in self.data_cache["recipes"]:
                for inp in recipe.get("inputs", []):
                    if isinstance(inp, dict) and "materialId" in inp:
                        mat_id = inp["materialId"]
                        material_ids.add(mat_id)
            # Create minimal material objects
            materials = [{"materialId": mat_id, "name": mat_id.replace("_", " ").title()}
                        for mat_id in sorted(material_ids)]

        self.data_cache["materials"] = materials
        self.file_mapping["materials"] = []

    def _load_recipes(self):
        """Load all recipe files"""
        recipes_dir = self.base_path / "recipes.JSON"
        all_recipes = []
        files = []

        if recipes_dir.exists():
            # Handle both .JSON and .json extensions
            for pattern in ["recipes-*.JSON", "recipes-*.json"]:
                for file_path in recipes_dir.glob(pattern):
                    recipes = self._load_json_file(file_path)
                    all_recipes.extend(recipes)
                    if str(file_path) not in files:
                        files.append(str(file_path))

        self.data_cache["recipes"] = all_recipes
        self.file_mapping["recipes"] = files

    def _load_placements(self):
        """Load all placement files"""
        placements_dir = self.base_path / "placements.JSON"
        all_placements = []
        files = []

        if placements_dir.exists():
            for pattern in ["placements-*.JSON", "placements-*.json"]:
                for file_path in placements_dir.glob(pattern):
                    placements = self._load_json_file(file_path)
                    all_placements.extend(placements)
                    if str(file_path) not in files:
                        files.append(str(file_path))

        self.data_cache["placements"] = all_placements
        self.file_mapping["placements"] = files

    def _load_skills(self):
        """Load skill files"""
        skills_dir = self.base_path / "Skills"
        all_skills = []
        files = []

        if skills_dir.exists():
            for pattern in ["*.JSON", "*.json"]:
                for file_path in skills_dir.glob(pattern):
                    skills = self._load_json_file(file_path)
                    all_skills.extend(skills)
                    if str(file_path) not in files:
                        files.append(str(file_path))

        self.data_cache["skills"] = all_skills
        self.file_mapping["skills"] = files

    def _load_quests(self):
        """Load quest files"""
        prog_dir = self.base_path / "progression"
        quests = self._load_json_file(prog_dir / "quests-1.JSON")

        self.data_cache["quests"] = quests
        self.file_mapping["quests"] = [str(prog_dir / "quests-1.JSON")]

    def _load_npcs(self):
        """Load NPC files"""
        prog_dir = self.base_path / "progression"
        npcs = self._load_json_file(prog_dir / "npcs-1.JSON")

        self.data_cache["npcs"] = npcs
        self.file_mapping["npcs"] = [str(prog_dir / "npcs-1.JSON")]

    def _load_titles(self):
        """Load title files"""
        prog_dir = self.base_path / "progression"
        titles = self._load_json_file(prog_dir / "titles-1.JSON")

        self.data_cache["titles"] = titles
        self.file_mapping["titles"] = [str(prog_dir / "titles-1.JSON")]

    def _load_classes(self):
        """Load class files"""
        prog_dir = self.base_path / "progression"
        classes = self._load_json_file(prog_dir / "classes-1.JSON")

        self.data_cache["classes"] = classes
        self.file_mapping["classes"] = [str(prog_dir / "classes-1.JSON")]

    def _load_enemies(self):
        """Load enemy files"""
        defs_dir = self.base_path / "Definitions.JSON"
        enemies = self._load_json_file(defs_dir / "hostile-entities-1.JSON")

        self.data_cache["enemies"] = enemies
        self.file_mapping["enemies"] = [str(defs_dir / "hostile-entities-1.JSON")]

    def _load_resource_nodes(self):
        """Load resource node files"""
        defs_dir = self.base_path / "Definitions.JSON"
        nodes = self._load_json_file(defs_dir / "resource-nodes-1.JSON")

        self.data_cache["resource_nodes"] = nodes
        self.file_mapping["resource_nodes"] = [str(defs_dir / "resource-nodes-1.JSON")]

    def get_all(self, json_type: str) -> List[Dict]:
        """Get all items of a specific type"""
        return self.data_cache.get(json_type, [])

    def get_ids(self, json_type: str) -> List[str]:
        """Get all IDs for a specific type"""
        items = self.get_all(json_type)
        id_fields = {
            "items": "itemId",
            "materials": "materialId",
            "recipes": "recipeId",
            "placements": "recipeId",
            "skills": "skillId",
            "quests": "quest_id",
            "npcs": "npc_id",
            "titles": "titleId",
            "classes": "classId",
            "enemies": "enemyId",
            "resource_nodes": "nodeId",
        }
        id_field = id_fields.get(json_type, "id")
        return [item.get(id_field) for item in items if item.get(id_field)]

    def get_file_for_type(self, json_type: str, discipline: str = None) -> str:
        """Get the appropriate file path for saving a new JSON of this type"""
        files = self.file_mapping.get(json_type, [])

        if not files:
            # Create default file path
            type_dirs = {
                "items": "items.JSON/items-unified.JSON",
                "recipes": "recipes.JSON/recipes-unified.JSON",
                "placements": "placements.JSON/placements-unified.JSON",
                "skills": "Skills/skills-unified.JSON",
                "quests": "progression/quests-1.JSON",
                "npcs": "progression/npcs-1.JSON",
                "titles": "progression/titles-1.JSON",
                "classes": "progression/classes-1.JSON",
                "enemies": "Definitions.JSON/hostile-entities-1.JSON",
                "resource_nodes": "Definitions.JSON/resource-nodes-1.JSON",
            }
            return str(self.base_path / type_dirs.get(json_type, f"{json_type}.JSON"))

        # If discipline is specified, try to find matching file
        if discipline and len(files) > 1:
            for file in files:
                if discipline.lower() in file.lower():
                    return file

        # Return first file or unified file
        unified_file = [f for f in files if 'unified' in f.lower()]
        return unified_file[0] if unified_file else files[0]


# ============================================================================
# VALIDATION ENGINE
# ============================================================================

@dataclass
class ValidationIssue:
    """Represents a validation issue"""
    severity: str  # "error", "warning", "info"
    field: str
    message: str
    suggestion: str = ""


class ValidationEngine:
    """Validates JSON data with cross-reference checking"""

    def __init__(self, data_loader: DataLoader):
        self.data_loader = data_loader

    def validate(self, json_type: str, data: Dict) -> List[ValidationIssue]:
        """Validate a JSON object"""
        issues = []
        schema = JSONSchemas.get_schema(json_type)

        # Check required fields
        for field_name, field_def in schema.items():
            if field_def.required and field_name not in data:
                issues.append(ValidationIssue(
                    "error", field_name,
                    f"Required field '{field_name}' is missing",
                    f"Add {field_name}: {self._get_default_value(field_def)}"
                ))

        # Check field types and references
        for field_name, value in data.items():
            if field_name not in schema:
                issues.append(ValidationIssue(
                    "warning", field_name,
                    f"Unknown field '{field_name}' (not in schema)",
                    "This field may be ignored or cause issues"
                ))
                continue

            field_def = schema[field_name]

            # Validate references
            if field_def.field_type == FieldType.REFERENCE:
                ref_issues = self._validate_reference(field_name, value, field_def.reference_type)
                issues.extend(ref_issues)

            # Validate enums
            elif field_def.field_type == FieldType.ENUM:
                if value not in field_def.enum_values:
                    issues.append(ValidationIssue(
                        "error", field_name,
                        f"Invalid value '{value}'. Must be one of: {field_def.enum_values}",
                        f"Change to one of: {', '.join(field_def.enum_values)}"
                    ))

        # Check for duplicate IDs
        id_issue = self._check_duplicate_id(json_type, data)
        if id_issue:
            issues.append(id_issue)

        # Type-specific validations
        issues.extend(self._validate_specific(json_type, data))

        return issues

    def _validate_reference(self, field_name: str, value: Any, ref_type: str) -> List[ValidationIssue]:
        """Validate that a reference points to an existing item"""
        issues = []

        if not value:
            return issues

        # Handle array of references
        if isinstance(value, list):
            for item in value:
                if isinstance(item, dict) and 'item_id' in item:
                    ref_id = item['item_id']
                elif isinstance(item, dict) and 'materialId' in item:
                    ref_id = item['materialId']
                elif isinstance(item, str):
                    ref_id = item
                else:
                    continue

                if ref_id not in self.data_loader.get_ids(ref_type):
                    issues.append(ValidationIssue(
                        "error", field_name,
                        f"Reference '{ref_id}' not found in {ref_type}",
                        f"Create this {ref_type} first or choose from: {', '.join(self.data_loader.get_ids(ref_type)[:5])}"
                    ))

        # Handle single reference
        elif isinstance(value, str):
            if value not in self.data_loader.get_ids(ref_type):
                available_ids = self.data_loader.get_ids(ref_type)
                issues.append(ValidationIssue(
                    "error", field_name,
                    f"Reference '{value}' not found in {ref_type}",
                    f"Available {ref_type}: {', '.join(available_ids[:10]) if available_ids else 'None'}"
                ))

        return issues

    def _check_duplicate_id(self, json_type: str, data: Dict) -> Optional[ValidationIssue]:
        """Check if the ID already exists"""
        id_fields = {
            "items": "itemId",
            "materials": "materialId",
            "recipes": "recipeId",
            "placements": "recipeId",
            "skills": "skillId",
            "quests": "quest_id",
            "npcs": "npc_id",
            "titles": "titleId",
            "classes": "classId",
            "enemies": "enemyId",
            "resource_nodes": "nodeId",
        }

        id_field = id_fields.get(json_type)
        if not id_field or id_field not in data:
            return None

        new_id = data[id_field]
        existing_ids = self.data_loader.get_ids(json_type)

        if new_id in existing_ids:
            return ValidationIssue(
                "error", id_field,
                f"Duplicate ID '{new_id}' already exists in {json_type}",
                "Choose a unique ID or load the existing item to edit"
            )

        return None

    def _validate_specific(self, json_type: str, data: Dict) -> List[ValidationIssue]:
        """Type-specific validation rules"""
        issues = []

        if json_type == "items":
            # Must have category="equipment" to load
            if data.get("category") != "equipment":
                issues.append(ValidationIssue(
                    "warning", "category",
                    "Items with category != 'equipment' may not load in game",
                    "Set category to 'equipment' for equipment items"
                ))

            # Range must be float
            if "range" in data and isinstance(data["range"], int):
                issues.append(ValidationIssue(
                    "error", "range",
                    "Range must be a float (e.g., 1.0 not 1)",
                    f"Change to {float(data['range'])}"
                ))

        elif json_type == "recipes":
            # Validate inputs reference materials
            if "inputs" in data:
                for inp in data["inputs"]:
                    if isinstance(inp, dict) and "materialId" in inp:
                        mat_id = inp["materialId"]
                        # Check in both materials and items
                        if (mat_id not in self.data_loader.get_ids("materials") and
                            mat_id not in self.data_loader.get_ids("items")):
                            issues.append(ValidationIssue(
                                "error", "inputs",
                                f"Input material '{mat_id}' not found",
                                "Create this material/item first"
                            ))

            # Enchanting specific validation
            if data.get("stationType") == "enchanting":
                if "enchantmentId" not in data:
                    issues.append(ValidationIssue(
                        "warning", "enchantmentId",
                        "Enchanting recipes should have 'enchantmentId' not 'outputId'",
                        "Add enchantmentId and enchantmentName fields"
                    ))

        elif json_type == "quests":
            # Validate quest rewards reference existing items/skills/titles
            if "rewards" in data:
                rewards = data["rewards"]

                # Check item rewards
                if "items" in rewards:
                    for item in rewards["items"]:
                        if isinstance(item, dict) and "item_id" in item:
                            if item["item_id"] not in self.data_loader.get_ids("items"):
                                issues.append(ValidationIssue(
                                    "error", "rewards.items",
                                    f"Reward item '{item['item_id']}' not found",
                                    "Create this item first"
                                ))

                # Check skill rewards
                if "skills" in rewards:
                    for skill_id in rewards["skills"]:
                        if skill_id not in self.data_loader.get_ids("skills"):
                            issues.append(ValidationIssue(
                                "error", "rewards.skills",
                                f"Reward skill '{skill_id}' not found",
                                "Create this skill first"
                            ))

                # Check title reward
                if "title" in rewards:
                    if rewards["title"] not in self.data_loader.get_ids("titles"):
                        issues.append(ValidationIssue(
                            "error", "rewards.title",
                            f"Reward title '{rewards['title']}' not found",
                            "Create this title first"
                        ))

        elif json_type == "placements":
            # Validate placement materials match recipe inputs
            recipe_id = data.get("recipeId")
            if recipe_id:
                # Find the recipe
                recipes = [r for r in self.data_loader.get_all("recipes") if r.get("recipeId") == recipe_id]
                if recipes:
                    recipe = recipes[0]
                    # Check if placement materials are in recipe inputs
                    if "placementMap" in data:
                        for pos, mat_id in data["placementMap"].items():
                            recipe_inputs = [inp.get("materialId") for inp in recipe.get("inputs", [])]
                            if mat_id not in recipe_inputs:
                                issues.append(ValidationIssue(
                                    "warning", "placementMap",
                                    f"Material '{mat_id}' at position {pos} not in recipe inputs",
                                    f"Recipe inputs: {', '.join(recipe_inputs)}"
                                ))

        return issues

    def _get_default_value(self, field_def: FieldDefinition) -> str:
        """Get a default value suggestion for a field"""
        if field_def.default is not None:
            return f'"{field_def.default}"' if isinstance(field_def.default, str) else str(field_def.default)

        if field_def.field_type == FieldType.STRING:
            return '""'
        elif field_def.field_type == FieldType.INTEGER:
            return "0"
        elif field_def.field_type == FieldType.FLOAT:
            return "0.0"
        elif field_def.field_type == FieldType.BOOLEAN:
            return "false"
        elif field_def.field_type == FieldType.ARRAY:
            return "[]"
        elif field_def.field_type == FieldType.OBJECT:
            return "{}"
        elif field_def.field_type == FieldType.ENUM and field_def.enum_values:
            return f'"{field_def.enum_values[0]}"'

        return '""'


# ============================================================================
# GUI APPLICATION
# ============================================================================

class UnifiedJSONCreatorGUI:
    """Main GUI application for creating JSONs"""

    def __init__(self, root):
        self.root = root
        self.root.title("Unified JSON Creator")
        self.root.geometry("1600x900")

        # Initialize data loader and validator
        self.data_loader = DataLoader()
        self.data_loader.load_all()
        self.validator = ValidationEngine(self.data_loader)

        # Current state
        self.current_json_type = "items"
        self.current_data = {}
        self.field_widgets = {}

        # Create UI
        self._create_ui()

        # Load initial type
        self._on_type_changed()

    def _create_ui(self):
        """Create the main UI layout"""

        # Top bar - JSON type selector
        top_frame = ttk.Frame(self.root, padding="10")
        top_frame.pack(fill=tk.X)

        ttk.Label(top_frame, text="JSON Type:", font=("Arial", 12, "bold")).pack(side=tk.LEFT, padx=5)

        json_types = ["items", "materials", "recipes", "placements", "skills", "quests",
                      "npcs", "titles", "classes", "enemies", "resource_nodes"]
        self.type_combo = ttk.Combobox(top_frame, values=json_types, state="readonly", width=20)
        self.type_combo.set("items")
        self.type_combo.pack(side=tk.LEFT, padx=5)
        self.type_combo.bind("<<ComboboxSelected>>", lambda e: self._on_type_changed())

        ttk.Button(top_frame, text="New", command=self._new_json).pack(side=tk.LEFT, padx=5)
        ttk.Button(top_frame, text="Save", command=self._save_json).pack(side=tk.LEFT, padx=5)
        ttk.Button(top_frame, text="Validate", command=self._validate_current).pack(side=tk.LEFT, padx=5)

        # Main content area - split into 3 panels
        main_paned = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        main_paned.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Left panel - Form for creating/editing JSON
        left_frame = ttk.Frame(main_paned)
        main_paned.add(left_frame, weight=2)

        ttk.Label(left_frame, text="JSON Editor", font=("Arial", 11, "bold")).pack(pady=5)

        # Scrollable form area
        form_canvas = tk.Canvas(left_frame)
        form_scrollbar = ttk.Scrollbar(left_frame, orient="vertical", command=form_canvas.yview)
        self.form_frame = ttk.Frame(form_canvas)

        form_canvas.configure(yscrollcommand=form_scrollbar.set)
        form_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        form_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        form_canvas_window = form_canvas.create_window((0, 0), window=self.form_frame, anchor="nw")

        def on_frame_configure(event):
            form_canvas.configure(scrollregion=form_canvas.bbox("all"))

        self.form_frame.bind("<Configure>", on_frame_configure)

        # Middle panel - Existing JSON library
        middle_frame = ttk.Frame(main_paned)
        main_paned.add(middle_frame, weight=1)

        ttk.Label(middle_frame, text="Existing JSONs", font=("Arial", 11, "bold")).pack(pady=5)

        # Search box
        search_frame = ttk.Frame(middle_frame)
        search_frame.pack(fill=tk.X, padx=5, pady=5)
        ttk.Label(search_frame, text="Search:").pack(side=tk.LEFT)
        self.search_var = tk.StringVar()
        self.search_var.trace("w", lambda *args: self._filter_library())
        ttk.Entry(search_frame, textvariable=self.search_var).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)

        # Listbox for existing items
        library_scroll = ttk.Scrollbar(middle_frame)
        library_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        self.library_listbox = tk.Listbox(middle_frame, yscrollcommand=library_scroll.set)
        self.library_listbox.pack(fill=tk.BOTH, expand=True, padx=5)
        library_scroll.config(command=self.library_listbox.yview)

        self.library_listbox.bind("<<ListboxSelect>>", self._on_library_select)

        # Right panel - Validation results and preview
        right_frame = ttk.Frame(main_paned)
        main_paned.add(right_frame, weight=1)

        ttk.Label(right_frame, text="Validation & Preview", font=("Arial", 11, "bold")).pack(pady=5)

        # Validation issues
        ttk.Label(right_frame, text="Issues:", font=("Arial", 10)).pack(anchor=tk.W, padx=5)

        validation_scroll = ttk.Scrollbar(right_frame)
        validation_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        self.validation_text = scrolledtext.ScrolledText(right_frame, height=15, wrap=tk.WORD)
        self.validation_text.pack(fill=tk.BOTH, expand=False, padx=5, pady=5)

        # JSON preview
        ttk.Label(right_frame, text="JSON Preview:", font=("Arial", 10)).pack(anchor=tk.W, padx=5, pady=(10, 0))

        self.preview_text = scrolledtext.ScrolledText(right_frame, height=20, wrap=tk.WORD)
        self.preview_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

    def _on_type_changed(self):
        """Handle JSON type selection change"""
        self.current_json_type = self.type_combo.get()
        self._build_form()
        self._update_library()
        self._new_json()

    def _build_form(self):
        """Build the form based on current JSON type schema"""
        # Clear existing form
        for widget in self.form_frame.winfo_children():
            widget.destroy()

        self.field_widgets = {}

        schema = JSONSchemas.get_schema(self.current_json_type)

        row = 0
        for field_name, field_def in schema.items():
            # Field label
            label_text = field_name
            if field_def.required:
                label_text += " *"

            label = ttk.Label(self.form_frame, text=label_text, font=("Arial", 9, "bold"))
            label.grid(row=row, column=0, sticky=tk.W, padx=5, pady=5)

            # Field description
            if field_def.description:
                desc_label = ttk.Label(self.form_frame, text=field_def.description,
                                      font=("Arial", 8), foreground="gray")
                desc_label.grid(row=row+1, column=0, columnspan=2, sticky=tk.W, padx=20)

            # Field widget based on type
            widget = self._create_field_widget(field_name, field_def)
            widget.grid(row=row, column=1, sticky=tk.EW, padx=5, pady=5)

            self.field_widgets[field_name] = widget

            row += 2 if field_def.description else 1

        self.form_frame.grid_columnconfigure(1, weight=1)

    def _create_field_widget(self, field_name: str, field_def: FieldDefinition) -> tk.Widget:
        """Create appropriate widget for a field"""

        # ENUM fields - use combobox
        if field_def.field_type == FieldType.ENUM:
            widget = ttk.Combobox(self.form_frame, values=field_def.enum_values or [], width=30)
            if field_def.default:
                widget.set(field_def.default)
            return widget

        # REFERENCE fields - use combobox with existing IDs
        elif field_def.field_type == FieldType.REFERENCE:
            ref_ids = self.data_loader.get_ids(field_def.reference_type)
            widget = ttk.Combobox(self.form_frame, values=ref_ids, width=30)
            return widget

        # BOOLEAN fields - use checkbox
        elif field_def.field_type == FieldType.BOOLEAN:
            var = tk.BooleanVar(value=field_def.default or False)
            widget = ttk.Checkbutton(self.form_frame, variable=var)
            widget.var = var
            return widget

        # INTEGER/FLOAT fields - use entry with validation
        elif field_def.field_type in [FieldType.INTEGER, FieldType.FLOAT]:
            widget = ttk.Entry(self.form_frame, width=30)
            if field_def.default is not None:
                widget.insert(0, str(field_def.default))
            return widget

        # ARRAY/OBJECT fields - use text widget
        elif field_def.field_type in [FieldType.ARRAY, FieldType.OBJECT]:
            frame = ttk.Frame(self.form_frame)
            widget = scrolledtext.ScrolledText(frame, height=4, width=30)
            widget.pack(fill=tk.BOTH, expand=True)
            default = field_def.default or ("[]" if field_def.field_type == FieldType.ARRAY else "{}")
            widget.insert("1.0", json.dumps(default, indent=2) if not isinstance(default, str) else default)
            return frame

        # STRING fields - use entry
        else:
            widget = ttk.Entry(self.form_frame, width=30)
            if field_def.default:
                widget.insert(0, field_def.default)
            return widget

    def _update_library(self):
        """Update the library list with existing JSONs of current type"""
        self.library_listbox.delete(0, tk.END)

        items = self.data_loader.get_all(self.current_json_type)

        # Get ID field for this type
        id_fields = {
            "items": "itemId",
            "materials": "materialId",
            "recipes": "recipeId",
            "placements": "recipeId",
            "skills": "skillId",
            "quests": "quest_id",
            "npcs": "npc_id",
            "titles": "titleId",
            "classes": "classId",
            "enemies": "enemyId",
            "resource_nodes": "nodeId",
        }
        id_field = id_fields.get(self.current_json_type, "id")

        for item in items:
            item_id = item.get(id_field, "Unknown")
            name = item.get("name", item.get("title", ""))
            display = f"{item_id}" + (f" - {name}" if name else "")
            self.library_listbox.insert(tk.END, display)

    def _filter_library(self):
        """Filter library list based on search"""
        search_term = self.search_var.get().lower()

        self.library_listbox.delete(0, tk.END)

        items = self.data_loader.get_all(self.current_json_type)

        id_fields = {
            "items": "itemId",
            "materials": "materialId",
            "recipes": "recipeId",
            "placements": "recipeId",
            "skills": "skillId",
            "quests": "quest_id",
            "npcs": "npc_id",
            "titles": "titleId",
            "classes": "classId",
            "enemies": "enemyId",
            "resource_nodes": "nodeId",
        }
        id_field = id_fields.get(self.current_json_type, "id")

        for item in items:
            item_id = item.get(id_field, "Unknown")
            name = item.get("name", item.get("title", ""))
            display = f"{item_id}" + (f" - {name}" if name else "")

            if search_term in display.lower():
                self.library_listbox.insert(tk.END, display)

    def _on_library_select(self, event):
        """Load selected JSON from library into form"""
        selection = self.library_listbox.curselection()
        if not selection:
            return

        index = selection[0]

        # Get the actual item from filtered list
        search_term = self.search_var.get().lower()
        items = self.data_loader.get_all(self.current_json_type)

        if search_term:
            id_fields = {
                "items": "itemId",
                "materials": "materialId",
                "recipes": "recipeId",
                "placements": "recipeId",
                "skills": "skillId",
                "quests": "quest_id",
                "npcs": "npc_id",
                "titles": "titleId",
                "classes": "classId",
                "enemies": "enemyId",
                "resource_nodes": "nodeId",
            }
            id_field = id_fields.get(self.current_json_type, "id")

            filtered_items = []
            for item in items:
                item_id = item.get(id_field, "Unknown")
                name = item.get("name", item.get("title", ""))
                display = f"{item_id}" + (f" - {name}" if name else "")
                if search_term in display.lower():
                    filtered_items.append(item)

            if index < len(filtered_items):
                selected_item = filtered_items[index]
            else:
                return
        else:
            if index < len(items):
                selected_item = items[index]
            else:
                return

        # Load into form
        self._load_json_to_form(selected_item)

    def _load_json_to_form(self, data: Dict):
        """Load JSON data into the form"""
        self.current_data = data

        for field_name, widget in self.field_widgets.items():
            value = data.get(field_name)

            if value is None:
                continue

            # Handle different widget types
            if isinstance(widget, ttk.Combobox):
                widget.set(str(value))
            elif isinstance(widget, ttk.Entry):
                widget.delete(0, tk.END)
                widget.insert(0, str(value))
            elif isinstance(widget, ttk.Checkbutton):
                widget.var.set(bool(value))
            elif isinstance(widget, ttk.Frame):
                # Text widget inside frame
                text_widget = widget.winfo_children()[0]
                if isinstance(text_widget, scrolledtext.ScrolledText):
                    text_widget.delete("1.0", tk.END)
                    if isinstance(value, (dict, list)):
                        text_widget.insert("1.0", json.dumps(value, indent=2))
                    else:
                        text_widget.insert("1.0", str(value))

        # Update preview
        self._update_preview()
        # Auto-validate
        self._validate_current()

    def _new_json(self):
        """Create a new empty JSON"""
        self.current_data = {}

        # Clear all fields
        for widget in self.field_widgets.values():
            if isinstance(widget, ttk.Combobox):
                widget.set("")
            elif isinstance(widget, ttk.Entry):
                widget.delete(0, tk.END)
            elif isinstance(widget, ttk.Checkbutton):
                widget.var.set(False)
            elif isinstance(widget, ttk.Frame):
                text_widget = widget.winfo_children()[0]
                if isinstance(text_widget, scrolledtext.ScrolledText):
                    text_widget.delete("1.0", tk.END)

        self.validation_text.delete("1.0", tk.END)
        self.preview_text.delete("1.0", tk.END)

    def _collect_form_data(self) -> Dict:
        """Collect data from form into a dictionary"""
        data = {}

        schema = JSONSchemas.get_schema(self.current_json_type)

        for field_name, widget in self.field_widgets.items():
            field_def = schema.get(field_name)

            if isinstance(widget, ttk.Combobox):
                value = widget.get()
                if value:
                    # Convert to appropriate type
                    if field_def.field_type == FieldType.INTEGER:
                        try:
                            value = int(value)
                        except ValueError:
                            pass
                    data[field_name] = value

            elif isinstance(widget, ttk.Entry):
                value = widget.get()
                if value:
                    # Convert to appropriate type
                    if field_def.field_type == FieldType.INTEGER:
                        try:
                            value = int(value)
                        except ValueError:
                            pass
                    elif field_def.field_type == FieldType.FLOAT:
                        try:
                            value = float(value)
                        except ValueError:
                            pass
                    data[field_name] = value

            elif isinstance(widget, ttk.Checkbutton):
                data[field_name] = widget.var.get()

            elif isinstance(widget, ttk.Frame):
                text_widget = widget.winfo_children()[0]
                if isinstance(text_widget, scrolledtext.ScrolledText):
                    value = text_widget.get("1.0", tk.END).strip()
                    if value:
                        try:
                            # Try to parse as JSON
                            data[field_name] = json.loads(value)
                        except json.JSONDecodeError:
                            data[field_name] = value

        return data

    def _update_preview(self):
        """Update JSON preview"""
        data = self._collect_form_data()

        self.preview_text.delete("1.0", tk.END)
        self.preview_text.insert("1.0", json.dumps(data, indent=2))

    def _validate_current(self):
        """Validate current form data"""
        data = self._collect_form_data()
        issues = self.validator.validate(self.current_json_type, data)

        self.validation_text.delete("1.0", tk.END)

        if not issues:
            self.validation_text.insert("1.0", "✓ No issues found! JSON is valid.\n", "success")
            self.validation_text.tag_config("success", foreground="green", font=("Arial", 10, "bold"))
        else:
            # Group by severity
            errors = [i for i in issues if i.severity == "error"]
            warnings = [i for i in issues if i.severity == "warning"]

            if errors:
                self.validation_text.insert(tk.END, f"❌ ERRORS ({len(errors)}):\n", "error_header")
                self.validation_text.tag_config("error_header", foreground="red", font=("Arial", 10, "bold"))

                for issue in errors:
                    self.validation_text.insert(tk.END, f"\n[{issue.field}] {issue.message}\n", "error")
                    if issue.suggestion:
                        self.validation_text.insert(tk.END, f"  → {issue.suggestion}\n", "suggestion")

                self.validation_text.tag_config("error", foreground="red")
                self.validation_text.tag_config("suggestion", foreground="blue", font=("Arial", 8, "italic"))

            if warnings:
                self.validation_text.insert(tk.END, f"\n⚠️  WARNINGS ({len(warnings)}):\n", "warning_header")
                self.validation_text.tag_config("warning_header", foreground="orange", font=("Arial", 10, "bold"))

                for issue in warnings:
                    self.validation_text.insert(tk.END, f"\n[{issue.field}] {issue.message}\n", "warning")
                    if issue.suggestion:
                        self.validation_text.insert(tk.END, f"  → {issue.suggestion}\n", "suggestion")

                self.validation_text.tag_config("warning", foreground="orange")

        # Also update preview
        self._update_preview()

    def _save_json(self):
        """Save the current JSON to file"""
        data = self._collect_form_data()

        # Validate first
        issues = self.validator.validate(self.current_json_type, data)
        errors = [i for i in issues if i.severity == "error"]

        if errors:
            response = messagebox.askyesno(
                "Validation Errors",
                f"There are {len(errors)} validation errors. Save anyway?"
            )
            if not response:
                return

        # Get the appropriate file
        discipline = data.get("stationType") or data.get("discipline")
        file_path = self.data_loader.get_file_for_type(self.current_json_type, discipline)

        try:
            # Load existing file
            if os.path.exists(file_path):
                with open(file_path, 'r', encoding='utf-8') as f:
                    existing_data = json.load(f)

                # Append to the appropriate array
                if isinstance(existing_data, list):
                    existing_data.append(data)
                elif isinstance(existing_data, dict):
                    # Find or create the appropriate array
                    # Try to find an existing array key (not metadata)
                    array_key = None
                    for key in existing_data:
                        if key != "metadata" and isinstance(existing_data[key], list):
                            array_key = key
                            existing_data[key].append(data)
                            break

                    # If no array found, create a default one
                    if array_key is None:
                        # Use json_type as key (e.g., "recipes", "items")
                        default_key = self.current_json_type
                        if default_key not in existing_data:
                            existing_data[default_key] = []
                        existing_data[default_key].append(data)

                        # Update metadata if it exists
                        if "metadata" in existing_data:
                            if "totalItems" in existing_data["metadata"]:
                                existing_data["metadata"]["totalItems"] += 1
                            elif "totalRecipes" in existing_data["metadata"]:
                                existing_data["metadata"]["totalRecipes"] += 1
                else:
                    existing_data = [data]
            else:
                # Create new file with proper structure
                existing_data = {
                    "metadata": {
                        "version": "1.0",
                        "discipline": discipline or "unified",
                        "description": f"Unified {self.current_json_type} created by JSON Creator",
                        "totalItems": 1
                    }
                }
                # Add the data to an array
                existing_data[self.current_json_type] = [data]

            # Save back
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(existing_data, f, indent=2)

            messagebox.showinfo("Success", f"JSON saved to:\n{file_path}")

            # Reload data and update library
            self.data_loader.load_all()
            self._update_library()

        except Exception as e:
            messagebox.showerror("Error", f"Failed to save JSON:\n{str(e)}")


def main():
    """Main entry point"""
    root = tk.Tk()
    app = UnifiedJSONCreatorGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()

"""
Crafting Training Data Generator for VLM/LLM Fine-tuning

Generates training data for:
- VLM (Vision-Language Models): Smithing & Adornments (images + recipes → item JSON)
- LLM (Language Models): Refining, Alchemy, Engineering (recipes → item JSON)

Key Features:
- Base64-encoded PNG images for VLM training (max 10MB each)
- Material-enriched recipe format with full metadata
- Natural variation naming (light_iron_ingot, shiny_copper_ingot, etc.)
- Automatic tag augmentation with variation descriptors

Output Format:
- Structured JSON matching material_enricher.py format
- Tags are preserved and augmented with variation descriptors

Usage:
    python crafting_training_data.py --discipline smithing --output ./training_data/
    python crafting_training_data.py --discipline all --output ./training_data/

Author: Claude
Created: 2026-02-04
"""

import json
import base64
import io
import os
import random
import copy
import uuid
import itertools
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Set, Any
from dataclasses import dataclass, field
from colorsys import hsv_to_rgb
import numpy as np

# Attempt to import PIL for PNG generation
try:
    from PIL import Image
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False
    print("Warning: PIL not available. Install with 'pip install Pillow' for image generation.")


# ============================================================================
# VARIATION NAMING SYSTEM
# ============================================================================

class VariationNamer:
    """
    Generates natural-looking variation names and corresponding tags.

    Instead of synthetic_a7c3e9f2, we use descriptive prefixes like:
    - light_iron_ingot, dark_iron_ingot (brightness variations)
    - shiny_iron_ingot, weathered_iron_ingot (saturation variations)
    - fire_iron_ingot, frost_iron_ingot (elemental variations)

    These prefixes are also added to the material's tags for semantic richness.
    """

    # Brightness-based variations (VALUE in HSV)
    BRIGHTNESS_PREFIXES = [
        ('light', 'bright'),      # +value
        ('dark', 'shadow'),       # -value
        ('brilliant', 'radiant'), # high value
        ('dull', 'dim'),          # low value
        ('glowing', 'luminous'),  # very high value
        ('faded', 'muted'),       # very low value
    ]

    # Saturation-based variations (SATURATION in HSV)
    SATURATION_PREFIXES = [
        ('vivid', 'rich'),        # high saturation
        ('pale', 'washed'),       # low saturation
        ('pure', 'pristine'),     # high saturation
        ('weathered', 'aged'),    # low saturation
        ('vibrant', 'intense'),   # high saturation
        ('dusty', 'faint'),       # low saturation
    ]

    # Elemental/thematic variations (for visual diversity)
    ELEMENTAL_PREFIXES = [
        ('fire', 'blazing'),
        ('frost', 'frozen'),
        ('lightning', 'charged'),
        ('earth', 'earthen'),
        ('shadow', 'dark'),
        ('crystal', 'crystalline'),
        ('ancient', 'old'),
        ('blessed', 'holy'),
        ('cursed', 'corrupted'),
        ('enchanted', 'magical'),
    ]

    # Quality/condition variations
    QUALITY_PREFIXES = [
        ('polished', 'refined'),
        ('rough', 'crude'),
        ('tempered', 'hardened'),
        ('soft', 'malleable'),
        ('shiny', 'gleaming'),
        ('tarnished', 'worn'),
        ('flawless', 'perfect'),
        ('cracked', 'damaged'),
    ]

    def __init__(self, seed: int = 42):
        """Initialize with a seed for reproducibility."""
        self.rng = random.Random(seed)
        self._used_combinations = set()

        # Combine all prefix groups
        self.all_prefixes = (
            self.BRIGHTNESS_PREFIXES +
            self.SATURATION_PREFIXES +
            self.ELEMENTAL_PREFIXES +
            self.QUALITY_PREFIXES
        )

    def get_variation_name(self, base_material_id: str, variation_index: int) -> Tuple[str, List[str]]:
        """
        Generate a natural variation name and associated tags.

        Args:
            base_material_id: Original material ID (e.g., "iron_ingot")
            variation_index: Index of this variation (0 = original, 1+ = variations)

        Returns:
            Tuple of (variation_name, additional_tags)
            e.g., ("light_iron_ingot", ["light", "bright"])
        """
        if variation_index == 0:
            # Original material - no variation
            return base_material_id, []

        # Select a prefix pair based on variation index
        prefix_idx = (variation_index - 1) % len(self.all_prefixes)
        prefix_pair = self.all_prefixes[prefix_idx]

        # Use the primary prefix for naming
        primary_prefix = prefix_pair[0]

        # Create variation name
        variation_name = f"{primary_prefix}_{base_material_id}"

        # Both prefixes become tags
        additional_tags = list(prefix_pair)

        return variation_name, additional_tags

    def get_random_variation(self, base_material_id: str) -> Tuple[str, List[str]]:
        """
        Generate a random variation name for material substitutions.

        Args:
            base_material_id: Original material ID

        Returns:
            Tuple of (variation_name, additional_tags)
        """
        prefix_pair = self.rng.choice(self.all_prefixes)
        primary_prefix = prefix_pair[0]

        variation_name = f"{primary_prefix}_{base_material_id}"
        additional_tags = list(prefix_pair)

        return variation_name, additional_tags


# ============================================================================
# MATERIAL ENRICHER (Adapted from material_enricher.py)
# ============================================================================

class MaterialEnricher:
    """
    Enriches recipe inputs with material metadata for training context.
    Adds variation tags when materials have been augmented.
    """

    def __init__(self, materials_path: str):
        """Initialize with materials JSON file path."""
        self.materials_path = Path(materials_path)
        self.materials: Dict[str, Dict] = {}
        self._load_materials()
        self.variation_namer = VariationNamer()

    def _load_materials(self):
        """Load and index materials by materialId."""
        try:
            with open(self.materials_path, 'r') as f:
                data = json.load(f)

            for material in data.get("materials", []):
                material_id = material.get("materialId")
                if material_id:
                    self.materials[material_id] = material

        except FileNotFoundError:
            raise FileNotFoundError(f"Materials file not found: {self.materials_path}")
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in materials file: {e}")

    def get_material(self, material_id: str) -> Optional[Dict]:
        """Get a material by its ID (handles variation prefixes)."""
        # Try exact match first
        if material_id in self.materials:
            return self.materials[material_id]

        # Try stripping variation prefix
        for prefix_pair in VariationNamer.BRIGHTNESS_PREFIXES + VariationNamer.SATURATION_PREFIXES + \
                          VariationNamer.ELEMENTAL_PREFIXES + VariationNamer.QUALITY_PREFIXES:
            for prefix in prefix_pair:
                if material_id.startswith(f"{prefix}_"):
                    base_id = material_id[len(prefix) + 1:]
                    if base_id in self.materials:
                        return self.materials[base_id]

        return None

    def extract_base_material_id(self, material_id: str) -> str:
        """Extract base material ID from a variation name."""
        for prefix_pair in VariationNamer.BRIGHTNESS_PREFIXES + VariationNamer.SATURATION_PREFIXES + \
                          VariationNamer.ELEMENTAL_PREFIXES + VariationNamer.QUALITY_PREFIXES:
            for prefix in prefix_pair:
                if material_id.startswith(f"{prefix}_"):
                    return material_id[len(prefix) + 1:]
        return material_id

    def extract_material_metadata(self, material: Dict, variation_tags: List[str] = None) -> Dict:
        """
        Extract relevant metadata from a material for training context.
        Adds variation_tags to the tags list if provided.
        """
        mat_metadata = material.get("metadata", {})

        # Get base tags
        base_tags = mat_metadata.get("tags", []).copy() if isinstance(mat_metadata.get("tags"), list) else []

        # Add variation tags if provided
        if variation_tags:
            base_tags = base_tags + variation_tags

        metadata = {
            "name": material.get("name", ""),
            "tier": material.get("tier", 1),
            "category": material.get("category", ""),
            "rarity": material.get("rarity", "common"),
            "tags": base_tags,
        }

        # Include description if present
        if "description" in mat_metadata:
            metadata["description"] = mat_metadata["description"]

        # Include narrative if present (skip if empty per user request)
        if mat_metadata.get("narrative"):
            metadata["narrative"] = mat_metadata["narrative"]

        # Include elemental/damage type if present
        if "elementalType" in material:
            metadata["elementalType"] = material["elementalType"]
        if "damageType" in material:
            metadata["damageType"] = material["damageType"]

        return metadata

    def enrich_input(self, input_item: Dict, variation_tags: List[str] = None) -> Dict:
        """
        Enrich a single recipe input with material metadata.
        """
        enriched = copy.deepcopy(input_item)

        material_id = input_item.get("materialId") or input_item.get("itemId")

        if material_id:
            # Get base material (handles variation prefixes)
            material = self.get_material(material_id)
            if material:
                enriched["material_metadata"] = self.extract_material_metadata(material, variation_tags)
            else:
                enriched["material_metadata"] = {"note": "not_in_materials_db"}

        return enriched


# ============================================================================
# IMAGE GENERATION UTILITIES
# ============================================================================

class ImageGenerator:
    """
    Generates training images for CNN-based disciplines (Smithing, Adornments).
    Uses HSV color encoding with natural variation names.
    """

    # Category hues (CONSTANT - encodes category)
    CATEGORY_HUES = {
        'metal': 210,
        'wood': 30,
        'stone': 0,
        'monster_drop': 300,
        'gem': 280,
        'herb': 120,
        'fabric': 45,
        'elemental': 280,
    }

    ELEMENT_HUES = {
        'fire': 0, 'water': 210, 'earth': 120, 'air': 60,
        'lightning': 270, 'ice': 180, 'light': 45,
        'dark': 280, 'void': 290, 'chaos': 330,
    }

    # Tier to value mapping
    TIER_VALUES = {1: 0.50, 2: 0.65, 3: 0.80, 4: 0.95}

    # Category shape masks (4x4 patterns)
    CATEGORY_SHAPES = {
        'metal': np.array([[1,1,1,1],[1,1,1,1],[1,1,1,1],[1,1,1,1]], dtype=np.float32),
        'wood': np.array([[1,1,1,1],[0,0,0,0],[1,1,1,1],[0,0,0,0]], dtype=np.float32),
        'stone': np.array([[1,0,0,1],[0,1,1,0],[0,1,1,0],[1,0,0,1]], dtype=np.float32),
        'monster_drop': np.array([[0,1,1,0],[1,1,1,1],[1,1,1,1],[0,1,1,0]], dtype=np.float32),
        'elemental': np.array([[0,1,1,0],[1,1,1,1],[1,1,1,1],[0,1,1,0]], dtype=np.float32),
        'gem': np.array([[0,1,1,0],[1,1,1,1],[1,1,1,1],[0,1,1,0]], dtype=np.float32),
        'herb': np.array([[0,1,1,0],[1,0,0,1],[1,0,0,1],[0,1,1,0]], dtype=np.float32),
        'fabric': np.array([[1,0,1,0],[0,1,0,1],[1,0,1,0],[0,1,0,1]], dtype=np.float32),
    }

    TIER_FILL_SIZES = {1: 1, 2: 2, 3: 3, 4: 4}

    def __init__(self, materials_dict: Dict[str, Dict]):
        """Initialize with materials dictionary."""
        self.materials_dict = materials_dict

    def get_base_hsv(self, material_id: str) -> Tuple[float, float, float]:
        """Get base HSV values for a material."""
        if material_id is None or material_id not in self.materials_dict:
            return (0, 0, 0)

        material = self.materials_dict[material_id]
        category = material.get('category', 'unknown')
        tier = material.get('tier', 1)
        tags = material.get('metadata', {}).get('tags', [])

        # Determine hue from category
        if category == 'elemental':
            hue = 280
            for tag in tags:
                if tag in self.ELEMENT_HUES:
                    hue = self.ELEMENT_HUES[tag]
                    break
        else:
            hue = self.CATEGORY_HUES.get(category, 0)

        # Value from tier
        value = self.TIER_VALUES.get(tier, 0.5)

        # Saturation from tags
        saturation = 0.6
        if category == 'stone':
            saturation = 0.2
        if 'legendary' in tags or 'mythical' in tags:
            saturation = min(1.0, saturation + 0.2)
        elif 'magical' in tags or 'ancient' in tags:
            saturation = min(1.0, saturation + 0.1)

        return (hue, saturation, value)

    def material_to_color(self, material_id: str, value_offset: float = 0,
                          sat_offset: float = 0) -> np.ndarray:
        """
        Convert material to RGB color with optional offsets.

        Args:
            material_id: Material identifier
            value_offset: Brightness adjustment (-0.1 to +0.1)
            sat_offset: Saturation adjustment (-0.15 to +0.15)
        """
        if material_id is None:
            return np.array([0.0, 0.0, 0.0])

        # Handle variation prefixes
        base_id = material_id
        for prefix_pair in VariationNamer.BRIGHTNESS_PREFIXES + VariationNamer.SATURATION_PREFIXES + \
                          VariationNamer.ELEMENTAL_PREFIXES + VariationNamer.QUALITY_PREFIXES:
            for prefix in prefix_pair:
                if material_id.startswith(f"{prefix}_"):
                    base_id = material_id[len(prefix) + 1:]
                    break

        if base_id not in self.materials_dict:
            return np.array([0.3, 0.3, 0.3])  # Unknown = gray

        hue, saturation, value = self.get_base_hsv(base_id)

        # Apply offsets
        value = max(0.30, min(0.95, value + value_offset))
        saturation = max(0.10, min(1.0, saturation + sat_offset))

        rgb = hsv_to_rgb(hue / 360.0, saturation, value)
        return np.array(rgb)

    def get_shape_mask(self, material_id: str) -> np.ndarray:
        """Get 4x4 shape mask for a material's category."""
        base_id = material_id
        # Handle variation prefixes
        for prefix_pair in VariationNamer.BRIGHTNESS_PREFIXES + VariationNamer.SATURATION_PREFIXES + \
                          VariationNamer.ELEMENTAL_PREFIXES + VariationNamer.QUALITY_PREFIXES:
            for prefix in prefix_pair:
                if material_id.startswith(f"{prefix}_"):
                    base_id = material_id[len(prefix) + 1:]
                    break

        if base_id not in self.materials_dict:
            return np.ones((4, 4), dtype=np.float32)

        category = self.materials_dict[base_id].get('category', 'unknown')
        return self.CATEGORY_SHAPES.get(category, np.ones((4, 4), dtype=np.float32))

    def get_tier_fill_mask(self, material_id: str, cell_size: int = 4) -> np.ndarray:
        """Get tier-based fill mask."""
        base_id = material_id
        for prefix_pair in VariationNamer.BRIGHTNESS_PREFIXES + VariationNamer.SATURATION_PREFIXES + \
                          VariationNamer.ELEMENTAL_PREFIXES + VariationNamer.QUALITY_PREFIXES:
            for prefix in prefix_pair:
                if material_id.startswith(f"{prefix}_"):
                    base_id = material_id[len(prefix) + 1:]
                    break

        if base_id not in self.materials_dict:
            return np.zeros((cell_size, cell_size), dtype=np.float32)

        tier = self.materials_dict[base_id].get('tier', 1)
        fill_size = self.TIER_FILL_SIZES.get(tier, 4)

        mask = np.zeros((cell_size, cell_size), dtype=np.float32)
        offset = (cell_size - fill_size) // 2
        mask[offset:offset+fill_size, offset:offset+fill_size] = 1.0

        return mask


# ============================================================================
# SMITHING VLM DATA GENERATOR
# ============================================================================

class SmithingVLMDataGenerator:
    """
    Generates VLM training data for Smithing discipline.

    Full augmentation pipeline (matching CNN training):
    1. Material substitution cross-product (all valid substitutes)
    2. Horizontal flips
    3. Color variations (1 exact + N varied per grid)

    Output format:
    {
        "recipe_id": "smithing_iron_sword_001_v2",
        "image_base64": "data:image/png;base64,...",
        "recipe": {
            "recipeId": "smithing_iron_sword_001_v2",
            "stationType": "smithing",
            "stationTier": 1,
            "gridSize": "3x3",
            "inputs": [
                {
                    "materialId": "light_iron_ingot",
                    "quantity": 3,
                    "position": "1,1",
                    "material_metadata": {
                        "name": "Iron Ingot",
                        "tier": 1,
                        "category": "metal",
                        "tags": ["refined", "metal", "standard", "light", "bright"]
                    }
                }
            ]
        }
    }
    """

    def __init__(self, materials_path: str, placements_path: str,
                 num_color_variations: int = 3):
        """
        Initialize the generator.

        Args:
            materials_path: Path to materials JSON
            placements_path: Path to smithing placements JSON
            num_color_variations: Number of color variations per grid (in addition to 1 exact)
        """
        self.enricher = MaterialEnricher(materials_path)
        self.variation_namer = VariationNamer()
        self.num_color_variations = num_color_variations

        # Load materials dict for image generation
        with open(materials_path, 'r') as f:
            data = json.load(f)
        self.materials_dict = {m['materialId']: m for m in data.get('materials', [])}

        # Load placements
        with open(placements_path, 'r') as f:
            data = json.load(f)
        self.placements = data.get('placements', [])

        self.image_gen = ImageGenerator(self.materials_dict)

        print(f"Loaded {len(self.materials_dict)} materials")
        print(f"Loaded {len(self.placements)} smithing placements")

    def placement_to_grid(self, placement: Dict) -> List[List[Optional[str]]]:
        """Convert placement to 9x9 grid."""
        grid = [[None] * 9 for _ in range(9)]

        grid_size_str = placement['metadata'].get('gridSize', '9x9')

        # Find bounding box
        positions = []
        for pos_str in placement['placementMap'].keys():
            y_idx, x_idx = map(int, pos_str.split(','))
            positions.append((y_idx, x_idx))

        if not positions:
            return grid

        min_y = min(p[0] for p in positions)
        max_y = max(p[0] for p in positions)
        min_x = min(p[1] for p in positions)
        max_x = max(p[1] for p in positions)

        actual_height = max_y - min_y + 1
        actual_width = max_x - min_x + 1

        offset_y = (9 - actual_height) // 2
        offset_x = (9 - actual_width) // 2

        for pos_str, material_id in placement['placementMap'].items():
            y_idx, x_idx = map(int, pos_str.split(','))
            final_y = offset_y + (y_idx - min_y)
            final_x = offset_x + (x_idx - min_x)

            if 0 <= final_y < 9 and 0 <= final_x < 9:
                grid[final_y][final_x] = material_id

        return grid

    def grid_to_image(self, grid: List[List[Optional[str]]],
                      value_offset: float = 0, sat_offset: float = 0,
                      cell_size: int = 4) -> np.ndarray:
        """Convert 9x9 grid to 36x36 RGB image."""
        img_size = 9 * cell_size
        img = np.zeros((img_size, img_size, 3), dtype=np.float32)

        for i in range(9):
            for j in range(9):
                material_id = grid[i][j]
                if material_id is None:
                    continue

                color = self.image_gen.material_to_color(material_id, value_offset, sat_offset)
                shape_mask = self.image_gen.get_shape_mask(material_id)
                tier_mask = self.image_gen.get_tier_fill_mask(material_id, cell_size)

                combined_mask = shape_mask * tier_mask

                cell = np.zeros((cell_size, cell_size, 3), dtype=np.float32)
                for c in range(3):
                    cell[:, :, c] = color[c] * combined_mask

                img[i * cell_size:(i + 1) * cell_size,
                    j * cell_size:(j + 1) * cell_size] = cell

        return img

    def image_to_base64(self, img_array: np.ndarray) -> str:
        """Convert numpy array to base64-encoded PNG."""
        if not PIL_AVAILABLE:
            raise RuntimeError("PIL required for image generation")

        # Convert to 8-bit RGB
        img_uint8 = (img_array * 255).astype(np.uint8)
        img = Image.fromarray(img_uint8, mode='RGB')

        # Save to buffer
        buffer = io.BytesIO()
        img.save(buffer, format='PNG')
        buffer.seek(0)

        # Encode to base64
        img_base64 = base64.b64encode(buffer.read()).decode('utf-8')

        return f"data:image/png;base64,{img_base64}"

    def save_image_to_disk(self, img_array: np.ndarray, path: str):
        """Save image to disk as PNG."""
        if not PIL_AVAILABLE:
            return

        img_uint8 = (img_array * 255).astype(np.uint8)
        img = Image.fromarray(img_uint8, mode='RGB')
        img.save(path, format='PNG')

    def create_enriched_recipe(self, placement: Dict, grid: List[List[Optional[str]]],
                               variation_index: int) -> Dict:
        """
        Create material-enriched recipe from placement.

        Args:
            placement: Original placement data
            grid: 9x9 grid with material IDs
            variation_index: 0 = original, 1+ = variations
        """
        recipe_id = placement['recipeId']
        if variation_index > 0:
            recipe_id = f"{recipe_id}_v{variation_index}"

        grid_size = placement['metadata'].get('gridSize', '3x3')

        # Extract inputs with positions
        inputs = []
        for pos_str, material_id in placement['placementMap'].items():
            # Get variation name and tags
            var_name, var_tags = self.variation_namer.get_variation_name(material_id, variation_index)

            input_item = {
                "materialId": var_name,
                "quantity": 1,  # Each cell is quantity 1
                "position": pos_str,
            }

            # Enrich with metadata
            enriched = self.enricher.enrich_input(input_item, var_tags)
            inputs.append(enriched)

        # Aggregate quantities for same materials
        aggregated = {}
        for inp in inputs:
            mat_id = inp['materialId']
            if mat_id not in aggregated:
                aggregated[mat_id] = {
                    "materialId": mat_id,
                    "quantity": 0,
                    "positions": [],
                    "material_metadata": inp.get('material_metadata', {})
                }
            aggregated[mat_id]['quantity'] += 1
            aggregated[mat_id]['positions'].append(inp['position'])

        recipe = {
            "recipeId": recipe_id,
            "stationType": "smithing",
            "stationTier": self._infer_station_tier(placement),
            "gridSize": grid_size,
            "inputs": list(aggregated.values())
        }

        # Include narrative if present
        if placement['metadata'].get('narrative'):
            recipe['narrative'] = placement['metadata']['narrative']

        return recipe

    def _infer_station_tier(self, placement: Dict) -> int:
        """Infer station tier from materials used."""
        max_tier = 1
        for material_id in placement['placementMap'].values():
            if material_id in self.materials_dict:
                tier = self.materials_dict[material_id].get('tier', 1)
                max_tier = max(max_tier, tier)
        return min(max_tier, 4)

    def is_station(self, recipe_id: str) -> bool:
        """Check if recipe is a station (exclude from training)."""
        return any(recipe_id.endswith(f'_t{i}') for i in range(1, 5))

    def find_substitutable_materials(self, material_id: str) -> List[str]:
        """
        Find all materials that can substitute for the given material.

        HARD REQUIREMENTS (must match):
        - Same category
        - Same refinement status (refined vs basic/raw)

        SUBSTITUTION RULES (one must be true):
        - Rule 1: ALL tags identical → can substitute at ANY tier
        - Rule 2: Tier difference ≤1 AND ≥2 matching tags
        """
        if material_id not in self.materials_dict:
            return []

        base_mat = self.materials_dict[material_id]
        base_tier = base_mat.get('tier', 1)
        base_tags = set(base_mat.get('metadata', {}).get('tags', []))
        base_category = base_mat.get('category', 'unknown')

        is_refined = 'refined' in base_tags
        is_basic = 'basic' in base_tags or 'raw' in base_tags

        substitutes = []

        for mat_id, mat in self.materials_dict.items():
            if mat_id == material_id:
                continue

            # Must be same category
            if mat.get('category') != base_category:
                continue

            mat_tags = set(mat.get('metadata', {}).get('tags', []))
            mat_tier = mat.get('tier', 1)

            # HARD: refined/basic must match
            mat_is_refined = 'refined' in mat_tags
            mat_is_basic = 'basic' in mat_tags or 'raw' in mat_tags

            if is_refined and not mat_is_refined:
                continue
            if is_basic and not mat_is_basic:
                continue
            if not is_refined and not is_basic:
                if mat_is_refined or mat_is_basic:
                    continue

            # Rule 1: All tags match (any tier)
            if mat_tags == base_tags:
                substitutes.append(mat_id)
                continue

            # Rule 2: ±1 tier and ≥2 matching tags
            if abs(mat_tier - base_tier) <= 1:
                matching_tags = base_tags & mat_tags
                if len(matching_tags) >= 2:
                    substitutes.append(mat_id)

        return substitutes

    def flip_grid_horizontal(self, grid: List[List[Optional[str]]]) -> List[List[Optional[str]]]:
        """Flip 9x9 grid horizontally."""
        return [row[::-1] for row in grid]

    def augment_recipe_materials(self, grid: List[List[Optional[str]]]) -> List[Tuple[List[List[Optional[str]]], Dict[str, str]]]:
        """
        Generate variants by substituting materials.
        Returns list of (grid, material_substitution_map) tuples.

        The substitution_map tracks which materials were substituted: {original_id: substituted_id}
        """
        variants = [(grid, {})]  # Original with empty substitution map

        # Add horizontal flip of original
        flipped = self.flip_grid_horizontal(grid)
        variants.append((flipped, {'_flipped': True}))

        # Find unique materials in grid
        unique_materials = set()
        for row in grid:
            for mat in row:
                if mat is not None:
                    unique_materials.add(mat)

        # Generate substitution variants
        for material_id in unique_materials:
            substitutes = self.find_substitutable_materials(material_id)

            for sub_mat in substitutes:
                # Create variant by replacing ALL instances
                new_grid = copy.deepcopy(grid)
                for i in range(9):
                    for j in range(9):
                        if new_grid[i][j] == material_id:
                            new_grid[i][j] = sub_mat

                sub_map = {material_id: sub_mat}
                variants.append((new_grid, sub_map))

                # Also add flipped version
                flipped_variant = self.flip_grid_horizontal(new_grid)
                sub_map_flipped = {material_id: sub_mat, '_flipped': True}
                variants.append((flipped_variant, sub_map_flipped))

        # Remove duplicates
        unique_variants = []
        seen = set()
        for variant_grid, sub_map in variants:
            variant_tuple = tuple(tuple(row) for row in variant_grid)
            if variant_tuple not in seen:
                seen.add(variant_tuple)
                unique_variants.append((variant_grid, sub_map))

        return unique_variants

    def grid_to_enriched_recipe(self, placement: Dict, grid: List[List[Optional[str]]],
                                 sub_map: Dict[str, str], variation_index: int) -> Dict:
        """
        Create material-enriched recipe from grid with substitution tracking.

        Args:
            placement: Original placement data
            grid: 9x9 grid with (possibly substituted) material IDs
            sub_map: Map of original→substituted materials
            variation_index: 0 = exact colors, 1+ = color variations
        """
        base_recipe_id = placement['recipeId']

        # Build recipe ID with substitution info
        sub_suffix = ""
        if sub_map:
            # Create readable suffix from substitutions
            for orig, sub in sub_map.items():
                if orig != '_flipped':
                    sub_suffix += f"_{sub.split('_')[0]}"  # Take first part of sub material
            if sub_map.get('_flipped'):
                sub_suffix += "_flip"

        recipe_id = f"{base_recipe_id}{sub_suffix}_v{variation_index}"

        grid_size = placement['metadata'].get('gridSize', '3x3')

        # Count materials from grid (aggregated)
        material_counts = {}
        material_positions = {}

        for i in range(9):
            for j in range(9):
                mat_id = grid[i][j]
                if mat_id is None:
                    continue

                if mat_id not in material_counts:
                    material_counts[mat_id] = 0
                    material_positions[mat_id] = []

                material_counts[mat_id] += 1
                material_positions[mat_id].append(f"{i},{j}")

        # Build enriched inputs
        inputs = []
        for mat_id, qty in material_counts.items():
            # Get variation name and tags
            var_name, var_tags = self.variation_namer.get_variation_name(mat_id, variation_index)

            input_item = {
                "materialId": var_name,
                "quantity": qty,
                "positions": material_positions[mat_id]
            }

            # Enrich with metadata (use actual material in grid, not variation name)
            enriched = self.enricher.enrich_input({"materialId": mat_id}, var_tags)
            input_item['material_metadata'] = enriched.get('material_metadata', {})
            inputs.append(input_item)

        recipe = {
            "recipeId": recipe_id,
            "stationType": "smithing",
            "stationTier": self._infer_station_tier_from_grid(grid),
            "gridSize": grid_size,
            "inputs": inputs
        }

        # Include narrative if present
        if placement['metadata'].get('narrative'):
            recipe['narrative'] = placement['metadata']['narrative']

        return recipe

    def _infer_station_tier_from_grid(self, grid: List[List[Optional[str]]]) -> int:
        """Infer station tier from materials in grid."""
        max_tier = 1
        for row in grid:
            for mat_id in row:
                if mat_id and mat_id in self.materials_dict:
                    tier = self.materials_dict[mat_id].get('tier', 1)
                    max_tier = max(max_tier, tier)
        return min(max_tier, 4)

    def generate(self, output_dir: str = None, save_images: bool = True) -> List[Dict]:
        """
        Generate training data for all smithing recipes with full augmentation.

        Pipeline:
        1. For each placement → convert to 9x9 grid
        2. Generate material substitution variants + horizontal flips
        3. For each grid variant → generate 1 exact + N color variations
        4. Each image gets paired with material-enriched recipe

        Args:
            output_dir: Directory to save PNG images (optional)
            save_images: Whether to save images to disk

        Returns:
            List of training data entries
        """
        training_data = []

        if output_dir and save_images:
            os.makedirs(output_dir, exist_ok=True)
            img_dir = os.path.join(output_dir, 'smithing_images')
            os.makedirs(img_dir, exist_ok=True)

        # Filter non-station placements
        valid_placements = [p for p in self.placements if not self.is_station(p['recipeId'])]

        print(f"\nProcessing {len(valid_placements)} non-station smithing recipes...")
        print(f"Augmentation: material substitution + horizontal flips + {self.num_color_variations} color variations")

        total_grids = 0
        example_idx = 0

        for placement in valid_placements:
            recipe_id = placement['recipeId']
            base_grid = self.placement_to_grid(placement)

            # Step 1: Generate all material substitution + flip variants
            grid_variants = self.augment_recipe_materials(base_grid)
            total_grids += len(grid_variants)

            print(f"  {recipe_id}: {len(grid_variants)} grid variants")

            # Step 2: For each grid variant, generate color variations
            for grid, sub_map in grid_variants:
                # Variation 0: Exact colors
                img_exact = self.grid_to_image(grid, 0, 0)
                recipe_exact = self.grid_to_enriched_recipe(placement, grid, sub_map, 0)

                entry = {
                    "recipe_id": recipe_exact['recipeId'],
                    "variation": "original",
                    "image_base64": self.image_to_base64(img_exact) if PIL_AVAILABLE else None,
                    "recipe": recipe_exact
                }
                training_data.append(entry)
                example_idx += 1

                if output_dir and save_images and PIL_AVAILABLE:
                    safe_id = recipe_exact['recipeId'].replace('/', '_')[:100]
                    img_path = os.path.join(img_dir, f"{safe_id}.png")
                    self.save_image_to_disk(img_exact, img_path)

                # Color variations (varied saturation/value)
                for v_idx in range(1, self.num_color_variations + 1):
                    val_offset = random.uniform(-0.10, 0.10)
                    sat_offset = random.uniform(-0.15, 0.15)

                    img_varied = self.grid_to_image(grid, val_offset, sat_offset)
                    recipe_varied = self.grid_to_enriched_recipe(placement, grid, sub_map, v_idx)

                    var_name = self.variation_namer.all_prefixes[(v_idx - 1) % len(self.variation_namer.all_prefixes)][0]

                    entry = {
                        "recipe_id": recipe_varied['recipeId'],
                        "variation": var_name,
                        "image_base64": self.image_to_base64(img_varied) if PIL_AVAILABLE else None,
                        "recipe": recipe_varied
                    }
                    training_data.append(entry)
                    example_idx += 1

                    if output_dir and save_images and PIL_AVAILABLE:
                        safe_id = recipe_varied['recipeId'].replace('/', '_')[:100]
                        img_path = os.path.join(img_dir, f"{safe_id}.png")
                        self.save_image_to_disk(img_varied, img_path)

        print(f"\n=== Smithing Augmentation Summary ===")
        print(f"Base recipes: {len(valid_placements)}")
        print(f"Grid variants (material sub + flips): {total_grids}")
        print(f"Color variations per grid: {1 + self.num_color_variations}")
        print(f"Total training examples: {len(training_data)}")

        return training_data


# ============================================================================
# ADORNMENT VLM DATA GENERATOR
# ============================================================================

class AdornmentVLMDataGenerator:
    """
    Generates VLM training data for Adornment/Enchanting discipline.
    Uses vertex-based geometric patterns on a 12x12 coordinate grid.

    Full augmentation pipeline:
    1. Material substitution (all valid substitutes)
    2. Reflections (vertical and horizontal)
    3. Color variations (1 exact + N varied per pattern)
    """

    def __init__(self, materials_path: str, placements_path: str,
                 num_color_variations: int = 3):
        """Initialize the generator."""
        self.enricher = MaterialEnricher(materials_path)
        self.variation_namer = VariationNamer()
        self.num_color_variations = num_color_variations

        # Load materials
        with open(materials_path, 'r') as f:
            data = json.load(f)
        self.materials_dict = {m['materialId']: m for m in data.get('materials', [])}

        # Load placements
        with open(placements_path, 'r') as f:
            data = json.load(f)
        self.placements = data.get('placements', [])

        self.image_gen = ImageGenerator(self.materials_dict)

        print(f"Loaded {len(self.materials_dict)} materials")
        print(f"Loaded {len(self.placements)} adornment placements")

    def parse_placement(self, placement: Dict) -> Tuple[Dict, List]:
        """Extract vertices and shapes from placement."""
        placement_map = placement.get('placementMap', {})
        vertices = placement_map.get('vertices', {})
        shapes = placement_map.get('shapes', [])
        return vertices, shapes

    def render_to_image(self, vertices: Dict, shapes: List,
                        value_offset: float = 0, sat_offset: float = 0,
                        img_size: int = 56) -> np.ndarray:
        """Render vertices and shapes to RGB image."""
        img = np.zeros((img_size, img_size, 3), dtype=np.float32)

        def coord_to_pixel(x, y):
            px = int((x + 7) * 4)
            py = int((7 - y) * 4)
            return px, py

        def draw_line(x0, y0, x1, y1, color, thickness=2):
            dx = abs(x1 - x0)
            dy = abs(y1 - y0)
            sx = 1 if x0 < x1 else -1
            sy = 1 if y0 < y1 else -1
            err = dx - dy

            while True:
                for ty in range(-thickness // 2, thickness // 2 + 1):
                    for tx in range(-thickness // 2, thickness // 2 + 1):
                        px, py = x0 + tx, y0 + ty
                        if 0 <= px < img_size and 0 <= py < img_size:
                            existing = img[py, px]
                            if np.any(existing > 0):
                                img[py, px] = (existing + color) / 2
                            else:
                                img[py, px] = color

                if x0 == x1 and y0 == y1:
                    break
                e2 = 2 * err
                if e2 > -dy:
                    err -= dy
                    x0 += sx
                if e2 < dx:
                    err += dx
                    y0 += sy

        def draw_circle(cx, cy, radius, color):
            for y in range(max(0, cy - radius), min(img_size, cy + radius + 1)):
                for x in range(max(0, cx - radius), min(img_size, cx + radius + 1)):
                    if (x - cx) ** 2 + (y - cy) ** 2 <= radius ** 2:
                        img[y, x] = color

        # Draw shape edges
        for shape in shapes:
            shape_vertices = shape.get('vertices', [])
            n = len(shape_vertices)

            for i in range(n):
                v1_str = shape_vertices[i]
                v2_str = shape_vertices[(i + 1) % n]

                x1, y1 = map(int, v1_str.split(','))
                x2, y2 = map(int, v2_str.split(','))
                px1, py1 = coord_to_pixel(x1, y1)
                px2, py2 = coord_to_pixel(x2, y2)

                mat1 = vertices.get(v1_str, {}).get('materialId')
                mat2 = vertices.get(v2_str, {}).get('materialId')

                if mat1 and mat2:
                    c1 = self.image_gen.material_to_color(mat1, value_offset, sat_offset)
                    c2 = self.image_gen.material_to_color(mat2, value_offset, sat_offset)
                    color = (c1 + c2) / 2
                elif mat1:
                    color = self.image_gen.material_to_color(mat1, value_offset, sat_offset)
                elif mat2:
                    color = self.image_gen.material_to_color(mat2, value_offset, sat_offset)
                else:
                    color = np.array([0.3, 0.3, 0.3])

                draw_line(px1, py1, px2, py2, color)

        # Draw vertices
        for coord_str, vertex_data in vertices.items():
            x, y = map(int, coord_str.split(','))
            px, py = coord_to_pixel(x, y)
            material_id = vertex_data.get('materialId')
            color = self.image_gen.material_to_color(material_id, value_offset, sat_offset)
            draw_circle(px, py, 3, color)

        return img

    def image_to_base64(self, img_array: np.ndarray) -> str:
        """Convert numpy array to base64-encoded PNG."""
        if not PIL_AVAILABLE:
            return None

        img_uint8 = (img_array * 255).astype(np.uint8)
        img = Image.fromarray(img_uint8, mode='RGB')

        buffer = io.BytesIO()
        img.save(buffer, format='PNG')
        buffer.seek(0)

        img_base64 = base64.b64encode(buffer.read()).decode('utf-8')
        return f"data:image/png;base64,{img_base64}"

    def save_image_to_disk(self, img_array: np.ndarray, path: str):
        """Save image to disk."""
        if not PIL_AVAILABLE:
            return

        img_uint8 = (img_array * 255).astype(np.uint8)
        img = Image.fromarray(img_uint8, mode='RGB')
        img.save(path, format='PNG')

    def create_enriched_recipe(self, placement: Dict, vertices: Dict,
                               variation_index: int) -> Dict:
        """Create material-enriched recipe from adornment placement."""
        recipe_id = placement['recipeId']
        if variation_index > 0:
            recipe_id = f"{recipe_id}_v{variation_index}"

        # Count materials
        material_counts = {}
        for coord_str, vertex_data in vertices.items():
            mat_id = vertex_data.get('materialId')
            if mat_id:
                var_name, var_tags = self.variation_namer.get_variation_name(mat_id, variation_index)
                if var_name not in material_counts:
                    material_counts[var_name] = {
                        "materialId": var_name,
                        "quantity": 0,
                        "positions": [],
                        "base_material": mat_id,
                        "variation_tags": var_tags
                    }
                material_counts[var_name]['quantity'] += 1
                material_counts[var_name]['positions'].append(coord_str)

        # Enrich inputs
        inputs = []
        for mat_data in material_counts.values():
            input_item = {
                "materialId": mat_data['materialId'],
                "quantity": mat_data['quantity'],
                "positions": mat_data['positions']
            }
            enriched = self.enricher.enrich_input(
                {"materialId": mat_data['base_material']},
                mat_data['variation_tags']
            )
            input_item['material_metadata'] = enriched.get('material_metadata', {})
            inputs.append(input_item)

        recipe = {
            "recipeId": recipe_id,
            "stationType": "enchanting",
            "stationTier": self._infer_station_tier(vertices),
            "inputs": inputs
        }

        return recipe

    def _infer_station_tier(self, vertices: Dict) -> int:
        """Infer station tier from materials."""
        max_tier = 1
        for vertex_data in vertices.values():
            mat_id = vertex_data.get('materialId')
            if mat_id and mat_id in self.materials_dict:
                tier = self.materials_dict[mat_id].get('tier', 1)
                max_tier = max(max_tier, tier)
        return min(max_tier, 4)

    def find_substitutable_materials(self, material_id: str) -> List[str]:
        """Find all materials that can substitute for the given material."""
        if material_id not in self.materials_dict:
            return []

        base_mat = self.materials_dict[material_id]
        base_tier = base_mat.get('tier', 1)
        base_tags = set(base_mat.get('metadata', {}).get('tags', []))
        base_category = base_mat.get('category', 'unknown')

        is_refined = 'refined' in base_tags
        is_basic = 'basic' in base_tags or 'raw' in base_tags

        substitutes = []

        for mat_id, mat in self.materials_dict.items():
            if mat_id == material_id:
                continue
            if mat.get('category') != base_category:
                continue

            mat_tags = set(mat.get('metadata', {}).get('tags', []))
            mat_tier = mat.get('tier', 1)

            mat_is_refined = 'refined' in mat_tags
            mat_is_basic = 'basic' in mat_tags or 'raw' in mat_tags

            if is_refined and not mat_is_refined:
                continue
            if is_basic and not mat_is_basic:
                continue

            if mat_tags == base_tags:
                substitutes.append(mat_id)
                continue

            if abs(mat_tier - base_tier) <= 1:
                matching_tags = base_tags & mat_tags
                if len(matching_tags) >= 2:
                    substitutes.append(mat_id)

        return substitutes

    def reflect_vertical(self, vertices: Dict, shapes: List) -> Tuple[Dict, List]:
        """Reflect pattern vertically: (x,y) -> (x,-y)."""
        new_vertices = {}
        coord_mapping = {}

        for coord_str, vertex_data in vertices.items():
            x, y = map(int, coord_str.split(','))
            new_coord_str = f"{x},{-y}"
            new_vertices[new_coord_str] = copy.deepcopy(vertex_data)
            coord_mapping[coord_str] = new_coord_str

        new_shapes = []
        for shape in shapes:
            new_shape = copy.deepcopy(shape)
            new_shape['vertices'] = [coord_mapping.get(v, v) for v in shape.get('vertices', [])]
            new_shapes.append(new_shape)

        return new_vertices, new_shapes

    def reflect_horizontal(self, vertices: Dict, shapes: List) -> Tuple[Dict, List]:
        """Reflect pattern horizontally: (x,y) -> (-x,y)."""
        new_vertices = {}
        coord_mapping = {}

        for coord_str, vertex_data in vertices.items():
            x, y = map(int, coord_str.split(','))
            new_coord_str = f"{-x},{y}"
            new_vertices[new_coord_str] = copy.deepcopy(vertex_data)
            coord_mapping[coord_str] = new_coord_str

        new_shapes = []
        for shape in shapes:
            new_shape = copy.deepcopy(shape)
            new_shape['vertices'] = [coord_mapping.get(v, v) for v in shape.get('vertices', [])]
            new_shapes.append(new_shape)

        return new_vertices, new_shapes

    def augment_pattern(self, vertices: Dict, shapes: List) -> List[Tuple[Dict, List, Dict]]:
        """
        Generate augmented patterns with material substitution and reflections.
        Returns list of (vertices, shapes, substitution_map) tuples.
        """
        variants = [(vertices, shapes, {})]  # Original

        # Add reflections
        v_reflect, s_reflect = self.reflect_vertical(vertices, shapes)
        variants.append((v_reflect, s_reflect, {'_reflected': 'vertical'}))

        h_reflect, h_shapes = self.reflect_horizontal(vertices, shapes)
        variants.append((h_reflect, h_shapes, {'_reflected': 'horizontal'}))

        # Find unique materials
        unique_materials = set()
        for vertex_data in vertices.values():
            mat_id = vertex_data.get('materialId')
            if mat_id:
                unique_materials.add(mat_id)

        # Generate substitution variants
        for material_id in unique_materials:
            substitutes = self.find_substitutable_materials(material_id)

            for sub_mat in substitutes:
                # Create variant with substitution
                new_vertices = copy.deepcopy(vertices)
                for coord_str, vertex_data in new_vertices.items():
                    if vertex_data.get('materialId') == material_id:
                        vertex_data['materialId'] = sub_mat

                sub_map = {material_id: sub_mat}
                variants.append((new_vertices, shapes, sub_map))

                # Also add reflected versions
                v_reflect, s_reflect = self.reflect_vertical(new_vertices, shapes)
                variants.append((v_reflect, s_reflect, {**sub_map, '_reflected': 'vertical'}))

        # Remove duplicates based on vertex content
        unique_variants = []
        seen = set()
        for verts, shps, sub_map in variants:
            # Create hashable representation
            vert_tuple = tuple(sorted((k, v.get('materialId', '')) for k, v in verts.items()))
            if vert_tuple not in seen:
                seen.add(vert_tuple)
                unique_variants.append((verts, shps, sub_map))

        return unique_variants

    def vertices_to_enriched_recipe(self, placement: Dict, vertices: Dict,
                                     sub_map: Dict, variation_index: int) -> Dict:
        """Create material-enriched recipe with substitution tracking."""
        base_recipe_id = placement['recipeId']

        # Build recipe ID suffix
        sub_suffix = ""
        for orig, sub in sub_map.items():
            if not orig.startswith('_'):
                sub_suffix += f"_{sub.split('_')[0]}"
        if sub_map.get('_reflected'):
            sub_suffix += f"_{sub_map['_reflected'][:4]}"

        recipe_id = f"{base_recipe_id}{sub_suffix}_v{variation_index}"

        # Count materials
        material_counts = {}
        for coord_str, vertex_data in vertices.items():
            mat_id = vertex_data.get('materialId')
            if mat_id:
                var_name, var_tags = self.variation_namer.get_variation_name(mat_id, variation_index)
                if var_name not in material_counts:
                    material_counts[var_name] = {
                        "materialId": var_name,
                        "quantity": 0,
                        "positions": [],
                        "base_material": mat_id,
                        "variation_tags": var_tags
                    }
                material_counts[var_name]['quantity'] += 1
                material_counts[var_name]['positions'].append(coord_str)

        inputs = []
        for mat_data in material_counts.values():
            input_item = {
                "materialId": mat_data['materialId'],
                "quantity": mat_data['quantity'],
                "positions": mat_data['positions']
            }
            enriched = self.enricher.enrich_input(
                {"materialId": mat_data['base_material']},
                mat_data['variation_tags']
            )
            input_item['material_metadata'] = enriched.get('material_metadata', {})
            inputs.append(input_item)

        recipe = {
            "recipeId": recipe_id,
            "stationType": "enchanting",
            "stationTier": self._infer_station_tier(vertices),
            "inputs": inputs
        }

        return recipe

    def generate(self, output_dir: str = None, save_images: bool = True) -> List[Dict]:
        """Generate training data with full augmentation pipeline."""
        training_data = []

        if output_dir and save_images:
            os.makedirs(output_dir, exist_ok=True)
            img_dir = os.path.join(output_dir, 'adornment_images')
            os.makedirs(img_dir, exist_ok=True)

        print(f"\nProcessing {len(self.placements)} adornment recipes...")
        print(f"Augmentation: material substitution + reflections + {self.num_color_variations} color variations")

        total_patterns = 0

        for placement in self.placements:
            recipe_id = placement['recipeId']
            vertices, shapes = self.parse_placement(placement)

            if not vertices:
                print(f"  Skipping {recipe_id}: no vertices")
                continue

            # Step 1: Generate all pattern variants
            pattern_variants = self.augment_pattern(vertices, shapes)
            total_patterns += len(pattern_variants)

            print(f"  {recipe_id}: {len(pattern_variants)} pattern variants")

            # Step 2: For each pattern, generate color variations
            for verts, shps, sub_map in pattern_variants:
                # Variation 0: Exact colors
                img_exact = self.render_to_image(verts, shps, 0, 0)
                recipe_exact = self.vertices_to_enriched_recipe(placement, verts, sub_map, 0)

                entry = {
                    "recipe_id": recipe_exact['recipeId'],
                    "variation": "original",
                    "image_base64": self.image_to_base64(img_exact),
                    "recipe": recipe_exact
                }
                training_data.append(entry)

                if output_dir and save_images and PIL_AVAILABLE:
                    safe_id = recipe_exact['recipeId'].replace('/', '_')[:100]
                    img_path = os.path.join(img_dir, f"{safe_id}.png")
                    self.save_image_to_disk(img_exact, img_path)

                # Color variations
                for v_idx in range(1, self.num_color_variations + 1):
                    val_offset = random.uniform(-0.10, 0.10)
                    sat_offset = random.uniform(-0.15, 0.15)

                    img_varied = self.render_to_image(verts, shps, val_offset, sat_offset)
                    recipe_varied = self.vertices_to_enriched_recipe(placement, verts, sub_map, v_idx)

                    var_name = self.variation_namer.all_prefixes[(v_idx - 1) % len(self.variation_namer.all_prefixes)][0]

                    entry = {
                        "recipe_id": recipe_varied['recipeId'],
                        "variation": var_name,
                        "image_base64": self.image_to_base64(img_varied),
                        "recipe": recipe_varied
                    }
                    training_data.append(entry)

                    if output_dir and save_images and PIL_AVAILABLE:
                        safe_id = recipe_varied['recipeId'].replace('/', '_')[:100]
                        img_path = os.path.join(img_dir, f"{safe_id}.png")
                        self.save_image_to_disk(img_varied, img_path)

        print(f"\n=== Adornment Augmentation Summary ===")
        print(f"Base recipes: {len(self.placements)}")
        print(f"Pattern variants (material sub + reflections): {total_patterns}")
        print(f"Color variations per pattern: {1 + self.num_color_variations}")
        print(f"Total training examples: {len(training_data)}")

        return training_data


# ============================================================================
# LLM DATA GENERATORS (Refining, Alchemy, Engineering)
# ============================================================================

class RefiningLLMDataGenerator:
    """
    Generates LLM training data for Refining discipline.
    No images - just material-enriched recipes.
    """

    def __init__(self, materials_path: str, placements_path: str):
        """Initialize the generator."""
        self.enricher = MaterialEnricher(materials_path)
        self.variation_namer = VariationNamer()

        # Load materials
        with open(materials_path, 'r') as f:
            data = json.load(f)
        self.materials_dict = {m['materialId']: m for m in data.get('materials', [])}

        # Load placements
        with open(placements_path, 'r') as f:
            data = json.load(f)
        self.placements = data.get('placements', [])

        print(f"Loaded {len(self.materials_dict)} materials")
        print(f"Loaded {len(self.placements)} refining placements")

    def find_substitutable_materials(self, material_id: str) -> List[str]:
        """Find materials that can substitute for this one."""
        if material_id not in self.materials_dict:
            return []

        base_mat = self.materials_dict[material_id]
        base_tags = set(base_mat.get('metadata', {}).get('tags', []))
        base_category = base_mat.get('category', 'unknown')
        base_tier = base_mat.get('tier', 1)

        base_is_refined = 'refined' in base_tags
        base_is_basic = 'basic' in base_tags or 'raw' in base_tags

        substitutes = []

        for candidate_id, candidate in self.materials_dict.items():
            if candidate_id == material_id:
                continue
            if candidate.get('category') != base_category:
                continue

            candidate_tags = set(candidate.get('metadata', {}).get('tags', []))
            candidate_tier = candidate.get('tier', 1)

            candidate_is_refined = 'refined' in candidate_tags
            candidate_is_basic = 'basic' in candidate_tags or 'raw' in candidate_tags

            if base_is_refined != candidate_is_refined:
                continue
            if base_is_basic != candidate_is_basic:
                continue

            # Same tags (any tier) or ±1 tier with ≥2 matching tags
            if candidate_tags == base_tags:
                substitutes.append(candidate_id)
            elif abs(candidate_tier - base_tier) <= 1 and len(base_tags & candidate_tags) >= 2:
                substitutes.append(candidate_id)

        return substitutes

    def create_enriched_recipe(self, placement: Dict, variation_index: int = 0,
                               material_substitutions: Dict[str, str] = None) -> Dict:
        """Create material-enriched recipe."""
        recipe_id = placement['recipeId']
        if variation_index > 0:
            recipe_id = f"{recipe_id}_v{variation_index}"

        # Get core and surrounding inputs
        core_inputs = []
        for core in placement.get('coreInputs', []):
            mat_id = core.get('materialId')
            if material_substitutions and mat_id in material_substitutions:
                mat_id = material_substitutions[mat_id]

            var_name, var_tags = self.variation_namer.get_variation_name(mat_id, variation_index)

            input_item = {
                "materialId": var_name,
                "quantity": core.get('quantity', 1)
            }
            enriched = self.enricher.enrich_input({"materialId": mat_id}, var_tags)
            input_item['material_metadata'] = enriched.get('material_metadata', {})
            core_inputs.append(input_item)

        surrounding_inputs = []
        for spoke in placement.get('surroundingInputs', []):
            mat_id = spoke.get('materialId')
            if material_substitutions and mat_id in material_substitutions:
                mat_id = material_substitutions[mat_id]

            var_name, var_tags = self.variation_namer.get_variation_name(mat_id, variation_index)

            input_item = {
                "materialId": var_name,
                "quantity": spoke.get('quantity', 1)
            }
            enriched = self.enricher.enrich_input({"materialId": mat_id}, var_tags)
            input_item['material_metadata'] = enriched.get('material_metadata', {})
            surrounding_inputs.append(input_item)

        recipe = {
            "recipeId": recipe_id,
            "stationType": "refining",
            "stationTier": placement.get('stationTier', 1),
            "outputId": placement.get('outputId', ''),
            "coreInputs": core_inputs,
            "surroundingInputs": surrounding_inputs
        }

        return recipe

    def augment_material_substitutions(self, placement: Dict) -> List[Dict[str, str]]:
        """
        Generate all material substitution combinations using cross-product.
        Returns list of substitution maps: [{original_id: substituted_id, ...}, ...]
        """
        # Get all materials in recipe
        core_materials = [core.get('materialId') for core in placement.get('coreInputs', [])]
        spoke_materials = [spoke.get('materialId') for spoke in placement.get('surroundingInputs', [])]

        # Get substitution options for each position
        core_options = []
        for mat_id in core_materials:
            if mat_id:
                subs = [mat_id] + self.find_substitutable_materials(mat_id)[:5]  # Limit per material
                core_options.append((mat_id, subs))

        spoke_options = []
        for mat_id in spoke_materials:
            if mat_id:
                subs = [mat_id] + self.find_substitutable_materials(mat_id)[:5]
                spoke_options.append((mat_id, subs))

        # Generate cross-product of substitutions
        all_substitutions = [{}]  # Start with empty (original)

        for orig_mat, subs in core_options + spoke_options:
            new_substitutions = []
            for existing_sub in all_substitutions:
                for sub_mat in subs:
                    new_sub = existing_sub.copy()
                    if sub_mat != orig_mat:
                        new_sub[orig_mat] = sub_mat
                    new_substitutions.append(new_sub)
            all_substitutions = new_substitutions

        # Remove duplicates and limit
        unique_subs = []
        seen = set()
        for sub_map in all_substitutions:
            key = tuple(sorted(sub_map.items()))
            if key not in seen:
                seen.add(key)
                unique_subs.append(sub_map)

        # Cap at reasonable limit
        if len(unique_subs) > 50:
            unique_subs = random.sample(unique_subs, 50)

        return unique_subs

    def augment_permutations(self, placement: Dict, sub_map: Dict[str, str]) -> List[Dict]:
        """Generate permutation variants of core and spoke ordering."""
        variants = []

        core_inputs = placement.get('coreInputs', [])
        spoke_inputs = placement.get('surroundingInputs', [])

        # Permute core inputs
        core_perms = list(itertools.permutations(core_inputs))
        if len(core_perms) > 6:
            core_perms = random.sample(core_perms, 6)

        # Permute spoke inputs
        if spoke_inputs:
            spoke_perms = list(itertools.permutations(spoke_inputs))
            if len(spoke_perms) > 4:
                spoke_perms = random.sample(spoke_perms, 4)
        else:
            spoke_perms = [tuple()]

        for core_perm in core_perms:
            for spoke_perm in spoke_perms:
                variant = {
                    'recipeId': placement['recipeId'],
                    'outputId': placement.get('outputId', ''),
                    'stationTier': placement.get('stationTier', 1),
                    'coreInputs': list(core_perm),
                    'surroundingInputs': list(spoke_perm) if spoke_perm else []
                }
                variants.append(variant)

        return variants

    def generate(self) -> List[Dict]:
        """Generate training data with full augmentation pipeline."""
        training_data = []

        print(f"\nProcessing {len(self.placements)} refining recipes...")
        print(f"Augmentation: material substitution cross-product + permutations")

        total_variants = 0
        variant_idx = 0

        for placement in self.placements:
            recipe_id = placement['recipeId']

            # Step 1: Generate material substitution combinations
            substitution_maps = self.augment_material_substitutions(placement)

            # Step 2: For each substitution, generate permutation variants
            recipe_variants = []
            for sub_map in substitution_maps:
                perm_variants = self.augment_permutations(placement, sub_map)
                for perm_variant in perm_variants:
                    recipe_variants.append((perm_variant, sub_map))

            total_variants += len(recipe_variants)

            # Step 3: Create enriched recipes
            for variant_placement, sub_map in recipe_variants:
                recipe = self.create_enriched_recipe(variant_placement, variant_idx, sub_map)
                training_data.append({
                    "recipe_id": recipe['recipeId'],
                    "recipe": recipe
                })
                variant_idx += 1

            print(f"  {recipe_id}: {len(recipe_variants)} variants")

        print(f"\n=== Refining Augmentation Summary ===")
        print(f"Base recipes: {len(self.placements)}")
        print(f"Total variants: {total_variants}")
        print(f"Total training examples: {len(training_data)}")

        return training_data


class AlchemyLLMDataGenerator:
    """Generates LLM training data for Alchemy discipline."""

    def __init__(self, materials_path: str, placements_path: str):
        """Initialize the generator."""
        self.enricher = MaterialEnricher(materials_path)
        self.variation_namer = VariationNamer()

        with open(materials_path, 'r') as f:
            data = json.load(f)
        self.materials_dict = {m['materialId']: m for m in data.get('materials', [])}

        with open(placements_path, 'r') as f:
            data = json.load(f)
        self.placements = data.get('placements', [])

        print(f"Loaded {len(self.materials_dict)} materials")
        print(f"Loaded {len(self.placements)} alchemy placements")

    def find_substitutable_materials(self, material_id: str) -> List[str]:
        """Find substitutable materials."""
        if material_id not in self.materials_dict:
            return []

        base_mat = self.materials_dict[material_id]
        base_tags = set(base_mat.get('metadata', {}).get('tags', []))
        base_category = base_mat.get('category', 'unknown')
        base_tier = base_mat.get('tier', 1)

        base_is_refined = 'refined' in base_tags
        base_is_basic = 'basic' in base_tags or 'raw' in base_tags

        substitutes = []

        for candidate_id, candidate in self.materials_dict.items():
            if candidate_id == material_id:
                continue
            if candidate.get('category') != base_category:
                continue

            candidate_tags = set(candidate.get('metadata', {}).get('tags', []))
            candidate_tier = candidate.get('tier', 1)

            candidate_is_refined = 'refined' in candidate_tags
            candidate_is_basic = 'basic' in candidate_tags or 'raw' in candidate_tags

            if base_is_refined != candidate_is_refined:
                continue
            if base_is_basic != candidate_is_basic:
                continue

            if candidate_tags == base_tags:
                substitutes.append(candidate_id)
            elif abs(candidate_tier - base_tier) <= 1 and len(base_tags & candidate_tags) >= 2:
                substitutes.append(candidate_id)

        return substitutes

    def create_enriched_recipe(self, placement: Dict, variation_index: int = 0,
                               material_substitutions: Dict[str, str] = None) -> Dict:
        """Create material-enriched alchemy recipe."""
        recipe_id = placement['recipeId']
        if variation_index > 0:
            recipe_id = f"{recipe_id}_v{variation_index}"

        ingredients = []
        for ing in placement.get('ingredients', []):
            mat_id = ing.get('materialId')
            if material_substitutions and mat_id in material_substitutions:
                mat_id = material_substitutions[mat_id]

            var_name, var_tags = self.variation_namer.get_variation_name(mat_id, variation_index)

            input_item = {
                "materialId": var_name,
                "quantity": ing.get('quantity', 1),
                "slot": ing.get('slot', 1)
            }
            enriched = self.enricher.enrich_input({"materialId": mat_id}, var_tags)
            input_item['material_metadata'] = enriched.get('material_metadata', {})
            ingredients.append(input_item)

        recipe = {
            "recipeId": recipe_id,
            "stationType": "alchemy",
            "stationTier": placement.get('stationTier', 1),
            "outputId": placement.get('outputId', ''),
            "ingredients": ingredients
        }

        return recipe

    def augment_material_substitutions(self, placement: Dict) -> List[Dict[str, str]]:
        """Generate all material substitution combinations using cross-product."""
        ingredients = placement.get('ingredients', [])

        # Get substitution options for each ingredient
        slot_options = []
        for ing in ingredients:
            mat_id = ing.get('materialId')
            if mat_id:
                subs = [mat_id] + self.find_substitutable_materials(mat_id)[:5]
                slot_options.append((mat_id, subs))

        # Generate cross-product of substitutions
        all_substitutions = [{}]

        for orig_mat, subs in slot_options:
            new_substitutions = []
            for existing_sub in all_substitutions:
                for sub_mat in subs:
                    new_sub = existing_sub.copy()
                    if sub_mat != orig_mat:
                        new_sub[orig_mat] = sub_mat
                    new_substitutions.append(new_sub)
            all_substitutions = new_substitutions

        # Remove duplicates and limit
        unique_subs = []
        seen = set()
        for sub_map in all_substitutions:
            key = tuple(sorted(sub_map.items()))
            if key not in seen:
                seen.add(key)
                unique_subs.append(sub_map)

        if len(unique_subs) > 40:
            unique_subs = random.sample(unique_subs, 40)

        return unique_subs

    def augment_permutations(self, placement: Dict, sub_map: Dict[str, str]) -> List[Dict]:
        """Generate permutation variants of ingredient sequence."""
        ingredients = placement.get('ingredients', [])

        perms = list(itertools.permutations(ingredients))
        if len(perms) > 24:
            perms = random.sample(perms, 24)

        variants = []
        for perm in perms:
            # Reassign slot numbers based on new order
            new_ingredients = []
            for i, ing in enumerate(perm, start=1):
                new_ing = ing.copy()
                new_ing['slot'] = i
                new_ingredients.append(new_ing)

            variant = {
                'recipeId': placement['recipeId'],
                'outputId': placement.get('outputId', ''),
                'stationTier': placement.get('stationTier', 1),
                'ingredients': new_ingredients
            }
            variants.append(variant)

        return variants

    def generate(self) -> List[Dict]:
        """Generate training data with full augmentation pipeline."""
        training_data = []

        print(f"\nProcessing {len(self.placements)} alchemy recipes...")
        print(f"Augmentation: material substitution cross-product + permutations")

        total_variants = 0
        variant_idx = 0

        for placement in self.placements:
            recipe_id = placement['recipeId']

            # Step 1: Generate material substitution combinations
            substitution_maps = self.augment_material_substitutions(placement)

            # Step 2: For each substitution, generate permutation variants
            recipe_variants = []
            for sub_map in substitution_maps:
                perm_variants = self.augment_permutations(placement, sub_map)
                for perm_variant in perm_variants:
                    recipe_variants.append((perm_variant, sub_map))

            # Limit total variants per recipe
            if len(recipe_variants) > 100:
                recipe_variants = random.sample(recipe_variants, 100)

            total_variants += len(recipe_variants)

            # Step 3: Create enriched recipes
            for variant_placement, sub_map in recipe_variants:
                recipe = self.create_enriched_recipe(variant_placement, variant_idx, sub_map)
                training_data.append({
                    "recipe_id": recipe['recipeId'],
                    "recipe": recipe
                })
                variant_idx += 1

            print(f"  {recipe_id}: {len(recipe_variants)} variants")

        print(f"\n=== Alchemy Augmentation Summary ===")
        print(f"Base recipes: {len(self.placements)}")
        print(f"Total variants: {total_variants}")
        print(f"Total training examples: {len(training_data)}")

        return training_data


class EngineeringLLMDataGenerator:
    """Generates LLM training data for Engineering discipline."""

    def __init__(self, materials_path: str, placements_path: str):
        """Initialize the generator."""
        self.enricher = MaterialEnricher(materials_path)
        self.variation_namer = VariationNamer()

        with open(materials_path, 'r') as f:
            data = json.load(f)
        self.materials_dict = {m['materialId']: m for m in data.get('materials', [])}

        with open(placements_path, 'r') as f:
            data = json.load(f)
        self.placements = data.get('placements', [])

        print(f"Loaded {len(self.materials_dict)} materials")
        print(f"Loaded {len(self.placements)} engineering placements")

    def find_substitutable_materials(self, material_id: str) -> List[str]:
        """Find substitutable materials."""
        if material_id not in self.materials_dict:
            return []

        base_mat = self.materials_dict[material_id]
        base_tags = set(base_mat.get('metadata', {}).get('tags', []))
        base_category = base_mat.get('category', 'unknown')
        base_tier = base_mat.get('tier', 1)

        base_is_refined = 'refined' in base_tags
        base_is_basic = 'basic' in base_tags or 'raw' in base_tags

        substitutes = []

        for candidate_id, candidate in self.materials_dict.items():
            if candidate_id == material_id:
                continue
            if candidate.get('category') != base_category:
                continue

            candidate_tags = set(candidate.get('metadata', {}).get('tags', []))
            candidate_tier = candidate.get('tier', 1)

            candidate_is_refined = 'refined' in candidate_tags
            candidate_is_basic = 'basic' in candidate_tags or 'raw' in candidate_tags

            if base_is_refined != candidate_is_refined:
                continue
            if base_is_basic != candidate_is_basic:
                continue

            if candidate_tags == base_tags:
                substitutes.append(candidate_id)
            elif abs(candidate_tier - base_tier) <= 1 and len(base_tags & candidate_tags) >= 2:
                substitutes.append(candidate_id)

        return substitutes

    def create_enriched_recipe(self, placement: Dict, variation_index: int = 0,
                               material_substitutions: Dict[str, str] = None) -> Dict:
        """Create material-enriched engineering recipe."""
        recipe_id = placement['recipeId']
        if variation_index > 0:
            recipe_id = f"{recipe_id}_v{variation_index}"

        slots = []
        for slot in placement.get('slots', []):
            mat_id = slot.get('materialId')
            if material_substitutions and mat_id in material_substitutions:
                mat_id = material_substitutions[mat_id]

            var_name, var_tags = self.variation_namer.get_variation_name(mat_id, variation_index)

            slot_item = {
                "materialId": var_name,
                "quantity": slot.get('quantity', 1),
                "type": slot.get('type', 'FRAME')
            }
            enriched = self.enricher.enrich_input({"materialId": mat_id}, var_tags)
            slot_item['material_metadata'] = enriched.get('material_metadata', {})
            slots.append(slot_item)

        recipe = {
            "recipeId": recipe_id,
            "stationType": "engineering",
            "stationTier": placement.get('stationTier', 1),
            "outputId": placement.get('outputId', ''),
            "slots": slots
        }

        return recipe

    def augment_material_substitutions(self, placement: Dict) -> List[Dict[str, str]]:
        """Generate all material substitution combinations using cross-product."""
        slots = placement.get('slots', [])

        # Get substitution options for each slot
        slot_options = []
        for slot in slots:
            mat_id = slot.get('materialId')
            if mat_id:
                subs = [mat_id] + self.find_substitutable_materials(mat_id)[:5]
                slot_options.append((mat_id, subs))

        # Generate cross-product of substitutions
        all_substitutions = [{}]

        for orig_mat, subs in slot_options:
            new_substitutions = []
            for existing_sub in all_substitutions:
                for sub_mat in subs:
                    new_sub = existing_sub.copy()
                    if sub_mat != orig_mat:
                        new_sub[orig_mat] = sub_mat
                    new_substitutions.append(new_sub)
            all_substitutions = new_substitutions

        # Remove duplicates and limit
        unique_subs = []
        seen = set()
        for sub_map in all_substitutions:
            key = tuple(sorted(sub_map.items()))
            if key not in seen:
                seen.add(key)
                unique_subs.append(sub_map)

        if len(unique_subs) > 50:
            unique_subs = random.sample(unique_subs, 50)

        return unique_subs

    def augment_optional_slots(self, placement: Dict) -> List[Dict]:
        """Generate variants with/without optional slots."""
        optional_types = {'MODIFIER', 'ENHANCEMENT', 'CORE', 'CATALYST', 'UTILITY'}

        slots = placement.get('slots', [])
        variants = [placement]  # Original

        optional_slots = [
            (i, slot) for i, slot in enumerate(slots)
            if slot.get('type') in optional_types
        ]

        if not optional_slots:
            return variants

        # Try removing 1 or 2 optional slots
        for num_to_remove in range(1, min(3, len(optional_slots) + 1)):
            for slots_to_remove in itertools.combinations(optional_slots, num_to_remove):
                remove_indices = {idx for idx, _ in slots_to_remove}
                new_slots = [
                    slot for i, slot in enumerate(slots)
                    if i not in remove_indices
                ]

                variant = {
                    'recipeId': placement['recipeId'],
                    'outputId': placement.get('outputId', ''),
                    'stationTier': placement.get('stationTier', 1),
                    'slots': new_slots
                }
                variants.append(variant)

        return variants[:8]

    def generate(self) -> List[Dict]:
        """Generate training data with full augmentation pipeline."""
        training_data = []

        print(f"\nProcessing {len(self.placements)} engineering recipes...")
        print(f"Augmentation: material substitution cross-product + optional slot variants")

        total_variants = 0
        variant_idx = 0

        for placement in self.placements:
            recipe_id = placement['recipeId']

            # Step 1: Generate material substitution combinations
            substitution_maps = self.augment_material_substitutions(placement)

            # Step 2: For each substitution, generate optional slot variants
            recipe_variants = []
            for sub_map in substitution_maps:
                slot_variants = self.augment_optional_slots(placement)
                for slot_variant in slot_variants:
                    recipe_variants.append((slot_variant, sub_map))

            # Limit total variants per recipe
            if len(recipe_variants) > 100:
                recipe_variants = random.sample(recipe_variants, 100)

            total_variants += len(recipe_variants)

            # Step 3: Create enriched recipes
            for variant_placement, sub_map in recipe_variants:
                recipe = self.create_enriched_recipe(variant_placement, variant_idx, sub_map)
                training_data.append({
                    "recipe_id": recipe['recipeId'],
                    "recipe": recipe
                })
                variant_idx += 1

            print(f"  {recipe_id}: {len(recipe_variants)} variants")

        print(f"\n=== Engineering Augmentation Summary ===")
        print(f"Base recipes: {len(self.placements)}")
        print(f"Total variants: {total_variants}")
        print(f"Total training examples: {len(training_data)}")

        return training_data


# ============================================================================
# GENERATION MODES AND MENU SYSTEM
# ============================================================================

class GenerationMode:
    """
    Generation modes for controlling data output:

    Mode 1 - ALL: Full augmentation + synthetic (original + augmented + synthetic variations)
             Creates maximum diversity but may be too large for practical use

    Mode 2 - SYNTHETIC_ONLY: Original + synthetic variations (no material substitution)
             Creates 3x synthetic variations per original (color/naming variations)

    Mode 3 - AUGMENTED_ONLY: Original + augmented (material substitution, flips, permutations)
             No synthetic color/naming variations, just structural augmentation

    Mode 4 - CUSTOM: User-defined parameters per discipline
    """
    ALL = 1
    SYNTHETIC_ONLY = 2
    AUGMENTED_ONLY = 3
    CUSTOM = 4

    @staticmethod
    def get_mode_description(mode: int) -> str:
        descriptions = {
            1: "All data (augmented + synthetic + original) - Maximum diversity",
            2: "Just synthetic (original + 3x synthetic variations) - No material substitution",
            3: "Just augmented (original + augmented) - No synthetic color variations",
            4: "Customized (specify parameters per discipline)"
        }
        return descriptions.get(mode, "Unknown mode")


def estimate_counts(paths: Dict, mode: int, color_variations: int = 3) -> Dict[str, Dict]:
    """
    Estimate output counts for each discipline based on mode.

    Returns dict with structure:
    {
        'discipline_name': {
            'base_recipes': int,
            'estimated_augmented': int,
            'estimated_synthetic_per_variant': int,
            'estimated_total': int
        }
    }
    """
    estimates = {}

    # Load placement counts for estimation
    for discipline, discipline_paths in paths.items():
        try:
            with open(discipline_paths['placements'], 'r') as f:
                data = json.load(f)
            placements = data.get('placements', [])
            base_count = len(placements)
        except:
            base_count = 0

        # Estimate augmentation multiplier based on discipline
        # These are rough estimates based on typical material diversity
        aug_multipliers = {
            'smithing': 12,      # ~12 grid variants per recipe (material sub + flips)
            'adornment': 8,      # ~8 pattern variants (material sub + reflections)
            'refining': 50,      # Cross-product can explode (capped at 50)
            'alchemy': 100,      # Cross-product + permutations (capped at 100)
            'engineering': 100,  # Cross-product + slot variants (capped at 100)
        }

        aug_mult = aug_multipliers.get(discipline, 10)

        if mode == GenerationMode.ALL:
            # Full augmentation × (1 exact + color_variations)
            aug_variants = base_count * aug_mult
            synthetic_mult = 1 + color_variations
            total = aug_variants * synthetic_mult

        elif mode == GenerationMode.SYNTHETIC_ONLY:
            # Original × (1 + 3 synthetic)
            aug_variants = base_count
            synthetic_mult = 4  # 1 original + 3 synthetic
            total = base_count * synthetic_mult

        elif mode == GenerationMode.AUGMENTED_ONLY:
            # Augmented variants × 1 (exact colors only)
            aug_variants = base_count * aug_mult
            synthetic_mult = 1
            total = aug_variants

        else:  # CUSTOM
            aug_variants = base_count * aug_mult
            synthetic_mult = 1 + color_variations
            total = aug_variants * synthetic_mult

        estimates[discipline] = {
            'base_recipes': base_count,
            'estimated_augmented': aug_variants,
            'estimated_synthetic_per_variant': synthetic_mult,
            'estimated_total': total
        }

    return estimates


def display_estimates(estimates: Dict, mode: int):
    """Display estimated counts for user review."""
    print("\n" + "=" * 70)
    print(f"ESTIMATED OUTPUT COUNTS (Mode {mode}: {GenerationMode.get_mode_description(mode)})")
    print("=" * 70)
    print(f"{'Discipline':<15} {'Base':<8} {'Augmented':<12} {'×Synthetic':<12} {'Total':<10}")
    print("-" * 70)

    grand_total = 0
    for discipline, est in estimates.items():
        print(f"{discipline:<15} {est['base_recipes']:<8} {est['estimated_augmented']:<12} "
              f"×{est['estimated_synthetic_per_variant']:<11} {est['estimated_total']:<10}")
        grand_total += est['estimated_total']

    print("-" * 70)
    print(f"{'GRAND TOTAL':<15} {'':<8} {'':<12} {'':<12} {grand_total:<10}")
    print("=" * 70)


def show_menu() -> int:
    """Display menu and get user selection."""
    print("\n" + "=" * 70)
    print("CRAFTING TRAINING DATA GENERATOR - MODE SELECTION")
    print("=" * 70)
    print("\nSelect generation mode:\n")
    print("  1. All data (augmented + synthetic + original)")
    print("     → Maximum diversity, typically 1000-5000 examples per discipline")
    print("     → Includes material substitution, flips, permutations, AND color variations")
    print()
    print("  2. Just synthetic (original + 3x synthetic variations)")
    print("     → Minimal structural variation, moderate output")
    print("     → Good for testing LLM with naming/tag variations")
    print()
    print("  3. Just augmented (augmented + original, no synthetic)")
    print("     → Structural diversity without color/naming variations")
    print("     → Each variant has exact colors only")
    print()
    print("  4. Customized (specify parameters)")
    print("     → Fine-tune augmentation and caps per discipline")
    print()

    while True:
        try:
            choice = input("Enter mode (1-4): ").strip()
            mode = int(choice)
            if 1 <= mode <= 4:
                return mode
            print("Please enter a number between 1 and 4.")
        except ValueError:
            print("Please enter a valid number.")
        except EOFError:
            # Default to mode 3 if running non-interactively
            print("\nNon-interactive mode detected. Using mode 3 (augmented only).")
            return GenerationMode.AUGMENTED_ONLY


def parse_discipline_selection(selection: str) -> List[str]:
    """
    Parse discipline selection string into list of discipline names.

    Accepts:
    - Single number: "1" → ['smithing']
    - Comma-separated: "1,3,5" → ['smithing', 'refining', 'engineering']
    - Range: "1-4" → ['smithing', 'adornment', 'refining', 'alchemy']
    - Mixed: "1,3-5" → ['smithing', 'refining', 'alchemy', 'engineering']
    """
    DISCIPLINE_MAP = {
        1: 'smithing',
        2: 'adornment',
        3: 'refining',
        4: 'alchemy',
        5: 'engineering'
    }

    selected = set()
    parts = selection.replace(' ', '').split(',')

    for part in parts:
        if '-' in part:
            # Range: "1-4"
            try:
                start, end = map(int, part.split('-'))
                for i in range(start, end + 1):
                    if i in DISCIPLINE_MAP:
                        selected.add(DISCIPLINE_MAP[i])
            except ValueError:
                pass
        else:
            # Single number
            try:
                num = int(part)
                if num in DISCIPLINE_MAP:
                    selected.add(DISCIPLINE_MAP[num])
            except ValueError:
                pass

    # Return in canonical order
    order = ['smithing', 'adornment', 'refining', 'alchemy', 'engineering']
    return [d for d in order if d in selected]


def get_custom_params() -> Dict:
    """
    Get customized parameters from user.

    Custom mode workflow:
    1. Select disciplines (1-6, where 6 allows custom selection)
    2. Enter sample count per discipline
    3. Data is generated in quality order: original → augmented → variation → variation+augmented
    """
    print("\n" + "=" * 70)
    print("CUSTOM MODE - DISCIPLINE SELECTION")
    print("=" * 70)
    print("\nSelect disciplines to generate:\n")
    print("  1. Smithing (VLM - images + recipes)")
    print("  2. Adornment (VLM - images + recipes)")
    print("  3. Refining (LLM - recipes only)")
    print("  4. Alchemy (LLM - recipes only)")
    print("  5. Engineering (LLM - recipes only)")
    print("  6. Custom selection (e.g., '1,3,5' or '1-4' or '2,4-5')")
    print()

    params = {}

    # Get discipline selection
    try:
        choice = input("Enter selection (1-6): ").strip()

        if choice == '6':
            # Custom selection
            custom_sel = input("Enter disciplines (e.g., '1,3,5' or '1-4'): ").strip()
            params['disciplines'] = parse_discipline_selection(custom_sel)
        elif choice in ['1', '2', '3', '4', '5']:
            discipline_map = {
                '1': ['smithing'],
                '2': ['adornment'],
                '3': ['refining'],
                '4': ['alchemy'],
                '5': ['engineering']
            }
            params['disciplines'] = discipline_map[choice]
        else:
            print("Invalid selection, using all disciplines.")
            params['disciplines'] = ['smithing', 'adornment', 'refining', 'alchemy', 'engineering']

    except EOFError:
        params['disciplines'] = ['smithing', 'adornment', 'refining', 'alchemy', 'engineering']

    if not params['disciplines']:
        print("No valid disciplines selected, using all.")
        params['disciplines'] = ['smithing', 'adornment', 'refining', 'alchemy', 'engineering']

    print(f"\nSelected: {', '.join(params['disciplines'])}")

    # Get sample count per discipline
    print("\n" + "-" * 70)
    print("SAMPLE COUNT")
    print("-" * 70)
    print("\nData quality order (highest to lowest):")
    print("  1. Original recipes (base recipes, no modifications)")
    print("  2. Augmented original (material substitution, exact colors)")
    print("  3. Variation original (color/naming variations of originals)")
    print("  4. Variation augmented (color/naming variations of augmented)")
    print("\nSamples are filled in quality order until count is reached.")
    print()

    params['sample_counts'] = {}

    for discipline in params['disciplines']:
        try:
            count = input(f"Samples for {discipline} (default 500): ").strip()
            params['sample_counts'][discipline] = int(count) if count else 500
        except (ValueError, EOFError):
            params['sample_counts'][discipline] = 500

    return params


def generate_quality_ordered(discipline: str, paths: Dict, sample_count: int,
                             output_dir: str = None, save_images: bool = False) -> List[Dict]:
    """
    Generate training data in quality order up to sample_count.

    Quality order (highest to lowest):
    1. Original recipes (base, no modifications)
    2. Augmented original (material substitution, exact colors)
    3. Variation original (naming/color variations of base recipes)
    4. Variation augmented (naming/color variations of augmented recipes)

    Fills each tier before moving to the next until sample_count is reached.
    """
    materials_path = paths['materials']
    placements_path = paths['placements']

    enricher = MaterialEnricher(materials_path)
    variation_namer = VariationNamer()

    with open(materials_path, 'r') as f:
        data = json.load(f)
    materials_dict = {m['materialId']: m for m in data.get('materials', [])}

    with open(placements_path, 'r') as f:
        data = json.load(f)
    placements = data.get('placements', [])

    print(f"\nGenerating {discipline} data (quality-ordered, max {sample_count})...")
    print(f"  Base recipes: {len(placements)}")

    training_data = []

    # ==========================================================================
    # TIER 1: Original recipes (highest quality)
    # ==========================================================================
    print("  Tier 1: Original recipes...")
    tier1_data = []

    for placement in placements:
        if len(tier1_data) + len(training_data) >= sample_count:
            break

        if discipline == 'smithing':
            recipe = create_enriched_smithing_recipe(placement, enricher, variation_namer, 0)
        elif discipline == 'adornment':
            recipe = create_enriched_adornment_recipe(placement, enricher, variation_namer, 0)
        elif discipline == 'refining':
            recipe = create_enriched_refining_recipe(placement, enricher, variation_namer, 0)
        elif discipline == 'alchemy':
            recipe = create_enriched_alchemy_recipe(placement, enricher, variation_namer, 0)
        elif discipline == 'engineering':
            recipe = create_enriched_engineering_recipe(placement, enricher, variation_namer, 0)
        else:
            continue

        entry = {
            "recipe_id": recipe.get('recipeId'),
            "quality_tier": 1,
            "variation": "original",
            "recipe": recipe
        }
        tier1_data.append(entry)

    training_data.extend(tier1_data)
    print(f"    Added {len(tier1_data)} original recipes (total: {len(training_data)})")

    if len(training_data) >= sample_count:
        return training_data[:sample_count]

    # ==========================================================================
    # TIER 2: Augmented original (material substitution, exact colors)
    # ==========================================================================
    print("  Tier 2: Augmented original (material substitution)...")
    tier2_data = []

    # Use discipline-specific generator for augmentation
    if discipline == 'smithing':
        gen = SmithingVLMDataGenerator(materials_path, placements_path, num_color_variations=0)
        augmented = gen.generate(output_dir, save_images)
        # Filter out originals (already in tier 1) - keep only substituted/flipped
        for entry in augmented:
            if len(tier2_data) + len(training_data) >= sample_count:
                break
            recipe_id = entry.get('recipe_id', '')
            # Skip if it's a base original (no suffix beyond _v0)
            if '_v0' in recipe_id and not any(x in recipe_id for x in ['_flip', '_iron', '_steel', '_copper', '_mithril']):
                continue
            entry['quality_tier'] = 2
            tier2_data.append(entry)

    elif discipline == 'adornment':
        gen = AdornmentVLMDataGenerator(materials_path, placements_path, num_color_variations=0)
        augmented = gen.generate(output_dir, save_images)
        for entry in augmented:
            if len(tier2_data) + len(training_data) >= sample_count:
                break
            recipe_id = entry.get('recipe_id', '')
            if '_v0' in recipe_id and '_vert' not in recipe_id and '_hori' not in recipe_id:
                continue
            entry['quality_tier'] = 2
            tier2_data.append(entry)

    elif discipline == 'refining':
        gen = RefiningLLMDataGenerator(materials_path, placements_path)
        augmented = gen.generate()
        # Skip first occurrence of each base recipe (those are originals)
        seen_bases = set()
        for entry in augmented:
            if len(tier2_data) + len(training_data) >= sample_count:
                break
            recipe_id = entry.get('recipe_id', '')
            base_id = recipe_id.split('_v')[0] if '_v' in recipe_id else recipe_id
            if base_id not in seen_bases:
                seen_bases.add(base_id)
                continue  # Skip the original
            entry['quality_tier'] = 2
            tier2_data.append(entry)

    elif discipline == 'alchemy':
        gen = AlchemyLLMDataGenerator(materials_path, placements_path)
        augmented = gen.generate()
        seen_bases = set()
        for entry in augmented:
            if len(tier2_data) + len(training_data) >= sample_count:
                break
            recipe_id = entry.get('recipe_id', '')
            base_id = recipe_id.split('_v')[0] if '_v' in recipe_id else recipe_id
            if base_id not in seen_bases:
                seen_bases.add(base_id)
                continue
            entry['quality_tier'] = 2
            tier2_data.append(entry)

    elif discipline == 'engineering':
        gen = EngineeringLLMDataGenerator(materials_path, placements_path)
        augmented = gen.generate()
        seen_bases = set()
        for entry in augmented:
            if len(tier2_data) + len(training_data) >= sample_count:
                break
            recipe_id = entry.get('recipe_id', '')
            base_id = recipe_id.split('_v')[0] if '_v' in recipe_id else recipe_id
            if base_id not in seen_bases:
                seen_bases.add(base_id)
                continue
            entry['quality_tier'] = 2
            tier2_data.append(entry)

    training_data.extend(tier2_data)
    print(f"    Added {len(tier2_data)} augmented recipes (total: {len(training_data)})")

    if len(training_data) >= sample_count:
        return training_data[:sample_count]

    # ==========================================================================
    # TIER 3: Variation original (naming/color variations of base recipes)
    # ==========================================================================
    print("  Tier 3: Variation original (naming variations of originals)...")
    tier3_data = []

    for var_idx in range(1, 4):  # 3 variations per original
        for placement in placements:
            if len(tier3_data) + len(training_data) >= sample_count:
                break

            if discipline == 'smithing':
                recipe = create_enriched_smithing_recipe(placement, enricher, variation_namer, var_idx)
            elif discipline == 'adornment':
                recipe = create_enriched_adornment_recipe(placement, enricher, variation_namer, var_idx)
            elif discipline == 'refining':
                recipe = create_enriched_refining_recipe(placement, enricher, variation_namer, var_idx)
            elif discipline == 'alchemy':
                recipe = create_enriched_alchemy_recipe(placement, enricher, variation_namer, var_idx)
            elif discipline == 'engineering':
                recipe = create_enriched_engineering_recipe(placement, enricher, variation_namer, var_idx)
            else:
                continue

            entry = {
                "recipe_id": recipe.get('recipeId'),
                "quality_tier": 3,
                "variation": f"variation_v{var_idx}",
                "recipe": recipe
            }
            tier3_data.append(entry)

        if len(tier3_data) + len(training_data) >= sample_count:
            break

    training_data.extend(tier3_data)
    print(f"    Added {len(tier3_data)} variation originals (total: {len(training_data)})")

    if len(training_data) >= sample_count:
        return training_data[:sample_count]

    # ==========================================================================
    # TIER 4: Variation augmented (naming/color variations of augmented recipes)
    # ==========================================================================
    print("  Tier 4: Variation augmented (variations of augmented)...")
    tier4_data = []

    # Generate full augmented data with color variations
    if discipline in ['smithing', 'adornment']:
        if discipline == 'smithing':
            gen = SmithingVLMDataGenerator(materials_path, placements_path, num_color_variations=3)
        else:
            gen = AdornmentVLMDataGenerator(materials_path, placements_path, num_color_variations=3)

        full_augmented = gen.generate(output_dir, save_images)

        # Filter to only include color variations (v1, v2, v3) of augmented recipes
        for entry in full_augmented:
            if len(tier4_data) + len(training_data) >= sample_count:
                break
            recipe_id = entry.get('recipe_id', '')
            # Only include if it's a variation (v1, v2, v3) AND augmented (has substitution markers)
            if any(f'_v{i}' in recipe_id for i in [1, 2, 3]):
                if any(x in recipe_id for x in ['_flip', '_vert', '_hori', '_iron', '_steel', '_copper']):
                    entry['quality_tier'] = 4
                    tier4_data.append(entry)
    else:
        # For LLM disciplines, just add more variation indices to augmented recipes
        # This requires re-generating with variation indices applied
        pass  # LLM disciplines don't have as much tier 4 data since no color variations

    training_data.extend(tier4_data)
    print(f"    Added {len(tier4_data)} variation augmented (total: {len(training_data)})")

    return training_data[:sample_count]


# ============================================================================
# MAIN EXECUTION
# ============================================================================

def get_default_paths() -> Dict[str, Dict[str, str]]:
    """Get default paths for all disciplines."""
    script_dir = Path(__file__).parent
    game_modular = script_dir.parent / "Game-1-modular"

    return {
        'smithing': {
            'materials': str(game_modular / "items.JSON" / "items-materials-1.JSON"),
            'placements': str(game_modular / "placements.JSON" / "placements-smithing-1.json"),
        },
        'adornment': {
            'materials': str(game_modular / "items.JSON" / "items-materials-1.JSON"),
            'placements': str(game_modular / "placements.JSON" / "placements-adornments-1.JSON"),
        },
        'refining': {
            'materials': str(game_modular / "items.JSON" / "items-materials-1.JSON"),
            'placements': str(game_modular / "placements.JSON" / "placements-refining-1.JSON"),
        },
        'alchemy': {
            'materials': str(game_modular / "items.JSON" / "items-materials-1.JSON"),
            'placements': str(game_modular / "placements.JSON" / "placements-alchemy-1.JSON"),
        },
        'engineering': {
            'materials': str(game_modular / "items.JSON" / "items-materials-1.JSON"),
            'placements': str(game_modular / "placements.JSON" / "placements-engineering-1.JSON"),
        },
    }


def save_training_data(data: List[Dict], output_path: str, discipline: str):
    """Save training data to JSON file."""
    output = {
        'metadata': {
            'discipline': discipline,
            'total_examples': len(data),
            'generator_version': '1.0',
        },
        'training_data': data
    }

    with open(output_path, 'w') as f:
        json.dump(output, f, indent=2)

    print(f"\nSaved {len(data)} examples to: {output_path}")


def apply_cap(data: List[Dict], cap: int, discipline: str) -> List[Dict]:
    """Apply cap to training data, sampling randomly if needed."""
    if cap <= 0 or len(data) <= cap:
        return data

    print(f"  Applying cap: {len(data)} → {cap} examples")
    return random.sample(data, cap)


def generate_synthetic_only(discipline: str, paths: Dict, output_dir: str,
                           num_synthetic: int = 3, cap: int = 1000) -> List[Dict]:
    """
    Generate synthetic variations only (no material substitution).
    Just original + naming/color variations.
    """
    training_data = []
    materials_path = paths['materials']
    placements_path = paths['placements']

    enricher = MaterialEnricher(materials_path)
    variation_namer = VariationNamer()

    with open(placements_path, 'r') as f:
        data = json.load(f)
    placements = data.get('placements', [])

    print(f"\nGenerating {discipline} synthetic variations (mode 2)...")
    print(f"  Base recipes: {len(placements)}")
    print(f"  Synthetic variations per recipe: {num_synthetic}")

    for placement in placements:
        recipe_id = placement['recipeId']

        # Generate original + synthetic variations
        for var_idx in range(num_synthetic + 1):
            # Create enriched recipe based on discipline
            if discipline == 'smithing':
                recipe = create_enriched_smithing_recipe(placement, enricher, variation_namer, var_idx)
            elif discipline == 'adornment':
                recipe = create_enriched_adornment_recipe(placement, enricher, variation_namer, var_idx)
            elif discipline == 'refining':
                recipe = create_enriched_refining_recipe(placement, enricher, variation_namer, var_idx)
            elif discipline == 'alchemy':
                recipe = create_enriched_alchemy_recipe(placement, enricher, variation_namer, var_idx)
            elif discipline == 'engineering':
                recipe = create_enriched_engineering_recipe(placement, enricher, variation_namer, var_idx)
            else:
                continue

            entry = {
                "recipe_id": recipe.get('recipeId', recipe_id),
                "variation": "original" if var_idx == 0 else f"synthetic_v{var_idx}",
                "recipe": recipe
            }

            # Add image for VLM disciplines
            if discipline in ['smithing', 'adornment'] and PIL_AVAILABLE:
                # Generate image (simplified - no augmentation)
                entry['image_base64'] = None  # Would need full generator for images

            training_data.append(entry)

    # Apply cap
    training_data = apply_cap(training_data, cap, discipline)

    print(f"  Total examples: {len(training_data)}")
    return training_data


def create_enriched_smithing_recipe(placement: Dict, enricher: MaterialEnricher,
                                    namer: VariationNamer, var_idx: int) -> Dict:
    """Create enriched smithing recipe for synthetic mode."""
    recipe_id = placement['recipeId']
    if var_idx > 0:
        recipe_id = f"{recipe_id}_v{var_idx}"

    inputs = []
    for pos_str, material_id in placement.get('placementMap', {}).items():
        var_name, var_tags = namer.get_variation_name(material_id, var_idx)
        input_item = {
            "materialId": var_name,
            "quantity": 1,
            "position": pos_str
        }
        enriched = enricher.enrich_input({"materialId": material_id}, var_tags)
        input_item['material_metadata'] = enriched.get('material_metadata', {})
        inputs.append(input_item)

    return {
        "recipeId": recipe_id,
        "stationType": "smithing",
        "stationTier": placement.get('stationTier', 1),
        "gridSize": placement.get('metadata', {}).get('gridSize', '3x3'),
        "inputs": inputs
    }


def create_enriched_adornment_recipe(placement: Dict, enricher: MaterialEnricher,
                                     namer: VariationNamer, var_idx: int) -> Dict:
    """Create enriched adornment recipe for synthetic mode."""
    recipe_id = placement['recipeId']
    if var_idx > 0:
        recipe_id = f"{recipe_id}_v{var_idx}"

    vertices = placement.get('placementMap', {}).get('vertices', {})
    inputs = []
    for coord_str, vertex_data in vertices.items():
        mat_id = vertex_data.get('materialId')
        if mat_id:
            var_name, var_tags = namer.get_variation_name(mat_id, var_idx)
            input_item = {
                "materialId": var_name,
                "quantity": 1,
                "position": coord_str
            }
            enriched = enricher.enrich_input({"materialId": mat_id}, var_tags)
            input_item['material_metadata'] = enriched.get('material_metadata', {})
            inputs.append(input_item)

    return {
        "recipeId": recipe_id,
        "stationType": "enchanting",
        "stationTier": placement.get('stationTier', 1),
        "inputs": inputs
    }


def create_enriched_refining_recipe(placement: Dict, enricher: MaterialEnricher,
                                    namer: VariationNamer, var_idx: int) -> Dict:
    """Create enriched refining recipe for synthetic mode."""
    recipe_id = placement['recipeId']
    if var_idx > 0:
        recipe_id = f"{recipe_id}_v{var_idx}"

    core_inputs = []
    for core in placement.get('coreInputs', []):
        mat_id = core.get('materialId')
        var_name, var_tags = namer.get_variation_name(mat_id, var_idx)
        input_item = {
            "materialId": var_name,
            "quantity": core.get('quantity', 1)
        }
        enriched = enricher.enrich_input({"materialId": mat_id}, var_tags)
        input_item['material_metadata'] = enriched.get('material_metadata', {})
        core_inputs.append(input_item)

    surrounding_inputs = []
    for spoke in placement.get('surroundingInputs', []):
        mat_id = spoke.get('materialId')
        var_name, var_tags = namer.get_variation_name(mat_id, var_idx)
        input_item = {
            "materialId": var_name,
            "quantity": spoke.get('quantity', 1)
        }
        enriched = enricher.enrich_input({"materialId": mat_id}, var_tags)
        input_item['material_metadata'] = enriched.get('material_metadata', {})
        surrounding_inputs.append(input_item)

    return {
        "recipeId": recipe_id,
        "stationType": "refining",
        "stationTier": placement.get('stationTier', 1),
        "outputId": placement.get('outputId', ''),
        "coreInputs": core_inputs,
        "surroundingInputs": surrounding_inputs
    }


def create_enriched_alchemy_recipe(placement: Dict, enricher: MaterialEnricher,
                                   namer: VariationNamer, var_idx: int) -> Dict:
    """Create enriched alchemy recipe for synthetic mode."""
    recipe_id = placement['recipeId']
    if var_idx > 0:
        recipe_id = f"{recipe_id}_v{var_idx}"

    ingredients = []
    for ing in placement.get('ingredients', []):
        mat_id = ing.get('materialId')
        var_name, var_tags = namer.get_variation_name(mat_id, var_idx)
        input_item = {
            "materialId": var_name,
            "quantity": ing.get('quantity', 1),
            "slot": ing.get('slot', 1)
        }
        enriched = enricher.enrich_input({"materialId": mat_id}, var_tags)
        input_item['material_metadata'] = enriched.get('material_metadata', {})
        ingredients.append(input_item)

    return {
        "recipeId": recipe_id,
        "stationType": "alchemy",
        "stationTier": placement.get('stationTier', 1),
        "outputId": placement.get('outputId', ''),
        "ingredients": ingredients
    }


def create_enriched_engineering_recipe(placement: Dict, enricher: MaterialEnricher,
                                       namer: VariationNamer, var_idx: int) -> Dict:
    """Create enriched engineering recipe for synthetic mode."""
    recipe_id = placement['recipeId']
    if var_idx > 0:
        recipe_id = f"{recipe_id}_v{var_idx}"

    slots = []
    for slot in placement.get('slots', []):
        mat_id = slot.get('materialId')
        var_name, var_tags = namer.get_variation_name(mat_id, var_idx)
        slot_item = {
            "materialId": var_name,
            "quantity": slot.get('quantity', 1),
            "type": slot.get('type', 'FRAME')
        }
        enriched = enricher.enrich_input({"materialId": mat_id}, var_tags)
        slot_item['material_metadata'] = enriched.get('material_metadata', {})
        slots.append(slot_item)

    return {
        "recipeId": recipe_id,
        "stationType": "engineering",
        "stationTier": placement.get('stationTier', 1),
        "outputId": placement.get('outputId', ''),
        "slots": slots
    }


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description='Generate VLM/LLM training data for crafting disciplines',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python crafting_training_data.py --discipline smithing --output ./training_data/
  python crafting_training_data.py --discipline all --output ./training_data/
  python crafting_training_data.py --mode 3 --cap 1000  # Augmented only with 1000 cap
  python crafting_training_data.py --mode 2  # Synthetic only (original + 3x variations)
        """
    )

    parser.add_argument('--discipline', '-d',
                        choices=['smithing', 'adornment', 'refining', 'alchemy', 'engineering', 'all'],
                        default='all',
                        help='Discipline to generate training data for')
    parser.add_argument('--output', '-o',
                        default='./training_data',
                        help='Output directory for training data')
    parser.add_argument('--mode', '-m',
                        type=int, choices=[1, 2, 3, 4],
                        default=None,
                        help='Generation mode: 1=all, 2=synthetic, 3=augmented, 4=custom')
    parser.add_argument('--cap', '-c',
                        type=int, default=1000,
                        help='Maximum examples per discipline (default 1000, 0 for no cap)')
    parser.add_argument('--color-variations', '-cv',
                        type=int, default=3,
                        help='Number of color variations for VLM disciplines')
    parser.add_argument('--save-images', '-si',
                        action='store_true',
                        help='Save images to disk (in addition to base64)')
    parser.add_argument('--seed', '-s',
                        type=int, default=42,
                        help='Random seed for reproducibility')
    parser.add_argument('--no-menu', '-n',
                        action='store_true',
                        help='Skip menu and use --mode argument directly')

    args = parser.parse_args()

    random.seed(args.seed)
    np.random.seed(args.seed)

    os.makedirs(args.output, exist_ok=True)

    paths = get_default_paths()
    disciplines = [args.discipline] if args.discipline != 'all' else list(paths.keys())

    # Determine generation mode
    if args.no_menu and args.mode:
        mode = args.mode
    elif args.mode:
        mode = args.mode
    else:
        mode = show_menu()

    # Get custom parameters if mode 4
    custom_params = {}
    if mode == GenerationMode.CUSTOM:
        custom_params = get_custom_params()
        # Override disciplines with custom selection
        disciplines = custom_params.get('disciplines', disciplines)
        cap = 0  # Custom mode uses per-discipline sample counts
        color_variations = args.color_variations
    else:
        cap = args.cap
        color_variations = args.color_variations

    # Show estimates (skip for custom mode - it has its own sample counts)
    if mode != GenerationMode.CUSTOM:
        estimates = estimate_counts(paths, mode, color_variations)
        display_estimates(estimates, mode)

        # Confirm before generating
        print(f"\nCap per discipline: {cap if cap > 0 else 'None'}")
        try:
            confirm = input("\nProceed with generation? (y/n): ").strip().lower()
            if confirm != 'y':
                print("Generation cancelled.")
                return
        except EOFError:
            pass  # Non-interactive, proceed
    else:
        # Custom mode shows its own summary
        print("\n" + "-" * 70)
        print("CUSTOM MODE SUMMARY")
        print("-" * 70)
        for disc in disciplines:
            count = custom_params.get('sample_counts', {}).get(disc, 500)
            print(f"  {disc}: {count} samples (quality-ordered)")
        print()
        try:
            confirm = input("Proceed with generation? (y/n): ").strip().lower()
            if confirm != 'y':
                print("Generation cancelled.")
                return
        except EOFError:
            pass

    print("\n" + "=" * 70)
    print("CRAFTING TRAINING DATA GENERATOR")
    print("=" * 70)
    print(f"Mode: {mode} ({GenerationMode.get_mode_description(mode)})")
    print(f"Disciplines: {', '.join(disciplines)}")
    print(f"Output: {args.output}")
    if mode != GenerationMode.CUSTOM:
        print(f"Cap: {cap if cap > 0 else 'None'}")
    if mode in [GenerationMode.ALL, GenerationMode.SYNTHETIC_ONLY]:
        print(f"Color variations: {color_variations}")
    print()

    for discipline in disciplines:
        print(f"\n{'='*70}")
        print(f"Processing: {discipline.upper()} (Mode {mode})")
        print(f"{'='*70}")

        try:
            data = []

            # MODE 2: Synthetic Only (original + 3x synthetic variations)
            if mode == GenerationMode.SYNTHETIC_ONLY:
                data = generate_synthetic_only(
                    discipline,
                    paths[discipline],
                    args.output,
                    num_synthetic=3,
                    cap=cap
                )
                output_file = f'{discipline}_synthetic_data.json'

            # MODE 3: Augmented Only (material substitution, no color variations)
            elif mode == GenerationMode.AUGMENTED_ONLY:
                if discipline == 'smithing':
                    gen = SmithingVLMDataGenerator(
                        paths[discipline]['materials'],
                        paths[discipline]['placements'],
                        num_color_variations=0  # No color variations
                    )
                    data = gen.generate(args.output, args.save_images)
                elif discipline == 'adornment':
                    gen = AdornmentVLMDataGenerator(
                        paths[discipline]['materials'],
                        paths[discipline]['placements'],
                        num_color_variations=0
                    )
                    data = gen.generate(args.output, args.save_images)
                elif discipline == 'refining':
                    gen = RefiningLLMDataGenerator(
                        paths[discipline]['materials'],
                        paths[discipline]['placements']
                    )
                    data = gen.generate()
                elif discipline == 'alchemy':
                    gen = AlchemyLLMDataGenerator(
                        paths[discipline]['materials'],
                        paths[discipline]['placements']
                    )
                    data = gen.generate()
                elif discipline == 'engineering':
                    gen = EngineeringLLMDataGenerator(
                        paths[discipline]['materials'],
                        paths[discipline]['placements']
                    )
                    data = gen.generate()

                # Apply cap
                data = apply_cap(data, cap, discipline)
                output_file = f'{discipline}_augmented_data.json'

            # MODE 1: All Data (augmented + synthetic)
            elif mode == GenerationMode.ALL:
                if discipline == 'smithing':
                    gen = SmithingVLMDataGenerator(
                        paths[discipline]['materials'],
                        paths[discipline]['placements'],
                        color_variations
                    )
                    data = gen.generate(args.output, args.save_images)
                elif discipline == 'adornment':
                    gen = AdornmentVLMDataGenerator(
                        paths[discipline]['materials'],
                        paths[discipline]['placements'],
                        color_variations
                    )
                    data = gen.generate(args.output, args.save_images)
                elif discipline == 'refining':
                    gen = RefiningLLMDataGenerator(
                        paths[discipline]['materials'],
                        paths[discipline]['placements']
                    )
                    data = gen.generate()
                elif discipline == 'alchemy':
                    gen = AlchemyLLMDataGenerator(
                        paths[discipline]['materials'],
                        paths[discipline]['placements']
                    )
                    data = gen.generate()
                elif discipline == 'engineering':
                    gen = EngineeringLLMDataGenerator(
                        paths[discipline]['materials'],
                        paths[discipline]['placements']
                    )
                    data = gen.generate()

                # Apply cap
                data = apply_cap(data, cap, discipline)
                output_file = f'{discipline}_all_data.json'

            # MODE 4: Custom (quality-ordered generation)
            elif mode == GenerationMode.CUSTOM:
                sample_count = custom_params.get('sample_counts', {}).get(discipline, 500)

                data = generate_quality_ordered(
                    discipline,
                    paths[discipline],
                    sample_count,
                    args.output,
                    args.save_images
                )
                output_file = f'{discipline}_custom_data.json'

            # Save output
            if data:
                save_training_data(data, os.path.join(args.output, output_file), discipline)

        except FileNotFoundError as e:
            print(f"  ERROR: {e}")
            print(f"  Skipping {discipline}")
            continue
        except Exception as e:
            print(f"  ERROR processing {discipline}: {e}")
            import traceback
            traceback.print_exc()
            continue

    print("\n" + "=" * 70)
    print("GENERATION COMPLETE")
    print("=" * 70)
    print(f"\nOutput files saved to: {args.output}/")
    print("\nTo use different modes:")
    print("  Mode 1 (all): python crafting_training_data.py --mode 1")
    print("  Mode 2 (synthetic): python crafting_training_data.py --mode 2")
    print("  Mode 3 (augmented): python crafting_training_data.py --mode 3")
    print("  Mode 4 (custom): python crafting_training_data.py --mode 4")


if __name__ == "__main__":
    main()

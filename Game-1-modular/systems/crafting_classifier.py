"""
Crafting Recipe Classifier Integration

Validates player-invented recipes using CNN and LightGBM models.
Designed for modularity - easy to swap models, prompts, and transformers.

Created: 2026-01-25
"""

import numpy as np
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Any, Protocol, Callable
from dataclasses import dataclass, field
from abc import ABC, abstractmethod
from colorsys import hsv_to_rgb
import json
import os

# ==============================================================================
# DEBUG MODE - Set CLASSIFIER_DEBUG=1 environment variable to enable
# ==============================================================================
CLASSIFIER_DEBUG = os.environ.get('CLASSIFIER_DEBUG', '0') == '1'

def _debug(msg: str):
    """Print debug message if debug mode is enabled"""
    if CLASSIFIER_DEBUG:
        print(f"[CLASSIFIER DEBUG] {msg}")


# ==============================================================================
# RESULT TYPES
# ==============================================================================

@dataclass
class ClassifierResult:
    """Result from a classifier prediction"""
    valid: bool
    confidence: float
    probability: float
    discipline: str
    error: Optional[str] = None

    @property
    def is_error(self) -> bool:
        return self.error is not None


@dataclass
class ClassifierConfig:
    """Configuration for a single classifier"""
    discipline: str
    classifier_type: str  # 'cnn' or 'lightgbm'
    model_path: str
    extractor_path: Optional[str] = None  # For LightGBM
    img_size: int = 36  # For CNN
    threshold: float = 0.5
    enabled: bool = True


# ==============================================================================
# MATERIAL COLOR ENCODER (Shared between CNN classifiers)
# ==============================================================================

class MaterialColorEncoder:
    """
    Encodes materials as RGB colors using HSV color space.

    This is the exact encoding used during CNN model training.
    DO NOT MODIFY without retraining models.
    """

    # Category to Hue mapping (degrees, 0-360)
    CATEGORY_HUES = {
        'metal': 210,
        'wood': 30,
        'stone': 0,
        'monster_drop': 300,
        'gem': 280,
        'herb': 120,
        'fabric': 45,
    }

    # Elemental tag to Hue mapping
    ELEMENT_HUES = {
        'fire': 0, 'water': 210, 'earth': 120, 'air': 60,
        'lightning': 270, 'ice': 180, 'light': 45,
        'dark': 280, 'void': 290, 'chaos': 330,
    }

    # Tier to Value (brightness) mapping
    TIER_VALUES = {1: 0.50, 2: 0.65, 3: 0.80, 4: 0.95}

    def __init__(self, materials_db, raw_materials_dict: Optional[Dict] = None):
        """
        Args:
            materials_db: MaterialDatabase instance or dict of {material_id: material_data}
            raw_materials_dict: Optional pre-loaded dict from raw JSON for tag access
        """
        self.materials_db = materials_db
        self.raw_materials = raw_materials_dict or {}

    @classmethod
    def from_json_file(cls, json_path: Path, materials_db=None):
        """
        Create encoder by loading raw materials JSON file directly.
        This ensures tags are available for color encoding.
        """
        try:
            with open(json_path, 'r') as f:
                data = json.load(f)
            raw_dict = {
                mat['materialId']: mat
                for mat in data.get('materials', [])
            }
            return cls(materials_db, raw_dict)
        except Exception as e:
            print(f"Warning: Could not load materials JSON: {e}")
            return cls(materials_db, {})

    def get_material_data(self, material_id: str) -> Optional[Dict]:
        """Get material data from database, preferring raw JSON for tag access"""
        if material_id is None:
            return None

        # First try raw materials dict (has full metadata.tags)
        if material_id in self.raw_materials:
            return self.raw_materials[material_id]

        # Fallback to MaterialDatabase
        if hasattr(self.materials_db, 'get_material'):
            mat = self.materials_db.get_material(material_id)
            if mat:
                # Try to get tags from various sources
                tags = []
                if hasattr(mat, 'properties') and isinstance(mat.properties, dict):
                    tags = mat.properties.get('tags', [])
                if hasattr(mat, 'effect_tags'):
                    tags = tags or mat.effect_tags
                return {
                    'category': mat.category,
                    'tier': mat.tier,
                    'rarity': getattr(mat, 'rarity', 'common'),
                    'metadata': {'tags': tags}
                }
            return None
        elif hasattr(self.materials_db, 'materials'):
            mat = self.materials_db.materials.get(material_id)
            if mat:
                tags = []
                if hasattr(mat, 'properties') and isinstance(mat.properties, dict):
                    tags = mat.properties.get('tags', [])
                if hasattr(mat, 'effect_tags'):
                    tags = tags or mat.effect_tags
                return {
                    'category': getattr(mat, 'category', 'unknown'),
                    'tier': getattr(mat, 'tier', 1),
                    'rarity': getattr(mat, 'rarity', 'common'),
                    'metadata': {'tags': tags}
                }
            return None
        elif isinstance(self.materials_db, dict):
            return self.materials_db.get(material_id)
        return None

    def encode(self, material_id: Optional[str]) -> np.ndarray:
        """
        Convert material ID to RGB color array.

        Args:
            material_id: Material ID string, or None for empty cell

        Returns:
            np.ndarray of shape (3,) with RGB values in [0, 1]
        """
        if material_id is None:
            return np.array([0.0, 0.0, 0.0])

        mat_data = self.get_material_data(material_id)
        if mat_data is None:
            # Unknown material - return gray
            return np.array([0.3, 0.3, 0.3])

        category = mat_data.get('category', 'unknown')
        tier = mat_data.get('tier', 1)
        tags = mat_data.get('metadata', {}).get('tags', [])

        # CATEGORY -> HUE
        if category == 'elemental':
            hue = 280  # Default for elemental
            for tag in tags:
                if tag in self.ELEMENT_HUES:
                    hue = self.ELEMENT_HUES[tag]
                    break
        else:
            hue = self.CATEGORY_HUES.get(category, 0)

        # TIER -> VALUE (brightness)
        value = self.TIER_VALUES.get(tier, 0.5)

        # TAGS -> SATURATION
        base_saturation = 0.6
        if category == 'stone':
            base_saturation = 0.2
        if 'legendary' in tags or 'mythical' in tags:
            base_saturation = min(1.0, base_saturation + 0.2)
        elif 'magical' in tags or 'ancient' in tags:
            base_saturation = min(1.0, base_saturation + 0.1)

        # Convert HSV to RGB
        hue_normalized = hue / 360.0
        rgb = hsv_to_rgb(hue_normalized, base_saturation, value)

        return np.array(rgb)


# ==============================================================================
# IMAGE RENDERERS (Transform UI state to CNN input)
# ==============================================================================

class SmithingImageRenderer:
    """
    Renders smithing grid to 36x36 RGB image for CNN.

    Grid: 9x9 cells, each cell = 4x4 pixels = 36x36 total
    """

    IMG_SIZE = 36
    CELL_SIZE = 4
    GRID_SIZE = 9

    def __init__(self, color_encoder: MaterialColorEncoder):
        self.color_encoder = color_encoder

    def render(self, interactive_ui) -> np.ndarray:
        """
        Transform InteractiveSmithingUI state to CNN input image.

        Args:
            interactive_ui: InteractiveSmithingUI instance

        Returns:
            np.ndarray of shape (36, 36, 3) with values in [0, 1]
        """
        # Create 9x9 grid from UI grid
        grid = [[None] * self.GRID_SIZE for _ in range(self.GRID_SIZE)]

        # Calculate offset to center the station grid in 9x9
        station_grid_size = interactive_ui.grid_size
        offset = (self.GRID_SIZE - station_grid_size) // 2

        # Transfer materials from UI grid to 9x9 grid
        for (x, y), placed_mat in interactive_ui.grid.items():
            grid_x = offset + x
            grid_y = offset + y
            if 0 <= grid_x < self.GRID_SIZE and 0 <= grid_y < self.GRID_SIZE:
                grid[grid_y][grid_x] = placed_mat.item_id

        # Render to image
        return self._grid_to_image(grid)

    def _grid_to_image(self, grid: List[List[Optional[str]]]) -> np.ndarray:
        """Convert 9x9 material grid to 36x36 RGB image"""
        img = np.zeros((self.IMG_SIZE, self.IMG_SIZE, 3), dtype=np.float32)

        for i in range(self.GRID_SIZE):
            for j in range(self.GRID_SIZE):
                color = self.color_encoder.encode(grid[i][j])
                y_start = i * self.CELL_SIZE
                y_end = (i + 1) * self.CELL_SIZE
                x_start = j * self.CELL_SIZE
                x_end = (j + 1) * self.CELL_SIZE
                img[y_start:y_end, x_start:x_end] = color

        return img


class AdornmentImageRenderer:
    """
    Renders adornment vertices and shapes to 56x56 RGB image for CNN.

    Coordinate space: [-7, 7] x [-7, 7]
    Pixel mapping: (x,y) -> (int((x+7)*4), int((7-y)*4))
    """

    IMG_SIZE = 56
    COORD_RANGE = 7

    def __init__(self, color_encoder: MaterialColorEncoder):
        self.color_encoder = color_encoder

    def render(self, interactive_ui) -> np.ndarray:
        """
        Transform InteractiveAdornmentsUI state to CNN input image.

        Args:
            interactive_ui: InteractiveAdornmentsUI instance

        Returns:
            np.ndarray of shape (56, 56, 3) with values in [0, 1]
        """
        img = np.zeros((self.IMG_SIZE, self.IMG_SIZE, 3), dtype=np.float32)

        # Build vertices dict in expected format
        vertices = {}
        for coord_key, placed_mat in interactive_ui.vertices.items():
            vertices[coord_key] = {'materialId': placed_mat.item_id}

        # Build shapes list
        shapes = []
        for shape_data in interactive_ui.shapes:
            shapes.append({
                'type': shape_data['type'],
                'vertices': shape_data['vertices']
            })

        # Draw edges (lines between shape vertices)
        for shape in shapes:
            shape_vertices = shape['vertices']
            n = len(shape_vertices)

            for i in range(n):
                v1_str = shape_vertices[i]
                v2_str = shape_vertices[(i + 1) % n]

                x1, y1 = map(int, v1_str.split(','))
                x2, y2 = map(int, v2_str.split(','))
                px1, py1 = self._coord_to_pixel(x1, y1)
                px2, py2 = self._coord_to_pixel(x2, y2)

                mat1 = vertices.get(v1_str, {}).get('materialId')
                mat2 = vertices.get(v2_str, {}).get('materialId')

                # Determine line color from endpoint materials
                if mat1 and mat2:
                    color = (self.color_encoder.encode(mat1) +
                            self.color_encoder.encode(mat2)) / 2
                elif mat1:
                    color = self.color_encoder.encode(mat1)
                elif mat2:
                    color = self.color_encoder.encode(mat2)
                else:
                    color = np.array([0.3, 0.3, 0.3])

                self._draw_line(img, px1, py1, px2, py2, color, thickness=2)

        # Draw vertices (filled circles)
        for coord_str, vertex_data in vertices.items():
            x, y = map(int, coord_str.split(','))
            px, py = self._coord_to_pixel(x, y)
            material_id = vertex_data.get('materialId')
            color = self.color_encoder.encode(material_id)
            self._draw_circle(img, px, py, radius=3, color=color)

        return img

    def _coord_to_pixel(self, x: int, y: int) -> Tuple[int, int]:
        """Convert Cartesian coordinates to pixel coordinates"""
        px = int((x + self.COORD_RANGE) * 4)
        py = int((self.COORD_RANGE - y) * 4)
        return px, py

    def _draw_line(self, img: np.ndarray, x0: int, y0: int, x1: int, y1: int,
                   color: np.ndarray, thickness: int = 1):
        """Draw line using Bresenham's algorithm with blending"""
        dx = abs(x1 - x0)
        dy = abs(y1 - y0)
        sx = 1 if x0 < x1 else -1
        sy = 1 if y0 < y1 else -1
        err = dx - dy

        while True:
            for ty in range(-thickness // 2, thickness // 2 + 1):
                for tx in range(-thickness // 2, thickness // 2 + 1):
                    px, py = x0 + tx, y0 + ty
                    if 0 <= px < img.shape[1] and 0 <= py < img.shape[0]:
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

    def _draw_circle(self, img: np.ndarray, cx: int, cy: int,
                     radius: int, color: np.ndarray):
        """Draw filled circle"""
        for y in range(max(0, cy - radius), min(img.shape[0], cy + radius + 1)):
            for x in range(max(0, cx - radius), min(img.shape[1], cx + radius + 1)):
                if (x - cx) ** 2 + (y - cy) ** 2 <= radius ** 2:
                    img[y, x] = color


# ==============================================================================
# FEATURE EXTRACTORS (Transform UI state to LightGBM input)
# ==============================================================================

class LightGBMFeatureExtractor:
    """
    Extracts features from recipes for LightGBM models.

    CRITICAL: Feature extraction MUST match training script EXACTLY.
    DO NOT modify vocabularies without retraining models.

    Vocabularies are HARDCODED to match training data:
    - Categories: {'elemental': 0, 'metal': 1, 'monster_drop': 2, 'stone': 3, 'wood': 4}
    - Refining: NO refinement features
    - Alchemy/Engineering: {'basic': 0}
    """

    # EXACT category vocabulary from training (alphabetical order)
    CATEGORY_TO_IDX = {
        'elemental': 0,
        'metal': 1,
        'monster_drop': 2,
        'stone': 3,
        'wood': 4
    }
    NUM_CATEGORIES = 5

    # Refinement vocabularies by discipline
    # All three LightGBM disciplines have only 'basic' (from training data)
    REFINEMENT_VOCAB = {
        'refining': {'basic': 0},     # 1 refinement feature
        'alchemy': {'basic': 0},      # 1 refinement feature
        'engineering': {'basic': 0}   # 1 refinement feature
    }

    def __init__(self, materials_db):
        """
        Args:
            materials_db: MaterialDatabase instance or dict
        """
        self.materials_db = materials_db

    def _get_material(self, material_id: str) -> Dict:
        """Get material data as dict"""
        if hasattr(self.materials_db, 'get_material'):
            mat = self.materials_db.get_material(material_id)
            if mat:
                return {
                    'category': mat.category,
                    'tier': mat.tier,
                    'metadata': {'tags': getattr(mat, 'properties', {}).get('tags', [])}
                }
        elif hasattr(self.materials_db, 'materials'):
            mat = self.materials_db.materials.get(material_id)
            if mat:
                return {
                    'category': getattr(mat, 'category', 'unknown'),
                    'tier': getattr(mat, 'tier', 1),
                    'metadata': {'tags': getattr(mat, 'properties', {}).get('tags', [])}
                }
        return {'category': 'unknown', 'tier': 1, 'metadata': {'tags': []}}

    def _get_category_idx(self, category: str) -> int:
        """Get category index, defaulting to 0 for unknown categories"""
        return self.CATEGORY_TO_IDX.get(category, 0)

    def _get_refinement_level(self, material: Dict) -> str:
        """Get refinement level from material"""
        tags = material.get('metadata', {}).get('tags', [])
        for tag in tags:
            if tag in ['basic', 'refined', 'raw', 'processed']:
                return tag
        return 'basic'

    def extract_refining_features(self, interactive_ui) -> np.ndarray:
        """
        Extract features from InteractiveRefiningUI.

        Feature count: 19 features (MUST match training script exactly!)
        - 2: num_cores, num_spokes
        - 2: core_qty, spoke_qty
        - 2: spokes/cores ratio, spoke_qty/core_qty ratio
        - 1: material diversity
        - 5: category distribution (5 categories)
        - 1: refinement distribution (1 refinement: 'basic')
        - 5: tier statistics (core_mean, core_max, spoke_mean, spoke_max, tier_mismatch)
        - 1: station tier
        """
        features = []
        from collections import Counter

        # Build recipe dict from UI
        core_inputs = []
        for placed_mat in interactive_ui.core_slots:
            if placed_mat:
                core_inputs.append({
                    'materialId': placed_mat.item_id,
                    'quantity': placed_mat.quantity
                })

        surrounding_inputs = []
        for placed_mat in interactive_ui.surrounding_slots:
            if placed_mat:
                surrounding_inputs.append({
                    'materialId': placed_mat.item_id,
                    'quantity': placed_mat.quantity
                })

        # Basic counts (2 features)
        num_cores = len(core_inputs)
        num_spokes = len(surrounding_inputs)
        features.extend([num_cores, num_spokes])

        # Total quantities (2 features)
        core_qty = sum(c.get('quantity', 0) for c in core_inputs)
        spoke_qty = sum(s.get('quantity', 0) for s in surrounding_inputs)
        features.extend([core_qty, spoke_qty])

        # Ratio features (2 features)
        features.append(num_spokes / max(1, num_cores))
        features.append(spoke_qty / max(1, core_qty))

        # Material diversity (1 feature)
        all_mats = [c['materialId'] for c in core_inputs]
        all_mats.extend([s['materialId'] for s in surrounding_inputs])
        features.append(len(set(all_mats)))

        # Category distribution - HARDCODED 5 categories (5 features)
        core_categories = [self._get_material(c['materialId']).get('category', 'unknown')
                          for c in core_inputs]
        cat_counts = Counter(core_categories)
        # Iterate in EXACT order: elemental, metal, monster_drop, stone, wood
        for cat_name in ['elemental', 'metal', 'monster_drop', 'stone', 'wood']:
            features.append(cat_counts.get(cat_name, 0))

        # Refinement distribution - HARDCODED 1 refinement: 'basic' (1 feature)
        # NOTE: This was MISSING before - training DOES include this for refining!
        core_refinements = [self._get_refinement_level(self._get_material(c['materialId']))
                           for c in core_inputs]
        ref_counts = Counter(core_refinements)
        features.append(ref_counts.get('basic', 0))

        # Tier statistics (5 features)
        core_tiers = [self._get_material(c['materialId']).get('tier', 1)
                     for c in core_inputs]
        spoke_tiers = [self._get_material(s['materialId']).get('tier', 1)
                      for s in surrounding_inputs]

        features.append(np.mean(core_tiers) if core_tiers else 0)
        features.append(np.max(core_tiers) if core_tiers else 0)
        features.append(np.mean(spoke_tiers) if spoke_tiers else 0)
        features.append(np.max(spoke_tiers) if spoke_tiers else 0)

        # Tier mismatch
        if core_tiers and spoke_tiers:
            features.append(abs(np.mean(core_tiers) - np.mean(spoke_tiers)))
        else:
            features.append(0)

        # Station tier (1 feature)
        features.append(interactive_ui.station_tier)

        return np.array(features, dtype=np.float32)

    def extract_alchemy_features(self, interactive_ui) -> np.ndarray:
        """
        Extract features from InteractiveAlchemyUI.

        Feature count: 34 features
        - 3: num_ingredients, total_qty, avg_qty
        - 18: position features (6 positions × 3 features: tier, qty, cat_idx)
        - 1: material diversity
        - 5: category distribution (5 categories)
        - 1: refinement distribution (only 'basic')
        - 3: tier statistics (mean, max, std)
        - 2: sequential patterns (tier_increases, tier_decreases)
        - 1: station tier
        """
        features = []
        from collections import Counter

        # Build ingredients list from UI
        ingredients = []
        for slot_idx, placed_mat in enumerate(interactive_ui.slots):
            if placed_mat:
                ingredients.append({
                    'slot': slot_idx + 1,
                    'materialId': placed_mat.item_id,
                    'quantity': placed_mat.quantity
                })

        # Basic counts (3 features)
        num_ingredients = len(ingredients)
        features.append(num_ingredients)

        total_qty = sum(ing.get('quantity', 0) for ing in ingredients)
        features.append(total_qty)

        features.append(total_qty / max(1, num_ingredients))

        # Position-based features - 6 positions × 3 features = 18 features
        for pos in range(6):
            if pos < len(ingredients):
                ing = ingredients[pos]
                mat = self._get_material(ing['materialId'])
                features.append(mat.get('tier', 1))
                features.append(ing.get('quantity', 0))
                cat = mat.get('category', 'unknown')
                cat_idx = self._get_category_idx(cat)
                features.append(cat_idx)
            else:
                features.extend([0, 0, 0])

        # Material diversity (1 feature)
        unique_materials = len(set(ing['materialId'] for ing in ingredients))
        features.append(unique_materials)

        # Category distribution - HARDCODED 5 categories (5 features)
        categories = [self._get_material(ing['materialId']).get('category', 'unknown')
                     for ing in ingredients]
        cat_counts = Counter(categories)
        # Iterate in EXACT order: elemental, metal, monster_drop, stone, wood
        for cat_name in ['elemental', 'metal', 'monster_drop', 'stone', 'wood']:
            features.append(cat_counts.get(cat_name, 0))

        # Refinement distribution - HARDCODED 1 refinement: 'basic' (1 feature)
        refinements = [self._get_refinement_level(self._get_material(ing['materialId']))
                      for ing in ingredients]
        ref_counts = Counter(refinements)
        features.append(ref_counts.get('basic', 0))

        # Tier statistics (3 features)
        tiers = [self._get_material(ing['materialId']).get('tier', 1)
                for ing in ingredients]
        features.append(np.mean(tiers) if tiers else 0)
        features.append(np.max(tiers) if tiers else 0)
        features.append(np.std(tiers) if len(tiers) > 1 else 0)

        # Sequential patterns (2 features)
        if len(tiers) >= 2:
            tier_increases = sum(1 for i in range(len(tiers) - 1) if tiers[i + 1] > tiers[i])
            tier_decreases = sum(1 for i in range(len(tiers) - 1) if tiers[i + 1] < tiers[i])
            features.extend([tier_increases, tier_decreases])
        else:
            features.extend([0, 0])

        # Station tier (1 feature)
        features.append(interactive_ui.station_tier)

        return np.array(features, dtype=np.float32)

    def extract_engineering_features(self, interactive_ui) -> np.ndarray:
        """
        Extract features from InteractiveEngineeringUI.

        Feature count: 28 features
        - 2: num_slots, total_qty
        - 8: slot type distribution (8 types)
        - 4: unique_slot_types, frame_present, function_present, power_present
        - 1: material diversity
        - 5: category distribution (5 categories)
        - 1: refinement distribution (only 'basic')
        - 3: tier statistics (mean, max, std)
        - 3: quantity by slot type (frame, power, function)
        - 1: station tier
        """
        features = []
        from collections import Counter

        # Build slots list from UI
        slots = []
        for slot_type, materials in interactive_ui.slots.items():
            for placed_mat in materials:
                slots.append({
                    'type': slot_type,
                    'materialId': placed_mat.item_id,
                    'quantity': placed_mat.quantity
                })

        # Basic counts (2 features)
        num_slots = len(slots)
        features.append(num_slots)

        total_qty = sum(slot.get('quantity', 0) for slot in slots)
        features.append(total_qty)

        # Slot type distribution - 8 features
        slot_types = [slot.get('type', 'unknown') for slot in slots]
        slot_type_counts = Counter(slot_types)

        for slot_type in ['FRAME', 'FUNCTION', 'POWER', 'MODIFIER', 'UTILITY',
                          'ENHANCEMENT', 'CORE', 'CATALYST']:
            features.append(slot_type_counts.get(slot_type, 0))

        # Unique slot types (1 feature)
        features.append(len(set(slot_types)))

        # Critical slots present - binary (3 features)
        features.append(1 if 'FRAME' in slot_types else 0)
        features.append(1 if 'FUNCTION' in slot_types else 0)
        features.append(1 if 'POWER' in slot_types else 0)

        # Material diversity (1 feature)
        unique_materials = len(set(slot['materialId'] for slot in slots)) if slots else 0
        features.append(unique_materials)

        # Category distribution - HARDCODED 5 categories (5 features)
        categories = [self._get_material(slot['materialId']).get('category', 'unknown')
                     for slot in slots]
        cat_counts = Counter(categories)
        # Iterate in EXACT order: elemental, metal, monster_drop, stone, wood
        for cat_name in ['elemental', 'metal', 'monster_drop', 'stone', 'wood']:
            features.append(cat_counts.get(cat_name, 0))

        # Refinement distribution - HARDCODED 1 refinement: 'basic' (1 feature)
        refinements = [self._get_refinement_level(self._get_material(slot['materialId']))
                      for slot in slots]
        ref_counts = Counter(refinements)
        features.append(ref_counts.get('basic', 0))

        # Tier statistics (3 features)
        tiers = [self._get_material(slot['materialId']).get('tier', 1)
                for slot in slots]
        features.append(np.mean(tiers) if tiers else 0)
        features.append(np.max(tiers) if tiers else 0)
        features.append(np.std(tiers) if len(tiers) > 1 else 0)

        # Quantity by slot type (3 features)
        frame_qty = sum(s.get('quantity', 0) for s in slots if s.get('type') == 'FRAME')
        power_qty = sum(s.get('quantity', 0) for s in slots if s.get('type') == 'POWER')
        function_qty = sum(s.get('quantity', 0) for s in slots if s.get('type') == 'FUNCTION')
        features.extend([frame_qty, power_qty, function_qty])

        # Station tier (1 feature)
        features.append(interactive_ui.station_tier)

        return np.array(features, dtype=np.float32)


# ==============================================================================
# CLASSIFIER BACKENDS (Abstract interface for different model types)
# ==============================================================================

class ClassifierBackend(ABC):
    """Abstract base class for classifier backends"""

    @abstractmethod
    def predict(self, input_data: Any) -> Tuple[float, Optional[str]]:
        """
        Make a prediction.

        Args:
            input_data: Model-specific input (image array for CNN, feature array for LightGBM)

        Returns:
            Tuple of (probability, error_message or None)
        """
        pass

    @abstractmethod
    def is_loaded(self) -> bool:
        """Check if model is loaded and ready"""
        pass


def _get_classifier_loading_state():
    """Get the loading state from llm_item_generator (shared system)"""
    try:
        from systems.llm_item_generator import get_loading_state
        return get_loading_state()
    except ImportError:
        return None


class CNNBackend(ClassifierBackend):
    """TensorFlow/Keras CNN backend"""

    def __init__(self, model_path: Path):
        self.model_path = model_path
        self.model = None
        self._tf = None
        self._load_error = None

    def _lazy_load(self):
        """Lazy load TensorFlow and model on first use"""
        if self.model is not None or self._load_error is not None:
            return

        # Note: Loading state is managed by CraftingClassifierManager.preload(),
        # NOT here, to avoid nested start/finish calls that break the indicator.
        try:
            import tensorflow as tf
            self._tf = tf

            # Suppress TF logging
            import os
            os.environ['TF_CPP_MIN_LOG_LEVEL'] = '2'

            self.model = tf.keras.models.load_model(str(self.model_path))

        except ImportError as e:
            self._load_error = f"TensorFlow not installed: {e}"
        except Exception as e:
            self._load_error = f"Failed to load CNN model: {e}"

    def predict(self, input_data: np.ndarray) -> Tuple[float, Optional[str]]:
        self._lazy_load()

        if self._load_error:
            return 0.0, self._load_error

        try:
            # Add batch dimension if needed
            if len(input_data.shape) == 3:
                input_data = np.expand_dims(input_data, axis=0)

            prob = float(self.model.predict(input_data, verbose=0)[0][0])
            return prob, None

        except Exception as e:
            return 0.0, f"CNN prediction failed: {e}"

    def is_loaded(self) -> bool:
        self._lazy_load()
        return self.model is not None


class LightGBMBackend(ClassifierBackend):
    """LightGBM backend - uses only the model file, not pickled extractors"""

    def __init__(self, model_path: Path):
        self.model_path = model_path
        self.model = None
        self._load_error = None
        self._loading = False

    def _lazy_load(self):
        """Lazy load LightGBM and model on first use"""
        if self.model is not None or self._load_error is not None:
            return

        # Prevent re-entrant loading
        if self._loading:
            return
        self._loading = True

        # Note: Loading state is managed by CraftingClassifierManager.preload(),
        # NOT here, to avoid nested start/finish calls that break the indicator.
        try:
            import lightgbm as lgb

            self.model = lgb.Booster(model_file=str(self.model_path))

            # NOTE: We do NOT load the pickled extractor files because they
            # contain a RecipeFeatureExtractor class that was defined in the
            # training script and doesn't exist in the game's namespace.
            # Instead, we use our own LightGBMFeatureExtractor class.

        except ImportError as e:
            self._load_error = f"LightGBM not installed: {e}"
        except Exception as e:
            self._load_error = f"Failed to load LightGBM model: {e}"
        finally:
            self._loading = False

    def predict(self, input_data: np.ndarray) -> Tuple[float, Optional[str]]:
        self._lazy_load()

        if self._load_error:
            _debug(f"LightGBM load error: {self._load_error}")
            return 0.0, self._load_error

        try:
            # Reshape if needed
            if len(input_data.shape) == 1:
                input_data = input_data.reshape(1, -1)

            _debug(f"LightGBM input shape after reshape: {input_data.shape}")
            _debug(f"LightGBM model expects {self.model.num_feature()} features")

            if input_data.shape[1] != self.model.num_feature():
                error_msg = f"Feature mismatch! Model expects {self.model.num_feature()} features, got {input_data.shape[1]}"
                _debug(f"ERROR: {error_msg}")
                return 0.0, error_msg

            prob = float(self.model.predict(input_data,
                        num_iteration=self.model.best_iteration)[0])
            _debug(f"LightGBM raw prediction: {prob}")
            return prob, None

        except Exception as e:
            _debug(f"LightGBM prediction exception: {e}")
            import traceback
            _debug(f"Traceback: {traceback.format_exc()}")
            return 0.0, f"LightGBM prediction failed: {e}"

    def is_loaded(self) -> bool:
        self._lazy_load()
        return self.model is not None


# ==============================================================================
# MAIN CLASSIFIER MANAGER
# ==============================================================================

class CraftingClassifierManager:
    """
    Main entry point for recipe validation.

    Manages all 5 discipline classifiers with:
    - Lazy loading (models loaded on first use)
    - Graceful fallbacks (returns error result if model unavailable)
    - Modular design (easy to swap models/configs)
    """

    # Default model paths (relative to project root)
    # Models are stored in Scaled JSON Development/models/{discipline}/
    DEFAULT_CONFIGS = {
        'smithing': ClassifierConfig(
            discipline='smithing',
            classifier_type='cnn',
            model_path='Scaled JSON Development/models/smithing/smithing_best.keras',
            img_size=36,
            threshold=0.5
        ),
        'adornments': ClassifierConfig(
            discipline='adornments',
            classifier_type='cnn',
            model_path='Scaled JSON Development/models/adornment/adornment_best.keras',
            img_size=56,
            threshold=0.5
        ),
        'alchemy': ClassifierConfig(
            discipline='alchemy',
            classifier_type='lightgbm',
            model_path='Scaled JSON Development/models/alchemy/alchemy_model.txt',
            extractor_path='Scaled JSON Development/models/alchemy/alchemy_extractor.pkl',
            threshold=0.5
        ),
        'refining': ClassifierConfig(
            discipline='refining',
            classifier_type='lightgbm',
            model_path='Scaled JSON Development/models/refining/refining_model.txt',
            extractor_path='Scaled JSON Development/models/refining/refining_extractor.pkl',
            threshold=0.5
        ),
        'engineering': ClassifierConfig(
            discipline='engineering',
            classifier_type='lightgbm',
            model_path='Scaled JSON Development/models/engineering/engineering_model.txt',
            extractor_path='Scaled JSON Development/models/engineering/engineering_extractor.pkl',
            threshold=0.5
        ),
    }

    def __init__(self, project_root: Path, materials_db,
                 configs: Optional[Dict[str, ClassifierConfig]] = None):
        """
        Initialize the classifier manager.

        Args:
            project_root: Path to Game-1 project root
            materials_db: MaterialDatabase instance
            configs: Optional custom configs (uses defaults if None)
        """
        self.project_root = Path(project_root)
        self.materials_db = materials_db
        self.configs = configs or self.DEFAULT_CONFIGS.copy()

        # Components (lazy initialized)
        self._color_encoder = None
        self._feature_extractor = None
        self._image_renderers = {}
        self._backends = {}

        print(f"CraftingClassifierManager initialized")
        print(f"  Project root: {self.project_root}")
        print(f"  Disciplines: {list(self.configs.keys())}")

    @property
    def color_encoder(self) -> MaterialColorEncoder:
        if self._color_encoder is None:
            # Try to load raw materials JSON for proper tag access
            materials_json_path = self.project_root / "Game-1-modular/items.JSON/items-materials-1.JSON"
            if materials_json_path.exists():
                self._color_encoder = MaterialColorEncoder.from_json_file(
                    materials_json_path, self.materials_db
                )
                print(f"  Loaded raw materials from: {materials_json_path}")
            else:
                self._color_encoder = MaterialColorEncoder(self.materials_db)
                print(f"  Warning: Using MaterialDatabase fallback (no raw JSON)")
        return self._color_encoder

    @property
    def feature_extractor(self) -> LightGBMFeatureExtractor:
        if self._feature_extractor is None:
            self._feature_extractor = LightGBMFeatureExtractor(self.materials_db)
        return self._feature_extractor

    def get_image_renderer(self, discipline: str):
        """Get or create image renderer for discipline"""
        if discipline not in self._image_renderers:
            if discipline == 'smithing':
                self._image_renderers[discipline] = SmithingImageRenderer(self.color_encoder)
            elif discipline == 'adornments':
                self._image_renderers[discipline] = AdornmentImageRenderer(self.color_encoder)
        return self._image_renderers.get(discipline)

    def get_backend(self, discipline: str) -> Optional[ClassifierBackend]:
        """Get or create classifier backend for discipline"""
        if discipline not in self._backends:
            config = self.configs.get(discipline)
            if not config:
                return None

            model_path = self.project_root / config.model_path

            if config.classifier_type == 'cnn':
                self._backends[discipline] = CNNBackend(model_path)
            elif config.classifier_type == 'lightgbm':
                # NOTE: We don't use the pickled extractor files - they contain
                # a class from the training script that doesn't exist here.
                # Instead, we use our own LightGBMFeatureExtractor.
                self._backends[discipline] = LightGBMBackend(model_path)

        return self._backends.get(discipline)

    def validate(self, discipline: str, interactive_ui) -> ClassifierResult:
        """
        Validate a recipe from interactive UI state.

        Args:
            discipline: One of 'smithing', 'adornments', 'alchemy', 'refining', 'engineering'
            interactive_ui: The InteractiveXUI instance with current placement

        Returns:
            ClassifierResult with valid/invalid, confidence, and any error
        """
        _debug(f"=== validate() called for {discipline} ===")

        config = self.configs.get(discipline)
        if not config:
            _debug(f"ERROR: No config for {discipline}")
            return ClassifierResult(
                valid=False,
                confidence=0.0,
                probability=0.0,
                discipline=discipline,
                error=f"No classifier configured for discipline: {discipline}"
            )

        _debug(f"Config: type={config.classifier_type}, model_path={config.model_path}")

        if not config.enabled:
            _debug(f"ERROR: Classifier disabled for {discipline}")
            return ClassifierResult(
                valid=False,
                confidence=0.0,
                probability=0.0,
                discipline=discipline,
                error=f"Classifier disabled for discipline: {discipline}"
            )

        # Get backend
        backend = self.get_backend(discipline)
        if not backend:
            _debug(f"ERROR: Failed to create backend for {discipline}")
            return ClassifierResult(
                valid=False,
                confidence=0.0,
                probability=0.0,
                discipline=discipline,
                error=f"Failed to create backend for discipline: {discipline}"
            )

        _debug(f"Backend loaded: {backend.is_loaded()}")

        # Transform UI to model input
        try:
            if config.classifier_type == 'cnn':
                input_data = self._transform_for_cnn(discipline, interactive_ui)
                _debug(f"CNN input shape: {input_data.shape}, dtype: {input_data.dtype}")
                _debug(f"CNN input min/max: {input_data.min():.4f}/{input_data.max():.4f}")
            else:
                input_data = self._transform_for_lightgbm(discipline, interactive_ui)
                _debug(f"LightGBM input shape: {input_data.shape}, dtype: {input_data.dtype}")
                _debug(f"LightGBM features: {input_data.tolist()}")
        except Exception as e:
            _debug(f"ERROR: Transform failed: {e}")
            import traceback
            _debug(f"Traceback: {traceback.format_exc()}")
            return ClassifierResult(
                valid=False,
                confidence=0.0,
                probability=0.0,
                discipline=discipline,
                error=f"Failed to transform input: {e}"
            )

        # Make prediction
        _debug(f"Calling backend.predict()...")
        prob, error = backend.predict(input_data)
        _debug(f"Prediction result: prob={prob}, error={error}")

        if error:
            _debug(f"ERROR: Prediction failed: {error}")
            return ClassifierResult(
                valid=False,
                confidence=0.0,
                probability=0.0,
                discipline=discipline,
                error=error
            )

        # Interpret result
        is_valid = prob >= config.threshold
        confidence = prob if is_valid else (1 - prob)

        _debug(f"Result: valid={is_valid}, prob={prob:.4f}, threshold={config.threshold}")

        return ClassifierResult(
            valid=is_valid,
            confidence=confidence,
            probability=prob,
            discipline=discipline
        )

    def _transform_for_cnn(self, discipline: str, interactive_ui) -> np.ndarray:
        """Transform UI state to CNN image input"""
        renderer = self.get_image_renderer(discipline)
        if not renderer:
            raise ValueError(f"No image renderer for discipline: {discipline}")
        return renderer.render(interactive_ui)

    def _transform_for_lightgbm(self, discipline: str, interactive_ui) -> np.ndarray:
        """Transform UI state to LightGBM feature vector"""
        if discipline == 'alchemy':
            return self.feature_extractor.extract_alchemy_features(interactive_ui)
        elif discipline == 'refining':
            return self.feature_extractor.extract_refining_features(interactive_ui)
        elif discipline == 'engineering':
            return self.feature_extractor.extract_engineering_features(interactive_ui)
        else:
            raise ValueError(f"No feature extractor for discipline: {discipline}")

    def update_config(self, discipline: str, **kwargs):
        """
        Update configuration for a discipline.

        Args:
            discipline: Discipline name
            **kwargs: Config fields to update (model_path, threshold, enabled, etc.)
        """
        if discipline not in self.configs:
            print(f"WARNING: Unknown discipline: {discipline}")
            return

        config = self.configs[discipline]
        for key, value in kwargs.items():
            if hasattr(config, key):
                setattr(config, key, value)
                print(f"Updated {discipline}.{key} = {value}")

        # Clear cached backend if model path changed
        if 'model_path' in kwargs and discipline in self._backends:
            del self._backends[discipline]

    def get_status(self) -> Dict[str, Dict]:
        """Get status of all classifiers"""
        status = {}
        for discipline, config in self.configs.items():
            backend = self.get_backend(discipline) if config.enabled else None
            status[discipline] = {
                'enabled': config.enabled,
                'type': config.classifier_type,
                'model_path': config.model_path,
                'loaded': backend.is_loaded() if backend else False,
                'threshold': config.threshold
            }
        return status

    def preload(self, discipline: Optional[str] = None):
        """
        Preload classifier models to avoid delay when validating recipes.

        Call this when the interactive crafting UI opens to load models
        in advance, rather than on first validation attempt.

        IMPORTANT: For CNN models (TensorFlow/Keras), this runs a warmup prediction
        to fully compile the computational graph. Without this, the first real
        prediction will still be slow even though the model file is loaded.

        Args:
            discipline: Specific discipline to preload, or None for all
        """
        disciplines = [discipline] if discipline else list(self.configs.keys())

        # Get loading state for UI feedback
        loading_state = _get_classifier_loading_state()

        enabled_disciplines = [d for d in disciplines
                              if self.configs.get(d) and self.configs[d].enabled]

        if not enabled_disciplines:
            return

        # Use try/finally to ensure loading state is ALWAYS finished
        try:
            for i, disc in enumerate(enabled_disciplines):
                config = self.configs.get(disc)

                try:
                    # Update loading state with progress
                    progress = i / len(enabled_disciplines)
                    if loading_state:
                        loading_state.start(
                            f"Loading {disc.title()} Classifier",
                            subtitle=f"{config.classifier_type.upper()} model",
                        )
                        loading_state.update(progress=progress)

                    # Initialize the backend (triggers lazy load)
                    backend = self.get_backend(disc)
                    if backend:
                        # Force load by checking if loaded
                        _ = backend.is_loaded()

                    # For CNN, also preload the image renderer (loads color encoder)
                    if config.classifier_type == 'cnn':
                        if loading_state:
                            loading_state.update(subtitle="Loading color encoder...")
                        renderer = self.get_image_renderer(disc)

                        # CRITICAL: Run warmup prediction to compile TensorFlow graph
                        # Without this, the first real prediction will still be slow
                        if loading_state:
                            loading_state.update(subtitle="Warming up model...")
                        if backend and backend.is_loaded() and renderer:
                            # Create dummy input matching the expected size
                            if disc == 'smithing':
                                dummy_input = np.zeros((36, 36, 3), dtype=np.float32)
                            elif disc == 'adornments':
                                dummy_input = np.zeros((56, 56, 3), dtype=np.float32)
                            else:
                                dummy_input = np.zeros((36, 36, 3), dtype=np.float32)

                            # Run warmup prediction (result is discarded)
                            try:
                                _ = backend.predict(dummy_input)
                                print(f"  Warmup prediction complete for {disc}")
                            except Exception as warmup_error:
                                print(f"  Warmup prediction failed for {disc}: {warmup_error}")

                    # For LightGBM, preload the feature extractor
                    if config.classifier_type == 'lightgbm':
                        if loading_state:
                            loading_state.update(subtitle="Loading feature extractor...")
                        _ = self.feature_extractor

                except Exception as e:
                    # Log error but continue with other disciplines
                    print(f"  Warning: Preload failed for {disc}: {e}")
                    pass
        finally:
            # Finish loading state (guaranteed to run)
            if loading_state:
                loading_state.finish()

    def unload(self, discipline: Optional[str] = None):
        """
        Unload classifier models to free memory.

        Call this when the interactive crafting UI closes.

        Args:
            discipline: Specific discipline to unload, or None for all
        """
        disciplines = [discipline] if discipline else list(self._backends.keys())

        for disc in list(disciplines):
            if disc in self._backends:
                del self._backends[disc]

        # Also clear image renderers if unloading all
        if discipline is None:
            self._image_renderers.clear()


# ==============================================================================
# SINGLETON INSTANCE
# ==============================================================================

_classifier_manager: Optional[CraftingClassifierManager] = None


def get_classifier_manager() -> Optional[CraftingClassifierManager]:
    """Get the global classifier manager instance"""
    return _classifier_manager


def init_classifier_manager(project_root: Path, materials_db) -> CraftingClassifierManager:
    """Initialize and return the global classifier manager"""
    global _classifier_manager
    _classifier_manager = CraftingClassifierManager(project_root, materials_db)
    return _classifier_manager

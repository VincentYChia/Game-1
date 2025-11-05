"""
Enchanting (Adornment) Crafting Subdiscipline

Framework:
- Python module ready for main.py integration
- Loads recipes from JSON files
- REQUIRED minigame (no skip option for adornments)
- Difficulty based on tier (tier + X + Y in future updates)

Minigame: Freeform pattern creation
- Phase 1: Place enhancement materials in circular workspace
- Phase 2: Draw lines between materials to create pattern
- Phase 3: System recognizes geometric pattern created
- Phase 4: System judges quality/precision of pattern

NOTE: Enchanting is unique - minigame is REQUIRED, cannot be skipped
"""

import pygame
import json
import math


class EnchantingMinigame:
    """
    Enchanting minigame implementation - Freeform pattern creation

    Process:
    1. Place materials anywhere in circular workspace
    2. Connect materials with lines to form pattern
    3. System recognizes pattern type (triangle, square, star, etc.)
    4. Quality judged by precision (angles, spacing, symmetry)
    """

    def __init__(self, recipe, tier=1, target_item=None):
        """
        Initialize enchanting minigame

        Args:
            recipe: Recipe dict from JSON (adornment recipe)
            tier: Recipe tier (1-4) - affects difficulty
            target_item: Item to enchant (optional, for accessories can be None)
        """
        self.recipe = recipe
        self.tier = tier
        self.target_item = target_item  # Item being enchanted
        self.ingredients = recipe.get('inputs', [])

        # Difficulty scaling
        self._setup_difficulty()

        # Game state
        self.active = False
        self.phase = 1  # 1=placement, 2=connection
        self.placed_materials = {}  # {index: {materialId, x, y, isKey}}
        self.connections = []  # [(index1, index2), ...]
        self.recognized_pattern = None
        self.pattern_quality = 0.0
        self.result = None

        # Workspace dimensions (circular)
        self.workspace_radius = 300
        self.workspace_center = (400, 400)

    def _setup_difficulty(self):
        """
        Setup difficulty parameters based on tier

        NOTE: Difficulty formula may be expanded in future updates
        """
        if self.tier == 1:
            self.material_count = 3  # 3-5 materials
            self.required_precision = 0.7  # 70% precision for success
            self.placement_grid_detail = 10  # Coarse grid
        elif self.tier == 2:
            self.material_count = 6  # 6-8 materials
            self.required_precision = 0.8
            self.placement_grid_detail = 20  # Finer grid
        elif self.tier == 3:
            self.material_count = 10  # 9-12 materials
            self.required_precision = 0.9
            self.placement_grid_detail = 40  # High precision
        else:  # tier 4
            self.material_count = 15  # 13-20 materials
            self.required_precision = 0.95  # Near-perfect required
            self.placement_grid_detail = 80  # Pixel-perfect

    def start(self):
        """Start the minigame"""
        self.active = True
        self.phase = 1  # Start with placement phase
        self.placed_materials = {}
        self.connections = []
        self.recognized_pattern = None
        self.pattern_quality = 0.0
        self.result = None

    def place_material(self, material_id, x, y, is_key=False):
        """
        Place material at position in workspace

        Args:
            material_id: Material ID being placed
            x, y: Position in workspace
            is_key: Whether this is a key material

        Returns:
            bool: True if placed successfully
        """
        if self.phase != 1:
            return False

        # Check if within circular workspace
        dx = x - self.workspace_center[0]
        dy = y - self.workspace_center[1]
        distance = math.sqrt(dx * dx + dy * dy)

        if distance > self.workspace_radius:
            return False

        # Add to placed materials
        index = len(self.placed_materials)
        self.placed_materials[index] = {
            "materialId": material_id,
            "x": x,
            "y": y,
            "isKey": is_key
        }

        return True

    def connect_materials(self, index1, index2):
        """
        Draw connection between two materials

        Args:
            index1, index2: Indices of materials to connect

        Returns:
            bool: True if connected successfully
        """
        if self.phase != 2:
            return False

        if index1 not in self.placed_materials or index2 not in self.placed_materials:
            return False

        # Add connection if not already exists
        connection = tuple(sorted([index1, index2]))
        if connection not in self.connections:
            self.connections.append(connection)
            return True

        return False

    def advance_phase(self):
        """
        Advance to next phase

        Returns:
            bool: True if advanced successfully
        """
        if self.phase == 1:
            # Move to connection phase
            if len(self.placed_materials) >= self.material_count:
                self.phase = 2
                return True
        elif self.phase == 2:
            # Finalize and recognize pattern
            self.recognize_pattern()
            self.judge_quality()
            self.end()
            return True

        return False

    def recognize_pattern(self):
        """
        Recognize what geometric pattern was created

        Pattern types:
        - Triangle (3 vertices)
        - Square (4 vertices)
        - Pentagon (5 vertices)
        - Star (varies)
        - Circle (smooth curve)
        - Nested patterns (complex)
        """
        if len(self.connections) == 0:
            self.recognized_pattern = "none"
            return

        # Simple pattern recognition based on connection count
        # TODO: Implement proper geometric pattern recognition

        vertex_count = len(set([i for conn in self.connections for i in conn]))

        if vertex_count == 3:
            self.recognized_pattern = "triangle"
        elif vertex_count == 4:
            self.recognized_pattern = "square"
        elif vertex_count == 5:
            self.recognized_pattern = "pentagon"
        elif vertex_count >= 6:
            self.recognized_pattern = "complex"
        else:
            self.recognized_pattern = "incomplete"

    def judge_quality(self):
        """
        Judge precision/quality of pattern

        Factors:
        - Angle accuracy (90 degrees for square, 60 for triangle, etc.)
        - Spacing uniformity
        - Symmetry
        - Connection straightness
        """
        if self.recognized_pattern in ["none", "incomplete"]:
            self.pattern_quality = 0.0
            return

        # Simple quality calculation for now
        # TODO: Implement proper geometric quality checking

        # Base quality from having a pattern
        base_quality = 0.5

        # Bonus for complexity
        complexity_bonus = len(self.connections) * 0.05

        # Random variance for now (would be based on actual geometry)
        import random
        precision = random.uniform(0.6, 1.0)

        self.pattern_quality = min(1.0, base_quality + complexity_bonus * precision)

    def end(self):
        """Complete the enchanting and calculate results"""
        self.active = False

        # Check if quality meets requirements
        if self.pattern_quality < self.required_precision:
            # Failure at high tier breaks item
            if self.tier >= 3 and self.target_item:
                self.result = {
                    "success": False,
                    "pattern": self.recognized_pattern,
                    "quality": self.pattern_quality,
                    "item_broken": True,
                    "message": f"Pattern quality {self.pattern_quality:.0%} insufficient - Item BROKEN!"
                }
            else:
                # Low-mid tier: materials consumed, item intact
                self.result = {
                    "success": False,
                    "pattern": self.recognized_pattern,
                    "quality": self.pattern_quality,
                    "item_broken": False,
                    "message": f"Pattern quality {self.pattern_quality:.0%} insufficient"
                }
        else:
            # Success!
            # Determine bonus type based on pattern
            bonus_type = self._determine_bonus_type()

            # Bonus magnitude based on quality
            bonus_magnitude = self._calculate_bonus_magnitude()

            self.result = {
                "success": True,
                "pattern": self.recognized_pattern,
                "quality": self.pattern_quality,
                "bonus_type": bonus_type,
                "bonus_magnitude": bonus_magnitude,
                "message": f"Enchantment successful! {bonus_type} +{bonus_magnitude}%"
            }

    def _determine_bonus_type(self):
        """Determine enchantment type based on pattern"""
        pattern_to_bonus = {
            "triangle": "offensive",
            "square": "defensive",
            "pentagon": "utility",
            "star": "elemental",
            "complex": "multi"
        }
        return pattern_to_bonus.get(self.recognized_pattern, "misc")

    def _calculate_bonus_magnitude(self):
        """Calculate bonus magnitude based on quality and tier"""
        base_bonus = self.tier * 5  # T1=5%, T2=10%, T3=15%, T4=20%
        quality_mult = self.pattern_quality  # 0.0-1.0

        return int(base_bonus * quality_mult)

    def get_state(self):
        """Get current minigame state for rendering"""
        return {
            "active": self.active,
            "phase": self.phase,
            "placed_materials": self.placed_materials,
            "connections": self.connections,
            "recognized_pattern": self.recognized_pattern,
            "pattern_quality": self.pattern_quality,
            "result": self.result,
            "workspace_radius": self.workspace_radius,
            "workspace_center": self.workspace_center
        }


class EnchantingCrafter:
    """
    Main enchanting crafting interface

    Handles:
    - Recipe loading from JSON
    - Material validation
    - NO instant crafting (minigame REQUIRED)
    - Minigame crafting (pattern creation)
    - Applying enchantments to items
    """

    def __init__(self):
        """Initialize enchanting crafter"""
        self.recipes = {}
        self.load_recipes()

    def load_recipes(self):
        """Load enchanting recipes from JSON files"""
        # Note: May be called "adornments" or "enchanting" in file names
        possible_paths = [
            "../recipes.JSON/recipes-enchanting-1.json",
            "../recipes.JSON/recipes-adornments-1.json",
            "recipes.JSON/recipes-enchanting-1.json",
            "recipes.JSON/recipes-adornments-1.json",
        ]

        for path in possible_paths:
            try:
                with open(path, 'r') as f:
                    data = json.load(f)
                    recipe_list = data.get('recipes', [])
                    for recipe in recipe_list:
                        self.recipes[recipe['recipeId']] = recipe
            except FileNotFoundError:
                continue

        if self.recipes:
            print(f"[Enchanting] Loaded {len(self.recipes)} recipes")
        else:
            print("[Enchanting] WARNING: No recipes loaded")

    def can_craft(self, recipe_id, inventory):
        """Check if recipe can be crafted"""
        if recipe_id not in self.recipes:
            return False

        recipe = self.recipes[recipe_id]
        for inp in recipe.get('inputs', []):
            if inventory.get(inp['materialId'], 0) < inp['quantity']:
                return False
        return True

    def craft_instant(self, recipe_id, inventory):
        """
        NO INSTANT CRAFTING FOR ENCHANTING

        Enchanting REQUIRES the minigame - cannot skip

        Returns:
            dict: Error message
        """
        return {
            "success": False,
            "message": "Enchanting requires the minigame - instant crafting not available"
        }

    def create_minigame(self, recipe_id, target_item=None):
        """
        Create an enchanting minigame for this recipe

        Args:
            recipe_id: Recipe ID to craft
            target_item: Item to enchant (can be None for accessories)

        Returns:
            EnchantingMinigame instance or None
        """
        if recipe_id not in self.recipes:
            return None

        recipe = self.recipes[recipe_id]
        tier = recipe.get('stationTier', 1)

        return EnchantingMinigame(recipe, tier, target_item)

    def craft_with_minigame(self, recipe_id, inventory, minigame_result, target_item=None):
        """
        Craft with minigame result - apply enchantment

        Args:
            recipe_id: Recipe ID to craft
            inventory: Dict of {material_id: quantity} (will be modified)
            minigame_result: Result dict from EnchantingMinigame
            target_item: Item to enchant (modified in place)

        Returns:
            dict: Result with success, enchantment details
        """
        recipe = self.recipes[recipe_id]

        # Always consume materials (even on failure)
        for inp in recipe['inputs']:
            inventory[inp['materialId']] -= inp['quantity']

        if not minigame_result.get('success'):
            # Check if item was broken
            if minigame_result.get('item_broken') and target_item:
                return {
                    "success": False,
                    "message": minigame_result.get('message'),
                    "item_broken": True,
                    "broken_item_id": target_item.get('itemId')
                }
            else:
                return {
                    "success": False,
                    "message": minigame_result.get('message'),
                    "materials_lost": True
                }

        # Success - apply enchantment
        enchantment_data = {
            "recipeId": recipe_id,
            "bonus_type": minigame_result.get('bonus_type'),
            "bonus_magnitude": minigame_result.get('bonus_magnitude'),
            "pattern": minigame_result.get('pattern'),
            "quality": minigame_result.get('quality')
        }

        if target_item:
            # Apply to existing item
            if 'enchantments' not in target_item:
                target_item['enchantments'] = []

            target_item['enchantments'].append(enchantment_data)

            return {
                "success": True,
                "message": f"Enchantment applied to {target_item.get('itemId')}",
                "enchantment": enchantment_data,
                "enchanted_item": target_item
            }
        else:
            # Create new accessory
            return {
                "success": True,
                "outputId": recipe['outputId'],
                "quantity": recipe['outputQty'],
                "message": "Accessory created",
                "enchantment": enchantment_data
            }

    def get_recipe(self, recipe_id):
        """Get recipe by ID"""
        return self.recipes.get(recipe_id)

    def get_all_recipes(self):
        """Get all loaded recipes"""
        return self.recipes

    def can_enchant_item(self, item, recipe_id):
        """
        Check if item can receive this enchantment

        Args:
            item: Item dict
            recipe_id: Enchantment recipe ID

        Returns:
            bool: True if compatible
        """
        if recipe_id not in self.recipes:
            return False

        recipe = self.recipes[recipe_id]
        applicable_to = recipe.get('applicableTo', [])

        # Check if item type is in applicable list
        item_type = item.get('type', 'unknown')

        if not applicable_to:
            return True  # No restrictions

        return item_type in applicable_to

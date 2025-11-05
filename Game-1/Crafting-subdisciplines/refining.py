"""
Refining Crafting Subdiscipline

Framework:
- Python module ready for main.py integration
- Loads recipes from JSON files
- Optional minigame (lockpicking-style cylinder alignment)
- Difficulty based on tier (tier + X + Y in future updates)

Minigame: Lockpicking-style timing game
- Watch rotating cylinders align with target zones
- Press key when aligned (spacebar or number keys)
- All-or-nothing success (no partial completion)
- Difficulty scales with tier
"""

import pygame
import json
import random
import math
from pathlib import Path
from rarity_utils import rarity_system


class RefiningMinigame:
    """
    Refining minigame implementation - Lockpicking style

    Goal: Align all cylinders by pressing key when indicator is in target zone
    - Visual rotating cylinders
    - Audio/visual feedback on successful alignment
    - All-or-nothing success
    """

    def __init__(self, recipe, tier=1):
        """
        Initialize refining minigame

        Args:
            recipe: Recipe dict from JSON
            tier: Recipe tier (1-4) - affects difficulty
        """
        self.recipe = recipe
        self.tier = tier

        # Difficulty scaling based on tier
        # NOTE: Future updates may include additional factors
        self._setup_difficulty()

        # Game state
        self.active = False
        self.cylinders = []
        self.current_cylinder = 0
        self.aligned_cylinders = []
        self.failed_attempts = 0
        self.time_left = self.time_limit
        self.result = None
        self.feedback_timer = 0  # For visual/audio feedback

    def _setup_difficulty(self):
        """
        Setup difficulty parameters based on tier

        NOTE: Difficulty formula may be expanded in future updates
        Currently: tier-based only
        Future: tier + material_rarity + recipe_complexity + etc.
        """
        if self.tier == 1:
            self.cylinder_count = 3
            self.timing_window = 0.8  # seconds
            self.rotation_speed = 1.0  # rotations per second
            self.allowed_failures = 2
            self.time_limit = 45
        elif self.tier == 2:
            self.cylinder_count = 6
            self.timing_window = 0.5
            self.rotation_speed = 1.3
            self.allowed_failures = 1
            self.time_limit = 30
        elif self.tier == 3:
            self.cylinder_count = 10
            self.timing_window = 0.3
            self.rotation_speed = 1.6
            self.allowed_failures = 0  # Perfect required
            self.time_limit = 20
        else:  # tier 4
            self.cylinder_count = 15
            self.timing_window = 0.2
            self.rotation_speed = 2.0
            self.allowed_failures = 0  # Perfect required
            self.time_limit = 15
            # Additional complexity for T4
            self.multi_speed = True  # Different cylinders rotate at different speeds

    def start(self):
        """Start the minigame"""
        self.active = True
        self.current_cylinder = 0
        self.aligned_cylinders = []
        self.failed_attempts = 0
        self.time_left = self.time_limit
        self.result = None
        self.feedback_timer = 0

        # Initialize cylinders
        self.cylinders = []
        for i in range(self.cylinder_count):
            # Randomize starting positions
            start_angle = random.uniform(0, 360)

            # For T4, vary rotation speeds
            if self.tier >= 4 and i % 2 == 0:
                speed = self.rotation_speed * 0.7
            elif self.tier >= 4 and i % 3 == 0:
                speed = self.rotation_speed * 1.3
            else:
                speed = self.rotation_speed

            # Randomize direction (some clockwise, some counter-clockwise)
            direction = random.choice([1, -1])

            self.cylinders.append({
                "angle": start_angle,
                "speed": speed,
                "direction": direction,
                "aligned": False,
                "target_zone": 0  # Top position
            })

    def update(self, dt):
        """
        Update minigame state

        Args:
            dt: Delta time in seconds
        """
        if not self.active:
            return

        # Update timer
        self.time_left -= dt
        if self.time_left <= 0:
            self.end(success=False, reason="Time's up!")
            return

        # Update feedback timer
        if self.feedback_timer > 0:
            self.feedback_timer -= dt

        # Rotate cylinders that aren't aligned yet
        for i, cylinder in enumerate(self.cylinders):
            if not cylinder["aligned"]:
                # Rotate
                rotation_per_second = cylinder["speed"] * 360  # degrees per second
                cylinder["angle"] += cylinder["direction"] * rotation_per_second * dt
                cylinder["angle"] %= 360  # Wrap around

    def handle_attempt(self):
        """
        Handle alignment attempt (spacebar press)

        Returns:
            bool: True if successful alignment
        """
        if not self.active or self.current_cylinder >= self.cylinder_count:
            return False

        cylinder = self.cylinders[self.current_cylinder]

        # Check if in target zone
        angle = cylinder["angle"]
        target = cylinder["target_zone"]

        # Calculate angular distance (accounting for wraparound)
        distance = min(abs(angle - target), 360 - abs(angle - target))

        # Convert timing window from seconds to degrees
        # timing_window seconds * speed rotations/sec * 360 degrees/rotation
        window_degrees = self.timing_window * cylinder["speed"] * 360

        if distance <= window_degrees / 2:
            # SUCCESS!
            cylinder["aligned"] = True
            self.aligned_cylinders.append(self.current_cylinder)
            self.current_cylinder += 1
            self.feedback_timer = 0.3  # Show success feedback for 0.3 seconds

            # Check if all cylinders aligned
            if self.current_cylinder >= self.cylinder_count:
                self.end(success=True)

            return True
        else:
            # FAILURE
            self.failed_attempts += 1
            self.feedback_timer = 0.3  # Show failure feedback

            if self.failed_attempts > self.allowed_failures:
                self.end(success=False, reason="Too many failed attempts!")

            return False

    def end(self, success, reason=None):
        """
        End the minigame

        Args:
            success: Whether refinement succeeded
            reason: Optional failure reason
        """
        self.active = False

        if success:
            self.result = {
                "success": True,
                "message": "Refinement successful!",
                "attempts": self.current_cylinder + self.failed_attempts
            }
        else:
            self.result = {
                "success": False,
                "message": reason or "Refinement failed",
                "materials_lost": 0.5  # 50% material loss on failure
            }

    def get_state(self):
        """Get current minigame state for rendering"""
        return {
            "active": self.active,
            "cylinders": self.cylinders,
            "current_cylinder": self.current_cylinder,
            "aligned_count": len(self.aligned_cylinders),
            "total_cylinders": self.cylinder_count,
            "failed_attempts": self.failed_attempts,
            "allowed_failures": self.allowed_failures,
            "time_left": self.time_left,
            "result": self.result,
            "feedback_timer": self.feedback_timer,
            "timing_window": self.timing_window
        }


class RefiningCrafter:
    """
    Main refining crafting interface

    Handles:
    - Recipe loading from JSON
    - Hub-and-spoke slot system
    - Material validation
    - Instant crafting (skip minigame)
    - Minigame crafting (all-or-nothing)
    """

    def __init__(self):
        """Initialize refining crafter"""
        self.recipes = {}
        self.placements = {}
        self.load_recipes()
        self.load_placements()

    def load_recipes(self):
        """Load refining recipes from JSON files"""
        possible_paths = [
            "../recipes.JSON/recipes-refining-1.json",
            "recipes.JSON/recipes-refining-1.json",
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
            print(f"[Refining] Loaded {len(self.recipes)} recipes")
        else:
            print("[Refining] WARNING: No recipes loaded")

    def load_placements(self):
        """Load placement data from JSON files"""
        possible_paths = [
            "../placements.JSON/placements-refining-1.JSON",
            "placements.JSON/placements-refining-1.JSON",
        ]

        for path in possible_paths:
            try:
                with open(path, 'r') as f:
                    data = json.load(f)
                    placement_list = data.get('placements', [])
                    for p in placement_list:
                        self.placements[p['recipeId']] = p
            except FileNotFoundError:
                continue

        if self.placements:
            print(f"[Refining] Loaded {len(self.placements)} placements")

    def get_placement(self, recipe_id):
        """Get placement pattern for a recipe"""
        return self.placements.get(recipe_id)

    def can_craft(self, recipe_id, inventory):
        """
        Check if recipe can be crafted with given inventory
        Also checks rarity uniformity (all materials must be same rarity)

        Args:
            recipe_id: Recipe ID to check
            inventory: Dict of {material_id: quantity}

        Returns:
            tuple: (can_craft: bool, error_message: str or None)
        """
        if recipe_id not in self.recipes:
            return False, "Recipe not found"

        recipe = self.recipes[recipe_id]

        # Check material quantities
        for inp in recipe.get('inputs', []):
            if inventory.get(inp['materialId'], 0) < inp['quantity']:
                return False, f"Insufficient {inp['materialId']}"

        # Check rarity uniformity
        inputs = recipe.get('inputs', [])
        is_uniform, rarity, error_msg = rarity_system.check_rarity_uniformity(inputs)

        if not is_uniform:
            return False, error_msg

        return True, None

    def craft_instant(self, recipe_id, inventory):
        """
        Instant craft (no minigame) - produces base output

        Args:
            recipe_id: Recipe ID to craft
            inventory: Dict of {material_id: quantity} (will be modified)

        Returns:
            dict: Result with outputId, quantity, success, rarity
        """
        can_craft, error_msg = self.can_craft(recipe_id, inventory)
        if not can_craft:
            return {"success": False, "message": error_msg or "Cannot craft"}

        recipe = self.recipes[recipe_id]

        # Detect input rarity
        inputs = recipe.get('inputs', [])
        _, input_rarity, _ = rarity_system.check_rarity_uniformity(inputs)

        # Deduct materials
        for inp in recipe['inputs']:
            inventory[inp['materialId']] -= inp['quantity']

        # Refining uses 'outputs' array instead of outputId/outputQty
        outputs = recipe.get('outputs', [])
        if outputs:
            output = outputs[0]  # Take first output
            output_id = output.get('materialId', recipe.get('outputId', 'unknown'))
            output_qty = output.get('quantity', recipe.get('outputQty', 1))
        else:
            # Fallback to old format
            output_id = recipe.get('outputId', 'unknown')
            output_qty = recipe.get('outputQty', 1)

        return {
            "success": True,
            "outputId": output_id,
            "quantity": output_qty,
            "rarity": input_rarity,
            "message": f"Refined ({input_rarity})"
        }

    def create_minigame(self, recipe_id):
        """
        Create a refining minigame for this recipe

        Args:
            recipe_id: Recipe ID to craft

        Returns:
            RefiningMinigame instance or None if recipe not found
        """
        if recipe_id not in self.recipes:
            return None

        recipe = self.recipes[recipe_id]
        tier = recipe.get('stationTier', 1)

        return RefiningMinigame(recipe, tier)

    def craft_with_minigame(self, recipe_id, inventory, minigame_result):
        """
        Craft with minigame result - all-or-nothing
        Refining outputs materials with rarity but NO stat bonuses

        Args:
            recipe_id: Recipe ID to craft
            inventory: Dict of {material_id: quantity} (will be modified)
            minigame_result: Result dict from RefiningMinigame

        Returns:
            dict: Result with outputId, quantity, rarity, success
        """
        recipe = self.recipes[recipe_id]

        if not minigame_result.get('success'):
            # Failure - lose 50% of materials
            for inp in recipe['inputs']:
                loss = inp['quantity'] // 2
                inventory[inp['materialId']] = max(0, inventory[inp['materialId']] - loss)

            return {
                "success": False,
                "message": minigame_result.get('message', 'Refining failed'),
                "materials_lost": True
            }

        # Success - deduct full materials and give output
        for inp in recipe['inputs']:
            inventory[inp['materialId']] -= inp['quantity']

        # Detect input rarity (base rarity from input materials)
        inputs = recipe.get('inputs', [])
        _, input_rarity, _ = rarity_system.check_rarity_uniformity(inputs)

        # Handle outputs array format (refining uses outputs, not outputId)
        outputs = recipe.get('outputs', [])
        if outputs:
            output = outputs[0]
            output_id = output.get('materialId', recipe.get('outputId', 'unknown'))
            output_qty = output.get('quantity', recipe.get('outputQty', 1))
        else:
            output_id = recipe.get('outputId', 'unknown')
            output_qty = recipe.get('outputQty', 1)

        # Apply rarity upgrade based on minigame performance (Game Mechanics v5)
        # Refining can upgrade material rarity based on quality
        quality = minigame_result.get('quality', 0.5)

        # Map rarity tiers to upgrade logic
        rarity_tiers = ['common', 'uncommon', 'rare', 'epic', 'legendary']
        current_tier_idx = rarity_tiers.index(input_rarity) if input_rarity in rarity_tiers else 0

        # Quality determines rarity upgrade
        if quality >= 0.95:  # Exceptional performance
            output_rarity_idx = min(current_tier_idx + 2, len(rarity_tiers) - 1)  # +2 tiers
        elif quality >= 0.8:  # Great performance
            output_rarity_idx = min(current_tier_idx + 1, len(rarity_tiers) - 1)  # +1 tier
        else:  # Good performance
            output_rarity_idx = current_tier_idx  # Same tier

        output_rarity = rarity_tiers[output_rarity_idx]

        result = {
            "success": True,
            "outputId": output_id,
            "quantity": output_qty,
            "rarity": output_rarity,
            "message": f"Refined to {output_rarity} quality!"
        }

        return result

    def get_recipe(self, recipe_id):
        """Get recipe by ID"""
        return self.recipes.get(recipe_id)

    def get_all_recipes(self):
        """Get all loaded recipes"""
        return self.recipes


# Hub-and-Spoke slot system (for future implementation in main.py)
class RefiningStation:
    """
    Refining station with hub-and-spoke slot system

    NOTE: This is a reference implementation for main.py integration
    Actual UI would be in main.py or simulator
    """

    def __init__(self, tier=1):
        """
        Initialize refining station

        Args:
            tier: Station tier (1-4)
        """
        self.tier = tier

        # Slot configuration based on tier
        if tier == 1:
            self.core_slots = 1
            self.surrounding_slots = 2
        elif tier == 2:
            self.core_slots = 1
            self.surrounding_slots = 4
        elif tier == 3:
            self.core_slots = 2
            self.surrounding_slots = 5
        else:  # tier 4
            self.core_slots = 3
            self.surrounding_slots = 6

        # Current slot contents {slot_index: {materialId, quantity}}
        self.slots = {}
        self.fuel_slot = None  # Optional fuel for minigame buffs

    def can_add_material(self, slot_index, material_id, quantity):
        """Check if material can be added to slot (stackable to 256)"""
        if slot_index in self.slots:
            current = self.slots[slot_index]
            if current['materialId'] != material_id:
                return False
            if current['quantity'] + quantity > 256:
                return False
        return quantity <= 256

    def add_material(self, slot_index, material_id, quantity):
        """Add material to slot"""
        if slot_index in self.slots:
            self.slots[slot_index]['quantity'] += quantity
        else:
            self.slots[slot_index] = {'materialId': material_id, 'quantity': quantity}

    def validate_recipe(self):
        """
        Validate that slots match a valid recipe

        Returns:
            bool: True if valid recipe configuration
        """
        # TODO: Implement recipe validation
        # Check that core slots have equal quantities
        # Check that materials match a known recipe
        return False

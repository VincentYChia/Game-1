"""
Smithing Crafting Subdiscipline

Framework:
- Python module ready for main.py integration
- Loads recipes from JSON files
- Optional minigame (temperature + hammering)
- Difficulty based on tier (tier + X + Y in future updates)

Minigame: Temperature management + hammering/forging
- Temperature: Keyboard controls (WASD/arrows/spacebar)
- Hammering: Mouse controls (clicking)
- Difficulty scales with tier
"""

import pygame
import json
from pathlib import Path


class SmithingMinigame:
    """
    Smithing minigame implementation

    Controls:
    - Spacebar: Fan flames (increase temperature)
    - Click HAMMER button: Execute hammer strike when indicator is in target zone

    Goal: Maintain ideal temperature while hitting perfect timing on hammer strikes
    """

    def __init__(self, recipe, tier=1):
        """
        Initialize smithing minigame

        Args:
            recipe: Recipe dict from JSON
            tier: Recipe tier (1-4) - affects difficulty
        """
        self.recipe = recipe
        self.tier = tier

        # Difficulty scaling based on tier
        # NOTE: Future updates may include additional factors (tier + X + Y = difficulty)
        self._setup_difficulty()

        # Game state
        self.active = False
        self.temperature = 50.0
        self.hammer_hits = 0
        self.hammer_position = 0
        self.hammer_direction = 1
        self.hammer_scores = []
        self.time_left = self.time_limit
        self.last_temp_update = 0
        self.result = None

    def _setup_difficulty(self):
        """
        Setup difficulty parameters based on tier

        NOTE: Difficulty formula may be expanded in future updates
        Currently: tier-based only
        Future: tier + material_complexity + recipe_size + etc.
        """
        # Temperature params
        if self.tier == 1:
            self.TEMP_IDEAL_MIN = 60
            self.TEMP_IDEAL_MAX = 80
            self.TEMP_DECAY = 0.5
            self.TEMP_FAN_INCREMENT = 3
            self.HAMMER_SPEED = 2.5
            self.REQUIRED_HITS = 5
            self.TARGET_WIDTH = 100
            self.PERFECT_WIDTH = 40
            self.time_limit = 45
        elif self.tier == 2:
            self.TEMP_IDEAL_MIN = 65
            self.TEMP_IDEAL_MAX = 75
            self.TEMP_DECAY = 0.7
            self.TEMP_FAN_INCREMENT = 2.5
            self.HAMMER_SPEED = 3.5
            self.REQUIRED_HITS = 7
            self.TARGET_WIDTH = 80
            self.PERFECT_WIDTH = 30
            self.time_limit = 40
        elif self.tier == 3:
            self.TEMP_IDEAL_MIN = 68
            self.TEMP_IDEAL_MAX = 72
            self.TEMP_DECAY = 0.9
            self.TEMP_FAN_INCREMENT = 2
            self.HAMMER_SPEED = 4.5
            self.REQUIRED_HITS = 9
            self.TARGET_WIDTH = 60
            self.PERFECT_WIDTH = 20
            self.time_limit = 35
        else:  # tier 4
            self.TEMP_IDEAL_MIN = 69
            self.TEMP_IDEAL_MAX = 71
            self.TEMP_DECAY = 1.1
            self.TEMP_FAN_INCREMENT = 1.5
            self.HAMMER_SPEED = 5.5
            self.REQUIRED_HITS = 12
            self.TARGET_WIDTH = 40
            self.PERFECT_WIDTH = 15
            self.time_limit = 30

        self.HAMMER_BAR_WIDTH = 400

    def start(self):
        """Start the minigame"""
        self.active = True
        self.temperature = 50.0
        self.hammer_hits = 0
        self.hammer_position = 0
        self.hammer_direction = 1
        self.hammer_scores = []
        self.time_left = self.time_limit
        self.last_temp_update = pygame.time.get_ticks()
        self.result = None

    def update(self, dt):
        """
        Update minigame state

        Args:
            dt: Delta time in milliseconds
        """
        if not self.active:
            return

        # Temperature decay
        now = pygame.time.get_ticks()
        if now - self.last_temp_update > 100:
            self.temperature = max(0, self.temperature - self.TEMP_DECAY)
            self.last_temp_update = now

        # Hammer movement
        if self.hammer_hits < self.REQUIRED_HITS:
            self.hammer_position += self.hammer_direction * self.HAMMER_SPEED
            if self.hammer_position <= 0 or self.hammer_position >= self.HAMMER_BAR_WIDTH:
                self.hammer_direction *= -1
                self.hammer_position = max(0, min(self.HAMMER_BAR_WIDTH, self.hammer_position))

        # Timer (rough implementation - improve for production)
        # TODO: Use proper delta time for accurate timing
        self.time_left = max(0, self.time_left - dt / 1000.0)
        if self.time_left <= 0:
            self.end(completed=False, reason="Time's up!")

    def handle_fan(self):
        """Handle fan action (spacebar) - increases temperature"""
        if self.active:
            self.temperature = min(100, self.temperature + self.TEMP_FAN_INCREMENT)

    def handle_hammer(self):
        """Handle hammer strike (click) - check timing accuracy"""
        if not self.active or self.hammer_hits >= self.REQUIRED_HITS:
            return

        center = self.HAMMER_BAR_WIDTH / 2
        distance = abs(self.hammer_position - center)

        # Score based on accuracy
        if distance <= self.PERFECT_WIDTH / 2:
            score = 100
        elif distance <= self.TARGET_WIDTH / 2:
            score = 70
        else:
            score = 30

        self.hammer_scores.append(score)
        self.hammer_hits += 1

        if self.hammer_hits >= self.REQUIRED_HITS:
            self.end(completed=True)

    def end(self, completed, reason=None):
        """
        End the minigame and calculate results

        Args:
            completed: Whether all hammer hits were completed
            reason: Optional failure reason
        """
        self.active = False

        if not completed:
            self.result = {
                "success": False,
                "message": reason or "Failed to complete",
                "score": 0,
                "bonus": 0
            }
            return

        # Calculate score
        avg_hammer_score = sum(self.hammer_scores) / len(self.hammer_scores) if self.hammer_scores else 0

        # Temperature multiplier
        in_ideal_range = self.TEMP_IDEAL_MIN <= self.temperature <= self.TEMP_IDEAL_MAX
        temp_mult = 1.5 if in_ideal_range else 1.0

        final_score = avg_hammer_score * temp_mult

        # Bonus stats based on score
        if final_score >= 140:
            bonus = 15  # +15% bonus stats
        elif final_score >= 100:
            bonus = 10  # +10% bonus stats
        elif final_score >= 70:
            bonus = 5   # +5% bonus stats
        else:
            bonus = 0   # Base stats only

        self.result = {
            "success": True,
            "score": final_score,
            "bonus": bonus,
            "temp_mult": temp_mult,
            "avg_hammer": avg_hammer_score,
            "message": f"Crafted with {bonus}% bonus!"
        }

    def get_state(self):
        """Get current minigame state for rendering"""
        return {
            "active": self.active,
            "temperature": self.temperature,
            "hammer_hits": self.hammer_hits,
            "required_hits": self.REQUIRED_HITS,
            "hammer_position": self.hammer_position,
            "hammer_scores": self.hammer_scores,
            "time_left": self.time_left,
            "result": self.result,
            # Config for rendering
            "temp_ideal_min": self.TEMP_IDEAL_MIN,
            "temp_ideal_max": self.TEMP_IDEAL_MAX,
            "hammer_bar_width": self.HAMMER_BAR_WIDTH,
            "target_width": self.TARGET_WIDTH,
            "perfect_width": self.PERFECT_WIDTH
        }


class SmithingCrafter:
    """
    Main smithing crafting interface

    Handles:
    - Recipe loading from JSON
    - Material validation
    - Instant crafting (skip minigame)
    - Minigame crafting (with bonuses)
    """

    def __init__(self):
        """Initialize smithing crafter"""
        self.recipes = {}
        self.placements = {}
        self.load_recipes()
        self.load_placements()

    def load_recipes(self):
        """Load smithing recipes from JSON files"""
        possible_paths = [
            "../recipes.JSON/recipes-smithing-1.json",
            "../recipes.JSON/recipes-smithing-2.json",
            "../recipes.JSON/recipes-smithing-3.json",
            "recipes.JSON/recipes-smithing-1.json",
            "recipes.JSON/recipes-smithing-2.json",
            "recipes.JSON/recipes-smithing-3.json",
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
            print(f"[Smithing] Loaded {len(self.recipes)} recipes")
        else:
            print("[Smithing] WARNING: No recipes loaded")

    def load_placements(self):
        """Load placement data from JSON files"""
        possible_paths = [
            "../placements.JSON/placements-smithing-1.JSON",
            "placements.JSON/placements-smithing-1.JSON",
        ]

        for path in possible_paths:
            try:
                with open(path, 'r') as f:
                    data = json.load(f)
                    placement_list = data.get('placements', [])
                    for p in placement_list:
                        self.placements[p['recipeId']] = p.get('placementMap', {})
            except FileNotFoundError:
                continue

        if self.placements:
            print(f"[Smithing] Loaded {len(self.placements)} placement maps")

    def get_placement(self, recipe_id):
        """Get placement pattern for a recipe"""
        return self.placements.get(recipe_id)

    def can_craft(self, recipe_id, inventory):
        """
        Check if recipe can be crafted with given inventory

        Args:
            recipe_id: Recipe ID to check
            inventory: Dict of {material_id: quantity}

        Returns:
            bool: True if can craft
        """
        if recipe_id not in self.recipes:
            return False

        recipe = self.recipes[recipe_id]
        for inp in recipe.get('inputs', []):
            if inventory.get(inp['materialId'], 0) < inp['quantity']:
                return False
        return True

    def craft_instant(self, recipe_id, inventory):
        """
        Instant craft (no minigame) - produces base item

        Args:
            recipe_id: Recipe ID to craft
            inventory: Dict of {material_id: quantity} (will be modified)

        Returns:
            dict: Result with outputId, quantity, success
        """
        if not self.can_craft(recipe_id, inventory):
            return {"success": False, "message": "Insufficient materials"}

        recipe = self.recipes[recipe_id]

        # Deduct materials
        for inp in recipe['inputs']:
            inventory[inp['materialId']] -= inp['quantity']

        return {
            "success": True,
            "outputId": recipe['outputId'],
            "quantity": recipe['outputQty'],
            "bonus": 0,
            "message": "Crafted (base stats)"
        }

    def create_minigame(self, recipe_id):
        """
        Create a smithing minigame for this recipe

        Args:
            recipe_id: Recipe ID to craft

        Returns:
            SmithingMinigame instance or None if recipe not found
        """
        if recipe_id not in self.recipes:
            return None

        recipe = self.recipes[recipe_id]
        tier = recipe.get('stationTier', 1)

        return SmithingMinigame(recipe, tier)

    def craft_with_minigame(self, recipe_id, inventory, minigame_result):
        """
        Craft with minigame result - produces item with bonuses

        Args:
            recipe_id: Recipe ID to craft
            inventory: Dict of {material_id: quantity} (will be modified)
            minigame_result: Result dict from SmithingMinigame

        Returns:
            dict: Result with outputId, quantity, bonus, success
        """
        if not minigame_result.get('success'):
            # Failure - lose some materials (50% for now)
            recipe = self.recipes[recipe_id]
            for inp in recipe['inputs']:
                loss = inp['quantity'] // 2
                inventory[inp['materialId']] = max(0, inventory[inp['materialId']] - loss)

            return {
                "success": False,
                "message": minigame_result.get('message', 'Crafting failed'),
                "materials_lost": True
            }

        # Success - deduct full materials
        recipe = self.recipes[recipe_id]
        for inp in recipe['inputs']:
            inventory[inp['materialId']] -= inp['quantity']

        # Calculate base stats for the item (will be modified by rarity bonus)
        tier = recipe.get('stationTier', 1)
        bonus_pct = minigame_result.get('bonus', 0)

        # Base stats scale with tier and minigame performance
        base_stats = {
            "durability": 100 + (tier * 20) + bonus_pct,  # Tier 1: 100-120, Tier 2: 120-140, etc.
            "quality": 100 + bonus_pct,  # Minigame performance
            "power": 100 + (tier * 15)  # Tier-based power
        }

        return {
            "success": True,
            "outputId": recipe['outputId'],
            "quantity": recipe['outputQty'],
            "bonus": minigame_result.get('bonus', 0),
            "score": minigame_result.get('score', 0),
            "stats": base_stats,
            "message": f"Crafted with +{minigame_result.get('bonus', 0)}% bonus!"
        }

    def get_recipe(self, recipe_id):
        """Get recipe by ID"""
        return self.recipes.get(recipe_id)

    def get_all_recipes(self):
        """Get all loaded recipes"""
        return self.recipes

    def get_placement(self, recipe_id):
        """Get placement map for recipe"""
        return self.placements.get(recipe_id, {})

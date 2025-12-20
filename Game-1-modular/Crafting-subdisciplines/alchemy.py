"""
Alchemy Crafting Subdiscipline

Framework:
- Python module ready for main.py integration
- Loads recipes from JSON files
- Optional minigame (reaction chain management)
- Difficulty based on tier (tier + X + Y in future updates)

Minigame: Reaction chain management - reading visual cues
- Watch reactions grow through stages
- Add next ingredient at optimal time (CHAIN)
- Or stabilize to end process
- Gradient success system (progress-based quality)
"""

import pygame
import json
import random
from pathlib import Path
from rarity_utils import rarity_system


class AlchemyReaction:
    """
    Individual ingredient reaction in alchemy minigame

    Reaction progresses through 5 stages:
    1. Initiation (5% progress)
    2. Building with false peaks (15-20% progress)
    3. SWEET SPOT optimal (30-35% progress) <- TARGET
    4. Degrading late (20-25% progress)
    5. Critical failure risk (5-10% progress or explosion)
    """

    def __init__(self, ingredient_id, ingredient_type="moderate"):
        """
        Initialize reaction

        Args:
            ingredient_id: Ingredient material ID
            ingredient_type: Reaction behavior type (stable, moderate, volatile, legendary)
        """
        self.ingredient_id = ingredient_id
        self.ingredient_type = ingredient_type

        # Reaction state
        self.stage = 1  # 1-5
        self.progress = 0.0  # 0.0-1.0 through current stage
        self.locked_quality = None  # Quality when chained/stabilized

        # Setup timing based on ingredient type
        self._setup_timing()

        # Visual state (for rendering)
        self.size = 0.0  # Bubble size
        self.glow = 0.0  # Glow intensity
        self.color_shift = 0.0  # Color variation

    def _setup_timing(self):
        """
        Setup reaction timing based on ingredient type

        NOTE: Timings may be adjusted in future updates
        """
        if self.ingredient_type == "stable":
            # Easy: slow, predictable, wide sweet spot
            self.stage_durations = [1.0, 2.5, 2.0, 2.0, 1.5]  # seconds
            self.sweet_spot_duration = 2.0  # Wide window
            self.false_peaks = []  # No false peaks
        elif self.ingredient_type == "moderate":
            # Medium: medium speed, some irregularity
            self.stage_durations = [0.8, 2.0, 1.5, 1.5, 1.2]
            self.sweet_spot_duration = 1.5
            self.false_peaks = [0.4, 0.7]  # False peaks during stage 2
        elif self.ingredient_type == "volatile":
            # Hard: fast, erratic, narrow sweet spot
            self.stage_durations = [0.5, 1.5, 1.0, 1.0, 0.8]
            self.sweet_spot_duration = 1.0
            self.false_peaks = [0.3, 0.5, 0.7, 0.9]  # Many false peaks
        else:  # legendary
            # Extreme: very fast, complex
            self.stage_durations = [0.4, 1.0, 0.5, 0.7, 0.5]
            self.sweet_spot_duration = 0.5  # Very narrow
            self.false_peaks = [0.2, 0.4, 0.5, 0.6, 0.8]  # Many false peaks

        self.current_stage_duration = self.stage_durations[0]

    def update(self, dt):
        """
        Update reaction progress

        Args:
            dt: Delta time in seconds
        """
        if self.locked_quality is not None:
            return  # Already locked

        # Progress through current stage
        self.progress += dt / self.current_stage_duration

        if self.progress >= 1.0:
            # Move to next stage
            self.progress = 0.0
            self.stage += 1

            if self.stage <= 5:
                self.current_stage_duration = self.stage_durations[self.stage - 1]
            else:
                # EXPLOSION! Stayed too long in stage 5
                self.stage = 6  # Explosion state
                self.locked_quality = 0.0  # Total failure

        # Update visual state
        self._update_visuals()

    def _update_visuals(self):
        """Update visual properties based on stage and progress"""
        if self.stage == 1:
            # Initiation: small, dim
            self.size = 0.2 + self.progress * 0.2
            self.glow = 0.3 + self.progress * 0.2
        elif self.stage == 2:
            # Building: growing, brightening, false peaks
            self.size = 0.4 + self.progress * 0.3
            base_glow = 0.5 + self.progress * 0.3

            # Add false peaks
            for peak_pos in self.false_peaks:
                if abs(self.progress - peak_pos) < 0.05:
                    base_glow += 0.2  # Spike in glow
                    self.size += 0.1

            self.glow = min(1.0, base_glow)
        elif self.stage == 3:
            # SWEET SPOT: steady, intense, optimal
            self.size = 0.7 + self.progress * 0.1
            self.glow = 0.9  # Sustained intense glow
            self.color_shift = 1.0  # Saturated color
        elif self.stage == 4:
            # Degrading: irregular, flickering
            self.size = 0.8 + random.uniform(-0.1, 0.1)  # Irregular
            self.glow = 0.7 - self.progress * 0.2  # Fading
            self.color_shift = 0.7 - self.progress * 0.3
        elif self.stage == 5:
            # Critical: over-expansion, dark, violent
            self.size = 0.9 + self.progress * 0.2
            self.glow = 0.4 - self.progress * 0.3  # Darkening
            self.color_shift = 0.0  # Dark/smoky

    def get_quality(self):
        """
        Get quality contribution if chained/stabilized now

        Returns:
            float: Progress contribution (0.0-0.35, with 0.30-0.35 being optimal)
        """
        if self.stage == 1:
            return 0.05  # Too early
        elif self.stage == 2:
            return 0.15 + self.progress * 0.05  # Building, not optimal
        elif self.stage == 3:
            return 0.30 + self.progress * 0.05  # OPTIMAL (30-35%)
        elif self.stage == 4:
            return 0.25 - self.progress * 0.05  # Declining
        elif self.stage == 5:
            return 0.10 - self.progress * 0.05  # Very weak
        else:
            return 0.0  # Explosion

    def chain(self):
        """
        Chain this reaction (lock quality, start next ingredient)

        Returns:
            float: Locked quality value
        """
        self.locked_quality = self.get_quality()
        return self.locked_quality

    def get_state(self):
        """Get visual state for rendering"""
        return {
            "ingredient_id": self.ingredient_id,
            "stage": self.stage,
            "progress": self.progress,
            "locked": self.locked_quality is not None,
            "quality": self.locked_quality if self.locked_quality is not None else self.get_quality(),
            "size": self.size,
            "glow": self.glow,
            "color_shift": self.color_shift
        }


class AlchemyMinigame:
    """
    Alchemy minigame implementation - Reaction chain management

    Process:
    1. Load ingredients into slots
    2. Start brewing
    3. Add first ingredient → reaction begins
    4. Watch reaction grow through stages
    5. CHAIN (add next) or STABILIZE (end)
    6. Total progress = sum of all locked reaction qualities
    """

    def __init__(self, recipe, tier=1, buff_time_bonus=0.0, buff_quality_bonus=0.0):
        """
        Initialize alchemy minigame

        Args:
            recipe: Recipe dict from JSON
            tier: Recipe tier (1-4) - affects difficulty
            buff_time_bonus: Skill buff bonus to time limit (0.0-1.0+)
            buff_quality_bonus: Skill buff bonus to quality (0.0-1.0+)
        """
        self.recipe = recipe
        self.tier = tier
        self.buff_time_bonus = buff_time_bonus
        self.buff_quality_bonus = buff_quality_bonus
        self.ingredients = recipe.get('inputs', [])

        # Difficulty scaling
        self._setup_difficulty()

        # Apply skill buff bonuses to time limit
        if self.buff_time_bonus > 0:
            self.time_limit = int(self.time_limit * (1.0 + self.buff_time_bonus))

        # Game state
        self.active = False
        self.current_ingredient_index = 0
        self.current_reaction = None
        self.locked_reactions = []
        self.total_progress = 0.0
        self.time_left = self.time_limit
        self.result = None

    def _setup_difficulty(self):
        """
        Setup difficulty parameters based on tier

        NOTE: Difficulty formula may be expanded in future updates
        """
        if self.tier == 1:
            self.time_limit = 60
            self.ingredient_types = ["stable", "stable", "moderate"]
        elif self.tier == 2:
            self.time_limit = 45
            self.ingredient_types = ["stable", "moderate", "moderate"]
        elif self.tier == 3:
            self.time_limit = 30
            self.ingredient_types = ["moderate", "volatile", "volatile"]
        else:  # tier 4
            self.time_limit = 20
            self.ingredient_types = ["volatile", "legendary", "legendary"]

    def start(self):
        """Start the minigame"""
        self.active = True
        self.current_ingredient_index = 0
        self.locked_reactions = []
        self.total_progress = 0.0
        self.time_left = self.time_limit
        self.result = None

        # Start first ingredient
        if self.ingredients:
            self._start_next_ingredient()

    def _start_next_ingredient(self):
        """Start reaction for next ingredient"""
        if self.current_ingredient_index >= len(self.ingredients):
            return

        ingredient = self.ingredients[self.current_ingredient_index]

        # Determine ingredient type based on tier and index
        if self.current_ingredient_index < len(self.ingredient_types):
            ing_type = self.ingredient_types[self.current_ingredient_index]
        else:
            ing_type = "moderate"  # Default

        self.current_reaction = AlchemyReaction(ingredient['materialId'], ing_type)

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
            # Time's up - stabilize with current progress
            self.stabilize()
            return

        # Update current reaction
        if self.current_reaction:
            self.current_reaction.update(dt)

            # Check for explosion
            if self.current_reaction.stage >= 6:
                self.end(explosion=True)

    def chain(self):
        """
        Chain current reaction (lock it and start next ingredient)

        Returns:
            bool: True if chained successfully
        """
        if not self.active or not self.current_reaction:
            print(f"[ALCHEMY DEBUG] Chain failed: active={self.active}, current_reaction={self.current_reaction}")
            return False

        # Lock current reaction quality
        quality = self.current_reaction.chain()
        self.locked_reactions.append(self.current_reaction)
        self.total_progress += quality

        # Move to next ingredient
        self.current_ingredient_index += 1
        print(f"[ALCHEMY DEBUG] Chained ingredient {self.current_ingredient_index-1}, moving to index {self.current_ingredient_index}/{len(self.ingredients)}")

        if self.current_ingredient_index < len(self.ingredients):
            self._start_next_ingredient()
            print(f"[ALCHEMY DEBUG] Started next ingredient")
            return True
        else:
            # No more ingredients - auto stabilize
            print(f"[ALCHEMY DEBUG] No more ingredients, auto-stabilizing")
            self.stabilize()
            return True

    def stabilize(self):
        """
        Stabilize current reaction and complete brewing

        Returns:
            bool: True if stabilized successfully
        """
        if not self.active:
            return False

        # Lock current reaction if exists
        if self.current_reaction and self.current_reaction.locked_quality is None:
            quality = self.current_reaction.chain()
            self.locked_reactions.append(self.current_reaction)
            self.total_progress += quality

        # Complete the brew
        self.end(explosion=False)
        return True

    def end(self, explosion=False):
        """
        End the minigame and calculate results

        Args:
            explosion: Whether brew exploded
        """
        self.active = False

        if explosion:
            self.result = {
                "success": False,
                "progress": 0.0,
                "quality": "Complete Failure",
                "message": "The brew exploded!",
                "materials_lost": 0.75  # 75% loss on explosion
            }
            return

        # Calculate final quality based on total progress
        progress = self.total_progress

        if progress < 0.25:
            quality = "Complete Failure"
            success = False
            materials_lost = 0.5
            duration_mult = 0.0
            effect_mult = 0.0
        elif progress < 0.50:
            quality = "Weak Success"
            success = True
            materials_lost = 0.0
            duration_mult = 0.5
            effect_mult = 0.5
        elif progress < 0.75:
            quality = "Standard Success"
            success = True
            materials_lost = 0.0
            duration_mult = 0.75
            effect_mult = 0.75
        elif progress < 0.90:
            quality = "Quality Success"
            success = True
            materials_lost = 0.0
            duration_mult = 1.0
            effect_mult = 1.0
        elif progress < 0.99:
            quality = "Superior Success"
            success = True
            materials_lost = 0.0
            duration_mult = 1.2
            effect_mult = 1.1
        else:  # >= 0.99
            quality = "Perfect Success"
            success = True
            materials_lost = 0.0
            duration_mult = 1.5
            effect_mult = 1.25

        # Apply skill buff quality bonus (empower/elevate)
        if self.buff_quality_bonus > 0:
            duration_mult *= (1.0 + self.buff_quality_bonus)
            effect_mult *= (1.0 + self.buff_quality_bonus)

        self.result = {
            "success": success,
            "progress": progress,
            "quality": quality,
            "duration_mult": duration_mult,
            "effect_mult": effect_mult,
            "materials_lost": materials_lost,
            "message": f"{quality}! Duration: {int(duration_mult*100)}%, Effect: {int(effect_mult*100)}%"
        }

    def get_state(self):
        """Get current minigame state for rendering"""
        return {
            "active": self.active,
            "current_ingredient_index": self.current_ingredient_index,
            "total_ingredients": len(self.ingredients),
            "current_reaction": self.current_reaction.get_state() if self.current_reaction else None,
            "locked_reactions": [r.get_state() for r in self.locked_reactions],
            "total_progress": self.total_progress,
            "time_left": self.time_left,
            "result": self.result
        }


class AlchemyCrafter:
    """
    Main alchemy crafting interface

    Handles:
    - Recipe loading from JSON
    - Material validation
    - Instant crafting (skip minigame)
    - Minigame crafting (gradient success)
    """

    def __init__(self):
        """Initialize alchemy crafter"""
        self.recipes = {}
        self.placements = {}
        self.load_recipes()
        self.load_placements()

    def load_recipes(self):
        """Load alchemy recipes from JSON files"""
        possible_paths = [
            "../recipes.JSON/recipes-alchemy-1.json",
            "recipes.JSON/recipes-alchemy-1.json",
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
            print(f"[Alchemy] Loaded {len(self.recipes)} recipes")
        else:
            print("[Alchemy] WARNING: No recipes loaded")

    
    def load_placements(self):
        """Load placement data from JSON files"""
        possible_paths = [
            "../placements.JSON/placements-alchemy-1.JSON",
            "placements.JSON/placements-alchemy-1.JSON",
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
            print(f"[Alchemy] Loaded {len(self.placements)} placements")

    def get_placement(self, recipe_id):
        """Get placement pattern for a recipe"""
        return self.placements.get(recipe_id)

    def can_craft(self, recipe_id, inventory):
        """
        Check if recipe can be crafted with given inventory
        Also checks rarity uniformity (all materials must be same rarity)
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

    def craft_instant(self, recipe_id, inventory, item_metadata=None):
        """
        Instant craft (no minigame) - produces base T-level output

        Args:
            recipe_id: Recipe ID to craft
            inventory: Dict of {material_id: quantity} (will be modified)
            item_metadata: Optional dict of item metadata for category lookup

        Returns:
            dict: Result with outputId, quantity, success, rarity, effect_type, is_consumable
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

        # Determine output type and effect from tags
        from core.crafting_tag_processor import AlchemyTagProcessor
        recipe_tags = recipe.get('metadata', {}).get('tags', [])
        is_consumable = AlchemyTagProcessor.is_consumable(recipe_tags)
        effect_type = AlchemyTagProcessor.get_effect_type(recipe_tags)

        return {
            "success": True,
            "outputId": recipe['outputId'],
            "quantity": recipe['outputQty'],
            "duration_mult": 1.0,  # Base duration
            "effect_mult": 1.0,  # Base effect
            "rarity": input_rarity,
            "is_consumable": is_consumable,  # Potion vs transmutation
            "effect_type": effect_type,  # Healing, buff, damage, etc.
            "message": f"Brewed ({input_rarity}) {'potion' if is_consumable else 'transmutation'}"
        }

    def create_minigame(self, recipe_id, buff_time_bonus=0.0, buff_quality_bonus=0.0):
        """Create an alchemy minigame for this recipe"""
        if recipe_id not in self.recipes:
            return None

        recipe = self.recipes[recipe_id]
        tier = recipe.get('stationTier', 1)

        return AlchemyMinigame(recipe, tier, buff_time_bonus, buff_quality_bonus)

    def craft_with_minigame(self, recipe_id, inventory, minigame_result, item_metadata=None):
        """
        Craft with minigame result - gradient success with rarity modifiers

        Args:
            recipe_id: Recipe ID to craft
            inventory: Dict of {material_id: quantity} (will be modified)
            minigame_result: Result dict from AlchemyMinigame
            item_metadata: Optional dict of item metadata for category lookup

        Returns:
            dict: Result with outputId, quality, multipliers, rarity, stats, effect_type, is_consumable
        """
        recipe = self.recipes[recipe_id]

        if not minigame_result.get('success'):
            # Failure - lose some materials
            materials_lost = minigame_result.get('materials_lost', 0.5)
            for inp in recipe['inputs']:
                loss = int(inp['quantity'] * materials_lost)
                inventory[inp['materialId']] = max(0, inventory[inp['materialId']] - loss)

            return {
                "success": False,
                "message": minigame_result.get('message', 'Brewing failed'),
                "materials_lost": True
            }

        # Success - deduct full materials
        for inp in recipe['inputs']:
            inventory[inp['materialId']] -= inp['quantity']

        # Detect input rarity
        inputs = recipe.get('inputs', [])
        _, input_rarity, _ = rarity_system.check_rarity_uniformity(inputs)

        # Convert multipliers to stats
        tier = recipe.get('stationTier', recipe.get('stationTierRequired', 1))
        duration_mult = minigame_result.get('duration_mult', 1.0)
        effect_mult = minigame_result.get('effect_mult', 1.0)

        base_stats = {
            "potency": int(100 * effect_mult),  # Effect strength
            "duration": int(100 * duration_mult),  # How long it lasts
            "quality": 100 + (tier * 10)  # Base quality from tier
        }

        # Get item category and apply rarity modifiers
        output_id = recipe['outputId']
        if item_metadata is None:
            item_metadata = {}

        item_category = rarity_system.get_item_category(output_id, item_metadata)
        modified_stats = rarity_system.apply_rarity_modifiers(base_stats, item_category, input_rarity)

        # Determine output type and effect from tags
        from core.crafting_tag_processor import AlchemyTagProcessor
        recipe_tags = recipe.get('metadata', {}).get('tags', [])
        is_consumable = AlchemyTagProcessor.is_consumable(recipe_tags)
        effect_type = AlchemyTagProcessor.get_effect_type(recipe_tags)

        return {
            "success": True,
            "outputId": output_id,
            "quantity": recipe['outputQty'],
            "quality": minigame_result.get('quality', 'Standard'),
            "duration_mult": duration_mult,
            "effect_mult": effect_mult,
            "rarity": input_rarity,
            "stats": modified_stats,
            "is_consumable": is_consumable,  # Potion vs transmutation
            "effect_type": effect_type,  # Healing, buff, damage, etc.
            "message": f"Brewed {input_rarity} {'potion' if is_consumable else 'transmutation'}! {minigame_result.get('message', '')}"
        }

    def get_recipe(self, recipe_id):
        """Get recipe by ID"""
        return self.recipes.get(recipe_id)

    def get_all_recipes(self):
        """Get all loaded recipes"""
        return self.recipes

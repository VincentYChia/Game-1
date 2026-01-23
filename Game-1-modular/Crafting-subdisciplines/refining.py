"""
Refining Crafting Subdiscipline

Framework:
- Python module ready for main.py integration
- Loads recipes from JSON files
- Optional minigame (lockpicking-style cylinder alignment)
- Difficulty based on material tier points × diversity multiplier

Difficulty System (v2):
- Material points: 2^(tier-1) × quantity per material
- Diversity multiplier: 1.0 + (unique_materials - 1) × 0.1
- Total difficulty = material_points × diversity_multiplier
- Higher difficulty = harder minigame = better potential rewards

Minigame: Lockpicking-style timing game
- Watch rotating cylinders align with target zones
- Press key when aligned (spacebar or number keys)
- All-or-nothing success (no partial completion)
- Cylinder count and timing window scale with difficulty

Failure Penalty System:
- Low difficulty: 30% material loss
- High difficulty: 90% material loss
- Scales linearly with difficulty points
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

    Difficulty System (v2):
    - Difficulty calculated from material tier point values × diversity multiplier
    - More unique materials = harder (complex reactions)
    - Higher points = harder minigame = better potential rewards
    """

    def __init__(self, recipe, buff_time_bonus=0.0, buff_quality_bonus=0.0):
        """
        Initialize refining minigame

        Args:
            recipe: Recipe dict from JSON (includes inputs for difficulty calculation)
            buff_time_bonus: Skill buff bonus to time limit (0.0-1.0+)
            buff_quality_bonus: Skill buff bonus to quality (0.0-1.0+)
        """
        self.recipe = recipe
        self.buff_time_bonus = buff_time_bonus
        self.buff_quality_bonus = buff_quality_bonus

        # Calculate difficulty from materials using new system
        self._setup_difficulty_from_materials()

        # Store speed bonus for spinner speed reduction (NOT for time limit!)
        # Speed bonus slows down spinner rotation, making timing easier
        # Formula: effective_speed = base_speed / (1.0 + speed_bonus)
        self.speed_bonus = self.buff_time_bonus
        if self.speed_bonus > 0:
            print(f"⚡ Speed bonus: +{self.speed_bonus*100:.0f}% (slows spinner rotation)")

        # Game state
        self.active = False
        self.cylinders = []
        self.current_cylinder = 0
        self.aligned_cylinders = []
        self.failed_attempts = 0
        self.time_left = self.time_limit
        self.result = None
        self.feedback_timer = 0  # For visual/audio feedback

    def _setup_difficulty_from_materials(self):
        """
        Setup difficulty parameters based on material tier points × diversity.

        Uses core.difficulty_calculator for centralized calculation.
        Falls back to legacy tier-based system if calculator unavailable.
        """
        try:
            from core.difficulty_calculator import (
                calculate_refining_difficulty,
                get_legacy_refining_params,
                get_difficulty_description
            )

            # Calculate difficulty from recipe materials with diversity
            params = calculate_refining_difficulty(self.recipe)

            # Store for reward calculation
            self.difficulty_points = params['difficulty_points']
            self.diversity_multiplier = params.get('diversity_multiplier', 1.0)

            # Apply parameters
            self.cylinder_count = int(params['cylinder_count'])
            self.timing_window = params['timing_window']
            self.rotation_speed = params['rotation_speed']
            self.allowed_failures = int(params['allowed_failures'])
            self.time_limit = int(params['time_limit'])
            self.multi_speed = params.get('multi_speed', False)

            # Log difficulty info
            difficulty_desc = get_difficulty_description(self.difficulty_points)
            print(f"⚗️ Refining difficulty: {difficulty_desc} ({self.difficulty_points:.1f} points)")
            print(f"   Cylinders: {self.cylinder_count}, Window: {self.timing_window:.2f}s, Diversity: {self.diversity_multiplier:.1f}x")

        except ImportError:
            # Fallback to legacy tier-based system
            print("⚠️ Difficulty calculator not available, using legacy tier system")
            self._setup_difficulty_legacy()

    def _setup_difficulty_legacy(self):
        """
        Legacy difficulty setup based on station tier only.
        Used as fallback when difficulty_calculator is unavailable.
        """
        tier = self.recipe.get('stationTier', 1)

        try:
            from core.difficulty_calculator import get_legacy_refining_params
            params = get_legacy_refining_params(tier)
        except ImportError:
            # Hardcoded fallback
            tier_configs = {
                1: {'time_limit': 45, 'cylinder_count': 3, 'timing_window': 0.8,
                    'rotation_speed': 1.0, 'allowed_failures': 2, 'multi_speed': False,
                    'difficulty_points': 5, 'diversity_multiplier': 1.0},
                2: {'time_limit': 30, 'cylinder_count': 6, 'timing_window': 0.5,
                    'rotation_speed': 1.3, 'allowed_failures': 1, 'multi_speed': False,
                    'difficulty_points': 20, 'diversity_multiplier': 1.0},
                3: {'time_limit': 20, 'cylinder_count': 10, 'timing_window': 0.3,
                    'rotation_speed': 1.6, 'allowed_failures': 0, 'multi_speed': False,
                    'difficulty_points': 50, 'diversity_multiplier': 1.0},
                4: {'time_limit': 15, 'cylinder_count': 15, 'timing_window': 0.2,
                    'rotation_speed': 2.0, 'allowed_failures': 0, 'multi_speed': True,
                    'difficulty_points': 80, 'diversity_multiplier': 1.0},
            }
            params = tier_configs.get(tier, tier_configs[1])

        self.difficulty_points = params.get('difficulty_points', tier * 20)
        self.diversity_multiplier = params.get('diversity_multiplier', 1.0)
        self.cylinder_count = params.get('cylinder_count', 3)
        self.timing_window = params.get('timing_window', 0.8)
        self.rotation_speed = params.get('rotation_speed', 1.0)
        self.allowed_failures = params.get('allowed_failures', 2)
        self.time_limit = params.get('time_limit', 45)
        self.multi_speed = params.get('multi_speed', False)

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

            # For high difficulty (multi_speed enabled), vary rotation speeds
            if self.multi_speed and i % 2 == 0:
                base_speed = self.rotation_speed * 0.7
            elif self.multi_speed and i % 3 == 0:
                base_speed = self.rotation_speed * 1.3
            else:
                base_speed = self.rotation_speed

            # Apply speed bonus (slows down rotation)
            speed = base_speed / (1.0 + self.speed_bonus)

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

        # Capture angle when button pressed for feedback (red mark)
        angle = cylinder["angle"]

        # Store the attempt angle for visual feedback (red mark)
        cylinder["last_attempt_angle"] = angle

        target = cylinder["target_zone"]

        # Calculate angular distance (accounting for wraparound)
        distance = min(abs(angle - target), 360 - abs(angle - target))

        # Convert timing window from seconds to degrees
        window_degrees = self.timing_window * cylinder["speed"] * 360

        if distance <= window_degrees / 2:
            # SUCCESS! Stop rotation on this cylinder
            cylinder["aligned"] = True
            self.aligned_cylinders.append(self.current_cylinder)
            self.current_cylinder += 1
            self.feedback_timer = 0.3  # Show success feedback

            # Check if all cylinders aligned
            if self.current_cylinder >= self.cylinder_count:
                self.end(success=True)

            return True
        else:
            # FAILURE - keep spinner rotating, just show red mark
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
            print(f"🎯 Refining successful! ({self.current_cylinder} alignments, {self.failed_attempts} failures)")

            # Calculate earned/max points for crafted stats system
            earned_points = len(self.aligned_cylinders)  # Successful alignments
            max_points = self.cylinder_count  # Total cylinders

            self.result = {
                "success": True,
                "message": "Refinement successful!",
                "attempts": self.current_cylinder + self.failed_attempts,
                "quality_bonus": self.buff_quality_bonus,
                "difficulty_points": self.difficulty_points,
                "diversity_multiplier": self.diversity_multiplier,
                "earned_points": earned_points,
                "max_points": max_points
            }
        else:
            # Calculate tier-scaled material loss
            try:
                from core.reward_calculator import calculate_failure_penalty
                loss_fraction = calculate_failure_penalty(self.difficulty_points)
            except ImportError:
                loss_fraction = 0.5  # Fallback

            print(f"❌ Refining failed! {int(loss_fraction * 100)}% materials will be lost")

            # Calculate earned/max points for crafted stats system (even on failure)
            earned_points = len(self.aligned_cylinders)  # Partial credit
            max_points = self.cylinder_count

            self.result = {
                "success": False,
                "message": reason or "Refinement failed",
                "materials_lost": loss_fraction,
                "difficulty_points": self.difficulty_points,
                "earned_points": earned_points,
                "max_points": max_points
            }

    def get_state(self):
        """Get current minigame state for rendering

        Each cylinder dict contains:
        - angle: Current angle (0-360)
        - speed: Rotation speed
        - direction: Rotation direction (1 or -1)
        - aligned: Whether successfully aligned
        - target_zone: Target angle (0 for top)
        - last_attempt_angle: Angle where player pressed button (for visual feedback)
        """
        return {
            "active": self.active,
            "cylinders": self.cylinders,  # Contains last_attempt_angle for each cylinder
            "current_cylinder": self.current_cylinder,
            "aligned_count": len(self.aligned_cylinders),
            "total_cylinders": self.cylinder_count,
            "failed_attempts": self.failed_attempts,
            "allowed_failures": self.allowed_failures,
            "time_left": self.time_left,
            "result": self.result,
            "feedback_timer": self.feedback_timer,
            "timing_window": self.timing_window,
            "window_degrees": self.timing_window * self.rotation_speed * 360  # Visual window size
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
            "../recipes.JSON/recipes-tag-tests.JSON",  # TEST RECIPES
            "recipes.JSON/recipes-refining-1.json",
            "recipes.JSON/recipes-tag-tests.JSON",  # TEST RECIPES
        ]

        loaded_count = 0
        for path in possible_paths:
            try:
                with open(path, 'r') as f:
                    data = json.load(f)
                    recipe_list = data.get('recipes', [])
                    for recipe in recipe_list:
                        # Only load refining recipes
                        station_type = recipe.get('stationType', 'refining')
                        if station_type == 'refining':
                            self.recipes[recipe['recipeId']] = recipe
                            loaded_count += 1
            except FileNotFoundError:
                continue
            except Exception as e:
                print(f"[Refining] Error loading {path}: {e}")

        if self.recipes:
            print(f"[Refining] Loaded {loaded_count} recipes from {len(self.recipes)} total")
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
            # Backward compatible: support both 'itemId' (new) and 'materialId' (legacy)
            item_id = inp.get('itemId') or inp.get('materialId')
            if inventory.get(item_id, 0) < inp['quantity']:
                return False, f"Insufficient {item_id}"

        # Check rarity uniformity
        inputs = recipe.get('inputs', [])
        is_uniform, rarity, error_msg = rarity_system.check_rarity_uniformity(inputs)

        if not is_uniform:
            return False, error_msg

        return True, None

    def craft_instant(self, recipe_id, inventory):
        """
        Instant craft (no minigame) - produces base output with rarity upgrade and probabilistic tag bonuses

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
        # Fallback to 'common' if rarity is None (material not in database)
        input_rarity = input_rarity or 'common'

        # Deduct materials
        for inp in recipe['inputs']:
            # Backward compatible: support both 'itemId' (new) and 'materialId' (legacy)
            item_id = inp.get('itemId') or inp.get('materialId')
            inventory[item_id] -= inp['quantity']

        # Refining uses 'outputs' array instead of outputId/outputQty
        outputs = recipe.get('outputs', [])
        if outputs:
            output = outputs[0]  # Take first output
            # Backward compatible: support both 'itemId' and 'materialId' in outputs
            output_id = output.get('itemId') or output.get('materialId') or recipe.get('outputId', 'unknown')
            base_output_qty = output.get('quantity', recipe.get('outputQty', 1))
            base_output_rarity = output.get('rarity', input_rarity)
        else:
            # Fallback to old format
            output_id = recipe.get('outputId', 'unknown')
            base_output_qty = recipe.get('outputQty', 1)
            base_output_rarity = input_rarity

        # Apply rarity upgrade based on input quantity (4:1 ratio)
        # Calculate total input quantity from recipe
        total_input_qty = sum(inp['quantity'] for inp in inputs)

        # Map rarity tiers
        rarity_tiers = ['common', 'uncommon', 'rare', 'epic', 'legendary']
        current_tier_idx = rarity_tiers.index(input_rarity) if input_rarity in rarity_tiers else 0

        # Determine rarity upgrade based on input quantity (4:1 ratio per tier)
        rarity_upgrade = 0
        if total_input_qty >= 256:
            rarity_upgrade = 4  # +4 tiers
        elif total_input_qty >= 64:
            rarity_upgrade = 3  # +3 tiers
        elif total_input_qty >= 16:
            rarity_upgrade = 2  # +2 tiers
        elif total_input_qty >= 4:
            rarity_upgrade = 1  # +1 tier
        # If < 4, no upgrade (stays same rarity)

        output_rarity_idx = min(current_tier_idx + rarity_upgrade, len(rarity_tiers) - 1)
        base_upgraded_rarity = rarity_tiers[output_rarity_idx]

        # Apply probabilistic tag bonuses (crushing, grinding, purifying, alloying)
        from core.crafting_tag_processor import RefiningTagProcessor
        from core.tag_debug import get_tag_debugger

        recipe_tags = recipe.get('metadata', {}).get('tags', [])
        final_quantity, final_rarity = RefiningTagProcessor.calculate_final_output(
            base_output_qty, base_upgraded_rarity, recipe_tags
        )

        # Detect bonus procs for feedback
        bonus_yield_proc = (final_quantity > base_output_qty)
        quality_upgrade_proc = (final_rarity != base_upgraded_rarity)

        # Debug output
        debugger = get_tag_debugger()
        debugger.log_refining_bonuses(recipe_id, recipe_tags, base_output_qty, base_upgraded_rarity,
                                      final_quantity, final_rarity)

        message_parts = [f"Refined to {final_rarity}!"]
        if bonus_yield_proc:
            bonus_amt = final_quantity - base_output_qty
            message_parts.append(f"+{bonus_amt} bonus yield!")
        if quality_upgrade_proc:
            message_parts.append(f"Quality upgrade: {base_upgraded_rarity} → {final_rarity}!")

        print(f"[Refining Instant] {total_input_qty} {input_rarity} inputs -> {final_rarity} output (+{rarity_upgrade} tiers from qty)")

        return {
            "success": True,
            "outputId": output_id,
            "quantity": final_quantity,
            "rarity": final_rarity,
            "message": " ".join(message_parts)
        }

    def create_minigame(self, recipe_id, buff_time_bonus=0.0, buff_quality_bonus=0.0):
        """
        Create a refining minigame for this recipe

        Difficulty is now calculated from material tier points × diversity multiplier
        rather than station tier alone.

        Args:
            recipe_id: Recipe ID to craft
            buff_time_bonus: Skill buff bonus to time limit (0.0-1.0+)
            buff_quality_bonus: Skill buff bonus to quality (0.0-1.0+)

        Returns:
            RefiningMinigame instance or None if recipe not found
        """
        if recipe_id not in self.recipes:
            return None

        recipe = self.recipes[recipe_id]

        # Pass full recipe for material-based difficulty calculation
        return RefiningMinigame(recipe, buff_time_bonus, buff_quality_bonus)

    def craft_with_minigame(self, recipe_id, inventory, minigame_result, alloy_quality_bonus=0.0):
        """
        Craft with minigame result - all-or-nothing with probabilistic tag bonuses
        Refining outputs materials with rarity but NO stat bonuses

        Failure penalty scales with difficulty:
        - Low difficulty (T1): 30% material loss
        - High difficulty (T4): 90% material loss

        Args:
            recipe_id: Recipe ID to craft
            inventory: Dict of {material_id: quantity} (will be modified)
            minigame_result: Result dict from RefiningMinigame
            alloy_quality_bonus: Title bonus for chance-based rarity upgrade (0.0-1.0)

        Returns:
            dict: Result with outputId, quantity, rarity, success
        """
        recipe = self.recipes[recipe_id]

        if not minigame_result.get('success'):
            # Use tier-scaled material loss from minigame result
            loss_fraction = minigame_result.get('materials_lost', 0.5)

            materials_lost_detail = {}
            for inp in recipe['inputs']:
                # Backward compatible: support both 'itemId' (new) and 'materialId' (legacy)
                item_id = inp.get('itemId') or inp.get('materialId')
                loss = int(inp['quantity'] * loss_fraction)
                if loss > 0:
                    inventory[item_id] = max(0, inventory[item_id] - loss)
                    materials_lost_detail[item_id] = loss

            return {
                "success": False,
                "message": minigame_result.get('message', 'Refining failed'),
                "materials_lost": True,
                "materials_lost_detail": materials_lost_detail,
                "loss_percentage": int(loss_fraction * 100)
            }

        # Material consumption is handled by RecipeDatabase.consume_materials() in game_engine.py
        # This keeps the architecture clean with a single source of truth for inventory management

        # Detect input rarity (base rarity from input materials)
        inputs = recipe.get('inputs', [])
        _, input_rarity, _ = rarity_system.check_rarity_uniformity(inputs)
        # Fallback to 'common' if rarity is None (material not in database)
        input_rarity = input_rarity or 'common'

        # Debug: Show what materials and their rarities
        print(f"\n[Refining Minigame] Recipe: {recipe_id}")
        for inp in inputs:
            # Backward compatible: support both 'itemId' (new) and 'materialId' (legacy)
            mat_id = inp.get('itemId') or inp.get('materialId')
            mat_qty = inp.get('quantity')
            mat_rarity = rarity_system.get_material_rarity(mat_id) or 'common'
            print(f"  Input: {mat_qty}x {mat_id} (rarity: {mat_rarity})")
        print(f"  Detected uniform input rarity: {input_rarity}")

        # Handle outputs array format (refining uses outputs, not outputId)
        outputs = recipe.get('outputs', [])
        if outputs:
            output = outputs[0]
            # Backward compatible: support both 'itemId' and 'materialId' in outputs
            output_id = output.get('itemId') or output.get('materialId') or recipe.get('outputId', 'unknown')
            base_output_qty = output.get('quantity', recipe.get('outputQty', 1))
            base_output_rarity = output.get('rarity', input_rarity)
        else:
            output_id = recipe.get('outputId', 'unknown')
            base_output_qty = recipe.get('outputQty', 1)
            base_output_rarity = input_rarity

        # Refining rarity upgrade based on INPUT QUANTITY (4:1 ratio)
        # 4 inputs = +1 rarity tier (common -> uncommon)
        # 16 inputs = +2 rarity tiers (common -> rare, skipping uncommon)
        # 64 inputs = +3 rarity tiers (common -> epic)
        # 256 inputs = +4 rarity tiers (common -> legendary)
        rarity_tiers = ['common', 'uncommon', 'rare', 'epic', 'legendary']
        current_tier_idx = rarity_tiers.index(input_rarity) if input_rarity in rarity_tiers else 0

        # Calculate total input quantity
        total_input_qty = sum(inp['quantity'] for inp in inputs)

        # Determine rarity upgrade based on input quantity (4:1 ratio per tier)
        rarity_upgrade = 0
        if total_input_qty >= 256:
            rarity_upgrade = 4  # +4 tiers
        elif total_input_qty >= 64:
            rarity_upgrade = 3  # +3 tiers
        elif total_input_qty >= 16:
            rarity_upgrade = 2  # +2 tiers
        elif total_input_qty >= 4:
            rarity_upgrade = 1  # +1 tier

        output_rarity_idx = min(current_tier_idx + rarity_upgrade, len(rarity_tiers) - 1)
        base_upgraded_rarity = rarity_tiers[output_rarity_idx]

        # Apply minigame quality modifier to alloy quality bonus
        # quality >= 50: boost alloy bonus (+0 to +100%)
        # quality < 50: reduce alloy bonus (down to -50%)
        earned_points = minigame_result.get('earned_points', 50)
        max_points = minigame_result.get('max_points', 100)
        quality = int((earned_points / max_points) * 100) if max_points > 0 else 50

        # Calculate quality multiplier (-0.5 to +1.0)
        # quality 100 = +100% bonus, quality 50 = +0%, quality 0 = -50% bonus
        quality_mult = (quality - 50) / 50.0  # -1.0 to +1.0
        adjusted_alloy_bonus = alloy_quality_bonus * (1.0 + quality_mult)
        adjusted_alloy_bonus = max(0.0, min(1.0, adjusted_alloy_bonus))  # Clamp to 0-100%

        # Apply alloyQuality bonus (chance-based rarity upgrade)
        # Each title bonus point (e.g., 25% = 0.25) gives a 25% chance for +1 rarity tier
        # Quality modifier can increase or decrease this chance
        if adjusted_alloy_bonus > 0 and output_rarity_idx < len(rarity_tiers) - 1:
            import random
            if random.random() < adjusted_alloy_bonus:
                output_rarity_idx += 1
                base_upgraded_rarity = rarity_tiers[output_rarity_idx]
                print(f"  🎲 ALLOY QUALITY PROC! +1 rarity tier (chance: {adjusted_alloy_bonus*100:.0f}% from {alloy_quality_bonus*100:.0f}% base, quality: {quality}/100)")

        # Apply probabilistic tag bonuses (crushing, grinding, purifying, alloying)
        from core.crafting_tag_processor import RefiningTagProcessor
        from core.tag_debug import get_tag_debugger

        recipe_tags = recipe.get('metadata', {}).get('tags', [])
        final_quantity, final_rarity = RefiningTagProcessor.calculate_final_output(
            base_output_qty, base_upgraded_rarity, recipe_tags
        )

        # Detect bonus procs for feedback
        bonus_yield_proc = (final_quantity > base_output_qty)
        quality_upgrade_proc = (final_rarity != base_upgraded_rarity)

        # Debug output
        debugger = get_tag_debugger()
        debugger.log_refining_bonuses(recipe_id, recipe_tags, base_output_qty, base_upgraded_rarity,
                                      final_quantity, final_rarity)

        print(f"  Rarity calculation: {total_input_qty} inputs -> +{rarity_upgrade} tiers from qty")
        if bonus_yield_proc:
            bonus_amt = final_quantity - base_output_qty
            print(f"  🎲 BONUS YIELD! +{bonus_amt} (from tag bonuses)")
        if quality_upgrade_proc:
            print(f"  ✨ QUALITY UPGRADE! {base_upgraded_rarity} → {final_rarity} (from tag bonuses)")
        print(f"  Final output: {final_quantity}x {output_id} ({input_rarity} -> {final_rarity})\n")

        message_parts = [f"Refined to {final_rarity} quality!"]
        if bonus_yield_proc:
            bonus_amt = final_quantity - base_output_qty
            message_parts.append(f"+{bonus_amt} bonus yield!")
        if quality_upgrade_proc:
            message_parts.append(f"Quality upgrade: {base_upgraded_rarity} → {final_rarity}!")

        result = {
            "success": True,
            "outputId": output_id,
            "quantity": final_quantity,
            "rarity": final_rarity,
            "message": " ".join(message_parts)
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

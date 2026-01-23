"""
Alchemy Crafting Subdiscipline

Framework:
- Python module ready for main.py integration
- Loads recipes from JSON files
- Optional minigame (reaction chain management)
- Difficulty based on material tier points × diversity × volatility

Difficulty System (v2):
- Material points: tier × quantity per material (LINEAR)
- Diversity multiplier: 1.0 + (unique_materials - 1) × 0.1
- Tier exponential: 1.2^avg_tier modifier
- Volatility: Vowel-based modifier (more vowels = more volatile)
- Higher difficulty = faster reactions, narrower sweet spots

Minigame: Reaction chain management - reading visual cues
- Watch reactions grow through stages
- Add next ingredient at optimal time (CHAIN)
- Or stabilize to end process
- Gradient success system (progress-based quality)

Failure Penalty System:
- Low difficulty: 30% material loss
- High difficulty: 90% material loss
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

    def __init__(self, ingredient_id, ingredient_type="moderate", speed_bonus=0.0, max_quality=0.30):
        """
        Initialize reaction

        Args:
            ingredient_id: Ingredient material ID
            ingredient_type: Reaction behavior type (stable, moderate, volatile, legendary)
            speed_bonus: Speed bonus multiplier (0.0-1.0+) - slows reaction timing
            max_quality: Dynamic max quality for this ingredient (0.0-1.0, e.g., 0.35 = 35%)
        """
        self.ingredient_id = ingredient_id
        self.ingredient_type = ingredient_type
        self.speed_bonus = speed_bonus
        self.max_quality = max_quality  # Dynamic based on vowel contribution

        # Reaction state
        self.stage = 1  # 1-5
        self.progress = 0.0  # 0.0-1.0 through current stage
        self.locked_quality = None  # Quality when chained/stabilized

        # Calculate secret value and oscillation pattern
        self.secret_value = self._calculate_secret_value(ingredient_id)
        self.oscillation_count = self._assign_oscillation_pattern(self.secret_value)

        # Setup timing based on ingredient type (applies speed bonus)
        self._setup_timing()

        # Visual state (for rendering)
        self.size = 0.0  # Bubble size
        self.glow = 0.0  # Glow intensity
        self.color_shift = 0.0  # Color variation

    def _calculate_secret_value(self, ingredient_id):
        """
        Calculate secret value for ingredient based on vowel count.

        Uses same vowel-counting method as volatility calculation.
        This creates unpredictable oscillation patterns.

        Returns:
            float: Secret value 0.0-1.0
        """
        vowels = set('aeiouAEIOU')
        total_chars = 0
        vowel_count = 0

        for char in ingredient_id:
            if char.isalpha():
                total_chars += 1
                if char in vowels:
                    vowel_count += 1

        if total_chars == 0:
            return 0.5  # Default middle value

        # Normalize vowel ratio to 0.0-1.0
        # Normal vowel ratio is ~40%, normalize around that
        vowel_ratio = vowel_count / total_chars
        secret_value = max(0.0, min(1.0, (vowel_ratio - 0.2) * 2.0))
        return secret_value

    def _assign_oscillation_pattern(self, secret_value):
        """
        Assign oscillation count based on secret value.

        Distribution (NEW):
        - 25% get 1 oscillation (simple up-down)
        - 40% get 2 oscillations (two up-down cycles)
        - 35% get 3 oscillations (three up-down cycles)

        Args:
            secret_value: 0.0-1.0

        Returns:
            int: Number of oscillation cycles (1, 2, or 3)
        """
        if secret_value < 0.25:
            return 1  # 25% of ingredients
        elif secret_value < 0.65:  # 0.25 + 0.40
            return 2  # 40% of ingredients
        else:
            return 3  # 35% of ingredients

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

        # Apply speed bonus to extend all stage durations
        # Speed bonus slows reaction: duration = base * (1.0 + bonus)
        if self.speed_bonus > 0:
            multiplier = 1.0 + self.speed_bonus
            self.stage_durations = [d * multiplier for d in self.stage_durations]
            self.sweet_spot_duration *= multiplier

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
        Get quality contribution if chained/stabilized now (NEW OSCILLATION SYSTEM)

        Quality now oscillates based on ingredient's secret value:
        - 1 oscillation: Simple up-down pattern (25% of ingredients)
        - 2 oscillations: Two up-down cycles (40% of ingredients)
        - 3 oscillations: Three up-down cycles (35% of ingredients)

        Max value always appears on the LAST oscillation peak.

        Each ingredient has a DYNAMIC max quality based on vowel contribution,
        so players can't just click at ~30% for all ingredients.

        Returns:
            float: Progress contribution (0.0 to max_quality, with max on last peak)
        """
        import math

        if self.stage >= 6:
            return 0.0  # Explosion

        # Calculate normalized progress through entire reaction (0.0 to 1.0)
        # Stage 1 progress 0.0 = 0.0, Stage 5 progress 1.0 = 1.0
        total_progress = (self.stage - 1 + self.progress) / 5.0

        # Create oscillating value based on oscillation_count
        # Use sine waves with increasing amplitude (last peak is highest)
        oscillations = self.oscillation_count

        # Calculate which oscillation cycle we're in
        cycle_progress = total_progress * oscillations  # 0.0 to oscillation_count
        current_cycle = int(cycle_progress)
        cycle_fraction = cycle_progress - current_cycle  # 0.0 to 1.0 within cycle

        # Each cycle is a sine wave (0 -> peak -> 0)
        # Sine wave: 0 at 0, peak at 0.5, 0 at 1.0
        cycle_value = math.sin(cycle_fraction * math.pi)

        # Amplitude increases with each cycle (last peak is highest)
        # Cycle 0: 60% amplitude, Cycle 1: 80% amplitude, Cycle 2+: 100% amplitude
        if oscillations == 1:
            amplitude = 1.0  # Single cycle always 100%
        else:
            cycle_index = min(current_cycle, oscillations - 1)
            amplitude = 0.6 + (0.4 * cycle_index / (oscillations - 1))

        # Scale to this ingredient's dynamic max quality
        # Base quality increases slightly with overall progress
        base_fraction = 0.15 + total_progress * 0.30  # 15% to 45% of max
        oscillation_fraction = cycle_value * amplitude * 0.55  # 0% to 55% of max

        quality_fraction = base_fraction + oscillation_fraction  # Total: 0% to 100% of max

        final_quality = quality_fraction * self.max_quality

        return min(self.max_quality, max(0.0, final_quality))

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

    def __init__(self, recipe, buff_time_bonus=0.0, buff_quality_bonus=0.0):
        """
        Initialize alchemy minigame

        Args:
            recipe: Recipe dict from JSON (includes inputs for difficulty calculation)
            buff_time_bonus: Skill buff bonus to time limit (0.0-1.0+)
            buff_quality_bonus: Skill buff bonus to quality (0.0-1.0+)
        """
        self.recipe = recipe
        self.buff_time_bonus = buff_time_bonus
        self.buff_quality_bonus = buff_quality_bonus
        self.ingredients = recipe.get('inputs', [])

        # Track attempts for first-try bonus
        self.attempt = 1

        # Difficulty scaling from materials
        self._setup_difficulty_from_materials()

        # Store speed bonus for reaction timing (NOT for time limit!)
        # Speed bonus slows down reaction progression, giving more time to react
        # Formula: effective_duration = base_duration * (1.0 + speed_bonus)
        self.speed_bonus = self.buff_time_bonus
        if self.speed_bonus > 0:
            print(f"⚡ Speed bonus: +{self.speed_bonus*100:.0f}% (slows reaction timing)")

        # Calculate dynamic max quality percentages based on vowel contribution
        self._calculate_ingredient_max_qualities()

        # Game state
        self.active = False
        self.current_ingredient_index = 0
        self.current_reaction = None
        self.locked_reactions = []
        self.total_progress = 0.0
        self.explosions = 0
        self.time_left = self.time_limit
        self.result = None

    def _calculate_ingredient_max_qualities(self):
        """
        Calculate dynamic max quality for each ingredient based on vowel contribution.

        Each ingredient's max quality = (its vowels / total vowels) * 100%
        This ensures:
        - Total max quality across all ingredients = 100%
        - Each ingredient has a unique, unpredictable max
        - Player can't just click at ~30% for all ingredients
        """
        vowels = set('aeiouAEIOU')

        # Calculate vowel count for each ingredient
        ingredient_vowel_counts = []
        total_vowels = 0

        for ingredient in self.ingredients:
            item_id = ingredient.get('itemId') or ingredient.get('materialId', '')
            vowel_count = 0

            for char in item_id:
                if char in vowels:
                    vowel_count += 1

            ingredient_vowel_counts.append(vowel_count)
            total_vowels += vowel_count

        # Assign max quality percentages based on contribution
        self.ingredient_max_qualities = []

        if total_vowels == 0:
            # Fallback: equal distribution if no vowels
            equal_share = 1.0 / max(1, len(self.ingredients))
            self.ingredient_max_qualities = [equal_share] * len(self.ingredients)
        else:
            for vowel_count in ingredient_vowel_counts:
                # Max quality = contribution to total (as fraction, e.g., 0.35 for 35%)
                max_quality = vowel_count / total_vowels
                self.ingredient_max_qualities.append(max_quality)

        # Debug output
        print(f"[Alchemy] Dynamic max qualities: {[f'{q*100:.1f}%' for q in self.ingredient_max_qualities]}")

    def _setup_difficulty_from_materials(self):
        """
        Setup difficulty parameters based on material tier points and volatility.

        Uses the centralized difficulty calculator for consistent scaling.
        """
        try:
            from core.difficulty_calculator import calculate_alchemy_difficulty
            params = calculate_alchemy_difficulty(self.recipe)

            self.difficulty_points = params['difficulty_points']
            self.difficulty_tier = params.get('difficulty_tier', 'common')
            self.time_limit = params['time_limit']
            self.reaction_count = params['reaction_count']
            self.sweet_spot_duration = params['sweet_spot_duration']
            self.stage_duration = params['stage_duration']
            self.false_peaks = params['false_peaks']
            self.volatility = params.get('volatility', 0.0)
            self.tier_modifier = params.get('tier_modifier', 1.0)

            # Map difficulty to ingredient types
            self._assign_ingredient_types()

            print(f"[Alchemy] Difficulty: {self.difficulty_points:.1f} pts ({self.difficulty_tier})")
            print(f"         Volatility: {self.volatility:.2f}, Tier mod: {self.tier_modifier:.2f}")

        except ImportError:
            # Fallback to legacy tier-based system
            tier = self.recipe.get('stationTier', 1)
            self._setup_difficulty_legacy(tier)

    def _assign_ingredient_types(self):
        """
        Assign ingredient types based on difficulty and volatility.
        """
        num_ingredients = len(self.ingredients)
        self.ingredient_types = []

        # Base type distribution based on difficulty tier
        if self.difficulty_tier == 'common':
            base_types = ['stable', 'stable', 'moderate']
        elif self.difficulty_tier == 'uncommon':
            base_types = ['stable', 'moderate', 'moderate']
        elif self.difficulty_tier == 'rare':
            base_types = ['moderate', 'moderate', 'volatile']
        elif self.difficulty_tier == 'epic':
            base_types = ['moderate', 'volatile', 'volatile']
        else:  # legendary
            base_types = ['volatile', 'volatile', 'legendary']

        # Assign types to each ingredient
        for i in range(num_ingredients):
            if i < len(base_types):
                ing_type = base_types[i]
            else:
                # For extra ingredients, use volatility to determine type
                if self.volatility > 0.7:
                    ing_type = 'legendary'
                elif self.volatility > 0.4:
                    ing_type = 'volatile'
                elif self.volatility > 0.2:
                    ing_type = 'moderate'
                else:
                    ing_type = 'stable'
            self.ingredient_types.append(ing_type)

    def _setup_difficulty_legacy(self, tier):
        """Legacy tier-based difficulty for backward compatibility."""
        self.difficulty_points = tier * 15
        self.difficulty_tier = ['common', 'uncommon', 'rare', 'epic'][min(tier - 1, 3)]
        self.volatility = 0.0
        self.tier_modifier = 1.0

        if tier == 1:
            self.time_limit = 60
            self.ingredient_types = ["stable", "stable", "moderate"]
        elif tier == 2:
            self.time_limit = 45
            self.ingredient_types = ["stable", "moderate", "moderate"]
        elif tier == 3:
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

        # Get dynamic max quality for this ingredient
        if self.current_ingredient_index < len(self.ingredient_max_qualities):
            max_quality = self.ingredient_max_qualities[self.current_ingredient_index]
        else:
            max_quality = 0.30  # Fallback

        # Backward compatible: support both 'itemId' (new) and 'materialId' (legacy)
        item_id = ingredient.get('itemId') or ingredient.get('materialId')
        self.current_reaction = AlchemyReaction(item_id, ing_type, self.speed_bonus, max_quality)

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

            # Check for explosion (NEW BEHAVIOR: Add 10% and move to next ingredient)
            if self.current_reaction.stage >= 6:
                print(f"   💥 Ingredient {self.current_ingredient_index + 1} failed! +10% progress")
                self.explosions += 1
                self.total_progress += 0.10  # Add 10% for failed ingredient
                self.locked_reactions.append(self.current_reaction)  # Keep for tracking

                # Move to next ingredient (encourages experimentation)
                self.current_ingredient_index += 1
                if self.current_ingredient_index < len(self.ingredients):
                    self._start_next_ingredient()
                else:
                    # No more ingredients - auto stabilize
                    self.stabilize()

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

        # Get difficulty points for tier-scaled penalties
        difficulty_points = getattr(self, 'difficulty_points', 30)

        if explosion:
            self.explosions += 1
            # Use tier-scaled penalty for explosion
            try:
                from core.reward_calculator import calculate_failure_penalty
                materials_lost = min(0.9, calculate_failure_penalty(difficulty_points) + 0.1)  # Extra 10% for explosion
            except ImportError:
                materials_lost = 0.75

            self.result = {
                "success": False,
                "progress": 0.0,
                "quality": "Complete Failure",
                "message": "The brew exploded!",
                "materials_lost": materials_lost,
                "difficulty_points": difficulty_points,
                "explosions": self.explosions,
                "earned_points": 0,
                "max_points": 100
            }
            return

        # Calculate final quality based on total progress
        progress = self.total_progress

        # Use reward calculator for consistent quality tiers
        try:
            from core.reward_calculator import calculate_alchemy_rewards, calculate_failure_penalty

            performance = {
                'chains_completed': len(self.locked_reactions),
                'total_chains': len(self.ingredients),
                'avg_timing_score': int(progress * 100),
                'explosions': self.explosions,
                'attempt': self.attempt
            }

            rewards = calculate_alchemy_rewards(difficulty_points, performance)

            if progress < 0.25:
                success = False
                materials_lost = calculate_failure_penalty(difficulty_points)
                quality = "Complete Failure"
                duration_mult = 0.0
                effect_mult = 0.0
            else:
                success = True
                materials_lost = 0.0
                quality = rewards['quality_tier']
                duration_mult = rewards['duration_multiplier']
                effect_mult = rewards['potency_multiplier']

        except ImportError:
            # Fallback to legacy quality calculation
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

        # Calculate earned/max points for crafted stats system
        # Progress is 0.0-1.0, scale to 0-100 for consistency with other minigames
        earned_points = int(progress * 100)
        max_points = 100  # Theoretical max (all ingredients at max quality)

        self.result = {
            "success": success,
            "progress": progress,
            "quality": quality,
            "quality_tier": quality,  # Alias for consistency
            "duration_mult": duration_mult,
            "effect_mult": effect_mult,
            "materials_lost": materials_lost,
            "difficulty_points": difficulty_points,
            "explosions": self.explosions,
            "earned_points": earned_points,
            "max_points": max_points,
            "message": f"Quality: {earned_points}/{max_points} points | Duration: {int(duration_mult*100)}%, Effect: {int(effect_mult*100)}%"
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
            "../recipes.JSON/recipes-tag-tests.JSON",  # TEST RECIPES
            "recipes.JSON/recipes-alchemy-1.json",
            "recipes.JSON/recipes-tag-tests.JSON",  # TEST RECIPES
        ]

        loaded_count = 0
        for path in possible_paths:
            try:
                with open(path, 'r') as f:
                    data = json.load(f)
                    recipe_list = data.get('recipes', [])
                    for recipe in recipe_list:
                        # Only load alchemy recipes
                        station_type = recipe.get('stationType', 'alchemy')
                        if station_type == 'alchemy':
                            self.recipes[recipe['recipeId']] = recipe
                            loaded_count += 1
            except FileNotFoundError:
                continue
            except Exception as e:
                print(f"[Alchemy] Error loading {path}: {e}")

        if self.recipes:
            print(f"[Alchemy] Loaded {loaded_count} recipes from {len(self.recipes)} total")
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
        # Fallback to 'common' if rarity is None (material not in database)
        input_rarity = input_rarity or 'common'

        # Deduct materials
        for inp in recipe['inputs']:
            # Backward compatible: support both 'itemId' (new) and 'materialId' (legacy)
            item_id = inp.get('itemId') or inp.get('materialId')
            inventory[item_id] -= inp['quantity']

        # Determine output type and effect from tags
        from core.crafting_tag_processor import AlchemyTagProcessor
        from core.tag_debug import get_tag_debugger

        recipe_tags = recipe.get('metadata', {}).get('tags', [])
        is_consumable = AlchemyTagProcessor.is_consumable(recipe_tags)
        effect_type = AlchemyTagProcessor.get_effect_type(recipe_tags)

        # Debug output
        debugger = get_tag_debugger()
        debugger.log_alchemy_detection(recipe_id, recipe_tags, is_consumable, effect_type)

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
        """
        Create an alchemy minigame for this recipe

        Difficulty is now calculated from material tier points × diversity × volatility
        rather than station tier alone.

        Args:
            recipe_id: Recipe ID to craft
            buff_time_bonus: Skill buff bonus to time limit (0.0-1.0+)
            buff_quality_bonus: Skill buff bonus to quality (0.0-1.0+)

        Returns:
            AlchemyMinigame instance or None if recipe not found
        """
        if recipe_id not in self.recipes:
            return None

        recipe = self.recipes[recipe_id]

        # Pass full recipe for material-based difficulty calculation
        return AlchemyMinigame(recipe, buff_time_bonus, buff_quality_bonus)

    def craft_with_minigame(self, recipe_id, inventory, minigame_result, item_metadata=None):
        """
        Craft with minigame result - gradient success with rarity modifiers

        Failure penalty scales with difficulty:
        - Low difficulty (Common): 30% material loss
        - High difficulty (Legendary): 90% material loss
        - Explosion adds extra 10% penalty

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
            # Failure - use tier-scaled material loss from minigame result
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
                "message": minigame_result.get('message', 'Brewing failed'),
                "materials_lost": True,
                "materials_lost_detail": materials_lost_detail,
                "loss_percentage": int(loss_fraction * 100),
                "explosions": minigame_result.get('explosions', 0)
            }

        # Material consumption is handled by RecipeDatabase.consume_materials() in game_engine.py
        # This keeps the architecture clean with a single source of truth for inventory management

        # Detect input rarity
        inputs = recipe.get('inputs', [])
        _, input_rarity, _ = rarity_system.check_rarity_uniformity(inputs)
        # Fallback to 'common' if rarity is None (material not in database)
        input_rarity = input_rarity or 'common'

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
        from core.tag_debug import get_tag_debugger

        recipe_tags = recipe.get('metadata', {}).get('tags', [])
        is_consumable = AlchemyTagProcessor.is_consumable(recipe_tags)
        effect_type = AlchemyTagProcessor.get_effect_type(recipe_tags)

        # Instant-effect potions (healing, damage) shouldn't have duration stats
        if effect_type in ['heal', 'damage']:
            # Remove duration from stats for instant effects
            modified_stats.pop('duration', None)
            print(f"   [Alchemy] Removed duration stat for instant-effect potion ({effect_type})")

        # Debug output
        debugger = get_tag_debugger()
        debugger.log_alchemy_detection(recipe_id, recipe_tags, is_consumable, effect_type)

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

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
import math
from pathlib import Path
from rarity_utils import rarity_system


class SmithingMinigame:
    """
    Smithing minigame implementation

    Controls:
    - Spacebar: Fan flames (increase temperature)
    - Click HAMMER button: Execute hammer strike when indicator is in target zone

    Goal: Maintain ideal temperature while hitting perfect timing on hammer strikes

    Difficulty System (v2):
    - Difficulty calculated from material tier point values
    - Each material: 2^(tier-1) * quantity points
    - Higher points = harder minigame = better potential rewards
    """

    def __init__(self, recipe, buff_time_bonus=0.0, buff_quality_bonus=0.0):
        """
        Initialize smithing minigame

        Args:
            recipe: Recipe dict from JSON (includes inputs for difficulty calculation)
            buff_time_bonus: Skill buff bonus to time limit (0.0-1.0+)
            buff_quality_bonus: Skill buff bonus to quality (0.0-1.0+)
        """
        self.recipe = recipe
        self.buff_time_bonus = buff_time_bonus
        self.buff_quality_bonus = buff_quality_bonus
        self.attempt = 1  # Track attempt number for first-try bonus

        # Calculate difficulty from materials using new system
        self._setup_difficulty_from_materials()

        # Store speed bonus for fire decrease rate calculation (NOT for time limit!)
        # Speed bonus slows down fire decrease, giving more time to work
        # Formula: effective_rate = base_rate / (1.0 + speed_bonus)
        self.speed_bonus = self.buff_time_bonus
        if self.speed_bonus > 0:
            print(f"⚡ Speed bonus: +{self.speed_bonus*100:.0f}% (slows fire decrease rate)")

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

        # Strike feedback (for UI display)
        self.last_strike_score = None  # Score of last strike (None = no strike yet)
        self.last_strike_temp_ok = True  # Was temperature OK during last strike?
        self.last_strike_temp_mult = 1.0  # Temperature multiplier for last strike
        self.last_strike_hammer_score = 0  # Raw hammer timing score before temp

        # Detailed stats tracking (for backwards compatibility and analytics)
        self.stats = {
            'perfect_strikes': 0,      # 100-point strikes (timing + temp both perfect)
            'excellent_strikes': 0,    # 90-99 point strikes
            'good_strikes': 0,         # 70-89 point strikes
            'fair_strikes': 0,         # 50-69 point strikes
            'poor_strikes': 0,         # 30-49 point strikes
            'miss_strikes': 0,         # <30 point strikes
            'temp_readings': [],       # Temperature at each strike
            'hammer_timing_scores': [], # Raw timing scores (before temp multiplier)
            'temp_multipliers': [],    # Temperature multipliers applied to each strike
            'time_in_ideal_temp': 0.0, # Cumulative time spent in ideal temp range
        }

    def _setup_difficulty_from_materials(self):
        """
        Setup difficulty parameters based on material tier point values.

        Uses core.difficulty_calculator for centralized calculation.
        Falls back to legacy tier-based system if calculator unavailable.
        """
        try:
            from core.difficulty_calculator import (
                calculate_smithing_difficulty,
                get_legacy_smithing_params,
                get_difficulty_description
            )

            # Calculate difficulty from recipe materials
            params = calculate_smithing_difficulty(self.recipe)

            # Store difficulty points for reward calculation
            self.difficulty_points = params['difficulty_points']

            # Apply parameters
            self.TEMP_IDEAL_MIN = int(params['temp_ideal_min'])
            self.TEMP_IDEAL_MAX = int(params['temp_ideal_max'])
            self.TEMP_DECAY = params['temp_decay_rate']
            self.TEMP_FAN_INCREMENT = params['temp_fan_increment']
            self.HAMMER_SPEED = params['hammer_speed']
            self.REQUIRED_HITS = int(params['required_hits'])
            self.TARGET_WIDTH = int(params['target_width'])
            self.PERFECT_WIDTH = int(params['perfect_width'])
            self.time_limit = int(params['time_limit'])
            self.HAMMER_BAR_WIDTH = 400

            # Log difficulty info
            difficulty_desc = get_difficulty_description(self.difficulty_points)
            print(f"🔥 Smithing difficulty: {difficulty_desc} ({self.difficulty_points:.1f} points)")
            print(f"   Hits: {self.REQUIRED_HITS}, Target: {self.TARGET_WIDTH}px, Time: {self.time_limit}s")

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
            from core.difficulty_calculator import get_legacy_smithing_params
            params = get_legacy_smithing_params(tier)
        except ImportError:
            # Hardcoded fallback
            tier_configs = {
                1: {'time_limit': 45, 'temp_ideal_min': 60, 'temp_ideal_max': 80,
                    'temp_decay_rate': 0.5, 'temp_fan_increment': 3, 'required_hits': 5,
                    'target_width': 100, 'perfect_width': 40, 'hammer_speed': 2.5,
                    'difficulty_points': 5},
                2: {'time_limit': 40, 'temp_ideal_min': 65, 'temp_ideal_max': 75,
                    'temp_decay_rate': 0.7, 'temp_fan_increment': 2.5, 'required_hits': 7,
                    'target_width': 80, 'perfect_width': 30, 'hammer_speed': 3.5,
                    'difficulty_points': 20},
                3: {'time_limit': 35, 'temp_ideal_min': 68, 'temp_ideal_max': 72,
                    'temp_decay_rate': 0.9, 'temp_fan_increment': 2, 'required_hits': 9,
                    'target_width': 60, 'perfect_width': 20, 'hammer_speed': 4.5,
                    'difficulty_points': 50},
                4: {'time_limit': 30, 'temp_ideal_min': 69, 'temp_ideal_max': 71,
                    'temp_decay_rate': 1.1, 'temp_fan_increment': 1.5, 'required_hits': 12,
                    'target_width': 40, 'perfect_width': 15, 'hammer_speed': 5.5,
                    'difficulty_points': 80},
            }
            params = tier_configs.get(tier, tier_configs[1])

        self.difficulty_points = params.get('difficulty_points', tier * 20)
        self.TEMP_IDEAL_MIN = params.get('temp_ideal_min', 60)
        self.TEMP_IDEAL_MAX = params.get('temp_ideal_max', 80)
        self.TEMP_DECAY = params.get('temp_decay_rate', 0.5)
        self.TEMP_FAN_INCREMENT = params.get('temp_fan_increment', 3)
        self.HAMMER_SPEED = params.get('hammer_speed', 2.5)
        self.REQUIRED_HITS = params.get('required_hits', 5)
        self.TARGET_WIDTH = params.get('target_width', 100)
        self.PERFECT_WIDTH = params.get('perfect_width', 40)
        self.time_limit = params.get('time_limit', 45)
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

        # Reset strike feedback
        self.last_strike_score = None
        self.last_strike_temp_ok = True
        self.last_strike_temp_mult = 1.0
        self.last_strike_hammer_score = 0

        # Reset stats tracking
        self.stats = {
            'perfect_strikes': 0,
            'excellent_strikes': 0,
            'good_strikes': 0,
            'fair_strikes': 0,
            'poor_strikes': 0,
            'miss_strikes': 0,
            'temp_readings': [],
            'hammer_timing_scores': [],
            'temp_multipliers': [],
            'time_in_ideal_temp': 0.0,
        }

    def update(self, dt):
        """
        Update minigame state

        Args:
            dt: Delta time in seconds
        """
        if not self.active:
            return

        # Track time in ideal temperature range
        if self.TEMP_IDEAL_MIN <= self.temperature <= self.TEMP_IDEAL_MAX:
            self.stats['time_in_ideal_temp'] += dt

        # Temperature decay using TEMP_DECAY parameter from difficulty calculator
        # TEMP_DECAY scales with difficulty: 0.3 (easy) to 1.2 (hard) per 100ms tick
        # Speed bonus slows down decay: effective_rate = base_rate / (1.0 + speed_bonus)
        now = pygame.time.get_ticks()
        if now - self.last_temp_update > 100:
            # Use TEMP_DECAY directly - higher value = faster decay = harder
            base_decay_per_tick = self.TEMP_DECAY

            # Apply speed bonus from skill buffs (slows down fire decrease)
            effective_decay = base_decay_per_tick / (1.0 + self.speed_bonus)

            self.temperature = max(0, self.temperature - effective_decay)
            self.last_temp_update = now

        # Hammer movement - HAMMER_SPEED scales with difficulty (higher = faster = harder)
        if self.hammer_hits < self.REQUIRED_HITS:
            self.hammer_position += self.hammer_direction * self.HAMMER_SPEED
            if self.hammer_position <= 0 or self.hammer_position >= self.HAMMER_BAR_WIDTH:
                self.hammer_direction *= -1
                self.hammer_position = max(0, min(self.HAMMER_BAR_WIDTH, self.hammer_position))

        # Timer - dt is already in seconds, no need to divide
        self.time_left = max(0, self.time_left - dt)
        if self.time_left <= 0:
            self.end(completed=False, reason="Time's up!")

    def handle_fan(self):
        """Handle fan action (spacebar) - increases temperature"""
        if self.active:
            self.temperature = min(100, self.temperature + self.TEMP_FAN_INCREMENT)

    def _calculate_hammer_timing_score(self, distance_from_center):
        """
        Calculate hammer timing score using binned system.

        Pattern: 0-30-50-60-70-80-90-100-90-80-70-60-50-30-0 (from edge to center to edge)
        - Standard zone width: w
        - 50 zone: 2w (2x larger)
        - 30 zone: 3w (3x larger)
        - Beyond zones: 0

        With HAMMER_BAR_WIDTH=400, half_width=200
        Zone widths: w=200/9≈22.2 pixels

        Returns:
            int: Raw timing score (0-100) before temperature multiplier
        """
        half_width = self.HAMMER_BAR_WIDTH / 2

        # Calculate zone width based on bar width
        # Total: 100(tiny) + 90(w) + 80(w) + 70(w) + 60(w) + 50(2w) + 30(3w) = 9w
        w = half_width / 9.0

        # Define cumulative thresholds from center
        # Zone boundaries (distance from center):
        perfect_threshold = w * 0.3  # Tiny center zone for 100 (easier to get center hits)
        zone_90 = w * 1.0
        zone_80 = w * 2.0
        zone_70 = w * 3.0
        zone_60 = w * 4.0
        zone_50 = w * 6.0  # 2w for 50 zone
        zone_30 = w * 9.0  # 3w for 30 zone

        # Determine score based on distance
        if distance_from_center <= perfect_threshold:
            return 100
        elif distance_from_center <= zone_90:
            return 90
        elif distance_from_center <= zone_80:
            return 80
        elif distance_from_center <= zone_70:
            return 70
        elif distance_from_center <= zone_60:
            return 60
        elif distance_from_center <= zone_50:
            return 50
        elif distance_from_center <= zone_30:
            return 30
        else:
            return 0

    def _calculate_temp_multiplier(self):
        """
        Calculate temperature multiplier using exponential falloff.

        - Maximum multiplier: 1.0 (when in ideal range)
        - At 4 degrees off from ideal: 0.5 multiplier
        - Exponential decay: mult = e^(-k * deviation^2)
        - k is tuned so that at 4 degrees: 0.5 = e^(-k * 16) → k = ln(2)/16 ≈ 0.0433

        Returns:
            float: Temperature multiplier (0.0 to 1.0)
        """
        # Calculate deviation from ideal center
        ideal_center = (self.TEMP_IDEAL_MIN + self.TEMP_IDEAL_MAX) / 2.0
        ideal_half_range = (self.TEMP_IDEAL_MAX - self.TEMP_IDEAL_MIN) / 2.0

        # If within ideal range, full multiplier
        if self.TEMP_IDEAL_MIN <= self.temperature <= self.TEMP_IDEAL_MAX:
            return 1.0

        # Calculate deviation from nearest ideal boundary
        if self.temperature < self.TEMP_IDEAL_MIN:
            deviation = self.TEMP_IDEAL_MIN - self.temperature
        else:
            deviation = self.temperature - self.TEMP_IDEAL_MAX

        # Exponential decay: 0.5 multiplier at 4 degrees off
        # k = ln(2) / 16 ≈ 0.0433
        k = 0.0433
        temp_mult = math.exp(-k * deviation * deviation)

        # Clamp to minimum of 0.1 to prevent complete zeroing
        return max(0.1, min(1.0, temp_mult))

    def handle_hammer(self):
        """
        Handle hammer strike with binned timing score and exponential temperature multiplier.

        Scoring system:
        - Hammer timing: Binned 0-30-50-60-70-80-90-100 scale based on distance from center
        - Temperature: Exponential multiplier (max 1.0, 0.5 at 4° off ideal)
        - Final score = hammer_score * temp_multiplier
        """
        if not self.active or self.hammer_hits >= self.REQUIRED_HITS:
            return

        center = self.HAMMER_BAR_WIDTH / 2
        distance = abs(self.hammer_position - center)

        # Calculate raw hammer timing score (0-100 binned)
        hammer_timing_score = self._calculate_hammer_timing_score(distance)

        # Calculate temperature multiplier (exponential, max 1.0, 0.5 at 4° off)
        temp_mult = self._calculate_temp_multiplier()

        # Final score = timing * temp multiplier
        final_score = int(round(hammer_timing_score * temp_mult))

        # Track temperature state for UI
        temp_in_ideal = self.TEMP_IDEAL_MIN <= self.temperature <= self.TEMP_IDEAL_MAX

        # Store detailed stats
        self.stats['temp_readings'].append(self.temperature)
        self.stats['hammer_timing_scores'].append(hammer_timing_score)
        self.stats['temp_multipliers'].append(temp_mult)

        # Categorize the strike for stats tracking
        if final_score >= 100:
            self.stats['perfect_strikes'] += 1
        elif final_score >= 90:
            self.stats['excellent_strikes'] += 1
        elif final_score >= 70:
            self.stats['good_strikes'] += 1
        elif final_score >= 50:
            self.stats['fair_strikes'] += 1
        elif final_score >= 30:
            self.stats['poor_strikes'] += 1
        else:
            self.stats['miss_strikes'] += 1

        # Store final score
        self.hammer_scores.append(final_score)
        self.hammer_hits += 1

        # Store strike result for UI feedback
        self.last_strike_score = final_score
        self.last_strike_temp_ok = temp_in_ideal
        self.last_strike_temp_mult = temp_mult
        self.last_strike_hammer_score = hammer_timing_score

        if self.hammer_hits >= self.REQUIRED_HITS:
            self.end(completed=True)

    def end(self, completed, reason=None):
        """
        End the minigame and calculate results using reward calculator.

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
                "bonus": 0,
                "difficulty_points": self.difficulty_points
            }
            return

        # Calculate performance metrics
        # Temperature is now factored into each strike score (100=perfect, 85=good timing/bad temp, etc.)
        # No need for additional temperature multiplier at the end
        avg_hammer_score = sum(self.hammer_scores) / len(self.hammer_scores) if self.hammer_scores else 0

        # Check if final temperature is in ideal range (for reward calculator)
        in_ideal_range = self.TEMP_IDEAL_MIN <= self.temperature <= self.TEMP_IDEAL_MAX

        # Final score is just the average of strike scores (temp already factored in)
        final_score = avg_hammer_score

        # Calculate earned/max points for crafted stats system
        earned_points = sum(self.hammer_scores)  # Total actual points earned
        max_points = self.REQUIRED_HITS * 100  # Perfect score (100 per hit)

        # Use reward calculator for scaling bonuses
        try:
            from core.reward_calculator import calculate_smithing_rewards

            rewards = calculate_smithing_rewards(
                self.difficulty_points,
                {
                    'avg_hammer_score': avg_hammer_score,
                    'temp_in_ideal': in_ideal_range,
                    'attempt': self.attempt
                }
            )

            bonus = rewards['bonus_pct']
            quality_tier = rewards['quality_tier']
            stat_multiplier = rewards['stat_multiplier']
            first_try_eligible = rewards['first_try_eligible']

            # Apply skill buff quality bonus (empower/elevate)
            if self.buff_quality_bonus > 0:
                buff_bonus = int(self.buff_quality_bonus * 10)
                bonus += buff_bonus
                print(f"⚡ Quality buff applied: +{buff_bonus}% bonus (total: {bonus}%)")

            # Log reward info
            print(f"🎯 Smithing result: {quality_tier} (+{bonus}%)")
            if first_try_eligible:
                print(f"   ✨ First-try bonus eligible!")

            self.result = {
                "success": True,
                "score": final_score,
                "bonus": bonus,
                "quality_tier": quality_tier,
                "stat_multiplier": stat_multiplier,
                "temp_in_ideal": in_ideal_range,
                "avg_hammer": avg_hammer_score,
                "difficulty_points": self.difficulty_points,
                "first_try_eligible": first_try_eligible,
                "earned_points": earned_points,
                "max_points": max_points,
                "message": f"Crafted {quality_tier} item with +{bonus}% bonus!",
                # Detailed stats for backwards compatibility and analytics
                "stats": self.stats.copy(),
            }

        except ImportError:
            # Fallback to legacy calculation
            if final_score >= 140:
                bonus = 15
            elif final_score >= 100:
                bonus = 10
            elif final_score >= 70:
                bonus = 5
            else:
                bonus = 0

            if self.buff_quality_bonus > 0:
                bonus += int(self.buff_quality_bonus * 10)

            self.result = {
                "success": True,
                "score": final_score,
                "bonus": bonus,
                "quality_tier": "Normal" if bonus == 0 else "Fine" if bonus <= 5 else "Superior",
                "stat_multiplier": 1.0 + (bonus / 100),
                "temp_in_ideal": in_ideal_range,
                "avg_hammer": avg_hammer_score,
                "difficulty_points": self.difficulty_points,
                "first_try_eligible": False,
                "earned_points": earned_points,
                "max_points": max_points,
                "message": f"Crafted with {bonus}% bonus!",
                # Detailed stats for backwards compatibility and analytics
                "stats": self.stats.copy(),
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
            "perfect_width": self.PERFECT_WIDTH,
            # Strike feedback for UI (new)
            "last_strike_score": self.last_strike_score,
            "last_strike_temp_ok": self.last_strike_temp_ok,
            "last_strike_temp_mult": self.last_strike_temp_mult,
            "last_strike_hammer_score": self.last_strike_hammer_score,
            # Stats for UI display
            "stats": self.stats,
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
            "../recipes.JSON/recipes-tag-tests.JSON",  # TEST RECIPES
            "recipes.JSON/recipes-smithing-1.json",
            "recipes.JSON/recipes-smithing-2.json",
            "recipes.JSON/recipes-smithing-3.json",
            "recipes.JSON/recipes-tag-tests.JSON",  # TEST RECIPES
        ]

        loaded_count = 0
        for path in possible_paths:
            try:
                with open(path, 'r') as f:
                    data = json.load(f)
                    recipe_list = data.get('recipes', [])
                    for recipe in recipe_list:
                        # Only load smithing recipes (or recipes with no stationType for backward compat)
                        station_type = recipe.get('stationType', 'smithing')
                        if station_type == 'smithing':
                            self.recipes[recipe['recipeId']] = recipe
                            loaded_count += 1
            except FileNotFoundError:
                continue
            except Exception as e:
                print(f"[Smithing] Error loading {path}: {e}")

        # Load recipes from Update-N packages
        loaded_count += self._load_update_recipes()

        if self.recipes:
            print(f"[Smithing] Loaded {loaded_count} recipes from {len(self.recipes)} total")
        else:
            print("[Smithing] WARNING: No recipes loaded")

    def _load_update_recipes(self):
        """Load smithing recipes from installed Update-N packages"""
        loaded_count = 0

        try:
            # Find the project root (where updates_manifest.json is located)
            current_dir = Path.cwd()
            project_root = None

            # Try current directory and parent directories
            for potential_root in [current_dir, current_dir.parent, current_dir.parent.parent]:
                manifest_path = potential_root / "updates_manifest.json"
                if manifest_path.exists():
                    project_root = potential_root
                    break

            if not project_root:
                return 0

            # Load manifest
            manifest_path = project_root / "updates_manifest.json"
            try:
                with open(manifest_path, 'r') as f:
                    manifest = json.load(f)
                    installed_updates = manifest.get('installed_updates', [])
            except Exception:
                return 0

            if not installed_updates:
                return 0

            # Scan each installed update for smithing recipes
            for update_name in installed_updates:
                update_path = project_root / update_name

                if not update_path.exists():
                    continue

                # Look for recipe files with smithing in the name (both .JSON and .json)
                recipe_files = list(update_path.glob("*recipes*smithing*.JSON"))
                recipe_files.extend(update_path.glob("*recipes*smithing*.json"))
                for recipe_file in recipe_files:
                    try:
                        with open(recipe_file, 'r') as f:
                            data = json.load(f)
                            recipe_list = data.get('recipes', [])
                            for recipe in recipe_list:
                                self.recipes[recipe['recipeId']] = recipe
                                loaded_count += 1
                            print(f"[Smithing] Loaded {len(recipe_list)} recipes from {update_name}/{recipe_file.name}")
                    except Exception as e:
                        print(f"[Smithing] Error loading {recipe_file}: {e}")

        except Exception as e:
            print(f"[Smithing] Error loading update recipes: {e}")

        return loaded_count

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

    def craft_instant(self, recipe_id, inventory, item_metadata=None):
        """
        Instant craft (no minigame) - produces base item

        Args:
            recipe_id: Recipe ID to craft
            inventory: Dict of {material_id: quantity} (will be modified)
            item_metadata: Optional dict of item metadata for category lookup

        Returns:
            dict: Result with outputId, quantity, success, rarity, tags
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

        # Get inheritable tags from recipe
        from core.crafting_tag_processor import SmithingTagProcessor
        from core.tag_debug import get_tag_debugger

        recipe_tags = recipe.get('metadata', {}).get('tags', [])
        inheritable_tags = SmithingTagProcessor.get_inheritable_tags(recipe_tags)

        # Debug output
        debugger = get_tag_debugger()
        debugger.log_smithing_inheritance(recipe_id, recipe_tags, inheritable_tags)

        # Console output for tag verification
        print(f"\n⚒️  SMITHING CRAFT: {recipe['outputId']}")
        print(f"   Recipe: {recipe_id}")
        if recipe_tags:
            print(f"   Recipe Tags: {', '.join(recipe_tags)}")
        else:
            print(f"   Recipe Tags: (none)")

        if inheritable_tags:
            print(f"   ✓ Inherited Tags: {', '.join(inheritable_tags)}")
        else:
            print(f"   ⚠️  NO TAGS INHERITED (no functional tags in recipe)")
        print(f"   Rarity: {input_rarity}")

        return {
            "success": True,
            "outputId": recipe['outputId'],
            "quantity": recipe['outputQty'],
            "bonus": 0,
            "rarity": input_rarity,
            "tags": inheritable_tags,  # Tags to apply to crafted item
            "message": f"Crafted ({input_rarity})"
        }

    def create_minigame(self, recipe_id, buff_time_bonus=0.0, buff_quality_bonus=0.0):
        """
        Create a smithing minigame for this recipe

        Args:
            recipe_id: Recipe ID to craft
            buff_time_bonus: Skill buff bonus to time limit (0.0-1.0+)
            buff_quality_bonus: Skill buff bonus to quality (0.0-1.0+)

        Returns:
            SmithingMinigame instance or None if recipe not found
        """
        if recipe_id not in self.recipes:
            return None

        recipe = self.recipes[recipe_id]

        # Pass full recipe for material-based difficulty calculation
        return SmithingMinigame(recipe, buff_time_bonus, buff_quality_bonus)

    def craft_with_minigame(self, recipe_id, inventory, minigame_result, item_metadata=None):
        """
        Craft with minigame result - produces item with bonuses and rarity modifiers

        Args:
            recipe_id: Recipe ID to craft
            inventory: Dict of {material_id: quantity} (will be modified)
            minigame_result: Result dict from SmithingMinigame
            item_metadata: Optional dict of item metadata for category lookup

        Returns:
            dict: Result with outputId, quantity, bonus, rarity, stats, tags, success
        """
        if not minigame_result.get('success'):
            # Failure - lose materials based on difficulty (tier-scaled penalty)
            recipe = self.recipes[recipe_id]
            difficulty_points = minigame_result.get('difficulty_points', 50)

            # Calculate loss fraction using reward calculator
            try:
                from core.reward_calculator import calculate_failure_penalty
                loss_fraction = calculate_failure_penalty(difficulty_points)
            except ImportError:
                loss_fraction = 0.5  # Fallback to 50%

            # Apply material loss
            total_lost = 0
            for inp in recipe['inputs']:
                mat_id = inp.get('materialId') or inp.get('itemId')
                loss = int(inp['quantity'] * loss_fraction)
                if mat_id not in inventory:
                    inventory[mat_id] = 0
                inventory[mat_id] = max(0, inventory[mat_id] - loss)
                total_lost += loss

            print(f"❌ Smithing failed! Lost {int(loss_fraction * 100)}% of materials ({total_lost} items)")

            return {
                "success": False,
                "message": minigame_result.get('message', 'Crafting failed'),
                "materials_lost": True,
                "loss_fraction": loss_fraction
            }

        # Success - deduct full materials
        recipe = self.recipes[recipe_id]
        # Material consumption is handled by RecipeDatabase.consume_materials() in game_engine.py
        # This keeps the architecture clean with a single source of truth for inventory management

        # Detect input rarity
        inputs = recipe.get('inputs', [])
        _, input_rarity, _ = rarity_system.check_rarity_uniformity(inputs)
        # Fallback to 'common' if rarity is None (material not in database)
        input_rarity = input_rarity or 'common'

        # Generate crafted stats using the new crafted_stats system
        from entities.components.crafted_stats import generate_crafted_stats
        from data.databases.equipment_db import EquipmentDatabase

        output_id = recipe['outputId']
        equip_db = EquipmentDatabase.get_instance()

        # Determine item_type from the output equipment
        item_type = 'weapon'  # Default fallback
        if equip_db.is_equipment(output_id):
            temp_equipment = equip_db.create_equipment_from_id(output_id)
            if temp_equipment and hasattr(temp_equipment, 'item_type'):
                item_type = temp_equipment.item_type

        # Generate appropriate stats based on minigame performance and item type
        base_stats = generate_crafted_stats(minigame_result, recipe, item_type)

        # Get item category and apply rarity modifiers
        if item_metadata is None:
            item_metadata = {}

        item_category = rarity_system.get_item_category(output_id, item_metadata)
        modified_stats = rarity_system.apply_rarity_modifiers(base_stats, item_category, input_rarity)

        # Get inheritable tags from recipe
        from core.crafting_tag_processor import SmithingTagProcessor
        from core.tag_debug import get_tag_debugger

        recipe_tags = recipe.get('metadata', {}).get('tags', [])
        inheritable_tags = SmithingTagProcessor.get_inheritable_tags(recipe_tags)

        # Debug output
        debugger = get_tag_debugger()
        debugger.log_smithing_inheritance(recipe_id, recipe_tags, inheritable_tags)

        # Extract bonus for logging
        bonus_pct = minigame_result.get('bonus', 0)

        # Console output for tag verification
        print(f"\n⚒️  SMITHING CRAFT (MINIGAME): {output_id}")
        print(f"   Recipe: {recipe_id}")
        print(f"   Minigame Bonus: {bonus_pct}%")
        if recipe_tags:
            print(f"   Recipe Tags: {', '.join(recipe_tags)}")
        else:
            print(f"   Recipe Tags: (none)")

        if inheritable_tags:
            print(f"   ✓ Inherited Tags: {', '.join(inheritable_tags)}")
        else:
            print(f"   ⚠️  NO TAGS INHERITED (no functional tags in recipe)")
        print(f"   Rarity: {input_rarity}")

        return {
            "success": True,
            "outputId": output_id,
            "quantity": recipe['outputQty'],
            "bonus": minigame_result.get('bonus', 0),
            "score": minigame_result.get('score', 0),
            "rarity": input_rarity,
            "stats": modified_stats,
            "tags": inheritable_tags,  # Tags to apply to crafted item
            "first_try_eligible": minigame_result.get('first_try_eligible', False),
            "earned_points": minigame_result.get('earned_points', 0),
            "max_points": minigame_result.get('max_points', 100),
            "message": f"Crafted {input_rarity} item with +{minigame_result.get('bonus', 0)}% bonus!"
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

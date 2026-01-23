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

    def update(self, dt):
        """
        Update minigame state

        Args:
            dt: Delta time in seconds
        """
        if not self.active:
            return

        # Temperature decay with speed bonus
        # Fire decrease rate is calibrated to "5 clicks per second" equivalent
        # Speed bonus slows down the decrease: effective_rate = base_rate / (1.0 + speed_bonus)
        now = pygame.time.get_ticks()
        if now - self.last_temp_update > 100:
            # Calculate base decay rate (5 clicks/sec worth, divided by 10 for 100ms ticks)
            # This means player needs to maintain ~5 clicks/sec to keep temperature stable
            clicks_per_second_equivalent = 5.0
            base_decay_per_second = clicks_per_second_equivalent * self.TEMP_FAN_INCREMENT
            base_decay_per_tick = base_decay_per_second / 10.0  # 100ms = 1/10 second

            # Apply speed bonus (slows down fire decrease)
            effective_decay = base_decay_per_tick / (1.0 + self.speed_bonus)

            self.temperature = max(0, self.temperature - effective_decay)
            self.last_temp_update = now

        # Hammer movement
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
        avg_hammer_score = sum(self.hammer_scores) / len(self.hammer_scores) if self.hammer_scores else 0
        in_ideal_range = self.TEMP_IDEAL_MIN <= self.temperature <= self.TEMP_IDEAL_MAX
        temp_mult = 1.2 if in_ideal_range else 1.0

        final_score = avg_hammer_score * temp_mult

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
                "temp_mult": temp_mult,
                "avg_hammer": avg_hammer_score,
                "difficulty_points": self.difficulty_points,
                "first_try_eligible": first_try_eligible,
                "earned_points": earned_points,
                "max_points": max_points,
                "message": f"Crafted {quality_tier} item with +{bonus}% bonus!"
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
                "temp_mult": temp_mult,
                "avg_hammer": avg_hammer_score,
                "difficulty_points": self.difficulty_points,
                "first_try_eligible": False,
                "earned_points": earned_points,
                "max_points": max_points,
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

                # Look for recipe files with smithing in the name
                for recipe_file in update_path.glob("*recipes*smithing*.JSON"):
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

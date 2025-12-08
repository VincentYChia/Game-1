"""
Enchanting (Adornment) Crafting Subdiscipline

Framework:
- Python module ready for main.py integration
- Loads recipes from JSON files
- REQUIRED minigame (no skip option for adornments)
- Difficulty based on tier (affects grid size and pattern complexity)

Minigame: Pattern-matching (like enchanting-pattern-designer.py in survival mode)
- Player must recreate the target pattern from placements JSON
- Place shapes (triangles, squares) at correct positions with correct rotations
- Assign correct materials to vertices
- Validation checks for exact match

NOTE: Enchanting is unique - minigame is REQUIRED, cannot be skipped
"""

import pygame
import json
import math
from pathlib import Path
from rarity_utils import rarity_system


class SpinningWheelMinigame:
    """
    Gambling-based spinning wheel minigame for enchanting

    Mechanics:
    - 20-slice wheel with green, red, grey colors
    - 3 spins total per minigame
    - Start with 100 currency
    - Bet currency, spin wheel, win/lose based on color
    - Different multipliers per spin
    - Final currency difference from 100 = efficacy boost (±50% max)
    """

    def __init__(self, recipe, tier, target_item=None):
        """
        Initialize spinning wheel minigame

        Args:
            recipe: Recipe dict from JSON
            tier: Recipe tier (1-4)
            target_item: Item being enchanted (optional)
        """
        self.recipe = recipe
        self.tier = tier
        self.target_item = target_item

        # Currency system
        self.starting_currency = 100
        self.current_currency = 100
        self.current_bet = 0

        # Wheel state
        self.current_spin_number = 0  # 0-2 for spins 1-3
        self.wheels = []  # Store 3 wheels (list of 20 colors each)
        self.spin_results = []  # Track results of each spin
        self.wheel_visible = False  # Hidden until bet (except first spin)
        self.wheel_spinning = False
        self.wheel_rotation = 0.0  # Current rotation angle
        self.spin_start_time = None
        self.final_slice_index = None  # Result of current spin

        # Multipliers for each spin [green, grey, red]
        self.multipliers = [
            {'green': 1.2, 'grey': 1.0, 'red': 0.66},   # Spin 1
            {'green': 1.5, 'grey': 0.95, 'red': 0.5},   # Spin 2
            {'green': 2.0, 'grey': 0.8, 'red': 0.0}     # Spin 3
        ]

        # Game state
        self.active = False
        self.result = None
        self.phase = 'betting'  # 'betting', 'spinning', 'result', 'completed'

        # Generate all 3 wheels upfront
        self._generate_wheels()

    def _generate_wheels(self):
        """Generate 3 wheels with constraints"""
        import random

        for spin_num in range(3):
            wheel = self._generate_single_wheel(spin_num)
            self.wheels.append(wheel)

    def _generate_single_wheel(self, spin_num):
        """
        Generate a single wheel with constraints

        Constraints:
        - Spin 0 (first): min 10 green, min 3 red, rest grey
        - Spin 1 (second): min 8 green, min 5 red, rest grey
        - Spin 2 (third): min 8 green, min 8 red, rest grey
        After minimums met, remaining slots are 33% split

        Args:
            spin_num: 0, 1, or 2

        Returns:
            List of 20 colors: ['green', 'red', 'grey', ...]
        """
        import random

        # Define minimum requirements per spin
        if spin_num == 0:
            min_green = 10
            min_red = 3
        elif spin_num == 1:
            min_green = 8
            min_red = 5
        else:  # spin_num == 2
            min_green = 8
            min_red = 8

        # Create wheel with minimums
        wheel = ['green'] * min_green + ['red'] * min_red

        # Fill remaining slots with 33% split
        remaining_slots = 20 - min_green - min_red
        colors = ['green', 'red', 'grey']
        for _ in range(remaining_slots):
            wheel.append(random.choice(colors))

        # Shuffle to randomize positions
        random.shuffle(wheel)
        return wheel

    def start(self):
        """Start the minigame"""
        self.active = True
        self.phase = 'betting'
        self.current_spin_number = 0
        self.current_currency = self.starting_currency
        self.current_bet = 0
        self.spin_results = []
        self.wheel_visible = True  # First spin wheel is visible
        self.wheel_spinning = False
        self.result = None

    def update(self, dt):
        """
        Update minigame state

        Args:
            dt: Delta time in milliseconds
        """
        if not self.active:
            return

        # Handle wheel spinning animation
        if self.wheel_spinning and self.spin_start_time is not None:
            import time
            elapsed = (time.time() - self.spin_start_time) * 1000  # Convert to ms

            # Spin duration: 2 seconds
            spin_duration = 2000

            if elapsed < spin_duration:
                # Animate rotation (decelerating)
                progress = elapsed / spin_duration
                # Ease-out cubic
                ease_progress = 1 - pow(1 - progress, 3)

                # Calculate final rotation (multiple full rotations + final position)
                if self.final_slice_index is not None:
                    # Target angle for the slice (each slice is 18 degrees = 360/20)
                    slice_angle = (self.final_slice_index * 18) + 9  # Center of slice
                    # Add multiple rotations for dramatic effect
                    total_rotation = 360 * 5 + slice_angle  # 5 full rotations plus final position
                    self.wheel_rotation = ease_progress * total_rotation
            else:
                # Spinning complete
                self.wheel_spinning = False
                self._process_spin_result()

    def place_bet(self, amount):
        """
        Place a bet for the current spin

        Args:
            amount: Bet amount

        Returns:
            bool: True if bet placed successfully
        """
        if self.phase != 'betting':
            return False

        if amount <= 0 or amount > self.current_currency:
            return False

        self.current_bet = amount
        self.phase = 'ready_to_spin'
        self.wheel_visible = True
        return True

    def spin_wheel(self):
        """
        Start spinning the wheel

        Returns:
            bool: True if spin started successfully
        """
        if self.phase != 'ready_to_spin':
            return False

        if self.current_bet <= 0:
            return False

        # Start spinning
        self.wheel_spinning = True
        self.wheel_rotation = 0.0
        import time
        self.spin_start_time = time.time()

        # Randomly select result slice
        import random
        current_wheel = self.wheels[self.current_spin_number]
        self.final_slice_index = random.randint(0, 19)

        self.phase = 'spinning'
        return True

    def _process_spin_result(self):
        """Process the result of a spin after animation completes"""
        current_wheel = self.wheels[self.current_spin_number]
        result_color = current_wheel[self.final_slice_index]

        # Get multiplier for this spin and color
        multiplier = self.multipliers[self.current_spin_number][result_color]

        # Calculate winnings
        winnings = int(self.current_bet * multiplier)
        profit = winnings - self.current_bet

        # Update currency
        self.current_currency = self.current_currency - self.current_bet + winnings

        # Record result
        self.spin_results.append({
            'spin_number': self.current_spin_number + 1,
            'bet': self.current_bet,
            'color': result_color,
            'multiplier': multiplier,
            'winnings': winnings,
            'profit': profit,
            'currency_after': self.current_currency
        })

        # Move to result phase
        self.phase = 'spin_result'
        self.current_bet = 0

    def advance_to_next_spin(self):
        """
        Advance to the next spin or complete the minigame

        Returns:
            bool: True if advanced successfully
        """
        if self.phase != 'spin_result':
            return False

        self.current_spin_number += 1

        if self.current_spin_number >= 3:
            # All spins complete
            self.complete()
            return True
        else:
            # Move to next spin
            self.phase = 'betting'
            self.wheel_visible = False  # Hide wheel until bet
            return True

    def complete(self):
        """Complete the minigame and calculate final efficacy"""
        self.active = False
        self.phase = 'completed'

        # Calculate efficacy from currency difference
        currency_diff = self.current_currency - self.starting_currency

        # Efficacy is capped at ±50%
        # Map currency difference to efficacy: -100 to +100 → -50% to +50%
        # But currency can go below 0 or above 200, so we need to cap
        efficacy_percent = (currency_diff / 100.0) * 50.0
        efficacy_percent = max(-50.0, min(50.0, efficacy_percent))

        # Convert to decimal (e.g., 25% = 0.25)
        efficacy = efficacy_percent / 100.0

        self.result = {
            "success": True,  # Always succeeds (but efficacy can be negative)
            "efficacy": efficacy,
            "efficacy_percent": efficacy_percent,
            "final_currency": self.current_currency,
            "currency_diff": currency_diff,
            "spin_results": self.spin_results,
            "message": f"Minigame complete! Efficacy: {efficacy_percent:+.1f}%"
        }

        return self.result

    def get_state(self):
        """Get current minigame state for rendering"""
        return {
            "active": self.active,
            "phase": self.phase,
            "current_spin_number": self.current_spin_number,
            "current_currency": self.current_currency,
            "current_bet": self.current_bet,
            "wheel_visible": self.wheel_visible,
            "wheel_spinning": self.wheel_spinning,
            "wheel_rotation": self.wheel_rotation,
            "wheels": self.wheels,
            "current_wheel": self.wheels[self.current_spin_number] if self.current_spin_number < len(self.wheels) else None,
            "multipliers": self.multipliers,
            "current_multiplier": self.multipliers[self.current_spin_number] if self.current_spin_number < len(self.multipliers) else None,
            "spin_results": self.spin_results,
            "final_slice_index": self.final_slice_index,
            "result": self.result
        }


class PatternMatchingMinigame:
    """
    Pattern-matching minigame for enchanting

    Player must recreate the target pattern by:
    1. Placing shapes (from available shape types based on tier)
    2. Assigning materials to vertices
    3. Matching the target pattern exactly
    """

    def __init__(self, recipe, tier, target_pattern, available_shapes):
        """
        Initialize pattern-matching minigame

        Args:
            recipe: Recipe dict from JSON
            tier: Recipe tier (1-4)
            target_pattern: Pattern from placements JSON {"gridType", "vertices", "shapes"}
            available_shapes: List of available shape types for this tier
        """
        self.recipe = recipe
        self.tier = tier
        self.target_pattern = target_pattern
        self.available_shapes = available_shapes

        # Parse grid size from gridType (e.g., "square_8x8")
        grid_type = target_pattern.get('gridType', 'square_8x8')
        self.grid_size = int(grid_type.split('_')[1].split('x')[0])

        # Game state
        self.active = False
        self.mode = 'shape_placement'  # 'shape_placement' or 'material_assignment'
        self.player_shapes = []  # List of placed shapes
        self.player_vertices = {}  # {(x,y): {"materialId": ..., "isKey": ...}}
        self.result = None

        # UI state
        self.selected_shape_type = None
        self.current_rotation = 0
        self.selected_material = None
        self.show_target_materials = True  # Show target materials as hint

        # Shape templates (same as in enchanting-pattern-designer.py)
        self.shape_templates = {
            "triangle_equilateral_small": [(0, 0), (-1, -2), (1, -2)],
            "square_small": [(0, 0), (2, 0), (2, -2), (0, -2)],
            "triangle_isosceles_small": [(0, 0), (-1, -3), (1, -3)],
            "triangle_equilateral_large": [(0, 0), (-2, -3), (2, -3)],
            "square_large": [(0, 0), (4, 0), (4, -4), (0, -4)],
            "triangle_isosceles_large": [(0, 0), (-1, -5), (1, -5)]
        }

        # Get available materials from recipe
        self.available_materials = [inp['materialId'] for inp in recipe.get('inputs', [])]

    def start(self):
        """Start the minigame"""
        self.active = True
        self.mode = 'shape_placement'
        self.player_shapes = []
        self.player_vertices = {}
        self.result = None

    def update(self, dt):
        """
        Update minigame state

        Args:
            dt: Delta time in milliseconds

        Note: Pattern-matching minigame is purely event-driven,
        no time-based updates needed.
        """
        if not self.active:
            return
        # No time-based logic needed for pattern matching

    def rotate_point(self, x, y, degrees):
        """Rotate a point around origin by degrees"""
        rad = math.radians(degrees)
        cos_a = math.cos(rad)
        sin_a = math.sin(rad)
        new_x = round(x * cos_a - y * sin_a)
        new_y = round(x * sin_a + y * cos_a)
        return (new_x, new_y)

    def get_rotated_shape_vertices(self, shape_type, anchor_x, anchor_y, rotation):
        """Get absolute vertices for a shape at anchor position with rotation"""
        if shape_type not in self.shape_templates:
            return []

        template = self.shape_templates[shape_type]
        vertices = []
        for dx, dy in template:
            # Rotate offset around origin
            rx, ry = self.rotate_point(dx, dy, rotation)
            # Add anchor position
            vertices.append((anchor_x + rx, anchor_y + ry))
        return vertices

    def place_shape(self, shape_type, anchor_x, anchor_y, rotation):
        """
        Place a shape at the given anchor position with rotation

        Returns:
            bool: True if placed successfully
        """
        if self.mode != 'shape_placement':
            return False

        if shape_type not in self.available_shapes:
            return False

        # Get vertices for this shape
        vertices = self.get_rotated_shape_vertices(shape_type, anchor_x, anchor_y, rotation)

        # Check if all vertices fit in grid
        half = self.grid_size // 2
        for vx, vy in vertices:
            if abs(vx) > half or abs(vy) > half:
                return False

        # Add shape to player's shapes
        shape_data = {
            "type": shape_type,
            "vertices": vertices,
            "rotation": rotation
        }
        self.player_shapes.append(shape_data)

        # Activate vertices for material assignment
        for v in vertices:
            if v not in self.player_vertices:
                self.player_vertices[v] = {"materialId": None, "isKey": False}

        return True

    def remove_last_shape(self):
        """Remove the last placed shape"""
        if not self.player_shapes:
            return False

        # Get vertices from last shape
        last_shape = self.player_shapes.pop()
        shape_vertices = set(last_shape['vertices'])

        # Check if any other shape uses these vertices
        other_vertices = set()
        for shape in self.player_shapes:
            other_vertices.update(shape['vertices'])

        # Remove vertices not used by other shapes
        vertices_to_remove = shape_vertices - other_vertices
        for v in vertices_to_remove:
            if v in self.player_vertices:
                del self.player_vertices[v]

        return True

    def assign_material(self, x, y, material_id):
        """
        Assign material to a vertex

        Returns:
            bool: True if assigned successfully
        """
        if self.mode != 'material_assignment':
            return False

        coord = (x, y)
        if coord not in self.player_vertices:
            return False

        if material_id not in self.available_materials and material_id is not None:
            return False

        self.player_vertices[coord]['materialId'] = material_id
        return True

    def toggle_key_vertex(self, x, y):
        """Toggle whether a vertex is marked as key"""
        coord = (x, y)
        if coord in self.player_vertices and self.player_vertices[coord]['materialId']:
            is_key = self.player_vertices[coord].get('isKey', False)
            self.player_vertices[coord]['isKey'] = not is_key
            return True
        return False

    def validate_pattern(self):
        """
        Check if player's pattern matches the target pattern exactly

        Returns:
            dict: {"success": bool, "message": str, "errors": list}
        """
        errors = []

        # Parse target vertices (convert string keys to tuples)
        target_vertices = {}
        for key, value in self.target_pattern.get('vertices', {}).items():
            x, y = map(int, key.split(','))
            target_vertices[(x, y)] = value

        # Parse target shapes
        target_shapes = []
        for shape in self.target_pattern.get('shapes', []):
            shape_vertices = []
            for v_str in shape['vertices']:
                x, y = map(int, v_str.split(','))
                shape_vertices.append((x, y))
            target_shapes.append({
                "type": shape['type'],
                "vertices": set(shape_vertices),
                "rotation": shape['rotation']
            })

        # Check shape count
        if len(self.player_shapes) != len(target_shapes):
            errors.append(f"Wrong number of shapes: {len(self.player_shapes)} placed, need {len(target_shapes)}")

        # Check if all target shapes are matched
        matched_target_shapes = set()
        for player_shape in self.player_shapes:
            player_vertices_set = set(player_shape['vertices'])
            matched = False

            for idx, target_shape in enumerate(target_shapes):
                if idx in matched_target_shapes:
                    continue

                # Check if vertices match
                if player_vertices_set == target_shape['vertices']:
                    # Check if type and rotation match
                    if player_shape['type'] == target_shape['type'] and player_shape['rotation'] == target_shape['rotation']:
                        matched_target_shapes.add(idx)
                        matched = True
                        break

            if not matched:
                errors.append(f"Unmatched shape: {player_shape['type']} at rotation {player_shape['rotation']}")

        # Check for missing target shapes
        for idx, target_shape in enumerate(target_shapes):
            if idx not in matched_target_shapes:
                errors.append(f"Missing target shape: {target_shape['type']}")

        # Check vertex materials
        for coord, target_data in target_vertices.items():
            if coord not in self.player_vertices:
                errors.append(f"Missing vertex at {coord}")
                continue

            player_data = self.player_vertices[coord]
            if player_data['materialId'] != target_data['materialId']:
                errors.append(f"Wrong material at {coord}: placed {player_data['materialId']}, need {target_data['materialId']}")

        # Check for extra vertices with materials
        for coord, player_data in self.player_vertices.items():
            if coord not in target_vertices and player_data['materialId']:
                errors.append(f"Extra material at {coord}: {player_data['materialId']}")

        # Success if no errors
        success = len(errors) == 0
        message = "Perfect match!" if success else f"{len(errors)} error(s) found"

        return {
            "success": success,
            "message": message,
            "errors": errors
        }

    def complete(self):
        """Complete the minigame and calculate results"""
        validation = self.validate_pattern()

        if validation['success']:
            # Success - determine enchantment quality based on tier
            self.result = {
                "success": True,
                "message": "Enchantment pattern matched perfectly!",
                "quality": 1.0,  # Perfect match
                "tier_bonus": self.tier * 5  # 5% per tier
            }
        else:
            # Failure
            self.result = {
                "success": False,
                "message": f"Pattern mismatch: {validation['message']}",
                "errors": validation['errors'],
                "materials_lost": True
            }

        self.active = False
        return self.result

    def get_state(self):
        """Get current minigame state for rendering"""
        return {
            "active": self.active,
            "mode": self.mode,
            "phase": 1 if self.mode == 'shape_placement' else 2,  # Map mode to phase for renderer compatibility
            "grid_size": self.grid_size,
            "target_pattern": self.target_pattern,
            "player_shapes": self.player_shapes,
            "player_vertices": self.player_vertices,
            "available_shapes": self.available_shapes,
            "available_materials": self.available_materials,
            "selected_shape_type": self.selected_shape_type,
            "current_rotation": self.current_rotation,
            "selected_material": self.selected_material,
            "show_target_materials": self.show_target_materials,
            "result": self.result
        }


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

    def update(self, dt):
        """
        Update minigame state

        Args:
            dt: Delta time in milliseconds

        Note: Enchanting minigame is purely event-driven,
        no time-based updates needed.
        """
        if not self.active:
            return
        # No time-based logic needed for enchanting

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
        self.placements = {}  # Pattern placements for each recipe
        self.load_recipes()
        self.load_placements()

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

    def load_placements(self):
        """Load pattern placements from JSON files"""
        possible_paths = [
            "../placements.JSON/placements-adornments-1.JSON",
            "placements.JSON/placements-adornments-1.JSON",
        ]

        for path in possible_paths:
            try:
                with open(path, 'r') as f:
                    data = json.load(f)
                    placement_list = data.get('placements', [])
                    for p in placement_list:
                        recipe_id = p.get('recipeId')
                        if recipe_id:
                            self.placements[recipe_id] = p.get('placementMap', {})
            except FileNotFoundError:
                continue

        if self.placements:
            print(f"[Enchanting] Loaded {len(self.placements)} placement patterns")
        else:
            print("[Enchanting] WARNING: No placement patterns loaded")

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
        Instant craft (basic crafting) - ONLY method for enchanting

        Enchanting does NOT have minigames - it's basic craft only

        Args:
            recipe_id: Recipe ID to craft
            inventory: Dict of {material_id: quantity} (will be modified)
            item_metadata: Optional dict of item metadata

        Returns:
            dict: Result with outputId, quantity, rarity, success
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

        # Create enchantment - enchanting uses enchantmentId not outputId
        enchantment_id = recipe.get('enchantmentId', recipe.get('outputId', 'unknown_enchantment'))
        enchantment_name = recipe.get('enchantmentName', recipe.get('name', 'Unknown Enchantment'))

        return {
            "success": True,
            "outputId": enchantment_id,  # Use enchantmentId as outputId
            "quantity": 1,  # Enchantments are always quantity 1
            "enchantmentName": enchantment_name,
            "rarity": input_rarity,
            "message": f"Created {input_rarity} {enchantment_name}"
        }

    def get_available_shapes_for_tier(self, tier):
        """Get available shape types for a given tier (cumulative)"""
        shapes = []

        # T1: Basic small shapes
        if tier >= 1:
            shapes.extend(["triangle_equilateral_small", "square_small"])

        # T2: Add small isosceles
        if tier >= 2:
            shapes.append("triangle_isosceles_small")

        # T3: Add large equilateral and square
        if tier >= 3:
            shapes.extend(["triangle_equilateral_large", "square_large"])

        # T4: Add large isosceles (all shapes now available)
        if tier >= 4:
            shapes.append("triangle_isosceles_large")

        return shapes

    def create_minigame(self, recipe_id, target_item=None):
        """
        Create an enchanting minigame for this recipe

        Args:
            recipe_id: Recipe ID to craft
            target_item: Item to enchant (can be None for accessories)

        Returns:
            SpinningWheelMinigame instance or None
        """
        if recipe_id not in self.recipes:
            return None

        recipe = self.recipes[recipe_id]
        tier = recipe.get('stationTier', 1)

        # Create spinning wheel minigame
        return SpinningWheelMinigame(recipe, tier, target_item)

    def craft_with_minigame(self, recipe_id, inventory, minigame_result, target_item=None, item_metadata=None):
        """
        Craft with minigame result - apply enchantment with rarity

        Args:
            recipe_id: Recipe ID to craft
            inventory: Dict of {material_id: quantity} (will be modified)
            minigame_result: Result dict from PatternMatchingMinigame
            target_item: Item to enchant (modified in place)
            item_metadata: Optional dict of item metadata

        Returns:
            dict: Result with success, enchantment details, rarity
        """
        recipe = self.recipes[recipe_id]

        # Detect input rarity before consuming materials
        inputs = recipe.get('inputs', [])
        _, input_rarity, _ = rarity_system.check_rarity_uniformity(inputs)

        # Always consume materials (even on failure)
        for inp in recipe['inputs']:
            inventory[inp['materialId']] -= inp['quantity']

        if not minigame_result.get('success'):
            # Minigame failed (shouldn't happen with spinning wheel, but keep for safety)
            return {
                "success": False,
                "message": minigame_result.get('message'),
                "errors": minigame_result.get('errors', []),
                "materials_lost": True
            }

        # Success - apply enchantment with efficacy from minigame
        # Efficacy ranges from -0.5 to +0.5 (-50% to +50%)
        efficacy = minigame_result.get('efficacy', 0.0)
        efficacy_percent = minigame_result.get('efficacy_percent', 0.0)

        # Base bonus from tier
        tier = recipe.get('stationTier', 1)
        base_bonus = tier * 5  # T1=5%, T2=10%, T3=15%, T4=20%

        # Apply rarity modifier to base
        rarity_multipliers = {
            'common': 1.0,
            'uncommon': 1.1,
            'rare': 1.2,
            'epic': 1.35,
            'legendary': 2.0
        }
        rarity_mult = rarity_multipliers.get(input_rarity, 1.0)

        # Calculate final bonus with efficacy applied
        # Base bonus is modified by (1 + efficacy)
        # E.g., if base is 10% and efficacy is +25%, final is 10 * 1.25 = 12.5%
        # If efficacy is -25%, final is 10 * 0.75 = 7.5%
        final_bonus_multiplier = 1.0 + efficacy
        final_bonus = int(base_bonus * rarity_mult * final_bonus_multiplier)

        # Get enchantment details from recipe
        enchantment_id = recipe.get('enchantmentId', recipe.get('outputId'))
        enchantment_name = recipe.get('enchantmentName', recipe.get('name', 'Unknown Enchantment'))

        enchantment_data = {
            "enchantmentId": enchantment_id,
            "enchantmentName": enchantment_name,
            "bonus_magnitude": final_bonus,
            "efficacy": efficacy,
            "efficacy_percent": efficacy_percent,
            "rarity": input_rarity
        }

        if target_item:
            # Apply to existing equipment item (EquipmentItem object, not dict)
            # Use the apply_enchantment method which handles the enchantment logic
            success, message = target_item.apply_enchantment(
                enchantment_id,
                enchantment_name,
                recipe.get('effect', {})
            )

            if success:
                return {
                    "success": True,
                    "message": f"{input_rarity.capitalize()} {enchantment_name} applied to {target_item.name}! (Efficacy: {efficacy_percent:+.1f}%)",
                    "enchantment": enchantment_data,
                    "enchanted_item": target_item,
                    "rarity": input_rarity
                }
            else:
                # Enchantment failed (e.g., tier protection, duplicate, etc.)
                return {
                    "success": False,
                    "message": f"Failed to apply enchantment: {message}",
                    "rarity": input_rarity
                }
        else:
            # Create new enchanted accessory
            return {
                "success": True,
                "outputId": enchantment_id,
                "quantity": 1,
                "enchantmentName": enchantment_name,
                "message": f"Created {input_rarity} {enchantment_name}",
                "enchantment": enchantment_data,
                "rarity": input_rarity
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

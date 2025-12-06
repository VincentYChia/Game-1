"""
Engineering Crafting Subdiscipline

Framework:
- Python module ready for main.py integration
- Loads recipes from JSON files
- Optional minigame (sequential cognitive puzzles)
- Difficulty based on tier (tier + X + Y in future updates)

Minigame: Sequential cognitive puzzle solving
- Pure problem-solving, no timing, no dexterity
- Multiple puzzles per device (tier-dependent)
- Rotation pipe puzzles (T1)
- Sliding tile puzzles (T2+)
- Traffic jam puzzles (T3+) [PLACEHOLDER]
- Pattern matching + logic grids (T4+) [PLACEHOLDER]
"""

import pygame
import json
import random
import copy
from pathlib import Path
from rarity_utils import rarity_system


class RotationPipePuzzle:
    """
    Rotation pipe puzzle - T1 Engineering

    Goal: Rotate pieces to connect input to output
    - Grid of pipe pieces
    - Click to rotate 90 degrees
    - All pieces must connect (no loose ends)

    Piece types:
    0 = empty
    1 = straight (2 connections: 0°=horizontal, 90°=vertical)
    2 = L-bend (2 connections: rotatable 90° increments)
    3 = T-junction (3 connections: rotatable)
    4 = cross (4 connections: doesn't need rotation)
    """

    # Connection maps: for each piece type, which sides connect at each rotation
    # Sides: 0=top, 1=right, 2=bottom, 3=left
    CONNECTIONS = {
        0: {0: [], 90: [], 180: [], 270: []},  # Empty
        1: {0: [1, 3], 90: [0, 2], 180: [1, 3], 270: [0, 2]},  # Straight
        2: {0: [0, 1], 90: [1, 2], 180: [2, 3], 270: [3, 0]},  # L-bend
        3: {0: [0, 1, 3], 90: [0, 1, 2], 180: [1, 2, 3], 270: [0, 2, 3]},  # T-junction
        4: {0: [0, 1, 2, 3], 90: [0, 1, 2, 3], 180: [0, 1, 2, 3], 270: [0, 1, 2, 3]}  # Cross
    }

    def __init__(self, grid_size=3, difficulty="easy"):
        """Initialize rotation pipe puzzle"""
        self.grid_size = grid_size
        self.difficulty = difficulty
        self.grid = []
        self.rotations = []
        self.solution_rotations = []  # Store the solution for checking
        self.input_pos = (0, random.randint(0, grid_size - 1))
        self.output_pos = (grid_size - 1, random.randint(0, grid_size - 1))
        self._generate_puzzle()

    def _generate_puzzle(self):
        """Generate solvable puzzle by creating path then scrambling"""
        self.grid = [[0 for _ in range(self.grid_size)] for _ in range(self.grid_size)]
        self.rotations = [[0 for _ in range(self.grid_size)] for _ in range(self.grid_size)]
        self.solution_rotations = [[0 for _ in range(self.grid_size)] for _ in range(self.grid_size)]

        # Create path from input to output using BFS-like generation
        current = list(self.input_pos)
        path = [tuple(current)]
        visited = {tuple(current)}

        # Build a winding path to output
        while tuple(current) != self.output_pos:
            # Get valid neighbors
            neighbors = []
            for dr, dc in [(0, 1), (1, 0), (0, -1), (-1, 0)]:
                nr, nc = current[0] + dr, current[1] + dc
                if 0 <= nr < self.grid_size and 0 <= nc < self.grid_size and (nr, nc) not in visited:
                    # Prefer moving towards output
                    dist = abs(nr - self.output_pos[0]) + abs(nc - self.output_pos[1])
                    neighbors.append(((nr, nc), dist))

            if not neighbors:
                # Backtrack if stuck
                if len(path) > 1:
                    path.pop()
                    current = list(path[-1])
                    continue
                else:
                    break

            # Choose next cell (biased towards output)
            neighbors.sort(key=lambda x: x[1])
            next_pos = neighbors[0][0] if random.random() < 0.7 else random.choice(neighbors)[0]
            current = list(next_pos)
            path.append(tuple(current))
            visited.add(tuple(current))

        # Convert path to pipe pieces
        for i, (r, c) in enumerate(path):
            if i == 0:
                # Input piece
                next_r, next_c = path[i + 1]
                self.grid[r][c], self.rotations[r][c] = self._get_piece_for_connection(r, c, next_r, next_c)
            elif i == len(path) - 1:
                # Output piece
                prev_r, prev_c = path[i - 1]
                self.grid[r][c], self.rotations[r][c] = self._get_piece_for_connection(r, c, prev_r, prev_c)
            else:
                # Middle pieces
                prev_r, prev_c = path[i - 1]
                next_r, next_c = path[i + 1]
                self.grid[r][c], self.rotations[r][c] = self._get_piece_for_two_connections(r, c, prev_r, prev_c, next_r, next_c)

        # Add some extra pieces for difficulty (based on difficulty level)
        extra_pieces = {"easy": 2, "medium": 4, "hard": 6}.get(self.difficulty, 2)
        for _ in range(extra_pieces):
            r, c = random.randint(0, self.grid_size - 1), random.randint(0, self.grid_size - 1)
            if self.grid[r][c] == 0:  # Only place in empty cells
                self.grid[r][c] = random.choice([1, 2])
                self.rotations[r][c] = random.choice([0, 90, 180, 270])

        # Save solution
        self.solution_rotations = [row[:] for row in self.rotations]

        # Scramble by rotating pieces randomly
        scramble_count = self.grid_size * 2
        for _ in range(scramble_count):
            r, c = random.randint(0, self.grid_size - 1), random.randint(0, self.grid_size - 1)
            if self.grid[r][c] not in [0, 4]:  # Don't rotate empty or cross pieces
                self.rotations[r][c] = random.choice([0, 90, 180, 270])

    def _get_piece_for_connection(self, r, c, target_r, target_c):
        """Get piece type and rotation for connecting to one neighbor"""
        # Determine direction to target
        if target_r < r:  # target above
            return 1, 90  # Straight vertical
        elif target_r > r:  # target below
            return 1, 90
        elif target_c < c:  # target left
            return 1, 0  # Straight horizontal
        else:  # target right
            return 1, 0

    def _get_piece_for_two_connections(self, r, c, prev_r, prev_c, next_r, next_c):
        """Get piece type and rotation for connecting to two neighbors"""
        # Determine directions
        dirs = []
        if prev_r < r or next_r < r:
            dirs.append(0)  # top
        if prev_c > c or next_c > c:
            dirs.append(1)  # right
        if prev_r > r or next_r > r:
            dirs.append(2)  # bottom
        if prev_c < c or next_c < c:
            dirs.append(3)  # left

        # If straight line, use straight piece
        if set(dirs) == {0, 2} or set(dirs) == {1, 3}:
            return 1, 90 if 0 in dirs else 0

        # Otherwise use L-bend and find correct rotation
        for rot in [0, 90, 180, 270]:
            connections = self.CONNECTIONS[2][rot]
            if set(connections) == set(dirs):
                return 2, rot

        return 2, 0  # Fallback

    def rotate_piece(self, row, col):
        """Rotate piece at position clockwise 90°"""
        if 0 <= row < self.grid_size and 0 <= col < self.grid_size:
            if self.grid[row][col] not in [0, 4]:  # Can't rotate empty or cross
                self.rotations[row][col] = (self.rotations[row][col] + 90) % 360
                return True
        return False

    def check_solution(self):
        """Check if all pieces are correctly connected"""
        # Check each piece has matching connections with neighbors
        for r in range(self.grid_size):
            for c in range(self.grid_size):
                if self.grid[r][c] == 0:
                    continue

                piece_type = self.grid[r][c]
                rotation = self.rotations[r][c]
                connections = self.CONNECTIONS[piece_type][rotation]

                # Check each connection direction
                for side in connections:
                    nr, nc = r, c
                    if side == 0:  # top
                        nr -= 1
                        opposite = 2
                    elif side == 1:  # right
                        nc += 1
                        opposite = 3
                    elif side == 2:  # bottom
                        nr += 1
                        opposite = 0
                    else:  # left
                        nc -= 1
                        opposite = 1

                    # Check if neighbor exists and connects back
                    if 0 <= nr < self.grid_size and 0 <= nc < self.grid_size:
                        neighbor_type = self.grid[nr][nc]
                        if neighbor_type == 0:
                            return False  # Connection to empty space
                        neighbor_rot = self.rotations[nr][nc]
                        neighbor_connections = self.CONNECTIONS[neighbor_type][neighbor_rot]
                        if opposite not in neighbor_connections:
                            return False  # Neighbor doesn't connect back
                    else:
                        # Edge connection only allowed at input/output
                        if (r, c) not in [self.input_pos, self.output_pos]:
                            return False

                # Check that piece doesn't have unconnected sides (except at edges)
                for side in range(4):
                    if side in connections:
                        continue
                    nr, nc = r, c
                    if side == 0:
                        nr -= 1
                    elif side == 1:
                        nc += 1
                    elif side == 2:
                        nr += 1
                    else:
                        nc -= 1

                    # If there's a neighbor with a connection pointing to us, fail
                    if 0 <= nr < self.grid_size and 0 <= nc < self.grid_size:
                        neighbor_type = self.grid[nr][nc]
                        if neighbor_type != 0:
                            opposite = (side + 2) % 4
                            neighbor_rot = self.rotations[nr][nc]
                            neighbor_connections = self.CONNECTIONS[neighbor_type][neighbor_rot]
                            if opposite in neighbor_connections:
                                return False

        return True

    def get_state(self):
        """Get puzzle state for rendering"""
        return {
            "grid_size": self.grid_size,
            "grid": self.grid,
            "rotations": self.rotations,
            "input_pos": self.input_pos,
            "output_pos": self.output_pos,
            "solved": self.check_solution()
        }


class SlidingTilePuzzle:
    """
    Sliding tile puzzle - T2 Engineering

    Goal: Arrange numbered tiles in order by sliding into empty space
    Classic sliding puzzle (3x3 or 4x4)

    [PLACEHOLDER - To be fully implemented]
    """

    def __init__(self, grid_size=3):
        """
        Initialize sliding tile puzzle

        Args:
            grid_size: Grid size (3 or 4)
        """
        self.grid_size = grid_size
        self.grid = []
        self.empty_pos = (grid_size - 1, grid_size - 1)
        self._generate_puzzle()

    def _generate_puzzle(self):
        """Generate solvable sliding puzzle"""
        # TODO: Implement proper puzzle generation
        # For now, simple placeholder
        self.grid = [[0 for _ in range(self.grid_size)] for _ in range(self.grid_size)]
        num = 1
        for r in range(self.grid_size):
            for c in range(self.grid_size):
                if (r, c) != self.empty_pos:
                    self.grid[r][c] = num
                    num += 1

    def slide_tile(self, row, col):
        """Slide tile at position into empty space"""
        # TODO: Implement sliding logic
        pass

    def check_solution(self):
        """Check if puzzle is solved"""
        # TODO: Implement solution checking
        return False

    def get_state(self):
        """Get puzzle state"""
        return {
            "grid_size": self.grid_size,
            "grid": self.grid,
            "empty_pos": self.empty_pos,
            "solved": self.check_solution()
        }


# Placeholder for Traffic Jam Puzzle (T3)
class TrafficJamPuzzle:
    """
    Traffic jam puzzle - T3 Engineering

    [PLACEHOLDER FOR FUTURE IMPLEMENTATION]

    Goal: Slide blocks to move target piece to exit
    - 6x6 grid
    - Various sized blocks (1x2, 1x3, 2x2, 2x3)
    - Blocks slide in direction of orientation only
    """

    def __init__(self):
        self.solved = False

    def get_state(self):
        return {"solved": self.solved, "placeholder": True}


# Placeholder for Pattern Matching Puzzle (T4)
class PatternMatchingPuzzle:
    """
    Pattern matching + logic grid puzzle - T4 Engineering

    [PLACEHOLDER FOR FUTURE IMPLEMENTATION]

    Goal: Complete patterns following rules
    - Symmetry, no adjacent same, tiling
    - Logic grid constraints (power flow, wiring, no loops)
    """

    def __init__(self):
        self.solved = False

    def get_state(self):
        return {"solved": self.solved, "placeholder": True}


class EngineeringMinigame:
    """
    Engineering minigame implementation - Sequential puzzle solving

    Process:
    1. Create device from slot configuration
    2. Solve sequence of puzzles (1-6 puzzles based on tier/rarity)
    3. Each puzzle affects different device stat
    4. No failure state - untimed, unlimited attempts
    5. Can save and resume progress
    """

    def __init__(self, recipe, tier=1, material_rarity="common", buff_time_bonus=0.0, buff_quality_bonus=0.0):
        """
        Initialize engineering minigame

        Args:
            recipe: Recipe dict from JSON
            tier: Recipe tier (1-4)
            material_rarity: Highest material rarity (affects puzzle count)
            buff_time_bonus: Skill buff bonus to time limit (0.0-1.0+)
            buff_quality_bonus: Skill buff bonus to quality (0.0-1.0+)
        """
        self.recipe = recipe
        self.tier = tier
        self.material_rarity = material_rarity
        self.buff_time_bonus = buff_time_bonus
        self.buff_quality_bonus = buff_quality_bonus

        # Determine puzzle count based on tier and rarity
        self._setup_difficulty()

        # Game state
        self.active = False
        self.puzzles = []
        self.current_puzzle_index = 0
        self.solved_puzzles = []
        self.result = None

    def _setup_difficulty(self):
        """
        Setup puzzle count and types based on tier and rarity

        NOTE: Puzzle count formula may be expanded in future updates
        Currently: tier + rarity based
        """
        # Puzzle count based on tier and rarity
        if self.tier == 1:
            base_count = 1
        elif self.tier == 2:
            base_count = 2
        elif self.tier == 3:
            base_count = 3
        else:  # tier 4
            base_count = 4

        # Add puzzles for rarity
        rarity_bonus = {
            "common": 0,
            "uncommon": 1,
            "rare": 2,
            "epic": 2,
            "legendary": 3
        }
        self.puzzle_count = base_count + rarity_bonus.get(self.material_rarity, 0)
        self.puzzle_count = min(6, self.puzzle_count)  # Max 6 puzzles

    def start(self):
        """Start the minigame"""
        self.active = True
        self.current_puzzle_index = 0
        self.solved_puzzles = []
        self.result = None

        # Generate puzzles based on tier
        self.puzzles = []
        for i in range(self.puzzle_count):
            puzzle = self._create_puzzle_for_tier(i)
            self.puzzles.append(puzzle)

    def _create_puzzle_for_tier(self, index):
        """
        Create appropriate puzzle based on tier

        Args:
            index: Puzzle index in sequence

        Returns:
            Puzzle instance
        """
        if self.tier == 1:
            # T1: Only rotation puzzles
            grid_size = 3 if index == 0 else 4
            return RotationPipePuzzle(grid_size, "easy")
        elif self.tier == 2:
            # T2: Rotation and sliding
            if index % 2 == 0:
                return RotationPipePuzzle(5, "medium")
            else:
                return SlidingTilePuzzle(3)
        elif self.tier == 3:
            # T3: Include traffic jam (placeholder)
            if index % 3 == 0:
                return RotationPipePuzzle(5, "hard")
            elif index % 3 == 1:
                return SlidingTilePuzzle(4)
            else:
                return TrafficJamPuzzle()  # Placeholder
        else:  # tier 4
            # T4: All puzzle types including pattern matching
            puzzle_type = index % 4
            if puzzle_type == 0:
                return RotationPipePuzzle(5, "hard")
            elif puzzle_type == 1:
                return SlidingTilePuzzle(4)
            elif puzzle_type == 2:
                return TrafficJamPuzzle()  # Placeholder
            else:
                return PatternMatchingPuzzle()  # Placeholder

    def handle_action(self, action_type, **kwargs):
        """
        Handle puzzle action (rotate, slide, etc.)

        Args:
            action_type: Type of action ("rotate", "slide", etc.)
            **kwargs: Action parameters

        Returns:
            bool: True if action was valid
        """
        if not self.active or self.current_puzzle_index >= len(self.puzzles):
            return False

        current_puzzle = self.puzzles[self.current_puzzle_index]

        if action_type == "rotate" and isinstance(current_puzzle, RotationPipePuzzle):
            row = kwargs.get('row', 0)
            col = kwargs.get('col', 0)
            return current_puzzle.rotate_piece(row, col)
        elif action_type == "slide" and isinstance(current_puzzle, SlidingTilePuzzle):
            row = kwargs.get('row', 0)
            col = kwargs.get('col', 0)
            return current_puzzle.slide_tile(row, col)

        return False

    def check_current_puzzle(self):
        """
        Check if current puzzle is solved

        Returns:
            bool: True if solved
        """
        if self.current_puzzle_index >= len(self.puzzles):
            return False

        current_puzzle = self.puzzles[self.current_puzzle_index]

        if current_puzzle.check_solution():
            # Puzzle solved! Move to next
            self.solved_puzzles.append(current_puzzle)
            self.current_puzzle_index += 1

            # Check if all puzzles done
            if self.current_puzzle_index >= len(self.puzzles):
                self.end()

            return True

        return False

    def abandon(self):
        """
        Abandon device creation

        Returns 50% of materials
        """
        self.active = False
        self.result = {
            "success": False,
            "abandoned": True,
            "materials_returned": 0.5,
            "message": "Device creation abandoned - 50% materials returned"
        }

    def save_progress(self):
        """
        Save current progress (for resuming later)

        Returns:
            dict: Save state
        """
        return {
            "recipe_id": self.recipe.get('recipeId'),
            "current_puzzle_index": self.current_puzzle_index,
            "puzzle_states": [p.get_state() for p in self.puzzles],
            "solved_count": len(self.solved_puzzles)
        }

    def load_progress(self, save_state):
        """
        Load saved progress

        Args:
            save_state: Previously saved state dict
        """
        # TODO: Implement state loading
        pass

    def end(self):
        """Complete device creation with stat modifications (Game Mechanics v5)"""
        self.active = False

        # Calculate device stats based on puzzle performance
        # Each puzzle affects a different aspect of the device
        stats = {
            "durability": 100,  # Base stats
            "efficiency": 100,
            "accuracy": 100,
            "power": 100
        }

        # Each solved puzzle adds +10-20% to its corresponding stat
        stat_types = ["durability", "efficiency", "accuracy", "power"]
        for i, puzzle in enumerate(self.solved_puzzles):
            stat_type = stat_types[i % len(stat_types)]
            # Bonus based on how well puzzle was solved (10-20%)
            bonus = 15  # Could be adjusted based on puzzle difficulty
            stats[stat_type] += bonus

        # Calculate overall quality (avg of all stats)
        quality = sum(stats.values()) / (len(stats) * 100)

        self.result = {
            "success": True,
            "puzzles_solved": len(self.solved_puzzles),
            "total_puzzles": self.puzzle_count,
            "stats": stats,
            "quality": quality,
            "message": f"Device created! Solved {len(self.solved_puzzles)} puzzles."
        }

    def get_state(self):
        """Get current minigame state for rendering"""
        current_puzzle = None
        if self.current_puzzle_index < len(self.puzzles):
            current_puzzle = self.puzzles[self.current_puzzle_index].get_state()

        return {
            "active": self.active,
            "current_puzzle_index": self.current_puzzle_index,
            "total_puzzles": self.puzzle_count,
            "current_puzzle": current_puzzle,
            "solved_count": len(self.solved_puzzles),
            "result": self.result
        }


class EngineeringCrafter:
    """
    Main engineering crafting interface

    Handles:
    - Recipe loading from JSON
    - Slot-based device creation
    - Material validation
    - Instant crafting (skip minigame)
    - Minigame crafting (puzzle solving)
    """

    def __init__(self):
        """Initialize engineering crafter"""
        self.recipes = {}
        self.placements = {}
        self.load_recipes()
        self.load_placements()

    def load_recipes(self):
        """Load engineering recipes from JSON files"""
        possible_paths = [
            "../recipes.JSON/recipes-engineering-1.json",
            "recipes.JSON/recipes-engineering-1.json",
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
            print(f"[Engineering] Loaded {len(self.recipes)} recipes")
        else:
            print("[Engineering] WARNING: No recipes loaded")

    
    def load_placements(self):
        """Load placement data from JSON files"""
        possible_paths = [
            "../placements.JSON/placements-engineering-1.JSON",
            "placements.JSON/placements-engineering-1.JSON",
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
            print(f"[Engineering] Loaded {len(self.placements)} placements")

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
        Instant craft (no minigame) - produces base device

        Args:
            recipe_id: Recipe ID to craft
            inventory: Dict of {material_id: quantity} (will be modified)
            item_metadata: Optional dict of item metadata for category lookup

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

        return {
            "success": True,
            "outputId": recipe['outputId'],
            "quantity": recipe['outputQty'],
            "rarity": input_rarity,
            "message": f"Device created ({input_rarity})"
        }

    def create_minigame(self, recipe_id, buff_time_bonus=0.0, buff_quality_bonus=0.0, material_rarity="common"):
        """
        Create an engineering minigame for this recipe

        Args:
            recipe_id: Recipe ID to craft
            buff_time_bonus: Skill buff bonus to time limit (0.0-1.0+)
            buff_quality_bonus: Skill buff bonus to quality (0.0-1.0+)
            material_rarity: Highest material rarity used

        Returns:
            EngineeringMinigame instance or None
        """
        if recipe_id not in self.recipes:
            return None

        recipe = self.recipes[recipe_id]
        tier = recipe.get('stationTier', 1)

        return EngineeringMinigame(recipe, tier, material_rarity, buff_time_bonus, buff_quality_bonus)

    def craft_with_minigame(self, recipe_id, inventory, minigame_result, item_metadata=None):
        """
        Craft with minigame result with rarity modifiers

        Args:
            recipe_id: Recipe ID to craft
            inventory: Dict of {material_id: quantity} (will be modified)
            minigame_result: Result dict from EngineeringMinigame
            item_metadata: Optional dict of item metadata for category lookup

        Returns:
            dict: Result with outputId, rarity, stats, success
        """
        recipe = self.recipes[recipe_id]

        if minigame_result.get('abandoned'):
            # Abandoned - return 50% materials
            for inp in recipe['inputs']:
                returned = inp['quantity'] // 2
                inventory[inp['materialId']] += returned

            return {
                "success": False,
                "message": "Device creation abandoned",
                "materials_returned": True
            }

        if not minigame_result.get('success'):
            # Failed somehow (shouldn't happen in engineering)
            return {
                "success": False,
                "message": "Device creation failed"
            }

        # Success - deduct full materials
        for inp in recipe['inputs']:
            inventory[inp['materialId']] -= inp['quantity']

        # Detect input rarity
        inputs = recipe.get('inputs', [])
        _, input_rarity, _ = rarity_system.check_rarity_uniformity(inputs)

        # Get device stats from minigame result
        base_stats = minigame_result.get('stats', {})
        quality = minigame_result.get('quality', 1.0)

        # Get item category and apply rarity modifiers
        output_id = recipe['outputId']
        if item_metadata is None:
            item_metadata = {}

        item_category = rarity_system.get_item_category(output_id, item_metadata)
        modified_stats = rarity_system.apply_rarity_modifiers(base_stats, item_category, input_rarity)

        result = {
            "success": True,
            "outputId": output_id,
            "quantity": recipe['outputQty'],
            "rarity": input_rarity,
            "message": f"Created {input_rarity} device successfully!"
        }

        # Add stats if present (from puzzle performance and rarity)
        if modified_stats:
            result["stats"] = modified_stats
            result["quality"] = quality

        return result

    def get_recipe(self, recipe_id):
        """Get recipe by ID"""
        return self.recipes.get(recipe_id)

    def get_all_recipes(self):
        """Get all loaded recipes"""
        return self.recipes

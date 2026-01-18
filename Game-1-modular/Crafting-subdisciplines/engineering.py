"""
Engineering Crafting Subdiscipline

Framework:
- Python module ready for main.py integration
- Loads recipes from JSON files
- Optional minigame (sequential cognitive puzzles)
- Difficulty based on material tier points × diversity × slot count

Difficulty System (v2):
- Material points: tier × quantity per material (LINEAR)
- Diversity multiplier: 1.0 + (unique_materials - 1) × 0.1
- Slot modifier: 1.0 + (total_slots - 1) × 0.05
- Higher difficulty = more puzzles, larger grids, fewer hints

Minigame: Sequential cognitive puzzle solving
- Pure problem-solving, no timing, no dexterity
- Multiple puzzles per device (1-4 based on difficulty)
- Rotation pipe puzzles (Common/Uncommon)
- Sliding tile puzzles (Rare+)
- Traffic jam puzzles (Epic+) [PLACEHOLDER]
- Pattern matching + logic grids (Legendary) [PLACEHOLDER]

Failure Penalty System:
- Low difficulty: 30% material loss (if quit early)
- High difficulty: 90% material loss
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
        self.ideal_path_length = 0  # Minimum possible path (Manhattan distance + 1)
        self.actual_path_length = 0  # Generated path length
        self.clicks = 0  # Track number of rotations made
        self._generate_puzzle()

    def _generate_puzzle(self):
        """Generate solvable puzzle by creating path then scrambling"""
        self.grid = [[0 for _ in range(self.grid_size)] for _ in range(self.grid_size)]
        self.rotations = [[0 for _ in range(self.grid_size)] for _ in range(self.grid_size)]
        self.solution_rotations = [[0 for _ in range(self.grid_size)] for _ in range(self.grid_size)]

        # Calculate ideal path length (Manhattan distance + 1 for inclusive count)
        self.ideal_path_length = abs(self.output_pos[0] - self.input_pos[0]) + \
                                  abs(self.output_pos[1] - self.input_pos[1]) + 1

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

        # Store actual path length for efficiency scoring
        self.actual_path_length = len(path)
        self.path_cells = set(path)  # Store path cells for reference

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

        # Fill ALL empty spaces with random pipes (not part of solution path)
        for r in range(self.grid_size):
            for c in range(self.grid_size):
                if self.grid[r][c] == 0:  # Empty cell
                    # Add random pipe piece (1=straight, 2=L-bend, 3=T-junction)
                    self.grid[r][c] = random.choice([1, 2, 2, 3])  # More L-bends for visual variety
                    self.rotations[r][c] = random.choice([0, 90, 180, 270])

        # Save solution (only path pieces matter, others are distractors)
        self.solution_rotations = [row[:] for row in self.rotations]
        # Restore correct rotations only for path cells
        for r, c in path:
            # Find the correct rotation for this path cell
            pass  # Already set correctly above

        # Scramble ALL pieces (including distractors)
        for r in range(self.grid_size):
            for c in range(self.grid_size):
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
                self.clicks += 1
                return True
        return False

    def get_efficiency_score(self):
        """
        Calculate efficiency score based on path length vs ideal.

        The actual_path_length is how many cells the generated path uses.
        The ideal_path_length is the Manhattan distance + 1.
        Efficiency = ideal / actual (capped at 1.0 for perfect path)

        Returns:
            float: Score from 0.0 to 1.0
        """
        if self.actual_path_length == 0:
            return 1.0
        # Efficiency based on how close to ideal path
        ratio = self.ideal_path_length / self.actual_path_length
        return min(1.0, ratio)  # Cap at 1.0 (perfect efficiency)

    def check_solution(self):
        """
        Check if puzzle is solved by verifying there's a valid path from input to output
        Uses BFS to find path through connected pipes
        """
        # BFS to find path from input to output
        from collections import deque

        visited = set()
        queue = deque([self.input_pos])
        visited.add(self.input_pos)

        while queue:
            r, c = queue.popleft()

            # Reached output!
            if (r, c) == self.output_pos:
                return True

            # Get connections from current piece
            piece_type = self.grid[r][c]
            if piece_type == 0:
                continue

            rotation = self.rotations[r][c]
            connections = self.CONNECTIONS[piece_type][rotation]

            # Check each connection direction
            for side in connections:
                nr, nc = r, c
                opposite = -1

                if side == 0:  # top
                    nr -= 1
                    opposite = 2  # bottom of neighbor
                elif side == 1:  # right
                    nc += 1
                    opposite = 3  # left of neighbor
                elif side == 2:  # bottom
                    nr += 1
                    opposite = 0  # top of neighbor
                else:  # left
                    nc -= 1
                    opposite = 1  # right of neighbor

                # Check if neighbor is valid and connects back
                if 0 <= nr < self.grid_size and 0 <= nc < self.grid_size:
                    if (nr, nc) in visited:
                        continue

                    neighbor_type = self.grid[nr][nc]
                    if neighbor_type == 0:
                        continue  # Empty cell, can't connect

                    neighbor_rot = self.rotations[nr][nc]
                    neighbor_connections = self.CONNECTIONS[neighbor_type][neighbor_rot]

                    # Check if neighbor connects back to us
                    if opposite in neighbor_connections:
                        visited.add((nr, nc))
                        queue.append((nr, nc))

        # Didn't reach output
        return False

    def get_state(self):
        """Get puzzle state for rendering"""
        return {
            "puzzle_type": "rotation_pipe",
            "grid_size": self.grid_size,
            "grid": self.grid,
            "rotations": self.rotations,
            "input_pos": self.input_pos,
            "output_pos": self.output_pos,
            "solved": self.check_solution(),
            "clicks": self.clicks,
            "ideal_path_length": self.ideal_path_length,
            "actual_path_length": self.actual_path_length,
            "efficiency": self.get_efficiency_score()
        }


class LogicSwitchPuzzle:
    """
    Logic Switch Puzzle - Replacement for sliding tile puzzle

    Goal: Toggle switches to match the target pattern
    - Clicking a switch toggles it AND its orthogonal neighbors (lights-out style)
    - Has calculable minimum solution for scoring
    - Easy to understand, difficulty scales with grid size and pattern complexity

    Puzzle Modes (in order of difficulty):
    A. random -> fully_lit: Random start, all-on target (easiest)
    B. random -> fully_dim: Random start, all-off target
    C. fully_dim -> random: All-off start, random target
    D. fully_lit -> random: All-on start, random target (hardest)

    Scoring: Based on moves vs ideal solution
    - Perfect (ideal moves) = 100% reward
    - More moves = exponential decay: reward * e^-(moves/ideal - 1)
    - Time limit adds pressure without failing instantly
    """

    def __init__(self, grid_size=3, difficulty="easy", max_moves=10, force_mode=None):
        """
        Initialize logic switch puzzle

        Args:
            grid_size: Grid size (3-6)
            difficulty: "easy", "medium", "hard" - affects puzzle mode
            max_moves: Maximum ideal moves (default 10 for solvability)
            force_mode: Optional specific mode to use ("random_to_lit", "random_to_dim",
                       "dim_to_random", "lit_to_random")
        """
        self.grid_size = grid_size
        self.difficulty = difficulty
        self.max_moves = max_moves
        self.force_mode = force_mode
        self.grid = []  # Current state (0=off, 1=on)
        self.target = []  # Target pattern to match
        self.initial_grid = []  # Store initial state for reset
        self.moves = 0
        self.ideal_moves = 0  # Minimum moves to solve
        self.solution_path = []  # Cells to toggle for ideal solution
        self.puzzle_mode = ""  # Describes the puzzle type
        self._generate_puzzle()

    def _generate_puzzle(self):
        """Generate solvable puzzle using exactly max_moves (10) random clicks"""
        # Use forced mode if specified, otherwise determine from difficulty
        if self.force_mode:
            self._generate_from_mode(self.force_mode)
        elif self.difficulty == "easy":
            # Mode A or B: Random start, uniform target
            mode = random.choice(["random_to_lit", "random_to_dim"])
            self._generate_from_mode(mode)
        elif self.difficulty == "medium":
            # Mode C or D: Uniform start, random target (reversed)
            mode = random.choice(["dim_to_random", "lit_to_random"])
            self._generate_from_mode(mode)
        else:  # hard
            # Mode D preferred: All lit -> random (hardest visual)
            self._generate_from_mode("lit_to_random")

    def _generate_from_mode(self, mode):
        """Generate puzzle from specific mode using exactly max_moves toggles"""
        num_toggles = self.max_moves  # Always use exactly max_moves (10)

        if mode == "random_to_lit":
            # Start from all lit, apply 10 toggles -> that becomes player start
            # Target is all lit
            self.puzzle_mode = "random -> fully_lit"
            self._generate_forward(target_state=1, num_toggles=num_toggles)

        elif mode == "random_to_dim":
            # Start from all dim, apply 10 toggles -> that becomes player start
            # Target is all dim
            self.puzzle_mode = "random -> fully_dim"
            self._generate_forward(target_state=0, num_toggles=num_toggles)

        elif mode == "dim_to_random":
            # Player starts at all dim
            # Apply 10 toggles to get target pattern
            self.puzzle_mode = "fully_dim -> random"
            self._generate_reversed(start_state=0, num_toggles=num_toggles)

        elif mode == "lit_to_random":
            # Player starts at all lit
            # Apply 10 toggles to get target pattern
            self.puzzle_mode = "fully_lit -> random"
            self._generate_reversed(start_state=1, num_toggles=num_toggles)

    def _generate_forward(self, target_state, num_toggles):
        """Generate puzzle: random start -> uniform target

        Process:
        1. Set target to uniform state (all lit or all dim)
        2. Start grid at target state
        3. Apply exactly num_toggles random clicks to create scrambled start
        4. The solution is reversing those clicks
        """
        # Target is uniform (all lit or all dim)
        self.target = [[target_state for _ in range(self.grid_size)] for _ in range(self.grid_size)]

        # Start with target state
        self.grid = [row[:] for row in self.target]

        # Apply exactly num_toggles random toggles to create the puzzle starting state
        self.solution_path = []
        cells_used = set()

        for _ in range(num_toggles):
            available = [(r, c) for r in range(self.grid_size) for c in range(self.grid_size)
                        if (r, c) not in cells_used]
            if not available:
                # Reset used cells if we've used all (shouldn't happen with 10 moves on 3x3+)
                cells_used.clear()
                available = [(r, c) for r in range(self.grid_size) for c in range(self.grid_size)]

            r, c = random.choice(available)
            cells_used.add((r, c))
            self.solution_path.append((r, c))
            self._do_toggle(r, c)

        self.ideal_moves = len(self.solution_path)
        self.moves = 0
        # Store initial grid state for reset
        self.initial_grid = [row[:] for row in self.grid]

    def _generate_reversed(self, start_state, num_toggles):
        """Generate puzzle: uniform start -> random target (reversed mode)

        Process:
        1. Set player start to uniform state (all lit or all dim)
        2. Copy to target
        3. Apply exactly num_toggles random clicks to target to create goal
        4. The solution is those same clicks applied to start
        """
        # Start is uniform (all lit or all dim)
        self.grid = [[start_state for _ in range(self.grid_size)] for _ in range(self.grid_size)]

        # Build target by applying random toggles to a copy
        self.target = [row[:] for row in self.grid]
        self.solution_path = []
        cells_used = set()

        for _ in range(num_toggles):
            available = [(r, c) for r in range(self.grid_size) for c in range(self.grid_size)
                        if (r, c) not in cells_used]
            if not available:
                cells_used.clear()
                available = [(r, c) for r in range(self.grid_size) for c in range(self.grid_size)]

            r, c = random.choice(available)
            cells_used.add((r, c))
            self.solution_path.append((r, c))
            # Toggle in target, not in grid
            self._toggle_in_grid(self.target, r, c)

        self.ideal_moves = len(self.solution_path)
        self.moves = 0
        # Store initial grid state for reset
        self.initial_grid = [row[:] for row in self.grid]

    def _toggle_in_grid(self, grid, row, col):
        """Toggle a cell and its neighbors in a specific grid"""
        grid[row][col] = 1 - grid[row][col]
        for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
            nr, nc = row + dr, col + dc
            if 0 <= nr < self.grid_size and 0 <= nc < self.grid_size:
                grid[nr][nc] = 1 - grid[nr][nc]

    def _do_toggle(self, row, col):
        """Toggle a cell and its neighbors (internal, doesn't count moves)"""
        # Toggle center
        self.grid[row][col] = 1 - self.grid[row][col]

        # Toggle orthogonal neighbors
        for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
            nr, nc = row + dr, col + dc
            if 0 <= nr < self.grid_size and 0 <= nc < self.grid_size:
                self.grid[nr][nc] = 1 - self.grid[nr][nc]

    def toggle_switch(self, row, col):
        """
        Toggle switch at position (player action)

        Args:
            row, col: Position to toggle

        Returns:
            bool: True if toggle was valid
        """
        if 0 <= row < self.grid_size and 0 <= col < self.grid_size:
            self._do_toggle(row, col)
            self.moves += 1
            return True
        return False

    def reset(self):
        """Reset grid to initial state (for retry)"""
        self.grid = [row[:] for row in self.initial_grid]
        self.moves = 0

    def check_solution(self):
        """Check if current grid matches target pattern"""
        for r in range(self.grid_size):
            for c in range(self.grid_size):
                if self.grid[r][c] != self.target[r][c]:
                    return False
        return True

    def get_efficiency_score(self):
        """
        Calculate efficiency score based on moves vs ideal

        Returns:
            float: Score from 0.0 to 1.0
        """
        import math
        if self.ideal_moves == 0:
            return 1.0
        ratio = self.moves / self.ideal_moves
        if ratio <= 1.0:
            return 1.0
        # Exponential decay: e^-(ratio - 1)
        return math.exp(-(ratio - 1))

    def get_state(self):
        """Get puzzle state"""
        return {
            "puzzle_type": "logic_switch",
            "puzzle_mode": self.puzzle_mode,
            "grid_size": self.grid_size,
            "grid": self.grid,
            "target": self.target,
            "initial_grid": self.initial_grid,
            "moves": self.moves,
            "ideal_moves": self.ideal_moves,
            "max_moves": self.max_moves,
            "efficiency": self.get_efficiency_score(),
            "solved": self.check_solution()
        }


class SlidingTilePuzzle:
    """
    DEPRECATED: Replaced by LogicSwitchPuzzle

    Kept for backwards compatibility with existing save files.
    New games should use LogicSwitchPuzzle instead.
    """

    def __init__(self, grid_size=3):
        """Initialize as a simple auto-solve puzzle for compatibility"""
        self.grid_size = grid_size
        self.grid = [[0 for _ in range(grid_size)] for _ in range(grid_size)]
        self.moves = 0
        self.solved = False
        # Mark as deprecated - auto-completes
        print("[WARNING] SlidingTilePuzzle is deprecated, using auto-complete")

    def slide_tile(self, row, col):
        """Auto-solve on any action"""
        self.solved = True
        return True

    def check_solution(self):
        """Always returns True (deprecated puzzle)"""
        return True

    def get_state(self):
        return {
            "grid_size": self.grid_size,
            "grid": self.grid,
            "moves": self.moves,
            "solved": True,
            "deprecated": True
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

    def __init__(self, recipe, buff_time_bonus=0.0, buff_quality_bonus=0.0):
        """
        Initialize engineering minigame

        Args:
            recipe: Recipe dict from JSON (includes inputs for difficulty calculation)
            buff_time_bonus: Skill buff bonus to time limit (0.0-1.0+)
            buff_quality_bonus: Skill buff bonus to quality (0.0-1.0+)
        """
        self.recipe = recipe
        self.buff_time_bonus = buff_time_bonus
        self.buff_quality_bonus = buff_quality_bonus

        # Track attempts for first-try bonus
        self.attempt = 1
        self.hints_used = 0
        self.start_time = None

        # Determine puzzle count based on material difficulty
        self._setup_difficulty_from_materials()

        # Game state
        self.active = False
        self.puzzles = []
        self.current_puzzle_index = 0
        self.solved_puzzles = []
        self.result = None

    def _setup_difficulty_from_materials(self):
        """
        Setup puzzle count and complexity based on material tier points.

        Uses the centralized difficulty calculator for consistent scaling.
        """
        try:
            from core.difficulty_calculator import calculate_engineering_difficulty
            params = calculate_engineering_difficulty(self.recipe)

            self.difficulty_points = params['difficulty_points']
            self.difficulty_tier = params.get('difficulty_tier', 'common')
            self.time_limit = params['time_limit']
            self.puzzle_count = max(2, params['puzzle_count'])  # Always at least 2 (rotation + logic switch)
            self.grid_size = params['grid_size']
            self.complexity = params['complexity']
            self.hints_allowed = params['hints_allowed']
            self.slot_modifier = params.get('slot_modifier', 1.0)
            self.total_slots = params.get('total_slots', 1)
            self.ideal_moves = params.get('ideal_moves', 7)  # 6-8 range based on difficulty

            print(f"[Engineering] Difficulty: {self.difficulty_points:.1f} pts ({self.difficulty_tier})")
            print(f"             Puzzles: {self.puzzle_count}, Grid: {self.grid_size}x{self.grid_size}, Ideal moves: {self.ideal_moves}")

        except ImportError:
            # Fallback to legacy tier-based system
            tier = self.recipe.get('stationTier', 1)
            self._setup_difficulty_legacy(tier)

    def _setup_difficulty_legacy(self, tier):
        """Legacy tier-based difficulty for backward compatibility."""
        self.difficulty_points = tier * 15
        self.difficulty_tier = ['common', 'uncommon', 'rare', 'epic'][min(tier - 1, 3)]
        self.time_limit = 300
        self.grid_size = 3 + tier
        self.complexity = tier
        self.hints_allowed = max(0, 4 - tier)
        self.slot_modifier = 1.0
        self.total_slots = 1
        # Ideal moves scales with tier: T1=6, T2=6, T3=7, T4=8
        self.ideal_moves = min(8, 5 + tier)

        # Puzzle count based on tier (minimum 2 for rotation + logic switch)
        if tier == 1:
            self.puzzle_count = 2  # Always at least 2
        elif tier == 2:
            self.puzzle_count = 2
        elif tier == 3:
            self.puzzle_count = 3
        else:  # tier 4
            self.puzzle_count = 4

    def start(self):
        """Start the minigame"""
        import time
        self.active = True
        self.current_puzzle_index = 0
        self.solved_puzzles = []
        self.puzzle_efficiencies = []  # Track efficiency per puzzle
        self.result = None
        self.start_time = time.time()
        self.time_expired = False

        # Generate puzzles based on tier
        self.puzzles = []
        for i in range(self.puzzle_count):
            puzzle = self._create_puzzle_for_tier(i)
            self.puzzles.append(puzzle)

    def update(self, dt):
        """Update time tracking (called from game engine)"""
        import time
        if not self.active or self.time_expired:
            return

        elapsed = time.time() - self.start_time
        if elapsed >= self.time_limit:
            self.time_expired = True
            # Auto-complete with current progress
            self.end()

    def get_time_remaining(self):
        """Get remaining time in seconds"""
        import time
        if not self.active:
            return 0
        elapsed = time.time() - self.start_time
        return max(0, self.time_limit - elapsed)

    def _create_puzzle_for_tier(self, index):
        """
        Create appropriate puzzle based on difficulty tier (rarity-based).

        ALL recipes get both puzzle types:
        - Puzzle 0: RotationPipePuzzle (path finding)
        - Puzzle 1+: LogicSwitchPuzzle (lights out)

        Args:
            index: Puzzle index in sequence

        Returns:
            Puzzle instance
        """
        tier = self.difficulty_tier  # Now uses rarity-named tiers
        # Get ideal_moves from difficulty calculation (6-8 range)
        ideal_moves = getattr(self, 'ideal_moves', 7)
        grid = self.grid_size if hasattr(self, 'grid_size') else 3

        # First puzzle is ALWAYS RotationPipePuzzle
        if index == 0:
            if tier in ('common', 'uncommon'):
                difficulty = "easy" if tier == 'common' else "medium"
            elif tier == 'rare':
                difficulty = "medium"
            else:  # epic, legendary
                difficulty = "hard"
            return RotationPipePuzzle(grid, difficulty)

        # Second puzzle onwards is ALWAYS LogicSwitchPuzzle
        else:
            if tier in ('common', 'uncommon'):
                difficulty = "easy"
            elif tier == 'rare':
                difficulty = "easy"
            elif tier == 'epic':
                difficulty = "medium"
            else:  # legendary
                difficulty = "hard"
            return LogicSwitchPuzzle(grid, difficulty, max_moves=ideal_moves)

    def handle_action(self, action_type, **kwargs):
        """
        Handle puzzle action (rotate, toggle, reset, etc.)

        Args:
            action_type: Type of action ("rotate", "toggle", "reset", etc.)
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
        elif action_type == "toggle" and isinstance(current_puzzle, LogicSwitchPuzzle):
            row = kwargs.get('row', 0)
            col = kwargs.get('col', 0)
            return current_puzzle.toggle_switch(row, col)
        elif action_type == "reset":
            # Reset current puzzle to initial state
            return self.reset_current_puzzle()
        # Legacy support for slide action (deprecated)
        elif action_type == "slide" and isinstance(current_puzzle, SlidingTilePuzzle):
            row = kwargs.get('row', 0)
            col = kwargs.get('col', 0)
            return current_puzzle.slide_tile(row, col)

        return False

    def reset_current_puzzle(self):
        """Reset the current puzzle to its initial state"""
        if self.current_puzzle_index >= len(self.puzzles):
            return False

        current_puzzle = self.puzzles[self.current_puzzle_index]
        if hasattr(current_puzzle, 'reset'):
            current_puzzle.reset()
            return True
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
            # Puzzle solved! Track efficiency for scoring
            self.solved_puzzles.append(current_puzzle)

            # Get efficiency score if puzzle supports it
            if hasattr(current_puzzle, 'get_efficiency_score'):
                efficiency = current_puzzle.get_efficiency_score()
            else:
                efficiency = 1.0  # Default for puzzles without efficiency tracking
            self.puzzle_efficiencies.append(efficiency)

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
        """Complete device creation with stat modifications and reward calculation."""
        import time
        self.active = False

        # Calculate performance score based on puzzle completion and efficiency
        puzzles_solved = len(self.solved_puzzles)
        completion_ratio = puzzles_solved / max(1, self.puzzle_count)

        # Calculate average efficiency from solved puzzles
        if hasattr(self, 'puzzle_efficiencies') and self.puzzle_efficiencies:
            avg_efficiency = sum(self.puzzle_efficiencies) / len(self.puzzle_efficiencies)
        else:
            avg_efficiency = 1.0

        # Calculate time factor
        time_remaining = self.get_time_remaining()
        time_ratio = time_remaining / max(1, self.time_limit)  # 0 to 1

        # Calculate device stats based on puzzle performance
        # Each puzzle affects a different aspect of the device
        stats = {
            "durability": 100,  # Base stats
            "efficiency": 100,
            "accuracy": 100,
            "power": 100
        }

        # Each solved puzzle adds bonus based on efficiency (5-20%)
        stat_types = ["durability", "efficiency", "accuracy", "power"]
        for i, puzzle in enumerate(self.solved_puzzles):
            stat_type = stat_types[i % len(stat_types)]
            # Bonus scales with efficiency: 5% at 0 efficiency, 20% at 100% efficiency
            efficiency = self.puzzle_efficiencies[i] if i < len(self.puzzle_efficiencies) else 1.0
            bonus = int(5 + 15 * efficiency)
            stats[stat_type] += bonus

        # Calculate performance (0.0-1.0) based on:
        # - Completion ratio (50% weight)
        # - Efficiency score (30% weight)
        # - Time bonus (20% weight, only if completed before time expires)
        base_performance = completion_ratio * 0.5 + avg_efficiency * 0.3

        # Time bonus only applies if all puzzles solved before time expired
        if not getattr(self, 'time_expired', False) and puzzles_solved == self.puzzle_count:
            base_performance += time_ratio * 0.2
        elif puzzles_solved == self.puzzle_count:
            base_performance += 0.1  # Partial time bonus for completion

        hint_penalty = self.hints_used * 0.05  # 5% penalty per hint
        performance = max(0.0, min(1.0, base_performance - hint_penalty))

        # Apply first-try bonus
        if self.attempt == 1:
            performance = min(1.0, performance + 0.05)

        # Calculate rewards using centralized calculator
        try:
            from core.reward_calculator import calculate_engineering_rewards
            rewards = calculate_engineering_rewards(
                self.difficulty_points,
                {
                    'puzzles_solved': puzzles_solved,
                    'total_puzzles': self.puzzle_count,
                    'hints_used': self.hints_used,
                    'time_remaining': time_ratio,
                    'efficiency': avg_efficiency,
                    'attempt': self.attempt
                }
            )
        except ImportError:
            # Fallback to basic rewards
            rewards = {
                'quality_tier': 'common',
                'xp_multiplier': 1.0,
                'rarity_upgrade_chance': 0.0,
                'bonus_output_chance': 0.0
            }

        # Calculate overall quality (avg of all stats)
        quality = sum(stats.values()) / (len(stats) * 100)

        self.result = {
            "success": True,
            "puzzles_solved": puzzles_solved,
            "total_puzzles": self.puzzle_count,
            "stats": stats,
            "quality": quality,
            "performance": performance,
            "efficiency": avg_efficiency,
            "time_expired": getattr(self, 'time_expired', False),
            "difficulty_points": getattr(self, 'difficulty_points', 0),
            "difficulty_tier": getattr(self, 'difficulty_tier', 'common'),
            "rewards": rewards,
            "message": f"Device created! Solved {puzzles_solved}/{self.puzzle_count} puzzles. Efficiency: {avg_efficiency*100:.0f}%"
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
            "time_remaining": self.get_time_remaining(),
            "time_limit": self.time_limit,
            "time_expired": getattr(self, 'time_expired', False),
            "efficiency_scores": getattr(self, 'puzzle_efficiencies', []),
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
        # Fallback to 'common' if rarity is None (material not in database)
        input_rarity = input_rarity or 'common'

        # Deduct materials
        for inp in recipe['inputs']:
            # Backward compatible: support both 'itemId' (new) and 'materialId' (legacy)
            item_id = inp.get('itemId') or inp.get('materialId')
            inventory[item_id] -= inp['quantity']

        return {
            "success": True,
            "outputId": recipe['outputId'],
            "quantity": recipe['outputQty'],
            "rarity": input_rarity,
            "message": f"Device created ({input_rarity})"
        }

    def create_minigame(self, recipe_id, buff_time_bonus=0.0, buff_quality_bonus=0.0, material_rarity="common"):
        """
        Create an engineering minigame for this recipe.

        Difficulty is now calculated from material tier points, not station tier.

        Args:
            recipe_id: Recipe ID to craft
            buff_time_bonus: Skill buff bonus to time limit (0.0-1.0+)
            buff_quality_bonus: Skill buff bonus to quality (0.0-1.0+)
            material_rarity: Highest material rarity used (deprecated, kept for compatibility)

        Returns:
            EngineeringMinigame instance or None
        """
        if recipe_id not in self.recipes:
            return None

        recipe = self.recipes[recipe_id]

        # Pass full recipe - difficulty calculated from material inputs
        return EngineeringMinigame(recipe, buff_time_bonus, buff_quality_bonus)

    def craft_with_minigame(self, recipe_id, inventory, minigame_result, item_metadata=None):
        """
        Craft with minigame result with rarity modifiers and tier-scaled penalties.

        Failure Penalties (by difficulty tier):
        - Common: 30% material loss
        - Uncommon: 45% material loss
        - Rare: 60% material loss
        - Epic: 75% material loss
        - Legendary: 90% material loss

        Args:
            recipe_id: Recipe ID to craft
            inventory: Dict of {material_id: quantity} (will be modified)
            minigame_result: Result dict from EngineeringMinigame
            item_metadata: Optional dict of item metadata for category lookup

        Returns:
            dict: Result with outputId, rarity, stats, success
        """
        recipe = self.recipes[recipe_id]

        # Get difficulty tier from minigame result for tier-scaled penalties
        difficulty_tier = minigame_result.get('difficulty_tier', 'common')

        # Tier-scaled failure penalties
        FAILURE_PENALTIES = {
            'common': 0.30,
            'uncommon': 0.45,
            'rare': 0.60,
            'epic': 0.75,
            'legendary': 0.90
        }
        penalty = FAILURE_PENALTIES.get(difficulty_tier, 0.30)

        if minigame_result.get('abandoned'):
            # Abandoned - return materials minus tier-scaled penalty
            materials_returned = 1.0 - penalty
            for inp in recipe['inputs']:
                # Backward compatible: support both 'itemId' (new) and 'materialId' (legacy)
                item_id = inp.get('itemId') or inp.get('materialId')
                returned = int(inp['quantity'] * materials_returned)
                if returned > 0:
                    inventory[item_id] = inventory.get(item_id, 0) + returned

            return {
                "success": False,
                "message": f"Device creation abandoned ({int(materials_returned * 100)}% materials returned)",
                "materials_returned": True,
                "materials_returned_pct": materials_returned
            }

        if not minigame_result.get('success'):
            # Failed somehow (shouldn't happen in engineering)
            return {
                "success": False,
                "message": "Device creation failed"
            }

        # Success - deduct full materials
        for inp in recipe['inputs']:
            # Backward compatible: support both 'itemId' (new) and 'materialId' (legacy)
            item_id = inp.get('itemId') or inp.get('materialId')
            inventory[item_id] -= inp['quantity']

        # Detect input rarity
        inputs = recipe.get('inputs', [])
        _, input_rarity, _ = rarity_system.check_rarity_uniformity(inputs)
        # Fallback to 'common' if rarity is None (material not in database)
        input_rarity = input_rarity or 'common'

        # Get device stats from minigame result
        base_stats = minigame_result.get('stats', {})
        quality = minigame_result.get('quality', 1.0)

        # Get item category and apply rarity modifiers
        output_id = recipe['outputId']
        if item_metadata is None:
            item_metadata = {}

        item_category = rarity_system.get_item_category(output_id, item_metadata)
        modified_stats = rarity_system.apply_rarity_modifiers(base_stats, item_category, input_rarity)

        # Extract rewards from minigame result
        rewards = minigame_result.get('rewards', {})

        result = {
            "success": True,
            "outputId": output_id,
            "quantity": recipe['outputQty'],
            "rarity": input_rarity,
            "performance": minigame_result.get('performance', 1.0),
            "difficulty_tier": difficulty_tier,
            "rewards": rewards,
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

"""
Collision System - Handles collision detection, line-of-sight, and pathfinding

This module provides:
1. Line-of-sight checking for attacks
2. Collision detection for movement
3. A* pathfinding for hostile navigation
4. Collidable object management

Design principles:
- JSON-driven where possible (collision config)
- Scalable for future features (attack tags that bypass obstacles)
- Works with existing tile, resource, and placed entity systems
"""

from typing import List, Tuple, Optional, Set, Dict, Any, TYPE_CHECKING
from dataclasses import dataclass, field
from enum import Enum
import math
import heapq

from data.models.world import Position, PlacedEntityType

if TYPE_CHECKING:
    from systems.world_system import WorldSystem
    from systems.natural_resource import NaturalResource
    from data.models.world import PlacedEntity


class CollisionType(Enum):
    """Types of collisions that can occur"""
    NONE = "none"
    TILE = "tile"  # Non-walkable tile (water)
    RESOURCE = "resource"  # Natural resource (tree, ore, stone)
    BARRIER = "barrier"  # Player-placed barrier
    ENTITY = "entity"  # Turret, crafting station, etc.


@dataclass
class CollisionResult:
    """Result of a collision check"""
    blocked: bool = False
    collision_type: CollisionType = CollisionType.NONE
    collision_position: Optional[Tuple[float, float]] = None
    collision_object: Optional[Any] = None
    distance_to_collision: float = float('inf')


@dataclass
class PathNode:
    """Node for A* pathfinding"""
    x: int
    y: int
    g_cost: float = 0.0  # Cost from start
    h_cost: float = 0.0  # Heuristic to goal
    parent: Optional['PathNode'] = None

    @property
    def f_cost(self) -> float:
        return self.g_cost + self.h_cost

    def __lt__(self, other: 'PathNode') -> bool:
        return self.f_cost < other.f_cost

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, PathNode):
            return False
        return self.x == other.x and self.y == other.y

    def __hash__(self) -> int:
        return hash((self.x, self.y))


class CollisionSystem:
    """
    Central collision and line-of-sight system.

    Handles:
    - Line-of-sight checking for attacks (ray casting)
    - Collision detection for movement
    - A* pathfinding for hostiles
    - Manages collidable objects
    """

    # Tags that bypass line-of-sight checks (AoE effects)
    BYPASS_LOS_TAGS = {'circle', 'aoe', 'ground'}

    # Tags that can pass through obstacles (future expansion)
    PASSTHROUGH_TAGS: Set[str] = set()  # Empty for now, can add 'ethereal', 'ghost', etc.

    def __init__(self, world_system: Optional['WorldSystem'] = None):
        """
        Initialize the collision system.

        Args:
            world_system: Reference to the world system for tile/resource checks
        """
        self.world_system = world_system

        # Cache for performance (cleared on world changes)
        self._collision_cache: Dict[str, CollisionResult] = {}
        self._path_cache: Dict[str, List[Tuple[int, int]]] = {}
        self._cache_valid = False

    def set_world_system(self, world_system: 'WorldSystem'):
        """Set or update the world system reference."""
        self.world_system = world_system
        self.invalidate_cache()

    def invalidate_cache(self):
        """Invalidate collision cache (call when world changes)."""
        self._collision_cache.clear()
        self._path_cache.clear()
        self._cache_valid = False

    # =========================================================================
    # Line-of-Sight Checking
    # =========================================================================

    def has_line_of_sight(self,
                          source: Tuple[float, float],
                          target: Tuple[float, float],
                          attack_tags: Optional[List[str]] = None,
                          check_resources: bool = True,
                          check_barriers: bool = True,
                          check_tiles: bool = True) -> CollisionResult:
        """
        Check if there is a clear line of sight between source and target.

        Uses Bresenham's line algorithm to check each tile along the path.

        Args:
            source: (x, y) source position
            target: (x, y) target position
            attack_tags: Tags of the attack (circle, etc. bypass LoS)
            check_resources: Whether to check resources as blockers
            check_barriers: Whether to check placed barriers
            check_tiles: Whether to check non-walkable tiles

        Returns:
            CollisionResult indicating if LoS is blocked and by what
        """
        if self.world_system is None:
            return CollisionResult(blocked=False)

        # Check if attack bypasses LoS (circle/AoE attacks)
        if attack_tags:
            if any(tag in self.BYPASS_LOS_TAGS for tag in attack_tags):
                return CollisionResult(blocked=False)
            if any(tag in self.PASSTHROUGH_TAGS for tag in attack_tags):
                return CollisionResult(blocked=False)

        # Get all tiles along the line
        line_tiles = self._get_line_tiles(source, target)

        # Skip the source tile (index 0) and target tile (last index)
        # We only care about obstacles BETWEEN source and target
        check_tiles_list = line_tiles[1:-1] if len(line_tiles) > 2 else []

        for tile_x, tile_y in check_tiles_list:
            result = self._check_tile_collision(tile_x, tile_y,
                                                check_resources=check_resources,
                                                check_barriers=check_barriers,
                                                check_tiles=check_tiles)
            if result.blocked:
                # Calculate distance to the collision
                dx = tile_x - source[0]
                dy = tile_y - source[1]
                result.distance_to_collision = math.sqrt(dx * dx + dy * dy)
                return result

        return CollisionResult(blocked=False)

    def _get_line_tiles(self,
                        source: Tuple[float, float],
                        target: Tuple[float, float]) -> List[Tuple[int, int]]:
        """
        Get all tiles along a line using Bresenham's algorithm.

        Args:
            source: Start position
            target: End position

        Returns:
            List of (x, y) tile coordinates along the line
        """
        x0, y0 = int(math.floor(source[0])), int(math.floor(source[1]))
        x1, y1 = int(math.floor(target[0])), int(math.floor(target[1]))

        tiles = []

        dx = abs(x1 - x0)
        dy = abs(y1 - y0)
        sx = 1 if x0 < x1 else -1
        sy = 1 if y0 < y1 else -1
        err = dx - dy

        while True:
            tiles.append((x0, y0))

            if x0 == x1 and y0 == y1:
                break

            e2 = 2 * err
            if e2 > -dy:
                err -= dy
                x0 += sx
            if e2 < dx:
                err += dx
                y0 += sy

        return tiles

    def _check_tile_collision(self,
                              x: int,
                              y: int,
                              check_resources: bool = True,
                              check_barriers: bool = True,
                              check_tiles: bool = True) -> CollisionResult:
        """
        Check if a specific tile blocks line of sight.

        Args:
            x: Tile X coordinate
            y: Tile Y coordinate
            check_resources: Check natural resources
            check_barriers: Check placed barriers
            check_tiles: Check non-walkable tiles

        Returns:
            CollisionResult for this tile
        """
        pos = Position(x, y, 0)

        # Check non-walkable tiles (water, etc.)
        if check_tiles:
            tile = self.world_system.get_tile(pos)
            if tile and not tile.walkable:
                return CollisionResult(
                    blocked=True,
                    collision_type=CollisionType.TILE,
                    collision_position=(x, y),
                    collision_object=tile
                )

        # Check resources (trees, ores, etc.)
        if check_resources:
            resource = self.world_system.get_resource_at(pos)
            if resource and not resource.depleted:
                return CollisionResult(
                    blocked=True,
                    collision_type=CollisionType.RESOURCE,
                    collision_position=(x, y),
                    collision_object=resource
                )

        # Check placed barriers
        if check_barriers:
            entity = self.world_system.get_entity_at(pos)
            if entity and entity.entity_type == PlacedEntityType.BARRIER:
                return CollisionResult(
                    blocked=True,
                    collision_type=CollisionType.BARRIER,
                    collision_position=(x, y),
                    collision_object=entity
                )

        return CollisionResult(blocked=False)

    # =========================================================================
    # Movement Collision
    # =========================================================================

    def is_position_walkable(self,
                             x: float,
                             y: float,
                             check_resources: bool = True,
                             check_barriers: bool = True,
                             check_entities: bool = False) -> bool:
        """
        Check if a position is walkable (for movement).

        Args:
            x: X position
            y: Y position
            check_resources: Check natural resources block movement
            check_barriers: Check placed barriers block movement
            check_entities: Check other entities (turrets, etc.) block movement

        Returns:
            True if position is walkable
        """
        if self.world_system is None:
            return True

        pos = Position(math.floor(x), math.floor(y), 0)

        # First check tile walkability
        tile = self.world_system.get_tile(pos)
        if tile and not tile.walkable:
            return False

        # Check resources (undepleted resources block movement)
        if check_resources:
            resource = self.world_system.get_resource_at(pos)
            if resource and not resource.depleted:
                return False

        # Check placed entities
        if check_barriers or check_entities:
            entity = self.world_system.get_entity_at(pos)
            if entity:
                if check_barriers and entity.entity_type == PlacedEntityType.BARRIER:
                    return False
                if check_entities:
                    # Other entities like turrets don't block by default
                    # But barriers always block
                    if entity.entity_type == PlacedEntityType.BARRIER:
                        return False

        return True

    def can_move_to(self,
                    current_x: float,
                    current_y: float,
                    new_x: float,
                    new_y: float,
                    entity_radius: float = 0.3) -> Tuple[bool, float, float]:
        """
        Check if an entity can move from current position to new position.
        Implements collision sliding (try X-only or Y-only if diagonal blocked).

        Args:
            current_x: Current X position
            current_y: Current Y position
            new_x: Desired X position
            new_y: Desired Y position
            entity_radius: Radius for collision checking

        Returns:
            Tuple of (can_move, final_x, final_y)
        """
        # Check if direct movement is possible
        if self.is_position_walkable(new_x, new_y, check_resources=True, check_barriers=True):
            return True, new_x, new_y

        # Try X-only movement (sliding along Y walls)
        if current_x != new_x:
            if self.is_position_walkable(new_x, current_y, check_resources=True, check_barriers=True):
                return True, new_x, current_y

        # Try Y-only movement (sliding along X walls)
        if current_y != new_y:
            if self.is_position_walkable(current_x, new_y, check_resources=True, check_barriers=True):
                return True, current_x, new_y

        # Cannot move at all
        return False, current_x, current_y

    # =========================================================================
    # A* Pathfinding
    # =========================================================================

    def find_path(self,
                  start: Tuple[float, float],
                  goal: Tuple[float, float],
                  max_iterations: int = 200,
                  max_path_length: int = 50) -> Optional[List[Tuple[float, float]]]:
        """
        Find a path from start to goal using A* algorithm.

        Args:
            start: (x, y) starting position
            goal: (x, y) goal position
            max_iterations: Maximum iterations before giving up
            max_path_length: Maximum path length

        Returns:
            List of (x, y) waypoints, or None if no path found
        """
        if self.world_system is None:
            return None

        # Convert to grid coordinates
        start_x, start_y = int(math.floor(start[0])), int(math.floor(start[1]))
        goal_x, goal_y = int(math.floor(goal[0])), int(math.floor(goal[1]))

        # Quick check: if goal is not walkable, find nearest walkable tile
        if not self.is_position_walkable(goal_x, goal_y):
            goal_x, goal_y = self._find_nearest_walkable(goal_x, goal_y, goal)
            if goal_x is None:
                return None

        # Check cache
        cache_key = f"{start_x},{start_y}->{goal_x},{goal_y}"
        if cache_key in self._path_cache:
            return self._path_cache[cache_key]

        # A* algorithm
        start_node = PathNode(start_x, start_y)
        goal_node = PathNode(goal_x, goal_y)

        start_node.h_cost = self._heuristic(start_x, start_y, goal_x, goal_y)

        open_set: List[PathNode] = [start_node]
        closed_set: Set[Tuple[int, int]] = set()
        open_dict: Dict[Tuple[int, int], PathNode] = {(start_x, start_y): start_node}

        iterations = 0

        while open_set and iterations < max_iterations:
            iterations += 1

            # Get node with lowest f_cost
            current = heapq.heappop(open_set)
            current_key = (current.x, current.y)

            if current_key in closed_set:
                continue

            # Check if we reached the goal
            if current.x == goal_x and current.y == goal_y:
                path = self._reconstruct_path(current)
                # Convert to float positions (center of tiles)
                path = [(x + 0.5, y + 0.5) for x, y in path]

                # Cache the result
                if len(path) <= max_path_length:
                    self._path_cache[cache_key] = path

                return path

            closed_set.add(current_key)

            # Explore neighbors
            for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1),
                           (-1, -1), (-1, 1), (1, -1), (1, 1)]:
                nx, ny = current.x + dx, current.y + dy
                neighbor_key = (nx, ny)

                if neighbor_key in closed_set:
                    continue

                # Check if walkable
                if not self.is_position_walkable(nx, ny):
                    continue

                # Diagonal movement check: ensure not cutting corners
                if dx != 0 and dy != 0:
                    if not self.is_position_walkable(current.x + dx, current.y):
                        continue
                    if not self.is_position_walkable(current.x, current.y + dy):
                        continue

                # Calculate costs
                move_cost = 1.414 if (dx != 0 and dy != 0) else 1.0
                new_g = current.g_cost + move_cost

                # Check if this is a better path
                if neighbor_key in open_dict:
                    existing = open_dict[neighbor_key]
                    if new_g >= existing.g_cost:
                        continue

                # Create or update neighbor node
                neighbor = PathNode(nx, ny)
                neighbor.g_cost = new_g
                neighbor.h_cost = self._heuristic(nx, ny, goal_x, goal_y)
                neighbor.parent = current

                heapq.heappush(open_set, neighbor)
                open_dict[neighbor_key] = neighbor

        # No path found
        return None

    def _heuristic(self, x1: int, y1: int, x2: int, y2: int) -> float:
        """Calculate heuristic distance (octile distance for 8-way movement)."""
        dx = abs(x2 - x1)
        dy = abs(y2 - y1)
        return max(dx, dy) + 0.414 * min(dx, dy)

    def _reconstruct_path(self, node: PathNode) -> List[Tuple[int, int]]:
        """Reconstruct path from goal node back to start."""
        path = []
        current = node
        while current is not None:
            path.append((current.x, current.y))
            current = current.parent
        return list(reversed(path))

    def _find_nearest_walkable(self,
                               x: int,
                               y: int,
                               original_goal: Tuple[float, float]) -> Tuple[Optional[int], Optional[int]]:
        """Find the nearest walkable tile to a non-walkable goal."""
        # Search in expanding squares
        for radius in range(1, 5):
            best_tile = None
            best_dist = float('inf')

            for dx in range(-radius, radius + 1):
                for dy in range(-radius, radius + 1):
                    # Only check edge tiles of the square
                    if abs(dx) != radius and abs(dy) != radius:
                        continue

                    nx, ny = x + dx, y + dy
                    if self.is_position_walkable(nx, ny):
                        dist = math.sqrt((nx - original_goal[0])**2 +
                                        (ny - original_goal[1])**2)
                        if dist < best_dist:
                            best_dist = dist
                            best_tile = (nx, ny)

            if best_tile:
                return best_tile

        return None, None

    def get_next_step(self,
                      current: Tuple[float, float],
                      goal: Tuple[float, float]) -> Optional[Tuple[float, float]]:
        """
        Get the next step in the path toward a goal.
        Used for simple movement (one step at a time).

        Args:
            current: Current position
            goal: Goal position

        Returns:
            Next position to move to, or None if blocked
        """
        path = self.find_path(current, goal, max_iterations=100, max_path_length=20)
        if path and len(path) > 1:
            return path[1]  # Return second waypoint (first is current)
        return None

    # =========================================================================
    # Utility Methods
    # =========================================================================

    def get_collidables_in_area(self,
                                center: Tuple[float, float],
                                radius: float) -> List[CollisionResult]:
        """
        Get all collidable objects within an area.

        Args:
            center: Center of the area
            radius: Radius to check

        Returns:
            List of CollisionResults for each collidable found
        """
        if self.world_system is None:
            return []

        results = []

        # Get tile range to check
        min_x = int(math.floor(center[0] - radius))
        max_x = int(math.ceil(center[0] + radius))
        min_y = int(math.floor(center[1] - radius))
        max_y = int(math.ceil(center[1] + radius))

        for x in range(min_x, max_x + 1):
            for y in range(min_y, max_y + 1):
                # Check distance
                dist = math.sqrt((x - center[0])**2 + (y - center[1])**2)
                if dist > radius:
                    continue

                result = self._check_tile_collision(x, y)
                if result.blocked:
                    result.distance_to_collision = dist
                    results.append(result)

        return results


# Global singleton instance
_collision_system: Optional[CollisionSystem] = None


def get_collision_system() -> CollisionSystem:
    """Get the global collision system instance."""
    global _collision_system
    if _collision_system is None:
        _collision_system = CollisionSystem()
    return _collision_system


def init_collision_system(world_system: 'WorldSystem') -> CollisionSystem:
    """Initialize the collision system with a world system."""
    global _collision_system
    _collision_system = CollisionSystem(world_system)
    return _collision_system

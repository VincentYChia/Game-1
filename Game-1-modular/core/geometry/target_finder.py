"""
Target Finder - Geometry-based target selection
Finds targets based on geometry tags (chain, cone, circle, beam, etc.)
"""

from typing import List, Optional, Any, Set, Callable
from data.models.world import Position
from core.geometry.math_utils import (
    distance, is_in_cone, is_in_circle, direction_vector,
    get_facing_from_target, estimate_facing_direction
)
from core.tag_debug import get_tag_debugger


class TargetFinder:
    """
    Finds targets for effects based on geometry and context
    """

    def __init__(self):
        self.debugger = get_tag_debugger()

    def find_targets(self, geometry: str, source: Any, primary_target: Any,
                    params: dict, context: str,
                    available_entities: List[Any]) -> List[Any]:
        """
        Find all targets based on geometry

        Args:
            geometry: Geometry tag (chain, cone, circle, beam, single_target)
            source: Source entity (caster/turret)
            primary_target: Primary target entity
            params: Effect parameters (chain_count, cone_angle, radius, etc.)
            context: Context filter (enemy, ally, etc.)
            available_entities: List of all entities to consider

        Returns:
            List of target entities
        """
        if geometry == 'single_target':
            return self.find_single_target(primary_target, context)

        elif geometry == 'chain':
            return self.find_chain_targets(
                source, primary_target,
                params.get('chain_count', 2),
                params.get('chain_range', 5.0),
                context, available_entities
            )

        elif geometry == 'cone':
            return self.find_cone_targets(
                source, primary_target,
                params.get('cone_angle', 60),
                params.get('cone_range', 8.0),
                context, available_entities
            )

        elif geometry == 'circle' or geometry == 'aoe':
            origin_type = params.get('origin', 'target')
            if origin_type == 'target':
                center = self._get_position(primary_target)
            elif origin_type == 'source':
                center = self._get_position(source)
            else:
                # 'position' - use primary_target as position
                center = primary_target if isinstance(primary_target, Position) else self._get_position(primary_target)

            return self.find_circle_targets(
                center,
                params.get('radius', 3.0),
                params.get('max_targets', 0),
                context, available_entities
            )

        elif geometry == 'beam' or geometry == 'line':
            return self.find_beam_targets(
                source, primary_target,
                params.get('beam_range', 10.0),
                params.get('beam_width', 0.5),
                params.get('pierce_count', 0),
                context, available_entities
            )

        else:
            self.debugger.warning(f"Unknown geometry: {geometry}, using single_target")
            return self.find_single_target(primary_target, context)

    def find_single_target(self, target: Any, context: str) -> List[Any]:
        """Single target - just return the primary target if valid"""
        if self._is_valid_context(target, context):
            return [target]
        return []

    def find_chain_targets(self, source: Any, initial_target: Any,
                          chain_count: int, chain_range: float,
                          context: str, available_entities: List[Any]) -> List[Any]:
        """
        Find chain targets

        Args:
            source: Source entity
            initial_target: First target in chain
            chain_count: Number of additional jumps
            chain_range: Max distance to next target
            context: Context filter
            available_entities: All entities to consider

        Returns:
            List of chained targets [initial, jump1, jump2, ...]
        """
        targets = []
        hit_set: Set[Any] = set()
        current_target = initial_target

        # Add initial target
        if self._is_valid_context(initial_target, context):
            targets.append(initial_target)
            hit_set.add(initial_target)
        else:
            return []  # Initial target invalid

        # Chain jumps
        for jump in range(chain_count):
            next_target = self._find_nearest_valid_target(
                current_target, chain_range, context,
                available_entities, exclude=hit_set
            )

            if next_target is None:
                break  # No more targets

            dist = distance(self._get_position(current_target),
                          self._get_position(next_target))

            self.debugger.log_chain_target(current_target, next_target, jump + 1, dist)

            targets.append(next_target)
            hit_set.add(next_target)
            current_target = next_target

        self.debugger.log_geometry_calculation('chain', targets)
        return targets

    def find_cone_targets(self, source: Any, primary_target: Any,
                         cone_angle: float, cone_range: float,
                         context: str, available_entities: List[Any]) -> List[Any]:
        """
        Find all targets in a cone

        Args:
            source: Source entity (cone origin)
            primary_target: Target to aim toward (or None for current facing)
            cone_angle: Cone angle in degrees
            cone_range: Max cone range
            context: Context filter
            available_entities: All entities

        Returns:
            List of targets in cone
        """
        source_pos = self._get_position(source)

        # Determine cone facing direction
        if primary_target:
            target_pos = self._get_position(primary_target)
            facing = get_facing_from_target(source_pos, target_pos)
        else:
            facing = estimate_facing_direction(source)

        targets = []
        for entity in available_entities:
            if not self._is_valid_context(entity, context):
                continue

            entity_pos = self._get_position(entity)

            if is_in_cone(source_pos, facing, entity_pos, cone_angle, cone_range):
                targets.append(entity)

        self.debugger.log_cone_targets(source, cone_angle, cone_range, len(targets))
        self.debugger.log_geometry_calculation('cone', targets)

        return targets

    def find_circle_targets(self, center: Position, radius: float,
                           max_targets: int, context: str,
                           available_entities: List[Any]) -> List[Any]:
        """
        Find all targets in a circle

        Args:
            center: Center position
            radius: Circle radius
            max_targets: Max number of targets (0 = unlimited)
            context: Context filter
            available_entities: All entities

        Returns:
            List of targets in circle (sorted by distance)
        """
        targets_with_dist = []

        for entity in available_entities:
            if not self._is_valid_context(entity, context):
                continue

            entity_pos = self._get_position(entity)
            if is_in_circle(center, entity_pos, radius):
                dist = distance(center, entity_pos)
                targets_with_dist.append((entity, dist))

        # Sort by distance (closest first)
        targets_with_dist.sort(key=lambda x: x[1])

        # Apply max_targets limit
        if max_targets > 0:
            targets_with_dist = targets_with_dist[:max_targets]

        targets = [t[0] for t in targets_with_dist]

        self.debugger.log_geometry_calculation('circle', targets)
        return targets

    def find_beam_targets(self, source: Any, primary_target: Any,
                         beam_range: float, beam_width: float,
                         pierce_count: int, context: str,
                         available_entities: List[Any]) -> List[Any]:
        """
        Find all targets in a beam/line

        Args:
            source: Source entity
            primary_target: Target to aim toward
            beam_range: Max beam range
            beam_width: Width of beam
            pierce_count: Number of targets to penetrate (0 = first only, -1 = infinite)
            context: Context filter
            available_entities: All entities

        Returns:
            List of targets hit by beam (in order along beam)
        """
        source_pos = self._get_position(source)
        target_pos = self._get_position(primary_target)
        beam_direction = direction_vector(source_pos, target_pos)

        targets_with_dist = []

        for entity in available_entities:
            if not self._is_valid_context(entity, context):
                continue

            entity_pos = self._get_position(entity)

            # Check if entity is along the beam line
            dist_along_beam = self._distance_along_line(source_pos, beam_direction, entity_pos)

            if dist_along_beam < 0 or dist_along_beam > beam_range:
                continue  # Outside beam range

            # Check perpendicular distance (beam width)
            perp_dist = self._perpendicular_distance(source_pos, beam_direction, entity_pos)

            if perp_dist <= beam_width:
                targets_with_dist.append((entity, dist_along_beam))

        # Sort by distance along beam
        targets_with_dist.sort(key=lambda x: x[1])

        # Apply pierce limit
        if pierce_count >= 0:
            targets_with_dist = targets_with_dist[:pierce_count + 1]

        targets = [t[0] for t in targets_with_dist]

        self.debugger.log_geometry_calculation('beam', targets)
        return targets

    # Helper methods

    def _get_position(self, entity: Any) -> Position:
        """Get position from entity"""
        if isinstance(entity, Position):
            return entity

        if hasattr(entity, 'position'):
            pos = entity.position
            # Handle position as list [x, y] or [x, y, z] (for Enemy class)
            if isinstance(pos, list) or isinstance(pos, tuple):
                x, y = pos[0], pos[1]
                z = pos[2] if len(pos) > 2 else 0.0
                return Position(x, y, z)
            # Already a Position object
            return pos

        # Fallback for other structures
        if hasattr(entity, 'x') and hasattr(entity, 'y'):
            z = getattr(entity, 'z', 0.0)
            return Position(entity.x, entity.y, z)

        raise ValueError(f"Cannot get position from {type(entity)}")

    def _is_valid_context(self, entity: Any, context: str) -> bool:
        """
        Check if entity matches context filter

        Args:
            entity: Entity to check
            context: Context string (enemy, ally, all, etc.)

        Returns:
            True if entity is valid for this context
        """
        if context == 'all':
            return True

        if context == 'self':
            # Cannot determine self without source reference
            # Caller should handle this
            return False

        # Check entity category/type
        entity_category = getattr(entity, 'category', None)
        entity_type = type(entity).__name__.lower()

        if context == 'enemy' or context == 'hostile':
            # Enemy entities - check for Enemy class, enemy-like attributes, or enemy type name
            # Check if it's an Enemy instance (handles Enemy subclasses like TrainingDummy)
            if hasattr(entity, 'definition') and hasattr(entity, 'is_alive'):
                return True  # Has Enemy-like attributes
            # Check type name contains "enemy"
            if 'enemy' in entity_type:
                return True
            # Check category
            if entity_category and entity_category in ['beast', 'undead', 'construct', 'mechanical', 'elemental']:
                return True
            return False

        elif context == 'ally' or context == 'friendly':
            # Allied entities (player, turrets, etc.)
            return entity_type in ['character', 'player', 'placedentity'] or 'turret' in entity_type.lower()

        elif context == 'player':
            return entity_type in ['character', 'player']

        elif context == 'turret' or context == 'device':
            return entity_type == 'placedentity' or 'turret' in entity_type.lower()

        elif context == 'construct':
            return entity_category == 'construct'

        elif context == 'undead':
            return entity_category == 'undead'

        elif context == 'mechanical':
            return entity_category == 'mechanical'

        # Default: allow
        return True

    def _find_nearest_valid_target(self, from_entity: Any, max_range: float,
                                   context: str, available_entities: List[Any],
                                   exclude: Set[Any]) -> Optional[Any]:
        """Find nearest valid target from an entity"""
        from_pos = self._get_position(from_entity)
        nearest = None
        nearest_dist = float('inf')

        for entity in available_entities:
            if entity in exclude:
                continue

            if not self._is_valid_context(entity, context):
                continue

            entity_pos = self._get_position(entity)
            dist = distance(from_pos, entity_pos)

            if dist <= max_range and dist < nearest_dist:
                nearest = entity
                nearest_dist = dist

        return nearest

    def _distance_along_line(self, line_start: Position, line_direction: tuple,
                            point: Position) -> float:
        """Calculate distance along a line from start to point's projection"""
        # Vector from line start to point
        to_point = (point.x - line_start.x, point.y - line_start.y)

        # Dot product with line direction
        from core.geometry.math_utils import dot_product
        return dot_product(to_point, line_direction)

    def _perpendicular_distance(self, line_start: Position, line_direction: tuple,
                               point: Position) -> float:
        """Calculate perpendicular distance from point to line"""
        # Distance along line
        dist_along = self._distance_along_line(line_start, line_direction, point)

        # Projection point on line
        proj_x = line_start.x + line_direction[0] * dist_along
        proj_y = line_start.y + line_direction[1] * dist_along

        # Distance from point to projection
        dx = point.x - proj_x
        dy = point.y - proj_y

        return (dx * dx + dy * dy) ** 0.5


# Global instance
_target_finder = None

def get_target_finder() -> TargetFinder:
    """Get global target finder instance"""
    global _target_finder
    if _target_finder is None:
        _target_finder = TargetFinder()
    return _target_finder

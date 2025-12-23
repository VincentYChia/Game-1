"""
Math utilities for geometry calculations
Works with Position class from data.models.world
"""

import math
from typing import Tuple
from data.models.world import Position


def distance(pos1: Position, pos2: Position) -> float:
    """Calculate distance between two positions"""
    return pos1.distance_to(pos2)


def normalize_vector(dx: float, dy: float) -> Tuple[float, float]:
    """Normalize a 2D vector"""
    length = math.sqrt(dx * dx + dy * dy)
    if length == 0:
        return (0.0, 0.0)
    return (dx / length, dy / length)


def dot_product(v1: Tuple[float, float], v2: Tuple[float, float]) -> float:
    """Calculate dot product of two 2D vectors"""
    return v1[0] * v2[0] + v1[1] * v2[1]


def angle_between_vectors(v1: Tuple[float, float], v2: Tuple[float, float]) -> float:
    """
    Calculate angle between two vectors in degrees
    Returns value between 0 and 180
    """
    dot = dot_product(v1, v2)
    # Clamp to avoid numerical errors with acos
    dot = max(-1.0, min(1.0, dot))
    angle_rad = math.acos(dot)
    return math.degrees(angle_rad)


def direction_vector(from_pos: Position, to_pos: Position) -> Tuple[float, float]:
    """Get normalized direction vector from one position to another"""
    dx = to_pos.x - from_pos.x
    dy = to_pos.y - from_pos.y
    return normalize_vector(dx, dy)


def is_in_cone(source_pos: Position, source_facing: Tuple[float, float],
               target_pos: Position, cone_angle: float, cone_range: float) -> bool:
    """
    Check if target position is inside a cone

    Args:
        source_pos: Origin of cone
        source_facing: Direction vector the cone faces (normalized)
        target_pos: Position to test
        cone_angle: Total angle of cone in degrees
        cone_range: Maximum range of cone

    Returns:
        True if target is in cone
    """
    # Check range first
    dist = distance(source_pos, target_pos)
    if dist > cone_range:
        return False

    # Check angle
    to_target = direction_vector(source_pos, target_pos)
    angle = angle_between_vectors(source_facing, to_target)

    # Cone angle is total angle, so half-angle for each side
    half_angle = cone_angle / 2.0

    return angle <= half_angle


def is_in_circle(center: Position, target_pos: Position, radius: float) -> bool:
    """Check if target position is inside a circle"""
    return distance(center, target_pos) <= radius


def get_facing_from_target(source_pos: Position, target_pos: Position) -> Tuple[float, float]:
    """Get facing direction vector from source toward target"""
    return direction_vector(source_pos, target_pos)


def estimate_facing_direction(source: any) -> Tuple[float, float]:
    """
    Estimate facing direction for an entity
    Tries to use last_move_direction, velocity, or defaults to (1, 0)

    Args:
        source: Entity with potential direction/velocity

    Returns:
        Normalized direction vector (dx, dy)
    """
    # Try last_move_direction
    if hasattr(source, 'last_move_direction') and source.last_move_direction:
        dx, dy = source.last_move_direction
        return normalize_vector(dx, dy)

    # Try velocity
    if hasattr(source, 'velocity'):
        vel = source.velocity
        if hasattr(vel, 'x') and hasattr(vel, 'y'):
            if vel.x != 0 or vel.y != 0:
                return normalize_vector(vel.x, vel.y)

    # Default facing right
    return (1.0, 0.0)

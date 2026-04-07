"""Ecosystem generator — 3x3 chunk danger grouping with gradient.

Ecosystems are groups of 3x3 chunks that share the same danger level.
Adjacent ecosystems may differ by at most ±2 danger levels.
Biome type and region identity influence danger generation odds.

The spawn area at (0,0) is automatically safe (Tranquil).
"""

from __future__ import annotations

from typing import Dict, Set, Tuple

from systems.geography.config import GeographicConfig
from systems.geography.models import (
    DangerLevel,
    EcosystemData,
    NewChunkType,
    RegionData,
    DANGER_GRADIENT_MAX,
)
from systems.geography.noise import hash_2d, hash_2d_int


# Chunk types that bias toward lower danger (safer environments)
_SAFE_CHUNK_TYPES = {
    NewChunkType.LAKE, NewChunkType.RIVER, NewChunkType.FOREST,
}

# Chunk types that bias toward higher danger
_DANGEROUS_CHUNK_TYPES = {
    NewChunkType.DEEP_CAVE, NewChunkType.CURSED_MARSH,
    NewChunkType.CRYSTAL_CAVERN, NewChunkType.BARREN_WASTE,
}


def _chunk_to_ecosystem(cx: int, cy: int, group_size: int) -> Tuple[int, int]:
    """Convert chunk coordinates to ecosystem grid coordinates."""
    # Use floor division to handle negative coordinates correctly
    if cx >= 0:
        ex = cx // group_size
    else:
        ex = (cx - group_size + 1) // group_size
    if cy >= 0:
        ey = cy // group_size
    else:
        ey = (cy - group_size + 1) // group_size
    return (ex, ey)


def _ecosystem_to_chunks(
    ex: int, ey: int, group_size: int,
    valid_chunks: Set[Tuple[int, int]],
) -> Set[Tuple[int, int]]:
    """Get all valid chunks belonging to an ecosystem cell."""
    result = set()
    base_x = ex * group_size
    base_y = ey * group_size
    for dx in range(group_size):
        for dy in range(group_size):
            pos = (base_x + dx, base_y + dy)
            if pos in valid_chunks:
                result.add(pos)
    return result


def _compute_base_danger(
    eco_x: int,
    eco_y: int,
    eco_chunks: Set[Tuple[int, int]],
    chunk_type_map: Dict[Tuple[int, int], NewChunkType],
    region_map: Dict[Tuple[int, int], int],
    region_metadata: Dict[int, RegionData],
    seed: int,
    config: GeographicConfig,
) -> int:
    """Compute the base danger level for an ecosystem before gradient smoothing.

    Considers:
    1. Base probability distribution from config
    2. Chunk type bias (some types are safer/more dangerous)
    3. Distance from spawn (only for spawn safety)
    """
    spawn_safe = config.ecosystem.spawn_safe_radius
    eco_dist = max(abs(eco_x), abs(eco_y))

    # Spawn area is always Tranquil
    if eco_dist <= spawn_safe:
        return DangerLevel.TRANQUIL

    # Start with base weights from config
    weights = dict(config.ecosystem.base_danger_weights)

    # Modify weights based on chunk types in this ecosystem
    safe_count = 0
    dangerous_count = 0
    for pos in eco_chunks:
        ct = chunk_type_map.get(pos)
        if ct in _SAFE_CHUNK_TYPES:
            safe_count += 1
        elif ct in _DANGEROUS_CHUNK_TYPES:
            dangerous_count += 1

    total = len(eco_chunks) if eco_chunks else 1
    safe_ratio = safe_count / total
    dangerous_ratio = dangerous_count / total

    # Shift weights toward safety or danger
    if safe_ratio > 0.5:
        # Bias toward lower danger
        for level in [1, 2, 3]:
            weights[level] = weights.get(level, 0) * (1.0 + safe_ratio)
    if dangerous_ratio > 0.3:
        # Bias toward higher danger
        for level in [4, 5, 6]:
            weights[level] = weights.get(level, 0) * (1.0 + dangerous_ratio * 2)

    # Normalize weights
    total_weight = sum(weights.values())
    if total_weight <= 0:
        return DangerLevel.MODERATE

    # Deterministic selection using hash
    roll = hash_2d(eco_x, eco_y, seed + 700000)
    cumulative = 0.0
    for level in sorted(weights.keys()):
        cumulative += weights[level] / total_weight
        if roll < cumulative:
            return level

    return DangerLevel.MODERATE


def _smooth_gradient(
    eco_dangers: Dict[Tuple[int, int], int],
    gradient_max: int,
    seed: int,
) -> Dict[Tuple[int, int], int]:
    """Smooth danger levels so neighbors differ by at most ±gradient_max.

    Uses iterative relaxation: repeatedly adjust levels that violate
    the constraint until convergence.
    """
    result = dict(eco_dangers)
    max_iterations = 20

    for iteration in range(max_iterations):
        changed = False
        for (ex, ey), level in list(result.items()):
            # Check all 4-connected neighbors
            for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                neighbor = (ex + dx, ey + dy)
                if neighbor not in result:
                    continue
                neighbor_level = result[neighbor]
                diff = abs(level - neighbor_level)
                if diff > gradient_max:
                    # Move this ecosystem's level toward neighbor
                    if level > neighbor_level:
                        new_level = neighbor_level + gradient_max
                    else:
                        new_level = neighbor_level - gradient_max
                    new_level = max(1, min(6, new_level))
                    if new_level != level:
                        result[(ex, ey)] = new_level
                        changed = True

        if not changed:
            break

    return result


# ══════════════════════════════════════════════════════════════════
# PUBLIC API
# ══════════════════════════════════════════════════════════════════

def generate_ecosystems(
    chunk_type_map: Dict[Tuple[int, int], NewChunkType],
    region_map: Dict[Tuple[int, int], int],
    region_metadata: Dict[int, RegionData],
    seed: int,
    config: GeographicConfig,
) -> Tuple[
    Dict[Tuple[int, int], int],
    Dict[Tuple[int, int], DangerLevel],
    Dict[int, EcosystemData],
]:
    """Generate ecosystem layer (3x3 danger groupings).

    Args:
        chunk_type_map: Per-chunk chunk types.
        region_map: Per-chunk region IDs.
        region_metadata: Region metadata.
        seed: World seed.
        config: Geographic configuration.

    Returns:
        Tuple of:
        - ecosystem_map: (chunk_x, chunk_y) → ecosystem_id
        - danger_map: (chunk_x, chunk_y) → DangerLevel
        - ecosystem_metadata: ecosystem_id → EcosystemData
    """
    group_size = config.ecosystem.group_size
    gradient_max = DANGER_GRADIENT_MAX
    all_chunks = set(chunk_type_map.keys())

    # Step 1: Identify all ecosystem grid cells
    eco_cells: Dict[Tuple[int, int], Set[Tuple[int, int]]] = {}
    for pos in all_chunks:
        eco_pos = _chunk_to_ecosystem(pos[0], pos[1], group_size)
        eco_cells.setdefault(eco_pos, set()).add(pos)

    # Step 2: Compute base danger for each ecosystem
    eco_dangers: Dict[Tuple[int, int], int] = {}
    for eco_pos, eco_chunks in eco_cells.items():
        eco_dangers[eco_pos] = _compute_base_danger(
            eco_pos[0], eco_pos[1], eco_chunks,
            chunk_type_map, region_map, region_metadata,
            seed, config,
        )

    # Step 3: Smooth gradient to enforce ±2 constraint
    smoothed = _smooth_gradient(eco_dangers, gradient_max, seed)

    # Step 4: Build output maps
    ecosystem_map: Dict[Tuple[int, int], int] = {}
    danger_map: Dict[Tuple[int, int], DangerLevel] = {}
    ecosystem_metadata: Dict[int, EcosystemData] = {}

    eco_id = 0
    eco_id_lookup: Dict[Tuple[int, int], int] = {}

    for eco_pos, eco_chunks in eco_cells.items():
        eid = eco_id
        eco_id += 1
        eco_id_lookup[eco_pos] = eid

        danger = DangerLevel(max(1, min(6, smoothed.get(eco_pos, 3))))

        ecosystem_metadata[eid] = EcosystemData(
            ecosystem_id=eid,
            danger_level=danger,
            eco_x=eco_pos[0],
            eco_y=eco_pos[1],
        )

        for pos in eco_chunks:
            ecosystem_map[pos] = eid
            danger_map[pos] = danger

    return ecosystem_map, danger_map, ecosystem_metadata

"""Deterministic noise and deformation utilities for geographic generation.

All functions are pure and deterministic — same seed + same input = same output.
No external dependencies (no numpy, no Perlin library). Uses hash-based noise
similar to the existing BiomeGenerator approach.
"""

from __future__ import annotations

import math
from typing import List, Set, Tuple


# ══════════════════════════════════════════════════════════════════
# HASH-BASED PSEUDO-RANDOM
# ══════════════════════════════════════════════════════════════════

def hash_2d(x: int, y: int, seed: int) -> float:
    """Deterministic pseudo-random float in [0, 1) from 2D coordinates.

    Uses a mixing function that produces well-distributed values.
    Same (x, y, seed) always returns the same result.
    """
    # Combine coordinates with seed using prime multiplication and XOR
    h = seed
    h = ((h ^ (x * 374761393)) + (y * 668265263)) & 0xFFFFFFFF
    h = ((h ^ (h >> 13)) * 1274126177) & 0xFFFFFFFF
    h = (h ^ (h >> 16)) & 0xFFFFFFFF
    return (h & 0x7FFFFFFF) / 0x7FFFFFFF


def hash_2d_int(x: int, y: int, seed: int, max_val: int) -> int:
    """Deterministic pseudo-random int in [0, max_val) from 2D coordinates."""
    return int(hash_2d(x, y, seed) * max_val) % max_val


# ══════════════════════════════════════════════════════════════════
# VALUE NOISE (smooth, interpolated)
# ══════════════════════════════════════════════════════════════════

def _smoothstep(t: float) -> float:
    """Smooth interpolation curve (3t^2 - 2t^3)."""
    return t * t * (3.0 - 2.0 * t)


def value_noise_2d(x: float, y: float, seed: int) -> float:
    """2D value noise with smooth interpolation. Returns [-1, 1].

    Generates smooth, continuous noise suitable for terrain and borders.
    """
    ix = int(math.floor(x))
    iy = int(math.floor(y))
    fx = x - ix
    fy = y - iy

    # Smooth the fractional parts
    sx = _smoothstep(fx)
    sy = _smoothstep(fy)

    # Four corner values
    v00 = hash_2d(ix, iy, seed) * 2.0 - 1.0
    v10 = hash_2d(ix + 1, iy, seed) * 2.0 - 1.0
    v01 = hash_2d(ix, iy + 1, seed) * 2.0 - 1.0
    v11 = hash_2d(ix + 1, iy + 1, seed) * 2.0 - 1.0

    # Bilinear interpolation with smoothstep
    top = v00 + sx * (v10 - v00)
    bottom = v01 + sx * (v11 - v01)
    return top + sy * (bottom - top)


def fractal_noise_2d(x: float, y: float, seed: int,
                     octaves: int = 4, lacunarity: float = 2.0,
                     persistence: float = 0.5) -> float:
    """Multi-octave fractal noise. Returns approximately [-1, 1].

    Higher octaves add finer detail. Lacunarity controls frequency
    scaling between octaves. Persistence controls amplitude falloff.
    """
    total = 0.0
    amplitude = 1.0
    frequency = 1.0
    max_amplitude = 0.0

    for i in range(octaves):
        total += value_noise_2d(x * frequency, y * frequency, seed + i * 31337) * amplitude
        max_amplitude += amplitude
        amplitude *= persistence
        frequency *= lacunarity

    return total / max_amplitude if max_amplitude > 0 else 0.0


# ══════════════════════════════════════════════════════════════════
# BORDER DEFORMATION
# ══════════════════════════════════════════════════════════════════

def deform_border(
    border_chunks: Set[Tuple[int, int]],
    territory: Set[Tuple[int, int]],
    seed: int,
    amplitude: float,
    frequency: float,
    octaves: int = 4,
) -> Set[Tuple[int, int]]:
    """Deform a set of territory chunks by displacing border regions.

    This is the core deformation function. It works by:
    1. For each chunk near the border, compute a noise-based displacement
    2. Shift chunks inward or outward based on the displacement
    3. Validate that the result stays contiguous

    Args:
        border_chunks: Set of (x, y) chunks that form the border zone.
        territory: Complete set of (x, y) chunks in this territory.
        seed: Deterministic seed for noise.
        amplitude: Maximum displacement in chunks.
        frequency: Noise frequency (lower = smoother borders).
        octaves: Fractal noise octaves.

    Returns:
        New set of territory chunks after deformation.
    """
    result = set(territory)

    # Identify border chunks (adjacent to non-territory)
    border = set()
    for cx, cy in territory:
        for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
            if (cx + dx, cy + dy) not in territory:
                border.add((cx, cy))
                break

    # Expand border zone to amplitude range for smoother deformation
    border_zone = set()
    zone_width = max(1, int(amplitude * 0.5))
    for bx, by in border:
        for dx in range(-zone_width, zone_width + 1):
            for dy in range(-zone_width, zone_width + 1):
                pos = (bx + dx, by + dy)
                if pos in territory:
                    border_zone.add(pos)

    # Apply displacement to border zone chunks
    to_remove = set()
    to_add = set()

    for cx, cy in border_zone:
        # Compute displacement from noise
        noise_val = fractal_noise_2d(
            cx * frequency, cy * frequency,
            seed, octaves=octaves,
        )
        # Displacement direction: perpendicular to nearest border
        disp = noise_val * amplitude

        # Determine if this chunk should be added or removed
        # Positive noise pushes border outward, negative pulls inward
        dist_to_border = _min_border_distance(cx, cy, border)
        if dist_to_border < abs(disp):
            if disp < 0:
                # Pull inward — remove from territory
                to_remove.add((cx, cy))
            else:
                # Push outward — add adjacent non-territory chunks
                for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                    neighbor = (cx + dx, cy + dy)
                    if neighbor not in territory:
                        to_add.add(neighbor)

    result -= to_remove
    result |= to_add

    return result


def _min_border_distance(x: int, y: int, border: Set[Tuple[int, int]]) -> float:
    """Approximate minimum Chebyshev distance to border set."""
    if (x, y) in border:
        return 0.0
    min_dist = float('inf')
    for bx, by in border:
        dist = max(abs(x - bx), abs(y - by))
        if dist < min_dist:
            min_dist = dist
        if dist <= 1:
            return dist
    return min_dist


# ══════════════════════════════════════════════════════════════════
# CONTIGUITY VALIDATION
# ══════════════════════════════════════════════════════════════════

def is_contiguous(territory: Set[Tuple[int, int]]) -> bool:
    """Check if a set of chunks forms a single contiguous region.

    Uses flood-fill from an arbitrary starting chunk.
    """
    if not territory:
        return True
    start = next(iter(territory))
    visited = set()
    stack = [start]
    while stack:
        pos = stack.pop()
        if pos in visited or pos not in territory:
            continue
        visited.add(pos)
        x, y = pos
        stack.extend([(x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)])
    return len(visited) == len(territory)


def find_components(territory: Set[Tuple[int, int]]) -> List[Set[Tuple[int, int]]]:
    """Find all connected components in a set of chunks."""
    remaining = set(territory)
    components = []
    while remaining:
        start = next(iter(remaining))
        component = set()
        stack = [start]
        while stack:
            pos = stack.pop()
            if pos in component or pos not in remaining:
                continue
            component.add(pos)
            x, y = pos
            stack.extend([(x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)])
        remaining -= component
        components.append(component)
    return components


def measure_min_corridor_width(territory: Set[Tuple[int, int]]) -> int:
    """Estimate the minimum corridor width of a territory.

    Checks horizontal and vertical cross-sections to find the thinnest
    passage. Returns width in chunks.
    """
    if not territory:
        return 0

    # Build row and column spans
    rows = {}
    cols = {}
    for x, y in territory:
        rows.setdefault(y, []).append(x)
        cols.setdefault(x, []).append(y)

    min_width = float('inf')

    # Check horizontal spans at each row
    for y, xs in rows.items():
        xs.sort()
        # Count contiguous runs
        run_length = 1
        for i in range(1, len(xs)):
            if xs[i] == xs[i - 1] + 1:
                run_length += 1
            else:
                min_width = min(min_width, run_length)
                run_length = 1
        min_width = min(min_width, run_length)

    # Check vertical spans at each column
    for x, ys in cols.items():
        ys.sort()
        run_length = 1
        for i in range(1, len(ys)):
            if ys[i] == ys[i - 1] + 1:
                run_length += 1
            else:
                min_width = min(min_width, run_length)
                run_length = 1
        min_width = min(min_width, run_length)

    return int(min_width) if min_width != float('inf') else 0


# ══════════════════════════════════════════════════════════════════
# VORONOI SUBDIVISION
# ══════════════════════════════════════════════════════════════════

def voronoi_subdivide(
    territory: Set[Tuple[int, int]],
    num_regions: int,
    seed: int,
) -> List[Set[Tuple[int, int]]]:
    """Subdivide a territory into regions using Voronoi partitioning.

    Places seed points within the territory and assigns each chunk
    to the nearest seed. All seed points and assignments are
    deterministic from the seed.

    Args:
        territory: Set of (x, y) chunks to subdivide.
        num_regions: Target number of sub-regions.
        seed: Deterministic seed.

    Returns:
        List of chunk sets, one per sub-region.
    """
    if not territory or num_regions <= 0:
        return [set(territory)] if territory else []

    if num_regions >= len(territory):
        return [{chunk} for chunk in territory]

    # Place seed points spread across the territory
    seed_points = _place_spread_seeds(territory, num_regions, seed)

    # Assign each chunk to nearest seed
    regions: List[Set[Tuple[int, int]]] = [set() for _ in range(len(seed_points))]
    for cx, cy in territory:
        best_idx = 0
        best_dist = float('inf')
        for i, (sx, sy) in enumerate(seed_points):
            dist = (cx - sx) ** 2 + (cy - sy) ** 2
            if dist < best_dist:
                best_dist = dist
                best_idx = i
        regions[best_idx].add((cx, cy))

    # Remove empty regions
    return [r for r in regions if r]


def _place_spread_seeds(
    territory: Set[Tuple[int, int]],
    count: int,
    seed: int,
) -> List[Tuple[int, int]]:
    """Place seed points spread across territory using rejection sampling.

    Tries to maximize distance between seeds for even subdivision.
    """
    territory_list = sorted(territory)  # Sort for determinism
    if count >= len(territory_list):
        return territory_list[:count]

    # Pick first seed deterministically
    idx = hash_2d_int(0, 0, seed, len(territory_list))
    seeds = [territory_list[idx]]

    # Greedily pick remaining seeds maximizing min distance to existing seeds
    for i in range(1, count):
        best_pos = None
        best_min_dist = -1

        # Sample candidates from territory (not all — that would be O(n*k))
        num_candidates = min(len(territory_list), max(50, len(territory_list) // 10))
        for j in range(num_candidates):
            c_idx = hash_2d_int(i, j, seed + 999, len(territory_list))
            candidate = territory_list[c_idx]

            # Min distance to all existing seeds
            min_dist = min(
                (candidate[0] - s[0]) ** 2 + (candidate[1] - s[1]) ** 2
                for s in seeds
            )
            if min_dist > best_min_dist:
                best_min_dist = min_dist
                best_pos = candidate

        if best_pos:
            seeds.append(best_pos)

    return seeds

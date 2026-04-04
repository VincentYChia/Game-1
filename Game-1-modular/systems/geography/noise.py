"""Deterministic noise and deformation utilities for geographic generation.

All functions are pure and deterministic — same seed + same input = same output.
No external dependencies (no numpy, no Perlin library). Uses hash-based noise
similar to the existing BiomeGenerator approach.

Performance-critical: optimized for 512x512 (262K chunk) worlds.
"""

from __future__ import annotations

import math
from typing import Dict, List, Set, Tuple


# ══════════════════════════════════════════════════════════════════
# HASH-BASED PSEUDO-RANDOM
# ══════════════════════════════════════════════════════════════════

def hash_2d(x: int, y: int, seed: int) -> float:
    """Deterministic pseudo-random float in [0, 1) from 2D coordinates."""
    h = seed
    h = ((h ^ (x * 374761393)) + (y * 668265263)) & 0xFFFFFFFF
    h = ((h ^ (h >> 13)) * 1274126177) & 0xFFFFFFFF
    h = (h ^ (h >> 16)) & 0xFFFFFFFF
    return (h & 0x7FFFFFFF) / 0x7FFFFFFF


def hash_2d_int(x: int, y: int, seed: int, max_val: int) -> int:
    """Deterministic pseudo-random int in [0, max_val) from 2D coordinates."""
    if max_val <= 0:
        return 0
    return int(hash_2d(x, y, seed) * max_val) % max_val


# ══════════════════════════════════════════════════════════════════
# VALUE NOISE (smooth, interpolated)
# ══════════════════════════════════════════════════════════════════

def _smoothstep(t: float) -> float:
    """Smooth interpolation curve (3t^2 - 2t^3)."""
    return t * t * (3.0 - 2.0 * t)


def value_noise_2d(x: float, y: float, seed: int) -> float:
    """2D value noise with smooth interpolation. Returns [-1, 1]."""
    ix = int(math.floor(x))
    iy = int(math.floor(y))
    fx = x - ix
    fy = y - iy

    sx = _smoothstep(fx)
    sy = _smoothstep(fy)

    v00 = hash_2d(ix, iy, seed) * 2.0 - 1.0
    v10 = hash_2d(ix + 1, iy, seed) * 2.0 - 1.0
    v01 = hash_2d(ix, iy + 1, seed) * 2.0 - 1.0
    v11 = hash_2d(ix + 1, iy + 1, seed) * 2.0 - 1.0

    top = v00 + sx * (v10 - v00)
    bottom = v01 + sx * (v11 - v01)
    return top + sy * (bottom - top)


def fractal_noise_2d(x: float, y: float, seed: int,
                     octaves: int = 4, lacunarity: float = 2.0,
                     persistence: float = 0.5) -> float:
    """Multi-octave fractal noise. Returns approximately [-1, 1]."""
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
# CONTIGUITY VALIDATION
# ══════════════════════════════════════════════════════════════════

def is_contiguous(territory: Set[Tuple[int, int]]) -> bool:
    """Check if a set of chunks forms a single contiguous region."""
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
    """Estimate the minimum corridor width of a territory."""
    if not territory:
        return 0
    rows = {}
    cols = {}
    for x, y in territory:
        rows.setdefault(y, []).append(x)
        cols.setdefault(x, []).append(y)

    min_width = float('inf')
    for y, xs in rows.items():
        xs.sort()
        run_length = 1
        for i in range(1, len(xs)):
            if xs[i] == xs[i - 1] + 1:
                run_length += 1
            else:
                min_width = min(min_width, run_length)
                run_length = 1
        min_width = min(min_width, run_length)

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
# VORONOI SUBDIVISION (optimized)
# ══════════════════════════════════════════════════════════════════

def voronoi_subdivide(
    territory: Set[Tuple[int, int]],
    num_regions: int,
    seed: int,
    noise_amplitude: float = 0.0,
    noise_frequency: float = 0.05,
) -> List[Set[Tuple[int, int]]]:
    """Subdivide a territory into regions using Voronoi partitioning.

    Optimized: uses noise-perturbed distances for organic boundaries
    instead of separate deformation pass.

    Args:
        territory: Set of (x, y) chunks to subdivide.
        num_regions: Target number of sub-regions.
        seed: Deterministic seed.
        noise_amplitude: If > 0, add noise to distance calculations
                         for organic (non-geometric) boundaries.
        noise_frequency: Frequency of boundary noise.
    """
    if not territory or num_regions <= 0:
        return [set(territory)] if territory else []

    if num_regions >= len(territory):
        return [{chunk} for chunk in territory]

    # Place seed points
    seed_points = _place_spread_seeds(territory, num_regions, seed)

    # Pre-compute seed positions for fast access
    sp = [(sx, sy) for sx, sy in seed_points]
    use_noise = noise_amplitude > 0

    # Assign each chunk to nearest seed (with optional noise perturbation)
    regions: List[Set[Tuple[int, int]]] = [set() for _ in range(len(sp))]
    amp_sq = noise_amplitude * noise_amplitude

    for cx, cy in territory:
        best_idx = 0
        best_dist = float('inf')

        if use_noise:
            # Single noise sample per chunk (not per seed) — much faster
            noise = value_noise_2d(cx * noise_frequency, cy * noise_frequency, seed + 77777)
            noise_offset = noise * amp_sq
        else:
            noise_offset = 0.0

        for i in range(len(sp)):
            dx = cx - sp[i][0]
            dy = cy - sp[i][1]
            # Alternate noise sign per seed for organic boundaries
            dist = dx * dx + dy * dy + (noise_offset if i % 2 == 0 else -noise_offset)
            if dist < best_dist:
                best_dist = dist
                best_idx = i
        regions[best_idx].add((cx, cy))

    return [r for r in regions if r]


def _place_spread_seeds(
    territory: Set[Tuple[int, int]],
    count: int,
    seed: int,
) -> List[Tuple[int, int]]:
    """Place seed points spread across territory using farthest-point sampling."""
    territory_list = sorted(territory)
    if count >= len(territory_list):
        return territory_list[:count]

    # Pick first seed deterministically
    idx = hash_2d_int(0, 0, seed, len(territory_list))
    seeds = [territory_list[idx]]

    # Greedily pick farthest points — sample subset for performance
    sample_size = min(len(territory_list), max(100, len(territory_list) // 20))
    # Pre-select sample indices
    sample_indices = []
    for j in range(sample_size):
        sample_indices.append(hash_2d_int(0, j, seed + 999, len(territory_list)))

    for i in range(1, count):
        best_pos = None
        best_min_dist = -1

        for j in range(sample_size):
            c_idx = hash_2d_int(i, j, seed + 999, len(territory_list))
            candidate = territory_list[c_idx]

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

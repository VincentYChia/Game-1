"""Region generator — subdivides nations into geographic regions.

Regions are the large-scale geographic identity of an area.
Biomes derive FROM regions, not the other way around.

Optimized for 512x512 worlds using noise-perturbed Voronoi
(organic boundaries without expensive separate deformation pass).
"""

from __future__ import annotations

from typing import Dict, List, Set, Tuple

from systems.geography.config import GeographicConfig
from systems.geography.models import (
    NationData,
    RegionData,
    RegionIdentity,
)
from systems.geography.noise import (
    find_components,
    hash_2d,
    hash_2d_int,
    voronoi_subdivide,
)


_ALL_IDENTITIES = list(RegionIdentity)


def _determine_region_count(
    nation_id: int,
    nation_chunk_count: int,
    seed: int,
    config: GeographicConfig,
) -> int:
    """Determine how many regions a nation should have."""
    min_r = config.region.min_per_nation
    max_r = config.region.max_per_nation
    range_r = max_r - min_r

    size_factor = min(1.0, nation_chunk_count / 60000.0)
    base = min_r + size_factor * range_r

    variance = hash_2d(nation_id, 0, seed + 33333) * 2.0 - 1.0
    count = int(base + variance * 1.5)

    return max(min_r, min(max_r, count))


def _assign_identity(
    region_idx: int,
    nation_id: int,
    seed: int,
) -> RegionIdentity:
    """Assign a geographic identity to a region."""
    identity_idx = hash_2d_int(region_idx, nation_id, seed + 44444, len(_ALL_IDENTITIES))
    return _ALL_IDENTITIES[identity_idx]


def _fix_contiguity(
    regions: List[Set[Tuple[int, int]]],
) -> List[Set[Tuple[int, int]]]:
    """Ensure each region is contiguous. Merge fragments into neighbors."""
    result = list(regions)

    for i in range(len(result)):
        components = find_components(result[i])
        if len(components) <= 1:
            continue

        components.sort(key=len, reverse=True)
        main = components[0]
        result[i] = main

        for fragment in components[1:]:
            merge_target = _find_adjacent_region(fragment, result, i)
            if merge_target >= 0:
                result[merge_target] |= fragment
            else:
                result[i] |= fragment

    return result


def _find_adjacent_region(
    region: Set[Tuple[int, int]],
    all_regions: List[Set[Tuple[int, int]]],
    exclude_idx: int,
) -> int:
    """Find the index of an adjacent region to merge into."""
    neighbor_counts: Dict[int, int] = {}
    for cx, cy in region:
        for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
            neighbor = (cx + dx, cy + dy)
            for idx, other_region in enumerate(all_regions):
                if idx != exclude_idx and neighbor in other_region:
                    neighbor_counts[idx] = neighbor_counts.get(idx, 0) + 1
                    break

    if not neighbor_counts:
        return -1
    return max(neighbor_counts, key=neighbor_counts.get)


def _validate_region_areas(
    regions: List[Set[Tuple[int, int]]],
    nation_chunk_count: int,
    config: GeographicConfig,
) -> List[Set[Tuple[int, int]]]:
    """Merge regions that are too small into neighbors."""
    min_pct = config.region.min_area_pct
    min_area = int(nation_chunk_count * min_pct)

    result = list(regions)
    changed = True
    max_iterations = 10

    while changed and max_iterations > 0:
        changed = False
        max_iterations -= 1
        i = 0
        while i < len(result):
            if len(result[i]) < min_area and len(result) > 1:
                merge_target = _find_adjacent_region(result[i], result, i)
                if merge_target >= 0:
                    result[merge_target] |= result[i]
                    result.pop(i)
                    changed = True
                    continue
            i += 1

    return result


def _compute_bounds(chunks: Set[Tuple[int, int]]) -> Tuple[int, int, int, int]:
    """Compute bounding box (min_x, min_y, max_x, max_y)."""
    if not chunks:
        return (0, 0, 0, 0)
    xs = [c[0] for c in chunks]
    ys = [c[1] for c in chunks]
    return (min(xs), min(ys), max(xs), max(ys))


# ══════════════════════════════════════════════════════════════════
# PUBLIC API
# ══════════════════════════════════════════════════════════════════

def generate_regions(
    nation_map: Dict[Tuple[int, int], int],
    nation_metadata: Dict[int, NationData],
    seed: int,
    config: GeographicConfig,
) -> Tuple[Dict[Tuple[int, int], int], Dict[int, RegionData]]:
    """Generate regions within all nations.

    Uses noise-perturbed Voronoi for organic boundaries without
    expensive separate deformation pass.
    """
    nation_territories: Dict[int, Set[Tuple[int, int]]] = {}
    for pos, nid in nation_map.items():
        nation_territories.setdefault(nid, set()).add(pos)

    region_map: Dict[Tuple[int, int], int] = {}
    region_metadata: Dict[int, RegionData] = {}
    next_region_id = 0

    for nation_id, territory in sorted(nation_territories.items()):
        nation_data = nation_metadata.get(nation_id)
        if not nation_data or not territory:
            continue

        region_seed = seed + nation_id * 1000 + 100000

        # Determine region count
        region_count = _determine_region_count(
            nation_id, len(territory), region_seed, config,
        )

        # Voronoi with noise perturbation for organic boundaries
        raw_regions = voronoi_subdivide(
            territory, region_count, region_seed,
            noise_amplitude=config.region.deform_amplitude,
            noise_frequency=config.region.deform_frequency,
        )

        # Fix contiguity
        fixed_regions = _fix_contiguity(raw_regions)

        # Validate area constraints
        validated_regions = _validate_region_areas(
            fixed_regions, len(territory), config,
        )

        # Assign identities and build metadata
        for i, region_chunks in enumerate(validated_regions):
            if not region_chunks:
                continue

            rid = next_region_id
            next_region_id += 1

            identity = _assign_identity(i, nation_id, region_seed)

            region_metadata[rid] = RegionData(
                region_id=rid,
                name="",
                nation_id=nation_id,
                identity=identity,
                chunk_count=len(region_chunks),
                bounds=_compute_bounds(region_chunks),
            )

            nation_data.region_ids.append(rid)

            for pos in region_chunks:
                region_map[pos] = rid

    return region_map, region_metadata

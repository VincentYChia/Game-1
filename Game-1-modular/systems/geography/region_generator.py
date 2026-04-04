"""Region generator — subdivides nations into geographic regions.

Regions are the large-scale geographic identity of an area.
Biomes derive FROM regions, not the other way around.

Flow:
1. Determine region count per nation (3-8, from config)
2. Voronoi subdivide each nation's territory
3. Deform region boundaries with noise
4. Assign geographic identity (Forest, Mountains, etc.)
5. Validate constraints (contiguity, area percentages)
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
    deform_border,
    find_components,
    fractal_noise_2d,
    hash_2d,
    hash_2d_int,
    is_contiguous,
    voronoi_subdivide,
)


# All available region identities
_ALL_IDENTITIES = list(RegionIdentity)


def _determine_region_count(
    nation_id: int,
    nation_chunk_count: int,
    seed: int,
    config: GeographicConfig,
) -> int:
    """Determine how many regions a nation should have.

    Considers nation size and configured min/max.
    Larger nations tend to have more regions.
    """
    min_r = config.region.min_per_nation
    max_r = config.region.max_per_nation
    range_r = max_r - min_r

    # Base count scales with nation size
    # A nation with ~52K chunks (avg for 5 nations in 262K world) gets ~5 regions
    size_factor = min(1.0, nation_chunk_count / 60000.0)
    base = min_r + size_factor * range_r

    # Add seed-based variance
    variance = hash_2d(nation_id, 0, seed + 33333) * 2.0 - 1.0  # [-1, 1]
    count = int(base + variance * 1.5)

    return max(min_r, min(max_r, count))


def _assign_identity(
    region_idx: int,
    nation_id: int,
    region_chunks: Set[Tuple[int, int]],
    seed: int,
) -> RegionIdentity:
    """Assign a geographic identity to a region.

    Uses position-based heuristics and seed randomness.
    Tries to avoid adjacent regions with the same identity.
    """
    # Deterministic selection weighted by position
    identity_idx = hash_2d_int(region_idx, nation_id, seed + 44444, len(_ALL_IDENTITIES))
    return _ALL_IDENTITIES[identity_idx]


def _validate_region_areas(
    regions: List[Set[Tuple[int, int]]],
    nation_chunk_count: int,
    config: GeographicConfig,
) -> List[Set[Tuple[int, int]]]:
    """Validate that region areas fall within configured percentages.

    Merges regions that are too small into their largest neighbor.
    Splits regions that are too large (by adding a new Voronoi seed).
    """
    min_pct = config.region.min_area_pct
    max_pct = config.region.max_area_pct
    min_area = int(nation_chunk_count * min_pct)
    max_area = int(nation_chunk_count * max_pct)

    result = list(regions)
    changed = True
    max_iterations = 10

    while changed and max_iterations > 0:
        changed = False
        max_iterations -= 1

        # Merge tiny regions
        i = 0
        while i < len(result):
            if len(result[i]) < min_area and len(result) > 1:
                # Find adjacent region to merge into
                merge_target = _find_adjacent_region(result[i], result, i)
                if merge_target >= 0:
                    result[merge_target] |= result[i]
                    result.pop(i)
                    changed = True
                    continue
            i += 1

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


def _fix_contiguity(
    regions: List[Set[Tuple[int, int]]],
) -> List[Set[Tuple[int, int]]]:
    """Ensure each region is contiguous. Merge fragments into neighbors."""
    result = list(regions)

    for i in range(len(result)):
        components = find_components(result[i])
        if len(components) <= 1:
            continue

        # Keep largest, merge rest into nearest neighbor region
        components.sort(key=len, reverse=True)
        main = components[0]
        result[i] = main

        for fragment in components[1:]:
            merge_target = _find_adjacent_region(fragment, result, i)
            if merge_target >= 0:
                result[merge_target] |= fragment
            else:
                # Can't find neighbor — reattach to main
                result[i] |= fragment

    return result


def _compute_bounds(chunks: Set[Tuple[int, int]]) -> Tuple[int, int, int, int]:
    """Compute bounding box (min_x, min_y, max_x, max_y) for a chunk set."""
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

    Args:
        nation_map: Dict mapping (chunk_x, chunk_y) → nation_id.
        nation_metadata: Nation metadata from nation generator.
        seed: World seed.
        config: Geographic configuration.

    Returns:
        Tuple of:
        - region_map: Dict mapping (chunk_x, chunk_y) → region_id
        - region_metadata: Dict mapping region_id → RegionData
    """
    # Build per-nation territory sets
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

        # Step 1: Determine region count
        region_count = _determine_region_count(
            nation_id, len(territory), region_seed, config,
        )

        # Step 2: Voronoi subdivide
        raw_regions = voronoi_subdivide(territory, region_count, region_seed)

        # Step 3: Deform boundaries
        deformed_regions = []
        for i, region_chunks in enumerate(raw_regions):
            deformed = deform_border(
                region_chunks, region_chunks, region_seed + i * 100,
                amplitude=config.region.deform_amplitude,
                frequency=config.region.deform_frequency,
            )
            # Keep only chunks that are in the nation territory
            deformed &= territory
            deformed_regions.append(deformed)

        # Step 3b: Reassign any unassigned chunks (deformation may leave gaps)
        all_assigned = set()
        for r in deformed_regions:
            all_assigned |= r
        unassigned = territory - all_assigned
        if unassigned and deformed_regions:
            # Assign to nearest region
            for cx, cy in unassigned:
                best_idx = 0
                best_dist = float('inf')
                for idx, region_chunks in enumerate(deformed_regions):
                    for rx, ry in region_chunks:
                        d = (cx - rx) ** 2 + (cy - ry) ** 2
                        if d < best_dist:
                            best_dist = d
                            best_idx = idx
                        if d <= 1:
                            break
                    if best_dist <= 1:
                        break
                deformed_regions[best_idx].add((cx, cy))

        # Step 3c: Remove duplicate assignments (chunk in multiple regions)
        seen = set()
        for i, region_chunks in enumerate(deformed_regions):
            overlap = region_chunks & seen
            deformed_regions[i] -= overlap
            seen |= region_chunks

        # Step 4: Fix contiguity
        fixed_regions = _fix_contiguity(deformed_regions)

        # Step 5: Validate area constraints
        validated_regions = _validate_region_areas(
            fixed_regions, len(territory), config,
        )

        # Step 6: Assign identities and build metadata
        for i, region_chunks in enumerate(validated_regions):
            if not region_chunks:
                continue

            rid = next_region_id
            next_region_id += 1

            identity = _assign_identity(i, nation_id, region_chunks, region_seed)

            region_metadata[rid] = RegionData(
                region_id=rid,
                name="",  # Name assigned later by name_generator
                nation_id=nation_id,
                identity=identity,
                chunk_count=len(region_chunks),
                bounds=_compute_bounds(region_chunks),
            )

            # Update nation metadata
            nation_data.region_ids.append(rid)

            # Write to region map
            for pos in region_chunks:
                region_map[pos] = rid

    return region_map, region_metadata

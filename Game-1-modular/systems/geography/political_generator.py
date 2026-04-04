"""Political generator — provinces and districts.

Subdivides regions into provinces, and provinces into districts.
Both use the same Voronoi + deformation pattern at different scales.
"""

from __future__ import annotations

import math
from typing import Dict, List, Set, Tuple

from systems.geography.config import GeographicConfig
from systems.geography.models import (
    DistrictData,
    NationData,
    ProvinceData,
    RegionData,
)
from systems.geography.noise import (
    deform_border,
    find_components,
    hash_2d_int,
    voronoi_subdivide,
)
from systems.geography.region_generator import _compute_bounds, _fix_contiguity


def _determine_subdivision_count(
    parent_chunk_count: int,
    min_child_area: int,
    max_child_area: int,
    parent_id: int,
    seed: int,
) -> int:
    """Determine how many children a parent territory should have.

    Uses min/max child area to compute a valid range of child counts,
    then picks within that range using seed-based randomness.
    """
    if min_child_area <= 0:
        return 1

    # min_count: fewest children (each child at max size)
    min_count = max(2, parent_chunk_count // max_child_area)
    # max_count: most children (each child at min size)
    max_count = max(min_count, parent_chunk_count // min_child_area)

    if min_count >= max_count:
        return min_count

    # Pick within range using seed
    range_size = max_count - min_count + 1
    offset = hash_2d_int(parent_id, 0, seed, range_size)
    return min_count + offset


def _subdivide_territory(
    territories: Dict[int, Set[Tuple[int, int]]],
    parent_metadata: dict,
    seed_offset: int,
    seed: int,
    min_area: int,
    max_area: int,
    deform_amplitude: float,
    deform_frequency: float,
) -> Tuple[Dict[Tuple[int, int], int], List]:
    """Generic subdivision: split each parent territory into children.

    Returns mapping of chunk → child_id and list of (child_id, parent_id, chunks).
    """
    child_map: Dict[Tuple[int, int], int] = {}
    child_records = []
    next_id = 0

    for parent_id, territory in sorted(territories.items()):
        if not territory:
            continue

        child_seed = seed + parent_id * 500 + seed_offset

        # Determine how many children
        count = _determine_subdivision_count(
            len(territory), min_area, max_area, parent_id, child_seed,
        )

        if count <= 1:
            # Single child = entire territory
            cid = next_id
            next_id += 1
            for pos in territory:
                child_map[pos] = cid
            child_records.append((cid, parent_id, set(territory)))
            continue

        # Voronoi subdivide
        raw_children = voronoi_subdivide(territory, count, child_seed)

        # Deform boundaries
        deformed_children = []
        for i, child_chunks in enumerate(raw_children):
            deformed = deform_border(
                child_chunks, child_chunks, child_seed + i * 77,
                amplitude=deform_amplitude,
                frequency=deform_frequency,
            )
            deformed &= territory
            deformed_children.append(deformed)

        # Reassign unassigned chunks
        all_assigned = set()
        for c in deformed_children:
            all_assigned |= c
        unassigned = territory - all_assigned
        if unassigned and deformed_children:
            for cx, cy in unassigned:
                best_idx = 0
                best_dist = float('inf')
                for idx, child in enumerate(deformed_children):
                    if not child:
                        continue
                    for rx, ry in child:
                        d = (cx - rx) ** 2 + (cy - ry) ** 2
                        if d < best_dist:
                            best_dist = d
                            best_idx = idx
                        if d <= 1:
                            break
                    if best_dist <= 1:
                        break
                deformed_children[best_idx].add((cx, cy))

        # Remove overlaps
        seen = set()
        for i, child in enumerate(deformed_children):
            overlap = child & seen
            deformed_children[i] -= overlap
            seen |= child

        # Fix contiguity
        fixed = _fix_contiguity(deformed_children)

        # Merge children that are too small
        merged = _merge_tiny(fixed, min_area)

        # Record results
        for child_chunks in merged:
            if not child_chunks:
                continue
            cid = next_id
            next_id += 1
            for pos in child_chunks:
                child_map[pos] = cid
            child_records.append((cid, parent_id, child_chunks))

    return child_map, child_records


def _merge_tiny(
    children: List[Set[Tuple[int, int]]],
    min_area: int,
) -> List[Set[Tuple[int, int]]]:
    """Merge children smaller than min_area into adjacent siblings."""
    result = list(children)
    changed = True
    max_iter = 10

    while changed and max_iter > 0:
        changed = False
        max_iter -= 1
        i = 0
        while i < len(result):
            if len(result[i]) < min_area and len(result) > 1:
                # Find adjacent sibling to merge into
                best_idx = -1
                best_border = 0
                for cx, cy in result[i]:
                    for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                        neighbor = (cx + dx, cy + dy)
                        for j, other in enumerate(result):
                            if j != i and neighbor in other:
                                border = sum(
                                    1 for ax, ay in result[i]
                                    for ddx, ddy in [(-1, 0), (1, 0), (0, -1), (0, 1)]
                                    if (ax + ddx, ay + ddy) in other
                                )
                                if border > best_border:
                                    best_border = border
                                    best_idx = j
                                break

                if best_idx >= 0:
                    result[best_idx] |= result[i]
                    result.pop(i)
                    changed = True
                    continue
            i += 1

    return result


# ══════════════════════════════════════════════════════════════════
# PUBLIC API
# ══════════════════════════════════════════════════════════════════

def generate_provinces(
    region_map: Dict[Tuple[int, int], int],
    region_metadata: Dict[int, RegionData],
    nation_metadata: Dict[int, NationData],
    seed: int,
    config: GeographicConfig,
) -> Tuple[Dict[Tuple[int, int], int], Dict[int, ProvinceData]]:
    """Generate provinces within all regions.

    Returns:
        - province_map: (chunk_x, chunk_y) → province_id
        - province_metadata: province_id → ProvinceData
    """
    # Build per-region territories
    region_territories: Dict[int, Set[Tuple[int, int]]] = {}
    for pos, rid in region_map.items():
        region_territories.setdefault(rid, set()).add(pos)

    province_map, records = _subdivide_territory(
        territories=region_territories,
        parent_metadata=region_metadata,
        seed_offset=200000,
        seed=seed,
        min_area=config.province.min_area,
        max_area=config.province.max_area,
        deform_amplitude=config.province.deform_amplitude,
        deform_frequency=config.province.deform_frequency,
    )

    # Build province metadata
    province_metadata: Dict[int, ProvinceData] = {}
    for pid, parent_rid, chunks in records:
        region = region_metadata.get(parent_rid)
        nation_id = region.nation_id if region else -1

        province_metadata[pid] = ProvinceData(
            province_id=pid,
            name="",  # Name assigned later
            region_id=parent_rid,
            nation_id=nation_id,
            chunk_count=len(chunks),
            bounds=_compute_bounds(chunks),
        )

        # Update region metadata
        if region:
            region.province_ids.append(pid)

    return province_map, province_metadata


def generate_districts(
    province_map: Dict[Tuple[int, int], int],
    province_metadata: Dict[int, ProvinceData],
    seed: int,
    config: GeographicConfig,
) -> Tuple[Dict[Tuple[int, int], int], Dict[int, DistrictData]]:
    """Generate districts within all provinces.

    Returns:
        - district_map: (chunk_x, chunk_y) → district_id
        - district_metadata: district_id → DistrictData
    """
    # Build per-province territories
    province_territories: Dict[int, Set[Tuple[int, int]]] = {}
    for pos, pid in province_map.items():
        province_territories.setdefault(pid, set()).add(pos)

    district_map, records = _subdivide_territory(
        territories=province_territories,
        parent_metadata=province_metadata,
        seed_offset=300000,
        seed=seed,
        min_area=config.district.min_area,
        max_area=config.district.max_area,
        deform_amplitude=config.district.deform_amplitude,
        deform_frequency=config.district.deform_frequency,
    )

    # Build district metadata
    district_metadata: Dict[int, DistrictData] = {}
    for did, parent_pid, chunks in records:
        province = province_metadata.get(parent_pid)
        region_id = province.region_id if province else -1
        nation_id = province.nation_id if province else -1

        district_metadata[did] = DistrictData(
            district_id=did,
            name="",  # Name assigned later
            province_id=parent_pid,
            region_id=region_id,
            nation_id=nation_id,
            chunk_count=len(chunks),
            bounds=_compute_bounds(chunks),
        )

        # Update province metadata
        if province:
            province.district_ids.append(did)

    return district_map, district_metadata

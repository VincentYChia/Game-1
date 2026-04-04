"""Political generator — provinces and districts.

Subdivides regions into provinces, and provinces into districts.
Uses noise-perturbed Voronoi for organic boundaries at all scales.
Optimized for 512x512 worlds.
"""

from __future__ import annotations

from typing import Dict, List, Set, Tuple

from systems.geography.config import GeographicConfig
from systems.geography.models import (
    DistrictData,
    NationData,
    ProvinceData,
    RegionData,
)
from systems.geography.noise import (
    find_components,
    hash_2d_int,
    voronoi_subdivide,
)


def _compute_bounds(chunks: Set[Tuple[int, int]]) -> Tuple[int, int, int, int]:
    if not chunks:
        return (0, 0, 0, 0)
    xs = [c[0] for c in chunks]
    ys = [c[1] for c in chunks]
    return (min(xs), min(ys), max(xs), max(ys))


def _determine_subdivision_count(
    parent_chunk_count: int,
    min_child_area: int,
    max_child_area: int,
    parent_id: int,
    seed: int,
) -> int:
    """Determine how many children a parent territory should have."""
    if min_child_area <= 0:
        return 1

    min_count = max(2, parent_chunk_count // max_child_area)
    max_count = max(min_count, parent_chunk_count // min_child_area)

    if min_count >= max_count:
        return min_count

    range_size = max_count - min_count + 1
    offset = hash_2d_int(parent_id, 0, seed, range_size)
    return min_count + offset


def _fix_contiguity(regions: List[Set[Tuple[int, int]]]) -> List[Set[Tuple[int, int]]]:
    """Ensure each region is contiguous."""
    result = list(regions)
    for i in range(len(result)):
        components = find_components(result[i])
        if len(components) <= 1:
            continue
        components.sort(key=len, reverse=True)
        main = components[0]
        result[i] = main
        for fragment in components[1:]:
            # Find adjacent sibling
            merged = False
            for cx, cy in fragment:
                for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                    neighbor = (cx + dx, cy + dy)
                    for j, other in enumerate(result):
                        if j != i and neighbor in other:
                            result[j] |= fragment
                            merged = True
                            break
                    if merged:
                        break
                if merged:
                    break
            if not merged:
                result[i] |= fragment
    return result


def _merge_tiny(children: List[Set[Tuple[int, int]]], min_area: int) -> List[Set[Tuple[int, int]]]:
    """Merge children smaller than min_area into adjacent siblings."""
    result = list(children)
    changed = True
    max_iter = 5
    while changed and max_iter > 0:
        changed = False
        max_iter -= 1
        i = 0
        while i < len(result):
            if len(result[i]) < min_area and len(result) > 1:
                # Find adjacent sibling with most shared border
                best_idx = -1
                for cx, cy in result[i]:
                    for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                        neighbor = (cx + dx, cy + dy)
                        for j, other in enumerate(result):
                            if j != i and neighbor in other:
                                best_idx = j
                                break
                        if best_idx >= 0:
                            break
                    if best_idx >= 0:
                        break
                if best_idx >= 0:
                    result[best_idx] |= result[i]
                    result.pop(i)
                    changed = True
                    continue
            i += 1
    return result


def _subdivide_territories(
    territories: Dict[int, Set[Tuple[int, int]]],
    seed: int,
    seed_offset: int,
    min_area: int,
    max_area: int,
    noise_amplitude: float,
    noise_frequency: float,
) -> Tuple[Dict[Tuple[int, int], int], List]:
    """Generic subdivision using noise-perturbed Voronoi."""
    child_map: Dict[Tuple[int, int], int] = {}
    child_records = []
    next_id = 0

    for parent_id, territory in sorted(territories.items()):
        if not territory:
            continue

        child_seed = seed + parent_id * 500 + seed_offset
        count = _determine_subdivision_count(
            len(territory), min_area, max_area, parent_id, child_seed,
        )

        if count <= 1:
            cid = next_id
            next_id += 1
            for pos in territory:
                child_map[pos] = cid
            child_records.append((cid, parent_id, set(territory)))
            continue

        # Voronoi with noise perturbation
        raw_children = voronoi_subdivide(
            territory, count, child_seed,
            noise_amplitude=noise_amplitude,
            noise_frequency=noise_frequency,
        )

        # Fix contiguity and merge tiny regions
        fixed = _fix_contiguity(raw_children)
        merged = _merge_tiny(fixed, min_area)

        for child_chunks in merged:
            if not child_chunks:
                continue
            cid = next_id
            next_id += 1
            for pos in child_chunks:
                child_map[pos] = cid
            child_records.append((cid, parent_id, child_chunks))

    return child_map, child_records


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
    """Generate provinces within all regions."""
    region_territories: Dict[int, Set[Tuple[int, int]]] = {}
    for pos, rid in region_map.items():
        region_territories.setdefault(rid, set()).add(pos)

    province_map, records = _subdivide_territories(
        territories=region_territories,
        seed=seed,
        seed_offset=200000,
        min_area=config.province.min_area,
        max_area=config.province.max_area,
        noise_amplitude=config.province.deform_amplitude,
        noise_frequency=config.province.deform_frequency,
    )

    province_metadata: Dict[int, ProvinceData] = {}
    for pid, parent_rid, chunks in records:
        region = region_metadata.get(parent_rid)
        nation_id = region.nation_id if region else -1

        province_metadata[pid] = ProvinceData(
            province_id=pid,
            name="",
            region_id=parent_rid,
            nation_id=nation_id,
            chunk_count=len(chunks),
            bounds=_compute_bounds(chunks),
        )

        if region:
            region.province_ids.append(pid)

    return province_map, province_metadata


def generate_districts(
    province_map: Dict[Tuple[int, int], int],
    province_metadata: Dict[int, ProvinceData],
    seed: int,
    config: GeographicConfig,
) -> Tuple[Dict[Tuple[int, int], int], Dict[int, DistrictData]]:
    """Generate districts within all provinces."""
    province_territories: Dict[int, Set[Tuple[int, int]]] = {}
    for pos, pid in province_map.items():
        province_territories.setdefault(pid, set()).add(pos)

    district_map, records = _subdivide_territories(
        territories=province_territories,
        seed=seed,
        seed_offset=300000,
        min_area=config.district.min_area,
        max_area=config.district.max_area,
        noise_amplitude=config.district.deform_amplitude,
        noise_frequency=config.district.deform_frequency,
    )

    district_metadata: Dict[int, DistrictData] = {}
    for did, parent_pid, chunks in records:
        province = province_metadata.get(parent_pid)
        region_id = province.region_id if province else -1
        nation_id = province.nation_id if province else -1

        district_metadata[did] = DistrictData(
            district_id=did,
            name="",
            province_id=parent_pid,
            region_id=region_id,
            nation_id=nation_id,
            chunk_count=len(chunks),
            bounds=_compute_bounds(chunks),
        )

        if province:
            province.district_ids.append(did)

    return district_map, district_metadata

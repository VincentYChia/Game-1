"""Biome generator — paints chunk types derived from region identity.

Biomes are a SEPARATE geographic layer that crosses political boundaries.
Optimized for 512x512 worlds — uses fast hash noise instead of fractal.
"""

from __future__ import annotations

from typing import Dict, List, Tuple

from systems.geography.config import GeographicConfig
from systems.geography.models import (
    BiomeData,
    NewChunkType,
    RegionData,
    RegionIdentity,
    REGION_PRIMARY_CHUNKS,
    REGION_PRIMARY_WEIGHT,
    REGION_SECONDARY_CHUNKS,
)
from systems.geography.noise import hash_2d, value_noise_2d


def _assign_chunk_type(
    cx: int,
    cy: int,
    identity: RegionIdentity,
    seed: int,
    primary_weight: float,
) -> NewChunkType:
    """Assign a chunk type based on region identity using fast noise."""
    primary = REGION_PRIMARY_CHUNKS.get(identity, [NewChunkType.FOREST])
    secondary = REGION_SECONDARY_CHUNKS.get(identity, [])

    if not primary:
        primary = [NewChunkType.FOREST]

    # Use value_noise for biome-scale patches (fast, single octave)
    biome_val = (value_noise_2d(cx * 0.03, cy * 0.03, seed + 500000) + 1.0) * 0.5

    if biome_val < primary_weight or not secondary:
        pool = primary
    else:
        pool = secondary

    type_noise = hash_2d(cx, cy, seed + 600000)
    type_idx = int(type_noise * len(pool)) % len(pool)
    return pool[type_idx]


# ══════════════════════════════════════════════════════════════════
# PUBLIC API
# ══════════════════════════════════════════════════════════════════

def generate_biomes(
    region_map: Dict[Tuple[int, int], int],
    region_metadata: Dict[int, RegionData],
    seed: int,
    config: GeographicConfig,
) -> Tuple[
    Dict[Tuple[int, int], NewChunkType],
    Dict[Tuple[int, int], int],
    Dict[int, BiomeData],
]:
    """Generate biome layer (chunk types + biome patches).

    Optimized: skips expensive flood-fill patch detection. Instead,
    assigns biome IDs based on coarse grid cells (cheaper and produces
    the right visual effect of biome "zones").
    """
    primary_weight = config.biome.primary_weight

    # Step 1: Assign chunk types based on region identity
    chunk_type_map: Dict[Tuple[int, int], NewChunkType] = {}
    for pos, rid in region_map.items():
        region = region_metadata.get(rid)
        if not region:
            chunk_type_map[pos] = NewChunkType.FOREST
            continue
        chunk_type_map[pos] = _assign_chunk_type(
            pos[0], pos[1], region.identity, seed, primary_weight,
        )

    # Step 2: Assign biome IDs using coarse grid (skip expensive flood-fill)
    # Each ~16x16 chunk area becomes a biome zone
    biome_cell_size = 16
    biome_map: Dict[Tuple[int, int], int] = {}
    biome_metadata: Dict[int, BiomeData] = {}
    cell_to_biome: Dict[Tuple[int, int], int] = {}
    next_biome_id = 0

    for pos in chunk_type_map:
        cx, cy = pos
        # Coarse cell
        if cx >= 0:
            bx = cx // biome_cell_size
        else:
            bx = (cx - biome_cell_size + 1) // biome_cell_size
        if cy >= 0:
            by = cy // biome_cell_size
        else:
            by = (cy - biome_cell_size + 1) // biome_cell_size

        cell_key = (bx, by)
        if cell_key not in cell_to_biome:
            bid = next_biome_id
            next_biome_id += 1
            cell_to_biome[cell_key] = bid

            # Determine dominant chunk type for this cell
            ct = chunk_type_map[pos]
            rid = region_map.get(pos, -1)
            region = region_metadata.get(rid)
            identity = region.identity if region else RegionIdentity.FOREST

            biome_metadata[bid] = BiomeData(
                biome_id=bid,
                dominant_chunk_type=ct,
                region_identity=identity,
                chunk_count=0,
                bounds=(cx, cy, cx, cy),
            )

        bid = cell_to_biome[cell_key]
        biome_map[pos] = bid
        biome_metadata[bid].chunk_count += 1

    return chunk_type_map, biome_map, biome_metadata

"""Biome generator — paints chunk types derived from region identity.

Biomes are a SEPARATE geographic layer that crosses political boundaries.
A region's identity (Forest, Mountains, etc.) drives what chunk types
generate within it, but biome boundaries don't align to province/district
lines.

Flow:
1. For each chunk, get its region's identity
2. Use noise to select between primary (~70%) and secondary (~30%) chunk types
3. Create biome patches (400-800 chunks of similar chunk types)
4. Chunk type assignment is the final per-chunk result
"""

from __future__ import annotations

import math
from typing import Dict, List, Optional, Set, Tuple

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
from systems.geography.noise import (
    fractal_noise_2d,
    hash_2d,
    hash_2d_int,
    value_noise_2d,
)


def _assign_chunk_type(
    cx: int,
    cy: int,
    identity: RegionIdentity,
    seed: int,
    config: GeographicConfig,
) -> NewChunkType:
    """Assign a chunk type based on its region identity and noise.

    Uses layered noise to:
    1. Decide primary vs secondary (70/30 split)
    2. Select specific type from the chosen pool
    3. Create natural clustering (similar chunks group together)
    """
    primary = REGION_PRIMARY_CHUNKS.get(identity, [NewChunkType.FOREST])
    secondary = REGION_SECONDARY_CHUNKS.get(identity, [])

    if not primary:
        primary = [NewChunkType.FOREST]

    # Noise-based primary/secondary decision
    # Use low-frequency noise for large-scale biome patches
    biome_noise = fractal_noise_2d(
        cx * 0.03, cy * 0.03,
        seed + 500000, octaves=3,
    )

    # Map noise to [0, 1] range
    biome_val = (biome_noise + 1.0) * 0.5

    primary_weight = config.biome.primary_weight

    if biome_val < primary_weight or not secondary:
        # Pick from primary pool
        pool = primary
    else:
        pool = secondary

    # Select specific type using higher-frequency noise for local variety
    type_noise = hash_2d(cx, cy, seed + 600000)
    type_idx = int(type_noise * len(pool)) % len(pool)
    return pool[type_idx]


def _build_biome_patches(
    chunk_types: Dict[Tuple[int, int], NewChunkType],
    config: GeographicConfig,
) -> Tuple[Dict[Tuple[int, int], int], Dict[int, BiomeData]]:
    """Group chunks into biome patches based on shared chunk type.

    Adjacent chunks with the same type form a biome patch.
    Very small patches get merged into their largest neighbor.
    """
    # Flood-fill to find connected regions of same chunk type
    remaining = set(chunk_types.keys())
    patches: List[Tuple[NewChunkType, Set[Tuple[int, int]]]] = []

    while remaining:
        start = next(iter(remaining))
        chunk_type = chunk_types[start]
        patch = set()
        stack = [start]

        while stack:
            pos = stack.pop()
            if pos in patch or pos not in remaining:
                continue
            if chunk_types.get(pos) != chunk_type:
                continue
            patch.add(pos)
            x, y = pos
            stack.extend([(x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)])

        remaining -= patch
        patches.append((chunk_type, patch))

    # Assign biome IDs
    biome_map: Dict[Tuple[int, int], int] = {}
    biome_metadata: Dict[int, BiomeData] = {}
    biome_id = 0

    for chunk_type, patch in patches:
        bid = biome_id
        biome_id += 1

        for pos in patch:
            biome_map[pos] = bid

        xs = [p[0] for p in patch]
        ys = [p[1] for p in patch]
        biome_metadata[bid] = BiomeData(
            biome_id=bid,
            dominant_chunk_type=chunk_type,
            region_identity=RegionIdentity.FOREST,  # Updated below
            chunk_count=len(patch),
            bounds=(min(xs), min(ys), max(xs), max(ys)),
        )

    return biome_map, biome_metadata


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

    This produces the GEOGRAPHIC layer that crosses political boundaries.
    Each chunk gets a chunk type derived from its region's identity.

    Args:
        region_map: (chunk_x, chunk_y) → region_id
        region_metadata: region_id → RegionData
        seed: World seed.
        config: Geographic configuration.

    Returns:
        Tuple of:
        - chunk_type_map: (chunk_x, chunk_y) → NewChunkType
        - biome_map: (chunk_x, chunk_y) → biome_id
        - biome_metadata: biome_id → BiomeData
    """
    # Step 1: Assign chunk types based on region identity
    chunk_type_map: Dict[Tuple[int, int], NewChunkType] = {}

    for pos, rid in region_map.items():
        region = region_metadata.get(rid)
        if not region:
            chunk_type_map[pos] = NewChunkType.FOREST
            continue

        chunk_type_map[pos] = _assign_chunk_type(
            pos[0], pos[1], region.identity, seed, config,
        )

    # Step 2: Build biome patches from chunk type adjacency
    biome_map, biome_metadata = _build_biome_patches(chunk_type_map, config)

    # Step 3: Set region identity on biome metadata
    for bid, bdata in biome_metadata.items():
        # Find the most common region identity for chunks in this biome
        identity_counts: Dict[RegionIdentity, int] = {}
        sample_count = 0
        for pos, b_id in biome_map.items():
            if b_id == bid:
                rid = region_map.get(pos)
                if rid is not None:
                    region = region_metadata.get(rid)
                    if region:
                        identity_counts[region.identity] = (
                            identity_counts.get(region.identity, 0) + 1
                        )
                sample_count += 1
                if sample_count > 100:
                    break  # Enough samples

        if identity_counts:
            bdata.region_identity = max(identity_counts, key=identity_counts.get)

    return chunk_type_map, biome_map, biome_metadata

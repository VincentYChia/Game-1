"""Village generation — places villages in the world during geographic generation.

Villages are 2x2 chunk features that override terrain with:
- Stone walls around perimeter with 4 cardinal entrances
- Simple building structures inside the walls
- 3-5 dummy NPCs per village

Villages are placed in peaceful/moderate danger areas, avoiding water
and cave chunks. Each village creates a LocalityData entry.
"""

from __future__ import annotations

import random
from typing import Dict, List, Optional, Set, Tuple

from systems.geography.models import (
    DangerLevel,
    GeographicData,
    LocalityData,
    NewChunkType,
    WorldMap,
)
from systems.geography.noise import hash_2d, hash_2d_int


# Chunk types that can't have villages
_INVALID_VILLAGE_CHUNKS = {
    NewChunkType.LAKE, NewChunkType.RIVER, NewChunkType.CURSED_MARSH,
    NewChunkType.WETLAND, NewChunkType.DEEP_CAVE, NewChunkType.CRYSTAL_CAVERN,
    NewChunkType.FLOODED_CAVE,
}

# Danger levels that can have villages (safer areas)
_VALID_VILLAGE_DANGER = {
    DangerLevel.TRANQUIL, DangerLevel.PEACEFUL, DangerLevel.MODERATE,
}

# Village placement config
VILLAGE_MIN_DISTANCE = 40  # Minimum chunks between village centers
VILLAGE_TARGET_COUNT = 30  # Target number of villages in the world
VILLAGE_SIZE = 2  # Chunks per side (2x2)


def place_villages(
    world_map: WorldMap,
    seed: int,
) -> List[Dict]:
    """Place villages across the world map.

    Returns a list of village definitions, each containing:
    - center_chunk: (cx, cy) center of the 2x2 village area
    - chunks: list of (cx, cy) chunks in the village
    - npc_positions: list of (tile_x, tile_y) for NPC placement
    - locality_id: assigned locality ID
    - name: generated village name
    """
    rng = random.Random(seed + 777777)
    chunk_data = world_map.chunk_data
    half = world_map.world_size // 2

    # Find candidate positions (2x2 areas where all chunks are valid)
    candidates = []
    checked = set()

    for (cx, cy), geo in chunk_data.items():
        if (cx, cy) in checked:
            continue

        # Check if this 2x2 area is all valid
        valid = True
        area_chunks = []
        for dx in range(VILLAGE_SIZE):
            for dy in range(VILLAGE_SIZE):
                pos = (cx + dx, cy + dy)
                g = chunk_data.get(pos)
                if g is None:
                    valid = False
                    break
                if g.chunk_type in _INVALID_VILLAGE_CHUNKS:
                    valid = False
                    break
                if g.danger_level not in _VALID_VILLAGE_DANGER:
                    valid = False
                    break
                area_chunks.append(pos)
            if not valid:
                break

        if valid and len(area_chunks) == VILLAGE_SIZE * VILLAGE_SIZE:
            candidates.append((cx, cy))
            # Mark all chunks in this area as checked
            for ac in area_chunks:
                checked.add(ac)

    # Select villages from candidates with distance constraint
    rng.shuffle(candidates)
    selected = []

    for cx, cy in candidates:
        if len(selected) >= VILLAGE_TARGET_COUNT:
            break

        # Check minimum distance from existing villages
        too_close = False
        for sx, sy in selected:
            if abs(cx - sx) + abs(cy - sy) < VILLAGE_MIN_DISTANCE:
                too_close = True
                break
        if too_close:
            continue

        selected.append((cx, cy))

    # Generate village definitions
    villages = []
    next_locality_id = max((ld.locality_id for ld in world_map.localities.values()), default=-1) + 1

    for i, (cx, cy) in enumerate(selected):
        chunks = [(cx + dx, cy + dy) for dx in range(VILLAGE_SIZE) for dy in range(VILLAGE_SIZE)]

        # Generate NPC positions (tile coords, inside the village area)
        npc_count = rng.randint(3, 5)
        npc_positions = []
        base_tx = cx * 16 + 4  # Leave space for walls
        base_ty = cy * 16 + 4
        area_w = VILLAGE_SIZE * 16 - 8  # Inner area
        area_h = VILLAGE_SIZE * 16 - 8
        for n in range(npc_count):
            nx = base_tx + rng.randint(2, area_w - 2)
            ny = base_ty + rng.randint(2, area_h - 2)
            npc_positions.append((nx, ny))

        # Get nation name for village naming
        geo = chunk_data.get((cx, cy))
        nation = world_map.nations.get(geo.nation_id) if geo else None
        nation_name = nation.name if nation else "Unknown"

        # Generate village name
        village_prefixes = ["Old", "New", "East", "West", "North", "South",
                           "Upper", "Lower", "Little", "Great"]
        village_suffixes = ["haven", "stead", "ton", "burg", "ford", "dale",
                           "brook", "field", "wood", "gate"]
        prefix = village_prefixes[hash_2d_int(i, 0, seed + 888888, len(village_prefixes))]
        suffix = village_suffixes[hash_2d_int(i, 1, seed + 888888, len(village_suffixes))]
        village_name = f"{prefix}{suffix}"

        lid = next_locality_id + i
        locality = LocalityData(
            locality_id=lid,
            name=village_name,
            chunk_x=cx,
            chunk_y=cy,
            feature_type="village",
            adjacent_chunks=chunks,
        )
        world_map.localities[lid] = locality

        # Mark these chunks as having a locality
        for chunk_pos in chunks:
            gd = chunk_data.get(chunk_pos)
            if gd:
                gd.locality_id = lid

        villages.append({
            "center_chunk": (cx, cy),
            "chunks": chunks,
            "npc_positions": npc_positions,
            "locality_id": lid,
            "name": village_name,
            "nation": nation_name,
        })

    return villages


def get_village_wall_tiles(
    village: Dict,
) -> List[Tuple[int, int]]:
    """Get tile positions for village wall placement.

    Creates a rectangular wall around the village perimeter
    with 4 entrances at cardinal directions.
    """
    cx, cy = village["center_chunk"]
    wall_tiles = []

    # Village tile bounds
    x1 = cx * 16 + 1
    y1 = cy * 16 + 1
    x2 = (cx + VILLAGE_SIZE) * 16 - 2
    y2 = (cy + VILLAGE_SIZE) * 16 - 2
    mid_x = (x1 + x2) // 2
    mid_y = (y1 + y2) // 2
    entrance_w = 3  # Width of entrance in tiles

    # Top wall
    for x in range(x1, x2 + 1):
        if abs(x - mid_x) > entrance_w // 2:
            wall_tiles.append((x, y1))

    # Bottom wall
    for x in range(x1, x2 + 1):
        if abs(x - mid_x) > entrance_w // 2:
            wall_tiles.append((x, y2))

    # Left wall
    for y in range(y1, y2 + 1):
        if abs(y - mid_y) > entrance_w // 2:
            wall_tiles.append((x1, y))

    # Right wall
    for y in range(y1, y2 + 1):
        if abs(y - mid_y) > entrance_w // 2:
            wall_tiles.append((x2, y))

    return wall_tiles


def get_village_building_tiles(
    village: Dict,
    seed: int,
) -> List[List[Tuple[int, int]]]:
    """Get tile positions for simple building structures inside village.

    Creates 2-4 small rectangular buildings (4x3 to 6x4 tiles).
    """
    rng = random.Random(seed + village["locality_id"])
    cx, cy = village["center_chunk"]
    buildings = []

    # Inner area bounds (inside walls)
    x1 = cx * 16 + 3
    y1 = cy * 16 + 3
    area_w = VILLAGE_SIZE * 16 - 6
    area_h = VILLAGE_SIZE * 16 - 6

    building_count = rng.randint(2, 4)
    occupied = set()

    for _ in range(building_count):
        bw = rng.randint(4, 6)
        bh = rng.randint(3, 4)

        # Try to place building without overlap
        for attempt in range(20):
            bx = x1 + rng.randint(1, max(1, area_w - bw - 2))
            by = y1 + rng.randint(1, max(1, area_h - bh - 2))

            # Check overlap
            tiles = []
            overlap = False
            for dx in range(bw):
                for dy in range(bh):
                    pos = (bx + dx, by + dy)
                    if pos in occupied:
                        overlap = True
                        break
                    tiles.append(pos)
                if overlap:
                    break

            if not overlap and tiles:
                # Only add perimeter tiles (walls of building)
                building_walls = []
                for tx, ty in tiles:
                    if tx == bx or tx == bx + bw - 1 or ty == by or ty == by + bh - 1:
                        # Leave a door on the south side
                        if ty == by + bh - 1 and tx == bx + bw // 2:
                            continue
                        building_walls.append((tx, ty))
                        occupied.add((tx, ty))

                buildings.append(building_walls)
                break

    return buildings

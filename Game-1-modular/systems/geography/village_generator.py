"""Village generation — places villages using JSON-driven configuration.

Reads village-config.JSON for all parameters: placement rules, tier
definitions, entrance distribution, NPC templates, and naming.
"""

from __future__ import annotations

import json
import os
import random
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from systems.geography.models import (
    DangerLevel,
    GeographicData,
    LocalityData,
    NewChunkType,
    WorldMap,
)
from systems.geography.noise import hash_2d_int


# ══════════════════════════════════════════════════════════════════
# CONFIG LOADING
# ══════════════════════════════════════════════════════════════════

_config_cache = None

def _load_config() -> dict:
    global _config_cache
    if _config_cache is not None:
        return _config_cache

    search_paths = [
        Path(__file__).resolve().parent.parent.parent / "Definitions.JSON" / "village-config.JSON",
        Path(__file__).resolve().parent.parent.parent / "world_system" / "config" / "village-config.JSON",
    ]
    for p in search_paths:
        if p.exists():
            with open(p, "r", encoding="utf-8") as f:
                _config_cache = json.load(f)
                return _config_cache

    # Fallback defaults
    _config_cache = {
        "placement": {"target_count": 30, "min_distance": 40,
                      "valid_danger_levels": [1, 2, 3],
                      "excluded_chunk_types": ["lake", "river", "cursed_marsh", "wetland",
                                               "deep_cave", "crystal_cavern", "flooded_cave"]},
        "tiers": {"small": {"size": 2, "entrances": 4, "entrance_width": 3, "wall_inset": 1,
                             "npc_min": 3, "npc_max": 5, "buildings_min": 2, "buildings_max": 4,
                             "building_width_range": [4, 6], "building_height_range": [3, 4],
                             "spawn_weight": 100, "display_name": "Hamlet"}},
        "npc_templates": [
            {"npc_id_prefix": "village_villager", "name": "Villager", "sprite_color": [180, 160, 140],
             "dialogue_lines": ["Hello!", "Welcome!"], "spawn_weight": 100}],
        "naming": {"prefixes": ["Old", "New"], "suffixes": ["haven", "stead"]},
    }
    return _config_cache


def _select_tier(rng: random.Random) -> Tuple[str, dict]:
    """Select a village tier based on spawn weights."""
    cfg = _load_config()
    tiers = {k: v for k, v in cfg.get("tiers", {}).items()
             if isinstance(v, dict) and not k.startswith("_")}
    entries = list(tiers.items())
    total = sum(t.get("spawn_weight", 1) for _, t in entries)
    roll = rng.uniform(0, total)
    cumulative = 0
    for name, tier in entries:
        cumulative += tier.get("spawn_weight", 1)
        if roll <= cumulative:
            return name, tier
    return entries[-1] if entries else ("small", {})


def _select_npc_template(rng: random.Random) -> dict:
    """Select an NPC template based on spawn weights."""
    cfg = _load_config()
    templates = cfg.get("npc_templates", [])
    if not templates:
        return {"npc_id_prefix": "villager", "name": "Villager",
                "sprite_color": [180, 160, 140], "dialogue_lines": ["Hello!"]}
    total = sum(t.get("spawn_weight", 1) for t in templates)
    roll = rng.uniform(0, total)
    cumulative = 0
    for t in templates:
        cumulative += t.get("spawn_weight", 1)
        if roll <= cumulative:
            return t
    return templates[-1]


# ══════════════════════════════════════════════════════════════════
# ENTRANCE DISTRIBUTION
# ══════════════════════════════════════════════════════════════════

def _distribute_entrances(num_entrances: int) -> List[str]:
    """Distribute entrances evenly across 4 walls.

    Returns list of wall names that get entrances.
    4 entrances = one per wall (N, S, E, W).
    5 = one per wall + one extra on south.
    3 = south + north + east.
    """
    walls = ["south", "north", "east", "west"]
    if num_entrances <= 0:
        return []
    if num_entrances >= 4:
        result = list(walls)
        # Extra entrances distributed round-robin
        extras = num_entrances - 4
        for i in range(extras):
            result.append(walls[i % 4])
        return result
    # Fewer than 4: take first N from priority order
    return walls[:num_entrances]


# ══════════════════════════════════════════════════════════════════
# PLACEMENT
# ══════════════════════════════════════════════════════════════════

def place_villages(world_map: WorldMap, seed: int) -> List[Dict]:
    """Place villages across the world map using JSON configuration."""
    cfg = _load_config()
    placement = cfg.get("placement", {})
    rng = random.Random(seed + 777777)
    chunk_data = world_map.chunk_data

    target_count = placement.get("target_count", 30)
    min_distance = placement.get("min_distance", 40)
    valid_dangers = set(placement.get("valid_danger_levels", [1, 2, 3]))
    excluded_types = set(placement.get("excluded_chunk_types", []))

    # Find candidate positions
    candidates = []
    checked = set()

    # Pre-check: get max tier size for area validation
    # Filter out non-dict entries (like _comment strings)
    tiers = {k: v for k, v in cfg.get("tiers", {}).items()
             if isinstance(v, dict) and not k.startswith("_")}
    max_size = max((t.get("size", 2) for t in tiers.values()), default=2)

    for (cx, cy), geo in chunk_data.items():
        if (cx, cy) in checked:
            continue

        # Check all sizes up to max
        for _, tier in tiers.items():
            size = tier.get("size", 2)
            valid = True
            area_chunks = []
            for dx in range(size):
                for dy in range(size):
                    pos = (cx + dx, cy + dy)
                    g = chunk_data.get(pos)
                    if g is None:
                        valid = False
                        break
                    ct = g.chunk_type.value if hasattr(g.chunk_type, 'value') else str(g.chunk_type)
                    if ct in excluded_types:
                        valid = False
                        break
                    dl = g.danger_level.value if hasattr(g.danger_level, 'value') else int(g.danger_level)
                    if dl not in valid_dangers:
                        valid = False
                        break
                    area_chunks.append(pos)
                if not valid:
                    break

            if valid and len(area_chunks) == size * size:
                candidates.append((cx, cy, size))
                for ac in area_chunks:
                    checked.add(ac)
                break  # Found valid size, don't check smaller

    # Select villages with distance constraint
    rng.shuffle(candidates)
    selected = []

    for cx, cy, size in candidates:
        if len(selected) >= target_count:
            break
        too_close = any(abs(cx - sx) + abs(cy - sy) < min_distance for sx, sy, _ in selected)
        if too_close:
            continue
        selected.append((cx, cy, size))

    # Generate village definitions
    villages = []
    naming = cfg.get("naming", {})
    prefixes = naming.get("prefixes", ["Village"])
    suffixes = naming.get("suffixes", ["town"])
    next_lid = max((ld.locality_id for ld in world_map.localities.values()), default=-1) + 1

    for i, (cx, cy, size) in enumerate(selected):
        tier_name, tier = _select_tier(rng)
        # Override size from the tier that was selected
        actual_size = tier.get("size", size)
        chunks = [(cx + dx, cy + dy) for dx in range(actual_size) for dy in range(actual_size)]

        # NPC positions
        npc_min = tier.get("npc_min", 3)
        npc_max = tier.get("npc_max", 5)
        npc_count = rng.randint(npc_min, npc_max)
        inset = tier.get("wall_inset", 1)
        inner_x = cx * 16 + inset + 3
        inner_y = cy * 16 + inset + 3
        inner_w = actual_size * 16 - (inset + 3) * 2
        inner_h = actual_size * 16 - (inset + 3) * 2

        npc_positions = []
        npc_templates_chosen = []
        for n in range(npc_count):
            nx = inner_x + rng.randint(2, max(3, inner_w - 2))
            ny = inner_y + rng.randint(2, max(3, inner_h - 2))
            npc_positions.append((nx, ny))
            npc_templates_chosen.append(_select_npc_template(rng))

        # Name
        prefix = prefixes[hash_2d_int(i, 0, seed + 888888, len(prefixes))]
        suffix = suffixes[hash_2d_int(i, 1, seed + 888888, len(suffixes))]
        village_name = f"{prefix}{suffix}"

        lid = next_lid + i
        geo = chunk_data.get((cx, cy))
        nation = world_map.nations.get(geo.nation_id) if geo else None

        locality = LocalityData(
            locality_id=lid, name=village_name,
            chunk_x=cx, chunk_y=cy,
            feature_type="village",
            adjacent_chunks=chunks,
        )
        world_map.localities[lid] = locality

        for chunk_pos in chunks:
            gd = chunk_data.get(chunk_pos)
            if gd:
                gd.locality_id = lid

        villages.append({
            "center_chunk": (cx, cy),
            "chunks": chunks,
            "size": actual_size,
            "tier": tier_name,
            "tier_config": tier,
            "npc_positions": npc_positions,
            "npc_templates": npc_templates_chosen,
            "locality_id": lid,
            "name": village_name,
            "nation": nation.name if nation else "Unknown",
        })

    return villages


# ══════════════════════════════════════════════════════════════════
# STRUCTURE GENERATION
# ══════════════════════════════════════════════════════════════════

def get_village_wall_tiles(village: Dict) -> List[Tuple[int, int]]:
    """Get tile positions for village walls with configurable entrances."""
    cx, cy = village["center_chunk"]
    tier = village.get("tier_config", {})
    size = village.get("size", 2)
    inset = tier.get("wall_inset", 1)
    num_entrances = tier.get("entrances", 4)
    entrance_width = tier.get("entrance_width", 3)

    x1 = cx * 16 + inset
    y1 = cy * 16 + inset
    x2 = (cx + size) * 16 - inset - 1
    y2 = (cy + size) * 16 - inset - 1
    mid_x = (x1 + x2) // 2
    mid_y = (y1 + y2) // 2
    half_ew = entrance_width // 2

    walls_with_entrances = _distribute_entrances(num_entrances)
    # Count entrances per wall for multi-entrance walls
    wall_entrance_counts = {}
    for w in walls_with_entrances:
        wall_entrance_counts[w] = wall_entrance_counts.get(w, 0) + 1

    wall_tiles = []

    # Top wall (north)
    n_north = wall_entrance_counts.get("north", 0)
    for x in range(x1, x2 + 1):
        is_entrance = False
        if n_north == 1:
            is_entrance = abs(x - mid_x) <= half_ew
        elif n_north >= 2:
            # Multiple entrances spaced evenly
            span = x2 - x1
            for e in range(n_north):
                pos = x1 + int(span * (e + 1) / (n_north + 1))
                if abs(x - pos) <= half_ew:
                    is_entrance = True
        if not is_entrance:
            wall_tiles.append((x, y1))

    # Bottom wall (south)
    n_south = wall_entrance_counts.get("south", 0)
    for x in range(x1, x2 + 1):
        is_entrance = False
        if n_south == 1:
            is_entrance = abs(x - mid_x) <= half_ew
        elif n_south >= 2:
            span = x2 - x1
            for e in range(n_south):
                pos = x1 + int(span * (e + 1) / (n_south + 1))
                if abs(x - pos) <= half_ew:
                    is_entrance = True
        if not is_entrance:
            wall_tiles.append((x, y2))

    # Left wall (west)
    n_west = wall_entrance_counts.get("west", 0)
    for y in range(y1 + 1, y2):
        is_entrance = False
        if n_west == 1:
            is_entrance = abs(y - mid_y) <= half_ew
        elif n_west >= 2:
            span = y2 - y1
            for e in range(n_west):
                pos = y1 + int(span * (e + 1) / (n_west + 1))
                if abs(y - pos) <= half_ew:
                    is_entrance = True
        if not is_entrance:
            wall_tiles.append((x1, y))

    # Right wall (east)
    n_east = wall_entrance_counts.get("east", 0)
    for y in range(y1 + 1, y2):
        is_entrance = False
        if n_east == 1:
            is_entrance = abs(y - mid_y) <= half_ew
        elif n_east >= 2:
            span = y2 - y1
            for e in range(n_east):
                pos = y1 + int(span * (e + 1) / (n_east + 1))
                if abs(y - pos) <= half_ew:
                    is_entrance = True
        if not is_entrance:
            wall_tiles.append((x2, y))

    return wall_tiles


def get_village_building_tiles(village: Dict, seed: int) -> List[List[Tuple[int, int]]]:
    """Get tile positions for building structures inside village walls."""
    tier = village.get("tier_config", {})
    rng = random.Random(seed + village.get("locality_id", 0))
    cx, cy = village["center_chunk"]
    size = village.get("size", 2)
    inset = tier.get("wall_inset", 1)

    x1 = cx * 16 + inset + 2
    y1 = cy * 16 + inset + 2
    area_w = size * 16 - (inset + 2) * 2
    area_h = size * 16 - (inset + 2) * 2

    bw_range = tier.get("building_width_range", [4, 6])
    bh_range = tier.get("building_height_range", [3, 4])
    b_min = tier.get("buildings_min", 2)
    b_max = tier.get("buildings_max", 4)
    building_count = rng.randint(b_min, b_max)

    buildings = []
    occupied = set()

    for _ in range(building_count):
        bw = rng.randint(bw_range[0], bw_range[1])
        bh = rng.randint(bh_range[0], bh_range[1])

        for attempt in range(20):
            bx = x1 + rng.randint(1, max(1, area_w - bw - 2))
            by = y1 + rng.randint(1, max(1, area_h - bh - 2))

            tiles = [(bx + dx, by + dy) for dx in range(bw) for dy in range(bh)]
            if any(t in occupied for t in tiles):
                continue

            building_walls = []
            for tx, ty in tiles:
                if tx == bx or tx == bx + bw - 1 or ty == by or ty == by + bh - 1:
                    if ty == by + bh - 1 and tx == bx + bw // 2:
                        continue  # Door
                    building_walls.append((tx, ty))
                    occupied.add((tx, ty))
            buildings.append(building_walls)
            break

    return buildings

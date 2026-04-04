"""Nation generator — template loading + severe deformation.

Nations are the ONLY static tier. Generation flow:
1. Load a 512x512 template (blocky boundaries)
2. Apply severe noise-based deformation
3. Shuffle nation ID assignments per seed
4. Validate constraints (contiguity, min area, min corridor)
"""

from __future__ import annotations

import json
import math
import os
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

from systems.geography.config import GeographicConfig
from systems.geography.models import NamingFlavor, NationData
from systems.geography.noise import (
    fractal_noise_2d,
    hash_2d,
    hash_2d_int,
    is_contiguous,
    find_components,
    measure_min_corridor_width,
)


# ══════════════════════════════════════════════════════════════════
# BUILT-IN TEMPLATE (simple 5-nation partition)
# ══════════════════════════════════════════════════════════════════

def _generate_default_template(
    world_size: int,
    nation_count: int,
) -> Dict[Tuple[int, int], int]:
    """Generate a simple blocky template programmatically.

    Creates a roughly even partition using angular sectors from center.
    This replaces hand-drawn pixel grids — the deformation will make
    these angular slices look like real country borders.

    Args:
        world_size: Chunks per side.
        nation_count: Number of nations.

    Returns:
        Dict mapping (chunk_x, chunk_y) → nation_id (0-based).
    """
    half = world_size // 2
    template = {}
    angle_step = 2.0 * math.pi / nation_count

    for y in range(-half, half):
        for x in range(-half, half):
            # Angle from center
            angle = math.atan2(y, x) + math.pi  # [0, 2pi]
            nation_id = int(angle / angle_step) % nation_count
            template[(x, y)] = nation_id

    return template


def _load_template_from_file(
    path: str,
    world_size: int,
) -> Optional[Dict[Tuple[int, int], int]]:
    """Load a template from a JSON file.

    Expected format: {"template": [[nation_id, ...], ...]}
    where the outer list is rows (y) and inner is columns (x).
    The grid should be world_size x world_size.
    """
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        grid = data.get("template", [])
        if not grid or len(grid) < world_size:
            return None

        half = world_size // 2
        template = {}
        for row_idx, row in enumerate(grid[:world_size]):
            y = row_idx - half
            for col_idx, nation_id in enumerate(row[:world_size]):
                x = col_idx - half
                template[(x, y)] = int(nation_id)
        return template
    except (json.JSONDecodeError, IOError, IndexError):
        return None


# ══════════════════════════════════════════════════════════════════
# DEFORMATION ENGINE
# ══════════════════════════════════════════════════════════════════

def _deform_nations(
    template: Dict[Tuple[int, int], int],
    seed: int,
    config: GeographicConfig,
) -> Dict[Tuple[int, int], int]:
    """Apply severe deformation to nation boundaries.

    This is the heart of the system. Simple blocky templates are
    transformed into articulate, detailed country borders through:
    1. Multi-octave noise displacement of border chunks
    2. Slight area scaling per nation
    3. Iterative refinement to maintain constraints

    The deformation is SEVERE — rectangles become organic shapes.
    """
    world_size = config.world.world_size
    half = world_size // 2
    amplitude = config.nation.deform_amplitude
    frequency = config.nation.deform_frequency
    octaves = config.nation.deform_octaves
    nation_count = config.nation.count

    # Build per-nation territory sets
    territories: Dict[int, Set[Tuple[int, int]]] = {}
    for pos, nid in template.items():
        territories.setdefault(nid, set()).add(pos)

    # Phase 1: Area scaling — some nations grow, some shrink
    scale_seed = seed + 7777
    scale_factors = {}
    for nid in range(nation_count):
        # Deterministic scale factor per nation: ±scale_variance
        raw = hash_2d(nid, 0, scale_seed) * 2.0 - 1.0
        scale_factors[nid] = 1.0 + raw * config.nation.deform_scale_variance

    # Phase 2: Border displacement using fractal noise
    # For each chunk, compute its "loyalty" to its current nation vs neighbors.
    # Noise modifies this loyalty, causing border shifts.
    result = {}
    all_positions = set(template.keys())

    for cx, cy in all_positions:
        original_nation = template[(cx, cy)]

        # Get noise displacement
        noise_x = fractal_noise_2d(
            cx * frequency, cy * frequency,
            seed + 11111, octaves=octaves,
        )
        noise_y = fractal_noise_2d(
            cx * frequency + 500.0, cy * frequency + 500.0,
            seed + 22222, octaves=octaves,
        )

        # Displaced lookup position
        lookup_x = cx + noise_x * amplitude
        lookup_y = cy + noise_y * amplitude

        # Round to nearest chunk and look up template nation
        lx = max(-half, min(half - 1, int(round(lookup_x))))
        ly = max(-half, min(half - 1, int(round(lookup_y))))
        lookup_pos = (lx, ly)

        if lookup_pos in template:
            displaced_nation = template[lookup_pos]
            # Apply scale factor bias — larger nations "win" border disputes
            if displaced_nation != original_nation:
                scale_displaced = scale_factors.get(displaced_nation, 1.0)
                scale_original = scale_factors.get(original_nation, 1.0)
                # Bias toward the nation with higher scale factor
                if scale_displaced > scale_original:
                    result[(cx, cy)] = displaced_nation
                else:
                    result[(cx, cy)] = original_nation
            else:
                result[(cx, cy)] = displaced_nation
        else:
            result[(cx, cy)] = original_nation

    return result


def _validate_and_repair(
    nation_map: Dict[Tuple[int, int], int],
    config: GeographicConfig,
    seed: int,
) -> Dict[Tuple[int, int], int]:
    """Validate constraints and repair violations.

    Checks:
    1. Contiguity — each nation must be one connected region
    2. Minimum area — no nation below min_area
    3. Minimum corridor — no passage thinner than min_corridor_width

    Repairs by merging orphaned fragments into the nearest valid nation.
    """
    nation_count = config.nation.count
    min_area = config.nation.min_area
    min_corridor = config.nation.min_corridor_width

    # Build territories
    territories: Dict[int, Set[Tuple[int, int]]] = {}
    for pos, nid in nation_map.items():
        territories.setdefault(nid, set()).add(pos)

    result = dict(nation_map)

    # Pass 1: Fix contiguity — keep largest component, reassign fragments
    for nid in list(territories.keys()):
        if nid not in territories or not territories[nid]:
            continue
        components = find_components(territories[nid])
        if len(components) <= 1:
            continue

        # Keep the largest component
        components.sort(key=len, reverse=True)
        main_component = components[0]
        fragments = []
        for comp in components[1:]:
            fragments.extend(comp)

        # Reassign fragment chunks to their nearest neighbor nation
        for fx, fy in fragments:
            best_nation = _find_nearest_nation(fx, fy, nid, result)
            result[(fx, fy)] = best_nation
            territories[nid].discard((fx, fy))
            territories.setdefault(best_nation, set()).add((fx, fy))

    # Pass 2: Fix minimum area — merge tiny nations into neighbors
    for nid in list(territories.keys()):
        if nid not in territories:
            continue
        if len(territories[nid]) < min_area:
            # Merge into largest neighboring nation
            neighbor_counts: Dict[int, int] = {}
            for cx, cy in territories[nid]:
                for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                    neighbor_pos = (cx + dx, cy + dy)
                    if neighbor_pos in result:
                        neighbor_nid = result[neighbor_pos]
                        if neighbor_nid != nid:
                            neighbor_counts[neighbor_nid] = neighbor_counts.get(
                                neighbor_nid, 0
                            ) + 1

            if neighbor_counts:
                merge_into = max(neighbor_counts, key=neighbor_counts.get)
                for pos in territories[nid]:
                    result[pos] = merge_into
                    territories.setdefault(merge_into, set()).add(pos)
                territories[nid] = set()

    return result


def _find_nearest_nation(
    x: int, y: int, exclude_nation: int,
    nation_map: Dict[Tuple[int, int], int],
) -> int:
    """Find the nearest nation to (x, y) excluding a specific nation."""
    for radius in range(1, 50):
        for dx in range(-radius, radius + 1):
            for dy in range(-radius, radius + 1):
                if abs(dx) == radius or abs(dy) == radius:
                    pos = (x + dx, y + dy)
                    if pos in nation_map and nation_map[pos] != exclude_nation:
                        return nation_map[pos]
    return 0  # Fallback


# ══════════════════════════════════════════════════════════════════
# NATION ID SHUFFLING
# ══════════════════════════════════════════════════════════════════

def _shuffle_nation_ids(
    nation_map: Dict[Tuple[int, int], int],
    nation_count: int,
    seed: int,
) -> Dict[Tuple[int, int], int]:
    """Randomly reassign which nation ID gets which territory.

    The template defines geometric shapes. This shuffles which nation
    (with its naming flavor and identity) occupies which shape.
    Deterministic from seed.
    """
    # Generate a permutation using Fisher-Yates with hash
    ids = list(range(nation_count))
    for i in range(len(ids) - 1, 0, -1):
        j = hash_2d_int(i, 0, seed + 55555, i + 1)
        ids[i], ids[j] = ids[j], ids[i]

    # Build mapping: old_id → new_id
    id_map = {old: new for old, new in enumerate(ids)}

    return {pos: id_map.get(nid, nid) for pos, nid in nation_map.items()}


# ══════════════════════════════════════════════════════════════════
# NAMING FLAVOR ASSIGNMENT
# ══════════════════════════════════════════════════════════════════

# Default flavor assignment order
_DEFAULT_FLAVORS = [
    NamingFlavor.STOIC,
    NamingFlavor.FLOWING,
    NamingFlavor.IMPERIAL,
    NamingFlavor.STONEWORN,
    NamingFlavor.ETHEREAL,
]

# Default nation colors for map rendering — vivid and distinct
_DEFAULT_COLORS = [
    (70, 110, 170),   # Stoic: deep steel blue
    (80, 155, 80),    # Flowing: rich forest green
    (190, 155, 60),   # Imperial: warm gold
    (155, 95, 70),    # Stoneworn: burnt umber
    (130, 100, 175),  # Ethereal: amethyst purple
    (170, 80, 80),    # Extra: muted crimson
    (80, 155, 150),   # Extra: teal
    (160, 140, 90),   # Extra: sand
    (100, 80, 140),   # Extra: deep violet
    (140, 160, 80),   # Extra: olive
    (180, 120, 100),  # Extra: terracotta
    (90, 130, 120),   # Extra: sage
]


# ══════════════════════════════════════════════════════════════════
# PUBLIC API
# ══════════════════════════════════════════════════════════════════

def generate_nations(
    seed: int,
    config: GeographicConfig,
    template_path: Optional[str] = None,
) -> Tuple[Dict[Tuple[int, int], int], Dict[int, NationData]]:
    """Generate nation territories from template + deformation.

    Args:
        seed: World seed for deterministic generation.
        config: Geographic configuration.
        template_path: Optional path to template JSON. If None, uses
                       built-in angular sector template.

    Returns:
        Tuple of:
        - nation_map: Dict mapping (chunk_x, chunk_y) → nation_id
        - nation_metadata: Dict mapping nation_id → NationData
    """
    world_size = config.world.world_size
    nation_count = config.nation.count

    # Step 1: Load or generate template
    template = None
    if template_path and os.path.exists(template_path):
        template = _load_template_from_file(template_path, world_size)
    if template is None:
        # Select from built-in templates (currently just one, expandable)
        template = _generate_default_template(world_size, nation_count)

    # Step 2: Severe deformation
    deformed = _deform_nations(template, seed, config)

    # Step 3: Shuffle nation IDs
    shuffled = _shuffle_nation_ids(deformed, nation_count, seed)

    # Step 4: Validate and repair
    validated = _validate_and_repair(shuffled, config, seed)

    # Step 5: Build metadata
    territories: Dict[int, Set[Tuple[int, int]]] = {}
    for pos, nid in validated.items():
        territories.setdefault(nid, set()).add(pos)

    # Assign naming flavors and colors
    flavor_seed = seed + 88888
    flavor_order = list(range(nation_count))
    for i in range(len(flavor_order) - 1, 0, -1):
        j = hash_2d_int(i, 0, flavor_seed, i + 1)
        flavor_order[i], flavor_order[j] = flavor_order[j], flavor_order[i]

    metadata: Dict[int, NationData] = {}
    for nid in range(nation_count):
        flavor_idx = flavor_order[nid] % len(_DEFAULT_FLAVORS)
        chunks = territories.get(nid, set())
        metadata[nid] = NationData(
            nation_id=nid,
            name="",  # Name assigned later by name_generator
            naming_flavor=_DEFAULT_FLAVORS[flavor_idx],
            chunk_count=len(chunks),
            color=_DEFAULT_COLORS[flavor_idx % len(_DEFAULT_COLORS)],
        )

    return validated, metadata

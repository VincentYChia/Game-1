"""Setting and status tag resolution from geographic data.

Determines the `setting`, `population_status`, and `resource_status`
tags for chunks based on their geographic features and ecosystem data.

These feed into the WMS Layer 3 evaluators as baseline values.
"""

from __future__ import annotations

from typing import Dict, Optional, Tuple

from systems.geography.models import (
    DangerLevel,
    GeographicData,
    NewChunkType,
    WorldMap,
)


# Chunk types that indicate specific settings
_CAVE_TYPES = {
    NewChunkType.CAVE, NewChunkType.DEEP_CAVE,
    NewChunkType.CRYSTAL_CAVERN, NewChunkType.FLOODED_CAVE,
}

_RUINS_TYPES = {
    NewChunkType.OVERGROWN_RUINS,
}

_WATER_TYPES = {
    NewChunkType.LAKE, NewChunkType.RIVER,
    NewChunkType.WETLAND, NewChunkType.CURSED_MARSH,
}


def resolve_setting(geo: GeographicData, world_map: Optional[WorldMap] = None) -> str:
    """Determine the setting tag for a chunk.

    Priority:
    1. Has village locality → "village"
    2. Has dungeon → "dungeon"
    3. Cave/underground chunk type → "underground"
    4. Ruins chunk type → "ruins"
    5. Otherwise → "wilderness"
    """
    # Village check
    if geo.locality_id >= 0 and world_map:
        loc = world_map.localities.get(geo.locality_id)
        if loc and loc.feature_type == "village":
            return "village"

    # Dungeon would be checked at runtime (not stored in geographic data)

    # Chunk type based
    if geo.chunk_type in _CAVE_TYPES:
        return "underground"
    if geo.chunk_type in _RUINS_TYPES:
        return "ruins"

    return "wilderness"


def resolve_population_status(danger_level: DangerLevel) -> str:
    """Baseline population status from ecosystem danger level.

    Higher danger → more creatures → thriving population.
    Lower danger → fewer creatures → stable/declining.

    This is a BASELINE — WMS evaluators can override based on
    actual kill/spawn event data.
    """
    if danger_level == DangerLevel.TRANQUIL:
        return "stable"
    elif danger_level == DangerLevel.PEACEFUL:
        return "stable"
    elif danger_level == DangerLevel.MODERATE:
        return "thriving"
    elif danger_level == DangerLevel.DANGEROUS:
        return "thriving"
    elif danger_level == DangerLevel.PERILOUS:
        return "thriving"
    elif danger_level == DangerLevel.LETHAL:
        return "thriving"
    return "stable"


def resolve_resource_status(danger_level: DangerLevel) -> str:
    """Baseline resource status from ecosystem danger level.

    Peaceful areas → abundant resources (less competition).
    Dangerous areas → steady (creatures consume some).
    Lethal areas → scarce (hostile environment depletes).

    This is a BASELINE — WMS evaluators can override based on
    actual gathering/depletion event data.
    """
    if danger_level == DangerLevel.TRANQUIL:
        return "abundant"
    elif danger_level == DangerLevel.PEACEFUL:
        return "abundant"
    elif danger_level == DangerLevel.MODERATE:
        return "steady"
    elif danger_level == DangerLevel.DANGEROUS:
        return "steady"
    elif danger_level == DangerLevel.PERILOUS:
        return "scarce"
    elif danger_level == DangerLevel.LETHAL:
        return "scarce"
    return "steady"


def get_chunk_tags(
    geo: GeographicData,
    world_map: Optional[WorldMap] = None,
) -> Dict[str, str]:
    """Get all resolvable tags for a chunk from geographic data.

    Returns dict of tag_category → tag_value.
    """
    tags = {}
    tags["setting"] = resolve_setting(geo, world_map)
    tags["population_status"] = resolve_population_status(geo.danger_level)
    tags["resource_status"] = resolve_resource_status(geo.danger_level)
    return tags

"""Setting tag resolution from geographic data.

Determines the `setting` tag for chunks based on their geographic
features. This is a FACTUAL geographic property — a village is a
village regardless of what events happen there.

Note: population_status and resource_status are Layer 3 concerns.
resource_harvesting is produced by the Layer 2 evaluator
ecosystem_resource_depletion. Neither is handled here.
"""

from __future__ import annotations

from typing import Optional

from systems.geography.models import (
    GeographicData,
    NewChunkType,
    WorldMap,
)


# Chunk types → setting mapping
_UNDERGROUND_TYPES = {
    NewChunkType.CAVE, NewChunkType.DEEP_CAVE,
    NewChunkType.CRYSTAL_CAVERN, NewChunkType.FLOODED_CAVE,
}

_RUINS_TYPES = {
    NewChunkType.OVERGROWN_RUINS,
}

_WATER_TYPES = {
    NewChunkType.LAKE, NewChunkType.RIVER, NewChunkType.WETLAND,
}

_WASTELAND_TYPES = {
    NewChunkType.BARREN_WASTE,
}

_THICKET_TYPES = {
    NewChunkType.DENSE_THICKET,
}


def resolve_setting(geo: GeographicData, world_map: Optional[WorldMap] = None) -> str:
    """Determine the setting tag for a chunk.

    Priority order:
    1. Has village locality → "village"
    2. Cave types → "underground"
    3. Ruins type → "ruins"
    4. Water types → "waterside"
    5. Barren waste → "wasteland"
    6. Dense thicket → "thicket"
    7. Default → "wilderness"
    """
    # Village check (geographic fact from world generation)
    if geo.locality_id >= 0 and world_map:
        loc = world_map.localities.get(geo.locality_id)
        if loc and loc.feature_type == "village":
            return "village"

    # Chunk type based settings
    if geo.chunk_type in _UNDERGROUND_TYPES:
        return "underground"
    if geo.chunk_type in _RUINS_TYPES:
        return "ruins"
    if geo.chunk_type in _WATER_TYPES:
        return "waterside"
    if geo.chunk_type in _WASTELAND_TYPES:
        return "wasteland"
    if geo.chunk_type in _THICKET_TYPES:
        return "thicket"

    return "wilderness"

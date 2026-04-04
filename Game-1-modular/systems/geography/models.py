"""Data models for the geographic system.

All enums, dataclasses, and type definitions for the world hierarchy:
World → Nation → Region → Province → District
                Region → Biome (separate geographic layer)
                Ecosystem (3x3 danger grouping)
                Locality (sparse POI)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, IntEnum
from typing import Dict, FrozenSet, List, Optional, Set, Tuple


# ══════════════════════════════════════════════════════════════════
# CHUNK TYPES (15) — recipes of existing resources + enemies
# ══════════════════════════════════════════════════════════════════

class NewChunkType(str, Enum):
    """15 chunk types defined by resource mix + enemy families.

    Each type is a recipe of existing game content — no new drops required.
    The str mixin allows direct use in JSON keys and string comparisons.
    """
    FOREST = "forest"
    DENSE_THICKET = "dense_thicket"
    CAVE = "cave"
    DEEP_CAVE = "deep_cave"
    QUARRY = "quarry"
    ROCKY_HIGHLANDS = "rocky_highlands"
    WETLAND = "wetland"
    LAKE = "lake"
    RIVER = "river"
    FLOODED_CAVE = "flooded_cave"
    ROCKY_FOREST = "rocky_forest"
    CRYSTAL_CAVERN = "crystal_cavern"
    OVERGROWN_RUINS = "overgrown_ruins"
    BARREN_WASTE = "barren_waste"
    CURSED_MARSH = "cursed_marsh"


# ══════════════════════════════════════════════════════════════════
# DANGER LEVELS (6 discrete)
# ══════════════════════════════════════════════════════════════════

class DangerLevel(IntEnum):
    """6 discrete danger levels for ecosystems.

    Each ecosystem (3x3 chunks) shares one danger level.
    Adjacent ecosystems may differ by at most ±2 levels.
    """
    TRANQUIL = 1
    PEACEFUL = 2
    MODERATE = 3
    DANGEROUS = 4
    PERILOUS = 5
    LETHAL = 6

    @property
    def display_name(self) -> str:
        return self.name.capitalize()

    @property
    def tier_weights(self) -> Dict[int, float]:
        """Enemy tier spawn weights for this danger level."""
        return DANGER_TIER_WEIGHTS[self]

    @property
    def spawn_density(self) -> str:
        return DANGER_SPAWN_DENSITY[self]


# Tier weights: {tier: probability} — must sum to 1.0
DANGER_TIER_WEIGHTS: Dict[DangerLevel, Dict[int, float]] = {
    DangerLevel.TRANQUIL:  {1: 1.00, 2: 0.00, 3: 0.00, 4: 0.00},
    DangerLevel.PEACEFUL:  {1: 0.80, 2: 0.15, 3: 0.05, 4: 0.00},
    DangerLevel.MODERATE:  {1: 0.60, 2: 0.30, 3: 0.10, 4: 0.00},
    DangerLevel.DANGEROUS: {1: 0.25, 2: 0.35, 3: 0.30, 4: 0.10},
    DangerLevel.PERILOUS:  {1: 0.15, 2: 0.20, 3: 0.45, 4: 0.20},
    DangerLevel.LETHAL:    {1: 0.00, 2: 0.15, 3: 0.45, 4: 0.40},
}

DANGER_SPAWN_DENSITY: Dict[DangerLevel, str] = {
    DangerLevel.TRANQUIL: "very_sparse",
    DangerLevel.PEACEFUL: "sparse",
    DangerLevel.MODERATE: "normal",
    DangerLevel.DANGEROUS: "dense",
    DangerLevel.PERILOUS: "dense",
    DangerLevel.LETHAL: "very_dense",
}

# Max ±2 gradient between neighboring ecosystems
DANGER_GRADIENT_MAX = 2


# ══════════════════════════════════════════════════════════════════
# REGION IDENTITY TYPES (10)
# ══════════════════════════════════════════════════════════════════

class RegionIdentity(str, Enum):
    """10 geographic identity types for regions.

    Each region IS its identity — "the great forest", "the mountain range".
    The identity drives which chunk types (biomes) generate within the region.
    """
    FOREST = "forest"
    MOUNTAINS = "mountains"
    PLAINS = "plains"
    STEPPE = "steppe"
    LOWLANDS = "lowlands"
    MARSHLANDS = "marshlands"
    CAVERNS = "caverns"
    HIGHLANDS = "highlands"
    LAKELAND = "lakeland"
    RUINS = "ruins"

    @property
    def display_name(self) -> str:
        return self.name.capitalize()

    @property
    def primary_chunks(self) -> List[NewChunkType]:
        """~70% of chunks in this region will be these types."""
        return REGION_PRIMARY_CHUNKS[self]

    @property
    def secondary_chunks(self) -> List[NewChunkType]:
        """~30% of chunks in this region will be these types."""
        return REGION_SECONDARY_CHUNKS[self]


# Region → primary chunk types (~70% generation weight)
REGION_PRIMARY_CHUNKS: Dict[RegionIdentity, List[NewChunkType]] = {
    RegionIdentity.FOREST: [
        NewChunkType.FOREST, NewChunkType.DENSE_THICKET,
    ],
    RegionIdentity.MOUNTAINS: [
        NewChunkType.ROCKY_HIGHLANDS, NewChunkType.QUARRY, NewChunkType.CAVE,
    ],
    RegionIdentity.PLAINS: [
        NewChunkType.FOREST, NewChunkType.QUARRY,
    ],
    RegionIdentity.STEPPE: [
        NewChunkType.BARREN_WASTE, NewChunkType.QUARRY,
    ],
    RegionIdentity.LOWLANDS: [
        NewChunkType.WETLAND, NewChunkType.FOREST,
    ],
    RegionIdentity.MARSHLANDS: [
        NewChunkType.WETLAND, NewChunkType.CURSED_MARSH,
    ],
    RegionIdentity.CAVERNS: [
        NewChunkType.CAVE, NewChunkType.DEEP_CAVE, NewChunkType.CRYSTAL_CAVERN,
    ],
    RegionIdentity.HIGHLANDS: [
        NewChunkType.ROCKY_HIGHLANDS, NewChunkType.ROCKY_FOREST,
    ],
    RegionIdentity.LAKELAND: [
        NewChunkType.LAKE, NewChunkType.RIVER, NewChunkType.WETLAND,
    ],
    RegionIdentity.RUINS: [
        NewChunkType.OVERGROWN_RUINS, NewChunkType.CRYSTAL_CAVERN,
    ],
}

# Region → secondary chunk types (~30% generation weight)
REGION_SECONDARY_CHUNKS: Dict[RegionIdentity, List[NewChunkType]] = {
    RegionIdentity.FOREST: [
        NewChunkType.ROCKY_FOREST, NewChunkType.WETLAND,
    ],
    RegionIdentity.MOUNTAINS: [
        NewChunkType.DEEP_CAVE, NewChunkType.BARREN_WASTE,
    ],
    RegionIdentity.PLAINS: [
        NewChunkType.ROCKY_HIGHLANDS, NewChunkType.WETLAND,
    ],
    RegionIdentity.STEPPE: [
        NewChunkType.ROCKY_HIGHLANDS, NewChunkType.OVERGROWN_RUINS,
    ],
    RegionIdentity.LOWLANDS: [
        NewChunkType.LAKE, NewChunkType.RIVER, NewChunkType.ROCKY_FOREST,
    ],
    RegionIdentity.MARSHLANDS: [
        NewChunkType.FLOODED_CAVE, NewChunkType.LAKE,
    ],
    RegionIdentity.CAVERNS: [
        NewChunkType.FLOODED_CAVE,
    ],
    RegionIdentity.HIGHLANDS: [
        NewChunkType.QUARRY, NewChunkType.FOREST,
    ],
    RegionIdentity.LAKELAND: [
        NewChunkType.FOREST, NewChunkType.FLOODED_CAVE,
    ],
    RegionIdentity.RUINS: [
        NewChunkType.DEEP_CAVE, NewChunkType.DENSE_THICKET,
    ],
}

# Generation ratio: primary vs secondary
REGION_PRIMARY_WEIGHT = 0.70
REGION_SECONDARY_WEIGHT = 0.30


# ══════════════════════════════════════════════════════════════════
# NAMING FLAVORS (5 nation cultural styles)
# ══════════════════════════════════════════════════════════════════

class NamingFlavor(str, Enum):
    """Cultural naming styles for nations — pure fantasy, no real cultures."""
    STOIC = "stoic"           # Heavy, northern, grim
    FLOWING = "flowing"       # Soft, musical, nature-touched
    IMPERIAL = "imperial"     # Formal, grand, structured
    STONEWORN = "stoneworn"   # Weathered, ancient, deep
    ETHEREAL = "ethereal"     # Mystical, luminous, otherworldly


# ══════════════════════════════════════════════════════════════════
# GEOGRAPHIC DATA — per-chunk lookup result
# ══════════════════════════════════════════════════════════════════

@dataclass
class GeographicData:
    """Complete geographic information for a single chunk.

    This is the primary lookup result — given (chunk_x, chunk_y),
    the WorldMap returns one of these with all layers resolved.
    """
    # Political hierarchy (every chunk has exactly one of each)
    nation_id: int = -1
    region_id: int = -1
    province_id: int = -1
    district_id: int = -1

    # Geographic layer (parallel to political)
    chunk_type: NewChunkType = NewChunkType.FOREST
    biome_id: int = -1

    # Danger layer
    ecosystem_id: int = -1
    danger_level: DangerLevel = DangerLevel.MODERATE

    # Locality (sparse — -1 means no locality here)
    locality_id: int = -1


# ══════════════════════════════════════════════════════════════════
# TIER DATA CLASSES — metadata for each geographic tier
# ══════════════════════════════════════════════════════════════════

@dataclass
class NationData:
    """Metadata for a nation (the only static tier)."""
    nation_id: int
    name: str
    naming_flavor: NamingFlavor
    chunk_count: int = 0
    region_ids: List[int] = field(default_factory=list)
    # Color for map rendering (R, G, B)
    color: Tuple[int, int, int] = (128, 128, 128)


@dataclass
class RegionData:
    """Metadata for a region within a nation."""
    region_id: int
    name: str
    nation_id: int
    identity: RegionIdentity = RegionIdentity.FOREST
    chunk_count: int = 0
    province_ids: List[int] = field(default_factory=list)
    # Bounding box in chunk coords (min_x, min_y, max_x, max_y)
    bounds: Tuple[int, int, int, int] = (0, 0, 0, 0)


@dataclass
class ProvinceData:
    """Metadata for a province within a region."""
    province_id: int
    name: str
    region_id: int
    nation_id: int
    chunk_count: int = 0
    district_ids: List[int] = field(default_factory=list)
    bounds: Tuple[int, int, int, int] = (0, 0, 0, 0)


@dataclass
class DistrictData:
    """Metadata for a district within a province."""
    district_id: int
    name: str
    province_id: int
    region_id: int
    nation_id: int
    chunk_count: int = 0
    bounds: Tuple[int, int, int, int] = (0, 0, 0, 0)


@dataclass
class BiomeData:
    """Metadata for a biome area (crosses political boundaries)."""
    biome_id: int
    dominant_chunk_type: NewChunkType
    region_identity: RegionIdentity
    chunk_count: int = 0
    bounds: Tuple[int, int, int, int] = (0, 0, 0, 0)


@dataclass
class EcosystemData:
    """Metadata for an ecosystem (3x3 chunk danger group)."""
    ecosystem_id: int
    danger_level: DangerLevel
    # Ecosystem grid position (not chunk position)
    eco_x: int = 0
    eco_y: int = 0


@dataclass
class LocalityData:
    """Metadata for a locality (sparse point of interest)."""
    locality_id: int
    name: str
    chunk_x: int
    chunk_y: int
    # What makes this place notable
    feature_type: str = ""  # "dungeon", "npc", "station", "rare_resource", etc.
    # Adjacent chunks that are part of this locality
    adjacent_chunks: List[Tuple[int, int]] = field(default_factory=list)


# ══════════════════════════════════════════════════════════════════
# WORLD MAP — the complete generated geographic data
# ══════════════════════════════════════════════════════════════════

@dataclass
class WorldMap:
    """Complete geographic map generated from a seed.

    The primary data structure is the chunk_data grid — a flat dict
    mapping (chunk_x, chunk_y) → GeographicData.

    All tier metadata (nations, regions, etc.) is stored in lookup dicts
    indexed by their respective IDs.
    """
    # World parameters
    seed: int = 0
    world_size: int = 512  # chunks per side (configurable, not hardcoded)

    # Per-chunk geographic data (the core lookup)
    chunk_data: Dict[Tuple[int, int], GeographicData] = field(default_factory=dict)

    # Tier metadata lookups
    nations: Dict[int, NationData] = field(default_factory=dict)
    regions: Dict[int, RegionData] = field(default_factory=dict)
    provinces: Dict[int, ProvinceData] = field(default_factory=dict)
    districts: Dict[int, DistrictData] = field(default_factory=dict)
    biomes: Dict[int, BiomeData] = field(default_factory=dict)
    ecosystems: Dict[int, EcosystemData] = field(default_factory=dict)
    localities: Dict[int, LocalityData] = field(default_factory=dict)

    # Coordinate system: chunks range from (-world_size//2) to (world_size//2 - 1)
    # so (0,0) is always near center

    @property
    def min_chunk(self) -> int:
        """Minimum chunk coordinate (inclusive)."""
        return -(self.world_size // 2)

    @property
    def max_chunk(self) -> int:
        """Maximum chunk coordinate (exclusive)."""
        return self.world_size // 2

    def in_bounds(self, chunk_x: int, chunk_y: int) -> bool:
        """Check if chunk coordinates are within world boundaries."""
        return (self.min_chunk <= chunk_x < self.max_chunk and
                self.min_chunk <= chunk_y < self.max_chunk)

    def get_chunk_data(self, chunk_x: int, chunk_y: int) -> Optional[GeographicData]:
        """Look up geographic data for a chunk. Returns None if out of bounds."""
        if not self.in_bounds(chunk_x, chunk_y):
            return None
        return self.chunk_data.get((chunk_x, chunk_y))

    def get_nation(self, nation_id: int) -> Optional[NationData]:
        return self.nations.get(nation_id)

    def get_region(self, region_id: int) -> Optional[RegionData]:
        return self.regions.get(region_id)

    def get_province(self, province_id: int) -> Optional[ProvinceData]:
        return self.provinces.get(province_id)

    def get_district(self, district_id: int) -> Optional[DistrictData]:
        return self.districts.get(district_id)

    def get_full_address(self, chunk_x: int, chunk_y: int) -> Optional[Dict[str, str]]:
        """Get the full named address for a chunk position."""
        data = self.get_chunk_data(chunk_x, chunk_y)
        if data is None:
            return None
        result = {}
        nation = self.nations.get(data.nation_id)
        if nation:
            result["nation"] = nation.name
        region = self.regions.get(data.region_id)
        if region:
            result["region"] = region.name
        province = self.provinces.get(data.province_id)
        if province:
            result["province"] = province.name
        district = self.districts.get(data.district_id)
        if district:
            result["district"] = district.name
        locality = self.localities.get(data.locality_id)
        if locality:
            result["locality"] = locality.name
        result["danger"] = data.danger_level.display_name
        result["chunk_type"] = data.chunk_type.value
        return result

"""Geographic System — generates the full world hierarchy from a seed.

Pipeline: Seed → Nations → Regions → Provinces → Districts
          Regions → Biomes (crosses political lines)
          Ecosystems (3x3 danger grouping)
          Localities (sparse POIs)

Usage:
    from systems.geography import WorldGenerator
    gen = WorldGenerator(seed=12345)
    world_map = gen.generate()
    # world_map.get_chunk_data(chunk_x, chunk_y) → GeographicData
"""

from systems.geography.models import (
    DangerLevel,
    RegionIdentity,
    GeographicData,
    NationData,
    RegionData,
    ProvinceData,
    DistrictData,
    BiomeData,
    EcosystemData,
    LocalityData,
)

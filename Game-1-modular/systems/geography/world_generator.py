"""World generator — orchestrates the full geographic generation pipeline.

This is the single entry point for generating a complete world from a seed.
It runs each generator in the correct order and assembles the WorldMap.

Pipeline:
    1. Nations (template + deformation)
    2. Regions (subdivision + identity assignment)
    3. Provinces (subdivision within regions)
    4. Districts (subdivision within provinces)
    5. Biomes (chunk types from region identity, crosses political lines)
    6. Ecosystems (3x3 danger grouping with gradient)
    7. Names (procedural, per-nation cultural banks)
    8. Assemble WorldMap

Usage:
    gen = WorldGenerator(seed=12345)
    world_map = gen.generate()
    data = world_map.get_chunk_data(0, 0)
    address = world_map.get_full_address(0, 0)
"""

from __future__ import annotations

import time
from typing import Optional

from systems.geography.config import GeographicConfig
from systems.geography.models import (
    DangerLevel,
    GeographicData,
    WorldMap,
)
from systems.geography.nation_generator import generate_nations
from systems.geography.region_generator import generate_regions
from systems.geography.political_generator import generate_provinces, generate_districts
from systems.geography.biome_generator import generate_biomes
from systems.geography.ecosystem_generator import generate_ecosystems
from systems.geography.name_generator import name_all


class WorldGenerator:
    """Generates a complete geographic world from a seed.

    All generation is deterministic — same seed + same config = same world.
    The generator produces a WorldMap that can be queried for any chunk's
    geographic data, or saved/loaded with the game state.
    """

    def __init__(
        self,
        seed: int,
        config: Optional[GeographicConfig] = None,
        template_path: Optional[str] = None,
    ):
        self.seed = seed
        self.config = config or GeographicConfig.load()
        self.template_path = template_path
        self._world_map: Optional[WorldMap] = None

    def generate(self, verbose: bool = False) -> WorldMap:
        """Run the full generation pipeline.

        Args:
            verbose: If True, print timing info for each phase.

        Returns:
            Complete WorldMap with all geographic data.
        """
        t_start = time.time()
        world_size = self.config.world.world_size

        if verbose:
            total_chunks = world_size * world_size
            print(f"Generating {world_size}x{world_size} world ({total_chunks:,} chunks)...")

        # Phase 1: Nations
        t = time.time()
        nation_map, nation_metadata = generate_nations(
            self.seed, self.config, self.template_path,
        )
        if verbose:
            print(f"  Nations: {len(nation_metadata)} nations in {time.time() - t:.2f}s")

        # Phase 2: Regions
        t = time.time()
        region_map, region_metadata = generate_regions(
            nation_map, nation_metadata, self.seed, self.config,
        )
        if verbose:
            print(f"  Regions: {len(region_metadata)} regions in {time.time() - t:.2f}s")

        # Phase 3: Provinces
        t = time.time()
        province_map, province_metadata = generate_provinces(
            region_map, region_metadata, nation_metadata,
            self.seed, self.config,
        )
        if verbose:
            print(f"  Provinces: {len(province_metadata)} provinces in {time.time() - t:.2f}s")

        # Phase 4: Districts
        t = time.time()
        district_map, district_metadata = generate_districts(
            province_map, province_metadata,
            self.seed, self.config,
        )
        if verbose:
            print(f"  Districts: {len(district_metadata)} districts in {time.time() - t:.2f}s")

        # Phase 5: Biomes (separate geographic branch)
        t = time.time()
        chunk_type_map, biome_map, biome_metadata = generate_biomes(
            region_map, region_metadata, self.seed, self.config,
        )
        if verbose:
            print(f"  Biomes: {len(biome_metadata)} patches in {time.time() - t:.2f}s")

        # Phase 6: Ecosystems (danger grouping)
        t = time.time()
        ecosystem_map, danger_map, ecosystem_metadata = generate_ecosystems(
            chunk_type_map, region_map, region_metadata,
            self.seed, self.config,
        )
        if verbose:
            print(f"  Ecosystems: {len(ecosystem_metadata)} groups in {time.time() - t:.2f}s")

        # Phase 7: Names
        t = time.time()
        # Localities are empty for now — villages will be added below
        localities = {}
        name_all(
            nation_metadata, region_metadata, province_metadata,
            district_metadata, localities, self.seed,
        )
        if verbose:
            print(f"  Names: applied in {time.time() - t:.2f}s")

        # Phase 8: Assemble WorldMap
        t = time.time()
        world_map = WorldMap(
            seed=self.seed,
            world_size=world_size,
            nations=nation_metadata,
            regions=region_metadata,
            provinces=province_metadata,
            districts=district_metadata,
            biomes=biome_metadata,
            ecosystems=ecosystem_metadata,
            localities=localities,
        )

        # Build per-chunk geographic data
        half = world_size // 2
        for y in range(-half, half):
            for x in range(-half, half):
                pos = (x, y)
                geo = GeographicData(
                    nation_id=nation_map.get(pos, -1),
                    region_id=region_map.get(pos, -1),
                    province_id=province_map.get(pos, -1),
                    district_id=district_map.get(pos, -1),
                    chunk_type=chunk_type_map.get(pos, chunk_type_map.get(pos)),
                    biome_id=biome_map.get(pos, -1),
                    ecosystem_id=ecosystem_map.get(pos, -1),
                    danger_level=danger_map.get(pos, DangerLevel.MODERATE),
                )
                world_map.chunk_data[pos] = geo

        if verbose:
            print(f"  Assembly: {len(world_map.chunk_data):,} chunks in {time.time() - t:.2f}s")

        # Phase 9: Villages
        t = time.time()
        try:
            from systems.geography.village_generator import place_villages
            self._villages = place_villages(world_map, self.seed)
            print(f"🏘️  {len(self._villages)} villages placed in {time.time() - t:.2f}s")
        except Exception as e:
            self._villages = []
            print(f"🏘️  Village placement failed: {e}")
            import traceback
            traceback.print_exc()

        if verbose:
            print(f"Total generation: {time.time() - t_start:.2f}s")
            self._print_summary(world_map)

        self._world_map = world_map
        return world_map

    @property
    def world_map(self) -> Optional[WorldMap]:
        """Get the generated world map, or None if not yet generated."""
        return self._world_map

    def _print_summary(self, wm: WorldMap) -> None:
        """Print a summary of the generated world."""
        print(f"\n=== World Summary (seed={wm.seed}) ===")
        print(f"Size: {wm.world_size}x{wm.world_size} chunks")

        for nid, nation in sorted(wm.nations.items()):
            print(f"\n  Nation {nid}: {nation.name} ({nation.naming_flavor.value})")
            print(f"    Chunks: {nation.chunk_count:,}")
            print(f"    Regions: {len(nation.region_ids)}")
            for rid in nation.region_ids:
                region = wm.regions.get(rid)
                if region:
                    print(f"      Region {rid}: {region.name} ({region.identity.value})")
                    print(f"        Chunks: {region.chunk_count:,}, Provinces: {len(region.province_ids)}")

        # Danger distribution
        danger_counts = {}
        for geo in wm.chunk_data.values():
            d = geo.danger_level
            danger_counts[d] = danger_counts.get(d, 0) + 1
        print(f"\n  Danger Distribution:")
        for dl in DangerLevel:
            count = danger_counts.get(dl, 0)
            pct = count / len(wm.chunk_data) * 100 if wm.chunk_data else 0
            print(f"    {dl.display_name}: {count:,} ({pct:.1f}%)")

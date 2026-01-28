"""Chunk system for world generation

Uses centered coordinate system where (0,0) is world center.
Chunk indices range from -half to +half (e.g., -5 to +5 for 11 chunks).
Water chunks can spawn anywhere except the spawn area, with spacing constraints.
"""

import random
import math
from typing import Dict, List, Set, Tuple, Optional, ClassVar

from data.models import Position, TileType, WorldTile, ChunkType, ResourceType, RESOURCE_TIERS
from systems.natural_resource import NaturalResource
from core.config import Config


class Chunk:
    """A 16x16 tile chunk of the world.

    Coordinates use centered system where chunk (0,0) contains the origin.
    Chunk (-5,-5) is the northwest corner, (+5,+5) is the southeast corner.
    """

    # Class-level tracking of water chunk positions to prevent cutting off areas
    _water_chunks: ClassVar[Set[Tuple[int, int]]] = set()
    _initialized: ClassVar[bool] = False

    @classmethod
    def _plan_water_chunks(cls) -> None:
        """Plan water chunk positions across the world.

        Water chunks are placed:
        - Anywhere except the spawn area (center 3x3 chunks)
        - Never adjacent to each other (minimum 2 chunks apart)
        - Approximately 8-12 water chunks total

        This allows water bodies to form naturally across the map
        rather than being restricted to edges only.
        """
        if cls._initialized:
            return

        cls._water_chunks = set()
        half = Config.NUM_CHUNKS // 2  # 5 for 11 chunks

        # Collect all valid chunk positions (excluding spawn area)
        valid_chunks = []
        for x in range(-half, half + 1):
            for y in range(-half, half + 1):
                # Skip spawn area (center 3x3 chunks)
                if abs(x) <= 1 and abs(y) <= 1:
                    continue
                valid_chunks.append((x, y))

        # Shuffle and select water chunks with spacing
        random.shuffle(valid_chunks)
        target_water_count = random.randint(8, 12)

        for cx, cy in valid_chunks:
            if len(cls._water_chunks) >= target_water_count:
                break

            # Check minimum distance from other water chunks (Manhattan distance >= 2)
            too_close = False
            for wx, wy in cls._water_chunks:
                if abs(cx - wx) + abs(cy - wy) < 3:  # Minimum spacing of 3
                    too_close = True
                    break

            if not too_close:
                cls._water_chunks.add((cx, cy))

        cls._initialized = True
        print(f"🌊 Planned {len(cls._water_chunks)} water chunks across the world")

    @classmethod
    def is_water_chunk(cls, chunk_x: int, chunk_y: int) -> bool:
        """Check if this position is designated as a water chunk."""
        cls._plan_water_chunks()
        return (chunk_x, chunk_y) in cls._water_chunks

    @classmethod
    def restore_water_chunks(cls, water_chunk_positions: List[Tuple[int, int]]) -> None:
        """Restore water chunk positions from save data.

        Args:
            water_chunk_positions: List of (chunk_x, chunk_y) tuples for water chunks
        """
        if water_chunk_positions:
            cls._water_chunks = set(tuple(pos) for pos in water_chunk_positions)
            cls._initialized = True
            print(f"🌊 Restored {len(cls._water_chunks)} water chunks from save")

    def __init__(self, chunk_x: int, chunk_y: int):
        self.chunk_x = chunk_x
        self.chunk_y = chunk_y
        self.tiles: Dict[str, WorldTile] = {}
        self.resources: List[NaturalResource] = []
        self.chunk_type = self._determine_chunk_type()
        self.generate_tiles()
        self.spawn_resources()

    def _determine_chunk_type(self) -> ChunkType:
        """Determine chunk type with spawn area protection and water placement.

        The center chunk (0,0) and adjacent chunks are always peaceful.
        Edge chunks may be designated as water during world planning.
        """
        # Check if this is a pre-planned water chunk
        if Chunk.is_water_chunk(self.chunk_x, self.chunk_y):
            return random.choice([ChunkType.WATER_LAKE, ChunkType.WATER_RIVER])

        # Spawn area protection: center 3x3 chunks are always peaceful
        if abs(self.chunk_x) <= 1 and abs(self.chunk_y) <= 1:
            return random.choice([ChunkType.PEACEFUL_FOREST, ChunkType.PEACEFUL_QUARRY, ChunkType.PEACEFUL_CAVE])

        roll = random.randint(1, 10)
        if roll <= 5:
            return random.choice([ChunkType.PEACEFUL_FOREST, ChunkType.PEACEFUL_QUARRY, ChunkType.PEACEFUL_CAVE])
        elif roll <= 8:
            return random.choice([ChunkType.DANGEROUS_FOREST, ChunkType.DANGEROUS_QUARRY, ChunkType.DANGEROUS_CAVE])
        else:
            # Rare chunks (20% chance): 75% land rare, 25% cursed swamp
            if random.random() < 0.25:
                return ChunkType.WATER_CURSED_SWAMP
            return random.choice([ChunkType.RARE_HIDDEN_FOREST, ChunkType.RARE_ANCIENT_QUARRY, ChunkType.RARE_DEEP_CAVE])

    def _is_water_chunk(self) -> bool:
        """Check if this chunk is a water type."""
        return self.chunk_type in (ChunkType.WATER_LAKE, ChunkType.WATER_RIVER, ChunkType.WATER_CURSED_SWAMP)

    def generate_tiles(self):
        """Generate tiles for this chunk using centered coordinates."""
        start_x = self.chunk_x * Config.CHUNK_SIZE
        start_y = self.chunk_y * Config.CHUNK_SIZE

        if self._is_water_chunk():
            self._generate_water_tiles(start_x, start_y)
        else:
            self._generate_land_tiles(start_x, start_y)

    def _generate_land_tiles(self, start_x: int, start_y: int):
        """Generate standard land tiles."""
        base_tile = TileType.STONE if "quarry" in self.chunk_type.value or "cave" in self.chunk_type.value else TileType.GRASS

        for x in range(start_x, start_x + Config.CHUNK_SIZE):
            for y in range(start_y, start_y + Config.CHUNK_SIZE):
                pos = Position(x, y, 0)
                tile_type = TileType.DIRT if random.random() < 0.1 else base_tile
                self.tiles[pos.to_key()] = WorldTile(pos, tile_type)

    def _generate_water_tiles(self, start_x: int, start_y: int):
        """Generate water tiles with guaranteed land border for passability.

        Water chunks have:
        - A 2-tile grass border on the side facing the map center (edge chunks)
        - Cursed swamps have land borders on ALL sides (can spawn anywhere)
        - Water tiles in the interior (65% for lake, 35% for river, 50% for swamp)
        - Optional islands (grass patches) in lakes and swamps
        """
        is_lake = self.chunk_type == ChunkType.WATER_LAKE
        is_swamp = self.chunk_type == ChunkType.WATER_CURSED_SWAMP

        if is_swamp:
            water_coverage = 0.50
        elif is_lake:
            water_coverage = 0.65
        else:
            water_coverage = 0.35

        chunk_size = Config.CHUNK_SIZE

        # Cursed swamps need land borders on ALL sides (not edge-only)
        # Edge water chunks only need borders facing the map center
        if is_swamp:
            needs_land_north = True
            needs_land_south = True
            needs_land_east = True
            needs_land_west = True
        else:
            # Edge water chunks - only border toward center
            needs_land_north = self.chunk_y > 0  # South edge of world
            needs_land_south = self.chunk_y < 0  # North edge of world
            needs_land_east = self.chunk_x < 0   # West edge of world
            needs_land_west = self.chunk_x > 0   # East edge of world

        for x in range(start_x, start_x + chunk_size):
            for y in range(start_y, start_y + chunk_size):
                local_x = x - start_x
                local_y = y - start_y
                pos = Position(x, y, 0)

                # Land border on edges (2 tiles wide for passability)
                is_land_border = False
                if needs_land_south and local_y < 2:
                    is_land_border = True
                if needs_land_north and local_y >= chunk_size - 2:
                    is_land_border = True
                if needs_land_west and local_x < 2:
                    is_land_border = True
                if needs_land_east and local_x >= chunk_size - 2:
                    is_land_border = True

                if is_land_border:
                    # Cursed swamp has dirt borders instead of grass
                    tile_type = TileType.DIRT if is_swamp else TileType.GRASS
                elif is_lake or is_swamp:
                    # Lake/Swamp: water with occasional islands
                    if random.random() < water_coverage:
                        tile_type = TileType.WATER
                    else:
                        tile_type = TileType.DIRT if is_swamp else TileType.GRASS  # Island
                else:
                    # River: create a flowing pattern
                    # River runs roughly through the middle
                    dist_from_center = abs(local_x - chunk_size // 2)
                    if dist_from_center < 3 and random.random() < 0.8:
                        tile_type = TileType.WATER
                    else:
                        tile_type = TileType.GRASS

                self.tiles[pos.to_key()] = WorldTile(pos, tile_type, walkable=(tile_type != TileType.WATER))

    def spawn_resources(self):
        """Spawn resources with safe zone and collision checks."""
        if self._is_water_chunk():
            self._spawn_fishing_spots()
            return

        start_x = self.chunk_x * Config.CHUNK_SIZE
        start_y = self.chunk_y * Config.CHUNK_SIZE

        # Determine resource count and tier based on chunk type
        if "peaceful" in self.chunk_type.value:
            resource_count, tier_range = random.randint(3, 6), (1, 2)
        elif "dangerous" in self.chunk_type.value:
            resource_count, tier_range = random.randint(5, 8), (2, 3)
        else:
            resource_count, tier_range = random.randint(6, 10), (3, 4)

        # Track occupied positions to prevent overlap
        occupied_positions: Set[Tuple[int, int]] = set()

        for _ in range(resource_count):
            # Try to find a valid position (up to 10 attempts)
            pos = None
            for attempt in range(10):
                candidate_x = start_x + random.randint(1, Config.CHUNK_SIZE - 2)
                candidate_y = start_y + random.randint(1, Config.CHUNK_SIZE - 2)

                # Check safe zone around origin (0, 0)
                dist_to_origin = math.sqrt(candidate_x ** 2 + candidate_y ** 2)
                if dist_to_origin < Config.SAFE_ZONE_RADIUS:
                    continue

                # Check collision with existing resources in this chunk
                if (candidate_x, candidate_y) in occupied_positions:
                    continue

                # Valid position found
                pos = Position(candidate_x, candidate_y, 0)
                occupied_positions.add((candidate_x, candidate_y))
                break

            if pos is None:
                continue  # Skip this resource if no valid position found

            # Determine resource type based on chunk terrain
            if "forest" in self.chunk_type.value:
                types = [ResourceType.OAK_TREE, ResourceType.BIRCH_TREE,
                         ResourceType.MAPLE_TREE, ResourceType.IRONWOOD_TREE]
            elif "quarry" in self.chunk_type.value:
                types = [ResourceType.LIMESTONE, ResourceType.GRANITE,
                         ResourceType.OBSIDIAN, ResourceType.STAR_CRYSTAL]
            else:
                types = [ResourceType.COPPER_ORE, ResourceType.IRON_ORE,
                         ResourceType.STEEL_ORE, ResourceType.MITHRIL_ORE]

            # Filter by tier
            tier = min(random.randint(*tier_range), 4)
            valid = [r for r in types if RESOURCE_TIERS[r] <= tier]
            if valid:
                resource_type = random.choice(valid)
                self.resources.append(NaturalResource(pos, resource_type, RESOURCE_TIERS[resource_type]))

    def _spawn_fishing_spots(self):
        """Spawn fishing spots on water tiles."""
        start_x = self.chunk_x * Config.CHUNK_SIZE
        start_y = self.chunk_y * Config.CHUNK_SIZE

        # Find water tiles
        water_tiles = []
        for key, tile in self.tiles.items():
            if tile.tile_type == TileType.WATER:
                water_tiles.append(tile.position)

        # Determine tier based on water type
        # Cursed swamp has higher tier fishing (3-4), lake/river are tier 1-2
        is_swamp = self.chunk_type == ChunkType.WATER_CURSED_SWAMP
        if is_swamp:
            tier_range = (3, 4)  # High tier fishing in cursed swamp
            num_spots = min(random.randint(5, 8), len(water_tiles))  # More spots
        else:
            tier_range = (1, 2)
            num_spots = min(random.randint(3, 6), len(water_tiles))

        if water_tiles and num_spots > 0:
            spots = random.sample(water_tiles, num_spots)
            for pos in spots:
                tier = random.randint(tier_range[0], tier_range[1])
                self.resources.append(NaturalResource(pos, ResourceType.FISHING_SPOT, tier=tier))

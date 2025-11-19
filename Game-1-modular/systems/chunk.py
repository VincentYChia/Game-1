"""Chunk system for world generation"""

import random
from typing import Dict, List

from data.models import Position, TileType, WorldTile, ChunkType, ResourceType, RESOURCE_TIERS
from systems.natural_resource import NaturalResource
from core.config import Config


class Chunk:
    def __init__(self, chunk_x: int, chunk_y: int):
        self.chunk_x = chunk_x
        self.chunk_y = chunk_y
        self.tiles: Dict[str, WorldTile] = {}
        self.resources: List[NaturalResource] = []
        self.chunk_type = self._determine_chunk_type()
        self.generate_tiles()
        self.spawn_resources()

    def _determine_chunk_type(self) -> ChunkType:
        roll = random.randint(1, 10)
        if roll <= 5:
            return random.choice([ChunkType.PEACEFUL_FOREST, ChunkType.PEACEFUL_QUARRY, ChunkType.PEACEFUL_CAVE])
        elif roll <= 8:
            return random.choice([ChunkType.DANGEROUS_FOREST, ChunkType.DANGEROUS_QUARRY, ChunkType.DANGEROUS_CAVE])
        return random.choice([ChunkType.RARE_HIDDEN_FOREST, ChunkType.RARE_ANCIENT_QUARRY, ChunkType.RARE_DEEP_CAVE])

    def generate_tiles(self):
        start_x, start_y = self.chunk_x * Config.CHUNK_SIZE, self.chunk_y * Config.CHUNK_SIZE
        base_tile = TileType.STONE if "quarry" in self.chunk_type.value or "cave" in self.chunk_type.value else TileType.GRASS
        for x in range(start_x, start_x + Config.CHUNK_SIZE):
            for y in range(start_y, start_y + Config.CHUNK_SIZE):
                pos = Position(x, y, 0)
                self.tiles[pos.to_key()] = WorldTile(pos, TileType.DIRT if random.random() < 0.1 else base_tile)

    def spawn_resources(self):
        start_x, start_y = self.chunk_x * Config.CHUNK_SIZE, self.chunk_y * Config.CHUNK_SIZE
        if "peaceful" in self.chunk_type.value:
            resource_count, tier_range = random.randint(3, 6), (1, 2)
        elif "dangerous" in self.chunk_type.value:
            resource_count, tier_range = random.randint(5, 8), (2, 3)
        else:
            resource_count, tier_range = random.randint(6, 10), (3, 4)

        for _ in range(resource_count):
            pos = Position(start_x + random.randint(1, Config.CHUNK_SIZE - 2),
                           start_y + random.randint(1, Config.CHUNK_SIZE - 2), 0)
            if "forest" in self.chunk_type.value:
                types = [ResourceType.OAK_TREE, ResourceType.BIRCH_TREE, ResourceType.MAPLE_TREE,
                         ResourceType.IRONWOOD_TREE]
            elif "quarry" in self.chunk_type.value:
                types = [ResourceType.LIMESTONE, ResourceType.GRANITE, ResourceType.OBSIDIAN, ResourceType.STAR_CRYSTAL]
            else:
                types = [ResourceType.COPPER_ORE, ResourceType.IRON_ORE, ResourceType.STEEL_ORE,
                         ResourceType.MITHRIL_ORE]

            tier = min(random.randint(*tier_range), 4)
            valid = [r for r in types if RESOURCE_TIERS[r] <= tier]
            if valid:
                resource_type = random.choice(valid)
                self.resources.append(NaturalResource(pos, resource_type, RESOURCE_TIERS[resource_type]))

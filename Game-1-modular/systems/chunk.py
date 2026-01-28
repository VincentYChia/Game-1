"""Chunk system for world generation - uses ResourceNodeDatabase for JSON-driven resources"""

import random
from typing import Dict, List, Optional

from data.models import Position, TileType, WorldTile, ChunkType, ResourceType, RESOURCE_TIERS
from data.databases.resource_node_db import ResourceNodeDatabase
from systems.natural_resource import NaturalResource
from core.config import Config


class Chunk:
    # Class-level reference to database (initialized once)
    _resource_db: Optional[ResourceNodeDatabase] = None

    def __init__(self, chunk_x: int, chunk_y: int):
        self.chunk_x = chunk_x
        self.chunk_y = chunk_y
        self.tiles: Dict[str, WorldTile] = {}
        self.resources: List[NaturalResource] = []
        self.chunk_type = self._determine_chunk_type()
        self.generate_tiles()
        self.spawn_resources()

    @classmethod
    def get_resource_db(cls) -> ResourceNodeDatabase:
        """Get the ResourceNodeDatabase singleton"""
        if cls._resource_db is None:
            cls._resource_db = ResourceNodeDatabase.get_instance()
        return cls._resource_db

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
        """Spawn resources using JSON-driven ResourceNodeDatabase"""
        start_x, start_y = self.chunk_x * Config.CHUNK_SIZE, self.chunk_y * Config.CHUNK_SIZE

        # Determine resource count and tier range based on chunk danger level
        if "peaceful" in self.chunk_type.value:
            resource_count, tier_range = random.randint(3, 6), (1, 2)
        elif "dangerous" in self.chunk_type.value:
            resource_count, tier_range = random.randint(5, 8), (2, 3)
        else:  # rare chunks
            resource_count, tier_range = random.randint(6, 10), (3, 4)

        # Get resource candidates from database
        db = self.get_resource_db()
        if db.loaded:
            # Use database for resource selection (JSON-driven)
            candidates = db.get_resources_for_chunk(self.chunk_type.value, tier_range)
            if candidates:
                for _ in range(resource_count):
                    pos = Position(
                        start_x + random.randint(1, Config.CHUNK_SIZE - 2),
                        start_y + random.randint(1, Config.CHUNK_SIZE - 2),
                        0
                    )
                    # Filter by tier within range
                    tier = min(random.randint(*tier_range), 4)
                    valid = [r for r in candidates if r.tier <= tier]
                    if valid:
                        node_def = random.choice(valid)
                        # Convert to ResourceType enum for NaturalResource
                        try:
                            resource_type = ResourceType(node_def.resource_id)
                        except ValueError:
                            # If not in enum, skip (shouldn't happen with proper enum)
                            continue
                        self.resources.append(NaturalResource(pos, resource_type, node_def.tier))
                return

        # Fallback: Use hardcoded types if database not loaded
        self._spawn_resources_fallback(start_x, start_y, resource_count, tier_range)

    def _spawn_resources_fallback(self, start_x: int, start_y: int, resource_count: int, tier_range: tuple):
        """Fallback resource spawning using hardcoded types (for backwards compatibility)"""
        for _ in range(resource_count):
            pos = Position(
                start_x + random.randint(1, Config.CHUNK_SIZE - 2),
                start_y + random.randint(1, Config.CHUNK_SIZE - 2),
                0
            )

            # Determine resource types based on chunk category
            if "forest" in self.chunk_type.value:
                types = [
                    ResourceType.OAK_TREE, ResourceType.PINE_TREE, ResourceType.ASH_TREE,
                    ResourceType.BIRCH_TREE, ResourceType.MAPLE_TREE, ResourceType.IRONWOOD_TREE,
                    ResourceType.EBONY_TREE, ResourceType.WORLDTREE_SAPLING
                ]
            elif "quarry" in self.chunk_type.value:
                types = [
                    ResourceType.LIMESTONE_OUTCROP, ResourceType.GRANITE_FORMATION, ResourceType.SHALE_BED,
                    ResourceType.BASALT_COLUMN, ResourceType.MARBLE_QUARRY, ResourceType.QUARTZ_CLUSTER,
                    ResourceType.OBSIDIAN_FLOW, ResourceType.VOIDSTONE_SHARD, ResourceType.DIAMOND_GEODE,
                    ResourceType.ETERNITY_MONOLITH, ResourceType.PRIMORDIAL_FORMATION, ResourceType.GENESIS_STRUCTURE
                ]
            else:  # cave
                types = [
                    ResourceType.COPPER_VEIN, ResourceType.IRON_DEPOSIT, ResourceType.TIN_SEAM,
                    ResourceType.STEEL_NODE, ResourceType.MITHRIL_CACHE, ResourceType.ADAMANTINE_LODE,
                    ResourceType.ORICHALCUM_TROVE, ResourceType.ETHERION_NEXUS
                ]

            tier = min(random.randint(*tier_range), 4)
            valid = [r for r in types if RESOURCE_TIERS.get(r, 1) <= tier]
            if valid:
                resource_type = random.choice(valid)
                self.resources.append(NaturalResource(pos, resource_type, RESOURCE_TIERS.get(resource_type, 1)))

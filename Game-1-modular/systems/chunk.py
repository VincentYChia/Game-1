"""Chunk system for world generation - uses ResourceNodeDatabase for JSON-driven resources

Uses centered coordinate system where (0,0) is world center.
Supports infinite world expansion through seed-based deterministic generation.
"""

import random
import math
from typing import Dict, List, Set, Tuple, Optional, ClassVar, TYPE_CHECKING

from data.models import Position, TileType, WorldTile, ChunkType, ResourceType, RESOURCE_TIERS
from data.databases.resource_node_db import ResourceNodeDatabase
from systems.natural_resource import NaturalResource
from core.config import Config

if TYPE_CHECKING:
    from systems.biome_generator import BiomeGenerator


class Chunk:
    """A 16x16 tile chunk of the world.

    Coordinates use centered system where chunk (0,0) contains the origin.
    Chunks can be generated at any coordinate for infinite world support.

    Attributes:
        chunk_x: Chunk X coordinate
        chunk_y: Chunk Y coordinate
        seed: Deterministic seed for this chunk
        tiles: Dictionary of tiles keyed by position string
        resources: List of natural resources in this chunk
        chunk_type: The biome/type of this chunk
        dungeon_entrance: Optional dungeon entrance in this chunk
        unload_timestamp: Game time when chunk was unloaded (for respawn calculation)
    """

    # Class-level reference to database (initialized once)
    _resource_db: ClassVar[Optional[ResourceNodeDatabase]] = None

    # Legacy class-level water tracking (kept for save compatibility)
    _water_chunks: ClassVar[Set[Tuple[int, int]]] = set()
    _initialized: ClassVar[bool] = False

    @classmethod
    def get_resource_db(cls) -> ResourceNodeDatabase:
        """Get the ResourceNodeDatabase singleton"""
        if cls._resource_db is None:
            cls._resource_db = ResourceNodeDatabase.get_instance()
        return cls._resource_db

    @classmethod
    def restore_water_chunks(cls, water_chunk_positions: List[Tuple[int, int]]) -> None:
        """Restore water chunk positions from legacy save data.

        This method exists for backwards compatibility with saves that used
        the old water planning system. New saves use seed-based generation.

        Args:
            water_chunk_positions: List of (chunk_x, chunk_y) tuples for water chunks
        """
        if water_chunk_positions:
            cls._water_chunks = set(tuple(pos) for pos in water_chunk_positions)
            cls._initialized = True
            print(f"🌊 Restored {len(cls._water_chunks)} water chunks from legacy save")

    def __init__(self, chunk_x: int, chunk_y: int,
                 seed: Optional[int] = None,
                 biome_generator: Optional['BiomeGenerator'] = None):
        """Initialize a chunk at the given coordinates.

        Args:
            chunk_x: Chunk X coordinate
            chunk_y: Chunk Y coordinate
            seed: Deterministic seed for this chunk (optional, for legacy support)
            biome_generator: BiomeGenerator instance for chunk type determination
        """
        self.chunk_x = chunk_x
        self.chunk_y = chunk_y

        # Store biome generator reference
        self._biome_generator = biome_generator

        # Get seed - either from biome generator, passed directly, or generate random
        if biome_generator:
            self.seed = biome_generator.get_chunk_seed(chunk_x, chunk_y)
        elif seed is not None:
            self.seed = seed
        else:
            # Legacy mode - random seed (not recommended for infinite worlds)
            self.seed = random.randint(0, 2**32 - 1)

        # Create seeded RNG for deterministic generation
        self._rng = random.Random(self.seed)

        # Initialize data structures
        self.tiles: Dict[str, WorldTile] = {}
        self.resources: List[NaturalResource] = []
        self.dungeon_entrance = None  # Set by WorldSystem if dungeon spawns here
        self.unload_timestamp: Optional[float] = None  # For respawn calculation on reload

        # Modification tracking for save system
        self._modified = False
        self._resource_modifications: Dict[str, dict] = {}

        # Determine chunk type and generate content
        self.chunk_type = self._determine_chunk_type()
        self.generate_tiles()
        self.spawn_resources()

    def _determine_chunk_type(self) -> ChunkType:
        """Determine chunk type using BiomeGenerator or legacy random.

        Returns:
            ChunkType for this chunk
        """
        # Use BiomeGenerator if available (new infinite world system)
        if self._biome_generator:
            return self._biome_generator.get_chunk_type(self.chunk_x, self.chunk_y)

        # Legacy mode: check class-level water chunks first
        if Chunk._initialized and (self.chunk_x, self.chunk_y) in Chunk._water_chunks:
            return self._rng.choice([ChunkType.WATER_LAKE, ChunkType.WATER_RIVER])

        # Spawn area protection: center 3x3 chunks are always peaceful
        if abs(self.chunk_x) <= 1 and abs(self.chunk_y) <= 1:
            return self._rng.choice([
                ChunkType.PEACEFUL_FOREST,
                ChunkType.PEACEFUL_QUARRY,
                ChunkType.PEACEFUL_CAVE
            ])

        # Legacy random distribution
        roll = self._rng.randint(1, 10)
        if roll <= 5:
            return self._rng.choice([
                ChunkType.PEACEFUL_FOREST,
                ChunkType.PEACEFUL_QUARRY,
                ChunkType.PEACEFUL_CAVE
            ])
        elif roll <= 8:
            return self._rng.choice([
                ChunkType.DANGEROUS_FOREST,
                ChunkType.DANGEROUS_QUARRY,
                ChunkType.DANGEROUS_CAVE
            ])
        else:
            # Rare chunks (20% chance): 75% land rare, 25% cursed swamp
            if self._rng.random() < 0.25:
                return ChunkType.WATER_CURSED_SWAMP
            return self._rng.choice([
                ChunkType.RARE_HIDDEN_FOREST,
                ChunkType.RARE_ANCIENT_QUARRY,
                ChunkType.RARE_DEEP_CAVE
            ])

    def _is_water_chunk(self) -> bool:
        """Check if this chunk is a water type."""
        return self.chunk_type in (
            ChunkType.WATER_LAKE,
            ChunkType.WATER_RIVER,
            ChunkType.WATER_CURSED_SWAMP
        )

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
        is_stone_biome = "quarry" in self.chunk_type.value or "cave" in self.chunk_type.value
        base_tile = TileType.STONE if is_stone_biome else TileType.GRASS

        for x in range(start_x, start_x + Config.CHUNK_SIZE):
            for y in range(start_y, start_y + Config.CHUNK_SIZE):
                pos = Position(x, y, 0)
                tile_type = TileType.DIRT if self._rng.random() < 0.1 else base_tile
                self.tiles[pos.to_key()] = WorldTile(pos, tile_type)

    def _generate_water_tiles(self, start_x: int, start_y: int):
        """Generate water tiles with guaranteed land border for passability.

        Lakes have circular water pattern with land border.
        Rivers have flowing water through the middle.
        Cursed swamps have 50% water coverage with paths.
        """
        chunk_size = Config.CHUNK_SIZE
        is_swamp = self.chunk_type == ChunkType.WATER_CURSED_SWAMP
        is_lake = self.chunk_type == ChunkType.WATER_LAKE

        center_x = chunk_size // 2
        center_y = chunk_size // 2

        for local_x in range(chunk_size):
            for local_y in range(chunk_size):
                x = start_x + local_x
                y = start_y + local_y
                pos = Position(x, y, 0)

                # Determine tile type based on water pattern
                if is_lake:
                    # Lake: circular pattern with land border
                    dist_from_center = math.sqrt(
                        (local_x - center_x) ** 2 + (local_y - center_y) ** 2
                    )
                    # Land border (outer 2 tiles)
                    if (local_x < 2 or local_x >= chunk_size - 2 or
                            local_y < 2 or local_y >= chunk_size - 2):
                        tile_type = TileType.GRASS
                    elif dist_from_center < 5:  # Water in center
                        tile_type = TileType.WATER
                    else:
                        tile_type = TileType.GRASS

                elif is_swamp:
                    # Cursed swamp: 50% water with 4-way land paths
                    is_path = (abs(local_x - center_x) < 2) or (abs(local_y - center_y) < 2)
                    if is_path:
                        tile_type = TileType.DIRT
                    elif self._rng.random() < 0.5:
                        tile_type = TileType.WATER
                    else:
                        tile_type = TileType.DIRT

                else:
                    # River: create a flowing pattern through the middle
                    dist_from_center = abs(local_x - chunk_size // 2)
                    if dist_from_center < 3 and self._rng.random() < 0.8:
                        tile_type = TileType.WATER
                    else:
                        tile_type = TileType.GRASS

                self.tiles[pos.to_key()] = WorldTile(
                    pos, tile_type, walkable=(tile_type != TileType.WATER)
                )

    def spawn_resources(self):
        """Spawn resources using JSON-driven ResourceNodeDatabase"""
        # Handle water chunks separately (fishing spots)
        if self._is_water_chunk():
            self._spawn_fishing_spots()
            return

        start_x = self.chunk_x * Config.CHUNK_SIZE
        start_y = self.chunk_y * Config.CHUNK_SIZE

        # Determine resource count and tier range based on chunk danger level
        if "peaceful" in self.chunk_type.value:
            resource_count = self._rng.randint(3, 6)
            tier_range = (1, 2)
        elif "dangerous" in self.chunk_type.value:
            resource_count = self._rng.randint(5, 8)
            tier_range = (2, 3)
        else:  # rare chunks
            resource_count = self._rng.randint(6, 10)
            tier_range = (3, 4)

        # Track occupied positions to prevent overlap
        occupied_positions: Set[Tuple[int, int]] = set()

        # Get resource candidates from database
        db = self.get_resource_db()
        if db.loaded:
            candidates = db.get_resources_for_chunk(self.chunk_type.value, tier_range)
            if candidates:
                for _ in range(resource_count):
                    pos = self._find_resource_position(
                        start_x, start_y, occupied_positions
                    )
                    if pos is None:
                        continue

                    # Filter by tier within range
                    tier = min(self._rng.randint(*tier_range), 4)
                    valid = [r for r in candidates if r.tier <= tier]
                    if valid:
                        node_def = self._rng.choice(valid)
                        try:
                            resource_type = ResourceType(node_def.resource_id)
                            self.resources.append(
                                NaturalResource(pos, resource_type, node_def.tier)
                            )
                        except ValueError:
                            continue
                return

        # Fallback: Use hardcoded types if database not loaded
        self._spawn_resources_fallback(
            start_x, start_y, resource_count, tier_range, occupied_positions
        )

    def _find_resource_position(self, start_x: int, start_y: int,
                                occupied: Set[Tuple[int, int]]) -> Optional[Position]:
        """Find a valid position for a resource within this chunk.

        Args:
            start_x: Chunk start X coordinate
            start_y: Chunk start Y coordinate
            occupied: Set of already-occupied positions

        Returns:
            Valid Position or None if no position found
        """
        for _ in range(10):  # Up to 10 attempts
            candidate_x = start_x + self._rng.randint(1, Config.CHUNK_SIZE - 2)
            candidate_y = start_y + self._rng.randint(1, Config.CHUNK_SIZE - 2)

            # Check safe zone around origin (0, 0)
            dist_to_origin = math.sqrt(candidate_x ** 2 + candidate_y ** 2)
            if dist_to_origin < Config.SAFE_ZONE_RADIUS:
                continue

            # Check collision with existing resources
            if (candidate_x, candidate_y) in occupied:
                continue

            # Valid position found
            occupied.add((candidate_x, candidate_y))
            return Position(candidate_x, candidate_y, 0)

        return None

    def _spawn_resources_fallback(self, start_x: int, start_y: int,
                                  resource_count: int, tier_range: tuple,
                                  occupied_positions: Set[Tuple[int, int]]):
        """Fallback resource spawning using hardcoded types."""
        for _ in range(resource_count):
            pos = self._find_resource_position(start_x, start_y, occupied_positions)
            if pos is None:
                continue

            # Determine resource types based on chunk category
            if "forest" in self.chunk_type.value:
                types = [
                    ResourceType.OAK_TREE, ResourceType.PINE_TREE,
                    ResourceType.ASH_TREE, ResourceType.BIRCH_TREE,
                    ResourceType.MAPLE_TREE, ResourceType.IRONWOOD_TREE,
                    ResourceType.EBONY_TREE, ResourceType.WORLDTREE_SAPLING
                ]
            elif "quarry" in self.chunk_type.value:
                types = [
                    ResourceType.LIMESTONE_OUTCROP, ResourceType.GRANITE_FORMATION,
                    ResourceType.SHALE_BED, ResourceType.BASALT_COLUMN,
                    ResourceType.MARBLE_QUARRY, ResourceType.QUARTZ_CLUSTER,
                    ResourceType.OBSIDIAN_FLOW, ResourceType.VOIDSTONE_SHARD,
                    ResourceType.DIAMOND_GEODE, ResourceType.ETERNITY_MONOLITH,
                    ResourceType.PRIMORDIAL_FORMATION, ResourceType.GENESIS_STRUCTURE
                ]
            else:  # cave
                types = [
                    ResourceType.COPPER_VEIN, ResourceType.IRON_DEPOSIT,
                    ResourceType.TIN_SEAM, ResourceType.STEEL_NODE,
                    ResourceType.MITHRIL_CACHE, ResourceType.ADAMANTINE_LODE,
                    ResourceType.ORICHALCUM_TROVE, ResourceType.ETHERION_NEXUS
                ]

            tier = min(self._rng.randint(*tier_range), 4)
            valid = [r for r in types if RESOURCE_TIERS.get(r, 1) <= tier]
            if valid:
                resource_type = self._rng.choice(valid)
                self.resources.append(
                    NaturalResource(pos, resource_type, RESOURCE_TIERS.get(resource_type, 1))
                )

    def _spawn_fishing_spots(self):
        """Spawn fishing spots on water tiles."""
        water_tiles = [
            tile.position for tile in self.tiles.values()
            if tile.tile_type == TileType.WATER
        ]

        # Determine tier based on water type
        is_swamp = self.chunk_type == ChunkType.WATER_CURSED_SWAMP
        if is_swamp:
            tier_range = (3, 4)
            num_spots = min(self._rng.randint(5, 8), len(water_tiles))
        else:
            tier_range = (1, 2)
            num_spots = min(self._rng.randint(3, 6), len(water_tiles))

        if water_tiles and num_spots > 0:
            spots = self._rng.sample(water_tiles, num_spots)
            for pos in spots:
                tier = self._rng.randint(tier_range[0], tier_range[1])
                self.resources.append(
                    NaturalResource(pos, ResourceType.FISHING_SPOT, tier=tier)
                )

    # =========================================================================
    # Modification Tracking (for save system)
    # =========================================================================

    def mark_resource_modified(self, resource: NaturalResource):
        """Mark a resource as modified for save tracking.

        Args:
            resource: The modified resource
        """
        local_x = int(resource.position.x) - (self.chunk_x * Config.CHUNK_SIZE)
        local_y = int(resource.position.y) - (self.chunk_y * Config.CHUNK_SIZE)
        local_key = f"{local_x},{local_y}"

        self._resource_modifications[local_key] = {
            "local_x": local_x,
            "local_y": local_y,
            "resource_type": resource.resource_type.name,
            "current_hp": resource.current_hp,
            "max_hp": resource.max_hp,
            "depleted": resource.depleted,
            "time_until_respawn": resource.time_until_respawn
        }
        self._modified = True

    def has_modifications(self) -> bool:
        """Check if this chunk has any modifications to save."""
        return self._modified or self.dungeon_entrance is not None

    def get_save_data(self) -> Optional[dict]:
        """Get save data for this chunk.

        Returns:
            Dictionary of chunk modifications, or None if no modifications
        """
        if not self.has_modifications():
            return None

        data = {
            "chunk_x": self.chunk_x,
            "chunk_y": self.chunk_y,
            "chunk_type": self.chunk_type.value,
        }

        if self._resource_modifications:
            data["modified_resources"] = list(self._resource_modifications.values())

        if self.dungeon_entrance:
            data["dungeon_entrance"] = {
                "position": {
                    "x": self.dungeon_entrance.position.x,
                    "y": self.dungeon_entrance.position.y,
                    "z": self.dungeon_entrance.position.z
                },
                "rarity": self.dungeon_entrance.rarity.value
            }

        if self.unload_timestamp is not None:
            data["unload_timestamp"] = self.unload_timestamp

        return data

    def restore_modifications(self, save_data: dict, elapsed_time: float = 0.0):
        """Restore chunk state from save data.

        Args:
            save_data: Chunk save data dictionary
            elapsed_time: Time elapsed since chunk was saved (for respawn calculation)
        """
        # Restore resource modifications
        modified_resources = save_data.get("modified_resources", [])

        # Create lookup by local position
        mod_lookup = {}
        for mod in modified_resources:
            key = f"{mod['local_x']},{mod['local_y']}"
            mod_lookup[key] = mod

        # Apply modifications to resources
        for resource in self.resources:
            local_x = int(resource.position.x) - (self.chunk_x * Config.CHUNK_SIZE)
            local_y = int(resource.position.y) - (self.chunk_y * Config.CHUNK_SIZE)
            key = f"{local_x},{local_y}"

            if key in mod_lookup:
                mod = mod_lookup[key]
                resource.current_hp = mod.get("current_hp", resource.max_hp)
                resource.depleted = mod.get("depleted", False)
                resource.time_until_respawn = mod.get("time_until_respawn", 0.0)

                # Add elapsed time for respawn calculation
                if resource.depleted and resource.respawns and elapsed_time > 0:
                    resource.time_until_respawn += elapsed_time
                    # Check if resource should have respawned
                    if resource.respawn_timer and resource.time_until_respawn >= resource.respawn_timer:
                        resource.current_hp = resource.max_hp
                        resource.depleted = False
                        resource.time_until_respawn = 0.0

        # Mark modifications as restored
        self._resource_modifications = mod_lookup
        self._modified = bool(mod_lookup)

    def prepare_for_unload(self, game_time: float):
        """Prepare chunk for unloading by recording timestamp.

        Args:
            game_time: Current game time for respawn calculation
        """
        self.unload_timestamp = game_time

        # Update modifications for any resources that have been changed
        for resource in self.resources:
            if (resource.current_hp < resource.max_hp or
                    resource.depleted or
                    resource.time_until_respawn > 0):
                self.mark_resource_modified(resource)

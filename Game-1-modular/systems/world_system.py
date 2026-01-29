"""World system for managing the game world, tiles, resources, and stations"""

import random
from typing import Dict, List, Optional, Tuple

from data.models import Position, WorldTile, TileType, StationType, CraftingStation, PlacedEntity, PlacedEntityType, DungeonRarity, DungeonEntrance
from data.models.world import DUNGEON_CONFIG
from systems.natural_resource import NaturalResource
from systems.chunk import Chunk
from core.config import Config


class WorldSystem:
    def __init__(self):
        self.tiles: Dict[str, WorldTile] = {}
        self.chunks: Dict[Tuple[int, int], Chunk] = {}
        self.resources: List[NaturalResource] = []
        self.crafting_stations: List[CraftingStation] = []
        self.placed_entities: List[PlacedEntity] = []  # Player-placed turrets, traps, stations, etc.
        self.dungeon_entrances: List[DungeonEntrance] = []  # Dungeon entrance locations
        self.dungeon_manager = None  # Set by game_engine for dungeon tile lookups
        self.generate_world()
        self.spawn_starting_stations()
        self.spawn_dungeon_entrances()

    def generate_world(self):
        """Generate world with centered coordinate system.

        Chunks are indexed from -half to +half (e.g., -5 to +5 for 11 chunks).
        Tile coordinates range from -WORLD_SIZE/2 to +WORLD_SIZE/2.
        Origin (0,0,0) is at the center of the world.
        """
        half_chunks = Config.NUM_CHUNKS // 2  # 5 for 11 chunks
        for chunk_x in range(-half_chunks, half_chunks + 1):
            for chunk_y in range(-half_chunks, half_chunks + 1):
                chunk = Chunk(chunk_x, chunk_y)
                self.chunks[(chunk_x, chunk_y)] = chunk
                self.tiles.update(chunk.tiles)
                self.resources.extend(chunk.resources)
        print(f"Generated {Config.NUM_CHUNKS}x{Config.NUM_CHUNKS} chunk world ({Config.WORLD_SIZE}x{Config.WORLD_SIZE} tiles), {len(self.resources)} resources")

    def spawn_starting_stations(self):
        """Spawn all tiers of crafting stations near player spawn at origin (0, 0).

        Stations are placed NORTH of spawn (negative Y) in a grid layout
        to avoid collision with player spawn position.
        """
        # Station layout: spread horizontally around X=0, placed north (Y < 0)
        # Format: (base_x, station_type)
        station_positions = [
            (-8, StationType.SMITHING),      # Far left
            (-4, StationType.REFINING),      # Left
            (0, StationType.ADORNMENTS),     # Center
            (4, StationType.ALCHEMY),        # Right
            (8, StationType.ENGINEERING),    # Far right
        ]

        # Spawn T1-T4 of each station type, arranged vertically going north
        # T1 closest to spawn (-10), T4 furthest (-16)
        for base_x, stype in station_positions:
            for tier in range(1, 5):  # T1, T2, T3, T4
                y = -10 - (tier - 1) * 2  # -10, -12, -14, -16 (north of spawn)
                self.crafting_stations.append(CraftingStation(Position(base_x, y, 0), stype, tier))

    def spawn_dungeon_entrances(self):
        """Spawn dungeon entrances across the world.

        Target: ~1 entrance per 12 chunks on average.
        Avoids spawn area (within 20 tiles of origin).
        Each entrance has a pre-rolled rarity based on spawn weights.
        """
        half_chunks = Config.NUM_CHUNKS // 2  # 5 for 11 chunks
        total_chunks = Config.NUM_CHUNKS * Config.NUM_CHUNKS  # 121 chunks for 11x11

        # Target ~1 dungeon per 12 chunks = about 10 dungeons total for 121 chunks
        target_dungeons = max(1, total_chunks // 12)

        # Use a probability per chunk approach for more even distribution
        spawn_chance_per_chunk = target_dungeons / total_chunks  # ~0.083

        dungeon_count = 0
        for chunk_x in range(-half_chunks, half_chunks + 1):
            for chunk_y in range(-half_chunks, half_chunks + 1):
                # Skip spawn area chunks (chunks near 0,0)
                if abs(chunk_x) <= 1 and abs(chunk_y) <= 1:
                    continue

                # Roll for dungeon spawn
                if random.random() < spawn_chance_per_chunk:
                    # Generate position within chunk (avoid edges)
                    tile_x = chunk_x * Config.CHUNK_SIZE + random.randint(2, Config.CHUNK_SIZE - 3)
                    tile_y = chunk_y * Config.CHUNK_SIZE + random.randint(2, Config.CHUNK_SIZE - 3)

                    # Ensure position is on walkable terrain
                    pos = Position(tile_x, tile_y, 0)
                    tile = self.get_tile(pos)
                    if tile and tile.tile_type != TileType.WATER:
                        # Roll rarity based on spawn weights
                        rarity = self._roll_dungeon_rarity()
                        entrance = DungeonEntrance(position=pos, rarity=rarity)
                        self.dungeon_entrances.append(entrance)
                        dungeon_count += 1

        print(f"Generated {dungeon_count} dungeon entrances across the world")

    def _roll_dungeon_rarity(self) -> DungeonRarity:
        """Roll for dungeon rarity based on spawn weights."""
        total_weight = sum(DUNGEON_CONFIG[r]["spawn_weight"] for r in DungeonRarity)
        roll = random.randint(1, total_weight)

        cumulative = 0
        for rarity in DungeonRarity:
            cumulative += DUNGEON_CONFIG[rarity]["spawn_weight"]
            if roll <= cumulative:
                return rarity

        return DungeonRarity.COMMON  # Fallback

    def get_visible_dungeon_entrances(self, camera_pos: Position, vw: int, vh: int) -> List[DungeonEntrance]:
        """Get all dungeon entrances visible in the camera viewport."""
        tw, th = vw // Config.TILE_SIZE + 2, vh // Config.TILE_SIZE + 2
        sx, sy = camera_pos.x - tw // 2, camera_pos.y - th // 2
        ex, ey = camera_pos.x + tw // 2, camera_pos.y + th // 2
        return [e for e in self.dungeon_entrances if sx <= e.position.x <= ex and sy <= e.position.y <= ey]

    def get_dungeon_entrance_at(self, position: Position, tolerance: float = 1.0) -> Optional[DungeonEntrance]:
        """Get dungeon entrance at position with tolerance for easier clicking."""
        for entrance in self.dungeon_entrances:
            dx = abs(entrance.position.x - position.x)
            dy = abs(entrance.position.y - position.y)
            if dx <= tolerance and dy <= tolerance:
                return entrance
        return None

    def get_tile(self, position: Position) -> Optional[WorldTile]:
        return self.tiles.get(position.snap_to_grid().to_key())

    def is_walkable(self, position: Position) -> bool:
        """Check if a position is walkable (no water, no solid resources).

        When in a dungeon, checks dungeon tiles instead of world tiles.
        """
        # Check if we're in a dungeon - use dungeon tiles instead
        if self.dungeon_manager and self.dungeon_manager.in_dungeon:
            dungeon = self.dungeon_manager.current_dungeon
            if dungeon:
                # Use dungeon tiles
                tile_key = position.snap_to_grid().to_key()
                tile = dungeon.tiles.get(tile_key)
                if not tile:
                    return False
                return tile.walkable
            return False

        # Normal world tile check
        tile = self.get_tile(position)
        if not tile or tile.tile_type == TileType.WATER or not tile.walkable:
            return False

        # Check for non-depleted resources blocking movement
        for resource in self.resources:
            if not resource.depleted:
                # Check if player center would overlap with resource
                dx = abs(resource.position.x - position.x)
                dy = abs(resource.position.y - position.y)
                if dx < 0.5 and dy < 0.5:  # Resource occupies ~1 tile
                    return False

        return True

    def get_visible_tiles(self, camera_pos: Position, vw: int, vh: int) -> List[WorldTile]:
        tw, th = vw // Config.TILE_SIZE + 2, vh // Config.TILE_SIZE + 2
        sx, sy = int(camera_pos.x - tw // 2), int(camera_pos.y - th // 2)
        visible = []
        for x in range(sx, sx + tw):
            for y in range(sy, sy + th):
                tile = self.get_tile(Position(x, y, 0))
                if tile:
                    visible.append(tile)
        return visible

    def get_visible_resources(self, camera_pos: Position, vw: int, vh: int) -> List[NaturalResource]:
        tw, th = vw // Config.TILE_SIZE + 2, vh // Config.TILE_SIZE + 2
        sx, sy = camera_pos.x - tw // 2, camera_pos.y - th // 2
        ex, ey = camera_pos.x + tw // 2, camera_pos.y + th // 2
        return [r for r in self.resources if sx <= r.position.x <= ex and sy <= r.position.y <= ey]

    def get_resource_at(self, position: Position, tolerance: float = Config.CLICK_TOLERANCE) -> Optional[
        NaturalResource]:
        for r in self.resources:
            if not r.depleted:
                dx = abs(r.position.x - position.x)
                dy = abs(r.position.y - position.y)
                if dx <= tolerance and dy <= tolerance:
                    return r
        return None

    def get_visible_stations(self, camera_pos: Position, vw: int, vh: int) -> List[CraftingStation]:
        tw, th = vw // Config.TILE_SIZE + 2, vh // Config.TILE_SIZE + 2
        sx, sy = camera_pos.x - tw // 2, camera_pos.y - th // 2
        ex, ey = camera_pos.x + tw // 2, camera_pos.y + th // 2
        return [s for s in self.crafting_stations if sx <= s.position.x <= ex and sy <= s.position.y <= ey]

    def get_station_at(self, position: Position, tolerance: float = 0.8) -> Optional[CraftingStation]:
        """Get station at position with tolerance for easier clicking"""
        for s in self.crafting_stations:
            dx = abs(s.position.x - position.x)
            dy = abs(s.position.y - position.y)
            if dx <= tolerance and dy <= tolerance:
                return s
        return None

    def place_entity(self, position: Position, item_id: str, entity_type: PlacedEntityType,
                     tier: int = 1, range: float = 5.0, damage: float = 20.0,
                     tags: List[str] = None, effect_params: dict = None,
                     crafted_stats: dict = None) -> PlacedEntity:
        """Place an entity (turret, trap, station, etc.) in the world"""
        entity = PlacedEntity(
            position=position.snap_to_grid(),
            item_id=item_id,
            entity_type=entity_type,
            tier=tier,
            range=range,
            damage=damage,
            tags=tags,
            effect_params=effect_params,
            crafted_stats=crafted_stats
        )
        self.placed_entities.append(entity)
        return entity

    def remove_entity(self, entity: PlacedEntity) -> bool:
        """Remove a placed entity from the world"""
        if entity in self.placed_entities:
            self.placed_entities.remove(entity)
            return True
        return False

    def get_entity_at(self, position: Position, tolerance: float = 0.8) -> Optional[PlacedEntity]:
        """Get placed entity at position with tolerance for easier clicking"""
        for entity in self.placed_entities:
            dx = abs(entity.position.x - position.x)
            dy = abs(entity.position.y - position.y)
            if dx <= tolerance and dy <= tolerance:
                return entity
        return None

    def get_visible_placed_entities(self, camera_pos: Position, vw: int, vh: int) -> List[PlacedEntity]:
        """Get all placed entities visible in the camera viewport"""
        tw, th = vw // Config.TILE_SIZE + 2, vh // Config.TILE_SIZE + 2
        sx, sy = camera_pos.x - tw // 2, camera_pos.y - th // 2
        ex, ey = camera_pos.x + tw // 2, camera_pos.y + tw // 2
        return [e for e in self.placed_entities if sx <= e.position.x <= ex and sy <= e.position.y <= ey]

    def update(self, dt: float):
        for r in self.resources:
            r.update(dt)

    def restore_from_save(self, world_state: dict):
        """
        Restore world state from save data.

        This includes:
        - Placed entities (turrets, traps, devices, player-placed stations)
        - Modified resources (harvested nodes with HP changes)
        - Player-placed crafting stations (if any)

        Args:
            world_state: Dictionary containing world state data from save file
        """
        # Clear existing placed entities
        self.placed_entities.clear()

        # Restore placed entities
        for entity_data in world_state.get("placed_entities", []):
            position = Position(
                entity_data["position"]["x"],
                entity_data["position"]["y"],
                entity_data["position"]["z"]
            )

            # Convert string entity type back to enum
            from data.models.world import PlacedEntityType
            entity_type = PlacedEntityType[entity_data["entity_type"]]

            # Create the placed entity
            entity = PlacedEntity(
                position=position,
                item_id=entity_data["item_id"],
                entity_type=entity_type,
                tier=entity_data.get("tier", 1),
                health=entity_data.get("health", 100.0),
                owner=entity_data.get("owner"),
                time_remaining=entity_data.get("time_remaining", 300.0),
                tags=entity_data.get("tags"),
                effect_params=entity_data.get("effect_params")
            )

            # Restore turret-specific properties
            if "range" in entity_data:
                entity.range = entity_data["range"]
                entity.damage = entity_data["damage"]
                entity.attack_speed = entity_data["attack_speed"]

            self.placed_entities.append(entity)

        # Restore modified resources
        # Create a mapping of position -> saved resource data for quick lookup
        modified_resources_map = {}
        for resource_data in world_state.get("modified_resources", []):
            pos_key = f"{resource_data['position']['x']},{resource_data['position']['y']},{resource_data['position']['z']}"
            modified_resources_map[pos_key] = resource_data

        # Apply modifications to existing resources
        for resource in self.resources:
            pos_key = f"{resource.position.x},{resource.position.y},{resource.position.z}"
            if pos_key in modified_resources_map:
                resource_data = modified_resources_map[pos_key]

                # Restore resource state
                resource.current_hp = resource_data.get("current_hp", resource.max_hp)
                resource.depleted = resource_data.get("depleted", False)
                resource.time_until_respawn = resource_data.get("time_until_respawn", 0.0)

        # Restore player-placed crafting stations (if different from default spawns)
        # For now, we'll keep the default stations and only add extras
        saved_stations = world_state.get("crafting_stations", [])
        if saved_stations:
            # Clear and restore all stations from save
            self.crafting_stations.clear()
            for station_data in saved_stations:
                position = Position(
                    station_data["position"]["x"],
                    station_data["position"]["y"],
                    station_data["position"]["z"]
                )

                # Convert string station type back to enum
                station_type = StationType[station_data["station_type"]]

                station = CraftingStation(
                    position=position,
                    station_type=station_type,
                    tier=station_data.get("tier", 1)
                )

                self.crafting_stations.append(station)

        print(f"Restored {len(self.placed_entities)} placed entities and {len(modified_resources_map)} modified resources")

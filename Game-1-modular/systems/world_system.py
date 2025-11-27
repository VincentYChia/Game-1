"""World system for managing the game world, tiles, resources, and stations"""

from typing import Dict, List, Optional, Tuple

from data.models import Position, WorldTile, TileType, StationType, CraftingStation, PlacedEntity, PlacedEntityType
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
        self.generate_world()
        self.spawn_starting_stations()

    def generate_world(self):
        num_chunks = Config.WORLD_SIZE // Config.CHUNK_SIZE
        for chunk_x in range(num_chunks):
            for chunk_y in range(num_chunks):
                chunk = Chunk(chunk_x, chunk_y)
                self.chunks[(chunk_x, chunk_y)] = chunk
                self.tiles.update(chunk.tiles)
                self.resources.extend(chunk.resources)
        print(f"Generated {Config.WORLD_SIZE}x{Config.WORLD_SIZE} world, {len(self.resources)} resources")

    def spawn_starting_stations(self):
        """Spawn all tiers of crafting stations near player start (50, 50)"""
        # Place all 4 tiers of each station type in a grid layout
        # Format: (base_x, base_y, station_type)
        # Each station type gets T1-T4 arranged vertically

        station_positions = [
            # SMITHING - Far left column
            (44, StationType.SMITHING),
            # REFINING - Left column
            (46, StationType.REFINING),
            # ALCHEMY - Right column
            (54, StationType.ALCHEMY),
            # ENGINEERING - Far right column
            (56, StationType.ENGINEERING),
            # ADORNMENTS/ENCHANTING - Center column
            (50, StationType.ADORNMENTS),
        ]

        # Spawn T1-T4 of each station type
        for base_x, stype in station_positions:
            for tier in range(1, 5):  # T1, T2, T3, T4
                y = 46 + (tier - 1) * 2  # Vertical spacing: 46, 48, 50, 52
                self.crafting_stations.append(CraftingStation(Position(base_x, y, 0), stype, tier))

    def get_tile(self, position: Position) -> Optional[WorldTile]:
        return self.tiles.get(position.snap_to_grid().to_key())

    def is_walkable(self, position: Position) -> bool:
        tile = self.get_tile(position)
        return tile and tile.tile_type != TileType.WATER and tile.walkable

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
                     tier: int = 1, range: float = 5.0, damage: float = 20.0) -> PlacedEntity:
        """Place an entity (turret, trap, station, etc.) in the world"""
        entity = PlacedEntity(
            position=position.snap_to_grid(),
            item_id=item_id,
            entity_type=entity_type,
            tier=tier,
            range=range,
            damage=damage
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
